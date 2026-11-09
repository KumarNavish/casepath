// node cap.js <out> <prefix> <case-id|-> [knowledge]
const { chromium } = require('playwright');
(async () => {
  const [out, prefix, CASE, withK] = process.argv.slice(2);
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const shots = CASE === '-' ? [] : [
    ['1-claim-reader', `/case/${CASE}/claim_reader`, ['.cp-spine', 'article.cp-card', 'section.cp-card']],
    ['2-source-checker', `/case/${CASE}/source_checker`, []],
    ['3-process-builder', `/case/${CASE}/process_builder`, ['.cp-graph']],
    ['4-document-finder', `/case/${CASE}/document_finder`, ['table']],
    ['5-result-checker', `/case/${CASE}/result_checker`, []],
  ];
  if (withK) shots.push(['6-knowledge', '/knowledge', []]);
  for (const [name, route, crops] of shots) {
    await p.setViewportSize({ width: 1440, height: 900 });
    await p.goto(`http://127.0.0.1:8765/?lang=en#${route}`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(2500);
    await p.evaluate(() => window.scrollTo(0, 0));
    await p.waitForTimeout(300);
    await p.screenshot({ path: `${out}/${prefix}${name}.png` });
    let i = 0;
    for (const sel of crops) {
      const el = await p.$(sel);
      if (el) await el.screenshot({ path: `${out}/${prefix}${name}-crop${++i}.png` }); else console.log('no element', name, sel);
    }
    await p.setViewportSize({ width: 1440, height: 1600 }); await p.waitForTimeout(1200);
    await p.evaluate(() => window.scrollTo(0, 0)); await p.waitForTimeout(300);
    await p.screenshot({ path: `${out}/${prefix}${name}-tall.png` });
  }
  await b.close();
})();
