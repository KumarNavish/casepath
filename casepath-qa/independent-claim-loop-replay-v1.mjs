import { createHash } from 'node:crypto';

const FLOAT_FIELDS = new Set(['confidence', 'deterministic_confidence', 'cost_usd']);
const DEFAULT_TOOL_ID = 'casepath.claim-evidence-adapter/1.0.0';
const LOOPBACK_ADAPTER_ID = 'loopback-source-byte-acquisition-v1';
const INTERPRETER_ID = 'casepath.fixed-source-span-interpreter/1.0.0';
const MAX_SOURCE_BYTES = 100_000;
const GENERIC_ACQUISITION_FIELDS = Object.freeze([
  'contract', 'status', 'session_id', 'loop_id', 'record_version', 'action_id',
  'action_sha256', 'dispatch_sha256', 'dispatch_generation', 'adapter_id',
  'adapter_implementation_id', 'adapter_implementation_source_sha256',
  'adapter_implementation_sha256', 'source_locator', 'acquisition_request_sha256',
  'acquired_at', 'content_kind', 'mime_type', 'raw_byte_count', 'raw_bytes_sha256',
  'sanitizer_implementation', 'sanitized_content', 'sanitized_content_sha256',
  'artifact_page_count', 'reason_code', 'model_calls', 'provider_calls',
  'provider_credentials_read', 'cost_usd', 'receipt_sha256',
]);
const INTENT_FIELDS = Object.freeze([
  'contract', 'intent_id', 'session_id', 'loop_id', 'claim_id', 'record_version',
  'expected_revision', 'expected_state_sha256', 'action_id', 'action_sha256',
  'evidence_item_id', 'idempotency_key', 'adapter_id',
  'claim_registry_watermark_sha256', 'issued_at', 'expires_at', 'receipt_sha256',
]);
const SOURCE_ACQUISITION_FIELDS = Object.freeze([
  'contract', 'acquisition_receipt_id', 'acquisition_intent_id',
  'intent_receipt_sha256', 'session_id', 'loop_id', 'claim_id', 'record_version',
  'expected_revision', 'expected_state_sha256', 'action_id', 'action_sha256',
  'evidence_item_id', 'idempotency_key', 'adapter_id', 'adapter_artifact_sha256',
  'claim_registry_watermark_sha256', 'claim_first_seen_receipt_sha256',
  'source_entry_sha256', 'source_artifact_id', 'source_artifact_sha256',
  'source_version', 'text_start', 'text_end', 'byte_start', 'byte_end',
  'content_sha256', 'content_length', 'server_sniffed_media_type',
  'media_sniffer_id', 'media_sniffer_sha256', 'channel', 'freshness_nonce',
  'acquired_at', 'expires_at', 'freshness', 'receipt_sha256',
]);
const REGISTRATION_FIELDS = Object.freeze([
  'contract', 'session_id', 'loop_id', 'claim_id', 'record_version',
  'parent_revision', 'parent_state_sha256', 'action_id', 'action_sha256',
  'evidence_item_id', 'idempotency_key', 'acquisition_intent_id',
  'intent_receipt_sha256', 'acquisition_receipt_id',
  'source_acquisition_receipt_sha256', 'content_sha256', 'content_length',
  'server_sniffed_media_type', 'media_sniffer_id', 'media_sniffer_sha256',
  'channel', 'freshness_nonce', 'adapter_id', 'adapter_artifact_sha256',
  'source_entry_sha256', 'byte_start', 'byte_end', 'registered_at', 'receipt_sha256',
]);
const PROPOSAL_FIELDS = Object.freeze([
  'contract', 'authoritative', 'claim_id', 'loop_id', 'record_version',
  'parent_revision', 'action_id', 'action_sha256', 'acquisition_intent_id',
  'acquisition_receipt_id', 'acquisition_receipt_sha256',
  'registration_receipt_sha256', 'content_sha256', 'content_length',
  'source_entry_sha256', 'source_artifact_sha256', 'text_start', 'text_end',
  'byte_start', 'byte_end', 'span_sha256', 'interpreter_id',
  'interpreter_source_sha256', 'grammar_id', 'grammar_sha256', 'schema_id',
  'schema_sha256', 'catalog_sha256', 'policy_sha256', 'actor_grant_sha256',
  'intent_receipt_sha256', 'source_acquisition_receipt_sha256', 'freshness_nonce',
  'proposed_normalized_value', 'proposed_fact_state', 'proposed_evidence_status',
  'interpretation_receipt_sha256', 'proposal_sha256',
]);
const ADMISSION_FIELDS = Object.freeze([
  'contract', 'proposal_sha256', 'interpretation_receipt_sha256',
  'acquisition_receipt_sha256', 'registration_receipt_sha256',
  'intent_receipt_sha256', 'source_acquisition_receipt_sha256', 'authority_id',
  'authority_source_sha256', 'decision', 'authoritative_state_effect', 'receipt_sha256',
]);
const REJECTION_FIELDS = Object.freeze([
  'contract', 'session_id', 'loop_id', 'claim_id', 'record_version',
  'parent_revision', 'parent_state_sha256', 'action_id', 'action_sha256',
  'dispatch_sha256', 'acquisition_receipt_sha256', 'acquisition_intent_id',
  'source_acquisition_receipt_sha256', 'source_entry_sha256', 'content_sha256',
  'proposal_sha256', 'authority_id', 'authority_source_sha256', 'reason',
  'rejected_at', 'authoritative_semantic_effect', 'receipt_sha256',
]);
const OUTCOME_FIELDS = Object.freeze([
  'contract', 'acquisition_receipt_sha256', 'decision',
  'authority_receipt_sha256', 'receipt_sha256',
]);
const HEALTH_POSITIVE_TERMS = [
  'cough', 'coughing', 'hustet', 'husten', 'rash', 'ausschlag',
  'pharmacy', 'apotheke', 'breathing', 'atem',
];
const HEALTH_NEGATIVE_TERMS = [
  'no health effects', 'no immediate health risk',
  'keine gesundheitlichen folgen', 'kein unmittelbares gesundheitsrisiko',
];
const UNCERTAINTY_TERMS = [
  'unresolved', 'unclear', 'unknown', 'missing', 'cannot safely',
  'ungeklärt', 'unklar', 'offen', 'fehlt', 'nicht sicher',
];
const LEASE_TERMINATION_INTAKE_TERMS = [
  'termination', 'termination notice', 'notice of termination',
  'kündigung', 'kündigungsschreiben', 'mietvertragskündigung',
];
const RENT_INCREASE_INTAKE_TERMS = [
  'rent increase', 'rent increases', 'rent rises', 'net rent', 'gross rent',
  'mietzinserhöhung', 'mietzins', 'nettomiete', 'bruttomiete',
];
const INSTRUCTION_PATTERNS = [
  /\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions?\b/iu,
  /\b(?:set|choose|select|override|change|mark|grant)\s+(?:the\s+)?(?:finding|readiness|parser|policy|authority|branch|normalized value)\b/iu,
  /["'](?:finding|readiness|parser|policy|authority|process_branch|normalized_value)["']\s*[:=]/iu,
  /\b(?:approve|deny|pay|close)\s+(?:this\s+|the\s+)?claim\b/iu,
];
const NEGATED_HEALTH_PATTERNS = [
  /\bno\s+(?:cough|coughing|rash|breathing problem)\b/iu,
  /\bwithout\s+(?:a\s+)?(?:cough|rash|breathing problem)\b/iu,
  /\bkein(?:e|en)?\s+(?:husten|ausschlag|atemproblem)\b/iu,
];

function canonical(value, field = null) {
  if (value === null || typeof value !== 'object') {
    if (typeof value === 'number' && Number.isInteger(value) && FLOAT_FIELDS.has(field)) return value.toFixed(1);
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(item => canonical(item)).join(',')}]`;
  return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key], key)}`).join(',')}}`;
}

function digest(value) {
  const material = typeof value === 'string' || Buffer.isBuffer(value) || value instanceof Uint8Array
    ? value : canonical(value);
  return createHash('sha256').update(material).digest('hex');
}

function clone(value) {
  return structuredClone(value);
}

function firstDifference(left, right, location = '$') {
  if (canonical(left) === canonical(right)) return null;
  if (Array.isArray(left) && Array.isArray(right)) {
    if (left.length !== right.length) return `${location}.length=${left.length}/${right.length}`;
    for (let index = 0; index < left.length; index += 1) {
      const difference = firstDifference(left[index], right[index], `${location}[${index}]`);
      if (difference) return difference;
    }
  } else if (left && right && typeof left === 'object' && typeof right === 'object') {
    const keys = [...new Set([...Object.keys(left), ...Object.keys(right)])].sort();
    for (const key of keys) {
      if (!Object.hasOwn(left, key) || !Object.hasOwn(right, key)) {
        return `${location}.${key}=present:${Object.hasOwn(left, key)}/${Object.hasOwn(right, key)}`;
      }
      const difference = firstDifference(left[key], right[key], `${location}.${key}`);
      if (difference) return difference;
    }
  }
  return `${location}=${canonical(left)}/${canonical(right)}`;
}

function omit(value, ...keys) {
  const excluded = new Set(keys);
  return Object.fromEntries(Object.entries(value).filter(([key]) => !excluded.has(key)));
}

function invariant(value, message) {
  if (!value) throw new Error(message);
}

function selfHashed(value, field = 'receipt_sha256', excluded = [field]) {
  return Boolean(value) && value[field] === digest(omit(value, ...excluded));
}

function hasExactFields(value, fields) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).length === fields.length
    && fields.every(field => Object.hasOwn(value, field));
}

function termPresent(text, term) {
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(?<![\\p{L}\\p{N}_])${escaped}(?![\\p{L}\\p{N}_])`, 'iu').test(text);
}

function substantive(text) {
  return (text.match(/[\p{L}\p{N}_]+/gu) || []).length >= 5;
}

function singleEdgeIntakeIsDecisive(processNodeId, text) {
  const terms = processNodeId.endsWith('lt_intake')
    ? LEASE_TERMINATION_INTAKE_TERMS
    : processNodeId.endsWith('ri_intake') ? RENT_INCREASE_INTAKE_TERMS : [];
  return terms.length > 0 && terms.some(term => termPresent(text, term));
}

