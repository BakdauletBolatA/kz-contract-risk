"""Оценка извлечения на размеченных договорах.

Считает для одной модели и одного среза:
- долю валидных ответов с первой попытки и после повтора;
- точность по каждому полю; провалившийся документ засчитывается ошибкой
  по всем полям (иначе модель, часто отвечающая мусором, выглядела бы точнее);
- ошибки по типам: `hallucinated` (в эталоне null, модель назвала значение),
  `missed` (в эталоне значение, модель дала null), `wrong` (оба заданы, не совпали);
- латентность и токены на документ, стоимость на 100 документов по `config/pricing.yaml`.
"""

from __future__ import annotations

import json
import math
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from contract_risk.extraction.extractor import (
    PROMPT_VERSION,
    ExtractionResult,
    Extractor,
    extract_many,
)
from contract_risk.extraction.schema import EXTRACTION_FIELDS

ROOT = Path(__file__).resolve().parents[3]
GOLD_DIR = ROOT / "data/extraction_gold"
PRICING_PATH = ROOT / "config/pricing.yaml"
SPLITS = ("dev", "test", "hard")
PARTY_FIELDS = ("parties.role_bin", "parties.name")
ALL_FIELDS = (*EXTRACTION_FIELDS, *PARTY_FIELDS)

_LEGAL = re.compile(r"\b(тоо|ип|ао|жшс|жк|ооо)\b", re.IGNORECASE)


@dataclass
class GoldDoc:
    doc_id: str
    split: str
    text: str
    labels: dict[str, Any]


