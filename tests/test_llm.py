"""LLM-слой без сети: настоящий код SDK и LangChain поверх подменённого HTTP-транспорта.

Живой вызов API в тестах не нужен и не желателен: проверяется то, за что
отвечает этот код, — какой запрос уходит, как разбирается ответ и отказ,
что отбрасываются находки без дословной цитаты, что работает кэш.
"""

import json

import httpx2
import pytest
from anthropic import Anthropic, DefaultHttpxClient

from contract_risk.hybrid import HybridDetector
from contract_risk.ingestion import parse_text
from contract_risk.llm.backends import (
    FALLBACK_BETA,
    AnthropicBackend,
    ClauseAssessment,
    LangChainBackend,
    LLMReply,
)
from contract_risk.llm.cache import ResponseCache
from contract_risk.llm.classifier import LLMClassifier, LLMDetector, ground
from contract_risk.llm.redact import redact
from contract_risk.rules.engine import RulesDetector
from contract_risk.schemas import Clause, ContractType, PartyRole

RISKY = {
    "is_risky": True,
    "category": "payment",
    "level": "medium",
    "evidence_quote": "100-процентной предоплаты",
    "explanation": "Вы платите всю сумму вперёд.",
    "safer_wording": "Предоплата 30%.",
    "confidence": 0.9,
}


def mock_client(stop_reason="end_turn", payload=RISKY):
    seen = {}

    def handler(request):
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        content = [] if payload is None else [{"type": "text", "text": json.dumps(payload)}]
        return httpx2.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "claude-opus-5",
                "content": content,
                "stop_reason": stop_reason,
                "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    client = Anthropic(
        api_key="test", http_client=DefaultHttpxClient(transport=httpx2.MockTransport(handler))
    )
    return client, seen


@pytest.mark.parametrize("backend_cls", [AnthropicBackend, LangChainBackend])
def test_backend_request_shape_and_parsing(backend_cls):
    client, seen = mock_client()
    backend = backend_cls("claude-opus-5", effort="medium", client=client)
    reply = backend.assess("СИСТЕМА", "ПУНКТ")

    body = seen["body"]
    assert body["model"] == "claude-opus-5"
    assert body["output_config"]["effort"] == "medium"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["fallbacks"] == "default"
    assert FALLBACK_BETA in seen["headers"]["anthropic-beta"]
    # на текущих моделях сэмплинг не задаётся, а вызов инструмента не форсируется
    assert "temperature" not in body and "tool_choice" not in body
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert reply.assessment == ClauseAssessment(**RISKY)


@pytest.mark.parametrize("backend_cls", [AnthropicBackend, LangChainBackend])
def test_backend_refusal_returns_no_assessment(backend_cls):
    client, _ = mock_client(stop_reason="refusal", payload=None)
    reply = backend_cls("claude-opus-5", client=client).assess("С", "П")
    assert reply.assessment is None
    assert reply.stop_reason == "refusal"


def test_redact_personal_data():
    text = (
        "ИИН 900101300123, счет KZ12345678901234567A, тел. +7 (701) 123-45-67, "
        "почта a.b@mail.kz. Пеня 0,5% за 10 дней."
    )
    masked, n = redact(text)
    assert n == 4
    assert "900101300123" not in masked and "KZ1234" not in masked
    assert "[ИИН/БИН]" in masked and "[IBAN]" in masked and "[ТЕЛЕФОН]" in masked
    assert "Пеня 0,5% за 10 дней." in masked  # смысл для классификации не тронут
    assert redact("IBAN KZ12 3456 7890 1234 567A")[0] == "IBAN [IBAN]"


def test_ground_finds_quote_despite_whitespace_quotes_and_case():
    text = "Товар поставляется на  условиях\n«100-процентной» предоплаты."
    ev = ground('на условиях "100-ПРОЦЕНТНОЙ" предоплаты', text)
    assert ev is not None
    assert text[ev.start : ev.end] == ev.quote
    assert ev.quote.startswith("на  условиях")


def test_ground_rejects_hallucination_and_trivial_quotes():
    text = "Товар поставляется на условиях предоплаты."
    assert ground("штраф 50% от суммы договора", text) is None
    assert ground("", text) is None
    assert ground("..", text) is None


class FakeBackend:
    """Ответы по ключевой фразе в сообщении — детерминированная замена модели."""

    name = "fake"
    model = "fake-model"

    def __init__(self, answers: dict[str, dict | None], fail_on: str | None = None):
        self.answers = answers
        self.fail_on = fail_on
        self.calls = 0

    def assess(self, system, user):
        self.calls += 1
        if self.fail_on and self.fail_on in user:
            raise ConnectionError("сеть недоступна")
        for key, payload in self.answers.items():
            if key in user:
                if payload is None:
                    return LLMReply(None, "refusal", self.model)
                return LLMReply(ClauseAssessment(**payload), "end_turn", self.model)
        return LLMReply(
            ClauseAssessment(
                is_risky=False,
                category=None,
                level=None,
                evidence_quote="",
                explanation="Риска нет.",
                safer_wording=None,
                confidence=0.9,
            ),
            "end_turn",
            self.model,
        )


def clause(text, cid="1.1"):
    return Clause(id=cid, text=text)


