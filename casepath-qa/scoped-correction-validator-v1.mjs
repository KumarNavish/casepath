export const SCOPED_CORRECTION_PREDICATE_CONTRACT =
  'casepath.scoped-correction-locality-predicates/1.0.0';

export const SCOPED_CORRECTION_DERIVED_CHECKLIST_FIELDS = Object.freeze([
  'applies_when',
  'current_path',
  'required_level',
]);

export const SCOPED_CORRECTION_PREDICATES = Object.freeze([
  { legacy_operand_index:1, name:'target_fact_changed' },
  { legacy_operand_index:2, name:'target_evidence_changed' },
  { legacy_operand_index:3, name:'unrelated_fact_digest_unchanged' },
  { legacy_operand_index:4, name:'non_target_facts_unchanged' },
  {
    legacy_operand_index:5,
    name:'non_target_checklist_content_unchanged_and_applicability_rederived',
  },
  { legacy_operand_index:6, name:'prior_fact_hash_matches_delta' },
  { legacy_operand_index:7, name:'prior_evidence_hash_matches_delta' },
  { legacy_operand_index:8, name:'corrected_fact_hash_matches_delta' },
  { legacy_operand_index:9, name:'corrected_evidence_hash_matches_delta' },
  { legacy_operand_index:10, name:'corrected_fact_is_unknown' },
  { legacy_operand_index:11, name:'corrected_evidence_is_insufficient' },
  { legacy_operand_index:12, name:'before_semantics_match_candidate' },
  { legacy_operand_index:13, name:'after_semantics_match_authoritative_state' },
  { legacy_operand_index:14, name:'effect_matches_candidate' },
  { legacy_operand_index:15, name:'cycle_kind_is_correction' },
]);

const observed = value => value === undefined ? null : value;
const derivedFieldSet = new Set(SCOPED_CORRECTION_DERIVED_CHECKLIST_FIELDS);
const isObject = value => Boolean(value && typeof value === 'object' && !Array.isArray(value));

function canonicalEqual(left, right, canonical) {
  try {
    return canonical(left) === canonical(right);
  } catch {
    return false;
  }
}

function hashMatches(value, expected, claimLoopSha) {
  if (!value || typeof value !== 'object' || typeof expected !== 'string') return false;
  try {
    return claimLoopSha(value) === expected;
  } catch {
    return false;
  }
}

function itemIdRoster(items) {
  if (!Array.isArray(items)) return { valid:false, ids:[], duplicates:[] };
  const ids = items.map(item => item?.item_id);
  const counts = new Map();
  for (const id of ids) counts.set(id, (counts.get(id) || 0) + 1);
  const duplicates = [...counts.entries()]
    .filter(([, count]) => count !== 1)
    .map(([id]) => observed(id));
  return {
    valid:ids.every(id => typeof id === 'string' && id.length > 0)
      && duplicates.length === 0,
    ids,
    duplicates,
  };
}

function processProjection(process, canonical) {
  const errors = [];
  const nodes = process?.nodes;
  if (!Array.isArray(nodes)) {
    return { valid:false, errors:['nodes_missing'], owners:new Map(), active:new Set() };
  }
  const nodeIds = nodes.map(node => node?.node_id);
  const nodeSet = new Set(nodeIds);
  if (nodeIds.some(id => typeof id !== 'string' || id.length === 0)) {
    errors.push('node_id_invalid');
  }
  if (nodeSet.size !== nodeIds.length) errors.push('node_id_duplicate');

  const owners = new Map();
  for (const node of nodes) {
    if (!Array.isArray(node?.evidence_requirement_ids)) {
      errors.push(`evidence_requirement_ids_invalid:${observed(node?.node_id)}`);
      continue;
    }
    for (const itemId of node.evidence_requirement_ids) {
      if (typeof itemId !== 'string' || itemId.length === 0) {
        errors.push(`evidence_item_id_invalid:${observed(node?.node_id)}`);
        continue;
      }
      const current = owners.get(itemId) || [];
      current.push(node.node_id);
      owners.set(itemId, current);
    }
  }

  const selectedPath = process?.selected_path;
  if (!Array.isArray(selectedPath)
    || selectedPath.some(id => typeof id !== 'string' || !nodeSet.has(id))) {
    errors.push('selected_path_invalid');
  } else if (new Set(selectedPath).size !== selectedPath.length) {
    errors.push('selected_path_duplicate');
  }
  const currentNode = process?.current_node;
  const overlayCurrentNode = process?.current_overlay?.current_node_id;
  const nextActionNode = process?.current_overlay?.next_action_node_id;
  if (typeof currentNode !== 'string'
    || currentNode !== overlayCurrentNode
    || !Array.isArray(selectedPath)
    || !selectedPath.includes(currentNode)) {
    errors.push('current_node_binding_invalid');
  }
  if (typeof nextActionNode !== 'string' || !nodeSet.has(nextActionNode)) {
    errors.push('next_action_node_invalid');
  }

  const active = new Set(Array.isArray(selectedPath) ? selectedPath : []);
  if (typeof nextActionNode === 'string') active.add(nextActionNode);
  const ownerRoster = [...owners.entries()].map(([itemId, ids]) => ({ item_id:itemId, node_ids:ids }));
  ownerRoster.sort((left, right) => left.item_id.localeCompare(right.item_id));
  return {
    valid:errors.length === 0,
    errors,
    owners,
    owner_roster:ownerRoster,
    owner_roster_canonical:canonical(ownerRoster),
    active,
  };
}

