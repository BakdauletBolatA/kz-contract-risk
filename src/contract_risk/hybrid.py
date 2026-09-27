"""Гибрид: правила → (маршрутизация ML) → LLM для того, что правила не покрыли.

Порядок и приоритеты:

1. **Правила** — всегда и первыми: детерминированы, объяснимы, на всех
   срезах не дали ни одной ложной тревоги. Их находка на пункт окончательна.
2. **ML** — дешёвый маршрутизатор: из пунктов, где правила молчат, в LLM
   уходят только те, чья вероятность риска не ниже `route_threshold`
   (выбран на dev так, чтобы по пессимистичной оценке терять ≤ 5% рисковых).
   Без LLM ML может выдать находку сам, но только увереннее любого
   «молчащего» пункта dev (`emit_threshold`) — на текущих данных это
   практически никогда, и это осознанно: ML на синтетике не обобщается
   на новые формулировки (EVALUATION.md).
3. **LLM** — оценивает маршрутизированные пункты; находка принимается только
   с дословной цитатой из пункта.
"""

from __future__ import annotations

from typing import Any

from contract_risk.llm.classifier import LLMDetector
from contract_risk.ml.model import MLDetector
from contract_risk.rules.engine import RulesDetector, dedupe
from contract_risk.schemas import ContractDocument, Finding, PartyRole


class HybridDetector:
    def __init__(
        self,
        rules: RulesDetector,
        ml: MLDetector | None = None,
        llm: LLMDetector | None = None,
    ) -> None:
        self.rules = rules
        self.ml = ml
        self.llm = llm
        self.name = "hybrid_llm" if llm is not None else "hybrid"
        self.silent_clauses = 0
        self.routed_clauses = 0

    def detect(self, doc: ContractDocument, party_role: PartyRole) -> list[Finding]:
        findings = self.rules.detect(doc, party_role)
        flagged = {f.clause_id for f in findings if f.clause_id is not None}
        silent = [c for c in doc.analysable_clauses if c.id not in flagged]
        scores = self.ml.scores(doc, party_role) if self.ml is not None else {}
        self.silent_clauses += len(silent)

        if self.llm is not None:
            routed = [
                c
                for c in silent
                if self.ml is None or scores[c.id][0] >= self.ml.model.route_threshold
            ]
            self.routed_clauses += len(routed)
            findings += self.llm.assess_clauses(doc, routed, party_role)
        elif self.ml is not None:
            findings += [
                f
                for f in self.ml.detect(doc, party_role)
                if f.clause_id not in flagged and f.confidence >= self.ml.model.emit_threshold
            ]
        return dedupe(findings)

    def config(self) -> dict[str, Any]:
        mode = "rules" + ("+ml" if self.ml else "") + ("+llm" if self.llm else "")
        return {
            "mode": mode,
            "rules": self.rules.config(),
            "ml": self.ml.config() if self.ml else None,
            "ml_emit_threshold": self.ml.model.emit_threshold if self.ml else None,
            "ml_route_threshold": self.ml.model.route_threshold if self.ml else None,
            "llm": self.llm.config() if self.llm else None,
            "routing": {"silent": self.silent_clauses, "routed": self.routed_clauses},
        }
