"""HTML- и PDF-отчёт из `Report`.

Отчёт читает предприниматель, а не разработчик: сначала сводка и что
делать, потом пункты по убыванию риска. В каждом пункте — цитата
с подсвеченным фрагментом, объяснение простыми словами, «как обычно пишут»
с разницей в числах и формулировка, которую можно предложить контрагенту.
JSON с теми же данными отдаёт API — отчёт не единственный формат.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from contract_risk.schemas import Evidence, Finding, Report, RiskLevel
from contract_risk.taxonomy import (
    CATEGORY_TITLES,
    CONTRACT_TYPE_TITLES,
    DISCLAIMER,
    LEVEL_ADVICE,
    LEVEL_TITLES,
    ROLE_TITLES,
)

TEMPLATES = Path(__file__).parent / "templates"

SOURCE_TITLES = {
    "rule": "точное правило",
    "document_rule": "проверка договора целиком",
    "ml": "статистическая модель",
    "llm": "языковая модель",
}
FAVOURS_TITLES = {"neutral": "нейтральная формулировка"}

NOT_CHECKED = [
    "соответствие договора обязательным нормам закона и действительность условий;",
    "налоги, валютный контроль, лицензии и разрешения;",
    "цена, объём и характеристики товара или работ — это коммерческие условия;",
    "приложения, на которые договор ссылается, но которых нет в файле.",
]


def highlight(text: str, evidence: list[Evidence]) -> Markup:
    """Текст пункта с подсвеченными доказательствами; всё остальное экранируется."""
    spans = sorted({(e.start, e.end) for e in evidence if 0 <= e.start < e.end <= len(text)})
    merged: list[tuple[int, int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(e, merged[-1][1]))
        else:
            merged.append((s, e))
    out, last = [], 0
    for s, e in merged:
        out.append(escape(text[last:s]))
        out.append(f"<mark>{escape(text[s:e])}</mark>")
        last = e
    out.append(escape(text[last:]))
    return Markup("".join(out).replace("\n", "<br>"))


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals.update(
        CATEGORY_TITLES=CATEGORY_TITLES,
        LEVEL_TITLES=LEVEL_TITLES,
        LEVEL_ADVICE=LEVEL_ADVICE,
        SOURCE_TITLES=SOURCE_TITLES,
        highlight=highlight,
        anchor=finding_anchor,
    )
    return env


def render_html(report: Report) -> str:
    counts = report.count_by_level()
    clause_findings = [f for f in report.findings if f.clause_id is not None]
    document_findings = [f for f in report.findings if f.clause_id is None]
    top = [f for f in report.findings if f.level == RiskLevel.HIGH][:3]
    return (
        _environment()
        .get_template("report.html.j2")
        .render(
            report=report,
            counts={level.value: n for level, n in counts.items()},
            clause_findings=clause_findings,
            document_findings=document_findings,
            top=top,
            contract_type=CONTRACT_TYPE_TITLES.get(report.contract_type, "—")
            if report.contract_type
            else "—",
            role=ROLE_TITLES[report.party_role],
            disclaimer=DISCLAIMER,
            not_checked=NOT_CHECKED,
            favours_title=lambda f: FAVOURS_TITLES.get(
                f, f"вариант в пользу стороны «{_role_title(f)}»"
            ),
            verdict=_verdict(counts),
        )
    )


def _role_title(role_value: str) -> str:
    for role, title in ROLE_TITLES.items():
        if role.value == role_value:
            return title.split(" /")[0].lower()
    return role_value


def _verdict(counts: dict[RiskLevel, int]) -> str:
    if counts[RiskLevel.HIGH]:
        return "Есть условия, которые не стоит подписывать без изменений."
    if counts[RiskLevel.MEDIUM]:
        return "Серьёзных ловушек не найдено, но несколько условий стоит обсудить."
    if counts[RiskLevel.LOW]:
        return "Найдены только распространённые условия, о которых нужно помнить."
    return "Рискованных условий не найдено. Это не гарантия: см. ограничения в конце отчёта."


def render_pdf(report: Report) -> bytes:
    """PDF через WeasyPrint. Нет системных pango/cairo — понятная ошибка, а не падение сервиса."""
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "PDF недоступен: установите extra [pdf] и системные библиотеки pango/cairo"
        ) from exc
    return HTML(string=render_html(report)).write_pdf()


def finding_anchor(f: Finding) -> str:
    return f"f-{f.clause_id or 'doc'}-{f.category.value}"
