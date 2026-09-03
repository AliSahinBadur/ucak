from pathlib import Path
import re
from types import SimpleNamespace

from fastapi.testclient import TestClient
from fastapi import HTTPException
import pytest

from app.config import APP_VARIANT
from app.main import app
import app.main as main_module


ROOT = Path(__file__).resolve().parents[1]
V2_DIR = ROOT / "app" / "ui" / "smartcae_v2"


def test_smartcae_v2_is_separate_from_the_legacy_workspace() -> None:
    main_source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    v2_html = (V2_DIR / "index.html").read_text(encoding="utf-8")

    assert '@app.get("/smartcae-v2"' in main_source
    assert 'APP_VARIANT != "big_agent"' in main_source
    assert '"/smartcae-v2/assets"' in main_source
    assert '@app.get("/app"' in main_source
    assert 'data-module-filter="upload"' in main_source
    assert 'data-smartcae-version="2"' in v2_html
    assert 'href="/legacy"' in v2_html
    assert "/smartcae-v2/assets/smartcae-v2.css?v=__APP_VERSION__" in v2_html
    assert "/smartcae-v2/assets/smartcae-v2.js?v=__APP_VERSION__" in v2_html
    assert '"__SMARTCAE_V2_LINK__"' in main_source
    assert 'class="smartcae-v2-link"' in main_source


def test_chat_progress_distinguishes_model_direct_and_failed_thinking() -> None:
    script = (V2_DIR / "assets" / "smartcae-v2.js").read_text(encoding="utf-8")
    assert 'providerName: data.embedding_provider' in script
    assert 'thinkingAttempted: Boolean(data.thinking_attempted)' in script
    assert 'if (data.thinking_attempted && !data.thinking_used)' in script
    assert 'if (state.thinkingMode && !data.thinking_used)' not in script
    assert 'const directAnswer = providerName === "chat-direct";' in script
    assert 'const confidenceLabel = retrievalUsed && sourceCount > 0' in script
    assert 'Thinking gerekli değildi' in script


def test_smartcae_v2_system_status_shows_configured_llm_model() -> None:
    html = (V2_DIR / "index.html").read_text(encoding="utf-8")
    script = (V2_DIR / "assets" / "smartcae-v2.js").read_text(encoding="utf-8")

    assert '<span>Embedding modeli</span><strong id="embeddingModel">' in html
    assert '<span>LLM modeli</span><strong id="llmModel">' in html
    assert 'const llmModel = document.getElementById("llmModel");' in script
    assert 'llmModel.textContent = ollama.configured_model || "—";' in script


@pytest.mark.skipif(APP_VARIANT != "big_agent", reason="SmartCAE V2 is served only by the big_agent variant")
def test_smartcae_v2_route_and_assets_are_served_for_big_agent() -> None:
    with TestClient(app) as client:
        root_page = client.get("/")
        page = client.get("/smartcae-v2")
        legacy_page = client.get("/legacy")
        stylesheet = client.get("/smartcae-v2/assets/smartcae-v2.css")
        script = client.get("/smartcae-v2/assets/smartcae-v2.js")
        documents = client.get("/documents/list?limit=1")

    assert root_page.status_code == 200
    assert 'data-smartcae-version="2"' in root_page.text
    assert page.status_code == 200
    assert 'data-smartcae-version="2"' in page.text
    assert legacy_page.status_code == 200
    assert 'data-smartcae-version="2"' not in legacy_page.text
    assert 'class="smartcae-v2-link"' in legacy_page.text
    assert f"smartcae-v2.css?v={main_module.APP_VERSION}" in page.text
    assert f"smartcae-v2.js?v={main_module.APP_VERSION}" in page.text
    assert f'id="systemVersionLabel">v{main_module.APP_VERSION}</small>' in page.text
    assert "__APP_VERSION__" not in page.text
    assert stylesheet.status_code == 200
    assert "--red: #c12a42" in stylesheet.text
    assert "background: #fdecef" in stylesheet.text
    assert script.status_code == 200
    assert 'fetch("/chat"' in script.text
    assert 'fetch("/documents/list?limit=300"' in script.text
    assert documents.status_code == 200
    document_items = documents.json().get("items", [])
    if document_items:
        assert {
            "file_type",
            "page_count",
            "report_code",
            "vehicle_name",
            "report_title",
            "discipline",
            "report_date",
            "authors",
            "source_path",
        }.issubset(document_items[0])

    legacy_link = main_module._apply_brand_tokens("__SMARTCAE_V2_LINK__")
    assert '<a class="smartcae-v2-link" href="/smartcae-v2">' in legacy_link
    assert "Yeni arayüz" in legacy_link


