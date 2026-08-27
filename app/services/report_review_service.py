from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..db.models import CatalogDocumentLink, Document, DocumentPage, ReportCatalogEntry
from .document_path_service import resolve_document_file_path
from .llm_provider import DisabledLLMProvider, LLMProvider
from .pdf_highlight_service import PdfHighlightRequest, PdfHighlightService
from .report_quality_service import CaptionOccurrence, ReportQualityService


@dataclass(frozen=True, slots=True)
class ReportFinding:
    document_id: int
    document_title: str
    file_name: str
    rule_id: str
    category: str
    severity: str
    status: str
    message: str
    evidence: tuple[str, ...]
    page_start: int | None
    page_end: int | None
    suggested_fix: str
    engine: str = "rules"

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "document_title": self.document_title,
            "file_name": self.file_name,
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity,
            "status": self.status,
            "message": self.message,
            "evidence": list(self.evidence),
            "page_start": self.page_start,
            "page_end": self.page_end,
            "suggested_fix": self.suggested_fix,
            "engine": self.engine,
        }


@dataclass(frozen=True, slots=True)
class ReportRuleDefinition:
    rule_id: str
    label: str
    category: str
    handler_name: str


@dataclass(frozen=True, slots=True)
class ReportAnalysisContext:
    document: Document
    pages: tuple[DocumentPage, ...]
    full_text: str
    normalized_text: str
    captions: tuple[CaptionOccurrence, ...]
    catalog_metadata: dict[str, str]


class SemanticReviewEvidence(BaseModel):
    page: int = Field(ge=1)
    quote: str = Field(min_length=8, max_length=500)


class SemanticReviewFinding(BaseModel):
    rule_id: Literal[
        "semantic.scope_result_alignment",
        "semantic.unsupported_conclusion",
        "semantic.internal_contradiction",
    ]
    severity: Literal["warning", "info"] = "warning"
    message: str = Field(min_length=10, max_length=500)
    evidence: list[SemanticReviewEvidence] = Field(min_length=1, max_length=3)
    suggested_fix: str = Field(min_length=8, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)


class SemanticReviewOutput(BaseModel):
    findings: list[SemanticReviewFinding] = Field(default_factory=list, max_length=5)


