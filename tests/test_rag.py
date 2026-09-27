"""RAG-сравнение: нейтральные эталоны, граница рынка, разница числами."""

import pytest

from contract_risk.ingestion import parse_text
from contract_risk.rag.compare import MarketComparator, differences
from contract_risk.retrieval.embeddings import HashingEmbedder
from contract_risk.retrieval.index import ReferenceIndex
from contract_risk.rules.engine import RulesDetector
from contract_risk.schemas import ContractType, PartyRole, RiskCategory


@pytest.fixture(scope="module")
def comparator(corpus):
    return MarketComparator(ReferenceIndex.in_memory(corpus, HashingEmbedder()))


def test_penalty_difference_in_numbers():
    diffs = differences(
        RiskCategory.PENALTY,
        "Арендатор уплачивает пеню 1% за каждый день просрочки.",
        "Арендатор уплачивает пеню 0,1% за каждый день просрочки, но не более 10% от суммы долга.",
    )
    assert "Пеня: у вас 1% в день, в эталоне 0,1%." in diffs
    assert "Потолок неустойки: у вас нет, в эталоне 10%." in diffs


def test_notice_difference():
    diffs = differences(
        RiskCategory.TERMINATION,
        "Арендодатель вправе отказаться от Договора, уведомив Арендатора за 10 дней.",
        "Каждая из Сторон вправе отказаться от Договора, предупредив другую Сторону за 30 дней.",
    )
    assert any("10 дн., в эталоне 30 дн." in d for d in diffs)
    assert any("у обеих сторон" in d for d in diffs)


def test_references_are_neutral_first_then_counterparty_boundary(comparator):
    refs = comparator.compare(
        "Арендатор уплачивает пеню 1% за каждый день просрочки.",
        RiskCategory.PENALTY,
        ContractType.LEASE,
        PartyRole.TENANT,
    )
    assert [r.favours for r in refs] == ["neutral", "neutral", "landlord"]
    assert all(r.reference_id.startswith("lease.penalty") for r in refs)
    assert refs[0].differences


def test_attach_to_rule_findings_including_document_level(comparator):
    doc = parse_text(
        "ДОГОВОР АРЕНДЫ\n1. Условия\n"
        "1.1. Арендатор уплачивает пеню 1% за каждый день просрочки.\n"
        "1.2. Помещение передается по акту.\n1.3. Плата вносится ежемесячно.\n"
        "1.4. Помещение используется под офис.\n1.5. Договор составлен в двух экземплярах.\n",
        "d",
    )
    findings = RulesDetector().detect(doc, PartyRole.TENANT)
    comparator.attach(doc, findings, PartyRole.TENANT)
    by_rule = {f.rule_id: f for f in findings}
    assert by_rule["penalty.daily_rate"].comparison[0].differences
    fm = by_rule["document.force_majeure_missing"].comparison
    assert fm and fm[0].reference_id.startswith("lease.fm")
