"""Эмбеддеры за одним протоколом.

- `hashing` — символьные n-граммы в хэшированном пространстве. Офлайн,
  детерминирован, без весов модели; хорошо ловит почти-дословные
  формулировки и морфологию (пени/пеню/пеня), плохо — перефразы.
  По умолчанию: на нём воспроизводимы eval и тесты.
- `e5` — intfloat/multilingual-e5-small (понимает русский и казахский).
  Лучше на перефразах и между языками, требует extra [embeddings] и
  скачивания весов.

Имя и размерность эмбеддера записываются в pgvector рядом с векторами:
векторы разных эмбеддеров несравнимы, и смешать их молча нельзя.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np


class Embedder(Protocol):
    name: str
    dim: int

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


class HashingEmbedder:
    def __init__(self, dim: int = 1024) -> None:
        from sklearn.feature_extraction.text import HashingVectorizer

        # pgvector строит HNSW-индекс только до 2000 измерений.
        self.dim = dim
        self.name = f"hashing-char3-5-{dim}"
        self._vectorizer = HashingVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            n_features=dim,
            alternate_sign=False,
            norm="l2",
            lowercase=True,
        )

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._vectorizer.transform(texts).toarray().astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([text])[0]


class E5Embedder:
    def __init__(self, model: str = "intfloat/multilingual-e5-small") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover — зависит от окружения
            raise RuntimeError("для e5 нужен extra: pip install -e '.[embeddings]'") from exc
        self._model = SentenceTransformer(model)
        self.dim = int(self._model.get_sentence_embedding_dimension())
        self.name = f"e5:{model}"

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(
            [f"passage: {t}" for t in texts], normalize_embeddings=True
        ).astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self._model.encode([f"query: {text}"], normalize_embeddings=True)[0].astype(
            np.float32
        )


def build_embedder(name: str) -> Embedder:
    if name == "hashing":
        return HashingEmbedder()
    if name == "e5":
        return E5Embedder()
    raise ValueError(f"неизвестный эмбеддер {name!r}: hashing или e5")
