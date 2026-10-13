'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {gunzipSync} = require('node:zlib');
const {createHash} = require('node:crypto');
const {setTimeout: delay} = require('node:timers/promises');
const {execFileSync} = require('node:child_process');
const {chromium} = require('playwright');

const root = path.resolve(__dirname, '..');
const base = '/api/claim-loops/v1/autonomous';
const captured = JSON.parse(gunzipSync(fs.readFileSync(path.join(root, 'design/evidence-path/recorded-fixtures.json.gz')))).responses;
const historicalIds = captured[`${base}/claims`].claims.map(row => row.claim_id);
const completeStatusIds = historicalIds.filter(id => {
  const state = captured[`${base}/claims/${id}`].state;
  return state.outcome && !state.deferral;
}).slice(0, 3);
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
const referenceIds = [
  'clm_314f2d309fea25e6','clm_4a07dbbbd859a3ce','clm_95d08975bc575592',
  'clm_0f4f13b1e3e1328c','clm_393285577dcb12c4','clm_4a53299cfe619303',
  'clm_2c55cdd816b1d0e8','clm_543f08f2415b2a33','clm_7dbd7c7d1c4ddf90',
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

let acceptedFixture;
let sourceDrawerFixture;
let nativeReferenceFixture;
function referenceFixture() {
  if (!nativeReferenceFixture) {
    // Run the native reference controller and GET router in a disposable DB.
    // No authored assessment, model response, provider or public write is used.
    const script = `
import base64,json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path[:0]=[str(Path.cwd()/'casepath-api'),str(Path.cwd()/'casepath-api/tests'),str(Path.cwd()/'casepath-qa')]
from fastapi import FastAPI
from fastapi.testclient import TestClient
from casepath_api.autonomous_api_v1 import create_autonomous_router
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.autonomous_reference_v1 import ReferenceProfile
from casepath_api.autonomous_controller_v1 import AutonomousController
from test_complete_reference_intake_v1 import service_at,admit
from importlib.util import spec_from_file_location,module_from_spec
spec=spec_from_file_location('existing_clock',Path.cwd()/'casepath-qa/build-prior-assessment-fixture-v1.py')
clock=module_from_spec(spec);spec.loader.exec_module(clock)
with tempfile.TemporaryDirectory(prefix='casepath-native-reference-qa-') as temporary,patch('casepath_api.autonomous_store_v1.datetime',clock.FixtureClock):
 corpus=CanonicalCorpus();service=service_at(Path(temporary)/'claims.sqlite',corpus);app=FastAPI();app.include_router(create_autonomous_router(lambda:service,corpus_getter=lambda:corpus))
 output={'snapshots':{},'prefixes':{},'unprocessed':{},'sources':{},'raw_sources':{},'knowledge':None,'profile_sha256':ReferenceProfile().sha256,'earlier_context':None}
 try:
  with TestClient(app) as client:
   base='/api/claim-loops/v1/autonomous'
   def get(path):
    response=client.get(base+path);response.raise_for_status();return response.json()
   ids=json.loads(sys.argv[1])
   for cid in ids:
    output['unprocessed'][cid]=get('/claims/'+cid+'/snapshot')
    if cid=='clm_7dbd7c7d1c4ddf90':
     # An actual earlier ordinary engine context, stopped before any authored
     # model result. Reference admission must append and preserve its prefix.
     packet=corpus.packet(cid);service.store.admit_original(cid,packet,expected_revision=0,expected_state_sha256=packet['initial_state_sha256'],idempotency_key='qa-earlier-original')
     class NoTransport:
      def interpret(self,context,identity):raise ValueError('Isolated ordinary context boundary; no provider transport or interpretation result.')
     previous=AutonomousController(service.store,corpus._corpus.static_policy(),NoTransport())
     try:
      earlier=previous.run(cid);output['earlier_context']={'claim_id':cid,'revision':earlier['revision'],'state_sha256':earlier['state_sha256']}
     finally:previous.shutdown()
     service.store.add_sources(cid,ReferenceProfile().files(cid),expected_revision=earlier['revision'],expected_state_sha256=earlier['state_sha256'],idempotency_key='qa-reference-after-earlier')
    else:admit(service,corpus,cid)
    state=service.run(cid)
    assert state['outcome']['assessment_status']=='complete'
    output['snapshots'][cid]=get('/claims/'+cid+'/snapshot')
    output['prefixes'][cid]={str(seq):get('/claims/'+cid+'/replay?through_seq='+str(seq)) for seq in range(state['revision']+1)}
    for descriptor in state['source_descriptors']:
     identity=cid+'/'+descriptor['artifact_id'];output['sources'][identity]=get('/sources/'+identity+'/text')
     response=client.get(base+'/sources/'+identity);response.raise_for_status();output['raw_sources'][identity]=base64.b64encode(response.content).decode()
   output['knowledge']=get('/knowledge')
  print(json.dumps(output,sort_keys=True))
 finally:service.shutdown()
`;
    const encoded = process.env.CASEPATH_REFERENCE_FIXTURE
      ? fs.readFileSync(process.env.CASEPATH_REFERENCE_FIXTURE,'utf8')
      : execFileSync(process.env.CASEPATH_PYTHON || '/workspace/casepath/.runtime/casepath-dev-v2/venv/bin/python', ['-c',script,JSON.stringify(referenceIds)],
        {cwd:root,encoding:'utf8',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'},maxBuffer:128*1024*1024});
    nativeReferenceFixture = JSON.parse(encoded);
    if (process.env.CASEPATH_REFERENCE_FIXTURE_OUTPUT) fs.writeFileSync(process.env.CASEPATH_REFERENCE_FIXTURE_OUTPUT,encoded);
  }
  return nativeReferenceFixture;
}
function pdfDrawerFixture() {
  if (!sourceDrawerFixture) {
    const binding = corpusManifest.claims.find(row => row.observable_artifacts.some(source => source.media_type === 'application/pdf'));
    const descriptor = binding.observable_artifacts.find(source => source.media_type === 'application/pdf');
    const bytes = fs.readFileSync(path.join(corpusRoot, descriptor.path));
    assert.equal(sha(bytes), descriptor.sha256);
    const text = JSON.parse(execFileSync(process.env.CASEPATH_PYTHON || '/workspace/casepath/.runtime/casepath-dev-v2/venv/bin/python',
      ['-c', 'import json,sys; from pypdf import PdfReader; print(json.dumps("\\n".join(page.extract_text() or "" for page in PdfReader(sys.argv[1]).pages)))', path.join(corpusRoot, descriptor.path)],
      {encoding: 'utf8', env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}}));
    assert.ok(text.length > 100);
    sourceDrawerFixture = {claim_id: binding.claim_id, descriptor: {...descriptor, claim_id: binding.claim_id}, bytes: bytes.toString('base64'), text};
  }
  return sourceDrawerFixture;
}
function mimeDrawerFixture() {
  const binding=corpusManifest.claims.find(row=>row.claim_id==='clm_06400c75399e7f37');
  const descriptor=binding.observable_artifacts.find(source=>source.role==='customer_message');
  const intake=JSON.parse(fs.readFileSync(path.join(corpusRoot,binding.claim.path),'utf8'));
  const bytes=fs.readFileSync(path.join(corpusRoot,descriptor.path));
  assert.equal(sha(bytes),descriptor.sha256);assert.equal(sha(Buffer.from(intake.customer_message.raw_file.content_base64,'base64')),descriptor.sha256);
  return {claim_id:binding.claim_id,descriptor:{...descriptor,claim_id:binding.claim_id},intake,bytes:bytes.toString('base64'),text:bytes.toString('utf8')};
}
function priorAssessmentFixture() {
  if (!acceptedFixture) {
    const encoded = process.env.CASEPATH_PRIOR_ASSESSMENT_FIXTURE
      ? fs.readFileSync(process.env.CASEPATH_PRIOR_ASSESSMENT_FIXTURE, 'utf8')
      : execFileSync(process.env.CASEPATH_PYTHON || path.join(root, '.runtime/casepath-dev-v2/venv/bin/python'),
        [path.join(root, 'casepath-qa/build-prior-assessment-fixture-v1.py')],
        {encoding: 'utf8', env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}, maxBuffer: 64 * 1024 * 1024});
    acceptedFixture = JSON.parse(encoded);
  }
  return acceptedFixture;
}
const readCacheKey='casepath.read-cache/1';
function seededReadCache(snapshot,knowledge=null){
  const at=Date.parse('2026-10-09T12:00:00Z'),entry={at,state:clone(snapshot.state),projection:clone(snapshot.projection),cursor:snapshot.state.revision,history:clone(snapshot.events)},material={contract:readCacheKey,api:`http://localhost:41999${base}`,saved_at:at,snapshots:[entry],knowledge:knowledge?{at,value:clone(knowledge)}:null};
  return {...material,sha256:sha(canonical(material))};
}
function resealReadCache(value){const material=clone(value);delete material.sha256;return {...material,sha256:sha(canonical(material))};}

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
    contract:'casepath.autonomous-claim/1.0.0',
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
  const acceptedHistories = {}, authoredEvents = {}, controlHistories = {};
  if (config.controlRetryId) {
    // Authored command-authority boundary only: no model facts or outcome.
    // A lost response advances revision while leaving the requested command
    // legal; the explicit retry then returns its definite operational result.
    const id = config.controlRetryId, original = clone(envelopes[id].state);
    authoredEvents[id] = [];
    controlHistories[id] = [1, 2, 3].map(revision => {
      const paused = config.controlRetryAction === 'resume' ? revision < 3 : revision === 3;
      const state = {...clone(original), revision, mode: 'started', status: paused ? 'deferred' : 'running', phase: paused ? 'paused' : 'acquiring',
        deferral: paused ? {code: 'paused', reason: 'Authored command boundary is paused.'} : null,
        graph: {claim_id: id, title: 'Command retry boundary', graph_sha256: sha('command retry graph'),
          nodes: [{node_id: 'inspect_packet', label: 'Inspect original packet', entry: true}], edges: []},
        evaluation: {nodes: [{node_id: 'inspect_packet', execution_state: 'ready'}], edges: [], documents: []}};
      delete state.state_sha256; delete state.last_event_sha256;
      state.state_sha256 = sha(canonical(state));
      const event = {seq: revision, claim_id: id, revision, state_sha256: state.state_sha256,
        previous_event_sha256: authoredEvents[id].at(-1)?.event_sha256 || null,
        kind: revision === 1 ? 'intake' : 'work.phase', payload: {summary: 'Authored command retry boundary'}};
      event.event_sha256 = sha(canonical(event)); state.last_event_sha256 = event.event_sha256;
      authoredEvents[id].push(event);
      return {state, projection: {claim_id: id, revision, state_sha256: state.state_sha256}};
    });
    envelopes[id] = clone(controlHistories[id][0]);
  }
  if (config.pdfDrawer) {
    // A source-viewer boundary fixture, with real original PDF bytes and text.
    // It supplies no process, facts, model interpretation or legal outcome.
    const pdf = pdfDrawerFixture(), envelope = envelopes[pdf.claim_id], state = envelope.state;
    const source = {...pdf.descriptor, text: pdf.text, text_sha256: sha(pdf.text), complete: true, extraction: 'pdf_text'};
    Object.assign(state, {revision: 1, state_sha256: sha('isolated PDF viewer boundary state'), last_event_sha256: sha('isolated PDF viewer boundary event'), mode: 'saved', status: 'received', phase: 'received', acquired_sources: [source]});
    Object.assign(envelope.projection, {revision: state.revision, state_sha256: state.state_sha256});
    sources[`${pdf.claim_id}/${pdf.descriptor.artifact_id}`] = source;
    rawSources[`${pdf.claim_id}/${pdf.descriptor.artifact_id}`] = pdf.bytes;
  }
  if(config.mimeDrawer){
    // Real original .eml bytes and parsed intake body, isolated at the source
    // display boundary. This supplies no inferred facts, process or outcome.
    const mime=mimeDrawerFixture(),envelope=envelopes[mime.claim_id],state=envelope.state;
    const source={...mime.descriptor,text:mime.text,text_sha256:sha(mime.text),complete:true,extraction:'utf8_text'},variant=config.mimeDrawer.replace(/-plain$/,'');
    if(config.mimeDrawer.endsWith('-plain')){source.media_type='text/plain';state.source_descriptors.find(row=>row.artifact_id===source.artifact_id).media_type='text/plain';}
    state.original_binding={claim_id:mime.claim_id,intake:clone(mime.intake),source_map:[{artifact_id:source.artifact_id,original_artifact_id:mime.intake.customer_message.raw_file.artifact_id,sha256:source.sha256}]};
    if(variant==='foreign')state.original_binding.claim_id=demoIds[0];
    if(variant==='unbound')state.original_binding.source_map=[];
    if(variant==='supporting')state.source_descriptors.find(row=>row.artifact_id===source.artifact_id).role='supporting_document';
    Object.assign(state,{revision:1,state_sha256:sha(`isolated MIME display boundary ${config.mimeDrawer}`),last_event_sha256:sha('isolated MIME display event'),mode:'saved',status:'received',phase:'received',acquired_sources:[source]});
    Object.assign(envelope.projection,{revision:state.revision,state_sha256:state.state_sha256});
    sources[`${mime.claim_id}/${source.artifact_id}`]=source;rawSources[`${mime.claim_id}/${source.artifact_id}`]=mime.bytes;
  }
  if (config.presentationSuite) for (const id of demoIds) {
    // Authored scheduler/navigation control histories. Their only outcome is
    // deterministic packet-inspection completion; they supply no model result,
    // legal conclusion or performance evidence. Real replay acceptance uses
    // the separately exported 28-prefix journal below.
    const original = clone(envelopes[id]);
    original.state.last_event_sha256 = null;
    const openingFields = {...original.state}; delete openingFields.state_sha256;
    original.state.state_sha256 = sha(canonical(openingFields));
    original.projection.state_sha256 = original.state.state_sha256;
    envelopes[id] = clone(original);
    authoredEvents[id] = [];
    acceptedHistories[id] = [original, ...[1, 2].map(revision => {
      const state = {...clone(original.state), revision, mode: 'started',
        status: revision === 1 ? 'running' : 'completed', phase: revision === 1 ? 'acquiring' : 'complete',
        outcome: revision === 2 && config.presentationOutcome !== false ? {status: 'inspection_fixture_complete', title: 'Fixture packet inspection complete', summary: 'Authored scheduler fixture inspected its original packet. No legal or model result is supplied.'} : null,
        graph: {claim_id: id, title: 'Deterministic source inspection fixture', graph_sha256: sha(`fixture graph ${id}`),
          nodes: [{node_id: 'inspect_packet', label: 'Inspect original packet', entry: true}], edges: []},
        evaluation: {nodes: [{node_id: 'inspect_packet', execution_state: revision === 1 ? 'ready' : 'completed'}], edges: [], documents: []}};
      delete state.state_sha256; delete state.last_event_sha256;
      state.state_sha256 = sha(canonical(state));
      const event = {seq: revision, claim_id: id, revision, state_sha256: state.state_sha256,
        previous_event_sha256: authoredEvents[id].at(-1)?.event_sha256 || null,
        kind: revision === 1 ? 'intake' : state.outcome ? 'outcome.recorded' : 'work.phase',
        payload: state.outcome ? {outcome: state.outcome} : {summary: 'Authored packet-inspection scheduler fixture'}};
      event.event_sha256 = sha(canonical(event)); state.last_event_sha256 = event.event_sha256;
      authoredEvents[id].push(event);
      return {state, projection: {claim_id: id, revision, state_sha256: state.state_sha256}};
    })];
    if(config.presentationPublication&&id===demoIds[0]){
      // Typed Play/publication boundary only. No model facts, legal result,
      // inferred source passage or real qualification is supplied by this mock.
      const publication={knowledge_id:'procedure.packet_inspection_fixture',version:3,knowledge_sha256:sha('authored publication boundary definition'),source_claim_id:id,qualification:{status:'qualified',reason:'Authored playback boundary only; no legal or model result.'},added_document_types:['original_packet_identity'],evidence_recipes:[{document_type:'original_packet_identity',required_fields:['original_file_identity']}]};
      for(const revision of [3,4]){const state={...clone(acceptedHistories[id].at(-1).state),revision,knowledge_published:[publication]};delete state.state_sha256;delete state.last_event_sha256;state.state_sha256=sha(canonical(state));const event={seq:revision,claim_id:id,revision,state_sha256:state.state_sha256,previous_event_sha256:authoredEvents[id].at(-1).event_sha256,kind:revision===3?'knowledge.published':'work.phase',payload:revision===3?{knowledge:publication}:{summary:'Authored phase following the publication boundary.'}};event.event_sha256=sha(canonical(event));state.last_event_sha256=event.event_sha256;authoredEvents[id].push(event);acceptedHistories[id].push({state,projection:{claim_id:id,revision,state_sha256:state.state_sha256}});}
    }
    if (config.presentationSuite === 'replay') envelopes[id] = clone(acceptedHistories[id].at(-1));
  }
  // Lifecycle-code variants reuse recorded settled outcomes. A recorded
  // execution failure must never be relabeled merely by changing its code.
  if (config.completeStatuses) ['completed', 'complete', 'resolved'].forEach((status, index) => { envelopes[completeStatusIds[index]].state.status = status; });
  if (config.recordedHistoryId) envelopes[config.recordedHistoryId] = clone(captured[`${base}/claims/${config.recordedHistoryId}`]);
  const accepted = config.priorAssessment ? clone(priorAssessmentFixture()) : null;
  if (accepted) {
    const snapshot = config.acceptedPrefix ? accepted.prefixes[config.acceptedPrefix] : accepted.snapshots[config.priorAssessment];
    assert.ok(snapshot, 'the browser starts from an exported verified prefix');
    envelopes[accepted.claim_id] = {state: snapshot.state, projection: snapshot.projection};
    Object.assign(sources, accepted.sources);
  }
  const reference = config.referenceFixture ? referenceFixture() : null;
  if (reference) {
    for (const id of referenceIds) {
      const snapshot = clone(config.referenceUnprocessed || config.referenceUnprocessedIds?.includes(id) ? reference.unprocessed[id] : reference.snapshots[id]);
      envelopes[id] = {state:snapshot.state,projection:snapshot.projection};
      authoredEvents[id] = snapshot.events;
    }
    Object.assign(sources,reference.sources);Object.assign(rawSources,reference.raw_sources);
  }
  const rows = Object.values(envelopes).map(({state}) => ({
    claim_id: state.claim_id, title: state.title, origin: state.origin || (state.original_binding ? 'canonical_original' : historicalIds.includes(state.claim_id) ? 'native_intake' : undefined), mode: state.mode, status: state.status,
    phase: state.phase, phase_summary: state.phase_summary, revision: state.revision,
    state_sha256: state.state_sha256, policy_id:state.policy_id,outcome: state.outcome,
    source_preview: state.origin==='canonical_original'?{text:[...String(state.source_preview?.text||'')].slice(0,240).join('')}:undefined, browse_metadata: state.browse_metadata || {},
  }));
  assert.equal(rows.filter(row => row.origin === 'canonical_original').length, 150);
  assert.equal(rows.filter(row => row.origin === 'native_intake').length, 9);
  return {envelopes, sources, rawSources, acceptedHistories, authoredEvents, controlHistories, accepted,reference:reference ? {prefixes:Object.fromEntries((config.referenceReplayIds || referenceIds).map(id=>[id,reference.prefixes[id]]))} : null,
    recordedHistory: config.recordedHistoryId ? clone(captured[`${base}/claims/${config.recordedHistoryId}/events?after=0`].events) : [],
    acceptedEvents: accepted ? clone((config.acceptedPrefix ? accepted.prefixes[config.acceptedPrefix] : accepted.snapshots[config.priorAssessment]).events) : [],
    acceptedPrefixes: accepted ? config.priorAssessment === 'failed' ? accepted.failure_prefixes : accepted.prefixes : {},
    recordedKnowledgeData:reference?.knowledge || (config.recordedKnowledge?clone(captured[`${base}/knowledge`]):null),
    rows: config.rememberedNativeId ? rows.filter(row => row.claim_id !== config.rememberedNativeId) : rows};
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
  page.setDefaultTimeout(5000);
  page.on('pageerror', error => errors.push(error.message));
  t.after(async () => {
    if (process.env.CASEPATH_BROWSER_DIAGNOSTICS) {
      fs.mkdirSync(process.env.CASEPATH_BROWSER_DIAGNOSTICS,{recursive:true});
      const name=t.name.replace(/[^a-z0-9]+/gi,'-').slice(0,180);
      fs.writeFileSync(path.join(process.env.CASEPATH_BROWSER_DIAGNOSTICS,`${name}.json`),JSON.stringify(await page.evaluate(()=>({url:location.href,text:document.body.innerText,dialogs:[...document.querySelectorAll('dialog')].map(row=>({class:row.className,open:row.open})),active:document.activeElement?.outerHTML,revision:document.querySelector('[data-au-revision]')?.dataset.auRevision,record:document.querySelector('[data-au-record-content] pre')?.textContent,calls:window.__fixture?.calls,errors:window.__fixture?.startViolations})),null,2));
    }
    const writes = await page.evaluate(() => window.__fixture?.calls.filter(call => call.method !== 'GET') || []);
    const startViolations = await page.evaluate(() => window.__fixture?.startViolations || []);
    await page.evaluate(() => window.__controller?.destroy());
    await context.close();
    if (config.controlRetryId) {
      assert.ok(writes.every(call => call.method === 'POST' && call.url === `${base}/claims/${config.controlRetryId}/${config.controlRetryAction}`), 'only the explicitly configured guarded command POST is permitted');
      assert.deepEqual(startViolations, [], 'the command retry must carry the original guard and literal unchanged body');
    } else if (config.originalStartId || config.presentationSuite === 'live') {
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
  await page.goto('http://localhost:41999/' + (config.initialFragment || ''));
  if (!config.nativeClock) {
    const time = new Date('2026-10-09T12:00:00Z');
    await page.clock.install({time});
    await page.clock.pauseAt(time);
  }
  await mountFixture(page, config);
  return page;
}

async function mountFixture(page, config = {}) {
  const cssBytes=fs.readFileSync(process.env.CASEPATH_BROWSER_CSS_ASSET || path.join(root,'casepath/assets/autonomous-workspace-v1.css'));
  const javascriptBytes=fs.readFileSync(process.env.CASEPATH_BROWSER_JS_ASSET || path.join(root,'casepath/assets/autonomous-workspace-v1.js'));
  const style=await page.addStyleTag({content:cssBytes.toString('utf8')}),script=await page.addScriptTag({content:javascriptBytes.toString('utf8')});
  const injectedAssets={javascript:sha(await script.evaluate(element=>element.textContent)),css:sha(await style.evaluate(element=>element.textContent))};
  assert.deepEqual(injectedAssets,{javascript:sha(javascriptBytes),css:sha(cssBytes)},'the actual native DOM contains exactly the selected working asset bytes');
  await page.evaluate(assets=>window.__injectedAssets=assets,injectedAssets);
  await page.evaluate(({data, config, base}) => {
    window.__fixture = {...data, ...config, calls: [], held: [], splitRevision: {}, startPosts: 0, startViolations: [], suitePosts: {}, suiteReads: {},activeSnapshotReads:0,peakSnapshotReads:0};
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
    fixture.loadAccepted = position => {
      const snapshot = fixture.accepted.snapshots[position] || fixture.accepted.prefixes[position];
      if (!snapshot) throw new Error('No verified fixture position');
      fixture.envelopes[fixture.accepted.claim_id] = {state: structuredClone(snapshot.state), projection: structuredClone(snapshot.projection)};
      fixture.acceptedEvents = structuredClone(snapshot.events);
    };
    const batch = (state, after) => fixture.recordedHistoryId === state.claim_id ? {
      events: structuredClone(fixture.recordedHistory.filter(event => event.seq > after && event.seq <= state.revision)),
      current_revision: state.revision, current_state_sha256: state.state_sha256, cursor_sha256: state.last_event_sha256,
    } : fixture.accepted?.claim_id === state.claim_id ? {
      events: structuredClone(fixture.acceptedEvents.filter(event => event.seq > after && event.seq <= state.revision)),
      current_revision: state.revision, current_state_sha256: state.state_sha256, cursor_sha256: state.last_event_sha256,
    } : fixture.authoredEvents[state.claim_id] ? {
      events: structuredClone(fixture.authoredEvents[state.claim_id].filter(event => event.seq > after && event.seq <= state.revision)),
      current_revision: state.revision, current_state_sha256: state.state_sha256,
      cursor_sha256: state.revision === 0 ? null : state.last_event_sha256,
    } : ({
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
      if (method === 'POST' && fixture.controlRetryId && relative === `/claims/${fixture.controlRetryId}/${fixture.controlRetryAction}`) {
        const body = JSON.parse(init.body), original = fixture.controlHistories[fixture.controlRetryId][0].state, headers = init.headers || {};
        if (body.expected_revision !== original.revision || body.expected_state_sha256 !== original.state_sha256
          || !body.idempotency_key?.startsWith('browser.') || headers['X-CasePath-Agent-Work'] !== '1'
          || headers['Content-Type'] !== 'application/json' || fixture.firstControlBody && fixture.firstControlBody !== init.body) {
          fixture.startViolations.push('Command guard, intent header or exact retry body changed.');
          return response(422, {detail: 'Changed command identity.'});
        }
        fixture.firstControlBody ||= init.body; fixture.controlPosts = (fixture.controlPosts || 0) + 1;
        const result = fixture.controlHistories[fixture.controlRetryId][fixture.controlPosts === 1 ? 1 : 2];
        fixture.envelopes[fixture.controlRetryId] = structuredClone(result);
        if (fixture.controlPosts === 1) throw new TypeError('Isolated command response is uncertain.');
        return response(200, result);
      }
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
        if (fixture.startPosts === 1) {
          if (fixture.holdStart) return new Promise((_resolve, reject) => fixture.held.push({kind: 'start', release: () => reject(new TypeError('Isolated Start network outcome is uncertain.'))}));
          throw new TypeError('Isolated Start network outcome is uncertain.');
        }
        // The explicit retry returns the same accepted result. A concurrent
        // writer advances the live head before the follow-up snapshot.
        advance(state.claim_id);
        return response(200, accepted);
      }
      if (method !== 'GET') return response(405, {detail: 'This browser fixture prohibits writes.'});
      if (relative === '/claims') {
        if (fixture.collectionFailures > 0) { fixture.collectionFailures--; return response(500,{detail:'Isolated collection warm read failed.'}); }
        const limit = Number(parsed.searchParams.get('limit') || 50), offset = Number(parsed.searchParams.get('offset') || 0);
        if (fixture.holdCollections) return new Promise(resolve => fixture.held.push({id: 'collection', release: () => resolve(response(200, {claims: fixture.rows.slice(offset, offset + limit), total: fixture.rows.length, limit, offset}))}));
        return response(200, {claims: fixture.rows.slice(offset, offset + limit), total: fixture.rows.length, limit, offset});
      }
      if (relative === '/knowledge') {
        if(fixture.knowledgeFailures>0){fixture.knowledgeFailures--;return response(500,{detail:'Isolated Knowledge warm read failed.'});}
        const result = response(200, fixture.recordedKnowledgeData || fixture.accepted?.knowledge || {versions: [], uses: [], quarantined: []});
        if (fixture.holdKnowledge) return new Promise(resolve => fixture.held.push({kind: 'knowledge', release: () => resolve(result)}));
        return result;
      }
      if (relative === '/status') {
        const result = response(200, {enabled: true, provider_ready: fixture.providerReady ?? Boolean(fixture.originalStartId || fixture.presentationSuite === 'live'),...fixture.readOnlyStatus ? {read_only:true,writable:false} : {}});
        if (fixture.holdStatus) return new Promise(resolve => fixture.held.push({kind: 'status', release: () => resolve(result)}));
        return result;
      }
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
        if (fixture.reference?.prefixes[id]?.[through] && !fixture.referenceUnprocessed && !fixture.referenceUnprocessedIds?.includes(id)) {
          const prefix=structuredClone(fixture.reference.prefixes[id][through]);
          if(fixture.referenceReplayMissingId===id)return response(404,{detail:'No recorded replay for this original case.'});
          if(fixture.referenceChangedHeadId===id&&through===prefix.current_revision){prefix.current_revision++;prefix.current_head.revision++;}

          if(fixture.holdReplayId===id && through===fixture.holdReplayThrough)return new Promise(resolve=>fixture.held.push({id,kind:'replay',through,release:()=>resolve(response(200,prefix))}));
          return response(200,prefix);
        }
        if (fixture.accepted?.claim_id === id && fixture.acceptedPrefixes[through]) {
          const prefix = structuredClone(fixture.acceptedPrefixes[through]);
          if (fixture.corruptReplayThrough === through) prefix.provenance.sources[0].sha256 = '0'.repeat(64);
          if (fixture.holdReplayId === id && through === fixture.holdReplayThrough) return new Promise(resolve => fixture.held.push({id, kind: 'replay', through, release: () => resolve(response(200, prefix))}));
          if (fixture.replayLatency) await new Promise(resolve => setTimeout(resolve, fixture.replayLatency));
          return response(200, prefix);
        }
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
        if (fixture.readFailures > 0) { fixture.readFailures--; throw new TypeError('Isolated snapshot read interrupted.'); }
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
        if ((fixture.holdSnapshots || fixture.holdIds?.includes(id) || fixture.holdId === id) && (fixture.holdRemaining === undefined || fixture.holdRemaining > 0)) {
          if (fixture.holdRemaining !== undefined) fixture.holdRemaining--;
          fixture.activeSnapshotReads++;fixture.peakSnapshotReads=Math.max(fixture.peakSnapshotReads,fixture.activeSnapshotReads);
          return new Promise(resolve => fixture.held.push({id,kind:'snapshot',release:()=>{fixture.activeSnapshotReads--;resolve(fixture.heldSnapshotStatus ? response(fixture.heldSnapshotStatus,{detail:'Held snapshot transport unavailable.'}) : response(200,snapshot));}}));
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
    if(config.seedReadCache)sessionStorage.setItem('casepath.read-cache/1',JSON.stringify(config.seedReadCache));
    if(config.storageQuota){const set=Storage.prototype.setItem;Storage.prototype.setItem=function(key,value){if(key==='casepath.read-cache/1')throw new DOMException('Isolated cache quota exceeded.','QuotaExceededError');return set.call(this,key,value);};}
    if(config.publicReadOnly)window.CASEPATH_PUBLIC_READ_ONLY=true;
    window.__controller = window.CasePathAutonomous.mount(document.querySelector('#workspace'), {fetch});
  }, {data: fixtureData(config), config, base});
  const hash = new URL(page.url()).hash;
  if (hash.startsWith('#autonomous/claim/') || hash.startsWith('#autonomous/demonstration')) {
    if(config.allowHeldPreview){const id=decodeURIComponent(hash.slice('#autonomous/claim/'.length).split('?')[0]);await eventually(()=>page.locator(`[data-au-preview="catalog"][data-au-preview-claim="${id}"], [data-au-preview="unknown"]`).count().then(count=>count===1),'the held uncached reload did not retain an opening view without accepted content');}
    else await eventually(() => page.locator('[data-au-claim-title]').count().then(count => count === 1), 'the reloaded claim did not render');
  }
  else {
    const params=new URLSearchParams(hash.split('?')[1]),total=hash.includes('scope=added')?(config.rememberedNativeId?8:9):150,requested=Math.max(1,Number(params.get('page'))||1),pageNumber=Math.min(Math.ceil(total/20),requested),expectedRows=Math.min(20,total-(pageNumber-1)*20);
    await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === expectedRows), 'Cases did not load the requested fixture scope');
  }
  return page;
}

async function closeRecord(page){
  const identity=await page.locator('.au-record-dialog[open] pre').evaluate(element=>({kind:element.dataset.auRecordKind,id:element.dataset.auRecordId}));
  await page.locator('[data-au-close-record]').click();
  await eventually(()=>page.evaluate(({kind,id})=>!document.querySelector('.au-record-dialog').open&&document.activeElement?.dataset.auInspect===kind&&document.activeElement?.dataset.auRecordId===id,identity),'native record close did not restore its exact inspection origin');
}

async function caseDetails(page){
  const prior={detail:await page.locator('[data-au-panel]').getAttribute('data-au-panel'),route:new URL(page.url()).hash,playing:await page.locator('[data-au-demo-stop]').count()===1};
  if(prior.detail!=='activity')await page.locator('.au-work-head [data-au-detail="activity"]').click();
  await page.locator('[data-au-panel="activity"] [data-au-inspect="claim"]').click();
  const record=JSON.parse(await page.locator('.au-record-dialog[open] pre[data-au-record-kind="claim"]').textContent());
  await closeRecord(page);
  if(prior.detail!=='activity')await page.locator(`.au-context-nav [data-au-detail="${prior.detail}"]`).click();
  const before=new URLSearchParams(prior.route.split('?')[1]),after=new URLSearchParams(new URL(page.url()).hash.split('?')[1]);
  assert.equal(new URL(page.url()).hash.split('?')[0],prior.route.split('?')[0],'technical inspection cannot replace its exact claim');
  for(const [key,value]of before)assert.equal(after.get(key),value,`technical inspection must restore the explicit ${key} route identity`);
  assert.equal(await page.locator('[data-au-panel]').getAttribute('data-au-panel'),prior.detail,'History inspection returns to its original local purpose');
  if(prior.playing)await page.locator('[data-au-demo-resume]').click();
  return record;
}

async function knowledgeDetails(page){
  await page.locator('[data-au-inspect="knowledge-index"]').click();
  const record=JSON.parse(await page.locator('.au-record-dialog[open] pre[data-au-record-kind="knowledge-index"]').textContent());
  await closeRecord(page);return record;
}

async function originalPageIds(page){return page.locator('[data-au-claim-row]').evaluateAll(rows=>rows.map(row=>row.dataset.auClaimRow));}
async function collectVisiblePages(page){
  const ids=[];
  for(let pageNumber=1;pageNumber<=8;pageNumber++){
    const current=await originalPageIds(page);assert.ok(current.length<=20,'one collection page stays bounded');ids.push(...current);
    const next=page.locator('[data-au-pagination] [data-au-page]').last();if(await next.isDisabled())break;
    await next.click();await eventually(()=>page.locator('[data-au-pagination]').innerText().then(text=>text.includes(`Page ${pageNumber+1} of`)),'next page did not render');
  }
  return ids;
}

async function openFullProcess(page){
  const control=page.locator('[data-au-expand-process]');
  if(await control.count()&&await control.getAttribute('aria-expanded')!=='true')await control.click();
}

async function selectFact(page,id){
  const control=page.locator(`[data-au-panel="step"] [data-au-fact-select="${id}"]`);
  if(await control.count())await control.click();else assert.equal(await page.locator('[data-au-evidence-path] [data-au-fact]').getAttribute('data-au-fact'),id);
}
async function selectDocument(page,id){
  const control=page.locator(`[data-au-panel="step"] [data-au-document-select="${id}"]`);
  if(await control.count()){
    try { await control.click(); }
    catch(error){
      if(process.env.CASEPATH_BROWSER_DIAGNOSTICS){
        fs.mkdirSync(process.env.CASEPATH_BROWSER_DIAGNOSTICS,{recursive:true});
        const geometry=await control.evaluate(element=>{
          const rect=element.getBoundingClientRect(),style=getComputedStyle(element),body=element.closest('.au-context-body'),bodyRect=body?.getBoundingClientRect(),bodyStyle=body&&getComputedStyle(body),x=rect.left+rect.width/2,y=rect.top+rect.height/2;
          return {rect:rect.toJSON(),style:{position:style.position,zIndex:style.zIndex,opacity:style.opacity,transform:style.transform},bodyRect:bodyRect?.toJSON(),bodyStyle:bodyStyle&&{position:bodyStyle.position,zIndex:bodyStyle.zIndex,opacity:bodyStyle.opacity,transform:bodyStyle.transform,overflow:bodyStyle.overflow},hits:document.elementsFromPoint(x,y).slice(0,8).map(row=>row.outerHTML.slice(0,500)),animations:document.getAnimations().map(animation=>({time:animation.currentTime,state:animation.playState,target:animation.effect?.target?.outerHTML.slice(0,200)}))};
        });
        fs.writeFileSync(path.join(process.env.CASEPATH_BROWSER_DIAGNOSTICS,`document-pointer-${id}.json`),JSON.stringify(geometry,null,2));
      }
      throw error;
    }
  }else assert.equal(await page.locator('[data-au-evidence-path] [data-au-document]').getAttribute('data-au-document'),id);
}

async function playIfPaused(page) {
  const resume=page.locator('[data-au-demo-resume]'),play=page.locator('[data-au-demo-play]');
  if(await resume.count())await resume.click();else if(await play.count())await play.click();
}

const calls = (page, suffix) => page.evaluate(suffix => window.__fixture.calls.filter(call => new URL(call.url, location.origin).pathname.endsWith(suffix)), suffix);
async function open(page, id) {
  await page.evaluate(id => { void window.__controller.openClaim(id); }, id);
}
async function title(page, id) {
  await eventually(async () => {
    const rendered = await page.locator('[data-au-claim-title]').count() ? await page.locator('[data-au-claim-title]').textContent() : null;
    const expected = await page.evaluate(id => window.CasePathAutonomous.REFERENCE_DEMO_CASES?.find(row => row.claim_id === id)?.label || window.CasePathAutonomous.DEMO_CASES.find(row => row.claim_id === id)?.label || window.__fixture.envelopes[id].state.title, id);
    return rendered === expected;
  }, `The matching saved claim ${id} did not render`);
  // Request the actual product's single technical drawer once. Its closed
  // claim record stays synchronized to accepted renders, so subsequent replay
  // assertions read UI output without changing the scheduler on every poll.
  const record = page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]');
  if (!await record.count()) {
    await caseDetails(page);
    await eventually(() => record.count().then(count => count === 1), 'History Case details did not expose the synchronized exact accepted state');
  }
}

async function junctionConnections(page){
 const geometry=await page.locator('[data-au-graph]').evaluate(graph=>{const rectangle=element=>element.getBoundingClientRect().toJSON(),junction=id=>[...graph.querySelectorAll('[data-au-junction]')].find(row=>row.dataset.auJunction===id);return [...graph.querySelectorAll('[data-au-edge]')].map(path=>{const length=path.getTotalLength(),matrix=path.getScreenCTM(),screen=point=>new DOMPoint(point.x,point.y).matrixTransform(matrix).toJSON();return {id:path.dataset.auEdge,source:rectangle(junction(path.dataset.auEdgeSource)),target:rectangle(junction(path.dataset.auEdgeTarget)),start:screen(path.getPointAtLength(0)),end:screen(path.getPointAtLength(length)),length,samples:Array.from({length:101},(_,index)=>screen(path.getPointAtLength(length*index/100))),titles:[...graph.querySelectorAll('.au-node-title,.au-node-condition')].map(rectangle)};});});
 for(const edge of geometry){assert.ok(edge.length>20,'a real dependency has a continuous visible route beyond its arrow');assert.ok(Math.abs(edge.start.x-(edge.source.left+edge.source.width/2))<1&&Math.abs(edge.start.y-edge.source.bottom)<1,'the source is its actual junction');assert.ok(Math.abs(edge.end.x-(edge.target.left+edge.target.width/2))<1&&Math.abs(edge.end.y-edge.target.top)<1,'the target is its actual junction');assert.equal(edge.samples.some(point=>edge.titles.some(title=>point.x>title.left+.5&&point.x<title.right-.5&&point.y>title.top+.5&&point.y<title.bottom-.5)),false,'dependencies route through clear margins and row gaps');}
 return geometry;
}

for(const [width,height,reduced]of [[1440,900,false],[1280,800,true],[390,844,false]])test(`causal formation native: heating requirements enter at their actual steps and final content stays visible at ${width}x${height}`,async t=>{
 const fixture=referenceFixture(),id=referenceIds[0],page=await fixturePage(t,{referenceFixture:true,publicReadOnly:true,width,height});
 if(reduced)await page.emulateMedia({reducedMotion:'reduce'});
 const timeline=[[13,[]],[15,[]],[16,[]],[17,[]],[18,['tenancy_terms_evidence']],[19,['tenancy_terms_evidence','landlord_knowledge_evidence']],[21,['tenancy_terms_evidence','landlord_knowledge_evidence','objective_defect_observation']],[23,['tenancy_terms_evidence','landlord_knowledge_evidence','objective_defect_observation']]];
 for(const [through,types]of timeline){
  await page.evaluate(({id,through})=>window.__controller.openClaim(id,true,{mode:'replay',collection:'reference',through}),{id,through});
  const prefix=fixture.prefixes[id][through];await title(page,id);
  assert.deepEqual(sorted(await page.locator('.au-forming-documents [data-au-obligation]').evaluateAll(rows=>rows.map(row=>row.dataset.auDocument))),sorted(types),`native prefix ${through} has exactly the reached requirements`);
  assert.deepEqual(sorted(await page.locator('[data-au-node]').evaluateAll(rows=>rows.map(row=>row.dataset.auNode))),sorted(prefix.state.graph.nodes.map(row=>row.node_id)));
  assert.equal(await page.locator('[data-au-node-condition],[data-au-edge-label]').count(),0,'the actual unconditional linear reference graph gains no invented branch labels');
  assert.equal(await page.locator('[data-au-edge]').evaluateAll(rows=>rows.every(row=>row.getAttribute('marker-end')?.startsWith('url(')&&row.getTotalLength()>3)),true,'real dependencies have visible directional paths');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
  assert.equal(await page.locator('.au-forming-documents .au-document-review[data-au-review="sufficient"]').count(),types.length);
  if(through<18)assert.equal(await page.locator('[data-au-forming-wire="process-document"]').count(),0,'hidden future requirements cannot leave a document connector');
  assert.equal(await page.locator('[data-au-knowledge-publication]').count(),0,'the saved head cannot lend future knowledge to a displayed prefix');
  if(through===18){
   const probe=await page.evaluate(state=>{const copy=structuredClone(state),row=copy.obligations.find(item=>item.document_type==='tenancy_terms_evidence');row.node_id='dh_notice';row.decision_node_id='dh_notice';row.node_ids=['dh_notice','dh_scope'];const prior=structuredClone(copy);prior.evaluation.nodes.find(item=>item.node_id==='dh_scope').execution_state='blocked';prior.evaluation.nodes.find(item=>item.node_id==='dh_scope').blocked_by=['dh_intake'];return {context:window.CasePathAutonomous.enteredRequirementContext(prior,copy),html:window.CasePathAutonomous.obligationMarkup(copy,'dh_scope',[row],{},true)};},prefix.state);
   assert.equal(probe.context.node,'dh_scope');assert.match(probe.html,/data-au-select="dh_scope"/);assert.doesNotMatch(probe.html,/data-au-select="dh_notice"/);
   const row=page.locator('.au-forming-documents [data-au-obligation]').first(),origin=row.locator('[data-au-source][data-au-citation]').first();assert.equal(await origin.count(),1);
   const citation=JSON.parse(await origin.getAttribute('data-au-citation'));await origin.focus();await page.keyboard.press('Enter');await eventually(()=>page.locator('.au-source-dialog[open] mark').count().then(count=>count===1),'exact native requirement source did not open');assert.equal(await page.locator('.au-source-dialog mark').textContent(),citation.quote);await page.locator('[data-au-close]').click();assert.equal(await origin.evaluate(element=>element===document.activeElement),true);
  }
 }
 const head=fixture.snapshots[id];await page.evaluate(({id,through})=>window.__controller.openClaim(id,true,{mode:'replay',collection:'reference',through}),{id,through:head.state.revision});await title(page,id);
 assert.equal(await page.locator('[data-au-settled="true"]').count(),1);assert.ok((await page.locator('.au-assessment-conclusion').innerText()).includes(head.state.outcome.summary));
 assert.deepEqual(sorted(await page.locator('.au-forming-documents [data-au-obligation]').evaluateAll(rows=>rows.map(row=>row.dataset.auObligation))),sorted(head.state.obligations.map(row=>row.obligation_id)));
 assert.equal(await page.locator('.au-forming-documents .au-document-review[data-au-review="sufficient"]').count(),3);assert.equal(await page.locator('.au-forming-documents [data-au-source][data-au-citation]').count(),3);
 const publication=head.state.knowledge_published[0];assert.equal(await page.locator(`[data-au-knowledge-publication="${publication.knowledge_sha256}"]`).count(),1);assert.equal(await page.locator(`[data-au-knowledge-sha="${publication.knowledge_sha256}"]`).getAttribute('data-au-version'),String(publication.version));
 const connectors=await junctionConnections(page);
 await focusedReceipt(page,`causal-native-heating-settled-${width}x${height}`,{connectors,claimId:id,revision:head.state.revision,state_sha256:head.state.state_sha256,documents:head.state.obligations.map(row=>row.obligation_id),reduced});
});

for(const height of [900,1000])test(`causal formation native: the existing eleven-step termination fixture exposes real forks joins and exact conditional routes at 1440x${height}`,async t=>{
 const fixture=priorAssessmentFixture(),id=fixture.claim_id,page=await fixturePage(t,{priorAssessment:'reassessed',acceptedPrefix:9,publicReadOnly:true,width:1440,height});
 await open(page,id);await title(page,id);const saved=fixture.prefixes[9].state,layout=require('../casepath/assets/autonomous-workspace-v1.js').layoutGraph(saved.graph);
 assert.equal(layout.nodes.length,11);assert.equal(layout.edges.length,13);assert.equal(layout.children.get('lt_type').length,3);assert.equal(layout.children.get('lt_abuse').length,2);assert.ok([...layout.parents.values()].some(rows=>rows.length>1));
 assert.deepEqual(sorted(await page.locator('[data-au-edge]').evaluateAll(rows=>rows.map(row=>row.dataset.auEdge))),sorted(layout.edges.map(row=>row.edge_id)));
 assert.equal(await page.locator('[data-au-edge]').evaluateAll(rows=>rows.every(row=>row.getAttribute('marker-end')&&row.getTotalLength()>3)),true);
 const labels=await page.locator('[data-au-edge-label]').evaluateAll(rows=>rows.map(row=>({id:row.dataset.auEdgeLabel,state:row.dataset.state,text:row.textContent,font:parseFloat(getComputedStyle(row).fontSize),width:row.clientWidth,scroll:row.scrollWidth})));
 const expectedLabels={lt_e04:'Rent arrears',lt_e05:'Family home',lt_e06:'No rent arrears and not a family home',lt_e09:'Tenancy extension',lt_e10:'No tenancy extension'};for(const [edge,label]of Object.entries(expectedLabels))assert.ok(labels.find(row=>row.id===edge)?.text.startsWith(label),`the actual ${edge} keeps readable case language`);
 assert.ok(labels.length>=5);for(const label of labels){const edge=layout.edges.find(row=>row.edge_id===label.id),evaluated=saved.evaluation.edges.find(row=>row.edge_id===label.id);assert.ok(edge?.condition);assert.equal(label.state,evaluated.activation);assert.ok(label.font>=12&&label.scroll<=label.width+1);assert.match(label.text,/Applies|Excluded|Unresolved/);}
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
 const connectors=await junctionConnections(page);
 const bounds=await page.locator('[data-au-graph-pan]').evaluate(graph=>{const frame=graph.getBoundingClientRect();return {frame:frame.toJSON(),height:innerHeight,scrollHeight:graph.scrollHeight,clientHeight:graph.clientHeight,nodes:[...graph.querySelectorAll('[data-au-node]')].map(node=>({id:node.dataset.auNode,rect:node.getBoundingClientRect().toJSON()}))};});
 await focusedReceipt(page,`causal-native-termination-forks-bounds-${height}`,{bounds});
 assert.ok(bounds.nodes.every(row=>row.rect.left>=bounds.frame.left-1&&row.rect.right<=bounds.frame.right+1&&row.rect.top>=bounds.frame.top-1&&row.rect.bottom<=bounds.frame.bottom+1),'the compact native overview exposes all eleven actual nodes in its graph viewport');
 assert.ok(bounds.frame.bottom<=bounds.height+1,'the compact graph viewport stays in the initial desktop viewport');
 await focusedReceipt(page,`causal-native-termination-forks-${height}`,{claimId:id,fixture:'build-prior-assessment-fixture-v1.py',revision:saved.revision,state_sha256:saved.state_sha256,labels,bounds,connectors,nodes:layout.nodes.map(row=>row.node_id),edges:layout.edges.map(row=>row.edge_id)});
});

test('causal formation native: autoplay introduces early-reviewed requirements at the exact newly reached steps',async t=>{
 const fixture=referenceFixture(),id=referenceIds[0];
 for(const [before,through,node,type]of [[17,18,'dh_scope','tenancy_terms_evidence'],[18,19,'dh_notice','landlord_knowledge_evidence'],[20,21,'dh_evidence','objective_defect_observation']])await t.test(String(through),async t=>{
  const page=await fixturePage(t,{referenceFixture:true,publicReadOnly:true});await page.evaluate(({id,through})=>window.__controller.openClaim(id,true,{mode:'replay',collection:'reference',through}),{id,through:before});await page.locator('[data-au-demo-play]').click();
  for(let step=0;step<250&&Number(await page.locator('[data-au-revision]').getAttribute('data-au-revision'))<through;step++)await page.clock.runFor(50);
  assert.equal(await page.locator('[data-au-revision]').getAttribute('data-au-revision'),String(through));assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'),node);
  const obligation=fixture.prefixes[id][through].state.obligations.find(row=>row.document_type===type);
  assert.equal(await page.locator(`.au-forming-documents [data-au-obligation="${obligation.obligation_id}"][data-selected="true"]`).count(),1);
  const wire=page.locator('[data-au-forming-wire="process-document"]');assert.equal(await wire.getAttribute('data-au-wire-node'),node);assert.equal(await wire.getAttribute('data-au-wire-obligation'),obligation.obligation_id);assert.ok(await wire.getAttribute('d'));
  const row=page.locator(`.au-forming-documents [data-au-obligation="${obligation.obligation_id}"]`),source=row.locator('[data-au-source][data-au-citation]').first(),citation=JSON.parse(await source.getAttribute('data-au-citation'));
  await source.focus();await page.keyboard.press('Enter');await eventually(()=>page.locator('.au-source-dialog[open] mark').count().then(count=>count===1),'exact newly reached source did not open');assert.equal(await page.locator('mark').textContent(),citation.quote);
  await page.clock.runFor(8000);assert.equal(await page.locator('[data-au-revision]').getAttribute('data-au-revision'),String(through));await page.locator('[data-au-close]').click();assert.equal(await source.evaluate(element=>document.activeElement===element),true);assert.equal(await page.locator('[data-au-demo-resume]').count(),1);
  await focusedReceipt(page,`causal-native-autoplay-${through}`,{id,before,through,node,obligation:obligation.obligation_id,source:citation.artifact_id,source_sha256:citation.sha256});
 });
});

for(const interruption of ['none','pause','navigation','unstarted','pause-head','navigation-head','changed-head','missing'])test(`causal formation native: next case handoff retains verified content through ${interruption}`,async t=>{
 const fixture=referenceFixture(),id=referenceIds[0],next=referenceIds[1],head=fixture.snapshots[id].state,page=await fixturePage(t,{referenceFixture:true,publicReadOnly:true,holdReplayId:next,holdReplayThrough:interruption.endsWith('-head')?fixture.snapshots[next].state.revision:0,...(interruption==='unstarted'?{referenceUnprocessedIds:[next]}:{}),...(interruption==='changed-head'?{referenceChangedHeadId:next}:{}),...(interruption==='missing'?{referenceReplayMissingId:next}:{})});
 await page.evaluate(({id,through})=>window.__controller.openClaim(id,true,{mode:'replay',collection:'reference',through}),{id,through:head.revision-1});await page.locator('[data-au-demo-play]').click();
 for(let step=0;step<200&&Number(await page.locator('[data-au-revision]').getAttribute('data-au-revision'))<head.revision;step++)await page.clock.runFor(50);
 assert.equal(await page.locator('[data-au-revision]').getAttribute('data-au-revision'),String(head.revision));
 await page.evaluate(()=>{window.__handoffPaints=[];window.__handoffObserver=new MutationObserver(()=>window.__handoffPaints.push({claim:document.querySelector('[data-au-claim-title]')?.textContent,revision:document.querySelector('[data-au-revision]')?.dataset.auRevision,state_sha256:document.querySelector('[data-au-revision]')?.dataset.auStateSha,nodes:[...document.querySelectorAll('[data-au-node]')].map(row=>row.dataset.auNode),knowledge:[...document.querySelectorAll('[data-au-knowledge-publication],[data-au-knowledge-use]')].map(row=>row.dataset.auKnowledgePublication||row.dataset.auKnowledgeUse),empty:!!document.querySelector('.au-catalog-preview,[data-au-preview=unknown],[data-au-skeleton]')}));window.__handoffObserver.observe(document.querySelector('[data-au-view]'),{childList:true,subtree:true});});
 await page.clock.runFor(4500);
 assert.equal(await page.locator('[data-au-revision]').getAttribute('data-au-revision'),String(head.revision),'the last verified case survives a pending next-case read');assert.equal(await page.locator('.au-catalog-preview').count(),0);
 if(interruption.startsWith('navigation')){await page.locator('.au-nav [data-au-nav="work"]').click();}
 else if(interruption.startsWith('pause')){await page.locator('[data-au-demo-stop]').click();const held=await page.locator('[data-au-claim-title]').innerText();await page.evaluate(()=>{window.__fixture.holdReplayId=null;for(const row of window.__fixture.held.splice(0))row.release();});await page.clock.runFor(6000);assert.equal(await page.locator('[data-au-claim-title]').innerText(),held);assert.equal(await page.locator('[data-au-demo-resume]').count(),1);await page.locator('[data-au-demo-resume]').click();}
 await page.evaluate(()=>{window.__fixture.holdReplayId=null;for(const row of window.__fixture.held.splice(0))row.release();});
 if(interruption.startsWith('navigation')){await page.clock.runFor(6000);assert.equal(await page.locator('[data-au-claim-row]').count(),20);assert.equal(await page.locator('[data-au-revision]').count(),0);}
 else if(['unstarted','changed-head','missing'].includes(interruption)){await eventually(()=>page.locator('.au-global-status').innerText().then(text=>text.includes('Next case')&&/No recorded execution|head changed|No recorded replay/.test(text)),'an unstarted next case did not fail truthfully');assert.equal(await page.locator('[data-au-revision]').getAttribute('data-au-revision'),String(head.revision));assert.ok((await page.locator('.au-global-status').innerText()).includes(next)|| (await page.locator('.au-global-status').innerText()).includes('Heating resets'));}
 else {await page.clock.runFor(4100);await eventually(()=>page.evaluate(()=>window.__handoffPaints.some(row=>row.revision==='0')),'verified next prefix zero did not paint directly');assert.ok(new URL(page.url()).hash.includes(next));const opening=await page.evaluate(()=>window.__handoffPaints.find(row=>row.revision==='0'));assert.equal(opening.state_sha256,fixture.prefixes[next][0].state.state_sha256);assert.deepEqual(opening.nodes,[]);assert.deepEqual(opening.knowledge,[]);assert.equal(await page.locator('[data-au-node]').count(),0,'the next verified head never lends its process to intake prefix zero');}
 assert.equal(await page.evaluate(()=>window.__handoffPaints.some(row=>row.empty)),false,'no empty Choose a case interstitial is painted');assert.equal(await page.evaluate(()=>window.__fixture.calls.some(call=>call.method!=='GET')),false);
 await focusedReceipt(page,`causal-native-handoff-${interruption}`,{prior:id,next,interruption,paints:await page.evaluate(()=>window.__handoffPaints)});
});

test('replay entry: a legacy link without collection plays its exact roster and highlights Demonstration',async t=>{
 const id=demoIds[0],page=await fixturePage(t,{presentationSuite:'replay',initialFragment:`#autonomous/claim/${id}?mode=replay&through=0`});
 await title(page,id);
 assert.equal(await page.locator('[data-au-demo-play]').count(),1,'a direct replay stays still until Play');
 const before=await visibleRecord(page);await page.clock.runFor(7000);assert.deepEqual(await visibleRecord(page),before);
 await page.locator('[data-au-demo-play]').click();await page.clock.runFor(1600);
 assert.ok(Number(await page.locator('[data-au-revision]').getAttribute('data-au-revision'))>0,'Play must consume a real legacy prefix');
 assert.equal(await page.locator('.au-nav [aria-current="page"]').getAttribute('data-au-nav'),'demonstration');
 assert.equal(new URLSearchParams(new URL(page.url()).hash.split('?')[1]).get('collection'),'legacy');
 await page.locator('.au-nav [data-au-nav="work"]').click();
});

test('replay entry: programmatic titles stay quiet while native keyboard focus remains visible',async t=>{
 const id=referenceIds[0],page=await fixturePage(t,{referenceFixture:true,publicReadOnly:true,initialFragment:`#autonomous/claim/${id}?mode=replay&through=0`});
 const heading=page.locator('h1');
 const focus=await heading.evaluate(element=>({active:document.activeElement===element,visible:element.matches(':focus-visible'),outline:getComputedStyle(element).outlineStyle}));
 assert.equal(focus.active,true);assert.equal(focus.outline,'none','the initial programmatic title focus must not add a red rectangle');
 await page.keyboard.press('Tab');const active=await page.evaluate(()=>({tag:document.activeElement.tagName,visible:document.activeElement.matches(':focus-visible'),outline:getComputedStyle(document.activeElement).outlineStyle}));
 assert.equal(active.tag,'BUTTON');assert.equal(active.visible,true);assert.equal(active.outline,'solid');
 await heading.focus();assert.equal(await heading.evaluate(element=>getComputedStyle(element).outlineStyle),'solid','keyboard modality retains heading focus indication');
});

for(const publicReadOnly of [false,true])test(`replay entry: fresh ${publicReadOnly?'public visitor':'owner'} consumes all 218 reference prefixes and eight native handoffs`,async t=>{
 const fixture=referenceFixture(),id=referenceIds[0],page=await fixturePage(t,{referenceFixture:true,publicReadOnly,providerReady:!publicReadOnly,initialFragment:publicReadOnly?'#autonomous/demonstration?mode=replay':'#autonomous'});
 if(!publicReadOnly)await page.locator('.au-nav [data-au-nav="demonstration"]').click();
 await eventually(()=>page.locator('[data-au-revision="0"]').count().then(count=>count===1),'fresh Demonstration must begin at reference intake prefix zero');
 assert.ok(new URL(page.url()).hash.startsWith(`#autonomous/claim/${id}?collection=reference&mode=replay&through=0`));
 assert.equal(await page.locator('[data-au-node],[data-au-reference-mode]').count(),0,'the verified head cannot paint into prefix zero');
 await title(page,id);assert.deepEqual(await visibleRecord(page),{state:fixture.prefixes[id][0].state,projection:fixture.prefixes[id][0].projection});
 await page.evaluate(()=>{
  window.__referencePaints=[];
  const capture=()=>{
   const pre=document.querySelector('[data-au-record-content] > pre[data-au-record-kind="claim"]'),surface=document.querySelector('[data-au-revision]');
   if(!pre||!surface)return;const record=JSON.parse(pre.textContent);if(!record?.state)return;
   const identity=`${record.state.claim_id}:${record.state.revision}:${record.state.state_sha256}`;
   if(window.__referencePaints.at(-1)?.identity===identity)return;
   window.__referencePaints.push({identity,record,revision:surface.dataset.auRevision,state_sha256:surface.dataset.auStateSha,route:location.hash,nav:document.querySelector('.au-nav [aria-current="page"]')?.dataset.auNav,nodes:[...surface.querySelectorAll('[data-au-node]')].map(row=>row.dataset.auNode),requirements:[...surface.querySelectorAll('[data-au-obligation]')].map(row=>row.dataset.auObligation)});
  };
  capture();window.__referenceObserver=new MutationObserver(capture);window.__referenceObserver.observe(document.querySelector('#workspace'),{subtree:true,childList:true});
 });
 for(let tick=0;tick<1000&&await page.locator('[data-au-demo-stop]').count();tick++)await page.clock.runFor(1600);
 assert.match(await page.locator('.au-global-status').innerText(),/Recorded playback finished/);
 const paints=await page.evaluate(()=>{window.__referenceObserver.disconnect();return window.__referencePaints;});
 const expected=referenceIds.flatMap(claim=>Object.values(fixture.prefixes[claim]));assert.equal(expected.length,218);assert.equal(paints.length,218,'no real accepted prefix may disappear during playback or case handoff');
 for(let index=0;index<expected.length;index++){
  const paint=paints[index],prefix=expected[index];assert.deepEqual(paint.record,{state:prefix.state,projection:prefix.projection},`native paint ${index} retains the complete accepted prefix`);
  assert.equal(paint.revision,String(prefix.through_seq));assert.equal(paint.state_sha256,prefix.state.state_sha256);assert.equal(paint.nav,'demonstration');
  assert.ok(paint.route.startsWith(`#autonomous/claim/${prefix.state.claim_id}?collection=reference&mode=replay&through=${prefix.through_seq}`));
  assert.deepEqual(sorted(paint.nodes),sorted((prefix.state.graph?.nodes||[]).map(row=>row.node_id)),`native paint ${index} keeps its own recorded graph`);
  assert.ok(paint.requirements.every(identity=>prefix.state.obligations.some(row=>row.obligation_id===identity)),`native paint ${index} requirements belong to this accepted prefix`);
 }
 assert.deepEqual([...new Set(paints.map(row=>row.record.state.claim_id))],referenceIds);assert.equal(paints.filter((row,index)=>index&&row.record.state.claim_id!==paints[index-1].record.state.claim_id).length,8);
 assert.deepEqual(await visibleRecord(page),{state:fixture.snapshots[referenceIds.at(-1)].state,projection:fixture.snapshots[referenceIds.at(-1)].projection});
 assert.equal(await page.evaluate(()=>window.__fixture.calls.some(call=>call.method!=='GET')),false);
 await focusedReceipt(page,`replay-entry-all218-${publicReadOnly?'visitor':'owner'}`,{prefixes:paints.map(({record,...paint})=>({...paint,claim_id:record.state.claim_id})),handoffs:8,requests:await page.evaluate(()=>window.__fixture.calls)});
});

test('replay entry: shared reference identity and explicit legacy links keep manual past-state inspection until Play',async t=>{
 const fixture=referenceFixture(),shared='clm_7dbd7c7d1c4ddf90';
 for(const [id,query,collection]of [[shared,'','reference'],[demoIds[0],'&collection=legacy','legacy']])await t.test(collection,async t=>{
  const page=await fixturePage(t,{referenceFixture:true,presentationSuite:'replay',publicReadOnly:true,initialFragment:`#autonomous/claim/${id}?mode=replay&through=0&detail=sources${query}`});
  await title(page,id);const before=await visibleRecord(page);await page.clock.runFor(8000);assert.deepEqual(await visibleRecord(page),before);assert.equal(await page.locator('[data-au-demo-play]').count(),1);assert.equal(await page.locator('.au-nav [aria-current="page"]').getAttribute('data-au-nav'),'demonstration');
  assert.equal(new URLSearchParams(new URL(page.url()).hash.split('?')[1]).get('collection'),collection);
  if(collection==='reference')assert.deepEqual(before,{state:fixture.prefixes[id][0].state,projection:fixture.prefixes[id][0].projection});
  await page.locator('[data-au-demo-play]').focus();await page.keyboard.press('Enter');await page.clock.runFor(1600);assert.ok(Number(await page.locator('[data-au-revision]').getAttribute('data-au-revision'))>0);
  await page.locator('.au-nav [data-au-nav="work"]').click();
 });
});

test('replay lifecycle: actual index retains a native back-forward cached prefix and resumes only by intent',async()=>{
 const fixture=referenceFixture(),id=referenceIds[0],assets=new Map([
  ['casepath/index.html',fs.readFileSync(path.join(root,'casepath/index.html'))],
  ['casepath/assets/autonomous-entry-v1.js',fs.readFileSync(process.env.CASEPATH_BROWSER_ENTRY_ASSET || path.join(root,'casepath/assets/autonomous-entry-v1.js'))],
  ['casepath/assets/autonomous-workspace-v1.js',fs.readFileSync(process.env.CASEPATH_BROWSER_JS_ASSET || path.join(root,'casepath/assets/autonomous-workspace-v1.js'))],
  ['casepath/assets/autonomous-workspace-v1.css',fs.readFileSync(process.env.CASEPATH_BROWSER_CSS_ASSET || path.join(root,'casepath/assets/autonomous-workspace-v1.css'))]
 ]),evidence={assets:Object.fromEntries([...assets].map(([file,bytes])=>[file,sha(bytes)])),runs:[]};
 // Playwright normally disables BFCache. This separate browser exercises a
 // genuine persisted pageshow without changing other tests' browser policy.
 const cachedBrowser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH || '/usr/bin/chromium',headless:true,args:['--no-sandbox'],ignoreDefaultArgs:['--disable-back-forward-cache']});
 try {
  for(const fragment of [`#autonomous/claim/${id}?collection=reference&mode=replay&through=18&detail=sources`,'#autonomous/demonstration?mode=replay']){
   const context=await cachedBrowser.newContext({serviceWorkers:'block'}),page=await context.newPage(),requests=[],errors=[],shows=[],served={};
   page.on('pageerror',error=>errors.push(error.message));
   await page.exposeFunction('observePageShow',row=>shows.push(row));
   await page.addInitScript(()=>addEventListener('pageshow',event=>void window.observePageShow({persisted:event.persisted,path:location.pathname})));
   const time=new Date('2026-10-13T12:00:00Z');await page.clock.install({time});await page.clock.pauseAt(time);
   await page.route('**/*',async route=>{
    const request=route.request(),url=new URL(request.url()),name=decodeURIComponent(url.pathname);requests.push({path:name+url.search,method:request.method()});
    assert.equal(url.origin,'http://native-entry.invalid','every request remains in the local native fixture');assert.equal(request.method(),'GET');
    if(name==='/away')return route.fulfill({status:200,contentType:'text/html',body:'<!doctype html><title>Away</title><p>Away</p>'});
    if(name.startsWith(base)){
     const suffix=name.slice(base.length),match=suffix.match(/^\/claims\/([^/]+)(?:\/(snapshot|replay|events))?$/);
     const data=suffix==='/claims'?{claims:Object.values(fixture.snapshots).map(row=>({...row.state,origin:'canonical_original'})),total:9}:suffix==='/knowledge'?fixture.knowledge:suffix==='/status'?{enabled:true,provider_ready:false,read_only:true,writable:false,limits:{}}:match?match[2]==='replay'?fixture.prefixes[match[1]]?.[Number(url.searchParams.get('through_seq')||0)]:fixture.snapshots[match[1]]:null;
     return route.fulfill({status:data?200:404,contentType:'application/json',body:JSON.stringify(data||{detail:'Synthetic GET unavailable'})});
    }
    const file='casepath/'+(name==='/'?'index.html':name.slice(1));let body=assets.get(file);
    if(!body&&!file.includes('..')&&fs.existsSync(path.join(root,file)))body=fs.readFileSync(path.join(root,file));
    if(!body)return route.fulfill({status:404,body:'Unavailable'});
    served[file]=sha(body);
    if(file==='casepath/index.html')body=Buffer.from(body.toString().replace('<head>','<head><script>window.CASEPATH_PUBLIC_READ_ONLY=true;window.CASEPATH_HOSTED_AUTONOMOUS=true;</script>'));
    return route.fulfill({status:200,contentType:{'.html':'text/html','.js':'application/javascript','.css':'text/css','.ttf':'font/ttf','.json':'application/json'}[path.extname(file)]||'application/octet-stream',body});
   });
   await page.goto('http://native-entry.invalid/'+fragment);await page.locator('[data-au-revision]').waitFor();
   const sample=()=>page.evaluate(()=>({hash:location.hash,revision:Number(document.querySelector('[data-au-revision]')?.dataset.auRevision),state_sha256:document.querySelector('[data-au-state-sha]')?.dataset.auStateSha,nav:document.querySelector('.au-nav [aria-current]')?.dataset.auNav,panel:document.querySelector('[data-au-context]')?.dataset.auContext,play:!!document.querySelector('[data-au-demo-play]'),resume:!!document.querySelector('[data-au-demo-resume]'),workspaceLength:document.querySelector('#autonomousWorkspace').innerHTML.length,hidden:document.hidden}));
   const autoplay=fragment.startsWith('#autonomous/demonstration');
   if(autoplay){await page.clock.runFor(4100);await eventually(async()=>(await sample()).revision>0,'actual entry did not autoplay its recorded prefixes');}
   const before=await sample();assert.equal(before.nav,'demonstration');assert.equal(before.state_sha256,fixture.prefixes[id][before.revision].state.state_sha256);
   await page.evaluate(()=>addEventListener('pagehide',event=>sessionStorage.setItem('casepath-qa-lifecycle',JSON.stringify({persisted:event.persisted,workspaceLength:document.querySelector('#autonomousWorkspace')?.innerHTML.length}))));
   await page.goto('http://native-entry.invalid/away');await page.goBack({waitUntil:'commit',timeout:3000});
   await eventually(()=>shows.some(row=>row.path==='/'&&row.persisted===true),'Back did not restore a genuine native cached page');
   const restored=await sample();for(const field of ['revision','state_sha256','hash','nav','panel'])assert.equal(restored[field],before[field],`native cached Back must retain its exact ${field}`);assert.ok(restored.workspaceLength>0);
   const persistedHide=await page.evaluate(()=>JSON.parse(sessionStorage.getItem('casepath-qa-lifecycle')));assert.equal(persistedHide.persisted,true);
   await page.clock.runFor(9000);const held=await sample();assert.equal(held.revision,before.revision,'native visibility restoration must hold the inspected recorded prefix');
   if(autoplay){
    assert.equal(restored.resume,true);await page.locator('[data-au-demo-resume]').click();
    for(let tick=0;(await sample()).revision===held.revision&&tick<300;tick++)await page.clock.runFor(20);
    const resumed=await sample();assert.equal(resumed.revision,held.revision+1);assert.equal(resumed.state_sha256,fixture.prefixes[id][resumed.revision].state.state_sha256);
   }
   await page.reload();await page.locator('[data-au-revision]').waitFor();
   const departure=await page.evaluate(()=>JSON.parse(sessionStorage.getItem('casepath-qa-lifecycle'))),reloaded=await sample();assert.equal(departure.persisted,false);assert.equal(departure.workspaceLength,0);assert.equal(reloaded.nav,'demonstration');assert.equal(reloaded.play,true,'a normal reload preserves the recorded route for deliberate Play');
   for(const [file,hash]of Object.entries(evidence.assets))assert.equal(served[file],hash,'the actual native loader serves the current selected asset bytes');
   assert.deepEqual(errors,[]);assert.equal(requests.some(row=>row.method!=='GET'||row.path==='/api/demo'),false);
   evidence.runs.push({fragment,before,shows,persistedHide,restored,held,departure,reloaded,requests});await context.close();
  }
 }finally{await cachedBrowser.close();}
 if(focusedReceiptRoot){fs.mkdirSync(focusedReceiptRoot,{recursive:true});fs.writeFileSync(path.join(focusedReceiptRoot,'native-entry-bfcache.json'),JSON.stringify(evidence,null,2));}
});

