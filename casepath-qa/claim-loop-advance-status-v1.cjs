'use strict';

const assert = require('node:assert/strict');
const {
  claimLoopAdvanceStatus,
  SAFE_REJECTION_COPY,
  ADMITTED_ADVANCE_COPY,
} = require('../casepath/assets/claims-workspace-v1.js');

for (const [outcome, copy] of Object.entries(ADMITTED_ADVANCE_COPY)) {
  assert.deepEqual(
    claimLoopAdvanceStatus({
      beforeRevision:7,
      afterRevision:9,
      beforeObservationCount:2,
      afterObservationCount:3,
      outcome,
    }),
    {kind:'observation_admitted', observationDelta:1, copy},
  );
  assert.match(copy, /^Observation committed once\./);
}

assert.deepEqual(
  claimLoopAdvanceStatus({
    beforeRevision:7,
    afterRevision:9,
    beforeObservationCount:2,
    afterObservationCount:2,
    outcome:'next_action',
  }),
  {kind:'safely_rejected', observationDelta:0, copy:SAFE_REJECTION_COPY},
);
assert.equal(
  SAFE_REJECTION_COPY,
  'Evidence was safely rejected; no observation was added. CasePath kept the bounded action open.',
);
assert.doesNotMatch(SAFE_REJECTION_COPY, /Observation committed|observation added|observation was committed/i);

const invalid = [
  {beforeRevision:7, afterRevision:8, beforeObservationCount:2, afterObservationCount:3, outcome:'next_action'},
  {beforeRevision:7, afterRevision:10, beforeObservationCount:2, afterObservationCount:3, outcome:'next_action'},
  {beforeRevision:7, afterRevision:9, beforeObservationCount:2, afterObservationCount:4, outcome:'next_action'},
  {beforeRevision:7, afterRevision:9, beforeObservationCount:2, afterObservationCount:1, outcome:'next_action'},
  {beforeRevision:7, afterRevision:9, beforeObservationCount:2, afterObservationCount:2, outcome:'decision_ready'},
  {beforeRevision:7, afterRevision:9, beforeObservationCount:2, afterObservationCount:3, outcome:'processing'},
  {beforeRevision:7.5, afterRevision:9, beforeObservationCount:2, afterObservationCount:3, outcome:'next_action'},
];
for (const input of invalid) assert.throws(() => claimLoopAdvanceStatus(input));

console.log('claim-loop-advance-status-v1: PASS');
