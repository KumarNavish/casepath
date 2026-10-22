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
  const proof=await page.evaluate(()=>{
   const active=CasepathPresentation.active,manifest=active.manifest,failures=[];
   for(const beat of manifest.beats){for(const at of [beat.start,beat.start+beat.duration/2,beat.end-.001]){active.advanceTo(at);const host=document.querySelector('[data-au-view]');if(document.getAnimations().length)failures.push('native motion');if(Number(host.dataset.auPresentationTime)!==at)failures.push('wrong clock');if(beat.act==='process'&&host.querySelector('[data-au-film-speed]').textContent!=='4×')failures.push('missing pace');if(host.querySelector('[data-au-demo-stop]')?.textContent!=='Pause'||host.querySelector('[data-au-demo-resume]'))failures.push('capture transport');if(['answer','cases'].includes(beat.view)&&!host.querySelector('[data-au-operation-skip]').hidden)failures.push('skip on answer/cases');if([...host.querySelectorAll('[data-au-desk-watch]')].some(el=>!el.hidden&&!el.closest('.au-executive-transition')))failures.push('watch during playback');if(beat.act==='cases'&&beat.phase!=='act-transition'&&host.querySelector('.au-ns-sources'))failures.push('case sources beside roster');}}
   active.seek(manifest.beats.find(b=>b.phase==='fact-rest').start);
   const fact=document.querySelector('[data-au-ns-fact]'),citation=JSON.parse(fact.dataset.auCitation);
   return {manifest,failures,citation,factOperation:fact.dataset.auNsFact,animations:document.getAnimations().length};
  });
  for(const beat of proof.manifest.beats){if(beat.operation){const bound=recorded.cases.find(c=>c.id===beat.claim)?.trace.trim().split('\n').map(JSON.parse).find(row=>row.id===beat.operation);assert.ok(bound,'recorded operation '+beat.operation);assert.equal(bound.seq,beat.seq);}}
  assert.deepEqual(proof.failures,[]);assert.deepEqual(proof.manifest.acts.map(a=>a.id),['customer','reading','process','decision','learning','cases']);
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
   active.advanceTo(m.beats.find(b=>b.phase==='draft-rest').start);
   const tests=[...document.querySelectorAll('[data-au-desk-answer] > .au-desk-tests > li')].map(e=>({step:+e.dataset.auLegalStep,ring:e.querySelector('.au-executive-step')?.getBoundingClientRect().width}));
   const later=m.beats.find(b=>b.phase==='later-case-rest');active.advanceTo(later.start+899);
   const railOnly=getComputedStyle(document.querySelector('.au-ns-completed-canvas')).opacity==='0',label=document.querySelector('.au-executive-later').textContent,title=document.querySelector('[data-au-claim-title]').textContent;
   active.advanceTo(m.beats.find(b=>b.phase==='memory-card-rest').start);
   return {failures,checked,tests,laterDuration:later.duration,railOnly,label,title,sourceHeading:document.querySelector('.au-ns-memory-source h3').textContent,border:getComputedStyle(document.querySelector('.au-ns-memory-source blockquote')).borderTop};
  },completions);
  assert.deepEqual(bindings.failures,[]);assert.ok(bindings.checked>900);
  assert.deepEqual(bindings.tests.map(t=>t.step),[2,3,3,5,5]);assert.ok(bindings.tests.every(t=>t.ring===20));
  assert.equal(bindings.laterDuration,900);assert.equal(bindings.railOnly,true);assert.equal(bindings.label,'Later case');assert.ok(bindings.title.length);assert.equal(bindings.sourceHeading,'Later case source');assert.equal(bindings.border,'1px solid rgb(46, 107, 53)');
  assert.ok(proof.manifest.beats.filter(b=>b.phase==='source-swap').every(b=>b.duration===250));
  await page.evaluate(at=>CasepathPresentation.active.seek(at),proof.manifest.beats.find(b=>b.phase==='fact-rest').start);
  const op=recorded.cases[0].trace.trim().split('\n').map(JSON.parse).find(row=>row.id===proof.factOperation);assert.deepEqual(proof.citation,op.source);
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
