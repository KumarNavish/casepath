'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {gunzipSync}=require('node:zlib'),{chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),load=name=>JSON.parse(gunzipSync(fs.readFileSync(path.join(__dirname,'fixtures',name+'.json.gz'))));
// The photo scene reads one recorded customer photo and the service's reading of it.
const photo=load('photo-reading-v1'),wire={...load('presentation-v1').responses,...photo.responses},recorded=load('desk-v3');
const original=(route,key)=>{const file=photo.binary[key];return file&&route.fulfill({contentType:file.media_type,headers:{'x-content-sha256':file.sha256},body:Buffer.from(file.base64,'base64')});};

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
  if(photo.binary[key])return original(route,key);
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
  assert.match(orientation.purpose,/From a customer’s documents/);assert.match(orientation.purpose,/A person decides/);assert.match(orientation.transport,/Example case · made-up customers and cases/);
  const documentary=await page.evaluate(()=>{
   const a=CasepathPresentation.active,m=a.manifest,failures=[],sentences=[];
   for(const cue of m.guidance){const previous=sentences.at(-1);if(previous?.id===cue.id)previous.end=cue.end;else sentences.push({...cue});}
   // Live work between captions carries no card; only shown captions need reading time.
   for(const cue of sentences)if(cue.card!==false&&cue.end-cue.start<2000)failures.push({reason:'caption too brief',cue});
   for(const beat of m.beats.filter(b=>!b.phase.endsWith('transition'))){
    a.advanceTo(beat.start+Math.min(beat.duration-1,Math.max(450,beat.duration*.75)));
    const guide=document.querySelector('.au-documentary-guide'),scene={top:document.querySelector('.au-identity-header').getBoundingClientRect().bottom,bottom:document.querySelector('.au-executive-transport').getBoundingClientRect().top},card=guide.querySelector('.au-doc-card'),copy=guide.querySelector('[data-au-guide-headline]'),focus=guide.querySelector('.au-doc-focus').getBoundingClientRect(),shown=+getComputedStyle(card).opacity>.05,lit=+getComputedStyle(guide.querySelector('.au-doc-focus-layer')).opacity>.05;
    if(document.querySelectorAll('.au-documentary-guide').length!==1)failures.push({reason:'multiple guides',beat:beat.index});
    if(guide.dataset.auGuideSpotlight==='true'&&guide.dataset.auGuideResolved!=='true')failures.push({reason:'unresolved focus',beat:beat.index,target:guide.dataset.auGuideTarget});
    if(shown){const box=card.getBoundingClientRect();if(copy.scrollWidth>copy.clientWidth+1||box.top<scene.top||box.bottom>scene.bottom||box.left<0||box.right>innerWidth)failures.push({reason:'caption clipped or outside the scene',beat:beat.index});
     // A caption sits beside its spotlight and never covers it.
     if(lit&&Math.min(box.right,focus.right)-Math.max(box.left,focus.left)>2&&Math.min(box.bottom,focus.bottom)-Math.max(box.top,focus.top)>2)failures.push({reason:'caption covers its spotlight',beat:beat.index,target:guide.dataset.auGuideTarget});}
    if(lit&&(guide.dataset.auGuideVisible!=='true'||focus.width<=4||focus.height<=4||focus.top<scene.top-1||focus.bottom>scene.bottom+1))failures.push({reason:'focus invisible or outside the scene',beat:beat.index});
   }
   const openBeat=m.beats.find(b=>b.act==='decision'&&b.phase==='answer-rest');a.advanceTo(openBeat.start+4500);const open=document.querySelector('.au-desk-open').getBoundingClientRect(),rail=document.querySelector('.au-identity-header').getBoundingClientRect();if(open.top<rail.bottom||open.bottom>innerHeight-36)failures.push({reason:'unresolved questions clipped',top:open.top,bottom:open.bottom});
   for(const beat of m.beats.filter(b=>['chain','legal-test','memory-transfer'].includes(b.phase))){const at=beat.start+20,index=m.guidance.findIndex(row=>at>=row.start&&at<row.end);if(index<1||m.guidance[index-1].id!==m.guidance[index].id||m.guidance[index].mode!=='hold')continue;a.advanceTo(at);const guide=document.querySelector('.au-documentary-guide');if(guide.dataset.auGuideSpotlight==='true'&&Number(getComputedStyle(guide.querySelector('.au-doc-focus-layer')).opacity)<.9)failures.push({reason:'attention wash pulses between related targets',beat:beat.index});}
   const legal=m.beats.filter(b=>b.phase==='legal-test-rest');
   for(const beat of legal){a.advanceTo(beat.end-1);const rows=[...document.querySelectorAll('[data-au-desk-answer] > .au-desk-tests > li')],current=rows.find(el=>el.dataset.auDeskPredicate===beat.predicate),guide=document.querySelector('.au-documentary-guide');if(!current||getComputedStyle(current).opacity!=='1')failures.push({reason:'wrong legal identity',beat:beat.index});if(beat.predicate_status==='failed'&&(beat.duration!==3400||guide.dataset.auGuideCue!=='unmet'||guide.dataset.auGuideTargetId!==beat.predicate))failures.push({reason:'failed requirement hold',beat:beat.index});}
   const ringBeat=m.beats.find(b=>b.phase==='passage-rest'&&b.act==='reading'&&b.duration>=1600);
   a.advanceTo(ringBeat.start+500);const ring=document.querySelector('.au-ns-building-ring'),number=document.querySelector('.au-ns-current-number'),before=ring.style.transform;
   a.advanceTo(ringBeat.start+1100);const after=document.querySelector('.au-ns-building-ring').style.transform;
   const snapshot=()=>{const guide=document.querySelector('.au-documentary-guide');return JSON.stringify({cue:guide.dataset.auGuideCue,target:guide.dataset.auGuideTargetId,box:guide.querySelector('.au-doc-focus').style.cssText,ring:document.querySelector('.au-ns-building-ring')?.style.transform});};
   const direct=snapshot();a.advanceTo(m.duration-1);a.advanceTo(ringBeat.start+1100);if(snapshot()!==direct)failures.push({reason:'guide or ring differs after backward seek'});
   a.seek(ringBeat.start+1100);
   return {failures,sentences:sentences.length,ringBefore:before,ringAfter:after,numberTransform:number.style.transform,ringCount:document.querySelectorAll('.au-ns-building-ring').length,at:a.time,paused:a.paused};
  });
  assert.deepEqual(documentary.failures,[]);assert.ok(documentary.sentences>=15);assert.notEqual(documentary.ringBefore,documentary.ringAfter);assert.equal(documentary.numberTransform,'');assert.equal(documentary.ringCount,1);assert.equal(documentary.paused,true);
  await page.waitForTimeout(60);assert.deepEqual(await page.evaluate(()=>({at:CasepathPresentation.active.time,ring:document.querySelector('.au-ns-building-ring').style.transform})),{at:documentary.at,ring:documentary.ringAfter});
  await page.evaluate(()=>CasepathPresentation.active.resume());await page.waitForTimeout(100);assert.notEqual(await page.evaluate(()=>document.querySelector('.au-ns-building-ring').style.transform),documentary.ringAfter,'the actual live frame clock advances the ring');await page.evaluate(()=>CasepathPresentation.active.pause());
  await page.emulateMedia({reducedMotion:'reduce'});
  const reducedRing=await page.evaluate(at=>{const a=CasepathPresentation.active;a.advanceTo(at);const before=document.querySelector('.au-ns-building-ring').style.transform;a.advanceTo(at+300);return [before,document.querySelector('.au-ns-building-ring').style.transform];},documentary.at);
  assert.deepEqual(reducedRing,['rotate(0deg)','rotate(0deg)']);await page.emulateMedia({reducedMotion:'no-preference'});
  const teachingState=recorded.cases[7].envelope.state;
  const teaching=await page.evaluate(({draftBody})=>{
   const a=CasepathPresentation.active,m=a.manifest,failures=[];
   const inside=(box,outer)=>box.width>4&&box.height>4&&box.left>=outer.left-1&&box.right<=outer.right+1&&box.top>=outer.top-1&&box.bottom<=outer.bottom+1;
   const guide=()=>document.querySelector('.au-documentary-guide'),focus=()=>guide().querySelector('.au-doc-focus').getBoundingClientRect();
   const draftBeat=m.beats.find(b=>b.act==='decision'&&b.phase==='draft-rest');
   a.advanceTo(draftBeat.start+1500);
   const draft=document.querySelector('[data-au-recorded-draft]'),body=draft?.querySelector('pre'),bodyBox=focus(),bodyHeadline=guide().querySelector('[data-au-guide-headline]').textContent;
   if(body?.textContent!==draftBody)failures.push('recorded draft text changed');
   if(guide().dataset.auGuideTarget!=='draft-body'||guide().dataset.auGuideVisible!=='true'||!draft||!inside(draft.getBoundingClientRect(),bodyBox))failures.push('draft artifact is not focused before review boundary');
   if(body&&!getComputedStyle(body).fontFamily.includes('Mulish'))failures.push('draft typography is not presentation font');
   a.advanceTo(draftBeat.start+4500);
   const status=document.querySelector('[data-au-draft-status]');
   if(guide().dataset.auGuideTarget!=='draft'||guide().dataset.auGuideVisible!=='true'||!status||!inside(status.getBoundingClientRect(),focus()))failures.push('draft focus does not hand off to human review');
   if(guide().querySelector('[data-au-guide-headline]').textContent!==bodyHeadline)failures.push('draft caption changes during target handoff');
   if(document.querySelector('[data-au-recorded-draft] pre')?.textContent!==draftBody)failures.push('draft text changed at review boundary');
   return {failures,duration:m.duration};
  },{draftBody:teachingState.outcome.request_draft.body});
  assert.deepEqual(teaching.failures,[]);assert.equal(teaching.duration,163180);
  const controls=await page.evaluate(()=>{const a=CasepathPresentation.active,footer=document.querySelector('.au-executive-transport'),button=footer.querySelector('[data-au-demo-stop]');const mutations=[];const observer=new MutationObserver(rows=>mutations.push(...rows));observer.observe(footer,{childList:true,subtree:true,attributes:true});for(const beat of a.manifest.beats)a.advanceTo(beat.start);const pending=observer.takeRecords();observer.disconnect();return {connected:footer.isConnected,sameButton:button===document.querySelector('.au-executive-transport [data-au-demo-stop]'),labelChanges:[...mutations,...pending].filter(row=>row.target===button).length};});
  assert.equal(controls.connected,true);assert.equal(controls.sameButton,true);assert.equal(controls.labelChanges,0,'unchanged Pause control does not repaint on every frame');
  const proof=await page.evaluate(()=>{
   const active=CasepathPresentation.active,manifest=active.manifest,failures=[];
   for(const beat of manifest.beats){for(const at of [beat.start,beat.start+beat.duration/2,beat.end-.001]){active.advanceTo(at);const host=document.querySelector('[data-au-view]');if(document.getAnimations().length)failures.push('native motion');if(Number(host.dataset.auPresentationTime)!==at)failures.push('wrong clock');if(beat.act==='process'&&host.querySelector('[data-au-film-speed]').textContent!=='Sped up')failures.push('missing pace');if(host.querySelector('[data-au-demo-stop]')?.textContent!=='Pause'||host.querySelector('[data-au-demo-resume]'))failures.push('capture transport');if((['answer','cases'].includes(beat.view)||['library','cases'].includes(beat.act))&&!host.querySelector('[data-au-operation-skip]').hidden)failures.push('skip on answer, library or cases');if([...host.querySelectorAll('[data-au-desk-watch]')].some(el=>!el.hidden&&!el.closest('.au-executive-transition')))failures.push('watch during playback');if(beat.act==='cases'&&beat.phase!=='act-transition'&&host.querySelector('.au-ns-sources'))failures.push('case sources beside roster');}}
   active.seek(manifest.beats.find(b=>b.phase==='fact-rest').start);
   const fact=document.querySelector('[data-au-ns-fact]'),citation=JSON.parse(fact.dataset.auCitation);
   return {manifest,failures,citation,factOperation:fact.dataset.auNsFact,animations:document.getAnimations().length};
  });
  for(const beat of proof.manifest.beats){if(beat.operation){const bound=recorded.cases.find(c=>c.id===beat.claim)?.trace.trim().split('\n').map(JSON.parse).find(row=>row.id===beat.operation);assert.ok(bound,'recorded operation '+beat.operation);assert.equal(bound.seq,beat.seq);}}
  assert.deepEqual(proof.failures,[]);assert.deepEqual(proof.manifest.acts.map(a=>a.id),['customer','plan','reading','process','decision','photo','learning','library','cases']);
  const continuity=await page.evaluate(()=>{
   const a=CasepathPresentation.active,failures=[];
   const visible=()=>{const outer=document.querySelector('[data-au-ns],.au-executive-cases'),inner=document.querySelector('.au-ns-canvas,.au-ns-completed-canvas');return Number(getComputedStyle(outer).opacity)*(inner?Number(getComputedStyle(inner).opacity):1);};
   for(const b of a.manifest.beats.filter(b=>['act-transition','scene-transition'].includes(b.phase))){a.advanceTo(b.end-.001);const before=visible();a.advanceTo(b.end);const after=visible();if(before<.99||after<.99||Math.abs(before-after)>.01)failures.push({act:b.act,next:b.nextPhase,before,after});}
   return failures;
  });assert.deepEqual(continuity,[],'incoming content stays visible after every scene transition');
  const stable=await page.evaluate(()=>{
   const a=CasepathPresentation.active,m=a.manifest,cursor=m.beats.find(b=>b.phase==='cursor'&&b.act==='reading'),highlight=m.beats.find(b=>b.phase==='highlight'&&b.operation===cursor.operation);
   a.advanceTo(cursor.start+cursor.duration/2);const selectors=['[data-au-ns-paper]','[data-au-ns-plan]','.au-ns-spine'],before=selectors.map(s=>document.querySelector(s));
   a.advanceTo(highlight.start+highlight.duration/2);return selectors.map((s,i)=>({selector:s,present:Boolean(before[i]),same:before[i]===document.querySelector(s),connected:before[i]?.isConnected}));
  });assert.ok(stable.every(r=>r.present&&r.same&&r.connected),JSON.stringify(stable));
  const recordedOrder=recorded.cases[7].trace.trim().split('\n').map(JSON.parse).filter(o=>o.kind==='step.complete'&&o.result?.status==='completed').map(o=>o.object.id);
  // Recorded document checks may serve a later question before an earlier one is answered.
  const documentChecks=recorded.cases[7].trace.trim().split('\n').map(JSON.parse).filter(o=>o.kind==='document.check').map(o=>o.id);
  const acceptance=await page.evaluate(([order,documentChecks])=>{
   const a=CasepathPresentation.active,failures=[];let previous=0;
   for(const beat of a.manifest.beats.filter(b=>['reading','process'].includes(b.act)&&!b.phase.endsWith('transition'))){
    a.advanceTo(beat.end-.001);const nodes=[...document.querySelectorAll('[data-au-ns-node]')].filter(el=>!el.closest('.au-executive-transition')),done=nodes.filter(el=>el.dataset.state==='done').map(el=>el.dataset.auNsNode),building=nodes.find(el=>el.dataset.state==='building')?.dataset.auNsNode;
    if(done.length<previous||JSON.stringify(done)!==JSON.stringify(order.slice(0,done.length))||building&&!documentChecks.includes(beat.operation)&&building!==order[done.length])failures.push({beat:beat.index,done,building,previous});
    previous=done.length;
   }return failures;
  },[recordedOrder,documentChecks]);assert.deepEqual(acceptance,[],'accepted steps never disappear and active nodes follow process order');
  const deterministic=await page.evaluate(()=>{
   const a=CasepathPresentation.active,failures=[];
   const snapshot=()=>{const selectors=['[data-au-ns]','.au-ns-canvas','.au-ns-completed-canvas','[data-au-ns-paper]','[data-au-ns-plan]','[data-au-ns-procedure]','[data-au-photo-frame]','[data-au-photo-findings]','[data-au-ns-shelf]','[data-au-map]','.au-cinema-finale'];return JSON.stringify({styles:selectors.map(s=>{const el=document.querySelector(s);return el?[s,getComputedStyle(el).opacity,el.style.transform]:[s,null];}),nodes:[...document.querySelectorAll('[data-au-ns-node]')].filter(e=>!e.closest('.au-executive-transition')).map(e=>[e.dataset.auNsNode,e.dataset.state]),source:document.querySelector('[data-au-ns-quote]')?.textContent,marks:[...document.querySelectorAll('.au-photo-mark')].map(e=>getComputedStyle(e).opacity).join(),scroll:document.querySelector('.au-ns-view-content')?.scrollTop});};
   for(const phase of ['plan-shelf','plan-rest','fact-rest','node-rest','answer-rest','photo-rest','map-use','map-rest','wordmark-rest']){
    const b=a.manifest.beats.find(b=>b.phase===phase),target=b.end-1;a.advanceTo(0);a.advanceTo(target);const first=snapshot();a.advanceTo(a.manifest.duration-1);a.advanceTo(target);if(snapshot()!==first)failures.push(phase);
   }return failures;
  });assert.deepEqual(deterministic,[],'direct and backward seeks produce the same visible state');
  const intake=await page.evaluate(()=>{const a=CasepathPresentation.active;a.advanceTo(a.manifest.beats.find(b=>b.phase==='customer-passage-rest').end-1);return {source:document.querySelector('[data-au-customer-source]').dataset.auCustomerSource,quote:document.querySelector('[data-au-ns-quote]').textContent,fields:[...document.querySelectorAll('.au-ns-source-fields dt')].map(el=>el.textContent)};});
  const intakeState=recorded.cases[7].envelope.state;assert.equal(intake.source,intakeState.acquired_sources.find(s=>s.role==='customer_message').artifact_id);assert.equal(intake.quote,require('../casepath/assets/autonomous-workspace-v1.js').deskRequest(intakeState.message));assert.deepEqual(intake.fields,['From','To','Date']);
  const w10=await page.evaluate(()=>{
   const a=CasepathPresentation.active,m=a.manifest,checks=[];
   for(const beat of m.beats.filter(b=>['cursor','customer-cursor'].includes(b.phase))){a.advanceTo(beat.end-.001);const mark=document.querySelector('[data-au-ns-quote]'),pane=document.querySelector('.au-ns-source-scroll'),r=mark.getBoundingClientRect(),q=pane.getBoundingClientRect();checks.push({center:Math.abs((r.top+r.bottom-q.top-q.bottom)/2),font:getComputedStyle(mark).fontSize,line:getComputedStyle(mark).lineHeight,context:getComputedStyle(document.querySelector('.au-ns-source-context')).opacity,badge:document.querySelector('.au-executive-cursor .au-ns-role-badge')?.childElementCount,highlight:document.querySelector('.au-executive-ink').style.opacity});}
   // The shelf holds every learned checklist; the case on screen takes its own kind, in both cases.
   const shelves=m.beats.filter(b=>b.phase==='plan-shelf').map(beat=>{a.advanceTo(beat.end-1);return {act:beat.act,cards:document.querySelectorAll('[data-au-shelf-card]').length,selected:document.querySelector('[data-au-shelf-card][data-selected]')?.dataset.auShelfCard,claim:document.querySelector('[data-au-ns]')?.closest('[data-au-view]')&&document.querySelector('[data-au-claim-title]')?.textContent};});
   // The map ends on the recorded totals: every use drawn as one ring.
   a.advanceTo(m.beats.find(b=>b.phase==='map-rest').end-1);
   const counts=['checklists','cases','uses'].map(key=>+document.querySelector(`[data-au-map-count="${key}"]`).textContent),rings=[...document.querySelectorAll('.au-km-ring')].filter(e=>+getComputedStyle(e).opacity===1).length,lit=document.querySelectorAll('.au-km-case[data-lit=true]').length;
   a.advanceTo(m.beats.find(b=>b.phase==='fact-rest').end-1);const connector=document.querySelector('.au-ns-fact-connector');
   return {checks,counts,rings,lit,shelves,connector:connector.dataset.auNsConnectorNode,path:connector.querySelector('path').getAttribute('d'),selection:m.showcase};
  });
  assert.equal(w10.selection.claimId,recorded.cases[7].id);const replay=load('knowledge-w6').learning_replay,used=replay.events.filter(e=>e.kind==='knowledge.used');
  assert.deepEqual(w10.counts,[replay.events.filter(e=>e.kind==='knowledge.published').length,new Set(replay.events.map(e=>e.claim_id)).size,used.length]);assert.equal(w10.rings,used.length);assert.equal(w10.lit,w10.counts[1]);
  assert.deepEqual(w10.shelves.map(row=>[row.act,row.cards,row.selected]),[['plan',3,'procedure.rent_increase_dispute'],['learning',3,'procedure.rent_increase_dispute']]);
  assert.ok(w10.checks.every(row=>row.center<2&&row.font==='17px'&&row.line==='25.5px'&&row.context==='0.45'&&row.badge===1&&row.highlight==='0'),JSON.stringify(w10.checks));assert.ok(w10.connector);assert.match(w10.path,/H.*V.*H.*V/);
  if(process.env.CASEPATH_W10_SHOTS){for(const [name,phase]of [['reading','fact-rest'],['answer','answer-rest'],['knowledge','map-rest']]){await page.evaluate(phase=>{const a=CasepathPresentation.active,b=a.manifest.beats.find(b=>b.phase===phase);a.advanceTo(b.end-1);},phase);await page.screenshot({path:process.env.CASEPATH_W10_SHOTS+'/'+name+'.png'});}}
  const {auditPresentation}=await import('../design-plans/w9-20261021/audit_presentation.mjs');
  const {auditChecklistGeometry}=await import('../design-plans/tools/checklist_geometry_audit.mjs');
  await page.evaluate(`window.auditChecklistGeometry=${auditChecklistGeometry.toString()}`);
  const everyFrame=await page.evaluate(()=>{
   const active=CasepathPresentation.active,count=Math.ceil(active.manifest.duration*60/1000),failures=[],labelViews={};
   let collapsedFrames=0,checkedRows=0,checkedFacts=0,checkedLabels=0;
   for(let n=0;n<count;n++){
    active.advanceTo(n*1000/60);
    const audit=window.auditChecklistGeometry();
    for(const [act,labels] of Object.entries(audit.labelViews))labelViews[act]=(labelViews[act]||0)+labels;
    checkedRows+=audit.checked.rows;checkedFacts+=audit.checked.facts;checkedLabels+=audit.checked.labels;
    if(!audit.passed&&failures.length<40)failures.push({n,time:n*1000/60,...audit});
    const plan=document.querySelector('[data-au-ns-plan]');if(!plan)continue;
    const rows=[...plan.querySelectorAll('[data-au-ns-plan-row]')],spinners=rows.filter(row=>row.dataset.state==='active');
    const op=plan.closest('[data-au-ns]').dataset.auNsOperation;
    if(spinners.length>1||spinners.some(row=>row.hidden||!JSON.parse(row.dataset.auNsPlanOperations).includes(op)))failures.push({n,reason:'spinner does not identify only the current operation'});
    const summary=plan.querySelector('[data-au-ns-plan-summary]'),hidden=rows.filter(row=>row.hidden);
    if(!summary.hidden){collapsedFrames++;if(hidden.some(row=>row.dataset.state!=='done')||summary.textContent.replace(/\s+/g,' ').trim()!==`✓ ${hidden.length} done`)failures.push({n,reason:'summary must count exactly the collapsed completed rows'});}
   }
   return {count,checkedRows,checkedFacts,checkedLabels,labelViews,collapsedFrames,failures};
  });
  if(process.env.CASEPATH_W11_DIAGNOSTICS)fs.writeFileSync(process.env.CASEPATH_W11_DIAGNOSTICS+'-every-frame.json',JSON.stringify(everyFrame,null,2));
  assert.equal(everyFrame.count,Math.ceil(proof.manifest.duration*60/1000));
  assert.deepEqual(Object.keys(everyFrame.labelViews).sort(),proof.manifest.acts.map(act=>act.id).sort(),'labels are audited in all film acts');
  assert.ok(everyFrame.checkedRows>0&&everyFrame.checkedFacts>0&&everyFrame.checkedLabels>0&&everyFrame.collapsedFrames>0);
  assert.deepEqual(everyFrame.failures,[],'every film frame has intact rows, facts and labels and only its current spinner');
  // Negative control: the old cropped list must fail the new audit.
  await page.evaluate(at=>CasepathPresentation.active.advanceTo(at),proof.manifest.beats.find(b=>b.phase==='fact-rest').end-1);
  const clipped=await page.addStyleTag({content:'.au-workspace .au-ns-plan ol {max-height:30px;overflow:hidden}'});
  assert.equal((await page.evaluate(auditChecklistGeometry)).passed,false,'the audit detects a clipped checklist row');
  await clipped.evaluate(el=>el.remove());
  for(const [phase,selector] of [['legal-test-rest','.au-desk-tests > li > button'],['plan-rest','.au-ns-procedure li'],['fact-rest','.au-executive-checklist li'],['photo-rest','.au-ns-photo-findings li'],['map-rest','.au-km-case p']]){
   await page.evaluate(at=>CasepathPresentation.active.advanceTo(at),proof.manifest.beats.find(b=>b.phase===phase).end-1);
   assert.equal((await page.evaluate(auditChecklistGeometry)).passed,true,'unmodified '+phase+' labels fit');
   const crop=await page.addStyleTag({content:selector+' {height:5px!important;min-height:0!important;overflow:hidden!important}'});
   assert.equal((await page.evaluate(auditChecklistGeometry)).passed,false,'the audit detects a clipped '+phase+' label');
   await crop.evaluate(el=>el.remove());
  }

  const geometry=[];
  for(const beat of proof.manifest.beats.filter(b=>b.phase!=='act-transition')){await page.evaluate(at=>CasepathPresentation.active.advanceTo(at),beat.start+beat.duration/2);const hits=await page.evaluate(auditPresentation);if(hits.length)geometry.push({phase:beat.phase,operation:beat.operation,hits});}
  if(process.env.CASEPATH_W10_SHOTS)fs.writeFileSync(process.env.CASEPATH_W10_SHOTS+'/geometry.json',JSON.stringify(geometry,null,2));
  if(geometry.length&&process.env.CASEPATH_W11_DIAGNOSTICS){
   const failure=geometry[0],beat=proof.manifest.beats.find(b=>b.phase===failure.phase&&b.operation===failure.operation);
   await page.evaluate(at=>CasepathPresentation.active.advanceTo(at),beat.start+beat.duration/2);
   fs.writeFileSync(process.env.CASEPATH_W11_DIAGNOSTICS+'.json',JSON.stringify(await page.evaluate(()=>[...document.querySelectorAll('.au-ns-plan,.au-ns-plan li,.au-ns-log,.au-ns-right')].map(el=>({text:el.textContent,hidden:el.hidden,state:el.dataset.state,rect:el.getBoundingClientRect().toJSON()}))),null,2));
   await page.screenshot({path:process.env.CASEPATH_W11_DIAGNOSTICS+'.png'});
  }
  assert.deepEqual(geometry,[],'all beat midpoints have no unintended content overlaps');
  await page.evaluate(at=>CasepathPresentation.active.advanceTo(at),proof.manifest.beats.find(b=>b.phase==='fact-rest').end-1);
  const obstructingCard=await page.addStyleTag({content:'.au-workspace .au-doc-card {opacity:1!important}'});
  assert.ok((await page.evaluate(auditPresentation)).length===0,'the coach-mark card is audited by its own spotlight check, not as page content');
  await obstructingCard.evaluate(el=>el.remove());
  const ending=await page.evaluate(()=>{const a=CasepathPresentation.active;a.advanceTo(a.manifest.duration-1);const finale=document.querySelector('.au-cinema-finale'),heading=finale.querySelector('h2').getBoundingClientRect(),notice=finale.querySelector('small').getBoundingClientRect(),footer=document.querySelector('.au-executive-transport').getBoundingClientRect();return {above:heading.top,below:footer.top-notice.bottom,visible:getComputedStyle(finale).opacity,roster:getComputedStyle(document.querySelector('.au-claim-list')).opacity,title:finale.querySelector('h2').textContent,hidden:finale.getAttribute('aria-hidden')};});
  assert.ok(ending.above>=32&&ending.below>=32,JSON.stringify(ending));assert.equal(ending.visible,'1');assert.equal(ending.roster,'0');assert.equal(ending.hidden,'false');assert.match(ending.title,/A person always decides/);

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
   active.advanceTo(m.beats.find(b=>b.phase==='draft-rest').start);const draft=document.querySelector('[data-au-recorded-draft]').textContent;
   active.advanceTo(m.beats.find(b=>b.phase==='plan-rest').end-1);const plan={documents:[...document.querySelectorAll('[data-au-ns-procedure] li')].map(e=>e.dataset.auNsChecklistDoc),planned:document.querySelectorAll('[data-au-ns-planned]').length,heading:document.querySelector('[data-au-ns-procedure] h2').textContent};
   active.advanceTo(m.beats.find(b=>b.phase==='node-rest'&&b.act==='process').end-1);const checklist=document.querySelector('[data-au-ns-checklist] h2').textContent;
   const scan=m.beats.find(b=>b.phase==='photo-scan');active.advanceTo(scan.start+1);const litAtStart=[...document.querySelectorAll('.au-photo-mark')].filter(e=>+getComputedStyle(e).opacity>0).length;
   active.advanceTo(m.beats.find(b=>b.phase==='photo-rest').end-1);const photo={marks:document.querySelectorAll('.au-photo-mark').length,lit:[...document.querySelectorAll('.au-photo-mark')].filter(e=>+getComputedStyle(e).opacity===1).length,litAtStart,image:document.querySelector('[data-au-photo-frame] img').src,findings:document.querySelector('[data-au-photo-findings]').textContent};
   const later=m.beats.find(b=>b.act==='learning'&&b.phase==='plan-rest');active.advanceTo(later.end-1);
   const label=document.querySelector('.au-executive-later').textContent,title=document.querySelector('[data-au-claim-title]').textContent,laterDocuments=document.querySelectorAll('[data-au-ns-procedure] li').length;
   return {failures,checked,tests,draft,plan,checklist,photo,label,title,laterDocuments};
  },completions);
  assert.deepEqual(bindings.failures,[]);assert.ok(bindings.checked>0);
  assert.ok(proof.manifest.duration<170000,'the complete recorded story stays below 170 seconds');assert.match(bindings.draft,/Not sent — you decide/);assert.ok(bindings.draft.includes(recorded.cases[7].envelope.state.outcome.request_draft.body));
  assert.deepEqual(bindings.tests.map(t=>t.step),[2,2,2,3,3]);assert.ok(bindings.tests.every(t=>t.ring===20&&t.label===String(t.step)));
  // The plan shows only what the recording required: one row per document.require, one circle per evaluated step.
  const mainOps=recorded.cases[7].trace.trim().split('\n').map(JSON.parse).filter(row=>row.type==='operation');
  assert.equal(bindings.plan.documents.length,mainOps.filter(o=>o.kind==='document.require').length);assert.equal(new Set(bindings.plan.documents).size,bindings.plan.documents.length);
  assert.equal(bindings.plan.planned,new Set(mainOps.filter(o=>o.kind==='node.evaluate').map(o=>o.object.id)).size);assert.match(bindings.plan.heading,/rent increase/i);
  assert.match(bindings.checklist,/3 of 3 checked/);
  // The photo scene draws every measured mark from the service reading, revealed by the scan, never before it.
  const photoReading=Object.entries(photo.responses).find(([key])=>key.endsWith('/photo-reading'))[1];
  assert.equal(photoReading.evidence_admitted,false);assert.equal(bindings.photo.marks,photoReading.regions[0].segments.length);assert.equal(bindings.photo.lit,bindings.photo.marks);assert.ok(bindings.photo.litAtStart<bindings.photo.marks/4);
  assert.match(bindings.photo.image,/^blob:/);assert.match(bindings.photo.findings,/Dark spots found/);assert.match(bindings.photo.findings,/Photo taken 14 March 2025/);
  assert.ok(proof.manifest.acts.find(a=>a.id==='customer').end-proof.manifest.acts.find(a=>a.id==='customer').start<13000,'intake stops before repeated document reading');
  assert.equal(bindings.label,'New case');assert.ok(bindings.title.length);
  const laterOps=recorded.cases[8].trace.trim().split('\n').map(JSON.parse).filter(row=>row.type==='operation');assert.equal(bindings.laterDocuments,new Set(laterOps.filter(o=>o.kind==='document.require'&&o.seq>laterOps.find(r=>r.kind==='knowledge.reuse').seq).map(o=>o.object.id)).size);
  assert.ok(proof.manifest.beats.filter(b=>b.phase==='source-swap').every(b=>b.duration===(b.act==='process'?250:500)));
  await page.evaluate(at=>CasepathPresentation.active.seek(at),proof.manifest.beats.find(b=>b.phase==='fact-rest').start);
  const op=recorded.cases[7].trace.trim().split('\n').map(JSON.parse).find(row=>row.id===proof.factOperation);assert.deepEqual(proof.citation,op.source);const reading=proof.manifest.beats.find(b=>b.act==='reading'&&b.phase==='fact-rest'),readingOp=recorded.cases[7].trace.trim().split('\n').map(JSON.parse).find(row=>row.id===reading.operation);const recordingRows=recorded.cases[7].trace.trim().split('\n').map(JSON.parse).filter(row=>row.type==='operation'),catalogue=require('../casepath/assets/autonomous-workspace-v1.js').northStarPlanModel(recorded.cases[7].envelope.state,recordingRows),nextCompletion=proof.manifest.beats.find(b=>b.phase==='node-rest'&&b.start>reading.end),completionOp=recordingRows.find(row=>row.id===nextCompletion.operation);
  assert.equal(catalogue.links.get(readingOp.id),completionOp.object.id,'shown fact belongs to the next completed process node');assert.ok(readingOp.seq<completionOp.seq);assert.ok(reading.through>=readingOp.seq);assert.equal(await page.locator('[data-au-ns-fact-proposed]').first().textContent(),'The documents say no');
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
  if(photo.binary[key])return original(route,key);
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

