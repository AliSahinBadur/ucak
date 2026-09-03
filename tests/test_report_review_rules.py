"""Rule-by-rule coverage of the report review catalog, plus the precision report.

`tests/test_report_quality_service.py` covers the review flow end to end -- how a
question routes to it, how findings reach the answer and the PDF. This module
covers the *catalog*: every `rule_id` the engine can emit is asserted here or
there, which the meta-tests at the bottom enforce so a new rule cannot be added
without a test.

Each profile rule is driven by a document that satisfies its other requirement
groups and misses exactly one, so the assertion pins the specific group the rule
is meant to notice rather than "some finding appeared". The complementary
"complete report passes" direction is covered by
`test_auto_profile_detection_applies_all_discipline_rule_sets`.

Everything here is deterministic: no LLM except a scripted fake, no embeddings,
no network.
"""

from __future__ import annotations

from pathlib import Path
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import (
    Base,
    CatalogDocumentLink,
    Document,
    DocumentPage,
    ReportCatalogEntry,
    ReportReviewDecision,
)
from app.processing import extraction_metrics
from app.services.report_quality_service import ReportQualityService
from app.services.report_review_service import ReportReviewService


COVER = "RAPOR NO: {code} TARIH: 2026-08-27 HAZIRLAYAN: TEST KONTROL: TEST"


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


class ReportReviewRuleCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    # --- fixtures -------------------------------------------------------------

    def _add_document(self, code: str, page_texts: list[str], *, discipline: str = "") -> int:
        document = Document(
            title=code,
            file_name=f"{code}.pdf",
            file_type="pdf",
            file_hash=(code.lower().replace("-", "") + "0" * 64)[:64],
            file_path=f"C:/{code}.pdf",
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
                    extraction_method="native",
                    ocr_attempted=False,
                    char_count=extraction_metrics.char_count(text),
                    word_count=extraction_metrics.word_count(text),
                )
            )
        if discipline:
            # The catalog discipline pins the profile, so a rule test does not
            # depend on the title-pattern fallback in _resolve_document_profile.
            entry = ReportCatalogEntry(
                report_code=code,
                vehicle_name="SYN",
                report_title=f"{code} profil testi",
                discipline=discipline,
                report_date="2026-08-27",
                authors="TEST HAZIRLAYAN",
                source_path=f"V:\\RAPORLAR\\{code}",
                row_hash=(f"rule-{code}-{discipline}" + "0" * 64)[:64],
            )
            self.session.add(entry)
            self.session.flush()
            self.session.add(
                CatalogDocumentLink(
                    catalog_entry_id=int(entry.id),
                    document_id=int(document.id),
                    source_path=entry.source_path,
                    match_method="test",
                )
            )
        self.session.commit()
        return int(document.id)

    def _finding(self, document_id: int, rule_id: str, *, profile: str = "auto") -> dict:
        review = ReportReviewService(self.session).analyze_documents([document_id], profile=profile)
        matches = [item for item in review["findings"] if item["rule_id"] == rule_id]
        self.assertEqual(
            1,
            len(matches),
            f"expected exactly one {rule_id} finding, got "
            f"{[item['rule_id'] for item in review['findings']]}",
        )
        return matches[0]

    def _assert_missing_group(
        self,
        code: str,
        page_texts: list[str],
        *,
        discipline: str,
        rule_id: str,
        missing_label: str,
        severity: str = "warning",
    ) -> dict:
        """A profile rule fires as needs_review and names the group it missed."""
        document_id = self._add_document(code, page_texts, discipline=discipline)
        finding = self._finding(document_id, rule_id)
        self.assertEqual("needs_review", finding["status"])
        self.assertEqual(severity, finding["severity"])
        self.assertIn(missing_label, finding["message"])
        self.assertTrue(finding["suggested_fix"])
        return finding

    # --- general rules --------------------------------------------------------

    def test_captions_title_fails_for_a_numbered_item_without_a_title(self) -> None:
        document_id = self._add_document(
            "SYN-CAPTION-TITLE",
            [
                COVER.format(code="SYN-CAPTION-TITLE")
                + " KAPSAM Braket dayanimi incelenmistir ve olcumler raporlanmistir.",
                # Numbering is complete, so captions.sequence stays quiet and the
                # only thing wrong with Tablo 2 is that it has no title.
                "SONUCLAR Tablo 1 - Basinc sonuclari\nTablo 2\n"
                "Tablo 1'de ve Tablo 2'de verilen sonuclar kabul kriterini saglamistir.",
            ],
        )

        finding = self._finding(document_id, "captions.title")

        self.assertEqual("fail", finding["status"])
        self.assertIn("Tablo 2", finding["message"])
        self.assertEqual(2, finding["page_start"])

    def test_captions_title_is_not_applicable_without_any_caption(self) -> None:
        document_id = self._add_document(
            "SYN-CAPTION-NONE",
            [
                COVER.format(code="SYN-CAPTION-NONE")
                + " KAPSAM Braket dayanimi incelenmistir.",
                "SONUCLAR Olculen degerler kabul kriterinin altinda kalmistir.",
            ],
        )

        review = ReportReviewService(self.session).analyze_documents([document_id])

        status = next(
            check["status"]
            for check in review["documents"][0]["checks"]
            if check["rule_id"] == "captions.title"
        )
        self.assertEqual("not_applicable", status)

    # --- NVH profile ----------------------------------------------------------

    def test_nvh_measurement_setup_flags_a_missing_measurement_axis(self) -> None:
        self._assert_missing_group(
            "SYN-NVH-SETUP",
            [
                COVER.format(code="SYN-NVH-SETUP")
                + " KAPSAM Sensor koltuk uzerinden yerlestirildi, 50 km/h parkur kosulunda olcum yapildi.",
                "SONUCLAR gRMS ve crest faktor 0-80 Hz frekans araliginda filtre ile hesaplandi. "
                "ISO 2631 limitine gore sonuc uygun bulundu.",
            ],
            discipline="NVH",
            rule_id="nvh.measurement_setup",
            missing_label="eksen / olcum yonu",
        )

    def test_nvh_acceptance_basis_flags_a_result_with_no_standard_or_limit(self) -> None:
        self._assert_missing_group(
            "SYN-NVH-ACCEPT",
            [
                COVER.format(code="SYN-NVH-ACCEPT")
                + " KAPSAM Sensor koltuk uzerinden x ekseni yonunde, 50 km/h parkur kosulunda olcum yapildi.",
                # A verdict with nothing behind it: no standard, no threshold.
                "SONUCLAR gRMS ve crest faktor 0-80 Hz frekans araliginda filtre ile hesaplandi "
                "ve degerlendirme sonucunda uygun bulundu.",
            ],
            discipline="NVH",
            rule_id="nvh.acceptance_basis",
            missing_label="standart / limit / kabul kriteri",
        )

    # --- CFD profile ----------------------------------------------------------

    def test_cfd_model_boundary_setup_flags_missing_boundary_conditions(self) -> None:
        self._assert_missing_group(
            "SYN-CFD-BOUNDARY",
            [
                COVER.format(code="SYN-CFD-BOUNDARY")
                + " KAPSAM Fluent solver ve k-epsilon turbulans modeli kullanildi.",
                "Mesh hucre sayisi ve grid kalitesi raporlandi, residual convergence ile yakinsama izlendi. "
                "SONUCLAR Mevcut tasarim 0,108 m3/s degeri ile hedefe gore karsilastirildi.",
            ],
            discipline="CFD",
            rule_id="cfd.model_boundary_setup",
            missing_label="sinir sartlari",
        )

    def test_cfd_numerical_evidence_flags_a_mesh_with_no_convergence_record(self) -> None:
        self._assert_missing_group(
            "SYN-CFD-NUMERIC",
            [
                COVER.format(code="SYN-CFD-NUMERIC")
                + " KAPSAM Fluent solver ve k-epsilon modeli, inlet ve outlet sinir sartlari tanimlandi.",
                "Mesh hucre sayisi ve grid kalitesi raporlandi. "
                "SONUCLAR Mevcut tasarim 0,108 m3/s degeri ile hedefe gore karsilastirildi.",
            ],
            discipline="CFD",
            rule_id="cfd.numerical_evidence",
            missing_label="yakinsama / zaman adimi",
        )

    def test_cfd_result_traceability_flags_a_verdict_with_no_measured_value(self) -> None:
        self._assert_missing_group(
            "SYN-CFD-RESULT",
            [
                COVER.format(code="SYN-CFD-RESULT")
                + " KAPSAM Fluent solver ve k-epsilon modeli, inlet ve outlet sinir sartlari tanimlandi.",
                "Mesh hucre sayisi ve grid kalitesi raporlandi, residual convergence ile yakinsama izlendi. "
                # "Uygun bulundu" with no number behind it is exactly what this
                # rule exists to catch.
                "SONUCLAR Mevcut tasarim hedefle karsilastirildi ve uygun bulundu.",
            ],
            discipline="CFD",
            rule_id="cfd.result_traceability",
            missing_label="birimli sonuc",
        )

    # --- Durability profile ---------------------------------------------------

    def test_durability_material_definition_flags_an_undefined_material(self) -> None:
        self._assert_missing_group(
            "SYN-DUR-MATERIAL",
            [
                COVER.format(code="SYN-DUR-MATERIAL")
                + " KAPSAM Uygulanan yuk 10 kN kuvvet, sinir sartlari fixed mesnettir.",
                "Sonlu eleman mesh yapisi, civata baglanti ve contact tanimlari verildi. "
                "SONUCLAR Von Mises gerilme ve deformasyon emniyet katsayisi ile karsilastirildi.",
            ],
            discipline="DURABILITY",
            rule_id="durability.material_definition",
            missing_label="malzeme ve mekanik ozellik",
        )

    def test_durability_load_boundary_setup_flags_a_load_with_no_support(self) -> None:
        self._assert_missing_group(
            "SYN-DUR-LOAD",
            [
                COVER.format(code="SYN-DUR-LOAD")
                + " KAPSAM Malzeme S235, elastisite modulu ve akma dayanimi tanimlandi. "
                "Uygulanan yuk 10 kN kuvvettir.",
                "Sonlu eleman mesh yapisi, civata baglanti ve contact tanimlari verildi. "
                "SONUCLAR Von Mises gerilme ve deformasyon akma dayanimi ile karsilastirildi.",
            ],
            discipline="DURABILITY",
            rule_id="durability.load_boundary_setup",
            missing_label="sinir sartlari / mesnet",
        )

    def test_durability_model_evidence_flags_a_mesh_with_no_connection_definition(self) -> None:
        self._assert_missing_group(
            "SYN-DUR-MODEL",
            [
                COVER.format(code="SYN-DUR-MODEL")
                + " KAPSAM Malzeme S235, elastisite modulu ve akma dayanimi tanimlandi. "
                "Uygulanan yuk 10 kN kuvvet, sinir sartlari fixed mesnettir.",
                "Sonlu eleman mesh yapisi ve eleman boyutu verildi. "
                "SONUCLAR Von Mises gerilme ve deformasyon akma dayanimi ile karsilastirildi.",
            ],
            discipline="DURABILITY",
            rule_id="durability.model_evidence",
            missing_label="baglanti / temas tanimi",
        )

    def test_durability_result_criterion_flags_a_stress_result_with_no_acceptance_basis(self) -> None:
        self._assert_missing_group(
            "SYN-DUR-RESULT",
            [
                COVER.format(code="SYN-DUR-RESULT")
                + " KAPSAM Malzeme S235 ve elastisite modulu tanimlandi. "
                "Uygulanan yuk 10 kN kuvvet, sinir sartlari fixed mesnettir.",
                "Sonlu eleman mesh yapisi, civata baglanti ve contact tanimlari verildi. "
                # A stress number with nothing to compare it against.
                "SONUCLAR Von Mises gerilme ve deformasyon degerleri hesaplandi.",
            ],
            discipline="DURABILITY",
            rule_id="durability.result_criterion",
            missing_label="kabul dayanagi",
        )

    # --- Test / validation profile -------------------------------------------

    def test_test_setup_traceability_flags_a_setup_with_no_instrument(self) -> None:
        self._assert_missing_group(
            "SYN-TEST-SETUP",
            [
                COVER.format(code="SYN-TEST-SETUP")
                + " KAPSAM Arac konfigurasyonu kaydedildi, ortam sicakligi olculdu.",
                "Test yontemi 30 dakika 1500 rpm calisma olarak uygulandi. Kalibrasyon sertifika no kaydedildi. "
                "SONUCLAR Kabul kriteri maksimum 90 derece C limitidir; test sonucu OK olarak degerlendirildi.",
            ],
            discipline="TEST",
            rule_id="test.setup_traceability",
            missing_label="olcum cihazi / sensor",
        )

    def test_test_procedure_traceability_flags_a_run_with_no_stated_method(self) -> None:
        self._assert_missing_group(
            "SYN-TEST-PROCEDURE",
            [
                COVER.format(code="SYN-TEST-PROCEDURE")
                + " KAPSAM Arac konfigurasyonu, sicaklik sensoru ve ortam sicakligi kaydedildi.",
                "Calisma 30 dakika 1500 rpm olarak yurutuldu. Cihaz seri no ve kalibrasyon kaydedildi. "
                "SONUCLAR Kabul kriteri maksimum 90 derece C limitidir; test sonucu OK olarak degerlendirildi.",
            ],
            discipline="TEST",
            rule_id="test.procedure_traceability",
            missing_label="yontem / prosedur",
        )

    def test_test_acceptance_result_flags_a_verdict_with_no_criterion(self) -> None:
        self._assert_missing_group(
            "SYN-TEST-ACCEPT",
            [
                COVER.format(code="SYN-TEST-ACCEPT")
                + " KAPSAM Arac konfigurasyonu, sicaklik sensoru ve ortam sicakligi kaydedildi.",
                "Test yontemi 30 dakika 1500 rpm calisma olarak uygulandi. "
                "Cihaz seri no ve kalibrasyon sertifika no kaydedildi. "
                # A pass/fail call with no criterion to justify it.
                "SONUCLAR Test sonucu OK olarak degerlendirildi.",
            ],
            discipline="TEST",
            rule_id="test.acceptance_result",
            missing_label="kabul kriteri / limit",
        )

    def test_test_measurement_traceability_flags_uncalibrated_instruments(self) -> None:
        self._assert_missing_group(
            "SYN-TEST-CALIB",
            [
                COVER.format(code="SYN-TEST-CALIB")
                + " KAPSAM Arac konfigurasyonu, sicaklik sensoru ve ortam sicakligi kaydedildi.",
                "Test yontemi 30 dakika 1500 rpm calisma olarak uygulandi. "
                "SONUCLAR Kabul kriteri maksimum 90 derece C limitidir; test sonucu OK olarak degerlendirildi.",
            ],
            discipline="TEST",
            rule_id="test.measurement_traceability",
            missing_label="kalibrasyon / cihaz kimligi",
            # Calibration is a record-keeping gap, not a result the reader can
            # be misled by, so this rule reports at info severity.
            severity="info",
        )

    # --- semantic.unsupported_conclusion -------------------------------------
    #
    # The one semantic rule the flow tests do not reach. It is gated on the LLM
    # having seen the *whole* report: a conclusion cannot be called unsupported
    # from a partial reading.

    def _semantic_findings(self, document_id: int, provider) -> list[dict]:
        result = ReportQualityService(self.session).answer_question(
            "Bu raporu kontrol et",
            [document_id],
            llm_provider=provider,
        )
        return [
            finding
            for finding in result["review"]["findings"]
            if finding["engine"].startswith("llm:")
        ]

    @staticmethod
    def _unsupported_payload(quote: str, page: int = 2) -> dict:
        return {
            "findings": [
                {
                    "rule_id": "semantic.unsupported_conclusion",
                    "severity": "warning",
                    "message": "Sonuc, rapor icinde bir olcum veya hesaba dayandirilmamis.",
                    "evidence": [{"page": page, "quote": quote}],
                    "suggested_fix": "Sonucu dayandigi olcum veya hesap ile iliskilendirin.",
                    "confidence": 0.91,
                }
            ]
        }

    def test_semantic_unsupported_conclusion_is_accepted_when_the_whole_report_was_read(self) -> None:
        conclusion = "SONUCLAR: Tasarim guvenli kabul edilmistir."
        document_id = self._add_document(
            "SYN-SEM-UNSUPPORTED",
            [
                COVER.format(code="SYN-SEM-UNSUPPORTED")
                + " KAPSAM: Braket dayanimi incelenmistir ve olcumler degerlendirilmistir.",
                conclusion + " Ek bir olcum veya hesap raporda paylasilmamistir.",
            ],
        )
        provider = FakeSemanticLLMProvider(self._unsupported_payload(conclusion))

        findings = self._semantic_findings(document_id, provider)

        self.assertEqual(1, len(findings))
        self.assertEqual("semantic.unsupported_conclusion", findings[0]["rule_id"])
        self.assertEqual("needs_review", findings[0]["status"])
        self.assertIn(conclusion, findings[0]["evidence"][0])
        self.assertIn("Sonuclarin dayanagi kontrolu: ACIK", provider.prompt)

    def test_semantic_unsupported_conclusion_is_dropped_when_only_part_was_read(self) -> None:
        conclusion = "SONUCLAR: Tasarim guvenli kabul edilmistir."
        # Pages 3..10 carry no scope/result keyword and are not in the last two,
        # so the context window holds only part of the report.
        filler = [
            f"Ara sayfa {number}: olcum tablosu ve grafik aciklamalari yer almaktadir. "
            "Bu bolum yalnizca ham veri listelemektedir."
            for number in range(3, 11)
        ]
        document_id = self._add_document(
            "SYN-SEM-PARTIAL",
            [
                COVER.format(code="SYN-SEM-PARTIAL")
                + " KAPSAM: Braket dayanimi incelenmistir ve olcumler degerlendirilmistir.",
                conclusion + " Ek bir olcum veya hesap raporda paylasilmamistir.",
                *filler,
            ],
        )
        provider = FakeSemanticLLMProvider(self._unsupported_payload(conclusion))

        findings = self._semantic_findings(document_id, provider)

        self.assertEqual([], findings)
        self.assertIn("Sonuclarin dayanagi kontrolu: KAPALI", provider.prompt)


