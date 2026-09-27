"""LLM-классификатор пунктов: промпт, кэш, проверка цитаты, статистика.

Защита от «LLM сказала, что это плохо» без оснований:

1. **Дословная цитата.** Модель обязана вернуть фрагмент пункта, на котором
   основан вывод. Цитата ищется в тексте пункта (с нормализацией пробелов,
   кавычек и регистра); не нашлась — находка отбрасывается и считается в
   `rejected_ungrounded`. Так галлюцинация не попадает в отчёт.
2. **Схема.** Ответ строго по Pydantic-схеме; «рискованно», но без категории
   или уровня — отбрасывается (`rejected_invalid`).
3. **Порог уверенности.** Находки с confidence < 0,5 не выдаются.
4. **Воспроизводимость.** Кэш по хэшу (модель, версия промпта, вход):
   повторный прогон даёт те же находки; версия промпта пишется в каждую
   находку и в результат eval.
"""

from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from contract_risk.llm.backends import ClauseAssessment, LLMBackend, LLMReply
from contract_risk.llm.cache import ResponseCache, cache_key
from contract_risk.llm.redact import redact
from contract_risk.retrieval.index import ReferenceIndex
from contract_risk.schemas import (
    Clause,
    ContractDocument,
    ContractType,
    Evidence,
    Finding,
    PartyRole,
    RiskCategory,
    RiskLevel,
    contract_type_of,
    counterparty,
)
from contract_risk.taxonomy import CATEGORY_TITLES, CONTRACT_TYPE_TITLES, ROLE_TITLES

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "clause_v1.txt"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")
PROMPT_VERSION = f"clause_v1:{hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:8]}"
MIN_CONFIDENCE = 0.5


@dataclass
class LLMStats:
    calls: int = 0
    cache_hits: int = 0
    refusals: int = 0
    errors: int = 0
    rejected_ungrounded: int = 0
    rejected_invalid: int = 0
    low_confidence: int = 0
    redactions: int = 0


# --- проверка цитаты ---------------------------------------------------------

_QUOTE_CHARS = str.maketrans({"«": '"', "»": '"', "“": '"', "”": '"', "„": '"', "ё": "е", "Ё": "Е"})


def _normalized_with_map(text: str) -> tuple[str, list[int]]:
    """Текст без повторных пробелов, в нижнем регистре, + карта индексов в исходный."""
    out, index = [], []
    prev_space = False
    for i, ch in enumerate(text.translate(_QUOTE_CHARS)):
        if ch.isspace():
            if prev_space:
                continue
            ch, prev_space = " ", True
        else:
            prev_space = False
        out.append(ch.lower())
        index.append(i)
    return "".join(out), index


def ground(quote: str, clause_text: str) -> Evidence | None:
    """Дословная цитата → смещения в тексте пункта; нет в тексте — None."""
    q = " ".join(quote.translate(_QUOTE_CHARS).split()).lower().strip(" .,;:\"'")
    if len(q) < 3:
        return None
    norm, index = _normalized_with_map(clause_text)
    pos = norm.find(q)
    if pos < 0:
        return None
    start, end = index[pos], index[pos + len(q) - 1] + 1
    return Evidence(quote=clause_text[start:end], start=start, end=end)


# --- классификатор -----------------------------------------------------------