test('reference native: exact nine actual accepted assessments retain graph documents Knowledge and source bytes',async t=>{
 const fixture=referenceFixture(),page=await fixturePage(t,{referenceFixture:true,readOnlyStatus:true});
 assert.equal(fixture.profile_sha256,'15c44d004cc1a34b90e8662b3185deb63652ab066c7727b080dfc0987a648de7');
 assert.deepEqual(await page.evaluate(()=>window.CasePathAutonomous.REFERENCE_DEMO_CASES.map(row=>row.claim_id)),referenceIds);
 await page.locator('[data-au-filter="investigation_complete"]').click();
 assert.equal(await page.locator('[data-au-filter="investigation_complete"]').innerText(),'Assessment complete');
 assert.deepEqual(sorted(await page.locator('[data-au-claim-row]').evaluateAll(rows=>rows.map(row=>row.dataset.auClaimRow))),sorted(referenceIds));
 await page.locator('[data-au-filter="deferred"]').click();assert.equal(await page.locator('[data-au-claim-row]').count(),0);
 await page.locator('[data-au-filter="all"]').click();
 for(const id of referenceIds){
  await open(page,id);await title(page,id);const record=await visibleRecord(page),expected=fixture.snapshots[id];
  assert.deepEqual(record.state,expected.state);assert.deepEqual(record.projection,expected.projection);
  assert.equal(await page.locator('[data-au-settled="true"]').count(),1);
  assert.deepEqual(sorted(await page.locator('.au-forming-documents [data-au-obligation]').evaluateAll(rows=>rows.map(row=>row.dataset.auObligation))),sorted(expected.state.obligations.map(row=>row.obligation_id)));
  assert.equal(await page.locator('.au-forming-documents [data-au-review="sufficient"]').count(),expected.state.obligations.length);
  assert.equal(await page.locator('.au-forming-documents [data-au-source][data-au-citation]').count(),expected.state.obligations.length);
  for(const use of expected.state.knowledge_uses)assert.equal(await page.locator(`[data-au-knowledge-use="${use.knowledge_sha256||use.knowledge_id||use.version_id}"] [data-au-version="${use.version}"]`).count(),1);
  for(const publication of expected.state.knowledge_published)assert.equal(await page.locator(`[data-au-knowledge-publication="${publication.knowledge_sha256}"] [data-au-version="${publication.version}"]`).count(),1);

  assert.equal(expected.state.status,'deferred');assert.equal(expected.state.outcome.status,'deferred');assert.equal(expected.state.outcome.assessment_status,'complete');
  assert.equal(await page.locator('[data-au-reference-mode]').count(),1);assert.equal(await page.locator('[data-au-reference-mode]').innerText(),`Historical synthetic recording · as of ${expected.state.outcome.reference_provenance.as_of} · rules-based`);
  assert.match(await page.locator('[data-au-claim-status]').innerText(),/Assessment complete/);assert.match(await page.locator('.au-claim-constraint').first().innerText(),/Assessment only; no external action taken/);
  assert.equal(await page.locator('.au-assessment-conclusion > p').first().textContent(),expected.state.outcome.summary);
  const context=expected.state.semantic_contexts[expected.state.run_id],authority=context.rule_packs.find(row=>row.family===expected.state.graph.family).legal_authority;
  const articles=[...new Set(expected.state.outcome.legal_predicates.flatMap(row=>row.rule_refs).map(ref=>/^CO:(\d+[a-z]?)$/.exec(ref)?.[1]).filter(Boolean))];
  assert.deepEqual(sorted(await page.locator('[data-au-law-article]').evaluateAll(rows=>rows.map(row=>row.dataset.auLawArticle))),sorted(articles));
  for(const article of articles)assert.equal(await page.locator(`[data-au-law-article="${article}"]`).getAttribute('href'),authority.find(row=>row.article===article).source.publisher_url);
  assert.deepEqual(sorted(await page.locator('[data-au-node]').evaluateAll(rows=>rows.map(row=>row.dataset.auNode))),sorted(expected.state.graph.nodes.map(row=>row.node_id)));
  await page.locator('.au-context-nav [data-au-detail="documents"]').click();
  assert.deepEqual(sorted(await page.locator('[data-au-obligation]').evaluateAll(rows=>rows.map(row=>row.dataset.auObligation))),sorted(expected.state.obligations.map(row=>row.obligation_id)));
  await page.locator('.au-context-nav [data-au-detail="sources"]').click();
  const originalIds=new Set(expected.state.original_binding.source_map.map(row=>row.artifact_id)),supplements=expected.state.source_descriptors.filter(row=>!originalIds.has(row.artifact_id));
  for(const supplement of supplements){
   assert.match(await page.locator(`li[data-au-source-arrival="${supplement.artifact_id}"]`).innerText(),/Authored synthetic supplement/);
   await page.locator(`[data-au-source="${supplement.artifact_id}"]`).click();
   await eventually(()=>page.locator('.au-source-body').count().then(count=>count===1),'the native synthetic supplement did not open');
   assert.equal(await page.locator('.au-source-dialog .au-eyebrow').innerText(),'Authored synthetic supplement');
   assert.equal(await page.locator('.au-source-body').textContent(),fixture.sources[`${id}/${supplement.artifact_id}`].source?.text || fixture.sources[`${id}/${supplement.artifact_id}`].text);
   assert.equal(sha(Buffer.from(fixture.raw_sources[`${id}/${supplement.artifact_id}`],'base64')),supplement.sha256);
   await page.keyboard.press('Escape');
  }
  assert.equal(await page.locator('[data-au-start],[data-au-pause],[data-au-resume],[data-au-arrival]').count(),0,'visitor permission cannot be inferred from engine capabilities');
 }
 assert.equal(fixture.knowledge.versions.length,3);assert.equal(fixture.knowledge.uses.length,6);
 await page.locator('.au-nav [data-au-nav="knowledge"]').click();await eventually(()=>page.locator('[data-au-knowledge-identity]').count().then(count=>count===1),'native reference Knowledge did not open');
 const version=await page.locator('[data-au-knowledge-identity]').getAttribute('data-au-knowledge-identity');assert.ok(fixture.knowledge.versions.some(row=>`${row.knowledge_id}:${row.version}`===version));
 assert.equal(await page.evaluate(()=>window.__fixture.calls.some(call=>call.method!=='GET')),false);
});