@pytest.mark.parametrize("variant", ["raporhub", "repocto"])
def test_smartcae_v2_page_is_not_available_to_other_variants(
    monkeypatch: pytest.MonkeyPatch,
    variant: str,
) -> None:
    monkeypatch.setattr(main_module, "APP_VARIANT", variant)
    with pytest.raises(HTTPException) as error:
        main_module.smartcae_v2_page()
    assert error.value.status_code == 404

    assert main_module._apply_brand_tokens("__SMARTCAE_V2_LINK__") == ""


def test_smartcae_v2_has_functional_workspace_targets_and_no_placeholder_links() -> None:
    html = (V2_DIR / "index.html").read_text(encoding="utf-8")
    script = (V2_DIR / "assets" / "smartcae-v2.js").read_text(encoding="utf-8")
    css = (V2_DIR / "assets" / "smartcae-v2.css").read_text(encoding="utf-8")

    view_targets = set(re.findall(r'data-view-target="([^"]+)"', html))
    views = set(re.findall(r'data-view="([^"]+)"', html))
    element_ids = re.findall(r'\sid="([^"]+)"', html)
    assert view_targets == {"home", "chat", "skills", "documents", "search", "compare", "writing", "catia"}
    assert view_targets == views
    assert len(element_ids) == len(set(element_ids))
    assert '<span class="brand-robot" aria-hidden="true">🤖</span>' in html
    for target, icon in {
        "home": "🏠",
        "chat": "💬",
        "skills": "🧰",
        "documents": "📚",
        "search": "🔎",
        "compare": "⚖️",
        "writing": "📝",
        "catia": "⚙️",
    }.items():
        assert f'data-view-target="{target}"' in html
        assert f'<span class="rail-emoji" aria-hidden="true">{icon}</span>' in html
    assert 'class="rail-icon"' not in html
    assert 'href="#"' not in html
    assert "onclick=" not in html
    assert "http://" not in html
    assert "https://" not in html

    for endpoint in (
        'fetch("/chat"',
        'fetch("/documents/list?limit=300"',
        'fetch("/ingest/batch"',
        "fetch(`/search?${params}`",
        'fetch("/report-comparison/multi"',
        'fetch("/draft-report"',
        'fetch("/draft-report/pdf"',
        'fetch("/skills/catia-mass-cg/status"',
        'fetch("/skills/catia-mass-cg/chat"',
        'fetch("/skills/catia-mass-cg/approve"',
    ):
        assert endpoint in script

    assert "@media (max-width: 860px)" in css
    assert "@media (max-width: 640px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ":focus-visible" in css
    assert 'minlength="2" maxlength="1000"' in html
    assert 'aria-hidden="true" inert' in html
    assert 'id="chatThinkingToggle"' in html
    assert 'role="switch" aria-checked="false"' in html
    assert "evidencePanel.inert = !evidenceOpen" in script
    assert "chatContextDocumentIds: []" in script
    assert ": state.chatContextDocumentIds.slice(0, 8)" in script
    assert "state.chatContextDocumentIds = sourceDocumentIds" in script
    assert "thinking_mode: state.thinkingMode" in script
    assert 'state.thinkingMode ? "LLM bağlam çözümü"' in script
    assert '.thinking-mode-toggle[aria-checked="true"]' in css


