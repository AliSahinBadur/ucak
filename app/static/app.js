const picker = document.getElementById("reportPicker");
const uploadButton = document.getElementById("uploadButton");
const summary = document.getElementById("summary");
const filesList = document.getElementById("filesList");
const statusBox = document.getElementById("statusBox");
const uploadResults = document.getElementById("uploadResults");
const uploadResultList = document.getElementById("uploadResultList");
const uploadedDocumentsRefreshButton = document.getElementById("uploadedDocumentsRefreshButton");
const uploadedDocumentsStatus = document.getElementById("uploadedDocumentsStatus");
const uploadedDocumentsTable = document.getElementById("uploadedDocumentsTable");
const catalogPicker = document.getElementById("catalogPicker");
const catalogImportButton = document.getElementById("catalogImportButton");
const catalogSummary = document.getElementById("catalogSummary");
const catalogStatusBox = document.getElementById("catalogStatusBox");
const catalogResultBox = document.getElementById("catalogResultBox");
const catalogLogSummary = document.getElementById("catalogLogSummary");
const catalogTableRefreshButton = document.getElementById("catalogTableRefreshButton");
const catalogSelectedIngestButton = document.getElementById("catalogSelectedIngestButton");
const catalogEmbeddingRebuildButton = document.getElementById("catalogEmbeddingRebuildButton");
const catalogIngestedCount = document.getElementById("catalogIngestedCount");
const catalogPendingCount = document.getElementById("catalogPendingCount");
const catalogIngestedTable = document.getElementById("catalogIngestedTable");
const catalogPendingTable = document.getElementById("catalogPendingTable");
const catalogQuestion = document.getElementById("catalogQuestion");
const catalogAskButton = document.getElementById("catalogAskButton");
const catalogAskMeta = document.getElementById("catalogAskMeta");
const catalogAnswer = document.getElementById("catalogAnswer");
const catalogMatches = document.getElementById("catalogMatches");
const catalogMatchCount = document.getElementById("catalogMatchCount");
const catalogDocumentCount = document.getElementById("catalogDocumentCount");
const catalogScopeReady = document.getElementById("catalogScopeReady");
const multiDocumentQuestion = document.getElementById("multiDocumentQuestion");
const multiDocumentMode = document.getElementById("multiDocumentMode");
const multiDocumentLimit = document.getElementById("multiDocumentLimit");
const multiDocumentAskButton = document.getElementById("multiDocumentAskButton");
const multiDocumentMeta = document.getElementById("multiDocumentMeta");
const multiDocumentAnswer = document.getElementById("multiDocumentAnswer");
const multiDocumentDocuments = document.getElementById("multiDocumentDocuments");
const multiDocumentComparison = document.getElementById("multiDocumentComparison");
const multiDocumentSources = document.getElementById("multiDocumentSources");
const graphRefreshButton = document.getElementById("graphRefreshButton");
const graphStatus = document.getElementById("graphStatus");
const graphStats = document.getElementById("graphStats");
const graphTree = document.getElementById("graphTree");
const graphSearchInput = document.getElementById("graphSearchInput");
const graphCategoryFilter = document.getElementById("graphCategoryFilter");
const graphDensityChart = document.getElementById("graphDensityChart");
const graphDocumentsTable = document.getElementById("graphDocumentsTable");
const searchQuery = document.getElementById("searchQuery");
const searchMode = document.getElementById("searchMode");
const searchButton = document.getElementById("searchButton");
const searchMeta = document.getElementById("searchMeta");
const searchResultsLayout = document.getElementById("searchResultsLayout");
const resultsList = document.getElementById("resultsList");
const similarList = document.getElementById("similarList");
const duplicateScanButton = document.getElementById("duplicateScanButton");
const duplicateRefreshButton = document.getElementById("duplicateRefreshButton");
const duplicateStatus = document.getElementById("duplicateStatus");
const duplicateList = document.getElementById("duplicateList");
const duplicateCandidatesTab = document.getElementById("duplicateCandidatesTab");
const reportComparisonTab = document.getElementById("reportComparisonTab");
const duplicateCandidatesPane = document.getElementById("duplicateCandidatesPane");
const reportComparisonPane = document.getElementById("reportComparisonPane");
const comparisonLeftSelect = document.getElementById("comparisonLeftSelect");
const comparisonRightSelect = document.getElementById("comparisonRightSelect");
const comparisonLeftUpload = document.getElementById("comparisonLeftUpload");
const comparisonRightUpload = document.getElementById("comparisonRightUpload");
const comparisonLeftMeta = document.getElementById("comparisonLeftMeta");
const comparisonRightMeta = document.getElementById("comparisonRightMeta");
const comparisonPersistUploads = document.getElementById("comparisonPersistUploads");
const comparisonSwapButton = document.getElementById("comparisonSwapButton");
const comparisonRunButton = document.getElementById("comparisonRunButton");
const comparisonStatus = document.getElementById("comparisonStatus");
const comparisonOutput = document.getElementById("comparisonOutput");
const comparisonSummary = document.getElementById("comparisonSummary");
const comparisonSimilaritiesTab = document.getElementById("comparisonSimilaritiesTab");
const comparisonDifferencesTab = document.getElementById("comparisonDifferencesTab");
const comparisonSimilaritiesPane = document.getElementById("comparisonSimilaritiesPane");
const comparisonDifferencesPane = document.getElementById("comparisonDifferencesPane");
const comparisonSimilarities = document.getElementById("comparisonSimilarities");
const comparisonDifferences = document.getElementById("comparisonDifferences");
const comparisonPdfWorkspace = document.getElementById("comparisonPdfWorkspace");
const comparisonPdfStatus = document.getElementById("comparisonPdfStatus");
const comparisonHighlightLegend = document.getElementById("comparisonHighlightLegend");
const comparisonPairFullscreenOpen = document.getElementById("comparisonPairFullscreenOpen");
const comparisonLeftPdfTitle = document.getElementById("comparisonLeftPdfTitle");
const comparisonRightPdfTitle = document.getElementById("comparisonRightPdfTitle");
const comparisonLeftPdfOpen = document.getElementById("comparisonLeftPdfOpen");
const comparisonRightPdfOpen = document.getElementById("comparisonRightPdfOpen");
const comparisonLeftPdfFrame = document.getElementById("comparisonLeftPdfFrame");
const comparisonRightPdfFrame = document.getElementById("comparisonRightPdfFrame");
const comparisonLeftPdfPlaceholder = document.getElementById("comparisonLeftPdfPlaceholder");
const comparisonRightPdfPlaceholder = document.getElementById("comparisonRightPdfPlaceholder");
const chatMessages = document.getElementById("chatMessages");
const chatInput = document.getElementById("chatInput");
const chatAssistantMode = document.getElementById("chatAssistantMode");
const chatRetrievalVersion = document.getElementById("chatRetrievalVersion");
const chatMode = document.getElementById("chatMode");
const chatSendButton = document.getElementById("chatSendButton");
const chatClearButton = document.getElementById("chatClearButton");
const chatStatus = document.getElementById("chatStatus");
const chatSources = document.getElementById("chatSources");
const chatSourceMeta = document.getElementById("chatSourceMeta");
const chatPromptButtons = Array.from(document.querySelectorAll("[data-chat-prompt]"));
const askQuestion = document.getElementById("askQuestion");
const askMode = document.getElementById("askMode");
const askDocumentId = document.getElementById("askDocumentId");
const askButton = document.getElementById("askButton");
const askMeta = document.getElementById("askMeta");
const answerText = document.getElementById("answerText");
const answerSources = document.getElementById("answerSources");
const draftTitle = document.getElementById("draftTitle");
const draftType = document.getElementById("draftType");
const draftMode = document.getElementById("draftMode");
const draftReportNo = document.getElementById("draftReportNo");
const draftReportDate = document.getElementById("draftReportDate");
const draftPreparedBy = document.getElementById("draftPreparedBy");
const draftRequestedBy = document.getElementById("draftRequestedBy");
const draftCheckedBy = document.getElementById("draftCheckedBy");
const draftObjective = document.getElementById("draftObjective");
const draftKeywords = document.getElementById("draftKeywords");
const draftNotes = document.getElementById("draftNotes");
const draftQuickButton = document.getElementById("draftQuickButton");
const draftDetailedButton = document.getElementById("draftDetailedButton");
const draftSampleButton = document.getElementById("draftSampleButton");
const draftClearButton = document.getElementById("draftClearButton");
const draftCopyButton = document.getElementById("draftCopyButton");
const draftPdfButton = document.getElementById("draftPdfButton");
const draftMeta = document.getElementById("draftMeta");
const draftOutput = document.getElementById("draftOutput");
const draftSources = document.getElementById("draftSources");
const moduleModal = document.getElementById("moduleModal");
const moduleModalTitle = document.getElementById("moduleModalTitle");
const moduleModalBody = document.getElementById("moduleModalBody");
const moduleModalClose = document.getElementById("moduleModalClose");
const moduleFilterButtons = Array.from(document.querySelectorAll("[data-module-filter]"));
const moduleSections = Array.from(document.querySelectorAll(".section[data-module-key]"));

let selectedFiles = [];
let selectedCatalogFile = null;
let lastCatalogQuestion = "";
let lastCatalogMatches = [];
let chatHistory = [];
let chatContextDocumentIds = [];
let lastDraftPayload = null;
let lastDraftData = null;
let lastAutoReportNo = "";
let selectedDraftDocumentIds = [];
let graphState = { categories: [], documents: [], selectedCategoryId: "all", search: "" };
let activeTimerId = null;
let activeModule = null;
let selectedModuleFilter = "upload";
let duplicateWorkspaceView = "candidates";
let comparisonDocumentsLoaded = false;
let latestComparisonData = null;

function applyModuleFilter(filterKey) {
  selectedModuleFilter = filterKey || "upload";
  if (activeModule) {
    closeModule();
  }

  moduleFilterButtons.forEach(button => {
    button.classList.toggle("active", button.dataset.moduleFilter === selectedModuleFilter);
  });
  document.body.classList.toggle("chat-focus", selectedModuleFilter === "chat");

  moduleSections.forEach(section => {
    const keys = String(section.dataset.moduleKey || "").split(/\\s+/);
    const shouldShow = selectedModuleFilter === "all" || keys.includes(selectedModuleFilter);
    section.classList.toggle("module-hidden", !shouldShow);
  });

  if (selectedModuleFilter === "graph") {
    refreshGraph();
  }
  if (selectedModuleFilter === "duplicates") {
    if (duplicateWorkspaceView === "comparison") {
      refreshComparisonDocuments();
    } else {
      refreshDuplicates();
    }
  }
}

function formatElapsed(milliseconds) {
  const seconds = milliseconds / 1000;
  return seconds < 10 ? `${seconds.toFixed(2)} sn` : `${seconds.toFixed(1)} sn`;
}

function startTimer(setMessage, baseMessage) {
  const startedAt = performance.now();
  if (activeTimerId) {
    clearInterval(activeTimerId);
  }
  const update = () => {
    setMessage(`${baseMessage} | Sure: ${formatElapsed(performance.now() - startedAt)}`);
  };
  update();
  activeTimerId = setInterval(update, 200);
  return startedAt;
}

function stopTimer(startedAt, setMessage, finalMessage) {
  if (activeTimerId) {
    clearInterval(activeTimerId);
    activeTimerId = null;
  }
  setMessage(`${finalMessage} | Sure: ${formatElapsed(performance.now() - startedAt)}`);
}

function formatTodayForDraft() {
  const today = new Date();
  const day = String(today.getDate()).padStart(2, "0");
  const month = String(today.getMonth() + 1).padStart(2, "0");
  return `${day}.${month}.${today.getFullYear()}`;
}

function guessDraftReportNo(title) {
  const match = String(title || "").match(/\\b20\\d{2}[-_][0-9A-Za-z.]+(?:[-_][0-9A-Za-z.]+){1,}\\b/);
  return match ? match[0] : "TASLAK";
}

function updateDraftReportNoAuto(force = false) {
  const current = draftReportNo.value.trim();
  const guessed = guessDraftReportNo(draftTitle.value);
  if (force || !current || current === "TASLAK" || current === lastAutoReportNo) {
    draftReportNo.value = guessed;
    lastAutoReportNo = guessed;
  }
}

function ensureDraftDefaults() {
  if (!draftReportDate.value.trim()) {
    draftReportDate.value = formatTodayForDraft();
  }
  updateDraftReportNoAuto(false);
}

