import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const base = (process.env.BASE_URL || 'http://127.0.0.1:4173').replace(/\/$/, '');
const out = process.env.PHASE1_SHOTS || '/Users/kumar0002/Documents/Die Mobiliar/casepath-critique-2026-09-23/phase1-shots';
const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH || '/Applications/ego lite.app/Contents/MacOS/ego lite';
const claims = [
  { name: 'flagship', id: 'clm_f69b1747447bc221', flags: { family_home: 'true', extension_relevant: 'true', arrears: 'unresolved' }, words: ['Proof of receipt', 'Spouse notice copy', 'Art. 273'] },
  { name: 'mould', id: 'clm_7ac806bd30792cfb', flags: { health_effects: 'true', mold: 'true', heating: 'unresolved' }, words: ['Medical confirmation', 'Dated photographs', 'Humidity and temperature log'] },
  { name: 'rent', id: 'clm_6f04d0907ecb96bb', flags: { reference_rate: 'true', renovation: 'unresolved' }, words: ['Rent increase notice', 'Reference rate basis', 'Art. 270b'] },
];

const browser = await chromium.launch({ executablePath, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
const errors = [];
const timings = [];
const outputs = [];
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const queue = await context.newPage();
const claimPage = await context.newPage();
for (const page of [queue, claimPage]) {
  page.on('pageerror', error => errors.push(`page: ${error.message}`));
  page.on('console', message => { if (message.type() === 'error') errors.push(`console: ${message.text()}`); });
}

try {
  await fs.mkdir(out, { recursive: true });
  let start = performance.now();
  await queue.goto(`${base}/`, { waitUntil: 'domcontentloaded' });
  await queue.locator('[data-claim-id]').first().waitFor({ timeout: 30000 });
  const queueReadyMs = Math.round(performance.now() - start);

  for (const claim of claims) {
    await claimPage.goto(`${base}/#claim=${claim.id}`, { waitUntil: 'domcontentloaded' });
    await claimPage.locator('#cwDetailPanel').waitFor({ timeout: 30000 });
    await claimPage.locator('#cpReviewCard').waitFor({ timeout: 30000 });
    const before = await claimPage.locator('.cp-source-rail').boundingBox();
    assert(before, `${claim.name}: source rail before review`);
    const button = claimPage.locator('#cwStart');
    assert(await button.count(), `${claim.name}: fresh claim can be reviewed`);
    start = performance.now();
    await button.click();
    await claimPage.locator('.aw-narrative-lines li button').first().waitFor({ timeout: 30000 });
    const firstLineMs = Math.round(performance.now() - start);
    const during = await claimPage.locator('.cp-source-rail').boundingBox();
    await claimPage.locator('.aw-narrative-card[data-status="completed"]').waitFor({ timeout: 90000 });
    await claimPage.waitForFunction(() => Boolean(document.querySelector('#cpReviewCard')?.dataset.assessment), null, { timeout: 30000 });
    const reviewMs = Math.round(performance.now() - start);
    const after = await claimPage.locator('.cp-source-rail').boundingBox();
    assert.equal(before.x, during.x, `${claim.name}: source rail moved during review`);
    assert.equal(before.x, after.x, `${claim.name}: source rail moved after review`);
    const assessment = await claimPage.locator('#cpReviewCard').evaluate(node => JSON.parse(node.dataset.assessment));
    for (const [flag, verdict] of Object.entries(claim.flags)) assert.equal(assessment.conditions[flag]?.verdict, verdict, `${claim.name}: ${flag}`);
    const text = await claimPage.locator('#cwDetailPanel').innerText();
    for (const word of claim.words) assert(text.includes(word), `${claim.name}: missing ${word}`);
    assert.equal(await claimPage.locator('.cp-decision-tabs button').count(), 0, `${claim.name}: obsolete tabs remain`);
    const chain = await claimPage.locator('#cpCanvasTrace li strong').allTextContents();
    assert(chain.every((value, index) => index === 0 || value !== chain[index - 1]), `${claim.name}: repeated adjacent why link`);
    assert(await queue.locator('[data-claim-id]').first().count(), `${claim.name}: second tab lost the queue`);
    const queueReply = await queue.evaluate(async () => {
      const start = performance.now();
      const result = await fetch('/api/claim-loops/v1/workspace/claims?limit=25', { cache: 'no-store' });
      return { status: result.status, ms: Math.round(performance.now() - start) };
    });
    assert.equal(queueReply.status, 200, `${claim.name}: queue errored in the second tab`);
    const output = {
      claim: claim.name, id: claim.id, language: assessment.language,
      noticed: assessment.noticed.map(item => item.text),
      conditions: Object.fromEntries(Object.entries(assessment.conditions).map(([flag, value]) => [flag, { verdict: value.verdict, quote: value.quote || value.candidate_quote || null }])),
      path: assessment.steps.map(step => ({ label: step.label, state: step.state })),
      documents: assessment.documents.map(doc => ({ label: doc.label, route_state: doc.route_state })),
      deadline: assessment.candidate_deadline, next_step: assessment.next_step,
    };
    outputs.push(output);
    timings.push({ claim: claim.name, firstLineMs, reviewMs, queueStatus: queueReply.status, queueReadMs: queueReply.ms, railX: after.x });

    for (const width of [1440, 1024, 390, 320]) {
      const page = width === 1440 ? claimPage : await context.newPage();
      if (width !== 1440) {
        page.on('pageerror', error => errors.push(`page ${width}: ${error.message}`));
        await page.setViewportSize({ width, height: 900 });
        await page.goto(`${base}/#claim=${claim.id}`, { waitUntil: 'domcontentloaded' });
        await page.locator('.cp-a-path').waitFor({ timeout: 30000 });
      }
      const layout = await page.evaluate(() => {
        const box = selector => document.querySelector(selector)?.getBoundingClientRect();
        const rail = box('.cp-source-rail'), path = box('.cp-a-path'), needs = box('.cp-a-needs');
        return { overflow: document.documentElement.scrollWidth - innerWidth, railX: rail?.x, railY: rail?.y, pathY: path?.y, needsY: needs?.y, mobileBar: getComputedStyle(document.querySelector('.cp-a-mobile-action')).display };
      });
      assert.equal(layout.overflow, 0, `${claim.name} ${width}: horizontal overflow`);
      assert(width > 900 ? layout.railX < 0.3 * width : layout.pathY < layout.needsY && layout.needsY < layout.railY, `${claim.name} ${width}: source/path/needs order`);
      if (width <= 900) assert.equal(layout.mobileBar, 'grid', `${claim.name} ${width}: next action bar`);
      await page.screenshot({ path: path.join(out, `${claim.name}-${width}.png`), fullPage: false });
      if (width !== 1440) await page.close();
    }
  }
  assert.deepEqual(errors, []);
  await fs.writeFile(path.join(out, 'phase1-browser-results.json'), JSON.stringify({ queueReadyMs, timings, outputs, errors }, null, 2));
  console.log(JSON.stringify({ queueReadyMs, timings, screenshotDirectory: out, errors }));
} finally {
  await browser.close();
}
