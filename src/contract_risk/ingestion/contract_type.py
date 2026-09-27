"""Тип договора по ключевым словам в заголовке и начале текста.

Используется только как подсказка в интерфейсе: роль пользователя
(`tenant`, `buyer`…) однозначно задаёт тип, и в анализе участвует она.
"""

from __future__ import annotations

import re

from contract_risk.schemas import ContractType

_PATTERNS: dict[ContractType, list[str]] = {
    ContractType.LEASE: [
        r"аренд",
        r"имущественн\w*\s+найм",
        r"наймодател",
        r"нанимател",
        r"жалға",
        r"жалдау",
    ],
    ContractType.SUPPLY: [r"поставк", r"поставщик", r"жеткіз", r"өнім\s+беруш"],
    ContractType.WORKS: [
        r"подряд",
        r"оказани\w*\s+услуг",
        r"исполнител",
        r"мердігер",
        r"қызмет\w*\s+көрсет",
        r"орындаушы",
    ],
}
_COMPILED = {t: [re.compile(p, re.IGNORECASE) for p in ps] for t, ps in _PATTERNS.items()}


def contract_type_scores(text: str, title: str | None = None) -> dict[ContractType, int]:
    head = text[:3000]
    scores = {}
    for ctype, patterns in _COMPILED.items():
        score = sum(len(p.findall(head)) for p in patterns)
        if title:
            score += 5 * sum(len(p.findall(title)) for p in patterns)
        scores[ctype] = score
    return scores


def detect_contract_type(text: str, title: str | None = None) -> ContractType | None:
    scores = contract_type_scores(text, title)
    best = max(scores, key=lambda t: scores[t])
    return best if scores[best] > 0 else None