def test_cache_makes_second_run_free(tmp_path):
    backend = FakeBackend({"предоплат": RISKY})
    cache = ResponseCache(tmp_path / "c.sqlite")
    c = clause("Товар поставляется на условиях 100-процентной предоплаты.")
    first = LLMClassifier(backend, cache)
    a1, cached1 = first.assess(c, ContractType.SUPPLY, PartyRole.BUYER)
    second = LLMClassifier(backend, cache)
    a2, cached2 = second.assess(c, ContractType.SUPPLY, PartyRole.BUYER)
    assert (cached1, cached2) == (False, True)
    assert a1 == a2 and backend.calls == 1
    # другая роль — другой вход — промах кэша
    second.assess(c, ContractType.SUPPLY, PartyRole.SUPPLIER)
    assert backend.calls == 2


def test_refusal_is_cached_and_counted(tmp_path):
    backend = FakeBackend({"предоплат": None})
    classifier = LLMClassifier(backend, ResponseCache(tmp_path / "c.sqlite"))
    c = clause("Товар поставляется на условиях 100-процентной предоплаты.")
    assert classifier.assess(c, ContractType.SUPPLY, PartyRole.BUYER) == (None, False)
    assert classifier.assess(c, ContractType.SUPPLY, PartyRole.BUYER) == (None, True)
    assert classifier.stats.refusals == 2 and backend.calls == 1


def test_backend_error_does_not_break_analysis():
    classifier = LLMClassifier(FakeBackend({}, fail_on="предоплат"))
    result = classifier.assess(
        clause("Товар поставляется на условиях 100-процентной предоплаты."),
        ContractType.SUPPLY,
        PartyRole.BUYER,
    )
    assert result == (None, False)
    assert classifier.stats.errors == 1


def test_personal_data_never_reaches_backend():
    backend = FakeBackend({})
    sent = []
    original = backend.assess
    backend.assess = lambda system, user: sent.append(user) or original(system, user)
    classifier = LLMClassifier(backend)
    classifier.assess(
        clause("Оплата на счет KZ12345678901234567A, БИН 123456789012."),
        ContractType.SUPPLY,
        PartyRole.BUYER,
    )
    assert "123456789012" not in sent[0] and "KZ1234" not in sent[0]
    assert classifier.stats.redactions == 2


@pytest.mark.parametrize(
    ("answer", "counter"),
    [
        ({**RISKY, "evidence_quote": "штраф 50% в день"}, "rejected_ungrounded"),
        ({**RISKY, "category": None}, "rejected_invalid"),
        ({**RISKY, "confidence": 0.3}, "low_confidence"),
    ],
)
def test_detector_rejects_unsupported_findings(answer, counter):
    detector = LLMDetector(LLMClassifier(FakeBackend({"предоплат": answer})))
    doc = parse_text(
        "ДОГОВОР\n1.1. Товар поставляется на условиях 100-процентной предоплаты.\n", "d"
    )
    assert detector.detect(doc, PartyRole.BUYER) == []
    assert getattr(detector.classifier.stats, counter) == 1


def test_detector_accepts_grounded_finding():
    detector = LLMDetector(LLMClassifier(FakeBackend({"предоплат": RISKY})))
    doc = parse_text(
        "ДОГОВОР\n1.1. Товар поставляется на условиях 100-процентной предоплаты.\n", "d"
    )
    [finding] = detector.detect(doc, PartyRole.BUYER)
    assert finding.source == "llm"
    assert finding.category.value == "payment"
    assert finding.evidence[0].quote == "100-процентной предоплаты"
    assert finding.details["prompt_version"].startswith("clause_v1:")


class StubML:
    """ML-маршрутизатор с заданными вероятностями."""

    class model:  # noqa: N801 — повторяет интерфейс ClauseRiskModel
        route_threshold = 0.5
        emit_threshold = 0.99

    def __init__(self, probs):
        self.probs = probs

    def scores(self, doc, role):
        return {
            c.id: (self.probs.get(c.id, 0.0), "payment", "medium", "")
            for c in doc.analysable_clauses
        }

    def detect(self, doc, role):
        return []

    def config(self):
        return {}


CONTRACT = """ДОГОВОР ПОСТАВКИ
1. Условия
1.1. Покупатель уплачивает пеню 1% за каждый день просрочки оплаты.
1.2. Товар поставляется на условиях 100-процентной предоплаты.
1.3. Товар доставляется до склада Покупателя.
"""


def test_hybrid_sends_only_rule_silent_routed_clauses_to_llm():
    backend = FakeBackend({"предоплат": RISKY})
    llm = LLMDetector(LLMClassifier(backend))
    hybrid = HybridDetector(RulesDetector(), StubML({"1.2": 0.7, "1.3": 0.1}), llm)
    findings = hybrid.detect(parse_text(CONTRACT, "d"), PartyRole.BUYER)
    by_clause = {f.clause_id: f.source for f in findings if f.clause_id}
    # 1.1 нашли правила — в LLM не уходит; 1.3 отсеял маршрутизатор
    assert by_clause == {"1.1": "rule", "1.2": "llm"}
    assert backend.calls == 1
    assert hybrid.config()["routing"] == {"silent": 2, "routed": 1}
    assert hybrid.name == "hybrid_llm"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ИП Калиев Д.С. обязуется", "ИП [ФИО] обязуется"),
        ("в лице директора Д. С. Калиева", "в лице директора [ФИО]"),
        ("в лице Жаксылыковой-Смит А.Н., действующей", "в лице [ФИО], действующей"),
        ("Сейтов Асан Ерланұлы, именуемый", "[ФИО], именуемый"),
        ("Иванова Мария Петровна подписала", "[ФИО] подписала"),
    ],
)
def test_redact_names(text, expected):
    assert redact(text)[0] == expected


def test_redact_names_keeps_contract_terms():
    text = "Арендатор уплачивает Арендодателю пеню по ст. 297 ГК РК, п. 5.2 Договора."
    assert redact(text) == (text, 0)
