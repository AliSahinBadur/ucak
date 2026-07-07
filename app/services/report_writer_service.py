from __future__ import annotations

from datetime import date
from functools import lru_cache
from io import BytesIO
import logging
from pathlib import Path
import re
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as ReportImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from ..config import (
    LLM_MAX_CONTEXT_TOKENS,
    REPORT_LLM_BACKEND,
    REPORT_LLM_ENABLED,
    REPORT_LLM_MODEL_NAME,
    REPORT_LLM_TIMEOUT_SECONDS,
)
from .llm_provider import DisabledLLMProvider, LLMProvider, OllamaLLMProvider
from .search_service import SearchService


logger = logging.getLogger(__name__)


class ReportWriterService:
    _FONT_READY = False
    _FONT_BODY = "Helvetica"
    _FONT_BOLD = "Helvetica-Bold"
    _REPORT_LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "report_logo.png"

    def __init__(self, session: Session) -> None:
        self.session = session
        self.search_service = SearchService(session)
        self.llm_provider = _build_report_provider()

    def build_draft(
        self,
        title: str,
        report_type: str,
        report_no: str = "",
        report_date: str = "",
        prepared_by: str = "",
        checked_by: str = "",
        requested_by: str = "",
        classification: str = "GENEL / PUBLIC",
        objective: str = "",
        keywords: str = "",
        raw_notes: str = "",
        detail_level: str = "detailed",
        mode: str = "hybrid",
        limit: int = 5,
    ) -> dict:
        cleaned_title = " ".join(title.split())
        cleaned_report_type = " ".join(report_type.split()) or "Genel Teknik Rapor"
        cleaned_report_no = " ".join(report_no.split()) or self._guess_report_no(cleaned_title)
        cleaned_report_date = " ".join(report_date.split()) or date.today().strftime("%d.%m.%Y")
        cleaned_prepared_by = " ".join(prepared_by.split()) or "-"
        cleaned_checked_by = self._normalize_people(checked_by) or "-"
        cleaned_requested_by = " ".join(requested_by.split()) or "-"
        cleaned_classification = " ".join(classification.split()) or "GENEL / PUBLIC"
        cleaned_objective = self._clean_sentence(objective)
        cleaned_notes = self._clean_notes(raw_notes)
        refined_keywords = self._refine_keywords(keywords, cleaned_title, cleaned_objective, cleaned_notes)
        retrieval_query = self._build_retrieval_query(cleaned_title, cleaned_objective, refined_keywords, cleaned_notes)
        sources = self._run_search(retrieval_query, mode=mode, limit=limit) if retrieval_query else []
        template_draft = self._compose_draft(
            title=cleaned_title,
            report_type=cleaned_report_type,
            report_no=cleaned_report_no,
            report_date=cleaned_report_date,
            prepared_by=cleaned_prepared_by,
            checked_by=cleaned_checked_by,
            requested_by=cleaned_requested_by,
            classification=cleaned_classification,
            objective=cleaned_objective,
            refined_keywords=refined_keywords,
            cleaned_notes=cleaned_notes,
            sources=sources,
            detail_level=detail_level,
        )
        draft, generation_provider = self._compose_llm_draft(
            template_draft=template_draft,
            title=cleaned_title,
            report_type=cleaned_report_type,
            report_no=cleaned_report_no,
            report_date=cleaned_report_date,
            prepared_by=cleaned_prepared_by,
            checked_by=cleaned_checked_by,
            requested_by=cleaned_requested_by,
            classification=cleaned_classification,
            objective=cleaned_objective,
            refined_keywords=refined_keywords,
            cleaned_notes=cleaned_notes,
            sources=sources,
            detail_level=detail_level,
        )
        return {
            "title": cleaned_title,
            "report_type": cleaned_report_type,
            "report_no": cleaned_report_no,
            "report_date": cleaned_report_date,
            "prepared_by": cleaned_prepared_by,
            "checked_by": cleaned_checked_by,
            "requested_by": cleaned_requested_by,
            "classification": cleaned_classification,
            "detail_level": detail_level,
            "draft": draft,
            "refined_keywords": refined_keywords,
            "cleaned_notes": cleaned_notes,
            "embedding_provider": self.search_service.embedding_provider_name(),
            "generation_provider": generation_provider,
            "sources": sources[:3],
        }

    def build_pdf_bytes(self, draft_payload: dict) -> bytes:
        self._ensure_pdf_font()
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DraftTitle",
            parent=styles["Heading1"],
            fontName=self._FONT_BOLD,
            fontSize=16,
            leading=20,
            spaceAfter=8,
        )
        meta_style = ParagraphStyle(
            "DraftMeta",
            parent=styles["BodyText"],
            fontName=self._FONT_BODY,
            fontSize=9,
            leading=12,
            textColor="#6b3f45",
            spaceAfter=10,
        )
        heading_style = ParagraphStyle(
            "DraftHeading",
            parent=styles["Heading2"],
            fontName=self._FONT_BOLD,
            fontSize=12,
            leading=15,
            spaceBefore=8,
            spaceAfter=5,
        )
        body_style = ParagraphStyle(
            "DraftBody",
            parent=styles["BodyText"],
            fontName=self._FONT_BODY,
            fontSize=10,
            leading=14,
            spaceAfter=4,
        )
        bullet_style = ParagraphStyle(
            "DraftBullet",
            parent=body_style,
            leftIndent=10,
            bulletIndent=0,
        )
        cover_label_style = ParagraphStyle(
            "CoverLabel",
            parent=body_style,
            fontName=self._FONT_BOLD,
            fontSize=8,
            leading=10,
            alignment=1,
        )
        cover_value_style = ParagraphStyle(
            "CoverValue",
            parent=body_style,
            fontName=self._FONT_BODY,
            fontSize=10,
            leading=12,
            alignment=1,
        )
        cover_title_style = ParagraphStyle(
            "CoverTitle",
            parent=title_style,
            fontName=self._FONT_BOLD,
            fontSize=13,
            leading=16,
            alignment=1,
        )

        story = [
            Paragraph(xml_escape(draft_payload.get("classification", "GENEL / PUBLIC")), meta_style),
            self._build_pdf_cover_table(
                draft_payload,
                cover_label_style=cover_label_style,
                cover_value_style=cover_value_style,
                cover_title_style=cover_title_style,
            ),
            self._build_pdf_summary_table(
                draft_payload,
                body_style=body_style,
                cover_label_style=cover_label_style,
                cover_title_style=cover_title_style,
            ),
            Spacer(1, 8),
        ]

        for raw_line in self._draft_body_without_cover(draft_payload["draft"]).splitlines():
            line = raw_line.strip()
            if not line:
                story.append(Spacer(1, 5))
                continue
            escaped = xml_escape(line)
            if re.match(r"^\d+\.\s+[A-Z0-9 ]+$", line):
                story.append(Paragraph(escaped, heading_style))
            elif line.startswith("- "):
                story.append(Paragraph(xml_escape(line[2:]), bullet_style, bulletText="•"))
            elif line.isupper() and len(line) <= 80:
                story.append(Paragraph(escaped, heading_style))
            else:
                story.append(Paragraph(escaped, body_style))

        document.build(story)
        return buffer.getvalue()

    def _build_pdf_cover_table(
        self,
        draft_payload: dict,
        *,
        cover_label_style: ParagraphStyle,
        cover_value_style: ParagraphStyle,
        cover_title_style: ParagraphStyle,
    ) -> Table:
        def paragraph(value: str, style: ParagraphStyle) -> Paragraph:
            return Paragraph(xml_escape(str(value or "")), style)
        def paragraph_html(value: str, style: ParagraphStyle) -> Paragraph:
            return Paragraph(str(value or ""), style)

        checked_by = "<br/>".join(xml_escape(part) for part in str(draft_payload.get("checked_by") or "-").splitlines())
        table = Table(
            [
                [
                    self._build_logo_flowable(cover_title_style),
                    paragraph("DEVELOPMENT STATEMENT", cover_title_style),
                    paragraph_html("TARIH<br/>" + xml_escape(str(draft_payload.get("report_date") or "")), cover_label_style),
                    paragraph_html("RAPOR NO.<br/>" + xml_escape(str(draft_payload.get("report_no") or "")), cover_label_style),
                ],
                [
                    "",
                    paragraph(str(draft_payload.get("title") or "").upper(), cover_title_style),
                    paragraph_html("HAZIRLAYAN<br/>" + xml_escape(str(draft_payload.get("prepared_by") or "-")), cover_label_style),
                    paragraph_html("KONTROL<br/>" + checked_by, cover_label_style),
                ],
            ],
            colWidths=[42 * mm, 64 * mm, 31 * mm, 37 * mm],
            rowHeights=[26 * mm, 34 * mm],
        )
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.9, colors.black),
                    ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#d9d9d9")),
                    ("SPAN", (0, 0), (0, 1)),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return table

    @classmethod
    def _build_logo_flowable(cls, fallback_style: ParagraphStyle) -> Paragraph | ReportImage:
        if cls._REPORT_LOGO_PATH.exists():
            logo = ReportImage(str(cls._REPORT_LOGO_PATH))
            logo._restrictSize(38 * mm, 24 * mm)
            return logo
        return Paragraph("ISUZU", fallback_style)

    def _build_pdf_summary_table(
        self,
        draft_payload: dict,
        *,
        body_style: ParagraphStyle,
        cover_label_style: ParagraphStyle,
        cover_title_style: ParagraphStyle,
    ) -> Table:
        draft = str(draft_payload.get("draft") or "")
        scope = self._extract_cover_section(draft, "KAPSAM:", "SONUCLAR:") or "-"
        results = self._extract_cover_section(draft, "SONUCLAR:", "HAZIRLAYAN:") or "-"
        table = Table(
            [
                [Paragraph(xml_escape(str(draft_payload.get("title") or "").upper()), cover_title_style)],
                [Paragraph("<b>KAPSAM:</b><br/>" + xml_escape(scope), body_style)],
                [Paragraph("<b>SONUCLAR:</b><br/>" + xml_escape(results), body_style)],
            ],
            colWidths=[174 * mm],
        )
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.7, colors.HexColor("#000080")),
                    ("TEXTCOLOR", (0, 0), (0, 0), colors.HexColor("#000080")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return table

    @staticmethod
    def _draft_body_without_cover(draft: str) -> str:
        match = re.search(r"\n(?=1\.\s+)", draft or "")
        if not match:
            return draft
        return draft[match.end():].lstrip()

    @staticmethod
    def _extract_cover_section(draft: str, start_marker: str, end_marker: str) -> str:
        start = draft.find(start_marker)
        if start < 0:
            return ""
        start += len(start_marker)
        end = draft.find(end_marker, start)
        if end < 0:
            end = len(draft)
        return " ".join(draft[start:end].split())

    @classmethod
    def _ensure_pdf_font(cls) -> None:
        if cls._FONT_READY:
            return

        regular_candidates = [
            Path(r"C:\Windows\Fonts\arial.ttf"),
            Path(r"C:\Windows\Fonts\DejaVuSans.ttf"),
        ]
        bold_candidates = [
            Path(r"C:\Windows\Fonts\arialbd.ttf"),
            Path(r"C:\Windows\Fonts\DejaVuSans-Bold.ttf"),
        ]

        regular_path = next((path for path in regular_candidates if path.exists()), None)
        bold_path = next((path for path in bold_candidates if path.exists()), None)

        if regular_path and bold_path:
            pdfmetrics.registerFont(TTFont("BigAgentBody", str(regular_path)))
            pdfmetrics.registerFont(TTFont("BigAgentBold", str(bold_path)))
            cls._FONT_BODY = "BigAgentBody"
            cls._FONT_BOLD = "BigAgentBold"

        cls._FONT_READY = True

    def _run_search(self, query: str, mode: str, limit: int) -> list[dict]:
        if mode == "keyword":
            return self.search_service.keyword_search(query, limit=limit)
        if mode == "semantic":
            return self.search_service.semantic_search(query, limit=limit)
        return self.search_service.hybrid_search(query, limit=limit)

    @staticmethod
    def _guess_report_no(title: str) -> str:
        match = re.search(r"\b20\d{2}[-_][0-9A-Za-z.]+(?:[-_][0-9A-Za-z.]+){1,}\b", title or "")
        if match:
            return match.group(0)
        return "TASLAK"

    @staticmethod
    def _normalize_people(value: str) -> str:
        parts = re.split(r"[,;\n\r]+", value or "")
        names = [" ".join(part.split()) for part in parts if part.strip()]
        return "\n".join(names)

    @staticmethod
    def _clean_sentence(text: str) -> str:
        compact = " ".join(text.split()).strip(" ;")
        if not compact:
            return ""
        if compact[-1] not in ".!?":
            compact += "."
        return compact[0].upper() + compact[1:]

    def _clean_notes(self, raw_notes: str) -> list[str]:
        if not raw_notes.strip():
            return []
        raw_parts = re.split(r"[\n\r]+|;", raw_notes)
        notes: list[str] = []
        for part in raw_parts:
            stripped = part.strip(" \t-•")
            if not stripped:
                continue
            normalized = self._clean_sentence(stripped)
            if normalized and normalized not in notes:
                notes.append(normalized)
        return notes[:8]

    @staticmethod
    def _refine_keywords(keywords: str, title: str, objective: str, notes: list[str]) -> list[str]:
        token_pool: list[str] = []
        for source in (keywords, title, objective, " ".join(notes)):
            token_pool.extend(re.findall(r"[A-Za-zÀ-ÿ0-9_+-]+", source))
        refined: list[str] = []
        stopwords = {
            "ve",
            "ile",
            "icin",
            "olan",
            "olanlar",
            "rapor",
            "teknik",
            "genel",
            "calisma",
            "bu",
            "bir",
            "the",
            "for",
        }
        for token in token_pool:
            normalized = token.strip().strip(".,:;()[]{}")
            lowered = normalized.casefold()
            if len(normalized) < 3 or lowered in stopwords:
                continue
            if normalized not in refined:
                refined.append(normalized)
        return refined[:10]

    @staticmethod
    def _build_retrieval_query(title: str, objective: str, refined_keywords: list[str], notes: list[str]) -> str:
        parts = [title, objective]
        parts.extend(refined_keywords[:6])
        if notes:
            parts.append(" ".join(notes[:3]))
        return " ".join(part for part in parts if part).strip()

    def _compose_draft(
        self,
        title: str,
        report_type: str,
        report_no: str,
        report_date: str,
        prepared_by: str,
        checked_by: str,
        requested_by: str,
        classification: str,
        objective: str,
        refined_keywords: list[str],
        cleaned_notes: list[str],
        sources: list[dict],
        detail_level: str,
    ) -> str:
        source_titles = []
        for source in sources[:2]:
            document_title = source.get("document_title")
            if document_title and document_title not in source_titles:
                source_titles.append(document_title)

        intro_parts = [f"Bu {report_type.lower()} taslagi, {title.lower()} konusu icin hazirlanmistir."]
        if objective:
            intro_parts.append(objective)
        if refined_keywords:
            intro_parts.append(
                "Calisma kapsaminda "
                + ", ".join(refined_keywords[:5])
                + " basliklari esas alinmistir."
            )
        if source_titles:
            intro_parts.append(
                "Yuklu raporlar icinden ozellikle "
                + ", ".join(source_titles)
                + " belgelerindeki anlatim dili referans alinmistir."
            )

        scope_section = "\n".join(f"- {note}" for note in cleaned_notes) if cleaned_notes else "- Kullanici notu eklenmedi."
        findings_lines = [
            "- Analiz akisi, giris verileri ve elde edilen bulgular tutarli bir teknik dil ile sunulmalidir.",
            "- Sayisal bulgular, test kosullari ve varsa senaryo farklari ayri satirlarda belirtilmelidir.",
            "- Sonuc bolumunde aksiyon, risk veya uygunluk degerlendirmesi net cumlelerle verilmelidir.",
        ]
        if sources:
            first_source = sources[0]
            section_label = first_source.get("section_title") or "Ilgili bolum"
            findings_lines.append(
                f"- Ornek raporlarda '{section_label}' benzeri bolum basliklari kullanilmis; sen de benzer bir baslik yapisi izleyebilirsin."
            )

        source_snippets = []
        for source in sources[:3]:
            snippet = " ".join((source.get("chunk_text") or "").split())
            if len(snippet) > 240:
                snippet = snippet[:237].rstrip() + "..."
            if snippet:
                source_snippets.append(
                    f"- {source.get('document_title', 'Kaynak belge')} / Sayfa {source.get('page_start', '?')}-{source.get('page_end', '?')}: {snippet}"
                )

        conclusion = "Bu taslak, kullanicinin girdigi notlari duzgun bir rapor iskeletine cevirir. Nihai surumde sayisal degerler, test kosullari ve teknik yorumlar ilgili ekibin dogrulamasiyla netlestirilmelidir."
        if refined_keywords:
            conclusion += " Ozellikle " + ", ".join(refined_keywords[:4]) + " kavramlari tutarli sekilde korunmalidir."

        scope_summary = objective or "Bu rapor, kullanicidan gelen teknik notlar ve yuklu raporlardan cekilen referanslarla hazirlanan bir degerlendirme taslagidir."
        result_summary = self._build_result_summary(cleaned_notes, sources)
        method_bullets = self._build_method_bullets(cleaned_notes, refined_keywords)
        solution_bullets = self._build_solution_suggestions(refined_keywords, cleaned_notes)
        cover_block = self._build_template_cover_text(
            title=title,
            report_no=report_no,
            report_date=report_date,
            prepared_by=prepared_by,
            checked_by=checked_by,
            requested_by=requested_by,
            classification=classification,
            scope_summary=scope_summary,
            result_summary=result_summary,
        )

        if detail_level == "quick":
            summary_lines = [
                cover_block,
                "",
                "1. GIRDI NOTLARI",
                scope_section,
                "",
                "2. KISA SONUC",
                conclusion,
            ]
            if source_snippets:
                summary_lines.extend(
                    [
                        "",
                        "3. REFERANS PASAJLAR",
                        "\n".join(source_snippets[:2]),
                    ]
                )
            return "\n".join(summary_lines).strip()

        sections = [
            cover_block,
            "",
            "1. GIRIS",
            " ".join(intro_parts),
            "",
            "2. TEST VE DEGERLENDIRME YONTEMI",
            "\n".join(f"- {item}" for item in method_bullets),
            "",
            "3. GIRDI VERILERI VE KULLANICI NOTLARI",
            scope_section,
            "",
            "4. BULGULAR VE TEKNIK DEGERLENDIRME",
            result_summary,
            "",
            "5. RAPOR METNI TASLAGI",
            self._build_body_paragraph(report_type, title, cleaned_notes, refined_keywords, sources),
            "",
            "6. YONETICI OZETI",
            self._build_executive_summary(scope_summary, result_summary, solution_bullets),
            "",
            "7. YAZIM ICIN DIKKAT EDILECEK NOKTALAR",
            "\n".join(findings_lines),
            "",
            "8. ACIK NOKTALAR VE DOGRULAMA IHTIYACI",
            "\n".join(self._build_open_items(cleaned_notes, sources)),
            "",
            "9. SONUC VE ONERILEN AKSIYONLAR",
            conclusion,
            "",
            "\n".join(f"- {item}" for item in solution_bullets),
        ]

        if source_snippets:
            sections.extend(
                [
                    "",
                    "10. REFERANS ALINAN ORNEK PASAJLAR",
                    "\n".join(source_snippets),
                ]
            )

        return "\n".join(sections).strip()

    def _compose_llm_draft(
        self,
        *,
        template_draft: str,
        title: str,
        report_type: str,
        report_no: str,
        report_date: str,
        prepared_by: str,
        checked_by: str,
        requested_by: str,
        classification: str,
        objective: str,
        refined_keywords: list[str],
        cleaned_notes: list[str],
        sources: list[dict],
        detail_level: str,
    ) -> tuple[str, str]:
        if not self.llm_provider.is_available():
            return template_draft, "template"
        if not cleaned_notes and not sources:
            return template_draft, "template:no-input"

        cover_block = template_draft[: template_draft.find("\n\n1.")] if "\n\n1." in template_draft else ""
        if not cover_block:
            return template_draft, "template"

        prompt = self._build_llm_report_prompt(
            template_draft=template_draft,
            title=title,
            report_type=report_type,
            report_no=report_no,
            report_date=report_date,
            prepared_by=prepared_by,
            checked_by=checked_by,
            requested_by=requested_by,
            classification=classification,
            objective=objective,
            refined_keywords=refined_keywords,
            cleaned_notes=cleaned_notes,
            sources=sources,
            detail_level=detail_level,
            cover_block=cover_block,
        )
        try:
            generated = self.llm_provider.generate(
                prompt,
                max_tokens=900 if detail_level == "quick" else 1500,
                temperature=0.12,
            ).strip()
        except Exception:
            logger.exception("Report writer LLM failed; falling back to template draft.")
            return template_draft, f"template:fallback:{self.llm_provider.provider_name}"

        allowed_terms_text = " ".join([title, objective, " ".join(refined_keywords), " ".join(cleaned_notes)])
        sanitized = self._sanitize_llm_draft(generated, cover_block, allowed_terms_text)
        if not sanitized:
            return template_draft, f"template:invalid-llm:{self.llm_provider.provider_name}"
        return sanitized, f"report-llm:{self.llm_provider.provider_name}"

    def _build_llm_report_prompt(
        self,
        *,
        template_draft: str,
        title: str,
        report_type: str,
        report_no: str,
        report_date: str,
        prepared_by: str,
        checked_by: str,
        requested_by: str,
        classification: str,
        objective: str,
        refined_keywords: list[str],
        cleaned_notes: list[str],
        sources: list[dict],
        detail_level: str,
        cover_block: str,
    ) -> str:
        notes_text = "\n".join(f"- {note}" for note in cleaned_notes) if cleaned_notes else "- Kullanici notu yok."
        keywords_text = ", ".join(refined_keywords) if refined_keywords else "Yok."
        sources_text = self._format_sources_for_llm(sources)
        required_sections = (
            "1. GIRDI NOTLARI\n2. KISA SONUC\n3. REFERANS PASAJLAR"
            if detail_level == "quick"
            else (
                "1. GIRIS\n2. TEST VE DEGERLENDIRME YONTEMI\n3. GIRDI VERILERI VE KULLANICI NOTLARI\n"
                "4. BULGULAR VE TEKNIK DEGERLENDIRME\n5. RAPOR METNI TASLAGI\n6. YONETICI OZETI\n"
                "7. YAZIM ICIN DIKKAT EDILECEK NOKTALAR\n8. ACIK NOKTALAR VE DOGRULAMA IHTIYACI\n"
                "9. SONUC VE ONERILEN AKSIYONLAR\n10. REFERANS ALINAN ORNEK PASAJLAR"
            )
        )
        return f"""Sen Anadolu Isuzu teknik rapor yazim editorusun.
Gorevin SADECE rapor govdesini yazmak. Kapak, KAPSAM ve SONUCLAR kod tarafindan eklenecek.
Ilk satirin mutlaka "1." ile baslamali. Baslik disinda markdown, #, kod blogu veya tablo kullanma.
Turkce, resmi ve teknik rapor diliyle yaz.
Sadece kullanici notlari ve verilen kaynak pasajlara dayan. Teknik deger, test sonucu, tarih, arac bilgisi veya kisi adi uydurma.
Veride olmayan veya emin olmadigin her teknik nokta icin "dogrulanmalidir" de.
Kaynak pasajlarda gecen ama rapor basligi, amac, anahtar kelime veya kullanici notunda gecmeyen arac/model adlarini yeni rapora tasima.
Kaynak pasajlari yeni teknik sonuc uretmek icin degil, rapor dili ve dogrulanabilir destek bilgisi icin kullan.
Basliklari tam olarak su sirada kullan:
{required_sections}

Rapor metadata:
Baslik: {title}
Tur: {report_type}
Rapor no: {report_no}
Tarih: {report_date}
Hazirlayan: {prepared_by}
Kontrol: {checked_by}
Talep eden: {requested_by}
Gizlilik: {classification}
Amac: {objective or "Yok."}
Anahtar kelimeler: {keywords_text}

Kullanici notlari:
{notes_text}

Kaynak pasajlar:
{sources_text}

Cikti:
Sadece rapor govdesini yaz. Ilk satir "1." ile baslasin."""

    @staticmethod
    def _sanitize_llm_draft(generated: str, cover_block: str, allowed_terms_text: str) -> str:
        cleaned = generated.strip()
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
        cleaned = re.sub(r"(?m)^\s{0,3}#{1,6}\s*(\d+\.\s+)", r"\1", cleaned)
        cleaned = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", cleaned)
        cleaned = cleaned.replace("**", "")
        match = re.search(r"(?m)^1\.\s+", cleaned)
        body = cleaned[match.start():].strip() if match else ""
        if len(body) < 120 or not re.search(r"(?m)^1\.\s+", body):
            return ""
        body = ReportWriterService._remove_prompt_leakage(body)
        body = ReportWriterService._normalize_llm_section_headings(body)
        body = ReportWriterService._mask_unallowed_vehicle_names(body, allowed_terms_text)
        return f"{cover_block.strip()}\n\n{body.strip()}"

    @staticmethod
    def _remove_prompt_leakage(body: str) -> str:
        blocked_fragments = (
            "gorevin sadece",
            "ilk satirin",
            "basliklari tam olarak",
            "markdown",
            "kod blogu",
            "cikti:",
            "kapak",
            "sen anadolu",
            "turkce, resmi",
            "sadece kullanici",
            "veride olmayan",
            "kaynak pasajlari",
        )
        kept_lines = []
        for line in body.splitlines():
            folded = line.casefold()
            if any(fragment in folded for fragment in blocked_fragments):
                continue
            kept_lines.append(line)
        return "\n".join(kept_lines).strip()

    @staticmethod
    def _normalize_llm_section_headings(body: str) -> str:
        is_quick = "2. KISA" in body.upper() or "KISA SONUC" in body.upper()
        heading_map = {
            "1": "1. GIRDI NOTLARI" if is_quick else "1. GIRIS",
            "2": "2. KISA SONUC" if is_quick else "2. TEST VE DEGERLENDIRME YONTEMI",
            "3": "3. REFERANS PASAJLAR" if is_quick else "3. GIRDI VERILERI VE KULLANICI NOTLARI",
            "4": "4. BULGULAR VE TEKNIK DEGERLENDIRME",
            "5": "5. RAPOR METNI TASLAGI",
            "6": "6. YONETICI OZETI",
            "7": "7. YAZIM ICIN DIKKAT EDILECEK NOKTALAR",
            "8": "8. ACIK NOKTALAR VE DOGRULAMA IHTIYACI",
            "9": "9. SONUC VE ONERILEN AKSIYONLAR",
            "10": "10. REFERANS ALINAN ORNEK PASAJLAR",
        }

        def replace_heading(match: re.Match[str]) -> str:
            number = match.group(1)
            return heading_map.get(number, match.group(0))

        return re.sub(r"(?m)^(\d{1,2})\.\s+.*$", replace_heading, body)

    @staticmethod
    def _mask_unallowed_vehicle_names(body: str, allowed_terms_text: str) -> str:
        allowed = allowed_terms_text.casefold()
        patterns = {
            "goupil": r"\bGoupil\b",
            "citibus": r"\bCITIBUS\b|\bCitibus\b",
            "citiport": r"\bCITIPORT\b|\bCitiport\b",
            "novocitivolt": r"\bNovocitivolt\b|\bNOVOCITIVOLT\b",
            "tase": r"\bTASE\b",
            "big-e": r"\bBIG\s*-\s*E\b|\bBig\s*-\s*E\b|\bBIG-E\b|\bBig-E\b|\bBIG E\b|\bBig E\b",
        }
        cleaned = body
        for key, pattern in patterns.items():
            if key in allowed or key.replace("-", " ") in allowed:
                continue
            cleaned = re.sub(pattern, "referans arac", cleaned)
        return cleaned

    @staticmethod
    def _format_sources_for_llm(sources: list[dict]) -> str:
        if not sources:
            return "Kaynak pasaj yok."
        contexts = []
        budget = max(2400, LLM_MAX_CONTEXT_TOKENS * 2)
        used = 0
        for index, source in enumerate(sources[:4], start=1):
            text = " ".join(str(source.get("chunk_text", "")).split())
            if not text:
                continue
            remaining = max(budget - used, 0)
            if remaining <= 0:
                break
            text = text[:remaining]
            used += len(text)
            contexts.append(
                "\n".join(
                    [
                        f"[Kaynak {index}]",
                        f"Belge: {source.get('document_title', '')}",
                        f"Sayfa: {source.get('page_start', '')}-{source.get('page_end', '')}",
                        f"Bolum: {source.get('section_title', '')}",
                        f"Metin: {text}",
                    ]
                )
            )
        return "\n\n".join(contexts) if contexts else "Kaynak pasaj yok."

    @staticmethod
    def _build_template_cover_text(
        *,
        title: str,
        report_no: str,
        report_date: str,
        prepared_by: str,
        checked_by: str,
        requested_by: str,
        classification: str,
        scope_summary: str,
        result_summary: str,
    ) -> str:
        return "\n".join(
            [
                classification,
                "DEVELOPMENT STATEMENT",
                f"TARIH: {report_date}",
                f"RAPOR NO.: {report_no}",
                f"HAZIRLAYAN: {prepared_by}",
                f"KONTROL: {checked_by}",
                "",
                title.upper(),
                "",
                "KAPSAM:",
                scope_summary,
                "",
                "SONUCLAR:",
                result_summary,
                "",
                f"HAZIRLAYAN: {prepared_by}",
                f"TALEP EDEN: {requested_by}",
            ]
        )

    @staticmethod
    def _build_executive_summary(scope_summary: str, result_summary: str, solution_bullets: list[str]) -> str:
        action = solution_bullets[0] if solution_bullets else "Nihai rapor, teknik ekip dogrulamasindan sonra yayina alinmalidir."
        return (
            f"Bu calisma {scope_summary.rstrip('.').lower()} amaciyla hazirlanmistir. "
            f"One cikan degerlendirme: {result_summary.rstrip('.')} "
            f"Onerilen ilk aksiyon: {action}"
        )

    @staticmethod
    def _build_body_paragraph(
        report_type: str,
        title: str,
        cleaned_notes: list[str],
        refined_keywords: list[str],
        sources: list[dict],
    ) -> str:
        keyword_text = ", ".join(refined_keywords[:5]) if refined_keywords else "ilgili test ve analiz bulgulari"
        note_text = " ".join(cleaned_notes[:3]) if cleaned_notes else "Kullanici tarafindan eklenen sayisal veri ve gozlemler bu bolume yerlestirilmelidir."
        source_text = ""
        if sources:
            source_names = []
            for source in sources[:2]:
                name = source.get("document_title")
                if name and name not in source_names:
                    source_names.append(name)
            if source_names:
                source_text = " Benzer rapor dili acisindan " + ", ".join(source_names) + " kaynaklari dikkate alinmistir."
        return (
            f"Bu {report_type.lower()} kapsaminda {title} konusu; {keyword_text} basliklari uzerinden ele alinmistir. "
            f"{note_text} Test kosullari, varsayimlar ve olcum/analiz sonuclari raporun nihai halinde sayisal degerlerle desteklenmelidir."
            f"{source_text}"
        )

    @staticmethod
    def _build_open_items(cleaned_notes: list[str], sources: list[dict]) -> list[str]:
        items = [
            "- Test kosullari, arac konfigurasyonu ve tarih bilgileri nihai raporda dogrulanmalidir.",
            "- Kritik sayisal degerler tablo veya madde halinde acik verilmelidir.",
            "- Sonuc cumleleri uygunluk, risk veya takip aksiyonu seklinde netlestirilmelidir.",
        ]
        if not cleaned_notes:
            items.append("- Kullanici notu girilmedigi icin raporun teknik bulgu kismi ekip girdisiyle tamamlanmalidir.")
        if not sources:
            items.append("- Benzer rapor kaynagi bulunamadigi icin ifade dili manuel kontrol edilmelidir.")
        return items

    @staticmethod
    def _build_result_summary(cleaned_notes: list[str], sources: list[dict]) -> str:
        if cleaned_notes:
            summary = "Bu taslakta one cikan bulgular: " + "; ".join(cleaned_notes[:3])
            if not summary.endswith("."):
                summary += "."
        else:
            summary = "Belirgin kullanici notu bulunmadigi icin sonuclar bolumu referans raporlar ve verilen amaca gore sekillendirilmelidir."

        if sources:
            source_names = []
            for source in sources[:2]:
                name = source.get("document_title")
                if name and name not in source_names:
                    source_names.append(name)
            if source_names:
                summary += " Referans olarak " + ", ".join(source_names) + " belgeleri dikkate alinmistir."
        return summary

    @staticmethod
    def _build_method_bullets(cleaned_notes: list[str], refined_keywords: list[str]) -> list[str]:
        bullets = [
            "Ilgili raporlar, kullanicinin girdigi anahtar kelimeler ve yuklu dokumanlar uzerinden incelenmelidir.",
            "Test kosullari, olcum suresi, senaryo farklari ve varsa standard referanslari ayri alt satirlarda belirtilmelidir.",
            "Sayisal degerler ve gozlemler, yorum kismindan ayrilarak teknik tutarlilik korunmalidir.",
        ]
        if refined_keywords:
            bullets.append("Ozellikle " + ", ".join(refined_keywords[:5]) + " kavramlari ekseninde bir degerlendirme yapisi kurulmalidir.")
        if cleaned_notes:
            bullets.append("Kullanici notlarinda gecen " + ", ".join(note.rstrip(".") for note in cleaned_notes[:3]) + " maddeleri yontem aciklamasina dahil edilmelidir.")
        return bullets[:5]

    @staticmethod
    def _build_solution_suggestions(refined_keywords: list[str], cleaned_notes: list[str]) -> list[str]:
        suggestions = [
            "Nihai raporda test kosullari ve bulgular arasindaki neden-sonuc iliskisi daha acik kurulmalidir.",
            "Sayisal degerler, senaryolar ve karar cumleleri birbirinden ayrilarak okunabilirlik artirilmalidir.",
            "Benzer raporlardan alinacak ifade bicimi korunurken yeni raporun teknik baglami netlestirilmelidir.",
        ]
        if cleaned_notes:
            suggestions.append("Kullanici notlarindaki kritik maddeler ayri alt basliklar altinda sunulursa rapor daha izlenebilir olur.")
        if refined_keywords:
            suggestions.append("Ozellikle " + ", ".join(refined_keywords[:4]) + " terimlerinin rapor boyunca tutarli kullanilmasi onerilir.")
        return suggestions[:5]


@lru_cache(maxsize=1)
def _build_report_provider() -> LLMProvider:
    if not REPORT_LLM_ENABLED or REPORT_LLM_BACKEND in {"", "disabled", "none"}:
        logger.info("Report writer LLM disabled.")
        return DisabledLLMProvider()
    if REPORT_LLM_BACKEND == "ollama":
        try:
            return OllamaLLMProvider(
                model_name=REPORT_LLM_MODEL_NAME,
                timeout_seconds=REPORT_LLM_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.exception("Report writer Ollama provider could not load.")
            return DisabledLLMProvider()
    logger.warning("Unsupported REPORT_LLM_BACKEND=%s; report writer LLM disabled.", REPORT_LLM_BACKEND)
    return DisabledLLMProvider()
