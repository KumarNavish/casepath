'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {gunzipSync} = require('node:zlib');
const {createHash} = require('node:crypto');
const {setTimeout: delay} = require('node:timers/promises');
const {chromium} = require('playwright');

const root = path.resolve(__dirname, '..');
const base = '/api/claim-loops/v1/autonomous';
const captured = JSON.parse(gunzipSync(fs.readFileSync(path.join(root, 'design/evidence-path/recorded-fixtures.json.gz')))).responses;
const historicalIds = captured[`${base}/claims`].claims.map(row => row.claim_id);
const corpusRoot = path.join(root, 'casepath-api/casepath_api/corpora/synthetic-150');
const corpusManifest = JSON.parse(fs.readFileSync(path.join(corpusRoot, 'manifest.json')));
const originals = JSON.parse(fs.readFileSync(path.join(root, 'casepath/assets/corpus-index.json'))).claims;
// Authorized browsing-only projection: case_id/domain/family_id, source manifest
// SHA256 638630886a1d291dfe9009839eb0519130e56700bb4d454277ce2e45c6044f4c.
// It cannot contribute facts or determine a process in these fixtures.
const browsingRows = [
  ["clm_06400c75399e7f37", "defect_mold_heating", "ndg_dad4a5d6a4f7b52bc8e7"],
  ["clm_0b431bbf8391ce3e", "defect_mold_heating", "ndg_5f8a5967e30c99ace5fd"],
  ["clm_0c1a91bc008f8747", "lease_termination_dispute", "ndg_e4b59cb36ee930ff8170"],
  ["clm_0c373e693a363f9e", "rent_increase_dispute", "ndg_37c1682ff2791211ed22"],
  ["clm_0c5e7c7723a3c694", "lease_termination_dispute", "ndg_3a823602ce7bef9d0920"],
  ["clm_0c7beda7583b3558", "rent_increase_dispute", "ndg_df13fa653dbc7412d7fd"],
  ["clm_0e11979130681bd0", "lease_termination_dispute", "ndg_bf5d3883c36c4bfcf46d"],
  ["clm_0e538990cc6ba7ef", "lease_termination_dispute", "ndg_d96952eab1221dc77757"],
  ["clm_0f4f13b1e3e1328c", "lease_termination_dispute", "ndg_4d7a1d77fb07b966ea91"],
  ["clm_1093c1917b109a21", "lease_termination_dispute", "ndg_d96952eab1221dc77757"],
  ["clm_125b6fe2f3cada64", "lease_termination_dispute", "ndg_e4b59cb36ee930ff8170"],
  ["clm_136438c6463a5721", "lease_termination_dispute", "ndg_bf5d3883c36c4bfcf46d"],
  ["clm_14970d755f5b88ed", "defect_mold_heating", "ndg_e19a5fb7f22bc045ee49"],
  ["clm_15dc0a0f31eced5a", "rent_increase_dispute", "ndg_7c7d0384a5ad3f1a5673"],
  ["clm_16ac3b7054d73cc0", "defect_mold_heating", "ndg_2c84c98c26fa701f0b1d"],
  ["clm_1afd6bbf29e6539a", "lease_termination_dispute", "ndg_bf5d3883c36c4bfcf46d"],
  ["clm_1ba0a82246459c6f", "lease_termination_dispute", "ndg_3a823602ce7bef9d0920"],
  ["clm_1bad44cf27f47443", "rent_increase_dispute", "ndg_62ffbe8dcd779ba4d74a"],
  ["clm_1bf3e350283511e5", "lease_termination_dispute", "ndg_d871df8a69082323ee27"],
  ["clm_1e3f5e4acec3ef7f", "defect_mold_heating", "ndg_6f4e3d123af68974a977"],
  ["clm_1e7d16e71afda920", "defect_mold_heating", "ndg_a20d783d19a332fc4aed"],
  ["clm_1f1dffaac057e7e4", "rent_increase_dispute", "ndg_df13fa653dbc7412d7fd"],
  ["clm_24a7ac8c2e07dd51", "defect_mold_heating", "ndg_72ebb23fb65399c57718"],
  ["clm_280ce47169bdff61", "lease_termination_dispute", "ndg_a5c0081018016ea8071e"],
  ["clm_28950c69c5992e15", "rent_increase_dispute", "ndg_62ffbe8dcd779ba4d74a"],
  ["clm_29cfae9067da08bd", "rent_increase_dispute", "ndg_e966d21ab457ae284945"],
  ["clm_2a9c260c26afaa34", "lease_termination_dispute", "ndg_a5c0081018016ea8071e"],
  ["clm_2bfdbc92e9178821", "lease_termination_dispute", "ndg_e4b59cb36ee930ff8170"],
  ["clm_2c55cdd816b1d0e8", "rent_increase_dispute", "ndg_cd00f7dc71077b84ac60"],
  ["clm_2e6d8907d83dae8f", "defect_mold_heating", "ndg_5f8a5967e30c99ace5fd"],
  ["clm_3051e263a9581028", "lease_termination_dispute", "ndg_d871df8a69082323ee27"],
  ["clm_30cac536260351c8", "rent_increase_dispute", "ndg_7c7d0384a5ad3f1a5673"],
  ["clm_314f2d309fea25e6", "defect_mold_heating", "ndg_316158e13ca0984b4ada"],
  ["clm_324cd9e32649ba74", "rent_increase_dispute", "ndg_e52b8cc001ac83b13e21"],
  ["clm_329b8e1bf37554bf", "rent_increase_dispute", "ndg_37c1682ff2791211ed22"],
  ["clm_366b82c3e3dd7442", "rent_increase_dispute", "ndg_127402cafd0644b36fd4"],
  ["clm_37909940906c3d22", "defect_mold_heating", "ndg_1ac923f8ee27f5e78f9f"],
  ["clm_393285577dcb12c4", "lease_termination_dispute", "ndg_4d7a1d77fb07b966ea91"],
  ["clm_3ad3b76f5da143ca", "defect_mold_heating", "ndg_72ebb23fb65399c57718"],
  ["clm_3c803e1aa2da483a", "lease_termination_dispute", "ndg_d871df8a69082323ee27"],
  ["clm_3f3c313482ea5657", "rent_increase_dispute", "ndg_127402cafd0644b36fd4"],
  ["clm_401e7d78a88016c6", "rent_increase_dispute", "ndg_e52b8cc001ac83b13e21"],
  ["clm_4335669eb30c238b", "rent_increase_dispute", "ndg_e966d21ab457ae284945"],
  ["clm_434b9dace61705ce", "defect_mold_heating", "ndg_1ac923f8ee27f5e78f9f"],
  ["clm_44bf2425a1373f3f", "rent_increase_dispute", "ndg_7c7d0384a5ad3f1a5673"],
  ["clm_470f9c19b4ae7713", "defect_mold_heating", "ndg_6f4e3d123af68974a977"],
  ["clm_478488eeea2665d7", "lease_termination_dispute", "ndg_d96952eab1221dc77757"],
  ["clm_4a07dbbbd859a3ce", "defect_mold_heating", "ndg_316158e13ca0984b4ada"],
  ["clm_4a53299cfe619303", "lease_termination_dispute", "ndg_4d7a1d77fb07b966ea91"],
  ["clm_4f7e346be88ed820", "rent_increase_dispute", "ndg_b77d75fed7009b7639d1"],
  ["clm_4fc7750e99cdf8fe", "defect_mold_heating", "ndg_a20d783d19a332fc4aed"],
  ["clm_505e3fc9e90f61fa", "defect_mold_heating", "ndg_2c84c98c26fa701f0b1d"],
  ["clm_5156de89a4189cd1", "defect_mold_heating", "ndg_2c84c98c26fa701f0b1d"],
  ["clm_521c20913f4e0f9b", "defect_mold_heating", "ndg_5f8a5967e30c99ace5fd"],
  ["clm_526d6c802e28b1da", "lease_termination_dispute", "ndg_bf5d3883c36c4bfcf46d"],
  ["clm_53b7982ac9bc1a95", "defect_mold_heating", "ndg_5f8a5967e30c99ace5fd"],
  ["clm_53e9ef7917c4ae36", "defect_mold_heating", "ndg_1ac923f8ee27f5e78f9f"],
  ["clm_543f08f2415b2a33", "rent_increase_dispute", "ndg_cd00f7dc71077b84ac60"],
  ["clm_58a690d3e8748a6d", "rent_increase_dispute", "ndg_e966d21ab457ae284945"],
  ["clm_5a25bfdab3e98a61", "lease_termination_dispute", "ndg_e4b59cb36ee930ff8170"],
  ["clm_5ada7e71f6f329e1", "defect_mold_heating", "ndg_6f4e3d123af68974a977"],
  ["clm_5c6863b143c9c001", "rent_increase_dispute", "ndg_e966d21ab457ae284945"],
  ["clm_5e2271e9b416dd22", "rent_increase_dispute", "ndg_b77d75fed7009b7639d1"],
  ["clm_5f1fbce88f6e5a92", "defect_mold_heating", "ndg_e19a5fb7f22bc045ee49"],
  ["clm_64a401e6678f4871", "rent_increase_dispute", "ndg_e966d21ab457ae284945"],
  ["clm_672f2604d8f44888", "defect_mold_heating", "ndg_72ebb23fb65399c57718"],
  ["clm_6e2d3a5178b4bce5", "lease_termination_dispute", "ndg_e4b59cb36ee930ff8170"],
  ["clm_6ecae3f11685e3b2", "rent_increase_dispute", "ndg_df13fa653dbc7412d7fd"],
  ["clm_6f04d0907ecb96bb", "rent_increase_dispute", "ndg_4d4dcce6ba3807cfa53f"],
  ["clm_7078fe1804ad03cc", "rent_increase_dispute", "ndg_7c7d0384a5ad3f1a5673"],
  ["clm_7108870bd133fed4", "defect_mold_heating", "ndg_d458b9a62149384aecee"],
  ["clm_7255037b122de8a3", "lease_termination_dispute", "ndg_a5c0081018016ea8071e"],
  ["clm_72b3020bfe3de742", "lease_termination_dispute", "ndg_4d7a1d77fb07b966ea91"],
  ["clm_731b214dde882f89", "defect_mold_heating", "ndg_e19a5fb7f22bc045ee49"],
  ["clm_76238b1a82b5c877", "rent_increase_dispute", "ndg_7c7d0384a5ad3f1a5673"],
  ["clm_79beea0ce763d9b8", "lease_termination_dispute", "ndg_1c5cbeb1c457c4dc97ef"],
  ["clm_7ac806bd30792cfb", "defect_mold_heating", "ndg_dad4a5d6a4f7b52bc8e7"],
  ["clm_7ace38ce2814fdb9", "rent_increase_dispute", "ndg_e52b8cc001ac83b13e21"],
  ["clm_7b92cc30892368b3", "defect_mold_heating", "ndg_d458b9a62149384aecee"],
  ["clm_7db24a8ce46c8c50", "lease_termination_dispute", "ndg_a5c0081018016ea8071e"],
  ["clm_7dbd7c7d1c4ddf90", "rent_increase_dispute", "ndg_cd00f7dc71077b84ac60"],
  ["clm_7eb9780fa5d65658", "defect_mold_heating", "ndg_1ac923f8ee27f5e78f9f"],
  ["clm_8167911d95e79fdb", "lease_termination_dispute", "ndg_3a823602ce7bef9d0920"],
  ["clm_8b7fca3c1704e47f", "defect_mold_heating", "ndg_72ebb23fb65399c57718"],
  ["clm_8f8de9368e97ca31", "lease_termination_dispute", "ndg_4d7a1d77fb07b966ea91"],
  ["clm_92264ed30ac9bc8d", "defect_mold_heating", "ndg_a20d783d19a332fc4aed"],
  ["clm_93efa6c5f16b2da5", "rent_increase_dispute", "ndg_b77d75fed7009b7639d1"],
  ["clm_95d08975bc575592", "defect_mold_heating", "ndg_316158e13ca0984b4ada"],
  ["clm_97f495fcbee20c74", "lease_termination_dispute", "ndg_4d7a1d77fb07b966ea91"],
  ["clm_99188a578845347c", "defect_mold_heating", "ndg_dad4a5d6a4f7b52bc8e7"],
  ["clm_99cc6719f9923d03", "rent_increase_dispute", "ndg_37c1682ff2791211ed22"],
  ["clm_9a179a4481767d43", "rent_increase_dispute", "ndg_4d4dcce6ba3807cfa53f"],
  ["clm_9c83b12ba8dfce68", "defect_mold_heating", "ndg_dad4a5d6a4f7b52bc8e7"],
  ["clm_9fc9c41746bca87d", "defect_mold_heating", "ndg_6f4e3d123af68974a977"],
  ["clm_a31f0d7e70441f32", "lease_termination_dispute", "ndg_a5c0081018016ea8071e"],
  ["clm_a44c2ac127c942c8", "lease_termination_dispute", "ndg_d96952eab1221dc77757"],
  ["clm_a601453abb9b2e32", "lease_termination_dispute", "ndg_d871df8a69082323ee27"],
  ["clm_a62c178195d21648", "defect_mold_heating", "ndg_6f4e3d123af68974a977"],
  ["clm_a91f0e5c3e7df086", "lease_termination_dispute", "ndg_d871df8a69082323ee27"],
  ["clm_ab8afc6b0ad3b9e4", "lease_termination_dispute", "ndg_e4b59cb36ee930ff8170"],
  ["clm_aba6faab059a697e", "lease_termination_dispute", "ndg_bf5d3883c36c4bfcf46d"],
  ["clm_ac7d7a08ca8d5a55", "rent_increase_dispute", "ndg_62ffbe8dcd779ba4d74a"],
  ["clm_aeab1f696a63e3f4", "lease_termination_dispute", "ndg_a5c0081018016ea8071e"],
  ["clm_af5b8495ef298d23", "lease_termination_dispute", "ndg_3a823602ce7bef9d0920"],
  ["clm_b14c5e2b8f9620a8", "lease_termination_dispute", "ndg_1c5cbeb1c457c4dc97ef"],
  ["clm_bbe4806aa3607ee3", "defect_mold_heating", "ndg_316158e13ca0984b4ada"],
  ["clm_bd74de2a73d9e05a", "rent_increase_dispute", "ndg_37c1682ff2791211ed22"],
  ["clm_bdb9322222de3810", "rent_increase_dispute", "ndg_cd00f7dc71077b84ac60"],
  ["clm_bfbb1a8f3fc58156", "defect_mold_heating", "ndg_dad4a5d6a4f7b52bc8e7"],
  ["clm_c10b97ecdfea47f5", "defect_mold_heating", "ndg_2c84c98c26fa701f0b1d"],
  ["clm_c138c15d0886b345", "lease_termination_dispute", "ndg_3a823602ce7bef9d0920"],
  ["clm_c44ddc0914ba9298", "rent_increase_dispute", "ndg_df13fa653dbc7412d7fd"],
  ["clm_c50db5a1837bf4e3", "defect_mold_heating", "ndg_5f8a5967e30c99ace5fd"],
  ["clm_c683ace4cb02ccb3", "defect_mold_heating", "ndg_72ebb23fb65399c57718"],
  ["clm_c7ffe208c9390ad5", "rent_increase_dispute", "ndg_127402cafd0644b36fd4"],
  ["clm_c8b46247757abe15", "rent_increase_dispute", "ndg_62ffbe8dcd779ba4d74a"],
  ["clm_c9029af5de9fa5a6", "rent_increase_dispute", "ndg_e52b8cc001ac83b13e21"],
  ["clm_c9a03c7ad06533fb", "lease_termination_dispute", "ndg_1c5cbeb1c457c4dc97ef"],
  ["clm_cbfda394bc5fc2d3", "rent_increase_dispute", "ndg_b77d75fed7009b7639d1"],
  ["clm_cdfdac3cdf7f809a", "defect_mold_heating", "ndg_d458b9a62149384aecee"],
  ["clm_cf91859f633a8189", "rent_increase_dispute", "ndg_127402cafd0644b36fd4"],
  ["clm_d830a8410fe8c94a", "defect_mold_heating", "ndg_e19a5fb7f22bc045ee49"],
  ["clm_da6786a395031f3a", "defect_mold_heating", "ndg_d458b9a62149384aecee"],
  ["clm_de7ddb30509c2358", "rent_increase_dispute", "ndg_4d4dcce6ba3807cfa53f"],
  ["clm_df9fc7fa4ca80f6d", "defect_mold_heating", "ndg_d458b9a62149384aecee"],
  ["clm_e262801f9368bc12", "defect_mold_heating", "ndg_1ac923f8ee27f5e78f9f"],
  ["clm_e331d769683c8207", "lease_termination_dispute", "ndg_a5c0081018016ea8071e"],
  ["clm_e3e0212c8bdc4fb5", "lease_termination_dispute", "ndg_bf5d3883c36c4bfcf46d"],
  ["clm_e4a8342461b8cf79", "rent_increase_dispute", "ndg_62ffbe8dcd779ba4d74a"],
  ["clm_e790e7cc236593e3", "lease_termination_dispute", "ndg_1c5cbeb1c457c4dc97ef"],
  ["clm_e9ab4f62e362fee3", "lease_termination_dispute", "ndg_1c5cbeb1c457c4dc97ef"],
  ["clm_ec246327ccda00a0", "lease_termination_dispute", "ndg_bf5d3883c36c4bfcf46d"],
  ["clm_ee0cd23eb1730f9d", "rent_increase_dispute", "ndg_127402cafd0644b36fd4"],
  ["clm_ee29ac770b1bf7b9", "defect_mold_heating", "ndg_2c84c98c26fa701f0b1d"],
  ["clm_ee6628dbc9cd16ff", "rent_increase_dispute", "ndg_df13fa653dbc7412d7fd"],
  ["clm_f14f53b1f55c294f", "lease_termination_dispute", "ndg_1c5cbeb1c457c4dc97ef"],
  ["clm_f58dd10e77d46554", "defect_mold_heating", "ndg_316158e13ca0984b4ada"],
  ["clm_f69b1747447bc221", "lease_termination_dispute", "ndg_d96952eab1221dc77757"],
  ["clm_f7cd8b8d07f8c933", "rent_increase_dispute", "ndg_e52b8cc001ac83b13e21"],
  ["clm_f8d04bdabc36bfe8", "rent_increase_dispute", "ndg_b77d75fed7009b7639d1"],
  ["clm_fa340390e701525c", "defect_mold_heating", "ndg_a20d783d19a332fc4aed"],
  ["clm_fc3fad19cc8db954", "defect_mold_heating", "ndg_e19a5fb7f22bc045ee49"],
  ["clm_fc970e956872f431", "rent_increase_dispute", "ndg_4d4dcce6ba3807cfa53f"],
  ["clm_fd22c426938b6320", "lease_termination_dispute", "ndg_3a823602ce7bef9d0920"],
  ["clm_fd68e3dbacb17a8e", "lease_termination_dispute", "ndg_d96952eab1221dc77757"],
  ["clm_fd8e5004c663cecb", "rent_increase_dispute", "ndg_37c1682ff2791211ed22"],
  ["clm_fded14caf513a043", "lease_termination_dispute", "ndg_d871df8a69082323ee27"],
  ["clm_fe259be188154a0c", "defect_mold_heating", "ndg_a20d783d19a332fc4aed"],
  ["clm_fe914f68772c8f3b", "rent_increase_dispute", "ndg_cd00f7dc71077b84ac60"],
  ["clm_ff0434f401f4c442", "rent_increase_dispute", "ndg_4d4dcce6ba3807cfa53f"]
];
const browsing = new Map(browsingRows.map(([id, domain, family_id]) => [id, {domain, family_id, browsing_only: true}]));
// Deliberately independent of the production DEMO_CASES export. A roster change
// must not silently make its own regression assertion pass.
const demoIds = [
  'clm_e262801f9368bc12', 'clm_521c20913f4e0f9b', 'clm_ee29ac770b1bf7b9',
  'clm_f69b1747447bc221', 'clm_0c5e7c7723a3c694', 'clm_2a9c260c26afaa34',
  'clm_c44ddc0914ba9298', 'clm_7dbd7c7d1c4ddf90', 'clm_9a179a4481767d43',
];
const processedId = historicalIds[3];
const otherId = historicalIds[4];
const unprocessedId = demoIds[3];
const jpegBinding = corpusManifest.claims.find(row => row.observable_artifacts.some(source => source.media_type === 'image/jpeg'));
const jpegDescriptor = jpegBinding.observable_artifacts.find(source => source.media_type === 'image/jpeg');
const sha = value => createHash('sha256').update(value).digest('hex');
const sorted = values => [...values].sort();
const clone = value => structuredClone(value);
const canonical = value => Array.isArray(value)
  ? `[${value.map(canonical).join(',')}]`
  : value && typeof value === 'object'
    ? `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`
    : JSON.stringify(value);

