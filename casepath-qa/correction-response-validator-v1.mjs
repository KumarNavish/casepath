export const CORRECTION_RESPONSE_PREDICATE_CONTRACT =
  'casepath.correction-lost-response-predicates/1.0.0';

export const CORRECTION_RESPONSE_PREDICATES = Object.freeze([
  { legacy_operand_index:1, name:'response_dropped' },
  { legacy_operand_index:2, name:'single_durable_correction' },
  { legacy_operand_index:3, name:'no_remaining_correction_candidate' },
  { legacy_operand_index:4, name:'revision_incremented_once' },
  { legacy_operand_index:6, name:'command_receipt_hash_valid' },
  { legacy_operand_index:7, name:'delta_hash_valid' },
  { legacy_operand_index:8, name:'response_state_matches_corrected_state' },
  { legacy_operand_index:9, name:'receipt_event_matches_delta_event' },
  { legacy_operand_index:10, name:'pending_command_body_matches_correction' },
]);

const observed = value => value === undefined ? null : value;

function parsePendingBody(pendingCommand) {
  const raw = pendingCommand?.body || 'null';
  try {
    return { value:JSON.parse(raw), error:null };
  } catch (error) {
    return { value:null, error:error instanceof Error ? error.message : String(error) };
  }
}

export function evaluateCorrectionResponsePredicates({
  dropped,
  corrected,
  priorRevision,
  committedResponse,
  delta,
  pendingCommand,
  exactLoopSha,
  canonical,
}) {
  if (typeof exactLoopSha !== 'function' || typeof canonical !== 'function') {
    throw new TypeError('correction response validation requires exact hash and canonical functions');
  }

  const pendingBody = parsePendingBody(pendingCommand);
  const expectedPendingBody = { correction_id:delta?.correction_id };
  const definitions = [
    {
      legacy_operand_index:1,
      name:'response_dropped',
      passed:Boolean(dropped),
      observed:{ dropped:Boolean(dropped) },
    },
    {
      legacy_operand_index:2,
      name:'single_durable_correction',
      passed:corrected?.correction_count === 1,
      observed:{ correction_count:observed(corrected?.correction_count) },
    },
    {
      legacy_operand_index:3,
      name:'no_remaining_correction_candidate',
      passed:Array.isArray(corrected?.correction_candidates)
        && corrected.correction_candidates.length === 0,
      observed:{
        correction_candidate_count:Array.isArray(corrected?.correction_candidates)
          ? corrected.correction_candidates.length
          : null,
      },
    },
    {
      legacy_operand_index:4,
      name:'revision_incremented_once',
      passed:corrected?.loop_state?.revision === priorRevision + 1,
      observed:{
        prior_revision:observed(priorRevision),
        expected_revision:typeof priorRevision === 'number' ? priorRevision + 1 : null,
        corrected_revision:observed(corrected?.loop_state?.revision),
      },
    },
    {
      legacy_operand_index:6,
      name:'command_receipt_hash_valid',
      passed:exactLoopSha(committedResponse?.command_receipt, 'receipt_sha256'),
      observed:{ receipt_sha256:observed(committedResponse?.command_receipt?.receipt_sha256) },
    },
    {
      legacy_operand_index:7,
      name:'delta_hash_valid',
      passed:exactLoopSha(delta, 'delta_sha256'),
      observed:{ delta_sha256:observed(delta?.delta_sha256) },
    },
    {
      legacy_operand_index:8,
      name:'response_state_matches_corrected_state',
      passed:committedResponse?.state_sha256 === corrected?.loop_state?.state_sha256,
      observed:{
        response_state_sha256:observed(committedResponse?.state_sha256),
        corrected_state_sha256:observed(corrected?.loop_state?.state_sha256),
      },
    },
    {
      legacy_operand_index:9,
      name:'receipt_event_matches_delta_event',
      passed:committedResponse?.command_receipt?.event_sha256 === delta?.event_sha256,
      observed:{
        receipt_event_sha256:observed(committedResponse?.command_receipt?.event_sha256),
        delta_event_sha256:observed(delta?.event_sha256),
      },
    },
    {
      legacy_operand_index:10,
      name:'pending_command_body_matches_correction',
      passed:pendingBody.error === null
        && canonical(pendingBody.value) === canonical(expectedPendingBody),
      observed:{
        pending_body:pendingBody.value,
        expected_body:expectedPendingBody,
        parse_error:pendingBody.error,
      },
    },
  ].map(value => ({ ...value, passed:Boolean(value.passed) }));

  const declared = CORRECTION_RESPONSE_PREDICATES.map(
    ({legacy_operand_index, name}) => `${legacy_operand_index}:${name}`,
  );
  const actual = definitions.map(
    ({legacy_operand_index, name}) => `${legacy_operand_index}:${name}`,
  );
  if (canonical(declared) !== canonical(actual)) {
    throw new Error('correction response predicate roster drifted');
  }

  const failedPredicates = definitions
    .filter(value => !value.passed)
    .map(({legacy_operand_index, name}) => ({legacy_operand_index, name}));
  return {
    contract:CORRECTION_RESPONSE_PREDICATE_CONTRACT,
    status:failedPredicates.length === 0 ? 'PASS' : 'FAIL',
    passed:failedPredicates.length === 0,
    predicate_count:definitions.length,
    failed_predicates:failedPredicates,
    predicates:definitions,
  };
}
