// node cap.js <port> <out-dir> <prefix> <case-id> [tab,tab,...]
// Unedited captures of the running product: Chromium, 1440 px wide, deviceScaleFactor 2, English interface.
// For each tab: the first screen (1440x900) and the full page.
const { chromium } = require('playwright');
(async () => {
  const [port, out, prefix, CASE, tabsArg] = process.argv.slice(2);
  const tabs = (tabsArg || 'overview,claim_reader,source_checker,process_builder,document_finder,result_checker').split(',');
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  for (const tab of tabs) {
    const route = tab === 'knowledge' ? '/knowledge' : `/case/${CASE}/${tab}`;
    await p.goto(`http://127.0.0.1:${port}/?lang=en#${route}`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(2500);
    await p.evaluate(() => window.scrollTo(0, 0));
    await p.waitForTimeout(300);
    await p.screenshot({ path: `${out}/${prefix}${tab}.png` });
    await p.screenshot({ path: `${out}/${prefix}${tab}-full.png`, fullPage: true });
  }
  await b.close();
})();
