const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const language = require('../casepath/assets/autonomous-language-v1.js');
const root = path.resolve(__dirname,'..');
const read = name => JSON.parse(fs.readFileSync(path.join(root,name),'utf8'));
// Real committed records supply the receipt shape. Changes below are negative cases.
const saved = read('casepath/assets/autonomous-saved-history-v1.json').state;
const currentReceipt = state => [...state.receipts].reverse().find(row => row.kind === 'interpretation.accepted' && row.receipt.workflow_id === state.run_id).receipt;
const accepted = currentReceipt(saved);
const packet = read('casepath/assets/autonomous-recorded-heating-v1.json');
const fragments = new Map();
function expand(id) {
  if (!fragments.has(id)) fragments.set(id,typeof packet.fragments[id] === 'string' ? packet.fragments[id] : packet.fragments[id].map(expand).join(''));
  return fragments.get(id);
}
const recorded = packet.claims.map(claim => {
  const bytes=Buffer.from(expand(claim.head_snapshot.root));
  assert.equal(bytes.length,claim.head_snapshot.bytes);
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),claim.head_snapshot.sha256);
  return JSON.parse(bytes).state;
});
const ui = require('../casepath/assets/autonomous-workspace-v1.js');
const templates = read('casepath-api/casepath_api/corpora/synthetic-150/policy/static-rule-templates-v3.json').templates;
const banned = /\b(?:provisional|derive|requalified|quarantined|compilation|recipe|applicability|regression|sha|hash|canonical|projection|branch|pinned|deterministic|verifier|synthetic)\b/iu;
function shortCopy(value) {
  assert.equal(typeof value,'string');
  assert.doesNotMatch(value,banned);
  assert.ok(value.trim().split(/\s+/u).filter(Boolean).length <= 20,`Long display copy: ${value}`);
}
function assertNextAction(state,expected) {
  const outcome=state.outcome || state.deferral,before=JSON.stringify(state);
  const view=language.outcomePresentation(state);
  assert.equal(view.nextAction,expected);shortCopy(view.nextAction);
  assert.equal(view.recordedSummary,outcome?.summary || outcome?.reason || '');
  if(outcome)assert.equal(view.details,outcome);else assert.deepEqual(view.details,{});
  assert.equal(JSON.stringify(state),before,'presentation must preserve every recorded byte and source quote');
  return view;
}

test('UMD and CommonJS expose the same frozen, side-effect-free API',()=>{
  const source=fs.readFileSync(path.join(root,'casepath/assets/autonomous-language-v1.js'),'utf8');
  const sandbox={};vm.runInNewContext(source,sandbox);
  assert.deepEqual(Object.keys(sandbox.CasepathLanguage),Object.keys(language));
  assert.equal(Object.isFrozen(language),true);
  assert.equal(Object.isFrozen(language.roles.reader),true);
  assert.doesNotMatch(source,/\b(?:fetch|localStorage|sessionStorage|XMLHttpRequest|document\.querySelector)\b/u);
});

test('roles describe source proposals, source checks, fixed rules and checked reuse',()=>{
  assert.deepEqual(Object.values(language.roles).map(row=>row.label),['Reader','Checker','Rulebook','Memory','CasePath']);
  for(const role of Object.values(language.roles)){assert.equal(role.id,role.label.toLowerCase());shortCopy(role.label);shortCopy(role.description);}
  assert.match(language.roles.reader.description,/Proposes/);
  assert.match(language.roles.checker.description,/exact sources/);
  assert.match(language.roles.rulebook.description,/fixed rules/);
  assert.match(language.roles.memory.description,/checks pass/);
});

test('only a completed recorded provider call supplies the exact model label',()=>{
  assert.equal(accepted.proposal_receipt.contract,'casepath.autonomous-provider-result/1.0.0');
  const original=JSON.stringify(saved);
  for(const stage of ['interpret','verify']){
    const call=stage==='interpret'?accepted.proposal_receipt:accepted.verifier_receipt;
    assert.deepEqual(language.provenancePresentation({state:saved},stage),{kind:'model',label:`AI model: ${call.model}`,model:call.model});
  }
  assert.equal(accepted.proposal_receipt.model,accepted.verifier_receipt.model,'these actual calls used the same model');
  assert.equal(JSON.stringify(saved),original);
  const metadataOnly={state:{run_id:saved.run_id,model:accepted.proposal_receipt.model,semantic_contexts:{[saved.run_id]:{model:accepted.proposal_receipt.model,execution_mode:'provider'}}}};
  assert.equal(language.provenancePresentation(metadataOnly).label,'CasePath');
});

