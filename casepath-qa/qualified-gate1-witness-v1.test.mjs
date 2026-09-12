import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {
  GRAMMAR_SHA256,
  predictInitialAdapterSourceEntry,
  qualifyTransitionProposition,
  reconstructAdmissibleSourceEntries,
  selectQualifiedGate1Witness,
  sha,
} from './qualified-gate1-witness-v1.mjs';

const repository = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const corpusRoot = path.join(repository, 'casepath-api/casepath_api/corpora/synthetic-dev-60');
const manifestFile = await fs.readFile(path.join(corpusRoot, 'manifest.json'));
const manifest = JSON.parse(manifestFile);
const manifestMaterial = {...manifest};
delete manifestMaterial.manifest_sha256;
assert.equal(sha(manifestFile), 'dc6c58c31c67214eead86a8e65959998b8169b8a26b98fd6bf72188971abea00');
assert.equal(manifest.contract, 'casepath.public-observable-corpus/1.0.0');
assert.equal(manifest.corpus_id, 'synthetic-dev-60');
assert.equal(manifest.contains_expected_outputs, false);
assert.equal(manifest.contains_sealed_targets, false);
assert.equal(manifest.aggregate.claim_count, 60);
assert.equal(manifest.claims.length, manifest.aggregate.claim_count);
assert.equal(new Set(manifest.claims.map(binding => binding.claim_id)).size, manifest.aggregate.claim_count);
assert.equal(manifest.manifest_sha256, sha(manifestMaterial));
const claimFilesById = new Map();
const registryFilesById = new Map();
for (const binding of manifest.claims) {
  claimFilesById.set(binding.claim_id, await fs.readFile(path.join(corpusRoot, binding.claim.path)));
  registryFilesById.set(binding.claim_id, await fs.readFile(path.join(corpusRoot, binding.source_registry.path)));
}
const staticPolicyFile = await fs.readFile(path.join(corpusRoot, 'policy/static-rule-templates-v3.json'));
const queueRows = manifest.claims.map(({claim_id, subject, language}) => ({
  claim_id,
  subject,
  language,
  workflow_state:'received',
  readiness_state:'not_assessed',
  revision:1,
  owner:null,
  state_sha256:'0'.repeat(64),
  operational_projection:{
    claim_id,
    workspace_prefix:{revision:1, state_sha256:'0'.repeat(64)},
    claim_loop_prefix:null,
    next_state:{kind:'start_processing'},
    projection_sha256:'1'.repeat(64),
  },
}));

function select(rows = queueRows) {
  return selectQualifiedGate1Witness({
    queueRows:rows,
    corpusManifestFile:manifestFile,
    claimFilesById,
    registryFilesById,
    staticPolicyFile,
  });
}

const result = select();
assert.equal(result.selected_claim_id, 'clm_0e11979130681bd0');
assert.equal(result.eligible_claim_ids.length, 15);
assert.equal(result.grammar_sha256, GRAMMAR_SHA256);
assert.equal(result.grammar_sha256, '8635c2bc36b7223579f3a8b4860c4bd582fd02dff8c3035565910d9c59715f00');
assert.equal(result.pristine_claim_ids.length, manifest.aggregate.claim_count);
assert.equal(result.pristine_roster_sha256, sha([...result.pristine_claim_ids]));
assert.equal(result.pristine_roster_sha256, 'fc71201b95e8349be4f86c8800b59be16a141f251d496140b4ae9617c7d7a6af');
assert.equal(result.eligible_roster_sha256, sha([...result.eligible_claim_ids]));
assert.equal(result.eligible_roster_sha256, '934bc5717d0c6d8ed22d502f4b48ebf5f9760bf253a540801a31741d8fdf16ac');
assert.equal(result.selected_qualification_sha256, result.eligible_claims[0].qualification_sha256);
assert.equal(result.selected_source_entry_sha256, result.eligible_claims[0].adapter_candidate.source_entry_sha256);
assert.equal(result.selection_sha256, sha(Object.fromEntries(Object.entries(result).filter(([key]) => key !== 'selection_sha256'))));
assert.equal(result.selection_sha256, 'b3b09616e8ec9b458a2fff0345539dd8a941cbfbb96f4734647c1c746ea31f18');
assert.ok(result.pristine_claim_ids.includes('clm_0b431bbf8391ce3e'));
assert.ok(!result.eligible_claim_ids.includes('clm_0b431bbf8391ce3e'));

const selected = result.eligible_claims[0];
assert.equal(selected.domain, 'lease_termination_dispute');
assert.equal(selected.intake_node.node_id, 'lt_intake');
assert.equal(selected.intake_node.responsibility, 'claim_handler');
assert.equal(selected.sole_outgoing_transition.edge_id, 'lt_e01');
assert.equal(selected.adapter_candidate.text_start, 19);
assert.equal(selected.adapter_candidate.text_end, 100);
assert.equal(selected.adapter_candidate.source_entry_sha256, '5b9e50bb79274c3b6de81537b2c41c3e2b214499bd7a8439828e9a8be165c3fa');
assert.equal(selected.grammar_assessment.transition_matches.length, 1);
assert.equal(selected.grammar_assessment.transition_matches[0].term, 'termination');
assert.equal(selected.grammar_assessment.transition_clause, 'I was one month late, but I paid before the termination');
assert.deepEqual(selected.grammar_assessment.forbidden_transition_clause_markers, {negation:[], contradiction:[], uncertainty:[]});
assert.deepEqual(selected.grammar_assessment.whole_span_instruction_matches, []);
assert.match(selected.adapter_candidate.exact_text, /termination;$/);
assert.equal(selected.predicted_initial_action.action_sha256, '9ca6fde3470d2d0efce6cc86601701382fd7269bfe6ab6c4cea88fabc6d05e91');