function processedEnvelope(id, recordedId) {
  const envelope = clone(captured[`${base}/claims/${recordedId}`]);
  envelope.state.claim_id = id;
  envelope.state.graph.claim_id = id;
  envelope.state.source_descriptors.forEach(source => { source.claim_id = id; });
  Object.assign(envelope.projection, {
    claim_id: id, revision: envelope.state.revision, state_sha256: envelope.state.state_sha256,
    parent_revision: envelope.state.revision, parent_state_sha256: envelope.state.state_sha256,
  });
  return envelope;
}

function unprocessedEnvelope(original, binding) {
  const id = original.claim_id, message = original.message;
  const state = {
    claim_id: id, title: original.subject, origin: 'canonical_original', browse_metadata: browsing.get(id),
    mode: 'unprocessed', status: 'not_started', phase: 'not_run', phase_summary: '',
    revision: 0, state_sha256: sha(`unprocessed fixture ${id}`),
    message, source_preview: {text: message},
    graph: null, evaluation: null, facts: [], obligations: [], actions: [], results: [],
    outcome: null, deferral: null, acquired_sources: [], knowledge_uses: [], knowledge_published: [],
    source_descriptors: binding.observable_artifacts.map(source => ({...source, claim_id: id})),
  };
  return {state, projection: {claim_id: id, revision: 0, state_sha256: state.state_sha256}};
}

function fixtureData(config = {}) {
  const envelopes = {}, sources = {}, rawSources = {};
  for (const original of originals) {
    const id = original.claim_id, binding = corpusManifest.claims.find(row => row.claim_id === id);
    const envelope = unprocessedEnvelope(original, binding);
    envelopes[id] = envelope;
    for (const source of envelope.state.source_descriptors) {
      const message = source.role === 'customer_message', text = message ? envelope.state.message : '';
      const preview = {...source, text_sha256: sha(text), text, complete: message,
        extraction: message ? 'message_body_projection' : 'unsupported_metadata', coverage: {limitation: message ? null : 'unsupported_visual_content'},
        preview_only: true, evidence_admitted: false};
      preview.preview_sha256 = sha(canonical(preview));
      sources[`${id}/${source.artifact_id}`] = preview;
      if (config.jpeg && id === jpegBinding.claim_id && source.artifact_id === jpegDescriptor.artifact_id) {
        rawSources[`${id}/${source.artifact_id}`] = fs.readFileSync(path.join(corpusRoot, source.path)).toString('base64');
      }
    }
  }
  historicalIds.forEach(id => {
    envelopes[id] = processedEnvelope(id, id);
    envelopes[id].state.origin = 'native_intake';
    for (const descriptor of envelopes[id].state.source_descriptors) {
      const recorded = captured[`${base}/sources/${id}/${descriptor.artifact_id}/text`];
      if (recorded) sources[`${id}/${descriptor.artifact_id}`] = clone(recorded);
    }
  });
  const acceptedHistories = {};
  if (config.presentationSuite) for (const id of demoIds) {
    const original = clone(envelopes[id]);
    acceptedHistories[id] = [original, ...[1, 2].map(revision => {
      const state = {...clone(original.state), revision, state_sha256: sha(`accepted fixture ${id} revision ${revision}`),
        last_event_sha256: sha(`accepted fixture ${id} event ${revision}`), mode: 'started',
        status: revision === 1 ? 'running' : 'completed', phase: revision === 1 ? 'acquiring' : 'complete',
        graph: {claim_id: id, title: 'Deterministic source inspection fixture', graph_sha256: sha(`fixture graph ${id}`),
          nodes: [{node_id: 'inspect_packet', label: 'Inspect original packet', entry: true}], edges: []},
        evaluation: {nodes: [{node_id: 'inspect_packet', execution_state: revision === 1 ? 'ready' : 'completed'}], edges: [], documents: []}};
      return {state, projection: {claim_id: id, revision, state_sha256: state.state_sha256}};
    })];
    if (config.presentationSuite === 'replay') envelopes[id] = clone(acceptedHistories[id][2]);
  }
  if (config.completeStatuses) ['completed', 'complete', 'resolved'].forEach((status, index) => { envelopes[historicalIds[index]].state.status = status; });
  const rows = Object.values(envelopes).map(({state}) => ({
    claim_id: state.claim_id, title: state.title, origin: state.origin, mode: state.mode, status: state.status,
    phase: state.phase, phase_summary: state.phase_summary, revision: state.revision,
    state_sha256: state.state_sha256, outcome: state.outcome,
    source_preview: state.source_preview, browse_metadata: state.browse_metadata || {},
  }));
  assert.equal(rows.filter(row => row.origin === 'canonical_original').length, 150);
  assert.equal(rows.filter(row => row.origin === 'native_intake').length, 9);
  return {envelopes, sources, rawSources, acceptedHistories, rows: config.rememberedNativeId ? rows.filter(row => row.claim_id !== config.rememberedNativeId) : rows};
}

let browser;
test.before(async () => {
  browser = await chromium.launch({
    executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH || '/usr/bin/chromium',
    headless: true, args: ['--no-sandbox'],
  });
});
test.after(async () => { await browser?.close(); });

async function eventually(read, message, timeout = 5000) {
  const deadline = Date.now() + timeout;
  do {
    if (await read()) return;
    await delay(10);
  } while (Date.now() < deadline);
  assert.fail(message);
}

async function fixturePage(t, config = {}) {
  const context = await browser.newContext({viewport: {width: config.width || 1440, height: config.height || 1000}, serviceWorkers: 'block'});
  const page = await context.newPage(), errors = [], network = [];
  page.on('pageerror', error => errors.push(error.message));
  t.after(async () => {
    const writes = await page.evaluate(() => window.__fixture?.calls.filter(call => call.method !== 'GET') || []);
    const startViolations = await page.evaluate(() => window.__fixture?.startViolations || []);
    await page.evaluate(() => window.__controller?.destroy());
    await context.close();
    if (config.originalStartId || config.presentationSuite === 'live') {
      const allowed = config.originalStartId ? [config.originalStartId] : demoIds;
      assert.ok(writes.every(call => call.method === 'POST' && allowed.some(id => call.url === `${base}/claims/${id}/start`)), 'only the explicitly configured Start POST is permitted');
      assert.deepEqual(startViolations, [], 'every mocked Start must carry the original guard and unchanged retry identity');
    } else assert.deepEqual(writes, [], 'opening and browsing product views must not write');
    assert.deepEqual(errors, [], 'production controller browser errors');
    assert.ok(network.every(request => request.method === 'GET'), 'browser requests cannot write');
    assert.equal(network.filter(request => request.url.includes('/api/')).length, 0, 'the API fixture must remain entirely local');
  });
  // The only document is fulfilled in memory. Every actual asset/API/provider
  // request is blocked; the response seam below never uses the network. The
  // original-start scenario alone permits its explicitly guarded mock POST.
  await page.route('**/*', route => {
    network.push({url: route.request().url(), method: route.request().method()});
    return route.request().isNavigationRequest()
      ? route.fulfill({status: 200, contentType: 'text/html', body: '<!doctype html><html><head><meta charset="utf-8"></head><body><main id="workspace"></main></body></html>'})
      : route.abort('blockedbyclient');
  });
  await page.goto('http://localhost:41999/');
  const time = new Date('2026-10-09T12:00:00Z');
  await page.clock.install({time});
  await page.clock.pauseAt(time);
  await mountFixture(page, config);
  return page;
}

