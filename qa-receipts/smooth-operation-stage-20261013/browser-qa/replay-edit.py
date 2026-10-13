from pathlib import Path
p=Path('/workspace/casepath-operation-count-repair-20261013/casepath-qa/unified-product-browser-v1.test.cjs')
s=p.read_text()
# Reference playback never observes the closed record, for owners or visitors.
s=s.replace("if(!publicReadOnly){await title(page,id);assert.deepEqual(await visibleRecord(page),{state:fixture.prefixes[id][0].state,projection:fixture.prefixes[id][0].projection});}","if(!publicReadOnly){await title(page,id);assertAcceptedPaint(await acceptedPaint(page),fixture.prefixes[id][0]);}")
s=s.replace("   const pre=document.querySelector('[data-au-record-content] > pre[data-au-record-kind=\"claim\"]'),surface=document.querySelector('[data-au-revision]');\n   if(!surface||!publicReadOnly&&!pre)return;const record=pre?JSON.parse(pre.textContent):null,claim_id=", "   const surface=document.querySelector('[data-au-revision]');\n   if(!surface)return;const claim_id=")
s=s.replace('window.__referencePaints.push({identity,claim_id,...record?{record}:{},revision:', 'window.__referencePaints.push({identity,claim_id,revision:')
s=s.replace("'Existing History drawer instrumentation; complete accepted state and projection for all prefixes.'", "'Uninterrupted native DOM playback, followed by deliberate History DTO inspection for every prefix.'")
s=s.replace("const paint=paints[index],prefix=expected[index];if(!publicReadOnly)assert.deepEqual(paint.record,{state:prefix.state,projection:prefix.projection},`native paint ${index} retains the complete accepted prefix`);", "const paint=paints[index],prefix=expected[index];")
s=s.replace(" if(!publicReadOnly)assert.deepEqual(await visibleRecord(page),{state:fixture.snapshots[referenceIds.at(-1)].state,projection:fixture.snapshots[referenceIds.at(-1)].projection});", " if(!publicReadOnly){for(const prefix of expected){await page.evaluate(({id,through})=>window.__controller.openClaim(id,true,{mode:'replay',collection:'reference',through}),{id:prefix.state.claim_id,through:prefix.through_seq});await title(page,prefix.state.claim_id);assert.deepEqual(await visibleRecord(page),{state:prefix.state,projection:prefix.projection},'deliberate History inspection retains every complete accepted prefix after uninterrupted playback');}}")
# Mocked roster observer tracks actual visible accepted identity.
s=s.replace("      const record = document.querySelector('[data-au-record-content] > pre[data-au-record-kind=\"claim\"]'); if (!record) return;\n      const state = JSON.parse(record.textContent).state;if(!state?.revision)return;", "      const surface=document.querySelector('[data-au-revision]');if(!surface)return;const state={claim_id:decodeURIComponent(location.hash.split('?')[0].slice('#autonomous/claim/'.length)),revision:Number(surface.dataset.auRevision),state_sha256:surface.dataset.auStateSha};if(!state.revision)return;")
s=s.replace("window.__fixture.acceptedHistories[id].slice(1).map(record => record.state)", "window.__fixture.acceptedHistories[id].slice(1).map(({state}) => ({claim_id:state.claim_id,revision:state.revision,state_sha256:state.state_sha256}))")
# Native immutable prefix replay polls only visible content. DTOs remain exact
# through a separately identified deliberate History phase after timed playback.
a=s.index("for (const latency of [0, 120]) test(`focused flow: actual accepted replay prefixes")
b=s.index("test('focused flow: a corrupted prefetched",a)
chunk=s[a:b]
chunk=chunk.replace('let record = await visibleRecord(page);','let paint = await acceptedPaint(page);').replace('record.state.revision','paint.revision').replace('record = await visibleRecord(page);','paint = await acceptedPaint(page);')
chunk=chunk.replace("    assert.deepEqual(record.state, fixture.prefixes[through].state, `prefix ${through} keeps every accepted field and hash`);\n    assert.deepEqual(record.projection, fixture.prefixes[through].projection);", "    assertAcceptedPaint(paint,fixture.prefixes[through],`prefix ${through} keeps its accepted identity and visible objects`);")
chunk=chunk.replace('await formingSnapshot(page,record.state)','await formingSnapshot(page,fixture.prefixes[through].state)')
chunk=chunk.replace("  await page.locator('.au-nav [data-au-nav=\"work\"]').click();", "  if(await page.locator('[data-au-demo-stop]').count())await page.locator('[data-au-demo-stop]').click();\n  for(const through of rendered){const prefix=fixture.prefixes[through];await page.evaluate(({id,through})=>window.__controller.openClaim(id,true,{mode:'replay',through}),{id,through});await title(page,id);assert.deepEqual(await visibleRecord(page),{state:prefix.state,projection:prefix.projection},`deliberate History inspection keeps every accepted field and projection at prefix ${through}`);}\n  await page.locator('.au-nav [data-au-nav=\"work\"]').click();")
s=s[:a]+chunk+s[b:]
# Source modal continuity observes visible accepted identity without reopening it.
s=s.replace("assert.deepEqual(await visibleRecord(page),record);assert.equal(new URL(page.url()).hash,inspectedRoute);", "assertAcceptedPaint(await acceptedPaint(page),prefix);assert.equal(new URL(page.url()).hash,inspectedRoute);",1)
# Polling after an explicit Resume observes the surface; DTO inspection occurs
# only once the next accepted prefix is actually visible.
s=s.replace("let record=await visibleRecord(page);for(let tick=0;record.state.revision===through&&tick<300;tick++){await page.clock.runFor(20);record=await visibleRecord(page);}assert.deepEqual(record,{state:fixture.prefixes[through+1].state,projection:fixture.prefixes[through+1].projection}", "let paint=await acceptedPaint(page);for(let tick=0;paint.revision===through&&tick<300;tick++){await page.clock.runFor(20);paint=await acceptedPaint(page);}assertAcceptedPaint(paint,fixture.prefixes[through+1]);assert.deepEqual(await visibleRecord(page),{state:fixture.prefixes[through+1].state,projection:fixture.prefixes[through+1].projection}")
s=s.replace("let record=await visibleRecord(page);for(let tick=0;record.state.revision===11&&tick<300;tick++){await page.clock.runFor(20);record=await visibleRecord(page);}assert.deepEqual(record.state,fixture.prefixes[12].state);assert.deepEqual(record.projection,fixture.prefixes[12].projection);", "let paint=await acceptedPaint(page);for(let tick=0;paint.revision===11&&tick<300;tick++){await page.clock.runFor(20);paint=await acceptedPaint(page);}assertAcceptedPaint(paint,fixture.prefixes[12]);assert.deepEqual(await visibleRecord(page),{state:fixture.prefixes[12].state,projection:fixture.prefixes[12].projection});")
# Visibility observer must capture the visible accepted surface, not closedpre.
a=s.index('    window.__visibilityPaints = [];')
b=s.index("  await eventually(() => page.evaluate(() => window.__fixture.held.some(row => row.kind === 'replay' && row.through === 9))",a)
chunk=s[a:b]
chunk=chunk.replace('await page.evaluate(() => {','await page.evaluate(captureSource => {',1)
start=chunk.index('    const capture = () => {')
end=chunk.index('    capture();',start)
chunk=chunk[:start]+"    const read=eval(`(${captureSource})`),capture=()=>{const paint=read();if(paint&&window.__visibilityPaints.at(-1)?.revision!==paint.revision)window.__visibilityPaints.push(paint);};\n"+chunk[end:]
chunk=chunk.replace("  });\n  const rendered", "  },acceptedPaintDOM.toString());\n  const rendered",1)
chunk=chunk.replace('let record = await visibleRecord(page);','let paint = await acceptedPaint(page);').replace('record.state.revision','paint.revision').replace('record = await visibleRecord(page);','paint = await acceptedPaint(page);')
chunk=chunk.replace("    assert.deepEqual(record, {state: fixture.prefixes[through].state, projection: fixture.prefixes[through].projection}, `automatic playback consumes exact accepted prefix ${through} before visibility interruption`);", "    assertAcceptedPaint(paint,fixture.prefixes[through],`automatic playback consumes exact accepted prefix ${through} before visibility interruption`);")
s=s[:a]+chunk+s[b:]
a=s.index("  await eventually(() => page.evaluate(() => window.__fixture.held.some(row => row.kind === 'replay' && row.through === 9))")
b=s.index("for (const intent of ['keyboard', 'Pause'])",a)
chunk=s[a:b]
chunk=chunk.replace("assert.deepEqual(await visibleRecord(page), {state: fixture.prefixes[8].state, projection: fixture.prefixes[8].projection}, 'a late next-prefix response cannot paint while hidden');", "assertAcceptedPaint(await acceptedPaint(page),fixture.prefixes[8],'a late next-prefix response cannot paint while hidden');")
chunk=chunk.replace('(await visibleRecord(page)).state.revision','(await acceptedPaint(page)).revision').replace('let record = await visibleRecord(page);','let paint = await acceptedPaint(page);').replace('record.state.revision','paint.revision').replace('record = await visibleRecord(page);','paint = await acceptedPaint(page);')
chunk=chunk.replace("assert.deepEqual(record, {state: fixture.prefixes[9].state, projection: fixture.prefixes[9].projection}, 'automatic restoration consumes only accepted prefix nine after prefix eight');", "assertAcceptedPaint(paint,fixture.prefixes[9],'automatic restoration consumes only accepted prefix nine after prefix eight');")
chunk=chunk.replace("  assert.deepEqual(paints, rendered.map(through => ({state: fixture.prefixes[through].state, projection: fixture.prefixes[through].projection})), 'every native paint remains in exact accepted journal order');", "  assert.deepEqual(paints.map(row=>row.revision),rendered,'every native paint remains in exact accepted journal order');for(const paint of paints)assertAcceptedPaint(paint,fixture.prefixes[paint.revision]);\n  assert.deepEqual(await visibleRecord(page),{state:fixture.prefixes[9].state,projection:fixture.prefixes[9].projection},'deliberate History inspection retains the complete accepted restoration prefix');")
s=s[:a]+chunk+s[b:]
# Remaining native resume loops, including inspection holds, use DOM polls.
s=s.replace("let resumed = await visibleRecord(page);\n  for (let tick = 0; resumed.state.revision === record.state.revision && tick < 300; tick++) { await page.clock.runFor(20); resumed = await visibleRecord(page); }\n  assert.deepEqual(resumed,", "let paint = await acceptedPaint(page);\n  for (let tick = 0; paint.revision === record.state.revision && tick < 300; tick++) { await page.clock.runFor(20); paint = await acceptedPaint(page); }\n  const resumed=await visibleRecord(page);assertAcceptedPaint(paint,fixture.prefixes[2]);\n  assert.deepEqual(resumed,")
for revision in [1,11]:
 old=f"let record = await visibleRecord(page);\n    for (let tick = 0; record.state.revision === {revision} && tick < 300; tick++) {{ await page.clock.runFor(20); record = await visibleRecord(page); }}"
 new=f"let paint = await acceptedPaint(page);\n    for (let tick = 0; paint.revision === {revision} && tick < 300; tick++) {{ await page.clock.runFor(20); paint = await acceptedPaint(page); }}\n    const record=await visibleRecord(page);assertAcceptedPaint(paint,fixture.prefixes[{revision+1}]);"
 s=s.replace(old,new)
 old=old.replace('    for','  for');new=new.replace('    for','  for').replace('    const','  const');s=s.replace(old,new)
# Corrupt playback waits use the visible revision, inspecting only after failure.
s=s.replace("await eventually(async () => (await visibleRecord(page)).state.revision === 2, 'the second accepted prefix did not render');", "await eventually(async () => (await acceptedPaint(page)).revision === 2, 'the second accepted prefix did not render');")
# Source remains actually open during the cancellation assertion.
s=s.replace("else assert.deepEqual((await visibleRecord(page)).state, fixture.prefixes[1].state, 'trusted inspection must leave the current accepted prefix stable through hiding');", "else assertAcceptedPaint(await acceptedPaint(page),fixture.prefixes[1],'trusted inspection must leave the current accepted prefix stable through hiding');")
p.write_text(s)
