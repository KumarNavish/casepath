'use strict';

// Offline lossless packaging of already recorded public response bodies.
// Playback still performs the existing replay/source/operation validators.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const zlib = require('node:zlib');
const {createHash} = require('node:crypto');
const {performance} = require('node:perf_hooks');

const HASH = /^[0-9a-f]{64}$/;
const KINDS = ['opening', 'head_snapshot', 'operations'];
const MAX_BODY_BYTES = 16 * 1024 * 1024;
const sha = bytes => createHash('sha256').update(bytes).digest('hex');

function encodeBodies(bodies) {
  const fragments = [], leaves = new Map(), branches = new Map();
  const leaf = raw => {
    if (!leaves.has(raw)) { leaves.set(raw, fragments.length); fragments.push(raw); }
    return leaves.get(raw);
  };
  const branch = ids => {
    if (ids.length === 1) return ids[0];
    const key = ids.join(',');
    if (!branches.has(key)) { branches.set(key, fragments.length); fragments.push(ids); }
    return branches.get(key);
  };
  const roots = bodies.map(body => {
    const text = new TextDecoder('utf-8', {fatal:true}).decode(body);
    assert.ok(Buffer.from(text).equals(body), 'Response body must preserve exact UTF-8 bytes.');
    const lexemes = /"(?:[^"\\]|\\[\s\S])*"|[{}\[\],:]|[ \t\r\n]+|[^{}\[\],:" \t\r\n]+/gy;
    const stack = [[]];
    let at = 0, match;
    while ((match = lexemes.exec(text))) {
      assert.equal(match.index, at); at = lexemes.lastIndex;
      const raw = match[0];
      if (raw === '{' || raw === '[') stack.push([leaf(raw)]);
      else if (raw === '}' || raw === ']') {
        assert.ok(stack.length > 1);
        const ids = stack.pop(); ids.push(leaf(raw)); stack.at(-1).push(branch(ids));
      } else stack.at(-1).push(leaf(raw));
    }
    assert.equal(at, text.length); assert.equal(stack.length, 1);
    return branch(stack[0]);
  });
  return {fragments, roots};
}

function decodeBodies(packet) {
  const cache = [];
  for (let id = 0; id < packet.fragments.length; id++) {
    const fragment = packet.fragments[id];
    if (typeof fragment === 'string') cache.push(fragment);
    else {
      assert.ok(Array.isArray(fragment) && fragment.every(ref => Number.isSafeInteger(ref) && ref >= 0 && ref < id), 'Fragment references must point backward.');
      cache.push(fragment.map(ref => cache[ref]).join(''));
    }
  }
  return packet.claims.flatMap(claim => KINDS.map(kind => {
    const entry = claim[kind];
    assert.ok(Number.isSafeInteger(entry.root) && entry.root >= 0 && entry.root < cache.length);
    const body = Buffer.from(cache[entry.root]);
    assert.equal(body.length, entry.bytes); assert.equal(sha(body), entry.sha256);
    return {claim_id:claim.claim_id, kind, body};
  }));
}

