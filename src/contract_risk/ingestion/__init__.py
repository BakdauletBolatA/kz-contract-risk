"""Извлечение структуры: файл → нормализованный текст → пункты.

Точки входа:

- `parse_text` — строка текста (eval-датасет, тесты, API /analyze/text);
- `parse_bytes` — загруженный файл (TXT, DOCX, PDF; сканы — через OCR).
"""

from __future__ import annotations

import bisect
import hashlib
from collections import Counter

from contract_risk.ingestion.contract_type import detect_contract_type
from contract_risk.ingestion.language import detect_language
from contract_risk.ingestion.loaders import RawDocument, load_bytes
from contract_risk.ingestion.normalize import normalize_text
from contract_risk.ingestion.ocr import OcrEngine
from contract_risk.ingestion.segmenter import segment
from contract_risk.schemas import ContractDocument, Language

__all__ = ["parse_bytes", "parse_raw", "parse_text"]


def parse_text(text: str, doc_id: str = "doc") -> ContractDocument:
    return parse_raw(RawDocument(normalize_text(text), "txt"), doc_id)


def parse_bytes(
    data: bytes,
    filename: str,
    doc_id: str | None = None,
    *,
    ocr: OcrEngine | None = None,
    prefer_language: Language = Language.RU,
) -> ContractDocument:
    raw = load_bytes(data, filename, ocr=ocr, prefer_language=prefer_language)
    return parse_raw(raw, doc_id or hashlib.sha256(data).hexdigest()[:12])


def parse_raw(raw: RawDocument, doc_id: str) -> ContractDocument:
    result = segment(raw.text) if raw.text.strip() else None
    clauses = result.clauses if result else []
    if raw.page_starts:
        for clause in clauses:
            clause.page = bisect.bisect_right(raw.page_starts, clause.start)

    weights: Counter[Language] = Counter()
    for clause in clauses:
        if clause.analysable:
            weights[clause.lang] += len(clause.text)
    language = weights.most_common(1)[0][0] if weights else detect_language(raw.text)

    title = result.title if result else None
    return ContractDocument(
        doc_id=doc_id,
        title=title,
        text=raw.text,
        language=language,
        contract_type=detect_contract_type(raw.text, title),
        clauses=clauses,
        source_format=raw.source_format,  # type: ignore[arg-type]
        needs_ocr=raw.needs_ocr,
        ocr_used=raw.ocr_used,
        warnings=[*raw.warnings, *(result.warnings if result else [])],
    )
