"""Аудит корпуса: баланс сторон, покрытие категорий, утечка в eval.

Правила — docs/CORPUS_POLICY.md. Каждая функция возвращает список проблем
человеческим языком; пустой список — корпус годен.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from contract_risk.corpus.manifest import ReferenceClause
from contract_risk.schemas import ROLES_BY_TYPE, ContractType, RiskCategory

# Категории, для которых у типа договора обязан быть нейтральный эталон.
# В аренде оплата и приёмка не размечаются руководством — и не требуются.
REQUIRED_CATEGORIES: dict[ContractType, set[RiskCategory]] = {
    ContractType.LEASE: set(RiskCategory) - {RiskCategory.PAYMENT, RiskCategory.ACCEPTANCE},
    ContractType.SUPPLY: set(RiskCategory),
    ContractType.WORKS: set(RiskCategory),
}
MIN_NEUTRAL_SHARE = 0.5
MAX_SIDE_GAP = 1
LEAKAGE_JACCARD = 0.8


@dataclass
class BalanceRow:
    contract_type: str
    category: str
    neutral: int
    side_a: int
    side_b: int

    @property
    def total(self) -> int:
        return self.neutral + self.side_a + self.side_b


def balance_table(clauses: Sequence[ReferenceClause]) -> list[BalanceRow]:
    counts: dict[tuple[ContractType, RiskCategory], dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for c in clauses:
        counts[(c.contract_type, c.category)][c.favours] += 1
    rows = []
    for (ctype, cat), by_side in sorted(counts.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        a, b = ROLES_BY_TYPE[ctype]
        rows.append(BalanceRow(ctype.value, cat.value, by_side["neutral"], by_side[a], by_side[b]))
    return rows


def audit_balance(clauses: Sequence[ReferenceClause]) -> list[str]:
    problems = []
    for row in balance_table(clauses):
        where = f"{row.contract_type}/{row.category}"
        if row.neutral / row.total < MIN_NEUTRAL_SHARE:
            problems.append(f"{where}: нейтральных {row.neutral} из {row.total} — меньше половины")
        if abs(row.side_a - row.side_b) > MAX_SIDE_GAP:
            problems.append(
                f"{where}: перекос сторон {row.side_a} против {row.side_b} — корпус "
                f"будет считать нормой условия одной стороны"
            )
    return problems


def audit_coverage(clauses: Sequence[ReferenceClause]) -> list[str]:
    have = {(c.contract_type, c.category) for c in clauses if c.favours == "neutral"}
    return [
        f"{ctype.value}/{cat.value}: нет ни одной нейтральной формулировки"
        for ctype, cats in REQUIRED_CATEGORIES.items()
        for cat in sorted(cats)
        if (ctype, cat) not in have
    ]


def _shingles(text: str, n: int = 5) -> set[str]:
    t = " ".join(text.lower().split())
    return {t[i : i + n] for i in range(max(len(t) - n + 1, 1))}


def jaccard(a: str, b: str) -> float:
    sa, sb = _shingles(a), _shingles(b)
    return len(sa & sb) / len(sa | sb) if sa | sb else 0.0


def audit_leakage(
    clauses: Sequence[ReferenceClause],
    eval_texts: Iterable[tuple[str, str]],
    threshold: float = LEAKAGE_JACCARD,
) -> list[str]:
    """Эталон, почти дословно совпадающий с пунктом eval, завышает метрики RAG."""
    eval_items = [(where, text, _shingles(text)) for where, text in eval_texts]
    problems = []
    for c in clauses:
        sc = _shingles(c.text)
        for where, _, se in eval_items:
            union = sc | se
            if union and len(sc & se) / len(union) >= threshold:
                problems.append(f"{c.id}: почти совпадает с пунктом {where}")
                break
    return problems
