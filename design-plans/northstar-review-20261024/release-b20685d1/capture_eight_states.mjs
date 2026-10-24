import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {gunzipSync} from 'node:zlib';
import {execFileSync} from 'node:child_process';
const ROOT="/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-northstar-20261024";
const NS=path.join(ROOT,'.runtime/commander-northstar'),BASE=path.join(NS,'release'),OUT=path.join(BASE,'eight-state-capture');
const SHA='b20685d1670b33b941b1bfcb902638a879c01b93',SITE='https://casepath-autonomous.kumarnavish.chatgpt.site';
const require=createRequire('/Users/kumar0002/Documents/Die Mobiliar/casepath-canonical/casepath-qa/package.json'),{chromium}=require('playwright'),ui=require(path.join(ROOT,'casepath/assets/autonomous-workspace-v1.js'));
const read=p=>JSON.parse(fs.readFileSync(p,'utf8')),hash=b=>createHash('sha256').update(b).digest('hex'),digest=p=>hash(fs.readFileSync(p));
const fixturePath=path.join(ROOT,'casepath-qa/fixtures/desk-v3.json.gz'),fixture=JSON.parse(gunzipSync(fs.readFileSync(fixturePath)));
const git=(...args)=>execFileSync('/usr/bin/git',args,{cwd:ROOT,encoding:'utf8'}).trim();
assert.equal(git('rev-parse','HEAD'),SHA);assert.equal(git('status','--porcelain'),'');
assert.equal(read(path.join(BASE,'published-acceptance-sequence.json')).status,'passed');
const gate=read(path.join(BASE,'full-gate-verified.json'));assert.equal(gate.canonical_commit,SHA);assert.equal(gate.exit_code,0);
assert.ok(fs.existsSync(path.join(BASE,'gate-actual-completion.json')));
const sealed=read(path.join(NS,'sealed-browser-command.json'));assert.equal(sealed.source_commit,SHA);assert.equal(sealed.status,'passed');
assert.equal(fs.existsSync(OUT),false);fs.mkdirSync(OUT);
const report={contract:'casepath.eight-state-engineering-evidence/1',source_commit:SHA,started_at:new Date().toISOString(),viewport:{width:1440,height:900},states:[],errors:[],writes:[],edge_beacons:[],fixture_graph_reference_sha256:digest(fixturePath),assets:{},coverage_scope:'Recorded source-to-process journey plus isolated Test handler edit, versioning and later-case reuse',qualified_human_approval:'pending',literal_state_8_expert_review_acceptance:false,claim_outcome_authorized:false};
let browser,context,page;
const traceReads=[],traces=new Map(),states=new Map();
report.trace_reads=[];
async function setup(){
browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
context=await browser.newContext({viewport:report.viewport,serviceWorkers:'block',reducedMotion:'no-preference',deviceScaleFactor:1});page=await context.newPage();
page.on('response',response=>{
 const url=new URL(response.url()),match=url.pathname.match(/\/claims\/([^/]+)\/operations$/);
 if(match){report.trace_reads.push({claim_id:match[1],url:url.href,status:response.status()});if(response.status()===200)traceReads.push((async()=>{const body=await response.text(),rows=body.trim().split('\n').filter(Boolean).map(JSON.parse).filter(row=>row.type==='operation');assert.ok(rows.length);traces.set(match[1],{url:url.href,sha256:hash(body),rows});})().catch(error=>report.errors.push('trace read: '+error.message)));}
 const claim=url.pathname.match(/\/api\/claim-loops\/v1\/autonomous\/claims\/([^/]+)$/);
 if(claim&&response.status()===200)traceReads.push((async()=>{const body=await response.json();if(body.state?.graph)states.set(claim[1],body.state);})().catch(error=>report.errors.push('claim read: '+error.message)));
});
page.on('pageerror',error=>report.errors.push(error.message));
page.on('console',message=>{if(message.type()==='error')report.errors.push(message.text());});
await page.route('**/*',route=>{const request=route.request(),url=new URL(request.url());if(['GET','HEAD'].includes(request.method()))return route.continue();if(url.origin===SITE&&url.pathname.startsWith('/cdn-cgi/')){report.edge_beacons.push(request.method()+' '+url.pathname);return route.continue();}report.writes.push(request.method()+' '+url.origin+url.pathname);return route.abort();});
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
 report.states.push(row);return row;
}
try{
 await setup();
 const deploymentResponse=await context.request.get(SITE+'/deployment.json',{headers:{'Cache-Control':'no-cache'}});assert.equal(deploymentResponse.status(),200);report.deployment=await deploymentResponse.json();assert.equal(report.deployment.source_commit,SHA);
 for(const asset of ['autonomous-workspace-v1.js','autonomous-workspace-v1.css','autonomous-presentation-v1.js','autonomous-language-v1.js','fonts/Mulish.ttf']){
  const response=await context.request.get(SITE+'/assets/'+asset);assert.equal(response.status(),200);const bytes=await response.body();assert.equal(hash(bytes),digest(path.join(ROOT,'casepath/assets',asset)));report.assets[asset]=hash(bytes);
 }
 await page.goto(SITE+'/#autonomous/demonstration',{waitUntil:'domcontentloaded'});
 await page.locator('[data-au-ns-start]').waitFor({timeout:90000});await page.waitForFunction(()=>window.CasepathPresentation?.active,undefined,{timeout:90000});await page.evaluate(()=>document.fonts.ready);
 const manifest=await page.evaluate(()=>CasepathPresentation.active.manifest);report.manifest=manifest;assert.equal(manifest.duration,88050);
 const ready=await capture(1,'ready',manifest.beats[0],null);assert.ok(ready.observed.start_control_visible);assert.equal(ready.observed.time,0);
 const choose=(act,phase,extra=()=>true)=>{const beat=manifest.beats.find(row=>row.act===act&&row.phase===phase&&extra(row));assert.ok(beat,act+'/'+phase);return beat;};
 const opened=choose('reading','camera-in');const state2=await capture(2,'source-opened',opened,opened.end-1);assert.ok(state2.observed.source_open);assert.equal(state2.observed.quote.ink_opacity,0);
 const passage=choose('reading','passage-rest');const state3=await capture(3,'exact-passage',passage,passage.end-1);const q=state3.observed.quote,pin=state3.observed.source_pin;assert.ok(pin);assert.equal(q.text,pin.quote);assert.equal(q.start,pin.start_char);assert.equal(q.end,pin.end_char);assert.ok(q.ink_opacity>0);
 const fact=choose('reading','fact-rest');const state4=await capture(4,'source-bound-fact',fact,fact.end-1);assert.ok(state4.observed.visible_facts.length);assert.deepEqual(state4.observed.visible_facts.at(-1).citation,state4.observed.source_pin);assert.deepEqual(state2.observed.source_pin,state3.observed.source_pin);assert.deepEqual(state3.observed.source_pin,state4.observed.source_pin);
 await Promise.all(traceReads);
 const factTrace=traces.get(state4.claim_id);assert.ok(factTrace,'the depicted fact has an actual recorded trace');
 for(const visible of state4.observed.visible_facts){const operation=factTrace.rows.find(row=>row.id===visible.operation);assert.equal(operation?.kind,'fact.extract');assert.deepEqual(visible.citation,operation.source);}
 assert.equal(state4.observed.visible_facts.at(-1).operation,state4.beat.operation);assert.equal(state3.beat.operation,state4.beat.operation);
 const candidates=[];
 for(const beat of manifest.beats.filter(row=>row.phase==='node-rest'&&['reading','process'].includes(row.act))){
  const actual=traces.get(beat.claim),reference=fixture.cases.find(row=>row.id===beat.claim);assert.ok(actual&&reference,'actual recorded trace and frozen graph exist');
  const rows=actual.rows,completion=rows.find(row=>row.id===beat.operation);assert.equal(completion?.kind,'step.complete');assert.equal(completion.result.status,'completed');
  const graphReference=states.get(beat.claim)||reference.envelope.state,model=ui.northStarPlanModel(graphReference,rows),plan=model.plans.get(completion.object.id),facts=plan.filter(row=>row.operation.kind==='fact.extract').map(row=>row.operation);
  assert.equal(graphReference.state_sha256,manifest.stateHashes[manifest.claims.indexOf(beat.claim)],'graph state matches the admitted presentation hash');
  const sources=new Map();for(const row of rows)if(row.kind==='source.open')sources.set(row.object.id,{...graphReference.source_descriptors.find(source=>source.artifact_id===row.object.id),...row.result});
  for(const fact of facts){const pin=ui.northStarPin(fact,sources);assert.ok(pin,'fact has a verified original source locator');assert.equal(pin.quote,Array.from(sources.get(pin.artifact_id).text).slice(pin.start_char,pin.end_char).join(''));assert.ok(fact.seq<=completion.seq);}
  const originalRows=reference.trace.trim().split('\n').map(JSON.parse).filter(row=>row.type==='operation'),byId=new Map(originalRows.map(row=>[row.id,row]));
  for(const row of plan)assert.deepEqual(row.operation,byId.get(row.operation.id),'actual operation matches the frozen recorded reference');
  if(new Set(facts.map(row=>row.object.id)).size>=2)candidates.push({beat,completion,plan,facts,trace:actual,graph_source:states.has(beat.claim)?'actual served claim state':'frozen graph reference with actual operation equality'});
 }
 assert.ok(candidates.length,'one accepted process question uses several recorded facts');
 const selected=candidates[0],state5=await capture(5,'accepted-question',selected.beat,selected.beat.end-1);
 assert.ok(state5.observed.done_nodes.some(row=>row.node_id===selected.completion.object.id));
 assert.ok(manifest.beats.some(row=>row.operation===selected.beat.operation&&row.phase==='plan-recede'&&row.end<=selected.beat.start));
 state5.recorded_relationship={graph_source:selected.graph_source,admitted_state_sha256:manifest.stateHashes[manifest.claims.indexOf(selected.beat.claim)],completion_operation:selected.completion.id,node_id:selected.completion.object.id,trace_url:selected.trace.url,trace_sha256:selected.trace.sha256,fact_count:new Set(selected.facts.map(row=>row.object.id)).size,fact_extract_operations_count:selected.facts.length,facts:selected.facts.map(row=>({operation_id:row.id,fact_id:row.object.id,sequence:row.seq,source:row.source})),plan_operations:selected.plan.map(row=>({id:row.operation.id,sequence:row.operation.seq,kind:row.operation.kind}))};
 state5.presentation_choice='Preserved W10/W11 sequential presentation: only the current source-matched fact is visible; prior contributing facts remain in recorded history. This still does not show simultaneous multiple fact cards.';
 const chain=choose('decision','chain-rest',row=>row.column==='facts'),state6=await capture(6,'completed-process',chain,chain.end-1);assert.ok(state6.observed.completed_process);assert.ok(state6.observed.local_chain_columns.length);
 const qa=read(path.join(NS,'sealed-browser/receipt.json'));assert.equal(qa.status,'passed');
 for(const [number,name,original,evidence]of [[7,'direct-edit','source-review.png',qa.stages.filter(row=>['new-prerequisite','resolution-dependency','saved-version'].includes(row.stage))],[8,'later-case-reuse','later-case-reuse.png',qa.stages.filter(row=>row.stage==='later-case-application')]]){
  const source=path.join(NS,'sealed-browser',original);assert.equal(digest(source),sealed.artifact_hashes[original]);const filename='state-'+number+'-'+name+'.png',dest=path.join(OUT,filename);fs.copyFileSync(source,dest,fs.constants.COPYFILE_EXCL);
  report.states.push({state:number,name,file:filename,capture_kind:'Byte-identical screenshot from the actual sealed isolated operator browser run',claim_id:number===7?'clm_f69b1747447bc221':'clm_0e538990cc6ba7ef',actor:'Test handler — engineering QA',capture_scope:number===7?'Accepted source graph after direct edits and fragment save; actual preview/acceptance continuity is in the event receipt and video.':'Receiving-case exact version and current consequence after accepted application.',source_receipt_sha256:digest(path.join(NS,'sealed-browser/receipt.json')),recorded_events:evidence,qualified_human_approval:false,...checkPNG(dest)});
 }
 assert.equal(report.states.length,8);assert.deepEqual(report.errors,[]);assert.deepEqual(report.writes,[]);
 assert.equal(git('rev-parse','HEAD'),SHA);assert.equal(git('status','--porcelain'),'');report.status='passed';
}catch(error){report.status='failed';report.failure=String(error.stack||error);throw error;}
finally{
 report.cleanup=[];
 for(const [name,owned]of [['context',context],['browser',browser]]){if(!owned)continue;let timer;try{await Promise.race([owned.close(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error(name+' close timed out')),10000);})]);report.cleanup.push({name,status:'closed'});}catch(error){report.cleanup.push({name,status:'failed',error:String(error)});report.status='failed';process.exitCode=1;}finally{clearTimeout(timer);}}
 report.finished_at=new Date().toISOString();fs.writeFileSync(path.join(OUT,'eight-state-evidence.json'),JSON.stringify(report,null,2)+'\n');
}
console.log(JSON.stringify({status:report.status,source_commit:SHA,states:report.states.length,multi_fact_count:report.states.find(row=>row.state===5)?.recorded_relationship?.fact_count,qualified_human_approval:'pending'}));
