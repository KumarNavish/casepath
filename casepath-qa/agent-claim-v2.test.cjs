'use strict';
const test = require('node:test'), assert = require('node:assert/strict');
const ui = require('../casepath/assets/agent-claim-v2.js');
const question = (extra = {}) => ({question_id:'condition:family_home', kind:'condition', prompt:'Does the family-home condition apply?', why:'Separate service depends on this answer.', decider:'M. Keller', previewable:true, proposal:{answer_id:'true', reason:'The message reports a shared family home.'}, counter_reading:'The message may describe an earlier household.', answers:[{answer_id:'true', label:'Yes, it applies'}, {answer_id:'false', label:'No, it does not apply'}, {answer_id:'unresolved', label:'Keep it unresolved'}], sources:[{artifact_id:'message', quote:'We live here as a family.', start:9, end:34, page:1}], ...extra});
const model = (id, extra = {}) => ({claim:{claim_id:id, owner:'M. Keller'}, agent:{contract:'casepath.agent-desk-claim/1.0.0', claim_id:id, workspace_revision:7, workspace_state_sha256:'state-seven', agent_revision:2, agent_state_sha256:'agent-two', owner:{accountable:'M. Keller', delegate:'CasePath agent'}, mandate:{unattended:['Read bound sources', 'Prepare requests'], requires_handler:['Change the working process', 'Any action leaving CasePath']}, state:'waiting_for_you', questions:[question()], activity:[], coverage:{total_sources:3, read_sources:1, unreadable_sources:1, unread_sources:2, arrived_since:null, limited_sources:[{artifact_id:'scan', label:'Notice scan', reason:'Page 2 has no readable text.'}], note:'Only extracted text was read.'}, learning:{fragments:[], memories:[], uses:[], automatic_learning:false}, ...extra}, sources:[{artifact_id:'message', filename:'Customer message'}]});
function rootFor(id) {
  const listeners = new Map();
  return {listeners, isConnected:true, innerHTML:'', marker:{dataset:{avClaim:id}},
    querySelector(selector) {return selector === '[data-av-claim]' ? this.marker : {focus(){},scrollIntoView(){}};},
    contains(){return true;}, addEventListener(type, listener){listeners.set(type, listener);},
    removeEventListener(type, listener){if (listeners.get(type) === listener) listeners.delete(type);}
  };
}
const button = (name, value = '') => ({dataset:{[name]:value}, hasAttribute(attr){return attr === 'data-' + name.replace(/[A-Z]/g, c => '-' + c.toLowerCase());}, closest(){return this;}});
function formFor(answer = 'true', reason = '') {
  return {dataset:{avDecision:'condition:family_home'}, elements:{answer_id:{value:answer}, actor:{value:'M. Keller'}, reason:{value:reason}}, matches(){return true;}, hasAttribute(attr){return attr === 'data-av-decision';}};
}
const settle = async () => {await new Promise(resolve => setImmediate(resolve));};

test('external stop describes an in-flight request and only a sealed clear-pause flag offers mandate resume', () => {
  const run={run_id:'work.external',facts_worker:'external_facts',status:'running',pending_calls:[],provider_requests:1};
  assert.match(ui.render(model('external-stop-label',{state:'working',run})),/data-av-control="pause">Stop after current request/);
  assert.match(ui.render(model('external-stopping-label',{state:'working',pause_requested:true,run})),/Stopping after current request/);
  const safe=model('external-mandate-label',{state:'paused',pause_requested:true,can_clear_external_pause:true,run:{...run,status:'completed'}});
  assert.match(ui.render(safe),/data-av-control="resume">Resume delegate/);
  safe.agent.can_clear_external_pause=false;
  assert.doesNotMatch(ui.render(safe),/data-av-control="resume"/);
  assert.match(ui.render(safe),/Inspect recorded work/);
});
const verifier = async (value, field, contract) => {assert.equal(value.contract, contract); assert.ok(value[field], `missing ${field}`);};
function previewFor(input) {return {contract:'casepath.agent-decision-preview/1.0.0', response_sha256:'preview-envelope', preview_sha256:'preview-identity', causal:{contract:'casepath.causal-process-preview/1.0.0', preview_sha256:'causal-engine-identity', claim_id:input.claim.claim_id, workspace_revision:7, workspace_state_sha256:'state-seven'}, claim_id:input.claim.claim_id, workspace_revision:7, workspace_state_sha256:'state-seven', question:input.agent.questions[0], answer_id:'false', reason:'The household moved out.', graph:{nodes:[], document_catalog:[]}, impact:{changed_document_types:['spouse_notice'], unchanged_document_types:['lease']}};}

test('accountability, mandate and native bounded decision are visible before interaction', () => {
  const html = ui.render(model('native'));
  assert.match(html, /Accountable handler <strong>M\. Keller<\/strong>/);
  assert.match(html, /CasePath agent<\/h2><span class="av-delegate">Delegated agent/);
  assert.match(html, /Waiting for you/); assert.match(html, /Works unattended/); assert.match(html, /Waits for your approval/);
  assert.match(html, /<fieldset class="av-answer-list"><legend>Choose your answer/);
  assert.match(html, /type="radio" name="answer_id" value="true" checked required/);
  assert.match(html, /Agent proposal/); assert.match(html, /Counter-reading/); assert.match(html, /data-av-source="0"/);
  assert.match(html, /<small class="av-proposal-label">Agent proposal · not saved<\/small>/);
  assert.match(html, /<span>Agent reading:<\/span> The message reports a shared family home\./);
  assert.match(html, /<span>Counter-reading:<\/span> The message may describe an earlier household\./);
  assert.match(html, /Preview is read-only\. Nothing is saved yet\./);
  assert.doesNotMatch(html, /confidence|spinner|typing|<h1/);
});

test('the handler mandate keeps its disclosure state when recorded work updates', () => {
  const input = model('mandate-poll'), root = rootFor('mandate-poll');ui.render(input);ui.bind({root});
  root.listeners.get('toggle')({target:{dataset:{avDisclosure:'mandate'},open:true}});
  input.agent = {...input.agent, agent_revision:3, activity:[{type:'SOURCE_OPENED',label:'A recorded source was read.'}]};
  let html=ui.render(input);
  assert.match(html, /class="av-mandate" data-av-disclosure="mandate" open><summary id="avMandateSummary">Agent mandate/);
  assert.match(html, /A recorded source was read/);
  root.listeners.get('toggle')({target:{dataset:{avDisclosure:'mandate'},open:false}});
  html=ui.render(input);assert.match(html, /class="av-mandate" data-av-disclosure="mandate"><summary id="avMandateSummary">/);
});

test('the first view distinguishes completed earlier work, current coverage and a current draft ask', () => {
  const input=model('work-summary',{run:{completed_roles:6,role_count:6,currentness:'historical'},questions:[question({kind:'draft_approval',draft:{body_markdown:'Please provide the receipt.'}})]});
  input.agent.coverage={scope:'original_bound_intake',read_sources:1,total_sources:1};
  const html=ui.render(input),header=html.slice(0,html.indexOf('</header>'));
  assert.match(header,/Earlier review · 6\/6 roles finished · 1\/1 original sources read/);
  assert.match(header,/Draft awaits review · not sent/);assert.doesNotMatch(header,/Current review/);
  input.agent={...input.agent,state:'working',run:{completed_roles:0,role_count:6,currentness:'current'},questions:[]};
  const current=ui.render(input).slice(0,ui.render(input).indexOf('</header>'));
  assert.match(current,/Current review · 0\/6 roles finished/);assert.doesNotMatch(current,/Draft awaits review|Earlier review/);
});

test('control labels distinguish an active stop from pausing the delegate awaiting the handler', () => {
  assert.match(ui.render(model('waiting-control')),/data-av-control="pause">Pause delegate/);
  assert.match(ui.render(model('working-control',{state:'working'})),/data-av-control="pause">Stop agent/);
  assert.match(ui.render(model('paused-control',{state:'paused'})),/data-av-control="resume">Resume agent/);
});