async function assertPreparationRailVisible(page, failed=false){
 for(const viewport of [{width:1440,height:900},{width:375,height:812}]){
  await page.setViewportSize(viewport);
  const proof=await page.evaluate(async failed=>{
   await document.fonts.ready;await new Promise(resolve=>requestAnimationFrame(resolve));
   const status=document.querySelector('.au-ns-preparation-status'),retry=document.querySelector('[data-au-presentation-unavailable] [data-au-nav="demonstration"]');
   const check=element=>{if(!element)return null;const rect=element.getBoundingClientRect();return {text:element.textContent,inRail:!!element.closest('.au-ns-sources'),bounds:rect.toJSON(),fullyVisible:rect.width>0&&rect.height>0&&rect.left>=0&&rect.top>=0&&rect.right<=innerWidth+1&&rect.bottom<=innerHeight+1&&element.scrollWidth<=element.clientWidth+1&&element.scrollHeight<=element.clientHeight+1};};
   const details=document.querySelector('.au-global-status > .au-record-link');
   return {status:check(status),retry:check(retry),detailsGap:details?parseFloat(getComputedStyle(details).marginInlineStart):null,overflow:Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)-innerWidth};
  },failed);
  assert.equal(proof.status?.inRail,true);assert.equal(proof.status?.fullyVisible,true,JSON.stringify({viewport,proof}));
  assert.match(proof.status.text,failed?/The recorded walkthrough could not be opened/:/Preparing the recorded walkthrough/);
  if(failed){assert.equal(proof.retry?.text,'Try again');assert.equal(proof.retry?.inRail,true);assert.equal(proof.retry?.fullyVisible,true,JSON.stringify({viewport,proof}));assert.ok(proof.detailsGap>=8,'Details is separated from the error text');}
  assert.ok(proof.overflow<=1,JSON.stringify({viewport,proof}));
 }
 await page.setViewportSize({width:1440,height:900});
}