test('missing, rejected, unmatched and incomplete call receipts cannot claim AI use',()=>{
  const changes=[
    r=>{delete r.proposal_receipt;}, r=>{r.workflow_id='another-run';},
    r=>{r.proposal_receipt.status='rejected';},r=>{r.proposal_receipt.status='unknown';},
    r=>{r.proposal_receipt.contract='configured-model';},r=>{r.proposal_receipt.stage='verify';},
    r=>{r.proposal_receipt.workflow_id='another-run';},r=>{delete r.proposal_receipt.model;},
    r=>{delete r.proposal_receipt.intent_sha256;},r=>{delete r.proposal_receipt.receipt_sha256;},
    r=>{delete r.proposal_receipt.request_sha256;},r=>{delete r.proposal_receipt.context_sha256;},
    r=>{delete r.proposal_receipt.result_sha256;},r=>{r.proposal_receipt.result=null;},
    r=>{r.proposal_receipt.metadata.http_status=503;},r=>{delete r.proposal_receipt.metadata.response_id;},
    r=>{delete r.proposal_receipt.metadata.response_sha256;}
  ];
  for(const change of changes){const s=structuredClone(saved),receipt=currentReceipt(s);change(receipt);assert.equal(language.provenancePresentation({state:s}).label,'CasePath');}
  const old=structuredClone(saved);old.run_id='new-run';
  assert.equal(language.provenancePresentation({state:old,receipt:accepted}).label,'CasePath');
});

test('the actual reference packet proves fixed rules and zero provider calls',()=>{
  for(const state of recorded){
    const receipt=currentReceipt(state);
    assert.equal(receipt.reference_execution.config.mode,'deterministic_reference');
    assert.equal(receipt.reference_execution.config.provider_calls,0);
    assert.deepEqual(language.provenancePresentation({state}),{kind:'rules',label:'Fixed rules',model:null});
    for(const field of ['proposal_receipt','verifier_receipt'])assert.equal(receipt[field].provider_calls,0);
    const s=structuredClone(state),r=currentReceipt(s);
    r.reference_execution.config.provider_calls=1;
    assert.equal(language.provenancePresentation({state:s}).label,'CasePath');
    r.reference_execution.config.provider_calls=0;
    s.semantic_contexts[s.run_id].execution_mode='provider';
    assert.equal(language.provenancePresentation({state:s}).label,'CasePath','old reference data cannot label a current provider context');
  }
});

test('reference labels require numeric zero calls in the matching actual workflow receipts',()=>{
  const reference=recorded[0];
  for(const stage of ['interpret','verify']){
    assert.equal(language.provenancePresentation({state:reference},stage).label,'Fixed rules');
    const field=stage==='verify'?'verifier_receipt':'proposal_receipt';
    for(const mutate of [
      r=>{r.reference_execution.config.provider_calls=1;},r=>{delete r.reference_execution.config.provider_calls;},
      r=>{r.reference_execution.config.provider_calls='0';},r=>{r[field].provider_calls=1;},
      r=>{delete r[field].provider_calls;},r=>{r[field].provider_calls='0';},
      r=>{r[field].identity.workflow_id='another-run';},r=>{r[field].identity.claim_id='another-claim';},
      r=>{delete r[field];},r=>{r.reference_execution.config.contract='generic-mode';}
    ]){const state=structuredClone(reference);mutate(currentReceipt(state));assert.equal(language.provenancePresentation({state},stage).label,'CasePath');}
  }
  for(const calls of [0,1,'0',undefined]){
    const value={policy_id:'casepath.bounded-reference-assessment/1.0.0',
      source_outcome:{reference_provenance:{mode:'deterministic_reference',provider_calls:calls}}};
    assert.equal(language.provenancePresentation(value).label,'CasePath');
    assert.equal(language.knowledgePresentation(value).how,'CasePath');
    assert.equal(language.provenancePresentation({mode:'deterministic_reference',provider_calls:calls}).label,'CasePath');
    assert.equal(language.provenancePresentation({receipt:{reference_execution:{config:{mode:'deterministic_reference',provider_calls:calls}}}}).label,'CasePath');
  }
});

test('operation role mapping, unknown fallback and phase events preserve the recorded distinction',()=>{
  const cases=[
    ['fact.extract',{verification_required:true},'reader','Found a possible fact'],
    ['fact.extract',{verification_required:false},'checker','Checked it in the document'],
    ['verification.check',{},'checker','Checked it in the document'],
    ['document.check',{},'checker','Checked it in the document'],
    ['step.complete',{},'rulebook','Completed this step'],['decision',{},'rulebook','Reached a result'],
    ['document.require',{},'rulebook','Listed a needed document'],
    ['branch.activate',{},'rulebook','Followed this path'],['branch.drop',{},'rulebook','Ruled out this path'],
    ['knowledge.used',{},'memory','Reused the exact version'],['knowledge.reuse',{},'memory','Reused the exact version'],
    ['unknown.future.operation',{},'casepath','Recorded work']
  ];
  for(const [kind,result,roleId,label]of cases){
    const op={kind,result},before=JSON.stringify(op),view=language.operationPresentation(op,{state:saved});
    assert.equal(view.roleId,roleId);assert.equal(view.roleLabel,language.roles[roleId].label);assert.equal(view.label,label);
    shortCopy(view.now);shortCopy(view.label);shortCopy(view.how);assert.equal(view.details,op);assert.equal(JSON.stringify(op),before);
    const history=language.operationPresentation(op,{state:saved,history:true});
    assert.equal(history.now,`${view.roleLabel}: ${label.charAt(0).toLowerCase()+label.slice(1)}.`);
    if(['rulebook','memory'].includes(roleId))assert.equal(view.how,'Fixed rules');
  }
  for(const [phase,roleId]of [['acquiring','casepath'],['interpreting','reader'],['verifying','checker'],['progressing','rulebook'],['learning','memory'],['future','casepath']]){
    const view=language.operationPresentation({kind:'work.phase',payload:{phase}});assert.equal(view.roleId,roleId);shortCopy(view.now);
  }
  assert.equal(language.operationPresentation({kind:'source.open',stage:'interpret_reference'}).roleId,'reader');
  assert.equal(language.operationPresentation({kind:'source.open',stage:'verify_reference'}).roleId,'checker');
  assert.equal(language.operationPresentation({kind:'source.open',stage:'acquiring'}).roleId,'casepath');
  assert.equal(language.operationPresentation({kind:'branch.activate',result:{activation:'unresolved'}}).label,'Kept this path open');
});

