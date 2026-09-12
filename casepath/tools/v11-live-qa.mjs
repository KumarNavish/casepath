import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND = process.env.CASEPATH_FRONTEND || 'https://casepath-swiss-claim-lab.onrender.com';
const API = process.env.CASEPATH_API || 'https://casepath-agentic-api.onrender.com';
const OUT = process.env.CASEPATH_QA_OUT || 'casepath/reports/v11-live';
fs.mkdirSync(OUT, { recursive: true });

const checks = [];
const browserErrors = [];
const add = (name, ok, detail = '') => checks.push({ name, ok: Boolean(ok), detail });
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function fetchText(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  if (!response.ok) throw new Error(`${response.status} ${url}: ${text.slice(0, 300)}`);
  return { response, text };
}
async function fetchJson(url, options = {}) {
  const result = await fetchText(url, options);
  return { response: result.response, body: JSON.parse(result.text) };
}
async function waitJson(url, predicate, attempts = 48) {
  let last;
  for (let i = 0; i < attempts; i += 1) {
    try {
      const result = await fetchJson(`${url}${url.includes('?') ? '&' : '?'}nocache=${Date.now()}`, { headers: { 'Cache-Control': 'no-cache' } });
      last = result;
      if (predicate(result.body)) return result;
    } catch (error) { last = error; }
    await sleep(5000);
  }
  throw new Error(`Timed out waiting for ${url}: ${String(last)}`);
}

const release = await waitJson(`${FRONTEND}/release.json`, body => body?.release === '11.0.0');
add('Frontend identifies release 11.0.0', release.body.release === '11.0.0', JSON.stringify(release.body));
for (const asset of ['assets/process-v11.css', 'assets/process-v11.js']) {
  const result = await fetchText(`${FRONTEND}/${asset}?nocache=${Date.now()}`, { headers: { 'Cache-Control': 'no-cache' } });
  add(`${asset} is publicly available`, result.response.status === 200 && result.text.length > 1000, `status=${result.response.status}, bytes=${result.text.length}`);
}
const api = await waitJson(`${API}/healthz`, body => body?.status === 'ok' || Boolean(body?.release));
add('Agentic API is reachable', Boolean(api.body.status || api.body.release), JSON.stringify(api.body));
await fetchJson(`${API}/api/demo/reset`, { method: 'POST' });

const browser = await chromium.launch({ headless: true });
const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const page = await desktop.newPage();
page.on('console', message => { if (message.type() === 'error') browserErrors.push(`console: ${message.text()}`); });
page.on('pageerror', error => browserErrors.push(`pageerror: ${error.message}`));

const response = await page.goto(`${FRONTEND}/?v11qa=${Date.now()}`, { waitUntil: 'domcontentloaded', timeout: 120000 });
add('Canonical frontend returns HTTP 200', response?.status() === 200, `status=${response?.status()}`);
await page.getByRole('heading', { name: /Recurring mould/i }).waitFor({ timeout: 120000 });
add('Default demo claim is visible', await page.getByText('DEF-027-E0-DEMO', { exact: false }).isVisible(), 'claim id visible');
add('Original submission remains visible', await page.getByText(/moisture and black spots have returned/i).isVisible(), 'customer message visible');
add('All six source attachments remain available', await page.locator('.attachment-row').count() === 6, `count=${await page.locator('.attachment-row').count()}`);

await page.getByRole('button', { name: /Analyse claim/i }).click();
await page.locator('.stage-item[data-status="started"]').first().waitFor({ state: 'visible', timeout: 60000 });
add('Analysis enters a real active pipeline stage', true, await page.locator('#analysisLive').innerText());
await page.screenshot({ path: path.join(OUT, '01-agents-processing.png') });

