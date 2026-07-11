// ==UserScript==
// @name         Investing.com One-Click Download
// @namespace    http://tampermonkey.net/
// @version      3.0
// @description  Adds a button to set date to 2005 and download on investing.com historical pages
// @match        https://www.investing.com/equities/*historical-data*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(function() {
    'use strict';

    function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

    // Wait for element to appear in DOM
    function waitFor(selector, timeout = 10000) {
        return new Promise((resolve, reject) => {
            const el = document.querySelector(selector);
            if (el) { resolve(el); return; }
            const observer = new MutationObserver(() => {
                const el = document.querySelector(selector);
                if (el) { observer.disconnect(); resolve(el); }
            });
            observer.observe(document.body, {childList: true, subtree: true});
            setTimeout(() => { observer.disconnect(); reject('Timeout: ' + selector); }, timeout);
        });
    }

    async function doDownload() {
        const btn = document.getElementById('auto-dl-btn');
        btn.textContent = '⏳ Working...';
        btn.style.background = '#ffa500';

        try {
            // 1. Click date picker
            const picker = document.querySelector('[class*="shadow-select"]');
            if (!picker) { btn.textContent = '❌ No date picker'; return; }
            picker.click();
            btn.textContent = '⏳ Opening dates...';

            // 2. Wait for the date panel to appear
            const panel = await waitFor('.NativeDateInputV2_root__uAIu0');
            btn.textContent = '⏳ Setting date...';
            await sleep(500);

            // 3. Set start date
            const input = panel.querySelector('input[type="date"]');
            if (!input) { btn.textContent = '❌ No date input'; return; }

            const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeSetter.call(input, '2005-01-01');
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new Event('change', {bubbles: true}));
            btn.textContent = '⏳ Date set, applying...';
            await sleep(500);

            // 4. Click Apply
            const applyBtns = document.querySelectorAll('[class*="bg-v2-blue"]');
            if (applyBtns.length > 0) {
                applyBtns[0].click();
            } else {
                // Fallback: find "Apply" text
                document.querySelectorAll('span').forEach(s => {
                    if (s.textContent.trim() === 'Apply') s.closest('div').click();
                });
            }
            btn.textContent = '⏳ Loading data...';
            await sleep(7000);

            // 5. Click Download
            let downloaded = false;
            document.querySelectorAll('span').forEach(s => {
                if (s.textContent.trim() === 'Download' && !downloaded) {
                    s.closest('div').click();
                    downloaded = true;
                }
            });

            if (downloaded) {
                btn.textContent = '✅ Done!';
                btn.style.background = '#28a745';
            } else {
                btn.textContent = '❌ Download not found';
                btn.style.background = '#dc3545';
            }
        } catch(e) {
            btn.textContent = '❌ ' + e;
            btn.style.background = '#dc3545';
            console.error(e);
        }
    }

    // Add the button to the page
    function addButton() {
        const btn = document.createElement('button');
        btn.id = 'auto-dl-btn';
        btn.textContent = '📥 Download from 2005';
        btn.style.cssText = 'position:fixed;top:10px;right:10px;z-index:99999;padding:12px 20px;font-size:14px;font-weight:bold;background:#1f77b4;color:white;border:none;border-radius:8px;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,0.3);';
        btn.onclick = doDownload;
        document.body.appendChild(btn);
    }

    // Wait for page to load then add button
    if (document.readyState === 'complete') {
        addButton();
    } else {
        window.addEventListener('load', addButton);
    }
})();