def test_smartcae_v2_has_a_dedicated_engineering_skill_center() -> None:
    html = (V2_DIR / "index.html").read_text(encoding="utf-8")
    script = (V2_DIR / "assets" / "smartcae-v2.js").read_text(encoding="utf-8")
    css = (V2_DIR / "assets" / "smartcae-v2.css").read_text(encoding="utf-8")

    assert 'data-view="skills"' in html
    assert 'aria-label="Mühendislik skill merkezi"' in html
    assert 'id="skillsTitle"' in html
    assert 'id="skillContextHint"' in html
    assert 'aria-label="Kullanılabilir mühendislik skill\'leri"' in html
    assert html.count('data-skill-launch=') == 3
    assert html.count('class="skill-howto"') == 4
    assert html.count("Nasıl kullanılır?") == 4
    assert 'data-skill-launch="report-review"' in html
    assert 'data-skill-launch="revision-review"' in html
    assert 'data-skill-launch="numbering-review"' in html
    assert "Rapor kontrolü" in html
    assert "Revizyon kontrolü" in html
    assert "Tablo / şekil kontrolü" in html
    assert '<strong id="skillsActiveCount">3</strong> aktif skill' in html
    assert 'skills: { overline: "UZMAN İŞ AKIŞLARI", title: "Skill Merkezi" }' in script
    assert 'const skillContextHint = document.getElementById("skillContextHint")' in script
    assert 'document.querySelectorAll("[data-prompt]")' in script
    assert 'if (skillLaunch) setView("chat", { focus: false })' in script
    assert '"Skill komutu hazır. Metni kontrol edip gönderebilirsin."' in script
    assert ".skill-grid" in css
    assert ".skill-card-review" in css
    assert ".skill-card-revision" in css
    assert ".skill-card-numbering" in css
    assert ".skill-workflow" in css


def test_catia_skill_is_feature_flagged_and_connected_to_smartcae_v2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = (V2_DIR / "index.html").read_text(encoding="utf-8")
    script = (V2_DIR / "assets" / "smartcae-v2.js").read_text(encoding="utf-8")
    css = (V2_DIR / "assets" / "smartcae-v2.css").read_text(encoding="utf-8")

    assert 'id="catiaSkillCard" hidden' in html
    assert 'id="chatCatiaSkill"' in html
    assert 'class="skill-example catia-skill-link"' in html
    assert 'data-chat-skill="catia"' in html
    assert 'data-view="catia"' not in html
    assert 'data-view-target="catia"' not in html
    assert 'id="catiaComposer"' not in html
    assert 'id="chatSkillModeBar"' in html
    assert 'id="chatCatiaSuggestions"' in html
    assert 'id="chatCatiaApproval"' in html
    assert 'data-catia-prompt=' in html
    assert 'data-catia-shortcut="doctor"' in html
    assert 'activeChatSkill: null' in script
    assert 'function activateCatiaChat(trigger)' in script
    assert 'if (state.activeChatSkill === "catia")' in script
    assert 'await sendCatiaMessage(message)' in script
    assert 'session_id: state.catiaSessionId, shortcut' in script
    assert 'skillsActiveCount.textContent = usable ? "4" : "3"' in script
    assert 'chatCatiaSkill.hidden = !usable' in script
    assert 'chatCatiaSuggestions.querySelectorAll("[data-catia-prompt]")' in script
    assert 'fetch("/skills/catia-mass-cg/status"' in script
    assert 'fetch("/skills/catia-mass-cg/chat"' in script
    assert 'fetch("/skills/catia-mass-cg/approve"' in script
    assert ".chat-skill-mode-bar" in css
    assert ".catia-chat-active" in css
    assert ".catia-approval" in css
    assert ".chat-suggestions .catia-skill-link" in css

    request = SimpleNamespace(client=SimpleNamespace(host="testclient"))
    monkeypatch.setattr(main_module, "CATIA_SKILL_ENABLED", False)
    assert main_module.catia_skill_status(request) == {"enabled": False}

    service = SimpleNamespace(
        status=lambda: {
            "source": "fake",
            "model": "test-model",
            "workspace_root": "test-workspace",
        }
    )
    monkeypatch.setattr(main_module, "CATIA_SKILL_ENABLED", True)
    monkeypatch.setattr(main_module, "get_catia_skill_service", lambda: service)
    status = main_module.catia_skill_status(request)
    assert status["enabled"] is True
    assert status["available"] is True
    assert status["local_client"] is True
    assert status["source"] == "fake"


