"""Эмбеддеры и хранилища: in-memory всегда, pgvector — при KZCR_TEST_DSN.

pgvector тестируется настоящий: фильтры, порядок выдачи и защиту от смены
эмбеддера нечем замокать — проверять надо поведение базы.
"""

import numpy as np
import pytest

from contract_risk.retrieval.embeddings import HashingEmbedder
from contract_risk.retrieval.index import ReferenceIndex, load_into_pgvector
from contract_risk.retrieval.store import Filters, IndexMismatchError, PgVectorStore

QUERY = "За просрочку арендной платы Арендатор платит пеню 0,1% в день, но не более 10%."


def test_hashing_embedder_is_deterministic_and_normalized():
    e = HashingEmbedder()
    a, b = e.embed_documents([QUERY]), e.embed_documents([QUERY])
    assert np.array_equal(a, b)
    assert a.shape == (1, e.dim)
    assert np.isclose(np.linalg.norm(a[0]), 1.0)


def test_morphology_close_topics_far():
    e = HashingEmbedder()
    q = e.embed_query("Арендатор уплачивает пеню за просрочку платежа")
    near = e.embed_query("Арендатором уплачиваются пени за просрочку платежей")
    far = e.embed_query("Споры разрешаются в суде по месту нахождения ответчика")
    assert q @ near > q @ far + 0.2


def test_in_memory_index_filters_and_ranks(corpus):
    index = ReferenceIndex.in_memory(corpus, HashingEmbedder())
    hits = index.similar(QUERY, contract_type="lease", category="penalty", k=3)
    assert len(hits) == 3
    assert all(h.clause.category.value == "penalty" for h in hits)
    assert hits[0].score >= hits[1].score >= hits[2].score
    neutral = index.similar(QUERY, contract_type="lease", category="penalty", favours="neutral")
    assert {h.clause.favours for h in neutral} == {"neutral"}


def test_language_fallback_to_russian(corpus):
    index = ReferenceIndex.in_memory(corpus, HashingEmbedder())
    # казахских эталонов поставки нет — берутся русские
    hits = index.similar(
        "Сатып алушы төлейді", contract_type="supply", category="payment", lang="kk"
    )
    assert hits and all(h.clause.lang.value == "ru" for h in hits)


@pytest.mark.pg
def test_pgvector_matches_in_memory_ranking(pg_dsn, corpus):
    embedder = HashingEmbedder()
    assert load_into_pgvector(corpus, embedder, pg_dsn, rebuild=True) == len(corpus)
    store = PgVectorStore(pg_dsn, embedder.name, embedder.dim)
    try:
        store.check_compatible()
        pg_index = ReferenceIndex(embedder, store)
        mem_index = ReferenceIndex.in_memory(corpus, embedder)
        kwargs = {"contract_type": "lease", "category": "penalty", "k": 4}
        pg_hits = pg_index.similar(QUERY, **kwargs)
        mem_hits = mem_index.similar(QUERY, **kwargs)
        assert [h.clause.id for h in pg_hits] == [h.clause.id for h in mem_hits]
        assert pg_hits[0].score == pytest.approx(mem_hits[0].score, abs=1e-4)
        assert store.search(embedder.embed_query(QUERY), 50, Filters(lang="kk"))
    finally:
        store.close()


@pytest.mark.pg
def test_pgvector_refuses_other_embedder(pg_dsn, corpus):
    embedder = HashingEmbedder()
    load_into_pgvector(corpus, embedder, pg_dsn, rebuild=True)
    other = PgVectorStore(pg_dsn, "hashing-char3-5-512", 512)
    try:
        with pytest.raises(IndexMismatchError, match="--rebuild"):
            other.check_compatible()
    finally:
        other.close()


@pytest.mark.pg
def test_reload_without_changes_keeps_table(pg_dsn, corpus):
    embedder = HashingEmbedder()
    load_into_pgvector(corpus, embedder, pg_dsn, rebuild=True)
    assert load_into_pgvector(corpus, embedder, pg_dsn) == len(corpus)
