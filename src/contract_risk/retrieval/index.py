"""Индекс эталонного корпуса: эмбеддер + хранилище + правила поиска."""

from __future__ import annotations

from collections.abc import Sequence

from contract_risk.corpus.manifest import ReferenceClause, corpus_hash
from contract_risk.retrieval.embeddings import Embedder
from contract_risk.retrieval.store import Filters, InMemoryStore, SearchHit, VectorStore


class ReferenceIndex:
    def __init__(self, embedder: Embedder, store: VectorStore, version: str = "") -> None:
        self.embedder = embedder
        self.store = store
        self.version = version

    @classmethod
    def in_memory(cls, clauses: Sequence[ReferenceClause], embedder: Embedder) -> ReferenceIndex:
        store = InMemoryStore()
        store.add(clauses, embedder.embed_documents([c.text for c in clauses]))
        return cls(embedder, store, corpus_hash(list(clauses)))

    def similar(
        self,
        text: str,
        *,
        contract_type: str | None = None,
        category: str | None = None,
        lang: str | None = None,
        favours: str | None = None,
        k: int = 3,
    ) -> list[SearchHit]:
        """Ближайшие эталоны; если на языке пункта эталонов нет — на русском."""
        vector = self.embedder.embed_query(text)
        filters = Filters(contract_type, category, lang, favours)
        hits = self.store.search(vector, k, filters)
        if not hits and lang not in (None, "ru"):
            hits = self.store.search(vector, k, Filters(contract_type, category, "ru", favours))
        return hits


def load_into_pgvector(
    clauses: Sequence[ReferenceClause], embedder: Embedder, dsn: str, rebuild: bool = False
) -> int:
    from contract_risk.retrieval.store import IndexMismatchError, PgVectorStore

    store = PgVectorStore(dsn, embedder.name, embedder.dim)
    try:
        version = corpus_hash(list(clauses))
        try:
            meta = store.check_compatible()
            needs_reset = rebuild or meta.get("corpus_version") != version
        except IndexMismatchError:
            if not rebuild and store._meta():
                raise
            needs_reset = True
        if needs_reset:
            store.reset(version)
            store.add(clauses, embedder.embed_documents([c.text for c in clauses]))
        return store.count()
    finally:
        store.close()