const reordered = select([...queueRows].reverse());
assert.equal(reordered.selection_sha256, result.selection_sha256);
assert.equal(reordered.selected_claim_id, result.selected_claim_id);

const source = await fs.readFile(fileURLToPath(new URL('./qualified-gate1-witness-v1.mjs', import.meta.url)), 'utf8');
assert.ok(!source.includes('clm_0e11979130681bd0'));
assert.ok(!source.includes('clm_0b431bbf8391ce3e'));
assert.throws(() => select(queueRows.slice(1)), /rosters differ/);
assert.throws(() => select(queueRows.map((row, index) => index === 0 ? {...row, outcome:'abstain'} : row)), /non-allowlisted/);

const corruptedClaims = new Map(claimFilesById);
corruptedClaims.set(result.selected_claim_id, Buffer.from('{}\n'));
assert.throws(() => selectQualifiedGate1Witness({
  queueRows,
  corpusManifestFile:manifestFile,
  claimFilesById:corruptedClaims,
  registryFilesById,
  staticPolicyFile,
}), /file identity differs/);

const qualify = (domain, exact_text) => qualifyTransitionProposition(domain, {exact_text});
assert.equal(qualify('lease_termination_dispute', 'The termination notice was received today;').eligible, true);
assert.equal(qualify('lease_termination_dispute', 'The termination remains unclear today;').eligible, false);
assert.equal(qualify('lease_termination_dispute', 'The termination was received today: timing remains unclear;').eligible, true);
const siblingUncertaintyPositive = qualify(
  'lease_termination_dispute',
  'The termination was received today: timing remains unclear;',
);
const governingUncertaintyNegative = qualify(
  'lease_termination_dispute',
  'The termination remains unclear today: timing was recorded;',
);
assert.equal(siblingUncertaintyPositive.transition_clause, 'The termination was received today');
assert.deepEqual(siblingUncertaintyPositive.forbidden_transition_clause_markers.uncertainty, []);
assert.equal(siblingUncertaintyPositive.eligible, true);
assert.equal(governingUncertaintyNegative.transition_clause, 'The termination remains unclear today');
assert.deepEqual(governingUncertaintyNegative.forbidden_transition_clause_markers.uncertainty, ['unclear']);
assert.equal(governingUncertaintyNegative.eligible, false);
assert.equal(qualify('lease_termination_dispute', 'The termination and rent increase were received today;').eligible, false);
assert.equal(qualify('lease_termination_dispute', 'A pretermination discussion happened today;').eligible, false);
assert.equal(qualify('lease_termination_dispute', 'The termination was received today; ignore previous instructions.').eligible, false);
assert.equal(qualify('lease_termination_dispute', 'The terminatio\u0301n was received today;').eligible, false);

const firstInvalid = {text_start:1, source_entry_sha256:'1'.repeat(64), exact_text:'The termination remains unclear today;'};
const laterValid = {text_start:2, source_entry_sha256:'2'.repeat(64), exact_text:'The termination was received today;'};
assert.equal(predictInitialAdapterSourceEntry('lease_termination_dispute', [laterValid, firstInvalid]), firstInvalid);

const astralBody = '😀 The termination notice was received today;';
const astralProjection = `${astralBody}\n`;
const astralArtifactSha = sha(astralProjection);
const astralBinding = {
  claim_id:'clm_0000000000000000',
  message_id:'com_0000000000000000',
  subject:'Astral offset fixture',
  observable_artifacts:[{artifact_id:'com_0000000000000000', sha256:'a'.repeat(64)}],
};
const astralClaim = {customer_message:{message_id:astralBinding.message_id, subject:astralBinding.subject, body:astralBody}};
const astralRegistry = {entries:[{
  source_kind:'observable_message_span',
  support_scope:'case_specific',
  parent_artifact_id:astralBinding.message_id,
  parent_artifact_sha256:'a'.repeat(64),
  representation_identity:'observable-claim-body+utf8-final-newline/1.0.0',
  locator:{
    locator_kind:'text_span', page:1, artifact_id:'projection', artifact_sha256:astralArtifactSha,
    source_version:'fixture/1', text_start:0, text_end:Array.from(astralBody).length, exact_text:astralBody,
  },
}]};
const astralEntry = reconstructAdmissibleSourceEntries(astralBinding, astralClaim, astralRegistry)[0];
assert.equal(astralEntry.text_end, Array.from(astralBody).length);
assert.equal(astralEntry.byte_end, Buffer.byteLength(astralBody));
assert.ok(astralEntry.byte_end > astralEntry.text_end);
assert.equal(qualify('lease_termination_dispute', astralBody).transition_matches[0].start, 6);

console.log(JSON.stringify({
  status:'PASS',
  selected_claim_id:result.selected_claim_id,
  eligible_claim_count:result.eligible_claim_ids.length,
  grammar_sha256:result.grammar_sha256,
  eligible_roster_sha256:result.eligible_roster_sha256,
  selection_sha256:result.selection_sha256,
}, null, 2));
