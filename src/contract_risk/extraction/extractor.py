"""Извлечение с проверкой по схеме и одним повтором по тексту ошибки.

Цикл: запрос → разбор JSON → `ContractExtraction.model_validate`. Если ответ
не разобрался или не прошёл схему, модели один раз возвращают её же ответ и
список ошибок («поле X: …») с просьбой исправить. Больше одного повтора не
делаем: это измеряемое решение (см. README, «Повтор»), а не «пока не
получится» — иначе валидность превращается в функцию бюджета.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from contract_risk.extraction.backends import ChatBackend, Completion, Message
from contract_risk.extraction.schema import ContractExtraction
from contract_risk.llm.cache import ResponseCache, cache_key

PROMPT_PATH = Path(__file__).parent / "prompts" / "extract_v1.txt"
_SCHEMA_JSON = json.dumps(ContractExtraction.model_json_schema(), ensure_ascii=False)
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8").replace("{schema}", _SCHEMA_JSON)
PROMPT_VERSION = f"extract_v1:{hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:8]}"

Status = Literal["ok_first_try", "ok_after_retry", "failed", "backend_error"]


@dataclass
class Attempt:
    ok: bool
    error: str | None
    input_tokens: int
    output_tokens: int
    latency_s: float


@dataclass
class ExtractionResult:
    status: Status
    extraction: ContractExtraction | None
    attempts: list[Attempt] = field(default_factory=list)
    model: str = ""
    cached: bool = False

    @property
    def ok(self) -> bool:
        return self.extraction is not None

    @property
    def input_tokens(self) -> int:
        return sum(a.input_tokens for a in self.attempts)

    @property
    def output_tokens(self) -> int:
        return sum(a.output_tokens for a in self.attempts)

    @property
    def latency_s(self) -> float:
        return sum(a.latency_s for a in self.attempts)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "model": self.model,
            "extraction": self.extraction.model_dump(mode="json") if self.extraction else None,
            "attempts": [asdict(a) for a in self.attempts],
        }

    @classmethod
    def from_dict(cls, d: dict) -> ExtractionResult:
        return cls(
            status=d["status"],
            extraction=ContractExtraction.model_validate(d["extraction"])
            if d["extraction"]
            else None,
            attempts=[Attempt(**a) for a in d["attempts"]],
            model=d["model"],
            cached=True,
        )


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json_object(text: str) -> dict:
    """Достаёт JSON-объект из ответа; ValueError с понятным текстом, если не вышло."""
    s = _FENCE.sub("", text.strip())
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("в ответе нет JSON-объекта")
    try:
        obj = json.loads(s[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"невалидный JSON: {exc.msg} (позиция {exc.pos})") from exc
    if not isinstance(obj, dict):
        raise ValueError("ожидался JSON-объект")
    return obj


def format_validation_error(exc: ValidationError) -> str:
    lines = []
    for e in exc.errors()[:12]:
        loc = ".".join(str(x) for x in e["loc"]) or "(корень)"
        lines.append(f"- {loc}: {e['msg']}")
    return "\n".join(lines)


def _validate(text: str) -> tuple[ContractExtraction | None, str | None]:
    try:
        obj = parse_json_object(text)
    except ValueError as exc:
        return None, str(exc)
    try:
        return ContractExtraction.model_validate(obj), None
    except ValidationError as exc:
        return None, format_validation_error(exc)


RETRY_TEMPLATE = (
    "Твой ответ не прошёл проверку:\n{error}\n\n"
    "Исправь ответ. Верни ТОЛЬКО исправленный JSON-объект по схеме, все ключи обязательны."
)


class Extractor:
    def __init__(
        self,
        backend: ChatBackend,
        cache: ResponseCache | None = None,
        max_retries: int = 1,
    ) -> None:
        self.backend = backend
        self.cache = cache
        self.max_retries = max_retries

    def _key(self, text: str) -> str:
        version = f"{PROMPT_VERSION}:r{self.max_retries}"
        return cache_key(self.backend.model, version, SYSTEM_PROMPT, text)

    def extract(self, text: str) -> ExtractionResult:
        key = self._key(text) if self.cache is not None else None
        if self.cache is not None and key:
            hit = self.cache.get(key)
            if hit:
                return ExtractionResult.from_dict(hit)

        messages: list[Message] = [{"role": "user", "content": f"Договор:\n\n{text}"}]
        attempts: list[Attempt] = []
        extraction: ContractExtraction | None = None
        for _ in range(self.max_retries + 1):
            try:
                completion = self.backend.complete(SYSTEM_PROMPT, messages)
            except Exception as exc:  # noqa: BLE001 — сеть/таймаут/API: фиксируем и не кэшируем
                attempts.append(Attempt(False, f"{type(exc).__name__}: {exc}", 0, 0, 0.0))
                return ExtractionResult("backend_error", None, attempts, self.backend.model)
            extraction, error = _validate(completion.text)
            attempts.append(_attempt(completion, error))
            if extraction is not None:
                break
            messages = [
                *messages,
                {"role": "assistant", "content": completion.text or "{}"},
                {"role": "user", "content": RETRY_TEMPLATE.format(error=error)},
            ]

        if extraction is None:
            status: Status = "failed"
        else:
            status = "ok_first_try" if len(attempts) == 1 else "ok_after_retry"
        result = ExtractionResult(status, extraction, attempts, self.backend.model)
        if self.cache is not None and key:
            self.cache.put(key, self.backend.model, PROMPT_VERSION, result.to_dict())
        return result


def _attempt(c: Completion, error: str | None) -> Attempt:
    return Attempt(error is None, error, c.input_tokens, c.output_tokens, c.latency_s)


def extract_many(
    extractor: Extractor, texts: Sequence[str], workers: int = 4
) -> list[ExtractionResult]:
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(extractor.extract, texts))
