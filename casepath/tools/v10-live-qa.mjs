import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = process.env.CASEPATH_FRONTEND || 'https://casepath-swiss-claim-lab.onrender.com';
const API = process.env.CASEPATH_API || 'https://casepath-agentic-api.onrender.com';
const OUT = process.env.CASEPATH_QA_OUT || 'casepath/reports/v10-live';
fs.mkdirSync(OUT, { recursive: true });

const checks = [];
const errors = [];
const add = (name, ok, detail = '') => {
  checks.push({ name, ok: Boolean(ok), detail });
  if (!ok) errors.push(`${name}: ${detail}`);
};
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  let body;
  try { body = JSON.parse(text); } catch { body = text; }
  if (!response.ok) throw new Error(`${response.status} ${url}: ${text.slice(0, 300)}`);
  return { response, body };
}

async function waitJson(url, predicate, attempts = 48) {
  let last;
  for (let i = 0; i < attempts; i += 1) {
    try {
      const result = await fetchJson(url, { headers: { 'Cache-Control': 'no-cache' } });
      last = result;
      if (predicate(result.body)) return result;
    } catch (error) { last = error; }
    await sleep(5000);
  }
  throw new Error(`Timed out waiting for ${url}: ${String(last)}`);
}

const apiHealth = await waitJson(`${API}/healthz`, body => body?.release === '10.0.0');
add('API health identifies release 10.0.0', apiHealth.body.release === '10.0.0', JSON.stringify(apiHealth.body));
const apiReady = await waitJson(`${API}/readyz`, body => body?.status === 'ready');
add('API is ready', apiReady.body.status === 'ready', JSON.stringify(apiReady.body));
await fetchJson(`${API}/api/demo/reset`, { method: 'POST' });

const release = await waitJson(`${FRONTEND}/release.json?qa=${Date.now()}`, body => body?.release === '10.0.0');
add('Frontend release identifies 10.0.0', release.body.release === '10.0.0', JSON.stringify(release.body));

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const page = await context.newPage();
page.on('console', message => { if (message.type() === 'error') errors.push(`console: ${message.text()}`); });
page.on('pageerror', error => errors.push(`pageerror: ${error.message}`));

const url = `${FRONTEND}/?qa=${Date.now()}`;
const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120000 });
add('Frontend returns HTTP 200', response?.status() === 200, `status=${response?.status()}`);
await page.getByRole('heading', { name: /Recurring mould/i }).waitFor({ timeout: 120000 });
add('Demo claim loads', await page.getByText('DEF-027-E0-DEMO', { exact: false }).isVisible(), 'DEF-027-E0-DEMO visible');
add('Original customer message is visible', await page.getByText(/moisture and black spots have returned/i).isVisible(), 'message visible');
add('Six source attachments are listed', await page.locator('.attachment-row').count() === 6, `count=${await page.locator('.attachment-row').count()}`);
await page.screenshot({ path: path.join(OUT, '01-submission.png'), fullPage: true });

await page.getByRole('button', { name: /Residential lease agreement/i }).click();
await page.locator('#artifactViewer[open] #pdfPageImage').waitFor({ state: 'visible', timeout: 120000 });
await page.waitForFunction(() => { const img=document.querySelector('#pdfPageImage'); return Boolean(img && img.complete && img.naturalWidth > 0); }, null, { timeout: 60000 });
add('Actual six-page PDF opens', (await page.locator('#artifactViewer #viewerMeta').innerText()).includes('6 pages'), await page.locator('#artifactViewer #viewerMeta').innerText());
await page.getByRole('button', { name: 'Next PDF page' }).click();
await page.locator('#pdfCurrentPage').waitFor({ state: 'visible', timeout: 30000 });
await page.waitForFunction(() => document.querySelector('#pdfCurrentPage')?.textContent === '2', null, { timeout: 30000 });
await page.waitForFunction(() => { const img=document.querySelector('#pdfPageImage'); return Boolean(img && img.complete && img.naturalWidth > 0 && img.alt.includes('page 2')); }, null, { timeout: 60000 });
await page.screenshot({ path: path.join(OUT, '02-actual-pdf-open.png') });
await page.getByRole('button', { name: 'Close attachment viewer' }).click();

await page.getByRole('button', { name: /Bedroom photograph/i }).click();
await page.locator('#artifactViewer[open] #sourceImage').waitFor({ state: 'visible', timeout: 120000 });
await page.waitForFunction(() => { const img=document.querySelector('#sourceImage'); return Boolean(img && img.complete && img.naturalWidth > 0); }, null, { timeout: 60000 });
await page.locator('[data-image-zoom="in"]').click();
add('Actual source image opens and zoom works', (await page.locator('#sourceImage').getAttribute('style') || '').includes('scale'), await page.locator('#sourceImage').getAttribute('style') || '');
await page.screenshot({ path: path.join(OUT, '03-actual-image-open.png') });
await page.getByRole('button', { name: 'Close attachment viewer' }).click();