test('all admitted stable step and document IDs have plain display labels',()=>{
  for(const template of templates){
    for(const node of template.process_catalog.nodes){assert.ok(language.stepLabels[node.node_id],node.node_id);shortCopy(language.stepLabel(node));}
    for(const doc of template.process_catalog.documents){assert.ok(language.documentLabels[doc.document_type],doc.document_type);shortCopy(language.documentTitle(doc));}
  }
  for(const catalog of ui.RELEASE_PROCEDURE_OUTLINE.catalogs){
    for(const node of catalog.nodes){assert.ok(language.stepLabels[node.node_id]);shortCopy(language.stepLabel(node));}
    for(const doc of catalog.documents){assert.ok(language.documentLabels[doc.document_type]);shortCopy(language.documentTitle(doc));}
  }
  for(const [label,expected]of [
    ['Establish landlord knowledge','Check the landlord knew'],['Assess supported cause','Check what caused it'],
    ['Record repair and rent reduction eligibility','Check if a repair and rent reduction apply'],
    ['Keep causation open until supported',"Don't decide the cause without proof"]
  ])assert.equal(language.stepLabel({node_id:'dh_cause',label}),expected);
  assert.equal(language.stepLabel({node_id:'future',label:'Derive a canonical branch'}),'Recorded step');
});

test('document titles are separate from original filenames and exact recorded wording',()=>{
  const doc={artifact_id:'source',file_name:'02-heating_service_report.txt'},before=JSON.stringify(doc);
  assert.equal(language.documentTitle(doc),'Heating service report');assert.equal(JSON.stringify(doc),before);
  assert.equal(language.documentTitle('01-lease_contract.pdf'),'Lease contract');
  assert.equal(language.documentTitle({file_name:'SHA_canonical_recipe.txt'}),'Supporting document');
  assert.equal(language.documentTitle({document_type:'termination_notice',file_name:'record-0001.txt'}),'Termination notice');
  const exact='The  landlord\n  first knew.  ';
  const op={kind:'fact.extract',source:{artifact_id:'source',quote:exact},result:{summary:exact,verification_required:true}};
  const view=language.operationPresentation(op,{documents:[doc]});
  assert.equal(view.recordedResult,exact);assert.equal(view.details.source.quote,exact);assert.equal(view.document,'Heating service report');
  assert.equal(language.plainLabel('  Exact  wording  '),'  Exact  wording  ');
});

test('source-less Memory, decisions and paths never inherit a selected document title',()=>{
  const documents=[{file_name:'01-customer-tenancy.txt'},{artifact_id:'real-source',file_name:'02-heating-service-report.txt'}];
  const context={documents,state:{source_descriptors:documents}},before=JSON.stringify(context);
  for(const kind of ['knowledge.used','knowledge.reuse','knowledge.add','knowledge.published','decision','branch.activate','branch.drop','branch.evaluate']){
    for(const source of [undefined,{}, {artifact_id:''}, {artifact_id:'real-source'}]){
      const operation={kind,source,input:{document_type:'heating_service_report'},object:{type:'document',id:'heating_service_report'}};
      assert.equal(language.operationPresentation(operation,context).document,'',`${kind} cannot inherit a document`);
    }
  }
  for(const kind of ['source.open','span.read','phrase.match','fact.extract','verification.check','document.check']){
    const source={artifact_id:'real-source',quote:'The  exact\nsource wording. '};
    const operation={kind,source},view=language.operationPresentation(operation,context);
    assert.equal(view.document,'Heating service report');assert.equal(view.details.source,source);
    assert.equal(view.details.source.quote,'The  exact\nsource wording. ');
    assert.equal(language.operationPresentation({...operation,source:undefined,input:{document_type:'heating_service_report'}},context).document,'');
    assert.equal(language.operationPresentation({...operation,source:{artifact_id:'missing-source'}},context).document,'');
    assert.equal(language.operationPresentation(operation,{documents:[],state:context.state}).document,'Heating service report');
  }
  const requireDocument={kind:'document.require',input:{document_type:'heating_service_report'},source:{artifact_id:'retired-source'}};
  assert.equal(language.operationPresentation(requireDocument,context).document,'Heating service report');
  assert.equal(language.operationPresentation({kind:'document.require',object:{type:'document',id:'lease_contract'}},context).document,'Lease contract');
  assert.equal(language.operationPresentation({kind:'document.require'},context).document,'');
  assert.equal(JSON.stringify(context),before);
});

