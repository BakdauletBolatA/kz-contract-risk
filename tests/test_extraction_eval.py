import json
import re

import pytest
from extraction_data import VALID

from contract_risk.extraction.backends import MockBackend
from contract_risk.extraction.eval import (
    GoldDoc,
    compare_fields,
    evaluate,
    load_gold,
    norm_name,
    oracle_backend,
    price_of,
    summary_table,
)
from contract_risk.extraction.extractor import Extractor
from contract_risk.extraction.schema import ContractExtraction

PRICING = {
    "anthropic:m": {"input": 1.0, "output": 5.0},
    "ollama:*": {"input": 0.0, "output": 0.0},
    "anthropic:unknown": {"input": None, "output": None},
}


def test_norm_name_ignores_legal_form_quotes_and_case():
    assert norm_name("ТОО «Дала Агро»") == norm_name("дала агро тоо") == "дала агро"
    assert norm_name("«Кофе Нүкте» ЖШС") == "кофе нүкте"


def test_compare_fields_outcome_kinds():
    gold = dict(VALID)
    pred = {
        **VALID,
        "city": "Астана",
        "term_months": 12,
        "price_amount": 5.0,
        "payment_deadline_days": None,
    }
    out = compare_fields(gold, pred)
    assert out["city"] == "wrong"
    assert out["term_months"] == "hallucinated"
    assert out["price_amount"] == "hallucinated"
    assert out["payment_deadline_days"] == "missed"
    assert out["contract_type"] == "correct" and out["parties.role_bin"] == "correct"


def test_failed_document_is_all_wrong():
    out = compare_fields(dict(VALID), None)
    assert set(out.values()) == {"failed"}


def test_parties_compared_as_sets_not_order():
    pred = {**VALID, "parties": list(reversed(VALID["parties"]))}
    assert compare_fields(dict(VALID), pred)["parties.name"] == "correct"
    wrong_bin = {
        **VALID,
        "parties": [{**VALID["parties"][0], "bin": "000000000000"}, VALID["parties"][1]],
    }
    assert compare_fields(dict(VALID), wrong_bin)["parties.role_bin"] == "wrong"


def test_price_lookup_wildcard_and_unknown():
    assert price_of("ollama:qwen", PRICING) == (0.0, 0.0)
    assert price_of("anthropic:m", PRICING) == (1.0, 5.0)
    assert price_of("anthropic:unknown", PRICING) is None
    assert price_of("anthropic:other", PRICING) is None


def _docs(n=4):
    return [GoldDoc(f"d{i}", "dev", f"текст {i}", dict(VALID)) for i in range(n)]


def test_evaluate_counts_validity_accuracy_and_cost():
    docs = _docs(4)
    bad = {**VALID, "city": "Шымкент", "term_months": 11}  # wrong + hallucinated

    def respond(system, messages):
        text = messages[0]["content"]
        if "текст 0" in text and len(messages) == 1:
            return "не json"  # первая попытка мимо, повтор — ниже
        if "текст 1" in text:
            return json.dumps(bad)
        if "текст 2" in text:
            return "всегда мусор"
        return json.dumps(VALID)

    # текст 0: после «не json» повтор должен дать валидный ответ
    run = evaluate(Extractor(MockBackend(respond)), docs, "anthropic:m", "dev", pricing=PRICING)
    m = run["metrics"]
    assert m["n_docs"] == 4
    assert m["valid_first_try"] == 0.5  # доки 1 и 3
    assert m["valid_after_retry"] == 0.75  # + док 0
    assert m["failed"] == 1
    assert m["field_accuracy"]["city"] == 0.5  # доки 0 и 3
    assert m["hallucination_rate"] == pytest.approx(
        1 / (4 * sum(v is None for k, v in VALID.items() if k != "parties"))
    )
    assert m["cost_usd_per_100_docs"] is not None and m["cost_usd_per_100_docs"] > 0
    assert m["retry_rate"] == 0.5
    statuses = {d["doc_id"]: d["status"] for d in run["docs"]}
    assert statuses == {
        "d0": "ok_after_retry",
        "d1": "ok_first_try",
        "d2": "failed",
        "d3": "ok_first_try",
    }


def test_oracle_backend_is_perfect_after_retry():
    docs = _docs(5)
    docs = [GoldDoc(f"d{i}", "dev", f"текст {i}", dict(VALID)) for i in range(5)]
    run = evaluate(Extractor(oracle_backend(docs)), docs, "mock", "dev", pricing=PRICING)
    assert run["metrics"]["macro_field_accuracy"] == 1.0
    assert 0 < run["metrics"]["valid_first_try"] < 1 and run["metrics"]["valid_after_retry"] == 1.0


def test_table_hides_mock_by_default():
    docs = _docs(2)
    mock = evaluate(Extractor(oracle_backend(docs)), docs, "mock", "dev", pricing=PRICING)
    assert summary_table([mock]).count("\n") == 1  # только шапка
    assert "mock" in summary_table([mock], include_mock=True)


# --- целостность эталона ----------------------------------------------------

SPLITS = ["dev", "test", "hard"]


@pytest.mark.parametrize("split", SPLITS)
def test_gold_validates_against_schema_and_text(split):
    docs = load_gold(split)
    assert docs
    for d in docs:
        ContractExtraction.model_validate(d.labels)
        flat = re.sub(r"\s+", " ", d.text)
        assert d.labels["contract_number"] in flat, d.doc_id
        for p in d.labels["parties"]:
            if p["bin"]:
                assert p["bin"] in flat, (d.doc_id, p)
        if d.labels["price_amount"]:
            digits = f"{int(d.labels['price_amount']):,}".replace(",", " ")
            assert digits in flat.replace("\xa0", " "), (d.doc_id, digits)
        rate = d.labels["payment_penalty_rate_percent_per_day"]
        if rate is not None:
            variants = {str(rate).replace(".", ","), f"{rate:g}".replace(".", ",")}
            assert any(v in flat for v in variants), (d.doc_id, rate)


def test_gold_has_no_overlap_between_splits_and_enough_docs():
    ids = [d.doc_id for s in SPLITS for d in load_gold(s)]
    assert len(ids) == len(set(ids)) >= 60
    assert len(load_gold("test")) >= 30