def load_gold(split: str, root: Path = ROOT) -> list[GoldDoc]:
    docs = []
    for line in (GOLD_DIR / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            text = (root / r["path"]).read_text(encoding="utf-8")
            docs.append(GoldDoc(r["doc_id"], split, text, r["labels"]))
    return docs


def norm_name(name: str) -> str:
    s = _LEGAL.sub(" ", name.casefold())
    return " ".join(re.sub(r"[«»\"'“”.,]", " ", s).split())


def _same(field: str, gold: Any, pred: Any) -> bool:
    if gold is None or pred is None:
        return gold is None and pred is None
    if isinstance(gold, float) or isinstance(pred, float):
        return math.isclose(float(gold), float(pred), rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(gold, str):
        return str(gold).casefold().strip() == str(pred).casefold().strip()
    return gold == pred


def compare_fields(gold: dict, pred: dict | None) -> dict[str, str]:
    """Для каждого поля: correct | hallucinated | missed | wrong | failed."""
    out: dict[str, str] = {}
    if pred is None:
        return {f: "failed" for f in ALL_FIELDS}
    for f in EXTRACTION_FIELDS:
        g, p = gold[f], pred[f]
        if _same(f, g, p):
            out[f] = "correct"
        elif g is None:
            out[f] = "hallucinated"
        elif p is None:
            out[f] = "missed"
        else:
            out[f] = "wrong"
    gp = {(x["role"], x["bin"]) for x in gold["parties"]}
    pp = {(x["role"], x["bin"]) for x in pred["parties"]}
    out["parties.role_bin"] = "correct" if gp == pp else "wrong"
    gn = {(x["role"], norm_name(x["name"])) for x in gold["parties"]}
    pn = {(x["role"], norm_name(x["name"])) for x in pred["parties"]}
    out["parties.name"] = "correct" if gn == pn else "wrong"
    return out


def oracle_backend(docs: list[GoldDoc], broken_every: int = 4):  # noqa: ANN201
    """Подставная «модель», отвечающая эталоном; каждый N-й документ с первой попытки ломает.

    Нужна для проверки конвейера целиком без моделей: не измеряет качество,
    прогоны с ней в таблицу не попадают.
    """
    from contract_risk.extraction.backends import MockBackend

    by_text = {d.text: d for d in docs}
    seen: dict[str, int] = {}

    def respond(system: str, messages) -> str:  # noqa: ANN001
        text = messages[0]["content"].removeprefix("Договор:\n\n")
        doc = by_text[text]
        seen[doc.doc_id] = seen.get(doc.doc_id, 0) + 1
        idx = list(by_text.values()).index(doc)
        if idx % broken_every == 0 and seen[doc.doc_id] == 1:
            return '{"contract_type": "lease"'
        return json.dumps(doc.labels, ensure_ascii=False)

    return MockBackend(respond, model="oracle")


def load_pricing(path: Path = PRICING_PATH) -> dict[str, dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["models"]


def price_of(model_spec: str, pricing: dict[str, dict]) -> tuple[float, float] | None:
    entry = pricing.get(model_spec)
    if entry is None:
        kind = model_spec.split(":", 1)[0]
        entry = pricing.get(f"{kind}:*")
    if entry is None or entry.get("input") is None or entry.get("output") is None:
        return None
    return float(entry["input"]), float(entry["output"])


def _slug(spec: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]+", "_", spec)


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _bootstrap_macro(per_doc_acc: np.ndarray, n: int = 1000, seed: int = 13) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(per_doc_acc), size=(n, len(per_doc_acc)))
    means = per_doc_acc[idx].mean(axis=1)
    lo, hi = np.quantile(means, [0.025, 0.975])
    return round(float(lo), 4), round(float(hi), 4)


def evaluate(
    extractor: Extractor,
    docs: list[GoldDoc],
    model_spec: str,
    split: str,
    workers: int = 1,
    pricing: dict[str, dict] | None = None,
) -> dict:
    results: list[ExtractionResult] = extract_many(extractor, [d.text for d in docs], workers)
    pricing = pricing if pricing is not None else load_pricing()
    price = price_of(model_spec, pricing)

    statuses = Counter(r.status for r in results)
    n = len(docs)
    per_doc = []
    field_outcomes: dict[str, Counter] = defaultdict(Counter)
    for d, r in zip(docs, results, strict=True):
        pred = r.extraction.model_dump(mode="json") if r.extraction else None
        cmp = compare_fields(d.labels, pred)
        for f, o in cmp.items():
            field_outcomes[f][o] += 1
        per_doc.append(
            {
                "doc_id": d.doc_id,
                "status": r.status,
                "cached": r.cached,
                "attempts": [
                    {
                        "ok": a.ok,
                        "error": a.error,
                        "in": a.input_tokens,
                        "out": a.output_tokens,
                        "s": round(a.latency_s, 3),
                    }
                    for a in r.attempts
                ],
                "prediction": pred,
                "outcome": cmp,
            }
        )

    field_acc = {f: field_outcomes[f]["correct"] / n for f in ALL_FIELDS}
    doc_acc = np.array([np.mean([o == "correct" for o in p["outcome"].values()]) for p in per_doc])
    gold_null = {
        f: sum(1 for d in docs if f in d.labels and d.labels[f] is None) for f in EXTRACTION_FIELDS
    }
    gold_set = {f: n - gold_null[f] for f in EXTRACTION_FIELDS}
    halluc = sum(field_outcomes[f]["hallucinated"] for f in EXTRACTION_FIELDS)
    missed = sum(field_outcomes[f]["missed"] for f in EXTRACTION_FIELDS)
    total_null = sum(gold_null.values())
    total_set = sum(gold_set.values())

    lat = [r.latency_s for r in results if r.attempts]
    tin = [r.input_tokens for r in results]
    tout = [r.output_tokens for r in results]
    cost100 = None
    if price is not None and n:
        cost100 = round((sum(tin) * price[0] + sum(tout) * price[1]) / 1e6 / n * 100, 4)

    metrics = {
        "n_docs": n,
        "valid_first_try": round(statuses["ok_first_try"] / n, 4),
        "valid_after_retry": round((statuses["ok_first_try"] + statuses["ok_after_retry"]) / n, 4),
        "failed": statuses["failed"],
        "backend_errors": statuses["backend_error"],
        "macro_field_accuracy": round(float(np.mean(list(field_acc.values()))), 4),
        "macro_field_accuracy_ci95": _bootstrap_macro(doc_acc),
        "exact_match_docs": round(
            sum(1 for p in per_doc if all(o == "correct" for o in p["outcome"].values())) / n, 4
        ),
        "hallucination_rate": round(halluc / total_null, 4) if total_null else None,
        "miss_rate": round(missed / total_set, 4) if total_set else None,
        "field_accuracy": {f: round(v, 4) for f, v in field_acc.items()},
        "field_outcomes": {f: dict(c) for f, c in field_outcomes.items()},
        "latency_p50_s": round(statistics.median(lat), 3) if lat else None,
        "latency_p95_s": round(float(np.quantile(lat, 0.95)), 3) if lat else None,
        "tokens_in_per_doc": round(sum(tin) / n, 1),
        "tokens_out_per_doc": round(sum(tout) / n, 1),
        "retry_rate": round(sum(1 for r in results if len(r.attempts) > 1) / n, 4),
        "cost_usd_per_100_docs": cost100,
    }
    return {
        "run_id": f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}__{split}__{_slug(model_spec)}",
        "model": model_spec,
        "split": split,
        "prompt_version": PROMPT_VERSION,
        "git_commit": _git_commit(),
        "workers": workers,
        "cached_docs": sum(1 for r in results if r.cached),
        "metrics": metrics,
        "docs": per_doc,
    }


def write_run(run: dict, docs: list[GoldDoc], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    jp = out_dir / f"{run['run_id']}.json"
    jp.write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
    ep = out_dir / f"{run['run_id']}.errors.md"
    ep.write_text(errors_markdown(run, docs), encoding="utf-8")
    return jp, ep


def errors_markdown(run: dict, docs: list[GoldDoc]) -> str:
    gold = {d.doc_id: d.labels for d in docs}
    by_field: dict[str, list[str]] = defaultdict(list)
    for p in run["docs"]:
        for f, o in p["outcome"].items():
            if o == "correct":
                continue
            if f.startswith("parties"):
                g = gold[p["doc_id"]]["parties"]
                pr = p["prediction"]["parties"] if p["prediction"] else None
                by_field[f].append(f"- `{p['doc_id']}` {o}: эталон {g} → модель {pr}")
            else:
                pr = p["prediction"][f] if p["prediction"] else "—"
                by_field[f].append(
                    f"- `{p['doc_id']}` {o}: эталон `{gold[p['doc_id']][f]}` → модель `{pr}`"
                )
    lines = [f"# Ошибки: {run['model']} на {run['split']} ({run['run_id']})", ""]
    failed = [p for p in run["docs"] if p["status"] in ("failed", "backend_error")]
    if failed:
        lines += ["## Документы без валидного ответа", ""]
        for p in failed:
            err = p["attempts"][-1]["error"] if p["attempts"] else "—"
            lines.append(f"- `{p['doc_id']}` {p['status']}: {str(err)[:200]}")
        lines.append("")
    order = sorted(by_field, key=lambda f: -len(by_field[f]))
    for f in order:
        lines += [f"## {f} ({len(by_field[f])})", "", *by_field[f], ""]
    return "\n".join(lines)


def load_runs(out_dir: Path) -> list[dict]:
    runs = []
    for p in sorted(out_dir.glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        r.pop("docs", None)
        runs.append(r)
    return runs


def field_table(runs: list[dict], split: str = "test") -> str:
    """Точность по полям: строки — поля, столбцы — модели (последний прогон на срезе)."""
    latest: dict[str, dict] = {}
    for r in sorted(runs, key=lambda r: r["run_id"]):
        if r["split"] == split and not r["model"].startswith("mock"):
            latest[r["model"]] = r
    names = sorted(latest)
    if not names:
        return ""
    rows = ["| поле | " + " | ".join(f"`{n}`" for n in names) + " |", "|---|" + "---|" * len(names)]
    for f in ALL_FIELDS:
        cells = " | ".join(f"{latest[n]['metrics']['field_accuracy'][f] * 100:.0f}%" for n in names)
        rows.append(f"| {f} | {cells} |")
    return "\n".join(rows)


def summary_table(runs: list[dict], include_mock: bool = False) -> str:
    rows = [
        "| модель | срез | n | валидно с 1-й | после повтора | macro-точность [95% ДИ] "
        "| halluc. | пропуск | p50, с | p95, с | токены вх/вых | $/100 док. |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    def pct(x: float | None) -> str:
        return "—" if x is None else f"{x * 100:.1f}%"

    order = {name: i for i, name in enumerate(SPLITS)}
    for r in sorted(runs, key=lambda r: (r["model"], order.get(r["split"], 99), r["run_id"])):
        if r["model"].startswith("mock") and not include_mock:
            continue
        m = r["metrics"]
        lo, hi = m["macro_field_accuracy_ci95"]
        cost = "—" if m["cost_usd_per_100_docs"] is None else f"{m['cost_usd_per_100_docs']:.3f}"
        rows.append(
            f"| `{r['model']}` | {r['split']} | {m['n_docs']} | {pct(m['valid_first_try'])} | "
            f"{pct(m['valid_after_retry'])} | "
            f"{pct(m['macro_field_accuracy'])} [{lo * 100:.1f}, {hi * 100:.1f}] | "
            f"{pct(m['hallucination_rate'])} | {pct(m['miss_rate'])} | "
            f"{m['latency_p50_s']} | {m['latency_p95_s']} | "
            f"{m['tokens_in_per_doc']:.0f}/{m['tokens_out_per_doc']:.0f} | {cost} |"
        )
    return "\n".join(rows)
