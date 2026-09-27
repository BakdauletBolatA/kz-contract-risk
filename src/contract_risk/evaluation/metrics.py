"""Метрики качества скрининга.

Главный вопрос пользователя — «можно ли доверять тому, что система пометила,
и тому, что она промолчала». Поэтому метрики считаются на уровне пункта
договора, а не находки или токена:

- **detection** — пункт помечен / не помечен, категория не важна. Это то,
  что видит пользователь: «на этот пункт смотреть».
- **strict** — совпадают пункт и категория. Строже: система могла найти
  пункт по неверной причине, и тогда объяснение в отчёте будет ложным.
- **high_recall** — доля пунктов с высоким эталонным риском, которые система
  пометила хоть как-то. Пропуск высокого риска — самая дорогая ошибка.
- **level** — на совпавших (пункт, категория): точность уровня и отдельно
  доля недооценок (система сказала «низкий», эталон — «высокий»).
- **clean_docs** — ложные тревоги на договорах без единой ловушки. Именно
  здесь теряется доверие: инструмент, который «находит риски» в
  нейтральном договоре, перестают открывать.
- **document** — находки без привязки к пункту («нет форс-мажора»).

Precision при нуле предсказаний не определён и возвращается как None, а не
0 или 1: иначе null-детектор выглядит либо идеально точным, либо бесполезным
по неверной причине.

Формулы версионированы. Изменение любой из них делает прошлые строки
EVALUATION.md несравнимыми — версия поднимается, прошлые прогоны
пересчитываются.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import numpy as np

from contract_risk.evaluation.dataset import EvalDoc
from contract_risk.schemas import Finding, RiskCategory, RiskLevel

METRICS_VERSION = "1.0"


@dataclass
class DocResult:
    doc: EvalDoc
    predictions: list[Finding]
    parsed_clause_ids: set[str] = field(default_factory=set)


def prf(tp: int, fp: int, fn: int) -> dict[str, float | int | None]:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    if precision and recall:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0 if (tp + fp + fn) else None
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def _clause_sets(r: DocResult) -> tuple[set, set, set, set]:
    doc_id = r.doc.doc_id
    gold_det = {(doc_id, g.clause) for g in r.doc.clause_findings}
    pred_det = {(doc_id, p.clause_id) for p in r.predictions if p.clause_id is not None}
    gold_strict = {(doc_id, g.clause, g.category) for g in r.doc.clause_findings}
    pred_strict = {
        (doc_id, p.clause_id, p.category) for p in r.predictions if p.clause_id is not None
    }
    return gold_det, pred_det, gold_strict, pred_strict


def _doc_sets(r: DocResult) -> tuple[set, set]:
    doc_id = r.doc.doc_id
    gold = {(doc_id, g.category) for g in r.doc.document_findings}
    pred = {(doc_id, p.category) for p in r.predictions if p.clause_id is None}
    return gold, pred


def detection_counts(r: DocResult) -> tuple[int, int, int]:
    gold, pred, _, _ = _clause_sets(r)
    return len(gold & pred), len(pred - gold), len(gold - pred)


def strict_counts(r: DocResult) -> tuple[int, int, int]:
    _, _, gold, pred = _clause_sets(r)
    return len(gold & pred), len(pred - gold), len(gold - pred)


def compute_metrics(results: Sequence[DocResult]) -> dict:
    gold_det: set = set()
    pred_det: set = set()
    gold_strict: set = set()
    pred_strict: set = set()
    gold_doc: set = set()
    pred_doc: set = set()
    gold_levels: dict[tuple, RiskLevel] = {}
    pred_levels: dict[tuple, RiskLevel] = {}
    gold_high: set = set()
    covered = total_gold_clauses = 0
    clean_fp: list[int] = []

    for r in results:
        gd, pd_, gs, ps = _clause_sets(r)
        gold_det |= gd
        pred_det |= pd_
        gold_strict |= gs
        pred_strict |= ps
        gdoc, pdoc = _doc_sets(r)
        gold_doc |= gdoc
        pred_doc |= pdoc

        for g in r.doc.clause_findings:
            key = (r.doc.doc_id, g.clause, g.category)
            gold_levels[key] = _max_level(gold_levels.get(key), g.level)
            if g.level == RiskLevel.HIGH:
                gold_high.add((r.doc.doc_id, g.clause))
        for p in r.predictions:
            if p.clause_id is not None:
                key = (r.doc.doc_id, p.clause_id, p.category)
                pred_levels[key] = _max_level(pred_levels.get(key), p.level)

        gold_clause_ids = {g.clause for g in r.doc.clause_findings}
        total_gold_clauses += len(gold_clause_ids)
        covered += len(gold_clause_ids & r.parsed_clause_ids)

        if r.doc.is_clean:
            clean_fp.append(len(r.predictions))

    per_category = {}
    for cat in RiskCategory:
        g = {k for k in gold_strict if k[2] == cat}
        p = {k for k in pred_strict if k[2] == cat}
        if not g and not p:
            continue
        stats = prf(len(g & p), len(p - g), len(g - p))
        stats["support"] = len(g)
        per_category[cat.value] = stats

    matched = gold_strict & pred_strict
    exact = under = over = 0
    for key in matched:
        g_rank, p_rank = gold_levels[key].rank, pred_levels[key].rank
        exact += g_rank == p_rank
        under += p_rank < g_rank
        over += p_rank > g_rank

    return {
        "n_docs": len(results),
        "n_clean_docs": len(clean_fp),
        "n_gold_clause_findings": len(gold_strict),
        "n_pred_clause_findings": len(pred_strict),
        "detection": prf(
            len(gold_det & pred_det), len(pred_det - gold_det), len(gold_det - pred_det)
        ),
        "strict": prf(
            len(gold_strict & pred_strict),
            len(pred_strict - gold_strict),
            len(gold_strict - pred_strict),
        ),
        "high_recall": (len(gold_high & pred_det) / len(gold_high)) if gold_high else None,
        "high_support": len(gold_high),
        "level": {
            "n": len(matched),
            "accuracy": exact / len(matched) if matched else None,
            "underestimated": under / len(matched) if matched else None,
            "overestimated": over / len(matched) if matched else None,
        },
        "document": prf(
            len(gold_doc & pred_doc), len(pred_doc - gold_doc), len(gold_doc - pred_doc)
        ),
        "clean_docs": {
            "n": len(clean_fp),
            "false_alarms_per_doc": float(np.mean(clean_fp)) if clean_fp else None,
            "docs_with_false_alarm": (
                sum(1 for x in clean_fp if x) / len(clean_fp) if clean_fp else None
            ),
        },
        "segmentation_coverage": covered / total_gold_clauses if total_gold_clauses else None,
        "per_category": per_category,
    }


def bootstrap_ci(
    results: Sequence[DocResult],
    n_resamples: int = 1000,
    seed: int = 13,
    alpha: float = 0.05,
) -> dict[str, tuple[float, float] | None]:
    """Интервалы для detection P/R/F1 и strict F1 бутстрепом по документам.

    Ресемплируются договоры, а не пункты: пункты одного договора зависимы
    (один шаблон, одна сторона), и ресемплинг пунктов дал бы ложно узкие
    интервалы.
    """
    if not results:
        return {}
    det = np.array([detection_counts(r) for r in results], dtype=float)
    strict = np.array([strict_counts(r) for r in results], dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(results), size=(n_resamples, len(results)))

    def _ratios(counts: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        sums = counts[idx].sum(axis=1)
        tp, fp, fn = sums[:, 0], sums[:, 1], sums[:, 2]
        with np.errstate(divide="ignore", invalid="ignore"):
            p = np.where(tp + fp > 0, tp / (tp + fp), np.nan)
            r = np.where(tp + fn > 0, tp / (tp + fn), np.nan)
            f1 = np.where((p + r) > 0, 2 * p * r / (p + r), 0.0)
        return p, r, f1

    def _interval(values: np.ndarray) -> tuple[float, float] | None:
        values = values[~np.isnan(values)]
        if values.size == 0:
            return None
        lo, hi = np.quantile(values, [alpha / 2, 1 - alpha / 2])
        return (round(float(lo), 4), round(float(hi), 4))

    p, r, f1 = _ratios(det)
    _, _, strict_f1 = _ratios(strict)
    return {
        "detection_precision": _interval(p),
        "detection_recall": _interval(r),
        "detection_f1": _interval(f1),
        "strict_f1": _interval(strict_f1),
    }


def _max_level(current: RiskLevel | None, new: RiskLevel) -> RiskLevel:
    if current is None or new.rank > current.rank:
        return new
    return current


def slice_results(results: Iterable[DocResult], key: str) -> dict[str, list[DocResult]]:
    out: dict[str, list[DocResult]] = {}
    for r in results:
        value = getattr(r.doc, key)
        out.setdefault(str(getattr(value, "value", value)), []).append(r)
    return out
