(() => {
  "use strict";

  const viewMeta = {
    home: { overline: "MÜHENDİSLİK ÇALIŞMA ALANI", title: "Ana alan" },
    chat: { overline: "SMARTCAE COPILOT", title: "Kaynaklı mühendislik asistanı" },
    skills: { overline: "UZMAN İŞ AKIŞLARI", title: "Skill Merkezi" },
    documents: { overline: "MÜHENDİSLİK ÇALIŞMA ALANI", title: "Dokümanlar" },
    search: { overline: "ANLAMSAL ARAMA", title: "Bilgiyi geçtiği yerde bul" },
    compare: { overline: "MÜHENDİSLİK ÇALIŞMA ALANI", title: "Karşılaştırma" },
    writing: { overline: "MÜHENDİSLİK ÇALIŞMA ALANI", title: "Doküman hazırlama" },
  };

  const state = {
    activeView: "home",
    documents: [],
    selectedDocumentIds: new Set(),
    chatContextDocumentIds: [],
    comparisonDocumentIds: [],
    comparisonReferenceId: null,
    sourceFilter: "all",
    chatHistory: [],
    activeChatSkill: null,
    thinkingMode: false,
    evidence: [],
    previewDocumentId: null,
    lastDraftPayload: null,
    systemStatusLoaded: false,
    catiaSessionId: null,
    catiaPendingRunId: null,
    catiaRejectedRunId: null,
    catiaApprovalPending: false,
    catiaShortcut: null,
    catiaBusy: false,
    catiaEnabled: false,
    catiaAvailable: false,
    catiaSource: "fake",
  };

  const body = document.body;
  const workspaceMain = document.getElementById("workspaceMain");
  const activeViewOverline = document.getElementById("activeViewOverline");
  const activeViewTitle = document.getElementById("activeViewTitle");
  const sourceSidebar = document.getElementById("sourceSidebar");
  const toggleSourceSidebar = document.getElementById("toggleSourceSidebar");
  const sourceResizer = document.getElementById("sourceResizer");
  const openSourceSidebar = document.getElementById("openSourceSidebar");
  const closeSourceSidebar = document.getElementById("closeSourceSidebar");
  const mobileScrim = document.getElementById("mobileScrim");
  const evidencePanel = document.getElementById("evidencePanel");
  const evidenceResizer = document.getElementById("evidenceResizer");
  const evidenceToggle = document.getElementById("evidenceToggle");
  const closeEvidencePanel = document.getElementById("closeEvidencePanel");
  const exportReviewButton = document.getElementById("exportReviewButton");
  const evidenceList = document.getElementById("evidenceList");
  const evidenceIntro = document.getElementById("evidenceIntro");
  const sourcePreviewPane = document.getElementById("sourcePreviewPane");
  const sourcePreviewTitle = document.getElementById("sourcePreviewTitle");
  const sourcePreviewMeta = document.getElementById("sourcePreviewMeta");
  const sourcePreviewFrame = document.getElementById("sourcePreviewFrame");
  const sourcePreviewLoading = document.getElementById("sourcePreviewLoading");
  const closeSourcePreviewButton = document.getElementById("closeSourcePreview");
  const toast = document.getElementById("toast");

  const sourceDocumentList = document.getElementById("sourceDocumentList");
  const sidebarDocumentFilter = document.getElementById("sidebarDocumentFilter");
  const selectedContextCount = document.getElementById("selectedContextCount");
  const sourceAllCount = document.getElementById("sourceAllCount");
  const sourceSelectedCount = document.getElementById("sourceSelectedCount");
  const sourceSelectionBar = document.getElementById("sourceSelectionBar");
  const sourceFilterButtons = Array.from(document.querySelectorAll("[data-source-filter]"));
  const clearContextButton = document.getElementById("clearContextButton");
  const globalFilePicker = document.getElementById("globalFilePicker");
  const refreshDocumentsButton = document.getElementById("refreshDocumentsButton");
  const sidebarStatus = document.getElementById("sidebarStatus");
  const recentDocuments = document.getElementById("recentDocuments");
  const documentMetric = document.getElementById("documentMetric");
  const embeddingCoverageBar = document.getElementById("embeddingCoverageBar");
  const embeddingCoverageText = document.getElementById("embeddingCoverageText");
  const documentGrid = document.getElementById("documentGrid");
  const documentListMeta = document.getElementById("documentListMeta");
  const documentPageFilter = document.getElementById("documentPageFilter");
  const homeContextHint = document.getElementById("homeContextHint");
  const chatContextHint = document.getElementById("chatContextHint");
  const skillContextHint = document.getElementById("skillContextHint");

  const heroComposer = document.getElementById("heroComposer");
  const heroPrompt = document.getElementById("heroPrompt");
  const chatComposer = document.getElementById("chatComposer");
  const chatInput = document.getElementById("chatInput");
  const chatMessages = document.getElementById("chatMessages");
  const chatAgentIcon = document.getElementById("chatAgentIcon");
  const chatAgentName = document.getElementById("chatAgentName");
  const chatAgentDescription = document.getElementById("chatAgentDescription");
  const chatControls = document.querySelector(".chat-controls");
  const chatSuggestions = document.getElementById("chatSuggestions");
  const chatSkillModeBar = document.getElementById("chatSkillModeBar");
  const chatSkillExitButton = document.getElementById("chatSkillExitButton");
  const chatCatiaModeDetail = document.getElementById("chatCatiaModeDetail");
  const chatCatiaSuggestions = document.getElementById("chatCatiaSuggestions");
  const chatCatiaApproval = document.getElementById("chatCatiaApproval");
  const chatCatiaApprovalRun = document.getElementById("chatCatiaApprovalRun");
  const chatCatiaApproveButton = document.getElementById("chatCatiaApproveButton");
  const chatCatiaRejectButton = document.getElementById("chatCatiaRejectButton");
  const chatCatiaResetButton = document.getElementById("chatCatiaResetButton");
  const chatStatus = document.getElementById("chatStatus");
  const chatProcess = document.getElementById("chatProcess");
  const chatProcessTitle = document.getElementById("chatProcessTitle");
  const chatProcessElapsed = document.getElementById("chatProcessElapsed");
  const chatProcessToggle = document.getElementById("chatProcessToggle");
  const chatProcessTrack = document.getElementById("chatProcessTrack");
  const chatProcessRequestStep = document.getElementById("chatProcessRequestStep");
  const chatProcessRetrievalStep = document.getElementById("chatProcessRetrievalStep");
  const chatProcessEvidenceStep = document.getElementById("chatProcessEvidenceStep");
  const chatProcessGenerationStep = document.getElementById("chatProcessGenerationStep");
  const chatProcessResponseStep = document.getElementById("chatProcessResponseStep");
  const chatProcessDetail = document.getElementById("chatProcessDetail");
  const chatSendButton = document.getElementById("chatSendButton");
  const chatAssistantMode = document.getElementById("chatAssistantMode");
  const chatRetrievalVersion = document.getElementById("chatRetrievalVersion");
  const chatSearchMode = document.getElementById("chatSearchMode");
  const chatThinkingToggle = document.getElementById("chatThinkingToggle");
  const chatEvidenceButton = document.getElementById("chatEvidenceButton");
  const chatEvidenceCount = document.getElementById("chatEvidenceCount");
  const newChatButton = document.getElementById("newChatButton");

  const searchForm = document.getElementById("searchForm");
  const searchQuery = document.getElementById("searchQuery");
  const searchMode = document.getElementById("searchMode");
  const searchStatus = document.getElementById("searchStatus");
  const searchResults = document.getElementById("searchResults");

  const compareForm = document.getElementById("compareForm");
  const compareDocumentFilter = document.getElementById("compareDocumentFilter");
  const compareDocumentPicker = document.getElementById("compareDocumentPicker");
  const compareAddButton = document.getElementById("compareAddButton");
  const compareAddContextButton = document.getElementById("compareAddContextButton");
  const compareSelection = document.getElementById("compareSelection");
  const compareSelectedCount = document.getElementById("compareSelectedCount");
  const compareMode = document.getElementById("compareMode");
  const compareModeNote = document.getElementById("compareModeNote");
  const comparePairEstimate = document.getElementById("comparePairEstimate");
  const compareRunButton = document.getElementById("compareRunButton");
  const compareStatus = document.getElementById("compareStatus");
  const comparisonSummary = document.getElementById("comparisonSummary");
  const comparisonResults = document.getElementById("comparisonResults");

  const writingForm = document.getElementById("writingForm");
  const draftTitle = document.getElementById("draftTitle");
  const draftType = document.getElementById("draftType");
  const draftDetail = document.getElementById("draftDetail");
  const draftObjective = document.getElementById("draftObjective");
  const draftNotes = document.getElementById("draftNotes");
  const draftStatus = document.getElementById("draftStatus");
  const draftOutput = document.getElementById("draftOutput");
  const downloadDraftButton = document.getElementById("downloadDraftButton");

  const chatCatiaSkill = document.getElementById("chatCatiaSkill");
  const catiaSkillCard = document.getElementById("catiaSkillCard");
  const skillsActiveCount = document.getElementById("skillsActiveCount");

  const systemStatusButton = document.getElementById("systemStatusButton");
  const systemStatusPopover = document.getElementById("systemStatusPopover");
  const systemStatusDot = document.getElementById("systemStatusDot");
  const systemStatusLabel = document.getElementById("systemStatusLabel");
  const embeddingStatus = document.getElementById("embeddingStatus");
  const embeddingModel = document.getElementById("embeddingModel");
  const embeddingDevice = document.getElementById("embeddingDevice");
  const ollamaStatus = document.getElementById("ollamaStatus");
  const llmModel = document.getElementById("llmModel");
  const systemStatusMessage = document.getElementById("systemStatusMessage");

  let toastTimer = null;
  let evidenceReturnFocus = evidenceToggle;
  let previewReturnFocus = null;
  let evidenceResizePointerId = null;
  let sourceResizePointerId = null;
  let chatProcessTimerId = null;
  let chatProcessCollapseTimerId = null;
  let chatProcessStartedAt = 0;
  let chatProcessMode = "document";
  let chatProcessExpectsRetrieval = true;
  const defaultEvidenceWidth = 340;
  const minimumEvidenceWidth = 280;
  const defaultSourceWidth = 304;
  const minimumSourceWidth = 250;
  const collapsedSourceWidth = 58;

  function evidenceWidthBounds() {
    const rootStyles = getComputedStyle(document.documentElement);
    const railWidth = parseFloat(rootStyles.getPropertyValue("--rail-width")) || 76;
    const sourceWidth = body.classList.contains("source-collapsed")
      ? collapsedSourceWidth
      : parseFloat(rootStyles.getPropertyValue("--source-width")) || defaultSourceWidth;
    const maximum = Math.min(720, window.innerWidth - railWidth - sourceWidth - 520);
    return { minimum: minimumEvidenceWidth, maximum: Math.max(minimumEvidenceWidth, maximum) };
  }

  function currentEvidenceWidth() {
    return parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--evidence-width")) || defaultEvidenceWidth;
  }

  function setEvidenceWidth(width) {
    const bounds = evidenceWidthBounds();
    const nextWidth = Math.round(Math.max(bounds.minimum, Math.min(bounds.maximum, Number(width) || defaultEvidenceWidth)));
    document.documentElement.style.setProperty("--evidence-width", `${nextWidth}px`);
    evidenceResizer.setAttribute("aria-valuemin", String(bounds.minimum));
    evidenceResizer.setAttribute("aria-valuemax", String(Math.round(bounds.maximum)));
    evidenceResizer.setAttribute("aria-valuenow", String(nextWidth));
  }

  function resetEvidenceWidth() {
    setEvidenceWidth(defaultEvidenceWidth);
  }

  function stopEvidenceResize(event) {
    if (event?.pointerId !== undefined && evidenceResizePointerId !== null && event.pointerId !== evidenceResizePointerId) return;
    if (evidenceResizePointerId !== null && evidenceResizer.hasPointerCapture(evidenceResizePointerId)) {
      evidenceResizer.releasePointerCapture(evidenceResizePointerId);
    }
    evidenceResizePointerId = null;
    body.classList.remove("evidence-resizing");
  }

  function sourceWidthBounds() {
    const rootStyles = getComputedStyle(document.documentElement);
    const railWidth = parseFloat(rootStyles.getPropertyValue("--rail-width")) || 76;
    const evidenceWidth = body.classList.contains("evidence-open") && !window.matchMedia("(max-width: 1120px)").matches
      ? currentEvidenceWidth()
      : 0;
    const maximum = Math.min(420, window.innerWidth - railWidth - evidenceWidth - 520);
    return { minimum: minimumSourceWidth, maximum: Math.max(minimumSourceWidth, maximum) };
  }

  function currentSourceWidth() {
    return parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--source-width")) || defaultSourceWidth;
  }

  function setSourceWidth(width) {
    const bounds = sourceWidthBounds();
    const nextWidth = Math.round(Math.max(bounds.minimum, Math.min(bounds.maximum, Number(width) || defaultSourceWidth)));
    document.documentElement.style.setProperty("--source-width", `${nextWidth}px`);
    sourceResizer.setAttribute("aria-valuemin", String(bounds.minimum));
    sourceResizer.setAttribute("aria-valuemax", String(Math.round(bounds.maximum)));
    sourceResizer.setAttribute("aria-valuenow", String(nextWidth));
  }

  function resetSourceWidth() {
    setSourceWidth(defaultSourceWidth);
  }

  function stopSourceResize(event) {
    if (event?.pointerId !== undefined && sourceResizePointerId !== null && event.pointerId !== sourceResizePointerId) return;
    if (sourceResizePointerId !== null && sourceResizer.hasPointerCapture(sourceResizePointerId)) {
      sourceResizer.releasePointerCapture(sourceResizePointerId);
    }
    sourceResizePointerId = null;
    body.classList.remove("source-resizing");
  }

  function setSourceCollapsed(collapsed) {
    const shouldCollapse = Boolean(collapsed) && !window.matchMedia("(max-width: 860px)").matches;
    body.classList.toggle("source-collapsed", shouldCollapse);
    toggleSourceSidebar.setAttribute("aria-expanded", String(!shouldCollapse));
    toggleSourceSidebar.setAttribute("aria-label", shouldCollapse ? "Kaynak panelini genişlet" : "Kaynak panelini daralt");
    toggleSourceSidebar.title = shouldCollapse ? "Kaynak panelini genişlet" : "Kaynak panelini daralt";
    if (body.classList.contains("evidence-open") && !window.matchMedia("(max-width: 1120px)").matches) {
      setEvidenceWidth(currentEvidenceWidth());
    }
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function clampText(value, length = 260) {
    const text = String(value ?? "").replace(/\s+/g, " ").trim();
    return text.length > length ? `${text.slice(0, length - 1)}…` : text;
  }

  function formatScore(value) {
    const number = Number(value);
    return Number.isFinite(number) ? `%${Math.round(Math.max(0, Math.min(1, number)) * 100)}` : "—";
  }

  function formatRelevance(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "—";
    return number <= 1 ? `%${Math.round(Math.max(0, number) * 100)}` : number.toFixed(2);
  }

  function cleanEvidenceExcerpt(value, documentTitle = "") {
    let text = String(value ?? "")
      .replace(/^(?:(?:[a-z]:\\)|(?:\\\\))[\s\S]*?\bpage\s+\d+\s*\/\s*\d+\s*/i, "")
      .replace(/^page\s+\d+\s*\/\s*\d+\s*/i, "")
      .replace(/\s+/g, " ")
      .trim();
    if (/^(?:[a-z]:\\|\\\\)/i.test(text) && documentTitle) {
      const titleIndex = text.toLocaleLowerCase("tr-TR").indexOf(String(documentTitle).toLocaleLowerCase("tr-TR"));
      if (titleIndex >= 0) text = text.slice(titleIndex + String(documentTitle).length).trim();
    }
    return text;
  }

  function parseFlowRateTable(value) {
    const text = cleanEvidenceExcerpt(value);
    if (!/volumetric\s+flowrate/i.test(text) || !/(?:mevcut\s+tasar[ıi]m|[öo]neri\s*-\s*\d+)/i.test(text)) return [];
    const markerPattern = /(mevcut\s+tasar[ıi]m(?=\s*\()|[öo]neri\s*-\s*\d+)\s*(\([^)]*\))?/gi;
    const markers = [...text.matchAll(markerPattern)];
    const rows = [];
    markers.forEach((marker, index) => {
      const start = Number(marker.index || 0);
      const end = index + 1 < markers.length ? Number(markers[index + 1].index || text.length) : text.length;
      const segment = text.slice(start, end);
      const numbers = [...segment.matchAll(/\b\d+(?:[.,]\d+)?\b/g)].map(match => match[0]);
      if (numbers.length < 2) return;
      const perSecond = Number(numbers.at(-2).replace(",", "."));
      const perHour = Number(numbers.at(-1).replace(",", "."));
      if (!Number.isFinite(perSecond) || !Number.isFinite(perHour) || perSecond >= 5 || perHour < 50) return;
      rows.push({
        design: `${marker[1].replace(/\s*-\s*/, "-")}${marker[2] ? ` ${marker[2]}` : ""}`,
        perSecond: numbers.at(-2),
        perHour: numbers.at(-1),
      });
    });
    return rows.slice(0, 8);
  }

  function evidenceTableHtml(excerpt) {
    const rows = parseFlowRateTable(excerpt);
    if (!rows.length) return "";
    return `
      <div class="evidence-table-wrap" role="region" aria-label="Pasajdan çıkarılan hava debisi tablosu" tabindex="0">
        <table class="evidence-table">
          <thead><tr><th>Tasarım</th><th>m³/s</th><th>m³/h</th></tr></thead>
          <tbody>${rows.map(row => `
            <tr><td>${escapeHtml(row.design)}</td><td>${escapeHtml(row.perSecond)}</td><td>${escapeHtml(row.perHour)}</td></tr>
          `).join("")}</tbody>
        </table>
      </div>
    `;
  }

  function evidenceFactHtml(label, value) {
    if (!String(value || "").trim()) return "";
    return `<div class="evidence-fact"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
  }

  function showToast(message) {
    window.clearTimeout(toastTimer);
    toast.textContent = message;
    toast.hidden = false;
    toastTimer = window.setTimeout(() => { toast.hidden = true; }, 4200);
  }

  async function readJson(response) {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) return response.json();
    const text = await response.text();
    return { detail: text || `Sunucu ${response.status} yanıtını döndürdü.` };
  }

  function requestError(data, fallback) {
    if (typeof data?.detail === "string" && data.detail.trim()) return data.detail;
    if (Array.isArray(data?.detail)) {
      const messages = data.detail
        .map(item => typeof item === "string" ? item : item?.msg)
        .filter(Boolean);
      if (messages.length) return messages.join(" ");
    }
    return fallback;
  }

  function createAnalyticsSessionId() {
    const storageKey = "smartaios.analytics.session_id";
    try {
      const stored = sessionStorage.getItem(storageKey);
      if (stored) return stored;
      const suffix = typeof crypto?.randomUUID === "function"
        ? crypto.randomUUID()
        : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
      const sessionId = `smartaios-${suffix}`;
      sessionStorage.setItem(storageKey, sessionId);
      return sessionId;
    } catch (_error) {
      return `smartaios-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    }
  }

  const analyticsSessionId = createAnalyticsSessionId();
  let accumulatedActiveSeconds = 0;
  let activeClockStartedAt = performance.now();
  let pageWasActive = document.visibilityState === "visible" && document.hasFocus();

  function captureActiveSeconds() {
    const now = performance.now();
    if (pageWasActive) accumulatedActiveSeconds += Math.max(0, (now - activeClockStartedAt) / 1000);
    activeClockStartedAt = now;
    pageWasActive = document.visibilityState === "visible" && document.hasFocus();
  }

  function analyticsHeartbeatPayload(seconds) {
    return {
      session_id: analyticsSessionId,
      application: "big_agent",
      current_view: state.activeView,
      active_seconds_delta: seconds,
    };
  }

  async function sendAnalyticsHeartbeat() {
    captureActiveSeconds();
    const seconds = Math.min(60, Math.floor(accumulatedActiveSeconds));
    if (seconds <= 0) return;
    accumulatedActiveSeconds -= seconds;
    try {
      const response = await fetch("/analytics/heartbeat", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(analyticsHeartbeatPayload(seconds)),
        keepalive: true,
      });
      if (!response.ok) accumulatedActiveSeconds += seconds;
    } catch (_error) {
      accumulatedActiveSeconds += seconds;
    }
  }

  function flushAnalyticsHeartbeat() {
    captureActiveSeconds();
    const seconds = Math.min(60, Math.floor(accumulatedActiveSeconds));
    if (seconds <= 0 || typeof navigator.sendBeacon !== "function") return;
    accumulatedActiveSeconds -= seconds;
    const body = new Blob([JSON.stringify(analyticsHeartbeatPayload(seconds))], { type: "application/json" });
    if (!navigator.sendBeacon("/analytics/heartbeat", body)) accumulatedActiveSeconds += seconds;
  }

  function updateScrim() {
    const sourceIsDrawer = window.matchMedia("(max-width: 860px)").matches;
    const sourceOpen = body.classList.contains("source-open");
    const evidenceOpen = body.classList.contains("evidence-open");
    const show = (sourceIsDrawer && sourceOpen) || (
      evidenceOpen && window.matchMedia("(max-width: 1120px)").matches
    );
    sourceSidebar.inert = sourceIsDrawer && !sourceOpen;
    sourceSidebar.setAttribute("aria-hidden", String(sourceIsDrawer && !sourceOpen));
    evidencePanel.inert = !evidenceOpen;
    mobileScrim.hidden = !show;
  }

  function openSources() {
    setSourceCollapsed(false);
    body.classList.add("source-open");
    updateScrim();
    window.setTimeout(() => sidebarDocumentFilter.focus(), 80);
  }

  function closeSources() {
    body.classList.remove("source-open");
    updateScrim();
  }

  function setEvidenceOpen(open, { focus = false, returnFocus = null, restoreFocus = false } = {}) {
    if (open && returnFocus instanceof HTMLElement) evidenceReturnFocus = returnFocus;
    body.classList.toggle("evidence-open", open);
    evidencePanel.setAttribute("aria-hidden", String(!open));
    evidenceToggle.setAttribute("aria-expanded", String(open));
    chatEvidenceButton.setAttribute("aria-expanded", String(open));
    updateScrim();
    if (open && focus) window.setTimeout(() => closeEvidencePanel.focus(), 80);
    if (!open && restoreFocus) {
      window.setTimeout(() => {
        const target = document.contains(evidenceReturnFocus) ? evidenceReturnFocus : evidenceToggle;
        target.focus();
      }, 0);
    }
  }

  function closeTransientPanels() {
    closeSources();
    if (window.matchMedia("(max-width: 1120px)").matches) {
      setEvidenceOpen(false, { restoreFocus: true });
    }
    systemStatusPopover.hidden = true;
    systemStatusButton.setAttribute("aria-expanded", "false");
  }

  function setView(view, { updateHash = true, focus = true } = {}) {
    if (!Object.hasOwn(viewMeta, view)) view = "home";
    state.activeView = view;
    body.dataset.activeView = view;

    document.querySelectorAll("[data-view]").forEach(section => {
      section.classList.toggle("active", section.dataset.view === view);
    });
    document.querySelectorAll(".rail-button[data-view-target]").forEach(button => {
      const active = button.dataset.viewTarget === view;
      button.classList.toggle("active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });

    activeViewOverline.textContent = viewMeta[view].overline;
    activeViewTitle.textContent = viewMeta[view].title;
    if (updateHash && window.location.hash !== `#${view}`) {
      history.replaceState(null, "", `#${view}`);
    }
    closeSources();
    if (view === "chat") {
      systemStatusPopover.hidden = true;
      systemStatusButton.setAttribute("aria-expanded", "false");
    }
    if (["home", "documents", "writing"].includes(view)) setEvidenceOpen(false);
    if (focus) workspaceMain.focus({ preventScroll: true });
    workspaceMain.scrollTo({ top: 0, behavior: "smooth" });
  }

  function documentById(documentId) {
    return state.documents.find(item => Number(item.document_id) === Number(documentId));
  }

  function fileTypeLabel(document) {
    const value = String(document?.file_type || document?.file_name?.split(".").pop() || "FILE").toUpperCase();
    return ["PDF", "DOCX", "PPTX"].includes(value) ? value : "FILE";
  }

  function openDocument(documentId, detail = false) {
    const route = detail ? `/documents/${Number(documentId)}` : `/documents/${Number(documentId)}/file`;
    window.open(route, "_blank", "noopener,noreferrer");
  }

  function closeDocumentPreview({ restoreFocus = false } = {}) {
    evidencePanel.classList.remove("preview-active");
    sourcePreviewPane.hidden = true;
    sourcePreviewFrame.src = "about:blank";
    sourcePreviewLoading.hidden = false;
    state.previewDocumentId = null;
    if (restoreFocus && previewReturnFocus instanceof HTMLElement && document.contains(previewReturnFocus)) {
      previewReturnFocus.focus();
    }
  }

  function previewDocument(documentId, pageNumber = 1, trigger = null, previewUrl = "") {
    const id = Number(documentId);
    const page = Math.max(1, Number(pageNumber) || 1);
    const documentData = documentById(id);
    state.previewDocumentId = id;
    previewReturnFocus = trigger instanceof HTMLElement ? trigger : null;
    sourcePreviewTitle.textContent = documentData?.title || `Doküman ${id}`;
    const isReviewPreview = String(previewUrl || "").includes("/review-preview");
    sourcePreviewMeta.textContent = `${fileTypeLabel(documentData)} · Sayfa ${page}${isReviewPreview ? " · Kontrol kanıtı işaretli" : ""}`;
    sourcePreviewLoading.hidden = false;
    sourcePreviewPane.hidden = false;
    evidencePanel.classList.add("preview-active");
    const previewBase = String(previewUrl || "").trim() || `/documents/${id}/preview?page=${page}`;
    sourcePreviewFrame.src = `${previewBase}#page=${page}&view=FitH&toolbar=0&navpanes=0`;
    setEvidenceOpen(true, { returnFocus: trigger });
    window.requestAnimationFrame(() => sourcePreviewPane.scrollIntoView({ block: "start", behavior: "smooth" }));
  }

  async function openDocumentFolder(documentId, trigger) {
    const button = trigger instanceof HTMLButtonElement ? trigger : null;
    if (button) button.disabled = true;
    try {
      const response = await fetch(`/documents/${Number(documentId)}/open-folder`, {
        method: "POST",
        headers: { Accept: "application/json" },
      });
      const data = await readJson(response);
      if (!response.ok) throw new Error(requestError(data, "Dokümanın klasörü açılamadı."));
      showToast(`${data.file_name || "Doküman"} klasörde gösterildi.`);
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Dokümanın klasörü açılamadı.");
    } finally {
      if (button) button.disabled = false;
    }
  }

  function selectedDocuments() {
    return [...state.selectedDocumentIds]
      .map(documentById)
      .filter(Boolean);
  }

  function contextLabel() {
    const count = state.selectedDocumentIds.size;
    return count ? `${count} seçili doküman` : "Tüm dokümanlar";
  }

  function renderContext() {
    const selected = selectedDocuments();
    selectedContextCount.textContent = `${selected.length} seçili`;
    sourceSelectedCount.textContent = String(selected.length);
    sourceSelectionBar.classList.toggle("has-selection", selected.length > 0);
    clearContextButton.disabled = selected.length === 0;
    homeContextHint.textContent = selected.length ? `${selected.length} doküman bağlama eklendi` : "Tüm dokümanlar kullanılacak";
    chatContextHint.textContent = state.activeChatSkill === "catia"
      ? `CATIA skill · ${state.catiaSource === "catia" ? "gerçek montaj" : "fake montaj"}`
      : contextLabel();
    skillContextHint.textContent = selected.length
      ? `${selected.length} doküman skill bağlamına eklendi`
      : "Henüz doküman seçilmedi";
    draftStatus.textContent = selected.length
      ? `${selected.length} seçili doküman kaynak olarak kullanılacak.`
      : "Kaynak seçilmedi; SmartCAE ilgili dokümanları arayacak.";
  }

  function toggleDocumentContext(documentId, desiredState = null) {
    const id = Number(documentId);
    const shouldSelect = desiredState === null ? !state.selectedDocumentIds.has(id) : desiredState;
    if (shouldSelect && !state.selectedDocumentIds.has(id) && state.selectedDocumentIds.size >= 8) {
      showToast("Aynı çalışmada en fazla 8 doküman seçilebilir.");
      return;
    }
    if (shouldSelect) state.selectedDocumentIds.add(id);
    else state.selectedDocumentIds.delete(id);
    renderSourceDocuments();
    renderDocumentGrid();
    renderContext();
  }

  function filteredDocuments(filterValue) {
    const query = String(filterValue || "").trim().toLocaleLowerCase("tr-TR");
    if (!query) return state.documents;
    return state.documents.filter(document => `${document.title} ${document.file_name} ${document.file_type}`.toLocaleLowerCase("tr-TR").includes(query));
  }

  function renderSourceDocuments() {
    const matchingDocuments = filteredDocuments(sidebarDocumentFilter.value);
    const documents = state.sourceFilter === "selected"
      ? matchingDocuments.filter(document => state.selectedDocumentIds.has(Number(document.document_id)))
      : matchingDocuments;
    sourceAllCount.textContent = String(state.documents.length);
    sourceSelectedCount.textContent = String(state.selectedDocumentIds.size);
    sourceFilterButtons.forEach(button => {
      const active = button.dataset.sourceFilter === state.sourceFilter;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
    });
    if (!documents.length) {
      const message = state.sourceFilter === "selected"
        ? "Henüz doküman seçmedin."
        : "Eşleşen doküman bulunamadı.";
      sourceDocumentList.innerHTML = `<p class="empty-state">${message}</p>`;
      return;
    }
    sourceDocumentList.innerHTML = documents.map(document => {
      const id = Number(document.document_id);
      const selected = state.selectedDocumentIds.has(id);
      const fileType = fileTypeLabel(document);
      const fileClass = fileType.toLocaleLowerCase("tr-TR");
      const passageCount = Number(document.chunk_count || 0);
      return `
        <button class="source-document${selected ? " selected" : ""}" type="button" data-context-document="${id}" aria-pressed="${selected}">
          <span class="file-badge file-badge-${fileClass}">${fileType}</span>
          <span class="source-document-copy">
            <strong title="${escapeHtml(document.title)}">${escapeHtml(document.title)}</strong>
            <span title="${escapeHtml(document.file_name)}">${passageCount} pasaj · ${escapeHtml(document.file_name)}</span>
          </span>
          <span class="source-document-check" aria-hidden="true"></span>
        </button>
      `;
    }).join("");
    sourceDocumentList.querySelectorAll("[data-context-document]").forEach(button => {
      button.addEventListener("click", () => toggleDocumentContext(Number(button.dataset.contextDocument)));
    });
  }

  function renderRecentDocuments() {
    const items = state.documents.slice(0, 3);
    if (!items.length) {
      recentDocuments.innerHTML = '<p class="empty-state">Henüz eklenmiş doküman yok.</p>';
      return;
    }
    recentDocuments.innerHTML = items.map(document => `
      <button class="recent-document" type="button" data-open-document="${Number(document.document_id)}">
        <span class="file-badge">${fileTypeLabel(document)}</span>
        <span>
          <strong title="${escapeHtml(document.title)}">${escapeHtml(document.title)}</strong>
          <span>${escapeHtml(document.created_at || document.file_name)}</span>
        </span>
      </button>
    `).join("");
    recentDocuments.querySelectorAll("[data-open-document]").forEach(button => {
      button.addEventListener("click", () => openDocument(Number(button.dataset.openDocument)));
    });
  }

  function renderDocumentGrid() {
    const items = filteredDocuments(documentPageFilter.value);
    documentListMeta.textContent = `${items.length} / ${state.documents.length} doküman`;
    if (!items.length) {
      documentGrid.innerHTML = '<p class="empty-state">Eşleşen doküman bulunamadı.</p>';
      return;
    }
    documentGrid.innerHTML = items.map(document => {
      const id = Number(document.document_id);
      const selected = state.selectedDocumentIds.has(id);
      return `
        <article class="document-card">
          <span class="file-badge">${fileTypeLabel(document)}</span>
          <div class="document-card-copy">
            <strong title="${escapeHtml(document.title)}">${escapeHtml(document.title)}</strong>
            <span title="${escapeHtml(document.file_name)}">${escapeHtml(document.file_name)}</span>
            <div class="document-card-meta"><span>${Number(document.chunk_count || 0)} pasaj</span><span>${escapeHtml(document.created_at || "")}</span></div>
            <div class="document-card-actions">
              <button class="mini-button" type="button" data-open-document="${id}">Dosyayı aç</button>
              <button class="mini-button" type="button" data-grid-context="${id}">${selected ? "Bağlamdan çıkar" : "Bağlama ekle"}</button>
            </div>
          </div>
        </article>
      `;
    }).join("");
    documentGrid.querySelectorAll("[data-open-document]").forEach(button => {
      button.addEventListener("click", () => openDocument(Number(button.dataset.openDocument)));
    });
    documentGrid.querySelectorAll("[data-grid-context]").forEach(button => {
      button.addEventListener("click", () => toggleDocumentContext(Number(button.dataset.gridContext)));
    });
  }

  function comparisonPairCount() {
    const count = state.comparisonDocumentIds.length;
    if (count < 2) return 0;
    return compareMode.value === "all_pairs" ? (count * (count - 1)) / 2 : count - 1;
  }

  function renderComparePicker() {
    const currentValue = compareDocumentPicker.value;
    const query = compareDocumentFilter.value.trim().toLocaleLowerCase("tr-TR");
    const selected = new Set(state.comparisonDocumentIds);
    const available = state.documents.filter(document => {
      const id = Number(document.document_id);
      if (selected.has(id)) return false;
      if (!query) return true;
      return `${document.title || ""} ${document.file_name || ""}`.toLocaleLowerCase("tr-TR").includes(query);
    });
    compareDocumentPicker.innerHTML = '<option value="">Doküman seç</option>' + available.map(document => (
      `<option value="${Number(document.document_id)}">${escapeHtml(document.title)} · ${escapeHtml(fileTypeLabel(document))}</option>`
    )).join("");
    if (available.some(item => String(item.document_id) === currentValue)) {
      compareDocumentPicker.value = currentValue;
    }
    compareAddButton.disabled = !Number(compareDocumentPicker.value);
  }

  function renderComparisonSelection() {
    const validIds = state.comparisonDocumentIds.filter(id => documentById(id));
    state.comparisonDocumentIds = validIds;
    if (!validIds.includes(Number(state.comparisonReferenceId))) {
      state.comparisonReferenceId = validIds[0] || null;
    }
    compareSelectedCount.textContent = `${validIds.length} doküman seçildi`;
    if (!validIds.length) {
      compareSelection.innerHTML = '<p class="empty-state">Karşılaştırmak için en az iki doküman ekle.</p>';
    } else {
      compareSelection.innerHTML = validIds.map((id, index) => {
        const documentData = documentById(id);
        const reference = Number(state.comparisonReferenceId) === id;
        return `
          <article class="compare-source-card ${reference ? "reference" : ""}" role="listitem">
            <label class="compare-reference-control" title="Referans doküman">
              <input type="radio" name="compareReference" value="${id}" ${reference ? "checked" : ""}>
              <span aria-hidden="true">★</span><span class="visually-hidden">Referans yap</span>
            </label>
            <span class="file-badge">${escapeHtml(fileTypeLabel(documentData))}</span>
            <div class="compare-source-copy"><strong>${escapeHtml(documentData.title || `Doküman ${index + 1}`)}</strong><small>${escapeHtml(documentData.file_name || "")}</small></div>
            <span class="compare-source-role">${reference ? "Referans" : `${index + 1}. kaynak`}</span>
            <button class="icon-button compare-remove-button" type="button" data-remove-comparison="${id}" aria-label="${escapeHtml(documentData.title || "Doküman")} kaynağını kaldır">×</button>
          </article>
        `;
      }).join("");
    }
    const pairCount = comparisonPairCount();
    comparePairEstimate.textContent = String(pairCount);
    compareRunButton.disabled = validIds.length < 2;
    compareRunButton.textContent = validIds.length >= 2
      ? `${validIds.length} dokümanı karşılaştır`
      : "Dokümanları karşılaştır";
    compareModeNote.textContent = compareMode.value === "all_pairs"
      ? `Her doküman diğerleriyle karşılaştırılır; toplam ${pairCount} ayrı işlem çalışır.`
      : `Referans doküman diğer ${Math.max(validIds.length - 1, 0)} dokümanla karşılaştırılır.`;
    renderComparePicker();
  }

  function addComparisonDocument(documentId) {
    const id = Number(documentId);
    if (!id || !documentById(id) || state.comparisonDocumentIds.includes(id)) return false;
    state.comparisonDocumentIds.push(id);
    if (!state.comparisonReferenceId) state.comparisonReferenceId = id;
    renderComparisonSelection();
    return true;
  }

  function addContextDocumentsToComparison() {
    let added = 0;
    state.selectedDocumentIds.forEach(id => {
      if (addComparisonDocument(id)) added += 1;
    });
    compareStatus.textContent = added
      ? `${added} bağlam dokümanı karşılaştırma listesine eklendi.`
      : "Bağlamda eklenebilecek yeni doküman yok.";
  }

  function renderWorkspaceMetrics() {
    const totalChunks = state.documents.reduce((sum, item) => sum + Number(item.chunk_count || 0), 0);
    const totalEmbeddings = state.documents.reduce((sum, item) => sum + Number(item.embedding_count || 0), 0);
    const coverage = totalChunks ? Math.min(100, Math.round((totalEmbeddings / totalChunks) * 100)) : 0;
    documentMetric.textContent = String(state.documents.length);
    embeddingCoverageBar.style.width = `${coverage}%`;
    embeddingCoverageText.textContent = totalChunks
      ? `Embedding kapsamı %${coverage}`
      : "Henüz indekslenmiş pasaj yok.";
  }

  function renderAllDocuments() {
    renderSourceDocuments();
    renderRecentDocuments();
    renderDocumentGrid();
    renderComparisonSelection();
    renderWorkspaceMetrics();
    renderContext();
  }

  async function loadDocuments({ quiet = false } = {}) {
    if (!quiet) sidebarStatus.textContent = "Dokümanlar yükleniyor…";
    refreshDocumentsButton.disabled = true;
    try {
      const response = await fetch("/documents/list?limit=300", { headers: { Accept: "application/json" } });
      const data = await readJson(response);
      if (!response.ok) throw new Error(requestError(data, "Doküman listesi alınamadı."));
      state.documents = Array.isArray(data.items) ? data.items : [];
      for (const id of [...state.selectedDocumentIds]) {
        if (!documentById(id)) state.selectedDocumentIds.delete(id);
      }
      renderAllDocuments();
      sidebarStatus.textContent = `${Number(data.total || state.documents.length)} doküman kullanıma hazır.`;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Dokümanlar yüklenemedi.";
      sourceDocumentList.innerHTML = `<p class="empty-state">${escapeHtml(message)}</p>`;
      documentGrid.innerHTML = `<p class="empty-state">${escapeHtml(message)}</p>`;
      recentDocuments.innerHTML = `<p class="empty-state">${escapeHtml(message)}</p>`;
      sidebarStatus.textContent = message;
    } finally {
      refreshDocumentsButton.disabled = false;
    }
  }

  async function uploadDocuments(files) {
    const supported = [...files].filter(file => /\.(pdf|docx|pptx)$/i.test(file.name));
    if (!supported.length) {
      showToast("PDF, DOCX veya PPTX dosyası seçmelisin.");
      return;
    }
    const formData = new FormData();
    supported.forEach(file => formData.append("files", file));
    sidebarStatus.textContent = `${supported.length} doküman işleniyor…`;
    globalFilePicker.disabled = true;
    try {
      const response = await fetch("/ingest/batch", { method: "POST", body: formData });
      const data = await readJson(response);
      if (!response.ok) throw new Error(requestError(data, "Dokümanlar yüklenemedi."));
      const message = `${Number(data.ingested_count || 0)} yeni, ${Number(data.duplicate_count || 0)} mevcut, ${Number(data.error_count || 0)} hatalı.`;
      showToast(message);
      sidebarStatus.textContent = message;
      await loadDocuments({ quiet: true });
      setView("documents");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Doküman yükleme başarısız.";
      sidebarStatus.textContent = message;
      showToast(message);
    } finally {
      globalFilePicker.disabled = false;
      globalFilePicker.value = "";
    }
  }

  function resetChat() {
    resetChatProcess();
    setChatSkillMode(null);
    state.chatHistory = [];
    state.chatContextDocumentIds = [];
    state.catiaSessionId = null;
    state.catiaRejectedRunId = null;
    setChatCatiaApproval(false);
    chatMessages.innerHTML = `
      <article class="message assistant-message">
        <div class="message-avatar" aria-hidden="true">🤖</div>
        <div class="message-bubble"><span class="message-author">SmartCAE AI</span><p>Yeni çalışma hazır. Bir mühendislik sorusu sorabilir veya soldan doküman seçebilirsin.</p></div>
      </article>
    `;
    setChatStatus();
    chatInput.value = "";
    resizeChatInput();
    chatSuggestions.hidden = false;
    renderEvidence([], "Yeni çalışmada henüz kaynak kullanılmadı.");
    setEvidenceOpen(false);
    setView("chat");
    chatInput.focus();
  }

  function retrievalVersionLabel(value) {
    if (value === "v1") return "RAG v1 · Klasik";
    if (value === "v3") return "RAG v3 · Haystack";
    return "RAG v2 · Beta";
  }

  function resizeChatInput() {
    chatInput.style.height = "auto";
    chatInput.style.height = `${Math.min(chatInput.scrollHeight, 120)}px`;
  }

  function formatChatProcessElapsed(milliseconds) {
    const seconds = Math.max(0, milliseconds / 1000);
    return seconds > 0 && seconds < 0.1 ? "<0.1 sn" : `${seconds.toFixed(1)} sn`;
  }

  function setChatStatus(message = "") {
    chatStatus.textContent = message;
    chatStatus.hidden = !message;
  }

  function setChatProcessStep(step, stateName, label, detail) {
    step.className = `chat-process-step${stateName ? ` ${stateName}` : ""}`;
    if (label) step.querySelector("strong").textContent = label;
    if (detail) step.querySelector("small").textContent = detail;
  }

  function setChatProcessProgress(value, label) {
    const progress = Math.max(0, Math.min(100, Number(value) || 0));
    chatProcess.style.setProperty("--process-progress", `${progress}%`);
    chatProcessTrack.setAttribute("aria-valuenow", String(progress));
    chatProcessTrack.setAttribute("aria-valuetext", label);
  }

  function updateChatProcessStage(milliseconds) {
    if (chatProcess.dataset.state !== "running") return;
    if (chatProcessMode === "catia") {
      if (milliseconds < 1600) {
        setChatProcessStep(chatProcessRetrievalStep, "active", "Skill planlama", "İstek güvenli komuta çevriliyor");
        setChatProcessStep(chatProcessEvidenceStep, "", "Komut doğrulama", "Harness sırasını bekliyor");
        setChatProcessStep(chatProcessGenerationStep, "", "CATIA işlemi", "Bekliyor");
        setChatProcessProgress(28, "CATIA skill planlama aşaması");
        return;
      }
      if (milliseconds < 4200) {
        setChatProcessStep(chatProcessRetrievalStep, "done", "Skill planlama", "İzinli komut hazırlandı");
        setChatProcessStep(chatProcessEvidenceStep, "active", "Komut doğrulama", "Güvenlik harness'ı kontrol ediyor");
        setChatProcessStep(chatProcessGenerationStep, "", "CATIA işlemi", "Bekliyor");
        setChatProcessProgress(54, "CATIA komut doğrulama aşaması");
        return;
      }
      setChatProcessStep(chatProcessRetrievalStep, "done", "Skill planlama", "İzinli komut hazırlandı");
      setChatProcessStep(chatProcessEvidenceStep, "done", "Komut doğrulama", "Harness kontrolü tamamlandı");
      setChatProcessStep(chatProcessGenerationStep, "active", "CATIA işlemi", "Ölçüm veya çıktı hazırlanıyor");
      setChatProcessProgress(78, "CATIA işlem aşaması");
      return;
    }
    if (!chatProcessExpectsRetrieval) {
      setChatProcessStep(chatProcessRetrievalStep, "skipped", "Kaynak tarama", "Genel modda gerekmiyor");
      setChatProcessStep(chatProcessEvidenceStep, "skipped", "Kanıt seçimi", "Kaynak kullanılmayacak");
      setChatProcessStep(chatProcessGenerationStep, "active", "Yanıt üretimi", "Genel model cevaplıyor");
      setChatProcessProgress(72, "Yanıt üretimi aşaması");
      return;
    }
    if (milliseconds < 1800) {
      setChatProcessStep(chatProcessRetrievalStep, "active", "Kaynak tarama", "Raporlar ve pasajlar aranıyor");
      setChatProcessStep(chatProcessEvidenceStep, "", "Kanıt seçimi", "En ilgili pasajlar seçilecek");
      setChatProcessStep(chatProcessGenerationStep, "", "Yanıt üretimi", "Model sırasını bekliyor");
      setChatProcessProgress(24, "Kaynak tarama aşaması");
      return;
    }
    if (milliseconds < 4500) {
      setChatProcessStep(chatProcessRetrievalStep, "done", "Kaynak tarama", "RAG araması yürütüldü");
      setChatProcessStep(chatProcessEvidenceStep, "active", "Kanıt seçimi", "Pasajlar sıralanıyor");
      setChatProcessStep(chatProcessGenerationStep, "", "Yanıt üretimi", "Model sırasını bekliyor");
      setChatProcessProgress(48, "Kanıt seçimi aşaması");
      return;
    }
    setChatProcessStep(chatProcessRetrievalStep, "done", "Kaynak tarama", "RAG araması yürütüldü");
    setChatProcessStep(chatProcessEvidenceStep, "done", "Kanıt seçimi", "İlgili pasajlar işleniyor");
    setChatProcessStep(chatProcessGenerationStep, "active", "Yanıt üretimi", "Model kaynaklı cevap yazıyor");
    setChatProcessProgress(74, "Yanıt üretimi aşaması");
  }

  function stopChatProcessTimer() {
    if (chatProcessTimerId !== null) {
      window.clearInterval(chatProcessTimerId);
      chatProcessTimerId = null;
    }
  }

  async function saveReviewDecision(item, decision, trigger) {
    const button = trigger instanceof HTMLButtonElement ? trigger : null;
    const documentId = Number(item?.document_id || 0);
    const findingKey = String(item?.review_finding_key || "");
    const ruleId = String(item?.review_rule_id || "");
    if (!documentId || !findingKey || !ruleId) {
      showToast("Bu bulgu için karar kaydı oluşturulamadı.");
      return;
    }
    if (button) button.disabled = true;
    try {
      const response = await fetch("/report-review/decisions", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          document_id: documentId,
          finding_key: findingKey,
          rule_id: ruleId,
          decision,
          note: "",
          reviewer: "",
        }),
      });
      const data = await readJson(response);
      if (!response.ok) throw new Error(requestError(data, "İnceleme kararı kaydedilemedi."));
      item.human_decision = data.decision;
      item.human_decision_note = data.note || "";
      item.human_reviewer = data.reviewer || "";
      item.human_decided_at = data.decided_at || null;
      renderEvidence(state.evidence, evidenceIntro.textContent);
      showToast(data.decision === "confirmed" ? "Bulgu onaylandı." : data.decision === "dismissed" ? "Bulgu geçersiz olarak işaretlendi." : "Bulgu kararı kaldırıldı.");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "İnceleme kararı kaydedilemedi.");
    } finally {
      if (button) button.disabled = false;
    }
  }

  function exportReviewPdf() {
    const documentIds = [...new Set(
      state.evidence
        .filter(item => item.source_kind === "report_review")
        .map(item => Number(item.document_id || 0))
        .filter(Boolean),
    )].slice(0, 8);
    if (!documentIds.length) {
      showToast("Dışa aktarılacak kontrol kaydı bulunamadı.");
      return;
    }
    const params = new URLSearchParams();
    documentIds.forEach(documentId => params.append("document_ids", String(documentId)));
    window.location.assign(`/report-review/export?${params.toString()}`);
  }

  function stopChatProcessCollapseTimer() {
    if (chatProcessCollapseTimerId !== null) {
      window.clearTimeout(chatProcessCollapseTimerId);
      chatProcessCollapseTimerId = null;
    }
  }

  function setChatProcessCompact(compact) {
    chatProcess.classList.toggle("compact", compact);
    chatProcessToggle.setAttribute("aria-expanded", String(!compact));
    chatProcessToggle.setAttribute(
      "aria-label",
      compact ? "İşlem ayrıntılarını aç" : "İşlem ayrıntılarını daralt",
    );
  }

  function scheduleChatProcessCompact() {
    stopChatProcessCollapseTimer();
    chatProcessCollapseTimerId = window.setTimeout(() => {
      setChatProcessCompact(true);
      chatProcessCollapseTimerId = null;
    }, 4000);
  }

  function updateChatProcessElapsed() {
    if (!chatProcessStartedAt) return;
    const elapsed = performance.now() - chatProcessStartedAt;
    chatProcessElapsed.textContent = formatChatProcessElapsed(elapsed);
    updateChatProcessStage(elapsed);
  }

  function resetChatProcess() {
    stopChatProcessTimer();
    stopChatProcessCollapseTimer();
    chatProcessStartedAt = 0;
    chatProcessExpectsRetrieval = true;
    chatProcessMode = "document";
    chatProcess.hidden = true;
    chatProcess.dataset.state = "idle";
    setChatProcessCompact(false);
    chatProcess.style.removeProperty("--process-progress");
  }

  function startChatProcess() {
    stopChatProcessTimer();
    stopChatProcessCollapseTimer();
    setChatProcessCompact(false);
    chatProcessStartedAt = performance.now();
    chatProcessMode = "document";
    chatProcess.hidden = false;
    chatProcess.dataset.state = "running";
    chatProcessTitle.textContent = "SmartCAE çalışıyor";
    chatProcessElapsed.textContent = "0.0 sn";
    chatProcessExpectsRetrieval = chatAssistantMode.value !== "general";
    setChatProcessStep(chatProcessRequestStep, "done", "Soru gönderildi", "Sunucuya iletildi");
    setChatProcessStep(
      chatProcessRetrievalStep,
      "",
      state.thinkingMode ? "LLM bağlam çözümü" : "Kaynak tarama",
      state.thinkingMode ? "Soru yeniden yazılıyor" : "Başlatılıyor",
    );
    setChatProcessStep(chatProcessEvidenceStep, "", "Kanıt seçimi", "Bekliyor");
    setChatProcessStep(chatProcessGenerationStep, "", "Yanıt üretimi", "Bekliyor");
    setChatProcessStep(chatProcessResponseStep, "", "Tamamlandı", "Yanıt bekleniyor");
    const assistantLabel = chatAssistantMode.selectedOptions[0]?.textContent?.trim() || "Otomatik";
    const searchLabel = chatSearchMode.selectedOptions[0]?.textContent?.trim() || "Hibrit";
    const contextLabel = state.selectedDocumentIds.size
      ? `${state.selectedDocumentIds.size} seçili doküman`
      : "Tüm dokümanlar";
    const engineLabel = retrievalVersionLabel(chatRetrievalVersion.value).replaceAll(" · ", " ");
    const thinkingLabel = state.thinkingMode ? " · Muhakeme: Thinking" : "";
    chatProcessDetail.textContent = `Mod: ${assistantLabel} · Motor: ${engineLabel} · Arama: ${searchLabel} · Kapsam: ${contextLabel}${thinkingLabel}`;
    updateChatProcessElapsed();
    chatProcessTimerId = window.setInterval(updateChatProcessElapsed, 100);
  }

  function finishChatProcess({ sourceCount = 0, confidence = null, retrievalUsed = false, thinkingRequested = false, thinkingUsed = false, thinkingRoute = null, error = "" } = {}) {
    updateChatProcessElapsed();
    stopChatProcessTimer();
    const elapsedText = chatProcessElapsed.textContent;
    if (error) {
      chatProcess.dataset.state = "error";
      chatProcessTitle.textContent = "İşlem tamamlanamadı";
      [chatProcessRetrievalStep, chatProcessEvidenceStep, chatProcessGenerationStep].forEach(step => {
        if (step.classList.contains("active")) setChatProcessStep(step, "error", null, "Aşama tamamlanamadı");
      });
      setChatProcessStep(chatProcessResponseStep, "error", "Tamamlanamadı", "Yanıt alınamadı");
      chatProcess.style.setProperty("--process-progress", "100%");
      chatProcessTrack.removeAttribute("aria-valuenow");
      chatProcessTrack.setAttribute("aria-valuetext", "İşlem hata ile tamamlandı");
      chatProcessDetail.textContent = error;
      chatSuggestions.hidden = false;
      scheduleChatProcessCompact();
      return elapsedText;
    }
    chatProcess.dataset.state = "complete";
    chatProcessTitle.textContent = "Yanıt hazır";
    setChatProcessStep(chatProcessRequestStep, "done", "Soru gönderildi", "Sunucuya iletildi");
    if (retrievalUsed) {
      setChatProcessStep(
        chatProcessRetrievalStep,
        "done",
        thinkingUsed ? "LLM + kaynak" : "Kaynak tarama",
        sourceCount ? `${sourceCount} kaynak bulundu` : "Kaynak bulunamadı",
      );
      setChatProcessStep(
        chatProcessEvidenceStep,
        sourceCount ? "done" : "skipped",
        "Kanıt seçimi",
        sourceCount && Number.isFinite(Number(confidence)) ? `Güven ${formatScore(confidence)}` : "Kanıt kullanılmadı",
      );
    } else {
      setChatProcessStep(
        chatProcessRetrievalStep,
        thinkingUsed ? "done" : "skipped",
        thinkingUsed ? "LLM bağlam çözümü" : "Kaynak tarama",
        thinkingUsed ? `Yön: ${thinkingRoute === "general" ? "genel" : "doküman"}` : "Genel yanıtta kullanılmadı",
      );
      setChatProcessStep(chatProcessEvidenceStep, "skipped", "Kanıt seçimi", "Kaynak kullanılmadı");
    }
    setChatProcessStep(chatProcessGenerationStep, "done", "Yanıt üretimi", "Model yanıtı oluşturdu");
    setChatProcessStep(chatProcessResponseStep, "done", "Tamamlandı", `${elapsedText} içinde hazırlandı`);
    setChatProcessProgress(100, "İşlem tamamlandı");
    const engineLabel = retrievalUsed ? retrievalVersionLabel(chatRetrievalVersion.value) : "Genel model";
    const confidenceLabel = Number.isFinite(Number(confidence)) ? ` · güven ${formatScore(confidence)}` : "";
    const thinkingLabel = thinkingUsed
      ? " · Thinking kullanıldı"
      : (thinkingRequested ? " · Thinking yedeğe geçti" : "");
    chatProcessDetail.textContent = `${engineLabel} · ${sourceCount} kaynak${confidenceLabel}${thinkingLabel}`;
    chatSuggestions.hidden = false;
    scheduleChatProcessCompact();
    return elapsedText;
  }

  function appendMessage(role, content, meta = "") {
    const article = document.createElement("article");
    article.className = `message ${role === "user" ? "user-message" : "assistant-message"}`;
    const copy = document.createElement("div");
    copy.className = "message-bubble";
    const author = document.createElement("span");
    author.className = "message-author";
    author.textContent = role === "user" ? "Siz" : `SmartCAE AI${meta ? ` · ${meta}` : ""}`;
    const paragraph = document.createElement("p");
    paragraph.textContent = content;
    copy.append(author, paragraph);
    if (role === "user") {
      article.append(copy);
    } else {
      const avatar = document.createElement("div");
      avatar.className = "message-avatar";
      avatar.setAttribute("aria-hidden", "true");
      avatar.textContent = meta.includes("CATIA") ? "⚙️" : "🤖";
      article.append(avatar, copy);
    }
    chatMessages.appendChild(article);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function renderEvidence(items, intro = "") {
    closeDocumentPreview();
    state.evidence = Array.isArray(items) ? items : [];
    exportReviewButton.hidden = !state.evidence.some(item => item.source_kind === "report_review");
    chatEvidenceCount.textContent = `${state.evidence.length} kaynak`;
    evidenceIntro.textContent = intro || (
      state.evidence.length
        ? `${state.evidence.length} kaynak ve ilgili pasaj bulundu.`
        : "Henüz görüntülenecek bir kaynak yok."
    );
    if (!state.evidence.length) {
      evidenceList.innerHTML = '<p class="empty-state">Henüz görüntülenecek bir kaynak yok.</p>';
      return;
    }
    evidenceList.innerHTML = state.evidence.map((item, index) => {
      const title = item.document_title || item.title || item.file_name || `Kaynak ${index + 1}`;
      const documentId = Number(item.document_id || 0);
      const documentData = documentById(documentId) || {};
      const fileType = fileTypeLabel({ ...documentData, file_name: item.file_name || documentData.file_name });
      const pageStart = Number(item.page_start || 0);
      const pageEnd = Number(item.page_end || pageStart || 0);
      const pageCount = Number(documentData.page_count || 0);
      const pages = pageStart
        ? `Sayfa ${pageStart}${pageEnd && pageEnd !== pageStart ? `–${pageEnd}` : ""}${pageCount ? `/${pageCount}` : ""}`
        : (pageCount ? `${pageCount} sayfa` : "Doküman kaynağı");
      const rawExcerpt = item.chunk_text || item.excerpt || item.summary || "İlgili kaynak pasajı.";
      const excerpt = cleanEvidenceExcerpt(rawExcerpt, title) || "İlgili kaynak pasajı.";
      const authors = item.authors || documentData.authors || "";
      const reportDate = item.report_date || documentData.report_date || "";
      const reportTopic = item.report_title || documentData.report_title || "";
      const discipline = item.discipline || documentData.discipline || "";
      const isReviewEvidence = item.source_kind === "report_review";
      const reviewRuleId = String(item.review_rule_id || "");
      const reviewSeverity = ["critical", "warning", "info"].includes(item.review_severity)
        ? item.review_severity
        : "warning";
      const reviewSeverityLabel = {
        critical: "Kritik",
        warning: "Uyarı",
        info: "Bilgi",
      }[reviewSeverity];
      const reviewMessage = String(item.review_message || "").trim();
      const suggestedFix = String(item.suggested_fix || "").trim();
      const reviewEngine = String(item.review_engine || "").trim();
      const reviewFindingKey = String(item.review_finding_key || "").trim();
      const humanDecision = ["confirmed", "dismissed"].includes(item.human_decision)
        ? item.human_decision
        : "open";
      const humanDecisionLabel = {
        open: "İnceleme bekliyor",
        confirmed: "Onaylandı",
        dismissed: "Geçersiz",
      }[humanDecision];
      const revisionChange = ["new", "resolved", "continuing"].includes(item.review_revision_change)
        ? item.review_revision_change
        : "";
      const revisionChangeLabel = {
        new: "Yeni bulgu",
        resolved: "Giderildi",
        continuing: "Devam ediyor",
      }[revisionChange] || "";
      const isSemanticReview = reviewEngine.startsWith("llm:");
      const reviewRuleLabel = String(item.section_title || reviewRuleId || "Kontrol bulgusu").trim();
      const reviewPreviewUrl = isReviewEvidence
        && item.review_highlight_available
        && fileType === "PDF"
        && reviewRuleId
        ? `/documents/${documentId}/review-preview?rule_id=${encodeURIComponent(reviewRuleId)}&page=${Math.max(1, pageStart || 1)}`
        : "";
      const relevance = Number(item.combined_score);
      const relevanceLabel = !isReviewEvidence && Number.isFinite(relevance) && relevance > 0
        ? (relevance <= 1 ? `${formatRelevance(relevance)} eşleşme` : `${relevance.toFixed(2)} puan`)
        : "";
      const tableHtml = evidenceTableHtml(excerpt);
      const visibleFacts = [
        evidenceFactHtml("Hazırlayan", authors),
        evidenceFactHtml("Rapor tarihi", reportDate),
        evidenceFactHtml("Rapor konusu", reportTopic),
      ].join("");
      const openAttributes = documentId
        ? ` data-evidence-document="${documentId}" role="link" tabindex="0" aria-label="${escapeHtml(`${title} orijinal dosyasını aç`)}"`
        : "";
      return `
        <article class="evidence-card${documentId ? " is-openable" : ""}${isReviewEvidence ? ` is-review-evidence review-${reviewSeverity}` : ""}"${openAttributes}>
          <div class="evidence-card-head">
            <strong>${escapeHtml(title)}</strong>
            <div class="evidence-card-tools">
              ${documentId ? `
                <button class="result-action-button evidence-action-button preview-action" type="button" data-evidence-preview="${documentId}" data-evidence-page="${Math.max(1, pageStart || 1)}"${reviewPreviewUrl ? ` data-evidence-preview-url="${escapeHtml(reviewPreviewUrl)}"` : ""} aria-label="${escapeHtml(`${title} önizlemesini göster`)}" title="${isReviewEvidence && reviewPreviewUrl ? "İşaretli kontrol kanıtını aç" : "Kaynak önizlemesi"}">
                  <svg aria-hidden="true"><use href="#icon-eye"></use></svg>
                </button>
                <button class="result-action-button evidence-action-button folder-action" type="button" data-evidence-folder="${documentId}" aria-label="${escapeHtml(`${title} klasörünü aç`)}" title="Bulunduğu klasörü aç">
                  <svg aria-hidden="true"><use href="#icon-folder-open"></use></svg>
                </button>
              ` : ""}
              <span class="evidence-index">${isReviewEvidence ? "B" : "K"}${index + 1}</span>
            </div>
          </div>
          <div class="evidence-tags">
            <span class="evidence-tag file">${escapeHtml(fileType)}</span>
            <span class="evidence-tag">${escapeHtml(pages)}</span>
            ${discipline ? `<span class="evidence-tag">${escapeHtml(discipline)}</span>` : ""}
            ${relevanceLabel ? `<span class="evidence-tag score">${escapeHtml(relevanceLabel)}</span>` : ""}
            ${isReviewEvidence ? `<span class="evidence-tag review-severity ${reviewSeverity}">${escapeHtml(reviewSeverityLabel)}</span>` : ""}
            ${revisionChangeLabel ? `<span class="evidence-tag revision-change ${revisionChange}">${escapeHtml(revisionChangeLabel)}</span>` : ""}
            ${isSemanticReview ? '<span class="evidence-tag semantic-engine">LLM destekli</span>' : ""}
          </div>
          ${isReviewEvidence ? `
            <div class="review-evidence-callout ${reviewSeverity}">
              <span>${escapeHtml(reviewRuleLabel)}</span>
              <strong>${escapeHtml(reviewMessage || "Kontrol edilmesi gereken bir bulgu var.")}</strong>
              ${suggestedFix ? `<p><b>Öneri:</b> ${escapeHtml(suggestedFix)}</p>` : ""}
              ${reviewPreviewUrl ? `
                <button class="review-preview-cta" type="button" data-evidence-preview="${documentId}" data-evidence-page="${Math.max(1, pageStart || 1)}" data-evidence-preview-url="${escapeHtml(reviewPreviewUrl)}" aria-label="${escapeHtml(`${title} işaretli PDF kanıtını aç`)}">
                  <svg aria-hidden="true"><use href="#icon-eye"></use></svg>
                  <span>İşaretli PDF kanıtını aç</span>
                </button>
              ` : ""}
              ${reviewFindingKey ? `
                <div class="review-decision-row" data-review-state="${humanDecision}">
                  <span>${escapeHtml(humanDecisionLabel)}</span>
                  <div>
                    <button type="button" data-review-decision="confirmed" data-review-index="${index}" aria-pressed="${humanDecision === "confirmed"}">Onayla</button>
                    <button type="button" data-review-decision="dismissed" data-review-index="${index}" aria-pressed="${humanDecision === "dismissed"}">Geçersiz</button>
                    ${humanDecision !== "open" ? `<button class="review-decision-reset" type="button" data-review-decision="open" data-review-index="${index}">Kaldır</button>` : ""}
                  </div>
                </div>
              ` : ""}
            </div>
          ` : ""}
          ${visibleFacts ? `<div class="evidence-facts">${visibleFacts}</div>` : ""}
          ${isReviewEvidence ? "" : (tableHtml || `<p class="evidence-excerpt">${escapeHtml(clampText(excerpt, 420))}</p>`)}
        </article>
      `;
    }).join("");
    evidenceList.querySelectorAll("[data-evidence-document]").forEach(card => {
      const documentId = Number(card.dataset.evidenceDocument);
      card.addEventListener("click", event => {
        if (event.target.closest("button, a")) return;
        openDocument(documentId);
      });
      card.addEventListener("keydown", event => {
        if (event.target !== card) return;
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        openDocument(documentId);
      });
    });
    evidenceList.querySelectorAll("[data-evidence-preview]").forEach(button => {
      button.addEventListener("click", event => {
        event.stopPropagation();
        previewDocument(
          Number(button.dataset.evidencePreview),
          Number(button.dataset.evidencePage || 1),
          button,
          button.dataset.evidencePreviewUrl || "",
        );
      });
    });
    evidenceList.querySelectorAll("[data-evidence-folder]").forEach(button => {
      button.addEventListener("click", event => {
        event.stopPropagation();
        openDocumentFolder(Number(button.dataset.evidenceFolder), button);
      });
    });
    evidenceList.querySelectorAll("[data-review-decision]").forEach(button => {
      button.addEventListener("click", event => {
        event.stopPropagation();
        const item = state.evidence[Number(button.dataset.reviewIndex)];
        saveReviewDecision(item, button.dataset.reviewDecision, button);
      });
    });
  }

  async function sendChatMessage(message) {
    if (state.activeChatSkill === "catia") {
      await sendCatiaMessage(message);
      return;
    }
    const cleanMessage = String(message || "").trim();
    if (chatSendButton.disabled) return;
    if (cleanMessage.length < 2 || cleanMessage.length > 1000) {
      const validationMessage = "Mesaj 2 ile 1000 karakter arasında olmalı.";
      setChatStatus(validationMessage);
      showToast(validationMessage);
      return;
    }
    setView("chat", { focus: false });
    chatSuggestions.hidden = true;
    appendMessage("user", cleanMessage);
    state.chatHistory.push({ role: "user", content: cleanMessage });
    chatInput.value = "";
    resizeChatInput();
    chatSendButton.disabled = true;
    setChatStatus();
    startChatProcess();

    try {
      const selectedContextIds = [...state.selectedDocumentIds].slice(0, 8);
      const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          message: cleanMessage,
          history: state.chatHistory.slice(-8),
          assistant_mode: chatAssistantMode.value,
          retrieval_version: chatRetrievalVersion.value,
          mode: chatSearchMode.value,
          limit: 5,
          thinking_mode: state.thinkingMode,
          document_ids: selectedContextIds.length
            ? selectedContextIds
            : state.chatContextDocumentIds.slice(0, 8),
        }),
      });
      const data = await readJson(response);
      if (!response.ok) throw new Error(requestError(data, "Asistan yanıt oluşturamadı."));
      const engine = data.retrieval_used
        ? `${retrievalVersionLabel(data.retrieval_version)} · ${formatScore(data.confidence)}${data.thinking_used ? " · Thinking" : ""}`
        : `Genel yanıt${data.thinking_used ? " · Thinking" : ""}`;
      appendMessage("assistant", data.answer || "Yanıt bulunamadı.", engine);
      state.chatHistory = Array.isArray(data.history)
        ? data.history.slice(-10)
        : [...state.chatHistory, { role: "assistant", content: data.answer || "" }].slice(-10);
      const sources = Array.isArray(data.sources) ? data.sources : [];
      const sourceDocumentIds = [...new Set(sources
        .map(source => Number(source.document_id))
        .filter(documentId => Number.isInteger(documentId) && documentId > 0)
      )].slice(0, 8);
      if (sourceDocumentIds.length) state.chatContextDocumentIds = sourceDocumentIds;
      renderEvidence(sources, sources.length
        ? `${sources.length} kaynak · güven ${formatScore(data.confidence)}`
        : "Bu yanıt için doküman kaynağı kullanılmadı.");
      if (sources.length) setEvidenceOpen(true);
      finishChatProcess({
        sourceCount: sources.length,
        confidence: data.confidence,
        retrievalUsed: Boolean(data.retrieval_used),
        thinkingRequested: state.thinkingMode,
        thinkingUsed: Boolean(data.thinking_used),
        thinkingRoute: data.thinking_route,
      });
      if (state.thinkingMode && !data.thinking_used) {
        showToast("Thinking Mode için LLM kullanılamadı; güvenli yedek akış çalıştı.");
      }
      setChatStatus();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Asistan yanıt veremedi.";
      appendMessage("assistant", `Yanıt oluşturulamadı: ${message}`);
      const elapsedText = finishChatProcess({ error: message });
      setChatStatus(`${message} · ${elapsedText}`);
    } finally {
      chatSendButton.disabled = false;
      chatInput.focus();
    }
  }

  function renderSearchResults(items, similarDocuments = []) {
    const allEvidence = [...items, ...similarDocuments.map(item => ({
      ...item,
      chunk_text: item.top_excerpt,
      page_start: item.top_page_start,
      page_end: item.top_page_end,
      section_title: item.top_section_title,
    }))];
    renderEvidence(allEvidence, `${items.length} pasaj ve ${similarDocuments.length} benzer doküman bulundu.`);
    if (!items.length) {
      searchResults.innerHTML = '<p class="empty-state">Bu sorguyla eşleşen pasaj bulunamadı.</p>';
      return;
    }
    searchResults.innerHTML = items.map((item, index) => {
      const documentId = Number(item.document_id);
      const page = Math.max(1, Number(item.page_start) || 1);
      const title = item.document_title || item.file_name || `Doküman ${documentId}`;
      const documentData = documentById(documentId) || {};
      const fileType = fileTypeLabel({ ...documentData, file_name: item.file_name || documentData.file_name });
      const pageEnd = Math.max(page, Number(item.page_end) || page);
      const pageCount = Number(documentData.page_count || 0);
      const pageLabel = `Sayfa ${page}${pageEnd !== page ? `–${pageEnd}` : ""}${pageCount ? `/${pageCount}` : ""}`;
      const excerpt = cleanEvidenceExcerpt(item.chunk_text, title) || "İlgili kaynak pasajı.";
      const authors = item.authors || documentData.authors || "";
      const reportDate = item.report_date || documentData.report_date || "";
      const reportTopic = item.report_title || documentData.report_title || "";
      const discipline = item.discipline || documentData.discipline || "";
      const relevance = Number(item.combined_score);
      const relevanceLabel = Number.isFinite(relevance) && relevance > 0
        ? (relevance <= 1 ? `${formatRelevance(relevance)} eşleşme` : `${relevance.toFixed(2)} puan`)
        : "";
      const visibleFacts = [
        evidenceFactHtml("Hazırlayan", authors),
        evidenceFactHtml("Rapor tarihi", reportDate),
        evidenceFactHtml("Rapor konusu", reportTopic),
      ].join("");
      const tableHtml = evidenceTableHtml(excerpt);
      return `
      <article class="result-card" role="link" tabindex="0" data-result-card-document="${documentId}" aria-label="${escapeHtml(title)} dosyasını aç">
        <div class="result-card-head">
          <h3>${escapeHtml(title)}</h3>
        </div>
        <div class="evidence-tags result-tags">
          <span class="evidence-tag file">${escapeHtml(fileType)}</span>
          <span class="evidence-tag">${escapeHtml(pageLabel)}</span>
          ${discipline ? `<span class="evidence-tag">${escapeHtml(discipline)}</span>` : ""}
          ${relevanceLabel ? `<span class="evidence-tag score">${escapeHtml(relevanceLabel)}</span>` : ""}
        </div>
        ${visibleFacts ? `<div class="evidence-facts result-evidence-facts">${visibleFacts}</div>` : ""}
        ${tableHtml || `<p class="result-excerpt">${escapeHtml(clampText(excerpt, 640))}</p>`}
        <div class="result-card-footer">
          <div class="result-meta">${item.section_title ? `Eşleşen bölüm: ${escapeHtml(item.section_title)}` : "Kaynak pasajı"}</div>
          <div class="result-card-actions" aria-label="Doküman işlemleri">
            <button class="result-action-button folder-action" type="button" data-result-folder="${documentId}" aria-label="${escapeHtml(title)} klasörünü aç" title="Bulunduğu klasörü aç"><svg><use href="#icon-folder-open"/></svg></button>
            <button class="result-action-button preview-action" type="button" data-result-preview="${documentId}" data-result-page="${page}" aria-label="${escapeHtml(title)} önizlemesini göster" title="Kaynaklarda önizle"><svg><use href="#icon-eye"/></svg></button>
          </div>
        </div>
      </article>
    `;
    }).join("");
    searchResults.querySelectorAll("[data-result-card-document]").forEach(card => {
      const openResult = () => openDocument(Number(card.dataset.resultCardDocument));
      card.addEventListener("click", event => {
        if (event.target.closest("button, a")) return;
        openResult();
      });
      card.addEventListener("keydown", event => {
        if (event.target !== card || !["Enter", " "].includes(event.key)) return;
        event.preventDefault();
        openResult();
      });
    });
    searchResults.querySelectorAll("[data-result-folder]").forEach(button => {
      button.addEventListener("click", event => {
        event.stopPropagation();
        openDocumentFolder(Number(button.dataset.resultFolder), button);
      });
    });
    searchResults.querySelectorAll("[data-result-preview]").forEach(button => {
      button.addEventListener("click", event => {
        event.stopPropagation();
        previewDocument(Number(button.dataset.resultPreview), Number(button.dataset.resultPage), button);
      });
    });
    if (allEvidence.length) setEvidenceOpen(true);
  }

  async function runSearch() {
    const query = searchQuery.value.trim();
    if (query.length < 2) {
      searchStatus.textContent = "En az iki karakterlik bir sorgu yaz.";
      return;
    }
    const submitButton = searchForm.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    searchStatus.textContent = "Dokümanlar ve ilgili pasajlar aranıyor…";
    try {
      const params = new URLSearchParams({
        query,
        mode: searchMode.value,
        limit: "8",
        search_scope: "content",
        use_query_enhancement: "true",
      });
      const response = await fetch(`/search?${params}`, { headers: { Accept: "application/json" } });
      const data = await readJson(response);
      if (!response.ok) throw new Error(requestError(data, "Arama tamamlanamadı."));
      const items = Array.isArray(data.results) ? data.results : [];
      const similar = Array.isArray(data.similar_documents) ? data.similar_documents : [];
      renderSearchResults(items, similar);
      searchStatus.textContent = `${items.length} pasaj · ${similar.length} benzer doküman · ${data.embedding_provider || "yerel indeks"}`;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Arama tamamlanamadı.";
      searchStatus.textContent = message;
      searchResults.innerHTML = `<p class="empty-state">${escapeHtml(message)}</p>`;
    } finally {
      submitButton.disabled = false;
    }
  }

  function comparisonEvidenceItems(data) {
    const result = [];
    (data.comparisons || []).forEach(comparison => {
      const pairResult = comparison.result || {};
      [...(pairResult.similarities || []), ...(pairResult.differences || [])].forEach(item => {
        if (item.left) result.push({ ...item.left, summary: item.summary });
        if (item.right) result.push({ ...item.right, summary: item.summary });
      });
    });
    return result.slice(0, 18);
  }

  function comparisonKindLabel(kind) {
    return {
      common: "Ortak",
      changed: "Değişen",
      conflict: "Çelişki",
      unique: "Yalnız bulunan",
    }[kind] || "Bulgu";
  }

  function renderAggregateRows(data) {
    const documents = Array.isArray(data.documents) ? data.documents : [];
    const rows = Array.isArray(data.rows) ? data.rows : [];
    if (!rows.length) return "";
    return `
      <section class="comparison-insights" aria-labelledby="comparisonInsightsTitle">
        <div class="comparison-results-heading"><div><span class="overline">TOPLU GÖRÜNÜM</span><h2 id="comparisonInsightsTitle">Dokümanlar arası bulgular</h2></div><span>${rows.length} konu grubu</span></div>
        <div class="comparison-insight-list">
          ${rows.slice(0, 24).map(row => {
            const present = (row.present_in || []).map(index => documents[Number(index)]?.title).filter(Boolean);
            const missing = (row.missing_from || []).map(index => documents[Number(index)]?.title).filter(Boolean);
            return `
              <article class="comparison-insight ${escapeHtml(row.kind || "common")}">
                <div class="comparison-insight-head"><span class="comparison-kind-badge">${comparisonKindLabel(row.kind)}</span><strong>${escapeHtml(row.topic || "Teknik bulgu")}</strong><span>Güven ${formatScore(row.confidence)}</span></div>
                <p>${escapeHtml(row.summary || "")}</p>
                <div class="comparison-document-tags">
                  ${present.map(title => `<span title="Bu konuda kanıt bulundu">${escapeHtml(title)}</span>`).join("")}
                  ${missing.length ? `<span class="missing" title="Bu konu için eşleşen kanıt bulunmadı">Eksik: ${escapeHtml(missing.join(", "))}</span>` : ""}
                </div>
              </article>
            `;
          }).join("")}
        </div>
      </section>
    `;
  }

  function renderPairComparison(comparison, index, documents) {
    const result = comparison.result || {};
    const left = documents[Number(comparison.left_index)] || result.left || {};
    const right = documents[Number(comparison.right_index)] || result.right || {};
    const items = [
      ...(result.similarities || []).map(item => ({ ...item, displayKind: "Benzerlik" })),
      ...(result.differences || []).map(item => ({ ...item, displayKind: "Fark" })),
    ];
    const viewerLink = result.comparison_id ? `
      <a class="secondary-button compact-button" href="/report-comparison/${encodeURIComponent(result.comparison_id)}/viewer" target="_blank" rel="noopener noreferrer">Renkli PDF görünümü</a>
    ` : "";
    return `
      <details class="comparison-pair" ${index === 0 ? "open" : ""}>
        <summary>
          <span class="comparison-pair-index">${String(index + 1).padStart(2, "0")}</span>
          <span class="comparison-pair-titles"><strong>${escapeHtml(left.title || "Doküman A")}</strong><span>↔</span><strong>${escapeHtml(right.title || "Doküman B")}</strong></span>
          <span class="comparison-pair-metrics"><b>${Number(result.similarity_count || 0)}</b> ortak · <b>${Number(result.difference_count || 0)}</b> fark · ${formatScore(result.coverage)} kapsam</span>
        </summary>
        <div class="comparison-pair-body">
          <div class="comparison-pair-actions">${viewerLink}<span>${escapeHtml(result.generation_provider || "deterministic")}${result.cache_hit ? " · önbellekten" : ""}</span></div>
          ${items.length ? `<div class="comparison-pair-items">${items.slice(0, 20).map(item => `
            <article class="comparison-card compact">
              <div class="comparison-card-head"><h3>${escapeHtml(item.topic || "Teknik bulgu")}</h3><span class="comparison-kind">${item.displayKind}</span></div>
              <p>${escapeHtml(item.summary || "")}</p>
              <div class="result-meta">Güven ${formatScore(item.confidence)}${item.difference_type ? ` · ${escapeHtml(item.difference_type)}` : ""}</div>
            </article>
          `).join("")}</div>` : '<p class="empty-state">Bu ikili için karşılaştırılabilir pasaj bulunamadı.</p>'}
        </div>
      </details>
    `;
  }

  function renderComparison(data) {
    comparisonSummary.hidden = false;
    comparisonSummary.innerHTML = `
      <div><span>Doküman</span><strong>${Number(data.source_count || 0)}</strong></div>
      <div><span>Karşılaştırma</span><strong>${Number(data.comparison_count || 0)}</strong></div>
      <div><span>Benzerlik</span><strong>${Number(data.similarity_count || 0)}</strong></div>
      <div><span>Fark</span><strong>${Number(data.difference_count || 0)}</strong></div>
      <div><span>Kapsam</span><strong>${formatScore(data.coverage)}</strong></div>
    `;
    const comparisons = Array.isArray(data.comparisons) ? data.comparisons : [];
    const documents = Array.isArray(data.documents) ? data.documents : [];
    if (!comparisons.length) {
      comparisonResults.innerHTML = '<p class="empty-state">Karşılaştırılabilir pasaj bulunamadı.</p>';
    } else {
      comparisonResults.innerHTML = `
        ${renderAggregateRows(data)}
        <section class="comparison-pairs" aria-labelledby="comparisonPairsTitle">
          <div class="comparison-results-heading"><div><span class="overline">AYRINTILI SONUÇLAR</span><h2 id="comparisonPairsTitle">İkili karşılaştırmalar</h2></div><span>${comparisons.length} karşılaştırma</span></div>
          ${comparisons.map((comparison, index) => renderPairComparison(comparison, index, documents)).join("")}
        </section>
      `;
    }
    const evidence = comparisonEvidenceItems(data);
    renderEvidence(evidence, `${Number(data.source_count || documents.length)} dokümandaki karşılaştırma kaynakları.`);
    if (evidence.length) setEvidenceOpen(true);
  }

  async function runComparison() {
    const sourceIds = [...state.comparisonDocumentIds];
    if (sourceIds.length < 2) {
      compareStatus.textContent = "En az iki farklı doküman eklemelisin.";
      return;
    }
    const referenceIndex = Math.max(sourceIds.indexOf(Number(state.comparisonReferenceId)), 0);
    compareRunButton.disabled = true;
    compareStatus.textContent = `${comparisonPairCount()} karşılaştırma hazırlanıyor…`;
    comparisonSummary.hidden = true;
    comparisonResults.innerHTML = '<p class="empty-state">Karşılaştırma hazırlanıyor.</p>';
    try {
      const response = await fetch("/report-comparison/multi", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          sources: sourceIds.map(documentId => ({ document_id: documentId })),
          mode: compareMode.value,
          reference_index: referenceIndex,
          use_llm: true,
        }),
      });
      const data = await readJson(response);
      if (!response.ok) throw new Error(requestError(data, "Karşılaştırma tamamlanamadı."));
      renderComparison(data);
      compareStatus.textContent = `${Number(data.comparison_count || 0)} karşılaştırmada ${Number(data.similarity_count || 0)} benzerlik ve ${Number(data.difference_count || 0)} fark bulundu.`;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Karşılaştırma tamamlanamadı.";
      compareStatus.textContent = message;
      comparisonResults.innerHTML = `<p class="empty-state">${escapeHtml(message)}</p>`;
    } finally {
      compareRunButton.disabled = state.comparisonDocumentIds.length < 2;
    }
  }

  function buildDraftPayload() {
    return {
      title: draftTitle.value.trim(),
      report_type: draftType.value.trim() || "Genel Teknik Doküman",
      report_no: "",
      report_date: new Date().toLocaleDateString("tr-TR"),
      prepared_by: "",
      checked_by: "",
      requested_by: "",
      classification: "GENEL / PUBLIC",
      objective: draftObjective.value.trim(),
      keywords: "",
      raw_notes: draftNotes.value.trim(),
      detail_level: draftDetail.value,
      mode: "hybrid",
      limit: 8,
      document_ids: [...state.selectedDocumentIds].slice(0, 8),
    };
  }

  async function generateDraft() {
    const payload = buildDraftPayload();
    if (payload.title.length < 3) {
      draftStatus.textContent = "Başlık en az üç karakter olmalı.";
      draftTitle.focus();
      return;
    }
    const submitButton = writingForm.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    downloadDraftButton.disabled = true;
    draftStatus.textContent = "Kaynaklar taranıyor ve taslak hazırlanıyor…";
    draftOutput.innerHTML = '<p class="empty-state">Taslak oluşturuluyor.</p>';
    try {
      const response = await fetch("/draft-report", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await readJson(response);
      if (!response.ok) throw new Error(requestError(data, "Taslak oluşturulamadı."));
      state.lastDraftPayload = payload;
      draftOutput.textContent = data.draft || "Taslak metni oluşturulamadı.";
      downloadDraftButton.disabled = false;
      const sources = Array.isArray(data.sources) ? data.sources : [];
      renderEvidence(sources, `${sources.length} kaynak taslak hazırlanırken kullanıldı.`);
      if (sources.length) setEvidenceOpen(true);
      draftStatus.textContent = `Taslak hazır · ${sources.length} kaynak · ${data.generation_provider || "yerel üretim"}`;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Taslak oluşturulamadı.";
      draftStatus.textContent = message;
      draftOutput.innerHTML = `<p class="empty-state">${escapeHtml(message)}</p>`;
    } finally {
      submitButton.disabled = false;
    }
  }

  async function downloadDraftPdf() {
    if (!state.lastDraftPayload) return;
    downloadDraftButton.disabled = true;
    draftStatus.textContent = "PDF hazırlanıyor…";
    try {
      const response = await fetch("/draft-report/pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state.lastDraftPayload),
      });
      if (!response.ok) {
        const data = await readJson(response);
        throw new Error(requestError(data, "PDF hazırlanamadı."));
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "SmartCAE_teknik_dokuman.pdf";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      draftStatus.textContent = "PDF indirildi.";
    } catch (error) {
      draftStatus.textContent = error instanceof Error ? error.message : "PDF hazırlanamadı.";
    } finally {
      downloadDraftButton.disabled = false;
    }
  }

  // CATIA ana sohbet yüzeyinde çalışır. Model yalnızca skill harness'ının izin
  // verdiği komutları kullanır; dışa aktarım yine açık kullanıcı onayı ister.
  const catiaStateBadges = {
    PREVIEW_READY: { tone: "pending", label: "Önizleme hazır" },
    NEEDS_CALIBRATION: { tone: "pending", label: "Kalibrasyon gerekli" },
    NEEDS_VEHICLE_INFO: { tone: "pending", label: "Araç bilgisi gerekli" },
    READY: { tone: "ok", label: "Hazır" },
    DONE: { tone: "ok", label: "Tamamlandı" },
    ERROR: { tone: "error", label: "Hata" },
  };

  const catiaWelcomeMessage = 'Merhaba. Araç, varyant ve revizyon numarasını yazarsan montajı tarayıp önizlemeyi hazırlarım. Önce ortamı kontrol etmek istersen "doctor" diyebilirsin.';

  function setCatiaBusy(busy) {
    state.catiaBusy = busy;
    chatSendButton.disabled = busy;
    chatCatiaApproveButton.disabled = busy;
    chatCatiaRejectButton.disabled = busy;
    chatCatiaResetButton.disabled = busy;
    chatSkillExitButton.disabled = busy;
  }

  function appendCatiaNode(node) {
    chatMessages.appendChild(node);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function appendCatiaMessage(role, content) {
    appendMessage(role, content, role === "user" ? "" : "CATIA skill");
  }

  function catiaTraceEntry(event) {
    if (event.kind === "command") {
      return {
        className: "catia-trace-entry command",
        html: `<span>Komut</span><code>${escapeHtml(event.text || "")}</code>`,
      };
    }
    if (event.kind === "result") {
      const badge = catiaStateBadges[String(event.state || "")];
      const failed = String(event.status || "") === "error";
      return {
        className: `catia-trace-entry result${failed ? " error" : ""}`,
        html: `
          <span>Sonuç</span>
          <div>
            ${badge ? `<span class="catia-state-badge ${badge.tone}">${escapeHtml(badge.label)}</span>` : ""}
            <p>${escapeHtml(event.message_tr || "Komut tamamlandı.")}</p>
            ${event.hint_tr ? `<p>${escapeHtml(event.hint_tr)}</p>` : ""}
            ${event.code ? `<p>Kod: ${escapeHtml(event.code)}</p>` : ""}
          </div>
        `,
      };
    }
    return {
      className: "catia-trace-entry harness",
      html: `<span>Harness</span><p>${escapeHtml(event.text || "")}</p>`,
    };
  }

  function renderCatiaEvents(events) {
    let trace = null;
    (Array.isArray(events) ? events : []).forEach(event => {
      if (event.kind === "model") {
        trace = null;
        appendCatiaMessage("assistant", event.text || "");
        return;
      }
      if (event.kind === "screen") {
        // Önizleme ve onay kodu yalnızca ekran kanalında görünür; modelin
        // bağlamına eklenmez.
        trace = null;
        const preview = document.createElement("article");
        preview.className = "catia-preview";
        preview.innerHTML = `
          <div class="catia-preview-head"><strong>Değişiklik önizlemesi</strong><span>Onay kodu yalnızca bu ekranda</span></div>
          <pre>${escapeHtml(event.text || "")}</pre>
        `;
        appendCatiaNode(preview);
        return;
      }
      if (!trace) {
        trace = document.createElement("div");
        trace.className = "catia-trace";
        appendCatiaNode(trace);
      }
      const rendered = catiaTraceEntry(event);
      const entry = document.createElement("div");
      entry.className = rendered.className;
      entry.innerHTML = rendered.html;
      trace.appendChild(entry);
      chatMessages.scrollTop = chatMessages.scrollHeight;
    });
  }

  function setChatCatiaApproval(pending, runId = "") {
    const dismissed = Boolean(runId) && runId === state.catiaRejectedRunId;
    state.catiaPendingRunId = runId || null;
    state.catiaApprovalPending = Boolean(pending) && !dismissed;
    chatCatiaApproval.hidden = !state.catiaApprovalPending;
    chatCatiaApprovalRun.textContent = state.catiaApprovalPending && runId ? `Ölçüm: ${runId}` : "";
  }

  function applyCatiaResponse(data) {
    state.catiaSessionId = data.session_id || state.catiaSessionId;
    renderCatiaEvents(data.events);
    setChatCatiaApproval(data.approval_pending, String(data.pending_run_id || ""));
    chatContextHint.textContent = state.catiaSessionId
      ? `CATIA oturumu ${state.catiaSessionId.slice(0, 8)} · ${state.catiaSource === "catia" ? "gerçek montaj" : "fake montaj"}`
      : `CATIA skill · ${state.catiaSource === "catia" ? "gerçek montaj" : "fake montaj"}`;
  }

  function startCatiaChatProcess() {
    stopChatProcessTimer();
    stopChatProcessCollapseTimer();
    setChatProcessCompact(false);
    chatProcessStartedAt = performance.now();
    chatProcessMode = "catia";
    chatProcessExpectsRetrieval = false;
    chatProcess.hidden = false;
    chatProcess.dataset.state = "running";
    chatProcessTitle.textContent = "CATIA skill çalışıyor";
    chatProcessElapsed.textContent = "0.0 sn";
    setChatProcessStep(chatProcessRequestStep, "done", "İstek gönderildi", "CATIA skill oturumuna iletildi");
    setChatProcessStep(chatProcessRetrievalStep, "active", "Skill planlama", "İstek güvenli komuta çevriliyor");
    setChatProcessStep(chatProcessEvidenceStep, "", "Komut doğrulama", "Bekliyor");
    setChatProcessStep(chatProcessGenerationStep, "", "CATIA işlemi", "Bekliyor");
    setChatProcessStep(chatProcessResponseStep, "", "Tamamlandı", "Sonuç bekleniyor");
    chatProcessDetail.textContent = `CATIA kütle / CG · ${state.catiaSource === "catia" ? "gerçek CATIA montajı" : "fake montaj"} · güvenli harness`;
    updateChatProcessElapsed();
    chatProcessTimerId = window.setInterval(updateChatProcessElapsed, 100);
  }

  function finishCatiaChatProcess({ error = "", skillState = "", approvalPending = false } = {}) {
    updateChatProcessElapsed();
    stopChatProcessTimer();
    const elapsedText = chatProcessElapsed.textContent;
    if (error) {
      chatProcess.dataset.state = "error";
      chatProcessTitle.textContent = "CATIA işlemi tamamlanamadı";
      [chatProcessRetrievalStep, chatProcessEvidenceStep, chatProcessGenerationStep].forEach(step => {
        if (step.classList.contains("active")) setChatProcessStep(step, "error", null, "Aşama tamamlanamadı");
      });
      setChatProcessStep(chatProcessResponseStep, "error", "Tamamlanamadı", "Skill yanıtı alınamadı");
      setChatProcessProgress(100, "CATIA işlemi hata ile tamamlandı");
      chatProcessDetail.textContent = error;
      scheduleChatProcessCompact();
      return elapsedText;
    }
    chatProcess.dataset.state = "complete";
    chatProcessTitle.textContent = approvalPending ? "CATIA önizlemesi hazır" : "CATIA turu tamamlandı";
    setChatProcessStep(chatProcessRetrievalStep, "done", "Skill planlama", "İzinli komut hazırlandı");
    setChatProcessStep(chatProcessEvidenceStep, "done", "Komut doğrulama", "Harness kontrolü tamamlandı");
    setChatProcessStep(chatProcessGenerationStep, "done", "CATIA işlemi", approvalPending ? "Önizleme üretildi" : "Komut çalıştırıldı");
    setChatProcessStep(chatProcessResponseStep, "done", "Tamamlandı", `${elapsedText} içinde hazırlandı`);
    setChatProcessProgress(100, "CATIA işlemi tamamlandı");
    chatProcessDetail.textContent = `${skillState || "CATIA skill"} · ${approvalPending ? "kullanıcı onayı bekleniyor" : "işlem tamamlandı"}`;
    scheduleChatProcessCompact();
    return elapsedText;
  }

  async function sendCatiaMessage(message) {
    const cleanMessage = String(message || "").trim();
    if (state.catiaBusy) return;
    if (cleanMessage.length < 2 || cleanMessage.length > 2000) {
      const validationMessage = "Mesaj 2 ile 2000 karakter arasında olmalı.";
      setChatStatus(validationMessage);
      showToast(validationMessage);
      return;
    }
    setView("chat", { focus: false });
    appendCatiaMessage("user", cleanMessage);
    const shortcut = state.catiaShortcut;
    state.catiaShortcut = null;
    chatInput.value = "";
    resizeChatInput();
    setCatiaBusy(true);
    setChatStatus();
    startCatiaChatProcess();
    try {
      const response = await fetch("/skills/catia-mass-cg/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ message: cleanMessage, session_id: state.catiaSessionId, shortcut }),
      });
      const data = await readJson(response);
      if (!response.ok) {
        if (response.status === 404) state.catiaSessionId = null;
        throw new Error(requestError(data, "Skill yanıt üretemedi."));
      }
      applyCatiaResponse(data);
      finishCatiaChatProcess({
        skillState: String(data.state || "CATIA skill"),
        approvalPending: Boolean(data.approval_pending),
      });
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Skill yanıt üretemedi.";
      appendCatiaMessage("assistant", `İstek tamamlanamadı: ${detail}`);
      finishCatiaChatProcess({ error: detail });
      setChatStatus(detail);
    } finally {
      setCatiaBusy(false);
      chatInput.focus();
    }
  }

  async function approveCatiaPreview() {
    if (state.catiaBusy || !state.catiaApprovalPending || !state.catiaSessionId) return;
    appendCatiaMessage("user", "Ekrandaki önizlemeyi onaylıyorum.");
    setCatiaBusy(true);
    startCatiaChatProcess();
    chatProcessTitle.textContent = "CATIA aktarımı çalışıyor";
    chatProcessDetail.textContent = "Kullanıcı onayı doğrulandı · Adams/Car .cmd çıktısı hazırlanıyor";
    try {
      const response = await fetch("/skills/catia-mass-cg/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ session_id: state.catiaSessionId }),
      });
      const data = await readJson(response);
      if (!response.ok) throw new Error(requestError(data, "Aktarım çalıştırılamadı."));
      applyCatiaResponse(data);
      finishCatiaChatProcess({ skillState: String(data.state || "Aktarım tamamlandı") });
      showToast("Onay verildi; aktarım skill harness'ı üzerinden çalıştırıldı.");
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Aktarım çalıştırılamadı.";
      appendCatiaMessage("assistant", `Aktarım yapılamadı: ${detail}`);
      finishCatiaChatProcess({ error: detail });
      showToast(detail);
    } finally {
      setCatiaBusy(false);
    }
  }

  function rejectCatiaPreview() {
    if (state.catiaBusy || !state.catiaApprovalPending) return;
    state.catiaRejectedRunId = state.catiaPendingRunId;
    setChatCatiaApproval(false);
    sendCatiaMessage("Onaylamıyorum, aktarma.");
  }

  function resetCatiaSession({ prefill = false } = {}) {
    resetChatProcess();
    state.catiaSessionId = null;
    state.catiaRejectedRunId = null;
    state.catiaShortcut = null;
    setChatCatiaApproval(false);
    chatMessages.innerHTML = `
      <article class="message assistant-message">
        <div class="message-avatar" aria-hidden="true">⚙️</div>
        <div class="message-bubble"><span class="message-author">SmartCAE AI · CATIA skill</span><p>${escapeHtml(catiaWelcomeMessage)}</p></div>
      </article>
    `;
    chatInput.value = prefill ? "ARAC-X / BASE / R04 montajından kütle ve CG çıkar." : "";
    resizeChatInput();
    renderContext();
    setChatStatus(prefill ? "Araç, varyant ve revizyon değerlerini düzenleyip gönderebilirsin." : "Yeni CATIA oturumu hazır.");
    chatInput.focus();
    if (prefill) chatInput.setSelectionRange(0, "ARAC-X / BASE / R04".length);
  }

  function setChatSkillMode(skillName) {
    const catiaActive = skillName === "catia";
    state.activeChatSkill = catiaActive ? "catia" : null;
    body.classList.toggle("catia-chat-active", catiaActive);
    chatSkillModeBar.hidden = !catiaActive;
    chatCatiaSuggestions.hidden = !catiaActive;
    chatSuggestions.hidden = catiaActive;
    chatControls.hidden = catiaActive;
    chatEvidenceButton.hidden = catiaActive;
    chatThinkingToggle.hidden = catiaActive;
    chatAgentIcon.textContent = catiaActive ? "⚙️" : "🤖";
    chatAgentName.textContent = catiaActive ? "SmartCAE AI · CATIA" : "SmartCAE AI";
    chatAgentDescription.textContent = catiaActive
      ? "Kütle, ağırlık merkezi ve atalet işlemleri güvenli skill harness'ıyla çalışır"
      : "Seçili dokümanlarla kaynaklı yanıt üretir";
    chatInput.maxLength = catiaActive ? 2000 : 1000;
    chatInput.placeholder = catiaActive
      ? "Örn. ARAC-X / BASE / R04 montajından kütle ve CG çıkar"
      : "Mühendislik sorunu yaz...";
    if (!catiaActive) setChatCatiaApproval(false);
    renderContext();
  }

  function activateCatiaChat(trigger) {
    if (!state.catiaAvailable) {
      showToast("CATIA skill bu istemcide kullanıma hazır değil.");
      return;
    }
    state.chatHistory = [];
    state.chatContextDocumentIds = [];
    state.catiaSessionId = null;
    state.catiaRejectedRunId = null;
    renderEvidence([], "CATIA skill işlemleri doküman kaynağı kullanmaz.");
    setEvidenceOpen(false);
    setChatSkillMode("catia");
    resetCatiaSession();
    setView("chat", { focus: false });
    const prompt = trigger?.dataset?.catiaPrompt || "ARAC-X / BASE / R04 montajından kütle ve CG çıkar.";
    const selectToken = trigger?.dataset?.catiaSelectToken || "ARAC-X / BASE / R04";
    state.catiaShortcut = trigger?.dataset?.catiaShortcut || null;
    chatInput.value = prompt;
    resizeChatInput();
    chatInput.focus();
    const tokenStart = prompt.indexOf(selectToken);
    if (tokenStart >= 0) chatInput.setSelectionRange(tokenStart, tokenStart + selectToken.length);
    else chatInput.setSelectionRange(prompt.length, prompt.length);
    setChatStatus("CATIA skill hazır. Değerleri düzenleyip ana sohbetten gönderebilirsin.");
  }

  function applyCatiaStatus(data) {
    const enabled = Boolean(data?.enabled);
    const available = enabled && data?.available !== false;
    const localClient = data?.local_client !== false;
    const usable = available && localClient;
    const usesCatia = String(data?.source || "") === "catia";

    state.catiaEnabled = enabled;
    state.catiaAvailable = usable;
    state.catiaSource = usesCatia ? "catia" : "fake";
    chatCatiaSkill.hidden = !usable;
    catiaSkillCard.hidden = !usable;
    skillsActiveCount.textContent = usable ? "4" : "3";
    chatCatiaModeDetail.textContent = `${usesCatia ? "Gerçek CATIA montajı" : "Fake montaj"} · ${data?.model || "yerel model"} · güvenli harness`;
    if (!usable && state.activeChatSkill === "catia") {
      resetChat();
      showToast(!enabled
        ? "CATIA skill devre dışı."
        : !available ? "CATIA skill paketi kullanılamıyor." : "CATIA skill yalnızca localhost üzerinden kullanılabilir.");
    }
  }

  async function loadCatiaStatus() {
    try {
      const response = await fetch("/skills/catia-mass-cg/status", { headers: { Accept: "application/json" } });
      const data = await readJson(response);
      if (!response.ok) throw new Error(requestError(data, "CATIA skill durumu alınamadı."));
      applyCatiaStatus(data);
    } catch (error) {
      applyCatiaStatus({ enabled: false });
      console.warn(error instanceof Error ? error.message : "CATIA skill durumu alınamadı.");
    }
  }

  function applySystemStatus(data) {
    const embedding = data.embedding || {};
    const ollama = data.ollama || {};
    const ready = Boolean(embedding.ready) && (!ollama.configured || Boolean(ollama.model_available));
    systemStatusDot.className = `status-dot ${ready ? "ready" : (embedding.state === "error" || ollama.state === "error" ? "error" : "checking")}`;
    systemStatusLabel.textContent = ready ? "Sistem hazır" : "Sistem uyarısı";
    embeddingStatus.textContent = embedding.ready ? "Hazır" : (embedding.fallback_active ? "Yedek mod" : "Kontrol gerekli");
    embeddingModel.textContent = embedding.active_model || embedding.configured_model || "—";
    embeddingDevice.textContent = String(embedding.device || "—").toUpperCase();
    llmModel.textContent = ollama.configured_model || "—";
    ollamaStatus.textContent = !ollama.configured
      ? "Devre dışı"
      : (ollama.connected ? (ollama.model_available ? "Bağlı · model hazır" : "Bağlı · model eksik") : "Bağlantı yok");
    systemStatusMessage.textContent = [embedding.message, ollama.message].filter(Boolean).join(" ") || "Sistem durumu güncel.";
  }

  async function loadSystemStatus() {
    if (state.systemStatusLoaded) return;
    try {
      const response = await fetch("/system/model-status", { headers: { Accept: "application/json" } });
      const data = await readJson(response);
      if (!response.ok) throw new Error(requestError(data, "Sistem durumu alınamadı."));
      applySystemStatus(data);
      state.systemStatusLoaded = true;
    } catch (error) {
      systemStatusDot.className = "status-dot error";
      systemStatusLabel.textContent = "Durum alınamadı";
      systemStatusMessage.textContent = error instanceof Error ? error.message : "Sistem durumu alınamadı.";
    }
  }

  document.querySelectorAll("[data-view-target]").forEach(control => {
    control.addEventListener("click", () => setView(control.dataset.viewTarget));
  });
  openSourceSidebar.addEventListener("click", openSources);
  closeSourceSidebar.addEventListener("click", closeSources);
  toggleSourceSidebar.addEventListener("click", () => {
    setSourceCollapsed(!body.classList.contains("source-collapsed"));
  });
  sourceResizer.addEventListener("pointerdown", event => {
    if (window.matchMedia("(max-width: 860px)").matches || body.classList.contains("source-collapsed")) return;
    event.preventDefault();
    sourceResizePointerId = event.pointerId;
    sourceResizer.setPointerCapture(event.pointerId);
    body.classList.add("source-resizing");
    setSourceWidth(event.clientX - sourceSidebar.getBoundingClientRect().left);
  });
  window.addEventListener("pointermove", event => {
    if (!body.classList.contains("source-resizing") || event.pointerId !== sourceResizePointerId) return;
    setSourceWidth(event.clientX - sourceSidebar.getBoundingClientRect().left);
  });
  window.addEventListener("pointerup", stopSourceResize);
  window.addEventListener("pointercancel", stopSourceResize);
  sourceResizer.addEventListener("dblclick", resetSourceWidth);
  sourceResizer.addEventListener("keydown", event => {
    const bounds = sourceWidthBounds();
    let nextWidth = null;
    if (event.key === "ArrowLeft") nextWidth = currentSourceWidth() - 24;
    if (event.key === "ArrowRight") nextWidth = currentSourceWidth() + 24;
    if (event.key === "Home") nextWidth = bounds.minimum;
    if (event.key === "End") nextWidth = bounds.maximum;
    if (nextWidth === null) return;
    event.preventDefault();
    setSourceWidth(nextWidth);
  });
  evidenceToggle.addEventListener("click", () => {
    const open = !body.classList.contains("evidence-open");
    setEvidenceOpen(open, { focus: open, returnFocus: evidenceToggle, restoreFocus: !open });
  });
  chatEvidenceButton.addEventListener("click", () => {
    const open = !body.classList.contains("evidence-open");
    setEvidenceOpen(open, { focus: open, returnFocus: chatEvidenceButton, restoreFocus: !open });
  });
  closeEvidencePanel.addEventListener("click", () => setEvidenceOpen(false, { restoreFocus: true }));
  evidenceResizer.addEventListener("pointerdown", event => {
    if (window.matchMedia("(max-width: 1120px)").matches) return;
    event.preventDefault();
    evidenceResizePointerId = event.pointerId;
    evidenceResizer.setPointerCapture(event.pointerId);
    body.classList.add("evidence-resizing");
    setEvidenceWidth(window.innerWidth - event.clientX);
  });
  window.addEventListener("pointermove", event => {
    if (!body.classList.contains("evidence-resizing") || event.pointerId !== evidenceResizePointerId) return;
    setEvidenceWidth(window.innerWidth - event.clientX);
  });
  window.addEventListener("pointerup", stopEvidenceResize);
  window.addEventListener("pointercancel", stopEvidenceResize);
  evidenceResizer.addEventListener("dblclick", resetEvidenceWidth);
  evidenceResizer.addEventListener("keydown", event => {
    const bounds = evidenceWidthBounds();
    let nextWidth = null;
    if (event.key === "ArrowLeft") nextWidth = currentEvidenceWidth() + 24;
    if (event.key === "ArrowRight") nextWidth = currentEvidenceWidth() - 24;
    if (event.key === "Home") nextWidth = bounds.minimum;
    if (event.key === "End") nextWidth = bounds.maximum;
    if (nextWidth === null) return;
    event.preventDefault();
    setEvidenceWidth(nextWidth);
  });
  closeSourcePreviewButton.addEventListener("click", () => closeDocumentPreview({ restoreFocus: true }));
  exportReviewButton.addEventListener("click", exportReviewPdf);
  sourcePreviewFrame.addEventListener("load", () => { sourcePreviewLoading.hidden = true; });
  mobileScrim.addEventListener("click", closeTransientPanels);
  refreshDocumentsButton.addEventListener("click", () => loadDocuments());
  sidebarDocumentFilter.addEventListener("input", renderSourceDocuments);
  sourceFilterButtons.forEach(button => {
    button.addEventListener("click", () => {
      state.sourceFilter = button.dataset.sourceFilter === "selected" ? "selected" : "all";
      renderSourceDocuments();
    });
  });
  clearContextButton.addEventListener("click", () => {
    state.selectedDocumentIds.clear();
    renderSourceDocuments();
    renderDocumentGrid();
    renderContext();
    showToast("Doküman seçimi temizlendi.");
  });
  documentPageFilter.addEventListener("input", renderDocumentGrid);
  globalFilePicker.addEventListener("change", () => uploadDocuments(globalFilePicker.files));
  newChatButton.addEventListener("click", resetChat);
  chatThinkingToggle.addEventListener("click", () => {
    state.thinkingMode = !state.thinkingMode;
    chatThinkingToggle.setAttribute("aria-checked", String(state.thinkingMode));
    showToast(state.thinkingMode
      ? "Thinking Mode açık: sohbet bağlamını yerel LLM çözecek."
      : "Thinking Mode kapalı: hızlı bağlam çözümü kullanılacak.");
  });
  chatProcessToggle.addEventListener("click", () => {
    stopChatProcessCollapseTimer();
    setChatProcessCompact(!chatProcess.classList.contains("compact"));
  });
  chatRetrievalVersion.addEventListener("change", () => {
    const selectedLabel = retrievalVersionLabel(chatRetrievalVersion.value);
    resetChat();
    setChatStatus(`${selectedLabel} seçildi. Yeni sohbet bağlamı hazır.`);
  });

  heroComposer.addEventListener("submit", event => {
    event.preventDefault();
    const prompt = heroPrompt.value.trim();
    if (!prompt) {
      heroPrompt.focus();
      return;
    }
    if (state.activeChatSkill === "catia") resetChat();
    heroPrompt.value = "";
    sendChatMessage(prompt);
  });

  chatComposer.addEventListener("submit", event => {
    event.preventDefault();
    sendChatMessage(chatInput.value);
  });

  [heroPrompt, chatInput].forEach(textarea => {
    textarea.addEventListener("keydown", event => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        textarea.closest("form").requestSubmit();
      }
    });
  });
  chatInput.addEventListener("input", () => {
    state.catiaShortcut = null;
    resizeChatInput();
  });

  document.querySelectorAll('[data-chat-skill="catia"]').forEach(button => {
    button.addEventListener("click", () => activateCatiaChat(button));
  });
  chatSkillExitButton.addEventListener("click", resetChat);
  chatCatiaResetButton.addEventListener("click", () => resetCatiaSession({ prefill: true }));
  chatCatiaApproveButton.addEventListener("click", approveCatiaPreview);
  chatCatiaRejectButton.addEventListener("click", rejectCatiaPreview);
  chatCatiaSuggestions.querySelectorAll("[data-catia-prompt]").forEach(button => {
    button.addEventListener("click", () => {
      const prompt = button.dataset.catiaPrompt || "";
      const selectToken = button.dataset.catiaSelectToken || "";
      state.catiaShortcut = button.dataset.catiaShortcut || null;
      chatInput.value = prompt;
      resizeChatInput();
      chatInput.focus();
      const tokenStart = selectToken ? prompt.indexOf(selectToken) : -1;
      if (tokenStart >= 0) chatInput.setSelectionRange(tokenStart, tokenStart + selectToken.length);
      else chatInput.setSelectionRange(prompt.length, prompt.length);
      setChatStatus("CATIA adımı hazır. Değerleri düzenleyip gönderebilirsin.");
    });
  });

  document.querySelectorAll("[data-prompt]").forEach(button => {
    button.addEventListener("click", () => {
      if (state.activeChatSkill === "catia") resetChat();
      const selectedCount = state.selectedDocumentIds.size;
      const contextPrompt = selectedCount > 1
        ? button.dataset.contextMultiPrompt
        : button.dataset.contextPrompt;
      const prompt = selectedCount > 0 && contextPrompt
        ? contextPrompt
        : button.dataset.prompt || "";
      const selectToken = selectedCount > 0 && contextPrompt
        ? ""
        : button.dataset.selectToken || "";
      const skillLaunch = Boolean(button.dataset.skillLaunch);
      if (skillLaunch) setView("chat", { focus: false });
      chatInput.value = prompt;
      if (button.dataset.assistantMode) chatAssistantMode.value = button.dataset.assistantMode;
      chatInput.focus();
      const tokenStart = selectToken ? prompt.indexOf(selectToken) : -1;
      if (tokenStart >= 0) chatInput.setSelectionRange(tokenStart, tokenStart + selectToken.length);
      else chatInput.setSelectionRange(prompt.length, prompt.length);
      setChatStatus(skillLaunch
        ? "Skill komutu hazır. Metni kontrol edip gönderebilirsin."
        : "Örnek soru hazır. Metni düzenleyip gönderebilirsin.");
    });
  });

  searchForm.addEventListener("submit", event => {
    event.preventDefault();
    runSearch();
  });

  compareDocumentFilter.addEventListener("input", renderComparePicker);
  compareDocumentPicker.addEventListener("change", () => {
    compareAddButton.disabled = !Number(compareDocumentPicker.value);
  });
  compareAddButton.addEventListener("click", () => {
    if (addComparisonDocument(compareDocumentPicker.value)) {
      compareDocumentFilter.value = "";
      compareStatus.textContent = "Doküman karşılaştırma listesine eklendi.";
      renderComparePicker();
    }
  });
  compareDocumentPicker.addEventListener("dblclick", () => compareAddButton.click());
  compareAddContextButton.addEventListener("click", addContextDocumentsToComparison);
  compareMode.addEventListener("change", renderComparisonSelection);
  compareSelection.addEventListener("change", event => {
    const control = event.target.closest('input[name="compareReference"]');
    if (!control) return;
    state.comparisonReferenceId = Number(control.value);
    renderComparisonSelection();
  });
  compareSelection.addEventListener("click", event => {
    const button = event.target.closest("[data-remove-comparison]");
    if (!button) return;
    const id = Number(button.dataset.removeComparison);
    state.comparisonDocumentIds = state.comparisonDocumentIds.filter(item => item !== id);
    if (Number(state.comparisonReferenceId) === id) {
      state.comparisonReferenceId = state.comparisonDocumentIds[0] || null;
    }
    renderComparisonSelection();
    compareStatus.textContent = "Doküman karşılaştırma listesinden çıkarıldı.";
  });

  compareForm.addEventListener("submit", event => {
    event.preventDefault();
    runComparison();
  });

  writingForm.addEventListener("submit", event => {
    event.preventDefault();
    generateDraft();
  });
  downloadDraftButton.addEventListener("click", downloadDraftPdf);

  systemStatusButton.addEventListener("click", () => {
    const willOpen = systemStatusPopover.hidden;
    systemStatusPopover.hidden = !willOpen;
    systemStatusButton.setAttribute("aria-expanded", String(willOpen));
    if (willOpen) loadSystemStatus();
  });

  document.addEventListener("keydown", event => {
    if (event.key !== "Escape") return;
    if (body.classList.contains("source-open")) {
      closeSources();
      openSourceSidebar.focus();
    } else if (body.classList.contains("evidence-open")) {
      setEvidenceOpen(false, { restoreFocus: true });
    } else if (!systemStatusPopover.hidden) {
      systemStatusPopover.hidden = true;
      systemStatusButton.setAttribute("aria-expanded", "false");
      systemStatusButton.focus();
    }
  });

  window.addEventListener("hashchange", () => {
    const view = window.location.hash.slice(1);
    if (Object.hasOwn(viewMeta, view) && view !== state.activeView) {
      setView(view, { updateHash: false });
    }
  });
  window.addEventListener("resize", () => {
    if (window.matchMedia("(max-width: 860px)").matches) setSourceCollapsed(false);
    else if (!body.classList.contains("source-collapsed")) setSourceWidth(currentSourceWidth());
    updateScrim();
    if (!window.matchMedia("(max-width: 1120px)").matches) setEvidenceWidth(currentEvidenceWidth());
  });
  ["visibilitychange", "focus", "blur"].forEach(eventName => {
    const target = eventName === "visibilitychange" ? document : window;
    target.addEventListener(eventName, captureActiveSeconds);
  });
  window.addEventListener("pagehide", flushAnalyticsHeartbeat);
  window.setInterval(sendAnalyticsHeartbeat, 30_000);

  const initialView = window.location.hash.slice(1);
  if (window.matchMedia("(max-width: 860px)").matches) {
    setSourceCollapsed(false);
  } else {
    setSourceWidth(currentSourceWidth());
    setSourceCollapsed(true);
  }
  updateScrim();
  setView(Object.hasOwn(viewMeta, initialView) ? initialView : "home", { updateHash: false, focus: false });
  loadDocuments();
  loadCatiaStatus();
  window.setTimeout(loadSystemStatus, 300);
})();
