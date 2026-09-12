import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const BASE_URL = (process.env.BASE_URL || 'https://casepath.kumarnavish.chatgpt.site').replace(/\/$/, '');
const API_URL = (process.env.API_URL || 'https://casepath-agentic-api.onrender.com').replace(/\/$/, '');
const OUT = path.resolve('browser-qa-out');
const checks = [];
const errors = { console: [], page: [], requests: [] };

function record(name, passed, detail = '') {
  const item = { name, passed: Boolean(passed), detail };
  checks.push(item);
  if (!item.passed) throw new Error(`${name}: ${detail || 'failed'}`);
}

async function waitVisible(page, selector, timeout = 120000) {
  await page.locator(selector).waitFor({ state: 'visible', timeout });
}

async function loadFresh(page, suffix) {
  await page.goto(`${BASE_URL}/?browserqa=${Date.now()}-${suffix}`, {
    waitUntil: 'domcontentloaded',
    timeout: 120000,
  });
  await waitVisible(page, 'h1');
  await page.waitForFunction(() => document.querySelectorAll('.attachment-row').length > 0, null, { timeout: 120000 });
}

async function main() {
  await fs.rm(OUT, { recursive: true, force: true });
  await fs.mkdir(OUT, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const page = await context.newPage();

  page.on('console', message => {
    if (message.type() === 'error') errors.console.push(message.text());
  });
  page.on('pageerror', error => errors.page.push(String(error)));
  page.on('requestfailed', request => {
    const url = request.url();
    if (url.startsWith(BASE_URL) || url.startsWith(API_URL)) {
      errors.requests.push(`${request.failure()?.errorText || 'failed'} ${url}`);
    }
  });

  await loadFresh(page, 'desktop');
  record('Fresh browser reaches the claim workspace', (await page.locator('h1').textContent())?.trim() === 'Recurring mould. The landlord blames ventilation.');
  record('No bootstrap error is visible', await page.locator('text=CasePath could not open').count() === 0);
  record('No intermediate loader survives', await page.locator('text=Opening the flagship claim').count() === 0);
  record('Original customer message is visible', await page.locator('#customerMessage .email-body').isVisible());
  record('Source attachments are visible', await page.locator('.attachment-row').count() >= 5, `attachments=${await page.locator('.attachment-row').count()}`);
  await page.screenshot({ path: path.join(OUT, '01-fresh-workspace.png'), fullPage: false });

  const lease = page.locator('[data-artifact-id="art_lease"]').first();
  record('Lease attachment is available', await lease.count() === 1);
  await lease.click();
  await waitVisible(page, '#artifactViewer[open]');
  await waitVisible(page, '#pdfPageImage');
  const pdfSource = await page.locator('#pdfPageImage').getAttribute('src');
  record('Actual PDF page is rendered', Boolean(pdfSource && pdfSource.includes('/pages/')), String(pdfSource));
  record('PDF viewer exposes page navigation', await page.locator('[data-pdf-page]').count() >= 2);
  record('PDF viewer separates original and extraction', await page.locator('[data-viewer-tab="original"]').count() === 1 && await page.locator('[data-viewer-tab="extraction"]').count() === 1);
  await page.screenshot({ path: path.join(OUT, '02-pdf-viewer.png'), fullPage: false });
  await page.locator('#closeViewer').click();

  const photo = page.locator('[data-artifact-id="art_photo"]').first();
  record('Photographic evidence is available', await photo.count() === 1);
  await photo.click();
  await waitVisible(page, '#artifactViewer[open]');
  await waitVisible(page, '#originalView img');
  record('Original image is rendered', Boolean(await page.locator('#originalView img').getAttribute('src')));
  record('Image viewer exposes zoom controls', await page.locator('[data-image-zoom]').count() >= 2);
  await page.screenshot({ path: path.join(OUT, '03-image-viewer.png'), fullPage: false });
  await page.locator('#closeViewer').click();

  await page.locator('#analyseBtn').click();
  await waitVisible(page, '#analysis');
  record('Analysis state becomes visible', await page.locator('#analysis').isVisible());
  await page.waitForTimeout(700);
  await page.screenshot({ path: path.join(OUT, '04-analysis-running.png'), fullPage: false });
  await page.waitForFunction(() => {
    const result = document.querySelector('#result');
    return result && !result.hidden;
  }, null, { timeout: 120000 });

  record('Final process is rendered', await page.locator('#processPath .process-node').count() >= 5, `nodes=${await page.locator('#processPath .process-node').count()}`);
  record('Current blocker is explicit', /what caused the recurring mould/i.test(await page.locator('#decisionSummary').innerText()));
  record('Process-bound evidence is rendered', await page.locator('#evidenceColumn .evidence-item').count() >= 2, `evidence=${await page.locator('#evidenceColumn .evidence-item').count()}`);
  record('Three useful precedents are rendered', await page.locator('#precedentList .precedent-row').count() === 3, `precedents=${await page.locator('#precedentList .precedent-row').count()}`);
  record('Pipeline emitted all visible work stages', await page.locator('#stageList .stage-item[data-status="completed"]').count() >= 6, `completed=${await page.locator('#stageList .stage-item[data-status="completed"]').count()}`);
  await page.screenshot({ path: path.join(OUT, '05-process-and-evidence.png'), fullPage: false });

  await page.locator('#review').scrollIntoViewIfNeeded();
  await waitVisible(page, '#reviewForm');
  await page.locator('#reviewForm button[type="submit"]').click();
  await page.waitForFunction(() => {
    const learning = document.querySelector('#learning');
    return learning && !learning.hidden;
  }, null, { timeout: 90000 });
  const learningText = await page.locator('#learningNow').innerText();
  record('Expert review creates visible case memory', /saved as a reviewed precedent/i.test(learningText), learningText);
  record('Shared rule remains visibly quarantined', /quarantined|not yet shared/i.test(learningText), learningText);
  await page.screenshot({ path: path.join(OUT, '06-review-and-learning.png'), fullPage: false });

  await page.locator('#tryLearningBtn').click();
  await page.waitForFunction(() => {
    const later = document.querySelector('#laterClaim');
    return later && !later.hidden;
  }, null, { timeout: 90000 });
  const comparisonText = await page.locator('#beforeAfter').innerText();
  record('Later claim uses reviewed memory', /expert-reviewed precedent used/i.test(comparisonText), comparisonText);
  record('Before-and-after comparison renders two meaningful states', await page.locator('#beforeAfter .compare-panel').count() >= 2 && /before/i.test(comparisonText) && /after/i.test(comparisonText), comparisonText);
  record('Later claim shows an evidence-sequence change', /conditional evidence|what improved|unnecessary immediate request/i.test(comparisonText), comparisonText);
  await page.screenshot({ path: path.join(OUT, '07-later-claim-improved.png'), fullPage: false });

  record('No browser console errors', errors.console.length === 0, JSON.stringify(errors.console));
  record('No page errors', errors.page.length === 0, JSON.stringify(errors.page));
  record('No relevant failed requests', errors.requests.length === 0, JSON.stringify(errors.requests));

  await context.close();

  for (const viewport of [
    { width: 390, height: 844, name: 'mobile-390' },
    { width: 320, height: 700, name: 'mobile-320' },
  ]) {
    const mobileContext = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
    const mobile = await mobileContext.newPage();
    await loadFresh(mobile, viewport.name);
    const overflow = await mobile.evaluate(() => Math.max(0, document.documentElement.scrollWidth - window.innerWidth));
    record(`${viewport.width}px has no page-level horizontal overflow`, overflow === 0, `overflow=${overflow}`);
    record(`${viewport.width}px shows the claim and primary action`, await mobile.locator('h1').isVisible() && await mobile.locator('#analyseBtn').isVisible());
    await mobile.screenshot({ path: path.join(OUT, `08-${viewport.name}.png`), fullPage: false });
    await mobileContext.close();
  }

  await browser.close();

  const report = {
    status: 'passed',
    checkedAt: new Date().toISOString(),
    baseUrl: BASE_URL,
    apiUrl: API_URL,
    passed: checks.filter(check => check.passed).length,
    failed: checks.filter(check => !check.passed).length,
    checks,
    errors,
  };
  await fs.writeFile(path.join(OUT, 'report.json'), `${JSON.stringify(report, null, 2)}\n`);
  await fs.writeFile(path.join(OUT, 'index.html'), `<!doctype html><meta charset="utf-8"><title>CasePath browser QA</title><style>body{font:16px system-ui;max-width:900px;margin:40px auto;padding:0 20px;color:#142033}img{max-width:100%;margin:12px 0;border:1px solid #ddd}.ok{color:#087443}</style><h1>CasePath public browser QA: passed</h1><p><strong>${report.passed}</strong> browser checks passed against <code>${BASE_URL}</code>.</p><ul>${checks.map(check => `<li class="ok">✓ ${check.name}</li>`).join('')}</ul>${['01-fresh-workspace.png','02-pdf-viewer.png','03-image-viewer.png','04-analysis-running.png','05-process-and-evidence.png','06-review-and-learning.png','07-later-claim-improved.png','08-mobile-390.png','08-mobile-320.png'].map(file => `<h2>${file}</h2><img src="${file}" alt="${file}">`).join('')}`);
  console.log(JSON.stringify(report, null, 2));
}

main().catch(async error => {
  await fs.mkdir(OUT, { recursive: true });
  const report = {
    status: 'failed',
    checkedAt: new Date().toISOString(),
    baseUrl: BASE_URL,
    apiUrl: API_URL,
    passed: checks.filter(check => check.passed).length,
    failed: checks.filter(check => !check.passed).length + 1,
    checks,
    errors,
    error: error instanceof Error ? error.stack : String(error),
  };
  await fs.writeFile(path.join(OUT, 'report.json'), `${JSON.stringify(report, null, 2)}\n`);
  console.error(report.error);
  process.exitCode = 1;
});