def test_smartcae_v2_comparison_supports_an_unbounded_dynamic_source_list() -> None:
    html = (V2_DIR / "index.html").read_text(encoding="utf-8")
    script = (V2_DIR / "assets" / "smartcae-v2.js").read_text(encoding="utf-8")
    css = (V2_DIR / "assets" / "smartcae-v2.css").read_text(encoding="utf-8")

    assert 'id="compareDocumentFilter"' in html
    assert 'id="compareDocumentPicker"' in html
    assert 'id="compareSelection"' in html
    assert 'id="compareMode"' in html
    assert '<option value="reference">Referansa göre</option>' in html
    assert '<option value="all_pairs">Tüm doküman çiftleri</option>' in html
    assert 'id="comparePairEstimate"' in html
    assert 'id="compareRunButton"' in html
    assert 'id="compareLeft"' not in html
    assert 'id="compareRight"' not in html

    assert "comparisonDocumentIds: []" in script
    assert "comparisonReferenceId: null" in script
    assert 'fetch("/report-comparison/multi"' in script
    assert "sources: sourceIds.map(documentId => ({ document_id: documentId }))" in script
    assert 'compareMode.value === "all_pairs" ? (count * (count - 1)) / 2 : count - 1' in script
    assert ".slice(0," not in script[script.index("async function runComparison"):script.index("function buildDraftPayload")]
    assert ".compare-source-card" in css
    assert ".comparison-pair" in css
    assert ".comparison-insight-list" in css


def test_smartcae_v2_search_heading_moves_to_the_dynamic_topbar() -> None:
    html = (V2_DIR / "index.html").read_text(encoding="utf-8")
    script = (V2_DIR / "assets" / "smartcae-v2.js").read_text(encoding="utf-8")

    assert 'id="activeViewOverline"' in html
    assert '<h1 id="searchTitle" class="visually-hidden">Bilgiyi geçtiği yerde bul</h1>' in html
    assert html.index('class="legacy-link"') < html.index('class="system-chip"')
    assert html.index('class="system-chip"') < html.index('id="evidenceToggle"')
    assert html.index('id="evidenceToggle"') < html.index('class="system-popover"')
    assert 'search: { overline: "ANLAMSAL ARAMA", title: "Bilgiyi geçtiği yerde bul" }' in script
    assert "activeViewOverline.textContent = viewMeta[view].overline" in script
    assert "activeViewTitle.textContent = viewMeta[view].title" in script


