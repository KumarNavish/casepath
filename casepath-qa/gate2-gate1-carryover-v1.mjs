import { createHash } from 'node:crypto';

export const NEGATIVE_CARRYOVER_CLAIM_ID = 'clm_a62c178195d21648';
export const MAIN_CARRYOVER_CLAIM_ID = 'clm_0c1a91bc008f8747';
export const ORDERED_CARRYOVER_CLAIM_IDS = Object.freeze([
  NEGATIVE_CARRYOVER_CLAIM_ID,
  MAIN_CARRYOVER_CLAIM_ID,
]);
export const SAFE_REJECTION_COPY =
  'Evidence was safely rejected; no observation was added. CasePath kept the bounded action open.';

const canonical = value => {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
};
const exact = (left, right) => canonical(left) === canonical(right);
const sha = value => createHash('sha256').update(canonical(value)).digest('hex');
const without = (value, key) => Object.fromEntries(Object.entries(value).filter(([name]) => name !== key));
const selfHashed = (value, field = 'receipt_sha256') => Boolean(value)
  && /^[0-9a-f]{64}$/.test(value[field] || '')
  && value[field] === sha(without(value, field));
const exactSha = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);

function requireValue(condition, message) {
  if (!condition) throw new Error(`Gate 2 carryover compatibility failed: ${message}`);
}

function finiteWithin(value, maximum) {
  return Number.isFinite(value) && value >= 0 && value <= maximum;
}

