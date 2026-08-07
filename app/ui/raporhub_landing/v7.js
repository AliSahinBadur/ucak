const header = document.getElementById("site-header");
const menuButton = document.getElementById("menu-button");
const mobileMenu = document.getElementById("mobile-menu");

function updateHeader() {
  header.classList.toggle("is-scrolled", window.scrollY > 24);
}

function closeMenu() {
  menuButton.setAttribute("aria-expanded", "false");
  mobileMenu.hidden = true;
  header.classList.remove("menu-active");
  document.body.classList.remove("menu-open");
}

menuButton.addEventListener("click", () => {
  const willOpen = menuButton.getAttribute("aria-expanded") !== "true";
  menuButton.setAttribute("aria-expanded", String(willOpen));
  mobileMenu.hidden = !willOpen;
  header.classList.toggle("menu-active", willOpen);
  document.body.classList.toggle("menu-open", willOpen);
});

mobileMenu.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMenu));
window.addEventListener("scroll", updateHeader, { passive: true });
window.addEventListener("resize", () => {
  if (window.innerWidth > 900) closeMenu();
});
updateHeader();

const appLaunchLinks = [...document.querySelectorAll('a[href="/app"]')];
const appLaunchProgress = document.getElementById("app-launch-progress");
let appLaunchInProgress = false;
let appLaunchResetTimer = 0;

function resetAppLaunchState() {
  appLaunchInProgress = false;
  document.body.classList.remove("app-launching");
  appLaunchProgress.setAttribute("aria-hidden", "true");
  window.clearTimeout(appLaunchResetTimer);
  appLaunchLinks.forEach((link) => {
    link.removeAttribute("aria-disabled");
    link.classList.remove("is-launch-source");
    link.style.removeProperty("min-width");
    if (link.dataset.launchLabel) link.textContent = link.dataset.launchLabel;
  });
}

appLaunchLinks.forEach((link) => {
  link.dataset.launchLabel = link.textContent.trim();
  link.addEventListener("click", (event) => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if (appLaunchInProgress) {
      event.preventDefault();
      return;
    }

    appLaunchInProgress = true;
    link.style.minWidth = `${Math.ceil(link.getBoundingClientRect().width)}px`;
    link.textContent = "Açılıyor...";
    link.classList.add("is-launch-source");
    appLaunchLinks.forEach((item) => item.setAttribute("aria-disabled", "true"));
    appLaunchProgress.setAttribute("aria-hidden", "false");
    document.body.classList.add("app-launching");
    appLaunchResetTimer = window.setTimeout(resetAppLaunchState, 15000);
  });
});

window.addEventListener("pageshow", resetAppLaunchState);

const tabButtons = [...document.querySelectorAll("[data-product-tab]")];
const tabPanels = [...document.querySelectorAll("[data-product-panel]")];

function activateTab(name, focus = false) {
  tabButtons.forEach((button) => {
    const selected = button.dataset.productTab === name;
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
    if (selected && focus) button.focus();
  });

  tabPanels.forEach((panel) => {
    const selected = panel.dataset.productPanel === name;
    panel.hidden = !selected;
    panel.classList.toggle("active-panel", selected);
  });
}

tabButtons.forEach((button, index) => {
  button.addEventListener("click", () => activateTab(button.dataset.productTab));
  button.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const direction = event.key === "ArrowRight" ? 1 : -1;
    const nextIndex = (index + direction + tabButtons.length) % tabButtons.length;
    activateTab(tabButtons[nextIndex].dataset.productTab, true);
  });
});
activateTab("memory");

const revealItems = document.querySelectorAll(".reveal");
if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  const pendingRevealItems = new Set(revealItems);
  let revealTimer = 0;

  const revealVisibleItems = () => {
    pendingRevealItems.forEach((item) => {
      const bounds = item.getBoundingClientRect();
      if (bounds.top >= window.innerHeight - 36 || bounds.bottom <= 0) return;
      item.classList.add("is-visible");
      pendingRevealItems.delete(item);
    });
    if (pendingRevealItems.size) return;
    window.removeEventListener("scroll", revealVisibleItems);
    window.removeEventListener("resize", revealVisibleItems);
    window.clearTimeout(revealTimer);
  };

  const pollRevealItems = () => {
    revealVisibleItems();
    if (pendingRevealItems.size) revealTimer = window.setTimeout(pollRevealItems, 240);
  };

  window.addEventListener("scroll", revealVisibleItems, { passive: true });
  window.addEventListener("resize", revealVisibleItems);
  pollRevealItems();
} else {
  revealItems.forEach((item) => item.classList.add("is-visible"));
}
