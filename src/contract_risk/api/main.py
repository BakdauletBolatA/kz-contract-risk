"""FastAPI: загрузка договора → отчёт (JSON, HTML или PDF).

Файл не сохраняется ни на диск, ни в базу: байты живут в памяти запроса.
В логи попадают только метаданные (размер, формат, число находок) — не
текст договора: там персональные и коммерческие данные.

    uvicorn contract_risk.api.main:app --port 8000
"""

from __future__ import annotations

import asyncio
import json
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
from contract_risk.extraction.extractor import ExtractionResult, Extractor
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
if not log.handlers and log.level == logging.NOTSET:
    # Под uvicorn логгеры приложения по умолчанию молчат (уровень WARNING, без обработчика),
    # а токены и латентность запросов /extract должны быть видны.
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    log.addHandler(_handler)
    log.setLevel(logging.INFO)
OutputFormat = Literal["json", "html", "pdf"]
MAX_TEXT_CHARS = 300_000


class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    party_role: PartyRole
    format: OutputFormat = "json"


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    model: str | None = Field(
        default=None,
        description="ollama:<имя> или anthropic:<имя>; по умолчанию KZCR_EXTRACT_MODEL",
    )


class ExtractBatchRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=100)
    model: str | None = None


def _default_extractor(model: str) -> Extractor:
    from contract_risk.extraction.backends import build_backend
    from contract_risk.llm.cache import ResponseCache

    return Extractor(
        build_backend(model), cache=ResponseCache(get_settings().cache_dir / "extraction.sqlite")
    )


def create_app(
    analyzer_factory: Callable[[], Analyzer] | None = None,
    extractor_factory: Callable[[str], Extractor] | None = None,
) -> FastAPI:
    factory = analyzer_factory or Analyzer.from_settings
    make_extractor = extractor_factory or _default_extractor
    extractors: dict[str, Extractor] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Модели и корпус загружаются один раз при старте, а не на каждый запрос.
        app.state.analyzer = factory()
        app.state.extract_semaphore = asyncio.Semaphore(get_settings().extract_concurrency)
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

    def extractor_for(model: str | None) -> tuple[str, Extractor]:
        name = model or get_settings().extract_model
        if name not in extractors:
            try:
                extractors[name] = make_extractor(name)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
        return name, extractors[name]

    async def run_extract(name: str, extractor: Extractor, text: str) -> dict:
        async with app.state.extract_semaphore:
            result: ExtractionResult = await asyncio.to_thread(extractor.extract, text)
        payload = {
            "model": name,
            "status": result.status,
            "extraction": result.extraction.model_dump(mode="json") if result.extraction else None,
            "attempts": len(result.attempts),
            "errors": [a.error for a in result.attempts if a.error],
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "latency_ms": round(result.latency_s * 1000),
            "cached": result.cached,
        }
        # В лог — только метаданные: текст договора содержит персональные данные.
        log.info(
            "extract %s",
            json.dumps(
                {
                    k: payload[k]
                    for k in (
                        "model",
                        "status",
                        "attempts",
                        "input_tokens",
                        "output_tokens",
                        "latency_ms",
                        "cached",
                    )
                }
            ),
        )
        return payload

    @app.post("/extract")
    async def extract(request: ExtractRequest) -> JSONResponse:
        name, extractor = extractor_for(request.model)
        payload = await run_extract(name, extractor, request.text)
        return JSONResponse(payload, status_code=200 if payload["extraction"] else 502)

    @app.post("/extract/batch")
    async def extract_batch(request: ExtractBatchRequest) -> JSONResponse:
        name, extractor = extractor_for(request.model)
        if any(len(t) > MAX_TEXT_CHARS for t in request.texts):
            raise HTTPException(413, f"Текст длиннее {MAX_TEXT_CHARS} символов")
        items = await asyncio.gather(*(run_extract(name, extractor, t) for t in request.texts))
        ok = sum(1 for i in items if i["extraction"])
        return JSONResponse(
            {
                "model": name,
                "count": len(items),
                "ok": ok,
                "input_tokens": sum(i["input_tokens"] for i in items),
                "output_tokens": sum(i["output_tokens"] for i in items),
                "items": items,
            }
        )

    return app


app = create_app()