def test_smartcae_v2_chat_workspace_and_light_emoji_rail_contract() -> None:
    html = (V2_DIR / "index.html").read_text(encoding="utf-8")
    script = (V2_DIR / "assets" / "smartcae-v2.js").read_text(encoding="utf-8")
    css = (V2_DIR / "assets" / "smartcae-v2.css").read_text(encoding="utf-8")

    assert '<h1 id="chatTitle" class="visually-hidden">Kaynaklı mühendislik asistanı</h1>' in html
    assert 'class="chat-workspace-bar"' in html
    assert 'id="chatEvidenceButton"' in html
    assert 'id="chatEvidenceCount">0 kaynak</span>' in html
    assert 'id="chatProcess" data-state="idle"' in html
    assert 'id="chatProcessElapsed"' in html
    assert 'role="progressbar" aria-label="Yanıt hazırlama ilerlemesi"' in html
    assert 'id="chatProcessRequestStep"' in html
    assert 'id="chatProcessRetrievalStep"' in html
    assert 'id="chatProcessEvidenceStep"' in html
    assert 'id="chatProcessGenerationStep"' in html
    assert 'id="chatProcessResponseStep"' in html
    assert 'id="chatStatus" role="status" hidden' in html
    assert 'id="chatRetrievalVersion"' in html
    assert '<option value="v2">v2 · Beta</option>' in html
    assert '<option value="v3">v3 · Haystack</option>' in html
    assert '<option value="v1">v1 · Klasik</option>' in html
    assert "Seçili dokümanlarla kaynaklı yanıt üretir" in html
    assert "chatEvidenceButton.setAttribute(\"aria-expanded\", String(open))" in script
    assert "chatEvidenceCount.textContent" in script
    assert "let evidenceReturnFocus = evidenceToggle" in script
    assert "returnFocus: chatEvidenceButton" in script
    assert "setEvidenceOpen(false, { restoreFocus: true })" in script
    assert "evidenceToggle.focus()" not in script
    assert 'const chatRetrievalVersion = document.getElementById("chatRetrievalVersion")' in script
    assert "retrieval_version: chatRetrievalVersion.value" in script
    assert 'retrieval_version: "v2"' not in script
    assert 'chatRetrievalVersion.addEventListener("change"' in script
    assert 'return "RAG v3 · Haystack"' in script
    assert "function startChatProcess()" in script
    assert "function finishChatProcess(" in script
    assert "function updateChatProcessStage(milliseconds)" in script
    assert "function setChatProcessProgress(value, label)" in script
    assert "window.setInterval(updateChatProcessElapsed, 100)" in script
    assert "startChatProcess();" in script
    assert "const elapsedText = finishChatProcess({" in script
    assert 'chatProcess.dataset.state = "complete"' in script
    assert 'chatProcess.dataset.state = "error"' in script
    assert 'id="chatProcessToggle"' in html
    assert "function scheduleChatProcessCompact()" in script
    assert 'chatProcess.classList.toggle("compact", compact)' in script
    assert ".chat-process.compact .chat-process-track" in css
    assert ".chat-process-track" in css
    assert "width: var(--process-progress, 20%)" in css
    assert ".chat-process-step.active" in css
    assert ".chat-process-step.skipped" in css
    assert ".rag-version-control select" in css
    assert "flex-direction: column; flex-wrap: nowrap" in css
    assert ".chat-controls::-webkit-scrollbar" in css
    assert 'aria-label="Skill\'ler ve örnek sorular"' in html
    assert 'data-suggestion-section="skills"' in html
    assert 'data-suggestion-section="examples"' in html
    assert "Skill'ler" in html
    assert 'data-prompt="RAPOR-KODU raporu kontrol et; hata, eksik ve tutarsızlıkları sayfa kanıtlarıyla göster."' in html
    assert 'data-context-prompt="Bu raporu kontrol et; hata, eksik ve tutarsızlıkları sayfa kanıtlarıyla göster."' in html
    assert 'data-context-multi-prompt="Bu raporları kontrol et; hata, eksik ve tutarsızlıkları ayrı ayrı sayfa kanıtlarıyla göster."' in html
    assert "Rapor kontrolü" in html
    assert 'id="chatInput" rows="1"' in html
    assert 'data-select-token="RAPOR-KODU"' in html
    assert 'data-prompt="SmartCAE AI ne yapar?" data-assistant-mode="auto"' in html
    assert "Uygulama nedir?" in html
    assert "Kendinden bahset" in html
    assert "BIG-E konfor parkurları" in html
    assert "Alternatör braket" in html
    assert "TASE sensör" in html
    assert 'chatInput.setSelectionRange(tokenStart, tokenStart + selectToken.length)' in script
    assert "const selectedCount = state.selectedDocumentIds.size" in script
    assert "button.dataset.contextMultiPrompt" in script
    assert "selectedCount > 0 && contextPrompt" in script
    assert '"Örnek soru hazır. Metni düzenleyip gönderebilirsin."' in script
    assert "kaynakla yanıtlandı" not in script
    assert 'button.addEventListener("click", () => sendChatMessage(button.dataset.prompt))' not in script
    assert "👤" not in script
    assert ".user-message .message-avatar" not in css
    assert ".user-message p { margin-top: 0; }" in css
    assert "padding: 9px 12px" in css
    assert "line-height: 1.5" in css
    assert 'body.dataset.activeView = view' in script
    assert 'if (view === "chat")' in script
    assert 'body[data-active-view="chat"] .topbar' in css
    assert 'body[data-active-view="chat"] .workspace-main {' in css
    assert 'position: absolute;\n  inset: 0;' in css
    assert 'body[data-active-view="chat"] .chat-stage' in css
    assert 'height: calc(100dvh - 12px)' in css
    assert ".chat-suggestions-label" in css
    assert "grid-template-columns: minmax(300px, 0.9fr) minmax(0, 1.1fr)" in css
    assert ".chat-suggestion-track::-webkit-scrollbar" in css
    assert ".chat-suggestion-section + .chat-suggestion-section" in css
    assert ".chat-suggestion-track::-webkit-scrollbar-thumb" in css
    assert "scrollbar-width: thin" in css
    assert "scrollbar-gutter: stable" in css
    assert ".chat-view {\n  padding: 6px 0;" in css
    assert "height: calc(100dvh - var(--topbar-height) - 12px)" in css
    assert "min-height: 58px" in css
    assert ".chat-composer textarea { min-height: 26px; max-height: 120px" in css
    assert "function resizeChatInput()" in script
    assert 'chatInput.addEventListener("input", resizeChatInput)' in script
    assert "Math.min(chatInput.scrollHeight, 120)" in script
    assert 'function cleanEvidenceExcerpt(value, documentTitle = "")' in script
    assert "function parseFlowRateTable(value)" in script
    assert 'evidenceFactHtml("Hazırlayan", authors)' in script
    assert 'evidenceFactHtml("Rapor tarihi", reportDate)' in script
    assert 'evidenceFactHtml("Rapor konusu", reportTopic)' in script
    assert 'evidenceFactHtml("Rapor konusu", reportTopic, true)' not in script
    assert '`${relevance.toFixed(2)} puan`' in script
    assert "function evidenceDetailHtml" not in script
    assert "Belge detayları ve tam pasaj" not in script
    assert 'event.target.closest("button, a")' in script
    assert ".evidence-facts" in css
    assert "grid-template-columns: repeat(3, minmax(0, 1fr))" in css
    assert ".evidence-fact-wide" not in css
    assert ".evidence-table-wrap" in css
    assert ".evidence-details" not in css

    rail_hover = re.search(r"\.rail-button:hover\s*\{([^}]*)\}", css, re.DOTALL)
    rail_active = re.search(r"\.rail-button\.active\s*\{([^}]*)\}", css, re.DOTALL)
    rail_emoji = re.search(r"\.rail-emoji\s*\{([^}]*)\}", css, re.DOTALL)
    tool_rail = re.search(r"\.tool-rail\s*\{([^}]*)\}", css, re.DOTALL)
    assert rail_hover and "background: #fff" in rail_hover.group(1)
    assert rail_active and "background: #c62839" in rail_active.group(1)
    assert rail_active and "box-shadow:" in rail_active.group(1)
    assert rail_emoji and "font-size: 20px" in rail_emoji.group(1)
    assert tool_rail and "background: #fdecef" in tool_rail.group(1)
    assert ".rail-nav .rail-button + .rail-button::after" in css
    assert "background: rgba(143, 20, 33, 0.14)" in css