function openModule(section) {
  closeModule();
  activeModule = section;
  section.classList.add("module-expanded");
  const expandButton = section.querySelector("[data-expand-module]");
  if (expandButton) {
    expandButton.textContent = "Kucult";
  }
  document.body.classList.add("modal-open");
  if (section.dataset.moduleKey === "upload") {
    refreshUploadedDocuments();
  }
  if (section.dataset.moduleKey === "graph") {
    refreshGraph();
  }
  if (section.dataset.moduleKey === "duplicates") {
    if (duplicateWorkspaceView === "comparison") {
      refreshComparisonDocuments();
    } else {
      refreshDuplicates();
    }
  }
}

function closeModule() {
  if (!activeModule) {
    return;
  }
  activeModule.classList.remove("module-expanded");
  const expandButton = activeModule.querySelector("[data-expand-module]");
  if (expandButton) {
    expandButton.textContent = "Buyut";
  }
  activeModule = null;
  document.body.classList.remove("modal-open");
}

function renderFiles() {
  filesList.innerHTML = "";
  if (selectedFiles.length === 0) {
    filesList.innerHTML = "<li>Dosya listesi burada gorunecek.</li>";
    summary.textContent = "Henuz rapor secilmedi.";
    return;
  }

  const supported = selectedFiles.filter(file => {
    const lower = file.name.toLowerCase();
    return lower.endsWith(".pdf") || lower.endsWith(".docx") || lower.endsWith(".pptx");
  });

  summary.textContent = supported.length === 1
    ? "1 rapor secildi."
    : `${supported.length} rapor secildi.`;
  supported.slice(0, 12).forEach(file => {
    const item = document.createElement("li");
    item.textContent = file.webkitRelativePath || file.name;
    filesList.appendChild(item);
  });
  if (supported.length > 12) {
    const more = document.createElement("li");
    more.textContent = `... ve ${supported.length - 12} dosya daha`;
    filesList.appendChild(more);
  }
}

function renderUploadResults(items) {
  uploadResultList.innerHTML = "";
  if (!items || items.length === 0) {
    uploadResults.hidden = true;
    return;
  }
  items.forEach(result => {
    const item = document.createElement("li");
    const statusLabels = {
      ingested: "Yeni eklendi",
      duplicate: "Zaten mevcut",
      error: "Hata",
    };
    const details = [];
    if (result.pages) details.push(`${result.pages} sayfa`);
    if (result.chunks) details.push(`${result.chunks} parca`);
    if (result.embeddings_created) details.push(`${result.embeddings_created} embedding`);
    if (result.error) details.push(result.error);
    const detailText = details.length ? ` | ${details.join(" | ")}` : "";
    item.textContent = `${result.file_name}: ${statusLabels[result.status] || result.status}${detailText}`;
    uploadResultList.appendChild(item);
  });
  uploadResults.hidden = false;
}

function renderUploadedDocuments(items) {
  if (!items || items.length === 0) {
    uploadedDocumentsTable.innerHTML = '<tr><td colspan="6" class="small">Iceride yuklenmis rapor bulunamadi.</td></tr>';
    return;
  }

  uploadedDocumentsTable.innerHTML = items.map(item => `
    <tr onclick="openDocumentFile(${item.document_id})" style="cursor:pointer;">
      <td>${item.document_id}</td>
      <td>
        <div class="title">${escapeHtml(item.title)}</div>
        <div class="small">${escapeHtml(item.file_name)}</div>
      </td>
      <td>${escapeHtml(item.file_type)}</td>
      <td>${item.chunk_count}</td>
      <td>${item.embedding_count}</td>
      <td>${escapeHtml(item.created_at || "")}</td>
    </tr>
  `).join("");
}

async function refreshUploadedDocuments() {
  uploadedDocumentsRefreshButton.disabled = true;
  uploadedDocumentsStatus.textContent = "Icerideki raporlar yukleniyor...";
  try {
    const response = await fetch("/documents/list?limit=300");
    const data = await response.json();
    if (!response.ok) {
      uploadedDocumentsStatus.textContent = data.detail || "Rapor listesi alinamadi.";
      return;
    }
    renderUploadedDocuments(data.items || []);
    uploadedDocumentsStatus.textContent = `Icerideki rapor: ${data.total}. Gosterilen: ${(data.items || []).length}.`;
  } catch (error) {
    uploadedDocumentsStatus.textContent = `Rapor listesi alinamadi: ${error}`;
  } finally {
    uploadedDocumentsRefreshButton.disabled = false;
  }
}

function setStatus(kind, message) {
  statusBox.className = `status show ${kind}`;
  statusBox.textContent = message;
}

function setCatalogStatus(kind, message) {
  catalogStatusBox.className = `status show ${kind}`;
  catalogStatusBox.textContent = message;
}

function setCatalogLog(data) {
  catalogResultBox.textContent = JSON.stringify(data, null, 2);
  if (data.total_seen !== undefined) {
    catalogLogSummary.textContent = `Teknik log | toplam ${data.total_seen} | ingested ${data.ingested_count} | pending ${data.pending_count}`;
    return;
  }
  if (data.created_count !== undefined) {
    catalogLogSummary.textContent = `Teknik log | yeni ${data.created_count} | guncellenen ${data.updated_count || 0} | duplicate ${data.duplicate_count} | hata ${data.error_count}`;
    return;
  }
  if (data.ingested_count !== undefined) {
    catalogLogSummary.textContent = `Teknik log | ingested ${data.ingested_count} | duplicate ${data.duplicate_count} | hata ${data.error_count}`;
    return;
  }
  if (data.chunks_seen !== undefined) {
    catalogLogSummary.textContent = `Teknik log | chunk ${data.chunks_seen} | embedding ${data.embeddings_created}`;
    return;
  }
  catalogLogSummary.textContent = "Teknik log";
}

function catalogIngestResultMessage(data) {
  const base = `Ice alma tamamlandi. Yeni: ${data.ingested_count}, duplicate: ${data.duplicate_count}, hata: ${data.error_count}.`;
  const failedItems = (data.items || []).filter(item => item.status === "error");
  if (failedItems.length === 0) {
    return base;
  }

  const firstError = failedItems[0];
  const report = firstError.report_code || firstError.source_path || `ID ${firstError.catalog_entry_id}`;
  return `${base} Ilk hata: ${report} -> ${firstError.error || "detay yok"}`;
}

function formatScore(value) {
  if (typeof value !== "number") return "0.000";
  return value.toFixed(3);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function tokenizeHighlightTerms(query) {
  return String(query || "")
    .split(/\\s+/)
    .map(term => term.trim())
    .filter(term => term.length >= 2);
}

function normalizeSearchText(value) {
  return String(value || "")
    .toLocaleLowerCase("tr-TR")
    .replaceAll("ı", "i")
    .replaceAll("ğ", "g")
    .replaceAll("ü", "u")
    .replaceAll("ş", "s")
    .replaceAll("ö", "o")
    .replaceAll("ç", "c")
    .normalize("NFD")
    .replace(/[\\u0300-\\u036f]/g, "");
}

function editDistance(left, right) {
  if (Math.abs(left.length - right.length) > 1) {
    return 2;
  }
  const previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let leftIndex = 1; leftIndex <= left.length; leftIndex += 1) {
    const current = [leftIndex];
    for (let rightIndex = 1; rightIndex <= right.length; rightIndex += 1) {
      const insertCost = current[rightIndex - 1] + 1;
      const deleteCost = previous[rightIndex] + 1;
      const replaceCost = previous[rightIndex - 1] + (left[leftIndex - 1] === right[rightIndex - 1] ? 0 : 1);
      current.push(Math.min(insertCost, deleteCost, replaceCost));
    }
    previous.splice(0, previous.length, ...current);
  }
  return previous[right.length];
}

function isHighlightMatch(word, terms) {
  const normalizedWord = normalizeSearchText(word);
  return terms.some(term => {
    const normalizedTerm = normalizeSearchText(term);
    if (!normalizedTerm) {
      return false;
    }
    if (normalizedWord.includes(normalizedTerm) || normalizedTerm.includes(normalizedWord)) {
      return true;
    }
    if (normalizedTerm.length < 5 || normalizedWord.length < 5 || normalizedTerm[0] !== normalizedWord[0]) {
      return false;
    }
    const maxDistance = Math.min(normalizedTerm.length, normalizedWord.length) >= 6 ? 2 : 1;
    return editDistance(normalizedTerm, normalizedWord) <= maxDistance;
  });
}

function highlightText(value, query) {
  const terms = tokenizeHighlightTerms(query).sort((a, b) => b.length - a.length);
  if (terms.length === 0) {
    return escapeHtml(value);
  }

  return String(value ?? "")
    .split(/([\\p{L}\\p{N}_]+)/gu)
    .map(part => isHighlightMatch(part, terms) ? `<mark>${escapeHtml(part)}</mark>` : escapeHtml(part))
    .join("");
}

function renderResults(items, query) {
  if (!items || items.length === 0) {
    resultsList.innerHTML = '<div class="empty">Sonuc bulunamadi.</div>';
    return;
  }

  resultsList.innerHTML = items.map(item => `
    <article class="result-card" onclick="openDocumentFile(${item.document_id})" style="cursor:pointer;">
      <div class="result-head">
        <div>
          <div class="title">${highlightText(item.document_title, query)}</div>
          <div class="small">Belge ID: ${item.document_id} | Sayfa ${item.page_start}-${item.page_end}${item.section_title ? " | " + highlightText(item.section_title, query) : ""}</div>
        </div>
        <span class="tag">${escapeHtml(item.match_type)}</span>
      </div>
      <div class="small">keyword: ${formatScore(item.keyword_score)} | semantic: ${formatScore(item.semantic_score)} | combined: ${formatScore(item.combined_score)}</div>
      <div class="excerpt">${highlightText(item.chunk_text, query)}</div>
    </article>
  `).join("");
}

function renderSimilar(items, query) {
  if (!items || items.length === 0) {
    similarList.innerHTML = '<div class="empty">Benzer rapor bulunamadi.</div>';
    return;
  }

  similarList.innerHTML = items.map(item => `
    <article class="similar-card" onclick="openDocumentFile(${item.document_id})" style="cursor:pointer;">
      <div class="similar-head">
        <div>
          <div class="title">${highlightText(item.document_title, query)}</div>
          <div class="small">Belge ID: ${item.document_id} | ${highlightText(item.file_name, query)}</div>
        </div>
        <span class="tag">score ${formatScore(item.score)}</span>
      </div>
      <div class="small">matched chunks: <span class="count">${item.matched_chunks}</span>${item.top_page_start ? ` | sayfa ${item.top_page_start}-${item.top_page_end}` : ""}</div>
      <div class="excerpt">${highlightText(item.top_excerpt, query)}</div>
    </article>
  `).join("");
}

function renderDuplicatePairs(items) {
  if (!items || items.length === 0) {
    duplicateList.innerHTML = '<div class="empty">Kayitli mukerrer adayi bulunamadi. Once taramayi baslat.</div>';
    return;
  }

  duplicateList.innerHTML = items.map(item => `
    <article class="similar-card">
      <div class="similar-head">
        <div>
          <div class="title">Benzerlik: ${formatScore(item.similarity_score)}</div>
          <div class="small">Sebep: ${escapeHtml(item.reason)} | Baslik: ${formatScore(item.title_score)} | Embedding: ${formatScore(item.embedding_score)}</div>
        </div>
        <span class="tag">${escapeHtml(item.status || "candidate")}</span>
      </div>
      <div class="split" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:12px;">
        <div class="source-card" onclick="openDocumentFile(${item.document_id_a})" style="cursor:pointer;">
          <div class="title">${escapeHtml(item.document_title_a)}</div>
          <div class="small">Belge ID: ${item.document_id_a} | ${escapeHtml(item.file_name_a)}</div>
        </div>
        <div class="source-card" onclick="openDocumentFile(${item.document_id_b})" style="cursor:pointer;">
          <div class="title">${escapeHtml(item.document_title_b)}</div>
          <div class="small">Belge ID: ${item.document_id_b} | ${escapeHtml(item.file_name_b)}</div>
        </div>
      </div>
    </article>
  `).join("");
}

async function refreshDuplicates() {
  duplicateRefreshButton.disabled = true;
  duplicateStatus.textContent = "Kayitli mukerrer adaylari yukleniyor...";
  try {
    const response = await fetch("/duplicates?limit=100");
    const data = await response.json();
    if (!response.ok) {
      duplicateStatus.textContent = data.detail || "Mukerrer adaylari alinamadi.";
      return;
    }
    renderDuplicatePairs(data.items || []);
    duplicateStatus.textContent = `Kayitli mukerrer adayi: ${data.total}.`;
  } catch (error) {
    duplicateStatus.textContent = `Mukerrer adaylari alinamadi: ${error}`;
  } finally {
    duplicateRefreshButton.disabled = false;
  }
}