for(const reduced of [false,true])test(`reference native: default playback shows only accepted prefix mode and holds exact inspection with reduced motion ${reduced}`,async t=>{
 const fixture=referenceFixture(),id=referenceIds[0],page=await fixturePage(t,{referenceFixture:true,readOnlyStatus:true});
 if(reduced)await page.emulateMedia({reducedMotion:'reduce'});
 await page.locator('.au-nav [data-au-nav="demonstration"]').click();
 await eventually(()=>page.locator('[data-au-revision="0"]').count().then(count=>count===1),'default reference demonstration did not start at the actual original prefix');
 assert.equal(await page.locator('[data-au-reference-mode]').count(),0,'head admission cannot leak its mode/as-of into prefix zero');assert.equal(await page.locator('[data-au-node]').count(),0);
 const prefixes=fixture.prefixes[id],contextSeq=Object.values(prefixes).find(row=>row.events.at(-1)?.kind==='work.context').through_seq;
 for(let seq=1;seq<=contextSeq;seq++){
  let attempts=0;while(Number(await page.locator('[data-au-revision]').getAttribute('data-au-revision'))<seq&&attempts++<250)await page.clock.runFor(20);
  assert.equal(Number(await page.locator('[data-au-revision]').getAttribute('data-au-revision')),seq);
  const expected=prefixes[seq].state,mode=await page.locator('[data-au-reference-mode]').allTextContents();
  assert.deepEqual(mode,expected.policy_id==='casepath.bounded-reference-assessment/1.0.0'?[`Historical synthetic recording${expected.semantic_contexts?.[expected.run_id]?.reference_provenance ? ` · as of ${expected.semantic_contexts[expected.run_id].reference_provenance.as_of}` : ''} · rules-based`]:[]);
 }
 await page.locator('.au-work-head [data-au-detail="activity"]').focus();await page.keyboard.press('Enter');
 assert.equal(await page.locator('[data-au-demo-resume]').count(),1);const record=await caseDetails(page);assert.deepEqual(record.state,prefixes[contextSeq].state);assert.deepEqual(record.projection,prefixes[contextSeq].projection);
 const hashBefore=new URL(page.url()).hash;await page.clock.runFor(8000);assert.equal(new URL(page.url()).hash,hashBefore);assert.deepEqual((await visibleRecord(page)).state,record.state);
 assert.equal(await page.evaluate(()=>window.__fixture.calls.some(call=>call.method!=='GET')),false);
});

test('reference native: unavailable recordings retain actual unprocessed intake and its source-backed missing list read-only',async t=>{
 const fixture=referenceFixture(),id=referenceIds[0],page=await fixturePage(t,{referenceFixture:true,referenceUnprocessed:true,providerReady:true,publicReadOnly:true});
 await page.locator('.au-nav [data-au-nav="demonstration"]').click();
 await eventually(()=>page.locator('.au-global-status').innerText().then(value=>value.includes('no completed recorded history')),'unavailable reference recording did not stop honestly');
 assert.equal(await page.locator('[data-au-revision]').getAttribute('data-au-revision'),'0');assert.equal(await page.locator('[data-au-node]').count(),0);assert.equal(await page.locator('[data-au-reference-mode]').count(),0);
 assert.deepEqual(await page.locator('[data-au-intake-document]').evaluateAll(rows=>rows.map(row=>({document_type:row.dataset.auIntakeDocument,status:row.dataset.status}))),fixture.unprocessed[id].projection.intake.checklist.map(row=>({document_type:row.document_type,status:row.status})));
 await open(page,id);await title(page,id);assert.deepEqual((await visibleRecord(page)).state,fixture.unprocessed[id].state);assert.equal(await page.locator('[data-au-start],[data-au-pause],[data-au-resume],[data-au-arrival]').count(),0);
 await page.locator('.au-context-nav [data-au-detail="documents"]').click();assert.match(await page.locator('[data-au-intake-gate]').innerText(),/Intake incomplete/);assert.doesNotMatch(await page.locator('[data-au-intake-gate]').innerText(),/Reference assessment complete|Established/);
});

test('reference native: an earlier ordinary canonical prefix keeps its mode and context before reference admission',async t=>{
 const fixture=referenceFixture(),id='clm_7dbd7c7d1c4ddf90',earlier=fixture.earlier_context,page=await fixturePage(t,{referenceFixture:true,referenceReplayIds:[id],publicReadOnly:true});
 assert.equal(earlier.claim_id,id);const prefixes=fixture.prefixes[id],old=prefixes[earlier.revision];assert.equal(old.state.state_sha256,earlier.state_sha256);assert.ok(!old.state.outcome?.reference_provenance);
 const start=Object.values(prefixes).find(row=>row.state.policy_id==='casepath.bounded-reference-assessment/1.0.0' && row.events.at(-1)?.kind==='work.started');
 const context=Object.values(prefixes).find(row=>row.state.semantic_contexts?.[row.state.run_id]?.execution_mode==='deterministic_reference' && row.events.at(-1)?.kind==='work.context');
 for(const [prefix,hasDate] of [[old,false],[start,false],[context,true]]){
  await page.evaluate(({id,through})=>window.__controller.openClaim(id,true,{mode:'replay',collection:'legacy',through,detail:'activity'}),{id,through:prefix.through_seq});await title(page,id);
  assert.deepEqual((await visibleRecord(page)).state,prefix.state);assert.deepEqual((await visibleRecord(page)).projection,prefix.projection);
  const label=await page.locator('[data-au-reference-mode]').allTextContents();
  if(prefix===old)assert.deepEqual(label,[]);else assert.deepEqual(label,[`Historical synthetic recording${hasDate ? ` · as of ${context.state.semantic_contexts[context.state.run_id].reference_provenance.as_of}` : ''} · rules-based`]);
 }
 await page.evaluate(({id,through})=>window.__controller.openClaim(id,true,{mode:'replay',collection:'legacy',through,detail:'activity'}),{id,through:earlier.revision});await title(page,id);
 await page.locator('.au-nav [data-au-nav="knowledge"]').click();await eventually(()=>page.locator('[data-au-return-case]').count().then(count=>count>0),'Knowledge lost the earlier recorded return context');
 await page.locator('[data-au-return-case="step"]').click();await title(page,id);assert.deepEqual((await visibleRecord(page)).state,old.state);assert.equal(await page.locator('[data-au-reference-mode]').count(),0);
 assert.equal(new URLSearchParams(new URL(page.url()).hash.split('?')[1]).get('collection'),'legacy');
});

test('reference native: public entry omits creation and forged flag status and controls cannot reopen writes',async t=>{
 const page=await fixturePage(t,{publicReadOnly:true,providerReady:true,originalStartId:unprocessedId});
 assert.equal(await page.locator('.au-header-new').count(),0);assert.equal(await page.locator('[data-au-public-access]:visible').count(),1);assert.equal(await page.locator('[data-au-public-access]').innerText(),'Read-only');
 await page.evaluate(()=>{window.CASEPATH_PUBLIC_READ_ONLY=false;window.__fixture.readOnlyStatus=false;window.__fixture.providerReady=true;});
 await open(page,unprocessedId);await title(page,unprocessedId);
 assert.equal(await page.locator('[data-au-start],[data-au-pause],[data-au-resume],[data-au-arrival],[data-au-add-files]').count(),0);
 await page.evaluate(()=>{
  for(const action of ['start','pause','resume']){const button=document.createElement('button');button.setAttribute('data-au-'+action,'');document.querySelector('[data-au-view]').append(button);button.click();button.remove();}
  const form=document.createElement('form');form.setAttribute('data-au-intake','');document.querySelector('[data-au-view]').append(form);form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));form.remove();
 });
 await page.evaluate(()=>window.__controller.showIntake());
 assert.equal(await page.locator('[data-au-intake]').count(),0);assert.equal(await page.locator('.au-header-new').count(),0);assert.equal(await page.locator('[data-au-public-access]:visible').count(),1);
 assert.equal(await page.evaluate(()=>window.__fixture.calls.some(row=>row.method!=='GET')),false);
});

test('reference native: acquired pinned supplements show their actual body before accepted context and preserve exact source access',async t=>{
 const fixture=referenceFixture(),id=referenceIds[0],prefix=Object.values(fixture.prefixes[id]).find(row=>row.events.at(-1)?.kind==='sources.acquired' && row.events.at(-1).payload.sources.some(source=>source.text.startsWith('SYNTHETIC SUPPLEMENT —'))),page=await fixturePage(t,{referenceFixture:true,publicReadOnly:true});
 assert.ok(!prefix.state.semantic_contexts?.[prefix.state.run_id]);
 await page.evaluate(({id,through})=>window.__controller.openClaim(id,true,{mode:'replay',through,detail:'step'}),{id,through:prefix.through_seq});await title(page,id);
 assert.deepEqual((await visibleRecord(page)).state,prefix.state);assert.equal(await page.locator('[data-au-legal-basis]').count(),0);
 const supplement=prefix.events.at(-1).payload.sources.find(source=>source.text.startsWith('SYNTHETIC SUPPLEMENT —')),button=page.locator(`.au-reading-acquisition [data-au-source="${supplement.artifact_id}"]`),excerpt=await button.locator('.au-acquired-text').textContent();
 assert.ok(excerpt.startsWith(supplement.text.slice(supplement.text.indexOf('\n\n')+2, supplement.text.indexOf('\n\n')+62)));assert.doesNotMatch(excerpt,/Original corpus manifest SHA256|Fixture author:|SYNTHETIC SUPPLEMENT —/);assert.equal(await button.getAttribute('data-au-citation'),null);
 await button.click();await eventually(()=>page.locator('.au-source-body').count().then(count=>count===1),'the exact pre-context source did not open');assert.equal(await page.locator('.au-source-body').textContent(),supplement.text);await page.keyboard.press('Escape');
 assert.deepEqual((await visibleRecord(page)).state,prefix.state);assert.equal(await page.evaluate(()=>window.__fixture.calls.some(row=>row.method!=='GET')),false);
 const interpreted=Object.values(fixture.prefixes[id]).find(row=>row.events.at(-1)?.kind==='interpretation.accepted');
 await page.evaluate(({id,through})=>window.__controller.openClaim(id,true,{mode:'replay',through,detail:'step'}),{id,through:interpreted.through_seq});await title(page,id);assert.ok(!interpreted.state.outcome);assert.ok(await page.locator('[data-au-law-article]').count()>0);assert.deepEqual((await visibleRecord(page)).state,interpreted.state);
});

for(const width of [1428,390])test(`quiet language: the saved insufficient reason owns the reading view while History retains every exact record at ${width}px`,async t=>{
  const id='auto_764f712d3833988ce6ff6cfd',saved=fixtureData().envelopes[id],fact=saved.state.facts.find(row=>row.fact_id==='fact:notice_period_evidence'),obligation=saved.state.obligations.find(row=>row.required_fact_ids.includes(fact.fact_id)),page=await fixturePage(t,{width,height:width===390?844:801});
  assert.equal(fact.status,'insufficient');assert.ok(fact.citations.length,'this recorded conclusion has an original-source span');
  await page.evaluate(preferences=>window.__controller.openClaim(preferences.id,true,preferences),{id,node:obligation.node_id,document:obligation.document_type,obligation:obligation.obligation_id,fact:fact.fact_id});await title(page,id);
  const reading=page.locator('[data-au-evidence-path]'),reason=reading.locator('.au-fact-summary'),header=page.locator('.au-work-head');
  assert.equal(await reason.textContent(),fact.summary,'the visible conclusion uses the exact saved reason, without an inferred missing page or rewritten field checklist');
  assert.equal(await reading.locator('[data-au-fact] > .au-meta').count(),0,'the selected reason is not followed by a field-list and generic verdict suffix');
  assert.equal(await reading.locator('[data-au-inspect]').count(),0,'raw object controls do not divide the dominant reading surface');
  assert.equal(await header.locator('[data-au-refresh-claim], [data-au-inspect="claim"]').count(),0,'the claim header has no technical Record or Refresh workflow');
  assert.equal(await header.locator('[data-au-detail="activity"]').innerText(),'History');assert.equal(await page.locator('.au-context-nav [data-au-detail="activity"]').count(),0,'History is available once');
  assert.equal((await header.innerText()).includes(fact.summary),false,'the header does not repeat the current source-grounded conclusion');
  assert.ok((await page.locator('[data-au-node] .au-node-state').allTextContents()).every(text=>text.trim()!=='Evidence needed'),'the map does not repeat a generic unresolved badge beneath every question');
  const citation=fact.citations[0],source=reading.locator(`[data-au-source="${citation.artifact_id}"]`);assert.equal(JSON.parse(await source.getAttribute('data-au-citation')).quote,citation.quote);
  const route=new URL(page.url()).hash;await source.focus();await page.keyboard.press('Enter');await eventually(()=>page.locator('.au-source-dialog[open] mark').count().then(count=>count===1),'the saved insufficient reason lost its precise original source');
  assert.equal(await page.locator('.au-source-dialog[open] mark').textContent(),citation.quote);await page.locator('[data-au-close]').click();assert.equal(await source.evaluate(element=>document.activeElement===element),true);
  assert.equal(new URL(page.url()).hash,route);assert.deepEqual(await visibleRecord(page),saved,'reading and native source inspection preserve the full accepted state and capability projection');
  await page.locator('.au-context-nav [data-au-detail="sources"]').click();assert.equal(await page.locator('[data-au-panel="sources"] [data-au-inspect="claim"]').count(),0,'the source list uses the same quiet History access');assert.doesNotMatch(await page.locator('[data-au-panel="sources"]').innerText(),/Original file received/);assert.deepEqual(await visibleRecord(page),saved);
});

test('quiet language: Cases omit repetitive unstarted badges and global History opens the complete recorded Knowledge index',async t=>{
  const page=await fixturePage(t,{recordedKnowledge:true}),expected=captured[`${base}/knowledge`];assert.equal(await page.locator('[data-au-claim-row]').count(),20);
  assert.doesNotMatch((await page.locator('[data-au-claim-row]').allInnerTexts()).join('\n'),/Not started/i,'original case rows show useful identity and excerpts instead of repeating their initial status');
  await page.locator('.au-nav [data-au-nav="knowledge"]').click();await eventually(()=>page.locator('[data-au-knowledge-identity]').count().then(count=>count===1),'the actual recorded procedure index did not render');
  const selected=page.locator('[data-au-knowledge-identity]');assert.equal(await selected.locator('[data-au-inspect]').count(),0,'the main procedure reading has no per-version or reuse technical buttons');
  const history=page.locator('[data-au-inspect="knowledge-index"]');assert.equal(await history.count(),1);assert.equal(await history.innerText(),'History');await history.focus();await page.keyboard.press('Enter');
  const drawer=page.locator('.au-record-dialog[open] pre');assert.equal(await drawer.getAttribute('data-au-record-kind'),'knowledge-index');assert.deepEqual(JSON.parse(await drawer.textContent()),expected,'History preserves all exact versions, uses and quarantine records rather than only the selected friendly procedure');
  assert.equal(expected.versions.length,2);assert.equal(expected.uses.length,5);assert.equal(expected.quarantined.length,2);await closeRecord(page);assert.equal(await history.evaluate(element=>document.activeElement===element),true);
});

test('Cases pages all 150 originals and Demo enters their exact canonical identities as autoplaying real claims', async t => {
  const page = await fixturePage(t, {presentationSuite:'replay'});
  const actual=await collectVisiblePages(page);
  assert.equal(new Set(actual).size,150);assert.deepEqual(sorted(actual),sorted(originals.map(row=>row.claim_id)));
  const collectionCalls=await calls(page,'/claims');let nextOffset=0;
  for(const call of collectionCalls){const params=new URL(call.url,'http://fixture.invalid').searchParams;assert.equal(Number(params.get('offset')||0),nextOffset);nextOffset+=Math.min(Number(params.get('limit')||50),159-nextOffset);}assert.equal(nextOffset,159);
  await page.evaluate(()=>window.__controller.showDemonstration(true,'legacy'));
  await eventually(()=>page.locator('[data-au-claim-title]').count().then(count=>count===1),'Demo did not enter a real claim');
  assert.equal(new URL(page.url()).hash.split('?')[0],`#autonomous/claim/${demoIds[0]}`);
  assert.equal(await page.locator('.au-demonstration').count(),0,'Demo has no separate showcase page');
  assert.equal(await page.locator('[data-au-demo-stop]').count(),1,'Demo starts accepted prefix playback on entry');
  await title(page,demoIds[0]);assert.deepEqual((await visibleRecord(page)).state,fixtureData({presentationSuite:'replay'}).acceptedHistories[demoIds[0]][0].state);
  await page.locator('[data-au-inspect="demo"]').click();
  const picker=page.locator('.au-record-dialog[open]');const ids=await picker.locator('[data-au-demo-case]').evaluateAll(rows=>rows.map(row=>row.dataset.auDemoCase));
  assert.deepEqual(sorted(ids),sorted(demoIds));assert.ok(ids.every(id=>actual.includes(id)&&!historicalIds.includes(id)));
  assert.equal(await picker.locator('section').count(),3,'the canonical roster retains three recorded identities per supplied domain');
  await picker.locator(`[data-au-demo-case="${demoIds[3]}"]`).click();await title(page,demoIds[3]);
  assert.equal((await visibleRecord(page)).state.claim_id,demoIds[3]);assert.equal(await page.locator('[data-au-demo-stop]').count(),1);
  await page.locator('.au-nav [data-au-nav="work"]').click();await eventually(()=>page.locator('[data-au-claim-row]').count().then(count=>count===20),'Cases did not restore all originals');
  await page.evaluate(()=>{location.hash='#autonomous/work';});await eventually(()=>page.locator('[data-au-claim-row]').count().then(count=>count===20),'the prior Work route did not resolve to Cases');

});

test('the 150 originals and nine added histories retain distinct scopes through hash navigation and reload', async t => {
  const page = await fixturePage(t);
  const rowIds = () => page.locator('[data-au-claim-row]').evaluateAll(rows => rows.map(row => row.dataset.auClaimRow));
  assert.deepEqual(sorted(await rowIds()),sorted(originals.slice(0,20).map(row=>row.claim_id)));
  assert.equal(await page.locator('[data-au-collection-scope="originals"]').getAttribute('aria-pressed'), 'true');
  assert.equal(await page.locator('[data-au-domain="all"]').count(), 1);
  for (const domain of ['defect_mold_heating', 'lease_termination_dispute', 'rent_increase_dispute']) assert.equal(await page.locator(`[data-au-domain="${domain}"]`).count(), 1);
  await page.locator('.au-nav [data-au-nav="work"]').click();
  await page.locator('[data-au-collection-scope="added"]').click();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 9), 'Added cases did not retain all nine histories');
  assert.deepEqual(sorted(await rowIds()), sorted(historicalIds));
  assert.equal(new URL(page.url()).hash, '#autonomous/cases?scope=added');
  assert.match(await page.locator('[data-au-collection-scope="added"]').innerText(), /Added cases/);
  await page.goBack();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 20), 'Back did not restore Originals');
  assert.deepEqual(sorted(await rowIds()),sorted(originals.slice(0,20).map(row=>row.claim_id)));
  await page.goForward();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 9), 'Forward did not restore Added cases');
  await page.reload();
  await mountFixture(page);
  assert.equal(new URL(page.url()).hash, '#autonomous/cases?scope=added');
  assert.deepEqual(sorted(await rowIds()), sorted(historicalIds));
  await page.locator('[data-au-collection-scope="originals"]').click();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 20), 'Originals did not restore after Added reload');
  assert.equal(await page.locator('[data-au-domain="all"]').count(), 1);
});

test('a newly remembered native intake appears in Added cases while original counts remain 150', async t => {
  const id = historicalIds.at(-1), page = await fixturePage(t, {rememberedNativeId: id});
  await open(page, id);
  await title(page, id);
  await page.evaluate(() => { window.__fixture.holdCollections = true; });
  await page.locator('.au-nav [data-au-nav="work"]').click();
  assert.equal(await page.locator('[data-au-claim-row]').count(), 20);
  assert.equal(await page.locator('[data-au-domain="all"]').count(), 1);
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
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 20), 'remembering an added intake changed original membership');
  assert.equal(await page.locator(`[data-au-claim-row="${id}"]`).count(), 0);
});

test('Investigation complete groups completed codes without changing the raw claim or its legal outcome', async t => {
  const page = await fixturePage(t, {completeStatuses: true});
  await page.locator('[data-au-collection-scope="added"]').click();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 9), 'Added case statuses did not render');
  const filter=page.locator('[data-au-filter="investigation_complete"]');assert.equal(await filter.innerText(),'Investigation complete');assert.equal(await page.locator('select').count(),0);await filter.click();
  assert.deepEqual(sorted(await page.locator('[data-au-claim-row]').evaluateAll(rows => rows.map(row => row.dataset.auClaimRow))), sorted(completeStatusIds));
  assert.deepEqual(await page.locator('[data-au-claim-row] > .au-claim-state').allTextContents(), ['Investigation complete', 'Investigation complete', 'Investigation complete']);
  for (const [index, status] of ['completed', 'complete', 'resolved'].entries()) {
    const id = completeStatusIds[index], expected = await page.evaluate(id => window.__fixture.envelopes[id].state.outcome, id);
    await open(page, id);
    await title(page, id);
    assert.equal((await page.locator('[data-au-claim-status]').innerText()).replace(/\.$/,''), 'Investigation complete');
    const saved = JSON.parse(await page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').textContent());
    assert.equal(saved.state.status, status);
    assert.deepEqual(saved.state.outcome, expected);
    assert.deepEqual((await visibleRecord(page)).state.outcome,expected,'the investigation label cannot rewrite the recorded legal outcome');
  }
});

