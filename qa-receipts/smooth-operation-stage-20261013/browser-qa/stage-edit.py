from pathlib import Path
p=Path('/workspace/casepath-operation-count-repair-20261013/casepath-qa/unified-product-browser-v1.test.cjs')
s=p.read_text()
# Explicit saved-history entry. Default Demonstration now operates the stage.
s=s.replace("initialFragment:publicReadOnly?'#autonomous/demonstration?mode=replay':'#autonomous'});\n if(!publicReadOnly)await page.locator('.au-nav [data-au-nav=\"demonstration\"]').click();", "initialFragment:`#autonomous/claim/${id}?collection=reference&mode=replay&through=0`});\n // This history-only fixture enters a saved claim, then deliberately starts\n // Play. Default public operation autoplay has separate native acceptance.")
s=s.replace(" },publicReadOnly);\n if(migrated){", " },publicReadOnly);\n if(publicReadOnly)await page.evaluate(()=>document.querySelector('[data-au-demo-play]').click());else await page.locator('[data-au-demo-play]').click();\n if(migrated){",1)
s=s.replace("scope:publicReadOnly?'Public entry without trusted input; native DOM identities and accepted visible content.':", "setup:{entry:`#autonomous/claim/${id}?collection=reference&mode=replay&through=0`,play:publicReadOnly?'Explicit programmatic saved-history Play before unattended traversal':'Native saved-history Play click'},scope:publicReadOnly?'After explicit saved-history Play: no trusted input during native playback; actual visible accepted content.':",1)
s=s.replace("'fresh public playback finishes without any trusted user input'", "'after explicit programmatic saved-history Play, public playback needs no trusted input'")
s=s.replace("'the zero-input public run never opens History or Resume'", "'unattended saved-history traversal never opens History or Resume'")
# Both completed stage and forming surfaces display the actual outcome.
s=s.replace("surface.querySelector('.au-assessment-conclusion > p')", "surface.querySelector('.au-assessment-conclusion > p,.au-stage-outcome > p')")
# Junction assertions keep the exact tolerance; completed stage is horizontal
# on desktop and vertical on mobile, as the native renderer declares.
s=s.replace("return {id:path.dataset.auEdge,source:", "return {id:path.dataset.auEdge,vertical:graph.dataset.orientation==='vertical'||Boolean(graph.closest('.au-operation-stage'))&&matchMedia('(max-width:700px)').matches,source:",1)
s=s.replace("Math.abs(edge.start.x-(edge.source.left+edge.source.width/2))<1&&Math.abs(edge.start.y-edge.source.bottom)<1", "Math.abs(edge.start.x-(edge.vertical?edge.source.left+edge.source.width/2:edge.source.right))<1&&Math.abs(edge.start.y-(edge.vertical?edge.source.bottom:edge.source.top+edge.source.height/2))<1",1)
s=s.replace("Math.abs(edge.end.x-(edge.target.left+edge.target.width/2))<1&&Math.abs(edge.end.y-edge.target.top)<1", "Math.abs(edge.end.x-(edge.vertical?edge.target.left+edge.target.width/2:edge.target.left))<1&&Math.abs(edge.end.y-(edge.vertical?edge.target.top:edge.target.top+edge.target.height/2))<1",1)
# Positive source wire only originates from the actually visible cited source.
s=s.replace("assert.deepEqual(sorted(wires.map(row=>row.kind)),['process-document','source-process']);for(const wire of wires)", "const sourceVisible=await page.locator('.au-forming-reading [data-au-wire=\"source\"]').evaluate(element=>{const r=element.getBoundingClientRect();return r.width>0&&r.height>0&&r.left>=0&&r.top>=0&&r.right<=innerWidth&&r.bottom<=innerHeight;});assert.deepEqual(sorted(wires.map(row=>row.kind)),sourceVisible?['process-document','source-process']:['process-document']);if(width===1440)assert.equal(sourceVisible,true,'the desktop source-wire assertion uses the complete visible cited source');for(const wire of wires)",1)
old=''' assert.equal(await page.locator('[data-au-settled="true"]').count(),1);assert.ok((await page.locator('.au-assessment-conclusion').innerText()).includes(head.state.outcome.summary));
 assert.deepEqual(sorted(await page.locator('.au-forming-documents [data-au-obligation]').evaluateAll(rows=>rows.map(row=>row.dataset.auObligation))),sorted(head.state.obligations.map(row=>row.obligation_id)));
 assert.equal(await page.locator('.au-forming-documents .au-document-review[data-au-review="sufficient"]').count(),3);assert.equal(await page.locator('.au-forming-documents [data-au-source][data-au-citation]').count(),3);
 const publication=head.state.knowledge_published[0];assert.equal(await page.locator(`[data-au-knowledge-publication="${publication.knowledge_sha256}"]`).count(),1);assert.equal(await page.locator(`[data-au-knowledge-sha="${publication.knowledge_sha256}"]`).getAttribute('data-au-version'),String(publication.version));
 const connectors=await junctionConnections(page);'''