async function runDuplicateScan() {
  duplicateScanButton.disabled = true;
  duplicateRefreshButton.disabled = true;
  const startedAt = startTimer(
    message => { duplicateStatus.textContent = message; },
    "Mukerrer taramasi calisiyor..."
  );
  try {
    const response = await fetch("/duplicates/scan?threshold=0.90&dry_run=false", {
      method: "POST",
    });
    const data = await response.json();
    if (!response.ok) {
      stopTimer(startedAt, message => { duplicateStatus.textContent = message; }, data.detail || "Mukerrer taramasi basarisiz oldu.");
      return;
    }
    stopTimer(
      startedAt,
      message => { duplicateStatus.textContent = message; },
      `Tarama tamamlandi. Dokuman: ${data.documents_seen}, aday: ${data.candidate_count}, yeni: ${data.created_count}, guncellenen: ${data.updated_count}.`
    );
    await refreshDuplicates();
  } catch (error) {
    stopTimer(startedAt, message => { duplicateStatus.textContent = message; }, `Mukerrer taramasi basarisiz oldu: ${error}`);
  } finally {
    duplicateScanButton.disabled = false;
    duplicateRefreshButton.disabled = false;
  }
}

function setDuplicateWorkspace(view) {
  duplicateWorkspaceView = view === "comparison" ? "comparison" : "candidates";
  const comparisonActive = duplicateWorkspaceView === "comparison";
  duplicateCandidatesTab.classList.toggle("active", !comparisonActive);
  reportComparisonTab.classList.toggle("active", comparisonActive);
  duplicateCandidatesTab.setAttribute("aria-selected", String(!comparisonActive));
  reportComparisonTab.setAttribute("aria-selected", String(comparisonActive));
  duplicateCandidatesPane.hidden = comparisonActive;
  reportComparisonPane.hidden = !comparisonActive;
  if (comparisonActive) {
    refreshComparisonDocuments();
  } else {
    refreshDuplicates();
  }
}

function temporaryOptionSnapshot(select) {
  const option = select.selectedOptions[0];
  if (!option || !option.value.startsWith("temp:")) {
    return null;
  }
  return { value: option.value, text: option.textContent };
}

function fillComparisonSelect(select, items, preserved) {
  const previousValue = select.value;
  select.innerHTML = '<option value="">Rapor sec...</option>';
  items.forEach(item => {
    const option = document.createElement("option");
    option.value = `doc:${item.document_id}`;
    option.textContent = `${item.title} | ${item.file_name}`;
    select.appendChild(option);
  });
  if (preserved && !Array.from(select.options).some(option => option.value === preserved.value)) {
    const option = document.createElement("option");
    option.value = preserved.value;
    option.textContent = preserved.text;
    option.dataset.temporary = "true";
    select.appendChild(option);
  }
  if (Array.from(select.options).some(option => option.value === previousValue)) {
    select.value = previousValue;
  } else if (preserved) {
    select.value = preserved.value;
  }
}

async function refreshComparisonDocuments(force = false) {
  if (comparisonDocumentsLoaded && !force) {
    return;
  }
  const leftTemporary = temporaryOptionSnapshot(comparisonLeftSelect);
  const rightTemporary = temporaryOptionSnapshot(comparisonRightSelect);
  try {
    const response = await fetch("/documents/list?limit=500");
    const data = await response.json();
    if (!response.ok) {
      comparisonStatus.textContent = data.detail || "Rapor listesi alinamadi.";
      return;
    }
    fillComparisonSelect(comparisonLeftSelect, data.items || [], leftTemporary);
    fillComparisonSelect(comparisonRightSelect, data.items || [], rightTemporary);
    comparisonDocumentsLoaded = true;
  } catch (error) {
    comparisonStatus.textContent = `Rapor listesi alinamadi: ${error}`;
  }
}

function setTemporaryComparisonSelection(select, data) {
  const value = `temp:${data.upload_token}`;
  let option = Array.from(select.options).find(item => item.value === value);
  if (!option) {
    option = document.createElement("option");
    option.value = value;
    option.dataset.temporary = "true";
    select.appendChild(option);
  }
  option.textContent = `${data.title} | gecici yukleme`;
  select.value = value;
}

function updateComparisonSourceMeta(select, meta) {
  const option = select.selectedOptions[0];
  if (!option || !option.value) {
    meta.textContent = "Kaynak secilmedi.";
    return;
  }
  meta.textContent = option.value.startsWith("temp:")
    ? "Gecici rapor, havuza eklenmedi."
    : "Rapor havuzundan secildi.";
}

async function uploadComparisonSource(side, input) {
  const file = input.files && input.files[0];
  if (!file) {
    return;
  }
  const select = side === "left" ? comparisonLeftSelect : comparisonRightSelect;
  const meta = side === "left" ? comparisonLeftMeta : comparisonRightMeta;
  comparisonRunButton.disabled = true;
  input.disabled = true;
  const persist = comparisonPersistUploads.checked;
  const startedAt = startTimer(
    message => { comparisonStatus.textContent = message; },
    persist ? "Rapor havuza ekleniyor..." : "Gecici rapor yukleniyor..."
  );
  try {
    const formData = new FormData();
    formData.append("file", file);
    const endpoint = persist ? "/ingest" : "/report-comparison/upload";
    const response = await fetch(endpoint, { method: "POST", body: formData });
    const data = await response.json();
    if (!response.ok) {
      stopTimer(
        startedAt,
        message => { comparisonStatus.textContent = message; },
        data.detail || "Rapor yuklenemedi."
      );
      return;
    }
    if (persist) {
      comparisonDocumentsLoaded = false;
      await refreshComparisonDocuments(true);
      select.value = `doc:${data.document_id}`;
      meta.textContent = "Rapor havuzuna eklendi ve secildi.";
    } else {
      setTemporaryComparisonSelection(select, data);
      meta.textContent = "Gecici rapor yuklendi; rapor havuzuna eklenmedi.";
    }
    stopTimer(
      startedAt,
      message => { comparisonStatus.textContent = message; },
      `${file.name} karsilastirma icin hazir.`
    );
  } catch (error) {
    stopTimer(
      startedAt,
      message => { comparisonStatus.textContent = message; },
      `Rapor yuklenemedi: ${error}`
    );
  } finally {
    input.value = "";
    input.disabled = false;
    comparisonRunButton.disabled = false;
  }
}

function comparisonSourcePayload(value) {
  if (value.startsWith("doc:")) {
    return { document_id: Number(value.slice(4)) };
  }
  if (value.startsWith("temp:")) {
    return { upload_token: value.slice(5) };
  }
  return null;
}

function ensureComparisonOption(target, source, value) {
  if (!value || Array.from(target.options).some(option => option.value === value)) {
    return;
  }
  const sourceOption = Array.from(source.options).find(option => option.value === value);
  if (sourceOption) {
    target.appendChild(sourceOption.cloneNode(true));
  }
}

function swapComparisonSources() {
  const leftValue = comparisonLeftSelect.value;
  const rightValue = comparisonRightSelect.value;
  ensureComparisonOption(comparisonLeftSelect, comparisonRightSelect, rightValue);
  ensureComparisonOption(comparisonRightSelect, comparisonLeftSelect, leftValue);
  comparisonLeftSelect.value = rightValue;
  comparisonRightSelect.value = leftValue;
  updateComparisonSourceMeta(comparisonLeftSelect, comparisonLeftMeta);
  updateComparisonSourceMeta(comparisonRightSelect, comparisonRightMeta);
}

function comparisonTypeLabel(type) {
  const labels = {
    value_change: "Deger degisikligi",
    result_change: "Sonuc degisikligi",
    contradiction: "Celiski",
    content_change: "Icerik farki",
    only_left: "Yalniz Rapor A",
    only_right: "Yalniz Rapor B",
  };
  return labels[type] || "Farklilik";
}

function comparisonHighlightColor(value) {
  const color = String(value || "").trim();
  return /^#[0-9a-fA-F]{6}$/.test(color) ? color : "";
}

function renderComparisonEvidence(source, label) {
  const page = source.page_start
    ? `Sayfa ${source.page_start}${source.page_end && source.page_end !== source.page_start ? "-" + source.page_end : ""}`
    : "Eslesen kaynak yok";
  const section = source.section_title ? ` | ${escapeHtml(source.section_title)}` : "";
  const openButton = Number.isInteger(source.document_id)
    ? `<button class="comparison-open" type="button" onclick="openDocumentFile(${source.document_id})">Raporu Ac</button>`
    : "";
  return `
    <div class="comparison-evidence">
      <div class="comparison-evidence-title">
        <span>${label} | ${escapeHtml(source.document_title)}</span>
        ${openButton}
      </div>
      <div class="small">${page}${section}</div>
      <div class="comparison-evidence-text">${escapeHtml(source.excerpt)}</div>
    </div>
  `;
}

function renderComparisonRows(container, items, emptyMessage) {
  if (!items || items.length === 0) {
    container.innerHTML = `<div class="empty" style="padding:16px 0;">${escapeHtml(emptyMessage)}</div>`;
    return;
  }
  container.innerHTML = items.map(item => {
    const tag = item.kind === "difference"
      ? comparisonTypeLabel(item.difference_type)
      : "Ortak bulgu";
    const confidence = Math.round((Number(item.confidence) || 0) * 100);
    const highlightColor = comparisonHighlightColor(item.highlight_color);
    const highlightNumber = Number(item.highlight_number) || 0;
    const highlighted = Boolean(highlightColor && highlightNumber);
    const highlightActions = highlighted
      ? `
        <span class="comparison-pair-marker" style="--pair-color:${highlightColor}">Eslesme ${highlightNumber}</span>
        <button class="comparison-focus" type="button" data-comparison-focus="${escapeHtml(item.id)}">PDF'de Goster</button>
      `
      : "";
    return `
      <article class="comparison-row${highlighted ? " has-pdf-highlight" : ""}"${highlighted ? ` style="--pair-color:${highlightColor}"` : ""}>
        <div class="comparison-row-head">
          <div>
            <div class="comparison-row-topic">${escapeHtml(item.topic)}</div>
            <div class="comparison-row-summary">${escapeHtml(item.summary)}</div>
          </div>
          <div class="comparison-highlight-actions">
            ${highlightActions}
            <span class="tag">${escapeHtml(tag)} | %${confidence}</span>
          </div>
        </div>
        <div class="comparison-evidence-grid">
          ${renderComparisonEvidence(item.left, "Rapor A")}
          ${renderComparisonEvidence(item.right, "Rapor B")}
        </div>
      </article>
    `;
  }).join("");
}

function setComparisonResultView(view) {
  const showDifferences = view === "differences";
  comparisonSimilaritiesTab.classList.toggle("active", !showDifferences);
  comparisonDifferencesTab.classList.toggle("active", showDifferences);
  comparisonSimilaritiesTab.setAttribute("aria-selected", String(!showDifferences));
  comparisonDifferencesTab.setAttribute("aria-selected", String(showDifferences));
  comparisonSimilaritiesPane.hidden = showDifferences;
  comparisonDifferencesPane.hidden = !showDifferences;
}

function comparisonItems() {
  if (!latestComparisonData) return [];
  return [
    ...(latestComparisonData.similarities || []),
    ...(latestComparisonData.differences || []),
  ];
}

function comparisonPdfPageUrl(url, page) {
  const safePage = Math.max(Number(page) || 1, 1);
  return `${url}#page=${safePage}&zoom=page-width`;
}

function setComparisonPdfSide(side, preview, documentData, page) {
  const leftSide = side === "left";
  const frame = leftSide ? comparisonLeftPdfFrame : comparisonRightPdfFrame;
  const placeholder = leftSide ? comparisonLeftPdfPlaceholder : comparisonRightPdfPlaceholder;
  const title = leftSide ? comparisonLeftPdfTitle : comparisonRightPdfTitle;
  const openButton = leftSide ? comparisonLeftPdfOpen : comparisonRightPdfOpen;
  const label = leftSide ? "Rapor A" : "Rapor B";
  title.textContent = `${label} | ${documentData?.title || documentData?.file_name || "PDF"}`;
  if (preview?.available && preview.url) {
    const targetUrl = comparisonPdfPageUrl(preview.url, page);
    frame.hidden = false;
    placeholder.hidden = true;
    if (frame.getAttribute("src") !== targetUrl) {
      frame.setAttribute("src", targetUrl);
    }
    openButton.disabled = false;
    openButton.dataset.url = targetUrl;
    return;
  }
  frame.hidden = true;
  frame.removeAttribute("src");
  placeholder.hidden = false;
  placeholder.textContent = preview?.reason || "Bu kaynak icin PDF onizlemesi bulunmuyor.";
  openButton.disabled = true;
  delete openButton.dataset.url;
}