for (const width of [1440, 390]) test(`original messages and exact subjects remain complete and readable at ${width}px`, async t => {
  const id=demoIds[0],page=await fixturePage(t,{width,height:844}),original=originals.find(row=>row.claim_id===id);
  await open(page,id);await title(page,id);
  assert.equal(await page.locator('.au-original-message').textContent(),original.message);
  const geometry=await page.locator('.au-original-message').evaluate(element=>{
    const rect=element.getBoundingClientRect(),style=getComputedStyle(element),canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');ctx.font=`${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
    return {top:rect.top,width:rect.width,height:rect.height,fontSize:parseFloat(style.fontSize),ch:ctx.measureText('0').width,scrollWidth:element.scrollWidth,clientWidth:element.clientWidth,documentWidth:document.documentElement.scrollWidth};
  });
  assert.ok(geometry.fontSize>=15&&geometry.fontSize<=18,'original source text remains comfortably readable');
  assert.ok(geometry.width<=72*geometry.ch+3,'full original message lines have a readable maximum length');
  assert.ok(geometry.width>=280&&geometry.scrollWidth<=geometry.clientWidth+1&&geometry.documentWidth<=width+1,'the exact body fits without clipping or page overflow');
  assert.ok(geometry.top<650,'the actual original body is visible after the quiet header');
  await page.locator('.au-context-nav [data-au-detail="sources"]').click();
  assert.equal(await page.locator('.au-original-title').textContent(),original.subject,'the original subject remains exactly inspectable');
  assert.equal(await page.locator('.au-original-message').textContent(),original.message);
  const sources=await page.locator('[data-au-panel="sources"] [data-au-source]').evaluateAll(rows=>rows.map(row=>({id:row.dataset.auSource,label:row.textContent})));
  const expected=corpusManifest.claims.find(row=>row.claim_id===id).observable_artifacts;
  assert.deepEqual(sources.map(row=>row.id),expected.map(row=>row.artifact_id));assert.deepEqual(sources.map(row=>row.label),expected.map(row=>row.file_name));
  assert.deepEqual((await visibleRecord(page)).state,fixtureData().envelopes[id].state);
  await focusedReceipt(page,`quiet-original-${width}`,{identity:id,geometry,sourceIds:sources.map(row=>row.id)});
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
    fs.writeFileSync('/tmp/casepath-original-jpeg-dialog-390.json', JSON.stringify(await page.evaluate(() => ({dialog: document.querySelector('.au-source-dialog').getBoundingClientRect().toJSON(), image: document.querySelector('.au-native-image').getBoundingClientRect().toJSON(), naturalWidth: document.querySelector('.au-native-image').naturalWidth, naturalHeight: document.querySelector('.au-native-image').naturalHeight, capability: document.querySelector('.au-source-capability').textContent})), null, 2));
  }
  await page.keyboard.press('Escape');
  await eventually(() => page.locator('.au-source-dialog').getAttribute('open').then(value => value === null), 'Escape did not close the source');
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

test('a recovered verified original starts only by explicit intent and an uncertain Start never retries automatically', async t => {
  const id=demoIds[0],page=await fixturePage(t,{originalStartId:id,mismatchedSnapshots:3});
  const originalHash=await page.evaluate(id=>window.__fixture.envelopes[id].state.state_sha256,id);
  await open(page,id);await eventually(async()=>(await calls(page,`/claims/${id}/snapshot`)).length===3&&/automatically/i.test(await page.locator('.au-global-status').innerText()),'the original opening did not retain bounded recovery');
  assert.equal((await calls(page,`/claims/${id}/start`)).length,0);
  await page.clock.runFor(7000);await title(page,id);await eventually(()=>page.locator('[data-au-start]').isEnabled(),'verified recovered original cannot be explicitly started');
  await page.locator('[data-au-start]').click();await eventually(async()=>(await calls(page,`/claims/${id}/start`)).length===1,'one explicit Start was not submitted');
  const [started]=await calls(page,`/claims/${id}/start`);assert.equal(JSON.parse(started.body).expected_revision,0);assert.equal(JSON.parse(started.body).expected_state_sha256,originalHash);assert.equal(started.headers['X-CasePath-Agent-Work'],'1');
  await page.evaluate(id=>{window.__fixture.advance(id);Object.assign(window.__fixture.envelopes[id].state,{status:'completed',phase:'complete'});},id);
  await page.clock.runFor(10000);assert.equal((await calls(page,`/claims/${id}/start`)).length,1,'lost Start response requires an explicit identical retry');
  assert.equal(new URL(page.url()).hash.split('?')[0],`#autonomous/claim/${id}`);assert.equal(await page.locator('[data-au-start]').innerText(),'Retry start');
});

for (const mode of ['replay']) test(`timed ${mode} presentation inspects all nine canonical cases with modal and hidden pauses, then cancels on navigation`, async t => {
  const page = await fixturePage(t, {presentationSuite: mode});
  if (mode === 'replay') await page.evaluate(() => {
    window.__consumedControlStates = [];
    new MutationObserver(() => {
      const record = document.querySelector('[data-au-record-content] > pre[data-au-record-kind="claim"]'); if (!record) return;
      const state = JSON.parse(record.textContent).state;if(!state?.revision)return;const previous = window.__consumedControlStates.at(-1);
      if (!previous || previous.claim_id !== state.claim_id || previous.revision !== state.revision || previous.state_sha256 !== state.state_sha256) window.__consumedControlStates.push(state);
    }).observe(document.querySelector('#workspace'), {childList: true, subtree: true});
  });
  await page.evaluate(()=>window.__controller.showDemonstration(true,'legacy'));
  await playIfPaused(page);
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
  assert.equal(await page.locator('[data-au-demo-resume]').count(), 1, 'inspection requires deliberate resumption of the same presentation');
  await page.locator('[data-au-demo-resume]').click();
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
    for (const id of demoIds) assert.deepEqual((await calls(page, `/claims/${id}/replay`)).map(call => Number(new URL(call.url, 'http://fixture.invalid').searchParams.get('through_seq'))), id === demoIds[0] ? [0,1,2,1,2,1,2] : [0,1,2], 'each replay verifies both prefixes; deliberate Resume revalidates the first case\'s cancelled prefetch');
    const consumed = await page.evaluate(() => window.__consumedControlStates);
    const expected = await page.evaluate(ids => ids.flatMap(id => window.__fixture.acceptedHistories[id].slice(1).map(record => record.state)), demoIds);
    assert.deepEqual(consumed, expected, 'all nine authored control histories consume each exact accepted prefix once in roster order');
  } else {
    assert.equal(posts.length, 9, 'Live Play may admit one Start for each of the nine unprocessed originals');
    assert.deepEqual(posts.map(call => call.url.match(/\/claims\/([^/]+)\//)[1]), demoIds);
    for (const call of posts) assert.equal(JSON.parse(call.body).expected_revision, 0);
  }
  // Restart an active presentation and abandon it through product navigation.
  // Live originals are already processed, so this restart has no Start intent.
  await page.evaluate(()=>window.__controller.showDemonstration(true,'legacy'));
  await playIfPaused(page);
  await title(page, demoIds[0]);
  await page.locator('.au-nav [data-au-nav="work"]').click();
  const cancelledReads = (await reads()).length, cancelledPosts = await page.evaluate(() => window.__fixture.calls.filter(call => call.method === 'POST').length);
  await page.clock.runFor(20000);
  assert.equal((await reads()).length, cancelledReads, 'navigation must abandon every pending presentation read');
  assert.equal(await page.evaluate(() => window.__fixture.calls.filter(call => call.method === 'POST').length), cancelledPosts);
  assert.equal(await page.locator('[data-au-claim-row]').count(), 20);
});

test('a replay control history without an accepted operational outcome stops honestly at its exact saved head', async t => {
  const page = await fixturePage(t, {presentationSuite: 'replay', presentationOutcome: false});
  await page.evaluate(()=>window.__controller.showDemonstration(true,'legacy'));
  await playIfPaused(page);
  await title(page, demoIds[0]);
  // The first accepted graph has its own reading interval. Reach the actual
  // saved head before checking its outcome gate, rather than assuming 700ms.
  for(let tick=0;Number(await page.locator('[data-au-revision]').getAttribute('data-au-revision'))<2&&tick<300;tick++)await page.clock.runFor(20);
  assert.equal(await page.locator('[data-au-revision]').getAttribute('data-au-revision'),'2');
  await eventually(() => page.locator('.au-global-status').innerText().then(text => /no settled operational outcome/i.test(text)), 'the authored history without an outcome did not stop');
  const saved = JSON.parse(await page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').textContent());
  const expected = await page.evaluate(id => window.__fixture.acceptedHistories[id][2], demoIds[0]);
  assert.deepEqual(saved.state, expected.state);
  assert.deepEqual(saved.projection, {...expected.projection, parent_revision: expected.state.revision, parent_state_sha256: expected.state.state_sha256});
  assert.equal(saved.state.outcome, null);
  assert.equal(new URL(page.url()).hash.split('?')[0], `#autonomous/claim/${demoIds[0]}`);
  const before = (await calls(page, '/replay')).length;
  await page.clock.runFor(12000);
  assert.equal((await calls(page, '/replay')).length, before);
  assert.equal((await calls(page, `/claims/${demoIds[1]}/replay`)).length, 0);
  assert.deepEqual(await page.evaluate(() => window.__fixture.calls.filter(call => call.method !== 'GET')), []);
});

test('leaving a recovering original cancels its delayed read without admitting Start', async t => {
  const id=demoIds[0],page=await fixturePage(t,{originalStartId:id,mismatchedSnapshots:3});
  await open(page,id);await eventually(async()=>(await calls(page,`/claims/${id}/snapshot`)).length===3&&/automatically/i.test(await page.locator('.au-global-status').innerText()),'opening recovery did not begin');
  await page.locator('.au-nav [data-au-nav="work"]').click();await page.clock.runFor(10000);
  assert.equal((await calls(page,`/claims/${id}/start`)).length,0);assert.equal((await calls(page,`/claims/${id}/snapshot`)).length,3);assert.equal(await page.locator('[data-au-claim-row]').count(),20);
});

test('overlapping opening reads preserve the newer record and source disclosure while equal revisions remain strict', async t => {
  const page = await fixturePage(t);
  const revision = await page.evaluate(id => window.__fixture.envelopes[id].state.revision, processedId);
  await open(page, processedId); await title(page, processedId);
  await page.evaluate(id => { window.__fixture.holdId = id; window.__fixture.holdRemaining = 1; void window.__controller.refresh(); }, processedId);
  await eventually(() => page.evaluate(() => window.__fixture.held.length === 1), 'the earlier cursor refresh was not held');
  await page.evaluate(id => { window.__fixture.advance(id); void window.__controller.openClaim(id); }, processedId);
  await eventually(async () => (await visibleRecord(page)).state.revision === revision + 1, 'the distinct full snapshot did not render its newer accepted record');
  assert.equal(await page.locator('[data-au-revision]').getAttribute('data-au-revision'),String(revision+1));
  await openFullProcess(page);const chosen = await page.locator('[data-au-node]').last().getAttribute('data-au-node');
  await page.locator(`[data-au-node="${chosen}"]`).click();
  await page.locator('[data-au-detail="sources"]').click();
  const sourceId = await page.locator('[data-au-panel="sources"] [data-au-source]').first().getAttribute('data-au-source');
  await page.locator(`[data-au-panel="sources"] [data-au-source="${sourceId}"]`).click();
  await eventually(() => page.locator('details.au-source-identity').count().then(count => count === 1), 'the current original source identity did not verify');
  await page.locator('details.au-source-identity > summary').click();
  const before = await page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').textContent();
  await page.evaluate(() => { window.__retainedSource = document.querySelector('details.au-source-identity'); for (const held of window.__fixture.held.splice(0)) held.release(); });
  await page.evaluate(() => new Promise(resolve => queueMicrotask(resolve)));
  assert.equal(await page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').textContent(), before, 'the delayed older opening cannot replace the verified newer record');
  assert.equal(await page.evaluate(() => document.querySelector('details.au-source-identity') === window.__retainedSource && window.__retainedSource.open), true);
  assert.equal(new URLSearchParams(new URL(page.url()).hash.split('?')[1]).get('node'),chosen,'source inspection preserves the exact selected decision in its route');
  await page.evaluate(() => window.__controller.refresh());
  assert.equal(await page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').textContent(), before, 'a matching equal revision must remain valid');
  const reads = (await calls(page, `/claims/${processedId}/snapshot`)).length;
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await eventually(async () => (await calls(page, `/claims/${processedId}/snapshot`)).length > reads, 'normal visibility resume did not refresh the saved claim');
  assert.doesNotMatch(await page.locator('.au-global-status').innerText(), /connection restored/i, 'normal visibility resume cannot fabricate a failed connection');
  await page.evaluate(() => { window.__fixture.conflictingHash = true; });
  await page.evaluate(() => window.__controller.refresh());
  assert.match(await page.locator('.au-global-status').innerText(), /saved revision changed identity/i);
  assert.equal(await page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').textContent(), before, 'a conflicting equal-revision hash fails closed while saved work remains visible');
});

test('a Documents link returns to its process step and reload retains the step detail', async t => {
  const page = await fixturePage(t);
  await open(page, processedId);
  await title(page, processedId);
  await page.locator('.au-context-nav [data-au-detail="documents"]').click();
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

test('a recorded document selection retains its exact obligation and fact through picker changes, Back and reload', async t => {
  const page = await fixturePage(t), id = 'auto_265cf377bb7485dce74573c8';
  await open(page, id); await title(page, id);
  const expected = await page.evaluate(id => {
    const s = window.__fixture.envelopes[id].state;
    return s.obligations.filter(row => row.node_id === 'lt_deadline');
  }, id);
  assert.ok(expected.length > 1, 'the recorded decision has multiple document obligations');
  const notice = expected.find(row => row.document_type === 'notice_period_evidence');
  const receipt = expected.find(row => row.document_type === 'proof_of_receipt');
  async function focus(obligation) {
    const hero = page.locator('[data-au-evidence-path]');
    assert.equal(await hero.locator('[data-au-document][data-au-obligation]').getAttribute('data-au-document'), obligation.document_type);
    assert.equal(await hero.locator('[data-au-document][data-au-obligation]').getAttribute('data-au-obligation'), obligation.obligation_id);
    assert.equal(await hero.locator('[data-au-fact]').getAttribute('data-au-fact'), obligation.required_fact_ids[0]);
    const query = new URLSearchParams(new URL(page.url()).hash.split('?')[1]);
    assert.equal(query.get('node'), 'lt_deadline');
    assert.equal(query.get('document'), obligation.document_type);
    assert.equal(query.get('obligation'), obligation.obligation_id);
    assert.equal(query.get('fact'), obligation.required_fact_ids[0]);
  }
  await page.locator('.au-context-nav [data-au-detail="documents"]').click();
  const documentRows = page.locator('[data-au-panel="documents"] .au-obligation');
  const expectedRows = await page.evaluate(id => window.__fixture.envelopes[id].state.obligations.map(row => row.obligation_id || row.document_type), id);
  assert.equal(await documentRows.count(), 11, 'the compact list preserves all eleven recorded requirements');
  assert.deepEqual(sorted(await documentRows.evaluateAll(rows => rows.map(row => row.dataset.auObligation))), sorted(expectedRows));
  const rowGeometry = await documentRows.evaluateAll(rows => rows.slice(0, 3).map(row => { const rect = row.getBoundingClientRect(); return {top: rect.top, bottom: rect.bottom, height: rect.height}; }));
  assert.ok(rowGeometry[2].bottom <= 1000, `at least three real requirements are scannable on arrival: ${JSON.stringify(rowGeometry)}`);
  assert.ok(rowGeometry.every(row => row.height <= 160), 'contextual reasons do not turn the requirements into permanent large panels');
  assert.equal(await documentRows.locator('details[open]').count(), 0);
  await page.locator(`[data-au-panel="documents"] [data-au-obligation="${notice.obligation_id}"] [data-au-select="lt_deadline"]`).click();
  await focus(notice);
  await page.locator('.au-context-nav [data-au-detail="documents"]').click();
  const selectedRequirement = page.locator('[data-au-panel="documents"] .au-obligation[data-selected="true"]');
  assert.equal(await selectedRequirement.count(), 1, 'sharing a process node does not select sibling obligations');
  assert.equal(await selectedRequirement.getAttribute('data-au-obligation'), notice.obligation_id);
  await selectedRequirement.locator('[data-au-select="lt_deadline"]').click();
  assert.deepEqual((await caseDetails(page)).state.obligations.filter(row=>row.obligation_id===notice.obligation_id),[notice]);await title(page,id);
  await focus(notice);
  await selectDocument(page,receipt.document_type);
  await focus(receipt);
  // The old picker retained this fact while showing the notice-period document.
  await selectFact(page,'fact:proof_of_receipt');
  await selectDocument(page,notice.document_type);
  await focus(notice);
  const route = new URL(page.url()).hash;
  await selectDocument(page,notice.document_type);
  assert.equal(new URL(page.url()).hash, route);
  await page.goBack();
  await eventually(() => page.locator('[data-au-evidence-path] [data-au-fact]').getAttribute('data-au-fact').then(value => value === receipt.required_fact_ids[0]), 'Back lost the previous exact obligation');
  await focus(receipt);
  await page.goForward();
  await eventually(() => page.locator('[data-au-evidence-path] [data-au-fact]').getAttribute('data-au-fact').then(value => value === notice.required_fact_ids[0]), 'Forward lost the requested obligation');
  await focus(notice);
  await page.reload(); await mountFixture(page);
  await focus(notice);
  assert.equal(await page.locator('[data-au-panel="step"]').isVisible(), true);
  await selectDocument(page,receipt.document_type);
  await page.locator('.au-context-nav [data-au-detail="sources"]').click();
  await page.goBack();
  await eventually(() => page.locator('[data-au-panel="step"]').isVisible(), 'Back to an exact requirement retained the later Sources context');
  await focus(notice);
  await page.goForward();
  await eventually(() => page.locator('[data-au-panel="sources"]').isVisible(), 'Forward did not restore the explicit Sources context');
  await page.locator('.au-context-nav [data-au-detail="documents"]').click();
  await page.goBack();
  await eventually(() => page.locator('[data-au-panel="step"]').isVisible(), 'Back to an exact requirement retained the later Documents context');
  await focus(notice);
  await page.reload(); await mountFixture(page);
  assert.equal(await page.locator('[data-au-panel="step"]').isVisible(), true);
  await focus(notice);
});

test('verified new-source prefixes retain prior assessment through unavailable and failed rereading, then accepted reassessment clears it', async t => {
  const fixture = priorAssessmentFixture(), id = fixture.claim_id;
  const page = await fixturePage(t, {priorAssessment: 'assessed'});
  await open(page, id); await title(page, id);
  assert.equal(await page.locator('[data-au-assessment-freshness]').count(), 0);
  const newSource = fixture.states.arrived.source_descriptors.find(row => !fixture.states.assessed.source_descriptors.some(old => old.artifact_id === row.artifact_id));
  for (const position of ['arrived', 'deferred', 'same_roster_retry']) {
    await page.evaluate(position => window.__fixture.loadAccepted(position), position);
    await page.evaluate(() => window.__controller.refresh());
    const notice=page.locator('.au-claim-constraint');
    assert.equal(await notice.isVisible(), true, position);
    assert.match(await notice.innerText(), /Prior assessment:/);
    await page.locator('.au-context-nav [data-au-detail="sources"]').click();
    const source = page.locator(`[data-au-panel="sources"] [data-au-source-freshness="unassessed"]`).filter({has: page.locator(`[data-au-source="${newSource.artifact_id}"]`)});
    assert.equal(await source.count(), 1);
    assert.match(await source.innerText(), position==='arrived'?/Original file received · Awaiting assessment/:/Text available for assessment · Awaiting assessment/);
    const rendered = JSON.parse(await page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').textContent()).state;
    assert.deepEqual(rendered, fixture.states[position], `${position} presentation cannot rewrite a saved field or hash`);
    assert.deepEqual(rendered.facts, fixture.states.assessed.facts);
    assert.deepEqual(rendered.actions, fixture.states.assessed.actions);
    assert.doesNotMatch(await notice.innerText(), /contradiction|invalidated/i);
  }
  await page.locator(`[data-au-panel="sources"] [data-au-source="${newSource.artifact_id}"]`).click();
  await eventually(() => page.locator('dialog[open] [data-au-source-freshness="unassessed"]').count().then(count => count === 1), 'the new source viewer lost its assessment distinction');
  await page.locator('[data-au-close]').click();
  await page.evaluate(() => window.__fixture.loadAccepted('reassessed'));
  await page.evaluate(() => window.__controller.refresh());
  assert.equal(await page.locator('[data-au-assessment-freshness], [data-au-panel] [data-au-source-freshness="unassessed"]').count(), 0);
  const after = JSON.parse(await page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').textContent()).state;
  assert.deepEqual(after, fixture.states.reassessed);
  assert.equal(after.facts.find(row => row.fact_id === 'condition:family_home').status, 'false');
  assert.deepEqual(after.actions.slice(0, fixture.states.assessed.actions.length), fixture.states.assessed.actions);
  await page.locator(`[data-au-panel="sources"] [data-au-source="${newSource.artifact_id}"]`).click();
  await eventually(() => page.locator('dialog[open] details.au-source-identity').count().then(count => count === 1), 'the reassessed source did not reopen');
  assert.equal(await page.locator('dialog[open] [data-au-source-freshness="unassessed"]').count(), 0);
  await page.locator('[data-au-close]').click();
  const failed = await fixturePage(t, {priorAssessment: 'failed'});
  await open(failed, id); await title(failed, id);
  await failed.evaluate(() => window.__controller.refresh());
  assert.match(await failed.locator('.au-claim-constraint').innerText(),/Prior assessment/);
  assert.deepEqual(JSON.parse(await failed.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').textContent()).state, fixture.states.failed);
  assert.deepEqual(fixture.states.failed.receipts, fixture.states.assessed.receipts);
});

test('historical verified replay derives assessment coverage from that prefix and preserves every saved state field', async t => {
  const fixture = priorAssessmentFixture(), page = await fixturePage(t, {priorAssessment: 'reassessed'}), id = fixture.claim_id;
  for (const position of ['assessed', 'arrived', 'deferred', 'reassessed']) {
    const through = fixture.revisions[position];
    await page.evaluate(({id, through}) => window.__controller.openClaim(id, true, {mode: 'replay', through}), {id, through});
    await title(page, id);
    assert.match(await page.locator('.au-work-head').innerText(), /Recorded investigation/);
    assert.equal(/Prior assessment/.test(await page.locator('.au-claim-constraint').innerText()),['arrived','deferred'].includes(position),position);
    const rendered = JSON.parse(await page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').textContent()).state;
    assert.deepEqual(rendered, fixture.states[position]);
  }
  assert.equal((await calls(page, `/claims/${id}/snapshot`)).length, 0);
});

async function observeAnimations(page) {
  await page.evaluate(() => {
    window.__acceptedAnimations = [];
    window.__uiAnimations = [];
    const original = Element.prototype.animate;
    Element.prototype.animate = function(frames, options) {
      const record = {event:this.dataset.auSemanticEvent||null,node:this.dataset.auNode||null,fact:this.dataset.auFact||null,document:this.dataset.auDocument||null,source:this.dataset.auSource||null,kind:this.dataset.auSemanticKind||null,publication:this.dataset.auKnowledgePublication||null,formingGroup:this.matches('.au-forming-work [data-au-graph-pan]')?'process':this.matches('.au-forming-documents .au-obligations')?'documents':null,options,frames};
      window.__uiAnimations.push(record);
      if (record.event) window.__acceptedAnimations.push(record);
      return original.call(this, frames, options);
    };
  });
}

test('a recorded withheld knowledge candidate remains distinguishable and exposes its exact accepted journal record', async t => {
  const id='auto_7373bbf206ab25bacf71b82e',page=await fixturePage(t,{recordedHistoryId:id});
  const event=captured[`${base}/claims/${id}/events?after=0`].events.at(-1);assert.equal(event.payload.knowledge.qualification.status,'quarantined');
  await observeAnimations(page);await open(page,id);await title(page,id);
  await page.locator('.au-work-head [data-au-detail="activity"]').click();
  const entry=page.locator(`[data-au-inspect="event"][data-au-record-id="${event.seq}"]`);assert.match(await entry.locator('..').innerText(),/Knowledge candidate withheld/i);
  await entry.click();assert.deepEqual(JSON.parse(await page.locator('.au-record-dialog[open] pre').textContent()),event);await closeRecord(page);
  await page.locator('.au-context-nav [data-au-detail="knowledge"]').click();assert.equal(await page.locator('[data-au-panel="knowledge"] .au-knowledge-publication [data-au-knowledge]').count(),0,'withheld candidate cannot borrow a qualified version link');
  assert.doesNotMatch(await page.locator('[data-au-panel="knowledge"] .au-knowledge-publication').innerText(),/Qualified for reuse/);await title(page,id);
  assert.deepEqual((await visibleRecord(page)).state,captured[`${base}/claims/${id}`].state);
});

for(const kind of ['action.completed','knowledge.published','knowledge.used'])test(`the exact accepted ${kind} result survives live refresh and a settled verified prefix inspection`,async t=>{
  const fixture=priorAssessmentFixture(),id=fixture.claim_id,event=fixture.snapshots.reassessed.events.find(row=>row.kind===kind),through=event.seq;
  const page=await fixturePage(t,{priorAssessment:'assessed',acceptedPrefix:through-1});await open(page,id);await title(page,id);await observeAnimations(page);
  await page.evaluate(seq=>window.__fixture.loadAccepted(seq),through);await page.evaluate(()=>window.__controller.refresh());
  assert.deepEqual((await visibleRecord(page)).state,fixture.prefixes[through].state);
  const rendered=await page.evaluate(()=>window.__uiAnimations.length);await page.evaluate(async()=>{await window.__controller.refresh();await window.__controller.refresh();});
  assert.equal(await page.evaluate(()=>window.__uiAnimations.length),rendered,'repeated identical accepted reads cannot create another motion');
  await page.locator('.au-work-head [data-au-detail="activity"]').click();await page.locator(`[data-au-inspect="event"][data-au-record-id="${through}"]`).click();
  assert.deepEqual(JSON.parse(await page.locator('.au-record-dialog[open] pre').textContent()),event,'native drawer exposes the exact accepted event and receipt');await closeRecord(page);
  if(kind==='action.completed'){
    const citation=event.payload.result.citations[0],source=page.locator(`[data-au-panel="activity"] [data-au-source="${citation.artifact_id}"]`).first();
    assert.equal(JSON.parse(await source.getAttribute('data-au-citation')).quote,citation.quote);await source.focus();await page.keyboard.press('Enter');
    await eventually(()=>page.locator('.au-source-dialog[open] mark').count().then(count=>count===1),'accepted action citation did not verify by keyboard');assert.equal(await page.locator('.au-source-dialog[open] mark').textContent(),citation.quote);
    await page.locator('[data-au-close]').click();assert.equal(await source.evaluate(element=>document.activeElement===element),true);
  }else{
    await page.locator('.au-context-nav [data-au-detail="knowledge"]').click();
    const records=(await caseDetails(page)).state,recorded=kind==='knowledge.used'?records.knowledge_uses.at(-1):records.knowledge_published.at(-1);assert.deepEqual(recorded,event.payload.knowledge);
  }
  const replay=await fixturePage(t,{priorAssessment:'reassessed'});await replay.evaluate(({id,through})=>window.__controller.openClaim(id,true,{mode:'replay',through}),{id,through});await title(replay,id);await observeAnimations(replay);
  assert.deepEqual((await visibleRecord(replay)).state,fixture.prefixes[through].state);await replay.evaluate(()=>window.__controller.refresh());assert.deepEqual(await replay.evaluate(()=>window.__uiAnimations),[],'an already verified prefix stays settled');
});

for(const interruption of ['reduce','reconnect','dialog','keyboard','hidden'])test(`accepted causal motion stays still during ${interruption} while its exact action receipt remains inspectable`,async t=>{
  const fixture=priorAssessmentFixture(),id=fixture.claim_id,event=fixture.snapshots.reassessed.events.find(row=>row.kind==='action.completed');
  const page=await fixturePage(t,{priorAssessment:'assessed',acceptedPrefix:event.seq-1});await open(page,id);await title(page,id);
  if(interruption==='reduce')await page.emulateMedia({reducedMotion:'reduce'});
  if(interruption==='reconnect'){await page.evaluate(()=>{window.__fixture.readFailures=1;});await page.evaluate(()=>window.__controller.refresh());assert.match(await page.locator('.au-global-status').innerText(),/paused|interrupted|unavailable/i);}
  if(interruption==='dialog'){await page.locator('.au-context-nav [data-au-detail="sources"]').click();await page.locator('[data-au-panel="sources"] [data-au-source]').first().click();await eventually(()=>page.locator('.au-source-dialog[open]').count().then(count=>count===1),'original source inspection did not open');}
  if(interruption==='keyboard')await page.keyboard.press('Tab');
  if(interruption==='hidden')await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));});
  await observeAnimations(page);await page.evaluate(seq=>window.__fixture.loadAccepted(seq),event.seq);await page.evaluate(()=>window.__controller.refresh());
  if(interruption==='hidden')await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'));});
  assert.deepEqual((await visibleRecord(page)).state,fixture.prefixes[event.seq].state);
  assert.equal(await page.evaluate(()=>window.__uiAnimations.filter(row=>row.node||row.fact||row.document||row.source||row.event).length),0,'inhibited causal targets settle without animation');
});

test('Verified replay stays visible as presentation mode when the accepted prefix status is Working', async t => {
  const page = await fixturePage(t, {replayStatus: 'running'});
  await page.evaluate(id => { void window.__controller.openClaim(id, true, {mode: 'replay', through: 2}); }, processedId);
  await title(page, processedId);
  assert.match(await page.locator('.au-work-head').innerText(), /Recorded investigation/);
  assert.equal((await page.locator('[data-au-claim-status]').innerText()).replace(/\.$/,''), 'Working');
  assert.match(new URL(page.url()).hash, /mode=replay/);
  assert.match(new URL(page.url()).hash, /through=2/);
  assert.equal((await calls(page, `/claims/${processedId}/replay`)).length, 1);
  assert.equal(await page.locator('[data-au-arrival], [data-au-pause], [data-au-resume], [data-au-start]').count(), 0, 'a replay cannot expose live write controls');
  const before = (await calls(page, `/claims/${processedId}/snapshot`)).length;
  await page.evaluate(async () => { await window.__controller.refresh(); await window.__controller.refresh(); });
  await page.clock.runFor(7000);
  assert.equal((await calls(page, `/claims/${processedId}/snapshot`)).length, before, 'a replay must not poll live state');
  assert.match(await page.locator('.au-work-head').innerText(), /Recorded investigation/);
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
    if (!await page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').count()) return false;
    return JSON.parse(await page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').textContent()).state.revision === 1;
  }, 'background polling did not observe the accepted revision after the Start response was lost');
  assert.equal(await page.locator('[data-au-revision]').getAttribute('data-au-revision'),'1');
  await eventually(async () => await currentReadState(page) === 'verified' && await page.locator('[data-au-start]').innerText() === 'Retry start' && await page.locator('[data-au-start]').isEnabled(), 'the fresh accepted snapshot must finish the pending admission and restore its exact Start retry');
  assert.equal(await page.locator('[data-au-start]').innerText(), 'Retry start');
  assert.equal(await page.locator('[data-au-start]').isEnabled(), true, 'the nonzero accepted revision must retain its original pending Start retry');
  assert.equal((await posts()).length, 1, 'a network-uncertain Start cannot retry automatically');
  const liveReads = (await calls(page, `/claims/${startId}/snapshot`)).length;
  await page.evaluate(id => { void window.__controller.openClaim(id, true, {mode: 'replay', through: 1}); }, startId);
  await title(page, startId);
  assert.match(await page.locator('.au-work-head').innerText(), /Recorded investigation/);
  assert.equal(await page.locator('[data-au-arrival], [data-au-pause], [data-au-resume], [data-au-start]').count(), 0, 'replay must hide write controls even when that claim has a pending Start');
  await page.evaluate(() => window.__controller.refresh());
  assert.equal((await calls(page, `/claims/${startId}/snapshot`)).length, liveReads, 'refreshing the pending claim in replay cannot read live state');
  assert.equal((await posts()).length, 1, 'entering replay cannot submit the pending Start');
  await page.evaluate(() => { window.__fixture.providerReady = false; });
  await page.locator('.au-nav [data-au-nav="work"]').click();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 20), 'Cases did not restore after an uncertain Start');
  await page.locator(`[data-au-claim-row="${startId}"] [data-au-claim="${startId}"]`).click();
  await title(page, startId);
  assert.equal(new URL(page.url()).hash, `#autonomous/claim/${startId}`);
  assert.equal((await posts()).length, 1, 'returning to the original must preserve the pending request without submitting it');
  await eventually(() => page.locator('[data-au-start]').isEnabled(), 'the original pending Start retry must remain available after readiness changes');
  assert.equal(await page.locator('[data-au-start]').innerText(), 'Retry start');
  await page.locator('[data-au-start]').click();
  await eventually(async () => {
    const record = await page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').count();
    if (!record) return false;
    return JSON.parse(await page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').textContent()).state.revision >= 2;
  }, 'Start did not read the concurrently advanced matching snapshot');
  const [initial, retry] = await posts();
  assert.equal((await posts()).length, 2, 'each explicit Start click must make one POST');
  assert.equal(retry.body, initial.body, 'retry must preserve the exact JSON and idempotency key across navigation');
  assert.deepEqual(retry.headers, initial.headers);
  const saved = JSON.parse(await page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').textContent());
  assert.equal(saved.state.claim_id, startId);
  assert.equal(saved.state.revision, 2);
  assert.equal(saved.projection.state_sha256, saved.state.state_sha256);
  assert.deepEqual(saved.state.source_descriptors, original.source_descriptors, 'Start must preserve the original source identity');
  assert.equal(saved.state.title, original.title);
  assert.doesNotMatch(await page.locator('.au-work-head').innerText(), /Recorded investigation/);
  assert.equal(new URL(page.url()).hash, `#autonomous/claim/${startId}`);
  assert.equal(await page.locator('[data-au-revision]').getAttribute('data-au-revision'),'2');
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
  await eventually(() => page.locator('.au-source-dialog').getAttribute('open').then(value => value !== null), 'The original source did not open');
  await eventually(() => page.locator('.au-source-body').count().then(count => count === 1), 'the original source text did not verify');
  assert.equal(await page.locator('.au-source-body').textContent(), original.message);
  assert.equal(await page.locator('[data-au-node], [data-au-edge]').count(), 0);
});

test('an atomic snapshot renders a matching state and cursor even while a writer advances after each read', async t => {
  const page = await fixturePage(t, {atomicWriter: true, splitWriter: true});
  const revision = await page.evaluate(id => window.__fixture.envelopes[id].state.revision, processedId);
  await open(page, processedId);
  await title(page, processedId);
  assert.equal(await page.locator('[data-au-revision]').getAttribute('data-au-revision'),String(revision));
  assert.ok(await page.locator('[data-au-node]').count() > 1, 'the verified snapshot renders its saved substantive graph');
  assert.equal((await calls(page, `/claims/${processedId}`)).length, 0, 'atomic reads cannot split state and events');
  assert.equal((await calls(page, `/claims/${processedId}/events`)).length, 0);
  assert.deepEqual((await calls(page, `/claims/${processedId}/snapshot`)).map(call => new URL(call.url, 'http://fixture.invalid').searchParams.get('after')), ['0']);
  await page.evaluate(() => window.__controller.refresh());
  await eventually(()=>page.locator('[data-au-revision]').getAttribute('data-au-revision').then(value=>value===String(revision+1)), 'polling did not render the next atomic revision');
  assert.deepEqual((await calls(page, `/claims/${processedId}/snapshot`)).map(call => new URL(call.url, 'http://fixture.invalid').searchParams.get('after')), ['0', String(revision)]);
  await page.locator('.au-context-nav [data-au-detail="documents"]').click();
  assert.equal(await page.locator('[data-au-graph]').isVisible(), false, 'Documents must hide the process graph');
  await page.locator('.au-context-nav [data-au-detail="sources"]').click();
  assert.equal(await page.locator('[data-au-graph]').isVisible(), false, 'Original sources must hide the process graph');
  await page.locator('.au-context-nav [data-au-detail="step"]').click();
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

test('quiet work: bounded case pages preserve all original membership, off-page search and domain history',async t=>{
  const page=await fixturePage(t),first=await originalPageIds(page),params=()=>new URLSearchParams(new URL(page.url()).hash.split('?')[1]);
  assert.deepEqual(first,originals.slice(0,20).map(row=>row.claim_id));
  await page.locator('[data-au-page="2"]').click();const second=await originalPageIds(page);assert.deepEqual(second,originals.slice(20,40).map(row=>row.claim_id));assert.equal(params().get('page'),'2');
  await page.goBack();await eventually(()=>originalPageIds(page).then(ids=>JSON.stringify(ids)===JSON.stringify(first)),'Back did not restore page one');
  await page.goForward();await eventually(()=>originalPageIds(page).then(ids=>JSON.stringify(ids)===JSON.stringify(second)),'Forward did not restore page two');
  const domain='lease_termination_dispute',expected=originals.filter(row=>browsing.get(row.claim_id).domain===domain).map(row=>row.claim_id);
  await page.locator(`[data-au-domain="${domain}"]`).click();assert.equal(params().get('domain'),domain);assert.equal(params().get('page'),null);
  const domainIds=await collectVisiblePages(page);assert.deepEqual(domainIds,expected);assert.equal(new Set(domainIds).size,50);assert.equal(await page.locator('[data-au-claim-row]').count(),10);
  const id=expected.at(-1),search=page.locator('[data-au-claim-search]');await search.fill(id);
  await eventually(()=>originalPageIds(page).then(ids=>ids.length===1&&ids[0]===id),'global cached search did not find the original beyond the first page');
  assert.equal(params().get('q'),id);assert.equal(params().get('page'),null);assert.equal(await search.evaluate(element=>document.activeElement===element),true,'typing preserves the native search field');
  assert.match(await page.locator('[data-au-pagination]').innerText(),/Page 1 of 1/);
  const searchRoute=new URL(page.url()).hash;await page.locator(`[data-au-claim="${id}"]`).click();await title(page,id);await page.goBack();
  await eventually(()=>new URL(page.url()).hash===searchRoute&&page.locator('[data-au-claim-row]').count().then(count=>count===1),'Back from a selected case lost its search/domain/page context');
  assert.equal(await page.locator('[data-au-claim-search]').inputValue(),id);assert.deepEqual(await originalPageIds(page),[id]);
  await search.fill('');await page.locator('[data-au-domain="all"]').click();const all=await collectVisiblePages(page);assert.deepEqual(all,originals.map(row=>row.claim_id));assert.equal(new Set(all).size,150);
});

test('quiet work: known original previews remain exact and read only through a held malformed read until fresh verification',async t=>{
  const id=originals.find(row=>!demoIds.includes(row.claim_id)).claim_id,original=originals.find(row=>row.claim_id===id),page=await fixturePage(t,{holdId:id,holdRemaining:1,corruptProjection:true,providerReady:true});
  const assertPreview=async()=>{
    const preview=page.locator(`[data-au-preview="catalog"][data-au-preview-claim="${id}"]`);assert.equal(await preview.isVisible(),true);
    assert.equal(await preview.locator('[data-au-catalog-title]').textContent(),original.subject);
    const displayed=await preview.locator('.au-original-message').textContent(),body=displayed.replace(/…$/,'');
    assert.ok(body.length>=120&&[...displayed].length<=240,'the pending preview exposes substantive original content within its bounded reading length');assert.equal(original.message.startsWith(body),true,'the displayed excerpt comes from this exact original message');
    if(body.length<original.message.length)assert.match(original.message.slice(body.length,body.length+1),/\s/,'a clipped preview ends at a whole original word');
    assert.equal(await page.locator('[data-au-revision], [data-au-state-sha], [data-au-node], [data-au-fact], [data-au-obligation], [data-au-outcome], [data-au-claim-title], [data-au-start], [data-au-pause], [data-au-resume], [data-au-arrival], [data-au-submit], input[type=file]').count(),0,'a catalog excerpt cannot grant accepted state or command authority');
  };
  await page.locator(`[data-au-claim="${id}"]`).click();await eventually(()=>page.evaluate(()=>window.__fixture.held.length===1),'the fresh claim read was not held');await assertPreview();
  await page.evaluate(()=>{window.__fixture.holdId=null;for(const held of window.__fixture.held.splice(0))held.release();});
  await eventually(()=>currentReadState(page).then(state=>state==='failed'),'the malformed projection was not rejected');await assertPreview();
  assert.deepEqual(await page.evaluate(()=>window.__fixture.calls.filter(call=>call.method!=='GET')),[]);
  await page.evaluate(()=>{window.__fixture.corruptProjection=false;});await page.clock.runFor(1601);await title(page,id);assert.equal(await currentReadState(page),'verified');assert.equal(await page.locator('[data-au-preview]').count(),0);
  assert.deepEqual((await visibleRecord(page)).state,fixtureData().envelopes[id].state);assert.equal(await page.locator('[data-au-start]:enabled').count(),1,'only the freshly verified original can expose its guarded Start');
  await open(page,'clm_ffffffffffffffff');await eventually(()=>page.locator('[data-au-preview="unknown"]').count().then(count=>count===1),'an unknown claim borrowed a catalog case');
  assert.equal(await page.locator('[data-au-catalog-title], .au-original-message, [data-au-revision], [data-au-start]').count(),0);
});

test('quiet work: acquired MIME originals use only their bound parsed message while exact wire bytes and text hashes stay inspectable',async t=>{
  const mime=mimeDrawerFixture();assert.match(mime.text,/MIME-Version:/);assert.notEqual(mime.text,mime.intake.customer_message.body);
  for(const mode of ['bound','foreign','unbound','supporting','bound-plain','unbound-plain'])await t.test(mode,async t=>{
    const page=await fixturePage(t,{mimeDrawer:mode,width:390,height:844});await open(page,mime.claim_id);await title(page,mime.claim_id);
    const excerpt=page.locator('.au-acquired-text'),source=fixtureData({mimeDrawer:mode}).envelopes[mime.claim_id].state.acquired_sources[0];
    if(mode==='bound'||mode==='bound-plain'){
      assert.equal(await excerpt.textContent(),[...mime.intake.customer_message.body].slice(0,520).join('')+'…');assert.doesNotMatch(await excerpt.textContent(),/MIME-Version:|Content-Transfer-Encoding:|Content-Type:|^From:/);
      assert.equal(await page.locator('[data-au-source-identity]').getAttribute('data-au-source-identity'),[mime.claim_id,source.artifact_id,source.sha256,source.text_sha256].join(':'));
    }else assert.equal(await excerpt.count(),0,'a foreign, unbound or supporting MIME artifact cannot present wire content as a readable original message');
    const record=await visibleRecord(page);assert.equal(record.state.acquired_sources[0].text,mime.text);assert.equal(record.state.acquired_sources[0].text_sha256,sha(mime.text));assert.equal(record.state.acquired_sources[0].sha256,sha(Buffer.from(mime.bytes,'base64')));
    assert.equal(record.state.graph,null);assert.deepEqual(record.state.facts,[]);assert.deepEqual(record.state.obligations,[]);assert.equal(record.state.outcome,null);
    await page.locator('.au-context-nav [data-au-detail="sources"]').click();await page.locator(`[data-au-panel="sources"] [data-au-source="${source.artifact_id}"]`).first().click();
    await eventually(()=>page.locator('.au-source-dialog[open] .au-source-body').count().then(count=>count===1),'the original MIME source record did not remain openable');
    // HTML parsing normalizes line endings in the displayed pre; the exact
    // CRLF wire text and original byte digest were checked in the UI record.
    assert.equal(await page.locator('.au-source-dialog[open] .au-source-body').textContent(),mime.text.replace(/\r\n/g,'\n'));await page.locator('[data-au-close]').click();
  });
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
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 20), 'navigation did not restore Cases');
  await page.evaluate(() => { window.__fixture.splitWriter = false; });
  await page.clock.runFor(7000);
  assert.equal((await calls(page, `/claims/${processedId}/events`)).length, 3, 'a cancelled opening must not retry after navigation');
  assert.equal(await page.locator('[data-au-claim-title]').count(), 0);
  assert.equal(await page.locator('[data-au-claim-row]').count(), 20);
  assert.equal(new URL(page.url()).hash, '#autonomous/cases');
});

test('a delayed response from an abandoned claim cannot replace the next claim or its route', async t => {
  const page = await fixturePage(t, {holdId: processedId});
  await open(page, processedId);
  await eventually(() => page.evaluate(() => window.__fixture.held.length === 1), 'the first claim snapshot was not held');
  await page.locator('.au-nav [data-au-nav="work"]').click();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 20), 'navigation did not return to Cases');
  await open(page, otherId);
  await title(page, otherId);
  const renderedIdentity = () => page.evaluate(() => ({
    title: document.querySelector('[data-au-claim-title]')?.textContent,
    header: document.querySelector('.au-work-head')?.textContent,
    nodes: [...document.querySelectorAll('[data-au-node]')].map(node => node.dataset.auNode),
    savedRecord: document.querySelector('[data-au-record-content] > pre[data-au-record-kind="claim"]')?.textContent,
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

test('real graph routes retain at least 3:1 effective contrast with dashed excluded branches and coral selection', async t => {
  for (const width of [1440, 390]) {
    const page = await fixturePage(t, {width});
    await open(page, processedId);
    await title(page, processedId);
    await page.clock.runFor(320);
    await page.evaluate(async () => { const animations = document.getAnimations(); for (const animation of animations) animation.finish(); await Promise.allSettled(animations.map(animation => animation.finished)); });
    await openFullProcess(page);const receipt = await connectorContrast(page);
    assert.ok(receipt.some(row => row.kind === 'graph' && row.selected === 'false'), 'the contrast check must include ordinary recorded connections');
    assert.ok(receipt.every(row=>row.kind==='graph'),'the quiet reading path does not invent SVG connections between records');
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

test('the mobile Demo chooser keeps nine domain-bound independent identities and pauses accepted playback', async t => {
  const page=await fixturePage(t,{presentationSuite:'replay',width:390,height:844});
  await page.evaluate(()=>window.__controller.showDemonstration(true,'legacy'));await title(page,demoIds[0]);
  const original=(await visibleRecord(page)).state;assert.equal(original.revision,0);assert.equal(original.status,'not_started');
  await page.locator('[data-au-inspect="demo"]').click();const picker=page.locator('.au-record-dialog[open]');
  assert.deepEqual(await picker.locator('h3').allTextContents(),['Defects & repairs','Lease termination','Rent changes']);
  for(let index=0;index<3;index++)assert.deepEqual(await picker.locator('section').nth(index).locator('[data-au-demo-case]').evaluateAll(rows=>rows.map(row=>row.dataset.auDemoCase)),demoIds.slice(index*3,index*3+3));
  assert.equal(await picker.locator('svg').count(),0,'independent case choice cannot imply process connections between claims');
  const before=(await calls(page,`/claims/${demoIds[0]}/replay`)).length;await page.clock.runFor(7000);assert.equal((await calls(page,`/claims/${demoIds[0]}/replay`)).length,before,'roster inspection pauses prefix playback');
  await picker.locator(`[data-au-demo-case="${demoIds[1]}"]`).click();await title(page,demoIds[1]);assert.equal((await visibleRecord(page)).state.revision,0);assert.equal((await visibleRecord(page)).state.claim_id,demoIds[1]);
  assert.equal(await page.locator('[data-au-demo-stop]').count(),1);await focusedReceipt(page,'quiet-demo-picker-390',{roster:demoIds,independentClaims:true});
});

for (const reducedMotion of ['no-preference', 'reduce']) test(`mobile inspection navigates and centers every real step while retaining forks, excluded routes and free pan (${reducedMotion})`, async t => {
  const page = await fixturePage(t, {width: 390, height: 844});
  await page.emulateMedia({reducedMotion});
  await open(page, processedId);
  await title(page, processedId);
  await openFullProcess(page);const record = await page.evaluate(id => structuredClone(window.__fixture.envelopes[id].state), processedId);
  const ids = record.graph.nodes.map(node => node.node_id);
  assert.equal(ids.length, 11);
  assert.equal(record.graph.edges.length, 13);
  const topology = () => page.locator('[data-au-edge]').evaluateAll(edges => edges.map(edge => [edge.dataset.auEdge, edge.dataset.state]));
  const before = await topology();
  assert.equal(before.length, record.graph.edges.length);
  assert.deepEqual(sorted(await page.locator('[data-au-node]').evaluateAll(nodes => nodes.map(node => node.dataset.auNode))), sorted(ids));
  const assertStep=async index=>{
    assert.equal(await page.locator('[data-au-node][aria-pressed="true"]').getAttribute('data-au-node'),ids[index]);
    assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'),ids[index]);
    assert.equal(new URLSearchParams(new URL(page.url()).hash.split('?')[1]).get('node'),ids[index]);
    const geometry=await page.evaluate(id=>{const viewport=document.querySelector('[data-au-graph-pan]'),node=document.querySelector(`[data-au-node="${id}"]`),area=viewport.getBoundingClientRect(),bounds=node.getBoundingClientRect();return {left:bounds.left,right:bounds.right,viewportLeft:area.left,viewportRight:area.right};},ids[index]);
    assert.ok(geometry.left>=geometry.viewportLeft-1&&geometry.right<=geometry.viewportRight+1,'direct inspection keeps the actual selected step visible');
  };
  for(let index=0;index<ids.length;index++){
    const node=page.locator(`[data-au-node="${ids[index]}"]`);await node.scrollIntoViewIfNeeded();await node.focus();await page.keyboard.press('Enter');await assertStep(index);
    assert.equal(await node.evaluate(element=>document.activeElement===element),true,'native keyboard graph selection keeps focus on its selected decision');
    if(reducedMotion==='reduce')assert.equal(await page.evaluate(()=>document.getAnimations().filter(animation=>animation.playState==='running').length),0);
  }
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
  await page.locator(`[data-au-node="${ids[ids.indexOf(excludedId)+1]}"]`).click();
  await assertStep(ids.indexOf(excludedId)+1);
  if (process.env.CASEPATH_BROWSER_RECEIPTS) await page.screenshot({path: `/tmp/casepath-visual-inspection-390-${reducedMotion}.png`, fullPage: true});
});

test('collection search retains a persistent input affordance and visible focus while filtering exact case IDs', async t => {
  for (const width of [1440, 390]) {
    const page = await fixturePage(t, {width, height: 844});
    const input = page.locator('[data-au-claim-search]');
    const style = () => input.evaluate(element => { const css = getComputedStyle(element); return {border: Number.parseFloat(css.borderBottomWidth), borderStyle: css.borderBottomStyle, shadow: css.boxShadow, outline: Number.parseFloat(css.outlineWidth), outlineStyle: css.outlineStyle, focusVisible: element.matches(':focus-visible'), height: element.getBoundingClientRect().height}; });
    const idle = await style();
    assert.ok(idle.border >= 1 && idle.borderStyle !== 'none', 'search must remain visibly underlined before focus');
    assert.ok(idle.border>=1,'the native search affordance remains visible at rest');
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
  assert.equal((await page.locator('[data-au-claim-status]').innerText()).replace(/\.$/,''), 'Working');
  const completedNodes = page.locator('[data-au-node][data-status="completed"]');
  assert.ok(await completedNodes.count() > 0, 'the accepted record must include completed steps within a working claim');
  for (const label of await completedNodes.locator('.au-node-state').allTextContents()) assert.equal(label, 'Completed');
  const id = await completedNodes.first().getAttribute('data-au-node');
  await completedNodes.first().click();
  assert.equal(await page.locator('.au-step-status').innerText(), 'Completed');
  assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'), id);
  const saved = JSON.parse(await page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').textContent()).state;
  assert.equal(saved.status, 'running');
  assert.deepEqual(saved.evaluation.nodes, expected.nodes);
  assert.deepEqual(saved.actions, expected.actions, 'presentation labels cannot rewrite the accepted action status or receipt');
  await page.locator('.au-work-head [data-au-detail="activity"]').click();
  const actions=page.locator('[data-au-panel="activity"] [data-au-inspect="action"]');assert.equal(await actions.count(),expected.actions.length);
  for(let index=0;index<expected.actions.length;index++){await actions.nth(index).click();const record=JSON.parse(await page.locator('.au-record-dialog[open] pre').textContent());assert.deepEqual(record.result,expected.actions[index].result||expected.actions[index]);assert.equal(record.result.status,'completed');await closeRecord(page);}
  assert.equal((await page.locator('[data-au-claim-status]').innerText()).replace(/\.$/,''),'Working');
});

test('the desktop Demo chooses actual canonical claims without an additional showcase or disclosure journey', async t => {
  const page=await fixturePage(t,{presentationSuite:'replay',width:1440,height:900});
  await page.evaluate(()=>window.__controller.showDemonstration(true,'legacy'));await title(page,demoIds[0]);
  assert.equal(await page.locator('.au-demonstration').count(),0);await page.locator('[data-au-inspect="demo"]').click();
  const picker=page.locator('.au-record-dialog[open]'),rows=picker.locator('[data-au-demo-case]');assert.equal(await rows.count(),9);
  assert.deepEqual(await rows.evaluateAll(elements=>elements.map(element=>element.dataset.auDemoCase)),demoIds);
  for(const id of demoIds){const row=picker.locator(`[data-au-demo-case="${id}"]`);assert.ok((await row.textContent()).trim().length>0);assert.equal(await row.evaluate(element=>element.scrollWidth<=element.clientWidth+1),true);}
  assert.equal(await picker.locator('select,details').count(),0);await focusedReceipt(page,'quiet-demo-picker-1440',{roster:demoIds});
  await picker.locator(`[data-au-demo-case="${demoIds[4]}"]`).click();await title(page,demoIds[4]);
  assert.equal((await visibleRecord(page)).state.claim_id,demoIds[4]);assert.equal(await page.locator('.au-original-message').textContent(),originals.find(row=>row.claim_id===demoIds[4]).message);
});

test('pending raw navigation blocks original admission, timed advancement and delayed replay before route events dispatch', async t => {
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
  await open(opening,id);
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
  await eventually(() => opening.locator('[data-au-claim-row]').count().then(count => count === 20), 'the pending raw route did not restore Cases');
  assert.equal((await calls(opening, `/claims/${id}/start`)).length, 0);

  const timed = await fixturePage(t, {presentationSuite: 'replay'});
  await timed.evaluate(ids => { for (const id of ids) window.__fixture.envelopes[id] = structuredClone(window.__fixture.acceptedHistories[id][2]); }, demoIds);
  await timed.evaluate(()=>window.__controller.showDemonstration(true,'legacy'));
  await playIfPaused(timed);
  await title(timed, id);
  await freezeRoutes(timed);
  await timed.evaluate(() => { location.hash = '#autonomous/cases'; });
  await timed.clock.runFor(5000);
  assert.equal((await calls(timed, `/claims/${demoIds[1]}/replay`)).length, 0, 'a timed presentation cannot open its next case while product navigation is pending');
  assert.deepEqual(await timed.evaluate(() => window.__fixture.calls.filter(call => call.method === 'POST')), []);
  await resumeRoutes(timed);
  await eventually(() => timed.locator('[data-au-claim-row]').count().then(count => count === 20), 'timed pending navigation did not restore Cases');

  const replay = await fixturePage(t, {presentationSuite: 'replay', holdReplayId: id, holdReplayThrough: 1});
  await replay.evaluate(()=>window.__controller.showDemonstration(true,'legacy'));
  await playIfPaused(replay);
  await title(replay, id);
  await replay.clock.runFor(1400);
  await eventually(() => replay.evaluate(() => window.__fixture.held.some(held => held.kind === 'replay')), 'the next accepted replay prefix was not held');
  const prefetchedReads = (await calls(replay, `/claims/${id}/replay`)).length;
  const prefetchedPositions=(await calls(replay,`/claims/${id}/replay`)).map(call=>Number(new URL(call.url,'http://fixture.invalid').searchParams.get('through_seq')));assert.ok(prefetchedReads>=2&&prefetchedPositions.every(seq=>seq<=2),'record inspection may revalidate its cancelled read but prefetch remains at most two prefixes ahead');
  await freezeRoutes(replay);
  await replay.evaluate(() => {
    location.hash = '#autonomous/cases';
    for (const held of window.__fixture.held.splice(0)) held.release();
  });
  await replay.evaluate(async () => { for (let turn = 0; turn < 20; turn++) await Promise.resolve(); });
  await replay.clock.runFor(5000);
  assert.equal(new URL(replay.url()).hash, '#autonomous/cases', 'a delayed accepted replay prefix cannot replace the newly selected product route');
  assert.equal((await calls(replay, `/claims/${id}/replay`)).length, prefetchedReads, 'the abandoned replay cannot request another prefix');
  assert.equal((await calls(replay, `/claims/${demoIds[1]}/replay`)).length, 0);
  assert.deepEqual(await replay.evaluate(() => window.__fixture.calls.filter(call => call.method === 'POST')), []);
  await resumeRoutes(replay);
  await eventually(() => replay.locator('[data-au-claim-row]').count().then(count => count === 20), 'delayed replay cancellation did not retain Cases');
});

const focusedReceiptRoot = process.env.CASEPATH_FOCUSED_RECEIPTS;
async function focusedReceipt(page, name, measurements) {
  if (!focusedReceiptRoot) return;
  fs.mkdirSync(focusedReceiptRoot, {recursive: true});
  const injectedAssets=await page.evaluate(()=>window.__injectedAssets);assert.deepEqual(injectedAssets,{javascript:sha(fs.readFileSync(process.env.CASEPATH_BROWSER_JS_ASSET || path.join(root,'casepath/assets/autonomous-workspace-v1.js'))),css:sha(fs.readFileSync(process.env.CASEPATH_BROWSER_CSS_ASSET || path.join(root,'casepath/assets/autonomous-workspace-v1.css')))},'the receipt binds the actually injected current assets');
  fs.writeFileSync(path.join(focusedReceiptRoot, `${name}.json`), JSON.stringify({...measurements,viewport:page.viewportSize(),injectedAssets,assets:{
    javascript:sha(fs.readFileSync(process.env.CASEPATH_BROWSER_JS_ASSET || path.join(root,'casepath/assets/autonomous-workspace-v1.js'))),
    css:sha(fs.readFileSync(process.env.CASEPATH_BROWSER_CSS_ASSET || path.join(root,'casepath/assets/autonomous-workspace-v1.css'))),
  }}, null, 2));
  await page.screenshot({path: path.join(focusedReceiptRoot, `${name}.png`), fullPage: true, animations:'disabled'});
}
const visibleRecord = page => page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').textContent().then(JSON.parse);
const currentReadState = page => page.locator('[data-au-view]').getAttribute('data-au-read-state');

async function formingSnapshot(page,state){
  const scene=page.locator('.au-forming-work[data-au-forming="true"]');
  assert.equal(await scene.count(),1,'accepted work stays in one continuous source, process and document composition');
  assert.equal(await scene.getAttribute('data-au-forming-revision'),String(state.revision));assert.equal(await scene.getAttribute('data-au-forming-sha'),state.state_sha256);
  const nodes=state.graph?.nodes||[],edges=state.graph?.edges||[],evaluations=new Map((state.evaluation?.nodes||[]).map(row=>[row.node_id,row]));
  assert.deepEqual(sorted(await scene.locator('[data-au-node]').evaluateAll(rows=>rows.map(row=>row.dataset.auNode))),sorted(nodes.map(row=>row.node_id)),'the forming graph contains every actual node and no anticipated node');
  const renderedEdges=await scene.locator('[data-au-edge]').evaluateAll(rows=>rows.map(row=>({id:row.dataset.auEdge,source:row.dataset.auEdgeSource,target:row.dataset.auEdgeTarget})));
  assert.deepEqual(renderedEdges.sort((a,b)=>a.id.localeCompare(b.id)),edges.map(row=>({id:row.edge_id,source:row.source_node_id,target:row.target_node_id})).sort((a,b)=>a.id.localeCompare(b.id)),'every drawn connection belongs to the accepted graph');
  assert.equal(await scene.locator('[data-au-edge]').evaluateAll(rows=>rows.every(row=>Boolean(row.getAttribute('d'))&&row.getTotalLength()>0)),true,'every actual edge has a drawn native SVG path');
  for(const node of nodes){const control=scene.locator(`[data-au-node="${node.node_id}"]`),evaluation=evaluations.get(node.node_id)||{};assert.equal(await control.getAttribute('data-activation'),evaluation.activation||'unresolved');assert.equal(await control.getAttribute('data-status'),evaluation.execution_state||evaluation.state||'pending');}
  const documents=new Map((state.evaluation?.documents||[]).map(row=>[row.document_type,row])),obligations=state.obligations||[];
  const rows=obligations.concat((state.evaluation?.documents||[]).filter(row=>!obligations.some(item=>item.document_type===row.document_type))).filter(row=>state.graph?.family!=='incoming_packet' && documents.get(row.document_type)?.activation==='true' && !['not_needed','inactive','excluded','held_behind_question','needed_later','optional'].includes(documents.get(row.document_type)?.route_state||row.status) && [row.node_id,row.decision_node_id,...(row.node_ids||[])].filter(Boolean).some(id=>evaluations.get(id)?.activation==='true' && ['ready','completed'].includes(evaluations.get(id)?.execution_state)));
  const expected=rows.map(row=>({id:row.obligation_id||`document:${row.document_type}`,type:row.document_type,status:documents.get(row.document_type)?.route_state||row.status||'pending'})).sort((a,b)=>a.id.localeCompare(b.id));
  const actual=await scene.locator('.au-forming-documents .au-obligation').evaluateAll(rows=>rows.map(row=>({id:row.dataset.auObligation,type:row.dataset.auDocument,status:row.dataset.status})));
  assert.deepEqual(actual.sort((a,b)=>a.id.localeCompare(b.id)),expected,'only a genuinely reached applicable requiring step puts its obligation in the active rail');
  for(const review of await scene.locator('.au-forming-documents .au-document-review').evaluateAll(rows=>rows.map(row=>({type:row.closest('[data-au-document]').dataset.auDocument,state:row.dataset.auReview,marks:[...row.querySelectorAll('[aria-hidden="true"]')].map(mark=>mark.textContent)})))){
    assert.equal(review.state,documents.get(review.type)?.review_state,'review wording follows its independent accepted document review');assert.deepEqual(review.marks,review.state==='sufficient'?['✓']:[],'a checkmark certifies sufficient source review only');
  }
  const alternateFacts=await scene.locator('.au-reading-fact [data-au-fact-select]').evaluateAll(rows=>rows.map(row=>({id:row.dataset.auFactSelect,state:row.dataset.auFactState,text:row.textContent})));
  if(alternateFacts.length)assert.equal(await scene.locator('.au-reading-fact h3').filter({hasText:'Other questions'}).count(),1,'the current established passage does not silently establish its other questions');
  for(const alternate of alternateFacts){const fact=state.facts.find(row=>row.fact_id===alternate.id),status=fact.verdict||fact.status;assert.equal(alternate.state,status);const labels={established:'Established',sufficient:'Sufficient',true:'Applies',false:'Does not apply',insufficient:'Not established',unresolved:'Not established',unknown:'Not established',missing:'Not established'};assert.ok(labels[status],`the genuine alternate fact has a known explicit state: ${status}`);assert.equal(alternate.text,`${labels[status]}: ${fact.label}`,'each alternate question keeps its own actual state visible');}
  const acceptedCitations=(state.facts||[]).flatMap(row=>row.citations||[]).concat((state.actions||[]).flatMap(row=>(row.result||row).citations||[]));
  for(const citation of await scene.locator('[data-au-citation]').evaluateAll(rows=>rows.map(row=>JSON.parse(row.dataset.auCitation)))){
    const descriptor=state.source_descriptors.find(row=>row.artifact_id===citation.artifact_id);assert.ok(descriptor);assert.equal(citation.sha256,descriptor.sha256);assert.ok(acceptedCitations.some(row=>canonical(row)===canonical(citation)),'a rendered source passage is an exact accepted citation');
  }
  assert.equal(await page.locator('[data-au-panel]').getAttribute('data-au-panel'),'step','accepted arrivals cannot switch the main work to another tab');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true,'the actual graph stays within its own scrolling region');
  const geometry=await scene.evaluate(element=>{const rect=node=>node?.getBoundingClientRect().toJSON(),graph=element.querySelector('[data-au-graph-pan]');return {process:rect(element.querySelector('.au-forming-process')),reading:rect(element.querySelector('.au-forming-reading')),documents:rect(element.querySelector('.au-forming-documents')),graph:graph&&{rect:rect(graph),scrollTop:graph.scrollTop,scrollHeight:graph.scrollHeight,clientHeight:graph.clientHeight,scrollWidth:graph.scrollWidth,clientWidth:graph.clientWidth},nodes:[...element.querySelectorAll('[data-au-node]')].map(node=>{const title=node.querySelector('.au-node-title');return {id:node.dataset.auNode,rect:rect(node),rank:rect(node.closest('.au-graph-rank')),title:rect(title),titleFontSize:parseFloat(getComputedStyle(title).fontSize),titleClientWidth:title?.clientWidth,titleScrollWidth:title?.scrollWidth};})};});
  return {nodes:nodes.map(row=>row.node_id),edges:renderedEdges,documents:actual,geometry};
}

for(const [width,height]of [[1440,1000],[1440,900],[1280,800],[390,844]])test(`forming work: live accepted sources, graph and conditional documents form one exact composition at ${width}x${height}`,async t=>{
  const fixture=priorAssessmentFixture(),id=fixture.claim_id,page=await fixturePage(t,{priorAssessment:'reassessed',acceptedPrefix:7,width,height}),consoleProblems=[];page.on('console',message=>{if(['error','warning'].includes(message.type()))consoleProblems.push(message.text());});
  await open(page,id);await title(page,id);const before=await formingSnapshot(page,fixture.prefixes[7].state);assert.equal(before.nodes.length,1);assert.equal(before.edges.length,0);
  await focusedReceipt(page,`forming-live-before-${width}x${height}`,{identity:id,through:7,...before});
  for(const through of [9,11,12,24,25]){
    const reads=(await calls(page,`/claims/${id}/snapshot`)).length;await page.evaluate(seq=>window.__fixture.loadAccepted(seq),through);await page.evaluate(()=>window.__controller.refresh());
    assert.ok((await calls(page,`/claims/${id}/snapshot`)).length>reads,'each accepted live update passes through its independent fresh GET');
    const expected=fixture.prefixes[through];assert.deepEqual(await visibleRecord(page),{state:expected.state,projection:expected.projection});const proof=await formingSnapshot(page,expected.state);assert.equal(proof.nodes.length,11);assert.equal(proof.edges.length,13);
    if(through===9){assert.equal(await page.locator('.au-forming-documents .au-document-review').count(),0,'missing review is expressed once for the rail rather than repeated on every requirement');assert.ok(proof.geometry.nodes.every(node=>node.rect.height>=(width>1000&&height<=850?36:44)&&node.titleFontSize>=14&&node.titleScrollWidth<=node.titleClientWidth+1),'actual nodes retain readable labels and native short-desktop or mobile target sizes');if(width>1000){assert.ok(proof.geometry.reading.x<proof.geometry.process.x&&proof.geometry.process.x<proof.geometry.documents.x,'original evidence precedes the central process and its document rail');assert.ok(proof.geometry.process.width>proof.geometry.reading.width&&proof.geometry.process.width>proof.geometry.documents.width,'the whole accepted process owns the dominant center');assert.ok(proof.geometry.nodes.every(node=>node.rect.y>=proof.geometry.graph.rect.y-1&&node.rect.y+node.rect.height<=height+1),'every actual node is readable within the initial desktop viewport');assert.ok(proof.geometry.graph.scrollHeight<=proof.geometry.graph.clientHeight+1,'the accepted eleven-node graph fits without forced desktop scrolling');}}
    if(through===9)await page.evaluate(()=>{window.__formingObjects={nodes:[...document.querySelectorAll('.au-forming-process [data-au-node]')],edges:[...document.querySelectorAll('.au-forming-process [data-au-edge]')],rows:[...document.querySelectorAll('.au-forming-documents .au-obligation')],choices:[...document.querySelectorAll('.au-forming-documents .au-document-choice')]};});
    if(through===11)assert.equal(await page.evaluate(()=>Object.values(window.__formingObjects).flat().every(element=>element.isConnected)),true,'unchanged accepted graph and requirement identities retain their original native nodes and buttons');
    if(through===11){
      const row=page.locator('.au-forming-documents [data-au-document="spouse_notice_copy"]');assert.equal(await row.getAttribute('data-status'),'established');assert.match(await row.locator('.au-document-review').innerText(),/sufficient/i);
      assert.equal(await page.locator('[data-au-node="lt_family"]').getAttribute('data-status'),'blocked','sufficient source evidence does not establish an earlier process prerequisite');
      const obligation=expected.state.obligations.find(item=>item.document_type==='spouse_notice_copy');await row.locator(`[data-au-select-obligation="${obligation.obligation_id}"]`).click();assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'),obligation.node_id);const selectedRoute=new URLSearchParams(new URL(page.url()).hash.split('?')[1]);for(const [key,value]of Object.entries({node:obligation.node_id,document:obligation.document_type,obligation:obligation.obligation_id,fact:obligation.required_fact_ids[0]}))assert.equal(selectedRoute.get(key),value);
      const source=row.locator('[data-au-source][data-au-citation]').first();await source.focus();await page.keyboard.press('Enter');const citation=JSON.parse(await source.getAttribute('data-au-citation'));await eventually(()=>page.locator('.au-source-dialog[open] mark').count().then(count=>count===1),'the document source marker did not verify its accepted quote');assert.equal(await page.locator('.au-source-dialog[open] mark').textContent(),citation.quote);
      await page.evaluate(()=>{window.__liveSourceFocus=document.activeElement;window.__liveSourceBody=document.querySelector('.au-source-dialog .au-source-body');window.__fixture.loadAccepted(12);});await page.evaluate(()=>window.__controller.refresh());assert.deepEqual((await visibleRecord(page)).state,fixture.prefixes[12].state);assert.equal(await page.evaluate(()=>document.querySelector('.au-source-dialog').open&&document.activeElement===window.__liveSourceFocus&&document.querySelector('.au-source-dialog .au-source-body')===window.__liveSourceBody),true,'an actual accepted live update retains the inspected original source and native focus');assert.equal(await page.locator('.au-source-dialog[open] mark').textContent(),citation.quote);await page.locator('[data-au-close]').click();assert.equal(await source.evaluate(element=>document.activeElement===element),true);
      const current=fixture.prefixes[12].state,after=await formingSnapshot(page,current),wires=await page.locator('[data-au-forming-wire]').evaluateAll(rows=>rows.filter(row=>getComputedStyle(row).display!=='none'&&row.getBoundingClientRect().width>0).map(row=>({kind:row.dataset.auFormingWire,fact:row.dataset.auWireFact,source:row.dataset.auWireSource,node:row.dataset.auWireNode,obligation:row.dataset.auWireObligation,path:row.getAttribute('d')})));
      if(width>1000){assert.deepEqual(sorted(wires.map(row=>row.kind)),['process-document','source-process']);for(const wire of wires){assert.equal(wire.fact,obligation.required_fact_ids[0]);assert.equal(wire.source,citation.artifact_id);assert.equal(wire.node,obligation.node_id);assert.equal(wire.obligation,obligation.obligation_id);assert.ok(wire.path);}
        const connector=await page.locator('[data-au-forming-wire="process-document"]').evaluate(path=>{const scene=path.closest('.au-forming-layout'),node=[...scene.querySelectorAll('[data-au-node]')].find(row=>row.dataset.auNode===path.dataset.auWireNode),row=[...scene.querySelectorAll('.au-forming-documents [data-au-obligation]')].find(row=>row.dataset.auObligation===path.dataset.auWireObligation),matrix=path.getScreenCTM(),screen=point=>new DOMPoint(point.x,point.y).matrixTransform(matrix),rect=element=>element.getBoundingClientRect().toJSON(),length=path.getTotalLength(),coordinates=path.getAttribute('d').match(/-?\d*\.?\d+(?:e[-+]?\d+)?/gi).map(Number),points=[];for(let index=0;index<coordinates.length;index+=2){const point=screen({x:coordinates[index],y:coordinates[index+1]});points.push({x:point.x,y:point.y});}return {start:screen(path.getPointAtLength(0)).toJSON(),end:screen(path.getPointAtLength(length)).toJSON(),points,junction:rect(node.querySelector('[data-au-junction]')),rank:rect(node.closest('.au-graph-rank')),graph:rect(node.closest('[data-au-graph-pan]')),document:rect(row),titles:[...scene.querySelectorAll('.au-forming-process .au-node-title')].map(rect),samples:Array.from({length:501},(_,index)=>screen(path.getPointAtLength(length*index/500)).toJSON())};});
        assert.ok(Math.abs(connector.start.x-(connector.junction.left+connector.junction.width/2))<1&&Math.abs(connector.start.y-connector.junction.bottom)<1,'the requirement connector starts at the actual selected junction');
        assert.ok(Math.abs(connector.end.x-connector.document.left)<1&&Math.abs(connector.end.y-(connector.document.top+connector.document.height/2))<1,'the same connector terminates at the exact requiring document row');
        assert.ok(connector.points[1].y>=connector.rank.bottom+3&&Math.abs(connector.points[1].x-connector.start.x)<1,'the selected junction lane reaches below the entire parallel rank before turning');
        assert.ok(Math.abs(connector.points[2].y-connector.points[1].y)<1&&connector.points[2].x>connector.graph.right&&connector.points[2].x<connector.document.left,'the connector crosses beneath the full rank into the outside gutter');
        assert.equal(connector.samples.some(point=>connector.titles.some(title=>point.x>title.left+.5&&point.x<title.right-.5&&point.y>title.top+.5&&point.y<title.bottom-.5)),false,'the actual connector never crosses a branch label');
        after.connector=connector;
      }else assert.equal(await page.locator('[data-au-forming-wire]:visible').count(),0,'mobile does not paint connections through stacked reading content');
      await focusedReceipt(page,`forming-live-after-${width}x${height}`,{identity:id,through:12,...after,wires,source: citation.artifact_id,sourceHash:citation.sha256});
    }
    if(through===24){const use=expected.state.knowledge_uses[0],body=page.locator(`.au-forming-knowledge [data-au-knowledge-use="${use.knowledge_sha256||use.knowledge_id||use.version_id}"]`);assert.equal(await body.count(),1);assert.ok((await body.innerText()).includes(`Version ${use.version}`));}
    if(through===25){assert.equal(await page.locator('.au-forming-documents [data-au-document="spouse_notice_copy"]').count(),0);assert.equal(await page.locator('[data-au-node="lt_family"]').getAttribute('data-activation'),'false');}
  }
  const selected=await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step');await page.evaluate(()=>window.__fixture.loadAccepted(28));await page.evaluate(()=>window.__controller.refresh());assert.deepEqual((await visibleRecord(page)).state,fixture.prefixes[28].state);assert.equal(await page.locator('[data-au-panel]').getAttribute('data-au-panel'),'step');assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'),selected,'settling accepted work retains its current inspection');assert.deepEqual(consoleProblems,[]);
  if(width===1280){
    // This is the actual native v1 qualification. A fresh independent opening
    // avoids rewinding accepted authority or carrying the source inspection hold
    // above into a scene intended to follow a newly accepted publication.
    const live=await fixturePage(t,{priorAssessment:'reassessed',acceptedPrefix:12,width,height});await open(live,originals[0].claim_id);await title(live,originals[0].claim_id);await open(live,id);await title(live,id);
    const normal=await formingSnapshot(live,fixture.prefixes[12].state);assert.deepEqual(await visibleRecord(live),{state:fixture.prefixes[12].state,projection:fixture.prefixes[12].projection});assert.equal(await live.locator('[data-au-publication-focus]').count(),0,'the global index cannot supply a future qualification to the normal accepted scene');
    assert.ok(normal.geometry.nodes.every(node=>node.rect.bottom<height)&&normal.geometry.graph.scrollHeight<=normal.geometry.graph.clientHeight+1,'all eleven native nodes fit before publication');
    await live.evaluate(()=>{window.__beforePublicationObjects=[...document.querySelectorAll('.au-forming-process [data-au-node], .au-forming-process [data-au-edge], .au-forming-documents .au-obligation')];window.__fixture.loadAccepted(14);});await live.evaluate(()=>window.__controller.refresh());
    const expected=fixture.prefixes[14],publication=expected.state.knowledge_published[0],event=expected.events.at(-1),focus=live.locator(`.au-forming-process [data-au-publication-focus="${event.event_sha256}"] [data-au-knowledge-publication="${publication.knowledge_sha256}"]`);assert.equal(await focus.count(),1,'the actual newly accepted qualification receives central focus without opening History');
    const qualified=await formingSnapshot(live,expected.state),publicationGeometry=await focus.evaluate(element=>({rect:element.getBoundingClientRect().toJSON(),parts:[...element.children].map(child=>({tag:child.tagName,text:child.textContent,rect:child.getBoundingClientRect().toJSON(),font:getComputedStyle(child).fontSize,lineHeight:getComputedStyle(child).lineHeight,margin:getComputedStyle(child).margin}))}));await focusedReceipt(live,'forming-live-publication-1280x800',{identity:id,through:14,normal,...qualified,publicationGeometry,publicationHash:publication.knowledge_sha256,publicationEvent:event.event_sha256});assert.equal(qualified.nodes.length,11);assert.ok(qualified.geometry.nodes.every(node=>node.rect.y>=qualified.geometry.graph.rect.y-1&&node.rect.bottom<height&&node.rect.height>=36&&node.titleFontSize>=14),'the actual qualified publication keeps every node readable in the 800px viewport');assert.ok(qualified.geometry.graph.scrollHeight<=qualified.geometry.graph.clientHeight+1,'publication cannot push the complete graph into forced scrolling');assert.equal(qualified.geometry.graph.scrollTop,0);
    assert.equal(await live.evaluate(()=>window.__beforePublicationObjects.every(element=>element.isConnected)),true,'the compact addition retains the existing actual graph and obligation objects');assert.equal(await live.locator('.au-forming-process .au-process-question').count(),0,'the focused addition replaces the duplicate selected-question heading');
    assert.deepEqual(await focus.locator('[data-au-knowledge-use]').evaluateAll(rows=>rows.map(row=>row.dataset.auKnowledgeUse)),expected.state.knowledge_uses.map(use=>use.knowledge_sha256||use.knowledge_id||use.version_id),'only an actual accepted use is available alongside this publication');
    const procedure=focus.locator(`[data-au-knowledge="${publication.knowledge_id}"][data-au-version="${publication.version}"]`);assert.equal(await procedure.getAttribute('data-au-knowledge-sha'),publication.knowledge_sha256);assert.equal(await procedure.getAttribute('data-au-definition-sha'),publication.qualification.definition_sha256);assert.equal(await procedure.isEnabled(),true);assert.equal(await procedure.evaluate(element=>element.tabIndex),0);
    for(const recipe of publication.evidence_recipes)for(const field of recipe.required_fields)assert.ok((await focus.innerText()).toLowerCase().includes(field.replaceAll('_',' ')),`the accepted added field ${field} remains readable`);
    assert.deepEqual(await visibleRecord(live),{state:expected.state,projection:expected.projection});assert.deepEqual(expected.state.source_descriptors,fixture.prefixes[12].state.source_descriptors);assert.deepEqual(expected.state.acquired_sources,fixture.prefixes[12].state.acquired_sources,'the compact publication does not rewrite admitted source bytes or hashes');
    const route=new URL(live.url()).hash;await procedure.click();await eventually(()=>live.locator(`[data-au-knowledge-identity="${publication.knowledge_id}:${publication.version}"]`).count().then(count=>count===1),'the compact publication did not open its exact accepted procedure');const pinned=live.locator('.au-procedure-versions [aria-pressed="true"]');assert.equal(await pinned.getAttribute('data-au-knowledge-sha'),publication.knowledge_sha256);assert.equal(await pinned.getAttribute('data-au-definition-sha'),publication.qualification.definition_sha256);const pinRoute=new URLSearchParams(new URL(live.url()).hash.split('?')[1]);for(const [key,value]of Object.entries({knowledge:publication.knowledge_id,version:String(publication.version),sha256:publication.knowledge_sha256,definition:publication.qualification.definition_sha256}))assert.equal(pinRoute.get(key),value);await live.goBack();await title(live,id);assert.equal(new URL(live.url()).hash,route);assert.deepEqual((await visibleRecord(live)).state,expected.state);
  }
});

test('forming work: a live terminal qualification appears centrally and new source arrival clears attention without rewriting its record',async t=>{
  const fixture=priorAssessmentFixture(),id=fixture.claim_id,page=await fixturePage(t,{priorAssessment:'reassessed',acceptedPrefix:13,width:1440,height:900});await open(page,originals[0].claim_id);await title(page,originals[0].claim_id);await open(page,id);await title(page,id);assert.deepEqual((await visibleRecord(page)).state,fixture.prefixes[13].state);
  for(const through of [14,15]){await page.evaluate(seq=>window.__fixture.loadAccepted(seq),through);await page.evaluate(()=>window.__controller.refresh());const expected=fixture.prefixes[through],publication=expected.state.knowledge_published[0],event=fixture.prefixes[14].events.at(-1);assert.deepEqual(await visibleRecord(page),{state:expected.state,projection:expected.projection});await formingSnapshot(page,expected.state);const focus=page.locator(`.au-forming-process .au-forming-publication-focus[data-au-publication-focus="${event.event_sha256}"] [data-au-knowledge-publication="${publication.knowledge_sha256}"]`);if(through===14){assert.equal(await focus.count(),1,'the exact accepted qualification is central despite a terminal lifecycle code');assert.equal(expected.state.status,'deferred');}else{assert.equal(expected.events.at(-1).kind,'sources.arrived');assert.equal(await focus.count(),0,'a new source cannot present the prior qualification as a new current addition');assert.deepEqual(expected.state.knowledge_published,fixture.prefixes[14].state.knowledge_published);}assert.equal(await page.locator('[data-au-forming]').getAttribute('data-au-forming-sha'),expected.state.state_sha256);}
  await focusedReceipt(page,'forming-live-qualified-1440x900',{identity:id,through:15,...await formingSnapshot(page,fixture.prefixes[15].state)});
});

test('forming work: verified knowledge appears only at its accepted prefix with actual added fields and exact reused version',async t=>{
  const fixture=priorAssessmentFixture(),id=fixture.claim_id,page=await fixturePage(t,{priorAssessment:'reassessed'});
  for(const through of [10,14,24]){
    await page.evaluate(({id,through})=>window.__controller.openClaim(id,true,{mode:'replay',through,node:'lt_family'}),{id,through});await title(page,id);const state=fixture.prefixes[through].state;await formingSnapshot(page,state);assert.deepEqual(await visibleRecord(page),{state,projection:fixture.prefixes[through].projection});
    if(through===10)assert.equal(await page.locator('.au-forming-knowledge [data-au-knowledge-use], .au-forming-knowledge [data-au-knowledge-publication]').count(),0,'the latest global index cannot publish future knowledge into an earlier prefix');
    if(through===14){await page.locator('.au-context-nav [data-au-detail="knowledge"]').click();const publication=state.knowledge_published[0],body=page.locator(`[data-au-panel="knowledge"] [data-au-knowledge-publication="${publication.knowledge_sha256}"]`);assert.equal(await body.count(),1);const text=(await body.innerText()).toLocaleLowerCase();assert.ok(text.includes('added for reuse'));for(const recipe of publication.evidence_recipes)for(const field of recipe.required_fields)assert.ok(text.includes(field.replaceAll('_',' ')),`actual added field ${field} is visible rather than a generic learning claim`);assert.doesNotMatch(text,/improved accuracy|human approved|facts established by reuse/);assert.deepEqual((await caseDetails(page)).state,state);await page.locator('.au-context-nav [data-au-detail="step"]').click();}
    if(through===24){const use=state.knowledge_uses[0],link=page.locator(`.au-forming-knowledge [data-au-knowledge="${use.knowledge_id}"][data-au-version="${use.version}"]`).first();assert.equal(await link.getAttribute('data-au-knowledge-sha'),use.knowledge_sha256||'');assert.equal(await link.getAttribute('data-au-definition-sha'),use.definition_sha256);const route=new URL(page.url()).hash;await link.focus();await page.keyboard.press('Enter');await eventually(()=>page.locator(`[data-au-knowledge-identity="${use.knowledge_id}:${use.version}"]`).count().then(count=>count===1),'inline reuse did not open its exact qualified version');await page.goBack();await title(page,id);assert.equal(new URL(page.url()).hash,route);assert.deepEqual((await visibleRecord(page)).state,state);await formingSnapshot(page,state);}
  }
  assert.equal((await calls(page,`/claims/${id}/snapshot`)).length,0,'verified historical composition remains pure replay');
});

for (const width of [1428, 1440, 390]) test(`quiet work: one reading focus exposes accepted reasons and one-click Process, Documents and Knowledge at ${width}px`, async t => {
  const height = width === 390 ? 844 : width === 1440 ? 900 : 801;
  const fixture = priorAssessmentFixture(), id = fixture.claim_id;
  const page = await fixturePage(t, {width, height, priorAssessment: 'assessed'});
  const saved = fixture.states.assessed;
  const obligation = saved.obligations.find(item => item.document_type === 'spouse_notice_copy');
  assert.ok(obligation, 'the accepted fixture records the family-home document dependency');
  const fact = saved.facts.find(item => item.fact_id === obligation.required_fact_ids[0]);
  await page.evaluate(preferences => window.__controller.openClaim(preferences.id, true, preferences), {
    id, node: obligation.node_id, document: obligation.document_type,
    obligation: obligation.obligation_id, fact: fact.fact_id,
  });
  await title(page, id);
  await focusedReceipt(page, `quiet-process-${width}`, {identity: id, revision: saved.revision, node: obligation.node_id, obligation: obligation.obligation_id, fact: fact.fact_id});
  const reading = page.locator('[data-au-panel="step"]');
  assert.equal(await reading.locator('details details').count(), 0, 'accepted reasons cannot require a nested disclosure journey');
  assert.equal(await reading.locator('select').count(), 0, 'the reading path cannot depend on a dropdown picker');
  assert.ok((await reading.innerText()).includes(fact.summary || fact.reason), 'the actual accepted fact reason is readable on arrival');
  assert.equal(await reading.locator('[data-au-document]').getAttribute('data-au-document'),obligation.document_type,'the visible consequence belongs to the exact requiring obligation');
  assert.deepEqual((await caseDetails(page)).state.obligations.filter(row=>row.obligation_id===obligation.obligation_id),[obligation],'History retains the full exact requirement reason and binding');await title(page,id);
  assert.equal(await page.locator('.au-context-nav [data-au-detail="step"]').innerText(), 'Process');
  assert.equal(await page.locator('.au-context-nav [data-au-detail="documents"]').count(), 1);
  assert.equal(await page.locator('.au-context-nav [data-au-detail="knowledge"]').count(), 1);
  for (const detail of ['documents', 'knowledge', 'step']) {
    const tab = page.locator(`.au-context-nav [data-au-detail="${detail}"]`);
    await tab.focus();assert.equal(await tab.evaluate(element=>document.activeElement===element),true,'a local view button receives native keyboard focus');await page.keyboard.press('Enter');
    assert.equal(await page.locator(`[data-au-panel="${detail}"]`).isVisible(), true, 'one keyboard activation opens the connected local view');
    assert.equal(await page.locator('[data-au-panel]:visible').count(), 1, 'exactly one local purpose owns the reading surface');
    assert.equal((await visibleRecord(page)).state.claim_id, id);
    assert.deepEqual((await visibleRecord(page)).state, saved, 'local inspection never rewrites accepted state, source hashes or receipts');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    await focusedReceipt(page, `quiet-${detail}-${width}`, {identity: id, revision: saved.revision, detail, route: new URL(page.url()).hash});
  }
});

for (const action of ['start', 'pause', 'resume']) test(`focused flow: uncertain ${action} restores the current replacement control and its exact guarded retry`, async t => {
  const id = demoIds[3], config = action === 'start' ? {originalStartId: id} : {controlRetryId: id, controlRetryAction: action};
  const page = await fixturePage(t, config), selector = `[data-au-${action}]`;
  await open(page, id); await title(page, id);
  await eventually(() => page.locator(selector).isEnabled(), 'the fresh command did not become available');
  const original = await page.evaluate(id => structuredClone(window.__fixture.envelopes[id].state), id);
  const posts = async () => (await calls(page, `/claims/${id}/${action}`)).filter(call => call.method === 'POST');
  await page.evaluate(({id, selector}) => {
    window.__fixture.holdId = id; window.__fixture.holdRemaining = 1;
    window.__clickedCommand = document.querySelector(selector);
  }, {id, selector});
  await page.locator(selector).click();
  await eventually(() => page.evaluate(id => window.__fixture.held.some(held => held.id === id), id), 'the uncertain response did not trigger a held fresh snapshot');
  assert.equal(await currentReadState(page), 'refreshing');
  assert.equal(await page.locator(selector).innerText(), {start: 'Starting…', pause: 'Pausing…', resume: 'Resuming…'}[action]);
  assert.equal(await page.locator('[data-au-start]:enabled, [data-au-pause]:enabled, [data-au-resume]:enabled, [data-au-arrival] input:enabled, [data-au-arrival] button:enabled').count(), 0, 'a held fresh read cannot authorize any mutation');
  await page.clock.runFor(7000);
  assert.equal((await posts()).length, 1, 'uncertainty cannot automatically retry a command');
  const first = (await posts())[0], body = JSON.parse(first.body);
  assert.deepEqual(sorted(Object.keys(body)), ['expected_revision', 'expected_state_sha256', 'idempotency_key']);
  assert.equal(body.expected_revision, original.revision); assert.equal(body.expected_state_sha256, original.state_sha256);
  assert.match(body.idempotency_key, /^browser\.[a-f0-9-]+$/i);
  assert.equal(first.headers['X-CasePath-Agent-Work'], '1'); assert.equal(first.headers['Content-Type'], 'application/json');
  await page.evaluate(() => { window.__fixture.holdId = null; for (const held of window.__fixture.held.splice(0)) held.release(); });
  await eventually(async () => await currentReadState(page) === 'verified' && await page.locator(selector).innerText() === `Retry ${action}` && await page.locator(selector).isEnabled(), 'the matched fresh snapshot must label and enable the current exact retry');
  assert.deepEqual(await page.evaluate(selector => ({replaced: document.querySelector(selector) !== window.__clickedCommand, oldConnected: window.__clickedCommand.isConnected}), selector), {replaced: true, oldConnected: false});
  const accepted = await page.evaluate(id => window.__fixture.envelopes[id].state, id);
  assert.deepEqual(JSON.parse(await page.locator('[data-au-record-content] > pre[data-au-record-kind="claim"]').textContent()).state, accepted, 'the full matched accepted state remains inspectable');
  assert.equal((await posts()).length, 1);
  await page.locator(selector).click();
  const normalSelector = action === 'pause' ? '[data-au-resume]' : '[data-au-pause]', normalLabel = action === 'pause' ? 'Resume work' : 'Pause work';
  await eventually(async () => await currentReadState(page) === 'verified' && await page.locator(normalSelector).count() === 1 && await page.locator(normalSelector).innerText() === normalLabel && await page.locator(normalSelector).isEnabled(), 'a definite response must restore the current normal command label');
  const writes = await posts(); assert.equal(writes.length, 2);
  assert.equal(writes[1].body, first.body, 'the explicit retry must preserve the literal guard and idempotency body');
  assert.deepEqual(writes[1].headers, first.headers);
});

test('quiet work: background Knowledge warming stays read only, revalidates exact pins and cannot revive an invalidated generation',async t=>{
  await t.test('a completed warm read paints its exact pinned version immediately while a fresh GET is held',async t=>{
    const page=await fixturePage(t,{priorAssessment:'reassessed',holdKnowledge:true});
    await eventually(()=>page.evaluate(()=>window.__fixture.held.some(row=>row.kind==='knowledge')),'Cases did not begin its bounded read-only Knowledge warm');
    const cases=await originalPageIds(page);assert.equal(cases.length,20);assert.equal(await page.locator('[data-au-knowledge-identity], [data-au-skeleton="knowledge"]').count(),0);assert.equal(await page.locator('.au-global-status').textContent(),'');
    await page.evaluate(async()=>{window.__fixture.holdKnowledge=false;for(const held of window.__fixture.held.filter(row=>row.kind==='knowledge'))held.release();window.__fixture.held=window.__fixture.held.filter(row=>row.kind!=='knowledge');for(let turn=0;turn<100;turn++)await Promise.resolve();window.__fixture.holdKnowledge=true;});
    assert.deepEqual(await originalPageIds(page),cases,'warm completion cannot render over Cases');assert.equal((await calls(page,'/knowledge')).length,1);
    const version=priorAssessmentFixture().knowledge.versions.find(row=>row.knowledge_sha256&&row.qualification?.definition_sha256),pin={knowledge_id:version.knowledge_id,version:version.version,knowledge_sha256:version.knowledge_sha256,definition_sha256:version.qualification.definition_sha256};
    const immediate=await page.evaluate(pin=>{void window.__controller.showKnowledge(true,pin);const row=document.querySelector('[data-au-knowledge-identity]');return {identity:row?.dataset.auKnowledgeIdentity,hash:row?.dataset.auKnowledgeHash,read:document.querySelector('[data-au-view]')?.dataset.auReadState};},pin);
    assert.equal(immediate.identity,`${version.knowledge_id}:${version.version}`);assert.equal(immediate.read,'refreshing');
    await eventually(()=>page.evaluate(()=>window.__fixture.held.some(row=>row.kind==='knowledge')),'explicit Knowledge navigation did not revalidate its warmed representation');assert.equal((await calls(page,'/knowledge')).length,2);
    assert.deepEqual((await knowledgeDetails(page)).versions.find(row=>row.knowledge_id===version.knowledge_id&&row.version===version.version&&row.knowledge_sha256===version.knowledge_sha256),version);
    await page.evaluate(()=>{window.__fixture.holdKnowledge=false;for(const held of window.__fixture.held.splice(0))held.release();});await eventually(()=>currentReadState(page).then(read=>read==='verified'),'fresh Knowledge did not settle its exact pin');
    const invalid={...pin,knowledge_sha256:'0'.repeat(64)};await page.evaluate(pin=>{void window.__controller.showKnowledge(true,pin);},invalid);
    await eventually(()=>page.locator('.au-global-status').textContent().then(text=>text.includes('exact reused knowledge version')),'the invalid pin was not surfaced');assert.equal(await page.locator('[data-au-knowledge-identity]').count(),0,'warmed content cannot substitute a different primary version for an invalid exact hash');
  });
  await t.test('a failed warm read leaves Cases intact and explicit Knowledge navigation can recover',async t=>{
    const page=await fixturePage(t,{priorAssessment:'reassessed',knowledgeFailures:1});await eventually(async()=>(await calls(page,'/knowledge')).length===1,'the warm GET did not run');
    await page.evaluate(async()=>{for(let turn=0;turn<100;turn++)await Promise.resolve();});assert.equal(await page.locator('[data-au-claim-row]').count(),20);assert.equal(await page.locator('.au-global-status').textContent(),'');assert.equal(await page.locator('[data-au-knowledge-identity], [data-au-skeleton="knowledge"]').count(),0);
    await page.locator('.au-nav [data-au-nav="knowledge"]').click();await eventually(()=>page.locator('[data-au-knowledge-identity]').count().then(count=>count===1),'explicit navigation did not recover from the silent warm failure');assert.equal((await calls(page,'/knowledge')).length,2);
  });
  await t.test('a guarded write invalidates an in-flight warm response before it can repopulate visible cache',async t=>{
    const id=demoIds[0],page=await fixturePage(t,{priorAssessment:'reassessed',originalStartId:id,holdStart:true,holdKnowledge:true});await eventually(()=>page.evaluate(()=>window.__fixture.held.some(row=>row.kind==='knowledge')),'the stale warm response was not held');
    await open(page,id);await title(page,id);await eventually(()=>page.locator('[data-au-start]').isEnabled(),'the isolated original did not obtain fresh Start authority');await page.locator('[data-au-start]').click();await eventually(async()=>(await calls(page,`/claims/${id}/start`)).length===1,'the guarded write did not invalidate the old read generation');
    await page.evaluate(async()=>{window.__fixture.holdKnowledge=false;const stale=window.__fixture.held.filter(row=>row.kind==='knowledge'||row.kind==='start');window.__fixture.held=window.__fixture.held.filter(row=>row.kind!=='knowledge'&&row.kind!=='start');for(const held of stale)held.release();for(let turn=0;turn<100;turn++)await Promise.resolve();window.__fixture.holdKnowledge=true;});
    await eventually(async()=>await page.locator('[data-au-start]').isEnabled()&&(await page.locator('[data-au-start]').textContent()).includes('Retry'),'the uncertain guarded write did not settle to its native literal-retry control');
    await page.locator('.au-nav [data-au-nav="knowledge"]').click();await eventually(()=>page.evaluate(()=>window.__fixture.held.some(row=>row.kind==='knowledge')),'the post-write fresh Knowledge read was not held');assert.equal(await page.locator('[data-au-knowledge-identity]').count(),0,'a late invalidated warm response cannot resurrect its old cache');assert.equal(await page.locator('[data-au-skeleton="knowledge"]').isVisible(),true);
    await page.evaluate(()=>{window.__fixture.holdKnowledge=false;const fresh=window.__fixture.held.filter(row=>row.kind==='knowledge');window.__fixture.held=window.__fixture.held.filter(row=>row.kind!=='knowledge');for(const held of fresh)held.release();});await eventually(()=>page.locator('[data-au-knowledge-identity]').count().then(count=>count===1),'the current generation did not render its own fresh Knowledge result');
  });
});

test('direct replay warmth: cold accepted entry primes real Cases and Knowledge without replacing its prefix or source inspection',async t=>{
  const fixture=referenceFixture(),id=referenceIds[0],prefix=Object.values(fixture.prefixes[id]).find(row=>row.events.at(-1)?.kind==='sources.acquired');
  assert.ok(prefix);assert.deepEqual(prefix.state.knowledge_uses,[]);
  const fragment=`#autonomous/claim/${id}?mode=replay&collection=reference&through=${prefix.through_seq}&detail=sources`;
  const page=await fixturePage(t,{referenceFixture:true,publicReadOnly:true,nativeClock:true,initialFragment:fragment,holdCollections:true,holdKnowledge:true,holdSnapshots:true});
  await title(page,id);const record=await visibleRecord(page);assert.deepEqual(record,{state:prefix.state,projection:prefix.projection});
  await eventually(()=>page.evaluate(()=>window.__fixture.held.some(row=>row.id==='collection')),'direct replay did not quietly begin its first real collection read');
  assert.equal((await calls(page,'/knowledge')).length,0,'collection identity loads before dependent warming');
  const source=page.locator('[data-au-panel="sources"] [data-au-source]').first();await source.focus();await page.keyboard.press('Enter');
  await eventually(()=>page.locator('.au-source-dialog[open] .au-source-body').count().then(count=>count===1),'the exact original did not open during a held background collection');
  const inspected=await page.locator('.au-source-dialog').innerText(),active=await page.evaluate(()=>document.activeElement?.outerHTML),inspectedRoute=new URL(page.url()).hash;
  const routeParams=new URLSearchParams(inspectedRoute.split('?')[1]);assert.equal(inspectedRoute.split('?')[0],fragment.split('?')[0]);assert.equal(routeParams.get('mode'),'replay');assert.equal(routeParams.get('through'),String(prefix.through_seq));assert.equal(routeParams.get('detail'),'sources');
  await page.evaluate(()=>{window.__fixture.holdCollections=false;for(const held of window.__fixture.held.filter(row=>row.id==='collection'))held.release();window.__fixture.held=window.__fixture.held.filter(row=>row.id!=='collection');});
  await eventually(()=>page.evaluate(()=>window.__fixture.activeSnapshotReads===2&&window.__fixture.held.some(row=>row.kind==='knowledge')),'verified collection did not prime bounded snapshot and Knowledge reads');
  await page.evaluate(async()=>{window.__fixture.holdKnowledge=false;for(const held of window.__fixture.held.filter(row=>row.kind==='knowledge'))held.release();window.__fixture.held=window.__fixture.held.filter(row=>row.kind!=='knowledge');for(let turn=0;turn<100;turn++)await Promise.resolve();});
  assert.deepEqual(await visibleRecord(page),record);assert.equal(new URL(page.url()).hash,inspectedRoute);assert.equal(await page.locator('.au-source-dialog').innerText(),inspected);assert.equal(await page.evaluate(()=>document.activeElement?.outerHTML),active);
  assert.equal(await page.locator('[data-au-knowledge-identity],[data-au-skeleton="knowledge"]').count(),0,'global warm Knowledge cannot appear over the current prefix');assert.equal(await page.locator('.au-global-status').innerText(),'');
  await page.locator('[data-au-close]').click();assert.equal(await source.evaluate(element=>document.activeElement===element),true);
  await page.evaluate(()=>{window.__fixture.holdSnapshots=false;for(const held of window.__fixture.held.filter(row=>row.kind==='snapshot'))held.release();window.__fixture.held=window.__fixture.held.filter(row=>row.kind!=='snapshot');});
  await eventually(()=>page.evaluate(ids=>ids.every(id=>window.__fixture.calls.some(row=>row.url.includes(`/claims/${id}/snapshot`))),referenceIds),'the bounded idle queue did not warm the nine real reference heads');
  const snapshotReads=await page.evaluate(()=>window.__fixture.calls.filter(row=>row.url.includes('/snapshot'))),collectionReads=await calls(page,'/claims'),peak=await page.evaluate(()=>window.__fixture.peakSnapshotReads);
  assert.equal(snapshotReads.length,9);assert.equal(peak,2);assert.equal(collectionReads.filter(row=>new URL(row.url,'http://fixture.invalid').pathname===`${base}/claims`).length,2,'the actual 159-case collection is paginated once');
  assert.deepEqual(await visibleRecord(page),record);assert.equal(await page.locator('[data-au-start],[data-au-arrival],[data-au-pause],[data-au-resume]').count(),0);
  await focusedReceipt(page,'direct-replay-warm-prefix-source',{claim_id:id,through_seq:prefix.through_seq,record,snapshotReads,collectionReads,peakSnapshotReads:peak});
  await page.evaluate(({id,through})=>window.__controller.openClaim(id,true,{mode:'replay',collection:'reference',through,detail:'knowledge'}),{id,through:prefix.through_seq});await title(page,id);
  assert.equal((await calls(page,'/knowledge')).length,1,'later case entry does not repeat a successful global warm');assert.deepEqual(await visibleRecord(page),record);assert.equal(await page.locator('[data-au-knowledge-version],[data-au-knowledge-identity]').count(),0,'future global versions cannot leak into a prefix without a recorded use');
  const cases=await page.evaluate(()=>{void window.__controller.showWork();return {rows:document.querySelectorAll('[data-au-claim-row]').length,skeleton:document.querySelectorAll('[data-au-skeleton]').length};});assert.equal(cases.rows,20);assert.equal(cases.skeleton,0);
  await page.evaluate(()=>{window.__fixture.holdKnowledge=true;});const knowledge=await page.evaluate(()=>{void window.__controller.showKnowledge();return {identities:document.querySelectorAll('[data-au-knowledge-identity]').length,read:document.querySelector('[data-au-view]').dataset.auReadState,skeleton:document.querySelectorAll('[data-au-skeleton="knowledge"]').length};});
  assert.ok(knowledge.identities>0);assert.equal(knowledge.read,'refreshing');assert.equal(knowledge.skeleton,0);
  await eventually(()=>page.evaluate(()=>window.__fixture.held.some(row=>row.kind==='knowledge')),'explicit Knowledge did not revalidate its warm cache');assert.equal((await calls(page,'/knowledge')).length,2);assert.deepEqual(await knowledgeDetails(page),fixture.knowledge);
  await focusedReceipt(page,'direct-replay-warm-knowledge',{cases,knowledge,recordedKnowledge:fixture.knowledge});
});

test('direct replay warmth: hidden cycles and navigation cancel quiet collection pagination and cache admission',async t=>{
  for(const interruption of ['hidden','navigation'])await t.test(interruption,async t=>{
    const id=referenceIds[0],fragment=`#autonomous/claim/${id}?mode=replay&through=0`,page=await fixturePage(t,{referenceFixture:true,nativeClock:true,initialFragment:fragment,holdCollections:true});await title(page,id);
    await eventually(()=>page.evaluate(()=>window.__fixture.held.some(row=>row.id==='collection')),'the initial collection warm was not held');
    if(interruption==='hidden')await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'));});else await page.evaluate(()=>window.__controller.showIntake());
    await page.evaluate(async()=>{for(const held of window.__fixture.held.splice(0))held.release();for(let turn=0;turn<100;turn++)await Promise.resolve();});await delay(100);
    assert.equal((await calls(page,'/knowledge')).length,0);assert.equal((await calls(page,'/claims')).filter(row=>new URL(row.url,'http://fixture.invalid').pathname===`${base}/claims`).length,1,'canceled collection cannot start a second page');assert.equal(await page.evaluate(()=>window.__fixture.calls.filter(row=>row.url.includes('/snapshot')).length),0);
    const immediate=await page.evaluate(()=>{void window.__controller.showWork();return document.querySelectorAll('[data-au-claim-row]').length;});assert.equal(immediate,0,'canceled metadata cannot seed the next Cases opening');
    await eventually(()=>page.evaluate(()=>window.__fixture.held.some(row=>row.id==='collection')),'Cases did not make its own fresh collection read');await page.evaluate(()=>{window.__fixture.holdCollections=false;for(const held of window.__fixture.held.splice(0))held.release();});await eventually(()=>page.locator('[data-au-claim-row]').count().then(count=>count===20),'fresh collection did not recover');
  });
});

test('direct replay warmth: canceled Knowledge and snapshot fallback cannot drain or seed a later entry',async t=>{
  const id=referenceIds[0],fragment=`#autonomous/claim/${id}?mode=replay&through=0`,page=await fixturePage(t,{referenceFixture:true,nativeClock:true,initialFragment:fragment,holdKnowledge:true,holdSnapshots:true,heldSnapshotStatus:404});await title(page,id);
  await eventually(()=>page.evaluate(()=>window.__fixture.activeSnapshotReads===2&&window.__fixture.held.some(row=>row.kind==='knowledge')),'the direct warm reads were not held');
  const before=await page.evaluate(()=>window.__fixture.calls.length),record=await visibleRecord(page);
  await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'));});
  await page.evaluate(async()=>{for(const held of window.__fixture.held.splice(0))held.release();for(let turn=0;turn<100;turn++)await Promise.resolve();});await delay(100);assert.equal(await page.evaluate(()=>window.__fixture.calls.length),before,'canceled snapshot queue cannot drain');assert.deepEqual(await visibleRecord(page),record);
  const immediate=await page.evaluate(()=>{void window.__controller.showKnowledge();return {identities:document.querySelectorAll('[data-au-knowledge-identity]').length,skeleton:document.querySelectorAll('[data-au-skeleton="knowledge"]').length};});assert.equal(immediate.identities,0);assert.equal(immediate.skeleton,1,'hide→show late response cannot seed Knowledge');
  await page.evaluate(()=>{window.__fixture.holdKnowledge=false;for(const held of window.__fixture.held.splice(0))held.release();});await eventually(()=>page.locator('[data-au-knowledge-identity]').count().then(count=>count>0),'explicit current Knowledge read did not recover');
  await focusedReceipt(page,'direct-replay-hidden-cancellation',{before,immediate,record,calls:await page.evaluate(()=>window.__fixture.calls)});
});

test('direct replay warmth: metadata failures stay silent and explicit navigation recovers',async t=>{
  for(const failed of ['collection','knowledge'])await t.test(failed,async t=>{
    const id=referenceIds[0],page=await fixturePage(t,{referenceFixture:true,publicReadOnly:true,nativeClock:true,initialFragment:`#autonomous/claim/${id}?mode=replay&through=0`,[`${failed}Failures`]:1});await title(page,id);const record=await visibleRecord(page);
    await eventually(async()=>(await calls(page,failed==='collection'?'/claims':'/knowledge')).length>0,'the failing metadata warm did not execute');await delay(100);assert.deepEqual(await visibleRecord(page),record);assert.equal(await page.locator('.au-global-status').innerText(),'');assert.equal(await page.locator('[data-au-skeleton="knowledge"]').count(),0);
    if(failed==='collection'){await page.evaluate(()=>window.__controller.showWork());assert.equal(await page.locator('[data-au-claim-row]').count(),20);}else{await page.evaluate(()=>window.__controller.showKnowledge());assert.ok(await page.locator('[data-au-knowledge-identity]').count()>0);assert.equal((await calls(page,'/knowledge')).length,2);}
  });
});

test('read cache: visible and native hover warming bounds GET concurrency and shares the exact source-bound foreground read',async t=>{
  const id=originals[0].claim_id,page=await fixturePage(t,{holdSnapshots:true});await page.clock.runFor(100);
  await page.locator(`[data-au-claim="${id}"]`).hover();await page.locator(`[data-au-claim="${originals[1].claim_id}"]`).focus();
  await eventually(()=>page.evaluate(()=>window.__fixture.activeSnapshotReads===2),'known visible/hovered claims did not start their bounded read-only warm');
  assert.equal(await page.locator('[data-au-claim-row]').count(),20);assert.equal(await page.locator('[data-au-revision]').count(),0,'background warming cannot render accepted claim content over Cases');assert.equal(await page.evaluate(()=>window.__fixture.peakSnapshotReads),2);
  assert.equal((await calls(page,`/claims/${id}/snapshot`)).length,1);await page.locator(`[data-au-claim="${id}"]`).click();await eventually(()=>page.locator('[data-au-preview="catalog"]').count().then(count=>count===1),'opening did not retain its matched original preview while the shared read was held');
  assert.equal((await calls(page,`/claims/${id}/snapshot`)).length,1,'foreground opening shares the exact in-flight GET');
  await page.evaluate(id=>{window.__fixture.holdSnapshots=false;const matching=window.__fixture.held.filter(row=>row.id===id);window.__fixture.held=window.__fixture.held.filter(row=>row.id!==id);for(const held of matching)held.release();},id);await title(page,id);
  const record=await visibleRecord(page);assert.deepEqual(record,fixtureData().envelopes[id]);assert.deepEqual(record.state.source_descriptors.map(row=>({artifact_id:row.artifact_id,sha256:row.sha256})),corpusManifest.claims.find(row=>row.claim_id===id).observable_artifacts.map(row=>({artifact_id:row.artifact_id,sha256:row.sha256})));
  const reads=(await page.evaluate(()=>window.__fixture.calls.filter(row=>row.url.includes('/snapshot')))).length;await page.clock.runFor(1000);assert.equal((await page.evaluate(()=>window.__fixture.calls.filter(row=>row.url.includes('/snapshot')))).length,reads,'navigation cancels queued background warm reads');
});

test('read cache: a validated saved head paints read only before held fresh reads and History and original source inspection retain its exact bytes',async t=>{
  const fixture=priorAssessmentFixture(),id=fixture.claim_id,snapshot=fixture.snapshots.assessed,seed=seededReadCache(snapshot,fixture.knowledge),page=await fixturePage(t,{priorAssessment:'assessed',seedReadCache:seed,holdId:id,holdRemaining:1,holdStatus:true});
  await open(page,id);await eventually(()=>page.locator('[data-au-revision]').getAttribute('data-au-revision').then(revision=>revision===String(snapshot.state.revision)).catch(()=>false),'the verified session copy did not paint before the fresh read');await title(page,id);
  assert.equal(await currentReadState(page),'refreshing');assert.deepEqual(await visibleRecord(page),{state:snapshot.state,projection:snapshot.projection});
  await page.locator('.au-context-nav [data-au-detail="sources"]').click();assert.equal(await page.locator('[data-au-arrival] input:enabled, [data-au-arrival] button:enabled, [data-au-pause]:enabled, [data-au-resume]:enabled, [data-au-start]:enabled').count(),0,'a persisted head never grants write authority');
  const source=page.locator('[data-au-panel="sources"] [data-au-source]').first();await source.focus();await page.keyboard.press('Enter');await eventually(()=>page.locator('.au-source-dialog[open] .au-source-body').count().then(count=>count===1),'the read-only original source did not remain inspectable');await page.locator('[data-au-close]').click();assert.equal(await source.evaluate(element=>document.activeElement===element),true);assert.deepEqual((await caseDetails(page)).state,snapshot.state);
  await page.evaluate(()=>{window.__fixture.loadAccepted('reassessed');window.__fixture.holdId=null;window.__fixture.holdStatus=false;});
  await page.evaluate(()=>window.__controller.refresh());await eventually(()=>currentReadState(page).then(state=>state==='verified'),'fresh server data did not replace saved-copy authority');
  assert.deepEqual((await visibleRecord(page)).state,fixture.states.reassessed);assert.deepEqual((await visibleRecord(page)).projection,fixture.snapshots.reassessed.projection);assert.equal((await visibleRecord(page)).state.last_event_sha256,fixture.snapshots.reassessed.events.at(-1).event_sha256);
  await page.evaluate(async()=>{for(const held of window.__fixture.held.splice(0))held.release();for(let turn=0;turn<100;turn++)await Promise.resolve();});assert.deepEqual((await visibleRecord(page)).state,fixture.states.reassessed,'a late older captured read cannot overwrite the newer foreground head');
});

test('read cache: an actual foreground head persists across reload and keeps its exact read-only return context while fresh GETs are held',async t=>{
  const fixture=priorAssessmentFixture(),id=fixture.claim_id,saved=fixture.states.assessed,obligation=saved.obligations.find(row=>row.document_type==='spouse_notice_copy'),fact=obligation.required_fact_ids[0],page=await fixturePage(t,{priorAssessment:'assessed'});
  await page.evaluate(preferences=>window.__controller.openClaim(preferences.id,true,preferences),{id,node:obligation.node_id,document:obligation.document_type,obligation:obligation.obligation_id,fact});await title(page,id);
  await eventually(()=>page.evaluate(({key,id})=>{const value=sessionStorage.getItem(key);return value&&JSON.parse(value).snapshots.some(row=>row.state.claim_id===id);},{key:readCacheKey,id}),'the accepted foreground snapshot was not persisted by the actual product');
  const stored=await page.evaluate(key=>sessionStorage.getItem(key),readCacheKey),envelope=JSON.parse(stored);assert.ok(stored.length*2<=2*1024*1024);assert.ok(envelope.snapshots.length<=3);assert.deepEqual(envelope.snapshots.find(row=>row.state.claim_id===id).state,saved);assert.equal(envelope.snapshots.find(row=>row.state.claim_id===id).cursor,saved.revision);
  await page.reload();await mountFixture(page,{priorAssessment:'assessed',holdId:id,holdStatus:true});await title(page,id);assert.equal(await currentReadState(page),'refreshing');assert.deepEqual((await visibleRecord(page)).state,saved);
  await page.locator('.au-nav [data-au-nav="work"]').click();const process=page.locator('[data-au-return-case="step"]'),documents=page.locator('[data-au-return-case="documents"]');assert.equal(await process.isVisible(),true,'a checked reload copy retains its exact case navigation context');assert.equal(await documents.isVisible(),true);
  await documents.click();await title(page,id);assert.equal(await page.locator('[data-au-panel="documents"]').isVisible(),true);assert.equal(await page.locator(`[data-au-obligation="${obligation.obligation_id}"]`).getAttribute('data-selected'),'true');
  assert.equal(await page.locator('[data-au-arrival] input:enabled, [data-au-arrival] button:enabled, [data-au-pause]:enabled, [data-au-resume]:enabled, [data-au-start]:enabled').count(),0);
  await page.locator('.au-nav [data-au-nav="knowledge"]').click();await page.locator('[data-au-return-case="step"]').click();await title(page,id);const query=new URLSearchParams(new URL(page.url()).hash.split('?')[1]);for(const [key,value]of Object.entries({node:obligation.node_id,document:obligation.document_type,obligation:obligation.obligation_id,fact}))assert.equal(query.get(key),value);
  await page.goBack();await eventually(()=>page.locator('.au-quiet-knowledge').count().then(count=>count===1),'Back lost the prior Knowledge route');assert.equal(await page.locator('[data-au-return-case="step"]').isVisible(),true);
});

test('read cache: a newer manual node and exact requirement survive the held initial deep-link read and Back',async t=>{
  const fixture=priorAssessmentFixture(),id=fixture.claim_id,saved=fixture.states.assessed,spouse=saved.obligations.find(row=>row.document_type==='spouse_notice_copy'),receipt=saved.obligations.find(row=>row.document_type==='proof_of_receipt'&&row.node_id==='lt_deadline'),page=await fixturePage(t,{priorAssessment:'assessed',seedReadCache:seededReadCache(fixture.snapshots.assessed),holdId:id,holdRemaining:1});
  await page.evaluate(preferences=>{void window.__controller.openClaim(preferences.id,true,preferences);},{id,node:spouse.node_id,document:spouse.document_type,obligation:spouse.obligation_id,fact:spouse.required_fact_ids[0]});await title(page,id);assert.equal(await currentReadState(page),'refreshing');
  const initialRoute=new URL(page.url()).hash;await openFullProcess(page);await page.locator('[data-au-node="lt_deadline"]').click();await page.locator('.au-context-nav [data-au-detail="documents"]').click();const priorSelectionRoute=new URL(page.url()).hash;await page.locator(`[data-au-panel="documents"] [data-au-select-obligation="${receipt.obligation_id}"]`).click();const route=new URL(page.url()).hash;
  assert.equal(await page.locator('[data-au-evidence-path] [data-au-obligation]').getAttribute('data-au-obligation'),receipt.obligation_id,'the native selection must display the exact newer requirement before the delayed read');
  await page.evaluate(()=>{window.__fixture.holdId=null;for(const held of window.__fixture.held.splice(0))held.release();});await eventually(()=>currentReadState(page).then(state=>state==='verified'),'the held fresh snapshot did not reconcile');
  await page.locator('.au-context-nav [data-au-detail="documents"]').click();assert.equal(await page.locator(`[data-au-obligation="${receipt.obligation_id}"]`).getAttribute('data-selected'),'true','a newer manual exact requirement must win over the initial requested one');await page.locator('.au-context-nav [data-au-detail="step"]').click();
  const query=new URLSearchParams(new URL(page.url()).hash.split('?')[1]);for(const [key,value]of Object.entries({node:receipt.node_id,document:receipt.document_type,obligation:receipt.obligation_id,fact:receipt.required_fact_ids[0]}))assert.equal(query.get(key),value);
  assert.equal(new URL(page.url()).hash,route);assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'),receipt.node_id);assert.deepEqual((await visibleRecord(page)).state,saved);
  await page.goBack();await eventually(()=>page.locator('[data-au-panel="documents"]').count().then(count=>count===1),'Back did not restore the Documents view before the exact requirement selection');assert.equal(new URL(page.url()).hash,priorSelectionRoute);
  for(let step=0;new URL(page.url()).hash!==initialRoute&&step<8;step++)await page.goBack();assert.equal(new URL(page.url()).hash,initialRoute,'bounded native Back navigation retains the earlier exact inspection route');await eventually(()=>page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step').then(node=>node===spouse.node_id).catch(()=>false),'Back did not retain the older explicitly requested inspection');
  for(let step=0;new URL(page.url()).hash!==route&&step<8;step++)await page.goForward();assert.equal(new URL(page.url()).hash,route,'bounded native Forward navigation restores the newer exact inspection route');await title(page,id);
  await page.locator('.au-nav [data-au-nav="work"]').click();await page.locator('[data-au-return-case="documents"]').click();await title(page,id);assert.equal(await page.locator(`[data-au-obligation="${receipt.obligation_id}"]`).getAttribute('data-selected'),'true');
  await page.locator('.au-nav [data-au-nav="work"]').click();await page.locator('[data-au-return-case="step"]').click();await title(page,id);assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'),receipt.node_id);const returned=new URLSearchParams(new URL(page.url()).hash.split('?')[1]);for(const [key,value]of Object.entries({node:receipt.node_id,document:receipt.document_type,obligation:receipt.obligation_id,fact:receipt.required_fact_ids[0]}))assert.equal(returned.get(key),value);
});

test('read cache: corrupt, expired and mismatched saved representations cannot paint accepted content before fresh verification',async t=>{
  const fixture=priorAssessmentFixture(),id=fixture.claim_id,good=seededReadCache(fixture.snapshots.assessed);
  const variants={checksum:value=>{value.sha256='0'.repeat(64);},expired:value=>{value.saved_at-=16*60000;value.snapshots[0].at-=16*60000;},api:value=>{value.api='http://other.invalid/api/claim-loops/v1/autonomous';},contract:value=>{value.contract='casepath.read-cache/obsolete';},claim:value=>{value.snapshots[0].projection.claim_id=otherId;},hash:value=>{value.snapshots[0].projection.state_sha256='0'.repeat(64);},cursor:value=>{value.snapshots[0].cursor--;},source:value=>{value.snapshots[0].state.acquired_sources[0].sha256='0'.repeat(64);},span:value=>{value.snapshots[0].state.facts.find(row=>row.citations?.length).citations[0].end_char++;}};
  for(const [name,mutate]of Object.entries(variants))await t.test(name,async t=>{
    const value=clone(good);mutate(value);const seed=name==='checksum'?value:resealReadCache(value),page=await fixturePage(t,{priorAssessment:'assessed',seedReadCache:seed,holdId:id,holdRemaining:1});await open(page,id);
    await eventually(()=>page.evaluate(id=>window.__fixture.held.some(row=>row.id===id),id),'the independent fresh snapshot was not requested');await page.clock.runFor(100);await delay(40);
    assert.equal(await page.locator('[data-au-revision], [data-au-state-sha], [data-au-node], [data-au-fact], [data-au-outcome]').count(),0,'invalid local data cannot be promoted into an accepted reading');assert.equal(await page.locator('[data-au-arrival], [data-au-start], [data-au-pause], [data-au-resume]').count(),0);
    await page.evaluate(()=>{window.__fixture.holdId=null;for(const held of window.__fixture.held.splice(0))held.release();});await title(page,id);assert.deepEqual((await visibleRecord(page)).state,fixture.states.assessed);assert.equal(await currentReadState(page),'verified');
  });
});

test('read cache: saved final heads never replace the actual Demo prefix zero and quota failure leaves fresh source reads intact',async t=>{
  await t.test('stored head separation',async t=>{
    const id=demoIds[0],page=await fixturePage(t,{presentationSuite:'replay'});await open(page,id);await title(page,id);assert.equal((await visibleRecord(page)).state.revision,2);
    await eventually(()=>page.evaluate(({key,id})=>{const value=sessionStorage.getItem(key);return value&&JSON.parse(value).snapshots.some(row=>row.state.claim_id===id&&row.state.revision===2);},{key:readCacheKey,id}),'the normal saved head was not persisted');
    await page.reload();await mountFixture(page,{presentationSuite:'replay'});await title(page,id);await page.evaluate(()=>window.__controller.showDemonstration(true,'legacy'));await title(page,id);const record=await visibleRecord(page);assert.equal(record.state.revision,0);assert.equal(record.state.graph,null);assert.deepEqual(record.state.facts,[]);assert.equal(record.state.outcome,null);const reads=await calls(page,`/claims/${id}/replay`);assert.equal(reads.filter(row=>new URL(row.url,'http://fixture.invalid').searchParams.get('through_seq')==='0').length,1);assert.ok(reads.length<=3,'at most two verified future prefixes may be prefetched');assert.match(new URL(page.url()).hash,/through=0/);assert.equal(await page.locator('[data-au-start], [data-au-arrival], [data-au-pause], [data-au-resume]').count(),0);
  });
  await t.test('quota fallback',async t=>{
    const fixture=priorAssessmentFixture(),id=fixture.claim_id,page=await fixturePage(t,{priorAssessment:'assessed',storageQuota:true});await open(page,id);await title(page,id);assert.deepEqual((await visibleRecord(page)).state,fixture.states.assessed);assert.equal(await currentReadState(page),'verified');assert.doesNotMatch(await page.locator('.au-global-status').innerText(),/quota|storage/i);
    await page.reload();await mountFixture(page,{priorAssessment:'assessed',holdId:id,holdRemaining:1,storageQuota:true,allowHeldPreview:true});await eventually(()=>page.evaluate(id=>window.__fixture.held.some(row=>row.id===id),id),'the quota fallback did not continue through an ordinary fresh GET');assert.equal(await page.locator('[data-au-revision]').count(),0);await page.evaluate(()=>{window.__fixture.holdId=null;for(const held of window.__fixture.held.splice(0))held.release();});await title(page,id);assert.deepEqual((await visibleRecord(page)).state,fixture.states.assessed);
  });
});

test('read cache: hidden and abandoned Cases cancel queued warming and late results cannot seed the next opening',async t=>{
  for(const interruption of ['hidden','navigation'])await t.test(interruption,async t=>{
    const page=await fixturePage(t,{holdSnapshots:true});await page.locator(`[data-au-claim="${originals[0].claim_id}"]`).hover();await page.locator(`[data-au-claim="${originals[1].claim_id}"]`).focus();await eventually(()=>page.evaluate(()=>window.__fixture.activeSnapshotReads===2),'the two warm reads were not held');
    const ids=await page.evaluate(()=>window.__fixture.held.filter(row=>row.kind==='snapshot').map(row=>row.id)),before=(await page.evaluate(()=>window.__fixture.calls.filter(row=>row.url.includes('/snapshot')))).length;
    if(interruption==='hidden')await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));});else await page.locator('.au-nav [data-au-nav="knowledge"]').click();
    await page.evaluate(async()=>{for(const held of window.__fixture.held.splice(0))held.release();for(let turn=0;turn<100;turn++)await Promise.resolve();});await page.clock.runFor(100);assert.equal((await page.evaluate(()=>window.__fixture.calls.filter(row=>row.url.includes('/snapshot')))).length,before,'abandoned warm queues cannot drain after their late responses');
    if(interruption==='hidden')await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});});await page.evaluate(id=>{window.__fixture.holdSnapshots=false;window.__fixture.holdId=id;},ids[0]);await open(page,ids[0]);await eventually(()=>page.evaluate(id=>window.__fixture.held.some(row=>row.id===id),ids[0]),'the new opening did not make its own fresh GET');assert.equal(await page.locator('[data-au-revision]').count(),0,'late abandoned warm results must not repopulate the current cache');
  });
});

test('read cache: idle pressure keeps the inspected foreground head and oversize persistence falls back to ordinary fresh reading',async t=>{
  const fixture=priorAssessmentFixture(),id=fixture.claim_id,page=await fixturePage(t,{priorAssessment:'assessed',presentationSuite:'replay'});await open(page,id);await title(page,id);const saved=await visibleRecord(page);
  for(const other of historicalIds.filter(value=>value!==id).slice(0,3)){await open(page,other);await title(page,other);}
  await page.locator('.au-nav [data-au-nav="work"]').click();await page.clock.runFor(500);await page.evaluate(async()=>{for(let turn=0;turn<100;turn++)await Promise.resolve();});
  await page.evaluate(id=>{window.__fixture.holdId=id;},id);await open(page,id);await eventually(()=>page.locator('[data-au-revision]').getAttribute('data-au-revision').then(revision=>revision===String(saved.state.revision)).catch(()=>false),'idle warming evicted the explicitly inspected source-bound head');await title(page,id);assert.equal(await currentReadState(page),'refreshing');assert.deepEqual(await visibleRecord(page),saved);
  const large=await fixturePage(t,{priorAssessment:'assessed'});await large.evaluate(id=>{window.__fixture.envelopes[id].state.public_display_extension={note:'x'.repeat(1100*1024)};},id);await open(large,id);await title(large,id);assert.equal(await currentReadState(large),'verified');assert.equal((await visibleRecord(large)).state.public_display_extension.note.length,1100*1024);await large.evaluate(async()=>{for(let turn=0;turn<100;turn++)await Promise.resolve();});const encoded=await large.evaluate(key=>sessionStorage.getItem(key),readCacheKey);assert.ok(!encoded||encoded.length*2<=2*1024*1024,'oversize state cannot exceed the storage budget');if(encoded)assert.equal(JSON.parse(encoded).snapshots.some(row=>row.state.claim_id===id),false,'an oversize head remains a foreground read rather than an unsafe stored derivative');
});

test('focused flow: cached claim revisits paint the verified record synchronously and fail revalidation read-only', async t => {
  const page = await fixturePage(t);
  await open(page, processedId); await title(page, processedId);
  const verified = await visibleRecord(page),verifiedTitle=await page.locator('[data-au-claim-title]').textContent();
  await open(page, otherId); await title(page, otherId);
  const immediate = await page.evaluate(id => {
    window.__fixture.holdId = id;
    void window.__controller.openClaim(id);
    const host = document.querySelector('[data-au-view]');
    return {title: host.querySelector('[data-au-claim-title]')?.textContent, state: host.dataset.auReadState,
      record: document.querySelector('[data-au-record-content] > pre[data-au-record-kind="claim"]')?.textContent,
      enabledWrites: [...host.querySelectorAll('[data-au-arrival] input, [data-au-arrival] button, [data-au-pause], [data-au-resume], [data-au-start]')].filter(element => !element.disabled).length};
  }, processedId);
  assert.equal(immediate.title, verifiedTitle, 'the cached accepted record must paint in the same navigation turn');
  assert.equal(immediate.state, 'refreshing');
  assert.deepEqual(JSON.parse(immediate.record).state, verified.state);
  assert.equal(immediate.enabledWrites, 0, 'a cached revision cannot authorize a mutation while its read is pending');
  await eventually(() => page.evaluate(() => window.__fixture.held.length > 0), 'the fresh revalidation was not requested');
  await page.evaluate(() => { window.__fixture.holdId = null; for (const held of window.__fixture.held.splice(0)) held.release(); });
  await eventually(() => currentReadState(page).then(state => state === 'verified'), 'the matching accepted snapshot did not release read-only mode');
  await open(page, otherId); await title(page, otherId);
  await page.evaluate(id => { window.__fixture.readFailures = 1; void window.__controller.openClaim(id); }, processedId);
  await eventually(() => currentReadState(page).then(state => state === 'failed'), 'the failed cache revalidation did not retain a read-only record');
  assert.deepEqual((await visibleRecord(page)).state, verified.state);
  assert.equal(await page.locator('[data-au-claim-title]').textContent(), verifiedTitle);
  assert.equal(await page.locator('[data-au-arrival] input:enabled, [data-au-arrival] button:enabled, [data-au-pause]:enabled, [data-au-resume]:enabled, [data-au-start]:enabled').count(), 0);
  assert.match(await page.locator('.au-global-status').innerText(), /paused|unavailable|interrupted|refresh/i);
  await focusedReceipt(page, 'cache-failed-revalidation', {immediate, snapshots: (await calls(page, `/claims/${processedId}/snapshot`)).length});
});

test('focused flow: cold claim and Knowledge reads show honest stable skeletons and overlapping GETs deduplicate', async t => {
  const page = await fixturePage(t, {holdId: processedId, holdKnowledge: true});
  await open(page, processedId);
  await eventually(() => page.evaluate(id => window.__fixture.held.filter(row=>row.id===id).length === 1,processedId), 'the cold claim read was not held');
  assert.equal(await page.locator('[data-au-preview="catalog"]').isVisible(),true);
  assert.equal(await page.locator('[data-au-node], [data-au-fact], [data-au-obligation], [data-au-outcome], [data-au-claim-title]').count(), 0, 'a loading skeleton cannot invent claim facts or a result');
  await page.evaluate(id => { void window.__controller.openClaim(id); document.dispatchEvent(new Event('visibilitychange')); }, processedId);
  await page.evaluate(async () => { for (let turn = 0; turn < 20; turn++) await Promise.resolve(); });
  assert.equal((await calls(page, `/claims/${processedId}/snapshot`)).length, 1, 'the exact same inflight GET must be shared');
  await page.evaluate(() => { window.__fixture.holdId = null; for (const held of window.__fixture.held.splice(0)) held.release(); });
  await title(page, processedId);
  await page.locator('.au-nav [data-au-nav="knowledge"]').click();
  await eventually(() => page.evaluate(() => window.__fixture.held.some(held => held.kind === 'knowledge')), 'the first Knowledge read was not held');
  assert.equal(await page.locator('[data-au-skeleton="knowledge"]').isVisible(), true);
  assert.equal(await page.locator('[data-au-knowledge-identity]').count(), 0, 'the skeleton cannot imply a qualified knowledge entry');
  const heading = await page.locator('h1').textContent();
  await page.keyboard.press('Tab');
  await page.evaluate(() => { window.__fixture.holdKnowledge = false; for (const held of window.__fixture.held.splice(0)) held.release(); });
  await eventually(() => page.locator('.au-knowledge-layout').count().then(count => count === 1), 'Knowledge did not settle from its own response');
  assert.equal(await page.locator('h1').textContent(), heading, 'settlement keeps the same page identity');
  await page.locator('.au-nav [data-au-nav="work"]').click();
  const knowledge = await page.evaluate(() => {
    window.__fixture.holdKnowledge = true;
    document.querySelector('.au-nav [data-au-nav="knowledge"]').click();
    return {heading: document.querySelector('h1')?.textContent, grid: Boolean(document.querySelector('.au-knowledge-layout')), skeleton: Boolean(document.querySelector('[data-au-skeleton="knowledge"]'))};
  });
  assert.equal(knowledge.grid, true, 'warm Knowledge navigation must render without awaiting another response');
  assert.equal(knowledge.skeleton, false);
  assert.equal(knowledge.heading, heading);
  await focusedReceipt(page, 'cold-and-warm-reads', {claimReads: (await calls(page, `/claims/${processedId}/snapshot`)).length, knowledgeReads: (await calls(page, '/knowledge')).length, knowledge});
});

test('focused flow: bounded claim cache evicts the oldest accepted record without borrowing another identity', async t => {
  const page = await fixturePage(t), ids = originals.slice(0, 13).map(row => row.claim_id);
  for (const id of ids) { await open(page, id); await title(page, id); }
  const oldest = await page.evaluate(id => {
    window.__fixture.holdId = id; void window.__controller.openClaim(id);
    return {preview:document.querySelector('[data-au-preview]')?.dataset.auPreview, title:document.querySelector('[data-au-catalog-title]')?.textContent||null,accepted:document.querySelector('[data-au-revision]')?.dataset.auRevision||null};
  }, ids[0]);
  assert.equal(oldest.preview,'catalog');assert.equal(oldest.accepted,null,'an evicted snapshot cannot lend accepted authority to its matched catalog excerpt');assert.equal(oldest.title,originals.find(row=>row.claim_id===ids[0]).subject);
  await page.evaluate(() => { window.__fixture.holdId = null; for (const held of window.__fixture.held.splice(0)) held.release(); });
  await title(page, ids[0]);
  const newest = await page.evaluate(id => {
    window.__fixture.holdId = id; void window.__controller.openClaim(id);
    return {state: document.querySelector('[data-au-view]').dataset.auReadState, title: document.querySelector('[data-au-claim-title]')?.textContent};
  }, ids.at(-1));
  assert.equal(newest.state, 'refreshing');
  assert.equal(newest.title, originals.find(row => row.claim_id === ids.at(-1)).subject);
});

test('focused flow: selected process changes preserve the graph, original arrival FileList and source-origin focus', async t => {
  const page = await fixturePage(t); await open(page, processedId); await title(page, processedId);
  await page.locator('.au-context-nav [data-au-detail="sources"]').click();
  const files = page.locator('[data-au-arrival] input[type="file"]');
  await files.setInputFiles({name: 'isolated-retained-original.txt', mimeType: 'text/plain', buffer: Buffer.from('Fictional QA original retained locally; never submitted.')});
  await page.evaluate(() => {
    window.__retainedArrival = document.querySelector('[data-au-arrival]');
    window.__retainedFiles = window.__retainedArrival.elements.files.files;
  });
  await page.locator('.au-context-nav [data-au-detail="step"]').click();
  await openFullProcess(page);await page.evaluate(()=>{window.__retainedGraph=document.querySelector('[data-au-graph]');window.__retainedNodes=[...document.querySelectorAll('[data-au-node]')];});
  const node = await page.locator('[data-au-node]').last().getAttribute('data-au-node');
  await page.locator(`[data-au-node="${node}"]`).focus(); await page.keyboard.press('Enter');
  assert.equal(await page.evaluate(() => document.querySelector('[data-au-graph]') === window.__retainedGraph && window.__retainedNodes.every(element => element.isConnected)), true, 'selecting a real node must update the inspector without replacing the graph');
  assert.equal(await page.evaluate(() => window.__retainedArrival.elements.files.files === window.__retainedFiles), true, 'selection must preserve the same native files');
  assert.equal(await page.locator(`[data-au-node="${node}"]`).getAttribute('aria-pressed'), 'true');
  await page.locator('.au-context-nav [data-au-detail="sources"]').click();
  const source = page.locator('[data-au-panel="sources"] [data-au-source]').first();
  await source.focus(); await page.keyboard.press('Enter');
  await eventually(() => page.locator('dialog[open] details.au-source-identity').count().then(count => count === 1), 'the exact original did not open by keyboard');
  await page.keyboard.press('Escape');
  assert.equal(await source.evaluate(element => document.activeElement === element), true, 'closing the original viewer must restore its visible source origin');
  assert.equal(await files.evaluate(element => element.files[0].name), 'isolated-retained-original.txt');
});

test('focused flow: a recorded action opens its exact document and fact while manual inspection retains its chosen context', async t => {
  const fixture = priorAssessmentFixture(), event = fixture.snapshots.reassessed.events.find(row => row.kind === 'action.completed' && row.payload.result.document_type);
  const page = await fixturePage(t, {priorAssessment: 'reassessed', acceptedPrefix: event.seq});
  await open(page, fixture.claim_id); await title(page, fixture.claim_id);
  const selected = event.payload.result.node_ids[0], requirement = fixture.prefixes[event.seq].state.obligations.find(row => row.node_id === selected && row.document_type === event.payload.result.document_type);
  assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'), selected);
  const context = async () => ({document: new URLSearchParams(new URL(page.url()).hash.split('?')[1]).get('document'), fact: await page.locator('[data-au-evidence-path] [data-au-fact]').getAttribute('data-au-fact'), obligation: new URLSearchParams(new URL(page.url()).hash.split('?')[1]).get('obligation')});
  assert.equal((await context()).document, requirement.document_type);
  assert.equal((await context()).fact, requirement.required_fact_ids[0]);
  assert.equal(await page.locator(`.au-forming-documents [data-au-obligation="${requirement.obligation_id}"]`).count(),0,'early review cannot promote a future requirement');
  assert.deepEqual((await visibleRecord(page)).state, fixture.prefixes[event.seq].state);
  const source=page.locator('.au-reading-passages [data-au-source][data-au-citation]').first(),citation=JSON.parse(await source.getAttribute('data-au-citation'));await source.focus();await page.keyboard.press('Enter');await eventually(()=>page.locator('.au-source-dialog[open] mark').count().then(count=>count===1),'the recorded future requirement retains its exact source passage');assert.equal(await page.locator('mark').textContent(),citation.quote);await page.locator('[data-au-close]').click();assert.equal(await source.evaluate(element=>document.activeElement===element),true);
  await page.locator('.au-forming-documents [data-au-detail="documents"]').click();
  const recorded=page.locator(`[data-au-panel="documents"] [data-au-obligation="${requirement.obligation_id}"]`);assert.equal(await recorded.count(),1);assert.equal(await recorded.locator('[data-au-review]').getAttribute('data-au-review'),'sufficient');
  const manual = fixture.prefixes[event.seq].state.obligations.find(row => row.node_id === 'lt_form' && row.document_type === 'termination_notice');
  await page.locator(`[data-au-panel="documents"] [data-au-select-obligation="${manual.obligation_id}"]`).click();
  assert.deepEqual(await context(), {document: manual.document_type, fact: manual.required_fact_ids[0], obligation: manual.obligation_id});
  await page.evaluate(() => window.__controller.refresh());
  assert.deepEqual(await context(), {document: manual.document_type, fact: manual.required_fact_ids[0], obligation: manual.obligation_id}, 'a settled refresh may not replace an explicit inspection with the latest action');
  assert.deepEqual((await visibleRecord(page)).state, fixture.prefixes[event.seq].state);
});

for (const width of [1428, 390]) test(`focused flow: expanding the complete process retains its native nodes and chosen inspection at ${width}px`, async t => {
  const page = await fixturePage(t, {width, height: width === 390 ? 844 : 801});
  await open(page, processedId); await title(page, processedId);
  const record = await visibleRecord(page), selected = await page.locator('[data-au-node][aria-pressed="true"]').getAttribute('data-au-node');
  await page.evaluate(() => { window.__expandedGraph = document.querySelector('[data-au-graph]'); window.__expandedNodes = [...document.querySelectorAll('[data-au-node]')]; });
  const viewport = page.locator('[data-au-graph-pan]'), expand = page.locator('[data-au-expand-process]');
  const collapsed = await viewport.evaluate(element => ({height: element.clientHeight, content: element.scrollHeight}));
  assert.equal(await expand.getAttribute('aria-expanded'), 'false');
  await expand.focus(); await page.keyboard.press('Enter');
  assert.equal(await expand.getAttribute('aria-expanded'), 'true');
  assert.equal(await viewport.getAttribute('data-au-graph-expanded'), 'true');
  const expanded = await viewport.evaluate(element => ({height: element.clientHeight, content: element.scrollHeight}));
  assert.ok(expanded.height >= expanded.content - 1, `Expand exposes the complete existing graph instead of clipping its rows: ${JSON.stringify({collapsed, expanded})}`);
  const nodeIdentity = () => page.evaluate(() => window.__expandedGraph === document.querySelector('[data-au-graph]') && window.__expandedNodes.every(node => node.isConnected && document.querySelector(`[data-au-node="${node.dataset.auNode}"]`) === node));
  assert.equal(await nodeIdentity(), true);
  assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'), selected);
  const nextNode=record.state.graph.nodes.find(node=>node.node_id!==selected).node_id;await page.locator(`[data-au-node="${nextNode}"]`).click();
  const changed = await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step');
  assert.equal(await nodeIdentity(), true);
  assert.equal(await viewport.getAttribute('data-au-graph-expanded'), 'true');
  await page.evaluate(() => window.__controller.refresh());
  assert.equal(await viewport.getAttribute('data-au-graph-expanded'), 'true');
  assert.equal(await nodeIdentity(), true, 'a matching accepted refresh preserves native graph elements');
  await open(page, otherId); await title(page, otherId); await open(page, processedId); await title(page, processedId);
  assert.equal(await viewport.getAttribute('data-au-graph-expanded'), 'true', 'local claim navigation remembers the explicit expansion');
  assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'), changed);
  assert.deepEqual((await visibleRecord(page)).state, record.state);
  await expand.click();
  assert.equal(await viewport.getAttribute('data-au-graph-expanded'), 'false');
  await focusedReceipt(page, `expanded-process-${width}`, {collapsed, expanded, selected, changed, nodes: record.state.graph.nodes.map(node => node.node_id)});
});

for(const width of [1428,390])test(`quiet work: substantive collection, current question and one exact Knowledge version are reachable at ${width}px`,async t=>{
  const height=width===390?844:801,page=await fixturePage(t,{width,height,priorAssessment:'reassessed'});
  const bounds=selector=>page.locator(selector).first().evaluate(element=>{const r=element.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right};});
  const collection=await bounds('[data-au-claim-row]');assert.ok(collection.bottom<=height&&collection.top<=height*.65,'actual case content is visible on collection arrival');
  await focusedReceipt(page,`cases-${width}`,{width,height,firstCase:collection});
  await open(page,processedId);await title(page,processedId);
  const graph=await bounds('[data-au-graph-pan]'),question=await bounds('[data-au-inspector-heading]');assert.ok(graph.top<height-160&&question.top<height,'the real graph and selected question fit the initial view');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);await focusedReceipt(page,`claim-${width}`,{width,height,graph,question});
  await page.locator('.au-nav [data-au-nav="knowledge"]').click();await eventually(()=>page.locator('[data-au-knowledge-identity]').count().then(count=>count===1),'global Knowledge did not render one selected immutable version');
  const selected=page.locator('[data-au-knowledge-identity]'),identity=await selected.getAttribute('data-au-knowledge-identity'),version=priorAssessmentFixture().knowledge.versions.find(row=>`${row.knowledge_id}:${row.version}`===identity);
  assert.ok(version);assert.equal(await selected.getAttribute('data-au-version'),String(version.version));assert.ok((await bounds('[data-au-knowledge-identity]')).top<height,'the actual selected procedure is visible on arrival');
  const links=await selected.locator('[data-au-claim]').evaluateAll(rows=>rows.map(row=>row.dataset.auClaim));
  const expectedUses=priorAssessmentFixture().knowledge.uses.filter(use=>use.knowledge_id===version.knowledge_id&&use.version===version.version&&(!use.knowledge_sha256||use.knowledge_sha256===version.knowledge_sha256)&&(!use.definition_sha256||use.definition_sha256===(version.qualification?.definition_sha256||version.definition_sha256)));
  assert.deepEqual(links,[version.source_claim_id,...expectedUses.map(use=>use.claim_id)],'every source and receiving link belongs to the exact selected recorded version');
  const procedureIds=await page.locator('.au-procedure-list [data-au-knowledge]').evaluateAll(rows=>rows.map(row=>row.dataset.auKnowledge));assert.deepEqual(sorted(procedureIds),sorted([...new Set(priorAssessmentFixture().knowledge.versions.map(row=>row.knowledge_id))]));const siblings=await page.locator('.au-procedure-versions [data-au-version]').evaluateAll(rows=>rows.map(row=>`${row.dataset.auKnowledge}:${row.dataset.auVersion}`));assert.deepEqual(sorted(siblings),sorted(priorAssessmentFixture().knowledge.versions.filter(row=>row.knowledge_id===version.knowledge_id).map(row=>`${row.knowledge_id}:${row.version}`)));
  assert.deepEqual((await knowledgeDetails(page)).versions.find(row=>row.knowledge_id===version.knowledge_id&&row.version===version.version&&row.knowledge_sha256===version.knowledge_sha256),version,'History preserves complete qualification and immutable lineage for the exact selected version');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);await focusedReceipt(page,`knowledge-${width}`,{width,height,identity,sourceClaim:version.source_claim_id,receivingClaims:expectedUses.map(use=>use.claim_id)});
  if(expectedUses.length){const receiver=selected.locator(`[data-au-claim="${expectedUses[0].claim_id}"]`).last();await receiver.scrollIntoViewIfNeeded();await receiver.focus();const reachable=await receiver.evaluate(element=>{const r=element.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&document.activeElement===element;});assert.equal(reachable,true,'normal scrolling keeps recorded receiving cases keyboard reachable');await page.keyboard.press('Enter');await title(page,expectedUses[0].claim_id);assert.equal((await visibleRecord(page)).state.claim_id,expectedUses[0].claim_id);}
});

// Reuse the public replay-opening preference to exercise the real scheduler
// against one actual deterministic accepted journal. This does not change the
// canonical nine roster or count the native fixture as a demonstration case.
async function actualJournalPresentation(t, config = {}) {
  const fixture = priorAssessmentFixture(), page = await fixturePage(t, {presentationSuite: 'replay', priorAssessment: 'reassessed', ...config});
  await page.evaluate(()=>window.__controller.showDemonstration(true,'legacy'));
  await playIfPaused(page);
  await title(page, demoIds[0]);
  await page.evaluate(({id, latency, through, node}) => {
    window.__fixture.replayLatency = latency;
    void window.__controller.openClaim(id, true, {mode: 'replay', through, node, demo: true});
  }, {id: fixture.claim_id, latency: config.replayLatency || 0, through: config.startThrough || 1, node: config.startNode});
  if (config.replayLatency) await page.clock.runFor(config.replayLatency);
  await title(page, fixture.claim_id);
  return {page, fixture, id: fixture.claim_id};
}

for(const interruption of ['visibility','context'])test(`forming work: trusted Play after ${interruption} reveals only its accepted mocked publication and retains real inspection`,async t=>{
  const config={presentationSuite:'replay',presentationPublication:true},id=demoIds[0],page=await fixturePage(t,config),fixture=fixtureData(config),publication=fixture.acceptedHistories[id][3].state.knowledge_published[0],event=fixture.authoredEvents[id][2];
  await page.evaluate(()=>window.__controller.showDemonstration(true,'legacy'));await page.locator('[data-au-demo-stop]').click();await page.reload();await mountFixture(page,config);assert.equal(await page.locator('[data-au-demo-play]').count(),1);assert.equal(await page.locator('[data-au-revision]').getAttribute('data-au-revision'),'0');
  if(interruption==='visibility')await page.evaluate(()=>{for(let cycle=0;cycle<2;cycle++){Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'));}});else await caseDetails(page);
  assert.equal(await page.locator('[data-au-publication-focus]').count(),0,'the saved final head cannot publish into prefix zero');await observeAnimations(page);await page.locator('[data-au-demo-play]').click();
  for(const through of [1,2,3]){for(let tick=0;Number(await page.locator('[data-au-revision]').getAttribute('data-au-revision'))<through&&tick<300;tick++)await page.clock.runFor(20);assert.equal(await page.locator('[data-au-revision]').getAttribute('data-au-revision'),String(through));assert.equal(await page.locator('[data-au-state-sha]').getAttribute('data-au-state-sha'),fixture.acceptedHistories[id][through].state.state_sha256);if(through<3)assert.equal(await page.locator('[data-au-publication-focus]').count(),0,'a future qualification is absent before its accepted event');}
  const focus=page.locator(`[data-au-publication-focus="${event.event_sha256}"] [data-au-knowledge-publication="${publication.knowledge_sha256}"]`);assert.equal(await focus.count(),1);assert.match(await focus.innerText(),/Version 3/);assert.ok((await page.evaluate(()=>window.__uiAnimations)).some(row=>row.publication===publication.knowledge_sha256),'the accepted publication performs real native WAAPI motion after trusted Play');
  await page.locator('[data-au-node="inspect_packet"]').click();assert.equal(await page.locator('[data-au-demo-resume]').count(),1);assert.equal(await focus.count(),1,'the actual inspection retains the already displayed qualified publication');const record=await caseDetails(page);assert.deepEqual(record.state,fixture.acceptedHistories[id][3].state);assert.deepEqual(record.projection,{...fixture.acceptedHistories[id][3].projection,parent_revision:3,parent_state_sha256:record.state.state_sha256});await page.clock.runFor(7000);assert.equal(await page.locator('[data-au-revision]').getAttribute('data-au-revision'),'3');assert.equal(await focus.count(),1);await page.locator('.au-nav [data-au-nav="work"]').click();
});

for(const inspection of ['source','document','node','knowledge'])test(`forming work: native ${inspection} inspection preserves its exact replay composition`,async t=>{
  const fixture=priorAssessmentFixture(),id=fixture.claim_id,through=inspection==='knowledge'?24:11,{page}=await actualJournalPresentation(t,{startThrough:through,startNode:'lt_form',holdReplayId:id,holdReplayThrough:through+1});
  await eventually(()=>page.evaluate(()=>window.__fixture.held.some(row=>row.kind==='replay')),'the exact next immutable prefix was not held');const before=new URL(page.url()).hash;let origin;
  if(inspection==='source'){origin=page.locator('.au-forming-documents [data-au-source][data-au-citation]').first();await origin.focus();await page.keyboard.press('Enter');await eventually(()=>page.locator('.au-source-dialog[open] mark').count().then(count=>count===1),'the actual inline document source did not verify');}
  if(inspection==='document'){const row=fixture.prefixes[through].state.obligations.find(item=>item.node_id==='lt_form'&&item.document_type==='termination_notice');await page.locator(`.au-forming-documents [data-au-select-obligation="${row.obligation_id}"]`).click();}
  if(inspection==='node'){await page.locator('[data-au-node="lt_deadline"]').focus();await page.keyboard.press('Enter');}
  if(inspection==='knowledge'){const use=fixture.prefixes[through].state.knowledge_uses[0];await page.locator(`.au-forming-process [data-au-knowledge="${use.knowledge_id}"][data-au-version="${use.version}"]`).focus();await page.keyboard.press('Enter');await eventually(()=>page.locator(`[data-au-knowledge-identity="${use.knowledge_id}:${use.version}"]`).count().then(count=>count===1),'the graph origin did not open its exact qualified version');}
  await page.evaluate(()=>{window.__fixture.holdReplayId=null;for(const row of window.__fixture.held.splice(0))row.release();});const reads=(await calls(page,`/claims/${id}/replay`)).length;await page.clock.runFor(7000);assert.equal((await calls(page,`/claims/${id}/replay`)).length,reads,'inspection cannot advance or read another prefix');
  if(inspection==='source'){await page.keyboard.press('Escape');assert.equal(await origin.evaluate(element=>document.activeElement===element),true,'native Escape preserves the exact inline source origin');}
  if(inspection==='knowledge'){await page.goBack();await title(page,id);assert.equal(new URL(page.url()).hash,before);}
  const route=new URL(page.url()).hash;await formingSnapshot(page,fixture.prefixes[through].state);assert.deepEqual((await visibleRecord(page)).state,fixture.prefixes[through].state);await page.clock.runFor(5000);assert.equal(new URL(page.url()).hash,route);assert.deepEqual((await visibleRecord(page)).state,fixture.prefixes[through].state);
  if(inspection==='knowledge'){assert.equal(await page.locator('[data-au-demo-stop]').count(),0,'returning from global Knowledge cannot restart cancelled playback');await page.locator('.au-nav [data-au-nav="work"]').click();return;}
  await playIfPaused(page);let record=await visibleRecord(page);for(let tick=0;record.state.revision===through&&tick<300;tick++){await page.clock.runFor(20);record=await visibleRecord(page);}assert.deepEqual(record,{state:fixture.prefixes[through+1].state,projection:fixture.prefixes[through+1].projection},'deliberate Resume consumes exactly the next accepted prefix');await page.locator('.au-nav [data-au-nav="work"]').click();
});

for(const reduced of [false,true])test(`forming work: actual graph creation precedes the document group with reduced motion ${reduced}`,async t=>{
  const fixture=priorAssessmentFixture(),id=fixture.claim_id,page=await fixturePage(t,{priorAssessment:'reassessed',acceptedPrefix:8,width:1440,height:1000});await open(page,originals[0].claim_id);await title(page,originals[0].claim_id);await open(page,id);await title(page,id);assert.deepEqual((await visibleRecord(page)).state,fixture.prefixes[8].state);await page.emulateMedia({reducedMotion:reduced?'reduce':'no-preference'});await observeAnimations(page);await page.evaluate(()=>window.__fixture.loadAccepted(9));await page.evaluate(()=>window.__controller.refresh());await formingSnapshot(page,fixture.prefixes[9].state);assert.deepEqual((await visibleRecord(page)).state,fixture.prefixes[9].state);
  const animations=await page.evaluate(()=>window.__uiAnimations),groups=animations.filter(row=>row.formingGroup);if(reduced)assert.deepEqual(groups,[],'reduced motion renders the full accepted graph and checklist without motion');else{assert.deepEqual(groups.map(row=>row.formingGroup),['process','documents']);assert.ok(groups[1].options.delay>=groups[0].options.delay+groups[0].options.duration,'actual graph and document group animation intervals do not overlap');assert.equal(animations.filter(row=>row.node||row.document).length,0,'whole graph creation does not pulse each individual node or requirement');}
});

test('quiet language: History pauses the real replay immediately and exposes exact Playback details before Resume consumes only its next prefix',async t=>{
  const fixture=priorAssessmentFixture(),id=fixture.claim_id,{page}=await actualJournalPresentation(t,{startThrough:11,startNode:'lt_form',holdReplayId:id,holdReplayThrough:12});
  await eventually(()=>page.evaluate(()=>window.__fixture.held.some(row=>row.kind==='replay')),'the actual next accepted replay prefix was not held');
  assert.equal(await page.locator('[data-au-inspect="replay"]').count(),0,'playback provenance is not repeated beneath the dominant reading view');
  const prior=new URLSearchParams(new URL(page.url()).hash.split('?')[1]);await page.locator('.au-work-head [data-au-detail="activity"]').click();assert.equal(await page.locator('[data-au-demo-resume]').count(),1,'opening History pauses playback immediately');
  const details=page.locator('[data-au-panel="activity"] [data-au-inspect="replay"]');assert.equal(await details.innerText(),'Playback details');await details.focus();await page.keyboard.press('Enter');assert.deepEqual(JSON.parse(await page.locator('.au-record-dialog[open] pre').textContent()),fixture.prefixes[11],'History retains the complete original replay envelope and provenance');await closeRecord(page);
  assert.deepEqual((await caseDetails(page)).state,fixture.prefixes[11].state);await page.locator('.au-context-nav [data-au-detail="step"]').click();
  const route=new URL(page.url()).hash,restored=new URLSearchParams(route.split('?')[1]);for(const [key,value]of prior)assert.equal(restored.get(key),value,`History retains the explicit replay ${key} identity`);
  await page.evaluate(()=>{window.__fixture.holdReplayId=null;for(const held of window.__fixture.held.splice(0))held.release();});const reads=(await calls(page,`/claims/${id}/replay`)).length;await page.clock.runFor(7000);
  assert.equal(new URL(page.url()).hash,route);assert.equal((await calls(page,`/claims/${id}/replay`)).length,reads);assert.deepEqual((await visibleRecord(page)).state,fixture.prefixes[11].state);
  await page.locator('[data-au-demo-resume]').click();let record=await visibleRecord(page);for(let tick=0;record.state.revision===11&&tick<300;tick++){await page.clock.runFor(20);record=await visibleRecord(page);}assert.deepEqual(record.state,fixture.prefixes[12].state);assert.deepEqual(record.projection,fixture.prefixes[12].projection);await page.locator('.au-nav [data-au-nav="work"]').click();
});

test('quiet work: Cases and global Knowledge return to the same verified claim and exact local requirement and knowledge version', async t => {
  const fixture=priorAssessmentFixture(),id=fixture.claim_id,page=await fixturePage(t,{priorAssessment:'reassessed'});
  assert.equal(await page.locator('[data-au-return-case]:visible').count(),0,'a first visit cannot invent a current case');
  await page.locator('.au-nav [data-au-nav="knowledge"]').click();
  await eventually(()=>page.locator('.au-quiet-knowledge').count().then(count=>count===1),'global Knowledge did not open');
  assert.equal(await page.locator('[data-au-return-case]:visible').count(),0);
  const saved=fixture.states.reassessed,obligation=saved.obligations.find(row=>row.document_type==='spouse_notice_copy'),fact=obligation.required_fact_ids[0];
  await page.evaluate(preferences=>window.__controller.openClaim(preferences.id,true,preferences),{id,node:obligation.node_id,document:obligation.document_type,obligation:obligation.obligation_id,fact});
  await title(page,id);
  const selectedRoute=new URL(page.url()).hash;
  await page.locator('.au-context-nav [data-au-detail="knowledge"]').click();
  const use=saved.knowledge_uses[0];assert.ok(use,'this accepted native prefix records an exact knowledge use');
  await page.locator(`[data-au-panel="knowledge"] [data-au-knowledge="${use.knowledge_id}"][data-au-version="${use.version}"]`).first().click();
  await eventually(()=>page.locator(`[data-au-knowledge-identity="${use.knowledge_id}:${use.version}"]`).count().then(count=>count===1),'global Knowledge did not select the exact used version');
  const pin=new URLSearchParams(new URL(page.url()).hash.split('?')[1]);
  assert.equal(pin.get('knowledge'),use.knowledge_id);assert.equal(pin.get('version'),String(use.version));
  if(use.definition_sha256)assert.equal(pin.get('definition'),use.definition_sha256);
  const knowledgeReads=(await calls(page,'/knowledge')).length;
  for(const facet of ['process','facts','documents','exceptions','changes']){const tab=page.locator(`[data-au-knowledge-facet="${facet}"]`);await tab.focus();await page.keyboard.press('Enter');assert.equal(await page.locator(`[data-au-knowledge-facet-panel="${facet}"]`).count(),1);assert.equal(await page.locator('[data-au-knowledge-facet-panel]').count(),1,'one exact immutable procedure facet owns the reading surface');assert.equal(await page.locator('[data-au-knowledge-identity]').getAttribute('data-au-knowledge-identity'),`${use.knowledge_id}:${use.version}`);}
  assert.equal((await calls(page,'/knowledge')).length,knowledgeReads,'procedure facet inspection uses its exact verified cached version');
  await page.locator('[data-au-return-case="documents"]').click();await title(page,id);
  assert.equal(await page.locator('[data-au-panel="documents"]').isVisible(),true);
  const chosen=page.locator(`[data-au-panel="documents"] [data-au-obligation="${obligation.obligation_id}"]`);
  assert.equal(await chosen.getAttribute('data-selected'),'true');
  await chosen.locator('[data-au-select]').click();
  const route=new URLSearchParams(new URL(page.url()).hash.split('?')[1]);
  assert.equal(route.get('node'),obligation.node_id);assert.equal(route.get('document'),obligation.document_type);assert.equal(route.get('obligation'),obligation.obligation_id);assert.equal(route.get('fact'),fact);
  assert.deepEqual((await visibleRecord(page)).state,saved);
  await page.locator('.au-nav [data-au-nav="work"]').click();
  await eventually(()=>page.locator('[data-au-claim-row]').count().then(count=>count===20),'Cases did not restore the original collection');
  await page.locator('[data-au-return-case="step"]').click();await title(page,id);
  assert.equal(new URL(page.url()).hash,selectedRoute);
  assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'),obligation.node_id);
  await page.goBack();await eventually(()=>page.locator('[data-au-claim-row]').count().then(count=>count===20),'Back did not restore Cases');
  await page.goForward();await title(page,id);
  assert.deepEqual((await visibleRecord(page)).state,saved);
});

test('quiet work: cached local view content changes before its native paint without a network wait', async t => {
  const fixture=priorAssessmentFixture(),page=await fixturePage(t,{priorAssessment:'assessed',nativeClock:true,width:1428,height:801});
  await open(page,fixture.claim_id);await title(page,fixture.claim_id);
  const times=await page.evaluate(async()=>{
    const samples=[];
    for(let cycle=0;cycle<4;cycle++)for(const detail of ['documents','knowledge','step']){
      const started=performance.now(),control=document.querySelector(`.au-context-nav [data-au-detail="${detail}"]`);
      control.click();
      const selected=document.querySelector(`[data-au-panel="${detail}"]`);
      const content=performance.now()-started;
      if(!selected || !selected.textContent.trim())throw new Error('A local view did not contain its actual accepted content synchronously.');
      await new Promise(resolve=>requestAnimationFrame(resolve));
      samples.push({detail,content,firstFrame:performance.now()-started,claim:document.querySelector('[data-au-revision]').dataset.auRevision});
    }
    return samples;
  });
  const median=values=>sorted(values).sort((a,b)=>a-b)[Math.floor(values.length/2)];
  assert.ok(times.every(sample=>sample.claim===String(fixture.states.assessed.revision)));
  assert.ok(median(times.map(sample=>sample.content))<250,'cached native local content should update without a visible wait');
  assert.ok(times.every(sample=>sample.content<1000),'local controller rendering cannot add the reported one-second delay');
  assert.deepEqual((await visibleRecord(page)).state,fixture.states.assessed);
  await focusedReceipt(page,'quiet-native-content-paint',{samples:times,contentMedianMs:median(times.map(sample=>sample.content)),firstFrameMedianMs:median(times.map(sample=>sample.firstFrame)),scope:'Local deterministic fixture GETs; native Chromium content and first frame only.'});
});

test('quiet work: the single native technical drawer renders hostile public record text as literal bytes', async t => {
  const page=await fixturePage(t),marker='</pre><img src=x onerror="window.__recordInjection=true"><script>window.__recordInjection=true</script>';
  // Authored display boundary only. This passive public extension is not a
  // source, proposed fact, operational result or verified journal prefix.
  await page.evaluate(({id,marker})=>{window.__fixture.envelopes[id].state.public_display_extension={note:marker};},{id:processedId,marker});
  await open(page,processedId);await title(page,processedId);
  await page.locator('.au-work-head [data-au-detail="activity"]').click();await page.locator('[data-au-panel="activity"] [data-au-inspect="claim"]').click();
  const drawer=page.locator('.au-record-dialog[open]');
  assert.equal(await drawer.locator('pre').count(),1,'one contextual record owns the technical surface');
  assert.equal(await drawer.locator('img,script').count(),0);
  assert.equal(JSON.parse(await drawer.locator('pre').textContent()).state.public_display_extension.note,marker);
  assert.equal(await page.evaluate(()=>window.__recordInjection),undefined);
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('[data-au-inspect="claim"]').evaluate(element=>document.activeElement===element),true,'native Escape returns to the exact record origin');
});

test('quiet work: real source-grounded prefixes keep a blocked question honest, retire its document on a false branch and retain qualified reuse', async t => {
  const fixture=priorAssessmentFixture(),id=fixture.claim_id,page=await fixturePage(t,{priorAssessment:'reassessed'});
  for(const through of [11,25]){
    const state=fixture.prefixes[through].state,obligation=state.obligations.find(row=>row.document_type==='spouse_notice_copy');
    const fact=state.facts.find(row=>row.fact_id===(through===11?obligation.required_fact_ids[0]:'condition:family_home'));
    await page.evaluate(preferences=>window.__controller.openClaim(preferences.id,true,preferences),{id,mode:'replay',through,node:'lt_family',document:obligation.document_type,obligation:obligation.obligation_id,fact:fact.fact_id});
    await title(page,id);assert.deepEqual((await visibleRecord(page)).state,state);
    const question=page.locator('[data-au-node="lt_family"]'),requirement=page.locator('[data-au-evidence-path] [data-au-document="spouse_notice_copy"]');
    assert.equal(await question.getAttribute('data-activation'),through===11?'true':'false');
    assert.equal(await question.getAttribute('data-status'),through===11?'blocked':'inactive');
    assert.equal(await requirement.getAttribute('data-route'),through===11?'established':'not_needed');
    assert.ok((await page.locator('[data-au-evidence-path]').innerText()).includes(fact.summary));
    if(through===11)assert.match(await page.locator('.au-step-status').innerText(),/Waiting for prerequisites/,'sufficient spouse evidence does not satisfy an earlier process prerequisite');
    else assert.match(await requirement.innerText(),/not required/,'the accepted false condition visibly retires the request');
    const citation=fact.citations[0],source=page.locator(`[data-au-evidence-path] [data-au-source="${citation.artifact_id}"]`);
    assert.equal(JSON.parse(await source.getAttribute('data-au-citation')).quote,citation.quote);await source.focus();await page.keyboard.press('Enter');
    await eventually(()=>page.locator('.au-source-dialog[open] mark').count().then(count=>count===1),'the selected accepted fact citation did not verify');assert.equal(await page.locator('.au-source-dialog[open] mark').textContent(),citation.quote);
    await page.locator('[data-au-close]').click();assert.equal(await source.evaluate(element=>document.activeElement===element),true);
    await focusedReceipt(page,`quiet-branch-prefix-${through}`,{identity:id,through,source: citation.artifact_id,sourceHash:citation.sha256,fact:fact.fact_id,activation:through===11?'true':'false',documentRoute:through===11?'established':'not_needed'});
  }
  const state=fixture.prefixes[24].state;await page.evaluate(({id})=>window.__controller.openClaim(id,true,{mode:'replay',through:24,detail:'knowledge'}),{id});await title(page,id);
  for(const [kind,expected]of [['publication',state.knowledge_published[0]],['use',state.knowledge_uses[0]]]){
    assert.ok(expected);const record=(await caseDetails(page)).state;assert.deepEqual(kind==='publication'?record.knowledge_published[0]:record.knowledge_uses[0],expected);
  }
  await title(page,id);assert.deepEqual((await visibleRecord(page)).state,state);
  assert.doesNotMatch(await page.locator('[data-au-panel="knowledge"]').innerText(),/facts established by reuse|improved accuracy|human approved/i);
});

test('quiet work: a readable acquired original becomes a cited fact through the same native hash-bound source object',async t=>{
  const fixture=priorAssessmentFixture(),id=fixture.claim_id,before=fixture.prefixes[7].state,after=fixture.prefixes[9].state;
  const citation=after.facts.find(row=>row.fact_id==='condition:family_home').citations[0],source=before.acquired_sources.find(row=>row.artifact_id===citation.artifact_id);
  assert.ok(source&&source.text&&source.extraction!=='unsupported_metadata','the actual prefix supplies readable original text');
  const page=await fixturePage(t,{priorAssessment:'assessed',acceptedPrefix:7});await open(page,id);await title(page,id);
  const original=page.locator(`[data-au-source-identity][data-au-source="${source.artifact_id}"]`);
  assert.equal(await original.count(),1);assert.ok((await original.innerText()).includes(source.text.slice(0,120)),'source acquisition presents actual text before any accepted fact');
  assert.equal(await original.getAttribute('data-au-citation'),null,'an acquisition excerpt cannot invent a fact citation');
  const identity=await original.getAttribute('data-au-source-identity');await original.evaluate(element=>{window.__nativeAcquiredSource=element;});
  await page.evaluate(()=>window.__fixture.loadAccepted(9));await page.evaluate(()=>window.__controller.refresh());
  await eventually(()=>page.locator(`[data-au-source-identity][data-au-source="${source.artifact_id}"][data-au-citation]`).count().then(count=>count===1),'the actual accepted interpretation did not cite its original source');
  const cited=page.locator(`[data-au-source-identity][data-au-source="${source.artifact_id}"][data-au-citation]`);
  assert.equal(await cited.getAttribute('data-au-source-identity'),identity);
  assert.equal(await cited.evaluate(element=>element===window.__nativeAcquiredSource&&element.isConnected),true,'the source becomes a fact dependency without destroying and recreating its native object');
  const acceptedCitation=JSON.parse(await cited.getAttribute('data-au-citation'));assert.equal(acceptedCitation.artifact_id,source.artifact_id);assert.equal(acceptedCitation.sha256,source.sha256);assert.equal(acceptedCitation.text_sha256,source.text_sha256);
  assert.ok(source.text.includes(acceptedCitation.quote));assert.deepEqual((await visibleRecord(page)).state,after);
  await cited.focus();await page.keyboard.press('Enter');await eventually(()=>page.locator('.au-source-dialog[open] mark').count().then(count=>count===1),'the reconciled native source could not verify its cited span');assert.equal(await page.locator('.au-source-dialog[open] mark').textContent(),acceptedCitation.quote);await page.locator('[data-au-close]').click();
  assert.equal(await cited.evaluate(element=>document.activeElement===element),true);
});

for (const latency of [0, 120]) test(`focused flow: actual accepted replay prefixes stay immutable with ${latency}ms GET latency and bounded prefetch`, async t => {
  const {page, fixture, id} = await actualJournalPresentation(t, {replayLatency: latency});
  const rendered = [], times = [];
  for (let through = 1; through <= fixture.snapshots.reassessed.state.revision; through++) {
    let record = await visibleRecord(page);
    for (let tick = 0; record.state.revision < through && tick < 300; tick++) {
      await page.clock.runFor(20); record = await visibleRecord(page);
    }
    assert.equal(record.state.revision, through, 'replay may not skip an accepted journal prefix');
    assert.deepEqual(record.state, fixture.prefixes[through].state, `prefix ${through} keeps every accepted field and hash`);
    assert.deepEqual(record.projection, fixture.prefixes[through].projection);
    if(through<fixture.snapshots.reassessed.state.revision)await formingSnapshot(page,record.state);
    else assert.equal(await page.locator('[data-au-panel]').getAttribute('data-au-panel'),'step','the final recorded outcome retains the main work focus');
    assert.match(await page.locator('.au-work-head').innerText(), /Recorded investigation/);
    assert.equal(await page.locator('[data-au-arrival], [data-au-start], [data-au-pause], [data-au-resume]').count(), 0);
    const prefixCalls = (await calls(page, `/claims/${id}/replay`)).map(call => Number(new URL(call.url, 'http://fixture.invalid').searchParams.get('through_seq')));
    assert.ok(prefixCalls.every(seq => seq <= through + 2), 'prefetch must remain at most two accepted prefixes ahead');
    assert.equal(new Set(prefixCalls).size, prefixCalls.length, 'each prefetched prefix GET is deduplicated');
    rendered.push(through); times.push(await page.evaluate(() => performance.now()));
  }
  const gaps = times.slice(1).map((time, index) => time - times[index]);
  assert.ok(gaps.every(gap=>gap<=5500),`accepted content has a bounded reading interval including the120msGETfixture: ${JSON.stringify(gaps)}`);
  const readingKinds=new Set(['sources.acquired','sources.arrived','interpretation.accepted','knowledge.used','knowledge.published','outcome.recorded','work.completed','work.deferred']);
  for(let index=0;index<gaps.length;index++){
    const event=fixture.prefixes[rendered[index]].events.at(-1),prefix=fixture.prefixes[rendered[index]].state,previous=fixture.prefixes[rendered[index]-1]?.state;
    const substantiveAction=event.kind==='action.completed'&&previous&&canonical({facts:prefix.facts,documents:prefix.evaluation?.documents})!==canonical({facts:previous.facts,documents:previous.evaluation?.documents});
    if(readingKinds.has(event.kind)||substantiveAction)assert.ok(gaps[index]>=3000&&gaps[index]<=5000,`accepted ${event.kind} atprefix${rendered[index]} stays readable3–5seconds: ${gaps[index]}`);
  }
  assert.ok(gaps.some(gap=>gap>=3000),'meaningful accepted content receives an observable reading interval');
  assert.deepEqual(rendered, Array.from({length: 28}, (_, index) => index + 1));
  const replayCalls = await calls(page, `/claims/${id}/replay`);
  assert.equal(replayCalls.length, 28);
  assert.doesNotMatch(await page.locator('.au-global-status').innerText(), /out of sequence|stopped|changed identity/i, 'immediate responses cannot schedule the same accepted prefix twice');
  await page.locator('.au-nav [data-au-nav="work"]').click();
  await focusedReceipt(page, `actual-28-prefix-replay-${latency}`, {identity: id, latency, rendered, virtualTimes: times, gaps, replayCalls});
});

test('focused flow: a corrupted prefetched original identity stops before replacing the accepted replay prefix', async t => {
  const {page, fixture, id} = await actualJournalPresentation(t, {corruptReplayThrough: 3});
  await page.clock.runFor(1400);
  await eventually(async () => (await visibleRecord(page)).state.revision === 2, 'the second accepted prefix did not render');
  await page.clock.runFor(1400);
  await eventually(() => page.locator('.au-global-status').innerText().then(text => /stopped|provenance|identity/i.test(text)), 'corrupt prefetched provenance did not stop replay');
  assert.deepEqual((await visibleRecord(page)).state, fixture.prefixes[2].state);
  assert.match(await page.locator('.au-work-head').innerText(), /Recorded investigation/);
  await page.clock.runFor(5000);
  assert.equal((await visibleRecord(page)).state.revision, 2, 'a rejected prefetched prefix cannot advance later');
  assert.equal((await calls(page, `/claims/${demoIds[1]}/replay`)).length, 0);
});

for (const interruption of ['source', 'hidden', 'navigation']) test(`focused flow: ${interruption} cancels replay with a prefetched accepted response in flight`, async t => {
  const fixture = priorAssessmentFixture(), id = fixture.claim_id;
  const {page} = await actualJournalPresentation(t, {holdReplayId: id, holdReplayThrough: 2});
  await eventually(() => page.evaluate(() => window.__fixture.held.some(held => held.kind === 'replay')), 'the next accepted prefix was not prefetched');
  if (interruption === 'source') {
    await page.locator('.au-context-nav [data-au-detail="sources"]').click();
    await page.locator('[data-au-panel="sources"] [data-au-source]').first().click();
    await eventually(() => page.locator('dialog[open] details.au-source-identity').count().then(count => count === 1), 'original inspection did not open');
  } else if (interruption === 'hidden') await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', {configurable: true, get: () => true}); document.dispatchEvent(new Event('visibilitychange'));
  });
  else await page.locator('.au-nav [data-au-nav="knowledge"]').click();
  await page.evaluate(() => { window.__fixture.holdReplayId = null; for (const held of window.__fixture.held.splice(0)) held.release(); });
  await page.clock.runFor(7000);
  if (interruption === 'navigation') assert.equal(new URL(page.url()).hash, '#autonomous/knowledge');
  else assert.deepEqual((await visibleRecord(page)).state, fixture.prefixes[1].state, 'inspection or hiding must leave the current accepted prefix stable');
  const before = (await calls(page, `/claims/${id}/replay`)).length;
  if (interruption === 'source') await page.locator('[data-au-close]').click();
  if (interruption === 'hidden') await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', {configurable: true, get: () => false}); document.dispatchEvent(new Event('visibilitychange'));
  });
  await page.clock.runFor(5000);
  assert.equal((await calls(page, `/claims/${id}/replay`)).length, before, 'a cancelled replay cannot restart on close or visibility resume');
  assert.equal((await calls(page, `/claims/${demoIds[1]}/replay`)).length, 0);
  if (interruption !== 'navigation') {
    assert.equal(await page.locator('[data-au-demo-resume]').count(), 1);
    await page.locator('[data-au-demo-resume]').click();
    let record = await visibleRecord(page);
    for (let tick = 0; record.state.revision === 1 && tick < 300; tick++) { await page.clock.runFor(20); record = await visibleRecord(page); }
    assert.deepEqual(record.state, fixture.prefixes[2].state, 'explicit Resume consumes exactly the next accepted prefix of the same journal');
    assert.deepEqual(record.projection, fixture.prefixes[2].projection);
    assert.doesNotMatch(await page.locator('.au-global-status').innerText(), /out of sequence|changed identity/i);
  }
});

for (const inspection of ['node', 'fact', 'document']) test(`focused flow: manual ${inspection} inspection pauses the same accepted journal until deliberate Resume`, async t => {
  const fixture = priorAssessmentFixture(), id = fixture.claim_id;
  const {page} = await actualJournalPresentation(t, {startThrough: 11, startNode: 'lt_form', holdReplayId: id, holdReplayThrough: 12});
  await eventually(() => page.evaluate(() => window.__fixture.held.some(held => held.kind === 'replay')), 'the exact next accepted prefix was not held');
  if (inspection === 'node') await page.locator('[data-au-node="lt_deadline"]').click();
  if (inspection === 'fact') await page.locator('[data-au-panel="step"] [data-au-fact-select="fact:termination_notice"]').click();
  if (inspection === 'document') {assert.equal(await page.locator('.au-forming-documents [data-au-select-document="termination_notice"]').count(),0);await page.locator('.au-forming-documents [data-au-detail="documents"]').click();await page.locator('[data-au-panel="documents"] [data-au-select-document="termination_notice"]').click();}
  assert.equal(await page.locator('[data-au-demo-resume]').count(), 1);
  const selected = await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'), route = new URL(page.url()).hash;
  if (inspection !== 'node') {const context=new URLSearchParams(new URL(page.url()).hash.split('?')[1]),requirement=fixture.prefixes[11].state.obligations.find(row=>row.node_id===selected&&row.document_type==='termination_notice');assert.equal(context.get('document'),'termination_notice');assert.equal(context.get('obligation'),requirement.obligation_id);assert.ok(requirement.required_fact_ids.includes(context.get('fact')));assert.equal(await page.locator('.au-forming-documents [data-au-document="termination_notice"]').count(),0,'the contextual future requirement remains outside the active rail');assert.equal(await page.locator('.au-reading-fact').getAttribute('data-au-fact'),context.get('fact'));}
  await page.evaluate(() => { window.__fixture.holdReplayId = null; for (const held of window.__fixture.held.splice(0)) held.release(); });
  const reads = (await calls(page, `/claims/${id}/replay`)).length;
  await page.clock.runFor(7000);
  assert.equal((await calls(page, `/claims/${id}/replay`)).length, reads, 'manual inspection cannot trigger idle replay reads');
  assert.equal(new URL(page.url()).hash, route);
  assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'), selected);
  assert.deepEqual((await visibleRecord(page)).state, fixture.prefixes[11].state);
  await page.locator('[data-au-demo-resume]').click();
  let record = await visibleRecord(page);
  for (let tick = 0; record.state.revision === 11 && tick < 300; tick++) { await page.clock.runFor(20); record = await visibleRecord(page); }
  assert.deepEqual(record.state, fixture.prefixes[12].state, 'Resume verifies and consumes the exact next immutable prefix');
  assert.deepEqual(record.projection, fixture.prefixes[12].projection);
  assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'),'lt_deadline','Resume follows the actual newly reached requiring step after intake completes');const reached=fixture.prefixes[12].state.obligations.find(row=>row.node_id==='lt_deadline'&&row.document_type==='proof_of_receipt'),resumed=new URLSearchParams(new URL(page.url()).hash.split('?')[1]);assert.equal(resumed.get('obligation'),reached.obligation_id);assert.equal(resumed.get('document'),reached.document_type);assert.equal(await page.locator(`.au-forming-documents [data-au-obligation="${reached.obligation_id}"]`).getAttribute('data-status'),'needed_now');
  assert.doesNotMatch(await page.locator('.au-global-status').innerText(), /out of sequence|changed identity/i);
  await page.locator('.au-nav [data-au-nav="work"]').click();
});

async function traceFocusedMotion(page) {
  await page.evaluate(() => {
    window.__focusedMotion = [];
    const animate = Element.prototype.animate;
    Element.prototype.animate = function(frames, options) {
      const animation = animate.call(this, frames, options);
      window.__focusedMotion.push({element: this, animation, frames, options});
      return animation;
    };
  });
}
async function motionTrace(page) {
  return page.evaluate(() => window.__focusedMotion.map(row => ({
    tag: row.element.tagName, frames: row.frames, options: row.options, state: row.animation.playState,
    transform: getComputedStyle(row.element).transform, opacity: getComputedStyle(row.element).opacity,
  })));
}
function assertFocusedMotion(trace, acceptedWave = false) {
  assert.ok(trace.length > 0, 'the actual interaction must create a native animation');
  for (const row of trace) {
    assert.ok(row.options.duration >= 160 && row.options.duration <= 320, `bounded duration: ${JSON.stringify(row.options)}`);
    assert.notEqual(row.options.iterations, Infinity);
    assert.ok((row.options.delay || 0) >= 0 && (row.options.delay || 0) + row.options.duration <= (acceptedWave ? 800 : 400));
    if (!acceptedWave) assert.ok((row.options.delay || 0) <= 80);
    const frames = Array.isArray(row.frames) ? row.frames : [row.frames];
    assert.ok(frames.some(frame=>frame.opacity!==undefined),'content motion carries actual visible opacity frames');if(acceptedWave)assert.ok(frames.some(frame=>frame.transform!==undefined),'accepted causal change carries bounded object motion');
    for (const frame of frames) assert.ok(Object.keys(frame).every(key => ['transform', 'opacity', 'offset', 'easing', 'composite'].includes(key)), 'motion cannot animate layout, scroll or an SVG path');
  }
}

test('quiet work: initial and reconnect navigation settle immediately while rapid routes, keyboard and reduced motion preserve authority',async t=>{
  const page=await fixturePage(t,{presentationSuite:'replay'});await traceFocusedMotion(page);
  await page.evaluate(()=>window.__controller.showDemonstration(true,'legacy'));await title(page,demoIds[0]);
  assert.deepEqual(await motionTrace(page),[],'opening accepted history and whole-page navigation stay settled');
  await page.locator('.au-nav [data-au-nav="knowledge"]').click();await eventually(()=>page.locator('.au-quiet-knowledge').count().then(count=>count===1),'rapid navigation did not retain Knowledge');
  await page.emulateMedia({reducedMotion:'reduce'});await page.locator('.au-nav [data-au-nav="work"]').focus();await page.keyboard.press('Enter');
  await eventually(()=>page.locator('[data-au-claim-row]').count().then(count=>count===20),'native keyboard route did not restore all original cases');
  assert.equal(await page.evaluate(()=>document.getAnimations().filter(animation=>animation.playState==='running').length),0);
  const reads=(await calls(page,`/claims/${demoIds[0]}/replay`)).length;await page.clock.runFor(7000);assert.equal((await calls(page,`/claims/${demoIds[0]}/replay`)).length,reads,'abandoned replay cannot continue behind reduced-motion Cases');
});

test('focused flow: local tabs and filters settle while native source entry motion remains cancellable without changing identity', async t => {
  const page = await fixturePage(t); await traceFocusedMotion(page);
  const search=page.locator('[data-au-claim-search]');await search.evaluate(element=>{window.__nativeSearch=element;});await search.fill('heating');
  assert.deepEqual(await motionTrace(page),[],'filtering does not create an ancestor paint animation');assert.equal(await search.evaluate(element=>element===window.__nativeSearch&&document.activeElement===element),true);
  assert.ok(await page.locator('[data-au-claim-row]').count()>0,'the settled filter exposes actual matching case content');
  await open(page, processedId); await title(page, processedId);
  await page.evaluate(() => { window.__focusedMotion.length = 0; document.querySelector('.au-context-nav [data-au-detail="sources"]').click(); });
  assert.deepEqual(await motionTrace(page),[],'a saved local view settles without a whole-panel animation');
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', {configurable: true, get: () => true}); document.dispatchEvent(new Event('visibilitychange'));
  });
  assert.equal(await page.evaluate(() => document.getAnimations().filter(animation => animation.playState === 'running').length), 0);
  await page.evaluate(() => { Object.defineProperty(document, 'hidden', {configurable: true, get: () => false}); document.dispatchEvent(new Event('visibilitychange')); });
  await page.evaluate(() => { window.__focusedMotion.length = 0; document.querySelector('[data-au-panel="sources"] [data-au-source]').click(); });
  await eventually(() => page.locator('dialog[open] details.au-source-identity').count().then(count => count === 1), 'the original source must verify before the dialog animation');
  assertFocusedMotion(await motionTrace(page));
  const identity = await page.locator('dialog[open] details.au-source-identity').textContent();
  await page.locator('dialog[open] details.au-source-identity > summary').click();
  await page.evaluate(async () => { for (let turn = 0; turn < 20; turn++) await Promise.resolve(); });
  const afterDisclosure = await motionTrace(page); assertFocusedMotion(afterDisclosure);
  assert.equal(await page.locator('dialog[open] details.au-source-identity').textContent(), identity);
  assert.ok(afterDisclosure.filter(row => row.state === 'running').length <= 1);
  await page.keyboard.press('Tab');
  assert.equal(await page.evaluate(() => document.getAnimations().filter(animation => animation.playState === 'running').length), 0, 'keyboard inspection cancels pointer motion');
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('dialog[open]').count(), 0);
  assert.equal(await page.locator('[data-au-panel="sources"]').isVisible(), true);
});

