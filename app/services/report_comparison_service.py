from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import json
import logging
from pathlib import Path
import re
import secrets
import time
import unicodedata
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import (
    CHAT_LLM_BACKEND,
    CHAT_LLM_ENABLED,
    CHAT_LLM_MODEL_NAME,
    CHAT_LLM_TIMEOUT_SECONDS,
    DATA_DIR,
)
from ..db.models import ChunkEmbedding, Document, DocumentChunk
from ..parsers.docx_parser import parse_docx
from ..parsers.pdf_parser import parse_pdf
from ..parsers.pptx_parser import parse_pptx
from ..processing.chunker import chunk_sections
from ..processing.text_cleaner import normalize_sections
from .embedding_service import EmbeddingService, build_embedding_service
from .llm_provider import DisabledLLMProvider, LLMProvider, OllamaLLMProvider
from .pdf_highlight_service import PdfHighlightRequest, PdfHighlightService


logger = logging.getLogger(__name__)


@dataclass
class ComparisonChunk:
    key: str
    page_start: int
    page_end: int
    section_title: str | None
    text: str
    vector: list[float]


@dataclass
class ComparisonDocument:
    source_ref: str
    title: str
    file_name: str
    source_path: Path
    content_hash: str
    document_id: int | None
    temporary: bool
    chunks: list[ComparisonChunk]


