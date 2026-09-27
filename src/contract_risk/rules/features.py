"""Числа из текста пункта: ставки неустойки, потолки, сроки.

Числовые признаки — самая объяснимая часть системы: «пеня 1% в день, это
365% годовых, потолка нет» проверяется глазами за секунду. Они же нужны
RAG-слою, чтобы показать разницу с эталоном не словами, а числами.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from contract_risk.rules import lexicon as lx

_WORD_NUMBERS = {
    "одного": 1, "одной": 1, "один": 1, "одну": 1, "одна": 1, "двух": 2, "два": 2, "две": 2,
    "трех": 3, "трёх": 3, "три": 3, "четырех": 4, "четыре": 4, "пяти": 5, "пять": 5,
    "шести": 6, "шесть": 6, "семи": 7, "семь": 7, "десяти": 10, "десять": 10,
    "четырнадцати": 14, "пятнадцати": 15, "двадцати": 20, "тридцати": 30, "тридцать": 30,
    "шестидесяти": 60, "шестьдесят": 60, "девяноста": 90, "девяносто": 90,
    "бір": 1, "екі": 2, "үш": 3, "бес": 5, "алты": 6, "он": 10, "отыз": 30,
}  # fmt: skip
_MONTH_ADJ = {"одномесячн": 1, "месячн": 1, "двухмесячн": 2, "трехмесячн": 3, "трёхмесячн": 3,
              "шестимесячн": 6}  # fmt: skip

_NUM = r"(?P<n>\d+|" + "|".join(sorted(_WORD_NUMBERS, key=len, reverse=True)) + r")"
_PAREN = r"(?:\s*\([^)]{1,40}\))?"
_DAYS_RE = re.compile(
    rf"(?<![\w,.]){_NUM}{_PAREN}\s*(?:календарн\w*|рабоч\w*|банковск\w*|күнтізбелік|жұмыс|банктік)?\s*"
    r"(?P<unit>дн(?:я|ей|и)\b|день\b|сут\w*|час\w*|күн\w*|сағат\w*)",
    re.IGNORECASE,
)
_MONTHS_RE = re.compile(
    rf"(?:(?<![\w,.]){_NUM}{_PAREN}\s*|(?<=за\s)|(?<=через\s))"
    r"(?P<unit>месяц\w*|ай\b|айға|айды|айдан)",
    re.IGNORECASE,
)
_KK_MONTH_ADJ_RE = re.compile(r"(?P<n>бір|екі|үш|алты|\d+)\s+айлық", re.IGNORECASE)
_MONTH_ADJ_RE = re.compile(
    r"(?P<adj>" + "|".join(sorted(_MONTH_ADJ, key=len, reverse=True)) + r")\w*", re.IGNORECASE
)


def _to_number(token: str) -> float:
    token = token.lower()
    if token in _WORD_NUMBERS:
        return float(_WORD_NUMBERS[token])
    return float(token.replace(",", "."))


@dataclass
class Span:
    value: float
    start: int
    end: int


@dataclass
class PenaltyTerms:
    daily_rates: list[Span] = field(default_factory=list)
    caps: list[Span] = field(default_factory=list)
    fines: list[Span] = field(default_factory=list)
    capped_in_words: bool = False

    @property
    def max_daily_rate(self) -> Span | None:
        return max(self.daily_rates, key=lambda s: s.value, default=None)

    @property
    def max_fine(self) -> Span | None:
        return max(self.fines, key=lambda s: s.value, default=None)

    @property
    def capped(self) -> bool:
        return bool(self.caps) or self.capped_in_words


def penalty_terms(text: str) -> PenaltyTerms:
    """Проценты в пункте о неустойке: ставка в день, потолок, разовый штраф."""
    terms = PenaltyTerms()
    if not lx.PENALTY_WORDS.search(text):
        return terms
    per_day = lx.PER_DAY.search(text) is not None
    for m in lx.PERCENT.finditer(text):
        value = _to_number(m.group("num"))
        span = Span(value, m.start(), m.end())
        before, after = text[max(0, m.start() - 60) : m.start()], text[m.end() : m.end() + 25]
        if lx.CAP_BEFORE.search(before) or lx.CAP_AFTER.search(after):
            terms.caps.append(span)
        elif per_day and _near_per_day(text, m.start(), m.end()):
            terms.daily_rates.append(span)
        else:
            terms.fines.append(span)
    terms.capped_in_words = bool(
        re.search(r"(?:не\s+более|не\s+свыше|не\s+может\s+превышать)[^.;]{0,40}сумм", text, re.I)
    )
    return terms


def _near_per_day(text: str, start: int, end: int, window: int = 120) -> bool:
    around = text[max(0, start - window) : end + window]
    return lx.PER_DAY.search(around) is not None


def durations_days(text: str) -> list[Span]:
    """Сроки в днях: «30 (тридцать) календарных дней», «за три месяца», «24 часа»."""
    out = []
    for m in _DAYS_RE.finditer(text):
        n = _to_number(m.group("n"))
        unit = m.group("unit").lower()
        days = n / 24 if unit.startswith(("час", "сағат")) else n
        out.append(Span(days, m.start(), m.end()))
    for m in _MONTHS_RE.finditer(text):
        if not m.group("n") and m.group("unit").lower() not in ("месяц", "ай"):
            continue  # «следующего за месяцем уведомления» — не срок
        n = _to_number(m.group("n")) if m.group("n") else 1.0
        out.append(Span(30 * n, m.start(), m.end()))
    return sorted(out, key=lambda s: s.start)


def months_amount(text: str) -> float | None:
    """Плата в месяцах: «двухмесячной арендной платы», «плату за 6 месяцев»."""
    kk = _KK_MONTH_ADJ_RE.search(text)
    if kk:
        return _to_number(kk.group("n"))
    m = _MONTH_ADJ_RE.search(text)
    if m:
        prefix = text[max(0, m.start() - 10) : m.start()].lower()
        base = _MONTH_ADJ[m.group("adj").lower()]
        if base == 1 and re.search(r"(?:двух|трех|трёх|шести)\s*$", prefix):
            return None
        return float(base)
    spans = [s for s in durations_days(text) if s.value >= 30 and s.value % 30 == 0]
    return spans[0].value / 30 if spans else None


_TERM_PREFIX = re.compile(
    r"(?:за|не\s+(?:позднее|менее)\s+(?:чем\s+)?за|в\s+течение|не\s+позднее|по\s+истечении"
    r"|через|кемінде|ішінде)\s*$",
    re.IGNORECASE,
)


def notice_days(text: str) -> list[Span]:
    """Сроки предупреждения: «за 10 дней», «не позднее чем за месяц», «30 күн бұрын»."""
    out = []
    for span in durations_days(text):
        before = text[max(0, span.start - 30) : span.start]
        after = text[span.end : span.end + 12]
        if re.search(r"(?:\bза|чем\s+за)\s*$", before, re.I) or re.match(r"\s*бұрын", after):
            out.append(span)
    return out


def term_days(text: str) -> list[Span]:
    """Сроки исполнения: «в течение 90 дней», «по истечении 120 дней», «не позднее 75 дней»."""
    return [
        s
        for s in durations_days(text)
        if _TERM_PREFIX.search(text[max(0, s.start - 30) : s.start])
        or re.match(r"\s*ішінде", text[s.end : s.end + 10])
    ]
