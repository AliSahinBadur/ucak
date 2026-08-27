from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Document, DocumentPage
from .llm_provider import LLMProvider


@dataclass(frozen=True, slots=True)
class CaptionOccurrence:
    kind: str
    label: str
    number_text: str
    number_parts: tuple[int, ...]
    title: str
    page_number: int
    raw_line: str


class ReportQualityService:
    CAPTION_PATTERN = re.compile(
        r"^\s*(tablo|table|sekil|\u015fekil|figure|resim)\s*"
        r"(?:no\.?|numara)?\s*[-\u2013\u2014:]?\s*"
        r"(\d+(?:\.\d+)*)\s*([-\u2013\u2014:.]?\s*)(.*)$",
        flags=re.IGNORECASE,
    )
    REFERENCE_SUFFIX_PATTERN = re.compile(r"^[\u2019']?(?:de|da|te|ta|den|dan)\b", flags=re.IGNORECASE)
    KIND_LABELS = {
        "table": "Tablolar",
        "figure": "Sekiller",
        "image": "Resimler",
    }

    def __init__(self, session: Session) -> None:
        self.session = session

    def answer_question(
        self,
        question: str,
        document_ids: list[int],
        *,
        llm_provider: LLMProvider | None = None,
    ) -> dict:
        if not self._is_caption_sequence_question(question):
            from .report_review_service import ReportReviewService

            review_service = ReportReviewService(self.session, llm_provider=llm_provider)
            if len(document_ids) == 2 and review_service.is_revision_comparison_question(question):
                return review_service.answer_revision_comparison(question, document_ids)
            return review_service.answer_question(question, document_ids)

        documents = self._load_documents(document_ids)
        if not documents:
            return self._empty_response(question, "Kalite kontrolu icin rapor belirlenemedi.")

        requested_kinds = self._requested_kinds(question)
        answer_blocks: list[str] = []
        sources: list[dict] = []
        analyzed_count = 0

        for document in documents[:4]:
            pages = self.session.scalars(
                select(DocumentPage)
                .where(DocumentPage.document_id == document.id)
                .order_by(DocumentPage.page_number.asc())
            ).all()
            occurrences = self.extract_captions(pages)
            selected = [item for item in occurrences if item.kind in requested_kinds]
            block, document_sources, analyzed = self._document_answer(document, selected, requested_kinds)
            answer_blocks.append(block)
            sources.extend(document_sources)
            analyzed_count += int(analyzed)

        if not analyzed_count:
            return {
                "question": question,
                "mode": "keyword",
                "answer": "\n\n".join(answer_blocks),
                "answer_found": False,
                "confidence": 0.0,
                "embedding_provider": "document-quality:rules",
                "sources": [],
            }

        return {
            "question": question,
            "mode": "keyword",
            "answer": "\n\n".join(answer_blocks),
            "answer_found": True,
            "confidence": 1.0,
            "embedding_provider": "document-quality:rules",
            "sources": sources[:8],
        }

    def analyze_documents(self, document_ids: list[int], profile: str = "auto") -> dict:
        from .report_review_service import ReportReviewService

        return ReportReviewService(self.session).analyze_documents(document_ids, profile=profile)

    @classmethod
    def extract_captions(cls, pages: list[DocumentPage]) -> list[CaptionOccurrence]:
        occurrences: list[CaptionOccurrence] = []
        for page in pages:
            text = page.raw_text or page.clean_text or ""
            for raw_line in text.splitlines():
                line = " ".join(raw_line.split()).strip()
                match = cls.CAPTION_PATTERN.match(line)
                if not match:
                    continue
                trailing_text = match.group(4).strip()
                if cls.REFERENCE_SUFFIX_PATTERN.match(trailing_text):
                    continue
                number_text = match.group(2)
                occurrences.append(
                    CaptionOccurrence(
                        kind=cls._caption_kind(match.group(1)),
                        label=match.group(1),
                        number_text=number_text,
                        number_parts=tuple(int(part) for part in number_text.split(".")),
                        title=trailing_text.strip(" -\u2013\u2014:.")[:240],
                        page_number=int(page.page_number),
                        raw_line=line[:500],
                    )
                )
        return occurrences

    def _document_answer(
        self,
        document: Document,
        occurrences: list[CaptionOccurrence],
        requested_kinds: tuple[str, ...],
    ) -> tuple[str, list[dict], bool]:
        by_kind = {kind: [item for item in occurrences if item.kind == kind] for kind in requested_kinds}
        available_kinds = [kind for kind in requested_kinds if by_kind[kind]]
        if not available_kinds:
            labels = "/".join(self.KIND_LABELS[kind].lower() for kind in requested_kinds)
            return (
                f"{document.title}: Secilebilir veya OCR metninde {labels} icin numarali baslik bulunamadi; "
                "bu nedenle sira dogrulanamadi.",
                [],
                False,
            )

        lines: list[str] = []
        all_valid = True
        for kind in available_kinds:
            result = self._sequence_result(by_kind[kind])
            all_valid = all_valid and result["valid"]
            lines.append(self._format_sequence_line(kind, result))

        requested_label = " ve ".join(self.KIND_LABELS[kind].lower() for kind in available_kinds)
        if all_valid:
            headline = f"{document.title} raporunda {requested_label} numaralandirmasi dogru gorunuyor."
        else:
            headline = f"{document.title} raporunda {requested_label} numaralandirmasinda sorun bulundu."

        note = (
            "Bu kontrol numara sirasi, eksik ve tekrar denetimidir; basligin gorsel icerigi dogru tarif edip "
            "etmedigi ayrica gorsel inceleme gerektirir."
        )
        sources = [self._source_for_kind(document, kind, by_kind[kind]) for kind in available_kinds]
        return "\n".join([headline, *lines, note]), sources, True

    @staticmethod
    def _sequence_result(occurrences: list[CaptionOccurrence]) -> dict:
        number_texts = [item.number_text for item in occurrences]
        counts = Counter(number_texts)
        duplicates = [number for number, count in counts.items() if count > 1]
        number_parts = [item.number_parts for item in occurrences]
        out_of_order = number_parts != sorted(number_parts)
        simple_numbers = [parts[0] for parts in number_parts if len(parts) == 1]
        hierarchical = len(simple_numbers) != len(number_parts)
        missing: list[str] = []
        if simple_numbers and not hierarchical:
            existing = set(simple_numbers)
            missing = [str(number) for number in range(1, max(simple_numbers) + 1) if number not in existing]

        return {
            "numbers": number_texts,
            "duplicates": sorted(duplicates, key=lambda value: tuple(int(part) for part in value.split("."))),
            "missing": missing,
            "out_of_order": out_of_order,
            "hierarchical": hierarchical,
            "valid": not duplicates and not missing and not out_of_order,
        }

    def _format_sequence_line(self, kind: str, result: dict) -> str:
        numbers = ", ".join(result["numbers"])
        label = self.KIND_LABELS[kind]
        issues: list[str] = []
        if result["duplicates"]:
            issues.append("tekrar eden: " + ", ".join(result["duplicates"]))
        if result["missing"]:
            issues.append("eksik: " + ", ".join(result["missing"]))
        if result["out_of_order"]:
            issues.append("gecis sirasi bozuk")
        if issues:
            return f"- {label}: {numbers}. Sorun: {'; '.join(issues)}."
        if result["hierarchical"]:
            return f"- {label}: {numbers}. Tekrar veya geriye giden numara yok."
        return f"- {label}: {numbers}. Eksik, tekrar veya sira bozuklugu yok."

    @staticmethod
    def _source_for_kind(document: Document, kind: str, occurrences: list[CaptionOccurrence]) -> dict:
        page_numbers = [item.page_number for item in occurrences]
        return {
            "document_id": int(document.id),
            "document_title": document.title,
            "file_name": document.file_name,
            "page_start": min(page_numbers),
            "page_end": max(page_numbers),
            "section_title": ReportQualityService.KIND_LABELS[kind] + " numaralandirmasi",
            "chunk_text": "\n".join(
                f"Sayfa {item.page_number}: {item.raw_line}" for item in occurrences
            )[:6000],
            "match_type": "keyword",
            "keyword_score": 1.0,
            "semantic_score": 0.0,
            "combined_score": 1.0,
        }

    def _load_documents(self, document_ids: list[int]) -> list[Document]:
        if not document_ids:
            return []
        rows = self.session.scalars(select(Document).where(Document.id.in_(document_ids))).all()
        rows_by_id = {int(document.id): document for document in rows}
        return [rows_by_id[document_id] for document_id in document_ids if document_id in rows_by_id]

    @classmethod
    def _requested_kinds(cls, question: str) -> tuple[str, ...]:
        normalized = cls._normalize_text(question)
        wants_tables = any(term in normalized for term in ("tablo", "table"))
        wants_figures = any(term in normalized for term in ("sekil", "figure"))
        wants_images = "resim" in normalized
        selected: list[str] = []
        if wants_tables:
            selected.append("table")
        if wants_figures:
            selected.append("figure")
        if wants_images:
            if "figure" not in selected:
                selected.append("figure")
            selected.append("image")
        return tuple(selected or ("table", "figure", "image"))

    @classmethod
    def _is_caption_sequence_question(cls, question: str) -> bool:
        normalized = cls._normalize_text(question)
        subject = any(term in normalized for term in ("tablo", "sekil", "resim", "figure", "table"))
        action = any(
            term in normalized
            for term in (
                "isimlendirme",
                "adlandirma",
                "numaralandirma",
                "numaralari dogru",
                "sirali mi",
                "sirayla mi",
                "sira dogru",
                "eksik numara",
                "tekrar eden",
            )
        )
        return subject and action

    @staticmethod
    def _caption_kind(label: str) -> str:
        normalized = ReportQualityService._normalize_text(label)
        if normalized in {"tablo", "table"}:
            return "table"
        if normalized == "resim":
            return "image"
        return "figure"

    @staticmethod
    def _normalize_text(text: str) -> str:
        return str(text or "").casefold().translate(
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

    @staticmethod
    def _empty_response(question: str, answer: str) -> dict:
        return {
            "question": question,
            "mode": "keyword",
            "answer": answer,
            "answer_found": False,
            "confidence": 0.0,
            "embedding_provider": "document-quality:rules",
            "sources": [],
        }
