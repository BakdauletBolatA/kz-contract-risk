"""ML: относительный текст ролей, обучение, пороги, объяснение."""

from pathlib import Path

import numpy as np
import pytest

from contract_risk.evaluation.dataset import load_split
from contract_risk.ingestion import parse_text
from contract_risk.ml.features import feature_tokens, humanize, relative_text
from contract_risk.ml.model import ClauseRiskModel, MLDetector, choose_threshold, wording_signature
from contract_risk.schemas import ContractType, Language, PartyRole

ROOT = Path(__file__).resolve().parents[1]
PENALTY = "Арендатор уплачивает Арендодателю пеню 1% за каждый день просрочки."


def test_relative_text_depends_on_user_side():
    tenant = relative_text(PENALTY, ContractType.LEASE, Language.RU, PartyRole.TENANT)
    landlord = relative_text(PENALTY, ContractType.LEASE, Language.RU, PartyRole.LANDLORD)
    assert tenant.startswith("USER_nom уплачивает CP_dat пеню")
    assert landlord.startswith("CP_nom уплачивает USER_dat пеню")
    assert "RATE_HIGH" in tenant and "NOCAP" in tenant


def test_feature_tokens_and_humanize():
    assert feature_tokens("Покупатель оплачивает Товар в течение 90 дней.") == ["TERM_LONG"]
    assert humanize("cp_nom вправе rate_high") == "контрагент вправе пеня от 0,5% в день"


def test_wording_signature_ignores_numbers():
    assert wording_signature("пеня 0,5% за 10 дней") == wording_signature("Пеня 1% за 30 дней")


def test_choose_threshold_respects_min_precision():
    y = np.array([1, 1, 1, 0, 0, 0])
    proba = np.array([0.9, 0.8, 0.4, 0.6, 0.2, 0.1])
    threshold, f1, precision, recall = choose_threshold(y, proba, min_precision=0.9)
    assert precision >= 0.9
    assert threshold == pytest.approx(0.8)
    assert recall == pytest.approx(2 / 3)


@pytest.fixture(scope="module")
def small_model():
    docs = load_split(ROOT / "data/eval", "dev")[::3]
    return ClauseRiskModel.train(docs, parse_text, folds=3)


def test_training_records_both_oof_estimates_and_thresholds(small_model):
    oof = small_model.oof
    assert {"by_doc_f1", "by_wording_f1", "n_clauses", "n_risky"} <= set(oof)
    # группировка по формулировке строже группировки по договору
    assert oof["by_wording_f1"] <= oof["by_doc_f1"]
    assert 0 < small_model.route_threshold < small_model.emit_threshold <= 0.99


def test_detector_scores_every_analysable_clause(small_model):
    doc = parse_text(
        "ДОГОВОР АРЕНДЫ\n1.1. " + PENALTY + "\n1.2. Помещение передается по акту.\n", "d"
    )
    scores = MLDetector(small_model).scores(doc, PartyRole.TENANT)
    assert set(scores) == {"1.1", "1.2"}
    assert scores["1.1"][0] > scores["1.2"][0]
    for finding in MLDetector(small_model).detect(doc, PartyRole.TENANT):
        assert finding.source == "ml" and 0 <= finding.confidence <= 1