async function mountFixture(page, config = {}) {
  await page.addStyleTag({path: path.join(root, 'casepath/assets/autonomous-workspace-v1.css')});
  await page.addScriptTag({path: path.join(root, 'casepath/assets/autonomous-workspace-v1.js')});
  await page.evaluate(({data, config, base}) => {
    window.__fixture = {...data, ...config, calls: [], held: [], splitRevision: {}, startPosts: 0, startViolations: [], suitePosts: {}, suiteReads: {}};
    const fixture = window.__fixture;
    const originalStart = fixture.originalStartId ? structuredClone(fixture.envelopes[fixture.originalStartId]) : null;
    const response = (status, body) => ({ok: status >= 200 && status < 300, status, json: async () => structuredClone(body)});
    const advance = id => {
      const envelope = fixture.envelopes[id];
      envelope.state.revision++;
      envelope.state.state_sha256 = (envelope.state.revision % 16).toString(16).repeat(64);
      envelope.state.last_event_sha256 = ((envelope.state.revision + 1) % 16).toString(16).repeat(64);
      Object.assign(envelope.projection, {
        claim_id: id, revision: envelope.state.revision, state_sha256: envelope.state.state_sha256,
        parent_revision: envelope.state.revision, parent_state_sha256: envelope.state.state_sha256,
      });
      return envelope;
    };
    fixture.advance = advance;
    const batch = (state, after) => ({
      events: Array.from({length: Math.max(0, state.revision - after)}, (_, index) => {
        const seq = after + index + 1;
        const accepted = fixture.acceptedHistories[state.claim_id]?.[seq]?.state;
        return {seq, claim_id: state.claim_id, revision: seq, state_sha256: accepted?.state_sha256 || (seq === state.revision ? state.state_sha256 : 'e'.repeat(64)), event_sha256: accepted?.last_event_sha256 || (seq === state.revision ? state.last_event_sha256 : 'd'.repeat(64)), kind: seq === 1 ? 'intake' : 'work.phase', payload: {summary: 'Deterministic browser fixture revision'}};
      }),
      current_revision: state.revision, current_state_sha256: state.state_sha256,
      cursor_sha256: state.revision === 0 ? null : state.last_event_sha256,
    });
    const fetch = async (url, init = {}) => {
      const parsed = new URL(String(url), location.origin), method = init.method || 'GET';
      fixture.calls.push({url: parsed.pathname + parsed.search, method, time: performance.now(), body: init.body, headers: init.headers || {}});
      const relative = parsed.pathname.slice(base.length);
      const suiteStart = relative.match(/^\/claims\/([^/]+)\/start$/);
      if (method === 'POST' && fixture.presentationSuite === 'live' && suiteStart && fixture.acceptedHistories[suiteStart[1]]) {
        const id = suiteStart[1], original = fixture.acceptedHistories[id][0], body = JSON.parse(init.body), headers = init.headers || {};
        if (body.expected_revision !== 0 || body.expected_state_sha256 !== original.state.state_sha256 || !body.idempotency_key?.startsWith('browser.')
          || headers['X-CasePath-Agent-Work'] !== '1' || headers['Content-Type'] !== 'application/json' || fixture.suitePosts[id]) {
          fixture.startViolations.push('A presentation Start was duplicated or changed its original guard.');
          return response(422, {detail: 'Invalid deterministic presentation Start.'});
        }
        fixture.suitePosts[id] = 1;
        fixture.envelopes[id] = structuredClone(fixture.acceptedHistories[id][1]);
        return response(200, fixture.envelopes[id]);
      }
      if (method === 'POST' && originalStart && relative === `/claims/${fixture.originalStartId}/start`) {
        const body = JSON.parse(init.body), headers = init.headers || {};
        const correct = body.expected_revision === 0 && body.expected_state_sha256 === originalStart.state.state_sha256
          && typeof body.idempotency_key === 'string' && body.idempotency_key.startsWith('browser.')
          && headers['X-CasePath-Agent-Work'] === '1' && headers['Content-Type'] === 'application/json'
          && (!fixture.firstStartBody || init.body === fixture.firstStartBody);
        if (!correct) {
          fixture.startViolations.push('Start guard, intent header or retry body changed.');
          return response(422, {detail: 'Start fixture rejected a changed guard or retry identity.'});
        }
        fixture.startPosts++;
        fixture.firstStartBody ||= init.body;
        // The first request is accepted at revision 1, but its response is lost.
        // Background reads can observe acceptance while the browser retains
        // the unconfirmed original guard and idempotency key.
        const state = {...structuredClone(originalStart.state), mode: 'started', status: 'running', phase: 'acquiring',
          revision: 1, state_sha256: '1'.repeat(64), last_event_sha256: '2'.repeat(64),
          graph: {claim_id: fixture.originalStartId, title: 'Original packet investigation', graph_sha256: '3'.repeat(64),
            nodes: [{node_id: 'investigate_packet', label: 'Inspect original packet', entry: true}], edges: []},
          evaluation: {nodes: [{node_id: 'investigate_packet', execution_state: 'ready'}], edges: [], documents: []}};
        const envelope = {state, projection: {claim_id: state.claim_id, revision: 1, state_sha256: state.state_sha256}};
        const accepted = structuredClone(envelope);
        fixture.envelopes[state.claim_id] = envelope;
        if (fixture.startPosts === 1) throw new TypeError('Isolated Start network outcome is uncertain.');
        // The explicit retry returns the same accepted result. A concurrent
        // writer advances the live head before the follow-up snapshot.
        advance(state.claim_id);
        return response(200, accepted);
      }
      if (method !== 'GET') return response(405, {detail: 'This browser fixture prohibits writes.'});
      if (relative === '/claims') {
        const limit = Number(parsed.searchParams.get('limit') || 50), offset = Number(parsed.searchParams.get('offset') || 0);
        if (fixture.holdCollections) return new Promise(resolve => fixture.held.push({id: 'collection', release: () => resolve(response(200, {claims: fixture.rows.slice(offset, offset + limit), total: fixture.rows.length, limit, offset}))}));
        return response(200, {claims: fixture.rows.slice(offset, offset + limit), total: fixture.rows.length, limit, offset});
      }
      if (relative === '/knowledge') return response(200, {versions: [], uses: [], quarantined: []});
      if (relative === '/status') return response(200, {enabled: true, provider_ready: fixture.providerReady ?? Boolean(fixture.originalStartId || fixture.presentationSuite === 'live')});
      const rawSource = relative.match(/^\/sources\/([^/]+)\/([^/]+)$/);
      if (rawSource && fixture.rawSources[`${rawSource[1]}/${rawSource[2]}`]) {
        const raw = fixture.rawSources[`${rawSource[1]}/${rawSource[2]}`];
        return {ok: true, status: 200, arrayBuffer: async () => Uint8Array.from(atob(raw), char => char.charCodeAt(0)).buffer};
      }
      const source = relative.match(/^\/sources\/([^/]+)\/([^/]+)\/(?:text|preview)$/);
      if (source) return response(fixture.sources[`${source[1]}/${source[2]}`] ? 200 : 404, fixture.sources[`${source[1]}/${source[2]}`] || {detail: 'No source in this fixture.'});
      const read = relative.match(/^\/claims\/([^/]+)(?:\/(snapshot|events|replay))?$/);
      if (!read || !fixture.envelopes[read[1]]) return response(404, {detail: 'No GET response in this fixture.'});
      const [, id, kind] = read, after = Number(parsed.searchParams.get('after') || 0);
      if (kind === 'replay') {
        const live = fixture.envelopes[id], through = Number(parsed.searchParams.get('through_seq') || 0);
        const envelope = structuredClone(fixture.acceptedHistories[id]?.[through] || live), state = envelope.state;
        state.revision = through;
        if (!fixture.acceptedHistories[id]) {
          state.state_sha256 = through === live.state.revision ? live.state.state_sha256 : (through % 16).toString(16).repeat(64);
          state.last_event_sha256 = through === live.state.revision ? live.state.last_event_sha256 ?? null : through === 0 ? null : ((through + 1) % 16).toString(16).repeat(64);
          state.status = fixture.replayStatus || 'running';
        }
        if (through === 0) Object.assign(state, {mode: 'unprocessed', status: 'not_started', phase: 'not_run', graph: null, evaluation: null, facts: [], obligations: [], actions: [], acquired_sources: [], outcome: null, deferral: null});
        Object.assign(envelope.projection, {claim_id: id, revision: through, state_sha256: state.state_sha256, parent_revision: through, parent_state_sha256: state.state_sha256});
        const provenance = {claim_id: id, prefix_revision: through, fixture: 'deterministic accepted prefix',
          sources: structuredClone(state.source_descriptors), source_map: structuredClone(state.original_binding?.source_map || []),
          rule_pack_sha256: [...new Set((state.receipts || []).map(row => row.receipt?.rule_pack_sha256).filter(Boolean))].sort()};
        for (const [field, stateField] of [['source_roster_sha256', 'source_roster_sha256'], ['policy_id', 'policy_id'], ['run_id', 'run_id'], ['event_sha256', 'last_event_sha256']]) {
          if (state[stateField] !== undefined) provenance[field] = state[stateField];
        }
        for (const field of ['original_binding_sha256', 'claim_binding_sha256', 'corpus_manifest_sha256', 'static_template_sha256']) {
          if (state.original_binding?.[field] !== undefined) provenance[field] = state.original_binding[field];
        }
        const currentEvent = live.state.revision === 0 ? null : live.state.last_event_sha256;
        const replay = {...envelope, ...batch(state, 0), mode: 'replay', replay_only: true, through_seq: through,
          current_revision: live.state.revision, current_state_sha256: live.state.state_sha256, current_event_sha256: currentEvent,
          current_head: {revision: live.state.revision, state_sha256: live.state.state_sha256, event_sha256: currentEvent}, provenance};
        if (fixture.holdReplayId === id && through === fixture.holdReplayThrough) {
          return new Promise(resolve => fixture.held.push({id, kind: 'replay', release: () => resolve(response(200, replay))}));
        }
        return response(200, replay);
      }
      if (kind === 'snapshot') {
        if (fixture.presentationSuite === 'live' && fixture.suitePosts[id] && (fixture.suiteReads[id] = (fixture.suiteReads[id] || 0) + 1) >= 2) fixture.envelopes[id] = structuredClone(fixture.acceptedHistories[id][2]);
        if (fixture.snapshotStatus && fixture.snapshotStatus !== 200) return response(fixture.snapshotStatus, {detail: 'Configured snapshot transport response.'});
        const envelope = structuredClone(fixture.envelopes[id]);
        if (fixture.conflictingHash) {
          envelope.state.state_sha256 = '0'.repeat(64);
          Object.assign(envelope.projection, {state_sha256: envelope.state.state_sha256, parent_state_sha256: envelope.state.state_sha256});
        }
        const snapshot = {...envelope, ...batch(envelope.state, after)};
        if (fixture.atomicWriter) advance(id); // writer runs after the complete read was captured
        if (fixture.mismatchedSnapshots > 0) { fixture.mismatchedSnapshots--; snapshot.current_revision++; }
        if (fixture.corruptProjection) snapshot.projection.state_sha256 = '0'.repeat(64);
        if (fixture.holdId === id && (fixture.holdRemaining === undefined || fixture.holdRemaining > 0)) {
          if (fixture.holdRemaining !== undefined) fixture.holdRemaining--;
          return new Promise(resolve => fixture.held.push({id, release: () => resolve(response(200, snapshot))}));
        }
        return response(200, snapshot);
      }
      if (!kind) {
        if (fixture.splitWriter) advance(id);
        return response(200, fixture.envelopes[id]);
      }
      if (fixture.splitWriter) advance(id); // a writer advances between the legacy pair
      const events = batch(fixture.envelopes[id].state, after);
      if (fixture.corruptLegacyHash) events.current_state_sha256 = '0'.repeat(64);
      return response(200, events);
    };
    window.__controller = window.CasePathAutonomous.mount(document.querySelector('#workspace'), {fetch});
  }, {data: fixtureData(config), config, base});
  const hash = new URL(page.url()).hash;
  if (hash.startsWith('#autonomous/claim/')) await eventually(() => page.locator('[data-au-claim-title]').count().then(count => count === 1), 'the reloaded claim did not render');
  else {
    const expectedRows = hash.includes('scope=added') ? config.rememberedNativeId ? 8 : 9 : 150;
    await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === expectedRows), 'Cases did not load the requested fixture scope');
  }
  return page;
}

const calls = (page, suffix) => page.evaluate(suffix => window.__fixture.calls.filter(call => new URL(call.url, location.origin).pathname.endsWith(suffix)), suffix);
async function open(page, id) {
  await page.evaluate(id => { void window.__controller.openClaim(id); }, id);
}
async function title(page, id) {
  await eventually(async () => {
    const rendered = await page.locator('[data-au-claim-title]').count() ? await page.locator('[data-au-claim-title]').textContent() : null;
    const expected = await page.evaluate(id => window.__fixture.envelopes[id].state.title, id);
    return rendered === expected;
  }, `The matching saved claim ${id} did not render`);
}

