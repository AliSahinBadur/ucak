from pathlib import Path
from types import SimpleNamespace

import app.main as main


def test_embedding_runtime_status_reports_loaded_sentence_transformer(monkeypatch, tmp_path: Path) -> None:
    model_dir = tmp_path / "Qwen3-Embedding-4B"
    model_dir.mkdir()
    service = SimpleNamespace(
        provider_name=f"sentence-transformers:{model_dir}",
        model=object(),
        device="cuda:0",
    )
    monkeypatch.setattr(main, "build_embedding_service", lambda: service)
    monkeypatch.setattr(main, "EMBEDDING_PROVIDER", "sentence-transformers")
    monkeypatch.setattr(main, "EMBEDDING_MODEL_NAME", str(model_dir))
    monkeypatch.setattr(main, "EMBEDDING_LOCAL_FILES_ONLY", True)

    status = main._embedding_runtime_status()

    assert status["state"] == "ready"
    assert status["ready"] is True
    assert status["active_model"] == "Qwen3-Embedding-4B"
    assert status["device"] == "cuda:0"
    assert status["model_path_exists"] is True
    assert status["fallback_active"] is False


def test_embedding_runtime_status_exposes_token_hash_fallback(monkeypatch, tmp_path: Path) -> None:
    configured_model = tmp_path / "Qwen3-Embedding-4B"
    service = SimpleNamespace(provider_name="token-hash-v1")
    monkeypatch.setattr(main, "build_embedding_service", lambda: service)
    monkeypatch.setattr(main, "EMBEDDING_PROVIDER", "sentence-transformers")
    monkeypatch.setattr(main, "EMBEDDING_MODEL_NAME", str(configured_model))
    monkeypatch.setattr(main, "EMBEDDING_LOCAL_FILES_ONLY", True)

    status = main._embedding_runtime_status()

    assert status["state"] == "warning"
    assert status["ready"] is False
    assert status["fallback_active"] is True
    assert status["active_model"] == "token-hash-v1"
    assert status["model_path_exists"] is False


def test_ollama_runtime_status_checks_host_and_configured_model(monkeypatch) -> None:
    requested_urls: list[str] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"models": [{"name": "qwen2.5:3b"}, {"name": "nomic-embed-text:latest"}]}

    class FakeClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 2.0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            requested_urls.append(url)
            return FakeResponse()

    monkeypatch.setattr(main, "CHAT_LLM_ENABLED", True)
    monkeypatch.setattr(main, "CHAT_LLM_BACKEND", "ollama")
    monkeypatch.setattr(main, "CHAT_LLM_MODEL_NAME", "qwen2.5:3b")
    monkeypatch.setattr(main, "OLLAMA_HOST", "http://127.0.0.1:11435")
    monkeypatch.setattr(main.httpx, "Client", FakeClient)

    status = main._ollama_runtime_status()

    assert requested_urls == ["http://127.0.0.1:11435/api/tags"]
    assert status["state"] == "ready"
    assert status["connected"] is True
    assert status["model_available"] is True


def test_gpu_menu_loads_model_status_only_when_opened() -> None:
    source = Path(main.__file__).read_text(encoding="utf-8")

    assert 'id="systemStatusMenu"' in source
    assert 'id="systemEmbeddingState"' in source
    assert 'id="systemOllamaState"' in source
    assert '<div data-repocto-hide><span>Embedding</span><strong>__DEVICE_LABEL__</strong></div>' in source
    assert 'data-repocto-only hidden><span>Ollama</span>' in source
    assert 'fetch("/system/model-status"' in source
    assert "if (isRepOcto) {" in source
    assert 'if (systemStatusMenu.open) refreshSystemModelStatus();' in source
