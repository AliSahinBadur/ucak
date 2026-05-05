from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    version: str


class IngestResponse(BaseModel):
    document_id: int
    status: Literal["ingested", "duplicate"]
    file_name: str | None = None
    pages: int | None = None
    chunks: int | None = None
    embeddings_created: int = 0
    embedding_provider: str


class BatchIngestItemResponse(BaseModel):
    file_name: str
    status: Literal["ingested", "duplicate", "error"]
    document_id: int | None = None
    pages: int | None = None
    chunks: int | None = None
    embeddings_created: int = 0
    embedding_provider: str | None = None
    error: str | None = None


class BatchIngestResponse(BaseModel):
    total_files: int
    ingested_count: int
    duplicate_count: int
    error_count: int
    items: list[BatchIngestItemResponse]


class SearchResultResponse(BaseModel):
    id: int
    document_id: int
    document_title: str
    page_start: int
    page_end: int
    section_title: str | None = None
    chunk_text: str
    match_type: Literal["keyword", "semantic", "hybrid"]
    keyword_score: float = Field(default=0.0)
    semantic_score: float = Field(default=0.0)
    combined_score: float = Field(default=0.0)


class SimilarDocumentResponse(BaseModel):
    document_id: int
    document_title: str
    file_name: str
    matched_chunks: int
    score: float
    top_section_title: str | None = None
    top_page_start: int | None = None
    top_page_end: int | None = None
    top_excerpt: str


class SearchResponse(BaseModel):
    mode: Literal["keyword", "semantic", "hybrid"]
    semantic_available: bool
    embedding_provider: str
    results: list[SearchResultResponse]
    similar_documents: list[SimilarDocumentResponse]


class AskRequest(BaseModel):
    question: str = Field(min_length=3)
    mode: Literal["keyword", "semantic", "hybrid"] = "hybrid"
    limit: int = Field(default=5, ge=1, le=10)


class AnswerSourceResponse(BaseModel):
    document_id: int
    document_title: str
    file_name: str | None = None
    page_start: int
    page_end: int
    section_title: str | None = None
    chunk_text: str
    match_type: Literal["keyword", "semantic", "hybrid"]
    keyword_score: float = Field(default=0.0)
    semantic_score: float = Field(default=0.0)
    combined_score: float = Field(default=0.0)


class AskResponse(BaseModel):
    question: str
    mode: Literal["keyword", "semantic", "hybrid"]
    answer: str
    answer_found: bool
    confidence: float = Field(default=0.0)
    embedding_provider: str
    sources: list[AnswerSourceResponse]


class ReindexEmbeddingsResponse(BaseModel):
    embedding_provider: str
    chunks_seen: int
    embeddings_created: int


class StorageIssueResponse(BaseModel):
    document_id: int
    file_name: str
    file_path: str
    issue: str


class StorageCheckResponse(BaseModel):
    total_documents: int
    healthy_documents: int
    missing_file_count: int
    issues: list[StorageIssueResponse]