class ReportReviewService:
    KIND_LABELS = ReportQualityService.KIND_LABELS
    KIND_NAMES = {
        "table": "Tablo",
        "figure": "Sekil",
        "image": "Resim",
    }
    REFERENCE_PATTERN = re.compile(
        r"\b(tablo|table|sekil|\u015fekil|figure|resim)\s*"
        r"(?:no\.?|numara)?\s*[-\u2013\u2014:]?\s*(\d+(?:\.\d+)*)\b",
        flags=re.IGNORECASE,
    )
    MEASUREMENT_PATTERN = re.compile(
        r"(?<![\w])[-+]?\d+(?P<separator>[,.])\d+\s*"
        r"(?P<unit>m(?:3|\u00b3)/s|m/s(?:2|\u00b2)?|m(?:2|\u00b2)|mm|cm|km|kg|kn|nm|"
        r"mpa|kpa|pa|hz|rpm|kw|mw|w|v|a|n|g|m|%|\u00b0\s*c)"
        r"(?=\s|[),;:]|\.|$)",
        flags=re.IGNORECASE,
    )
    FILE_PATH_PATTERN = re.compile(r"(?:\b[A-Za-z]:\\|\\\\)[^\r\n]{3,}")
    PAGE_EVIDENCE_PATTERN = re.compile(r"^Sayfa\s+(\d+)\s*:\s*(.+)$", flags=re.IGNORECASE)
    HIGHLIGHT_COLORS = {
        "critical": "F28B82",
        "warning": "F6C453",
        "info": "8EC5FF",
    }
    HIGHLIGHT_STYLE_VERSION = "review-v2"
    SEMANTIC_RULE_LABELS = {
        "semantic.scope_result_alignment": "Kapsam ve sonuc uyumu",
        "semantic.unsupported_conclusion": "Sonuclarin rapor ici dayanagi",
        "semantic.internal_contradiction": "Metin ici celiski kontrolu",
    }
    REQUIRED_METADATA = (
        ("report_number", "Rapor no", ("rapor no", "rapor numarasi", "report no")),
        ("report_date", "Tarih", ("tarih", "report date")),
        ("prepared_by", "Hazirlayan", ("hazirlayan", "prepared by")),
        ("checked_by", "Kontrol", ("kontrol", "kontrol eden", "checked by", "approved by")),
    )
    REQUIRED_SECTIONS = (
        ("scope", "Kapsam", ("kapsam", "scope")),
        ("results", "Sonuclar", ("sonuclar", "sonuc", "results", "conclusion")),
    )
    RULES = (
        ReportRuleDefinition(
            "metadata.required_fields",
            "Zorunlu kapak alanlari",
            "structure",
            "_check_required_metadata",
        ),
        ReportRuleDefinition(
            "structure.required_sections",
            "Zorunlu rapor bolumleri",
            "structure",
            "_check_required_sections",
        ),
        ReportRuleDefinition(
            "captions.sequence",
            "Tablo ve sekil numara sirasi",
            "captions",
            "_check_caption_sequences",
        ),
        ReportRuleDefinition(
            "captions.title",
            "Tablo ve sekil basliklari",
            "captions",
            "_check_caption_titles",
        ),
        ReportRuleDefinition(
            "captions.references",
            "Metin ici tablo ve sekil referanslari",
            "captions",
            "_check_caption_references",
        ),
        ReportRuleDefinition(
            "numbers.decimal_style",
            "Olcumlerde ondalik gosterimi",
            "numbers",
            "_check_decimal_style",
        ),
        ReportRuleDefinition(
            "extraction.sparse_pages",
            "Metin cikarim kalitesi",
            "extraction",
            "_check_sparse_pages",
        ),
        ReportRuleDefinition(
            "content.embedded_paths",
            "Metne tasinmis dosya yollari",
            "content",
            "_check_embedded_paths",
        ),
    )

    def __init__(self, session: Session, llm_provider: LLMProvider | None = None) -> None:
        self.session = session
        self.llm_provider = llm_provider or DisabledLLMProvider()

    def answer_question(self, question: str, document_ids: list[int]) -> dict:
        review = self.analyze_documents(document_ids)
        rule_summary = dict(review["summary"])
        semantic = self._run_semantic_review(document_ids)
        self._merge_semantic_review(review, semantic)
        summary = review["summary"]
        if not summary["documents_analyzed"]:
            response = ReportQualityService._empty_response(
                question,
                "Kalite kontrolu icin rapor belirlenemedi.",
            )
            response["review"] = review
            return response

        lines = [
            f"{summary['documents_analyzed']} rapor icin kural tabanli kontrol tamamlandi.",
            (
                f"{rule_summary['passed']} kural kontrolu gecti, {rule_summary['failed']} kural hata verdi, "
                f"{rule_summary['needs_review']} kural insan incelemesi istiyor."
            ),
        ]
        if semantic["status"] == "completed":
            lines.append(
                f"LLM destekli anlamsal kontrol tamamlandi; {semantic['finding_count']} kanitli bulgu uretildi."
            )
        elif semantic["status"] == "partial":
            lines.append(
                f"LLM destekli anlamsal kontrol kismen tamamlandi; {semantic['finding_count']} kanitli bulgu uretildi."
            )
        elif semantic["status"] == "failed":
            lines.append("LLM destekli anlamsal kontrol tamamlanamadi; kural tabanli sonuclar korunuyor.")
        findings = review["findings"]
        if not findings:
            lines.append("Etkin kurallarda raporlanacak bir sorun bulunmadi.")
        else:
            lines.append("Onemli bulgular:")
            for finding in findings[:10]:
                page_label = self._page_label(finding["page_start"], finding["page_end"])
                severity = {
                    "critical": "KRITIK",
                    "warning": "UYARI",
                    "info": "BILGI",
                }.get(finding["severity"], "KONTROL")
                suffix = f" ({page_label})" if page_label else ""
                lines.append(f"- [{severity}] {finding['message']}{suffix}")
        lines.append(
            "Bu kontrol rapor ici yapisal ve anlamsal incelemedir; muhendislik sonucunun fiziksel "
            "dogrulugunu onaylamaz."
        )

        sources = [
            self._source_for_finding(finding)
            for finding in findings
            if finding["page_start"] is not None
        ][:8]
        return {
            "question": question,
            "mode": "keyword",
            "answer": "\n".join(lines),
            "answer_found": True,
            "confidence": 1.0,
            "embedding_provider": "document-quality:rules",
            "sources": sources,
            "review": review,
        }

    def _run_semantic_review(self, document_ids: list[int]) -> dict:
        provider_name = self.llm_provider.provider_name
        if not self.llm_provider.is_available():
            return {
                "status": "disabled",
                "provider": provider_name,
                "documents": {},
                "finding_count": 0,
            }

        findings_by_document: dict[int, list[ReportFinding]] = {}
        document_status: dict[int, str] = {}
        attempted = 0
        failures = 0
        for document in self._load_documents(document_ids)[:4]:
            pages = tuple(
                self.session.scalars(
                    select(DocumentPage)
                    .where(DocumentPage.document_id == document.id)
                    .order_by(DocumentPage.page_number.asc())
                ).all()
            )
            if sum(len(page.clean_text or page.raw_text or "") for page in pages) < 160:
                findings_by_document[int(document.id)] = []
                document_status[int(document.id)] = "not_applicable"
                continue
            attempted += 1
            try:
                selected_pages = self._semantic_context_pages(pages)
                complete_context = (
                    len(selected_pages) == len(pages)
                    and all(len(self._compact_page_text(page)) <= 2200 for page in pages)
                )
                output = self.llm_provider.generate_json(
                    self._semantic_prompt(document, selected_pages, complete_context=complete_context),
                    SemanticReviewOutput,
                )
                findings_by_document[int(document.id)] = self._validated_semantic_findings(
                    document,
                    pages,
                    output,
                    allow_unsupported_conclusion=complete_context,
                )
                document_status[int(document.id)] = "completed"
            except Exception:
                failures += 1
                findings_by_document[int(document.id)] = []
                document_status[int(document.id)] = "failed"

        finding_count = sum(len(items) for items in findings_by_document.values())
        status = (
            "not_applicable"
            if attempted == 0
            else ("failed" if failures == attempted else ("partial" if failures else "completed"))
        )
        return {
            "status": status,
            "provider": provider_name,
            "documents": findings_by_document,
            "document_status": document_status,
            "finding_count": finding_count,
            "failed_documents": failures,
        }

    def _semantic_prompt(
        self,
        document: Document,
        selected_pages: list[DocumentPage],
        *,
        complete_context: bool,
    ) -> str:
        context = "\n\n".join(
            f"[SAYFA {page.page_number}]\n{self._compact_page_text(page)[:2200]}"
            for page in selected_pages
        )
        return f"""Sen teknik rapor kalite kontrol asistanisin.
Yalnizca asagidaki rapor metnini incele. Fiziksel muhendislik dogrulamasi yapma.

Uc kontrol yap:
1. Kapsamda vaat edilen calisma ile sonuclarda cevaplanan konu arasinda belirgin uyumsuzluk.
2. Sonuclarda kesin yazilan ancak verilen rapor metninde dayanak bulunmayan iddia.
3. Birbiriyle acikca celisen iki ifade.

Kurallar:
- Yalnizca belirgin ve kullanici tarafindan kontrol edilmeye deger bulgulari dondur.
- Her kanit alintisi rapor metninden harfiyen kopyalanmali ve dogru sayfa numarasini tasimali.
- Bir alintiyi uydurma, duzeltme veya yeniden yazma.
- Kapsam-sonuc uyumu ve celiski icin en az iki alinti ver.
- Kapsam-sonuc uyumsuzlugu yalnizca iki ifade acikca uyusmuyorsa yaz; sadece sonucun eksik gorunmesi yeterli degildir.
- Sonuclarin dayanagi kontrolu: {"ACIK" if complete_context else "KAPALI"}.
- Bu kontrol KAPALI ise semantic.unsupported_conclusion bulgusu kesinlikle uretme.
- Emin degilsen bulgu ekleme. confidence 0.70 altinda bulgu ekleme.
- Cikti sadece istenen JSON semasina uysun.

Rapor: {document.title}

Rapor metni:
{context}
"""

    def _semantic_context_pages(self, pages: tuple[DocumentPage, ...]) -> list[DocumentPage]:
        if not pages:
            return []
        selected: list[DocumentPage] = []
        keywords = ("kapsam", "scope", "sonuc", "result", "conclusion", "bulgu", "degerlendirme")
        for page in pages:
            normalized = self._normalize_text(page.clean_text or page.raw_text or "")
            if int(page.page_number) <= 2 or any(keyword in normalized for keyword in keywords):
                selected.append(page)
        for page in pages[-2:]:
            if page not in selected:
                selected.append(page)
        selected.sort(key=lambda item: int(item.page_number))
        return selected[:8]

    @staticmethod
    def _compact_page_text(page: DocumentPage) -> str:
        return " ".join((page.clean_text or page.raw_text or "").split())

    def _validated_semantic_findings(
        self,
        document: Document,
        pages: tuple[DocumentPage, ...],
        output: SemanticReviewOutput,
        *,
        allow_unsupported_conclusion: bool,
    ) -> list[ReportFinding]:
        page_text = {
            int(page.page_number): self._normalize_semantic_quote(self._compact_page_text(page))
            for page in pages
        }
        accepted: list[ReportFinding] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for candidate in output.findings:
            if candidate.confidence < 0.70:
                continue
            if candidate.rule_id == "semantic.unsupported_conclusion" and not allow_unsupported_conclusion:
                continue
            evidence: list[str] = []
            evidence_pages: list[int] = []
            normalized_quotes: list[str] = []
            for item in candidate.evidence:
                normalized_quote = self._normalize_semantic_quote(item.quote)
                if len(normalized_quote) < 8 or normalized_quote not in page_text.get(int(item.page), ""):
                    continue
                evidence.append(f"Sayfa {int(item.page)}: {item.quote.strip()}")
                evidence_pages.append(int(item.page))
                normalized_quotes.append(normalized_quote)
            minimum_evidence = 2 if candidate.rule_id in {
                "semantic.scope_result_alignment",
                "semantic.internal_contradiction",
            } else 1
            if len(evidence) < minimum_evidence:
                continue
            key = (candidate.rule_id, tuple(sorted(normalized_quotes)))
            if key in seen:
                continue
            seen.add(key)
            accepted.append(
                ReportFinding(
                    document_id=int(document.id),
                    document_title=document.title,
                    file_name=document.file_name,
                    rule_id=candidate.rule_id,
                    category="semantic",
                    severity=candidate.severity,
                    status="needs_review",
                    message=candidate.message.strip(),
                    evidence=tuple(evidence),
                    page_start=min(evidence_pages),
                    page_end=max(evidence_pages),
                    suggested_fix=candidate.suggested_fix.strip(),
                    engine=f"llm:{self.llm_provider.provider_name}",
                )
            )
        return accepted[:5]

    @staticmethod
    def _normalize_semantic_quote(value: str) -> str:
        return " ".join(ReportQualityService._normalize_text(value).split())

    def _merge_semantic_review(self, review: dict, semantic: dict) -> None:
        review["semantic"] = {
            key: value
            for key, value in semantic.items()
            if key != "documents"
        }
        if semantic["status"] not in {"completed", "partial"}:
            return
        document_status = semantic.get("document_status", {})
        documents_by_id = {
            int(document["document_id"]): document
            for document in review["documents"]
        }
        all_semantic_findings: list[ReportFinding] = []
        for document_id, findings in semantic["documents"].items():
            document_result = documents_by_id.get(int(document_id))
            if document_result is None:
                continue
            semantic_status = document_status.get(int(document_id), "failed")
            if semantic_status == "not_applicable":
                review["summary"]["not_applicable"] += 1
                continue
            if semantic_status != "completed":
                continue
            status = "needs_review" if findings else "pass"
            document_result["checks"].append(
                {
                    "rule_id": "semantic.review",
                    "label": "LLM destekli anlamsal kontrol",
                    "category": "semantic",
                    "status": status,
                    "finding_count": len(findings),
                }
            )
            serialized = [finding.to_dict() for finding in findings]
            document_result["findings"].extend(serialized)
            all_semantic_findings.extend(findings)
            review["summary"]["checks_run"] += 1
            review["summary"]["needs_review" if findings else "passed"] += 1
        review["findings"].extend(finding.to_dict() for finding in all_semantic_findings)
        review["summary"]["findings"] += len(all_semantic_findings)
        review["summary"]["warnings"] += sum(
            1 for finding in all_semantic_findings if finding.severity == "warning"
        )
        review["summary"]["info"] += sum(
            1 for finding in all_semantic_findings if finding.severity == "info"
        )

    def analyze_documents(self, document_ids: list[int], profile: str = "general") -> dict:
        normalized_profile = self._normalize_text(profile).strip() or "general"
        if normalized_profile != "general":
            normalized_profile = "general"

        document_results: list[dict] = []
        all_findings: list[ReportFinding] = []
        status_counts = Counter()

        documents = self._load_documents(document_ids)
        catalog_metadata = self._load_catalog_metadata([int(document.id) for document in documents])
        for document in documents:
            pages = tuple(
                self.session.scalars(
                    select(DocumentPage)
                    .where(DocumentPage.document_id == document.id)
                    .order_by(DocumentPage.page_number.asc())
                ).all()
            )
            full_text = "\n".join((page.raw_text or page.clean_text or "") for page in pages)
            context = ReportAnalysisContext(
                document=document,
                pages=pages,
                full_text=full_text,
                normalized_text=self._normalize_text(full_text),
                captions=tuple(ReportQualityService.extract_captions(list(pages))),
                catalog_metadata=catalog_metadata.get(int(document.id), {}),
            )
            checks: list[dict] = []
            document_findings: list[ReportFinding] = []

            for rule in self.RULES:
                findings = getattr(self, rule.handler_name)(context)
                if findings is None:
                    status = "not_applicable"
                    findings = []
                elif any(item.status == "fail" for item in findings):
                    status = "fail"
                elif findings:
                    status = "needs_review"
                else:
                    status = "pass"
                status_counts[status] += 1
                checks.append(
                    {
                        "rule_id": rule.rule_id,
                        "label": rule.label,
                        "category": rule.category,
                        "status": status,
                        "finding_count": len(findings),
                    }
                )
                document_findings.extend(findings)

            all_findings.extend(document_findings)
            document_results.append(
                {
                    "document_id": int(document.id),
                    "document_title": document.title,
                    "file_name": document.file_name,
                    "page_count": len(pages),
                    "checks": checks,
                    "findings": [item.to_dict() for item in document_findings],
                }
            )

        severity_counts = Counter(item.severity for item in all_findings)
        return {
            "profile": normalized_profile,
            "documents": document_results,
            "findings": [item.to_dict() for item in all_findings],
            "summary": {
                "documents_analyzed": len(document_results),
                "checks_run": sum(status_counts.values()),
                "passed": status_counts["pass"],
                "failed": status_counts["fail"],
                "needs_review": status_counts["needs_review"],
                "not_applicable": status_counts["not_applicable"],
                "findings": len(all_findings),
                "critical": severity_counts["critical"],
                "warnings": severity_counts["warning"],
                "info": severity_counts["info"],
            },
        }

    def _check_required_metadata(self, context: ReportAnalysisContext) -> list[ReportFinding]:
        cover_text = "\n".join(
            page.raw_text or page.clean_text or ""
            for page in context.pages
            if int(page.page_number) <= 2
        )
        normalized_cover = self._normalize_text(cover_text)
        missing = [
            label
            for key, label, aliases in self.REQUIRED_METADATA
            if not any(alias in normalized_cover for alias in aliases)
            and not context.catalog_metadata.get(key)
        ]
        if not missing:
            return []
        last_page = min(2, max((int(page.page_number) for page in context.pages), default=1))
        return [
            self._finding(
                context,
                rule_id="metadata.required_fields",
                category="structure",
                severity="warning",
                status="needs_review",
                message="Ilk iki sayfada zorunlu kapak alanlari bulunamadi: " + ", ".join(missing) + ".",
                evidence=(),
                page_start=1,
                page_end=last_page,
                suggested_fix="Kapakta eksik alanlari ekleyin veya taranmis kapak icin OCR sonucunu kontrol edin.",
            )
        ]

    def _load_catalog_metadata(self, document_ids: list[int]) -> dict[int, dict[str, str]]:
        normalized_ids = sorted({int(item) for item in document_ids if int(item) > 0})
        if not normalized_ids:
            return {}
        rows = self.session.execute(
            select(
                CatalogDocumentLink.document_id,
                ReportCatalogEntry.report_code,
                ReportCatalogEntry.report_date,
                ReportCatalogEntry.authors,
            )
            .join(ReportCatalogEntry, ReportCatalogEntry.id == CatalogDocumentLink.catalog_entry_id)
            .where(CatalogDocumentLink.document_id.in_(normalized_ids))
            .order_by(ReportCatalogEntry.id.desc())
        ).all()
        metadata_by_document: dict[int, dict[str, str]] = {}
        for document_id, report_code, report_date, authors in rows:
            metadata = metadata_by_document.setdefault(int(document_id), {})
            if report_code and "report_number" not in metadata:
                metadata["report_number"] = str(report_code).strip()
            if report_date and "report_date" not in metadata:
                metadata["report_date"] = str(report_date).strip()
            if authors and "prepared_by" not in metadata:
                metadata["prepared_by"] = str(authors).strip()
        return metadata_by_document

    def _check_required_sections(self, context: ReportAnalysisContext) -> list[ReportFinding]:
        missing = [
            label
            for _key, label, aliases in self.REQUIRED_SECTIONS
            if not any(alias in context.normalized_text for alias in aliases)
        ]
        if not missing:
            return []
        return [
            self._finding(
                context,
                rule_id="structure.required_sections",
                category="structure",
                severity="warning",
                status="needs_review",
                message="Zorunlu rapor bolumleri metinde bulunamadi: " + ", ".join(missing) + ".",
                evidence=(),
                page_start=None,
                page_end=None,
                suggested_fix="Eksik bolumleri ekleyin veya farkli baslik kullanimini kontrol profilinde tanimlayin.",
            )
        ]

    def _check_caption_sequences(
        self,
        context: ReportAnalysisContext,
    ) -> list[ReportFinding] | None:
        if not context.captions:
            return None
        findings: list[ReportFinding] = []
        for kind in self.KIND_NAMES:
            occurrences = [item for item in context.captions if item.kind == kind]
            if not occurrences:
                continue
            result = ReportQualityService._sequence_result(occurrences)
            if result["valid"]:
                continue
            issues: list[str] = []
            if result["duplicates"]:
                issues.append("tekrar eden " + ", ".join(result["duplicates"]))
            if result["missing"]:
                issues.append("eksik " + ", ".join(result["missing"]))
            if result["out_of_order"]:
                issues.append("gecis sirasi bozuk")
            page_numbers = [item.page_number for item in occurrences]
            findings.append(
                self._finding(
                    context,
                    rule_id="captions.sequence",
                    category="captions",
                    severity="warning",
                    status="fail",
                    message=f"{self.KIND_LABELS[kind]} numaralandirmasinda sorun var: {'; '.join(issues)}.",
                    evidence=tuple(
                        f"Sayfa {item.page_number}: {item.raw_line}" for item in occurrences[:12]
                    ),
                    page_start=min(page_numbers),
                    page_end=max(page_numbers),
                    suggested_fix="Numaralari belge icindeki gecis sirasina gore benzersiz ve kesintisiz duzenleyin.",
                )
            )
        return findings

    def _check_caption_titles(
        self,
        context: ReportAnalysisContext,
    ) -> list[ReportFinding] | None:
        if not context.captions:
            return None
        untitled = [item for item in context.captions if len(self._normalize_text(item.title).strip()) < 3]
        if not untitled:
            return []
        page_numbers = [item.page_number for item in untitled]
        labels = ", ".join(
            f"{self.KIND_NAMES[item.kind]} {item.number_text}" for item in untitled[:10]
        )
        return [
            self._finding(
                context,
                rule_id="captions.title",
                category="captions",
                severity="warning",
                status="fail",
                message="Aciklayici basligi bulunmayan ogeler var: " + labels + ".",
                evidence=tuple(
                    f"Sayfa {item.page_number}: {item.raw_line}" for item in untitled[:10]
                ),
                page_start=min(page_numbers),
                page_end=max(page_numbers),
                suggested_fix="Her tablo, sekil ve resme icerigini aciklayan kisa bir baslik ekleyin.",
            )
        ]

    def _check_caption_references(
        self,
        context: ReportAnalysisContext,
    ) -> list[ReportFinding] | None:
        if not context.captions:
            return None
        declared = {(item.kind, item.number_text): item for item in context.captions}
        references: dict[tuple[str, str], list[tuple[int, str]]] = {}

        for page in context.pages:
            text = page.raw_text or page.clean_text or ""
            for raw_line in text.splitlines():
                line = " ".join(raw_line.split()).strip()
                if not line:
                    continue
                caption_match = ReportQualityService.CAPTION_PATTERN.match(line)
                caption_key: tuple[str, str] | None = None
                if caption_match and not ReportQualityService.REFERENCE_SUFFIX_PATTERN.match(
                    caption_match.group(4).strip()
                ):
                    caption_key = (
                        ReportQualityService._caption_kind(caption_match.group(1)),
                        caption_match.group(2),
                    )
                skipped_caption = False
                for match in self.REFERENCE_PATTERN.finditer(line):
                    key = (ReportQualityService._caption_kind(match.group(1)), match.group(2))
                    if caption_key == key and not skipped_caption:
                        skipped_caption = True
                        continue
                    references.setdefault(key, []).append((int(page.page_number), line[:500]))

        unreferenced = [key for key in declared if key not in references]
        dangling = [key for key in references if key not in declared]
        if not unreferenced and not dangling:
            return []

        issue_parts: list[str] = []
        evidence: list[str] = []
        page_numbers: list[int] = []
        if unreferenced:
            issue_parts.append(
                "metinde anilmayan "
                + ", ".join(f"{self.KIND_NAMES[kind]} {number}" for kind, number in unreferenced[:10])
            )
            for key in unreferenced[:8]:
                item = declared[key]
                evidence.append(f"Sayfa {item.page_number}: {item.raw_line}")
                page_numbers.append(item.page_number)
        if dangling:
            issue_parts.append(
                "basligi bulunamayan referans "
                + ", ".join(f"{self.KIND_NAMES[kind]} {number}" for kind, number in dangling[:10])
            )
            for key in dangling[:8]:
                page_number, line = references[key][0]
                evidence.append(f"Sayfa {page_number}: {line}")
                page_numbers.append(page_number)

        return [
            self._finding(
                context,
                rule_id="captions.references",
                category="captions",
                severity="warning",
                status="needs_review",
                message="Tablo/sekil referanslari kontrol edilmeli: " + "; ".join(issue_parts) + ".",
                evidence=tuple(evidence),
                page_start=min(page_numbers) if page_numbers else None,
                page_end=max(page_numbers) if page_numbers else None,
                suggested_fix="Her ogeyi metinde en az bir kez anin ve her metin ici referansin bir basliga karsilik geldigini dogrulayin.",
            )
        ]

    def _check_decimal_style(self, context: ReportAnalysisContext) -> list[ReportFinding]:
        matches: dict[str, list[tuple[int, str]]] = {",": [], ".": []}
        for page in context.pages:
            text = page.raw_text or page.clean_text or ""
            for raw_line in text.splitlines():
                line = " ".join(raw_line.split()).strip()
                if not line:
                    continue
                for match in self.MEASUREMENT_PATTERN.finditer(line):
                    matches[match.group("separator")].append((int(page.page_number), line[:500]))
        if not matches[","] or not matches["."]:
            return []

        examples = [matches[","][0], matches["."][0]]
        page_numbers = [page_number for page_number, _line in examples]
        return [
            self._finding(
                context,
                rule_id="numbers.decimal_style",
                category="numbers",
                severity="warning",
                status="needs_review",
                message="Birimli olcumlerde hem virgul hem nokta ondalik ayraci kullanilmis.",
                evidence=tuple(f"Sayfa {page}: {line}" for page, line in examples),
                page_start=min(page_numbers),
                page_end=max(page_numbers),
                suggested_fix="Raporun dil ve kurum standardina uygun tek bir ondalik ayraci kullanin.",
            )
        ]

    def _check_sparse_pages(self, context: ReportAnalysisContext) -> list[ReportFinding]:
        sparse_pages = [
            int(page.page_number)
            for page in context.pages
            if len(re.sub(r"\W+", "", page.raw_text or page.clean_text or "", flags=re.UNICODE)) < 20
        ]
        if not sparse_pages:
            return []
        return [
            self._finding(
                context,
                rule_id="extraction.sparse_pages",
                category="extraction",
                severity="warning",
                status="needs_review",
                message="Metni cikarilamayan veya cok az metin bulunan sayfalar var: "
                + ", ".join(str(page) for page in sparse_pages[:20])
                + ".",
                evidence=(),
                page_start=min(sparse_pages),
                page_end=max(sparse_pages),
                suggested_fix="Sayfalari gorsel olarak kontrol edin; gerekiyorsa OCR calistirin.",
            )
        ]

    def _check_embedded_paths(self, context: ReportAnalysisContext) -> list[ReportFinding]:
        matches: list[tuple[int, str]] = []
        for page in context.pages:
            text = page.raw_text or page.clean_text or ""
            for raw_line in text.splitlines():
                line = " ".join(raw_line.split()).strip()
                if line and self.FILE_PATH_PATTERN.search(line):
                    matches.append((int(page.page_number), line[:500]))
        if not matches:
            return []
        page_numbers = [page_number for page_number, _line in matches]
        return [
            self._finding(
                context,
                rule_id="content.embedded_paths",
                category="content",
                severity="info",
                status="needs_review",
                message="Rapor metninde yerel veya ag dosya yolu bulundu.",
                evidence=tuple(f"Sayfa {page}: {line}" for page, line in matches[:8]),
                page_start=min(page_numbers),
                page_end=max(page_numbers),
                suggested_fix="Dosya yolunun raporun yayinlanan surumunde gorunmesinin gerekli olup olmadigini kontrol edin.",
            )
        ]

    @staticmethod
    def _finding(
        context: ReportAnalysisContext,
        *,
        rule_id: str,
        category: str,
        severity: str,
        status: str,
        message: str,
        evidence: tuple[str, ...],
        page_start: int | None,
        page_end: int | None,
        suggested_fix: str,
    ) -> ReportFinding:
        return ReportFinding(
            document_id=int(context.document.id),
            document_title=context.document.title,
            file_name=context.document.file_name,
            rule_id=rule_id,
            category=category,
            severity=severity,
            status=status,
            message=message,
            evidence=evidence,
            page_start=page_start,
            page_end=page_end,
            suggested_fix=suggested_fix,
        )

    def _load_documents(self, document_ids: list[int]) -> list[Document]:
        if not document_ids:
            return []
        rows = self.session.scalars(select(Document).where(Document.id.in_(document_ids))).all()
        rows_by_id = {int(document.id): document for document in rows}
        return [rows_by_id[document_id] for document_id in document_ids if document_id in rows_by_id]

    def build_highlighted_preview(
        self,
        document_id: int,
        rule_id: str,
        page: int,
        *,
        cache_dir: str | Path | None = None,
    ) -> tuple[Path, int]:
        document = self.session.get(Document, int(document_id))
        if document is None:
            raise ValueError("Document not found.")
        source_path = resolve_document_file_path(document.file_path)
        if source_path is None or source_path.suffix.lower() != ".pdf":
            raise ValueError("Review highlighting is available only for PDF documents.")

        findings = self.analyze_documents([int(document_id)])["findings"]
        candidates = [
            finding
            for finding in findings
            if finding["rule_id"] == rule_id and finding["evidence"]
        ]
        if not candidates:
            raise ValueError("Review finding could not be found.")
        requested_page = max(int(page), 1)
        finding = next(
            (
                item
                for item in candidates
                if int(item["page_start"] or 1) <= requested_page <= int(item["page_end"] or item["page_start"] or 1)
            ),
            candidates[0],
        )
        requests = self._highlight_requests_for_finding(finding)
        if not requests:
            raise ValueError("Review finding has no highlightable page evidence.")

        stat = source_path.stat()
        cache_key = "|".join(
            [
                self.HIGHLIGHT_STYLE_VERSION,
                str(source_path.resolve()),
                str(stat.st_mtime_ns),
                str(stat.st_size),
                str(rule_id),
                str(requested_page),
                *finding["evidence"],
            ]
        )
        digest = hashlib.sha256(cache_key.encode("utf-8", errors="ignore")).hexdigest()[:20]
        target_dir = Path(cache_dir) if cache_dir else DATA_DIR / "review_cache"
        output_path = target_dir / f"document-{int(document_id)}-{digest}.pdf"
        if output_path.is_file():
            return output_path, len(requests)

        result = PdfHighlightService().build(source_path, output_path, requests)
        if result.highlighted_passages < 1:
            result.output_path.unlink(missing_ok=True)
            raise ValueError("Review evidence could not be located on the PDF page.")
        return result.output_path, result.highlighted_passages

    def _highlight_requests_for_finding(self, finding: dict) -> list[PdfHighlightRequest]:
        color = self.HIGHLIGHT_COLORS.get(str(finding.get("severity") or ""), "F6C453")
        requests: list[PdfHighlightRequest] = []
        for index, raw_evidence in enumerate(finding.get("evidence") or []):
            evidence = " ".join(str(raw_evidence).split()).strip()
            if not evidence:
                continue
            match = self.PAGE_EVIDENCE_PATTERN.match(evidence)
            evidence_page = int(match.group(1)) if match else int(finding.get("page_start") or 1)
            excerpt = match.group(2).strip() if match else evidence
            if not excerpt:
                continue
            requests.append(
                PdfHighlightRequest(
                    key=f"{finding['rule_id']}:{index}",
                    page_start=evidence_page,
                    page_end=evidence_page,
                    excerpt=excerpt,
                    color=color,
                    label=str(finding.get("message") or self._rule_label(finding["rule_id"])),
                )
            )
        return requests

    @staticmethod
    def _page_label(page_start: int | None, page_end: int | None) -> str:
        if page_start is None:
            return ""
        if page_end is None or page_start == page_end:
            return f"Sayfa {page_start}"
        return f"Sayfa {page_start}-{page_end}"

    @classmethod
    def _rule_label(cls, rule_id: str) -> str:
        if rule_id in cls.SEMANTIC_RULE_LABELS:
            return cls.SEMANTIC_RULE_LABELS[rule_id]
        for rule in cls.RULES:
            if rule.rule_id == rule_id:
                return rule.label
        return rule_id

    @classmethod
    def _source_for_finding(cls, finding: dict) -> dict:
        evidence_text = "\n".join(finding["evidence"]).strip()
        return {
            "document_id": int(finding["document_id"]),
            "document_title": finding["document_title"],
            "file_name": finding["file_name"],
            "page_start": finding["page_start"],
            "page_end": finding["page_end"] or finding["page_start"],
            "section_title": cls._rule_label(finding["rule_id"]),
            "chunk_text": (evidence_text or finding["message"])[:6000],
            "match_type": "keyword",
            "keyword_score": 1.0,
            "semantic_score": 0.0,
            "combined_score": 1.0,
            "source_kind": "report_review",
            "review_rule_id": finding["rule_id"],
            "review_category": finding["category"],
            "review_severity": finding["severity"],
            "review_status": finding["status"],
            "review_message": finding["message"],
            "suggested_fix": finding["suggested_fix"],
            "review_engine": finding["engine"],
            "review_highlight_available": bool(evidence_text) and finding["engine"] == "rules",
        }

    @staticmethod
    def _normalize_text(text: str) -> str:
        return ReportQualityService._normalize_text(text)
