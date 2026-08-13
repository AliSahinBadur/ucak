from __future__ import annotations

from .repocto_styles import REPOCTO_CSS


RAPORHUB_CSS = """
    body[data-app-variant="raporhub"] {
      --rh-canvas: #e8f1ed;
      --rh-surface: #f8fbf9;
      --rh-surface-muted: #eef7f2;
      --rh-sidebar: #064e3b;
      --rh-sidebar-soft: #0f6a52;
      --rh-ink: #13271f;
      --rh-muted: #63766e;
      --rh-line: #b8ccc3;
      --rh-accent: #059669;
      --rh-accent-dark: #047857;
      --rh-amber: #c58a2a;
      --rh-blue: #316f9f;
      --rh-topbar: rgba(248, 251, 249, 0.97);
      min-width: 0;
      max-width: 100%;
      overflow-x: hidden;
      background: var(--rh-canvas);
    }
    body[data-app-variant="raporhub"].raporhub-dark {
      --rh-canvas: #17201e;
      --rh-surface: #1f2c27;
      --rh-surface-muted: #263630;
      --rh-sidebar: #0b2f25;
      --rh-sidebar-soft: #124737;
      --rh-ink: #edf8f2;
      --rh-muted: #a9bdb4;
      --rh-line: #3d574b;
      --rh-accent: #34d399;
      --rh-accent-dark: #6ee7b7;
      --rh-amber: #d5a54b;
      --rh-blue: #78a9ce;
      --rh-topbar: rgba(31, 44, 39, 0.97);
      --panel: var(--rh-surface);
      --line: var(--rh-line);
      --text: var(--rh-ink);
      --muted: var(--rh-muted);
      --accent: var(--rh-accent);
      --accent-strong: var(--rh-accent-dark);
      --soft: #2b4037;
      --soft-2: #22312b;
      --ok: #6ee7b7;
      --error: #ff8d9a;
      color-scheme: dark;
    }
    body[data-app-variant="raporhub"] .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
    body[data-app-variant="raporhub"] [hidden] {
      display: none !important;
    }
    body[data-app-variant="raporhub"] .wrap,
    body[data-app-variant="raporhub"] .stack,
    body[data-app-variant="raporhub"] .card {
      width: 100%;
      max-width: 100%;
      min-width: 0;
      min-height: 100vh;
      margin: 0;
      padding: 0;
    }
    body[data-app-variant="raporhub"] .stack {
      gap: 0;
    }
    body[data-app-variant="raporhub"] .card {
      position: relative;
      display: grid;
      grid-template-columns: 264px minmax(0, 1fr);
      grid-template-rows: minmax(100vh, auto);
      align-items: stretch;
      overflow: visible;
      border: 0;
      border-radius: 0;
      background: var(--rh-canvas);
      box-shadow: none;
      transition: grid-template-columns 180ms ease;
    }
    body[data-app-variant="raporhub"] .hero {
      position: sticky;
      top: 0;
      z-index: 30;
      grid-column: 1;
      grid-row: 1;
      display: flex;
      flex-direction: column;
      width: 264px;
      min-width: 0;
      min-height: 100vh;
      max-height: 100vh;
      overflow-y: auto;
      padding: 24px 16px 18px;
      border: 0;
      background: var(--rh-sidebar);
      color: #ffffff;
      transition: width 180ms ease, padding 180ms ease;
    }
    body[data-app-variant="raporhub"] .hero-title-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-width: 0;
      margin: 0;
    }
    body[data-app-variant="raporhub"] .hero h1 {
      display: flex;
      align-items: center;
      gap: 11px;
      margin: 0;
      color: #ffffff;
      font-size: 22px;
      line-height: 1.15;
    }
    body[data-app-variant="raporhub"] .raporhub-brand-subtitle {
      margin: 8px 0 0;
      padding-bottom: 18px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.16);
      color: #acd7c5;
      font-size: 11px;
      line-height: 1.3;
    }
    body[data-app-variant="raporhub"] .hero p,
    body[data-app-variant="raporhub"] .hero .version-pill,
    body[data-app-variant="raporhub"] .hero .logout-link {
      display: none;
    }
    body[data-app-variant="raporhub"] .module-switcher {
      display: flex;
      flex-direction: column;
      align-items: stretch;
      gap: 3px;
      margin-top: 18px;
    }
    body[data-app-variant="raporhub"] .raporhub-nav-label {
      margin: 18px 11px 5px;
      color: #8fc4af;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0;
      text-transform: uppercase;
    }
    body[data-app-variant="raporhub"] .raporhub-nav-label:first-child {
      margin-top: 0;
    }
    body[data-app-variant="raporhub"] .module-filter {
      position: relative;
      width: 100%;
      min-height: 40px;
      border: 0;
      border-radius: 4px;
      background: transparent;
      color: #d1e9df;
      padding: 10px 12px 10px 16px;
      text-align: left;
      font-size: 13px;
      font-weight: 700;
      line-height: 1.25;
    }
    body[data-app-variant="raporhub"] .module-filter:hover {
      background: var(--rh-sidebar-soft);
      color: #ffffff;
    }
    body[data-app-variant="raporhub"] .module-filter.active {
      border-color: transparent;
      background: var(--rh-surface);
      color: var(--rh-accent-dark);
      box-shadow: none;
    }
    body[data-app-variant="raporhub"] .module-filter.active::before {
      content: "";
      position: absolute;
      top: 8px;
      bottom: 8px;
      left: 0;
      width: 3px;
      background: var(--rh-amber);
    }
    body[data-app-variant="raporhub"] .raporhub-sidebar-footer {
      margin-top: auto;
      padding: 18px 10px 0;
      border-top: 1px solid rgba(255, 255, 255, 0.12);
      color: #acd7c5;
      font-size: 11px;
    }
    body[data-app-variant="raporhub"] .raporhub-sidebar-footer a {
      display: inline-block;
      margin-top: 11px;
      color: #d9e4e2;
      font-weight: 700;
      text-decoration: none;
    }
    body[data-app-variant="raporhub"] .raporhub-local-status {
      display: flex;
      align-items: center;
      gap: 7px;
    }
    body[data-app-variant="raporhub"] .raporhub-local-status span {
      width: 7px;
      height: 7px;
      flex: 0 0 7px;
      border-radius: 50%;
      background: #61ba88;
      box-shadow: 0 0 0 3px rgba(97, 186, 136, 0.12);
    }

    body[data-app-variant="raporhub"].raporhub-sidebar-collapsed .card {
      grid-template-columns: 72px minmax(0, 1fr);
    }
    body[data-app-variant="raporhub"].raporhub-sidebar-collapsed .hero {
      width: 72px;
      padding: 18px 10px;
    }
    body[data-app-variant="raporhub"].raporhub-sidebar-collapsed .hero h1,
    body[data-app-variant="raporhub"].raporhub-sidebar-collapsed .raporhub-brand-subtitle,
    body[data-app-variant="raporhub"].raporhub-sidebar-collapsed .raporhub-nav-label,
    body[data-app-variant="raporhub"].raporhub-sidebar-collapsed .raporhub-sidebar-footer {
      display: none;
    }
    body[data-app-variant="raporhub"].raporhub-sidebar-collapsed .module-switcher {
      margin-top: 24px;
      gap: 7px;
    }
    body[data-app-variant="raporhub"].raporhub-sidebar-collapsed .hero-title-row {
      justify-content: center;
    }
    body[data-app-variant="raporhub"].raporhub-sidebar-collapsed .module-filter {
      display: grid;
      place-items: center;
      min-height: 42px;
      padding: 0;
      overflow: hidden;
      font-size: 0;
      text-align: center;
    }
    body[data-app-variant="raporhub"].raporhub-sidebar-collapsed .module-filter::after {
      content: attr(data-nav-short);
      color: inherit;
      font-size: 10px;
      font-weight: 900;
    }

    body[data-app-variant="raporhub"] .raporhub-sidebar-toggle {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 38px;
      height: 38px;
      flex: 0 0 38px;
      border: 1px solid var(--rh-line);
      border-radius: 4px;
      border-color: rgba(255, 255, 255, 0.24);
      background: transparent;
      padding: 0;
      cursor: pointer;
    }
    body[data-app-variant="raporhub"] .raporhub-sidebar-toggle:hover {
      border-color: rgba(255, 255, 255, 0.42);
      background: var(--rh-sidebar-soft);
    }
    body[data-app-variant="raporhub"] .raporhub-sidebar-toggle-icon {
      position: relative;
      display: block;
      width: 18px;
      height: 16px;
      border: 1.5px solid #d9e5e2;
      border-radius: 4px;
      background: transparent;
    }
    body[data-app-variant="raporhub"] .raporhub-sidebar-toggle-icon::before {
      content: "";
      position: absolute;
      top: 1px;
      bottom: 1px;
      left: 6px;
      width: 1.5px;
      border-radius: 1px;
      background: #d9e5e2;
      transition: left 180ms ease;
    }
    body[data-app-variant="raporhub"].raporhub-sidebar-collapsed .raporhub-sidebar-toggle-icon::before {
      left: 10px;
    }

    body[data-app-variant="raporhub"] .raporhub-theme-toggle {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 38px;
      height: 38px;
      justify-self: end;
      border: 1px solid var(--rh-line);
      border-radius: 4px;
      background: var(--rh-surface);
      color: var(--rh-accent-dark);
      padding: 0;
      cursor: pointer;
    }
    body[data-app-variant="raporhub"] .raporhub-theme-toggle:hover {
      background: var(--rh-surface-muted);
    }
    body[data-app-variant="raporhub"] .raporhub-theme-icon {
      position: relative;
      display: block;
      width: 16px;
      height: 16px;
      border: 2px solid currentColor;
      border-radius: 50%;
    }
    body[data-app-variant="raporhub"] .raporhub-theme-icon::after {
      content: "";
      position: absolute;
      top: -3px;
      left: 5px;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: var(--rh-surface);
    }
    body[data-app-variant="raporhub"].raporhub-dark .raporhub-theme-icon {
      width: 12px;
      height: 12px;
      border-color: #e2b85f;
      background: #e2b85f;
      box-shadow: 0 -7px 0 -5px #e2b85f, 0 7px 0 -5px #e2b85f, 7px 0 0 -5px #e2b85f, -7px 0 0 -5px #e2b85f;
    }
    body[data-app-variant="raporhub"].raporhub-dark .raporhub-theme-icon::after {
      display: none;
    }

    body[data-app-variant="raporhub"] .raporhub-topbar {
      position: absolute;
      top: 10px;
      right: 14px;
      z-index: 40;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 10px;
      width: auto;
      min-width: 0;
      min-height: 0;
      padding: 0;
      border: 0;
      background: transparent;
    }
    body[data-app-variant="raporhub"] .raporhub-system-menu {
      position: relative;
      justify-self: end;
    }
    body[data-app-variant="raporhub"] .raporhub-system-menu summary {
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 38px;
      border: 1px solid var(--rh-line);
      border-radius: 4px;
      background: var(--rh-surface);
      padding: 0 10px;
      color: var(--rh-muted);
      font-size: 11px;
      cursor: pointer;
      list-style: none;
    }
    body[data-app-variant="raporhub"] .raporhub-system-menu summary::-webkit-details-marker {
      display: none;
    }
    body[data-app-variant="raporhub"] .raporhub-system-menu summary strong {
      color: var(--rh-ink);
      font-size: 12px;
    }
    body[data-app-variant="raporhub"] .raporhub-device-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--rh-amber);
    }
    body[data-app-variant="raporhub"] .raporhub-device-dot.compute-gpu {
      background: #2a9762;
    }
    body[data-app-variant="raporhub"] .raporhub-system-popover {
      position: absolute;
      top: calc(100% + 8px);
      right: 0;
      z-index: 40;
      width: min(320px, calc(100vw - 32px));
      border: 1px solid var(--rh-line);
      border-radius: 6px;
      background: var(--rh-surface);
      box-shadow: 0 16px 36px rgba(16, 47, 43, 0.16);
      padding: 10px 14px;
    }
    body[data-app-variant="raporhub"] .raporhub-system-popover div {
      display: grid;
      grid-template-columns: 88px minmax(0, 1fr);
      gap: 10px;
      padding: 8px 0;
      border-bottom: 1px solid #e3eae8;
      font-size: 12px;
    }
    body[data-app-variant="raporhub"] .raporhub-system-popover div:last-child {
      border-bottom: 0;
    }
    body[data-app-variant="raporhub"] .raporhub-system-popover span {
      color: var(--rh-muted);
    }
    body[data-app-variant="raporhub"] .raporhub-system-popover strong {
      min-width: 0;
      overflow-wrap: anywhere;
      color: var(--rh-ink);
      text-align: right;
    }

    body[data-app-variant="raporhub"] .section {
      grid-column: 2;
      grid-row: 1;
      width: 100%;
      max-width: 100%;
      min-width: 0;
      min-height: 100vh;
      padding: 28px 30px 46px;
      background: var(--rh-canvas);
    }
    body[data-app-variant="raporhub"] .section + .section {
      border-top: 0;
    }
    body[data-app-variant="raporhub"] .section-head {
      align-items: center;
      margin-bottom: 20px;
      padding-bottom: 15px;
      border-bottom: 1px solid var(--rh-line);
      padding-right: 180px;
    }
    body[data-app-variant="raporhub"] .section-head h2 {
      display: none;
    }
    body[data-app-variant="raporhub"] .section-head p {
      color: var(--rh-muted);
      font-size: 13px;
    }
    body[data-app-variant="raporhub"] .expand-button {
      display: none;
    }
    body[data-app-variant="raporhub"] .upload-card,
    body[data-app-variant="raporhub"] .panel,
    body[data-app-variant="raporhub"] .comparison-source,
    body[data-app-variant="raporhub"] .comparison-pdf-panel,
    body[data-app-variant="raporhub"] .duplicate-workspace-pane,
    body[data-app-variant="raporhub"] .category-browser-panel,
    body[data-app-variant="raporhub"] .category-chart-panel {
      min-width: 0;
      max-width: 100%;
      border-radius: 6px;
      border-color: #becdca;
      background: var(--rh-surface);
      box-shadow: none;
    }
    body[data-app-variant="raporhub"] .upload-card {
      padding: 22px;
    }
    body[data-app-variant="raporhub"] .section[data-module-key="upload"] .uploaded-documents-panel {
      display: block;
      margin-top: 20px;
      padding: 20px;
      border: 1px solid #becdca;
      border-radius: 6px;
      background: var(--rh-surface);
    }
    body[data-app-variant="raporhub"] .button,
    body[data-app-variant="raporhub"] button,
    body[data-app-variant="raporhub"] input,
    body[data-app-variant="raporhub"] select,
    body[data-app-variant="raporhub"] textarea,
    body[data-app-variant="raporhub"] .files,
    body[data-app-variant="raporhub"] .note,
    body[data-app-variant="raporhub"] .status,
    body[data-app-variant="raporhub"] .result {
      border-radius: 4px;
    }
    body[data-app-variant="raporhub"] input,
    body[data-app-variant="raporhub"] select,
    body[data-app-variant="raporhub"] textarea {
      min-width: 0;
      max-width: 100%;
      border-color: var(--rh-line);
      background: var(--rh-surface-muted);
    }
    body[data-app-variant="raporhub"] .primary {
      background: #047857;
      box-shadow: none;
    }
    body[data-app-variant="raporhub"] .primary:hover {
      background: #065f46;
    }
    body[data-app-variant="raporhub"] .secondary {
      background: #e7f1ef;
      color: var(--rh-accent-dark);
    }
    body[data-app-variant="raporhub"] .files {
      border-style: solid;
      background: var(--rh-surface-muted);
    }
    body[data-app-variant="raporhub"] .table-box,
    body[data-app-variant="raporhub"] .catalog-table-scroll {
      max-width: 100%;
      overflow-x: auto;
    }
    body[data-app-variant="raporhub"] table thead th {
      background: #dfe8e5;
      color: #29423e;
    }
    body[data-app-variant="raporhub"] table tbody tr:hover {
      background: #e3eeeb;
    }
    body[data-app-variant="raporhub"] .module-modal-shell,
    body[data-app-variant="raporhub"] .section.module-expanded {
      border-color: #8fa6a2;
      border-radius: 8px;
      box-shadow: 0 24px 70px rgba(9, 38, 35, 0.28);
    }
    body[data-app-variant="raporhub"] .module-modal-bar {
      background: var(--rh-surface-muted);
    }
    body[data-app-variant="raporhub"].modal-open::before {
      background: rgba(8, 31, 29, 0.58);
    }
    body[data-app-variant="raporhub"] .section.module-expanded {
      inset: 18px;
      min-height: 0;
      background: var(--rh-canvas);
    }

    body[data-app-variant="raporhub"] .raporhub-home {
      padding-top: 24px;
    }
    body[data-app-variant="raporhub"] .raporhub-welcome-band {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      padding: 0 0 22px;
      border-bottom: 1px solid var(--rh-line);
    }
    body[data-app-variant="raporhub"] .raporhub-eyebrow,
    body[data-app-variant="raporhub"] .raporhub-panel-heading span {
      color: var(--rh-accent-dark);
      font-size: 10px;
      font-weight: 900;
      letter-spacing: 0;
    }
    body[data-app-variant="raporhub"] .raporhub-welcome-band h2 {
      margin: 5px 0 6px;
      color: var(--rh-ink);
      font-size: 24px;
    }
    body[data-app-variant="raporhub"] .raporhub-welcome-band p {
      color: var(--rh-muted);
      font-size: 13px;
    }
    body[data-app-variant="raporhub"] .raporhub-question-workspace {
      margin-top: 22px;
      border: 1px solid #b9c9c6;
      border-left: 4px solid var(--rh-accent);
      border-radius: 6px;
      background: var(--rh-surface);
      padding: 18px 20px;
    }
    body[data-app-variant="raporhub"] .raporhub-question-copy {
      display: flex;
      align-items: baseline;
      gap: 9px;
      color: var(--rh-muted);
      font-size: 12px;
    }
    body[data-app-variant="raporhub"] .raporhub-question-copy strong {
      color: var(--rh-ink);
      font-size: 14px;
    }
    body[data-app-variant="raporhub"] .raporhub-question-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: stretch;
      gap: 10px;
      margin-top: 12px;
    }
    body[data-app-variant="raporhub"] .raporhub-question-row textarea {
      width: 100%;
      min-height: 58px;
      resize: vertical;
      border-color: #afc1bd;
      background: var(--rh-surface-muted);
    }
    body[data-app-variant="raporhub"] .raporhub-question-row .button {
      min-width: 124px;
    }
    body[data-app-variant="raporhub"] .raporhub-starters {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin-top: 10px;
    }
    body[data-app-variant="raporhub"] .raporhub-starters button,
    body[data-app-variant="raporhub"] .raporhub-panel-heading button,
    body[data-app-variant="raporhub"] .raporhub-text-action {
      border: 0;
      background: transparent;
      color: var(--rh-accent-dark);
      padding: 3px 0;
      font-size: 12px;
      font-weight: 800;
      cursor: pointer;
    }
    body[data-app-variant="raporhub"] .raporhub-starters button {
      border-right: 1px solid var(--rh-line);
      border-radius: 0;
      padding-right: 9px;
    }
    body[data-app-variant="raporhub"] .raporhub-starters button:last-child {
      border-right: 0;
    }
    body[data-app-variant="raporhub"] .raporhub-metric-strip {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      margin-top: 22px;
      border-top: 1px solid var(--rh-line);
      border-bottom: 1px solid var(--rh-line);
      background: var(--rh-surface-muted);
    }
    body[data-app-variant="raporhub"] .raporhub-metric-strip > div {
      min-width: 0;
      padding: 15px 18px;
      border-right: 1px solid var(--rh-line);
    }
    body[data-app-variant="raporhub"] .raporhub-metric-strip > div:last-child {
      border-right: 0;
    }
    body[data-app-variant="raporhub"] .raporhub-metric-strip span {
      display: block;
      color: var(--rh-muted);
      font-size: 11px;
    }
    body[data-app-variant="raporhub"] .raporhub-metric-strip strong {
      display: block;
      margin-top: 5px;
      overflow: hidden;
      color: var(--rh-ink);
      font-size: 20px;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    body[data-app-variant="raporhub"] .raporhub-overview-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.65fr) minmax(280px, 0.75fr);
      gap: 18px;
      margin-top: 22px;
    }
    body[data-app-variant="raporhub"] .raporhub-recent-workspace,
    body[data-app-variant="raporhub"] .raporhub-readiness-panel {
      min-width: 0;
      border: 1px solid var(--rh-line);
      border-radius: 6px;
      background: var(--rh-surface);
      padding: 18px;
    }
    body[data-app-variant="raporhub"] .raporhub-panel-heading {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 14px;
      padding-bottom: 12px;
      border-bottom: 1px solid #dbe4e2;
    }
    body[data-app-variant="raporhub"] .raporhub-panel-heading h3 {
      margin: 4px 0 0;
      color: var(--rh-ink);
      font-size: 16px;
    }
    body[data-app-variant="raporhub"] .raporhub-recent-list {
      min-height: 220px;
    }
    body[data-app-variant="raporhub"] .raporhub-document-row {
      display: grid;
      grid-template-columns: 44px minmax(0, 1fr) minmax(90px, auto) 28px;
      align-items: center;
      gap: 12px;
      width: 100%;
      min-height: 58px;
      border: 0;
      border-bottom: 1px solid #e1e8e6;
      border-radius: 0;
      background: var(--rh-surface);
      padding: 8px 4px;
      text-align: left;
      cursor: pointer;
    }
    body[data-app-variant="raporhub"] .raporhub-document-row:hover {
      background: #e7efed;
    }
    body[data-app-variant="raporhub"] .raporhub-document-row:last-child {
      border-bottom: 0;
    }
    body[data-app-variant="raporhub"] .raporhub-file-badge {
      display: grid;
      place-items: center;
      width: 40px;
      height: 36px;
      border-radius: 4px;
      background: #e7f1ef;
      color: var(--rh-accent-dark);
      font-size: 10px;
      font-weight: 900;
    }
    body[data-app-variant="raporhub"] .raporhub-file-badge.type-docx {
      background: #e6eef6;
      color: var(--rh-blue);
    }
    body[data-app-variant="raporhub"] .raporhub-file-badge.type-pptx {
      background: #f8ecde;
      color: #9b5c24;
    }
    body[data-app-variant="raporhub"] .raporhub-document-main {
      min-width: 0;
    }
    body[data-app-variant="raporhub"] .raporhub-document-main strong,
    body[data-app-variant="raporhub"] .raporhub-document-main span {
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    body[data-app-variant="raporhub"] .raporhub-document-main strong {
      color: var(--rh-ink);
      font-size: 13px;
    }
    body[data-app-variant="raporhub"] .raporhub-document-main span,
    body[data-app-variant="raporhub"] .raporhub-document-meta {
      margin-top: 3px;
      color: var(--rh-muted);
      font-size: 11px;
    }
    body[data-app-variant="raporhub"] .raporhub-document-open {
      color: var(--rh-accent-dark);
      font-size: 18px;
      text-align: center;
    }
    body[data-app-variant="raporhub"] .raporhub-empty-state {
      display: flex;
      flex-direction: column;
      justify-content: center;
      min-height: 210px;
      color: var(--rh-muted);
    }
    body[data-app-variant="raporhub"] .raporhub-empty-state strong {
      color: var(--rh-ink);
      font-size: 15px;
    }
    body[data-app-variant="raporhub"] .raporhub-empty-state span {
      margin-top: 5px;
      font-size: 12px;
    }
    body[data-app-variant="raporhub"] .raporhub-ready-badge {
      border: 1px solid #bedacb;
      border-radius: 4px;
      background: #eef8f2;
      padding: 5px 7px;
      color: #237249;
      font-size: 10px;
      font-weight: 900;
    }
    body[data-app-variant="raporhub"] .raporhub-ready-badge.partial {
      border-color: #e7c998;
      background: #fff7e9;
      color: #8c5a11;
    }
    body[data-app-variant="raporhub"] .raporhub-coverage-track {
      height: 8px;
      margin-top: 20px;
      overflow: hidden;
      border-radius: 4px;
      background: #d2ddda;
    }
    body[data-app-variant="raporhub"] .raporhub-coverage-track span {
      display: block;
      width: 0;
      height: 100%;
      background: var(--rh-accent);
      transition: width 260ms ease;
    }
    body[data-app-variant="raporhub"] .raporhub-readiness-copy {
      margin-top: 10px;
      color: var(--rh-muted);
      font-size: 12px;
      line-height: 1.5;
    }
    body[data-app-variant="raporhub"] .raporhub-system-facts {
      margin: 18px 0 12px;
      border-top: 1px solid #dbe4e2;
    }
    body[data-app-variant="raporhub"] .raporhub-system-facts div {
      display: grid;
      grid-template-columns: 110px minmax(0, 1fr);
      gap: 8px;
      padding: 10px 0;
      border-bottom: 1px solid #e2e9e7;
      font-size: 11px;
    }
    body[data-app-variant="raporhub"] .raporhub-system-facts dt {
      color: var(--rh-muted);
    }
    body[data-app-variant="raporhub"] .raporhub-system-facts dd {
      min-width: 0;
      margin: 0;
      overflow-wrap: anywhere;
      color: var(--rh-ink);
      font-weight: 800;
      text-align: right;
    }
    body[data-app-variant="raporhub"] .raporhub-overview-status {
      margin-top: 12px;
      color: var(--rh-muted);
      font-size: 11px;
    }
    body[data-app-variant="raporhub"] .raporhub-skeleton-row {
      height: 58px;
      border-bottom: 1px solid #e2e9e7;
      background: #e7eeec;
      animation: raporhub-pulse 1.2s ease-in-out infinite alternate;
    }
    @keyframes raporhub-pulse {
      from { opacity: 0.45; }
      to { opacity: 0.9; }
    }

    body[data-app-variant="raporhub"] .section[data-module-key="chat"] {
      height: 100vh;
      min-height: 100vh;
      padding: 0;
      overflow: hidden;
    }
    body[data-app-variant="raporhub"] .section[data-module-key="chat"] .section-head {
      display: none;
    }
    body[data-app-variant="raporhub"] .chat-layout,
    body[data-app-variant="raporhub"].chat-focus .chat-layout {
      grid-template-columns: minmax(0, 1fr) minmax(300px, 340px);
      gap: 0;
      height: 100%;
      min-height: 0;
      margin: 0;
      background: var(--rh-surface);
    }
    body[data-app-variant="raporhub"] .chat-panel,
    body[data-app-variant="raporhub"] .chat-side {
      min-width: 0;
      height: 100%;
      min-height: 0;
      border-radius: 0;
      box-shadow: none;
    }
    body[data-app-variant="raporhub"] .chat-panel {
      overflow: hidden;
      border: 0;
      background: var(--rh-surface);
      padding: 0;
    }
    body[data-app-variant="raporhub"] .chat-side {
      position: relative;
      overflow: hidden;
      border: 0;
      border-left: 1px solid var(--rh-line);
      background: var(--rh-surface-muted);
      padding: 70px 20px 22px;
    }
    body[data-app-variant="raporhub"] .chat-side::before {
      content: "";
      position: absolute;
      top: 58px;
      right: 20px;
      left: 20px;
      height: 1px;
      background: var(--rh-line);
    }
    body[data-app-variant="raporhub"] .chat-toolbar {
      display: none;
    }
    body[data-app-variant="raporhub"] .chat-messages {
      flex: 1 1 auto;
      min-width: 0;
      min-height: 0;
      max-height: none;
      border: 0;
      border-radius: 0;
      background: var(--rh-canvas);
      padding: 24px;
      overscroll-behavior: contain;
    }
    body[data-app-variant="raporhub"] .chat-message,
    body[data-app-variant="raporhub"] .chat-prompt,
    body[data-app-variant="raporhub"] .tag,
    body[data-app-variant="raporhub"] .tag-chip,
    body[data-app-variant="raporhub"] .doc-tag,
    body[data-app-variant="raporhub"] .chat-source-card {
      border-radius: 4px;
    }
    body[data-app-variant="raporhub"] .chat-message.user {
      border-color: var(--rh-accent);
      background: #047857;
    }
    body[data-app-variant="raporhub"] .chat-message.assistant {
      border-color: var(--rh-line);
      background: var(--rh-surface);
      box-shadow: none;
    }
    body[data-app-variant="raporhub"] .chat-prompts-shell {
      flex: 0 0 auto;
      min-width: 0;
      background: var(--rh-surface);
    }
    body[data-app-variant="raporhub"] .chat-prompts {
      flex-wrap: nowrap;
      overflow-x: auto;
      overflow-y: hidden;
      margin: 0;
      padding: 12px 22px 8px;
      border-top: 1px solid var(--rh-line);
      background: var(--rh-surface);
      overscroll-behavior-inline: contain;
      scrollbar-width: thin;
      scrollbar-color: var(--rh-line) transparent;
    }
    body[data-app-variant="raporhub"] .chat-prompts > .chat-prompt,
    body[data-app-variant="raporhub"] .chat-prompt-help {
      flex: 0 0 auto;
    }
    body[data-app-variant="raporhub"] .chat-prompt-tooltip {
      left: 22px;
    }
    body[data-app-variant="raporhub"] .chat-prompt {
      border-color: var(--rh-line);
      background: var(--rh-surface-muted);
      color: var(--rh-accent-dark);
    }
    body[data-app-variant="raporhub"] .chat-prompt:hover {
      border-color: var(--rh-accent);
      background: var(--rh-surface);
    }
    body[data-app-variant="raporhub"] .chat-prompt.chat-prompt-feature {
      border-color: var(--rh-accent);
      background: var(--rh-accent);
      color: #ffffff;
    }
    body[data-app-variant="raporhub"] .chat-prompt.chat-prompt-feature:hover,
    body[data-app-variant="raporhub"] .chat-prompt.chat-prompt-feature:focus-visible {
      border-color: var(--rh-accent-dark);
      background: var(--rh-accent-dark);
      color: #ffffff;
    }
    body[data-app-variant="raporhub"].raporhub-dark .chat-prompt.chat-prompt-feature,
    body[data-app-variant="raporhub"].raporhub-dark .chat-prompt.chat-prompt-feature:hover,
    body[data-app-variant="raporhub"].raporhub-dark .chat-prompt.chat-prompt-feature:focus-visible {
      color: #062d22;
    }
    body[data-app-variant="raporhub"] .chat-input-row {
      display: flex;
      flex-direction: column;
      align-items: stretch;
      gap: 0;
      min-width: 0;
      width: calc(100% - 44px);
      max-width: 900px;
      flex: 0 0 auto;
      margin: 12px auto 8px;
      padding: 8px 8px 8px 14px;
      border: 1px solid var(--rh-line);
      border-radius: 24px;
      background: var(--rh-surface-muted);
      box-shadow: 0 8px 24px rgba(6, 78, 59, 0.08);
      transition: border-color 140ms ease, box-shadow 140ms ease;
    }
    body[data-app-variant="raporhub"] .chat-input-row:focus-within {
      border-color: var(--rh-accent);
      box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.12), 0 8px 24px rgba(6, 78, 59, 0.08);
    }
    body[data-app-variant="raporhub"] .chat-input-row textarea {
      width: 100%;
      min-width: 0;
      min-height: 40px;
      max-height: 150px;
      flex: 1 1 auto;
      resize: none;
      overflow-y: auto;
      border: 0;
      border-radius: 0;
      background: transparent;
      padding: 9px 4px 7px;
      line-height: 1.5;
    }
    body[data-app-variant="raporhub"] .chat-input-row textarea:focus {
      outline: 0;
      box-shadow: none;
    }
    body[data-app-variant="raporhub"] .chat-composer-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-width: 0;
    }
    body[data-app-variant="raporhub"] .chat-composer-options {
      display: flex;
      align-items: center;
      gap: 6px;
      min-width: 0;
      flex: 1 1 auto;
      overflow-x: auto;
      padding: 1px 0;
      scrollbar-width: thin;
    }
    body[data-app-variant="raporhub"] .chat-composer-options select {
      width: auto;
      min-width: 104px;
      max-width: 140px;
      height: 34px;
      flex: 0 0 auto;
      border-color: var(--rh-line);
      border-radius: 17px;
      background: var(--rh-surface);
      padding: 0 30px 0 11px;
      font-size: 11px;
    }
    body[data-app-variant="raporhub"] .chat-composer-options #chatRetrievalVersion {
      min-width: 126px;
    }
    body[data-app-variant="raporhub"] .chat-composer-options #chatMode {
      min-width: 94px;
    }
    body[data-app-variant="raporhub"] .chat-input-row .button {
      display: grid;
      place-items: center;
      width: 40px;
      min-width: 40px;
      height: 40px;
      min-height: 40px;
      flex: 0 0 40px;
      border-radius: 50%;
      padding: 0;
      font-size: 0;
    }
    body[data-app-variant="raporhub"] .chat-input-row .button::before {
      content: "\\2191";
      font-size: 22px;
      font-weight: 800;
      line-height: 1;
    }
    body[data-app-variant="raporhub"] .chat-input-row .button:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }
    body[data-app-variant="raporhub"] #chatStatus {
      flex: 0 0 auto;
      width: calc(100% - 44px);
      max-width: 900px;
      min-height: 28px;
      margin: 0 auto;
      padding: 0 0 12px;
      background: var(--rh-surface);
      font-size: 11px;
    }
    body[data-app-variant="raporhub"] .chat-source-head {
      flex: 0 0 auto;
      margin-bottom: 16px;
      padding-bottom: 14px;
      border-bottom: 1px solid var(--rh-line);
    }
    body[data-app-variant="raporhub"] .chat-side .cards {
      flex: 1 1 auto;
      min-height: 0;
      overflow-y: auto;
      padding-right: 3px;
    }

    body[data-app-variant="raporhub"].raporhub-dark {
      scrollbar-color: #46685a var(--rh-canvas);
    }
    body[data-app-variant="raporhub"].raporhub-dark input,
    body[data-app-variant="raporhub"].raporhub-dark select,
    body[data-app-variant="raporhub"].raporhub-dark textarea {
      color: var(--rh-ink);
    }
    body[data-app-variant="raporhub"].raporhub-dark input::placeholder,
    body[data-app-variant="raporhub"].raporhub-dark textarea::placeholder {
      color: #8ca99d;
    }
    body[data-app-variant="raporhub"].raporhub-dark .raporhub-system-popover div,
    body[data-app-variant="raporhub"].raporhub-dark .raporhub-panel-heading,
    body[data-app-variant="raporhub"].raporhub-dark .raporhub-document-row,
    body[data-app-variant="raporhub"].raporhub-dark .raporhub-system-facts,
    body[data-app-variant="raporhub"].raporhub-dark .raporhub-system-facts div,
    body[data-app-variant="raporhub"].raporhub-dark .raporhub-skeleton-row {
      border-color: var(--rh-line);
    }
    body[data-app-variant="raporhub"].raporhub-dark .secondary,
    body[data-app-variant="raporhub"].raporhub-dark .comparison-swap:hover {
      background: #2b4037;
      color: var(--rh-accent-dark);
    }
    body[data-app-variant="raporhub"].raporhub-dark .upload-card,
    body[data-app-variant="raporhub"].raporhub-dark .panel,
    body[data-app-variant="raporhub"].raporhub-dark .stat-card,
    body[data-app-variant="raporhub"].raporhub-dark .table-box,
    body[data-app-variant="raporhub"].raporhub-dark .catalog-pane,
    body[data-app-variant="raporhub"].raporhub-dark .catalog-candidate-cell,
    body[data-app-variant="raporhub"].raporhub-dark .catalog-candidate-item,
    body[data-app-variant="raporhub"].raporhub-dark .answer-box,
    body[data-app-variant="raporhub"].raporhub-dark .draft-box,
    body[data-app-variant="raporhub"].raporhub-dark .source-card,
    body[data-app-variant="raporhub"].raporhub-dark .result-card,
    body[data-app-variant="raporhub"].raporhub-dark .similar-card,
    body[data-app-variant="raporhub"].raporhub-dark .comparison-source select,
    body[data-app-variant="raporhub"].raporhub-dark .comparison-swap,
    body[data-app-variant="raporhub"].raporhub-dark .comparison-info-button,
    body[data-app-variant="raporhub"].raporhub-dark .comparison-evidence,
    body[data-app-variant="raporhub"].raporhub-dark .comparison-pair-marker,
    body[data-app-variant="raporhub"].raporhub-dark .comparison-pdf-toolbar,
    body[data-app-variant="raporhub"].raporhub-dark .graph-sidebar,
    body[data-app-variant="raporhub"].raporhub-dark .graph-main,
    body[data-app-variant="raporhub"].raporhub-dark .category-button,
    body[data-app-variant="raporhub"].raporhub-dark .document-table-wrap,
    body[data-app-variant="raporhub"].raporhub-dark .chat-source-card {
      border-color: var(--rh-line);
      background: var(--rh-surface);
      color: var(--rh-ink);
    }
    body[data-app-variant="raporhub"].raporhub-dark .catalog-pane-actions,
    body[data-app-variant="raporhub"].raporhub-dark .catalog-count,
    body[data-app-variant="raporhub"].raporhub-dark .log-details summary,
    body[data-app-variant="raporhub"].raporhub-dark .draft-hint,
    body[data-app-variant="raporhub"].raporhub-dark .chat-prompt,
    body[data-app-variant="raporhub"].raporhub-dark .tag-chip,
    body[data-app-variant="raporhub"].raporhub-dark .tag,
    body[data-app-variant="raporhub"].raporhub-dark .doc-tag {
      border-color: var(--rh-line);
      background: var(--rh-surface-muted);
      color: var(--rh-accent-dark);
    }
    body[data-app-variant="raporhub"].raporhub-dark .chat-prompt.chat-prompt-feature,
    body[data-app-variant="raporhub"].raporhub-dark .chat-prompt.chat-prompt-feature:hover,
    body[data-app-variant="raporhub"].raporhub-dark .chat-prompt.chat-prompt-feature:focus-visible {
      border-color: var(--rh-accent);
      background: var(--rh-accent);
      color: #062d22;
    }
    body[data-app-variant="raporhub"].raporhub-dark .catalog-pane.ingested .catalog-pane-head {
      background: #263f36;
      color: #8bd4ad;
    }
    body[data-app-variant="raporhub"].raporhub-dark .catalog-pane.pending .catalog-pane-head {
      background: #3a3430;
      color: #e1b66d;
    }
    body[data-app-variant="raporhub"].raporhub-dark .table-box th,
    body[data-app-variant="raporhub"].raporhub-dark .catalog-table th,
    body[data-app-variant="raporhub"].raporhub-dark .document-table th,
    body[data-app-variant="raporhub"].raporhub-dark table thead th {
      background: #2b4037;
      color: #dcece5;
    }
    body[data-app-variant="raporhub"].raporhub-dark .table-box th,
    body[data-app-variant="raporhub"].raporhub-dark .table-box td,
    body[data-app-variant="raporhub"].raporhub-dark .catalog-table th,
    body[data-app-variant="raporhub"].raporhub-dark .catalog-table td,
    body[data-app-variant="raporhub"].raporhub-dark .document-table th,
    body[data-app-variant="raporhub"].raporhub-dark .document-table td,
    body[data-app-variant="raporhub"].raporhub-dark .comparison-row {
      border-color: var(--rh-line);
    }
    body[data-app-variant="raporhub"].raporhub-dark table tbody tr:hover,
    body[data-app-variant="raporhub"].raporhub-dark .category-button:hover,
    body[data-app-variant="raporhub"].raporhub-dark .category-button.active,
    body[data-app-variant="raporhub"].raporhub-dark .raporhub-document-row:hover {
      background: #294036;
      color: var(--rh-accent-dark);
    }
    body[data-app-variant="raporhub"].raporhub-dark .raporhub-file-badge {
      background: #26463f;
      color: #8ed5ca;
    }
    body[data-app-variant="raporhub"].raporhub-dark .raporhub-file-badge.type-docx {
      background: #293f52;
      color: #91badc;
    }
    body[data-app-variant="raporhub"].raporhub-dark .raporhub-file-badge.type-pptx {
      background: #493728;
      color: #efb77e;
    }
    body[data-app-variant="raporhub"].raporhub-dark .raporhub-ready-badge {
      border-color: #3c7257;
      background: #243c32;
      color: #8dd3aa;
    }
    body[data-app-variant="raporhub"].raporhub-dark .raporhub-ready-badge.partial {
      border-color: #725c36;
      background: #3b3428;
      color: #e4bd78;
    }
    body[data-app-variant="raporhub"].raporhub-dark .raporhub-coverage-track,
    body[data-app-variant="raporhub"].raporhub-dark .density-track,
    body[data-app-variant="raporhub"].raporhub-dark .comparison-pdf-frame {
      background: #1b2422;
    }
    body[data-app-variant="raporhub"].raporhub-dark .status.ok {
      border-color: #35634d;
      background: #223c31;
      color: #8bd4aa;
    }
    body[data-app-variant="raporhub"].raporhub-dark .status.error {
      border-color: #74434a;
      background: #422c30;
      color: #ff9aa5;
    }
    body[data-app-variant="raporhub"].raporhub-dark .status-pill.complete {
      background: #263f51;
      color: #91c5e6;
    }
    body[data-app-variant="raporhub"].raporhub-dark .status-pill.partial,
    body[data-app-variant="raporhub"].raporhub-dark .status-pill.missing {
      background: #453a25;
      color: #e5bd70;
    }
    body[data-app-variant="raporhub"].raporhub-dark .status-pill.not_ingested {
      background: #4b3035;
      color: #ef9da8;
    }
    body[data-app-variant="raporhub"].raporhub-dark .chat-message-meta {
      color: #9fb2ae;
    }
    body[data-app-variant="raporhub"].raporhub-dark mark {
      background: #796a31;
      color: #fff3c9;
      box-shadow: none;
    }

    @media (max-width: 1220px) {
      body[data-app-variant="raporhub"] .raporhub-topbar {
        right: 12px;
        gap: 10px;
        padding: 0;
      }
      body[data-app-variant="raporhub"] .chat-toolbar {
        grid-template-columns: 1fr;
        align-items: start;
      }
      body[data-app-variant="raporhub"] .chat-toolbar-actions {
        justify-content: flex-start;
      }
    }

    @media (max-width: 980px) {
      body[data-app-variant="raporhub"] .card {
        display: flex;
        flex-direction: column;
        min-width: 0;
      }
      body[data-app-variant="raporhub"] .hero {
        position: relative;
        width: 100%;
        min-height: 0;
        max-height: none;
        overflow: visible;
        padding: 14px 16px 12px;
      }
      body[data-app-variant="raporhub"] .hero-title-row {
        display: flex;
        align-items: center;
      }
      body[data-app-variant="raporhub"] .hero h1 {
        font-size: 20px;
      }
      body[data-app-variant="raporhub"] .raporhub-brand-subtitle,
      body[data-app-variant="raporhub"] .raporhub-sidebar-footer,
      body[data-app-variant="raporhub"] .raporhub-nav-label {
        display: none;
      }
      body[data-app-variant="raporhub"] .module-switcher {
        display: flex;
        flex-direction: row;
        flex-wrap: nowrap;
        gap: 6px;
        margin-top: 12px;
        padding-bottom: 2px;
        overflow-x: auto;
      }
      body[data-app-variant="raporhub"] .module-filter {
        width: auto;
        min-height: 36px;
        flex: 0 0 auto;
        border: 1px solid rgba(255, 255, 255, 0.14);
        padding: 8px 11px;
      }
      body[data-app-variant="raporhub"] .module-filter.active::before {
        display: none;
      }
      body[data-app-variant="raporhub"] .raporhub-topbar {
        position: absolute;
        top: 12px;
        right: 12px;
        display: flex;
        width: auto;
        min-height: 0;
        padding: 0;
      }
      body[data-app-variant="raporhub"] .raporhub-sidebar-toggle {
        display: none;
      }
      body[data-app-variant="raporhub"] .section {
        order: 1;
        width: 100%;
        min-height: calc(100vh - 124px);
        padding: 22px 18px 36px;
      }
      body[data-app-variant="raporhub"] .upload-grid,
      body[data-app-variant="raporhub"] .split,
      body[data-app-variant="raporhub"] .chat-layout,
      body[data-app-variant="raporhub"].chat-focus .chat-layout,
      body[data-app-variant="raporhub"] .raporhub-overview-grid {
        grid-template-columns: minmax(0, 1fr);
      }
      body[data-app-variant="raporhub"] .upload-grid > *,
      body[data-app-variant="raporhub"] .split > *,
      body[data-app-variant="raporhub"] .chat-layout > *,
      body[data-app-variant="raporhub"] .raporhub-overview-grid > * {
        min-width: 0;
      }
      body[data-app-variant="raporhub"] .raporhub-metric-strip {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      body[data-app-variant="raporhub"] .raporhub-metric-strip > div:nth-child(2) {
        border-right: 0;
      }
      body[data-app-variant="raporhub"] .raporhub-metric-strip > div:nth-child(-n + 2) {
        border-bottom: 1px solid var(--rh-line);
      }
      body[data-app-variant="raporhub"] .chat-panel {
        min-height: 580px;
      }
      body[data-app-variant="raporhub"] .section[data-module-key="chat"] {
        height: auto;
        min-height: calc(100vh - 124px);
        overflow: visible;
      }
      body[data-app-variant="raporhub"] .chat-layout,
      body[data-app-variant="raporhub"].chat-focus .chat-layout {
        height: auto;
      }
      body[data-app-variant="raporhub"] .chat-side {
        min-height: 320px;
        border-left: 0;
        border-top: 1px solid var(--rh-line);
        padding: 22px 20px;
      }
      body[data-app-variant="raporhub"] .chat-side::before {
        display: none;
      }
    }

    @media (max-width: 620px) {
      body[data-app-variant="raporhub"] .wrap,
      body[data-app-variant="raporhub"] .stack,
      body[data-app-variant="raporhub"] .card,
      body[data-app-variant="raporhub"] .section,
      body[data-app-variant="raporhub"] .panel,
      body[data-app-variant="raporhub"] .upload-card {
        max-width: 100%;
        min-width: 0;
      }
      body[data-app-variant="raporhub"] .raporhub-topbar {
        top: 10px;
        right: 10px;
        min-height: 0;
        padding: 0;
      }
      body[data-app-variant="raporhub"] .raporhub-system-menu {
        display: block;
      }
      body[data-app-variant="raporhub"] .section {
        min-height: calc(100vh - 122px);
        padding: 18px 12px 30px;
      }
      body[data-app-variant="raporhub"] .section-head {
        align-items: flex-start;
        padding-right: 0;
      }
      body[data-app-variant="raporhub"] .section-head h2 {
        font-size: 20px;
      }
      body[data-app-variant="raporhub"] .raporhub-welcome-band {
        align-items: flex-start;
        flex-direction: column;
        gap: 14px;
      }
      body[data-app-variant="raporhub"] .raporhub-welcome-band h2 {
        font-size: 21px;
      }
      body[data-app-variant="raporhub"] .raporhub-question-workspace,
      body[data-app-variant="raporhub"] .raporhub-recent-workspace,
      body[data-app-variant="raporhub"] .raporhub-readiness-panel,
      body[data-app-variant="raporhub"] .section[data-module-key="upload"] .uploaded-documents-panel {
        padding: 14px;
      }
      body[data-app-variant="raporhub"] .raporhub-question-row {
        grid-template-columns: minmax(0, 1fr);
      }
      body[data-app-variant="raporhub"] .raporhub-question-row .button {
        width: 100%;
      }
      body[data-app-variant="raporhub"] .raporhub-metric-strip > div {
        padding: 12px;
      }
      body[data-app-variant="raporhub"] .raporhub-metric-strip strong {
        font-size: 17px;
      }
      body[data-app-variant="raporhub"] .raporhub-document-row {
        grid-template-columns: 40px minmax(0, 1fr) 24px;
        gap: 9px;
      }
      body[data-app-variant="raporhub"] .raporhub-document-meta {
        display: none;
      }
      body[data-app-variant="raporhub"] .chat-toolbar-actions select,
      body[data-app-variant="raporhub"] .chat-toolbar-actions .button {
        flex: 1 1 120px;
        width: auto;
        max-width: none;
      }
      body[data-app-variant="raporhub"] .chat-message {
        max-width: 94%;
      }
      body[data-app-variant="raporhub"] .chat-input-row {
        width: calc(100% - 28px);
      }
      body[data-app-variant="raporhub"] .chat-input-row .button {
        width: 40px;
        min-width: 40px;
      }
      body[data-app-variant="raporhub"] .chat-toolbar,
      body[data-app-variant="raporhub"] .chat-messages,
      body[data-app-variant="raporhub"] .chat-prompts {
        padding-left: 14px;
        padding-right: 14px;
      }
      body[data-app-variant="raporhub"] #chatStatus {
        width: calc(100% - 28px);
      }
    }

    @media (prefers-reduced-motion: reduce) {
      body[data-app-variant="raporhub"] .card,
      body[data-app-variant="raporhub"] .hero {
        transition: none;
      }
      body[data-app-variant="raporhub"] .raporhub-skeleton-row {
        animation: none;
      }
      body[data-app-variant="raporhub"] .raporhub-coverage-track span {
        transition: none;
      }
    }
"""


def get_variant_css(app_variant: str) -> str:
    if app_variant == "raporhub":
        return RAPORHUB_CSS
    if app_variant == "repocto":
        repocto_base = RAPORHUB_CSS.replace(
            'data-app-variant="raporhub"',
            'data-app-variant="repocto"',
        )
        return f"{repocto_base}\n{REPOCTO_CSS}"
    return ""
