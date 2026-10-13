for (const reduced of [false, true]) test(`replay visibility: an in-flight next prefix survives hide show and programmatic focus through eight with reduced motion ${reduced}`, async t => {
  const fixture = priorAssessmentFixture(), id = fixture.claim_id;
  const {page} = await actualJournalPresentation(t, {holdReplayId: id, holdReplayThrough: 2});
  await page.emulateMedia({reducedMotion: reduced ? 'reduce' : 'no-preference'});
  await eventually(() => page.evaluate(() => window.__fixture.held.some(row => row.kind === 'replay')), 'the exact next accepted prefix was not held in flight');
  await page.evaluate(() => {
    window.__visibilityPaints = [];
    const capture = () => {
      const pre = document.querySelector('[data-au-record-content] > pre[data-au-record-kind="claim"]');
      if (!pre) return; const record = JSON.parse(pre.textContent);
      if (record.state && window.__visibilityPaints.at(-1)?.state.revision !== record.state.revision) window.__visibilityPaints.push(record);
    };
    capture(); window.__visibilityObserver = new MutationObserver(capture);
    window.__visibilityObserver.observe(document.querySelector('#workspace'), {childList: true, subtree: true});
    window.__fixture.hidden = true;
    Object.defineProperty(document, 'hidden', {configurable: true, get: () => window.__fixture.hidden});
    document.dispatchEvent(new Event('visibilitychange'));
  });
  const hiddenReads = (await calls(page, `/claims/${id}/replay`)).length;
  await page.evaluate(() => { window.__fixture.holdReplayId = null; for (const row of window.__fixture.held.splice(0)) row.release(); });
  await page.clock.runFor(8000);
  assert.deepEqual(await visibleRecord(page), {state: fixture.prefixes[1].state, projection: fixture.prefixes[1].projection}, 'a late next-prefix response cannot paint while hidden');
  assert.equal((await calls(page, `/claims/${id}/replay`)).length, hiddenReads, 'hidden playback cannot drain a replay queue');
  assert.equal(await page.evaluate(() => document.getAnimations().filter(row => row.playState === 'running').length), 0, 'hidden playback cancels native visual motion');
  await page.evaluate(() => {
    window.__fixture.hidden = false; document.dispatchEvent(new Event('visibilitychange'));
    const heading = document.querySelector('h1'); heading.focus(); heading.blur(); heading.focus();
    window.dispatchEvent(new Event('blur')); window.dispatchEvent(new Event('focus')); window.dispatchEvent(new Event('resize'));
    document.fonts.dispatchEvent(new Event('loadingdone'));
    for (const key of ['Tab', 'ArrowDown', 'ArrowRight']) document.dispatchEvent(new KeyboardEvent('keydown', {key, bubbles: true}));
  });
  assert.equal(await page.locator('[data-au-demo-resume]').count(), 0, 'visibility and untrusted focus or keyboard events cannot create an inspection hold');
  await page.clock.runFor(100);
  assert.equal((await visibleRecord(page)).state.revision, 1, 'restoration gives the held prefix a reading interval before its exact next prefix');
  const rendered = [], times = [];
  for (let through = 1; through <= 8; through++) {
    let record = await visibleRecord(page);
    for (let tick = 0; record.state.revision < through && tick < 300; tick++) { await page.clock.runFor(20); record = await visibleRecord(page); }
    assert.deepEqual(record, {state: fixture.prefixes[through].state, projection: fixture.prefixes[through].projection}, `automatic restoration consumes exact accepted prefix ${through}`);
    assert.equal(await page.locator('[data-au-demo-resume]').count(), 0);
    rendered.push(through); times.push(await page.evaluate(() => performance.now()));
    if (through === 4) {
      await page.evaluate(() => { window.__fixture.hidden = true; document.dispatchEvent(new Event('visibilitychange')); });
      const reads = (await calls(page, `/claims/${id}/replay`)).length;
      await page.clock.runFor(8000);
      assert.deepEqual(await visibleRecord(page), record); assert.equal((await calls(page, `/claims/${id}/replay`)).length, reads);
      await page.evaluate(() => { window.__fixture.hidden = false; document.dispatchEvent(new Event('visibilitychange')); document.querySelector('h1').focus(); });
      await page.emulateMedia({reducedMotion: reduced ? 'no-preference' : 'reduce'});
      await page.emulateMedia({reducedMotion: reduced ? 'reduce' : 'no-preference'});
      await page.clock.runFor(100); assert.deepEqual(await visibleRecord(page), record, 'repeat restoration cannot burst into later prefixes');
    }
  }
  const paints = await page.evaluate(() => { window.__visibilityObserver.disconnect(); return window.__visibilityPaints; });
  assert.deepEqual(paints, rendered.map(through => ({state: fixture.prefixes[through].state, projection: fixture.prefixes[through].projection})), 'every native paint remains in exact accepted journal order');
  assert.equal((await calls(page, `/claims/${demoIds[1]}/replay`)).length, 0);
  assert.doesNotMatch(await page.locator('.au-global-status').innerText(), /out of sequence|changed identity|stopped/i);
  await focusedReceipt(page, `replay-visibility-through8-${reduced}`, {id, reduced, rendered, virtualTimes: times, calls: await calls(page, `/claims/${id}/replay`)});
  await page.locator('.au-nav [data-au-nav="work"]').click();
});