function deriveFinding(action, text, unresolved, resolved, grant) {
  invariant(unresolved !== null && unresolved !== undefined,
    'independent source span has no closed decision catalog');
  invariant(grant?.decision_bearing === true,
    'independent source span lacks a decision-bearing actor grant');
  invariant(!INSTRUCTION_PATTERNS.some(pattern => pattern.test(text)),
    'independent source span is instruction-bearing');
  invariant(substantive(text), 'independent source span is not substantive');
  if (resolved.length === 1 && singleEdgeIntakeIsDecisive(action.process_node_id, text)) {
    return resolved[0];
  }
  if (UNCERTAINTY_TERMS.some(term => termPresent(text, term))) return unresolved;
  if (action.process_node_id.endsWith('dh_intake')
    && canonical([...resolved].sort()) === canonical(['dh_e01', 'dh_e02'])) {
    const positive = HEALTH_POSITIVE_TERMS.some(term => termPresent(text, term));
    const negative = HEALTH_NEGATIVE_TERMS.some(term => termPresent(text, term));
    const negatedPositive = NEGATED_HEALTH_PATTERNS.some(pattern => pattern.test(text));
    invariant(!negatedPositive && positive !== negative,
      'independent health span is ambiguous, negated, or contradictory');
    return positive ? 'dh_e01' : 'dh_e02';
  }
  throw new Error('independent source span has no decisive grammar token');
}

function deriveAuthorityObservation(context, state, action, artifact, binding, primitives) {
  invariant(primitives && typeof primitives === 'object',
    `${context.claimId}: independent replay lacks authority primitives`);
  const {
    intent, source_acquisition: sourceAcquisition,
    acquisition_index: acquisitionIndex, claim_registry: claimRegistry,
    registration, proposal_index: proposalIndex, proposal,
    admission_index: admissionIndex, admission, outcome,
    source_blob_base64: sourceBlobBase64,
    expected_interpreter_source_sha256: expectedInterpreterSourceSha256,
    expected_authority_source_sha256: expectedAuthoritySourceSha256,
  } = primitives;
  const acquisition = artifact.acquisition_receipt;
  invariant(hasExactFields(acquisition, GENERIC_ACQUISITION_FIELDS)
    && hasExactFields(intent, INTENT_FIELDS)
    && hasExactFields(sourceAcquisition, SOURCE_ACQUISITION_FIELDS)
    && hasExactFields(registration, REGISTRATION_FIELDS)
    && hasExactFields(proposal, PROPOSAL_FIELDS)
    && hasExactFields(admission, ADMISSION_FIELDS)
    && hasExactFields(outcome, OUTCOME_FIELDS),
  `${context.claimId}: authority primitive field roster differs`);
  invariant(selfHashed(acquisition) && selfHashed(intent) && selfHashed(sourceAcquisition)
    && selfHashed(acquisitionIndex) && selfHashed(claimRegistry)
    && selfHashed(registration) && selfHashed(proposalIndex)
    && selfHashed(proposal, 'proposal_sha256') && selfHashed(admissionIndex)
    && selfHashed(admission) && selfHashed(outcome),
  `${context.claimId}: authority primitive self-hash differs`);

  const raw = Buffer.from(sourceBlobBase64, 'base64');
  invariant(raw.length > 0 && raw.length <= MAX_SOURCE_BYTES && !raw.includes(0),
    `${context.claimId}: immutable source bytes are empty, oversized, or contain NUL`);
  const text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(raw);
  invariant(text === text.normalize('NFC'),
    `${context.claimId}: immutable source bytes are not NFC-normalized UTF-8`);
  const locatorParts = acquisition.source_locator.split(':');
  invariant(locatorParts.length === 4 && locatorParts[0] === 'loopback-source-span'
    && acquisition.contract === 'casepath.acquisition-receipt/1.1.0'
    && acquisition.status === 'observed'
    && acquisition.adapter_id === LOOPBACK_ADAPTER_ID
    && acquisition.action_id === action.action_id
    && acquisition.action_sha256 === action.action_sha256
    && acquisition.dispatch_sha256 === context.activeDispatchSha
    && acquisition.raw_byte_count === raw.length
    && acquisition.raw_bytes_sha256 === digest(raw)
    && acquisition.sanitized_content_sha256 === digest(raw)
    && acquisition.sanitized_content === text
    && artifact.sanitized_content === text
    && locatorParts[1] === sourceAcquisition.acquisition_intent_id
    && locatorParts[2] === sourceAcquisition.acquisition_receipt_id
    && locatorParts[3] === sourceAcquisition.source_entry_sha256,
  `${context.claimId}: generic acquisition differs from immutable source bytes`);

  const admissionPolicy = context.accepted.observable_package?.workspace_evidence_admission;
  const entries = admissionPolicy?.source_entries || [];
  const matchingEntries = entries.filter(value => value.source_entry_sha256 === sourceAcquisition.source_entry_sha256);
  const entry = matchingEntries[0];
  const grant = admissionPolicy?.actor_grants?.[action.evidence_item_id];
  invariant(matchingEntries.length === 1 && entry && grant
    && entry.source_entry_sha256 === digest(omit(entry, 'source_entry_sha256'))
    && entry.exact_text === text
    && entry.span_sha256 === digest(raw)
    && entry.byte_end - entry.byte_start === raw.length
    && sourceAcquisition.contract === 'casepath.workspace-source-acquisition/1.0.0'
    && sourceAcquisition.receipt_sha256 === digest(omit(sourceAcquisition, 'receipt_sha256'))
    && sourceAcquisition.acquisition_receipt_id === `acquisition.${digest(omit(
      sourceAcquisition, 'acquisition_receipt_id', 'receipt_sha256', 'acquired_at',
    ))}`
    && sourceAcquisition.claim_id === context.claimId
    && sourceAcquisition.session_id === context.sessionId
    && sourceAcquisition.loop_id === context.loopId
    && sourceAcquisition.record_version === context.recordVersion
    && sourceAcquisition.expected_revision === context.authorityParentRevision
    && sourceAcquisition.expected_state_sha256 === context.authorityParentStateSha
    && sourceAcquisition.acquisition_intent_id === intent.intent_id
    && sourceAcquisition.action_id === action.action_id
    && sourceAcquisition.action_sha256 === action.action_sha256
    && sourceAcquisition.evidence_item_id === action.evidence_item_id
    && sourceAcquisition.intent_receipt_sha256 === intent.receipt_sha256
    && sourceAcquisition.content_sha256 === digest(raw)
    && sourceAcquisition.content_length === raw.length
    && sourceAcquisition.source_artifact_id === entry.artifact_id
    && sourceAcquisition.source_artifact_sha256 === entry.artifact_sha256
    && sourceAcquisition.source_version === entry.source_version
    && sourceAcquisition.text_start === entry.text_start
    && sourceAcquisition.text_end === entry.text_end
    && sourceAcquisition.byte_start === entry.byte_start
    && sourceAcquisition.byte_end === entry.byte_end,
  `${context.claimId}: source acquisition differs from admitted source entry`);

  const intentIdentity = omit(intent, 'intent_id', 'receipt_sha256', 'issued_at', 'expires_at');
  invariant(intent.contract === 'casepath.workspace-acquisition-intent/1.0.0'
    && intent.intent_id === `intent.${digest(intentIdentity)}`
    && intent.claim_id === context.claimId
    && intent.session_id === context.sessionId
    && intent.loop_id === context.loopId
    && intent.record_version === context.recordVersion
    && intent.expected_revision === context.authorityParentRevision
    && intent.expected_state_sha256 === context.authorityParentStateSha
    && intent.action_id === action.action_id
    && intent.action_sha256 === action.action_sha256
    && intent.evidence_item_id === action.evidence_item_id
    && registration.contract === 'casepath.workspace-evidence-registration-receipt/1.0.0'
    && registration.claim_id === context.claimId
    && registration.session_id === context.sessionId
    && registration.loop_id === context.loopId
    && registration.record_version === context.recordVersion
    && registration.parent_revision === context.authorityParentRevision
    && registration.parent_state_sha256 === context.authorityParentStateSha
    && registration.action_id === action.action_id
    && registration.action_sha256 === action.action_sha256
    && registration.acquisition_intent_id === intent.intent_id
    && registration.intent_receipt_sha256 === intent.receipt_sha256
    && registration.acquisition_receipt_id === sourceAcquisition.acquisition_receipt_id
    && registration.source_acquisition_receipt_sha256 === sourceAcquisition.receipt_sha256
    && registration.content_sha256 === digest(raw)
    && registration.content_length === raw.length
    && registration.source_entry_sha256 === entry.source_entry_sha256,
  `${context.claimId}: intent or registration primitive differs`);

  invariant(acquisitionIndex.contract === 'casepath.workspace-acquisition-intent-index/1.0.0'
    && acquisitionIndex.acquisition_intent_id === intent.intent_id
    && acquisitionIndex.acquisition_receipt_id === sourceAcquisition.acquisition_receipt_id
    && acquisitionIndex.source_acquisition_receipt_sha256 === sourceAcquisition.receipt_sha256
    && claimRegistry.contract === 'casepath.workspace-claim-content-first-seen/1.0.0'
    && claimRegistry.claim_id === context.claimId
    && claimRegistry.content_sha256 === sourceAcquisition.content_sha256
    && claimRegistry.acquisition_intent_id === intent.intent_id
    && claimRegistry.intent_receipt_sha256 === intent.receipt_sha256
    && claimRegistry.claim_registry_watermark_sha256 === intent.claim_registry_watermark_sha256
    && claimRegistry.source_entry_sha256 === entry.source_entry_sha256
    && claimRegistry.receipt_sha256 === sourceAcquisition.claim_first_seen_receipt_sha256,
  `${context.claimId}: acquisition indexes differ from immutable source authority`);

  const catalog = templateCatalog(context.accepted);
  const priorFact = state.facts.find(value => value.fact_id === action.fact_id);
  invariant(priorFact && catalog.decision_options && catalog.fail_closed_normalized_values,
    `${context.claimId}: independent fact catalog is incomplete`);
  const decisionKey = priorFact.decision_key;
  const options = decisionKey === null || decisionKey === undefined
    ? {} : catalog.decision_options[decisionKey];
  const unresolved = decisionKey === null || decisionKey === undefined
    ? null : catalog.fail_closed_normalized_values[decisionKey];
  invariant(options && typeof options === 'object' && Object.hasOwn(options, unresolved),
    `${context.claimId}: independent decision catalog is not closed`);
  const resolved = Object.keys(options).filter(value => value !== unresolved);
  const assertionCatalog = {
    template_sha256: context.accepted.playbook_template.template_sha256,
    decision_key: decisionKey,
    normalized_values: Object.keys(options),
    unresolved_normalized_value: unresolved,
  };
  const finding = deriveFinding(action, text, unresolved, resolved, grant);
  const didResolve = finding !== null && finding !== unresolved;
  const sourceRef = {
    contract: 'casepath.claim-source-reference/1.0.0',
    source_id: entry.artifact_id,
    source_sha256: entry.artifact_sha256,
    source_version: entry.source_version,
    locator_kind: 'text_quote',
    page: 1,
    sanitized_excerpt: text,
    text_start: entry.text_start,
    text_end: entry.text_end,
    field: null,
    value: null,
    span_sha256: entry.span_sha256,
    adapter_id: LOOPBACK_ADAPTER_ID,
  };
  const observationMaterial = {
    contract: 'casepath.claim-observation/1.0.0',
    observation_id: `observation.${digest({
      acquisition_receipt_sha256: acquisition.receipt_sha256,
      source_entry_sha256: entry.source_entry_sha256,
      action_sha256: action.action_sha256,
    })}`,
    fact_id: action.fact_id,
    evidence_item_id: action.evidence_item_id,
    value: text,
    fact_state: didResolve ? 'known' : 'unknown',
    normalized_value: didResolve && decisionKey !== null && decisionKey !== undefined ? finding : null,
    explanation: didResolve
      ? 'A fixed-version server interpreter derived this bounded policy transition from an exact acquired source span.'
      : 'The fixed-version server interpreter abstained because this acquired source span does not resolve the current policy step.',
    evidence_status: didResolve ? 'provided_sufficient' : 'provided_insufficient',
    source_refs: [sourceRef],
    observed_at: acquisition.acquired_at,
  };
  const observation = { ...observationMaterial, observation_sha256: digest(observationMaterial) };
  const interpretationMaterial = {
    contract: 'casepath.canonical-fact-interpretation/1.2.0',
    action_id: action.action_id,
    action_sha256: action.action_sha256,
    fact_id: action.fact_id,
    evidence_item_id: action.evidence_item_id,
    acquisition_receipt_sha256: acquisition.receipt_sha256,
    raw_artifact_sha256: acquisition.receipt_sha256,
    prior_fact_sha256: digest(priorFact),
    assertion_catalog_sha256: digest(assertionCatalog),
    selected_assertion_id: didResolve
      ? `server-source-span.${action.evidence_item_id}.${finding}/1` : null,
    observation,
    implementation: INTERPRETER_ID,
    implementation_source_sha256: proposal.interpreter_source_sha256,
    model_calls: 0,
    provider_calls: 0,
    provider_credentials_read: false,
    cost_usd: 0.0,
  };
  const interpretation = {
    ...interpretationMaterial,
    receipt_sha256: digest(interpretationMaterial),
  };
  invariant(canonical(artifact.observation) === canonical(observation)
    && canonical(artifact.interpretation) === canonical(interpretation),
  `${context.claimId}: journal semantics differ from independent raw-byte interpretation `
    + `(observation ${artifact.observation?.observation_sha256}/${observation.observation_sha256}, `
    + `interpretation ${artifact.interpretation?.receipt_sha256}/${interpretation.receipt_sha256}; `
    + `observation difference ${firstDifference(
      omit(artifact.observation, 'observation_sha256'), observationMaterial,
    )}; interpretation difference ${firstDifference(
      omit(artifact.interpretation, 'receipt_sha256', 'observation'),
      omit(interpretationMaterial, 'observation'),
    )})`);

  const grammarSha256 = digest({
    positive: HEALTH_POSITIVE_TERMS,
    negative: HEALTH_NEGATIVE_TERMS,
    uncertainty: UNCERTAINTY_TERMS,
    lease_termination_intake: LEASE_TERMINATION_INTAKE_TERMS,
    rent_increase_intake: RENT_INCREASE_INTAKE_TERMS,
  });
  const schemaSha256 = digest({
    schema_id: 'casepath.workspace-source-span-interpretation/1.0.0',
    input: 'exact-receipted-source-span',
    output: 'canonical-fact-interpretation/1.2.0',
    unknown_default: true,
  });
  invariant(proposal.contract === 'casepath.workspace-server-interpretation-proposal/1.0.0'
    && proposalIndex.contract === 'casepath.workspace-proposal-acquisition-index/1.0.0'
    && proposalIndex.acquisition_receipt_sha256 === acquisition.receipt_sha256
    && proposalIndex.proposal_sha256 === proposal.proposal_sha256
    && proposal.authoritative === false
    && proposal.claim_id === context.claimId
    && proposal.loop_id === context.loopId
    && proposal.record_version === context.recordVersion
    && proposal.parent_revision === context.authorityParentRevision
    && proposal.action_id === action.action_id
    && proposal.action_sha256 === action.action_sha256
    && proposal.acquisition_intent_id === intent.intent_id
    && proposal.acquisition_receipt_id === sourceAcquisition.acquisition_receipt_id
    && proposal.acquisition_receipt_sha256 === acquisition.receipt_sha256
    && proposal.registration_receipt_sha256 === registration.receipt_sha256
    && proposal.intent_receipt_sha256 === intent.receipt_sha256
    && proposal.source_acquisition_receipt_sha256 === sourceAcquisition.receipt_sha256
    && proposal.source_entry_sha256 === entry.source_entry_sha256
    && proposal.source_artifact_sha256 === entry.artifact_sha256
    && proposal.text_start === entry.text_start
    && proposal.text_end === entry.text_end
    && proposal.byte_start === entry.byte_start
    && proposal.byte_end === entry.byte_end
    && proposal.span_sha256 === entry.span_sha256
    && proposal.content_sha256 === digest(raw)
    && proposal.content_length === raw.length
    && proposal.interpreter_id === INTERPRETER_ID
    && proposal.interpreter_source_sha256 === interpretation.implementation_source_sha256
    && proposal.interpreter_source_sha256 === expectedInterpreterSourceSha256
    && proposal.grammar_id === 'casepath.workspace-source-span-grammar/1.0.0'
    && proposal.grammar_sha256 === grammarSha256
    && proposal.schema_id === 'casepath.workspace-source-span-interpretation/1.0.0'
    && proposal.schema_sha256 === schemaSha256
    && proposal.catalog_sha256 === digest(assertionCatalog)
    && proposal.policy_sha256 === admissionPolicy.policy_sha256
    && proposal.actor_grant_sha256 === digest(grant)
    && proposal.freshness_nonce === sourceAcquisition.freshness_nonce
    && proposal.proposed_normalized_value === (finding === unresolved ? null : finding)
    && proposal.proposed_fact_state === observation.fact_state
    && proposal.proposed_evidence_status === observation.evidence_status
    && proposal.interpretation_receipt_sha256 === interpretation.receipt_sha256
    && admissionIndex.contract === 'casepath.workspace-admission-interpretation-index/1.0.0'
    && admissionIndex.interpretation_receipt_sha256 === interpretation.receipt_sha256
    && admissionIndex.admission_receipt_sha256 === admission.receipt_sha256
    && admission.contract === 'casepath.workspace-evidence-authority-admission/1.0.0'
    && admission.proposal_sha256 === proposal.proposal_sha256
    && admission.interpretation_receipt_sha256 === interpretation.receipt_sha256
    && admission.acquisition_receipt_sha256 === acquisition.receipt_sha256
    && admission.registration_receipt_sha256 === registration.receipt_sha256
    && admission.intent_receipt_sha256 === intent.receipt_sha256
    && admission.source_acquisition_receipt_sha256 === sourceAcquisition.receipt_sha256
    && admission.authority_id === 'casepath.independent-evidence-authority/1.0.0'
    && admission.authority_source_sha256 === expectedAuthoritySourceSha256
    && admission.decision === 'admitted'
    && admission.authoritative_state_effect === 'delegated_to_claim_loop_journal'
    && outcome.contract === 'casepath.workspace-authority-outcome-index/1.0.0'
    && outcome.acquisition_receipt_sha256 === acquisition.receipt_sha256
    && outcome.authority_receipt_sha256 === admission.receipt_sha256
    && outcome.decision === 'admitted'
    && binding.proposal_sha256 === proposal.proposal_sha256
    && binding.admission_receipt_sha256 === admission.receipt_sha256
    && binding.interpretation_receipt_sha256 === interpretation.receipt_sha256
    && binding.acquisition_receipt_sha256 === acquisition.receipt_sha256
    && binding.registration_receipt_sha256 === registration.receipt_sha256
    && binding.authority_id === admission.authority_id
    && binding.authority_source_sha256 === admission.authority_source_sha256
    && selfHashed(binding, 'binding_sha256'),
  `${context.claimId}: interpreted semantics lack their primitive authority chain`);
  return { observation, interpretation };
}

