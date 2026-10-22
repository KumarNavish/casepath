'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {gunzipSync}=require('node:zlib'),{chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),load=name=>JSON.parse(gunzipSync(fs.readFileSync(path.join(__dirname,'fixtures',name+'.json.gz'))));
const wire=load('presentation-v1').responses,recorded=load('desk-v3');

test('the admitted six-act product uses one deterministic clock, preserves sources and handles pause',async()=>{
 const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH||(fs.existsSync('/usr/bin/chromium')?'/usr/bin/chromium':chromium.executablePath())});
 const context=await browser.newContext({viewport:{width:1440,height:900},serviceWorkers:'block'}),page=await context.newPage(),errors=[],writes=[],missing=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',async route=>{
  const request=route.request(),url=new URL(request.url()),key=url.pathname+url.search;
  if(!['GET','HEAD'].includes(request.method())){writes.push(key);return route.abort();}
  if(request.isNavigationRequest())return route.fulfill({contentType:'text/html',body:'<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0"><main id="workspace"></main></body></html>'});
  if(/\/fonts\/[^/]+\.ttf$/.test(url.pathname))return route.fulfill({contentType:'font/ttf',path:path.join(root,'casepath/assets/fonts',path.basename(url.pathname))});
  const id=url.pathname.match(/\/claims\/([^/]+)\/operations$/)?.[1],record=id&&recorded.cases.find(row=>row.id===id);
  if(record)return route.fulfill({contentType:'application/x-ndjson',body:record.trace});
  if(wire[key])return route.fulfill({contentType:'application/json',body:JSON.stringify(wire[key])});
  missing.push(key);return route.fulfill({status:404,contentType:'application/json',body:JSON.stringify({detail:'No recorded fixture for '+key})});
 });
 try{
  await page.goto('http://localhost:41999/#autonomous/demonstration');
  await page.addStyleTag({path:path.join(root,'casepath/assets/autonomous-workspace-v1.css')});
  for(const asset of ['autonomous-language-v1.js','autonomous-presentation-v1.js','autonomous-workspace-v1.js'])await page.addScriptTag({path:path.join(root,'casepath/assets',asset)});
  await page.evaluate(()=>{window.product=CasePathAutonomous.mount(document.querySelector('#workspace'),{fetch:window.fetch.bind(window)});});
  await page.waitForFunction(()=>window.CasepathPresentation?.active,{},{timeout:45000});await page.evaluate(()=>document.fonts.ready);
  assert.deepEqual(errors,[]);assert.equal(await page.locator('[data-au-ns-start]').count(),1);assert.equal(await page.evaluate(()=>CasepathPresentation.active.time),0);
  await page.locator('[data-au-ns-start]').click();await page.waitForTimeout(50);assert.equal(await page.locator('[data-au-demo-stop]').count(),1);
  await page.locator('[data-au-demo-stop]').click();const at=await page.evaluate(()=>CasepathPresentation.active.time);await page.waitForTimeout(60);assert.equal(await page.evaluate(()=>CasepathPresentation.active.time),at);
  await page.locator('[data-au-demo-resume]').click();await page.waitForTimeout(60);assert.ok(await page.evaluate(()=>CasepathPresentation.active.time)>at);
  const orientation=await page.evaluate(()=>{const a=CasepathPresentation.active;a.advanceTo(0);return {purpose:document.querySelector('[data-au-ns-purpose]').textContent,transport:document.querySelector('.au-executive-transport').textContent};});
  assert.match(orientation.purpose,/From customer documents/);assert.match(orientation.purpose,/You make the decision/);assert.match(orientation.transport,/Recorded replay/);
  const controls=await page.evaluate(()=>{const a=CasepathPresentation.active,footer=document.querySelector('.au-executive-transport'),button=footer.querySelector('[data-au-demo-stop]');const mutations=[];const observer=new MutationObserver(rows=>mutations.push(...rows));observer.observe(footer,{childList:true,subtree:true,attributes:true});for(const beat of a.manifest.beats)a.advanceTo(beat.start);const pending=observer.takeRecords();observer.disconnect();return {connected:footer.isConnected,sameButton:button===document.querySelector('.au-executive-transport [data-au-demo-stop]'),labelChanges:[...mutations,...pending].filter(row=>row.target===button).length};});
  assert.equal(controls.connected,true);assert.equal(controls.sameButton,true);assert.equal(controls.labelChanges,0,'unchanged Pause control does not repaint on every frame');
  const proof=await page.evaluate(()=>{
   const active=CasepathPresentation.active,manifest=active.manifest,failures=[];
   for(const beat of manifest.beats){for(const at of [beat.start,beat.start+beat.duration/2,beat.end-.001]){active.advanceTo(at);const host=document.querySelector('[data-au-view]');if(document.getAnimations().length)failures.push('native motion');if(Number(host.dataset.auPresentationTime)!==at)failures.push('wrong clock');if(beat.act==='process'&&host.querySelector('[data-au-film-speed]').textContent!=='4×')failures.push('missing pace');if(host.querySelector('[data-au-demo-stop]')?.textContent!=='Pause'||host.querySelector('[data-au-demo-resume]'))failures.push('capture transport');if(['answer','cases'].includes(beat.view)&&!host.querySelector('[data-au-operation-skip]').hidden)failures.push('skip on answer/cases');if([...host.querySelectorAll('[data-au-desk-watch]')].some(el=>!el.hidden&&!el.closest('.au-executive-transition')))failures.push('watch during playback');if(beat.act==='cases'&&beat.phase!=='act-transition'&&host.querySelector('.au-ns-sources'))failures.push('case sources beside roster');}}
   active.seek(manifest.beats.find(b=>b.phase==='fact-rest').start);
   const fact=document.querySelector('[data-au-ns-fact]'),citation=JSON.parse(fact.dataset.auCitation);
   return {manifest,failures,citation,factOperation:fact.dataset.auNsFact,animations:document.getAnimations().length};
  });
  for(const beat of proof.manifest.beats){if(beat.operation){const bound=recorded.cases.find(c=>c.id===beat.claim)?.trace.trim().split('\n').map(JSON.parse).find(row=>row.id===beat.operation);assert.ok(bound,'recorded operation '+beat.operation);assert.equal(bound.seq,beat.seq);}}
  assert.deepEqual(proof.failures,[]);assert.deepEqual(proof.manifest.acts.map(a=>a.id),['customer','reading','process','decision','learning','cases']);
  const intake=await page.evaluate(()=>{const a=CasepathPresentation.active;a.advanceTo(a.manifest.beats.find(b=>b.phase==='customer-passage-rest').end-1);return {source:document.querySelector('[data-au-customer-source]').dataset.auCustomerSource,quote:document.querySelector('[data-au-ns-quote]').textContent,fields:[...document.querySelectorAll('.au-ns-source-fields dt')].map(el=>el.textContent)};});
  const intakeState=recorded.cases[7].envelope.state;assert.equal(intake.source,intakeState.acquired_sources.find(s=>s.role==='customer_message').artifact_id);assert.equal(intake.quote,require('../casepath/assets/autonomous-workspace-v1.js').deskRequest(intakeState.message));assert.deepEqual(intake.fields,['From','To','Date']);
  const w10=await page.evaluate(()=>{
   const a=CasepathPresentation.active,m=a.manifest,checks=[];
   for(const beat of m.beats.filter(b=>['cursor','customer-cursor'].includes(b.phase))){a.advanceTo(beat.end-.001);const mark=document.querySelector('[data-au-ns-quote]'),pane=document.querySelector('.au-ns-source-scroll'),r=mark.getBoundingClientRect(),q=pane.getBoundingClientRect();checks.push({center:Math.abs((r.top+r.bottom-q.top-q.bottom)/2),font:getComputedStyle(mark).fontSize,line:getComputedStyle(mark).lineHeight,context:getComputedStyle(document.querySelector('.au-ns-source-context')).opacity,badge:document.querySelector('.au-executive-cursor .au-ns-role-badge')?.childElementCount,highlight:document.querySelector('.au-executive-ink').style.opacity});}
   const counts=[];for(const beat of m.beats.filter(b=>b.phase==='memory-landed')){a.advanceTo(beat.end-1);counts.push(+document.querySelector('[data-au-memory-count]').textContent);}
   a.advanceTo(m.beats.find(b=>b.phase==='memory-notice-rest').end-1);
   const mapping=[...document.querySelectorAll('[data-au-memory-target]')].map(el=>({type:el.dataset.auMemoryTarget,node:el.dataset.auMemoryStep,request:el.dataset.auMemoryRequest,landed:el.dataset.landed}));
   a.advanceTo(m.beats.find(b=>b.phase==='fact-rest').end-1);const connector=document.querySelector('.au-ns-fact-connector');
   return {checks,counts,mapping,connector:connector.dataset.auNsConnectorNode,path:connector.querySelector('path').getAttribute('d'),selection:m.showcase};
  });
  assert.equal(w10.selection.claimId,recorded.cases[7].id);assert.deepEqual(w10.counts,[1,2,3]);assert.equal(w10.mapping.length,3);assert.ok(w10.mapping.every(row=>row.landed==='true'&&row.request));
  assert.ok(w10.checks.every(row=>row.center<2&&row.font==='17px'&&row.line==='25.5px'&&row.context==='0.45'&&row.badge===1&&row.highlight==='0'),JSON.stringify(w10.checks));assert.ok(w10.connector);assert.match(w10.path,/H.*V.*H.*V/);
  if(process.env.CASEPATH_W10_SHOTS){for(const [name,phase]of [['reading','fact-rest'],['completed','chain-rest'],['learning','memory-notice-rest']]){await page.evaluate(phase=>{const a=CasepathPresentation.active,b=a.manifest.beats.find(b=>b.phase===phase);a.advanceTo(b.end-1);},phase);await page.screenshot({path:process.env.CASEPATH_W10_SHOTS+'/'+name+'.png'});}}
  const {auditPresentation}=await import('../design-plans/w9-20261021/audit_presentation.mjs');
  const geometry=[];
  for(const beat of proof.manifest.beats.filter(b=>b.phase!=='act-transition')){await page.evaluate(at=>CasepathPresentation.active.advanceTo(at),beat.start+beat.duration/2);const hits=await page.evaluate(auditPresentation);if(hits.length)geometry.push({phase:beat.phase,operation:beat.operation,hits});}
  if(process.env.CASEPATH_W10_SHOTS)fs.writeFileSync(process.env.CASEPATH_W10_SHOTS+'/geometry.json',JSON.stringify(geometry,null,2));
  assert.deepEqual(geometry,[],'all beat midpoints have no unintended content overlaps');
  const ending=await page.evaluate(()=>{const a=CasepathPresentation.active;a.advanceTo(a.manifest.duration-1);const word=document.querySelector('.au-executive-wordmark').getBoundingClientRect(),list=document.querySelector('.au-claim-list').getBoundingClientRect(),footer=document.querySelector('.au-executive-transport').getBoundingClientRect();return {above:word.top-list.bottom,below:footer.top-word.bottom};});
  assert.ok(ending.above>=32&&ending.below>=32,JSON.stringify(ending));

  const completions=Object.fromEntries(recorded.cases.flatMap(c=>c.trace.trim().split('\n').map(JSON.parse).filter(o=>o.kind==='step.complete').map(o=>[o.id,o.source])));
  const bindings=await page.evaluate(completions=>{
   const active=CasepathPresentation.active,m=active.manifest,failures=[];let checked=0;
   const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
   for(let n=0;n<Math.ceil(m.duration*60/1000);n++){
    const at=n*1000/60,beat=m.beats.find(b=>at>=b.start&&at<b.end);if(beat.act!=='process')continue;
    active.advanceTo(at);checked++;
    const paper=document.querySelector('[data-au-ns-paper]'),pin=JSON.parse(paper.querySelector('[data-au-citation]').dataset.auCitation),mark=paper.querySelector('[data-au-ns-quote]');
    const facts=[...document.querySelectorAll('[data-au-ns-fact]')].filter(e=>!e.closest('.au-executive-transition')&&+getComputedStyle(e).opacity>0).map(e=>JSON.parse(e.dataset.auCitation));
    if(!same(pin,facts.at(-1)||completions[beat.operation]))failures.push({n,reason:'source is not latest visible fact or completion'});
    if(mark.textContent!==pin.quote||+mark.dataset.start!==pin.start_char||+mark.dataset.end!==pin.end_char)failures.push({n,reason:'wrong highlighted passage'});
    if(['source-swap','camera-in','cursor'].includes(beat.phase)&&+paper.querySelector('.au-executive-ink').style.opacity!==0)failures.push({n,reason:'highlight before cursor'});
   }
   active.advanceTo(m.beats.find(b=>b.phase==='answer-rest'&&b.act==='decision').start);
   const tests=[...document.querySelectorAll('[data-au-desk-answer] > .au-desk-tests > li')].map(e=>({step:+e.dataset.auLegalStep,label:e.querySelector('.au-executive-step-label')?.textContent,ring:e.querySelector('.au-executive-step')?.getBoundingClientRect().width}));
   const stepContext=document.querySelector('.au-executive-test-context').textContent;
   active.advanceTo(m.beats.find(b=>b.phase==='source-check-rest').start);const sourceCheck={text:document.querySelector('.au-ns-role-purpose').textContent,role:document.querySelector('[data-au-ns]').dataset.auNsRoleActive,passages:document.querySelectorAll('[data-au-ns-verified]').length};
   active.advanceTo(m.beats.find(b=>b.phase==='draft-rest').start);const draft=document.querySelector('[data-au-recorded-draft]').textContent;
   active.advanceTo(m.beats.find(b=>b.phase==='law-rest').start);const law=document.querySelector('[data-au-ns-law-source]').textContent,publisher=document.querySelector('[data-au-law-article]').href;
   active.advanceTo(m.beats.find(b=>b.phase==='answer-rest'&&b.act==='learning').end-1);const laterResult=(document.querySelector('.au-ns-initial-date')?.textContent||'')+document.querySelector('.au-desk-lead').textContent;
   const later=m.beats.find(b=>b.phase==='later-case-rest');active.advanceTo(later.start+899);
   const railOnly=getComputedStyle(document.querySelector('.au-ns-completed-canvas')).opacity==='0',label=document.querySelector('.au-executive-later').textContent,title=document.querySelector('[data-au-claim-title]').textContent;
   active.advanceTo(m.beats.find(b=>b.phase==='memory-landed').start);
   return {failures,checked,tests,stepContext,sourceCheck,draft,law,publisher,laterResult,laterDuration:later.duration,railOnly,label,title,sourceHeading:document.querySelector('.au-ns-memory-source h3').textContent,border:getComputedStyle(document.querySelector('.au-ns-memory-source blockquote')).borderTop};
  },completions);
  assert.deepEqual(bindings.failures,[]);assert.ok(bindings.checked>0);
  assert.ok(proof.manifest.duration<90000);assert.match(bindings.draft,/Not sent — you decide/);assert.ok(bindings.draft.includes(recorded.cases[7].envelope.state.outcome.request_draft.body));assert.match(bindings.law,/publisher: Fedlex/);assert.match(bindings.publisher,/^https:\/\/www.fedlex.admin.ch\//);assert.ok(bindings.laterResult.includes(recorded.cases[8].envelope.state.outcome.summary.split('. ')[0]+'.'));
  assert.deepEqual(bindings.tests.map(t=>t.step),[2,2,2,3,3]);assert.ok(bindings.tests.every(t=>t.ring===20&&t.label===String(t.step)));
  assert.match(bindings.stepContext,/3 process steps · 5 legal tests/);assert.match(bindings.stepContext,/Numbers link each legal test to its process step/);
  assert.equal(bindings.sourceCheck.role,'checker');assert.ok(bindings.sourceCheck.passages>0);assert.match(bindings.sourceCheck.text,/matches quoted passages to received files/);
  assert.ok(proof.manifest.acts.find(a=>a.id==='customer').end-proof.manifest.acts.find(a=>a.id==='customer').start<8000,'intake stops before repeated document reading');
  assert.equal(bindings.laterDuration,900);assert.equal(bindings.railOnly,true);assert.equal(bindings.label,'Later case');assert.ok(bindings.title.length);assert.equal(bindings.sourceHeading,'Later case source');assert.equal(bindings.border,'1px solid rgb(46, 107, 53)');
  assert.ok(proof.manifest.beats.filter(b=>b.phase==='source-swap').every(b=>b.duration===250));
  await page.evaluate(at=>CasepathPresentation.active.seek(at),proof.manifest.beats.find(b=>b.phase==='fact-rest').start);
  const op=recorded.cases[7].trace.trim().split('\n').map(JSON.parse).find(row=>row.id===proof.factOperation);assert.deepEqual(proof.citation,op.source);
  await page.locator('[data-au-ns-fact]').first().click();await page.locator('dialog[open]').waitFor();assert.equal(await page.evaluate(()=>CasepathPresentation.active.paused),true);
  await page.keyboard.press('Escape');await page.locator('dialog[open]').waitFor({state:'detached'});await page.locator('[data-au-demo-resume]').click();
  await page.evaluate(()=>product.showWork());assert.equal(await page.evaluate(()=>Boolean(CasepathPresentation.active)),false);assert.equal(await page.locator('html[data-casepath-presentation]').count(),0);await page.evaluate(()=>product.destroy());
  assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);assert.deepEqual(missing,[],'all reads use frozen fixtures');
 }catch(error){error.message+='\nMissing fixture reads: '+JSON.stringify(missing)+'\nPage errors: '+JSON.stringify(errors)+'\nUI: '+(await page.locator('body').innerText()).slice(-1000);throw error;}
 finally{for(const close of [()=>page.close(),()=>context.close(),()=>browser.close()]){let timer;await Promise.race([close(),new Promise(resolve=>{timer=setTimeout(resolve,10000);})]);clearTimeout(timer);}}
});

