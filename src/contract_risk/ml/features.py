"""Представление пункта для ML: роли относительно пользователя + токены-признаки.

«Арендатор уплачивает Арендодателю пеню 1%» для арендатора превращается в
«USER_nom уплачивает CP_dat пеню 1% RATE_HIGH NOCAP», а для арендодателя —
в «CP_nom уплачивает USER_dat …». Линейная модель над n-граммами этого
текста видит направление обязательства, не зная ничего о падежах, и одни и
те же веса работают для аренды, поставки и подряда.
"""

from __future__ import annotations

from contract_risk.rules import lexicon as lx
from contract_risk.rules.features import notice_days, penalty_terms, term_days
from contract_risk.rules.parties import PartyView
from contract_risk.schemas import ContractType, Language, PartyRole

PLACEHOLDERS = {
    "USER": "вы",
    "CP": "контрагент",
    "BOTH": "обе стороны",
}


def relative_text(text: str, contract_type: ContractType, lang: Language, user: PartyRole) -> str:
    view = PartyView.of(text, contract_type, lang)
    parts, last = [], 0
    for m in sorted(view.mentions, key=lambda x: x.start):
        parts.append(text[last : m.start])
        parts.append(f" {'USER' if m.role == user else 'CP'}_{m.case} ")
        last = m.end
    parts.append(text[last:])
    rel = "".join(parts)
    pattern = lx.MUTUAL_KK if lang == Language.KK else lx.MUTUAL_RU
    rel = pattern.sub(" BOTH ", rel)
    return f"{rel} {' '.join(feature_tokens(text))}".strip()


def feature_tokens(text: str) -> list[str]:
    tokens = []
    terms = penalty_terms(text)
    rate = terms.max_daily_rate
    if rate is not None:
        tokens.append(
            "RATE_HIGH" if rate.value >= 0.5 else "RATE_MED" if rate.value > 0.1 else "RATE_LOW"
        )
        tokens.append("CAPPED" if terms.capped else "NOCAP")
    fine = terms.max_fine
    if fine is not None:
        tokens.append(
            "FINE_HIGH" if fine.value >= 30 else "FINE_MED" if fine.value > 10 else "FINE_LOW"
        )
    notices = notice_days(text)
    if notices:
        shortest, longest = min(s.value for s in notices), max(s.value for s in notices)
        tokens.append("NOTICE_SHORT" if shortest < 30 else "NOTICE_OK")
        if longest >= 60:
            tokens.append("NOTICE_LONG")
    terms_days = term_days(text)
    if terms_days:
        longest = max(s.value for s in terms_days)
        shortest = min(s.value for s in terms_days)
        if longest >= 120:
            tokens.append("TERM_VERYLONG")
        elif longest >= 60:
            tokens.append("TERM_LONG")
        if shortest <= 3:
            tokens.append("TERM_TINY")
    if lx.FORCE_MAJEURE.search(text):
        tokens.append("FORCE_MAJEURE")
    return tokens


FEATURE_WORDS = {
    "RATE_HIGH": "пеня от 0,5% в день",
    "RATE_MED": "пеня 0,1–0,5% в день",
    "RATE_LOW": "пеня до 0,1% в день",
    "NOCAP": "без потолка неустойки",
    "CAPPED": "с потолком неустойки",
    "FINE_HIGH": "штраф от 30%",
    "FINE_MED": "штраф 10–30%",
    "FINE_LOW": "штраф до 10%",
    "NOTICE_SHORT": "предупреждение меньше месяца",
    "NOTICE_OK": "предупреждение от месяца",
    "NOTICE_LONG": "уведомление за 60+ дней",
    "TERM_VERYLONG": "срок от 120 дней",
    "TERM_LONG": "срок 60–119 дней",
    "TERM_TINY": "срок до 3 дней",
    "FORCE_MAJEURE": "форс-мажор",
}


def humanize(feature: str) -> str:
    """«cp_nom вправе» → «контрагент вправе» — для объяснения в отчёте."""
    words = []
    for w in feature.split():
        upper = w.upper()
        head = upper.split("_")[0]
        if upper in FEATURE_WORDS:
            words.append(FEATURE_WORDS[upper])
        elif head in PLACEHOLDERS and (upper == head or "_" in upper):
            words.append(PLACEHOLDERS[head])
        else:
            words.append(w)
    return " ".join(words)