test('outcome summaries follow only recorded checks, open facts, gaps and authority limits',()=>{
  const reference=recorded[0],before=JSON.stringify(reference),view=language.outcomePresentation(reference);
  assert.equal(view.summary,'The checks support repair and rent reduction eligibility.');assert.equal(view.recordedSummary,reference.outcome.summary);
  assert.equal(view.support,'Supported by the documents.');
  assert.deepEqual(view.constraints,['Real-world action still needs its own authority.']);
  assert.equal(view.nextAction,"A person's go-ahead is needed before any real-world action.");
  assert.equal(JSON.stringify(reference),before);
  assert.equal(language.outcomePresentation(saved).summary,'Some facts still need proof.');
  const sameSummary=structuredClone(reference);delete sameSummary.outcome.legal_predicates;
  assert.equal(language.outcomePresentation(sameSummary).summary,'A result is recorded.','a legal-sounding sentence cannot supply predicate support');
  for(const change of [
    s=>{s.outcome.legal_predicates[0].status='unknown';},s=>{s.outcome.assessment_status='incomplete';},
    s=>{s.outcome.missing_evidence=[{document_type:'lease_contract'}];},s=>{s.outcome.unresolved_facts=[{fact_id:'open'}];}
  ]){const s=structuredClone(reference);change(s);assert.equal(language.outcomePresentation(s).summary,'Repair and rent reduction eligibility remain open.');}
  const failed=structuredClone(reference);failed.outcome.legal_predicates[0].status='failed';
  assert.equal(language.outcomePresentation(failed).summary,'Repair and rent reduction eligibility remain open.','failed tenancy scope cannot establish eligibility');
  assert.equal(language.outcomePresentation({}).summary,'No result is recorded yet.');
  for(const state of [reference,saved,{},sameSummary,{deferral:{reason:'An actual recorded reason.'}}]){
    const result=language.outcomePresentation(state);for(const key of ['label','summary','nextAction'])shortCopy(result[key]);
    assert.doesNotMatch(result.summary,/\b(?:repaired|paid|awarded|filed|sent|approved)\b/iu);
  }
});

test('outcome next actions separate complete document checks from authority to act',()=>{
  const expected="A person's go-ahead is needed before any real-world action.";
  for(const state of recorded){
    assert.equal(state.outcome.assessment_status,'complete');
    assert.deepEqual(state.outcome.missing_evidence,[]);assert.deepEqual(state.outcome.unresolved_facts,[]);
    assert.ok(state.outcome.authority_limits.length);
    const view=assertNextAction(state,expected);
    assert.equal(view.summary,'The checks support repair and rent reduction eligibility.');
    assert.equal(view.support,'Supported by the documents.');
    assert.deepEqual(view.constraints,['Real-world action still needs its own authority.']);
  }
  // Unit cases use the actual predicate IDs and statuses, not recorded notice workflows.
  for(const [family,predicates,summary]of [
    ['termination',[['residential_tenancy_scope','supported'],['issuer_authority_and_received_packet','supported'],
      ['complete_channel_archive','supported'],['canton_approved_form','failed']],
    'The termination notice is missing the required official form.'],
    ['rent',[['residential_tenancy_scope','supported'],['ordinary_non269c_tenancy','supported'],
      ['issuer_authority_and_complete_packet','supported'],['contemporaneous_substantive_reasons','failed'],
      ['later_email_is_not_original_reasons','supported']],
    'The rent increase notice is missing reasons supplied with the notice.']
  ]){
    const state={outcome:{assessment_status:'complete',status:'deferred',summary:`The  exact\n${family} unit summary. `,
      legal_predicates:predicates.map(([predicate_id,status])=>({predicate_id,status})),
      missing_evidence:[],unresolved_facts:[],authority_limits:['Separate authority is needed for real-world action.']}};
    const view=assertNextAction(state,expected);
    assert.equal(view.summary,summary);assert.equal(view.support,'Supported by the documents.');
    assert.deepEqual(view.constraints,['Real-world action still needs its own authority.']);
    assert.doesNotMatch(view.nextAction,/\b(?:documents|proof|approved|sent|filed|paid|awarded)\b/iu);
  }
});

