const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const {execFileSync}=require('node:child_process'),{createHash}=require('node:crypto');
const repo='/workspace/casepath-map-first-review-20261015',rootRepo='/workspace/casepath-map-first-stage-20261015';
const before='7677fe8f86b61bab3ad73204af5d886afe1e4e11',candidate='2908c2dedeb82bc45a969d65e3c956b57c8c21fe',integrated='1b493f3cbaae18131751c015c5d428fd32911932';
const js='casepath/assets/autonomous-workspace-v1.js',css='casepath/assets/autonomous-workspace-v1.css';
const get=(commit,file,cwd=repo)=>execFileSync('git',['show',commit+':'+file],{cwd});
const sha=value=>createHash('sha256').update(value).digest('hex');
const old=get(before,js).toString(),source=get(candidate,js).toString(),combined=get(integrated,js,rootRepo).toString();
const helper=source.slice(source.indexOf('  async function operationFrameYield('),source.indexOf('  function checkedOperationBinding('));
const budgetLine='        const frameBudget = {started:root.performance?.now?.() ?? Date.now()};\n';
const callLine='          if (!await operationFrameYield(frameBudget,root,() => operationActive(session,token) && operationTrace === trace,() => operationGate(session,token))) return;\n';
for(const text of [helper,budgetLine,callLine])assert.equal(source.split(text).length,2,'exactly one expected insertion');
const stripped=source.replace(helper,'').replace(budgetLine,'').replace(callLine,'').replace('return {operationFrameYield,claimFragment','return {claimFragment');
assert.equal(stripped,old,'all pre-existing production JS bytes remain identical after removing exactly four yield insertions');
assert.equal(combined,source,'integrated root JS equals immutable writer JS');
assert.equal(sha(get(before,css)),sha(get(candidate,css)),'CSS unchanged');
assert.equal(sha(get(candidate,css)),sha(get(integrated,css,rootRepo)),'integrated CSS identical');
const uiModule=new Module(path.join(repo,'immutable-task-yield.js'),module);uiModule.filename=path.join(repo,'immutable-task-yield.js');uiModule.paths=module.paths;uiModule._compile(source,uiModule.filename);const ui=uiModule.exports;
const gateSource=source.slice(source.indexOf('    function operationActive(session, token)'),source.indexOf('    function skipOperations()'));
const factory=new Function('runtime','document',`
  const root=runtime,doc=document,session={claimId:'case-a',skip:false,operationController:new AbortController()};
  const token=7,trace={};let operationTrace=trace,disposed=false,epoch=token,pending=false,view='claim',current={claim_id:'case-a'},demoSession=session,inspectionHold=false,demoTimer=null;
  const dialog={open:false},recordDialog={open:false},reduced={matches:false};function pendingRoute(){return pending;}
  ${gateSource}
  return {session,active:()=>operationActive(session,token)&&operationTrace===trace,gate:()=>operationGate(session,token),
    set(name,value){if(name==='pause')demoSession=value?null:session;else if(name==='hidden')doc.hidden=value;else if(name==='inspection')inspectionHold=value;else if(name==='dialog')dialog.open=value;else if(name==='recordDialog')recordDialog.open=value;else if(name==='skip')session.skip=value;else if(name==='reduced')reduced.matches=value;else if(name==='abort')session.operationController.abort();else if(name==='stale')epoch++;else if(name==='route')pending=value;else if(name==='disposed')disposed=value;else if(name==='owner')operationTrace=value?{}:trace;else if(name==='claim')current={claim_id:value};else throw new Error(name);},
    wake(){session.operationWake?.();},waiting(){return typeof session.operationWake==='function';}};
`);
const turn=()=>new Promise(resolve=>setImmediate(resolve));
const rows=[];
async function holdTest(kind,fallback=false){
  let releaseTask,taskCount=0,taskDelay=null,completed=false,clock=10;
  const runtime={performance:{now:()=>clock},clearTimeout(){},setTimeout(resolve,delay){taskCount++;taskDelay=delay;releaseTask=resolve;}};
  if(!fallback)runtime.scheduler={yield(){taskCount++;return new Promise(resolve=>{releaseTask=resolve;});}};
  const gate=factory(runtime,{hidden:false}),budget={started:0};
  const promise=ui.operationFrameYield(budget,runtime,gate.active,gate.gate).then(value=>{completed=true;return value;});
  assert.equal(taskCount,1);assert.equal(completed,false);gate.set(kind,true);releaseTask();await turn();
  assert.equal(completed,false,kind+' must hold the continuation after the task');assert.equal(gate.waiting(),true);
  clock=31;gate.set(kind,false);gate.wake();assert.equal(await promise,true);assert.equal(budget.started,31,'gate wait excluded from next work budget');
  rows.push({case:kind+(fallback?'-fallback':''),held_after_task:true,resumed_after_actual_gate:true,task_delay:fallback?taskDelay:null});
}
async function cancelTest(kind,whileGated=false){
  let releaseTask,tasks=0,gates=0;const runtime={performance:{now:()=>10},scheduler:{yield(){tasks++;return new Promise(resolve=>{releaseTask=resolve;});}},clearTimeout(){}};
  const gate=factory(runtime,{hidden:false}),budget={started:0};
  const promise=ui.operationFrameYield(budget,runtime,gate.active,async()=>{gates++;return gate.gate();});
  if(whileGated){gate.set('inspection',true);releaseTask();await turn();assert.equal(gate.waiting(),true);gate.set(kind,kind==='claim'?'case-b':true);gate.wake();}
  else{gate.set(kind,kind==='claim'?'case-b':true);releaseTask();}
  assert.equal(await promise,false);assert.equal(tasks,1);assert.equal(gates,whileGated?1:0);assert.equal(budget.started,0);
  rows.push({case:kind+(whileGated?'-during-gate':'-during-task'),continued:false,gates});
}
(async()=>{
  for(const kind of ['pause','hidden','inspection','dialog','recordDialog'])await holdTest(kind);
  await holdTest('inspection',true);
  for(const kind of ['abort','stale','route','disposed','owner','claim'])await cancelTest(kind);
  for(const kind of ['abort','stale','route','disposed','claim'])await cancelTest(kind,true);
  for(const mode of ['skip','reduced']){
    let tasks=0;const runtime={performance:{now:()=>10},scheduler:{async yield(){tasks++;}},setTimeout(){assert.fail('no presentation dwell added');},clearTimeout(){}};
    const gate=factory(runtime,{hidden:false});gate.set(mode,true);if(mode==='skip'){gate.set('pause',true);gate.set('hidden',true);gate.set('inspection',true);}
    assert.equal(await ui.operationFrameYield({started:0},runtime,gate.active,gate.gate),true);assert.equal(tasks,1);rows.push({case:mode,verified_processing_continues:true,presentation_timer_count:0});
  }
  let tasks=0,gates=0;const runtime={performance:{now:()=>9.99},scheduler:{async yield(){tasks++;}}};
  assert.equal(await ui.operationFrameYield({started:0},runtime,()=>true,async()=>{gates++;return true;}),true);assert.equal(tasks,0);assert.equal(gates,0);
  assert.equal(await ui.operationFrameYield({started:0},{...runtime,performance:{now:()=>10}},()=>false,async()=>true),false);assert.equal(tasks,0);
  const failure=new Error('task rejected');await assert.rejects(ui.operationFrameYield({started:0},{performance:{now:()=>10},scheduler:{async yield(){throw failure;}}},()=>true,async()=>true),error=>error===failure);
  rows.push({case:'budget-and-task-failure',below_10ms_no_task:true,inactive_no_task:true,rejection_propagates_to_existing_outer_catch:true});
  const start=source.indexOf('    async function startOperations('),end=source.indexOf('    function presentationFailed(',start),loop=source.slice(start,end);
  assert.equal(loop.split('operationFrameYield(').length,2);assert.ok(loop.indexOf('await checkedOperation(frame')<loop.indexOf(callLine));assert.ok(loop.indexOf('await checkedOperationCheckpoint(frame')<loop.indexOf(callLine));assert.ok(loop.indexOf("else throw new Error('The operation stream contains an unknown frame.')")<loop.indexOf(callLine));
  const oldMount=old.slice(old.indexOf('    async function startOperations('),old.indexOf('    function presentationFailed('));assert.equal(loop.replace(budgetLine,'').replace(callLine,''),oldMount);
  console.log(JSON.stringify({status:'PASS: no introduced blocking correctness finding in bounded immutable yield delta',writer_commit:candidate,writer_parent:before,integrated_root_commit:integrated,javascript_sha256:sha(source),css_sha256:sha(get(candidate,css)),review_checkout:'local no-checkout clone; immutable Git objects only',preexisting_production_js_identical_after_exact_yield_insertions_removed:true,native_validators_crypto_order_source_authority_and_existing_lifecycle_bytes_unchanged:true,common_yield_only_after_complete_verified_binding_operation_or_checkpoint:true,result_error_unknown_and_rejected_frames_exit_before_yield:true,integrated_assets_identical:true,focused_cases:rows,limits:['No product or test writes; this artifact exercises immutable exported helper with exact production operationActive/operationGate source.','No browser, rendering, native fixture replay, network, provider, production2.0 or performance acceptance claim in this check. Existing native receipts remain applicable because their validators and authority code are byte-identical.','Ten milliseconds is a between-frame budget, not a cap on an individual hash, checkpoint, operation or render. scheduler.yield rejection propagates to the unchanged stream failure handling.']},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
