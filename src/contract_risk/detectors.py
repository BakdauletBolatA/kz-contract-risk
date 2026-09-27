"""Детекторы рисков за одним протоколом.

Харнесс, пайплайн и API знают только протокол `Detector`: документ и роль
пользователя на входе, список находок на выходе. Поэтому rules, ml, llm и
гибрид сравниваются на одном датасете одной командой, а смена детектора
в API — это смена одной строки конфигурации.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from contract_risk.schemas import ContractDocument, Finding, PartyRole


@runtime_checkable
class Detector(Protocol):
    name: str

    def detect(self, doc: ContractDocument, party_role: PartyRole) -> list[Finding]: ...

    def config(self) -> dict[str, Any]: ...


class NullDetector:
    """Ничего не находит. Нижняя граница: recall = 0, ложных тревог нет.

    Нужен как санити-проверка харнесса: если у null-детектора ненулевой
    recall, сломан харнесс, а не система.
    """

    name = "null"

    def detect(self, doc: ContractDocument, party_role: PartyRole) -> list[Finding]:
        return []

    def config(self) -> dict[str, Any]:
        return {}


DETECTORS = ("null", "rules", "ml", "llm", "hybrid")


def _ml_detector():
    from contract_risk.config import get_settings
    from contract_risk.ingestion import parse_text
    from contract_risk.ml.model import MLDetector, load_or_train

    settings = get_settings()
    return MLDetector(load_or_train(settings.models_dir, settings.data_dir, parse_text))


def build_llm_detector(backend=None):  # noqa: ANN001, ANN201 — LLMBackend | None
    """LLM-детектор с кэшем ответов и эталонами из корпуса для подсказки."""
    from contract_risk.config import get_settings
    from contract_risk.corpus.manifest import load_corpus
    from contract_risk.llm.backends import build_backend
    from contract_risk.llm.cache import ResponseCache
    from contract_risk.llm.classifier import LLMClassifier, LLMDetector
    from contract_risk.retrieval.embeddings import HashingEmbedder
    from contract_risk.retrieval.index import ReferenceIndex

    settings = get_settings()
    backend = backend or build_backend(
        settings.llm_backend, settings.llm_model, settings.llm_effort
    )
    index = ReferenceIndex.in_memory(load_corpus(settings.data_dir / "corpus"), HashingEmbedder())
    classifier = LLMClassifier(
        backend,
        ResponseCache(settings.cache_dir / "llm_responses.sqlite"),
        index,
        settings.llm_workers,
    )
    return LLMDetector(classifier)


def build_detector(name: str) -> Detector:
    from contract_risk.config import get_settings

    if name == "null":
        return NullDetector()
    if name == "rules":
        from contract_risk.rules.engine import RulesDetector

        return RulesDetector()
    if name == "ml":
        return _ml_detector()
    if name == "llm":
        if not get_settings().llm_available:
            raise RuntimeError("LLM-детектору нужен ANTHROPIC_API_KEY (см. .env.example)")
        return build_llm_detector()
    if name == "hybrid":
        from contract_risk.hybrid import HybridDetector
        from contract_risk.rules.engine import RulesDetector

        llm = build_llm_detector() if get_settings().llm_available else None
        return HybridDetector(RulesDetector(), _ml_detector(), llm)
    raise ValueError(f"неизвестный детектор {name!r}; доступны: {', '.join(DETECTORS)}")
