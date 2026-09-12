import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import {
  MAIN_CARRYOVER_CLAIM_ID,
  NEGATIVE_CARRYOVER_CLAIM_ID,
  ORDERED_CARRYOVER_CLAIM_IDS,
  SAFE_REJECTION_COPY,
  validateGate2Gate1Carryovers,
} from './gate2-gate1-carryover-v1.mjs';

const canonical = value => Array.isArray(value)
  ? `[${value.map(canonical).join(',')}]`
  : value && typeof value === 'object'
    ? `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`
    : JSON.stringify(value);
const sha = value => createHash('sha256').update(canonical(value)).digest('hex');
const seal = (material, field = 'receipt_sha256') => ({ ...material, [field]:sha(material) });
const filler = Array.from({ length:148 }, (_, index) => `clm_fresh_${String(index).padStart(3, '0')}`);
const claimIds = [...ORDERED_CARRYOVER_CLAIM_IDS, ...filler].sort();

function fixture() {
  const rejectionReceipt = seal({
    contract:'casepath.workspace-authority-rejection/1.0.0',
    authoritative_semantic_effect:false,
  });
  const queueIsolation = seal({
    contract:'casepath.gate1-negative-queue-isolation/1.0.0',
    claim_id:NEGATIVE_CARRYOVER_CLAIM_ID,
    changed_claim_ids:[NEGATIVE_CARRYOVER_CLAIM_ID],
    unchanged_nonfocal_count:149,
    nonfocal_before_sha256:'b'.repeat(64),
    nonfocal_after_sha256:'b'.repeat(64),
  });
  const negativeView = {
    outcome:'next_action',
    loop_state:{
      revision:4,
      state_sha256:'1'.repeat(64),
      observations:[],
      selected_action:{ action_sha256:'a'.repeat(64) },
    },
    operational_projection:{ workspace_prefix:{ state_sha256:'2'.repeat(64) } },
  };
  const negativeControl = seal({
    contract:'casepath.gate1-safe-rejection-negative-control/1.0.0',
    control_claim_id:NEGATIVE_CARRYOVER_CLAIM_ID,
    expected_semantic_effect:false,
    exact_ui_copy:SAFE_REJECTION_COPY,
    evidence:{
      claim_id:NEGATIVE_CARRYOVER_CLAIM_ID,
      recovered_copy:SAFE_REJECTION_COPY,
      before:{
        outcome:'next_action',
        loop_state:{ revision:2, observations:[], selected_action:{ action_sha256:'a'.repeat(64) } },
      },
      recovered:negativeView,
      rejection_receipt:rejectionReceipt,
      timing:{
        first_safe_action_seconds:0.1,
        source_acquisition_seconds:0.2,
        post_evidence_replan_seconds:0.3,
        post_mutation_queue_seconds:0.01,
      },
      post_mutation_queue_timing:{
        claim_id:NEGATIVE_CARRYOVER_CLAIM_ID,
        evidence_origin:'sealed_gate1_safe_rejection_control',
        row_count:150,
        unique_claim_count:150,
        mutation_visible:true,
        seconds:0.01,
      },
      queue_isolation:queueIsolation,
    },
  });
  const qualifiedSelection = seal({
    contract:'casepath.gate1-qualified-witness-selection/1.0.0',
    selected_claim_id:MAIN_CARRYOVER_CLAIM_ID,
    selection_sha256:'3'.repeat(64),
  });
  const carryoverMaterial = {
    contract:'casepath.gate1-gate2-carryovers/1.0.0',
    ordered_claim_ids:[...ORDERED_CARRYOVER_CLAIM_IDS],
    rows:[
      {
        role:'safe_rejection_zero_effect',
        claim_id:NEGATIVE_CARRYOVER_CLAIM_ID,
        final_outcome:'next_action',
        typed_safe_rejection:true,
        authoritative_semantic_effect:false,
        loop_revision:4,
        loop_state_sha256:'1'.repeat(64),
        workspace_state_sha256:'2'.repeat(64),
        observation_count:0,
        selected_action_sha256:'a'.repeat(64),
        queue_row_sha256:'4'.repeat(64),
        negative_control_receipt_sha256:negativeControl.receipt_sha256,
      },
      {
        role:'qualified_typed_abstention',
        claim_id:MAIN_CARRYOVER_CLAIM_ID,
        final_outcome:'abstain',
        typed_abstention:true,
        loop_revision:12,
        loop_state_sha256:'5'.repeat(64),
        workspace_state_sha256:'6'.repeat(64),
        observation_count:3,
        selected_action_sha256:null,
        queue_row_sha256:'7'.repeat(64),
        qualified_witness_selection_receipt_sha256:qualifiedSelection.receipt_sha256,
      },
    ],
    aggregate_claim_count:150,
    fresh_gate2_claim_count:148,
    expected_outcomes:{next_action:149, decision_ready:0, abstain:1},
    expected_gate2_journal_delta:{total:740, claim_loop:592, workspace:148},
    expected_gate2_sidecar_delta:{total:296, acquisition:148, tool_artifact:148},
    expected_gate2_admitted_authority_per_kind:148,
  };
  return {
    gate1Report:{
      mutated_claim_count:2,
      mutated_claim_ids:[...ORDERED_CARRYOVER_CLAIM_IDS],
      gate2_carryovers:seal(carryoverMaterial),
    },
    negativeControl,
    qualifiedSelection,
  };
}