test('focused flow: fresh status waits for cached revision zero revalidation and attempted writes invalidate the mutated claim authority', async t => {
  const id = demoIds[0], page = await fixturePage(t, {originalStartId: id, holdStart: true});
  await open(page, otherId); await title(page, otherId);
  await open(page, id); await title(page, id);
  await page.locator('.au-nav [data-au-nav="work"]').click();
  await page.clock.runFor(10001);
  await page.evaluate(id => { window.__fixture.holdId = id; window.__fixture.holdRemaining = 1; window.__fixture.holdStatus = true; }, id);
  await open(page,id);
  assert.equal(await currentReadState(page), 'refreshing');
  assert.equal(await page.locator('[data-au-start]:enabled').count(), 0);
  await eventually(() => page.evaluate(() => window.__fixture.held.some(held => held.kind === 'status') && window.__fixture.held.some(held => held.id)), 'the fresh capability and cached snapshot reads were not held independently');
  await page.evaluate(() => {
    window.__fixture.holdStatus = false;
    const status = window.__fixture.held.filter(held => held.kind === 'status'); window.__fixture.held = window.__fixture.held.filter(held => held.kind !== 'status');
    for (const held of status) held.release();
  });
  await page.evaluate(async () => { for (let turn = 0; turn < 20; turn++) await Promise.resolve(); });
  assert.equal((await calls(page, `/claims/${id}/start`)).length, 0, 'fresh capabilities cannot authorize a still-cached claim revision');
  await page.evaluate(() => { window.__fixture.holdId = null; for (const held of window.__fixture.held.splice(0)) held.release(); });
  await eventually(()=>page.locator('[data-au-start]').isEnabled(),'the original may be explicitly started only after its fresh snapshot matches');
  await page.locator('[data-au-start]').click();await eventually(async()=>(await calls(page,`/claims/${id}/start`)).length===1,'the explicit fresh Start did not submit exactly once');
  await page.clock.runFor(2000);
  assert.equal((await calls(page, `/claims/${id}/start`)).length, 1, 'the uncertain accepted Start cannot repeat automatically');
  const oldCache = await page.evaluate(id => {
    window.__fixture.holdId = id; void window.__controller.openClaim(id);
    const host = document.querySelector('[data-au-view]');
    return {state: host.dataset.auReadState, title: host.querySelector('[data-au-claim-title]')?.textContent || null,
      enabledWrites: [...host.querySelectorAll('[data-au-arrival] input, [data-au-arrival] button, [data-au-pause], [data-au-resume], [data-au-start]')].filter(element => !element.disabled).length};
  }, otherId);
  assert.equal(oldCache.state, 'refreshing');
  assert.equal(oldCache.enabledWrites, 0, 'an unchanged other claim cache remains read-only until its own snapshot matches');
  const changedCache = await page.evaluate(id => {
    window.__fixture.holdId = id; void window.__controller.openClaim(id);
    return {preview:document.querySelector('[data-au-preview]')?.dataset.auPreview, title:document.querySelector('[data-au-catalog-title]')?.textContent||null,accepted:document.querySelector('[data-au-revision]')?.dataset.auRevision||null};
  }, id);
  assert.equal(changedCache.preview,'catalog');assert.equal(changedCache.accepted,null,'an attempted mutation evicts accepted authority while its catalog excerpt stays readonly');
  await page.evaluate(() => { for (const held of window.__fixture.held.splice(0)) held.release(); });
});