function validateAuthorityRejection(context, state, action, command, primitives) {
  invariant(primitives?.decision === 'rejected',
    `${context.claimId}: independent replay lacks rejected authority primitives`);
  const {
    intent, source_acquisition:sourceAcquisition,
    acquisition_index:acquisitionIndex, claim_registry:claimRegistry,
    registration, rejection_index:rejectionIndex, rejection, outcome,
    source_blob_base64:sourceBlobBase64,
    expected_authority_source_sha256:expectedAuthoritySourceSha256,
  } = primitives;
  const acquisition = command.acquisition_receipt;
  invariant(hasExactFields(command, [
    'action_id', 'action_sha256', 'dispatch_sha256', 'acquisition_receipt_sha256',
    'acquisition_receipt', 'authority_rejection_receipt_sha256',
    'authority_rejection_receipt', 'advance_request_sha256',
  ])
    && hasExactFields(acquisition, GENERIC_ACQUISITION_FIELDS)
    && hasExactFields(intent, INTENT_FIELDS)
    && hasExactFields(sourceAcquisition, SOURCE_ACQUISITION_FIELDS)
    && hasExactFields(registration, REGISTRATION_FIELDS)
    && hasExactFields(rejection, REJECTION_FIELDS)
    && hasExactFields(outcome, OUTCOME_FIELDS),
  `${context.claimId}: rejected authority primitive field roster differs`);
  invariant(selfHashed(acquisition) && selfHashed(intent) && selfHashed(sourceAcquisition)
    && selfHashed(acquisitionIndex) && selfHashed(claimRegistry)
    && selfHashed(registration) && selfHashed(rejectionIndex)
    && selfHashed(rejection) && selfHashed(outcome),
  `${context.claimId}: rejected authority primitive self-hash differs`);

  const raw = Buffer.from(sourceBlobBase64, 'base64');
  const text = new TextDecoder('utf-8', { fatal:true, ignoreBOM:true }).decode(raw);
  const locatorParts = acquisition.source_locator.split(':');
  const admissionPolicy = context.accepted.observable_package?.workspace_evidence_admission;
  const entries = admissionPolicy?.source_entries || [];
  const matchingEntries = entries.filter(value => value.source_entry_sha256 === sourceAcquisition.source_entry_sha256);
  const entry = matchingEntries[0];
  invariant(raw.length > 0 && raw.length <= MAX_SOURCE_BYTES && !raw.includes(0)
    && text === text.normalize('NFC')
    && locatorParts.length === 4 && locatorParts[0] === 'loopback-source-span'
    && acquisition.contract === 'casepath.acquisition-receipt/1.1.0'
    && acquisition.status === 'observed'
    && acquisition.adapter_id === LOOPBACK_ADAPTER_ID
    && acquisition.session_id === context.sessionId
    && acquisition.loop_id === context.loopId
    && acquisition.record_version === context.recordVersion
    && acquisition.action_id === action.action_id
    && acquisition.action_sha256 === action.action_sha256
    && acquisition.dispatch_sha256 === context.activeDispatchSha
    && acquisition.raw_byte_count === raw.length
    && acquisition.raw_bytes_sha256 === digest(raw)
    && acquisition.sanitized_content === text
    && acquisition.sanitized_content_sha256 === digest(raw)
    && matchingEntries.length === 1
    && entry.source_entry_sha256 === digest(omit(entry, 'source_entry_sha256'))
    && entry.exact_text === text
    && entry.span_sha256 === digest(raw)
    && locatorParts[1] === sourceAcquisition.acquisition_intent_id
    && locatorParts[2] === sourceAcquisition.acquisition_receipt_id
    && locatorParts[3] === sourceAcquisition.source_entry_sha256,
  `${context.claimId}: rejected generic acquisition differs from immutable source bytes`);

  const intentIdentity = omit(intent, 'intent_id', 'receipt_sha256', 'issued_at', 'expires_at');
  invariant(intent.contract === 'casepath.workspace-acquisition-intent/1.0.0'
    && intent.intent_id === `intent.${digest(intentIdentity)}`
    && intent.claim_id === context.claimId
    && intent.session_id === context.sessionId
    && intent.loop_id === context.loopId
    && intent.record_version === context.recordVersion
    && intent.expected_revision === context.authorityParentRevision
    && intent.expected_state_sha256 === context.authorityParentStateSha
    && intent.action_id === action.action_id
    && intent.action_sha256 === action.action_sha256
    && sourceAcquisition.contract === 'casepath.workspace-source-acquisition/1.0.0'
    && sourceAcquisition.claim_id === context.claimId
    && sourceAcquisition.session_id === context.sessionId
    && sourceAcquisition.loop_id === context.loopId
    && sourceAcquisition.record_version === context.recordVersion
    && sourceAcquisition.expected_revision === context.authorityParentRevision
    && sourceAcquisition.expected_state_sha256 === context.authorityParentStateSha
    && sourceAcquisition.acquisition_intent_id === intent.intent_id
    && sourceAcquisition.intent_receipt_sha256 === intent.receipt_sha256
    && sourceAcquisition.action_id === action.action_id
    && sourceAcquisition.action_sha256 === action.action_sha256
    && sourceAcquisition.source_entry_sha256 === entry.source_entry_sha256
    && sourceAcquisition.content_sha256 === digest(raw)
    && sourceAcquisition.content_length === raw.length,
  `${context.claimId}: rejected intent or source acquisition differs`);
  invariant(registration.contract === 'casepath.workspace-evidence-registration-receipt/1.0.0'
    && registration.claim_id === context.claimId
    && registration.session_id === context.sessionId
    && registration.loop_id === context.loopId
    && registration.record_version === context.recordVersion
    && registration.parent_revision === context.authorityParentRevision
    && registration.parent_state_sha256 === context.authorityParentStateSha
    && registration.action_id === action.action_id
    && registration.action_sha256 === action.action_sha256
    && registration.acquisition_intent_id === intent.intent_id
    && registration.intent_receipt_sha256 === intent.receipt_sha256
    && registration.acquisition_receipt_id === sourceAcquisition.acquisition_receipt_id
    && registration.source_acquisition_receipt_sha256 === sourceAcquisition.receipt_sha256
    && registration.content_sha256 === digest(raw)
    && registration.source_entry_sha256 === entry.source_entry_sha256
    && acquisitionIndex.contract === 'casepath.workspace-acquisition-intent-index/1.0.0'
    && acquisitionIndex.acquisition_intent_id === intent.intent_id
    && acquisitionIndex.acquisition_receipt_id === sourceAcquisition.acquisition_receipt_id
    && acquisitionIndex.source_acquisition_receipt_sha256 === sourceAcquisition.receipt_sha256
    && claimRegistry.contract === 'casepath.workspace-claim-content-first-seen/1.0.0'
    && claimRegistry.claim_id === context.claimId
    && claimRegistry.content_sha256 === sourceAcquisition.content_sha256
    && claimRegistry.receipt_sha256 === sourceAcquisition.claim_first_seen_receipt_sha256,
  `${context.claimId}: rejected registration or acquisition index differs`);

  invariant(command.action_id === action.action_id
    && command.action_sha256 === action.action_sha256
    && command.dispatch_sha256 === context.activeDispatchSha
    && command.acquisition_receipt_sha256 === acquisition.receipt_sha256
    && command.authority_rejection_receipt_sha256 === rejection.receipt_sha256
    && canonical(command.authority_rejection_receipt) === canonical(rejection)
    && /^[0-9a-f]{64}$/.test(command.advance_request_sha256)
    && rejection.contract === 'casepath.workspace-authority-rejection/1.0.0'
    && rejection.session_id === context.sessionId
    && rejection.loop_id === context.loopId
    && rejection.claim_id === context.claimId
    && rejection.record_version === context.recordVersion
    && rejection.parent_revision === state.revision
    && rejection.parent_state_sha256 === state.state_sha256
    && rejection.action_id === action.action_id
    && rejection.action_sha256 === action.action_sha256
    && rejection.dispatch_sha256 === context.activeDispatchSha
    && rejection.acquisition_receipt_sha256 === acquisition.receipt_sha256
    && rejection.acquisition_intent_id === intent.intent_id
    && rejection.source_acquisition_receipt_sha256 === sourceAcquisition.receipt_sha256
    && rejection.source_entry_sha256 === sourceAcquisition.source_entry_sha256
    && rejection.content_sha256 === acquisition.sanitized_content_sha256
    && rejection.proposal_sha256 === null
    && rejection.authority_id === 'casepath.independent-evidence-authority/1.0.0'
    && rejection.authority_source_sha256 === expectedAuthoritySourceSha256
    && typeof rejection.reason === 'string' && rejection.reason.length > 0 && rejection.reason.length <= 300
    && rejection.rejected_at === acquisition.acquired_at
    && rejection.authoritative_semantic_effect === false
    && rejectionIndex.contract === 'casepath.workspace-rejection-acquisition-index/1.0.0'
    && rejectionIndex.acquisition_receipt_sha256 === acquisition.receipt_sha256
    && rejectionIndex.rejection_receipt_sha256 === rejection.receipt_sha256
    && outcome.contract === 'casepath.workspace-authority-outcome-index/1.0.0'
    && outcome.acquisition_receipt_sha256 === acquisition.receipt_sha256
    && outcome.decision === 'rejected'
    && outcome.authority_receipt_sha256 === rejection.receipt_sha256,
  `${context.claimId}: rejected event differs from exclusive durable authority`);
  return { acquisition_receipt_sha256:acquisition.receipt_sha256, rejection_receipt_sha256:rejection.receipt_sha256 };
}

