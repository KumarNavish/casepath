// node capture.js <out> <lang> <prefix> ; captures every tab of the case + list + knowledge
const { chromium } = require('playwright');
const CASE = 'case_30e0064700cd481e';
(async () => {
  const [out, lang, prefix] = process.argv.slice(2);
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const shots = [
    ['h-cases', '/cases', []],
    ['i-case2-claim-reader', `/case/${CASE}/claim_reader`, ['.cp-spine', 'article.cp-card', 'section.cp-card']],
    ['j-case2-source-checker', `/case/${CASE}/source_checker`, ['.cp-main section.cp-card', '.cp-main article.cp-card']],
    ['k-case2-process-builder', `/case/${CASE}/process_builder`, ['.cp-graph']],
    ['l-case2-document-finder', `/case/${CASE}/document_finder`, ['.cp-main section.cp-card', '.cp-main article.cp-card']],
    ['m-case2-result-checker', `/case/${CASE}/result_checker`, []],
    ['n-knowledge-refinement', '/knowledge', []],
  ];
  for (const [name, route, crops] of shots) {
    await p.setViewportSize({ width: 1440, height: 900 });
    await p.goto(`http://127.0.0.1:8765/?lang=${lang}#${route}`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(2500);
    await p.screenshot({ path: `${out}/${prefix}${name}.png` });
    await p.setViewportSize({ width: 1440, height: 1600 }); await p.waitForTimeout(1200);
    await p.screenshot({ path: `${out}/${prefix}${name}-tall.png` });
    let i = 0;
    for (const sel of crops) {
      const el = await p.$(sel);
      if (el) { await el.screenshot({ path: `${out}/${prefix}${name}-crop${++i}.png` }); }
      else console.log('no element', name, sel);
    }
  }
  await b.close();
})();
