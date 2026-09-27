"""Нормализация текста договора перед сегментацией.

Всё, что здесь делается, — обратимо-безопасно для смысла: пробелы,
невидимые символы, переносы слов и служебные строки страниц. Текст
пункта не переписывается, иначе цитата-доказательство в отчёте разошлась
бы с тем, что пользователь видит в своём файле.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

_INVISIBLE = re.compile(r"[​‌‍⁠﻿­]")
_SPACES = re.compile(r"[    \t]")
_MULTISPACE = re.compile(r" {2,}")
# Перенос слова на границе строки: «обяза-\nтельства». Только между строчными
# буквами — «бизнес-\nЦентр» или «1-\n2» не склеиваются.
_HYPHEN_BREAK = re.compile(r"([а-яёәғқңөұүһіa-z])-\n([а-яёәғқңөұүһіa-z])")
_PAGE_MARKER = re.compile(
    r"^(?:"
    r"(?:стр(?:аница)?|бет)\.?\s*\d+(?:\s*(?:из|/)\s*\d+)?"
    r"|[-–—]\s*\d{1,3}\s*[-–—]"
    r"|\d{1,3}\s*(?:из|/)\s*\d{1,3}"
    r"|\d{1,3}\s*[-‐]\s*бет"
    r")$",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _INVISIBLE.sub("", text)
    text = _SPACES.sub(" ", text)
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    lines = [_MULTISPACE.sub(" ", line).strip() for line in text.split("\n")]
    lines = [line for line in lines if not _PAGE_MARKER.match(line)]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n" if text.strip() else ""


def strip_repeated_lines(pages: list[str], min_share: float = 0.5) -> list[str]:
    """Убирает колонтитулы: короткие строки, повторяющиеся на большинстве страниц.

    Работает только при трёх и более страницах — на двух страницах повтор
    строки ничего не доказывает (например, «Арендатор:» в двух местах).
    """
    if len(pages) < 3:
        return pages
    counts: Counter[str] = Counter()
    for page in pages:
        counts.update({line.strip() for line in page.split("\n") if line.strip()})
    threshold = max(3, int(len(pages) * min_share + 0.5))
    repeated = {line for line, n in counts.items() if n >= threshold and len(line) <= 100}
    if not repeated:
        return pages
    return [
        "\n".join(line for line in page.split("\n") if line.strip() not in repeated)
        for page in pages
    ]
