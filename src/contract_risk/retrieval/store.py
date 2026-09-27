"""Векторные хранилища эталонного корпуса: в памяти и pgvector.

Оба реализуют один протокол, поэтому пайплайн, тесты и eval не знают,
где живёт корпус. В памяти — для офлайн-режима и воспроизводимого eval;
pgvector — для сервиса, где корпус один на все процессы и пополняется
без передеплоя.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from contract_risk.corpus.manifest import ReferenceClause


@dataclass
class SearchHit:
    clause: ReferenceClause
    score: float


@dataclass
class Filters:
    contract_type: str | None = None
    category: str | None = None
    lang: str | None = None
    favours: str | None = None

    def match(self, c: ReferenceClause) -> bool:
        return (
            (self.contract_type is None or c.contract_type.value == self.contract_type)
            and (self.category is None or c.category.value == self.category)
            and (self.lang is None or c.lang.value == self.lang)
            and (self.favours is None or c.favours == self.favours)
        )


class VectorStore(Protocol):
    def add(self, clauses: Sequence[ReferenceClause], vectors: np.ndarray) -> None: ...

    def search(self, vector: np.ndarray, k: int, filters: Filters) -> list[SearchHit]: ...

    def count(self) -> int: ...


class InMemoryStore:
    def __init__(self) -> None:
        self._clauses: list[ReferenceClause] = []
        self._vectors = np.zeros((0, 0), dtype=np.float32)

    def add(self, clauses: Sequence[ReferenceClause], vectors: np.ndarray) -> None:
        vectors = _normalize(vectors)
        self._vectors = vectors if not self._clauses else np.vstack([self._vectors, vectors])
        self._clauses.extend(clauses)

    def search(self, vector: np.ndarray, k: int, filters: Filters) -> list[SearchHit]:
        idx = [i for i, c in enumerate(self._clauses) if filters.match(c)]
        if not idx:
            return []
        q = _normalize(vector.reshape(1, -1))[0]
        scores = self._vectors[idx] @ q
        order = np.argsort(-scores, kind="stable")[:k]
        return [SearchHit(self._clauses[idx[i]], float(scores[i])) for i in order]

    def count(self) -> int:
        return len(self._clauses)


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return (vectors / np.where(norms == 0, 1, norms)).astype(np.float32)


class IndexMismatchError(RuntimeError):
    pass


class PgVectorStore:
    """Корпус в Postgres + pgvector.

    Таблица создаётся под размерность эмбеддера. В `corpus_meta` хранится,
    каким эмбеддером построены векторы и какая версия корпуса загружена:
    поиск с другим эмбеддером по старым векторам вернул бы мусор без
    единой ошибки, поэтому он запрещён явно (`IndexMismatchError`).
    """

    TABLE = "reference_clauses"

    def __init__(self, dsn: str, embedder_name: str, dim: int) -> None:
        import psycopg
        from pgvector.psycopg import register_vector

        self.embedder_name = embedder_name
        self.dim = dim
        self._conn = psycopg.connect(dsn, autocommit=True)
        self._conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(self._conn)
        try:
            # HNSW с фильтром WHERE отбрасывает строки уже после поиска и может
            # вернуть меньше k. Итеративный скан (pgvector >= 0.8) добирает их.
            self._conn.execute("SET hnsw.iterative_scan = relaxed_order")
        except psycopg.errors.Error:
            pass

    def close(self) -> None:
        self._conn.close()

    def _meta(self) -> dict[str, str]:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS corpus_meta (key text PRIMARY KEY, value text NOT NULL)"
        )
        rows = self._conn.execute("SELECT key, value FROM corpus_meta").fetchall()
        return dict(rows)

    def reset(self, corpus_version: str) -> None:
        """Пересоздать таблицу под текущий эмбеддер и версию корпуса."""
        self._conn.execute(f"DROP TABLE IF EXISTS {self.TABLE}")
        self._conn.execute(
            f"""CREATE TABLE {self.TABLE} (
                id text PRIMARY KEY,
                contract_type text NOT NULL,
                category text NOT NULL,
                lang text NOT NULL,
                favours text NOT NULL,
                source_id text NOT NULL,
                text text NOT NULL,
                note text,
                embedding vector({self.dim}) NOT NULL
            )"""
        )
        self._conn.execute(f"CREATE INDEX ON {self.TABLE} USING hnsw (embedding vector_cosine_ops)")
        self._conn.execute(f"CREATE INDEX ON {self.TABLE} (contract_type, category)")
        self._meta()
        for key, value in {
            "embedder": self.embedder_name,
            "dim": str(self.dim),
            "corpus_version": corpus_version,
        }.items():
            self._conn.execute(
                "INSERT INTO corpus_meta (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, value),
            )

    def check_compatible(self) -> dict[str, str]:
        meta = self._meta()
        if not meta:
            raise IndexMismatchError("корпус в pgvector не загружен: kzcr corpus load")
        if meta.get("embedder") != self.embedder_name or meta.get("dim") != str(self.dim):
            raise IndexMismatchError(
                f"векторы построены эмбеддером {meta.get('embedder')} ({meta.get('dim')}), "
                f"а поиск идёт эмбеддером {self.embedder_name} ({self.dim}): "
                f"kzcr corpus load --rebuild"
            )
        return meta

    def add(self, clauses: Sequence[ReferenceClause], vectors: np.ndarray) -> None:
        vectors = _normalize(vectors)
        with self._conn.cursor() as cur:
            cur.executemany(
                f"""INSERT INTO {self.TABLE}
                    (id, contract_type, category, lang, favours, source_id, text, note, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                      text = EXCLUDED.text, embedding = EXCLUDED.embedding,
                      favours = EXCLUDED.favours, note = EXCLUDED.note""",
                [
                    (
                        c.id,
                        c.contract_type.value,
                        c.category.value,
                        c.lang.value,
                        c.favours,
                        c.source_id,
                        c.text,
                        c.note,
                        v,
                    )
                    for c, v in zip(clauses, vectors, strict=True)
                ],
            )

    def search(self, vector: np.ndarray, k: int, filters: Filters) -> list[SearchHit]:
        q = _normalize(vector.reshape(1, -1))[0]
        conditions, params = [], []
        for column in ("contract_type", "category", "lang", "favours"):
            value = getattr(filters, column)
            if value is not None:
                conditions.append(f"{column} = %s")
                params.append(value)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self._conn.execute(
            f"""SELECT id, contract_type, category, lang, favours, source_id, text, note,
                       1 - (embedding <=> %s) AS score
                FROM {self.TABLE} {where}
                ORDER BY embedding <=> %s
                LIMIT %s""",
            [q, *params, q, k],
        ).fetchall()
        return [
            SearchHit(
                ReferenceClause(
                    id=r[0],
                    contract_type=r[1],
                    category=r[2],
                    lang=r[3],
                    favours=r[4],
                    source_id=r[5],
                    text=r[6],
                    note=r[7],
                ),
                float(r[8]),
            )
            for r in rows
        ]

    def count(self) -> int:
        return int(self._conn.execute(f"SELECT count(*) FROM {self.TABLE}").fetchone()[0])
