"""Чат-бэкенды для извлечения: Ollama (локально), Anthropic (API), Mock (тесты).

Бэкенд возвращает сырой текст ответа и счётчики — разбор и проверка по схеме
делает `Extractor`. Так «валидный JSON с первой попытки» измеряется одинаково
для всех моделей. Схему декодирования ни один бэкенд не навязывает: Ollama
получает `format: "json"` (синтаксис JSON, но не схема), Claude — обычный
запрос. Иначе метрика валидности измеряла бы сервер, а не модель.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

import httpx

Message = dict[str, str]


@dataclass
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    latency_s: float


class BackendError(RuntimeError):
    """Сеть, таймаут, отказ API — ошибка окружения, а не плохой ответ модели."""


class ChatBackend(Protocol):
    name: str
    model: str

    def complete(self, system: str, messages: Sequence[Message]) -> Completion: ...


class OllamaBackend:
    name = "ollama"

    def __init__(
        self,
        model: str,
        host: str = "http://127.0.0.1:11434",
        timeout_s: float = 300.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self._client = client or httpx.Client(base_url=host, timeout=timeout_s)

    def complete(self, system: str, messages: Sequence[Message]) -> Completion:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "seed": 0, "num_ctx": 8192},
            "messages": [{"role": "system", "content": system}, *messages],
        }
        t0 = time.perf_counter()
        try:
            r = self._client.post("/api/chat", json=payload)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise BackendError(f"ollama {self.model}: {exc}") from exc
        elapsed = time.perf_counter() - t0
        body = r.json()
        return Completion(
            text=body.get("message", {}).get("content", ""),
            input_tokens=int(body.get("prompt_eval_count", 0)),
            output_tokens=int(body.get("eval_count", 0)),
            latency_s=elapsed,
        )


class AnthropicBackend:
    name = "anthropic"

    def __init__(
        self,
        model: str,
        max_tokens: int = 2048,
        client=None,  # noqa: ANN001
        api_key: str | None = None,
    ) -> None:
        import anthropic

        self.model = model
        self.max_tokens = max_tokens
        self._client = client or anthropic.Anthropic(api_key=api_key)

    def complete(self, system: str, messages: Sequence[Message]) -> Completion:
        import anthropic

        t0 = time.perf_counter()
        try:
            r = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=list(messages),
            )
        except anthropic.APIError as exc:
            raise BackendError(f"anthropic {self.model}: {exc}") from exc
        elapsed = time.perf_counter() - t0
        text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        return Completion(text, r.usage.input_tokens, r.usage.output_tokens, elapsed)


class OpenAIBackend:
    """Chat Completions через httpx: JSON-режим без схемы, как и у остальных бэкендов."""

    name = "openai"

    def __init__(
        self,
        model: str,
        api_key: str | None,
        base_url: str = "https://api.openai.com/v1",
        timeout_s: float = 120.0,
        client: httpx.Client | None = None,
        name: str = "openai",
    ) -> None:
        self.name = name  # grok и deepseek говорят на том же диалекте
        self.model = model
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = client or httpx.Client(base_url=base_url, headers=headers, timeout=timeout_s)

    def complete(self, system: str, messages: Sequence[Message]) -> Completion:
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, *messages],
        }
        t0 = time.perf_counter()
        try:
            r = self._client.post("/chat/completions", json=payload)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            detail = ""
            if isinstance(exc, httpx.HTTPStatusError):
                detail = f" {exc.response.status_code}"
            raise BackendError(f"{self.name} {self.model}:{detail} {type(exc).__name__}") from exc
        elapsed = time.perf_counter() - t0
        body = r.json()
        usage = body.get("usage", {})
        return Completion(
            text=body["choices"][0]["message"]["content"] or "",
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
            latency_s=elapsed,
        )


class MockBackend:
    """Ответы по очереди из функции — для тестов retry и API без сети."""

    name = "mock"

    def __init__(
        self, respond: Callable[[str, Sequence[Message]], str], model: str = "mock"
    ) -> None:
        self.model = model
        self._respond = respond
        self.calls = 0

    def complete(self, system: str, messages: Sequence[Message]) -> Completion:
        self.calls += 1
        text = self._respond(system, messages)
        return Completion(text, len(system) // 4, len(text) // 4, 0.001)


def build_backend(spec: str) -> ChatBackend:
    """Строка вида `<бэкенд>:<модель>`.

    Примеры: `ollama:qwen2.5:7b`, `anthropic:claude-haiku-4-5-20251001`,
    `openai:gpt-4o-mini`, `grok:<модель>`, `deepseek:<модель>` (последние три —
    диалект OpenAI Chat Completions).
    """
    kind, _, model = spec.partition(":")
    if kind == "ollama" and model:
        from contract_risk.config import get_settings

        return OllamaBackend(model, host=get_settings().ollama_host)
    if kind == "anthropic" and model:
        from contract_risk.config import get_settings

        return AnthropicBackend(model, api_key=get_settings().anthropic_api_key)
    if kind == "openai" and model:
        from contract_risk.config import get_settings

        return OpenAIBackend(model, api_key=get_settings().openai_api_key)
    if kind in ("grok", "deepseek") and model:
        from contract_risk.config import get_settings

        st = get_settings()
        key, url = (
            (st.grok_api_key, st.grok_base_url)
            if kind == "grok"
            else (st.deepseek_api_key, st.deepseek_base_url)
        )
        return OpenAIBackend(model, api_key=key, base_url=url, name=kind)
    raise ValueError(
        f"неизвестная модель {spec!r}: ожидается <бэкенд>:<имя>, "
        "бэкенд — ollama, anthropic, openai, grok или deepseek"
    )