new=''' assert.equal(await page.locator('.au-operation-stage[data-au-stage-phase="map"]').count(),1);assert.ok((await page.locator('.au-stage-outcome').innerText()).includes(head.state.outcome.summary));
 assert.deepEqual(sorted(await page.locator('.au-operation-stage [data-au-stage-document]').evaluateAll(rows=>rows.map(row=>row.dataset.auStageDocument))),sorted(head.state.obligations.map(row=>row.document_type)));
 assert.equal(await page.locator('.au-operation-stage [data-au-document-checked="true"]').count(),3);assert.equal(await page.locator('.au-operation-stage [data-au-source][data-au-citation]').count(),3);
 for(const citation of await page.locator('.au-operation-stage [data-au-citation]').evaluateAll(rows=>rows.map(row=>JSON.parse(row.dataset.auCitation)))){assert.ok(head.state.facts.flatMap(row=>row.citations||[]).some(row=>canonical(row)===canonical(citation)));assert.equal(citation.sha256,head.state.source_descriptors.find(row=>row.artifact_id===citation.artifact_id).sha256);}
 assert.deepEqual(sorted(await page.locator('.au-stage-outcome [data-au-law-article]').evaluateAll(rows=>rows.map(row=>row.dataset.auLawArticle))),['259','259a','259d']);
 const connectors=await junctionConnections(page);assert.deepEqual(await visibleRecord(page),{state:head.state,projection:head.projection});
 await page.locator('.au-work-head [data-au-detail="activity"]').click();await page.locator('.au-context-nav [data-au-detail="knowledge"]').click();
 const publication=head.state.knowledge_published[0];assert.equal(await page.locator(`[data-au-knowledge-publication="${publication.knowledge_sha256}"]`).count(),1);assert.equal(await page.locator(`[data-au-knowledge-sha="${publication.knowledge_sha256}"]`).getAttribute('data-au-version'),String(publication.version));
 await page.locator('.au-context-nav [data-au-detail="step"]').click();'''
assert old in s;s=s.replace(old,new)
# Full DOM snapshot must reject a lost graph on the Process surface.
s=s.replace("return {claim_id:decodeURIComponent(location.hash.split('?')[0].slice('#autonomous/claim/'.length)),revision:", "return {panel:surface.querySelector('[data-au-panel]')?.dataset.auPanel,claim_id:decodeURIComponent(location.hash.split('?')[0].slice('#autonomous/claim/'.length)),revision:",1)
s=s.replace('if(paint.nodes.length)assert.deepEqual','if(paint.panel===\'step\')assert.deepEqual').replace('if(paint.edges.length)assert.deepEqual','if(paint.panel===\'step\')assert.deepEqual')
s=s.replace("assert.equal(paint.outcome,state.outcome?.summary||null,message);", "assert.equal(paint.outcome,paint.panel==='step'?state.outcome?.summary||null:null,message);")
# Migrate hold tests inspect no hidden or open-modal UI.
s=s.replace("await page.clock.runFor(8000);if(inspection==='source')assertAcceptedPaint(await acceptedPaint(page),prefix);else assert.deepEqual(await visibleRecord(page),record);", "await page.clock.runFor(8000);assertAcceptedPaint(await acceptedPaint(page),prefix);")
# Overlapping reads: baseline DTO before native modal; visible paint and original
# disclosure identity during it; exact DTO again after ordinary Close.
a=s.index("test('overlapping opening reads preserve")
b=s.index("test('a Documents link",a)
c=s[a:b]
c=c.replace("await eventually(async () => (await visibleRecord(page)).state.revision === revision + 1", "await eventually(async () => (await acceptedPaint(page)).revision === revision + 1")
c=c.replace("  const sourceId =", "  const before=await visibleRecord(page);\n  const sourceId =",1).replace("  const before = await visibleRecord(page);", "  const inspectedPaint=await acceptedPaint(page);")
c=c.replace('assert.deepEqual(await visibleRecord(page), before,','assert.deepEqual(await acceptedPaint(page), inspectedPaint,')
c=c.replace("  assert.deepEqual(await acceptedPaint(page), inspectedPaint, 'a conflicting equal-revision hash fails closed while saved work remains visible');", "  assert.deepEqual(await acceptedPaint(page), inspectedPaint, 'a conflicting equal-revision hash fails closed while saved work remains visible');\n  await page.locator('[data-au-close]').click();assert.deepEqual(await visibleRecord(page),before,'History exposes the exact retained newer DTO after native source close');")
s=s[:a]+c+s[b:]
p.write_text(s)