class ReportReviewCatalogCoverageTests(unittest.TestCase):
    """The acceptance criterion for Phase 1, enforced instead of asserted once.

    `checks_run` counts the rules the engine executed. If a rule can run, a test
    must assert on it -- otherwise the review summary claims coverage the suite
    does not have.
    """

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_every_catalog_rule_id_is_asserted_somewhere_in_the_suite(self) -> None:
        suite_source = "\n".join(
            path.read_text(encoding="utf-8") for path in sorted(Path(__file__).parent.glob("*.py"))
        )

        untested = [
            rule_id
            for rule_id in ReportReviewService.catalog_rule_ids()
            if f'"{rule_id}"' not in suite_source
        ]

        self.assertEqual(
            [],
            untested,
            "rules the engine can emit but no test asserts on: " + ", ".join(untested),
        )

    def test_checks_run_equals_the_number_of_rules_active_for_the_profile(self) -> None:
        document = Document(
            title="SYN-CHECKS-RUN",
            file_name="SYN-CHECKS-RUN.pdf",
            file_type="pdf",
            file_hash="c" * 64,
            file_path="C:/SYN-CHECKS-RUN.pdf",
        )
        self.session.add(document)
        self.session.flush()
        text = (
            "RAPOR NO: SYN-CHECKS-RUN TARIH: 2026-08-27 HAZIRLAYAN: TEST KONTROL: TEST "
            "KAPSAM Braket dayanimi incelenmistir. SONUCLAR Uygun bulunmustur."
        )
        self.session.add(
            DocumentPage(
                document_id=document.id,
                page_number=1,
                raw_text=text,
                clean_text=text,
                char_count=extraction_metrics.char_count(text),
                word_count=extraction_metrics.word_count(text),
                extraction_method="native",
                ocr_attempted=False,
            )
        )
        self.session.commit()

        # Driven by the loaded catalog, not a list here: a discipline added as a
        # data file is covered by this test the moment its file exists.
        for profile in ("general", *ReportReviewService.PROFILE_RULES):
            with self.subTest(profile=profile):
                review = ReportReviewService(self.session).analyze_documents(
                    [int(document.id)], profile=profile
                )
                expected = len(ReportReviewService.RULES) + len(
                    ReportReviewService.PROFILE_RULES.get(profile, ())
                )
                self.assertEqual(expected, review["summary"]["checks_run"])
                self.assertEqual(expected, len(review["documents"][0]["checks"]))

    def test_catalog_rule_ids_covers_general_profile_and_semantic_rules(self) -> None:
        rule_ids = ReportReviewService.catalog_rule_ids()

        self.assertEqual(len(rule_ids), len(set(rule_ids)), "duplicate rule_id in the catalog")
        for rule in ReportReviewService.RULES:
            self.assertIn(rule.rule_id, rule_ids)
        for rules in ReportReviewService.PROFILE_RULES.values():
            for rule in rules:
                self.assertIn(rule.rule_id, rule_ids)
        for rule_id in ReportReviewService.SEMANTIC_RULE_LABELS:
            self.assertIn(rule_id, rule_ids)