await page.locator('#result:not([hidden])').waitFor({ state: 'visible', timeout: 120000 });
await page.locator('.cp-process-graph').waitFor({ state: 'visible', timeout: 60000 });
add('New decision graph is rendered', await page.locator('.cp-process-graph').isVisible(), 'graph visible');
add('Lifecycle rail contains seven stages', await page.locator('.cp-stage-rail > li').count() === 7, `count=${await page.locator('.cp-stage-rail > li').count()}`);
add('Completed decisions are visually quiet', await page.locator('.cp-graph-step.is-complete').count() >= 3, `completed=${await page.locator('.cp-graph-step.is-complete').count()}`);
const currentText = await page.locator('.cp-graph-step.is-current').innerText();
add('Exactly one current decision is dominant', await page.locator('.cp-graph-step.is-current').count() === 1 && /cause|causation|mould/i.test(currentText), currentText);
const blockerText = await page.locator('#decisionSummary').innerText();
add('Current blocker remains explicit', blockerText.includes('What caused the recurring mould?'), blockerText);
add('Evidence stays linked to the current question', await page.locator('#evidenceColumn .evidence-item.still_needed').count() >= 1, await page.locator('#evidenceColumn').innerText());

const branchToggle = page.locator('.cp-branch-toggle');
if (await branchToggle.count()) {
  await branchToggle.click();
  add('Alternative decision branches reveal progressively', await page.locator('.cp-branch-grid:not([hidden]) .cp-branch-card').count() >= 2, `branches=${await page.locator('.cp-branch-card').count()}`);
} else {
  add('Alternative decision branches reveal progressively', false, 'No branch control found');
}
await page.locator('[data-cp-zoom="in"]').click();
add('Process zoom control works', (await page.locator('.cp-process-tools output').innerText()).includes('110%'), await page.locator('.cp-process-tools output').innerText());
await page.locator('#result').scrollIntoViewIfNeeded();
await page.screenshot({ path: path.join(OUT, '02-process-graph-1440x900.png'), fullPage: true });

await page.setViewportSize({ width: 1280, height: 800 });
await page.screenshot({ path: path.join(OUT, '03-process-graph-1280x800.png'), fullPage: true });
add('Decision graph remains visible at 1280px', await page.locator('.cp-process-graph').isVisible(), 'visible');

for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 700 }]) {
  const mobile = await browser.newContext({ viewport });
  const mobilePage = await mobile.newPage();
  const mobileErrors = [];
  mobilePage.on('console', message => { if (message.type() === 'error') mobileErrors.push(message.text()); });
  mobilePage.on('pageerror', error => mobileErrors.push(error.message));
  await mobilePage.goto(`${FRONTEND}/?v11mobile=${viewport.width}&qa=${Date.now()}`, { waitUntil: 'domcontentloaded', timeout: 120000 });
  await mobilePage.getByRole('heading', { name: /Recurring mould/i }).waitFor({ timeout: 120000 });
  await mobilePage.getByRole('button', { name: /Analyse claim/i }).click();
  await mobilePage.locator('.cp-process-graph').waitFor({ state: 'visible', timeout: 120000 });
  const overflow = await mobilePage.evaluate(() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth));
  const internalScroll = await mobilePage.locator('.cp-graph-viewport').evaluate(element => element.scrollWidth > element.clientWidth);
  add(`No page-level horizontal overflow at ${viewport.width}px`, overflow === 0, `overflow=${overflow}`);
  add(`Complex graph scroll is contained internally at ${viewport.width}px`, internalScroll, `internalScroll=${internalScroll}`);
  add(`No browser errors at ${viewport.width}px`, mobileErrors.length === 0, mobileErrors.join('; '));
  await mobilePage.screenshot({ path: path.join(OUT, `04-process-mobile-${viewport.width}.png`), fullPage: true });
  await mobile.close();
}

await desktop.close();
await browser.close();

const report = {
  release: '11.0.0',
  frontend: FRONTEND,
  api: API,
  source_commit: '2cbac8fc38dcee41c952b71df5552ce172b6fbf7',
  render_deploy: 'dep-d9rf36dbedkc73bkgt4g',
  verified_at_utc: new Date().toISOString(),
  passed: checks.filter(item => item.ok).length,
  failed: checks.filter(item => !item.ok).length,
  checks,
  browser_errors: browserErrors,
};
report.success = report.failed === 0 && report.browser_errors.length === 0;
fs.writeFileSync(path.join(OUT, 'live-browser-qa.json'), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
if (!report.success) process.exit(1);
