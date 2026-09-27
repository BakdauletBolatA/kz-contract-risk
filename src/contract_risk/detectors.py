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


DETECTORS = ("null", "rules")


def build_detector(name: str) -> Detector:
    if name == "null":
        return NullDetector()
    if name == "rules":
        from contract_risk.rules.engine import RulesDetector

        return RulesDetector()
    raise ValueError(f"неизвестный детектор {name!r}; доступны: {', '.join(DETECTORS)}")