class RulePrecisionReportTests(unittest.TestCase):
    """Rule precision from the decisions engineers already recorded (F3)."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.document_ids = [self._add_document(index) for index in range(1, 4)]
        self.service = ReportReviewService(self.session)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def _add_document(self, index: int) -> int:
        document = Document(
            title=f"SYN-PRECISION-{index}",
            file_name=f"SYN-PRECISION-{index}.pdf",
            file_type="pdf",
            file_hash=(f"precision{index}" + "0" * 64)[:64],
            file_path=f"C:/SYN-PRECISION-{index}.pdf",
        )
        self.session.add(document)
        self.session.flush()
        self.session.commit()
        return int(document.id)

    def _record(self, rule_id: str, decision: str, count: int, *, document_index: int = 0) -> None:
        document_id = self.document_ids[document_index]
        for serial in range(count):
            self.session.add(
                ReportReviewDecision(
                    document_id=document_id,
                    finding_key=f"{rule_id}-{decision}-{document_index}-{serial}",
                    rule_id=rule_id,
                    decision=decision,
                )
            )
        self.session.commit()

    def _rule(self, report: dict, rule_id: str) -> dict:
        return next(item for item in report["rules"] if item["rule_id"] == rule_id)

    def test_precision_is_confirmed_over_confirmed_plus_dismissed(self) -> None:
        self._record("captions.sequence", "confirmed", 9)
        self._record("captions.sequence", "dismissed", 3)

        rule = self._rule(self.service.rule_precision_report(), "captions.sequence")

        self.assertEqual("measured", rule["status"])
        self.assertEqual(9, rule["confirmed"])
        self.assertEqual(3, rule["dismissed"])
        self.assertEqual(12, rule["decided"])
        self.assertEqual(0.75, rule["precision"])

    def test_open_findings_are_counted_but_excluded_from_the_ratio(self) -> None:
        # Undecided is not disagreement: 5 open findings must not drag a rule
        # that a human confirmed every time down to 50%.
        self._record("metadata.required_fields", "confirmed", 10)
        self._record("metadata.required_fields", "open", 5)

        rule = self._rule(self.service.rule_precision_report(), "metadata.required_fields")

        self.assertEqual(5, rule["open"])
        self.assertEqual(10, rule["decided"])
        self.assertEqual(1.0, rule["precision"])

    def test_a_rule_below_the_threshold_reports_insufficient_data_not_a_number(self) -> None:
        self._record("numbers.decimal_style", "dismissed", 9)

        rule = self._rule(self.service.rule_precision_report(), "numbers.decimal_style")

        self.assertEqual("insufficient_data", rule["status"])
        self.assertIsNone(rule["precision"])
        self.assertEqual(9, rule["decided"])

    def test_the_threshold_is_configurable(self) -> None:
        self._record("numbers.decimal_style", "dismissed", 9)

        rule = self._rule(
            self.service.rule_precision_report(minimum_decisions=5), "numbers.decimal_style"
        )

        self.assertEqual("measured", rule["status"])
        self.assertEqual(0.0, rule["precision"])

    def test_every_catalog_rule_is_listed_even_with_no_decisions(self) -> None:
        report = self.service.rule_precision_report()

        listed = {rule["rule_id"] for rule in report["rules"]}
        self.assertEqual(set(ReportReviewService.catalog_rule_ids()), listed)
        self.assertTrue(all(rule["in_catalog"] for rule in report["rules"]))
        self.assertEqual(len(listed), report["summary"]["insufficient_data"])
        self.assertEqual(0, report["summary"]["measured"])

    def test_a_retired_rule_id_keeps_its_history_and_is_marked(self) -> None:
        # extraction.sparse_pages was split into extraction.no_text and
        # extraction.ocr_low_quality; its old decisions must stay visible rather
        # than disappearing from the table.
        self._record("extraction.sparse_pages", "dismissed", 11)

        report = self.service.rule_precision_report()

        rule = self._rule(report, "extraction.sparse_pages")
        self.assertFalse(rule["in_catalog"])
        self.assertEqual(0.0, rule["precision"])
        self.assertEqual(1, report["summary"]["retired"])

    def test_rules_are_ordered_worst_confirm_rate_first(self) -> None:
        self._record("captions.sequence", "confirmed", 10)
        self._record("captions.references", "confirmed", 2)
        self._record("captions.references", "dismissed", 8)
        self._record("content.embedded_paths", "confirmed", 5)
        self._record("content.embedded_paths", "dismissed", 5)

        report = self.service.rule_precision_report()

        measured = [rule["rule_id"] for rule in report["rules"] if rule["status"] == "measured"]
        self.assertEqual(
            ["captions.references", "content.embedded_paths", "captions.sequence"], measured
        )
        # Measured rules come before every undecidable one.
        first_insufficient = next(
            index
            for index, rule in enumerate(report["rules"])
            if rule["status"] == "insufficient_data"
        )
        self.assertEqual(len(measured), first_insufficient)

    def test_the_report_can_be_scoped_to_selected_documents(self) -> None:
        self._record("captions.sequence", "confirmed", 10, document_index=0)
        self._record("captions.sequence", "dismissed", 10, document_index=1)

        scoped = self.service.rule_precision_report(document_ids=[self.document_ids[0]])
        everything = self.service.rule_precision_report()

        self.assertEqual(1.0, self._rule(scoped, "captions.sequence")["precision"])
        self.assertEqual(1, self._rule(scoped, "captions.sequence")["documents"])
        self.assertEqual(0.5, self._rule(everything, "captions.sequence")["precision"])
        self.assertEqual(2, self._rule(everything, "captions.sequence")["documents"])

    def test_summary_totals_add_up(self) -> None:
        self._record("captions.sequence", "confirmed", 6)
        self._record("captions.sequence", "dismissed", 4)
        self._record("captions.title", "open", 3)

        summary = self.service.rule_precision_report()["summary"]

        self.assertEqual(6, summary["confirmed"])
        self.assertEqual(4, summary["dismissed"])
        self.assertEqual(3, summary["open"])
        self.assertEqual(10, summary["decided"])
        self.assertEqual(1, summary["measured"])
        self.assertEqual(len(ReportReviewService.catalog_rule_ids()) - 1, summary["insufficient_data"])


if __name__ == "__main__":
    unittest.main()
