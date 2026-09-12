const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const {claimLoopStateHashMaterials} = require('../casepath/assets/claims-workspace-v1.js');

const FLOAT_FIELDS = new Set(['confidence', 'cost_usd']);
function canonical(value, field = null) {
  if (value === null || typeof value !== 'object') {
    if (typeof value === 'number' && Number.isInteger(value) && FLOAT_FIELDS.has(field)) return value.toFixed(1);
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(item => canonical(item)).join(',')}]`;
  return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key], key)}`).join(',')}}`;
}
const sha = value => createHash('sha256').update(canonical(value)).digest('hex');
const validates = value => claimLoopStateHashMaterials(value).some(material => sha(material) === value.state_sha256);

const legacyEmptyMaterial = {
  contract:'casepath.claim-loop-state/1.0.0',
  revision:2,
  cost_usd:0.0,
  selected_action:{action_id:'action.public-fixture'},
};
const legacyEmptyState = {
  ...legacyEmptyMaterial,
  native_proposal_revisions:[],
  state_sha256:sha(legacyEmptyMaterial),
};
const oldFullMaterial = Object.fromEntries(Object.entries(legacyEmptyState).filter(([key]) => key !== 'state_sha256'));
assert.notEqual(sha(oldFullMaterial), legacyEmptyState.state_sha256, 'the former client algorithm must reproduce the reported failure');
assert.equal(validates(legacyEmptyState), true, 'the server-compatible empty-revision identity must validate');
assert.equal(validates({...legacyEmptyState, revision:3}), false, 'changing a hash-bound field must fail');

const currentNativeMaterial = {
  ...legacyEmptyMaterial,
  native_proposal_revisions:[{
    revision_id:'proposal.public-fixture',
    readings:[{need_id:'need.public-fixture', state:'pending', until:null}],
  }],
};
const currentNativeState = {...currentNativeMaterial, state_sha256:sha(currentNativeMaterial)};
assert.equal(validates(currentNativeState), true, 'the current native-revision identity must validate');
assert.equal(validates({
  ...currentNativeState,
  native_proposal_revisions:[{
    ...currentNativeState.native_proposal_revisions[0],
    readings:[{need_id:'need.public-fixture', state:'received', until:null}],
  }],
}), false, 'changing a native reading must fail');

const legacyNativeMaterial = {
  ...legacyEmptyMaterial,
  native_proposal_revisions:[{
    revision_id:'proposal.public-fixture',
    readings:[{need_id:'need.public-fixture', state:'pending'}],
  }],
};
const projectedLegacyNativeState = {
  ...currentNativeMaterial,
  state_sha256:sha(legacyNativeMaterial),
};
assert.equal(validates(projectedLegacyNativeState), true, 'the exact legacy nullable-until identity must validate');

assert.deepEqual(claimLoopStateHashMaterials({...legacyEmptyState, native_proposal_revisions:null}), []);
console.log('claims-workspace-state-hash-v1: PASS');
