import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs from 'node:fs/promises';
import {
  SCOPED_CORRECTION_DERIVED_CHECKLIST_FIELDS,
  SCOPED_CORRECTION_PREDICATES,
  evaluateScopedCorrectionPredicates,
} from './scoped-correction-validator-v1.mjs';

const FLOAT_FIELDS = new Set(['confidence', 'cost_usd']);
const canonical = value => {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(item => canonical(item)).join(',')}]`;
  return `{${Object.keys(value).sort().map(
    key => `${JSON.stringify(key)}:${canonical(value[key])}`,
  ).join(',')}}`;
};
const claimLoopCanonical = (value, field = null) => {
  if (value === null || typeof value !== 'object') {
    if (typeof value === 'number' && Number.isInteger(value) && FLOAT_FIELDS.has(field)) {
      return value.toFixed(1);
    }
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map(item => claimLoopCanonical(item)).join(',')}]`;
  }
  return `{${Object.keys(value).sort().map(
    key => `${JSON.stringify(key)}:${claimLoopCanonical(value[key], key)}`,
  ).join(',')}}`;
};
const claimLoopSha = value => createHash('sha256')
  .update(claimLoopCanonical(value))
  .digest('hex');
const clone = value => structuredClone(value);

const TARGET_FACT_ID = 'fact.workspace.lt_intake.transition';
const TARGET_ITEM_ID = 'workspace_evidence.lt_intake';
const DEADLINE_ITEM_ID = 'workspace_evidence.lt_deadline';
const FORM_ITEM_ID = 'workspace_evidence.lt_form';
const CONDITIONAL = nodeId => `One of the linked process nodes is reached: ${nodeId}`;

function process({ selectedPath, currentNode, nextAction }) {
  const requirements = [
    ['lt_intake', TARGET_ITEM_ID],
    ['lt_deadline', DEADLINE_ITEM_ID],
    ['lt_form', FORM_ITEM_ID],
  ];
  const gaps = ['workspace_evidence_gap.lt_intake', 'workspace_evidence_gap.lt_deadline'];
  return {
    current_node:currentNode,
    selected_path:selectedPath,
    current_overlay:{
      current_node_id:currentNode,
      next_action_node_id:nextAction,
    },
    nodes:[
      ...requirements.map(([nodeId, itemId]) => ({
        node_id:nodeId,
        evidence_requirement_ids:[itemId],
      })),
      ...gaps.map(nodeId => ({ node_id:nodeId, evidence_requirement_ids:[] })),
    ],
  };
}

function evidence({ itemId, nodeId, status, active, sourceRef }) {
  return {
    acceptable_alternatives:[],
    applies_when:active ? 'always' : CONDITIONAL(nodeId),
    artifact_ids:[`artifact.${nodeId}`],
    bounded_tool_id:'loopback-source-byte-acquisition-v1',
    current_path:active,
    fact_id:`fact.workspace.${nodeId}.transition`,
    item_id:itemId,
    legal_basis_ids:['policy.test.clause-01'],
    loop_source_ref_ids:[sourceRef],
    max_observed_attempts:2,
    node_id:nodeId,
    node_ids:[nodeId],
    required_level:active ? 'mandatory' : 'conditional',
    status,
    title:nodeId,
    why:'Bounded evidence is required.',
  };
}

