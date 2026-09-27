"""Streamlit-интерфейс MVP.

    streamlit run src/contract_risk/ui/app.py

Если задан KZCR_API_URL, интерфейс ходит в FastAPI-сервис; иначе вызывает
пайплайн в своём процессе — так MVP запускается одной командой.
"""

from __future__ import annotations

import os

import streamlit as st

from contract_risk.config import Settings
from contract_risk.pipeline import Analyzer, default_role
from contract_risk.report.render import highlight, render_html, render_pdf
from contract_risk.schemas import ROLES_BY_TYPE, ContractType, Language, Report, RiskLevel
from contract_risk.taxonomy import (
    CATEGORY_TITLES,
    CONTRACT_TYPE_TITLES,
    DISCLAIMER,
    LEVEL_ADVICE,
    LEVEL_TITLES,
    ROLE_TITLES,
)

LEVEL_ICONS = {RiskLevel.HIGH: "🔴", RiskLevel.MEDIUM: "🟠", RiskLevel.LOW: "🔵"}


@st.cache_resource(show_spinner="Загружаю правила, модель и эталонный корпус…")
def get_analyzer() -> Analyzer:
    return Analyzer.from_settings(Settings())


def analyze(
    data: bytes | None, filename: str | None, text: str, role, language: Language
) -> Report:
    api_url = os.environ.get("KZCR_API_URL")
    if api_url:
        import httpx

        if data is not None:
            response = httpx.post(
                f"{api_url.rstrip('/')}/v1/analyze",
                files={"file": (filename, data)},
                data={"party_role": role.value, "prefer_language": language.value},
                timeout=300,
            )
        else:
            response = httpx.post(
                f"{api_url.rstrip('/')}/v1/analyze/text",
                json={"text": text, "party_role": role.value},
                timeout=300,
            )
        response.raise_for_status()
        return Report.model_validate(response.json())
    analyzer = get_analyzer()
    if data is not None:
        return analyzer.analyze_bytes(data, filename or "upload.txt", role, language)
    return analyzer.analyze_text(text, role)


def show_report(report: Report) -> None:
    counts = report.count_by_level()
    cols = st.columns(3)
    for col, level in zip(cols, (RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW), strict=True):
        col.metric(f"{LEVEL_ICONS[level]} {LEVEL_TITLES[level]}", counts[level])
    for warning in report.warnings:
        st.warning(warning)
    if not report.findings:
        st.success("Рискованных условий не найдено. Это не гарантия — см. ограничения ниже.")

    for f in report.findings:
        where = f"пункт {f.clause_id}" if f.clause_id else "договор целиком"
        with st.expander(
            f"{LEVEL_ICONS[f.level]} {f.title} — {where}", expanded=f.level == RiskLevel.HIGH
        ):
            st.caption(f"{LEVEL_TITLES[f.level]} · {CATEGORY_TITLES[f.category]}")
            if f.clause_id:
                st.markdown("**Что написано**")
                st.markdown(
                    highlight(report.clause_texts.get(f.clause_id, ""), f.evidence),
                    unsafe_allow_html=True,  # highlight() экранирует текст договора
                )
            st.markdown("**Чем это грозит**")
            st.write(f.explanation)
            st.caption(LEVEL_ADVICE[f.level])
            neutral = [c for c in f.comparison if c.favours == "neutral"]
            if neutral:
                st.markdown("**Как такое условие обычно звучит**")
                st.info(neutral[0].reference_text)
                for d in dict.fromkeys(d for c in neutral for d in c.differences):
                    st.markdown(f"- {d}")
            if f.safer_wording:
                st.markdown("**Что предложить контрагенту**")
                st.success(f.safer_wording)
            if f.legal_basis:
                st.caption(f"Где почитать: {f.legal_basis}")

    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.download_button("Отчёт HTML", render_html(report), "contract-report.html", mime="text/html")
    try:
        c2.download_button(
            "Отчёт PDF", render_pdf(report), "contract-report.pdf", mime="application/pdf"
        )
    except RuntimeError as exc:
        c2.caption(str(exc))
    c3.download_button(
        "Данные JSON",
        report.model_dump_json(indent=2),
        "contract-report.json",
        mime="application/json",
    )


def main() -> None:
    st.set_page_config(page_title="Проверка договора", page_icon="📄", layout="centered")
    st.title("Проверка договора")
    st.caption(DISCLAIMER)

    ctype = st.selectbox(
        "Тип договора",
        list(ContractType),
        format_func=lambda t: CONTRACT_TYPE_TITLES[t],
    )
    roles = list(ROLES_BY_TYPE[ctype])
    role = st.radio(
        "Кто вы в этом договоре",
        roles,
        index=roles.index(default_role(ctype)),
        format_func=lambda r: ROLE_TITLES[r],
        horizontal=True,
    )
    language = st.radio(
        "Если договор на двух языках, анализировать",
        list(Language),
        format_func=lambda lang: {"ru": "русский текст", "kk": "казахский текст"}[lang.value],
        horizontal=True,
    )

    uploaded = st.file_uploader("Файл договора", type=["docx", "pdf", "txt"])
    text = st.text_area("…или вставьте текст договора", height=200)
    st.caption("Файл обрабатывается в памяти и не сохраняется.")

    if st.button("Проверить", type="primary", disabled=not (uploaded or text.strip())):
        with st.spinner("Проверяю пункты договора…"):
            report = analyze(
                uploaded.getvalue() if uploaded else None,
                uploaded.name if uploaded else None,
                text,
                role,
                language,
            )
        st.session_state["report"] = report
    if "report" in st.session_state:
        show_report(st.session_state["report"])


main()