function focusComparisonPdf(itemId, scrollToViewer = true) {
  if (!latestComparisonData) return;
  const item = comparisonItems().find(row => row.id === itemId);
  if (!item) return;
  const leftPage = item.left?.highlight_page || item.left?.page_start || 1;
  const rightPage = item.right?.highlight_page || item.right?.page_start || 1;
  setComparisonPdfSide("left", latestComparisonData.left_pdf, latestComparisonData.left, leftPage);
  setComparisonPdfSide("right", latestComparisonData.right_pdf, latestComparisonData.right, rightPage);
  const number = Number(item.highlight_number) || "";
  comparisonPdfStatus.textContent = number
    ? `Eslesme ${number} secildi. PDF'lerin tamami acik; ayni renk eslestirilen pasaj ciftini gosterir.`
    : "PDF'lerin tamami renkli isaretlemelerle acildi.";
  if (scrollToViewer) {
    comparisonPdfWorkspace.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function renderComparisonPdfWorkspace(data) {
  comparisonPdfWorkspace.hidden = false;
  const pairViewerAvailable = Boolean(
    data.comparison_id && data.left_pdf?.available && data.right_pdf?.available
  );
  comparisonPairFullscreenOpen.disabled = !pairViewerAvailable;
  if (pairViewerAvailable) {
    comparisonPairFullscreenOpen.dataset.url =
      `/report-comparison/${encodeURIComponent(data.comparison_id)}/viewer`;
    comparisonPairFullscreenOpen.title = "Renkli iki PDF'yi yeni sekmede yan yana ac";
  } else {
    delete comparisonPairFullscreenOpen.dataset.url;
    comparisonPairFullscreenOpen.title = "Tam ekran icin iki kaynagin da PDF olmasi gerekir";
  }
  const highlightedItems = comparisonItems().filter(
    item => comparisonHighlightColor(item.highlight_color) && Number(item.highlight_number)
  );
  const legendItems = [];
  const seenNumbers = new Set();
  highlightedItems.forEach(item => {
    const number = Number(item.highlight_number);
    if (seenNumbers.has(number)) return;
    seenNumbers.add(number);
    legendItems.push(item);
  });
  comparisonHighlightLegend.innerHTML = legendItems.map(item => {
    const color = comparisonHighlightColor(item.highlight_color);
    return `
      <span class="comparison-highlight-legend-item" title="${escapeHtml(item.topic)}">
        <span class="comparison-highlight-swatch" style="--pair-color:${color}"></span>
        ${Number(item.highlight_number)}
      </span>
    `;
  }).join("");

  const leftCount = Number(data.left_pdf?.highlighted_passages) || 0;
  const rightCount = Number(data.right_pdf?.highlighted_passages) || 0;
  comparisonPdfStatus.textContent = highlightedItems.length
    ? `Rapor A: ${leftCount}, Rapor B: ${rightCount} pasaj isaretlendi. Bir sonuc uzerinden PDF'de Goster'e basabilirsin.`
    : "PDF'ler acildi ancak eslesen pasaj koordinati bulunamadi.";

  const initialItem = highlightedItems[0];
  const leftPage = initialItem?.left?.highlight_page || initialItem?.left?.page_start || 1;
  const rightPage = initialItem?.right?.highlight_page || initialItem?.right?.page_start || 1;
  setComparisonPdfSide("left", data.left_pdf, data.left, leftPage);
  setComparisonPdfSide("right", data.right_pdf, data.right, rightPage);
}

function renderComparison(data) {
  latestComparisonData = data;
  comparisonOutput.hidden = false;
  comparisonSummary.innerHTML = `
    <div class="comparison-summary-item">
      <span class="comparison-summary-value">${data.similarity_count}</span>
      <span class="comparison-summary-label">Benzerlik</span>
    </div>
    <div class="comparison-summary-item">
      <span class="comparison-summary-value">${data.difference_count}</span>
      <span class="comparison-summary-label">Farklilik</span>
    </div>
    <div class="comparison-summary-item">
      <span class="comparison-summary-value">%${Math.round((Number(data.coverage) || 0) * 100)}</span>
      <span class="comparison-summary-label">Eslesen icerik kapsami</span>
    </div>
  `;
  comparisonSimilaritiesTab.textContent = `Benzerlikler (${data.similarity_count})`;
  comparisonDifferencesTab.textContent = `Farkliliklar (${data.difference_count})`;
  renderComparisonRows(
    comparisonSimilarities,
    data.similarities || [],
    "Guvenilir ortak teknik bulgu bulunamadi."
  );
  renderComparisonRows(
    comparisonDifferences,
    data.differences || [],
    "Guvenilir farklilik bulunamadi."
  );
  renderComparisonPdfWorkspace(data);
  setComparisonResultView(data.similarity_count > 0 ? "similarities" : "differences");
}

async function runReportComparison() {
  const left = comparisonSourcePayload(comparisonLeftSelect.value);
  const right = comparisonSourcePayload(comparisonRightSelect.value);
  if (!left || !right) {
    comparisonStatus.textContent = "Karsilastirma icin Rapor A ve Rapor B secilmeli.";
    return;
  }
  if (comparisonLeftSelect.value === comparisonRightSelect.value) {
    comparisonStatus.textContent = "Iki farkli rapor sec.";
    return;
  }
  comparisonRunButton.disabled = true;
  comparisonOutput.hidden = true;
  comparisonPdfWorkspace.hidden = true;
  comparisonPairFullscreenOpen.disabled = true;
  delete comparisonPairFullscreenOpen.dataset.url;
  comparisonLeftPdfFrame.removeAttribute("src");
  comparisonRightPdfFrame.removeAttribute("src");
  const startedAt = startTimer(
    message => { comparisonStatus.textContent = message; },
    "Raporlar eslestiriliyor ve farklar dogrulaniyor..."
  );
  try {
    const response = await fetch("/report-comparison", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ left, right, use_llm: true }),
    });
    const data = await response.json();
    if (!response.ok) {
      stopTimer(
        startedAt,
        message => { comparisonStatus.textContent = message; },
        data.detail || "Raporlar karsilastirilamadi."
      );
      return;
    }
    renderComparison(data);
    const generation = data.llm_used ? data.generation_provider : "kural tabanli";
    const cacheText = data.cache_hit ? " | onbellek" : "";
    stopTimer(
      startedAt,
      message => { comparisonStatus.textContent = message; },
      `Karsilastirma tamamlandi. Benzerlik: ${data.similarity_count}, farklilik: ${data.difference_count} | ${generation}${cacheText}`
    );
  } catch (error) {
    stopTimer(
      startedAt,
      message => { comparisonStatus.textContent = message; },
      `Raporlar karsilastirilamadi: ${error}`
    );
  } finally {
    comparisonRunButton.disabled = false;
  }
}

function compactChatProvider(provider) {
  const value = String(provider || "");
  if (!value) return "";
  if (value.includes("Qwen3-Embedding")) return "Qwen3 Embedding";
  if (value.includes("ollama:")) return value.split("ollama:").pop();
  if (value === "document-analysis:status") return "Kural tabanli";
  if (value === "database") return "Veritabani";
  if (value === "keyword-only") return "Keyword";
  return value.split(":").pop();
}

function chatEngineLabel(data) {
  if (!data.retrieval_used) {
    return `Genel LLM${data.embedding_provider ? ` • ${compactChatProvider(data.embedding_provider)}` : ""}`;
  }
  const version = data.retrieval_version === "v1" ? "RAG v1 • Klasik" : "RAG v2 • Beta";
  const providers = [
    compactChatProvider(data.retrieval_provider),
    compactChatProvider(data.embedding_provider),
  ].filter((value, index, items) => value && items.indexOf(value) === index);
  return [version, ...providers].join(" • ");
}

function appendChatMessage(role, content, meta = "") {
  const node = document.createElement("div");
  node.className = `chat-message ${role}`;
  const label = document.createElement("div");
  label.className = "chat-message-label";
  const labelText = document.createElement("span");
  labelText.textContent = role === "user" ? "Sen" : "Big Agent";
  label.appendChild(labelText);
  if (meta) {
    const metaNode = document.createElement("span");
    metaNode.className = "chat-message-meta";
    metaNode.textContent = meta;
    label.appendChild(metaNode);
  }
  const body = document.createElement("div");
  body.className = "chat-message-body";
  body.textContent = content;
  node.appendChild(label);
  node.appendChild(body);
  chatMessages.appendChild(node);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function resetChat() {
  chatHistory = [];
  chatContextDocumentIds = [];
  chatMessages.innerHTML = "";
  appendChatMessage("assistant", "Merhaba. Raporlar uzerinden soru sorabilir, ben de kaynaklariyla birlikte cevaplayabilirim.");
  chatSources.innerHTML = '<div class="empty">Kaynaklar cevap geldikce burada listelenecek.</div>';
  chatSourceMeta.textContent = "Cevap geldikce ilgili rapor pasajlari burada gorunur.";
  chatStatus.textContent = "Chatbot hazir.";
  chatInput.value = "";
  chatInput.focus();
}

async function sendChatMessage() {
  const message = chatInput.value.trim();
  if (!message) {
    chatStatus.textContent = "Mesaj yazmadan gonderemem.";
    return;
  }

  chatInput.value = "";
  appendChatMessage("user", message);
  chatHistory.push({ role: "user", content: message });
  chatSendButton.disabled = true;
  const startedAt = startTimer(
    text => { chatStatus.textContent = text; },
    "Chatbot cevap ariyor..."
  );

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message,
        history: chatHistory.slice(-8),
        assistant_mode: chatAssistantMode.value,
        retrieval_version: chatRetrievalVersion.value,
        mode: chatMode.value,
        limit: 5,
        document_ids: chatContextDocumentIds.slice(0, 8),
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      stopTimer(startedAt, text => { chatStatus.textContent = text; }, data.detail || "Chatbot cevap veremedi.");
      appendChatMessage("assistant", data.detail || "Cevap olusturulamadi.");
      return;
    }
    const engineLabel = chatEngineLabel(data);
    appendChatMessage("assistant", data.answer, engineLabel);
    chatHistory = data.history || [
      ...chatHistory,
      { role: "assistant", content: data.answer },
    ];
    chatContextDocumentIds = [...new Set((data.sources || [])
      .map(item => Number(item.document_id))
      .filter(value => Number.isInteger(value) && value > 0)
    )].slice(0, 8);
    renderChatSources(data.sources || []);
    stopTimer(
      startedAt,
      text => { chatStatus.textContent = text; },
      `${engineLabel} | Guven: ${formatScore(data.confidence)} | Kaynak: ${(data.sources || []).length}`
    );
  } catch (error) {
    stopTimer(startedAt, text => { chatStatus.textContent = text; }, `Chatbot hata verdi: ${error}`);
    appendChatMessage("assistant", "Cevap olusturulurken hata olustu.");
  } finally {
    chatSendButton.disabled = false;
  }
}

function renderChatSources(items) {
  if (!items || items.length === 0) {
    chatSources.innerHTML = '<div class="empty">Bu cevap icin kaynak bulunamadi.</div>';
    chatSourceMeta.textContent = "Bu cevap sohbet yaniti olarak dondu; kaynak pasaj kullanilmadi.";
    return;
  }

  chatSourceMeta.textContent = `${items.length} kaynak bulundu. Karta tiklayinca orijinal dosya acilir.`;
  chatSources.innerHTML = items.map(item => `
    <article class="chat-source-card" onclick="openDocumentFile(${item.document_id})">
      <div class="title">${escapeHtml(item.document_title)}</div>
      <div class="small">Belge ID: ${item.document_id} | Sayfa ${item.page_start}-${item.page_end}${item.section_title ? " | " + escapeHtml(item.section_title) : ""}</div>
      <div class="small">match: ${escapeHtml(item.match_type)} | combined: ${formatScore(item.combined_score)}</div>
      <div class="excerpt">${escapeHtml(item.chunk_text)}</div>
    </article>
  `).join("");
}

function renderAnswerSources(items) {
  if (!items || items.length === 0) {
    answerSources.innerHTML = '<div class="empty">Kaynak bulunamadi.</div>';
    return;
  }

  answerSources.innerHTML = items.map(item => `
    <article class="source-card" onclick="openDocumentFile(${item.document_id})" style="cursor:pointer;">
      <div class="title">${escapeHtml(item.document_title)}</div>
      <div class="small">Belge ID: ${item.document_id} | Sayfa ${item.page_start}-${item.page_end}${item.section_title ? " | " + escapeHtml(item.section_title) : ""}</div>
      <div class="small">match: ${escapeHtml(item.match_type)} | combined: ${formatScore(item.combined_score)}</div>
      <div class="excerpt">${escapeHtml(item.chunk_text)}</div>
    </article>
  `).join("");
}

