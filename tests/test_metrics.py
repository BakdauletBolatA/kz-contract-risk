"""Метрики на вручную посчитанных случаях.

Каждое ожидаемое число здесь выведено на бумаге, а не взято из вывода
функции: тест, который сверяет функцию с её же результатом, ничего не ловит.
"""

import pytest

from contract_risk.evaluation.dataset import EvalDoc, GoldFinding
from contract_risk.evaluation.metrics import DocResult, bootstrap_ci, compute_metrics, prf
from contract_risk.schemas import Finding, RiskCategory, RiskLevel

PEN = RiskCategory.PENALTY
TERM = RiskCategory.TERMINATION
FM = RiskCategory.FORCE_MAJEURE


def gold(clause, cat, level=RiskLevel.HIGH):
    return GoldFinding(clause=clause, category=cat, level=level)


def pred(clause, cat, level=RiskLevel.HIGH):
    return Finding(
        clause_id=clause, category=cat, level=level, source="rule", title="t", explanation="e"
    )


def doc(doc_id, findings):
    return EvalDoc(
        doc_id=doc_id,
        split="dev",
        contract_type="lease",
        language="ru",
        party_role="tenant",
        origin="synthetic",
        findings=findings,
    )


def test_prf_undefined_precision_without_predictions():
    stats = prf(tp=0, fp=0, fn=3)
    assert stats["precision"] is None
    assert stats["recall"] == 0.0
    assert stats["f1"] == 0.0


def test_prf_everything_empty_is_undefined():
    assert prf(0, 0, 0) == {
        "precision": None,
        "recall": None,
        "f1": None,
        "tp": 0,
        "fp": 0,
        "fn": 0,
    }


def test_detection_ignores_category_strict_does_not():
    # Эталон: 5.1 penalty, 6.2 termination. Система: 5.1 как termination
    # (верный пункт, неверная причина) и лишний 7.1.
    r = DocResult(
        doc("d1", [gold("5.1", PEN), gold("6.2", TERM)]),
        [pred("5.1", TERM), pred("7.1", PEN)],
        {"5.1", "6.2", "7.1"},
    )
    m = compute_metrics([r])
    # detection: tp={5.1}, fp={7.1}, fn={6.2}
    assert m["detection"]["tp"] == 1
    assert m["detection"]["fp"] == 1
    assert m["detection"]["fn"] == 1
    assert m["detection"]["precision"] == pytest.approx(0.5)
    # strict: ни одной пары (пункт, категория) не совпало
    assert m["strict"]["tp"] == 0
    assert m["strict"]["fp"] == 2
    assert m["strict"]["fn"] == 2


def test_two_findings_on_same_clause_count_once_for_detection():
    r = DocResult(doc("d1", [gold("3.1", PEN)]), [pred("3.1", PEN), pred("3.1", TERM)], {"3.1"})
    m = compute_metrics([r])
    assert m["detection"] == prf(1, 0, 0)
    assert m["strict"]["fp"] == 1


def test_high_recall_counts_detection_of_high_clauses_only():
    r = DocResult(
        doc(
            "d1",
            [
                gold("1.1", PEN, RiskLevel.HIGH),
                gold("1.2", PEN, RiskLevel.HIGH),
                gold("1.3", PEN, RiskLevel.LOW),
            ],
        ),
        [pred("1.1", TERM, RiskLevel.LOW), pred("1.3", PEN, RiskLevel.LOW)],
        set(),
    )
    m = compute_metrics([r])
    # высоких два, помечен (в любой категории) один
    assert m["high_recall"] == pytest.approx(0.5)
    assert m["high_support"] == 2


def test_level_accuracy_and_underestimation():
    r = DocResult(
        doc("d1", [gold("1.1", PEN, RiskLevel.HIGH), gold("1.2", PEN, RiskLevel.MEDIUM)]),
        [pred("1.1", PEN, RiskLevel.MEDIUM), pred("1.2", PEN, RiskLevel.MEDIUM)],
        set(),
    )
    level = compute_metrics([r])["level"]
    assert level["n"] == 2
    assert level["accuracy"] == pytest.approx(0.5)
    assert level["underestimated"] == pytest.approx(0.5)
    assert level["overestimated"] == 0.0


def test_clean_doc_false_alarms():
    clean_a = DocResult(doc("a", []), [pred("2.1", PEN), pred("3.1", TERM)], set())
    clean_b = DocResult(doc("b", []), [], set())
    dirty = DocResult(doc("c", [gold("1.1", PEN)]), [pred("9.9", PEN)], set())
    clean = compute_metrics([clean_a, clean_b, dirty])["clean_docs"]
    assert clean["n"] == 2
    assert clean["false_alarms_per_doc"] == pytest.approx(1.0)
    assert clean["docs_with_false_alarm"] == pytest.approx(0.5)


def test_document_level_findings_are_separate_from_clauses():
    r = DocResult(
        doc("d1", [gold(None, FM, RiskLevel.MEDIUM)]),
        [pred(None, FM, RiskLevel.MEDIUM), pred(None, PEN)],
        set(),
    )
    m = compute_metrics([r])
    assert m["document"]["tp"] == 1
    assert m["document"]["fp"] == 1
    assert m["detection"]["tp"] + m["detection"]["fp"] + m["detection"]["fn"] == 0
    # документ с документной находкой не «чистый»
    assert m["clean_docs"]["n"] == 0


def test_segmentation_coverage():
    r = DocResult(doc("d1", [gold("1.1", PEN), gold("2.4", TERM)]), [], {"1.1", "2.1"})
    assert compute_metrics([r])["segmentation_coverage"] == pytest.approx(0.5)


def test_per_category_support_and_precision():
    r = DocResult(
        doc("d1", [gold("1.1", PEN), gold("2.1", TERM)]),
        [pred("1.1", PEN), pred("3.1", PEN)],
        set(),
    )
    per_cat = compute_metrics([r])["per_category"]
    assert per_cat["penalty"]["precision"] == pytest.approx(0.5)
    assert per_cat["penalty"]["support"] == 1
    assert per_cat["termination"]["recall"] == 0.0


def test_bootstrap_is_deterministic_and_brackets_point_estimate():
    results = [
        DocResult(doc(f"d{i}", [gold("1.1", PEN)]), [pred("1.1", PEN)] if i % 3 else [], set())
        for i in range(30)
    ]
    ci_a = bootstrap_ci(results, n_resamples=300)
    ci_b = bootstrap_ci(results, n_resamples=300)
    assert ci_a == ci_b
    point = compute_metrics(results)["detection"]["recall"]
    lo, hi = ci_a["detection_recall"]
    assert lo <= point <= hi
