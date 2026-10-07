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
const verifier = async (value, field, contract) => {assert.equal(value.contract, contract); assert.ok(value[field], `missing ${field}`);};
function previewFor(input) {return {contract:'casepath.agent-decision-preview/1.0.0', response_sha256:'preview-envelope', preview_sha256:'preview-identity', causal:{contract:'casepath.causal-process-preview/1.0.0', preview_sha256:'causal-engine-identity', claim_id:input.claim.claim_id, workspace_revision:7, workspace_state_sha256:'state-seven'}, claim_id:input.claim.claim_id, workspace_revision:7, workspace_state_sha256:'state-seven', question:input.agent.questions[0], answer_id:'false', reason:'The household moved out.', graph:{nodes:[], document_catalog:[]}, impact:{changed_document_types:['spouse_notice'], unchanged_document_types:['lease']}};}

test('accountability, mandate and native bounded decision are visible before interaction', () => {
  const html = ui.render(model('native'));
  assert.match(html, /Accountable handler <strong>M\. Keller<\/strong>/);
  assert.match(html, /CasePath agent<\/h2><span class="av-delegate">Delegate/);
  assert.match(html, /Waiting for you/); assert.match(html, /Works unattended/); assert.match(html, /Waits for your approval/);
  assert.match(html, /<fieldset class="av-answer-list"><legend>Choose your answer/);
  assert.match(html, /type="radio" name="answer_id" value="true" checked required/);
  assert.match(html, /Agent proposal/); assert.match(html, /Counter-reading/); assert.match(html, /data-av-source="0"/);
  assert.match(html, /<small class="av-proposal-label">Agent proposal · not saved<\/small>/);
  assert.match(html, /<span>Agent reading:<\/span> The message reports a shared family home\./);
  assert.match(html, /<span>Counter-reading:<\/span> The message may describe an earlier household\./);
  assert.match(html, /Preview first\. Apply saves your answer and starts the next review\. Drafts stay not sent\./);
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
  assert.match(header,/Earlier review · 6 of 6 review roles finished · 1 of 1 original sources read/);
  assert.match(header,/Draft awaits review · not sent/);assert.doesNotMatch(header,/Current review/);
  input.agent={...input.agent,state:'working',run:{completed_roles:0,role_count:6,currentness:'current'},questions:[]};
  const current=ui.render(input).slice(0,ui.render(input).indexOf('</header>'));
  assert.match(current,/Current review · 0 of 6 review roles finished/);assert.doesNotMatch(current,/Draft awaits review|Earlier review/);
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
  assert.match(root.innerHTML, /Preview first\. Apply saves your answer and starts the next review\. Drafts stay not sent\./);
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
  assert.match(html, /Preview scope and conflicts/); assert.match(html, /needs its own review before reuse/);
  assert.doesNotMatch(html, /automatically learned|Approve reusable fragment/);
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
