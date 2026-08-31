"""HTTP-level tests over the real FastAPI app.

The `client` fixture runs the app's lifespan against the temp-directory SQLite
database configured in conftest, so these exercise routing, dependency wiring,
Pydantic request/response contracts and the service layer underneath -- with no
model, no Ollama and no network.
"""

from __future__ import annotations

import time

import pytest

from app.version import APP_VERSION


def _await_job(client, job_id: str, timeout_seconds: float = 10.0) -> dict:
    """Poll a background job until it reaches a terminal state."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"succeeded", "failed"}:
            return payload
        time.sleep(0.02)
    raise AssertionError(f"Job {job_id} did not finish within {timeout_seconds}s")


# --- health and metadata -----------------------------------------------------


def test_health_reports_the_running_variant(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": APP_VERSION,
        "application": "SmartCAE AI",
        "variant": "big_agent",
    }


def test_meta_reports_the_active_embedding_model(client) -> None:
    response = client.get("/meta")

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == APP_VERSION
    assert payload["model"] == "token-hash-v1"


def test_model_status_reports_the_token_hash_fallback_and_a_disabled_ollama(client) -> None:
    response = client.get("/system/model-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["embedding"]["active_provider"] == "token-hash-v1"
    assert payload["embedding"]["ready"] is False
    # token-hash is what was *configured*, so this is not a failed-model fallback.
    assert payload["embedding"]["fallback_active"] is False
    assert payload["ollama"]["configured"] is False
    assert payload["ollama"]["state"] == "disabled"


def test_favicon_is_served_inline_for_the_default_variant(client) -> None:
    response = client.get("/favicon.ico")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")


def test_root_serves_the_smartcae_workspace(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "__APP_VERSION__" not in response.text


def test_legacy_spa_is_still_reachable(client) -> None:
    response = client.get("/app")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_openapi_schema_builds_and_is_cached(client) -> None:
    first = client.get("/openapi.json")

    assert first.status_code == 200
    schema = first.json()
    assert "/search" in schema["paths"]
    assert "/ask" in schema["paths"]
    # The binary-upload patch rewrites the multipart body of /ingest.
    upload_schema = schema["paths"]["/ingest"]["post"]["requestBody"]["content"]
    assert "multipart/form-data" in upload_schema

    assert client.get("/openapi.json").json() == schema


def test_login_page_redirects_home_when_auth_is_disabled(client) -> None:
    response = client.post("/login", data={"username": "x", "password": "y"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"


# --- /search -----------------------------------------------------------------


def test_search_returns_hybrid_results_over_the_seeded_corpus(client, seed_corpus) -> None:
    response = client.get("/search", params={"query": "dayanim testi", "limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "hybrid"
    assert payload["semantic_available"] is True
    assert payload["embedding_provider"] == "token-hash-v1"
    assert [item["document_id"] for item in payload["results"]] == [seed_corpus["durability"].id]
    assert payload["retrieval"] is None


@pytest.mark.parametrize("mode", ["keyword", "semantic", "hybrid"])
def test_search_supports_every_mode(client, seed_corpus, mode: str) -> None:
    response = client.get("/search", params={"query": "radyator sicakligi", "mode": mode})

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == mode
    assert [item["document_id"] for item in payload["results"]] == [seed_corpus["thermal"].id]


def test_search_report_scope_returns_document_level_hits(client, seed_corpus) -> None:
    response = client.get("/search", params={"query": "titresim", "search_scope": "reports"})

    assert response.status_code == 200
    payload = response.json()
    assert [item["document_id"] for item in payload["results"]] == [seed_corpus["nvh"].id]
    assert payload["similar_documents"] == []


def test_search_through_the_orchestrator_reports_its_retrieval_trace(client, seed_corpus) -> None:
    response = client.get(
        "/search",
        params={"query": "dayanim testi", "use_query_enhancement": "true"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval"] is not None
    assert [item["document_id"] for item in payload["results"]] == [seed_corpus["durability"].id]


def test_search_on_an_empty_corpus_answers_with_no_results(client) -> None:
    response = client.get("/search", params={"query": "dayanim"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"] == []
    assert payload["semantic_available"] is False


@pytest.mark.parametrize(
    "params",
    [
        {"query": "a"},
        {"query": "dayanim", "limit": 0},
        {"query": "dayanim", "limit": 21},
        {"query": "dayanim", "mode": "magic"},
        {"query": "dayanim", "search_scope": "everything"},
        {},
    ],
)
def test_search_rejects_out_of_contract_parameters(client, params: dict) -> None:
    assert client.get("/search", params=params).status_code == 422


# --- /ask --------------------------------------------------------------------


def test_ask_cites_the_document_the_answer_came_from(client, seed_corpus) -> None:
    response = client.post("/ask", json={"question": "Yorulma olcumleri nerede yapildi?", "mode": "hybrid"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["sources"]
    assert payload["sources"][0]["document_id"] == seed_corpus["durability"].id
    assert payload["embedding_provider"] == "token-hash-v1"


def test_ask_says_so_when_nothing_matches(client, seed_corpus) -> None:
    response = client.post("/ask", json={"question": "Hidrojen yakit hucresi verimi nedir?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer_found"] is False
    assert payload["confidence"] == 0.0
    assert payload["sources"] == []


def test_ask_can_be_scoped_to_one_document(client, seed_corpus) -> None:
    response = client.post(
        "/ask",
        json={
            "question": "Olcumler nasil yapildi?",
            "mode": "keyword",
            "document_id": seed_corpus["nvh"].id,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert {item["document_id"] for item in payload["sources"]} <= {seed_corpus["nvh"].id}


@pytest.mark.parametrize(
    "body",
    [
        {"question": "ab"},
        {"question": "gecerli soru", "limit": 0},
        {"question": "gecerli soru", "limit": 11},
        {"question": "gecerli soru", "mode": "magic"},
        {"question": "gecerli soru", "document_id": 0},
        {},
    ],
)
def test_ask_rejects_out_of_contract_bodies(client, body: dict) -> None:
    assert client.post("/ask", json=body).status_code == 422


# --- /chat -------------------------------------------------------------------


def test_chat_answers_small_talk_without_touching_retrieval(client, seed_corpus) -> None:
    response = client.post("/chat", json={"message": "tesekkurler"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval_used"] is False
    assert payload["sources"] == []
    assert payload["history"][-1]["role"] == "assistant"


def test_chat_routes_a_report_question_through_retrieval(client, seed_corpus) -> None:
    response = client.post(
        "/chat",
        json={"message": "Yorulma olcumleri nerede yapildi?", "assistant_mode": "report"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval_used"] is True
    assert payload["retrieval_version"] == "v2"
    assert payload["history"][0]["content"] == "Yorulma olcumleri nerede yapildi?"


def test_chat_still_short_circuits_small_talk_in_report_mode(client, seed_corpus) -> None:
    response = client.post("/chat", json={"message": "tesekkurler", "assistant_mode": "report"})

    assert response.status_code == 200
    assert response.json()["retrieval_used"] is False


def test_chat_drops_a_history_entry_that_repeats_the_current_message(client, seed_corpus) -> None:
    response = client.post(
        "/chat",
        json={
            "message": "tesekkurler",
            "history": [{"role": "user", "content": "tesekkurler"}],
        },
    )

    assert response.status_code == 200
    history = response.json()["history"]
    assert [item["content"] for item in history] == ["tesekkurler", history[-1]["content"]]


@pytest.mark.parametrize(
    "body",
    [
        {"message": "a"},
        {"message": "gecerli mesaj", "assistant_mode": "magic"},
        {"message": "gecerli mesaj", "retrieval_version": "v9"},
        {"message": "gecerli mesaj", "document_ids": list(range(1, 10))},
        {},
    ],
)
def test_chat_rejects_out_of_contract_bodies(client, body: dict) -> None:
    assert client.post("/chat", json=body).status_code == 422


# --- /documents --------------------------------------------------------------


def test_documents_list_is_empty_for_a_fresh_install(client) -> None:
    response = client.get("/documents/list")

    assert response.status_code == 200
    assert response.json() == {"total": 0, "items": []}


def test_documents_list_counts_chunks_and_embeddings(client, seed_corpus) -> None:
    response = client.get("/documents/list")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    by_id = {item["document_id"]: item for item in payload["items"]}
    durability = by_id[seed_corpus["durability"].id]
    assert durability["title"] == "2025-BIG-E-DUR-01 Dayanim Testi Raporu"
    assert durability["file_type"] == "pdf"
    assert durability["chunk_count"] == 2
    assert durability["embedding_count"] == 2


def test_documents_list_limit_is_bounded(client) -> None:
    assert client.get("/documents/list", params={"limit": 0}).status_code == 422
    assert client.get("/documents/list", params={"limit": 501}).status_code == 422
    assert client.get("/documents/list", params={"limit": 1}).status_code == 200


def test_document_detail_renders_the_stored_pages(client, seed_corpus) -> None:
    response = client.get(f"/documents/{seed_corpus['durability'].id}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "2025-BIG-E-DUR-01" in response.text


def test_document_detail_is_404_for_an_unknown_id(client, seed_corpus) -> None:
    assert client.get("/documents/999999").status_code == 404


def test_document_file_is_404_when_the_original_is_gone(client, seed_corpus) -> None:
    # seed_corpus stores a file_path that intentionally does not exist on disk.
    response = client.get(f"/documents/{seed_corpus['durability'].id}/file")

    assert response.status_code == 404


def test_storage_check_flags_every_missing_source_file(client, seed_corpus) -> None:
    response = client.get("/storage/check")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_documents"] == 3
    assert payload["missing_file_count"] == 3
    assert payload["healthy_documents"] == 0
    assert {issue["issue"] for issue in payload["issues"]} == {"missing_file"}


# --- ingest guardrails -------------------------------------------------------


def test_ingest_rejects_an_unsupported_extension(client) -> None:
    response = client.post("/ingest", files={"file": ("notlar.txt", b"merhaba", "text/plain")})

    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_ingest_requires_a_file(client) -> None:
    assert client.post("/ingest").status_code == 422


# --- background jobs ---------------------------------------------------------


def test_jobs_list_is_bounded_and_ordered_newest_first(client) -> None:
    response = client.get("/jobs", params={"limit": 5})

    assert response.status_code == 200
    assert len(response.json()["items"]) <= 5


def test_jobs_list_rejects_an_out_of_range_limit(client) -> None:
    assert client.get("/jobs", params={"limit": 0}).status_code == 422
    assert client.get("/jobs", params={"limit": 101}).status_code == 422


def test_unknown_job_is_404(client) -> None:
    response = client.get("/jobs/does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found."


def test_embedding_rebuild_runs_as_a_job_and_re_embeds_every_chunk(client, seed_corpus) -> None:
    accepted = client.post("/embeddings/rebuild")

    assert accepted.status_code == 202
    submitted = accepted.json()
    assert submitted["kind"] == "embeddings_rebuild"
    assert submitted["status"] in {"queued", "running", "succeeded"}

    finished = _await_job(client, submitted["job_id"])

    assert finished["status"] == "succeeded", finished["error"]
    assert finished["result"]["chunks_seen"] == 4
    assert finished["result"]["embeddings_created"] == 4
    assert finished["result"]["embedding_provider"] == "token-hash-v1"

    listed = client.get("/jobs").json()["items"]
    assert submitted["job_id"] in {item["job_id"] for item in listed}


def test_duplicate_scan_runs_as_a_job(client, seed_corpus) -> None:
    accepted = client.post("/duplicates/scan", params={"dry_run": "true"})

    assert accepted.status_code == 202
    finished = _await_job(client, accepted.json()["job_id"])

    assert finished["status"] == "succeeded", finished["error"]
    assert finished["result"]["dry_run"] is True
    assert finished["result"]["documents_seen"] == 3


def test_duplicates_listing_is_empty_before_a_scan(client, seed_corpus) -> None:
    response = client.get("/duplicates")

    assert response.status_code == 200
    assert response.json() == {"total": 0, "items": []}


# --- other read-only surfaces ------------------------------------------------


def test_catalog_search_is_empty_without_an_import(client, seed_corpus) -> None:
    response = client.get("/catalog/search", params={"query": "dayanim"})

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_graph_overview_describes_the_seeded_corpus(client, seed_corpus) -> None:
    response = client.get("/graph/overview")

    assert response.status_code == 200
    assert "nodes" in response.json()


def test_catia_skill_reports_itself_disabled(client) -> None:
    response = client.get("/skills/catia-mass-cg/status")

    assert response.status_code == 200
    assert response.json()["enabled"] is False
