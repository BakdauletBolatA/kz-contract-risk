import json

import pytest
from extraction_data import VALID
from fastapi.testclient import TestClient

from contract_risk.api.main import create_app
from contract_risk.extraction.backends import MockBackend
from contract_risk.extraction.extractor import Extractor


class _FakeAnalyzer:
    detector = type("D", (), {"name": "fake"})()


def _client(respond):
    app = create_app(
        analyzer_factory=lambda: _FakeAnalyzer(),
        extractor_factory=lambda name: Extractor(MockBackend(respond, model=name)),
    )
    return TestClient(app)


def test_extract_ok():
    with _client(lambda s, m: json.dumps(VALID)) as c:
        r = c.post("/extract", json={"text": "договор", "model": "mock:a"})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "ok_first_try"
    assert body["extraction"]["contract_number"] == "189"
    assert body["attempts"] == 1 and body["input_tokens"] >= 0 and "latency_ms" in body


def test_extract_failed_is_502_with_errors():
    with _client(lambda s, m: "мусор") as c:
        r = c.post("/extract", json={"text": "договор"})
    body = r.json()
    assert r.status_code == 502 and body["status"] == "failed" and body["extraction"] is None
    assert body["attempts"] == 2 and len(body["errors"]) == 2


def test_batch_mixed_results_and_totals():
    def respond(system, messages):
        return json.dumps(VALID) if "хороший" in messages[0]["content"] else "мусор"

    with _client(respond) as c:
        r = c.post("/extract/batch", json={"texts": ["хороший 1", "плохой", "хороший 2"]})
    body = r.json()
    assert r.status_code == 200 and body["count"] == 3 and body["ok"] == 2
    assert [i["status"] for i in body["items"]] == ["ok_first_try", "failed", "ok_first_try"]
    assert body["input_tokens"] == sum(i["input_tokens"] for i in body["items"])


def test_unknown_model_spec_is_422():
    def boom(name):
        raise ValueError("неизвестная модель")

    app = create_app(analyzer_factory=lambda: _FakeAnalyzer(), extractor_factory=boom)
    with TestClient(app) as c:
        r = c.post("/extract", json={"text": "x", "model": "что-то"})
    assert r.status_code == 422


def test_empty_batch_rejected():
    with _client(lambda s, m: "{}") as c:
        assert c.post("/extract/batch", json={"texts": []}).status_code == 422


@pytest.mark.parametrize("path", ["/extract", "/extract/batch"])
def test_log_has_no_contract_text(path, caplog):
    secret = "СЕКРЕТНЫЙ-ТЕКСТ-ДОГОВОРА"
    body = {"text": secret} if path == "/extract" else {"texts": [secret]}
    with caplog.at_level("INFO", logger="contract_risk.api"):
        with _client(lambda s, m: json.dumps(VALID)) as c:
            c.post(path, json=body)
    assert caplog.records and secret not in caplog.text
