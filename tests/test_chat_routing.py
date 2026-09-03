from __future__ import annotations

import unittest
from unittest.mock import Mock

from fastapi import HTTPException
import httpx
import pytest

from app.main import _chat_general_answer, _is_general_chat_message, _should_use_general_chat
import app.main as main_module
from app.api_models import ChatRequest
from app.branding import get_app_brand
from app.services.general_chat_service import GeneralChatService, GeneralChatResult
import app.services.general_chat_service as general_module


class ChatRoutingTests(unittest.TestCase):
    def test_application_capability_questions_do_not_use_rag(self) -> None:
        for message in (
            "RaporHub ne yapar?",
            "RepOcto ne yapar?",
            "SmartCAE AI ne yapar?",
            "Bu uygulama ne yapar?",
            "Kendinden bahset",
        ):
            with self.subTest(message=message):
                self.assertTrue(_is_general_chat_message(message))

    def test_report_questions_still_use_rag(self) -> None:
        for message in (
            "BIG-E konfor raporunda hangi parkurlar var?",
            "2025-BIG-E-DUR-01 raporunun sonucu nedir?",
        ):
            with self.subTest(message=message):
                self.assertFalse(_is_general_chat_message(message))

    def test_short_thanks_use_general_chat_even_in_report_mode(self) -> None:
        for message in ("sağol", "teşekkürler", "eyvallah"):
            with self.subTest(message=message):
                self.assertTrue(_should_use_general_chat("report", message))

        self.assertFalse(
            _should_use_general_chat("report", "2025-BIG-E-DUR-01 raporunun sonucu nedir?")
        )
        self.assertEqual(("Rica ederim.", "chat-direct", 1.0), _chat_general_answer("sağol"))


@pytest.mark.parametrize("variant", ["big_agent", "raporhub", "repocto"])
@pytest.mark.parametrize("failure", ["timeout", "empty"])
def test_general_chat_failure_does_not_become_a_successful_canned_reply(monkeypatch, variant, failure):
    monkeypatch.setattr(main_module, "APP_BRAND", get_app_brand(variant))
    provider = Mock()
    provider.is_available.return_value = True
    if failure == "timeout":
        provider.generate.side_effect = httpx.ReadTimeout("timed out")
    else:
        provider.generate.return_value = ""
    service = GeneralChatService(provider=provider)
    monkeypatch.setattr(main_module, "GeneralChatService", lambda: service)

    with pytest.raises(HTTPException) as error:
        main_module.chat(ChatRequest(message="selam", thinking_mode=True), session=object())

    assert error.value.status_code == 503
    assert "yanıt alınamadı" in error.value.detail
    provider.generate.assert_called_once()


@pytest.mark.parametrize("message", ["selam", "naber", "yaş kaç", "ka. ya;indasin", "bunu nasıl açıklarsın"])
def test_general_questions_use_the_model_answer(monkeypatch, message):
    service = Mock()
    service.answer.return_value = GeneralChatResult("Modelden gelen yanit", "chat-llm:ollama:test", 0.95)
    monkeypatch.setattr(main_module, "GeneralChatService", lambda: service)
    result = main_module.chat(ChatRequest(message=message, assistant_mode="general", thinking_mode=True), session=object())

    assert result.answer == "Modelden gelen yanit"
    assert result.embedding_provider == "chat-llm:ollama:test"
    assert result.thinking_attempted is False
    assert result.thinking_used is False
    service.answer.assert_called_once_with(message, [])


def test_failed_thinking_resolution_is_reported_and_not_retried(monkeypatch):
    document_service = Mock()
    document_service.resolve_conversation.return_value = None
    document_service.last_thinking_used = False
    document_service.last_thinking_route = None
    document_service.last_resolved_question = None
    document_service.retrieval_provider_name.return_value = "test-retrieval"
    document_service.answer_question.return_value = {
        "answer": "Test sonucu", "answer_found": False, "confidence": 0,
        "embedding_provider": "test", "sources": [],
    }
    monkeypatch.setattr(main_module, "DocumentIntelligenceService", lambda session: document_service)
    result = main_module.chat(ChatRequest(message="Raporun sonucu nedir?", thinking_mode=True), session=object())

    assert result.thinking_attempted is True
    assert result.thinking_used is False
    document_service.resolve_conversation.assert_called_once()
    assert document_service.answer_question.call_args.kwargs["thinking_resolution_attempted"] is True


def test_small_talk_skips_thinking_without_reporting_failure(monkeypatch):
    document_factory = Mock(side_effect=AssertionError("Small talk must not start a document planner"))
    monkeypatch.setattr(main_module, "DocumentIntelligenceService", document_factory)
    service = Mock()
    service.answer.return_value = GeneralChatResult("Model yaniti", "chat-llm:ollama:test", 0.95)
    monkeypatch.setattr(main_module, "GeneralChatService", lambda: service)

    result = main_module.chat(ChatRequest(message="selam", thinking_mode=True), session=object())

    assert result.thinking_mode is True
    assert result.thinking_attempted is False
    assert result.thinking_used is False
    document_factory.assert_not_called()


def test_general_chat_preserves_original_question_when_thinking_rewrites_it(monkeypatch):
    document_service = Mock()
    document_service.resolve_conversation.return_value = Mock(
        route="general", standalone_question="Bir kitap icin tavsiye edilen yas nedir?",
    )
    monkeypatch.setattr(main_module, "DocumentIntelligenceService", lambda session: document_service)
    service = Mock()
    service.answer.return_value = GeneralChatResult("Model yaniti", "chat-llm:ollama:test", 0.95)
    monkeypatch.setattr(main_module, "GeneralChatService", lambda: service)

    result = main_module.chat(ChatRequest(message="ka. ya;indasin", thinking_mode=True), session=object())

    service.answer.assert_called_once_with("ka. ya;indasin", [])
    assert result.message == "ka. ya;indasin"
    assert result.history[-2].content == "ka. ya;indasin"
    assert result.thinking_used is True
    assert result.thinking_attempted is True


def test_general_chat_instructions_are_not_embedded_in_the_user_question(monkeypatch):
    monkeypatch.setattr(general_module, "CHAT_LLM_ENABLED", True)
    monkeypatch.setattr(general_module, "CHAT_LLM_BACKEND", "ollama")
    provider_factory = Mock()
    monkeypatch.setattr(general_module, "OllamaLLMProvider", provider_factory)
    general_module._build_chat_provider.__wrapped__()

    assert GeneralChatService._build_prompt("selam", []) == "selam"
    assert provider_factory.call_args.kwargs["system_prompt"] == GeneralChatService._build_system_prompt()


if __name__ == "__main__":
    unittest.main()