function acceptedArtifacts(command) {
  const source = command.accepted_result;
  const keys = [
    'claim_id', 'facts', 'legal_research', 'process', 'checklist', 'verification',
    'next_action', 'agent_orchestration', 'playbook_template',
  ];
  const accepted = Object.fromEntries(keys.map(key => [key, clone(source[key] ?? {})]));
  if (source.playbook_template_record !== undefined) accepted.playbook_template_record = clone(source.playbook_template_record);
  if (source.observable_package !== undefined) accepted.observable_package = clone(source.observable_package);
  return accepted;
}

function templateCatalog(accepted) {
  const catalog = accepted.playbook_template_record?.catalog;
  invariant(catalog && typeof catalog === 'object', 'independent replay lacks its playbook catalog');
  return catalog;
}

function sourceRefId(value) {
  return `source-ref.${digest(value)}`;
}

function pipelineSourceRef(value) {
  const artifactId = value.source_id || value.artifact_id;
  if (value.locator_kind === 'text_quote') {
    return {
      artifact_id: artifactId,
      locator_kind: 'text_quote',
      page: value.page,
      excerpt: value.sanitized_excerpt ?? value.excerpt,
      agent: 'Record-driven Evidence Projector',
    };
  }
  if (value.locator_kind === 'metadata_field') {
    return {
      artifact_id: artifactId,
      locator_kind: 'metadata_field',
      field: value.field,
      value: value.value,
      agent: 'Record-driven Evidence Projector',
    };
  }
  throw new Error(`independent replay saw unsupported locator ${value.locator_kind}`);
}

function applyObservation(fact, observation, catalog) {
  const updated = clone(fact);
  const sourceRefs = observation.source_refs.map(pipelineSourceRef);
  const cumulative = [...(updated.source_refs || [])];
  for (const sourceRef of sourceRefs) {
    if (!cumulative.some(value => canonical(value) === canonical(sourceRef))) cumulative.push(sourceRef);
  }
  updated.source_refs = cumulative;
  if (observation.evidence_status === 'provided_insufficient') {
    if (observation.contract === 'casepath.correction-observation/1.0.0') {
      invariant(observation.fact_state === 'unknown' && observation.normalized_value === null,
        'independent correction attempted to author replacement truth');
      Object.assign(updated, {
        value: observation.value,
        state: 'unknown',
        explanation: observation.explanation,
        confidence: 1.0,
      });
      if (updated.controls_process === true) {
        const safe = catalog.fail_closed_normalized_values[updated.decision_key];
        updated.normalized_value = safe;
        updated.decision_value = catalog.decision_options[updated.decision_key][safe];
      }
    }
    return updated;
  }
  invariant(observation.evidence_status === 'provided_sufficient', 'independent observation status is unsupported');
  Object.assign(updated, {
    value: observation.value,
    state: observation.fact_state,
    explanation: observation.explanation,
    source_refs: cumulative,
    confidence: 1.0,
  });
  if (updated.controls_process === true && observation.fact_state === 'known') {
    updated.normalized_value = observation.normalized_value;
    updated.decision_value = catalog.decision_options[updated.decision_key][observation.normalized_value];
  } else if (updated.controls_process === true) {
    const safe = catalog.fail_closed_normalized_values[updated.decision_key];
    updated.normalized_value = safe;
    updated.decision_value = catalog.decision_options[updated.decision_key][safe];
  } else {
    invariant(observation.normalized_value === null, 'non-controlling fact received a normalized value');
  }
  return updated;
}

