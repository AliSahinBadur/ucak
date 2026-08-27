(() => {
  "use strict";

  const viewMeta = {
    home: { overline: "MÜHENDİSLİK ÇALIŞMA ALANI", title: "Ana alan" },
    chat: { overline: "SMARTCAE COPILOT", title: "Kaynaklı mühendislik asistanı" },
    documents: { overline: "MÜHENDİSLİK ÇALIŞMA ALANI", title: "Dokümanlar" },
    search: { overline: "ANLAMSAL ARAMA", title: "Bilgiyi geçtiği yerde bul" },
    compare: { overline: "MÜHENDİSLİK ÇALIŞMA ALANI", title: "Karşılaştırma" },
    writing: { overline: "MÜHENDİSLİK ÇALIŞMA ALANI", title: "Doküman hazırlama" },
  };

  const state = {
    activeView: "home",
    documents: [],
    selectedDocumentIds: new Set(),
    sourceFilter: "all",
    chatHistory: [],
    evidence: [],
    previewDocumentId: null,
    lastDraftPayload: null,
    systemStatusLoaded: false,
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

  const heroComposer = document.getElementById("heroComposer");
  const heroPrompt = document.getElementById("heroPrompt");
  const chatComposer = document.getElementById("chatComposer");
  const chatInput = document.getElementById("chatInput");
  const chatMessages = document.getElementById("chatMessages");
  const chatSuggestions = document.getElementById("chatSuggestions");
  const chatStatus = document.getElementById("chatStatus");
  const chatProcess = document.getElementById("chatProcess");
  const chatProcessTitle = document.getElementById("chatProcessTitle");
  const chatProcessElapsed = document.getElementById("chatProcessElapsed");
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
  const chatEvidenceButton = document.getElementById("chatEvidenceButton");
  const chatEvidenceCount = document.getElementById("chatEvidenceCount");
  const newChatButton = document.getElementById("newChatButton");

  const searchForm = document.getElementById("searchForm");
  const searchQuery = document.getElementById("searchQuery");
  const searchMode = document.getElementById("searchMode");
  const searchStatus = document.getElementById("searchStatus");
  const searchResults = document.getElementById("searchResults");

  const compareForm = document.getElementById("compareForm");
  const compareLeft = document.getElementById("compareLeft");
  const compareRight = document.getElementById("compareRight");
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

  const systemStatusButton = document.getElementById("systemStatusButton");
  const systemStatusPopover = document.getElementById("systemStatusPopover");
  const systemStatusDot = document.getElementById("systemStatusDot");
  const systemStatusLabel = document.getElementById("systemStatusLabel");
  const embeddingStatus = document.getElementById("embeddingStatus");
  const embeddingModel = document.getElementById("embeddingModel");
  const embeddingDevice = document.getElementById("embeddingDevice");
  const ollamaStatus = document.getElementById("ollamaStatus");
  const systemStatusMessage = document.getElementById("systemStatusMessage");

  let toastTimer = null;
  let evidenceReturnFocus = evidenceToggle;
  let previewReturnFocus = null;
  let evidenceResizePointerId = null;
  let sourceResizePointerId = null;
  let chatProcessTimerId = null;
  let chatProcessStartedAt = 0;
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
    chatContextHint.textContent = contextLabel();
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

  function renderCompareOptions() {
    const currentLeft = compareLeft.value;
    const currentRight = compareRight.value;
    const options = '<option value="">Seçiniz</option>' + state.documents.map(document => (
      `<option value="${Number(document.document_id)}">${escapeHtml(document.title)}</option>`
    )).join("");
    compareLeft.innerHTML = options;
    compareRight.innerHTML = options;
    if (state.documents.some(item => String(item.document_id) === currentLeft)) compareLeft.value = currentLeft;
    if (state.documents.some(item => String(item.document_id) === currentRight)) compareRight.value = currentRight;
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
    renderCompareOptions();
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
    state.chatHistory = [];
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

  function updateChatProcessElapsed() {
    if (!chatProcessStartedAt) return;
    const elapsed = performance.now() - chatProcessStartedAt;
    chatProcessElapsed.textContent = formatChatProcessElapsed(elapsed);
    updateChatProcessStage(elapsed);
  }

  function resetChatProcess() {
    stopChatProcessTimer();
    chatProcessStartedAt = 0;
    chatProcessExpectsRetrieval = true;
    chatProcess.hidden = true;
    chatProcess.dataset.state = "idle";
    chatProcess.style.removeProperty("--process-progress");
  }

  function startChatProcess() {
    stopChatProcessTimer();
    chatProcessStartedAt = performance.now();
    chatProcess.hidden = false;
    chatProcess.dataset.state = "running";
    chatProcessTitle.textContent = "SmartCAE çalışıyor";
    chatProcessElapsed.textContent = "0.0 sn";
    chatProcessExpectsRetrieval = chatAssistantMode.value !== "general";
    setChatProcessStep(chatProcessRequestStep, "done", "Soru gönderildi", "Sunucuya iletildi");
    setChatProcessStep(chatProcessRetrievalStep, "", "Kaynak tarama", "Başlatılıyor");
    setChatProcessStep(chatProcessEvidenceStep, "", "Kanıt seçimi", "Bekliyor");
    setChatProcessStep(chatProcessGenerationStep, "", "Yanıt üretimi", "Bekliyor");
    setChatProcessStep(chatProcessResponseStep, "", "Tamamlandı", "Yanıt bekleniyor");
    const assistantLabel = chatAssistantMode.selectedOptions[0]?.textContent?.trim() || "Otomatik";
    const searchLabel = chatSearchMode.selectedOptions[0]?.textContent?.trim() || "Hibrit";
    const contextLabel = state.selectedDocumentIds.size
      ? `${state.selectedDocumentIds.size} seçili doküman`
      : "Tüm dokümanlar";
    const engineLabel = retrievalVersionLabel(chatRetrievalVersion.value).replaceAll(" · ", " ");
    chatProcessDetail.textContent = `Mod: ${assistantLabel} · Motor: ${engineLabel} · Arama: ${searchLabel} · Kapsam: ${contextLabel}`;
    updateChatProcessElapsed();
    chatProcessTimerId = window.setInterval(updateChatProcessElapsed, 100);
  }

  function finishChatProcess({ sourceCount = 0, confidence = null, retrievalUsed = false, error = "" } = {}) {
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
      return elapsedText;
    }
    chatProcess.dataset.state = "complete";
    chatProcessTitle.textContent = "Yanıt hazır";
    setChatProcessStep(chatProcessRequestStep, "done", "Soru gönderildi", "Sunucuya iletildi");
    if (retrievalUsed) {
      setChatProcessStep(chatProcessRetrievalStep, "done", "Kaynak tarama", sourceCount ? `${sourceCount} kaynak bulundu` : "Kaynak bulunamadı");
      setChatProcessStep(
        chatProcessEvidenceStep,
        sourceCount ? "done" : "skipped",
        "Kanıt seçimi",
        sourceCount && Number.isFinite(Number(confidence)) ? `Güven ${formatScore(confidence)}` : "Kanıt kullanılmadı",
      );
    } else {
      setChatProcessStep(chatProcessRetrievalStep, "skipped", "Kaynak tarama", "Genel yanıtta kullanılmadı");
      setChatProcessStep(chatProcessEvidenceStep, "skipped", "Kanıt seçimi", "Kaynak kullanılmadı");
    }
    setChatProcessStep(chatProcessGenerationStep, "done", "Yanıt üretimi", "Model yanıtı oluşturdu");
    setChatProcessStep(chatProcessResponseStep, "done", "Tamamlandı", `${elapsedText} içinde hazırlandı`);
    setChatProcessProgress(100, "İşlem tamamlandı");
    const engineLabel = retrievalUsed ? retrievalVersionLabel(chatRetrievalVersion.value) : "Genel model";
    const confidenceLabel = Number.isFinite(Number(confidence)) ? ` · güven ${formatScore(confidence)}` : "";
    chatProcessDetail.textContent = `${engineLabel} · ${sourceCount} kaynak${confidenceLabel}`;
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
      avatar.textContent = "🤖";
      article.append(avatar, copy);
    }
    chatMessages.appendChild(article);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function renderEvidence(items, intro = "") {
    closeDocumentPreview();
    state.evidence = Array.isArray(items) ? items : [];
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
            </div>
          ` : ""}
          ${visibleFacts ? `<div class="evidence-facts">${visibleFacts}</div>` : ""}
          ${isReviewEvidence
            ? `<div class="review-evidence-proof"><span>Sayfa kanıtı</span><p>${escapeHtml(clampText(excerpt, 420))}</p></div>`
            : (tableHtml || `<p class="evidence-excerpt">${escapeHtml(clampText(excerpt, 420))}</p>`)}
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
  }

  async function sendChatMessage(message) {
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
          document_ids: [...state.selectedDocumentIds].slice(0, 8),
        }),
      });
      const data = await readJson(response);
      if (!response.ok) throw new Error(requestError(data, "Asistan yanıt oluşturamadı."));
      const engine = data.retrieval_used
        ? `${retrievalVersionLabel(data.retrieval_version)} · ${formatScore(data.confidence)}`
        : "Genel yanıt";
      appendMessage("assistant", data.answer || "Yanıt bulunamadı.", engine);
      state.chatHistory = Array.isArray(data.history)
        ? data.history.slice(-10)
        : [...state.chatHistory, { role: "assistant", content: data.answer || "" }].slice(-10);
      const sources = Array.isArray(data.sources) ? data.sources : [];
      renderEvidence(sources, sources.length
        ? `${sources.length} kaynak · güven ${formatScore(data.confidence)}`
        : "Bu yanıt için doküman kaynağı kullanılmadı.");
      if (sources.length) setEvidenceOpen(true);
      finishChatProcess({
        sourceCount: sources.length,
        confidence: data.confidence,
        retrievalUsed: Boolean(data.retrieval_used),
      });
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
    [...(data.similarities || []), ...(data.differences || [])].slice(0, 12).forEach(item => {
      if (item.left) result.push({ ...item.left, summary: item.summary });
      if (item.right) result.push({ ...item.right, summary: item.summary });
    });
    return result;
  }

  function renderComparison(data) {
    comparisonSummary.hidden = false;
    comparisonSummary.innerHTML = `
      <div><span>Benzerlik</span><strong>${Number(data.similarity_count || 0)}</strong></div>
      <div><span>Fark</span><strong>${Number(data.difference_count || 0)}</strong></div>
      <div><span>Kapsam</span><strong>${formatScore(data.coverage)}</strong></div>
      <div><span>Üretim</span><strong>${escapeHtml(data.generation_provider || "—")}</strong></div>
    `;
    const items = [
      ...(data.similarities || []).map(item => ({ ...item, displayKind: "Benzerlik" })),
      ...(data.differences || []).map(item => ({ ...item, displayKind: "Fark" })),
    ];
    if (!items.length) {
      comparisonResults.innerHTML = '<p class="empty-state">Karşılaştırılabilir pasaj bulunamadı.</p>';
    } else {
      comparisonResults.innerHTML = items.map(item => `
        <article class="comparison-card">
          <div class="comparison-card-head"><h3>${escapeHtml(item.topic || "Teknik bulgu")}</h3><span class="comparison-kind">${item.displayKind}</span></div>
          <p>${escapeHtml(item.summary || "")}</p>
          <div class="result-meta">Güven ${formatScore(item.confidence)} · ${escapeHtml(item.left?.document_title || "Doküman A")} ↔ ${escapeHtml(item.right?.document_title || "Doküman B")}</div>
        </article>
      `).join("");
    }
    if (data.comparison_id) {
      const viewer = document.createElement("a");
      viewer.className = "primary-button";
      viewer.href = `/report-comparison/${encodeURIComponent(data.comparison_id)}/viewer`;
      viewer.target = "_blank";
      viewer.rel = "noopener noreferrer";
      viewer.textContent = "Renkli PDF görünümünü aç";
      comparisonResults.prepend(viewer);
    }
    const evidence = comparisonEvidenceItems(data);
    renderEvidence(evidence, `${data.left?.title || "Doküman A"} ve ${data.right?.title || "Doküman B"} kaynakları.`);
    if (evidence.length) setEvidenceOpen(true);
  }

  async function runComparison() {
    const leftId = Number(compareLeft.value);
    const rightId = Number(compareRight.value);
    if (!leftId || !rightId) {
      compareStatus.textContent = "İki dokümanı da seçmelisin.";
      return;
    }
    if (leftId === rightId) {
      compareStatus.textContent = "Aynı doküman kendiyle karşılaştırılamaz.";
      return;
    }
    const submitButton = compareForm.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    compareStatus.textContent = "Dokümanlar karşılaştırılıyor…";
    comparisonSummary.hidden = true;
    comparisonResults.innerHTML = '<p class="empty-state">Karşılaştırma hazırlanıyor.</p>';
    try {
      const response = await fetch("/report-comparison", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          left: { document_id: leftId },
          right: { document_id: rightId },
          use_llm: true,
        }),
      });
      const data = await readJson(response);
      if (!response.ok) throw new Error(requestError(data, "Karşılaştırma tamamlanamadı."));
      renderComparison(data);
      compareStatus.textContent = `${Number(data.similarity_count || 0)} benzerlik ve ${Number(data.difference_count || 0)} fark bulundu.`;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Karşılaştırma tamamlanamadı.";
      compareStatus.textContent = message;
      comparisonResults.innerHTML = `<p class="empty-state">${escapeHtml(message)}</p>`;
    } finally {
      submitButton.disabled = false;
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

  function applySystemStatus(data) {
    const embedding = data.embedding || {};
    const ollama = data.ollama || {};
    const ready = Boolean(embedding.ready) && (!ollama.configured || Boolean(ollama.model_available));
    systemStatusDot.className = `status-dot ${ready ? "ready" : (embedding.state === "error" || ollama.state === "error" ? "error" : "checking")}`;
    systemStatusLabel.textContent = ready ? "Sistem hazır" : "Sistem uyarısı";
    embeddingStatus.textContent = embedding.ready ? "Hazır" : (embedding.fallback_active ? "Yedek mod" : "Kontrol gerekli");
    embeddingModel.textContent = embedding.active_model || embedding.configured_model || "—";
    embeddingDevice.textContent = String(embedding.device || "—").toUpperCase();
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
  chatInput.addEventListener("input", resizeChatInput);

  chatSuggestions.querySelectorAll("[data-prompt]").forEach(button => {
    button.addEventListener("click", () => {
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
      chatInput.value = prompt;
      if (button.dataset.assistantMode) chatAssistantMode.value = button.dataset.assistantMode;
      chatInput.focus();
      const tokenStart = selectToken ? prompt.indexOf(selectToken) : -1;
      if (tokenStart >= 0) chatInput.setSelectionRange(tokenStart, tokenStart + selectToken.length);
      else chatInput.setSelectionRange(prompt.length, prompt.length);
      setChatStatus("Örnek soru hazır. Metni düzenleyip gönderebilirsin.");
    });
  });

  searchForm.addEventListener("submit", event => {
    event.preventDefault();
    runSearch();
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
  window.setTimeout(loadSystemStatus, 300);
})();
