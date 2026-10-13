from pathlib import Path
p=Path('/workspace/casepath-operation-count-repair-20261013/casepath-qa/unified-product-browser-v1.test.cjs')
s=p.read_text()
a=s.index('  // Request the actual product\'s single technical drawer once.')
b=s.index('\n}',a)
s=s[:a]+s[b:]
s=s.replace("  if(prior.playing)await page.locator('[data-au-demo-resume]').click();", "  if(prior.playing)assert.equal(await page.locator('[data-au-demo-resume]').count(),1,'actual History inspection holds replay until deliberate Resume');")
s=s.replace('const visibleRecord = page => page.locator(\'[data-au-record-content] > pre[data-au-record-kind="claim"]\').textContent().then(JSON.parse);', '''// Full DTO observation is an explicit product inspection. Passive playback
// observers below read the accepted visible surface and never open History.
const visibleRecord = page => caseDetails(page);
function acceptedPaintDOM() {
  const surface=document.querySelector('[data-au-revision]');if(!surface)return null;
  return {claim_id:decodeURIComponent(location.hash.split('?')[0].slice('#autonomous/claim/'.length)),revision:Number(surface.dataset.auRevision),state_sha256:surface.dataset.auStateSha,
    nodes:[...surface.querySelectorAll('[data-au-node]')].map(row=>({id:row.dataset.auNode,activation:row.dataset.activation,status:row.dataset.status})),
    edges:[...surface.querySelectorAll('[data-au-edge]')].map(row=>({id:row.dataset.auEdge,source:row.dataset.auEdgeSource,target:row.dataset.auEdgeTarget,activation:row.dataset.state})),
    forming:[...surface.querySelectorAll('[data-au-forming-revision]')].map(row=>({revision:Number(row.dataset.auFormingRevision),state_sha256:row.dataset.auFormingSha})),
    documents:[...surface.querySelectorAll('.au-forming-documents .au-obligation')].map(row=>({id:row.dataset.auObligation,type:row.dataset.auDocument,status:row.dataset.status,review:row.querySelector('[data-au-review]')?.dataset.auReview||null})),
    facts:[...surface.querySelectorAll('[data-au-fact],[data-au-fact-select]')].map(row=>({id:row.dataset.auFact||row.dataset.auFactSelect,status:row.dataset.auFactState||null})),
    sources:[...surface.querySelectorAll('[data-au-source-identity]')].map(row=>row.dataset.auSourceIdentity),
    citations:[...surface.querySelectorAll('[data-au-citation]')].map(row=>JSON.parse(row.dataset.auCitation)),
    knowledge:[...surface.querySelectorAll('[data-au-knowledge][data-au-version]')].map(row=>({id:row.dataset.auKnowledge,version:row.dataset.auVersion,sha256:row.dataset.auKnowledgeSha||''})),
    outcome:surface.querySelector('.au-assessment-conclusion > p')?.textContent||null};
}
const acceptedPaint = page => page.evaluate(acceptedPaintDOM);
function assertAcceptedPaint(paint,prefix,message='the visible accepted prefix retains its exact native identities and content') {
  const state=prefix.state;
  assert.ok(paint,message);assert.equal(paint.claim_id,state.claim_id,message);assert.equal(paint.revision,state.revision,message);assert.equal(paint.state_sha256,state.state_sha256,message);
  const byId=rows=>[...rows].sort((a,b)=>a.id.localeCompare(b.id)),evaluations=new Map((state.evaluation?.nodes||[]).map(row=>[row.node_id,row]));
  if(paint.nodes.length)assert.deepEqual(byId(paint.nodes),byId((state.graph?.nodes||[]).map(row=>{const evaluated=evaluations.get(row.node_id)||{};return {id:row.node_id,activation:evaluated.activation||'unresolved',status:evaluated.execution_state||evaluated.state||'pending'};})),message);
  if(paint.edges.length)assert.deepEqual(byId(paint.edges),byId((state.graph?.edges||[]).map(row=>({id:row.edge_id,source:row.source_node_id,target:row.target_node_id,activation:state.evaluation?.edges.find(edge=>edge.edge_id===row.edge_id)?.activation||'unresolved'}))),message);
  for(const row of paint.forming)assert.deepEqual(row,{revision:state.revision,state_sha256:state.state_sha256},message);
  for(const row of paint.documents){const obligation=state.obligations.find(item=>item.obligation_id===row.id),document=state.evaluation?.documents.find(item=>item.document_type===row.type);assert.ok(obligation,message);assert.equal(row.type,obligation.document_type,message);assert.equal(row.status,document?.route_state||obligation.status||'pending',message);if(row.review)assert.equal(row.review,document?.review_state,message);}
  for(const row of paint.facts){const fact=state.facts.find(item=>item.fact_id===row.id);assert.ok(fact,message);if(row.status)assert.equal(row.status,fact.verdict||fact.status,message);}
  for(const identity of paint.sources)assert.ok(state.source_descriptors.some(row=>identity===`${state.claim_id}:${row.artifact_id}:${row.sha256}:${state.acquired_sources.find(source=>source.artifact_id===row.artifact_id)?.text_sha256||''}`),message);
  const citations=state.facts.flatMap(row=>row.citations||[]).concat(state.actions.flatMap(row=>(row.result||row).citations||[]));
  for(const citation of paint.citations){assert.ok(citations.some(row=>canonical(row)===canonical(citation)),message);assert.equal(citation.sha256,state.source_descriptors.find(row=>row.artifact_id===citation.artifact_id)?.sha256,message);}
  for(const pin of paint.knowledge)assert.ok([...state.knowledge_uses,...state.knowledge_published].some(row=>(row.knowledge_id||row.version_id)===pin.id&&String(row.version||row.version_id)===pin.version&&(row.knowledge_sha256||'')===pin.sha256),message);
  assert.equal(paint.outcome,state.outcome?.summary||null,message);
}''')
# Extract the existing connector assertions without changing thresholds.
a=s.index("        const connector=await page.locator('[data-au-forming-wire=\"process-document\"]')")
b=s.index('        after.connector=connector;',a)
connector=s[a:b].replace('        ','  ')
helper='\nasync function requirementConnector(page) {\n'+connector+'  return connector;\n}\n'
start=s.index('      if(width>1000){assert.deepEqual(sorted(wires.map(row=>row.kind))')
end=s.index('      await focusedReceipt(page,`forming-live-after-',start)
s=s[:start]+'''      assert.equal(await page.locator('[data-au-forming-wire="process-document"]').count(),0,'an upstream-blocked requirement cannot gain an active document connector');
      if(width<=1000)assert.equal(await page.locator('[data-au-forming-wire]:visible').count(),0,'mobile does not paint connections through stacked reading content');
'''+s[end:]
pos=s.index('\nasync function junctionConnections')
s=s[:pos]+helper+s[pos:]
# Retain object identity before intentional History navigation.
old="    if(through===11)assert.equal(await page.evaluate(()=>Object.values(window.__formingObjects).flat().every(element=>element.isConnected)),true,'unchanged accepted graph and requirement identities retain their original native nodes and buttons');\n"
s=s.replace(old,'')
needle='    const expected=fixture.prefixes[through];assert.deepEqual(await visibleRecord(page)'
s=s.replace(needle,"    if(through===11)assert.equal(await page.evaluate(()=>Object.values(window.__formingObjects).flat().every(element=>element.isConnected)),true,'unchanged accepted graph and requirement identities retain their original native nodes and buttons');\n"+needle,1)
# Spouse is received source review in Documents, not a reached active requirement.
old='''      const row=page.locator('.au-forming-documents [data-au-document="spouse_notice_copy"]');assert.equal(await row.getAttribute('data-status'),'established');assert.match(await row.locator('.au-document-review').innerText(),/sufficient/i);
      assert.equal(await page.locator('[data-au-node="lt_family"]').getAttribute('data-status'),'blocked','sufficient source evidence does not establish an earlier process prerequisite');
      const obligation=expected.state.obligations.find(item=>item.document_type==='spouse_notice_copy');await row.locator(`[data-au-select-obligation="${obligation.obligation_id}"]`).click();'''
