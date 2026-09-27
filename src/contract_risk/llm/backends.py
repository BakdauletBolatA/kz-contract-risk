"""Вызов Claude со structured output: через LangChain (стек проекта) или Anthropic SDK.

Оба бэкенда отправляют одинаковый запрос, это проверено тестом с подменённым
HTTP-транспортом (tests/test_llm.py):

- ответ строго по JSON-схеме `ClauseAssessment` (`output_config.format`,
  нативный structured output, а не принудительный вызов инструмента);
- `effort` в `output_config` — глубина рассуждения; для классификации
  пунктов по умолчанию `medium`;
- `temperature` не передаётся: на текущих моделях Claude параметры
  сэмплинга не принимаются. Поэтому воспроизводимость обеспечивает не
  temperature=0, а кэш ответов по хэшу входа (llm/cache.py);
- серверные фолбэки при отказе модели (`fallbacks: "default"`): если модель
  отклонит запрос, API повторит его на резервной модели в том же вызове.
  Если отказала вся цепочка — `stop_reason == "refusal"`, пункт остаётся
  без оценки LLM и это видно в статистике прогона;
- системный промпт помечен для кэширования: он одинаковый для всех пунктов.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel

FALLBACK_BETA = "server-side-fallback-2026-07-01"

Category = Literal[
    "penalty",
    "auto_renewal",
    "liability",
    "force_majeure",
    "jurisdiction",
    "termination",
    "unilateral_change",
    "payment",
    "acceptance",
]


class ClauseAssessment(BaseModel):
    is_risky: bool
    category: Category | None
    level: Literal["low", "medium", "high"] | None
    evidence_quote: str
    explanation: str
    safer_wording: str | None
    confidence: float


@dataclass
class LLMReply:
    assessment: ClauseAssessment | None
    stop_reason: str | None
    model: str | None


class LLMBackend(Protocol):
    name: str
    model: str

    def assess(self, system: str, user: str) -> LLMReply: ...


class AnthropicBackend:
    """Прямой вызов Anthropic SDK: `beta.messages.parse` с Pydantic-схемой."""

    name = "anthropic"

    def __init__(
        self,
        model: str,
        effort: str = "medium",
        max_tokens: int = 4096,
        client=None,  # noqa: ANN001 — anthropic.Anthropic, подменяется в тестах
    ) -> None:
        import anthropic

        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self._client = client or anthropic.Anthropic()

    def assess(self, system: str, user: str) -> LLMReply:
        response = self._client.beta.messages.parse(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_format=ClauseAssessment,
            output_config={"effort": self.effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            return LLMReply(None, "refusal", response.model)
        return LLMReply(response.parsed_output, response.stop_reason, response.model)


class LangChainBackend:
    """Тот же запрос через `ChatAnthropic.with_structured_output(method="json_schema")`."""

    name = "langchain"

    def __init__(
        self,
        model: str,
        effort: str = "medium",
        max_tokens: int = 4096,
        client=None,  # noqa: ANN001 — anthropic.Anthropic, подменяется в тестах
    ) -> None:
        from langchain_anthropic import ChatAnthropic

        self.model = model
        chat = ChatAnthropic(
            model=model,
            max_tokens=max_tokens,
            output_config={"effort": effort},
            betas=[FALLBACK_BETA],
            model_kwargs={"fallbacks": "default"},
        )
        if client is not None:
            chat.__dict__["_client"] = client
        self._runnable = chat.with_structured_output(
            ClauseAssessment, method="json_schema", include_raw=True
        )

    def assess(self, system: str, user: str) -> LLMReply:
        from langchain_core.messages import HumanMessage, SystemMessage

        out = self._runnable.invoke(
            [
                SystemMessage(
                    content=[
                        {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
                    ]
                ),
                HumanMessage(content=user),
            ]
        )
        meta = out["raw"].response_metadata
        stop = meta.get("stop_reason")
        if stop == "refusal" or out.get("parsing_error") is not None:
            return LLMReply(None, stop or "parsing_error", meta.get("model"))
        return LLMReply(out["parsed"], stop, meta.get("model"))


def build_backend(kind: str, model: str, effort: str) -> LLMBackend:
    if kind == "anthropic":
        return AnthropicBackend(model, effort)
    if kind == "langchain":
        return LangChainBackend(model, effort)
    raise ValueError(f"неизвестный LLM-бэкенд {kind!r}: langchain или anthropic")