class LLMClassifier:
    def __init__(
        self,
        backend: LLMBackend,
        cache: ResponseCache | None = None,
        index: ReferenceIndex | None = None,
        max_workers: int = 4,
    ) -> None:
        self.backend = backend
        self.cache = cache
        self.index = index
        self.max_workers = max_workers
        self.stats = LLMStats()

    def user_message(self, clause: Clause, contract_type: ContractType, user: PartyRole) -> str:
        text, n = redact(clause.text)
        self.stats.redactions += n
        other = counterparty(user)
        lines = [
            f"Тип договора: {CONTRACT_TYPE_TITLES[contract_type]} ({contract_type.value}).",
            f"Роль пользователя: {ROLE_TITLES[user]} ({user.value}). "
            f"Контрагент: {ROLE_TITLES[other]} ({other.value}).",
        ]
        if clause.section_title:
            lines.append(f"Раздел договора: {clause.section_title}")
        lines += ["", f"Пункт {clause.id}:", f"«{text}»"]
        if self.index is not None:
            hits = self.index.similar(
                clause.text,
                contract_type=contract_type.value,
                lang=clause.lang.value,
                favours="neutral",
                k=2,
            )
            if hits:
                lines += ["", "Как похожие условия обычно звучат на рынке (нейтральные эталоны):"]
                lines += [f"{i}. «{h.clause.text}»" for i, h in enumerate(hits, start=1)]
        return "\n".join(lines)

    def assess(
        self, clause: Clause, contract_type: ContractType, user: PartyRole
    ) -> tuple[ClauseAssessment | None, bool]:
        """Оценка пункта и признак «из кэша»."""
        message = self.user_message(clause, contract_type, user)
        key = cache_key(self.backend.model, PROMPT_VERSION, SYSTEM_PROMPT, message)
        if self.cache is not None and (hit := self.cache.get(key)) is not None:
            self.stats.cache_hits += 1
            if hit.get("refusal"):
                self.stats.refusals += 1
                return None, True
            return ClauseAssessment(**hit["assessment"]), True

        self.stats.calls += 1
        try:
            reply: LLMReply = self.backend.assess(SYSTEM_PROMPT, message)
        except Exception as exc:  # noqa: BLE001 — сбой одного пункта не должен ронять отчёт
            self.stats.errors += 1
            log.warning("LLM недоступна для пункта %s: %s", clause.id, type(exc).__name__)
            return None, False
        if reply.assessment is None:
            self.stats.refusals += 1
            if self.cache is not None and reply.stop_reason == "refusal":
                self.cache.put(key, self.backend.model, PROMPT_VERSION, {"refusal": True})
            return None, False
        if self.cache is not None:
            self.cache.put(
                key,
                self.backend.model,
                PROMPT_VERSION,
                {"assessment": reply.assessment.model_dump(), "served_by": reply.model},
            )
        return reply.assessment, False


class LLMDetector:
    """Находки LLM с дословной цитатой; используется гибридом и отдельно в eval."""

    name = "llm"

    def __init__(self, classifier: LLMClassifier) -> None:
        self.classifier = classifier

    def assess_clauses(
        self, doc: ContractDocument, clauses: list[Clause], user: PartyRole
    ) -> list[Finding]:
        ctype = contract_type_of(user)
        with ThreadPoolExecutor(max_workers=self.classifier.max_workers) as pool:
            results = list(pool.map(lambda c: self.classifier.assess(c, ctype, user), clauses))
        findings = []
        for clause, (assessment, cached) in zip(clauses, results, strict=True):
            finding = self._finding(clause, assessment, cached)
            if finding is not None:
                findings.append(finding)
        return findings

    def _finding(self, clause: Clause, a: ClauseAssessment | None, cached: bool) -> Finding | None:
        stats = self.classifier.stats
        if a is None or not a.is_risky:
            return None
        if a.category is None or a.level is None:
            stats.rejected_invalid += 1
            return None
        confidence = min(max(a.confidence, 0.0), 1.0)
        if confidence < MIN_CONFIDENCE:
            stats.low_confidence += 1
            return None
        evidence = ground(a.evidence_quote, clause.text)
        if evidence is None:
            stats.rejected_ungrounded += 1
            return None
        category = RiskCategory(a.category)
        return Finding(
            clause_id=clause.id,
            category=category,
            level=RiskLevel(a.level),
            source="llm",
            title=CATEGORY_TITLES[category],
            explanation=a.explanation.strip() + " (Оценка языковой модели по цитате из пункта.)",
            evidence=[evidence],
            safer_wording=a.safer_wording,
            confidence=round(confidence, 3),
            details={
                "model": self.classifier.backend.model,
                "prompt_version": PROMPT_VERSION,
                "cached": cached,
            },
        )

    def detect(self, doc: ContractDocument, party_role: PartyRole) -> list[Finding]:
        return self.assess_clauses(doc, doc.analysable_clauses, party_role)

    def config(self) -> dict[str, Any]:
        return {
            "backend": self.classifier.backend.name,
            "model": self.classifier.backend.model,
            "prompt_version": PROMPT_VERSION,
            "stats": asdict(self.classifier.stats),
        }
