"""Report drafting on the template path (no report LLM configured).

`REPORT_LLM_ENABLED=false` in conftest means `_build_report_provider()` hands
back `DisabledLLMProvider`, so `build_draft` composes the deterministic template
draft and reports "template" as its generation provider -- exactly the shape the
app degrades to when Ollama is absent.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.report_writer_service import ReportWriterService


@pytest.fixture
def writer(db_session) -> ReportWriterService:
    return ReportWriterService(db_session)


# --- build_draft -------------------------------------------------------------


def test_detailed_draft_has_the_full_nine_section_skeleton(writer, seed_corpus) -> None:
    payload = writer.build_draft(title="Yorulma Olcumleri", report_type="Dayanim", mode="keyword")

    headings = [line for line in payload["draft"].splitlines() if line[:3].strip().rstrip(".").isdigit()]
    assert headings[:9] == [
        "1. GIRIS",
        "2. TEST VE DEGERLENDIRME YONTEMI",
        "3. GIRDI VERILERI VE KULLANICI NOTLARI",
        "4. BULGULAR VE TEKNIK DEGERLENDIRME",
        "5. RAPOR METNI TASLAGI",
        "6. YONETICI OZETI",
        "7. YAZIM ICIN DIKKAT EDILECEK NOKTALAR",
        "8. ACIK NOKTALAR VE DOGRULAMA IHTIYACI",
        "9. SONUC VE ONERILEN AKSIYONLAR",
    ]
    assert payload["detail_level"] == "detailed"
    assert payload["generation_provider"] == "template"


def test_quick_draft_collapses_to_the_short_skeleton(writer, seed_corpus) -> None:
    payload = writer.build_draft(title="Yorulma Olcumleri", report_type="Dayanim", detail_level="quick")

    headings = [line for line in payload["draft"].splitlines() if line[:3].strip().rstrip(".").isdigit()]
    assert headings[:2] == ["1. GIRDI NOTLARI", "2. KISA SONUC"]
    assert payload["detail_level"] == "quick"


def test_draft_cites_the_retrieved_passages(writer, seed_corpus) -> None:
    payload = writer.build_draft(title="Yorulma Olcumleri", report_type="Dayanim", mode="keyword")

    assert [item["document_id"] for item in payload["sources"]] == [
        seed_corpus["durability"].id,
        seed_corpus["nvh"].id,
    ]
    assert "10. REFERANS ALINAN ORNEK PASAJLAR" in payload["draft"]
    assert "Torku" in payload["draft"]


def test_draft_without_matching_sources_omits_the_reference_section(writer, seed_corpus) -> None:
    payload = writer.build_draft(title="Hidrojen Yakit Hucresi", report_type="Genel", mode="keyword")

    assert payload["sources"] == []
    assert "10. REFERANS ALINAN ORNEK PASAJLAR" not in payload["draft"]


def test_draft_can_be_scoped_to_chosen_documents(writer, seed_corpus) -> None:
    payload = writer.build_draft(
        title="Olcum Ozeti",
        report_type="Genel",
        mode="keyword",
        document_ids=[seed_corpus["nvh"].id],
    )

    assert {item["document_id"] for item in payload["sources"]} <= {seed_corpus["nvh"].id}


def test_draft_fills_in_the_cover_defaults(writer, seed_corpus) -> None:
    payload = writer.build_draft(title="Yorulma Olcumleri", report_type="")

    assert payload["report_type"] == "Genel Teknik Rapor"
    assert payload["report_no"] == "TASLAK"
    assert payload["report_date"] == date.today().strftime("%d.%m.%Y")
    assert payload["prepared_by"] == "-"
    assert payload["checked_by"] == "-"
    assert payload["requested_by"] == "-"
    assert payload["classification"] == "GENEL / PUBLIC"


def test_draft_lifts_the_report_number_out_of_the_title(writer, seed_corpus) -> None:
    payload = writer.build_draft(title="2025-BIG-E-DUR-02 Dayanim Dogrulama", report_type="Dayanim")

    assert payload["report_no"] == "2025-BIG-E-DUR-02"


def test_draft_keeps_an_explicit_report_number(writer, seed_corpus) -> None:
    payload = writer.build_draft(title="Dayanim", report_type="Dayanim", report_no=" AR-GE-77 ")

    assert payload["report_no"] == "AR-GE-77"


def test_draft_normalises_notes_and_keywords(writer, seed_corpus) -> None:
    payload = writer.build_draft(
        title="Sasi Dayanim",
        report_type="Dayanim",
        keywords="yorulma, ve, rapor",
        raw_notes="- torku parkurunda olcum yapildi\n- ek takviye onerildi",
    )

    assert payload["cleaned_notes"] == [
        "Torku parkurunda olcum yapildi.",
        "Ek takviye onerildi.",
    ]
    # Stopwords are dropped; the surviving keyword leads the refined list.
    assert payload["refined_keywords"][0] == "yorulma"
    assert "rapor" not in payload["refined_keywords"]


# --- build_pdf_bytes ---------------------------------------------------------


def test_pdf_rendering_produces_a_real_pdf(writer, seed_corpus) -> None:
    payload = writer.build_draft(title="Yorulma Olcumleri", report_type="Dayanim", mode="keyword")

    pdf_bytes = writer.build_pdf_bytes(payload)

    assert pdf_bytes.startswith(b"%PDF-")
    assert pdf_bytes.rstrip().endswith(b"%%EOF")
    assert len(pdf_bytes) > 1000


def test_pdf_rendering_works_for_a_quick_draft_with_no_sources(writer) -> None:
    payload = writer.build_draft(title="Bos Taslak", report_type="Genel", detail_level="quick")

    assert writer.build_pdf_bytes(payload).startswith(b"%PDF-")


# --- pure helpers ------------------------------------------------------------


def test_guess_report_no_falls_back_to_taslak() -> None:
    assert ReportWriterService._guess_report_no("2025-BIG-E-DUR-01 Rapor") == "2025-BIG-E-DUR-01"
    assert ReportWriterService._guess_report_no("Basliksiz") == "TASLAK"
    assert ReportWriterService._guess_report_no("") == "TASLAK"


def test_normalize_people_splits_on_commas_semicolons_and_newlines() -> None:
    assert ReportWriterService._normalize_people("Ali Veli; Ayse  Yilmaz\nMehmet") == (
        "Ali Veli\nAyse Yilmaz\nMehmet"
    )
    assert ReportWriterService._normalize_people("") == ""


def test_clean_sentence_capitalises_and_terminates() -> None:
    assert ReportWriterService._clean_sentence("  merhaba dunya ") == "Merhaba dunya."
    assert ReportWriterService._clean_sentence("bitti.") == "Bitti."
    assert ReportWriterService._clean_sentence("   ") == ""


def test_clean_notes_dedupes_and_caps_at_eight(writer) -> None:
    notes = writer._clean_notes("a; b\nc; a; " + "; ".join(str(index) for index in range(20)))

    assert notes[:4] == ["A.", "B.", "C.", "0."]
    assert len(notes) == 8


def test_clean_notes_is_empty_for_blank_input(writer) -> None:
    assert writer._clean_notes("   ") == []


def test_refine_keywords_drops_stopwords_and_short_tokens() -> None:
    refined = ReportWriterService._refine_keywords("ve rapor yorulma", "Sasi Dayanim", "", [])

    assert refined == ["yorulma", "Sasi", "Dayanim"]


def test_build_retrieval_query_caps_keywords_and_notes() -> None:
    query = ReportWriterService._build_retrieval_query(
        "T", "O", [f"k{index}" for index in range(8)], ["n1", "n2", "n3", "n4"]
    )

    assert query == "T O k0 k1 k2 k3 k4 k5 n1 n2 n3"


def test_normalize_document_ids_distinguishes_none_from_empty() -> None:
    assert ReportWriterService._normalize_document_ids(None) is None
    assert ReportWriterService._normalize_document_ids([]) == []
    assert ReportWriterService._normalize_document_ids([1, 1, "2", 0, None]) == [1, 2]
    assert ReportWriterService._normalize_document_ids(list(range(1, 30))) == list(range(1, 11))


def test_vehicle_names_outside_the_allowed_terms_are_masked() -> None:
    masked = ReportWriterService._mask_unallowed_vehicle_names("BIG-E ve Goupil araclari", "big-e testi")

    assert masked == "BIG-E ve referans arac araclari"


def test_prompt_leakage_lines_are_stripped_from_a_generated_body() -> None:
    body = "1. GIRIS\nmarkdown kullanma\nnormal satir"

    assert ReportWriterService._remove_prompt_leakage(body) == "1. GIRIS\nnormal satir"


def test_sanitizer_rejects_a_generation_that_is_too_short_to_be_a_draft() -> None:
    assert ReportWriterService._sanitize_llm_draft("```\n1. GIRIS\nkisa\n```", "KAPAK", "") == ""


def test_sanitizer_strips_markdown_and_re_attaches_the_cover() -> None:
    generated = "## 1. GIRIS\n" + "x" * 200

    sanitized = ReportWriterService._sanitize_llm_draft(generated, "KAPAK", "")

    assert sanitized.startswith("KAPAK\n\n1. GIRIS")
    assert "#" not in sanitized


def test_llm_section_headings_are_forced_back_onto_the_template() -> None:
    body = "1. Bambaska bir baslik\n2. Baska bir sey"

    normalized = ReportWriterService._normalize_llm_section_headings(body)

    assert normalized == "1. GIRIS\n2. TEST VE DEGERLENDIRME YONTEMI"
