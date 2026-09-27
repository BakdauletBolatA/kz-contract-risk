"""Загрузка эталонного корпуса с проверкой лицензионного статуса источников.

Проверка сделана кодом, а не договорённостью: формулировка из источника
со статусом, отличным от разрешённых, не загрузится ни в память, ни
в pgvector. Политика и обоснование — docs/CORPUS_POLICY.md.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, model_validator

from contract_risk.schemas import (
    ROLES_BY_TYPE,
    ContractType,
    Language,
    RiskCategory,
)

LicenseStatus = Literal["authored_cc0", "official_public_domain", "cc_by", "candidate"]
ALLOWED_LICENSES: frozenset[str] = frozenset({"authored_cc0", "official_public_domain", "cc_by"})


class LicenseError(ValueError):
    pass


class Source(BaseModel):
    id: str
    title: str
    license_status: LicenseStatus
    url: str | None = None
    legal_basis: str | None = None
    attribution: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _requirements(self) -> Source:
        if self.license_status == "official_public_domain" and not self.legal_basis:
            raise ValueError(f"{self.id}: для официального документа нужен legal_basis")
        if self.license_status == "cc_by" and not self.attribution:
            raise ValueError(f"{self.id}: для CC BY нужна attribution")
        return self


class ReferenceClause(BaseModel):
    id: str
    contract_type: ContractType
    category: RiskCategory
    lang: Language
    favours: str
    text: str
    source_id: str
    note: str | None = None

    @model_validator(mode="after")
    def _favours_is_known(self) -> ReferenceClause:
        allowed = {"neutral"} | {r.value for r in ROLES_BY_TYPE[self.contract_type]}
        if self.favours not in allowed:
            raise ValueError(f"{self.id}: favours={self.favours}, допустимо {sorted(allowed)}")
        return self


def load_sources(path: Path) -> dict[str, Source]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    sources = [Source(**s) for s in raw["sources"]]
    return {s.id: s for s in sources}


def load_corpus(corpus_dir: Path) -> list[ReferenceClause]:
    sources = load_sources(corpus_dir / "sources.yaml")
    clauses: list[ReferenceClause] = []
    for path in sorted((corpus_dir / "clauses").glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        source_id = raw["source"]
        source = sources.get(source_id)
        if source is None:
            raise LicenseError(f"{path.name}: источник {source_id!r} не описан в sources.yaml")
        if source.license_status not in ALLOWED_LICENSES:
            raise LicenseError(
                f"{path.name}: источник {source_id!r} имеет статус "
                f"{source.license_status!r} — загрузка запрещена политикой корпуса"
            )
        for item in raw["clauses"]:
            clauses.append(
                ReferenceClause(
                    contract_type=raw["contract_type"],
                    source_id=source_id,
                    **{**item, "text": " ".join(item["text"].split())},
                )
            )
    ids = [c.id for c in clauses]
    if len(ids) != len(set(ids)):
        raise ValueError("повторяющиеся id в корпусе")
    return clauses


def corpus_hash(clauses: list[ReferenceClause]) -> str:
    h = hashlib.sha256()
    for c in sorted(clauses, key=lambda c: c.id):
        h.update(c.model_dump_json().encode())
    return h.hexdigest()[:16]
