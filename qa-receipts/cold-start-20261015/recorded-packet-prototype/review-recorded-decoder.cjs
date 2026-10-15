'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict'),{createHash,webcrypto}=require('node:crypto');
globalThis.crypto ||= webcrypto;
const source=process.argv[2],out=process.argv[3],ui=require(source),dir=__dirname,sha=value=>createHash('sha256').update(value).digest('hex');
const raw=fs.readFileSync(dir+'/recorded-nine-session-native.json'),input=JSON.parse(fs.readFileSync(dir+'/recorded-session-inputs-native.json'));
const descriptor=bytes=>({bytes:bytes.length,sha256:sha(bytes),deployment_commit:null,history_kind:'native_fixture'});
(async()=>{
 const checks=[];
 await assert.rejects(ui.checkedRecordedPacket(raw,descriptor(raw)));checks.push('native_requires_explicit_QA_permission');
 await assert.rejects(ui.checkedRecordedPacket(raw,{...descriptor(raw),sha256:'0'.repeat(64)},true));checks.push('exact_asset_hash_required');
 const packet=await ui.checkedRecordedPacket(raw,descriptor(raw),true);assert.ok(Object.isFrozen(packet)&&Object.isFrozen(packet.fragments));
 const rows=[];
 for(const claim of input.claims){
  const decoded=await ui.decodeRecordedSession(packet,claim.claim_id),opening=JSON.parse(fs.readFileSync(dir+'/'+claim.opening.file)),head=JSON.parse(fs.readFileSync(dir+'/'+claim.head_snapshot.file)),ops=fs.readFileSync(dir+'/'+claim.operations.file);
  assert.deepEqual(decoded.opening,opening);assert.deepEqual(decoded.head_snapshot,head);assert.ok(Buffer.from(decoded.operations).equals(ops));
  const zero=ui.readReplay(decoded.opening,claim.claim_id,0),actual=await ui.checkedAtomicOperationHead(decoded.head_snapshot,decoded.head,zero.replay.replay_start,zero.state),reference=ui.referenceExecution(actual.state),first=JSON.parse(ops.subarray(0,ops.indexOf(10)));
  ui.checkedOperationBinding(first,{...decoded.head,source_roster_sha256:actual.state.source_roster_sha256,rule_set_sha256:reference.rule_set_sha256},zero.replay.replay_start);
  rows.push({claim_id:claim.claim_id,revision:actual.state.revision,exact_decoded_bodies_and_existing_head_start_binding_checks:true});
 }
 checks.push('all_nine_individually_selected_raw_body_and_existing_head_binding_checks');
 const bad=JSON.parse(raw),other=bad.claims[1],first=bad.claims[0].claim_id;
 let root=bad.fragments.push('x')-1;for(let i=0;i<25;i++)root=bad.fragments.push([root,root])-1;
 other.opening.root=root;
 const badBytes=Buffer.from(JSON.stringify(bad)),bounded=await ui.checkedRecordedPacket(badBytes,descriptor(badBytes),true);
 await ui.decodeRecordedSession(bounded,first);checks.push('unselected_exponential_fragment_tree_is_not_expanded');
 await assert.rejects(ui.decodeRecordedSession(bounded,other.claim_id),/exceeds its bound/);checks.push('selected_expansion_rejects_before_exceeding_declared_body_bound');
 const controller=new AbortController();controller.abort();await assert.rejects(ui.decodeRecordedSession(packet,first,controller.signal),/cancelled/);checks.push('aborted_selection_rejected');
 await assert.rejects(ui.decodeRecordedSession(JSON.parse(raw),first),/not verified/);checks.push('unchecked_packet_object_rejected');
 const forward=JSON.parse(raw);forward.fragments.push([forward.fragments.length]);const forwardBytes=Buffer.from(JSON.stringify(forward));await assert.rejects(ui.checkedRecordedPacket(forwardBytes,descriptor(forwardBytes),true),/fragment graph/);checks.push('forward_or_cyclic_reference_rejected');
 const receipt={classification:'Independent pure exported decoder/native fixture checks only; no browser, engine, network, production heads or operation recomputation.',javascript_sha256:sha(fs.readFileSync(source)),packet_sha256:sha(raw),history_kind:'native_fixture',deployment_commit:null,checks,rows};
 fs.writeFileSync(out,JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify({checks:checks.length,selected_native_cases:rows.length,receipt:out}));
})().catch(error=>{console.error(error);process.exitCode=1;});