function expectedApplicability(itemId, projection) {
  const owners = projection.owners.get(itemId) || [];
  if (!projection.valid || owners.length === 0) return null;
  const currentPath = owners.some(nodeId => projection.active.has(nodeId));
  return {
    node_id:owners[0],
    node_ids:owners,
    applies_when:currentPath
      ? 'always'
      : `One of the linked process nodes is reached: ${owners.join(', ')}`,
    current_path:currentPath,
    required_level:currentPath ? 'mandatory' : 'conditional',
  };
}

function actualApplicability(item) {
  if (!item || typeof item !== 'object') return null;
  return {
    node_id:item.node_id,
    node_ids:item.node_ids,
    applies_when:item.applies_when,
    current_path:item.current_path,
    required_level:item.required_level,
  };
}

function stableChecklistContent(item) {
  if (!item || typeof item !== 'object') return null;
  return Object.fromEntries(
    Object.entries(item).filter(([key]) => !derivedFieldSet.has(key)),
  );
}

function changedFields(before, after, canonical) {
  const keys = new Set([
    ...Object.keys(before || {}),
    ...Object.keys(after || {}),
  ]);
  return [...keys]
    .filter(key => !canonicalEqual(before?.[key], after?.[key], canonical))
    .sort();
}

function evaluateChecklistLocality({
  beforeItems,
  afterItems,
  targetItemId,
  beforeProcess,
  afterProcess,
  canonical,
}) {
  const beforeRoster = itemIdRoster(beforeItems);
  const afterRoster = itemIdRoster(afterItems);
  const rosterMatches = beforeRoster.valid
    && afterRoster.valid
    && canonicalEqual([...beforeRoster.ids].sort(), [...afterRoster.ids].sort(), canonical)
    && beforeRoster.ids.includes(targetItemId);
  const beforeProjection = processProjection(beforeProcess, canonical);
  const afterProjection = processProjection(afterProcess, canonical);
  const ownershipUnchanged = beforeProjection.valid
    && afterProjection.valid
    && beforeProjection.owner_roster_canonical === afterProjection.owner_roster_canonical;
  const beforeById = new Map((Array.isArray(beforeItems) ? beforeItems : [])
    .map(item => [item?.item_id, item]));
  const afterById = new Map((Array.isArray(afterItems) ? afterItems : [])
    .map(item => [item?.item_id, item]));
  const ids = rosterMatches ? [...beforeRoster.ids].sort() : [];
  const contentMutations = [];
  const beforeApplicabilityMismatches = [];
  const afterApplicabilityMismatches = [];
  const outsideConeMutations = [];
  const affectedItemIds = [];
  const changedItemFields = [];

  for (const itemId of ids) {
    const before = beforeById.get(itemId);
    const after = afterById.get(itemId);
    const beforeExpected = expectedApplicability(itemId, beforeProjection);
    const afterExpected = expectedApplicability(itemId, afterProjection);
    const beforeActual = actualApplicability(before);
    const afterActual = actualApplicability(after);
    const expectedChanged = !canonicalEqual(beforeExpected, afterExpected, canonical);
    const actualChanged = !canonicalEqual(beforeActual, afterActual, canonical);
    const fields = changedFields(before, after, canonical);
    if (fields.length > 0) changedItemFields.push({ item_id:itemId, changed_fields:fields });
    if (expectedChanged) affectedItemIds.push(itemId);
    if (!canonicalEqual(beforeExpected, beforeActual, canonical)) {
      beforeApplicabilityMismatches.push({
        item_id:itemId,
        expected:beforeExpected,
        actual:beforeActual,
      });
    }
    if (!canonicalEqual(afterExpected, afterActual, canonical)) {
      afterApplicabilityMismatches.push({
        item_id:itemId,
        expected:afterExpected,
        actual:afterActual,
      });
    }
    if (itemId !== targetItemId
      && !canonicalEqual(stableChecklistContent(before), stableChecklistContent(after), canonical)) {
      contentMutations.push({ item_id:itemId, changed_fields:fields });
    }
    if (itemId !== targetItemId && actualChanged && !expectedChanged) {
      outsideConeMutations.push({ item_id:itemId, changed_fields:fields });
    }
  }

  const passed = rosterMatches
    && ownershipUnchanged
    && contentMutations.length === 0
    && beforeApplicabilityMismatches.length === 0
    && afterApplicabilityMismatches.length === 0
    && outsideConeMutations.length === 0;
  return {
    passed,
    roster_matches:rosterMatches,
    before_roster_valid:beforeRoster.valid,
    after_roster_valid:afterRoster.valid,
    before_roster_duplicates:beforeRoster.duplicates,
    after_roster_duplicates:afterRoster.duplicates,
    process_evidence_ownership_unchanged:ownershipUnchanged,
    before_process_errors:beforeProjection.errors,
    after_process_errors:afterProjection.errors,
    affected_item_ids:affectedItemIds,
    changed_item_fields:changedItemFields,
    non_target_content_mutations:contentMutations,
    before_applicability_mismatches:beforeApplicabilityMismatches,
    after_applicability_mismatches:afterApplicabilityMismatches,
    outside_cone_mutations:outsideConeMutations,
  };
}