const valid = fixture();
const plan = validateGate2Gate1Carryovers({ claimIds, ...valid });
assert.equal(plan.fresh_claim_count, 148);
assert.deepEqual(plan.expected_journal_delta, { total:740, claim_loop:592, workspace:148 });
assert.deepEqual(plan.expected_latency_rows, {
  first_safe_action:150,
  source_acquisition:149,
  post_evidence_replan:149,
  post_mutation_queue:149,
});

function rejected(mutator, reseal = () => {}) {
  const value = fixture();
  mutator(value);
  reseal(value);
  assert.throws(() => validateGate2Gate1Carryovers({ claimIds, ...value }),
    /Gate 2 carryover compatibility failed/);
}
const resealCarryovers = value => {
  const material = Object.fromEntries(Object.entries(value.gate1Report.gate2_carryovers)
    .filter(([key]) => key !== 'receipt_sha256'));
  value.gate1Report.gate2_carryovers = seal(material);
};
const resealNegative = value => {
  const material = Object.fromEntries(Object.entries(value.negativeControl)
    .filter(([key]) => key !== 'receipt_sha256'));
  value.negativeControl = seal(material);
};

rejected(value => { value.gate1Report.mutated_claim_ids.reverse(); });
rejected(value => { value.gate1Report.mutated_claim_ids.push('clm_unexpected_third'); value.gate1Report.mutated_claim_count = 3; });
rejected(value => { value.gate1Report.gate2_carryovers.rows[0].role = 'qualified_typed_abstention'; }, resealCarryovers);
rejected(value => { value.gate1Report.gate2_carryovers.expected_gate2_journal_delta.total = 741; }, resealCarryovers);
rejected(value => { value.gate1Report.gate2_carryovers.expected_gate2_sidecar_delta.total = 297; }, resealCarryovers);
rejected(value => { value.gate1Report.gate2_carryovers.expected_gate2_admitted_authority_per_kind = 149; }, resealCarryovers);
rejected(value => { value.negativeControl.evidence.recovered.loop_state.observations.push({}); }, resealNegative);
rejected(value => { value.negativeControl.evidence.recovered.loop_state.revision = 5; }, resealNegative);
rejected(value => { value.negativeControl.expected_semantic_effect = true; }, resealNegative);
rejected(value => { value.negativeControl.evidence.queue_isolation.nonfocal_after_sha256 = '8'.repeat(64); }, resealNegative);
for (const [field, maximum] of [
  ['first_safe_action_seconds', 10],
  ['source_acquisition_seconds', 10],
  ['post_evidence_replan_seconds', 10],
  ['post_mutation_queue_seconds', 0.300],
]) rejected(value => { value.negativeControl.evidence.timing[field] = maximum + 0.001; }, resealNegative);

console.log('gate2-gate1-carryover-v1: PASS');