function boundedFactCatalog(facts, decisionOptions) {
  return facts.map(value => ({
    fact_id: value.fact_id,
    label: value.label,
    controls_process: value.controls_process,
    decision_key: value.decision_key,
    normalized_options: decisionOptions[value.decision_key] || {},
    admissible_normalized_values: value.controls_process ? [value.normalized_value] : [],
    expected_state: value.state,
    canonical_value: value.value,
    canonical_explanation: value.explanation,
    semantic_role: value.semantic_role,
    deterministic_confidence: value.confidence,
    admissible_text_refs: (value.source_refs || []).filter(ref => ref.locator_kind === 'text_quote').map(ref => ({
      artifact_id: ref.artifact_id,
      page: ref.page,
      excerpt: ref.excerpt,
    })),
    deterministic_text_refs: (value.source_refs || []).filter(ref => ref.locator_kind === 'text_quote').map(clone),
    bounded_enrichments: (value.source_refs || []).filter(ref => ['visual_observation', 'metadata_field'].includes(ref.locator_kind)).map(clone),
  }));
}

function correctionObservation(correction) {
  const effect = correction.effect;
  const payload = {
    contract: 'casepath.correction-observation/1.0.0',
    observation_id: `correction-observation.${correction.correction_sha256}`,
    fact_id: effect.fact_id,
    evidence_item_id: effect.evidence_item_id,
    value: effect.value,
    fact_state: effect.fact_state,
    normalized_value: effect.normalized_value,
    explanation: effect.explanation,
    evidence_status: effect.evidence_status,
    source_refs: [clone(correction.source_ref)],
    observed_at: correction.effective_at,
  };
  return { ...payload, observation_sha256: digest(payload) };
}

function projectionRecords(observations, corrections, ledger) {
  const observationByHash = new Map(observations.map(value => [value.observation_sha256, value]));
  const correctionByHash = new Map(corrections.map(value => [value.correction_sha256, correctionObservation(value)]));
  invariant(ledger.length === observations.length + corrections.length, 'independent projection ledger is not one-to-one');
  return ledger.map(entry => {
    const value = entry.kind === 'observation'
      ? observationByHash.get(entry.record_sha256)
      : correctionByHash.get(entry.record_sha256);
    invariant(value, 'independent projection ledger references an unknown record');
    return value;
  });
}

function projectFacts(accepted, records) {
  const catalog = templateCatalog(accepted);
  const facts = clone(accepted.facts);
  const index = new Map(facts.map((value, offset) => [value.fact_id, offset]));
  for (const record of records) {
    invariant(selfHashed(record, 'observation_sha256'), 'independent projection record is not self-hashed');
    invariant(index.has(record.fact_id), 'independent projection record references an unknown fact');
    facts[index.get(record.fact_id)] = applyObservation(facts[index.get(record.fact_id)], record, catalog);
  }
  const bounded = boundedFactCatalog(facts, catalog.decision_options);
  return { facts, fact_catalog_sha256: digest(bounded) };
}

function decisionProjection(facts, program) {
  const grouped = new Map(program.steps.map(step => [step.decision_key, []]));
  for (const fact of facts) {
    if (fact.controls_process === true && grouped.has(fact.decision_key)) grouped.get(fact.decision_key).push(fact.decision_value);
  }
  const decisions = Object.fromEntries([...grouped].map(([key, values]) => {
    invariant(values.length === 1, `independent route has ${values.length} controlling facts for ${key}`);
    return [key, values[0]];
  }));
  const route = [...program.start_path];
  const stepIndex = new Map(program.steps.map((step, index) => [step.node_id, index]));
  let index = 0;
  while (index < program.steps.length) {
    const step = program.steps[index];
    if (route.at(-1) !== step.node_id) route.push(step.node_id);
    const transition = step.transitions[decisions[step.decision_key]];
    invariant(transition, 'independent route lacks a closed transition');
    if (transition.kind === 'continue') { index += 1; continue; }
    if (transition.kind === 'jump') { index = stepIndex.get(transition.target_node_id); continue; }
    invariant(transition.kind === 'stop', 'independent route transition kind is invalid');
    const selectedPath = [...route];
    if (transition.append_target === true && transition.target_node_id !== step.node_id) selectedPath.push(transition.target_node_id);
    return {
      decisions,
      selected_path: selectedPath,
      current_node: step.node_id,
      next_action_node: transition.target_node_id,
      selected_branch_id: transition.selected_branch_id,
    };
  }
  throw new Error('independent route has no terminal transition');
}

function applyProcessProjection(process, projection, profile) {
  const current = projection.current_node;
  const nextAction = projection.next_action_node;
  const selectedPairs = new Set(projection.selected_path.slice(1).map((target, index) => `${projection.selected_path[index]}\u0000${target}`));
  const completed = projection.selected_path.slice(0, projection.selected_path.indexOf(current));
  const spinePosition = process.main_spine.includes(current) ? process.main_spine.indexOf(current) : process.main_spine.length;
  const blockedCandidates = new Set(profile.blocked_node_ids || []);
  const blocked = process.main_spine.slice(spinePosition + 1).filter(value => blockedCandidates.has(value));
  const branchTargets = new Set();
  const answerByNode = {};
  for (const [nodeId, answers] of Object.entries(profile.answer_by_node || {})) {
    const decision = Object.values(projection.decisions).find(value => Object.hasOwn(answers, value));
    if (decision !== undefined) answerByNode[nodeId] = answers[decision];
  }
  const loopEdges = new Set((profile.loop_edge_pairs || []).map(value => value.join('\u0000')));
  const futureSources = new Set(profile.future_edge_sources || []);
  for (const node of process.nodes) {
    for (const branch of node.branches || []) branchTargets.add(branch.target);
    node.state = completed.includes(node.node_id) ? 'complete'
      : node.node_id === current ? 'current'
        : node.node_id === nextAction ? 'next'
          : blocked.includes(node.node_id) ? 'blocked'
            : node.main_spine ? 'future' : 'inactive';
    if (Object.hasOwn(answerByNode, node.node_id)) node.answer = answerByNode[node.node_id];
    else if (node.main_spine && ['blocked', 'future'].includes(node.state)) node.answer = 'Not reached';
    for (const branch of node.branches || []) branch.state = branch.branch_id === projection.selected_branch_id ? 'selected' : 'possible';
  }
  for (const edge of process.edges) {
    const pair = `${edge.source}\u0000${edge.target}`;
    edge.state = selectedPairs.has(pair) ? 'selected'
      : loopEdges.has(pair) ? 'loop'
        : futureSources.has(edge.source) ? 'future' : 'possible';
  }
  const inactive = [...branchTargets].filter(value => ![nextAction, current].includes(value)).sort();
  return {
    completed_node_ids: completed,
    current_node_id: current,
    selected_branch_id: projection.selected_branch_id,
    blocked_node_ids: blocked,
    inactive_branch_ids: inactive,
    next_action_node_id: nextAction,
    decisions: projection.decisions,
  };
}

function applyEvidenceRelations(process, items) {
  const requirements = new Map(items.map(item => [item.item_id, []]));
  for (const node of process.nodes) {
    for (const itemId of node.evidence_requirement_ids) {
      invariant(requirements.has(itemId), 'independent process references unknown evidence');
      requirements.get(itemId).push(node.node_id);
    }
  }
  const active = new Set([...process.selected_path, process.current_overlay.next_action_node_id]);
  for (const item of items) {
    const owners = requirements.get(item.item_id);
    invariant(owners.length > 0, 'independent evidence item has no process owner');
    item.node_ids = owners;
    item.node_id = owners[0];
    item.current_path = owners.some(value => active.has(value));
  }
}

function applyEvidenceProjection(items, process, mode) {
  const decisions = process.current_overlay.decisions;
  const byId = new Map(items.map(item => [item.item_id, item]));
  const requireCurrent = itemId => {
    const item = byId.get(itemId);
    item.required_level = 'mandatory';
    if (!item.artifact_ids?.length) item.status = 'missing';
    else if (!['provided_sufficient', 'provided_insufficient'].includes(item.status)) item.status = 'provided_insufficient';
  };
  if (mode === 'mould_v20' && decisions.urgency === 'urgency_unverified') {
    const item = byId.get('health_safety_statement');
    item.status = 'missing'; item.artifact_ids = [];
    item.why = 'Current health, safety and deadline information is absent and must be established before ordinary handling continues.';
  }
  if (mode === 'mould_v20' && decisions.notification === 'not_notified') {
    for (const id of ['defect_notice', 'proof_of_delivery']) { byId.get(id).status = 'missing'; byId.get(id).artifact_ids = []; }
  } else if (mode === 'mould_v20' && decisions.notification === 'notification_unverified') {
    const notice = byId.get('defect_notice');
    notice.status = notice.artifact_ids?.length ? 'provided_insufficient' : 'missing';
    byId.get('proof_of_delivery').status = 'missing'; byId.get('proof_of_delivery').artifact_ids = [];
  }
  if (mode === 'mould_v20' && ['recurrence_unverified', 'recurrence_not_supported'].includes(decisions.recurrence)) {
    const photos = byId.get('dated_photos');
    photos.status = photos.artifact_ids?.length ? 'provided_insufficient' : 'missing';
    byId.get('recurrence_chronology').status = 'missing';
  }
  if (mode === 'mould_v20' && decisions.causation === 'cause_building') {
    requireCurrent('building_envelope'); byId.get('use_evidence').status = 'not_applicable';
  } else if (mode === 'mould_v20' && decisions.causation === 'cause_tenant_use') {
    byId.get('building_envelope').status = 'not_applicable'; requireCurrent('use_evidence');
  } else if (mode === 'mould_v20' && decisions.causation === 'cause_mixed') {
    requireCurrent('building_envelope'); requireCurrent('use_evidence');
  }
  const active = new Set([...process.selected_path, process.current_overlay.next_action_node_id]);
  for (const item of items) {
    const ownerIds = item.node_ids?.length ? item.node_ids : [item.node_id];
    item.current_path = ownerIds.some(value => active.has(value));
    if (mode === 'current_path_only_v1' && item.current_path && item.status === 'conditional') {
      item.required_level = 'mandatory';
      item.status = item.artifact_ids?.length ? 'provided_insufficient' : 'missing';
      item.applies_when = 'always';
    }
    if (!item.current_path && item.status === 'missing') {
      item.status = 'conditional'; item.required_level = 'conditional';
      item.applies_when = `One of the linked process nodes is reached: ${ownerIds.join(', ')}`;
    }
  }
  if (mode === 'mould_v20' && decisions.urgency === 'urgency_unverified') {
    const item = byId.get('health_safety_statement');
    item.status = 'missing'; item.artifact_ids = []; item.required_level = 'mandatory';
  }
}

