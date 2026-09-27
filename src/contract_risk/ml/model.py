"""Три логистические регрессии над относительным текстом пункта.

- **риск** — вероятность того, что пункт рискован для стороны пользователя;
- **категория** — к какой из девяти категорий относится риск;
- **уровень** — low / medium / high.

Почему логрегрессия, а не fine-tuned трансформер: размеченных пунктов
~200, и все они с dev-среза. Трансформер на таком объёме запомнит шаблоны,
а веса логрегрессии можно показать пользователю («сильнее всего повлияла
фраза „контрагент вправе в одностороннем“»). Fine-tuning — следующий шаг,
когда появятся размеченные публичные договоры (EVALUATION.md).

Обучение — только на dev. Out-of-fold считается двумя способами, и
обе цифры сохраняются рядом с моделью:

- GroupKFold **по договору** — оптимистичная оценка: синтетические договоры
  собраны из одних и тех же вариантов пунктов, и вариант попадает и в
  обучение, и в валидацию (F1 ≈ 0,93 при F1 ≈ 0,56 на test);
- GroupKFold **по формулировке** (текст без чисел) — пессимистичная:
  отложенный вариант часто уносит с собой весь тип ловушки.

Настоящее качество на новых формулировках — между ними. Порог выбирается
по первой оценке с требованием precision ≥ 0,9: в гибриде ML работает
только там, где правила молчат, и цена его ложной тревоги — доверие
к отчёту.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import FeatureUnion, Pipeline

from contract_risk.evaluation.dataset import EvalDoc
from contract_risk.ml.features import humanize, relative_text
from contract_risk.schemas import (
    ContractDocument,
    Evidence,
    Finding,
    PartyRole,
    RiskCategory,
    RiskLevel,
    contract_type_of,
)

# Версия меняется при любой правке признаков: сохранённая модель старой версии
# не загружается, а переобучается (load_or_train).
MODEL_VERSION = "1.1"
MIN_PRECISION = 0.9
ROUTE_MISS_RATE = 0.05
Parser = Callable[[str, str], ContractDocument]


def _vectorizer() -> FeatureUnion:
    return FeatureUnion(
        [
            (
                "words",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 3),
                    token_pattern=r"(?u)\b[\w%]+\b",
                    sublinear_tf=True,
                    min_df=2,
                ),
            ),
            (
                "chars",
                TfidfVectorizer(
                    analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=3
                ),
            ),
        ]
    )


def _classifier(balanced: bool = True) -> Pipeline:
    return Pipeline(
        [
            ("tfidf", _vectorizer()),
            (
                "lr",
                LogisticRegression(
                    C=4.0, max_iter=3000, class_weight="balanced" if balanced else None
                ),
            ),
        ]
    )


def training_frame(docs: Sequence[EvalDoc], parser: Parser) -> pd.DataFrame:
    """Все анализируемые пункты dev-среза с разметкой относительно стороны договора."""
    rows = []
    for doc in docs:
        parsed = parser(doc.text, doc.doc_id)
        gold = {g.clause: g for g in doc.clause_findings}
        for clause in parsed.analysable_clauses:
            g = gold.get(clause.id)
            rows.append(
                {
                    "doc_id": doc.doc_id,
                    "clause_id": clause.id,
                    "text": relative_text(
                        clause.text, doc.contract_type, clause.lang, doc.party_role
                    ),
                    "risky": int(g is not None),
                    "category": g.category.value if g else None,
                    "level": g.level.value if g else None,
                }
            )
    return pd.DataFrame(rows)


def wording_signature(text: str) -> str:
    """Формулировка без чисел: варианты «пеня 0,5%» и «пеня 1%» — одна группа."""
    return re.sub(r"\d+(?:[.,]\d+)?", "#", " ".join(text.lower().split()))


def _rule_silent_mask(docs: Sequence[EvalDoc], frame: pd.DataFrame, parser: Parser) -> np.ndarray:
    """Пункты dev, на которых правила ничего не нашли."""
    from contract_risk.rules.engine import RuleEngine

    engine = RuleEngine()
    flagged: set[tuple[str, str]] = set()
    for doc in docs:
        parsed = parser(doc.text, doc.doc_id)
        for f in engine.analyze(parsed, doc.party_role):
            if f.clause_id is not None:
                flagged.add((doc.doc_id, f.clause_id))
    return np.array(
        [(d, c) not in flagged for d, c in zip(frame["doc_id"], frame["clause_id"], strict=True)]
    )


def _oof(frame: pd.DataFrame, y: np.ndarray, groups: np.ndarray, folds: int) -> np.ndarray:
    oof = np.zeros(len(frame))
    for train_idx, val_idx in GroupKFold(n_splits=folds).split(frame, y, groups):
        model = _classifier().fit(frame["text"].iloc[train_idx], y[train_idx])
        oof[val_idx] = model.predict_proba(frame["text"].iloc[val_idx])[:, 1]
    return oof


def _metrics_at(y: np.ndarray, proba: np.ndarray, threshold: float) -> dict[str, float]:
    pred = proba >= threshold
    tp = int((pred & (y == 1)).sum())
    fp = int((pred & (y == 0)).sum())
    fn = int((~pred & (y == 1)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"f1": round(f1, 4), "precision": round(precision, 4), "recall": round(recall, 4)}


def choose_threshold(y: np.ndarray, proba: np.ndarray, min_precision: float = MIN_PRECISION):
    """Порог с максимальным F1 среди порогов, где precision ≥ min_precision."""
    best = (0.5, -1.0, 0.0, 0.0)
    for t in np.unique(np.round(proba, 3)):
        pred = proba >= t
        tp = int((pred & (y == 1)).sum())
        fp = int((pred & (y == 0)).sum())
        fn = int((~pred & (y == 1)).sum())
        if tp == 0:
            continue
        precision, recall = tp / (tp + fp), tp / (tp + fn)
        f1 = 2 * precision * recall / (precision + recall)
        if precision >= min_precision and f1 > best[1]:
            best = (float(t), f1, precision, recall)
    return best


@dataclass
class ClauseRiskModel:
    risk: Pipeline
    category: Pipeline
    level: Pipeline
    threshold: float
    trained_on: str
    oof: dict[str, float] = field(default_factory=dict)
    # В гибриде: выдать находку сверх правил — только увереннее, чем на любом
    # пункте dev, где правила молчат; отправить в LLM — если вероятность не
    # ниже порога, который по пессимистичной оценке теряет ≤ 5% рисковых.
    emit_threshold: float = 1.0
    route_threshold: float = 0.0

    @classmethod
    def train(cls, docs: Sequence[EvalDoc], parser: Parser, folds: int = 5) -> ClauseRiskModel:
        frame = training_frame(docs, parser)
        y = frame["risky"].to_numpy()
        by_doc = _oof(frame, y, frame["doc_id"].to_numpy(), folds)
        by_wording = _oof(frame, y, frame["text"].map(wording_signature).to_numpy(), folds)
        threshold, f1, precision, recall = choose_threshold(y, by_doc)
        pessimistic = _metrics_at(y, by_wording, threshold)

        silent = _rule_silent_mask(docs, frame, parser)
        silent_negatives = by_doc[silent & (y == 0)]
        emit = float(min(0.99, silent_negatives.max() + 1e-3)) if silent_negatives.size else 0.99
        route = float(np.quantile(by_wording[y == 1], ROUTE_MISS_RATE)) if y.sum() else 0.0

        risky = frame[frame["risky"] == 1]
        return cls(
            risk=_classifier().fit(frame["text"], y),
            category=_classifier(balanced=False).fit(risky["text"], risky["category"]),
            level=_classifier(balanced=False).fit(risky["text"], risky["level"]),
            threshold=threshold,
            trained_on=_docs_hash(docs),
            emit_threshold=round(emit, 4),
            route_threshold=round(route, 4),
            oof={
                "by_doc_f1": round(f1, 4),
                "by_doc_precision": round(precision, 4),
                "by_doc_recall": round(recall, 4),
                "by_wording_f1": pessimistic["f1"],
                "by_wording_precision": pessimistic["precision"],
                "by_wording_recall": pessimistic["recall"],
                "n_clauses": len(frame),
                "n_risky": int(y.sum()),
            },
        )

    def predict(self, texts: list[str]) -> list[tuple[float, str, str]]:
        if not texts:
            return []
        proba = self.risk.predict_proba(texts)[:, 1]
        categories = self.category.predict(texts)
        levels = self.level.predict(texts)
        return list(zip(proba.tolist(), categories.tolist(), levels.tolist(), strict=True))

    def top_features(self, text: str, n: int = 4) -> list[str]:
        """N-граммы с наибольшим вкладом в «рискованно» для этого пункта."""
        tfidf: FeatureUnion = self.risk.named_steps["tfidf"]
        lr: LogisticRegression = self.risk.named_steps["lr"]
        words: TfidfVectorizer = tfidf.transformer_list[0][1]
        vec = words.transform([text]).tocoo()
        n_words = len(words.vocabulary_)
        names = words.get_feature_names_out()
        contrib = [
            (float(v * lr.coef_[0][j]), names[j])
            for j, v in zip(vec.col, vec.data, strict=True)
            if j < n_words
        ]
        contrib.sort(reverse=True)
        return [humanize(name) for weight, name in contrib[:n] if weight > 0]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self, "sklearn": sklearn.__version__, "version": MODEL_VERSION}, path)

    @staticmethod
    def load(path: Path) -> ClauseRiskModel | None:
        if not path.exists():
            return None
        payload = joblib.load(path)
        if payload.get("sklearn") != sklearn.__version__ or payload.get("version") != MODEL_VERSION:
            return None
        return payload["model"]


def _docs_hash(docs: Sequence[EvalDoc]) -> str:
    h = hashlib.sha256()
    for d in sorted(docs, key=lambda d: d.doc_id):
        h.update(d.doc_id.encode())
        h.update(d.text.encode())
    return h.hexdigest()[:16]


class MLDetector:
    """Находки по вероятности риска выше порога, выбранного на dev."""

    name = "ml"

    def __init__(self, model: ClauseRiskModel) -> None:
        self.model = model

    def scores(self, doc: ContractDocument, party_role: PartyRole) -> dict[str, tuple]:
        ctype = contract_type_of(party_role)
        clauses = doc.analysable_clauses
        texts = [relative_text(c.text, ctype, c.lang, party_role) for c in clauses]
        return {
            c.id: (*pred, text)
            for c, pred, text in zip(clauses, self.model.predict(texts), texts, strict=True)
        }

    def detect(self, doc: ContractDocument, party_role: PartyRole) -> list[Finding]:
        findings = []
        for clause_id, (p, category, level, text) in self.scores(doc, party_role).items():
            if p < self.model.threshold:
                continue
            clause = doc.clause(clause_id)
            assert clause is not None
            features = self.model.top_features(text)
            findings.append(
                Finding(
                    clause_id=clause_id,
                    category=RiskCategory(category),
                    level=RiskLevel(level),
                    source="ml",
                    rule_id=None,
                    title="Пункт похож на рискованные формулировки",
                    explanation=(
                        f"Модель оценивает вероятность риска для вас в {p:.0%}. "
                        + (
                            "Сильнее всего повлияло: " + "; ".join(f"«{f}»" for f in features) + "."
                            if features
                            else ""
                        )
                        + " Это статистическая оценка без точного правила — проверьте пункт сами."
                    ),
                    evidence=[Evidence(quote=clause.text, start=0, end=len(clause.text))],
                    confidence=round(p, 4),
                    details={"probability": round(p, 4)},
                )
            )
        return findings

    def config(self) -> dict[str, Any]:
        return {
            "model_version": MODEL_VERSION,
            "threshold": self.model.threshold,
            "trained_on": self.model.trained_on,
            "oof": self.model.oof,
        }


def load_or_train(models_dir: Path, data_dir: Path, parser: Parser) -> ClauseRiskModel:
    """Модель из models/, а если её нет или dev-срез изменился — обучить заново (секунды)."""
    from contract_risk.evaluation.dataset import load_split

    dev = load_split(data_dir / "eval", "dev")
    path = models_dir / "clause_risk.joblib"
    model = ClauseRiskModel.load(path)
    if model is None or model.trained_on != _docs_hash(dev):
        model = ClauseRiskModel.train(dev, parser)
        model.save(path)
    return model
