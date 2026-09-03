"""The discipline rule catalog as data (`app/rules/profiles/*.json`).

`tests/test_report_review_rules.py` asserts what each shipped rule *notices*.
This module asserts the thing that made those rules data in the first place:

- adding a discipline check -- a new rule, or a whole new discipline -- is a
  data edit plus a golden case, with no Python change (`NewDisciplineTests`);
- a malformed data file fails loudly at load time, naming the file and the path
  inside it, instead of quietly producing a rule that never fires
  (`ProfileCatalogValidationTests`).

Everything here is deterministic: no LLM, no embeddings, no network.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import (
    Base,
    CatalogDocumentLink,
    Document,
    DocumentPage,
    ReportCatalogEntry,
)
from app.processing import extraction_metrics
from app.rules.profile_catalog import (
    PROFILES_DIR,
    ProfileCatalogError,
    discipline_profiles,
    load_profile_directory,
)
from app.services.report_review_service import ReportReviewService, build_profile_maps


# A discipline that does not exist in app/rules/profiles: if the engine runs it,
# it ran it from data alone.
THERMAL_PROFILE = {
    "profile": "thermal",
    "label": "Termal",
    "detect_priority": 25,
    "aliases": ["thermal", "termal", "isil"],
    "detect_patterns": [r"\bthermal\b", r"termal analiz"],
    "rules": [
        {
            "rule_id": "thermal.boundary_setup",
            "label": "Termal sinir sartlari",
            "category": "thermal",
            "severity": "warning",
            "message": "Termal analizin sinir sartlari raporda tam izlenemiyor.",
            "suggested_fix": "Ortam sicakligini ve isi tasinim katsayisini degerleriyle yazin.",
            "requirement_groups": [
                {"label": "ortam sicakligi", "aliases": ["ortam sicakligi", "ambient"]},
                {"label": "tasinim katsayisi", "aliases": ["tasinim katsayisi", "htc"]},
            ],
        }
    ],
}


def _write_profile(directory: Path, payload: dict, *, name: str | None = None) -> Path:
    path = directory / f"{name or payload['profile']}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class ShippedCatalogTests(unittest.TestCase):
    """The catalog the app actually loads."""

    def test_every_profile_rule_is_data_and_every_general_rule_is_code(self) -> None:
        for profile, rules in ReportReviewService.PROFILE_RULES.items():
            for rule in rules:
                with self.subTest(rule_id=rule.rule_id):
                    self.assertIsNotNone(
                        rule.requirement,
                        f"{rule.rule_id} should come from app/rules/profiles/{profile}.json",
                    )
                    self.assertEqual("", rule.handler_name)
                    self.assertEqual(rule.rule_id, rule.requirement.rule_id)
                    self.assertEqual(rule.category, rule.requirement.category)

        for rule in ReportReviewService.RULES:
            with self.subTest(rule_id=rule.rule_id):
                self.assertIsNone(rule.requirement)
                self.assertTrue(
                    hasattr(ReportReviewService, rule.handler_name),
                    f"{rule.rule_id} names a handler that does not exist: {rule.handler_name}",
                )

    def test_profiles_are_ordered_by_the_detect_priority_they_declare(self) -> None:
        # _resolve_document_profile keeps the first pattern match, so the order
        # is behaviour, not presentation.
        priorities = [profile.detect_priority for profile in discipline_profiles()]
        self.assertEqual(sorted(priorities), priorities)
        self.assertEqual(len(set(priorities)), len(priorities), "ambiguous detection order")

    def test_labels_and_aliases_cover_every_shipped_discipline(self) -> None:
        for profile in discipline_profiles():
            with self.subTest(profile=profile.name):
                self.assertEqual(profile.label, ReportReviewService.PROFILE_LABELS[profile.name])
                self.assertEqual(profile.name, ReportReviewService._normalize_profile(profile.name))
                for alias in profile.aliases:
                    self.assertEqual(profile.name, ReportReviewService._normalize_profile(alias))


class NewDisciplineTests(unittest.TestCase):
    """Phase 3 acceptance: a discipline check is a data edit, not a Python change."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self._temp = tempfile.TemporaryDirectory()
        self.profiles_dir = Path(self._temp.name) / "profiles"
        shutil.copytree(PROFILES_DIR, self.profiles_dir)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()
        self._temp.cleanup()

    def _installed(self):
        """Load the edited directory and hand it to the engine, as import does."""
        profiles = load_profile_directory(self.profiles_dir)
        labels, aliases, rules = build_profile_maps(profiles)
        return patch.multiple(
            ReportReviewService,
            DISCIPLINE_PROFILES=profiles,
            PROFILE_LABELS=labels,
            PROFILE_ALIASES=aliases,
            PROFILE_RULES=rules,
        )

    def _add_document(self, code: str, page_texts: list[str]) -> int:
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
                    extraction_method="native",
                    ocr_attempted=False,
                    char_count=extraction_metrics.char_count(text),
                    word_count=extraction_metrics.word_count(text),
                )
            )
        self.session.commit()
        return int(document.id)

    def test_a_new_discipline_file_is_detected_labelled_and_run(self) -> None:
        _write_profile(self.profiles_dir, THERMAL_PROFILE)
        document_id = self._add_document(
            "SYN-THERMAL-01",
            [
                "RAPOR NO: SYN-THERMAL-01 TARIH: 2026-08-27 HAZIRLAYAN: TEST KONTROL: TEST "
                "KAPSAM Batarya paketi termal analiz calismasi yapilmistir.",
                # Ambient is stated, the convection coefficient is not: the new
                # rule should name exactly that group.
                "Ortam sicakligi 25 derece C alinmistir. SONUCLAR Sicaklik dagilimi uygundur.",
            ],
        )

        with self._installed():
            review = ReportReviewService(self.session).analyze_documents([document_id])

        document = review["documents"][0]
        self.assertEqual("thermal", document["profile"])
        self.assertEqual("Termal", document["profile_label"])

        finding = next(
            item for item in review["findings"] if item["rule_id"] == "thermal.boundary_setup"
        )
        self.assertEqual("needs_review", finding["status"])
        self.assertEqual("warning", finding["severity"])
        self.assertEqual("thermal", finding["category"])
        self.assertIn("tasinim katsayisi", finding["message"])
        self.assertNotIn("ortam sicakligi", finding["message"])
        self.assertEqual(
            "Ortam sicakligini ve isi tasinim katsayisini degerleriyle yazin.",
            finding["suggested_fix"],
        )
        self.assertEqual("rules", finding["engine"])

    def test_a_new_rule_in_a_shipped_discipline_needs_no_python_change(self) -> None:
        path = self.profiles_dir / "nvh.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["rules"].append(
            {
                "rule_id": "nvh.operator_note",
                "label": "NVH operator notu",
                "category": "nvh",
                "severity": "info",
                "message": "Olcumu yapan operator raporda belirtilmemis.",
                "suggested_fix": "Olcumu yapan kisiyi rapora ekleyin.",
                "requirement_groups": [
                    {"label": "operator", "aliases": ["olcumu yapan", "operator"]}
                ],
            }
        )
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        document_id = self._add_document(
            "SYN-NVH-KAYIT",
            [
                "RAPOR NO: SYN-NVH-KAYIT TARIH: 2026-08-27 HAZIRLAYAN: TEST KONTROL: TEST "
                "KAPSAM NVH olcumu yapilmistir.",
                "SONUCLAR Olcum tamamlanmistir.",
            ],
        )

        with self._installed():
            review = ReportReviewService(self.session).analyze_documents(
                [document_id], profile="nvh"
            )
            expected_checks = len(ReportReviewService.RULES) + len(
                ReportReviewService.PROFILE_RULES["nvh"]
            )
            self.assertIn("nvh.operator_note", ReportReviewService.catalog_rule_ids())

        self.assertEqual(expected_checks, review["summary"]["checks_run"])
        finding = next(
            item for item in review["findings"] if item["rule_id"] == "nvh.operator_note"
        )
        self.assertEqual("info", finding["severity"])
        self.assertIn("operator", finding["message"])

    def test_a_catalog_discipline_reaches_an_alias_through_the_same_folding(self) -> None:
        # The catalog discipline column is free text an operator typed. It is
        # folded exactly like the alias keys, so "Isıl / Termal" finds the
        # alias "isil termal" rather than missing on the slash.
        payload = json.loads(json.dumps(THERMAL_PROFILE))
        payload["aliases"] = ["isil termal"]
        _write_profile(self.profiles_dir, payload)
        document_id = self._add_document(
            "SYN-KATALOG-01",
            [
                "RAPOR NO: SYN-KATALOG-01 TARIH: 2026-08-27 HAZIRLAYAN: TEST KONTROL: TEST "
                "KAPSAM Batarya paketi incelenmistir.",
                "Ortam sicakligi 25 derece C alinmistir. SONUCLAR Uygundur.",
            ],
        )
        entry = ReportCatalogEntry(
            report_code="SYN-KATALOG-01",
            vehicle_name="SYN",
            report_title="SYN-KATALOG-01 katalog testi",
            discipline="Is\u0131l  /  Termal",
            report_date="2026-08-27",
            authors="TEST HAZIRLAYAN",
            source_path="V:\\RAPORLAR\\SYN-KATALOG-01",
            row_hash=("catalog-thermal" + "0" * 64)[:64],
        )
        self.session.add(entry)
        self.session.flush()
        self.session.add(
            CatalogDocumentLink(
                catalog_entry_id=int(entry.id),
                document_id=document_id,
                source_path=entry.source_path,
                match_method="test",
            )
        )
        self.session.commit()

        with self._installed():
            review = ReportReviewService(self.session).analyze_documents([document_id])

        self.assertEqual("thermal", review["documents"][0]["profile"])

    def test_removing_a_discipline_file_removes_its_rules(self) -> None:
        (self.profiles_dir / "cfd.json").unlink()

        with self._installed():
            self.assertNotIn("cfd", ReportReviewService.PROFILE_RULES)
            self.assertNotIn("cfd", ReportReviewService.PROFILE_LABELS)
            self.assertEqual("general", ReportReviewService._normalize_profile("cfd"))
            self.assertNotIn(
                "cfd.numerical_evidence", ReportReviewService.catalog_rule_ids()
            )