function renderDraftSources(items) {
  if (!items || items.length === 0) {
    draftSources.innerHTML = '<div class="empty">Referans kaynak bulunamadi.</div>';
    selectedDraftDocumentIds = [];
    return;
  }

  const previousSelection = new Set(selectedDraftDocumentIds.map(Number));
  const hasPreviousSelection = previousSelection.size > 0;
  const sourceDocumentIds = [...new Set(items.map(item => Number(item.document_id)).filter(value => Number.isInteger(value) && value > 0))];
  selectedDraftDocumentIds = hasPreviousSelection
    ? sourceDocumentIds.filter(value => previousSelection.has(value))
    : sourceDocumentIds;

  draftSources.innerHTML = items.map(item => `
    <article class="source-card">
      <div class="title">${escapeHtml(item.document_title)}</div>
      <div class="small">Belge ID: ${item.document_id} | Sayfa ${item.page_start}-${item.page_end}${item.section_title ? " | " + escapeHtml(item.section_title) : ""}</div>
      <label class="small" style="display:flex;gap:8px;align-items:center;margin:8px 0;">
        <input type="checkbox" class="draft-source-check" value="${item.document_id}" ${selectedDraftDocumentIds.includes(Number(item.document_id)) ? "checked" : ""} />
        Rapor taslaginda kullan
      </label>
      <div class="excerpt">${escapeHtml(item.chunk_text)}</div>
      <button class="button secondary" type="button" onclick="openDocumentFile(${item.document_id})" style="margin-top:8px;">Raporu Gor</button>
    </article>
  `).join("");

  draftSources.querySelectorAll(".draft-source-check").forEach(input => {
    input.addEventListener("change", updateSelectedDraftSources);
  });
  updateSelectedDraftSources();
}

function updateSelectedDraftSources() {
  selectedDraftDocumentIds = Array.from(draftSources.querySelectorAll(".draft-source-check:checked"))
    .map(input => Number(input.value))
    .filter(value => Number.isInteger(value) && value > 0);
}

function renderCatalogMatches(items) {
  if (!items || items.length === 0) {
    catalogMatches.innerHTML = '<div class="empty">Eslesen katalog kaydi bulunamadi.</div>';
    return;
  }

  catalogMatches.innerHTML = items.map(item => {
    const openAction = item.matched_document_id ? ` onclick="openDocumentFile(${item.matched_document_id})" style="cursor:pointer;"` : "";
    const matched = item.matched_document_id ? ` | Belge ID: ${item.matched_document_id}` : "";
    return `
      <article class="source-card"${openAction}>
        <div class="title">${escapeHtml(item.report_code)}</div>
        <div class="small">${escapeHtml(item.vehicle_name)} | ${escapeHtml(item.discipline)}${item.report_date ? " | " + escapeHtml(item.report_date) : ""}${matched}</div>
        <div class="excerpt">${escapeHtml(item.report_title)}</div>
        <div class="small">${escapeHtml(item.authors || "")}</div>
      </article>
    `;
  }).join("");
}

function updateCatalogScope(items, question = "") {
  const matches = Array.isArray(items) ? items : [];
  const matchedDocumentIds = [...new Set(matches
    .map(item => Number(item.matched_document_id))
    .filter(value => Number.isInteger(value) && value > 0)
  )];
  catalogMatchCount.textContent = String(matches.length);
  catalogDocumentCount.textContent = String(matchedDocumentIds.length);
  catalogScopeReady.textContent = matchedDocumentIds.length > 0 ? "Evet" : "Hayir";
  lastCatalogMatches = matches;
  lastCatalogQuestion = question || "";
}

function renderMultiDocumentDocuments(items) {
  if (!items || items.length === 0) {
    multiDocumentDocuments.innerHTML = '<div class="empty">Yuklu ve eslesen belge bulunamadi.</div>';
    return;
  }

  multiDocumentDocuments.innerHTML = items.map(item => `
    <article class="source-card" onclick="openDocumentFile(${item.document_id})" style="cursor:pointer;">
      <div class="title">${escapeHtml(item.document_title)}</div>
      <div class="small">Belge ID: ${item.document_id} | ${escapeHtml(item.file_name || "")}</div>
    </article>
  `).join("");
}

function renderMultiDocumentSources(items) {
  if (!items || items.length === 0) {
    multiDocumentSources.innerHTML = '<div class="empty">Kaynak pasaj bulunamadi.</div>';
    return;
  }

  multiDocumentSources.innerHTML = items.map(item => `
    <article class="source-card" onclick="openDocumentFile(${item.document_id})" style="cursor:pointer;">
      <div class="title">${escapeHtml(item.document_title)}</div>
      <div class="small">Belge ID: ${item.document_id} | Sayfa ${item.page_start}-${item.page_end}${item.section_title ? " | " + escapeHtml(item.section_title) : ""}</div>
      <div class="small">match: ${escapeHtml(item.match_type)} | combined: ${formatScore(item.combined_score)}</div>
      <div class="excerpt">${escapeHtml(item.chunk_text)}</div>
    </article>
  `).join("");
}

