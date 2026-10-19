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
    replay:'Replay', viewOnly:'View only', notRun:'Original intake · not run', live:'Live',
    fictional:'Fictional case', fixedRules:'fixed rules',
    noRealWorldAction:'No real-world action. Playback shows saved records and changes nothing.',
    analysisUnavailable:'Analysis is not available in this workspace. Original sources are viewable.',
    notRunHere:'Not run in this workspace', noHistories:'No recorded histories in this workspace yet.',
    procedureNotRun:'Procedure for this domain · not run for this case',
    intakeNotChecked:'Intake not checked', notCheckedYet:'Not checked yet',
    candidateFiles:'Attached files, not yet checked against these items',
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
    const referenceCall = stage === 'verify' ? receipt?.verifier_receipt : receipt?.proposal_receipt;
    if (reference?.contract === 'casepath.deterministic-reference/1.0.0'
      && reference.mode === 'deterministic_reference' && reference.provider_calls === 0
      && receipt.operation === 'accept_verified_interpretation' && Boolean(text(receipt.workflow_id))
      && referenceCall?.contract === reference.contract && referenceCall.provider_calls === 0
      && referenceCall.stage === (stage === 'verify' ? 'verify_reference' : 'interpret_reference')
      && referenceCall.identity?.workflow_id === receipt.workflow_id && seal(referenceCall.receipt_sha256)
      && (!state?.claim_id || referenceCall.identity.claim_id === state.claim_id)
      && (!current || current.execution_mode === 'deterministic_reference')) return {kind:'rules',label:'Fixed rules',model:null};
    // A retained source outcome alone does not record the calls behind a knowledge version.
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
    const sourceId = text(operation.source?.artifact_id);
    const sourceBearing = ['source.open','span.read','phrase.match','fact.extract','verification.check','document.check'].includes(operation.kind);
    const requiredType = operation.kind === 'document.require'
      ? text(operation.input?.document_type) || (operation.object?.type === 'document' ? text(operation.object.id) : '') : '';
    const document = sourceBearing && sourceId
      ? documents.find(row => row?.artifact_id === sourceId)
        || list(context.state?.source_descriptors).find(row => row?.artifact_id === sourceId)
      : requiredType ? {document_type:requiredType} : null;
    return {roleId,roleLabel:role.label,label,action,now:context.history ? `${role.label}: ${label.charAt(0).toLowerCase()+label.slice(1)}.` : `${role.label} ${action}.`,
      how:provenance.label,document:document ? documentTitle(document) : '',
      recordedResult:text(operation.result?.summary) || text(operation.result?.reason),details:operation};
  }

  // Past-tense journal wording for the "Last:" line. The role names who the
  // saved event belongs to; unknown kinds stay with CasePath.
  const journalEvents = Object.freeze({
    'intake':['casepath','received the case'], 'intake.received':['casepath','received the case'],
    'sources.arrived':['casepath','added supporting files'], 'sources.acquired':['casepath','read the supplied files'],
    'process.prepared':['casepath','opened the case'], 'work.started':['casepath','started the checks'],
    'work.context':['casepath','recorded the check setup'],
    'interpretation.accepted':['casepath','saved the checked evidence assessment'],
    'graph.advanced':['rulebook','updated the document requirements'], 'action.completed':['rulebook','saved an action result'],
    'outcome.recorded':['rulebook','saved the result'], 'work.completed':['rulebook','saved the result'],
    'work.deferred':['casepath','stopped the checks'], 'knowledge.used':['memory','reused a saved procedure'],
    'knowledge.reused':['memory','reused a saved procedure'],
    'reconciliation.started':['casepath','started a saved result review'],
    'reconciliation.completed':['casepath','finished a saved result review'],
    'reconciliation.failed':['casepath','stopped a saved result review']
  });
  const journalPhases = Object.freeze({acquiring:['casepath','read the supplied files'],interpreting:['reader','proposed facts and wording'],
    verifying:['checker','checked the proposed wording'],progressing:['rulebook','applied rules to confirmed wording'],learning:['memory','checked procedures for reuse']});
  function eventPresentation(event = {}) {
    let [roleId,past] = event.kind === 'work.phase' ? journalPhases[event.payload?.phase] || ['casepath','recorded work']
      : journalEvents[event.kind] || ['casepath','recorded work'];
    if (event.kind === 'knowledge.published') [roleId,past] = event.payload?.knowledge?.qualification?.status === 'qualified'
      ? ['memory','saved steps for reuse'] : ['memory','did not save the steps'];
    return {roleId,roleLabel:roles[roleId].label,past};
  }
  const recordedDay = value => {
    const time = Date.parse(text(value));
    return Number.isFinite(time) ? new Intl.DateTimeFormat('en-GB',{timeZone:'UTC',day:'numeric',month:'short',year:'numeric'}).format(new Date(time)) : '';
  };
  // One header phrase names what the viewer is looking at. Only corpus or
  // featured originals are fictional; an added case never inherits that word.
  function modeLine({revision, presentation = 'saved', provenance = null, origin = '', recordedAt = '', readOnly = false} = {}) {
    const known = Number.isSafeInteger(revision) && revision >= 0, parts = [];
    if (known && revision === 0) parts.push(copy.notRun);
    else if (presentation === 'replay') {
      const day = recordedDay(recordedAt);
      parts.push(day ? `${copy.replay} · recorded ${day}` : copy.replay);
      if (provenance?.mode === 'deterministic_reference') parts.push(copy.fixedRules);
    } else if (presentation === 'live') parts.push(copy.live);
    else parts.push(known ? `Saved result · revision ${revision}` : 'Saved result');
    if (['canonical_original','corpus','featured'].includes(origin)) parts.push(copy.fictional);
    if (readOnly) parts.push(copy.viewOnly);
    return parts.join(' · ');
  }

  const legalFindingLabels = Object.freeze({
    residential_tenancy_scope:[
      'The residential tenancy is supported.',
      'Residential tenancy is not supported.',
      'Whether this is a residential tenancy is still unknown.'
    ],
    objective_use_impairment:[
      'The defect limits normal use of the home.',
      'A loss of normal use is not supported.',
      'Whether the defect limits normal use is still unknown.'
    ],
    outside_small_tenant_maintenance_and_no_tenant_cause:[
      'The defect is outside small tenant repairs, and tenant fault is not supported.',
      'The checks do not confirm both repair responsibility and absence of tenant fault.',
      'Repair responsibility and possible tenant fault remain open.'
    ],
    landlord_first_knowledge:[
      "The landlord's first knowledge of the defect is documented.",
      "The landlord's first knowledge of the defect is not supported.",
      'When the landlord first knew is still unknown.'
    ],
    continuing_defect_without_remedy:[
      'The defect continues without a lasting repair.',
      'A continuing unrepaired defect is not supported.',
      'Whether the defect has been fixed is still unknown.'
    ],
    issuer_authority_and_received_packet:[
      "The sender's authority and received notice are documented.",
      "The sender's authority and received notice are not both supported.",
      "The sender's authority or received notice remains unknown."
    ],
    complete_channel_archive:[
      'The complete notice and delivery record are documented.',
      'A complete notice and delivery record is not supported.',
      'Whether the notice and delivery record is complete remains unknown.'
    ],
    canton_approved_form:[
      'The termination notice has the required official form.',
      'The termination notice is missing the required official form.',
      'Whether the termination notice uses the required official form is still unknown.'
    ],
    ordinary_non269c_tenancy:[
      'An ordinary tenancy without an agreed rent increase is documented.',
      'The checks do not confirm an ordinary tenancy without an agreed rent increase.',
      'Whether the tenancy has an agreed rent increase remains unknown.'
    ],
    issuer_authority_and_complete_packet:[
      "The sender's authority and complete original notice are documented.",
      "The sender's authority and complete original notice are not both supported.",
      "The sender's authority or complete original notice remains unknown."
    ],
    contemporaneous_substantive_reasons:[
      'The rent increase notice includes reasons supplied with the notice.',
      'The rent increase notice is missing reasons supplied with the notice.',
      'Whether reasons came with the rent increase notice is still unknown.'
    ],
    later_email_is_not_original_reasons:[
      'The later email was not part of the original reasons.',
      'The checks do not support separating the later email from the original reasons.',
      'Whether the email came with the original reasons remains unknown.'
    ]
  });
  const defectEligibilityChecks = Object.freeze(['residential_tenancy_scope','objective_use_impairment',
    'outside_small_tenant_maintenance_and_no_tenant_cause','landlord_first_knowledge','continuing_defect_without_remedy']);
  function outcomePresentation(state = {}) {
    const outcome = state.outcome || state.deferral || {};
    const predicates = list(outcome.legal_predicates);
    const unknown = predicates.some(row => !['supported','failed'].includes(row.status));
    const missing = list(outcome.missing_evidence).length, unresolved = list(outcome.unresolved_facts).length;
    const limits = list(outcome.authority_limits).length;
    const supported = predicates.length > 0 && !unknown && !missing && !unresolved && outcome.assessment_status === 'complete';
    const findings = [];
    for (const id of Object.keys(legalFindingLabels)) {
      const matches = predicates.filter(row => row.predicate_id === id);
      if (!matches.length) continue;
      const status = matches.length === 1 && ['supported','failed'].includes(matches[0].status) ? matches[0].status : 'unknown';
      findings.push({id,status,summary:legalFindingLabels[id][status === 'supported' ? 0 : status === 'failed' ? 1 : 2]});
    }
    const finding = id => findings.find(row => row.id === id);
    const notice = finding('canton_approved_form') || finding('contemporaneous_substantive_reasons');
    const defect = defectEligibilityChecks.slice(1).some(id => finding(id));
    const eligible = defectEligibilityChecks.every(id => finding(id)?.status === 'supported') && supported;
    // A failed form/reason check is a recorded finding, never an award or real-world action.
    const summary = notice ? notice.summary : defect ? eligible
      ? 'The checks support repair and rent reduction eligibility.' : 'Repair and rent reduction eligibility remain open.'
      : findings[0]?.summary || (missing ? 'More documents are needed.'
      : unresolved || unknown ? 'Some facts still need proof.' : state.deferral ? 'Work stopped for the recorded reason.'
      : state.outcome ? 'A result is recorded.' : 'No result is recorded yet.');
    const constraints = [missing ? 'More documents are needed.' : '',
      unresolved || unknown ? 'Some facts still need proof.' : '',
      limits ? 'Real-world action still needs its own authority.' : ''].filter(Boolean);
    const nextAction = [missing ? 'Waiting for the listed documents.' : '',
      unresolved || unknown || findings.some(row => row.status === 'unknown') ? 'Waiting for proof of open facts.' : '',
      limits ? "A person's go-ahead is needed before any real-world action." : ''].filter(Boolean).join(' ') || 'Review the case details.';
    return {label:supported ? 'Document checks complete' : state.outcome ? 'Recorded result' : state.deferral ? 'Work stopped' : 'Result pending',
      summary,nextAction,
      findings,support:supported ? copy.supported : '',constraints,
      openItems:outcome.assessment_scope==='defect_removal_and_reduction_eligibility' && text(outcome.summary).includes('Repair, the reduction amount and any award remain undetermined.') ? 'Repair, the reduction amount and any award remain undetermined.' : '',
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

  function refusalReason(reason) {
    return ({
      'knowledge candidate is not bound to a verified sufficient supporting file':'A checked supporting document was not linked to these steps.',
      'The independent verifier rejected this knowledge candidate.':'The independent check rejected these steps.'
    })[text(reason)] || 'These steps were not saved. Open Details for the recorded reason.';
  }
  return Object.freeze({refusalReason,roles,copy,tabs,stepLabels,documentLabels,plainLabel,stepLabel,documentTitle,
    provenancePresentation,operationPresentation,outcomePresentation,knowledgePresentation,modeLine,eventPresentation});
});