class ProfileCatalogValidationTests(unittest.TestCase):
    """A bad data edit fails at load, naming the file and the path inside it."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.directory = Path(self._temp.name)

    def tearDown(self) -> None:
        self._temp.cleanup()

    def _assert_rejects(self, payload: dict, *, expected: str, name: str | None = None) -> None:
        _write_profile(self.directory, payload, name=name)
        with self.assertRaises(ProfileCatalogError) as caught:
            load_profile_directory(self.directory)
        self.assertIn(expected, str(caught.exception))

    def _thermal(self, **overrides) -> dict:
        payload = json.loads(json.dumps(THERMAL_PROFILE))
        payload.update(overrides)
        return payload

    def test_the_fixture_profile_is_valid_on_its_own(self) -> None:
        _write_profile(self.directory, THERMAL_PROFILE)
        profiles = load_profile_directory(self.directory)
        self.assertEqual(("thermal",), tuple(profile.name for profile in profiles))
        self.assertEqual(1, len(profiles[0].rules))

    def test_an_unknown_key_is_rejected_rather_than_ignored(self) -> None:
        # The whole point: a typo must not silently disable part of a rule.
        payload = self._thermal()
        payload["alises"] = ["termal"]
        self._assert_rejects(payload, expected="unknown key(s) alises")

    def test_a_missing_key_names_the_key(self) -> None:
        payload = self._thermal()
        del payload["detect_patterns"]
        self._assert_rejects(payload, expected="missing key(s) detect_patterns")

    def test_the_profile_name_must_match_the_file_name(self) -> None:
        self._assert_rejects(
            self._thermal(),
            expected="does not match the file name",
            name="thermik",
        )

    def test_general_and_auto_are_reserved(self) -> None:
        payload = self._thermal(profile="general")
        payload["rules"][0]["rule_id"] = "general.boundary_setup"
        self._assert_rejects(payload, expected="reserved", name="general")

    def test_a_rule_id_must_be_prefixed_with_its_profile(self) -> None:
        payload = self._thermal()
        payload["rules"][0]["rule_id"] = "cfd.boundary_setup"
        self._assert_rejects(payload, expected="must start with 'thermal.'")

    def test_an_unknown_severity_is_rejected(self) -> None:
        payload = self._thermal()
        payload["rules"][0]["severity"] = "blocker"
        self._assert_rejects(payload, expected="rules[0].severity")

    def test_a_rule_needs_at_least_one_requirement_group(self) -> None:
        payload = self._thermal()
        payload["rules"][0]["requirement_groups"] = []
        self._assert_rejects(payload, expected="rules[0].requirement_groups")

    def test_a_group_needs_at_least_one_alias(self) -> None:
        payload = self._thermal()
        payload["rules"][0]["requirement_groups"][0]["aliases"] = []
        self._assert_rejects(payload, expected="requirement_groups[0].aliases")

    def test_an_empty_alias_is_rejected(self) -> None:
        # An empty alias is a substring of every report, so the group would
        # always pass and the rule would never fire again.
        payload = self._thermal()
        payload["rules"][0]["requirement_groups"][0]["aliases"] = ["ambient", "   "]
        self._assert_rejects(payload, expected="requirement_groups[0].aliases[1]")

    def test_a_duplicate_group_label_is_rejected(self) -> None:
        payload = self._thermal()
        payload["rules"][0]["requirement_groups"][1]["label"] = "ortam sicakligi"
        self._assert_rejects(payload, expected="duplicate group label(s) 'ortam sicakligi'")

    def test_an_uncompilable_detect_pattern_is_rejected(self) -> None:
        self._assert_rejects(
            self._thermal(detect_patterns=[r"termal ("]),
            expected="profile.detect_patterns[0]: invalid regex",
        )

    def test_a_duplicate_rule_id_inside_one_file_is_rejected(self) -> None:
        payload = self._thermal()
        payload["rules"].append(json.loads(json.dumps(payload["rules"][0])))
        self._assert_rejects(
            payload, expected="duplicate rule_id thermal.boundary_setup"
        )

    def test_a_rule_id_the_general_catalog_already_owns_is_rejected(self) -> None:
        # Two checks sharing one rule_id would merge their recorded human
        # decisions, so the rule-precision table would report a blend of both.
        payload = self._thermal(profile="captions", detect_priority=99)
        payload["rules"][0]["rule_id"] = "captions.sequence"
        _write_profile(self.directory, payload, name="captions")
        profiles = load_profile_directory(self.directory)

        with self.assertRaises(ProfileCatalogError) as caught:
            build_profile_maps(
                profiles,
                reserved_rule_ids=[rule.rule_id for rule in ReportReviewService.RULES],
            )
        self.assertIn("captions.json:captions.sequence", str(caught.exception))

    def test_a_duplicate_alias_inside_a_group_is_rejected(self) -> None:
        payload = self._thermal()
        payload["rules"][0]["requirement_groups"][0]["aliases"] = ["ambient", "ambient"]
        self._assert_rejects(payload, expected="duplicate entries 'ambient'")

    def test_wrongly_typed_values_are_rejected(self) -> None:
        cases = {
            "label is not a string": (lambda p: p.update(label=7), "profile.label"),
            "detect_priority is a bool": (
                lambda p: p.update(detect_priority=True),
                "profile.detect_priority",
            ),
            "rules is not a list": (lambda p: p.update(rules={}), "profile.rules"),
            "a rule is not an object": (lambda p: p.update(rules=["thermal.x"]), "rules[0]"),
            "a group is not an object": (
                lambda p: p["rules"][0].update(requirement_groups=["ambient"]),
                "requirement_groups[0]",
            ),
            "aliases is not a list": (
                lambda p: p["rules"][0]["requirement_groups"][0].update(aliases="ambient"),
                "requirement_groups[0].aliases",
            ),
        }
        for name, (mutate, expected) in cases.items():
            with self.subTest(case=name):
                payload = self._thermal()
                mutate(payload)
                self._assert_rejects(payload, expected=expected)

    def test_a_json_file_that_is_not_an_object_is_rejected(self) -> None:
        (self.directory / "thermal.json").write_text("[]", encoding="utf-8")
        with self.assertRaises(ProfileCatalogError) as caught:
            load_profile_directory(self.directory)
        self.assertIn("must be a JSON object", str(caught.exception))

    def test_invalid_json_names_the_file(self) -> None:
        (self.directory / "thermal.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(ProfileCatalogError) as caught:
            load_profile_directory(self.directory)
        self.assertIn("thermal.json", str(caught.exception))
        self.assertIn("invalid JSON", str(caught.exception))

    def test_an_empty_directory_is_an_error_not_an_empty_catalog(self) -> None:
        with self.assertRaises(ProfileCatalogError) as caught:
            load_profile_directory(self.directory)
        self.assertIn("no discipline profiles", str(caught.exception))

    def test_a_missing_directory_is_an_error(self) -> None:
        with self.assertRaises(ProfileCatalogError) as caught:
            load_profile_directory(self.directory / "nope")
        self.assertIn("not found", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
