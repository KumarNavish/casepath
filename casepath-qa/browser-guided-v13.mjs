import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const BASE_URL = (process.env.BASE_URL || 'https://casepath-guided-v13-preview.onrender.com').replace(/\/$/, '');
const API_URL = (process.env.API_URL || 'https://casepath-agentic-api.onrender.com').replace(/\/$/, '');
const OUT = path.resolve('guided-v13-qa-out');
const checks = [];
const errors = { console: [], page: [], requests: [] };
let browser;
let page;

function record(name, passed, detail = '') {
  const item = { name, passed: Boolean(passed), detail };
  checks.push(item);
  if (!item.passed) throw new Error(`${name}: ${detail || 'failed'}`);
}

async function waitVisible(selector, timeout = 120000) {
  await page.locator(selector).waitFor({ state: 'visible', timeout });
}

async function question() {
  return (await page.locator('.stage-question').innerText()).trim();
}

async function shot(name) {
  await page.screenshot({ path: path.join(OUT, name), fullPage: false });
}

async function clickNext(expectedQuestion) {
  await page.locator('#guideNext').click();
  await page.waitForFunction(expected => document.querySelector('.stage-question')?.textContent?.trim() === expected, expectedQuestion, { timeout: 30000 });
}

async function main() {
  await fs.rm(OUT, { recursive: true, force: true });
  await fs.mkdir(OUT, { recursive: true });

  const reset = await fetch(`${API_URL}/api/demo/reset`, { method: 'POST' });
  record('Demo state reset', reset.ok, `status=${reset.status}`);

  browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  page = await context.newPage();
  page.on('console', message => { if (message.type() === 'error') errors.console.push(message.text()); });
  page.on('pageerror', error => errors.page.push(String(error)));
  page.on('requestfailed', request => {
    const url = request.url();
    if (url.startsWith(BASE_URL) || url.startsWith(API_URL)) errors.requests.push(`${request.failure()?.errorText || 'failed'} ${url}`);
  });

  const response = await page.goto(`${BASE_URL}/?qa=${Date.now()}`, { waitUntil: 'domcontentloaded', timeout: 120000 });
  record('Preview returned HTTP 200', response?.status() === 200, `status=${response?.status()}`);
  await waitVisible('#analyseBtn');
  await page.waitForFunction(() => document.querySelectorAll('.attachment-row').length >= 5, null, { timeout: 120000 });
  record('Original customer message is visible', await page.locator('#customerMessage .email-body').isVisible());
  record('Original attachments are visible', await page.locator('.attachment-row').count() >= 5, `attachments=${await page.locator('.attachment-row').count()}`);
  record('No post-analysis panels are visible before analysis', await page.locator('#guide').isHidden());
  await shot('01-original-submission.png');

  const lease = page.locator('[data-artifact-id="art_lease"]').first();
  record('Lease source is available', await lease.count() === 1);
  await lease.click();
  await waitVisible('#artifactViewer[open]');
  await waitVisible('#pdfPageImage');
  record('Actual PDF page renders', (await page.locator('#pdfPageImage').getAttribute('src'))?.includes('/pages/'));
  record('Original and extraction stay separate', await page.locator('[data-viewer-tab="original"]').count() === 1 && await page.locator('[data-viewer-tab="extraction"]').count() === 1);
  await page.locator('#closeViewer').click();

  await page.locator('#analyseBtn').click();
  await waitVisible('#analysis');
  await page.waitForTimeout(650);
  record('Real pipeline activity is visible', await page.locator('#stageList .stage-item').count() === 6);
  await shot('02-analysis-running.png');
  await page.waitForFunction(() => {
    const guide = document.querySelector('#guide');
    return guide && !guide.hidden && document.querySelector('.stage-question');
  }, null, { timeout: 150000 });

  record('Guided review begins at step 1', (await page.locator('#guideStepNumber').innerText()).trim() === '1');
  record('Only one dominant guided question is visible', await page.locator('#guideStage .stage-question').count() === 1 && await page.locator('#guideStage .stage-answer').count() === 1);
  record('Step 1 asks what the customer sent', await question() === 'What did the customer send?');
  record('Full process/checklist/law are hidden by default', await page.locator('#detailDialog[open]').count() === 0 && await page.locator('.detail-path').count() === 0);
  await shot('03-guided-submission.png');

  await clickNext('What does CasePath understand?');
  record('Step 2 separates supported and uncertain facts', await page.locator('.fact-summary-row').count() >= 3);
  const factSource = page.locator('.fact-summary-row button').first();
  if (await factSource.count()) {
    await factSource.click();
    await waitVisible('#artifactViewer[open]');
    record('Fact opens its original source', await page.locator('#artifactViewer').isVisible());
    await page.locator('#closeViewer').click();
  }

  await clickNext('What legal or process question matters now?');
  record('Current path preview is visible without irrelevant branches', await page.locator('.path-preview .path-step').count() >= 1 && await page.locator('#guideStage .branch-preview').count() === 0);
  await page.locator('#guideDetail').click();
  await waitVisible('#detailDialog[open]');
  record('Full decision path is available on demand', await page.locator('#detailContent .detail-path-node').count() >= 4);
  record('Alternative branches are collapsed by default', await page.locator('#detailContent .branch-details details:not([open])').count() >= 1);
  await page.locator('#closeDetail').click();
  await shot('04-current-question.png');

  await clickNext('What is blocking the claim?');
  record('The blocker is the dominant message', /cause|caused|causation/i.test(await page.locator('.stage-answer').innerText()));
  record('Only relevant competing explanations are shown', await page.locator('.branch-option').count() >= 2);

  await clickNext('What evidence would resolve the blocker?');
  record('Evidence emerges from the process question', await page.locator('.reason-chain .chain-step').count() === 3);
  record('One evidence item is visually dominant', await page.locator('.evidence-focus').count() === 1);
  await shot('05-evidence-guidance.png');

  await clickNext('Which previous cases are useful here?');
  record('Exactly three previous cases are shown', await page.locator('.precedent-guide-row').count() === 3, `precedents=${await page.locator('.precedent-guide-row').count()}`);
  record('Each precedent explains why it helps', await page.locator('.precedent-guide-row p').count() === 3);
  await shot('06-previous-cases.png');

  await clickNext('What should the expert review or do next?');
  record('Expert sees one consequential decision', await page.locator('#guidedReviewForm').isVisible() && await page.locator('.review-choice').count() === 2);
  record('One clear approval action is present', await page.locator('#guidedReviewForm button[type="submit"]').count() === 1);
  await shot('07-expert-review.png');
  await page.locator('#guidedReviewForm button[type="submit"]').click();
  await page.waitForFunction(() => document.querySelector('.stage-question')?.textContent?.trim() === 'What does CasePath learn after approval?', null, { timeout: 90000 });

  record('Learning separates immediate memory from shared rules', await page.locator('.learning-line').count() === 2);
  record('Reviewed precedent is available immediately', /Reviewed precedent/i.test(await page.locator('.learning-line.available').innerText()));
  record('Reusable rule remains quarantined', /Candidate reusable rule/i.test(await page.locator('.learning-line.quarantined').innerText()));
  await shot('08-learning-moment.png');

  await page.locator('#guideNext').click();
  await page.waitForFunction(() => /later claim/i.test(document.querySelector('.stage-answer')?.textContent || ''), null, { timeout: 90000 });
  record('Later-claim proof replaces the learning screen', await page.locator('.before-after-panel').count() === 2);
  record('Before and after show a meaningful evidence change', /conditional/i.test(await page.locator('.before-after').innerText()));
  await shot('09-later-claim-proof.png');

  await page.locator('#openAuditGuide').click();
  await waitVisible('#auditDrawer[open]');
  record('Complete technical audit remains available on demand', await page.locator('#auditContent .audit-event').count() >= 6);
  await page.locator('#closeAudit').click();

  for (const viewport of [
    { width: 390, height: 844, name: '390' },
    { width: 320, height: 700, name: '320' },
  ]) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.waitForTimeout(300);
    const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth);
    record(`${viewport.name}px has no page-level horizontal overflow`, overflow <= 1, `overflow=${overflow}`);
    record(`${viewport.name}px keeps the guided proof readable`, await page.locator('#guide').isVisible() && await page.locator('.stage-answer').isVisible());
    await shot(`10-mobile-${viewport.name}.png`);
  }

  record('No browser console errors', errors.console.length === 0, JSON.stringify(errors.console));
  record('No page errors', errors.page.length === 0, JSON.stringify(errors.page));
  record('No public request failures', errors.requests.length === 0, JSON.stringify(errors.requests));

  await context.close();
  await browser.close();
  browser = null;

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
  const images = ['01-original-submission.png','02-analysis-running.png','03-guided-submission.png','04-current-question.png','05-evidence-guidance.png','06-previous-cases.png','07-expert-review.png','08-learning-moment.png','09-later-claim-proof.png','10-mobile-390.png','10-mobile-320.png'];
  await fs.writeFile(path.join(OUT, 'index.html'), `<!doctype html><meta charset="utf-8"><title>CasePath guided v13 QA</title><style>body{font:16px system-ui;max-width:1080px;margin:40px auto;padding:0 20px;color:#15171a}li{margin:7px 0;color:#18744f}img{max-width:100%;border:1px solid #ddd;margin:8px 0 28px}</style><h1>CasePath guided v13 QA: passed</h1><p><strong>${report.passed}</strong> checks passed against ${BASE_URL}.</p><ul>${checks.map(check => `<li>✓ ${check.name}</li>`).join('')}</ul>${images.map(image => `<h2>${image}</h2><img src="${image}" alt="${image}">`).join('')}`);
  console.log(JSON.stringify(report, null, 2));
}

main().catch(async error => {
  await fs.mkdir(OUT, { recursive: true });
  if (page) await page.screenshot({ path: path.join(OUT, 'failure.png'), fullPage: true }).catch(() => null);
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
}).finally(async () => {
  if (browser) await browser.close().catch(() => null);
});