class ReportComparisonService:
    ALGORITHM_VERSION = "hybrid-v3-pdf-highlights"
    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx"}
    MAX_UPLOAD_BYTES = 80 * 1024 * 1024
    TEMP_UPLOAD_TTL_SECONDS = 24 * 60 * 60
    MAX_CHUNKS_PER_DOCUMENT = 40
    MAX_MATCHED_PAIRS = 16
    MAX_RESULT_ITEMS = 20
    HIGHLIGHT_PALETTE = (
        "#F6C344",
        "#55B5FF",
        "#6CD49D",
        "#FF8FB1",
        "#FFA75A",
        "#B695FF",
        "#54D6C4",
        "#EF767A",
        "#A7D46F",
        "#64C6E3",
        "#D8A657",
        "#C587D9",
        "#8CC8A5",
        "#F08A5D",
        "#84A9FF",
        "#D4C45E",
    )

    STOP_WORDS = {
        "aciklama",
        "analiz",
        "ara",
        "bir",
        "bu",
        "da",
        "de",
        "degerlendirme",
        "degerlendirilmistir",
        "degerleri",
        "degerlerinin",
        "datalarinin",
        "den",
        "dosyasi",
        "edilebilir",
        "gerceklestirilmistir",
        "icin",
        "ile",
        "incelenmistir",
        "islenmesi",
        "ise",
        "linki",
        "neticesinde",
        "olarak",
        "olan",
        "ortak",
        "rapor",
        "raporu",
        "raporunda",
        "raporunun",
        "sayfa",
        "sonuc",
        "tablo",
        "tarafindan",
        "test",
        "ve",
        "veya",
        "yapilan",
    }
    POSITIVE_STATUS = {"ok", "uygun", "basarili", "gecti", "guvenli", "emniyetli"}
    NEGATIVE_STATUS = {"nok", "uygun degil", "basarisiz", "gecmedi", "guvensiz", "emniyetsiz"}
    TECHNICAL_TERMS = {
        "amac",
        "bulgu",
        "deger",
        "frekans",
        "gerilme",
        "ivme",
        "kapsam",
        "konfor",
        "maksimum",
        "minimum",
        "parkur",
        "sensor",
        "sonuc",
        "stres",
        "strain",
        "sicaklik",
        "tasarim",
        "titresim",
        "tork",
        "yontem",
        "yuk",
    }
    UNIT_ALIASES = {
        "mpa": "MPa",
        "kpa": "kPa",
        "pa": "Pa",
        "kn": "kN",
        "n": "N",
        "nm": "Nm",
        "n.m": "Nm",
        "mm": "mm",
        "cm": "cm",
        "m": "m",
        "hz": "Hz",
        "kg": "kg",
        "g": "g",
        "c": "C",
        "°c": "C",
        "%": "%",
    }

    def __init__(
        self,
        session: Session,
        embedding_service: EmbeddingService | None = None,
        llm_provider: LLMProvider | None = None,
        temp_dir: str | Path | None = None,
        cache_dir: str | Path | None = None,
    ) -> None:
        self.session = session
        self.embedding_service = embedding_service or build_embedding_service()
        self.llm_provider = llm_provider or _build_report_comparison_provider()
        self.temp_dir = Path(temp_dir) if temp_dir else DATA_DIR / "comparison_temp"
        self.cache_dir = Path(cache_dir) if cache_dir else DATA_DIR / "comparison_cache"
        self.pdf_preview_dir = self.cache_dir / "pdf"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_preview_dir.mkdir(parents=True, exist_ok=True)

    def store_temporary_upload(self, file_name: str, content: bytes) -> dict:
        extension = Path(file_name or "").suffix.lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError("Yalnizca PDF, DOCX ve PPTX dosyalari destekleniyor.")
        if not content:
            raise ValueError("Yuklenen dosya bos.")
        if len(content) > self.MAX_UPLOAD_BYTES:
            raise ValueError("Dosya boyutu 80 MB sinirini asiyor.")

        self._cleanup_temporary_uploads()
        token = secrets.token_urlsafe(18)
        target_path = self.temp_dir / f"{token}{extension}"
        metadata_path = self.temp_dir / f"{token}.json"
        content_hash = sha256(content).hexdigest()
        target_path.write_bytes(content)
        metadata_path.write_text(
            json.dumps(
                {
                    "token": token,
                    "file_name": Path(file_name).name,
                    "extension": extension,
                    "content_hash": content_hash,
                    "created_at": int(time.time()),
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
        return {
            "upload_token": token,
            "source_ref": f"temp:{token}",
            "title": Path(file_name).stem,
            "file_name": Path(file_name).name,
            "temporary": True,
            "expires_in_seconds": self.TEMP_UPLOAD_TTL_SECONDS,
        }

    def compare(self, left_source: dict, right_source: dict, use_llm: bool = True) -> dict:
        left = self._resolve_source(left_source)
        right = self._resolve_source(right_source)
        if left.source_ref == right.source_ref:
            raise ValueError("Karsilastirma icin iki farkli rapor sec.")
        if not left.chunks or not right.chunks:
            raise ValueError("Raporlardan birinde karsilastirilabilir metin bulunamadi.")

        cache_key = self._cache_key(left, right, use_llm=use_llm)
        cached = self._read_cache(cache_key, require_llm=use_llm)
        if cached is not None:
            self._attach_pdf_previews(cached, left, right, cache_key)
            cached["cache_hit"] = True
            return cached

        pairs = self._align_chunks(left, right)
        similarities, differences = self._build_pair_results(left, right, pairs)
        llm_used = False
        if use_llm and self.llm_provider.is_available() and pairs:
            similarities, differences, llm_used = self._refine_with_llm(
                left,
                right,
                pairs,
                similarities,
                differences,
            )

        differences.extend(self._unmatched_results(left, right, pairs))
        similarities = self._dedupe_results(similarities)[: self.MAX_RESULT_ITEMS]
        differences = self._dedupe_results(differences)[: self.MAX_RESULT_ITEMS]
        self._assign_highlight_metadata(similarities, differences)
        matched_left = {pair["left"].key for pair in pairs}
        matched_right = {pair["right"].key for pair in pairs}
        coverage = (
            (len(matched_left) + len(matched_right))
            / max(len(left.chunks) + len(right.chunks), 1)
        )

        result = {
            "left": self._document_payload(left),
            "right": self._document_payload(right),
            "similarities": similarities,
            "differences": differences,
            "similarity_count": len(similarities),
            "difference_count": len(differences),
            "matched_pair_count": len(pairs),
            "coverage": round(min(coverage, 1.0), 3),
            "embedding_provider": self.embedding_service.provider_name,
            "generation_provider": self.llm_provider.provider_name if llm_used else "deterministic",
            "llm_used": llm_used,
            "cache_hit": False,
        }
        self._attach_pdf_previews(result, left, right, cache_key)
        self._write_cache(cache_key, result)
        return result

    def _resolve_source(self, source: dict) -> ComparisonDocument:
        document_id = source.get("document_id")
        upload_token = str(source.get("upload_token") or "").strip()
        if document_id:
            return self._load_database_document(int(document_id))
        if upload_token:
            return self._load_temporary_document(upload_token)
        raise ValueError("Rapor kaynagi secilmedi.")

    def _load_database_document(self, document_id: int) -> ComparisonDocument:
        document = self.session.get(Document, document_id)
        if document is None:
            raise ValueError(f"Belge bulunamadi: {document_id}")

        rows = self.session.execute(
            select(DocumentChunk, ChunkEmbedding.embedding)
            .outerjoin(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_order.asc())
        ).all()
        chunks = []
        for chunk, serialized_vector in rows:
            text = self._clean_chunk_text(chunk.chunk_text)
            if not self._has_useful_content(text):
                continue
            vector = (
                self.embedding_service.deserialize(serialized_vector)
                if serialized_vector
                else self.embedding_service.embed_text(text)
            )
            chunks.append(
                ComparisonChunk(
                    key=f"db-{chunk.id}",
                    page_start=int(chunk.page_start),
                    page_end=int(chunk.page_end),
                    section_title=self._clean_section_title(chunk.section_title),
                    text=text,
                    vector=vector,
                )
            )
        return ComparisonDocument(
            source_ref=f"document:{document.id}",
            title=document.title,
            file_name=document.file_name,
            source_path=Path(document.file_path),
            content_hash=document.file_hash,
            document_id=document.id,
            temporary=False,
            chunks=self._dedupe_chunks(chunks),
        )

    def _load_temporary_document(self, token: str) -> ComparisonDocument:
        if not re.fullmatch(r"[A-Za-z0-9_-]{20,40}", token):
            raise ValueError("Gecici rapor anahtari gecersiz.")
        self._cleanup_temporary_uploads()
        metadata_path = self.temp_dir / f"{token}.json"
        if not metadata_path.exists():
            raise ValueError("Gecici rapor bulunamadi veya suresi doldu.")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        extension = str(metadata.get("extension") or "").lower()
        source_path = self.temp_dir / f"{token}{extension}"
        if extension not in self.SUPPORTED_EXTENSIONS or not source_path.exists():
            raise ValueError("Gecici rapor dosyasi bulunamadi.")

        sections = self._parse_document(source_path, extension)
        cleaned_sections = normalize_sections(sections)
        parsed_chunks = chunk_sections(cleaned_sections)
        chunks = []
        for chunk in parsed_chunks:
            text = self._clean_chunk_text(chunk.chunk_text)
            if not self._has_useful_content(text):
                continue
            chunks.append(
                ComparisonChunk(
                    key=f"temp-{token}-{chunk.chunk_order}",
                    page_start=int(chunk.page_start),
                    page_end=int(chunk.page_end),
                    section_title=self._clean_section_title(chunk.section_title),
                    text=text,
                    vector=self.embedding_service.embed_text(text),
                )
            )
        file_name = str(metadata.get("file_name") or source_path.name)
        return ComparisonDocument(
            source_ref=f"temp:{token}",
            title=Path(file_name).stem,
            file_name=file_name,
            source_path=source_path,
            content_hash=str(metadata.get("content_hash") or self._hash_file(source_path)),
            document_id=None,
            temporary=True,
            chunks=self._dedupe_chunks(chunks),
        )

    @staticmethod
    def _parse_document(source_path: Path, extension: str):
        if extension == ".pdf":
            return parse_pdf(source_path)
        if extension == ".docx":
            return parse_docx(source_path)
        if extension == ".pptx":
            return parse_pptx(source_path)
        raise ValueError(f"Desteklenmeyen dosya turu: {extension}")

    def _align_chunks(
        self,
        left: ComparisonDocument,
        right: ComparisonDocument,
    ) -> list[dict]:
        candidates = []
        for left_chunk in left.chunks:
            for right_chunk in right.chunks:
                semantic_score = max(
                    0.0,
                    self.embedding_service.cosine_similarity(left_chunk.vector, right_chunk.vector),
                )
                lexical_score = self._lexical_similarity(left_chunk.text, right_chunk.text)
                section_score = self._lexical_similarity(
                    left_chunk.section_title or "",
                    right_chunk.section_title or "",
                )
                comparable_signal = self._comparable_signal(left_chunk.text, right_chunk.text)
                combined_score = (
                    semantic_score * 0.62
                    + lexical_score * 0.23
                    + section_score * 0.10
                    + comparable_signal * 0.05
                )
                if lexical_score >= 0.45:
                    combined_score = max(combined_score, 0.45 + lexical_score * 0.35)
                if (
                    combined_score < 0.40
                    and semantic_score < 0.58
                    and lexical_score < 0.18
                    and comparable_signal == 0.0
                ):
                    continue
                candidates.append(
                    {
                        "left": left_chunk,
                        "right": right_chunk,
                        "semantic_score": semantic_score,
                        "lexical_score": lexical_score,
                        "section_score": section_score,
                        "combined_score": combined_score,
                    }
                )

        candidates.sort(
            key=lambda item: (
                item["combined_score"],
                item["semantic_score"],
                item["lexical_score"],
            ),
            reverse=True,
        )
        selected = []
        used_left: set[str] = set()
        used_right: set[str] = set()
        for candidate in candidates:
            if candidate["left"].key in used_left or candidate["right"].key in used_right:
                continue
            if candidate["combined_score"] < 0.42:
                continue
            selected.append(candidate)
            used_left.add(candidate["left"].key)
            used_right.add(candidate["right"].key)
            if len(selected) >= self.MAX_MATCHED_PAIRS:
                break

        for index, candidate in enumerate(selected, start=1):
            candidate["pair_id"] = f"pair-{index}"
        return selected

    def _build_pair_results(
        self,
        left_document: ComparisonDocument,
        right_document: ComparisonDocument,
        pairs: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        similarities: list[dict] = []
        differences: list[dict] = []
        for pair in pairs:
            left_chunk = pair["left"]
            right_chunk = pair["right"]
            topic = self._topic_for_pair(left_chunk, right_chunk)
            left_source = self._source_payload(left_document, left_chunk, right_chunk.text)
            right_source = self._source_payload(right_document, right_chunk, left_chunk.text)
            confidence = round(min(max(pair["combined_score"], 0.0), 1.0), 3)

            if (
                pair["semantic_score"] >= 0.66
                or pair["lexical_score"] >= 0.22
                or pair["combined_score"] >= 0.58
                or (
                    pair["combined_score"] >= 0.46
                    and pair["semantic_score"] >= 0.60
                    and pair["lexical_score"] >= 0.12
                )
            ):
                similarities.append(
                    {
                        "id": f"{pair['pair_id']}-similarity",
                        "pair_id": pair["pair_id"],
                        "kind": "similarity",
                        "difference_type": None,
                        "topic": topic,
                        "summary": self._similarity_summary(left_chunk.text, right_chunk.text),
                        "left": left_source,
                        "right": right_source,
                        "semantic_score": round(pair["semantic_score"], 3),
                        "lexical_score": round(pair["lexical_score"], 3),
                        "confidence": confidence,
                    }
                )

            difference = self._deterministic_difference(left_chunk.text, right_chunk.text)
            if difference:
                differences.append(
                    {
                        "id": f"{pair['pair_id']}-difference",
                        "pair_id": pair["pair_id"],
                        "kind": "difference",
                        "difference_type": difference["type"],
                        "topic": topic,
                        "summary": difference["summary"],
                        "left": left_source,
                        "right": right_source,
                        "semantic_score": round(pair["semantic_score"], 3),
                        "lexical_score": round(pair["lexical_score"], 3),
                        "confidence": max(confidence, 0.82),
                    }
                )
        return similarities, differences

    def _unmatched_results(
        self,
        left_document: ComparisonDocument,
        right_document: ComparisonDocument,
        pairs: list[dict],
    ) -> list[dict]:
        matched_left = {pair["left"].key for pair in pairs}
        matched_right = {pair["right"].key for pair in pairs}
        results = []
        for side, document, other_document, matched_keys in (
            ("left", left_document, right_document, matched_left),
            ("right", right_document, left_document, matched_right),
        ):
            candidates = [
                chunk
                for chunk in document.chunks
                if chunk.key not in matched_keys and self._chunk_importance(chunk) >= 2.0
            ]
            candidates.sort(key=self._chunk_importance, reverse=True)
            for index, chunk in enumerate(candidates[:4], start=1):
                source = self._source_payload(document, chunk, "")
                empty_source = self._empty_source_payload(other_document)
                results.append(
                    {
                        "id": f"only-{side}-{index}-{chunk.key}",
                        "pair_id": None,
                        "kind": "difference",
                        "difference_type": f"only_{side}",
                        "topic": chunk.section_title or "Yalniz bir raporda bulunan bulgu",
                        "summary": (
                            "Bu teknik bulgu yalnizca Rapor A'da bulundu."
                            if side == "left"
                            else "Bu teknik bulgu yalnizca Rapor B'de bulundu."
                        ),
                        "left": source if side == "left" else empty_source,
                        "right": source if side == "right" else empty_source,
                        "semantic_score": 0.0,
                        "lexical_score": 0.0,
                        "confidence": 0.72,
                    }
                )
        return results

    def _refine_with_llm(
        self,
        left_document: ComparisonDocument,
        right_document: ComparisonDocument,
        pairs: list[dict],
        similarities: list[dict],
        differences: list[dict],
    ) -> tuple[list[dict], list[dict], bool]:
        prompt_pairs = []
        for pair in pairs[:8]:
            prompt_pairs.append(
                {
                    "id": pair["pair_id"],
                    "a": pair["left"].text[:900],
                    "b": pair["right"].text[:900],
                }
            )
        prompt = f"""Sen iki teknik rapordaki eslestirilmis metinleri siniflandiriyorsun.
Yalnizca verilen metinlere dayan. Turkce ve kisa yaz.
Her eslesme icin iliskiyi su degerlerden biriyle ver:
same, partial, different, contradiction, unrelated.
"similarity" ortak teknik noktayi; "difference" gercek farki anlatsin.
Fark yoksa difference bos, ortak nokta yoksa similarity bos olsun.
Metinde bulunmayan sayi, birim, sonuc veya yorum ekleme.
Butun eslesme ID'lerini birer kez dondur: {", ".join(pair["id"] for pair in prompt_pairs)}.
"kisa konu", "kisa ortak nokta" gibi sablon ifadeleri kesinlikle kullanma.

Rapor A: {left_document.title}
Rapor B: {right_document.title}

Eslesmeler:
{json.dumps(prompt_pairs, ensure_ascii=False)}

Yalnizca su JSON seklinde cevap ver:
{{"items":[{{"id":"pair-1","relation":"same","topic":"","similarity":"","difference":""}}]}}"""
        try:
            raw_answer = self.llm_provider.generate(prompt, max_tokens=900, temperature=0.0)
            payload = json.loads(self._extract_json_object(raw_answer))
        except Exception:
            logger.exception("Report comparison LLM refinement failed.")
            return similarities, differences, False

        pair_map = {pair["pair_id"]: pair for pair in pairs}
        similarity_map = {item.get("pair_id"): item for item in similarities if item.get("pair_id")}
        difference_map = {item.get("pair_id"): item for item in differences if item.get("pair_id")}
        refined_count = 0
        for item in payload.get("items", []):
            pair_id = str(item.get("id") or "")
            pair = pair_map.get(pair_id)
            if pair is None:
                continue
            relation = str(item.get("relation") or "").strip().lower()
            if relation not in {"same", "partial", "different", "contradiction", "unrelated"}:
                continue
            source_text = f"{pair['left'].text} {pair['right'].text}"
            topic = self._safe_llm_text(item.get("topic"), source_text, allow_short=True)
            similarity_text = self._safe_llm_text(item.get("similarity"), source_text)
            difference_text = self._safe_llm_text(item.get("difference"), source_text)

            similarity_item = similarity_map.get(pair_id)
            if relation == "unrelated" and similarity_item:
                similarities = [row for row in similarities if row.get("pair_id") != pair_id]
                similarity_map.pop(pair_id, None)
                continue
            if similarity_item and topic:
                similarity_item["topic"] = topic
                refined_count += 1
            if similarity_item and similarity_text and relation != "unrelated":
                similarity_item["summary"] = similarity_text
                refined_count += 1
            if (
                similarity_item is None
                and similarity_text
                and relation in {"same", "partial", "different"}
            ):
                similarity_item = {
                    "id": f"{pair_id}-llm-similarity",
                    "pair_id": pair_id,
                    "kind": "similarity",
                    "difference_type": None,
                    "topic": topic or self._topic_for_pair(pair["left"], pair["right"]),
                    "summary": similarity_text,
                    "left": self._source_payload(left_document, pair["left"], pair["right"].text),
                    "right": self._source_payload(right_document, pair["right"], pair["left"].text),
                    "semantic_score": round(pair["semantic_score"], 3),
                    "lexical_score": round(pair["lexical_score"], 3),
                    "confidence": round(min(max(pair["combined_score"], 0.64), 0.90), 3),
                }
                similarities.append(similarity_item)
                similarity_map[pair_id] = similarity_item
                refined_count += 1

            difference_item = difference_map.get(pair_id)
            if difference_item and topic:
                difference_item["topic"] = topic
                refined_count += 1
            if difference_item and difference_text:
                difference_item["summary"] = difference_text
                refined_count += 1
                continue
            if relation not in {"partial", "different", "contradiction"} or not difference_text:
                continue

            left_source = self._source_payload(left_document, pair["left"], pair["right"].text)
            right_source = self._source_payload(right_document, pair["right"], pair["left"].text)
            new_item = {
                "id": f"{pair_id}-llm-difference",
                "pair_id": pair_id,
                "kind": "difference",
                "difference_type": "contradiction" if relation == "contradiction" else "content_change",
                "topic": topic or self._topic_for_pair(pair["left"], pair["right"]),
                "summary": difference_text,
                "left": left_source,
                "right": right_source,
                "semantic_score": round(pair["semantic_score"], 3),
                "lexical_score": round(pair["lexical_score"], 3),
                "confidence": round(min(max(pair["combined_score"], 0.68), 0.92), 3),
            }
            differences.append(new_item)
            difference_map[pair_id] = new_item
            refined_count += 1
        return similarities, differences, refined_count > 0

    def _source_payload(
        self,
        document: ComparisonDocument,
        chunk: ComparisonChunk,
        other_text: str,
    ) -> dict:
        return {
            "source_ref": document.source_ref,
            "document_id": document.document_id,
            "document_title": document.title,
            "file_name": document.file_name,
            "temporary": document.temporary,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "section_title": chunk.section_title,
            "excerpt": self._best_excerpt(chunk.text, other_text),
        }

    @staticmethod
    def _empty_source_payload(document: ComparisonDocument) -> dict:
        return {
            "source_ref": document.source_ref,
            "document_id": document.document_id,
            "document_title": document.title,
            "file_name": document.file_name,
            "temporary": document.temporary,
            "page_start": None,
            "page_end": None,
            "section_title": None,
            "excerpt": "Bu raporda eslesen bir bulgu bulunamadi.",
        }

    @staticmethod
    def _document_payload(document: ComparisonDocument) -> dict:
        return {
            "source_ref": document.source_ref,
            "document_id": document.document_id,
            "title": document.title,
            "file_name": document.file_name,
            "temporary": document.temporary,
            "chunk_count": len(document.chunks),
        }

    def _assign_highlight_metadata(
        self,
        similarities: list[dict],
        differences: list[dict],
    ) -> None:
        pair_styles: dict[str, tuple[int, str]] = {}
        for item in similarities + differences:
            left = item.get("left") or {}
            right = item.get("right") or {}
            if not left.get("page_start") or not right.get("page_start"):
                item["highlight_number"] = None
                item["highlight_color"] = None
                continue
            pair_key = str(item.get("pair_id") or item.get("id") or "")
            if pair_key not in pair_styles:
                number = len(pair_styles) + 1
                color = self.HIGHLIGHT_PALETTE[(number - 1) % len(self.HIGHLIGHT_PALETTE)]
                pair_styles[pair_key] = (number, color)
            number, color = pair_styles[pair_key]
            item["highlight_number"] = number
            item["highlight_color"] = color

    def _attach_pdf_previews(
        self,
        result: dict,
        left: ComparisonDocument,
        right: ComparisonDocument,
        comparison_id: str,
    ) -> None:
        result["comparison_id"] = comparison_id
        for side, document in (("left", left), ("right", right)):
            preview_key = f"{side}_pdf"
            target_path = self.pdf_preview_dir / f"{comparison_id}-{side}.pdf"
            existing = result.get(preview_key) or {}
            if existing.get("available") and target_path.exists():
                existing["url"] = f"/report-comparison/{comparison_id}/pdf/{side}"
                result[preview_key] = existing
                continue

            preview = {
                "available": False,
                "url": None,
                "file_name": document.file_name,
                "highlighted_passages": 0,
                "reason": None,
            }
            if document.source_path.suffix.lower() != ".pdf":
                preview["reason"] = "Bu kaynak PDF olmadigi icin renkli onizleme olusturulmadi."
                result[preview_key] = preview
                continue
            if not document.source_path.exists():
                preview["reason"] = "PDF dosyasi bulunamadi."
                result[preview_key] = preview
                continue

            requests = self._pdf_highlight_requests(result, side)
            try:
                build_result = PdfHighlightService().build(
                    document.source_path,
                    target_path,
                    requests,
                )
            except Exception:
                logger.exception("Comparison PDF highlights could not be generated for %s.", side)
                preview["reason"] = "PDF isaretlemeleri olusturulamadi."
                result[preview_key] = preview
                continue

            for item in (result.get("similarities") or []) + (result.get("differences") or []):
                page = build_result.page_by_key.get(f"{item.get('id')}:{side}")
                if page:
                    evidence = item.get(side) or {}
                    evidence["highlight_page"] = page
            preview.update(
                {
                    "available": True,
                    "url": f"/report-comparison/{comparison_id}/pdf/{side}",
                    "highlighted_passages": build_result.highlighted_passages,
                    "reason": (
                        None
                        if build_result.highlighted_passages
                        else "PDF acildi ancak eslesen metnin koordinati bulunamadi."
                    ),
                }
            )
            result[preview_key] = preview

    @staticmethod
    def _pdf_highlight_requests(result: dict, side: str) -> list[PdfHighlightRequest]:
        requests = []
        for item in (result.get("similarities") or []) + (result.get("differences") or []):
            color = str(item.get("highlight_color") or "")
            number = item.get("highlight_number")
            evidence = item.get(side) or {}
            if not color or not number or not evidence.get("page_start"):
                continue
            requests.append(
                PdfHighlightRequest(
                    key=f"{item.get('id')}:{side}",
                    page_start=int(evidence["page_start"]),
                    page_end=int(evidence.get("page_end") or evidence["page_start"]),
                    excerpt=str(evidence.get("excerpt") or ""),
                    color=color,
                    label=f"Eslesme {number}: {item.get('topic') or 'Teknik bulgu'}",
                )
            )
        return requests

    def _deterministic_difference(self, left_text: str, right_text: str) -> dict | None:
        lexical_score = self._lexical_similarity(left_text, right_text)
        left_status = self._status_polarities(left_text)
        right_status = self._status_polarities(right_text)
        if left_status and right_status and left_status != right_status and lexical_score >= 0.25:
            return {
                "type": "result_change",
                "summary": (
                    f"Sonuc durumu degisiyor: Rapor A {self._status_label(left_status)}, "
                    f"Rapor B {self._status_label(right_status)}."
                ),
            }

        left_values = self._numeric_values(left_text)
        right_values = self._numeric_values(right_text)
        if lexical_score >= 0.25:
            for unit in sorted(set(left_values) & set(right_values)):
                left_numbers = left_values[unit]
                right_numbers = right_values[unit]
                if left_numbers != right_numbers:
                    return {
                        "type": "value_change",
                        "summary": (
                            f"Ayni teknik baglamdaki {unit} degerleri farkli: "
                            f"Rapor A {self._format_values(left_numbers, unit)}, "
                            f"Rapor B {self._format_values(right_numbers, unit)}."
                        ),
                    }

        left_negative = self._has_negative_direction(left_text)
        right_negative = self._has_negative_direction(right_text)
        if left_negative != right_negative and lexical_score >= 0.30:
            return {
                "type": "contradiction",
                "summary": "Ayni teknik konu icin olumlu ve olumsuz ifadeler farklilik gosteriyor.",
            }
        return None

    def _similarity_summary(self, left_text: str, right_text: str) -> str:
        left_status = self._status_polarities(left_text)
        right_status = self._status_polarities(right_text)
        if left_status and left_status == right_status:
            return f"Her iki rapor da bu teknik konu icin {self._status_label(left_status)} sonuc bildiriyor."
        left_values = self._numeric_values(left_text)
        right_values = self._numeric_values(right_text)
        for unit in sorted(set(left_values) & set(right_values)):
            common_values = left_values[unit] & right_values[unit]
            if common_values:
                return (
                    f"Her iki raporda da {self._format_values(common_values, unit)} "
                    "degeri ayni teknik baglamda yer aliyor."
                )
        return "Iki rapor ayni teknik konuyu benzer kapsam veya yontemle ele aliyor."

    def _topic_for_pair(self, left: ComparisonChunk, right: ComparisonChunk) -> str:
        left_section = " ".join((left.section_title or "").split())
        right_section = " ".join((right.section_title or "").split())
        if left_section and right_section:
            if self._lexical_similarity(left_section, right_section) >= 0.45:
                return left_section[:120]
        if left_section:
            return left_section[:120]
        if right_section:
            return right_section[:120]
        common = self._tokens(left.text) & self._tokens(right.text)
        technical = sorted(common & self.TECHNICAL_TERMS)
        ranked = technical + sorted(common - set(technical), key=lambda token: (-len(token), token))
        return " / ".join(ranked[:3])[:120] or "Ortak teknik konu"

    def _best_excerpt(self, text: str, other_text: str) -> str:
        sentences = [
            " ".join(item.split()).strip(" -;:")
            for item in re.split(r"(?<=[.!?])\s+|\n+", text)
            if len(item.split()) >= 4
        ]
        if not sentences:
            return text[:420].strip()
        other_tokens = self._tokens(other_text)
        best = max(
            sentences,
            key=lambda item: (
                len(self._tokens(item) & other_tokens),
                len(self._numeric_values(item)),
                min(len(item), 420),
            ),
        )
        return best[:420].strip()

    def _lexical_similarity(self, left: str, right: str) -> float:
        left_tokens = self._tokens(left)
        right_tokens = self._tokens(right)
        if not left_tokens or not right_tokens:
            return 0.0
        intersection = left_tokens & right_tokens
        denominator = max((len(left_tokens) * len(right_tokens)) ** 0.5, 1.0)
        return min(len(intersection) / denominator, 1.0)

    def _comparable_signal(self, left_text: str, right_text: str) -> float:
        left_values = self._numeric_values(left_text)
        right_values = self._numeric_values(right_text)
        if set(left_values) & set(right_values):
            return 1.0
        left_status = self._status_polarities(left_text)
        right_status = self._status_polarities(right_text)
        return 1.0 if left_status and right_status else 0.0

    @classmethod
    def _numeric_values(cls, text: str) -> dict[str, set[float]]:
        values: dict[str, set[float]] = {}
        pattern = (
            r"(?<![\w.])(-?\d+(?:[.,]\d+)?)\s*"
            r"(MPa|kPa|Pa|kN|N\.m|Nm|mm|cm|Hz|kg|°C|N|m|g|C|%)"
            r"(?=\s|[.,;:)\]]|$)"
        )
        for raw_value, raw_unit in re.findall(pattern, text, flags=re.IGNORECASE):
            try:
                value = round(float(raw_value.replace(",", ".")), 6)
            except ValueError:
                continue
            unit = cls.UNIT_ALIASES.get(raw_unit.casefold(), raw_unit)
            values.setdefault(unit, set()).add(value)
        return values

    @classmethod
    def _status_polarities(cls, text: str) -> set[str]:
        normalized = cls._normalize_text(text)
        statuses: set[str] = set()
        for status in cls.NEGATIVE_STATUS:
            if re.search(rf"\b{re.escape(status)}\b", normalized):
                statuses.add("NOK")
        positive_text = normalized
        for status in cls.NEGATIVE_STATUS:
            positive_text = re.sub(rf"\b{re.escape(status)}\b", " ", positive_text)
        for status in cls.POSITIVE_STATUS:
            if re.search(rf"\b{re.escape(status)}\b", positive_text):
                statuses.add("OK")
        return statuses

    @staticmethod
    def _status_label(statuses: set[str]) -> str:
        return "/".join(sorted(statuses))

    @classmethod
    def _has_negative_direction(cls, text: str) -> bool:
        normalized = cls._normalize_text(text)
        return any(
            term in normalized
            for term in ("degil", "asildi", "basarisiz", "emniyetsiz", "gecmedi", "nok", "yetersiz")
        )

    @staticmethod
    def _format_values(values: set[float], unit: str) -> str:
        formatted = []
        for value in sorted(values)[:4]:
            text = f"{value:.6f}".rstrip("0").rstrip(".")
            formatted.append(f"{text} {unit}")
        return ", ".join(formatted)

    @classmethod
    def _tokens(cls, text: str) -> set[str]:
        normalized = cls._normalize_text(text)
        return {
            token
            for token in re.findall(r"[a-z0-9]+", normalized)
            if len(token) >= 3 and token not in cls.STOP_WORDS
        }

    @classmethod
    def _normalize_text(cls, text: str) -> str:
        translated = str(text or "").casefold().translate(
            str.maketrans(
                {
                    "\u0131": "i",
                    "\u011f": "g",
                    "\u00fc": "u",
                    "\u015f": "s",
                    "\u00f6": "o",
                    "\u00e7": "c",
                    "\u0130": "i",
                }
            )
        )
        normalized = unicodedata.normalize("NFKD", translated)
        return "".join(char for char in normalized if not unicodedata.combining(char))

    @classmethod
    def _clean_chunk_text(cls, text: str) -> str:
        cleaned = str(text or "").replace("\x00", " ")
        cleaned = re.sub(
            r"ANAL[\u0130I]Z\s+DOSYASI\s+ORTAK\s+ALAN\s+L[\u0130I]NK[\u0130I]\s*:\s*",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"[A-Za-z]:\\.*?(?=(?:Page|Sayfa)\s+\d+|$)",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\b(?:Page|Sayfa)\s+\d+\s*/\s*\d+\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @classmethod
    def _has_useful_content(cls, text: str) -> bool:
        tokens = cls._tokens(text)
        if len(tokens) < 5:
            return False
        normalized = cls._normalize_text(text)
        if any(
            term in normalized
            for term in (
                "sekerpinar mahallesi",
                "otomotiv caddesi",
                "www anadoluisuzu",
                "anadoluisuzu isuzutr",
            )
        ):
            return False
        cover_hits = sum(
            term in normalized
            for term in (
                "development statement",
                "hazirlayan",
                "kontrol",
                "onaylayan",
                "rapor no",
                "talep eden",
                "tarih",
            )
        )
        technical_hits = sum(term in normalized for term in cls.TECHNICAL_TERMS)
        if cover_hits >= 3 and technical_hits == 0:
            return False
        return True

    @classmethod
    def _clean_section_title(cls, value: str | None) -> str | None:
        title = " ".join(str(value or "").split()).strip(" -:")
        if not title:
            return None
        normalized = cls._normalize_text(title)
        searchable = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
        if len(title) > 90 or any(
            term in searchable
            for term in (
                "analiz dosyasi ortak alan",
                "development statement",
                "genel public",
                "validasyon mudurlugu",
                "yapisal ve akustik sistemler analiz birimi",
            )
        ):
            return None
        return title[:120]

    def _dedupe_chunks(self, chunks: list[ComparisonChunk]) -> list[ComparisonChunk]:
        deduped = []
        seen: set[str] = set()
        for chunk in chunks:
            fingerprint = self._normalize_text(chunk.text)[:300]
            if not fingerprint or fingerprint in seen:
                continue
            seen.add(fingerprint)
            deduped.append(chunk)
            if len(deduped) >= self.MAX_CHUNKS_PER_DOCUMENT:
                break
        return deduped

    def _chunk_importance(self, chunk: ComparisonChunk) -> float:
        normalized = self._normalize_text(f"{chunk.section_title or ''} {chunk.text}")
        score = min(len(self._tokens(chunk.text)) / 30.0, 2.0)
        score += len(self._numeric_values(chunk.text)) * 0.8
        if self._status_polarities(chunk.text):
            score += 1.4
        score += sum(0.4 for term in self.TECHNICAL_TERMS if term in normalized)
        return score

    def _safe_llm_text(self, value: Any, source_text: str, allow_short: bool = False) -> str:
        text = " ".join(str(value or "").split()).strip()
        minimum = 3 if allow_short else 12
        if len(text) < minimum or len(text) > 320:
            return ""
        normalized = self._normalize_text(text)
        if normalized in {
            "kisa konu",
            "kisa ortak nokta",
            "kisa fark",
            "ortak nokta",
            "konu",
            "fark",
        }:
            return ""
        if not (self._tokens(text) & self._tokens(source_text)):
            return ""
        source_numbers = {
            item.replace(",", ".")
            for item in re.findall(r"-?\d+(?:[.,]\d+)?", source_text)
        }
        generated_numbers = {
            item.replace(",", ".")
            for item in re.findall(r"-?\d+(?:[.,]\d+)?", text)
        }
        if not generated_numbers.issubset(source_numbers):
            return ""
        return text

    @staticmethod
    def _extract_json_object(value: str) -> str:
        stripped = value.strip()
        start = stripped.find("{")
        end = stripped.rfind("}")
        return stripped[start : end + 1] if start >= 0 and end > start else stripped

    @staticmethod
    def _dedupe_results(items: list[dict]) -> list[dict]:
        deduped = []
        seen: set[tuple[str, str, str]] = set()
        for item in sorted(items, key=lambda row: row.get("confidence", 0.0), reverse=True):
            key = (
                str(item.get("difference_type") or item.get("kind") or ""),
                str(item.get("left", {}).get("excerpt") or "")[:160],
                str(item.get("right", {}).get("excerpt") or "")[:160],
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _cache_key(
        self,
        left: ComparisonDocument,
        right: ComparisonDocument,
        *,
        use_llm: bool,
    ) -> str:
        raw = "|".join(
            (
                self.ALGORITHM_VERSION,
                left.content_hash,
                right.content_hash,
                self.embedding_service.provider_name,
                self.llm_provider.provider_name if use_llm else "no-llm",
            )
        )
        return sha256(raw.encode("utf-8")).hexdigest()

    def _read_cache(self, cache_key: str, require_llm: bool) -> dict | None:
        cache_path = self.cache_dir / f"{cache_key}.json"
        if not cache_path.exists():
            return None
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if require_llm and not payload.get("llm_used"):
            return None
        return payload

    def _write_cache(self, cache_key: str, payload: dict) -> None:
        try:
            (self.cache_dir / f"{cache_key}.json").write_text(
                json.dumps(payload, ensure_ascii=True),
                encoding="utf-8",
            )
        except OSError:
            logger.exception("Report comparison cache could not be written.")

    def _cleanup_temporary_uploads(self) -> None:
        cutoff = time.time() - self.TEMP_UPLOAD_TTL_SECONDS
        for metadata_path in self.temp_dir.glob("*.json"):
            try:
                if metadata_path.stat().st_mtime >= cutoff:
                    continue
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                token = str(metadata.get("token") or "")
                extension = str(metadata.get("extension") or "")
                if re.fullmatch(r"[A-Za-z0-9_-]{20,40}", token) and extension in self.SUPPORTED_EXTENSIONS:
                    (self.temp_dir / f"{token}{extension}").unlink(missing_ok=True)
                metadata_path.unlink(missing_ok=True)
            except (OSError, json.JSONDecodeError):
                logger.exception("Expired comparison upload could not be cleaned.")

    @staticmethod
    def _hash_file(source_path: Path) -> str:
        digest = sha256()
        with source_path.open("rb") as file_obj:
            for block in iter(lambda: file_obj.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()


def resolve_comparison_pdf_path(comparison_id: str, side: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", comparison_id):
        raise ValueError("Karsilastirma kimligi gecersiz.")
    if side not in {"left", "right"}:
        raise ValueError("PDF tarafi gecersiz.")
    preview_dir = DATA_DIR / "comparison_cache" / "pdf"
    target = preview_dir / f"{comparison_id}-{side}.pdf"
    if not target.exists() or target.parent.resolve() != preview_dir.resolve():
        raise ValueError("Isaretli PDF bulunamadi.")
    return target


@lru_cache(maxsize=1)
def _build_report_comparison_provider() -> LLMProvider:
    if not CHAT_LLM_ENABLED or CHAT_LLM_BACKEND in {"", "disabled", "none"}:
        return DisabledLLMProvider()
    if CHAT_LLM_BACKEND == "ollama":
        try:
            return OllamaLLMProvider(
                model_name=CHAT_LLM_MODEL_NAME,
                timeout_seconds=CHAT_LLM_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.exception("Report comparison Ollama provider could not load.")
            return DisabledLLMProvider()
    logger.warning("Unsupported CHAT_LLM_BACKEND=%s; report comparison LLM disabled.", CHAT_LLM_BACKEND)
    return DisabledLLMProvider()