test('outcome next actions retain every combination of recorded wait causes',async t=>{
  // Each input below is a unit case, including the deliberately incomplete records.
  for(const field of ['outcome','deferral'])for(let mask=0;mask<16;mask++){
    await t.test(`${field}: cause mask ${mask}`,()=>{
      const missing=Boolean(mask&1),unresolved=Boolean(mask&2),unknown=Boolean(mask&4),limits=Boolean(mask&8);
      const value={status:'deferred',assessment_status:'complete',summary:'The  exact\nrecorded unit summary. ',
        legal_predicates:[{predicate_id:'residential_tenancy_scope',status:unknown?'unknown':'supported',
          citations:[{quote:'The  exact\nsource quote. '}]}],
        missing_evidence:missing?[{document_type:'lease_contract'}]:[],unresolved_facts:unresolved?[{fact_id:'open'}]:[],
        authority_limits:limits?['Separate authority is needed for real-world action.']:[]};
      const expected=[missing?'Waiting for the listed documents.':'',unresolved||unknown?'Waiting for proof of open facts.':'',
        limits?"A person's go-ahead is needed before any real-world action.":''].filter(Boolean).join(' ') || 'Review the case details.';
      assertNextAction({[field]:value},expected);
    });
  }
});

test('outcome next actions retain unknown checks without inventing document or authority gaps',async t=>{
  for(const status of ['unknown','pending','true','false',true,false,null,undefined,'unexpected']){
    await t.test(`unit predicate status ${String(status)} (${typeof status})`,()=>{
      const state={outcome:{assessment_status:'complete',legal_predicates:[{predicate_id:'canton_approved_form',status}],
        missing_evidence:[],unresolved_facts:[],authority_limits:[]}};
      assertNextAction(state,'Waiting for proof of open facts.');
    });
  }
  const duplicate={outcome:{legal_predicates:[{predicate_id:'canton_approved_form',status:'supported'},
    {predicate_id:'canton_approved_form',status:'failed'}]}};
  assertNextAction(duplicate,'Waiting for proof of open facts.');
  for(const status of ['supported','failed']){
    const unmapped={outcome:{assessment_status:'complete',legal_predicates:[{predicate_id:'future_check',status}]}};
    assertNextAction(unmapped,'Review the case details.');
    unmapped.outcome.authority_limits=['Separate authority is needed for real-world action.'];
    assertNextAction(unmapped,"A person's go-ahead is needed before any real-world action.");
  }
});

test('outcome next actions stay neutral when no result or wait cause is recorded',()=>{
  for(const state of [{},{outcome:{}},{outcome:{status:'deferred'}},{deferral:{}},
    {deferral:{reason:'The  exact\nrecorded reason. '}},
    {outcome:{status:'deferred',assessment_status:'complete',missing_evidence:[],unresolved_facts:[],authority_limits:[]}},
    {outcome:{status:'complete',assessment_status:'complete',summary:'The  exact\nrecorded unit summary. '}}]){
    assertNextAction(state,'Review the case details.');
  }
});

test('official form and original reasons findings preserve supported, failed and unknown meanings',()=>{
  const cases=[
    ['canton_approved_form','supported','The termination notice has the required official form.'],
    ['canton_approved_form','failed','The termination notice is missing the required official form.'],
    ['canton_approved_form','unknown','Whether the termination notice uses the required official form is still unknown.'],
    ['contemporaneous_substantive_reasons','supported','The rent increase notice includes reasons supplied with the notice.'],
    ['contemporaneous_substantive_reasons','failed','The rent increase notice is missing reasons supplied with the notice.'],
    ['contemporaneous_substantive_reasons','unknown','Whether reasons came with the rent increase notice is still unknown.']
  ];
  for(const [predicate_id,status,summary]of cases){
    const state={outcome:{assessment_status:'complete',status:'deferred',legal_predicates:[{predicate_id,status}],
      summary:'The  exact\nrecorded summary. ',missing_evidence:[{document_type:'lease_contract'}],unresolved_facts:[{fact_id:'open'}],authority_limits:['Exact recorded limit.']}},before=JSON.stringify(state);
    const view=language.outcomePresentation(state);
    assert.equal(view.summary,summary);shortCopy(view.summary);
    assert.deepEqual(view.findings,[{id:predicate_id,status,summary}]);
    assert.equal(view.recordedSummary,state.outcome.summary);
    assert.deepEqual(view.constraints,['More documents are needed.','Some facts still need proof.','Real-world action still needs its own authority.']);
    assert.equal(view.nextAction,"Waiting for the listed documents. Waiting for proof of open facts. A person's go-ahead is needed before any real-world action.");
    assert.equal(JSON.stringify(state),before);
    assert.doesNotMatch(view.summary,/\b(?:valid|invalid|awarded|paid|sent|filed|excessive)\b/iu,'a specific check cannot assert a legal outcome or completed action');
  }
});