def test_smartcae_v2_search_cards_open_files_and_offer_folder_and_inline_preview() -> None:
    html = (V2_DIR / "index.html").read_text(encoding="utf-8")
    script = (V2_DIR / "assets" / "smartcae-v2.js").read_text(encoding="utf-8")
    css = (V2_DIR / "assets" / "smartcae-v2.css").read_text(encoding="utf-8")
    main_source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")

    assert 'id="sourcePreviewPane"' in html
    assert 'id="sourcePreviewFrame"' in html
    assert 'id="icon-folder-open"' in html
    assert 'id="icon-eye"' in html
    assert 'id="exportReviewButton"' in html
    assert "Revizyon kontrolü" in html
    assert 'href="#icon-folder-open"' in script
    assert 'href="#icon-eye"' in script
    assert 'class="result-action-button folder-action"' in script
    assert 'class="result-action-button preview-action"' in script
    assert 'data-result-card-document="${documentId}"' in script
    assert 'data-result-folder="${documentId}"' in script
    assert 'data-result-preview="${documentId}"' in script
    assert 'data-evidence-folder="${documentId}"' in script
    assert 'data-evidence-preview="${documentId}"' in script
    assert 'data-evidence-preview-url="${escapeHtml(reviewPreviewUrl)}"' in script
    assert 'class="review-preview-cta"' in script
    assert 'data-review-decision="confirmed"' in script
    assert 'data-review-decision="dismissed"' in script
    assert 'fetch("/report-review/decisions"' in script
    assert 'window.location.assign(`/report-review/export?' in script
    assert 'review_revision_change' in script
    assert "İşaretli PDF kanıtını aç" in script
    assert ".review-preview-cta" in css
    assert ".review-decision-row" in css
    assert ".evidence-tag.revision-change.new" in css
    assert "openDocumentFolder(Number(button.dataset.evidenceFolder), button)" in script
    assert "Number(button.dataset.evidencePreview)" in script
    assert 'source_kind === "report_review"' in script
    assert 'reviewEngine.startsWith("llm:")' in script
    assert 'LLM destekli' in script
    assert 'Kontrol kanıtı işaretli' in script
    assert "data-result-document" not in script
    assert 'event.target.closest("button, a")' in script
    assert 'class="evidence-facts result-evidence-facts"' in script
    assert 'class="evidence-tags result-tags"' in script
    assert 'class="evidence-details result-details"' not in script
    assert 'cleanEvidenceExcerpt(item.chunk_text, title)' in script
    assert 'evidenceTableHtml(excerpt)' in script
    assert 'fetch(`/documents/${Number(documentId)}/open-folder`' in script
    assert 'const previewBase = String(previewUrl || "").trim() || `/documents/${id}/preview?page=${page}`' in script
    assert 'sourcePreviewFrame.src = `${previewBase}#page=${page}&view=FitH&toolbar=0&navpanes=0`' in script
    assert 'evidencePanel.classList.add("preview-active")' in script
    assert 'evidencePanel.classList.remove("preview-active")' in script
    assert ".result-action-button" in css
    assert ".result-action-button.folder-action" in css
    assert "background: #fff5d9" in css
    assert ".result-action-button.preview-action" in css
    assert "background: #eaf4ff" in css
    assert ".evidence-card-tools" in css
    assert ".evidence-action-button" in css
    assert ".evidence-card.is-review-evidence" in css
    assert ".review-evidence-callout" in css
    assert "Sayfa kanıtı" not in script
    assert ".review-evidence-proof" not in css
    assert ".evidence-tag.semantic-engine" in css
    assert ".result-evidence-facts" in css
    assert ".result-card .evidence-table" in css
    assert ".result-details" not in css
    assert ".source-preview-pane" in css
    assert ".evidence-panel.preview-active .source-preview-canvas" in css
    assert '@app.post("/documents/{document_id}/open-folder")' in main_source
    assert '@app.get("/documents/{document_id}/preview")' in main_source
    assert '@app.get("/documents/{document_id}/review-preview")' in main_source
    assert '"/report-review/decisions"' in main_source
    assert '@app.get("/report-review/export")' in main_source