export function evaluateScopedCorrectionPredicates({
  observedState,
  correctedState,
  candidate,
  delta,
  priorFact,
  priorEvidence,
  correctedFact,
  correctedEvidence,
  actualAfterSemantics,
  claimLoopSha,
  canonical,
}) {
  if (typeof claimLoopSha !== 'function' || typeof canonical !== 'function') {
    throw new TypeError('scoped correction validation requires hash and canonical functions');
  }

  const checklistLocality = evaluateChecklistLocality({
    beforeItems:observedState?.checklist?.items,
    afterItems:correctedState?.checklist?.items,
    targetItemId:delta?.evidence_item_id,
    beforeProcess:observedState?.process,
    afterProcess:correctedState?.process,
    canonical,
  });
  const nonTargetFactsBefore = Array.isArray(observedState?.facts)
    ? observedState.facts.filter(row => row?.fact_id !== delta?.fact_id)
    : null;
  const nonTargetFactsAfter = Array.isArray(correctedState?.facts)
    ? correctedState.facts.filter(row => row?.fact_id !== delta?.fact_id)
    : null;

  const definitions = [
    {
      legacy_operand_index:1,
      name:'target_fact_changed',
      passed:typeof delta?.before_fact_sha256 === 'string'
        && typeof delta?.after_fact_sha256 === 'string'
        && delta.before_fact_sha256 !== delta.after_fact_sha256,
      observed:{
        before_fact_sha256:observed(delta?.before_fact_sha256),
        after_fact_sha256:observed(delta?.after_fact_sha256),
      },
    },
    {
      legacy_operand_index:2,
      name:'target_evidence_changed',
      passed:typeof delta?.before_evidence_sha256 === 'string'
        && typeof delta?.after_evidence_sha256 === 'string'
        && delta.before_evidence_sha256 !== delta.after_evidence_sha256,
      observed:{
        before_evidence_sha256:observed(delta?.before_evidence_sha256),
        after_evidence_sha256:observed(delta?.after_evidence_sha256),
      },
    },
    {
      legacy_operand_index:3,
      name:'unrelated_fact_digest_unchanged',
      passed:typeof delta?.unrelated_facts_before_sha256 === 'string'
        && delta.unrelated_facts_before_sha256 === delta?.unrelated_facts_after_sha256,
      observed:{
        before_sha256:observed(delta?.unrelated_facts_before_sha256),
        after_sha256:observed(delta?.unrelated_facts_after_sha256),
      },
    },
    {
      legacy_operand_index:4,
      name:'non_target_facts_unchanged',
      passed:Array.isArray(nonTargetFactsBefore)
        && Array.isArray(nonTargetFactsAfter)
        && canonicalEqual(nonTargetFactsBefore, nonTargetFactsAfter, canonical),
      observed:{
        before_count:Array.isArray(nonTargetFactsBefore) ? nonTargetFactsBefore.length : null,
        after_count:Array.isArray(nonTargetFactsAfter) ? nonTargetFactsAfter.length : null,
      },
    },
    {
      legacy_operand_index:5,
      name:'non_target_checklist_content_unchanged_and_applicability_rederived',
      passed:checklistLocality.passed,
      observed:checklistLocality,
    },
    {
      legacy_operand_index:6,
      name:'prior_fact_hash_matches_delta',
      passed:hashMatches(priorFact, delta?.before_fact_sha256, claimLoopSha),
      observed:{ expected_sha256:observed(delta?.before_fact_sha256) },
    },
    {
      legacy_operand_index:7,
      name:'prior_evidence_hash_matches_delta',
      passed:hashMatches(priorEvidence, delta?.before_evidence_sha256, claimLoopSha),
      observed:{ expected_sha256:observed(delta?.before_evidence_sha256) },
    },
    {
      legacy_operand_index:8,
      name:'corrected_fact_hash_matches_delta',
      passed:hashMatches(correctedFact, delta?.after_fact_sha256, claimLoopSha),
      observed:{ expected_sha256:observed(delta?.after_fact_sha256) },
    },
    {
      legacy_operand_index:9,
      name:'corrected_evidence_hash_matches_delta',
      passed:hashMatches(correctedEvidence, delta?.after_evidence_sha256, claimLoopSha),
      observed:{ expected_sha256:observed(delta?.after_evidence_sha256) },
    },
    {
      legacy_operand_index:10,
      name:'corrected_fact_is_unknown',
      passed:correctedFact?.state === 'unknown',
      observed:{ state:observed(correctedFact?.state) },
    },
    {
      legacy_operand_index:11,
      name:'corrected_evidence_is_insufficient',
      passed:correctedEvidence?.status === 'provided_insufficient',
      observed:{ status:observed(correctedEvidence?.status) },
    },
    {
      legacy_operand_index:12,
      name:'before_semantics_match_candidate',
      passed:isObject(delta?.before_semantics)
        && isObject(candidate?.current_semantics)
        && canonicalEqual(delta.before_semantics, candidate.current_semantics, canonical),
      observed:{ matches:canonicalEqual(delta?.before_semantics, candidate?.current_semantics, canonical) },
    },
    {
      legacy_operand_index:13,
      name:'after_semantics_match_authoritative_state',
      passed:isObject(delta?.after_semantics)
        && isObject(actualAfterSemantics)
        && canonicalEqual(delta.after_semantics, actualAfterSemantics, canonical),
      observed:{ matches:canonicalEqual(delta?.after_semantics, actualAfterSemantics, canonical) },
    },
    {
      legacy_operand_index:14,
      name:'effect_matches_candidate',
      passed:isObject(delta?.effect)
        && isObject(candidate?.proposed_semantics)
        && canonicalEqual(delta.effect, candidate.proposed_semantics, canonical),
      observed:{ matches:canonicalEqual(delta?.effect, candidate?.proposed_semantics, canonical) },
    },
    {
      legacy_operand_index:15,
      name:'cycle_kind_is_correction',
      passed:correctedState?.six_agent_cycle_receipt?.cycle_kind === 'correction',
      observed:{
        cycle_kind:observed(correctedState?.six_agent_cycle_receipt?.cycle_kind),
      },
    },
  ].map(value => ({ ...value, passed:Boolean(value.passed) }));

  const declared = SCOPED_CORRECTION_PREDICATES.map(
    ({legacy_operand_index, name}) => `${legacy_operand_index}:${name}`,
  );
  const actual = definitions.map(
    ({legacy_operand_index, name}) => `${legacy_operand_index}:${name}`,
  );
  if (!canonicalEqual(declared, actual, canonical)) {
    throw new Error('scoped correction predicate roster drifted');
  }

  const failedPredicates = definitions
    .filter(value => !value.passed)
    .map(({legacy_operand_index, name}) => ({ legacy_operand_index, name }));
  return {
    contract:SCOPED_CORRECTION_PREDICATE_CONTRACT,
    status:failedPredicates.length === 0 ? 'PASS' : 'FAIL',
    passed:failedPredicates.length === 0,
    predicate_count:definitions.length,
    failed_predicates:failedPredicates,
    affected_checklist_item_ids:checklistLocality.affected_item_ids,
    predicates:definitions,
  };
}
