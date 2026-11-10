// node hero_narrow.js <port> <out-dir> <prefix> <case-id>
// fig_hero, half-width version: real captures at narrower browser viewports, so that the interface itself wraps the
// text to a 400-CSS-px panel (deviceScaleFactor 2, so every crop is 800 px wide). Nothing is edited; each output is one
// rectangle of the rendered page.
//   <prefix>claim400.png  claim reader at a 1068-px viewport (source panel 400 px wide): the health paragraph
//   <prefix>steps400.png  result checker at a 722-px viewport (its card 400 px wide): "Next steps" and its list
const { chromium } = require('playwright');
(async () => {
  const [port, out, prefix, CASE] = process.argv.slice(2);
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  let p = await b.newPage({ viewport: { width: 1068, height: 1600 }, deviceScaleFactor: 2 });
  await p.goto(`http://127.0.0.1:${port}/?lang=en#/case/${CASE}/claim_reader`, { waitUntil: 'networkidle' });
  await p.waitForTimeout(2500);
  const para = await p.evaluate(() => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = []; let n; while ((n = walker.nextNode())) nodes.push(n);
    const full = nodes.map((x) => x.textContent).join('');
    const start = full.indexOf('Our daughter');
    const endA = full.indexOf('doctor.', start), endB = full.indexOf('report yet.', start);
    const end = endA > 0 ? endA + 7 : endB + 11;
    const at = (k) => { let o = 0; for (const x of nodes) { if (o + x.textContent.length >= k) return [x, k - o]; o += x.textContent.length; } };
    const r = document.createRange(); r.setStart(...at(start)); r.setEnd(...at(end));
    // the source view (.cp-doc-body, 470 px high) scrolls on its own: scroll it so the paragraph is in view, as a reader does
    const body = at(start)[0].parentElement.closest('.cp-doc-body');
    const first = r.getClientRects()[0];
    body.scrollTop += first.top - body.getBoundingClientRect().top - 120;
    const rects = [...r.getClientRects()].filter((q) => q.width > 0);
    const panel = (r.commonAncestorContainer.nodeType === 1 ? r.commonAncestorContainer : r.commonAncestorContainer.parentElement).getBoundingClientRect();
    return { x: panel.x, w: panel.width, top: Math.min(...rects.map((q) => q.top)) + window.scrollY, bottom: Math.max(...rects.map((q) => q.bottom)) + window.scrollY };
  });
  console.log('claim', JSON.stringify(para));
  await p.screenshot({ path: `${out}/${prefix}claim400.png`, clip: { x: para.x, y: para.top - 5, width: 400, height: para.bottom - para.top + 10 } });
  await p.close();
  p = await b.newPage({ viewport: { width: 722, height: 1600 }, deviceScaleFactor: 2 });
  await p.goto(`http://127.0.0.1:${port}/?lang=en#/case/${CASE}/result_checker`, { waitUntil: 'networkidle' });
  await p.waitForTimeout(2500);
  const box = await p.evaluate(() => {
    const h = [...document.querySelectorAll('h2,h3,h4,b,strong,p')].find((e) => e.textContent.trim() === 'Next steps');
    const ul = h.nextElementSibling, card = h.closest('section').getBoundingClientRect();
    const a = h.getBoundingClientRect(), z = ul.getBoundingClientRect();
    return { x: card.x, w: card.width, top: a.top + window.scrollY, bottom: z.bottom + window.scrollY };
  });
  console.log('steps', JSON.stringify(box));
  await p.screenshot({ path: `${out}/${prefix}steps400.png`, clip: { x: box.x, y: box.top - 8, width: 400, height: box.bottom - box.top + 14 } });
  await b.close();
})();
