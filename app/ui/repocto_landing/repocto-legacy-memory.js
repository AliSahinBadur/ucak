(() => {
  const scriptUrl = document.currentScript?.src || document.baseURI;
  const wordmarkUrl = new URL("assets/repocto-wordmark.png", scriptUrl).href;
  const documents = [
    {
      id: "big-e-dur-01",
      title: "2025-BIG-E-DUR-01",
      subtitle: "Detay stok regalleri statik analiz dokümanı",
      work: "BIG-E",
      topic: "Dayanım",
      year: "2025",
      person: "Ali Şahin",
      type: "PDF",
      confidence: 96,
      path: "V:\\DOKÜMANLAR\\BIG-E\\2025-BIG-E-DUR-01\\2025-BIG-E-DUR-01.pdf",
      reason: "Kapak kodu, statik analiz başlığı ve dayanım sonuçları aynı sınıfı destekliyor.",
      evidence: ["Dosya adı: BIG-E + DUR", "Kapak alanı: Hazırlayan - Ali Şahin", "Başlıklar: Statik Analiz, Sonuçlar"]
    },
    {
      id: "big-e-test-13",
      title: "2025-BIG-E-TEST-13",
      subtitle: "Konfor parkuru test dokümanı",
      work: "BIG-E",
      topic: "Konfor",
      year: "2025",
      person: "Ece Demir",
      type: "PDF",
      confidence: 93,
      path: "V:\\DOKÜMANLAR\\BIG-E\\2025-BIG-E-TEST-13\\2025-BIG-E-TEST-13.pdf",
      reason: "Parkur adları, ivme ölçümleri ve sürüş konforu ifadeleri birlikte değerlendirildi.",
      evidence: ["Dosya adı: BIG-E + TEST", "Kapak alanı: Hazırlayan - Ece Demir", "İçerik: parkur, ivme, konfor"]
    },
    {
      id: "big-e-therm-03",
      title: "2023-BIG-E-THERM-03",
      subtitle: "İnverter termal analiz çalışması",
      work: "BIG-E",
      topic: "Termal",
      year: "2023",
      person: "Selin Yılmaz",
      type: "DOCX",
      confidence: 91,
      path: "V:\\DOKÜMANLAR\\BIG-E\\TERMAL\\2023-BIG-E-THERM-03.docx",
      reason: "Sıcaklık, inverter ve termal limit ifadeleri konu kümesiyle güçlü biçimde eşleşiyor.",
      evidence: ["Belge özelliği: Yazar - Selin Yılmaz", "Başlık: Termal Analiz", "İçerik: °C, sıcaklık limiti"]
    },
    {
      id: "citibus-dur-04",
      title: "2024-CITIBUS-DUR-04",
      subtitle: "Tutma kolu dayanım analizi",
      work: "CITIBUS",
      topic: "Dayanım",
      year: "2024",
      person: "Ali Şahin",
      type: "PPTX",
      confidence: 89,
      path: "V:\\DOKÜMANLAR\\CITIBUS\\DAYANIM\\2024-CITIBUS-DUR-04.pptx",
      reason: "Tutma kolu, yük, deformasyon ve emniyet katsayısı kavramları dayanım dalını işaret ediyor.",
      evidence: ["Dosya adı: CITIBUS + DUR", "Sunum yazarı: Ali Şahin", "İçerik: yük, deformasyon, FOS"]
    },
    {
      id: "citiport-nvh-02",
      title: "2026-CITIPORT-NVH-02",
      subtitle: "Yol testi gürültü ve titreşim sonuçları",
      work: "CITIPORT",
      topic: "NVH",
      year: "2026",
      person: "Can Kaya",
      type: "PDF",
      confidence: 95,
      path: "V:\\DOKÜMANLAR\\CITIPORT\\NVH\\2026-CITIPORT-NVH-02.pdf",
      reason: "dB(A), titreşim, frekans ve yol testi sinyalleri NVH taksonomisiyle eşleşiyor.",
      evidence: ["Kapak kodu: CITIPORT + NVH", "Hazırlayan: Can Kaya", "İçerik: dB(A), Hz, titreşim"]
    },
    {
      id: "13m-weight",
      title: "13M_Ağırlıkdağılımı_Dokümanı",
      subtitle: "Aks ve tekerlek yük dağılımı",
      work: "13M",
      topic: "Ağırlık Dağılımı",
      year: "2024",
      person: "Belgede bulunamadı",
      type: "DOCX",
      confidence: 68,
      path: "V:\\DOKÜMANLAR\\13M\\HESAPLAR\\13M_Ağırlıkdağılımı_Dokümanı.docx",
      reason: "Konu içerikten çıkarıldı; kişi bilgisi belge özelliklerinde ve kapakta bulunamadı.",
      evidence: ["Dosya adı: 13M + Ağırlık dağılımı", "İçerik: aks yükü, tekerlek kuvveti", "Eksik alan: Hazırlayan"]
    }
  ];

  const escapeHtml = (value) => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const unique = (field) => [...new Set(documents.map((item) => item[field]))]
    .sort((a, b) => String(a).localeCompare(String(b), "tr"));

  const groupBy = (items, field) => items.reduce((groups, item) => {
    const key = item[field];
    if (!groups[key]) groups[key] = [];
    groups[key].push(item);
    return groups;
  }, {});

  function explorerMarkup() {
    return `
      <section class="mx-app" aria-label="Etkileşimli kurumsal hafıza ağacı">
        <header class="mx-topbar">
          <div class="mx-brand">
            <img class="mx-brand-logo" src="${escapeHtml(wordmarkUrl)}" alt="RepOcto">
            <span class="mx-brand-copy"><strong>RepOcto</strong><span>Kurumsal Hafıza</span></span>
          </div>
          <div class="mx-path-control">
            <label>Kök klasör</label>
            <input type="text" value="V:\\DOKÜMANLAR" aria-label="Taranacak kök klasör yolu" data-memory-path>
            <button type="button" class="mx-button mx-button-primary" data-memory-scan>Tara</button>
          </div>
        </header>

        <div class="mx-pipeline" aria-label="Otomatik işleme adımları">
          <div class="mx-stage"><b class="mx-stage-number">01</b><span><strong>Alt klasörler</strong><span>Özyinelemeli tarama</span></span></div>
          <div class="mx-stage"><b class="mx-stage-number">02</b><span><strong>Metin + OCR</strong><span>İçerik çıkarımı</span></span></div>
          <div class="mx-stage"><b class="mx-stage-number">03</b><span><strong>Metadata</strong><span>Kişi, yıl, çalışma</span></span></div>
          <div class="mx-stage"><b class="mx-stage-number">04</b><span><strong>Taksonomi</strong><span>Otomatik dallanma</span></span></div>
          <div class="mx-stage"><b class="mx-stage-number">05</b><span><strong>Hafıza indeksi</strong><span>Arama + ilişkiler</span></span></div>
        </div>

        <div class="mx-toolbar">
          <div class="mx-view-switch" aria-label="Görünüm seçimi">
            <button type="button" class="mx-view-button" data-memory-view="tree" aria-pressed="true">Ağaç</button>
            <button type="button" class="mx-view-button" data-memory-view="relations" aria-pressed="false">İlişkiler</button>
          </div>
          <div class="mx-filters">
            <label class="mx-filter">Çalışma<select data-memory-filter="work"><option value="">Tümü</option></select></label>
            <label class="mx-filter">Kişi<select data-memory-filter="person"><option value="">Tümü</option></select></label>
            <label class="mx-filter">Yıl<select data-memory-filter="year"><option value="">Tümü</option></select></label>
          </div>
          <div class="mx-toolbar-end">
            <span class="mx-result-count" data-memory-result-count>6 belge</span>
            <button type="button" class="mx-button" data-memory-reset>Temizle</button>
          </div>
        </div>

        <div class="mx-workspace">
          <aside class="mx-pane" aria-label="Otomatik kategori ağacı">
            <div class="mx-pane-header"><strong>Otomatik kategoriler</strong><span data-memory-tree-summary>4 çalışma</span></div>
            <div class="mx-tree" data-memory-tree></div>
          </aside>

          <section class="mx-pane mx-main-view" aria-label="Kurumsal hafıza görünümü">
            <div class="mx-pane-header"><strong data-memory-main-title>Anlamsal ağaç</strong><span data-memory-main-summary>Çalışma → konu → belge</span></div>
            <div class="mx-branch-view" data-memory-branch-view>
              <div class="mx-branch-canvas">
                <div class="mx-root-node">Kurumsal Hafıza</div>
                <div class="mx-branches" data-memory-branches></div>
              </div>
            </div>
            <div class="mx-relations-view" data-memory-relations-view hidden>
              <svg class="mx-relations" data-memory-relations role="img" aria-label="Belgelerin çalışma, kişi ve yıl ilişkileri"></svg>
            </div>
          </section>

          <aside class="mx-pane mx-detail-pane" aria-label="Seçili belge ayrıntıları">
            <div class="mx-pane-header"><strong>Belge profili</strong><span>Otomatik çıkarıldı</span></div>
            <div class="mx-detail-body" data-memory-detail></div>
          </aside>
        </div>
        <div class="mx-status" role="status" aria-live="polite" data-memory-status>Hazır: 6 belge ve 4 çalışma indekslendi.</div>
      </section>`;
  }

  function fillSelect(select, values) {
    values.forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });
  }

  function documentButton(item, state, leaf = false) {
    const selected = item.id === state.selectedId ? " is-selected" : "";
    if (leaf) {
      return `<button type="button" class="mx-leaf${selected}" data-doc-id="${escapeHtml(item.id)}"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.topic)} · ${escapeHtml(item.year)}</span></button>`;
    }
    const low = item.confidence < 75 ? " is-low" : "";
    return `<button type="button" class="mx-document${selected}" data-doc-id="${escapeHtml(item.id)}"><span class="mx-confidence-dot${low}" aria-hidden="true"></span><span class="mx-document-title">${escapeHtml(item.title)}</span><span>${escapeHtml(item.year)}</span></button>`;
  }

  function svgElement(name, attributes = {}) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    return element;
  }

  function svgNode({ x, y, width, label, subtitle = "", className = "", documentId = "" }) {
    const group = svgElement("g", { class: documentId ? "mx-svg-doc" : "" });
    if (documentId) {
      group.dataset.docId = documentId;
      group.setAttribute("role", "button");
      group.setAttribute("tabindex", "0");
      group.setAttribute("aria-label", `${label} belgesini seç`);
    }
    group.appendChild(svgElement("rect", { x, y, width, height: 46, rx: 4, class: `mx-node ${className}` }));
    const title = svgElement("text", { x: x + 10, y: y + 19 });
    title.textContent = label.length > 26 ? `${label.slice(0, 24)}…` : label;
    group.appendChild(title);
    if (subtitle) {
      const sub = svgElement("text", { x: x + 10, y: y + 35, class: "mx-svg-muted" });
      sub.textContent = subtitle.length > 28 ? `${subtitle.slice(0, 26)}…` : subtitle;
      group.appendChild(sub);
    }
    return group;
  }

  function initializeExplorer(root) {
    root.innerHTML = explorerMarkup();

    const state = { work: "", person: "", year: "", selectedId: documents[0].id, view: "tree" };
    const tree = root.querySelector("[data-memory-tree]");
    const branches = root.querySelector("[data-memory-branches]");
    const detail = root.querySelector("[data-memory-detail]");
    const relations = root.querySelector("[data-memory-relations]");
    const resultCount = root.querySelector("[data-memory-result-count]");
    const treeSummary = root.querySelector("[data-memory-tree-summary]");
    const mainTitle = root.querySelector("[data-memory-main-title]");
    const mainSummary = root.querySelector("[data-memory-main-summary]");
    const status = root.querySelector("[data-memory-status]");
    const filters = [...root.querySelectorAll("[data-memory-filter]")];

    fillSelect(root.querySelector('[data-memory-filter="work"]'), unique("work"));
    fillSelect(root.querySelector('[data-memory-filter="person"]'), unique("person"));
    fillSelect(root.querySelector('[data-memory-filter="year"]'), unique("year").sort((a, b) => Number(b) - Number(a)));

    const filteredDocuments = () => documents.filter((item) =>
      (!state.work || item.work === state.work) &&
      (!state.person || item.person === state.person) &&
      (!state.year || item.year === state.year)
    );

    function renderTree(items) {
      const works = groupBy(items, "work");
      tree.innerHTML = Object.entries(works)
        .sort(([a], [b]) => a.localeCompare(b, "tr"))
        .map(([work, workItems]) => {
          const topics = groupBy(workItems, "topic");
          const topicMarkup = Object.entries(topics)
            .sort(([a], [b]) => a.localeCompare(b, "tr"))
            .map(([topic, topicItems]) => `
              <details open>
                <summary><strong>${escapeHtml(topic)}</strong><span class="mx-count">${topicItems.length}</span></summary>
                <div class="mx-tree-level">${topicItems
                  .sort((a, b) => Number(b.year) - Number(a.year))
                  .map((item) => documentButton(item, state))
                  .join("")}</div>
              </details>`).join("");
          return `<details open><summary><strong>${escapeHtml(work)}</strong><span class="mx-count">${workItems.length}</span></summary><div class="mx-tree-level">${topicMarkup}</div></details>`;
        }).join("");
      if (!items.length) tree.innerHTML = '<div class="mx-empty">Bu filtrelerle eşleşen belge yok.</div>';
    }

    function renderBranches(items) {
      branches.innerHTML = Object.entries(groupBy(items, "work"))
        .sort(([a], [b]) => a.localeCompare(b, "tr"))
        .map(([work, workItems]) => `
          <section class="mx-branch">
            <div class="mx-branch-title">${escapeHtml(work)} · ${workItems.length}</div>
            <div class="mx-branch-list">${workItems.map((item) => documentButton(item, state, true)).join("")}</div>
          </section>`).join("");
      if (!items.length) branches.innerHTML = '<div class="mx-empty">Filtreleri değiştirerek ağacı yeniden oluşturun.</div>';
    }

    function renderRelations(items) {
      relations.innerHTML = "";
      const height = Math.max(500, 86 + items.length * 76);
      relations.setAttribute("viewBox", `0 0 900 ${height}`);

      [["ÇALIŞMA", 35], ["BELGE", 320], ["KİŞİ / YIL", 685]].forEach(([label, x]) => {
        const text = svgElement("text", { x, y: 30, class: "mx-svg-muted" });
        text.textContent = label;
        relations.appendChild(text);
      });

      if (!items.length) {
        const empty = svgElement("text", { x: 450, y: 250, "text-anchor": "middle", class: "mx-svg-muted" });
        empty.textContent = "Bu filtrelerle gösterilecek ilişki yok.";
        relations.appendChild(empty);
        return;
      }

      const positions = {};
      items.forEach((item, index) => {
        positions[item.id] = { x: 320, y: 62 + index * 76 };
      });

      const works = groupBy(items, "work");
      const workPositions = {};
      Object.entries(works).forEach(([work, workItems]) => {
        const average = workItems.reduce((sum, item) => sum + positions[item.id].y, 0) / workItems.length;
        workPositions[work] = { x: 35, y: average };
      });

      items.forEach((item) => {
        const work = workPositions[item.work];
        const doc = positions[item.id];
        relations.appendChild(svgElement("line", { x1: work.x + 170, y1: work.y + 23, x2: doc.x, y2: doc.y + 23, class: "mx-edge" }));
        relations.appendChild(svgElement("line", { x1: doc.x + 250, y1: doc.y + 23, x2: 685, y2: doc.y + 23, class: "mx-edge mx-edge-meta" }));
      });

      Object.entries(workPositions).forEach(([work, position]) => {
        relations.appendChild(svgNode({ x: position.x, y: position.y, width: 170, label: work }));
      });

      items.forEach((item) => {
        const position = positions[item.id];
        relations.appendChild(svgNode({ x: position.x, y: position.y, width: 250, label: item.title, subtitle: item.topic, className: "mx-node-doc", documentId: item.id }));
        relations.appendChild(svgNode({ x: 685, y: position.y, width: 180, label: item.person, subtitle: item.year, className: "mx-node-meta" }));
      });
    }

    function renderDetail(item) {
      if (!item) {
        detail.innerHTML = '<div class="mx-empty">Bir belge seçin.</div>';
        return;
      }
      const low = item.confidence < 75;
      detail.innerHTML = `
        <div>
          <p class="mx-detail-title">${escapeHtml(item.title)}</p>
          <p class="mx-detail-path">${escapeHtml(item.path)}</p>
          <dl class="mx-metadata">
            <div><dt>Çalışma</dt><dd>${escapeHtml(item.work)}</dd></div>
            <div><dt>Konu</dt><dd>${escapeHtml(item.topic)}</dd></div>
            <div><dt>Kişi</dt><dd>${escapeHtml(item.person)}</dd></div>
            <div><dt>Yıl</dt><dd>${escapeHtml(item.year)}</dd></div>
            <div><dt>Tür</dt><dd>${escapeHtml(item.type)}</dd></div>
            <div><dt>Güven</dt><dd><span class="mx-score${low ? " is-low" : ""}">%${item.confidence}</span></dd></div>
          </dl>
        </div>
        <div>
          <div class="mx-divider"></div>
          <div class="mx-reason-title">Neden bu kategoride?</div>
          <p class="mx-reason">${escapeHtml(item.reason)}</p>
          <div class="mx-divider"></div>
          <div class="mx-reason-title">Kaynak izleri</div>
          <ul class="mx-evidence-list">${item.evidence.map((text) => `<li>${escapeHtml(text)}</li>`).join("")}</ul>
          ${low ? '<div class="mx-warning">Düşük güven: sınıflandırma korundu, belirsizlik görünür bırakıldı.</div>' : ""}
        </div>`;
    }

    function applyView() {
      const relationsActive = state.view === "relations";
      root.querySelector("[data-memory-branch-view]").hidden = relationsActive;
      root.querySelector("[data-memory-relations-view]").hidden = !relationsActive;
      root.querySelectorAll("[data-memory-view]").forEach((button) => {
        button.setAttribute("aria-pressed", String(button.dataset.memoryView === state.view));
      });
      mainTitle.textContent = relationsActive ? "İlişki ağı" : "Anlamsal ağaç";
      mainSummary.textContent = relationsActive ? "Belge ↔ kişi ↔ yıl" : "Çalışma → konu → belge";
    }

    function renderAll(announce = false) {
      const items = filteredDocuments();
      if (!items.some((item) => item.id === state.selectedId)) state.selectedId = items[0]?.id || "";
      renderTree(items);
      renderBranches(items);
      renderRelations(items);
      renderDetail(items.find((item) => item.id === state.selectedId));
      resultCount.textContent = `${items.length} belge`;
      treeSummary.textContent = `${new Set(items.map((item) => item.work)).size} çalışma`;
      if (announce) status.textContent = `Filtreler uygulandı: ${items.length} belge görüntüleniyor.`;
      applyView();
    }

    root.addEventListener("click", (event) => {
      const documentTarget = event.target.closest("[data-doc-id]");
      if (documentTarget) {
        state.selectedId = documentTarget.dataset.docId;
        renderAll();
        status.textContent = `${documents.find((item) => item.id === state.selectedId)?.title || "Belge"} seçildi.`;
        return;
      }

      const viewButton = event.target.closest("[data-memory-view]");
      if (viewButton) {
        state.view = viewButton.dataset.memoryView;
        applyView();
        status.textContent = state.view === "relations" ? "İlişki görünümü açıldı." : "Ağaç görünümü açıldı.";
      }
    });

    root.addEventListener("keydown", (event) => {
      const documentTarget = event.target.closest("[data-doc-id]");
      if (!documentTarget || (event.key !== "Enter" && event.key !== " ")) return;
      event.preventDefault();
      documentTarget.click();
    });

    filters.forEach((select) => {
      select.addEventListener("change", () => {
        state[select.dataset.memoryFilter] = select.value;
        renderAll(true);
      });
    });

    root.querySelector("[data-memory-reset]").addEventListener("click", () => {
      state.work = "";
      state.person = "";
      state.year = "";
      filters.forEach((select) => { select.value = ""; });
      renderAll();
      status.textContent = "Filtreler temizlendi; tüm belgeler görüntüleniyor.";
    });

    root.querySelector("[data-memory-scan]").addEventListener("click", (event) => {
      const button = event.currentTarget;
      const path = root.querySelector("[data-memory-path]").value.trim() || "Seçilen klasör";
      button.disabled = true;
      button.textContent = "Taranıyor...";
      status.textContent = `${path} altındaki klasörler ve belgeler taranıyor.`;
      window.setTimeout(() => {
        button.textContent = "Tamamlandı";
        status.textContent = `Tarama tamamlandı: ${documents.length} belge, ${unique("work").length} çalışma ve ${unique("person").length} kişi bulundu.`;
        window.setTimeout(() => {
          button.disabled = false;
          button.textContent = "Tara";
        }, 1100);
      }, 800);
    });

    renderAll();
  }

  document.querySelectorAll("[data-memory-explorer]").forEach(initializeExplorer);
})();
