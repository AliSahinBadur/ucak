"""Shared test setup: an offline, deterministic app instance.

The environment is pinned *before* anything under ``app`` is imported, because
``app.db.session`` builds the engine from ``Settings`` at module import time and
``get_settings()`` is ``lru_cache``d -- by the time a fixture body runs it is
already too late to redirect the database. Everything here keeps the suite
model-free and network-free: ``token-hash`` embeddings need no model download,
and every LLM path is switched off, so the tests below exercise real retrieval
and real HTTP routing rather than mocks.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterator

import pytest


TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="ucak-test-data-"))

os.environ["BIG_AGENT_DATA_DIR"] = str(TEST_DATA_DIR)
os.environ["APP_VARIANT"] = "big_agent"
os.environ["APP_AUTH_ENABLED"] = "false"
os.environ["EMBEDDING_BACKEND"] = "token-hash"
os.environ["LLM_ENABLED"] = "false"
os.environ["LLM_ANSWER_ENABLED"] = "false"
os.environ["CHAT_LLM_ENABLED"] = "false"
os.environ["REPORT_LLM_ENABLED"] = "false"
os.environ["RERANKER_ENABLED"] = "false"
os.environ["CATIA_SKILL_ENABLED"] = "false"

# Imported only after the environment above is in place.
from app.db.models import Base  # noqa: E402
from app.db.models import ChunkEmbedding, Document, DocumentChunk, DocumentPage  # noqa: E402
from app.db.session import SessionLocal, engine, init_db  # noqa: E402
from app.services.embedding_service import TokenHashEmbeddingService  # noqa: E402
from app.services.vector_index import invalidate_vector_index  # noqa: E402


EMBEDDER = TokenHashEmbeddingService()

# Sentinel for "derive the embedding from the chunk text with the token-hash
# provider", so callers can still pass None to mean "store no embedding at all".
AUTO_EMBEDDING = object()


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ARG001
    # Windows will not delete the database file while a pooled connection still
    # holds it, so close the pool first; ignore_errors keeps a stubborn temp dir
    # from turning into a failing teardown.
    engine.dispose()
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


def _clear_tables(db) -> None:
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()


@pytest.fixture
def db_session() -> Iterator:
    """A session on the app's own engine, with every table emptied around the test."""
    init_db()
    session = SessionLocal()
    _clear_tables(session)
    invalidate_vector_index()
    try:
        yield session
    finally:
        session.rollback()
        _clear_tables(session)
        invalidate_vector_index()
        session.close()


@pytest.fixture
def client(db_session) -> Iterator:
    """TestClient over the real app; `db_session` guarantees a clean corpus."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def add_document(
    session,
    title: str,
    *,
    file_name: str | None = None,
    file_type: str = "pdf",
    file_hash: str | None = None,
    file_path: str | None = None,
) -> Document:
    """Insert a Document and flush it so its id is available."""
    resolved_file_name = file_name or f"{title}.{file_type}"
    document = Document(
        title=title,
        file_name=resolved_file_name,
        file_type=file_type,
        file_hash=file_hash or f"hash-{title}-{resolved_file_name}",
        file_path=file_path or f"/nonexistent/{resolved_file_name}",
    )
    session.add(document)
    session.flush()
    return document


def add_page(
    session,
    document: Document,
    text: str,
    *,
    page_number: int = 1,
    section_title: str | None = None,
) -> DocumentPage:
    page = DocumentPage(
        document_id=document.id,
        page_number=page_number,
        raw_text=text,
        clean_text=text,
        section_title=section_title,
    )
    session.add(page)
    session.flush()
    return page


def add_chunk(
    session,
    document: Document,
    text: str,
    *,
    chunk_order: int = 1,
    page_start: int = 1,
    page_end: int = 1,
    section_title: str | None = None,
    embedding: object = AUTO_EMBEDDING,
) -> DocumentChunk:
    """Insert a chunk, optionally with an embedding row.

    `embedding` accepts the AUTO_EMBEDDING sentinel (token-hash of `text`),
    None (no embedding row at all), a list of floats, or raw bytes -- the last
    two let tests plant vectors with known geometry or deliberately corrupt
    payloads.
    """
    chunk = DocumentChunk(
        document_id=document.id,
        page_start=page_start,
        page_end=page_end,
        section_title=section_title,
        chunk_text=text,
        chunk_order=chunk_order,
    )
    session.add(chunk)
    session.flush()

    if embedding is None:
        return chunk
    if embedding is AUTO_EMBEDDING:
        payload = EMBEDDER.serialize(EMBEDDER.embed_document(text))
    elif isinstance(embedding, (bytes, bytearray)):
        payload = bytes(embedding)
    else:
        payload = EMBEDDER.serialize(list(embedding))
    session.add(ChunkEmbedding(chunk_id=chunk.id, embedding=payload))
    session.flush()
    return chunk


@pytest.fixture
def seed_corpus(db_session):
    """Three small Turkish reports with token-hash embeddings, committed.

    Returns the documents by a short key so tests can assert on ids without
    re-querying.
    """
    durability = add_document(
        db_session,
        "2025-BIG-E-DUR-01 Dayanim Testi Raporu",
        file_name="2025-BIG-E-DUR-01-dayanim.pdf",
    )
    add_page(db_session, durability, "Dayanim testi kapsaminda yorulma olcumleri yapilmistir.")
    add_chunk(
        db_session,
        durability,
        "Dayanim testi kapsaminda sasi yorulma olcumleri Torku parkurunda yapilmistir. "
        "Toplam 12000 km yol verisi toplanmistir.",
        chunk_order=1,
    )
    add_chunk(
        db_session,
        durability,
        "Yorulma omru hesaplamasi icin gerinim olcer verileri kullanilmistir. "
        "Kritik bolgelerde hasar birikimi sinir degerin altinda kalmistir.",
        chunk_order=2,
        page_start=2,
        page_end=2,
    )

    nvh = add_document(
        db_session,
        "2024-BIG-E-NVH-07 Titresim ve Gurultu Raporu",
        file_name="2024-BIG-E-NVH-07-titresim.pdf",
    )
    add_chunk(
        db_session,
        nvh,
        "Titresim olcumleri direksiyon simidi ve koltuk rayi uzerinden alinmistir. "
        "Kabin ici gurultu seviyesi 68 dBA olarak olculmustur.",
        chunk_order=1,
    )

    thermal = add_document(
        db_session,
        "Termal Analiz Ozeti",
        file_name="termal-analiz-ozeti.pdf",
    )
    add_chunk(
        db_session,
        thermal,
        "Motor bolmesi sicaklik dagilimi CFD ile incelenmistir. "
        "Radyator cikis sicakligi 92 santigrat derece olarak hesaplanmistir.",
        chunk_order=1,
    )

    db_session.commit()
    invalidate_vector_index()
    return {"durability": durability, "nvh": nvh, "thermal": thermal}
