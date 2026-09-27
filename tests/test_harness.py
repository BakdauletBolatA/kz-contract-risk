"""Харнесс на двух крайних детекторах: null (ничего) и оракул (эталон).

Если у оракула не P = R = 1, сломан харнесс — например, id пунктов
в разметке и после разбора разошлись. Если у null-детектора ненулевой
recall — тоже харнесс.
"""

import json
import re

from contract_risk.detectors import Detector, NullDetector
from contract_risk.evaluation.dataset import EvalDoc, GoldFinding, dataset_hash
from contract_risk.evaluation.harness import evaluate, load_runs, summary_table, write_run
from contract_risk.schemas import Clause, ContractDocument, Finding, PartyRole

TEXT = """ДОГОВОР АРЕНДЫ
1. Предмет
1.1. Арендодатель передаёт помещение.
2. Ответственность
2.1. Арендатор уплачивает пеню 1% за каждый день.
2.2. Арендодатель уплачивает пеню 0,1%.
"""


def stub_parser(text: str, doc_id: str) -> ContractDocument:
    clauses = []
    for line in text.splitlines():
        m = re.match(r"^(\d+\.\d+)\.\s+(.*)$", line)
        if m:
            clauses.append(Clause(id=m.group(1), text=m.group(2)))
    return ContractDocument(doc_id=doc_id, text=text, clauses=clauses)


class OracleDetector:
    name = "oracle"

    def __init__(self, docs: list[EvalDoc]):
        self._gold = {d.doc_id: d for d in docs}

    def detect(self, doc: ContractDocument, party_role: PartyRole) -> list[Finding]:
        return [
            Finding(
                clause_id=g.clause,
                category=g.category,
                level=g.level,
                source="rule",
                title="oracle",
                explanation="oracle",
            )
            for g in self._gold[doc.doc_id].findings
        ]

    def config(self):
        return {}


def make_docs() -> list[EvalDoc]:
    risky = EvalDoc(
        doc_id="lease_001",
        split="dev",
        contract_type="lease",
        language="ru",
        party_role="tenant",
        origin="synthetic",
        text=TEXT,
        findings=[
            GoldFinding(clause="2.1", category="penalty", level="high"),
            GoldFinding(clause=None, category="force_majeure", level="medium"),
        ],
    )
    clean = risky.model_copy(update={"doc_id": "lease_002", "findings": []})
    return [risky, clean]


def test_null_and_oracle_are_protocol_detectors():
    assert isinstance(NullDetector(), Detector)
    assert isinstance(OracleDetector([]), Detector)


def test_null_detector_has_zero_recall_and_no_false_alarms():
    run, _, _ = evaluate(NullDetector(), make_docs(), stub_parser, "dev")
    m = run["metrics"]
    assert m["detection"]["recall"] == 0.0
    assert m["detection"]["precision"] is None
    assert m["clean_docs"]["false_alarms_per_doc"] == 0.0
    assert m["document"]["recall"] == 0.0


def test_oracle_detector_is_perfect():
    docs = make_docs()
    run, _, _ = evaluate(OracleDetector(docs), docs, stub_parser, "dev")
    m = run["metrics"]
    assert m["detection"]["f1"] == 1.0
    assert m["strict"]["f1"] == 1.0
    assert m["document"]["f1"] == 1.0
    assert m["segmentation_coverage"] == 1.0
    assert m["level"]["accuracy"] == 1.0


def test_run_is_written_and_summarised(tmp_path):
    docs = make_docs()
    run, results, parsed = evaluate(NullDetector(), docs, stub_parser, "dev")
    json_path, errors_path = write_run(run, results, parsed, tmp_path)

    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["dataset_hash"] == dataset_hash(docs)
    assert saved["metrics_version"]
    assert "ci95" in saved and "slices" in saved
    # пропуск виден в разборе ошибок вместе с текстом пункта
    errors = errors_path.read_text(encoding="utf-8")
    assert "пропуск" in errors and "1% за каждый день" in errors

    table = summary_table(load_runs(tmp_path))
    assert "| null | dev |" in table


def test_dataset_hash_changes_with_labels():
    docs = make_docs()
    before = dataset_hash(docs)
    docs[1] = docs[1].model_copy(
        update={"findings": [GoldFinding(clause="1.1", category="penalty", level="low")]}
    )
    assert dataset_hash(docs) != before
