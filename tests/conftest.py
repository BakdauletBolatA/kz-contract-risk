import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def pg_dsn():
    """DSN настоящего pgvector. Без KZCR_TEST_DSN pg-тесты пропускаются.

    Локально: make db && export KZCR_TEST_DSN=postgresql://kzcr:kzcr@localhost:5439/kzcr
    """
    dsn = os.environ.get("KZCR_TEST_DSN")
    if not dsn:
        pytest.skip("KZCR_TEST_DSN не задан — тест против pgvector пропущен")
    return dsn


@pytest.fixture(scope="session")
def corpus():
    from contract_risk.corpus.manifest import load_corpus

    return load_corpus(ROOT / "data/corpus")
