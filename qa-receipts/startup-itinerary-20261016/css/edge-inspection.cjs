'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{createHash,webcrypto}=require('node:crypto');
if(!globalThis.crypto)globalThis.crypto=webcrypto;
const {chromium}=require('/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='/workspace/casepath-stage-edge-css-20261016',out=__dirname,ui=require(path.join(root,'casepath/assets/autonomous-workspace-v1.js'));
const cssFile=path.join(root,'casepath/assets/autonomous-workspace-v1.css'),baseCSS=fs.readFileSync(path.join(out,'base.css'),'utf8');
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
async function fixture(){
 const bytes=fs.readFileSync('/workspace/casepath-recorded-packet-prototype-evidence-20261015/first-native.json');
 const packet=await ui.checkedRecordedPacket(bytes,{bytes:bytes.length,sha256:sha(bytes),history_kind:'native_fixture',deployment_commit:null},true);
 const id=packet.claims[0].claim_id,session=await ui.decodeRecordedSession(packet,id),frames=new TextDecoder().decode(session.operations).trim().split('\n').map(JSON.parse);
 const head=await ui.checkedAtomicOperationHead(session.head_snapshot,session.head,session.opening.replay_start,session.opening.state);
 const trace={binding:null,rows:[],bytes:0,sources:new Map(),journal:[],pinnedJournal:head.accepted.events,transportState:null,finished:false,working:null,checkpoints:[],dockedFacts:new Map(),dockPhases:new Map(),recorded:true,plannedProcess:await ui.plannedOperationProcess(head.state),releasePlan:ui.releaseOperationProcess(id)};
 let current=session.opening.state,projection=session.opening.projection,events=[],target=null,firstFact=null;
 for(const frame of frames){
  if(frame.type==='binding')trace.binding=ui.checkedOperationBinding(frame,session.head,session.opening.replay_start);
  if(frame.type==='checkpoint'){
   const incoming=await ui.checkedOperationCheckpoint(frame,trace);current=incoming.state;projection=incoming.projection;events=incoming.accepted.events;trace.working=null;
   trace.checkpoints.push({after_operation:trace.rows.length,state:current,projection,events});
  }
  if(frame.type==='operation'){
   await ui.checkedOperation(frame,trace,current);ui.applyWorkingOperation(frame,trace,current);trace.current=frame;
   const node=ui.operationNodeId(frame,ui.operationStageGraph(trace,current),current,trace);
   if(frame.kind==='fact.extract'&&frame.source&&node)trace.dockedFacts.set(frame.object.id,{operation:frame,node,observed:true});
   if(frame.kind==='fact.extract'&&frame.source&&node&&!firstFact)firstFact=ui.workMarkup(current,projection,node,events,'step',{}, {mode:'replay',operations:trace,playing:true});
   if(frame.kind==='fact.extract'&&frame.object.id==='fact:objective_defect_observation'&&!target){
    const html=ui.workMarkup(current,projection,node,events,'step',{}, {mode:'replay',operations:trace,playing:true});
    target={html,operation:frame.id,source:frame.source,node,revision:current.revision,graph:ui.operationStageGraph(trace,current).graph_sha256};
   }
  }
 }
 assert.ok(target);assert.equal(current.state_sha256,head.state.state_sha256);assert.equal(trace.rows.length,frames.at(-1).operation_count);
 return {...target,firstFact,settled:ui.workMarkup(current,projection,ui.preferredNode(current),events,'step',{}, {mode:'replay',operations:{...trace,finished:true,current:null},playing:false}),packet_sha256:sha(bytes),operations:trace.rows.length};
}
async function geometry(page){return page.evaluate(()=>{
 const port=document.querySelector('.au-graph-viewport'),active=document.querySelector('[data-au-stage-active=true]'),source=active?.querySelector('.au-stage-source'),node=active?.querySelector('.au-node');
 const rect=el=>{const r=el?.getBoundingClientRect();return r?{left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height}:null;};
 const area=port.getBoundingClientRect();return{viewport:rect(port),active:rect(active),source:rect(source),node:rect(node),mask:getComputedStyle(port).maskImage,scrollLeft:port.scrollLeft,scrollTop:port.scrollTop,text:source?.textContent,labels:[...document.querySelectorAll('.au-node-title')].map(el=>({text:el.textContent,rect:rect(el)})).filter(({rect:r})=>r.left<area.right&&r.right>area.left&&r.top<area.bottom&&r.bottom>area.top),animations:document.getAnimations().length,accessible:port.getAttribute('aria-label'),tabindex:port.tabIndex};
});}
async function stage(page,html,css){await page.setContent('<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0"><main class="au-workspace"><div class="au-shell"><header class="au-header"><span class="au-brand">CasePath</span></header><div class="au-main"><div data-au-operation-presentation="playing">'+html+'</div></div></div></main></body></html>');await page.addStyleTag({content:css});await page.evaluate(()=>document.fonts.ready);await page.evaluate(()=>{const port=document.querySelector('.au-graph-viewport'),step=document.querySelector('[data-au-stage-active=true]');if(step){const a=port.getBoundingClientRect(),b=step.getBoundingClientRect();port.scrollLeft+=b.left-a.left-(a.width-b.width)/2;port.scrollTop+=b.top-a.top-(a.height-b.height)/2;}});}
(async()=>{
 const native=await fixture(),browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']}),runs=[];
 try{
  for(const config of [{name:'desktop',width:1280,height:800,reducedMotion:'no-preference'},{name:'mobile',width:390,height:844,reducedMotion:'no-preference'},{name:'reduced',width:1280,height:800,reducedMotion:'reduce'}]){
   const context=await browser.newContext({viewport:{width:config.width,height:config.height},reducedMotion:config.reducedMotion,serviceWorkers:'block'}),page=await context.newPage();
   await page.route('**/*',route=>route.abort());await stage(page,native.html,baseCSS);const before=await geometry(page);await page.screenshot({path:path.join(out,config.name+'-before.png')});runs.push({config,context,page,before});
  }
  fs.writeFileSync(path.join(out,'before.json'),JSON.stringify({native:{...native,html:undefined,settled:undefined,firstFact:undefined},runs:runs.map(({config,before})=>({config,before}))},null,2));console.log('BASELINE_READY');
  if(!process.argv.includes('--auto'))await new Promise(resolve=>process.stdin.once('data',resolve));
  const css=fs.readFileSync(cssFile,'utf8'),results=[];
  for(const {config,page,before} of runs){
   await stage(page,native.html,css);const after=await geometry(page);await page.screenshot({path:path.join(out,config.name+'-after.png')});
   assert.deepEqual(after.source,before.source,'active excerpt geometry');assert.deepEqual(after.node,before.node,'destination geometry');assert.equal(after.text,before.text);assert.equal(after.tabindex,0);assert.equal(after.accessible,before.accessible);assert.equal(after.animations,0);
   const pans=[];for(const dx of config.width>700?[-220,0,12]:[-10,0,10]){
    await stage(page,native.html,baseCSS);await page.evaluate(dx=>document.querySelector('.au-graph-viewport').scrollLeft+=dx,dx);const panBefore=await geometry(page);await page.screenshot({path:path.join(out,config.name+'-pan'+dx+'-before.png')});
    await stage(page,native.html,css);await page.evaluate(dx=>document.querySelector('.au-graph-viewport').scrollLeft+=dx,dx);const panAfter=await geometry(page);await page.screenshot({path:path.join(out,config.name+'-pan'+dx+'-after.png')});
    assert.deepEqual(panAfter.source,panBefore.source);assert.deepEqual(panAfter.node,panBefore.node);pans.push({dx,before:panBefore,after:panAfter});
   }
   await page.locator('.au-graph-viewport').focus();const focused=await geometry(page);assert.equal(focused.mask,'none');
   await stage(page,native.firstFact,css);const first=await geometry(page),inset=config.width>700?64:8;
   assert.ok(first.source.left-first.viewport.left>=inset);assert.ok(first.source.right<=first.viewport.right-inset);assert.ok(first.node.left-first.viewport.left>=inset);assert.ok(first.node.right<=first.viewport.right-inset);
   await page.screenshot({path:path.join(out,config.name+'-first-source.png')});
   await stage(page,native.settled,css);const settled=await geometry(page);await page.screenshot({path:path.join(out,config.name+'-settled.png')});assert.equal(settled.mask,'none');
   results.push({config,before,after,pans,focused,first,settled});
  }
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({disclosure:'Static production stage markup from existing native fixture, each operation and checkpoint verified in order; native Chromium geometry/pan/screenshots. No controller timing or live runtime claim.',base:'5086624c8a024ba298819e5e27d749efbd0cc7fc',css_sha256:sha(css),native:{...native,html:undefined,settled:undefined,firstFact:undefined},results},null,2));console.log('EDGE_CHECKS_PASSED '+results.length);
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
