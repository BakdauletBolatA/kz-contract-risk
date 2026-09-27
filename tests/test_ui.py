"""Streamlit-интерфейс в безголовом режиме: вставить текст → увидеть находки."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "src/contract_risk/ui/app.py"
LEASE = (
    "ДОГОВОР АРЕНДЫ\n1. Условия\n"
    "1.1. Арендатор уплачивает Арендодателю пеню 1% за каждый день просрочки.\n"
    "1.2. Помещение используется под офис.\n"
)


def test_paste_text_and_get_findings(monkeypatch):
    monkeypatch.setenv("KZCR_DETECTOR", "rules")
    monkeypatch.delenv("KZCR_API_URL", raising=False)
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    at.text_area[0].input(LEASE).run()
    at.button[0].click().run()
    assert not at.exception
    titles = [e.label for e in at.expander]
    assert any("Пеня 1% в день" in t and "пункт 1.1" in t for t in titles)
    assert at.metric[0].value == "1"  # один высокий риск