test('Cases pages all 150 IDs and Demonstration contains exactly the nine canonical Cases IDs', async t => {
  const page = await fixturePage(t);
  const actual = await page.locator('[data-au-claim-row]').evaluateAll(rows => rows.map(row => row.dataset.auClaimRow));
  const expected = await page.evaluate(() => window.__fixture.rows.filter(row => row.origin === 'canonical_original').map(row => row.claim_id));
  assert.equal(new Set(actual).size, 150);
  assert.deepEqual(sorted(actual), sorted(expected));
  const collectionCalls = await calls(page, '/claims');
  assert.ok(collectionCalls.length >= 2, 'a 50-row first page must cause another collection read');
  let nextOffset = 0;
  for (const call of collectionCalls) {
    const params = new URL(call.url, 'http://fixture.invalid').searchParams;
    assert.equal(Number(params.get('offset') || 0), nextOffset, 'collection pages must not skip or repeat rows');
    nextOffset += Math.min(Number(params.get('limit') || 50), 159 - nextOffset);
  }
  assert.equal(nextOffset, 159, 'all original and added histories must be read before applying the collection scope');
  await page.locator('.au-nav [data-au-nav="work"]').click();
  assert.equal(new URL(page.url()).hash, '#autonomous/cases');
  await page.locator('.au-nav [data-au-nav="demonstration"]').click();
  await eventually(() => page.locator('[data-au-demo-case]').count().then(count => count === 9), 'Demonstration did not render exactly nine cases');
  const demo = await page.locator('[data-au-demo-case]').evaluateAll(rows => rows.map(row => row.dataset.auDemoCase));
  assert.deepEqual(sorted(demo), sorted(demoIds));
  assert.ok(demo.every(id => actual.includes(id)), 'demonstrations must refer to Cases identities');
  assert.ok(demo.every(id => !historicalIds.includes(id)), 'historical autonomous captures cannot become demonstration members');
  assert.equal(new URL(page.url()).hash.split('?')[0], '#autonomous/demonstration');
  assert.equal(await page.locator('[data-au-demo-mode="replay"]').getAttribute('aria-pressed'), 'true');
  await page.locator('[data-au-demo-mode="live"]').click();
  assert.equal(await page.locator('[data-au-demo-mode="live"]').getAttribute('aria-pressed'), 'true');
  await page.locator('[data-au-demo-mode="replay"]').click();
  assert.equal(await page.locator('[data-au-demo-mode="replay"]').getAttribute('aria-pressed'), 'true');
  await page.evaluate(() => { location.hash = '#autonomous/work'; });
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 150), 'The prior Work route did not resolve to Cases');
});

test('the 150 originals and nine added histories retain distinct scopes through hash navigation and reload', async t => {
  const page = await fixturePage(t);
  const rowIds = () => page.locator('[data-au-claim-row]').evaluateAll(rows => rows.map(row => row.dataset.auClaimRow));
  assert.deepEqual(sorted(await rowIds()), sorted(originals.map(row => row.claim_id)));
  assert.equal(await page.locator('[data-au-collection-scope="originals"]').getAttribute('aria-pressed'), 'true');
  assert.equal(await page.locator('[data-au-domain="all"] strong').innerText(), '150');
  for (const domain of ['defect_mold_heating', 'lease_termination_dispute', 'rent_increase_dispute']) assert.equal(await page.locator(`[data-au-domain="${domain}"] strong`).innerText(), '50');
  await page.locator('.au-nav [data-au-nav="work"]').click();
  await page.locator('[data-au-collection-scope="added"]').click();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 9), 'Added cases did not retain all nine histories');
  assert.deepEqual(sorted(await rowIds()), sorted(historicalIds));
  assert.equal(new URL(page.url()).hash, '#autonomous/cases?scope=added');
  assert.match(await page.locator('[data-au-collection-scope="added"]').innerText(), /Added cases\s*9/);
  await page.goBack();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 150), 'Back did not restore Originals');
  assert.deepEqual(sorted(await rowIds()), sorted(originals.map(row => row.claim_id)));
  await page.goForward();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 9), 'Forward did not restore Added cases');
  await page.reload();
  await mountFixture(page);
  assert.equal(new URL(page.url()).hash, '#autonomous/cases?scope=added');
  assert.deepEqual(sorted(await rowIds()), sorted(historicalIds));
  await page.locator('[data-au-collection-scope="originals"]').click();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 150), 'Originals did not restore after Added reload');
  assert.equal(await page.locator('[data-au-domain="all"] strong').innerText(), '150');
});

test('a newly remembered native intake appears in Added cases while original counts remain 150', async t => {
  const id = historicalIds.at(-1), page = await fixturePage(t, {rememberedNativeId: id});
  await open(page, id);
  await title(page, id);
  await page.evaluate(() => { window.__fixture.holdCollections = true; });
  await page.locator('.au-nav [data-au-nav="work"]').click();
  assert.equal(await page.locator('[data-au-claim-row]').count(), 150);
  assert.equal(await page.locator('[data-au-domain="all"] strong').innerText(), '150');
  await page.locator('[data-au-collection-scope="added"]').click();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 9), 'the newly remembered intake was not classified as Added');
  assert.equal(await page.locator(`[data-au-claim-row="${id}"]`).count(), 1);
  await page.evaluate(id => {
    const state = window.__fixture.envelopes[id].state;
    window.__fixture.rows.push({claim_id: id, title: state.title, origin: 'native_intake', revision: state.revision, state_sha256: state.state_sha256, status: state.status});
    window.__fixture.holdCollections = false;
    for (const held of window.__fixture.held.splice(0)) held.release();
  }, id);
  await page.locator('[data-au-collection-scope="originals"]').click();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 150), 'remembering an added intake changed original membership');
  assert.equal(await page.locator(`[data-au-claim-row="${id}"]`).count(), 0);
});

test('Investigation complete groups completed codes without changing the raw claim or its legal outcome', async t => {
  const page = await fixturePage(t, {completeStatuses: true});
  await page.locator('[data-au-collection-scope="added"]').click();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 9), 'Added case statuses did not render');
  const filter = page.locator('[data-au-claim-filter]');
  assert.equal(await filter.locator('option[value="investigation_complete"]').innerText(), 'Investigation complete');
  assert.equal(await filter.locator('option[value="completed"], option[value="complete"], option[value="resolved"]').count(), 0);
  await filter.selectOption('investigation_complete');
  assert.deepEqual(sorted(await page.locator('[data-au-claim-row]').evaluateAll(rows => rows.map(row => row.dataset.auClaimRow))), sorted(historicalIds.slice(0, 3)));
  assert.deepEqual(await page.locator('[data-au-claim-row] > .au-status').allTextContents(), ['Investigation complete', 'Investigation complete', 'Investigation complete']);
  for (const [index, status] of ['completed', 'complete', 'resolved'].entries()) {
    const id = historicalIds[index], expected = await page.evaluate(id => window.__fixture.envelopes[id].state.outcome, id);
    await open(page, id);
    await title(page, id);
    assert.equal(await page.locator('.au-work-head .au-status').innerText(), 'Investigation complete');
    const saved = JSON.parse(await page.locator('[data-au-disclosure="claim-record"] pre').textContent());
    assert.equal(saved.state.status, status);
    assert.deepEqual(saved.state.outcome, expected);
    if (expected?.summary || expected?.reason) assert.ok((await page.locator('.au-outcome-body').textContent()).includes(expected.summary || expected.reason), 'the investigation label cannot rewrite the recorded legal outcome');
  }
});

async function originalGeometry(page) {
  return page.evaluate(() => {
    const box = selector => { const element = document.querySelector(selector), rect = element.getBoundingClientRect(); return {x: rect.x, y: rect.y, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height, clientWidth: element.clientWidth, scrollWidth: element.scrollWidth, clientHeight: element.clientHeight, scrollHeight: element.scrollHeight}; };
    const message = document.querySelector('.au-original-message'), subject = document.querySelector('.au-original-subject');
    const style = getComputedStyle(message), subjectStyle = getComputedStyle(subject), canvas = document.createElement('canvas');
    const context = canvas.getContext('2d'); context.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
    return {subject: box('.au-original-subject'), message: box('.au-original-message'), column: box('.au-original-message-column'), rail: box('.au-original-source-rail'),
      fontSize: Number.parseFloat(style.fontSize), subjectFontSize: Number.parseFloat(subjectStyle.fontSize), ch: context.measureText('0').width,
      layout: getComputedStyle(document.querySelector('.au-original-layout')).display, ellipsis: subjectStyle.textOverflow,
      viewport: innerWidth, documentWidth: document.documentElement.scrollWidth};
  });
}

for (const width of [1440, 390]) test(`original subjects, full bodies and adjacent sources remain readable at ${width}px`, async t => {
  const id = demoIds[0], page = await fixturePage(t, {width, height: 844}), original = originals.find(row => row.claim_id === id);
  await open(page, id);
  await title(page, id);
  assert.equal(await page.locator('.au-original-subject').textContent(), original.subject);
  assert.equal(await page.locator('.au-original-message').textContent(), original.message);
  const geometry = await originalGeometry(page);
  assert.equal(geometry.fontSize, 16);
  assert.ok(geometry.subjectFontSize >= (width === 390 ? 24 : 28) && geometry.subjectFontSize <= (width === 390 ? 32 : 34), `the exact subject must remain comfortably sized: ${JSON.stringify(geometry)}`);
  assert.ok(geometry.message.width <= 72 * geometry.ch + 3, `message lines must stay within approximately 72 characters: ${JSON.stringify(geometry)}`);
  assert.ok(geometry.subject.scrollWidth <= geometry.subject.clientWidth + 1 && geometry.subject.scrollHeight <= geometry.subject.clientHeight + 1, 'the full subject cannot be clipped');
  assert.notEqual(geometry.ellipsis, 'ellipsis');
  assert.ok(geometry.documentWidth <= width + 1, 'the original message must not create horizontal page overflow');
  if (width === 1440) {
    assert.equal(geometry.layout, 'grid');
    assert.ok(geometry.rail.x >= geometry.column.right - 1, 'desktop originals need an adjacent source rail');
    assert.ok(Math.abs(geometry.rail.y - geometry.column.y) <= 40, 'the source rail must begin beside the full original body');
    assert.ok(geometry.message.width >= 48 * geometry.ch, 'desktop message lines must not collapse into a narrow column');
  } else {
    assert.ok(geometry.rail.bottom <= geometry.column.y + 1, 'mobile sources must precede the complete message');
    assert.ok(geometry.rail.y < 650, 'source controls must remain near the top of the mobile view');
    assert.ok(geometry.message.width >= 280);
    const header = await page.evaluate(() => {
      const rect = selector => { const r = document.querySelector(selector).getBoundingClientRect(); return {y: r.y, bottom: r.bottom, height: r.height}; };
      return {header: rect('.au-identity-header'), brand: rect('.au-brand'), intake: rect('.au-header-new'), nav: [...document.querySelectorAll('.au-nav [data-au-nav]')].map(element => ({name: element.dataset.auNav, y: element.getBoundingClientRect().y}))};
    });
    assert.ok(header.header.height <= 140, 'the mobile header must keep the case evidence near the top');
    assert.ok(Math.abs(header.brand.y - header.intake.y) <= 12, 'New claim belongs beside the brand');
    assert.deepEqual(header.nav.map(item => item.name), ['work', 'demonstration', 'knowledge']);
    assert.ok(Math.max(...header.nav.map(item => item.y)) - Math.min(...header.nav.map(item => item.y)) <= 2, 'primary navigation must occupy one row');
  }
  if (process.env.CASEPATH_BROWSER_RECEIPTS) {
    const receipt = await page.evaluate(() => {
      const bounds = selector => [...document.querySelectorAll(selector)].map(element => ({label: element.textContent, ...element.getBoundingClientRect().toJSON()}));
      return {header: bounds('.au-identity-header'), brand: bounds('.au-brand'), navigation: bounds('.au-nav [data-au-nav]'), newClaim: bounds('.au-header-new'), sources: bounds('[data-au-source]')};
    });
    const destination = `/tmp/casepath-original-${id}-${width}`;
    await page.screenshot({path: `${destination}.png`, fullPage: true});
    fs.writeFileSync(`${destination}.json`, JSON.stringify({claim_id: id, width, geometry, ...receipt, exactSubject: true, completeBody: true}, null, 2));
  }
});

