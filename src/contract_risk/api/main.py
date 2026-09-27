"""FastAPI: загрузка договора → отчёт (JSON, HTML или PDF).

Файл не сохраняется ни на диск, ни в базу: байты живут в памяти запроса.
В логи попадают только метаданные (размер, формат, число находок) — не
текст договора: там персональные и коммерческие данные.

    uvicorn contract_risk.api.main:app --port 8000
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from contract_risk import __version__
from contract_risk.config import get_settings
from contract_risk.ingestion.loaders import SUPPORTED_EXTENSIONS, UnsupportedFormatError
from contract_risk.pipeline import Analyzer
from contract_risk.report.render import render_html, render_pdf
from contract_risk.schemas import (
    ROLES_BY_TYPE,
    Language,
    PartyRole,
    Report,
    RiskCategory,
    RiskLevel,
)
from contract_risk.taxonomy import (
    CATEGORY_DESCRIPTIONS,
    CATEGORY_TITLES,
    DISCLAIMER,
    LEVEL_TITLES,
    ROLE_TITLES,
)

log = logging.getLogger("contract_risk.api")
OutputFormat = Literal["json", "html", "pdf"]
MAX_TEXT_CHARS = 300_000


class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    party_role: PartyRole
    format: OutputFormat = "json"


def create_app(analyzer_factory: Callable[[], Analyzer] | None = None) -> FastAPI:
    factory = analyzer_factory or Analyzer.from_settings

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Модели и корпус загружаются один раз при старте, а не на каждый запрос.
        app.state.analyzer = factory()
        yield

    app = FastAPI(
        title="kz-contract-risk",
        version=__version__,
        description="Первичный скрининг договоров аренды, поставки и подряда. " + DISCLAIMER,
        lifespan=lifespan,
    )

    def analyzer() -> Analyzer:
        return app.state.analyzer

    def respond(report: Report, fmt: OutputFormat) -> Response:
        log.info(
            "analyzed doc=%s findings=%d detector=%s",
            report.doc_id,
            len(report.findings),
            report.detector,
        )
        if fmt == "html":
            return HTMLResponse(render_html(report))
        if fmt == "pdf":
            try:
                pdf = render_pdf(report)
            except RuntimeError as exc:
                raise HTTPException(501, str(exc)) from exc
            return Response(
                pdf,
                media_type="application/pdf",
                headers={"Content-Disposition": 'attachment; filename="contract-report.pdf"'},
            )
        return JSONResponse(report.model_dump(mode="json"))

    @app.get("/health")
    def health() -> dict:
        a = analyzer()
        return {
            "status": "ok",
            "version": __version__,
            "detector": a.detector.name,
            "llm": getattr(a.detector, "llm", None) is not None,
        }

    @app.get("/v1/taxonomy")
    def taxonomy() -> dict:
        return {
            "categories": {
                c.value: {"title": CATEGORY_TITLES[c], "description": CATEGORY_DESCRIPTIONS[c]}
                for c in RiskCategory
            },
            "levels": {level.value: LEVEL_TITLES[level] for level in RiskLevel},
            "roles": {
                ctype.value: {role.value: ROLE_TITLES[role] for role in roles}
                for ctype, roles in ROLES_BY_TYPE.items()
            },
            "formats": sorted(SUPPORTED_EXTENSIONS),
            "disclaimer": DISCLAIMER,
        }

    @app.post("/v1/analyze")
    def analyze_file(
        file: Annotated[UploadFile, File()],
        party_role: Annotated[PartyRole, Form()],
        prefer_language: Annotated[Language, Form()] = Language.RU,
        format: Annotated[OutputFormat, Form()] = "json",
    ) -> Response:
        max_bytes = get_settings().max_upload_mb * 1024 * 1024
        filename = file.filename or "upload"
        if Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                415, f"Поддерживаются файлы: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )
        data = file.file.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise HTTPException(413, f"Файл больше {get_settings().max_upload_mb} МБ")
        if not data:
            raise HTTPException(400, "Пустой файл")
        try:
            report = analyzer().analyze_bytes(data, filename, party_role, prefer_language)
        except UnsupportedFormatError as exc:
            raise HTTPException(415, str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 — битый DOCX/PDF: ответ клиенту, а не 500
            log.warning(
                "не удалось разобрать файл %s: %s", Path(filename).suffix, type(exc).__name__
            )
            raise HTTPException(422, "Не удалось прочитать файл: он повреждён или защищён") from exc
        return respond(report, format)

    @app.post("/v1/analyze/text")
    def analyze_text(request: TextRequest) -> Response:
        return respond(analyzer().analyze_text(request.text, request.party_role), request.format)

    return app


app = create_app()
