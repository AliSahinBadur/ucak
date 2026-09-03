from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
from pydantic import BaseModel

from app.services.llm_provider import OllamaLLMProvider


class StructuredPayload(BaseModel):
    status: str
    score: int


def test_ollama_generate_json_sends_pydantic_schema_as_format() -> None:
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"message": {"content": '{"status":"ok","score":7}'}}

    class FakeClient:
        def __init__(self, *, timeout: float) -> None:
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def post(self, url: str, *, json: dict):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    provider = OllamaLLMProvider("qwen-test", timeout_seconds=12.0)
    with patch("app.services.llm_provider.httpx.Client", FakeClient):
        result = provider.generate_json("Kontrol et", StructuredPayload)

    assert result == StructuredPayload(status="ok", score=7)
    assert captured["timeout"] == 12.0
    assert captured["json"]["format"] == StructuredPayload.model_json_schema()
    assert captured["json"]["options"]["temperature"] == 0.0
    assert captured["json"]["stream"] is False
    assert captured["json"]["think"] is False


@pytest.mark.parametrize("model", ["qwen2.5:3b", "qwen3.5:9b"])
def test_ollama_text_answer_disables_implicit_thinking(model: str) -> None:
    with patch("app.services.llm_provider.httpx.Client") as client:
        response = client.return_value.__enter__.return_value.post.return_value
        response.json.return_value = {"message": {"content": "Test yaniti"}}
        answer = OllamaLLMProvider(model).generate("selam", max_tokens=240)
        payload = client.return_value.__enter__.return_value.post.call_args.kwargs["json"]

    assert answer == "Test yaniti"
    assert payload["model"] == model
    assert payload["think"] is False
    assert "think" not in payload["options"]
    assert payload["options"]["num_predict"] == 240


@pytest.mark.parametrize("content", ["", "  ", None, 42])
def test_ollama_empty_answer_is_not_replaced_with_thinking(content) -> None:
    with patch("app.services.llm_provider.httpx.Client") as client:
        response = client.return_value.__enter__.return_value.post.return_value
        response.json.return_value = {"message": {"content": content, "thinking": "internal trace"}}
        with pytest.raises(RuntimeError, match="empty or invalid"):
            OllamaLLMProvider("qwen3.5:9b").generate("selam")


def test_ollama_timeout_is_not_retried_or_disguised_as_an_answer() -> None:
    with patch("app.services.llm_provider.httpx.Client") as client:
        post = client.return_value.__enter__.return_value.post
        post.side_effect = httpx.ReadTimeout("timed out")
        with pytest.raises(httpx.ReadTimeout):
            OllamaLLMProvider("qwen3.5:9b").generate("selam")
        post.assert_called_once()


def test_ollama_system_instructions_have_their_own_message_role() -> None:
    with patch("app.services.llm_provider.httpx.Client") as client:
        post = client.return_value.__enter__.return_value.post
        post.return_value.json.return_value = {"message": {"content": "Test yaniti"}}
        OllamaLLMProvider("qwen-test", system_prompt="Asistan talimati").generate("Kullanici sorusu")
        messages = post.call_args.kwargs["json"]["messages"]

    assert messages == [
        {"role": "system", "content": "Asistan talimati"},
        {"role": "user", "content": "Kullanici sorusu"},
    ]
