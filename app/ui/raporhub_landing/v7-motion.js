(() => {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const reduceMotion = reducedMotion.matches;
  document.body.classList.add("motion-ready");

  const videos = [...document.querySelectorAll(".proof-video, .hero-video")];
  videos.forEach((video) => {
    video.muted = true;
    video.defaultMuted = true;
    const playbackRate = Number(video.dataset.playbackRate || 1.5);
    video.defaultPlaybackRate = playbackRate;
    video.playbackRate = playbackRate;
    if (reduceMotion) {
      video.removeAttribute("autoplay");
      video.pause();
    }
  });

  if (!reduceMotion) {
    let videoVisibilityTimer = 0;
    const updateVideoPlayback = () => {
      videos.forEach((video) => {
        if (document.hidden) {
          video.pause();
          return;
        }
        const bounds = video.getBoundingClientRect();
        const visible = bounds.top < window.innerHeight && bounds.bottom > 0;
        if (visible) {
          const playRequest = video.play();
          if (playRequest) playRequest.catch(() => {});
        } else {
          video.pause();
        }
      });
    };
    const pollVideoPlayback = () => {
      updateVideoPlayback();
      videoVisibilityTimer = window.setTimeout(pollVideoPlayback, 600);
    };
    window.addEventListener("scroll", updateVideoPlayback, { passive: true });
    window.addEventListener("resize", updateVideoPlayback);
    pollVideoPlayback();
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden || reduceMotion) return;
    videos.forEach((video) => video.pause());
  });

  if (!reduceMotion) {
    const hero = document.querySelector(".hero");
    let frameRequested = false;

    const updateParallax = () => {
      frameRequested = false;
      if (!hero || window.innerWidth <= 900) {
        hero?.style.setProperty("--v7-parallax", "0px");
        return;
      }
      const bounds = hero.getBoundingClientRect();
      const visibleProgress = Math.max(-1, Math.min(1, -bounds.top / Math.max(bounds.height, 1)));
      hero.style.setProperty("--v7-parallax", `${Math.round(visibleProgress * 18)}px`);
    };

    const requestParallax = () => {
      if (frameRequested) return;
      frameRequested = true;
      window.requestAnimationFrame(updateParallax);
    };

    window.addEventListener("scroll", requestParallax, { passive: true });
    window.addEventListener("resize", requestParallax);
    updateParallax();
  }

  document.querySelectorAll("[data-memory-explorer]").forEach((explorer) => {
    const assignMotionOrder = () => {
      explorer.querySelectorAll(".mx-branch").forEach((branch, index) => {
        branch.style.setProperty("--motion-order", index);
      });
      explorer.querySelectorAll(".mx-leaf").forEach((leaf, index) => {
        leaf.style.setProperty("--motion-order", index);
      });
    };

    const replayTree = () => {
      if (!explorer.classList.contains("motion-active")) return;
      explorer.classList.remove("motion-active");
      window.requestAnimationFrame(() => window.requestAnimationFrame(() => explorer.classList.add("motion-active")));
    };

    assignMotionOrder();
    const branchHost = explorer.querySelector("[data-memory-branches]");
    if (branchHost && typeof MutationObserver === "function") {
      const branchObserver = new MutationObserver(() => {
        assignMotionOrder();
        if (!reduceMotion) replayTree();
      });
      branchObserver.observe(branchHost, { childList: true, subtree: true });
    }

    if (!reduceMotion) {
      let treeVisibilityTimer = 0;
      const activateTreeWhenVisible = () => {
        const bounds = explorer.getBoundingClientRect();
        const visible = bounds.top < window.innerHeight * 0.88 && bounds.bottom > window.innerHeight * 0.12;
        if (!visible) return;
        explorer.classList.add("motion-active");
        window.removeEventListener("scroll", activateTreeWhenVisible);
        window.removeEventListener("resize", activateTreeWhenVisible);
        window.clearTimeout(treeVisibilityTimer);
      };
      const pollTreeVisibility = () => {
        activateTreeWhenVisible();
        if (!explorer.classList.contains("motion-active")) {
          treeVisibilityTimer = window.setTimeout(pollTreeVisibility, 240);
        }
      };
      window.addEventListener("scroll", activateTreeWhenVisible, { passive: true });
      window.addEventListener("resize", activateTreeWhenVisible);
      pollTreeVisibility();
    } else {
      explorer.classList.add("motion-active");
    }

    explorer.addEventListener("click", (event) => {
      const relationButton = event.target.closest('[data-memory-view="relations"]');
      if (!relationButton || reduceMotion) return;
      window.requestAnimationFrame(() => {
        const graph = explorer.querySelector(".mx-relations");
        if (!graph) return;
        graph.classList.remove("motion-relations");
        void graph.getBoundingClientRect();
        graph.classList.add("motion-relations");
      });
    });
  });
})();