for (const width of [1428, 390]) test(`focused flow: exact cited PDF keeps its filename and native Close visible through drawer scrolling at ${width}px`, async t => {
  const pdf = pdfDrawerFixture(), page = await fixturePage(t, {pdfDrawer: true, width, height: width === 390 ? 844 : 801});
  await open(page, pdf.claim_id); await title(page, pdf.claim_id);
  await page.locator('.au-context-nav [data-au-detail="sources"]').click();
  const trigger = page.locator(`[data-au-panel="sources"] [data-au-source="${pdf.descriptor.artifact_id}"]`);
  const start = Math.max(0, Math.floor(pdf.text.length * .7)), quote = pdf.text.slice(start, start + 70);
  const citation = {artifact_id: pdf.descriptor.artifact_id, sha256: pdf.descriptor.sha256, text_sha256: sha(pdf.text), start_char: [...pdf.text.slice(0, start)].length, end_char: [...pdf.text.slice(0, start + quote.length)].length, quote};
  await trigger.evaluate((element, citation) => { element.dataset.auCitation = JSON.stringify(citation); }, citation);
  await trigger.focus(); await page.keyboard.press('Enter');
  await eventually(() => page.locator('dialog[open] .au-source-body mark').count().then(count => count === 1), 'the original PDF citation did not verify');
  assert.equal(await page.locator('dialog[open] .au-native-document').count(), 1, 'the original hash-checked PDF remains available beside the exact source span');
  assert.equal(await page.locator('dialog[open] .au-source-body mark').textContent(), quote);
  const geometry = () => page.evaluate(() => {
    const box = selector => { const r = document.querySelector(selector).getBoundingClientRect(); return {top: r.top, bottom: r.bottom, left: r.left, right: r.right}; };
    return {height: innerHeight, header: box('dialog[open] .au-dialog-header'), close: box('dialog[open] [data-au-close]'), filename: box('#auSourceTitle'), quote: box('dialog[open] mark'), scroll: document.querySelector('.au-source-dialog').scrollTop};
  });
  const cited = await geometry();
  assert.ok(cited.close.top >= 0 && cited.close.bottom <= cited.height && cited.filename.top >= 0 && cited.filename.bottom <= cited.height, `source identity and Close must stay visible after cited-span navigation: ${JSON.stringify(cited)}`);
  assert.ok(cited.quote.top >= cited.header.bottom - 1 && cited.quote.bottom <= cited.height, 'a highlighted citation cannot be obscured by the persistent header');
  await page.locator('dialog[open]').evaluate(element => { element.scrollTop = element.scrollHeight; });
  const scrolled = await geometry();
  assert.ok(scrolled.close.top >= 0 && scrolled.close.bottom <= scrolled.height && scrolled.filename.top >= 0 && scrolled.filename.bottom <= scrolled.height, 'manual source scrolling retains Close and the exact filename');
  assert.equal(await page.locator('#auSourceTitle').textContent(), pdf.descriptor.file_name);
  await page.locator('[data-au-close]').click();
  assert.equal(await trigger.evaluate(element => document.activeElement === element), true);
  await focusedReceipt(page, `cited-pdf-drawer-${width}`, {citation, cited, scrolled, filename: pdf.descriptor.file_name});
});

