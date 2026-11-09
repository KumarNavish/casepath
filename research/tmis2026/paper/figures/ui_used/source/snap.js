// usage: node snap.js <out-dir> <name> <hash-route> [lang] [waitMs] [fullPage]
const { chromium } = require('playwright');
(async () => {
  const [out, name, route, lang = 'en', wait = '2500', full = '0'] = process.argv.slice(2);
  const browser = await chromium.launch({ args: ['--no-proxy-server'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await page.goto(`http://127.0.0.1:8765/?lang=${lang}#${route}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(+wait);
  await page.screenshot({ path: `${out}/${name}.png`, fullPage: full === '1' });
  await browser.close();
})();
