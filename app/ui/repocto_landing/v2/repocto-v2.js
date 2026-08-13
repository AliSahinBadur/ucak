(() => {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const octopusMaps = [];
  const featureKeys = ["search", "qa", "citation", "summary", "compare", "category", "memory", "writing"];

  function setupMenu() {
    const button = document.querySelector("[data-menu-toggle]");
    const nav = document.querySelector("[data-site-nav]");
    const header = document.querySelector("[data-site-header]");
    if (!button || !nav || !header) return;

    const close = () => {
      nav.classList.remove("open");
      header.classList.remove("menu-visible");
      document.body.classList.remove("menu-open");
      button.setAttribute("aria-expanded", "false");
      button.textContent = "Menü";
    };

    button.addEventListener("click", () => {
      const open = !nav.classList.contains("open");
      nav.classList.toggle("open", open);
      header.classList.toggle("menu-visible", open);
      document.body.classList.toggle("menu-open", open);
      button.setAttribute("aria-expanded", String(open));
      button.textContent = open ? "Kapat" : "Menü";
    });

    nav.querySelectorAll("a").forEach((link) => link.addEventListener("click", close));
    window.addEventListener("resize", () => {
      if (window.innerWidth > 1180) close();
    });
  }

  function setupScrollState() {
    const header = document.querySelector("[data-site-header]");
    const progress = document.querySelector("[data-scroll-progress]");
    let queued = false;

    const update = () => {
      queued = false;
      const scrollable = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
      const value = Math.min(1, Math.max(0, window.scrollY / scrollable));
      if (header) header.classList.toggle("is-scrolled", window.scrollY > 28);
      if (progress) progress.style.transform = `scaleX(${value})`;
    };

    window.addEventListener("scroll", () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(update);
    }, { passive: true });
    update();
  }

  function setupSectionNavigation() {
    const links = [...document.querySelectorAll(".site-nav a[href^='#']")];
    const sections = links
      .map((link) => document.querySelector(link.getAttribute("href")))
      .filter(Boolean);
    if (!links.length || !sections.length || !("IntersectionObserver" in window)) return;

    const observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      links.forEach((link) => {
        const active = link.getAttribute("href") === `#${visible.target.id}`;
        link.classList.toggle("active", active);
        if (active) link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      });
    }, { rootMargin: "-22% 0px -58%", threshold: [0.05, 0.2, 0.45] });

    sections.forEach((section) => observer.observe(section));
  }

  function setupReveal() {
    const nodes = [...document.querySelectorAll(".reveal")];
    if (!nodes.length) return;
    if (reducedMotion || !("IntersectionObserver" in window)) {
      nodes.forEach((node) => node.classList.add("is-visible"));
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.12 });
    nodes.forEach((node) => observer.observe(node));
  }

  function setupHeroVideo() {
    const video = document.querySelector(".hero-video");
    if (!video) return;
    video.muted = true;
    video.playsInline = true;
    if (reducedMotion) {
      video.pause();
      video.removeAttribute("autoplay");
      return;
    }
    video.addEventListener("playing", () => video.removeAttribute("poster"), { once: true });
    const start = () => {
      const playback = video.play();
      if (playback && typeof playback.catch === "function") playback.catch(() => {});
    };
    start();
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && video.paused) start();
    });
  }

  function cubicPoint(curve, t) {
    const mt = 1 - t;
    const mt2 = mt * mt;
    const t2 = t * t;
    return {
      x: curve.p0.x * mt2 * mt + 3 * curve.p1.x * mt2 * t + 3 * curve.p2.x * mt * t2 + curve.p3.x * t2 * t,
      y: curve.p0.y * mt2 * mt + 3 * curve.p1.y * mt2 * t + 3 * curve.p2.y * mt * t2 + curve.p3.y * t2 * t
    };
  }

  function cubicTangent(curve, t) {
    const mt = 1 - t;
    return {
      x: 3 * mt * mt * (curve.p1.x - curve.p0.x) + 6 * mt * t * (curve.p2.x - curve.p1.x) + 3 * t * t * (curve.p3.x - curve.p2.x),
      y: 3 * mt * mt * (curve.p1.y - curve.p0.y) + 6 * mt * t * (curve.p2.y - curve.p1.y) + 3 * t * t * (curve.p3.y - curve.p2.y)
    };
  }

  function tentaclePolygon(context, curve, widthStart, widthEnd) {
    const left = [];
    const right = [];
    const samples = 42;
    for (let index = 0; index <= samples; index += 1) {
      const t = index / samples;
      const point = cubicPoint(curve, t);
      const tangent = cubicTangent(curve, t);
      const length = Math.hypot(tangent.x, tangent.y) || 1;
      const normal = { x: -tangent.y / length, y: tangent.x / length };
      const eased = Math.pow(t, 0.82);
      const halfWidth = (widthStart + (widthEnd - widthStart) * eased) / 2;
      left.push({ x: point.x + normal.x * halfWidth, y: point.y + normal.y * halfWidth });
      right.push({ x: point.x - normal.x * halfWidth, y: point.y - normal.y * halfWidth });
    }

    context.beginPath();
    context.moveTo(left[0].x, left[0].y);
    left.slice(1).forEach((point) => context.lineTo(point.x, point.y));
    right.reverse().forEach((point) => context.lineTo(point.x, point.y));
    context.closePath();
  }

  function drawTentacle(context, curve, active, index, compact) {
    const startWidth = compact ? 17 : 25;
    const endWidth = compact ? 7 : 10;

    context.save();
    context.shadowColor = "rgba(5, 1, 9, 0.34)";
    context.shadowBlur = compact ? 7 : 12;
    context.shadowOffsetY = compact ? 4 : 7;
    tentaclePolygon(context, curve, startWidth + 5, endWidth + 3);
    context.fillStyle = "rgba(20, 7, 29, 0.7)";
    context.fill();
    context.restore();

    const gradient = context.createLinearGradient(curve.p0.x, curve.p0.y, curve.p3.x, curve.p3.y);
    if (active) {
      gradient.addColorStop(0, "#c382d3");
      gradient.addColorStop(0.62, "#6a47a0");
      gradient.addColorStop(1, "#23a8a9");
    } else {
      gradient.addColorStop(0, "#8551a6");
      gradient.addColorStop(0.68, "#50306a");
      gradient.addColorStop(1, "#216e78");
    }
    tentaclePolygon(context, curve, startWidth, endWidth);
    context.fillStyle = gradient;
    context.fill();

    context.save();
    context.beginPath();
    context.moveTo(curve.p0.x, curve.p0.y);
    context.bezierCurveTo(curve.p1.x, curve.p1.y, curve.p2.x, curve.p2.y, curve.p3.x, curve.p3.y);
    context.strokeStyle = active ? "rgba(255, 255, 255, 0.28)" : "rgba(255, 255, 255, 0.15)";
    context.lineWidth = compact ? 1.5 : 2.5;
    context.lineCap = "round";
    context.stroke();
    context.restore();

    const suckerCount = compact ? 4 : 6;
    for (let suckerIndex = 0; suckerIndex < suckerCount; suckerIndex += 1) {
      const t = 0.3 + suckerIndex * (0.56 / Math.max(1, suckerCount - 1));
      const point = cubicPoint(curve, t);
      const tangent = cubicTangent(curve, t);
      const length = Math.hypot(tangent.x, tangent.y) || 1;
      const side = (index + suckerIndex) % 2 === 0 ? 1 : -1;
      const normal = { x: (-tangent.y / length) * side, y: (tangent.x / length) * side };
      const currentWidth = startWidth + (endWidth - startWidth) * t;
      context.beginPath();
      context.arc(point.x + normal.x * currentWidth * 0.3, point.y + normal.y * currentWidth * 0.3, compact ? 1.4 : 2.2, 0, Math.PI * 2);
      context.fillStyle = active ? "rgba(255, 244, 236, 0.72)" : "rgba(255, 244, 236, 0.42)";
      context.fill();
    }
  }

  function setupOctopusMap(stage) {
    const canvas = stage.querySelector(".octopus-canvas");
    const head = stage.querySelector(".octopus-head");
    const links = [...stage.querySelectorAll("[data-arm-link]")];
    if (!links.length) return;

    const bindLinkInteractions = () => {
      links.forEach((link) => {
        link.addEventListener("mouseenter", () => { stage.dataset.hoverArm = link.dataset.armLink; });
        link.addEventListener("mouseleave", () => { delete stage.dataset.hoverArm; });
        link.addEventListener("focus", () => { stage.dataset.hoverArm = link.dataset.armLink; });
        link.addEventListener("blur", () => { delete stage.dataset.hoverArm; });
        link.addEventListener("click", () => activateFeature(link.dataset.armLink));
      });
    };

    if (stage.classList.contains("octopus-stage-static")) {
      bindLinkInteractions();
      octopusMaps.push({ stage, links, observer: { disconnect() {} }, stop() {} });
      return;
    }
    if (!canvas || !head) return;
    const context = canvas.getContext("2d");
    const compact = stage.classList.contains("octopus-stage-secondary");
    let frame = 0;
    let size = { width: 0, height: 0, dpr: 1 };

    const resize = () => {
      const rect = stage.getBoundingClientRect();
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      size = { width: rect.width, height: rect.height, dpr };
      canvas.width = Math.max(1, Math.round(rect.width * dpr));
      canvas.height = Math.max(1, Math.round(rect.height * dpr));
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (reducedMotion) draw(0);
    };

    const geometry = (link, index, elapsed) => {
      const stageRect = stage.getBoundingClientRect();
      const headRect = head.getBoundingClientRect();
      const linkRect = link.getBoundingClientRect();
      const spread = compact ? 5.5 : 8.5;
      const origin = {
        x: headRect.left - stageRect.left + headRect.width / 2 + (index - 3.5) * spread,
        y: headRect.bottom - stageRect.top - (compact ? 8 : 10)
      };
      const target = {
        x: linkRect.left - stageRect.left + linkRect.width / 2,
        y: linkRect.top - stageRect.top + linkRect.height / 2
      };
      const dx = target.x - origin.x;
      const dy = Math.max(80, target.y - origin.y);
      const direction = dx === 0 ? (index < 4 ? -1 : 1) : Math.sign(dx);
      const wave = reducedMotion ? 0 : Math.sin(elapsed * 0.0012 + index * 0.78) * (compact ? 3 : 5);
      return {
        p0: origin,
        p1: { x: origin.x + dx * 0.18 + direction * (compact ? 19 : 30) + wave, y: origin.y + dy * 0.28 },
        p2: { x: target.x - dx * 0.16 + direction * (compact ? 10 : 16) - wave, y: origin.y + dy * 0.7 },
        p3: target
      };
    };

    function draw(elapsed) {
      context.clearRect(0, 0, size.width, size.height);
      const activeKey = stage.dataset.hoverArm || stage.dataset.activeArm || "search";
      links.forEach((link, index) => {
        drawTentacle(context, geometry(link, index, elapsed), link.dataset.armLink === activeKey, index, compact);
      });
      if (!reducedMotion && !document.hidden) frame = requestAnimationFrame(draw);
    }

    bindLinkInteractions();

    const observer = new ResizeObserver(resize);
    observer.observe(stage);
    resize();
    if (!reducedMotion) frame = requestAnimationFrame(draw);
    octopusMaps.push({ stage, links, observer, stop: () => cancelAnimationFrame(frame) });
  }

  function activateFeature(key) {
    if (!featureKeys.includes(key)) return;
    octopusMaps.forEach(({ stage, links }) => {
      stage.dataset.activeArm = key;
      links.forEach((link) => {
        const active = link.dataset.armLink === key;
        link.classList.toggle("active", active);
        if (active) link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      });
    });
    document.querySelectorAll("[data-feature-key]").forEach((node) => {
      node.classList.toggle("feature-active", node.dataset.featureKey === key);
    });
  }

  function setupFeatureTracking() {
    const features = [...document.querySelectorAll("[data-feature-key]")];
    activateFeature("search");
    if (!("IntersectionObserver" in window)) return;
    const observer = new IntersectionObserver((entries) => {
      const active = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (active) activateFeature(active.target.dataset.featureKey);
    }, { rootMargin: "-30% 0px -55%", threshold: [0.1, 0.45, 0.8] });
    features.forEach((feature) => observer.observe(feature));
  }

  function setupDocumentWorkspace() {
    const workspace = document.querySelector("[data-document-workspace]");
    if (!workspace) return;
    const filters = [...workspace.querySelectorAll("[data-doc-filter]")];
    const items = [...workspace.querySelectorAll("[data-doc-item]")];
    const count = workspace.querySelector("[data-document-count]");

    const outputs = {
      code: workspace.querySelector("[data-detail-code]"),
      title: workspace.querySelector("[data-detail-title]"),
      path: workspace.querySelector("[data-detail-path]"),
      study: workspace.querySelector("[data-detail-study]"),
      topic: workspace.querySelector("[data-detail-topic]"),
      year: workspace.querySelector("[data-detail-year]"),
      type: workspace.querySelector("[data-detail-type]"),
      confidence: workspace.querySelector("[data-detail-confidence]"),
      reason: workspace.querySelector("[data-detail-reason]")
    };

    const selectItem = (item, focus = false) => {
      if (!item || item.hidden) return;
      items.forEach((candidate) => {
        const active = candidate === item;
        candidate.classList.toggle("active", active);
        candidate.setAttribute("aria-pressed", String(active));
      });
      Object.entries(outputs).forEach(([key, output]) => {
        if (!output) return;
        const value = item.dataset[key] || "—";
        output.textContent = key === "confidence" ? `${value} güven` : value;
      });
      if (focus) item.focus();
    };

    const applyFilter = (filter) => {
      filters.forEach((button) => {
        const active = button === filter;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", String(active));
      });
      const key = filter.dataset.docFilter;
      items.forEach((item) => { item.hidden = key !== "all" && item.dataset.category !== key; });
      const visible = items.filter((item) => !item.hidden);
      if (count) count.textContent = `${visible.length} örnek doküman`;
      if (!visible.some((item) => item.classList.contains("active"))) selectItem(visible[0], true);
    };

    filters.forEach((filter) => filter.addEventListener("click", () => applyFilter(filter)));
    items.forEach((item) => item.addEventListener("click", () => selectItem(item)));
    items.forEach((item) => item.setAttribute("aria-pressed", String(item.classList.contains("active"))));
  }

  setupMenu();
  setupScrollState();
  setupSectionNavigation();
  setupReveal();
  setupHeroVideo();
  document.querySelectorAll("[data-octopus-map]").forEach(setupOctopusMap);
  setupFeatureTracking();
  setupDocumentWorkspace();

  window.addEventListener("pagehide", () => {
    octopusMaps.forEach(({ observer, stop }) => {
      observer.disconnect();
      stop();
    });
  }, { once: true });
})();
