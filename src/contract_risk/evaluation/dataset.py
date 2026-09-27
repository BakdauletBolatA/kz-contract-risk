"""Формат eval-датасета и его загрузка.

Каждый договор — пара файлов в `data/eval/<split>/`:

- `<doc_id>.txt` — текст договора, ровно в том виде, в каком его получит
  система (через тот же сегментатор, что и пользовательский файл);
- `<doc_id>.yaml` — метаданные и эталонные находки.

Пункт, не упомянутый в `findings`, — эталонный негатив: если система его
пометила, это ложная тревога. Поэтому разметка обязана быть полной, а не
«отметил, что заметил».
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from contract_risk.schemas import (
    ContractType,
    Language,
    PartyRole,
    RiskCategory,
    RiskLevel,
    contract_type_of,
)

SPLITS = ("dev", "test", "handwritten")
Origin = Literal["synthetic", "handwritten", "public"]


class GoldFinding(BaseModel):
    clause: str | None
    category: RiskCategory
    level: RiskLevel
    trap_id: str | None = None
    note: str | None = None


class EvalDoc(BaseModel):
    doc_id: str
    split: str
    contract_type: ContractType
    language: Language
    party_role: PartyRole
    origin: Origin
    findings: list[GoldFinding] = Field(default_factory=list)
    text: str = ""

    @model_validator(mode="after")
    def _role_matches_type(self) -> EvalDoc:
        if contract_type_of(self.party_role) != self.contract_type:
            raise ValueError(
                f"{self.doc_id}: роль {self.party_role} не относится к типу {self.contract_type}"
            )
        return self

    @property
    def is_clean(self) -> bool:
        return not self.findings

    @property
    def clause_findings(self) -> list[GoldFinding]:
        return [f for f in self.findings if f.clause is not None]

    @property
    def document_findings(self) -> list[GoldFinding]:
        return [f for f in self.findings if f.clause is None]


def load_doc(label_path: Path, split: str) -> EvalDoc:
    meta = yaml.safe_load(label_path.read_text(encoding="utf-8"))
    text_path = label_path.with_suffix(".txt")
    if not text_path.exists():
        raise FileNotFoundError(f"нет текста договора для разметки {label_path}")
    return EvalDoc(split=split, text=text_path.read_text(encoding="utf-8"), **meta)


def load_split(root: Path, split: str) -> list[EvalDoc]:
    split_dir = root / split
    if not split_dir.is_dir():
        raise FileNotFoundError(f"нет среза {split}: {split_dir}")
    docs = [load_doc(p, split) for p in sorted(split_dir.glob("*.yaml"))]
    ids = [d.doc_id for d in docs]
    if len(ids) != len(set(ids)):
        raise ValueError(f"повторяющиеся doc_id в срезе {split}")
    return docs


def dump_labels(doc: EvalDoc) -> str:
    """YAML разметки в стабильном порядке ключей — чтобы диффы были читаемыми."""
    payload = {
        "doc_id": doc.doc_id,
        "contract_type": doc.contract_type.value,
        "language": doc.language.value,
        "party_role": doc.party_role.value,
        "origin": doc.origin,
        "findings": [
            {k: v for k, v in f.model_dump(mode="json").items() if v is not None or k == "clause"}
            for f in doc.findings
        ],
    }
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


def dataset_hash(docs: list[EvalDoc]) -> str:
    """Хэш содержимого среза: текст + разметка. Любая правка — другой хэш,
    и прогон с другим хэшем несравним с прошлыми строками EVALUATION.md."""
    h = hashlib.sha256()
    for doc in sorted(docs, key=lambda d: d.doc_id):
        h.update(doc.doc_id.encode())
        h.update(doc.text.encode())
        h.update(dump_labels(doc).encode())
    return h.hexdigest()[:16]