function checklistSections(items) {
  const present = [];
  const required = [];
  for (const item of items) {
    if (item.status.startsWith('provided')) {
      present.push({
        item_id: item.item_id, title: item.title,
        status: item.status === 'provided_sufficient' ? 'available' : 'insufficient',
        node_id: item.node_id, fact: item.fact_id, why: item.why,
        artifact_id: item.artifact_ids?.[0] ?? null,
      });
    } else if (['missing', 'conditional'].includes(item.status) && item.current_path) {
      required.push({
        item_id: item.item_id, title: item.title,
        status: item.status === 'missing' ? 'still_needed' : 'conditional',
        node_id: item.node_id, fact: item.fact_id, why: item.why,
        mandatory: item.status === 'missing' ? 'now' : item.applies_when,
        already_supplied: false,
      });
    }
  }
  const summary = {
    provided_sufficient: items.filter(item => item.status === 'provided_sufficient').length,
    provided_insufficient: items.filter(item => item.status === 'provided_insufficient').length,
    missing: items.filter(item => item.status === 'missing').length,
    conditional: items.filter(item => item.status === 'conditional').length,
    not_applicable: items.filter(item => item.status === 'not_applicable').length,
    process_nodes_covered: new Set(items.flatMap(item => item.node_ids || [item.node_id])).size,
  };
  return { present, required, summary };
}

function projectMajorArtifacts(accepted, observations, corrections, ledger) {
  const catalog = templateCatalog(accepted);
  const records = projectionRecords(observations, corrections, ledger);
  const factProjection = projectFacts(accepted, records);
  const process = clone(accepted.process);
  const route = decisionProjection(factProjection.facts, catalog.route_program);
  process.selected_path = clone(route.selected_path);
  process.current_node = route.current_node;
  process.current_overlay = applyProcessProjection(process, route, catalog.process_rendering_profile);
  const checklist = clone(accepted.checklist);
  applyEvidenceRelations(process, checklist.items);
  applyEvidenceProjection(checklist.items, process, catalog.evidence_projection_mode);
  const updates = new Map();
  for (const record of records) {
    updates.set(record.evidence_item_id, {
      status: record.evidence_status,
      source_ref_ids: record.source_refs.map(sourceRefId),
      artifact_ids: record.source_refs.map(value => value.source_id),
    });
  }
  for (const item of checklist.items) {
    const update = updates.get(item.item_id);
    if (update) {
      item.status = update.status === 'unavailable' ? 'missing' : update.status;
      item.loop_source_ref_ids = update.source_ref_ids;
      item.artifact_ids = update.artifact_ids;
    }
  }
  applyEvidenceRelations(process, checklist.items);
  Object.assign(checklist, checklistSections(checklist.items));
  return { ...factProjection, process, checklist };
}

const SPECIALIST_ARTIFACT_KEYS = Object.freeze([
  'document_source_integrity',
  'evidence_checklist',
  'final_claim_brief_audit',
  'orchestrator_plan',
  'process_decision_mapping',
]);

function reconstructAcceptedCycle(major, verification, graphAudit) {
  const specialists = graphAudit?.specialist_artifacts;
  invariant(specialists && canonical(Object.keys(specialists).sort()) === canonical([...SPECIALIST_ARTIFACT_KEYS].sort()),
    'cycle graph has an unsupported specialist-artifact roster');
  invariant(SPECIALIST_ARTIFACT_KEYS.every(key => specialists[key]
    && typeof specialists[key] === 'object' && !Array.isArray(specialists[key])),
  'cycle graph has a malformed specialist artifact');
  const finalBrief = graphAudit.final_claim_brief;
  invariant(finalBrief && typeof finalBrief === 'object' && !Array.isArray(finalBrief)
    && canonical(finalBrief) === canonical(specialists.final_claim_brief_audit),
  'cycle graph final brief and final specialist artifact differ');
  const rolePayload = {
    contract: 'casepath.accepted-role-artifacts/1.0.0',
    canonical_facts: clone(major.facts),
    ...Object.fromEntries([...SPECIALIST_ARTIFACT_KEYS].sort().map(key => [key, clone(specialists[key])])),
  };
  const roleArtifacts = { ...rolePayload, receipt_sha256: digest(rolePayload) };
  const payload = {
    contract: 'casepath.accepted-cycle-artifacts/1.0.0',
    facts: clone(major.facts),
    process: clone(major.process),
    checklist: clone(major.checklist),
    final_claim_brief: clone(finalBrief),
    verification: clone(verification),
    role_artifacts: roleArtifacts,
  };
  return { ...payload, receipt_sha256: digest(payload) };
}

function deriveAndBindAcceptedCycle(context, journalCycle) {
  const major = projectMajorArtifacts(
    context.accepted, context.observations, context.corrections, context.ledger,
  );
  const reconstructed = reconstructAcceptedCycle(major, context.verification, context.graphAudit);
  invariant(selfHashed(journalCycle) && canonical(reconstructed) === canonical(journalCycle),
    'journal accepted-cycle envelope differs from independently reconstructed authority');
  return reconstructed;
}

function derivedArtifacts(accepted, major, observations, corrections, ledger) {
  const factById = new Map(major.facts.map(value => [value.fact_id, value]));
  const acceptedFactById = new Map(accepted.facts.map(value => [value.fact_id, value]));
  const obligations = major.checklist.items.map(item => {
    const fact = factById.get(item.fact_id);
    const status = fact.state === 'conflicting' ? 'contradicted'
      : item.status === 'provided_sufficient' && fact.state === 'known' ? 'satisfied'
        : item.status === 'conditional' ? 'conditional'
          : !item.current_path || item.status === 'not_applicable' ? 'blocked' : 'active';
    const seed = (acceptedFactById.get(item.fact_id)?.source_refs || []).map(sourceRefId);
    const refs = [...new Set([...seed, ...(item.loop_source_ref_ids || [])])];
    return {
      obligation_id: item.item_id,
      process_node_ids: clone(item.node_ids || [item.node_id]),
      fact_id: item.fact_id,
      status,
      evidence_status: item.status,
      mandatory_now: Boolean(item.current_path) && item.required_level === 'mandatory' && ['active', 'contradicted'].includes(status),
      source_ref_ids: refs,
    };
  });
  const observationsByHash = new Map(observations.map(value => [value.observation_sha256, value]));
  const correctionsByHash = new Map(corrections.map(value => [value.correction_sha256, value]));
  const provenance = [];
  for (const item of major.checklist.items) {
    const acceptedFact = acceptedFactById.get(item.fact_id) || {};
    for (const sourceRef of acceptedFact.source_refs || []) {
      provenance.push({
        observation_sha256: digest({
          contract: 'casepath.accepted-fact-provenance/1.0.0',
          accepted_fact_sha256: digest(acceptedFact),
          evidence_item_id: item.item_id,
          source_ref: clone(sourceRef),
        }),
        source_ref_id: sourceRefId(sourceRef),
        fact_id: item.fact_id,
        evidence_item_id: item.item_id,
      });
    }
  }
  for (const entry of ledger) {
    if (entry.kind === 'observation') {
      const observation = observationsByHash.get(entry.record_sha256);
      for (const sourceRef of observation.source_refs) provenance.push({
        observation_sha256: observation.observation_sha256,
        source_ref_id: sourceRefId(sourceRef),
        fact_id: observation.fact_id,
        evidence_item_id: observation.evidence_item_id,
      });
    } else {
      const correction = correctionsByHash.get(entry.record_sha256);
      provenance.push({
        observation_sha256: correction.correction_sha256,
        source_ref_id: sourceRefId(correction.source_ref),
        fact_id: correction.effect.fact_id,
        evidence_item_id: correction.effect.evidence_item_id,
      });
    }
  }
  const unresolved = obligations.filter(value => value.mandatory_now).map(value => value.obligation_id);
  const contradicted = obligations.filter(value => value.status === 'contradicted').map(value => value.obligation_id);
  const uncertainty = major.facts.filter(value => ['unknown', 'conflicting'].includes(value.state)).map(value => value.fact_id);
  const requiredFacts = new Set(obligations.filter(value => value.mandatory_now
    || (value.status === 'contradicted' && major.checklist.items.some(item => item.item_id === value.obligation_id && item.current_path)))
    .map(value => value.fact_id));
  const controllingFacts = new Set(major.facts.filter(value => value.controls_process === true).map(value => value.fact_id));
  const blocking = uncertainty.filter(value => requiredFacts.has(value) || controllingFacts.has(value));
  const provenanceKeys = new Set(provenance.map(value => canonical([value.fact_id, value.evidence_item_id, value.source_ref_id])));
  const provenanceComplete = obligations.filter(value => value.status === 'satisfied').every(value => value.source_ref_ids.length > 0
    && value.source_ref_ids.every(ref => provenanceKeys.has(canonical([value.fact_id, value.obligation_id, ref]))));
  return {
    obligations,
    uncertainty_fact_ids: uncertainty,
    blocking_uncertainty_fact_ids: blocking,
    provenance_edges: provenance,
    sufficiency: {
      status: unresolved.length === 0 && contradicted.length === 0 && blocking.length === 0 && provenanceComplete
        ? 'decision_ready' : 'insufficient',
      unresolved_mandatory_obligation_ids: unresolved,
      contradicted_obligation_ids: contradicted,
      provenance_complete: provenanceComplete,
    },
  };
}

function deriveAction(process, checklist, obligations, history) {
  const byId = new Map(obligations.map(value => [value.obligation_id, value]));
  const candidates = checklist.items.map((item, index) => [index, item, byId.get(item.item_id)]).filter(([, item, obligation]) => {
    const attempts = history.filter(value => value.action.evidence_item_id === item.item_id && value.outcome === 'observed').length;
    return obligation && !history.some(value => value.action.evidence_item_id === item.item_id
      && ['unavailable', 'failed', 'unknown'].includes(value.outcome))
      && (item.max_observed_attempts === undefined || attempts < item.max_observed_attempts);
  });
  const mandatory = candidates.filter(([, , obligation]) => obligation.mandatory_now);
  const conditional = candidates.filter(([, item, obligation]) => obligation.status === 'conditional'
    && (item.node_ids || [item.node_id]).includes(process.current_overlay.next_action_node_id));
  const eligible = mandatory.length ? mandatory : conditional;
  if (!eligible.length) return null;
  const [, item, obligation] = eligible[0];
  const payload = {
    contract: 'casepath.evidence-action/1.0.0',
    action_kind: obligation.status === 'contradicted' ? 'clarify'
      : item.status === 'provided_insufficient' ? 'validate' : 'acquire',
    process_node_id: process.current_overlay.next_action_node_id,
    evidence_item_id: item.item_id,
    fact_id: item.fact_id,
    title: item.title,
    bounded_tool_id: item.bounded_tool_id || DEFAULT_TOOL_ID,
  };
  const actionSha = digest(payload);
  return { ...payload, action_id: `action.${actionSha}`, action_sha256: actionSha };
}

