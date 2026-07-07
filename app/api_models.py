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


class DuplicateReportPairResponse(BaseModel):
    id: int | None = None
    document_id_a: int
    document_title_a: str
    file_name_a: str
    document_id_b: int
    document_title_b: str
    file_name_b: str
    similarity_score: float
    title_score: float
    embedding_score: float
    matched_chunks: int = 0
    reason: str
    status: str = "candidate"
    updated_at: str | None = None


class DuplicateReportListResponse(BaseModel):
    total: int
    items: list[DuplicateReportPairResponse]


class DuplicateReportScanResponse(BaseModel):
    dry_run: bool
    threshold: float
    documents_seen: int
    candidate_count: int
    created_count: int
    updated_count: int
    items: list[DuplicateReportPairResponse]


class SearchResponse(BaseModel):
    mode: Literal["keyword", "semantic", "hybrid"]
    semantic_available: bool
    embedding_provider: str
    results: list[SearchResultResponse]
    similar_documents: list[SimilarDocumentResponse]
    retrieval: dict | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=3)
    mode: Literal["keyword", "semantic", "hybrid"] = "keyword"
    limit: int = Field(default=5, ge=1, le=10)
    document_id: int | None = Field(default=None, ge=1)
    use_llm_answer: bool = False


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=1000)
    history: list[ChatMessage] = Field(default_factory=list)
    mode: Literal["keyword", "semantic", "hybrid"] = "hybrid"
    assistant_mode: Literal["auto", "report", "general"] = "auto"
    limit: int = Field(default=5, ge=1, le=10)
    document_id: int | None = Field(default=None, ge=1)
    use_llm_answer: bool = False


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


class ChatResponse(BaseModel):
    message: str
    answer: str
    answer_found: bool
    confidence: float = Field(default=0.0)
    embedding_provider: str
    sources: list[AnswerSourceResponse]
    history: list[ChatMessage]


class DraftReportRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    report_type: str = Field(default="Genel Teknik Rapor", min_length=3, max_length=120)
    report_no: str = Field(default="", max_length=120)
    report_date: str = Field(default="", max_length=40)
    prepared_by: str = Field(default="", max_length=160)
    checked_by: str = Field(default="", max_length=240)
    requested_by: str = Field(default="", max_length=160)
    classification: str = Field(default="GENEL / PUBLIC", max_length=80)
    objective: str = Field(default="", max_length=400)
    keywords: str = Field(default="", max_length=400)
    raw_notes: str = Field(default="", max_length=4000)
    detail_level: Literal["quick", "detailed"] = "detailed"
    mode: Literal["keyword", "semantic", "hybrid"] = "hybrid"
    limit: int = Field(default=5, ge=1, le=10)


class DraftReportResponse(BaseModel):
    title: str
    report_type: str
    report_no: str
    report_date: str
    prepared_by: str
    checked_by: str
    requested_by: str
    classification: str
    detail_level: Literal["quick", "detailed"]
    draft: str
    refined_keywords: list[str]
    cleaned_notes: list[str]
    embedding_provider: str
    generation_provider: str
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


class CatalogImportResponse(BaseModel):
    file_name: str
    rows_seen: int
    created_count: int
    duplicate_count: int
    updated_count: int = 0
    error_count: int
    errors: list[str]


class CatalogEntryResponse(BaseModel):
    id: int
    report_code: str
    vehicle_name: str
    report_title: str
    discipline: str
    report_date: str | None = None
    authors: str | None = None
    source_path: str | None = None
    matched_document_id: int | None = None


class CatalogSearchResponse(BaseModel):
    results: list[CatalogEntryResponse]


class CatalogAskRequest(BaseModel):
    question: str = Field(min_length=3)
    limit: int = Field(default=30, ge=1, le=100)


class CatalogAskResponse(BaseModel):
    question: str
    answer: str
    answer_found: bool
    match_count: int
    filters: dict
    catalog_matches: list[CatalogEntryResponse]


class MultiDocumentAskRequest(BaseModel):
    question: str = Field(min_length=3)
    catalog_question: str | None = Field(default=None, max_length=400)
    mode: Literal["keyword", "semantic", "hybrid"] = "hybrid"
    limit: int = Field(default=6, ge=1, le=12)
    document_ids: list[int] = Field(default_factory=list)


class MultiDocumentScopeResponse(BaseModel):
    document_id: int
    document_title: str
    file_name: str


class MultiDocumentComparisonRowResponse(BaseModel):
    document_id: int
    document_title: str
    answer: str
    confidence: float = Field(default=0.0)
    source_count: int = Field(default=0, ge=0)


class MultiDocumentAskResponse(BaseModel):
    question: str
    catalog_question: str | None = None
    mode: Literal["keyword", "semantic", "hybrid"]
    answer: str
    answer_found: bool
    confidence: float = Field(default=0.0)
    embedding_provider: str
    matched_catalog_count: int = Field(default=0, ge=0)
    matched_document_count: int = Field(default=0, ge=0)
    documents: list[MultiDocumentScopeResponse]
    comparison_rows: list[MultiDocumentComparisonRowResponse]
    sources: list[AnswerSourceResponse]


class CatalogSampleIngestItemResponse(BaseModel):
    catalog_entry_id: int
    discipline: str
    report_code: str
    vehicle_name: str
    report_title: str
    source_path: str
    document_id: int | None = None
    status: Literal["found", "ingested", "duplicate", "error"]
    error: str | None = None


class CatalogSampleIngestResponse(BaseModel):
    dry_run: bool
    per_discipline: int
    disciplines_seen: int
    files_selected: int
    ingested_count: int
    duplicate_count: int
    found_count: int
    error_count: int
    summary: dict
    items: list[CatalogSampleIngestItemResponse]


class CatalogTableRowResponse(BaseModel):
    id: int
    report_code: str
    vehicle_name: str
    report_title: str
    discipline: str
    report_date: str | None = None
    authors: str | None = None
    source_path: str | None = None
    matched_document_id: int | None = None
    status: Literal["ingested", "pending"]
    chunk_count: int = Field(default=0, ge=0)
    embedding_count: int = Field(default=0, ge=0)
    embedding_status: Literal["complete", "partial", "missing", "not_ingested"] = "not_ingested"


class CatalogTableResponse(BaseModel):
    total_seen: int
    ingested_count: int
    pending_count: int
    embedded_count: int
    embedding_pending_count: int
    auto_link_created_count: int = 0
    auto_link_existing_count: int = 0
    ingested: list[CatalogTableRowResponse]
    pending: list[CatalogTableRowResponse]
    embedded: list[CatalogTableRowResponse]
    embedding_pending: list[CatalogTableRowResponse]


class CatalogSelectedIngestRequest(BaseModel):
    catalog_entry_ids: list[int] = Field(default_factory=list)


class CatalogCandidateIngestRequest(BaseModel):
    catalog_entry_id: int = Field(gt=0)
    file_path: str = Field(min_length=1)


class CatalogSelectedIngestResponse(BaseModel):
    requested_count: int
    ingested_count: int
    duplicate_count: int
    error_count: int
    items: list[CatalogSampleIngestItemResponse]