test('the mobile JPEG viewer presents one capability statement, checked original bytes and technical extraction details', async t => {
  const page = await fixturePage(t, {width: 390, height: 844, jpeg: true}), id = jpegBinding.claim_id, source = jpegDescriptor;
  await open(page, id);
  await title(page, id);
  await page.locator(`[data-au-source="${source.artifact_id}"]`).click();
  await eventually(() => page.locator('.au-native-image').evaluate(image => image.complete && image.naturalWidth > 0).catch(() => false), 'the byte-verified original JPEG did not decode');
  assert.equal(await page.locator('.au-source-capability').innerText(), 'Original image viewable. The agent cannot interpret this image.');
  assert.equal(await page.locator('[data-au-source-content] p:visible').count(), 1, 'binary extraction caveats belong in technical disclosure');
  const identity = page.locator('details.au-source-identity');
  assert.equal(await identity.evaluate(element => element.open), false);
  assert.equal(await identity.locator('summary').innerText(), 'Source identity and extraction');
  assert.match(await page.locator('.au-native-image').getAttribute('src'), /^blob:/);
  assert.equal(await page.locator('[data-au-source-content] a[download]').getAttribute('download'), source.file_name);
  assert.equal((await calls(page, `/sources/${id}/${source.artifact_id}`)).length, 1);
  await identity.locator('summary').click();
  const technical = await identity.textContent();
  for (const value of [source.media_type, source.sha256, 'unsupported_metadata', 'coverage', 'preview_only', 'evidence_admitted']) assert.ok(technical.includes(value), `technical source identity retains ${value}`);
  if (process.env.CASEPATH_BROWSER_RECEIPTS) {
    await page.screenshot({path: '/tmp/casepath-original-jpeg-dialog-390.png', fullPage: true});
    fs.writeFileSync('/tmp/casepath-original-jpeg-dialog-390.json', JSON.stringify(await page.evaluate(() => ({dialog: document.querySelector('dialog').getBoundingClientRect().toJSON(), image: document.querySelector('.au-native-image').getBoundingClientRect().toJSON(), naturalWidth: document.querySelector('.au-native-image').naturalWidth, naturalHeight: document.querySelector('.au-native-image').naturalHeight, capability: document.querySelector('.au-source-capability').textContent})), null, 2));
  }
  await page.keyboard.press('Escape');
  await eventually(() => page.locator('dialog').getAttribute('open').then(value => value === null), 'Escape did not close the source');
  assert.equal(await page.evaluate(() => document.activeElement?.dataset.auSource), source.artifact_id);
});

test('a corrupted original JPEG retains its verified preview and identity without claiming the native image is viewable', async t => {
  const page = await fixturePage(t, {width: 390, jpeg: true}), id = jpegBinding.claim_id, source = jpegDescriptor;
  await page.evaluate(key => { window.__fixture.rawSources[key] = btoa('corrupted original bytes'); }, `${id}/${source.artifact_id}`);
  await open(page, id);
  await title(page, id);
  await page.locator(`[data-au-source="${source.artifact_id}"]`).click();
  await eventually(() => page.locator('.au-source-capability').count().then(count => count === 1), 'the valid preview was discarded after a native byte mismatch');
  assert.equal(await page.locator('.au-source-capability').innerText(), 'Original image preview unavailable. The agent cannot interpret this image.');
  assert.equal(await page.locator('.au-native-image').count(), 0);
  assert.match(await page.locator('[data-au-source-content]').innerText(), /original file failed its byte identity check/i);
  assert.equal(await page.locator('[data-au-source-content] a[download]').getAttribute('download'), source.file_name);
  await page.locator('details.au-source-identity > summary').click();
  assert.match(await page.locator('details.au-source-identity').innerText(), /Read-only preview verified/);
  assert.ok((await page.locator('details.au-source-identity').innerText()).includes(source.sha256));
});

test('Live Play resumes a verified original opening once after bounded mismatches and never retries an uncertain Start automatically', async t => {
  const id = demoIds[0], page = await fixturePage(t, {originalStartId: id, mismatchedSnapshots: 3});
  const originalHash = await page.evaluate(id => window.__fixture.envelopes[id].state.state_sha256, id);
  await page.locator('.au-nav [data-au-nav="demonstration"]').click();
  await page.locator('[data-au-demo-mode="live"]').click();
  await page.locator('[data-au-demo-play]').click();
  await eventually(async () => (await calls(page, `/claims/${id}/snapshot`)).length === 3 && /automatically/i.test(await page.locator('.au-global-status').innerText()), 'Live Play did not retain its recovering original opening');
  assert.equal((await calls(page, `/claims/${id}/start`)).length, 0);
  await page.clock.runFor(7000);
  await eventually(async () => (await calls(page, `/claims/${id}/start`)).length === 1, 'the same active Live Play did not start its recovered original');
  const [started] = await calls(page, `/claims/${id}/start`);
  assert.equal(JSON.parse(started.body).expected_revision, 0);
  assert.equal(JSON.parse(started.body).expected_state_sha256, originalHash);
  assert.equal(started.headers['X-CasePath-Agent-Work'], '1');
  await page.evaluate(id => { window.__fixture.advance(id); Object.assign(window.__fixture.envelopes[id].state, {status: 'completed', phase: 'complete'}); }, id);
  await page.clock.runFor(10000);
  assert.equal((await calls(page, `/claims/${id}/start`)).length, 1, 'a lost Start response requires an explicit retry, including inside Live Play');
  assert.equal(new URL(page.url()).hash.split('?')[0], `#autonomous/claim/${id}`, 'a terminal background observation cannot move uncertain Start admission to another original');
  assert.equal(await page.locator('[data-au-start]').innerText(), 'Retry start');
});