function renderMultiDocumentComparison(rows) {
  if (!rows || rows.length === 0) {
    multiDocumentComparison.innerHTML = `
      <table>
        <thead>
          <tr>
            <th>Belge</th>
            <th>Cevap</th>
            <th>Guven</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td colspan="3" class="small">Karsilastirma sonuclari burada yer alacak.</td>
          </tr>
        </tbody>
      </table>
    `;
    return;
  }

  multiDocumentComparison.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Belge</th>
          <th>Cevap</th>
          <th>Guven</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map(row => `
          <tr>
            <td>${escapeHtml(row.document_title)}</td>
            <td>${escapeHtml(row.answer)}</td>
            <td>${formatScore(row.confidence)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function resetMultiDocumentWorkspace() {
  multiDocumentAnswer.textContent = "Secilen rapor grubunun icerik cevabi burada gorunecek.";
  multiDocumentMeta.textContent = "Ikinci asama soru sorulmadi.";
  renderMultiDocumentDocuments([]);
  renderMultiDocumentSources([]);
  renderMultiDocumentComparison([]);
}

async function runCatalogAsk() {
  const question = catalogQuestion.value.trim();
  if (!question) {
    catalogAskMeta.textContent = "Katalog sorusu icin once bir soru gir.";
    return;
  }

  catalogAskButton.disabled = true;
  const startedAt = startTimer(
    message => { catalogAskMeta.textContent = message; },
    "Katalog sorusu isleniyor..."
  );
  try {
    const response = await fetch("/ask/catalog", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ question, limit: 30 }),
    });
    const data = await response.json();
    if (!response.ok) {
      stopTimer(startedAt, message => { catalogAskMeta.textContent = message; }, data.detail || "Katalog sorusu basarisiz oldu.");
      return;
    }
    stopTimer(
      startedAt,
      message => { catalogAskMeta.textContent = message; },
      `Eslesen katalog kaydi: ${data.match_count}`
    );
    catalogAnswer.textContent = data.answer;
    updateCatalogScope(data.catalog_matches, question);
    renderCatalogMatches(data.catalog_matches);
    resetMultiDocumentWorkspace();
  } catch (error) {
    stopTimer(startedAt, message => { catalogAskMeta.textContent = message; }, `Katalog sorusu basarisiz oldu: ${error}`);
  } finally {
    catalogAskButton.disabled = false;
  }
}

async function runMultiDocumentAsk() {
  const question = multiDocumentQuestion.value.trim();
  if (!question) {
    multiDocumentMeta.textContent = "Icerik sorusu icin once bir soru gir.";
    return;
  }

  const documentIds = [...new Set((lastCatalogMatches || [])
    .map(item => Number(item.matched_document_id))
    .filter(value => Number.isInteger(value) && value > 0)
  )];
  const catalogScopeQuestion = lastCatalogQuestion || catalogQuestion.value.trim();
  if (documentIds.length === 0 && !catalogScopeQuestion) {
    multiDocumentMeta.textContent = "Once katalog sorusu sorup eslesen rapor grubunu olustur.";
    return;
  }

  multiDocumentAskButton.disabled = true;
  const startedAt = startTimer(
    message => { multiDocumentMeta.textContent = message; },
    "Coklu belge icerigi taraniyor..."
  );
  try {
    const response = await fetch("/ask/multi-document", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question,
        catalog_question: catalogScopeQuestion || null,
        mode: multiDocumentMode.value,
        limit: Number(multiDocumentLimit.value) || 6,
        document_ids: documentIds,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      stopTimer(startedAt, message => { multiDocumentMeta.textContent = message; }, data.detail || "Coklu belge QA basarisiz oldu.");
      return;
    }
    stopTimer(
      startedAt,
      message => { multiDocumentMeta.textContent = message; },
      `Yuklu belge: ${data.matched_document_count} | Katalog kaydi: ${data.matched_catalog_count} | Guven: ${formatScore(data.confidence)}`
    );
    multiDocumentAnswer.textContent = data.answer;
    renderMultiDocumentDocuments(data.documents);
    renderMultiDocumentComparison(data.comparison_rows);
    renderMultiDocumentSources(data.sources);
  } catch (error) {
    stopTimer(startedAt, message => { multiDocumentMeta.textContent = message; }, `Coklu belge QA basarisiz oldu: ${error}`);
  } finally {
    multiDocumentAskButton.disabled = false;
  }
}

function renderGraph(data) {
  graphState = buildGraphBrowserState(data);
  renderGraphBrowser();
  graphStatus.textContent = `Kategori tarayici hazir. Kategori: ${graphState.categories.length}, belge: ${graphState.documents.length}.`;
}

function buildGraphBrowserState(data) {
  const nodes = data.nodes || [];
  const nodeById = new Map(nodes.map(node => [node.id, node]));
  const tagNodes = nodes.filter(node => node.type === "tag");
  const reportNodes = nodes.filter(node => node.type === "document" || node.type === "catalog");
  const tagsByReport = new Map(reportNodes.map(node => [node.id, []]));

  (data.edges || []).forEach(edge => {
    if (!tagsByReport.has(edge.source)) return;
    const tagNode = nodeById.get(edge.target);
    if (!tagNode || tagNode.type !== "tag") return;
    tagsByReport.get(edge.source).push({
      id: `${tagNode.tag_type || "tag"}::${tagNode.label}`,
      type: tagNode.tag_type || "tag",
      label: tagNode.label || "",
    });
  });

  const categories = tagNodes
    .map(node => ({
      id: `${node.tag_type || "tag"}::${node.label}`,
      type: node.tag_type || "tag",
      label: node.label || "",
      count: 0,
    }))
    .filter(category => category.label);
  const categoryById = new Map(categories.map(category => [category.id, category]));

  const documents = reportNodes.map(node => {
    const tags = tagsByReport.get(node.id) || [];
    tags.forEach(tag => {
      const category = categoryById.get(tag.id);
      if (category) category.count += 1;
    });
    const discipline = tags.find(tag => tag.type === "discipline");
    const year = tags.find(tag => tag.type === "year");
    return {
      id: node.id,
      name: node.label || "-",
      type: discipline ? discipline.label : (node.type === "document" ? "Yuklu belge" : "Katalog kaydi"),
      date: year ? year.label : "-",
      tags,
      status: node.status === "ingested" ? "Iceride" : "Iceri alinacak",
      documentId: node.document_id,
      catalogEntryId: node.catalog_entry_id,
    };
  });

  return {
    categories: categories.sort((a, b) => b.count - a.count || a.label.localeCompare(b.label)),
    documents,
    selectedCategoryId: graphState.selectedCategoryId || "all",
    search: graphState.search || "",
  };
}

function renderGraphBrowser() {
  const selectedExists = graphState.selectedCategoryId === "all" || graphState.categories.some(category => category.id === graphState.selectedCategoryId);
  if (!selectedExists) graphState.selectedCategoryId = "all";
  renderGraphStats();
  renderGraphTree();
  renderGraphCategoryFilter();
  renderGraphDensityChart();
  renderGraphDocuments();
}

function graphCategoryTypeLabel(type) {
  const labels = {
    vehicle: "Arac",
    discipline: "Analiz Tipi",
    year: "Yil",
    author: "Yazar",
    status: "Durum",
  };
  return labels[type] || "Etiket";
}

function filteredGraphDocuments() {
  const search = normalizeSearchText(graphState.search || "");
  return graphState.documents.filter(document => {
    const categoryMatch = graphState.selectedCategoryId === "all" || document.tags.some(tag => tag.id === graphState.selectedCategoryId);
    if (!categoryMatch) return false;
    if (!search) return true;
    const haystack = normalizeSearchText([
      document.name,
      document.type,
      document.date,
      document.status,
      document.tags.map(tag => tag.label).join(" "),
    ].join(" "));
    return haystack.includes(search);
  });
}

function renderGraphStats() {
  const densest = graphState.categories[0];
  graphStats.innerHTML = `
    <div class="stat-card"><div class="stat-label">Kategori</div><div class="stat-value">${graphState.categories.length}</div></div>
    <div class="stat-card"><div class="stat-label">Belge</div><div class="stat-value">${graphState.documents.length}</div></div>
    <div class="stat-card"><div class="stat-label">En Yogun</div><div class="stat-value">${densest ? escapeHtml(densest.label).slice(0, 18) : "-"}</div></div>
  `;
}

function renderGraphTree() {
  const groups = new Map();
  graphState.categories.forEach(category => {
    if (!groups.has(category.type)) groups.set(category.type, []);
    groups.get(category.type).push(category);
  });
  const allButton = `
    <button class="category-button ${graphState.selectedCategoryId === "all" ? "active" : ""}" type="button" data-graph-category="all">
      <span>Tum Belgeler</span><span class="count">${graphState.documents.length}</span>
    </button>
  `;
  const groupHtml = Array.from(groups.entries()).map(([type, items]) => `
    <div class="category-group">
      <div class="category-group-title">${escapeHtml(graphCategoryTypeLabel(type))}</div>
      ${items.slice(0, 30).map(category => `
        <button class="category-button ${graphState.selectedCategoryId === category.id ? "active" : ""}" type="button" data-graph-category="${escapeHtml(category.id)}">
          <span>${escapeHtml(category.label)}</span><span class="count">${category.count}</span>
        </button>
      `).join("")}
    </div>
  `).join("");
  graphTree.innerHTML = allButton + groupHtml;
  graphTree.querySelectorAll("[data-graph-category]").forEach(button => {
    button.addEventListener("click", () => {
      graphState.selectedCategoryId = button.dataset.graphCategory || "all";
      graphCategoryFilter.value = graphState.selectedCategoryId;
      renderGraphBrowser();
    });
  });
}

function renderGraphCategoryFilter() {
  const options = [
    '<option value="all">Tum kategoriler</option>',
    ...graphState.categories.map(category => `<option value="${escapeHtml(category.id)}">${escapeHtml(graphCategoryTypeLabel(category.type))}: ${escapeHtml(category.label)}</option>`),
  ];
  graphCategoryFilter.innerHTML = options.join("");
  graphCategoryFilter.value = graphState.selectedCategoryId;
}

function renderGraphDensityChart() {
  const top = graphState.categories.slice(0, 10);
  if (!top.length) {
    graphDensityChart.innerHTML = '<div class="empty">Yogunluk verisi bulunamadi.</div>';
    return;
  }
  const maxCount = Math.max(...top.map(category => category.count), 1);
  graphDensityChart.innerHTML = top.map(category => `
    <div class="density-row">
      <div class="density-label" title="${escapeHtml(category.label)}">${escapeHtml(category.label)}</div>
      <div class="density-track"><div class="density-bar" style="width:${Math.max(4, Math.round(category.count * 100 / maxCount))}%;"></div></div>
      <div>${category.count}</div>
    </div>
  `).join("");
}

function renderGraphDocuments() {
  const items = filteredGraphDocuments();
  if (!items.length) {
    graphDocumentsTable.innerHTML = '<tr><td colspan="5" class="small">Bu filtreyle belge bulunamadi.</td></tr>';
    return;
  }
  graphDocumentsTable.innerHTML = items.slice(0, 120).map(document => `
    <tr>
      <td><div class="doc-name">${escapeHtml(document.name)}</div><div class="small">${escapeHtml(document.documentId ? `Belge ID: ${document.documentId}` : `Katalog ID: ${document.catalogEntryId || "-"}`)}</div></td>
      <td>${escapeHtml(document.type)}</td>
      <td>${escapeHtml(document.date)}</td>
      <td><div class="doc-tags">${document.tags.slice(0, 5).map(tag => `<span class="doc-tag">${escapeHtml(tag.label)}</span>`).join("")}</div></td>
      <td><span class="status-pill ${document.status === "Iceride" ? "complete" : "not_ingested"}">${escapeHtml(document.status)}</span></td>
    </tr>
  `).join("");
}

async function refreshGraph() {
  graphRefreshButton.disabled = true;
  graphStatus.textContent = "Kategori verisi yukleniyor...";
  try {
    const response = await fetch("/graph/overview?limit=160");
    const data = await response.json();
    if (!response.ok) {
      graphStatus.textContent = data.detail || "Kategori verisi yuklenemedi.";
      return;
    }
    renderGraph(data);
  } catch (error) {
    graphStatus.textContent = `Kategori verisi yuklenemedi: ${error}`;
  } finally {
    graphRefreshButton.disabled = false;
  }
}

function fileHrefFromPath(rawPath) {
  const backslash = String.fromCharCode(92);
  return rawPath && (rawPath.includes(backslash) || rawPath.includes("/"))
    ? `file:///${rawPath.split(backslash).join("/")}`
    : "";
}

function catalogLinkHtml(item) {
  const rawPath = item.source_path || item.report_code || "";
  if (!rawPath) {
    return "";
  }
  const label = rawPath.length > 42 ? `${rawPath.slice(0, 39)}...` : rawPath;
  const href = fileHrefFromPath(rawPath);
  if (!href) {
    return `<span title="${escapeHtml(rawPath)}">${escapeHtml(label)}</span>`;
  }
  return `<a href="${escapeHtml(href)}" title="${escapeHtml(rawPath)}" target="_blank">${escapeHtml(label)}</a>`;
}

function renderCatalogTableRows(target, items, options = {}) {
  const selectable = Boolean(options.selectable);
  const columns = selectable ? 6 : 5;
  if (!items || items.length === 0) {
    target.innerHTML = `<tr><td colspan="${columns}" class="small">Kayit bulunamadi.</td></tr>`;
    return;
  }

  target.innerHTML = items.map(item => {
    const checkbox = selectable
      ? `<td><input class="catalog-select" type="checkbox" data-catalog-entry-id="${item.id}" /></td>`
      : "";
    const statusCell = selectable ? "" : `<td>${embeddingStatusHtml(item)}</td>`;
    const previewCell = selectable
      ? `<td class="catalog-preview-cell"><button class="button secondary catalog-preview-button" type="button" data-catalog-preview="${item.id}">Raporu Gor</button></td>`
      : "";
    const openAction = item.matched_document_id
      ? ` onclick="openDocumentFile(${item.matched_document_id})" style="cursor:pointer;"`
      : "";
    const documentText = item.matched_document_id ? ` | Belge ID: ${item.matched_document_id}` : "";
    return `
      <tr${openAction}>
        ${checkbox}
        <td>
          <div class="title">${escapeHtml(item.report_code)}</div>
          <div class="small">${escapeHtml(item.report_title || "")}${documentText}</div>
        </td>
        <td>${escapeHtml(item.vehicle_name || "")}</td>
        <td>${escapeHtml(item.discipline || "")}</td>
        ${statusCell}
        <td>${catalogLinkHtml(item)}</td>
        ${previewCell}
      </tr>
    `;
  }).join("");
}

function catalogCandidateLogPayload(item) {
  return {
    requested_count: 1,
    ingested_count: item.status === "ingested" ? 1 : 0,
    duplicate_count: item.status === "duplicate" ? 1 : 0,
    error_count: item.status === "error" ? 1 : 0,
    items: [item],
  };
}

function renderCatalogCandidates(entryId, data) {
  const items = data.items || [];
  if (items.length === 0) {
    return '<div class="small">Bu katalog kaydi icin PDF/DOCX/PPTX aday dosya bulunamadi.</div>';
  }
  const rows = items.slice(0, 20).map(item => {
    const fileName = item.file_name || item.path || "";
    const href = `/catalog/${entryId}/file-preview?file_path=${encodeURIComponent(item.path || "")}`;
    const fileLabel = href
      ? `<a href="${escapeHtml(href)}" title="${escapeHtml(item.path || "")}" target="_blank">${escapeHtml(fileName)}</a>`
      : escapeHtml(fileName);
    const encodedPath = escapeHtml(encodeURIComponent(item.path || ""));
    return `
    <div class="catalog-candidate-item">
      <div>
        <div class="catalog-candidate-name">${fileLabel}</div>
        <div class="catalog-candidate-meta">
          ${escapeHtml((item.extension || "").toUpperCase())} | skor ${Number(item.score || 0)} | ${escapeHtml(item.match_method || "")}
        </div>
        <div class="catalog-candidate-meta">${escapeHtml(item.path || "")}</div>
      </div>
      <div class="actions">
        <a class="button secondary" href="${escapeHtml(href)}" target="_blank">Gor</a>
        <button
          class="button primary"
          type="button"
          data-catalog-ingest-candidate="${entryId}"
          data-file-path="${encodedPath}"
        >Bu dosyayi ice al</button>
      </div>
    </div>
  `;
  }).join("");
  const more = items.length > 20
    ? `<div class="small">... ve ${items.length - 20} aday daha var. Ilk 20 aday gosteriliyor.</div>`
    : "";
  return rows + more;
}

async function loadCatalogCandidates(entryId) {
  const row = document.getElementById(`catalogCandidateRow${entryId}`);
  const list = document.getElementById(`catalogCandidateList${entryId}`);
  if (!row || !list) return;
  if (!row.classList.contains("hidden") && list.dataset.loaded === "true") {
    row.classList.add("hidden");
    return;
  }

  row.classList.remove("hidden");
  list.dataset.loaded = "false";
  list.innerHTML = '<div class="small">Aday dosyalar araniyor...</div>';
  try {
    const response = await fetch(`/catalog/${entryId}/file-candidates`);
    const data = await response.json();
    setCatalogLog(data);
    if (!response.ok || data.error) {
      list.innerHTML = `<div class="small">${escapeHtml(data.detail || data.error || "Aday dosyalar alinamadi.")}</div>`;
      return;
    }
    list.innerHTML = renderCatalogCandidates(entryId, data);
    list.dataset.loaded = "true";
  } catch (error) {
    list.innerHTML = `<div class="small">Aday dosyalar alinamadi: ${escapeHtml(error)}</div>`;
  }
}

async function ingestCatalogCandidate(entryId, encodedFilePath) {
  const filePath = decodeURIComponent(encodedFilePath || "");
  if (!filePath) {
    setCatalogStatus("error", "Iceri almak icin aday dosya yolu bulunamadi.");
    return;
  }

  catalogTableRefreshButton.disabled = true;
  catalogSelectedIngestButton.disabled = true;
  const startedAt = startTimer(
    message => setCatalogStatus("ok", message),
    "Secilen aday dosya ice aliniyor..."
  );
  try {
    const response = await fetch("/catalog/ingest-candidate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ catalog_entry_id: entryId, file_path: filePath }),
    });
    const data = await response.json();
    const logPayload = catalogCandidateLogPayload(data);
    setCatalogLog(logPayload);
    if (!response.ok || data.status === "error") {
      stopTimer(
        startedAt,
        message => setCatalogStatus("error", message),
        data.detail || data.error || "Secilen aday dosya ice alinamadi."
      );
      return;
    }
    stopTimer(
      startedAt,
      message => setCatalogStatus("ok", message),
      `Aday dosya ice alindi. Durum: ${data.status}. Belge ID: ${data.document_id || "-"}`
    );
    await refreshCatalogTable();
    await refreshUploadedDocuments();
  } catch (error) {
    stopTimer(startedAt, message => setCatalogStatus("error", message), `Secilen aday dosya ice alinamadi: ${error}`);
  } finally {
    catalogTableRefreshButton.disabled = false;
    catalogSelectedIngestButton.disabled = false;
  }
}

function embeddingStatusHtml(item) {
  const status = item.embedding_status || "not_ingested";
  const labels = {
    complete: "Embedding tamam",
    partial: "Embedding eksik",
    missing: "Embedding yok",
    not_ingested: "Ingest yok",
  };
  const countText = Number(item.chunk_count) > 0
    ? ` ${Number(item.embedding_count || 0)}/${Number(item.chunk_count || 0)}`
    : "";
  return `<span class="status-pill ${escapeHtml(status)}">${escapeHtml(labels[status] || status)}${countText}</span>`;
}

function renderCatalogTable(data) {
  catalogIngestedCount.textContent = String(data.ingested_count || 0);
  catalogPendingCount.textContent = String(data.pending_count || 0);
  renderCatalogTableRows(catalogIngestedTable, data.ingested || [], { selectable: false });
  renderCatalogTableRows(catalogPendingTable, data.pending || [], { selectable: true });
}

