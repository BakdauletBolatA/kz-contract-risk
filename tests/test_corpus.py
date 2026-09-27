"""Эталонный корпус: лицензии проверяются кодом, баланс сторон, утечка в eval."""

from pathlib import Path

import pytest
import yaml

from contract_risk.corpus.audit import (
    audit_balance,
    audit_coverage,
    audit_leakage,
    jaccard,
)
from contract_risk.corpus.manifest import LicenseError, ReferenceClause, load_corpus
from contract_risk.evaluation.dataset import SPLITS, load_split
from contract_risk.ingestion import parse_text

ROOT = Path(__file__).resolve().parents[1]


def write_corpus(tmp_path: Path, status: str, extra: dict | None = None) -> Path:
    (tmp_path / "clauses").mkdir(parents=True)
    source = {"id": "s1", "title": "t", "license_status": status, **(extra or {})}
    (tmp_path / "sources.yaml").write_text(
        yaml.safe_dump({"sources": [source]}, allow_unicode=True), encoding="utf-8"
    )
    (tmp_path / "clauses/lease.yaml").write_text(
        yaml.safe_dump(
            {
                "contract_type": "lease",
                "source": "s1",
                "clauses": [
                    {
                        "id": "x",
                        "category": "penalty",
                        "lang": "ru",
                        "favours": "neutral",
                        "text": "Текст.",
                    }
                ],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.parametrize("status", ["candidate"])
def test_unapproved_source_is_refused(tmp_path, status):
    with pytest.raises(LicenseError, match="запрещена политикой"):
        load_corpus(write_corpus(tmp_path, status))


def test_official_document_requires_legal_basis(tmp_path):
    with pytest.raises(ValueError, match="legal_basis"):
        load_corpus(write_corpus(tmp_path, "official_public_domain"))
    ok = write_corpus(tmp_path / "ok", "official_public_domain", {"legal_basis": "ст. 8"})
    assert len(load_corpus(ok)) == 1


def test_unknown_source_is_refused(tmp_path):
    path = write_corpus(tmp_path, "authored_cc0")
    (path / "sources.yaml").write_text("sources: []\n", encoding="utf-8")
    with pytest.raises(LicenseError, match="не описан"):
        load_corpus(path)


def test_favours_must_be_a_role_of_this_contract_type():
    with pytest.raises(ValueError, match="favours"):
        ReferenceClause(
            id="x",
            contract_type="lease",
            category="penalty",
            lang="ru",
            favours="supplier",
            text="т",
            source_id="s",
        )


def test_real_corpus_is_balanced_and_covers_categories(corpus):
    assert len(corpus) >= 60
    assert audit_balance(corpus) == []
    assert audit_coverage(corpus) == []
    assert {c.source_id for c in corpus} == {"authored-v1"}


def test_balance_audit_catches_one_sided_corpus(corpus):
    skewed = [c for c in corpus if not (c.contract_type == "lease" and c.favours == "tenant")]
    skewed += [
        c.model_copy(update={"id": f"{c.id}-dup", "favours": "landlord"})
        for c in corpus
        if c.contract_type == "lease" and c.favours == "landlord"
    ]
    assert any("перекос сторон" in p for p in audit_balance(skewed))


def test_corpus_does_not_leak_into_eval(corpus):
    texts = [
        (f"{d.doc_id}:{c.id}", c.text)
        for split in SPLITS
        for d in load_split(ROOT / "data/eval", split)
        for c in parse_text(d.text, d.doc_id).analysable_clauses
    ]
    assert audit_leakage(corpus, texts) == []


def test_jaccard_detects_near_duplicates():
    a = "Арендатор уплачивает пеню 0,1% за каждый день просрочки."
    assert jaccard(a, a) == 1.0
    assert jaccard(a, a.replace("0,1%", "0,2%")) > 0.8
    assert jaccard(a, "Споры рассматриваются в суде.") < 0.2