def test_smartcae_v2_evidence_panel_is_resizable_on_desktop() -> None:
    html = (V2_DIR / "index.html").read_text(encoding="utf-8")
    script = (V2_DIR / "assets" / "smartcae-v2.js").read_text(encoding="utf-8")
    css = (V2_DIR / "assets" / "smartcae-v2.css").read_text(encoding="utf-8")

    assert 'id="evidenceResizer" role="separator"' in html
    assert 'aria-valuemin="280" aria-valuemax="720" aria-valuenow="340"' in html
    assert 'evidenceResizer.addEventListener("pointerdown"' in script
    assert 'window.addEventListener("pointermove"' in script
    assert 'evidenceResizer.addEventListener("keydown"' in script
    assert 'document.documentElement.style.setProperty("--evidence-width"' in script
    assert ".evidence-resizer" in css
    assert "body.evidence-resizing iframe" in css
    assert '@media (max-width: 1120px)' in css


def test_smartcae_v2_source_sidebar_is_compact_filterable_and_resizable() -> None:
    html = (V2_DIR / "index.html").read_text(encoding="utf-8")
    script = (V2_DIR / "assets" / "smartcae-v2.js").read_text(encoding="utf-8")
    css = (V2_DIR / "assets" / "smartcae-v2.css").read_text(encoding="utf-8")

    assert 'id="newChatButton"' in html
    assert 'class="new-work-button"' not in html
    assert 'class="source-upload-button"' in html
    assert 'data-source-filter="all"' in html
    assert 'data-source-filter="selected"' in html
    assert 'id="sourceSelectionBar"' in html
    assert 'id="clearContextButton"' in html
    assert 'id="sourceResizer" role="separator"' in html
    assert 'id="toggleSourceSidebar"' in html
    assert "selectedContextList" not in html
    assert "selectedContextList" not in script

    assert 'sourceFilter: "all"' in script
    assert 'state.sourceFilter === "selected"' in script
    assert 'sourceFilterButtons.forEach(button =>' in script
    assert 'sourceResizer.addEventListener("pointerdown"' in script
    assert 'sourceResizer.addEventListener("keydown"' in script
    assert 'document.documentElement.style.setProperty("--source-width"' in script
    assert 'body.classList.toggle("source-collapsed"' in script
    assert 'setSourceWidth(currentSourceWidth());\n    setSourceCollapsed(true);' in script
    assert 'file-badge-${fileClass}' in script

    assert ".source-toolbar" in css
    assert ".source-tabs button.active::after" in css
    assert ".file-badge-pdf" in css
    assert ".file-badge-docx" in css
    assert ".file-badge-pptx" in css
    assert ".source-selection-bar" in css
    assert ".source-resizer" in css
    assert "body.source-collapsed" in css


