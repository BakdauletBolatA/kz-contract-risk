"""Файл договора → отчёт. Единая точка входа для API, UI и CLI.

Пайплайн не хранит загруженный файл: байты живут только в памяти запроса.
Договор — это персональные и коммерческие данные контрагентов, и сервис
первичного скрининга не должен становиться их архивом.
"""

from __future__ import annotations

from datetime import UTC, datetime

from contract_risk import __version__
from contract_risk.config import Settings, get_settings
from contract_risk.detectors import Detector, build_detector
from contract_risk.ingestion import parse_bytes, parse_text
from contract_risk.ingestion.ocr import OcrEngine, TesseractOcr
from contract_risk.rag.compare import MarketComparator
from contract_risk.schemas import (
    ContractDocument,
    ContractType,
    Language,
    PartyRole,
    Report,
    contract_type_of,
)
from contract_risk.taxonomy import CONTRACT_TYPE_TITLES, ROLE_TITLES


def build_comparator(settings: Settings) -> MarketComparator:
    """Корпус из pgvector, если он настроен, иначе в памяти процесса."""
    from contract_risk.corpus.manifest import load_corpus
    from contract_risk.retrieval.embeddings import build_embedder
    from contract_risk.retrieval.index import ReferenceIndex

    embedder = build_embedder(settings.embedder)
    if settings.database_url:
        from contract_risk.retrieval.store import PgVectorStore

        store = PgVectorStore(settings.database_url, embedder.name, embedder.dim)
        meta = store.check_compatible()
        return MarketComparator(ReferenceIndex(embedder, store, meta.get("corpus_version", "")))
    corpus = load_corpus(settings.data_dir / "corpus")
    return MarketComparator(ReferenceIndex.in_memory(corpus, embedder))


class Analyzer:
    def __init__(
        self,
        detector: Detector,
        comparator: MarketComparator | None = None,
        ocr: OcrEngine | None = None,
    ) -> None:
        self.detector = detector
        self.comparator = comparator
        self.ocr = ocr

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> Analyzer:
        settings = settings or get_settings()
        ocr = TesseractOcr() if settings.ocr_enabled and TesseractOcr.available() else None
        return cls(build_detector(settings.detector), build_comparator(settings), ocr)

    def analyze_bytes(
        self,
        data: bytes,
        filename: str,
        party_role: PartyRole,
        prefer_language: Language = Language.RU,
    ) -> Report:
        doc = parse_bytes(data, filename, ocr=self.ocr, prefer_language=prefer_language)
        return self.analyze_document(doc, party_role)

    def analyze_text(self, text: str, party_role: PartyRole, doc_id: str = "text") -> Report:
        return self.analyze_document(parse_text(text, doc_id), party_role)

    def analyze_document(self, doc: ContractDocument, party_role: PartyRole) -> Report:
        warnings = list(doc.warnings)
        expected = contract_type_of(party_role)
        if doc.contract_type is not None and doc.contract_type != expected:
            warnings.append(
                f"Похоже, это договор типа «{CONTRACT_TYPE_TITLES[doc.contract_type]}», "
                f"а выбрана роль «{ROLE_TITLES[party_role]}». Проверьте, что роль указана верно."
            )
        doc.contract_type = expected
        if not doc.analysable_clauses:
            warnings.append("В документе не найдено ни одного пункта договора для анализа.")
            findings = []
        else:
            findings = self.detector.detect(doc, party_role)
        if self.comparator is not None:
            self.comparator.attach(doc, findings, party_role)
        if getattr(self.detector, "llm", "absent") is None:
            warnings.append(
                "Проверка языковой моделью выключена: отчёт показывает только условия, "
                "распознанные точными правилами. Нестандартные формулировки могут быть "
                "пропущены."
            )

        order = {c.id: i for i, c in enumerate(doc.clauses)}
        findings.sort(
            key=lambda f: (-f.level.rank, f.clause_id is not None, order.get(f.clause_id or "", 0))
        )
        return Report(
            doc_id=doc.doc_id,
            title=doc.title,
            contract_type=expected,
            party_role=party_role,
            language=doc.language,
            detector=self.detector.name,
            pipeline_version=__version__,
            generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
            clauses_total=len(doc.clauses),
            clauses_analysed=len(doc.analysable_clauses),
            findings=findings,
            warnings=warnings,
            clause_texts={
                f.clause_id: doc.clause(f.clause_id).text
                for f in findings
                if f.clause_id is not None and doc.clause(f.clause_id) is not None
            },
        )


def default_role(contract_type: ContractType) -> PartyRole:
    """Сторона, которую малый бизнес занимает чаще всего: арендатор, покупатель, заказчик."""
    return {
        ContractType.LEASE: PartyRole.TENANT,
        ContractType.SUPPLY: PartyRole.BUYER,
        ContractType.WORKS: PartyRole.CUSTOMER,
    }[contract_type]
