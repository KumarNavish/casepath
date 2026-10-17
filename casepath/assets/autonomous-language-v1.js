/* Display-only language for records that the caller has already validated. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.CasepathLanguage = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';

  const list = value => Array.isArray(value) ? value : [];
  const text = value => typeof value === 'string' ? value : '';
  const seal = value => /^[a-f0-9]{64}$/i.test(text(value));
  const count = value => Number.isSafeInteger(value) && value >= 0 ? value : null;
  const banned = /\b(?:provisional|derive|requalified|quarantined|compilation|recipe|applicability|regression|sha|hash|canonical|projection|branch|pinned|deterministic|verifier|synthetic)\b/iu;
  const safe = value => Boolean(text(value).trim()) && !banned.test(value) && value.trim().split(/\s+/u).length <= 20;
  const roles = Object.freeze(Object.fromEntries([
    ['reader','Reader','Proposes facts, paths and wording from the documents.'],
    ['checker','Checker','Checks the proposed wording against the exact sources.'],
    ['rulebook','Rulebook','Uses fixed rules to act on confirmed wording.'],
    ['memory','Memory','Uses fixed rules to recheck, reuse and save procedures after their checks pass.'],
    ['casepath','CasePath','Shows the recorded work and reads the supplied files.']
  ].map(([id,label,description]) => [id,Object.freeze({id,label,description})])));

  // IDs and original labels stay in the records; these strings are display labels only.
  const stepLabels = Object.freeze({
    dh_intake:'Read the reported defect', dh_safety:'Check for an urgent safety risk',
    dh_scope:'Check the tenancy and defect dates', dh_notice:'Check the landlord knew',
    dh_cause:'Check what caused it', dh_evidence:'Check the defect evidence',
    dh_response:'Check the landlord response and access', dh_specialist:'List the technical inspection needed',
    dh_deposit:'Check the safeguards for paying rent into an official account',
    dh_resolution:'Record the repair or referral result', dh_close:'Close or hand over the case',
    lt_intake:'Read who sent the notice and when it arrived', lt_deadline:'Check the time limit',
    lt_form:'Check the notice form and delivery', lt_type:'Check the type of termination',
    lt_arrears:'Check the unpaid rent and payment warning', lt_family:'Check separate delivery to each spouse',
    lt_abuse:'Check the stated reason and fairness concerns', lt_extension:'Check the evidence for more time',
    lt_evidence:'List the evidence needed for this notice', lt_resolution:'Prepare the next option',
    lt_close:'Record the termination result', ri_intake:'Read the rent increase and arrival date',
    ri_deadline:'Check the time limit', ri_form:'Check the notice form and timing',
    ri_reason:'Check the stated reason', ri_reference:'Check the reference rate calculation',
    ri_renovation:'Check the renovation costs', ri_evidence:'List the calculation evidence needed',
    ri_assessment:'Check what is supported and what remains open', ri_resolution:'Prepare the next option',
    ri_close:'Record the result'
  });
  const labels = Object.freeze({
    'Establish landlord knowledge':'Check the landlord knew',
    'Establish landlord notice':'Check the landlord knew',
    'Assess supported cause':'Check what caused it',
    'Record repair and rent reduction eligibility':'Check if a repair and rent reduction apply',
    'Keep causation open until supported':"Don't decide the cause without proof",
    'Establish relevant tenancy terms':'Check the relevant tenancy terms',
    'Assess objective defect evidence':'Check the defect evidence',
    'Capture the reported defect':'Read the reported defect',
    'Capture the received termination packet':'Read the received notice',
    'Assess whether the termination notice is valid':'Check if the termination notice is valid',
    'Capture the original increase packet':'Read the rent increase notice',
    'Assess notification context':'Check how the notice arrived',
    'Assess whether the increase notice is valid':'Check if the increase notice is valid',
    'Relevant ordinary tenancy terms':'Relevant tenancy terms',
    'Landlord knowledge and continuing repair status':'Landlord notice and repair status',
    'Dated technical defect observation':'Dated defect report',
    'Who sent the notice and how it arrived':'Notice sender and delivery',
    'Reasons supplied with the increase notice':'Reasons sent with the rent increase',
    'Qualified':'Checked for reuse', 'Requalified':'Rechecked', 'Quarantined':'Not saved',
    'Provisional':'Needs a source check', 'Applicability':'When it applies',
    'Evidence recipes':'Document checks', 'Pinned version':'Exact version used',
    'Regression cases':'Rule checks', 'Canonical original':'Original case',
    'Synthetic claim':'Fictional case', 'Read only':'View only'
  });
  const documentLabels = Object.freeze({
    tenancy_terms_evidence:'Relevant tenancy terms', landlord_knowledge_evidence:'Landlord notice and repair status',
    objective_defect_observation:'Dated defect report', received_termination_packet:'Received termination notice',
    original_notification_context:'Notice sender and delivery', received_rent_increase_packet:'Received rent increase notice',
    lease_contract:'Lease contract', defect_notification:'Defect notice', proof_of_notification:'Proof the landlord was told',
    dated_photos:'Dated photographs', landlord_response_history:'Landlord replies',
    humidity_temperature_log:'Humidity and temperature log', heating_service_report:'Heating service report',
    medical_confirmation:'Medical confirmation', technical_inspection:'Technical inspection',
    written_repair_deadline:'Written repair deadline', caretaker_correspondence:'Caretaker messages',
    termination_notice:'Termination notice', proof_of_receipt:'Proof of delivery',
    notice_period_evidence:'Notice period evidence', stated_reason:'Stated termination reason',
    spouse_notice_copy:'Separate notice for the spouse', payment_deadline_letter:'Payment warning with a deadline',
    rent_ledger_payment_evidence:'Rent account and payment records', prior_rights_correspondence:'Earlier messages about tenancy rights',
    housing_search_log:'Housing search log', landlord_correspondence:'Landlord messages',
    rent_increase_notice:'Rent increase notice', current_rent_evidence:'Current rent evidence',
    prior_rent_adjustment:'Earlier rent change', stated_calculation:'Stated reasons and calculation',
    reference_rate_basis:'Reference rate details', renovation_cost_breakdown:'Renovation cost breakdown'
  });
  const tabs = Object.freeze([
    ['process','Steps'], ['facts','Facts it needs'], ['documents','Documents'],
    ['exceptions','Special cases'], ['changes','What changed']
  ].map(([id,label]) => Object.freeze({id,label})));
  const copy = Object.freeze({
    replay:'Replay · Fictional case · No real-world action', viewOnly:'View only',
    supported:'Supported by the documents.', waiting:"Waiting for the listed documents or a person's go-ahead.",
    draft:'Draft ready, not sent.', documentChecks:'Document checks', whenItApplies:'When it applies',
    exactVersion:'Exact version used', ruleChecks:'Rule checks', reused:'Times reused instead of rebuilding'
  });

  function plainLabel(value, fallback = 'Recorded item') {
    const original = typeof value === 'string' ? value : text(value?.label) || text(value?.title);
    const replacement = labels[original] || documentLabels[original] || stepLabels[original];
    return replacement || (safe(original) ? original : safe(fallback) ? fallback : 'Recorded item');
  }
  function stepLabel(node) {
    if (typeof node === 'string') return labels[node] || stepLabels[node] || plainLabel(node,'Recorded step');
    return labels[text(node?.label)] || stepLabels[text(node?.node_id)] || plainLabel(node,'Recorded step');
  }
  function documentTitle(document) {
    if (typeof document === 'string') document = documentLabels[document] ? {document_type:document}
      : /\.[a-z0-9]{1,8}$/iu.test(document) ? {file_name:document} : {label:document};
    if (!document || typeof document !== 'object') return 'Supporting document';
    if (documentLabels[document.document_type]) return documentLabels[document.document_type];
    if (document.role === 'customer_message') return 'Case message';
    if (document.label) return plainLabel(document.label,'Supporting document');
    const file = text(document.file_name).split(/[\\/]/u).at(-1) || '';
    const title = file.replace(/\.[a-z0-9]{1,8}$/iu,'').replace(/^\d+[-_ ]+/u,'').replace(/[-_]+/gu,' ');
    if (/heating.*(?:report|service)|(?:report|service).*heating/iu.test(title)) return 'Heating service report';
    if (/tenancy.*(?:clarification|terms)|(?:clarification|terms).*tenancy/iu.test(title)) return 'Tenancy details';
    if (/termination.*notice|notice.*termination/iu.test(title)) return 'Termination notice';
    if (/rent.*increase|increase.*rent/iu.test(title)) return 'Rent increase notice';
    if (/sole packet|notification packet/iu.test(title)) return 'Notice and delivery details';
    return safe(title) ? title.charAt(0).toUpperCase()+title.slice(1) : 'Supporting document';
  }

  function acceptedReceipt(context) {
    const state = context?.state;
    const receipt = context?.receipt || [...list(state?.receipts)].reverse()
      .find(row => row.kind === 'interpretation.accepted' && (!state.run_id || row.receipt?.workflow_id === state.run_id))?.receipt;
    if (state?.run_id && receipt?.workflow_id !== state.run_id) return null;
    return receipt || null;
  }
  function providerCall(receipt, stage) {
    const call = stage === 'verify' ? receipt?.verifier_receipt : receipt?.proposal_receipt;
    // These are the persisted provider-result fields, not configured model hints.
    return call?.contract === 'casepath.autonomous-provider-result/1.0.0' && call.status === 'completed'
      && call.stage === stage && typeof receipt.workflow_id === 'string' && call.workflow_id === receipt.workflow_id
      && /^[^\s/]+\/[^\s]+$/u.test(text(call.model)) && seal(call.receipt_sha256) && seal(call.intent_sha256)
      && seal(call.request_sha256) && seal(call.context_sha256) && seal(call.result_sha256)
      && call.result && typeof call.result === 'object' && call.metadata?.http_status === 200
      && Boolean(text(call.metadata.response_id)) && seal(call.metadata.response_sha256) ? call : null;
  }
  function provenancePresentation(context = {}, stage = 'interpret') {
    const receipt = acceptedReceipt(context), state = context.state;
    const current = state?.run_id ? state.semantic_contexts?.[state.run_id] : null;
    const reference = receipt?.reference_execution?.config;
    const call = providerCall(receipt,stage);
    if (call) return {kind:'model',label:`AI model: ${call.model}`,model:call.model};
    if (reference?.mode === 'deterministic_reference' && reference.provider_calls === 0
      && (!current || current.execution_mode === 'deterministic_reference')) return {kind:'rules',label:'Fixed rules',model:null};
    // Knowledge retains its source outcome, but does not inherit an absent model receipt.
    if (context.source_outcome?.reference_provenance?.mode === 'deterministic_reference'
      && context.policy_id === 'casepath.bounded-reference-assessment/1.0.0') return {kind:'rules',label:'Fixed rules',model:null};
    return {kind:'unknown',label:'CasePath',model:null};
  }

  const operations = Object.freeze({
    'source.open':['casepath','Opened a document','opens a document'],
    'span.read':['reader','Read a passage','reads a passage'],
    'phrase.match':['reader','Looked for source wording','looks for source wording'],
    'fact.extract':['reader','Found a possible fact','finds a possible fact'],
    'verification.check':['checker','Checked it in the document','checks it in the document'],
    'document.check':['checker','Checked it in the document','checks it in the document'],
    'process.inspect':['rulebook','Checked the steps','checks the steps'],
    'condition.evaluate':['rulebook','Checked a condition','checks a condition'],
    'node.evaluate':['rulebook','Checked a step','checks a step'],
    'dependency.evaluate':['rulebook','Checked what a step needs','checks what a step needs'],
    'branch.evaluate':['rulebook','Kept this path open','keeps this path open'],
    'branch.activate':['rulebook','Followed this path','follows this path'],
    'branch.drop':['rulebook','Ruled out this path','rules out this path'],
    'document.require':['rulebook','Listed a needed document','lists a needed document'],
    'step.complete':['rulebook','Completed this step','completes this step'],
    'decision':['rulebook','Reached a result','shows the recorded result'],
    'knowledge.used':['memory','Reused the exact version','reuses the exact version'],
    'knowledge.reuse':['memory','Reused the exact version','reuses the exact version'],
    'knowledge.add':['memory','Checked whether to save it','checks whether to save it'],
    'knowledge.published':['memory','Checked whether to save it','checks whether to save it']
  });
  const phases = Object.freeze({acquiring:'casepath',interpreting:'reader',verifying:'checker',progressing:'rulebook',learning:'memory'});
  function operationPresentation(operation = {}, context = {}) {
    const phase = operation.kind === 'work.phase' ? operation.payload?.phase : operation.phase;
    const definition = operations[operation.kind];
    let roleId = definition?.[0] || phases[phase] || 'casepath';
    if (operation.kind === 'fact.extract' && operation.result?.verification_required === false) roleId = 'checker';
    if (operation.kind === 'source.open' || operation.kind === 'span.read' || operation.kind === 'phrase.match') {
      roleId = /^(?:interpret|interpret_reference)$/u.test(operation.stage || '') ? 'reader'
        : /^(?:verify|verify_reference)$/u.test(operation.stage || '') ? 'checker' : 'casepath';
    }
    const role = roles[roleId];
    let label = definition?.[1] || 'Recorded work', action = definition?.[2] || 'shows the recorded work';
    if (operation.kind === 'work.phase' && phases[phase]) {
      [label,action] = ({acquiring:['Read the supplied files','reads the supplied files'],
        interpreting:['Proposed facts and wording','proposes facts and wording'],
        verifying:['Checked the proposed wording','checks the proposed wording'],
        progressing:['Applied rules to confirmed wording','applies rules to confirmed wording'],
        learning:['Checked procedures for reuse','checks procedures for reuse']})[phase];
    }
    if (operation.kind === 'fact.extract' && roleId === 'checker') { label='Checked it in the document'; action='checks it in the document'; }
    if (['branch.activate','branch.evaluate'].includes(operation.kind) && operation.result?.activation === 'unresolved') {
      label='Kept this path open'; action='keeps this path open';
    }
    const knowledge = ['knowledge.add','knowledge.published'].includes(operation.kind)
      ? knowledgePresentation(operation.payload?.knowledge || operation.result || {},operation) : null;
    if (knowledge) { label=knowledge.label; action=knowledge.status === 'not_saved' ? 'shows why this was not saved' : 'checks the procedure for reuse'; }
    const provenance = roleId === 'reader' || roleId === 'checker'
      ? provenancePresentation(context,roleId === 'checker' ? 'verify' : 'interpret')
      : {kind:roleId === 'rulebook' || roleId === 'memory' ? 'rules' : 'unknown',label:roleId === 'rulebook' || roleId === 'memory' ? 'Fixed rules' : 'CasePath',model:null};
    const documents = Array.isArray(context.documents) ? context.documents : Object.values(context.documents || {});
    const document = documents.find(row => row.artifact_id === operation.source?.artifact_id)
      || list(context.state?.source_descriptors).find(row => row.artifact_id === operation.source?.artifact_id)
      || (operation.input?.document_type ? {document_type:operation.input.document_type} : operation.object?.type === 'document' ? {document_type:operation.object.id} : null);
    return {roleId,roleLabel:role.label,label,action,now:context.history ? `${role.label}: ${label.charAt(0).toLowerCase()+label.slice(1)}.` : `${role.label} ${action}.`,
      how:provenance.label,document:document ? documentTitle(document) : '',
      recordedResult:text(operation.result?.summary) || text(operation.result?.reason),details:operation};
  }

  function outcomePresentation(state = {}) {
    const outcome = state.outcome || state.deferral || {};
    const predicates = list(outcome.legal_predicates);
    const unknown = predicates.some(row => !['supported','failed'].includes(row.status));
    const missing = list(outcome.missing_evidence).length, unresolved = list(outcome.unresolved_facts).length;
    const limits = list(outcome.authority_limits).length;
    const supported = predicates.length > 0 && !unknown && !missing && !unresolved && outcome.assessment_status === 'complete';
    const summary = supported ? copy.supported : missing ? 'More documents are needed.'
      : unresolved || unknown ? 'Some facts still need proof.' : state.deferral ? 'Work stopped for the recorded reason.'
      : state.outcome ? 'A result is recorded.' : 'No result is recorded yet.';
    return {label:supported ? 'Document checks complete' : state.outcome ? 'Recorded result' : state.deferral ? 'Work stopped' : 'Result pending',
      summary,nextAction:missing || unresolved || unknown || limits || outcome.status === 'deferred' ? copy.waiting : 'Read the recorded result and its sources.',
      recordedSummary:text(outcome.summary) || text(outcome.reason),details:outcome};
  }

  function knowledgePresentation(value = {}, event = {}) {
    const qualification = value.qualification || event.qualification || {};
    const refused = qualification.status === 'quarantined' || event.projection_status === 'quarantined' || event.refused === true;
    const used = event.kind === 'knowledge.used' || event.kind === 'knowledge.reuse';
    const qualified = qualification.status === 'qualified';
    const rechecked = qualified && text(value.change_reason).startsWith('Requalified ');
    const status = refused ? 'not_saved' : used ? 'reused' : qualified ? 'saved' : 'unknown';
    const label = refused ? 'Not saved' : used ? 'Reused' : rechecked ? 'Rechecked' : qualified ? 'Saved for reuse' : 'Recorded procedure';
    const provenance = provenancePresentation(value);
    return {roleId:'memory',roleLabel:'Memory',label,status,how:provenance.label,
      reason:text(qualification.reason),ruleChecks:count(qualification.regression_cases),
      reuseCount:used && text(event.claim_id || event.receiving_claim_id) ? 1 : null,
      avoidedBuilds:count(event.avoided_rule_compilations),
      versionLabel:Number.isSafeInteger(value.version) && value.version > 0 ? `Exact version used: ${value.version}` : 'Version not recorded',
      tabs,details:value};
  }

  return Object.freeze({roles,copy,tabs,stepLabels,documentLabels,plainLabel,stepLabel,documentTitle,
    provenancePresentation,operationPresentation,outcomePresentation,knowledgePresentation});
});
