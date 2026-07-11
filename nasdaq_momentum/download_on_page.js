// Paste this in browser console when on an investing.com historical data page.
// It sets start date to 2005-01-01, clicks Apply, waits, then downloads.

(async function() {
    function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

    // 1. Click date picker to open the dropdown panel
    const picker = document.querySelector('[class*="shadow-select"]');
    if (picker) { picker.click(); console.log("✅ Opened date picker"); }
    else { console.log("❌ No date picker found"); return; }
    await sleep(2000);

    // 2. Find date input inside the dropdown panel (it has opacity-0)
    const panel = document.querySelector('.NativeDateInputV2_root__uAIu0');
    if (!panel) { console.log("❌ Date panel not found"); return; }
    const input = panel.querySelector('input[type="date"]');
    if (input) {
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeSetter.call(input, '2005-01-01');
        input.dispatchEvent(new Event('input', {bubbles: true}));
        input.dispatchEvent(new Event('change', {bubbles: true}));
        console.log("✅ Set start date to 2005-01-01");
    } else {
        console.log("❌ Date input not found inside panel");
        return;
    }
    await sleep(1000);

    // 3. Click Apply (blue button with white "Apply" text)
    let applied = false;
    document.querySelectorAll('span').forEach(s => {
        if (s.textContent.trim() === 'Apply' && !applied) {
            s.closest('div[class*="bg-v2-blue"], div[class*="cursor-pointer"]').click();
            applied = true;
            console.log("✅ Clicked Apply");
        }
    });
    if (!applied) console.log("❌ Apply not found");
    await sleep(6000);

    // 4. Click Download
    let downloaded = false;
    document.querySelectorAll('span').forEach(s => {
        if (s.textContent.trim() === 'Download' && !downloaded) {
            s.closest('div').click();
            downloaded = true;
            console.log("✅ Downloaded!");
        }
    });
    if (!downloaded) console.log("❌ Download button not found");
})();
