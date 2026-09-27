"""Правила: встроенные примеры каждого правила, анализ сторон, признаки, документные проверки."""

import pytest

from contract_risk.ingestion import parse_text
from contract_risk.rules.catalog import RULES, RuleContext
from contract_risk.rules.engine import RuleEngine, RulesDetector
from contract_risk.rules.features import durations_days, months_amount, penalty_terms
from contract_risk.rules.parties import PartyView
from contract_risk.schemas import Clause, ContractType, Language, PartyRole

EXAMPLES = [(rule, ex) for rule in RULES for ex in rule.examples]


def test_every_rule_has_positive_and_negative_examples():
    for rule in RULES:
        levels = [ex.level for ex in rule.examples]
        assert any(levels), f"{rule.id}: нет примера, где правило срабатывает"
        assert None in levels, f"{rule.id}: нет примера, где правило молчит"


@pytest.mark.parametrize(
    ("rule", "ex"), EXAMPLES, ids=[f"{r.id}-{i}" for i, (r, _) in enumerate(EXAMPLES)]
)
def test_rule_example(rule, ex):
    clause = Clause(id="1.1", text=ex.text, lang=Language(ex.lang))
    user = PartyRole(ex.role)
    ctx = RuleContext(clause, ContractType(ex.contract_type), user)
    hits = [h for h in rule.fn(ctx) if user in h.against]
    if ex.level is None:
        assert hits == [], f"сработало на нейтральном примере: {[h.level for h in hits]}"
    else:
        assert hits, "не сработало"
        assert max(h.level.rank for h in hits) == {"low": 1, "medium": 2, "high": 3}[ex.level]
        for h in hits:
            for s, e in h.spans:
                assert 0 <= s < e <= len(ex.text)


def test_evidence_quotes_are_verbatim_substrings():
    doc = parse_text(
        "ДОГОВОР АРЕНДЫ\n1. Ответственность\n"
        "1.1. Арендатор уплачивает Арендодателю пеню в размере 1% от суммы долга за каждый день просрочки.\n",
        "d",
    )
    findings = RuleEngine().analyze(doc, PartyRole.TENANT)
    assert findings
    for f in findings:
        clause = doc.clause(f.clause_id)
        for ev in f.evidence:
            assert clause.text[ev.start : ev.end] == ev.quote


@pytest.mark.parametrize(
    ("text", "ctype", "lang", "payers"),
    [
        ("Арендатор уплачивает Арендодателю пеню.", "lease", "ru", {"tenant"}),
        ("Арендодатель вправе взыскать с Арендатора неустойку.", "lease", "ru", {"tenant"}),
        ("Каждый день задержки влечет для Поставщика неустойку.", "supply", "ru", {"supplier"}),
        ("Нарушение влечет штраф, уплачиваемый Арендатором.", "lease", "ru", {"tenant"}),
        (
            "Уплата неустойки не освобождает Арендатора от возмещения убытков.",
            "lease",
            "ru",
            {"tenant"},
        ),
        ("Жалға беруші Жалға алушыдан айыпты өндіріп алуға құқылы.", "lease", "kk", {"tenant"}),
        (
            "Оплата производится Заказчиком после оплаты от Генерального заказчика.",
            "works",
            "ru",
            set(),
        ),
    ],
)
def test_payers(text, ctype, lang, payers):
    view = PartyView.of(text, ContractType(ctype), Language(lang))
    assert {r.value for r in view.payers()} == payers


def test_negated_right_is_not_a_right():
    view = PartyView.of(
        "Арендатор не вправе досрочно расторгнуть Договор.", ContractType.LEASE, Language.RU
    )
    assert view.right_holders(r"расторг") == set()


def test_penalty_terms_separate_rate_cap_and_fine():
    t = penalty_terms(
        "Пеня 0,05% за каждый день просрочки, при этом общий размер пени не может превышать 10% от суммы долга."
    )
    assert [s.value for s in t.daily_rates] == [0.05]
    assert [s.value for s in t.caps] == [10.0]
    kk = penalty_terms(
        "әрбір кешіктірілген күн үшін 0,1% мөлшерінде өсімпұл төлейді, бірақ 10%-ынан аспайды"
    )
    assert [s.value for s in kk.caps] == [10.0]


def test_durations_and_months():
    assert [
        s.value for s in durations_days("в течение 24 часов; за три месяца; 30 күнтізбелік күн")
    ] == [1.0, 90.0, 30.0]
    assert months_amount("в размере двухмесячной арендной платы") == 2.0
    assert months_amount("бір айлық жалдау ақысы") == 1.0


LEASE_WITHOUT_FM = """ДОГОВОР АРЕНДЫ
1. ПРЕДМЕТ
1.1. Арендодатель передает Арендатору помещение.
1.2. Помещение используется под офис.
2. ПЛАТЕЖИ
2.1. Арендная плата вносится ежемесячно.
2.2. За просрочку оплаты Арендатор уплачивает пеню 0,1% за каждый день просрочки, но не более 10%.
3. ПРОЧЕЕ
3.1. Споры разрешаются в суде.
3.2. Договор составлен в двух экземплярах.
"""


def test_document_checks_missing_fm_and_one_sided_liability():
    doc = parse_text(LEASE_WITHOUT_FM, "d")
    findings = RulesDetector().detect(doc, PartyRole.TENANT)
    doc_level = {f.rule_id for f in findings if f.clause_id is None}
    assert doc_level == {"document.force_majeure_missing", "document.liability_one_sided"}
    # у арендодателя нет пени — асимметрия против арендатора, не против арендодателя
    landlord = RulesDetector().detect(doc, PartyRole.LANDLORD)
    assert {f.rule_id for f in landlord if f.clause_id is None} == {
        "document.force_majeure_missing"
    }


def test_mutual_liability_clause_removes_asymmetry():
    text = LEASE_WITHOUT_FM.replace(
        "3.2. Договор", "3.2. Стороны несут ответственность по законодательству РК.\n3.3. Договор"
    )
    findings = RulesDetector().detect(parse_text(text, "d"), PartyRole.TENANT)
    assert "document.liability_one_sided" not in {f.rule_id for f in findings}
