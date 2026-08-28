(() => {
  const skillCopy = {
    search: {
      title: "Akıllı Arama",
      copy: "Doküman havuzunu kaynak, sayfa ve pasaj düzeyinde tarar; doğru kanıtı öne çıkarır."
    },
    writing: {
      title: "Doküman Hazırlama",
      copy: "Kurumsal şablonları ve geçmiş içerikleri kullanarak izlenebilir ilk taslaklar üretir."
    },
    summary: {
      title: "Teknik Özet",
      copy: "Uzun mühendislik dokümanlarını karar, bulgu, risk ve aksiyon başlıklarına ayırır."
    },
    memory: {
      title: "Kurumsal Hafıza",
      copy: "Dağınık dokümanları kalıcı ve aranabilir bir ekip hafızasına dönüştürür."
    },
    citation: {
      title: "Kaynak İzleme",
      copy: "Her cevabın hangi belge, sayfa ve pasajdan geldiğini görünür tutar."
    },
    compare: {
      title: "Karşılaştırma",
      copy: "İki dokümanın bulgularını, şartlarını ve değişen teknik kararlarını yan yana getirir."
    },
    category: {
      title: "Sınıflandırma",
      copy: "Belgeleri araç, test, sistem ve mühendislik disiplinine göre düzenler."
    },
    qa: {
      title: "Soru & Cevap",
      copy: "Doğal dilde sorulan teknik sorulara yalnızca doğrulanabilir doküman kanıtıyla yanıt verir."
    }
  };

  const colors = ["#25bfc3", "#ef655e", "#9be3d3", "#efc85b", "#ad83ef", "#5fa9ef", "#ef8a83", "#61d390"];
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function setupMenu() {
    const button = document.querySelector("[data-menu-toggle]");
    const links = document.querySelector(".nav-links");
    if (!button || !links) return;

    button.addEventListener("click", () => {
      const open = !links.classList.contains("open");
      links.classList.toggle("open", open);
      button.setAttribute("aria-expanded", String(open));
      button.textContent = open ? "×" : "≡";
    });

    links.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        links.classList.remove("open");
        button.setAttribute("aria-expanded", "false");
        button.textContent = "≡";
      });
    });
  }

  function setupReveal() {
    const elements = [...document.querySelectorAll(".reveal")];
    if (!elements.length) return;
    if (reducedMotion || !("IntersectionObserver" in window)) {
      elements.forEach((element) => element.classList.add("visible"));
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.12 });
    elements.forEach((element) => observer.observe(element));
  }

  function setupHeroVideo() {
    const video = document.querySelector(".hero-video");
    if (!video) return;

    video.muted = true;
    video.playsInline = true;
    video.addEventListener("playing", () => video.removeAttribute("poster"), { once: true });

    const startPlayback = () => {
      const playback = video.play();
      if (playback && typeof playback.catch === "function") playback.catch(() => {});
    };

    startPlayback();
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && video.paused) startPlayback();
    });
  }

  function setupCounters() {
    const counters = [...document.querySelectorAll("[data-count]")];
    if (!counters.length) return;
    const animate = (element) => {
      const target = Number(element.dataset.count || 0);
      const suffix = element.dataset.suffix || "";
      if (reducedMotion) {
        element.textContent = `${target}${suffix}`;
        return;
      }
      const startedAt = performance.now();
      const duration = 900;
      const step = (now) => {
        const progress = Math.min(1, (now - startedAt) / duration);
        const eased = 1 - Math.pow(1 - progress, 3);
        element.textContent = `${Math.round(target * eased)}${suffix}`;
        if (progress < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    };

    if (!("IntersectionObserver" in window)) {
      counters.forEach(animate);
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        animate(entry.target);
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.7 });
    counters.forEach((counter) => observer.observe(counter));
  }

  function setupHeroParallax() {
    const hero = document.querySelector(".hero");
    if (!hero || reducedMotion || window.matchMedia("(max-width: 680px)").matches) return;
    hero.addEventListener("pointermove", (event) => {
      const rect = hero.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width - 0.5) * -10;
      const y = ((event.clientY - rect.top) / rect.height - 0.5) * -7;
      hero.style.setProperty("--hero-shift-x", `${x}px`);
      hero.style.setProperty("--hero-shift-y", `${y}px`);
    });
    hero.addEventListener("pointerleave", () => {
      hero.style.setProperty("--hero-shift-x", "0px");
      hero.style.setProperty("--hero-shift-y", "0px");
    });
  }

  function setupSkillDetails() {
    document.querySelectorAll("[data-skill]").forEach((node) => {
      const activate = () => {
        const stage = node.closest("[data-tentacle-stage]") || document;
        stage.querySelectorAll("[data-skill]").forEach((item) => item.classList.remove("active"));
        node.classList.add("active");
        stage.dataset.activeSkill = node.dataset.skill || "";
        const detail = stage.querySelector("[data-skill-detail]");
        const data = skillCopy[node.dataset.skill];
        if (detail && data) {
          const title = detail.querySelector("strong");
          const copy = detail.querySelector("p");
          if (title) title.textContent = data.title;
          if (copy) copy.textContent = data.copy;
        }
      };
      node.addEventListener("pointerenter", activate);
      node.addEventListener("focus", activate);
      node.addEventListener("click", activate);
    });
  }

  function setupTentacleStage(stage) {
    const canvas = stage.querySelector(".tentacle-canvas");
    const nodes = [...stage.querySelectorAll("[data-skill]")];
    if (!canvas || !nodes.length) return;

    const context = canvas.getContext("2d");
    const pointer = { x: 0, y: 0, inside: false };
    let width = 0;
    let height = 0;
    let ratio = 1;
    let frame = 0;
    let lastDrawAt = 0;

    const resize = () => {
      const rect = stage.getBoundingClientRect();
      width = Math.max(1, rect.width);
      height = Math.max(1, rect.height);
      ratio = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      draw(performance.now());
    };

    const origin = () => {
      const core = stage.querySelector(".octo-core");
      const stageRect = stage.getBoundingClientRect();
      if (core && getComputedStyle(core).display !== "none") {
        const coreRect = core.getBoundingClientRect();
        return {
          x: coreRect.left - stageRect.left + coreRect.width / 2,
          y: coreRect.top - stageRect.top + coreRect.height / 2
        };
      }
      return {
        x: width * Number(stage.dataset.originX || 0.68),
        y: height * Number(stage.dataset.originY || 0.52)
      };
    };

    const drawTentacle = (start, end, index, active, now) => {
      const dx = end.x - start.x;
      const dy = end.y - start.y;
      const length = Math.max(1, Math.hypot(dx, dy));
      const normalX = -dy / length;
      const normalY = dx / length;
      const curlDirection = index % 2 === 0 ? 1 : -1;
      const baseCurl = curlDirection * Math.min(active ? 104 : 88, length * (active ? 0.24 : 0.2));
      const wave = reducedMotion ? 0 : Math.sin(now / 720 + index * 0.84) * (active ? 13 : 7);
      const pointerPull = pointer.inside ? ((pointer.x - width / 2) / Math.max(width, 1)) * 16 : 0;
      const bend = baseCurl + wave + pointerPull;
      const controlA = {
        x: start.x + dx * 0.3 + normalX * bend,
        y: start.y + dy * 0.3 + normalY * bend
      };
      const controlB = {
        x: start.x + dx * 0.72 - normalX * bend * 0.68,
        y: start.y + dy * 0.72 - normalY * bend * 0.68
      };
      const color = colors[index % colors.length];

      const pointAt = (t) => {
        const mt = 1 - t;
        return {
          x: mt ** 3 * start.x + 3 * mt ** 2 * t * controlA.x + 3 * mt * t ** 2 * controlB.x + t ** 3 * end.x,
          y: mt ** 3 * start.y + 3 * mt ** 2 * t * controlA.y + 3 * mt * t ** 2 * controlB.y + t ** 3 * end.y
        };
      };
      const tangentAt = (t) => {
        const mt = 1 - t;
        return {
          x: 3 * mt ** 2 * (controlA.x - start.x) + 6 * mt * t * (controlB.x - controlA.x) + 3 * t ** 2 * (end.x - controlB.x),
          y: 3 * mt ** 2 * (controlA.y - start.y) + 6 * mt * t * (controlB.y - controlA.y) + 3 * t ** 2 * (end.y - controlB.y)
        };
      };
      const halfWidthAt = (t) => {
        const base = active ? 27 : 23;
        const tip = active ? 7 : 5.5;
        const taper = Math.pow(1 - t, 0.72);
        return tip + (base - tip) * taper;
      };

      const samples = Array.from({ length: 37 }, (_, sampleIndex) => {
        const t = sampleIndex / 36;
        const point = pointAt(t);
        const tangent = tangentAt(t);
        const tangentLength = Math.max(1, Math.hypot(tangent.x, tangent.y));
        const localNormal = { x: -tangent.y / tangentLength, y: tangent.x / tangentLength };
        const organicRipple = reducedMotion
          ? 0
          : Math.sin(now / 880 + index * 1.31 + t * Math.PI * 2.4) * (active ? 4 : 2.6) * Math.sin(Math.PI * t);
        return {
          t,
          x: point.x + localNormal.x * organicRipple,
          y: point.y + localNormal.y * organicRipple,
          normalX: localNormal.x,
          normalY: localNormal.y,
          tangentAngle: Math.atan2(tangent.y, tangent.x),
          halfWidth: halfWidthAt(t)
        };
      });

      const traceBody = () => {
        context.beginPath();
        samples.forEach((sample, sampleIndex) => {
          const x = sample.x + sample.normalX * sample.halfWidth;
          const y = sample.y + sample.normalY * sample.halfWidth;
          if (sampleIndex === 0) context.moveTo(x, y);
          else context.lineTo(x, y);
        });
        [...samples].reverse().forEach((sample) => {
          context.lineTo(
            sample.x - sample.normalX * sample.halfWidth,
            sample.y - sample.normalY * sample.halfWidth
          );
        });
        context.closePath();
      };

      context.save();
      context.translate(0, active ? 6 : 4);
      traceBody();
      context.fillStyle = active ? "rgba(8, 3, 14, 0.52)" : "rgba(8, 3, 14, 0.38)";
      context.fill();
      context.restore();

      traceBody();
      const bodyGradient = context.createLinearGradient(start.x, start.y, end.x, end.y);
      bodyGradient.addColorStop(0, active ? "#a36bc3" : "#81549a");
      bodyGradient.addColorStop(0.54, active ? "#8750a8" : "#6c4382");
      bodyGradient.addColorStop(1, active ? "#72438f" : "#563269");
      context.fillStyle = bodyGradient;
      context.fill();
      context.strokeStyle = active ? "rgba(225, 189, 239, 0.58)" : "rgba(202, 164, 219, 0.3)";
      context.lineWidth = active ? 1.8 : 1.2;
      context.stroke();

      context.beginPath();
      context.moveTo(start.x, start.y);
      context.bezierCurveTo(controlA.x, controlA.y, controlB.x, controlB.y, end.x, end.y);
      context.strokeStyle = active ? "rgba(248, 220, 252, 0.68)" : "rgba(229, 202, 239, 0.28)";
      context.globalAlpha = active ? 0.78 : 0.52;
      context.lineWidth = active ? 3.6 : 2.2;
      context.lineCap = "round";
      context.stroke();
      context.globalAlpha = 1;

      const suckerSide = dx >= 0 ? 1 : -1;
      const suckerCount = active ? 8 : 6;
      for (let suckerIndex = 0; suckerIndex < suckerCount; suckerIndex += 1) {
        const t = 0.28 + suckerIndex * (0.55 / Math.max(1, suckerCount - 1));
        const sample = samples[Math.round(t * 36)];
        const radius = (active ? 4.1 : 3.4) * (1 - t * 0.38);
        const offset = sample.halfWidth * 0.58 * suckerSide;
        context.save();
        context.translate(
          sample.x + sample.normalX * offset,
          sample.y + sample.normalY * offset
        );
        context.rotate(sample.tangentAngle);
        context.beginPath();
        context.ellipse(0, 0, radius * 1.18, radius * 0.72, 0, 0, Math.PI * 2);
        context.fillStyle = active ? "rgba(249, 203, 221, 0.9)" : "rgba(232, 187, 207, 0.66)";
        context.fill();
        context.beginPath();
        context.ellipse(0, 0, radius * 0.52, radius * 0.31, 0, 0, Math.PI * 2);
        context.fillStyle = active ? "rgba(87, 44, 105, 0.86)" : "rgba(69, 37, 82, 0.68)";
        context.fill();
        context.restore();
      }

      if (active) {
        const pulse = reducedMotion ? 4 : 4 + Math.sin(now / 180) * 1.5;
        context.beginPath();
        context.arc(end.x, end.y, pulse, 0, Math.PI * 2);
        context.fillStyle = color;
        context.fill();
      }
    };

    const draw = (now) => {
      if (!width || !height) return;
      context.clearRect(0, 0, width, height);
      if (window.matchMedia("(max-width: 980px)").matches && stage.classList.contains("capability-stage")) return;
      const start = origin();
      const stageRect = stage.getBoundingClientRect();
      const orderedNodes = nodes
        .map((node, index) => ({ node, index }))
        .sort((left, right) => Number(left.node.classList.contains("active")) - Number(right.node.classList.contains("active")));
      orderedNodes.forEach(({ node, index }) => {
        if (getComputedStyle(node).display === "none") return;
        const rect = node.getBoundingClientRect();
        const end = {
          x: rect.left - stageRect.left + rect.width / 2,
          y: rect.top - stageRect.top + rect.height / 2
        };
        drawTentacle(start, end, index, node.classList.contains("active"), now);
      });
    };

    const tick = (now) => {
      if (now - lastDrawAt >= 33) {
        draw(now);
        lastDrawAt = now;
      }
      frame = requestAnimationFrame(tick);
    };

    stage.addEventListener("pointermove", (event) => {
      const rect = stage.getBoundingClientRect();
      pointer.x = event.clientX - rect.left;
      pointer.y = event.clientY - rect.top;
      pointer.inside = true;
    });
    stage.addEventListener("pointerleave", () => {
      pointer.inside = false;
    });

    const observer = new ResizeObserver(resize);
    observer.observe(stage);
    resize();
    if (!reducedMotion) frame = requestAnimationFrame(tick);
    else draw(performance.now());

    window.addEventListener("pagehide", () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    }, { once: true });
  }

  function setupProductTabs() {
    const tabs = [...document.querySelectorAll("[data-repocto-tab]")];
    const panels = [...document.querySelectorAll("[data-repocto-panel]")];
    if (!tabs.length || !panels.length) return;

    const activate = (tab, focus = false) => {
      const target = tab.dataset.repoctoTab;
      tabs.forEach((item) => {
        const active = item === tab;
        item.setAttribute("aria-selected", String(active));
        item.tabIndex = active ? 0 : -1;
      });
      panels.forEach((panel) => {
        const active = panel.dataset.repoctoPanel === target;
        panel.hidden = !active;
        panel.classList.toggle("active-panel", active);
      });
      if (focus) tab.focus();
    };

    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => activate(tab));
      tab.addEventListener("keydown", (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        let next = index;
        if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
        if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = tabs.length - 1;
        activate(tabs[next], true);
      });
    });
  }

  function setupMemoryExplorer() {
    const explorer = document.querySelector("[data-memory-explorer]");
    if (!explorer) return;
    const filters = [...explorer.querySelectorAll("[data-memory-filter]")];
    const records = [...explorer.querySelectorAll("[data-memory-record]")];
    const detail = explorer.querySelector("[data-memory-detail]");

    const showRecord = (record) => {
      records.forEach((item) => item.classList.toggle("active", item === record));
      if (!detail || !record) return;
      const fields = {
        code: record.dataset.code,
        title: record.dataset.title,
        study: record.dataset.study,
        person: record.dataset.person,
        year: record.dataset.year,
        confidence: record.dataset.confidence
      };
      Object.entries(fields).forEach(([key, value]) => {
        const output = detail.querySelector(`[data-memory-${key}]`);
        if (output) output.textContent = value || "-";
      });
    };

    filters.forEach((filter) => {
      filter.addEventListener("click", () => {
        const category = filter.dataset.memoryFilter;
        filters.forEach((item) => item.classList.toggle("active", item === filter));
        records.forEach((record) => {
          record.hidden = category !== "all" && record.dataset.category !== category;
        });
        const visible = records.find((record) => !record.hidden);
        if (visible) showRecord(visible);
      });
    });
    records.forEach((record) => record.addEventListener("click", () => showRecord(record)));
  }

  function setupEdgeTentacles() {
    if (reducedMotion) return;
    document.querySelectorAll(".tentacle-zone").forEach((zone) => {
      const tentacles = [...zone.querySelectorAll(".edge-tentacle")];
      if (!tentacles.length) return;
      zone.addEventListener("pointermove", (event) => {
        const rect = zone.getBoundingClientRect();
        const x = ((event.clientX - rect.left) / rect.width - 0.5) * 12;
        const y = ((event.clientY - rect.top) / rect.height - 0.5) * 10;
        tentacles.forEach((tentacle, index) => {
          tentacle.style.setProperty("--tentacle-shift-x", `${x * (index + 1)}px`);
          tentacle.style.setProperty("--tentacle-shift-y", `${y * (index + 1)}px`);
        });
      });
      zone.addEventListener("pointerleave", () => {
        tentacles.forEach((tentacle) => {
          tentacle.style.setProperty("--tentacle-shift-x", "0px");
          tentacle.style.setProperty("--tentacle-shift-y", "0px");
        });
      });
    });
  }

  setupMenu();
  setupHeroVideo();
  setupReveal();
  setupCounters();
  setupHeroParallax();
  setupSkillDetails();
  setupProductTabs();
  setupMemoryExplorer();
  setupEdgeTentacles();
  document.querySelectorAll("[data-tentacle-stage]").forEach(setupTentacleStage);
})();
