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

test('outcome summaries follow only recorded checks, open facts, gaps and authority limits',()=>{
  const reference=recorded[0],before=JSON.stringify(reference),view=language.outcomePresentation(reference);
  assert.equal(view.summary,'Supported by the documents.');assert.equal(view.recordedSummary,reference.outcome.summary);
  assert.equal(view.nextAction,"Waiting for the listed documents or a person's go-ahead.");
  assert.equal(JSON.stringify(reference),before);
  assert.equal(language.outcomePresentation(saved).summary,'Some facts still need proof.');
  const sameSummary=structuredClone(reference);delete sameSummary.outcome.legal_predicates;
  assert.equal(language.outcomePresentation(sameSummary).summary,'A result is recorded.','a legal-sounding sentence cannot supply predicate support');
  for(const change of [
    s=>{s.outcome.legal_predicates[0].status='unknown';},s=>{s.outcome.assessment_status='incomplete';},
    s=>{s.outcome.missing_evidence=[{document_type:'lease_contract'}];},s=>{s.outcome.unresolved_facts=[{fact_id:'open'}];}
  ]){const s=structuredClone(reference);change(s);assert.notEqual(language.outcomePresentation(s).summary,'Supported by the documents.');}
  const failed=structuredClone(reference);failed.outcome.legal_predicates[0].status='failed';
  assert.equal(language.outcomePresentation(failed).summary,'Supported by the documents.','a recorded negative predicate is not a completed real-world action');
  assert.equal(language.outcomePresentation({}).summary,'No result is recorded yet.');
  for(const state of [reference,saved,{},sameSummary,{deferral:{reason:'An actual recorded reason.'}}]){
    const result=language.outcomePresentation(state);for(const key of ['label','summary','nextAction'])shortCopy(result[key]);
    assert.doesNotMatch(result.summary,/\b(?:repaired|paid|awarded|filed|sent|approved)\b/iu);
  }
});

test('knowledge reports rule combinations separately from reuse and preserves actual rejection reasons',()=>{
  const version=saved.knowledge_published[0],before=JSON.stringify(version),view=language.knowledgePresentation(version);
  assert.equal(view.ruleChecks,243);assert.equal(view.reuseCount,null);assert.equal(view.avoidedBuilds,null);
  assert.equal(view.how,'CasePath','a source outcome without provider receipts cannot invent a model');
  assert.equal(view.label,'Saved for reuse');assert.equal(JSON.stringify(version),before);
  for(const state of recorded)for(const version of state.knowledge_published){assert.equal(language.knowledgePresentation(version).how,'Fixed rules');}
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