for (const mode of ['live', 'replay']) test(`timed ${mode} presentation inspects all nine canonical cases with modal and hidden pauses, then cancels on navigation`, async t => {
  const page = await fixturePage(t, {presentationSuite: mode});
  await page.locator('.au-nav [data-au-nav="demonstration"]').click();
  await page.locator(`[data-au-demo-mode="${mode}"]`).click();
  await page.locator('[data-au-demo-play]').click();
  await title(page, demoIds[0]);
  if (mode === 'live') {
    await eventually(() => page.locator('[data-au-detail="sources"]').count().then(count => count === 1), 'Live Play did not admit its initial Start');
    await page.locator('[data-au-detail="sources"]').click();
  }
  await page.locator('[data-au-source]').first().click();
  await eventually(() => page.locator('details.au-source-identity').count().then(count => count === 1), 'presentation source inspection did not verify its exact original');
  const path = mode === 'live' ? 'snapshot' : 'replay';
  const reads = () => page.evaluate(({base, path}) => window.__fixture.calls.filter(call => call.url.startsWith(`${base}/claims/`) && call.url.includes(`/${path}?`)), {base, path});
  const modalReads = (await reads()).length;
  await page.clock.runFor(10000);
  assert.equal(new URL(page.url()).hash.split('?')[0], `#autonomous/claim/${demoIds[0]}`, 'an open original-source dialog pauses presentation advancement');
  if (mode === 'replay') assert.equal((await reads()).length, modalReads, 'source inspection pauses accepted replay prefixes');
  assert.equal((await page.evaluate(() => window.__fixture.calls.filter(call => call.method === 'POST'))).length, mode === 'live' ? 1 : 0);
  await page.keyboard.press('Escape');
  await page.evaluate(() => { window.__fixture.hidden = true; Object.defineProperty(document, 'hidden', {configurable: true, get: () => window.__fixture.hidden}); document.dispatchEvent(new Event('visibilitychange')); });
  const hiddenReads = (await reads()).length;
  await page.clock.runFor(10000);
  assert.equal(new URL(page.url()).hash.split('?')[0], `#autonomous/claim/${demoIds[0]}`, 'a hidden tab pauses the canonical presentation');
  if (mode === 'replay') assert.equal((await reads()).length, hiddenReads);
  await page.evaluate(() => { window.__fixture.hidden = false; document.dispatchEvent(new Event('visibilitychange')); });
  for (let tick = 0; tick < 90 && await page.locator('[data-au-demo-stop]').count(); tick++) {
    await page.clock.runFor(1600);
    await delay(10);
  }
  assert.equal(await page.locator('[data-au-demo-stop]').count(), 0, `the ${mode} presentation did not finish its nine histories automatically`);
  assert.equal(new URL(page.url()).hash.split('?')[0], `#autonomous/claim/${demoIds[8]}`);
  const opened = (await reads()).map(call => call.url.match(/\/claims\/([^/]+)\//)[1]);
  assert.deepEqual([...new Set(opened)], demoIds, 'the full timed presentation must inspect exactly the nine canonical identities in order');
  const posts = await page.evaluate(() => window.__fixture.calls.filter(call => call.method === 'POST'));
  if (mode === 'replay') {
    assert.deepEqual(posts, []);
    for (const id of demoIds) assert.deepEqual((await calls(page, `/claims/${id}/replay`)).map(call => Number(new URL(call.url, 'http://fixture.invalid').searchParams.get('through_seq'))), [0, 1, 2], 'each replay exposes the verified original and both accepted prefixes');
  } else {
    assert.equal(posts.length, 9, 'Live Play may admit one Start for each of the nine unprocessed originals');
    assert.deepEqual(posts.map(call => call.url.match(/\/claims\/([^/]+)\//)[1]), demoIds);
    for (const call of posts) assert.equal(JSON.parse(call.body).expected_revision, 0);
  }
  // Restart an active presentation and abandon it through product navigation.
  // Live originals are already processed, so this restart has no Start intent.
  await page.locator('.au-nav [data-au-nav="demonstration"]').click();
  await page.locator('[data-au-demo-play]').click();
  await title(page, demoIds[0]);
  await page.locator('.au-nav [data-au-nav="work"]').click();
  const cancelledReads = (await reads()).length, cancelledPosts = await page.evaluate(() => window.__fixture.calls.filter(call => call.method === 'POST').length);
  await page.clock.runFor(20000);
  assert.equal((await reads()).length, cancelledReads, 'navigation must abandon every pending presentation read');
  assert.equal(await page.evaluate(() => window.__fixture.calls.filter(call => call.method === 'POST').length), cancelledPosts);
  assert.equal(await page.locator('[data-au-claim-row]').count(), 150);
});

test('leaving a recovering Live Play cancels its original Start authorization', async t => {
  const id = demoIds[0], page = await fixturePage(t, {originalStartId: id, mismatchedSnapshots: 3});
  await page.locator('.au-nav [data-au-nav="demonstration"]').click();
  await page.locator('[data-au-demo-mode="live"]').click();
  await page.locator('[data-au-demo-play]').click();
  await eventually(async () => (await calls(page, `/claims/${id}/snapshot`)).length === 3 && /automatically/i.test(await page.locator('.au-global-status').innerText()), 'Live Play did not reach its recovering opening');
  await page.locator('.au-nav [data-au-nav="work"]').click();
  await page.clock.runFor(10000);
  assert.equal((await calls(page, `/claims/${id}/start`)).length, 0);
  assert.equal((await calls(page, `/claims/${id}/snapshot`)).length, 3);
  assert.equal(await page.locator('[data-au-claim-row]').count(), 150);
});

test('overlapping opening reads preserve the newer record and source disclosure while equal revisions remain strict', async t => {
  const page = await fixturePage(t, {holdId: processedId, holdRemaining: 1});
  const revision = await page.evaluate(id => window.__fixture.envelopes[id].state.revision, processedId);
  await open(page, processedId);
  await eventually(() => page.evaluate(() => window.__fixture.held.length === 1), 'the earlier opening read was not held');
  await page.evaluate(id => { window.__fixture.advance(id); document.dispatchEvent(new Event('visibilitychange')); }, processedId);
  await title(page, processedId);
  assert.match(await page.locator('.au-work-head').innerText(), new RegExp(`revision ${revision + 1}\\b`, 'i'));
  const chosen = await page.locator('[data-au-node]').last().getAttribute('data-au-node');
  await page.locator(`[data-au-node="${chosen}"]`).click();
  await page.locator('[data-au-detail="sources"]').click();
  const sourceId = await page.locator('[data-au-panel="sources"] [data-au-source]').first().getAttribute('data-au-source');
  await page.locator(`[data-au-panel="sources"] [data-au-source="${sourceId}"]`).click();
  await eventually(() => page.locator('details.au-source-identity').count().then(count => count === 1), 'the current original source identity did not verify');
  await page.locator('details.au-source-identity > summary').click();
  const before = await page.locator('[data-au-disclosure="claim-record"] pre').textContent();
  await page.evaluate(() => { window.__retainedSource = document.querySelector('details.au-source-identity'); for (const held of window.__fixture.held.splice(0)) held.release(); });
  await page.evaluate(() => new Promise(resolve => queueMicrotask(resolve)));
  assert.equal(await page.locator('[data-au-disclosure="claim-record"] pre').textContent(), before, 'the delayed older opening cannot replace the verified newer record');
  assert.equal(await page.evaluate(() => document.querySelector('details.au-source-identity') === window.__retainedSource && window.__retainedSource.open), true);
  assert.equal(await page.locator(`[data-au-node="${chosen}"]`).getAttribute('aria-pressed'), 'true');
  await page.evaluate(() => window.__controller.refresh());
  assert.equal(await page.locator('[data-au-disclosure="claim-record"] pre').textContent(), before, 'a matching equal revision must remain valid');
  const reads = (await calls(page, `/claims/${processedId}/snapshot`)).length;
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await eventually(async () => (await calls(page, `/claims/${processedId}/snapshot`)).length > reads, 'normal visibility resume did not refresh the saved claim');
  assert.doesNotMatch(await page.locator('.au-global-status').innerText(), /connection restored/i, 'normal visibility resume cannot fabricate a failed connection');
  await page.evaluate(() => { window.__fixture.conflictingHash = true; });
  await page.evaluate(() => window.__controller.refresh());
  assert.match(await page.locator('.au-global-status').innerText(), /saved revision changed identity/i);
  assert.equal(await page.locator('[data-au-disclosure="claim-record"] pre').textContent(), before, 'a conflicting equal-revision hash fails closed while saved work remains visible');
});

test('a Documents link returns to its process step and reload retains the step detail', async t => {
  const page = await fixturePage(t);
  await open(page, processedId);
  await title(page, processedId);
  await page.locator('[data-au-detail="documents"]').click();
  assert.match(new URL(page.url()).hash, /detail=documents/);
  const target = page.locator('[data-au-panel="documents"] [data-au-select]').first();
  assert.equal(await target.count(), 1, 'the recorded document requirement must link to a requiring node');
  const node = await target.getAttribute('data-au-select');
  await target.click();
  assert.equal(await page.locator('[data-au-panel="step"]').isVisible(), true);
  assert.equal(await page.locator(`[data-au-node="${node}"]`).getAttribute('aria-pressed'), 'true');
  assert.doesNotMatch(new URL(page.url()).hash, /detail=documents/);
  await page.reload();
  await mountFixture(page);
  assert.equal(await page.locator('[data-au-panel="step"]').isVisible(), true);
  assert.equal(await page.locator('[data-au-graph]').isVisible(), true);
});

test('Verified replay stays visible as presentation mode when the accepted prefix status is Working', async t => {
  const page = await fixturePage(t, {replayStatus: 'running'});
  await page.evaluate(id => { void window.__controller.openClaim(id, true, {mode: 'replay', through: 2}); }, processedId);
  await title(page, processedId);
  assert.equal(await page.locator('[data-au-presentation-mode]').innerText(), 'Verified replay');
  assert.equal(await page.locator('.au-work-head .au-status').innerText(), 'Working');
  assert.match(new URL(page.url()).hash, /mode=replay/);
  assert.match(new URL(page.url()).hash, /through=2/);
  assert.equal((await calls(page, `/claims/${processedId}/replay`)).length, 1);
  assert.equal(await page.locator('[data-au-arrival], [data-au-pause], [data-au-resume], [data-au-start]').count(), 0, 'a replay cannot expose live write controls');
  const before = (await calls(page, `/claims/${processedId}/snapshot`)).length;
  await page.evaluate(async () => { await window.__controller.refresh(); await window.__controller.refresh(); });
  await page.clock.runFor(7000);
  assert.equal((await calls(page, `/claims/${processedId}/snapshot`)).length, before, 'a replay must not poll live state');
  assert.equal(await page.locator('[data-au-presentation-mode]').innerText(), 'Verified replay');
  await page.evaluate(id => { void window.__controller.openClaim(id, true, {mode: 'replay', through: 0}); }, processedId);
  await title(page, processedId);
  assert.equal(await page.locator('[data-au-arrival], [data-au-pause], [data-au-resume], [data-au-start]').count(), 0, 'a revision-zero replay cannot expose Start or file arrival');
  await page.evaluate(() => window.__controller.refresh());
  assert.equal((await calls(page, `/claims/${processedId}/snapshot`)).length, before);
  assert.deepEqual(await page.evaluate(() => window.__fixture.calls.filter(call => call.method !== 'GET')), []);
});

test('an explicit original Start preserves its guarded retry after background acceptance and navigation', async t => {
  const startId = demoIds[3];
  const page = await fixturePage(t, {originalStartId: startId});
  const original = await page.evaluate(id => structuredClone(window.__fixture.envelopes[id].state), startId);
  const posts = async () => (await calls(page, `/claims/${startId}/start`)).filter(call => call.method === 'POST');
  await open(page, startId);
  await title(page, startId);
  await eventually(() => page.locator('[data-au-start]').isEnabled(), 'the configured original Start did not become available');
  assert.equal(original.revision, 0);
  assert.equal((await posts()).length, 0, 'opening an original claim cannot start it');
  await page.locator('[data-au-start]').click();
  await eventually(() => page.locator('.au-global-status').innerText().then(value => value.includes('Response unconfirmed')), 'the uncertain Start response was not retained for retry');
  const [first] = await posts(), firstBody = JSON.parse(first.body);
  assert.equal((await posts()).length, 1, 'one Start click must make exactly one POST');
  assert.deepEqual(sorted(Object.keys(firstBody)), ['expected_revision', 'expected_state_sha256', 'idempotency_key']);
  assert.equal(firstBody.expected_revision, 0);
  assert.equal(firstBody.expected_state_sha256, original.state_sha256);
  assert.match(firstBody.idempotency_key, /^browser\.[a-f0-9-]+$/i);
  assert.equal(first.headers['X-CasePath-Agent-Work'], '1');
  assert.equal(first.headers['Content-Type'], 'application/json');
  await page.clock.runFor(7000);
  await eventually(async () => {
    if (!await page.locator('[data-au-disclosure="claim-record"] pre').count()) return false;
    return JSON.parse(await page.locator('[data-au-disclosure="claim-record"] pre').textContent()).state.revision === 1;
  }, 'background polling did not observe the accepted revision after the Start response was lost');
  assert.match(await page.locator('.au-work-head').innerText(), /revision 1\b/i);
  assert.equal(await page.locator('[data-au-start]').innerText(), 'Retry start');
  assert.equal(await page.locator('[data-au-start]').isEnabled(), true, 'the nonzero accepted revision must retain its original pending Start retry');
  assert.equal((await posts()).length, 1, 'a network-uncertain Start cannot retry automatically');
  const liveReads = (await calls(page, `/claims/${startId}/snapshot`)).length;
  await page.evaluate(id => { void window.__controller.openClaim(id, true, {mode: 'replay', through: 1}); }, startId);
  await title(page, startId);
  assert.equal(await page.locator('[data-au-presentation-mode]').innerText(), 'Verified replay');
  assert.equal(await page.locator('[data-au-arrival], [data-au-pause], [data-au-resume], [data-au-start]').count(), 0, 'replay must hide write controls even when that claim has a pending Start');
  await page.evaluate(() => window.__controller.refresh());
  assert.equal((await calls(page, `/claims/${startId}/snapshot`)).length, liveReads, 'refreshing the pending claim in replay cannot read live state');
  assert.equal((await posts()).length, 1, 'entering replay cannot submit the pending Start');
  await page.evaluate(() => { window.__fixture.providerReady = false; });
  await page.locator('.au-nav [data-au-nav="work"]').click();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 150), 'Cases did not restore after an uncertain Start');
  await page.locator(`[data-au-claim-row="${startId}"] [data-au-claim="${startId}"]`).click();
  await title(page, startId);
  assert.equal(new URL(page.url()).hash, `#autonomous/claim/${startId}`);
  assert.equal((await posts()).length, 1, 'returning to the original must preserve the pending request without submitting it');
  await eventually(() => page.locator('[data-au-start]').isEnabled(), 'the original pending Start retry must remain available after readiness changes');
  assert.equal(await page.locator('[data-au-start]').innerText(), 'Retry start');
  await page.locator('[data-au-start]').click();
  await eventually(async () => {
    const record = await page.locator('[data-au-disclosure="claim-record"] pre').count();
    if (!record) return false;
    return JSON.parse(await page.locator('[data-au-disclosure="claim-record"] pre').textContent()).state.revision >= 2;
  }, 'Start did not read the concurrently advanced matching snapshot');
  const [initial, retry] = await posts();
  assert.equal((await posts()).length, 2, 'each explicit Start click must make one POST');
  assert.equal(retry.body, initial.body, 'retry must preserve the exact JSON and idempotency key across navigation');
  assert.deepEqual(retry.headers, initial.headers);
  const saved = JSON.parse(await page.locator('[data-au-disclosure="claim-record"] pre').textContent());
  assert.equal(saved.state.claim_id, startId);
  assert.equal(saved.state.revision, 2);
  assert.equal(saved.projection.state_sha256, saved.state.state_sha256);
  assert.deepEqual(saved.state.source_descriptors, original.source_descriptors, 'Start must preserve the original source identity');
  assert.equal(saved.state.title, original.title);
  assert.equal(await page.locator('[data-au-presentation-mode]').innerText(), 'Live execution');
  assert.equal(new URL(page.url()).hash, `#autonomous/claim/${startId}`);
  assert.match(await page.locator('.au-work-head').innerText(), /revision 2\b/i);
  assert.equal(await page.locator('[data-au-start]').count(), 0);
  await page.clock.runFor(10000);
  assert.equal((await posts()).length, 2, 'neither snapshot polling nor accepted Start can submit another POST');
});

test('an original revision-zero packet exposes its source without a substantive graph or outcome', async t => {
  const page = await fixturePage(t);
  await open(page, unprocessedId);
  await title(page, unprocessedId);
  assert.equal(new URL(page.url()).hash, `#autonomous/claim/${unprocessedId}`);
  assert.equal(await page.locator('[data-au-node], [data-au-edge]').count(), 0);
  assert.equal(await page.locator('.au-outcome').count(), 0);
  assert.match(await page.locator('[data-au-view]').innerText(), /not started|not run|unprocessed/i);
  const original = await page.evaluate(id => window.__fixture.envelopes[id].state, unprocessedId);
  await page.locator(`[data-au-source="${original.source_descriptors[0].artifact_id}"]`).click();
  await eventually(() => page.locator('dialog').getAttribute('open').then(value => value !== null), 'The original source did not open');
  await eventually(() => page.locator('.au-source-body').count().then(count => count === 1), 'the original source text did not verify');
  assert.equal(await page.locator('.au-source-body').textContent(), original.message);
  assert.equal(await page.locator('[data-au-node], [data-au-edge]').count(), 0);
});

test('an atomic snapshot renders a matching state and cursor even while a writer advances after each read', async t => {
  const page = await fixturePage(t, {atomicWriter: true, splitWriter: true});
  const revision = await page.evaluate(id => window.__fixture.envelopes[id].state.revision, processedId);
  await open(page, processedId);
  await title(page, processedId);
  assert.match(await page.locator('.au-work-head').innerText(), new RegExp(`revision ${revision}\\b`, 'i'));
  assert.ok(await page.locator('[data-au-node]').count() > 1, 'the verified snapshot renders its saved substantive graph');
  assert.equal((await calls(page, `/claims/${processedId}`)).length, 0, 'atomic reads cannot split state and events');
  assert.equal((await calls(page, `/claims/${processedId}/events`)).length, 0);
  assert.deepEqual((await calls(page, `/claims/${processedId}/snapshot`)).map(call => new URL(call.url, 'http://fixture.invalid').searchParams.get('after')), ['0']);
  await page.evaluate(() => window.__controller.refresh());
  await eventually(async () => new RegExp(`revision ${revision + 1}\\b`, 'i').test(await page.locator('.au-work-head').innerText()), 'polling did not render the next atomic revision');
  assert.deepEqual((await calls(page, `/claims/${processedId}/snapshot`)).map(call => new URL(call.url, 'http://fixture.invalid').searchParams.get('after')), ['0', String(revision)]);
  await page.locator('[data-au-detail="documents"]').click();
  assert.equal(await page.locator('[data-au-graph]').isVisible(), false, 'Documents must hide the process graph');
  await page.locator('[data-au-detail="sources"]').click();
  assert.equal(await page.locator('[data-au-graph]').isVisible(), false, 'Original sources must hide the process graph');
  await page.locator('[data-au-detail="step"]').click();
  assert.equal(await page.locator('[data-au-graph]').isVisible(), true);
});

test('three mismatched legacy pairs stay unrendered and recover on the scheduled retry without manual Retry', async t => {
  const page = await fixturePage(t, {snapshotStatus: 404, splitWriter: true});
  await open(page, processedId);
  await eventually(async () => (await calls(page, `/claims/${processedId}/events`)).length === 3, 'opening did not make three bounded legacy read pairs');
  assert.equal((await calls(page, `/claims/${processedId}`)).length, 3);
  assert.equal(await page.locator('[data-au-claim-title]').count(), 0, 'an advancing legacy cursor must not render the mismatched state');
  assert.equal(await page.locator('[data-au-node]').count(), 0);
  await page.evaluate(() => { window.__fixture.splitWriter = false; });
  await page.clock.runFor(7000);
  await title(page, processedId);
  assert.ok((await calls(page, `/claims/${processedId}/events`)).length >= 4, 'the recovery must issue a timed new read pair');
  assert.ok(await page.locator('[data-au-node]').count() > 1);
});

test('three mismatched atomic snapshots also recover automatically and never fall back to split reads', async t => {
  const page = await fixturePage(t, {mismatchedSnapshots: 3});
  await open(page, processedId);
  await eventually(async () => (await calls(page, `/claims/${processedId}/snapshot`)).length === 3, 'opening did not retry the mismatched snapshot three times');
  assert.equal(await page.locator('[data-au-claim-title]').count(), 0);
  await page.clock.runFor(7000);
  await title(page, processedId);
  assert.equal((await calls(page, `/claims/${processedId}`)).length, 0);
  assert.equal((await calls(page, `/claims/${processedId}/events`)).length, 0);
});

test('visibility resume recovers an initial opening after three mismatched snapshots without manual Retry', async t => {
  const page = await fixturePage(t, {mismatchedSnapshots: 3});
  await page.evaluate(id => { void window.__controller.openClaim(id, true, {detail: 'sources'}); }, processedId);
  await eventually(async () => (await calls(page, `/claims/${processedId}/snapshot`)).length === 3
    && /automatically/i.test(await page.locator('.au-global-status').innerText()), 'the initial three mismatches did not reach automatic recovery');
  assert.equal(await page.locator('[data-au-claim-title]').count(), 0);
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', {configurable: true, value: false});
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await page.clock.runFor(7000);
  await title(page, processedId);
  assert.equal(await page.locator('[data-au-panel="sources"]').isVisible(), true, 'visibility recovery must retain the requested claim detail');
  assert.equal(await page.locator('[data-au-graph]').isVisible(), false);
  assert.ok((await calls(page, `/claims/${processedId}/snapshot`)).length >= 4);
  assert.equal((await calls(page, `/claims/${processedId}`)).length, 0);
  assert.equal((await calls(page, `/claims/${processedId}/events`)).length, 0);
});

test('an unknown claim snapshot and legacy 404 cannot disable atomic reads for the next known claim', async t => {
  const page = await fixturePage(t), unknownId = 'clm_ffffffffffffffff';
  await open(page, unknownId);
  await eventually(() => page.locator('.au-global-status').innerText().then(value => value.includes('No GET response in this fixture.')), 'the unknown claim response was not surfaced');
  assert.equal((await calls(page, `/claims/${unknownId}/snapshot`)).length, 1);
  assert.equal((await calls(page, `/claims/${unknownId}`)).length, 1);
  assert.equal((await calls(page, `/claims/${unknownId}/events`)).length, 0, 'an unknown legacy claim cannot request events');
  assert.equal(await page.locator('[data-au-claim-title]').count(), 0);
  await open(page, processedId);
  await title(page, processedId);
  assert.equal((await calls(page, `/claims/${processedId}/snapshot`)).length, 1, 'the known claim must still use its atomic snapshot');
  assert.equal((await calls(page, `/claims/${processedId}`)).length, 0);
  assert.equal((await calls(page, `/claims/${processedId}/events`)).length, 0);
});

test('snapshot compatibility fallback is restricted to 404, 405 and 501', async t => {
  for (const status of [404, 405, 501, 401, 403, 409, 500]) {
    await t.test(String(status), async t => {
      const page = await fixturePage(t, {snapshotStatus: status});
      await open(page, processedId);
      await eventually(async () => (await calls(page, `/claims/${processedId}/snapshot`)).length > 0, 'the snapshot endpoint was not read');
      if ([404, 405, 501].includes(status)) {
        await title(page, processedId);
        assert.equal((await calls(page, `/claims/${processedId}`)).length, 1);
        assert.equal((await calls(page, `/claims/${processedId}/events`)).length, 1);
      } else {
        await eventually(() => page.locator('.au-global-status').innerText().then(value => value.includes('Configured snapshot transport response.')), 'the snapshot error was not surfaced');
        assert.equal(await page.locator('[data-au-claim-title]').count(), 0);
        assert.equal((await calls(page, `/claims/${processedId}`)).length, 0, 'transport errors cannot downgrade consistency');
        assert.equal((await calls(page, `/claims/${processedId}/events`)).length, 0);
      }
    });
  }
});

test('a snapshot capability projection with a different state hash remains unrendered', async t => {
  const page = await fixturePage(t, {corruptProjection: true});
  await open(page, processedId);
  await eventually(() => page.locator('.au-global-status').innerText().then(value => /different saved claim revision|projection/i.test(value)), 'the mismatched capability projection was not rejected');
  assert.equal(await page.locator('[data-au-claim-title]').count(), 0);
  assert.equal(await page.locator('[data-au-node]').count(), 0);
  assert.equal((await calls(page, `/claims/${processedId}`)).length, 0);
});

test('legacy fallback also rejects a same-revision cursor with a different state hash', async t => {
  const page = await fixturePage(t, {snapshotStatus: 501, corruptLegacyHash: true});
  await open(page, processedId);
  await eventually(() => page.locator('.au-global-status').innerText().then(value => /event response differs from the saved claim identity/i.test(value)), 'the legacy hash mismatch was not rejected');
  assert.equal(await page.locator('[data-au-claim-title]').count(), 0);
  assert.equal(await page.locator('[data-au-node]').count(), 0);
});

test('navigation abandons the scheduled recovery of an opening that never matched', async t => {
  const page = await fixturePage(t, {snapshotStatus: 404, splitWriter: true});
  await open(page, processedId);
  await eventually(async () => (await calls(page, `/claims/${processedId}/events`)).length === 3, 'the initial read pairs did not complete');
  await page.locator('.au-nav [data-au-nav="work"]').click();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 150), 'navigation did not restore Cases');
  await page.evaluate(() => { window.__fixture.splitWriter = false; });
  await page.clock.runFor(7000);
  assert.equal((await calls(page, `/claims/${processedId}/events`)).length, 3, 'a cancelled opening must not retry after navigation');
  assert.equal(await page.locator('[data-au-claim-title]').count(), 0);
  assert.equal(await page.locator('[data-au-claim-row]').count(), 150);
  assert.equal(new URL(page.url()).hash, '#autonomous/cases');
});

test('a delayed response from an abandoned claim cannot replace the next claim or its route', async t => {
  const page = await fixturePage(t, {holdId: processedId});
  await open(page, processedId);
  await eventually(() => page.evaluate(() => window.__fixture.held.length === 1), 'the first claim snapshot was not held');
  await page.locator('.au-nav [data-au-nav="work"]').click();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 150), 'navigation did not return to Cases');
  await open(page, otherId);
  await title(page, otherId);
  const renderedIdentity = () => page.evaluate(() => ({
    title: document.querySelector('[data-au-claim-title]')?.textContent,
    header: document.querySelector('.au-work-head')?.textContent,
    nodes: [...document.querySelectorAll('[data-au-node]')].map(node => node.dataset.auNode),
    savedRecord: document.querySelector('[data-au-disclosure="claim-record"] pre')?.textContent,
  }));
  const before = await renderedIdentity();
  await page.evaluate(() => { for (const held of window.__fixture.held.splice(0)) held.release(); });
  await page.evaluate(() => new Promise(resolve => queueMicrotask(resolve)));
  await title(page, otherId);
  assert.equal(new URL(page.url()).hash, `#autonomous/claim/${otherId}`);
  assert.deepEqual(await renderedIdentity(), before, 'the abandoned response must not replace the visible saved claim');
});

