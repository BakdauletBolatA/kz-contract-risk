"""Русский или казахский — по буквам, которых нет в русском алфавите.

Словарные модели определения языка на коротких юридических фразах путают
казахский с русским (общая кириллица, общие заимствования: «договор»,
«арбитраж»). Специфичные буквы казахского алфавита — прямой и объяснимый
признак: в казахском тексте их обычно 5–10% от кириллических букв, в русском —
ноль, если не считать казахских топонимов в адресах.
"""

from __future__ import annotations

from contract_risk.schemas import Language

KAZAKH_LETTERS = frozenset("әғқңөұүһіӘҒҚҢӨҰҮҺІ")

# Порог на уровне документа ниже, чем на уровне пункта: в русском договоре
# с казахскими названиями улиц доля всё равно доли процента, а в коротком
# русском пункте с адресом «Құрманғазы көшесі» — уже несколько процентов.
DOC_THRESHOLD = 0.02
CLAUSE_THRESHOLD = 0.03


def kazakh_share(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha() and ("Ѐ" <= ch <= "ӿ")]
    if not letters:
        return 0.0
    return sum(ch in KAZAKH_LETTERS for ch in letters) / len(letters)


def detect_language(text: str, threshold: float = DOC_THRESHOLD) -> Language:
    kk_count = sum(ch in KAZAKH_LETTERS for ch in text)
    if kk_count >= 2 and kazakh_share(text) >= threshold:
        return Language.KK
    return Language.RU