function fixture() {
  const priorFact = {
    confidence:1,
    explanation:'A source assertion controls intake.',
    fact_id:TARGET_FACT_ID,
    normalized_value:'lt_e01',
    state:'known',
    value:'Intake is supported.',
  };
  const correctedFact = {
    confidence:1,
    explanation:'The correction withdraws decision sufficiency.',
    fact_id:TARGET_FACT_ID,
    normalized_value:'unresolved',
    state:'unknown',
    value:'Correction receipt: evidence is insufficient.',
  };
  const otherFact = {
    confidence:1,
    explanation:'Deadline remains unresolved.',
    fact_id:'fact.workspace.lt_deadline.transition',
    normalized_value:'unresolved',
    state:'unknown',
    value:'Unresolved.',
  };
  const priorEvidence = evidence({
    itemId:TARGET_ITEM_ID,
    nodeId:'lt_intake',
    status:'provided_sufficient',
    active:true,
    sourceRef:'source-ref.intake',
  });
  const correctedEvidence = {
    ...priorEvidence,
    status:'provided_insufficient',
  };
  const priorDeadline = evidence({
    itemId:DEADLINE_ITEM_ID,
    nodeId:'lt_deadline',
    status:'provided_insufficient',
    active:true,
    sourceRef:'source-ref.deadline',
  });
  const correctedDeadline = {
    ...priorDeadline,
    applies_when:CONDITIONAL('lt_deadline'),
    current_path:false,
    required_level:'conditional',
  };
  const form = evidence({
    itemId:FORM_ITEM_ID,
    nodeId:'lt_form',
    status:'conditional',
    active:false,
    sourceRef:'source-ref.form',
  });
  const observedState = {
    facts:[priorFact, otherFact],
    process:process({
      selectedPath:['lt_intake', 'lt_deadline', 'workspace_evidence_gap.lt_deadline'],
      currentNode:'lt_deadline',
      nextAction:'workspace_evidence_gap.lt_deadline',
    }),
    checklist:{ items:[priorEvidence, priorDeadline, form] },
    six_agent_cycle_receipt:{ cycle_kind:'observation' },
  };
  const correctedState = {
    facts:[correctedFact, clone(otherFact)],
    process:process({
      selectedPath:['lt_intake', 'workspace_evidence_gap.lt_intake'],
      currentNode:'lt_intake',
      nextAction:'workspace_evidence_gap.lt_intake',
    }),
    checklist:{ items:[correctedEvidence, correctedDeadline, clone(form)] },
    six_agent_cycle_receipt:{ cycle_kind:'correction' },
  };
  const proposedSemantics = {
    evidence_item_id:TARGET_ITEM_ID,
    evidence_status:'provided_insufficient',
    explanation:correctedFact.explanation,
    fact_id:TARGET_FACT_ID,
    fact_state:'unknown',
    normalized_value:null,
    value:correctedFact.value,
  };
  const currentSemantics = {
    evidence_status:priorEvidence.status,
    explanation:priorFact.explanation,
    fact_state:priorFact.state,
    normalized_value:priorFact.normalized_value,
    value:priorFact.value,
  };
  const actualAfterSemantics = {
    evidence_status:correctedEvidence.status,
    explanation:correctedFact.explanation,
    fact_state:correctedFact.state,
    normalized_value:correctedFact.normalized_value,
    value:correctedFact.value,
  };
  return {
    observedState,
    correctedState,
    candidate:{
      current_semantics:clone(currentSemantics),
      proposed_semantics:clone(proposedSemantics),
    },
    delta:{
      fact_id:TARGET_FACT_ID,
      evidence_item_id:TARGET_ITEM_ID,
      before_fact_sha256:claimLoopSha(priorFact),
      after_fact_sha256:claimLoopSha(correctedFact),
      before_evidence_sha256:claimLoopSha(priorEvidence),
      after_evidence_sha256:claimLoopSha(correctedEvidence),
      unrelated_facts_before_sha256:'a'.repeat(64),
      unrelated_facts_after_sha256:'a'.repeat(64),
      before_semantics:clone(currentSemantics),
      after_semantics:clone(actualAfterSemantics),
      effect:clone(proposedSemantics),
    },
    priorFact,
    priorEvidence,
    correctedFact,
    correctedEvidence,
    actualAfterSemantics:clone(actualAfterSemantics),
    claimLoopSha,
    canonical,
  };
}

function evaluate(value) {
  return evaluateScopedCorrectionPredicates(value);
}

function reject(name, mutate, expectedPredicate) {
  const value = fixture();
  mutate(value);
  const result = evaluate(value);
  assert.equal(result.passed, false, name);
  assert.ok(result.failed_predicates.some(row => row.name === expectedPredicate), name);
  return result;
}