test('every declared legal predicate has distinct supported, failed and unknown display findings',()=>{
  const definitions=fs.readFileSync(path.join(root,'casepath-api/casepath_api/autonomous_reference_v1.py'),'utf8');
  const ids=[...definitions.matchAll(/\bpredicate\('([^']+)'/gu)].map(match=>match[1]);
  assert.equal(new Set(ids).size,12);
  for(const predicate_id of ids){
    const summaries=[];
    for(const status of ['supported','failed','unknown']){
      const state={outcome:{legal_predicates:[{predicate_id,status}],assessment_status:'complete'}};
      const view=language.outcomePresentation(state);
      assert.equal(view.findings.length,1,predicate_id);assert.equal(view.findings[0].id,predicate_id);
      assert.equal(view.findings[0].status,status);shortCopy(view.findings[0].summary);shortCopy(view.summary);
      summaries.push(view.findings[0].summary);
    }
    assert.equal(new Set(summaries).size,3,`${predicate_id} must retain all three recorded meanings`);
  }
  for(const status of ['true','false',true,false,null,'unexpected']){
    const view=language.outcomePresentation({outcome:{legal_predicates:[{predicate_id:'canton_approved_form',status}],assessment_status:'complete'}});
    assert.equal(view.findings[0].status,'unknown');assert.match(view.summary,/unknown/);
  }
  const unknown=language.outcomePresentation({outcome:{legal_predicates:[{predicate_id:'new_future_predicate',status:'supported'}],assessment_status:'complete',summary:'The notice is invalid.'}});
  assert.equal(unknown.summary,'A result is recorded.');assert.deepEqual(unknown.findings,[]);
  const conflict=language.outcomePresentation({outcome:{legal_predicates:[{predicate_id:'canton_approved_form',status:'supported'},{predicate_id:'canton_approved_form',status:'failed'}]}});
  assert.equal(conflict.findings[0].status,'unknown');assert.match(conflict.summary,/unknown/);
});

test('repair eligibility needs every recorded defect check and never implies work was performed',()=>{
  for(const predicate of recorded[0].outcome.legal_predicates){
    for(const status of ['failed','unknown']){
      const state=structuredClone(recorded[0]);state.outcome.legal_predicates.find(row=>row.predicate_id===predicate.predicate_id).status=status;
      assert.equal(language.outcomePresentation(state).summary,'Repair and rent reduction eligibility remain open.');
    }
    const state=structuredClone(recorded[0]);state.outcome.legal_predicates=state.outcome.legal_predicates.filter(row=>row.predicate_id!==predicate.predicate_id);
    assert.equal(language.outcomePresentation(state).summary,'Repair and rent reduction eligibility remain open.');
  }
  for(const state of recorded){const view=language.outcomePresentation(state);assert.match(view.summary,/eligibility/);assert.doesNotMatch(view.summary,/\b(?:completed|repaired|awarded|paid|sent|filed)\b/iu);}
});

test('knowledge reports rule combinations separately from reuse and preserves actual rejection reasons',()=>{
  const version=saved.knowledge_published[0],before=JSON.stringify(version),view=language.knowledgePresentation(version);
  assert.equal(view.ruleChecks,243);assert.equal(view.reuseCount,null);assert.equal(view.avoidedBuilds,null);
  assert.equal(view.how,'CasePath','a source outcome without provider receipts cannot invent a model');
  assert.equal(view.label,'Saved for reuse');assert.equal(JSON.stringify(version),before);
  for(const state of recorded)for(const version of state.knowledge_published){assert.equal(language.knowledgePresentation(version).how,'CasePath','a retained source outcome does not preserve an explicit zero-call receipt');}
  const changed=structuredClone(version);changed.change_reason='Requalified the procedure against the current admitted rule version.';
  assert.equal(language.knowledgePresentation(changed).label,'Rechecked');
  const rejected={knowledge_id:'quarantine.test',qualification:{status:'quarantined',reason:'The exact recorded  source check failed.\nNo source was saved.'}};
  const rejectedView=language.knowledgePresentation(rejected);
  assert.equal(rejectedView.label,'Not saved');assert.equal(rejectedView.status,'not_saved');assert.equal(rejectedView.reason,rejected.qualification.reason);
  const use={kind:'knowledge.used',claim_id:saved.claim_id,avoided_rule_compilations:1};
  const used=language.knowledgePresentation(version,use);assert.equal(used.reuseCount,1);assert.equal(used.avoidedBuilds,1);assert.equal(used.ruleChecks,243);
  assert.deepEqual(language.tabs.map(row=>row.label),['Steps','Facts it needs','Documents','Special cases','What changed']);
});

test('all fixed display strings avoid restricted terms and stay within twenty words',()=>{
  for(const value of Object.values(language.copy))shortCopy(value);
  for(const value of Object.values(language.stepLabels))shortCopy(value);
  for(const value of Object.values(language.documentLabels))shortCopy(value);
  for(const tab of language.tabs)shortCopy(tab.label);
  for(const bad of ['provisional','derive','requalified','quarantined','compilation','recipe','applicability','regression','sha','hash','canonical','projection','branch','pinned','deterministic','verifier','synthetic'])shortCopy(language.plainLabel(`A ${bad} label`));
  for(const state of [saved,...recorded]){
    for(const version of state.knowledge_published){const value=language.knowledgePresentation(version);for(const key of ['label','roleLabel','how','versionLabel'])shortCopy(value[key]);}
  }
});

test('every actual operation in the committed replay has short display copy and preserves its record',()=>{
  const entry=packet.claims[0].operations,bytes=Buffer.from(expand(entry.root));
  assert.equal(bytes.length,entry.bytes);
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),entry.sha256);
  const operations=bytes.toString('utf8').trim().split('\n').map(JSON.parse).filter(row=>row.type==='operation');
  assert.ok(operations.length>100,'the test must exercise the recorded operation stream');
  const state=recorded[0],before=crypto.createHash('sha256').update(JSON.stringify(operations)).digest('hex');
  for(const operation of operations){
    const view=language.operationPresentation(operation,{state});
    for(const key of ['roleLabel','label','action','now','how','document'])shortCopy(view[key]);
    assert.equal(view.details,operation);
    assert.equal(view.recordedResult,operation.result?.summary || operation.result?.reason || '');
    if(view.roleId==='reader'||view.roleId==='checker')assert.equal(view.how,'Fixed rules');
    if(operation.kind==='fact.extract')assert.equal(view.roleId,operation.result.verification_required===false?'checker':'reader');
  }
  assert.equal(crypto.createHash('sha256').update(JSON.stringify(operations)).digest('hex'),before);
});