test('a slow cold read keeps the north-star frame on landing and on opening a recorded case',async()=>{
 const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH||(fs.existsSync('/usr/bin/chromium')?'/usr/bin/chromium':chromium.executablePath())});
 const context=await browser.newContext({viewport:{width:1440,height:900},serviceWorkers:'block'}),page=await context.newPage(),errors=[],writes=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',async route=>{
  const request=route.request(),url=new URL(request.url()),key=url.pathname+url.search;
  if(!['GET','HEAD'].includes(request.method())){writes.push(key);return route.abort();}
  if(request.isNavigationRequest())return route.fulfill({contentType:'text/html',body:'<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0"><main id="workspace"></main></body></html>'});
  if(/\/fonts\/[^/]+\.ttf$/.test(url.pathname))return route.fulfill({contentType:'font/ttf',path:path.join(root,'casepath/assets/fonts',path.basename(url.pathname))});
  const id=url.pathname.match(/\/claims\/([^/]+)\/operations$/)?.[1],record=id&&recorded.cases.find(row=>row.id===id);
  // A cold hosted read: the recorded operations arrive well after the verified head.
  if(record){await new Promise(resolve=>setTimeout(resolve,1500));return route.fulfill({contentType:'application/x-ndjson',body:record.trace});}
  if(wire[key])return route.fulfill({contentType:'application/json',body:JSON.stringify(wire[key])});
  return route.fulfill({status:404,contentType:'application/json',body:JSON.stringify({detail:'No recorded fixture for '+key})});
 });
 const views=()=>page.evaluate(()=>window.views);
 try{
  await page.goto('http://localhost:41999/#autonomous/demonstration');
  await page.addStyleTag({path:path.join(root,'casepath/assets/autonomous-workspace-v1.css')});
  for(const asset of ['autonomous-language-v1.js','autonomous-presentation-v1.js','autonomous-workspace-v1.js'])await page.addScriptTag({path:path.join(root,'casepath/assets',asset)});
  await page.evaluate(()=>{
   // Every distinct case frame the visitor sees, in order; the text navigation must stay hidden on case views.
   window.views=[];
   const kind=()=>{const ns=document.querySelector('[data-au-ns]'),other=document.querySelector('[data-au-agent-desk]:not([data-au-ns]),[data-au-desk-loading]:not([data-au-ns]),.au-quiet-claim');
    if(ns&&document.querySelector('.au-nav')?.getClientRects().length)return 'north-star with text navigation';
    if(document.querySelector('[data-au-ns-state="opening"]'))window.sawOpening=true;
    return ns?'north-star':other?'interim':'none';};
   new MutationObserver(()=>{const k=kind();if(window.views.at(-1)!==k)window.views.push(k);}).observe(document.body,{childList:true,subtree:true,attributes:true});
   window.product=CasePathAutonomous.mount(document.querySelector('#workspace'),{fetch:window.fetch.bind(window)});
  });
  await page.waitForFunction(()=>window.CasepathPresentation?.active,{},{timeout:45000});
  assert.deepEqual((await views()).filter(k=>k!=='none'),['north-star'],'landing frames');assert.equal(await page.evaluate(()=>window.sawOpening),true,'the opening frame covered the cold read');
  assert.equal(await page.locator('[data-au-ns-start]').count(),1);
  await page.evaluate(()=>{window.views=[];window.sawOpening=false;location.hash='#autonomous/claim/clm_4a07dbbbd859a3ce';});
  await page.locator('[data-au-ns-completed]').waitFor({timeout:45000});
  assert.deepEqual((await views()).filter(k=>k!=='none'),['north-star'],'recorded case frames');assert.equal(await page.evaluate(()=>window.sawOpening),true,'the opening frame covered the recorded case read');
  assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);
 }catch(error){error.message+='\nViews: '+JSON.stringify(await views().catch(()=>null))+'\nPage errors: '+JSON.stringify(errors)+'\nUI: '+(await page.locator('body').innerText()).slice(0,600);throw error;}
 finally{for(const close of [()=>page.close(),()=>context.close(),()=>browser.close()]){let timer;await Promise.race([close(),new Promise(resolve=>{timer=setTimeout(resolve,10000);})]);clearTimeout(timer);}}
});
