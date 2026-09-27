"""Прогон детектора по срезу датасета и запись результата.

Документ из датасета проходит **тот же** путь, что пользовательский файл:
текст → сегментатор → детектор. Поэтому ошибка сегментации (пункт 5.2 склеился
с 5.3) видна в метриках как пропуск, а не прячется за готовой разметкой
пунктов. Отдельно считается `segmentation_coverage` — чтобы по пропуску было
понятно, чья это ошибка: сегментатора или детектора.

Каждый прогон пишет JSON в `evals/results/`: метрики, интервалы, срезы,
все предсказания, хэш датасета и коммит. Строки EVALUATION.md
восстанавливаются из этих файлов, а не переписываются руками.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from contract_risk import __version__
from contract_risk.detectors import Detector
from contract_risk.evaluation.dataset import EvalDoc, dataset_hash
from contract_risk.evaluation.metrics import (
    METRICS_VERSION,
    DocResult,
    bootstrap_ci,
    compute_metrics,
    slice_results,
)
from contract_risk.schemas import ContractDocument

Parser = Callable[[str, str], ContractDocument]


def run_detector(
    detector: Detector, docs: Sequence[EvalDoc], parser: Parser
) -> tuple[list[DocResult], dict[str, ContractDocument]]:
    results: list[DocResult] = []
    parsed_docs: dict[str, ContractDocument] = {}
    for doc in docs:
        parsed = parser(doc.text, doc.doc_id)
        parsed.contract_type = doc.contract_type
        predictions = detector.detect(parsed, doc.party_role)
        results.append(DocResult(doc, predictions, {c.id for c in parsed.clauses}))
        parsed_docs[doc.doc_id] = parsed
    return results, parsed_docs


def evaluate(
    detector: Detector, docs: Sequence[EvalDoc], parser: Parser, split: str
) -> tuple[dict[str, Any], list[DocResult], dict[str, ContractDocument]]:
    started = time.perf_counter()
    results, parsed = run_detector(detector, docs, parser)
    elapsed = time.perf_counter() - started

    created = datetime.now(UTC)
    run = {
        "run_id": f"{created:%Y%m%d-%H%M%S}_{split}_{detector.name}",
        "created_at": created.isoformat(timespec="seconds"),
        "detector": {"name": detector.name, "config": detector.config()},
        "split": split,
        "dataset_hash": dataset_hash(list(docs)),
        "metrics_version": METRICS_VERSION,
        "pipeline_version": __version__,
        **_git_state(),
        "metrics": compute_metrics(results),
        "ci95": bootstrap_ci(results),
        "slices": {
            key: {name: _slice_summary(rs) for name, rs in slice_results(results, key).items()}
            for key in ("language", "contract_type", "origin")
        },
        "timing": {
            "seconds": round(elapsed, 3),
            "ms_per_doc": round(1000 * elapsed / max(len(docs), 1), 1),
        },
        "predictions": predictions_frame(results).to_dict(orient="records"),
    }
    return run, results, parsed


def predictions_frame(results: Sequence[DocResult]) -> pd.DataFrame:
    rows = [
        {
            "doc_id": r.doc.doc_id,
            "clause_id": p.clause_id,
            "category": p.category.value,
            "level": p.level.value,
            "source": p.source,
            "rule_id": p.rule_id,
            "confidence": round(p.confidence, 4),
        }
        for r in results
        for p in r.predictions
    ]
    columns = ["doc_id", "clause_id", "category", "level", "source", "rule_id", "confidence"]
    return pd.DataFrame(rows, columns=columns)


def write_run(
    run: dict[str, Any],
    results: Sequence[DocResult],
    parsed: dict[str, ContractDocument],
    out_dir: Path,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{run['run_id']}.json"
    json_path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    errors_path = out_dir / f"{run['run_id']}.errors.md"
    errors_path.write_text(render_errors(run, results, parsed), encoding="utf-8")
    return json_path, errors_path


def render_errors(
    run: dict[str, Any], results: Sequence[DocResult], parsed: dict[str, ContractDocument]
) -> str:
    """Разбор ошибок: пропуски, ложные тревоги, промахи категории — с текстом пункта."""
    lines = [
        f"# Разбор ошибок: {run['run_id']}",
        "",
        f"Детектор `{run['detector']['name']}`, срез `{run['split']}`, "
        f"датасет `{run['dataset_hash']}`.",
        "",
    ]
    for r in results:
        doc = parsed[r.doc.doc_id]
        gold = {(g.clause, g.category): g for g in r.doc.findings}
        pred = {(p.clause_id, p.category): p for p in r.predictions}
        gold_clauses = {g.clause for g in r.doc.clause_findings}
        pred_clauses = {p.clause_id for p in r.predictions if p.clause_id is not None}

        block: list[str] = []
        for key in sorted(gold.keys() - pred.keys(), key=str):
            g = gold[key]
            if g.clause is not None and g.clause in pred_clauses:
                continue  # пункт найден под другой категорией — ниже
            block.append(
                f"- **пропуск** `{g.clause or 'документ'}` {g.category.value}/{g.level.value}"
                f" (`{g.trap_id}`): {_excerpt(doc, g.clause)}"
            )
        for key in sorted(pred.keys() - gold.keys(), key=str):
            p = pred[key]
            if p.clause_id is not None and p.clause_id in gold_clauses:
                wanted = ", ".join(
                    g.category.value for g in r.doc.findings if g.clause == p.clause_id
                )
                block.append(
                    f"- **не та категория** `{p.clause_id}`: {p.category.value} "
                    f"(`{p.rule_id or p.source}`), в эталоне {wanted}"
                )
                continue
            block.append(
                f"- **ложная тревога** `{p.clause_id or 'документ'}` "
                f"{p.category.value}/{p.level.value} (`{p.rule_id or p.source}`): "
                f"{_excerpt(doc, p.clause_id)}"
            )
        if block:
            lines.append(f"## {r.doc.doc_id} — {r.doc.party_role.value}, {r.doc.language.value}")
            lines.extend(block)
            lines.append("")
    if len(lines) == 4:
        lines.append("Ошибок нет.")
    return "\n".join(lines) + "\n"


def _excerpt(doc: ContractDocument, clause_id: str | None, limit: int = 220) -> str:
    if clause_id is None:
        return "—"
    clause = doc.clause(clause_id)
    if clause is None:
        return "_пункт не найден сегментатором_"
    text = " ".join(clause.text.split())
    return f"«{text[:limit]}{'…' if len(text) > limit else ''}»"


def _slice_summary(results: Sequence[DocResult]) -> dict[str, Any]:
    m = compute_metrics(results)
    return {
        "n_docs": m["n_docs"],
        "detection": m["detection"],
        "strict_f1": m["strict"]["f1"],
        "high_recall": m["high_recall"],
        "clean_docs": m["clean_docs"],
    }


def _git_state() -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return {"git_commit": None, "git_dirty": None}
    return {"git_commit": commit, "git_dirty": dirty}


def load_runs(results_dir: Path) -> list[dict[str, Any]]:
    runs = []
    for path in sorted(results_dir.glob("*.json")):
        runs.append(json.loads(path.read_text(encoding="utf-8")))
    return runs


def summary_table(runs: Sequence[dict[str, Any]]) -> str:
    """Markdown-таблица по прогонам — для EVALUATION.md."""

    def fmt(x: float | None) -> str:
        return "—" if x is None else f"{x:.2f}"

    def ci(run: dict[str, Any], key: str) -> str:
        interval = run.get("ci95", {}).get(key)
        return "" if not interval else f" [{interval[0]:.2f}–{interval[1]:.2f}]"

    header = (
        "| прогон | детектор | срез | датасет | P | R | F1 | strict F1 | high R | "
        "ложн. тревоги / чистый дог. | док. F1 |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|"
    )
    rows = []
    for run in runs:
        m = run["metrics"]
        rows.append(
            f"| {run['run_id']} | {run['detector']['name']} | {run['split']} | "
            f"`{run['dataset_hash'][:8]}` | {fmt(m['detection']['precision'])} | "
            f"{fmt(m['detection']['recall'])} | {fmt(m['detection']['f1'])}"
            f"{ci(run, 'detection_f1')} | {fmt(m['strict']['f1'])} | {fmt(m['high_recall'])} | "
            f"{fmt(m['clean_docs']['false_alarms_per_doc'])} | {fmt(m['document']['f1'])} |"
        )
    return "\n".join([header, *rows])