const baseline = evaluate(fixture());
assert.equal(baseline.status, 'PASS');
assert.equal(baseline.passed, true);
assert.equal(baseline.predicate_count, 15);
assert.deepEqual(baseline.failed_predicates, []);
assert.deepEqual(
  baseline.predicates.map(row => row.name),
  SCOPED_CORRECTION_PREDICATES.map(row => row.name),
);
assert.deepEqual(
  baseline.predicates.map(row => row.legacy_operand_index),
  Array.from({ length:15 }, (_, index) => index + 1),
);
assert.deepEqual(baseline.affected_checklist_item_ids, [DEADLINE_ITEM_ID]);
assert.deepEqual(SCOPED_CORRECTION_DERIVED_CHECKLIST_FIELDS, [
  'applies_when',
  'current_path',
  'required_level',
]);
const checklistControl = baseline.predicates[4].observed;
assert.deepEqual(checklistControl.non_target_content_mutations, []);
assert.deepEqual(checklistControl.before_applicability_mismatches, []);
assert.deepEqual(checklistControl.after_applicability_mismatches, []);
assert.deepEqual(checklistControl.outside_cone_mutations, []);

const runnerSource = await fs.readFile(
  new URL('./browser-claims-workspace-authority-v1.mjs', import.meta.url),
  'utf8',
);
assert.ok(runnerSource.includes(
  "import { evaluateScopedCorrectionPredicates } from './scoped-correction-validator-v1.mjs';",
));
const localityStart = runnerSource.indexOf(
  'const correctionLocalityValidation = evaluateScopedCorrectionPredicates({',
);
const localityCheck = runnerSource.indexOf(
  'check(`${prefix}: authoritative delta changes only the target fact/evidence`',
  localityStart,
);
assert.ok(localityStart > 0 && localityCheck > localityStart);
const localityBlock = runnerSource.slice(localityStart, localityCheck);
assert.ok(localityBlock.includes('process.stdout.write'));
assert.ok(localityBlock.indexOf('process.stdout.write') < localityCheck - localityStart);
assert.ok(!runnerSource.includes(
  'canonical(observed.loop_state.checklist.items.filter(row => row.item_id !== delta.evidence_item_id))',
));

reject('unchanged target fact', value => {
  value.delta.after_fact_sha256 = value.delta.before_fact_sha256;
}, 'target_fact_changed');
reject('unchanged target evidence', value => {
  value.delta.after_evidence_sha256 = value.delta.before_evidence_sha256;
}, 'target_evidence_changed');
reject('unrelated fact digest drift', value => {
  value.delta.unrelated_facts_after_sha256 = 'b'.repeat(64);
}, 'unrelated_fact_digest_unchanged');
reject('non-target fact mutation', value => {
  value.correctedState.facts[1].value = 'Mutated.';
}, 'non_target_facts_unchanged');
reject('prior fact hash mismatch', value => {
  value.delta.before_fact_sha256 = '0'.repeat(64);
}, 'prior_fact_hash_matches_delta');
reject('prior evidence hash mismatch', value => {
  value.delta.before_evidence_sha256 = '0'.repeat(64);
}, 'prior_evidence_hash_matches_delta');
reject('corrected fact hash mismatch', value => {
  value.delta.after_fact_sha256 = '0'.repeat(64);
}, 'corrected_fact_hash_matches_delta');
reject('corrected evidence hash mismatch', value => {
  value.delta.after_evidence_sha256 = '0'.repeat(64);
}, 'corrected_evidence_hash_matches_delta');
reject('corrected fact remains known', value => {
  value.correctedFact.state = 'known';
}, 'corrected_fact_is_unknown');
reject('corrected evidence remains sufficient', value => {
  value.correctedEvidence.status = 'provided_sufficient';
}, 'corrected_evidence_is_insufficient');
reject('before semantics differ from candidate', value => {
  value.candidate.current_semantics.normalized_value = 'different';
}, 'before_semantics_match_candidate');
reject('after semantics differ from authoritative state', value => {
  value.delta.after_semantics.normalized_value = 'different';
}, 'after_semantics_match_authoritative_state');
reject('effect differs from candidate', value => {
  value.candidate.proposed_semantics.value = 'Different effect.';
}, 'effect_matches_candidate');
reject('cycle kind is not correction', value => {
  value.correctedState.six_agent_cycle_receipt.cycle_kind = 'observation';
}, 'cycle_kind_is_correction');

