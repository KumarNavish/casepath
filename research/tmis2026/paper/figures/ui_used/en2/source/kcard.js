// node kcard.js <out-prefix> <text>  -> knowledge page + crop of each card containing text
const { chromium } = require('playwright');
(async () => {
  const [out, text] = process.argv.slice(2);
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await p.goto('http://127.0.0.1:8765/?lang=en#/knowledge', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2500);
  await p.screenshot({ path: `${out}.png` });
  await p.setViewportSize({ width: 1440, height: 1600 });
  await p.waitForTimeout(1200);
  await p.screenshot({ path: `${out}-tall.png` });
  const cards = await p.$$('article, .cp-card');
  let i = 0;
  for (const c of cards) {
    const t = (await c.innerText()).toLowerCase();
    const box = await c.boundingBox();
    if (t.includes(text.toLowerCase()) && box && box.height < 1200 && box.width < 900) {
      await c.screenshot({ path: `${out}-card${++i}.png` });
    }
  }
  console.log('cards', i);
  await b.close();
})();
