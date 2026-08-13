from pathlib import Path
import re

from app.api_models import HealthResponse
from app.branding import get_app_brand, normalize_app_variant
from app.ui.variant_styles import RAPORHUB_CSS, get_variant_css


def test_existing_raporhub_brand_is_unchanged() -> None:
    brand = get_app_brand("raporhub")
    main_html = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(encoding="utf-8")

    assert brand.display_name == "RaporHub"
    assert brand.default_data_dir == "data_raporhub"
    assert brand.default_cookie_name == "raporhub_session"
    assert get_variant_css("raporhub") == RAPORHUB_CSS
    assert 'data-module-filter="catalog" data-nav-label="Katalog"' in main_html
    assert 'data-module-filter="graph" data-nav-label="Kategoriler"' in main_html
    assert 'data-module-filter="writing" data-nav-label="Yazim"' in main_html
    assert "Rapor havuzunu yonet, katalogla eslestir" in main_html
    assert "__WORKSPACE_INTRO__" in main_html


def test_repocto_is_an_independent_supported_variant() -> None:
    brand = get_app_brand("repocto")

    assert normalize_app_variant(" RepOcto ") == "repocto"
    assert brand.display_name == "RepOcto"
    assert brand.data_dir_env == "RAPORHUB_DATA_DIR"
    assert brand.default_data_dir == "data_raporhub"
    assert brand.default_cookie_name == "repocto_session"

    health = HealthResponse(
        status="ok",
        version="test",
        application=brand.display_name,
        variant="repocto",
    )
    assert health.variant == "repocto"


def test_repocto_has_separate_landing_and_application_styles() -> None:
    ui_dir = Path(__file__).resolve().parents[1] / "app" / "ui"
    landing = ui_dir / "repocto_landing" / "index.html"
    landing_html = landing.read_text(encoding="utf-8")
    repocto_css = get_variant_css("repocto")

    assert landing.exists()
    assert '<base href="/repocto-landing/">' in landing_html
    assert 'href="/app"' in landing_html
    assert 'id="yetenekler"' in landing_html
    assert 'href="/#yetenekler"' in landing_html
    assert landing_html.count('<button class="skill-node') == 8
    assert "RaporHub" not in landing_html
    assert "Dokümanları bulur, karşılaştırır" in landing_html
    assert "Çoklu doküman karşılaştırma" in landing_html
    assert "Mühendislik dokümanlarının tamamı" in landing_html
    assert "Raporları bulur, karşılaştırır" not in landing_html
    assert 'id="iletisim"' in landing_html
    assert 'href="#iletisim"' in landing_html
    assert "https://anadoluisuzu.com.tr/iletisim/iletisim-formu" in landing_html
    main_html = (ui_dir.parent / "main.py").read_text(encoding="utf-8")
    assert 'data-module-filter="catalog"' in main_html
    assert 'data-module-filter="catalog" data-nav-label="Katalog" data-nav-short="KT" title="Katalog" data-repocto-hide' in main_html
    assert 'data-repocto-label="Kütüphane"' in main_html
    assert 'data-repocto-label="Raporlama"' in main_html
    assert 'id="libraryPathInput"' in main_html
    assert 'id="libraryTree"' in main_html
    assert 'data-app-variant="repocto"' in repocto_css
    assert "/repocto-landing/assets/repocto-wordmark.png" in repocto_css
    assert get_variant_css("big_agent") == ""


def test_repocto_v2_is_separate_and_has_the_reviewed_scroll_flow() -> None:
    ui_dir = Path(__file__).resolve().parents[1] / "app" / "ui"
    v1_html = (ui_dir / "repocto_landing" / "index.html").read_text(encoding="utf-8")
    v2_dir = ui_dir / "repocto_landing" / "v2"
    v2_html = (v2_dir / "index.html").read_text(encoding="utf-8")
    v2_css = (v2_dir / "repocto-v2.css").read_text(encoding="utf-8")
    v2_js = (v2_dir / "repocto-v2.js").read_text(encoding="utf-8")
    main_html = (ui_dir.parent / "main.py").read_text(encoding="utf-8")

    assert 'data-landing-version="2"' in v2_html
    assert 'data-landing-version="2"' not in v1_html
    assert (v2_dir / "repocto-v2.css").exists()
    assert (v2_dir / "repocto-v2.js").exists()
    assert '@app.get("/repocto-v2"' in main_html
    assert 'APP_VARIANT != "repocto"' in main_html

    flow_ids = ["ana-anlatim", "uzantilar", "yetenekler", "detaylar", "dokumanlar", "son"]
    positions = [v2_html.index(f'id="{section_id}"') for section_id in flow_ids]
    assert positions == sorted(positions)

    assert "Mercan Lab" not in v2_html
    assert "Yerel mühendislik zekâsı" not in v2_html
    assert "Mühendislik Bilgisi" not in v2_html
    assert "TEKNİK RAPOR" not in v2_html
    assert "DOKÜMAN NO." in v2_html
    assert 'href="#"' not in v2_html
    hero_video_tag = re.search(r'<video class="hero-video"[^>]*>', v2_html)
    assert hero_video_tag is not None
    assert "autoplay" not in hero_video_tag.group(0)
    assert "if (reducedMotion)" in v2_js
    assert 'video.removeAttribute("autoplay")' in v2_js
    assert ".octopus-layout { grid-template-columns: 1fr; }" in v2_css
    assert "repocto-octopus-friendly-v2.png" in v2_html
    assert 'class="octopus-stage octopus-stage-secondary octopus-stage-static"' in v2_html

    arm_targets = re.findall(r'href="#(detay-[^"]+)" data-arm-link="([^"]+)"', v2_html)
    assert len(arm_targets) == 16
    assert len(set(arm_targets)) == 8
    assert {key for _, key in arm_targets} == {
        "search", "qa", "citation", "summary", "compare", "category", "memory", "writing"
    }
    for target, _ in set(arm_targets):
        assert f'id="{target}"' in v2_html
