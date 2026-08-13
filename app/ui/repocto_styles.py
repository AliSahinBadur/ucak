from __future__ import annotations


REPOCTO_CSS = """
    body[data-app-variant="repocto"] {
      --rh-canvas: #f2eadf;
      --rh-surface: #fffaf2;
      --rh-surface-muted: #eee4f0;
      --rh-sidebar: #281638;
      --rh-sidebar-soft: #3a214d;
      --rh-ink: #281636;
      --rh-muted: #74657d;
      --rh-line: #cdbfd1;
      --rh-accent: #2f9499;
      --rh-accent-dark: #5b3475;
      --rh-amber: #c28b3c;
      --rh-blue: #427b9b;
      --rh-topbar: rgba(255, 250, 242, 0.97);
      background: var(--rh-canvas);
      color: var(--rh-ink);
    }

    body[data-app-variant="repocto"].raporhub-dark {
      --rh-canvas: #17101e;
      --rh-surface: #24182d;
      --rh-surface-muted: #30203b;
      --rh-sidebar: #100a16;
      --rh-sidebar-soft: #2b1938;
      --rh-ink: #f7eef8;
      --rh-muted: #c2b2c8;
      --rh-line: #55415f;
      --rh-accent: #58c4c2;
      --rh-accent-dark: #b68ace;
      --rh-amber: #d2a65a;
      --rh-blue: #74a7c2;
      --rh-topbar: rgba(36, 24, 45, 0.97);
      --panel: var(--rh-surface);
      --line: var(--rh-line);
      --text: var(--rh-ink);
      --muted: var(--rh-muted);
      --accent: var(--rh-accent);
      --accent-strong: var(--rh-accent-dark);
      --soft: #352440;
      --soft-2: #21172a;
      --ok: #72d2c8;
      --error: #ff9ca8;
      color-scheme: dark;
    }

    body[data-app-variant="repocto"] .card {
      grid-template-columns: 286px minmax(0, 1fr);
      background: var(--rh-canvas);
      transition: grid-template-columns 180ms ease;
    }

    body[data-app-variant="repocto"] .hero {
      width: 286px;
      padding: 20px 14px 16px;
      background: var(--rh-sidebar);
      border-right: 1px solid rgba(255, 255, 255, 0.12);
    }

    body[data-app-variant="repocto"] .hero-title-row {
      position: relative;
      align-items: flex-start;
      gap: 8px;
    }

    body[data-app-variant="repocto"] .hero h1 {
      display: block;
      width: 205px;
      height: 64px;
      min-height: 64px;
      overflow: hidden;
      border: 1px solid rgba(210, 188, 218, 0.5);
      border-radius: 6px;
      background: #fff8ed url('/repocto-landing/assets/repocto-wordmark.png') center / 188px auto no-repeat;
      box-shadow: 0 12px 28px rgba(8, 3, 13, 0.2);
      color: transparent;
      font-size: 0;
      text-indent: -9999px;
    }

    body[data-app-variant="repocto"] .raporhub-sidebar-toggle {
      position: absolute;
      top: 17px;
      right: -4px;
      width: 32px;
      height: 32px;
      border-color: rgba(255, 255, 255, 0.24);
      background: #3b2449;
      color: #ffffff;
    }

    body[data-app-variant="repocto"] .raporhub-brand-subtitle {
      margin: 13px 4px 0;
      padding: 0 0 18px;
      color: #cdb6d7;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0;
      text-transform: uppercase;
    }

    body[data-app-variant="repocto"] .module-switcher {
      gap: 4px;
      margin-top: 14px;
    }

    body[data-app-variant="repocto"] .raporhub-nav-label {
      margin: 17px 10px 5px;
      color: #9ed1ce;
      font-size: 9px;
    }

    body[data-app-variant="repocto"] .module-filter {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      align-items: center;
      gap: 0;
      min-height: 42px;
      padding: 6px 10px;
      border: 1px solid transparent;
      border-radius: 5px;
      color: #e2d6e7;
      font-size: 12px;
    }

    body[data-app-variant="repocto"] .module-filter::before {
      content: none;
      display: none;
    }

    body[data-app-variant="repocto"] .module-filter:hover {
      border-color: rgba(255, 255, 255, 0.08);
      background: #3a214d;
    }

    body[data-app-variant="repocto"] .module-filter.active {
      border-color: #d4c0db;
      background: #fff8ed;
      color: #4b2862;
      box-shadow: 0 9px 22px rgba(7, 3, 12, 0.2);
    }

    body[data-app-variant="repocto"] .module-filter.active::before {
      content: none;
    }

    body[data-app-variant="repocto"] .raporhub-sidebar-footer {
      margin: auto 2px 0;
      padding: 16px 7px 2px;
      border-top-color: rgba(255, 255, 255, 0.13);
    }

    body[data-app-variant="repocto"] .raporhub-local-status {
      color: #c6e7e1;
    }

    body[data-app-variant="repocto"] .raporhub-local-status span {
      background: #51c7bc;
      box-shadow: 0 0 0 4px rgba(81, 199, 188, 0.12);
    }

    body[data-app-variant="repocto"] .raporhub-topbar {
      position: absolute;
      left: auto;
      right: 14px;
      top: 10px;
      z-index: 40;
      display: flex;
      justify-content: flex-end;
      width: auto;
      min-height: 0;
      padding: 0;
      border: 0;
      background: transparent;
      box-shadow: none;
      backdrop-filter: none;
    }

    body[data-app-variant="repocto"] .repocto-page-context {
      display: none !important;
    }

    body[data-app-variant="repocto"] .repocto-page-context span {
      color: var(--rh-accent);
      font-size: 9px;
      font-weight: 900;
      text-transform: uppercase;
    }

    body[data-app-variant="repocto"] .repocto-page-context strong {
      color: var(--rh-ink);
      font-family: Georgia, 'Times New Roman', serif;
      font-size: 22px;
      font-weight: 500;
    }

    body[data-app-variant="repocto"] .raporhub-theme-toggle,
    body[data-app-variant="repocto"] .raporhub-system-menu > summary {
      min-height: 36px;
      border-color: var(--rh-line);
      border-radius: 5px;
      background: var(--rh-surface);
    }

    body[data-app-variant="repocto"] .section {
      padding: 98px clamp(22px, 3.2vw, 52px) 42px;
    }

    body[data-app-variant="repocto"] .section:not(.raporhub-home) {
      width: min(100%, 1540px);
      margin: 0 auto;
    }

    body[data-app-variant="repocto"] .section-head {
      align-items: end;
      margin-bottom: 22px;
      padding-bottom: 17px;
      border-bottom: 1px solid var(--rh-line);
    }

    body[data-app-variant="repocto"] .section-head h2,
    body[data-app-variant="repocto"] .raporhub-welcome-band h2 {
      font-family: Georgia, 'Times New Roman', serif;
      font-weight: 500;
      letter-spacing: 0;
    }

    body[data-app-variant="repocto"] .section-head h2 {
      font-size: clamp(28px, 3vw, 42px);
    }

    body[data-app-variant="repocto"] .section-head p {
      max-width: 720px;
      color: var(--rh-muted);
    }

    body[data-app-variant="repocto"] .repocto-library {
      display: grid;
      gap: 15px;
    }

    body[data-app-variant="repocto"] .repocto-library-hero {
      display: grid;
      grid-template-columns: minmax(280px, 0.9fr) minmax(420px, 1.1fr);
      gap: 30px;
      align-items: end;
      overflow: hidden;
      padding: 30px clamp(24px, 3vw, 44px);
      border: 1px solid #4f3260;
      border-radius: 6px;
      background: linear-gradient(128deg, #281638 0%, #3c2450 74%, #2d6e76 150%);
      color: #ffffff;
      box-shadow: 0 18px 42px rgba(52, 29, 68, 0.16);
    }

    body[data-app-variant="repocto"] .repocto-library-eyebrow {
      color: #85d8cf;
      font-size: 10px;
      font-weight: 900;
      letter-spacing: 0.15em;
    }

    body[data-app-variant="repocto"] .repocto-library-hero h2 {
      margin: 8px 0 6px;
      color: #ffffff;
      font-family: Georgia, 'Times New Roman', serif;
      font-size: clamp(34px, 3.7vw, 52px);
      font-weight: 500;
    }

    body[data-app-variant="repocto"] .repocto-library-hero p {
      max-width: 680px;
      margin: 0;
      color: rgba(255, 255, 255, 0.72);
      line-height: 1.6;
    }

    body[data-app-variant="repocto"] .repocto-library-path {
      display: grid;
      gap: 8px;
      padding: 17px;
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: 5px;
      background: rgba(16, 8, 23, 0.34);
    }

    body[data-app-variant="repocto"] .repocto-library-path label {
      color: #b9e5df;
      font-size: 10px;
      font-weight: 900;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    body[data-app-variant="repocto"] .repocto-library-path > div {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
    }

    body[data-app-variant="repocto"] .repocto-library-path input {
      min-width: 0;
      border-color: rgba(255, 255, 255, 0.28);
      background: #fffaf2;
      color: #30203d;
      font-family: Consolas, monospace;
    }

    body[data-app-variant="repocto"] .repocto-library-path .button.primary {
      border-color: #56bdb7;
      background: #318f95;
    }

    body[data-app-variant="repocto"] .repocto-library-pipeline {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      overflow: hidden;
      border: 1px solid var(--rh-line);
      border-radius: 6px;
      background: var(--rh-line);
      gap: 1px;
    }

    body[data-app-variant="repocto"] .repocto-library-pipeline > div {
      display: grid;
      grid-template-columns: 34px minmax(0, 1fr);
      gap: 11px;
      align-items: center;
      min-height: 70px;
      padding: 13px 16px;
      background: var(--rh-surface);
    }

    body[data-app-variant="repocto"] .repocto-library-pipeline b {
      display: grid;
      place-items: center;
      width: 32px;
      height: 32px;
      border: 1px solid #bba9c3;
      border-radius: 50%;
      color: #68427c;
      font-size: 10px;
    }

    body[data-app-variant="repocto"] .repocto-library-pipeline span,
    body[data-app-variant="repocto"] .repocto-library-pipeline strong,
    body[data-app-variant="repocto"] .repocto-library-pipeline small {
      display: block;
    }

    body[data-app-variant="repocto"] .repocto-library-pipeline strong {
      font-size: 12px;
    }

    body[data-app-variant="repocto"] .repocto-library-pipeline small {
      margin-top: 3px;
      color: var(--rh-muted);
      font-size: 9px;
    }

    body[data-app-variant="repocto"] .repocto-library-status {
      padding: 12px 15px;
      border: 1px solid #b7d9d4;
      border-left: 4px solid #349a9c;
      border-radius: 5px;
      background: #edf7f4;
      color: #285f64;
      font-size: 12px;
    }

    body[data-app-variant="repocto"].raporhub-dark .repocto-library-status {
      border-color: #416b6a;
      background: #203638;
      color: #a7ded9;
    }

    body[data-app-variant="repocto"] .repocto-library-controls {
      display: grid;
      grid-template-columns: auto minmax(180px, 1fr) auto 150px auto;
      gap: 9px;
      align-items: center;
      padding: 12px 15px;
      border: 1px solid var(--rh-line);
      border-radius: 6px;
      background: var(--rh-surface);
    }

    body[data-app-variant="repocto"] .repocto-library-controls label {
      color: #57336a;
      font-size: 9px;
      font-weight: 900;
      text-transform: uppercase;
    }

    body[data-app-variant="repocto"] .repocto-library-controls input,
    body[data-app-variant="repocto"] .repocto-library-controls select {
      min-width: 0;
      min-height: 38px;
    }

    body[data-app-variant="repocto"] .repocto-library-workspace {
      display: grid;
      grid-template-columns: minmax(255px, 0.86fr) minmax(270px, 1.02fr) minmax(245px, 0.82fr);
      min-height: 500px;
      overflow: hidden;
      border: 1px solid var(--rh-line);
      border-radius: 6px;
      background: var(--rh-surface);
      box-shadow: 0 10px 28px rgba(52, 29, 68, 0.07);
    }

    body[data-app-variant="repocto"] .repocto-library-tree-pane,
    body[data-app-variant="repocto"] .repocto-library-map-pane,
    body[data-app-variant="repocto"] .repocto-library-detail-pane {
      min-width: 0;
      padding: 18px;
    }

    body[data-app-variant="repocto"] .repocto-library-map-pane,
    body[data-app-variant="repocto"] .repocto-library-detail-pane {
      border-left: 1px solid var(--rh-line);
    }

    body[data-app-variant="repocto"] .repocto-library-detail-pane {
      background: var(--rh-surface-muted);
    }

    body[data-app-variant="repocto"] .repocto-library-pane-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      padding-bottom: 13px;
      border-bottom: 1px solid var(--rh-line);
    }

    body[data-app-variant="repocto"] .repocto-library-pane-head strong {
      color: #57336a;
      font-size: 12px;
      letter-spacing: 0.03em;
      text-transform: uppercase;
    }

    body[data-app-variant="repocto"] .repocto-library-pane-head span {
      color: var(--rh-muted);
      font-size: 10px;
    }

    body[data-app-variant="repocto"] .repocto-library-tree {
      max-height: 630px;
      overflow: auto;
      padding: 12px 3px 10px;
      scrollbar-width: thin;
    }

    body[data-app-variant="repocto"] .repocto-library-map {
      max-height: 630px;
      overflow: auto;
      padding: 20px 12px 24px;
      scrollbar-width: thin;
    }

    body[data-app-variant="repocto"] .repocto-library-map-root {
      position: relative;
      width: fit-content;
      margin: 0 auto 31px;
      padding: 11px 18px;
      border-radius: 5px;
      background: #59346d;
      color: #fff;
      font-size: 11px;
      font-weight: 900;
    }

    body[data-app-variant="repocto"] .repocto-library-map-root::after {
      position: absolute;
      top: 100%;
      left: 50%;
      width: 1px;
      height: 22px;
      background: var(--rh-line);
      content: '';
    }

    body[data-app-variant="repocto"] .repocto-library-map-list {
      display: grid;
      gap: 6px;
    }

    body[data-app-variant="repocto"] .repocto-library-map-node {
      position: relative;
      display: grid;
      grid-template-columns: 32px minmax(0, 1fr);
      gap: 8px;
      align-items: center;
      min-height: 42px;
      margin-left: calc((var(--map-depth) - 1) * 15px);
      padding: 6px 8px;
      border: 1px solid var(--rh-line);
      border-radius: 4px;
      background: var(--rh-surface);
    }

    body[data-app-variant="repocto"] .repocto-library-map-node::before {
      position: absolute;
      right: 100%;
      top: 50%;
      width: 12px;
      height: 1px;
      background: var(--rh-line);
      content: '';
    }

    body[data-app-variant="repocto"] .repocto-library-map-node span {
      display: grid;
      place-items: center;
      width: 30px;
      height: 28px;
      border-radius: 4px;
      background: #eaddec;
      color: #57336a;
      font-size: 8px;
      font-weight: 900;
    }

    body[data-app-variant="repocto"] .repocto-library-map-node.document span {
      background: #d7efeb;
      color: #286d70;
    }

    body[data-app-variant="repocto"] .repocto-library-map-node strong {
      min-width: 0;
      overflow: hidden;
      font-size: 10px;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    body[data-app-variant="repocto"] .repocto-library-folder > summary {
      display: flex;
      gap: 8px;
      align-items: center;
      min-height: 35px;
      margin-left: calc(var(--library-depth) * 14px);
      padding: 5px 8px;
      border-radius: 4px;
      cursor: pointer;
      list-style: none;
    }

    body[data-app-variant="repocto"] .repocto-library-folder > summary::-webkit-details-marker {
      display: none;
    }

    body[data-app-variant="repocto"] .repocto-library-folder > summary:hover {
      background: var(--rh-surface-muted);
    }

    body[data-app-variant="repocto"] .repocto-library-folder > summary::before {
      content: '›';
      color: var(--rh-muted);
      font-size: 16px;
      transform: rotate(0);
    }

    body[data-app-variant="repocto"] .repocto-library-folder[open] > summary::before {
      transform: rotate(90deg);
    }

    body[data-app-variant="repocto"] .repocto-library-folder-icon {
      position: relative;
      width: 17px;
      height: 12px;
      border-radius: 2px;
      background: #d19a45;
    }

    body[data-app-variant="repocto"] .repocto-library-folder-icon::before {
      content: '';
      position: absolute;
      left: 2px;
      top: -3px;
      width: 8px;
      height: 4px;
      border-radius: 2px 2px 0 0;
      background: #e0b05e;
    }

    body[data-app-variant="repocto"] .repocto-library-folder > summary strong {
      min-width: 0;
      overflow: hidden;
      color: var(--rh-ink);
      font-size: 12px;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    body[data-app-variant="repocto"] .repocto-library-folder > summary small {
      margin-left: auto;
      color: var(--rh-muted);
      font-size: 9px;
    }

    body[data-app-variant="repocto"] .repocto-library-document {
      display: grid;
      grid-template-columns: 42px minmax(0, 1fr);
      gap: 10px;
      align-items: center;
      width: calc(100% - calc(var(--library-depth) * 14px));
      min-height: 54px;
      margin: 3px 0 3px calc(var(--library-depth) * 14px);
      padding: 7px 9px;
      border: 1px solid transparent;
      background: transparent;
      color: var(--rh-ink);
      text-align: left;
    }

    body[data-app-variant="repocto"] .repocto-library-document:hover,
    body[data-app-variant="repocto"] .repocto-library-document.active {
      border-color: #b9a6c1;
      background: #f2e8f3;
    }

    body[data-app-variant="repocto"].raporhub-dark .repocto-library-document:hover,
    body[data-app-variant="repocto"].raporhub-dark .repocto-library-document.active {
      background: #352440;
    }

    body[data-app-variant="repocto"] .repocto-library-file-icon,
    body[data-app-variant="repocto"] .repocto-library-document-icon {
      display: grid;
      place-items: center;
      border: 1px solid #6e4a80;
      border-radius: 4px;
      background: #57336b;
      color: #ffffff;
      font-size: 9px;
      font-weight: 900;
    }

    body[data-app-variant="repocto"] .repocto-library-file-icon {
      width: 38px;
      height: 38px;
    }

    body[data-app-variant="repocto"] .repocto-library-document > span:last-child,
    body[data-app-variant="repocto"] .repocto-library-document strong,
    body[data-app-variant="repocto"] .repocto-library-document small {
      display: block;
      min-width: 0;
    }

    body[data-app-variant="repocto"] .repocto-library-document strong {
      overflow: hidden;
      font-size: 11px;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    body[data-app-variant="repocto"] .repocto-library-document small {
      margin-top: 4px;
      color: var(--rh-muted);
      font-size: 9px;
    }

    body[data-app-variant="repocto"] .repocto-library-empty,
    body[data-app-variant="repocto"] .repocto-library-detail-empty {
      padding: 34px 18px;
      color: var(--rh-muted);
      text-align: center;
    }

    body[data-app-variant="repocto"] .repocto-library-detail {
      display: grid;
      gap: 18px;
      justify-items: start;
      padding: 28px 10px;
    }

    body[data-app-variant="repocto"] .repocto-library-detail-empty span,
    body[data-app-variant="repocto"] .repocto-library-document-icon {
      width: 66px;
      height: 66px;
      margin: 0 auto 15px;
    }

    body[data-app-variant="repocto"] .repocto-library-detail-empty strong,
    body[data-app-variant="repocto"] .repocto-library-detail-empty p {
      display: block;
    }

    body[data-app-variant="repocto"] .repocto-library-detail-empty strong {
      color: var(--rh-ink);
    }

    body[data-app-variant="repocto"] .repocto-library-detail-empty p {
      max-width: 330px;
      margin: 8px auto 0;
      line-height: 1.6;
    }

    body[data-app-variant="repocto"] .repocto-library-document-copy {
      width: 100%;
    }

    body[data-app-variant="repocto"] .repocto-library-document-copy > span,
    body[data-app-variant="repocto"] .repocto-library-document-path > span {
      color: #2d9295;
      font-size: 9px;
      font-weight: 900;
      letter-spacing: 0.08em;
    }

    body[data-app-variant="repocto"] .repocto-library-document-copy h3 {
      margin: 7px 0 20px;
      overflow-wrap: anywhere;
      font-family: Georgia, 'Times New Roman', serif;
      font-size: 23px;
      font-weight: 500;
    }

    body[data-app-variant="repocto"] .repocto-library-document-copy dl {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 1px;
      overflow: hidden;
      margin: 0;
      border: 1px solid var(--rh-line);
      border-radius: 5px;
      background: var(--rh-line);
    }

    body[data-app-variant="repocto"] .repocto-library-document-copy dl div {
      padding: 12px;
      background: var(--rh-surface);
    }

    body[data-app-variant="repocto"] .repocto-library-document-copy dt {
      color: var(--rh-muted);
      font-size: 9px;
    }

    body[data-app-variant="repocto"] .repocto-library-document-copy dd {
      margin: 5px 0 0;
      overflow-wrap: anywhere;
      font-size: 11px;
      font-weight: 800;
    }

    body[data-app-variant="repocto"] .repocto-library-document-path {
      margin-top: 16px;
      padding: 14px;
      border: 1px solid var(--rh-line);
      border-radius: 5px;
      background: var(--rh-surface);
    }

    body[data-app-variant="repocto"] .repocto-library-document-path code {
      display: block;
      margin-top: 8px;
      overflow-wrap: anywhere;
      color: var(--rh-ink);
      font-family: Consolas, monospace;
      font-size: 10px;
      line-height: 1.6;
    }

    body[data-app-variant="repocto"] .button,
    body[data-app-variant="repocto"] button,
    body[data-app-variant="repocto"] input,
    body[data-app-variant="repocto"] select,
    body[data-app-variant="repocto"] textarea {
      border-radius: 5px;
    }

    body[data-app-variant="repocto"] .button.primary {
      border-color: #59346d;
      background: #59346d;
      color: #ffffff;
    }

    body[data-app-variant="repocto"] .button.primary:hover {
      border-color: #442653;
      background: #442653;
    }

    body[data-app-variant="repocto"] .button.secondary {
      border-color: #bca9c4;
      background: #fffaf2;
      color: #4d2b5f;
    }

    body[data-app-variant="repocto"] .raporhub-home {
      width: min(100%, 1560px);
      margin: 0 auto;
    }

    body[data-app-variant="repocto"] .raporhub-welcome-band {
      position: relative;
      min-height: 222px;
      overflow: hidden;
      padding: clamp(30px, 4vw, 58px);
      border: 1px solid #4f3260;
      border-radius: 6px;
      background: #352044;
      color: #ffffff;
      box-shadow: 0 18px 42px rgba(52, 29, 68, 0.16);
    }

    body[data-app-variant="repocto"] .raporhub-welcome-band::after {
      content: "";
      position: absolute;
      right: -8px;
      bottom: -56px;
      width: 290px;
      height: 290px;
      background: url('/repocto-landing/assets/repocto-symbol.png') center / contain no-repeat;
      opacity: 0.18;
      pointer-events: none;
    }

    body[data-app-variant="repocto"] .raporhub-welcome-band > * {
      position: relative;
      z-index: 1;
    }

    body[data-app-variant="repocto"] .raporhub-eyebrow {
      color: #88d4cd;
    }

    body[data-app-variant="repocto"] .raporhub-welcome-band h2 {
      max-width: 720px;
      color: #ffffff;
      font-size: clamp(34px, 4vw, 56px);
      line-height: 1.05;
    }

    body[data-app-variant="repocto"] .raporhub-welcome-band p {
      max-width: 680px;
      color: rgba(255, 255, 255, 0.72);
    }

    body[data-app-variant="repocto"] .raporhub-welcome-band .button.secondary {
      border-color: #e4d4e9;
      background: #fff8ed;
    }

    body[data-app-variant="repocto"] .repocto-capability-strip {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 1px;
      margin-top: 16px;
      overflow: hidden;
      border: 1px solid var(--rh-line);
      border-radius: 6px;
      background: var(--rh-line);
    }

    body[data-app-variant="repocto"] .repocto-capability-strip button {
      display: grid;
      grid-template-columns: 34px 1fr;
      gap: 11px;
      align-items: center;
      min-height: 66px;
      padding: 12px 15px;
      border: 0;
      border-radius: 0;
      background: var(--rh-surface);
      color: var(--rh-ink);
      text-align: left;
    }

    body[data-app-variant="repocto"] .repocto-capability-strip button:hover {
      background: var(--rh-surface-muted);
    }

    body[data-app-variant="repocto"] .repocto-capability-strip i {
      display: grid;
      place-items: center;
      width: 34px;
      height: 34px;
      border: 1px solid #bca8c4;
      border-radius: 50%;
      color: #68427c;
      font-style: normal;
      font-size: 10px;
      font-weight: 900;
    }

    body[data-app-variant="repocto"] .repocto-capability-strip strong,
    body[data-app-variant="repocto"] .repocto-capability-strip span {
      display: block;
    }

    body[data-app-variant="repocto"] .repocto-capability-strip strong {
      font-size: 12px;
    }

    body[data-app-variant="repocto"] .repocto-capability-strip span {
      margin-top: 3px;
      color: var(--rh-muted);
      font-size: 9px;
    }

    body[data-app-variant="repocto"] .raporhub-question-workspace,
    body[data-app-variant="repocto"] .raporhub-recent-workspace,
    body[data-app-variant="repocto"] .raporhub-readiness-panel,
    body[data-app-variant="repocto"] .panel,
    body[data-app-variant="repocto"] .upload-card {
      border-color: var(--rh-line);
      border-radius: 6px;
      background: var(--rh-surface);
      box-shadow: 0 10px 28px rgba(52, 29, 68, 0.07);
    }

    body[data-app-variant="repocto"] .raporhub-question-workspace {
      grid-template-columns: 220px minmax(0, 1fr);
      margin-top: 16px;
      padding: 22px;
    }

    body[data-app-variant="repocto"] .raporhub-question-copy {
      border-right-color: var(--rh-line);
    }

    body[data-app-variant="repocto"] .raporhub-question-copy span,
    body[data-app-variant="repocto"] .raporhub-panel-heading span,
    body[data-app-variant="repocto"] .panel-title {
      color: #68427c;
    }

    body[data-app-variant="repocto"] .raporhub-question-row textarea {
      min-height: 74px;
      border-color: #bca9c4;
      background: #fffcf7;
    }

    body[data-app-variant="repocto"] .raporhub-starters button {
      border-color: #d7cadb;
      background: #f4ebf5;
      color: #5d3a70;
    }

    body[data-app-variant="repocto"] .raporhub-metric-strip {
      margin-top: 16px;
      overflow: hidden;
      border: 1px solid var(--rh-line);
      border-radius: 6px;
      background: var(--rh-surface);
    }

    body[data-app-variant="repocto"] .raporhub-metric-strip div {
      min-height: 92px;
      padding: 20px;
      border-color: var(--rh-line);
    }

    body[data-app-variant="repocto"] .raporhub-metric-strip strong {
      color: #513065;
      font-family: Georgia, 'Times New Roman', serif;
      font-size: 28px;
      font-weight: 500;
    }

    body[data-app-variant="repocto"] .raporhub-overview-grid {
      grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.75fr);
      gap: 16px;
    }

    body[data-app-variant="repocto"] .raporhub-coverage-track span {
      background: #359fa0;
    }

    body[data-app-variant="repocto"] .raporhub-ready-badge {
      border-color: #8acac4;
      background: #e4f4f1;
      color: #1d7778;
    }

    body[data-app-variant="repocto"] .raporhub-file-badge {
      border-radius: 4px;
    }

    body[data-app-variant="repocto"] .chat-layout {
      grid-template-columns: minmax(0, 1fr) minmax(320px, 390px);
      gap: 14px;
      align-items: stretch;
    }

    body[data-app-variant="repocto"] .chat-panel,
    body[data-app-variant="repocto"] .chat-side {
      min-height: calc(100vh - 190px);
      overflow: hidden;
    }

    body[data-app-variant="repocto"] .chat-panel {
      display: grid;
      grid-template-rows: minmax(280px, 1fr) auto auto auto;
    }

    body[data-app-variant="repocto"] .chat-toolbar {
      border-bottom-color: var(--rh-line);
      background: #f0e5f2;
    }

    body[data-app-variant="repocto"] .chat-avatar {
      border: 1px solid #6a477b;
      border-radius: 50%;
      background: #57336b;
      color: #ffffff;
    }

    body[data-app-variant="repocto"] .chat-agent-title {
      color: #3c244b;
    }

    body[data-app-variant="repocto"] .chat-messages {
      background: #fffaf2;
    }

    body[data-app-variant="repocto"] .chat-message {
      border-radius: 5px;
    }

    body[data-app-variant="repocto"] .chat-message.assistant {
      border-color: #d0c0d5;
      background: #f2e9f4;
      color: #3d2749;
    }

    body[data-app-variant="repocto"] .chat-message.user {
      background: #543068;
      color: #ffffff;
    }

    body[data-app-variant="repocto"] .chat-prompts-shell,
    body[data-app-variant="repocto"] .chat-input-row {
      border-top-color: var(--rh-line);
      background: var(--rh-surface);
    }

    body[data-app-variant="repocto"] .chat-input-row textarea {
      border-color: #bdaac5;
      background: #fffcf7;
    }

    body[data-app-variant="repocto"] .chat-side {
      border-left: 3px solid #5b3670;
    }

    @media (min-width: 981px) {
      body[data-app-variant="repocto"].chat-focus .section[data-module-key="chat"] {
        box-sizing: border-box;
        padding: 0;
      }

      body[data-app-variant="repocto"].chat-focus .chat-layout {
        height: 100vh;
        min-height: 100vh;
      }

      body[data-app-variant="repocto"].chat-focus .chat-panel,
      body[data-app-variant="repocto"].chat-focus .chat-side {
        min-height: 0;
      }
    }

    body[data-app-variant="repocto"] .result-card,
    body[data-app-variant="repocto"] .similar-card,
    body[data-app-variant="repocto"] .source-card,
    body[data-app-variant="repocto"] .duplicate-card {
      border-radius: 5px;
      border-color: var(--rh-line);
      background: var(--rh-surface);
    }

    body[data-app-variant="repocto"] table {
      border-collapse: collapse;
    }

    body[data-app-variant="repocto"] th {
      background: #eee3f0;
      color: #4d2e5e;
    }

    body[data-app-variant="repocto"] td,
    body[data-app-variant="repocto"] th {
      border-color: var(--rh-line);
    }

    body[data-app-variant="repocto"] tr:hover td {
      background: #faf1fa;
    }

    body[data-app-variant="repocto"].raporhub-sidebar-collapsed .card {
      grid-template-columns: 82px minmax(0, 1fr);
    }

    body[data-app-variant="repocto"].raporhub-sidebar-collapsed .hero {
      width: 82px;
      padding-left: 10px;
      padding-right: 10px;
    }

    body[data-app-variant="repocto"].raporhub-sidebar-collapsed .hero h1 {
      display: none;
    }

    body[data-app-variant="repocto"].raporhub-sidebar-collapsed .hero-title-row {
      min-height: 42px;
    }

    body[data-app-variant="repocto"].raporhub-sidebar-collapsed .raporhub-sidebar-toggle {
      top: 4px;
      right: 15px;
    }

    body[data-app-variant="repocto"].raporhub-sidebar-collapsed .raporhub-topbar {
      left: auto;
    }

    body[data-app-variant="repocto"].raporhub-sidebar-collapsed .module-filter {
      display: grid;
      grid-template-columns: 1fr;
      justify-items: center;
      padding: 7px;
      color: transparent;
      font-size: 0;
    }

    body[data-app-variant="repocto"].raporhub-sidebar-collapsed .module-filter::before {
      content: attr(data-nav-short);
      display: block;
      position: static;
      inset: auto;
      width: auto;
      height: auto;
      border: 0;
      border-radius: 0;
      background: transparent;
      color: #b8e5df;
      font-size: 10px;
      font-weight: 900;
    }

    body[data-app-variant="repocto"].raporhub-sidebar-collapsed .module-filter.active::before {
      content: attr(data-nav-short);
      display: block;
      background: transparent;
      color: #4b2862;
    }

    body[data-app-variant="repocto"].raporhub-sidebar-collapsed .module-filter::after {
      content: none;
      display: none;
    }

    @media (max-width: 1180px) {
      body[data-app-variant="repocto"] .repocto-library-hero {
        grid-template-columns: 1fr;
      }

      body[data-app-variant="repocto"] .repocto-library-pipeline {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      body[data-app-variant="repocto"] .repocto-library-workspace {
        grid-template-columns: minmax(300px, 0.9fr) minmax(0, 1.1fr);
      }

      body[data-app-variant="repocto"] .repocto-library-detail-pane {
        grid-column: 1 / -1;
        border-top: 1px solid var(--rh-line);
        border-left: 0;
      }

      body[data-app-variant="repocto"] .repocto-capability-strip {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      body[data-app-variant="repocto"] .chat-layout {
        grid-template-columns: minmax(0, 1fr) 320px;
      }
    }

    @media (max-width: 980px) {
      body[data-app-variant="repocto"] .repocto-library-workspace {
        grid-template-columns: 1fr;
      }

      body[data-app-variant="repocto"] .repocto-library-detail-pane {
        border-top: 1px solid var(--rh-line);
        border-left: 0;
      }

      body[data-app-variant="repocto"] .repocto-library-map-pane {
        border-top: 1px solid var(--rh-line);
        border-left: 0;
      }

      body[data-app-variant="repocto"] .card {
        display: flex;
        flex-direction: column;
      }

      body[data-app-variant="repocto"] .hero {
        position: relative;
        width: 100%;
        min-height: 0;
        max-height: none;
        padding: 10px 14px;
      }

      body[data-app-variant="repocto"] .hero-title-row {
        align-items: center;
      }

      body[data-app-variant="repocto"] .hero h1 {
        width: 164px;
        height: 50px;
        min-height: 50px;
        background-size: 150px auto;
      }

      body[data-app-variant="repocto"] .raporhub-sidebar-toggle,
      body[data-app-variant="repocto"] .raporhub-brand-subtitle,
      body[data-app-variant="repocto"] .raporhub-nav-label,
      body[data-app-variant="repocto"] .raporhub-sidebar-footer {
        display: none !important;
      }

      body[data-app-variant="repocto"] .module-switcher {
        display: flex;
        flex-direction: row;
        gap: 6px;
        margin-top: 9px;
        overflow-x: auto;
        scrollbar-width: thin;
      }

      body[data-app-variant="repocto"] .module-filter {
        display: inline-flex;
        flex: 0 0 auto;
        width: auto;
        min-height: 36px;
        padding: 4px 10px;
      }

      body[data-app-variant="repocto"] .module-filter::before {
        content: none;
        display: none;
      }

      body[data-app-variant="repocto"] .raporhub-topbar {
        position: absolute;
        left: auto;
        right: 14px;
        top: 12px;
        min-height: 0;
        padding: 0;
      }

      body[data-app-variant="repocto"] .repocto-page-context span {
        display: none;
      }

      body[data-app-variant="repocto"] .repocto-page-context strong {
        font-size: 18px;
      }

      body[data-app-variant="repocto"] .section {
        padding: 24px 16px 34px;
      }

      body[data-app-variant="repocto"] .raporhub-overview-grid,
      body[data-app-variant="repocto"] .chat-layout {
        grid-template-columns: 1fr;
      }

      body[data-app-variant="repocto"] .chat-panel,
      body[data-app-variant="repocto"] .chat-side {
        min-height: 0;
      }

      body[data-app-variant="repocto"] .chat-panel {
        min-height: 620px;
      }

      body[data-app-variant="repocto"] .chat-side {
        border-top: 3px solid #5b3670;
        border-left-width: 1px;
      }
    }

    @media (max-width: 640px) {
      body[data-app-variant="repocto"] .repocto-library-hero {
        padding: 22px 16px;
      }

      body[data-app-variant="repocto"] .repocto-library-path > div,
      body[data-app-variant="repocto"] .repocto-library-pipeline,
      body[data-app-variant="repocto"] .repocto-library-controls,
      body[data-app-variant="repocto"] .repocto-library-document-copy dl {
        grid-template-columns: 1fr;
      }

      body[data-app-variant="repocto"] .raporhub-topbar {
        gap: 8px;
      }

      body[data-app-variant="repocto"] .raporhub-system-menu > summary span:not(.raporhub-device-dot),
      body[data-app-variant="repocto"] .raporhub-system-menu > summary strong {
        display: none;
      }

      body[data-app-variant="repocto"] .raporhub-welcome-band {
        min-height: 0;
        padding: 27px 22px;
      }

      body[data-app-variant="repocto"] .raporhub-welcome-band::after {
        right: -72px;
        width: 220px;
        height: 220px;
      }

      body[data-app-variant="repocto"] .raporhub-welcome-band h2 {
        max-width: 82%;
        font-size: 34px;
      }

      body[data-app-variant="repocto"] .repocto-capability-strip,
      body[data-app-variant="repocto"] .raporhub-metric-strip {
        grid-template-columns: 1fr 1fr;
      }

      body[data-app-variant="repocto"] .raporhub-question-workspace {
        grid-template-columns: 1fr;
        padding: 17px;
      }

      body[data-app-variant="repocto"] .raporhub-question-copy {
        padding: 0 0 14px;
        border-right: 0;
        border-bottom: 1px solid var(--rh-line);
      }

      body[data-app-variant="repocto"] .raporhub-question-row {
        grid-template-columns: 1fr;
      }

      body[data-app-variant="repocto"] .chat-panel {
        min-height: 560px;
      }

      body[data-app-variant="repocto"] .chat-toolbar,
      body[data-app-variant="repocto"] .chat-toolbar-actions {
        grid-template-columns: 1fr;
      }

      body[data-app-variant="repocto"] .chat-composer-footer {
        display: grid;
        grid-template-columns: minmax(0, 1fr) 40px;
        align-items: end;
        gap: 8px;
        width: 100%;
      }

      body[data-app-variant="repocto"] .chat-composer-options {
        display: grid;
        grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.15fr);
        gap: 6px;
        width: 100%;
        overflow: visible;
      }

      body[data-app-variant="repocto"] .chat-composer-options select {
        width: 100%;
        min-width: 0;
        max-width: none;
      }

      body[data-app-variant="repocto"] .chat-composer-options #chatMode {
        grid-column: 1 / -1;
      }

      body[data-app-variant="repocto"] .chat-composer-footer #chatSendButton {
        align-self: end;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      body[data-app-variant="repocto"] .card,
      body[data-app-variant="repocto"] .hero {
        transition: none;
      }
    }
"""
