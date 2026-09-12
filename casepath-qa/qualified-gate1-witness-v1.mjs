import {createHash} from 'node:crypto';

const SELECTOR_ID = 'casepath.gate1-qualified-witness-selector/1.0.0';
const INTAKE_COMPILER_ID = 'casepath.observable-message-policy-compiler/1.1.0';
const INTAKE_CATALOG_SHA256 = 'd550af3b4361098e1717f54422f219753b24fee854f8639d4f7bfa4de460b6d1';

const INTAKE_TERMS = Object.freeze({
  defect_mold_heating: Object.freeze([
    'abwasserrückstau', 'boiler failure', 'dampness', 'feuchtigkeit', 'heating failure',
    'heizkesselausfall', 'heizungsausfall', 'leakage', 'mold', 'mould', 'moisture',
    'multi-unit leak', 'schimmel', 'sewage backflow', 'water leak', 'wasserleck',
    'wiederholter heizungsausfall', 'wohnungsübergreifende leckage',
  ].sort()),
  lease_termination_dispute: Object.freeze([
    'arrears termination', 'family-home termination', 'familienwohnung', 'kündigung',
    'termination', 'termination notice', 'verzugskündigung',
  ].sort()),
  rent_increase_dispute: Object.freeze([
    'amtlich mitgeteilte erhöhung', 'ancillary charges', 'erhöhungsformular', 'increase form',
    'mietzinserhöhung', 'nebenkosten', 'official increase', 'officially notified increase',
    'reference-rate', 'referenzzins', 'renovation grant', 'renovation-related increase',
    'rent increase', 'sanierungsbeitrag', 'sanierungsbedingte erhöhung',
  ].sort()),
});

const QUALIFICATION_GRAMMAR = Object.freeze({
  contract: 'casepath.gate1-qualified-witness-grammar/1.0.0',
  input_surface: Object.freeze([
    'pristine_queue_projection',
    'public_corpus_manifest',
    'observable_customer_message',
    'public_source_registry',
    'static_playbook',
  ]),
  excluded_surface: Object.freeze([
    'benchmark_labels',
    'expected_actions',
    'selected_runtime_actions',
    'runtime_outcomes',
    'admission_results',
    'correction_results',
  ]),
  eligible_domains: Object.freeze(['lease_termination_dispute', 'rent_increase_dispute']),
  required_intake_owner: 'claim_handler',
  required_outgoing_transition_count: 1,
  adapter_candidate_rule: 'earliest-substantive-span-with-domain-transition-term-then-source-sha256',
  token_count: Object.freeze({minimum:5, maximum:64}),
  terminal_punctuation: Object.freeze(['.', ';', ':', '!', '?']),
  clause_delimiters: Object.freeze(['\n', '\r', '!', '.', ':', ';', '?']),
  transition_terms: Object.freeze({
    lease_termination_dispute: Object.freeze([
      'notice of termination', 'termination notice', 'mietvertragskündigung',
      'kündigungsschreiben', 'termination', 'kündigung',
    ]),
    rent_increase_dispute: Object.freeze([
      'rent increases', 'rent increase', 'rent rises', 'mietzinserhöhung',
      'bruttomiete', 'nettomiete', 'gross rent', 'net rent', 'mietzins',
    ]),
  }),
  transition_count: 1,
  transition_scope: 'smallest-colon-semicolon-or-sentence-delimited-clause-containing-transition',
  forbidden_marker_scope: 'transition-clause-only',
  instruction_pattern_scope: 'entire-selected-span',
  unicode_normalization: 'NFC',
  offset_unit: 'unicode-code-point-with-separate-utf8-byte-offsets',
  word_category: 'Unicode Letter|Mark|Number|Connector_Punctuation',
  forbidden_transition_clause_markers: Object.freeze({
    negation: Object.freeze([
      'no', 'not', 'never', 'without', 'kein', 'keine', 'keinen', 'keinem',
      'keiner', 'keines', 'nicht', 'nie', 'ohne',
    ]),
    contradiction: Object.freeze([
      'conflicting', 'contradicted', 'contradictory', 'contradicts', 'inconsistent',
      'inkonsistent', 'inkonsistente', 'inkonsistenten', 'inkonsistenter',
      'inkonsistentes', 'widersprechend', 'widersprechen', 'widerspricht',
      'widersprüchlich', 'widersprüchliche', 'widersprüchlichen',
      'widersprüchlicher', 'widersprüchliches',
    ]),
    uncertainty: Object.freeze([
      'unresolved', 'unclear', 'uncertain', 'unknown', 'missing', 'cannot safely',
      'ungeklärt', 'unklar', 'offen', 'fehlt', 'nicht sicher',
    ]),
  }),
  whole_span_instruction_patterns: Object.freeze([
    '\\bignore\\s+(?:all\\s+)?(?:previous|prior)\\s+instructions?\\b',
    '\\b(?:set|choose|select|override|change|mark|grant)\\s+(?:the\\s+)?(?:finding|readiness|parser|policy|authority|branch|normalized value)\\b',
    "[\"'](?:finding|readiness|parser|policy|authority|process_branch|normalized_value)[\"']\\s*[:=]",
    '\\b(?:approve|deny|pay|close)\\s+(?:this\\s+|the\\s+)?claim\\b',
  ]),
});

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
  return JSON.stringify(value);
}

