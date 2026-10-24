import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createHash,webcrypto} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const ROOT="/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-demo-polish-clone-20261024";
const NS=path.join(ROOT,'.runtime/commander-demo-polish'),BASE=path.join(NS,'release'),OUT=path.join(BASE,'eight-state-capture');
const SITE='https://casepath-autonomous.kumarnavish.chatgpt.site';
const read=file=>JSON.parse(fs.readFileSync(file,'utf8')),hash=bytes=>createHash('sha256').update(bytes).digest('hex'),digest=file=>hash(fs.readFileSync(file));
const SHA=read(path.join(NS,'source-binding.json')).source_commit;assert.match(SHA,/^[0-9a-f]{40}$/);
const helperBindingPath=path.join(BASE,'northstar-artifact-inputs.json'),helperBinding=read(helperBindingPath);
assert.equal(helperBinding.source_commit,SHA);assert.equal(helperBinding.helpers['capture_eight_states.mjs'],digest(new URL(import.meta.url)));
assert.equal(helperBinding.source_binding_sha256,digest(path.join(NS,'source-binding.json')));
const PY=path.join(ROOT,'.runtime/casepath-dev-v2/venv/bin/python');
execFileSync(PY,['-I','-B','-c','import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); from require_completed_gate import require_completed_gate; require_completed_gate(Path(sys.argv[1]),sys.argv[2])',BASE,SHA],{cwd:ROOT,env:{PATH:'/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',PYTHONDONTWRITEBYTECODE:'1',LANG:'C.UTF-8',LC_ALL:'C.UTF-8',TZ:'UTC'},timeout:60000});
const acceptancePath=path.join(BASE,'published-acceptance-sequence.json'),acceptance=read(acceptancePath);
assert.equal(acceptance.status,'passed');assert.equal(acceptance.source_commit,SHA);assert.equal(digest(acceptancePath),helperBinding.published_acceptance_sha256);
const git=(...args)=>execFileSync('/usr/bin/git',args,{cwd:ROOT,encoding:'utf8'}).trim();
assert.equal(git('rev-parse','HEAD'),SHA);assert.equal(git('status','--porcelain'),'');
const sealedPath=path.join(NS,'sealed-browser-command.json'),sealed=read(sealedPath);
assert.equal(sealed.source_commit,SHA);assert.equal(sealed.status,'passed');assert.equal(sealed.exit_code,0);assert.equal(sealed.source_clean_after,true);
assert.equal(digest(sealedPath),helperBinding.sealed_browser_command_sha256);
if(!globalThis.crypto)globalThis.crypto=webcrypto;
const require=createRequire('/Users/kumar0002/Documents/Die Mobiliar/casepath-canonical/casepath-qa/package.json'),{chromium}=require('playwright'),ui=require(path.join(ROOT,'casepath/assets/autonomous-workspace-v1.js'));
for(const name of ['readState','readReplay','checkedAtomicOperationHead','checkedReferenceReplayStart','checkedOperationBinding','checkedOperation','checkedOperationCheckpoint'])assert.equal(typeof ui[name],'function',name);
assert.equal(fs.existsSync(OUT),false);fs.mkdirSync(OUT);fs.mkdirSync(path.join(OUT,'inputs'));
const report={contract:'casepath.eight-state-engineering-evidence/2',source_commit:SHA,started_at:new Date().toISOString(),viewport:{width:1440,height:900},status:'running',script_sha256:digest(new URL(import.meta.url)),helper_binding_sha256:digest(helperBindingPath),source_binding_sha256:digest(path.join(NS,'source-binding.json')),official_validator_sha256:digest(path.join(ROOT,'casepath/assets/autonomous-workspace-v1.js')),states:[],errors:[],writes:[],edge_beacons:[],http_inputs:[],live_trace_validations:[],trace_reads:[],assets:{},coverage_scope:'Fresh recorded source-to-process journey plus the exact sealed isolated Test handler edit, versioning and later-case reuse',trace_input_proof_scope:'Production checkedOperationBinding validates the run, accepted replay start, profile, source roster, rule set, saved head and input hash field. The top-level input_sha256 is not independently reconstructed from a separate initial-input payload. Every operation input/result hash, source text hash, Unicode span, checkpoint and final chain is validated from freshly captured responses.',qualified_human_approval:'pending',literal_state_8_expert_review_acceptance:false,claim_outcome_authorized:false};
const reportPath=path.join(OUT,'eight-state-evidence.json');fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n',{flag:'wx'});
function persist(){const next=reportPath+'.next';fs.writeFileSync(next,JSON.stringify(report,null,2)+'\n',{flag:'wx'});fs.renameSync(next,reportPath);}
let browser,context,page;
const traces=new Map(),states=new Map();
async function getBytes(url,name,limit=24*1024*1024){
 assert.equal(new URL(url).origin,SITE);assert.match(name,/^[a-zA-Z0-9_.-]+$/);
 const response=await context.request.get(url,{headers:{'Cache-Control':'no-cache'},timeout:60000,maxRedirects:0});
 const bytes=await response.body();assert.ok(bytes.length>0&&bytes.length<=limit,name+' response bound');
 const file='inputs/'+name;fs.writeFileSync(path.join(OUT,file),bytes,{flag:'wx'});
 const headers=response.headers(),observed={method:'GET',url:response.url(),status:response.status(),file,sha256:hash(bytes),bytes:bytes.length,content_type:headers['content-type']||null,received_at:new Date().toISOString()};
 report.http_inputs.push(observed);persist();assert.equal(response.status(),200,name+' HTTP status');assert.equal(new URL(response.url()).origin,SITE);
 return {bytes,observed,json(){return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}};
}
async function setup(){
browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
context=await browser.newContext({viewport:report.viewport,serviceWorkers:'block',reducedMotion:'no-preference',deviceScaleFactor:1});page=await context.newPage();
page.on('pageerror',error=>report.errors.push(error.message));
page.on('console',message=>{if(message.type()==='error')report.errors.push(message.text());});
await page.route('**/*',route=>{const request=route.request(),url=new URL(request.url());if(['GET','HEAD'].includes(request.method()))return route.continue();if(url.origin===SITE&&url.pathname.startsWith('/cdn-cgi/')){report.edge_beacons.push({method:request.method(),path:url.pathname,network_request_suppressed:true});return route.fulfill({status:204,body:''});}report.writes.push(request.method()+' '+url.origin+url.pathname);return route.abort();});
}
function checkPNG(file){const bytes=fs.readFileSync(file);assert.equal(bytes.subarray(1,4).toString(),'PNG');assert.equal(bytes.readUInt32BE(16),1440);assert.equal(bytes.readUInt32BE(20),900);return {sha256:hash(bytes),bytes:bytes.length,width:1440,height:900};}
async function capture(number,name,beat,at){
 if(at!==null)await page.evaluate(time=>CasepathPresentation.active.advanceTo(time),at);
 const observed=await page.evaluate(()=>{
  const host=document.querySelector('[data-au-view]'),visible=e=>e.getClientRects().length>0&&!e.closest('.au-executive-transition')&&Number(getComputedStyle(e).opacity)>0;
  const paper=[...document.querySelectorAll('[data-au-ns-paper]')].find(visible),mark=paper?.querySelector('[data-au-ns-quote]'),pin=paper?.querySelector('[data-au-citation]'),ink=paper?.querySelector('.au-executive-ink');
  return {time:CasepathPresentation.active.time,phase:host?.dataset.auPresentationPhase,act:host?.dataset.auPresentationAct,
   overflow:document.documentElement.scrollWidth>innerWidth,animations:document.getAnimations().filter(a=>a.playState==='running').length,
   start_control_visible:[...document.querySelectorAll('[data-au-ns-start]')].some(visible),source_open:!!paper,
   quote:mark?{text:mark.textContent,start:Number(mark.dataset.start),end:Number(mark.dataset.end),ink_opacity:ink?Number(ink.style.opacity):null}:null,
   source_pin:pin?JSON.parse(pin.dataset.auCitation):null,
   visible_facts:[...document.querySelectorAll('[data-au-ns-fact]')].filter(visible).map(e=>({operation:e.dataset.auNsFact,citation:JSON.parse(e.dataset.auCitation),text:e.textContent.trim()})),
   done_nodes:[...document.querySelectorAll('[data-au-ns-node][data-state=done]')].filter(visible).map(e=>({node_id:e.dataset.auNsNode,text:e.textContent.trim()})),
   completed_process:!!document.querySelector('[data-au-ns-completed]'),
   local_chain_columns:[...document.querySelectorAll('[data-au-ns-chain]')].filter(visible).map(e=>e.dataset.auNsChain)};
 });
 assert.equal(observed.overflow,false,name+' overflow');assert.equal(observed.animations,0,name+' animations');
 const filename='state-'+number+'-'+name+'.png',file=path.join(OUT,filename);await page.screenshot({path:file});
 const row={state:number,name,file:filename,capture_kind:'Deterministic inspection of the actual deployed recorded presentation',claim_id:beat?.claim||null,beat:beat||null,observed,...checkPNG(file)};
 report.states.push(row);persist();return row;
}
try{
 await setup();
 const deploymentResponse=await getBytes(SITE+'/deployment.json','deployment.json',1024*1024);report.deployment=deploymentResponse.json();assert.equal(report.deployment.source_commit,SHA);
 for(const asset of ['autonomous-workspace-v1.js','autonomous-workspace-v1.css','autonomous-presentation-v1.js','autonomous-language-v1.js','fonts/Mulish.ttf']){
  const response=await getBytes(SITE+'/assets/'+asset,'asset-'+asset.replaceAll('/','-'));assert.equal(hash(response.bytes),digest(path.join(ROOT,'casepath/assets',asset)));report.assets[asset]=hash(response.bytes);
 }
 await page.goto(SITE+'/#autonomous/demonstration',{waitUntil:'domcontentloaded'});
 await page.locator('[data-au-ns-start]').waitFor({timeout:90000});await page.waitForFunction(()=>window.CasepathPresentation?.active,undefined,{timeout:90000});await page.evaluate(()=>document.fonts.ready);
 const manifest=await page.evaluate(()=>CasepathPresentation.active.manifest);report.manifest=manifest;assert.equal(manifest.duration,88050);assert.equal(manifest.claims.length,manifest.stateHashes.length);assert.equal(new Set(manifest.claims).size,manifest.claims.length);
 const manifestBytes=Buffer.from(JSON.stringify(manifest,null,2)+'\n');fs.writeFileSync(path.join(OUT,'admitted-manifest.json'),manifestBytes,{flag:'wx'});report.admitted_manifest_sha256=hash(manifestBytes);
 const ready=await capture(1,'ready',manifest.beats[0],null);assert.ok(ready.observed.start_control_visible);assert.equal(ready.observed.time,0);
 const choose=(act,phase,extra=()=>true)=>{const beat=manifest.beats.find(row=>row.act===act&&row.phase===phase&&extra(row));assert.ok(beat,act+'/'+phase);return beat;};
 const opened=choose('reading','camera-in');const state2=await capture(2,'source-opened',opened,opened.end-1);assert.ok(state2.observed.source_open);assert.equal(state2.observed.quote.ink_opacity,0);
 const passage=choose('reading','passage-rest');const state3=await capture(3,'exact-passage',passage,passage.end-1);const q=state3.observed.quote,pin=state3.observed.source_pin;assert.ok(pin);assert.equal(q.text,pin.quote);assert.equal(q.start,pin.start_char);assert.equal(q.end,pin.end_char);assert.ok(q.ink_opacity>0);
 const fact=choose('reading','fact-rest');const state4=await capture(4,'source-bound-fact',fact,fact.end-1);assert.ok(state4.observed.visible_facts.length);assert.deepEqual(state4.observed.visible_facts.at(-1).citation,state4.observed.source_pin);assert.deepEqual(state2.observed.source_pin,state3.observed.source_pin);assert.deepEqual(state3.observed.source_pin,state4.observed.source_pin);
 for(const cid of manifest.claims){
  assert.match(cid,/^clm_[a-f0-9]+$/);
  const endpoint=SITE+'/api/claim-loops/v1/autonomous/claims/'+encodeURIComponent(cid);
  const fetched=await Promise.allSettled([
   getBytes(endpoint,cid+'-claim.json',8*1024*1024),
   getBytes(endpoint+'/replay?through_seq=0',cid+'-opening.json',8*1024*1024),
   getBytes(endpoint+'/snapshot?after=0',cid+'-snapshot.json'),
   getBytes(endpoint+'/operations?mode=recorded',cid+'-operations.ndjson')
  ]);
  const rejected=fetched.filter(row=>row.status==='rejected');if(rejected.length)throw new AggregateError(rejected.map(row=>row.reason),'Fresh recorded inputs unavailable for '+cid);
  const [claimInput,openingInput,snapshotInput,operationsInput]=fetched.map(row=>row.value);
  const state=ui.readState(claimInput.json(),cid).state,opening=ui.readReplay(openingInput.json(),cid,0);
  const head={claimId:cid,revision:opening.replay.current_revision,state_sha256:opening.replay.current_state_sha256,event_sha256:opening.replay.current_event_sha256};
  assert.equal(state.state_sha256,head.state_sha256);assert.equal(state.revision,head.revision);assert.equal(state.last_event_sha256,head.event_sha256);
  assert.equal(state.state_sha256,manifest.stateHashes[manifest.claims.indexOf(cid)],'fresh current state matches the admitted presentation');
  const full=await ui.checkedAtomicOperationHead(snapshotInput.json(),head,opening.replay.replay_start,opening.state);
  assert.deepEqual(full.state,state,'independent current and atomic reads agree exactly');
  const start=ui.checkedReferenceReplayStart(opening.replay.replay_start,full);assert.ok(start);
  const operationHead={...head,source_roster_sha256:state.source_roster_sha256,rule_set_sha256:ui.referenceExecution(state)?.rule_set_sha256};
  assert.match(operationHead.source_roster_sha256,/^[a-f0-9]{64}$/);assert.match(operationHead.rule_set_sha256,/^[a-f0-9]{64}$/);
  const body=new TextDecoder('utf-8',{fatal:true}).decode(operationsInput.bytes),lines=body.split('\n').filter(line=>line.trim());
  assert.ok(lines.length>2&&lines.length<=10002,'bounded complete operation stream');
  for(const line of lines)assert.ok(line.length*2<=2*1024*1024,'production per-frame bound');
  const frames=lines.map(JSON.parse),trace={rows:[],sources:new Map(),bytes:0,pinnedJournal:full.accepted.events,journal:[],transportState:null,frameHashes:[],headState:state};
  let prefix=opening.state,result=null,checkpointCount=0;
  for(const frame of frames){
   assert.equal(frame.contract,'casepath.operations-stream/1.0.0');assert.equal(result,null,'no frames may follow the final result');
   if(frame.type!=='result')trace.frameHashes.push(hash(ui.canonicalJSON(frame)));
   if(frame.type==='binding'){
    assert.equal(trace.binding,undefined,'exactly one binding');assert.equal(trace.rows.length,0);assert.equal(trace.frameHashes.length,1);
    trace.binding=ui.checkedOperationBinding(frame,operationHead,start);
   }else if(frame.type==='operation')await ui.checkedOperation(frame,trace,prefix);
   else if(frame.type==='checkpoint'){prefix=(await ui.checkedOperationCheckpoint(frame,trace)).state;checkpointCount++;}
   else if(frame.type==='result'){
    assert.ok(trace.binding);assert.equal(prefix.state_sha256,state.state_sha256,'checkpoints reach the admitted saved head');
    assert.equal(frame.state_sha256,state.state_sha256);assert.equal(frame.current_event_sha256,state.last_event_sha256);
    assert.equal(frame.operation_count,trace.rows.length);assert.equal(frame.operation_chain_sha256,trace.rows.at(-1)?.operation_sha256);assert.equal(frame.exact_output_verified,true);
    assert.equal(frame.trace_sha256,hash(ui.canonicalJSON(trace.frameHashes)));result=frame;
   }else throw new Error('Unsupported recorded frame: '+frame.type);
  }
  assert.ok(result&&checkpointCount>0,'a verified recorded ending and accepted checkpoints are required');
  assert.deepEqual(prefix,state,'the final checkpoint reproduces the exact current state');
  const validation={claim_id:cid,trace_url:operationsInput.observed.url,trace_file:operationsInput.observed.file,trace_sha256:operationsInput.observed.sha256,claim_file:claimInput.observed.file,claim_sha256:claimInput.observed.sha256,opening_file:openingInput.observed.file,opening_sha256:openingInput.observed.sha256,snapshot_file:snapshotInput.observed.file,snapshot_sha256:snapshotInput.observed.sha256,state_sha256:state.state_sha256,operation_count:trace.rows.length,checkpoint_count:checkpointCount,operation_chain_sha256:result.operation_chain_sha256,frame_trace_sha256:result.trace_sha256,delivery_mode:trace.binding.mode,input_sha256:trace.binding.input_sha256,input_digest_independently_reconstructed:false,official_readState_passed:true,official_atomic_head_passed:true,official_replay_start_passed:true,official_checkedOperationBinding_passed:true,official_checkedOperation_all_passed:true,official_checkpoints_all_passed:true,final_binding_verified:true,admitted_state_hash_matched:true};
  report.live_trace_validations.push(validation);report.trace_reads.push({claim_id:cid,url:operationsInput.observed.url,status:200});persist();
  traces.set(cid,{url:operationsInput.observed.url,sha256:operationsInput.observed.sha256,rows:trace.rows,sources:trace.sources,validation});states.set(cid,state);
 }
 const factTrace=traces.get(state4.claim_id);assert.ok(factTrace,'the depicted fact has an actual recorded trace');
 for(const visible of state4.observed.visible_facts){const operation=factTrace.rows.find(row=>row.id===visible.operation);assert.equal(operation?.kind,'fact.extract');assert.deepEqual(visible.citation,operation.source);}
 assert.equal(state4.observed.visible_facts.at(-1).operation,state4.beat.operation);assert.equal(state3.beat.operation,state4.beat.operation);
 const candidates=[];
 for(const beat of manifest.beats.filter(row=>row.phase==='node-rest'&&['reading','process'].includes(row.act))){
  const actual=traces.get(beat.claim);assert.ok(actual&&states.has(beat.claim),'actual recorded trace and actual served graph exist');
  const rows=actual.rows,completion=rows.find(row=>row.id===beat.operation);assert.equal(completion?.kind,'step.complete');assert.equal(completion.result.status,'completed');
  const graphReference=states.get(beat.claim),model=ui.northStarPlanModel(graphReference,rows),plan=model.plans.get(completion.object.id),facts=plan.filter(row=>row.operation.kind==='fact.extract').map(row=>row.operation);
  assert.equal(graphReference.state_sha256,manifest.stateHashes[manifest.claims.indexOf(beat.claim)],'graph state matches the admitted presentation hash');
  const sources=new Map();for(const row of rows)if(row.kind==='source.open')sources.set(row.object.id,{...graphReference.source_descriptors.find(source=>source.artifact_id===row.object.id),...row.result});
  for(const fact of facts){const pin=ui.northStarPin(fact,sources);assert.ok(pin,'fact has a verified original source locator');assert.equal(pin.quote,Array.from(sources.get(pin.artifact_id).text).slice(pin.start_char,pin.end_char).join(''));assert.ok(fact.seq<=completion.seq);}
  const byId=new Map(actual.rows.map(row=>[row.id,row]));
  for(const row of plan)assert.deepEqual(row.operation,byId.get(row.operation.id),'plan operation exactly matches the verified actual live history');
  if(new Set(facts.map(row=>row.object.id)).size>=2)candidates.push({beat,completion,plan,facts,trace:actual,graph_source:'fresh served claim state, atomic saved journal and production-validated recorded operation/checkpoint chain'});
 }
 assert.ok(candidates.length,'one accepted process question uses several recorded facts');
 const selected=candidates[0],state5=await capture(5,'accepted-question',selected.beat,selected.beat.end-1);
 assert.ok(state5.observed.done_nodes.some(row=>row.node_id===selected.completion.object.id));
 assert.ok(manifest.beats.some(row=>row.operation===selected.beat.operation&&row.phase==='plan-recede'&&row.end<=selected.beat.start));
 state5.recorded_relationship={graph_source:selected.graph_source,admitted_state_sha256:manifest.stateHashes[manifest.claims.indexOf(selected.beat.claim)],completion_operation:selected.completion.id,node_id:selected.completion.object.id,trace_url:selected.trace.url,trace_sha256:selected.trace.sha256,fact_count:new Set(selected.facts.map(row=>row.object.id)).size,fact_extract_operations_count:selected.facts.length,facts:selected.facts.map(row=>({operation_id:row.id,fact_id:row.object.id,sequence:row.seq,source:row.source})),plan_operations:selected.plan.map(row=>({id:row.operation.id,sequence:row.operation.seq,kind:row.operation.kind}))};
 state5.presentation_choice='Preserved W10/W11 sequential presentation: only the current source-matched fact is visible; prior contributing facts remain in recorded history. This still does not show simultaneous multiple fact cards.';
 const chain=choose('decision','chain-rest',row=>row.column==='facts'),state6=await capture(6,'completed-process',chain,chain.end-1);assert.ok(state6.observed.completed_process);assert.ok(state6.observed.local_chain_columns.length);
 const qaPath=path.join(NS,'sealed-browser/receipt.json'),qa=read(qaPath);assert.equal(qa.status,'passed');assert.deepEqual(qa.browser_errors,[]);assert.deepEqual(qa.unexpected_destinations,[]);assert.equal(digest(qaPath),helperBinding.sealed_browser_receipt_sha256);assert.equal(digest(qaPath),sealed.artifact_hashes['receipt.json']);
 for(const [number,name,original,evidence]of [[7,'direct-edit','source-review.png',qa.stages.filter(row=>['new-prerequisite','resolution-dependency','saved-version'].includes(row.stage))],[8,'later-case-reuse','later-case-reuse.png',qa.stages.filter(row=>row.stage==='later-case-application')]]){
  assert.ok(evidence.length);const source=path.join(NS,'sealed-browser',original);assert.equal(digest(source),sealed.artifact_hashes[original]);const filename='state-'+number+'-'+name+'.png',dest=path.join(OUT,filename);fs.copyFileSync(source,dest,fs.constants.COPYFILE_EXCL);
  report.states.push({state:number,name,file:filename,capture_kind:'Byte-identical screenshot from the actual sealed isolated operator browser run',claim_id:number===7?'clm_f69b1747447bc221':'clm_0e538990cc6ba7ef',actor:'Test handler — engineering QA',capture_scope:number===7?'Accepted source graph after direct edits and fragment save; actual preview/acceptance continuity is in the event receipt and video.':'Receiving-case exact version and current consequence after accepted application.',source_receipt_sha256:digest(path.join(NS,'sealed-browser/receipt.json')),recorded_events:evidence,qualified_human_approval:false,...checkPNG(dest)});
 }
 assert.equal(report.live_trace_validations.length,manifest.claims.length);assert.equal(report.states.length,8);assert.deepEqual(report.errors,[]);assert.deepEqual(report.writes,[]);
 assert.equal(git('rev-parse','HEAD'),SHA);assert.equal(git('status','--porcelain'),'');report.status='passed';
}catch(error){report.status='failed';report.failure=String(error.stack||error);throw error;}
finally{
 report.cleanup=[];
 for(const [name,owned]of [['context',context],['browser',browser]]){if(!owned)continue;let timer;try{await Promise.race([owned.close(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error(name+' close timed out')),10000);})]);report.cleanup.push({name,status:'closed'});}catch(error){report.cleanup.push({name,status:'failed',error:String(error)});report.status='failed';process.exitCode=1;}finally{clearTimeout(timer);}}
 report.finished_at=new Date().toISOString();persist();
}
console.log(JSON.stringify({status:report.status,source_commit:SHA,states:report.states.length,multi_fact_count:report.states.find(row=>row.state===5)?.recorded_relationship?.fact_count,qualified_human_approval:'pending'}));