async function connectorContrast(page) {
  return page.evaluate(() => {
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 1;
    const context = canvas.getContext('2d', {willReadFrequently: true});
    const color = css => {
      context.clearRect(0, 0, 1, 1); context.fillStyle = css; context.fillRect(0, 0, 1, 1);
      return [...context.getImageData(0, 0, 1, 1).data].map((value, index) => index === 3 ? value / 255 : value);
    };
    const over = (front, back) => front.slice(0, 3).map((value, index) => value * front[3] + back[index] * (1 - front[3])).concat(1);
    const luminance = rgb => rgb.slice(0, 3).map(value => value / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4).reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
    const ratio = (front, back) => { const a = luminance(front), b = luminance(back); return (Math.max(a, b) + .05) / (Math.min(a, b) + .05); };
    return [...document.querySelectorAll('.au-graph-lines path, .au-evidence-lines path, .au-evidence-lines circle, .au-evidence-tether path')].filter(element => element.getAttribute('d') || element.tagName.toLowerCase() === 'circle').map(element => {
      const ancestry = []; for (let ancestor = element; ancestor; ancestor = ancestor.parentElement) ancestry.unshift(ancestor);
      let background = [255, 255, 255, 1], opacity = 1;
      for (const ancestor of ancestry) {
        const style = getComputedStyle(ancestor);
        background = over(color(style.backgroundColor), background);
        opacity *= Number(style.opacity);
      }
      const style = getComputedStyle(element), stroke = color(style.stroke);
      stroke[3] *= opacity * Number(style.strokeOpacity);
      const effective = over(stroke, background);
      return {kind: element.closest('.au-graph-lines') ? 'graph' : element.closest('.au-evidence-lines') ? 'evidence' : 'selection',
        edge: element.dataset.auEdge || null, state: element.dataset.state || null, selected: element.dataset.selected || null,
        stroke: style.stroke, opacity, strokeOpacity: Number(style.strokeOpacity), dash: style.strokeDasharray,
        background: background.slice(0, 3), effective: effective.slice(0, 3), contrast: ratio(effective, background)};
    });
  });
}

test('graph routes and evidence connectors retain at least 3:1 effective contrast with dashed excluded routes and coral selection', async t => {
  for (const width of [1440, 390]) {
    const page = await fixturePage(t, {width});
    await open(page, processedId);
    await title(page, processedId);
    const receipt = await connectorContrast(page);
    assert.ok(receipt.some(row => row.kind === 'graph' && row.selected === 'false'), 'the contrast check must include ordinary recorded connections');
    assert.ok(receipt.some(row => row.kind === 'evidence'), 'the contrast check must include actual evidence connectors');
    assert.ok(receipt.some(row => row.kind === 'selection'), 'the contrast check must include the selected-step tether and its opacity');
    for (const row of receipt) assert.ok(row.contrast >= 3, `${width}px ${row.kind} connector must reach 3:1 after opacity and background composition: ${JSON.stringify(row)}`);
    const excluded = receipt.filter(row => row.kind === 'graph' && ['false', 'inactive', 'not_reached'].includes(row.state));
    assert.ok(excluded.length > 0, 'the real process must retain excluded routes');
    assert.ok(excluded.every(row => row.dash !== 'none' && /[1-9]/.test(row.dash)), 'excluded routes remain dashed');
    const selection = await page.evaluate(() => {
      const node = document.querySelector('[data-au-node][aria-pressed="true"]'), workspace = document.querySelector('.au-workspace');
      const probe = document.createElement('span'); probe.style.color = getComputedStyle(workspace).getPropertyValue('--au-accent'); workspace.append(probe);
      const accent = getComputedStyle(probe).color; probe.remove();
      return {accent, title: getComputedStyle(node.querySelector('.au-node-title')).color, junction: getComputedStyle(node.querySelector('.au-node-index')).backgroundColor};
    });
    assert.equal(selection.title, selection.accent);
    assert.equal(selection.junction, selection.accent);
    if (process.env.CASEPATH_BROWSER_RECEIPTS) {
      await page.screenshot({path: `/tmp/casepath-visual-graph-${width}.png`, fullPage: true});
      fs.writeFileSync(`/tmp/casepath-visual-contrast-${width}.json`, JSON.stringify(receipt, null, 2));
    }
  }
});

test('the demonstration itinerary numbers its nine domain-grouped cases and shows verified status at the current presentation position', async t => {
  const page = await fixturePage(t, {presentationSuite: 'replay', width: 390, height: 844});
  await page.locator('.au-nav [data-au-nav="demonstration"]').click();
  const groups = page.locator('.au-demo-selection section');
  assert.equal(await groups.count(), 3);
  assert.deepEqual(await groups.locator('h2, h3').allTextContents(), ['Defects & repairs', 'Lease termination', 'Rent changes']);
  for (let index = 0; index < 3; index++) assert.deepEqual(await groups.nth(index).locator('[data-au-demo-case]').evaluateAll(rows => rows.map(row => row.dataset.auDemoCase)), demoIds.slice(index * 3, index * 3 + 3));
  assert.deepEqual(await page.locator('.au-demo-selection .au-demo-order').allTextContents(), ['01', '02', '03', '04', '05', '06', '07', '08', '09']);
  assert.equal(await page.locator('.au-demo-selection svg').count(), 0, 'the itinerary cannot imply a process or causal connection between separate cases');
  await page.locator('[data-au-demo-play]').click();
  await title(page, demoIds[0]);
  const itinerary = page.locator('details.au-demo-itinerary[data-au-disclosure="demo-itinerary"]');
  assert.equal(await itinerary.count(), 1);
  const position = () => itinerary.locator('.au-demo-position').innerText().then(text => text.match(/\d+/g).map(Number));
  assert.deepEqual(await position(), [1, 9]);
  assert.equal(await itinerary.locator('[data-au-demo-case][aria-current="step"]').getAttribute('data-au-demo-case'), demoIds[0]);
  assert.equal(await itinerary.locator('[aria-current="step"] .au-status').textContent(), 'Not started', 'the verified original overrides the collection summary of a completed head');
  await itinerary.locator('summary').click();
  assert.deepEqual(await itinerary.locator('.au-demo-order').allTextContents(), ['01', '02', '03', '04', '05', '06', '07', '08', '09']);
  await page.clock.runFor(1400);
  await eventually(() => itinerary.locator('[aria-current="step"] .au-status').textContent().then(text => text === 'Working'), 'the itinerary retained a stale collection status after the accepted prefix changed');
  assert.deepEqual(await position(), [1, 9]);
  await page.clock.runFor(1400);
  await page.clock.runFor(3200);
  await title(page, demoIds[1]);
  assert.deepEqual(await position(), [2, 9]);
  assert.equal(await itinerary.locator('[data-au-demo-case][aria-current="step"]').getAttribute('data-au-demo-case'), demoIds[1]);
  if (process.env.CASEPATH_BROWSER_RECEIPTS) await page.screenshot({path: '/tmp/casepath-visual-itinerary-390.png', fullPage: true});
  await page.locator('.au-nav [data-au-nav="work"]').click();
});

