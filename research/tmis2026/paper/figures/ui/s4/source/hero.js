// node hero.js <port> <out-dir> <prefix> <case-id>
// Element captures (crops of the rendered page, nothing else) for fig_hero: the result checker's
// "Where the case stands in its process" box and the document finder's row for the medical confirmation.
const { chromium } = require('playwright');
(async () => {
  const [port, out, prefix, CASE] = process.argv.slice(2);
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const go = async (tab) => { await p.goto(`http://127.0.0.1:${port}/?lang=en#/case/${CASE}/${tab}`, { waitUntil: 'networkidle' }); await p.waitForTimeout(2500); };
  // the claim reader's source view, at a taller viewport so that the whole first page shows; clip around the
  // health paragraph (from the line holding "Our daughter" to the line that ends the paragraph)
  await p.setViewportSize({ width: 1440, height: 1600 });
  await go('claim_reader');
  const para = await p.evaluate(() => {
    // the rectangles of the text from "Our daughter" to the end of the paragraph, found with a DOM Range
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = []; let n; while ((n = walker.nextNode())) nodes.push(n);
    const full = nodes.map((x) => x.textContent).join('');
    const start = full.indexOf('Our daughter');
    const endA = full.indexOf('doctor.', start), endB = full.indexOf('report yet.', start);
    const end = endA > 0 ? endA + 7 : endB + 11;
    const at = (k) => { let o = 0; for (const x of nodes) { if (o + x.textContent.length >= k) return [x, k - o]; o += x.textContent.length; } };
    const r = document.createRange(); r.setStart(...at(start)); r.setEnd(...at(end));
    const rects = [...r.getClientRects()].filter((q) => q.width > 0);
    let panel = r.commonAncestorContainer.nodeType === 1 ? r.commonAncestorContainer : r.commonAncestorContainer.parentElement;
    const pr = panel.getBoundingClientRect();
    return { x: pr.x, w: pr.width, top: Math.min(...rects.map((q) => q.top)) + window.scrollY, bottom: Math.max(...rects.map((q) => q.bottom)) + window.scrollY };
  });
  console.log(JSON.stringify(para));
  await p.screenshot({ path: `${out}/${prefix}claim.png`, clip: { x: para.x, y: para.top - 6, width: para.w, height: para.bottom - para.top + 12 } });
  await p.setViewportSize({ width: 1440, height: 900 });
  await go('result_checker');
  const box = p.locator('h2, h3, h4, b, strong, p, div').filter({ hasText: /^Where the case stands in its process$/ }).first();
  const card = box.locator('xpath=ancestor::*[self::section or self::article or self::div][1]');
  await card.screenshot({ path: `${out}/${prefix}stands.png` });
  await go('document_finder');
  await p.locator('table thead tr').first().screenshot({ path: `${out}/${prefix}head.png` });
  await p.locator('table tbody tr').filter({ hasText: 'Medical confirmation' }).first().screenshot({ path: `${out}/${prefix}medical.png` });
  await b.close();
})();
