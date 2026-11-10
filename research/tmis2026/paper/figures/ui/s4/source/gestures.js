// node gestures.js <port> <out-dir> <case-id> <phase>
// The feedback gestures the interface at 6a72159c offers, done as a case handler does them, in the browser,
// on the open-variant mould claim. Each capture is the rendered page or one element of it (cropped only).
//   phase "rate":   result checker, mark the first open point correct (the ✓ button) -> feedback line counts it
//   phase "done":   overview, "Done" on the point "Decides the path, no source yet: ..." -> listed as settled
//   phase "form":   process builder, "Edit decision", add a document need with a reason (form filled, not sent)
//   phase "submit": the same form, sent; then the process builder and document finder after the change
const { chromium } = require('playwright');
(async () => {
  const [port, out, CASE, phase] = process.argv.slice(2);
  const b = await chromium.launch({ args: ['--no-proxy-server'] });
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const go = async (tab) => { await p.goto(`http://127.0.0.1:${port}/?lang=en#/case/${CASE}/${tab}`, { waitUntil: 'networkidle' }); await p.waitForTimeout(2500); };
  const shot = async (name, loc) => { if (loc) await loc.screenshot({ path: `${out}/${name}.png` }); else await p.screenshot({ path: `${out}/${name}.png`, fullPage: true }); };
  if (phase === 'rate') {
    await go('result_checker');
    await shot('g1-before');
    await p.locator('[data-rate][data-verdict="correct"]').first().click();
    await p.waitForTimeout(2000);
    await shot('g1-after');
    await shot('g1-line', p.locator('.cp-feedback-line').first());
    const li = p.locator('li').filter({ has: p.locator('[data-rate][aria-pressed="true"]') }).first();
    await shot('g1-item', li);
  }
  if (phase === 'done') {
    await go('overview');
    await shot('g2-before');
    const btn = p.locator('[data-point-done^="path."]').first();
    await btn.click();
    await p.waitForTimeout(2000);
    await shot('g2-after');
  }
  if (phase === 'form' || phase === 'submit') {
    await go('process_builder');
    await p.getByText('Edit decision').first().click();
    await p.waitForTimeout(1200);
    const form = p.locator('#edit-form');
    await form.locator('select[name="op"]').selectOption('add_document');
    await form.locator('input[name="title"]').fill('Ventilation and heating record');
    await form.locator('input[name="why"]').fill('It shows whether the tenant ventilated and heated the rooms.');
    await form.locator('textarea[name="reason"]').fill('The landlord will argue that the mould comes from ventilation.');
    await form.locator('input[name="similar"]').check();
    await p.waitForTimeout(500);
    await shot('g3-form-page');
    await shot('g3-form', form);
    if (phase === 'submit') {
      await form.locator('button[type="submit"], input[type="submit"]').first().click();
      await p.waitForTimeout(4000);
      await shot('g3-after-page');
    }
  }
  await b.close();
})();
