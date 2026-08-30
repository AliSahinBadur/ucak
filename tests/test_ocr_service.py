from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pymupdf

from app.parsers.pdf_parser import parse_pdf
from app.services.ocr_service import SelectiveOCRService


class SelectiveOCRServiceTests(unittest.TestCase):
    def test_ocr_reads_an_image_only_pdf_page(self) -> None:
        ocr_service = SelectiveOCRService()
        if not ocr_service.available:
            self.skipTest("Local Tesseract language data is unavailable.")

        with TemporaryDirectory() as temp_dir:
            image_pdf_path = Path(temp_dir) / "image-only.pdf"
            source = pymupdf.open()
            source_page = source.new_page(width=800, height=400)
            source_page.insert_text(
                (60, 130),
                "TABLO 1 - OCR KALITE KONTROLU",
                fontsize=24,
                fontname="helv",
            )
            pixmap = source_page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)

            image_pdf = pymupdf.open()
            image_page = image_pdf.new_page(width=800, height=400)
            image_page.insert_image(image_page.rect, stream=pixmap.tobytes("png"))
            image_pdf.save(image_pdf_path)
            image_pdf.close()
            source.close()

            sections = parse_pdf(image_pdf_path)

        self.assertEqual(1, len(sections))
        self.assertEqual("ocr", sections[0].extraction_method)
        self.assertIn("OCR KALITE", sections[0].raw_text.upper())


if __name__ == "__main__":
    unittest.main()
