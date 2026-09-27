"""Прогон правил по договору и документные проверки.

Пункт → все применимые правила → находки против стороны пользователя.
Документные проверки смотрят на договор целиком: нет пункта о форс-мажоре;
ответственность есть только у пользователя.
"""

from __future__ import annotations

import re
from typing import Any

from contract_risk.rules import lexicon as lx
from contract_risk.rules.catalog import (
    _TERMINATION_CONTEXT,
    RULES,
    Hit,
    Rule,
    RuleContext,
)
from contract_risk.rules.parties import PartyView
from contract_risk.schemas import (
    Clause,
    ContractDocument,
    Evidence,
    Finding,
    PartyRole,
    RiskCategory,
    RiskLevel,
    contract_type_of,
    counterparty,
)
from contract_risk.taxonomy import LEGAL_REFS

RULES_VERSION = "1.0"
MIN_CLAUSES_FOR_DOCUMENT_CHECKS = 5

_DAMAGES = re.compile(
    r"(?:возмеща|возмещени|убытк|ущерб|ответственност|отвеча|залал|жауапты|жауап\s+береді)",
    re.IGNORECASE,
)


def _finding(hit: Hit, clause: Clause) -> Finding:
    evidence = [
        Evidence(quote=clause.text[s:e], start=s, end=e)
        for s, e in sorted(set(hit.spans))
        if 0 <= s < e <= len(clause.text)
    ]
    return Finding(
        clause_id=clause.id,
        category=hit.category,
        level=hit.level,
        source="rule",
        rule_id=hit.rule_id,
        title=hit.title,
        explanation=hit.explanation,
        evidence=evidence,
        safer_wording=hit.safer_wording,
        legal_basis=hit.legal_basis,
        confidence=0.95,
        details={k: v for k, v in hit.details.items() if v is not None},
    )


def dedupe(findings: list[Finding]) -> list[Finding]:
    """Одна находка на (пункт, категория): остаётся самая высокая."""
    best: dict[tuple[str | None, RiskCategory], Finding] = {}
    for f in findings:
        key = (f.clause_id, f.category)
        if key not in best or f.level.rank > best[key].level.rank:
            best[key] = f
    return list(best.values())


class RuleEngine:
    def __init__(self, rules: list[Rule] | None = None) -> None:
        self.rules = rules if rules is not None else RULES

    def clause_hits(self, clause: Clause, user: PartyRole) -> list[Hit]:
        ctype = contract_type_of(user)
        ctx = RuleContext(clause, ctype, user)
        hits = []
        for rule in self.rules:
            if ctype in rule.contract_types:
                hits.extend(rule.fn(ctx))
        return hits

    def analyze(self, doc: ContractDocument, user: PartyRole) -> list[Finding]:
        findings = [
            _finding(hit, clause)
            for clause in doc.analysable_clauses
            for hit in self.clause_hits(clause, user)
            if user in hit.against
        ]
        findings.extend(document_findings(doc, user))
        return dedupe(findings)


def document_findings(doc: ContractDocument, user: PartyRole) -> list[Finding]:
    clauses = doc.analysable_clauses
    if len(clauses) < MIN_CLAUSES_FOR_DOCUMENT_CHECKS:
        return []
    out = []
    has_fm = any(
        lx.FORCE_MAJEURE.search(c.text)
        or (c.section_title and lx.FORCE_MAJEURE.search(c.section_title))
        for c in doc.clauses
    )
    if not has_fm:
        out.append(
            Finding(
                clause_id=None,
                category=RiskCategory.FORCE_MAJEURE,
                level=RiskLevel.MEDIUM,
                source="document_rule",
                rule_id="document.force_majeure_missing",
                title="В договоре нет пункта о форс-мажоре",
                explanation=(
                    "Закон и без этого пункта освобождает от ответственности при непреодолимой "
                    "силе, но в договоре не определено, как и в какой срок уведомлять, какими "
                    "документами подтверждать и можно ли выйти из договора, если обстоятельства "
                    "затянутся."
                ),
                safer_wording=(
                    "Стороны освобождаются от ответственности за неисполнение обязательств, "
                    "вызванное обстоятельствами непреодолимой силы, при условии уведомления "
                    "другой Стороны в течение 5 рабочих дней. Если такие обстоятельства длятся "
                    "более 60 дней, каждая Сторона вправе отказаться от Договора."
                ),
                legal_basis=LEGAL_REFS["force_majeure"],
                confidence=0.9,
            )
        )

    user_burdened, other_burdened, evidence_ids = False, False, []
    other = counterparty(user)
    for c in clauses:
        text = c.text
        if lx.FORCE_MAJEURE.search(text) or _TERMINATION_CONTEXT.search(text):
            continue
        if lx.NOT_LIABLE_RU.search(text) or lx.NOT_LIABLE_KK.search(text):
            continue
        if not (lx.PENALTY_WORDS.search(text) or _DAMAGES.search(text)):
            continue
        view = PartyView.of(text, contract_type_of(user), c.lang)
        payers = view.payers()
        if payers:
            if user in payers:
                user_burdened = True
                evidence_ids.append(c.id)
            other_burdened |= other in payers
        elif view.mutual:
            user_burdened = other_burdened = True
    if user_burdened and not other_burdened:
        out.append(
            Finding(
                clause_id=None,
                category=RiskCategory.LIABILITY,
                level=RiskLevel.MEDIUM,
                source="document_rule",
                rule_id="document.liability_one_sided",
                title="Ответственность в договоре только у вас",
                explanation=(
                    "За нарушения платите только вы: для контрагента в договоре нет ни "
                    "неустойки, ни общей ответственности сторон. Если он сорвёт сроки, "
                    "компенсацию придётся доказывать и взыскивать самостоятельно."
                ),
                safer_wording=(
                    "За нарушение сроков исполнения обязательств виновная Сторона уплачивает "
                    "другой Стороне пеню 0,1% за каждый день просрочки, но не более 10%."
                ),
                confidence=0.8,
                details={"user_clauses": ", ".join(evidence_ids)},
            )
        )
    return out


class RulesDetector:
    name = "rules"

    def __init__(self, engine: RuleEngine | None = None) -> None:
        self.engine = engine or RuleEngine()

    def detect(self, doc: ContractDocument, party_role: PartyRole) -> list[Finding]:
        return self.engine.analyze(doc, party_role)

    def config(self) -> dict[str, Any]:
        return {"rules_version": RULES_VERSION, "rules": [r.id for r in self.engine.rules]}