async function refreshCatalogTable() {
  catalogTableRefreshButton.disabled = true;
  catalogSelectedIngestButton.disabled = true;
  const startedAt = startTimer(
    message => setCatalogStatus("ok", message),
    "Katalog tablosu yenileniyor..."
  );
  try {
    const response = await fetch("/catalog/table?limit=2000");
    const data = await response.json();
    setCatalogLog(data);
    if (!response.ok) {
      stopTimer(startedAt, message => setCatalogStatus("error", message), data.detail || "Katalog tablosu alinamadi.");
      return;
    }
    renderCatalogTable(data);
    const autoLinkText = Number(data.auto_link_created_count || 0) > 0
      ? ` Yeni otomatik eslesme: ${data.auto_link_created_count}.`
      : "";
    stopTimer(
      startedAt,
      message => setCatalogStatus("ok", message),
      `Katalog tablosu hazir. Ingest edilmis: ${data.ingested_count}, edilmemis: ${data.pending_count}.${autoLinkText}`
    );
  } catch (error) {
    stopTimer(startedAt, message => setCatalogStatus("error", message), `Katalog tablosu alinamadi: ${error}`);
  } finally {
    catalogTableRefreshButton.disabled = false;
    catalogSelectedIngestButton.disabled = false;
  }
}

async function ingestSelectedCatalogRows() {
  const selectedIds = Array.from(document.querySelectorAll(".catalog-select:checked"))
    .map(input => Number(input.dataset.catalogEntryId))
    .filter(value => Number.isInteger(value) && value > 0);
  if (selectedIds.length === 0) {
    setCatalogStatus("error", "Ice almak icin once kirmizi tablodan rapor sec.");
    return;
  }

  catalogTableRefreshButton.disabled = true;
  catalogSelectedIngestButton.disabled = true;
  const startedAt = startTimer(
    message => setCatalogStatus("ok", message),
    `${selectedIds.length} katalog kaydi ice aliniyor...`
  );
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 60000);
  try {
    const response = await fetch("/catalog/ingest-selected", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ catalog_entry_ids: selectedIds }),
      signal: controller.signal,
    });
    window.clearTimeout(timeoutId);
    const data = await response.json();
    setCatalogLog(data);
    if (!response.ok) {
      stopTimer(startedAt, message => setCatalogStatus("error", message), data.detail || "Secilen raporlar ice alinamadi.");
      return;
    }
    stopTimer(
      startedAt,
      message => setCatalogStatus(data.error_count ? "error" : "ok", message),
      catalogIngestResultMessage(data)
    );
    await refreshCatalogTable();
    await refreshUploadedDocuments();
  } catch (error) {
    window.clearTimeout(timeoutId);
    const message = error && error.name === "AbortError"
      ? "Secilen raporlar ice alinamadi: dosya arama 60 saniyeyi asti."
      : `Secilen raporlar ice alinamadi: ${error}`;
    stopTimer(startedAt, messageText => setCatalogStatus("error", messageText), message);
  } finally {
    catalogTableRefreshButton.disabled = false;
    catalogSelectedIngestButton.disabled = false;
  }
}

async function openCatalogPreview(entryId) {
  if (!entryId) {
    setCatalogStatus("error", "Raporu acmak icin katalog kaydi bulunamadi.");
    return;
  }
  setCatalogStatus("ok", "Rapor dosyasi araniyor...");
  try {
    const response = await fetch(`/catalog/${entryId}/best-file-preview-info`);
    const data = await response.json();
    if (!response.ok || !data.available) {
      setCatalogStatus("error", data.detail || data.error || "Bu katalog kaydi icin acilacak rapor dosyasi bulunamadi.");
      setCatalogLog(data);
      return;
    }
    const extension = String(data.extension || "").toLowerCase();
    if (extension === ".pdf") {
      setCatalogStatus("ok", `PDF tarayicida aciliyor: ${data.file_name || "dosya"}`);
      window.open(data.preview_url, "_blank");
      return;
    }

    const openResponse = await fetch(data.open_url, { method: "POST" });
    const openData = await openResponse.json();
    if (!openResponse.ok || !openData.opened) {
      setCatalogStatus("error", openData.detail || openData.error || "Dosya Office/Explorer ile acilamadi.");
      return;
    }
    setCatalogStatus("ok", `Dosya Office/Explorer ile acildi: ${openData.file_name || data.file_name || "dosya"}`);
  } catch (error) {
    setCatalogStatus("error", `Rapor dosyasi acilamadi: ${error}`);
  }
}

async function rebuildCatalogEmbeddings() {
  catalogEmbeddingRebuildButton.disabled = true;
  catalogTableRefreshButton.disabled = true;
  catalogSelectedIngestButton.disabled = true;
  const startedAt = startTimer(
    message => setCatalogStatus("ok", message),
    "Embeddingler yenileniyor..."
  );
  try {
    const response = await fetch("/embeddings/rebuild", {
      method: "POST",
    });
    const data = await response.json();
    setCatalogLog(data);
    if (!response.ok) {
      stopTimer(startedAt, message => setCatalogStatus("error", message), data.detail || "Embedding yenileme basarisiz oldu.");
      return;
    }
    stopTimer(
      startedAt,
      message => setCatalogStatus("ok", message),
      `Embeddingler yenilendi. Chunk: ${data.chunks_seen}, embedding: ${data.embeddings_created}.`
    );
    await refreshCatalogTable();
  } catch (error) {
    stopTimer(startedAt, message => setCatalogStatus("error", message), `Embedding yenileme basarisiz oldu: ${error}`);
  } finally {
    catalogEmbeddingRebuildButton.disabled = false;
    catalogTableRefreshButton.disabled = false;
    catalogSelectedIngestButton.disabled = false;
  }
}

async function runSearch() {
  const query = searchQuery.value.trim();
  const mode = searchMode.value;
  if (!query) {
    searchMeta.textContent = "Arama yapmak icin once bir sorgu gir.";
    return;
  }

  searchButton.disabled = true;
  const startedAt = startTimer(
    message => { searchMeta.textContent = message; },
    "Arama calisiyor..."
  );
  try {
    const useQueryEnhancement = true;
    const response = await fetch(`/search?query=${encodeURIComponent(query)}&mode=${encodeURIComponent(mode)}&limit=5&search_scope=content&use_query_enhancement=${useQueryEnhancement}`);
    const data = await response.json();
    if (!response.ok) {
      stopTimer(startedAt, message => { searchMeta.textContent = message; }, data.detail || "Arama basarisiz oldu.");
      return;
    }
    const retrieval = data.retrieval || {};
    const expandedCount = Array.isArray(retrieval.expanded_queries) ? retrieval.expanded_queries.length : 0;
    const filters = retrieval.applied_filters || {};
    const activeFilters = Object.entries(filters)
      .filter(([, value]) => value !== null && value !== undefined && value !== "")
      .map(([key, value]) => `${key}: ${value}`);
    const filterText = activeFilters.length ? ` | Filtre: ${activeFilters.join(", ")}` : "";
    const catalogScope = retrieval.catalog_scope || {};
    const catalogText = ` | Katalog: ${catalogScope.match_count || 0}`;
    const scopeWarning = catalogScope.scope_status === "catalog_matches_not_ingested"
      ? " | Katalogda var ama henuz iceri alinmis dokuman yok"
      : catalogScope.scope_status === "strict_catalog_title_fallback"
        ? " | Katalog linki yok, basliktan eslesen dokumanlar gosteriliyor"
      : "";
    const enhancementText = ` | Ek sorgu: ${expandedCount}${filterText}${catalogText}${scopeWarning}`;
    stopTimer(
      startedAt,
      message => { searchMeta.textContent = message; },
      `Mod: ${data.mode} | Provider: ${data.embedding_provider} | Sonuc: ${data.results.length} | Benzer rapor: ${data.similar_documents.length}${enhancementText}`
    );
    renderResults(data.results, query);
    renderSimilar(data.similar_documents, query);
  } catch (error) {
    stopTimer(startedAt, message => { searchMeta.textContent = message; }, `Arama basarisiz oldu: ${error}`);
  } finally {
    searchButton.disabled = false;
  }
}

async function runAsk() {
  const question = askQuestion.value.trim();
  const mode = askMode.value;
  const documentId = Number(askDocumentId.value);
  if (!question) {
    askMeta.textContent = "Soru sormak icin once bir soru gir.";
    return;
  }

  const payload = {
    question,
    mode,
    limit: 5,
  };
  if (Number.isInteger(documentId) && documentId > 0) {
    payload.document_id = documentId;
  }

  askButton.disabled = true;
  const startedAt = startTimer(
    message => { askMeta.textContent = message; },
    "Soru isleniyor..."
  );
  try {
    const response = await fetch("/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      stopTimer(startedAt, message => { askMeta.textContent = message; }, data.detail || "Soru-cevap basarisiz oldu.");
      return;
    }
    const scopeText = payload.document_id ? ` | Belge ID: ${payload.document_id}` : "";
    stopTimer(
      startedAt,
      message => { askMeta.textContent = message; },
      `Mod: ${data.mode}${scopeText} | Provider: ${data.embedding_provider} | Guven: ${formatScore(data.confidence)} | Kaynak: ${data.sources.length}`
    );
    answerText.textContent = data.answer;
    renderAnswerSources(data.sources);
  } catch (error) {
    stopTimer(startedAt, message => { askMeta.textContent = message; }, `Soru-cevap basarisiz oldu: ${error}`);
  } finally {
    askButton.disabled = false;
  }
}

async function runDraft(detailLevel) {
  ensureDraftDefaults();
  const title = draftTitle.value.trim();
  if (!title) {
    draftMeta.textContent = "Taslak uretmek icin once rapor basligi gir.";
    return;
  }

  const payload = {
    title,
    report_type: draftType.value.trim() || "Genel Teknik Rapor",
    report_no: draftReportNo.value.trim(),
    report_date: draftReportDate.value.trim(),
    prepared_by: draftPreparedBy.value.trim(),
    requested_by: draftRequestedBy.value.trim(),
    checked_by: draftCheckedBy.value.trim(),
    classification: "GENEL / PUBLIC",
    objective: draftObjective.value.trim(),
    keywords: draftKeywords.value.trim(),
    raw_notes: draftNotes.value.trim(),
    detail_level: detailLevel,
    mode: draftMode.value,
    limit: 5,
  };
  updateSelectedDraftSources();
  if (selectedDraftDocumentIds.length > 0) {
    payload.document_ids = selectedDraftDocumentIds;
  }

  draftQuickButton.disabled = true;
  draftDetailedButton.disabled = true;
  draftCopyButton.disabled = true;
  draftPdfButton.disabled = true;
  const startedAt = startTimer(
    message => { draftMeta.textContent = message; },
    detailLevel === "quick" ? "Hizli rapor uretiliyor..." : "Detayli rapor uretiliyor..."
  );
  try {
    const response = await fetch("/draft-report", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      stopTimer(startedAt, message => { draftMeta.textContent = message; }, data.detail || "Taslak olusturma basarisiz oldu.");
      return;
    }
    stopTimer(
      startedAt,
      message => { draftMeta.textContent = message; },
      `Tur: ${data.detail_level} | Arama: ${data.embedding_provider} | Yazim: ${data.generation_provider || "template"} | Anahtar kelime: ${data.refined_keywords.length} | Kaynak: ${data.sources.length}${payload.document_ids ? " | Secili belge: " + payload.document_ids.length : ""}`
    );
    draftOutput.textContent = data.draft;
    renderDraftSources(data.sources);
    lastDraftPayload = payload;
    lastDraftData = data;
    draftCopyButton.disabled = false;
    draftPdfButton.disabled = false;
  } catch (error) {
    stopTimer(startedAt, message => { draftMeta.textContent = message; }, `Taslak olusturma basarisiz oldu: ${error}`);
  } finally {
    draftQuickButton.disabled = false;
    draftDetailedButton.disabled = false;
  }
}