function sha(value) {
  const bytes = typeof value === 'string' || Buffer.isBuffer(value) ? value : canonical(value);
  return createHash('sha256').update(bytes).digest('hex');
}

const FROZEN_GRAMMAR_SHA256 = '8635c2bc36b7223579f3a8b4860c4bd582fd02dff8c3035565910d9c59715f00';
const GRAMMAR_SHA256 = sha(QUALIFICATION_GRAMMAR);
if (GRAMMAR_SHA256 !== FROZEN_GRAMMAR_SHA256) {
  throw new Error(`qualified witness grammar identity drifted: ${GRAMMAR_SHA256}`);
}

function parseBoundFile(raw, expectedSha256, label) {
  if (!(typeof raw === 'string' || Buffer.isBuffer(raw))) throw new Error(`${label} bytes are absent`);
  if (sha(raw) !== expectedSha256) throw new Error(`${label} file identity differs from the public manifest`);
  const text = Buffer.isBuffer(raw) ? raw.toString('utf8') : raw;
  try {
    const value = JSON.parse(text);
    if (text !== canonical(value)) throw new Error('bytes are not canonical JSON');
    return value;
  } catch (cause) {
    throw new Error(`${label} is not JSON: ${cause.message}`);
  }
}

function parseCanonicalFile(raw, label) {
  if (!(typeof raw === 'string' || Buffer.isBuffer(raw))) throw new Error(`${label} bytes are absent`);
  const text = Buffer.isBuffer(raw) ? raw.toString('utf8') : raw;
  try {
    const value = JSON.parse(text);
    if (text !== canonical(value)) throw new Error('bytes are not canonical JSON');
    return value;
  } catch (cause) {
    throw new Error(`${label} is not canonical JSON: ${cause.message}`);
  }
}

