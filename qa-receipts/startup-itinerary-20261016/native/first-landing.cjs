'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict'),{chromium}=require('playwright');
globalThis.crypto||=crypto.webcrypto;
const root='/workspace/casepath-startup-itinerary-js-20261016',out=__dirname,asset=process.env.CASEPATH_JS||path.join(out,'base.js'),css=process.env.CASEPATH_CSS||path.join(root,'casepath/assets/autonomous-workspace-v1.css'),label=process.env.CASEPATH_LABEL||'baseline',ui=require(asset),origin='http://127.0.0.1:4199',id='clm_314f2d309fea25e6',delay=Number(process.env.API_DELAY||5000),assetDelay=Number(process.env.ASSET_DELAY||0);
const sha=b=>crypto.createHash('sha256').update(b).digest('hex'),pause=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const bytes=fs.readFileSync(path.join(root,'casepath/assets/autonomous-recorded-heating-v1.json')),raw=JSON.parse(bytes),descriptor={url:'/packet.json',bytes:bytes.length,sha256:sha(bytes),history_kind:raw.history_kind,deployment_commit:raw.deployment_commit},packet=await ui.checkedRecordedPacket(bytes,descriptor),decoded=await ui.decodeRecordedSession(packet,id),frames=Buffer.from(decoded.operations).toString().trim().split('\n').map(JSON.parse),operationById=new Map(frames.filter(f=>f.type==='operation').map(f=>[f.id,f]));
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try {for(const mode of (process.env.CASEPATH_MODES||'click,direct,early').split(',')){
  const context=await browser.newContext({viewport:{width:1280,height:800},serviceWorkers:'block'}),page=await context.newPage(),requests=[],errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const r=route.request(),u=new URL(r.url());requests.push({url:r.url(),method:r.method(),t:Date.now()});assert.equal(r.method(),'GET');assert.equal(u.origin,origin);
   if(r.isNavigationRequest())return route.fulfill({contentType:'text/html',body:'<!doctype html><html><head><meta charset="utf-8"></head><body><main id="workspace"></main></body></html>'});
   if(u.pathname==='/packet.json'){if(assetDelay||mode==='early')await pause(assetDelay||100);return route.fulfill({contentType:'application/json',body:bytes});}
   await pause(delay);
   if(u.pathname===`/api/claim-loops/v1/autonomous/claims/${id}/replay`) {
    const n=Number(u.searchParams.get('through_seq'));
    return route.fulfill({contentType:'application/json',body:JSON.stringify(n===0?decoded.opening:frames.find(f=>f.type==='checkpoint'&&f.journal_seq===n)||{...decoded.head_snapshot,through_seq:n,replay_only:true})});
   }
   if(u.pathname.endsWith(`/${id}/snapshot`))return route.fulfill({contentType:'application/json',body:JSON.stringify(decoded.head_snapshot)});
   if(u.pathname.endsWith(`/${id}/operations`))return route.fulfill({contentType:'application/x-ndjson',body:Buffer.from(decoded.operations)});
   return route.fulfill({status:404,contentType:'application/json',body:'{"detail":"not part of selected immutable fixture"}'});
  });
  await page.goto(origin+(mode==='direct'?'/#autonomous/demonstration?mode=replay'+(process.env.CASEPATH_OPERATIONS==='recorded'?'&operations=recorded':''):'/#autonomous/cases'));
  await page.addStyleTag({content:fs.readFileSync(css,'utf8')});await page.addScriptTag({content:fs.readFileSync(asset,'utf8')});
  await page.evaluate(({descriptor,mode})=>{
   window.CASEPATH_PUBLIC_READ_ONLY=true;localStorage.clear();sessionStorage.clear();window.requestIdleCallback=undefined;window.cancelIdleCallback=undefined;
   const log=window.__landing={mounted:performance.now(),map:null,firstText:null,flights:[],landings:[],labels:[],samples:[]};
   const animate=Element.prototype.animate;
   Element.prototype.animate=function(keys,opts){const a=animate.call(this,keys,opts);if(this.classList.contains('au-operation-fact-token')){
    const row={operation:this.dataset.auOperationId,kind:this.dataset.auObjectType,text:this.textContent,at:performance.now(),duration:typeof opts==='object'?opts.duration:opts};log.flights.push(row);
    a.finished.then(()=>{row.finished=performance.now();requestAnimationFrame(()=>{const dock=[...document.querySelectorAll('[data-au-stage-fact],[data-au-check-operation]')].find(el=>(el.dataset.auFactOperation||el.dataset.auCheckOperation)===row.operation);if(!dock)return;const r=dock.getBoundingClientRect(),s=getComputedStyle(dock);if(r.width&&r.height&&s.opacity!=='0'&&s.visibility!=='hidden'&&dock.dataset.auDockPhase==='landed'){row.landed=performance.now();row.node=dock.closest('[data-au-stage-step]')?.dataset.auStageStep;log.landings.push(row);}});},()=>{row.cancelled=performance.now();});}return a;};
   const sample=()=>{const host=document.querySelector('[data-au-view]'),graph=document.querySelector('.au-stage-process');if(graph&&log.map===null){const r=graph.getBoundingClientRect();if(r.width&&r.height)log.map=performance.now();}if(log.firstText===null&&document.querySelector('[data-au-stage-fact]'))log.firstText=performance.now();const label=document.querySelector('.au-reference-mode')?.textContent;if(label&&!log.labels.includes(label))log.labels.push(label);};
   new MutationObserver(sample).observe(document,{subtree:true,childList:true,attributes:true});
   window.__controller=window.CasePathAutonomous.mount(document.querySelector('#workspace'),{recordedPacket:descriptor});
   log.ready=window.__controller.recordedPacketReady.then(ready=>{log.packetVerified=performance.now();log.packetAccepted=ready;return ready;});
  },{descriptor,mode});
  if(mode!=='direct'){if(mode==='click')await page.evaluate(()=>window.__landing.ready);await page.locator('[data-au-nav="demonstration"]').first().click();}
  let timeout=null;try{await page.waitForFunction(()=>window.__landing.landings.some(x=>x.kind==='fact'),null,{timeout:12000});}catch(e){timeout=e.message;}
  const receipt=await page.evaluate(()=>({...window.__landing,ready:undefined,status:document.querySelector('.au-global-status')?.textContent,title:document.querySelector('h1')?.textContent,current_operation:document.querySelector('[data-au-view]')?.dataset.auCurrentOperation,read_mode:document.querySelector('[data-au-view]')?.dataset.auOperationRunMode,packetResource:performance.getEntriesByType('resource').filter(x=>x.name.endsWith('/packet.json')).map(x=>({start:x.startTime,headers:x.responseStart,end:x.responseEnd,decoded:x.decodedBodySize}))}));
  await page.screenshot({path:path.join(out,`${label}-${mode}.png`)});await page.evaluate(()=>window.__controller.destroy());await context.close();
  const landed=receipt.landings.find(x=>x.kind==='fact');if(landed){const op=operationById.get(landed.operation);assert.equal(op.kind,'fact.extract');assert.ok(op.source);}
  const result={label,mode,disclosure:'Native isolated Chromium over exact shipped public synthetic heating packet; public-mode renderer, 5s artificial selected API delay, no production requests; default Live-versus-Recorded500ms budget retained.',source_base:'5086624c8a024ba298819e5e27d749efbd0cc7fc',asset_sha256:sha(fs.readFileSync(asset)),css_sha256:sha(fs.readFileSync(css)),packet_sha256:sha(bytes),head:decoded.head,api_delay_ms:delay,asset_delay_ms:assetDelay|| (mode==='early'?100:0),metrics:{first_visible_map_ms:receipt.map-receipt.mounted,first_text_after_map_ms:receipt.firstText===null?null:receipt.firstText-receipt.map,first_actual_landing_after_map_ms:landed?landed.landed-receipt.map:null},receipt,requests,errors,timeout};
  fs.writeFileSync(path.join(out,`${label}-${mode}.json`),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({label,mode,...result.metrics,timeout,errors}));
 }}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