test('settled defect limits stay visible only when the exact recorded scope and sentence support them',()=>{
  for(const state of recorded){
    assert.equal(language.outcomePresentation(state).openItems,'Repair, the reduction amount and any award remain undetermined.');
    const altered=structuredClone(state);altered.outcome.summary='A different recorded finding.';
    assert.equal(language.outcomePresentation(altered).openItems,'');
    altered.outcome.summary=state.outcome.summary;delete altered.outcome.assessment_scope;
    assert.equal(language.outcomePresentation(altered).openItems,'');
    const html=ui.workMarkup(state,{},state.graph.nodes[0].node_id,[], 'step',{}, {readOnly:true});
    assert.match(html,/class="au-outcome-open">Repair, the reduction amount and any award remain undetermined/);
    assert.equal((html.match(/class="au-role-badge"/g)||[]).length,1);
    assert.doesNotMatch(html,/no recorded method|Waiting for the listed documents/);
  }
});

test('refusal labels explain the recorded cause while unknown reasons remain in Details',()=>{
  assert.equal(language.refusalReason('knowledge candidate is not bound to a verified sufficient supporting file'),'A checked supporting document was not linked to these steps.');
  assert.equal(language.refusalReason('The independent verifier rejected this knowledge candidate.'),'The independent check rejected these steps.');
  assert.equal(language.refusalReason('Another unknown cause'),'These steps were not saved. Open Details for the recorded reason.');
});

test('the mode line names original intake, saved result, replay, live and view only; added cases are never fictional',()=>{
  const at='2026-10-19T21:18:51.039329+00:00',rules={mode:'deterministic_reference'};
  const lines={
    original:language.modeLine({revision:0,presentation:'saved',origin:'canonical_original'}),
    saved:language.modeLine({revision:39,presentation:'saved',origin:'canonical_original'}),
    replay:language.modeLine({revision:39,presentation:'replay',provenance:rules,origin:'featured',recordedAt:at}),
    replayModel:language.modeLine({revision:39,presentation:'replay',provenance:{mode:'model'},origin:'featured',recordedAt:at}),
    live:language.modeLine({revision:4,presentation:'live',origin:'canonical_original'}),
    added:language.modeLine({revision:4,presentation:'saved',origin:'native_intake'}),
    viewOnly:language.modeLine({revision:39,presentation:'replay',provenance:rules,origin:'featured',recordedAt:at,readOnly:true})
  };
  assert.equal(lines.original,'Original intake · not run · Fictional case');
  assert.equal(lines.saved,'Saved result · revision 39 · Fictional case');
  assert.equal(lines.replay,'Replay · recorded 19 Oct 2026 · fixed rules · Fictional case');
  assert.equal(lines.replayModel,'Replay · recorded 19 Oct 2026 · Fictional case','only a fixed-rule history says fixed rules');
  assert.equal(lines.live,'Live · Fictional case');
  assert.equal(lines.added,'Saved result · revision 4');
  assert.equal(lines.viewOnly,'Replay · recorded 19 Oct 2026 · fixed rules · Fictional case · View only');
  assert.equal(new Set(Object.values(lines)).size,Object.keys(lines).length);
  for(const presentation of ['saved','replay','live'])for(const revision of [0,1,48])for(const readOnly of [false,true]){
    const line=language.modeLine({revision,presentation,provenance:rules,origin:'native_intake',recordedAt:at,readOnly});
    assert.doesNotMatch(line,/Fictional/,'an added case is never called fictional');shortCopy(line);
  }
  assert.equal(language.modeLine({revision:0,presentation:'replay',provenance:rules,origin:'featured',recordedAt:at}),'Original intake · not run · Fictional case','a revision-zero head is never a replay');
  assert.equal(language.modeLine({presentation:'replay'}),'Replay','an unknown recording date is not invented');
  assert.doesNotMatch(Object.values(lines).join(' '),/No real-world action/,'the safety note lives in the reading guide');
  assert.match(language.copy.noRealWorldAction,/^No real-world action\./);
});

