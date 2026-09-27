"""Доменные типы: договор, пункт, находка, отчёт.

Все остальные слои — извлечение структуры, правила, ML, LLM, отчёт и eval —
обмениваются только этими типами. Это то, что позволяет сравнивать детекторы
в одном харнессе: у всех одинаковый вход (ContractDocument) и выход (Finding).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ContractType(StrEnum):
    LEASE = "lease"
    SUPPLY = "supply"
    WORKS = "works"


class PartyRole(StrEnum):
    LANDLORD = "landlord"
    TENANT = "tenant"
    SUPPLIER = "supplier"
    BUYER = "buyer"
    CONTRACTOR = "contractor"
    CUSTOMER = "customer"


class Language(StrEnum):
    RU = "ru"
    KK = "kk"


class RiskCategory(StrEnum):
    PENALTY = "penalty"
    AUTO_RENEWAL = "auto_renewal"
    LIABILITY = "liability"
    FORCE_MAJEURE = "force_majeure"
    JURISDICTION = "jurisdiction"
    TERMINATION = "termination"
    UNILATERAL_CHANGE = "unilateral_change"
    PAYMENT = "payment"
    ACCEPTANCE = "acceptance"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def rank(self) -> int:
        return _LEVEL_RANK[self]

    def lowered(self) -> RiskLevel | None:
        """Уровень на ступень ниже; ниже low — «не риск» (None)."""
        return {RiskLevel.HIGH: RiskLevel.MEDIUM, RiskLevel.MEDIUM: RiskLevel.LOW}.get(self)


_LEVEL_RANK = {RiskLevel.LOW: 1, RiskLevel.MEDIUM: 2, RiskLevel.HIGH: 3}

# Пары ролей: (сторона, которая обычно составляет договор, вторая сторона).
# Порядок не несёт оценки — он нужен только для генератора и отчёта.
ROLES_BY_TYPE: dict[ContractType, tuple[PartyRole, PartyRole]] = {
    ContractType.LEASE: (PartyRole.LANDLORD, PartyRole.TENANT),
    ContractType.SUPPLY: (PartyRole.SUPPLIER, PartyRole.BUYER),
    ContractType.WORKS: (PartyRole.CONTRACTOR, PartyRole.CUSTOMER),
}


def contract_type_of(role: PartyRole) -> ContractType:
    for ctype, roles in ROLES_BY_TYPE.items():
        if role in roles:
            return ctype
    raise ValueError(f"неизвестная роль: {role}")


def counterparty(role: PartyRole) -> PartyRole:
    a, b = ROLES_BY_TYPE[contract_type_of(role)]
    return b if role == a else a


ClauseKind = Literal["clause", "heading", "preamble", "requisites"]


class Clause(BaseModel):
    """Пункт договора после сегментации.

    `id` — нормализованный номер без хвостовой точки («5.2»), по нему же
    размечен eval-датасет. Ненумерованные абзацы получают id вида «p7».
    `start`/`end` — смещения в `ContractDocument.text`; `text` — содержимое
    пункта без номера, с перечислениями (а), б), 1)…) внутри.
    """

    id: str
    number: str | None = None
    level: int = 1
    parent_id: str | None = None
    section_id: str | None = None
    section_title: str | None = None
    kind: ClauseKind = "clause"
    text: str
    start: int = 0
    end: int = 0
    page: int | None = None
    lang: Language = Language.RU

    @property
    def analysable(self) -> bool:
        return self.kind == "clause" and bool(self.text.strip())


class ContractDocument(BaseModel):
    doc_id: str
    title: str | None = None
    text: str
    language: Language = Language.RU
    contract_type: ContractType | None = None
    clauses: list[Clause] = Field(default_factory=list)
    source_format: Literal["txt", "docx", "pdf"] = "txt"
    needs_ocr: bool = False
    ocr_used: bool = False
    warnings: list[str] = Field(default_factory=list)

    def clause(self, clause_id: str) -> Clause | None:
        for c in self.clauses:
            if c.id == clause_id:
                return c
        return None

    @property
    def analysable_clauses(self) -> list[Clause]:
        return [c for c in self.clauses if c.analysable]


class Evidence(BaseModel):
    """Дословный фрагмент пункта, на котором основана находка.

    Смещения — внутри `Clause.text`. Инвариант, который проверяют тесты и
    LLM-слой: `clause.text[start:end] == quote`.
    """

    quote: str
    start: int
    end: int


class MarketComparison(BaseModel):
    reference_id: str
    reference_text: str
    similarity: float
    favours: str
    source_id: str
    differences: list[str] = Field(default_factory=list)


FindingSource = Literal["rule", "document_rule", "ml", "llm"]


class Finding(BaseModel):
    clause_id: str | None
    category: RiskCategory
    level: RiskLevel
    source: FindingSource
    rule_id: str | None = None
    title: str
    explanation: str
    evidence: list[Evidence] = Field(default_factory=list)
    safer_wording: str | None = None
    legal_basis: str | None = None
    confidence: float = 1.0
    comparison: list[MarketComparison] = Field(default_factory=list)
    details: dict[str, str | float | int | bool | None] = Field(default_factory=dict)


class Report(BaseModel):
    doc_id: str
    title: str | None
    contract_type: ContractType | None
    party_role: PartyRole
    language: Language
    detector: str
    pipeline_version: str
    generated_at: str
    clauses_total: int
    clauses_analysed: int
    findings: list[Finding]
    warnings: list[str] = Field(default_factory=list)
    clause_texts: dict[str, str] = Field(default_factory=dict)

    def count_by_level(self) -> dict[RiskLevel, int]:
        counts = {level: 0 for level in RiskLevel}
        for f in self.findings:
            counts[f.level] += 1
        return counts