export function validateGate2Gate1Carryovers({ claimIds, gate1Report, negativeControl, qualifiedSelection }) {
  requireValue(Array.isArray(claimIds) && claimIds.length === 150, 'claim roster is not exactly 150 rows');
  requireValue(new Set(claimIds).size === 150, 'claim roster contains duplicates');
  requireValue(ORDERED_CARRYOVER_CLAIM_IDS.every(claimId => claimIds.includes(claimId)),
    'one or both authorized carryovers are absent');
  requireValue(gate1Report?.mutated_claim_count === 2, 'Gate 1 mutation count is not two');
  requireValue(exact(gate1Report?.mutated_claim_ids, ORDERED_CARRYOVER_CLAIM_IDS),
    'Gate 1 mutation roster is not the exact ordered two-claim carryover');

  const carryovers = gate1Report?.gate2_carryovers;
  requireValue(carryovers?.contract === 'casepath.gate1-gate2-carryovers/1.0.0',
    'carryover contract differs');
  requireValue(exact(carryovers.ordered_claim_ids, ORDERED_CARRYOVER_CLAIM_IDS),
    'carryover receipt has a different ordered claim roster');
  requireValue(Array.isArray(carryovers.rows) && carryovers.rows.length === 2,
    'carryover receipt does not contain exactly two typed rows');
  requireValue(selfHashed(carryovers), 'carryover receipt is not canonical and self-hashed');
  requireValue(carryovers.aggregate_claim_count === 150 && carryovers.fresh_gate2_claim_count === 148,
    'aggregate/fresh claim accounting differs');
  requireValue(exact(carryovers.expected_outcomes, { next_action:149, decision_ready:0, abstain:1 }),
    'outcome accounting differs');
  requireValue(exact(carryovers.expected_gate2_journal_delta, { total:740, claim_loop:592, workspace:148 }),
    'journal accounting differs');
  requireValue(exact(carryovers.expected_gate2_sidecar_delta, { total:296, acquisition:148, tool_artifact:148 }),
    'sidecar accounting differs');
  requireValue(carryovers.expected_gate2_admitted_authority_per_kind === 148,
    'admitted-authority accounting differs');

  const [negativeRow, mainRow] = carryovers.rows;
  requireValue(negativeRow?.role === 'safe_rejection_zero_effect'
    && negativeRow.claim_id === NEGATIVE_CARRYOVER_CLAIM_ID
    && negativeRow.final_outcome === 'next_action'
    && negativeRow.typed_safe_rejection === true
    && negativeRow.authoritative_semantic_effect === false
    && negativeRow.observation_count === 0
    && Number.isInteger(negativeRow.loop_revision) && negativeRow.loop_revision >= 1
    && negativeRow.typed_abstention !== true
    && exactSha(negativeRow.loop_state_sha256)
    && exactSha(negativeRow.workspace_state_sha256)
    && exactSha(negativeRow.selected_action_sha256)
    && exactSha(negativeRow.queue_row_sha256)
    && exactSha(negativeRow.negative_control_receipt_sha256),
  'negative carryover row is not an exact zero-effect safe rejection');
  requireValue(mainRow?.role === 'qualified_typed_abstention'
    && mainRow.claim_id === MAIN_CARRYOVER_CLAIM_ID
    && mainRow.final_outcome === 'abstain'
    && mainRow.typed_abstention === true
    && mainRow.selected_action_sha256 === null
    && Number.isInteger(mainRow.loop_revision) && mainRow.loop_revision >= 1
    && Number.isInteger(mainRow.observation_count) && mainRow.observation_count >= 1
    && mainRow.typed_safe_rejection !== true
    && exactSha(mainRow.loop_state_sha256)
    && exactSha(mainRow.workspace_state_sha256)
    && exactSha(mainRow.queue_row_sha256)
    && exactSha(mainRow.qualified_witness_selection_receipt_sha256),
  'main carryover row is not a typed abstention');

  requireValue(negativeControl?.contract === 'casepath.gate1-safe-rejection-negative-control/1.0.0'
    && negativeControl.control_claim_id === NEGATIVE_CARRYOVER_CLAIM_ID
    && negativeControl.expected_semantic_effect === false
    && negativeControl.exact_ui_copy === SAFE_REJECTION_COPY,
  'negative-control envelope differs');
  requireValue(selfHashed(negativeControl), 'negative-control envelope is not self-hashed');
  requireValue(negativeRow.negative_control_receipt_sha256 === negativeControl.receipt_sha256,
    'negative carryover does not bind the negative-control receipt');
  requireValue(qualifiedSelection?.contract === 'casepath.gate1-qualified-witness-selection/1.0.0'
    && qualifiedSelection.selected_claim_id === MAIN_CARRYOVER_CLAIM_ID
    && exactSha(qualifiedSelection.selection_sha256)
    && selfHashed(qualifiedSelection)
    && mainRow.qualified_witness_selection_receipt_sha256 === qualifiedSelection.receipt_sha256,
  'main carryover does not bind the qualified-selection receipt');
  const evidence = negativeControl.evidence;
  requireValue(evidence?.claim_id === NEGATIVE_CARRYOVER_CLAIM_ID
    && evidence.recovered_copy === SAFE_REJECTION_COPY
    && evidence.before?.outcome === 'next_action'
    && evidence.recovered?.outcome === 'next_action'
    && evidence.recovered.loop_state.revision === evidence.before.loop_state.revision + 2
    && evidence.before.loop_state.observations.length === 0
    && evidence.recovered.loop_state.observations.length === 0
    && evidence.before.loop_state.selected_action.action_sha256
      === evidence.recovered.loop_state.selected_action.action_sha256
    && evidence.rejection_receipt?.authoritative_semantic_effect === false
    && selfHashed(evidence.rejection_receipt),
  'negative-control evidence does not prove +2 revision, +0 observations, and preserved action');
  requireValue(negativeRow.loop_revision === evidence.recovered.loop_state.revision
    && negativeRow.loop_state_sha256 === evidence.recovered.loop_state.state_sha256
    && negativeRow.workspace_state_sha256
      === evidence.recovered.operational_projection.workspace_prefix.state_sha256
    && negativeRow.selected_action_sha256
      === evidence.recovered.loop_state.selected_action.action_sha256,
  'negative carryover row does not bind the recovered authoritative view');

  const timing = evidence.timing;
  requireValue(finiteWithin(timing?.first_safe_action_seconds, 10)
    && finiteWithin(timing?.source_acquisition_seconds, 10)
    && finiteWithin(timing?.post_evidence_replan_seconds, 10)
    && finiteWithin(timing?.post_mutation_queue_seconds, 0.300),
  'negative carryover timings exceed their unchanged thresholds');
  const queueTiming = evidence.post_mutation_queue_timing;
  requireValue(queueTiming?.claim_id === NEGATIVE_CARRYOVER_CLAIM_ID
    && queueTiming.evidence_origin === 'sealed_gate1_safe_rejection_control'
    && queueTiming.row_count === 150
    && queueTiming.unique_claim_count === 150
    && queueTiming.mutation_visible === true
    && finiteWithin(queueTiming.seconds, 0.300),
  'negative carryover post-mutation queue timing is incomplete');
  const isolation = evidence.queue_isolation;
  requireValue(isolation?.contract === 'casepath.gate1-negative-queue-isolation/1.0.0'
    && isolation.claim_id === NEGATIVE_CARRYOVER_CLAIM_ID
    && exact(isolation.changed_claim_ids, [NEGATIVE_CARRYOVER_CLAIM_ID])
    && isolation.unchanged_nonfocal_count === 149
    && isolation.nonfocal_before_sha256 === isolation.nonfocal_after_sha256
    && selfHashed(isolation),
  'negative carryover queue-isolation proof differs');

  const carryoverSet = new Set(ORDERED_CARRYOVER_CLAIM_IDS);
  const freshClaimIds = claimIds.filter(claimId => !carryoverSet.has(claimId));
  requireValue(freshClaimIds.length === 148, 'fresh Gate 2 roster is not exactly 148 claims');
  return Object.freeze({
    contract:'casepath.gate2-gate1-carryover-plan/1.0.0',
    ordered_carryover_claim_ids:[...ORDERED_CARRYOVER_CLAIM_IDS],
    negative_claim_id:NEGATIVE_CARRYOVER_CLAIM_ID,
    main_claim_id:MAIN_CARRYOVER_CLAIM_ID,
    fresh_claim_ids:freshClaimIds,
    aggregate_claim_count:150,
    fresh_claim_count:148,
    expected_outcomes:{next_action:149, decision_ready:0, abstain:1},
    expected_journal_delta:{total:740, claim_loop:592, workspace:148},
    expected_sidecar_delta:{total:296, acquisition:148, tool_artifact:148},
    expected_admitted_authority_per_kind:148,
    expected_fresh_queue_isolation_rows:148,
    expected_latency_rows:{first_safe_action:150, source_acquisition:149, post_evidence_replan:149, post_mutation_queue:149},
  });
}
