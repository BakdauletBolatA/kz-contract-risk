"""Целостность замороженного eval-датасета.

Эти тесты — страховка от тихой порчи эталона: правка текста договора без
правки разметки, ручная «подгонка» сгенерированного файла, утечка
формулировки ловушки из test в dev.
"""

from pathlib import Path

import pytest

from contract_risk.evaluation.dataset import SPLITS, load_split
from contract_risk.evaluation.integrity import check_docs, check_split_leakage
from contract_risk.evaluation.synthetic import generate_doc, load_template
from contract_risk.ingestion import parse_text

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/eval"


@pytest.fixture(scope="module")
def splits():
    return {split: load_split(DATA, split) for split in SPLITS}


@pytest.mark.parametrize("split", SPLITS)
def test_every_gold_clause_is_found_by_segmenter(splits, split):
    assert check_docs(splits[split], parse_text) == []


def test_no_trap_wording_leaks_from_test_into_dev(splits):
    assert check_split_leakage(splits["dev"], splits["test"], parse_text) == []


def test_splits_have_clean_docs_and_both_languages(splits):
    for split in ("dev", "test"):
        docs = splits[split]
        assert sum(d.is_clean for d in docs) >= 20
        assert {d.language.value for d in docs} == {"ru", "kk"}
        # есть договоры с позиции «сильной» стороны — там зеркальные ловушки
        assert {d.party_role.value for d in docs} >= {"landlord", "supplier", "contractor"}


def test_committed_synthetic_files_match_generator(splits):
    """Сгенерированные файлы не правились руками: генератор даёт те же байты."""
    templates = {p.stem: load_template(p) for p in (DATA / "templates").glob("*.yaml")}
    for split in ("dev", "test"):
        for doc in splits[split]:
            name, _, index = doc.doc_id.rpartition(f"_{split}_")
            regenerated = generate_doc(templates[name], split, int(index))
            assert regenerated.text == doc.text, doc.doc_id
            assert regenerated.findings == doc.findings, doc.doc_id


def test_mirror_traps_are_not_labelled_for_the_other_side():
    """Ловушка против арендатора в договоре арендодателя не размечается."""
    template = load_template(DATA / "templates/lease_ru.yaml")
    labelled_roles = set()
    for i in range(1, 200):
        doc = generate_doc(template, "dev", i)
        if doc.party_role.value == "landlord":
            traps = {g.trap_id for g in doc.findings}
            assert "penalty_uncapped" not in traps  # эта ловушка есть только против арендатора
            labelled_roles.add("landlord")
    assert labelled_roles == {"landlord"}
