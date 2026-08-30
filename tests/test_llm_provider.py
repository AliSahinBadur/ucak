from __future__ import annotations

from unittest.mock import patch

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