def test_smartcae_v2_evidence_cards_open_original_files_without_a_button() -> None:
    script = (V2_DIR / "assets" / "smartcae-v2.js").read_text(encoding="utf-8")
    css = (V2_DIR / "assets" / "smartcae-v2.css").read_text(encoding="utf-8")

    assert "Orijinal dosyayı aç" not in script
    assert 'role="link" tabindex="0"' in script
    assert 'card.addEventListener("click"' in script
    assert 'card.addEventListener("keydown"' in script
    assert 'event.key !== "Enter" && event.key !== " "' in script
    assert ".evidence-card.is-openable" in css
    assert ".evidence-card.is-openable:focus-visible" in css


def test_document_folder_endpoint_opens_the_resolved_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_path = tmp_path / "sample.pdf"
    document_path.write_bytes(b"pdf")
    document = SimpleNamespace(id=73, file_path=str(document_path), file_name=document_path.name)

    class StubSession:
        @staticmethod
        def get(model, document_id):
            assert model is main_module.Document
            assert document_id == 73
            return document

    opened_paths: list[str] = []
    monkeypatch.setattr(main_module.os, "startfile", opened_paths.append, raising=False)

    result = main_module.open_document_folder(73, session=StubSession())

    assert result["opened"] is True
    assert result["file_name"] == "sample.pdf"
    assert result["folder_path"] == str(tmp_path)
    assert opened_paths == [str(tmp_path)]
