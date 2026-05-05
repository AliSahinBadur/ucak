from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import logging
import shutil

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DOCUMENTS_DIR
from ..db.models import ChunkEmbedding, Document, DocumentChunk, DocumentPage
from ..parsers.docx_parser import parse_docx
from ..parsers.pdf_parser import parse_pdf
from ..processing.chunker import chunk_sections
from ..processing.text_cleaner import normalize_sections
from ..schemas import ParsedSection
from .embedding_service import EmbeddingService, build_embedding_service


logger = logging.getLogger(__name__)
SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


class IngestService:
    def __init__(
        self,
        session: Session,
        storage_dir: str | Path | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.session = session
        self.storage_dir = Path(storage_dir) if storage_dir else DOCUMENTS_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_service = embedding_service or build_embedding_service()

    def ingest(self, source_file: str | Path, original_file_name: str | None = None) -> dict:
        source_path = Path(source_file)
        extension = source_path.suffix.lower()
        file_name = original_file_name or source_path.name
        title = Path(file_name).stem
        if extension not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {extension}")

        file_hash = self._hash_file(source_path)
        existing = self.session.scalar(select(Document).where(Document.file_hash == file_hash))
        if existing:
            return {
                "document_id": existing.id,
                "status": "duplicate",
                "file_name": existing.file_name,
                "embeddings_created": 0,
                "embedding_provider": self.embedding_service.provider_name,
            }

        stored_path = self._store_file(source_path, file_hash, original_file_name=file_name)

        try:
            parsed_sections = self._parse(stored_path, extension)
            cleaned_sections = normalize_sections(parsed_sections)
            chunks = chunk_sections(cleaned_sections)
        except Exception:
            logger.exception("Ingest failed while parsing or processing %s", stored_path)
            raise

        document = Document(
            title=title,
            file_name=file_name,
            file_type=extension.lstrip("."),
            file_hash=file_hash,
            file_path=str(stored_path),
        )
        self.session.add(document)
        self.session.flush()

        for section in cleaned_sections:
            self.session.add(
                DocumentPage(
                    document_id=document.id,
                    page_number=section.page_number,
                    raw_text=section.raw_text,
                    clean_text=section.clean_text,
                    section_title=section.section_title,
                )
            )

        chunk_models: list[DocumentChunk] = []
        for chunk in chunks:
            chunk_model = DocumentChunk(
                document_id=document.id,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                section_title=chunk.section_title,
                chunk_text=chunk.chunk_text,
                chunk_order=chunk.chunk_order,
            )
            self.session.add(chunk_model)
            chunk_models.append(chunk_model)

        self.session.flush()

        embeddings_created = 0
        for chunk_model in chunk_models:
            vector = self.embedding_service.embed_text(chunk_model.chunk_text)
            if not self.embedding_service.has_signal(vector):
                continue
            self.session.add(
                ChunkEmbedding(
                    chunk_id=chunk_model.id,
                    embedding=self.embedding_service.serialize(vector),
                )
            )
            embeddings_created += 1

        self.session.commit()
        return {
            "document_id": document.id,
            "status": "ingested",
            "file_name": file_name,
            "pages": len(cleaned_sections),
            "chunks": len(chunks),
            "embeddings_created": embeddings_created,
            "embedding_provider": self.embedding_service.provider_name,
        }

    def _parse(self, source_path: Path, extension: str) -> list[ParsedSection]:
        if extension == ".pdf":
            return parse_pdf(source_path)
        if extension == ".docx":
            return parse_docx(source_path)
        raise ValueError(f"Unsupported file type: {extension}")

    def _store_file(
        self,
        source_path: Path,
        file_hash: str,
        original_file_name: str | None = None,
    ) -> Path:
        preferred_name = original_file_name or source_path.name
        original_stem = Path(preferred_name).stem.strip() or "document"
        safe_stem = "".join(
            character if character.isalnum() or character in {"-", "_"} else "_"
            for character in original_stem
        ).strip("_") or "document"
        short_hash = file_hash[:8]
        target_name = f"{safe_stem}__{short_hash}{source_path.suffix.lower()}"
        stored_path = self.storage_dir / target_name
        if stored_path.resolve() != source_path.resolve() and not stored_path.exists():
            shutil.copy2(source_path, stored_path)
        return stored_path

    @staticmethod
    def _hash_file(source_path: Path) -> str:
        digest = sha256()
        with source_path.open("rb") as file_obj:
            for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
