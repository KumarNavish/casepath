import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs from 'node:fs/promises';
import {
  CORRECTION_RESPONSE_PREDICATES,
  evaluateCorrectionResponsePredicates,
} from './correction-response-validator-v1.mjs';

const FLOAT_FIELDS = new Set(['confidence', 'cost_usd']);
const canonical = value => {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(item => canonical(item)).join(',')}]`;
  return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
};
const claimLoopCanonical = (value, field = null) => {
  if (value === null || typeof value !== 'object') {
    if (typeof value === 'number' && Number.isInteger(value) && FLOAT_FIELDS.has(field)) {
      return value.toFixed(1);
    }
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(item => claimLoopCanonical(item)).join(',')}]`;
  return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${claimLoopCanonical(value[key], key)}`).join(',')}}`;
};
const claimLoopSha = value => createHash('sha256').update(claimLoopCanonical(value)).digest('hex');
const without = (value, key) => Object.fromEntries(Object.entries(value).filter(([name]) => name !== key));
const exactLoopSha = (value, field) => Boolean(value && typeof value === 'object'
  && value[field] === claimLoopSha(without(value, field)));
const seal = (value, field) => ({ ...value, [field]:claimLoopSha(value) });

const STATE_SHA = '1'.repeat(64);
const EVENT_SHA = '2'.repeat(64);
const CORRECTION_ID = `correction.${'3'.repeat(64)}`;
const IDEMPOTENCY_KEY = 'correction-apply-focused-regression';

const responseMaterial = receipt => ({
  command_receipt:receipt,
  contract:'casepath.claim-loop-response/1.0.0',
  cost_status:'known',
  cost_usd:0,
  credential_access_status:'none_due_to_zero_provider_calls',
  incremental_loop_activity:{ model_calls:0, provider_calls:0, cost_usd:0 },
  loop_id:'loop.focused-regression',
  model_calls:0,
  phase:'TERMINAL',
  provider_calls:0,
  provider_credentials_read:false,
  revision:9,
  selected_action:null,
  source_acceptance_activity:{ model_calls:0, provider_calls:0, cost_usd:0 },
  state_sha256:STATE_SHA,
  sufficiency:{ sufficient:false },
  terminal_mode:'abstain',
  total_bound_activity:{ model_calls:0, provider_calls:0, cost_usd:0 },
  upstream_source_run_activity:{ model_calls:0, provider_calls:0, cost_usd:0 },
});

function fixture() {
  const receipt = seal({
    contract:'casepath.claim-loop-command-receipt/1.0.0',
    event_sha256:EVENT_SHA,
    idempotency_key:IDEMPOTENCY_KEY,
    loop_id:'loop.focused-regression',
    revision:9,
    state_sha256:STATE_SHA,
  }, 'receipt_sha256');
  const delta = seal({
    contract:'casepath.workspace-correction-delta/1.0.0',
    correction_id:CORRECTION_ID,
    event_sha256:EVENT_SHA,
  }, 'delta_sha256');
  return {
    dropped:true,
    corrected:{
      correction_count:1,
      correction_candidates:[],
      loop_state:{ revision:9, state_sha256:STATE_SHA },
    },
    priorRevision:8,
    committedResponse:responseMaterial(receipt),
    delta,
    pendingCommand:{ body:JSON.stringify({correction_id:CORRECTION_ID}) },
    exactLoopSha,
    canonical,
  };
}

const controls = [];
function control(name, passed) {
  assert.equal(Boolean(passed), true, name);
  controls.push(name);
}

const frontendSource = await fs.readFile(
  new URL('../casepath/assets/claims-workspace-v1.js', import.meta.url),
  'utf8',
);
const runnerSource = await fs.readFile(
  new URL('./browser-claims-workspace-authority-v1.mjs', import.meta.url),
  'utf8',
);
const frontendKeysMatch = frontendSource.match(
  /async function validateCorrectionApplyResponse[\s\S]*?const keys = \[([^\]]+)\]/,
);
assert.ok(frontendKeysMatch);
const frontendKeys = [...frontendKeysMatch[1].matchAll(/'([^']+)'/g)].map(match => match[1]);

const baseline = fixture();
const response = baseline.committedResponse;
const externalResponseSha = claimLoopSha(response);
const withSelfHash = { ...response, response_sha256:externalResponseSha };
const mutatedReceipt = { ...response.command_receipt, event_sha256:'0'.repeat(64) };
const mutatedDelta = { ...baseline.delta, event_sha256:'0'.repeat(64) };
const legacyOperands = [
  baseline.dropped,
  baseline.corrected.correction_count === 1,
  baseline.corrected.correction_candidates.length === 0,
  baseline.corrected.loop_state.revision === baseline.priorRevision + 1,
  exactLoopSha(response, 'response_sha256'),
  exactLoopSha(response.command_receipt, 'receipt_sha256'),
  exactLoopSha(baseline.delta, 'delta_sha256'),
  response.state_sha256 === baseline.corrected.loop_state.state_sha256,
  response.command_receipt.event_sha256 === baseline.delta.event_sha256,
  canonical(JSON.parse(baseline.pendingCommand.body))
    === canonical({correction_id:baseline.delta.correction_id}),
];

