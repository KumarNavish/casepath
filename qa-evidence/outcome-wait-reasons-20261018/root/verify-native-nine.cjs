const assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const base=require('./base-language-v1.cjs'),patched=require('/workspace/casepath-operations-review-20261013/casepath/assets/autonomous-language-v1.js');
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const fixturePath='/workspace/casepath-reference-polish-evidence-20261013/native-v1-v2-reference.json',bytes=fs.readFileSync(fixturePath);
assert.equal(sha(bytes),'ba3ddf796cb39489e47158ca6b69d53be1866e365afa0363a7b49665af7224ce');
const fixture=JSON.parse(bytes),rows=[];
for(const [claimId,snapshot] of Object.entries(fixture.snapshots)){
  const state=snapshot.state;assert.ok(state&&state.outcome);const original=JSON.stringify(state),outcome=state.outcome;
  const before=base.outcomePresentation(state),after=patched.outcomePresentation(state);
  assert.equal(JSON.stringify(state),original);assert.equal(before.details,outcome);assert.equal(after.details,outcome);
  assert.deepEqual({...after,nextAction:null},{...before,nextAction:null});
  assert.equal(after.recordedSummary,outcome.summary||outcome.reason||'');
  for(const sentence of after.nextAction.match(/[^.!?]+[.!?]?/gu)||[]){assert.ok(sentence.trim().split(/\s+/u).length<=20);}
  assert.doesNotMatch(after.nextAction,/\b(?:provisional|derive|requalified|quarantined|compilation|recipe|applicability|regression|sha|hash|canonical|projection|branch|pinned|deterministic|verifier|synthetic)\b/iu);
  const missing=(outcome.missing_evidence||[]).length,open=(outcome.unresolved_facts||[]).length,limits=(outcome.authority_limits||[]).length,unknown=(outcome.legal_predicates||[]).some(x=>!['supported','failed'].includes(x.status));
  assert.equal(missing,0,'retained completed reference outcome has no listed missing documents');
  assert.ok(limits>0);assert.doesNotMatch(after.nextAction,/listed documents/iu);assert.match(after.nextAction,/person.*go-ahead.*real-world action/iu);
  rows.push({claim_id:claimId,revision:snapshot.revision??state.revision??null,assessment_status:outcome.assessment_status,status:outcome.status,predicate_ids:(outcome.legal_predicates||[]).map(x=>x.predicate_id),missing_evidence:missing,unresolved_facts:open,unknown_predicate:unknown,authority_limits:limits,before:before.nextAction,after:after.nextAction,non_next_action_output_equal:true,state_bytes_unchanged:true,details_same_original_object:true,recorded_summary_unchanged:true,state_json_fingerprint_sha256:sha(original)});
}
assert.equal(rows.length,9);
const result={classification:'Display-only adapter check against retained native v2 fixture; separate from published hosted acceptance and recorded trace execution.',base:'4bf9b439813ae5dd82c8820cbe96e4c1ec6db2cd',native_fixture_sha256:sha(bytes),native_profile_sha256:fixture.profile_sha256,base_language_sha256:sha(fs.readFileSync(require.resolve('./base-language-v1.cjs'))),patched_language_sha256:sha(fs.readFileSync('/workspace/casepath-operations-review-20261013/casepath/assets/autonomous-language-v1.js')),count:rows.length,all_passed:true,rows};
fs.writeFileSync('/workspace/casepath-outcome-wait-reasons-20261018/root/native-nine.json',JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({count:rows.length,all_passed:true,after:[...new Set(rows.map(x=>x.after))],all_non_next_action_outputs_equal:true,all_states_unchanged:true}));