for(const ending of ['ready','cancelled','invalid','visibility'])test(`public preparation overlaps independent reads and keeps admission honest: ${ending}`,async()=>{
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
  if(photo.binary[key])return original(route,key);
  if(wire[key])return route.fulfill({contentType:'application/json',body:JSON.stringify(wire[key])});
  missing.push(key);return route.fulfill({status:404,contentType:'application/json',body:JSON.stringify({detail:'No recorded fixture for '+key})});
 });
 try{
  await page.goto('http://localhost:41999/?present=1');
  await page.addStyleTag({path:path.join(root,'casepath/assets/autonomous-workspace-v1.css')});
  for(const asset of ['autonomous-language-v1.js','autonomous-presentation-v1.js','autonomous-workspace-v1.js'])await page.addScriptTag({path:path.join(root,'casepath/assets',asset)});
  const initial=await page.evaluate(firstId=>{
   window.CASEPATH_PUBLIC_READ_ONLY=true;window.heldStates=[];window.beforeAdmissionTitles=[];window.preparationReadPaths=[];window.stateBodiesRead=[];
   new MutationObserver(()=>{if(!window.CasepathPresentation?.active){const title=document.querySelector('[data-au-claim-title]')?.textContent;if(title)window.beforeAdmissionTitles.push(title);}}).observe(document.querySelector('#workspace'),{childList:true,subtree:true});
   const fetch=async(url,init)=>{
    const address=new URL(url,location.href),path=address.pathname;window.preparationReadPaths.push(path+address.search);
    const response=await window.fetch(url,init);
    if(path.endsWith(`/claims/${firstId}/operations`)&&!window.openingReleased)return new Promise(resolve=>{window.releaseOpening=()=>{window.openingReleased=true;resolve(response);};});
    const id=path.match(/\/claims\/([^/]+)$/)?.[1];
    // Deliberately deliver held responses even after abort: route ownership
    // must reject late work rather than relying only on a cooperative network.
    if(id){const json=response.json.bind(response);response.json=async()=>{const data=await json();window.stateBodiesRead.push(id);return data;};return new Promise(resolve=>window.heldStates.push({id,signal:init.signal,response,resolve}));}
    return response;
   };
   window.product=CasePathAutonomous.mount(document.querySelector('#workspace'),{fetch});
   return {preparing:!!document.querySelector('[data-au-presentation-preparing][aria-busy="true"]'),purpose:document.querySelector('[data-au-ns-purpose]')?.textContent,title:document.title,caseTitle:document.querySelector('[data-au-claim-title]')?.textContent};
  },recorded.cases[0].id);
  assert.equal(initial.preparing,true,'the introduction exists synchronously before any response');assert.match(initial.purpose,/From a customer’s documents/);assert.match(initial.purpose,/A person decides/);assert.equal(initial.caseTitle,undefined);assert.equal(initial.title,'Demonstration — CasePath');
  await page.waitForFunction(()=>typeof window.releaseOpening==='function',{},{timeout:45000});
  assert.equal(await page.locator('[data-au-presentation-preparing]').count(),1);assert.equal(await page.evaluate(()=>Boolean(CasepathPresentation.active)),false);
  await page.evaluate(()=>window.releaseOpening());
  await page.waitForFunction(count=>window.heldStates.length===count,recorded.cases.length-1,{timeout:10000});
  assert.deepEqual((await page.evaluate(()=>window.heldStates.map(row=>row.id))).sort(),recorded.cases.slice(1).map(row=>row.id).sort(),'every independent state read starts before any is released');
  assert.deepEqual(await page.evaluate(()=>window.beforeAdmissionTitles),[],'the unrelated first case is never painted while selecting the showcase');
  assert.equal(await page.locator('[data-au-presentation-preparing]').count(),1);
  if(ending==='ready')await assertPreparationRailVisible(page);
  if(ending==='cancelled')await page.evaluate(()=>product.showWork());
  let hiddenReads;
  if(ending==='visibility')hiddenReads=await page.evaluate(()=>{
   const before=window.preparationReadPaths.filter(path=>/\/operations\?|\/replay\?/.test(path));
   Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));
   return before;
  });
  await page.evaluate(async ending=>{
   const reads=[...window.heldStates].reverse();
   if(ending==='invalid'){
    const row=reads.shift(),data=await row.response.json();
    (data.state||data).claim_id='unrelated-claim';
    row.resolve(new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}}));
   }
   for(const row of reads){row.resolve(row.response);await Promise.resolve();}
  },ending);
  if(ending==='ready'){
   await page.waitForFunction(()=>window.CasepathPresentation?.active,{},{timeout:45000});
   const admitted=await page.evaluate(()=>({claims:CasepathPresentation.active.manifest.claims,hashes:CasepathPresentation.active.manifest.stateHashes,paused:CasepathPresentation.active.paused}));
   assert.deepEqual(admitted.claims,recorded.cases.slice(7).map(row=>row.id));assert.deepEqual(admitted.hashes,recorded.cases.slice(7).map(row=>row.envelope.state.state_sha256));assert.equal(admitted.paused,false,'present=1 begins only after actual admission');
   assert.equal(await page.locator('[data-au-ns-start]').count(),0);assert.equal(await page.locator('[data-au-presentation-preparing]').count(),0);
  }else if(ending==='cancelled'){
   await page.waitForFunction(()=>window.heldStates.every(row=>row.signal.aborted)&&!document.querySelector('[data-au-presentation-preparing]'));
   assert.equal(await page.locator('[data-au-view-state="work"]').count(),1);assert.equal(await page.evaluate(()=>Boolean(CasepathPresentation.active)),false);
  }else if(ending==='visibility'){
   // Wait for all held JSON bodies to be consumed. The existing operation gate
   // must keep the next-case admission suspended until the tab is visible.
   await page.waitForFunction(count=>window.stateBodiesRead.length===count,recorded.cases.length-1,{timeout:45000});
   assert.equal(await page.evaluate(()=>Boolean(CasepathPresentation.active)),false);
   assert.equal(await page.locator('[data-au-presentation-preparing]').count(),1);assert.equal(await page.locator('[data-au-presentation-unavailable]').count(),0);
   assert.deepEqual(await page.evaluate(()=>window.preparationReadPaths.filter(path=>/\/operations\?|\/replay\?/.test(path))),hiddenReads,'hidden state delivery cannot start the next recording or a fallback');
   await page.evaluate(()=>{delete document.hidden;document.dispatchEvent(new Event('visibilitychange'));});
   await page.waitForFunction(()=>window.CasepathPresentation?.active,{},{timeout:45000});
   const admitted=await page.evaluate(()=>({claims:CasepathPresentation.active.manifest.claims,hashes:CasepathPresentation.active.manifest.stateHashes,paused:CasepathPresentation.active.paused}));
   assert.deepEqual(admitted.claims,recorded.cases.slice(7).map(row=>row.id));assert.deepEqual(admitted.hashes,recorded.cases.slice(7).map(row=>row.envelope.state.state_sha256));assert.equal(admitted.paused,false);
   assert.equal(await page.locator('[data-au-presentation-preparing],[aria-busy="true"]').count(),0,'returning to the tab cannot leave admission hanging');
  }else{
   await page.waitForFunction(()=>document.querySelector('.au-global-status')?.textContent.includes('Could not load this recorded walkthrough'),{},{timeout:45000});
   assert.equal(await page.evaluate(()=>Boolean(CasepathPresentation.active)),false);assert.equal(await page.locator('[data-au-presentation-preparing]').count(),0,'invalid state cannot leave a permanent preparation screen or start the film');
   assert.equal(await page.locator('[data-au-presentation-unavailable]').count(),1);assert.equal(await page.locator('[aria-busy="true"]').count(),0);
   assert.equal(await page.locator('[data-au-presentation-unavailable] [data-au-nav="demonstration"]').textContent(),'Try again');
   assert.equal(await page.locator('[data-au-claim-title],.au-ns-spine li,[data-au-source]').count(),0,'an admitted fallback remains in memory without exposing the unrelated first case');
   assert.doesNotMatch(await page.locator('[data-au-view]').innerText(),/heating|Showing the saved result/i);
   await assertPreparationRailVisible(page,true);
  }
  assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);assert.deepEqual(missing,[]);
 }catch(error){error.message+='\nMissing fixture reads: '+JSON.stringify(missing)+'\nPage errors: '+JSON.stringify(errors)+'\nUI: '+(await page.locator('body').innerText()).slice(0,1000);throw error;}
 finally{await page.evaluate(()=>{window.releaseOpening?.();for(const row of window.heldStates||[])row.resolve(row.response);window.product?.destroy();}).catch(()=>{});for(const close of [()=>page.close(),()=>context.close(),()=>browser.close()]){let timer;await Promise.race([close(),new Promise(resolve=>{timer=setTimeout(resolve,10000);})]);clearTimeout(timer);}}
});
