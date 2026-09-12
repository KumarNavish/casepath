'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {
  NATIVE_INQUIRY_MODE_HEADER,
  NATIVE_INQUIRY_MODE,
  buildEvidenceInvestigationView,
  evidenceInvestigationMarkup,
} = require('../casepath/assets/claims-workspace-v1.js');

const CLAIM_ID = 'clm_product_connection';
const OBSERVED_AT = '2025-08-29T09:00:00+02:00';
const RECEIVED_AT = '2025-08-29T10:00:00+02:00';
const SHA_A = 'a'.repeat(64);
const SHA_B = 'b'.repeat(64);
const hostile = '<script>globalThis.compromised=true</script>';

function validState() {
  const actorOutput = {
    needs:[{
      need_id:'grant_record',
      description:`Confirm the grant record ${hostile}`,
      answer:`Supported value is <img src=x onerror=alert(1)> & ${hostile}`,
      warrant_refs:['t0'],
      evidence:[{ref:'p0',role:'support'}],
      state:'received',
      until:null,
    }],
    requests:[{
      channel_id:'archive<script>',
      need_ids:['grant_record'],
      purpose:`Retrieve the decision record ${hostile}`,
    }],
  };
  const proposal = {
    contract:'casepath.native-live-provisional-proposal/1.0.0',
    observed_at:OBSERVED_AT,
    input_identity:SHA_A,
    source_prefix_sha256:SHA_B,
    needs:[{
      need_id:'grant_record',
      description:actorOutput.needs[0].description,
      answer:actorOutput.needs[0].answer,
      state:'received',
      until:null,
      until_status:null,
      warrants:[{
        ref:'t0',
        kind:'text',
        source_id:`customer-message-${hostile}`,
        view_id:'complete<body>',
        first_observed_at:OBSERVED_AT,
        text:`Exact cited source span ${hostile}\nSecond source line.`,
      }],
      evidence:[{
        ref:'p0',
        kind:'native_image',
        role:'support',
        source_id:'inspection-photo<img>',
        view_id:'page-1<script>',
        first_observed_at:OBSERVED_AT,
        page_index:0,
      }],
    }],
    authority:'FALLIBLE_MODEL_PROPOSAL_OVER_ADMITTED_SOURCE_BYTES',
    canonical_fact_effect:null,
    readiness_effect:null,
    customer_send:false,
    proposal_sha256:SHA_A,
  };
  return {
    contract:'casepath.native-live-workspace-state/1.0.0',
    claim_id:CLAIM_ID,
    completed_cycle_count:1,
    unresolved_cycle_keys:[],
    latest_cycle:{
      contract:'casepath.native-live-workspace-cycle/1.0.0',
      cycle_id:'native-cycle.fixture-recorded-0001',
      claim_id:CLAIM_ID,
      qualified:true,
      status:'completed_qualified',
      observed_at:OBSERVED_AT,
      input_identity:SHA_A,
      source_prefix_sha256:SHA_B,
      transport_receipt:{qualified:true, stdout:`DO NOT SHOW ${hostile}`},
      cost_receipt:{
        model:'fixture-recorded-reader',
        billable_cost_usd:0,
      },
      actor_output:actorOutput,
      provisional_proposal:proposal,
      canonical_facts:{},
      certified_readiness:null,
      customer_send:false,
    },
    export_state:{
      contract:'casepath.native-live-export-state/1.0.0',
      configured:true,
      available_channels:[{
        channel_id:'archive<script>',
        description:`Building archive & records ${hostile}`,
      }],
      actions:[
        {
          channel_id:'archive<script>',
          need_ids:['grant_record'],
          purpose:`Returned lookup ${hostile}`,
          status:'exported',
          cost:1,
          source_id:'return<img>',
          sha256:SHA_A,
        },
        {
          channel_id:'archive<script>',
          need_ids:['grant_record'],
          purpose:'Second lookup unavailable',
          status:'unavailable',
          cost:1,
          source_id:'unavailable-envelope',
          sha256:SHA_B,
        },
      ],
      source_admissions:[
        {kind:'export',status:'exported',source_id:'return<img>',sha256:SHA_A,observed_at:RECEIVED_AT},
        {kind:'export',status:'unavailable',source_id:'unavailable-envelope',sha256:SHA_B,observed_at:RECEIVED_AT},
      ],
      current_output:actorOutput,
    },
    canonical_facts:{},
    certified_readiness:null,
    customer_send:false,
  };
}