function boundaryPattern(term, global = false) {
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(?<![\\p{L}\\p{M}\\p{N}\\p{Pc}])${escaped}(?![\\p{L}\\p{M}\\p{N}\\p{Pc}])`, global ? 'giu' : 'iu');
}

function termPresent(text, term) {
  return boundaryPattern(term).test(text);
}

function classifySubject(subject) {
  const folded = subject.toLowerCase();
  const scores = Object.keys(INTAKE_TERMS).sort().map(claimType => {
    const matchedTerms = INTAKE_TERMS[claimType].filter(term => folded.includes(term));
    return {claim_type:claimType, matched_terms:matchedTerms, score:matchedTerms.length};
  });
  const maximum = Math.max(...scores.map(row => row.score));
  const winners = scores.filter(row => row.score === maximum);
  if (maximum < 1 || winners.length !== 1) return {claim_type:null, domain_scores:scores};
  return {claim_type:winners[0].claim_type, domain_scores:scores};
}

function pristine(row) {
  const operational = row?.operational_projection || {};
  return row?.workflow_state === 'received'
    && row?.readiness_state === 'not_assessed'
    && row?.revision === 1
    && row?.owner === null
    && operational.workspace_prefix?.revision === 1
    && operational.claim_loop_prefix === null
    && operational.next_state?.kind === 'start_processing';
}

const QUEUE_KEYS = Object.freeze([
  'claim_id', 'language', 'owner', 'readiness_state', 'revision', 'state_sha256',
  'subject', 'workflow_state', 'operational_projection',
].sort());
const OPERATIONAL_KEYS = Object.freeze([
  'claim_id', 'claim_loop_prefix', 'next_state', 'projection_sha256', 'workspace_prefix',
].sort());

function validateQueueProjection(row) {
  const operational = row?.operational_projection;
  if (
    !row
    || Object.keys(row).sort().join('|') !== QUEUE_KEYS.join('|')
    || !operational
    || Object.keys(operational).sort().join('|') !== OPERATIONAL_KEYS.join('|')
    || Object.keys(operational.workspace_prefix || {}).sort().join('|') !== 'revision|state_sha256'
    || Object.keys(operational.next_state || {}).sort().join('|') !== 'kind'
    || typeof row.claim_id !== 'string'
    || typeof row.subject !== 'string'
    || typeof row.language !== 'string'
    || !/^[0-9a-f]{64}$/.test(row.state_sha256 || '')
    || !/^[0-9a-f]{64}$/.test(operational.workspace_prefix?.state_sha256 || '')
    || !/^[0-9a-f]{64}$/.test(operational.projection_sha256 || '')
    || operational.claim_id !== row.claim_id
    || operational.workspace_prefix.revision !== row.revision
    || operational.workspace_prefix.state_sha256 !== row.state_sha256
  ) throw new Error('qualified witness queue projection contains non-allowlisted or invalid data');
  return row;
}

function sourceEntries(binding, claim, registry) {
  const message = claim?.customer_message;
  if (!message || message.message_id !== binding.message_id || message.subject !== binding.subject) {
    throw new Error(`${binding.claim_id}: observable message differs from its binding`);
  }
  const rawArtifacts = binding.observable_artifacts.filter(row => row.artifact_id === message.message_id);
  if (rawArtifacts.length !== 1 || typeof message.body !== 'string' || !message.body) {
    throw new Error(`${binding.claim_id}: observable message artifact is not unique`);
  }
  const projection = `${message.body}\n`;
  const projectionCodePoints = Array.from(projection);
  const projectionSha256 = sha(projection);
  const values = [];
  for (const registryEntry of registry.entries || []) {
    if (registryEntry?.source_kind !== 'observable_message_span' || registryEntry?.support_scope !== 'case_specific') continue;
    const locator = registryEntry.locator;
    const start = locator?.text_start;
    const end = locator?.text_end;
    const exactText = locator?.exact_text;
    if (
      locator?.locator_kind !== 'text_span'
      || locator?.page !== 1
      || locator?.artifact_sha256 !== projectionSha256
      || registryEntry.parent_artifact_id !== message.message_id
      || registryEntry.parent_artifact_sha256 !== rawArtifacts[0].sha256
      || registryEntry.representation_identity !== 'observable-claim-body+utf8-final-newline/1.0.0'
      || !Number.isSafeInteger(start)
      || !Number.isSafeInteger(end)
      || start < 0
      || end <= start
      || end > projectionCodePoints.length
      || typeof exactText !== 'string'
      || Array.from(exactText).length !== end - start
      || projectionCodePoints.slice(start, end).join('') !== exactText
    ) throw new Error(`${binding.claim_id}: public source span differs from its registry`);
    const material = {
      contract: 'casepath.workspace-admissible-source-span/1.0.0',
      source_kind: 'observable_message_span',
      support_scope: 'case_specific',
      artifact_id: locator.artifact_id,
      artifact_sha256: locator.artifact_sha256,
      parent_artifact_id: registryEntry.parent_artifact_id,
      parent_artifact_sha256: registryEntry.parent_artifact_sha256,
      representation_identity: registryEntry.representation_identity,
      source_version: locator.source_version,
      locator_kind: 'text_span',
      page: 1,
      text_start: start,
      text_end: end,
      byte_start: Buffer.byteLength(projectionCodePoints.slice(0, start).join('')),
      byte_end: Buffer.byteLength(projectionCodePoints.slice(0, end).join('')),
      exact_text: exactText,
      span_sha256: sha(exactText),
    };
    values.push({...material, source_entry_sha256:sha(material)});
  }
  if (!values.length || new Set(values.map(row => row.source_entry_sha256)).size !== values.length) {
    throw new Error(`${binding.claim_id}: public source roster is not closed`);
  }
  return values;
}

const HEALTH_POSITIVE_TERMS = Object.freeze([
  'cough', 'coughing', 'hustet', 'husten', 'rash', 'ausschlag', 'pharmacy',
  'apotheke', 'breathing', 'atem',
]);

function predictInitialAdapterSourceEntry(domain, entries) {
  if (!Array.isArray(entries) || !entries.length) throw new Error('adapter source roster is empty');
  const ordered = [...entries].sort((left, right) => left.text_start - right.text_start
    || left.source_entry_sha256.localeCompare(right.source_entry_sha256));
  if (domain === 'defect_mold_heating') {
    const positive = ordered.filter(entry => HEALTH_POSITIVE_TERMS.some(term => entry.exact_text.toLowerCase().includes(term)));
    return (positive.length ? positive : ordered)[0];
  }
  const domainTerms = QUALIFICATION_GRAMMAR.transition_terms[domain] || [];
  const decisive = ordered.filter(entry => {
    const tokens = entry.exact_text.match(/[\p{L}\p{M}\p{N}\p{Pc}]+/gu)?.length || 0;
    return tokens >= 5 && domainTerms.some(term => termPresent(entry.exact_text, term));
  });
  return (decisive.length ? decisive : ordered)[0];
}

function transitionMatches(text) {
  const raw = [];
  for (const [domain, terms] of Object.entries(QUALIFICATION_GRAMMAR.transition_terms)) {
    for (const term of terms) {
      for (const match of text.matchAll(boundaryPattern(term, true))) {
        const start = Array.from(text.slice(0, match.index)).length;
        raw.push({domain, term, start, end:start + Array.from(match[0]).length});
      }
    }
  }
  raw.sort((left, right) => left.start - right.start || (right.end - right.start) - (left.end - left.start) || left.term.localeCompare(right.term));
  const nonOverlapping = [];
  for (const value of raw) {
    if (!nonOverlapping.some(other => value.start < other.end && value.end > other.start)) nonOverlapping.push(value);
  }
  return nonOverlapping;
}

function transitionClause(text, match) {
  const codePoints = Array.from(text);
  const delimiters = new Set(QUALIFICATION_GRAMMAR.clause_delimiters);
  let start = 0;
  let end = codePoints.length;
  for (let index = match.start - 1; index >= 0; index -= 1) {
    if (delimiters.has(codePoints[index])) { start = index + 1; break; }
  }
  for (let index = match.end; index < codePoints.length; index += 1) {
    if (delimiters.has(codePoints[index])) { end = index; break; }
  }
  return codePoints.slice(start, end).join('').trim();
}

function forbiddenMarkers(clause) {
  return Object.fromEntries(Object.entries(QUALIFICATION_GRAMMAR.forbidden_transition_clause_markers).map(([kind, terms]) => [
    kind,
    terms.filter(marker => termPresent(clause, marker)),
  ]));
}

function instructionPatterns(text) {
  return QUALIFICATION_GRAMMAR.whole_span_instruction_patterns.filter(pattern => new RegExp(pattern, 'iu').test(text));
}

function grammarAssessment(domain, entry) {
  const text = entry.exact_text;
  const matches = transitionMatches(text);
  const match = matches.length === 1 ? matches[0] : null;
  const clause = match ? transitionClause(text, match) : '';
  const markers = match ? forbiddenMarkers(clause) : [];
  const instructionMatches = instructionPatterns(text);
  const markerCount = markers && !Array.isArray(markers)
    ? Object.values(markers).reduce((total, values) => total + values.length, 0)
    : 0;
  const tokenCount = text.match(/[\p{L}\p{M}\p{N}\p{Pc}]+/gu)?.length || 0;
  const terminal = QUALIFICATION_GRAMMAR.terminal_punctuation.includes(text.trim().slice(-1));
  return {
    eligible: Boolean(
      match
      && match.domain === domain
      && text.normalize('NFC') === text
      && tokenCount >= QUALIFICATION_GRAMMAR.token_count.minimum
      && tokenCount <= QUALIFICATION_GRAMMAR.token_count.maximum
      && terminal
      && markerCount === 0
      && instructionMatches.length === 0
    ),
    unicode_nfc: text.normalize('NFC') === text,
    token_count: tokenCount,
    terminal_punctuation: terminal,
    transition_matches: matches,
    transition_clause: clause,
    forbidden_transition_clause_markers: markers,
    whole_span_instruction_matches: instructionMatches,
  };
}

function mapValue(values, claimId, label) {
  const value = values instanceof Map ? values.get(claimId) : values?.[claimId];
  if (value === undefined) throw new Error(`${claimId}: ${label} bytes are absent`);
  return value;
}

export function selectQualifiedGate1Witness({
  queueRows,
  corpusManifestFile,
  claimFilesById,
  registryFilesById,
  staticPolicyFile,
}) {
  if (!Array.isArray(queueRows)) {
    throw new Error('qualified witness selector inputs are incomplete');
  }
  const corpusManifest = parseCanonicalFile(corpusManifestFile, 'public corpus manifest');
  if (!Array.isArray(corpusManifest.claims)) throw new Error('public corpus claim roster is invalid');
  const manifestMaterial = {...corpusManifest};
  delete manifestMaterial.manifest_sha256;
  if (
    corpusManifest.contract !== 'casepath.public-observable-corpus/1.0.0'
    || corpusManifest.contains_expected_outputs !== false
    || corpusManifest.contains_sealed_targets !== false
    || corpusManifest.manifest_sha256 !== sha(manifestMaterial)
  ) throw new Error('public corpus manifest identity is invalid');
  const policyIdentity = corpusManifest.static_template?.files?.find(row => row.path === 'policy/static-rule-templates-v3.json');
  const staticPolicy = parseBoundFile(staticPolicyFile, policyIdentity?.sha256, 'static playbook');
  const templateByDomain = new Map((staticPolicy.templates || []).map(row => [row.domain, row]));
  if (templateByDomain.size !== 3 || staticPolicy.contract !== 'casepath.static-rule-templates/3.0.0') {
    throw new Error('static playbook roster is invalid');
  }
  const catalogMaterial = Object.keys(INTAKE_TERMS).sort().map(claimType => ({claim_type:claimType, terms:[...INTAKE_TERMS[claimType]].sort()}));
  if (sha(catalogMaterial) !== INTAKE_CATALOG_SHA256) throw new Error('intake catalog identity drifted');
  const bindings = [...corpusManifest.claims].sort((left, right) => left.claim_id.localeCompare(right.claim_id));
  queueRows.forEach(validateQueueProjection);
  const bindingIds = bindings.map(row => row.claim_id);
  const queueIds = queueRows.map(row => row.claim_id).sort();
  if (
    new Set(bindingIds).size !== bindings.length
    || new Set(queueIds).size !== queueRows.length
    || canonical(queueIds) !== canonical(bindingIds)
  ) throw new Error('pristine queue and public corpus rosters differ');
  const pristineRows = queueRows.filter(pristine).sort((left, right) => left.claim_id.localeCompare(right.claim_id));
  if (pristineRows.length !== bindings.length) throw new Error('qualified witness selection requires the complete pristine queue');

  const eligible = [];
  for (const binding of bindings) {
    const bindingMaterial = {...binding};
    delete bindingMaterial.binding_sha256;
    if (
      binding.binding_sha256 !== sha(bindingMaterial)
      || binding.static_template_sha256 !== corpusManifest.static_template.template_sha256
    ) throw new Error(`${binding.claim_id}: public binding identity is invalid`);
    const claim = parseBoundFile(mapValue(claimFilesById, binding.claim_id, 'claim'), binding.claim.sha256, `${binding.claim_id} claim`);
    const registry = parseBoundFile(mapValue(registryFilesById, binding.claim_id, 'registry'), binding.source_registry.sha256, `${binding.claim_id} registry`);
    const registryMaterial = {...registry};
    delete registryMaterial.registry_sha256;
    if (
      claim.contract?.contains_post_intake_information !== false
      || registry.registry_sha256 !== sha(registryMaterial)
      || registry.case_id !== binding.claim_id
      || registry.contains_case_activation_values !== false
      || registry.contains_selected_paths !== false
    ) {
      throw new Error(`${binding.claim_id}: public registry identity is invalid`);
    }
    const queueRow = pristineRows.find(row => row.claim_id === binding.claim_id);
    if (queueRow.subject !== binding.subject
      || queueRow.subject !== claim.customer_message?.subject
      || queueRow.language !== binding.language) {
      throw new Error(`${binding.claim_id}: queue identity differs from the public claim binding`);
    }
    const classification = classifySubject(claim.customer_message?.subject || '');
    if (!QUALIFICATION_GRAMMAR.eligible_domains.includes(classification.claim_type)) continue;
    const template = templateByDomain.get(classification.claim_type);
    const firstNode = template?.process_catalog?.nodes?.[0];
    const outgoing = (template?.process_catalog?.transitions || []).filter(row => row.source_node_id === firstNode?.node_id);
    const staticExpectation = classification.claim_type === 'lease_termination_dispute'
      ? {node_id:'lt_intake', template_sha256:'db7ea6f9b7adc927d26d66963f142483f3ff2d4ed76c5b4c057f4000d8e7902a', edge_id:'lt_e01', condition:'termination received', target_node_id:'lt_deadline'}
      : {node_id:'ri_intake', template_sha256:'4351ae9a95af7ae129c3080c0904019fa7a0b3043bc79b1a6aa244a29cd01d75', edge_id:'ri_e01', condition:'claim received', target_node_id:'ri_deadline'};
    if (
      firstNode?.responsibility !== QUALIFICATION_GRAMMAR.required_intake_owner
      || firstNode?.terminal !== false
      || !firstNode.node_id.endsWith('_intake')
      || outgoing.length !== QUALIFICATION_GRAMMAR.required_outgoing_transition_count
      || firstNode.node_id !== staticExpectation.node_id
      || sha(template) !== staticExpectation.template_sha256
      || outgoing[0].edge_id !== staticExpectation.edge_id
      || outgoing[0].condition !== staticExpectation.condition
      || outgoing[0].target_node_id !== staticExpectation.target_node_id
    ) continue;
    const entries = sourceEntries(binding, claim, registry);
    const candidate = predictInitialAdapterSourceEntry(classification.claim_type, entries);
    const grammar = grammarAssessment(classification.claim_type, candidate);
    if (!grammar.eligible) continue;
    const actionMaterial = {
      contract:'casepath.evidence-action/1.0.0',
      action_kind:'acquire',
      process_node_id:`workspace_evidence_gap.${firstNode.node_id}`,
      evidence_item_id:`workspace_evidence.${firstNode.node_id}`,
      fact_id:`fact.workspace.${firstNode.node_id}.transition`,
      title:firstNode.label,
      bounded_tool_id:'loopback-source-byte-acquisition-v1',
    };
    const predictedAction = {
      ...actionMaterial,
      action_id:`action.${sha(actionMaterial)}`,
      action_sha256:sha(actionMaterial),
    };
    const material = {
      claim_id: binding.claim_id,
      binding_sha256: binding.binding_sha256,
      claim_file_sha256: binding.claim.sha256,
      source_registry_sha256: binding.source_registry.sha256,
      intake_compiler_id: INTAKE_COMPILER_ID,
      intake_catalog_sha256: INTAKE_CATALOG_SHA256,
      domain: classification.claim_type,
      domain_scores: classification.domain_scores,
      static_template_id: template.template_id,
      intake_node: firstNode,
      sole_outgoing_transition: outgoing[0],
      predicted_initial_action: predictedAction,
      adapter_candidate: candidate,
      grammar_assessment: grammar,
    };
    eligible.push({...material, qualification_sha256:sha(material)});
  }
  eligible.sort((left, right) => left.claim_id.localeCompare(right.claim_id));
  if (!eligible.length) throw new Error('no qualified Gate 1 witness exists');
  const pristineClaimIds = pristineRows.map(row => row.claim_id);
  const eligibleClaimIds = eligible.map(row => row.claim_id);
  const material = {
    contract: 'casepath.gate1-qualified-witness-selection/1.0.0',
    selector_id: SELECTOR_ID,
    selection_rule: 'lexicographically-first-qualified-claim-id',
    grammar: QUALIFICATION_GRAMMAR,
    grammar_sha256: GRAMMAR_SHA256,
    corpus_manifest_file_sha256: sha(corpusManifestFile),
    corpus_manifest_sha256: corpusManifest.manifest_sha256,
    static_policy_file_sha256: sha(staticPolicyFile),
    static_template_sha256: corpusManifest.static_template.template_sha256,
    pristine_claim_ids: pristineClaimIds,
    pristine_roster_sha256: sha(pristineClaimIds),
    eligible_claims: eligible,
    eligible_claim_ids: eligibleClaimIds,
    eligible_roster_sha256: sha(eligibleClaimIds),
    selected_claim_id: eligible[0].claim_id,
    selected_qualification_sha256: eligible[0].qualification_sha256,
    selected_source_entry_sha256: eligible[0].adapter_candidate.source_entry_sha256,
  };
  return {...material, selection_sha256:sha(material)};
}

export {
  GRAMMAR_SHA256,
  INTAKE_CATALOG_SHA256,
  INTAKE_TERMS,
  QUALIFICATION_GRAMMAR,
  SELECTOR_ID,
  canonical,
  grammarAssessment as qualifyTransitionProposition,
  predictInitialAdapterSourceEntry,
  sourceEntries as reconstructAdmissibleSourceEntries,
  sha,
};