new='''      const obligation=expected.state.obligations.find(item=>item.document_type==='spouse_notice_copy'),family=expected.state.evaluation.nodes.find(item=>item.node_id===obligation.node_id),document=expected.state.evaluation.documents.find(item=>item.document_type===obligation.document_type);
      assert.equal(family.execution_state,'blocked');assert.deepEqual(family.blocked_by,['lt_type']);assert.deepEqual(family.missing_document_types,[]);assert.equal(document.route_state,'established');assert.equal(document.review_state,'sufficient');
      assert.equal(await page.locator('.au-forming-documents [data-au-document="spouse_notice_copy"]').count(),0,'received sufficient source evidence does not make an upstream-blocked requirement active');
      assert.equal(await page.locator('[data-au-node="lt_family"]').getAttribute('data-status'),'blocked','sufficient source evidence does not establish an earlier process prerequisite');
      await page.locator('.au-forming-documents [data-au-detail="documents"]').click();const row=page.locator('[data-au-panel="documents"] [data-au-document="spouse_notice_copy"]');assert.equal(await row.getAttribute('data-status'),'established');assert.match(await row.locator('.au-document-review').innerText(),/sufficient/i);
      await row.locator(`[data-au-select-obligation="${obligation.obligation_id}"]`).click();'''
assert old in s;s=s.replace(old,new)
s=s.replace("      const source=row.locator('[data-au-source][data-au-citation]').first();", "      const source=page.locator('.au-forming-reading [data-au-source][data-au-citation]').first();",1)
s=s.replace("assert.deepEqual((await visibleRecord(page)).state,fixture.prefixes[12].state);assert.equal(await page.evaluate(()=>document.querySelector('.au-source-dialog').open", "assertAcceptedPaint(await acceptedPaint(page),fixture.prefixes[12]);assert.equal(await page.evaluate(()=>document.querySelector('.au-source-dialog').open",1)
s=s.replace("      const current=fixture.prefixes[12].state,after=", "      assert.deepEqual(await visibleRecord(page),{state:fixture.prefixes[12].state,projection:fixture.prefixes[12].projection});\n      const current=fixture.prefixes[12].state,after=",1)
# Exercise the actual reached requirements with the full positive geometry helper.
a=s.index('  if(through===18){\n   const probe=')
b=s.index('\n  }\n }\n const head=',a)
old=s[a:b+4]
probe=old[old.index('   const probe='):old.index('   const row=')]
new="  if([18,19,21].includes(through)){\n"+"   if(through===18){\n"+probe+"   }\n"+'''   const type=types.at(-1),obligation=prefix.state.obligations.find(item=>item.document_type===type),node=prefix.state.evaluation.nodes.find(item=>item.node_id===obligation.node_id),fact=prefix.state.facts.find(item=>item.fact_id===obligation.required_fact_ids[0]);
   assert.equal(node.activation,'true');assert.ok(['ready','completed'].includes(node.execution_state),'positive interaction requires an actually reached native step');assert.equal(prefix.state.evaluation.documents.find(item=>item.document_type===type).review_state,'sufficient');assert.ok(fact.citations.length);
   const row=page.locator(`.au-forming-documents [data-au-obligation="${obligation.obligation_id}"]`);await row.locator(`[data-au-select-obligation="${obligation.obligation_id}"]`).click();assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'),obligation.node_id);
   const origin=row.locator('[data-au-source][data-au-citation]').first();assert.equal(await origin.count(),1);const citation=JSON.parse(await origin.getAttribute('data-au-citation'));assert.ok(fact.citations.some(item=>canonical(item)===canonical(citation)));assert.equal(citation.sha256,prefix.state.source_descriptors.find(item=>item.artifact_id===citation.artifact_id).sha256);
   await origin.focus();await page.keyboard.press('Enter');await eventually(()=>page.locator('.au-source-dialog[open] mark').count().then(count=>count===1),'exact native requirement source did not open');assert.equal(await page.locator('.au-source-dialog mark').textContent(),citation.quote);await page.locator('[data-au-close]').click();assert.equal(await origin.evaluate(element=>element===document.activeElement),true);
   if(width>1000){const wires=await page.locator('[data-au-forming-wire]').evaluateAll(rows=>rows.filter(row=>getComputedStyle(row).display!=='none'&&row.getBoundingClientRect().width>0).map(row=>({kind:row.dataset.auFormingWire,fact:row.dataset.auWireFact,source:row.dataset.auWireSource,node:row.dataset.auWireNode,obligation:row.dataset.auWireObligation,path:row.getAttribute('d')})));assert.deepEqual(sorted(wires.map(row=>row.kind)),['process-document','source-process']);for(const wire of wires){assert.equal(wire.fact,obligation.required_fact_ids[0]);assert.equal(wire.source,citation.artifact_id);assert.equal(wire.node,obligation.node_id);assert.equal(wire.obligation,obligation.obligation_id);assert.ok(wire.path);}await focusedReceipt(page,`causal-native-requirement-connector-${through}-${width}x${height}`,{through,obligation:obligation.obligation_id,citation,connector:await requirementConnector(page)});}
   else assert.equal(await page.locator('[data-au-forming-wire]:visible').count(),0,'mobile does not paint connections through stacked reading content');
  }'''
s=s[:a]+new+s[b+4:]
p.write_text(s)