// Reuse the accepted diagnosis's eleven pure-data controls.
control('baseline frontend keyset accepts response',
  Object.keys(response).sort().join('|') === frontendKeys.join('|'));
control('baseline external response hash binding accepts', externalResponseSha === claimLoopSha(response));
control('response content mutation rejected by external hash',
  externalResponseSha !== claimLoopSha({...response, revision:10}));
control('durable hash mutation rejected by external hash', '0'.repeat(64) !== claimLoopSha(response));
control('inserted self hash rejected by frontend keyset',
  Object.keys(withSelfHash).sort().join('|') !== frontendKeys.join('|'));
control('inserted self hash only makes old operand true', exactLoopSha(withSelfHash, 'response_sha256'));
control('receipt mutation rejected by receipt hash', !exactLoopSha(mutatedReceipt, 'receipt_sha256'));
control('delta mutation rejected by delta hash', !exactLoopSha(mutatedDelta, 'delta_sha256'));
control('state identity mutation rejected', response.state_sha256 !== '0'.repeat(64));
control('event identity mutation rejected', response.command_receipt.event_sha256 !== '0'.repeat(64));
control('old validator isolates only operand 5',
  canonical(legacyOperands.flatMap((passed, index) => passed ? [] : [index + 1])) === canonical([5]));
assert.equal(controls.length, 11);

const validatorStart = runnerSource.indexOf('const correctionResponseValidation =');
const nextCheckStart = runnerSource.indexOf(
  'check(`${prefix}: authoritative delta changes only the target fact/evidence`',
  validatorStart,
);
assert.ok(validatorStart > 0 && nextCheckStart > validatorStart);
const runnerValidatorBlock = runnerSource.slice(validatorStart, nextCheckStart);
assert.ok(!runnerValidatorBlock.includes("exactLoopSha(committedResponse, 'response_sha256')"));
assert.ok(runnerValidatorBlock.includes('process.stdout.write'));
assert.ok(runnerValidatorBlock.indexOf('process.stdout.write')
  < runnerValidatorBlock.indexOf('check(`${prefix}: lost response'));

const valid = evaluateCorrectionResponsePredicates(baseline);
assert.equal(valid.passed, true);
assert.equal(valid.status, 'PASS');
assert.equal(valid.predicate_count, 9);
assert.deepEqual(valid.failed_predicates, []);
assert.deepEqual(valid.predicates.map(value => value.legacy_operand_index), [1,2,3,4,6,7,8,9,10]);
assert.deepEqual(valid.predicates.map(value => value.name), CORRECTION_RESPONSE_PREDICATES.map(value => value.name));

function rejected(name, mutate, expectedPredicate) {
  const value = fixture();
  mutate(value);
  const result = evaluateCorrectionResponsePredicates(value);
  assert.equal(result.passed, false, name);
  assert.ok(result.failed_predicates.some(value => value.name === expectedPredicate), name);
  return result;
}

rejected('mutated receipt', value => {
  value.committedResponse.command_receipt.event_sha256 = '0'.repeat(64);
}, 'command_receipt_hash_valid');
rejected('mutated state', value => {
  value.committedResponse.state_sha256 = '0'.repeat(64);
}, 'response_state_matches_corrected_state');
rejected('mutated event with valid receipt hash', value => {
  const changed = {
    ...without(value.committedResponse.command_receipt, 'receipt_sha256'),
    event_sha256:'0'.repeat(64),
  };
  value.committedResponse.command_receipt = seal(changed, 'receipt_sha256');
}, 'receipt_event_matches_delta_event');
rejected('mutated pending body', value => {
  value.pendingCommand.body = JSON.stringify({correction_id:`correction.${'4'.repeat(64)}`});
}, 'pending_command_body_matches_correction');
rejected('mutated delta', value => {
  value.delta.event_sha256 = '0'.repeat(64);
}, 'delta_hash_valid');

console.log(JSON.stringify({
  status:'PASS',
  reused_pure_data_controls:controls.length,
  remaining_contract_predicates:valid.predicate_count,
  valid_response_admitted:true,
  rejected_mutations:['receipt','state','event','pending_body','delta'],
  removed_legacy_operand:5,
  named_diagnostics_before_fail_fast:true,
}, null, 2));