test('saved journal events read as past-tense work by the recorded role',()=>{
  assert.deepEqual(language.eventPresentation({kind:'outcome.recorded'}),{roleId:'rulebook',roleLabel:'Rulebook',past:'saved the result'});
  assert.deepEqual(language.eventPresentation({kind:'work.phase',payload:{phase:'verifying'}}),{roleId:'checker',roleLabel:'Checker',past:'checked the proposed wording'});
  assert.equal(language.eventPresentation({kind:'knowledge.published',payload:{knowledge:{qualification:{status:'qualified'}}}}).past,'saved steps for reuse');
  assert.equal(language.eventPresentation({kind:'knowledge.published',payload:{knowledge:{qualification:{status:'quarantined'}}}}).past,'did not save the steps');
  assert.deepEqual(language.eventPresentation({kind:'unknown.kind'}),{roleId:'casepath',roleLabel:'CasePath',past:'recorded work'});
  for(const kind of ['intake','sources.arrived','work.started','interpretation.accepted','action.completed','work.deferred','knowledge.used','reconciliation.failed'])shortCopy(language.eventPresentation({kind}).past);
});

test('recorded outcome fields lead and the draft line follows only its own record',()=>{
  const before=JSON.stringify(saved),view=language.outcomePresentation(saved);
  assert.equal(view.recorded.summary,saved.outcome.summary);assert.deepEqual(view.recorded.issues,saved.outcome.issues);
  assert.deepEqual(view.recorded.openFacts,['Rent arrears','Tenancy extension','Family home','Retaliation concern','Termination received']);
  assert.equal(view.recorded.nextAction,saved.outcome.next_action);assert.deepEqual(view.recorded.missing,[]);assert.deepEqual(view.recorded.limits,[]);
  assert.deepEqual(view.recorded.draft,{status:'no_gap',label:'No active document gap identified'});
  assert.equal(view.summary,'Some facts still need proof.','the templated fallback is unchanged');assert.equal(JSON.stringify(saved),before);
  for(const state of recorded){
    const shown=language.outcomePresentation(state);
    assert.deepEqual(shown.recorded.draft,{status:'',label:''},'a completed fixed-rule assessment drafted nothing to send');assert.deepEqual(shown.recorded.limits,state.outcome.authority_limits);
    assert.ok(shown.recorded.summary.includes(shown.openItems),'the recorded limit stays inside the recorded sentence');
  }
  const draft={status:'prepared_not_sent',body:'No additional active document gap was identified.'};
  assert.equal(language.draftStatus({missing_evidence:[{document_type:'lease_contract'}],request_draft:draft}).status,'draft','a listed missing document is never described as no gap');
  assert.equal(language.draftStatus({request_draft:draft}).status,'draft','an unrecorded missing list is not an empty one');
  assert.deepEqual(language.draftStatus({summary:' Recorded summary. ',missing_evidence:[],request_draft:{status:'prepared_not_sent',body:'Recorded summary.'}}),{status:'',label:''},'a draft that repeats the summary is not a request');
  assert.deepEqual(language.draftStatus({assessment_status:'complete',reference_provenance:{mode:'deterministic_reference'},missing_evidence:[],request_draft:{status:'prepared_not_sent',body:'Other wording.'}}),{status:'',label:''});
  assert.equal(language.draftStatus({summary:'Recorded summary.',missing_evidence:[],request_draft:{status:'prepared_not_sent',body:'Please send the lease.'}}).label,'Draft ready · not sent');
  assert.deepEqual(language.draftStatus({}),{status:'',label:''});assert.deepEqual(language.draftStatus({request_draft:{status:'unexpected'}}),{status:'recorded',label:'Draft recorded'});
  assert.deepEqual(language.outcomePresentation({outcome:{issues:[{code:'source_discrepancy',reason:'Recorded discrepancy.'},'  ',null]}}).recorded.issues,['Recorded discrepancy.']);
});

test('fact labels name the subject without field identifiers',()=>{
  assert.equal(language.factLabel({fact_id:'condition:family_home',label:'family home'}),'Family home');
  assert.equal(language.factLabel('condition:arrears'),'Rent arrears');
  assert.equal(language.factLabel({fact_id:'fact:tenancy_terms_evidence',label:'Relevant residential tenancy terms, parties and dwelling; this is not a complete lease contract'}),'Relevant residential tenancy terms, parties and dwelling');
  assert.equal(language.factLabel({fact_id:'fact:landlord_knowledge_evidence',label:'INTERNAL_FACT_FIELD'}),'Landlord notice and repair status');
  assert.equal(language.factLabel({fact_id:'unknown'}),'Recorded fact');
});
