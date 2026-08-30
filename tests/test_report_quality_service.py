from __future__ import annotations

import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Base, CatalogDocumentLink, Document, DocumentPage, ReportCatalogEntry
from app.services.document_intelligence_service import DocumentIntelligenceService
from app.services.llm_provider import DisabledLLMProvider
from app.services.report_quality_service import ReportQualityService
from app.services.report_review_service import ReportReviewService
from app.services.report_review_export_service import ReportReviewExportService


class FakeSemanticLLMProvider:
    provider_name = "fake-semantic"

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.prompt = ""

    def is_available(self) -> bool:
        return True

    def generate_json(self, prompt: str, schema):
        self.prompt = prompt
        return schema.model_validate(self.payload)


class ReportQualityServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def _add_document(self, title: str, page_texts: list[str]) -> int:
        document = Document(
            title=title,
            file_name=f"{title}.pdf",
            file_type="pdf",
            file_hash=(title.lower().replace("-", "") + "0" * 64)[:64],
            file_path=f"C:/{title}.pdf",
        )
        self.session.add(document)
        self.session.flush()
        for page_number, text in enumerate(page_texts, start=1):
            self.session.add(
                DocumentPage(
                    document_id=document.id,
                    page_number=page_number,
                    raw_text=text,
                    clean_text=text,
                    section_title=None,
                )
            )
        self.session.commit()
        return int(document.id)

    def _link_catalog(
        self,
        document_id: int,
        *,
        report_code: str,
        discipline: str,
        report_title: str,
    ) -> None:
        catalog_entry = ReportCatalogEntry(
            report_code=report_code,
            vehicle_name="SYN",
            report_title=report_title,
            discipline=discipline,
            report_date="2026-08-27",
            authors="TEST HAZIRLAYAN",
            source_path=f"V:\\RAPORLAR\\{report_code}",
            row_hash=(f"profile-{document_id}-{discipline}" + "0" * 64)[:64],
        )
        self.session.add(catalog_entry)
        self.session.flush()
        self.session.add(
            CatalogDocumentLink(
                catalog_entry_id=int(catalog_entry.id),
                document_id=document_id,
                source_path=catalog_entry.source_path,
                match_method="test",
            )
        )
        self.session.commit()

    def test_reports_complete_table_and_figure_sequences(self) -> None:
        document_id = self._add_document(
            "SYN-001",
            [
                "Tablo 1 - Ilk tablo\nSekil 1 - Ilk model",
                "Tablo 2 - Ikinci tablo\nSekil 2 - Ikinci model",
                "Tablo 3 - Son tablo\nSekil 3 - Son model",
            ],
        )

        result = ReportQualityService(self.session).answer_question(
            "SYN-001 raporunda tablo ve sekil numaralandirmasi dogru mu?",
            [document_id],
        )

        self.assertTrue(result["answer_found"])
        self.assertIn("numaralandirmasi dogru gorunuyor", result["answer"])
        self.assertIn("Tablolar: 1, 2, 3", result["answer"])
        self.assertIn("Sekiller: 1, 2, 3", result["answer"])

    def test_reports_missing_duplicate_and_out_of_order_numbers(self) -> None:
        document_id = self._add_document(
            "SYN-002",
            [
                "Tablo 1 - Ilk tablo",
                "Tablo 3 - Ucuncu tablo",
                "Tablo 3 - Tekrarlanan tablo",
                "Tablo 5 - Besinci tablo",
                "Tablo 2 - Ikinci tablo",
            ],
        )

        result = ReportQualityService(self.session).answer_question(
            "SYN-002 tablo numaralandirmasi dogru mu?",
            [document_id],
        )

        self.assertIn("sorun bulundu", result["answer"])
        self.assertIn("tekrar eden: 3", result["answer"])
        self.assertIn("eksik: 4", result["answer"])
        self.assertIn("gecis sirasi bozuk", result["answer"])

    def test_ignores_inline_table_references(self) -> None:
        document_id = self._add_document(
            "SYN-003",
            ["Tablo 1 - Sonuclar\nTablo 1'de sonuclar verilmistir."],
        )
        page = self.session.scalar(select(DocumentPage).where(DocumentPage.document_id == document_id))

        captions = ReportQualityService.extract_captions([page])

        self.assertEqual(["1"], [caption.number_text for caption in captions])

    def test_detects_quality_question_intent(self) -> None:
        question = "2025-BIG-E-DUR-01 bu rapordaki tablo isimlendirmesi dogru mu yapilmis?"
        self.assertEqual("quality", DocumentIntelligenceService._detect_intent(question))

    def test_general_review_passes_complete_deterministic_report(self) -> None:
        document_id = self._add_document(
            "SYN-004",
            [
                (
                    "RAPOR NO: SYN-004\nTARIH: 2026-08-27\nHAZIRLAYAN: TEST\n"
                    "KONTROL: TEST\nKAPSAM\nParca dayanimi incelenmistir."
                ),
                (
                    "SONUCLAR\nTablo 1 - Basinc sonuclari\n"
                    "Tablo 1'de verilen sonuclar kabul kriterini saglamistir."
                ),
            ],
        )

        result = ReportQualityService(self.session).answer_question(
            "SYN-004 raporu kontrol et",
            [document_id],
        )

        self.assertTrue(result["answer_found"])
        self.assertIn("review", result)
        self.assertEqual(0, result["review"]["summary"]["findings"])
        self.assertEqual(8, result["review"]["summary"]["passed"])

    def test_general_review_reports_missing_metadata_and_sections(self) -> None:
        document_id = self._add_document(
            "SYN-005",
            ["GIRIS\nBu belge yalnizca kisa bir teknik aciklama icermektedir."],
        )

        review = ReportQualityService(self.session).analyze_documents([document_id])

        rule_ids = {finding["rule_id"] for finding in review["findings"]}
        self.assertIn("metadata.required_fields", rule_ids)
        self.assertIn("structure.required_sections", rule_ids)
        self.assertGreaterEqual(review["summary"]["needs_review"], 2)

    def test_general_review_uses_linked_catalog_metadata_when_cover_ocr_misses_fields(self) -> None:
        document_id = self._add_document(
            "SYN-005-CATALOG",
            ["KONTROL: TEST\nKAPSAM\nParca incelendi.\nSONUCLAR\nUygun bulundu."],
        )
        catalog_entry = ReportCatalogEntry(
            report_code="SYN-005-CATALOG",
            vehicle_name="SYN",
            report_title="Katalog metadata testi",
            discipline="TEST",
            report_date="2026-08-27",
            authors="TEST HAZIRLAYAN",
            source_path="V:\\RAPORLAR\\SYN-005-CATALOG",
            row_hash="catalog-metadata-test".ljust(64, "0"),
        )
        self.session.add(catalog_entry)
        self.session.flush()
        self.session.add(
            CatalogDocumentLink(
                catalog_entry_id=int(catalog_entry.id),
                document_id=document_id,
                source_path=catalog_entry.source_path,
                match_method="test",
            )
        )
        self.session.commit()

        review = ReportQualityService(self.session).analyze_documents([document_id])

        rule_ids = {finding["rule_id"] for finding in review["findings"]}
        self.assertNotIn("metadata.required_fields", rule_ids)

    def test_auto_profile_detection_applies_all_discipline_rule_sets(self) -> None:
        documents = {
            "nvh": self._add_document(
                "SYN-NVH-001",
                [
                    (
                        "RAPOR NO: SYN-NVH-001 TARIH: 2026-08-27 HAZIRLAYAN: TEST KONTROL: TEST "
                        "KAPSAM Sensor koltuk uzerinde x ekseni yonunde, 50 km/h parkur kosulunda olcum yapti."
                    ),
                    (
                        "SONUCLAR gRMS ve crest faktor, 0-80 Hz frekans araliginda filtre ve "
                        "agirliklandirma ile hesaplandi. ISO 2631 limitine gore sonuc uygun bulundu."
                    ),
                ],
            ),
            "cfd": self._add_document(
                "SYN-CFD-001",
                [
                    (
                        "RAPOR NO: SYN-CFD-001 TARIH: 2026-08-27 HAZIRLAYAN: TEST KONTROL: TEST "
                        "KAPSAM Fluent solver ve k-epsilon modeli kullanildi. Sinir sartlari inlet debi "
                        "ve outlet basinci olarak tanimlandi."
                    ),
                    (
                        "Mesh hucre sayisi ve grid kalitesi raporlandi. Residual convergence ile "
                        "yakinsama izlendi. SONUCLAR Mevcut tasarim 0,108 m3/s, oneri 0,123 m3/s "
                        "debi sagladi ve hedefle karsilastirildi."
                    ),
                ],
            ),
            "durability": self._add_document(
                "SYN-DUR-001",
                [
                    (
                        "RAPOR NO: SYN-DUR-001 TARIH: 2026-08-27 HAZIRLAYAN: TEST KONTROL: TEST "
                        "KAPSAM Malzeme S235, Young modulu ve akma dayanimi tanimlandi. Uygulanan yuk "
                        "10 kN kuvvet, sinir sartlari fixed mesnettir."
                    ),
                    (
                        "Sonlu eleman mesh yapisi, civata baglanti ve contact tanimlari verildi. "
                        "SONUCLAR Von Mises gerilme ve deformasyon, akma dayanimi ve emniyet katsayisi "
                        "ile karsilastirilarak uygun bulundu."
                    ),
                ],
            ),
            "test": self._add_document(
                "SYN-TEST-001",
                [
                    (
                        "RAPOR NO: SYN-TEST-001 TARIH: 2026-08-27 HAZIRLAYAN: TEST KONTROL: TEST "
                        "KAPSAM Arac konfigurasyonu, sicaklik sensoru ve ortam sicakligi kaydedildi. "
                        "Test yontemi 30 dakika 1500 rpm calisma olarak uygulandi."
                    ),
                    (
                        "Cihaz seri no ve kalibrasyon sertifika no kaydedildi. SONUCLAR Kabul kriteri "
                        "maksimum 90 derece C limitidir; test sonucu OK olarak degerlendirildi."
                    ),
                ],
            ),
        }
        disciplines = {
            "nvh": "NVH",
            "cfd": "CFD",
            "durability": "DURABILITY",
            "test": "TEST",
        }
        for profile, document_id in documents.items():
            self._link_catalog(
                document_id,
                report_code=f"SYN-{profile.upper()}-001",
                discipline=disciplines[profile],
                report_title=f"{profile} profil testi",
            )

        review = ReportQualityService(self.session).analyze_documents(list(documents.values()))

        results_by_profile = {item["profile"]: item for item in review["documents"]}
        self.assertEqual(set(documents), set(results_by_profile))
        for profile, result in results_by_profile.items():
            profile_checks = [check for check in result["checks"] if check["category"] == profile]
            self.assertTrue(profile_checks)
            self.assertTrue(all(check["status"] == "pass" for check in profile_checks))

    def test_nvh_profile_marks_missing_frequency_processing_for_review(self) -> None:
        document_id = self._add_document(
            "SYN-NVH-MISSING",
            [
                (
                    "RAPOR NO: SYN-NVH-MISSING TARIH: 2026-08-27 HAZIRLAYAN: TEST KONTROL: TEST "
                    "KAPSAM Sensor koltuk uzerinde x ekseninde, 30 km/h parkur kosulunda olcum yapti."
                ),
                "SONUCLAR gRMS degeri ISO 2631 limitine gore uygun olarak degerlendirildi.",
            ],
        )
        self._link_catalog(
            document_id,
            report_code="SYN-NVH-MISSING",
            discipline="NVH",
            report_title="Eksik sinyal isleme testi",
        )

        review = ReportQualityService(self.session).analyze_documents([document_id])

        self.assertEqual("nvh", review["documents"][0]["profile"])
        finding = next(
            item for item in review["findings"] if item["rule_id"] == "nvh.signal_processing"
        )
        self.assertEqual("needs_review", finding["status"])
        self.assertIn("frekans / filtre / agirliklandirma", finding["message"])

    def test_review_decision_persists_and_pdf_export_includes_review(self) -> None:
        document_id = self._add_document(
            "SYN-REVIEW-DECISION",
            ["KAPSAM Kisa teknik aciklama.\nSONUCLAR Sonuc metni."],
        )
        service = ReportReviewService(self.session)
        review = service.analyze_documents([document_id])
        finding = next(
            item for item in review["findings"] if item["rule_id"] == "metadata.required_fields"
        )

        decision = service.record_decision(
            document_id=document_id,
            finding_key=finding["finding_key"],
            rule_id=finding["rule_id"],
            decision="confirmed",
            note="Kapak alanlari gercekten eksik.",
            reviewer="Test Muhendisi",
        )
        refreshed = service.analyze_documents([document_id])
        refreshed_finding = next(
            item for item in refreshed["findings"] if item["finding_key"] == finding["finding_key"]
        )
        pdf_content = ReportReviewExportService.build_pdf(refreshed)

        self.assertEqual("confirmed", decision["decision"])
        self.assertEqual("confirmed", refreshed_finding["human_decision"])
        self.assertEqual("Kapak alanlari gercekten eksik.", refreshed_finding["human_decision_note"])
        self.assertEqual(1, refreshed["summary"]["human_decisions"]["confirmed"])
        self.assertTrue(pdf_content.startswith(b"%PDF"))
        self.assertGreater(len(pdf_content), 2000)

    def test_revision_review_reports_new_resolved_and_continuing_rules(self) -> None:
        old_document_id = self._add_document(
            "SYN-REV-A",
            [
                (
                    "KAPSAM Eski revizyon incelendi. SONUCLAR Sonuc yazildi. "
                    "Olcumler 1,25 MPa ve 1.50 MPa. DOSYA: V:\\RAPORLAR\\SYN-REV-A"
                )
            ],
        )
        new_document_id = self._add_document(
            "SYN-REV-B",
            [
                (
                    "RAPOR NO: SYN-REV-B TARIH: 2026-08-27 HAZIRLAYAN: TEST KONTROL: TEST "
                    "KAPSAM Yeni revizyon incelendi. Olcumler 1,25 MPa ve 1.50 MPa."
                )
            ],
        )

        result = ReportQualityService(self.session).answer_question(
            "Bu iki raporun rapor kontrolu bulgularini revizyon bazinda karsilastir; "
            "yeni, giderilen ve devam eden bulgulari goster.",
            [old_document_id, new_document_id],
        )

        comparison = result["revision_comparison"]
        self.assertIn("structure.required_sections", comparison["new"])
        self.assertIn("metadata.required_fields", comparison["resolved"])
        self.assertIn("content.embedded_paths", comparison["resolved"])
        self.assertIn("numbers.decimal_style", comparison["continuing"])
        self.assertIn("Yeni bulgular", result["answer"])
        self.assertTrue(any(source.get("review_revision_change") == "resolved" for source in result["sources"]))
        self.assertTrue(all(isinstance(source["page_start"], int) for source in result["sources"]))

    def test_general_review_returns_structured_caption_sequence_finding(self) -> None:
        document_id = self._add_document(
            "SYN-006",
            [
                "RAPOR NO: SYN-006\nTARIH: 2026-08-27\nHAZIRLAYAN: TEST\nKONTROL: TEST\nKAPSAM",
                "Tablo 1 - Ilk tablo\nTablo 3 - Ucuncu tablo\nSONUCLAR",
            ],
        )

        review = ReportQualityService(self.session).analyze_documents([document_id])

        finding = next(item for item in review["findings"] if item["rule_id"] == "captions.sequence")
        self.assertEqual("fail", finding["status"])
        self.assertIn("eksik 2", finding["message"])
        self.assertEqual(2, finding["page_start"])

    def test_general_review_detects_reference_decimal_and_path_issues(self) -> None:
        document_id = self._add_document(
            "SYN-007",
            [
                (
                    "RAPOR NO: SYN-007\nTARIH: 2026-08-27\nHAZIRLAYAN: TEST\nKONTROL: TEST\n"
                    "KAPSAM\nTablo 1 - Basinc degerleri\nOlcumler 1,25 MPa ve 1.50 MPa olarak verildi."
                ),
                (
                    "SONUCLAR\nTablo 2'de kabul degerleri verilmistir.\n"
                    "ANALIZ DOSYASI: V:\\RAPORLAR\\SYN-007"
                ),
            ],
        )

        review = ReportQualityService(self.session).analyze_documents([document_id])

        rule_ids = {finding["rule_id"] for finding in review["findings"]}
        self.assertIn("captions.references", rule_ids)
        self.assertIn("numbers.decimal_style", rule_ids)
        self.assertIn("content.embedded_paths", rule_ids)

        result = ReportQualityService(self.session).answer_question("SYN-007 raporu kontrol et", [document_id])
        review_sources = [source for source in result["sources"] if source["source_kind"] == "report_review"]
        self.assertTrue(review_sources)
        reference_source = next(
            source for source in review_sources if source["review_rule_id"] == "captions.references"
        )
        self.assertEqual("warning", reference_source["review_severity"])
        self.assertTrue(reference_source["review_message"])
        self.assertTrue(reference_source["suggested_fix"])
        self.assertTrue(reference_source["review_highlight_available"])

        finding = next(item for item in review["findings"] if item["rule_id"] == "captions.references")
        requests = ReportReviewService(self.session)._highlight_requests_for_finding(finding)
        self.assertTrue(requests)
        self.assertEqual(1, requests[0].page_start)

    def test_detects_general_report_review_intent(self) -> None:
        self.assertEqual(
            "quality",
            DocumentIntelligenceService._detect_intent("Bu raporu kontrol et, hata veya eksik var mi?"),
        )

    def test_quality_review_honors_selected_document_context(self) -> None:
        selected_document_id = self._add_document(
            "SYN-SELECTED",
            ["Yalnizca secilen rapora ait kisa kontrol metni."],
        )
        self._add_document(
            "SYN-UNSELECTED",
            ["Arama sonucundan gelmemesi gereken baska bir rapor metni."],
        )

        result = DocumentIntelligenceService(
            self.session,
            llm_provider=DisabledLLMProvider(),
        ).answer_question(
            "Secili raporu kontrol et",
            context_document_ids=[selected_document_id],
        )

        analyzed_titles = {item["document_title"] for item in result["review"]["documents"]}
        self.assertEqual({"SYN-SELECTED"}, analyzed_titles)
        self.assertEqual(1, result["review"]["summary"]["documents_analyzed"])

    def test_semantic_review_accepts_only_page_verified_quotes(self) -> None:
        scope_quote = "KAPSAM: Tasarimin 10 kN yuk altindaki davranisi incelenecektir."
        result_quote = "SONUCLAR: Tasarim 15 kN yuk altinda uygun kabul edilmistir."
        document_id = self._add_document(
            "SYN-SEM-001",
            [
                (
                    "RAPOR NO: SYN-SEM-001 TARIH: 2026-08-27 HAZIRLAYAN: TEST KONTROL: TEST "
                    + scope_quote
                    + " Sinir sartlari ve malzeme bilgileri tanimlanmistir."
                ),
                result_quote + " Emniyet katsayisi ayrica raporlanmistir.",
            ],
        )
        provider = FakeSemanticLLMProvider(
            {
                "findings": [
                    {
                        "rule_id": "semantic.scope_result_alignment",
                        "severity": "warning",
                        "message": "Kapsam ile sonuc farkli yuk seviyelerini esas aliyor.",
                        "evidence": [
                            {"page": 1, "quote": scope_quote},
                            {"page": 2, "quote": result_quote},
                        ],
                        "suggested_fix": "Kapsam ve sonuc yuk seviyelerini ayni kabul kosuluna baglayin.",
                        "confidence": 0.94,
                    },
                    {
                        "rule_id": "semantic.internal_contradiction",
                        "severity": "warning",
                        "message": "Bu bulgu uydurma bir alinti tasiyor.",
                        "evidence": [
                            {"page": 1, "quote": "Bu cumle raporda kesinlikle yoktur."},
                            {"page": 2, "quote": result_quote},
                        ],
                        "suggested_fix": "Metni kontrol edin.",
                        "confidence": 0.99,
                    },
                ]
            }
        )

        result = ReportQualityService(self.session).answer_question(
            "Bu raporu kontrol et",
            [document_id],
            llm_provider=provider,
        )

        semantic_findings = [
            finding for finding in result["review"]["findings"] if finding["engine"].startswith("llm:")
        ]
        self.assertEqual(1, len(semantic_findings))
        self.assertEqual("semantic.scope_result_alignment", semantic_findings[0]["rule_id"])
        self.assertIn(scope_quote, provider.prompt)
        self.assertIn("LLM destekli anlamsal kontrol tamamlandi", result["answer"])
        self.assertIn("rapor ici yapisal ve anlamsal incelemedir", result["answer"])
        semantic_source = next(
            source for source in result["sources"] if source.get("review_engine", "").startswith("llm:")
        )
        self.assertFalse(semantic_source["review_highlight_available"])
        self.assertEqual("fake-semantic", result["review"]["semantic"]["provider"])

    def test_semantic_review_marks_short_content_not_applicable(self) -> None:
        document_id = self._add_document("SYN-SEM-SHORT", ["Kisa rapor metni."])
        provider = FakeSemanticLLMProvider({"findings": []})

        result = ReportQualityService(self.session).answer_question(
            "Bu raporu kontrol et",
            [document_id],
            llm_provider=provider,
        )

        self.assertEqual("not_applicable", result["review"]["semantic"]["status"])
        self.assertEqual("", provider.prompt)


if __name__ == "__main__":
    unittest.main()
