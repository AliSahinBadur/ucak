from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class ReportReviewExportService:
    _font_ready = False
    _font_body = "Helvetica"
    _font_bold = "Helvetica-Bold"

    @classmethod
    def build_pdf(cls, review: dict) -> bytes:
        cls._ensure_fonts()
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title="SmartCAE AI Rapor Kontrol Kaydi",
            author="SmartCAE AI",
        )
        styles = cls._styles()
        summary = review.get("summary", {})
        story = [
            Paragraph("SMARTCAE AI", styles["overline"]),
            Paragraph("Rapor Kontrol Kaydı", styles["title"]),
            Paragraph(
                f"Oluşturulma: {datetime.now().astimezone().strftime('%d.%m.%Y %H:%M')} · "
                f"İncelenen rapor: {summary.get('documents_analyzed', 0)}",
                styles["meta"],
            ),
            Spacer(1, 6 * mm),
            cls._summary_table(summary, styles),
            Spacer(1, 5 * mm),
            Paragraph(
                "Bu çıktı rapor içi yapı, izlenebilirlik ve tutarlılık kontrolüdür; "
                "mühendislik sonucunun fiziksel doğruluğunu onaylamaz.",
                styles["notice"],
            ),
            Spacer(1, 7 * mm),
        ]

        documents = review.get("documents", [])
        for document_index, item in enumerate(documents):
            if document_index:
                story.append(PageBreak())
            checks = item.get("checks", [])
            findings = item.get("findings", [])
            passed = sum(1 for check in checks if check.get("status") == "pass")
            review_needed = sum(
                1 for check in checks if check.get("status") in {"fail", "needs_review"}
            )
            story.extend(
                [
                    Paragraph(escape(str(item.get("document_title") or "Rapor")), styles["document_title"]),
                    Paragraph(
                        f"Dosya: {escape(str(item.get('file_name') or '-'))} · "
                        f"Profil: {escape(str(item.get('profile_label') or 'Genel'))} · "
                        f"{item.get('page_count', 0)} sayfa · {passed} geçen · {review_needed} inceleme",
                        styles["meta"],
                    ),
                    Spacer(1, 4 * mm),
                ]
            )
            if not findings:
                story.append(Paragraph("Etkin kontrollerde raporlanacak bulgu bulunmadı.", styles["pass_box"]))
                continue
            for finding_index, finding in enumerate(findings, start=1):
                story.append(cls._finding_block(finding_index, finding, styles))
                story.append(Spacer(1, 3 * mm))

        document.build(story, onFirstPage=cls._page_footer, onLaterPages=cls._page_footer)
        return buffer.getvalue()

    @classmethod
    def _summary_table(cls, summary: dict, styles: dict[str, ParagraphStyle]) -> Table:
        decisions = summary.get("human_decisions", {})
        cells = (
            ("Kontrol", summary.get("checks_run", 0)),
            ("Bulgu", summary.get("findings", 0)),
            ("Onaylı", decisions.get("confirmed", 0)),
            ("Geçersiz", decisions.get("dismissed", 0)),
            ("Açık", decisions.get("open", summary.get("findings", 0))),
        )
        table = Table(
            [[Paragraph(label, styles["metric_label"]), Paragraph(str(value), styles["metric_value"])] for label, value in cells],
            colWidths=[31 * mm, 14 * mm] * 0 + [31 * mm, 14 * mm],
        )
        # Keep the summary compact and readable as a two-column ledger.
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F8F7")),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#C9D9D4")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DCE7E3")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return table

    @classmethod
    def _finding_block(cls, index: int, finding: dict, styles: dict[str, ParagraphStyle]) -> KeepTogether:
        severity = str(finding.get("severity") or "warning")
        severity_label = {"critical": "KRİTİK", "warning": "UYARI", "info": "BİLGİ"}.get(severity, "KONTROL")
        decision = str(finding.get("human_decision") or "open")
        decision_label = {"confirmed": "Onaylandı", "dismissed": "Geçersiz", "open": "Açık"}.get(decision, "Açık")
        page_start = finding.get("page_start")
        page_end = finding.get("page_end") or page_start
        page_label = "Sayfa belirtilmedi"
        if page_start:
            page_label = f"Sayfa {page_start}" if page_start == page_end else f"Sayfa {page_start}-{page_end}"

        evidence = finding.get("evidence") or []
        parts = [
            Table(
                [[
                    Paragraph(f"{index}. {severity_label}", styles[f"severity_{severity}" if severity in {"critical", "warning", "info"} else "severity_warning"]),
                    Paragraph(escape(decision_label), styles["decision"]),
                ]],
                colWidths=[120 * mm, 50 * mm],
                style=TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (1, 0), "RIGHT")]),
            ),
            Paragraph(escape(str(finding.get("message") or "Kontrol bulgusu")), styles["finding_title"]),
            Paragraph(
                f"{escape(str(finding.get('rule_id') or '-'))} · {page_label}",
                styles["meta"],
            ),
        ]
        if finding.get("suggested_fix"):
            parts.append(
                Paragraph(
                    f"<b>Öneri:</b> {escape(str(finding['suggested_fix']))}",
                    styles["body"],
                )
            )
        if evidence:
            parts.append(Paragraph("<b>Kanıt:</b>", styles["body"]))
            for excerpt in evidence[:2]:
                compact = " ".join(str(excerpt).split())
                parts.append(Paragraph(escape(compact[:700]), styles["evidence"]))
        if finding.get("human_decision_note"):
            parts.append(
                Paragraph(
                    f"<b>İnceleme notu:</b> {escape(str(finding['human_decision_note']))}",
                    styles["body"],
                )
            )
        return KeepTogether(parts)

    @classmethod
    def _styles(cls) -> dict[str, ParagraphStyle]:
        base = getSampleStyleSheet()["BodyText"]
        return {
            "overline": ParagraphStyle("ReviewOverline", parent=base, fontName=cls._font_bold, fontSize=8, textColor=colors.HexColor("#16745E"), spaceAfter=3),
            "title": ParagraphStyle("ReviewTitle", parent=base, fontName=cls._font_bold, fontSize=22, leading=26, textColor=colors.HexColor("#173A32")),
            "document_title": ParagraphStyle("ReviewDocument", parent=base, fontName=cls._font_bold, fontSize=15, leading=19, textColor=colors.HexColor("#203B35")),
            "finding_title": ParagraphStyle("ReviewFinding", parent=base, fontName=cls._font_bold, fontSize=10, leading=14, textColor=colors.HexColor("#2D3533"), spaceBefore=3, spaceAfter=3),
            "body": ParagraphStyle("ReviewBody", parent=base, fontName=cls._font_body, fontSize=8.5, leading=12, textColor=colors.HexColor("#364541"), spaceBefore=3),
            "evidence": ParagraphStyle("ReviewEvidence", parent=base, fontName=cls._font_body, fontSize=7.5, leading=10.5, leftIndent=7, borderColor=colors.HexColor("#D7E3DF"), borderWidth=0.5, borderPadding=5, backColor=colors.HexColor("#F8FAF9"), textColor=colors.HexColor("#52605D"), spaceBefore=2),
            "meta": ParagraphStyle("ReviewMeta", parent=base, fontName=cls._font_body, fontSize=7.5, leading=10, textColor=colors.HexColor("#6B7774"), spaceAfter=2),
            "notice": ParagraphStyle("ReviewNotice", parent=base, fontName=cls._font_body, fontSize=8, leading=11, borderColor=colors.HexColor("#BCD6CE"), borderWidth=0.7, borderPadding=7, backColor=colors.HexColor("#F1F8F5"), textColor=colors.HexColor("#31574D")),
            "pass_box": ParagraphStyle("ReviewPass", parent=base, fontName=cls._font_bold, fontSize=9, leading=12, borderColor=colors.HexColor("#A9D3C2"), borderWidth=0.7, borderPadding=8, backColor=colors.HexColor("#EFF9F4"), textColor=colors.HexColor("#176548")),
            "metric_label": ParagraphStyle("ReviewMetricLabel", parent=base, fontName=cls._font_body, fontSize=8, textColor=colors.HexColor("#65736F")),
            "metric_value": ParagraphStyle("ReviewMetricValue", parent=base, fontName=cls._font_bold, fontSize=11, alignment=TA_CENTER, textColor=colors.HexColor("#173A32")),
            "decision": ParagraphStyle("ReviewDecision", parent=base, fontName=cls._font_bold, fontSize=8, alignment=2, textColor=colors.HexColor("#16745E")),
            "severity_critical": ParagraphStyle("ReviewCritical", parent=base, fontName=cls._font_bold, fontSize=8, textColor=colors.HexColor("#A9283B")),
            "severity_warning": ParagraphStyle("ReviewWarning", parent=base, fontName=cls._font_bold, fontSize=8, textColor=colors.HexColor("#A05A00")),
            "severity_info": ParagraphStyle("ReviewInfo", parent=base, fontName=cls._font_bold, fontSize=8, textColor=colors.HexColor("#276B9D")),
        }

    @classmethod
    def _ensure_fonts(cls) -> None:
        if cls._font_ready:
            return
        regular = next((path for path in (Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\DejaVuSans.ttf")) if path.exists()), None)
        bold = next((path for path in (Path(r"C:\Windows\Fonts\arialbd.ttf"), Path(r"C:\Windows\Fonts\DejaVuSans-Bold.ttf")) if path.exists()), None)
        if regular and bold:
            pdfmetrics.registerFont(TTFont("ReviewBody", str(regular)))
            pdfmetrics.registerFont(TTFont("ReviewBold", str(bold)))
            cls._font_body = "ReviewBody"
            cls._font_bold = "ReviewBold"
        cls._font_ready = True

    @staticmethod
    def _page_footer(canvas, document) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D9E4E0"))
        canvas.line(16 * mm, 12 * mm, 194 * mm, 12 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#78837F"))
        canvas.drawString(16 * mm, 8 * mm, "SmartCAE AI · Rapor Kontrol Kaydı")
        canvas.drawRightString(194 * mm, 8 * mm, f"Sayfa {document.page}")
        canvas.restoreState()