await page.getByRole('button', { name: /Analyse claim/i }).click();
await page.locator('.stage-item[data-status="started"]').first().waitFor({ state: 'visible', timeout: 60000 });
add('Visible pipeline enters an active stage', true, await page.locator('#analysisLive').innerText());
await page.screenshot({ path: path.join(OUT, '04-agents-processing.png') });

await page.locator('#result:not([hidden])').waitFor({ state: 'visible', timeout: 120000 });
await page.getByText('What caused the recurring mould?', { exact: false }).first().waitFor({ timeout: 60000 });
const blocker = await page.locator('#decisionSummary').innerText();
add('Current blocker is clear', blocker.includes('What caused the recurring mould?'), blocker);
const requiredCount = await page.locator('#evidenceColumn .evidence-item.still_needed').count();
add('Process-derived evidence is visible', requiredCount >= 1, `still_needed=${requiredCount}`);
await page.locator('#result').scrollIntoViewIfNeeded();
await page.screenshot({ path: path.join(OUT, '05-final-process-evidence.png'), fullPage: true });

await page.locator('.precedents-block').scrollIntoViewIfNeeded();
const precedentCount = await page.locator('.precedent-row').count();
add('Exactly three precedents are visible', precedentCount === 3, `count=${precedentCount}`);
const precedentText = await page.locator('.precedent-list').innerText();
add('Each precedent explains why it helps', (precedentText.match(/Why this case helps:/g) || []).length === 3, precedentText.slice(0, 500));
await page.screenshot({ path: path.join(OUT, '06-three-precedents.png') });

await page.locator('#review').scrollIntoViewIfNeeded();
add('Expert review focuses on one consequential decision', await page.getByText(/Make the building-envelope assessment conditional/i).isVisible(), 'conditional option visible');
await page.screenshot({ path: path.join(OUT, '07-expert-correction.png') });
await page.getByRole('button', { name: 'Approve reviewed claim' }).click();
await page.locator('#learning:not([hidden])').waitFor({ state: 'visible', timeout: 60000 });
const learnedText = await page.locator('#learningNow').innerText();
add('Reviewed case becomes immediate case memory', learnedText.includes('Saved as a reviewed precedent'), learnedText);
add('Reusable rule stays quarantined', learnedText.includes('1 of 3') && learnedText.includes('quarantined'), learnedText);
await page.screenshot({ path: path.join(OUT, '08-what-was-learned.png'), fullPage: true });

await page.getByRole('button', { name: /Try what CasePath learned/i }).click();
await page.locator('#laterClaim:not([hidden])').waitFor({ state: 'visible', timeout: 60000 });
const laterText = await page.locator('#laterClaim').innerText();
add('Later unseen claim retrieves expert-reviewed memory', laterText.includes('Expert-reviewed precedent used'), laterText.slice(0, 700));
add('Later evidence sequence improves', laterText.includes('conditional') && laterText.includes('unnecessary immediate technical request'), laterText.slice(0, 700));
await page.screenshot({ path: path.join(OUT, '09-later-claim-improved.png'), fullPage: true });

await page.getByRole('button', { name: 'Audit trail' }).first().click();
await page.locator('#auditDrawer[open]').waitFor({ state: 'visible', timeout: 30000 });
const auditText = await page.locator('#auditContent').innerText();
add('Audit trail reveals specialist agents and validators', auditText.includes('Attachment Parsing Agent') && auditText.includes('Process Graph Agent') && auditText.includes('Document Checklist Agent'), auditText.slice(0, 700));
await page.screenshot({ path: path.join(OUT, '10-audit-trail.png') });
await page.getByRole('button', { name: 'Close audit trail' }).click();

for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 700 }]) {
  const mobile = await browser.newContext({ viewport });
  const mobilePage = await mobile.newPage();
  await mobilePage.goto(`${FRONTEND}/?mobile=${viewport.width}&qa=${Date.now()}`, { waitUntil: 'domcontentloaded', timeout: 120000 });
  await mobilePage.getByRole('heading', { name: /Recurring mould/i }).waitFor({ timeout: 120000 });
  const overflow = await mobilePage.evaluate(() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth));
  add(`No page overflow at ${viewport.width}px`, overflow === 0, `overflow=${overflow}`);
  await mobilePage.screenshot({ path: path.join(OUT, `11-mobile-${viewport.width}.png`), fullPage: true });
  await mobile.close();
}

const proof = await fetchJson(`${API}/api/learning-proof`);
add('Server-side learning proof is ready', proof.body.ready === true, JSON.stringify(proof.body));
add('Approved memory is present in later precedents', (proof.body.after?.precedents || []).some(x => String(x).includes('DEF-027-E0-DEMO')), JSON.stringify(proof.body.after));

await context.close();
await browser.close();

const report = {
  release: '10.0.0',
  frontend: FRONTEND,
  api: API,
  demo_claim: 'DEF-027-E0-DEMO',
  verified_at_utc: new Date().toISOString(),
  passed: checks.filter(x => x.ok).length,
  failed: checks.filter(x => !x.ok).length,
  checks,
  browser_errors: errors,
  success: checks.every(x => x.ok) && errors.length === 0,
};
fs.writeFileSync(path.join(OUT, 'live-browser-qa.json'), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
if (!report.success) process.exit(1);
