from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy.orm import Session

from .search_service import SearchService


class ReportWriterService:
    _FONT_READY = False
    _FONT_BODY = "Helvetica"
    _FONT_BOLD = "Helvetica-Bold"

    def __init__(self, session: Session) -> None:
        self.session = session
        self.search_service = SearchService(session)

    def build_draft(
        self,
        title: str,
        report_type: str,
        objective: str,
        keywords: str,
        raw_notes: str,
        detail_level: str = "detailed",
        mode: str = "hybrid",
        limit: int = 5,
    ) -> dict:
        cleaned_title = " ".join(title.split())
        cleaned_report_type = " ".join(report_type.split()) or "Genel Teknik Rapor"
        cleaned_objective = self._clean_sentence(objective)
        cleaned_notes = self._clean_notes(raw_notes)
        refined_keywords = self._refine_keywords(keywords, cleaned_title, cleaned_objective, cleaned_notes)
        retrieval_query = self._build_retrieval_query(cleaned_title, cleaned_objective, refined_keywords, cleaned_notes)
        sources = self._run_search(retrieval_query, mode=mode, limit=limit) if retrieval_query else []
        draft = self._compose_draft(
            title=cleaned_title,
            report_type=cleaned_report_type,
            objective=cleaned_objective,
            refined_keywords=refined_keywords,
            cleaned_notes=cleaned_notes,
            sources=sources,
            detail_level=detail_level,
        )
        return {
            "title": cleaned_title,
            "report_type": cleaned_report_type,
            "detail_level": detail_level,
            "draft": draft,
            "refined_keywords": refined_keywords,
            "cleaned_notes": cleaned_notes,
            "embedding_provider": self.search_service.embedding_provider_name(),
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

        story = [
            Paragraph(xml_escape(draft_payload["title"]), title_style),
            Paragraph(
                xml_escape(
                    f"Tur: {draft_payload['report_type']} | Seviye: {draft_payload['detail_level']} | Provider: {draft_payload['embedding_provider']}"
                ),
                meta_style,
            ),
        ]

        for raw_line in draft_payload["draft"].splitlines():
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
            if "," in stripped and len(stripped) < 120:
                comma_parts = [item.strip() for item in stripped.split(",") if item.strip()]
                if len(comma_parts) > 1:
                    for item in comma_parts:
                        normalized = self._clean_sentence(item)
                        if normalized and normalized not in notes:
                            notes.append(normalized)
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

        if detail_level == "quick":
            summary_lines = [
                title.upper(),
                "",
                "KAPSAM:",
                scope_summary,
                "",
                "SONUCLAR:",
                result_summary,
                "",
                "ANA NOTLAR:",
                scope_section,
                "",
                "KISA SONUC:",
                conclusion,
            ]
            if source_snippets:
                summary_lines.extend(
                    [
                        "",
                        "REFERANS PASAJLAR:",
                        "\n".join(source_snippets[:2]),
                    ]
                )
            return "\n".join(summary_lines).strip()

        sections = [
            title.upper(),
            "",
            "KAPSAM:",
            scope_summary,
            "",
            "SONUCLAR:",
            result_summary,
            "",
            "GIRIS",
            " ".join(intro_parts),
            "",
            "TEST VE DEGERLENDIRME YONTEMI",
            "\n".join(f"- {item}" for item in method_bullets),
            "",
            "GIRDI NOTLARI",
            scope_section,
            "",
            "TASLAK DEGERLENDIRME METNI",
            "Bu bolumde kullanicidan gelen notlar, daha okunabilir ve rapora uygun bir dille duzenlenmelidir. Girdiler arasindaki iliski acik kurulmalidir; test senaryolari, olcum kosullari ve teknik bulgular mumkun oldugunca ayri cumlelerde verilmelidir.",
            "",
            "YAZIM ICIN ONERILEN NOKTALAR",
            "\n".join(findings_lines),
            "",
            "SONUC",
            conclusion,
            "",
            "COZUM ONERILERI",
            "\n".join(f"- {item}" for item in solution_bullets),
        ]

        if source_snippets:
            sections.extend(
                [
                    "",
                    "REFERANS ALINAN ORNEK PASAJLAR",
                    "\n".join(source_snippets),
                ]
            )

        return "\n".join(sections).strip()

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
