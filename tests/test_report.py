"""Пайплайн «текст → отчёт» и рендер HTML/PDF."""

import pytest

from contract_risk.pipeline import Analyzer
from contract_risk.rag.compare import MarketComparator
from contract_risk.report.render import highlight, render_html, render_pdf
from contract_risk.retrieval.embeddings import HashingEmbedder
from contract_risk.retrieval.index import ReferenceIndex
from contract_risk.rules.engine import RulesDetector
from contract_risk.schemas import Evidence, PartyRole, RiskLevel

LEASE = """ДОГОВОР АРЕНДЫ № 1
1. Условия
1.1. Арендатор уплачивает Арендодателю пеню 1% за каждый день просрочки.
1.2. Споры рассматриваются в суде по месту нахождения Арендодателя.
1.3. Помещение используется под офис <script>alert(1)</script>.
1.4. Арендная плата вносится ежемесячно.
1.5. Стороны освобождаются от ответственности при обстоятельствах непреодолимой силы.
1.6. Стороны несут ответственность по законодательству Республики Казахстан.
"""


@pytest.fixture(scope="module")
def analyzer(corpus):
    return Analyzer(
        RulesDetector(), MarketComparator(ReferenceIndex.in_memory(corpus, HashingEmbedder()))
    )


def test_report_sorted_by_level_with_comparisons(analyzer):
    report = analyzer.analyze_text(LEASE, PartyRole.TENANT)
    levels = [f.level.rank for f in report.findings]
    assert levels == sorted(levels, reverse=True)
    assert report.findings[0].level == RiskLevel.HIGH
    assert report.findings[0].comparison
    assert set(report.clause_texts) == {f.clause_id for f in report.findings}
    assert report.clauses_analysed == 6


def test_role_mismatch_is_warned(analyzer):
    report = analyzer.analyze_text(LEASE, PartyRole.BUYER)
    assert any("выбрана роль" in w for w in report.warnings)


def test_empty_document_gives_warning_not_crash(analyzer):
    report = analyzer.analyze_text("", PartyRole.TENANT)
    assert report.findings == []
    assert any("не найдено ни одного пункта" in w for w in report.warnings)


def test_highlight_escapes_html_and_merges_spans():
    text = "a <b> пеня 1% в день"
    html = str(
        highlight(
            text,
            [Evidence(quote="пеня", start=6, end=10), Evidence(quote="ня 1%", start=8, end=13)],
        )
    )
    assert html == "a &lt;b&gt; <mark>пеня 1%</mark> в день"


def test_html_report_escapes_contract_text_and_has_disclaimer(analyzer):
    report = analyzer.analyze_text(
        LEASE.replace(
            "1.3. Помещение", "1.3. Арендатор уплачивает штраф 50% <script>x</script>. Помещение"
        ),
        PartyRole.TENANT,
    )
    html = render_html(report)
    assert "<script>" not in html
    assert "не юридическое заключение" in html
    assert "<mark>" in html
    assert "Что предложить контрагенту" in html


def test_pdf_report(analyzer):
    pytest.importorskip("weasyprint")
    pdf = render_pdf(analyzer.analyze_text(LEASE, PartyRole.TENANT))
    assert pdf.startswith(b"%PDF")