test('focused flow: accepted changes settle every record while animating only the selected visible causal path', async t => {
  const fixture = priorAssessmentFixture(), id = fixture.claim_id, event = fixture.snapshots.reassessed.events.find(row => row.kind === 'action.completed');
  const page = await fixturePage(t, {priorAssessment: 'assessed', acceptedPrefix: event.seq - 1, width: 1428, height: 801});
  const node = event.payload.result.node_ids[0], requirement = fixture.prefixes[event.seq].state.obligations.find(item => item.node_id === node && item.document_type === event.payload.result.document_type);
  await page.evaluate(preferences => window.__controller.openClaim(preferences.id, true, preferences), {id, node, document: requirement.document_type, obligation: requirement.obligation_id, fact: requirement.required_fact_ids[0]});
  await title(page, id); await traceFocusedMotion(page);
  await page.evaluate(() => {
    const animate = Element.prototype.animate;
    window.__attentionTargets = [];
    Element.prototype.animate = function(frames, options) {
      const bounds = this.getBoundingClientRect(), host = document.querySelector('[data-au-view]');
      const selected = host.querySelector('[data-au-node][aria-pressed="true"]')?.dataset.auNode;
      const inspector = host.querySelector('[data-au-selected-step]');
      const allowedSources = [...(inspector?.querySelectorAll('[data-au-source]') || [])].map(element => element.dataset.auSource);
      const allowedFacts = [...(inspector?.querySelectorAll('[data-au-fact]') || [])].map(element => element.dataset.auFact);
      const allowedRequirements = [...(inspector?.querySelectorAll('[data-au-document]') || [])].map(element => element.dataset.auDocument);
      const allowedEdges = [...host.querySelectorAll('[data-au-edge][data-selected="true"]')].map(element => element.dataset.auEdge);
      const edgeOverlay = this.classList.contains('au-live-edge'), edgeOverlayMatches = edgeOverlay && [...host.querySelectorAll('[data-au-edge][data-selected="true"]')].some(element => element.getAttribute('d') === this.getAttribute('d'));
      window.__attentionTargets.push({tag: this.tagName, node: this.dataset.auNode, junction: this.querySelector('[data-au-expanded-junction]')?.dataset.auExpandedJunction, edge: this.dataset.auEdge, edgeOverlay, edgeOverlayMatches, source: this.dataset.auSource, fact: this.dataset.auFact, document: this.dataset.auDocument, semantic: this.dataset.auSemanticEvent,
        selected, allowedSources, allowedFacts, allowedRequirements, allowedEdges, closed: Boolean(this.closest('[hidden], details:not([open])')), bounds: {left: bounds.left, right: bounds.right, top: bounds.top, bottom: bounds.bottom}, width: innerWidth, height: innerHeight, options});
      return animate.call(this, frames, options);
    };
  });
  await page.evaluate(seq => window.__fixture.loadAccepted(seq), event.seq);
  await page.evaluate(() => window.__controller.refresh());
  assert.deepEqual((await visibleRecord(page)).state, fixture.prefixes[event.seq].state, 'static updates retain all accepted changes even when their objects do not animate');
  const targets = await page.evaluate(() => window.__attentionTargets);
  assert.ok(targets.some(row=>row.source||row.fact||row.document),'the accepted receipt changes an actual selected evidence object rather than an activity counter');
  for (const row of targets) {
    assert.equal(row.closed, false, 'closed disclosures and hidden contexts cannot animate');
    assert.ok(row.bounds.bottom > 0 && row.bounds.top < row.height && row.bounds.right > 0 && row.bounds.left < row.width, `offviewport records settle without animation: ${JSON.stringify(row)}`);
    const belongs = row.semantic === event.event_sha256 || row.node && row.node === row.selected || row.junction && row.junction === row.selected || row.edge && row.allowedEdges.includes(row.edge) || row.edgeOverlayMatches || row.source && row.allowedSources.includes(row.source) || row.fact && row.allowedFacts.includes(row.fact) || row.document && row.allowedRequirements.includes(row.document);
    assert.ok(belongs, `motion belongs to the selected meaningful source → fact → step → requirement or its accepted cue: ${JSON.stringify(row)}`);
    assert.ok((row.options.delay || 0) + row.options.duration <= 800);
  }
  // Only visible changed groups participate in the source → fact → process →
  // requirement sequence. Native 180ms groups finish before the next starts;
  // missing or clipped groups remain static and do not introduce empty waits.
  const orderedGroups = [targets.filter(row => row.source), targets.filter(row => row.fact), targets.filter(row => row.node || row.junction || row.edge || row.edgeOverlay), targets.filter(row => row.document)].filter(rows => rows.length);
  assert.ok(orderedGroups.length >= 3, 'the actual accepted action must exercise at least three visible causal stages, beyond its compact cue');
  for (let index = 1; index < orderedGroups.length; index++) assert.ok(Math.max(...orderedGroups[index - 1].map(row => (row.options.delay || 0) + row.options.duration)) <= Math.min(...orderedGroups[index].map(row => row.options.delay || 0)), 'each visible actual changed group finishes before source → fact → selected step/junction → derived requirement advances');
  assert.ok(targets.filter(row => row.node || row.junction || row.edge || row.edgeOverlay).length <= 1, 'the selected graph, edge and expanded context cannot become parallel strong motion targets');
  assertFocusedMotion(await motionTrace(page), true);
  await focusedReceipt(page, 'accepted-visible-causal-motion', {identity: id, event_sha256: event.event_sha256, sequence: event.seq, targets});
  await page.emulateMedia({reducedMotion: 'reduce'});
  await eventually(() => page.evaluate(() => document.getAnimations().filter(animation => animation.playState === 'running').length === 0), 'reduced motion cancels the whole accepted wave');
});