for (const reducedMotion of ['no-preference', 'reduce']) test(`mobile inspection navigates and centers every real step while retaining forks, excluded routes and free pan (${reducedMotion})`, async t => {
  const page = await fixturePage(t, {width: 390, height: 844});
  await page.emulateMedia({reducedMotion});
  await open(page, processedId);
  await title(page, processedId);
  const record = await page.evaluate(id => structuredClone(window.__fixture.envelopes[id].state), processedId);
  const ids = record.graph.nodes.map(node => node.node_id);
  assert.equal(ids.length, 11);
  assert.equal(record.graph.edges.length, 13);
  const topology = () => page.locator('[data-au-edge]').evaluateAll(edges => edges.map(edge => [edge.dataset.auEdge, edge.dataset.state]));
  const before = await topology();
  assert.equal(before.length, record.graph.edges.length);
  assert.deepEqual(sorted(await page.locator('[data-au-node]').evaluateAll(nodes => nodes.map(node => node.dataset.auNode))), sorted(ids));
  const inspection = page.locator('.au-mobile-inspection[data-au-node-inspection]');
  assert.equal(await inspection.isVisible(), true);
  const previous = inspection.locator('[data-au-node-previous]'), next = inspection.locator('[data-au-node-next]');
  const label = control => control.getAttribute('aria-label').then(async text => text || await control.innerText());
  assert.match(await label(previous), /previous.*step|step.*previous/i);
  assert.match(await label(next), /next.*step|step.*next/i);
  await page.locator(`[data-au-node="${ids[0]}"]`).click();
  assert.equal(await previous.isDisabled(), true);
  assert.equal(await next.isDisabled(), false);
  const assertStep = async index => {
    assert.match(await inspection.locator('[data-au-inspection-position]').innerText(), new RegExp(`Step\\s+${index + 1}\\s+of\\s+${ids.length}\\b`, 'i'));
    assert.equal(await page.locator('[data-au-node][aria-pressed="true"]').getAttribute('data-au-node'), ids[index]);
    assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'), ids[index]);
    const geometry = await page.evaluate(id => {
      const viewport = document.querySelector('[data-au-graph-pan]'), node = document.querySelector(`[data-au-node="${id}"]`), area = viewport.getBoundingClientRect(), bounds = node.getBoundingClientRect();
      return {left: bounds.left, right: bounds.right, viewportLeft: area.left, viewportRight: area.right, centerDifference: Math.abs((bounds.left + bounds.right - area.left - area.right) / 2), scroll: viewport.scrollLeft, maximum: viewport.scrollWidth - viewport.clientWidth};
    }, ids[index]);
    assert.ok(geometry.left >= geometry.viewportLeft - 1 && geometry.right <= geometry.viewportRight + 1, 'the selected real step must be visible in the mobile graph');
    if (geometry.scroll > 1 && geometry.scroll < geometry.maximum - 1) assert.ok(geometry.centerDifference <= 3, `mobile inspection must center the actual selected node: ${JSON.stringify(geometry)}`);
  };
  await assertStep(0);
  for (let index = 1; index < ids.length; index++) {
    await next.scrollIntoViewIfNeeded();
    await next.click();
    if (reducedMotion === 'reduce') assert.equal(await page.evaluate(() => document.getAnimations().filter(animation => animation.playState === 'running').length), 0, 'reduced motion must suppress navigation animation');
    await assertStep(index);
    const selectedVisible = await page.locator('[data-au-node][aria-pressed="true"]').evaluate(element => {
      const bounds = element.getBoundingClientRect();
      return bounds.top >= 15 && bounds.bottom <= innerHeight - 15;
    });
    assert.equal(selectedVisible, true, 'explicit inspection keeps the selected real step inside the browser viewport');
    if (index < ids.length - 1) assert.equal(await next.evaluate(element => document.activeElement === element), true, 'enabled inspection controls retain their accessible focus');
  }
  assert.equal(await next.isDisabled(), true);
  assert.equal(await previous.isDisabled(), false);
  await previous.click();
  await assertStep(ids.length - 2);
  const excludedId = record.evaluation.nodes.find(node => node.activation === 'false').node_id;
  await page.locator(`[data-au-node="${excludedId}"]`).click();
  assert.equal(await page.locator(`[data-au-node="${excludedId}"]`).getAttribute('aria-pressed'), 'true', 'an excluded branch remains inspectable without becoming applicable');
  assert.equal(await page.locator(`[data-au-node="${excludedId}"]`).getAttribute('data-status'), 'inactive');
  await page.evaluate(() => { const viewport = document.querySelector('[data-au-graph-pan]'); viewport.scrollLeft = (viewport.scrollWidth - viewport.clientWidth) * .7; viewport.dispatchEvent(new Event('scroll')); });
  const panned = await page.locator('[data-au-graph-pan]').evaluate(element => element.scrollLeft);
  await page.evaluate(() => window.__controller.refresh());
  assert.equal(await page.locator('[data-au-graph-pan]').evaluate(element => element.scrollLeft), panned, 'a matching update must preserve arbitrary free panning');
  assert.equal(await page.locator('[data-au-node][aria-pressed="true"]').getAttribute('data-au-node'), excludedId);
  assert.deepEqual(await topology(), before, 'inspection order cannot alter recorded forks or route applicability');
  await next.click();
  await assertStep(ids.indexOf(excludedId) + 1);
  if (process.env.CASEPATH_BROWSER_RECEIPTS) await page.screenshot({path: `/tmp/casepath-visual-inspection-390-${reducedMotion}.png`, fullPage: true});
});

test('collection search retains a persistent input affordance and visible focus while filtering exact case IDs', async t => {
  for (const width of [1440, 390]) {
    const page = await fixturePage(t, {width, height: 844});
    const input = page.locator('[data-au-claim-search]');
    const style = () => input.evaluate(element => { const css = getComputedStyle(element); return {border: Number.parseFloat(css.borderBottomWidth), borderStyle: css.borderBottomStyle, shadow: css.boxShadow, outline: Number.parseFloat(css.outlineWidth), outlineStyle: css.outlineStyle, focusVisible: element.matches(':focus-visible'), height: element.getBoundingClientRect().height}; });
    const idle = await style();
    assert.ok(idle.border >= 1 && idle.borderStyle !== 'none', 'search must remain visibly underlined before focus');
    assert.match(idle.shadow, /inset/, 'search retains its subtle inset affordance');
    assert.ok(idle.height >= 44);
    await input.focus();
    const focused = await style();
    assert.equal(focused.focusVisible, true);
    assert.ok(focused.outline >= 2 && focused.outlineStyle !== 'none', 'keyboard search focus must remain visible');
    await input.fill(demoIds[0]);
    await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 1), 'focused search did not retain exact case ID filtering');
    assert.equal(await page.locator('[data-au-claim-row]').getAttribute('data-au-claim-row'), demoIds[0]);
    assert.equal(await input.evaluate(element => document.activeElement === element), true, 'filtering must preserve the search input focus');
    assert.ok(new URLSearchParams(new URL(page.url()).hash.split('?')[1]).get('q') === demoIds[0]);
    if (process.env.CASEPATH_BROWSER_RECEIPTS) await page.screenshot({path: `/tmp/casepath-visual-search-${width}.png`, fullPage: true});
  }
});

test('a working claim keeps completed step and action labels scoped to Completed', async t => {
  const page = await fixturePage(t);
  const expected = await page.evaluate(id => {
    const state = window.__fixture.envelopes[id].state;
    state.status = 'running';
    return {nodes: structuredClone(state.evaluation.nodes), actions: structuredClone(state.actions)};
  }, processedId);
  await open(page, processedId);
  await title(page, processedId);
  assert.equal(await page.locator('.au-work-head .au-status').innerText(), 'Working');
  const completedNodes = page.locator('[data-au-node][data-status="completed"]');
  assert.ok(await completedNodes.count() > 0, 'the accepted record must include completed steps within a working claim');
  for (const label of await completedNodes.locator('.au-node-state').allTextContents()) assert.equal(label, 'Completed');
  const actionLabels = await page.locator('.au-recorded-actions .au-action-heading span').allTextContents();
  assert.ok(actionLabels.length > 0, 'the accepted record must include completed actions');
  for (const label of actionLabels) assert.equal(label, 'Completed');
  const id = await completedNodes.first().getAttribute('data-au-node');
  await completedNodes.first().click();
  assert.equal(await page.locator('.au-step-status').innerText(), 'Completed');
  assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'), id);
  const saved = JSON.parse(await page.locator('[data-au-disclosure="claim-record"] pre').textContent()).state;
  assert.equal(saved.status, 'running');
  assert.deepEqual(saved.evaluation.nodes, expected.nodes);
  assert.deepEqual(saved.actions, expected.actions, 'presentation labels cannot rewrite the accepted action status or receipt');
});

test('the desktop demonstration overview keeps all nine numbered cases visible while retaining each exact original subject', async t => {
  const page = await fixturePage(t, {presentationSuite: 'replay', width: 1440, height: 900});
  await page.locator('.au-nav [data-au-nav="demonstration"]').click();
  const rows = page.locator('.au-demo-selection [data-au-demo-case]');
  assert.equal(await rows.count(), 9);
  const geometry = await rows.evaluateAll(elements => elements.map(element => ({id: element.dataset.auDemoCase, number: element.querySelector('.au-demo-order').textContent, ...element.getBoundingClientRect().toJSON()})));
  assert.deepEqual(geometry.map(row => row.number), ['01', '02', '03', '04', '05', '06', '07', '08', '09']);
  for (const row of geometry) assert.ok(row.top >= 0 && row.bottom <= 900, `all nine itinerary positions must remain in the desktop overview: ${JSON.stringify(row)}`);
  const columns = await page.locator('.au-demo-selection > section').evaluateAll(elements => elements.map(element => element.getBoundingClientRect().x));
  assert.equal(new Set(columns).size, 3, 'the desktop overview groups its three domains into adjacent columns');
  for (const id of demoIds) {
    const row = page.locator(`[data-au-demo-case="${id}"]`), subject = originals.find(original => original.claim_id === id).subject;
    const preview = row.locator('button > span');
    assert.equal(await preview.textContent(), subject, 'a compact itinerary cannot rewrite the original subject');
    assert.equal(await preview.getAttribute('title') || await row.locator('button').getAttribute('title'), subject, 'the full original subject remains available on the preview');
    assert.ok((await row.locator('button').getAttribute('aria-label') || await row.locator('button').textContent()).includes(subject), 'the complete subject remains in the accessible case name');
    const style = await preview.evaluate(element => { const css = getComputedStyle(element); return {whiteSpace: css.whiteSpace, overflow: css.overflow, ellipsis: css.textOverflow, height: element.getBoundingClientRect().height, lineHeight: Number.parseFloat(css.lineHeight)}; });
    assert.equal(style.whiteSpace, 'nowrap');
    assert.equal(style.ellipsis, 'ellipsis');
    assert.ok(style.height <= style.lineHeight + 1, 'desktop subject previews remain one readable line');
    assert.equal(await row.locator('.au-status').innerText(), 'Investigation complete');
  }
  if (process.env.CASEPATH_BROWSER_RECEIPTS) {
    await page.screenshot({path: '/tmp/casepath-visual-itinerary-1440.png', fullPage: true});
    fs.writeFileSync('/tmp/casepath-visual-itinerary-1440.json', JSON.stringify(geometry, null, 2));
  }
});

test('pending raw navigation blocks automatic Live Start, timed advancement and delayed replay before route events dispatch', async t => {
  const freezeRoutes = page => page.evaluate(() => {
    window.__freezeRouteEvents = event => event.stopImmediatePropagation();
    window.addEventListener('hashchange', window.__freezeRouteEvents, true);
    window.addEventListener('popstate', window.__freezeRouteEvents, true);
  });
  const resumeRoutes = page => page.evaluate(() => {
    window.removeEventListener('hashchange', window.__freezeRouteEvents, true);
    window.removeEventListener('popstate', window.__freezeRouteEvents, true);
    window.dispatchEvent(new Event('hashchange'));
  });
  const id = demoIds[0], opening = await fixturePage(t, {originalStartId: id, holdId: id, holdRemaining: 1});
  await opening.locator('.au-nav [data-au-nav="demonstration"]').click();
  await opening.locator('[data-au-demo-mode="live"]').click();
  await opening.locator('[data-au-demo-play]').click();
  await eventually(() => opening.evaluate(() => window.__fixture.held.length === 1), 'the original opening GET was not held');
  await freezeRoutes(opening);
  await opening.evaluate(() => {
    location.hash = '#autonomous/cases';
    for (const held of window.__fixture.held.splice(0)) held.release();
  });
  await opening.evaluate(async () => { for (let turn = 0; turn < 20; turn++) await Promise.resolve(); });
  await opening.clock.runFor(1000);
  assert.equal((await calls(opening, `/claims/${id}/start`)).length, 0, 'a verified stale GET cannot reuse Play authorization after the URL changes');
  await resumeRoutes(opening);
  await eventually(() => opening.locator('[data-au-claim-row]').count().then(count => count === 150), 'the pending raw route did not restore Cases');
  assert.equal((await calls(opening, `/claims/${id}/start`)).length, 0);

  const timed = await fixturePage(t, {presentationSuite: 'live'});
  await timed.evaluate(ids => { for (const id of ids) window.__fixture.envelopes[id] = structuredClone(window.__fixture.acceptedHistories[id][2]); }, demoIds);
  await timed.locator('.au-nav [data-au-nav="demonstration"]').click();
  await timed.locator('[data-au-demo-mode="live"]').click();
  await timed.locator('[data-au-demo-play]').click();
  await title(timed, id);
  await freezeRoutes(timed);
  await timed.evaluate(() => { location.hash = '#autonomous/cases'; });
  await timed.clock.runFor(5000);
  assert.equal((await calls(timed, `/claims/${demoIds[1]}/snapshot`)).length, 0, 'a timed presentation cannot open its next case while product navigation is pending');
  assert.deepEqual(await timed.evaluate(() => window.__fixture.calls.filter(call => call.method === 'POST')), []);
  await resumeRoutes(timed);
  await eventually(() => timed.locator('[data-au-claim-row]').count().then(count => count === 150), 'timed pending navigation did not restore Cases');

  const replay = await fixturePage(t, {presentationSuite: 'replay', holdReplayId: id, holdReplayThrough: 1});
  await replay.locator('.au-nav [data-au-nav="demonstration"]').click();
  await replay.locator('[data-au-demo-play]').click();
  await title(replay, id);
  await replay.clock.runFor(1400);
  await eventually(() => replay.evaluate(() => window.__fixture.held.some(held => held.kind === 'replay')), 'the next accepted replay prefix was not held');
  await freezeRoutes(replay);
  await replay.evaluate(() => {
    location.hash = '#autonomous/cases';
    for (const held of window.__fixture.held.splice(0)) held.release();
  });
  await replay.evaluate(async () => { for (let turn = 0; turn < 20; turn++) await Promise.resolve(); });
  await replay.clock.runFor(5000);
  assert.equal(new URL(replay.url()).hash, '#autonomous/cases', 'a delayed accepted replay prefix cannot replace the newly selected product route');
  assert.equal((await calls(replay, `/claims/${id}/replay`)).length, 2, 'the abandoned replay cannot request another prefix');
  assert.equal((await calls(replay, `/claims/${demoIds[1]}/replay`)).length, 0);
  assert.deepEqual(await replay.evaluate(() => window.__fixture.calls.filter(call => call.method === 'POST')), []);
  await resumeRoutes(replay);
  await eventually(() => replay.locator('[data-au-claim-row]').count().then(count => count === 150), 'delayed replay cancellation did not retain Cases');
});
