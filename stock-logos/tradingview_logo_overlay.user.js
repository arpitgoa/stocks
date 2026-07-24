// ==UserScript==
// @name         TradingView Stock Logo Overlay
// @namespace    https://tradingview.com
// @version      2.0
// @description  Stock logo watermark on TradingView charts (GitHub-cached, portable across devices)
// @match        https://www.tradingview.com/chart/*
// @match        https://www.tradingview.com/symbols/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  // ─── Config ──────────────────────────────────────────────────────────────────
  // CHANGE THIS to your GitHub username/repo after pushing:
  const GITHUB_REPO = 'arpitgoa/stocks';
  const GITHUB_BRANCH = 'main';
  const GITHUB_PATH = 'stock-logos/logos';

  const LOGO_DEV_TOKEN = 'pk_YWcpl2HqTTyigO9G_HrRWA';

  const CONFIG = {
    size: 800,           // API request size
    displaySize: 250,    // CSS display size
    opacity: 0.3,
  };

  let currentTicker = null;
  let logoElement = null;
  let isDragging = false;
  let dragOffset = { x: 0, y: 0 };

  // ─── IndexedDB Cache (local browser fallback) ──────────────────────────────
  const DB_NAME = 'TradingViewLogoCache';
  const STORE_NAME = 'logos';

  function openDB() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: 'ticker' });
        }
      };
      req.onsuccess = (e) => resolve(e.target.result);
      req.onerror = (e) => reject(e.target.error);
    });
  }

  async function getCachedLogo(ticker) {
    try {
      const db = await openDB();
      return new Promise((resolve) => {
        const tx = db.transaction(STORE_NAME, 'readonly');
        const req = tx.objectStore(STORE_NAME).get(ticker);
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => resolve(null);
      });
    } catch { return null; }
  }

  async function cacheLogo(ticker, blob) {
    try {
      const db = await openDB();
      const tx = db.transaction(STORE_NAME, 'readwrite');
      tx.objectStore(STORE_NAME).put({ ticker, blob, cachedAt: Date.now() });
    } catch {}
  }

  // ─── Logo Resolution (3-tier: GitHub → IndexedDB → API) ───────────────────
  async function getLogoUrl(ticker) {
    // Tier 1: GitHub repo (portable across devices, free CDN)
    const githubUrl = `https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}/${GITHUB_PATH}/${ticker}.png`;
    try {
      const resp = await fetch(githubUrl, { method: 'HEAD' });
      if (resp.ok) {
        console.log(`[LogoOverlay] ✓ GitHub hit for ${ticker}`);
        return githubUrl;
      }
    } catch {}

    // Tier 2: Browser IndexedDB cache
    const cached = await getCachedLogo(ticker);
    if (cached && cached.blob) {
      console.log(`[LogoOverlay] ✓ IndexedDB hit for ${ticker}`);
      return URL.createObjectURL(cached.blob);
    }

    // Tier 3: Logo.dev API (last resort — uses API quota)
    console.log(`[LogoOverlay] Cache miss for ${ticker}, fetching from Logo.dev API...`);
    const apiUrl = `https://img.logo.dev/ticker/${ticker}?token=${LOGO_DEV_TOKEN}&size=${CONFIG.size}&format=png&retina=true&theme=dark&fallback=404`;
    try {
      const resp = await fetch(apiUrl);
      if (!resp.ok) return null;
      const blob = await resp.blob();
      await cacheLogo(ticker, blob);
      console.log(`[LogoOverlay] ✓ Fetched & cached ${ticker} (${(blob.size / 1024).toFixed(1)} KB)`);
      return URL.createObjectURL(blob);
    } catch (err) {
      console.warn(`[LogoOverlay] ✗ Failed for ${ticker}`, err);
      return null;
    }
  }

  // ─── Ticker Detection ──────────────────────────────────────────────────────
  function getTicker() {
    const titleMatch = document.title.match(/^([A-Z0-9.]{1,10})\s/);
    if (titleMatch) return titleMatch[1];

    const legendEl = document.querySelector('[data-symbol-short]');
    if (legendEl) return legendEl.getAttribute('data-symbol-short').split(':').pop().trim();

    const url = decodeURIComponent(window.location.href);
    const urlMatch = url.match(/symbol=([^&]+)/);
    if (urlMatch) return urlMatch[1].split(':').pop().trim();

    return null;
  }

  // ─── Chart DOM ─────────────────────────────────────────────────────────────
  function findChartPane() {
    return (
      document.querySelector('.chart-markup-table') ||
      document.querySelector('.layout__area--center') ||
      document.querySelector('[class*="chartContainer"]') ||
      document.querySelector('.chart-container')
    );
  }

  function makeDraggable(el) {
    el.addEventListener('mousedown', (e) => {
      isDragging = true;
      dragOffset.x = e.clientX - el.offsetLeft;
      dragOffset.y = e.clientY - el.offsetTop;
      el.style.cursor = 'grabbing';
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!isDragging || !logoElement) return;
      logoElement.style.left = (e.clientX - dragOffset.x) + 'px';
      logoElement.style.top = (e.clientY - dragOffset.y) + 'px';
    });

    document.addEventListener('mouseup', () => {
      if (isDragging && logoElement) {
        isDragging = false;
        logoElement.style.cursor = 'grab';
      }
    });
  }

  // ─── Render ────────────────────────────────────────────────────────────────
  async function createLogoOverlay(ticker) {
    if (logoElement) {
      logoElement.remove();
      logoElement = null;
    }

    const chartPane = findChartPane();
    if (!chartPane) {
      setTimeout(() => createLogoOverlay(ticker), 2000);
      return;
    }

    const pos = window.getComputedStyle(chartPane).position;
    if (pos === 'static') chartPane.style.position = 'relative';

    const logoUrl = await getLogoUrl(ticker);
    if (!logoUrl) return;

    logoElement = document.createElement('img');
    logoElement.src = logoUrl;
    logoElement.alt = `${ticker} logo`;
    logoElement.style.cssText = `
      position: absolute;
      top: 30%;
      right: 140px;
      transform: translateY(-50%);
      width: ${CONFIG.displaySize}px;
      height: ${CONFIG.displaySize}px;
      opacity: ${CONFIG.opacity};
      pointer-events: auto;
      z-index: 2;
      object-fit: contain;
      user-select: none;
      -webkit-user-drag: none;
      cursor: grab;
      mix-blend-mode: screen;
    `;

    chartPane.appendChild(logoElement);
    makeDraggable(logoElement);
    currentTicker = ticker;
  }

  function checkAndUpdate() {
    const ticker = getTicker();
    if (!ticker) return;
    if (ticker !== currentTicker) {
      createLogoOverlay(ticker);
    }
  }

  // ─── Init ──────────────────────────────────────────────────────────────────
  setTimeout(() => {
    checkAndUpdate();
    setInterval(checkAndUpdate, 1000);
  }, 3000);
})();