test('signed execution uncertainty shows its recovery ask and opens recorded work instead of offering an unsafe resume', () => {
  const ask='Inspect the unfinished operation and reconcile its outcome before retrying.';
  const input=model('execution-uncertain',{state:'unknown',recovery_required:true,recovery_ask:ask,questions:[],run:{run_id:'work.interrupted',status:'interrupted',facts_worker:'reference',recovery:{can_resume:false,reason:'pending_tool_call'}}});
  const root=rootFor('execution-uncertain'),opened=[];
  const html=ui.render(input),header=html.slice(0,html.indexOf('</header>'));
  assert.match(header,/data-state="unknown">Recovery needed<\/span>/);
  assert.match(header,/class="av-recovery-ask">Inspect the unfinished operation/);
  assert.match(header,/data-av-pane="trace">Inspect recorded work/);
  assert.doesNotMatch(header,/Not yet checked|data-av-control|Resume agent|Retry review/);
  assert.match(html,/<h3>Recovery needed<\/h3><p>Inspect the unfinished operation/);
  assert.match(html,/data-av-pane="trace">Inspect full review/);
  ui.bind({root,onOpenPane:page=>opened.push(page)});root.listeners.get('click')({target:button('avPane','trace')});
  assert.deepEqual(opened,['trace']);assert.equal(input.agent.state,'unknown');assert.equal(ui.session('execution-uncertain').pending,null);
  input.agent.owner.accountable=null;input.claim.owner=null;
  assert.match(ui.render(input),/data-edit-owner>Assign handler/);assert.match(ui.render(input),/data-av-pane="trace">Inspect recorded work/);
  input.agent.recovery_ask='<img src=x onerror="alert(1)">';
  assert.doesNotMatch(ui.render(input),/<img|onerror="alert/);assert.match(ui.render(input),/&lt;img/);
});

test('only a resumable reference checkpoint offers recovery Resume while unstarted unknown remains a retry', () => {
  const checkpoint={run_id:'work.safe',status:'interrupted',facts_worker:'reference',recovery:{can_resume:true}};
  const input=model('safe-recovery',{state:'unknown',recovery_required:true,recovery_ask:'Review the saved checkpoint before resuming the interrupted review.',questions:[],run:checkpoint});
  assert.match(ui.render(input),/data-av-control="resume">Resume agent/);
  input.agent.run={...checkpoint,facts_worker:'external_facts'};
  assert.match(ui.render(input),/data-av-pane="trace">Inspect recorded work/);assert.doesNotMatch(ui.render(input),/data-av-control="resume"/);
  input.agent={...input.agent,state:'paused',recovery_required:false,recovery_ask:null,run:{...checkpoint,recovery:{can_resume:false}}};
  assert.match(ui.render(input),/data-av-pane="trace">Inspect recorded work/);assert.doesNotMatch(ui.render(input),/data-av-control="resume"/);
  const unstarted=ui.render(model('unstarted-recovery',{state:'unknown',questions:[],recovery_required:false,recovery_ask:null}));
  assert.match(unstarted,/data-state="unknown">Not yet checked/);assert.match(unstarted,/data-av-control="resume">Retry review/);assert.doesNotMatch(unstarted,/Recovery needed|Inspect recorded work/);
});

test('pausing a completed reference delegate can clear the saved mandate pause without restarting the completed run', async () => {
  const id='completed-mandate',run={run_id:'work.completed',status:'completed',facts_worker:'reference',provider_requests:0,pending_calls:[],recovery:{can_resume:false,reason:'not_resumable'}};
  const input=model(id,{state:'waiting_for_you',recovery_required:false,recovery_ask:null,pause_requested:false,run}),root=rootFor(id),requests=[];
  let latest={...input.agent,projection_sha256:'saved-work'};
  ui.render(input);ui.bind({root,api:{verify:verifier,request:async(path,options)=>{
    requests.push({path,options});if(options.method==='GET')return latest;
    const command=JSON.parse(options.body);
    latest={...latest,state:command.action==='pause'?'paused':'waiting_for_you',pause_requested:command.action==='pause',agent_revision:latest.agent_revision+1,agent_state_sha256:'delegate-'+command.action,projection_sha256:'projection-'+command.action};
    return {contract:'casepath.agent-control-result/1.0.0',projection_sha256:'control-'+command.action,agent:latest};
  }}});
  root.listeners.get('click')({target:button('avControl','pause')});await settle();
  assert.match(root.innerHTML,/data-av-control="resume">Resume agent/);assert.doesNotMatch(root.innerHTML,/Inspect recorded work/);
  assert.equal(ui.session(id).input.agent.run.run_id,run.run_id);assert.equal(ui.session(id).input.agent.run.recovery.can_resume,false);
  root.listeners.get('click')({target:button('avControl','resume')});await settle();
  assert.deepEqual(requests.map(r=>r.options.method),['GET','POST','GET','POST']);
  const commands=requests.filter(r=>r.options.method==='POST').map(r=>JSON.parse(r.options.body));
  assert.deepEqual(commands.map(c=>c.action),['pause','resume']);assert.equal(commands[1].expected_agent_revision,3);assert.equal(commands[1].actor,'M. Keller');
  assert.equal(ui.session(id).input.agent.pause_requested,false);assert.equal(ui.session(id).input.agent.run.run_id,run.run_id);assert.equal(ui.session(id).input.agent.run.status,'completed');
  assert.equal(ui.session(id).pending,null);assert.match(root.innerHTML,/data-av-control="pause">Pause delegate/);
});

test('a completed run with pending or provider uncertainty cannot use the mandate unpause exception', () => {
  const run={run_id:'work.completed',status:'completed',facts_worker:'reference',provider_requests:0,pending_calls:[],recovery:{can_resume:false}};
  for(const [index,change] of [{pending_calls:[{call_id:'unfinished'}]},{provider_requests:1},{facts_worker:'external_facts'},{status:'interrupted'}].entries()) {
    const html=ui.render(model('unsafe-mandate-'+index,{state:'paused',pause_requested:true,recovery_required:false,run:{...run,...change}}));
    assert.match(html,/data-av-pane="trace">Inspect recorded work/);assert.doesNotMatch(html,/data-av-control="resume"/);
  }
  const flagged=ui.render(model('uncertain-mandate',{state:'unknown',pause_requested:true,recovery_required:true,recovery_ask:'Inspect the saved execution outcome.',run}));
  assert.match(flagged,/data-av-pane="trace">Inspect recorded work/);assert.doesNotMatch(flagged,/data-av-control="resume"/);
});

test('the completed milestone uses plain display copy while preserving its recorded trace text', () => {
  const original='All six roles completed. Claim readiness remains governed by the existing authority.';
  const input=model('completed-copy',{activity:[{type:'RUN_COMPLETED',label:original}]});
  const html=ui.render(input);
  assert.match(html.slice(html.indexOf('class="av-activity"'),html.indexOf('class="av-trace"')),/Six review roles finished; findings need handler review/);
  assert.match(html.slice(html.indexOf('class="av-trace"')),/All six roles completed\. Claim readiness remains governed by the existing authority\./);
  assert.equal(input.agent.activity[0].label,original);
});

test('untrusted question, source, state note, draft and learning text cannot create markup', () => {
  const attack = '<img src=x onerror="alert(1)">', input = model('escape');
  input.agent.questions = [question({prompt:attack, counter_reading:attack, kind:'draft_approval', draft:{body_markdown:attack}, sources:[{artifact_id:attack, quote:attack}]})];
  input.agent.coverage.note = attack; input.agent.learning.memories = [{condition:attack, note:attack, handler:attack, source_quote:attack}];
  const html = ui.render(input);
  assert.doesNotMatch(html, /<img|onerror="alert/); assert.match(html, /&lt;img/); assert.match(html, /Draft, not sent|draft, not sent/);
  const empty = ui.render(model('empty-escape', {questions:[], next_action:attack}));
  assert.doesNotMatch(empty, /<img/);
});

test('coverage preserves unknown arrival counts and limits without inventing activity or a full trace', () => {
  const html = ui.render(model('coverage'));
  assert.match(html, /1 of 3 sources read/); assert.match(html, /Page 2 has no readable text/);
  assert.match(html, /<strong>Unknown<\/strong> arrived since/);
  assert.match(html, /No agent activity has been recorded/);
  assert.doesNotMatch(html, /Full recorded trace|6 of 6|0<\/strong> arrived since/);
  assert.match(html, /data-state="unreadable"/); assert.match(html, /data-state="held-not-reviewed"/);
});

test('overrides require a reason and unsupported answers cannot cross the request boundary', () => {
  const q = question(), agent = model('guard').agent;
  assert.throws(() => ui.decisionBody(q, 'false', 'M. Keller', '', agent), /why/);
  assert.throws(() => ui.decisionBody(q, 'settle', 'M. Keller', 'Because', agent), /recorded answers/);
  assert.throws(() => ui.decisionBody(q, 'true', '', '', agent), /reviewing handler/);
  assert.deepEqual(ui.decisionBody(q, 'false', ' M. Keller ', ' Moved out. ', agent), {question_id:q.question_id, answer_id:'false', actor:'M. Keller', reason:'Moved out.', expected_revision:7, expected_state_sha256:'state-seven'});
});

test('an answer previews first, then applies the same reviewed identity and refreshes the claim', async () => {
  const input = model('flow'), root = rootFor('flow'), requests = [], refreshed = [], checks = [], opened = [];
  global.CasePathCausal = require('../casepath/assets/causal-process-v1.js');
  ui.render(input);
  ui.bind({root, api:{verify:async (value, field, contract) => {checks.push({field, contract}); await verifier(value, field, contract);}, request:async (path, options) => {
    requests.push({path, options});
    if (path.endsWith('/preview')) return previewFor(input);
    input.agent = {...input.agent, workspace_revision:8, workspace_state_sha256:'state-eight'};
    ui.render(input); // A poll sees the accepted revision before this POST response reaches the UI.
    return {contract:'casepath.agent-decision-result/1.0.0', response_sha256:'saved', causal_result:{contract:'casepath.causal-process-result/1.0.0', result_sha256:'original-engine-receipt'}, agent:{...input.agent, projection_sha256:'agent-seal'}, process:{contract:'casepath.causal-process-view/1.0.0', claim_id:'flow', view_sha256:'process-seal'}};
  }}, refresh:async value => refreshed.push(value), onOpenSource:source => opened.push(source)});
  root.listeners.get('submit')({target:formFor('false', 'The household moved out.'), preventDefault(){}});
  await settle();
  assert.equal(requests.length, 1); assert.match(requests[0].path, /\/decisions\/preview$/);
  assert.match(root.innerHTML, /Apply decision/); assert.match(root.innerHTML, /What stays unchanged/);
  assert.match(root.innerHTML, /Apply saves your answer and resumes review\. Drafts stay unsent\./);
  assert.match(root.innerHTML, /<span>Your answer:<\/span> <strong>No, it does not apply<\/strong>/);
  assert.match(root.innerHTML, /<span>Your reason<\/span> The household moved out\./);
  assert.match(root.innerHTML, /<span>Agent reading:<\/span> The message reports a shared family home\./);
  assert.match(root.innerHTML, /<span>Counter-reading:<\/span> The message may describe an earlier household\./);
  assert.match(root.innerHTML, /<blockquote>We live here as a family\.<\/blockquote>/);
  assert.ok(root.innerHTML.indexOf('Your answer:') < root.innerHTML.indexOf('data-av-apply'));
  assert.match(root.innerHTML, /class="av-apply-context"><span>[^<]+<\/span><strong>Your answer: No, it does not apply<\/strong><\/p><button[^>]*data-av-apply/);
  assert.match(root.innerHTML, /aria-label="Evidence for your answer"/);
  root.listeners.get('click')({target:button('avSource', '0')});
  assert.equal(requests.length, 1); assert.equal(opened.length, 1);
  assert.equal(opened[0].artifact_id, 'message'); assert.equal(opened[0].quote, 'We live here as a family.');
  assert.equal(opened[0].start, 9); assert.equal(opened[0].end, 34); assert.equal(opened[0].filename, 'Customer message');
  assert.match(root.innerHTML, /Lease/);
  root.listeners.get('click')({target:button('avApply')});
  await settle();
  assert.equal(requests.length, 2); assert.match(requests[1].path, /\/decisions\/apply$/);
  const body = JSON.parse(requests[1].options.body);
  assert.equal(body.preview_sha256, 'preview-identity'); assert.equal(body.expected_revision, 7); assert.equal(body.reason, 'The household moved out.');
  assert.notEqual(body.preview_sha256, 'causal-engine-identity');
  assert.ok(requests[1].options.headers['X-CasePath-Idempotency-Key']); assert.equal(refreshed.length, 1);
  assert.equal(ui.session('flow').preview, null); assert.equal(ui.session('flow').lastOverride.reason, body.reason);
  assert.equal(ui.session('flow').error, ''); assert.match(root.innerHTML, /Decision saved/); assert.doesNotMatch(root.innerHTML, /saved claim changed/);
  assert.ok(checks.some(check => check.field === 'result_sha256' && check.contract === 'casepath.causal-process-result/1.0.0'));
});

test('a forged preview for a different answer never exposes an apply action', async () => {
  const input = model('wrong-answer'), root = rootFor('wrong-answer'); ui.render(input);
  ui.bind({root, api:{verify:verifier, request:async () => ({...previewFor(input), answer_id:'true'})}});
  root.listeners.get('submit')({target:formFor('false', 'Moved out.'), preventDefault(){}}); await settle();
  assert.equal(ui.session('wrong-answer').preview, null); assert.match(root.innerHTML, /does not match/); assert.doesNotMatch(root.innerHTML, /data-av-apply/);
});

test('an ambiguous control save recovers with its original body and idempotency key', async () => {
  const savedStorage = global.sessionStorage, records = new Map(), calls = [];
  global.sessionStorage = {getItem:key => records.get(key) || null, setItem:(key, value) => records.set(key, value), removeItem:key => records.delete(key)};
  try {
    const input = model('recovery'), root = rootFor('recovery'); ui.render(input);
    ui.bind({root, api:{verify:verifier, request:async (path, options) => {
      calls.push({path, options});
      if (options.method === 'GET') return {...input.agent, projection_sha256:'fresh-agent-seal'};
      if (calls.length === 2) throw Object.assign(new Error('Connection lost after posting.'), {transportFailure:true});
      return {contract:'casepath.agent-control-result/1.0.0', projection_sha256:'control-seal', agent:{...input.agent, state:'paused', projection_sha256:'agent-seal'}};
    }}});
    root.listeners.get('click')({target:button('avControl', 'pause')}); await settle();
    assert.match(root.innerHTML, /Recover saved request/); assert.equal(records.size, 1);
    root.listeners.get('click')({target:button('avRecover')}); await settle();
    assert.equal(calls.length, 3); assert.equal(calls[0].options.method, 'GET');
    assert.equal(calls[1].options.body, calls[2].options.body);
    assert.equal(calls[1].options.headers['X-CasePath-Idempotency-Key'], calls[2].options.headers['X-CasePath-Idempotency-Key']);
    assert.equal(records.size, 0); assert.match(root.innerHTML, /The agent is paused/);
  } finally {global.sessionStorage = savedStorage;}
});

test('a failed save reveals its error and focuses recovery while confirmed success keeps the current position', async () => {
  const input=model('failure-focus'),root=rootFor('failure-focus'),effects=[];let posts=0;
  root.querySelector=selector=>selector==='[data-av-claim]'?root.marker:{focus:options=>effects.push({selector,method:'focus',options}),scrollIntoView:options=>effects.push({selector,method:'scroll',options})};
  ui.render(input);ui.bind({root,api:{verify:verifier,request:async(path,options)=>{
    if(options.method==='GET')return {...input.agent,projection_sha256:'read-seal'};
    if(++posts===1)throw Object.assign(new Error('Offline after posting.'),{transportFailure:true});
    return {contract:'casepath.agent-control-result/1.0.0',projection_sha256:'control-seal',agent:{...input.agent,state:'paused',projection_sha256:'agent-seal'}};
  }}});
  root.listeners.get('click')({target:button('avControl','pause')});await settle();
  assert.ok(effects.some(e=>e.selector==='[data-av-recover]'&&e.method==='focus'));
  assert.deepEqual(effects.find(e=>e.method==='scroll'),{selector:'.av-notice',method:'scroll',options:{block:'nearest',inline:'nearest',behavior:'instant'}});
  const scrolls=effects.filter(e=>e.method==='scroll').length;
  root.listeners.get('click')({target:button('avRecover')});await settle();
  assert.equal(ui.session('failure-focus').pending,null);assert.equal(effects.filter(e=>e.method==='scroll').length,scrolls);
  assert.deepEqual(effects.at(-1),{selector:'.av-notice',method:'focus',options:{preventScroll:true}});
});

test('control immediately locks the UI and posts only current verified guards with the original handler intent', async () => {
  const input = model('fresh-control'), root = rootFor('fresh-control'), requests = [], checks = [];
  const latest = {...input.agent, workspace_revision:9, workspace_state_sha256:'state-nine', agent_revision:4, agent_state_sha256:'agent-four', owner:{accountable:'Another handler'}, projection_sha256:'fresh-seal'};
  let resolveRead;
  ui.render(input);
  ui.bind({root, api:{verify:async (value, field, contract) => {checks.push(value); await verifier(value, field, contract);}, request:async (path, options) => {
    requests.push({path, options});
    if (options.method === 'GET') return new Promise(resolve => {resolveRead = resolve;});
    assert.ok(checks.includes(latest), 'fresh projection must be verified before posting');
    return {contract:'casepath.agent-control-result/1.0.0', projection_sha256:'control-seal', agent:{...latest, state:'paused'}};
  }}});
  root.listeners.get('click')({target:button('avControl', 'pause')});
  assert.equal(ui.session('fresh-control').busy, true); assert.equal(requests.length, 1);
  assert.match(root.innerHTML, /Checking saved work/); assert.match(root.innerHTML, /data-av-control="pause" disabled/);
  root.listeners.get('click')({target:button('avControl', 'pause')}); assert.equal(requests.length, 1);
  resolveRead(latest); await settle();
  assert.equal(requests.length, 2); assert.match(requests[1].path, /\/agent\/control$/);
  const body = JSON.parse(requests[1].options.body);
  assert.equal(body.action, 'pause'); assert.equal(body.actor, 'M. Keller');
  assert.equal(body.expected_revision, 9); assert.equal(body.expected_state_sha256, 'state-nine');
  assert.equal(body.expected_agent_revision, 4); assert.equal(body.expected_agent_state_sha256, 'agent-four');
  assert.equal(ui.session('fresh-control').busy, false); assert.match(root.innerHTML, /The agent is paused/);
});

test('wrong-claim or unverified control reads never prepare or post a mutation', async () => {
  for (const kind of ['wrong-claim', 'unverified']) {
    const input = model(`control-${kind}`), root = rootFor(input.claim.claim_id), requests = [];
    ui.render(input);
    ui.bind({root, api:{verify:async (value, field, contract) => {if (kind === 'unverified') throw new Error('Projection verification failed.'); await verifier(value, field, contract);}, request:async (path, options) => {
      requests.push({path, options});
      return {...input.agent, claim_id:kind === 'wrong-claim' ? 'another-claim' : input.claim.claim_id, projection_sha256:'read-seal'};
    }}});
    root.listeners.get('click')({target:button('avControl', 'pause')}); await settle();
    assert.equal(requests.length, 1); assert.equal(requests[0].options.method, 'GET');
    assert.equal(ui.session(input.claim.claim_id).pending, null); assert.equal(ui.session(input.claim.claim_id).busy, false);
    assert.match(root.innerHTML, kind === 'wrong-claim' ? /belongs to another claim/ : /Projection verification failed/);
    assert.doesNotMatch(root.innerHTML, /Recover saved request/);
  }
});

test('a stale Resume control verifies current recovery eligibility and never posts an unsafe run', async () => {
  for(const unsafe of ['not-resumable','external-worker']) {
    const id='resume-'+unsafe,ask='Inspect the unfinished operation and reconcile its outcome before retrying.';
    const input=model(id,{state:'unknown',recovery_required:true,recovery_ask:'Review the saved checkpoint before resuming.',run:{run_id:'work.safe',status:'interrupted',facts_worker:'reference',recovery:{can_resume:true}}});
    const root=rootFor(id),requests=[],checks=[];
    ui.render(input);
    const latest={...input.agent,recovery_ask:ask,projection_sha256:'latest-uncertainty',run:{...input.agent.run,facts_worker:unsafe==='external-worker'?'external_facts':'reference',recovery:{can_resume:unsafe==='external-worker'}}};
    ui.bind({root,api:{verify:async(value,field,contract)=>{await verifier(value,field,contract);checks.push(value);},request:async(path,options)=>{requests.push({path,options});return latest;}}});
    root.listeners.get('click')({target:button('avControl','resume')});await settle();
    assert.equal(requests.length,1);assert.equal(requests[0].options.method,'GET');assert.ok(checks.includes(latest));
    assert.equal(ui.session(id).pending,null);assert.equal(ui.session(id).busy,false);assert.equal(ui.session(id).error,ask);
    assert.match(root.innerHTML,/data-av-pane="trace">Inspect recorded work/);assert.doesNotMatch(root.innerHTML,/data-av-control="resume"|Recover saved request/);
  }
});

test('a definite stale control rejection is shown without retrying the post', async () => {
  const input = model('control-stale'), root = rootFor('control-stale'), requests = [];
  ui.render(input);
  ui.bind({root, api:{verify:verifier, request:async (path, options) => {
    requests.push({path, options});
    if (options.method === 'GET') return {...input.agent, projection_sha256:'read-seal'};
    throw Object.assign(new Error('The saved revision changed. Reload saved work.'), {responseReceived:true, ambiguousResponse:false});
  }}});
  root.listeners.get('click')({target:button('avControl', 'pause')}); await settle();
  assert.equal(requests.length, 2); assert.equal(ui.session('control-stale').pending, null);
  assert.match(root.innerHTML, /saved revision changed/); assert.doesNotMatch(root.innerHTML, /Recover saved request/);
});

test('source action passes the exact bound span and rebinding does not duplicate handlers', () => {
  const input = model('source'), root = rootFor('source'), opened = []; ui.render(input);
  const options = {root, onOpenSource:source => opened.push(source)};
  ui.bind(options); ui.bind(options); root.listeners.get('click')({target:button('avSource', '0')});
  assert.equal(opened.length, 1); assert.equal(opened[0].artifact_id, 'message'); assert.equal(opened[0].quote, 'We live here as a family.');
  assert.equal(opened[0].start, 9); assert.equal(opened[0].end, 34); assert.equal(opened[0].filename, 'Customer message');
});

test('citation labels stay concise while exact filenames and source identity remain available', () => {
  const filename = '123-abcdef-customer_email_with_a_long_subject_"quoted".eml';
  for (const [index, metadata] of [{role:'customer_message'}, {media_type:'message/rfc822'}, {extraction:'message_body'}].entries()) {
    const input = model(`source-label-${index}`);
    input.sources = [{artifact_id:'message', file_name:filename, ...metadata}];
    const html = ui.render(input);
    assert.match(html, /title="123-abcdef-customer_email_with_a_long_subject_&quot;quoted&quot;\.eml">Customer message · page 1<\/button>/);
    assert.equal(ui.session(input.claim.claim_id).sources[0].file_name, filename);
  }
  const input = model('attachment-label'); input.sources = [{artifact_id:'message', filename:'Termination_notice.pdf'}];
  assert.match(ui.render(input), /title="Termination_notice\.pdf">Termination notice\.pdf · page 1<\/button>/);
  const saved = global.CasePathPresentation;
  try {
    global.CasePathPresentation = require('../casepath/assets/claims-workspace-presentation-v1.js');
    input.sources = [{artifact_id:'message', file_name:'123-abcdef-Termination_notice.pdf'}];
    assert.match(ui.render(input), /title="123-abcdef-Termination_notice\.pdf">Termination notice\.pdf · page 1<\/button>/);
  } finally {global.CasePathPresentation = saved;}
});

test('reusable knowledge cannot include unvalidated steps or claim automatic learning', () => {
  const input = model('learning'); input.process = {graph:{nodes:[{node_id:'checked', label:'Checked step', validation:{status:'validated'}}, {node_id:'unchecked', label:'Unchecked step', validation:{status:'unvalidated'}}]}};
  const html = ui.render(input);
  assert.match(html, /name="node_ids" value="checked"/); assert.doesNotMatch(html, /name="node_ids" value="unchecked"/);
  assert.match(html, /Preview reuse scope/); assert.match(html, /needs its own review before reuse/);
  assert.doesNotMatch(html, /automatically learned|Approve new fragment/);
});

test('a newer saved claim invalidates a preview and keeps the handler answer for a fresh preview', () => {
  const input = model('stale'); ui.render(input);
  const s = ui.session('stale'); s.preview = previewFor(input); s.previewBody = {answer_id:'false'}; s.answers['condition:family_home'] = 'false'; s.reasons['condition:family_home'] = 'Moved out.';
  input.agent.workspace_revision = 8; input.agent.workspace_state_sha256 = 'state-eight';
  const html = ui.render(input);
  assert.equal(s.preview, null); assert.match(html, /saved claim changed/); assert.doesNotMatch(html, /data-av-apply/);
  assert.match(html, /value="false" checked required/); assert.match(html, />Moved out\.<\/textarea>/);
});

test('new snapshots preserve reviewed identities while a save is active or needs recovery', () => {
  for (const lock of ['busy', 'pending']) {
    const input = model(`preview-${lock}`); ui.render(input);
    const s = ui.session(input.claim.claim_id), preview = previewFor(input), lesson = {workspace_revision:7, workspace_state_sha256:'state-seven', scope:{}};
    s.preview = preview; s.lessonPreview = lesson;
    s[lock] = lock === 'busy' ? true : {kind:'decision', body:{question_id:'condition:family_home'}, key:'exact-pending-key'};
    input.agent = {...input.agent, workspace_revision:8, workspace_state_sha256:'state-eight'};
    ui.render(input);
    assert.equal(s.preview, preview); assert.equal(s.lessonPreview, lesson); assert.equal(s.error, '');
    s.busy = false; s.pending = null; ui.render(input);
    assert.equal(s.preview, null); assert.equal(s.lessonPreview, null); assert.match(s.error, /saved process changed/);
  }
});

test('a verified save remains confirmed when the follow-up refresh fails', async () => {
  const input = model('refresh-failure'), root = rootFor('refresh-failure'); ui.render(input);
  ui.bind({root, api:{verify:verifier, request:async (path, options) => options.method === 'GET' ? {...input.agent, projection_sha256:'read-seal'} : {contract:'casepath.agent-control-result/1.0.0', projection_sha256:'control-seal', agent:{...input.agent, state:'paused', projection_sha256:'agent-seal'}}}, refresh:async () => {throw new Error('Local service unavailable.');}});
  root.listeners.get('click')({target:button('avControl', 'pause')}); await settle();
  assert.equal(ui.session('refresh-failure').pending, null); assert.match(root.innerHTML, /save is confirmed/);
  assert.doesNotMatch(root.innerHTML, /Recover saved request/);
});

test('save completion repaints and rebinds a replacement mount only for the same claim', async () => {
  const savedDocument = global.document;
  try {
    for (const sameClaim of [true, false]) {
      const id = `replacement-${sameClaim}`, input = model(id), root = rootFor(id), replacement = rootFor(sameClaim ? id : 'other-claim');
      global.document = {querySelector:selector => selector === '#agentClaimMount' ? replacement : null};
      ui.render(input);
      ui.bind({root, api:{verify:verifier, request:async (path, options) => options.method === 'GET' ? {...input.agent, projection_sha256:'read-seal'} : {contract:'casepath.agent-control-result/1.0.0', projection_sha256:'control-seal', agent:{...input.agent, state:'paused', projection_sha256:'agent-seal'}}}, refresh:async () => {
        root.isConnected = false;
        replacement.innerHTML = sameClaim ? ui.render(input) : '<p>Other claim remains open.</p>';
        if (sameClaim) assert.match(replacement.innerHTML, /aria-busy="true"/);
      }});
      root.listeners.get('click')({target:button('avControl', 'pause')}); await settle();
      if (sameClaim) {
        assert.match(replacement.innerHTML, /aria-busy="false"/); assert.match(replacement.innerHTML, /data-av-control="resume">Resume agent/);
        assert.match(replacement.innerHTML, /The agent is paused/); assert.ok(replacement.listeners.has('click'));
        assert.doesNotMatch(replacement.innerHTML, /Reading saved work|Saving and checking/);
      } else {
        assert.equal(replacement.innerHTML, '<p>Other claim remains open.</p>'); assert.equal(replacement.listeners.size, 0);
      }
    }
  } finally {global.document = savedDocument;}
});

test('reviewing a source conflict preserves its unresolved status before agreement', () => {
  const input = model('conflict-state', {conflicts:[{fact:'Notice dates', message:'30 June and 31 July differ.', truth_status:'unresolved', sources:[{artifact_id:'message', quote:'30 June', start:1, end:8}], review:{actor:'M. Keller', reason:'Retain both dates.'}}]});
  input.process = {evaluation:{documents:[{document_type:'lease', label:'Lease', route_state:'established'}, {document_type:'notice', label:'Notice', route_state:'held_not_reviewed'}, {document_type:'receipt', label:'Receipt', route_state:'needed_now'}, {document_type:'spouse', label:'Spouse notice', route_state:'not_needed'}]}};
  const html = ui.render(input), coverage = html.slice(html.indexOf('class="av-document-states"'));
  assert.ok(coverage.indexOf('data-state="conflicting"') < coverage.indexOf('data-state="handler-confirmed"'));
  assert.match(coverage, /Source conflict remains unresolved/); assert.match(coverage, /Handler review: Retain both dates/);
  assert.match(coverage, /Missing · needed now/); assert.match(coverage, /Held · not reviewed/); assert.match(coverage, /Not applicable on this route/);
});

test('the decision selector shows one bounded question and preserves selection and edits on refresh', () => {
  const input = model('selector'), root = rootFor('selector');
  input.agent.questions = [question({question_id:'conflict:0', kind:'source_conflict', prompt:'How should the notice dates be handled?'}), question(), question({question_id:'node:service', kind:'step_validation', prompt:'Can the service step be used?'})];
  let html = ui.render(input);
  assert.equal((html.match(/<form data-av-decision=/g) || []).length, 1);
  assert.match(html, /<label for="avQuestionSelect">Choose a decision<\/label><small>3 decisions in this claim<\/small>/); assert.match(html, /value="conflict:0" selected/);
  ui.bind({root});
  root.listeners.get('change')({type:'change', target:{value:'condition:family_home', matches:selector => selector === '[data-av-question-select]'}});
  assert.equal(ui.session('selector').selectedQuestion, 'condition:family_home');
  assert.match(root.innerHTML, /data-av-decision="condition:family_home"/); assert.doesNotMatch(root.innerHTML, /data-av-decision="conflict:0"/);
  ui.session('selector').answers['condition:family_home'] = 'false'; ui.session('selector').reasons['condition:family_home'] = 'Moved out.';
  html = ui.render({...input, agent:{...input.agent, activity:[{type:'SOURCE_OPENED', label:'A source was read.'}]}});
  assert.match(html, /value="condition:family_home" selected/); assert.match(html, /value="false" checked required/); assert.match(html, />Moved out\.<\/textarea>/);
  assert.equal((html.match(/<form data-av-decision=/g) || []).length, 1);
});

test('a requested pause remains working until its checkpoint and cannot resume early', async () => {
  const input = model('pausing', {state:'working', pause_requested:true}), root = rootFor('pausing'), requests = [];
  const html = ui.render(input);
  assert.match(html, /data-state="working">Pausing at next checkpoint/);
  assert.match(html, /data-av-control="resume" disabled>Pausing at next checkpoint/); assert.doesNotMatch(html, />Resume agent</);
  ui.bind({root, api:{request:async path => requests.push(path)}});
  root.listeners.get('click')({target:button('avControl', 'resume')}); await settle();
  assert.equal(requests.length, 0);
  input.agent.state = 'paused';
  const paused = ui.render(input);
  assert.match(paused, /data-av-control="resume">Resume agent/); assert.match(paused, /The agent is paused/);
});

test('decision verification checks both the complete agent envelope and its original causal preview', async () => {
  const input = model('sealed-envelope'), root = rootFor('sealed-envelope'), checks = [];
  ui.render(input);
  ui.bind({root, api:{request:async () => previewFor(input), verify:async (value, field, contract) => {checks.push({field, contract}); await verifier(value, field, contract);}}});
  root.listeners.get('submit')({target:formFor('false', 'Moved out.'), preventDefault(){}}); await settle();
  assert.deepEqual(checks, [{field:'response_sha256', contract:'casepath.agent-decision-preview/1.0.0'}, {field:'preview_sha256', contract:'casepath.causal-process-preview/1.0.0'}]);
  assert.match(root.innerHTML, /data-av-apply/);
});

test('draft approval presents saved wording and records approval without claiming dispatch', async () => {
  const input = model('draft-approval'), root = rootFor('draft-approval'), calls = [];
  input.agent.questions = [question({question_id:'draft:request', kind:'draft_approval', proposal:{answer_id:'approve', reason:'The current process requests receipt dates.'}, answers:[{answer_id:'approve', label:'Approve this draft'}, {answer_id:'revise', label:'Revise the draft'}], draft:{body_markdown:'Please provide the receipt dates for both notices.', status:'draft_not_sent'}})];
  assert.match(ui.render(input), /Read draft, not sent/); assert.match(ui.render(input), /Please provide the receipt dates for both notices/);
  ui.bind({root, api:{verify:verifier, request:async (path, options) => {
    calls.push({path, options});
    if (path.endsWith('/preview')) return {...previewFor(input), causal:null, answer_id:'approve', reason:'The current process requests receipt dates.', operation:null, not_sent:true};
    return {contract:'casepath.agent-decision-result/1.0.0', response_sha256:'draft-approval-seal', question:input.agent.questions[0], not_sent:true, agent:{...input.agent, projection_sha256:'agent-seal'}};
  }}});
  const form = formFor('approve'); form.dataset.avDecision = 'draft:request';
  root.listeners.get('submit')({target:form, preventDefault(){}}); await settle();
  root.listeners.get('click')({target:button('avApply')}); await settle();
  assert.equal(calls.length, 2); assert.equal(JSON.parse(calls[1].options.body).answer_id, 'approve');
  assert.match(root.innerHTML, /Draft approved, not sent/); assert.doesNotMatch(root.innerHTML, /Request sent|Dispatched/);
});

test('recorded knowledge use identifies pinned fragment versions and matching lessons separately', () => {
  const input = model('reuse-record');
  input.agent.learning = {fragments:[{name:'Separate service review', version:2, fragment_sha256:'fragment-two', actor:'M. Keller', source_claim_id:'earlier'}], memories:[{condition:'family_home', memory_sha256:'memory-one', handler:'M. Keller', note:'Check current household.', status:'unverified'}], uses:[{kind:'fragment_use', fragment_sha256:'fragment-two', actor:'M. Keller', reason:'Confirmed for this claim.', revision:8}, {memory_sha256:'memory-one', target:'family_home', note:'Same statement, reviewed here.'}], automatic_learning:false};
  const html = ui.render(input);
  assert.match(html, /Recorded reuse/); assert.match(html, /Separate service review · version 2/);
  assert.match(html, /Applied in this claim · revision 8/); assert.match(html, /Same statement, reviewed here/);
  assert.doesNotMatch(html, /2 reviewed lesson applications/);
});

test('the recorded proposed answer is visible with its reading before alternatives and remains unsaved',()=>{
 const input=model('proposed-answer-first-view');
 ui.session(input.claim.claim_id).answers['condition:family_home']='false';
 const html=ui.render(input),proposal=html.match(/<p class="av-proposal">([\s\S]*?)<\/p>/)?.[1]||'';
 assert.match(proposal,/<span class="av-proposed-answer">Agent proposal: <strong>Yes, it applies<\/strong> · not saved<\/span>/);
 assert.match(proposal,/<span>Agent reading:<\/span> The message reports a shared family home\./);
 assert.ok(html.indexOf('av-proposed-answer')<html.indexOf('av-counter-reading'));
 assert.ok(html.indexOf('av-proposed-answer')<html.indexOf('av-answer-list'));
 assert.deepEqual([...html.matchAll(/name="answer_id" value="([^"]+)"/g)].map(match=>match[1]),['true','false','unresolved']);
 assert.match(html,/name="answer_id" value="false" checked required/);
});

test('proposal captions use only the matched recorded answer label and escape source text',()=>{
 const input=model('proposal-record-only');
 input.agent.questions=[question({answers:[{answer_id:'true',label:'Yes <candidate>'}],proposal:{answer_id:'true',reason:''}})];
 let html=ui.render(input);assert.match(html,/av-proposed-answer">Agent proposal: <strong>Yes &lt;candidate&gt;<\/strong> · not saved/);
 assert.doesNotMatch(html,/<candidate>|<span>Agent reading:<\/span>/);
 for(const proposal of [{answer_id:'absent',reason:'A source reading remains recorded.'},null]){
  input.agent.questions=[question({proposal})];html=ui.render(input);assert.doesNotMatch(html,/av-proposed-answer/);
 }
 input.agent.questions=[question({answers:[{answer_id:'true'}]})];assert.doesNotMatch(ui.render(input),/av-proposed-answer/);
});

test('an unassigned handler keeps every typed reuse field when saved work refreshes', () => {
  const input=model('reuse-input-refresh',{owner:{accountable:null,delegate:'CasePath agent'}});
  input.claim.owner=null;
  input.process={graph:{nodes:[{node_id:'intake',label:'Capture dates',validation:{status:'validated'}}]}};
  const root=rootFor(input.claim.claim_id);ui.render(input);ui.bind({root});
  const form={elements:{name:{value:'Separate "notice" dates'},actor:{value:'Reviewing Handler'},reason:{value:'Keep the two sources separate.'}},querySelectorAll(){return [{value:'intake'}];}};
  root.listeners.get('input')({target:{matches(){return false;},closest(selector){return selector==='[data-av-lesson]'?form:null;}}});
  input.agent={...input.agent,agent_revision:3,activity:[{type:'SOURCE_OPENED',label:'Another recorded read.'}]};
  const html=ui.render(input),lesson=html.slice(html.indexOf('data-av-lesson>'));
  assert.match(lesson,/name="name"[^>]*value="Separate &quot;notice&quot; dates"/);
  assert.match(lesson,/name="actor"[^>]*value="Reviewing Handler"/);
  assert.match(lesson,/name="node_ids" value="intake" checked/);
  assert.match(lesson,/>Keep the two sources separate\.<\/textarea>/);
  assert.equal(ui.session(input.claim.claim_id).pending,null);
  ui.session(input.claim.claim_id).lastOverride={reason:'Earlier correction reason.'};
  form.elements.reason.value='';
  root.listeners.get('input')({target:{matches(){return false;},closest(selector){return selector==='[data-av-lesson]'?form:null;}}});
  const cleared=ui.render(input).split('data-av-lesson>')[1];
  assert.match(cleared,/name="reason"[^>]*><\/textarea>/);
  assert.doesNotMatch(cleared,/Earlier correction reason/);
});

test('simultaneous error and invalid recovery keep distinct reload targets', () => {
  const input=model('recovery-focus-identities');ui.render(input);
  const s=ui.session(input.claim.claim_id);s.error='The saved recovery record is invalid.';s.pending={invalid:true};
  const html=ui.render(input),ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
  assert.equal((html.match(/\sdata-av-reload(?=[\s>])/g)||[]).length,2);
  assert.equal(ids.length,new Set(ids).size);
  assert.match(html,/Recovery repeats|recovery record could not be read/);
  assert.equal(s.pending.invalid,true);
});


test('a decision connects the saved condition dependency to its own document requirements', () => {
  const input=model('causal-context');
  input.process={process_adopted:true,graph:{nodes:[{node_id:'service',label:'Check separate service',document_types:['spouse'],provenance:{source:'static_policy'}}],edges:[]},evaluation:{nodes:[{node_id:'service',condition_flags:['family_home']}],documents:[{document_type:'spouse',label:'Separate notice',required_at_node_ids:['service'],route_state:'held_not_reviewed'},{document_type:'unrelated',label:'Unrelated file',required_at_node_ids:['other'],route_state:'needed_now'}]}};
  const html=ui.render(input),context=html.slice(html.indexOf('<aside class="av-consequence"'),html.indexOf('</aside>'));
  assert.equal(ui.contextNode(input.process,input.agent.questions[0]).node_id,'service');
  assert.match(context,/Saved process/);assert.match(context,/Your proposed answer has not been applied here/);assert.match(context,/Check separate service/);assert.match(context,/Separate notice/);assert.match(context,/Received · review needed/);
  assert.doesNotMatch(context,/Unrelated file/);assert.match(context,/Policy-derived step · source evidence is reviewed separately/);
  assert.match(context,/data-av-review-document="spouse" data-av-node-id="service"/);
  assert.ok(html.indexOf('av-question-condition:family_home')<html.indexOf('id="avQuestionSelect"') || !html.includes('id="avQuestionSelect"'));
});

test('a proposed graph cannot label its checklist as the saved request or family knowledge as applied', () => {
  const input=model('proposed-context',{learning:{fragments:[{name:'Service review',version:2}],memories:[],uses:[]}});
  input.process={process_adopted:false,graph:{nodes:[{node_id:'service',label:'Review <source>',document_types:['notice']}],edges:[]},evaluation:{focus_node_id:'service',nodes:[],documents:[{document_type:'notice',label:'Proposed notice',route_state:'needed_now'}]}};
  const html=ui.render(input),context=html.slice(html.indexOf('<aside class="av-consequence"'),html.indexOf('</aside>'));
  assert.match(context,/Proposed process/);assert.match(context,/Proposed requirements · the current request has not changed/);
  assert.match(context,/1 saved process version available · 0 recorded uses here/);assert.doesNotMatch(context,/Saved process|<source>/);assert.match(context,/Review &lt;source&gt;/);
});

test('context review opens the exact node and document without issuing a mutation', () => {
  const id='document-context-navigation',input=model(id),root=rootFor(id),opened=[];ui.render(input);
  ui.bind({root,onOpenPane:(pane,detail)=>opened.push({pane,detail}),api:{request(){throw new Error('Navigation must not mutate');}}});
  const target=button('avReviewDocument','spouse');target.dataset.avNodeId='service';root.listeners.get('click')({target});
  assert.deepEqual(opened,[{pane:'process',detail:{node_id:'service',document_type:'spouse'}}]);assert.equal(ui.session(id).pending,null);
});


test('an inconsistent completion keeps the corrected step instead of falling back to the active step', () => {
  const p={graph:{nodes:[{node_id:'active',label:'Current work'},{node_id:'incorrect',label:'Completion needs review'}],edges:[]},evaluation:{focus_node_id:'active',nodes:[]}};
  assert.equal(ui.contextNode(p,{question_id:'completion:incorrect'}).node_id,'incorrect');
});


test('a prior insufficient source cannot hide a conditional or closed document route', () => {
  const input=model('insufficient-route');input.process={process_adopted:true,graph:{nodes:[{node_id:'service',label:'Service',document_types:['a','b']}],edges:[]},evaluation:{focus_node_id:'service',nodes:[],documents:[{document_type:'a',label:'Closed requirement',route_state:'not_needed',review_state:'insufficient'},{document_type:'b',label:'Conditional requirement',route_state:'held_behind_question',review_state:'insufficient'}]}};
  const html=ui.render(input);assert.match(html,/Not needed on this route · Received · insufficient/);assert.match(html,/Depends on an answer · Received · insufficient/);
});


test('an edited policy step exposes its current review status rather than implying unchanged policy support', () => {
  const input=model('edited-policy');input.process={graph:{nodes:[{node_id:'step',label:'Edited step',document_types:[],provenance:{source:'static_policy',modified_by:'M. Keller'},validation:{status:'revised'}}]},evaluation:{focus_node_id:'step',nodes:[],documents:[]}};
  let html=ui.render(input);assert.match(html,/Saved handler edit · step validation needed/);assert.doesNotMatch(html,/Policy-derived step · source evidence is reviewed separately/);
  input.process.graph.nodes[0].validation.status='validated';html=ui.render(input);assert.match(html,/Handler-validated step · source evidence remains separate/);assert.doesNotMatch(html,/Saved handler edit · step validation needed/);
});


test('only an intentional context change animates and reduced motion disables it', () => {
  const prior=global.matchMedia;
  try {
    for (const reduce of [false,true]) {
      global.matchMedia=()=>({matches:reduce});const id='context-motion-'+reduce,input=model(id,{questions:[question(),question({question_id:'condition:other'})]}),root=rootFor(id),animations=[];
      const query=root.querySelector.bind(root);root.querySelector=selector=>selector==='.av-consequence'?{animate:(frames,timing)=>animations.push({frames,timing})}:query(selector);
      ui.render(input);ui.bind({root});assert.equal(animations.length,0);
      root.listeners.get('change')({type:'change',target:{value:'condition:other',matches:()=>true}});
      ui.render(input);root.listeners.get('change')({type:'change',target:{value:'condition:other',matches:()=>true}});
      assert.equal(animations.length,reduce?0:1);
      if(!reduce){assert.ok(animations[0].timing.duration<250);assert.deepEqual(Object.keys(animations[0].frames[0]).sort(),['opacity','transform']);}
    }
  } finally {if(prior)global.matchMedia=prior;else delete global.matchMedia;}
});


test('knowledge approval exposes the exact proposal and does not claim cross-claim conflict checks', () => {
  const input = model('learning-scope-honesty'); ui.render(input);
  const s = ui.session(input.claim.claim_id);
  s.lessonPreview = {workspace_revision:7, workspace_state_sha256:'state-seven',name:'Separate <notice> capture', actor:'M. Keller',reason:'Keep both reported dates unresolved.',scope:{family:'lease_termination_dispute',node_ids:[],boundary_relationships:[],documents:[]},conflicts:[]};
  const html=ui.render(input);
  assert.match(html, /Separate &lt;notice&gt; capture/);
  assert.match(html, /Keep both reported dates unresolved\./);
  assert.match(html, /Reviewing handler: <strong>M\. Keller<\/strong>/);
  assert.match(html, /Conflicts with other claims have not been checked/);
  assert.doesNotMatch(html, /No scope conflict|No conflicts/);
  assert.match(html, /Approval creates a new fragment at version 1/);
  assert.match(html, /Saved fragments stay unchanged/);
  assert.match(html, /Applying it to another claim requires a separate preview and approval/);
  assert.match(html, /Cancel reuse/);
  s.lessonPreview.conflicts=['Node identity differs'];
  assert.match(ui.render(input), /Node identity differs/);
});

const interruptedProjection = () => ({state:'unknown',recovery_required:true,run:{run_id:'work.local',status:'unconfirmed',facts_worker:'reference',provider_requests:0,pending_calls:[{call_id:'reference.process.4'}],recovery:{can_resume:false,reason:'pending_operation',reconciliation:{kind:'process_node',run_id:'work.local',call_id:'reference.process.4',object_id:'process:step',title:'Check separate service',expected_last_event_sha256:'work-event',expected_work_state_sha256:'work-state'}}}});

test('only a signed local proposal recovery exposes an explicit review before reconciliation', () => {
 const input=model('reconciliation-review',interruptedProjection()),root=rootFor(input.claim.claim_id);
 let html=ui.render(input);assert.match(html,/data-av-reconcile-review/);assert.doesNotMatch(html,/data-av-reconcile-form/);
 ui.bind({root});root.listeners.get('click')({target:button('avReconcileReview')});
 assert.match(root.innerHTML,/Check separate service/);assert.match(root.innerHTML,/The working process stays unchanged/);assert.match(root.innerHTML,/data-av-reconcile-form/);
 input.agent.workspace_revision=8;ui.render(input);assert.equal(ui.session(input.claim.claim_id).reconciliationReview,null);
 assert.match(ui.session(input.claim.claim_id).error,/saved work changed/);
 for(const change of [{facts_worker:'external_facts'},{provider_requests:1},{recovery:{can_resume:false,reason:'pending_operation'}},{run_id:'different'}]){
  input.agent={...input.agent,...interruptedProjection(),run:{...interruptedProjection().run,...change}};
  assert.doesNotMatch(ui.render(input),/data-av-reconcile-review/);
 }
});

test('reconciliation uses exact reviewed guards, preserves ambiguous request identity, and never resumes automatically',async()=>{
 const input=model('reconciliation-save',interruptedProjection()),root=rootFor(input.claim.claim_id),requests=[];
 ui.render(input);
 ui.bind({root,api:{verify:verifier,request:async(path,options)=>{requests.push({path,options});if(requests.length===1)throw new Error('Connection interrupted');return {contract:'casepath.agent-reconciliation-result/1.0.0',projection_sha256:'reconciled',reconciliation:{reconciled:true,event_sha256:'work-receipt',claim_state_changed:false},agent:{...input.agent,projection_sha256:'agent-current',run:{...input.agent.run,pending_calls:[],recovery:{can_resume:true,reason:'safe_checkpoint'}}}};}}});
 root.listeners.get('click')({target:button('avReconcileReview')});
 const form={matches(){return true;},hasAttribute(a){return a==='data-av-reconcile-form';},elements:{reason:{value:'I reviewed the saved local proposal.'}}};
 root.listeners.get('submit')({target:form,preventDefault(){}});await settle();
 assert.equal(requests.length,1);assert.match(requests[0].path,/\/api\/claim-loops\/v1\/workspace\/claims\/reconciliation-save\/agent\/reconcile$/);
 assert.equal(requests[0].options.headers['X-CasePath-Agent-Work'],'1');const body=JSON.parse(requests[0].options.body);assert.equal(body.run_id,'work.local');assert.equal(body.object_id,'process:step');assert.equal(body.expected_last_event_sha256,'work-event');assert.equal(body.expected_work_state_sha256,'work-state');assert.equal(body.expected_revision,7);assert.equal(body.expected_agent_revision,2);
 assert.ok(ui.session(input.claim.claim_id).pending);root.listeners.get('click')({target:button('avRecover')});await settle();
 assert.equal(requests.length,2);assert.deepEqual(requests[1],requests[0]);assert.equal(ui.session(input.claim.claim_id).pending,null);assert.match(root.innerHTML,/Resume agent/);assert.match(root.innerHTML,/Local proposal reconciled/);assert.doesNotMatch(root.innerHTML,/data-av-reconcile-form/);
});


test('a superseded recovery request never claims that the pending proposal was reconciled',async()=>{
 const input=model('reconciliation-superseded',interruptedProjection()),root=rootFor(input.claim.claim_id);ui.render(input);
 ui.bind({root,api:{verify:verifier,request:async()=>({contract:'casepath.agent-reconciliation-result/1.0.0',projection_sha256:'saved-request',reconciliation:{reconciled:false,reason:'superseded_recovery_request'},agent:{...input.agent,projection_sha256:'current-work'}})}});
 root.listeners.get('click')({target:button('avReconcileReview')});
 root.listeners.get('submit')({target:{matches(){return true;},hasAttribute(a){return a==='data-av-reconcile-form';},elements:{reason:{value:'Checked the saved process.'}}},preventDefault(){}});await settle();
 assert.match(root.innerHTML,/recovery request was superseded/);assert.doesNotMatch(root.innerHTML,/Local proposal reconciled/);assert.equal(ui.session(input.claim.claim_id).pending,null);
});


test('an override preview keeps the original proposed answer beside the handlers chosen answer',()=>{
 const input=model('preview-proposal-identity');ui.render(input);ui.session(input.claim.claim_id).preview=previewFor(input);
 const html=ui.render(input);
 assert.match(html,/Your answer:<\/span> <strong>No, it does not apply<\/strong>/);
 assert.match(html,/Agent proposal: <strong>Yes, it applies<\/strong> · not saved/);
 assert.match(html,/The message reports a shared family home/);
});

const liveReview = (extra = {}) => ({available:true,can_start:true,model:'small/source-reader',run_cost_limit_usd:0.03,total_cost_limit_usd:0.09,
  context_sha256:'a'.repeat(64),budget:{can_start:true,remaining_cost_usd:0.09},...extra});
const liveReceipt = (input, body, extra = {}) => ({contract:'casepath.agent-work/1.0.0',response_sha256:'sealed-work-response',
  summary:{claim_id:input.claim.claim_id,run_id:'work.'+'b'.repeat(32),facts_worker:'external_facts',
    requested_context_sha256:body.expected_context_sha256,idempotency_key:body.idempotency_key,...extra}});

test('live source review starts only after its explicit click and binds the displayed sealed context', async()=>{
  const input=model('live-explicit',{live_review:liveReview()}),root=rootFor(input.claim.claim_id),calls=[],checks=[],refreshes=[];
  const html=ui.render(input);assert.match(html,/Review sources live/);assert.match(html,/up to \$0\.03 per review/);
  ui.bind({root,api:{verify:async(value,field,contract)=>{checks.push({field,contract});await verifier(value,field,contract);},request:async(path,options)=>{calls.push({path,options});return liveReceipt(input,JSON.parse(options.body));}},refresh:async receipt=>refreshes.push(receipt)});
  await settle();ui.render(input);assert.equal(calls.length,0,'Rendering and binding cannot spend model credits');
  const current={...input,agent:{...input.agent,live_review:liveReview({context_sha256:'c'.repeat(64)})}};
  ui.render(current);root.listeners.get('click')({target:button('avLiveStart')});await settle();
  assert.equal(calls.length,1);assert.equal(calls[0].path,'/api/agent-work/v1/claims/live-explicit/runs');
  assert.equal(calls[0].options.method,'POST');assert.equal(calls[0].options.headers['X-CasePath-Agent-Work'],'1');
  const body=JSON.parse(calls[0].options.body);assert.deepEqual(Object.keys(body).sort(),['expected_context_sha256','facts_worker','idempotency_key']);
  assert.equal(body.expected_context_sha256,'c'.repeat(64));assert.equal(body.facts_worker,'external_facts');
  assert.equal(body.idempotency_key,calls[0].options.headers['X-CasePath-Idempotency-Key']);
  assert.match(body.idempotency_key,/^agent-claim:/);assert.deepEqual(checks,[{field:'response_sha256',contract:'casepath.agent-work/1.0.0'}]);
  assert.equal(refreshes.length,1);assert.equal(ui.session(input.claim.claim_id).pending,null);
  assert.match(root.innerHTML,/Live review requested/);assert.equal(ui.session(input.claim.claim_id).open.has('live-work'),true);
});

test('disabled budgets and missing or malformed context guards cannot start even through a stale button', async()=>{
  const denied=[{available:false},{can_start:false,reason:'external_cost_limit'},{context_sha256:null},{context_sha256:'not-bound'},
    {context_sha256:'https://external.invalid/context'},{can_start:false,reason:'accountable_handler_required'}];
  for(const [index,extra] of denied.entries()){
    const id='live-disabled-'+index,input=model(id,{live_review:liveReview(extra)}),root=rootFor(id),calls=[];
    assert.doesNotMatch(ui.render(input),/data-av-live-start/);
    ui.bind({root,api:{request:async(...args)=>calls.push(args),verify:verifier}});
    root.listeners.get('click')({target:button('avLiveStart')});await settle();
    assert.equal(calls.length,0);assert.equal(ui.session(id).pending,null);
  }
});

test('live response verification and claim, worker, context, request and run bindings are mandatory', async()=>{
  const mismatches=[{claim_id:'another-claim'},{facts_worker:'reference'},{requested_context_sha256:'c'.repeat(64)},
    {idempotency_key:'another-request'},{run_id:null},'unverified'];
  for(const [index,extra] of mismatches.entries()){
    const id='live-receipt-'+index,input=model(id,{live_review:liveReview()}),root=rootFor(id),calls=[],refreshes=[];
    ui.render(input);ui.bind({root,api:{verify:async(value,field,contract)=>{if(extra==='unverified')throw new Error('Work response seal differs');await verifier(value,field,contract);},request:async(path,options)=>{calls.push({path,options});return liveReceipt(input,JSON.parse(options.body),typeof extra==='object'?extra:{});}},refresh:async()=>refreshes.push(true)});
    root.listeners.get('click')({target:button('avLiveStart')});await settle();
    assert.equal(calls.length,1);assert.equal(refreshes.length,0);assert.ok(ui.session(id).pending,'Unconfirmed receipt must preserve its exact request');
    assert.match(root.innerHTML,extra==='unverified'?/Work response seal differs/:/live review receipt does not match/);
    assert.doesNotMatch(root.innerHTML,/Live review requested/);
    root.listeners.get('click')({target:button('avLiveStart')});await settle();assert.equal(calls.length,1,'An unconfirmed request cannot become a second paid request');
  }
});

test('an unknown live start survives reload and recovers the identical body and idempotency key', async()=>{
  const previous=global.sessionStorage,records=new Map(),calls=[];
  global.sessionStorage={getItem:key=>records.get(key)||null,setItem:(key,value)=>records.set(key,value),removeItem:key=>records.delete(key)};
  try{
    const id='live-persisted-recovery',input=model(id,{live_review:liveReview()}),root=rootFor(id),key='casepath:agent-claim-pending:'+id;
    ui.render(input);const api={verify:verifier,request:async(path,options)=>{calls.push({path,options});if(calls.length===1)throw new Error('Connection closed before receipt');return liveReceipt(input,JSON.parse(options.body));}};
    ui.bind({root,api});root.listeners.get('click')({target:button('avLiveStart')});await settle();
    const persisted=JSON.parse(records.get(key));assert.equal(persisted.kind,'live');assert.equal(persisted.key,JSON.parse(calls[0].options.body).idempotency_key);
    assert.deepEqual(persisted.body,JSON.parse(calls[0].options.body));assert.match(root.innerHTML,/Recover saved request/);
    // The server may now deny NEW work; recovery still checks only the prior
    // request. A fresh module reads the exact saved command, as after reload.
    const freshPath=require.resolve('../casepath/assets/agent-claim-v2.js'),cached=require.cache[freshPath];delete require.cache[freshPath];
    const fresh=require(freshPath);require.cache[freshPath]=cached;
    const next={...input,agent:{...input.agent,live_review:liveReview({can_start:false,context_sha256:'c'.repeat(64),reason:'external_cost_limit'})}},newRoot=rootFor(id);
    fresh.render(next);fresh.bind({root:newRoot,api});await settle();assert.equal(calls.length,1,'Reload cannot automatically retry a paid request');
    newRoot.listeners.get('click')({target:button('avRecover')});await settle();
    assert.equal(calls.length,2);assert.deepEqual(calls[1],calls[0]);assert.equal(records.has(key),false);assert.equal(fresh.session(id).pending,null);
    assert.match(newRoot.innerHTML,/Live review requested/);
  }finally{global.sessionStorage=previous;}
});

test('a definitive live HTTP rejection clears pending while an ambiguous response preserves it', async()=>{
  const previous=global.sessionStorage,records=new Map();
  global.sessionStorage={getItem:key=>records.get(key)||null,setItem:(key,value)=>records.set(key,value),removeItem:key=>records.delete(key)};
  try{
    for(const ambiguous of [false,true]){
      const id='live-http-'+ambiguous,input=model(id,{live_review:liveReview()}),root=rootFor(id),key='casepath:agent-claim-pending:'+id;
      ui.render(input);ui.bind({root,api:{verify:verifier,request:async()=>{throw Object.assign(new Error('The bounded request was rejected'),{responseReceived:true,ambiguousResponse:ambiguous,status:409});}}});
      root.listeners.get('click')({target:button('avLiveStart')});await settle();
      assert.equal(Boolean(ui.session(id).pending),ambiguous);assert.equal(records.has(key),ambiguous);
      assert.doesNotMatch(root.innerHTML,/Live review requested/);assert.match(root.innerHTML,/bounded request was rejected/);
    }
  }finally{global.sessionStorage=previous;}
});

test('live stages retain selection through updates and navigate exact sources, nodes and documents without calls',()=>{
  const previous=global.CasePathWorkMotion;global.CasePathWorkMotion=require('../casepath/assets/agent-work-motion-v3.js');
  try{
    const id='live-stage-navigation',source={artifact_id:'notice-pdf',source_id:'notice-pdf',claim_id:id,file_name:'Exact notice.pdf',quote:'30. Juni',start:4,end:12,source_sha256:'d'.repeat(64),text_sha256:'e'.repeat(64),extraction:'pdf_text'};
    const milestone=(sequence,stage,extra)=>({sequence,stage,summary:'Recorded '+stage,sources:[],nodes:[],documents:[],connections:[],...extra});
    const work={claim_id:id,run_id:'work.'+'b'.repeat(32),scope:'recorded_review_work_not_claim_authority',status:'running',currentness:'current',last_sequence:4,active_stage:'sources',headline:'Reading exact source statements',reader:{kind:'model',model:'small/source-reader'},
      stages:['sources','findings','process','documents'].map((stage,index)=>({id:stage,label:stage,state:'recorded',count:1,unit:'recorded',milestone_sequence:index+1})),
      milestones:[milestone(1,'sources',{sources:[source]}),milestone(2,'findings',{sources:[source]}),milestone(3,'process',{nodes:[{node_id:'notice-date',label:'Check the notice date'}]}),
        milestone(4,'documents',{nodes:[{node_id:'notice-date',label:'Check the notice date'}],documents:[{requirement_id:'process_document.notice',document_type:'notice',label:'Notice copy',state:'conditional',needed_now:false}],connections:[{from:'node:notice-date',to:'obligation:process_document.notice',relation:'required_by_process'}]})]};
    const input=model(id,{state:'working',live_work:work}),root=rootFor(id),opened=[],sources=[],calls=[];
    ui.render(input);ui.bind({root,api:{request(...args){calls.push(args);}},onOpenSource:span=>sources.push(span),onOpenPane:(pane,detail)=>opened.push({pane,detail})});
    const sourceIndex=ui.session(id).sources.findIndex(item=>item.source_sha256===source.source_sha256);
    root.listeners.get('click')({target:button('avSource',String(sourceIndex))});assert.deepEqual(sources,[source]);
    root.listeners.get('click')({target:button('avWorkStage','documents')});assert.equal(ui.session(id).workStage,'documents');
    assert.match(root.innerHTML,/data-av-work-stage="documents" aria-pressed="true"/);assert.match(root.innerHTML,/data-av-document="notice"/);
    root.listeners.get('click')({target:button('avNode','notice-date')});const doc=button('avPane','documents');doc.dataset.avDocument='notice';root.listeners.get('click')({target:doc});
    assert.deepEqual(opened,[{pane:'process',detail:{node_id:'notice-date'}},{pane:'documents',detail:{document_type:'notice'}}]);
    input.agent.live_work={...work,active_stage:'process',last_sequence:5};const updated=ui.render(input);
    assert.match(updated,/data-av-work-stage="documents" aria-pressed="true"/);assert.equal(ui.session(id).workStage,'documents');
    root.listeners.get('click')({target:button('avWorkStage','invented')});assert.equal(ui.session(id).workStage,'documents');
    root.listeners.get('click')({target:button('avWorkFollow')});assert.equal(ui.session(id).workStage,null);assert.match(root.innerHTML,/data-av-work-stage="process" aria-pressed="true"/);
    assert.equal(calls.length,0);assert.equal(ui.session(id).pending,null);
  }finally{global.CasePathWorkMotion?.dispose();global.CasePathWorkMotion=previous;}
});

test('Resume delegate verifies safe external completion then only clears its mandate before a separate live start',async()=>{
  const id='live-clear-mandate',run={run_id:'work.live',facts_worker:'external_facts',status:'cancelled',pending_calls:[],provider_requests:1,provider_cost_usd:0.001,recovery:{can_resume:false}};
  const input=model(id,{state:'paused',pause_requested:true,can_clear_external_pause:true,run,live_review:liveReview({can_start:false,context_sha256:null,reason:'paused_by_handler'})}),root=rootFor(id),calls=[];
  assert.match(ui.render(input),/data-av-control="resume">Resume delegate/);
  const latest={...input.agent,projection_sha256:'fresh-projection',agent_revision:3,agent_state_sha256:'fresh-control'};
  const resumed={...latest,state:'waiting_for_you',pause_requested:false,can_clear_external_pause:false,live_review:liveReview()};
  ui.bind({root,api:{verify:verifier,request:async(path,options)=>{calls.push({path,options});return options.method==='GET'?latest:{contract:'casepath.agent-control-result/1.0.0',projection_sha256:'mandate-cleared',agent:resumed,continuation:null};}}});
  root.listeners.get('click')({target:button('avControl','resume')});await settle();
  assert.equal(calls.length,2);assert.equal(calls[0].options.method,'GET');assert.match(calls[1].path,/\/agent\/control$/);
  assert.equal(JSON.parse(calls[1].options.body).action,'resume');assert.equal(JSON.parse(calls[1].options.body).expected_agent_revision,3);
  assert.equal(ui.session(id).input.agent.pause_requested,false);assert.equal(ui.session(id).input.agent.run.run_id,run.run_id);
  assert.match(root.innerHTML,/data-av-live-start/);assert.doesNotMatch(root.innerHTML,/Resume delegate/);
  assert.ok(calls.every(call=>!call.path.endsWith('/runs')),'Mandate resume must never create a model run');
});

test('stale Resume delegate cannot clear a newly uncertain external outcome',async()=>{
  const id='live-clear-became-unknown',run={run_id:'work.live',facts_worker:'external_facts',status:'cancelled',pending_calls:[],provider_requests:1,provider_cost_usd:0.001,recovery:{can_resume:false}};
  const input=model(id,{state:'paused',pause_requested:true,can_clear_external_pause:true,run}),root=rootFor(id),calls=[];
  ui.render(input);ui.bind({root,api:{verify:verifier,request:async(path,options)=>{calls.push({path,options});return {...input.agent,projection_sha256:'fresh-unknown',can_clear_external_pause:false,recovery_ask:'The provider outcome still needs inspection.',run:{...run,pending_calls:[{call_id:'provider.request.1'}],provider_cost_usd:null}};}}});
  root.listeners.get('click')({target:button('avControl','resume')});await settle();
  assert.equal(calls.length,1);assert.equal(calls[0].options.method,'GET');assert.match(root.innerHTML,/provider outcome still needs inspection/);
  assert.equal(ui.session(id).input.agent.pause_requested,true);assert.equal(ui.session(id).pending,null);
});
