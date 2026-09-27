"""Проверки целостности eval-датасета.

Запускаются тестами и командой `kzcr dataset check`. Датасет, который не
проходит эти проверки, не годится для замера: метрика на нём измеряет
ошибку разметки, а не систему.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from contract_risk.evaluation.dataset import EvalDoc
from contract_risk.schemas import ContractDocument

Parser = Callable[[str, str], ContractDocument]


def check_docs(docs: Sequence[EvalDoc], parser: Parser) -> list[str]:
    """Каждая эталонная находка указывает на существующий анализируемый пункт."""
    problems: list[str] = []
    for doc in docs:
        parsed = parser(doc.text, doc.doc_id)
        analysable = {c.id for c in parsed.analysable_clauses}
        seen: set[tuple[str | None, str]] = set()
        for g in doc.findings:
            key = (g.clause, g.category.value)
            if key in seen:
                problems.append(f"{doc.doc_id}: повтор находки {key}")
            seen.add(key)
            if g.clause is not None and g.clause not in analysable:
                problems.append(
                    f"{doc.doc_id}: пункт {g.clause} из разметки не найден сегментатором"
                )
    return problems


def trap_texts(docs: Sequence[EvalDoc], parser: Parser) -> dict[str, str]:
    """Тексты размеченных пунктов: нормализованный текст → doc_id."""
    out: dict[str, str] = {}
    for doc in docs:
        parsed = parser(doc.text, doc.doc_id)
        for g in doc.clause_findings:
            clause = parsed.clause(g.clause)
            if clause is not None:
                out[" ".join(clause.text.split()).lower()] = doc.doc_id
    return out


def check_split_leakage(
    dev: Sequence[EvalDoc], test: Sequence[EvalDoc], parser: Parser
) -> list[str]:
    """Ни одна формулировка ловушки из test не встречается в dev дословно."""
    dev_texts = trap_texts(dev, parser)
    return [
        f"{doc_id}: формулировка ловушки из test есть в dev ({dev_texts[text]})"
        for text, doc_id in trap_texts(test, parser).items()
        if text in dev_texts
    ]