const state = validState();
const view = buildEvidenceInvestigationView(state, CLAIM_ID);
assert.equal(view.kind, 'qualified');
assert.equal(view.needs.length, 1);
assert.equal(view.requests.length, 1);
assert.deepEqual(view.outcomes.map(row => row.status), ['exported','unavailable']);
const markup = evidenceInvestigationMarkup(view);
assert.match(markup, /Evidence investigation/);
assert.match(markup, /Latest source review/);
assert.match(markup, /Record returned/);
assert.match(markup, /Unavailable/);
assert.match(markup, /Suggested follow-ups/);
assert.doesNotMatch(markup, /Requested follow-ups/);
assert.match(markup, /Need basis t0/);
assert.match(markup, /Record support p0/);
assert.match(markup, /cw-investigation-source-text/);
assert.equal((markup.match(/class="cw-investigation-source-text"/g) || []).length, 1);
assert.match(markup, /Exact cited source span &lt;script&gt;globalThis\.compromised=true&lt;\/script&gt;\nSecond source line\./);
assert.match(markup, /&lt;script&gt;/);
assert.match(markup, /&lt;img/);
assert.doesNotMatch(markup, /<(?:script|img)\b/i);
assert.doesNotMatch(markup, /DO NOT SHOW/);
assert.doesNotMatch(markup, /stdout|transport_receipt|canonical_fact_effect/);

const withdrawn = validState();
withdrawn.latest_cycle.actor_output.needs[0].state = 'withdrawn';
withdrawn.latest_cycle.provisional_proposal.needs[0].state = 'withdrawn';
withdrawn.export_state.current_output = withdrawn.latest_cycle.actor_output;
const withdrawnMarkup = evidenceInvestigationMarkup(buildEvidenceInvestigationView(withdrawn, CLAIM_ID));
assert.match(withdrawnMarkup, /data-native-need-state="withdrawn">Reader: Withdrawn</);
assert.doesNotMatch(withdrawnMarkup, /No longer needed/);

const unconfigured = validState();
delete unconfigured.latest_cycle.actor_output.requests;
unconfigured.export_state = null;
const unconfiguredView = buildEvidenceInvestigationView(unconfigured, CLAIM_ID);
assert.equal(unconfiguredView.kind, 'qualified');
assert.equal(unconfiguredView.requests.length, 0);
assert.equal(unconfiguredView.outcomes.length, 0);
assert.match(evidenceInvestigationMarkup(unconfiguredView), /Confirm the grant record/);

const unqualified = validState();
unqualified.latest_cycle.qualified = false;
unqualified.latest_cycle.status = 'completed_unqualified';
unqualified.latest_cycle.transport_receipt.qualified = false;
const unqualifiedView = buildEvidenceInvestigationView(unqualified, CLAIM_ID);
assert.equal(unqualifiedView.kind, 'unavailable');
assert.doesNotMatch(evidenceInvestigationMarkup(unqualifiedView), /Confirm the grant record|Supported value|Record returned/);

const malformed = validState();
malformed.latest_cycle.provisional_proposal.readiness_effect = 'decision_ready';
const malformedView = buildEvidenceInvestigationView(malformed, CLAIM_ID);
assert.equal(malformedView.kind, 'unavailable');
assert.doesNotMatch(evidenceInvestigationMarkup(malformedView), /Confirm the grant record|Supported value/);

const mismatchedLatest = validState();
mismatchedLatest.export_state.current_output = {needs:[],requests:[]};
assert.equal(buildEvidenceInvestigationView(mismatchedLatest, CLAIM_ID).kind, 'unavailable');

const empty = validState();
empty.completed_cycle_count = 0;
empty.latest_cycle = null;
empty.export_state = null;
const emptyView = buildEvidenceInvestigationView(empty, CLAIM_ID);
assert.equal(emptyView.kind, 'empty');
assert.match(evidenceInvestigationMarkup(emptyView), /No evidence investigation has been recorded/);
assert.doesNotMatch(evidenceInvestigationMarkup(emptyView), /Latest source review/);

const pending = validState();
pending.unresolved_cycle_keys = ['newer-attempt'];
const pendingView = buildEvidenceInvestigationView(pending, CLAIM_ID);
assert.equal(pendingView.kind, 'qualified');
assert.equal(pendingView.hasNewerPendingAttempt, true);
assert.match(evidenceInvestigationMarkup(pendingView), /newer review is still being reconciled/i);

assert.equal(NATIVE_INQUIRY_MODE_HEADER, 'X-CasePath-Native-Research-Mode');
assert.equal(NATIVE_INQUIRY_MODE, 'current-public-corpus-provisional-v1');
const frontendSource = fs.readFileSync(path.join(__dirname, '../casepath/assets/claims-workspace-v1.js'), 'utf8');
const loader = frontendSource.match(/async function loadEvidenceInvestigation[\s\S]*?\n  }\n\n  function loopWorkbenchMarkup/)?.[0] || '';
assert.match(loader, /headers:\{\[NATIVE_INQUIRY_MODE_HEADER\]:NATIVE_INQUIRY_MODE\}/);
assert.match(loader, /signal,/);
assert.match(loader, /if \(!isActiveDetail\(context\)\) return;/);
assert.match(loader, /if \(error\.name === 'AbortError' \|\| !isActiveDetail\(context\)\) return;/);
assert.match(loader, /if \(error\.status === 404\) return;/);

console.log('evidence-investigation-panel-v1: PASS');