const wrongPath = reject('wrong derived path flag', value => {
  const deadline = value.correctedState.checklist.items
    .find(row => row.item_id === DEADLINE_ITEM_ID);
  deadline.current_path = true;
}, 'non_target_checklist_content_unchanged_and_applicability_rederived');
assert.deepEqual(
  wrongPath.predicates[4].observed.after_applicability_mismatches.map(row => row.item_id),
  [DEADLINE_ITEM_ID],
);

const processPathMutation = reject('checklist is inconsistent with authoritative process path', value => {
  value.correctedState.process.selected_path.splice(1, 0, 'lt_deadline');
}, 'non_target_checklist_content_unchanged_and_applicability_rederived');
assert.deepEqual(
  processPathMutation.predicates[4].observed.outside_cone_mutations.map(row => row.item_id),
  [DEADLINE_ITEM_ID],
);

const outsideCone = reject('outside-cone applicability mutation', value => {
  const formItem = value.correctedState.checklist.items.find(row => row.item_id === FORM_ITEM_ID);
  formItem.required_level = 'mandatory';
}, 'non_target_checklist_content_unchanged_and_applicability_rederived');
assert.deepEqual(
  outsideCone.predicates[4].observed.outside_cone_mutations.map(row => row.item_id),
  [FORM_ITEM_ID],
);

const provenance = reject('non-target provenance mutation', value => {
  const deadline = value.correctedState.checklist.items
    .find(row => row.item_id === DEADLINE_ITEM_ID);
  deadline.loop_source_ref_ids = ['source-ref.mutated'];
}, 'non_target_checklist_content_unchanged_and_applicability_rederived');
assert.deepEqual(
  provenance.predicates[4].observed.non_target_content_mutations.map(row => row.item_id),
  [DEADLINE_ITEM_ID],
);

reject('non-target artifact mutation', value => {
  const deadline = value.correctedState.checklist.items
    .find(row => row.item_id === DEADLINE_ITEM_ID);
  deadline.artifact_ids = ['artifact.mutated'];
}, 'non_target_checklist_content_unchanged_and_applicability_rederived');
reject('non-target status mutation', value => {
  const deadline = value.correctedState.checklist.items
    .find(row => row.item_id === DEADLINE_ITEM_ID);
  deadline.status = 'provided_sufficient';
}, 'non_target_checklist_content_unchanged_and_applicability_rederived');
reject('outside-cone applies_when mutation', value => {
  const formItem = value.correctedState.checklist.items.find(row => row.item_id === FORM_ITEM_ID);
  formItem.applies_when = 'always';
}, 'non_target_checklist_content_unchanged_and_applicability_rederived');
reject('evidence owner mutation', value => {
  const deadline = value.correctedState.checklist.items
    .find(row => row.item_id === DEADLINE_ITEM_ID);
  deadline.node_id = 'lt_form';
  deadline.node_ids = ['lt_form'];
}, 'non_target_checklist_content_unchanged_and_applicability_rederived');
reject('checklist roster mutation', value => {
  value.correctedState.checklist.items.pop();
}, 'non_target_checklist_content_unchanged_and_applicability_rederived');

console.log(JSON.stringify({
  status:'PASS',
  predicate_count:baseline.predicate_count,
  affected_cone:baseline.affected_checklist_item_ids,
  named_predicate_mutants:14,
  checklist_mutants:9,
  wrong_path_rejected:true,
  outside_cone_rejected:true,
  provenance_mutation_rejected:true,
}, null, 2));