async function downloadDraftPdf(payload, title, detailLevel) {
  const response = await fetch("/draft-report/pdf", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error("PDF olusturulamadi.");
  }

  const blob = await response.blob();
  const safeTitle = String(title || "rapor")
    .replace(/[\\/:*?"<>|]+/g, "_")
    .replace(/\\s+/g, "_");
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${safeTitle}_${detailLevel}.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

async function downloadLatestDraftPdf() {
  if (!lastDraftPayload || !lastDraftData) {
    draftMeta.textContent = "Once bir taslak olustur.";
    return;
  }
  draftPdfButton.disabled = true;
  const startedAt = startTimer(
    message => { draftMeta.textContent = message; },
    "PDF hazirlaniyor..."
  );
  try {
    await downloadDraftPdf(lastDraftPayload, lastDraftData.title, lastDraftData.detail_level);
    stopTimer(startedAt, message => { draftMeta.textContent = message; }, "PDF indirildi.");
  } catch (error) {
    stopTimer(startedAt, message => { draftMeta.textContent = message; }, `PDF olusturulamadi: ${error}`);
  } finally {
    draftPdfButton.disabled = false;
  }
}

async function copyDraftText() {
  const text = draftOutput.textContent.trim();
  if (!lastDraftData || !text || text === "Taslak burada gorunecek.") {
    draftMeta.textContent = "Kopyalanacak taslak yok.";
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    draftMeta.textContent = "Taslak metin panoya kopyalandi.";
  } catch (error) {
    draftMeta.textContent = `Kopyalama basarisiz oldu: ${error}`;
  }
}

function fillDraftSample() {
  draftTitle.value = "BIG-E Surus Konfor Degerlendirme Raporu";
  draftType.value = "Test Degerlendirme Raporu";
  draftReportNo.value = "2025-BIG-e-NVH-01";
  draftReportDate.value = "13.01.2025";
  draftPreparedBy.value = "KEMAL DEMIR";
  draftRequestedBy.value = "ERKAN KUTLU";
  draftCheckedBy.value = "EROL CIFCI, A.SALIH YILMAZ";
  lastAutoReportNo = draftReportNo.value;
  draftMode.value = "keyword";
  draftObjective.value = "BIG-E araci icin surus konforu kapsaminda elde edilen test bulgularini ozetlemek ve onceki raporlarla uyumlu bir degerlendirme dili olusturmak.";
  draftKeywords.value = "BIG-E, surus konforu, NVH, yol verisi, titreşim, parkur";
  draftNotes.value = [
    "Farkli parkur kosullarinda surus konforu izlenmistir.",
    "Titreşim ve yol verisi bulgulari karsilastirmali olarak degerlendirilecektir.",
    "Sonucta iyilestirme alanlari ve takip aksiyonlari belirtilecektir."
  ].join("\\n");
  draftMeta.textContent = "Ornek alanlar dolduruldu. Istersen hizli veya detayli taslak uret.";
}

function clearDraftForm() {
  draftTitle.value = "";
  draftType.value = "";
  draftReportNo.value = "TASLAK";
  lastAutoReportNo = "TASLAK";
  draftReportDate.value = formatTodayForDraft();
  draftPreparedBy.value = "";
  draftRequestedBy.value = "";
  draftCheckedBy.value = "";
  draftMode.value = "keyword";
  draftObjective.value = "";
  draftKeywords.value = "";
  draftNotes.value = "";
  draftOutput.textContent = "Taslak burada gorunecek.";
  draftSources.innerHTML = '<div class="empty">Taslak icin kullanilan referans pasajlar burada listelenecek.</div>';
  draftMeta.textContent = "Taslak uretilmedi.";
  lastDraftPayload = null;
  lastDraftData = null;
  selectedDraftDocumentIds = [];
  draftCopyButton.disabled = true;
  draftPdfButton.disabled = true;
}

picker.addEventListener("change", () => {
  selectedFiles = Array.from(picker.files || []);
  renderFiles();
  renderUploadResults([]);
  if (selectedFiles.length > 0) {
    setStatus("ok", "Raporlar secildi. Yuklemeyi baslatabilirsin.");
  }
});

catalogPicker.addEventListener("change", () => {
  selectedCatalogFile = (catalogPicker.files && catalogPicker.files[0]) ? catalogPicker.files[0] : null;
  if (!selectedCatalogFile) {
    catalogSummary.textContent = "Henuz katalog dosyasi secilmedi.";
    return;
  }
  catalogSummary.textContent = `Secilen katalog: ${selectedCatalogFile.name}`;
  setCatalogStatus("ok", "Katalog secildi. Istersen simdi yukleyebilirsin.");
});

uploadButton.addEventListener("click", async () => {
  const supported = selectedFiles.filter(file => {
    const lower = file.name.toLowerCase();
    return lower.endsWith(".pdf") || lower.endsWith(".docx") || lower.endsWith(".pptx");
  });

  if (supported.length === 0) {
    setStatus("error", "Yuklemek icin en az bir PDF, DOCX veya PPTX sec.");
    return;
  }

  const formData = new FormData();
  supported.forEach(file => formData.append("files", file, file.name));

  uploadButton.disabled = true;
  const startedAt = startTimer(
    message => setStatus("ok", message),
    supported.length === 1 ? "Rapor yukleniyor..." : "Raporlar yukleniyor..."
  );

  try {
    const response = await fetch("/ingest/batch", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    renderUploadResults(data.items || []);
    if (response.ok) {
      stopTimer(
        startedAt,
        message => setStatus("ok", message),
        `Yukleme tamamlandi. Yeni: ${data.ingested_count}, zaten mevcut: ${data.duplicate_count}, hata: ${data.error_count}.`
      );
      if (activeModule && activeModule.dataset.moduleKey === "upload") {
        await refreshUploadedDocuments();
      }
    } else {
      stopTimer(startedAt, message => setStatus("error", message), data.detail || "Yukleme basarisiz oldu.");
    }
  } catch (error) {
    stopTimer(startedAt, message => setStatus("error", message), `Istek basarisiz oldu: ${error}`);
  } finally {
    uploadButton.disabled = false;
  }
});

catalogImportButton.addEventListener("click", async () => {
  if (!selectedCatalogFile) {
    setCatalogStatus("error", "Yuklemek icin once katalog dosyasi sec.");
    return;
  }
  const lower = selectedCatalogFile.name.toLowerCase();
  if (!(lower.endsWith(".xlsx") || lower.endsWith(".csv") || lower.endsWith(".tsv") || lower.endsWith(".txt"))) {
    setCatalogStatus("error", "Sadece XLSX, CSV, TSV veya TXT katalog dosyasi desteklenir.");
    return;
  }

  const formData = new FormData();
  formData.append("file", selectedCatalogFile, selectedCatalogFile.name);
  catalogImportButton.disabled = true;
  const startedAt = startTimer(message => setCatalogStatus("ok", message), "Katalog yukleniyor...");

  try {
    const response = await fetch("/catalog/import", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    setCatalogLog(data);
    if (response.ok) {
      stopTimer(
        startedAt,
        message => setCatalogStatus("ok", message),
      `Katalog yuklendi. ${data.created_count} yeni kayit, ${data.updated_count || 0} guncellenen path, ${data.duplicate_count} duplicate.`
    );
      await refreshCatalogTable();
    } else {
      stopTimer(startedAt, message => setCatalogStatus("error", message), data.detail || "Katalog yukleme basarisiz oldu.");
    }
  } catch (error) {
    stopTimer(startedAt, message => setCatalogStatus("error", message), `Istek basarisiz oldu: ${error}`);
  } finally {
    catalogImportButton.disabled = false;
  }
});

searchButton.addEventListener("click", runSearch);
chatSendButton.addEventListener("click", sendChatMessage);
chatClearButton.addEventListener("click", resetChat);
chatRetrievalVersion.addEventListener("change", () => {
  const selectedLabel = chatRetrievalVersion.value === "v1" ? "RAG v1 (Klasik)" : "RAG v2 (Beta)";
  resetChat();
  chatStatus.textContent = `${selectedLabel} secildi. Yeni sohbet baglami hazir.`;
});
chatPromptButtons.forEach(button => {
  button.addEventListener("click", () => {
    chatInput.value = button.dataset.chatPrompt || "";
    chatInput.focus();
  });
});
chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendChatMessage();
  }
});
duplicateScanButton.addEventListener("click", runDuplicateScan);
duplicateRefreshButton.addEventListener("click", refreshDuplicates);
duplicateCandidatesTab.addEventListener("click", () => setDuplicateWorkspace("candidates"));
reportComparisonTab.addEventListener("click", () => setDuplicateWorkspace("comparison"));
comparisonLeftSelect.addEventListener("change", () => {
  updateComparisonSourceMeta(comparisonLeftSelect, comparisonLeftMeta);
});
comparisonRightSelect.addEventListener("change", () => {
  updateComparisonSourceMeta(comparisonRightSelect, comparisonRightMeta);
});
comparisonLeftUpload.addEventListener("change", () => {
  uploadComparisonSource("left", comparisonLeftUpload);
});
comparisonRightUpload.addEventListener("change", () => {
  uploadComparisonSource("right", comparisonRightUpload);
});
comparisonSwapButton.addEventListener("click", swapComparisonSources);
comparisonRunButton.addEventListener("click", runReportComparison);
comparisonSimilaritiesTab.addEventListener("click", () => setComparisonResultView("similarities"));
comparisonDifferencesTab.addEventListener("click", () => setComparisonResultView("differences"));
[comparisonSimilarities, comparisonDifferences].forEach(container => {
  container.addEventListener("click", event => {
    const button = event.target.closest("[data-comparison-focus]");
    if (!button) return;
    focusComparisonPdf(button.dataset.comparisonFocus);
  });
});
[comparisonLeftPdfOpen, comparisonRightPdfOpen].forEach(button => {
  button.addEventListener("click", () => {
    const url = button.dataset.url;
    if (url) window.open(url, "_blank", "noopener,noreferrer");
  });
});
comparisonPairFullscreenOpen.addEventListener("click", () => {
  const url = comparisonPairFullscreenOpen.dataset.url;
  if (url) window.open(url, "_blank", "noopener,noreferrer");
});
searchQuery.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    runSearch();
  }
});
askButton.addEventListener("click", runAsk);
askQuestion.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    runAsk();
  }
});
catalogAskButton.addEventListener("click", runCatalogAsk);
catalogTableRefreshButton.addEventListener("click", refreshCatalogTable);
catalogSelectedIngestButton.addEventListener("click", ingestSelectedCatalogRows);
catalogEmbeddingRebuildButton.addEventListener("click", rebuildCatalogEmbeddings);
catalogPendingTable.addEventListener("click", (event) => {
  const previewButton = event.target.closest("[data-catalog-preview]");
  if (previewButton) {
    event.preventDefault();
    openCatalogPreview(Number(previewButton.dataset.catalogPreview));
    return;
  }
  const ingestButton = event.target.closest("[data-catalog-ingest-candidate]");
  if (ingestButton) {
    event.preventDefault();
    ingestCatalogCandidate(
      Number(ingestButton.dataset.catalogIngestCandidate),
      ingestButton.dataset.filePath || ""
    );
  }
});
uploadedDocumentsRefreshButton.addEventListener("click", refreshUploadedDocuments);
graphRefreshButton.addEventListener("click", refreshGraph);
graphSearchInput.addEventListener("input", () => {
  graphState.search = graphSearchInput.value;
  renderGraphDocuments();
});
graphCategoryFilter.addEventListener("change", () => {
  graphState.selectedCategoryId = graphCategoryFilter.value || "all";
  renderGraphBrowser();
});
catalogQuestion.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    runCatalogAsk();
  }
});
multiDocumentAskButton.addEventListener("click", runMultiDocumentAsk);
multiDocumentQuestion.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    runMultiDocumentAsk();
  }
});
document.querySelectorAll("[data-expand-module]").forEach(button => {
  button.addEventListener("click", () => {
    const section = button.closest(".section");
    if (section) {
      if (section.classList.contains("module-expanded")) {
        closeModule();
      } else {
        openModule(section);
      }
    }
  });
});
moduleFilterButtons.forEach(button => {
  button.addEventListener("click", () => {
    applyModuleFilter(button.dataset.moduleFilter);
  });
});
moduleModalClose.addEventListener("click", closeModule);
moduleModal.addEventListener("click", (event) => {
  if (event.target === moduleModal) {
    closeModule();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && activeModule) {
    closeModule();
  }
});
draftTitle.addEventListener("input", () => {
  updateDraftReportNoAuto(false);
});
draftReportNo.addEventListener("input", () => {
  if (draftReportNo.value.trim() !== lastAutoReportNo) {
    lastAutoReportNo = "";
  }
});
draftQuickButton.addEventListener("click", () => runDraft("quick"));
draftDetailedButton.addEventListener("click", () => runDraft("detailed"));
draftSampleButton.addEventListener("click", fillDraftSample);
draftClearButton.addEventListener("click", clearDraftForm);
draftCopyButton.addEventListener("click", copyDraftText);
draftPdfButton.addEventListener("click", downloadLatestDraftPdf);
ensureDraftDefaults();
updateCatalogScope([], "");
resetMultiDocumentWorkspace();
resetChat();
applyModuleFilter("upload");

function openDocumentFile(documentId) {
  window.open(`/documents/${documentId}/file`, "_blank");
}
window.openDocumentFile = openDocumentFile;

/* ------------------------------------------------------------------ *
 * App metadata, previously server-interpolated into the page as the
 * __APP_VERSION__ / __MODEL_LABEL__ placeholders. Fetched at runtime so
 * index.html stays a static, cacheable file.
 * ------------------------------------------------------------------ */
async function loadAppMeta() {
  try {
    const response = await fetch("/meta");
    if (!response.ok) return;
    const meta = await response.json();
    const versionPill = document.getElementById("app-version-pill");
    const modelPill = document.getElementById("app-model-pill");
    if (versionPill && meta.version) versionPill.textContent = `v${meta.version}`;
    if (modelPill && meta.model) modelPill.textContent = `model: ${meta.model}`;
  } catch (error) {
    console.warn("App metadata unavailable", error);
  }
}
loadAppMeta();
