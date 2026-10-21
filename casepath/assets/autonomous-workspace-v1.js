/* Autonomous work is rendered from persisted state and its matching event cursor. */
(function (root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.CasePathAutonomous = api;
})(typeof globalThis === 'object' ? globalThis : this, function (root) {
  'use strict';
  const language = root.CasepathLanguage || (typeof require === 'function' ? require('./autonomous-language-v1.js') : null);
  if (!language) throw new Error('autonomous-language-v1.js must load before autonomous-workspace-v1.js');
  const plain = (value, fallback = 'Recorded item') => language?.plainLabel(value,fallback) || fallback;
  const BASE = '/api/claim-loops/v1/autonomous';
  const PUBLIC_READ_ONLY_MESSAGE = 'View only. Open saved cases, documents, replay and Knowledge.';
  const readOnlyAccess = status => root.CASEPATH_PUBLIC_READ_ONLY === true || status?.read_only === true || status?.writable === false;
  const READ_CACHE_CONTRACT = 'casepath.read-cache/1';
  const READ_CACHE_BYTES = 2 * 1024 * 1024, READ_CACHE_AGE = 15 * 60 * 1000;
  const DOMAINS = Object.freeze([
    {id:'defect_mold_heating',label:'Defects and repairs'},
    {id:'lease_termination_dispute',label:'Lease termination'},
    {id:'rent_increase_dispute',label:'Rent increases'}
  ]);
  // Mac's source-inspected selection, commit 80939f0. Presentation metadata only.
  // These IDs never create packets or contribute facts to an investigation.
  const DEMO_CASES = Object.freeze([
    {claim_id:'clm_e262801f9368bc12',domain:'defect_mold_heating',label:'Recurring leak and a received image'},
    {claim_id:'clm_521c20913f4e0f9b',domain:'defect_mold_heating',label:'Cold home and an unconfirmed repair plan'},
    {claim_id:'clm_ee29ac770b1bf7b9',domain:'defect_mold_heating',label:'Dampness with disputed contractor access'},
    {claim_id:'clm_f69b1747447bc221',domain:'lease_termination_dispute',label:'Different tenant and spouse notice dates'},
    {claim_id:'clm_0c5e7c7723a3c694',domain:'lease_termination_dispute',label:'Competing notices and an alleged correction'},
    {claim_id:'clm_2a9c260c26afaa34',domain:'lease_termination_dispute',label:'Mixed debt demand and unknown payment allocation'},
    {claim_id:'clm_c44ddc0914ba9298',domain:'rent_increase_dispute',label:'Net rent and ancillary-charge reclassification'},
    {claim_id:'clm_7dbd7c7d1c4ddf90',domain:'rent_increase_dispute',label:'A supplied form with an unfilled reason field'},
    {claim_id:'clm_9a179a4481767d43',domain:'rent_increase_dispute',label:'Reference-rate date conflict without supplied forms'}
  ].map(Object.freeze));
  // Source-inspected original IDs. These labels are navigation metadata only.
  const REFERENCE_DEMO_CASES = Object.freeze([
    {claim_id:'clm_314f2d309fea25e6',domain:'defect_mold_heating',label:'Repeated heating failure and reported repair calls'},
    {claim_id:'clm_4a07dbbbd859a3ce',domain:'defect_mold_heating',label:'Heating resets and an uncertain onset date'},
    {claim_id:'clm_95d08975bc575592',domain:'defect_mold_heating',label:'Cold mornings and a requested service assessment'},
    {claim_id:'clm_0f4f13b1e3e1328c',domain:'lease_termination_dispute',label:'An emailed termination and uncertain paper service'},
    {claim_id:'clm_393285577dcb12c4',domain:'lease_termination_dispute',label:'An unsigned notice and the issuer question'},
    {claim_id:'clm_4a53299cfe619303',domain:'lease_termination_dispute',label:'Email notice and the complete service record'},
    {claim_id:'clm_2c55cdd816b1d0e8',domain:'rent_increase_dispute',label:'A blank reason field and a later market email'},
    {claim_id:'clm_543f08f2415b2a33',domain:'rent_increase_dispute',label:'Rent amounts with an uncertain notification date'},
    {claim_id:'clm_7dbd7c7d1c4ddf90',domain:'rent_increase_dispute',label:'An increase form and the later email chronology'}
  ].map(Object.freeze));
  // Generated from the bounded release policy and exact nine source request pins.
  // Structural release context only; never an accepted claim or current-run result.
  const RELEASE_PROCEDURE_OUTLINE = freezeRelease({"artifact_material_sha256":"0dc901886e4399084f9600df8a3311445ca92d3c4ea4ba65d515261e0fd1e01a","base_policy_sha256":"986bf411784ada0524f03d06ef5038d2fb90e27422ee12300a713c644d849343","bounded_policy_sha256":"919645ab51b74ccc4ad01ba9d06148af08b28ccd6c9a3f67b19284feb9646056","catalogs":[{"catalog_sha256":"d23d143adc79bdf96bc2cbcf5573297aeb63a8566b73b089a903875285a6f5a9","documents":[{"document_type":"tenancy_terms_evidence","label":"Relevant tenancy terms","required_at_node_ids":["dh_scope"]},{"document_type":"landlord_knowledge_evidence","label":"Landlord knowledge and continuing repair status","required_at_node_ids":["dh_notice"]},{"document_type":"objective_defect_observation","label":"Dated technical defect observation","required_at_node_ids":["dh_evidence"]}],"family":"defect_mold_heating","nodes":[{"document_types":[],"label":"Capture the reported defect","node_id":"dh_intake"},{"document_types":["tenancy_terms_evidence"],"label":"Establish relevant tenancy terms","node_id":"dh_scope"},{"document_types":["landlord_knowledge_evidence"],"label":"Establish landlord knowledge","node_id":"dh_notice"},{"document_types":[],"label":"Assess supported cause","node_id":"dh_cause"},{"document_types":["objective_defect_observation"],"label":"Assess objective defect evidence","node_id":"dh_evidence"},{"document_types":[],"label":"Record repair and rent reduction eligibility","node_id":"dh_response"}],"rule_pack_sha256":"79821663ef817d4885d450dbae5e361a41311d396989cd452a9a3006d4a96831","transitions":[{"edge_id":"reference_defect_mold_heating_0","source_node_id":"dh_intake","target_node_id":"dh_scope"},{"edge_id":"reference_defect_mold_heating_1","source_node_id":"dh_scope","target_node_id":"dh_notice"},{"edge_id":"reference_defect_mold_heating_2","source_node_id":"dh_notice","target_node_id":"dh_cause"},{"edge_id":"reference_defect_mold_heating_3","source_node_id":"dh_cause","target_node_id":"dh_evidence"},{"edge_id":"reference_defect_mold_heating_4","source_node_id":"dh_evidence","target_node_id":"dh_response"}]},{"catalog_sha256":"7049334aeafc7c0b04f796195c080c46337368bc46ef961d4699b87aeb1f2945","documents":[{"document_type":"tenancy_terms_evidence","label":"Relevant tenancy terms","required_at_node_ids":["lt_form"]},{"document_type":"received_termination_packet","label":"Received termination notice","required_at_node_ids":["lt_form"]},{"document_type":"original_notification_context","label":"Who sent the notice and how it arrived","required_at_node_ids":["lt_form"]}],"family":"lease_termination_dispute","nodes":[{"document_types":[],"label":"Capture the received termination packet","node_id":"lt_intake"},{"document_types":["tenancy_terms_evidence","received_termination_packet","original_notification_context"],"label":"Assess whether the termination notice is valid","node_id":"lt_form"}],"rule_pack_sha256":"0fa0e683f84e09bd3fd7b30c1d9d26621ba4652e1b04cdb71282dc810b88f297","transitions":[{"edge_id":"reference_lease_termination_dispute_0","source_node_id":"lt_intake","target_node_id":"lt_form"}]},{"catalog_sha256":"2145779142660c3449df9d269c3bce7da0e0dcf86d58ec2e4866c40a13314ca1","documents":[{"document_type":"tenancy_terms_evidence","label":"Relevant ordinary tenancy terms","required_at_node_ids":["ri_form"]},{"document_type":"received_rent_increase_packet","label":"Received rent increase notice","required_at_node_ids":["ri_form"]},{"document_type":"original_notification_context","label":"Reasons supplied with the increase notice","required_at_node_ids":["ri_reason"]}],"family":"rent_increase_dispute","nodes":[{"document_types":[],"label":"Capture the original increase packet","node_id":"ri_intake"},{"document_types":["tenancy_terms_evidence","received_rent_increase_packet"],"label":"Assess notification context","node_id":"ri_form"},{"document_types":["original_notification_context"],"label":"Assess whether the increase notice is valid","node_id":"ri_reason"}],"rule_pack_sha256":"3dbf27c3327ee1059ca729e7c632f455baeb76543e6afb84940ea607b9b7c8a1","transitions":[{"edge_id":"reference_rent_increase_dispute_0","source_node_id":"ri_intake","target_node_id":"ri_form"},{"edge_id":"reference_rent_increase_dispute_1","source_node_id":"ri_form","target_node_id":"ri_reason"}]}],"claims":[{"claim_binding_sha256":"b0d51893ca6bd8debb408edf60a10e0dcf6016d2a23c7c059120c2257310cc64","claim_id":"clm_0f4f13b1e3e1328c","corpus_manifest_sha256":"921e7ce79ecb3ee7811b6ee2530b4f6dc5c302da3ade6afbdae0b92fd822790e","family":"lease_termination_dispute","request_source_pin":{"end_char":887,"family":"lease_termination_dispute","file_name":"01-sole-packet-and-tenant-clarification.txt","offset_unit":"unicode_code_point","quote":"assessment of the received landlord notice's approved-form/nullity defect","source_sha256":"5804ca68605622d5e1f004a8a956c2b00c6308943ea375511d833e5abb1ba50e","start_char":814,"text_sha256":"5804ca68605622d5e1f004a8a956c2b00c6308943ea375511d833e5abb1ba50e"},"source_sha256s":["5804ca68605622d5e1f004a8a956c2b00c6308943ea375511d833e5abb1ba50e","e067ac002b3782f410b25c0c8ebe8732247b05a7f1bc5845aab2101d76ad4660"]},{"claim_binding_sha256":"462c8217555033ab5bba43c966848536cce00b326f7d1f2d92dcd9528d4717e7","claim_id":"clm_2c55cdd816b1d0e8","corpus_manifest_sha256":"921e7ce79ecb3ee7811b6ee2530b4f6dc5c302da3ade6afbdae0b92fd822790e","family":"rent_increase_dispute","request_source_pin":{"end_char":1153,"family":"rent_increase_dispute","file_name":"01-ordinary-tenancy-and-original-notification-packet.txt","offset_unit":"unicode_code_point","quote":"assessment of the original notice's missing-reasons/nullity ground","source_sha256":"4e6fecbdbbb64c17b54fc0add7cea5ab447a0cd92daa95e9b62c520c21d6c6a2","start_char":1087,"text_sha256":"4e6fecbdbbb64c17b54fc0add7cea5ab447a0cd92daa95e9b62c520c21d6c6a2"},"source_sha256s":["4da12b6a6c5006bcaeddb0399fc4b64a49a86637a9dd66d18014a9bd93e4cd28","4e6fecbdbbb64c17b54fc0add7cea5ab447a0cd92daa95e9b62c520c21d6c6a2"]},{"claim_binding_sha256":"c121e223860d7509a29fa96c0955dbe06a752699c47d6d3a193fc6fd43ab5a13","claim_id":"clm_314f2d309fea25e6","corpus_manifest_sha256":"921e7ce79ecb3ee7811b6ee2530b4f6dc5c302da3ade6afbdae0b92fd822790e","family":"defect_mold_heating","request_source_pin":{"end_char":555,"family":"defect_mold_heating","file_name":"01-customer-and-tenancy-clarification.txt","offset_unit":"unicode_code_point","quote":"removal of the continuing heating defect and assessment of proportional rent-reduction eligibility","source_sha256":"b43fd882524544b4b860f54eedfe4f1b76fa12b0c7af6502c02b089030d699b9","start_char":457,"text_sha256":"b43fd882524544b4b860f54eedfe4f1b76fa12b0c7af6502c02b089030d699b9"},"source_sha256s":["1b19130a0ec03df636b69a63aedd84c36c00b5601b65bd347532b487ec824569","a5e40553523e2dcee2df0f7f1acf40f8743fd93ff0260cf81ee3004ff78e8e1c","b43fd882524544b4b860f54eedfe4f1b76fa12b0c7af6502c02b089030d699b9"]},{"claim_binding_sha256":"40a5529a0dec3bc53c7527d50fccdbdb982f890586da75fa5a58a9c6cf485e22","claim_id":"clm_393285577dcb12c4","corpus_manifest_sha256":"921e7ce79ecb3ee7811b6ee2530b4f6dc5c302da3ade6afbdae0b92fd822790e","family":"lease_termination_dispute","request_source_pin":{"end_char":899,"family":"lease_termination_dispute","file_name":"01-sole-packet-and-tenant-clarification.txt","offset_unit":"unicode_code_point","quote":"assessment of the received landlord notice's approved-form/nullity defect","source_sha256":"d419f3707d18b2b07b84a8ff88c347d77662bfb90d76898aa50ac15e9ec0143e","start_char":826,"text_sha256":"d419f3707d18b2b07b84a8ff88c347d77662bfb90d76898aa50ac15e9ec0143e"},"source_sha256s":["af3b5810dc9ba67ca288c4542732046b96641a76e84179ba942eee0214cef469","d419f3707d18b2b07b84a8ff88c347d77662bfb90d76898aa50ac15e9ec0143e"]},{"claim_binding_sha256":"4e886feafbe2c7c29e8c19d385c2efc2105f6de32d0b654134b175994a862dc4","claim_id":"clm_4a07dbbbd859a3ce","corpus_manifest_sha256":"921e7ce79ecb3ee7811b6ee2530b4f6dc5c302da3ade6afbdae0b92fd822790e","family":"defect_mold_heating","request_source_pin":{"end_char":555,"family":"defect_mold_heating","file_name":"01-customer-and-tenancy-clarification.txt","offset_unit":"unicode_code_point","quote":"removal of the continuing heating defect and assessment of proportional rent-reduction eligibility","source_sha256":"3589eeb27828e5e11a952f81c67f869024e31e66ddf7b3e907214711930ffca0","start_char":457,"text_sha256":"3589eeb27828e5e11a952f81c67f869024e31e66ddf7b3e907214711930ffca0"},"source_sha256s":["3589eeb27828e5e11a952f81c67f869024e31e66ddf7b3e907214711930ffca0","6124624a08dcc04ec83492b11790c02429065890815d894bd851766c325afb8a","691c9cd457b5f4d11106706eea705cd9d0c1c5186eadaa3e1dcd3660b702c916"]},{"claim_binding_sha256":"b35d1825a4ead3fb0fa3c9b4ca7d1c39080407a003b0344c69acc8bab47468e6","claim_id":"clm_4a53299cfe619303","corpus_manifest_sha256":"921e7ce79ecb3ee7811b6ee2530b4f6dc5c302da3ade6afbdae0b92fd822790e","family":"lease_termination_dispute","request_source_pin":{"end_char":892,"family":"lease_termination_dispute","file_name":"01-sole-packet-and-tenant-clarification.txt","offset_unit":"unicode_code_point","quote":"assessment of the received landlord notice's approved-form/nullity defect","source_sha256":"6dd6527016eec947a221797264e2a043fd62b8a3d6fad1a3882a2c8df0eceb96","start_char":819,"text_sha256":"6dd6527016eec947a221797264e2a043fd62b8a3d6fad1a3882a2c8df0eceb96"},"source_sha256s":["6dd6527016eec947a221797264e2a043fd62b8a3d6fad1a3882a2c8df0eceb96","b11a21b5c48097e59520fa7ed8f425c23f0bf43afe39c45377104264871f31ff"]},{"claim_binding_sha256":"026155cce657cd2ae8209aa4f7f24b107137e351fde68939c8e17b66fe7ee182","claim_id":"clm_543f08f2415b2a33","corpus_manifest_sha256":"921e7ce79ecb3ee7811b6ee2530b4f6dc5c302da3ade6afbdae0b92fd822790e","family":"rent_increase_dispute","request_source_pin":{"end_char":1154,"family":"rent_increase_dispute","file_name":"01-ordinary-tenancy-and-original-notification-packet.txt","offset_unit":"unicode_code_point","quote":"assessment of the original notice's missing-reasons/nullity ground","source_sha256":"9f2cb4a761da63dbed499d207f25fd7778f3b1e4a7bd890492786da7e974735f","start_char":1088,"text_sha256":"9f2cb4a761da63dbed499d207f25fd7778f3b1e4a7bd890492786da7e974735f"},"source_sha256s":["92bda8ef8744a22132cb37f3516c40cdcd03019191a660a15578927bc5bcb8d0","9f2cb4a761da63dbed499d207f25fd7778f3b1e4a7bd890492786da7e974735f"]},{"claim_binding_sha256":"2464f5bb86f065e9c7ecbca0027966e68eb047936e2f3c98f3bfa7ce133768d6","claim_id":"clm_7dbd7c7d1c4ddf90","corpus_manifest_sha256":"921e7ce79ecb3ee7811b6ee2530b4f6dc5c302da3ade6afbdae0b92fd822790e","family":"rent_increase_dispute","request_source_pin":{"end_char":1146,"family":"rent_increase_dispute","file_name":"01-ordinary-tenancy-and-original-notification-packet.txt","offset_unit":"unicode_code_point","quote":"assessment of the original notice's missing-reasons/nullity ground","source_sha256":"a80464834b0af6f726ffaacd28409cbe37d5ec6b8d21fe3be925ccb55252d9d4","start_char":1080,"text_sha256":"a80464834b0af6f726ffaacd28409cbe37d5ec6b8d21fe3be925ccb55252d9d4"},"source_sha256s":["66717d12a5196d405dbc05f003c39224951dbabdb63522dae601e6718dc95fc7","a80464834b0af6f726ffaacd28409cbe37d5ec6b8d21fe3be925ccb55252d9d4"]},{"claim_binding_sha256":"eafe9d2487947160481f604b31d7596e34eb8e9dc42b211e265ca33602433413","claim_id":"clm_95d08975bc575592","corpus_manifest_sha256":"921e7ce79ecb3ee7811b6ee2530b4f6dc5c302da3ade6afbdae0b92fd822790e","family":"defect_mold_heating","request_source_pin":{"end_char":552,"family":"defect_mold_heating","file_name":"01-customer-and-tenancy-clarification.txt","offset_unit":"unicode_code_point","quote":"removal of the continuing heating defect and assessment of proportional rent-reduction eligibility","source_sha256":"3d0bbab0966ae98a55c50e444c4700db6b2e6c99666be6ac40de96854aae4317","start_char":454,"text_sha256":"3d0bbab0966ae98a55c50e444c4700db6b2e6c99666be6ac40de96854aae4317"},"source_sha256s":["3d0bbab0966ae98a55c50e444c4700db6b2e6c99666be6ac40de96854aae4317","a09b657cef7653c9df2239ce4df5b41c6dd7d532348297daa3e56de8512fa761","f3a6ac61d2a261e5ce8c4681784eef8a343297ed474f0ffada8d904c1beac2b8"]}],"contract":"casepath.release-procedure-outline/1","profile_id":"synthetic-nine-v2","profile_raw_sha256":"18c2ff55eb39324fee225b2b44330079715d1de11234d2367a2ed172b59c0869","source_files_sha256":{"casepath-api/casepath_api/autonomous_reference_policy_v1.py":"c0f28e7f3d1190a3eaa1d0f303500a9c422708ab3c7558477ddd01d897f788cb","casepath-api/casepath_api/corpora/synthetic-150/policy/static-rule-templates-v3.json":"986bf411784ada0524f03d06ef5038d2fb90e27422ee12300a713c644d849343","casepath-api/casepath_api/reference_profiles/synthetic-nine-v1/normative_sources.json":"57686c1be8943715f6b93893ba31579c3cf5dca623837a56241114902f0fb2a0"}});
  const featuredCase = id => REFERENCE_DEMO_CASES.find(row => row.claim_id === id) || DEMO_CASES.find(row => row.claim_id === id);
  // Collections are named by provenance. `legacy` stays a URL alias only.
  const DEMO_COLLECTIONS = Object.freeze({selected:'Selected originals',reference:'Reference assessments · fixed rules · fictional supplements'});
  const demoCollection = value => value === 'selected' || value === 'legacy' ? 'selected' : value === 'reference' ? 'reference' : null;
  const demoCases = collection => demoCollection(collection) === 'selected' ? DEMO_CASES : REFERENCE_DEMO_CASES;
  const replayCollection = (id, collection) => demoCollection(collection) || (REFERENCE_DEMO_CASES.some(row => row.claim_id === id) ? 'reference' : DEMO_CASES.some(row => row.claim_id === id) ? 'selected' : 'reference');
  const REFERENCE_POLICY_ID = 'casepath.bounded-reference-assessment/1.0.0';
  // Catalog heads are routing hints. A fixed-rule reference history never
  // counts as a selected-original recording, and a model history never plays
  // as a reference assessment.
  const fixedRuleHistory = row => Boolean(row) && row.revision > 0 && (row.policy_id === REFERENCE_POLICY_ID || row.outcome?.reference_provenance?.mode === 'deterministic_reference');
  const selectedHistory = row => Boolean(row) && row.revision > 0 && !fixedRuleHistory(row);
  const referenceHistory = row => Boolean(row) && row.revision > 0 && (!row.policy_id || row.policy_id === REFERENCE_POLICY_ID);
  const collectionHistory = (collection, row) => demoCollection(collection) === 'selected' ? selectedHistory(row) : referenceHistory(row);
  function demoRoster(catalogRows) {
    const rows = list(catalogRows), at = id => rows.find(row => row?.claim_id === id);
    const reference = REFERENCE_DEMO_CASES.filter(row => !at(row.claim_id) || referenceHistory(at(row.claim_id)));
    if (reference.length) return {collection:'reference',cases:reference};
    const selected = DEMO_CASES.filter(row => selectedHistory(at(row.claim_id)));
    return selected.length ? {collection:'selected',cases:selected} : {collection:null,cases:[]};
  }
  // An explicitly chosen collection drops only cases known to lack its kind of
  // history. With none known, its fixed order opens and states what is missing.
  function collectionRoster(collection, catalogRows) {
    const fixed = demoCases(collection), rows = list(catalogRows);
    const kept = fixed.filter(row => { const known = rows.find(claim => claim?.claim_id === row.claim_id); return !known || collectionHistory(collection,known); });
    return kept.length ? kept : fixed;
  }
  // One label for a case everywhere: the featured label first, the original
  // subject second. Unfeatured cases keep their original subject.
  function caseLabel(claimId, apiRow = null) {
    const featured = featuredCase(claimId), subject = String(apiRow?.title || apiRow?.claim_title || '').trim();
    return featured ? {primary:featured.label,secondary:subject && subject !== featured.label ? subject : ''} : {primary:subject || claimId || 'Untitled case',secondary:''};
  }
  const mounts = new WeakMap();
  let activeMount = null;
  const h = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const list = value => Array.isArray(value) ? value : [];
  const words = value => String(value ?? '').replace(/[_.-]+/g, ' ').replace(/^./, c => c.toUpperCase());
  const text = value => typeof value === 'string' ? value : '';
  const recordedName = item => item?.label || item?.title || item?.name || words(item?.node_id || item?.document_type || item?.fact_id || item?.type || item?.action_id || item?.kind);
  const name = item => !item ? '' : item.document_type || item.file_name ? language.documentTitle(item) : item.node_id ? language.stepLabel(item) : plain(item.label || item.title || item.name || words(item.fact_id || item.type || item.action_id || item.kind));
  const dateLabel = value => { const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value || '') : new Intl.DateTimeFormat('en', {dateStyle:'medium',timeStyle:'short'}).format(date); };
  const key = value => encodeURIComponent(String(value));
  const button = (label, attr, primary = false) => `<button type="button" class="${primary ? 'au-primary' : 'au-secondary'}" ${attr}>${h(label)}</button>`;
  const complete = status => ['completed','complete','resolved'].includes(status);
  const referenceAssessmentComplete = claim => claim?.policy_id === 'casepath.bounded-reference-assessment/1.0.0' && claim.outcome?.assessment_status === 'complete' && claim.outcome.reference_provenance?.mode === 'deterministic_reference' && claim.outcome.reference_provenance.synthetic === true && !claim.deferral && !active(claim.status);
  const executionFailed = claim => claim?.status === 'failed' || !active(claim?.status) && (list(claim?.reconciliations).at(-1)?.status === 'failed' || ['provider_deferred','verification_deferred','execution_deferred'].includes(claim?.deferral?.code));
  // Where a case stands, in the shared lexicon (language.caseStatuses).
  // Received (or queued) work has not started running. An execution deferral
  // (failed, paused, no model, incomplete intake) is Stopped; a collection
  // row carries no deferral details, so a deferred row without an outcome
  // stays Stopped. A recorded deferred assessment is "More evidence needed"
  // unless its draft rules out a document gap; then it stays Deferred. A
  // status code outside the lexicon is Status unknown.
  function caseStatus(claim = {}) {
    const status = claim?.status;
    if (status === 'received' || status === 'queued') return 'received';
    if (active(status)) return 'working';
    if (!status || status === 'not_started' || status === 'not_run') return 'not_started';
    if (executionFailed(claim) || claim.deferral) return 'stopped';
    if (referenceAssessmentComplete(claim) || complete(status)) return 'investigation_complete';
    if (status === 'deferred') return !claim.outcome ? 'stopped' : language.draftStatus(claim.outcome).status === 'no_gap' ? 'deferred' : 'more_evidence';
    return 'unknown';
  }
  // Status filters use the lexicon IDs. Recorded codes in older links still resolve.
  const CASE_FILTER_ALIASES = Object.freeze({failed:'stopped',paused:'stopped',completed:'investigation_complete',complete:'investigation_complete',resolved:'investigation_complete',not_run:'not_started',queued:'received',running:'working',investigating:'working'});
  const caseFilter = value => value === 'all' || language.caseStatuses.some(row => row.id === value) ? value : CASE_FILTER_ALIASES[value] || 'all';
  // An older ?status= link named the recorded code; its deferred cases were
  // the ones asking for evidence. ?filter= names the lexicon status itself.
  const legacyStatusFilter = value => value === 'deferred' ? 'more_evidence' : caseFilter(value || 'all');
  const active = status => ['received', 'queued', 'running', 'working', 'investigating'].includes(status);
  const tone = status => ['completed', 'complete', 'resolved', 'established', 'satisfied', 'qualified'].includes(status) ? 'done' : ['deferred', 'blocked', 'failed', 'unresolved', 'unknown', 'quarantined'].includes(status) ? 'blocked' : active(status) || status === 'ready' ? 'active' : 'neutral';
  const statusLabel = status => ({not_started:'Not started',not_run:'Not run',received:'Received', queued:'Queued', running:'Working', working:'Working', completed:'Completed', complete:'Completed', resolved:'Completed', investigation_complete:'Checks complete', deferred:'Deferred', failed:'Stopped', ready:'Ready to check', true:'Applies', false:'Does not apply', insufficient:'Not established', missing:'Not established', prepared_not_sent:'Draft ready, not sent', not_reached:'Not reached', inactive:'Does not apply', unresolved:'Not established', unknown:'Not established', blocked:'Waiting for prerequisites', established:'Established', satisfied:'Satisfied', needed_now:'Needed now', needed_later:'Needed later', held_behind_question:'May be needed', held_not_reviewed:'Needs checking', not_needed:'Not required', optional:'Optional'})[status] || words(status) || 'Not recorded';
  function claimStatusLabel(status, claim = {}) { return language.caseStatusLabel(caseStatus({...claim,status})); }
  // Why a stopped case stopped, when the record says. A summary row without a
  // deferral is not given a reason it does not carry.
  function stopReason(claim = {}) {
    if (caseStatus(claim) !== 'stopped') return '';
    return claim.deferral?.code === 'paused' ? 'Paused.' : executionFailed(claim) ? 'Execution failed.' : '';
  }
  const replayCanAdvance = state => Boolean(state.outcome) && !active(state.status) && state.status !== 'failed' && !state.deferral && (!list(state.reconciliations).length || list(state.reconciliations).at(-1).status === 'completed');
  const isHash = value => /^[a-f0-9]{64}$/i.test(value || '');
  const originalText = state => state.message || state.original_binding?.intake?.customer_message?.body || (typeof state.source_preview === 'string' ? state.source_preview : state.source_preview?.text) || '';
  const domainOf = claim => claim.browse_metadata?.domain || '';

  function referenceExecution(state) {
    const contexts = state.semantic_contexts || {}, receipt = [...list(state.receipts)].reverse().find(row => row.kind === 'interpretation.accepted')?.receipt;
    // Every object here belongs to the displayed prefix. Current-run context
    // takes precedence over a retained assessment from an earlier run.
    const context = state.run_id ? contexts[state.run_id] : Object.values(contexts).at(-1);
    const provenance = context ? context.execution_mode === 'deterministic_reference' ? context.reference_provenance : null : state.run_id && receipt?.workflow_id && receipt.workflow_id !== state.run_id ? null : receipt?.reference_execution?.provenance || state.outcome?.reference_provenance;
    if (provenance?.mode === 'deterministic_reference' && provenance.synthetic === true && /^\d{4}-\d{2}-\d{2}$/.test(provenance.as_of || '')) return provenance;
    return state.revision > 0 && state.policy_id === 'casepath.bounded-reference-assessment/1.0.0' ? {mode:'deterministic_reference',synthetic:true} : null;
  }
  function intakeGate(projection) {
    const gate = projection?.intake;
    return gate?.contract === 'casepath.source-backed-intake/1.0.0' && isHash(gate.gate_sha256) ? gate : null;
  }
  const intakeEligible = projection => !projection?.intake || Boolean(intakeGate(projection)?.eligible === true && intakeGate(projection)?.status === 'complete');
  const writable = status => root.CASEPATH_PUBLIC_READ_ONLY !== true && status?.read_only !== true && status?.writable !== false;
  // A status with neither a model nor a reference adapter has no execution path.
  // Unknown status keeps its own wait; intake eligibility remains the server's.
  const executionUnavailable = status => Boolean(status) && status.provider_ready !== true && status.reference_ready !== true;
  function claimAvailability(status, state, projection) {
    if (!writable(status)) return {ready:false,reason:'This workspace is view only.'};
    if (executionUnavailable(status)) return {ready:false,reason:language.copy.analysisUnavailable};
    if (!intakeEligible(projection)) return {ready:false,reason:'Complete the source-backed intake requirements before starting.'};
    if (REFERENCE_DEMO_CASES.some(row => row.claim_id === state?.claim_id)) return {ready:false,reason:state?.revision > 0 ? 'Open replay to see the saved checks.' : 'This reference case is not started from this page.'};
    return liveAvailability(status);
  }
  const intakeRowLabel = status => ({sufficient:'Source support present',missing:'Missing',insufficient:'Needs more support',unassessed:language.copy.notCheckedYet})[status] || 'Not established';
  function intakeMarkup(state, projection = {}) {
    const gate = intakeGate(projection);
    if (!gate) return '';
    const rows = list(gate.checklist), unchecked = rows.length > 0 && rows.every(row => row.status === 'unassessed');
    const label = unchecked ? language.copy.intakeNotChecked : ({complete:'Intake complete',incomplete:'Intake incomplete',unsupported:'More information needed'})[gate.status] || 'More information needed';
    const known = id => list(state.source_descriptors).some(source => source.artifact_id === id);
    // Attached files are candidates only. A row's own recorded files stay with
    // that row; files no row names are listed once, without any sufficiency claim.
    const named = new Set(rows.flatMap(row => list(row.artifact_ids)));
    const candidates = list(state.source_descriptors).filter(source => source.role === 'supporting_document' && !named.has(source.artifact_id));
    const candidateMarkup = rows.length && candidates.length ? `<div class="au-intake-candidates" data-au-intake-candidates><p class="au-meta">${h(language.copy.candidateFiles)}</p><div class="au-related">${candidates.map(source => button(sourceLabel(state,source.artifact_id),`data-au-source="${h(source.artifact_id)}" data-au-source-origin="intake:candidate:${h(source.artifact_id)}" data-au-intake-candidate="${h(source.artifact_id)}"`)).join('')}</div></div>` : '';
    return `<section class="au-intake-inspection" data-au-intake-gate="${h(gate.status)}"${unchecked ? ' data-au-intake-unchecked' : ''}><div class="au-section-heading"><h2>${h(label)}</h2>${recordButton('Technical record','intake')}</div>${rows.length ? `<ul class="au-intake-checklist">${rows.map(row => `<li data-au-intake-document="${h(row.document_type)}" data-status="${h(row.status)}"><div><strong>${h(row.label || words(row.document_type))}</strong><span>${h(intakeRowLabel(row.status))}</span></div><div class="au-related">${list(row.artifact_ids).filter(known).map(id => button(sourceLabel(state,id),`data-au-source="${h(id)}" data-au-source-origin="intake:${h(row.document_type)}:${h(id)}"`)).join('')}</div></li>`).join('')}</ul>${candidateMarkup}` : '<p class="au-meta">Describe the issue and provide the relevant documents to begin an assessment.</p>'}</section>`;
  }
  function referenceSourcePin(state, source, projection = {}) {
    const context = Object.values(state.semantic_contexts || {}).some(row => row.execution_mode === 'deterministic_reference' && row.reference_provenance?.synthetic === true && list(row.sources).some(pin => pin.artifact_id === source.artifact_id && pin.sha256 === source.sha256));
    const gate = intakeGate(projection), provenance = gate?.provenance;
    return context || gate?.status === 'complete' && gate.eligible === true && provenance?.mode === 'deterministic_reference' && provenance.synthetic === true && isHash(state.source_roster_sha256) && provenance.source_roster_sha256 === state.source_roster_sha256 && list(state.source_descriptors).some(pin => pin.artifact_id === source.artifact_id && pin.sha256 === source.sha256);
  }
  function currentSourceSelection(state, projection = {}) {
    const sources = list(state.source_descriptors), gate = intakeGate(projection);
    const recorded = state.semantic_contexts?.[state.run_id]?.reference_provenance;
    const provenance = recorded?.source_roster_sha256 === state.source_roster_sha256 ? recorded : gate?.eligible === true ? gate.provenance : null;
    const ids = list(provenance?.source_artifact_ids);
    if (provenance?.mode !== 'deterministic_reference' || provenance.synthetic !== true || provenance.profile_id !== 'synthetic-nine-v2' ||
        !isHash(state.source_roster_sha256) || provenance.source_roster_sha256 !== state.source_roster_sha256 ||
        !ids.length || new Set(ids).size !== ids.length || ids.some(id => !sources.some(source => source.artifact_id === id)) ||
        list(state.original_binding?.source_map).some(source => !ids.includes(source.artifact_id))) return sources;
    return sources.filter(source => ids.includes(source.artifact_id));
  }
  function sourceExcerpt(state, source, projection = {}) {
    let body = readableSourceText(state,source) || '';
    if (referenceSourcePin(state,source,projection) && ['SYNTHETIC SUPPLEMENT — FICTIONAL DEMONSTRATION SOURCE\n','Synthetic demonstration document (fictional)\n'].some(header => body.startsWith(header))) {
      const separator = body.indexOf('\n\n');
      if (separator >= 0) body = body.slice(separator + 2);
    }
    const chars = Array.from(body);
    return chars.slice(0,520).join('') + (chars.length > 520 ? '…' : '');
  }
  function sourceKind(state, source, projection = {}) {
    const original = list(state.original_binding?.source_map).some(row => row.artifact_id === source.artifact_id && row.sha256 === source.sha256);
    if (original) return 'Original source';
    const acquired = list(state.acquired_sources).find(row => row.artifact_id === source.artifact_id && row.sha256 === source.sha256);
    return ['SYNTHETIC SUPPLEMENT — FICTIONAL DEMONSTRATION SOURCE\n','Synthetic demonstration document (fictional)\n'].some(header => acquired?.text?.startsWith(header)) || referenceSourcePin(state,source,projection) ? 'Fictional case document' : source.role === 'customer_message' ? 'Original source' : 'Supporting source';
  }
  function legalAuthorityRows(state) {
    const context = state.semantic_contexts?.[state.run_id];
    if (context?.execution_mode !== 'deterministic_reference') return [];
    const pack = list(context.rule_packs).find(row => row.family === state.graph?.family), authorities = list(pack?.legal_authority);
    const finalRefs = state.outcome?.assessment_status === 'complete' ? new Set(list(state.outcome.legal_predicates).flatMap(row => list(row.rule_refs)).map(ref => /^CO:(\d+[a-z]?)$/.exec(ref)?.[1]).filter(Boolean)) : null;
    return authorities.filter(row => typeof row.article === 'string' && typeof row.text === 'string' && (!finalRefs || finalRefs.has(row.article)));
  }
  function legalBasisMarkup(state) {
    const context = state.semantic_contexts?.[state.run_id];
    if (context?.execution_mode !== 'deterministic_reference') return '';
    const rows = legalAuthorityRows(state);
    const official = value => { try { const url = new URL(value); return url.protocol === 'https:' && ['www.fedlex.admin.ch','fedlex.admin.ch','fedlex.data.admin.ch'].includes(url.hostname) ? url.href : null; } catch (_) { return null; } };
    const links = rows.map(row => { const url = official(row.source?.publisher_url); return url ? `<a href="${h(url)}" target="_blank" rel="noopener noreferrer" data-au-law-article="${h(row.article)}" title="${h(`CO ${row.article} · Fedlex ${row.source.consolidation_date || ''}`)}">Swiss Code of Obligations, art. ${h(row.article)}</a>` : h(`Swiss Code of Obligations, art. ${row.article}`); });
    if (!links.length) return '';
    const law = context.normative_sources || {}, compared = list(law.historical_comparison?.substantive_paragraphs_reported_same), older = law.older_snapshot, asOf = context.reference_provenance?.as_of;
    const olderURL = official(older?.publisher_url), showComparison = asOf && rows.some(row => row.source?.consolidation_date > asOf && compared.includes(row.article));
    return `<p class="au-legal-basis" data-au-legal-basis>Legal basis · ${links.join(' · ')}${showComparison && olderURL ? ` · <a href="${h(olderURL)}" target="_blank" rel="noopener noreferrer" data-au-law-comparison>Earlier law text (${h(older.consolidation_date)})</a>` : ''}</p>`;
  }

  function readState(response, claimId) {
    const state = response?.state && typeof response.state === 'object' ? response.state : response;
    if (!state || typeof state.claim_id !== 'string' || !Number.isSafeInteger(state.revision) || state.revision < 0 || !isHash(state.state_sha256)) throw new Error('The saved claim identity is incomplete.');
    if (state.revision === 0 && (state.mode !== 'unprocessed' || state.status !== 'not_started' || state.phase !== 'not_run' || state.graph !== null || state.evaluation !== null || state.outcome || state.deferral || ['facts','obligations','actions','acquired_sources'].some(field => list(state[field]).length))) throw new Error('The unprocessed claim identity contains unaccepted work.');
    if (claimId && state.claim_id !== claimId) throw new Error('The response belongs to another claim.');
    if (state.graph?.claim_id && state.graph.claim_id !== state.claim_id) throw new Error('The process belongs to another claim.');
    const projection = response.projection || {};
    // Older envelopes omitted projection identity; present bindings must match.
    for (const field of ['claim_id','revision','state_sha256']) if (Object.prototype.hasOwnProperty.call(projection, field) && projection[field] !== state[field]) throw new Error('The capability projection belongs to a different saved claim revision.');
    if (Object.prototype.hasOwnProperty.call(projection, 'parent_revision') && projection.parent_revision !== state.revision) throw new Error('The capability projection belongs to a different saved claim revision.');
    if (Object.prototype.hasOwnProperty.call(projection, 'parent_state_sha256') && projection.parent_state_sha256 !== state.state_sha256) throw new Error('The capability projection belongs to a different saved claim revision.');
    return {state, projection};
  }
  function readSnapshot(response, claimId, previous, reconnect = false) {
    const incoming = readState(response,claimId), state = incoming.state;
    if (response.current_revision !== state.revision || response.current_state_sha256 !== state.state_sha256) {
      const error = new Error('The atomic snapshot does not match its saved revision.'); error.transientAdvance = true; throw error;
    }
    if (incoming.projection.revision !== state.revision || incoming.projection.state_sha256 !== state.state_sha256) throw new Error('The snapshot capability projection has no matching identity.');
    const zero = state.revision === 0;
    if (zero ? response.cursor_sha256 !== null : !isHash(response.cursor_sha256)) throw new Error('The snapshot journal cursor identity is incomplete.');
    if (state.last_event_sha256 !== undefined && response.cursor_sha256 !== state.last_event_sha256) throw new Error('The snapshot cursor differs from the saved journal identity.');
    const accepted = acceptEvents(previous,response,state,reconnect);
    if (!accepted.ready) throw new Error('The snapshot event cursor does not match its saved revision.');
    const last = accepted.events.at(-1);
    if (last?.event_sha256 && last.event_sha256 !== response.cursor_sha256) throw new Error('The snapshot final event differs from the journal cursor.');
    return {...incoming,accepted,cursor_sha256:response.cursor_sha256};
  }

  function layoutGraph(graph) {
    const nodes = list(graph?.nodes), edges = list(graph?.edges);
    const byId = new Map(), parents = new Map(), children = new Map(), ranks = new Map();
    for (const node of nodes) {
      if (!node.node_id || byId.has(node.node_id)) throw new Error('The saved process has duplicate or missing step identities.');
      byId.set(node.node_id, node); parents.set(node.node_id, []); children.set(node.node_id, []); ranks.set(node.node_id, 0);
    }
    for (const edge of edges) {
      const from = edge.source_node_id, to = edge.target_node_id;
      if (!byId.has(from) || !byId.has(to)) throw new Error('A saved process connection has no step.');
      parents.get(to).push(from); children.get(from).push(to);
    }
    const pending = new Map([...parents].map(([id, entries]) => [id, entries.length]));
    const queue = nodes.filter(node => !pending.get(node.node_id)).map(node => node.node_id), ordered = [];
    for (let i = 0; i < queue.length; i++) {
      const id = queue[i]; ordered.push(byId.get(id));
      for (const next of children.get(id)) {
        ranks.set(next, Math.max(ranks.get(next), ranks.get(id) + 1));
        pending.set(next, pending.get(next) - 1);
        if (!pending.get(next)) queue.push(next);
      }
    }
    if (ordered.length !== nodes.length) throw new Error('The saved process contains a cycle and cannot be displayed as an executable path.');
    const rows = [];
    for (const node of ordered) (rows[ranks.get(node.node_id)] ||= []).push(node);
    return {rows, nodes:ordered, edges, parents, children, byId};
  }

  function eventIdentity(event) {
    const after = event.after || event.payload?.after || {};
    return {revision:after.revision ?? event.revision ?? event.after_revision, state_sha256:after.state_sha256 ?? event.state_sha256 ?? event.after_state_sha256, graph_sha256:after.graph_sha256};
  }
  function acceptEvents(previous, batch, state, reconnect = false) {
    if (!batch || !Array.isArray(batch.events) || !Number.isSafeInteger(batch.current_revision)) throw new Error('The saved event cursor is incomplete.');
    if (batch.current_revision !== state.revision) return {ready:false, cursor:previous, events:[], animate:[]};
    if (batch.current_state_sha256 && batch.current_state_sha256 !== state.state_sha256) throw new Error('The event response differs from the saved claim identity.');
    const rows = [...batch.events].sort((a,b) => a.seq - b.seq);
    let cursor = previous ?? 0;
    for (const event of rows) {
      if (!Number.isSafeInteger(event.seq) || event.seq < 1 || (event.claim_id && event.claim_id !== state.claim_id)) throw new Error('An event has an invalid claim or sequence.');
      if (event.seq !== cursor + 1 || eventIdentity(event).revision !== event.seq) throw new Error('The saved event sequence has a gap or duplicate.');
      cursor = event.seq;
    }
    if (cursor !== state.revision) throw new Error('The event cursor does not reach the saved claim revision.');
    if (rows.length && eventIdentity(rows.at(-1)).state_sha256 !== state.state_sha256) throw new Error('The latest event does not match the saved claim identity.');
    const animate = previous == null || reconnect ? [] : rows.filter(event => {
      const after = eventIdentity(event);
      return event.seq > previous && after.revision === state.revision && after.state_sha256 === state.state_sha256 && (!after.graph_sha256 || after.graph_sha256 === state.graph?.graph_sha256);
    });
    return {ready:true, cursor, events:rows, animate};
  }

  function conditionFlags(expression) {
    if (!expression || typeof expression !== 'object') return [];
    return [...new Set([...(expression.flag ? [expression.flag] : []), ...conditionFlags(expression.not), ...list(expression.all || expression.any).flatMap(conditionFlags)])];
  }
  function changedTargets(before, after) {
    const nodeValue = (state, id) => JSON.stringify([list(state?.graph?.nodes).find(row => row.node_id === id), list(state?.evaluation?.nodes).find(row => row.node_id === id)]);
    const docValue = (state, id) => JSON.stringify([list(state?.obligations).filter(row => row.document_type === id), list(state?.evaluation?.documents).find(row => row.document_type === id)]);
    return {nodes:list(after.graph?.nodes).filter(node => nodeValue(before,node.node_id) !== nodeValue(after,node.node_id)).map(node => node.node_id), documents:[...new Set(list(after.obligations).map(row => row.document_type))].filter(id => docValue(before,id) !== docValue(after,id))};
  }

  function progressModel(state, history = []) {
    state ||= {};
    let start = state.run_id ? history.length : 0;
    for (let i=history.length-1;i>=0;i--) if (history[i].kind === 'work.started' && (!state.run_id || history[i].payload?.run_id === state.run_id)) { start=i; break; }
    const events=history.slice(start), phases=new Set(events.filter(event=>event.kind==='work.phase').map(event=>event.payload?.phase));
    if (state.status==='running') phases.add(state.phase);
    const has=kind=>events.some(event=>event.kind===kind);
    const accepted=[...events].reverse().find(event=>event.kind==='interpretation.accepted');
    const checks=list(accepted?.payload?.receipt?.checks);
    const sources=list(state.acquired_sources).length,total=list(state.source_descriptors).length;
    const publications=list(state.knowledge_published),published=publications.filter(item=>item.qualification?.status==='qualified').length,quarantined=publications.filter(item=>item.qualification?.status==='quarantined').length,uses=list(state.knowledge_uses).length;
    const phaseStage={acquiring:'sources',interpreting:'interpretation',verifying:'verification',progressing:'process'};
    const working=state.status==='running' ? phaseStage[state.phase] : null;
    const lastPhase=[...events].reverse().find(event=>event.kind==='work.phase')?.payload?.phase;
    const stopped=!active(state.status) ? phaseStage[lastPhase] : null;
    const definitions=[
      {id:'sources',label:'Sources',complete:total>0&&sources===total,detail:`${sources} / ${total} acquired`},
      {id:'interpretation',label:'Interpretation',complete:phases.has('verifying')||Boolean(accepted),detail:phases.has('verifying')||accepted?'Proposal recorded':phases.has('interpreting')?(working==='interpretation'?'Reading the evidence':'Interpretation not accepted'):'Not yet recorded'},
      {id:'verification',label:'Independent verification',complete:Boolean(accepted),detail:checks.length?`${checks.length} checks recorded`:accepted?'Interpretation admitted':phases.has('verifying')?(working==='verification'?'Checking source support':'Verification not accepted'):'Not yet recorded'},
      {id:'process',label:'Process & actions',complete:has('outcome.recorded'),detail:`${list(state.actions).length} action${list(state.actions).length===1?'':'s'} recorded in this claim · ${list(state.obligations).length} obligations`},
      {id:'knowledge',label:'Knowledge',complete:events.some(event=>event.kind==='knowledge.published'&&event.payload?.knowledge?.qualification?.status==='qualified'),detail:`${published} published · ${uses} reused${quarantined?` · ${quarantined} quarantined`:''}`}
    ];
    const stages=definitions.map(stage=>({...stage,state:working===stage.id?'active':stage.complete?'complete':stopped===stage.id?'blocked':stage.id==='knowledge'&&has('knowledge.published')?'blocked':stage.id==='knowledge'&&has('knowledge.used')?'recorded':'pending'}));
    const explanation=state.status==='running' ? (working ? state.phase_summary || 'Autonomous work has started.' : 'Autonomous work has started.') : state.deferral?.reason || state.outcome?.summary || 'Showing recorded work.';
    return {stages,explanation};
  }
  function progressMarkup(state,history) {
    const progress=progressModel(state,history);
    return `<section class="au-work-progress" aria-label="Recorded autonomous work"><ol class="au-progress-track">${progress.stages.map((stage,index)=>`<li data-au-stage="${stage.id}" data-state="${stage.state}"${stage.state==='active'?' aria-current="step"':''}><span class="au-progress-marker" aria-hidden="true">${stage.state==='complete'?'✓':stage.state==='recorded'?'↺':index+1}</span><div><strong>${h(stage.label)}</strong><span>${stage.state==='recorded'?'Reuse recorded · ':''}${h(stage.detail)}</span></div></li>`).join('')}</ol><p class="au-progress-explanation${active(state.status) ? '' : ' au-sr-only'}" role="status" aria-live="polite">${h(progress.explanation)}</p></section>`;
  }
  function transitionPlan(before,after,accepted,history=[]) {
    if (!before || before.claim_id!==after.claim_id || after.revision<=before.revision || !accepted?.ready || !accepted.animate?.length) return null;
    const newest=accepted.animate.at(-1),identity=eventIdentity(newest);
    if (identity.revision!==after.revision || identity.state_sha256!==after.state_sha256 || newest.seq!==accepted.cursor) return null;
    const changes=changedTargets(before,after);
    const changedFacts=list(after.facts).filter(fact=>JSON.stringify(list(before.facts).find(row=>row.fact_id===fact.fact_id))!==JSON.stringify(fact));
    const sourceValue=(state,id)=>JSON.stringify([list(state.source_descriptors).find(row=>row.artifact_id===id),list(state.acquired_sources).find(row=>row.artifact_id===id)]);
    const sourceIds=new Set(list(after.source_descriptors).filter(source=>sourceValue(before,source.artifact_id)!==sourceValue(after,source.artifact_id)).map(source=>source.artifact_id));
    for (const fact of changedFacts) for (const citation of citationRows(fact)) sourceIds.add(citation.artifact_id);
    const edgeValue=(state,id)=>JSON.stringify([list(state.graph?.edges).find(row=>row.edge_id===id),list(state.evaluation?.edges).find(row=>row.edge_id===id)]);
    const edges=list(after.graph?.edges).filter(edge=>edgeValue(before,edge.edge_id)!==edgeValue(after,edge.edge_id)).map(edge=>({id:edge.edge_id,delay:360,duration:180}));
    const nodes=changes.nodes.map(id=>({id,created:!list(before.graph?.nodes).some(node=>node.node_id===id),delay:360,duration:180}));
    const facts=changedFacts.map(fact=>({id:fact.fact_id,delay:180,duration:180}));
    const sources=[...sourceIds].filter(Boolean).map(id=>({id,delay:0,duration:180}));
    const beforeRequirements = new Set(formingRequirements(before).map(requirementIdentity));
    const enteredDocuments = formingRequirements(after).filter(item => !beforeRequirements.has(requirementIdentity(item))).map(item => item.document_type);
    const documents=[...new Set([...changes.documents,...enteredDocuments])].map(id => {
      const reviewed = list(before.evaluation?.documents).find(row => row.document_type === id)?.review_state !== list(after.evaluation?.documents).find(row => row.document_type === id)?.review_state;
      const obligationIds = formingRequirements(after).filter(item => item.document_type === id && (!beforeRequirements.has(requirementIdentity(item)) || canonicalJSON(item) !== canonicalJSON(list(before.obligations).find(row => requirementIdentity(row) === requirementIdentity(item))))).map(requirementIdentity);
      return {id,delay:540,duration:180,...(!reviewed && obligationIds.length ? {obligationIds} : {})};
    });
    const semantic = semanticEventRecord(after,newest);
    const knowledgeUses=list(after.knowledge_uses).filter(item=>!list(before.knowledge_uses).some(previous=>canonicalJSON(previous)===canonicalJSON(item))).map(item=>({id:item.knowledge_sha256 || item.knowledge_id || item.version_id,delay:360,duration:180}));
    const knowledgePublications=list(after.knowledge_published).filter(item=>!list(before.knowledge_published).some(previous=>canonicalJSON(previous)===canonicalJSON(item))).map(item=>({id:item.knowledge_sha256 || item.knowledge_id || item.candidate_id,delay:360,duration:180}));
    return {cue:{seq:newest.seq},sources,facts,edges,nodes,documents,knowledgeUses,knowledgePublications,semantic:semantic ? [{id:semantic.id,delay:360,duration:180}] : [],stages:[],duration:720};
  }
  function animateTransition(host,plan,environment={}) {
    const animations = new Set(), overlays = new Set();
    const cancel = () => { for (const animation of animations) animation.cancel(); animations.clear(); for (const overlay of overlays) overlay.remove(); overlays.clear(); };
    if (!plan || environment.reducedMotion || environment.hidden || environment.dialogOpen || environment.keyboard || environment.inspecting) return {cancel,count:0,duration:0};
    const selected = environment.selected ?? host.querySelector?.('[data-au-node][aria-pressed="true"]')?.dataset.auNode;
    const candidates = [], seen = new Set();
    const forming = host.querySelector?.('[data-au-forming="true"]'), formingGraph = forming && (plan.nodes || []).some(row => row.created);
    const add = (element,timing,edge = false,stage = 'process') => {
      if (!element?.animate || !timing || seen.has(element) || element.closest?.('[hidden],details:not([open])') || element === environment.activeElement || element.contains?.(environment.activeElement)) return;
      seen.add(element); candidates.push({element,timing,edge,stage});
    };
    // Only the visible selected evidence path carries motion. Every other
    // accepted change renders immediately into its inspectable settled state.
    for (const [selector,field,rows,stage] of [['[data-au-source-arrival]','auSourceArrival',plan.sources || [],'sources'],['[data-au-source]','auSource',plan.sources || [],'sources'],['[data-au-node]','auNode',plan.nodes || [],'process'],['[data-au-fact]','auFact',plan.facts || [],'facts'],['[data-au-document]','auDocument',plan.documents || [],'documents'],['[data-au-knowledge-use]','auKnowledgeUse',plan.knowledgeUses || [],'knowledge'],['[data-au-knowledge-publication]','auKnowledgePublication',plan.knowledgePublications || [],'knowledge']]) {
      for (const element of host.querySelectorAll(selector)) {
        if (formingGraph && field === 'auNode' || formingGraph && field === 'auDocument' && element.closest?.('.au-forming-documents')) continue;
        if (field === 'auNode' && selected && element.dataset.auNode !== selected && !rows.some(row=>row.id===element.dataset.auNode && row.created)) continue;
        if (['auSource','auFact','auDocument'].includes(field) && element.closest && !element.closest('[data-au-evidence-path]')) continue;
        if (field === 'auSemanticEvent' && element.matches && !element.matches('.au-event-cue')) continue;
        const timing = rows.find(row => row.id === element.dataset[field]);
        if (field === 'auDocument' && timing?.obligationIds && !timing.obligationIds.includes(element.dataset.auObligation || element.closest?.('.au-obligation')?.dataset.auObligation)) continue;
        add(element,timing,false,stage);
      }
    }
    if (formingGraph) add(forming.querySelector('[data-au-graph-pan]'),{delay:0,duration:160},false,'process');
    if (formingGraph && (plan.documents || []).length) add(forming.querySelector('.au-forming-documents .au-obligations'),{delay:0,duration:160},false,'documents');
    const stepTiming = (plan.nodes || []).find(row => row.id === selected);
    if (stepTiming) for (const junction of host.querySelectorAll('[data-au-expanded-junction]')) if (junction.dataset.auExpandedJunction === selected) add(junction.closest?.('header'),stepTiming);
    if (plan.cue) for (const cue of host.querySelectorAll('[data-au-event-seq]')) if (Number(cue.dataset.auEventSeq) === plan.cue.seq) add(cue,{delay:360,duration:180},false,'cue');
    const edge = [...host.querySelectorAll('[data-au-edge]')].find(element => (!selected || element.getAttribute?.('data-selected') === 'true') && (plan.edges || []).some(row => row.id === element.dataset.auEdge));
    if (edge && !formingGraph) add(edge,plan.edges.find(row => row.id === edge.dataset.auEdge),true);
    // Complete all visibility/clip and path-length measurements before WAAPI
    // or SVG writes. Partly clipped graph objects settle without animation.
    const clips = new Map(); let visible = candidates.filter(candidate => {
      const {element} = candidate, bounds = element.getBoundingClientRect?.();
      if (bounds) {
        if (!bounds.width || !bounds.height || bounds.right <= 0 || bounds.bottom <= 0 || bounds.left >= (root.innerWidth || Infinity) || bounds.top >= (root.innerHeight || Infinity)) return false;
        const clip = element.closest?.('.au-graph-viewport');
        if (clip) { if (!clips.has(clip)) clips.set(clip,clip.getBoundingClientRect()); const area = clips.get(clip); if (bounds.left < area.left || bounds.right > area.right || bounds.top < area.top || bounds.bottom > area.bottom) return false; }
      }
      if (candidate.edge) { candidate.length = element.getTotalLength?.(); if (!Number.isFinite(candidate.length) || candidate.length <= 0) return false; }
      return true;
    });
    // Carry process attention on one real object. Its other representations
    // still render the accepted state, without another competing pulse.
    const newNodes = new Set((plan.nodes || []).filter(row=>row.created).map(row=>row.id));
    const process = visible.find(({element}) => element.querySelector?.('[data-au-expanded-junction]')) || visible.find(({element}) => element.dataset?.auNode) || visible.find(row => row.stage === 'process');
    visible = visible.filter(row => row.stage !== 'process' || row === process || newNodes.has(row.element.dataset?.auNode));
    const stages = ['sources','facts','process','documents','knowledge'].filter(stage => visible.some(row => row.stage === stage));
    if (!stages.length && visible.length) stages.push('process');
    const cueStage = stages.includes('process') ? 'process' : stages.at(-1);
    for (const row of visible) row.timing = {delay:stages.indexOf(row.stage === 'cue' ? cueStage : row.stage)*180,duration:180};
    const duration = Math.min(800,stages.length*160);
    for (const row of visible) row.timing = {delay:Math.min(640,stages.indexOf(row.stage === 'cue' ? cueStage : row.stage)*160),duration:160};
    const run = (element,timing,cleanup = () => {}) => {
      const animation = element.animate([{opacity:.58,transform:'translateY(3px)'},{opacity:1,transform:'translateY(0)'}],{...timing,easing:'cubic-bezier(.2,.65,.3,1)',fill:'none'}); animations.add(animation);
      animation.finished?.then(() => { animations.delete(animation); cleanup(); },() => { animations.delete(animation); cleanup(); });
    };
    for (const {element,timing,edge} of visible) {
      if (!edge) { run(element,timing); continue; }
      const overlay = element.cloneNode(false); overlay.setAttribute('class','au-live-edge'); overlay.removeAttribute?.('data-au-edge'); overlay.removeAttribute?.('data-state'); overlay.removeAttribute?.('data-selected'); element.parentNode.appendChild(overlay); overlays.add(overlay);
      run(overlay,timing,() => { overlay.remove(); overlays.delete(overlay); });
    }
    return {cancel,count:animations.size,duration};
  }

  const citationRows = item => list(item?.citations || item?.sources || item?.source_spans);
  const sourceLabel = (state, id) => name(list(state.source_descriptors).find(source => source.artifact_id === id)) || list(state.source_descriptors).find(source => source.artifact_id === id)?.file_name || 'Original source';
  function sourceButtons(state, item, origin = `record:${item?.fact_id || item?.obligation_id || item?.document_type || item?.action_id || item?.kind || 'claim'}`) {
    return citationRows(item).map(citation => `<button type="button" class="au-source-link" data-au-source="${h(citation.artifact_id)}" data-au-source-origin="${h(origin)}" data-au-citation="${h(JSON.stringify(citation))}">${h(sourceLabel(state, citation.artifact_id))}${citation.quote ? `<q>${h(citation.quote)}</q>` : ''}</button>`).join('');
  }
  function rejectedItemsMarkup(state, receipt, origin) {
    const rejected = list(receipt?.item_rejections);
    if (!rejected.length) return '';
    return `<details class="au-evidence-inspection" data-au-disclosure="rejected-items:${h(origin)}"><summary>Rejected proposal items <span>${rejected.length}</span></summary><p class="au-meta">These proposed items were rejected. Their original text is retained as rejected provenance.</p><ul class="au-event-list">${rejected.map((rejection,index) => {
      const sources = [...new Set([rejection.item?.artifact_id,...list(rejection.item?.citations).map(citation => citation.artifact_id)])].filter(id => list(state.source_descriptors).some(source => source.artifact_id === id));
      return `<li><div><strong>Rejected · ${h(rejection.item_id)}</strong><p>${h(rejection.reason)}</p><div class="au-related">${sources.map(id => button(`Inspect original: ${sourceLabel(state,id)}`,`data-au-source="${h(id)}" data-au-source-origin="rejected:${h(origin)}:${h(rejection.item_id)}"`)).join('')}</div><details class="au-technical-record" data-au-disclosure="rejected-proposal:${h(origin)}:${h(index)}"><summary>Original rejected proposal</summary><pre class="au-record-body">${h(JSON.stringify(rejection.item,null,2))}</pre></details></div></li>`;
    }).join('')}</ul></details>`;
  }
  function rejectionHistoryMarkup(state) {
    const seen = new Set();
    return [...list(state.receipts),...list(state.actions)].map((row,index) => {
      const receipt = row.receipt || {};
      const identity = receipt.workflow_id || receipt.proposal_sha256 || receipt.receipt_sha256 || `unassociated:${index}`;
      const item_rejections = list(receipt.item_rejections).filter(item => {
        const key = canonicalJSON([identity,item]);
        if (seen.has(key)) return false;
        seen.add(key); return true;
      });
      return rejectedItemsMarkup(state,{item_rejections},`claim:${receipt.receipt_sha256 || index}`);
    }).join('');
  }
  function reconciliationMarkup(state) {
    const rows = list(state.reconciliations);
    if (!rows.length) return '';
    return `<section class="au-reconciliation-history"><h3>Saved-result reconciliation</h3><p class="au-meta">This history records checks of saved results. The original execution failure remains in the journal.</p><ol class="au-event-list">${rows.map(row => `<li><div><strong>${h(({started:'Saved-result reconciliation started',completed:'Saved-result reconciliation completed',failed:'Saved-result reconciliation failed'})[row.status] || 'Saved-result reconciliation status not recorded')}</strong><p>${h(row.reconciliation_id)}</p>${row.original_deferral?.reason ? `<p>Original execution failure: ${h(row.original_deferral.reason)}</p>` : ''}${row.failure_reason ? `<p>${h(row.failure_reason)}</p>` : ''}${row.status === 'completed' ? '<p>The saved results were reconciled. The recorded operational outcome determines which evidence remains unresolved.</p>' : row.status === 'started' ? '<p>No completed reconciliation is recorded for this attempt.</p>' : ''}<details class="au-technical-record" data-au-disclosure="reconciliation:${h(row.reconciliation_id)}"><summary>Full reconciliation record</summary><pre class="au-record-body">${h(JSON.stringify(row,null,2))}</pre></details></div></li>`).join('')}</ol></section>`;
  }
  function acceptedEventNode(state, event) {
    if (!event || event.claim_id !== state.claim_id || !['action.completed','graph.advanced','interpretation.accepted'].includes(event.kind) || !Number.isSafeInteger(event.seq) || event.seq < 1 || event.seq > state.revision || eventIdentity(event).revision !== event.seq || !isHash(event.event_sha256) || !isHash(eventIdentity(event).state_sha256)) return null;
    if (event.seq === state.revision && (eventIdentity(event).state_sha256 !== state.state_sha256 || state.last_event_sha256 && event.event_sha256 !== state.last_event_sha256)) return null;
    const known = new Set(list(state.graph?.nodes).map(node => node.node_id));
    const semantic = semanticEventRecord(state,event);
    if (semantic?.nodes?.length) return semantic.nodes.find(id => known.has(id)) || null;
    if (event.kind === 'interpretation.accepted') {
      const cited = list(state.graph?.nodes).find(node => evidenceRelationships(state,node.node_id).facts.some(fact => citationRows(fact).length));
      if (cited) return cited.node_id;
    }
    const payload = event.payload || {};
    return [payload.node_id,...list(payload.node_ids)].find(id => known.has(id)) || null;
  }
  function preferredNode(state, remembered = null, events = []) {
    const nodes = list(state.graph?.nodes), has = id => nodes.some(node => node.node_id === id);
    if (has(remembered)) return remembered;
    let eventFallback = null;
    for (const event of [...events].reverse()) {
      const node = acceptedEventNode(state,event);
      if (!node) continue;
      eventFallback ||= node;
      if (evidenceRelationships(state,node).facts.some(fact => citationRows(fact).length)) return node;
    }
    if (has(state.evaluation?.focus_node_id)) return state.evaluation.focus_node_id;
    const cited = nodes.find(node => evidenceRelationships(state,node.node_id).facts.some(fact => citationRows(fact).length));
    if (cited) return cited.node_id;
    if (eventFallback) return eventFallback;
    const relevant = list(state.evaluation?.nodes).find(node => has(node.node_id) && (node.execution_state === 'ready' || node.activation === 'unresolved') && evidenceRelationships(state,node.node_id).documents.length);
    return relevant?.node_id || list(state.evaluation?.nodes).find(node => node.execution_state === 'ready' && has(node.node_id))?.node_id || nodes[0]?.node_id || null;
  }
  function consequentialEventNode(before, state, event) {
    if (!before || before.claim_id !== state.claim_id || !Number.isSafeInteger(before.revision) || before.revision < 0 || !isHash(before.state_sha256) || before.revision >= state.revision) return null;
    const id = acceptedEventNode(state,event);
    if (!id) return null;
    const relations = evidenceRelationships(state,id), old = evidenceRelationships(before || {},id);
    if (!relations.facts.length && !relations.documents.length) return null;
    const same = (a,b) => canonicalJSON(a) === canonicalJSON(b);
    if (!old.node) return id;
    if (relations.facts.some(fact => !same(fact,old.facts.find(item => item.fact_id === fact.fact_id)))) return id;
    if (relations.documents.some(document => !same(document,old.documents.find(item => requirementIdentity(item) === requirementIdentity(document))))) return id;
    if (!same([relations.evaluation.activation,relations.evaluation.condition_verdict], [old.evaluation.activation,old.evaluation.condition_verdict])) return id;
    return null;
  }
  function replayContentPacing(event, changes = null) {
    if (!event) return 300;
    if (['sources.acquired','sources.arrived','interpretation.accepted','knowledge.used','knowledge.published','outcome.recorded','work.completed','work.deferred'].includes(event.kind)) return 4000;
    if (changes && ['facts','documents','nodes','edges','sources','knowledgeUses','knowledgePublications'].some(field => list(changes[field]).length)) return 3500;
    return 300;
  }
  function acceptedEventContext(state, event, selected) {
    const semantic = semanticEventRecord(state,event);
    if (semantic?.type !== 'action' || !semantic.nodes.includes(selected)) return {};
    const result = semantic.record.result, relationships = evidenceRelationships(state,selected), context = {};
    const obligations = [result.obligation_id,...list(result.obligation_ids)].filter(Boolean);
    const requirement = relationships.documents.find(item => obligations.includes(requirementIdentity(item)) && (!result.document_type || item.document_type === result.document_type)) || relationships.documents.find(item => item.document_type === result.document_type);
    if (requirement) Object.assign(context,{document:requirement.document_type,obligation:requirementIdentity(requirement)});
    const facts = [result.fact_id,...list(result.fact_ids),...list(result.required_fact_ids)].filter(Boolean);
    const compatible = evidenceRelationships(state,selected,context);
    const fact = compatible.facts.find(item => facts.includes(item.fact_id) && (!requirement || list(requirement.required_fact_ids).includes(item.fact_id)));
    if (fact) context.fact = fact.fact_id;
    // The requirement's recorded dependency is the existing graph relation;
    // no document or fact is inferred from the action's prose or citations.
    return evidenceSelection(state,selected,context);
  }
  function preferredEvidenceContext(state, selected, events, preferences = {}, previous = null) {
    if (preferences.node || preferences.document || preferences.obligation || preferences.fact) return {document:preferences.document,obligation:preferences.obligation,fact:preferences.fact,trace:preferences.trace};
    if (previous?.selected) return previous.evidenceContext || {};
    for (const event of [...events].reverse()) {
      const semantic = semanticEventRecord(state,event);
      if (semantic?.type === 'action' && semantic.nodes.includes(selected)) return acceptedEventContext(state,event,selected);
    }
    return {};
  }
  function edgeState(state, id) {
    const evaluation = list(state.evaluation?.edges).find(edge => edge.edge_id === id);
    return evaluation?.activation || evaluation?.condition_verdict || 'unresolved';
  }
  function recordButton(label, kind, id = '') {
    return `<button type="button" class="au-link au-record-link" data-au-inspect="${h(kind)}" data-au-record-id="${h(id)}">${h(label)}</button>`;
  }
  function factCaseText(fact) {
    const summary = text(fact?.summary).trim(), reason = text(fact?.reason).trim();
    if (summary && reason) return reason.includes(summary) ? reason : summary.includes(reason) ? summary : `${summary} ${reason}`;
    if (summary || reason) return summary || reason;
    return ({true:'This condition applies.',false:'This condition does not apply.',established:'This is established from the supplied sources.',satisfied:'This requirement is met.'})[fact?.verdict || fact?.status] || 'This question is not yet established.';
  }
  function messagePreview(message) {
    return message.length >= 240 ? message.slice(0,240).replace(/\s+\S*$/, '') + '…' : message;
  }
  function contextualRecord(state, projection = {}, events = [], kind = 'claim', id = '', data = {}, replay = null) {
    if (kind === 'claim') return {state,projection};
    if (kind === 'intake') return projection.intake;
    if (kind === 'replay') return replay;
    if (kind === 'step') return {node:list(state?.graph?.nodes).find(row => row.node_id === id),evaluation:list(state?.evaluation?.nodes).find(row => row.node_id === id),capability:projection.node_capabilities?.[id],edges:list(state?.graph?.edges).filter(row => row.source_node_id === id || row.target_node_id === id),edge_evaluations:list(state?.evaluation?.edges).filter(row => list(state?.graph?.edges).some(edge => edge.edge_id === row.edge_id && (edge.source_node_id === id || edge.target_node_id === id)))};
    if (kind === 'fact') return list(state?.facts).find(row => row.fact_id === id);
    if (kind === 'requirement') return {obligations:list(state?.obligations).filter(row => requirementIdentity(row) === id),evaluation:list(state?.evaluation?.documents).filter(row => `document:${row.document_type}` === id || list(state?.obligations).some(item => requirementIdentity(item) === id && item.document_type === row.document_type))};
    if (kind === 'event') return list(events).find(row => String(row.seq) === String(id));
    if (kind === 'action') { const rows = actionRows(state,events); return rows.find(row => row.instanceId === id) || (/^\d+$/.test(String(id)) ? rows[Number(id)] : undefined); }
    if (kind === 'outcome') return {outcome:state?.outcome,deferral:state?.deferral};
    if (kind === 'reconciliation') return list(state?.reconciliations).find(row => row.reconciliation_id === id);
    if (kind === 'knowledge-index') return data;
    if (kind === 'learning-event') return list(data.learning_replay?.events).find(event=>event.event_id===id) || null;
    if (kind === 'withheld-index') return list(data.quarantined);
    if (kind === 'knowledge') return list(data.versions).find(row => `${row.knowledge_id || row.version_id}:${row.version || row.version_id}` === id);
    if (kind === 'use') return list(state?.knowledge_uses).concat(list(data.uses))[Number(id)];
    if (kind === 'publication') return list(state?.knowledge_published)[Number(id)];
    if (kind === 'quarantine') return list(data.quarantined)[Number(id)];
    return null;
  }
  // The record dialog answers in place: one plain sentence, the cited passage
  // and labelled rows come first; the exact saved JSON stays one disclosure away.
  // The only <pre> in the record dialog sits inside its Technical record.
  const RECORD_DIALOG_SKELETON = '<div class="au-record-explain" data-au-record-explain></div><details class="au-technical-record au-record-technical" data-au-record-technical><summary>Technical record</summary><p class="au-record-context"></p><pre class="au-record-body"></pre></details>';
  function recordSource(state, trace, artifactId) {
    const source = trace?.sources?.get?.(artifactId) || list(state?.acquired_sources).find(row => row.artifact_id === artifactId);
    return typeof source?.text === 'string' ? source : null;
  }
  function recordSourceTitle(state, trace, artifactId) {
    const descriptor = list(state?.source_descriptors).find(row => row.artifact_id === artifactId) || trace?.sources?.get?.(artifactId);
    return descriptor ? operationSourceTitle(descriptor) : 'Original source';
  }
  // A passage is marked only when its exact Unicode span is found in the text
  // this view already verified; otherwise the quote is shown unmarked.
  function checkedCitationSpan(source, citation) {
    if (!source || typeof citation?.quote !== 'string' || !citation.quote || citation.text_sha256 && source.text_sha256 && citation.text_sha256 !== source.text_sha256) return null;
    const chars = sourceCharacters(source);
    let start = citation.start_char, end = citation.end_char;
    if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end)) {
      const at = source.text.indexOf(citation.quote);
      if (at < 0 || source.text.indexOf(citation.quote,at+1) >= 0) return null;
      start = Array.from(source.text.slice(0,at)).length; end = start+Array.from(citation.quote).length;
    }
    if (start < 0 || end <= start || end > chars.length || chars.slice(start,end).join('') !== citation.quote) return null;
    return {chars,start,end};
  }
  function passageWindow(chars, start, end) {
    const opens = i => i <= 0 || chars[i-1] === '\n' || /\s/u.test(chars[i-1]) && /[.!?]/u.test(chars[i-2] || '');
    const closes = i => i >= chars.length || chars[i] === '\n' || /[.!?]/u.test(chars[i-1] || '') && /\s/u.test(chars[i]);
    let left = start, right = end;
    while (left > 0 && start-left < 240 && !opens(left)) left--;
    while (right < chars.length && right-end < 240 && !closes(right)) right++;
    while (left < start && /\s/u.test(chars[left])) left++;
    while (right > end && /\s/u.test(chars[right-1])) right--;
    return {left,right,clippedLeft:left > 0 && !opens(left),clippedRight:right < chars.length && !closes(right)};
  }
  function recordPassageMarkup(state, trace, citation, options = {}) {
    if (!citation?.artifact_id || typeof citation.quote !== 'string') return '';
    const source = recordSource(state,trace,citation.artifact_id), span = checkedCitationSpan(source,citation), title = recordSourceTitle(state,trace,citation.artifact_id);
    const openable = list(state?.source_descriptors).some(row => row.artifact_id === citation.artifact_id);
    const open = openable ? `<button type="button" class="au-secondary au-record-open-source" data-au-source="${h(citation.artifact_id)}" data-au-citation="${h(JSON.stringify(citation))}" data-au-source-origin="${h(options.origin || 'record')}">Open source</button>` : '';
    const caption = `<figcaption><span class="au-record-passage-title">${h(title)}</span>${options.caption ? ` <span class="au-meta">${h(options.caption)}</span>` : ''}</figcaption>`;
    if (!span) return `<figure class="au-record-passage" data-au-record-passage data-au-passage-verified="false">${caption}<blockquote><p><q>${h(citation.quote)}</q></p></blockquote><p class="au-meta">The exact position could not be checked in this view. Open source checks it against the original.</p>${open}</figure>`;
    const {chars,start,end} = span, focus = options.focus && options.focus.start >= start && options.focus.end <= end && options.focus.end > options.focus.start ? options.focus : null;
    const window = passageWindow(chars,start,end), slice = (a,b) => h(chars.slice(a,b).join(''));
    const cited = focus ? `<span class="au-record-cited">${slice(start,focus.start)}</span><mark data-au-record-mark>${slice(focus.start,focus.end)}</mark><span class="au-record-cited">${slice(focus.end,end)}</span>` : `<mark data-au-record-mark>${slice(start,end)}</mark>`;
    return `<figure class="au-record-passage" data-au-record-passage data-au-passage-verified="true" data-au-source-start-char="${start}" data-au-source-end-char="${end}">${caption}<blockquote><p>${window.clippedLeft ? '…' : ''}${slice(window.left,start)}${cited}${slice(end,window.right)}${window.clippedRight ? '…' : ''}</p></blockquote>${open}</figure>`;
  }
  function citationLocator(state, trace, citation) {
    if (!citation?.artifact_id) return '';
    const span = checkedCitationSpan(recordSource(state,trace,citation.artifact_id),citation), title = recordSourceTitle(state,trace,citation.artifact_id);
    if (!span) return title;
    const line = span.chars.slice(0,span.start).filter(char => char === '\n').length+1;
    return `${title} · line ${line}, characters ${span.start}–${span.end}`;
  }
  function operationCitation(operation, trace) {
    if (!operation) return null;
    if (operation.source?.artifact_id) return operation.source;
    const recorded = citationRows(operation.result).find(row => row?.artifact_id && typeof row.quote === 'string');
    if (recorded) return recorded;
    const cause = list(trace?.rows).find(row => row.id === list(operation.cause_ids).at(-1));
    return ['phrase.match','span.read'].includes(operation.kind) && cause?.source ? cause.source : null;
  }
  // A step's own evaluation cites nothing; its passage is the one cited by a
  // fact checked at that step, and the caption says so.
  function stepCitation(trace, nodeId) {
    for (const row of trace?.dockedFacts?.values?.() || []) if (row.node === nodeId && row.operation?.source?.artifact_id) return row.operation;
    return null;
  }
  function operationSubject(operation, state, trace) {
    const id = operation?.object?.id, type = operation?.object?.type;
    if (!id) return '';
    if (type === 'fact') return id === 'category' ? 'the case category' : language.factLabel(list(state?.facts).find(row => row.fact_id === id) || {fact_id:id});
    if (type === 'node') { const node = list(state?.graph?.nodes).find(row => row.node_id === id) || list(trace?.working?.graph?.nodes).find(row => row.node_id === id); return node ? language.stepLabel(node) : ''; }
    if (type === 'document') return name(list(state?.graph?.document_catalog).find(row => row.document_type === id)) || language.documentTitle(id);
    if (type === 'source') return recordSourceTitle(state,trace,id);
    if (type === 'knowledge') return procedureLabel({knowledge_id:id});
    return '';
  }
  function recordRowsMarkup(rows) {
    const shown = rows.filter(row => row && row.value);
    return shown.length ? `<dl class="au-record-rows">${shown.map(row => `<div data-au-record-row="${h(row.id)}"><dt>${h(row.label)}</dt><dd>${row.html ? row.value : h(row.value)}</dd></div>`).join('')}</dl>` : '';
  }
  const sentence = value => /[.!?…]$/u.test(value.trim()) ? value.trim() : `${value.trim()}.`;
  const recordTime = timestamp => timestamp && Number.isFinite(Date.parse(timestamp)) ? `<time datetime="${h(timestamp)}">${h(dateLabel(timestamp))}</time>` : '';
  // Every passage a record cites is reachable: the first is shown in its
  // context with the exact span marked, the rest follow as source links.
  function recordMorePassagesMarkup(state, trace, citations, origin) {
    if (!citations.length) return '';
    const openable = citation => list(state?.source_descriptors).some(row => row.artifact_id === citation.artifact_id);
    return `<section class="au-record-more" data-au-record-more aria-label="Other cited passages"><p class="au-record-more-title">${citations.length === 1 ? '1 more cited passage' : `${citations.length} more cited passages`}</p><ul>${citations.map((citation,index) => {
      const link = openable(citation), locator = `<span class="au-record-more-locator">${h(citationLocator(state,trace,citation))}${link ? '<span aria-hidden="true"> ↗</span>' : ''}</span>`, quote = `<q>${h(citation.quote)}</q>`;
      return `<li>${link ? `<button type="button" class="au-source-link au-record-more-source" data-au-source="${h(citation.artifact_id)}" data-au-citation="${h(JSON.stringify(citation))}" data-au-source-origin="${h(`${origin}:${index+1}`)}">${locator}${quote}</button>` : `${locator}${quote}`}</li>`;
    }).join('')}</ul></section>`;
  }
  const quotedCitations = rows => list(rows).filter(row => row?.artifact_id && typeof row.quote === 'string');
  function recordExplanation(kind, record, context = {}) {
    const state = context.state || {}, events = list(context.events), trace = context.trace || null, origin = `record:${kind}:${context.id || ''}`;
    let title = '', what = '', role = '', citations = [], result = '', revision = '', time = '', caption = '', revisionLabel = 'Accepted revision';
    const roleValue = (roleId, how = '') => `${roleBadge(roleId)}${how ? ` <span class="au-record-how">${h(how)}</span>` : ''}`;
    if (!record) return {title:'Details',html:recordRowsMarkup([{id:'what',label:'What happened',value:'This record is not available in the current view.'}])};
    if (kind === 'operation' || kind === 'operation-attempt') {
      const shown = language.operationPresentation(record,{state,history:true,documents:[...list(state.source_descriptors),...list(state.graph?.document_catalog)]}), subject = operationSubject(record,state,trace);
      title = subject || shown.label; what = sentence(`${shown.label}${subject ? `: ${subject}` : ''}`); role = roleValue(shown.roleId,shown.how !== 'CasePath' ? shown.how : '');
      const own = operationCitation(record,trace); citations = own ? [own] : [];
      if (!own && record.object?.type === 'node') { const via = stepCitation(trace,record.object.id); if (via) { citations = [via.source]; caption = `Cited for ${operationSubject(via,state,trace) || 'this step'}`; } }
      // A recorded decision speaks for itself; templated status words only accompany other operations.
      result = [...new Set([text(shown.recordedResult).trim(),record.kind === 'decision' && text(shown.recordedResult).trim() ? '' : recordedResultLabel(record,state)].filter(value => value && value !== 'Recorded in History.'))].join(' ');
      // A working step is a proposal inside the run, never an accepted event;
      // the row names the accepted revision the case stood at instead.
      revisionLabel = 'Accepted';
      const checkpoint = kind === 'operation' && [...list(trace?.checkpoints)].reverse().find(row => row.after_operation < record.seq), step = Number.isSafeInteger(record.seq) ? `working step ${record.seq}` : 'a working step';
      if (checkpoint) { revision = `No · ${step} while the case stood at revision ${checkpoint.revision}`; const event = list(checkpoint.events).find(row => row.seq === checkpoint.revision); time = recordTime(event?.timestamp) ? `${recordTime(event.timestamp)} · when revision ${h(checkpoint.revision)} was saved` : ''; }
      else revision = `No · ${step}`;
    } else if (kind === 'event') {
      const shown = language.eventPresentation(record), semantic = semanticEventRecord(state,record);
      title = Number.isSafeInteger(record.seq) ? `Revision ${record.seq}` : 'Saved record'; what = sentence(`${shown.roleLabel} ${shown.past}${semantic?.title ? `: ${semantic.title}` : ''}`); role = roleValue(shown.roleId);
      citations = [semantic?.citations,citationRows(record.payload?.result),citationRows(record.payload?.outcome)].map(quotedCitations).find(rows => rows.length) || [];
      result = text(record.payload?.summary) || text(record.payload?.reason) || text(record.payload?.outcome?.summary) || text(semantic?.summary);
      revision = Number.isSafeInteger(record.seq) ? String(record.seq) : ''; time = recordTime(record.timestamp);
    } else if (kind === 'outcome') {
      const outcome = record.outcome, deferral = record.deferral, event = [...list(events)].reverse().find(row => ['outcome.recorded','work.completed','work.deferred'].includes(row.kind));
      title = outcome ? 'Recorded result' : 'Work stopped';
      if (event) { const shown = language.eventPresentation(event); what = `${shown.roleLabel} ${shown.past}.`; role = roleValue(shown.roleId); revision = String(event.seq); time = recordTime(event.timestamp); }
      else {
        // Without its journal event in view, the record does not say who saved it or when.
        what = outcome ? 'This result is part of the saved case. Its journal entry is not in the loaded history.' : 'The checks stopped. Its journal entry is not in the loaded history.';
        revision = Number.isSafeInteger(state.revision) ? `Not in the loaded history · the case at revision ${state.revision} includes it` : 'Not in the loaded history';
      }
      citations = outcome ? openableCitations(state,outcome) : []; result = text(outcome?.summary) || text(outcome?.reason) || text(deferral?.reason);
    } else if (kind === 'action') {
      const action = record.result || {}, receipt = record.receipt || {}, shown = language.eventPresentation({kind:'action.completed'}), seq = Number.isSafeInteger(receipt.parent_revision) ? receipt.parent_revision+1 : null;
      const step = [action.node_id,...list(action.node_ids)].map(id => list(state.graph?.nodes).find(node => node.node_id === id)).find(Boolean);
      // The title names the step; the recorded sentence stays in Result only.
      title = step ? `Recorded action · ${language.stepLabel(step)}` : 'Recorded action'; what = `${shown.roleLabel} ${shown.past}${step ? `: ${language.stepLabel(step)}` : ''}.`; role = roleValue(shown.roleId); citations = quotedCitations(citationRows(action));
      result = [text(action.summary) || text(action.reason),action.status ? statusLabel(action.status) : ''].filter(Boolean).join(' · ');
      revision = seq ? String(seq) : ''; time = recordTime(list(events).find(row => row.seq === seq)?.timestamp);
    } else if (kind === 'fact') {
      title = language.factLabel(record); what = sentence(`Recorded finding: ${title}`); citations = quotedCitations(citationRows(record));
      result = `${statusLabel(record.verdict || record.status)} · ${factCaseText(record)}`;
    } else {
      const node = record.node, sentences = {claim:`The saved case at revision ${state.revision ?? 'not recorded'}.`,intake:'The source-backed intake check for this case.',
        replay:`The verified replay at revision ${record.through_seq ?? '?'} of ${record.current_revision ?? '?'}.`,step:node ? `Recorded step: ${language.stepLabel(node)}.` : 'Recorded step.',
        requirement:'The recorded document requirement and its evaluation.',reconciliation:'A saved result review.',notice:text(record.message) || 'A recorded notice.',
        'knowledge-index':'The Knowledge index as read.',knowledge:'One saved procedure version.',use:'One recorded reuse of a saved procedure.',publication:'One recorded check of whether to save a procedure.',
        quarantine:'A procedure that was not saved.','withheld-index':'Procedures that were not saved.','learning-event':'One recorded Knowledge event.'};
      what = sentences[kind] || 'The exact saved record.';
    }
    const first = citations[0] || null;
    const passage = first ? `${recordPassageMarkup(state,trace,first,{origin,focus:context.focus,caption})}${recordMorePassagesMarkup(state,trace,citations.slice(1),origin)}` : '';
    const source = first ? `${citationLocator(state,trace,first)}${citations.length > 1 ? ` · passage 1 of ${citations.length}` : ''}` : ['operation','operation-attempt','event','outcome','action','fact'].includes(kind) ? 'None cited' : '';
    const rest = recordRowsMarkup([{id:'role',label:'Role',value:role,html:true},{id:'source',label:'Source',value:source},
      {id:'result',label:'Result',value:result},{id:'revision',label:revisionLabel,value:revision},{id:'time',label:'Time',value:time || (['event','outcome','action','operation'].includes(kind) ? 'Not recorded' : ''),html:Boolean(time)}]);
    const lead = recordRowsMarkup([{id:'what',label:'What happened',value:what}]);
    return {title,html:context.passageFirst && passage ? `${passage}${lead}${rest}` : `${lead}${passage}${rest}`};
  }
  function sourceObjectIdentity(state, id) {
    const descriptor = list(state.source_descriptors).find(item => item.artifact_id === id), acquired = list(state.acquired_sources).find(item => item.artifact_id === id);
    return descriptor ? `${state.claim_id}:${id}:${descriptor.sha256}:${acquired?.text_sha256 || ''}` : '';
  }
  function readableSourceText(state, source) {
    if (source.extraction === 'unsupported_metadata') return null;
    const media = String(source.media_type || '').split(';')[0].trim().toLowerCase();
    const wire = typeof source.text === 'string' ? source.text : '';
    const encodedMessage = media === 'message/rfc822' || /(?:^|\r?\n)Content-(?:Type:\s*multipart\/|Transfer-Encoding:)/i.test(wire);
    const binding = state.original_binding, message = binding?.intake?.customer_message, original = message?.raw_file;
    const descriptor = list(state.source_descriptors).find(item => item.artifact_id === source.artifact_id);
    if (!encodedMessage && !(binding && descriptor?.role === 'customer_message')) return wire || null;
    if (binding?.claim_id !== state.claim_id || !descriptor || descriptor.role !== 'customer_message' || !original || original.sha256 !== source.sha256 || descriptor.sha256 !== source.sha256 || typeof message.body !== 'string' || message.body !== state.message) return null;
    const mapped = list(binding.source_map).find(item => item.artifact_id === source.artifact_id && item.original_artifact_id === original.artifact_id && item.sha256 === original.sha256);
    return mapped ? message.body : null;
  }
  function acquiredContentMarkup(state, projection = {}) {
    const visible = new Set(currentSourceSelection(state,projection).map(source => source.artifact_id));
    const acquired = list(state.acquired_sources).filter(source => visible.has(source.artifact_id) && readableSourceText(state,source));
    if (!acquired.length) return '';
    return `<section class="au-reading-passages au-reading-acquisition"><h3 class="au-reading-label">Readable sources</h3>${acquired.map(source => `<button type="button" class="au-source-link au-evidence-source" data-au-source-identity="${h(sourceObjectIdentity(state,source.artifact_id))}" data-au-source="${h(source.artifact_id)}" data-au-source-arrival="${h(source.artifact_id)}" data-au-source-origin="acquisition:${h(source.artifact_id)}"><span class="au-evidence-source-label">${h(operationSourceTitle(source))}<span aria-hidden="true">↗</span></span><pre class="au-original-message au-source-excerpt au-acquired-text">${h(sourceExcerpt(state,source,projection))}</pre><span class="au-meta">${h(sourceKind(state,source))} · ${source.complete ? 'Readable text' : 'Partly readable text'} · Assessment is separate</span></button>`).join('')}</section>`;
  }
  function openingContentMarkup(state, projection = {}) {
    return `<div class="au-reading-column au-opening-content">${originalText(state) ? `<h2>Original message</h2><pre class="au-original-message">${h(originalText(state))}</pre>` : ''}${acquiredContentMarkup(state,projection) || sourceListMarkup(state,list(state.source_descriptors),'originals',projection)}${list(state.knowledge_uses).length ? claimKnowledgeMarkup(state) : ''}</div>`;
  }
  function procedureLabel(item) {
    const id = item.knowledge_id || item.version_id || '', family = item.family || (id.startsWith('procedure.') ? id.slice('procedure.'.length) : '');
    const friendly = {defect_mold_heating:'Defects and repairs',lease_termination_dispute:'Lease termination',rent_increase_dispute:'Rent increases'};
    return friendly[family] || item.name || item.title || words(id) || 'Recorded procedure';
  }
  function caseDomain(state, claims = []) {
    const row = list(claims).find(claim => claim?.claim_id === state.claim_id), family = state.graph?.family !== 'incoming_packet' ? state.graph?.family : '';
    return [family,row?.browse_metadata?.domain,state.browse_metadata?.domain].find(id => DOMAINS.some(domain => domain.id === id)) || '';
  }
  // The procedure that applies to this case's domain, from the Knowledge
  // index. Whether it applies is decided when the case runs, not here.
  function caseProcedureMarkup(state, context = {}) {
    const family = caseDomain(state,context.claims);
    if (!family) return '';
    const entry = context.knowledge ? knowledgeLibrary(context.knowledge).find(row => row.family === family) : null;
    // Without a recorded process the domain is the catalog's browsing label.
    const listed = state.graph?.family !== family;
    const status = [!context.knowledge ? 'Knowledge index not loaded' : entry?.current ? `version ${entry.current.version} qualified` : entry?.candidates.length ? 'no qualified version · candidates were not saved' : 'base procedure · nothing learned yet', listed ? 'domain listed for browsing only' : '', 'whether it applies is checked when the case runs'].filter(Boolean).join(' · ');
    return `<p class="au-case-procedure" data-au-case-procedure="${h(family)}"${listed ? ' data-au-domain-source="browsing"' : ''}><button type="button" class="au-link" data-au-knowledge="procedure.${h(family)}" data-au-knowledge-claim="${h(state.claim_id)}">${h(procedureScope({family}))}</button> · ${h(status)}</p>`;
  }
  // Browsing only: the same scenario family first, then cases that share an
  // exact saved knowledge version. Never evidence or engine context.
  function similarCases(state, claims = [], knowledge = null, limit = 6) {
    const rows = list(claims), self = state.claim_id, own = rows.find(row => row?.claim_id === self);
    const family = own?.browse_metadata?.family_id || state.browse_metadata?.family_id, found = [];
    const add = (id, reason) => { if (id && id !== self && !found.some(row => row.id === id)) found.push({id,reason,row:rows.find(row => row?.claim_id === id) || null}); };
    if (family) for (const row of rows) if (row?.browse_metadata?.family_id === family) add(row.claim_id,'family');
    if (knowledge) {
      const model = knowledgeLearningModel(knowledge);
      for (const version of model.versions) {
        const receiving = knowledgeUses(version,model.uses).map(use => use.claim_id);
        if (version.source_claim_id !== self && !receiving.includes(self)) continue;
        for (const id of [version.source_claim_id,...receiving]) add(id,'knowledge');
      }
    }
    return found.slice(0,limit);
  }
  function similarCasesMarkup(state, context = {}) {
    const rows = similarCases(state,context.claims,context.knowledge);
    if (!rows.length) return '';
    return `<section class="au-similar-cases" data-au-similar-cases aria-labelledby="au-similar-title"><h3 id="au-similar-title">Similar cases · browsing only</h3><p class="au-meta">Not used as evidence or by the checks.</p><ul>${rows.map(({id,reason,row}) => `<li data-au-similar-reason="${reason}"><button type="button" class="au-secondary au-case-link" data-au-claim="${h(id)}">${caseLabelMarkup(caseLabel(id,row))}</button><span class="au-meta">${reason === 'family' ? 'Same scenario family' : 'Shares a saved procedure version'}</span></li>`).join('')}</ul></section>`;
  }
  function claimKnowledgeMarkup(state, events = [], context = {}) {
    const uses = list(state.knowledge_uses), publications = list(state.knowledge_published);
    const latest = [...events].reverse().filter(event => ['knowledge.used','knowledge.published'].includes(event.kind)).map(event => semanticEventRecord(state,event)).find(Boolean);
    const focus = latest ? {kind:latest.type === 'reused' ? 'use' : 'publication',item:latest.knowledge} : publications.length ? {kind:'publication',item:publications.at(-1)} : uses.length ? {kind:'use',item:uses.at(-1)} : null;
    if (!focus) return `<section class="au-claim-knowledge" data-au-case-knowledge><h2>Knowledge in this case</h2>${caseProcedureMarkup(state,context)}<p>No reusable procedure has been recorded for this case.</p>${similarCasesMarkup(state,context)}</section>`;
    const item = focus.item, index = (focus.kind === 'use' ? uses : publications).findIndex(row => canonicalJSON(row) === canonicalJSON(item));
    const qualified = item.qualification?.status === 'qualified';
    const identity = item.knowledge_sha256 || item.knowledge_id || item.version_id || item.candidate_id;
    const applicability = (item.applicability === 'same_verified_family_and_rule_version' ? `Used for this ${({'Lease termination':'lease-termination','Defects and repairs':'defects-and-repairs','Rent increases':'rent-increase'})[procedureLabel(item)] || 'current'} case.` : item.applicability?.summary || '');
    const body = focus.kind === 'use' ? `<article class="au-knowledge-use" data-au-knowledge-use="${h(identity)}"><h3>${h(procedureLabel(item))}</h3><p>Used for this case · Version ${h(item.version || item.version_id)}</p>${applicability ? `<p>${h(applicability)}</p>` : ''}<p>The case still requires its own source evidence.</p>${knowledgeLink(item)}</article>` : `<article class="au-knowledge-publication" data-au-knowledge-publication="${h(identity)}"><h3>${h(procedureLabel(item.candidate || item))}</h3><p>${qualified && item.version ? `Saved for reuse · Version ${h(item.version)}` : 'Not saved'}</p>${!qualified ? `<blockquote>${h(item.qualification?.reason || item.reason || 'No reason is recorded.')}</blockquote>` : ''}${qualified ? `${procedureScope(item) !== procedureLabel(item) ? `<p>${h(procedureScope(item))}</p>` : ''}${list(item.added_document_types).length ? `${item.added_document_types.map(type => { const recipe = list(item.evidence_recipes).find(row => row.document_type === type), requirement = list(item.obligations).find(row => row.document_type === type); return `<p class="au-knowledge-change">Added ${h((name(requirement) || words(type)).toLocaleLowerCase())} requirements${list(recipe?.required_fields).length ? `: ${h(recipe.required_fields.map(field => words(field).toLocaleLowerCase()).join(', '))}` : ''}.</p>`; }).join('')}` : list(item.obligations).length ? `<h4>Reusable document requirements</h4><ul class="au-definition-list">${item.obligations.map(obligation => `<li>${h(name(obligation))}</li>`).join('')}</ul>` : ''}${knowledgeLink(item)}` : item.candidate?.summary ? `<h4>Proposed content</h4><p>Not saved. The recorded checks did not pass.</p>${recordButton('Details','publication',String(index))}` : ''}</article>`;
    const related = uses.filter(use => focus.kind !== 'use' || canonicalJSON(use) !== canonicalJSON(item)).map(use => `<div>Used for this case · ${h(procedureLabel(use))} · Version ${h(use.version || use.version_id)} ${knowledgeLink(use)}</div>`).concat(publications.filter(publication => focus.kind !== 'publication' || canonicalJSON(publication) !== canonicalJSON(item)).map(publication => publication.qualification?.status === 'qualified' && publication.version ? focus.kind === 'use' && String(publication.knowledge_id) === String(item.knowledge_id) && String(publication.version) === String(item.version) ? `<div>Contributed by this case · the same ${h(procedureLabel(publication))} version ${h(publication.version)}</div>` : `<div>Contributed by this case · ${h(procedureLabel(publication))} · Version ${h(publication.version)} ${knowledgeLink(publication)}</div>` : `<div>Proposed by this case · ${h(procedureLabel(publication.candidate || publication))} · not saved</div>`));
    return `<section class="au-claim-knowledge" data-au-case-knowledge><h2>Knowledge in this case</h2>${caseProcedureMarkup(state,context)}${body}${related.length ? `<nav class="au-reading-objects" aria-label="Other knowledge recorded in this case">${related.join('')}</nav>` : ''}${similarCasesMarkup(state,context)}</section>`;
  }
  function formingWork(state, presentation = {}) {
    if (presentation.mode === 'replay') {
      const replay = presentation.replay;
      return Boolean(replay && replay.state?.claim_id === state.claim_id && replay.state.state_sha256 === state.state_sha256 && replay.through_seq === state.revision && Number.isSafeInteger(replay.current_revision) && replay.current_revision >= state.revision && (replay.current_revision > state.revision || presentation.playing || presentation.paused) && isHash(replay.current_state_sha256));
    }
    return active(state.status) || state.deferral?.code === 'paused';
  }
  function documentReviewMarkup(review) {
    if (!review) return '';
    const label = review === 'sufficient' ? 'Supplied evidence is sufficient.' : review === 'insufficient' ? 'Supplied evidence is not sufficient.' : ['missing','unreviewed','unresolved'].includes(review) ? 'Source evidence is not yet established.' : `Source review: ${statusLabel(review)}.`;
    return `<span class="au-document-review" data-au-review="${h(review)}">${h(label)}${review === 'sufficient' ? ' <span aria-hidden="true">✓</span>' : ''}</span>`;
  }
  function knowledgeOriginMarkup(state, item, data = {}, suppressSelfOrigin = false, recordedOrigin = false) {
    const version = list(data.versions).find(row => String(row.knowledge_id || row.version_id) === String(item.knowledge_id || item.version_id) && String(row.version || row.version_id) === String(item.version || item.version_id) && Boolean(item.knowledge_sha256 || item.definition_sha256) && (!item.knowledge_sha256 || row.knowledge_sha256 === item.knowledge_sha256) && (!item.definition_sha256 || (row.qualification?.definition_sha256 || row.definition_sha256) === item.definition_sha256));
    const origin = item.source_claim_id || version?.source_claim_id;
    if (suppressSelfOrigin && origin === state.claim_id) return '';
    return origin ? origin === state.claim_id ? `<p class="au-knowledge-origin">${recordedOrigin ? 'Recorded origin: this case’s source evidence.' : 'From this case’s source evidence.'}</p>` : `<p class="au-knowledge-origin">${button(recordedOrigin ? 'Origin source case' : 'Source case',`data-au-claim="${h(origin)}"`)}</p>` : '';
  }
  function formingKnowledgeMarkup(state, data = {}, publicationsOnly = false, usesOnly = false, publication = null, inlineUses = [], operationDelivery = false) {
    const uses = publicationsOnly ? [] : list(state.knowledge_uses), publications = usesOnly ? [] : publication ? [publication] : list(state.knowledge_published);
    if (!uses.length && !publications.length) return '';
    return `<section class="au-forming-knowledge" aria-label="Procedure use and additions">${uses.map((use,index) => `<article class="au-knowledge-use" data-au-knowledge-use="${h(use.knowledge_sha256 || use.knowledge_id || use.version_id)}"><h3>${h(procedureLabel(use))}</h3><p>${operationDelivery ? 'Procedure reused' : 'Procedure used for this case'} · Version ${h(use.version || use.version_id)}</p>${knowledgeOriginMarkup(state,use,data,false,operationDelivery)}${knowledgeLink(use)}</article>`).join('')}${publications.map((item,index) => { const qualified = item.qualification?.status === 'qualified', links = `${qualified ? knowledgeLink(item) : ''}${inlineUses.map(use => `<p class="au-forming-used-version" data-au-knowledge-use="${h(use.knowledge_sha256 || use.knowledge_id || use.version_id)}">${knowledgeLink(use,`Used version ${use.version || use.version_id}`)}</p>`).join('')}`; return `<article class="au-knowledge-publication" data-au-knowledge-publication="${h(item.knowledge_sha256 || item.knowledge_id || item.candidate_id)}"><h3>${h(procedureLabel(item.candidate || item))}</h3><p>${qualified ? `${operationDelivery ? 'Historical addition' : 'Saved for reuse'} · Version ${h(item.version || item.version_id)}` : 'Not saved'}</p>${!qualified ? `<blockquote>${h(item.qualification?.reason || item.reason || 'No reason is recorded.')}</blockquote>` : ''}${publication ? links + knowledgeOriginMarkup(state,item,data,true) : ''}${qualified ? list(item.added_document_types).map(type => { const recipe = list(item.evidence_recipes).find(row => row.document_type === type), requirement = list(item.obligations).find(row => row.document_type === type); return `<p class="au-knowledge-change">Added ${h((name(requirement) || words(type)).toLocaleLowerCase())} requirements${list(recipe?.required_fields).length ? `: ${h(recipe.required_fields.map(field => words(field).toLocaleLowerCase()).join(', '))}` : ''}.</p>`; }).join('') : item.candidate?.summary ? `<p>Not saved. The recorded checks did not pass.</p>${recordButton('Details','publication',String(index))}` : ''}${!publication ? knowledgeOriginMarkup(state,item,data) + links : ''}</article>`; }).join('')}</section>`;
  }
  function formingPublication(state, events = [], attention) {
    // Attention is derived from a verified accepted delta, never the global index.
    const candidates = attention ? list(attention.acceptedEvents).filter(event => Number.isSafeInteger(attention.previousRevision) && event.seq > attention.previousRevision && event.seq <= attention.revision && list(attention.knowledgePublications).some(row => row.id === event.payload?.knowledge?.knowledge_sha256)) : events.filter(event => event.seq === state.revision);
    for (const event of [...candidates].reverse()) {
      if (!events.some(row => canonicalJSON(row) === canonicalJSON(event))) continue;
      const record = semanticEventRecord(state,event);
      if (record?.type === 'qualified') return record;
    }
    return null;
  }
  function formingRelations(state, selected, context = {}) {
    const relations = evidenceRelationships(state,selected,context);
    if (!relations.node || !relations.fact || state.graph?.family === 'incoming_packet') return null;
    const citation = citationRows(relations.fact).find(item => {
      const descriptor = list(state.source_descriptors).find(row => row.artifact_id === item.artifact_id), source = list(state.acquired_sources).find(row => row.artifact_id === item.artifact_id);
      if (!descriptor || !source || descriptor.sha256 !== source.sha256 || item.sha256 && item.sha256 !== descriptor.sha256 || item.text_sha256 && item.text_sha256 !== source.text_sha256 || typeof source.text !== 'string' || typeof item.quote !== 'string') return false;
      const chars = Array.from(source.text);
      return Number.isSafeInteger(item.start_char) && Number.isSafeInteger(item.end_char) && item.start_char >= 0 && item.end_char > item.start_char && item.end_char <= chars.length && chars.slice(item.start_char,item.end_char).join('') === item.quote;
    });
    if (!citation) return null;
    const obligation = relations.obligations.find(item => requirementIdentity(item) === requirementIdentity(relations.document) && list(item.required_fact_ids).includes(relations.fact.fact_id));
    return {fact:relations.fact.fact_id,source:citation.artifact_id,node:relations.node.node_id,obligation:obligation && formingRequirements(state).some(item => requirementIdentity(item) === requirementIdentity(obligation)) && requiringNodeReached(relations.evaluation,obligation,list(state.evaluation?.documents).find(row => row.document_type === obligation.document_type)) ? requirementIdentity(obligation) : null,citation};
  }
  function requiringNodeIds(item, document = {}) {
    const explicit = [...new Set([item.node_id,item.decision_node_id,...list(item.node_ids),...list(item.required_at_node_ids)].filter(Boolean))];
    return explicit.length ? explicit : list(document.required_at_node_ids).length ? document.required_at_node_ids : [item.decision_node_id].filter(Boolean);
  }
  function requiringNodeReached(node, item, document = {}) {
    if (node?.activation !== 'true') return false;
    const execution = node.execution_state || node.state;
    if (['ready','completed','complete','resolved','running','working'].includes(execution)) return (document.route_state || item.status) !== 'needed_later';
    // The active step may wait on its own missing evidence; upstream blocking
    // and unresolved dependencies still mean it has not been reached.
    return execution === 'blocked' && !list(node.blocked_by).length && !list(node.unresolved_dependencies).length && list(node.missing_document_types).includes(item.document_type);
  }
  function formingRequirements(state) {
    if (!state.graph || state.graph.family === 'incoming_packet') return [];
    const nodes = new Map(list(state.evaluation?.nodes).map(node => [node.node_id,node]));
    const documents = new Map(list(state.evaluation?.documents).map(doc => [doc.document_type,doc]));
    return list(state.obligations).filter(item => {
      const document = documents.get(item.document_type), route = document?.route_state || item.status;
      if (!document || document.activation !== 'true' || ['not_needed','inactive','excluded','held_behind_question','optional'].includes(route)) return false;
      return requiringNodeIds(item,document).some(id => requiringNodeReached(nodes.get(id),item,document));
    });
  }
  function enteredRequirementContext(before, after) {
    const previous = new Set(formingRequirements(before).map(requirementIdentity));
    const item = formingRequirements(after).find(row => !previous.has(requirementIdentity(row)));
    if (!item) return null;
    const document = list(after.evaluation?.documents).find(row => row.document_type === item.document_type);
    const node = requiringNodeIds(item,document).find(id => requiringNodeReached(list(after.evaluation?.nodes).find(row => row.node_id === id),item,document));
    return node ? {node,document:item.document_type,obligation:requirementIdentity(item),fact:list(item.required_fact_ids)[0]} : null;
  }
  function formingMarkup(state, projection, selected, events = [], context = {}, knowledge = {}, attention, settled = false, operations = null, chosen = null) {
    if (operations || settled) return operationStageMarkup(state,projection,selected,operations,settled,knowledge,{context,chosen});
    const activeRows = formingRequirements(state), workingState = workingProcessState(operations), working = workingState && operations.working;
    const processState = workingState || state, processSelected = working ? operationNodeId(operations.current,working.graph,state) || working.graph.nodes[0]?.node_id : selected;
    const publication = formingPublication(state,events,attention), node = list(processState.graph?.nodes).find(item => item.node_id === processSelected), relation = working ? null : formingRelations(state,selected,context), operationRelation = operationRelationship(operations,state);
    const evaluated = list(state.evaluation?.nodes).find(item => item.node_id === selected), capability = projection.node_capabilities?.[selected];
    const binding = relation ? ` data-au-wire-fact="${h(relation.fact)}" data-au-wire-source="${h(relation.source)}" data-au-wire-node="${h(relation.node)}"${relation.obligation ? ` data-au-wire-obligation="${h(relation.obligation)}"` : ''}` : '';
    const operationBinding = operationRelation ? ` data-au-operation-id="${h(operationRelation.operation_id)}" data-au-wire-source="${h(operationRelation.source)}" data-au-wire-node="${h(operationRelation.node)}" data-au-working-graph-sha="${h(operationRelation.graph_sha256)}"` : '';
    const documentOperation = working && operations.current?.kind === 'document.require' ? operations.current : null;
    const documentLabel = documentOperation && name(working.graph.document_catalog.find(row => row.document_type === documentOperation.object.id));
    const processHeading = working ? `<p class="au-reading-label">Steps awaiting checks ${recordButton('Inspect calculation','operation',working.inspect.id)}</p>` : publication ? `<div class="au-forming-publication-focus" data-au-publication-focus="${h(publication.id)}">${formingKnowledgeMarkup(state,knowledge,true,false,publication.knowledge,list(state.knowledge_uses),Boolean(operations))}</div>` : formingKnowledgeMarkup(state,knowledge,false,!settled,null,[],Boolean(operations));
    return `<section class="au-forming-work" data-au-forming="${!settled}"${settled ? ' data-au-settled="true"' : ''} data-au-forming-revision="${h(state.revision)}" data-au-forming-sha="${h(state.state_sha256)}"><div class="au-forming-layout"><div class="au-forming-reading">${!state.graph ? formingKnowledgeMarkup(state,knowledge,false,true,null,[],Boolean(operations)) : ''}${operationReadingMarkup(operations) || evidencePathMarkup(state,selected,projection,context,true)}${settled && evaluated ? `<div class="au-reading-decision"><p class="au-step-status">${h(statusLabel(evaluated.execution_state || evaluated.state))}</p>${capability?.authorized === false ? `<p class="au-reading-limit">${h(capability.reason || 'Execution is unavailable for this step.')}</p>` : ''}</div>` : ''}</div>${processState.graph ? `<section class="au-forming-process au-evidence-process" aria-label="${working ? 'Steps awaiting checks' : 'Complete recorded process'}"${working ? ` data-au-working-scope="${h(working.inspect.id)}" data-au-working-graph-sha="${h(working.graph.graph_sha256)}" data-au-operation-stage="${h(working.stage)}"` : ''}>${processHeading}${node && !publication ? `<h2 class="au-process-question au-reading-question" tabindex="-1"${working ? ` data-au-operation-id="${h(operations.current?.id || working.inspect.id)}"` : ` data-au-inspector-heading="${h(selected)}"`}>${h(name(node))}</h2>` : ''}${graphMarkup(processState,processSelected,working ? {} : projection,{overview:true,working})}${documentLabel ? `<p class="au-meta" data-au-working-document="${h(documentOperation.object.id)}" data-au-operation-id="${h(documentOperation.id)}">Requirement calculation · ${h(documentLabel)} ${recordButton('Inspect','operation',documentOperation.id)}</p>` : ''}</section>` : ''}${state.graph?.family !== 'incoming_packet' && list(state.obligations).length ? `<aside class="au-forming-documents" data-au-evidence-path aria-label="Recorded document requirements"><h2>Document requirements</h2>${activeRows.length ? obligationMarkup(state,selected,activeRows,context,true) : '<p>Requirements appear when their process step is reached.</p>'}${button('All recorded requirements','data-au-detail="documents"')}</aside>` : ''}<svg class="au-forming-connections" aria-hidden="true"${binding}>${operationRelation ? `<path data-au-forming-wire="operation-source-process"${operationBinding}></path>` : relation ? `<path data-au-forming-wire="source-process"${binding}></path>${relation.obligation ? `<path data-au-forming-wire="process-document"${binding}></path>` : ''}` : ''}</svg></div></section>`;
  }
  function conditionLabel(state, expression) {
    const positive = {arrears:'Rent arrears',family_home:'Family home',extension_relevant:'Tenancy extension'};
    const negative = {arrears:'No rent arrears',family_home:'Not a family home',extension_relevant:'No tenancy extension'};
    const constant = value => value === true || value === 'true' ? 'Always' : value === false || value === 'false' ? 'Never' : 'Unresolved condition';
    const render = (value, nested = false) => {
      if (!value || typeof value !== 'object') return '';
      if (Object.prototype.hasOwnProperty.call(value,'const')) return nested ? constant(value.const) : '';
      if (value.flag) {
        const fact = list(state.facts).find(item => item.fact_id === `condition:${value.flag}` || item.flag === value.flag);
        return positive[value.flag] || name(fact) || words(value.flag);
      }
      if (value.not) {
        if (value.not.flag) return negative[value.not.flag] || `Not (${render(value.not,true)})`;
        if (value.not.not) return render(value.not.not,nested);
        if (Object.prototype.hasOwnProperty.call(value.not,'const')) { const label=constant(value.not.const);return label==='Always'?'Never':label==='Never'?'Always':label; }
        return `Not (${render(value.not,true)})`;
      }
      const children = value.all || value.any;
      if (!children) return '';
      return list(children).map(child => {
        const label=render(child,true);
        return child.all || child.any ? `(${label})` : label;
      }).map((label,index) => index && /^(No |Not a )/.test(label) ? label[0].toLocaleLowerCase()+label.slice(1) : label).join(value.all ? ' and ' : ' or ');
    };
    return render(expression);
  }
  const routeLabel = value => ['true','applied','active'].includes(value) ? 'Applies' : ['false','excluded','inactive'].includes(value) ? 'Excluded' : 'Unresolved';
  // One visible state per step, read from the returned evaluation: done (✓)
  // only for a completion the evaluation accepts; review (!) for a recorded
  // completion it flags as inconsistent (a prerequisite, condition or document
  // is still open, so the API asks to review the completed step); active (ring
  // with a dot: applies, not done); open (empty ring: unresolved); inactive
  // (dashed ring: not activated or excluded).
  const DONE_NODE_STATES = ['completed','complete','resolved','established','satisfied'];
  function graphNodeState(evaluated = {}) {
    const execution = evaluated.execution_state || evaluated.state;
    if (evaluated.inconsistent_completion === true && !['completed','provisional','planned'].includes(execution)) return 'review';
    if (DONE_NODE_STATES.includes(execution)) return 'done';
    if (['false','excluded','inactive'].includes(evaluated.activation)) return 'inactive';
    return ['true','applied','active'].includes(evaluated.activation) ? 'active' : 'open';
  }
  const NODE_REVIEW_LABEL = 'Marked complete, needs review';
  const GRAPH_LEGEND = [['done','✓','completed','completed'],['review','!','marked complete, needs review','marked complete, need review'],['active','','applies, not done','apply, not done'],['open','','unresolved','unresolved'],['inactive','','does not apply','do not apply']];
  function graphLegendMarkup(states) {
    const rows = GRAPH_LEGEND.filter(([id]) => states.includes(id)).map(([id,glyph,one,many]) => { const count = states.filter(row => row === id).length; return `<li class="au-graph-legend-item" data-au-node-state="${id}"><span class="au-evidence-junction" aria-hidden="true">${glyph}</span>${count} ${count === 1 ? one : many}</li>`; });
    return rows.length ? `<ul class="au-graph-legend" role="list" aria-label="Step states">${rows.join('')}</ul>` : '';
  }
  function stageName(item) {
    const label = recordedName(item).replace(/^(?:Check|Read|Capture|Establish|Assess|Record)(?: the)?\s+/iu,'');
    return label ? label.charAt(0).toLocaleUpperCase('en')+label.slice(1) : recordedName(item);
  }
  function graphMarkup(state, selected, projection = {}, options = {}) {
    if (!state.graph) return '';
    const layout = layoutGraph(state.graph), neighborhood = new Set([selected,...(layout.parents.get(selected) || []),...(layout.children.get(selected) || [])]), evaluation = new Map(list(state.evaluation?.nodes).map(node => [node.node_id,node]));
    const acceptedNode = id => options.stage && options.working && options.working.graph.graph_sha256 === options.stage.state.graph?.graph_sha256 ? list(options.stage.state.evaluation?.nodes).find(row => row.node_id === id) : null;
    const nodeStatus = id => { const evaluated = evaluation.get(id) || {}; return options.stage?.planned ? 'planned' : acceptedNode(id)?.execution_state === 'completed' ? 'completed' : options.working ? 'provisional' : evaluated.execution_state || evaluated.state || 'pending'; };
    const nodeStates = new Map(layout.nodes.map(node => [node.node_id,options.stage?.planned ? 'planned' : graphNodeState({...(evaluation.get(node.node_id) || {}),execution_state:nodeStatus(node.node_id)})]));
    const legend = options.stage || options.overview ? '' : graphLegendMarkup([...nodeStates.values()]);
    return `<div class="au-graph-chrome"><button type="button" class="au-link" data-au-expand-process aria-expanded="false" aria-controls="auProcessGraphViewport">${options.overview ? 'Open all steps' : 'Open all steps'}</button></div><div id="auProcessGraphViewport" class="au-graph-viewport au-evidence-graph-scroll" data-au-graph-pan data-au-graph-overview="${Boolean(options.overview)}" data-au-graph-expanded="false" role="group" aria-label="${options.overview ? 'All steps' : 'Nearby steps'}"><div class="au-graph au-evidence-graph" data-au-graph${options.working ? ` data-au-working-graph-sha="${h(options.working.graph.graph_sha256)}" data-au-working-scope="${h(options.working.inspect.id)}" data-au-working-evaluation-sha="${h(options.working.inspect.result.evaluation_sha256)}" data-au-operation-stage="${h(options.working.stage)}"` : ''} data-orientation="${options.stage ? 'horizontal' : options.overview ? 'vertical' : 'horizontal'}" style="--au-ranks:${Math.max(1,layout.rows.length)}"><svg class="au-graph-lines" aria-hidden="true"><defs>${['true','false','unresolved'].map(value => `<marker id="au-process-arrow-${value}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path class="au-process-arrow" data-route="${value}" d="M1 1 L9 5 L1 9 Z" /></marker>`).join('')}</defs>${layout.edges.map(edge => `<path data-au-edge="${h(edge.edge_id)}" data-au-edge-source="${h(edge.source_node_id)}" data-au-edge-target="${h(edge.target_node_id)}" data-au-neighborhood="${neighborhood.has(edge.source_node_id) && neighborhood.has(edge.target_node_id)}" data-state="${h(edgeState(state,edge.edge_id))}" marker-end="url(#au-process-arrow-${edgeState(state,edge.edge_id) === 'true' ? 'true' : ['false','excluded'].includes(edgeState(state,edge.edge_id)) ? 'false' : 'unresolved'})" data-selected="${edge.source_node_id === selected || edge.target_node_id === selected}"><title>${h(plain(edge.label || edge.relation,'Step connection'))} · ${h(options.stage ? routeLabel(edgeState(state,edge.edge_id)) : options.working ? `When this applies: ${routeLabel(edgeState(state,edge.edge_id))}` : statusLabel(edgeState(state,edge.edge_id)))}</title></path>`).join('')}</svg>${layout.rows.map((row,rank) => `<div class="au-graph-rank" data-rank="${rank}" data-au-neighborhood="${row.some(node => neighborhood.has(node.node_id))}">${row.map(node => {
      const evaluated = evaluation.get(node.node_id) || {}, accepted = acceptedNode(node.node_id), status = nodeStatus(node.node_id), nodeState = nodeStates.get(node.node_id), inspection = options.working?.nodes.get(node.node_id) || options.working?.inspect;
      const parents = layout.parents.get(node.node_id).map(id => name(layout.byId.get(id)));
      const incoming = layout.edges.filter(edge => edge.target_node_id === node.node_id);
      const conditional = incoming.filter(edge => conditionLabel(state,edge.condition) || ['blocks','invalidates','supersedes'].includes(edge.relation));
      const labels = conditional.map(edge => `<span class="au-node-condition" data-au-edge-label="${h(edge.edge_id)}" data-state="${h(edgeState(state,edge.edge_id))}">${h(conditionLabel(state,edge.condition) || plain(edge.label || words(edge.relation),'Recorded path'))}<span>${h(routeLabel(edgeState(state,edge.edge_id)))}</span></span>`).join('');
      const ownCondition = !conditional.length && !incoming.length && conditionLabel(state,node.condition);

      const visibleStatus = options.working ? evaluated.activation && (selected === node.node_id || evaluated.activation === 'false') ? `When it applies · ${routeLabel(evaluated.activation)}` : '' : nodeState === 'review' ? NODE_REVIEW_LABEL : ['false','excluded'].includes(evaluated.activation) && !conditional.length ? 'Does not apply' : selected === node.node_id && ['completed','complete','resolved','ready','blocked','running','working','queued','paused','failed','deferred'].includes(status) ? statusLabel(status) : '';
      const readiness = options.working && selected === node.node_id ? workingReadiness(evaluated,state.graph) : '';
      const nodeHTML = `<button type="button" class="au-node au-evidence-node" data-au-node="${h(node.node_id)}"${options.stage?.planned ? ' data-au-planned-node disabled' : ''}${inspection ? ` data-au-inspect="operation" data-au-record-id="${h(inspection.id)}" data-au-operation-id="${h(inspection.id)}" data-au-working-graph-sha="${h(options.working.graph.graph_sha256)}" data-au-working-scope="${h(options.working.inspect.id)}" data-au-working-evaluation-sha="${h(options.working.inspect.result.evaluation_sha256)}" data-au-operation-stage="${h(options.working.stage)}"` : ''} data-au-neighborhood="${neighborhood.has(node.node_id)}" data-status="${h(status)}" data-activation="${h(evaluated.activation || 'unresolved')}" data-au-node-state="${nodeState}" aria-pressed="${selected === node.node_id}" aria-label="${h(options.stage ? stageName(node) || 'Recorded step' : name(node))}. ${h(options.stage ? options.stage.planned ? 'Planned step; source support is not yet assessed' : status === 'completed' ? 'Completed' : options.working ? 'Awaiting verification' : 'Awaiting source support' : options.working ? evaluated.activation ? `When this applies: ${routeLabel(evaluated.activation)}${readiness ? `. ${readiness}` : ''}` : 'Step awaiting a check' : statusLabel(status))}${nodeState === 'review' ? '. Marked complete; needs review' : ''}"><span class="au-node-index au-evidence-junction" data-au-junction="${h(node.node_id)}" aria-hidden="true">${nodeState === 'done' ? '✓' : nodeState === 'review' ? '!' : ''}</span><span class="au-node-copy"><span class="au-node-relation"${neighborhood.has(node.node_id) ? '' : ' hidden'}>${neighborhood.has(node.node_id) ? node.node_id === selected ? 'This decision' : layout.parents.get(selected)?.includes(node.node_id) ? 'Before' : 'Then' : ''}</span>${options.stage ? '' : labels}${ownCondition && !options.stage ? `<span class="au-node-condition" data-au-node-condition="${h(node.node_id)}">${h(ownCondition)}<span>${h(routeLabel(evaluated.activation))}</span></span>` : ''}<strong class="au-node-title">${h(options.stage ? stageName(node) || 'Recorded step' : name(node))}</strong>${visibleStatus && !options.stage ? `<span class="au-node-state">${h(visibleStatus)}</span>` : ''}${readiness && !options.stage ? `<span class="au-node-state" data-au-working-readiness>${h(readiness)}</span>` : ''}</span></button>`;
      return options.stage ? `<div class="au-stage-step" data-au-stage-step="${h(node.node_id)}" data-au-stage-active="${selected === node.node_id}" data-au-stage-complete="${nodeState === 'done'}">${nodeHTML}${selected === node.node_id && options.stage.excerpt ? `<div class="au-forming-reading au-stage-source">${options.stage.excerpt}</div>` : ''}${stageNodeContents(node,options.stage.state,options.stage.trace,options.working,options.stage.map,options.stage.planned ? state.graph : null,options.stage.reuse)}</div>` : nodeHTML;
    }).join('')}</div>`).join('')}</div></div>${legend}`;
  }

  function obligationMarkup(state, selected, suppliedRows, context = {}, forming = false) {
    const documents = new Map(list(state.evaluation?.documents).map(doc => [doc.document_type,doc]));
    const rows = suppliedRows || list(state.obligations).concat(list(state.evaluation?.documents).filter(doc => !list(state.obligations).some(item => item.document_type === doc.document_type)));
    if (!rows.length) return '<p class="au-empty">No document requirements have been recorded.</p>';
    if (!forming) return documentChecklistMarkup(state,rows,documents,context);
    return `<ul class="au-obligations">${rows.map(obligation => {
      const doc = documents.get(obligation.document_type) || {}, nodes = requiringNodeIds(obligation,doc);
      const requiring = nodes.find(id => list(state.graph?.nodes).some(node => node.node_id === id) && (!forming || requiringNodeReached(list(state.evaluation?.nodes).find(node => node.node_id === id),obligation,doc))), fact = list(obligation.required_fact_ids).find(id => list(state.facts).some(row => row.fact_id === id));
      const status = doc.route_state || obligation.status || 'pending', identity = requirementIdentity(obligation);
      const selection = requiring ? `data-au-select="${h(requiring)}" data-au-select-document="${h(obligation.document_type)}" data-au-select-obligation="${h(identity)}" data-au-select-fact="${h(fact || '')}"` : `data-au-inspect="requirement" data-au-record-id="${h(identity)}"`;
      const citations = list(obligation.required_fact_ids).flatMap(id => citationRows(list(state.facts).find(row => row.fact_id === id)));
      const reviewed = ['sufficient','insufficient'].includes(doc.review_state);
      const evidence = forming && reviewed ? citations.filter((citation,index) => citations.findIndex(row => row.artifact_id === citation.artifact_id) === index).map(citation => `<button type="button" class="au-link au-document-source" data-au-source="${h(citation.artifact_id)}" data-au-source-origin="requirement:${h(identity)}" data-au-citation="${h(JSON.stringify(citation))}">Source evidence · ${h(sourceLabel(state,citation.artifact_id))}</button>`).join('') : '';
      return `<li class="au-obligation" data-au-obligation="${h(identity)}" data-au-document="${h(obligation.document_type)}" data-status="${h(status)}"${context.obligation === identity ? ' data-selected="true"' : ''}><button type="button" class="au-document-open au-document-choice" ${selection}><strong>${h(name(obligation) || name(doc))}</strong>${!forming || ['needed_now','established','satisfied'].includes(status) ? `<span class="au-document-state au-document-route">${h(statusLabel(status))}.</span>` : ''}${!forming || reviewed ? documentReviewMarkup(doc.review_state) : ''}${requiring ? `<span class="au-document-decision">${h(name(list(state.graph?.nodes).find(node => node.node_id === requiring)))}</span>` : ''}</button>${evidence}</li>`;
    }).join('')}</ul>`;
  }
  // The full checklist reads causally: each row states its recorded route and
  // the step it belongs to, and that step's name selects it. A sufficient
  // review is said once ("Supplied") instead of beside a contradicting route.
  const DOCUMENT_ROUTE_COPY = {needed_now:['Missing','needed now for'],needed_later:['Needed later','waiting on'],held_behind_question:['May be needed','depends on'],held_not_reviewed:['Needs checking','for'],optional:['Optional','for'],not_needed:['Not needed','',' does not need it'],established:['Established','for'],satisfied:['Established','for']};
  const SUPPLIED_ROUTES = ['established','satisfied','held_behind_question','needed_later','optional'];
  function documentRouteGroup(route, review) {
    if (route === 'needed_now') return 'now';
    if (['established','satisfied'].includes(route) || review === 'sufficient' && SUPPLIED_ROUTES.includes(route)) return 'supplied';
    // A requirement held behind an open question is counted as it reads, "may be needed",
    // not as certain and merely waiting on its step.
    if (route === 'needed_later') return 'waiting';
    if (route === 'held_behind_question') return 'maybe';
    return route === 'held_not_reviewed' ? 'checking' : route === 'optional' ? 'optional' : route === 'not_needed' ? 'not_needed' : 'other';
  }
  function documentCountLine(groups) {
    const count = group => groups.filter(row => row === group).length;
    const extras = [['checking','to check'],['optional','optional'],['not_needed','not needed'],['other','without a recorded route']].filter(([group]) => count(group)).map(([group,label]) => `${count(group)} ${label}`);
    return [`${count('supplied')} of ${groups.length-count('not_needed')} received`,`${count('now')} missing`,`${count('waiting')} waiting on a step`,...count('maybe') ? [`${count('maybe')} may be needed`] : [],...extras].join(' · ');
  }
  function documentChecklistMarkup(state, rows, documents, context = {}) {
    const nodes = list(state.graph?.nodes), groups = [];
    const items = rows.map(obligation => {
      const doc = documents.get(obligation.document_type) || {}, identity = requirementIdentity(obligation), route = doc.route_state || obligation.status || 'pending', review = doc.review_state;
      const requiring = requiringNodeIds(obligation,doc).find(id => nodes.some(node => node.node_id === id)), fact = list(obligation.required_fact_ids).find(id => list(state.facts).some(row => row.fact_id === id));
      const supplied = review === 'sufficient' && SUPPLIED_ROUTES.includes(route), group = documentRouteGroup(route,review), label = name(obligation) || name(doc) || words(obligation.document_type);
      groups.push(group);
      const [state_, connector, suffix = ''] = supplied ? ['Received','sufficient for'] : DOCUMENT_ROUTE_COPY[route] || [statusLabel(route),'for'];
      const stepName = requiring ? stageName(nodes.find(node => node.node_id === requiring)) : '';
      // The connector travels inside the step control, so a narrow line never ends on a dangling
      // "depends on"; on phones the control takes its own line under the route.
      const stepWords = [connector,stepName,suffix.trim()].filter(Boolean).join(' ');
      const step = requiring ? `<span class="au-document-sep"> · </span><button type="button" class="au-link au-document-step" data-au-select="${h(requiring)}" data-au-select-document="${h(obligation.document_type)}" data-au-select-obligation="${h(identity)}" data-au-select-fact="${h(fact || '')}" aria-label="${h(stepWords)} (step for ${h(label)})">${connector ? `<span class="au-document-connector">${h(connector)}</span> ` : ''}<span class="au-document-step-name">${h(stepName)}</span>${suffix ? ` <span class="au-document-connector">${h(suffix.trim())}</span>` : ''}</button>` : '.';
      const routeLine = `<span class="au-document-state au-document-route" data-route="${h(route)}"${supplied ? ' data-au-review="sufficient"' : ''}><span class="au-document-route-label">${h(state_)}</span>${supplied ? ' <span aria-hidden="true">✓</span>' : ''}${step}</span>`;
      // A missing review adds nothing beside a route that already says the
      // document is not in hand, except where it is needed now.
      const reviewLine = supplied || !review || ['missing','unreviewed','unresolved'].includes(review) && route !== 'needed_now' ? '' : documentReviewMarkup(review);
      const title = requiring ? `<strong class="au-document-name">${h(label)}</strong>` : `<button type="button" class="au-link au-document-name au-document-record" data-au-inspect="requirement" data-au-record-id="${h(identity)}">${h(label)}</button>`;
      return `<li class="au-obligation" data-au-obligation="${h(identity)}" data-au-document="${h(obligation.document_type)}" data-status="${h(route)}" data-au-route-group="${group}"${context.obligation === identity ? ' data-selected="true" aria-current="true"' : ''}><div class="au-document-row">${title}${routeLine}${reviewLine}</div></li>`;
    });
    return `<p class="au-document-count" data-au-document-count>${h(documentCountLine(groups))}</p><ul class="au-obligations au-document-checklist">${items.join('')}</ul>`;
  }

  function actionInstanceIdentity(action, receipt = {}, index = 0, entry = {}) {
    const logical = action.action_id || name(action) || 'recorded-action';
    const binding = receipt.receipt_sha256 ? `receipt:${receipt.receipt_sha256}` : `record:${JSON.stringify([receipt.parent_revision ?? null,receipt.parent_state_sha256 ?? null,receipt.workflow_id || entry.workflow_id || action.workflow_id || null,receipt.run_id || entry.run_id || action.run_id || null,index])}`;
    return `${logical}:${binding}`;
  }
  function actionRows(state, events = []) {
    let start = null;
    const runId = typeof state.run_id === 'string' && state.run_id.trim() ? state.run_id : null;
    if (runId) for (const event of events) if (event.kind === 'work.started' && event.payload?.run_id === runId) start = event.seq;
    return list(state.actions).map((entry,index) => {
      const result = entry.result || entry, receipt = entry.receipt || {};
      const revision = receipt.parent_revision;
      const scope = Number.isSafeInteger(start) && Number.isSafeInteger(revision) ? revision >= start ? 'current' : 'historical' : 'unassociated';
      return {result, receipt, scope,instanceId:actionInstanceIdentity(result,receipt,index,entry)};
    });
  }
  function actionMarkup(state, rows) {
    return rows.map(({result:action,receipt,scope,instanceId},index) => `<article class="au-action" data-au-action-scope="${scope}"><div class="au-action-heading"><strong>${h(name(action))}</strong><span>${h(statusLabel(action.status))}</span></div><p class="au-meta">${scope === 'current' ? 'Recorded in this run' : scope === 'historical' ? 'Recorded in an earlier run' : 'Recorded action · run association not recorded'}</p><p>${h(action.summary || action.reason || '')}</p>${sourceButtons(state,action,`action:${instanceId || actionInstanceIdentity(action,receipt,index)}`)}${Object.keys(receipt).length ? `<details class="au-receipt" data-au-disclosure="action:${h(instanceId || actionInstanceIdentity(action,receipt,index))}"><summary>Details</summary>${Number.isSafeInteger(receipt.parent_revision) ? `<p>Recorded after revision ${h(receipt.parent_revision)}.</p>` : ''}${receipt.operation ? `<p>${h(words(receipt.operation))}</p>` : ''}<pre class="au-record-body">${h(JSON.stringify(receipt,null,2))}</pre></details>` : ''}<details class="au-technical-record" data-au-disclosure="action-record:${h(instanceId || actionInstanceIdentity(action,receipt,index))}"><summary>Details</summary><pre class="au-record-body">${h(JSON.stringify({result:action,receipt,scope},null,2))}</pre></details></article>`).join('') || '<p class="au-empty">No action result recorded for this step.</p>';
  }
  function semanticEventRecord(state, event) {
    if (!event || event.claim_id !== state.claim_id || !Number.isSafeInteger(event.seq) || event.seq < 1 || event.seq > state.revision || !isHash(event.event_sha256) || eventIdentity(event).revision !== event.seq || !isHash(eventIdentity(event).state_sha256)) return null;
    if (event.seq === state.revision && (eventIdentity(event).state_sha256 !== state.state_sha256 || state.last_event_sha256 && event.event_sha256 !== state.last_event_sha256)) return null;
    const payload = event.payload || {}, base = {id:event.event_sha256,seq:event.seq,kind:event.kind};
    const same = (left,right) => canonicalJSON(left) === canonicalJSON(right);
    const citations = item => citationRows(item).filter(citation => {
      const descriptor = list(state.source_descriptors).find(source => source.artifact_id === citation.artifact_id), acquired = list(state.acquired_sources).find(source => source.artifact_id === citation.artifact_id);
      return descriptor && acquired && descriptor.sha256 === acquired.sha256 && (!citation.sha256 || citation.sha256 === descriptor.sha256) && (!citation.text_sha256 || citation.text_sha256 === acquired.text_sha256) && typeof citation.quote === 'string' && citation.quote.length > 0 && typeof acquired.text === 'string' && acquired.text.includes(citation.quote);
    });
    if (event.kind === 'action.completed') {
      const action = list(state.actions).find(entry => same(entry.result || entry,payload.result) && same(entry.receipt || {},payload.receipt));
      const result = payload.result, receipt = payload.receipt;
      if (!action || !result?.action_id || result.status !== 'completed' || !isHash(receipt?.receipt_sha256) || receipt.parent_revision !== event.seq-1 || !isHash(receipt.parent_state_sha256)) return null;
      const nodes = [...new Set([result.node_id,...list(result.node_ids)].filter(id => list(state.graph?.nodes).some(node => node.node_id === id)))];
      return {...base,type:'action',label:'Action completed',title:name(result),summary:result.summary || result.reason || '',nodes,citations:citations(result),record:{result,receipt},itemId:actionInstanceIdentity(result,receipt)};
    }
    const knowledge = payload.knowledge;
    if (!knowledge || !knowledge.knowledge_id) return null;
    if (event.kind === 'knowledge.used') {
      if (!list(state.knowledge_uses).some(item => same(item,knowledge)) || !Number.isSafeInteger(knowledge.version) || knowledge.version < 1 || !isHash(knowledge.knowledge_sha256 || knowledge.definition_sha256)) return null;
      return {...base,type:'reused',label:'Saved steps reused',title:`${words(knowledge.knowledge_id)} · version ${knowledge.version}`,summary:knowledge.reason || words(typeof knowledge.applicability === 'string' ? knowledge.applicability : knowledge.applicability?.summary),knowledge,citations:[],record:knowledge,itemId:`${knowledge.knowledge_id}:${knowledge.version}:${knowledge.knowledge_sha256 || knowledge.definition_sha256}`};
    }
    if (event.kind !== 'knowledge.published' || !list(state.knowledge_published).some(item => same(item,knowledge))) return null;
    const status = knowledge.qualification?.status;
    if (status !== 'qualified' && status !== 'quarantined' || knowledge.source_claim_id && knowledge.source_claim_id !== state.claim_id) return null;
    if (status === 'qualified' && (!Number.isSafeInteger(knowledge.version) || knowledge.version < 1 || !isHash(knowledge.knowledge_sha256))) return null;
    const supporting = [...citationRows(knowledge),...citationRows(knowledge.candidate),...list(knowledge.source_evidence).flatMap(item => item.artifact_id && item.quote ? [item] : citationRows(item))];
    return {...base,type:status === 'qualified' ? 'qualified' : 'withheld',label:status === 'qualified' ? 'Steps saved for reuse' : 'Not saved',title:status === 'qualified' ? `${name(knowledge) || words(knowledge.knowledge_id)} · version ${knowledge.version}` : name(knowledge.candidate) || words(knowledge.knowledge_id),summary:knowledge.qualification?.reason || knowledge.qualification?.summary || knowledge.summary || knowledge.candidate?.summary || '',knowledge,citations:citations({citations:supporting}),record:knowledge,itemId:knowledge.knowledge_sha256 || knowledge.knowledge_id};
  }
  function lastSemanticEvent(state, history = []) {
    for (const event of [...history].sort((a,b) => b.seq-a.seq)) {
      const record = semanticEventRecord(state,event);
      if (record) return record;
    }
    return null;
  }
  function semanticEventMarkup(state, history = []) {
    const record = lastSemanticEvent(state,history);
    if (!record) return '';
    const sourceLinks = record.citations.map(citation => button(sourceLabel(state,citation.artifact_id),`data-au-source="${h(citation.artifact_id)}" data-au-citation="${h(JSON.stringify(citation))}" data-au-source-origin="semantic:${h(record.id)}"`));
    const nodes = list(record.nodes).map(id => button(name(list(state.graph?.nodes).find(node => node.node_id === id)),`data-au-select="${h(id)}"`));
    const version = record.knowledge && record.type !== 'withheld' ? button('Inspect exact version',`data-au-knowledge="${h(record.knowledge.knowledge_id)}" data-au-version="${h(record.knowledge.version)}" data-au-knowledge-sha="${h(record.knowledge.knowledge_sha256 || '')}" data-au-definition-sha="${h(record.knowledge.definition_sha256 || '')}"`) : '';
    return `<aside class="au-semantic-event" data-au-semantic-event="${h(record.id)}" data-au-semantic-kind="${h(record.kind)}" data-au-semantic-seq="${record.seq}" data-au-semantic-type="${record.type}" aria-label="Last recorded action or knowledge event"><span class="au-semantic-symbol" aria-hidden="true">${record.type === 'reused' ? '↺' : record.type === 'withheld' ? '·' : '✓'}</span><div data-au-semantic-item="${h(record.itemId)}"><p class="au-eyebrow">Last recorded · ${h(record.label)} · revision ${record.seq}</p><strong>${h(record.title)}</strong>${record.summary ? `<p class="au-semantic-summary">${h(record.summary)}</p>` : ''}<div class="au-related">${nodes.join('')}${sourceLinks.slice(0,2).join('')}${version}</div><details class="au-semantic-receipt" data-au-disclosure="semantic:${h(record.id)}"><summary>Inspect recorded ${record.type === 'action' ? 'action' : 'knowledge'}</summary>${sourceLinks.slice(2).join('')}<pre class="au-record-body">${h(JSON.stringify({revision:record.seq,event_sha256:record.id,...record.type === 'action' ? record.record : {knowledge:record.record}},null,2))}</pre></details></div></aside>`;
  }
  function assessmentFreshness(state) {
    const receipt = [...list(state.receipts)].reverse().find(item => item.kind === 'interpretation.accepted')?.receipt;
    const context = receipt?.workflow_id && state.semantic_contexts?.[receipt.workflow_id];
    if (!receipt || !isHash(receipt.receipt_sha256) || !context || context.claim_id !== state.claim_id || !Array.isArray(context.sources)) return {status:'unavailable',sources:[]};
    const valid = sources => sources.every(source => typeof source.artifact_id === 'string' && isHash(source.sha256)) && new Set(sources.map(source => source.artifact_id)).size === sources.length;
    const current = currentSourceSelection(state);
    if (!valid(context.sources) || !valid(current)) return {status:'unavailable',sources:[]};
    const accepted = new Map(context.sources.map(source => [source.artifact_id,source.sha256]));
    const sources = current.filter(source => accepted.get(source.artifact_id) !== source.sha256);
    const changed = sources.length > 0 || accepted.size !== current.length;
    return {status:changed ? 'prior' : 'current',sources,workflow_id:receipt.workflow_id};
  }
  function assessmentFreshnessMarkup(state) {
    const freshness = assessmentFreshness(state);
    if (freshness.status !== 'prior') return '';
    return `<aside class="au-assessment-freshness" data-au-assessment-freshness="prior"><strong>Prior assessment</strong><span>${freshness.sources.length ? `${freshness.sources.length} new source${freshness.sources.length === 1 ? '' : 's'} awaiting assessment` : 'The source roster has changed'}. The recorded facts and requirements reflect the earlier evidence.</span><div class="au-related">${freshness.sources.map(source => button(source.file_name || 'New source',`data-au-source="${h(source.artifact_id)}" data-au-source-origin="unassessed:${h(source.artifact_id)}"`)).join('')}</div></aside>`;
  }
  function routeMarkup(state, selected) {
    const nodes = new Map(list(state.graph?.nodes).map(node => [node.node_id,node]));
    const edges = list(state.graph?.edges).filter(edge => edge.target_node_id === selected || edge.source_node_id === selected);
    const evaluation = new Map(list(state.evaluation?.edges).map(edge => [edge.edge_id,edge]));
    const currentNode = list(state.evaluation?.nodes).find(node => node.node_id === selected);
    const expression = nodes.get(selected)?.condition;
    const condition = value => {
      if (!value || typeof value !== 'object') return '';
      if (Object.prototype.hasOwnProperty.call(value,'const')) return h(statusLabel(value.const));
      if (value.flag) { const fact = list(state.facts).find(item => item.fact_id === `condition:${value.flag}` || item.flag === value.flag); return `${h(name(fact) || words(value.flag))}: ${h(statusLabel(fact?.verdict || fact?.status))}`; }
      if (value.not) return `Not (${condition(value.not)})`;
      if (value.all) return list(value.all).map(condition).join(' and ');
      if (value.any) return list(value.any).map(condition).join(' or ');
      return '';
    };
    return `<details class="au-step-route" data-au-disclosure="route:${h(selected)}"><summary>Details <span>${edges.length} connections</span></summary>${expression ? `<p class="au-branch-condition">Recorded condition: ${condition(expression) || 'No condition detail recorded'}.</p>` : ''}${currentNode?.activation ? `<p>When this applies: ${h(statusLabel(currentNode.activation))}.</p>` : ''}<ul class="au-step-relations">${edges.map(edge => {
      const incoming = edge.target_node_id === selected, other = incoming ? edge.source_node_id : edge.target_node_id, view = evaluation.get(edge.edge_id);
      const relation = edge.relation ? words(edge.relation) : incoming ? 'Follows' : 'Leads to';
      return `<li data-au-relation="${h(edge.relation || 'recorded_connection')}" data-au-edge-status="${h(view?.activation || view?.condition_verdict || 'unknown')}"><span>${h(incoming ? 'From' : 'To')} ${h(name(nodes.get(other)) || words(other))} · ${h(relation)}${view?.activation || view?.condition_verdict ? ` · ${h(statusLabel(view.activation || view.condition_verdict))}` : ''}</span>${edge.condition ? `<p>${condition(edge.condition)}</p>` : ''}${button('Inspect connected step',`data-au-select="${h(other)}"`)}</li>`;
    }).join('') || '<li>No process connection recorded for this step.</li>'}</ul></details>`;
  }
  function evidenceRelationships(state, selected, context = {}) {
    const node = list(state.graph?.nodes).find(item => item.node_id === selected);
    const relates = item => item.node_id === selected || item.decision_node_id === selected || list(item.node_ids).includes(selected) || list(item.required_at_node_ids).includes(selected);
    const obligations = list(state.obligations).filter(relates), incoming = list(state.graph?.edges).filter(edge => edge.target_node_id === selected);
    const conditionIds = new Set(conditionFlags(node?.condition).concat(incoming.flatMap(edge => conditionFlags(edge.condition))).map(flag => `condition:${flag}`));
    const ids = new Set([...obligations.flatMap(item => list(item.required_fact_ids)),...conditionIds]);
    const facts = list(state.facts).filter(item => ids.has(item.fact_id) || relates(item)).sort((a,b) => Number(b.fact_id?.startsWith('condition:')) - Number(a.fact_id?.startsWith('condition:')));
    const evaluated = list(state.evaluation?.documents).filter(relates);
    // An obligation is the causal identity. Two obligations may require the same
    // document at one step while depending on different facts.
    const documents = obligations.map(item => ({...item,...list(state.evaluation?.documents).find(doc => doc.document_type === item.document_type),obligation_id:item.obligation_id,required_fact_ids:list(item.required_fact_ids)}));
    for (const item of evaluated) if (!documents.some(doc => doc.document_type === item.document_type)) documents.push({...item});
    const document = documents.find(item => requirementIdentity(item) === context.obligation && (!context.document || item.document_type === context.document)) || documents.find(item => item.document_type === context.document) || documents[0];
    const explicitRequirement = Boolean(context.obligation || context.document);
    const compatible = fact => !explicitRequirement || list(document?.required_fact_ids).includes(fact.fact_id) || conditionIds.has(fact.fact_id);
    const fact = facts.find(item => item.fact_id === context.fact && compatible(item)) || (explicitRequirement ? list(document?.required_fact_ids).map(id => facts.find(item => item.fact_id === id)).find(Boolean) || facts.find(item => conditionIds.has(item.fact_id)) : facts.find(item => citationRows(item).length) || facts[0]);
    return {node,obligations,incoming,facts,documents,fact,document,evaluation:list(state.evaluation?.nodes).find(item => item.node_id === selected) || {}};
  }
  const requirementIdentity = item => item?.obligation_id || `document:${item?.document_type || ''}`;
  function evidenceSelection(state, selected, context = {}) {
    const relationships = evidenceRelationships(state,selected,context), result = {};
    if (context.document || context.obligation) {
      if (relationships.document) Object.assign(result,{document:relationships.document.document_type,obligation:requirementIdentity(relationships.document)});
    }
    if (relationships.fact && (context.fact || context.document || context.obligation)) result.fact = relationships.fact.fact_id;
    if (context.trace && result.fact === context.fact) result.trace = true;
    return result;
  }
  function factRecordMarkup(state, fact) {
    return `<article class="au-fact" data-au-fact="${h(fact.fact_id)}"><strong>${h(name(fact) || words(fact.flag))}</strong><span>${h(statusLabel(fact.verdict || fact.status))}</span>${fact.summary || fact.reason ? `<details><summary>Details</summary><p>${h(fact.summary || fact.reason)}</p></details>` : ''}${sourceButtons(state,fact)}${['unresolved','unknown','insufficient'].includes(fact.verdict || fact.status) ? button('Add evidence','data-au-add-files') : ''}<details class="au-technical-record" data-au-disclosure="fact-record:${h(fact.fact_id)}"><summary>Details</summary><pre class="au-record-body">${h(JSON.stringify(fact,null,2))}</pre></details></article>`;
  }
  function evidencePathMarkup(state, selected, projection = {}, context = {}, forming = false, options = {}) {
    const r = evidenceRelationships(state,selected,context), {node,fact,document:requirement,evaluation} = r;
    if (!node) return forming ? `<div class="au-reading-column au-opening-content" data-au-evidence-path>${originalText(state) ? `<h2>Original message</h2><pre class="au-original-message">${h(originalText(state))}</pre>` : ''}${acquiredContentMarkup(state,projection) || sourceListMarkup(state,list(state.source_descriptors),'originals',projection)}</div>` : openingContentMarkup(state,projection);
    if (!forming) return stepDetailMarkup(state,selected,projection,context,options);
    const citations = citationRows(fact), capability = projection.node_capabilities?.[selected];
    const sources = citations.map(citation => `<button type="button" class="au-source-link au-evidence-source" data-au-source-identity="${h(sourceObjectIdentity(state,citation.artifact_id))}" data-au-source="${h(citation.artifact_id)}" data-au-citation="${h(JSON.stringify(citation))}" data-au-source-origin="path:${h(selected)}:${h(fact.fact_id)}"><span class="au-evidence-source-label">${h(sourceLabel(state,citation.artifact_id))}<span aria-hidden="true">↗</span></span>${citation.quote ? `<q>${h(citation.quote)}</q>` : '<span>Open cited source</span>'}</button>`).join('');
    const route = requirement?.route_state || requirement?.status || 'pending', review = requirement?.review_state;
    const timing = {needed_later:'Needed after its step is reached.',needed_now:'Listed as needed now.',held_behind_question:'May be needed',held_not_reviewed:'The file is available; its evidence remains unestablished.',not_needed:'This document is not required on the recorded route.'}[route] || statusLabel(route);
    const blocked = list(evaluation.blocked_by || evaluation.unresolved_dependencies);
    const branches = list(state.graph?.edges).filter(edge => edge.source_node_id === selected || edge.target_node_id === selected);
    return `<div class="au-reading-column" data-au-evidence-path data-au-selected-step="${h(selected)}">${sources ? `<section class="au-reading-passages"><h3 class="au-reading-label">From the sources</h3>${sources}</section>` : !list(state.facts).some(item => citationRows(item).length) ? acquiredContentMarkup(state,projection) : ''}${fact ? `<section class="au-reading-fact" data-au-fact="${h(fact.fact_id)}"><h3 class="au-reading-label">Recorded finding</h3><p class="au-fact-summary">${h(state.graph?.family === 'incoming_packet' ? 'This document has not been checked.' : statusLabel(fact.verdict || fact.status))}</p><details><summary>Details</summary><p>${h(factCaseText(fact))}</p></details>${forming && state.graph?.family !== 'incoming_packet' ? `<p class="au-fact-state">${h(statusLabel(fact.verdict || fact.status))}</p>` : ''}${r.facts.length > 1 ? `<h3 class="au-reading-label">Other questions</h3><div class="au-reading-objects" role="group" aria-label="Other questions for this decision">${r.facts.filter(item => item.fact_id !== fact.fact_id).map(item => `<button type="button" class="au-link" data-au-fact-select="${h(item.fact_id)}" data-au-fact-state="${h(item.verdict || item.status || '')}">${h(statusLabel(item.verdict || item.status))}: ${h(name(item))}</button>`).join('')}</div>` : ''}</section>` : ''}${requirement && !forming ? `<section class="au-reading-requirement" data-au-document="${h(requirement.document_type)}" data-au-obligation="${h(requirementIdentity(requirement))}" data-route="${h(route)}"><h3 class="au-reading-label">Document for this decision</h3><h3>${h(name(requirement))}</h3><p class="au-document-route">${h(timing)}</p>${documentReviewMarkup(review)}${r.documents.length > 1 ? `<div class="au-reading-objects" role="group" aria-label="Documents for this decision">${r.documents.filter(item => requirementIdentity(item) !== requirementIdentity(requirement)).map(item => `<button type="button" class="au-link" data-au-document-select="${h(item.document_type)}" data-au-obligation-select="${h(requirementIdentity(item))}">${h(name(item))}</button>`).join('')}</div>` : ''}</section>` : ''}${!forming ? `<section class="au-reading-decision"><h3 class="au-reading-label">Decision</h3>${recordButton('Details','step',selected)}<p class="au-step-status">${h(statusLabel(evaluation.execution_state || evaluation.state))}</p>${blocked.length ? `<p>Requires ${blocked.map(id => `<button type="button" class="au-link" data-au-select="${h(id)}">${h(name(list(state.graph?.nodes).find(item => item.node_id === id)) || words(id))}</button>`).join(', ')}.</p>` : ''}</section>` : ''}${!forming && (list(state.knowledge_uses).length || node.authority) ? `<section class="au-reading-procedure"><h3 class="au-reading-label">Procedure</h3>${list(state.knowledge_uses).map(use => `<p data-au-knowledge-use="${h(use.knowledge_sha256 || use.knowledge_id || use.version_id)}">${h(procedureLabel(use))} · version ${h(use.version || use.version_id)} ${knowledgeLink(use)}</p>`).join('')}${node.authority?.title ? `<p>${h(procedureLabel({family:state.graph?.family,title:node.authority.title}))}</p>` : ''}</section>` : ''}${!forming && branches.length ? `<nav class="au-reading-relations" aria-label="Connected decisions">${branches.map(edge => { const other = edge.source_node_id === selected ? edge.target_node_id : edge.source_node_id; return `<button type="button" class="au-link" data-au-select="${h(other)}">${edge.target_node_id === selected ? 'Requires' : 'Leads to'} ${h(name(list(state.graph?.nodes).find(item => item.node_id === other)) || words(other))}<span class="au-meta">${h(statusLabel(edgeState(state,edge.edge_id)))}</span></button>`; }).join('')}</nav>` : ''}${!forming && capability?.authorized === false ? `<p class="au-reading-limit">${h(capability.reason || 'Execution is unavailable for this step.')}</p>` : ''}</div>`;
  }

  // The selected step answers in one reading order: its title, the first
  // cited passage, one line per subject with a single status, the rule or
  // legal basis, then the procedure version the case used.
  function subjectQuote(quote, limit = 110) {
    const chars = Array.from(String(quote).replace(/\s+/gu,' ').trim());
    if (chars.length <= limit) return chars.join('');
    const cut = chars.slice(0,limit).join(''), space = cut.lastIndexOf(' ');
    return `${(space > 60 ? cut.slice(0,space) : cut).replace(/[\s,;:]+$/u,'')}…`;
  }
  function stepSubjects(state, r) {
    const resolved = value => ['established','satisfied','supported','true','false'].includes(String(value));
    const requirementFor = fact => r.documents.find(doc => list(doc.required_fact_ids).includes(fact.fact_id)) || list(state.obligations).find(doc => list(doc.required_fact_ids).includes(fact.fact_id));
    const rows = r.facts.map(fact => ({id:fact.fact_id,fact,established:resolved(fact.verdict ?? fact.status),requirement:requirementFor(fact),citation:citationRows(fact).find(row => typeof row?.quote === 'string' && row.quote)}));
    for (const doc of r.documents) if (!rows.some(row => row.requirement && requirementIdentity(row.requirement) === requirementIdentity(doc))) rows.push({id:`document:${requirementIdentity(doc)}`,document:doc,established:doc.review_state === 'sufficient',requirement:doc,citation:null});
    return rows;
  }
  // Each subject carries exactly one state. A question whose document the
  // recorded route does not require is moot, so it is not called open.
  function subjectEvaluation(state, row) {
    return row.requirement ? {...row.requirement,...list(state.evaluation?.documents).find(doc => doc.document_type === row.requirement.document_type)} : null;
  }
  function subjectState(state, row) {
    if (row.established) return 'established';
    const evaluated = subjectEvaluation(state,row);
    return evaluated && evaluated.review_state !== 'sufficient' && ['not_needed','inactive','excluded'].includes(evaluated.route_state || evaluated.status || '') ? 'not_needed' : 'open';
  }
  function subjectLineMarkup(state, row, current, passageShown = false) {
    const fact = row.fact, verdict = String(fact?.verdict ?? fact?.status ?? '');
    const subject = fact ? language.factLabel(fact) : name(row.document) || 'Recorded document', document = row.requirement ? name(row.requirement) || language.documentTitle(row.requirement) : '';
    const evaluated = subjectEvaluation(state,row), standing = subjectState(state,row);
    const word = ['true','false'].includes(verdict) ? `<span class="au-subject-verdict">${h(statusLabel(verdict))}</span>` : '';
    if (standing === 'established') return `<strong class="au-subject-state">Established:</strong> <span class="au-subject-name">${h(subject)}</span>${word ? ` · ${word}` : ''}${row.citation ? passageShown ? ' — cited above' : ` — <q class="au-subject-quote">${h(subjectQuote(row.citation.quote))}</q>` : ' · no passage cited'}`;
    if (standing === 'not_needed') return `<strong class="au-subject-state">Not needed:</strong> <span class="au-subject-name">${h(subject)}</span> · ${h(document)} is not required on the recorded route`;
    const route = evaluated?.route_state || evaluated?.status || '';
    const need = !document ? '' : evaluated?.review_state === 'sufficient' ? ` · not established from ${h(document)}` : route === 'held_behind_question' ? ` · may need <span class="au-subject-need">${h(document)}</span>` : ` · needs <span class="au-subject-need">${h(document)}</span>`;
    const timing = {needed_later:'Needed after its step is reached.',needed_now:'Listed as needed now.'}[route] || '';
    return `<strong class="au-subject-state">Open:</strong> <span class="au-subject-name">${h(subject)}</span>${need}${timing ? ` <span class="au-document-route">${h(timing)}</span>` : ''}`;
  }
  // The step's own recorded action: its result sentence and cited passages.
  function stepAction(state, selected) {
    return [...list(state.actions)].reverse().map(entry => entry?.result || entry).find(row => row && (row.node_id === selected || list(row.node_ids).includes(selected))) || null;
  }
  function stepPassageButton(state, citation, origin) {
    return `<button type="button" class="au-source-link au-evidence-source" data-au-source-identity="${h(sourceObjectIdentity(state,citation.artifact_id))}" data-au-source="${h(citation.artifact_id)}" data-au-citation="${h(JSON.stringify(citation))}" data-au-source-origin="${h(origin)}"><span class="au-evidence-source-label">${h(sourceLabel(state,citation.artifact_id))}<span aria-hidden="true">↗</span></span>${citation.quote ? `<q>${h(citation.quote)}</q>` : '<span>Open cited source</span>'}</button>`;
  }
  function stepVersionMarkup(state) {
    const uses = list(state.knowledge_uses);
    if (!uses.length) return '';
    return `<p class="au-step-version au-outcome-row" data-au-step-version><span class="au-outcome-key">Used</span> <span class="au-outcome-value">${uses.map(use => {
      const later = list(state.knowledge_published).filter(item => item.qualification?.status === 'qualified' && item.knowledge_id === use.knowledge_id && Number.isSafeInteger(item.version) && Number.isSafeInteger(use.version) && item.version > use.version && (!item.source_claim_id || item.source_claim_id === state.claim_id));
      return `<span class="au-step-version-used" data-au-knowledge-use="${h(use.knowledge_sha256 || use.knowledge_id || use.version_id)}">${knowledgeLink(use,`v${use.version || use.version_id}`)} · ${h(procedureLabel(use))}</span>${later.map(item => `<span class="au-step-version-later"> · Later version saved from this case: ${knowledgeLink(item,`v${item.version}`)}</span>`).join('')}`;
    }).join('<br>')}</span></p>`;
  }
  function stepDetailMarkup(state, selected, projection = {}, context = {}, options = {}) {
    const r = evidenceRelationships(state,selected,context), {node,evaluation} = r;
    if (!node) return openingContentMarkup(state,projection);
    const rows = stepSubjects(state,r), selectedRow = rows.find(row => row.fact && row.fact.fact_id === r.fact?.fact_id);
    const passageRow = selectedRow?.citation ? selectedRow : rows.find(row => row.citation);
    const passageFact = passageRow?.fact, capability = projection.node_capabilities?.[selected];
    const sources = passageFact ? citationRows(passageFact).map(citation => stepPassageButton(state,citation,`path:${selected}:${passageFact.fact_id}`)).join('') : '';
    // A step without a cited fact answers with its own recorded action: the
    // first passage that action cites, then the others one disclosure away.
    const action = stepAction(state,selected), actionCitations = action ? citationRows(action).filter(row => row?.artifact_id && typeof row.quote === 'string' && list(state.source_descriptors).some(source => source.artifact_id === row.artifact_id)) : [];
    const actionPassages = !sources && actionCitations.length ? `<section class="au-reading-passages" aria-label="Cited passage" data-au-step-action-passages><p class="au-meta">Cited for this step's recorded result</p>${stepPassageButton(state,actionCitations[0],`path:${selected}:action:0`)}${actionCitations.length > 1 ? `<details class="au-more-passages" data-au-disclosure="step-passages:${h(selected)}"><summary>${actionCitations.length === 2 ? '1 more cited passage' : `${actionCitations.length-1} more cited passages`}</summary>${actionCitations.slice(1).map((citation,index) => stepPassageButton(state,citation,`path:${selected}:action:${index+1}`)).join('')}</details>` : ''}</section>` : '';
    const passages = sources ? `<section class="au-reading-passages" aria-label="Cited passage">${passageRow !== selectedRow ? `<p class="au-meta">Cited for ${h(language.factLabel(passageFact))}</p>` : ''}${sources}</section>` : actionPassages || (!list(state.facts).some(item => citationRows(item).length) ? acquiredContentMarkup(state,projection) : '');
    const stepResult = text(action?.summary).trim() ? `<p class="au-step-result au-outcome-row" data-au-step-result><span class="au-outcome-key">Step result</span> <span class="au-outcome-value">${h(text(action.summary).trim())}</span></p>` : '';
    // One element carries the focused requirement's identity; other subjects
    // select their own fact (and its requirement) with a single control each.
    const focused = r.document ? requirementIdentity(r.document) : null, selects = new Set();
    const focusRow = selectedRow?.requirement && requirementIdentity(selectedRow.requirement) === focused ? selectedRow : rows.find(row => row.requirement && requirementIdentity(row.requirement) === focused);
    const lines = rows.map(row => {
      const current = Boolean(selectedRow) && row === selectedRow, requirement = row.requirement, identity = requirement ? requirementIdentity(requirement) : '';
      const route = requirement ? list(state.evaluation?.documents).find(doc => doc.document_type === requirement.document_type)?.route_state || requirement.status || 'pending' : '';
      const attributes = `class="au-subject" data-au-subject="${h(row.id)}" data-au-subject-state="${subjectState(state,row)}"${row === focusRow ? ` data-au-document="${h(requirement.document_type)}" data-au-obligation="${h(identity)}" data-route="${h(route)}"` : requirement ? ` data-au-subject-document="${h(requirement.document_type)}"` : ''}${current ? ' aria-current="true"' : ''}`;
      const copy = subjectLineMarkup(state,row,current,Boolean(sources) && row === passageRow);
      const documentSelect = requirement && identity !== focused && !selects.has(identity) ? (selects.add(identity), ` data-au-document-select="${h(requirement.document_type)}" data-au-obligation-select="${h(identity)}"`) : '';
      const control = current ? '' : row.fact ? `data-au-fact-select="${h(row.fact.fact_id)}" data-au-fact-state="${h(row.fact.verdict || row.fact.status || '')}"${documentSelect}` : documentSelect.trim();
      // The selected subject's recorded reason is the answer, so it is shown, not folded.
      const reason = current && row.fact && (text(row.fact.summary).trim() || text(row.fact.reason).trim() || subjectState(state,row) === 'open') ? `<p class="au-fact-summary">${h(factCaseText(row.fact))}</p>` : '';
      return `<li ${attributes}>${control ? `<button type="button" class="au-link au-subject-select" ${control}>${copy}</button>` : copy}${reason}</li>`;
    }).join('');
    const subjects = rows.length ? `<section class="au-step-subjects${r.fact ? ' au-reading-fact' : ''}"${r.fact ? ` data-au-fact="${h(r.fact.fact_id)}"` : ''} aria-label="What this step established and what is open"><ul class="au-subject-lines">${lines}</ul></section>` : '';
    // The outcome's legal basis belongs to the step that records the result.
    const legal = node.terminal === true ? legalAuthorityRows(state) : [];
    const rule = node.authority?.title ? `<p class="au-step-rule au-outcome-row"><span class="au-outcome-key">Rule</span> <span class="au-outcome-value">${h(procedureLabel({family:state.graph?.family,title:node.authority.title}))} procedure</span></p>` : '';
    const blocked = list(evaluation.blocked_by || evaluation.unresolved_dependencies);
    const branches = list(state.graph?.edges).filter(edge => edge.source_node_id === selected || edge.target_node_id === selected);
    const heading = options.title === false ? '' : `<h3 class="au-step-detail-title" tabindex="-1" data-au-step-detail-heading>${h(name(node))}</h3>`;
    return `<div class="au-reading-column au-step-detail" data-au-evidence-path data-au-selected-step="${h(selected)}">${heading}${passages}${subjects}${stepResult}${rule}${legal.length ? `<p class="au-step-legal au-outcome-row" data-au-step-legal><span class="au-outcome-key">Legal basis</span> <span class="au-outcome-value">Swiss Code of Obligations, ${h(legal.map(row => `art. ${row.article}`).join(', '))} · basis of the recorded result</span></p>` : ''}${stepVersionMarkup(state)}</div><div class="au-reading-column au-step-record" data-au-step-record="${h(selected)}"><section class="au-reading-decision"><p class="au-step-line au-outcome-row"><span class="au-outcome-key">This step</span> <span class="au-outcome-value"><span class="au-step-status">${h(statusLabel(evaluation.execution_state || evaluation.state))}</span>${blocked.length ? ` · Requires ${blocked.map(id => `<button type="button" class="au-link" data-au-select="${h(id)}">${h(name(list(state.graph?.nodes).find(item => item.node_id === id)) || words(id))}</button>`).join(', ')}` : ''} ${recordButton('Details','step',selected)}</span></p></section>${capability?.authorized === false ? `<p class="au-reading-limit">${h(capability.reason || 'Execution is unavailable for this step.')}</p>` : ''}${branches.length ? `<nav class="au-reading-relations" aria-label="Connected decisions">${branches.map(edge => { const other = edge.source_node_id === selected ? edge.target_node_id : edge.source_node_id; return `<button type="button" class="au-link" data-au-select="${h(other)}">${edge.target_node_id === selected ? 'Requires' : 'Leads to'} ${h(name(list(state.graph?.nodes).find(item => item.node_id === other)) || words(other))}<span class="au-meta">${h(statusLabel(edgeState(state,edge.edge_id)))}</span></button>`; }).join('')}</nav>` : ''}</div>`;
  }
  // The step title already heads this view above the map.
  function inspectorMarkup(state, selected, projection = {}, events = [], context = {}) {
    return evidencePathMarkup(state,selected,projection,context,false,{title:false});
  }

  function eventLabel(event) {
    if (event.kind === 'knowledge.published') return event.payload?.knowledge?.qualification?.status === 'qualified' ? 'Steps saved for reuse' : 'Not saved';
    if (event.kind?.startsWith('reconciliation.')) return ({'reconciliation.started':'Saved-result reconciliation started','reconciliation.completed':'Saved-result reconciliation completed','reconciliation.failed':'Saved-result reconciliation failed'})[event.kind] || words(event.kind);
    return event.payload?.summary || event.payload?.reason || ({'intake':'Incoming packet saved', 'intake.received':'Incoming packet saved', 'work.started':'Autonomous investigation started', 'sources.acquired':'Original sources acquired', 'interpretation.accepted':'Source-grounded process accepted', 'graph.advanced':'Process advanced', 'action.completed':'Action result saved', 'outcome.recorded':'Operational outcome saved', 'work.completed':'Operational outcome saved', 'work.deferred':'Work deferred', 'knowledge.published':'Steps saved for reuse', 'knowledge.used':'Saved steps reused', 'knowledge.reused':'Saved steps reused'})[event.kind] || words(event.kind);
  }
  function sourceListMarkup(state, sources = list(state.source_descriptors), origin = 'originals', projection = {}) {
    if (origin !== 'history') { const visible = new Set(currentSourceSelection(state,projection).map(source => source.artifact_id)); sources = sources.filter(source => visible.has(source.artifact_id)); }
    return `<ul class="au-source-list">${sources.map(source => {
      const acquired = list(state.acquired_sources).find(row => row.artifact_id === source.artifact_id), unassessed = assessmentFreshness(state).sources.some(row => row.artifact_id === source.artifact_id);
      const capability = acquired?.extraction === 'unsupported_metadata' ? 'Text could not be read' : acquired && !acquired.complete ? 'Only part of the source is readable' : '';
      const context = [sourceKind(state,source,projection) === 'Fictional case document' ? 'Fictional case document' : '',capability,unassessed ? 'Awaiting assessment' : ''].filter(Boolean).join(' · ');
      return `<li data-au-source-arrival="${h(source.artifact_id)}"${unassessed ? ' data-au-source-freshness="unassessed"' : ''}>${button(operationSourceTitle(source),`data-au-source="${h(source.artifact_id)}" data-au-source-origin="${h(origin)}:${h(source.artifact_id)}"`)}${context ? `<span>${h(context)}</span>` : ''}${acquired?.reason || acquired?.limitation ? `<p>${h(acquired.reason || acquired.limitation)}</p>` : ''}</li>`;
    }).join('') || '<li>No original source recorded.</li>'}</ul>`;
  }

  function unassignedSourcesMarkup(state) {
    const assigned = new Set(list(state.graph?.document_catalog).flatMap(doc => list(doc.held_files).map(file => file.artifact_id)));
    const sources = currentSourceSelection(state).filter(source => source.role === 'supporting_document' && !assigned.has(source.artifact_id));
    return sources.length ? `<section class="au-supporting"><h3>Files awaiting a document assignment</h3>${sourceListMarkup(state,sources,'documents')}</section>` : '';
  }

  function sourcesMarkup(state, readOnly = false, projection = {}) {
    return `<section class="au-supporting au-originals"><h2>Sources</h2><p class="au-original-title">${h(state.title || 'Untitled case')}</p>${originalText(state) ? `<pre class="au-original-message">${h(originalText(state))}</pre>` : ''}${sourceListMarkup(state,list(state.source_descriptors),'originals',projection)}${state.revision > 0 && !readOnly ? '<form data-au-arrival class="au-arrival"><label for="auAdditionalFiles">Add supporting files</label><input id="auAdditionalFiles" name="files" type="file" multiple required><button class="au-secondary" type="submit">Add files</button><p class="au-form-status"></p></form>' : ''}</section>`;
  }

  function historyLabel(event) {
    const labels = {'intake':'Case received','intake.received':'Case received','sources.arrived':'Supporting files added','sources.acquired':'Original source read','process.prepared':'Case opened','work.started':'Checks started','interpretation.accepted':'Evidence assessment saved','graph.advanced':'Document requirements updated','action.completed':'Action result saved','outcome.recorded':'Result saved','work.completed':'Result saved','work.deferred':'Checks stopped','knowledge.used':'Procedure reused','reconciliation.started':'Saved result review started','reconciliation.completed':'Saved result review finished','reconciliation.failed':'Saved result review failed'};
    if (event.kind === 'knowledge.published') return event.payload?.knowledge?.qualification?.status === 'qualified' ? 'Steps saved for reuse' : 'Not saved';
    if (event.kind === 'work.phase') return ({acquiring:'Read the documents',interpreting:'Read the documents',verifying:'Check the documents',progressing:'Follow the rules'})[event.payload?.phase] || 'Recorded work';
    return labels[event.kind] || event.payload?.summary || 'Recorded work';
  }
  function actionLabel(state, result) {
    if (result.label || result.title || result.summary) return result.label || result.title || result.summary;
    if (result.type === 'document_review') return `Reviewed ${name(list(state.obligations).find(item => item.document_type === result.document_type)) || words(result.document_type)}`;
    if (result.type === 'assessment_record') return 'Evidence assessment saved';
    return 'Recorded action';
  }
  function activityMarkup(state, events, projection = {}) {
    const visible = new Set(currentSourceSelection(state,projection).map(source => source.artifact_id)), earlier = list(state.source_descriptors).filter(source => !visible.has(source.artifact_id));
    return `<section class="au-activity"><h2>History</h2>${recordButton('Case details','claim')}${earlier.length ? `<section class="au-history-record"><h3>Earlier documents</h3>${sourceListMarkup(state,earlier,'history',projection)}</section>` : ''}${state.outcome || state.deferral ? `<section class="au-history-outcome"><h3>${h(claimStatusLabel(state.status,state))}</h3>${outcomeSummaryMarkup(state)}${recordButton('Details','outcome')}</section>` : ''}${list(state.reconciliations).map(row => `<article class="au-history-record"><h3>${h(({started:'Saved result review started',completed:'Saved result review finished',failed:'Saved result review failed'})[row.status] || 'Saved result review')}</h3>${row.original_deferral?.reason ? `<p>Original execution failure: ${h(row.original_deferral.reason)}</p>` : ''}${row.failure_reason ? `<p>${h(row.failure_reason)}</p>` : ''}${recordButton('Details','reconciliation',row.reconciliation_id)}</article>`).join('')}<ol class="au-event-list">${events.slice().reverse().map(event => `<li><div><strong>${h(historyLabel(event))}</strong><time datetime="${h(event.timestamp || '')}">${h(dateLabel(event.timestamp))}</time>${recordButton('Details','event',event.seq)}</div></li>`).join('') || '<li>No accepted work recorded.</li>'}</ol>${actionRows(state,events).length ? `<section><h3>Recorded actions</h3>${actionRows(state,events).map((row,index) => `<article class="au-history-record" data-au-action-scope="${h(row.scope)}" data-au-action-instance="${h(row.instanceId)}"><strong>${h(actionLabel(state,row.result))}</strong><p class="au-meta">${row.scope === 'historical' ? 'Recorded in an earlier run' : row.scope === 'current' ? 'Recorded in this run' : 'Run association is not recorded'}</p>${row.result.reason ? `<p>${h(row.result.reason)}</p>` : ''}${sourceButtons(state,row.result,`action:${row.instanceId}`)}${recordButton('Details','action',row.instanceId)}</article>`).join('')}</section>` : ''}</section>`;
  }

  function eventCueMarkup(state, events) {
    const event = events.at(-1);
    if (!event) return '';
    const semantic = semanticEventRecord(state,event), identity = semantic?.id;
    const label = semantic ? `${semantic.label} · ${semantic.title}` : eventLabel(event);
    return `<button type="button" class="au-event-cue" data-au-detail="activity" data-au-event-seq="${h(event.seq)}"${identity ? ` data-au-semantic-event="${h(identity)}" data-au-semantic-kind="${h(event.kind)}"` : ''} title="${h(label)} · accepted revision ${h(event.seq)}"><span class="au-event-marker" aria-hidden="true">${semantic?.type === 'reused' ? '↺' : '·'}</span><span>${h(label.length > 180 ? label.slice(0,177) + '…' : label)}</span><span class="au-event-revision">↗</span></button>`;
  }
  function claimHeadingMarkup(state, extraClass = '', openingTour = null) {
    const featured = featuredCase(state.claim_id);
    const opening = openingTour ? `Case ${openingTour.index+1} of ${openingTour.cases.length} · ${DOMAINS.find(item=>item.id===openingTour.cases[openingTour.index]?.domain)?.label || 'Recorded case'}` : '';
    // A featured case keeps its short label; the customer's own subject line says what they asked.
    const asked = featured && state.title && state.title !== featured.label ? `<p class="au-case-asks" data-au-case-asks><span>Customer asks</span> ${h(state.title)}</p>` : '';
    return `<h1 class="au-page-heading ${extraClass}" id="auClaimTitle" data-au-claim-title tabindex="-1">${h(opening || featured?.label || state.title || 'Untitled case')}</h1>${asked}`;
  }

  function readSkeletonMarkup(kind, title = '', claimId = '') {
    const featured = kind === 'claim' && featuredCase(claimId);
    return `<section class="au-read-skeleton" data-au-skeleton="${h(kind)}" aria-busy="true"><header class="au-work-head"><div><h1 class="au-page-heading" tabindex="-1">${h(featured?.label || title || (kind === 'knowledge' ? 'Knowledge' : 'Opening case'))}</h1></div></header></section>`;
  }

  function roleBadge(roleId = 'casepath') {
    const role = language.roles[roleId] || language.roles.casepath;
    return `<span class="au-role-badge" data-au-role="${h(role.id)}"><span class="au-role-shape" aria-hidden="true"></span>${h(role.label)}</span>`;
  }
  function roleExplanationMarkup() {
    return `<details class="au-role-explanation" data-au-disclosure="roles"><summary>How to read</summary><p>Each role names work in the saved record.</p><ul>${['reader','checker','rulebook','memory'].map(id=>`<li>${roleBadge(id)}<span>${h(language.roles[id].description)}</span></li>`).join('')}</ul><p>Checker can use the same recorded model as Reader.</p><p>Fixed rules means no model call was recorded for that work.</p><p>CasePath means the record does not identify a role.</p><p>${h(language.copy.noRealWorldAction)}</p></details>`;
  }
  function recordedResultLabel(operation, state) {
    if (!operation) return 'No result recorded yet.';
    const result = operation.result || operation.payload?.result || {};
    if (operation.kind === 'fact.extract') return result.verification_required === false ? 'Confirmed.' : 'To be confirmed.';
    if (operation.kind === 'decision') return language.outcomePresentation({...state,outcome:result}).summary;
    if (result.assessment === 'sufficient') return 'Confirmed by the document.';
    if (result.assessment === 'insufficient') return 'More proof is needed.';
    if (['false','excluded'].includes(result.activation)) return 'This step does not apply.';
    if (['true','active'].includes(result.activation)) return 'This step applies.';
    if (result.activation === 'unresolved') return 'Still open.';
    if (['knowledge.add','knowledge.published'].includes(operation.kind)) return language.knowledgePresentation(operation.payload?.knowledge || result,operation).label;
    return '';
  }
  function boundDisplayReceipt(head, binding) {
    if (!head || !binding) return null;
    const reference = referenceExecution(head);
    const receipt = [...list(head.receipts)].reverse().find(row=>row.kind==='interpretation.accepted' && row.receipt?.workflow_id===head.run_id)?.receipt;
    if (!receipt || !reference || !head.run_id || ![head.state_sha256,head.last_event_sha256,head.source_roster_sha256,reference.rule_set_sha256,reference.profile_sha256].every(isHash) || !reference.profile_id) return null;
    if (binding.claim_id!==head.claim_id || binding.run_id!==head.run_id || receipt.workflow_id!==binding.run_id ||
        binding.current_revision!==head.revision || binding.current_state_sha256!==head.state_sha256 || binding.current_event_sha256!==head.last_event_sha256 ||
        binding.source_roster_sha256!==head.source_roster_sha256 || binding.rule_set_sha256!==reference.rule_set_sha256 ||
        binding.profile_id!==reference.profile_id || binding.profile_sha256!==reference.profile_sha256) return null;
    return receipt;
  }
  function operationDisplayContext(state, trace, operation) {
    const display = trace?.displayProvenance, binding = trace?.binding;
    return display && display.binding===binding && state?.claim_id===binding.claim_id && state?.run_id===binding.run_id &&
      list(trace.rows).includes(operation) ? {state,receipt:display.receipt} : {state};
  }
  // Origin and provenance come from the record, never from the route.
  function claimOrigin(state, origin = state?.origin) {
    if (featuredCase(state?.claim_id)) return 'featured';
    return origin === 'canonical_original' || state?.original_binding?.corpus_id ? 'canonical_original' : origin || '';
  }
  function historyProvenance(state) {
    if (!state?.claim_id) return null;
    const kind = language.provenancePresentation({state}).kind;
    return kind === 'rules' ? {mode:'deterministic_reference'} : kind === 'model' ? {mode:'model'} : null;
  }
  function claimModeLine(state, presentation = {}) {
    const trace = presentation.transportOperations || presentation.operations, replay = presentation.replay;
    const replaying = presentation.mode === 'replay' && !trace?.savedFallback;
    const fullHead = replay && replay.through_seq === replay.current_revision && replay.state?.claim_id === state.claim_id;
    const head = trace?.headState?.claim_id === state.claim_id ? {state:trace.headState,events:list(trace.pinnedJournal)} : fullHead ? {state,events:presentation.events || []} : null;
    const revision = !replaying ? state.revision : Number.isSafeInteger(replay?.current_revision) ? replay.current_revision : Number.isSafeInteger(presentation.headRevision) ? presentation.headRevision : null;
    const recordedAt = head ? [...head.events].reverse().find(event => event.timestamp)?.timestamp : '';
    return language.modeLine({revision,presentation:replaying ? 'replay' : active(state.status) ? 'live' : 'saved',provenance:head ? historyProvenance(head.state) : null,origin:claimOrigin(state,presentation.origin),recordedAt,readOnly:Boolean(presentation.readOnly)});
  }
  // "Now" belongs to moving work: a running claim or a replay cursor that has
  // not reached its saved head. Settled work names its last recorded event.
  function nowIsLive(state, presentation = {}) {
    const trace = presentation.operations, replay = presentation.mode === 'replay' ? presentation.replay : null;
    if (trace) return !trace.finished && !trace.savedFallback && !trace.unrun;
    if (presentation.mode === 'replay' && (presentation.playing || presentation.paused)) return true;
    if (replay && Number.isSafeInteger(replay.through_seq) && Number.isSafeInteger(replay.current_revision)) return replay.through_seq < replay.current_revision;
    return active(state.status);
  }
  function lastMarkup(state, events = [], presentation = {}) {
    const trace = presentation.operations, event = [...events].reverse().find(row => Number.isSafeInteger(row.seq) && row.seq <= state.revision);
    // Revision zero has nothing to name. Without its event rows, a saved head
    // still states only what it is: a saved revision.
    if (!event && !(state.revision > 0)) return '';
    const checked = trace?.finished && state.outcome ? [...list(trace.rows)].reverse().find(row => row.kind === 'decision') : null;
    const actor = checked ? language.operationPresentation(checked,operationDisplayContext(state,trace,checked)) : null;
    const shown = actor ? {roleId:actor.roleId,past:actor.label.charAt(0).toLowerCase()+actor.label.slice(1)} : event ? language.eventPresentation(event) : {roleId:'casepath',past:`saved revision ${state.revision}`};
    const outcome = state.outcome && (trace?.finished || referenceAssessmentComplete(state)) ? language.outcomePresentation(state) : null;
    // The result stays named after its moment passes: the recorded finding, then the checks.
    const result = outcome ? [plainOutcomeLabel(outcome),`${outcome.label}.`].filter(Boolean).join(' ') : '';
    const at = event ? event.timestamp : state.updated_at;
    const time = at && Number.isFinite(Date.parse(at)) ? ` · <time datetime="${h(at)}">${h(dateLabel(at))}</time>` : '';
    return `<div class="au-now au-last" data-au-now-id="${h(checked?.id || event?.event_sha256 || state.last_event_sha256 || '')}" data-au-now-kind="last"><span class="au-now-label">Last:</span> ${roleBadge(shown.roleId)} <span data-au-now-copy>${h(shown.past)}${time}.</span> <span data-au-now-result>${h(result)}</span> ${checked || event ? recordButton('Details',checked ? 'operation' : 'event',checked ? checked.id : event.seq) : ''}</div>`;
  }
  function nowMarkup(state, events = [], presentation = {}) {
    const trace = presentation.operations;
    if (!nowIsLive(state,presentation)) return lastMarkup(state,events,presentation);
    const operation = trace?.current || [...events].reverse().find(event=>event.seq<=state.revision);
    const original = language.operationPresentation(operation,{...operationDisplayContext(state,trace,operation),history:false,documents:[...list(state.source_descriptors),...list(state.graph?.document_catalog)]});
    const cited = ['source.open','span.read','phrase.match','fact.extract','verification.check','document.check'].includes(operation?.kind) && typeof operation.source?.artifact_id === 'string' && operation.source.artifact_id;
    const reuse = operation?.kind==='knowledge.reuse' ? recordedReuseMoment(state,trace,presentation.knowledge || {}) : operation?.kind==='knowledge.used' && operation.payload?.knowledge && list(state.knowledge_uses).some(use=>canonicalJSON(use)===canonicalJSON(operation.payload.knowledge)) ? {use:operation.payload.knowledge} : null;
    const shown = {...original,document:cited?original.document:'',...(reuse?{action:`reuses ${procedureLabel(reuse.use)} version ${reuse.use.version}`}:{})};
    const id = operation?.id || operation?.event_sha256 || '';
    const action = ({'source.open':'opens this document','span.read':'reads the marked words','phrase.match':'finds matching wording','fact.extract':'finds a possible fact','verification.check':'checks this fact','document.check':'checks this document','knowledge.reuse':'reuses saved steps','knowledge.used':'reuses saved steps','decision':'records the result'})[operation?.kind] || shown.action;
    const recorded = h(operation ? `${action}.` : 'has no recorded action yet.');
    return `<div class="au-now" data-au-now-id="${h(id)}"><span class="au-now-label">Now</span> ${roleBadge(shown.roleId)}${trace?.current ? `<span class="au-working-dot" data-au-working-dot="${h(trace.current.id)}" aria-hidden="true"></span>` : ''} <span data-au-now-copy>${recorded}</span> <span data-au-now-result>${h(recordedResultLabel(operation,state))}</span> ${operation ? recordButton('Details',trace?.current ? 'operation' : 'event',trace?.current ? operation.id : operation.seq) : ''}</div>`;
  }
  function stepRole(node, state, trace) {
    const operation = !trace?.finished && trace?.current?.object && operationNodeId(trace.current,operationStageGraph(trace,state),state,trace) === node.node_id ? trace.current : null;
    return operation ? language.operationPresentation(operation,{state}).roleId : null;
  }
  // The recorded sentence leads; a recorded limit inside it keeps its own
  // emphasis. Templated copy is used only when nothing was recorded.
  function recordedSentenceMarkup(summary, limit = '') {
    const at = limit ? summary.indexOf(limit) : -1;
    return at < 0 ? h(summary) : `${h(summary.slice(0,at))}<span class="au-outcome-open">${h(limit)}</span>${h(summary.slice(at+limit.length))}`;
  }
  // Only citations whose source this case lists are linked; the reader then
  // checks the exact span against the original.
  function openableCitations(state, item) {
    return citationRows(item).filter(citation => typeof citation?.artifact_id === 'string' && typeof citation.quote === 'string' && list(state.source_descriptors).some(source => source.artifact_id === citation.artifact_id));
  }
  function outcomeCitation(state, outcome) {
    return openableCitations(state,outcome)[0] || null;
  }
  function outcomeCiteMarkup(state, citations, role) {
    return citations.map((citation,index) => `<button type="button" class="au-link au-outcome-cite" data-au-outcome-cite="${h(role)}" data-au-source="${h(citation.artifact_id)}" data-au-citation="${h(JSON.stringify(citation))}" data-au-source-origin="${h(`outcome:${role}:${index}`)}"><span class="au-outcome-cite-source">${h(sourceLabel(state,citation.artifact_id))}</span> <q>${h(subjectQuote(citation.quote,72))}</q><span aria-hidden="true"> ↗</span></button>`).join('');
  }
  // A prepared request stays readable in place; "no gap" names no document.
  function outcomeDraftMarkup(draft) {
    if (!draft.label) return '';
    if (!draft.subject && !draft.body) return `<p class="au-outcome-draft" data-au-draft-status="${h(draft.status)}">${h(draft.label)}</p>`;
    return `<details class="au-outcome-draft" data-au-draft-status="${h(draft.status)}" data-au-disclosure="outcome-draft"><summary>${h(draft.label)}</summary><div class="au-draft" data-au-draft>${draft.subject ? `<p class="au-draft-subject">${h(draft.subject)}</p>` : ''}${draft.body ? `<p class="au-draft-body">${h(draft.body)}</p>` : ''}</div></details>`;
  }
  function openFactsSentence(labels) {
    const shown = labels.slice(0,3), more = labels.length - shown.length;
    return `${shown.join(', ')}${more > 0 ? ` and ${more} more` : ''}`;
  }
  // The finding named by the recorded legal predicates, in plain words; none when none was recorded.
  function plainOutcomeLabel(shown) { return shown.findings.length ? shown.summary : ''; }
  // Received, missing and not-needed counts read from the recorded document routes.
  function documentTally(state) {
    const documents = new Map(list(state.evaluation?.documents).map(doc => [doc.document_type,doc]));
    const rows = list(state.obligations).concat(list(state.evaluation?.documents).filter(doc => !list(state.obligations).some(item => item.document_type === doc.document_type)));
    const groups = rows.map(row => { const doc = documents.get(row.document_type) || {}; return documentRouteGroup(doc.route_state || row.status || 'pending',doc.review_state); });
    const count = group => groups.filter(row => row === group).length;
    return {groups,received:count('supplied'),missing:count('now'),notNeeded:count('not_needed'),needed:groups.length-count('not_needed')};
  }
  function outcomeSummaryMarkup(state, outcome = state.outcome, supporting = '') {
    const shown = language.outcomePresentation({...state,outcome}), recorded = shown.recorded, citations = openableCitations(state,outcome || {});
    const lead = `<p class="au-outcome-plain" data-au-outcome-plain>${h(plainOutcomeLabel(shown) || shown.summary || shown.label)}${shown.openItems ? ` <span class="au-outcome-open">${h(shown.openItems)}</span>` : ''}</p>`;
    const wording = recorded.summary ? `<p class="au-outcome-summary" data-au-outcome-recorded>${recordedSentenceMarkup(recorded.summary,shown.openItems)}</p>` : '';
    const cited = citations.length ? `<p class="au-outcome-cited au-outcome-row" data-au-outcome-cited><span class="au-outcome-key">Cited</span> <span class="au-outcome-value">${outcomeCiteMarkup(state,citations,'summary')}</span></p>` : '';
    const issues = recorded.issueRows.length ? `<ul class="au-outcome-issues" aria-label="Recorded issue">${recorded.issueRows.map(issue => { const own = openableCitations(state,issue); return `<li data-au-outcome-issue>${h(issue.text)}${own.length ? ` ${outcomeCiteMarkup(state,own,'issue')}` : ''}</li>`; }).join('')}</ul>` : '';
    const open = recorded.openFacts.length ? `<p class="au-outcome-facts au-outcome-row" data-au-outcome-open-facts><span class="au-outcome-key">Open</span> <span class="au-outcome-value">${recorded.openFacts.map(label => `<span class="au-outcome-fact">${h(label)}</span>`).join('<span aria-hidden="true">&nbsp;· </span>')}</span></p>` : '';
    const missing = recorded.missing.map(row => `<button type="button" class="au-link" data-au-detail="documents"${row.document_type ? ` data-au-outcome-document="${h(row.document_type)}"` : ''}>${h(row.label)}</button>`).join(' · ');
    const tally = documentTally(state), noGap = recorded.draft.status === 'no_gap';
    const draftLink = recorded.missing.length && recorded.draft.status === 'draft' && (recorded.draft.subject || recorded.draft.body) ? '<button type="button" class="au-link" data-au-open-outcome-draft>Draft request</button>' : '';
    const documents = `<p class="au-outcome-documents au-outcome-row" data-au-outcome-documents><span class="au-outcome-key">Documents</span> <span class="au-outcome-value">${tally.groups.length ? `<button type="button" class="au-link" data-au-detail="documents">${tally.received} of ${tally.needed} received</button>${tally.missing ? ` · ${tally.missing} missing` : ''}${tally.notNeeded ? ` · ${tally.notNeeded} not needed` : ''}${noGap ? ' · no active document gap identified' : ''}` : 'No document check recorded'}${missing ? `<span data-au-outcome-missing> · Missing: ${missing}</span>` : ''}${draftLink ? ` · ${draftLink}` : ''}</span></p>`;
    // These controller boilerplates name no concrete handler action. Keep them in Why.
    const genericNext = ['Inspect the recorded assessment and its cited sources.', 'Inspect the recorded historical synthetic assessment; any real action needs its own current authority.', 'Await the named evidence or an authorized external action. New supporting files trigger reassessment.'].includes(recorded.nextAction);
    const next = genericNext ? '' : recorded.nextAction;
    const why = wording+cited+issues+open+(genericNext ? `<p data-au-recorded-next>${h(recorded.nextAction)}</p>` : '')+outcomeDraftMarkup(recorded.draft)+(recorded.limits.length ? `<p class="au-outcome-limit" data-au-outcome-limit>${h(recorded.limits.join(' '))}</p>` : '')+supporting;
    return `${lead}${documents}${next ? `<p class="au-outcome-next au-outcome-row" data-au-outcome-next><span class="au-outcome-key">Next</span> <span class="au-outcome-value">${h(next)}</span></p>` : ''}${why ? `<details class="au-outcome-why" data-au-disclosure="outcome-why"><summary>Why</summary>${why}</details>` : ''}`;
  }
  // Start stays focusable while unavailable, so its reason is announced
  // with it. aria-disabled blocks the action in the click handler.
  function startControlMarkup(availability = {}, pending = false) {
    const ready = Boolean(availability?.ready);
    return `<div class="au-start-control"><button type="button" class="au-primary" data-au-start aria-describedby="auStartReason"${ready ? '' : ' aria-disabled="true"'}>${pending ? 'Retry start' : 'Start checking'}</button><p class="au-start-reason" id="auStartReason" data-au-start-availability>${h(availability?.reason || 'Checking live execution availability…')}</p></div>`;
  }
  const DESK_RULE_KINDS = new Set(['condition.evaluate','node.evaluate','dependency.evaluate','process.inspect','document.require']);
  function deskFileLabel(source) {
    if (source.role === 'customer_message') return 'Customer’s message';
    return String(source.file_name || '').replace(/\.[a-z0-9]+$/iu,'').replace(/^\d+[-_ ]*/u,'').replace(/_\d{4}-\d{2}-\d{2}.*$/u,'').replace(/[-_]+/gu,' ').replace(/\bpacket\b/giu,'documents').replace(/\brecord\b/giu,'details').replace(/^./u,c => c.toUpperCase()) || 'Source';
  }
  function deskRequest(message) {
    const value=String(message || '');
    return (value.match(/(?:specifically asking for|specific request is|meine Bitte|bitte konkret um|request is|Mein Anliegen ist|Als Nächstes brauche ich|Jetzt benötige ich|Ich ersuche um)\s*:\s*([^;\n.]+)/iu)?.[1] || value.match(/(?:for the request|für)\s*[“«"]([^”»"]+)[”»"]/iu)?.[1] || '').trim();
  }
  function deskLaw(refs) {
    const codes=new Map();for(const ref of list(refs)){const [code,article]=String(ref).split(':');if(!codes.has(code))codes.set(code,new Set());if(article)codes.get(code).add(article);}
    return [...codes].map(([code,articles])=>`${code} ${[...articles].join(' · ')}`).join('  ');
  }
  function deskOperationModel(state, trace = null) {
    const head=trace?.headState || state, graph=head.graph?.family!=='incoming_packet'?head.graph:operationStageGraph(trace,state), nodes=list(graph?.nodes), rows=list(trace?.rows);
    const grouped=new Map(),fileById=new Map(),factFiles=new Map(),laws=new Map(),operationNodes=new Map();
    for(const source of list(head.source_descriptors)){
      const key=`${source.role || ''}:${source.file_name || source.artifact_id}`;
      if(!grouped.has(key))grouped.set(key,{key,source,ids:[]});grouped.get(key).ids.push(source.artifact_id);fileById.set(source.artifact_id,key);
    }
    const read=new Set(),received=new Set(),met=new Set(),evidence=new Map(),required=new Set(),activated=new Set();let facts=0,rules=0,reuse=null;
    for(const operation of rows){
      const artifact=operation.source?.artifact_id || operation.object?.id,file=fileById.get(artifact);
      if(operation.kind==='span.read'&&file)read.add(file);
      const predicate=operation.kind==='fact.extract'&&Array.isArray(operation.input?.rule_refs);
      // Use the existing source/cause chain, including its ambiguity checks.
      const node=operationNodeId(operation,graph,state,trace);
      if(node)operationNodes.set(operation.id,node);
      if(operation.kind==='fact.extract'&&operation.source){
        if(operation.result?.verification_required!==false){facts++;if(file)factFiles.set(file,(factFiles.get(file)||0)+1);}
        if(node){evidence.set(node,operation);activated.add(node);if(predicate){if(!laws.has(node))laws.set(node,new Set());for(const ref of operation.input.rule_refs)laws.get(node).add(ref);}}
      }
      if(DESK_RULE_KINDS.has(operation.kind))rules++;
      if(operation.kind==='node.evaluate'&&operation.result?.activation==='true')activated.add(operation.object.id);
      if(operation.kind==='step.complete'&&operation.result?.status==='completed'&&nodes.some(row=>row.node_id===operation.object.id)){met.add(operation.object.id);activated.add(operation.object.id);if(operation.source&&!evidence.has(operation.object.id))evidence.set(operation.object.id,operation);}
      if(operation.kind==='document.require'&&operation.result?.activation==='true')required.add(operation.object.id);
      if(operation.kind==='document.check'&&operation.result?.assessment==='sufficient'&&operation.source){received.add(operation.object.id);if(node)evidence.set(node,operation);}
      if(operation.kind==='knowledge.reuse'&&Number.isSafeInteger(operation.input?.version))reuse=operation;
    }
    const known=Boolean(trace?.binding || trace?.verifiedResult);
    if(!known&&state.outcome){
      for(const node of list(state.evaluation?.nodes))if(DONE_NODE_STATES.includes(node.execution_state)){met.add(node.node_id);activated.add(node.node_id);}
      for(const document of list(state.evaluation?.documents))if(document.review_state==='sufficient')received.add(document.document_type);
      for(const obligation of list(state.obligations))required.add(obligation.document_type);
    }
    return {head,graph,nodes,files:[...grouped.values()],fileById,factFiles,read,received,met,evidence,required,activated,laws,operationNodes,reuse,documents:list(head.obligations),counts:{documents:known?read.size:null,facts:known?facts:null,rules:known?rules:null,met:met.size,total:nodes.length}};
  }
  function deskDraftBinding(state) {
    const draft=state.outcome?.request_draft;
    return draft?.status==='prepared_not_sent' && (typeof draft.subject==='string' || typeof draft.body==='string') ? {contract:'casepath.local-draft/1',claim_id:state.claim_id,subject:text(draft.subject),body:text(draft.body),status:draft.status} : null;
  }
  function checkedDeskDraft(value, binding) {
    if (!value || value.contract!=='casepath.local-draft/1' || value.binding!==binding || typeof value.subject!=='string' || value.subject.length>500 || typeof value.body!=='string' || value.body.length>50000 || !Number.isFinite(Date.parse(value.saved_at))) return null;
    return {subject:value.subject,body:value.body,saved_at:value.saved_at};
  }
  const DESK_LEGAL_TESTS = Object.freeze({
    residential_tenancy_scope:'It is a residential tenancy',
    objective_use_impairment:'The defect really impairs use of the flat',
    outside_small_tenant_maintenance_and_no_tenant_cause:'Not a minor tenant repair, and not caused by the tenant',
    landlord_first_knowledge:'The landlord knew about the defect',
    continuing_defect_without_remedy:'The defect continues without a lasting repair',
    canton_approved_form:'Notice given on the canton-approved form',
    complete_channel_archive:'Every delivery channel is on file',
    issuer_authority_and_received_packet:'Sent by someone authorised, complete notice received',
    issuer_authority_and_complete_packet:'Sent by someone authorised, complete form received',
    contemporaneous_substantive_reasons:'Reasons given with the increase',
    ordinary_non269c_tenancy:'Ordinary lease, no staged rent',
    later_email_is_not_original_reasons:'A later email cannot supply the missing reasons'
  });
  const deskLegalLabel = id => DESK_LEGAL_TESTS[id] || words(id);
  const DESK_STEPS = Object.freeze({
    dh_intake:'Read the reported defect',dh_scope:'Check the tenancy terms',dh_notice:'Check what the landlord knew',dh_cause:'Check what caused the defect',dh_evidence:'Check the evidence of the defect',dh_response:'Check repair and rent reduction',
    lt_intake:'Read the received termination documents',lt_form:'Check whether the termination notice is valid',
    ri_intake:'Read the original increase documents',ri_form:'Check the context of the notice',ri_reason:'Check whether the increase notice is valid'
  });
  const deskStepLabel = node => DESK_STEPS[node?.node_id] || String(node?.label || node?.title || words(node?.node_id)).replace(/^Capture /u,'Read ').replace(/^Establish /u,'Check ').replace(/^Assess /u,'Check ').replace(/^Record /u,'Explain ').replace(/\bpacket\b/giu,'documents').replace(/\bassessment\b/giu,'answer');
  function deskLegalStatus(predicates) {
    const total=predicates.length,failed=predicates.filter(row=>row.status==='failed'),open=predicates.filter(row=>!['failed','supported'].includes(row.status));
    return {failed,open,label:failed.length?`${failed.length} of ${total} legal tests not met`:open.length?`${open.length} of ${total} legal tests still open`:total?`All ${total} legal tests met`:'No legal tests available'};
  }
  function agentDeskMarkup(state, projection, selected, events, context, presentation) {
    const trace=presentation.operations,model=deskOperationModel(state,trace),finished=Boolean(state.outcome&&(!trace||trace.finished)),tour=presentation.tour;
    const index=REFERENCE_DEMO_CASES.findIndex(row=>row.claim_id===state.claim_id),roster=tour?.single?REFERENCE_DEMO_CASES:tour?.cases||REFERENCE_DEMO_CASES;
    const selection=presentation.deskSelection,selectedNode=presentation.chosenNode,selectedDocument=selection?.document || (selectedNode?context?.document:null),inspecting=Boolean(selectedNode||selectedDocument||selection);
    const rows=list(trace?.rows),file=selection?.artifact_id&&model.files.find(row=>row.ids.includes(selection.artifact_id));
    const relevant=selection?.operation?rows.find(row=>row.id===selection.operation):file?rows.findLast(row=>row.source&&file.ids.includes(row.source.artifact_id))||rows.findLast(row=>row.kind==='source.open'&&file.ids.includes(row.object.id)):selectedDocument?rows.findLast(row=>row.kind==='document.check'&&row.object.id===selectedDocument&&row.source)||rows.findLast(row=>row.kind==='fact.extract'&&row.input?.document_type===selectedDocument&&row.source):selectedNode?model.evidence.get(selectedNode):null;
    const operation=inspecting?relevant:trace?.current,read=operation?.source,source=read&&trace?.sources?.get(read.artifact_id)||(operation?.kind==='source.open'&&trace?.sources?.get(operation.object.id)),nodeId=operation&&model.operationNodes.get(operation.id),node=model.nodes.find(row=>row.node_id===nodeId);
    const result=finished&&!inspecting,counts=model.counts,currentFile=model.fileById.get(read?.artifact_id||operation?.object?.id),docLabel=type=>(list(model.graph?.document_catalog).find(row=>row.document_type===type)||model.documents.find(row=>row.document_type===type))?.label||words(type);
    const metric=(id,value,label)=>`<div class="au-desk-metric" data-au-desk-metric="${id}"><span class="au-desk-number">${value??'—'}</span><span class="au-desk-metric-label">${label}</span></div>`;
    const transport=presentation.playing||presentation.paused?`${button(presentation.playing?'Pause':'Resume',presentation.playing?'data-au-demo-stop':'data-au-demo-resume')} ${button('Skip to answer','data-au-operation-skip')}`:finished?button('Watch this case','data-au-desk-watch'):'';
    const files=model.files.map(file=>{const customer=file.source.role==='customer_message',active=!finished&&currentFile===file.key,status=customer?'read':active?'reading':model.read.has(file.key)?'read':'waiting',facts=model.factFiles.get(file.key)||0;return `<li data-au-desk-file="${h(file.key)}" data-au-desk-file-state="${status}" data-au-desk-file-selected="${Boolean(inspecting&&currentFile===file.key || selection?.artifact_id&&file.ids.includes(selection.artifact_id))}"><span class="au-desk-file-dot" aria-hidden="true">${status==='read'?'✓':''}</span><button type="button" class="au-link" data-au-desk-file-select="${h(file.ids.at(-1))}" title="${h(file.source.file_name)}">${h(customer?'Customer’s message':deskFileLabel(file.source))}</button><span class="au-desk-file-meta">${customer?'Their request':facts?`${facts} fact${facts===1?'':'s'}`:status==='reading'?'Reading':status==='read'?'Read':'Waiting'}</span></li>`;}).join('');
    const steps=model.nodes.map((step,i)=>{const done=model.met.has(step.node_id),active=!done&&nodeId===step.node_id;return `<li data-au-desk-requirement="${h(step.node_id)}" data-au-desk-done="${done}" data-au-desk-active="${active}" data-au-desk-admitted="${model.activated.has(step.node_id)}"><span class="au-desk-edge"></span><span class="au-desk-junction" aria-hidden="true">${done?'✓':active?'•':''}</span><button type="button" class="au-link au-desk-node-label" data-au-desk-select="${h(step.node_id)}" aria-pressed="${selectedNode===step.node_id}">${h(deskStepLabel(step))}</button><div class="au-desk-node-evidence">${list(step.document_types).map(type=>`<button type="button" class="au-link" data-au-desk-document-select="${h(type)}" data-au-desk-received="${model.received.has(type)}">${h(docLabel(type))}${model.received.has(type)?' — received ✓':model.required.has(type)?' — needed':''}</button>`).join('')}<span class="au-desk-law">${h(deskLaw([...(model.laws.get(step.node_id)||[])]))}</span></div></li>`;}).join('');
    const predicate=operation?.kind==='fact.extract'&&Array.isArray(operation.input?.rule_refs),checker=operation?.result?.verification_required===false,role=result?'rulebook':operation?.kind==='fact.extract'?checker?'checker':'reader':operation?.kind==='document.check'?'checker':operation?.kind==='step.complete'?'rulebook':operation?.kind==='knowledge.reuse'?'memory':'casepath';
    const action=result?'writes the answer':inspecting?(source?`opens ${deskFileLabel(source)}`:'reads the customer’s message'):operation?.kind==='fact.extract'?checker?'confirms the wording':predicate?'checks it against the law':'finds a fact':operation?.kind==='document.check'?`accepts ${docLabel(operation.object.id)}`:operation?.kind==='step.complete'?'completes a step':operation?.kind==='knowledge.reuse'?'uses an earlier checklist':operation?.kind==='source.open'?`opens ${deskFileLabel(source||{})}`:'reads the customer’s message';
    const predicateState=finished?list(state.outcome?.legal_predicates).find(row=>row.predicate_id===operation?.object?.id)?.status:null;
    const caption=operation?.kind==='step.complete'?`Source for → <strong>${h(deskStepLabel(node))}</strong>`:predicate?`${predicateState==='supported'?'Meets':predicateState==='failed'?'Does not meet':'Checks'} → <strong data-au-legal-label="${h(operation.object.id)}">${h(deskLegalLabel(operation.object.id))}</strong> (${h(deskLaw(operation.input.rule_refs))})`:operation?.input?.document_type||operation?.kind==='document.check'?`Proves → <strong>${h(docLabel(operation.input?.document_type||operation.object.id))}</strong>`:'';
    const landing=caption?`${caption}${node&&operation?.kind!=='step.complete'?`<span>for step ${model.nodes.indexOf(node)+1}: ${h(deskStepLabel(node))}</span>`:''}`:'';
    const chars=source&&sourceCharacters(source),pin=read&&chars&&chars.slice(read.start_char,read.end_char).join('')===read.quote?read:null;
    const sourceText=chars?pin?`${h(chars.slice(0,pin.start_char).join(''))}<mark data-au-desk-quote="${h(operation.id)}" data-au-operation-start-char="${pin.start_char}" data-au-operation-end-char="${pin.end_char}">${h(pin.quote)}</mark>${h(chars.slice(pin.end_char).join(''))}`:h(source.text):h(file?.source.role==='customer_message'||!inspecting?model.head.message||'Opening the case…':'No source is cited for this step.');
    const sourceCard=`<section class="au-desk-source" data-au-desk-source><button type="button" class="au-desk-source-name" ${source?`data-au-source="${h(source.artifact_id)}"${pin?` data-au-citation="${h(JSON.stringify(pin))}" data-au-source-origin="operation:${h(operation.id)}"`:''}`:'disabled'}>${h(source?deskFileLabel(source):file?.source.role==='customer_message'||!inspecting?'Customer’s message':'Source')}</button><div class="au-desk-source-scroll" tabindex="0" aria-label="Source text"><pre class="au-desk-source-text">${sourceText}</pre></div></section>`;
    const outcome=language.outcomePresentation(state),recorded=outcome.recorded,summary=recorded.summary,lead=summary.match(/^.*?[.!?](?=\s|$)/u)?.[0]||summary||outcome.summary,open=[summary.slice(lead.length).trim(),outcome.openItems,...recorded.openFacts,...recorded.missing.map(row=>row.label)].filter(Boolean);
    const predicates=list(state.outcome?.legal_predicates),legal=deskLegalStatus(predicates),testRow=row=>`<li data-au-desk-predicate="${h(row.predicate_id)}" data-status="${h(row.status)}"><span aria-hidden="true">${row.status==='supported'?'✓':row.status==='failed'?'✕':'○'}</span><button type="button" class="au-link" data-au-desk-predicate-source="${h(row.predicate_id)}" data-au-legal-label="${h(row.predicate_id)}">${h(deskLegalLabel(row.predicate_id))}</button><span class="au-desk-law">${h(deskLaw(row.rule_refs))}</span></li>`;
    const tests=`<p class="au-desk-test-status" data-status="${legal.failed.length||legal.open.length?'open':'met'}">${h(legal.label)}</p>${legal.failed.length||legal.open.length?`<ul class="au-desk-tests">${[...legal.failed,...legal.open].map(testRow).join('')}</ul>`:''}`;
    const why=`<details class="au-desk-why" data-au-disclosure="outcome-why"><summary>Show the reasoning</summary><h3>Recorded steps</h3><ol class="au-desk-recorded-steps">${model.nodes.map(step=>`<li>${h(step.label || step.title || words(step.node_id))}</li>`).join('')}</ol><h3>Legal tests</h3><ul class="au-desk-tests">${predicates.map(testRow).join('')}</ul><p>${h(summary)}</p>${outcomeCiteMarkup(state,openableCitations(state,state.outcome),'summary')}${recorded.limits.map(line=>`<p>${h(line)}</p>`).join('')}${recordButton('Full details','outcome')}</details>`;
    const answer=`<section class="au-desk-answer" data-au-desk-answer><h2>Answer</h2>${tests}<p class="au-desk-lead">${h(lead)}</p>${open.length?`<p class="au-desk-open">Still open: ${h([...new Set(open)].join(' '))}</p>`:''}<div class="au-desk-actions">${deskDraftBinding(state)?`${button('Open draft letter','data-au-desk-draft')}<span>Not sent — you decide</span>`:'<span>No draft letter is available.</span>'}</div>${why}</section>`;
    const reuse=model.reuse?`<p class="au-desk-reuse" data-au-desk-reuse="${h(model.reuse.id)}">Uses the ${h((DOMAINS.find(row=>row.id===model.graph?.family)?.label||procedureLabel({family:model.graph?.family})).toLowerCase())} checklist learned from earlier cases</p>`:'';
    return `<section class="au-agent-desk" data-au-agent-desk data-au-tour="${Boolean(tour)}" data-au-story="${h(presentation.storyPhase||'work')}" data-au-playing="${Boolean(presentation.playing)}" data-au-revision="${state.revision}" data-au-state-sha="${h(state.state_sha256)}"><header class="au-desk-case"><div><h1 class="au-page-heading" data-au-claim-title tabindex="-1">${h(caseLabel(state.claim_id,state.title).primary.replace(/\brecord\b/giu,'documents'))}</h1><p class="au-desk-asks">Wants: <q>${h(deskRequest(model.head.message)||model.head.title)}</q></p><div class="au-desk-controls">${transport}${recordButton('Choose case','demo')}<button type="button" class="au-link" data-au-detail="activity">History</button></div></div><div class="au-desk-tally">${metric('documents',counts.documents,'files read')}${metric('facts',counts.facts,'facts found')}${metric('rules',counts.rules,'checks run')}${metric('met',`${counts.met}/${counts.total}`,'steps done')}<p data-au-desk-trace-status hidden></p></div></header><div class="au-desk-grid"><section class="au-desk-column"><h2>From the customer</h2><ul class="au-desk-files">${files}</ul></section><section class="au-desk-column au-desk-centre"><h2>${result?'For your review':'Reading now'}</h2><div class="au-desk-role" ${result?'hidden':''} data-au-now-id="${h(operation?.id||'')}">${roleBadge(role)}<span data-au-now-copy>${h(action)}</span></div>${result?answer:sourceCard}${!result&&landing?`<p class="au-desk-landing">${landing}</p>`:''}${finished&&inspecting?button('Back to the answer','data-au-desk-result'):''}</section><section class="au-desk-column au-desk-handler"><h2>Steps</h2>${reuse}<ol class="au-desk-requirements">${steps}</ol>${finished?`<nav class="au-desk-inspect" aria-label="Case views">${['documents','knowledge','sources'].map(id=>button(words(id),`data-au-detail="${id}"`)).join('')}</nav>`:''}</section></div><footer class="au-desk-footer" data-au-demo-position="${index+1}"><span>Case ${index+1} of ${roster.length}</span><span class="au-desk-pips" aria-hidden="true">${roster.map((_,i)=>`<i data-state="${i<index?'done':i===index?'now':'waiting'}"></i>`).join('')}</span><span class="au-desk-progress"><i style="transform:scaleX(${(index+(counts.total?counts.met/counts.total:0))/roster.length})"></i></span><span>All cases are fictional.</span></footer></section>`;
  }
  function workMarkup(state, projection, selected, events, detail = 'step', context = {}, presentation = {}) {
    if (presentation.desk && detail==='step' && (presentation.operations?.headState?.graph || state.outcome && REFERENCE_DEMO_CASES.some(row=>row.claim_id===state.claim_id))) return agentDeskMarkup(state,projection,selected,events,context,presentation);
    if (!presentation.operations && presentation.operationOpening) presentation = {...presentation,operations:{opening:true,rows:[],sources:new Map()}};
    const reference = referenceExecution(state), availability = claimAvailability(presentation.status || null,state,projection);
    const canWrite = !presentation.readOnly && presentation.writable !== false && writable(presentation.status) && presentation.mode !== 'replay';
    presentation = {...presentation,availability:{...presentation.availability,...(!intakeEligible(projection) || REFERENCE_DEMO_CASES.some(row => row.claim_id === state.claim_id) || !canWrite ? {ready:false,reason:availability.reason} : {})}};
    const fact = evidenceRelationships(state,selected,context).fact;
    const freshness = assessmentFreshness(state);
    const failure = state.deferral?.reason;
    const openFacts = state.outcome && !failure && language.draftStatus(state.outcome).status === 'no_gap' ? language.outcomePresentation(state).recorded.openFacts : [];
    const constraint = freshness.status === 'prior' ? 'New documents await checking.' : failure ? `${stopReason(state)} Open Details for the recorded reason.`.trim() : openFacts.length ? `Open: ${openFactsSentence(openFacts)}.` : stopReason(state);
    const stageView = (Boolean(presentation.operations) || referenceAssessmentComplete(state)) && detail === 'step';
    const trace = presentation.operations, transportTrace = presentation.transportOperations || trace, resultAvailable = transportTrace?.buffer?.result?.exact_output_verified === true && transportTrace.buffer.result.state_sha256 === transportTrace.binding?.current_state_sha256 && transportTrace.buffer.result.current_event_sha256 === transportTrace.binding?.current_event_sha256;
    const stageGraph=operationStageGraph(trace,state), stageHTML=stageGraph ? list(stageGraph.nodes).map(node=>stageNodeContents(node,state,trace,workingProcessState(trace),false)).join('') : '';
    const slots=[...stageHTML.matchAll(/<div class="au-stage-slot"([^>]*)>/g)].map(row=>({type:row[1].match(/data-au-stage-document="([^"]+)"/)?.[1],active:row[1].includes('data-au-document-active="true"'),checked:row[1].includes('data-au-document-checked="true"')}));
    const requiredCount=new Set(slots.filter(row=>row.active).map(row=>row.type)).size, checkedCount=new Set(slots.filter(row=>row.checked).map(row=>row.type)).size;
    const receivedCount = list(transportTrace?.rows).length, totalCount = bufferedOperationCount(transportTrace), operationCount = totalCount || receivedCount, operationIndex = trace?.inspection ? presentation.inspectionIndex : trace?.finished ? Math.max(0,operationCount-1) : Math.max(0,list(transportTrace?.rows).findIndex(row => row.id === trace?.current?.id));
    const transport = trace && !presentation.playing ? `<div class="au-stage-transport" role="group" aria-label="Replay controls"><span class="au-document-total">${requiredCount?`Documents checked ${checkedCount} of ${requiredCount}`:'Document checks appear with each step'}</span>${presentation.tour ? trace.inspection ? button('Result','data-au-inspection-clear') : '' : presentation.playing ? button('Pause','data-au-demo-stop') : presentation.paused ? button('Play','data-au-demo-resume') : trace.inspection ? button('Result','data-au-inspection-clear') : ''}<label class="au-stage-scrubber" style="--au-operation-ticks:${Math.max(1,operationCount)}"><span class="au-visually-hidden">Inspect this step</span><input type="range" data-au-operation-scrub min="0" max="${Math.max(0,operationCount-1)}" step="1" value="${operationIndex}" aria-valuetext="Operation ${operationIndex+1} of ${operationCount}" aria-label="Inspect this step"${operationCount ? '' : ' disabled'}><span class="au-visually-hidden" data-au-scrub-position>${totalCount || transportTrace?.finished ? `${operationCount ? operationIndex+1 : 0} / ${operationCount}` : `${receivedCount} received`}</span></label>${resultAvailable && !transportTrace.finished ? button('Skip to result','data-au-operation-skip') : ''}</div>` : '';
    const playControls = stageView ? '' : (presentation.operations && !presentation.operations.finished ? button('Skip to result','data-au-operation-skip') : '') + (presentation.tour && (presentation.playing || presentation.paused) ? '' : presentation.playing ? button('Pause','data-au-demo-stop') : presentation.paused ? button('Resume','data-au-demo-resume') : presentation.mode === 'replay' && presentation.replay?.current_revision !== 0 ? button(presentation.operations?.finished ? 'Play saved history' : 'Play','data-au-demo-play') : '');
    const panels = [['step','Steps'],['documents','Documents'],['knowledge','Knowledge'],['sources','Sources'],['activity','History']];
    const chosen = panels.some(([id]) => id === detail) ? detail : 'step', publicationFocus = presentation.attention && (!presentation.inspectionHold || presentation.attention.retained) && formingPublication(state,events,presentation.attention), forming = chosen === 'step' && (formingWork(state,presentation) || Boolean(publicationFocus) || Boolean(presentation.operations));
    const body = chosen === 'step' ? forming ? formingMarkup(state,projection,selected,events,context,presentation.knowledge,presentation.attention,false,presentation.operations,presentation.chosenNode) + (!state.graph && !presentation.operations ? intakeMarkup(state,projection) : '') : !state.graph ? openingContentMarkup(state,projection) + intakeMarkup(state,projection) : referenceAssessmentComplete(state) ? formingMarkup(state,projection,selected,events,context,presentation.knowledge,undefined,true,null,presentation.chosenNode) : formingKnowledgeMarkup(state,presentation.knowledge,true) + inspectorMarkup(state,selected,projection,events,context) : chosen === 'documents' ? `<section class="au-documents"><h2>Document checklist</h2>${state.graph ? obligationMarkup(state,selected,undefined,context) + unassignedSourcesMarkup(state) : intakeMarkup(state,projection)}${canWrite && state.revision > 0 ? button('Add supporting files','data-au-add-files') : ''}</section>` : chosen === 'knowledge' ? claimKnowledgeMarkup(state,events,{claims:presentation.claims,knowledge:presentation.knowledge}) : chosen === 'sources' ? sourcesMarkup(state,!canWrite,projection) : `${operationHistoryMarkup(presentation.operations)}${activityMarkup(state,events,projection)}${presentation.replay ? recordButton('Playback details','replay') : ''}`;
    const constraintMarkup = `<p class="au-claim-constraint"><span data-au-claim-status>${h(claimStatusLabel(state.status,state))}.</span>${constraint ? ` ${h(constraint)}` : ''}${failure ? recordButton('Details','outcome') : ''}${state.outcome?.assessment_status === 'complete' && reference && state.outcome.status === 'deferred' ? ' Assessment only; no external action taken.' : ''} <span class="au-read-state" data-au-read-state-label></span></p>`;
    return `<section class="au-quiet-claim" data-au-tour="${Boolean(presentation.tour)}" data-au-story="${h(presentation.storyPhase || 'work')}" data-au-playing="${Boolean(presentation.playing)}" data-au-operation-count="${operationCount}" data-au-operation-position="${operationIndex}" data-au-revision="${h(state.revision)}" data-au-state-sha="${h(state.state_sha256)}"${stageView ? ' data-au-stage-view="true"' : ''}><header class="au-work-head au-focused-claim-head"><div><p class="au-eyebrow"><button type="button" class="au-back-work" data-au-nav="work">Cases</button></p>${claimHeadingMarkup(state,'',presentation.storyPhase === 'opening' ? presentation.tour : null)}${presentation.tour ? '' : `<details class="au-claim-meta" data-au-disclosure="claim-meta"><summary>${['featured','canonical_original'].includes(claimOrigin(state,presentation.origin)) ? 'Fictional case' : 'Case details'}</summary><p class="au-reference-mode" data-au-operation-mode>${h(claimModeLine(state,{...presentation,events}))}</p>${state.outcome && !failure ? constraintMarkup : ''}</details>`}${state.outcome || presentation.tour || failure ? '' : constraintMarkup}</div>${presentation.tour ? '' : `<div class="au-work-controls">${canWrite ? state.revision === 0 || presentation.pendingStart ? startControlMarkup(presentation.availability,presentation.pendingStart) : state.status === 'running' ? button('Pause work','data-au-pause') : state.deferral?.code === 'paused' ? button('Resume work','data-au-resume') : '' : ''}${playControls}${presentation.mode === 'replay' && presentation.replay?.current_revision === 0 ? `<a class="au-link" href="#autonomous/claim/${key(state.claim_id)}" data-au-original-intake>Original intake</a>` : ''}${presentation.mode === 'replay' ? recordButton(transportTrace?.savedFallback || transportTrace?.replayUnavailable ? 'Replay choices' : 'Choose case','demo') : ''}<button type="button" class="au-link" data-au-detail="activity" aria-pressed="${chosen === 'activity'}"${chosen === 'activity' ? ' aria-controls="auPanel-activity"' : ''}>History</button></div>`}</header>${presentation.tour ? demoTransportMarkup(presentation.tour,{...presentation,modeLine:claimModeLine(state,{...presentation,events}),progress:completedStepFraction(state)},stageView ? stagePlaceLabel(state,trace) : '') : ''}${presentation.storyPhase === 'handoff' && presentation.tour?.cases[presentation.tour.index+1] ? `<p class="au-story-handoff" data-au-story-handoff>Next case: ${h(caseLabel(presentation.tour.cases[presentation.tour.index+1].claim_id).primary)}</p>` : ''}${failure ? constraintMarkup : ''}${!stageView || trace?.current && !trace.finished ? nowMarkup(state,events,presentation) : ''}${!stageView && presentation.mode === 'replay' && resultReached(state,presentation) ? knowledgePayoffMarkup(state,presentation.knowledge) : ''}<section class="au-evidence-canvas" data-au-canvas><nav class="au-context-nav" aria-label="Case views">${panels.filter(([id]) => id !== 'activity').map(([id,label],index) => `<button type="button"${index > 2 ? ' class="au-context-utility"' : ''} data-au-detail="${id}" aria-pressed="${chosen === id}"${chosen === id ? ` aria-controls="auPanel-${id}"` : ''}>${label}</button>`).join('')}</nav><div class="au-evidence-stage" data-au-evidence-stage>${!stageView && chosen === 'step' && !active(state.status) && state.outcome?.summary ? `<div class="au-assessment-conclusion">${outcomeSummaryMarkup(state,state.outcome,legalBasisMarkup(state))}</div>` : !stageView && chosen === 'step' && !state.outcome ? legalBasisMarkup(state) : ''}${chosen === 'step' && !forming && !referenceAssessmentComplete(state) && list(state.graph?.nodes).some(node => node.node_id === selected) ? `<h2 class="au-process-question au-reading-question" tabindex="-1" data-au-inspector-heading="${h(selected)}">${h(name(list(state.graph.nodes).find(node => node.node_id === selected)))}</h2>` : ''}${chosen === 'step' && !forming && !referenceAssessmentComplete(state) && state.graph ? `<section class="au-process-hero au-evidence-process" aria-label="Decision neighborhood">${graphMarkup(state,selected,projection)}</section>` : ''}<div class="au-context-body" data-au-context="${h(chosen)}"><section class="au-context-view" id="auPanel-${chosen}" data-au-panel="${chosen}">${body}</section></div>${stageView && !trace?.unrun ? transport : ''}</div></section></section>`;
  }

  function replayIdentityMarkup(record) {
    return `<details class="au-technical-record au-replay-identity"><summary>Verified replay · revision ${h(record.through_seq)} of ${h(record.current_revision)}</summary><dl class="au-chain"><div><dt>Recorded prefix · state</dt><dd class="au-hash">${h(record.state?.state_sha256)}</dd></div><div><dt>Current saved head</dt><dd class="au-hash">${h(record.current_state_sha256)}</dd></div></dl><pre class="au-record-body">${h(JSON.stringify(record.provenance,null,2))}</pre></details>`;
  }
  function knowledgeLink(use, label = 'Open procedure', claimId = '') {
    const id = use.knowledge_id || use.version_id, version = use.version || use.version_id;
    return id && version ? button(label,`data-au-knowledge="${h(id)}" data-au-version="${h(version)}" data-au-knowledge-sha="${h(use.knowledge_sha256 || '')}" data-au-definition-sha="${h(use.definition_sha256 || use.qualification?.definition_sha256 || '')}"${claimId ? ` data-au-knowledge-claim="${h(claimId)}"` : ''}`) : '';
  }
  function reuseDetails(use) {
    const applicability = typeof use.applicability === 'string' ? words(use.applicability) : use.applicability?.summary;
    const observed = [];
    if (Number.isSafeInteger(use.avoided_rule_compilations) && use.avoided_rule_compilations >= 0) observed.push(`${use.avoided_rule_compilations} rebuild${use.avoided_rule_compilations === 1 ? '' : 's'} avoided`);
    if (Number.isSafeInteger(use.avoided_qualification_cases) && use.avoided_qualification_cases >= 0) observed.push(`${use.avoided_qualification_cases} rule checks reused`);
    return `${use.reason || applicability ? `<p>${h(plain(use.reason || applicability,'When it applies is recorded in Details.'))}</p>` : ''}${observed.length ? `<p class="au-meta">${h(observed.join(' · '))}</p>` : ''}<details class="au-technical-record au-reuse-record" data-au-disclosure="reuse:${h(use.knowledge_id || use.version_id || '')}:${h(use.version || use.version_id || '')}:${h(use.workflow_id || use.claim_id || '')}"><summary>Details</summary><pre class="au-record-body">${h(JSON.stringify(use,null,2))}</pre></details>`;
  }
  // Plain words for a recorded branch condition. A constant true has none.
  function conditionSentence(expression, facts = new Map()) {
    if (!expression || typeof expression !== 'object') return '';
    const label = flag => facts.get(`condition:${flag}`)?.label || '';
    if (Object.prototype.hasOwnProperty.call(expression,'const')) return expression.const === false || expression.const === 'false' ? 'never' : '';
    if (expression.flag) return language.conditionClause(expression.flag,label(expression.flag),true);
    if (expression.not) {
      if (expression.not.flag) return language.conditionClause(expression.not.flag,label(expression.not.flag),false);
      if (Object.prototype.hasOwnProperty.call(expression.not,'const')) return expression.not.const === false || expression.not.const === 'false' ? '' : 'never';
      const inner = conditionSentence(expression.not,facts);
      return inner ? `not (${inner})` : '';
    }
    const parts = list(expression.all || expression.any).map(child => conditionSentence(child,facts)).filter(Boolean);
    return parts.join(expression.all ? ' and ' : ' or ');
  }
  const joinWords = (values, last = 'or') => values.length < 2 ? values.join('') : `${values.slice(0,-1).join(', ')} ${last} ${values.at(-1)}`;
  const NON_FLOW_RELATIONS = new Set(['requires','blocks','invalidates','supersedes']);
  // Steps in executable order. Branch conditions come from the recorded edges
  // and the step's own condition; nothing is inferred from labels.
  function libraryStepsMarkup(graph, facts = new Map()) {
    let layout;
    try { layout = layoutGraph(graph); } catch (_) { return '<p class="au-meta">The recorded steps cannot be shown in order.</p>'; }
    if (!layout.nodes.length) return '<p class="au-meta">No steps are recorded.</p>';
    const number = new Map(layout.nodes.map((node,index) => [node.node_id,index+1]));
    return `<ol class="au-library-steps">${layout.nodes.map((node,index) => {
      const incoming = list(graph.edges).filter(edge => edge.target_node_id === node.node_id), flow = incoming.filter(edge => !NON_FLOW_RELATIONS.has(edge.relation));
      const plainSources = [...new Set(flow.filter(edge => !conditionSentence(edge.condition,facts)).map(edge => number.get(edge.source_node_id)))];
      const branches = flow.map(edge => ({source:number.get(edge.source_node_id),clause:conditionSentence(edge.condition,facts)})).filter(row => row.clause);
      const required = incoming.filter(edge => edge.relation === 'requires').map(edge => number.get(edge.source_node_id));
      const own = conditionSentence(node.condition,facts), order = [], conditions = [];
      if (node.entry || !incoming.length) order.push('First step');
      if (!plainSources.length && branches.length === 1) { order.push(`After step ${branches[0].source}`); conditions.push(`Only if ${branches[0].clause}`); }
      else { if (plainSources.length) order.push(`After step ${joinWords(plainSources)}`); for (const row of branches) conditions.push(`After step ${row.source} only if ${row.clause}`); }
      if (required.length) order.push(`Needs step ${joinWords(required,'and')} finished`);
      if (own) conditions.push(`Only if ${own}`);
      const documents = list(node.document_types).map(type => language.documentTitle({document_type:type}));
      // The numbered list already says that a step follows the one before it.
      const sequential = !conditions.length && order.length === 1 && order[0] === (index ? `After step ${index}` : 'First step');
      return `<li data-au-library-step="${h(node.node_id)}"><strong>${h(name(node))}</strong>${order.length && !sequential ? `<p class="au-meta">${h(order.join(' · '))}</p>` : ''}${conditions.map(line => `<p class="au-library-condition">${h(line)}</p>`).join('')}${documents.length ? `<p class="au-meta">Documents: ${h(documents.join(', '))}</p>` : ''}</li>`;
    }).join('')}</ol>`;
  }
  const libraryFamily = item => item?.family || (String(item?.knowledge_id || '').startsWith('procedure.') ? String(item.knowledge_id).slice('procedure.'.length) : '') || item?.candidate?.family || '';
  const LIBRARY_CAPABILITIES = Object.freeze({'local_inbox.read':'Reads the files supplied with the case'});
  // The reusable definition of one saved version, read top to bottom.
  // Conditions are facts a case establishes, so they appear as plain-word
  // branch conditions rather than as facts or bare flags.
  function definitionMarkup(version, options = {}) {
    const graph = version.graph || {nodes:[],edges:[]}, facts = new Map(list(version.facts).map(fact => [fact.fact_id,fact]));
    const catalog = new Map(list(graph.document_catalog).map(item => [item.document_type,item]));
    const nodes = new Map(list(graph.nodes).map(node => [node.node_id,node]));
    let numbers = new Map(); try { numbers = new Map(layoutGraph(graph).nodes.map((node,index) => [node.node_id,index+1])); } catch (_) { /* steps say they cannot be ordered */ }
    const stepName = id => nodes.has(id) ? `Step ${numbers.get(id) ?? '?'} · ${name(nodes.get(id))}` : language.stepLabel(id);
    const used = new Set([...list(graph.edges).flatMap(edge => conditionFlags(edge.condition)),...list(graph.nodes).flatMap(node => conditionFlags(node.condition)),...list(graph.document_catalog).flatMap(item => [item.condition_flag,...conditionFlags(item.condition)].filter(Boolean))]);
    const flags = [...new Set([...Object.keys(graph.conditions || {}),...used])].filter(flag => used.has(flag)), scope = procedureScope(version);
    const applies = `<section class="au-library-applies"><h3>When it applies</h3><p>${h(scope)} cases checked under the same recorded rules.</p>${flags.length ? `<p>Each case establishes from its own documents whether:</p><ul class="au-definition-list">${flags.map(flag => `<li>${h(language.conditionClause(flag,facts.get(`condition:${flag}`)?.label,true))}</li>`).join('')}</ul>` : '<p>No step or document depends on a branch condition; every step applies to each case.</p>'}</section>`;
    const steps = `<section><h3>Steps</h3>${libraryStepsMarkup(graph,facts)}</section>`;
    const evidenceFor = new Map();
    for (const item of list(version.obligations)) for (const id of list(item.required_fact_ids)) { if (!evidenceFor.has(id)) evidenceFor.set(id,[]); evidenceFor.get(id).push(name(item)); }
    const plainFacts = [...facts.values()].filter(fact => !String(fact.fact_id || '').startsWith('condition:'));
    const factsSection = `<section><h3>Facts</h3><ul class="au-definition-list">${plainFacts.map(fact => `<li>${h(language.factLabel(fact))}${evidenceFor.has(fact.fact_id) ? ` <span class="au-meta">· from ${h([...new Set(evidenceFor.get(fact.fact_id))].join(', '))}</span>` : ''}</li>`).join('') || '<li>No facts are recorded.</li>'}</ul></section>`;
    const documents = `<section><h3>Documents</h3><ul class="au-definition-list au-library-documents">${list(version.obligations).map(item => {
      const entry = catalog.get(item.document_type), step = item.decision_node_id || item.node_id;
      const condition = entry?.condition_flag ? language.conditionClause(entry.condition_flag,facts.get(`condition:${entry.condition_flag}`)?.label,true) : conditionSentence(entry?.condition,facts);
      const establishes = list(item.required_fact_ids).map(id => language.factLabel(facts.get(id) || id));
      return `<li data-au-library-document="${h(item.document_type)}"><strong>${h(name(item))}</strong>${step ? `<p class="au-meta">For ${h(stepName(step))}</p>` : ''}${establishes.length ? `<p class="au-meta">Establishes: ${h(establishes.join('; '))}</p>` : ''}${condition ? `<p class="au-library-condition">Only if ${h(condition)}</p>` : ''}${entry?.requirement_class === 'optional' ? '<p class="au-meta">Optional</p>' : ''}</li>`;
    }).join('') || '<li>No documents are recorded.</li>'}</ul></section>`;
    const capabilities = [...new Set(list(version.obligations).map(item => item.capability_id).filter(Boolean))].map(id => LIBRARY_CAPABILITIES[id] || `Uses ${words(id).toLocaleLowerCase()}`);
    const endings = list(graph.nodes).filter(node => node.terminal === true).map(node => `Ends at ${stepName(node.node_id)}`);
    // Limits come from the saved record: its qualification checks and the reuse
    // binding. The definition check covers the reusable steps only; the
    // supporting passages below are the contributing case's own provenance.
    const checks = new Set(list(version.qualification?.checks).map(check => typeof check === 'string' ? check : check?.id).filter(Boolean));
    const branchChecks = version.qualification?.regression_cases;
    const limits = [
      checks.has('admitted_rule_identity') && version.rule_pack_sha256 ? 'Reused only for a case verified as this domain under the same admitted rule version.' : '',
      'A receiving case establishes its own facts and branch conditions from its own documents; reuse does not decide it.',
      checks.has('no_case_values_or_files') ? 'The steps, facts and document checks above hold no values or files from any case; this was checked before saving.' : '',
      flags.length && checks.has('all_ternary_branch_assignments') && Number.isSafeInteger(branchChecks) && branchChecks > 0 ? `Before saving, routing was checked for all ${branchChecks} combinations of recorded condition values.` : ''
    ].filter(Boolean);
    const actions = `<section><h3>Actions and limits</h3><ul class="au-definition-list">${[...capabilities,...endings].map(line => `<li>${h(line)}</li>`).join('') || '<li>No actions are recorded.</li>'}</ul><ul class="au-definition-list au-library-limits">${limits.map(line => `<li>${h(line)}</li>`).join('')}</ul></section>`;
    const passages = list(version.source_evidence).flatMap(row => list(row.citations).filter(citation => typeof citation?.quote === 'string' && citation.quote.trim()).map(citation => ({row,citation})));
    const sourceClaim = version.source_claim_id, label = options.caseTitle ? caseLabel(sourceClaim,{title:options.caseTitle(sourceClaim)}) : caseLabel(sourceClaim);
    const outcomeLimits = list(version.source_outcome?.authority_limits).filter(value => typeof value === 'string' && value.trim());
    const provenance = `<p class="au-library-provenance" data-au-library-provenance>Provenance, not part of the reusable procedure: quoted from the documents of the contributing case${sourceClaim ? `, <cite>${h(label.primary)}</cite>` : ''}. They may show that case's names, addresses and other personal details.</p>`;
    const outcome = outcomeLimits.length ? `<p class="au-library-outcome" data-au-library-outcome><span class="au-meta">Recorded with the contributing case's outcome:</span> ${outcomeLimits.map(line => `“${h(line)}”`).join(' ')}</p>` : '';
    const supporting = `<section class="au-library-supporting"><h3>Supporting passages</h3>${passages.length ? `${provenance}<ul class="au-library-passages">${passages.map(({row,citation},index) => `<li><p class="au-meta">${h(language.documentTitle({document_type:row.document_type}))}${sourceClaim && citation.artifact_id ? ` · <button type="button" class="au-source-link au-library-source" data-au-source="${h(citation.artifact_id)}" data-au-knowledge-source-claim="${h(sourceClaim)}" data-au-source-origin="${h(`library:${version.knowledge_id || ''}:${version.version || ''}:${index}`)}" data-au-citation="${h(JSON.stringify(citation))}">Open source</button>` : ''}</p><blockquote>${h(citation.quote)}</blockquote></li>`).join('')}</ul>` : '<p>No supporting passage is recorded for this version.</p>'}${outcome}</section>`;
    return `<div class="au-procedure-definition">${applies}${steps}${factsSection}${documents}${actions}${supporting}</div>`;
  }
  // Base procedure from the admitted release rule pack. Structural context
  // only: it is never presented as a case result or a saved version.
  function baseOutlineMarkup(family) {
    const outline = list(RELEASE_PROCEDURE_OUTLINE.catalogs).find(row => row.family === family);
    if (!outline) return '<p class="au-meta">No base procedure is recorded for this domain.</p>';
    const graph = {nodes:list(outline.nodes).map((node,index) => ({...node,condition:{const:'true'},entry:!list(outline.transitions).some(edge => edge.target_node_id === node.node_id)})),edges:list(outline.transitions).map(edge => ({...edge,relation:'enables',condition:{const:'true'}}))};
    const numbers = new Map(graph.nodes.map((node,index) => [node.node_id,index+1]));
    try { layoutGraph(graph).nodes.forEach((node,index) => numbers.set(node.node_id,index+1)); } catch (_) { /* outline order */ }
    const step = id => { const node = graph.nodes.find(row => row.node_id === id); return node ? `Step ${numbers.get(id)} · ${name(node)}` : language.stepLabel(id); };
    return `<p class="au-library-context">Structural context from the admitted rule pack. It is not a result for any case.</p><div class="au-procedure-definition"><section><h3>Steps</h3>${libraryStepsMarkup(graph)}</section><section><h3>Documents</h3><ul class="au-definition-list au-library-documents">${list(outline.documents).map(item => `<li data-au-library-document="${h(item.document_type)}"><strong>${h(language.documentTitle({document_type:item.document_type,label:item.label}))}</strong>${list(item.required_at_node_ids).length ? `<p class="au-meta">For ${h(item.required_at_node_ids.map(step).join('; '))}</p>` : ''}</li>`).join('') || '<li>No documents are recorded.</li>'}</ul></section></div>`;
  }
  // One entry per domain: its current qualified version, candidates that were
  // not saved, and the cases that contributed or received each version.
  function knowledgeLibrary(data) {
    const model = knowledgeLearningModel(data), versions = model.versions;
    const families = [...DOMAINS.map(row => row.id),...new Set(versions.map(libraryFamily).filter(id => id && !DOMAINS.some(row => row.id === id)))];
    // Learned entries come first, then candidates, then base procedures.
    const rank = entry => entry.current ? 0 : entry.candidates.length ? 1 : 2;
    return families.map(family => {
      const own = versions.filter(version => libraryFamily(version) === family).sort((a,b) => Number(b.version)-Number(a.version));
      const qualified = own.filter(version => version.qualification?.status === 'qualified');
      const candidates = model.events.filter(event => event.refused && event.family === family);
      return {family,label:procedureScope({family}),versions:own,current:qualified[0] || null,candidates,events:model.events.filter(event => event.family === family && !event.refused)};
    }).map((entry,index) => ({entry,index})).sort((a,b) => rank(a.entry)-rank(b.entry) || a.index-b.index).map(row => row.entry);
  }
  function libraryStatus(entry) {
    if (entry.current) return `Version ${entry.current.version} · qualified · current`;
    if (entry.candidates.length) return `No qualified version · ${entry.candidates.length} candidate${entry.candidates.length === 1 ? '' : 's'} not saved`;
    return 'Base procedure · admitted rule pack · nothing learned yet';
  }
  function libraryEntryMarkup(entry, data, options = {}) {
    const model = knowledgeLearningModel(data), pin = options.pin, exactRequested = pin?.version != null && pin.version !== '', exact = exactRequested ? entry.versions.find(version => knowledgePinMatches(version,pin)) : null;
    // An unavailable exact pin never borrows another version's content.
    if (exactRequested && !exact) return `<article class="au-library-entry" id="au-library-${h(entry.family)}" data-au-library-entry="${h(entry.family)}" data-au-library-unavailable aria-labelledby="au-library-${h(entry.family)}-title"><header class="au-library-entry-head"><h2 id="au-library-${h(entry.family)}-title" tabindex="-1">${h(entry.label)}</h2><p class="au-library-status" data-au-library-status="unavailable">This exact saved version is unavailable in this record.</p></header>${entry.current ? `<p>${knowledgeLink(entry.current,`Open current version ${entry.current.version}`)}</p>` : '<p>No qualified version is recorded for this domain.</p>'}</article>`;
    const shown = exact || entry.current, caseTitle = options.caseTitle || (() => ''), anchor = `au-library-${entry.family}`;
    const caseLink = (id, current = false) => id ? `<button type="button" class="au-secondary au-case-link" data-au-claim="${h(id)}"${current ? ' data-au-current-case="true" aria-current="true"' : ''}>${caseLabelMarkup(caseLabel(id,{title:caseTitle(id)}))}</button>` : '<span>Case not recorded</span>';
    const versionRows = entry.versions.map(version => {
      const qualified = version.qualification?.status === 'qualified', current = version === entry.current, selected = version === shown;
      return `<li${selected ? ' aria-current="true"' : ''} data-au-library-version="${h(version.version)}">${selected ? `<strong>Version ${h(version.version)}</strong>` : knowledgeLink(version,`Version ${version.version}`)} · ${qualified ? 'qualified' : 'candidate · not qualified'}${current ? ' · current' : ''}${version.created_at ? ` · ${h(learningTime({at:version.created_at}))}` : ''}<p class="au-meta">${h(learningChangeSummary(version))}</p></li>`;
    }).concat(entry.candidates.map(event => `<li data-au-library-candidate><span>Candidate · not saved</span>${event.at ? ` · ${h(learningTime(event))}` : ''}<p class="au-meta">${h(language.refusalReason(event.item?.qualification?.reason || event.qualification?.reason || event.item?.reason))}</p></li>`));
    const cases = entry.versions.map(version => {
      const receiving = [...new Set(knowledgeUses(version,model.uses).map(use => use.claim_id).filter(Boolean))];
      return `<li data-au-library-cases="${h(version.version)}"><p class="au-library-cases-version">Version ${h(version.version)}</p><div class="au-library-case-group" data-au-library-contributing><span class="au-meta">Contributed by</span><div class="au-library-case-links">${caseLink(version.source_claim_id,pin?.claim_id && pin.claim_id === version.source_claim_id)}</div></div><div class="au-library-case-group" data-au-library-receiving><span class="au-meta">Received by</span><div class="au-library-case-links">${receiving.map(id => caseLink(id,pin?.claim_id === id)).join('') || '<span>No receiving case is recorded.</span>'}</div></div></li>`;
    }).concat(entry.candidates.map(event => `<li data-au-library-candidate-case><p class="au-library-cases-version">Candidate · not saved</p><div class="au-library-case-group"><span class="au-meta">Proposed by</span><div class="au-library-case-links">${caseLink(event.source_claim_id || event.claim_id || event.item?.source_claim_id)}</div></div></li>`));
    const header = `<header class="au-library-entry-head"><h2 id="${h(anchor)}-title" tabindex="-1">${h(entry.label)}</h2><p class="au-library-status" data-au-library-status="${entry.current ? 'qualified' : entry.candidates.length ? 'candidate' : 'base'}">${h(libraryStatus(entry))}</p>${shown && shown !== entry.current ? `<p class="au-library-shown">Showing version ${h(shown.version)}${entry.current ? ` · ${knowledgeLink(entry.current,`Show current version ${entry.current.version}`)}` : ''}</p>` : ''}${entry.events.length ? `<button type="button" class="au-link au-library-learning" data-au-learning-open="${h(entry.family)}" data-au-learning-version="${h(shown ? `${shown.knowledge_id || shown.version_id}:${shown.version || shown.version_id}` : '')}">How this was learned</button>` : ''}</header>`;
    const body = shown ? `${definitionMarkup(shown,{caseTitle})}<section><h3>Versions</h3><ul class="au-library-versions">${versionRows.join('')}</ul></section><section class="au-library-cases"><h3>Contributing and receiving cases</h3><ul>${cases.join('')}</ul></section>` : `${baseOutlineMarkup(entry.family)}${entry.candidates.length ? `<section><h3>Versions</h3><ul class="au-library-versions">${versionRows.join('')}</ul></section><section class="au-library-cases"><h3>Contributing and receiving cases</h3><ul>${cases.join('')}</ul></section>` : ''}`;
    const identity = shown ? ` data-au-knowledge-identity="${h(`${shown.knowledge_id || shown.version_id}:${shown.version || shown.version_id}`)}" data-au-version="${h(shown.version)}"` : '';
    return `<article class="au-library-entry" id="${h(anchor)}" data-au-library-entry="${h(entry.family)}"${identity} aria-labelledby="${h(anchor)}-title">${header}${body}</article>`;
  }
  function knowledgeLibraryMarkup(data, claims = [], pin = null) {
    const model = knowledgeLearningModel(data), entries = knowledgeLibrary(data), learned = entries.some(entry => entry.current);
    const titles = new Map(list(claims).map(row => [row.claim_id,row.title]));
    for (const event of model.events) { if (event.claim_id && event.claim_title && !titles.has(event.claim_id)) titles.set(event.claim_id,event.claim_title); if (event.source_claim_id && event.source_claim_title && !titles.has(event.source_claim_id)) titles.set(event.source_claim_id,event.source_claim_title); }
    const orphans = model.events.filter(event => event.refused && !entries.some(entry => entry.family === event.family));
    const caseTitle = id => titles.get(id) || '', label = learningLabel(model,claims,false).replace(/^(?:Saved learning|No saved learning yet)/,'Procedure library');
    const indexStatus = entry => { if (!entry.current) return entry.candidates.length ? 'No qualified version' : 'Nothing learned yet'; const receiving = new Set(knowledgeUses(entry.current,model.uses).map(use => use.claim_id).filter(Boolean)).size; return `Version ${entry.current.version} · qualified${receiving ? ` · ${receiving} receiving case${receiving === 1 ? '' : 's'}` : ''}`; };
    const index = `<nav class="au-library-index" aria-label="Procedures">${entries.map(entry => `<button type="button" data-au-library-jump="${h(entry.family)}" aria-controls="au-library-${h(entry.family)}"><strong>${h(entry.label)}</strong><span>${h(indexStatus(entry))}</span></button>`).join('')}</nav>`;
    return `<section class="au-quiet-knowledge au-library" data-au-library><header class="au-work-head"><div><p class="au-learning-label">${h(label)}</p><h1 class="au-page-heading" tabindex="-1">Knowledge</h1></div><div><span class="au-read-state" data-au-knowledge-read-label></span>${button('Retry','data-au-knowledge-retry hidden')}${model.events.length ? button('How this was learned','data-au-learning-open=""') : ''}${recordButton('History','knowledge-index')}</div></header>${learned ? '' : `<p class="au-library-empty">Knowledge forms when a case finishes its checks. <button type="button" class="au-link" data-au-nav="demonstration">Demonstration</button> · <button type="button" class="au-link" data-au-nav="work">Cases</button></p>`}<div class="au-library-layout">${index}<div class="au-library-entries">${entries.map(entry => libraryEntryMarkup(entry,data,{pin:pin && (libraryFamily(pin) === entry.family) ? pin : null,caseTitle})).join('')}${orphans.length ? `<p class="au-meta au-library-orphans">${orphans.length} candidate${orphans.length === 1 ? '' : 's'} not saved · domain not recorded · shown in How this was learned</p>` : ''}</div></div></section>`;
  }
  function lineageMarkup(version, versions = []) {
    const parent = versions.find(item => item.knowledge_sha256 && item.knowledge_sha256 === version.parent_knowledge_sha256);
    return `<div class="au-lineage-summary">${version.change_reason ? `<p>${h(learningChangeSummary(version))}</p><details><summary>Details</summary><p>${h(version.change_reason)}</p></details>` : ''}${version.parent_knowledge_sha256 ? `<p class="au-meta">${parent ? `Derived from version ${h(parent.version || parent.version_id)}` : 'Parent version is not in this record'}${parent?.source_claim_id ? ` · ${button('Open parent source case',`data-au-claim="${h(parent.source_claim_id)}"`)}` : ''}</p>` : '<p class="au-meta">First recorded version</p>'}</div>`;
  }
  function knowledgeUses(version, uses = []) {
    return list(uses).filter(use => {
      if ((use.knowledge_id || use.version_id) !== (version.knowledge_id || version.version_id) || String(use.version ?? use.version_id) !== String(version.version ?? version.version_id)) return false;
      if (Object.prototype.hasOwnProperty.call(use,'knowledge_sha256') && use.knowledge_sha256 != null && (!use.knowledge_sha256 || use.knowledge_sha256 !== version.knowledge_sha256)) return false;
      if (use.definition_sha256 && use.definition_sha256 !== (version.qualification?.definition_sha256 || version.definition_sha256)) return false;
      return true;
    });
  }
  function procedureScope(version) {
    return ({defect_mold_heating:'Defects and repairs',lease_termination_dispute:'Lease termination',rent_increase_dispute:'Rent increases'})[version.family] || words(version.family || version.category || 'Reusable procedure');
  }
  function knowledgeFacetMarkup(version, facet = 'process', versions = []) {
    const graph = version.graph || {nodes:[],edges:[]}, layout = layoutGraph(graph), facts = new Map(list(version.facts).map(fact => [fact.fact_id,fact]));
    // Condition facts are branch questions, shown in plain words under Special cases.
    if (facet === 'facts') return `<div class="au-procedure-facts"><h3>Facts to establish in each case</h3>${[...facts.values()].filter(fact => !String(fact.fact_id || '').startsWith('condition:')).map(fact => `<p>${h(language.factLabel(fact))}</p>`).join('') || '<p>No required facts are recorded.</p>'}</div>`;
    if (facet === 'documents') return `<div class="au-procedure-documents"><h3>Document requirements</h3>${list(version.obligations).map(item => `<article><h4>${h(name(item))}</h4>${list(item.required_fact_ids).length ? `<p>${h(item.required_fact_ids.map(id => name(facts.get(id)) || words(id)).join('; '))}</p>` : ''}</article>`).join('') || '<p>No document requirements are recorded.</p>'}</div>`;
    if (facet === 'exceptions') {
      const conditional = list(graph.document_catalog).filter(item => item.condition_flag || conditionFlags(item.condition).length), conditions = Object.keys(graph.conditions || {});
      const conditionalEdges = list(graph.edges).filter(edge => edge.condition && conditionFlags(edge.condition).length);
      const documentCondition = item => item.condition_flag ? language.conditionClause(item.condition_flag,facts.get(`condition:${item.condition_flag}`)?.label,true) : conditionSentence(item.condition,facts);
      return `<div class="au-procedure-exceptions"><h3>Conditions and exceptions</h3>${conditions.length ? `<p>Each case establishes from its own documents whether:</p><ul class="au-definition-list">${conditions.map(flag => `<li>${h(language.conditionClause(flag,facts.get(`condition:${flag}`)?.label,true))}</li>`).join('')}</ul>` : ''}${conditional.map(item => `<article><h4>${h(name(item))}</h4><p>Only if ${h(documentCondition(item))}</p></article>`).join('')}${conditionalEdges.map(edge => `<p>${h(name(layout.byId.get(edge.source_node_id)))} → ${h(name(layout.byId.get(edge.target_node_id)))} · Only if ${h(conditionSentence(edge.condition,facts))}</p>`).join('')}${!conditions.length && !conditional.length && !conditionalEdges.length ? '<p>No conditional exception is recorded in this version.</p>' : ''}</div>`;
    }
    if (facet === 'changes') {
      const added = list(version.added_document_types), parent = list(versions).find(item => item.knowledge_sha256 === version.parent_knowledge_sha256);
      return `<div class="au-procedure-changes"><h3>What changed</h3>${version.change_reason?`<p data-au-change-reason>${h(learningChangeSummary(version))}</p><details><summary>Details</summary><p>${h(version.change_reason)}</p></details>`:''}${parent ? `<p>From version ${h(parent.version || parent.version_id)} to version ${h(version.version || version.version_id)}.</p>` : '<p>First recorded version.</p>'}${added.map(type => { const recipe = list(version.evidence_recipes).find(item => item.document_type === type), requirement = list(version.obligations).find(item => item.document_type === type); return `<article><h4>${h(name(requirement) || words(type))}</h4>${recipe?.summary ? `<p>Document checks are saved for this version.</p><details><summary>Details</summary><p>${h(recipe.summary)}</p></details>` : ''}${list(recipe?.required_fields).length ? `<p>${h(recipe.required_fields.map(field => words(field)).join('; '))}</p>` : ''}</article>`; }).join('')}${!added.length && parent ? '<p>No added document requirement is recorded for this version.</p>' : ''}</div>`;
    }
    return `<div class="au-procedure-process" role="group" aria-label="Reusable process">${layout.rows.map((row,rank) => `<div class="au-procedure-rank" data-au-procedure-rank="${rank}" style="--au-learning-rank:${rank}">${row.map(node => `<article class="au-procedure-stage" data-au-procedure-node="${h(node.node_id)}"><h3>${h(name(node))}</h3>${layout.parents.get(node.node_id).length ? `<p>${h(layout.parents.get(node.node_id).map(id => name(layout.byId.get(id))).join(' + '))}</p>` : ''}</article>`).join('')}</div>`).join('') || '<p>No process definition is recorded.</p>'}</div>`;
  }
  function readKnowledge(data) {
    if (!data || !Array.isArray(data.versions) || data.uses !== undefined && !Array.isArray(data.uses) || data.quarantined !== undefined && !Array.isArray(data.quarantined)) throw new Error('The recorded knowledge response is incomplete.');
    return data;
  }
  const learningModels = new WeakMap();
  const learningChecks = Object.freeze({admitted_rule_identity:'Matches the recorded rules',no_case_values_or_files:'Steps and checks hold no case values or files',all_ternary_branch_assignments:'All rule combinations checked',graph_and_checklist_equivalence:'Steps and document list agree',source_bound_proposer_and_verifier:'Reading and checking link to sources',exact_required_evidence_fields:'Required document details match',verified_sufficient_source_binding:'Checked sources support the result'});
  function knowledgePinMatches(version, pin) {
    return Boolean(version && pin && String(version.knowledge_id || version.version_id) === String(pin.knowledge_id) && String(version.version || version.version_id) === String(pin.version) && (!pin.knowledge_sha256 || version.knowledge_sha256 === pin.knowledge_sha256) && (!pin.definition_sha256 || (version.qualification?.definition_sha256 || version.definition_sha256) === pin.definition_sha256));
  }
  function knowledgeLearningModel(data) {
    if (learningModels.has(data)) return learningModels.get(data);
    const versions = list(data.versions), uses = list(data.uses), quarantined = list(data.quarantined);
    const projected = list(data.learning_replay?.events), events = [];
    for (const [index, row] of projected.entries()) {
      if (!['knowledge.published','knowledge.used'].includes(row.kind)) continue;
      const version = versions.find(item => knowledgePinMatches(item,row));
      // A use without an exact public pin cannot borrow the family's latest graph.
      const pinned = row.pin_status !== 'unavailable' && Boolean(row.knowledge_sha256 && row.definition_sha256);
      const refused = row.projection_status === 'quarantined' || row.qualification?.status === 'quarantined';
      const quarantine = refused ? quarantined[row.quarantine_index] || row : null;
      const item = row.kind === 'knowledge.used' ? {...uses.find(use => use.claim_id === row.claim_id && knowledgePinMatches(use,row)),...row} : quarantine || version || row;
      events.push({...row,id:String(row.event_id || `unindexed-event:${index}`),at:row.at || null,versionRecord:row.kind === 'knowledge.used' && !pinned ? null : version,item,refused,recorded:Boolean(row.event_id),family:row.family || version?.family || item.family || 'other'});
    }
    // Older cached/fixture responses still expose all their actual records. They
    // explicitly have no journal event identity or globally ordered timestamp.
    for (const [index, version] of versions.entries()) if (!events.some(row => row.kind === 'knowledge.published' && !row.refused && row.versionRecord === version)) events.push({id:`unindexed-version:${index}`,kind:'knowledge.published',at:null,versionRecord:version,item:version,family:version.family || 'other',recorded:false,source_claim_id:version.source_claim_id});
    if (!projected.length) {
      for (const [index,use] of uses.entries()) events.push({...use,id:`unindexed-use:${index}`,kind:'knowledge.used',at:null,versionRecord:use.knowledge_sha256 ? versions.find(version => knowledgePinMatches(version,use)) : null,item:use,family:versions.find(version => knowledgePinMatches(version,use))?.family || use.family || 'other',recorded:false});
      for (const [index,item] of quarantined.entries()) events.push({id:`unindexed-refused:${index}`,kind:'knowledge.published',at:null,item,refused:true,quarantine_index:index,family:item.family || 'other',recorded:false,source_claim_id:item.source_claim_id});
    } else for (const [index,item] of quarantined.entries()) if (!events.some(row => row.refused && row.quarantine_index === index)) events.push({id:`unindexed-refused:${index}`,kind:'knowledge.published',at:null,item,refused:true,quarantine_index:index,family:item.family || 'other',recorded:false,source_claim_id:item.source_claim_id});
    events.sort((a,b) => (learningDay(a)==='unordered'?1:0)-(learningDay(b)==='unordered'?1:0) || (a.at && b.at ? Date.parse(a.at)-Date.parse(b.at) : 0));
    const reuseGroups=new Map();
    for(const [index,event] of events.entries()) {if(event.kind!=='knowledge.used')continue;const key=[event.knowledge_id,event.version,event.knowledge_sha256,event.definition_sha256,learningDay(event)].join(':');if(!reuseGroups.has(key))reuseGroups.set(key,[]);reuseGroups.get(key).push(index);event.reuseGroup=reuseGroups.get(key);}
    const requalificationGroups=new Map();
    for(const [index,event] of events.entries()){if(event.refused || event.kind!=='knowledge.published' || !event.item.parent_knowledge_sha256 || !String(event.item.change_reason || '').startsWith('Requalified ') || learningDay(event)==='unordered')continue;const key=[event.item.change_reason,new Date(event.at).toISOString().slice(0,16)].join(':');if(!requalificationGroups.has(key))requalificationGroups.set(key,[]);requalificationGroups.get(key).push(index);event.requalificationGroup=requalificationGroups.get(key);}
    const frames = [];
    for (const [index,event] of events.entries()) {
      if(event.reuseGroup && event.reuseGroup[0]!==index || event.requalificationGroup && event.requalificationGroup[0]!==index)continue;
      const stages = event.refused || event.kind === 'knowledge.used' ? [10] : [0,1,2,...list(event.item.qualification?.checks).map((_,i)=>3+i),10];
      // Reading holds are presentation time, independent of journal timestamps.
      for (const stage of stages) frames.push({index,stage,duration:event.refused || event.kind==='knowledge.used'?1000:stage===0?700:stage===1?900:stage===2?700:stage===10?500:100});
    }
    const totals = data.learning_replay?.totals || {recorded_uses:uses.length,receiving_claims:new Set(uses.map(use=>use.claim_id).filter(Boolean)).size,avoided_rule_compilations:uses.reduce((sum,use)=>sum+(Number.isSafeInteger(use.avoided_rule_compilations) ? use.avoided_rule_compilations : 0),0)};
    const model = {events,frames,versions,uses,quarantined,totals}; learningModels.set(data,model); return model;
  }
  function learningFrameStart(model, index, stage = 10, completed = false) {
    if(completed)return {frame:0,alias:null};
    let frame=model.frames.findIndex(row=>row.index===index && row.stage>=stage);
    if(frame>=0)return {frame,alias:null};
    const event=model.events[index],representative=event?.reuseGroup?.[0] ?? event?.requalificationGroup?.[0];
    frame=model.frames.findIndex(row=>row.index===representative && row.stage>=stage);
    return frame>=0?{frame,alias:{representative,index}}:{frame:0,alias:null};
  }
  function learningDay(event) { return event.at && Number.isFinite(Date.parse(event.at)) ? new Date(event.at).toISOString().slice(0,10) : 'unordered'; }
  function learningEventLabel(event) {
    return event.refused ? 'Not saved' : event.kind === 'knowledge.used' ? `Reused · v${event.version || event.item.version || '?'}` : `${String(event.item.change_reason || '').startsWith('Requalified ')?'Rechecked':event.item.parent_knowledge_sha256 ? 'Updated' : 'Saved'} · v${event.item.version || event.item.version_id || '?'}`;
  }
  function learningTimelineProcedure(event) {
    const item=event.versionRecord || event.item, id=item.knowledge_id || '', family=item.family || event.family || (id.startsWith('procedure.')?id.slice('procedure.'.length):'');
    return DOMAINS.some(domain=>domain.id===family) ? procedureLabel({...item,family}) : 'Procedure not accepted';
  }
  let learningTimeFormat;
  function learningTime(event) {
    if (!event.at || !Number.isFinite(Date.parse(event.at))) return 'Timestamp unavailable · unordered';
    return (learningTimeFormat ||= new Intl.DateTimeFormat('en-GB',{timeZone:'UTC',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false})).format(new Date(event.at))+' UTC';
  }
  function learningPinAttributes(item) {
    return item?.knowledge_id && item?.version ? ` data-au-knowledge="${h(item.knowledge_id)}" data-au-version="${h(item.version)}" data-au-knowledge-sha="${h(item.knowledge_sha256 || '')}" data-au-definition-sha="${h(item.definition_sha256 || item.qualification?.definition_sha256 || '')}"` : '';
  }
  function caseLabelMarkup(label) { return `<span class="au-case-label">${h(label.primary)}</span>${label.secondary ? `<span class="au-case-subject">${h(label.secondary)}</span>` : ''}`; }
  function learningClaimLink(id, title) { return id ? `<button type="button" class="au-secondary au-case-link" data-au-claim="${h(id)}">${caseLabelMarkup(caseLabel(id,{title}))}</button>` : '<span>Source case unavailable</span>'; }
  function learningDefinitionDiff(version, versions) {
    const parent = versions.find(item => item.knowledge_sha256 && item.knowledge_sha256 === version.parent_knowledge_sha256);
    if (!parent) return '';
    const before = list(parent.graph?.nodes), after = list(version.graph?.nodes), removed = before.filter(node=>!after.some(row=>row.node_id===node.node_id)), added = after.filter(node=>!before.some(row=>row.node_id===node.node_id));
    const edgesBefore = list(parent.graph?.edges), edgesAfter = list(version.graph?.edges);
    const checklist=record=>list(record.obligations).map(item=>`<li>${h(name(item))}</li>`).join('') || '<li>No document requirements recorded.</li>';
    const connections=record=>list(record.graph?.edges).map(edge=>`<li>${h(name(list(record.graph?.nodes).find(node=>node.node_id===edge.source_node_id)) || edge.source_node_id)} → ${h(name(list(record.graph?.nodes).find(node=>node.node_id===edge.target_node_id)) || edge.target_node_id)}</li>`).join('') || '<li>No connections recorded.</li>';
    return `<section class="au-learning-diff"><h3>Recorded process change</h3><p>${before.length} → ${after.length} process steps · ${edgesBefore.length} → ${edgesAfter.length} connections</p><div class="au-learning-compare"><div><h4>Before · Version ${h(parent.version)}</h4><ol>${before.map(node=>`<li${removed.includes(node) ? ' data-au-diff="removed"' : ''}>${h(name(node))}</li>`).join('')}</ol><h4>Document checklist · before</h4><ul>${checklist(parent)}</ul>${knowledgeLink(parent,'Open parent version')}</div><div><h4>After · Version ${h(version.version)}</h4><ol>${after.map(node=>`<li${added.includes(node) ? ' data-au-diff="added"' : ''}>${h(name(node))}</li>`).join('')}</ol><h4>Document checklist · after</h4><ul>${checklist(version)}</ul></div></div><details><summary>Recorded connections before and after</summary><div class="au-learning-compare"><ul>${connections(parent)}</ul><ul>${connections(version)}</ul></div></details></section>`;
  }
  function learningChangeSummary(version) {
    if(!version.parent_knowledge_sha256)return 'First saved version.';
    if(String(version.change_reason || '').startsWith('Requalified '))return 'Rechecked against the recorded rules.';
    const added=list(version.added_document_types).map(type=>name(list(version.obligations).find(row=>row.document_type===type)) || name(list(version.graph?.document_catalog).find(row=>row.document_type===type)) || words(type));
    return added.length?`${added.join(', ')} document check${added.length===1?'':'s'} added.`:'Saved steps updated.';
  }
  function learningProcessMarkup(version) {
    const layout=layoutGraph(version.graph || {nodes:[],edges:[]}),positions=new Map(layout.nodes.map((node,index)=>[node.node_id,index+1]));
    return `<div class="au-learning-process-map"><ol>${layout.nodes.map((node,index)=>`<li data-au-procedure-node="${h(node.node_id)}" style="--au-learning-rank:${index}"><h3><span>${index+1}.</span> ${h(name(node))}</h3>${list(layout.parents.get(node.node_id)).length?`<p>After ${h(layout.parents.get(node.node_id).map(id=>positions.get(id)).join(' + '))}</p>`:'<p>Entry step</p>'}</li>`).join('') || '<li>No process definition recorded.</li>'}</ol></div>`;
  }
  function learningRecipesMarkup(version, event) {
    const reused = event.kind === 'knowledge.used', recipeTypes = Number.isSafeInteger(event.item.reused_evidence_recipes) && event.item.reused_evidence_recipes===list(version.evidence_recipes).length ? list(version.evidence_recipes).map(row=>row.document_type) : list(event.item.reused_evidence_recipes);
    return `<ul class="au-learning-checklist">${list(version.obligations).map((item,index)=>{ const recipe=list(version.evidence_recipes).find(row=>row.document_type===item.document_type), relevant = reused && recipeTypes.some(row=>(typeof row==='string'?row:row.document_type)===item.document_type); return `<li style="--au-learning-document:${index}" data-au-learning-document="${h(item.document_type)}" data-au-recipe-reused="${relevant}" data-au-learning-added="${list(version.added_document_types).includes(item.document_type)}"><span aria-hidden="true">${relevant?'↪':'□'}</span><div><strong>${h(name(item))}</strong>${recipe?.summary?`<p>${relevant?'Document check reused.':'Document checks are saved for this version.'}</p><details><summary>Details</summary><p>${h(recipe.summary)}</p></details>`:''}${list(recipe?.required_fields).length?`<p>${h(recipe.required_fields.map(field=>plain(words(field),'Recorded field')).join(' · '))}</p>`:''}</div></li>`; }).join('') || '<li>No document requirements recorded.</li>'}</ul>`;
  }
  function learningReceiptsMarkup(model,event) {
    const group=list(event.reuseGroup).map(index=>({event:model.events[index],index}));
    return group.length?`<section class="au-learning-receipts"><h3>${group.length} recorded reuse receipts</h3><ul>${group.map(({event:row,index})=>`<li${row.claim_id===event.claim_id?' data-au-current-case="true"':''}><button type="button" data-au-learning-event="${index}"${learningPinAttributes(row.versionRecord || row.item)}>${(()=>{const label=row.claim_id?caseLabel(row.claim_id,{title:row.claim_title}):{primary:'Receiving case',secondary:''};return `<span class="au-case-label">${row.claim_id===event.claim_id?'This case · ':''}${h(label.primary)}</span><span class="au-case-subject">${label.secondary?`${h(label.secondary)} · `:''}${h(learningTime(row))}</span>`;})()}</button> ${row.recorded?recordButton('Inspect receipt','learning-event',row.id):''}</li>`).join('')}</ul></section>`:'';
  }
  function knowledgeLearningFocus(model, event, facet = 'process') {
    if (!event) return '<p class="au-empty">No recorded learning events are available.</p>';
    const version=event.versionRecord, item=event.item, use=event.kind==='knowledge.used', identity=version ? `${version.knowledge_id || version.version_id}:${version.version || version.version_id}` : '';
    const memory=language.knowledgePresentation(version || item,event), reason=item.qualification?.reason || event.qualification?.reason || item.reason;
    if (event.refused) return `<article class="au-learning-refusal" data-au-learning-stage="10">${knowledgeNowMarkup(model,event)}<h2>${h(DOMAINS.some(row=>row.id===event.family)?procedureLabel({family:event.family}):'Procedure not accepted')}</h2><p>${h(learningTime(event))}</p><blockquote class="au-learning-refusal-reason">${h(language.refusalReason(reason))}</blockquote><details><summary>Details</summary><blockquote>${h(reason || 'No reason is recorded.')}</blockquote></details>${learningClaimLink(event.claim_id || event.source_claim_id || item.source_claim_id,event.claim_title || event.source_claim_title)}${recordButton('Details','quarantine',String(event.quarantine_index ?? ''))}${item.knowledge_id && item.version ? knowledgeLink(item,'Open exact version') : ''}</article>`;
    if (!version) return `<article class="au-learning-unavailable">${knowledgeNowMarkup(model,event)}<h2>${h(learningEventLabel(event))}</h2><p>The exact saved version is unavailable in this record.</p><p>${h(learningTime(event))}</p>${learningClaimLink(event.claim_id || item.claim_id,event.claim_title)}${knowledgeLink(item,'Open exact version')}${use?`<p>${Number.isSafeInteger(item.reused_evidence_recipes)?item.reused_evidence_recipes+' document checks reused · ':''}${Number.isSafeInteger(item.avoided_rule_compilations)?item.avoided_rule_compilations+' times reused instead of rebuilding':''}</p>${item.applicability?`<p>When it applies: ${h(plain(typeof item.applicability==='string'?words(item.applicability):item.applicability.summary,'Recorded rule conditions'))}</p>`:''}${learningReceiptsMarkup(model,event)}`:''}</article>`;
    const parent=model.versions.find(row=>row.knowledge_sha256===version.parent_knowledge_sha256), checks=list(version.qualification?.checks), sourceId=event.source_claim_id || version.source_claim_id;
    const facets=[['process','Steps'],['facts','Facts it needs'],['documents','Documents'],['exceptions','Special cases'],['changes','What changed']], selected=facets.some(([id])=>id===facet)?facet:'process';
    const receiving=knowledgeUses(version,model.uses);
    const receipts=use?learningReceiptsMarkup(model,event):'';
    const requalification=list(event.requalificationGroup).length>1?`<section class="au-learning-requalification"><h3>Rechecked rules · ${event.requalificationGroup.length} families</h3><p>${h(learningChangeSummary(version))}</p><ul>${event.requalificationGroup.map(index=>{const row=model.events[index],current=row.versionRecord,prior=model.versions.find(v=>v.knowledge_sha256===current?.parent_knowledge_sha256);return `<li><button type="button" data-au-learning-event="${index}"${learningPinAttributes(current)}>${h(procedureLabel(current || row.item))} · v${h(current?.version)} · ${list(prior?.graph?.nodes).length} → ${list(current?.graph?.nodes).length} steps</button><p>${h(learningTime(row))}</p></li>`;}).join('')}</ul></section>`:'';
    return `<article class="au-procedure-reading au-knowledge-version au-learning-record" data-au-knowledge-identity="${h(identity)}" data-au-version="${h(version.version)}"><header class="au-learning-record-head"><div><h2>${h(procedureLabel(version))} · ${knowledgeLink(version,`Version ${version.version}`)}</h2><p>${h(learningTime(event))}</p>${knowledgeNowMarkup(model,event)}</div></header><section class="au-learning-source" data-au-learning-reveal="0">${use?'':`<p>Source case</p>${learningClaimLink(sourceId,event.source_claim_title || event.claim_title)}`}${!use && !requalification?`<p>${h(learningChangeSummary(version))}</p>`:''}${parent?`<p>Parent ${knowledgeLink(parent,`Version ${parent.version} · exact saved version`)}</p>`:''}</section>${requalification}${use?`<section class="au-learning-reuse" data-au-learning-reveal="1"><div class="au-learning-reuse-arc"><span>Version ${h(version.version)}</span><span aria-hidden="true">⤳</span>${learningClaimLink(event.claim_id || item.claim_id,event.claim_title)}</div>${typeof item.applicability==='string'?`<p>When it applies: ${h(plain(words(item.applicability),'Recorded rule conditions'))}</p>`:item.applicability?.summary?`<p>${h(plain(item.applicability.summary,'When it applies is recorded in Details.'))}</p>`:''}${Number.isSafeInteger(item.avoided_rule_compilations)?`<p>${item.avoided_rule_compilations} rebuild${item.avoided_rule_compilations===1?'':'s'} avoided</p>`:''}${Number.isSafeInteger(item.reused_evidence_recipes)?`<p>${item.reused_evidence_recipes} document checks reused</p>`:''}${event.recorded?`<p class="au-learning-receipt">Recorded reuse ${recordButton('Details','learning-event',event.id)}</p>`:''}</section>`:''}<nav class="au-procedure-facets" aria-label="Procedure details">${facets.map(([id,label])=>`<button type="button" data-au-knowledge-facet="${id}" aria-pressed="${selected===id}">${label}</button>`).join('')}</nav><section class="au-procedure-facet" data-au-knowledge-facet-panel="${selected}" data-au-learning-reveal="${selected==='documents'?2:1}">${selected==='documents'?learningRecipesMarkup(version,event):selected==='process'?learningProcessMarkup(version):knowledgeFacetMarkup(version,selected,model.versions)}${selected==='changes' || requalification?learningDefinitionDiff(version,model.versions):''}</section>${selected!=='documents'?`<section class="au-learning-documents" data-au-learning-reveal="2"><h3>Recorded document checklist</h3>${learningRecipesMarkup(version,event)}</section>`:''}${use?receipts:''}${!use?`<details class="au-learning-proof" data-au-learning-proof><summary>Details</summary><section class="au-learning-qualification" data-au-learning-reveal="3"><h3>Recorded qualification</h3><ul>${checks.map((check,index)=>`<li data-au-learning-check="${index}"><span class="au-learning-check-symbol" aria-hidden="true">✓</span>${h(learningChecks[typeof check==='string'?check:check.id] || words(typeof check==='string'?check:check.label || check.id))}</li>`).join('') || '<li>No qualification checks recorded.</li>'}</ul>${Number.isSafeInteger(version.qualification?.regression_cases)?`<p>${version.qualification.regression_cases} checked rule combinations · ${h(memory.status)}</p>`:''}</section><footer class="au-learning-seal" data-au-learning-reveal="10"><p>Saved after the recorded checks passed.</p><details class="au-learning-identity" data-au-disclosure="knowledge-identity:${h(identity)}"><summary>Details</summary><p>Exact version record <code>${h(version.knowledge_sha256 || 'unavailable')}</code></p>${requalification?'':lineageMarkup(version,model.versions)}</details></footer></details>`:''}${!use?`<details class="au-learning-provenance"><summary>Source and receiving cases</summary><section class="au-procedure-provenance">${learningClaimLink(sourceId,event.source_claim_title || event.claim_title)}${receiving.map(row=>`<article>${learningClaimLink(row.claim_id,model.events.find(e=>e.kind==='knowledge.used'&&e.claim_id===row.claim_id)?.claim_title)}</article>`).join('')}${!receiving.length?'<p>No receiving case is recorded for this version.</p>':''}</section></details>`:''}</article>`;
  }
  function knowledgeNowMarkup(model, event) {
    if (!event) return `<div class="au-now" data-au-now-id=""><span class="au-now-label">Now</span> ${roleBadge('casepath')} <span data-au-now-copy>has no selected recorded event.</span><span data-au-now-result>No result is available.</span></div>`;
    const version=event.versionRecord || event.item, shown=language.knowledgePresentation(version,event), used=event.kind==='knowledge.used';
    const known=['saved','reused','not_saved'].includes(shown.status), role=known?'memory':'casepath', number=version.version || event.item.version;
    const action=!known?'shows this saved version. Its method was not recorded.':shown.status==='not_saved'?'does not save these steps after checking them with fixed rules.':used?`reuses the known document checks from version ${number || 'unknown'} using fixed rules.`:shown.label==='Rechecked'?`rechecks version ${number || 'unknown'} and its known document checks using fixed rules.`:`saves version ${number || 'unknown'} and its known document checks using fixed rules.`;
    const result=shown.status==='not_saved'?'The recorded checks did not pass.':used?'This case still needed its own proof.':shown.status==='saved'?'The recorded checks passed.':'Read the original record in Details.';
    return `<div class="au-now" data-au-now-id="${h(event.id)}"><span class="au-now-label">Now</span> ${roleBadge(role)} <span data-au-now-copy>${h(action)}</span> <span data-au-now-result>${h(result)}</span> ${event.recorded?recordButton('Details','learning-event',event.id):''}</div>`;
  }
  // "Replay" only while the learning view is playing. "Fictional" needs every
  // recorded case to be a known corpus or featured original.
  function learningLabel(model, claims = [], playing = false) {
    const ids = [...new Set(model.events.flatMap(event => [event.claim_id,event.source_claim_id,event.item?.source_claim_id]).filter(Boolean))];
    const fictional = ids.length > 0 && ids.every(id => featuredCase(id) || list(claims).some(row => row.claim_id === id && row.origin === 'canonical_original'));
    const base = !model.events.length ? 'No saved learning yet' : playing ? 'Replay' : 'Saved learning';
    return fictional ? `${base} · Fictional cases` : base;
  }
  function knowledgeMarkup(data, claims = [], pin = null, facet = 'process', position = null) {
    const model=knowledgeLearningModel(data), versions=[...model.versions].sort((a,b)=>String(name(a)).localeCompare(String(name(b))) || Number(b.version)-Number(a.version));
    const pinned=pin ? versions.find(version=>knowledgePinMatches(version,pin)):null;
    const selected=pin&&!pinned ? undefined : position?.event_id ? model.events.find(event=>event.id===position.event_id) : position && Number.isSafeInteger(position.index) ? model.events[position.index] : model.events.find(event=>event.kind==='knowledge.published'&&!event.refused&&event.versionRecord===(pinned || (!pin?versions[0]:null)));
    const knownDays=[...new Set(model.events.map(learningDay).filter(day=>day!=='unordered'))].sort(),days=[];
    if(knownDays.length){const first=Date.parse(knownDays[0]),last=Date.parse(knownDays.at(-1));if(last-first<=31*86400000){for(let time=first;time<=last;time+=86400000)days.push(new Date(time).toISOString().slice(0,10));}else days.push(...knownDays);}
    if(model.events.some(event=>!event.at || !Number.isFinite(Date.parse(event.at)))) days.push('unordered');
    const families=[...DOMAINS.map(row=>({id:row.id,label:procedureScope({family:row.id})})),...new Set(model.events.filter(event=>!event.refused&&!DOMAINS.some(row=>row.id===event.family)).map(event=>event.family))].map(row=>typeof row==='string'?{id:row,label:words(row)}:row);
    const lanes=[...families,{id:'refused',label:'Not saved'}];
    const totals=model.totals, initialStage=position?.stage ?? 10;
    return `<section class="au-quiet-knowledge au-learning" data-au-learning><header class="au-work-head"><div><p class="au-learning-label" data-au-learning-label>${h(learningLabel(model,claims,false))}</p><h1 class="au-page-heading" tabindex="-1">How this was learned</h1><p>See which steps were saved, checked again and reused.</p></div><div><span class="au-read-state" data-au-knowledge-read-label></span>${button('Retry','data-au-knowledge-retry hidden')}<button type="button" class="au-link" data-au-library-return>Back to the library</button>${recordButton('History','knowledge-index')}</div></header><div class="au-learning-transport" role="group" aria-label="Learning replay controls"><button type="button" data-au-learning-play${!model.events.length?' disabled':''}>Play</button><button type="button" data-au-learning-end${!model.events.length?' disabled':''}>Final view</button><label><span>Replay position</span><input type="range" data-au-learning-scrub min="0" max="${Math.max(0,model.events.length-1)}" value="${Math.max(0,model.events.indexOf(selected))}" aria-label="Recorded learning event"${!model.events.length?' disabled':''}></label><p data-au-learning-position-label>${selected?h(learningEventLabel(selected)):model.events.length?'Exact version unavailable':'No recorded events'}</p></div><div class="au-learning-focus" role="region" aria-label="Selected recorded knowledge" tabindex="0" data-au-learning-focus data-au-learning-stage="${initialStage}">${pin&&!pinned?`<article class="au-learning-unavailable">${knowledgeNowMarkup(model,null)}<h2>This exact saved version is unavailable.</h2><p>The recorded learning history is still available.</p>${button('Open the library','data-au-learning-end')}</article>`:knowledgeLearningFocus(model,selected,facet)}</div><section class="au-learning-timeline" style="--au-learning-days:${Math.max(1,days.length)}" aria-label="Recorded learning timeline"><div class="au-learning-dates"><span>Versions and reuses</span>${days.map(day=>`<span>${h(day==='unordered'?'Unordered':new Date(day+'T00:00:00Z').toLocaleDateString('en-GB',{timeZone:'UTC',day:'numeric',month:'short'}))}</span>`).join('')}</div>${lanes.map(lane=>`<section class="au-learning-lane" data-au-learning-lane="${h(lane.id)}"><h2>${h(lane.label)}</h2><div class="au-learning-track">${days.map(day=>`<div class="au-learning-day" data-au-learning-day="${h(day)}"><span class="au-learning-mobile-date">${h(day==='unordered'?'Unordered':day.slice(5))}</span>${model.events.map((event,index)=>({event,index})).filter(({event,index})=>(lane.id==='refused'?event.refused:!event.refused&&event.family===lane.id)&&learningDay(event)===day&&(!event.reuseGroup||event.reuseGroup[0]===index)).map(({event,index})=>`<button type="button" class="au-learning-node" data-au-learning-event="${index}" data-au-learning-event-id="${h(event.id)}"${learningPinAttributes(event.versionRecord || event.item)} aria-current="${selected===event?'step':'false'}" aria-label="${h(`${learningEventLabel(event)}. ${learningTimelineProcedure(event)}. ${learningTime(event)}.`)}"><span>${h(event.kind==='knowledge.used'?`${event.reuseGroup?.length || 1} ${event.reuseGroup?.length===1?'reuse':'reuses'}`:event.refused?'×':`v${event.item.version || '?'}`)}</span><span class="au-learning-node-text">${h(event.kind==='knowledge.used'?'':event.refused?'Not saved':String(event.item.change_reason || '').startsWith('Requalified ')?'Rechecked':event.item.parent_knowledge_sha256?'Updated':'Saved')}</span></button>`).join('')}</div>`).join('')}${!model.events.some(event=>lane.id==='refused'?event.refused:!event.refused&&event.family===lane.id)?'<p class="au-learning-no-events">No recorded events</p>':''}</div></section>`).join('')}</section><p class="au-learning-disclosure">Replay shows saved records. Playback does not change them.</p><p class="au-learning-totals">${h(totals.recorded_uses ?? model.uses.length)} recorded uses · ${h(totals.receiving_claims ?? 0)} receiving cases · ${h(totals.avoided_rule_compilations ?? 0)} times reused instead of rebuilding</p><p class="au-learning-announcement" data-au-learning-announcement></p></section>`;
  }
  function collectionRows(claims, scope = 'all') {
    return list(claims).filter(claim => scope === 'all' || (scope === 'originals' ? claim.origin === 'canonical_original' : claim.origin !== 'canonical_original'));
  }
  // Rows per lexicon status, before the status filter narrows them.
  function caseStatusCounts(rows) {
    const counts = Object.fromEntries(language.caseStatuses.map(row => [row.id,0]));
    for (const claim of list(rows)) counts[caseStatus(claim)]++;
    return counts;
  }
  const domainLabel = claim => DOMAINS.find(row => row.id === domainOf(claim))?.label || '';
  // Each fact is its own unbreakable item; the stylesheet draws the separator
  // before it and clips it at a line start, so no wrapped line ends or begins
  // with a dangling dot.
  const factsMarkup = facts => facts.split(' · ').map(part => `<span>${h(part)}</span>`).join('');
  // One quiet line of recorded intake metadata; unrecorded fields are omitted.
  function caseFactsLine(claim) {
    return language.caseFacts({domain:domainLabel(claim),language:claim?.language,attachments:claim?.attachment_count,mediaTypes:claim?.attachment_media_types,channel:claim?.channel,received:claim?.received_at});
  }
  const searchTerms = value => String(value || '').trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  // The words a row itself can show: no raw language or media type codes.
  const ownSearchText = claim => [claim.claim_id,claim.title,originalText(claim),claim.channel,claimStatusLabel(claim.status,claim),claim.phase,claim.phase_summary,claim.outcome?.summary,claim.outcome?.reason,claimConstraint(claim),claim.browse_metadata?.family_id,caseFactsLine(claim)].filter(Boolean).join(' ').toLocaleLowerCase();
  // A term matches the row's own fields, or the API's browsing search over the
  // full original message and file names (`searchMatches`: term -> claim ID ->
  // hint or null).
  function matchingClaims(claims, {search = '', filter = 'all', domain = 'all', scope = 'all', searchMatches = null} = {}) {
    const terms = searchTerms(search), wanted = caseFilter(filter);
    // Catalog order stays as recorded; demonstration cases are marked, not promoted.
    return collectionRows(claims,scope).filter(claim => {
      if (domain !== 'all' && domainOf(claim) !== domain || wanted !== 'all' && caseStatus(claim) !== wanted) return false;
      if (!terms.length) return true;
      const own = ownSearchText(claim);
      return terms.every(term => own.includes(term) || searchMatches?.get?.(term)?.has(claim.claim_id) === true);
    });
  }
  // A hint is the API's own words for a match the row cannot show.
  const searchHint = value => value && ['message','file_name'].includes(value.field) && (value.text === null || typeof value.text === 'string' && value.text.length <= 400) ? Object.freeze({field:value.field,text:value.text}) : null;
  // Why a row matched when its visible text does not say: the passage of the
  // full message, or the attached file name, for the first such term.
  function rowSearchHint(claim, terms, searchMatches) {
    if (!terms.length || !searchMatches) return null;
    const own = ownSearchText(claim);
    for (const term of terms) { if (own.includes(term)) continue; const hint = searchMatches.get?.(term)?.get?.(claim.claim_id); if (hint) return hint; }
    return null;
  }
  function markTerms(value, terms) {
    const words = terms.filter(Boolean).map(term => term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'));
    if (!words.length) return h(value);
    let html = '', last = 0;
    for (const match of String(value).matchAll(new RegExp(words.join('|'),'giu'))) { if (!match[0]) continue; html += `${h(value.slice(last,match.index))}<mark>${h(match[0])}</mark>`; last = match.index + match[0].length; }
    return html + h(value.slice(last));
  }
  function searchHintMarkup(id, hint, terms) {
    if (!hint) return '';
    const body = hint.field === 'file_name' ? `Found in an attached file name: <span class="au-claim-match-text">${markTerms(hint.text,terms)}</span>` : hint.text ? `Found in the full message: <span class="au-claim-match-text">“${markTerms(hint.text,terms)}”</span>` : 'Found in the full message.';
    return `<p class="au-claim-match" id="match-${h(id)}" data-au-search-hint="${hint.field}">${body}</p>`;
  }
  function claimConstraint(claim) {
    const outcome = claim.outcome;
    const missing = list(outcome?.missing_evidence).map(item => item.label || language.documentTitle(item)).filter(Boolean);
    return outcome?.reason || (missing.length ? `Missing: ${missing.join('; ')}.` : '') || list(outcome?.authority_limits)[0] || outcome?.next_action || '';
  }
  // One state line per row, in the shared lexicon: the recorded constraint
  // when work stopped short, the recorded next action when it is complete.
  function caseStateLine(claim) {
    const id = caseStatus(claim), label = language.caseStatusLabel(id);
    const detail = id === 'not_started' ? '' : id === 'working' || id === 'received' ? text(claim.phase_summary) : id === 'investigation_complete' ? text(claim.outcome?.next_action) : id === 'stopped' ? [stopReason(claim),claimConstraint(claim)].filter(Boolean).join(' ') : id === 'unknown' ? `Recorded status: ${words(claim.status)}.` : claimConstraint(claim);
    return {id,label,detail:detail.trim()};
  }
  // A salutation is greeting, not content; the excerpt begins after it.
  const SALUTATION = /^\s*(?:dear\b[^\n]{0,60}|hello\b[^\n]{0,30}|hi\b[^\n]{0,30}|good (?:morning|afternoon|evening)\b[^\n]{0,30}|to whom it may concern\b[^\n]{0,10}|gr(?:ü|ue)ezi\b[^\n]{0,30}|guten (?:tag|morgen|abend)\b[^\n]{0,30}|sehr geehrte[^\n]{0,60}|liebe[rs]?\b[^\n]{0,40}|hallo\b[^\n]{0,30}|bonjour\b[^\n]{0,30}|buongiorno\b[^\n]{0,30})\s*\n/iu;
  // The excerpt keeps whole words: a 240-character preview is a cut of a longer message.
  function caseExcerpt(source) {
    const value = text(source), clipped = value.length >= 240 ? value.slice(0,240).replace(/\s+\S*$/,'') : value;
    const body = clipped.replace(SALUTATION,'').replace(/\s+/g,' ').trim();
    return body && clipped !== value ? body + '…' : body;
  }
  function collectionPage(claims, options = {}, pageSize = 20) {
    const size = Number.isSafeInteger(pageSize) && pageSize > 0 ? Math.min(pageSize,50) : 20;
    const matching = matchingClaims(claims,options), pages = Math.max(1,Math.ceil(matching.length/size));
    const requested = Number(options.page), page = Math.min(pages,Number.isSafeInteger(requested) && requested > 0 ? requested : 1);
    return {rows:matching.slice((page-1)*size,page*size),page,pages,total:matching.length,pageSize:size};
  }
  function paginationMarkup(page) {
    return `<nav class="au-pagination" data-au-pagination aria-label="Case pages"><button type="button" class="au-link" data-au-page="${page.page-1}"${page.page <= 1 ? ' disabled' : ''}>Previous</button><span>Page ${page.page} of ${page.pages}</span><button type="button" class="au-link" data-au-page="${page.page+1}"${page.page >= page.pages ? ' disabled' : ''}>Next</button></nav>`;
  }
  function catalogPreviewMarkup(row, claimId) {
    if (!row || row.claim_id !== claimId || typeof row.title !== 'string') return null;
    const excerpt = messagePreview(originalText(row)), label = caseLabel(claimId,row);
    return `<section class="au-catalog-preview" data-au-preview="catalog" data-au-preview-claim="${h(row.claim_id)}" aria-busy="true"><header class="au-work-head"><div><p class="au-eyebrow"><button type="button" class="au-back-work" data-au-nav="work">Cases</button>${row.origin === 'canonical_original' ? ' / Fictional case' : ''}</p><h1 class="au-page-heading" data-au-catalog-title tabindex="-1">${h(label.primary)}</h1>${label.secondary ? `<p class="au-catalog-subject">${h(label.secondary)}</p>` : ''}</div></header>${excerpt ? `<section class="au-catalog-original"><h2>Original message excerpt</h2><pre class="au-original-message">${h(excerpt)}</pre></section>` : ''}</section>`;
  }
  function unknownClaimMarkup(claimId) {
    const featured = featuredCase(claimId);
    return `<section class="au-catalog-preview" data-au-preview="unknown" aria-busy="true">${featured ? `<h1 class="au-page-heading" tabindex="-1">${h(featured.label)}</h1>` : ''}${button('Choose a case','data-au-nav="work"')}</section>`;
  }
  function claimsMarkup(claims, options = {}) {
    const visible = options.page === undefined ? matchingClaims(claims,options) : collectionPage(claims,options).rows, terms = searchTerms(options.search);
    // The quiet marker names a case's place in the sequence the Demonstration plays.
    const roster = list(claims).length ? demoRoster(claims) : {cases:[]}, position = id => roster.cases.findIndex(row => row.claim_id === id);
    return visible.map(claim => {
      const id = claim.claim_id, label = caseLabel(id,claim), place = position(id), facts = caseFactsLine(claim), state = caseStateLine(claim);
      const excerpt = caseExcerpt(originalText(claim)) || list(claim.outcome?.unresolved_facts).find(fact => fact.summary)?.summary || claim.deferral?.reason || claim.outcome?.summary || '';
      const marker = place >= 0 ? `<p class="au-claim-demo" data-au-demo-position="${place+1}">In demonstration · ${String(place+1).padStart(2,'0')}</p>` : '';
      const hint = rowSearchHint(claim,terms,options.searchMatches), described = [excerpt ? `ex-${id}` : '',hint ? `match-${id}` : ''].filter(Boolean).join(' ');
      return `<article class="au-claim-row au-identity-claim-row" data-au-claim-row="${h(id)}" data-au-case-status="${state.id}"><h2 class="au-claim-title"><button type="button" class="au-claim-open" data-au-claim="${h(id)}"${described ? ` aria-describedby="${h(described)}"` : ''}>${h(label.primary)}</button></h2>${label.secondary ? `<p class="au-case-subject">${h(label.secondary)}</p>` : ''}${facts ? `<p class="au-case-facts">${factsMarkup(facts)}</p>` : ''}<p class="au-claim-state"><span class="au-claim-status-word">${h(state.label)}</span>${state.detail ? `<span class="au-claim-state-detail">&nbsp;·&nbsp;${h(state.detail)}</span>` : ''}</p>${excerpt ? `<p class="au-claim-excerpt" id="ex-${h(id)}">${h(excerpt)}</p>` : ''}${searchHintMarkup(id,hint,terms)}${marker}</article>`;
    }).join('') || (options.searchState === 'pending' && searchTerms(options.search).length ? '<p class="au-empty">Searching the full messages and files…</p>' : '<p class="au-empty">No cases match this search.</p>');
  }

  function domainMarkup(claims, domain = 'all') {
    return `<nav class="au-domain-browse" aria-label="Case domains"><button type="button" data-au-domain="all" aria-pressed="${domain === 'all'}">All cases</button>${DOMAINS.map(item => `<button type="button" data-au-domain="${item.id}" aria-pressed="${domain === item.id}">${h(item.label)}</button>`).join('')}</nav>`;
  }
  // An empty Added scope says so and offers the one way to add a case.
  function addedEmptyMarkup(readOnly = false) {
    return `<p class="au-empty" data-au-added-empty>No added cases yet.${readOnly ? '' : ' <button type="button" class="au-link" data-au-nav="intake">New case</button>'}</p>`;
  }
  // The scope toggle reads like a domain filter, with its own count.
  function scopeMarkup(claims, scope) {
    const target = scope === 'originals' ? 'added' : 'originals', count = collectionRows(claims,target).length;
    return `<div class="au-collection-scope"><button type="button" data-au-collection-scope="${target}">${target === 'added' ? 'Added' : 'Original cases'} <span data-au-scope-count>(${count})</span></button></div>`;
  }
  // One quiet status line, shown once any case in scope has moved past Not
  // started. Each item filters; the pressed item or "All statuses" clears it.
  // Items are spaced like the domain filters, with no separator glyph that
  // could be left dangling where a narrow line wraps.
  function statusLineMarkup(scoped, counted, filter = 'all') {
    const wanted = caseFilter(filter), counts = caseStatusCounts(counted);
    if (wanted === 'all' && !list(scoped).some(claim => caseStatus(claim) !== 'not_started')) return '';
    const items = language.caseStatuses.filter(row => row.id !== 'not_started' && counts[row.id] || row.id === wanted);
    if (!items.length) return '';
    return `<nav class="au-case-filter" aria-label="Case status">${items.map(row => `<button type="button" data-au-filter="${row.id}" aria-pressed="${wanted === row.id}">${counts[row.id]} ${h(row.label.toLocaleLowerCase('en'))}</button>`).join('')}${wanted !== 'all' ? '<button type="button" class="au-case-filter-clear" data-au-filter="all" aria-pressed="false">All statuses</button>' : ''}</nav>`;
  }
  // Rows whose match still waits on a term the API has not answered: their own
  // text lacks it and no cached answer has ruled them in or out.
  function undecidedSearchRows(rows, {search = '', filter = 'all', domain = 'all', searchMatches = null} = {}) {
    const terms = searchTerms(search), wanted = caseFilter(filter);
    if (!terms.length) return 0;
    return list(rows).filter(claim => {
      if (domain !== 'all' && domainOf(claim) !== domain || wanted !== 'all' && caseStatus(claim) !== wanted) return false;
      const own = ownSearchText(claim); let open = false;
      for (const term of terms) { if (own.includes(term)) continue; const known = searchMatches?.get?.(term); if (!known) open = true; else if (!known.has(claim.claim_id)) return false; }
      return open;
    }).length;
  }
  function collectionCountText(options, matching, total, rows = null) {
    const refined = searchTerms(options.search).length || caseFilter(options.filter || 'all') !== 'all' || (options.domain || 'all') !== 'all';
    if (!refined) return '';
    // While the full-text read could still add rows, a number would undercount.
    if (searchTerms(options.search).length && options.searchState === 'pending' && (rows === null || undecidedSearchRows(rows,options) > 0)) return 'Searching…';
    const note = searchTerms(options.search).length && options.searchState === 'failed' ? ' · titles and excerpts only' : '';
    return `${matching} of ${total}${note}`;
  }

  function collectionMarkup(claims, options = {}) {
    const {search = '',domain = 'all',scope = 'originals'} = options, filter = caseFilter(options.filter || 'all'), rows = collectionRows(claims,scope), page = collectionPage(rows,{...options,scope,filter});
    const counted = matchingClaims(rows,{...options,scope,filter:'all'});
    const emptyAdded = scope === 'added' && !rows.length;
    const listMarkup = emptyAdded ? addedEmptyMarkup(options.readOnly) : claimsMarkup(rows,{...options,scope,filter,page:page.page});
    return `<section class="au-collection au-identity-collection"><header class="au-collection-head"><div><h1 class="au-page-heading" tabindex="-1">Cases</h1><p class="au-lead">${scope === 'added' ? 'Added cases' : '150 fictional cases'}</p></div></header><div class="au-collection-tools"><label for="auClaimSearch"><span class="au-search-label">Search cases</span><input id="auClaimSearch" type="search" data-au-claim-search value="${h(search)}" placeholder="Message, title, file or case ID" autocomplete="off" aria-describedby="auCollectionCount"></label><p class="au-collection-count" id="auCollectionCount" data-au-collection-count>${h(collectionCountText({...options,scope,filter},page.total,rows.length,rows))}</p></div><div class="au-collection-filter-row">${scope==='originals'?domainMarkup(rows,domain):''}${scopeMarkup(claims,scope)}</div><div data-au-status-line>${statusLineMarkup(rows,counted,filter)}</div><div class="au-claim-list" data-au-claims>${listMarkup}</div>${emptyAdded ? paginationMarkup(page).replace('<nav ','<nav hidden ') : paginationMarkup(page)}</section>`;
  }

  function liveAvailability(status) {
    if (!writable(status)) return {ready:false,reason:'This workspace is view only.'};
    if (!status) return {ready:false,reason:'Checking live execution availability…'};
    if (!status.enabled) return {ready:false,reason:'Live execution is disabled.'};
    if (!status.provider_ready) return {ready:false,reason:status.reference_ready === true ? 'Live inference is unavailable.' : language.copy.analysisUnavailable};
    if (status.limits?.autonomous_can_start === false) return {ready:false,reason:status.limits.autonomous_reason === 'call_limit_reached' ? 'The recorded call allowance is exhausted.' : status.limits.autonomous_reason === 'cost_limit_reached' ? 'The recorded cost allowance is exhausted.' : 'The recorded allowance does not permit new work.'};
    return {ready:true,reason:'Cases are checked one at a time.'};
  }
  function demoItineraryMarkup(claims, position = null, current = null, roster = REFERENCE_DEMO_CASES) {
    return `<div class="au-demo-selection" role="group" aria-label="Presentation order of independent cases">${DOMAINS.map(domain => `<section data-au-demo-domain="${domain.id}"><div class="au-section-heading"><h2>${h(domain.label)}</h2><span>3 original cases</span></div><ol start="${roster.findIndex(row => row.domain === domain.id)+1}">${roster.filter(row => row.domain === domain.id).map(row => {
      const index = roster.indexOf(row), claim = current?.claim_id === row.claim_id ? current : claims.find(claim => claim.claim_id === row.claim_id), here = index === position, label = caseLabel(row.claim_id,claim);
      return `<li data-au-demo-case="${row.claim_id}"${here ? ' aria-current="step"' : ''}><span class="au-demo-order" aria-hidden="true">${String(index+1).padStart(2,'0')}</span><button type="button" data-au-claim="${row.claim_id}" title="${h(claim?.title || 'Original record')}" aria-label="${h(`Presentation case ${String(index+1).padStart(2,'0')}. ${label.primary}. ${claim?.title || 'Original record'}`)}"><strong>${h(label.primary)}</strong><span>${h(claim?.title || 'Original record')}</span></button>${claim?.status && !['not_started','not_run'].includes(claim.status) ? `<span class="au-status" data-tone="${tone(claim.status)}">${h(claimStatusLabel(claim.status,claim))}</span>` : ''}</li>`;
    }).join('')}</ol></section>`).join('')}</div>`;
  }
  // Catalog revisions are routing hints only: they decide whether a replay is
  // worth opening, never what a case contains.
  const catalogRow = (claims, id) => list(claims).find(row => row.claim_id === id);
  const rosterUnrun = claims => REFERENCE_DEMO_CASES.every(row => Number.isSafeInteger(catalogRow(claims,row.claim_id)?.revision)) && !REFERENCE_DEMO_CASES.some(row => catalogRow(claims,row.claim_id).revision > 0);
  const knownUnrun = (claims, id) => { const row = catalogRow(claims,id); return row?.revision === 0 || row?.mode === 'unprocessed'; };
  function demonstrationOverviewMarkup(claims) {
    const rows = REFERENCE_DEMO_CASES.map((row,index) => ({row,index,claim:catalogRow(claims,row.claim_id)}));
    const recorded = rows.filter(({claim}) => claim?.revision > 0).length;
    return `<section class="au-demonstration au-demo-overview" data-au-demo-overview><header class="au-collection-head"><div><p class="au-eyebrow">Demonstration · three domains</p><h1 class="au-page-heading" tabindex="-1">Nine original cases</h1><p class="au-lead">${recorded ? `${recorded} of 9 cases have a saved history in this workspace.` : h(language.copy.noHistories)}</p></div></header><ol class="au-demo-cases" aria-label="Nine original cases">${rows.map(({row,index,claim}) => {
      const domain = DOMAINS.find(item => item.id === row.domain)?.label || 'Other', stateLabel = !claim ? 'Not in this workspace' : claim.revision > 0 ? `Saved result · revision ${claim.revision}` : language.copy.notRunHere;
      const label = caseLabel(row.claim_id,claim);
      return `<li class="au-demo-case" data-au-demo-case="${h(row.claim_id)}" data-au-demo-state="${!claim ? 'unknown' : claim.revision > 0 ? 'saved' : 'not_run'}"><span class="au-demo-order" aria-hidden="true">${String(index+1).padStart(2,'0')}</span><div class="au-demo-case-copy"><strong>${h(label.primary)}</strong>${label.secondary ? `<span class="au-case-subject">${h(label.secondary)}</span>` : ''}<span class="au-demo-case-facts">${factsMarkup(language.caseFacts({domain,language:claim?.language,attachments:claim?.attachment_count,mediaTypes:claim?.attachment_media_types,channel:claim?.channel,received:claim?.received_at}))}</span></div><span class="au-demo-case-state">${h(stateLabel)}</span>${claim ? `<a class="au-demo-intake-link" href="#autonomous/claim/${key(row.claim_id)}" aria-label="${h(`Original intake: ${label.primary}`)}">Original intake</a>` : ''}</li>`;
    }).join('')}</ol></section>`;
  }
  // Both rosters, named by provenance. A row offers its saved history only
  // when the catalog records one of that kind; its original sources always open.
  function demoPickerMarkup(claims, first = null) {
    const order = first === 'selected' ? ['selected','reference'] : ['reference','selected'];
    const roster = collection => `<section class="au-demo-roster" data-au-demo-roster="${collection}"><h3>${h(DEMO_COLLECTIONS[collection])}</h3><ol class="au-demo-picks">${demoCases(collection).map((row,index) => {
      const claim = catalogRow(claims,row.claim_id), label = caseLabel(row.claim_id,claim), saved = collectionHistory(collection,claim), other = !saved && claim?.revision > 0;
      const state = !claim ? 'unknown' : saved ? 'saved' : other ? 'other_history' : 'not_run', domain = DOMAINS.find(item => item.id === row.domain)?.label || '';
      const open = state === 'saved' || state === 'unknown' ? `<button type="button" class="au-demo-case-open" data-au-demo-case="${h(row.claim_id)}" data-au-demo-collection="${collection}">${h(label.primary)}</button>` : `<strong>${h(label.primary)}</strong>`;
      const status = saved ? `<button type="button" class="au-link" data-au-demo-case="${h(row.claim_id)}" data-au-demo-collection="${collection}" data-au-demo-saved="true">Saved history</button>` : state === 'unknown' ? '' : `<span class="au-demo-pick-state">${h(other ? collection === 'selected' ? 'Fixed-rule history only' : 'Model history only' : language.copy.notRunHere)}</span>`;
      return `<li class="au-demo-pick" data-au-demo-pick="${h(row.claim_id)}" data-au-demo-pick-state="${state}"><span class="au-demo-order" aria-hidden="true">${String(index+1).padStart(2,'0')}</span><div class="au-demo-pick-copy">${open}<span class="au-demo-pick-facts">${h(domain)}</span></div>${status}<a class="au-link au-demo-sources" href="#autonomous/claim/${key(row.claim_id)}" aria-label="${h(`Original sources: ${label.primary}`)}">Original sources</a></li>`;
    }).join('')}</ol></section>`;
    return `<div class="au-demo-picker"><h2>Demonstration cases</h2><p class="au-meta">Each list plays on its own. A saved history replays without new work.</p>${order.map(roster).join('')}</div>`;
  }
  function demonstrationMarkup(claims, status, mode = 'reference') {
    const availability = liveAvailability(status);
    if (mode === 'reference') return demonstrationOverviewMarkup(claims);
    if (readOnlyAccess(status)) mode = 'replay';
    return `<section class="au-demonstration"><header class="au-collection-head"><div><p class="au-eyebrow">Nine original cases · three domains</p><h1 class="au-page-heading" tabindex="-1">Follow the evidence.</h1><p class="au-lead">A selected route through the same cases, sources and recorded histories.</p></div></header><div class="au-demo-controls"><div class="au-mode-choice" role="group" aria-label="Demonstration mode"><button type="button" data-au-demo-mode="replay" aria-pressed="${mode === 'replay'}">Verified replay</button>${readOnlyAccess(status) ? '' : `<button type="button" data-au-demo-mode="live" aria-pressed="${mode === 'live'}">Live execution</button>`}</div>${button(mode === 'replay' ? 'Play recorded work' : 'Start live presentation','data-au-demo-play',true)}<p class="au-meta" data-au-demo-availability>${h(mode === 'live' ? availability.reason : 'Recorded executions only. Playback stops if no operational outcome was accepted.')}</p></div><p class="au-meta au-demo-order-note">01–09 · Presentation order across independent original cases.</p>${demoItineraryMarkup(claims,null,null,DEMO_CASES)}</section>`;
  }
  function mediaType(file) {
    if (text(file.type).trim()) return file.type;
    const extension = String(file.name || '').match(/\.([^.]+)$/)?.[1].toLowerCase();
    return ({eml:'message/rfc822',txt:'text/plain',md:'text/markdown',csv:'text/csv',json:'application/json'})[extension] || 'application/octet-stream';
  }
  async function digest(value) {
    if (!root.crypto?.subtle) throw new Error('Source identity cannot be checked in this browser.');
    const bytes = typeof value === 'string' ? new TextEncoder().encode(value) : value;
    return [...new Uint8Array(await root.crypto.subtle.digest('SHA-256', bytes))].map(byte => byte.toString(16).padStart(2,'0')).join('');
  }
  function canonicalJSON(value) {
    if (Array.isArray(value)) return '[' + value.map(canonicalJSON).join(',') + ']';
    if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonicalJSON(value[key])).join(',') + '}';
    return JSON.stringify(value);
  }
  const OPERATIONS_CONTRACT = 'casepath.operations-stream/1.0.0';
  const OPERATION_CHOICE_GRACE_MS = 300;
  const OPERATION_INSTRUMENTATION = 'casepath.reference-operations/1.1.0';
  const OPERATION_FRAME_BYTES = 2 * 1024 * 1024, OPERATION_HISTORY_BYTES = 8 * 1024 * 1024;
  async function* operationFrames(response, signal = null) {
    if (!response?.body?.getReader) throw new Error('Operation streaming is unavailable.');
    const reader = response.body.getReader(), decoder = new TextDecoder('utf-8',{fatal:true});
    const cancel = () => { reader.cancel().catch(() => {}); };
    signal?.addEventListener('abort',cancel,{once:true});
    let pending = '';
    try {
      while (!signal?.aborted) {
        const chunk = await reader.read();
        pending += decoder.decode(chunk.value || new Uint8Array(),{stream:!chunk.done});
        let newline;
        while ((newline = pending.indexOf('\n')) >= 0) {
          const line = pending.slice(0,newline); pending = pending.slice(newline+1);
          if (line.length * 2 > OPERATION_FRAME_BYTES) throw new Error('An operation frame exceeds its bound.');
          if (line.trim()) yield JSON.parse(line);
        }
        if (pending.length * 2 > OPERATION_FRAME_BYTES) throw new Error('An operation frame exceeds its bound.');
        if (chunk.done) { if (pending.trim()) yield JSON.parse(pending); break; }
      }
    } finally { signal?.removeEventListener('abort',cancel); try { await reader.cancel(); } catch (_) {} reader.releaseLock?.(); }
  }
  function bufferedOperations(response, signal, resultAvailable = null) {
    // Drain the HTTP response at compute speed. Only application consumption
    // is paced or paused; the engine and proxy never wait for presentation.
    let firstFrame; const queue = [], buffer = {result:null,first:new Promise(resolve => { firstFrame=resolve; })};
    let bytes = 0, ended = false, failure = null, wake = null;
    const release = () => { const resolve = wake; wake = null; resolve?.(); };
    signal.addEventListener('abort',release,{once:true});
    const producer = (async () => {
      try {
        for await (const frame of operationFrames(response,signal)) {
          if (signal.aborted) break;
          const size = new TextEncoder().encode(canonicalJSON(frame)).byteLength;
          if (bytes + size > 24 * 1024 * 1024 || queue.length >= 10002) throw new Error('The buffered operation stream exceeds its bound.');
          queue.push({frame,size}); firstFrame?.(frame); firstFrame=null; bytes += size; if (frame.type === 'result') { buffer.result = frame; resultAvailable?.(frame); } release();
        }
      } catch (error) { failure = error; }
      finally { firstFrame?.(null); firstFrame=null; ended = true; release(); signal.removeEventListener('abort',release); }
    })();
    return Object.assign(buffer,{producer,[Symbol.asyncIterator]() { return this; },async next() {
      while (!queue.length && !ended && !signal.aborted) await new Promise(resolve => { wake = resolve; });
      if (signal.aborted) return {done:true};
      if (failure) throw failure;
      const row = queue.shift(); if (!row) return {done:true}; bytes -= row.size;
      return {done:false,value:row.frame};
    }});
  }
  async function operationFrameYield(budget, runtime, active, gate) {
    if (!active()) return false;
    const now = () => runtime.performance?.now?.() ?? Date.now();
    if (now()-budget.started < 10) return true;
    // Hash promises and a buffered iterator need not leave a paint opportunity.
    // Yield only between completely verified frames, then recheck the session
    // and its pause/inspection/visibility gate before consuming another frame.
    if (typeof runtime.scheduler?.yield === 'function') await runtime.scheduler.yield();
    else await new Promise(resolve => runtime.setTimeout(resolve,0));
    if (!active() || !await gate()) return false;
    budget.started = now();
    return active();
  }
  function checkedOperationBinding(frame, head, start) {
    if (frame?.contract !== OPERATIONS_CONTRACT || frame.type !== 'binding' || frame.instrumentation_id !== OPERATION_INSTRUMENTATION || !start ||
        frame.claim_id !== head.claimId || frame.run_id !== start.run_id || frame.from_seq !== start.from_seq ||
        frame.profile_id !== start.profile_id || frame.profile_sha256 !== start.profile_sha256 ||
        frame.current_revision !== head.revision || frame.current_state_sha256 !== head.state_sha256 ||
        frame.current_event_sha256 !== head.event_sha256 || !['historical_recomputed','recorded_operations'].includes(frame.mode) ||
        head.source_roster_sha256 && frame.source_roster_sha256 !== head.source_roster_sha256 ||
        head.rule_set_sha256 && frame.rule_set_sha256 !== head.rule_set_sha256 ||
        frame.mode === 'historical_recomputed' && frame.newly_recomputed !== true ||
        ![frame.source_roster_sha256,frame.rule_set_sha256,frame.input_sha256].every(isHash)) throw new Error('The operation binding differs from the selected saved assessment.');
    return frame;
  }
  async function checkedOperation(frame, trace, state) {
    if (frame?.contract !== OPERATIONS_CONTRACT || frame.type !== 'operation' || !trace.binding ||
        frame.seq !== trace.rows.length+1 || !frame.id || trace.rows.some(row => row.id === frame.id) ||
        !frame.kind || !frame.object?.id || !Array.isArray(frame.cause_ids) ||
        frame.cause_ids.some(id => !trace.rows.some(row => row.id === id)) ||
        frame.previous_operation_sha256 !== (trace.rows.at(-1)?.operation_sha256 || null) ||
        ![frame.input_sha256,frame.result_sha256,frame.operation_sha256].every(isHash)) throw new Error('The operation chain is incomplete or out of sequence.');
    const material = {...frame}; delete material.operation_sha256; delete material.contract; delete material.type;
    if (await digest(canonicalJSON(material)) !== frame.operation_sha256 || await digest(canonicalJSON(frame.input)) !== frame.input_sha256 || await digest(canonicalJSON(frame.result)) !== frame.result_sha256) throw new Error('The operation failed its identity check.');
    if (frame.kind === 'source.open' && !frame.source) {
      const opened = frame.result, id = opened?.artifact_id || frame.object.id, descriptor = list(state.source_descriptors).find(item => item.artifact_id === id);
      if (!descriptor || (opened.sha256 || frame.input.sha256) !== descriptor.sha256 || typeof opened.text !== 'string' || !isHash(opened.text_sha256) || await digest(opened.text) !== opened.text_sha256) throw new Error('The opened operation source failed its original identity check.');
      trace.sources.set(id,{...descriptor,...opened,sha256:descriptor.sha256});
    }
    let source = null;
    if (frame.source) {
      const pin = frame.source, descriptor = list(state.source_descriptors).find(item => item.artifact_id === pin.artifact_id);
      source = trace.sources.get(pin.artifact_id) || list(state.acquired_sources).find(item => item.artifact_id === pin.artifact_id);
      if (frame.kind === 'source.open' && typeof frame.result?.text === 'string') source = {...pin,text:frame.result.text};
      if (!descriptor || descriptor.sha256 !== pin.sha256 || !source || source.sha256 !== pin.sha256 || source.text_sha256 !== pin.text_sha256 ||
          !isHash(pin.text_sha256) || await digest(source.text) !== pin.text_sha256 || pin.offset_unit !== 'unicode_code_point') throw new Error('The operation source differs from the saved source packet.');
      const chars = Array.from(source.text);
      if (!Number.isSafeInteger(pin.start_char) || !Number.isSafeInteger(pin.end_char) || pin.start_char < 0 || pin.end_char < pin.start_char || pin.end_char > chars.length || chars.slice(pin.start_char,pin.end_char).join('') !== pin.quote) throw new Error('The operation passage is not the exact Unicode source span.');
      trace.sources.set(pin.artifact_id,source);
    }
    const bytes = canonicalJSON(frame).length * 2;
    if (trace.rows.length >= 4096 || trace.bytes + bytes > OPERATION_HISTORY_BYTES) throw new Error('The operation history exceeds its inspection bound.');
    workingOperationScope(frame,trace,state);
    if (frame.kind === 'process.inspect' && await digest(canonicalJSON({graph_sha256:frame.input.graph_sha256,conditions_override:frame.input.conditions_override,effective_conditions:frame.result.effective_conditions})) !== frame.result.evaluation_sha256) throw new Error('The working condition scope failed its identity check.');
    trace.bytes += bytes; trace.rows.push(frame);
    return frame;
  }
  function workingOperationScope(operation, trace, state) {
    if (operation.kind === 'process.inspect') {
      const graph = operation.result?.graph;
      if (operation.object.type !== 'process' || operation.object.id !== state.claim_id || operation.result.phase !== 'provisional' || !graph ||
          graph.claim_id !== state.claim_id || !isHash(graph.graph_sha256) || graph.graph_sha256 !== operation.input?.graph_sha256 || graph.graph_sha256 !== operation.result.graph_sha256 ||
          !isHash(operation.result.evaluation_sha256) || operation.result.evaluation_sha256 !== operation.input.evaluation_sha256 || !Object.prototype.hasOwnProperty.call(operation.input,'conditions_override') ||
          !Array.isArray(graph.nodes) || !Array.isArray(graph.edges) || !Array.isArray(graph.document_catalog) || !operation.result.effective_conditions || typeof operation.result.effective_conditions !== 'object') throw new Error('The working process is not bound to this actual evaluation.');
      const ids = new Set(graph.nodes.map(node => node.node_id));
      if (ids.size !== graph.nodes.length || ids.has(undefined) || graph.edges.some(edge => !ids.has(edge.source_node_id) || !ids.has(edge.target_node_id))) throw new Error('The working process contains an unbound step.');
      return operation;
    }
    if (operation.result?.phase !== 'provisional' || !operation.result.graph_sha256) return null;
    const inspect = trace.rows.find(row => operation.cause_ids.includes(row.id) && row.kind === 'process.inspect');
    if (!inspect || inspect.stage !== operation.stage || inspect.result.graph_sha256 !== operation.result.graph_sha256 || operation.input?.graph_sha256 !== inspect.result.graph_sha256 ||
        operation.input.evaluation_sha256 !== inspect.result.evaluation_sha256 || operation.result.evaluation_sha256 !== inspect.result.evaluation_sha256) throw new Error('The working evaluation has no exact inspected process scope.');
    const graph = inspect.result.graph, rows = operation.object.type === 'node' ? graph.nodes : operation.object.type === 'edge' ? graph.edges : operation.object.type === 'document' ? graph.document_catalog : null;
    const field = operation.object.type === 'node' ? 'node_id' : operation.object.type === 'edge' ? 'edge_id' : 'document_type';
    if (rows && !rows.some(row => row[field] === operation.object.id)) throw new Error('The working evaluation targets a different process object.');
    return inspect;
  }
  function applyWorkingOperation(operation, trace, state) {
    const inspect = workingOperationScope(operation,trace,state);
    if (!inspect) return;
    trace.workingScopes ||= new Map();
    let working = trace.workingScopes.get(inspect.id);
    if (!working) { working = {inspect,graph:inspect.result.graph,nodes:new Map(),edges:new Map(),documents:new Map(),conditions:new Map()}; trace.workingScopes.set(inspect.id,working); }
    const rows = operation.kind === 'condition.evaluate' ? working.conditions : operation.object.type === 'node' ? working.nodes : operation.object.type === 'edge' ? working.edges : operation.object.type === 'document' ? working.documents : null;
    rows?.set(operation.object.id,operation); working.stage = operation.stage; working.current = operation; trace.working = working;
  }
  const workingPresentations = new WeakMap();
  function workingProcessState(trace) {
    const working = !trace?.finished && !trace?.savedFallback && trace?.working;
    if (!working) return null;
    const prior = workingPresentations.get(working);
    if (prior && prior.operation === working.current && prior.nodes === working.nodes.size && prior.edges === working.edges.size) return prior.state;
    const state = {claim_id:working.graph.claim_id,graph:working.graph,conditions:working.inspect.result.effective_conditions,facts:[],evaluation:{nodes:[...working.nodes.values()].map(row => ({...row.result,node_id:row.object.id})),edges:[...working.edges.values()].map(row => ({...row.result,edge_id:row.object.id}))}};
    workingPresentations.set(working,{operation:working.current,nodes:working.nodes.size,edges:working.edges.size,state});
    return state;
  }
  function workingReadiness(node, graph) {
    if (!node.execution_state) return '';
    const labels = (ids,rows,field) => ids.map(id => name(list(rows).find(row => row[field] === id))).filter(Boolean).join(' + ');
    const blocked = labels(list(node.blocked_by),graph.nodes,'node_id'), unresolved = labels(list(node.unresolved_dependencies),graph.nodes,'node_id'), documents = labels(list(node.missing_document_types),graph.document_catalog,'document_type');
    return blocked ? `Execution · Waiting for ${blocked}` : unresolved ? `Execution · Unresolved prerequisite: ${unresolved}` : documents ? `Execution · Source support needed: ${documents}` : `Execution · ${statusLabel(node.execution_state)}`;
  }
  function directOperationNodeId(operation, graph, state) {
    if (!operation) return null;
    const factDocument = operation.object.type === 'fact' && operation.object.id.startsWith('fact:') ? operation.object.id.slice(5) : null;
    const document = operation.input?.document_type || (operation.object.type === 'document' ? operation.object.id : factDocument);
    const candidates = [operation.object.node_id,operation.result?.node_id,operation.input?.node_id,...list(operation.result?.required_at_node_ids),...list(operation.input?.required_at_node_ids),
      ...(operation.object.type === 'node' ? [operation.object.id] : []),...(operation.object.type === 'edge' ? [list(graph?.edges).find(edge => edge.edge_id === operation.object.id)?.target_node_id] : []),
      ...(document ? list(graph?.nodes).filter(node => list(node.document_types).includes(document)).map(node => node.node_id) : []),
      ...(operation.object.type === 'fact' ? list(state?.obligations).filter(row => list(row.required_fact_ids).includes(operation.object.id)).flatMap(row => list(row.node_ids).concat(row.node_id || row.decision_node_id || [])) : [])];
    return candidates.find(id => list(graph?.nodes).some(node => node.node_id === id)) || null;
  }
  // Source-context observations may follow the same native acquisition as a
  // document fact. Bind only to one already observed document destination;
  // ambiguous roots and facts without a recorded causal source remain unbound.
  const operationSourceIndexes = new WeakMap();
  function operationNodeId(operation, graph, state, trace = null) {
    const direct = directOperationNodeId(operation,graph,state);
    if (direct || operation?.kind !== 'fact.extract' || !isHash(operation.source?.sha256) || !isHash(operation.source?.text_sha256) || !trace?.rows) return direct;
    const rows = trace.rows;
    const through=rows.findIndex(row => row.id === operation.id)+1;
    if (!through) return null;
    let index = operationSourceIndexes.get(rows);
    if (!index || index.graph !== graph || index.length > through || index.last !== rows[index.length-1]) {
      index = {graph,length:0,last:null,roots:new Map(),opens:new Map(),anchors:new Map(),matches:new Map()}; operationSourceIndexes.set(rows,index);
    }
    for (let position=index.length; position<through; position++) {
      const row=rows[position], roots=new Set();
      if (row.kind === 'source.open') { roots.add(row.id); index.opens.set(row.id,row); }
      for (const cause of list(row.cause_ids)) for (const root of index.roots.get(cause) || []) roots.add(root);
      index.roots.set(row.id,roots);
      if (row.kind === 'fact.extract' && row.input?.document_type && row.source) {
        const consumers=list(graph?.nodes).filter(node => list(node.document_types).includes(row.input.document_type));
        const node=consumers.length === 1 ? consumers[0].node_id : null;
        if (node) for (const root of roots) {
          let anchors=index.anchors.get(root); if (!anchors) index.anchors.set(root,anchors=new Map());
          anchors.set(row.source.artifact_id+':'+node,{node,source:row.source});
        }
        if (node) for (const cause of list(row.cause_ids)) {
          let anchors=index.matches.get(cause); if (!anchors) index.matches.set(cause,anchors=new Map());
          anchors.set(node,{node,source:row.source});
        }
      }
    }
    index.length=through; index.last=rows[through-1];
    const sameSource = pin => pin.artifact_id === operation.source.artifact_id && pin.sha256 === operation.source.sha256 && pin.text_sha256 === operation.source.text_sha256;
    const nodes=new Set();
    for (const cause of list(operation.cause_ids)) for (const anchor of index.matches.get(cause)?.values() || []) if (sameSource(anchor.source)) nodes.add(anchor.node);
    if (nodes.size) return nodes.size === 1 ? [...nodes][0] : null;
    for (const root of index.roots.get(operation.id) || []) {
      const opened=index.opens.get(root);
      if (opened?.object.id !== operation.source.artifact_id || opened.result.sha256 !== operation.source.sha256 || opened.result.text_sha256 !== operation.source.text_sha256) continue;
      for (const anchor of index.anchors.get(root)?.values() || []) if (sameSource(anchor.source)) nodes.add(anchor.node);
    }
    return nodes.size === 1 ? [...nodes][0] : null;
  }
  function operationRelationship(trace, state) {
    const operation = trace?.current, working = workingProcessState(trace), graph = working?.graph || state.graph, node = operationNodeId(operation,graph,state,trace);
    if (!node || !operation?.source) return null;
    return {node,source:operation.source.artifact_id,pin:operation.source,operation_id:operation.id,graph_sha256:graph.graph_sha256};
  }
  function operationLabel(operation) { return language.operationPresentation(operation).label; }
  function freezeRelease(value) {
    if (value && typeof value === 'object') { Object.values(value).forEach(freezeRelease); Object.freeze(value); }
    return value;
  }
  function releaseOperationProcess(id) {
    const release = RELEASE_PROCEDURE_OUTLINE, claim = release.claims.find(row => row.claim_id === id), catalog = claim && release.catalogs.find(row => row.family === claim.family);
    if (!catalog || !REFERENCE_DEMO_CASES.some(row => row.claim_id === id)) return null;
    return {claim_id:id,release:{contract:release.contract,artifact_sha256:release.artifact_material_sha256,profile_id:release.profile_id,profile_sha256:release.profile_raw_sha256,policy_sha256:release.bounded_policy_sha256,catalog_sha256:catalog.catalog_sha256,rule_pack_sha256:catalog.rule_pack_sha256,...claim},
      graph:{claim_id:id,family:catalog.family,nodes:catalog.nodes,edges:catalog.transitions,document_catalog:catalog.documents.map(row => ({document_type:row.document_type,label:row.label}))},evaluation:{nodes:[],edges:[],documents:[]},facts:[],obligations:[]};
  }
  function releaseOpeningMatches(plan, state) {
    return Boolean(plan?.release && state?.claim_id === plan.claim_id && state.original_binding?.claim_binding_sha256 === plan.release.claim_binding_sha256 && state.original_binding?.corpus_manifest_sha256 === plan.release.corpus_manifest_sha256);
  }
  async function releaseHeadMatches(plan, state, admitted) {
    if (!releaseOpeningMatches(plan,state) || !admitted) return false;
    const reference = referenceExecution(state), context = state.semantic_contexts?.[state.run_id], release = plan.release, pin = release.request_source_pin;
    if (reference?.profile_id !== release.profile_id || reference.profile_sha256 !== release.profile_sha256 || admitted.rule_pack_sha256 !== release.rule_pack_sha256) return false;
    const topology = graph => ({family:graph.family,nodes:graph.nodes.map(row => ({id:row.node_id,label:recordedName(row),documents:[...list(row.document_types)].sort()})),edges:graph.edges.map(row => ({id:row.edge_id,from:row.source_node_id,to:row.target_node_id})),documents:graph.document_catalog.map(row => ({id:row.document_type,label:recordedName(row)}))});
    if (canonicalJSON(topology(plan.graph)) !== canonicalJSON(topology(admitted.graph))) return false;
    // Release supplements select this outline; only the current accepted
    // context can show that those exact sources belong to this investigation.
    const currentSources = list(context?.sources);
    if (release.source_sha256s.some(sha => !currentSources.some(row => row.sha256 === sha))) return false;
    const descriptor = currentSources.find(row => row.sha256 === pin.source_sha256 && row.file_name === pin.file_name), source = descriptor && list(state.acquired_sources).find(row => row.artifact_id === descriptor.artifact_id && row.sha256 === descriptor.sha256);
    return Boolean(source && source.text_sha256 === pin.text_sha256 && await digest(source.text) === pin.text_sha256 && Array.from(source.text).slice(pin.start_char,pin.end_char).join('') === pin.quote);
  }
  // The outline is release structure only. A known revision-zero catalog row
  // names it as not run; otherwise its recording date waits for the head.
  // One compact row while a roster plays: position, domain, Pause, Skip and
  // the next case. Real buttons; the row itself never animates.
  // The step a recorded operation is bound to, by its place in the drawn process;
  // once the result is reached, how many steps the evaluation records as done.
  function stagePlaceLabel(state, trace) {
    const graph = trace && !trace.unrun ? operationStageGraph(trace,state) : null, nodes = graph ? layoutGraph(graph).rows.flat() : [];
    if (!nodes.length) return '';
    if (trace.finished) { const done = nodes.filter(node => list(state.evaluation?.nodes).some(row => row.node_id === node.node_id && DONE_NODE_STATES.includes(row.execution_state))).length; return done ? `${done} of ${nodes.length} steps done` : ''; }
    const at = trace.current ? nodes.findIndex(node => node.node_id === operationNodeId(trace.current,graph,state,trace)) : -1;
    return at < 0 ? '' : `Step ${at+1} of ${nodes.length}`;
  }
  function demoTransportMarkup(tour, presentation = {}, place = '') {
    const row = tour?.cases?.[tour.index];
    if (!row) return '';
    const total = tour.cases.length, position = tour.index + 1, next = tour.cases[tour.index+1], domain = DOMAINS.find(item => item.id === row.domain)?.label || '';
    const separator = '<span class="au-demo-separator" aria-hidden="true">·</span>';
    const toggle = presentation.playing ? '<button type="button" class="au-demo-control" data-au-demo-stop>Pause</button>' : presentation.paused ? '<button type="button" class="au-demo-control" data-au-demo-resume>Resume</button>' : '';
    return `<div class="au-demo-transport" role="group" aria-label="${h(`${DEMO_COLLECTIONS[tour.collection] || 'Demonstration'} · case ${position} of ${total}`)}" data-au-demo-transport data-au-demo-collection="${h(tour.collection)}" data-au-demo-position="${position}"><span class="au-demo-position">${position}/${total}</span>${separator}<span class="au-demo-domain">${h(domain)}</span>${place ? `${separator}<span class="au-demo-step" data-au-demo-step>${h(place)}</span>` : ''}${toggle ? separator + toggle : ''}${separator}<button type="button" class="au-demo-control" data-au-demo-skip aria-describedby="auDemoNext">Skip</button>${separator}<span class="au-demo-next" id="auDemoNext">Next: ${h(next ? caseLabel(next.claim_id).primary : 'Knowledge')}</span><span class="au-demo-utilities"><button type="button" class="au-demo-control" data-au-inspect="demo">${presentation.operations?.savedFallback || presentation.operations?.replayUnavailable ? 'Replay choices' : 'Choose case'}</button><button type="button" class="au-demo-control" data-au-detail="activity">History</button>${presentation.modeLine ? `<span class="au-demo-mode" data-au-operation-mode title="${h(presentation.modeLine)}">${h(presentation.modeLine.startsWith('Original intake') ? 'Not started' : presentation.modeLine.split(' · ')[0])}${presentation.modeLine.includes('Fictional case') ? ' · Fictional case' : ''}</span>` : ''}</span><span class="au-demo-progress" aria-hidden="true"><span data-au-progress style="transform:scaleX(${Math.max(0,Math.min(1,presentation.progress || 0))})"></span></span></div>`;
  }
  function resultReached(state, presentation = {}) {
    const trace = presentation.operations, replay = presentation.replay;
    if (Number.isSafeInteger(presentation.inspectionIndex)) return false;
    if (trace) return trace.finished === true && !trace.unrun;
    return Boolean(state?.revision > 0 && replay && replay.current_revision > 0 && replay.through_seq >= replay.current_revision);
  }
  const knowledgeFragment = pin => `#autonomous/knowledge?knowledge=${key(pin.knowledge_id)}&version=${key(pin.version)}${pin.knowledge_sha256 ? `&sha256=${key(pin.knowledge_sha256)}` : ''}${pin.definition_sha256 ? `&definition=${key(pin.definition_sha256)}` : ''}${pin.claim_id ? `&claim=${key(pin.claim_id)}` : ''}`;
  // What this case's accepted state saved or reused, counted only from the
  // recorded Knowledge index. Without that index the count is not stated.
  function knowledgePayoff(state, data = null) {
    const publication = [...list(state?.knowledge_published)].reverse().find(item => item?.qualification?.status === 'qualified' && item.knowledge_id && item.version);
    const versions = list(data?.versions), indexed = Array.isArray(data?.uses);
    if (publication) {
      const version = versions.find(row => knowledgePinMatches(row,{knowledge_id:publication.knowledge_id,version:publication.version,knowledge_sha256:publication.knowledge_sha256})) || publication;
      const later = new Set(knowledgeUses(version,data?.uses).map(use => use.claim_id).filter(id => id && id !== state.claim_id)).size;
      return {kind:'published',pin:{knowledge_id:publication.knowledge_id,version:publication.version,knowledge_sha256:publication.knowledge_sha256 || '',definition_sha256:version.qualification?.definition_sha256 || version.definition_sha256 || ''},label:`${procedureLabel(publication)} · version ${publication.version} · ${indexed && later ? `reused by ${later} later case${later === 1 ? '' : 's'}` : 'saved for reuse'}`};
    }
    const use = list(state?.knowledge_uses).filter(item => item?.knowledge_id && item.version).at(-1);
    if (!use) return null;
    return {kind:'reused',pin:{knowledge_id:use.knowledge_id,version:use.version,knowledge_sha256:use.knowledge_sha256 || '',definition_sha256:use.definition_sha256 || '',claim_id:state.claim_id},label:`${procedureLabel(use)} · version ${use.version} · reused in this case`};
  }
  function knowledgePayoffMarkup(state, data = null) {
    const payoff = knowledgePayoff(state,data);
    return payoff ? `<p class="au-knowledge-payoff" data-au-knowledge-payoff="${h(payoff.kind)}"><span class="au-now-label">Knowledge</span> <a href="${h(knowledgeFragment(payoff.pin))}">${h(payoff.label)}</a></p>` : '';
  }
  // The tour ends at the last version its cases published, opened on a later
  // tour case's reuse receipt when one exists; otherwise at the last reuse.
  function tourKnowledgePayoff(data, claimIds = []) {
    const model = knowledgeLearningModel(data), ids = list(claimIds), place = id => ids.indexOf(id);
    const ordered = rows => rows.map(event => ({event,at:model.events.indexOf(event)})).sort((a,b) => place(a.event.claim_id || a.event.source_claim_id) - place(b.event.claim_id || b.event.source_claim_id) || a.at - b.at).map(row => row.event);
    const published = ordered(model.events.filter(event => event.kind === 'knowledge.published' && !event.refused && event.versionRecord && ids.includes(event.source_claim_id || event.claim_id))).at(-1);
    const fromUse = published ? null : ordered(model.events.filter(event => event.kind === 'knowledge.used' && event.versionRecord && ids.includes(event.claim_id))).at(-1);
    const version = published?.versionRecord || fromUse?.versionRecord;
    if (!version) return null;
    const source = version.source_claim_id || published?.source_claim_id;
    const receipts = model.events.filter(event => event.kind === 'knowledge.used' && event.versionRecord === version);
    const receiving = ordered(receipts.filter(event => event.claim_id !== source && ids.includes(event.claim_id))).at(-1) || fromUse;
    const later = new Set(receipts.map(event => event.claim_id).filter(id => id && id !== source)).size;
    const pin = {knowledge_id:version.knowledge_id,version:version.version,knowledge_sha256:version.knowledge_sha256 || '',definition_sha256:version.qualification?.definition_sha256 || version.definition_sha256 || '',...(receiving?.claim_id ? {claim_id:receiving.claim_id} : {})};
    const label = `${procedureLabel(version)} · version ${version.version}`;
    return {pin,label,receipts:receipts.length,announcement:`${label}${source ? `, saved from ${caseLabel(source).primary}` : ''}${later ? `, reused by ${later} later case${later === 1 ? '' : 's'}` : ''}.`};
  }
  function releaseProcedurePreview(plan, mode = 'live', options = {}) {
    const unrun = options.revision === 0, trace = {releasePlan:plan,rows:[],sources:new Map(),unrun};
    const line = language.modeLine({revision:Number.isSafeInteger(options.revision) ? options.revision : null,presentation:'replay',origin:'featured',readOnly:Boolean(options.readOnly)});
    return `<section class="au-quiet-claim" data-au-stage-view="true" data-au-release-opening="${h(plan.claim_id)}"><header class="au-work-head au-focused-claim-head"><div><p class="au-eyebrow"><button type="button" class="au-back-work" data-au-nav="work">Cases</button></p><h1 class="au-page-heading" tabindex="-1">${h(featuredCase(plan.claim_id)?.label || 'Fictional case')}</h1><p class="au-reference-mode">${h(line)}</p></div></header>${options.tour && !unrun ? demoTransportMarkup(options.tour) : ''}${nowMarkup(plan,[],{operations:trace,mode:'replay'})}<section class="au-evidence-canvas" data-au-canvas><div class="au-evidence-stage" data-au-evidence-stage>${operationStageMarkup(plan,{},null,trace)}${unrun ? '' : `<div class="au-stage-transport">${button('Pause','data-au-demo-stop')}</div>`}</div></section></section>`;
  }
  // A verified historical head supplies a plan, never the earlier prefix's
  // facts, conditions, requirements, completion flags or accepted outcome.
  async function plannedOperationProcess(state) {
    const graph = state?.graph, context = state?.semantic_contexts?.[state.run_id];
    if (!graph || graph.family === 'incoming_packet' || !isHash(graph.graph_sha256) || graph.claim_id !== state.claim_id || !isHash(state.state_sha256) || context?.claim_id !== state.claim_id) return null;
    const pack = list(context.rule_packs).find(row => row.family === graph.family), catalog = pack?.process_catalog;
    if (!Array.isArray(catalog?.nodes) || !Array.isArray(catalog.transitions) || !Array.isArray(catalog.documents) || !Array.isArray(graph.nodes) || !Array.isArray(graph.edges)) return null;
    const rulePackHash = pack.template_sha256;
    if (!isHash(rulePackHash)) return null;
    const use = list(state.knowledge_uses).findLast(row => row.workflow_id === state.run_id && row.knowledge_id === `procedure.${graph.family}`);
    if (use && (!isHash(use.definition_sha256) || use.rule_pack_sha256 !== rulePackHash || !list(context.compatible_knowledge).some(row => row.knowledge_id === use.knowledge_id && row.version === use.version && row.rule_pack_sha256 === rulePackHash && (!use.knowledge_sha256 || row.knowledge_sha256 === use.knowledge_sha256)))) return null;
    const nodes = catalog.nodes.map(node => ({node_id:node.node_id,label:recordedName(node),document_types:catalog.documents.filter(row => list(row.required_at_node_ids).includes(node.node_id)).map(row => row.document_type)}));
    const topology = (nodes,edges) => ({nodes:nodes.map(node => ({id:node.node_id,label:recordedName(node),documents:[...list(node.document_types)].sort()})),edges:edges.map(edge => ({id:edge.edge_id,from:edge.source_node_id,to:edge.target_node_id}))});
    // Comparing the entire pinned catalog prevents a case-pruned head from
    // silently dropping a branch from the early, unresolved plan.
    if (canonicalJSON(topology(nodes,catalog.transitions)) !== canonicalJSON(topology(graph.nodes,graph.edges))) return null;
    const ids = new Set(nodes.map(node => node.node_id));
    if (ids.size !== nodes.length || ids.has(undefined) || catalog.transitions.some(edge => !ids.has(edge.source_node_id) || !ids.has(edge.target_node_id))) return null;
    return {claim_id:state.claim_id,head_revision:state.revision,head_state_sha256:state.state_sha256,head_event_sha256:state.last_event_sha256,rule_pack_sha256:rulePackHash,
      procedure:use ? {knowledge_id:use.knowledge_id,version:use.version,definition_sha256:use.definition_sha256,knowledge_sha256:use.knowledge_sha256 || list(context.compatible_knowledge).find(row=>row.knowledge_id===use.knowledge_id && row.version===use.version && row.rule_pack_sha256===use.rule_pack_sha256)?.knowledge_sha256} : null,
      graph:{claim_id:state.claim_id,graph_sha256:graph.graph_sha256,family:graph.family,nodes,
        edges:catalog.transitions.map(edge => ({edge_id:edge.edge_id,source_node_id:edge.source_node_id,target_node_id:edge.target_node_id,label:edge.condition})),
        document_catalog:catalog.documents.map(row => ({document_type:row.document_type,label:recordedName(row)}))},evaluation:{nodes:[],edges:[],documents:[]},facts:[],obligations:[]};
  }
  function operationStageGraph(trace, state) {
    const graph = workingProcessState(trace)?.graph || state.graph;
    const planned = trace?.plannedProcess || trace?.releasePlan;
    return graph?.family !== 'incoming_packet' ? graph : planned?.claim_id === state.claim_id ? planned.graph : graph;
  }
  function operationReadDuration(operation) {
    const span = stageFactSpan(operation,operation?.kind === 'fact.extract' || operation?.kind === 'document.check');
    return Math.min(4200,Math.max(700,Array.from(span?.quote || '').length*24));
  }
  function operationChoreographyTiming(operation,trace) {
    return trace?.openingConsequenceId === operation?.id ? {read:360,transfer:300} : {read:Math.min(1000,operationReadDuration(operation)),transfer:600};
  }
  // Cues carry the identity of an already checked operation. A cited excerpt may
  // show a smaller part of an ancestor read, but cannot claim an unrelated read.
  function operationCues(operation, trace, {reducedMotion = false} = {}) {
    if (reducedMotion || !operation?.id || !list(trace?.rows).some(row => row.id === operation.id && row.kind === operation.kind)) return [];
    const cue = (name, trigger = operation) => ({name,kind:trigger.kind,operation_id:trigger.id});
    if (operation.kind === 'span.read' && operation.source?.quote) return [cue('reading')];
    if (operation.kind === 'fact.extract' && operation.source?.quote) {
      const rows = new Map(trace.rows.map(row => [row.id,row])), seen = new Set(), pending = [...list(operation.cause_ids)];
      let read = null;
      while (pending.length) {
        const id = pending.shift(); if (seen.has(id)) continue; seen.add(id);
        const row = rows.get(id); if (!row) continue;
        const pin = row.source, source = operation.source;
        if (row.kind === 'span.read' && pin && pin.artifact_id === source.artifact_id && pin.sha256 === source.sha256 && pin.text_sha256 === source.text_sha256 && pin.start_char <= source.start_char && pin.end_char >= source.end_char) { read = row; break; }
        pending.push(...list(row.cause_ids));
      }
      return [...(read ? [cue('reading',read)] : []),cue('thread'),cue('landing')];
    }
    if (operation.kind === 'verification.check' && operation.result?.accepted === true && operation.object?.type === 'fact') return [cue('confirmation')];
    if (operation.kind === 'document.check' && operation.result?.assessment === 'sufficient' && operation.source) return [cue('document')];
    if (operation.kind === 'step.complete' && operation.result?.status === 'completed') return [cue('completion'),cue('connector'),cue('progress')];
    if (operation.kind === 'decision' && operation.result?.summary) return [cue('answer')];
    if (operation.kind === 'knowledge.reuse' && Number.isSafeInteger(operation.input?.version)) return [cue('reuse')];
    return [];
  }
  function completedStepFraction(state) {
    const nodes = list(state.graph?.nodes);
    return nodes.length ? nodes.filter(node => list(state.evaluation?.nodes).some(row => row.node_id === node.node_id && DONE_NODE_STATES.includes(row.execution_state))).length / nodes.length : 0;
  }
  function operationReading(trace) {
    const operation = trace?.current;
    if (!operation) return null;
    const cause = trace.rows.find(row => row.id === operation.cause_ids?.at(-1)), currentPin = operation.source || (operation.kind === 'phrase.match' ? cause?.source : null);
    const reading = currentPin ? {artifact_id:currentPin.artifact_id,pin:currentPin,id:operation.id} : operation.kind === 'source.open' ? {artifact_id:operation.object.id,id:operation.id} : trace.displaySource;
    const source = trace.sources.get(reading?.artifact_id), chars = source && sourceCharacters(source);
    // Retained text is useful context. Only a current, bounded cited read gets
    // agent ink. A decision's citation remains inspection context while its
    // visible map and outcome take focus; its hidden source is never read.
    const active = Boolean(operation.kind !== 'decision' && !trace.inkRetired && currentPin && source && !(operation.kind === 'phrase.match' && operation.result.matched === false) &&
      !(operation.kind === 'span.read' && currentPin.start_char === 0 && currentPin.end_char === chars.length));
    return source ? {...reading,source,chars,active} : null;
  }
  function stageFactSpan(operation, compact = false) {
    const pin = operation?.source; if (!pin?.quote) return null;
    const sentences = pin.quote.split(/(?<=[.!?])\s+(?=[A-Z])/u), meaning = `${operation.object?.id || ''} ${operation.input?.document_type || ''}`;
    const semantic = /small.*(?:tenant|maintenance)|tenant.*cause/u.test(meaning) ? /outside.*small.*maintenance|no tenant.*misuse/iu :
      /landlord_first_knowledge/u.test(meaning) ? /first.*documented knowledge|received the first report/iu :
      /landlord.*knowledge/u.test(meaning) ? /call log|first.*knowledge|first.*report/iu :
      /objective.*use.*impairment/u.test(meaning) ? /inadequate|impair|contracted.*use/iu :
      /objective.*(?:defect|observation)|observation/u.test(meaning) ? /measured|observed|logger/iu :
      /residential_tenancy_scope/u.test(meaning) ? /residential lease|residential tenancy/iu :
      /tenancy_terms|lease_contract/u.test(meaning) ? /CHF|net rent|lease requires/iu :
      /continuing.*defect|repair_status/u.test(meaning) ? /no lasting repair|no.*repair|continuing defect/iu : null;
    let sentence = /continuing.*defect|repair_status/u.test(meaning) ? sentences.find(value => /no lasting repair/iu.test(value)) : null;
    sentence ||= semantic ? sentences.find(value => semantic.test(value)) : null;
    if (!sentence && operation.kind !== 'fact.extract') sentence = sentences.find(value => /measured|monthly|call log/iu.test(value));
    // A fact without a semantic match retains its native citation. A convenient
    // number in another sentence must never stand in for that fact's meaning.
    if (!sentence && operation.kind === 'fact.extract') {
      if (!compact) return pin;
      const term = /tenancy_terms|lease_contract/u.test(meaning) && pin.quote.match(/indefinite(?: ordinary)? residential lease/iu);
      const quote = term?.[0] || pin.quote.match(/^.*?(?:[.!?;](?=\s|$)|\r?\n|$)/su)?.[0].trim() || pin.quote;
      const start_char = pin.start_char+Array.from(pin.quote.slice(0,pin.quote.indexOf(quote))).length;
      return {...pin,start_char,end_char:start_char+Array.from(quote).length,quote};
    }
    sentence ||= pin.quote;
    const clausePattern = /continuing.*defect|repair_status/u.test(meaning) ? /\b(?:no lasting repair|no.*repair)\b/iu : /small.*(?:tenant|maintenance)|tenant.*cause/u.test(meaning) ? /\b(?:outside ordinary small tenant maintenance|no tenant alteration)\b/iu : /\b(?:measured|monthly|call log|records|reported)\b/iu;
    if (/small.*(?:tenant|maintenance)|tenant.*cause/u.test(meaning)) { const first = sentences.findIndex(value => /outside.*small.*maintenance/iu.test(value)), last = sentences.findIndex(value => /no tenant.*misuse/iu.test(value)); if (first >= 0 && last >= first) { const begin = pin.quote.indexOf(sentences[first]); sentence = pin.quote.slice(begin,pin.quote.indexOf(sentences[last],begin)+sentences[last].length); } }
    const clauseStart = sentence.search(clausePattern); let clause = sentence.slice(Math.max(0,clauseStart));
    if (compact) clause = clause.match(/CHF\s*[\d'.,]+|\d+(?:[.,]\d+)?\s*°?C|(?:one|two|three|four|five|\d+)\b.{0,55}?\breports?\b/iu)?.[0] || clause;
    if (compact) {
      const grounded = /residential_tenancy_scope/u.test(meaning) ? pin.quote.match(/(?:ordinary\s+residential\s+lease|indefinite\s+residential\s+lease|residential\s+tenancy)/iu) : /landlord_first_knowledge/u.test(meaning) ? pin.quote.match(/received the first report(?:\s+on\s*\d{4}-\d{2}-\d{2})?/iu) : /objective.*use.*impairment/u.test(meaning) ? pin.quote.match(/Heating is inadequate/iu) : /continuing.*defect|repair_status/u.test(meaning) ? pin.quote.match(/no lasting repair has yet occurred/iu) : null;
      if (grounded) clause=grounded[0];
      else if (Array.from(clause).length > 48) clause=clause.match(/^.*?(?:[.!?;](?=\s|$)|\r?\n|$)/su)?.[0].trim() || clause;
    }
    let chars = Array.from(clause).slice(0,compact ? Array.from(clause).length : /small.*(?:tenant|maintenance)|tenant.*cause/u.test(meaning) ? Array.from(clause).length : semantic || operation.kind !== 'fact.extract' ? 160 : Array.from(clause).length); if (chars.length < Array.from(clause).length) { const boundary = chars.lastIndexOf(' '); if (boundary > (compact ? 20 : 80)) chars = chars.slice(0,boundary); }
    const quote = chars.join(''), start_char = pin.start_char+Array.from(pin.quote.slice(0,pin.quote.indexOf(clause))).length;
    return {...pin,start_char,end_char:start_char+chars.length,quote};
  }
  function stageFactText(operation) { return stageFactSpan(operation)?.quote || ''; }
  function operationSourceTitle(source) { return language.documentTitle(source || {}); }
  function stageFactLabel(operation, state, graph = state.graph) {
    const fact = list(state.facts).find(row => row.fact_id === operation.object.id);
    const obligation = list(state.obligations).find(row => list(row.required_fact_ids).includes(operation.object.id));
    const type = fact?.document_type || obligation?.document_type || (operation.object.id.startsWith('fact:') ? operation.object.id.slice(5) : operation.input?.document_type);
    return name(list(graph?.document_catalog).find(row => row.document_type === type)) || fact?.label || fact?.title || fact?.name || words(operation.object.id.replace(/^fact:/,''));
  }
  // Accepted operation rows are append-only. Inspection prefixes use distinct
  // arrays, so their presentation indexes cannot see later source checks.
  const stageDocumentIndexes = new WeakMap();
  function stageDocumentIndex(rows) {
    let index = stageDocumentIndexes.get(rows);
    if (!index || index.length > rows.length || index.last !== rows[index.length-1]) {
      index = {length:0,last:null,requirements:new Map(),checks:new Map()}; stageDocumentIndexes.set(rows,index);
    }
    for (let position = index.length; position < rows.length; position++) {
      const row = rows[position], id = row.object?.id;
      if (row.kind === 'document.require') { index.requirements.delete(id); index.requirements.set(id,row); }
      if (row.kind === 'document.check' && row.result.assessment === 'sufficient' && row.source) index.checks.set(id,row);
    }
    index.length = rows.length; index.last = rows.at(-1);
    return index;
  }
  function stageNodeContents(node, state, trace, working, map = false, plannedGraph = null, reuse = null) {
    const graph = plannedGraph || working?.graph || state.graph, rows = list(trace?.rows);
    const facts = [...(trace?.dockedFacts?.values() || [])].filter(row => row.node === node.node_id && (row.observed || list(state.facts).some(fact => fact.fact_id === row.operation.object.id)));
    const chips = facts.map(row => { const span = stageFactSpan(row.operation,true); return `<button type="button" class="au-stage-fact" data-au-full-quote="${h(span.quote)}" data-au-fact-state="${row.operation.result.verification_required === false && list(state.facts).some(fact => fact.fact_id === row.operation.object.id) ? 'accepted' : 'observed'}" data-au-stage-fact="${h(row.operation.object.id)}" data-au-current-fact="${trace?.current?.id === row.operation.id}"${trace?.recentFact === row.operation.object.id ? ' data-au-landed-recent' : ''}${trace?.confirmedFacts?.has(row.operation.object.id) ? ' data-au-fact-confirmed="true"' : ''} data-au-fact-operation="${h(row.operation.id)}" data-au-dock-phase="${trace?.finished ? 'landed' : trace?.dockPhases?.get(row.operation.id) || 'landed'}" data-au-fact-start-char="${span.start_char}" data-au-fact-end-char="${span.end_char}" data-au-inspect="operation" data-au-record-id="${h(row.operation.id)}" ><span>${h(span.quote)}</span></button>`; }).join('');
    const accepted = new Map(list(state.evaluation?.documents).map(row => [row.document_type,row]));
    const observed = trace && stageDocumentIndex(rows);
    const activeRequirements = !plannedGraph && (trace ? [...observed.requirements.values()].reverse().filter(row => row.result.activation === 'true' && list(row.result.active_node_ids).includes(node.node_id) && list(node.document_types).includes(row.object.id)) : list(state.obligations).filter(row => requiringNodeIds(row,accepted.get(row.document_type)).includes(node.node_id))) || [];
    const requirements = list(node.document_types).map(type => activeRequirements.find(row => (row.object?.id || row.document_type) === type) || {document_type:type,planned:true});
    const slots = requirements.map(requirement => {
      const type = requirement.object?.id || requirement.document_type, doc = accepted.get(type), label = stageName(list(graph?.document_catalog).find(row => row.document_type === type)) || stageName(requirement) || words(type);
      const check = !requirement.planned && observed?.checks.get(type);
      const obligation = list(state.obligations).find(row => row.document_type === type);
      const citation = check?.source || (!trace && !requirement.planned ? list(obligation?.required_fact_ids).flatMap(id => citationRows(list(state.facts).find(row => row.fact_id === id)))[0] : null);
      const checked = !requirement.planned && doc?.review_state === 'sufficient' && (!trace || Boolean(check));
      const source = checked && citation && (trace?.sources.get(citation.artifact_id) || list(state.acquired_sources).find(row => row.artifact_id === citation.artifact_id));
      const preview = citation && stageFactSpan(check || {source:citation,object:{id:type}},true);
      const dockPhase = trace?.finished ? 'landed' : trace?.dockPhases?.get(check?.id) || 'landed';
      return `<div class="au-stage-slot" data-au-document="${h(type)}" data-au-stage-document="${h(type)}" data-au-document-active="${!requirement.planned}" data-au-document-planned="${Boolean(requirement.planned)}" data-au-recipe-known="${Boolean(reuse && list(reuse.recipes).some(recipe=>recipe.document_type===type))}" data-au-document-supported="${Boolean(source)}" data-au-document-checked="${Boolean(source) && dockPhase === 'landed'}" data-au-document-focused="${trace?.current?.object.id === type || trace?.current?.object.id === `fact:${type}`}"${check && !trace?.finished && trace?.recentLanding === check.id && dockPhase === 'landed' ? ' data-au-landed-recent' : ''}${requirement.id ? ` data-au-working-document="${h(type)}" data-au-operation-id="${h(requirement.id)}" data-au-working-graph-sha="${h(requirement.result.graph_sha256)}" data-au-working-evaluation-sha="${h(requirement.result.evaluation_sha256)}"` : ''}>${source ? '' : `<span>${h(label)}${requirement.planned ? '' : doc?.review_state === 'missing' ? ' — missing' : ' — to check'}</span>${requirement.planned ? '' : '<span class="au-stage-source-check au-document-needed">Needed</span>'}`}<div class="au-stage-landing">${source ? `<button type="button" class="au-stage-thumbnail" data-au-dock-phase="${dockPhase}" data-au-source="${h(source.artifact_id)}" data-au-source-origin="${check ? `operation:${h(check.id)}` : `requirement:${h(requirementIdentity(obligation))}`}" data-au-citation="${h(JSON.stringify(citation))}"${check ? ` data-au-check-operation="${h(check.id)}"` : ''} aria-label="${h(operationSourceTitle(source))} · Supported by documents"><span class="au-stage-source-name">${h(operationSourceTitle(source))}</span><span class="au-stage-source-check">Received ✓</span></button>` : ''}</div></div>`;
    }).join('');
    return chips+(slots?`<div class="au-stage-documents">${slots}</div>`:'');
  }
  function recordedReuseMoment(state, trace, knowledge = {}) {
    if(!trace || trace.finished || trace.current?.kind!=='knowledge.reuse')return null;
    const use=list(state.knowledge_uses).findLast(row=>row.workflow_id===state.run_id && row.knowledge_id===trace.current.object.id && row.version===trace.current.input?.version);
    if(!use || !isHash(use.definition_sha256))return null;
    const event=[...list(trace.journal)].reverse().find(row=>row.kind==='knowledge.used' && row.seq<=state.revision && row.claim_id===state.claim_id && row.payload?.knowledge?.knowledge_id===use.knowledge_id && row.payload.knowledge.version===use.version && row.payload.knowledge.definition_sha256===use.definition_sha256 && canonicalJSON(row.payload.knowledge)===canonicalJSON(use));
    const context=state.semantic_contexts?.[state.run_id],pin=list(context?.compatible_knowledge).find(row=>row.knowledge_id===use.knowledge_id && row.version===use.version && row.rule_pack_sha256===use.rule_pack_sha256 && isHash(row.knowledge_sha256));
    if(!event || !pin || trace.current.input.knowledge_sha256!==pin.knowledge_sha256 || trace.current.input.definition_sha256!==use.definition_sha256)return null;
    const version=list(knowledge.versions).find(row=>knowledgePinMatches(row,{...use,knowledge_sha256:pin.knowledge_sha256}));
    const plan=trace.plannedProcess, planned=plan?.claim_id===state.claim_id && plan.procedure?.knowledge_id===use.knowledge_id && plan.procedure.version===use.version && plan.procedure.definition_sha256===use.definition_sha256 && plan.procedure.knowledge_sha256===pin.knowledge_sha256;
    const graph=version?.graph || (planned?plan.graph:null);
    if(!graph)return null;
    return {event,use,pin:{...use,knowledge_sha256:pin.knowledge_sha256},graph,recipes:version?.evidence_recipes || pin.evidence_recipes || []};
  }
  function recordedReuseMomentMarkup(moment) {
    if(!moment)return '';
    return `<div class="au-stage-knowledge-moment" data-au-knowledge-moment="${h(moment.event.event_sha256)}" data-au-knowledge-use="${h(moment.pin.knowledge_sha256)}"><p>Procedure reused · ${knowledgeLink(moment.pin,`Version ${moment.use.version}`)} · ${list(moment.recipes).length} known document checks${Number.isSafeInteger(moment.use.avoided_rule_compilations)?` · ${moment.use.avoided_rule_compilations===1?'Reused once instead of rebuilding':`Reused ${moment.use.avoided_rule_compilations} times instead of rebuilding`}`:''} · ${recordButton('Reuse receipt','event',String(moment.event.seq))}</p></div>`;
  }
  function operationStageMarkup(state, projection, selected, trace, settled = false, knowledge = {}, inspection = {}) {
    const reuseMoment=recordedReuseMoment(state,trace,knowledge), retainedReuse=trace?.cueReuse;
    const workingState = workingProcessState(trace), actual = workingState?.graph?.family !== 'incoming_packet' ? workingState : null;
    const availablePlan = trace?.plannedProcess || trace?.releasePlan;
    const planned = !settled && !trace?.finished && (!actual?.graph && (!state.graph || state.graph.family === 'incoming_packet' || state === trace?.releasePlan)) && availablePlan?.claim_id === state.claim_id ? availablePlan : null;
    const working = actual && trace.working, process = planned || actual || state;
    const graph = process.graph?.family !== 'incoming_packet' ? process.graph : null;
    const map = settled || trace?.finished || trace?.current?.kind === 'decision';
    const boundNode = graph && operationNodeId(trace?.current,graph,state,trace);
    const currentNode = boundNode || (list(graph?.nodes).some(row => row.node_id === selected) ? selected : null);
    const outcome = trace?.current?.kind === 'decision' && !trace.finished ? trace.current.result : state.outcome;
    const uses = list(state.knowledge_uses), used = uses.at(-1);
    const exact = used && list(state.semantic_contexts?.[state.run_id]?.compatible_knowledge).find(row=>row.knowledge_id===used.knowledge_id && row.version===used.version && row.rule_pack_sha256===used.rule_pack_sha256 && isHash(row.knowledge_sha256));
    const use=used && exact ? {...used,knowledge_sha256:exact.knowledge_sha256} : used;
    const scope = working ? ` data-au-working-scope="${h(working.inspect.id)}" data-au-working-graph-sha="${h(graph?.graph_sha256)}" data-au-working-evaluation-sha="${h(working.inspect.result.evaluation_sha256)}" data-au-operation-stage="${h(working.stage)}"` : '';
    const sourceView = trace?.current && operationReading(trace)?.active ? operationReadingMarkup(trace,true) : '';
    const prefixIdentity = Number.isSafeInteger(state.revision) && isHash(state.state_sha256) ? ` data-au-forming-revision="${state.revision}" data-au-forming-sha="${h(state.state_sha256)}"` : '';
    const planAttributes = planned?.release ? ` data-au-release-plan="${h(planned.release.artifact_sha256)}" data-au-release-profile-sha="${h(planned.release.profile_sha256)}" data-au-release-catalog-sha="${h(planned.release.catalog_sha256)}" data-au-release-rule-pack-sha="${h(planned.release.rule_pack_sha256)}" data-au-release-authority="none"` : planned ? ` data-au-planned-process="${h(planned.head_state_sha256)}" data-au-planned-head-revision="${planned.head_revision}" data-au-planned-graph-sha="${h(graph.graph_sha256)}" data-au-planned-rule-pack-sha="${h(planned.rule_pack_sha256)}" data-au-planned-knowledge="${h(planned.procedure?.knowledge_id || '')}" data-au-planned-version="${planned.procedure?.version || ''}" data-au-planned-definition-sha="${h(planned.procedure?.definition_sha256 || '')}" data-au-planned-authority="none"` : '';
    const planLabel = planned?.release ? trace?.unrun ? h(language.copy.procedureNotRun) : 'Procedure outline' : planned?.procedure ? knowledgeLink(planned.procedure,`${procedureLabel(planned.procedure)} · Version ${planned.procedure.version}`) : 'Recorded procedure · planned steps';

    return `<section class="au-forming-work au-operation-stage" data-au-stage-phase="${map ? 'map' : 'source'}" data-au-forming="${!map}"${prefixIdentity}><div class="au-forming-layout au-stage-layout">${!map && sourceView ? `<div class="au-forming-reading au-stage-source au-stage-unbound-source">${sourceView}</div>` : ''}${graph ? `<section class="au-forming-process au-evidence-process au-stage-process" aria-label="${planned?.release ? 'Procedure outline' : planned ? 'Planned recorded process' : 'Case process'}"${planAttributes}${scope}>${retainedReuse ? `<p class="au-reuse-cue" data-au-reuse-cue="${h(retainedReuse.operation)}">Reused · ${h(procedureLabel(retainedReuse.pin))} v${retainedReuse.pin.version}</p>` : ''}${trace?.unrun ? `<p class="au-stage-plan-label">${planLabel}</p>` : ''}${graphMarkup(process,currentNode,working ? {} : projection,{overview:true,working,stage:{state,trace,map,planned:Boolean(planned),reuse:reuseMoment,excerpt:''}})}</section>` : ''}</div>${map && outcome?.summary ? `<div class="au-stage-outcome" data-au-stage-outcome><span class="au-answer-rule" aria-hidden="true"></span>${outcomeSummaryMarkup(state,outcome,legalBasisMarkup({...state,outcome})+(use ? `<p class="au-stage-reuse">Reused procedure · ${knowledgeLink(use,`${procedureLabel(use)} · Version ${use.version || use.version_id}`,state.claim_id)}. This case still needed its own proof.</p>` : '')+(!use ? knowledgePayoffMarkup(state,knowledge) : ''))}</div>` : ''}${map && inspection.chosen && inspection.chosen === currentNode && list(state.graph?.nodes).some(row => row.node_id === currentNode) ? `<section class="au-stage-step-detail" data-au-stage-step-detail="${h(currentNode)}" aria-label="Selected step">${stepDetailMarkup(state,currentNode,projection,inspection.context || {})}<p class="au-stage-step-back"><button type="button" class="au-link" data-au-back-process>Back to the steps</button></p></section>` : ''}</section>`;
  }
  function operationRoutePreference(fragment = '', search = '') {
    const query = fragment.includes('?') ? fragment.slice(fragment.indexOf('?')+1) : '';
    return new URLSearchParams(query).get('operations') === 'recorded' || new URLSearchParams(search).get('operations') === 'recorded' ? 'recorded' : 'live';
  }
  function claimFragment(id, preferences = {}) {
      const params = new URLSearchParams();
      if (preferences.operations === 'recorded') params.set('operations','recorded');
      if (preferences.mode === 'replay') { if (preferences.collection) params.set('collection',preferences.collection); params.set('mode','replay'); params.set('through',String(preferences.through || 0)); }
      const contextual = ['node','document','obligation','fact'].some(field => preferences[field]);
      if (contextual || preferences.detail && preferences.detail !== 'step') params.set('detail',preferences.detail || 'step');
      for (const field of ['node','document','obligation','fact']) if (preferences[field]) params.set(field,preferences[field]);
      if (preferences.trace && preferences.fact) params.set('trace','1');
      return `#autonomous/claim/${key(id)}${params.size ? '?' + params : ''}`;
    }
  function operationAttention(operation, trace) {
    // The source acquisition, scans, phrase matches and evaluation machinery
    // remain in the verified native stream. One consequence owns one visible
    // excerpt read: the first actual fact, sufficient source check or outcome.
    if (operation.kind === 'step.complete') return operation.result?.status === 'completed';
    if (operation.kind === 'verification.check') return operation.result?.accepted === true && Boolean(trace.dockedFacts?.has(operation.object?.id));
    if (!['fact.extract','document.check','decision','knowledge.reuse'].includes(operation.kind)) return false;
    if (operation.kind === 'fact.extract' && !operation.source) return false;
    if (operation.kind === 'document.check' && (!operation.source || operation.result.assessment !== 'sufficient')) return false;
    trace.visibleResults ||= new Map();
    const key = `${operation.kind}:${operation.object.type}:${operation.object.id}`;
    const meaning={...operation.result};
    delete meaning.verification_required;
    for (const field of ['graph_sha256','evaluation_sha256','phase']) delete meaning[field];
    if (['provisional','established','verified','accepted','accepted_historical_command'].includes(meaning.status)) delete meaning.status;
    const identity = ['fact.extract','document.check'].includes(operation.kind) ? canonicalJSON({source:operation.source,input:operation.input,meaning}) : canonicalJSON(operation.result);
    if (trace.visibleResults.get(key) === identity) return false;
    trace.visibleResults.set(key,identity); return true;
  }
  const sourcePresentations = new WeakMap();
  let sourceSentences;
  function sourceCharacters(source) {
    let presentation = sourcePresentations.get(source);
    if (!presentation || presentation.text !== source.text) { presentation = {text:source.text,chars:Object.freeze(Array.from(source.text))}; sourcePresentations.set(source,presentation); }
    return presentation.chars;
  }
  function sourceBodySpan(source) {
    for (const match of source.text.matchAll(/[^\n]+(?:\n(?!\n)[^\n]+)*/gu)) {
      if (match[0].split('\n').every(line => /^(?:Synthetic |Fictional |Source date:|Review as-of:|Service author:|Speaker:|Property:|Claim id:)/iu.test(line))) continue;
      const start_char = Array.from(source.text.slice(0,match.index)).length;
      return {start_char,end_char:start_char+Array.from(match[0]).length,quote:match[0]};
    }
    return null;
  }
  function bufferedOperationCount(trace) {
    const result = trace?.buffer?.result, binding = trace?.binding || trace?.openingBinding;
    return result?.contract === OPERATIONS_CONTRACT && result.exact_output_verified === true && result.state_sha256 === binding?.current_state_sha256 && result.current_event_sha256 === binding?.current_event_sha256 && Number.isSafeInteger(result.operation_count) && result.operation_count > 0 && result.operation_count <= 4096 ? result.operation_count : null;
  }
  function operationInspection(trace, index) {
    if (!Number.isSafeInteger(index) || index < 0 || index >= trace.rows.length) return null;
    const checkpoint = [...list(trace.checkpoints)].reverse().find(row => row.after_operation <= index && row.state && row.projection);
    if (!checkpoint) return null;
    const rows = trace.rows.slice(0,index+1), operation = rows.at(-1);
    const display = {...trace,dockPhases:new Map(trace.dockPhases || []),rows,current:operation,consumed:operation,inkRetired:false,finished:false,savedFallback:false,state:checkpoint.state,working:null,workingScopes:new Map(),dockedFacts:new Map(),displaySource:null,inspection:true};
    for (const row of rows) {
      const cause = rows.find(item => item.id === row.cause_ids.at(-1)), pin = row.source || (row.kind === 'phrase.match' ? cause?.source : null);
      if (pin) display.displaySource = {artifact_id:pin.artifact_id,pin,id:row.id};
      else if (row.kind === 'source.open') display.displaySource = {artifact_id:row.object.id,id:row.id};
      if (row.seq > checkpoint.after_operation) applyWorkingOperation(row,display,checkpoint.state);
    }
    const graph = operationStageGraph(display,checkpoint.state);
    for (const row of rows) {
      if (row.kind !== 'fact.extract' || !row.source) continue;
      const node = operationNodeId(row,graph,checkpoint.state,display); if (node) display.dockedFacts.set(row.object.id,{operation:row,node,observed:true});
    }
    return {index,trace:display,state:checkpoint.state,projection:checkpoint.projection,events:checkpoint.events,checkpoint,node:operationNodeId(operation,graph,checkpoint.state,display)};
  }
  function operationReadingMarkup(trace, stage = false) {
    const operation = trace?.current;
    if (!operation) return '';
    const reading = operationReading(trace), pin = reading?.pin, source = reading?.source, chars = reading?.chars;
    const objectLabel = plain(operation.object.label,'') || name(list(trace.working?.graph?.nodes).find(row => row.node_id === operation.object.id)) || name(list(trace.working?.graph?.document_catalog).find(row => row.document_type === operation.object.id)) || name(list(trace.state?.graph?.nodes).find(row => row.node_id === operation.object.id)) || name(list(trace.state?.facts).find(row => row.fact_id === operation.object.id)) || name(list(trace.state?.obligations).find(row => row.obligation_id === operation.object.id || row.document_type === operation.object.id)) || name(list(trace.state?.graph?.document_catalog).find(row => row.document_type === operation.object.id)) || '';
    const summary = plain(language.operationPresentation(operation,{state:trace.state}).recordedResult,'Result recorded') || (typeof operation.result?.matched === 'boolean' ? operation.result.matched ? 'Phrase found' : 'Phrase absent' : '');
    const sourceHTML = value => h(value).replace(/\r/g,'&#13;');
    const inkPin = pin ? stage && reading?.active ? stageFactSpan({...operation,source:pin},operation.kind === 'fact.extract' || operation.kind === 'document.check') : pin : stage && operation.kind === 'source.open' && source ? sourceBodySpan(source) : null;
    const body = stage && source && sourceBodySpan(source);
    const section = (start,end) => body && body.start_char >= start && body.start_char < end ? `${sourceHTML(chars.slice(start,body.start_char).join(''))}<span data-au-source-body-anchor></span>${sourceHTML(chars.slice(body.start_char,end).join(''))}` : sourceHTML(chars.slice(start,end).join(''));
    const passage = chars ? inkPin ? `${section(0,inkPin.start_char)}<${reading.active ? 'mark' : 'span'} ${reading.active ? 'data-au-operation-span' : 'data-au-operation-read-context'}="${h(reading.id)}" data-au-operation-start-char="${inkPin.start_char}" data-au-operation-end-char="${inkPin.end_char}">${section(inkPin.start_char,inkPin.end_char)}</${reading.active ? 'mark' : 'span'}>${section(inkPin.end_char,chars.length)}` : section(0,chars.length) : '';
    if (stage) {
      if (!source || !inkPin) return '';
      const bodyStart=sourceBodySpan(source)?.start_char || 0;
      let left=inkPin.start_char, right=inkPin.end_char;
      // Native sentence boundaries keep decimals and complete cited words intact.
      let offset=bodyStart;
      for(const {segment} of (sourceSentences ||= new Intl.Segmenter('en',{granularity:'sentence'})).segment(chars.slice(bodyStart).join(''))) {
        const end=offset+Array.from(segment).length;
        if(offset<=inkPin.start_char && inkPin.start_char<end)left=offset;
        if(offset<inkPin.end_char && inkPin.end_char<=end){right=end;break;}
        offset=end;
      }
      while(left<inkPin.start_char && /\s/u.test(chars[left]))left++;
      while(right>inkPin.end_char && /\s/u.test(chars[right-1]))right--;
      const excerpt=`${sourceHTML(chars.slice(left,inkPin.start_char).join(''))}<${reading.active?'mark':'span'} ${reading.active?'data-au-operation-span':'data-au-operation-read-context'}="${h(reading.id)}" data-au-operation-start-char="${inkPin.start_char}" data-au-operation-end-char="${inkPin.end_char}" data-au-citation-start-char="${pin?.start_char ?? inkPin.start_char}" data-au-citation-end-char="${pin?.end_char ?? inkPin.end_char}">${sourceHTML(inkPin.quote)}</${reading.active?'mark':'span'}>${sourceHTML(chars.slice(inkPin.end_char,right).join(''))}`;
      return `<section class="au-operation-reading" data-au-operation-object="${h(operation.object.id)}" data-au-object-type="${h(operation.object.type)}" data-au-object-id="${h(operation.object.id)}"><button type="button" class="au-stage-source-title" data-au-source="${h(source.artifact_id)}" data-au-source-origin="operation:${h(reading.id)}"${pin?` data-au-citation="${h(JSON.stringify(pin))}"`:''}>${h(operationSourceTitle(source))}</button><pre class="au-operation-passage" data-au-compact-excerpt data-au-operation-source="${h(source.artifact_id)}" data-au-operation-text-sha="${h(source.text_sha256)}" data-au-source-active="${reading.active}">${excerpt}</pre></section>`;
    }
    return `<section class="au-operation-reading" data-au-operation-object="${h(operation.object.id)}" data-au-object-type="${h(operation.object.type)}" data-au-object-id="${h(operation.object.id)}"><p class="au-reading-label">${h(operationLabel(operation))}</p>${trace.previousCurrent?.id === operation.id && !trace.rows.some(row => row.id === operation.id) ? '<p class="au-meta">Earlier attempt stopped · waiting for the stored trace.</p>' : ''}${source ? `<button type="button" class="au-link" data-au-source="${h(source.artifact_id)}" data-au-source-origin="operation:${h(operation.id)}">${h(source.file_name || 'Original source')} ↗</button><pre class="au-operation-passage" data-au-operation-source="${h(source.artifact_id)}" data-au-operation-text-sha="${h(source.text_sha256)}">${passage}</pre>` : ''}${objectLabel || summary ? `<p class="au-operation-summary">${operation.object.type === 'source' ? '' : h(objectLabel)}${summary ? `${operation.object.type === 'source' || !objectLabel ? '' : ' · '}${h(summary)}` : ''}</p>` : ''}${operation.kind === 'fact.extract' && operation.result?.verification_required !== false ? '<p class="au-meta">Provisional finding · the saved process changes after verification.</p>' : operation.kind === 'knowledge.add' ? '<p class="au-meta">Historical addition · this demonstration saves no knowledge.</p>' : ''}<button type="button" class="au-link" data-au-inspect="operation" data-au-record-id="${h(operation.id)}">Inspect this step</button></section>`;
  }
  function operationHistoryMarkup(trace) {
    if (!trace?.binding && !trace?.previousAttempts?.length) return '';
    const previous = list(trace.previousAttempts).map((attempt,index) => `<section class="au-history-record"><h4>Earlier ${attempt.recorded ? 'recorded trace' : 'live assessment'} stopped</h4><p class="au-meta">${h(attempt.reason)}</p><ol class="au-event-list">${attempt.rows.slice().reverse().map(operation => `<li><button type="button" class="au-link" data-au-inspect="operation-attempt" data-au-record-id="${index}:${h(operation.id)}">${h(operationLabel(operation))} · ${h(plain(operation.object.label || words(operation.object.id),'Recorded item'))}</button></li>`).join('')}</ol></section>`).join('');
    return `<section class="au-operation-history"><h3>Recorded work</h3><p class="au-meta">${trace.savedFallback ? 'The attempted assessment stopped.' : !trace.binding ? 'Waiting for the stored operation trace.' : !trace.recorded && trace.binding.mode === 'historical_recomputed' ? 'Recomputed from the saved source packet.' : 'Recorded operation trace.'} Saved case history remains below.</p><ol class="au-event-list">${trace.rows.slice().reverse().map(operation => `<li><button type="button" class="au-link" data-au-inspect="operation" data-au-record-id="${h(operation.id)}">${h(operationLabel(operation))} · ${h(plain(operation.object.label || words(operation.object.id),'Recorded item'))}</button></li>`).join('')}</ol>${previous}</section>`;
  }
  function operationRecord(trace, kind, id) {
    if (kind === 'operation-attempt') {
      const separator = id.indexOf(':'), index = Number(id.slice(0,separator));
      return trace?.previousAttempts?.[index]?.rows.find(row => row.id === id.slice(separator+1)) || null;
    }
    return trace?.rows.find(row => row.id === id) || list(trace?.previousAttempts).flatMap(attempt => attempt.rows).find(row => row.id === id) || null;
  }
  async function checkedOperationCheckpoint(frame, trace) {
    const previous = trace.transportState;
    if (frame?.contract !== OPERATIONS_CONTRACT || frame.type !== 'checkpoint' || frame.verified !== true ||
        !trace.binding || !Number.isSafeInteger(frame.journal_seq) || frame.journal_seq < 0 ||
        previous && frame.journal_seq !== previous.revision+1 || !previous && frame.journal_seq !== trace.binding.from_seq) throw new Error('The operation checkpoint is out of sequence.');
    let state;
    if (frame.state) { if (previous) throw new Error('A full operation checkpoint replaced its delta base.'); state = frame.state; }
    else {
      if (!previous || frame.base_state_sha256 !== previous.state_sha256 || !frame.state_delta?.set || !Array.isArray(frame.state_delta.remove)) throw new Error('The operation checkpoint has no exact delta base.');
      state = {...previous,...frame.state_delta.set};
      for (const field of frame.state_delta.remove) { if (typeof field !== 'string') throw new Error('The operation checkpoint removal is invalid.'); delete state[field]; }
    }
    const material = {...state}; delete material.state_sha256;
    if (state.claim_id !== trace.binding.claim_id || state.revision !== frame.journal_seq || state.state_sha256 !== frame.state_sha256 ||
        state.last_event_sha256 !== frame.event_sha256 || await digest(canonicalJSON(material)) !== state.state_sha256) throw new Error('The operation checkpoint failed its exact state hash.');
    const priorEvents = previous ? trace.journal : trace.pinnedJournal.filter(event => event.seq < frame.journal_seq);
    if (list(frame.events).length !== 1 || canonicalJSON(frame.events[0]) !== canonicalJSON(trace.pinnedJournal.find(event => event.seq === frame.journal_seq))) throw new Error('The operation checkpoint event differs from its verified saved history.');
    const events = [...priorEvents,...list(frame.events)];
    if (frame.journal_seq > 0) {
      const event = events.at(-1), last = priorEvents.at(-1);
      if (event?.event_sha256 !== frame.event_sha256 || event?.previous_event_sha256 !== (last?.event_sha256 || null)) throw new Error('The operation checkpoint broke its saved event chain.');
    }
    const incoming = readReplay({...frame,state,events,projection:frame.projection || {claim_id:state.claim_id,revision:state.revision,state_sha256:state.state_sha256},replay_only:true},trace.binding.claim_id,frame.journal_seq);
    if (frame.current_revision !== trace.binding.current_revision || frame.current_state_sha256 !== trace.binding.current_state_sha256 || frame.current_event_sha256 !== trace.binding.current_event_sha256) throw new Error('The operation checkpoint changed its pinned saved head.');
    trace.transportState = state; trace.journal = events;
    return incoming;
  }
  async function checkedPreview(state, descriptor, response) {
    if (!response || response.preview_only !== true || response.evidence_admitted !== false || Object.prototype.hasOwnProperty.call(response,'receipt_sha256')) throw new Error('The source preview is not a read-only preview.');
    if (response.claim_id !== state.claim_id || response.artifact_id !== descriptor.artifact_id || response.sha256 !== descriptor.sha256 || response.file_name !== descriptor.file_name || response.media_type !== descriptor.media_type) throw new Error('The preview source identity differs from the original packet.');
    const material = {...response}; delete material.preview_sha256;
    if (!isHash(response.preview_sha256) || await digest(canonicalJSON(material)) !== response.preview_sha256) throw new Error('The source preview failed its identity check.');
    if (typeof response.text !== 'string' || !isHash(response.text_sha256) || await digest(response.text) !== response.text_sha256) throw new Error('The preview text failed its identity check.');
    const originalSource = list(state.original_binding?.source_map).some(source => source.artifact_id === descriptor.artifact_id);
    if (originalSource && response.original_binding_sha256 !== state.original_binding.original_binding_sha256) throw new Error('The source preview belongs to another original binding.');
    return response;
  }
  function readReplay(response, claimId, through) {
    const incoming = readState(response,claimId), state = incoming.state;
    if (response.mode !== 'replay' || response.replay_only !== true || response.through_seq !== through || state.revision !== through || !Number.isSafeInteger(response.current_revision) || response.current_revision < through || !isHash(response.current_state_sha256) || !response.provenance || typeof response.provenance !== 'object') throw new Error('The verified replay identity or provenance is incomplete.');
    if (response.current_revision === 0 ? response.current_event_sha256 !== null : !isHash(response.current_event_sha256)) throw new Error('The replay current head event identity is incomplete.');
    if (response.current_revision === through && (response.current_state_sha256 !== state.state_sha256 || response.current_event_sha256 !== state.last_event_sha256)) throw new Error('The replay prefix differs from the same saved head revision.');
    const provenance = response.provenance;
    for (const [field,stateField] of [['source_roster_sha256','source_roster_sha256'],['policy_id','policy_id'],['run_id','run_id'],['event_sha256','last_event_sha256']]) {
      if (state[stateField] !== undefined && (!Object.prototype.hasOwnProperty.call(provenance,field) || provenance[field] !== state[stateField])) throw new Error('The replay provenance differs from its recorded prefix.');
    }
    const binding = state.original_binding || {};
    for (const field of ['original_binding_sha256','claim_binding_sha256','corpus_manifest_sha256','static_template_sha256']) {
      if ((field === 'original_binding_sha256' && binding[field] !== undefined || Object.prototype.hasOwnProperty.call(provenance,field)) && provenance[field] !== (binding[field] ?? null)) throw new Error('The replay original binding provenance differs from its prefix.');
    }
    if (provenance.sources) {
      const sources = list(state.source_descriptors), recorded = list(provenance.sources);
      if (sources.length !== recorded.length || new Set(recorded.map(source => source.artifact_id)).size !== recorded.length || recorded.some((source,index) => { const original = sources[index]; return original.artifact_id !== source.artifact_id || original.sha256 !== source.sha256 || Object.keys(source).some(field => canonicalJSON(source[field]) !== canonicalJSON(original[field])); })) throw new Error('The replay source provenance differs from the prefix packet.');
    }
    if (provenance.source_map && canonicalJSON(provenance.source_map) !== canonicalJSON(binding.source_map || [])) throw new Error('The replay source map differs from its original binding.');
    if (provenance.rule_pack_sha256) {
      const packs = [...new Set(list(state.receipts).map(row => row.receipt?.rule_pack_sha256).filter(Boolean))].sort();
      if (canonicalJSON(provenance.rule_pack_sha256) !== canonicalJSON(packs)) throw new Error('The replay rule provenance differs from its recorded receipts.');
    }
    if (response.current_head && (response.current_head.revision !== response.current_revision || response.current_head.state_sha256 !== response.current_state_sha256 || response.current_head.event_sha256 !== response.current_event_sha256)) throw new Error('The replay current head identity differs from its envelope.');
    // Prefix state and events bind to their own revision, separately from the live head.
    const prefix = {...response,current_revision:state.revision,current_state_sha256:state.state_sha256};
    return {...readSnapshot(prefix,claimId,null,true),replay:response};
  }
  function checkedReferenceReplayStart(start, incoming) {
    if (start == null) return null;
    const state = incoming.state, reference = referenceExecution(state), event = incoming.accepted.events.find(row => row.seq === start.from_seq);
    const context = state.semantic_contexts?.[state.run_id];
    const sources = list(start.source_artifact_ids), expected = list(context?.sources).map(row => row.artifact_id);
    if (start.contract !== 'casepath.reference-replay-start/1.0.0' || start.claim_id !== state.claim_id ||
        !Number.isSafeInteger(start.from_seq) || start.from_seq < 1 || start.from_seq >= state.revision ||
        !isHash(start.state_sha256) || !isHash(start.event_sha256) || !isHash(start.profile_sha256) ||
        start.run_id !== state.run_id || start.profile_id !== 'synthetic-nine-v2' ||
        start.profile_id !== reference?.profile_id || start.profile_sha256 !== reference?.profile_sha256 ||
        state.outcome?.assessment_status !== 'complete' || event?.kind !== 'process.prepared' ||
        event.state_sha256 !== start.state_sha256 || event.event_sha256 !== start.event_sha256 ||
        !sources.length || new Set(sources).size !== sources.length ||
        canonicalJSON([...sources].sort()) !== canonicalJSON(expected.sort())) throw new Error('The current recording start differs from its accepted investigation.');
    return start;
  }
  function checkedReferenceReplayOpening(response, start, claimId) {
    const incoming = readReplay(response,claimId,start.from_seq), state = incoming.state, event = incoming.accepted.events.at(-1);
    if (state.state_sha256 !== start.state_sha256 || state.last_event_sha256 !== start.event_sha256 ||
        state.run_id !== start.run_id || state.outcome || event?.kind !== 'process.prepared') throw new Error('The current recording opening differs from its saved prefix.');
    return incoming;
  }
  function demoAssetURL(value, location) {
    const url = new URL(value, location.href);
    if (url.origin !== location.origin || url.username || url.password || !/^[a-f0-9]{64}$/i.test(url.searchParams.get('sha256') || '')) throw new Error('The fictional packet asset has no local content identity.');
    return url;
  }
  async function checkedExamples(bytes, expectedHash) {
    if (await digest(bytes) !== expectedHash.toLowerCase()) throw new Error('The fictional packet asset failed its identity check.');
    const value = JSON.parse(new TextDecoder().decode(bytes));
    if (!Array.isArray(value.packets) || value.packets.length > 20) throw new Error('The fictional packet list is invalid.');
    for (const packet of value.packets) {
      if (typeof packet.title !== 'string' || !packet.title || packet.title.length > 300 || typeof packet.message !== 'string' || !packet.message || packet.message.length > 100000 || !Array.isArray(packet.files) || packet.files.length > 20) throw new Error('A fictional packet is incomplete.');
      for (const file of packet.files) if (typeof file.file_name !== 'string' || !file.file_name || typeof file.media_type !== 'string' || typeof file.content_base64 !== 'string' || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(file.content_base64)) throw new Error('A fictional source file is invalid.');
    }
    return value.packets;
  }
  function prefillExample(form, packet) {
    if (!root.DataTransfer || !root.File) throw new Error('This browser cannot prefill supporting files.');
    const transfer = new root.DataTransfer();
    for (const file of packet.files) {
      const bytes = Uint8Array.from(root.atob(file.content_base64), char => char.charCodeAt(0));
      transfer.items.add(new root.File([bytes], file.file_name, {type:file.media_type}));
    }
    form.elements.files.files = transfer.files;
    form.elements.title.value = packet.title;
    form.elements.message.value = packet.message;
  }
  async function checkedSource(state, descriptor, response, citation) {
    const source = response.source || response;
    if (source.claim_id && source.claim_id !== state.claim_id) throw new Error('The source belongs to another claim.');
    if (source.artifact_id !== descriptor.artifact_id || source.sha256 !== descriptor.sha256 || typeof source.text !== 'string') throw new Error('The source identity differs from the saved packet.');
    const hash = await digest(source.text);
    if (!source.text_sha256 || source.text_sha256 !== hash) throw new Error('The source text failed its identity check.');
    let span = null;
    if (citation) {
      if (citation.artifact_id !== source.artifact_id || (citation.sha256 && citation.sha256 !== source.sha256) || (citation.text_sha256 && citation.text_sha256 !== hash)) throw new Error('The cited passage belongs to a different source version.');
      const chars = Array.from(source.text), start = citation.start_char, end = citation.end_char;
      if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 0 || end <= start || end > chars.length || chars.slice(start,end).join('') !== citation.quote) throw new Error('The exact cited passage could not be located in this source.');
      span = {before:chars.slice(0,start).join(''), quote:chars.slice(start,end).join(''), after:chars.slice(end).join('')};
    }
    return {source, span};
  }

  // A local checksum detects damaged saved representations. It is never a
  // server signature, source admission or permission to execute a command.
  async function checkedSavedSnapshot(snapshot, claimId) {
    if (!snapshot || !Array.isArray(snapshot.history) || snapshot.cursor !== snapshot.state?.revision) throw new Error('The saved copy has no matching event cursor.');
    const state = snapshot.state, events = snapshot.history;
    if (state?.contract !== 'casepath.autonomous-claim/1.0.0') throw new Error('The saved claim contract is unavailable.');
    const cursorHash = state?.revision === 0 ? null : state?.last_event_sha256 || events.at(-1)?.event_sha256;
    readSnapshot({state,projection:snapshot.projection,current_revision:state?.revision,current_state_sha256:state?.state_sha256,cursor_sha256:cursorHash,events},claimId,null,true);
    let previous = null;
    for (const event of events) {
      if (event.claim_id !== state.claim_id || event.contract && event.contract !== 'casepath.autonomous-event/1.0.0' || !isHash(event.event_sha256) || !isHash(eventIdentity(event).state_sha256)) throw new Error('The saved event identity is incomplete.');
      for (const field of ['previous_event_sha256','prev_event_sha256']) if (Object.prototype.hasOwnProperty.call(event,field) && event[field] !== previous) throw new Error('The saved event chain changed identity.');
      previous = event.event_sha256;
    }
    const descriptors = new Map();
    for (const descriptor of list(state.source_descriptors)) {
      if (!descriptor.artifact_id || descriptors.has(descriptor.artifact_id) || !isHash(descriptor.sha256) || descriptor.claim_id && descriptor.claim_id !== state.claim_id) throw new Error('The saved source roster has an invalid identity.');
      descriptors.set(descriptor.artifact_id,descriptor);
    }
    if (state.original_binding?.claim_id && state.original_binding.claim_id !== state.claim_id) throw new Error('The saved original binding belongs to another claim.');
    for (const source of list(state.original_binding?.source_map)) if (!descriptors.has(source.artifact_id) || source.sha256 !== descriptors.get(source.artifact_id).sha256) throw new Error('The saved original source mapping changed identity.');
    const sources = new Map();
    for (const source of list(state.acquired_sources)) {
      const descriptor = descriptors.get(source.artifact_id);
      if (!descriptor || sources.has(source.artifact_id) || source.descriptor_sha256 && descriptor.descriptor_sha256 && source.descriptor_sha256 !== descriptor.descriptor_sha256) throw new Error('The saved acquired source differs from its original descriptor.');
      await checkedSource(state,descriptor,source);
      sources.set(source.artifact_id,source);
    }
    for (const fact of list(state.facts)) for (const citation of citationRows(fact)) {
      const source = sources.get(citation.artifact_id), chars = source && Array.from(source.text);
      if (!source || citation.sha256 && citation.sha256 !== source.sha256 || citation.text_sha256 && citation.text_sha256 !== source.text_sha256 || !Number.isSafeInteger(citation.start_char) || !Number.isSafeInteger(citation.end_char) || citation.start_char < 0 || citation.end_char <= citation.start_char || citation.end_char > chars.length || chars.slice(citation.start_char,citation.end_char).join('') !== citation.quote) throw new Error('The saved cited passage changed source identity.');
    }
    if (state.graph) layoutGraph(state.graph);
    return snapshot;
  }
  async function checkedAtomicOperationHead(response, head, start, openingState) {
    const incoming = readSnapshot(response,head?.claimId,null,true), state = incoming.state, events = incoming.accepted.events;
    // The atomic saved endpoint runs the same complete server replay as a head
    // replay GET. Its state is pinned by the separate revision-zero response;
    // it has no replay provenance mirror and must not acquire a synthetic one.
    if (response.mode !== 'saved' || ['replay_only','through_seq','provenance','current_head'].some(field => Object.prototype.hasOwnProperty.call(response,field)) ||
        state.claim_id !== head.claimId || state.revision !== head.revision || state.state_sha256 !== head.state_sha256 ||
        response.current_event_sha256 !== head.event_sha256 || response.cursor_sha256 !== head.event_sha256 || state.last_event_sha256 !== head.event_sha256 ||
        !isHash(head.event_sha256) || !events.length || events.length !== head.revision ||
        events.some((event,index) => event.seq !== index+1 || event.sequence !== index+1 || event.revision !== index+1 || event.state_sha256 !== event.resulting_state_sha256 || event.contract !== 'casepath.autonomous-event/1.0.0' || event.claim_id !== head.claimId || !Object.prototype.hasOwnProperty.call(event,'previous_event_sha256')) ||
        !start || canonicalJSON(response.replay_start) !== canonicalJSON(start) ||
        openingState?.claim_id !== head.claimId || openingState?.revision !== 0 || !openingState.original_binding || canonicalJSON(state.original_binding) !== canonicalJSON(openingState.original_binding) ||
        list(openingState.source_descriptors).some(source => canonicalJSON(source) !== canonicalJSON(list(state.source_descriptors).find(row => row.artifact_id === source.artifact_id)))) throw new Error('The complete atomic head differs from its verified opening.');
    const material = {...state}; delete material.state_sha256;
    if (await digest(canonicalJSON(material)) !== state.state_sha256) throw new Error('The atomic head failed its pinned state hash.');
    await checkedSavedSnapshot({state,projection:incoming.projection,cursor:state.revision,history:events},head.claimId);
    if (!checkedReferenceReplayStart(start,incoming) || !referenceExecution(state) || state.outcome?.assessment_status !== 'complete' || !replayCanAdvance(state)) throw new Error('The atomic head has no complete current reference assessment.');
    return incoming;
  }
  const SAVED_SNAPSHOT_BYTES = 8 * 1024 * 1024;
  async function checkedSavedSnapshotAsset(bytes, descriptor, allowNative = false) {
    const raw = new Uint8Array(bytes);
    if (!descriptor || !Number.isSafeInteger(descriptor.bytes) || descriptor.bytes < 1 || descriptor.bytes > SAVED_SNAPSHOT_BYTES || raw.byteLength !== descriptor.bytes || !isHash(descriptor.sha256) ||
        typeof descriptor.claim_id !== 'string' || !descriptor.claim_id || !Number.isSafeInteger(descriptor.revision) || descriptor.revision < 1 || descriptor.revision > 2000 || !isHash(descriptor.state_sha256) || !isHash(descriptor.event_sha256) ||
        !(descriptor.history_kind === 'published_public_synthetic' && /^[a-f0-9]{40}$/.test(descriptor.deployment_commit) || allowNative && descriptor.history_kind === 'native_fixture' && descriptor.deployment_commit === null) ||
        await digest(raw) !== descriptor.sha256) throw new Error('The saved snapshot asset identity is invalid.');
    const response = JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(raw)), incoming = readSnapshot(response,descriptor.claim_id,null,true), state = incoming.state, events = incoming.accepted.events;
    if (response.mode !== 'saved' || ['replay_only','through_seq','provenance','current_head'].some(field => Object.prototype.hasOwnProperty.call(response,field)) ||
        state.revision !== descriptor.revision || state.state_sha256 !== descriptor.state_sha256 || response.current_event_sha256 !== descriptor.event_sha256 || response.cursor_sha256 !== descriptor.event_sha256 || state.last_event_sha256 !== descriptor.event_sha256 || events.length !== descriptor.revision || response.events.some((event,index) => event.sequence !== index+1)) throw new Error('The saved snapshot differs from its published head.');
    let previousEvent = null, previousState = null;
    for (let index=0;index<events.length;index++) {
      const event = events[index], command = {kind:event.kind,payload:event.payload,expected_revision:event.expected_revision,expected_state_sha256:event.expected_state_sha256};
      if (event.contract !== 'casepath.autonomous-event/1.0.0' || event.claim_id !== descriptor.claim_id || event.sequence !== index+1 || event.seq !== event.sequence || event.revision !== event.sequence ||
          event.timestamp !== event.created_at || typeof event.created_at !== 'string' || event.state_sha256 !== event.resulting_state_sha256 || !isHash(event.resulting_state_sha256) ||
          event.previous_event_sha256 !== previousEvent || event.expected_revision !== index || event.expected_state_sha256 !== previousState || !isHash(event.command_sha256) || await digest(canonicalJSON(command)) !== event.command_sha256) throw new Error('The saved snapshot command or event chain changed identity.');
      const material = {...event}; for (const field of ['seq','revision','timestamp','state_sha256','event_sha256','resulting_state_sha256']) delete material[field];
      if (!isHash(event.event_sha256) || await digest(canonicalJSON(material)) !== event.event_sha256) throw new Error('The saved snapshot event failed its native hash.');
      previousEvent=event.event_sha256; previousState=event.resulting_state_sha256;
    }
    const material = {...state}; delete material.state_sha256;
    if (await digest(canonicalJSON(material)) !== descriptor.state_sha256) throw new Error('The saved snapshot failed its published state hash.');
    return checkedSavedSnapshot({state,projection:incoming.projection,cursor:state.revision,history:events},descriptor.claim_id);
  }
  const RECORDED_PACKET_BYTES = 8 * 1024 * 1024, RECORDED_BODY_BYTES = 24 * 1024 * 1024, recordedPacketValues = new WeakSet();
  async function checkedRecordedPacket(bytes, descriptor, allowNative = false) {
    const raw = new Uint8Array(bytes);
    if (!descriptor || !Number.isSafeInteger(descriptor.bytes) || descriptor.bytes < 1 || descriptor.bytes > RECORDED_PACKET_BYTES || raw.byteLength !== descriptor.bytes || !isHash(descriptor.sha256) || await digest(raw) !== descriptor.sha256) throw new Error('The recorded packet failed its asset identity check.');
    const packet = JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(raw));
    if (packet.contract !== 'casepath.recorded-session-packet/1.0.0' || packet.history_kind !== descriptor.history_kind || packet.deployment_commit !== descriptor.deployment_commit ||
        !(packet.history_kind === 'published_public_synthetic' && /^[a-f0-9]{40}$/.test(packet.deployment_commit) || allowNative && packet.history_kind === 'native_fixture' && packet.deployment_commit === null) ||
        !Array.isArray(packet.claims) || !packet.claims.length || packet.claims.length > 9 || !Array.isArray(packet.fragments) || !packet.fragments.length || packet.fragments.length > 250000) throw new Error('The recorded packet contract or publication identity is unavailable.');
    let references = 0; const ids = new Set();
    for (let id=0;id<packet.fragments.length;id++) {
      const fragment = packet.fragments[id];
      if (typeof fragment !== 'string' && (!Array.isArray(fragment) || !fragment.length || (references+=fragment.length) > 2000000 || fragment.some(ref => !Number.isSafeInteger(ref) || ref < 0 || ref >= id))) throw new Error('The recorded packet fragment graph is invalid.');
    }
    for (const claim of packet.claims) {
      if (!REFERENCE_DEMO_CASES.some(row => row.claim_id === claim.claim_id) || ids.has(claim.claim_id) || !Number.isSafeInteger(claim.head?.revision) || claim.head.revision < 1 || !isHash(claim.head.state_sha256) || !isHash(claim.head.event_sha256)) throw new Error('The recorded packet claim identity is invalid.');
      ids.add(claim.claim_id);
      for (const kind of ['opening','head_snapshot','operations']) { const entry = claim[kind]; if (!entry || !Number.isSafeInteger(entry.bytes) || entry.bytes < 1 || entry.bytes > RECORDED_BODY_BYTES || !isHash(entry.sha256) || !Number.isSafeInteger(entry.root) || entry.root < 0 || entry.root >= packet.fragments.length) throw new Error('The recorded packet body identity is invalid.'); }
    }
    recordedPacketValues.add(packet); return freezeRelease(packet);
  }
  async function decodeRecordedSession(packet, claimId, signal = null) {
    if (!recordedPacketValues.has(packet)) throw new Error('The recorded packet asset was not verified.');
    const claim = packet.claims.find(row => row.claim_id === claimId);
    if (!claim) throw new Error('The selected case is absent from the recorded packet.');
    const cancelled = () => { if (signal?.aborted) throw new Error('Recorded packet selection cancelled.'); };
    const output = {head:{claimId,...claim.head},raw:{}}, cache = new Map(); let expanded = 0;
    for (const kind of ['opening','head_snapshot','operations']) {
      cancelled(); const entry = claim[kind], needed = new Set(), pending = [entry.root];
      while (pending.length) { const id = pending.pop(); if (needed.has(id) || cache.has(id)) continue; needed.add(id); const fragment = packet.fragments[id]; if (Array.isArray(fragment)) for (const ref of fragment) pending.push(ref); }
      let count = 0;
      for (const id of [...needed].sort((a,b) => a-b)) {
        cancelled(); const fragment = packet.fragments[id];
        const length = typeof fragment === 'string' ? fragment.length : fragment.reduce((sum,ref) => sum+cache.get(ref).length,0);
        if (length > entry.bytes || (expanded+=length) > 96 * 1024 * 1024) throw new Error('The selected recorded packet expansion exceeds its bound.');
        cache.set(id,typeof fragment === 'string' ? fragment : fragment.map(ref => cache.get(ref)).join(''));
        if (++count % 2048 === 0) await new Promise(resolve => root.setTimeout(resolve,0));
      }
      const bytes = new TextEncoder().encode(cache.get(entry.root));
      if (bytes.byteLength !== entry.bytes || await digest(bytes) !== entry.sha256) throw new Error('The recorded body failed its exact byte identity check.');
      cancelled(); output.raw[kind] = bytes; output[kind] = kind === 'operations' ? bytes : JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
      await new Promise(resolve => root.setTimeout(resolve,0));
    }
    return output;
  }
  async function checkedReadCache(serialized, apiIdentity, now = Date.now()) {
    if (typeof serialized !== 'string' || serialized.length * 2 > READ_CACHE_BYTES) throw new Error('The saved read cache exceeds its bound.');
    const envelope = JSON.parse(serialized), {sha256,...material} = envelope || {};
    const fresh = at => Number.isSafeInteger(at) && at <= now && now - at <= READ_CACHE_AGE;
    if (material.contract !== READ_CACHE_CONTRACT || material.api !== apiIdentity || !fresh(material.saved_at) || !Array.isArray(material.snapshots) || material.snapshots.length > 3 || !isHash(sha256) || await digest(canonicalJSON(material)) !== sha256) throw new Error('The saved read cache identity is invalid.');
    const ids = new Set();
    for (const snapshot of material.snapshots) {
      if (!fresh(snapshot.at) || ids.has(snapshot.state?.claim_id)) throw new Error('The saved read cache entry is stale or duplicated.');
      await checkedSavedSnapshot(snapshot,snapshot.state?.claim_id); ids.add(snapshot.state.claim_id);
    }
    if (material.knowledge !== null && material.knowledge !== undefined) {
      if (!fresh(material.knowledge.at)) throw new Error('The saved Knowledge copy is stale.');
      readKnowledge(material.knowledge.value);
    }
    return material;
  }

  function mount(container, options = {}) {
    if (!container?.addEventListener) throw new Error('An autonomous workspace container is required.');
    destroy(container);
    const doc = container.ownerDocument, fetcher = options.fetch || root.fetch?.bind(root), base = options.apiBase || BASE;
    const mainTag = container.tagName === 'MAIN' ? 'div' : 'main';
    if (!fetcher) throw new Error('The autonomous API is unavailable.');
    let publicReadOnly = root.CASEPATH_PUBLIC_READ_ONLY === true;
    let publicationAttention = null, inspectionHold = false, operationTrace = null, attentionMarker = null, attentionPosition = null, attentionAnimation = null, factToken = null, factTokenAnimation = null, factTokenOperation = null, stageMotionTimer = null, stageReadAnimations = [], stageScrollCancel = null, stageScrollTarget = null, stageChoreography = null, operationPeek = null;
    let disposed = false, epoch = 0, timer = null, selected = null, current = null, projection = {}, cursor = null, history = [], detail = 'step', view = 'work', disconnected = false, connectionFailed = false, busy = false, status = null, pendingIntake = null, pendingArrival = null, pendingControl = null, dialogReturn = null, recordReturn = null, recordSelection = null, recordExplained = null, chosenNode = null, sourceEpoch = 0, polling = null, claimRead = 0;
    let openingId = null, openingPreferences = {}, snapshotAvailable = null, presentationMode = 'saved', replayRecord = null, demoMode = 'reference', tour = null, demoSession = null, demoTimer = null, pausedPresentation = null, pendingStart = null, nativeSourceURL = null;
    let evidenceContext = {}, selectionMotion = null, tetherGeometry = null, graphViewportWidth = null, interactionMotion = null, freshClaim = false, statusAuthority = null, readGeneration = 0;
    // Knowledge opens as the procedure library; the learning replay is a secondary view.
    let knowledgeMode = 'library', learningState = null, learningTimer = null, noticeCategory = null, announcedNow = null, noticeRecord = null;
    let knowledgeWarmGeneration = -1, knowledgeFacet = 'process', knowledgePin = null, lastCaseContext = null, collectionCache = null, knowledgeCache = null, statusCache = null, knowledgeRead = 0, renderedKnowledge = null;
    const snapshots = new Map(), sourcePreviews = new Map(), nativeBytes = new Map(), replayPrefixes = new Map(), inflightReads = new Map(), readOwners = new Map();
    const savedHeads = new Map(), warmQueue = [], warmAttempts = new Set(), warmIntents = new Set(), warmWorkers = new Set();
    let savedKnowledge = null, sessionRestore = null, storageWrite = 0, warmActive = 0, warmTicket = 0, warmIdle = null;
    let storage = null, apiIdentity = null;
    try { if (root.location?.href) { apiIdentity = new URL(base,root.location.href).href; storage = root.sessionStorage; } } catch (_) { /* Session storage is optional. */ }
    const controllers = new Set();
    let knowledgeOpening = options.knowledgeOpening || null;
    function discardKnowledgeOpening() {
      if (!knowledgeOpening) return;
      knowledgeOpening.controller.abort(); root.clearTimeout(knowledgeOpening.timeout); knowledgeOpening = null;
    }
    if (knowledgeOpening) {
      try { if (new URL(knowledgeOpening.url,root.location?.href).href !== new URL(base+'/knowledge',root.location?.href).href) discardKnowledgeOpening(); }
      catch (_) { discardKnowledgeOpening(); }
    }
    let recordedPacket = null, packetVerification = null, packetLoadController = null, packetAcquisition = null;
    let savedSnapshotLoad = null, savedSnapshotController = null;
    const reduced = root.matchMedia?.('(prefers-reduced-motion: reduce)');
    let motion = null, keyboard = false, pageArrival = true, examples = null, routedFragment = null, intakeForm = null, claims = [], claimsLoaded = false, claimsRead = 0, claimRenderComplete = false, renderedClaimId = null;
    const claimViews = new Map(), arrivalForms = new Map(), arrivals = new Map(), controls = new Map(), starts = new Map();
    const collection = {search:'',filter:'all',domain:'all',scope:'originals',page:1,opener:null,intakeFromWork:false};
    const originalTitle = typeof doc?.title === 'string' && doc.title ? doc.title : 'CasePath';
    // Each route places its own scroll: the top, or the restored list place.
    // The browser's history restoration would override it after Back/Forward.
    const originalScrollRestoration = (() => { try { const value = root.history?.scrollRestoration; if (typeof value === 'string') root.history.scrollRestoration = 'manual'; return typeof value === 'string' ? value : null; } catch (_) { return null; } })();
    container.classList.add('au-workspace');
    container.removeAttribute('data-au-keyboard');
    container.innerHTML = `<div class="au-shell au-identity-shell"><a class="au-skip-link" href="#auMain" data-au-skip>Skip to main content</a><header class="au-identity-header"><a class="au-brand" href="#autonomous/cases">CasePath<span>Follow the documents</span></a>${publicReadOnly ? '' : '<button type="button" class="au-header-new" data-au-nav="intake" aria-label="New case">New<span class="au-header-new-noun"> case</span></button>'}<span class="au-access-label" data-au-public-access${publicReadOnly ? '' : ' hidden'}>View only</span><nav class="au-nav" aria-label="CasePath"><button type="button" data-au-nav="work" aria-current="page">Cases</button><button type="button" data-au-nav="demonstration">Demonstration</button><button type="button" data-au-nav="knowledge">Knowledge</button></nav><div class="au-case-return" data-au-case-return hidden></div></header><${mainTag} class="au-main" id="auMain"><div class="au-global-status"></div><p class="au-visually-hidden" role="status" aria-live="polite" aria-atomic="true" data-au-announcement></p><div class="au-body" data-au-view data-au-view-state="work"></div><div data-au-role-legend hidden>${roleExplanationMarkup()}</div></${mainTag}></div><dialog class="au-source-dialog" aria-labelledby="auSourceTitle"><header class="au-dialog-header"><div><p class="au-eyebrow">Original source</p><h2 id="auSourceTitle">Source</h2></div><button type="button" class="au-secondary" data-au-close>Close source</button></header><div data-au-source-content></div></dialog><dialog class="au-record-dialog" aria-labelledby="auRecordTitle"><header class="au-dialog-header"><h2 id="auRecordTitle">Details</h2><button type="button" class="au-secondary" data-au-close-record>Close</button></header><div data-au-record-content></div></dialog>`;
    const host = container.querySelector('[data-au-view]'), globalStatus = container.querySelector('.au-global-status'), dialog = container.querySelector('.au-source-dialog'), recordDialog = container.querySelector('.au-record-dialog');
    function announceRecorded(message) { const live=container.querySelector('[data-au-announcement]');if(live)live.textContent=message; }
    function notice(message, error = false, category = null) {
      noticeCategory=message?category:null;noticeRecord=message || null;
      const shown=message?plain(message,'The record could not open. Retry.'):'';
      globalStatus.textContent=shown;
      if(message && shown!==message)globalStatus.insertAdjacentHTML?.('beforeend',recordButton('Details','notice'));
      globalStatus.classList.toggle('au-error',error);if(shown)announceRecorded(shown);
    }
    function route(fragment, writeHistory = true) {
      if (writeHistory) pageArrival = false;
      if (writeHistory && root.location && root.location.hash !== fragment && root.history?.pushState) root.history.pushState(null,'',root.location.pathname + root.location.search + fragment);
      routedFragment = writeHistory ? fragment : root.location ? root.location.hash : fragment;
      if (dialog.open) { dialogReturn = null; sourceEpoch++; clearNativeSource(); dialog.close(); }
      if (recordDialog.open) { recordReturn = null; recordDialog.close(); }
    }
    function pendingRoute() { return Boolean(root.location && root.location.hash !== routedFragment); }
    function routeChanged(event) {
      if (event?.type === 'hashchange' || event?.type === 'popstate') pageArrival = false;
      if (disposed || busy || (!root.location && routedFragment !== null)) return;
      let fragment = root.location?.hash || '';
      // `legacy` stays an accepted alias; the address shows the provenance name.
      if (/[?&]collection=legacy(?=&|$)/.test(fragment) && root.history?.replaceState) { fragment = fragment.replace(/([?&]collection=)legacy(?=&|$)/,'$1selected'); root.history.replaceState(null,'',root.location.pathname + root.location.search + fragment); }
      if (knowledgeOpening && fragment !== knowledgeOpening.fragment) discardKnowledgeOpening();
      if (fragment === routedFragment) return;
      if (!fragment && readOnlyAccess()) { showDemonstration(false,null,operationRoutePreference(fragment,root.location?.search)); return; }
      if (fragment === '#autonomous/knowledge') showKnowledge(false);
      else if (fragment.startsWith('#autonomous/knowledge?')) { const params = new URLSearchParams(fragment.slice(fragment.indexOf('?')+1)), learning = params.get('view') === 'learning' || params.has('event'); showKnowledge(false,params.get('knowledge')?{knowledge_id:params.get('knowledge'),version:params.get('version') || null,knowledge_sha256:params.get('sha256'),definition_sha256:params.get('definition'),claim_id:params.get('claim')}:null,{view:learning ? 'learning' : 'library',event:params.get('event'),stage:Number(params.get('stage')??10),facet:params.get('facet'),complete:params.get('complete')==='1'}); }
      else if (fragment.startsWith('#autonomous/claim/')) {
        try { const [encoded,query = ''] = fragment.slice('#autonomous/claim/'.length).split('?'), params = new URLSearchParams(query), id = decodeURIComponent(encoded); id ? openClaim(id,false,{mode:params.get('mode') === 'replay' ? 'replay' : 'saved',through:Number(params.get('through') || 0),collection:params.get('collection'),detail:params.get('detail'),node:params.get('node'),document:params.get('document'),obligation:params.get('obligation'),fact:params.get('fact'),trace:params.get('trace') === '1',operations:operationRoutePreference(fragment,root.location?.search)}) : showWork(false); }
        catch (_) { showWork(false); }
      } else if (fragment.startsWith('#autonomous/demonstration')) { const params = new URLSearchParams(fragment.split('?')[1] || ''); showDemonstration(false,demoCollection(params.get('collection')),operationRoutePreference(fragment,root.location?.search)); }
      else if (fragment.startsWith('#autonomous/cases?') || fragment.startsWith('#autonomous/work?')) {
        const params = new URLSearchParams(fragment.split('?')[1]); collection.search = params.get('q') || ''; collection.filter = params.get('filter') ? caseFilter(params.get('filter')) : legacyStatusFilter(params.get('status')); collection.domain = params.get('domain') || 'all'; collection.scope = params.get('scope') === 'added' ? 'added' : 'originals'; collection.page = Number(params.get('page') || 1); showWork(false);
      } else if (['#autonomous/new','#autonomous/intake'].includes(fragment)) showIntake(false);
      else { collection.search = ''; collection.filter = 'all'; collection.domain = 'all'; collection.scope = 'originals'; collection.page = 1; showWork(false); }
    }
    // These bounded session maps contain verified GET representations only.
    // Fresh snapshot admission, rather than a cached capability projection,
    // controls every existing-claim mutation.
    function rememberRead(map, id, value, limit, byteLimit = 12 * 1024 * 1024) {
      const bytes = value instanceof ArrayBuffer ? value.byteLength : JSON.stringify(value).length * 2;
      if (bytes > byteLimit) return;
      map.delete(id); map.set(id,{value,bytes});
      let total = [...map.values()].reduce((sum,row) => sum + row.bytes,0);
      while (map.size > limit || total > byteLimit) { const oldest = map.keys().next().value; total -= map.get(oldest).bytes; map.delete(oldest); }
    }
    function cachedRead(map, id) {
      const row = map.get(id);
      if (!row) return null;
      if (map === snapshots) row.idle = false;
      map.delete(id); map.set(id,row); return row.value;
    }
    function rememberSnapshot(id, value, idle = false) {
      const existing = snapshots.get(id);
      if (existing) {
        if (existing.value.state.revision > value.state.revision) return;
        if (existing.value.state.revision === value.state.revision && existing.value.state.state_sha256 !== value.state.state_sha256) throw new Error('A saved revision changed identity.');
        if (idle && !existing.idle) return;
      }
      const bytes = JSON.stringify(value).length * 2;
      if (bytes > 12 * 1024 * 1024) return;
      snapshots.delete(id); snapshots.set(id,{value,bytes,idle});
      let total = [...snapshots.values()].reduce((sum,row) => sum + row.bytes,0);
      while (snapshots.size > 12 || total > 12 * 1024 * 1024) {
        const oldest = [...snapshots].find(([key,row]) => row.idle && key !== openingId)?.[0] || [...snapshots.keys()].find(key => key !== openingId) || snapshots.keys().next().value;
        total -= snapshots.get(oldest).bytes; snapshots.delete(oldest);
      }
    }
    async function restoreReadCache() {
      if (!storage || !apiIdentity) return;
      const generation = readGeneration;
      try {
        const serialized = storage.getItem(READ_CACHE_CONTRACT);
        if (!serialized) return;
        const saved = await checkedReadCache(serialized,apiIdentity);
        if (disposed || generation !== readGeneration) return;
        for (const row of saved.snapshots) {
          const {at,...value} = row;
          if (!snapshots.has(value.state.claim_id)) rememberSnapshot(value.state.claim_id,value);
          if (!savedHeads.has(value.state.claim_id)) savedHeads.set(value.state.claim_id,{at,value});
        }
        if (saved.knowledge && !knowledgeCache) { savedKnowledge = saved.knowledge; knowledgeCache = {value:saved.knowledge.value}; }
      } catch (_) { /* A damaged, expired or unavailable derivative never blocks GETs. */ }
    }
    async function persistReadCache() {
      if (!storage || !apiIdentity) return;
      const generation = readGeneration, write = ++storageWrite;
      // The derivative must not extend the task that renders a fresh GET.
      await new Promise(resolve => root.requestAnimationFrame ? root.requestAnimationFrame(() => root.setTimeout(resolve,0)) : root.setTimeout(resolve,0));
      if (disposed || generation !== readGeneration || write !== storageWrite) return;
      const now = Date.now();
      for (const [id,row] of savedHeads) if (now - row.at > READ_CACHE_AGE) savedHeads.delete(id);
      if (savedKnowledge && now - savedKnowledge.at > READ_CACHE_AGE) savedKnowledge = null;
      while (savedHeads.size > 3) savedHeads.delete(savedHeads.keys().next().value);
      const material = {contract:READ_CACHE_CONTRACT,api:apiIdentity,saved_at:now,snapshots:[...savedHeads.values()].map(row => ({at:row.at,...row.value})),knowledge:savedKnowledge};
      const encoded = () => JSON.stringify({...material,sha256:'0'.repeat(64)});
      while (encoded().length * 2 > READ_CACHE_BYTES && material.snapshots.length) material.snapshots.shift();
      if (encoded().length * 2 > READ_CACHE_BYTES) material.knowledge = null;
      try {
        const sha256 = await digest(canonicalJSON(material));
        if (disposed || generation !== readGeneration || write !== storageWrite) return;
        storage.setItem(READ_CACHE_CONTRACT,JSON.stringify({...material,sha256}));
      } catch (_) { /* Quota and crypto failures leave the fresh read path intact. */ }
    }
    async function saveForegroundHead(value) {
      if (!storage || !apiIdentity) return;
      const generation = readGeneration;
      try {
        await checkedSavedSnapshot(value,value.state.claim_id);
        if (disposed || generation !== readGeneration) return;
        const previous = savedHeads.get(value.state.claim_id);
        if (previous && previous.value.state.revision > value.state.revision) return;
        savedHeads.delete(value.state.claim_id); savedHeads.set(value.state.claim_id,{at:Date.now(),value});
        persistReadCache();
      } catch (_) { /* Only complete, checked foreground heads may be saved. */ }
    }
    function snapshotCache() {
      if (presentationMode === 'replay' || !current || cursor !== current.revision) return;
      const value = {state:current,projection,cursor,history:[...history]};
      rememberSnapshot(current.claim_id,value);
      if (freshClaim) saveForegroundHead(value);
    }
    function cancelWarmReads() {
      warmTicket++; warmQueue.length = 0;
      if (warmIdle !== null) root.cancelIdleCallback?.(warmIdle);
      warmIdle = null;
    }
    function cancelIdleReadOwners() {
      warmAttempts.clear(); warmWorkers.clear(); warmActive = 0;
      for (const [identity,owner] of readOwners) if (!owner.foreground) {
        owner.controller.abort(); readOwners.delete(identity); inflightReads.delete(identity);
      }
    }
    function invalidateReads(id) {
      cancelNextOperationOpening(demoSession || pausedPresentation);
      cancelWarmReads(); warmAttempts.clear(); warmIntents.clear(); storageWrite++; savedHeads.clear(); savedKnowledge = null;
      try { storage?.removeItem(READ_CACHE_CONTRACT); } catch (_) { /* Storage is optional. */ }
      readGeneration++; claimRead++; claimsRead++; knowledgeRead++; collectionCache = null; knowledgeCache = null; statusCache = null;
      if (id) snapshots.delete(id); else snapshots.clear();
      sourcePreviews.clear(); nativeBytes.clear(); replayPrefixes.clear();
      freshClaim = false; statusAuthority = null; synchronizeAuthority('refreshing');
    }
    function markStart(control, blocked) {
      control.disabled = false;
      if (blocked) control.setAttribute?.('aria-disabled','true'); else control.removeAttribute?.('aria-disabled');
    }
    function canStartHere() { return !publicReadOnly && statusAuthority?.epoch === epoch && statusAuthority?.generation === readGeneration && claimAvailability(status,current,projection).ready; }
    function synchronizeAuthority(readState = freshClaim ? 'verified' : 'refreshing') {
      if (view !== 'claim') return;
      host.setAttribute?.('data-au-read-state',presentationMode === 'replay' ? 'verified' : readState);
      const label = host.querySelector('[data-au-read-state-label]');
      if (label) label.textContent = presentationMode === 'replay' || readState === 'verified' ? '' : readState === 'failed' ? 'Saved copy · refresh failed' : 'Saved copy · refreshing';
      const refresh = host.querySelector('[data-au-refresh-claim]');
      if (refresh) { refresh.textContent = presentationMode === 'replay' || readState === 'verified' ? 'Refresh' : readState === 'failed' ? 'Retry refresh' : 'Refreshing'; refresh.setAttribute('aria-label',presentationMode === 'replay' || readState === 'verified' ? 'Refresh saved state' : readState === 'failed' ? 'Saved copy; retry refresh' : 'Showing a saved copy while refreshing'); }
      for (const control of host.querySelectorAll('[data-au-start],[data-au-pause],[data-au-resume]')) {
        const action = control.hasAttribute('data-au-start') ? 'start' : control.hasAttribute('data-au-pause') ? 'pause' : 'resume';
        const pending = action === 'start' ? pendingStart?.claimId === current?.claim_id : pendingControl?.claimId === current?.claim_id && pendingControl?.action === action;
        control.textContent = pending ? busy ? ({start:'Starting…',pause:'Pausing…',resume:'Resuming…'})[action] : `Retry ${action}` : action === 'start' ? 'Start checking' : `${words(action)} work`;
        const blocked = publicReadOnly || busy || !freshClaim || !writable(status) || presentationMode === 'replay' || control.hasAttribute('data-au-resume') && !intakeEligible(projection) || control.hasAttribute('data-au-start') && !canStartHere() && !pendingStart;
        if (action === 'start') markStart(control,blocked); else control.disabled = blocked;
      }
      const form = host.querySelector('[data-au-arrival]');
      if (form) {
        const readonly = publicReadOnly || busy || !freshClaim || !status || !writable(status) || presentationMode === 'replay';
        if (readonly) {
          for (const control of form.querySelectorAll('input,textarea,select,button[type="submit"]')) control.disabled = true;
        } else if (pendingArrival) lockForm(form,true,true);
        else lockForm(form,false);
      }

    }
    function interact(element, direction = 1) {
      interactionMotion?.cancel(); interactionMotion = null;
      if (element === host || host.contains?.(element) || !element?.animate || disposed || doc.hidden || dialog.open && !dialog.contains?.(element) || reduced?.matches || keyboard || element === doc.activeElement || element.contains?.(doc.activeElement)) return;
      const animation = element.animate([{opacity:.7},{opacity:1}],{duration:220,easing:'cubic-bezier(.2,.65,.3,1)',fill:'none'});
      interactionMotion = animation;
      animation.finished?.then(() => { if (interactionMotion === animation) interactionMotion = null; },() => { if (interactionMotion === animation) interactionMotion = null; });
    }
    function request(path, init = {}, quiet = false) {
      const readonly = !init.method || init.method === 'GET';
      if (!readonly && (publicReadOnly || !status || !writable(status))) { const error = new Error(PUBLIC_READ_ONLY_MESSAGE); error.status = 403; return Promise.reject(error); }
      const identity = `${readGeneration}:${path}`;
      // A read whose owner was just cancelled is settling; a new reader starts its own.
      if (readonly && inflightReads.has(identity) && !readOwners.get(identity)?.controller.signal.aborted) { if (!quiet && readOwners.has(identity)) readOwners.get(identity).foreground = true; return inflightReads.get(identity); }
      const opening = readonly && path === '/knowledge' && knowledgeOpening && root.location?.hash === knowledgeOpening.fragment ? knowledgeOpening : null;
      if (opening) knowledgeOpening = null;
      const controller = opening?.controller || new AbortController(); controllers.add(controller);
      const owner = {controller,foreground:!quiet}; if (readonly) readOwners.set(identity,owner);
      const timeout = opening?.timeout || root.setTimeout(() => controller.abort(new DOMException('No response within 15 seconds. Try again.','TimeoutError')),15000);
      const operation = (async () => {
        try {
          const response = await (opening ? opening.response : fetcher(base + path,{...init,signal:controller.signal,headers:{Accept:'application/json',...(init.body ? {'Content-Type':'application/json','X-CasePath-Agent-Work':'1'} : {}),...init.headers},cache:'no-store'}));
          const data = await response.json();
          if (!response.ok) { const error = new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || data.message || `Request refused (${response.status}).`); error.status = response.status; throw error; }
          return data;
        } finally { root.clearTimeout(timeout); controllers.delete(controller); if (readOwners.get(identity) === owner) readOwners.delete(identity); }
      })();
      if (readonly) { inflightReads.set(identity,operation); const clear = () => { if (inflightReads.get(identity) === operation) inflightReads.delete(identity); }; operation.then(clear,clear); }
      return operation;
    }
    function cancelPoll() { if (timer) root.clearTimeout(timer); timer = null; }
    function clearNativeSource() { if (nativeSourceURL) root.URL?.revokeObjectURL(nativeSourceURL); nativeSourceURL = null; }
    async function nativeSource(path, descriptor, token, sourceToken) {
      const identity = `${path}:${descriptor.sha256}:${descriptor.size_bytes ?? ''}`, generation = readGeneration;
      let bytes = cachedRead(nativeBytes,identity);
      if (!bytes) {
        const controller = new AbortController(); controllers.add(controller);
        const timeout = root.setTimeout(() => controller.abort(new DOMException('No response within 15 seconds. Try again.','TimeoutError')),15000);
        try {
          const response = await fetcher(base + path,{signal:controller.signal,headers:{Accept:descriptor.media_type || 'application/octet-stream'},cache:'no-store',credentials:'same-origin',redirect:'error'});
          if (!response.ok) throw new Error('Native preview unavailable. Download the original file.');
          bytes = await response.arrayBuffer();
          if (await digest(bytes) !== descriptor.sha256 || Number.isSafeInteger(descriptor.size_bytes) && descriptor.size_bytes !== bytes.byteLength) throw new Error('The original file failed its byte identity check.');
          if (!disposed && generation === readGeneration) rememberRead(nativeBytes,identity,bytes,8,16 * 1024 * 1024);
        } finally { root.clearTimeout(timeout); controllers.delete(controller); }
      }
      if (disposed || token !== epoch || sourceToken !== sourceEpoch || !dialog.open) return null;
      clearNativeSource(); nativeSourceURL = root.URL.createObjectURL(new root.Blob([bytes],{type:descriptor.media_type})); return nativeSourceURL;
    }
    function schedule() { cancelPoll(); if (!disposed && !doc.hidden && view === 'claim' && openingId && presentationMode !== 'replay') timer = root.setTimeout(current ? poll : () => loadOpenedClaim(openingId,epoch), current && !active(current.status) && !pendingStart && !pendingArrival && !pendingControl && !connectionFailed ? 20000 : 1600); }
    // The page's own first route keeps the document's natural focus order, so
    // the first Tab reaches the skip link. Later route changes focus the title.
    function focusTitle() { if (!doc.hidden && !pageArrival) host.querySelector('h1')?.focus({preventScroll:true}); }
    // Every route settles the same way: the tab title names the place, a
    // forward arrival starts at the top with focus on its heading, and a
    // return to Cases restores the reader's place and the row they opened.
    function routeTitle(label) { const title = label ? `${label} — CasePath` : originalTitle; if (!disposed && doc && doc.title !== title) doc.title = title; }
    function routeSettled(name, label, {top = true, focus = true} = {}) {
      if (disposed || view !== name) return;
      routeTitle(label);
      if (top) root.scrollTo?.({top:0,left:0,behavior:'instant'});
      if (focus) focusTitle();
    }
    function collectionTitle() { return `${collection.scope === 'added' ? 'Added cases' : 'Cases'}${collection.page > 1 ? ` · page ${collection.page}` : ''}`; }
    // A page or filter change lands on the list heading and says what it shows.
    function collectionSettled() {
      pageArrival = false;
      const page = collectionPage(claims,collectionView());
      routeSettled('work',collectionTitle());
      announceRecorded(`${page.total} ${page.total === 1 ? 'case' : 'cases'}, page ${page.page} of ${page.pages}`);
    }
    function restoreCollectionPlace() {
      host.scrollTop = collection.scrollTop; const main = container.querySelector('.au-main'); if (main) { main.scrollTop = collection.mainTop; main.scrollLeft = collection.mainLeft; }
      root.scrollTo?.({left:collection.scrollX,top:collection.scrollY,behavior:'instant'});
    }
    // Returning to Cases focuses the row that was opened, once it is shown.
    function returnToOpener() {
      const id = collection.opener;
      if (!id || doc.hidden || view !== 'work') return false;
      const row = [...host.querySelectorAll('[data-au-claims] [data-au-claim]')].find(element => element.dataset?.auClaim === id);
      if (!row) return false;
      collection.opener = null; row.focus?.({preventScroll:true});
      return true;
    }
    function caseTitle(id, state = null) {
      const label = caseLabel(id,state || catalogRow(claims,id)).primary || 'Untitled case', position = tour?.cases?.[tour.index]?.claim_id === id ? tour.index : -1;
      return position >= 0 ? `Demonstration ${position+1}/${tour.cases.length} · ${label}` : label;
    }
    function focusPanel(element) {
      const panel = element?.closest?.('[data-au-panel]');
      return panel?.dataset?.auPanel ? panel : null;
    }
    function focusEligible(element, token) {
      const panel = focusPanel(element);
      return (!panel || !panel.hidden) && (!token?.panel || panel?.dataset.auPanel === token.panel);
    }
    function focusToken(element) {
      if (!element || !host.contains(element)) return null;
      const panel = focusPanel(element)?.dataset.auPanel || null;
      for (const attr of ['data-au-operation-scrub','data-au-inspection-clear','data-au-demo-stop','data-au-demo-resume','data-au-operation-skip','data-au-inspect','data-au-start','data-au-node-previous','data-au-node-next','data-au-node','data-au-select','data-au-fact-select','data-au-document-select','data-au-source','data-au-knowledge','data-au-nav','data-au-pause','data-au-resume','data-au-graph-pan','data-au-expand-process','data-au-claim-title','data-au-inspector-heading','data-au-back-process','data-au-detail','data-au-add-files']) if (element.hasAttribute(attr)) return {attr,value:element.getAttribute(attr),citation:element.getAttribute('data-au-citation'),origin:element.getAttribute('data-au-source-origin'),obligation:element.getAttribute('data-au-obligation-select') || element.getAttribute('data-au-select-obligation'),version:element.getAttribute('data-au-version'),knowledgeSha:element.getAttribute('data-au-knowledge-sha'),definitionSha:element.getAttribute('data-au-definition-sha'),recordId:element.getAttribute('data-au-record-id'),panel};
      const details = element.matches('summary') ? element.parentElement : null;
      return details?.hasAttribute('data-au-disclosure') ? {disclosure:details.dataset.auDisclosure,panel} : null;
    }
    function focusTarget(token) {
      if (!token) return null;
      if (token.disclosure) return [...host.querySelectorAll('[data-au-disclosure]')].find(el => el.dataset.auDisclosure === token.disclosure && focusEligible(el.querySelector('summary'),token))?.querySelector('summary');
      return [...host.querySelectorAll(`[${token.attr}]`)].find(el => el.getAttribute(token.attr) === token.value && el.getAttribute('data-au-record-id') === (token.recordId ?? null) && el.getAttribute('data-au-citation') === token.citation && el.getAttribute('data-au-source-origin') === token.origin && (el.getAttribute('data-au-obligation-select') || el.getAttribute('data-au-select-obligation')) === token.obligation && el.getAttribute('data-au-version') === token.version && el.getAttribute('data-au-knowledge-sha') === token.knowledgeSha && el.getAttribute('data-au-definition-sha') === token.definitionSha && focusEligible(el,token));
    }
    function rememberLastCase() {
      if (!current || view !== 'claim') return;
      const saved = presentationMode === 'saved' ? snapshots.get(current.claim_id)?.value : null;
      const savedContext = saved?.state.claim_id === current.claim_id && saved.state.revision === current.revision && saved.state.state_sha256 === current.state_sha256 && saved.cursor === cursor;
      // A checked saved copy may retain navigation, never command authority.
      if (!(freshClaim || savedContext || presentationMode === 'replay' && replayRecord?.through_seq === current.revision && replayRecord?.state?.state_sha256 === current.state_sha256)) return;
      lastCaseContext = {claim_id:current.claim_id,label:featuredCase(current.claim_id)?.label || current.title || 'Selected case',mode:presentationMode,collection:openingPreferences.collection,operations:openingPreferences.operations,through:replayRecord?.through_seq,node:selected,...evidenceContext};
    }
    function renderCaseReturn() {
      const navigation = container.querySelector('[data-au-case-return]'); if (!navigation) return;
      navigation.hidden = !lastCaseContext || !['work','knowledge'].includes(view);
      if (!lastCaseContext) { navigation.innerHTML = ''; return; }
      // Phones show one line, "← case", inside the brand row; wider screens name the case and its views.
      navigation.innerHTML = `<button type="button" class="au-link au-case-return-compact" data-au-return-case="step" aria-label="Back to case: ${h(lastCaseContext.label)}"><span aria-hidden="true">←</span> <span class="au-case-return-name">${h(lastCaseContext.label)}</span></button><span class="au-case-return-label">${h(lastCaseContext.label)}</span><button type="button" class="au-link" data-au-return-case="step">Steps</button><button type="button" class="au-link" data-au-return-case="documents">Documents</button>`;
    }
    function nav(name) { renderCaseReturn(); container.querySelectorAll('.au-identity-header [data-au-nav]').forEach(item => { if (item.dataset.auNav === name) item.setAttribute('aria-current','page'); else item.removeAttribute('aria-current'); }); }
    function connectionGeometry(surface, pairs) {
      const svg = surface?.querySelector?.('.au-evidence-lines'), frame = surface?.getBoundingClientRect?.();
      if (!svg || !frame?.width || !frame.height || surface.closest?.('[hidden],details:not([open])')) return null;
      const ports = new Map([...surface.querySelectorAll('[data-au-wire]')].map(element => [element.dataset.auWire,element.getBoundingClientRect()]));
      const paths = pairs.map(([from,to,muted=false]) => {
        const a = ports.get(from), b = ports.get(to); if (!a || !b) return '';
        const horizontal = b.left >= a.right, x1 = horizontal ? a.right-frame.left : a.left+a.width/2-frame.left, y1 = horizontal ? a.top+a.height/2-frame.top : a.bottom-frame.top, x2 = horizontal ? b.left-frame.left : b.left+b.width/2-frame.left, y2 = horizontal ? b.top+b.height/2-frame.top : b.top-frame.top;
        const path = horizontal ? `M${x1} ${y1} C${(x1+x2)/2} ${y1},${(x1+x2)/2} ${y2},${x2} ${y2}` : `M${x1} ${y1} C${x1} ${(y1+y2)/2},${x2} ${(y1+y2)/2},${x2} ${y2}`;
        return `<path d="${path}" data-state="${muted ? 'false' : 'true'}"/><circle cx="${x2}" cy="${y2}" r="2"/>`;
      }).join('');
      return {svg,width:frame.width,height:frame.height,paths};
    }
    function orthogonalPath(points, radius = 6) {
      const rows = points.filter((point,index) => !index || point[0] !== points[index-1][0] || point[1] !== points[index-1][1]);
      let d = `M${rows[0][0]} ${rows[0][1]}`;
      for (let i = 1; i < rows.length; i++) {
        const [x,y] = rows[i], next = rows[i+1];
        if (!next) { d += ` L${x} ${y}`; break; }
        const [px,py] = rows[i-1], r = Math.min(radius,Math.hypot(x-px,y-py)/2,Math.hypot(next[0]-x,next[1]-y)/2);
        const ax = x-Math.sign(x-px)*r, ay = y-Math.sign(y-py)*r, bx = x+Math.sign(next[0]-x)*r, by = y+Math.sign(next[1]-y)*r;
        d += ` L${ax} ${ay} Q${x} ${y},${bx} ${by}`;
      }
      return d;
    }
    function drawEdges(navigation = false) {
      if (disposed) return;
      // Read every relevant rectangle before writing SVG geometry.
      const trace = operationPeek?.trace || operationTrace, prefix = operationPeek?.state || current, planned = Boolean(host.querySelector('[data-au-planned-process],[data-au-release-plan]')), displayed = planned ? trace.plannedProcess || trace.releasePlan : workingProcessState(trace) || prefix, graphSelected = planned ? null : operationNodeId(trace?.current,displayed?.graph,displayed) || operationPeek?.node || selected;
      const graph = host.querySelector('[data-au-graph]'), graphSvg = graph?.querySelector('svg'), frame = graph?.getBoundingClientRect?.();
      let graphPaths = null;
      if (graphSvg && frame?.width && frame.height && displayed?.graph) {
        const nodes = new Map([...graph.querySelectorAll('[data-au-node]')].map(element => {
          const junction = element.querySelector('[data-au-junction]') || element;
          return [element.dataset.auNode,{bounds:junction.getBoundingClientRect(),box:element.getBoundingClientRect?.() || junction.getBoundingClientRect(),rank:Number(element.closest('.au-graph-rank').dataset.rank)}];
        }));
        const ranks = new Map([...graph.querySelectorAll('.au-graph-rank')].map(element => [Number(element.dataset.rank),element.getBoundingClientRect()]));
        // "Open all steps" wraps ranks into rows; its edges keep to the gutters.
        const wrapped = graph.dataset.orientation === 'horizontal' && !host.querySelector('.au-operation-stage') && graph.closest?.('[data-au-graph-pan]')?.dataset.auGraphExpanded === 'true';
        const rowTops = wrapped ? [...new Set([...ranks.values()].filter(rect => rect.height).map(rect => Math.round(rect.top)))].sort((a,b) => a-b) : [];
        const rowBottom = top => Math.max(...[...ranks.values()].filter(rect => rect.height && Math.round(rect.top) === top).map(rect => rect.bottom));
        // A single column (a narrow phone) keeps every edge in the left gutter: out of the source's dot,
        // down, and into the target's dot, instead of looping out to the right and back.
        const columnLefts = wrapped ? new Set([...ranks.values()].filter(rect => rect.height).map(rect => Math.round(rect.left))) : null;
        const singleColumn = Boolean(columnLefts && columnLefts.size === 1 && ranks.size > 1);
        const gutter = singleColumn ? Math.min(...[...nodes.values()].map(node => node.bounds.left)) - frame.left : 0;
        graphPaths = list(displayed.graph.edges).map((edge,index) => {
          const from = nodes.get(edge.source_node_id), to = nodes.get(edge.target_node_id); if (!from || !to || !from.bounds.width || !from.bounds.height || !to.bounds.width || !to.bounds.height) return null;
          const vertical = graph.dataset.orientation === 'vertical';
          if (singleColumn) {
            const sx = from.bounds.left-frame.left, sy = from.bounds.top+from.bounds.height/2-frame.top, tx = to.bounds.left-frame.left-1, ty = to.bounds.top+to.bounds.height/2-frame.top;
            const lane = Math.max(2,gutter-7-Math.min(Math.max(0,to.rank-from.rank-1),2)*4);
            return {id:edge.edge_id,d:orthogonalPath([[sx,sy],[lane,sy],[lane,ty],[tx,ty]],5),state:edgeState(displayed,edge.edge_id),selected:edge.source_node_id === graphSelected || edge.target_node_id === graphSelected};
          }
          if (wrapped) {
            const source = ranks.get(from.rank), target = ranks.get(to.rank), offset = (index%3)*5, sourceTop = Math.round(source.top), sameRow = sourceTop === Math.round(target.top);
            const sx = from.box.right-frame.left, sy = from.bounds.top+from.bounds.height/2-frame.top, tx = to.bounds.left-frame.left-1, ty = to.bounds.top+to.bounds.height/2-frame.top;
            if (sameRow && to.rank-from.rank === 1) return {id:edge.edge_id,d:`M${sx} ${sy} C${(sx+tx)/2} ${sy},${(sx+tx)/2} ${ty},${tx} ${ty}`,state:edgeState(displayed,edge.edge_id),selected:edge.source_node_id === graphSelected || edge.target_node_id === graphSelected};
            const nextTop = rowTops.find(top => top > sourceTop), outX = source.right-frame.left+10+offset, inX = target.left-frame.left-10-offset;
            const lane = sameRow || nextTop === undefined ? source.top-frame.top-10-offset : (rowBottom(sourceTop)+nextTop)/2-frame.top-5+offset;
            return {id:edge.edge_id,d:orthogonalPath([[sx,sy],[outX,sy],[outX,lane],[inX,lane],[inX,ty],[tx,ty]]),state:edgeState(displayed,edge.edge_id),selected:edge.source_node_id === graphSelected || edge.target_node_id === graphSelected};
          }
          const x1=(vertical ? from.bounds.left+from.bounds.width/2 : Math.max(from.bounds.right,from.box.right))-frame.left,y1=(vertical ? from.bounds.bottom : from.bounds.top+from.bounds.height/2)-frame.top,x2=(vertical ? to.bounds.left+to.bounds.width/2 : to.bounds.left)-frame.left,y2=(vertical ? to.bounds.top : to.bounds.top+to.bounds.height/2)-frame.top;
          let path;
          if (vertical) {
            const sourceRank=ranks.get(from.rank), nextRank=ranks.get(from.rank+1), targetRank=ranks.get(to.rank), previousRank=ranks.get(to.rank-1);
            const departure=(sourceRank.bottom+nextRank.top)/2-frame.top, arrival=(previousRank.bottom+targetRank.top)/2-frame.top;
            // Vertical runs stay on the actual junction's clear margin. Edges
            // skipping a rank use the outside gutter and cross only row gaps.
            const lane=8+(index%3)*6;
            path=to.rank-from.rank>1 ? `M${x1} ${y1} L${x1} ${departure} L${lane} ${departure} L${lane} ${arrival} L${x2} ${arrival} L${x2} ${y2}` : `M${x1} ${y1} L${x1} ${departure} C${x1} ${departure},${x2} ${departure},${x2} ${departure} L${x2} ${y2}`;
          } else {
            const lane=frame.height-14-(index%3)*9;
            if (host.querySelector('.au-operation-stage')) { const sx=from.bounds.left+from.bounds.width/2-frame.left,tx=to.bounds.left+to.bounds.width/2-frame.left,sy=from.bounds.top-frame.top,ty=to.bounds.top-frame.top,clear=Math.min(sy,ty)-12-(index%3)*3; path=`M${sx} ${sy} L${sx} ${clear} C${sx} ${clear},${tx} ${clear},${tx} ${clear} L${tx} ${ty}`; } else path=to.rank-from.rank>1 ? `M${x1} ${y1} C${x1+18} ${y1},${x1+18} ${lane},${x1+34} ${lane} L${x2-34} ${lane} C${x2-18} ${lane},${x2-18} ${y2},${x2} ${y2}` : `M${x1} ${y1} C${(x1+x2)/2} ${y1},${(x1+x2)/2} ${y2},${x2} ${y2}`;
          }
          return {id:edge.edge_id,d:path,state:edgeState(displayed,edge.edge_id),selected:edge.source_node_id === graphSelected || edge.target_node_id === graphSelected};
        }).filter(Boolean);
      }
      const lens = host.querySelector('[data-au-evidence-path]'), relations = current ? evidenceRelationships(current,selected,evidenceContext) : null;
      const wires = [connectionGeometry(lens,[...citationRows(relations?.fact).slice(0,2).map((_,index) => [`source-${index}`,'fact'])]), ...[...host.querySelectorAll('[data-au-knowledge-path]')].map(surface => connectionGeometry(surface,[['origin','version'],['version','reuse']]))].filter(Boolean);
      const formingLayout = host.querySelector('.au-forming-layout'), formingSvg = formingLayout?.querySelector('.au-forming-connections'), formingFrame = formingLayout?.getBoundingClientRect?.(), operationRelation = current && operationRelationship(operationTrace,current), formingRelation = current && !workingProcessState(operationTrace) ? formingRelations(current,selected,evidenceContext) : null;
      const formingPaths = [];
      if (formingSvg && formingFrame?.width && formingFrame.height && formingRelation && !doc.hidden && !root.matchMedia?.('(max-width: 1000px)')?.matches) {
        const sourceElement = [...formingLayout.querySelectorAll('.au-forming-reading [data-au-source]')].find(element => element.dataset.auSource === formingRelation.source && element.dataset.auCitation === JSON.stringify(formingRelation.citation));
        const nodeElement = [...formingLayout.querySelectorAll('[data-au-node]')].find(element => element.dataset.auNode === formingRelation.node), port = nodeElement?.querySelector('[data-au-junction]');
        const requirementElement = [...formingLayout.querySelectorAll('.au-forming-documents [data-au-obligation]')].find(element => element.dataset.auObligation === formingRelation.obligation);
        const sourceBounds = sourceElement?.getBoundingClientRect?.(), nodeBounds = nodeElement?.getBoundingClientRect?.(), portBounds = port?.getBoundingClientRect?.(), requirementBounds = requirementElement?.getBoundingClientRect?.(), graphBounds = nodeElement?.closest?.('[data-au-graph-pan]')?.getBoundingClientRect?.(), rankBounds = nodeElement?.parentElement?.getBoundingClientRect?.();
        const visible = rect => rect?.width > 0 && rect.height > 0 && rect.left >= 0 && rect.top >= 0 && rect.right <= (root.innerWidth || doc.documentElement?.clientWidth || Infinity) && rect.bottom <= (root.innerHeight || doc.documentElement?.clientHeight || Infinity);
        const visibleNode = visible(nodeBounds) && graphBounds && nodeBounds.left >= graphBounds.left && nodeBounds.right <= graphBounds.right && nodeBounds.top >= graphBounds.top && nodeBounds.bottom <= graphBounds.bottom;
        const connect = (id,from,to) => { const x1=from.x-formingFrame.left,y1=from.y-formingFrame.top,x2=to.x-formingFrame.left,y2=to.y-formingFrame.top,lane=(x1+x2)/2; formingPaths.push({id,d:`M${x1} ${y1} C${lane} ${y1},${lane} ${y2},${x2} ${y2}`}); };
        if (visible(sourceBounds) && visibleNode && visible(portBounds)) connect('source-process',{x:sourceBounds.right,y:sourceBounds.top+sourceBounds.height/2},{x:portBounds.left,y:portBounds.top+portBounds.height/2});
        if (visibleNode && visible(portBounds) && visible(requirementBounds) && rankBounds && rankBounds.bottom+4 <= graphBounds.bottom && rankBounds.bottom+4 <= (root.innerHeight || doc.documentElement?.clientHeight || Infinity)) {
          const x1=portBounds.left+portBounds.width/2-formingFrame.left,y1=portBounds.bottom-formingFrame.top,x2=requirementBounds.left-formingFrame.left,y2=requirementBounds.top+requirementBounds.height/2-formingFrame.top,belowRank=rankBounds.bottom+4-formingFrame.top,gutter=(graphBounds.right+requirementBounds.left)/2-formingFrame.left;
          formingPaths.push({id:'process-document',d:`M${x1} ${y1} L${x1} ${belowRank} L${gutter} ${belowRank} L${gutter} ${y2} L${x2} ${y2}`});
        }
      }
      if (formingSvg && formingFrame?.width && operationRelation && !doc.hidden && !root.matchMedia?.('(max-width: 1000px)')?.matches) {
        const mark = formingLayout.querySelector('[data-au-operation-span]'), pane = mark?.closest('.au-operation-passage'), port = [...formingLayout.querySelectorAll('[data-au-junction]')].find(element => element.dataset.auJunction === operationRelation.node), viewport = port?.closest('[data-au-graph-pan]');
        const from = mark?.getBoundingClientRect(), clip = pane?.getBoundingClientRect(), to = port?.getBoundingClientRect(), graphClip = viewport?.getBoundingClientRect();
        if (mark?.dataset.auOperationSpan === operationRelation.operation_id && pane?.dataset.auOperationSource === operationRelation.source && from?.width && clip?.width && to?.width && graphClip && to.top >= graphClip.top && to.bottom <= graphClip.bottom) {
          const x1=clip.right-formingFrame.left,y1=Math.max(clip.top+8,Math.min(from.top+from.height/2,clip.bottom-8))-formingFrame.top,x2=to.left-formingFrame.left,y2=to.top+to.height/2-formingFrame.top,lane=(x1+x2)/2;
          formingPaths.push({id:'operation-source-process',d:`M${x1} ${y1} C${lane} ${y1},${lane} ${y2},${x2} ${y2}`});
        }
      }
      const stage=host.querySelector('.au-evidence-stage'), tether=host.querySelector('[data-au-tether]'), path=tether?.querySelector('path'), junction=[...host.querySelectorAll('[data-au-junction]')].find(element => element.dataset.auJunction === selected), expanded=host.querySelector('[data-au-expanded-junction]'), viewport=host.querySelector('.au-graph-viewport');
      const a=junction?.getBoundingClientRect?.(), b=expanded?.getBoundingClientRect?.(), area=viewport?.getBoundingClientRect?.(), bounds=stage?.getBoundingClientRect?.();
      let nextTether=null;
      if (detail === 'step' && current && path && bounds?.width && bounds.height && a && b && area && a.left >= area.left && a.right <= area.right && !expanded.closest?.('[hidden]')) {
        const x=a.left+a.width/2-bounds.left,y=a.bottom-bounds.top,mid=area.bottom-bounds.top+18;
        const narrow = root.matchMedia?.('(max-width: 1000px)')?.matches || bounds.width < 650;
        const tx=narrow ? b.left-bounds.left : b.left+b.width/2-bounds.left,ty=narrow ? b.top+b.height/2-bounds.top : b.top-bounds.top;
        let geometry;
        if (narrow) {
          const lane=2,bend=mid+20,end=Math.max(bend,ty-18);
          geometry=`M${x} ${y} C${x} ${mid},${lane} ${mid},${lane} ${bend} L${lane} ${end} C${lane} ${ty},${tx} ${ty},${tx} ${ty}`;
        } else {
          // Geometry settles immediately; selection uses the shared short fade.
          const mx=(x+tx)/2,my=(y+6*mid+ty)/8;
          geometry=`M${x} ${y} C${x} ${(y+mid)/2},${(3*x+tx)/4} ${(y+3*mid)/4},${mx} ${my} L${mx} ${my} C${(x+3*tx)/4} ${(3*mid+ty)/4},${tx} ${(mid+ty)/2},${tx} ${ty}`;
        }
        nextTether={claim:current.claim_id,node:selected,width:bounds.width,height:bounds.height,d:geometry};
      }
      if (!navigation && selectionMotion && tetherGeometry?.d !== nextTether?.d) selectionMotion.cancel();
      if (graphPaths !== null) {
        graphSvg.setAttribute('viewBox',`0 0 ${frame.width} ${frame.height}`);
        const paths = new Map([...graphSvg.querySelectorAll('[data-au-edge]')].map(edge => [edge.dataset.auEdge,edge]));
        for (const geometry of graphPaths) { const edge = paths.get(geometry.id); if (edge) { edge.setAttribute('d',geometry.d); edge.setAttribute('data-state',geometry.state); edge.setAttribute('data-selected',String(geometry.selected)); } }
      }
      if (formingSvg) {
        if (formingFrame?.width && formingFrame.height) formingSvg.setAttribute('viewBox',`0 0 ${formingFrame.width} ${formingFrame.height}`);
        for (const element of formingSvg.querySelectorAll('[data-au-forming-wire]')) { const geometry = formingPaths.find(row => row.id === element.dataset.auFormingWire); if (geometry) element.setAttribute('d',geometry.d); else element.removeAttribute('d'); }
      }
      for (const wire of wires) { wire.svg.setAttribute('viewBox',`0 0 ${wire.width} ${wire.height}`); wire.svg.innerHTML=wire.paths; }
      if (path) {
        if (nextTether) {
          tether.setAttribute('viewBox',`0 0 ${nextTether.width} ${nextTether.height}`); path.setAttribute('d',nextTether.d); path.setAttribute('data-au-selected-junction',selected);
          if (navigation && tetherGeometry?.claim === nextTether.claim && tetherGeometry.node !== nextTether.node && tetherGeometry.width === nextTether.width && !doc.hidden && !dialog.open && !reduced?.matches && !keyboard && path.animate) {
            selectionMotion?.cancel(); selectionMotion=path.animate([{opacity:.25,transform:'translateY(-3px)'},{opacity:1,transform:'translateY(0)'}],{duration:220,easing:'cubic-bezier(.2,.65,.3,1)',fill:'none'});
          }
        } else path.removeAttribute('d');
      }
      tetherGeometry=nextTether; graphViewportWidth=area?.width ?? null;
    }
    function preserveClaimView() {
      if (view !== 'claim' || !current) return;
      const viewport = host.querySelector('.au-graph-viewport');
      claimViews.set(current.claim_id,{selected,detail,evidenceContext:{...evidenceContext},graphExpanded:viewport?.dataset?.auGraphExpanded === 'true',scrollLeft:viewport?.scrollLeft || 0,scrollTop:viewport?.scrollTop || 0,open:new Set([...host.querySelectorAll('details[open][data-au-disclosure]')].map(el => el.dataset.auDisclosure))});
      const arrival = host.querySelector('[data-au-arrival]');
      if (arrival) { arrivalForms.set(current.claim_id,arrival); arrival.remove?.(); }
      if (pendingArrival) arrivals.set(current.claim_id,pendingArrival); else arrivals.delete(current.claim_id);
      if (pendingControl) controls.set(current.claim_id,pendingControl); else controls.delete(current.claim_id);
    }
    function leaveView(keepAcquiredPacket = false, keepSavedSnapshot = false) {
      if(view==='knowledge')pauseLearning(false);
      if (!recordedPacket && !(keepAcquiredPacket && (packetVerification || packetAcquisition))) packetLoadController?.abort();
      if (!keepSavedSnapshot) savedSnapshotController?.abort();
      cancelWarmReads();
      motion?.cancel(); selectionMotion?.cancel(); interactionMotion?.cancel(); tetherGeometry = null;
      if (view === 'intake') { intakeForm = host.querySelector('[data-au-intake]') || intakeForm; intakeForm?.remove?.(); }
      if (view === 'work') { const main = container.querySelector('.au-main'); collection.scrollTop = host.scrollTop || 0; collection.mainTop = main?.scrollTop || 0; collection.mainLeft = main?.scrollLeft || 0; collection.scrollX = root.scrollX || 0; collection.scrollY = root.scrollY || 0; }
      preserveClaimView();
    }
    // The opened row stays the return target only while the reader goes
    // straight from Cases to that case and back; any other place clears it.
    function setView(name) { if (name !== view) announceRecorded(''); if (name !== 'claim' && name !== 'work') collection.opener = null; const legend=container.querySelector('[data-au-role-legend]'); if(legend)legend.hidden=true; if (name !== 'claim') { tour = null; for (const attribute of ['data-au-current-operation','data-au-operation-run-mode','data-au-operation-presentation','data-au-operation-result-available','data-au-operation-result-verified']) host.removeAttribute?.(attribute); } view = name; renderedClaimId = null; freshClaim = false; statusAuthority = null; host.setAttribute?.('data-au-view-state',name); host.removeAttribute?.('data-au-read-state'); measureChrome(); observeChrome(); }
    function revealStepAnswer(node) {
      const answer = host.querySelector?.('[data-au-stage-step-detail]'), bounds = answer?.getBoundingClientRect?.(), height = root.innerHeight;
      if (!bounds || !Number.isFinite(height)) return;
      // The sticky header's scroll padding is not available to the answer's top edge.
      const margin = 16, covered = Number.parseFloat(root.getComputedStyle?.(doc.documentElement)?.scrollPaddingTop) || 0;
      let delta = 0;
      if (bounds.top < covered || bounds.bottom > height) {
        const end = bounds.top > 0 && bounds.height <= height - covered - 2*margin;
        delta = end ? bounds.bottom - height + margin : bounds.top - covered - margin;
        answer.scrollIntoView?.({block:end ? 'end' : 'start',behavior:reduced?.matches ? 'instant' : 'smooth'});
      }
      // Focus stays on the chosen step while it remains in view; otherwise it
      // moves with the view to the answer's heading.
      const place = node?.getBoundingClientRect?.();
      if (!place || place.top - delta < covered || place.bottom - delta > height) answer.querySelector('[data-au-step-detail-heading]')?.focus({preventScroll:true});
    }
    function revealGraphNode(node, center = false) {
      const viewport = host.querySelector('.au-graph-viewport');
      const area = viewport?.getBoundingClientRect?.(), bounds = node?.getBoundingClientRect?.();
      if (!area || !bounds) return;
      if (center || bounds.left < area.left+8 || bounds.right > area.right-8) viewport.scrollLeft += bounds.left-area.left-(area.width-bounds.width)/2;
      if (center || bounds.top < area.top+8 || bounds.bottom > area.bottom-8) viewport.scrollTop += bounds.top-area.top-Math.max(0,(area.height-bounds.height)/2);
    }
    function sourceControls(surface) {
      const controls = new Map();
      for (const control of surface?.querySelectorAll?.('.au-evidence-source[data-au-source-identity]') || []) {
        const identity = control.dataset.auSourceIdentity;
        if (identity && !controls.has(identity)) controls.set(identity,control);
      }
      return controls;
    }
    function reuseSourceControls(surface, controls) {
      for (const replacement of surface?.querySelectorAll?.('.au-evidence-source[data-au-source-identity]') || []) {
        const original = controls.get(replacement.dataset.auSourceIdentity);
        if (!original || original === replacement || !original.attributes || !replacement.attributes || typeof original.replaceChildren !== 'function') continue;
        controls.delete(replacement.dataset.auSourceIdentity);
        for (const attribute of [...original.attributes]) if (!replacement.hasAttribute(attribute.name)) original.removeAttribute(attribute.name);
        for (const attribute of [...replacement.attributes]) if (original.getAttribute(attribute.name) !== attribute.value) original.setAttribute(attribute.name,attribute.value);
        if (original.innerHTML !== replacement.innerHTML) original.replaceChildren(...replacement.childNodes);
        replacement.replaceWith(original);
      }
    }
    function formingObjects(surface) {
      const objects = new Map();
      for (const [selector,keyFor] of [['[data-au-node]',element => `node:${element.dataset.auNode}`],['[data-au-edge]',element => `edge:${element.dataset.auEdge}`],['.au-document-choice',element => `document-button:${element.closest('.au-obligation')?.dataset.auObligation}`],['.au-obligation',element => `obligation:${element.dataset.auObligation}`],['[data-au-graph]',() => 'graph'],['[data-au-graph-pan]',() => 'graph-pan'],['[data-au-demo-stop],[data-au-demo-resume],[data-au-demo-play]',() => 'transport-play'],['[data-au-operation-scrub]',() => 'transport-scrub'],['[data-au-operation-skip],[data-au-inspection-clear]',() => 'transport-skip'],['[data-au-detail=activity]',() => 'title-history'],['[data-au-inspect=demo]',() => 'title-cases'],['.au-stage-inspect',element => `operation-inspect:${element.dataset.auRecordId}`]]) for (const element of surface.querySelectorAll(selector)) objects.set(keyFor(element),element);
      return objects;
    }
    function reuseFormingObjects(surface, objects) {
      const replacements = formingObjects(surface);
      for (const [identity,replacement] of replacements) {
        const original = objects.get(identity);
        if (!original || original === replacement || !original.attributes || typeof original.replaceChildren !== 'function') continue;
        for (const attribute of [...original.attributes]) if (!replacement.hasAttribute(attribute.name)) original.removeAttribute(attribute.name);
        for (const attribute of [...replacement.attributes]) if (original.getAttribute(attribute.name) !== attribute.value) original.setAttribute(attribute.name,attribute.value);
        if (replacement.hasAttribute('data-au-operation-scrub')) original.value = replacement.value;
        if (original.innerHTML !== replacement.innerHTML) original.replaceChildren(...replacement.childNodes);
        replacement.replaceWith(original);
      }
    }
    // The case Knowledge tab names its procedure and similar cases from the
    // catalog and Knowledge index; it repaints once either read arrives.
    function refreshCaseKnowledge() {
      if (view === 'claim' && detail === 'knowledge' && current && !demoSession && !operationPeek && host.querySelector('[data-au-case-knowledge]')) renderClaim();
    }
    let deskSelection = null, deskDraft = null;
    const deskRecords = new Map(), deskRecordReads = new Map();
    async function ensureDeskRecord(state, token) {
      if (!state.outcome || !REFERENCE_DEMO_CASES.some(row=>row.claim_id===state.claim_id) || deskRecords.has(state.state_sha256) || deskRecordReads.has(state.state_sha256)) return;
      const id=state.claim_id, identity=state.state_sha256, controller=new AbortController();controllers.add(controller);
      const valid=()=>!disposed && token===epoch && !pendingRoute() && current?.state_sha256===identity && presentationMode==='saved';
      const promise=(async()=>{
        const opening=readReplay(await request(`/claims/${key(id)}/replay?through_seq=0`),id,0);
        if (!valid()) return;
        const head={claimId:id,revision:state.revision,state_sha256:identity,event_sha256:state.last_event_sha256};
        checkedReplayHead(opening,{replayHead:head});
        const verification={replayHead:head,replayStart:opening.replay.replay_start,operationOpeningAnchor:{state:opening.state}};
        if (!await verifyReferenceHead(verification) || !valid()) return;
        let response=await fetcher(base+`/claims/${key(id)}/operations?mode=live`,{method:'GET',headers:{Accept:'application/x-ndjson'},signal:controller.signal});
        if (!response.ok) response=await fetcher(base+`/claims/${key(id)}/operations?mode=recorded`,{method:'GET',headers:{Accept:'application/x-ndjson'},signal:controller.signal});
        if (!response.ok) throw new Error('The recorded operation trace is unavailable.');
        const trace={rows:[],sources:new Map(),bytes:0,pinnedJournal:verification.verifiedJournal,journal:[],headState:state,plannedProcess:verification.plannedProcess,frameHashes:[],state:opening.state};let prefix=opening.state;
        for await (const frame of operationFrames(response,controller.signal)) {
          if (!valid()) { controller.abort();return; }
          if(frame.contract!==OPERATIONS_CONTRACT || trace.verifiedResult)throw new Error('The source history could not be verified.');
          if (frame.type!=='result') trace.frameHashes.push(await digest(canonicalJSON(frame)));
          if (frame.type==='binding') {if(trace.binding)throw new Error('Repeated source binding.');trace.binding=checkedOperationBinding(frame,{...head,...verification.operationBinding},verification.verifiedReplayStart);}
          else if (frame.type==='operation') await checkedOperation(frame,trace,prefix);
          else if (frame.type==='checkpoint') prefix=(await checkedOperationCheckpoint(frame,trace)).state;
          else if (frame.type==='result') {
            if (!trace.binding || prefix.state_sha256!==identity || frame.current_event_sha256!==state.last_event_sha256 || frame.state_sha256!==identity || frame.operation_count!==trace.rows.length || frame.operation_chain_sha256!==trace.rows.at(-1)?.operation_sha256 || frame.exact_output_verified!==true || frame.trace_sha256!==await digest(canonicalJSON(trace.frameHashes))) throw new Error('The recorded desk differs from its saved result.');
            trace.finished=true;trace.verifiedResult=true;trace.state=state;trace.current=null;
          } else throw new Error('The source history contains an unsupported frame.');
        }
        if (!trace.verifiedResult) throw new Error('The recorded desk has no verified final result.');
        if (!valid()) return;
        deskRecords.set(identity,trace);while(deskRecords.size>9)deskRecords.delete(deskRecords.keys().next().value);
        renderClaim();
      })().catch(error=>{if(valid()){const status=host.querySelector('[data-au-desk-trace-status]');if(status){status.hidden=false;status.innerHTML='Counts could not load. '+button('Retry','data-au-desk-retry');}}}).finally(()=>{controllers.delete(controller);deskRecordReads.delete(identity);});
      deskRecordReads.set(identity,promise);
    }
    function renderClaim(changes = null, navigation = false) {
      const displayedState = operationPeek?.state || current, displayedProjection = operationPeek?.projection || projection, displayedTrace = operationPeek?.trace || operationTrace || deskRecords.get(current?.state_sha256);
      if (!current || view !== 'claim') return;
      routeTitle(caseTitle(current.claim_id,current));
      if (inspectionHold && pausedPresentation && host.querySelector('[data-au-release-opening]')) return;
      if (doc.hidden) { claimRenderComplete = false; return; }
      evidenceContext = evidenceSelection(current,selected,evidenceContext);
      // A replay route of a revision-zero head has no history to read or play.
      if (operationTrace) operationTrace.unrun = presentationMode === 'replay' && replayRecord?.current_revision === 0;
      syncReplayGuide();
      if (operationTrace) { operationTrace.state = current; host.setAttribute?.('data-au-current-operation',displayedTrace.current?.id || ''); host.setAttribute?.('data-au-operation-run-mode',operationPeek ? 'operation_history' : operationTrace.savedFallback ? 'saved_result' : operationTrace.recorded ? 'recorded_operations' : operationTrace.binding?.mode || 'opening'); host.setAttribute?.('data-au-operation-presentation',operationPeek ? 'paused' : operationTrace.finished ? 'completed' : pausedPresentation ? 'paused' : 'playing'); host.setAttribute?.('data-au-operation-result-available',String(operationTrace.finished || operationTrace.buffer?.result?.exact_output_verified === true && operationTrace.buffer.result.state_sha256 === operationTrace.binding?.current_state_sha256 && operationTrace.buffer.result.current_event_sha256 === operationTrace.binding?.current_event_sha256)); host.setAttribute?.('data-au-operation-result-verified',String(!operationPeek && operationTrace.verifiedResult === true)); } else { for (const attribute of ['data-au-current-operation','data-au-operation-run-mode','data-au-operation-presentation','data-au-operation-result-available','data-au-operation-result-verified']) host.removeAttribute?.(attribute); }
      claimRenderComplete = false;
      motion?.cancel(); selectionMotion?.cancel(); interactionMotion?.cancel(); interactionMotion = null;
      const priorSourcePane = host.querySelector('.au-operation-passage');
      const focused = doc.activeElement, focusKey = focusToken(focused), sources = sourceControls(host), objects = renderedClaimId === current.claim_id ? formingObjects(host) : new Map();
      const previous = claimViews.get(current.claim_id);
      const sameClaim = renderedClaimId === current.claim_id;
      const open = new Set(sameClaim ? [...host.querySelectorAll('details[open][data-au-disclosure]')].map(el => el.dataset.auDisclosure) : previous?.open || []);
      const priorViewport = sameClaim ? host.querySelector('.au-graph-viewport') : null;
      const graphExpanded = priorViewport ? priorViewport.dataset?.auGraphExpanded === 'true' : Boolean(previous?.graphExpanded);
      const scrollLeft = priorViewport?.scrollLeft ?? previous?.scrollLeft ?? 0, scrollTop = priorViewport?.scrollTop ?? previous?.scrollTop ?? 0;
      const arrival = sameClaim && host.querySelector('[data-au-arrival]') || arrivalForms.get(current.claim_id), focusInArrival = arrival?.contains?.(focused);
      // Moving the original node keeps native FileList, entered text and retry state.
      arrival?.remove?.();
      const reuseOperation = displayedTrace?.finished && displayedTrace.verifiedResult ? list(displayedTrace.rows).findLast(row => row.kind === 'knowledge.reuse') : displayedTrace?.current;
      const cueReuse = recordedReuseMoment(displayedState,reuseOperation && displayedTrace ? {...displayedTrace,current:reuseOperation,finished:false} : displayedTrace,knowledgeCache?.value || {});
      if (cueReuse && !operationPeek) displayedTrace.cueReuse = {operation:reuseOperation.id,pin:cueReuse.pin};
      host.innerHTML = workMarkup(displayedState,displayedProjection,operationPeek?.node || selected,operationPeek?.events || history,detail,evidenceContext,{desk:(root.innerWidth || 0)>700,deskSelection,mode:presentationMode,readOnly:publicReadOnly,chosenNode:operationPeek ? null : chosenNode,origin:claims.find(row => row.claim_id === displayedState.claim_id)?.origin,replay:replayRecord,knowledge:knowledgeCache?.value,attention:publicationAttention || {},inspectionHold,pendingStart:Boolean(pendingStart),operations:displayedTrace,transportOperations:operationTrace,inspectionIndex:operationPeek?.index,operationOpening:(demoSession || pausedPresentation)?.mode === 'operations',playing:Boolean(demoSession),paused:Boolean(pausedPresentation),position:demoSession?.index,storyPhase:operationPeek ? '' : (demoSession || pausedPresentation)?.storyPhase,tour:activeTour(),claims,writable:writable(status),status,availability:pendingStart ? {ready:true,reason:'The start response is unconfirmed. Retry uses the same request.'} : claimAvailability(status,current,projection)});
      const handoff = host.querySelector('[data-au-story-handoff]'), answer = host.querySelector('[data-au-stage-outcome]');
      if (handoff && answer) answer.append?.(handoff);
      const now = host.querySelector('[data-au-now-id]'), nowId = now?.dataset.auNowId;
      if (nowId && announcedNow !== `${displayedState.claim_id}:${nowId}` && !operationPeek) {
        announcedNow = `${displayedState.claim_id}:${nowId}`;
        const role=now.querySelector('[data-au-role]')?.textContent?.trim(), copy=now.querySelector('[data-au-now-copy]')?.textContent?.replace(/\s*·\s*/g,'. '), result=now.querySelector('[data-au-now-result]')?.textContent;
        announceRecorded([`${role || 'CasePath'} ${copy || ''}`,result].filter(Boolean).map(part=>/[.!?]$/.test(part.trim())?part.trim():`${part.trim()}.`).join(' '));
      }
      reuseSourceControls(host,sources);
      retainOperationSource(priorSourcePane);
      reuseFormingObjects(host,objects);
      if (arrival) host.querySelector('[data-au-arrival]')?.replaceWith(arrival);
      const presentArrival = host.querySelector('[data-au-arrival]');
      if (presentArrival) arrivalForms.set(current.claim_id,presentArrival);
      if (pendingArrival && presentArrival) { lockForm(presentArrival,true,true); presentArrival.querySelector('.au-form-status').textContent ||= 'The prior response was not confirmed. Retry sends the same saved supporting-file request.'; }
      if (focusInArrival) focused?.focus?.({preventScroll:true});
      const viewport = host.querySelector('.au-graph-viewport'); if (viewport) { setGraphExpanded(graphExpanded); viewport.scrollLeft = scrollLeft; viewport.scrollTop = scrollTop; }
      for (const disclosure of host.querySelectorAll('[data-au-disclosure]')) disclosure.open = open.has(disclosure.dataset.auDisclosure);
      focusTarget(focusKey)?.focus({preventScroll:true});
      if (navigation || !priorViewport && !host.querySelector('[data-au-forming="true"]')) revealGraphNode([...host.querySelectorAll('[data-au-node]')].find(element => element.dataset.auNode === selected));
      fitActiveStage(); syncGraphViewport();
      positionOperationSource();
      drawEdges(navigation); followStage();
      motion = animateTransition(host,changes,{hidden:doc.hidden,dialogOpen:dialog.open || recordDialog.open,reducedMotion:reduced?.matches || Boolean(operationTrace),keyboard,inspecting:inspectionHold,activeElement:doc.activeElement,selected});
      synchronizeAuthority(); synchronizeRecord(); rememberLastCase(); positionOperationAttention();
      if(host.querySelector('[data-au-agent-desk]')){const legend=container.querySelector('[data-au-role-legend]');if(legend)legend.hidden=true;}
      claimRenderComplete = true; renderedClaimId = current.claim_id;
      if (presentationMode==='saved' && host.querySelector('[data-au-agent-desk]')) ensureDeskRecord(current,epoch);
    }
    function setGraphExpanded(expanded) {
      const viewport = host.querySelector('[data-au-graph-pan]'), control = host.querySelector('[data-au-expand-process]');
      if (!viewport || !control) return;
      viewport.dataset.auGraphExpanded = String(expanded);
      control.setAttribute('aria-expanded',String(expanded));
      const overview = viewport.dataset.auGraphOverview === 'true';
      control.textContent = overview ? expanded ? 'Close larger process' : 'Open all steps' : expanded ? 'Close full process' : 'Open all steps';
      host.querySelector('.au-evidence-process')?.setAttribute('aria-label',expanded || overview ? 'Complete process' : 'Decision neighborhood');
      syncGraphViewport();
    }
    // The complete process opens into view: the whole frame when it fits below the sticky chrome,
    // otherwise its top, and always the chosen step. One scroll, smooth only without reduced motion.
    function revealExpandedProcess() {
      const viewport = host.querySelector('[data-au-graph-pan][data-au-graph-expanded="true"]'), frame = viewport?.getBoundingClientRect?.();
      if (!frame || !Number.isFinite(root.innerHeight)) return;
      const node = [...viewport.querySelectorAll('[data-au-node]')].find(element => element.dataset.auNode === selected)?.getBoundingClientRect?.();
      const top = parseFloat(root.getComputedStyle?.(doc.documentElement)?.scrollPaddingTop) || 0, bottom = root.innerHeight - 12;
      let delta = frame.bottom > bottom ? Math.min(frame.bottom-bottom,frame.top-top) : frame.top < top ? frame.top-top : 0;
      if (node) { if (node.bottom-delta > bottom) delta = node.bottom-bottom; else if (node.top-delta < top) delta = node.top-top; }
      if (Math.abs(delta) > 1) root.scrollBy?.({top:delta,behavior:reduced?.matches ? 'instant' : 'smooth'});
    }
    // A graph frame is a keyboard stop only while it actually scrolls; a
    // frame that shows everything is a labelled group, not a tab stop.
    function syncGraphViewport() {
      for (const viewport of host.querySelectorAll?.('[data-au-graph-pan]') || []) {
        if (!viewport.setAttribute) continue;
        const style = root.getComputedStyle?.(viewport), scrolls = value => !style || /auto|scroll/.test(value || '');
        const scrollable = (viewport.scrollWidth > viewport.clientWidth+1 && scrolls(style?.overflowX)) || (viewport.scrollHeight > viewport.clientHeight+1 && scrolls(style?.overflowY));
        const label = viewport.dataset.auGraphExpanded === 'true' || viewport.dataset.auGraphOverview === 'true' ? 'All steps' : 'Nearby steps';
        if (scrollable) { viewport.setAttribute('tabindex','0'); viewport.setAttribute('role','region'); viewport.setAttribute('aria-label',`${label}. Use arrow keys or scroll to explore.`); }
        else { viewport.removeAttribute?.('tabindex'); viewport.setAttribute('role','group'); viewport.setAttribute('aria-label',label); }
      }
    }
    function renderSelection(navigation = false) {
      if (!current || view !== 'claim') return;
      evidenceContext = evidenceSelection(current,selected,evidenceContext);
      motion?.cancel(); selectionMotion?.cancel();
      if (host.querySelector('.au-operation-stage,[data-au-forming="true"]')) { renderClaim(null,navigation); return; }
      const panel = host.querySelector('[data-au-panel="step"]');
      if (!panel) { renderClaim(null,navigation); return; }
      const focused = doc.activeElement, focusKey = focusToken(focused), sources = sourceControls(panel);
      const open = new Set([...panel.querySelectorAll('details[open][data-au-disclosure]')].map(el => el.dataset.auDisclosure));
      panel.innerHTML = inspectorMarkup(current,selected,projection,history,evidenceContext);
      reuseSourceControls(panel,sources);
      const question = host.querySelector('.au-process-question'); if (question) { question.textContent = name(list(current.graph?.nodes).find(node => node.node_id === selected)); question.dataset.auInspectorHeading = selected; }
      for (const disclosure of panel.querySelectorAll('[data-au-disclosure]')) disclosure.open = open.has(disclosure.dataset.auDisclosure);
      const topology = layoutGraph(current.graph), neighborhood = new Set([selected,...(topology.parents.get(selected) || []),...(topology.children.get(selected) || [])]);
      for (const node of host.querySelectorAll('[data-au-node]')) { node.setAttribute('aria-pressed',String(node.dataset.auNode === selected)); node.dataset.auNeighborhood = String(neighborhood.has(node.dataset.auNode)); const relation = node.querySelector('.au-node-relation'); if (relation) { relation.hidden = !neighborhood.has(node.dataset.auNode); relation.textContent = relation.hidden ? '' : node.dataset.auNode === selected ? 'This decision' : topology.parents.get(selected)?.includes(node.dataset.auNode) ? 'Before' : 'Then'; } }
      for (const rank of host.querySelectorAll('.au-graph-rank')) rank.dataset.auNeighborhood = String([...rank.querySelectorAll('[data-au-node]')].some(node => neighborhood.has(node.dataset.auNode)));
      for (const edge of host.querySelectorAll('[data-au-edge]')) { const record = list(current.graph.edges).find(item => item.edge_id === edge.dataset.auEdge); edge.dataset.auNeighborhood = String(Boolean(record && neighborhood.has(record.source_node_id) && neighborhood.has(record.target_node_id))); }
      for (const row of host.querySelectorAll('.au-obligation[data-au-document]')) {
        const item = list(current.obligations).find(item => (item.obligation_id || item.document_type) === row.dataset.auObligation);
        const focused = item && (evidenceContext.obligation ? requirementIdentity(item) === evidenceContext.obligation : evidenceContext.document === item.document_type);
        if (focused) row.setAttribute('data-selected','true'); else row.removeAttribute('data-selected');
      }
      const nodes = layoutGraph(current.graph).nodes, index = nodes.findIndex(node => node.node_id === selected);
      const position = host.querySelector('[data-au-inspection-position]'); if (position) position.textContent = `Step ${index + 1} of ${nodes.length}`;
      const previous = host.querySelector('[data-au-node-previous]'), next = host.querySelector('[data-au-node-next]');
      if (previous) previous.disabled = index <= 0;
      if (next) next.disabled = index >= nodes.length - 1;
      if (!focused?.isConnected) focusTarget(focusKey)?.focus({preventScroll:true});
      if (navigation) revealGraphNode([...host.querySelectorAll('[data-au-node]')].find(node => node.dataset.auNode === selected));
      syncGraphViewport(); drawEdges(navigation); interact(panel); rememberLastCase();
    }
    function setDetail(value, focusFiles = false, writeRoute = true) {
      if (view !== 'claim' || !['step','documents','knowledge','sources','activity'].includes(value)) return;
      if (detail !== value || !host.querySelector(`[data-au-panel="${value}"]`)) { detail = value; renderClaim(); }
      if (writeRoute && root.history?.replaceState && current) { const fragment = selectedClaimFragment(); root.history.replaceState(null,'',root.location.pathname + root.location.search + fragment); routedFragment = fragment; }
      if (focusFiles) host.querySelector('#auAdditionalFiles')?.focus({preventScroll:true});
    }
    async function consistentRead(id, after, reconnect = false, token = epoch, valid = null, quiet = false) {
      let missingSnapshot = false;
      const check = () => { if (disposed || token !== epoch || valid && !valid()) throw new Error('The claim view changed while reading its snapshot.'); };
      if (valid) check();
      if (snapshotAvailable !== false) {
        try {
          const response = await request(`/claims/${key(id)}/snapshot?after=${after ?? 0}`,{},quiet);
          check();
          const result = readSnapshot(response,id,after,reconnect);
          snapshotAvailable = true;
          return result;
        } catch (error) {
          if (![404,405,501].includes(error.status)) throw error;
          if (error.status === 404) missingSnapshot = true; else snapshotAvailable = false;
        }
      }
      if (valid) check();
      const incoming = readState(await request(`/claims/${key(id)}`,{},quiet),id);
      check();
      const batch = await request(`/claims/${key(id)}/events?after=${after ?? 0}`,{},quiet);
      const accepted = acceptEvents(after,batch,incoming.state,reconnect);
      if (missingSnapshot) snapshotAvailable = false;
      return {...incoming,accepted};
    }
    function verifiedAdvance(incoming) {
      if (current && incoming.state.revision < current.revision) throw new Error('A stale claim revision was returned.');
      if (current && incoming.state.revision === current.revision && incoming.state.state_sha256 !== current.state_sha256) throw new Error('A saved revision changed identity.');
    }
    function acceptPublicationAttention(before, after, accepted, changes) {
      if (inspectionHold) return;
      const attention = {previousRevision:before?.revision,revision:after.revision,acceptedEvents:accepted.events,knowledgePublications:changes?.knowledgePublications || []};
      if (formingPublication(after,accepted.events,attention)) publicationAttention = attention;
      else if (changes && ['facts','documents','nodes','edges','sources','knowledgeUses'].some(field => list(changes[field]).length)) publicationAttention = null;
    }
    async function poll() {
      const token = epoch, id = current?.claim_id;
      if (!id || disposed || view !== 'claim' || presentationMode === 'replay' || polling === token) return;
      polling = token; const read = ++claimRead;
      try {
        const incoming = await consistentRead(id,cursor,disconnected);
        if (disposed || token !== epoch || pendingRoute() || view !== 'claim' || read !== claimRead) return;
        const accepted = incoming.accepted;
        if (!accepted.ready) return;
        verifiedAdvance(incoming);
        const changed = !claimRenderComplete || !current || current.state_sha256 !== incoming.state.state_sha256 || cursor !== accepted.cursor || JSON.stringify(projection) !== JSON.stringify(incoming.projection);
        const previousState = current, changes = transitionPlan(current,incoming.state,accepted,history);
        acceptPublicationAttention(previousState,incoming.state,accepted,changes);
        current = incoming.state; projection = incoming.projection; cursor = accepted.cursor; freshClaim = true;
        const existing = new Map(history.map(event => [event.seq,event])); for (const event of accepted.events) existing.set(event.seq,event);
        history = [...existing.values()].sort((a,b) => a.seq-b.seq);
        const entered = !inspectionHold && changes && enteredRequirementContext(previousState,current);
        const followed = demoSession && [...accepted.events].reverse().find(event => consequentialEventNode(previousState,current,event));
        selected = preferredNode(current,entered?.node || (followed ? consequentialEventNode(previousState,current,followed) : selected),history);
        if (entered) { evidenceContext = evidenceSelection(current,selected,entered); detail = 'step'; }
        else if (followed) { evidenceContext = acceptedEventContext(current,followed,selected); detail = 'step'; }
        const newest = accepted.events.at(-1); // Knowledge changes stay in the accepted investigation composition.
        if (changed) { renderClaim(changes); rememberClaim(current); } else synchronizeAuthority();
        snapshotCache();
        if (connectionFailed) notice('Connection restored. Showing saved work.'); else notice('');
        disconnected = false; connectionFailed = false;
        advanceLivePresentation();
      } catch (error) { if (!disposed && token === epoch && !pendingRoute() && read === claimRead) { disconnected = true; connectionFailed = true; freshClaim = false; synchronizeAuthority('failed'); notice(`Updates paused: ${error.message} Saved work remains visible.`, true); } }
      finally { if (polling === token) polling = null; if (!disposed && token === epoch && !pendingRoute() && view === 'claim') schedule(); }
    }
    async function loadOpenedClaim(id, token, preferences = openingPreferences) {
      const read = ++claimRead;
      try {
        let incoming;
        // Old servers still need paired reads. Three attempts stay bounded;
        // transient writer advances then recover on the normal timer.
        for (let attempt = 0; attempt < 3; attempt++) {
          try { incoming = await consistentRead(id,null,true,token); }
          catch (error) { if (!error.transientAdvance) throw error; incoming = null; }
          if (disposed || token !== epoch || pendingRoute() || view !== 'claim' || id !== openingId || read !== claimRead) return;
          if (incoming?.accepted.ready) break;
        }
        if (!incoming?.accepted.ready) {
          const error = new Error('The writer advanced while the claim was opening. Checking again automatically.'); error.transientAdvance = true; throw error;
        }
        verifiedAdvance(incoming);
        const initial = !current, changed = initial || current.state_sha256 !== incoming.state.state_sha256 || JSON.stringify(projection) !== JSON.stringify(incoming.projection);
        current = incoming.state; projection = incoming.projection; cursor = incoming.accepted.cursor; history = incoming.accepted.events; freshClaim = true;
        const previous = initial ? claimViews.get(id) : {selected,evidenceContext,detail};
        const initialPreferences = initial ? preferences : {};
        selected = preferredNode(current,initialPreferences.node || previous?.selected,history); evidenceContext = preferredEvidenceContext(current,selected,history,initialPreferences,previous);
        detail = initialPreferences.detail || previous?.detail || 'step';
        if (changed) renderClaim(); else { synchronizeAuthority(); rememberLastCase(); } snapshotCache(); rememberClaim(current); notice(''); if (initial) focusTitle(); schedule();
        resumeLivePresentation();
        primeClaimReads(token,!claimsLoaded);
        serviceStatus(token).catch(() => {});
        return current;
      } catch (error) {
        if (!disposed && token === epoch && !pendingRoute() && view === 'claim' && read === claimRead) {
          freshClaim = false; synchronizeAuthority('failed'); notice(current ? `Refresh failed: ${error.message} Saved work remains visible.` : error.message,true);
          if (!current) host.innerHTML = (catalogPreviewMarkup(claims.find(claim => claim.claim_id === id),id) || unknownClaimMarkup(id)) + button('Retry opening case',`data-au-claim="${h(id)}"`);
          if (error.transientAdvance || !error.status || error.status >= 500) schedule();
        }
      }
    }
    function selectedClaimFragment() { return claimFragment(current.claim_id,{mode:presentationMode,collection:openingPreferences.collection,operations:openingPreferences.operations,through:replayRecord?.through_seq,detail,node:selected,...evidenceContext}); }
    function rememberSelectionRoute() { if (current) route(selectedClaimFragment()); }
    function paintSavedClaim(id, preferences, focus = true) {
      const cached = cachedRead(snapshots,id);
      if (!cached) return false;
      const failed = host.getAttribute?.('data-au-read-state') === 'failed';
      current = cached.state; projection = cached.projection; cursor = cached.cursor; history = [...cached.history];
      const previous = claimViews.get(id); selected = preferredNode(current,preferences.node || previous?.selected,history); evidenceContext = preferredEvidenceContext(current,selected,history,preferences,previous); detail = preferences.detail || previous?.detail || 'step';
      renderClaim(); synchronizeAuthority(failed ? 'failed' : 'refreshing'); if (focus) focusTitle(); if (!failed) notice('');
      return true;
    }
    async function openClaim(id, writeHistory = true, preferences = {}) {
      const arriving = view !== 'claim' || openingId !== id;
      deskSelection = null;
      chosenNode = typeof preferences.node === 'string' && preferences.node ? preferences.node : null;
      if (preferences.mode === 'replay') preferences = {...preferences,collection:replayCollection(id,preferences.collection)};
      if (!preferences.demo && tour?.cases[tour.index]?.claim_id !== id) tour = null;
      if (!preferences.demo) stopPresentation();
      else { if (demoTimer) root.clearTimeout(demoTimer); demoTimer = null; if (demoSession) demoSession.preparing = null; }
      leaveView(Boolean(preferences.demo && demoSession?.mode === 'operations' && !doc.hidden),(preferences.mode || 'saved') === 'saved' && id === options.savedSnapshot?.claim_id && !doc.hidden); route(claimFragment(id,preferences),writeHistory);
      operationPeek = null; host.removeAttribute?.('data-au-inspection-operation'); cancelStageMotion(); epoch++; const token = epoch; if (preferences.demo && demoSession) demoSession.epoch = token; cancelPoll(); motion?.cancel(); if (collection.opener !== id) collection.opener = null; setView('claim'); publicationAttention = null; inspectionHold = Boolean(preferences.node || preferences.document || preferences.obligation || preferences.fact || ['sources','documents','knowledge','activity'].includes(preferences.detail)); operationTrace = null; factTokenOperation = null; factTokenAnimation?.cancel(); factToken?.remove?.(); attentionMarker?.remove?.(); attentionPosition = null; current = null; openingId = id; openingPreferences = preferences; selected = null; cursor = null; history = []; disconnected = false; connectionFailed = false; pendingArrival = arrivals.get(id) || null; pendingControl = controls.get(id) || null; pendingStart = starts.get(id) || null; presentationMode = preferences.mode || 'saved'; replayRecord = null; nav(preferences.demo || presentationMode === 'replay' ? 'demonstration' : 'work'); notice('');
      claimRenderComplete = false; detail = preferences.detail || 'step';
      // A newly opened case starts at its top, never at the list's scroll position.
      if (arriving && !doc.hidden) root.scrollTo?.({top:0,left:0,behavior:'instant'});
      routeTitle(caseTitle(id));
      for (const attribute of ['data-au-current-operation','data-au-operation-run-mode','data-au-operation-presentation','data-au-operation-result-available','data-au-operation-result-verified']) host.removeAttribute?.(attribute);
      if (presentationMode !== 'replay') serviceStatus(token,true).catch(error => { if (!disposed && token === epoch) { statusAuthority = null; synchronizeAuthority(); notice(`Live availability unavailable: ${error.message}`,true); } });
      let opening = preferences.demo && demoSession?.verifiedOpening?.claimId === id && demoSession.verifiedOpening.generation === readGeneration ? demoSession.verifiedOpening : null;
      const session = preferences.demo ? demoSession : null;
      const packetAtSelection = session?.mode === 'operations' ? recordedPacket || packetVerification || packetAcquisition : null;
      if (opening?.operationPreparation && session?.mode === 'operations') {
        session.operationPreparation = opening.operationPreparation; session.operationPreparation.token = token; session.operationController = opening.operationPreparation.controller;
        session.useRecorded = opening.operationPreparation.recorded; session.recorded = session.useRecorded;
      }
      if (session?.mode === 'operations' && !packetAtSelection) packetLoadController?.abort();
      if (session?.mode === 'operations') { session.releasePlan = releaseOperationProcess(id); if (session.releasePlan) operationTrace = {releasePlan:session.releasePlan,rows:[],sources:new Map()}; }
      if (demoSession) demoSession.verifiedOpening = null;
      const cached = presentationMode !== 'replay' && paintSavedClaim(id,preferences);
      if (!doc.hidden && !cached && !opening) { host.innerHTML = session?.releasePlan ? releaseProcedurePreview(session.releasePlan,packetAtSelection ? 'pending' : session.operations,{revision:catalogRow(claims,id)?.revision,readOnly:publicReadOnly,tour:tour?.cases === session.cases && tour.cases[tour.index]?.claim_id === id ? tour : null}) : catalogPreviewMarkup(claims.find(claim => claim.claim_id === id),id) || unknownClaimMarkup(id); focusTitle(); if (session?.releasePlan) drawEdges(); }
      interact(host);
      if (presentationMode !== 'replay') {
        sessionRestore?.then(() => { if (!disposed && token === epoch && !pendingRoute() && view === 'claim' && !current && id === openingId) paintSavedClaim(id,preferences); });
        const generation = readGeneration;
        savedSnapshotLoad?.then(ready => { if (ready && !disposed && token === epoch && generation === readGeneration && !pendingRoute() && view === 'claim' && presentationMode === 'saved' && id === openingId && !current && !inspectionHold && !doc.hidden && !dialog.open && !recordDialog.open) paintSavedClaim(id,preferences,false); });
        return loadOpenedClaim(id,token,preferences);
      }
      if (session) session.preparing = token;
      if (session?.mode === 'operations') { cancelIdleReadOwners(); if (!session.operationPreparation && !opening?.referenceReady && !doc.hidden && !inspectionHold && !(packetAtSelection && session.useRecorded)) prepareOperationReads(session,id,token); }
      try {
        const through = preferences.through ?? 0;
        if (!opening && session?.mode === 'operations' && packetAtSelection && through === 0 && (session.operationPreparation || session.useRecorded)) {
          opening = await chooseRecordedOpening(packetAtSelection,session,id,token);
          if (!opening && !session.operationPreparation && !disposed && token === epoch && !pendingRoute()) prepareOperationReads(session,id,token);
        }
        const incoming = readReplay(opening?.response || await request(`/claims/${key(id)}/replay?through_seq=${through}`),id,through);
        if (disposed || token !== epoch || pendingRoute() || view !== 'claim') return;
        if (opening) checkedReplayHead(incoming,{replayHead:opening.head});
        if (session?.releasePlan && !releaseOpeningMatches(session.releasePlan,incoming.state)) { session.releasePlan = null; operationTrace.releasePlan = null; host.querySelector('[data-au-release-plan]')?.remove(); }
        if (opening?.referenceReady && session?.releasePlan) {
          const plan = session.releasePlan, matched = await releaseHeadMatches(plan,opening.verifiedHeadState,opening.plannedProcess);
          if (disposed || token !== epoch || pendingRoute() || view !== 'claim') return;
          session.releaseMatched=matched; session.releasePlan=null; if (operationTrace?.releasePlan === plan) { operationTrace.releasePlan=null; operationTrace.releaseMatched=matched; }
          if (!matched) host.querySelector('[data-au-release-plan]')?.remove();
        }
        current = incoming.state; projection = incoming.projection; cursor = incoming.accepted.cursor; history = incoming.accepted.events; replayRecord = incoming.replay;
        if (opening?.openingBinding && session?.mode === 'operations') operationTrace = {openingBinding:opening.openingBinding,buffer:opening.operationBuffer,plannedProcess:opening.plannedProcess,recorded:opening.operationPreparation.recorded,headState:opening.verifiedHeadState,pinnedJournal:opening.verifiedJournal || [],rows:[],sources:new Map()};
        const previous = claimViews.get(id); selected = preferredNode(current,preferences.node || previous?.selected,history); evidenceContext = preferredEvidenceContext(current,selected,history,preferences,previous); detail = inspectionHold ? detail : preferences.detail || previous?.detail || 'step';
        renderClaim(); notice(''); if (!inspectionHold && !doc.hidden && !dialog.open && !recordDialog.open) focusTitle();
        primeClaimReads(token,!claimsLoaded);
        if (preferences.demo && ['replay','operations'].includes(session?.mode)) {
          session.replayHead = {claimId:id,revision:replayRecord.current_revision,state_sha256:replayRecord.current_state_sha256,event_sha256:replayRecord.current_event_sha256};
          session.referenceReady = Boolean(opening?.referenceReady);
          session.replayStart = through === 0 && session.collection !== 'selected' ? incoming.replay.replay_start : null;
          session.openingBinding = opening?.openingBinding || null; session.operationBuffer = opening?.operationBuffer || null;
          session.verifiedHeadState = opening?.verifiedHeadState || null; session.verifiedReplayStart = opening?.verifiedReplayStart || null; session.verifiedJournal = opening?.verifiedJournal || null; session.referenceAsOf = opening?.referenceAsOf; session.operationBinding = opening?.operationBinding; session.plannedProcess = opening?.plannedProcess || null;
          session.preparing = null; session.displayedAt = Date.now(); session.motionDuration = motion?.duration || 0;
          if (session.mode === 'operations') startOperations(session,token);
          else await startReplay(session,token);
        }
        return current;
      } catch (error) { if (!disposed && token === epoch) { if (session) presentationFailed(session,`Verified replay unavailable: ${error.message}`); else { notice(`Verified replay unavailable: ${error.message}`,true); host.innerHTML = button('Return to demonstration','data-au-nav="demonstration"'); stopPresentation(); } } }
      finally { if (session?.preparing === token) session.preparing = null; }
    }
    function railClaims() {
      const queue = container.querySelector('[data-au-recent-claims]');
      if (!queue) return;
      queue.innerHTML = claims.slice(0,6).map(claim => `<button type="button" class="au-recent-claim" data-au-claim="${h(claim.claim_id)}"${current?.claim_id === claim.claim_id && view === 'claim' ? ' aria-current="page"' : ''}><strong>${h(claim.title || 'Untitled case')}</strong><span data-tone="${tone(claim.status)}">${h(claimStatusLabel(claim.status,claim))}</span></button>`).join('') || '<p class="au-empty">No saved cases yet.</p>';
    }
    function rememberClaim(state, origin) {
      const index = claims.findIndex(row => row.claim_id === state.claim_id);
      const inferredOrigin = origin || state.origin || (index >= 0 ? claims[index].origin : state.revision > 0 && !state.original_binding ? 'native_intake' : state.original_binding ? 'canonical_original' : undefined);
      const summary = {...(index >= 0 ? claims[index] : {}),...(inferredOrigin ? {origin:inferredOrigin} : {}),claim_id:state.claim_id,title:state.title,status:state.status,phase:state.phase,phase_summary:state.phase_summary,revision:state.revision,state_sha256:state.state_sha256,policy_id:state.policy_id,updated_at:state.updated_at,outcome:state.outcome,deferral:state.deferral,reconciliations:state.reconciliations,mode:state.revision === 0 ? 'unprocessed' : 'saved'};
      if (index >= 0) {
        if (!Number.isSafeInteger(claims[index].revision) || claims[index].revision <= summary.revision) claims[index] = summary;
      } else claims.unshift(summary);
      railClaims();
    }
    // Rendering options: the reader's refinements plus the API's browsing
    // search results. Neither is part of any record.
    const collectionView = () => ({...collection,searchMatches,searchState:collectionSearch.state,readOnly:publicReadOnly});
    // A background refresh never moves focus. A control it replaces keeps
    // focus on its replacement.
    function keepCollectionFocus(update) {
      const active = doc.activeElement, inside = Boolean(active && host.contains?.(active));
      const attr = inside ? ['data-au-claim','data-au-filter','data-au-page','data-au-collection-scope','data-au-domain','data-au-nav'].find(name => active.hasAttribute?.(name)) : null, value = attr ? active.getAttribute(attr) : null;
      update();
      if (attr && !active.isConnected && focusEligible(active)) [...host.querySelectorAll(`[${attr}]`)].find(element => element.getAttribute(attr) === value)?.focus?.({preventScroll:true});
    }
    function refreshCollection() {
      if (view !== 'work') return;
      const options = collectionView(), previousPage = collection.page, page = collectionPage(claims,options); collection.page = page.page;
      if (previousPage !== page.page && !pendingRoute()) rememberCollectionRoute();
      const scoped = collectionRows(claims,collection.scope), emptyAdded = collection.scope === 'added' && !scoped.length;
      keepCollectionFocus(() => {
        const output = host.querySelector('[data-au-claims]');
        if (output) { const markup = emptyAdded ? addedEmptyMarkup(publicReadOnly) : claimsMarkup(claims,options); if (output.auRows !== markup) { output.innerHTML = markup; output.auRows = markup; } }
        const pagination = host.querySelector('[data-au-pagination]'); if (pagination) { const holder = doc.createElement?.('div'); if (holder) { holder.innerHTML = paginationMarkup(page); if (emptyAdded) holder.firstElementChild.hidden = true; pagination.replaceWith(holder.firstElementChild); } }
        const line = host.querySelector('[data-au-status-line]'); if (line) { const markup = statusLineMarkup(scoped,matchingClaims(scoped,{...options,filter:'all'}),collection.filter); if (line.auLine !== markup) { line.innerHTML = markup; line.auLine = markup; } }
      });
      const count = host.querySelector('[data-au-collection-count]'); if (count) count.textContent = collectionCountText(options,page.total,scoped.length,scoped);
      for (const control of host.querySelectorAll('[data-au-collection-scope]')) { const number = control.querySelector('[data-au-scope-count]'); if (number) number.textContent = `(${collectionRows(claims,control.dataset.auCollectionScope).length})`; }
      for (const control of host.querySelectorAll('[data-au-domain]')) {
        const id = control.dataset.auDomain, count = id === 'all' ? scoped.length : scoped.filter(claim => domainOf(claim) === id).length;
        control.setAttribute('aria-pressed',String(collection.domain === id)); control.disabled = id !== 'all' && !count;
      }
      // A return that arrived before its rows finishes once, on the opened row
      // or else the list heading, unless the reader has already moved focus.
      // The opener never outlives that first loaded refresh.
      if (collection.opener && claimsLoaded) {
        const focused = doc.activeElement;
        if (!focused || focused === doc.body) { if (returnToOpener()) { if (collection.scrollTop !== undefined) restoreCollectionPlace(); } else focusTitle(); }
        collection.opener = null;
      }
      routeTitle(collectionTitle());
    }
    // Collection search: each uncached term is also asked of the API, which
    // reads the full original message, the file names and language names.
    // Results are browsing hints for this collection identity only.
    const searchMatches = new Map(), collectionSearch = {state:'',timer:0,read:0,identity:null};
    function queueCollectionSearch(immediate = false) {
      root.clearTimeout(collectionSearch.timer); collectionSearch.timer = 0;
      const missing = searchTerms(collection.search).filter(term => !searchMatches.has(term));
      if (!missing.length) { collectionSearch.read++; collectionSearch.state = ''; return; }
      collectionSearch.state = 'pending';
      const run = () => readCollectionSearch(missing);
      if (immediate) run(); else collectionSearch.timer = root.setTimeout(run,250);
    }
    async function readCollectionSearch(terms) {
      const read = ++collectionSearch.read, generation = readGeneration;
      let failed = false;
      try {
        const results = await Promise.all(terms.map(term => request(`/claims?q=${encodeURIComponent(term)}&limit=500`,{},true)));
        if (disposed || read !== collectionSearch.read) return;
        if (generation !== readGeneration) throw new Error('The collection was read again during the search.');
        results.forEach((data,index) => {
          if (!Array.isArray(data?.claims) || Number.isSafeInteger(data.total) && data.total > data.claims.length) throw new Error('The collection search is incomplete.');
          if (searchMatches.size >= 48) searchMatches.delete(searchMatches.keys().next().value);
          searchMatches.set(terms[index],new Map(data.claims.filter(row => typeof row?.claim_id === 'string').map(row => [row.claim_id,searchHint(row.search_match)])));
        });
      } catch (_) { failed = true; }
      if (disposed || read !== collectionSearch.read) return;
      collectionSearch.state = failed ? 'failed' : '';
      refreshCollection();
      if (view === 'work' && searchTerms(collection.search).length) { const page = collectionPage(claims,collectionView()); announceRecorded(`${page.total} ${page.total === 1 ? 'case matches' : 'cases match'} “${collection.search.trim()}”.`); }
    }
    // Search results belong to one collection read; a changed catalog asks again.
    function resetCollectionSearch(identity) {
      if (identity === collectionSearch.identity) return;
      collectionSearch.identity = identity; searchMatches.clear();
      if (view === 'work' && searchTerms(collection.search).length) queueCollectionSearch(true);
    }
    function canWarmReads(token = epoch, generation = readGeneration, ticket = warmTicket) {
      const selectedOperation = view === 'claim' && (demoSession || pausedPresentation)?.mode === 'operations' && !operationTrace?.finished;
      return !selectedOperation && !disposed && token === epoch && generation === readGeneration && ticket === warmTicket && !doc.hidden && !pendingRoute() && (view === 'work' || view === 'claim' && current);
    }
    async function warmKnowledge(token = epoch) {
      const generation = readGeneration, ticket = warmTicket, attempt = `${generation}:${ticket}`;
      if (!canWarmReads(token,generation,ticket) || knowledgeCache || knowledgeWarmGeneration === attempt) return;
      const read = knowledgeRead; knowledgeWarmGeneration = attempt;
      try {
        const data = readKnowledge(await request('/knowledge',{},true));
        if (!canWarmReads(token,generation,ticket) || read !== knowledgeRead) return;
        if (JSON.stringify(data).length * 2 <= 8 * 1024 * 1024) { knowledgeCache = {value:data}; refreshCaseKnowledge(); }
        // The recorded index can now count later reuse for a shown result.
        const payoff = view === 'claim' && current && host.querySelector('[data-au-knowledge-payoff]');
        if (payoff && knowledgeCache) { const fresh = doc.createElement?.('div'); if (fresh) { fresh.innerHTML = knowledgePayoffMarkup(current,knowledgeCache.value); const next = fresh.querySelector('[data-au-knowledge-payoff]'); if (next && next.outerHTML !== payoff.outerHTML) payoff.replaceWith(next); } }
      } catch (_) { /* A quiet GET warm never replaces a successful read or reports an error. */ }
    }
    function queueClaimWarm(id, intent = false) {
      if (!canWarmReads() || !claims.some(claim => claim.claim_id === id) && !REFERENCE_DEMO_CASES.some(claim => claim.claim_id === id)) return;
      if (intent) warmIntents.add(id);
      const cached = snapshots.get(id);
      if (cached) { if (intent) cachedRead(snapshots,id); return; }
      const queued = warmQueue.findIndex(row => row.id === id);
      if (queued >= 0) { if (intent) warmQueue.unshift(...warmQueue.splice(queued,1)); return; }
      if (warmAttempts.has(id) || warmQueue.length >= 12) return;
      const row = {id,intent,token:epoch,generation:readGeneration,ticket:warmTicket};
      intent ? warmQueue.unshift(row) : warmQueue.push(row);
      runClaimWarmQueue();
    }
    function runClaimWarmQueue() {
      while (warmActive < 2 && warmQueue.length && canWarmReads()) {
        const row = warmQueue.shift(); warmAttempts.add(row.id); warmWorkers.add(row); warmActive++;
        (async () => {
          try {
            const valid = () => canWarmReads(row.token,row.generation,row.ticket);
            const incoming = await consistentRead(row.id,null,true,row.token,valid,true);
            if (!incoming.accepted.ready || !valid()) return;
            const value = {state:incoming.state,projection:incoming.projection,cursor:incoming.accepted.cursor,history:incoming.accepted.events};
            rememberSnapshot(row.id,value,!row.intent && !warmIntents.has(row.id));
          } catch (_) { /* Speculative GET failures never change the current view. */ }
          finally { if (warmWorkers.delete(row)) warmActive--; runClaimWarmQueue(); }
        })();
      }
    }
    function primeClaimReads(token, heads = true) {
      if (warmIdle !== null || !canWarmReads(token)) return;
      if (!root.requestIdleCallback) {
        if (!claimsLoaded) loadClaims(token,false,true).catch(() => {});
        else warmKnowledge(token);
        return;
      }
      const generation = readGeneration, ticket = warmTicket;
      warmIdle = root.requestIdleCallback(() => {
        warmIdle = null;
        if (!canWarmReads(token,generation,ticket)) return;
        // A direct claim entry has not visited Cases. Reuse its verified
        // collection read before priming the same bounded snapshot queue.
        if (!claimsLoaded) { loadClaims(token,false,true).catch(() => {}); return; }
        warmKnowledge(token);
        if (!heads) return;
        const visible = [...host.querySelectorAll('[data-au-claim]')].filter(element => { const bounds = element.getBoundingClientRect?.(); return bounds && bounds.bottom > 0 && bounds.top < (root.innerHeight || 1000); }).slice(0,2).map(element => element.dataset.auClaim);
        for (const id of [...new Set([...visible,...REFERENCE_DEMO_CASES.map(claim => claim.claim_id)])]) queueClaimWarm(id);
      });
    }
    function claimWarmIntent(event) {
      const target = event.target?.closest?.('[data-au-claim]');
      if (target && container.contains(target)) queueClaimWarm(target.dataset.auClaim,true);
    }
    async function loadClaims(token = epoch, force = false, quiet = false) {
      const read = ++claimsRead, generation = readGeneration, ticket = warmTicket;
      const valid = () => !disposed && token === epoch && generation === readGeneration && read === claimsRead && (!quiet || canWarmReads(token,generation,ticket));
      if (!valid()) return;
      const fromCache = !force && collectionCache && Date.now() - collectionCache.at < 15000;
      const data = fromCache ? collectionCache.value : await request('/claims',{},quiet);
      if (!valid()) return;
      const rows = [...list(data.claims)];
      if (Number.isSafeInteger(data.total) && data.total > rows.length) {
        let offset = rows.length;
        while (offset < data.total) {
          if (!valid()) return;
          const page = await request(`/claims?limit=200&offset=${offset}`,{},quiet);
          if (!valid()) return;
          if (page.total !== data.total || page.offset !== offset || !list(page.claims).length || (data.collection_sha256 && page.collection_sha256 !== data.collection_sha256)) throw new Error('The case collection changed while loading. Refresh to read one collection identity.');
          rows.push(...page.claims); offset += page.claims.length;
        }
      }
      if (new Set(rows.map(row => row.claim_id)).size !== rows.length) throw new Error('The case collection contains duplicate canonical identities.');
      const cacheValue = {...data,claims:rows};
      collectionCache = JSON.stringify(cacheValue).length * 2 <= 8 * 1024 * 1024 ? {at:Date.now(),value:cacheValue} : null;
      const remembered = new Map(claims.map(row => [row.claim_id,row]));
      claims = rows.map(row => {
        const known = remembered.get(row.claim_id);
        if (!known || !Number.isSafeInteger(known.revision)) return row;
        const verified = current?.claim_id === row.claim_id && current.revision === row.revision && known.revision === current.revision && known.state_sha256 === current.state_sha256;
        return !Number.isSafeInteger(row.revision) || known.revision > row.revision || verified ? {...row,...known} : row;
      });
      if (fromCache) { for (const [id,row] of remembered) if (!claims.some(claim => claim.claim_id === id)) claims.push(row); }
      else if (current && !claims.some(row => row.claim_id === current.claim_id) && remembered.has(current.claim_id)) claims.unshift(remembered.get(current.claim_id));
      claimsLoaded = true; resetCollectionSearch(isHash(data.collection_sha256) ? data.collection_sha256 : `${rows.length}:${rows.map(row => `${row.claim_id}:${row.revision ?? ''}`).join(',')}`); railClaims(); refreshCollection(); refreshDemonstration(); refreshCaseKnowledge(); warmKnowledge(token); primeClaimReads(token);
    }
    async function serviceStatus(token, force = false) {
      const generation = readGeneration;
      const fromCache = !force && statusCache && Date.now() - statusCache.at < 10000;
      const data = fromCache ? statusCache.value : await request('/status');
      if (disposed || token !== epoch || generation !== readGeneration) return;
      if (!fromCache && JSON.stringify(data).length < 128 * 1024) statusCache = {at:Date.now(),value:data};
      if (!fromCache) statusAuthority = {epoch:token,generation};
      const wasReadOnly = publicReadOnly;
      publicReadOnly ||= readOnlyAccess(data);
      status = publicReadOnly ? {...data,read_only:true,writable:false} : data;
      const newClaimControl = container.querySelector('.au-header-new');
      if (newClaimControl && publicReadOnly) { newClaimControl.remove?.(); newClaimControl.hidden = true; }
      const accessLabel = container.querySelector('[data-au-public-access]'); if (accessLabel) accessLabel.hidden = !publicReadOnly;
      if (!wasReadOnly && publicReadOnly && view === 'claim') renderClaim();
      if (view === 'intake' && publicReadOnly) { const form = host.querySelector('[data-au-intake]'); if (form) lockForm(form,true); }
      if (view === 'claim') {
        const start = host.querySelector('[data-au-start]'); if (start) markStart(start,busy || !freshClaim || !canStartHere() && !pendingStart);
        const availability = host.querySelector('[data-au-start-availability]'); if (availability) availability.textContent = pendingStart ? 'The start response is unconfirmed. Retry uses the same request.' : claimAvailability(status,current,projection).reason;
      }
      if (view === 'demonstration') refreshDemonstration();
      resumeLivePresentation();
      const service = host.querySelector('[data-au-service]');
      const allowanceMessage = status.limits?.autonomous_can_start === false ? new Map([
        ['call_limit_reached','The recorded call allowance does not permit more autonomous work.'],
        ['cost_limit_reached','The recorded cost allowance does not permit more autonomous work.'],
        ['provider_outcome_pending','A provider outcome is pending, so new autonomous work cannot start yet.'],
        ['provider_cost_bound_exceeded','A recorded provider cost exceeded its bound, so new autonomous work cannot start.']
      ]).get(status.limits.autonomous_reason) || 'Autonomous inference is unavailable for new work.' : '';
      if (service) service.textContent = !writable(status) ? 'This workspace is view only.' : !status.enabled ? 'Autonomous work is disabled.' : !status.provider_ready ? 'Inference is unavailable. New packets are saved with a named deferral.' : allowanceMessage ? `${allowanceMessage} You can still save a new case; autonomous work will have a named deferral.` : 'Local evidence acquisition and document preparation are available. External dispatch is not configured.';
      if (view === 'intake' && !busy && !pendingIntake) idleIntakeSubmit(host.querySelector('[data-au-intake]'));
      if (view === 'intake' && !status.enabled && !pendingIntake) { const submit = host.querySelector('button[type="submit"]'); if (submit) submit.disabled = true; }
    }
    function collectionFragment() {
      const params = new URLSearchParams();
      if (collection.scope === 'added') params.set('scope','added');
      if (collection.search) params.set('q',collection.search);
      if (collection.filter !== 'all') params.set('filter',collection.filter);
      if (collection.domain !== 'all') params.set('domain',collection.domain);
      if (collection.page > 1) params.set('page',String(collection.page));
      return '#autonomous/cases' + (params.size ? '?' + params : '');
    }
    function rememberCollectionRoute(push = false) {
      if (!root.location || !root.history?.replaceState) return;
      const fragment = collectionFragment();
      if (push && root.history.pushState && root.location.hash !== fragment) root.history.pushState(null,'',root.location.pathname + root.location.search + fragment);
      else root.history.replaceState(null,'',root.location.pathname + root.location.search + fragment);
      routedFragment = fragment;
    }
    function refreshDemonstration() {
      if (view !== 'demonstration') return;
      const overview = host.querySelector('[data-au-demo-overview] .au-demo-cases'), fresh = overview && doc.createElement?.('div');
      if (fresh) { fresh.innerHTML = demonstrationOverviewMarkup(claims); overview.innerHTML = fresh.querySelector('.au-demo-cases').innerHTML; }
      const selection = host.querySelector('.au-demo-selection');
      if (selection) { const wrapper = doc.createElement?.('div'); if (wrapper) { wrapper.innerHTML = demonstrationMarkup(claims,status,demoMode); selection.innerHTML = wrapper.querySelector('.au-demo-selection').innerHTML; } }
      for (const choice of host.querySelectorAll('[data-au-demo-mode]')) choice.setAttribute('aria-pressed',String(choice.dataset.auDemoMode === demoMode));
      const play = host.querySelector('[data-au-demo-play]'); if (play) { play.textContent = demoMode === 'live' ? 'Start live presentation' : 'Play recorded work'; play.disabled = demoMode === 'live' && !liveAvailability(status).ready; }
      const availability = host.querySelector('[data-au-demo-availability]'); if (availability) availability.textContent = demoMode === 'live' ? liveAvailability(status).reason : 'Recorded executions only. Playback stops if no operational outcome was accepted.';
    }
    function enterDemonstrationView(writeHistory) {
      if (view !== 'demonstration') { leaveView(); epoch++; cancelPoll(); setView('demonstration'); current = null; }
      route('#autonomous/demonstration',writeHistory); nav('demonstration'); notice('');
    }
    async function showDemonstration(writeHistory = true, collection = null, operations = operationRoutePreference(root.location?.hash,root.location?.search)) {
      if (busy) return;
      stopPresentation(); tour = null;
      const requested = demoCollection(collection);
      demoMode = requested === 'selected' ? 'replay' : 'reference';
      // View-only Sites and a configured recorded opening carry their own verified
      // history and open without waiting; a writable workspace first asks its
      // catalog which recorded set exists.
      if (!publicReadOnly && !options.recordedPacket && !claimsLoaded && !inflightReads.has(`${readGeneration}:/claims`)) {
        // Direct entry reads the catalog once, so an unrun workspace never
        // opens a replay frame or requests a history that does not exist.
        enterDemonstrationView(writeHistory); writeHistory = false;
        host.innerHTML = readSkeletonMarkup('demonstration','Demonstration'); routeSettled('demonstration','Demonstration');
        const token = epoch;
        try { await loadClaims(token); } catch (_) { /* An unreadable catalog keeps the verified opening path. */ }
        if (disposed || token !== epoch || pendingRoute() || view !== 'demonstration') return;
      }
      const roster = requested ? {collection:requested,cases:collectionRoster(requested,claims)} : demoRoster(claims);
      if (!roster.collection) {
        enterDemonstrationView(writeHistory);
        host.innerHTML = demonstrationMarkup(claims,status,'reference'); interact(host); routeSettled('demonstration','Demonstration');
        return;
      }
      const chosen = claimFragment(roster.cases[0].claim_id,{mode:'replay',collection:roster.collection,operations,through:0,detail:'step'});
      route(chosen,writeHistory);
      if (!writeHistory && root.history?.replaceState && root.location?.hash !== chosen) { root.history.replaceState(null,'',root.location.pathname + root.location.search + chosen); routedFragment = chosen; }
      demoSession = tourSession(roster.collection,roster.cases,0,operations);
      await openPresentationCase(demoSession,writeHistory);
    }
    // A tour is one roster played in order. Its session owns the exact cases,
    // so a sequence never mixes selected originals with reference assessments.
    function tourSession(collection, cases, index, operations, saved = false) {
      tour = {collection,cases,index,operations};
      return {mode:collection === 'selected' || saved ? 'replay' : 'operations',collection,cases,index,operations,useRecorded:operations === 'recorded'};
    }
    const sessionCases = session => session?.cases || demoCases(session?.collection);
    function activeTour() {
      const row = tour?.cases[tour.index];
      // A release opening has no accepted state yet; its routed case still counts.
      return row && view === 'claim' && presentationMode === 'replay' && (current ? current.claim_id : openingId) === row.claim_id ? tour : null;
    }
    // Skip moves on within the same roster; after the last case it ends the tour.
    function skipTourCase() {
      const shown = activeTour(); if (!shown || busy) return;
      const session = demoSession || pausedPresentation, next = shown.index + 1, operations = session?.operations || shown.operations;
      operationPeek = null; host.removeAttribute?.('data-au-inspection-operation'); inspectionHold = false;
      // A playing check finishes unpresented and advances on its own stream, so
      // the shared check allowance is not spent twice on one case.
      if (session?.mode === 'operations' && session.cases === shown.cases && session.claimId === current?.claim_id && operationTrace && !operationTrace.savedFallback && !reduced?.matches) {
        pausedPresentation = null; demoSession = session; session.skip = true; session.skipCase = true;
        if (demoTimer) root.clearTimeout(demoTimer); demoTimer = null; session.operationWake?.();
        cancelStageMotion(); renderClaim(); return;
      }
      stopPresentation();
      if (next >= shown.cases.length) { finishTour(shown,true); return; }
      demoSession = tourSession(shown.collection,shown.cases,next,operations);
      openPresentationCase(demoSession,true);
    }
    // The tour ends at the knowledge its cases saved or reused. Without any,
    // the last case stays and says so; nothing is inferred from labels.
    async function finishTour(finished, explicit = false) {
      const token = epoch, generation = readGeneration, ids = finished.cases.map(row => row.claim_id);
      stopPresentation();
      let data = knowledgeCache?.value || null;
      if (!data) { try { data = readKnowledge(await request('/knowledge')); } catch (_) { data = null; } }
      if (disposed || token !== epoch || generation !== readGeneration || pendingRoute() || view !== 'claim' || tour !== finished) return;
      const payoff = data && tourKnowledgePayoff(data,ids);
      if (!payoff) { tour = null; renderClaim(); notice(explicit ? 'Demonstration finished. These cases saved or reused no knowledge.' : 'Recorded playback finished.'); return; }
      tour = null;
      await showKnowledge(true,payoff.pin);
      if (!disposed && view === 'knowledge') announceRecorded(`Demonstration finished. ${payoff.announcement}`);
    }
    function stopPresentation() {
      const session = demoSession || pausedPresentation;
      cancelNextOperationOpening(session);
      if (session?.operationPreparation) cancelPreparedOperationReads(session.operationPreparation);
      session?.operationChoiceController?.abort(); session?.operationController?.abort(); session?.operationWake?.();
      cancelStageMotion(); const pane = host.querySelector('.au-operation-passage'); pane?.scrollTo?.({top:pane.scrollTop,behavior:'instant'});
      if (demoTimer) root.clearTimeout(demoTimer); demoTimer = null; demoSession = null; pausedPresentation = null; replayPrefixes.clear();
    }
    function retainOperationSource(previous) {
      let pane = host.querySelector('.au-operation-passage');
      if (!pane) return;
      if (previous?.replaceChildren) {
        const same = previous.dataset.auOperationSource === pane.dataset.auOperationSource && previous.dataset.auOperationTextSha === pane.dataset.auOperationTextSha, scroll = same ? previous.scrollTop : 0;
        previous.dataset.auOperationSource = pane.dataset.auOperationSource; previous.dataset.auOperationTextSha = pane.dataset.auOperationTextSha; previous.dataset.auSourceActive = pane.dataset.auSourceActive;
        if (previous.innerHTML !== pane.innerHTML) previous.replaceChildren(...pane.childNodes);
        pane.replaceWith(previous); pane = previous; pane.scrollTop = scroll;
      }
    }
    let mobileFollowId = null;
    function positionOperationSource() {
      const pane = host.querySelector('.au-operation-passage');
      if (!pane) return;
      if (doc.hidden) return;
      if (pane.hasAttribute('data-au-compact-excerpt')) {
        const source=pane.closest('.au-stage-source'), layout=host.querySelector('.au-stage-layout'), step=host.querySelector('[data-au-stage-active=true]');
        const narrow=(root.innerWidth || 1280)<=700, target=narrow&&step?step:layout;
        if(source && target && source.parentElement!==target)target.prepend?.(source);
        pointSourceAtStep(pane);
        const id=operationTrace?.current?.id;
        if(narrow && source && id!==mobileFollowId && demoSession && !inspectionHold && !operationPeek && !reduced?.matches && !operationTrace?.finished){
          mobileFollowId=id;
          source.scrollIntoView?.({block:'center',behavior:'instant'});
        }
        return;
      }
      pointSourceAtStep(pane);
      const operation = (operationPeek?.trace || operationTrace)?.current, mark = pane.querySelector('[data-au-operation-span]');
      if (mark && mark.dataset.auOperationSpan === operation?.id) {
        const frame = pane.getBoundingClientRect(), bounds = mark.getBoundingClientRect(), body = pane.querySelector('[data-au-source-body-anchor]'), floor = body ? pane.scrollTop+body.getBoundingClientRect().top-frame.top-28 : 0, top = pane.scrollTop + bounds.top-frame.top-Math.max(28,(frame.height-bounds.height)/2);
        const target = Math.max(0,Math.min(pane.scrollHeight-pane.clientHeight,Math.max(floor,top))); stageScrollTarget = {pane,top:target};
        pane.scrollTo?.({top:target,behavior:operationPeek || inspectionHold || reduced?.matches ? 'instant' : 'smooth'});
      } else if (operation?.kind === 'source.open') { const body = pane.querySelector('[data-au-operation-read-context]'); const top = body ? pane.scrollTop+body.getBoundingClientRect().top-pane.getBoundingClientRect().top-30 : 0; pane.scrollTo?.({top:Math.max(0,top),behavior:'instant'}); }
    }
    // On wide screens the open passage sits above the step it feeds and points at it.
    function pointSourceAtStep(pane) {
      const source = pane.closest('.au-stage-source'), step = host.querySelector('.au-operation-stage [data-au-stage-active=true] > .au-node') || host.querySelector('.au-operation-stage [data-au-stage-active=true]');
      if (!source) return;
      const parent = source.parentElement;
      if (!step || !parent || (root.innerWidth || 1280) <= 700) { source.style.marginLeft = ''; source.removeAttribute('data-au-pointing'); return; }
      const box = parent.getBoundingClientRect(), width = source.offsetWidth, center = step.getBoundingClientRect().left + step.getBoundingClientRect().width/2;
      const left = Math.max(0,Math.min(box.width-width,center-box.left-width/2));
      source.style.marginLeft = `${Math.round(left)}px`; source.style.marginRight = 'auto';
      source.style.setProperty('--au-pointer',`${Math.round(Math.max(18,Math.min(width-18,center-box.left-left)))}px`);
      source.setAttribute('data-au-pointing','true');
    }
    // While a case plays, the page keeps the cited passage, the active step and
    // what it produces in view; at the result, the recorded outcome comes into view.
    let followedId = null;
    function followStage() {
      const stage = host.querySelector('.au-operation-stage');
      if (!stage || !demoSession || operationPeek || inspectionHold || keyboard || reduced?.matches || doc.hidden || detail !== 'step' || (root.innerWidth || 1280) <= 700) return;
      const map = stage.dataset.auStagePhase === 'map', id = map ? `map:${current?.claim_id}` : operationTrace?.current?.id;
      if (!id || id === followedId) return;
      const step = stage.querySelector('[data-au-stage-active=true]');
      const target = map ? stage.querySelector('[data-au-stage-outcome]') : step && (step.querySelector('[data-au-current-fact=true],[data-au-document-focused=true]') || step);
      const keep = map ? stage.querySelector('.au-stage-process') : stage.querySelector('.au-stage-source') || step;
      if (!target || !keep) return;
      followedId = id;
      const covered = Number.parseFloat(root.getComputedStyle?.(doc.documentElement)?.scrollPaddingTop) || 0, height = root.innerHeight, margin = 16;
      const bounds = target.getBoundingClientRect(), top = Math.min(keep.getBoundingClientRect().top,bounds.top);
      let delta = bounds.bottom > height-margin ? Math.min(bounds.bottom-height+margin,top-covered-margin) : top < covered ? top-covered-margin : 0;
      // The outcome's plain result and recorded sentence always come into view.
      const lead = map && (target.querySelector('[data-au-outcome-plain]') || target).getBoundingClientRect();
      if (lead) delta = Math.max(delta,lead.bottom-height+margin);
      // Keep the case heading below the app header while the desktop follows work.
      const title = host.querySelector('[data-au-claim-title]'), header = container.querySelector('.au-identity-header')?.getBoundingClientRect();
      if (!title) return;
      delta = Math.min(delta,Math.max(0,title.getBoundingClientRect().top - Math.max(0,header?.bottom || 0) - margin));
      if (Math.abs(delta) > 4) root.scrollBy?.({top:delta,behavior:'instant'});
    }
    function cancelStageRead() {
      stageChoreography?.finalize?.();
      stageScrollCancel?.(); stageScrollCancel = null;
      if (stageMotionTimer) root.clearTimeout(stageMotionTimer); stageMotionTimer = null;
      if (factTokenAnimation?.playState === 'running') factTokenOperation = null;
      attentionAnimation?.cancel(); factTokenAnimation?.cancel(); factToken?.remove?.(); attentionMarker?.remove?.();
      for (const animation of stageReadAnimations) animation.cancel(); stageReadAnimations = [];
      for (const trail of host.querySelectorAll('[data-au-read-trail],[data-au-cue-artifact]')) trail.remove();
      host.removeAttribute?.('data-au-cue-active');
      for (const chip of host.querySelectorAll('[data-au-fact-docking]')) { chip.style.opacity = ''; chip.removeAttribute('data-au-fact-docking'); }
      if (stageChoreography && !stageChoreography.complete) { stageChoreography.cancelled=true; stageChoreography.resolve(); }
    }
    function cancelStageMotion() { cancelStageRead(); }
    function afterSourceScroll(pane, callback) {
      // Compact excerpts never scroll; no scroll event or quiet interval is due.
      if (pane?.hasAttribute('data-au-compact-excerpt')) { callback(); return; }
      let quiet = null, fallback = null, closed = false;
      const clear = () => { if (closed) return; closed=true; root.clearTimeout(quiet); root.clearTimeout(fallback); pane.removeEventListener?.('scroll',scrolled); pane.removeEventListener?.('scrollend',ended); };
      const finish = () => { if (closed) return; clear(); stageScrollCancel=null; callback(); };
      const ended = () => { const target=stageScrollTarget?.pane === pane ? stageScrollTarget.top : pane.scrollTop; if (Math.abs(pane.scrollTop-target) <= 1) finish(); };
      const scrolled = () => { root.clearTimeout(quiet); quiet=root.setTimeout(ended,90); };
      pane.addEventListener?.('scroll',scrolled,{passive:true}); pane.addEventListener?.('scrollend',ended,{passive:true}); scrolled();
      // A browser without scrollend, or an interrupted native smooth scroll,
      // gets one bounded instant settle. No frame loop samples geometry.
      fallback=root.setTimeout(() => { const top=stageScrollTarget?.pane === pane ? stageScrollTarget.top : pane.scrollTop; pane.scrollTo?.({top,behavior:'instant'}); root.clearTimeout(quiet); quiet=root.setTimeout(finish,0); },1200);
      stageScrollCancel=clear;
    }
    function positionDesk(animate = true) {
      const desk=host.querySelector('[data-au-agent-desk]');if(!desk)return;
      const trace=operationPeek?.trace||operationTrace||deskRecords.get(current?.state_sha256),mark=desk.querySelector('[data-au-desk-quote]'),pane=desk.querySelector('.au-desk-source-scroll');
      const op=trace?.finished?list(trace.rows).findLast(row=>row.kind==='decision'):trace?.current;
      const shown=mark&&list(trace?.rows).find(row=>row.id===mark.dataset.auDeskQuote),model=trace&&deskOperationModel(current,trace),nodeId=shown&&model.operationNodes.get(shown.id)||op&&model?.operationNodes.get(op.id),node=[...desk.querySelectorAll('[data-au-desk-requirement]')].find(el=>el.dataset.auDeskRequirement===nodeId),label=node?.querySelector('.au-desk-node-label');
      if(mark&&pane){const r=mark.getBoundingClientRect(),p=pane.getBoundingClientRect();pane.scrollTop=Math.max(0,pane.scrollTop+r.top-p.top-20);}
      if(stageChoreography&&stageChoreography.operation===op&&!stageChoreography.cancelled&&!stageChoreography.complete)return;
      cancelStageRead();
      const svgElement=tag=>doc.createElementNS('http://www.w3.org/2000/svg',tag),grid=desk.querySelector('.au-desk-grid');
      const draw=()=>{
        if(!mark||!label||!pane||reduced?.matches)return null;
        const area=grid.getBoundingClientRect(),clip=pane.getBoundingClientRect(),rects=[...mark.getClientRects()].filter(r=>r.bottom>clip.top+3&&r.bottom<clip.bottom-3),a=rects.at(-1),b=label.getBoundingClientRect(),card=mark.closest('[data-au-desk-source]').getBoundingClientRect();if(!a)return null;
        const junction=node.querySelector('.au-desk-junction').getBoundingClientRect();
        const x=a.right-area.left,y=a.bottom-area.top+2,tx=junction.left-area.left-3,ty=junction.top-area.top+junction.height/2,svg=svgElement('svg'),path=svgElement('path');svg.setAttribute('class','au-desk-thread');svg.setAttribute('data-au-cue-artifact','desk-thread');svg.setAttribute('aria-hidden','true');svg.setAttribute('viewBox',`0 0 ${area.width} ${area.height}`);path.setAttribute('pathLength','1');path.setAttribute('d',`M${x} ${y} L${card.right-area.left+10} ${y} C${card.right-area.left+28} ${y},${tx-24} ${ty},${tx} ${ty}`);svg.appendChild(path);
        for(const [cx,cy]of [[x,y],[tx,ty]]){const c=svgElement('circle');c.setAttribute('cx',cx);c.setAttribute('cy',cy);c.setAttribute('r','3');svg.appendChild(c);}grid.appendChild(svg);return {svg,path};
      };
      if(!op||!demoSession||inspectionHold||doc.hidden||reduced?.matches||!animate){if(!doc.hidden&&!reduced?.matches)draw();return;}
      trace.deskCues ||= new Set();if(trace.deskCues.has(op.id))return;
      const job={operation:op,complete:false,cancelled:false};job.promise=new Promise(resolve=>job.resolve=resolve);stageChoreography=job;
      const valid=()=>!job.cancelled&&!disposed&&!doc.hidden&&!inspectionHold&&!reduced?.matches&&operationTrace===trace&&demoSession&&(trace.current===op||trace.finished&&op.kind==='decision');
      const run=async(el,frames,duration,name)=>{if(!el?.animate||!valid())return;host.dataset.auCueActive=name;host.dataset.auCueOperation=op.id;host.dataset.auCueKind=op.kind;const animation=el.animate(frames,{duration,easing:'cubic-bezier(.2,.65,.3,1)'});stageReadAnimations.push(animation);try{await animation.finished;}catch(_){};};
      void(async()=>{let thread=null;try{
        if(mark&&shown){await run(mark,[{backgroundSize:'0% 100%'},{backgroundSize:'100% 100%'}],450,'reading');if(valid()){thread=draw();await run(thread?.path,[{strokeDashoffset:1},{strokeDashoffset:0}],600,'thread');await run(desk.querySelector('.au-desk-landing'),[{opacity:0,transform:'translateY(5px)'},{opacity:1,transform:'translateY(0)'}],250,'landing');}}
        if(node&&model.activated.has(nodeId)){trace.deskBuiltNodes ||= new Set();if(!trace.deskBuiltNodes.has(nodeId)){await run(node.querySelector('.au-desk-node-label'),[{opacity:.4,transform:'translateX(4px)'},{opacity:1,transform:'translateX(0)'}],200,'node-build');await run(node.querySelector('.au-desk-junction'),[{transform:'scale(.5)'},{transform:'scale(1)'}],200,'node-arrival');if(valid())trace.deskBuiltNodes.add(nodeId);}}
        if(op.kind==='step.complete'&&node){await run(node.querySelector('.au-desk-junction'),[{transform:'scale(.4)'},{transform:'scale(1.12)'},{transform:'scale(1)'}],300,'completion');await run(node.querySelector('.au-desk-edge'),[{transform:'scaleY(0)'},{transform:'scaleY(1)'}],600,'connector');}
        if(op.kind==='knowledge.reuse')await run(desk.querySelector('.au-desk-reuse'),[{opacity:0},{opacity:1}],300,'reuse');
        if(op.kind==='decision')await run(desk.querySelector('[data-au-desk-answer]'),[{opacity:0,transform:'translateY(6px)'},{opacity:1,transform:'translateY(0)'}],400,'answer');
        if(thread)await run(thread.svg,[{opacity:1},{opacity:0}],400,'thread-fade');
        if(valid())trace.deskCues.add(op.id);
      }finally{thread?.svg.remove();host.removeAttribute('data-au-cue-active');job.complete=true;job.resolve();}})();
    }
    function positionDesktopCues(animate = true) {
      const trace = operationTrace, operation = trace?.finished && trace.verifiedResult ? list(trace.rows).findLast(row => row.kind === 'decision') : trace?.current;
      if (!trace || !operation || detail !== 'step' || doc.hidden || inspectionHold || !demoSession || trace.cueTransition) return;
      if (operation.kind === 'decision' && !trace.finished) return;
      if (stageChoreography?.operation === operation && !stageChoreography.cancelled && !stageChoreography.complete) return;
      cancelStageRead();
      const canvas = host.querySelector('[data-au-canvas]'), mark = host.querySelector('[data-au-operation-span]');
      const fact = [...host.querySelectorAll('[data-au-stage-fact]')].find(el => el.dataset.auStageFact === operation.object.id);
      const document = [...host.querySelectorAll('[data-au-check-operation]')].find(el => el.dataset.auCheckOperation === operation.id);
      const node = [...host.querySelectorAll('[data-au-node]')].find(el => el.dataset.auNode === operation.object.id);
      const answer = host.querySelector('[data-au-stage-outcome]'), reuse = host.querySelector('[data-au-reuse-cue]');
      const dock = operation.kind === 'document.check' ? document : fact;
      const land = () => {
        if (!dock || !['fact.extract','document.check'].includes(operation.kind)) return;
        trace.dockPhases ||= new Map(); trace.dockPhases.set(operation.id,'landed'); dock.dataset.auDockPhase='landed';
        if (operation.kind === 'fact.extract') {
          trace.recentFact = operation.object.id;
          for (const prior of host.querySelectorAll('.au-stage-fact[data-au-landed-recent]')) prior.removeAttribute('data-au-landed-recent');
          fact.setAttribute('data-au-landed-recent','');
        } else {
          document.closest('[data-au-stage-document]')?.setAttribute('data-au-document-checked','true');
          const label = document.querySelector('.au-stage-source-check'); if (label) label.textContent='Received ✓';
        }
      };
      const cues = operationCues(operation,trace,{reducedMotion:Boolean(reduced?.matches || !animate)});
      const ready = operation.kind === 'step.complete' ? node?.dataset.auNodeState === 'done' : operation.kind === 'knowledge.reuse' ? Boolean(reuse) : true;
      trace.cuePresented ||= new Set();
      if (!cues.length || !ready || trace.cuePresented.has(operation.id)) { land(); if (stageChoreography?.operation === operation) { stageChoreography.complete=true; stageChoreography.resolve(); } return; }
      trace.cuePresented.add(operation.id);
      const job = {operation,complete:false,cancelled:false,finalize:land}; job.promise=new Promise(resolve => { job.resolve=resolve; }); stageChoreography=job;
      const valid = () => !job.cancelled && !disposed && operationTrace === trace && (trace.current === operation || trace.finished && operation.kind === 'decision') && !doc.hidden && !inspectionHold && !reduced?.matches;
      const run = async (element,frames,duration,cue) => {
        if (!element?.animate || !valid()) return false;
        host.dataset.auCueActive=cue.name; host.dataset.auCueOperation=cue.operation_id; host.dataset.auCueKind=cue.kind;
        const animation=element.animate(frames,{duration,easing:'cubic-bezier(.2,.65,.3,1)',fill:'none'}); stageReadAnimations.push(animation);
        try { await animation.finished; } catch (_) { return false; }
        return valid();
      };
      const svgElement = tag => doc.createElementNS('http://www.w3.org/2000/svg',tag);
      // Batch geometry reads once before adding the thread. Its vertical leg
      // uses the gutter beside the step, never the title's text rectangle.
      const area=canvas?.getBoundingClientRect(), sourceRects=mark ? [...mark.getClientRects()] : [], source=sourceRects.at(-1), destination=fact?.getBoundingClientRect();
      const targetNode=fact?.closest('.au-stage-step')?.querySelector('[data-au-node]')?.getBoundingClientRect();
      const sourceCard=mark?.closest('.au-stage-source')?.getBoundingClientRect();
      let thread = null, threadPath = null;
      const createThread = () => {
        if (!area || !source || !destination || !targetNode || !sourceCard) return;
        const x=source.left+source.width/2-area.left, y=source.bottom-area.top, lane=sourceCard.bottom-area.top+20, gutter=targetNode.left-area.left-4, endX=destination.left-area.left, endY=destination.top+destination.height/2-area.top;
        thread=svgElement('svg'); thread.setAttribute('class','au-cue-thread'); thread.setAttribute('viewBox',`0 0 ${area.width} ${area.height}`); thread.setAttribute('aria-hidden','true'); thread.setAttribute('data-au-cue-artifact','thread'); thread.dataset.auCuePhase='drawing';
        threadPath=svgElement('path'); threadPath.setAttribute('pathLength','1'); threadPath.setAttribute('d',`M${x} ${y} C${x} ${lane},${gutter} ${lane},${gutter} ${lane} L${gutter} ${endY-6} Q${gutter} ${endY},${endX} ${endY}`); thread.appendChild(threadPath); canvas.appendChild(thread);
      };
      void (async () => {
        try {
          for (const cue of cues) {
            if (!valid()) break;
            if (cue.name === 'reading' && mark) {
              await run(mark,[{backgroundSize:'0% 100%'},{backgroundSize:'100% 100%'}],450,cue);
              mark.dataset.auPhraseLocked=cue.operation_id;
            } else if (cue.name === 'thread' && fact) {
              createThread(); if (threadPath) await run(threadPath,[{strokeDashoffset:1},{strokeDashoffset:0}],500,cue);
              if (thread) thread.dataset.auCuePhase='held';
            } else if (cue.name === 'landing' && fact) {
              land(); await run(fact,[{opacity:0,transform:'translateY(6px)'},{opacity:1,transform:'translateY(0)'}],220,cue);
              if (thread) { thread.dataset.auCuePhase='fading'; await run(thread,[{opacity:1},{opacity:0}],600,cue); thread.remove(); }
            } else if (cue.name === 'confirmation' && fact) {
              trace.confirmedFacts ||= new Set(); trace.confirmedFacts.add(operation.object.id); fact.dataset.auFactConfirmed='true';
            } else if (cue.name === 'document' && document) {
              land(); const matching=host.querySelector(`[data-au-stage-fact="fact:${operation.object.id}"]`); if (matching) { trace.confirmedFacts ||= new Set(); trace.confirmedFacts.add(`fact:${operation.object.id}`); matching.dataset.auFactConfirmed='true'; }
              await run(document,[{backgroundColor:'#e1e8db'},{backgroundColor:'transparent'}],800,cue);
            } else if (cue.name === 'completion' && node) {
              const junction=node.querySelector('[data-au-junction]');
              if (junction) {
                const tick=svgElement('svg'), path=svgElement('path'); tick.setAttribute('viewBox','0 0 16 16'); tick.setAttribute('class','au-cue-check'); path.setAttribute('d','M3 8 L6.5 11.5 L13 4'); path.setAttribute('pathLength','1'); tick.appendChild(path); junction.replaceChildren(tick);
                await run(path,[{strokeDashoffset:1},{strokeDashoffset:0}],300,cue);
              }
            } else if (cue.name === 'connector') {
              for (const path of host.querySelectorAll(`[data-au-edge-source="${operation.object.id}"][data-state=true]`)) {
                path.setAttribute('pathLength','1'); await run(path,[{strokeDasharray:1,strokeDashoffset:1},{strokeDasharray:1,strokeDashoffset:0}],600,cue);
              }
            } else if (cue.name === 'progress') {
              const progress=host.querySelector('[data-au-progress]'), next=completedStepFraction(current), previous=trace.cueProgress || 0;
              if (next > previous) await run(progress,[{transform:`scaleX(${previous})`},{transform:`scaleX(${next})`}],400,cue); trace.cueProgress=next;
            } else if (cue.name === 'answer' && answer) {
              if (!trace.answerTransitioned) await run(answer,[{opacity:0},{opacity:1}],300,cue);
              const rule=answer.querySelector('.au-answer-rule');
              await run(rule,[{transform:'scaleY(0)'},{transform:'scaleY(1)'}],400,cue);
            } else if (cue.name === 'reuse' && reuse) await run(reuse,[{opacity:0},{opacity:1}],300,cue);
          }
          host.removeAttribute('data-au-cue-active');
          // One finite breath fills only the remaining dwell; it never competes
          // with a source/step cue and is cancelled when this operation changes.
          const dot=host.querySelector('[data-au-working-dot]');
          if (valid() && dot && trace.current === operation) {
            const breath=dot.animate([{opacity:.35},{opacity:1},{opacity:.35}],{duration:2400,easing:'ease-in-out',iterations:1}); stageReadAnimations.push(breath);
          }
        } finally { land(); thread?.remove(); job.complete=true; job.resolve(); }
      })();
    }
    function positionOperationAttention(animate = true, sourceReady = false, pending = null) {
      if(host.querySelector('[data-au-agent-desk]')){positionDesk(animate);return;}
      if ((root.innerWidth || 0) > 700) { positionDesktopCues(animate); return; }
      if (!sourceReady) cancelStageRead();
      const ownerTrace=operationTrace, operation = ownerTrace?.current, canvas = host.querySelector('[data-au-canvas]');
      if (!operation || !canvas || detail !== 'step' || doc.hidden || reduced?.matches || operationTrace.finished || inspectionHold || host.querySelector('.au-operation-stage[data-au-stage-phase=map]')) { attentionMarker?.remove?.(); return; }
      const reading = operationReading(operationTrace), mark = host.querySelector('[data-au-operation-span]');
      if (sourceReady && (stageChoreography !== pending || pending?.cancelled)) return;
      if (!sourceReady && animate && reading?.active && mark) {
        const choreography = {operation,complete:false,cancelled:false}; choreography.promise=new Promise(resolve => { choreography.resolve=resolve; }); stageChoreography=choreography;
        afterSourceScroll(mark.closest('.au-operation-passage'),() => { if (operationTrace?.current === operation && !doc.hidden && !inspectionHold) positionOperationAttention(true,true,choreography); else { choreography.cancelled=true; choreography.resolve(); } });
        return;
      }
      const complete = () => { if (pending && !pending.cancelled) { pending.complete=true; pending.resolve(); } };
      const graph = operationStageGraph(operationTrace,current), nodeId = operationNodeId(operation,graph,current,operationTrace);
      const node = [...host.querySelectorAll('[data-au-node]')].find(item => item.dataset.auNode === nodeId);
      const factDock = [...host.querySelectorAll('[data-au-stage-fact]')].find(item => item.dataset.auStageFact === operation.object.id);
      const documentDock = operation.kind === 'document.check' ? [...host.querySelectorAll('[data-au-check-operation]')].find(item => item.dataset.auCheckOperation === operation.id && item.closest('[data-au-document-supported=true]')) : null;
      const dock = documentDock || factDock;
      if(!reading?.active){attentionMarker?.remove?.();complete();return;}
      if (node) revealGraphNode(reading?.active && mark?.closest?.('.au-stage-source') || node.closest('.au-stage-step') || node,true);
      const passage = mark?.closest('.au-operation-passage'), destination = reading?.active && mark ? mark : node;
      if (!destination) { attentionMarker?.remove?.(); complete(); return; }
      // Read geometry once after source centering. Every sweep, fade, growth and
      // curved transfer below uses bounded compositor transforms and opacity.
      const lineRects = destination === mark ? [...mark.getClientRects()].slice(0,24) : [], area = canvas.getBoundingClientRect(), rect = lineRects[0] || destination.getBoundingClientRect(), clip = passage?.getBoundingClientRect(), dockRect = dock?.getBoundingClientRect();
      const local = (x,y) => ({x:x-area.left+canvas.scrollLeft,y:y-area.top+canvas.scrollTop});
      const transform = point => `translate(${point.x}px,${point.y}px)`;
      const origin = local(rect.left,clip ? Math.max(clip.top+6,Math.min(rect.top,clip.bottom-24)) : rect.top);
      const canDock = reading?.active && dock && dockRect && node && factTokenOperation !== operation.id && (
        operation.kind === 'fact.extract' ||
        operation.kind === 'document.check' && operation.result.assessment === 'sufficient' && list(current.evaluation?.documents).some(row => row.document_type === operation.object.id && row.review_state === 'sufficient'));
      const transfer = () => {
        if (!canDock || !demoSession || operationTrace !== ownerTrace || ownerTrace.current !== operation || doc.hidden || inspectionHold || reduced?.matches || !dock.isConnected) { complete(); return; }
        factTokenOperation = operation.id; ownerTrace.dockPhases ||= new Map(); ownerTrace.dockPhases.set(operation.id,'transfer'); dock.dataset.auDockPhase='transfer';
        const next = local(dockRect.left,dockRect.top), span = stageFactSpan(operation,true);
        factToken = doc.createElement('span'); factToken.className = 'au-operation-fact-token'; factToken.dataset.auOperationId = operation.id; factToken.dataset.auObjectType = documentDock ? 'document' : 'fact'; factToken.dataset.auObjectId = operation.object.id; factToken.setAttribute('aria-hidden','true');
        if (documentDock) { const title=doc.createElement('strong'), quote=doc.createElement('span'); title.textContent=operationSourceTitle(reading.source); quote.textContent=span.quote; factToken.append(title,quote); } else factToken.textContent = span.quote;
        factToken.dataset.auSourceArtifact = operation.source.artifact_id; factToken.dataset.auSourceSha = operation.source.sha256;
        factToken.dataset.auSourceStartChar = span.start_char; factToken.dataset.auSourceEndChar = span.end_char; factToken.dataset.auCitationStartChar = operation.source.start_char; factToken.dataset.auCitationEndChar = operation.source.end_char;
        if (documentDock) factToken.dataset.auDocumentTransfer = operation.id;
        factToken.style.transform = transform(next); canvas.appendChild(factToken);
        dock.dataset.auFactDocking = operation.id; dock.style.opacity = '0';
        const flight = [{transform:`${transform(origin)} scale(.82)`,opacity:0,offset:0},{transform:`${transform(origin)} scale(1)`,opacity:1,offset:.18}];
        // Sample one cubic curve once, never on animation frames.
        const bend = Math.max(32,Math.min(100,Math.abs(next.x-origin.x)*.25));
        for (let step=1; step<=8; step++) { const t=step/8, u=1-t; const point={x:u*u*u*origin.x+3*u*u*t*(origin.x+bend)+3*u*t*t*(next.x-bend)+t*t*t*next.x,y:u*u*u*origin.y+3*u*u*t*(origin.y-24)+3*u*t*t*(next.y-24)+t*t*t*next.y}; flight.push({transform:transform(point),opacity:1,offset:.18+.82*t}); }
        factTokenAnimation = factToken.animate(flight,{duration:operationChoreographyTiming(operation,ownerTrace).transfer,easing:'cubic-bezier(.18,.7,.25,1)',fill:'none'});
        const token = factToken; factTokenAnimation.onfinish = () => { token.remove(); if (operationTrace !== ownerTrace || ownerTrace.current !== operation) { complete(); return; } ownerTrace.dockPhases.set(operation.id,'landed'); ownerTrace.recentLanding = operation.id; if (dock.isConnected) { dock.dataset.auDockPhase='landed'; dock.style.opacity=''; dock.removeAttribute('data-au-fact-docking'); const slot=dock.closest('[data-au-stage-document]'); if (slot) slot.dataset.auDocumentChecked='true'; for (const earlier of host.querySelectorAll('[data-au-landed-recent]')) earlier.removeAttribute('data-au-landed-recent'); (slot || dock).setAttribute('data-au-landed-recent',''); } complete(); };
        node.dataset.auOperationId = operation.id; attentionPosition = next;
      };
      if (factTokenAnimation?.playState === 'running') return;
      attentionMarker ||= doc.createElement('div'); attentionMarker.className = 'au-operation-attention'; attentionMarker.setAttribute('aria-hidden','true'); attentionMarker.dataset.auOperationAttention = operation.id; attentionMarker.dataset.auActor = reading?.active ? 'reading' : 'process'; delete attentionMarker.dataset.auReadPhase; attentionMarker.style.height='';
      canvas.appendChild(attentionMarker); attentionMarker.style.transform = transform(origin);
      if (animate && reading?.active && operationTrace.dockPhases?.get(operation.id) === 'transfer') { mark.dataset.auPhraseLocked=operation.id; transfer(); return; }
      if (animate && reading?.active && lineRects.length) {
        const visible = lineRects.filter(line => line.width > 0 && (!clip || line.top >= clip.top-1 && line.bottom <= clip.bottom+1)), duration = operationChoreographyTiming(operation,ownerTrace).read;
        if (visible.length) {
          attentionMarker.remove();
          attentionAnimation=mark.animate([{opacity:.45},{opacity:1}],{duration,easing:'linear',fill:'none'});
          attentionAnimation.onfinish=() => { if (operationTrace?.current !== operation || !mark.isConnected || doc.hidden || inspectionHold) { complete(); return; } attentionMarker.dataset.auReadPhase='locked'; mark.dataset.auPhraseLocked=operation.id; attentionMarker.style.opacity='0'; attentionAnimation.cancel(); for (const animation of stageReadAnimations) animation.cancel(); transfer(); };
        } else { attentionMarker.remove(); complete(); }
      } else if (animate && attentionPosition) attentionAnimation = attentionMarker.animate([{transform:transform(attentionPosition),opacity:.2},{transform:transform(origin),opacity:1}],{duration:480,easing:'cubic-bezier(.18,.8,.25,1)',fill:'none'});
      attentionPosition = origin; if (node) node.dataset.auOperationId = operation.id; if (!reading?.active) complete();
    }
    async function operationPresentationGate(session,token,operation) {
      while (operationActive(session,token) && operationTrace?.current === operation && !session.skip && !reduced?.matches) {
        if (!await operationGate(session,token)) return false;
        if ((root.innerWidth || 0) <= 700 && !operationReading(operationTrace)?.active) break;
        if (!stageChoreography || stageChoreography.operation !== operation || stageChoreography.cancelled) { positionOperationSource(); positionOperationAttention(); }
        const choreography=stageChoreography; if (!choreography || choreography.operation !== operation) break;
        await choreography.promise; if (choreography.complete) break;
      }
      return operationGate(session,token,operation.kind === 'decision' ? 1200 : operation.source ? 300 : 400);
    }
    function operationActive(session, token) { return !disposed && token === epoch && !pendingRoute() && view === 'claim' && current?.claim_id === session.claimId && !session.operationController?.signal.aborted; }
    async function operationGate(session, token, duration = 0) {
      if (duration && !session.skip && !reduced?.matches && demoSession === session && !doc.hidden && !inspectionHold) await new Promise(resolve => { session.operationWake = resolve; demoTimer = root.setTimeout(() => { demoTimer = null; session.operationWake = null; resolve(); },duration); });
      while (operationActive(session,token) && !session.skip && (demoSession !== session || doc.hidden || inspectionHold || dialog.open || recordDialog.open)) await new Promise(resolve => { session.operationWake = resolve; });
      session.operationWake = null;
      return operationActive(session,token);
    }
    function skipOperations() {
      const session = demoSession?.mode === 'operations' ? demoSession : pausedPresentation?.mode === 'operations' ? pausedPresentation : null;
      if (!session) return;
      operationPeek = null; host.removeAttribute?.('data-au-inspection-operation'); inspectionHold = false; pausedPresentation = null; demoSession = session; session.skip = true;
      if (demoTimer) root.clearTimeout(demoTimer); demoTimer = null; session.operationWake?.();
      cancelStageMotion(); attentionMarker?.remove?.(); const pane = host.querySelector('.au-operation-passage'); pane?.scrollTo?.({top:pane.scrollTop,behavior:'instant'});
    }
    function operationFallbackNotice(session, reason, savedError = null) {
      const recorded = Boolean(session.useRecorded || session.recorded || session.operations === 'recorded');
      notice(savedError === null ? recorded ? 'Could not load this replay. Showing the saved result.' : 'Could not finish this check. Showing the saved result.' : recorded ? 'Could not load this replay or its saved result.' : 'Could not finish this check or load its saved result.',true,'operation-unavailable');
      noticeRecord = {message:reason,mode:recorded?'recorded':'live',...(savedError===null?{}:{saved_result_error:savedError})};
      globalStatus.insertAdjacentHTML?.('beforeend',recordButton('Details','notice'));
    }
    async function fallbackOperations(session, token, reason) {
      const response = await request(`/claims/${key(session.claimId)}/replay?through_seq=${session.replayHead.revision}`), incoming = readReplay(response,session.claimId,session.replayHead.revision);
      checkedReplayHead(incoming,session);
      if (!await operationGate(session,token)) return;
      current = incoming.state; projection = incoming.projection; cursor = incoming.accepted.cursor; history = incoming.accepted.events; replayRecord = incoming.replay;
      if (operationTrace) { operationTrace.finished = true; operationTrace.current = null; operationTrace.savedFallback = true; }
      stopPresentation(); renderClaim(); primeClaimReads(token); operationFallbackNotice(session,reason);
    }
    function prepareOperationReads(session, id, token) {
      // A catalog row at revision zero has no history: no head or operation prefetch.
      if (!REFERENCE_DEMO_CASES.some(row => row.claim_id === id) || knownUnrun(claims,id)) return null;
      const controller = new AbortController(); controllers.add(controller); session.operationController = controller;
      controller.signal.addEventListener('abort',() => controllers.delete(controller),{once:true});
      const prepared = {claimId:id,controller,token,recorded:Boolean(session.useRecorded),readControllers:new Set()};
      session.operationPreparation = prepared;
      const hint = claims.find(row => row.claim_id === id)?.revision;
      // A catalog revision chooses a speculative GET, never a replay authority.
      // Without that hint, a complete atomic head can replace the replay GET
      // only after its identity, history and sources match the real opening.
      if (Number.isSafeInteger(hint) && hint > 0) { prepared.revision = hint; prepared.head = operationRequest(prepared,`/claims/${key(id)}/replay?through_seq=${hint}`); prepared.head.catch(() => {}); }
      else { prepared.snapshot = operationRequest(prepared,`/claims/${key(id)}/snapshot?after=0`); prepared.snapshot.catch(() => {}); }
      prepared.delivery = (async () => {
        const response = await fetcher(base+`/claims/${key(id)}/operations?mode=${prepared.recorded ? 'recorded' : 'live'}`,{method:'GET',headers:{Accept:'application/x-ndjson'},signal:controller.signal});
        if (controller.signal.aborted || disposed || prepared.token !== epoch || pendingRoute()) { await response.body?.cancel?.(); return null; }
        // The existing bounded wire buffer is untrusted until head admission.
        // No early result callback can paint or advertise an accepted result.
        return {response,buffer:response.ok ? bufferedOperations(response,controller.signal,result => prepared.resultAvailable?.(result)) : null};
      })();
      prepared.delivery.catch(() => {});
      return prepared;
    }
    function cancelNextOperationOpening(session) {
      const slot = session?.nextOperationOpening; if (!slot) return;
      session.nextOperationOpening = null; slot.cancelled = true; slot.cancel?.();
      slot.owner.operationChoiceController?.abort();
      if (slot.owner.operationPreparation) cancelPreparedOperationReads(slot.owner.operationPreparation);
    }
    function prefetchNextOperationOpening(session) {
      const next = sessionCases(session)[session.index+1];
      if (next && !session.skip && !reduced?.matches && !doc.hidden) nextOperationOpening(session,next.claim_id).catch(() => {});
    }
    function nextOperationOpening(session,id) {
      const existing = session.nextOperationOpening;
      if (existing?.id === id && !existing.cancelled && existing.generation === readGeneration) return existing.promise;
      cancelNextOperationOpening(session);
      const token = epoch, generation = readGeneration, owner = {useRecorded:session.operations === 'recorded'}, slot = {id,generation,owner,cancelled:false};
      session.nextOperationOpening = slot;
      if (knownUnrun(claims,id)) { slot.promise = Promise.reject(new Error('No recorded execution is available for this original case.')); slot.promise.catch(() => {}); return slot.promise; }
      const active = () => !slot.cancelled && !disposed && token === epoch && generation === readGeneration && !pendingRoute() && !doc.hidden && (demoSession === session || pausedPresentation === session);
      // One bounded next-case buffer is owned independently of the visible trace.
      // Its admitted head supplies only the next case's plan, never prefix facts.
      const packet = recordedPacket;
      if (!(packet && owner.useRecorded)) prepareOperationReads(owner,id,token);
      const cancelled = new Promise((_resolve,reject) => { slot.cancel = () => reject(new Error('The next operation opening was cancelled.')); });
      slot.promise = Promise.race([cancelled,(async () => {
        let opening = packet ? await chooseRecordedOpening(packet,owner,id,token,{active}) : null;
        if (!active()) throw new Error('The next operation opening was cancelled.');
        if (!opening?.referenceReady) {
          if (!owner.operationPreparation) prepareOperationReads(owner,id,token);
          const prepared = owner.operationPreparation, response = opening?.response || await operationRequest(prepared,`/claims/${key(id)}/replay?through_seq=0`), incoming = readReplay(response,id,0);
          const head = {claimId:id,revision:incoming.replay.current_revision,state_sha256:incoming.replay.current_state_sha256,event_sha256:incoming.replay.current_event_sha256};
          const verification = {replayHead:head,replayStart:incoming.replay.replay_start,operationOpeningAnchor:{state:incoming.state}};
          if (!await verifyReferenceHead(verification,prepared) || !verification.verifiedReplayStart) throw new Error('No completed recorded reference assessment is available.');
          if (!active()) throw new Error('The next operation opening was cancelled.');
          opening = {claimId:id,generation,response,head,referenceReady:true,...verification};
        }
        if (!active()) throw new Error('The next operation opening was cancelled.');
        const prepared = owner.operationPreparation; let delivery = await prepared.delivery;
        if (!active()) throw new Error('The next operation opening was cancelled.');
        if (delivery && !delivery.response.ok && !prepared.recorded) {
          await delivery.response.body?.cancel?.();
          if (!active()) throw new Error('The next operation opening was cancelled.');
          const response = await fetcher(base+`/claims/${key(id)}/operations?mode=recorded`,{method:'GET',headers:{Accept:'application/x-ndjson'},signal:prepared.controller.signal});
          if (!active()) { await response.body?.cancel?.(); throw new Error('The next operation opening was cancelled.'); }
          delivery = {response,buffer:response.ok ? bufferedOperations(response,prepared.controller.signal,result => prepared.resultAvailable?.(result)) : null};
          prepared.recorded = true; owner.useRecorded = true; prepared.delivery = Promise.resolve(delivery);
        }
        if (!delivery?.response.ok) throw new Error('The next operation trace is unavailable.');
        const first = await delivery.buffer.first;
        if (!active()) throw new Error('The next operation opening was cancelled.');
        const openingBinding = checkedOperationBinding(first,{...opening.head,...opening.operationBinding},opening.verifiedReplayStart);
        return {...opening,generation,openingBinding,operationBuffer:delivery.buffer,operationPreparation:prepared};
      })()]);
      slot.promise.catch(() => {}); return slot.promise;
    }
    async function operationOutcomeHold(session,token,duration = 8000) {
      let remaining = duration;
      while (remaining > 0 && !session.skip && !reduced?.matches) {
        if (!await operationGate(session,token)) return false;
        const started = Date.now();
        await new Promise(resolve => { session.operationWake = resolve; demoTimer = root.setTimeout(resolve,remaining); });
        if (demoTimer) root.clearTimeout(demoTimer); demoTimer = null; session.operationWake = null;
        remaining -= Math.max(0,Date.now()-started);
        if (!operationActive(session,token)) return false;
      }
      return operationGate(session,token);
    }
    async function startOperations(session, token) {
      if (!operationActive(session,token) || session.operationStarted) return;
      const prepared = session.operationPreparation?.claimId === session.claimId && !session.operationPreparation.controller.signal.aborted && session.operationPreparation.recorded === Boolean(session.useRecorded) ? session.operationPreparation : null;
      session.operationPreparation = null;
      session.operationStarted = true; session.operationController = prepared?.controller || new AbortController(); controllers.add(session.operationController);
      const operationController = session.operationController;
      if (!session.operationOpeningAnchor || session.operationOpeningAnchor.state.claim_id !== session.claimId) session.operationOpeningAnchor = {after_operation:0,state:current,projection,events:history,revision:current.revision,state_sha256:current.state_sha256,event_sha256:current.last_event_sha256,anchor:'verified_opening'};
      const previousAttempts = session.previousAttempts || [], previousCurrent = operationTrace?.current, previousSources = operationTrace?.sources, previousDisplaySource = operationTrace?.displaySource;
      operationTrace = {binding:null,openingBinding:session.openingBinding,buffer:session.operationBuffer,recorded:Boolean(session.useRecorded || session.recorded),releasePlan:session.releasePlan,rows:[],bytes:previousAttempts.reduce((sum,attempt) => sum+attempt.bytes,0),sources:new Map(previousSources || []),current:previousCurrent || null,previousCurrent,displaySource:previousDisplaySource,journal:[],pinnedJournal:session.verifiedJournal || [],headState:session.verifiedHeadState,transportState:null,finished:false,frameHashes:[],visibleResults:new Map(),checkpoints:[session.operationOpeningAnchor],previousAttempts};
      const trace = operationTrace;
      try {
        if ((!session.referenceReady && !await verifyReferenceHead(session,prepared)) || !session.verifiedReplayStart) throw new Error('No current completed reference assessment is available.');
        if (!operationActive(session,token) || operationTrace !== trace) return;
        operationTrace.pinnedJournal = session.verifiedJournal || []; operationTrace.headState = session.verifiedHeadState; operationTrace.asOf = session.referenceAsOf; operationTrace.plannedProcess = session.plannedProcess; renderClaim();
        if (!await operationGate(session,token)) return;
        const delivery = prepared ? await prepared.delivery : null;
        let response = delivery?.response || await fetcher(base+`/claims/${key(session.claimId)}/operations?mode=${session.useRecorded ? 'recorded' : 'live'}`,{method:'GET',headers:{Accept:'application/x-ndjson'},signal:session.operationController.signal});
        if (!operationActive(session,token) || operationTrace !== trace) return;
        if (!response.ok && !session.useRecorded) {
          response = await fetcher(base+`/claims/${key(session.claimId)}/operations?mode=recorded`,{method:'GET',headers:{Accept:'application/x-ndjson'},signal:session.operationController.signal});
          if (!operationActive(session,token) || operationTrace !== trace) return;
          if (!response.ok) throw new Error(`Live assessment and stored operation trace are unavailable (HTTP ${response.status}).`);
          session.recorded = true; operationTrace.recorded = true;
        }
        if (!response.ok) throw new Error(`Stored operation trace unavailable (HTTP ${response.status}).`);
        if (session.useRecorded) { session.recorded = true; operationTrace.recorded = true; }
        if (!operationActive(session,token) || operationTrace !== trace) return;
        const resultAvailable = result => {
          if (operationActive(session,token) && operationTrace === trace && !doc.hidden && result.contract === OPERATIONS_CONTRACT && result.exact_output_verified === true && result.state_sha256 === session.replayHead.state_sha256 && result.current_event_sha256 === session.replayHead.event_sha256) { host.setAttribute?.('data-au-operation-result-available','true'); const total = bufferedOperationCount(trace), slider = host.querySelector('[data-au-operation-scrub]'), counter = host.querySelector('[data-au-scrub-position]'); if (total && slider) { slider.max=total-1; slider.setAttribute('aria-valuetext',`Operation ${Number(slider.value)+1} of ${total}`); slider.closest('.au-stage-scrubber')?.style.setProperty('--au-operation-ticks',total); if (counter) counter.textContent=`${Number(slider.value)+1} / ${total}`; } }
        };
        if (delivery?.buffer) { prepared.resultAvailable = resultAvailable; trace.buffer = delivery.buffer; if (trace.buffer.result) resultAvailable(trace.buffer.result); }
        else trace.buffer = bufferedOperations(response,operationController.signal,resultAvailable);
        const frameBudget = {started:root.performance?.now?.() ?? Date.now()};
        for await (const frame of trace.buffer) {
          if (!await operationGate(session,token)) return;
          if (frame.contract !== OPERATIONS_CONTRACT) throw new Error('The operation stream contract is unavailable.');
          if (frame.type !== 'result') {
            const frameHash = await digest(canonicalJSON(frame));
            if (!operationActive(session,token) || operationTrace !== trace) return;
            trace.frameHashes.push(frameHash);
          }
          if (frame.type === 'binding') {
            if (operationTrace.binding) throw new Error('The stream repeated its operation binding.');
            operationTrace.binding = checkedOperationBinding(frame,{...session.replayHead,...session.operationBinding},session.verifiedReplayStart);
            const receipt=boundDisplayReceipt(session.verifiedHeadState,operationTrace.binding);
            operationTrace.displayProvenance=receipt?{binding:operationTrace.binding,receipt}:null;
            if (session.cases && !session.skip && !reduced?.matches) {
              session.storyPhase = 'opening'; renderClaim(); prefetchNextOperationOpening(session);
              if (!await operationOutcomeHold(session,token,1500)) return;
            }
            session.storyPhase = 'work'; renderClaim(); prefetchNextOperationOpening(session);
          } else if (frame.type === 'operation') {
            const operation = await checkedOperation(frame,operationTrace,current);
            if (!await operationGate(session,token)) return;
            applyWorkingOperation(operation,operationTrace,current);
            const graph = operationStageGraph(operationTrace,current), dockingNode = operationNodeId(operation,graph,current,operationTrace);
            const show = operationAttention(operation,operationTrace) && !(operation.kind === 'decision' && (root.innerWidth || 0) > 700);
            if (show && ['fact.extract','document.check'].includes(operation.kind)) { operationTrace.dockPhases ||= new Map(); operationTrace.dockPhases.set(operation.id,'read'); }
            if (operation.kind === 'fact.extract' && operation.source && dockingNode) {
              operationTrace.dockedFacts ||= new Map(); operationTrace.dockedFacts.set(operation.object.id,{operation,node:dockingNode,observed:true});
            }
            operationTrace.consumed = operation;
            if (show && !session.skip && !reduced?.matches) {
              operationTrace.current = operation; operationTrace.inkRetired = false;
              if (['fact.extract','document.check'].includes(operation.kind)) operationTrace.openingConsequenceId ||= operation.id;
              const sourceCause = operationTrace.rows.find(row => row.id === operation.cause_ids.at(-1)), pin = operation.source || (operation.kind === 'phrase.match' ? sourceCause?.source : null);
              if (pin) operationTrace.displaySource = {artifact_id:pin.artifact_id,pin,id:operation.id};
              else if (operation.kind === 'source.open') operationTrace.displaySource = {artifact_id:operation.object.id,id:operation.id};
              const nodeId = dockingNode;
              if (nodeId && list(graph?.nodes).some(node => node.node_id === nodeId)) { selected = nodeId; evidenceContext = evidenceSelection(current,selected); }
              detail = 'step'; renderClaim();
              if (!await operationPresentationGate(session,token,operation)) return;
            }
          } else if (frame.type === 'checkpoint') {
            const incoming = await checkedOperationCheckpoint(frame,operationTrace);
            if (!await operationGate(session,token)) return;
            current = incoming.state; projection = incoming.projection; cursor = incoming.accepted.cursor; history = incoming.accepted.events; replayRecord = incoming.replay;
            operationTrace.working = null;
            operationTrace.checkpoints ||= []; operationTrace.checkpoints.push({after_operation:operationTrace.rows.length,revision:current.revision,state_sha256:current.state_sha256,event_sha256:frame.event_sha256,state:current,projection,events:history});
            selected = preferredNode(current,selected,history); evidenceContext = evidenceSelection(current,selected,evidenceContext);
            const stageIdentity = canonicalJSON({graph:current.graph?.graph_sha256,facts:list(current.facts).map(row => row.fact_id),documents:current.evaluation?.documents?.map(row => [row.document_type,row.review_state]),completed:current.evaluation?.nodes?.filter(row => row.execution_state === 'completed').map(row => row.node_id),knowledgeUses:list(current.knowledge_uses).map(row=>[row.workflow_id,row.knowledge_id,row.version,row.definition_sha256])});
            if (operationTrace.stageStateIdentity !== stageIdentity && !session.skip && !reduced?.matches) { operationTrace.stageStateIdentity = stageIdentity; renderClaim(); }
            if(frame.events?.[0]?.kind==='knowledge.used' && recordedReuseMoment(current,operationTrace,knowledgeCache?.value || {}) && !await operationGate(session,token,1200))return;
          } else if (frame.type === 'result') {
            const traceHash = await digest(canonicalJSON(trace.frameHashes));
            if (!operationActive(session,token) || operationTrace !== trace) return;
            if (!operationTrace.binding || current.revision !== session.replayHead.revision || current.state_sha256 !== session.replayHead.state_sha256 ||
                frame.state_sha256 !== current.state_sha256 || frame.operation_count !== operationTrace.rows.length || frame.operation_chain_sha256 !== operationTrace.rows.at(-1)?.operation_sha256 || frame.exact_output_verified !== true || frame.trace_sha256 !== traceHash) throw new Error('The operation result differs from its pinned saved result.');
            const revealAnswer = () => { trace.finished = true; trace.verifiedResult = true; trace.current = null; deskRecords.set(current.state_sha256,trace); session.storyPhase = 'answer'; selected = preferredNode(current,selected,history); renderClaim(); };
            cancelStageMotion();
            if ((root.innerWidth || 0) > 700 && !reduced?.matches && !session.skip && !doc.hidden && doc.startViewTransition && host.querySelector('.au-stage-source')) {
              trace.cueTransition = true; trace.answerTransitioned = true;
              const decision = trace.rows.findLast(row => row.kind === 'decision');
              host.dataset.auCueActive='answer-crossfade'; host.dataset.auCueOperation=decision.id; host.dataset.auCueKind=decision.kind;
              const transition = doc.startViewTransition(revealAnswer);
              try { await transition.finished; } catch (_) { /* The verified result remains rendered if the browser cancels a snapshot. */ }
              host.removeAttribute('data-au-cue-active'); trace.cueTransition = false;
              if (!operationActive(session,token) || operationTrace !== trace) return;
              positionOperationAttention();
            } else revealAnswer();
            if(host.querySelector('[data-au-agent-desk]') && !session.skip && !reduced?.matches){
              const decision=trace.rows.findLast(row=>row.kind==='decision');
              if(decision && !await operationPresentationGate(session,token,decision))return;
            }
            // Skip in the tour finishes this case unpresented, then advances like
            // a finished case, reusing the next opening this session prefetched.
            const next = sessionCases(session)[session.index+1], advancing = () => session.skipCase || !session.skip && !reduced?.matches;
            if (next && advancing()) {
              presentationOpening(session,next.claim_id);
              if (!session.skipCase && !await operationOutcomeHold(session,token)) return;
              if (!advancing()) { stopPresentation(); renderClaim(); primeClaimReads(token); return; }
              if (!session.skipCase) { session.storyPhase = 'handoff'; renderClaim(); if (!await operationOutcomeHold(session,token,600)) return; }
              session.skip = false; session.skipCase = false;
              session.operationStarted = false; session.operationOpeningAnchor = null; session.previousAttempts = []; session.useRecorded = session.operations === 'recorded'; session.recorded = false; session.referenceReady = false; session.verifiedReplayStart = null; session.verifiedHeadState = null; session.verifiedJournal = null; session.operationBinding = null; session.plannedProcess = null;
              await openPresentationCase(session,true,session.index+1); return;
            }
            // The last result holds like any other, then the tour ends at its knowledge.
            if (!next && session.cases && tour?.cases === session.cases && advancing()) {
              if (!session.skipCase && !await operationOutcomeHold(session,token)) return;
              if (advancing() && activeTour()?.cases === session.cases) { finishTour(tour,Boolean(session.skipCase)); return; }
            }
            stopPresentation(); renderClaim(); primeClaimReads(token); notice(''); return;
          } else if (frame.type === 'error') throw new Error(frame.message || frame.reason || frame.detail || 'The rules-based assessment stopped.');
          else throw new Error('The operation stream contains an unknown frame.');
          if (!await operationFrameYield(frameBudget,root,() => operationActive(session,token) && operationTrace === trace,() => operationGate(session,token))) return;
        }
        throw new Error('The operation stream ended without a verified result.');
      } catch (error) {
        if (operationActive(session,token)) {
          if (!session.recorded && !session.useRecorded) {
            if (operationTrace?.rows.length) session.previousAttempts = [...list(operationTrace.previousAttempts),{rows:operationTrace.rows,bytes:operationTrace.bytes,recorded:false,reason:error.message}];
            session.useRecorded = true; session.operationStarted = false; operationController.abort(); session.operationController = null; startOperations(session,token); return; }
          try { await fallbackOperations(session,token,error.message); }
          catch (fallback) { if (operationActive(session,token)) { if(operationTrace)operationTrace.replayUnavailable=true;stopPresentation(); renderClaim(); operationFallbackNotice(session,error.message,fallback.message); } }
        }
      } finally { operationController.abort(); controllers.delete(operationController); }
    }
    function presentationFailed(session, message) {
      if (demoSession !== session) return;
      if (doc.hidden) { session.failure = message; return; }
      stopPresentation(); renderClaim(); notice(message,true);
    }
    function syncReplayGuide() {
      const legend = container.querySelector('[data-au-role-legend]');
      if(host.querySelector('[data-au-agent-desk]')){if(legend)legend.hidden=true;return;}
      const recorded = replayRecord?.current_revision > 0 || operationTrace?.binding?.current_revision > 0;
      if (legend) legend.hidden = !(presentationMode === 'replay' && recorded && (pausedPresentation || operationPeek));
    }
    function pausePresentation() {
      if (!demoSession) return false;
      if (demoSession.mode === 'replay' && !demoSession.replayHead) { inspectionHold = true; return false; }
      pausedPresentation = demoSession.mode === 'operations' ? demoSession : {...demoSession,preparing:null};
      if (demoTimer) root.clearTimeout(demoTimer);
      demoTimer = null; demoSession = null; pausedPresentation.operationWake?.(); replayPrefixes.clear();
      motion?.cancel(); selectionMotion?.cancel(); interactionMotion?.cancel(); cancelStageMotion(); const pane = host.querySelector('.au-operation-passage'); pane?.scrollTo?.({top:pane.scrollTop,behavior:'instant'});
      if (pausedPresentation?.mode === 'operations') host.setAttribute?.('data-au-operation-presentation','paused');
      syncReplayGuide();
      if (!current && pausedPresentation?.releasePlan) {
        inspectionHold = true;
        const control = host.querySelector('[data-au-demo-stop]'); if (control) { control.removeAttribute('data-au-demo-stop'); control.setAttribute('data-au-demo-resume',''); control.textContent='Resume'; }
      }
      return true;
    }
    function pauseInspection() {
      if (demoSession && !inspectionHold) centerActiveOperation(true);
      inspectionHold = true; cancelStageMotion(); attentionMarker?.remove?.(); if (publicationAttention) publicationAttention.retained = true; motion?.cancel();
      if (!pausePresentation()) return false;
      const control = host.querySelector('[data-au-demo-stop]');
      if (control) { control.removeAttribute('data-au-demo-stop'); control.setAttribute('data-au-demo-resume',''); control.textContent = 'Resume'; }
      return true;
    }
    function resumePresentation() {
      const session = pausedPresentation;
      if (!session || disposed || pendingRoute() || doc.hidden || dialog.open || recordDialog.open || view !== 'claim') return;
      if (!current && session.releasePlan && openingId === session.claimId) {
        inspectionHold = false; pausedPresentation = null; demoSession = session;
        const control = host.querySelector('[data-au-demo-resume]'); if (control) { control.removeAttribute('data-au-demo-resume'); control.setAttribute('data-au-demo-stop',''); control.textContent='Pause'; }
        session.operationWake?.(); return;
      }
      if (!current || (session.mode === 'replay' ? session.replayHead?.claimId : session.claimId) !== current.claim_id) return;
      operationPeek = null; host.removeAttribute?.('data-au-inspection-operation'); inspectionHold = false; pausedPresentation = null; demoSession = session; session.epoch = epoch; session.displayedAt = Date.now(); renderClaim();
      if (session.mode === 'operations') session.operationWake?.();
      else if (session.mode === 'replay') startReplay(session,epoch);
      else { resumeLivePresentation(); advanceLivePresentation(); }
    }
    async function beginPresentation() {
      if (busy || view !== 'claim' || presentationMode !== 'replay' || !current || !replayRecord || dialog.open || recordDialog.open) return;
      if (pausedPresentation) { resumePresentation(); return; }
      const shown = activeTour(), collection = shown?.collection || replayCollection(current.claim_id,openingPreferences.collection);
      const filtered = shown?.cases || collectionRoster(collection,claims), cases = filtered.some(row => row.claim_id === current.claim_id) ? filtered : demoCases(collection);
      const index = cases.findIndex(row => row.claim_id === current.claim_id);
      if (index < 0) { notice('This recorded case is outside the selected demonstration collection. Its verified history remains available for inspection.'); return; }
      inspectionHold = false;
      if (replayRecord.through_seq >= replayRecord.current_revision) {
        demoSession = {...tourSession(collection,cases,index,shown?.operations || openingPreferences.operations,true)}; await openPresentationCase(demoSession); return;
      }
      tourSession(collection,cases,index,shown?.operations || openingPreferences.operations,true);
      demoSession = {mode:'replay',collection,cases,index,claimId:current.claim_id,epoch,replayHead:{claimId:current.claim_id,revision:replayRecord.current_revision,state_sha256:replayRecord.current_state_sha256,event_sha256:replayRecord.current_event_sha256},displayedAt:Date.now(),motionDuration:0};
      openingPreferences = {...openingPreferences,demo:true};
      renderClaim(); await startReplay(demoSession,epoch);
    }
    async function startReplay(session, token) {
      if (!replayActive(session,token) || doc.hidden || session.preparing) return;
      if (session.failure) { presentationFailed(session,session.failure); return; }
      if (inspectionHold) { pausePresentation(); renderClaim(); return; }
      if (dialog.open || recordDialog.open) return;
      if (session.collection !== 'selected' && !session.referenceReady) {
        session.preparing = token;
        try {
          if (!await verifyReferenceHead(session)) { if (replayActive(session,token)) presentationFailed(session,'This synthetic reference assessment has no completed recorded history available.'); return; }
          session.referenceReady = true;
        } catch (error) { if (replayActive(session,token)) presentationFailed(session,`Verified replay unavailable: ${error.message}`); return; }
        finally { if (session.preparing === token) session.preparing = null; }
      }
      if (!replayActive(session,token) || doc.hidden || inspectionHold || dialog.open || recordDialog.open) return;
      if (session.replayStart && current.revision === 0) {
        session.preparing = token;
        try {
          const start = session.verifiedReplayStart;
          if (!start) throw new Error('The current recording start was not verified.');
          const response = await request(`/claims/${key(current.claim_id)}/replay?through_seq=${start.from_seq}`);
          const incoming = checkedReferenceReplayOpening(response,start,current.claim_id); checkedReplayHead(incoming,session);
          if (!replayActive(session,token) || doc.hidden || inspectionHold || dialog.open || recordDialog.open) return;
          session.verifiedOpening = {claimId:current.claim_id,generation:readGeneration,response,head:session.replayHead,referenceReady:true};
          session.preparing = null;
          const preferences = {mode:'replay',collection:session.collection,operations:session.operations,through:start.from_seq,detail:'step',demo:true};
          const fragment = claimFragment(current.claim_id,preferences);
          if (root.history?.replaceState) { root.history.replaceState(null,'',root.location.pathname + root.location.search + fragment); routedFragment = fragment; }
          await openClaim(current.claim_id,false,preferences);
        } catch (error) { if (replayActive(session,token)) presentationFailed(session,`Verified replay unavailable: ${error.message}`); }
        finally { if (session.preparing === token) session.preparing = null; }
        return;
      }
      prefetchReplay(session); replayTick(session,token);
    }
    async function openPresentationCase(session, writeHistory = true, index = session.index) {
      if (demoSession !== session || disposed || pendingRoute() || doc.hidden && session.replayHead || session.preparing) return;
      if (index >= sessionCases(session).length) {
        detail = 'step'; selected = preferredNode(current,selected,history); evidenceContext = evidenceSelection(current,selected,evidenceContext);
        const shown = activeTour();
        if (shown && shown.cases === session.cases) { finishTour(shown); return; }
        stopPresentation(); notice('Recorded playback finished.'); renderClaim(); return;
      }
      const id = sessionCases(session)[index].claim_id;
      if (['replay','operations'].includes(session.mode) && current && replayRecord && session.claimId === current.claim_id && id !== current.claim_id) {
        const token = epoch, generation = readGeneration, priorId = current.claim_id, priorHash = current.state_sha256;
        session.preparing = token;
        try {
          const opening = await presentationOpening(session,id);
          if (session.mode === 'operations' && token === epoch && generation === readGeneration && (demoSession === session || pausedPresentation === session)) {
            if (!await operationGate(session,token)) return;
            if (session.skip || reduced?.matches) { stopPresentation(); renderClaim(); return; }
          }
          if (demoSession !== session || disposed || token !== epoch || generation !== readGeneration || pendingRoute() || current?.claim_id !== priorId || current.state_sha256 !== priorHash || inspectionHold || doc.hidden || dialog.open || recordDialog.open) return;
          if (session.collection !== 'selected' && !opening.referenceReady) {
            const verification = {replayHead:opening.head,replayStart:opening.response.replay_start};
            if (!await verifyReferenceHead(verification)) throw new Error('No completed recorded reference assessment is available.');
            opening.referenceReady = true; opening.verifiedReplayStart = verification.verifiedReplayStart;
            opening.referenceReady = true;
            if (demoSession !== session || disposed || token !== epoch || generation !== readGeneration || pendingRoute() || current?.claim_id !== priorId || current.state_sha256 !== priorHash || inspectionHold || doc.hidden || dialog.open || recordDialog.open) return;
          }
          session.verifiedOpening = opening;
          const remaining = session.mode === 'operations' ? 0 : Math.max(0,4000 - (Date.now() - session.displayedAt));
          if (remaining) { demoTimer = root.setTimeout(() => { demoTimer = null; openPresentationCase(session,writeHistory,index); },remaining); return; }
        } catch (error) {
          if (session.mode === 'operations' && token === epoch && generation === readGeneration && !disposed && !pendingRoute() && (demoSession === session || pausedPresentation === session) && !session.nextOperationOpening) {
            if (!await operationGate(session,token)) return;
            session.preparing = null; return openPresentationCase(session,writeHistory,index);
          }
          if (demoSession === session && token === epoch && !disposed && !pendingRoute()) presentationFailed(session,`Next case ${featuredCase(id)?.label || id} is unavailable: ${error.message} The last verified case remains visible.`);
          return;
        }
        finally { if (session.preparing === token) session.preparing = null; }
      }
      if (session.verifiedOpening?.operationPreparation?.recorded) { session.operations = 'recorded'; session.useRecorded = true; }
      if (session.nextOperationOpening?.id === id) session.nextOperationOpening = null;
      session.index = index; session.claimId = id; session.startAttempted = false; session.storyPhase = 'work';
      if (session.cases && tour?.cases === session.cases) tour.index = index;
      await openClaim(id,writeHistory,{mode:session.mode === 'operations' ? 'replay' : session.mode,collection:session.collection || 'reference',operations:session.operations,through:0,detail:'step',demo:true});
      if (demoSession !== session || !current || disposed || pendingRoute()) return;
      if (['replay','operations'].includes(session.mode)) {
        if (!replayRecord.current_revision) { stopPresentation(); renderClaim(); notice('This original case has no recorded execution to replay. Its original sources remain available.'); return; }
      } else { resumeLivePresentation(); advanceLivePresentation(); }
    }
    function presentationOpening(session,id) {
      if (session.mode === 'operations') return nextOperationOpening(session,id);
      const token = epoch, generation = readGeneration, identity = `opening:${id}:0`;
      if (replayPrefixes.has(identity)) return replayPrefixes.get(identity);
      const promise = (async () => {
        const response = await request(`/claims/${key(id)}/replay?through_seq=0`), incoming = readReplay(response,id,0);
        const head = {claimId:id,revision:incoming.replay.current_revision,state_sha256:incoming.replay.current_state_sha256,event_sha256:incoming.replay.current_event_sha256};
        if (!head.revision) throw new Error('No recorded execution is available for this original case.');
        const verification = {replayHead:head,replayStart:response.replay_start};
        const referenceReady = session.collection !== 'selected' && !doc.hidden && await verifyReferenceHead(verification);
        if (session.collection !== 'selected' && !doc.hidden && !referenceReady) throw new Error('No completed recorded reference assessment is available.');
        if (disposed || token !== epoch || generation !== readGeneration || demoSession !== session || pendingRoute()) throw new Error('The presentation changed while verifying the next case.');
        return {claimId:id,generation,response,head,referenceReady,verifiedReplayStart:verification.verifiedReplayStart,verifiedJournal:verification.verifiedJournal,referenceAsOf:verification.referenceAsOf,operationBinding:verification.operationBinding,plannedProcess:verification.plannedProcess};
      })();
      replayPrefixes.set(identity,promise);
      while (replayPrefixes.size > 2) replayPrefixes.delete(replayPrefixes.keys().next().value);
      promise.catch(() => {});
      return promise;
    }
    function checkedReplayHead(incoming, session) {
      const head = session.replayHead, record = incoming.replay;
      if (!head || incoming.state.claim_id !== head.claimId || record.current_revision !== head.revision || record.current_state_sha256 !== head.state_sha256 || record.current_event_sha256 !== head.event_sha256) throw new Error('The recorded replay head changed. Reopen to verify its newest history.');
    }
    async function loadRecordedPacket() {
      const descriptor = options.recordedPacket;
      const eligible = () => !disposed && !doc.hidden && (view === 'work' || view === 'claim' && ((demoSession || pausedPresentation)?.mode === 'operations' || publicReadOnly && presentationMode === 'replay' && openingPreferences.operations === 'recorded' && REFERENCE_DEMO_CASES.some(row => row.claim_id === openingId)));
      if (!descriptor || !eligible()) return false;
      let verification;
      try {
        await new Promise(resolve => root.setTimeout(resolve,0));
        if (!eligible()) return false;
        const url = new URL(descriptor.url,root.location?.href || 'http://localhost/');
        if (url.origin !== new URL(root.location?.href || 'http://localhost/').origin || url.username || url.password || !Number.isSafeInteger(descriptor.bytes) || descriptor.bytes < 1 || descriptor.bytes > RECORDED_PACKET_BYTES) return false;
        packetLoadController = new AbortController();
        const response = await fetcher(url.href,{method:'GET',cache:'force-cache',credentials:'same-origin',redirect:'error',signal:packetLoadController.signal});
        if (!response.ok || !response.body?.getReader) return false;
        const reader = response.body.getReader(), chunks = []; let length = 0;
        const cancel = () => { reader.cancel().catch(() => {}); }; packetLoadController.signal.addEventListener('abort',cancel,{once:true});
        try { while (!packetLoadController.signal.aborted) { const chunk = await reader.read(); if (chunk.done) break; length += chunk.value.byteLength; if (length > descriptor.bytes) throw new Error('Recorded packet asset exceeds its bound.'); chunks.push(chunk.value); } }
        finally { packetLoadController.signal.removeEventListener('abort',cancel); await reader.cancel().catch(() => {}); reader.releaseLock?.(); }
        if (!eligible() || packetLoadController.signal.aborted) return false;
        const bytes = new Uint8Array(length); let offset = 0; for (const chunk of chunks) { bytes.set(chunk,offset); offset+=chunk.byteLength; }
        if (length !== descriptor.bytes) throw new Error('Recorded packet acquisition is incomplete.');
        verification = {controller:packetLoadController,promise:checkedRecordedPacket(bytes,descriptor,options.allowNativeRecordedPacket === true)}; packetVerification=verification;
        const packet = await verification.promise;
        if (!eligible() || packetLoadController.signal.aborted) return false;
        recordedPacket = packet; return true;
      } catch (_) { return false; }
      finally { if (packetVerification === verification) packetVerification=null; }
    }
    async function loadSavedSnapshot() {
      const descriptor = options.savedSnapshot, generation = readGeneration;
      if (!descriptor || !publicReadOnly && options.allowNativeSavedSnapshot !== true || disposed || doc.hidden || view !== 'work' && !(view === 'claim' && presentationMode === 'saved' && openingId === descriptor.claim_id)) return false;
      const eligible = () => !disposed && !doc.hidden && generation === readGeneration && !savedSnapshotController?.signal.aborted && (view === 'work' || view === 'claim' && presentationMode === 'saved' && openingId === descriptor.claim_id);
      let timeout;
      try {
        const url = new URL(descriptor.url,root.location?.href || 'http://localhost/');
        if (url.origin !== new URL(root.location?.href || 'http://localhost/').origin || url.username || url.password || !Number.isSafeInteger(descriptor.bytes) || descriptor.bytes < 1 || descriptor.bytes > SAVED_SNAPSHOT_BYTES) return false;
        savedSnapshotController = new AbortController();
        timeout = root.setTimeout(() => savedSnapshotController.abort(),15000);
        const response = await fetcher(url.href,{method:'GET',cache:'force-cache',credentials:'same-origin',redirect:'error',signal:savedSnapshotController.signal});
        if (!response.ok || !response.body?.getReader) return false;
        const reader = response.body.getReader(), chunks = []; let length = 0;
        const cancel = () => { reader.cancel().catch(() => {}); }; savedSnapshotController.signal.addEventListener('abort',cancel,{once:true});
        try { while (!savedSnapshotController.signal.aborted) { const chunk = await reader.read(); if (chunk.done) break; length+=chunk.value.byteLength; if (length > descriptor.bytes) throw new Error('The saved snapshot asset exceeds its bound.'); chunks.push(chunk.value); } }
        finally { savedSnapshotController.signal.removeEventListener('abort',cancel); await reader.cancel().catch(() => {}); reader.releaseLock?.(); }
        if (!eligible() || length !== descriptor.bytes) return false;
        const bytes = new Uint8Array(length); let offset = 0; for (const chunk of chunks) { bytes.set(chunk,offset); offset+=chunk.byteLength; }
        const snapshot = await checkedSavedSnapshotAsset(bytes,descriptor,options.allowNativeSavedSnapshot === true);
        if (!eligible()) return false;
        rememberSnapshot(descriptor.claim_id,snapshot,true); return snapshots.has(descriptor.claim_id);
      } catch (_) { return false; }
      finally { root.clearTimeout(timeout); }
    }
    function operationRequest(prepared, path) {
      const identity = `${readGeneration}:${path}`, prior = readOwners.get(identity), promise = request(path), owner = readOwners.get(identity);
      if (owner && owner !== prior) prepared.readControllers.add(owner.controller);
      return promise;
    }
    function cancelPreparedOperationReads(prepared) {
      prepared.controller.abort(); for (const controller of prepared.readControllers) controller.abort();
    }
    async function chooseRecordedOpening(packet, session, id, token, ownership = null) {
      let prepared = session.operationPreparation; const choice = new AbortController(); session.operationChoiceController = choice;
      const active = () => !choice.signal.aborted && (ownership ? ownership.active() : !disposed && token === epoch && !pendingRoute() && openingId === id);
      const openingResult = (response, head, verification) => ({claimId:id,generation:readGeneration,response,head,referenceReady:true,verifiedHeadState:verification.verifiedHeadState,verifiedReplayStart:verification.verifiedReplayStart,verifiedJournal:verification.verifiedJournal,referenceAsOf:verification.referenceAsOf,operationBinding:verification.operationBinding,plannedProcess:verification.plannedProcess});
      let packetOpening = null, observedLiveHead = null, packetSettled = false, preferenceElapsed = false;
      const cancelled = new Promise((_resolve,reject) => choice.signal.addEventListener('abort',() => reject(new Error('The selected opening changed.')),{once:true}));
      cancelled.catch(() => {});
      const packetCandidate = (async () => {
        const verified = packet.promise ? await packet.promise : packet;
        if (!active() || packet.controller?.signal.aborted) return;
        const decoded = await decodeRecordedSession(verified,id,choice.signal), incoming = readReplay(decoded.opening,id,0), head = decoded.head;
        checkedReplayHead(incoming,{replayHead:head});
        const full = await checkedAtomicOperationHead(decoded.head_snapshot,head,incoming.replay.replay_start,incoming.state), plannedProcess = await plannedOperationProcess(full.state), start = checkedReferenceReplayStart(incoming.replay.replay_start,full);
        const operationBinding = {source_roster_sha256:full.state.source_roster_sha256,rule_set_sha256:referenceExecution(full.state)?.rule_set_sha256};
        const newline = decoded.operations.indexOf(10); if (newline < 0 || newline > OPERATION_FRAME_BYTES) throw new Error('The recorded packet has no bounded operation binding.');
        checkedOperationBinding(JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(decoded.operations.subarray(0,newline))),{...head,...operationBinding},start);
        if (active()) packetOpening = {opening:openingResult(decoded.opening,head,{verifiedHeadState:full.state,verifiedReplayStart:start,verifiedJournal:full.accepted.events,referenceAsOf:referenceExecution(full.state)?.as_of,operationBinding,plannedProcess}),bytes:decoded.operations};
      })(); packetCandidate.then(() => { packetSettled = true; },() => { packetSettled = true; });
      if (!prepared) {
        let timer;
        try { await Promise.race([cancelled,packetCandidate.catch(() => {}),new Promise(resolve => { timer=root.setTimeout(resolve,OPERATION_CHOICE_GRACE_MS); })]); }
        finally { root.clearTimeout(timer); }
        if (!active()) throw new Error('The selected opening changed.');
        if (packetOpening) return selectRecorded();
        if (packetSettled) { choice.abort(); return null; }
        // Explicit Recorded keeps the pending packet eligible while its existing
        // owned recorded endpoint reads become the other candidate.
        prepared = prepareOperationReads(session,id,token); preferenceElapsed = true;
        if (!prepared) { choice.abort(); return null; }
      }
      const liveOpening = operationRequest(prepared,`/claims/${key(id)}/replay?through_seq=0`);
      const liveCandidate = (async () => {
        const response = await liveOpening, incoming = readReplay(response,id,0), head = {claimId:id,revision:incoming.replay.current_revision,state_sha256:incoming.replay.current_state_sha256,event_sha256:incoming.replay.current_event_sha256};
        observedLiveHead = head;
        const verification = {replayHead:head,replayStart:incoming.replay.replay_start,operationOpeningAnchor:{state:incoming.state}};
        if (!await verifyReferenceHead(verification,prepared) || !verification.verifiedReplayStart) throw new Error('The live reference opening is incomplete.');
        const delivery = await prepared.delivery, first = await delivery?.buffer?.first;
        if (!first) throw new Error('The live operation binding is unavailable.');
        checkedOperationBinding(first,{...head,...verification.operationBinding},verification.verifiedReplayStart);
        if (!active() || prepared.controller.signal.aborted) throw new Error('The selected opening changed.');
        return openingResult(response,head,verification);
      })(); liveCandidate.catch(() => {});
      let timer, winner = null;
      if (!preferenceElapsed) {
        try { winner = await Promise.race([cancelled,liveCandidate.catch(() => new Promise(() => {})),new Promise(resolve => { timer=root.setTimeout(() => resolve(null),OPERATION_CHOICE_GRACE_MS); })]); }
        finally { root.clearTimeout(timer); }
      }
      if (!active()) throw new Error('The selected opening changed.');
      if (winner) { choice.abort(); return winner; }
      if (packetOpening && observedLiveHead && canonicalJSON(packetOpening.opening.head) !== canonicalJSON(observedLiveHead)) packetOpening = null;
      if (!packetOpening) {
        try {
          // The grace interval prefers complete Live, not an unready transport.
          // Until one session commits, either fully checked candidate may win.
          const ready = await Promise.race([cancelled,Promise.any([
            liveCandidate.then(opening => ({opening})),
            packetCandidate.then(() => {
              if (!packetOpening || observedLiveHead && canonicalJSON(packetOpening.opening.head) !== canonicalJSON(observedLiveHead)) throw new Error('No matching verified recorded opening is available.');
              return {recorded:true};
            })
          ])]);
          if (!active()) throw new Error('The selected opening changed.');
          if (ready.opening) { choice.abort(); return ready.opening; }
          // Live metadata may arrive while the readiness promises settle.
          // Recheck immediately before committing the recorded presentation.
          if (observedLiveHead && canonicalJSON(packetOpening.opening.head) !== canonicalJSON(observedLiveHead)) {
            const opening = await Promise.race([cancelled,liveCandidate]);
            if (!active()) throw new Error('The selected opening changed.');
            choice.abort(); return opening;
          }
          return selectRecorded();
        } catch (error) {
          if (!active()) throw error;
          // Both candidates were unusable; preserve the native endpoint fallback.
          choice.abort(); const response = await liveOpening, incoming = readReplay(response,id,0);
          return {claimId:id,generation:readGeneration,response,head:{claimId:id,revision:incoming.replay.current_revision,state_sha256:incoming.replay.current_state_sha256,event_sha256:incoming.replay.current_event_sha256},referenceReady:false};
        }
      }
      return selectRecorded();
      function selectRecorded() {
        if (prepared) cancelPreparedOperationReads(prepared);
        session.operations = 'recorded'; session.useRecorded = true; session.recorded = true;
        if (!ownership) { openingPreferences.operations = 'recorded'; if (operationTrace) operationTrace.recorded = true; }
        const controller = new AbortController(); controllers.add(controller); controller.signal.addEventListener('abort',() => controllers.delete(controller),{once:true}); session.operationController = controller;
        const response = new root.Response(packetOpening.bytes,{headers:{'Content-Type':'application/x-ndjson'}});
        session.operationPreparation = {claimId:id,controller,token,recorded:true,readControllers:new Set(),delivery:Promise.resolve({response,buffer:bufferedOperations(response,controller.signal)})};
        const fragment = claimFragment(id,{...openingPreferences,operations:'recorded'});
        if (!ownership && root.history?.replaceState) { root.history.replaceState(null,'',root.location.pathname+root.location.search+fragment); routedFragment=fragment; }
        const label = host.querySelector('.au-reference-mode'), chosen = packetOpening.opening;
        if (!ownership && label) label.textContent = language.modeLine({revision:chosen.head.revision,presentation:'replay',provenance:historyProvenance(chosen.verifiedHeadState),origin:'featured',recordedAt:[...list(chosen.verifiedJournal)].reverse().find(event => event.timestamp)?.timestamp,readOnly:publicReadOnly});
        choice.abort(); return packetOpening.opening;
      }
    }
    async function verifyReferenceHead(session, prepared = null) {
      const head = session.replayHead;
      if (!head?.revision) return false;
      let incoming;
      if (prepared?.revision === head.revision) { try { incoming = readReplay(await prepared.head,head.claimId,head.revision); checkedReplayHead(incoming,session); } catch (_) { incoming = null; } }
      if (prepared?.snapshot) { try { incoming = await checkedAtomicOperationHead(await prepared.snapshot,head,session.replayStart,session.operationOpeningAnchor?.state); } catch (_) { incoming = null; } }
      if (!incoming) {
        if (prepared && (prepared.controller.signal.aborted || disposed || prepared.token !== epoch || pendingRoute())) throw new Error('The selected operation opening was cancelled.');
        const path = `/claims/${key(head.claimId)}/replay?through_seq=${head.revision}`;
        incoming = readReplay(await (prepared ? operationRequest(prepared,path) : request(path)),head.claimId,head.revision);
        checkedReplayHead(incoming,session);
      }
      // Admission of playback does not paint the head or borrow its context
      // for an earlier prefix. The displayed prefix keeps its own identity.
      session.verifiedReplayStart = checkedReferenceReplayStart(session.replayStart,incoming);
      session.plannedProcess = await plannedOperationProcess(incoming.state);
      if (session.releasePlan) {
        session.releaseMatched = await releaseHeadMatches(session.releasePlan,incoming.state,session.plannedProcess);
        // Mismatch retires release context; this separately verified head
        // supplies its own plan. Release data never acquires a head identity.
        if (operationTrace?.releasePlan === session.releasePlan) { operationTrace.releasePlan = null; operationTrace.releaseMatched = session.releaseMatched; }
        session.releasePlan = null;
      }
      session.verifiedJournal = incoming.accepted.events; session.referenceAsOf = referenceExecution(incoming.state)?.as_of; session.operationBinding = {source_roster_sha256:incoming.state.source_roster_sha256,rule_set_sha256:referenceExecution(incoming.state)?.rule_set_sha256};
      session.verifiedHeadState = incoming.state;
      return Boolean(referenceExecution(incoming.state) && incoming.state.outcome?.assessment_status === 'complete' && replayCanAdvance(incoming.state));
    }
    function replayPrefix(id, through, session) {
      const identity = `${id}:${through}:${session.replayHead?.state_sha256}`, token = epoch, generation = readGeneration;
      if (replayPrefixes.has(identity)) return replayPrefixes.get(identity);
      const promise = request(`/claims/${key(id)}/replay?through_seq=${through}`).then(response => {
        const incoming = readReplay(response,id,through); checkedReplayHead(incoming,session);
        if (disposed || token !== epoch || generation !== readGeneration || demoSession !== session) throw new Error('The presentation changed while verifying its prefix.');
        return response;
      });
      replayPrefixes.set(identity,promise);
      while (replayPrefixes.size > 2) replayPrefixes.delete(replayPrefixes.keys().next().value);
      // Prefetch failures remain on their exact promise and stop playback when
      // consumed, rather than becoming an unhandled rejection or a hidden retry.
      promise.catch(() => {});
      return promise;
    }
    function prefetchReplay(session) {
      if (demoSession !== session || session.failure || session.preparing || disposed || doc.hidden || dialog.open || recordDialog.open || inspectionHold || !replayRecord || session.replayHead?.claimId !== current?.claim_id) return;
      for (let through = replayRecord.through_seq + 1; through <= Math.min(replayRecord.current_revision,replayRecord.through_seq + 2); through++) replayPrefix(current.claim_id,through,session);
    }
    function replayPacing(event, session) {
      return replayContentPacing(event,session?.contentChanges);
    }
    function replayActive(session, token) {
      return demoSession === session && !disposed && token === epoch && !pendingRoute() && presentationMode === 'replay' && view === 'claim' && current && replayRecord;
    }
    function consumeReplay(session, token, through, response) {
      demoTimer = null;
      if (!replayActive(session,token) || doc.hidden || dialog.open || recordDialog.open || inspectionHold) return;
      try {
        // Verify again on consumption, including every retained earlier event.
        const incoming = readReplay(response,current.claim_id,through); checkedReplayHead(incoming,session);
        if (through !== cursor + 1) throw new Error('The recorded replay prefix is out of sequence.');
        for (const previous of history) if (canonicalJSON(incoming.accepted.events.find(event => event.seq === previous.seq)) !== canonicalJSON(previous)) throw new Error('An earlier accepted replay event changed identity.');
        const accepted = acceptEvents(cursor,{...incoming.replay,current_revision:incoming.state.revision,current_state_sha256:incoming.state.state_sha256,events:incoming.accepted.events.filter(event => event.seq > cursor)},incoming.state);
        const newest = accepted.events.at(-1), previousHash = current.last_event_sha256;
        if (newest && Object.prototype.hasOwnProperty.call(newest,'previous_event_sha256') && newest.previous_event_sha256 !== previousHash || newest && Object.prototype.hasOwnProperty.call(newest,'prev_event_sha256') && newest.prev_event_sha256 !== previousHash) throw new Error('The replay journal chain no longer follows the accepted prefix.');
        const previousState = current, changes = transitionPlan(current,incoming.state,accepted,history);
        acceptPublicationAttention(previousState,incoming.state,accepted,changes);
        replayPrefixes.delete(`${current.claim_id}:${through}:${session.replayHead.state_sha256}`);
        current = incoming.state; projection = incoming.projection; cursor = incoming.accepted.cursor; history = incoming.accepted.events; replayRecord = incoming.replay;
        const entered = demoSession && enteredRequirementContext(previousState,current);
        const followed = demoSession && [...accepted.events].reverse().find(event => consequentialEventNode(previousState,current,event));
        selected = preferredNode(current,entered?.node || (followed ? consequentialEventNode(previousState,current,followed) : selected),history);
        if (entered) { evidenceContext = evidenceSelection(current,selected,entered); detail = 'step'; }
        else if (followed) { evidenceContext = acceptedEventContext(current,followed,selected); detail = 'step'; }
        // Knowledge changes stay in the accepted investigation composition.
        evidenceContext = evidenceSelection(current,selected,evidenceContext);
        const fragment = selectedClaimFragment();
        if (root.history?.replaceState) { root.history.replaceState(null,'',root.location.pathname + root.location.search + fragment); routedFragment = fragment; }
        renderClaim(changes); session.displayedAt = Date.now(); session.motionDuration = motion?.duration || 0; session.contentChanges = changes; prefetchReplay(session); replayTick(session,token);
      } catch (error) { if (replayActive(session,token)) { stopPresentation(); renderClaim(); notice(`Verified replay stopped: ${error.message}`,true); } }
    }
    async function replayTick(session, token) {
      if (demoTimer) return;
      if (!replayActive(session,token) || doc.hidden || dialog.open || recordDialog.open || inspectionHold || session.preparing) return;
      if (session.failure) { presentationFailed(session,session.failure); return; }
      if (replayRecord.through_seq >= replayRecord.current_revision) {
        if (!replayCanAdvance(current)) { stopPresentation(); renderClaim(); notice('This recorded investigation has no settled operational outcome. Replay stopped at its saved head.',true); return; }
        const next = sessionCases(session)[session.index+1];
        if (next) presentationOpening(session,next.claim_id);
        const remaining = session.mode === 'operations' ? 0 : Math.max(0,4000 - (Date.now() - session.displayedAt));
        demoTimer = root.setTimeout(() => { demoTimer = null; if (!replayActive(session,token) || doc.hidden || dialog.open) return; openPresentationCase(session,true,session.index+1); },remaining);
        return;
      }
      const id = current.claim_id, through = replayRecord.through_seq + 1;
      session.preparing = token;
      try {
        const response = await replayPrefix(id,through,session);
        if (!replayActive(session,token) || doc.hidden || dialog.open || recordDialog.open || inspectionHold) return;
        const remaining = Math.max(0,Math.max(replayPacing(history.at(-1),session),session.motionDuration || 0) - (Date.now() - session.displayedAt));
        demoTimer = root.setTimeout(() => consumeReplay(session,token,through,response),remaining);
      } catch (error) { if (replayActive(session,token)) presentationFailed(session,`Verified replay stopped: ${error.message}`); }
      finally { if (session.preparing === token) session.preparing = null; }
    }
    function resumeLivePresentation() {
      const session = demoSession;
      if (!session || session.mode !== 'live' || session.epoch !== epoch || disposed || pendingRoute() || doc.hidden || dialog.open || recordDialog.open || view !== 'claim' || presentationMode !== 'live' || !openingPreferences.demo || !current || !freshClaim || current.claim_id !== session.claimId || sessionCases(session)[session.index]?.claim_id !== session.claimId || current.revision !== 0 || busy || pendingStart || session.startAttempted || !canStartHere()) return;
      // Play authorizes one original Start after a verified opening. An uncertain
      // admission retains its exact request for explicit operator recovery.
      session.startAttempted = true;
      startOriginal(host.querySelector('[data-au-start]'));
    }
    function advanceLivePresentation() {
      const session = demoSession;
      if (!session || session.mode !== 'live' || !current || busy || pendingStart || active(current.status) || current.revision === 0 || demoTimer) return;
      if (['model_unavailable','call_limit_reached','cost_limit_reached'].includes(current.deferral?.code)) { stopPresentation(); renderClaim(); notice(current.deferral.reason || 'Live execution is unavailable.',true); return; }
      const token = epoch, id = current.claim_id;
      demoTimer = root.setTimeout(() => livePresentationTick(session,token,id),3200);
    }
    function livePresentationTick(session, token, id) {
      demoTimer = null;
      if (demoSession !== session || disposed || token !== epoch || pendingRoute() || session.epoch !== token || view !== 'claim' || presentationMode !== 'live' || current?.claim_id !== id || session.claimId !== id || sessionCases(session)[session.index]?.claim_id !== id || busy || pendingStart || active(current.status)) return;
      if (doc.hidden || dialog.open) { demoTimer = root.setTimeout(() => livePresentationTick(session,token,id),1600); return; }
      openPresentationCase(session,true,session.index+1);
    }
    async function startOriginal(target) {
      if (publicReadOnly || busy || pendingRoute() || !freshClaim || !status || !writable(status) || !current || !intakeEligible(projection) || REFERENCE_DEMO_CASES.some(row => row.claim_id === current.claim_id) || current.revision !== 0 && !pendingStart || presentationMode === 'replay' || !canStartHere() && !pendingStart) return;
      const token = epoch, id = current.claim_id;
      pendingStart ||= {claimId:id,body:{expected_revision:current.revision,expected_state_sha256:current.state_sha256,idempotency_key:`browser.${root.crypto.randomUUID()}`}};
      starts.set(id,pendingStart); busy = true;
      try {
        invalidateReads(id);
        readState(await request(`/claims/${key(id)}/start`,{method:'POST',body:JSON.stringify(pendingStart.body)}),id);
        starts.delete(id); pendingStart = null;
        if (!disposed && token === epoch && !pendingRoute()) { presentationMode = 'live'; await loadOpenedClaim(id,token); }
      } catch (error) {
        if (error.status && error.status < 500) { starts.delete(id); pendingStart = null; }
        if (!disposed && token === epoch && !pendingRoute()) await loadOpenedClaim(id,token);
        if (!disposed && token === epoch) notice(`${error.message}${pendingStart ? ' Response unconfirmed; retry uses the same request.' : ''}`,true);
      } finally { busy = false; synchronizeAuthority(); routeChanged(); }
    }
    async function showWork(writeHistory = true, fresh = false) {
      // Only a direct return keeps the reader's place: from the case opened
      // from this list (its row is the opener), or Cancel from a New case
      // opened from this list. Any other arrival starts at the top.
      const from = view, caseReturn = !fresh && from === 'claim' && Boolean(collection.opener) && openingId === collection.opener, intakeReturn = !fresh && from === 'intake' && collection.intakeFromWork === true;
      if (!caseReturn) collection.opener = null;
      collection.intakeFromWork = false;
      stopPresentation(); leaveView(); route(collectionFragment(),writeHistory);
      epoch++; const token = epoch; cancelPoll(); setView('work'); nav('work'); current = null; notice('');
      if (fresh) collection.scrollTop = undefined;
      const options = collectionView();
      host.innerHTML = collectionMarkup(claims,options); interact(host);
      // The list shows rows only from a loaded catalog; refreshes compare against what is shown.
      const output = host.querySelector('[data-au-claims]');
      if (output) { const rows = !claimsLoaded ? '' : collection.scope === 'added' && !collectionRows(claims,'added').length ? addedEmptyMarkup(publicReadOnly) : claimsMarkup(claims,options); output.innerHTML = rows; output.auRows = rows; }
      // Returning from the opened case keeps the reader's place and focuses
      // that row (or the list heading when the row is no longer shown);
      // Cancel from New case keeps the place and focuses New case.
      const place = collection.scrollTop !== undefined && (caseReturn || intakeReturn);
      if (place) restoreCollectionPlace();
      routeTitle(collectionTitle());
      if (place && caseReturn) { if (!returnToOpener() && claimsLoaded) { collection.opener = null; focusTitle(); } /* else the row receives focus once rows arrive */ }
      else if (place && intakeReturn) { if (!doc.hidden) container.querySelector('.au-header-new')?.focus?.({preventScroll:true}); }
      else { collection.opener = null; routeSettled('work',collectionTitle()); }
      if (searchTerms(collection.search).length) queueCollectionSearch(true);
      const results = await Promise.allSettled([serviceStatus(token),loadClaims(token)]);
      if (!disposed && token === epoch) for (const result of results) if (result.status === 'rejected') notice(result.reason.message,true);
    }
    async function showIntake(writeHistory = true) {
      if (publicReadOnly) return showWork(writeHistory);
      if (view === 'intake' && host.querySelector('[data-au-intake]')) { route('#autonomous/new',writeHistory); return; }
      collection.intakeFromWork = view === 'work';
      stopPresentation(); leaveView(); route('#autonomous/new',writeHistory);
      epoch++; const token = epoch; cancelPoll(); setView('intake'); nav('intake'); current = null; notice('');
      host.innerHTML = `<div class="au-intake-layout au-identity-intake"><section><p class="au-eyebrow">New case</p><h1 class="au-page-heading" tabindex="-1">Start with the source.</h1><p class="au-lead">Add the original message and files. CasePath reads them and records what it finds.</p><p class="au-meta" data-au-service>Checking service availability…</p><form class="au-intake" data-au-intake><div class="au-examples" data-au-examples hidden><label for="auExample">Try a fictional case</label><select id="auExample" data-au-example><option value="">Choose a fictional example</option></select></div><label for="auTitle">Case title</label><input id="auTitle" name="title" required maxlength="300" autocomplete="off" placeholder="A short name for this case"><label for="auMessage">Incoming message</label><textarea id="auMessage" name="message" required maxlength="100000" rows="7" placeholder="Paste the original message"></textarea><label class="au-upload" for="auFiles">Supporting files <span>Optional · original files stay available for inspection</span></label><input id="auFiles" name="files" type="file" multiple><div class="au-intake-controls"><button class="au-primary" type="submit">Start checking <span aria-hidden="true">↗</span></button><button type="button" class="au-secondary" data-au-nav="work">Cancel</button></div><p class="au-form-status"></p></form></section></div>`;
      if (intakeForm) host.querySelector('[data-au-intake]')?.replaceWith?.(intakeForm);
      else intakeForm = host.querySelector('[data-au-intake]');
      if (pendingIntake && intakeForm) {
        intakeForm.elements.title.value = pendingIntake.body.title; intakeForm.elements.message.value = pendingIntake.body.message;
        lockForm(intakeForm,true,true); intakeForm.querySelector('.au-form-status').textContent = 'The prior response was not confirmed. Retry sends the same saved intake request.';
      } else if (!busy) idleIntakeSubmit(intakeForm);
      loadExamples(token); interact(host); routeSettled('intake','New case');
      try { await serviceStatus(token,true); } catch (error) { if (!disposed && token === epoch) notice(error.message,true); }
    }
    async function loadExamples(token) {
      const meta = doc.querySelector?.('meta[name="casepath-autonomous-demo-packets"]')?.content;
      if (!meta || !root.location) return;
      const controller = new AbortController(); controllers.add(controller);
      const timeout = root.setTimeout(() => controller.abort(new DOMException('No response within 15 seconds. Try again.','TimeoutError')), 15000);
      try {
        if (!examples) {
          const url = demoAssetURL(meta, root.location);
          const response = await fetcher(url.href, {signal:controller.signal,cache:'no-store',credentials:'same-origin',redirect:'error'});
          if (!response.ok) throw new Error('The fictional packets could not be loaded.');
          examples = await checkedExamples(await response.arrayBuffer(), url.searchParams.get('sha256'));
        }
        if (disposed || token !== epoch || view !== 'intake') return;
        const wrapper = host.querySelector('[data-au-examples]'), select = host.querySelector('[data-au-example]');
        if (!wrapper || !select) return;
        const chosen = select.value;
        select.innerHTML = '<option value="">Choose a fictional example</option>' + examples.map((packet,index)=>`<option value="${index}">${h(packet.title)}</option>`).join('');
        if (/^\d+$/.test(chosen) && examples[Number(chosen)]) select.value = chosen;
        select.disabled = busy || Boolean(pendingIntake); wrapper.hidden = false;
      } catch (error) { if (!disposed && token === epoch) notice(`Fictional examples unavailable: ${error.message}`,true); }
      finally { root.clearTimeout(timeout); controllers.delete(controller); }
    }
    function change(event) {
      if (event.target.hasAttribute?.('data-au-operation-scrub')) return;
      const select = event.target;
      if (!select.matches?.('[data-au-example]') || view !== 'intake' || busy || pendingIntake || select.disabled || !/^\d+$/.test(select.value)) return;
      const packet = examples?.[Number(select.value)], form = host.querySelector('[data-au-intake]');
      if (!packet || !form) return;
      try { prefillExample(form,packet); form.querySelector('.au-form-status').textContent = 'Fictional example loaded. Start checking when ready.'; }
      catch (error) { form.querySelector('.au-form-status').textContent = error.message; }
    }
    function synchronizeKnowledgeRead(value = host.getAttribute?.('data-au-read-state') || 'verified') {
      const retry=host.querySelector('[data-au-knowledge-retry]');if(retry)retry.hidden=value!=='failed';
      host.setAttribute?.('data-au-read-state',value);
      const label = host.querySelector('[data-au-knowledge-read-label]');
      if (label) label.textContent = value === 'verified' ? '' : value === 'failed' ? 'Saved copy · refresh failed' : 'Saved copy · refreshing';
    }
    function cancelLearning() {
      if (learningTimer) root.clearTimeout(learningTimer); learningTimer = null;
      if (learningState) learningState.playing = false;
    }
    function learningRoute(replace = true) {
      if (!learningState || !root.history?.replaceState || !root.location || view !== 'knowledge') return;
      const event=learningState.model.events[learningState.index], item=event?.versionRecord || event?.item;
      if (!event) return;
      const params=new URLSearchParams([['view','learning']]);
      if(item?.knowledge_id && item?.version) { params.set('knowledge',item.knowledge_id);params.set('version',item.version);params.set('sha256',item.knowledge_sha256 || '');const definition=item.definition_sha256 || item.qualification?.definition_sha256;if(definition)params.set('definition',definition); }
      if(knowledgePin?.claim_id)params.set('claim',knowledgePin.claim_id);
      params.set('event',event.id);params.set('stage',String(learningState.stage));params.set('facet',knowledgeFacet);if(learningState.complete)params.set('complete','1');
      const fragment='#autonomous/knowledge?'+params;
      root.history[replace?'replaceState':'pushState'](null,'',root.location.pathname+root.location.search+fragment);routedFragment=fragment;
    }
    function synchronizeLearning(announce = false) {
      if (!learningState || view !== 'knowledge') return;
      const {model,index,stage,playing}=learningState, event=model.events[index], shell=host.querySelector('[data-au-learning]'), focus=host.querySelector('[data-au-learning-focus]');
      if(shell) { shell.dataset.auLearningEventId=event?.id || '';shell.dataset.auLearningKind=event?.kind || '';shell.dataset.auLearningPosition=String(index);shell.dataset.auLearningPlaying=String(playing);shell.dataset.auLearningSettled=String(stage===10&&!playing);shell.dataset.auLearningComplete=String(Boolean(learningState.complete)); }
      if(focus) { focus.dataset.auLearningStage=String(stage);for(const node of focus.querySelectorAll('[data-au-learning-reveal]')) { const waiting=playing&&stage<Number(node.dataset.auLearningReveal);node.setAttribute('data-au-learning-waiting',String(waiting));node.setAttribute('aria-hidden',String(waiting));node.inert=waiting; }for(const proof of focus.querySelectorAll('[data-au-learning-proof]')){if(playing)proof.open=stage>=3;}for(const node of focus.querySelectorAll('[data-au-learning-check]')) node.setAttribute('data-au-check-shown',String(stage>=3+Number(node.dataset.auLearningCheck))); }
      const now=host.querySelector('.au-now');if(now && now.dataset.auNowId!==(event?.id || ''))now.outerHTML=knowledgeNowMarkup(model,event);
      const learningCaption=host.querySelector('[data-au-learning-label]');if(learningCaption)learningCaption.textContent=learningLabel(model,claims,playing);
      const play=host.querySelector('[data-au-learning-play]');if(play){play.textContent=playing?'Pause':'Play';play.setAttribute('aria-label',playing?'Pause':'Play');play.setAttribute('aria-pressed',String(playing));}
      const range=host.querySelector('[data-au-learning-scrub]');if(range){range.value=String(learningState.complete?Math.max(0,model.events.length-1):index);range.setAttribute('aria-valuetext',learningState.complete?`Replay finished. ${model.events.length} of ${model.events.length} recorded events.`:event?`${index+1} of ${model.events.length}: ${learningEventLabel(event)} · ${learningTime(event)}`:model.events.length?`Exact version unavailable; ${model.events.length} recorded events available`:'No recorded events');}
      const position=host.querySelector('[data-au-learning-position-label]');if(position)position.textContent=learningState.complete?`Replay finished · ${model.events.length} / ${model.events.length}`:event?`${index+1} / ${model.events.length} · ${learningEventLabel(event)}`:model.events.length?'Exact version unavailable':'No recorded events';
      for(const node of host.querySelectorAll('[data-au-learning-event]'))node.setAttribute('aria-current',Number(node.dataset.auLearningEvent)===index?'step':'false');
      if(announce && event && learningState.announced!==event.id) { const live=host.querySelector('[data-au-learning-announcement]');if(live)live.textContent='';const now=host.querySelector('.au-now'),role=now?.querySelector('[data-au-role]')?.textContent?.trim(),copy=now?.querySelector('[data-au-now-copy]')?.textContent,result=now?.querySelector('[data-au-now-result]')?.textContent;const family=procedureLabel(event.versionRecord || event.item),sourceTitle=event.kind==='knowledge.used'?event.claim_title:event.source_claim_title || event.claim_title,title=plain(sourceTitle,'The case title is not recorded'),context=sourceTitle?`${event.kind==='knowledge.used'?'Receiving case':'Source case'}: ${title.split(/\s+/u).length<=17?title:'the recorded case'}.`:'';announceRecorded([`${family}.`,context,`${role || 'Memory'} ${copy || learningEventLabel(event)}`,result].filter(Boolean).join(' '));learningState.announced=event.id; }
    }
    function selectLearning(index, stage = 10, remember = false, announce = true, replace = true) {
      if (!learningState || !learningState.model.events.length) return;
      const next=Math.max(0,Math.min(learningState.model.events.length-1,Number(index)||0));
      const nextStage=Math.max(0,Math.min(10,Number(stage)||0)),changedPosition=learningState.index!==next || learningState.stage!==nextStage;
      const changed=learningState.index!==next || !host.querySelector('[data-au-learning-focus]')?.firstElementChild;
      learningState.index=next;if(!learningState.playing && changedPosition)learningState.complete=false;learningState.stage=nextStage;
      const pane=host.querySelector('[data-au-learning-focus]');
      if(pane && (changed || learningState.facet!==knowledgeFacet)) {pane.innerHTML=knowledgeLearningFocus(learningState.model,learningState.model.events[next],knowledgeFacet);learningState.facet=knowledgeFacet;}
      if(remember){const event=learningState.model.events[next],item=event.versionRecord || event.item;knowledgePin=item?.knowledge_id&&item?.version?{knowledge_id:item.knowledge_id,version:item.version,knowledge_sha256:item.knowledge_sha256,definition_sha256:item.definition_sha256 || item.qualification?.definition_sha256}:null;}
      const chosenEvent=learningState.model.events[next];if(noticeCategory==='knowledge-pin-unavailable' && (chosenEvent.versionRecord || chosenEvent.refused))notice('');
      synchronizeLearning(announce);if(remember)learningRoute(replace);
    }
    function pauseLearning(remember = true) {if(!learningState)return;cancelLearning();synchronizeLearning();if(remember)learningRoute();}
    function playLearning() {
      if(!learningState || !learningState.model.frames.length || view!=='knowledge')return;
      cancelLearning();knowledgeFacet='process';
      const {model}=learningState;
      const start=learningFrameStart(model,learningState.index,learningState.stage,learningState.complete);
      let frame=start.frame;learningState.complete=false;
      learningState.playing=true;
      function tick() {
        if(disposed || view!=='knowledge' || !learningState?.playing || doc.hidden || pendingRoute())return;
        const row=model.frames[frame++];
        if(!row) {learningState.playing=false;learningState.complete=true;learningState.stage=10;synchronizeLearning();learningRoute();return;}
        selectLearning(start.alias?.representative===row.index?start.alias.index:row.index,row.stage,true);
        learningTimer=root.setTimeout(tick,row.duration);
      }
      tick();
    }
    // A pin can come from a reuse, a contribution or a library version link.
    const PIN_UNAVAILABLE = 'This exact saved knowledge version is not available in this record.';
    const knowledgePinKey = pin => pin ? [pin.knowledge_id,pin.version,pin.knowledge_sha256,pin.definition_sha256,pin.claim_id].map(value => value ?? '').join('|') : '';
    let renderedLibraryPin = null;
    // The tab names the shown procedure and exact version, when one is pinned.
    function knowledgeTitle(data, pin) {
      const versions = knowledgeLearningModel(data).versions, exact = pin?.version != null && pin.version !== '';
      // An exact pin names its version only when it is shown; a domain entry names its current version.
      const version = !pin ? null : exact ? versions.find(item => knowledgePinMatches(item,pin)) : versions.filter(item => String(item.knowledge_id || '') === String(pin.knowledge_id)).sort((a,b) => Number(b.version)-Number(a.version))[0];
      const place = version ? `${procedureLabel(version)}${version.version ? ` v${version.version}` : ''}` : pin?.knowledge_id ? procedureLabel({knowledge_id:pin.knowledge_id}) : knowledgeMode === 'learning' ? 'How this was learned' : '';
      return place ? `Knowledge · ${place}` : 'Knowledge';
    }
    function renderKnowledge(data, pin, initial = false, preference = null) {
      try { return renderKnowledgeView(data,pin,initial,preference); }
      finally { if (view === 'knowledge') routeTitle(knowledgeTitle(data,knowledgePin)); }
    }
    function renderKnowledgeView(data, pin, initial = false, preference = null) {
      if (knowledgeMode === 'learning' && knowledgeLearningModel(data).events.length) return renderLearning(data,pin,initial,preference);
      // With nothing recorded to replay, the address names the library it shows.
      if (knowledgeMode === 'learning' && view === 'knowledge' && root.history?.replaceState && root.location) {
        const fragment = knowledgeFragment('library',pin);
        if (root.location.hash !== fragment) { root.history.replaceState(null,'',root.location.pathname+root.location.search+fragment); routedFragment = fragment; }
      }
      knowledgeMode = 'library';
      return renderLibrary(data,pin,initial);
    }
    // An entry is focused at its heading: the article itself is thousands of
    // pixels tall and a focus ring around it would frame the whole screen.
    function focusLibraryEntry(entry, behavior = 'instant') {
      const heading = entry.querySelector?.('.au-library-entry-head h2') || entry;
      if (heading === entry) entry.setAttribute('tabindex','-1');
      heading.focus({preventScroll:true}); entry.scrollIntoView?.({block:'start',behavior});
    }
    // A refreshed library keeps keyboard focus on the same control.
    const libraryFocusSignature = element => [element.tagName,...[...(element.attributes || [])].filter(attr => attr.name === 'id' || attr.name.startsWith('data-au-')).map(attr => `${attr.name}=${attr.value}`).sort()].join('&');
    function libraryFocusKey(element) {
      if (!element || element === host || !host.contains?.(element)) return null;
      const family = element.closest?.('[data-au-library-entry]')?.dataset.auLibraryEntry || '', scope = family ? element.closest('[data-au-library-entry]') : host, signature = libraryFocusSignature(element);
      return {family,signature,tag:element.tagName,index:[...scope.querySelectorAll(element.tagName)].filter(row => libraryFocusSignature(row) === signature).indexOf(element)};
    }
    function libraryFocusTarget(token) {
      if (!token) return null;
      const scope = token.family ? [...host.querySelectorAll('[data-au-library-entry]')].find(row => row.dataset.auLibraryEntry === token.family) : host;
      if (!scope) return host.querySelector('h1');
      const peers = [...scope.querySelectorAll(token.tag)].filter(row => libraryFocusSignature(row) === token.signature);
      return peers[token.index] || peers[0] || (token.family ? scope.querySelector('.au-library-entry-head h2') : host.querySelector('h1'));
    }
    function markLibraryEntry(family) {
      for (const row of host.querySelectorAll('[data-au-library-jump]')) row.setAttribute('aria-current',String(row.dataset.auLibraryJump === family));
      for (const row of host.querySelectorAll('[data-au-library-entry]')) { if (row.dataset.auLibraryEntry === family) row.setAttribute('data-pinned','true'); else row.removeAttribute('data-pinned'); }
      return [...host.querySelectorAll('[data-au-library-entry]')].find(row => row.dataset.auLibraryEntry === family) || null;
    }
    // The library is the current state of every domain. An exact pin shows that
    // version inside its entry; an unavailable pin says so and keeps the rest.
    function renderLibrary(data, pin, initial = false) {
      cancelLearning(); learningState = null;
      const exactRequested = pin?.version != null && pin.version !== '', matching = exactRequested ? knowledgeLearningModel(data).versions.find(item => knowledgePinMatches(item,pin)) : null;
      const pinChanged = knowledgePinKey(renderedLibraryPin) !== knowledgePinKey(pin);
      const same = !initial && !pinChanged && host.querySelector('[data-au-library]') && (renderedKnowledge === data || JSON.stringify(renderedKnowledge) === JSON.stringify(data));
      if (!same) {
        const open = new Set([...host.querySelectorAll('details[open][data-au-disclosure]')].map(element => element.dataset.auDisclosure));
        const focusKey = initial ? null : libraryFocusKey(doc.activeElement);
        host.innerHTML = knowledgeLibraryMarkup(data,claims,pin);
        for (const disclosure of host.querySelectorAll('[data-au-disclosure]')) disclosure.open = open.has(disclosure.dataset.auDisclosure);
        interact(host); if (initial) { focusTitle(); if (!pin) root.scrollTo?.(0,0); } else if (focusKey && !pinChanged) libraryFocusTarget(focusKey)?.focus({preventScroll:true});
      }
      renderedKnowledge = data; knowledgePin = pin; renderedLibraryPin = pin;
      synchronizeKnowledgeRead();
      if (exactRequested && !matching) notice(PIN_UNAVAILABLE,true,'knowledge-pin-unavailable');
      else if (noticeCategory === 'knowledge-pin-unavailable') notice('');
      const entry = pin ? (matching ? [...host.querySelectorAll('[data-au-knowledge-identity]')].find(row => row.dataset.auKnowledgeIdentity === `${matching.knowledge_id || matching.version_id}:${matching.version || matching.version_id}`) : null) || markLibraryEntry(libraryFamily(pin)) : null;
      if (entry) { markLibraryEntry(libraryFamily(pin)); entry.setAttribute('data-pinned','true'); }
      if (entry && (initial || pinChanged)) focusLibraryEntry(entry);
      return !(exactRequested && !matching);
    }
    function renderLearning(data, pin, initial = false, preference = null) {
      renderedLibraryPin = null;
      const open = new Set([...host.querySelectorAll('details[open][data-au-disclosure]')].map(element => element.dataset.auDisclosure));
      const model=knowledgeLearningModel(data), matching=pin?model.versions.find(item=>knowledgePinMatches(item,pin)):null;
      const reusedEvent=matching&&pin?.claim_id?model.events.findIndex(event=>event.kind==='knowledge.used'&&event.claim_id===pin.claim_id&&event.versionRecord===matching):-1;
      const pinnedEvent=reusedEvent>=0?reusedEvent:matching?model.events.findIndex(event=>event.kind==='knowledge.published'&&event.versionRecord===matching&&!event.refused):-1;
      const explicit=preference?.event ? model.events.findIndex(event=>event.id===preference.event):-1;
      // The replay plays only when a reader asks for it, never on arrival.
      const first=Boolean(preference?.play) && !pin && !preference?.event && !reduced?.matches && model.frames.length>0;
      const retainedId=learningState?.model.events[learningState.index]?.id;
      const retainedIndex=retainedId?model.events.findIndex(event=>event.id===retainedId):-1;
      const preserve=(!pin || matching) && !initial && !preference && retainedIndex>=0,wasPlaying=Boolean(preserve&&learningState?.playing),announced=preserve?learningState.announced:null,completed=preference?.complete ?? Boolean(preserve&&learningState.complete);
      const position=pin&&!matching?null:preserve?{index:retainedIndex,stage:learningState.stage}:explicit>=0?{index:explicit,stage:preference.stage??10}:pinnedEvent>=0?{index:pinnedEvent,stage:10}:pin?null:first?{index:0,stage:0}:null;
      const sameData=renderedKnowledge===data && host.querySelector('[data-au-learning]');
      if (!sameData || initial) {
        cancelLearning();host.innerHTML=knowledgeMarkup(data,claims,pin,knowledgeFacet,position);
        const fallback=model.events.findIndex(event=>event.kind==='knowledge.published'&&!event.refused&&event.versionRecord===[...model.versions].sort((a,b)=>String(name(a)).localeCompare(String(name(b)))||Number(b.version)-Number(a.version))[0]);
        learningState={data,model,index:pin&&!matching?-1:position?.index??Math.max(0,fallback),stage:position?.stage??10,playing:false,complete:completed,facet:knowledgeFacet,announced};
        renderedKnowledge=data;knowledgePin=pin;
        for(const disclosure of host.querySelectorAll('[data-au-disclosure]'))disclosure.open=open.has(disclosure.dataset.auDisclosure);
        interact(host);if(initial){focusTitle();if(!(pin&&matching))root.scrollTo?.(0,0);}
      } else {knowledgePin=pin;if(position)selectLearning(position.index,position.stage,false,false);else if(learningState?.facet!==knowledgeFacet)selectLearning(learningState.index,learningState.stage,false,false);}
      synchronizeKnowledgeRead();synchronizeLearning();
      host.querySelectorAll('[data-pinned]').forEach(row=>row.removeAttribute('data-pinned'));
      if(pin && !matching) {notice(PIN_UNAVAILABLE,true,'knowledge-pin-unavailable');return false;}
      if(pin && matching) {
        const row=[...host.querySelectorAll('[data-au-knowledge-identity]')].find(element=>element.dataset.auKnowledgeIdentity===`${pin.knowledge_id}:${pin.version}`);
        if(row){row.setAttribute('data-pinned','true');row.setAttribute('tabindex','-1');row.focus({preventScroll:true});row.scrollIntoView?.({block:'start',behavior:'instant'});}
      }
      if(first || wasPlaying&&!sameData)playLearning();
      return true;
    }
    function knowledgeFragment(mode, pin, preference = null) {
      const exact = pin?.version != null && pin.version !== '';
      return `#autonomous/knowledge${mode === 'learning' || pin ? '?' : ''}${mode === 'learning' ? `view=learning${pin ? '&' : ''}` : ''}${pin ? `knowledge=${key(pin.knowledge_id)}${exact ? `&version=${key(pin.version)}&sha256=${key(pin.knowledge_sha256 || '')}${pin.definition_sha256 ? `&definition=${key(pin.definition_sha256)}` : ''}` : ''}${pin.claim_id ? `&claim=${key(pin.claim_id)}` : ''}` : ''}${mode === 'learning' && preference?.event ? `&event=${key(preference.event)}&stage=${key(preference.stage ?? 10)}` : ''}`;
    }
    async function showKnowledge(writeHistory = true, pin = null, preference = null) {
      knowledgeMode = preference?.view === 'learning' || preference?.event ? 'learning' : 'library';
      knowledgeFacet = ['process','facts','documents','exceptions','changes'].includes(preference?.facet)?preference.facet:'process'; knowledgePin = pin;
      stopPresentation(); leaveView();
      route(knowledgeFragment(knowledgeMode,pin,preference),writeHistory);
      epoch++; const token = epoch, read = ++knowledgeRead, generation = readGeneration;
      let awaitingFresh = true, freshReadFailed = false;
      // A read may finish after inspection changes the pin or replay position.
      // Only the first paint consumes the originally requested preference.
      const reconcileKnowledge = data => {
        const initial = !host.querySelector('[data-au-learning]') && !host.querySelector('[data-au-library]');
        return renderKnowledge(data,initial ? pin : knowledgePin,initial,initial ? preference : null);
      };
      cancelPoll(); setView('knowledge'); nav('knowledge'); current = null;
      if (knowledgeCache) { renderKnowledge(knowledgeCache.value,pin,true,preference); synchronizeKnowledgeRead('refreshing'); notice(''); }
      else { host.innerHTML = readSkeletonMarkup('knowledge') + button('Retry','data-au-knowledge-retry hidden'); interact(host); routeSettled('knowledge',pin?.knowledge_id ? `Knowledge · ${procedureLabel({knowledge_id:pin.knowledge_id})}` : 'Knowledge'); notice(''); }
      sessionRestore?.then(() => {
        if (!disposed && (awaitingFresh || freshReadFailed) && token === epoch && read === knowledgeRead && generation === readGeneration && !pendingRoute() && view === 'knowledge' && knowledgeCache && !host.querySelector('[data-au-knowledge-identity]')) {
          reconcileKnowledge(knowledgeCache.value); synchronizeKnowledgeRead(freshReadFailed ? 'failed' : 'refreshing');
        }
      });
      // Source/receiving titles come from the persisted projection. A catalog
      // read must not compete with the selected Knowledge response.
      try {
        const data = await request('/knowledge');
        if (disposed || token !== epoch || read !== knowledgeRead || generation !== readGeneration || pendingRoute()) return;
        readKnowledge(data);
        knowledgeCache = JSON.stringify(data).length * 2 <= 8 * 1024 * 1024 ? {value:data} : null;
        savedKnowledge = {at:Date.now(),value:data}; persistReadCache();
        awaitingFresh = false;
        synchronizeKnowledgeRead('verified');host.removeAttribute?.('data-au-knowledge-error');
        notice(''); reconcileKnowledge(data);
      } catch (error) { awaitingFresh = false; freshReadFailed = true; if (!disposed && token === epoch && read === knowledgeRead) { synchronizeKnowledgeRead('failed');host.setAttribute?.('data-au-knowledge-error',knowledgeCache?'refresh':'load');notice('Could not load Knowledge. Try again.',true,'knowledge-load-failed');noticeRecord={message:error.message,status:error.status,code:error.code,operation:knowledgeCache?'refresh':'load'};globalStatus.insertAdjacentHTML?.('beforeend',recordButton('Details','notice')); } }
    }
    function idleIntakeSubmit(form) {
      const submit = form?.querySelector('button[type="submit"]');
      if (!submit) return;
      if (publicReadOnly) { submit.disabled = true; submit.textContent = 'Public workspace · read-only'; return; }
      submit.textContent = status?.enabled === true && (status.provider_ready === false || status.limits?.autonomous_can_start === false) ? 'Save case' : 'Start checking ↗';
      submit.disabled = !status?.enabled || !writable(status);
    }
    function lockForm(form, lock, retry = false) {
      if (publicReadOnly) { for (const control of form.querySelectorAll('input,textarea,select,button[type="submit"]')) control.disabled = true; const submit = form.querySelector('button[type="submit"]'); if (submit) submit.textContent = 'Public workspace · read-only'; return; }
      for (const control of form.querySelectorAll('input,textarea,select,button[type="submit"]')) control.disabled = lock;
      const submit = form.querySelector('button[type="submit"]');
      if (retry) { submit.disabled = !writable(status); submit.textContent = 'Retry same request'; }
      else if (!lock && form.matches('[data-au-intake]')) idleIntakeSubmit(form);
      else submit.textContent = lock ? 'Saving…' : 'Add files';
    }
    async function filesFrom(input) {
      const files = [...input.files], output = [];
      if (files.length > 20) throw new Error('Add at most 20 supporting files at once.');
      for (const file of files) {
        if (status?.limits?.max_file_bytes && file.size > status.limits.max_file_bytes) throw new Error(`${file.name} exceeds the file size limit.`);
        const bytes = new Uint8Array(await file.arrayBuffer()); let binary = '';
        for (let offset=0; offset<bytes.length; offset+=8192) binary += String.fromCharCode(...bytes.subarray(offset,offset+8192));
        output.push({file_name:file.name, media_type:mediaType(file), content_base64:root.btoa(binary)});
      }
      return output;
    }
    async function submit(event) {
      const form = event.target;
      if (!form.matches('[data-au-intake],[data-au-arrival]')) return;
      event.preventDefault(); if (publicReadOnly) { notice(PUBLIC_READ_ONLY_MESSAGE); return; } if (busy || !status || !writable(status)) return;
      const intake = form.matches('[data-au-intake]'), token = epoch, saved = current;
      if (!intake && (!saved || !freshClaim || presentationMode === 'replay')) return;
      let submitted = false;
      busy = true; lockForm(form,true); const message = form.querySelector('.au-form-status'); message.textContent = '';
      try {
        let operation = intake ? pendingIntake : pendingArrival;
        if (!operation) {
          const files = await filesFrom(form.elements.files), idempotency_key = `browser.${root.crypto.randomUUID()}`;
          operation = {body:intake ? {title:form.elements.title.value.trim(), message:form.elements.message.value, files, idempotency_key} : {files,idempotency_key,expected_revision:saved.revision,expected_state_sha256:saved.state_sha256}, claimId:saved?.claim_id};
          if (intake) pendingIntake = operation; else pendingArrival = operation;
        }
        submitted = true; invalidateReads(operation.claimId);
        const response = await request(intake ? '/claims' : `/claims/${key(operation.claimId)}/sources`, {method:'POST',body:JSON.stringify(operation.body)});
        const accepted = readState(response, intake ? undefined : operation.claimId);
        if (intake) { rememberClaim(accepted.state,'native_intake'); pendingIntake = null; form.reset?.(); lockForm(form,false); } else { pendingArrival = null; arrivals.delete(operation.claimId); form.reset?.(); lockForm(form,false); }
        if (!disposed && token === epoch && !pendingRoute()) await openClaim(accepted.state.claim_id);
      } catch (error) {
        if (!disposed && token === epoch) {
          const uncertain = submitted && (!error.status || error.status >= 500);
          if (!uncertain) { if (intake) pendingIntake = null; else pendingArrival = null; }
          if (!intake && submitted && !pendingRoute()) await loadOpenedClaim(saved.claim_id,token);
          if (disposed || token !== epoch || pendingRoute()) return;
          lockForm(form, uncertain, uncertain); message.textContent = uncertain ? `${error.message} The response is unconfirmed. Retry reuses the same request key.` : error.message;
        }
      } finally { busy = false; synchronizeAuthority(); routeChanged(); }
    }
    async function controlWork(target, action) {
      if (publicReadOnly || busy || !freshClaim || !status || !writable(status) || !current || presentationMode === 'replay' || action === 'resume' && !intakeEligible(projection) || (action === 'pause' ? current.status !== 'running' : current.status !== 'deferred' || current.deferral?.code !== 'paused')) return;
      if (pendingControl?.action !== action) pendingControl = null;
      const token = epoch, saved = current;
      pendingControl ||= {action,claimId:saved.claim_id,body:{expected_revision:saved.revision,expected_state_sha256:saved.state_sha256,idempotency_key:`browser.${root.crypto.randomUUID()}`}};
      busy = true;
      try {
        invalidateReads(pendingControl.claimId);
        const accepted = readState(await request(`/claims/${key(pendingControl.claimId)}/${action}`,{method:'POST',body:JSON.stringify(pendingControl.body)}),pendingControl.claimId);
        pendingControl = null;
        if (!disposed && token === epoch) await poll();
      } catch (error) {
        if (error.status && error.status < 500) pendingControl = null;
        if (!disposed && token === epoch) notice(`${error.message}${pendingControl ? ` ${words(action)} response unconfirmed; retry uses the same request.` : ' Refreshing the saved claim.'}`,true);
        if (!disposed && token === epoch && !pendingRoute()) await loadOpenedClaim(saved.claim_id,token);
        if (!disposed && token === epoch && pendingControl) notice(`${error.message} ${words(action)} response unconfirmed; retry uses the same request.`,true);
      } finally { busy = false; synchronizeAuthority(); routeChanged(); }
    }
    async function openSource(id, citation, trigger, sourceState = null) {
      if (!sourceState && !current) return;
      const saved = sourceState || operationPeek?.state || current, sourceProjection = sourceState ? {} : projection, token = epoch, sourceToken = ++sourceEpoch, descriptor = list(saved.source_descriptors).find(source => source.artifact_id === id);
      if (!descriptor) { notice('This source is not part of the saved claim.',true); return; }
      dialogReturn = {element:trigger,token:focusToken(trigger)}; container.querySelector('#auSourceTitle').textContent = operationSourceTitle(descriptor);
      const sourceEyebrow = dialog.querySelector?.('.au-eyebrow'); if (sourceEyebrow) sourceEyebrow.textContent = sourceKind(saved,descriptor,sourceProjection);
      const body = container.querySelector('[data-au-source-content]'), url = `${base}/sources/${key(saved.claim_id)}/${key(id)}`;
      const native = descriptor.media_type?.split(';')[0];
      let nativeMarkup = '', nativeViewable = false; clearNativeSource();
      body.innerHTML = `<div class="au-source-meta"><span>${h(descriptor.media_type || 'Original file')}</span><a href="${h(url)}" download="${h(descriptor.file_name || 'source')}">Download original</a></div>${nativeMarkup}<p class="au-empty">Checking source identity…</p>`;
      pauseInspection();
      motion?.cancel(); selectionMotion?.cancel(); interactionMotion?.cancel();
      if (!dialog.open) dialog.showModal();
      const nativePreview = native === 'application/pdf' || native?.startsWith('image/') ? nativeSource(url.slice(base.length),descriptor,token,sourceToken).then(blob => ({blob}),error => ({error})) : null;
      try {
        let acquired = list(saved.acquired_sources).some(source => source.artifact_id === id), response;
        const generation = readGeneration, sourceIdentity = `${saved.claim_id}:${id}:${descriptor.sha256}:${acquired ? 'text' : 'preview'}:${saved.original_binding?.original_binding_sha256 || ''}`;
        response = cachedRead(sourcePreviews,sourceIdentity);
        try { response ||= await request(`${url.slice(base.length)}/${acquired ? 'text' : 'preview'}`); }
        catch (error) {
          if (acquired || saved.revision === 0 || ![404,405,501].includes(error.status)) throw error;
          // Older servers expose only admitted text. Its independent identity
          // checks remain mandatory; unavailable extraction never admits it.
          response = await request(`${url.slice(base.length)}/text`); acquired = true;
        }
        const checked = acquired ? await checkedSource(saved,descriptor,response,citation) : {source:await checkedPreview(saved,descriptor,response),span:null};
        if (!disposed && generation === readGeneration) rememberRead(sourcePreviews,sourceIdentity,response,16,8 * 1024 * 1024);
        if (!acquired && citation) throw new Error('The cited source has no admitted acquisition record.');
        if (disposed || token !== epoch || sourceToken !== sourceEpoch || !dialog.open) return;
        if (nativePreview) {
          const preview = await nativePreview;
          if (preview.error) nativeMarkup = `<p class="au-meta">${h(preview.error.message)}</p>`;
          else if (preview.blob) { nativeViewable = true; nativeMarkup = `<div class="au-native-source" data-au-native-kind="${native === 'application/pdf' ? 'document' : 'image'}">${native === 'application/pdf' ? `<iframe class="au-native-document" src="${h(preview.blob)}" title="${h(operationSourceTitle(descriptor))}"></iframe>` : `<img class="au-native-image" src="${h(preview.blob)}" alt="${h(operationSourceTitle(descriptor))}">`}</div>`; }
        }
        if (disposed || token !== epoch || sourceToken !== sourceEpoch || !dialog.open) return;
        const unassessed = !sourceState && assessmentFreshness(current).sources.some(source => source.artifact_id === descriptor.artifact_id);
        const source = checked.source, unsupported = source.extraction === 'unsupported_metadata';
        const extraction = unsupported ? 'Received · interpretation unsupported' : source.complete ? 'Extracted text' : 'Extraction incomplete';
        const identity = `<details class="au-source-identity"><summary>Details</summary><p class="au-meta">${acquired ? 'Source text verified' : 'Document preview checked'}${checked.span ? ' · exact cited span verified' : ''} · ${h(extraction)}</p>${!acquired ? '<p class="au-meta">Preview does not admit evidence or establish understanding or sufficiency.</p>' : ''}<dl class="au-chain"><div><dt>Original filename</dt><dd>${h(descriptor.file_name)}</dd></div><div><dt>Media type</dt><dd>${h(descriptor.media_type)}</dd></div><div><dt>Original bytes · SHA-256</dt><dd class="au-hash">${h(descriptor.sha256)}</dd></div><div><dt>Extracted text · SHA-256</dt><dd class="au-hash">${h(source.text_sha256)}</dd></div>${!acquired ? `<div><dt>Preview · SHA-256</dt><dd class="au-hash">${h(source.preview_sha256)}</dd></div>` : ''}</dl><pre class="au-record-body">${h(JSON.stringify({descriptor,preview_only:source.preview_only,evidence_admitted:source.evidence_admitted,receipt_sha256:source.receipt_sha256,preview_sha256:source.preview_sha256,extraction:source.extraction,complete:source.complete,coverage:source.coverage,reason:source.reason,limitation:source.limitation},null,2))}</pre>${!source.text ? '<p class="au-meta">No readable text was extracted.</p>' : ''}</details>`;
        const unsupportedImage = unsupported && native?.startsWith('image/');
        body.innerHTML = (unassessed ? '<p class="au-assessment-freshness" data-au-source-freshness="unassessed"><strong>New source · awaiting assessment</strong></p>' : '') + (unsupportedImage ? `<div class="au-source-meta"><a href="${h(url)}" download="${h(descriptor.file_name || 'source')}">Download original</a></div><p class="au-source-capability">${nativeViewable ? 'Original image viewable.' : 'Original image preview unavailable.'} CasePath could not read this image.</p>${nativeMarkup}${identity}` : `<div class="au-source-meta"><span>${acquired ? 'Source text verified' : 'Document preview checked'}${checked.span ? ' · exact cited span verified' : ''}</span><span>${h(extraction)}</span><a href="${h(url)}" download="${h(descriptor.file_name || 'source')}">Download original</a></div>${nativeMarkup}${!acquired ? '<p class="au-meta">Preview does not admit evidence or establish understanding or sufficiency.</p>' : ''}${!source.complete ? `<p class="au-notice">${h(source.reason || source.limitation || words(source.coverage?.limitation) || 'This source does not have a complete text extraction.')}</p>` : ''}${source.text ? `<pre class="au-source-body">${checked.span ? `${h(checked.span.before)}<mark tabindex="-1">${h(checked.span.quote)}</mark>${h(checked.span.after)}` : h(source.text)}</pre>` : '<p class="au-meta">No readable text was extracted.</p>'}${identity}`);
        interact(body); body.querySelector('mark')?.scrollIntoView({block:'center',behavior:'instant'});
      } catch (error) { if (!disposed && token === epoch && sourceToken === sourceEpoch && dialog.open) body.innerHTML = `<div class="au-source-meta"><a href="${h(url)}" download="${h(descriptor.file_name || 'source')}">Download original</a></div>${nativeMarkup}<p class="au-error" role="alert">${h(plain(error.message,'The document could not open.'))}</p><details><summary>Details</summary><p>${h(error.message)}</p></details>`; }
    }
    // A Knowledge passage opens through its source case's verified snapshot
    // (GET only); the library never reads source bytes without that identity.
    async function openKnowledgeSource(claimId, id, citation, trigger) {
      const token = epoch;
      let saved = cachedRead(snapshots,claimId)?.state || null;
      if (!saved) {
        try {
          const incoming = await consistentRead(claimId,null,true,token,() => view === 'knowledge',true);
          saved = incoming.state; rememberSnapshot(claimId,{state:incoming.state,projection:incoming.projection,cursor:incoming.accepted.cursor,history:incoming.accepted.events},true);
        } catch (error) { if (!disposed && token === epoch && view === 'knowledge') notice(plain(error.message,'The source could not open.'),true); return; }
      }
      if (disposed || token !== epoch || view !== 'knowledge') return;
      return openSource(id,citation,trigger,saved);
    }
    function selectDesk(target) {
      if(!current)return;pauseInspection();
      const trace=operationTrace||deskRecords.get(current.state_sha256),model=deskOperationModel(current,trace);
      deskSelection=null;chosenNode=null;evidenceContext={};detail='step';
      if(target.hasAttribute('data-au-desk-select')){chosenNode=selected=target.dataset.auDeskSelect;}
      else if(target.hasAttribute('data-au-desk-document-select')){const document=target.dataset.auDeskDocumentSelect;const node=model.nodes.find(row=>list(row.document_types).includes(document));if(node)chosenNode=selected=node.node_id;deskSelection={document};evidenceContext={document};}
      else if(target.hasAttribute('data-au-desk-file-select')){deskSelection={artifact_id:target.dataset.auDeskFileSelect};}
      else if(target.hasAttribute('data-au-desk-predicate-source')){const id=target.dataset.auDeskPredicateSource,operation=list(trace?.rows).findLast(row=>row.kind==='fact.extract'&&row.object.id===id&&row.source);if(operation)deskSelection={operation:operation.id};}
      renderClaim();
      // Step/document selections survive reload. File peeks leave the saved
      // case route at its answer, so they cannot turn into an unrelated step.
      route(claimFragment(current.claim_id,{mode:presentationMode,collection:openingPreferences.collection,operations:openingPreferences.operations,through:replayRecord?.through_seq,detail:'step',node:chosenNode,...(chosenNode?evidenceContext:{})}));
      host.querySelector('[data-au-desk-source] .au-desk-source-name')?.focus({preventScroll:true});
    }
    function renderDeskDraft() {
      if(!deskDraft||!recordDialog.open)return;
      const d=deskDraft,body=recordDialog.querySelector('[data-au-record-content]'),value=d.value;
      body.innerHTML=`<section class="au-desk-draft"><p>Not sent — you decide</p><p data-au-draft-status role="status">${h(d.message|| (d.saved?'Saved on this device.':'Original draft.'))}</p>${d.editing?`<label>Subject<input data-au-draft-subject maxlength="500" value="${h(value.subject)}"></label><label>Letter<textarea data-au-draft-body maxlength="50000">${h(value.body)}</textarea></label>`:`<h3>${h(value.subject)}</h3><pre class="au-record-body">${h(value.body)}</pre>`}<div class="au-desk-draft-actions">${button(d.editing?'Save on this device':'Edit a copy',d.editing?'data-au-draft-save':'data-au-draft-edit')}${button('Copy text','data-au-draft-copy')}${button('Download letter','data-au-draft-download')}${d.saved?button('View original','data-au-draft-original'):''}</div></section>`;
    }
    async function openDeskDraft(target) {
      const binding=deskDraftBinding(current);if(!binding)return;
      pauseInspection();const token=epoch,claim=current.claim_id;recordSelection=null;recordReturn={element:target,token:focusToken(target)};recordExplained=null;
      recordDialog.querySelector('#auRecordTitle').textContent='Draft letter';recordDialog.querySelector('[data-au-record-content]').textContent='Opening the letter…';recordDialog.showModal();
      const hash=await digest(canonicalJSON({api:apiIdentity,draft:binding}));
      if(disposed||token!==epoch||current?.claim_id!==claim||!recordDialog.open)return;
      const key=`casepath.local-draft.v1:${hash}`;let saved=null,message='';
      try{const raw=root.localStorage.getItem(key);if(raw)saved=checkedDeskDraft(JSON.parse(raw),hash);}catch(_){message='Your saved copy could not be opened.';}
      deskDraft={binding,hash,key,saved:Boolean(saved),value:saved||{subject:binding.subject,body:binding.body},message,editing:false};renderDeskDraft();
    }
    async function deskDraftAction(target) {
      const d=deskDraft;if(!d||!recordDialog.open)return;
      const value=d.editing?{subject:recordDialog.querySelector('[data-au-draft-subject]').value,body:recordDialog.querySelector('[data-au-draft-body]').value}:d.value;
      if(target.hasAttribute('data-au-draft-edit')){d.editing=true;d.message='Your copy. Save it on this device.';renderDeskDraft();recordDialog.querySelector('[data-au-draft-body]')?.focus();return;}
      if(target.hasAttribute('data-au-draft-original')){d.value={subject:d.binding.subject,body:d.binding.body};d.editing=false;d.message='Original draft.';renderDeskDraft();return;}
      if(target.hasAttribute('data-au-draft-save')){
        const entry={contract:'casepath.local-draft/1',binding:d.hash,...value,saved_at:new Date().toISOString()};if(!checkedDeskDraft(entry,d.hash))return;
        try{root.localStorage.setItem(d.key,JSON.stringify(entry));d.value=value;d.saved=true;d.editing=false;d.message='Saved on this device.';renderDeskDraft();}catch(_){recordDialog.querySelector('[data-au-draft-status]').textContent='Could not save. Your edits are still here.';}return;
      }
      const content=`${value.subject}\n\n${value.body}`;
      if(target.hasAttribute('data-au-draft-copy')){try{await root.navigator.clipboard.writeText(content);if(deskDraft===d&&recordDialog.open)recordDialog.querySelector('[data-au-draft-status]').textContent='Copied.';}catch(_){if(deskDraft===d&&recordDialog.open)recordDialog.querySelector('[data-au-draft-status]').textContent='Could not copy. You can download the letter.';}return;}
      if(target.hasAttribute('data-au-draft-download')){const url=root.URL.createObjectURL(new root.Blob([content],{type:'text/plain;charset=utf-8'})),link=doc.createElement('a');link.href=url;link.download=`casepath-${d.binding.claim_id}-draft.txt`;doc.body.appendChild(link);link.click();link.remove();root.setTimeout(()=>root.URL.revokeObjectURL(url),1000);}
    }
    function synchronizeRecord(opening = false) {
      if (!recordSelection || !opening && !recordDialog.open) return;
      const {kind,id} = recordSelection, body = recordDialog.querySelector('[data-au-record-content]');
      if (kind === 'demo') {
        body.innerHTML = demoPickerMarkup(claims,activeTour()?.collection || demoRoster(claims).collection);
        return;
      }
      const trace = operationPeek?.trace || operationTrace, state = operationPeek?.state || current, events = operationPeek?.events || history;
      const record = kind === 'notice' ? {message:noticeRecord} : ['operation','operation-attempt'].includes(kind) ? operationRecord(trace,kind,id) : contextualRecord(state,operationPeek?.projection || projection,events,kind,id,knowledgeCache?.value || {},replayRecord);
      // The JSON lives in one nested Technical record; plain rows lead.
      if (!body.querySelector('pre')) body.innerHTML = RECORD_DIALOG_SKELETON;
      const explanation = recordExplanation(kind,record,{state,events,trace,id,passageFirst:recordSelection.passageFirst,focus:recordSelection.focus});
      const explain = body.querySelector('[data-au-record-explain]');
      if (explain && recordExplained !== explanation.html) { explain.innerHTML = explanation.html; recordExplained = explanation.html; }
      const technical = body.querySelector('[data-au-record-technical]'); if (technical && opening) technical.open = false;
      if (opening && recordSelection.generic && explanation.title) recordDialog.querySelector('#auRecordTitle').textContent = explanation.title;
      const context = body.querySelector('.au-record-context'); if (context) { const checkpoint = kind === 'operation' && [...list(operationTrace?.checkpoints)].reverse().find(row => row.after_operation < record?.seq); context.textContent = kind === 'operation' ? `History · working step ${record?.seq || ''}${checkpoint ? ` · the case stood at accepted revision ${checkpoint.revision}` : ''}` : ''; }
      const pre = body.querySelector('pre'); pre.dataset.auRecordKind = kind; pre.dataset.auRecordId = id; pre.textContent = JSON.stringify(record ?? null,null,2);
    }
    function openRecord(target) {
      pauseInspection(); motion?.cancel(); selectionMotion?.cancel(); interactionMotion?.cancel();
      // A fact chip or a step answers with its cited passage first.
      const chip = target.matches?.('.au-stage-fact'), step = target.matches?.('[data-au-node]'), label = target.textContent.trim();
      const start = Number(target.dataset?.auFactStartChar), end = Number(target.dataset?.auFactEndChar);
      recordSelection = {kind:target.dataset.auInspect,id:target.dataset.auRecordId || '',passageFirst:Boolean(chip || step),focus:chip && Number.isSafeInteger(start) && Number.isSafeInteger(end) ? {start,end} : null,generic:Boolean(step) || !label || label.length > 80 || /^(?:Details|Technical record|Inspect)$/u.test(label)};
      recordReturn = {element:target,token:focusToken(target)}; recordExplained = null;
      recordDialog.querySelector('#auRecordTitle').textContent = recordSelection.kind === 'demo' ? 'Choose a case' : label || 'Details';
      synchronizeRecord(true); recordDialog.showModal();
    }
    function restoreRecordFocus(returning) {
      if (!returning) return;
      (returning.element?.isConnected && focusEligible(returning.element,returning.token) ? returning.element : focusTarget(returning.token) || host.querySelector('[data-au-claim-title]'))?.focus({preventScroll:true});
    }
    function closeRecord() {
      if (!recordDialog.open) return;
      const returning = recordReturn; recordReturn = null; recordDialog.close(); restoreRecordFocus(returning);
    }
    function closedRecord() {
      if (recordDialog.open) return;
      deskDraft=null;
      const explain = recordDialog.querySelector('[data-au-record-explain]'); if (explain) { explain.innerHTML = ''; recordExplained = null; }
      const returning = recordReturn; recordReturn = null; restoreRecordFocus(returning);
    }
    function click(event) {
      // The skip link moves focus to the page heading; the hash router never sees it.
      const skip = event.target.closest?.('[data-au-skip]');
      if (skip?.hasAttribute?.('data-au-skip') && container.contains(skip)) {
        // Main is focusable only for the moment the skip link lands there, so
        // a click on plain text inside it never moves focus to the region.
        event.preventDefault?.(); const heading = host.querySelector('h1'), main = container.querySelector('.au-main');
        if (heading) heading.focus?.(); else if (main) { main.setAttribute('tabindex','-1'); main.addEventListener?.('blur',() => main.removeAttribute('tabindex'),{once:true}); main.focus?.(); }
        return;
      }
      const target = event.target.closest('button,[data-au-nav]'); if (!target || !container.contains(target)) return;
      if(view==='knowledge' && !target.hasAttribute('data-au-learning-play'))pauseLearning();
      if(target.hasAttribute('data-au-learning-play')){if(learningState?.playing)pauseLearning();else playLearning();}
      else if(target.hasAttribute('data-au-learning-event')){selectLearning(Number(target.dataset.auLearningEvent),10,true,true,false);}
      else if(target.hasAttribute('data-au-learning-end') || target.hasAttribute('data-au-library-return')){if(busy)return;const event=learningState?.model.events[learningState.index],family=event && !event.refused ? libraryFamily(event.versionRecord || event.item) || event.family : '';showKnowledge(true,DOMAINS.some(row=>row.id===family)?{knowledge_id:`procedure.${family}`}:null);}
      else if(target.hasAttribute('data-au-learning-open')){if(busy)return;const data=renderedKnowledge || knowledgeCache?.value;if(!data)return;const model=knowledgeLearningModel(data),family=target.dataset.auLearningOpen,identity=target.dataset.auLearningVersion,event=family?model.events.find(row=>row.kind==='knowledge.published'&&!row.refused&&row.versionRecord&&`${row.versionRecord.knowledge_id || row.versionRecord.version_id}:${row.versionRecord.version || row.versionRecord.version_id}`===identity) || model.events.find(row=>row.family===family):null;showKnowledge(true,null,event?{view:'learning',event:event.id,stage:10}:{view:'learning',play:true});}
      else if(target.hasAttribute('data-au-library-jump')){const family=target.dataset.auLibraryJump,entry=markLibraryEntry(family);if(!entry)return;knowledgePin=renderedLibraryPin={knowledge_id:`procedure.${family}`};if(renderedKnowledge)routeTitle(knowledgeTitle(renderedKnowledge,knowledgePin));const fragment=`#autonomous/knowledge?knowledge=${key(`procedure.${family}`)}`;if(root.history?.replaceState&&root.location){root.history.replaceState(null,'',root.location.pathname+root.location.search+fragment);routedFragment=fragment;}focusLibraryEntry(entry,reduced?.matches?'instant':'smooth');}
      else if(target.hasAttribute('data-au-knowledge-retry')){showKnowledge(false,knowledgePin,knowledgeMode==='learning'?{view:'learning',event:learningState?.model.events[learningState.index]?.id,stage:learningState?.stage,facet:knowledgeFacet,complete:learningState?.complete}:null);}
      else if (target.hasAttribute('data-au-close-record')) closeRecord();
      else if (target.hasAttribute('data-au-return-case')) { if (!busy && lastCaseContext) openClaim(lastCaseContext.claim_id,true,{...lastCaseContext,detail:target.dataset.auReturnCase}); }
      else if (target.hasAttribute('data-au-knowledge-facet')) { if (view === 'knowledge' && ['process','facts','documents','exceptions','changes'].includes(target.dataset.auKnowledgeFacet) && knowledgeCache) { knowledgeFacet = target.dataset.auKnowledgeFacet; if(learningState){selectLearning(learningState.index,10,true,false);}else renderKnowledge(knowledgeCache.value,knowledgePin); host.querySelector(`[data-au-knowledge-facet="${knowledgeFacet}"]`)?.focus({preventScroll:true}); } }
      else if (target.hasAttribute('data-au-open-outcome-draft')) {
        pauseInspection();
        const draft = host.querySelector('[data-au-disclosure=outcome-draft]');
        if (draft) { const why = draft.closest('[data-au-disclosure=outcome-why]'); if (why) why.open = true; draft.open = true; draft.querySelector('summary')?.focus(); draft.scrollIntoView?.({block:'nearest',behavior:'instant'}); }
      }
      else if(target.hasAttribute('data-au-desk-draft')) openDeskDraft(target);
      else if(['edit','save','original','copy','download'].some(action=>target.hasAttribute(`data-au-draft-${action}`))) deskDraftAction(target);
      else if(target.hasAttribute('data-au-desk-select')||target.hasAttribute('data-au-desk-document-select')||target.hasAttribute('data-au-desk-file-select')||target.hasAttribute('data-au-desk-predicate-source')) selectDesk(target);
      else if(target.hasAttribute('data-au-desk-result')){deskSelection=null;chosenNode=null;evidenceContext={};renderClaim();route(claimFragment(current.claim_id,{mode:presentationMode,collection:openingPreferences.collection,operations:openingPreferences.operations,through:replayRecord?.through_seq}));}
      else if(target.hasAttribute('data-au-desk-retry')){if(current)ensureDeskRecord(current,epoch);}
      else if(target.hasAttribute('data-au-desk-watch')){if(current){const row=REFERENCE_DEMO_CASES.find(row=>row.claim_id===current.claim_id);if(row){stopPresentation();tour=null;demoSession={mode:'operations',collection:'reference',cases:[row],index:0,operations:openingPreferences.operations,single:true};openPresentationCase(demoSession);}}}
      else if (target.hasAttribute('data-au-inspect')) openRecord(target);
      else if (target.hasAttribute('data-au-demo-case')) { const id = target.dataset.auDemoCase; recordReturn = null; recordDialog.close(); stopPresentation(); demoMode = 'replay'; const collection = demoCollection(target.dataset.auDemoCollection) || 'reference', filtered = collectionRoster(collection,claims), cases = filtered.some(row => row.claim_id === id) ? filtered : demoCases(collection), index = cases.findIndex(row => row.claim_id === id); if (index >= 0) { const operations=openingPreferences.operations || operationRoutePreference(root.location?.hash,root.location?.search); demoSession = tourSession(collection,cases,index,operations,target.dataset.auDemoSaved === 'true'); openPresentationCase(demoSession); } }
      else if (target.hasAttribute('data-au-demo-skip')) skipTourCase();
      else if (target.hasAttribute('data-au-filter')) { if (view !== 'work') return; const chosen = caseFilter(target.dataset.auFilter); collection.filter = target.getAttribute?.('aria-pressed') === 'true' ? 'all' : chosen; collection.page = 1; refreshCollection(); rememberCollectionRoute(true); collectionSettled(); }
      else if (target.hasAttribute('data-au-page')) { if (view === 'work' && !target.disabled) { collection.page = Number(target.dataset.auPage); refreshCollection(); rememberCollectionRoute(true); collectionSettled(); } }
      else if (target.hasAttribute('data-au-nav')) { if (busy) return; target.dataset.auNav === 'knowledge' ? showKnowledge() : target.dataset.auNav === 'intake' ? showIntake() : target.dataset.auNav === 'demonstration' ? showDemonstration() : showWork(); }
      else if (target.hasAttribute('data-au-claim')) { if (!busy) { if (view === 'work') collection.opener = target.dataset.auClaim; openClaim(target.dataset.auClaim); } }
      else if (target.hasAttribute('data-au-demo-mode')) { demoMode = !publicReadOnly && target.dataset.auDemoMode === 'live' ? 'live' : 'replay'; refreshDemonstration(); route(`#autonomous/demonstration?mode=${demoMode}`); }
      else if (target.hasAttribute('data-au-demo-play')) beginPresentation();
      else if (target.hasAttribute('data-au-inspection-clear')) { operationPeek = null; host.removeAttribute?.('data-au-inspection-operation'); renderClaim(); }
      else if (target.hasAttribute('data-au-operation-skip')) skipOperations();
      else if (target.hasAttribute('data-au-demo-stop')) { pausePresentation(); renderClaim(); }
      else if (target.hasAttribute('data-au-demo-resume')) resumePresentation();
      else if (target.hasAttribute('data-au-start')) { if (target.getAttribute?.('aria-disabled') !== 'true') startOriginal(target); }
      else if (target.hasAttribute('data-au-refresh-claim')) { if (!busy && current) { pauseInspection(); if (presentationMode === 'replay') openClaim(current.claim_id,true,{mode:'replay',through:replayRecord.through_seq,detail,node:selected,...evidenceContext}); else { freshClaim = false; synchronizeAuthority('refreshing'); disconnected = true; cancelPoll(); serviceStatus(epoch,true).catch(() => {}); poll(); } } }
      else if (target.hasAttribute('data-au-collection-scope')) { if (busy) return; collection.scope = target.dataset.auCollectionScope === 'added' ? 'added' : 'originals'; collection.domain = 'all'; collection.search = ''; collection.filter = 'all'; collection.page = 1; showWork(true,true); }
      else if (target.hasAttribute('data-au-domain')) { if (view !== 'work') return; collection.domain = target.dataset.auDomain; collection.page = 1; refreshCollection(); rememberCollectionRoute(true); collectionSettled(); }
      else if (target.hasAttribute('data-au-pause')) controlWork(target,'pause');
      else if (target.hasAttribute('data-au-resume')) controlWork(target,'resume');
      else if (target.hasAttribute('data-au-refresh-claims')) { const token = epoch; loadClaims(token,true).catch(error => { if (!disposed && token === epoch) notice(error.message,true); }); }
      else if (target.hasAttribute('data-au-knowledge')) { if (!busy) showKnowledge(true,{knowledge_id:target.dataset.auKnowledge,version:target.dataset.auVersion,knowledge_sha256:target.dataset.auKnowledgeSha,definition_sha256:target.dataset.auDefinitionSha,claim_id:target.dataset.auKnowledgeClaim}); }
      else if (target.hasAttribute('data-au-add-files')) { pauseInspection(); setDetail('sources',true); }
      else if (target.hasAttribute('data-au-expand-process')) {
        pauseInspection(); const expanding = target.getAttribute('aria-expanded') !== 'true'; setGraphExpanded(expanding); drawEdges();
        if (expanding) revealExpandedProcess();
      }
      else if (target.hasAttribute('data-au-detail')) {
        pauseInspection(); setDetail(target.dataset.auDetail);
        // A missing document named by the result opens at its own checklist row.
        const type = target.dataset.auOutcomeDocument, row = type ? [...host.querySelectorAll('[data-au-panel="documents"] .au-obligation')].find(element => element.dataset.auDocument === type) : null;
        if (row) { row.querySelector('.au-document-choice,.au-document-step,.au-document-record')?.focus({preventScroll:true}); row.scrollIntoView?.({block:'nearest',behavior:reduced?.matches ? 'instant' : 'smooth'}); }
      }
      else if (target.hasAttribute('data-au-back-process')) {
        const node = [...host.querySelectorAll('[data-au-node]')].find(element => element.dataset.auNode === selected);
        node?.focus({preventScroll:true}); revealGraphNode(node); drawEdges();
        const bounds = node?.getBoundingClientRect?.();
        if (bounds && (bounds.top < 0 || bounds.bottom > (root.innerHeight || Infinity))) node.scrollIntoView?.({block:'center',behavior:reduced?.matches ? 'instant' : 'smooth'});
      }
      else if (target.hasAttribute('data-au-fact-select') || target.hasAttribute('data-au-document-select')) {
        pauseInspection();
        if (view !== 'claim') return;
        const relations=evidenceRelationships(current,selected,evidenceContext);
        if (target.hasAttribute('data-au-fact-select')) {
          const id=target.dataset.auFactSelect;if (!relations.facts.some(fact => fact.fact_id === id)) return;
          const compatible = relations.documents.find(item => list(item.required_fact_ids).includes(id));
          if (compatible && !list(relations.document?.required_fact_ids).includes(id)) evidenceContext={document:compatible.document_type,obligation:requirementIdentity(compatible)};
          evidenceContext={...evidenceContext,fact:id,trace:relations.fact?.fact_id === id ? !evidenceContext.trace : true};
        } else {
          const type=target.dataset.auDocumentSelect, obligation=target.dataset.auObligationSelect;
          const requirement=relations.documents.find(item => item.document_type === type && (!obligation || requirementIdentity(item) === obligation));if (!requirement) return;
          const fact=list(requirement.required_fact_ids).find(id => relations.facts.some(item => item.fact_id === id));
          evidenceContext={document:type,obligation:requirementIdentity(requirement),fact};
        }
        renderSelection(); rememberSelectionRoute();
      }
      else if (target.hasAttribute('data-au-node-previous') || target.hasAttribute('data-au-node-next')) {
        pauseInspection();
        if (view !== 'claim' || !current?.graph || target.disabled) return;
        const nodes = layoutGraph(current.graph).nodes, index = nodes.findIndex(node => node.node_id === selected), direction = target.hasAttribute('data-au-node-previous') ? -1 : 1, node = nodes[index+direction];
        if (!node) return;
        selected = node.node_id; chosenNode = selected; evidenceContext = {}; setDetail('step',false,false); renderSelection(true); rememberSelectionRoute();
        const control = host.querySelector(direction < 0 ? '[data-au-node-previous]' : '[data-au-node-next]'), selectedNode = [...host.querySelectorAll('[data-au-node]')].find(element => element.dataset.auNode === selected);
        (control && !control.disabled ? control : selectedNode)?.focus({preventScroll:true});
        revealGraphNode(selectedNode,true); drawEdges();
        const bounds = selectedNode?.getBoundingClientRect?.();
        if (bounds) {
          const offset = bounds.top < 16 ? bounds.top-16 : Math.max(0,bounds.bottom-root.innerHeight+16);
          if (offset) root.scrollBy?.(0,offset);
        }
      }
      else if (target.hasAttribute('data-au-node') || target.hasAttribute('data-au-select')) {
        pauseInspection();
        const id=target.dataset.auNode || target.dataset.auSelect;
        if (!list(current?.graph?.nodes).some(node => node.node_id === id)) return;
        const changed=selected !== id; selected=id; chosenNode=id; if (operationPeek) operationPeek.node=id;
        if (target.dataset.auSelectDocument) {
          const relations=evidenceRelationships(current,id), requirement=relations.documents.find(item => item.document_type === target.dataset.auSelectDocument && requirementIdentity(item) === target.dataset.auSelectObligation);
          if (requirement) evidenceContext={document:requirement.document_type,obligation:requirementIdentity(requirement),fact:list(requirement.required_fact_ids).includes(target.dataset.auSelectFact) ? target.dataset.auSelectFact : undefined};
          else evidenceContext={};
        } else if (changed) evidenceContext={};
        setDetail('step',false,false); renderSelection(changed); rememberSelectionRoute();
        const node=[...host.querySelectorAll('[data-au-node]')].find(element => element.dataset.auNode === selected);
        node?.focus({preventScroll:true});
        // A step chosen on the settled map answers below the recorded result.
        // When that answer is not fully in view it is scrolled in; if the
        // chosen step would then leave the screen, focus moves with the view
        // to the answer's heading, and "Back to the steps" returns.
        revealStepAnswer(node);
      } else if (target.hasAttribute('data-au-source')) {
        let citation; try { citation = target.dataset.auCitation ? JSON.parse(target.dataset.auCitation) : null; } catch (_) { notice('The source reference is invalid.',true); return; }
        if (view === 'knowledge' && target.dataset.auKnowledgeSourceClaim) openKnowledgeSource(target.dataset.auKnowledgeSourceClaim,target.dataset.auSource,citation,target);
        else openSource(target.dataset.auSource,citation,target);
      } else if (target.hasAttribute('data-au-close')) closeSource();
    }
    function input(event) {
      if(view==='knowledge' && event.target.hasAttribute?.('data-au-learning-scrub')){const index=Number(event.target.value);if(learningState)learningState.complete=false;pauseLearning();selectLearning(index,10,true);return;}
      if (event.isTrusted && event.target.hasAttribute?.('data-au-operation-scrub') && operationTrace) {
        pauseInspection(); operationPeek = operationInspection(operationTrace,Math.min(Number(event.target.value),operationTrace.rows.length-1));
        if (operationPeek) { host.setAttribute('data-au-inspection-operation',operationPeek.trace.current.id); renderClaim(); }
        return;
      }
      if (view === 'work' && event.target.matches?.('[data-au-claim-search]')) { collection.search = event.target.value; collection.page = 1; queueCollectionSearch(); refreshCollection(); rememberCollectionRoute(); routeTitle(collectionTitle()); }
    }
    function restoreSourceFocus(returning) {
      if (!returning) return;
      (returning.element?.isConnected && focusEligible(returning.element,returning.token) ? returning.element : focusTarget(returning.token) || host.querySelector('[data-au-claim-title]'))?.focus({preventScroll:true});
    }
    function closeSource() {
      if (!dialog.open) return;
      const returning = dialogReturn; dialogReturn = null; sourceEpoch++; clearNativeSource(); dialog.close(); restoreSourceFocus(returning);
    }
    function closed() {
      if (dialog.open || !dialogReturn) return;
      const returning = dialogReturn; dialogReturn = null; sourceEpoch++; clearNativeSource(); restoreSourceFocus(returning);
    }
    function visibility() {
      if(doc.hidden && view==='knowledge')pauseLearning();
      if (doc.hidden) { if (!recordedPacket) packetLoadController?.abort(); savedSnapshotController?.abort(); cancelNextOperationOpening(demoSession || pausedPresentation); }
      motion?.cancel(); selectionMotion?.cancel(); interactionMotion?.cancel();
      if (doc.hidden) {
        cancelWarmReads();
        if (demoTimer) root.clearTimeout(demoTimer); demoTimer = null;
        if (demoSession?.mode === 'operations') { cancelStageMotion(); const pane = host.querySelector('.au-operation-passage'); pane?.scrollTo?.({top:pane.scrollTop,behavior:'instant'}); demoSession.operationWake?.(); }
        // Backgrounding suspends verified replay, not the user's inspection.
        // A live presentation cannot dispatch a new case on visibility restore.
        if (demoSession?.mode === 'live') stopPresentation();
        cancelPoll(); freshClaim = false; statusAuthority = null;
        if (presentationMode !== 'replay') synchronizeAuthority('refreshing');
        return;
      }
      if (demoSession?.mode === 'replay' && !demoSession.replayHead && !demoSession.preparing && !pendingRoute()) { openPresentationCase(demoSession); return; }
      if (view === 'claim') {
        if (presentationMode === 'replay') {
          if (pendingRoute()) return;
          const session = demoSession;
          if (!claimRenderComplete && current) renderClaim();
          if (session) {
            if (session.failure) { presentationFailed(session,session.failure); return; }
            // Resume one full reading interval; hidden time never causes catch-up.
            session.displayedAt = Date.now(); if (session.mode === 'operations') session.operationWake?.(); else startReplay(session,epoch);
          }
        } else { disconnected = true; cancelPoll(); serviceStatus(epoch,true).catch(() => {}); current ? poll() : openingId ? loadOpenedClaim(openingId,epoch) : schedule(); }
      }
    }
    function keyboardInput(event) {
      if(view==='knowledge' && event.key==='Tab' && container.contains(event.target))pauseLearning();
      if(view==='knowledge' && knowledgeMode==='learning' && learningState && container.contains(event.target) && !dialog.open && !recordDialog.open && !event.target?.closest?.('input,textarea,select,button,a,summary,[contenteditable=true]')) {
        if([' ','ArrowLeft','ArrowRight','Home','End'].includes(event.key) && !event.altKey && !event.ctrlKey && !event.metaKey){event.preventDefault();if(event.key===' '){if(learningState?.playing)pauseLearning();else playLearning();}else{pauseLearning();selectLearning(event.key==='Home'?0:event.key==='End'?learningState?.model.events.length-1:(learningState?.index||0)+(event.key==='ArrowRight'?1:-1),10,true);}return;}
        if(event.key==='Tab')pauseLearning();
      }
      if (event.isTrusted && (['Tab','PageDown','PageUp','Home','End'].includes(event.key) || event.key?.startsWith('Arrow'))) { keyboard=true;container.setAttribute('data-au-keyboard','true');pauseInspection();motion?.cancel();selectionMotion?.cancel();interactionMotion?.cancel(); } }
    function focusInput(event) {
      claimWarmIntent(event);
      const target = event.target?.closest?.('[data-au-inspect],[data-au-source],[data-au-node],[data-au-select],[data-au-detail],[data-au-fact-select],[data-au-document-select],[data-au-expand-process],[data-au-graph-pan]');
      if (target && (demoSession || pausedPresentation) && !target.closest('[data-au-demo-play],[data-au-demo-stop],[data-au-demo-resume]')) pauseInspection();
      if (view === 'knowledge' && learningState?.playing && event.target?.closest?.('[data-au-learning-event],[data-au-knowledge-facet],[data-au-learning-focus]')) pauseLearning();
    }
    function pointerInput(event) {
      keyboard=false;container.removeAttribute('data-au-keyboard');
      if(view==='knowledge' && event?.isTrusted && !event.target?.closest?.('[data-au-learning-play]'))pauseLearning();
      const target = event?.isTrusted && event.target?.closest?.('.au-operation-passage,summary,[data-au-operation-scrub],[data-au-inspect],[data-au-source],[data-au-node],[data-au-select],[data-au-detail],[data-au-fact-select],[data-au-document-select],[data-au-expand-process]');
      if (target && container.contains(target)) pauseInspection();
    }
    function sourceWheel(event) { if (event.isTrusted && event.target?.closest?.('.au-operation-stage')) { pauseInspection(); attentionMarker?.remove?.(); } }
    function motionPreference() { if (reduced?.matches) { if(view==='knowledge' && learningState){pauseLearning();selectLearning(learningState.index,10,true,false);}  skipOperations(); motion?.cancel();selectionMotion?.cancel();interactionMotion?.cancel(); } }
    doc.addEventListener('keydown',keyboardInput);container.addEventListener('pointerdown',pointerInput);reduced?.addEventListener?.('change',motionPreference);
    container.addEventListener('wheel',sourceWheel,{passive:true});
    function geometryEvent(event) { if (event.target?.matches?.('.au-operation-passage')) { if (host.querySelector('.au-operation-stage')) return; if (!doc.hidden && !inspectionHold) { positionOperationAttention(false); drawEdges(); } return; } if (event.type === 'toggle') { drawEdges(); if (event.target?.open) interact(event.target.querySelector(':scope > :not(summary)')); } else if (event.target?.hasAttribute?.('data-au-graph-pan')) drawEdges(); }
    container.addEventListener('scroll',geometryEvent,true);container.addEventListener('toggle',geometryEvent,true);
    doc.fonts?.ready?.then(() => { if (!disposed) {fitActiveStage();syncGraphViewport();drawEdges();} });
    container.addEventListener('click',click); container.addEventListener('pointerover',claimWarmIntent); container.addEventListener('focusin',focusInput); container.addEventListener('submit',submit); container.addEventListener('change',change); container.addEventListener('input',input); dialog.addEventListener('close',closed); recordDialog.addEventListener('close',closedRecord); doc.addEventListener('visibilitychange',visibility);
    root.addEventListener?.('hashchange',routeChanged); root.addEventListener?.('popstate',routeChanged);
    function fitActiveStage() {
      host.querySelector('.au-operation-stage .au-graph-viewport')?.style.removeProperty('--au-stage-available-height');
      headerReturn(); measureChrome(); observeChrome();
    }
    // Sticky chrome heights stay current: only chrome that actually sticks is
    // counted, and the case bands count only inside a claim. The page's scroll
    // padding reads the same values from the root element.
    const CHROME = [['header','.au-identity-header'],['transport','.au-quiet-claim > .au-demo-transport'],['now','.au-quiet-claim > .au-now']];
    function measureChrome() {
      if (disposed) return;
      for (const [name,selector] of CHROME) {
        const element = container.querySelector(selector), style = element && root.getComputedStyle?.(element);
        const sticks = Boolean(element) && (name === 'header' || view === 'claim') && (!style || ['sticky','fixed'].includes(style.position));
        const value = `${Math.ceil(sticks ? element.getBoundingClientRect?.().height || 0 : 0)}px`;
        container.style?.setProperty?.(`--au-${name}-height`,value);
        doc.documentElement?.style?.setProperty?.(`--au-${name}-height`,value);
      }
    }
    const chromeObserver = root.ResizeObserver ? new root.ResizeObserver(() => measureChrome()) : null;
    // Phones, while a case plays: the header leaves the stack of sticky chrome so the replay row and
    // the Now line stay small, and it comes back on the first upward touch or wheel scroll, so the
    // navigation is always one gesture away. Focus-driven scrolling never brings it back over a
    // focused control.
    const phoneChrome = root.matchMedia?.('(max-width:700px)');
    let chromeY = root.scrollY || 0, chromeFrame = 0, scrollIntent = 0;
    function scrollIntentEvent() { scrollIntent = Date.now(); }
    function chromeScroll() {
      if (disposed || chromeFrame) return;
      if (!root.requestAnimationFrame) { headerReturn(); return; }
      chromeFrame = root.requestAnimationFrame(() => { chromeFrame = 0; headerReturn(); });
    }
    function headerReturn() {
      const header = container.querySelector('.au-identity-header'); if (disposed || !header) return;
      const y = root.scrollY || 0, playing = Boolean(phoneChrome?.matches && view === 'claim' && container.querySelector('.au-quiet-claim > :is(.au-demo-transport,.au-now:not(.au-last))'));
      const was = Boolean(header.hasAttribute?.('data-au-header-return'));
      let back = was;
      if (!playing || y <= 0) back = false;
      else if (y < chromeY - 4) back = back || Date.now() - scrollIntent < 700;
      else if (y > chromeY + 4) back = false;
      if (Math.abs(y - chromeY) > 4 || !playing) chromeY = y;
      if (back !== was) { if (back) header.setAttribute?.('data-au-header-return',''); else header.removeAttribute?.('data-au-header-return'); measureChrome(); }
    }
    root.addEventListener?.('scroll',chromeScroll,{passive:true});
    for (const type of ['wheel','touchmove']) doc.addEventListener?.(type,scrollIntentEvent,{passive:true});
    function observeChrome() {
      if (!chromeObserver || disposed) return;
      chromeObserver.disconnect();
      for (const [,selector] of CHROME) { const element = container.querySelector(selector); if (element) chromeObserver.observe(element); }
    }
    function centerActiveOperation(force = false) {
      const viewport = host.querySelector('.au-operation-stage .au-graph-viewport');
      if (!viewport || doc.hidden) return;
      const width = viewport.getBoundingClientRect().width;
      if (!force && graphViewportWidth === width) return;
      graphViewportWidth = width;
      const trace = operationPeek?.trace || operationTrace, operation = trace?.current;
      const id = operationNodeId(operation,operationStageGraph(trace,current || {}),current || {},trace);
      const mark=[...host.querySelectorAll('[data-au-operation-span]')].find(element=>element.dataset.auOperationSpan===operation?.id);
      const sourceStep=mark?.closest('[data-au-stage-step]'), node=sourceStep || [...host.querySelectorAll('[data-au-stage-step]')].find(element=>element.dataset.auStageStep===id);
      if (node) revealGraphNode(sourceStep?.querySelector('.au-stage-source') || node,true);
      positionOperationSource();
    }
    let cueViewport = `${root.innerWidth}:${root.innerHeight}`;
    function resized() {
      syncGraphViewport();
      if (host.querySelector('.au-operation-stage')) {
        const nextViewport=`${root.innerWidth}:${root.innerHeight}`;
        if ((root.innerWidth || 0) <= 700 || cueViewport !== nextViewport) cancelStageMotion();
        cueViewport=nextViewport; fitActiveStage();centerActiveOperation();drawEdges();return;
      }
      const area=host.querySelector('.au-graph-viewport')?.getBoundingClientRect?.();
      if (!host.querySelector('[data-au-forming="true"]') && area && graphViewportWidth !== null && area.width !== graphViewportWidth) revealGraphNode([...host.querySelectorAll('[data-au-node]')].find(element => element.dataset.auNode === selected));
      drawEdges(); positionOperationAttention();
    }
    const resize = root.ResizeObserver ? new root.ResizeObserver(resized) : null; resize?.observe(host); root.addEventListener?.('resize',resized);
    const controller = {openClaim,showWork,showIntake,showKnowledge,showDemonstration,recordedPacketReady:Promise.resolve().then(loadRecordedPacket),savedSnapshotReady:savedSnapshotLoad=Promise.resolve().then(loadSavedSnapshot),refresh:poll,destroy() { if (disposed) return; disposed = true; root.clearTimeout(collectionSearch.timer); collectionSearch.read++; if (doc && doc.title !== originalTitle) doc.title = originalTitle; try { if (originalScrollRestoration && root.history) root.history.scrollRestoration = originalScrollRestoration; } catch (_) { /* the browser keeps its own setting */ } discardKnowledgeOpening(); cancelLearning(); packetLoadController?.abort(); savedSnapshotController?.abort(); cancelStageMotion(); epoch++; cancelWarmReads(); storageWrite++; cancelPoll(); stopPresentation(); clearNativeSource(); motion?.cancel(); selectionMotion?.cancel(); interactionMotion?.cancel(); snapshots.clear(); sourcePreviews.clear(); nativeBytes.clear(); replayPrefixes.clear(); inflightReads.clear();root.removeEventListener?.('resize',resized);root.removeEventListener?.('hashchange',routeChanged);root.removeEventListener?.('popstate',routeChanged);doc.removeEventListener('keydown',keyboardInput);container.removeEventListener('pointerdown',pointerInput);container.removeEventListener('wheel',sourceWheel);reduced?.removeEventListener?.('change',motionPreference); for (const controller of controllers) controller.abort(); resize?.disconnect();chromeObserver?.disconnect();if (chromeFrame) root.cancelAnimationFrame?.(chromeFrame);root.removeEventListener?.('scroll',chromeScroll);for (const type of ['wheel','touchmove']) doc.removeEventListener?.(type,scrollIntentEvent);for (const [name] of CHROME) doc.documentElement?.style?.removeProperty?.(`--au-${name}-height`);container.removeEventListener('scroll',geometryEvent,true);container.removeEventListener('toggle',geometryEvent,true); container.removeEventListener('click',click); container.removeEventListener('pointerover',claimWarmIntent); container.removeEventListener('focusin',focusInput); container.removeEventListener('submit',submit); container.removeEventListener('change',change); container.removeEventListener('input',input); dialog.removeEventListener('close',closed); recordDialog.removeEventListener('close',closedRecord); doc.removeEventListener('visibilitychange',visibility); if (dialog.open) dialog.close(); if (recordDialog.open) recordDialog.close(); mounts.delete(container); if (activeMount === controller) activeMount = null; container.innerHTML = ''; }};
    mounts.set(container,controller); activeMount = controller;
    sessionRestore = restoreReadCache();
    if (options.recordedPacket) packetAcquisition = {promise:controller.recordedPacketReady.then(ready => { if (!ready) throw new Error('The recorded packet asset is unavailable.'); return recordedPacket; })};
    packetAcquisition?.promise.catch(() => {});
    routeChanged();
    return controller;
  }
  function destroy(container) { (container ? mounts.get(container) : activeMount)?.destroy(); }
  return {DESK_STEPS,DESK_LEGAL_TESTS,deskLegalLabel,deskLegalStatus,deskStepLabel,deskRequest,deskLaw,agentDeskMarkup,deskOperationModel,deskFileLabel,deskDraftBinding,checkedDeskDraft,caseProcedureMarkup,similarCases,similarCasesMarkup,caseDomain,knowledgeLibraryMarkup,knowledgeLibrary,libraryEntryMarkup,definitionMarkup,baseOutlineMarkup,conditionSentence,libraryStepsMarkup,RECORD_DIALOG_SKELETON,recordExplanation,recordPassageMarkup,outcomeSummaryMarkup,stepDetailMarkup,demoRoster,collectionRoster,demoCollection,DEMO_COLLECTIONS,caseLabel,demoPickerMarkup,demoTransportMarkup,resultReached,knowledgePayoff,knowledgePayoffMarkup,tourKnowledgePayoff,learningChangeSummary,learningFrameStart,learningProcessMarkup,recordedReuseMoment,recordedReuseMomentMarkup,knowledgeLearningModel,knowledgeLearningFocus,knowledgePinMatches,learningEventLabel,learningTime,checkedSavedSnapshotAsset,checkedRecordedPacket,decodeRecordedSession,checkedAtomicOperationHead,RELEASE_PROCEDURE_OUTLINE,releaseOperationProcess,releaseOpeningMatches,releaseHeadMatches,releaseProcedurePreview,operationFrameYield,claimFragment,operationRoutePreference,plannedOperationProcess,operationStageGraph,operationReadDuration,operationChoreographyTiming,operationCues,completedStepFraction,bufferedOperationCount,operationInspection,sourceBodySpan,operationReading,stageFactSpan,stageFactText,operationStageMarkup,stageNodeContents,operationAttention,operationFrames,bufferedOperations,checkedOperationBinding,checkedOperation,checkedOperationCheckpoint,operationReadingMarkup,operationHistoryMarkup,operationRecord,operationLabel,currentSourceSelection,checkedReferenceReplayStart,checkedReferenceReplayOpening,enteredRequirementContext,formingRequirements,conditionLabel,legalBasisMarkup,sourceExcerpt,referenceSourcePin,REFERENCE_DEMO_CASES,referenceExecution,claimStatusLabel,intakeGate,intakeEligible,intakeMarkup,sourceKind,claimAvailability,formingPublication,formingRelations,formingWork,formingMarkup,formingKnowledgeMarkup,knowledgeOriginMarkup,documentReviewMarkup,checkedSavedSnapshot,checkedReadCache,factCaseText,readKnowledge,readableSourceText,collectionPage,paginationMarkup,catalogPreviewMarkup,unknownClaimMarkup,historyLabel,actionLabel,procedureScope,knowledgeFacetMarkup,sourceObjectIdentity,consequentialEventNode,replayContentPacing,procedureLabel,acquiredContentMarkup,contextualRecord,roleBadge,boundDisplayReceipt,operationDisplayContext,knowledgeNowMarkup,nowMarkup,outcomeSummaryMarkup,recordButton,claimKnowledgeMarkup,openingContentMarkup,acceptedEventNode,acceptedEventContext,preferredEvidenceContext,claimHeadingMarkup,eventCueMarkup,readSkeletonMarkup,assessmentFreshness,assessmentFreshnessMarkup,semanticEventRecord,lastSemanticEvent,semanticEventMarkup,evidenceSelection,requirementIdentity,DEMO_CASES,DOMAINS,replayCanAdvance,demoItineraryMarkup,canonicalJSON,workingOperationScope,applyWorkingOperation,workingProcessState,workingReadiness,operationNodeId,operationRelationship,checkedPreview,readSnapshot,readReplay,demonstrationMarkup,demonstrationOverviewMarkup,learningLabel,claimModeLine,rosterUnrun,startControlMarkup,liveAvailability,preferredNode,evidenceRelationships,evidencePathMarkup,knowledgeUses,edgeState,mount,destroy,demoAssetURL,checkedExamples,prefillExample,progressModel,progressMarkup,transitionPlan,animateTransition,mediaType,readState,layoutGraph,acceptEvents,eventIdentity,changedTargets,conditionFlags,checkedSource,graphMarkup,obligationMarkup,inspectorMarkup,workMarkup,knowledgeMarkup,claimsMarkup,collectionMarkup,matchingClaims,actionRows};
});