function zeroActivity() {
  return {
    contract: 'casepath.bound-activity/1.0.0', scope: 'incremental_loop', graph_traversal_count: 0,
    model_calls: 0, provider_calls: 0, activity_receipt_sha256s: [], execution_identity_sha256s: [],
    credential_access_status: 'none_due_to_zero_provider_calls', credential_access_receipt_sha256s: [],
    cost_status: 'exact', cost_usd: 0.0,
  };
}

function activityFromCycle(scope, receipt) {
  return {
    contract: 'casepath.bound-activity/1.0.0', scope, graph_traversal_count: 1,
    model_calls: receipt.model_calls, provider_calls: receipt.provider_calls,
    activity_receipt_sha256s: [receipt.receipt_sha256], execution_identity_sha256s: [receipt.graph_audit_sha256],
    credential_access_status: receipt.credential_access_status,
    credential_access_receipt_sha256s: clone(receipt.credential_access_receipt_sha256s),
    cost_status: receipt.cost_status, cost_usd: receipt.cost_usd,
  };
}

function addCycle(activity, receipt) {
  const next = activityFromCycle('incremental_loop', receipt);
  const exact = activity.cost_status === 'exact' && next.cost_status === 'exact';
  return {
    contract: 'casepath.bound-activity/1.0.0', scope: 'incremental_loop',
    graph_traversal_count: activity.graph_traversal_count + 1,
    model_calls: activity.model_calls + next.model_calls,
    provider_calls: activity.provider_calls + next.provider_calls,
    activity_receipt_sha256s: [...activity.activity_receipt_sha256s, ...next.activity_receipt_sha256s],
    execution_identity_sha256s: [...activity.execution_identity_sha256s, ...next.execution_identity_sha256s],
    credential_access_status: [activity, next].some(value => value.credential_access_status === 'receipt_bound') ? 'receipt_bound'
      : [activity, next].some(value => value.credential_access_status === 'not_measured') ? 'not_measured' : 'none_due_to_zero_provider_calls',
    credential_access_receipt_sha256s: [...activity.credential_access_receipt_sha256s, ...next.credential_access_receipt_sha256s],
    cost_status: exact ? 'exact' : 'unknown',
    cost_usd: exact ? Math.round(((activity.cost_usd || 0) + (next.cost_usd || 0)) * 1e8) / 1e8 : null,
  };
}

function totalActivity(upstream, source, incremental) {
  const activities = [upstream, source, incremental];
  const sourceReuses = upstream.graph_traversal_count === 1 && source.graph_traversal_count === 1
    && canonical(upstream.execution_identity_sha256s) === canonical(source.execution_identity_sha256s);
  const accounted = sourceReuses ? [upstream, incremental] : activities;
  const exact = accounted.every(value => value.cost_status === 'exact');
  return {
    contract: 'casepath.bound-activity/1.0.0', scope: 'total_bound',
    graph_traversal_count: new Set(activities.flatMap(value => value.execution_identity_sha256s)).size,
    model_calls: accounted.reduce((sum, value) => sum + value.model_calls, 0),
    provider_calls: accounted.reduce((sum, value) => sum + value.provider_calls, 0),
    activity_receipt_sha256s: activities.flatMap(value => value.activity_receipt_sha256s),
    execution_identity_sha256s: [...new Set(activities.flatMap(value => value.execution_identity_sha256s))],
    credential_access_status: accounted.some(value => value.credential_access_status === 'receipt_bound') ? 'receipt_bound'
      : accounted.some(value => value.credential_access_status === 'not_measured') ? 'not_measured' : 'none_due_to_zero_provider_calls',
    credential_access_receipt_sha256s: activities.flatMap(value => value.credential_access_receipt_sha256s),
    cost_status: exact ? 'exact' : 'unknown',
    cost_usd: exact ? Math.round(accounted.reduce((sum, value) => sum + (value.cost_usd || 0), 0) * 1e8) / 1e8 : null,
  };
}

function validateCycle(receipt, verification, graphAudit, acceptedCycle, { kind, priorStateSha, triggerSha, sourceRunId, loopId, templateSha }) {
  invariant(selfHashed(receipt), 'six-agent cycle receipt is not self-hashed');
  invariant(receipt.cycle_kind === kind && receipt.prior_state_sha256 === priorStateSha && receipt.trigger_sha256 === triggerSha,
    'six-agent cycle boundary is invalid');
  invariant(receipt.source_run_id === sourceRunId && receipt.loop_id === loopId
    && receipt.playbook_template_sha256 === templateSha
    && receipt.facts_sha256 === digest(acceptedCycle.facts)
    && receipt.process_sha256 === digest(acceptedCycle.process)
    && receipt.checklist_sha256 === digest(acceptedCycle.checklist)
    && receipt.accepted_cycle_artifacts_sha256 === acceptedCycle.receipt_sha256
    && receipt.final_claim_brief_sha256 === digest(acceptedCycle.final_claim_brief)
    && receipt.verification_sha256 === digest(verification)
    && receipt.graph_audit_sha256 === digest(graphAudit),
  'six-agent cycle hashes do not bind the projected state');
  invariant(receipt.model_calls === 0 && receipt.provider_calls === 0
    && receipt.credential_access_status === 'none_due_to_zero_provider_calls'
    && receipt.cost_status === 'exact' && receipt.cost_usd === 0,
  'six-agent cycle is not provider-free');
  invariant(selfHashed(verification) && verification.facts_sha256 === digest(acceptedCycle.facts)
    && verification.process_sha256 === digest(acceptedCycle.process)
    && verification.checklist_sha256 === digest(acceptedCycle.checklist)
    && verification.whole_playbook_hash === digest({ process: acceptedCycle.process, checklist: acceptedCycle.checklist }),
  'cycle verification is not independently bound');
}

function buildState(context, sequence, eventSha, forceSelect) {
  const major = projectMajorArtifacts(
    context.accepted, context.observations, context.corrections, context.ledger,
  );
  const acceptedCycle = reconstructAcceptedCycle(major, context.verification, context.graphAudit);
  invariant(canonical(acceptedCycle) === canonical(context.acceptedCycle),
    'state build accepted-cycle authority differs from its independent reconstruction');
  const derived = derivedArtifacts(context.accepted, major, context.observations, context.corrections, context.ledger);
  let selectedAction = context.selectedAction;
  let phase = sequence > 1 ? 'replanning' : 'compiled';
  let terminalMode = null;
  let abstainReason = null;
  const sufficiency = clone(derived.sufficiency);
  if (sufficiency.status === 'decision_ready') {
    selectedAction = null; terminalMode = 'finalize'; phase = 'decision_ready';
  } else if (forceSelect) {
    selectedAction = deriveAction(major.process, major.checklist, derived.obligations, context.history);
    if (selectedAction === null) {
      terminalMode = 'abstain';
      abstainReason = 'mandatory evidence is unresolved and no bounded action remains';
      phase = 'abstained';
      sufficiency.status = 'abstain';
    } else phase = 'awaiting_observation';
  } else if (context.activeDispatchSha && selectedAction) phase = 'dispatching';
  else if (selectedAction) phase = 'awaiting_observation';
  context.selectedAction = selectedAction;
  const payload = {
    contract: 'casepath.claim-loop-state/1.0.0',
    session_id: context.sessionId,
    loop_id: context.loopId,
    claim_id: context.claimId,
    source_run_id: context.sourceRunId,
    record_version: context.recordVersion,
    revision: sequence,
    phase,
    accepted_artifacts_sha256: digest(context.accepted),
    accepted_artifacts: clone(context.accepted),
    observations: clone(context.observations),
    projection_ledger: clone(context.ledger),
    facts: major.facts,
    fact_catalog_sha256: major.fact_catalog_sha256,
    process: major.process,
    checklist: major.checklist,
    accepted_cycle_artifacts_sha256: acceptedCycle.receipt_sha256,
    accepted_cycle_artifacts: acceptedCycle,
    deterministic_gate_receipt: clone(context.verification),
    six_agent_verification: clone(context.verification),
    six_agent_graph_audit: clone(context.graphAudit),
    six_agent_cycle_receipt: clone(context.cycleReceipt),
    upstream_source_run_activity: clone(context.upstreamActivity),
    source_acceptance_activity: clone(context.sourceActivity),
    incremental_loop_activity: clone(context.incrementalActivity),
    total_bound_activity: totalActivity(context.upstreamActivity, context.sourceActivity, context.incrementalActivity),
    obligations: derived.obligations,
    uncertainty_fact_ids: derived.uncertainty_fact_ids,
    blocking_uncertainty_fact_ids: derived.blocking_uncertainty_fact_ids,
    selected_action: clone(selectedAction),
    action_history: clone(context.history),
    sufficiency,
    provenance_edges: derived.provenance_edges,
    corrections: clone(context.corrections),
    correction_reuse_receipts: [],
    active_dispatch_sha256: context.activeDispatchSha,
    active_dispatch_owner: context.activeDispatchOwner,
    active_dispatch_expires_at: context.activeDispatchExpiresAt,
    terminal_mode: terminalMode,
    abstain_reason: abstainReason,
    last_event_sha256: eventSha,
  };
  return { ...payload, state_sha256: digest(payload) };
}

