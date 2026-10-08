import json

import pytest
from extraction_data import VALID

from contract_risk.extraction.backends import BackendError, MockBackend
from contract_risk.extraction.extractor import Extractor, parse_json_object
from contract_risk.extraction.schema import ContractExtraction
from contract_risk.llm.cache import ResponseCache


def _bad(**patch):
    return {**VALID, **patch}


def test_schema_accepts_valid():
    assert ContractExtraction.model_validate(VALID).payment_deadline_days == 30


@pytest.mark.parametrize(
    "patch",
    [
        {"contract_date": "1999-01-01"},
        {"price_amount": None, "price_period": "monthly"},
        {"parties": [VALID["parties"][0], VALID["parties"][0]]},
        {"parties": [{"role": "buyer", "name": "ТОО «Б»", "bin": "123"}, VALID["parties"][0]]},
        {"payment_penalty_rate_percent_per_day": 250},
        {"unknown_field": 1},
    ],
)
def test_schema_rejects(patch):
    with pytest.raises(Exception):  # noqa: B017
        ContractExtraction.model_validate(_bad(**patch))


def test_schema_requires_every_key():
    broken = dict(VALID)
    del broken["city"]
    with pytest.raises(Exception):  # noqa: B017
        ContractExtraction.model_validate(broken)


def test_parse_json_object_strips_fences_and_prose():
    assert parse_json_object('Вот:\n```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(ValueError, match="нет JSON"):
        parse_json_object("нет данных")
    with pytest.raises(ValueError, match="невалидный JSON"):
        parse_json_object('{"a": }')


def test_first_try_ok():
    backend = MockBackend(lambda s, m: json.dumps(VALID))
    r = Extractor(backend).extract("текст")
    assert r.status == "ok_first_try" and len(r.attempts) == 1 and backend.calls == 1


def test_retry_sends_validation_error_back():
    seen: list[list[dict]] = []

    def respond(system, messages):
        seen.append(list(messages))
        return json.dumps(_bad(contract_date="1999-01-01") if len(seen) == 1 else VALID)

    r = Extractor(MockBackend(respond)).extract("текст")
    assert r.status == "ok_after_retry" and len(r.attempts) == 2
    assert not r.attempts[0].ok and "contract_date" in r.attempts[0].error
    retry_msgs = seen[1]
    assert retry_msgs[-1]["role"] == "user" and "contract_date" in retry_msgs[-1]["content"]
    assert retry_msgs[-2]["role"] == "assistant"


def test_failed_after_one_retry_only():
    backend = MockBackend(lambda s, m: "не json")
    r = Extractor(backend).extract("текст")
    assert r.status == "failed" and r.extraction is None and backend.calls == 2


def test_no_retry_when_disabled():
    backend = MockBackend(lambda s, m: "не json")
    r = Extractor(backend, max_retries=0).extract("текст")
    assert r.status == "failed" and backend.calls == 1


def test_backend_error_is_not_cached(tmp_path):
    class Boom(MockBackend):
        def complete(self, system, messages):
            raise BackendError("сеть")

    cache = ResponseCache(tmp_path / "c.db")
    r = Extractor(Boom(lambda s, m: ""), cache=cache).extract("текст")
    assert r.status == "backend_error" and len(cache) == 0


def test_cache_returns_same_result_without_calls(tmp_path):
    cache = ResponseCache(tmp_path / "c.db")
    backend = MockBackend(lambda s, m: json.dumps(VALID))
    first = Extractor(backend, cache=cache).extract("текст")
    second = Extractor(backend, cache=cache).extract("текст")
    assert backend.calls == 1 and second.cached and not first.cached
    assert second.extraction == first.extraction
