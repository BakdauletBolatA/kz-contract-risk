"""Регрессия качества: зафиксированные цифры правил не должны молча ухудшаться.

Пороги — чуть ниже текущих значений из EVALUATION.md. Если правка правил
роняет метрику ниже порога, это не повод снижать порог: сначала разбор
ошибок (evals/results/*.errors.md), потом решение, записанное в журнал.
"""

from pathlib import Path

import pytest

from contract_risk.evaluation.dataset import load_split
from contract_risk.evaluation.harness import evaluate
from contract_risk.ingestion import parse_text
from contract_risk.rules.engine import RulesDetector

DATA = Path(__file__).resolve().parents[1] / "data/eval"


@pytest.mark.parametrize(
    ("split", "min_precision", "min_recall"),
    [("test", 0.98, 0.97), ("handwritten", 0.95, 0.95), ("stress", 0.95, 0.40)],
)
def test_rules_quality_does_not_regress(split, min_precision, min_recall):
    run, _, _ = evaluate(RulesDetector(), load_split(DATA, split), parse_text, split)
    m = run["metrics"]
    assert m["detection"]["precision"] >= min_precision
    assert m["detection"]["recall"] >= min_recall
    # доверие к отчёту: на договорах без ловушек — ни одной тревоги
    if m["clean_docs"]["n"]:
        assert m["clean_docs"]["false_alarms_per_doc"] == 0