export function replayClaimLoopJournalV1(rows, claimId, options = {}) {
  const authorityByAcquisition = options.authorityByAcquisition || new Map();
  let context = null;
  let state = null;
  const stateReceipts = [];
  const effects = [];
  const artifactReceipts = [];
  for (const row of rows) {
    const event = row.event || row;
    const command = event.command;
    let forceSelect = false;
    if (context === null) {
      invariant(event.sequence === 1 && event.event_type === 'LOOP_CREATED', `${claimId}: first raw event is not LOOP_CREATED`);
      const accepted = acceptedArtifacts(command);
      invariant(accepted.claim_id === claimId, `${claimId}: accepted artifacts bind another claim`);
      const cycle = clone(command.six_agent_cycle_receipt);
      const journalAcceptedCycle = clone(command.accepted_cycle_artifacts);
      const verification = clone(command.six_agent_verification);
      const graphAudit = clone(command.six_agent_graph_audit);
      const sourceActivity = activityFromCycle('source_acceptance', cycle);
      invariant(canonical(sourceActivity) === canonical(command.source_acceptance_activity), 'source activity differs from its cycle');
      context = {
        sessionId: command.session_id, loopId: command.loop_id, claimId: command.claim_id,
        sourceRunId: command.source_run_id, recordVersion: command.record_version,
        accepted, observations: [], corrections: [], ledger: [], history: [], selectedAction: null,
        acceptedCycle: null, verification, graphAudit, cycleReceipt: cycle,
        upstreamActivity: clone(command.upstream_source_run_activity), sourceActivity,
        incrementalActivity: zeroActivity(), activeDispatchSha: null, activeDispatchOwner: null,
        activeDispatchExpiresAt: null,
        authorityParentRevision: null, authorityParentStateSha: null,
      };
      context.acceptedCycle = deriveAndBindAcceptedCycle(context, journalAcceptedCycle);
      validateCycle(cycle, verification, graphAudit, context.acceptedCycle, {
        kind: 'source_acceptance', priorStateSha: null, triggerSha: digest(command.accepted_result),
        sourceRunId: command.source_run_id, loopId: command.loop_id,
        templateSha: accepted.playbook_template.template_sha256,
      });
      effects.push({ claim_id: claimId, sequence: event.sequence, event_type: event.event_type, effect: 'loop_created' });
    } else if (event.event_type === 'ACTION_SELECTED') {
      invariant(context.selectedAction === null && context.activeDispatchSha === null, `${claimId}: action selection has an outstanding action`);
      forceSelect = true;
      effects.push({ claim_id: claimId, sequence: event.sequence, event_type: event.event_type, effect: 'bounded_action_selected' });
    } else if (event.event_type === 'ACTION_DISPATCH_STARTED') {
      invariant(context.selectedAction && command.action_id === context.selectedAction.action_id
        && command.action_sha256 === context.selectedAction.action_sha256
        && command.adapter_id === context.selectedAction.bounded_tool_id
        && context.activeDispatchSha === null,
      `${claimId}: dispatch is not bound to the independently selected action`);
      context.authorityParentRevision = state.revision;
      context.authorityParentStateSha = state.state_sha256;
      context.activeDispatchSha = event.event_sha256;
      context.activeDispatchOwner = command.lease_owner;
      context.activeDispatchExpiresAt = command.lease_expires_at;
      effects.push({
        claim_id: claimId, sequence: event.sequence, event_type: event.event_type,
        effect: 'dispatch_started', dispatch_sha256: event.event_sha256,
        action_sha256: command.action_sha256,
      });
    } else if (event.event_type === 'OBSERVATION_INGESTED') {
      const artifact = clone(command.tool_artifact_receipt);
      invariant(context.selectedAction && command.action_id === context.selectedAction.action_id
        && selfHashed(artifact)
        && selfHashed(command.evidence_authority_binding, 'binding_sha256'),
      `${claimId}: raw observation lacks its independent action/authority binding`);
      const derived = deriveAuthorityObservation(
        context,
        state,
        context.selectedAction,
        artifact,
        command.evidence_authority_binding,
        authorityByAcquisition.get(artifact.acquisition_receipt_sha256),
      );
      const observation = derived.observation;
      invariant(selfHashed(observation, 'observation_sha256')
        && observation.fact_id === context.selectedAction.fact_id
        && observation.evidence_item_id === context.selectedAction.evidence_item_id
        && command.dispatch_sha256 === context.activeDispatchSha
        && artifact.action_id === context.selectedAction.action_id
        && artifact.action_sha256 === context.selectedAction.action_sha256
        && artifact.dispatch_sha256 === context.activeDispatchSha
        && artifact.interpretation.receipt_sha256 === derived.interpretation.receipt_sha256
        && canonical(command.observation) === canonical(observation)
        && canonical(artifact.observation) === canonical(observation),
      `${claimId}: raw observation lacks its independent action/dispatch/artifact binding`);
      const priorStateSha = state.state_sha256;
      const action = clone(context.selectedAction);
      context.observations.push(observation);
      context.ledger.push({
        kind: 'observation', record_sha256: observation.observation_sha256,
        artifact_receipt_sha256: command.artifact_receipt_sha256, recorded_at: event.created_at,
      });
      context.history.push({ action, outcome: 'observed', observation_sha256: observation.observation_sha256, recorded_at: event.created_at });
      context.selectedAction = null;
      context.activeDispatchSha = null; context.activeDispatchOwner = null; context.activeDispatchExpiresAt = null;
      context.authorityParentRevision = null; context.authorityParentStateSha = null;
      context.verification = clone(command.six_agent_verification);
      context.graphAudit = clone(command.six_agent_graph_audit);
      context.acceptedCycle = deriveAndBindAcceptedCycle(context, command.accepted_cycle_artifacts);
      context.cycleReceipt = clone(command.six_agent_cycle_receipt);
      validateCycle(context.cycleReceipt, context.verification, context.graphAudit, context.acceptedCycle, {
        kind: 'observation', priorStateSha, triggerSha: observation.observation_sha256,
        sourceRunId: context.sourceRunId, loopId: context.loopId,
        templateSha: context.accepted.playbook_template.template_sha256,
      });
      context.incrementalActivity = addCycle(context.incrementalActivity, context.cycleReceipt);
      artifactReceipts.push(artifact);
      forceSelect = true;
      effects.push({
        claim_id: claimId, sequence: event.sequence, event_type: event.event_type,
        effect: 'one_observation_ingested', fact_id: observation.fact_id,
        evidence_item_id: observation.evidence_item_id,
        observation_sha256: observation.observation_sha256,
        authority_binding_sha256: command.evidence_authority_binding.binding_sha256,
      });
    } else if (event.event_type === 'EVIDENCE_PROPOSAL_REJECTED') {
      invariant(context.selectedAction && context.activeDispatchSha,
        `${claimId}: rejected evidence has no active bounded dispatch`);
      const rejectedAction = clone(context.selectedAction);
      const rejectionBinding = validateAuthorityRejection(
        context,
        state,
        context.selectedAction,
        command,
        authorityByAcquisition.get(command.acquisition_receipt_sha256),
      );
      context.activeDispatchSha = null;
      context.activeDispatchOwner = null;
      context.activeDispatchExpiresAt = null;
      context.authorityParentRevision = null;
      context.authorityParentStateSha = null;
      effects.push({
        claim_id:claimId,
        sequence:event.sequence,
        event_type:event.event_type,
        effect:'one_proposal_rejected_zero_semantic_effect',
        action_sha256:rejectedAction.action_sha256,
        acquisition_receipt_sha256:rejectionBinding.acquisition_receipt_sha256,
        rejection_receipt_sha256:rejectionBinding.rejection_receipt_sha256,
        authoritative_semantic_effect:false,
      });
    } else if (event.event_type === 'CORRECTION_APPLIED') {
      const correction = clone(command.correction);
      const correctionArtifact = clone(command.correction_artifact_receipt);
      const sourceArtifact = clone(command.source_tool_artifact_receipt);
      const targetFact = state.facts.find(value => value.fact_id === correction.effect.fact_id);
      const targetEvidence = state.checklist.items.find(value => value.item_id === correction.effect.evidence_item_id);
      const beforeSemantics = {
        fact_state: targetFact.state, normalized_value: targetFact.normalized_value,
        value: targetFact.value, explanation: targetFact.explanation,
        evidence_status: targetEvidence.status,
      };
      invariant(correction.correction_sha256 === digest(omit(correction, 'correction_id', 'correction_sha256'))
        && selfHashed(correctionArtifact) && selfHashed(sourceArtifact)
        && canonical(command.before_semantics) === canonical(beforeSemantics)
        && correctionArtifact.unrelated_facts_before_sha256 === correctionArtifact.unrelated_facts_after_sha256,
      `${claimId}: raw correction lacks exact parent/locality authority`);
      const priorStateSha = state.state_sha256;
      context.corrections.push(correction);
      context.ledger.push({
        kind: 'correction', record_sha256: correction.correction_sha256,
        artifact_receipt_sha256: correction.source_artifact_receipt_sha256,
        recorded_at: correction.effective_at,
      });
      context.selectedAction = null;
      context.verification = clone(command.six_agent_verification);
      context.graphAudit = clone(command.six_agent_graph_audit);
      context.acceptedCycle = deriveAndBindAcceptedCycle(context, command.accepted_cycle_artifacts);
      context.cycleReceipt = clone(command.six_agent_cycle_receipt);
      validateCycle(context.cycleReceipt, context.verification, context.graphAudit, context.acceptedCycle, {
        kind: 'correction', priorStateSha, triggerSha: correction.correction_sha256,
        sourceRunId: context.sourceRunId, loopId: context.loopId,
        templateSha: context.accepted.playbook_template.template_sha256,
      });
      context.incrementalActivity = addCycle(context.incrementalActivity, context.cycleReceipt);
      artifactReceipts.push(sourceArtifact);
      forceSelect = true;
      effects.push({
        claim_id: claimId, sequence: event.sequence, event_type: event.event_type,
        effect: 'scoped_correction_applied', correction_sha256: correction.correction_sha256,
        fact_id: correction.effect.fact_id, evidence_item_id: correction.effect.evidence_item_id,
        before_semantics: command.before_semantics, after_semantics: command.after_semantics,
        unrelated_facts_before_sha256: correctionArtifact.unrelated_facts_before_sha256,
        unrelated_facts_after_sha256: correctionArtifact.unrelated_facts_after_sha256,
      });
    } else {
      throw new Error(`${claimId}: independent replay rejects event ${event.event_type}`);
    }
    state = buildState(context, event.sequence, event.event_sha256, forceSelect);
    invariant(state.state_sha256 === event.resulting_state_sha256,
      `${claimId}: independent state hash differs at event ${event.sequence} ${event.event_type}`);
    if (event.event_type === 'CORRECTION_APPLIED') {
      const correctedFact = state.facts.find(value => value.fact_id === command.correction.effect.fact_id);
      const correctedEvidence = state.checklist.items.find(value => value.item_id === command.correction.effect.evidence_item_id);
      invariant(canonical(command.after_semantics) === canonical({
        fact_state: correctedFact.state, normalized_value: correctedFact.normalized_value,
        value: correctedFact.value, explanation: correctedFact.explanation,
        evidence_status: correctedEvidence.status,
      }), `${claimId}: correction after semantics differ from independent state`);
    }
    stateReceipts.push({
      claim_id: claimId, sequence: event.sequence, event_type: event.event_type,
      event_sha256: event.event_sha256, recomputed_state_sha256: state.state_sha256,
      expected_state_sha256: event.resulting_state_sha256,
    });
  }
  invariant(state, `${claimId}: independent replay is empty`);
  return {
    final_state: state,
    state_receipts: stateReceipts,
    effects,
    artifact_receipts: artifactReceipts,
  };
}