async function pack(inputPath, outputPath, options = {}) {
  const api = require('../assets/autonomous-workspace-v1.js');
  const allowed = new Set(api.REFERENCE_DEMO_CASES.map(row => row.claim_id));
  const input = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
  assert.equal(input.contract, 'casepath.recorded-session-inputs/1.0.0');
  assert.ok(input.history_kind === 'published_public_synthetic' || options.nativeFixture && input.history_kind === 'native_fixture', 'Native fixtures require the explicit --native-fixture option.');
  assert.ok(input.history_kind === 'native_fixture' ? input.deployment_commit === null : /^[0-9a-f]{40}$/.test(input.deployment_commit));
  assert.ok(Array.isArray(input.claims) && input.claims.length > 0 && input.claims.length <= allowed.size);
  const ids = new Set();
  for (const claim of input.claims) {
    assert.ok(allowed.has(claim.claim_id) && !ids.has(claim.claim_id), 'Only distinct claims from the nine reference histories can be packaged.');
    ids.add(claim.claim_id);
  }
  const selected = input.claims.filter(row => !options.claim || row.claim_id === options.claim);
  assert.ok(selected.length, 'The selected claim is absent from the manifest.');
  const inputDirectory = fs.realpathSync(path.dirname(inputPath));
  const bodies = [], claims = [];
  const started = performance.now();
  for (const claim of selected) {
    assert.ok(Number.isSafeInteger(claim.head?.revision) && claim.head.revision > 0 && HASH.test(claim.head.state_sha256) && HASH.test(claim.head.event_sha256));
    const output = {claim_id:claim.claim_id, head:{revision:claim.head.revision, state_sha256:claim.head.state_sha256, event_sha256:claim.head.event_sha256}};
    const parsed = {};
    for (const kind of KINDS) {
      const entry = claim[kind];
      assert.ok(typeof entry?.file === 'string' && !path.isAbsolute(entry.file));
      const file = fs.realpathSync(path.resolve(inputDirectory, entry.file));
      assert.ok(file.startsWith(inputDirectory + path.sep), 'Inputs must stay inside the manifest directory.');
      assert.ok(Number.isSafeInteger(entry.bytes) && entry.bytes > 0 && entry.bytes <= MAX_BODY_BYTES && HASH.test(entry.sha256));
      assert.equal(fs.statSync(file).size, entry.bytes);
      const body = fs.readFileSync(file), text = new TextDecoder('utf-8', {fatal:true}).decode(body);
      assert.equal(body.length, entry.bytes); assert.equal(sha(body), entry.sha256);
      parsed[kind] = kind === 'operations' ? text.trimEnd().split('\n').map(line => JSON.parse(line)) : JSON.parse(text);
      output[kind] = {bytes:entry.bytes, sha256:entry.sha256, root:bodies.length}; bodies.push(body);
    }
    const opening = api.readReplay(parsed.opening, claim.claim_id, 0);
    const head = {claimId:claim.claim_id, ...output.head};
    assert.equal(parsed.opening.current_revision, head.revision);
    assert.equal(parsed.opening.current_state_sha256, head.state_sha256);
    assert.equal(parsed.opening.current_event_sha256, head.event_sha256);
    const incoming = await api.checkedAtomicOperationHead(parsed.head_snapshot, head, parsed.opening.replay_start, opening.state);
    const reference = api.referenceExecution(incoming.state);
    api.checkedOperationBinding(parsed.operations[0], {...head, source_roster_sha256:incoming.state.source_roster_sha256, rule_set_sha256:reference.rule_set_sha256}, parsed.opening.replay_start);
    const result = parsed.operations.at(-1);
    assert.ok(result?.type === 'result' && result.exact_output_verified === true && result.state_sha256 === head.state_sha256 && result.current_event_sha256 === head.event_sha256, 'The recorded stream must end at its declared verified head.');
    claims.push(output);
  }
  const {fragments, roots} = encodeBodies(bodies);
  for (const claim of claims) for (const kind of KINDS) claim[kind].root = roots[claim[kind].root];
  const packet = {contract:'casepath.recorded-session-packet/1.0.0', deployment_commit:input.deployment_commit, history_kind:input.history_kind, claims, fragments};
  const bytes = Buffer.from(JSON.stringify(packet));
  const packedMs = performance.now() - started, decodeStarted = performance.now();
  const decoded = decodeBodies(packet);
  for (let index = 0; index < bodies.length; index++) assert.ok(decoded[index].body.equals(bodies[index]));
  const decodeAndHashMs = performance.now() - decodeStarted;
  const gzip = zlib.gzipSync(bytes, {level:9, mtime:0});
  const br = zlib.brotliCompressSync(bytes, {params:{[zlib.constants.BROTLI_PARAM_QUALITY]:5, [zlib.constants.BROTLI_PARAM_LGWIN]:24}});
  const receipt = {contract:packet.contract, history_kind:packet.history_kind, deployment_commit:packet.deployment_commit, claims:claims.length,
    body_bytes:bodies.reduce((sum,body) => sum + body.length, 0), packet_bytes:bytes.length, packet_sha256:sha(bytes), gzip9_bytes:gzip.length, br5_bytes:br.length,
    fragments:fragments.length, exact_original_raw_bytes_reconstructed:true, pack_ms:packedMs, decode_and_hash_ms:decodeAndHashMs,
    admission:'Opening, full head, replay start and binding checked. Unchanged operation/checkpoint/result validators also run during playback.',
    frontend_sha256:sha(fs.readFileSync(path.join(__dirname, '../assets/autonomous-workspace-v1.js')))};
  fs.mkdirSync(path.dirname(outputPath), {recursive:true});
  fs.writeFileSync(outputPath, bytes); fs.writeFileSync(outputPath + '.gz', gzip); fs.writeFileSync(outputPath + '.br', br);
  fs.writeFileSync(outputPath + '.receipt.json', JSON.stringify(receipt, null, 2) + '\n');
  return receipt;
}

module.exports = {encodeBodies, decodeBodies, pack};
if (require.main === module) {
  const [input, output, ...flags] = process.argv.slice(2), options = {};
  assert.ok(input && output, 'node casepath/tools/pack_recorded_session.cjs INPUT.json OUTPUT.json [--claim ID] [--native-fixture]');
  for (let i = 0; i < flags.length; i++) {
    if (flags[i] === '--claim') { assert.ok(flags[i + 1]); options.claim = flags[++i]; }
    else if (flags[i] === '--native-fixture') options.nativeFixture = true;
    else throw new Error('Unknown packer option.');
  }
  pack(path.resolve(input), path.resolve(output), options).then(receipt => process.stdout.write(JSON.stringify(receipt) + '\n'), error => { process.stderr.write(error.stack + '\n'); process.exitCode = 1; });
}
