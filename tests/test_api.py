"""HTTP API: форматы ответа, валидация, ограничения, отсутствие хранения."""

import io

import docx
import pytest
from fastapi.testclient import TestClient

from contract_risk.api.main import create_app
from contract_risk.pipeline import Analyzer
from contract_risk.rules.engine import RulesDetector

LEASE = (
    "ДОГОВОР АРЕНДЫ\n1. Условия\n"
    "1.1. Арендатор уплачивает Арендодателю пеню 1% за каждый день просрочки.\n"
    "1.2. Помещение используется под офис.\n"
)


@pytest.fixture(scope="module")
def client():
    app = create_app(lambda: Analyzer(RulesDetector()))
    with TestClient(app) as c:
        yield c


def test_health_and_taxonomy(client):
    assert client.get("/health").json()["status"] == "ok"
    tax = client.get("/v1/taxonomy").json()
    assert set(tax["roles"]) == {"lease", "supply", "works"}
    assert ".docx" in tax["formats"]


def test_analyze_text_json(client):
    r = client.post("/v1/analyze/text", json={"text": LEASE, "party_role": "tenant"})
    assert r.status_code == 200
    body = r.json()
    assert body["party_role"] == "tenant"
    assert body["findings"][0]["category"] == "penalty"
    assert body["findings"][0]["evidence"][0]["quote"] == "1%"


def test_same_text_other_side_has_no_penalty_finding(client):
    body = client.post("/v1/analyze/text", json={"text": LEASE, "party_role": "landlord"}).json()
    assert all(f["category"] != "penalty" for f in body["findings"])


def test_analyze_docx_upload_html(client):
    document = docx.Document()
    for line in LEASE.splitlines():
        document.add_paragraph(line)
    buf = io.BytesIO()
    document.save(buf)
    r = client.post(
        "/v1/analyze",
        files={"file": ("lease.docx", buf.getvalue(), "application/octet-stream")},
        data={"party_role": "tenant", "format": "html"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "Проверка договора" in r.text


def test_pdf_format(client):
    pytest.importorskip("weasyprint")
    r = client.post(
        "/v1/analyze/text", json={"text": LEASE, "party_role": "tenant", "format": "pdf"}
    )
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_validation_errors(client):
    bad_role = client.post("/v1/analyze/text", json={"text": LEASE, "party_role": "owner"})
    assert bad_role.status_code == 422
    unsupported = client.post(
        "/v1/analyze",
        files={"file": ("c.odt", b"x", "application/octet-stream")},
        data={"party_role": "tenant"},
    )
    assert unsupported.status_code == 415
    empty = client.post(
        "/v1/analyze", files={"file": ("c.txt", b"", "text/plain")}, data={"party_role": "tenant"}
    )
    assert empty.status_code == 400
    broken = client.post(
        "/v1/analyze",
        files={"file": ("c.docx", b"not a zip", "application/octet-stream")},
        data={"party_role": "tenant"},
    )
    assert broken.status_code == 422


def test_upload_size_limit(client, monkeypatch):
    from contract_risk import config

    monkeypatch.setattr(config.get_settings(), "max_upload_mb", 0)
    r = client.post(
        "/v1/analyze",
        files={"file": ("c.txt", LEASE.encode(), "text/plain")},
        data={"party_role": "tenant"},
    )
    assert r.status_code == 413
