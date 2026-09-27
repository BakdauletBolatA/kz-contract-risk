"""«В норме такое условие звучит так, а у вас — так, и вот разница».

Для каждой находки:

1. ближайшие **нейтральные** эталоны той же категории и типа договора —
   это «как обычно пишут»;
2. один эталон в пользу **контрагента** — «граница рынка»: если даже
   выгодный контрагенту вариант мягче вашего, это сильный аргумент
   в переговорах;
3. разница числовых признаков словами: ставка, потолок, срок
   предупреждения, срок оплаты. Разница считается детерминированно,
   теми же функциями, что и в правилах, — никакой генерации.

Сравнение не влияет на то, найдена ли находка, и в метриках detection не
участвует: это объяснение, а не классификатор.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from contract_risk.corpus.manifest import ReferenceClause
from contract_risk.retrieval.index import ReferenceIndex
from contract_risk.retrieval.store import SearchHit
from contract_risk.rules import lexicon as lx
from contract_risk.rules.features import notice_days, penalty_terms, term_days
from contract_risk.schemas import (
    ContractDocument,
    ContractType,
    Finding,
    Language,
    MarketComparison,
    PartyRole,
    RiskCategory,
    contract_type_of,
    counterparty,
)
from contract_risk.taxonomy import CATEGORY_DESCRIPTIONS

_AGREEMENT = re.compile(
    r"(?:по\s+(?:письменному\s+)?соглашению|дополнительн\w+\s+соглашени|келісім)", re.I
)
_UNILATERAL = re.compile(
    r"(?:в\s+одностороннем\s+порядке|без\s+согласовани|самостоятельно|біржақты)", re.I
)
_NO_NOTICE = re.compile(
    r"(?:без\s+(?:\w+\s+){0,2}(?:уведомления|предупреждения)|в\s+любое\s+время)", re.I
)


def _fmt(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _penalty_diff(user: str, ref: str) -> list[str]:
    u, r = penalty_terms(user), penalty_terms(ref)
    out = []
    if u.max_daily_rate and r.max_daily_rate and u.max_daily_rate.value != r.max_daily_rate.value:
        out.append(
            f"Пеня: у вас {_fmt(u.max_daily_rate.value)}% в день, "
            f"в эталоне {_fmt(r.max_daily_rate.value)}%."
        )
    if r.capped and not u.capped:
        cap = max(r.caps, key=lambda s: s.value, default=None)
        out.append(
            "Потолок неустойки: у вас нет, в эталоне "
            + (f"{_fmt(cap.value)}%." if cap else "есть.")
        )
    if u.max_fine and not r.max_fine:
        out.append(f"Разовый штраф: у вас {_fmt(u.max_fine.value)}%, в эталоне штрафа нет.")
    return out


def _notice_diff(user: str, ref: str) -> list[str]:
    u, r = notice_days(user), notice_days(ref)
    out = []
    if _NO_NOTICE.search(user) and r:
        out.append(f"Предупреждение: у вас не требуется, в эталоне — за {int(r[0].value)} дней.")
    elif u and r and u[0].value != r[0].value:
        out.append(
            f"Срок предупреждения: у вас {int(u[0].value)} дн., в эталоне {int(r[0].value)} дн."
        )
    if lx.MUTUAL_RU.search(ref) and not lx.MUTUAL_RU.search(user):
        out.append("В эталоне право отказа есть у обеих сторон, у вас — только у одной.")
    return out


def _payment_diff(user: str, ref: str) -> list[str]:
    u, r = term_days(user), term_days(ref)
    if u and r and max(s.value for s in u) != max(s.value for s in r):
        return [
            f"Срок оплаты: у вас {int(max(s.value for s in u))} дн., "
            f"в эталоне {int(max(s.value for s in r))} дн."
        ]
    if "100" in user and "30%" in ref:
        return ["Предоплата: у вас 100%, в эталоне 30% с оплатой остатка после исполнения."]
    return []


def _change_diff(user: str, ref: str) -> list[str]:
    if _AGREEMENT.search(ref) and not _AGREEMENT.search(user):
        return [
            "В эталоне цена меняется только по соглашению сторон, у вас — решением одной стороны."
        ]
    return []


def _liability_diff(user: str, ref: str) -> list[str]:
    out = []
    if lx.LOST_PROFIT.search(user) and lx.LOST_PROFIT_EXCLUDED.search(ref):
        out.append("В эталоне упущенная выгода не возмещается, у вас — возмещается.")
    if lx.OVER_PENALTY.search(user) and "засчитывается" in ref:
        out.append(
            "В эталоне неустойка засчитывается в убытки, у вас — убытки взыскиваются сверх неё."
        )
    if lx.NOT_LIABLE_RU.search(user) and not lx.NOT_LIABLE_RU.search(ref):
        out.append(
            "В эталоне ответственность несут обе стороны, у вас одна сторона её с себя снимает."
        )
    return out


def _acceptance_diff(user: str, ref: str) -> list[str]:
    u, r = term_days(user), term_days(ref)
    if u and r and min(s.value for s in u) < min(s.value for s in r):
        return [
            f"Срок на проверку и претензии: у вас {_fmt(min(s.value for s in u))} дн., "
            f"в эталоне {_fmt(min(s.value for s in r))} дн."
        ]
    return []


_DIFFS: dict[RiskCategory, Callable[[str, str], list[str]]] = {
    RiskCategory.PENALTY: _penalty_diff,
    RiskCategory.TERMINATION: _notice_diff,
    RiskCategory.AUTO_RENEWAL: _notice_diff,
    RiskCategory.PAYMENT: _payment_diff,
    RiskCategory.UNILATERAL_CHANGE: _change_diff,
    RiskCategory.LIABILITY: _liability_diff,
    RiskCategory.ACCEPTANCE: _acceptance_diff,
}


def differences(category: RiskCategory, user_text: str, ref_text: str) -> list[str]:
    fn = _DIFFS.get(category)
    return fn(user_text, ref_text) if fn else []


class MarketComparator:
    def __init__(self, index: ReferenceIndex, k_neutral: int = 2) -> None:
        self.index = index
        self.k_neutral = k_neutral

    def references(
        self,
        text: str,
        category: RiskCategory,
        contract_type: ContractType,
        user: PartyRole,
        lang: Language = Language.RU,
    ) -> list[SearchHit]:
        common = {"contract_type": contract_type.value, "category": category.value}
        hits = self.index.similar(
            text, **common, lang=lang.value, favours="neutral", k=self.k_neutral
        )
        hits += self.index.similar(
            text, **common, lang=lang.value, favours=counterparty(user).value, k=1
        )
        return hits

    def compare(
        self,
        text: str,
        category: RiskCategory,
        contract_type: ContractType,
        user: PartyRole,
        lang: Language = Language.RU,
    ) -> list[MarketComparison]:
        return [
            _comparison(hit, differences(category, text, hit.clause.text))
            for hit in self.references(text, category, contract_type, user, lang)
        ]

    def attach(self, doc: ContractDocument, findings: list[Finding], user: PartyRole) -> None:
        ctype = contract_type_of(user)
        for f in findings:
            if f.comparison:
                continue
            clause = doc.clause(f.clause_id) if f.clause_id else None
            if clause is not None:
                f.comparison = self.compare(clause.text, f.category, ctype, user, clause.lang)
            else:
                query = CATEGORY_DESCRIPTIONS[f.category]
                hits = self.index.similar(
                    query,
                    contract_type=ctype.value,
                    category=f.category.value,
                    favours="neutral",
                    k=1,
                )
                f.comparison = [_comparison(h, []) for h in hits]


def _comparison(hit: SearchHit, diffs: list[str]) -> MarketComparison:
    ref: ReferenceClause = hit.clause
    return MarketComparison(
        reference_id=ref.id,
        reference_text=ref.text,
        similarity=round(hit.score, 4),
        favours=ref.favours,
        source_id=ref.source_id,
        differences=diffs,
    )
