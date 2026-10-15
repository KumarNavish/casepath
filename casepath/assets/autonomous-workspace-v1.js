/* Autonomous work is rendered from persisted state and its matching event cursor. */
(function (root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.CasePathAutonomous = api;
})(typeof globalThis === 'object' ? globalThis : this, function (root) {
  'use strict';
  const BASE = '/api/claim-loops/v1/autonomous';
  const PUBLIC_READ_ONLY_MESSAGE = 'The public workspace is read-only. Browse saved cases, original sources, verified replay and Knowledge.';
  const readOnlyAccess = status => root.CASEPATH_PUBLIC_READ_ONLY === true || status?.read_only === true || status?.writable === false;
  const READ_CACHE_CONTRACT = 'casepath.read-cache/1';
  const READ_CACHE_BYTES = 2 * 1024 * 1024, READ_CACHE_AGE = 15 * 60 * 1000;
  const DOMAINS = Object.freeze([
    {id:'defect_mold_heating',label:'Defects & repairs'},
    {id:'lease_termination_dispute',label:'Lease termination'},
    {id:'rent_increase_dispute',label:'Rent changes'}
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
  const demoCases = collection => collection === 'legacy' ? DEMO_CASES : REFERENCE_DEMO_CASES;
  const replayCollection = (id, collection) => ['reference','legacy'].includes(collection) ? collection : REFERENCE_DEMO_CASES.some(row => row.claim_id === id) ? 'reference' : DEMO_CASES.some(row => row.claim_id === id) ? 'legacy' : 'reference';
  const mounts = new WeakMap();
  let activeMount = null;
  const h = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const list = value => Array.isArray(value) ? value : [];
  const words = value => String(value ?? '').replace(/[_.-]+/g, ' ').replace(/^./, c => c.toUpperCase());
  const text = value => typeof value === 'string' ? value : '';
  const name = item => item?.label || item?.title || item?.name || words(item?.node_id || item?.document_type || item?.fact_id || item?.type || item?.action_id || item?.kind);
  const dateLabel = value => { const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value || '') : new Intl.DateTimeFormat('en', {dateStyle:'medium',timeStyle:'short'}).format(date); };
  const key = value => encodeURIComponent(String(value));
  const button = (label, attr, primary = false) => `<button type="button" class="${primary ? 'au-primary' : 'au-secondary'}" ${attr}>${h(label)}</button>`;
  const complete = status => ['completed','complete','resolved'].includes(status);
  const referenceAssessmentComplete = claim => claim?.policy_id === 'casepath.bounded-reference-assessment/1.0.0' && claim.outcome?.assessment_status === 'complete' && claim.outcome.reference_provenance?.mode === 'deterministic_reference' && claim.outcome.reference_provenance.synthetic === true && !claim.deferral && !active(claim.status);
  const statusFilter = (status, claim) => referenceAssessmentComplete(claim) || complete(status) ? 'investigation_complete' : status;
  const active = status => ['received', 'queued', 'running', 'working', 'investigating'].includes(status);
  const tone = status => ['completed', 'complete', 'resolved', 'established', 'satisfied', 'qualified'].includes(status) ? 'done' : ['deferred', 'blocked', 'failed', 'unresolved', 'unknown', 'quarantined'].includes(status) ? 'blocked' : active(status) || status === 'ready' ? 'active' : 'neutral';
  const statusLabel = status => ({not_started:'Not started',not_run:'Not run',received:'Received', queued:'Queued', running:'Working', working:'Working', completed:'Completed', complete:'Completed', resolved:'Completed', investigation_complete:'Investigation complete', deferred:'Deferred', failed:'Stopped', ready:'Ready to check', true:'Applies', false:'Does not apply', insufficient:'Not established', missing:'Not established', prepared_not_sent:'Prepared · not sent', not_reached:'Not reached', inactive:'Does not apply', unresolved:'Not established', unknown:'Not established', blocked:'Waiting for prerequisites', established:'Established', satisfied:'Satisfied', needed_now:'Needed now', needed_later:'Needed later', held_behind_question:'May be needed', held_not_reviewed:'Needs checking', not_needed:'Not required', optional:'Optional'})[status] || words(status) || 'Not recorded';
  function claimStatusLabel(status, claim = {}) {
    if (status === 'failed' || !active(status) && list(claim.reconciliations).at(-1)?.status === 'failed') return 'Execution failed';
    if (!active(status) && claim.deferral) {
      if (claim.deferral.code === 'paused') return 'Paused';
      return ['provider_deferred','verification_deferred','execution_deferred'].includes(claim.deferral.code) ? 'Execution failed' : 'Execution stopped';
    }
    if (referenceAssessmentComplete(claim)) return 'Assessment complete';
    if (complete(status)) return 'Investigation complete';
    return status === 'deferred' ? claim.outcome ? 'More evidence needed' : 'Execution stopped' : statusLabel(status);
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
  function claimAvailability(status, state, projection) {
    if (!writable(status)) return {ready:false,reason:'This workspace is read-only.'};
    if (!intakeEligible(projection)) return {ready:false,reason:'Complete the source-backed intake requirements before starting.'};
    if (REFERENCE_DEMO_CASES.some(row => row.claim_id === state?.claim_id)) return {ready:false,reason:'Synthetic reference assessments are available through recorded replay.'};
    return liveAvailability(status);
  }
  function intakeMarkup(state, projection = {}) {
    const gate = intakeGate(projection);
    if (!gate) return '';
    const label = ({complete:'Intake complete',incomplete:'Intake incomplete',unsupported:'More information needed'})[gate.status] || 'More information needed';
    return `<section class="au-intake-inspection" data-au-intake-gate="${h(gate.status)}"><div class="au-section-heading"><h2>${h(label)}</h2>${recordButton('Details','intake')}</div>${list(gate.checklist).length ? `<ul class="au-intake-checklist">${list(gate.checklist).map(row => `<li data-au-intake-document="${h(row.document_type)}" data-status="${h(row.status)}"><div><strong>${h(row.label || words(row.document_type))}</strong><span>${h(({sufficient:'Source support present',missing:'Missing',insufficient:'Needs more support'})[row.status] || 'Not established')}</span></div><div class="au-related">${list(row.artifact_ids).filter(id => list(state.source_descriptors).some(source => source.artifact_id === id)).map(id => button(sourceLabel(state,id),`data-au-source="${h(id)}" data-au-source-origin="intake:${h(row.document_type)}:${h(id)}"`)).join('')}</div></li>`).join('')}</ul>` : '<p class="au-meta">Describe the issue and provide the relevant documents to begin an assessment.</p>'}</section>`;
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
    return ['SYNTHETIC SUPPLEMENT — FICTIONAL DEMONSTRATION SOURCE\n','Synthetic demonstration document (fictional)\n'].some(header => acquired?.text?.startsWith(header)) || referenceSourcePin(state,source,projection) ? 'Synthetic demonstration document' : source.role === 'customer_message' ? 'Original source' : 'Supporting source';
  }
  function legalBasisMarkup(state) {
    const context = state.semantic_contexts?.[state.run_id];
    if (context?.execution_mode !== 'deterministic_reference') return '';
    const pack = list(context.rule_packs).find(row => row.family === state.graph?.family), authorities = list(pack?.legal_authority);
    const finalRefs = state.outcome?.assessment_status === 'complete' ? new Set(list(state.outcome.legal_predicates).flatMap(row => list(row.rule_refs)).map(ref => /^CO:(\d+[a-z]?)$/.exec(ref)?.[1]).filter(Boolean)) : null;
    const rows = authorities.filter(row => typeof row.article === 'string' && typeof row.text === 'string' && (!finalRefs || finalRefs.has(row.article)));
    const official = value => { try { const url = new URL(value); return url.protocol === 'https:' && ['www.fedlex.admin.ch','fedlex.admin.ch','fedlex.data.admin.ch'].includes(url.hostname) ? url.href : null; } catch (_) { return null; } };
    const links = rows.map(row => { const url = official(row.source?.publisher_url); return url ? `<a href="${h(url)}" target="_blank" rel="noopener noreferrer" data-au-law-article="${h(row.article)}" title="${h(`CO ${row.article} · Fedlex ${row.source.consolidation_date || ''}`)}">CO ${h(row.article)}</a>` : h(`CO ${row.article}`); });
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
    if (kind === 'withheld-index') return list(data.quarantined);
    if (kind === 'knowledge') return list(data.versions).find(row => `${row.knowledge_id || row.version_id}:${row.version || row.version_id}` === id);
    if (kind === 'use') return list(state?.knowledge_uses).concat(list(data.uses))[Number(id)];
    if (kind === 'publication') return list(state?.knowledge_published)[Number(id)];
    if (kind === 'quarantine') return list(data.quarantined)[Number(id)];
    return null;
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
    return `<section class="au-reading-passages au-reading-acquisition"><h3 class="au-reading-label">Readable sources</h3>${acquired.map(source => `<button type="button" class="au-source-link au-evidence-source" data-au-source-identity="${h(sourceObjectIdentity(state,source.artifact_id))}" data-au-source="${h(source.artifact_id)}" data-au-source-arrival="${h(source.artifact_id)}" data-au-source-origin="acquisition:${h(source.artifact_id)}"><span class="au-evidence-source-label">${h(source.file_name || sourceLabel(state,source.artifact_id))}<span aria-hidden="true">↗</span></span><pre class="au-original-message au-source-excerpt au-acquired-text">${h(sourceExcerpt(state,source,projection))}</pre><span class="au-meta">${h(sourceKind(state,source))} · ${source.complete ? 'Readable text' : 'Partly readable text'} · Assessment is separate</span></button>`).join('')}</section>`;
  }
  function openingContentMarkup(state, projection = {}) {
    return `<div class="au-reading-column au-opening-content">${originalText(state) ? `<h2>Original message</h2><pre class="au-original-message">${h(originalText(state))}</pre>` : ''}${acquiredContentMarkup(state,projection) || sourceListMarkup(state,list(state.source_descriptors),'originals',projection)}${list(state.knowledge_uses).length ? claimKnowledgeMarkup(state) : ''}</div>`;
  }
  function procedureLabel(item) {
    const id = item.knowledge_id || item.version_id || '', family = item.family || (id.startsWith('procedure.') ? id.slice('procedure.'.length) : '');
    const friendly = {defect_mold_heating:'Defects and repairs',lease_termination_dispute:'Lease termination',rent_increase_dispute:'Rent increases'};
    return friendly[family] || item.name || item.title || words(id) || 'Recorded procedure';
  }
  function claimKnowledgeMarkup(state, events = []) {
    const uses = list(state.knowledge_uses), publications = list(state.knowledge_published);
    const latest = [...events].reverse().filter(event => ['knowledge.used','knowledge.published'].includes(event.kind)).map(event => semanticEventRecord(state,event)).find(Boolean);
    const focus = latest ? {kind:latest.type === 'reused' ? 'use' : 'publication',item:latest.knowledge} : publications.length ? {kind:'publication',item:publications.at(-1)} : uses.length ? {kind:'use',item:uses.at(-1)} : null;
    if (!focus) return '<section class="au-claim-knowledge"><h2>Knowledge in this case</h2><p>No reusable procedure has been recorded for this case.</p></section>';
    const item = focus.item, index = (focus.kind === 'use' ? uses : publications).findIndex(row => canonicalJSON(row) === canonicalJSON(item));
    const qualified = item.qualification?.status === 'qualified';
    const identity = item.knowledge_sha256 || item.knowledge_id || item.version_id || item.candidate_id;
    const applicability = (item.applicability === 'same_verified_family_and_rule_version' ? `Used for this ${({'Lease termination':'lease-termination','Defects and repairs':'defects-and-repairs','Rent increases':'rent-increase'})[procedureLabel(item)] || 'current'} case.` : item.applicability?.summary || '');
    const body = focus.kind === 'use' ? `<article class="au-knowledge-use" data-au-knowledge-use="${h(identity)}"><h3>${h(procedureLabel(item))}</h3><p>Used for this case · Version ${h(item.version || item.version_id)}</p>${applicability ? `<p>${h(applicability)}</p>` : ''}<p>The case still requires its own source evidence.</p>${knowledgeLink(item)}</article>` : `<article class="au-knowledge-publication" data-au-knowledge-publication="${h(identity)}"><h3>${h(procedureLabel(item.candidate || item))}</h3><p>${qualified && item.version ? `Added for reuse · Version ${h(item.version)}` : 'Withheld from reuse'}</p>${qualified ? `${procedureScope(item) !== procedureLabel(item) ? `<p>${h(procedureScope(item))}</p>` : ''}${list(item.added_document_types).length ? `${item.added_document_types.map(type => { const recipe = list(item.evidence_recipes).find(row => row.document_type === type), requirement = list(item.obligations).find(row => row.document_type === type); return `<p class="au-knowledge-change">Added ${h((name(requirement) || words(type)).toLocaleLowerCase())} requirements${list(recipe?.required_fields).length ? `: ${h(recipe.required_fields.map(field => words(field).toLocaleLowerCase()).join(', '))}` : ''}.</p>`; }).join('')}` : list(item.obligations).length ? `<h4>Reusable document requirements</h4><ul class="au-definition-list">${item.obligations.map(obligation => `<li>${h(name(obligation))}</li>`).join('')}</ul>` : ''}${knowledgeLink(item)}` : item.candidate?.summary ? `<h4>Proposed content</h4><p>${h(item.candidate.summary)}</p>` : ''}</article>`;
    const related = uses.filter(use => focus.kind !== 'use' || canonicalJSON(use) !== canonicalJSON(item)).map(use => `<div>Used for this case · ${h(procedureLabel(use))} · Version ${h(use.version || use.version_id)} ${knowledgeLink(use)}</div>`).concat(publications.filter(publication => focus.kind !== 'publication' || canonicalJSON(publication) !== canonicalJSON(item)).map(publication => `<div>${h(procedureLabel(publication.candidate || publication))} </div>`));
    return `<section class="au-claim-knowledge"><h2>Knowledge in this case</h2>${body}${related.length ? `<nav class="au-reading-objects" aria-label="Other knowledge recorded in this case">${related.join('')}</nav>` : ''}</section>`;
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
    return `<section class="au-forming-knowledge" aria-label="Procedure use and additions">${uses.map((use,index) => `<article class="au-knowledge-use" data-au-knowledge-use="${h(use.knowledge_sha256 || use.knowledge_id || use.version_id)}"><h3>${h(procedureLabel(use))}</h3><p>${operationDelivery ? 'Procedure reused' : 'Procedure used for this case'} · Version ${h(use.version || use.version_id)}</p>${knowledgeOriginMarkup(state,use,data,false,operationDelivery)}${knowledgeLink(use)}</article>`).join('')}${publications.map((item,index) => { const qualified = item.qualification?.status === 'qualified', links = `${qualified ? knowledgeLink(item) : ''}${inlineUses.map(use => `<p class="au-forming-used-version" data-au-knowledge-use="${h(use.knowledge_sha256 || use.knowledge_id || use.version_id)}">${knowledgeLink(use,`Used version ${use.version || use.version_id}`)}</p>`).join('')}`; return `<article class="au-knowledge-publication" data-au-knowledge-publication="${h(item.knowledge_sha256 || item.knowledge_id || item.candidate_id)}"><h3>${h(procedureLabel(item.candidate || item))}</h3><p>${qualified ? `${operationDelivery ? 'Historical addition' : 'Added for reuse'} · Version ${h(item.version || item.version_id)}` : 'Withheld from reuse'}</p>${publication ? links + knowledgeOriginMarkup(state,item,data,true) : ''}${qualified ? list(item.added_document_types).map(type => { const recipe = list(item.evidence_recipes).find(row => row.document_type === type), requirement = list(item.obligations).find(row => row.document_type === type); return `<p class="au-knowledge-change">Added ${h((name(requirement) || words(type)).toLocaleLowerCase())} requirements${list(recipe?.required_fields).length ? `: ${h(recipe.required_fields.map(field => words(field).toLocaleLowerCase()).join(', '))}` : ''}.</p>`; }).join('') : item.candidate?.summary ? `<p>${h(item.candidate.summary)}</p>` : ''}${!publication ? knowledgeOriginMarkup(state,item,data) + links : ''}</article>`; }).join('')}</section>`;
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
  function formingMarkup(state, projection, selected, events = [], context = {}, knowledge = {}, attention, settled = false, operations = null) {
    if (operations || settled) return operationStageMarkup(state,projection,selected,operations,settled);
    const activeRows = formingRequirements(state), workingState = workingProcessState(operations), working = workingState && operations.working;
    const processState = workingState || state, processSelected = working ? operationNodeId(operations.current,working.graph,state) || working.graph.nodes[0]?.node_id : selected;
    const publication = formingPublication(state,events,attention), node = list(processState.graph?.nodes).find(item => item.node_id === processSelected), relation = working ? null : formingRelations(state,selected,context), operationRelation = operationRelationship(operations,state);
    const evaluated = list(state.evaluation?.nodes).find(item => item.node_id === selected), capability = projection.node_capabilities?.[selected];
    const binding = relation ? ` data-au-wire-fact="${h(relation.fact)}" data-au-wire-source="${h(relation.source)}" data-au-wire-node="${h(relation.node)}"${relation.obligation ? ` data-au-wire-obligation="${h(relation.obligation)}"` : ''}` : '';
    const operationBinding = operationRelation ? ` data-au-operation-id="${h(operationRelation.operation_id)}" data-au-wire-source="${h(operationRelation.source)}" data-au-wire-node="${h(operationRelation.node)}" data-au-working-graph-sha="${h(operationRelation.graph_sha256)}"` : '';
    const documentOperation = working && operations.current?.kind === 'document.require' ? operations.current : null;
    const documentLabel = documentOperation && name(working.graph.document_catalog.find(row => row.document_type === documentOperation.object.id));
    const processHeading = working ? `<p class="au-reading-label">Working model · provisional ${recordButton('Inspect calculation','operation',working.inspect.id)}</p>` : publication ? `<div class="au-forming-publication-focus" data-au-publication-focus="${h(publication.id)}">${formingKnowledgeMarkup(state,knowledge,true,false,publication.knowledge,list(state.knowledge_uses),Boolean(operations))}</div>` : formingKnowledgeMarkup(state,knowledge,false,!settled,null,[],Boolean(operations));
    return `<section class="au-forming-work" data-au-forming="${!settled}"${settled ? ' data-au-settled="true"' : ''} data-au-forming-revision="${h(state.revision)}" data-au-forming-sha="${h(state.state_sha256)}"><div class="au-forming-layout"><div class="au-forming-reading">${!state.graph ? formingKnowledgeMarkup(state,knowledge,false,true,null,[],Boolean(operations)) : ''}${operationReadingMarkup(operations) || evidencePathMarkup(state,selected,projection,context,true)}${settled && evaluated ? `<div class="au-reading-decision"><p class="au-step-status">${h(statusLabel(evaluated.execution_state || evaluated.state))}</p>${capability?.authorized === false ? `<p class="au-reading-limit">${h(capability.reason || 'Execution is unavailable for this step.')}</p>` : ''}</div>` : ''}</div>${processState.graph ? `<section class="au-forming-process au-evidence-process" aria-label="${working ? 'Provisional working process' : 'Complete recorded process'}"${working ? ` data-au-working-scope="${h(working.inspect.id)}" data-au-working-graph-sha="${h(working.graph.graph_sha256)}" data-au-operation-stage="${h(working.stage)}"` : ''}>${processHeading}${node && !publication ? `<h2 class="au-process-question au-reading-question" tabindex="-1"${working ? ` data-au-operation-id="${h(operations.current?.id || working.inspect.id)}"` : ` data-au-inspector-heading="${h(selected)}"`}>${h(name(node))}</h2>` : ''}${graphMarkup(processState,processSelected,working ? {} : projection,{overview:true,working})}${documentLabel ? `<p class="au-meta" data-au-working-document="${h(documentOperation.object.id)}" data-au-operation-id="${h(documentOperation.id)}">Requirement calculation · ${h(documentLabel)} ${recordButton('Inspect','operation',documentOperation.id)}</p>` : ''}</section>` : ''}${state.graph?.family !== 'incoming_packet' && list(state.obligations).length ? `<aside class="au-forming-documents" data-au-evidence-path aria-label="Recorded document requirements"><h2>Document requirements</h2>${activeRows.length ? obligationMarkup(state,selected,activeRows,context,true) : '<p>Requirements appear when their process step is reached.</p>'}${button('All recorded requirements','data-au-detail="documents"')}</aside>` : ''}<svg class="au-forming-connections" aria-hidden="true"${binding}>${operationRelation ? `<path data-au-forming-wire="operation-source-process"${operationBinding}></path>` : relation ? `<path data-au-forming-wire="source-process"${binding}></path>${relation.obligation ? `<path data-au-forming-wire="process-document"${binding}></path>` : ''}` : ''}</svg></div></section>`;
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
  function graphMarkup(state, selected, projection = {}, options = {}) {
    if (!state.graph) return '';
    const layout = layoutGraph(state.graph), neighborhood = new Set([selected,...(layout.parents.get(selected) || []),...(layout.children.get(selected) || [])]), evaluation = new Map(list(state.evaluation?.nodes).map(node => [node.node_id,node]));
    return `<div class="au-graph-chrome"><button type="button" class="au-link" data-au-expand-process aria-expanded="false" aria-controls="auProcessGraphViewport">${options.overview ? 'Open larger process' : 'Open full process'}</button></div><div id="auProcessGraphViewport" class="au-graph-viewport au-evidence-graph-scroll" data-au-graph-pan data-au-graph-overview="${Boolean(options.overview)}" data-au-graph-expanded="false" tabindex="0" role="region" aria-label="${options.overview ? 'Complete process; use arrow keys or scroll to explore' : 'Selected decision, its prerequisites and following decisions; open full process to explore the complete graph'}"><div class="au-graph au-evidence-graph" data-au-graph${options.working ? ` data-au-working-graph-sha="${h(options.working.graph.graph_sha256)}" data-au-working-scope="${h(options.working.inspect.id)}" data-au-working-evaluation-sha="${h(options.working.inspect.result.evaluation_sha256)}" data-au-operation-stage="${h(options.working.stage)}"` : ''} data-orientation="${options.stage ? 'horizontal' : options.overview ? 'vertical' : 'horizontal'}" style="--au-ranks:${Math.max(1,layout.rows.length)}"><svg class="au-graph-lines" aria-hidden="true"><defs>${['true','false','unresolved'].map(value => `<marker id="au-process-arrow-${value}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path class="au-process-arrow" data-route="${value}" d="M1 1 L9 5 L1 9 Z" /></marker>`).join('')}</defs>${layout.edges.map(edge => `<path data-au-edge="${h(edge.edge_id)}" data-au-edge-source="${h(edge.source_node_id)}" data-au-edge-target="${h(edge.target_node_id)}" data-au-neighborhood="${neighborhood.has(edge.source_node_id) && neighborhood.has(edge.target_node_id)}" data-state="${h(edgeState(state,edge.edge_id))}" marker-end="url(#au-process-arrow-${edgeState(state,edge.edge_id) === 'true' ? 'true' : ['false','excluded'].includes(edgeState(state,edge.edge_id)) ? 'false' : 'unresolved'})" data-selected="${edge.source_node_id === selected || edge.target_node_id === selected}"><title>${h(edge.label || edge.relation || 'Process connection')} · ${h(options.stage ? routeLabel(edgeState(state,edge.edge_id)) : options.working ? `Provisional applicability: ${routeLabel(edgeState(state,edge.edge_id))}` : statusLabel(edgeState(state,edge.edge_id)))}</title></path>`).join('')}</svg>${layout.rows.map((row,rank) => `<div class="au-graph-rank" data-rank="${rank}" data-au-neighborhood="${row.some(node => neighborhood.has(node.node_id))}">${row.map(node => {
      const evaluated = evaluation.get(node.node_id) || {}, accepted = options.stage && options.working && options.working.graph.graph_sha256 === options.stage.state.graph?.graph_sha256 ? list(options.stage.state.evaluation?.nodes).find(row => row.node_id === node.node_id) : null, status = options.stage?.planned ? 'planned' : accepted?.execution_state === 'completed' ? 'completed' : options.working ? 'provisional' : evaluated.execution_state || evaluated.state || 'pending', inspection = options.working?.nodes.get(node.node_id) || options.working?.inspect;
      const parents = layout.parents.get(node.node_id).map(id => name(layout.byId.get(id)));
      const incoming = layout.edges.filter(edge => edge.target_node_id === node.node_id);
      const conditional = incoming.filter(edge => conditionLabel(state,edge.condition) || ['blocks','invalidates','supersedes'].includes(edge.relation));
      const labels = conditional.map(edge => `<span class="au-node-condition" data-au-edge-label="${h(edge.edge_id)}" data-state="${h(edgeState(state,edge.edge_id))}">${h(conditionLabel(state,edge.condition) || edge.label || words(edge.relation))}<span>${h(routeLabel(edgeState(state,edge.edge_id)))}</span></span>`).join('');
      const ownCondition = !conditional.length && !incoming.length && conditionLabel(state,node.condition);

      const visibleStatus = options.working ? evaluated.activation && (selected === node.node_id || evaluated.activation === 'false') ? `Applicability · ${routeLabel(evaluated.activation)}` : '' : ['false','excluded'].includes(evaluated.activation) && !conditional.length ? 'Does not apply' : selected === node.node_id && ['completed','complete','resolved','ready','blocked','running','working','queued','paused','failed','deferred'].includes(status) ? statusLabel(status) : '';
      const readiness = options.working && selected === node.node_id ? workingReadiness(evaluated,state.graph) : '';
      const nodeHTML = `<button type="button" class="au-node au-evidence-node" data-au-node="${h(node.node_id)}"${options.stage?.planned ? ' data-au-planned-node disabled' : ''}${inspection ? ` data-au-inspect="operation" data-au-record-id="${h(inspection.id)}" data-au-operation-id="${h(inspection.id)}" data-au-working-graph-sha="${h(options.working.graph.graph_sha256)}" data-au-working-scope="${h(options.working.inspect.id)}" data-au-working-evaluation-sha="${h(options.working.inspect.result.evaluation_sha256)}" data-au-operation-stage="${h(options.working.stage)}"` : ''} data-au-neighborhood="${neighborhood.has(node.node_id)}" data-status="${h(status)}" data-activation="${h(evaluated.activation || 'unresolved')}" aria-pressed="${selected === node.node_id}" aria-label="${h(name(node))}. ${h(options.stage ? options.stage.planned ? 'Planned step; source support is not yet assessed' : status === 'completed' ? 'Completed' : options.working ? 'Awaiting verification' : 'Awaiting source support' : options.working ? evaluated.activation ? `Provisional applicability: ${routeLabel(evaluated.activation)}${readiness ? `. ${readiness}` : ''}` : 'Provisional working step; not yet evaluated' : statusLabel(status))}${parents.length ? `. After ${h(parents.join(' + '))}` : ''}"><span class="au-node-index au-evidence-junction" data-au-junction="${h(node.node_id)}" aria-hidden="true">${status === 'completed' && (!options.working || accepted) ? '✓' : evaluated.activation === 'false' ? '−' : '·'}</span><span class="au-node-copy"><span class="au-node-relation"${neighborhood.has(node.node_id) ? '' : ' hidden'}>${neighborhood.has(node.node_id) ? node.node_id === selected ? 'This decision' : layout.parents.get(selected)?.includes(node.node_id) ? 'Before' : 'Then' : ''}</span>${options.stage ? '' : labels}${ownCondition && !options.stage ? `<span class="au-node-condition" data-au-node-condition="${h(node.node_id)}">${h(ownCondition)}<span>${h(routeLabel(evaluated.activation))}</span></span>` : ''}<strong class="au-node-title">${h(name(node))}</strong>${visibleStatus && !options.stage ? `<span class="au-node-state">${h(visibleStatus)}</span>` : ''}${readiness && !options.stage ? `<span class="au-node-state" data-au-working-readiness>${h(readiness)}</span>` : ''}</span></button>`;
      return options.stage ? `<div class="au-stage-step" data-au-stage-step="${h(node.node_id)}" data-au-stage-active="${selected === node.node_id}">${nodeHTML}${selected === node.node_id && options.stage.excerpt ? `<div class="au-forming-reading au-stage-source">${options.stage.excerpt}</div>` : ''}${stageNodeContents(node,options.stage.state,options.stage.trace,options.working,options.stage.map,options.stage.planned ? state.graph : null)}</div>` : nodeHTML;
    }).join('')}</div>`).join('')}</div></div>`;
  }

  function obligationMarkup(state, selected, suppliedRows, context = {}, forming = false) {
    const documents = new Map(list(state.evaluation?.documents).map(doc => [doc.document_type,doc]));
    const rows = suppliedRows || list(state.obligations).concat(list(state.evaluation?.documents).filter(doc => !list(state.obligations).some(item => item.document_type === doc.document_type)));
    if (!rows.length) return '<p class="au-empty">No document requirements have been recorded.</p>';
    return `<ul class="au-obligations">${rows.map(obligation => {
      const doc = documents.get(obligation.document_type) || {}, nodes = requiringNodeIds(obligation,doc);
      const requiring = nodes.find(id => list(state.graph?.nodes).some(node => node.node_id === id) && (!forming || requiringNodeReached(list(state.evaluation?.nodes).find(node => node.node_id === id),obligation,doc))), fact = list(obligation.required_fact_ids).find(id => list(state.facts).some(row => row.fact_id === id));
      const status = doc.route_state || obligation.status || 'pending', identity = requirementIdentity(obligation);
      const selection = requiring ? `data-au-select="${h(requiring)}" data-au-select-document="${h(obligation.document_type)}" data-au-select-obligation="${h(identity)}" data-au-select-fact="${h(fact || '')}"` : `data-au-inspect="requirement" data-au-record-id="${h(identity)}"`;
      const citations = list(obligation.required_fact_ids).flatMap(id => citationRows(list(state.facts).find(row => row.fact_id === id)));
      const reviewed = ['sufficient','insufficient'].includes(doc.review_state);
      const evidence = forming && reviewed ? citations.filter((citation,index) => citations.findIndex(row => row.artifact_id === citation.artifact_id) === index).map(citation => `<button type="button" class="au-link au-document-source" data-au-source="${h(citation.artifact_id)}" data-au-source-origin="requirement:${h(identity)}" data-au-citation="${h(JSON.stringify(citation))}">Source evidence · ${h(sourceLabel(state,citation.artifact_id))}</button>`).join('') : '';
      return `<li class="au-obligation" data-au-obligation="${h(identity)}" data-au-document="${h(obligation.document_type)}" data-status="${h(status)}"${context.obligation === identity ? ' data-selected="true"' : ''}><button type="button" class="au-document-open au-document-choice" ${selection}><strong>${h(name(obligation) || name(doc))}</strong>${!forming || ['needed_now','established','satisfied'].includes(status) ? `<span class="au-document-state au-document-route">${h(statusLabel(status))}</span>` : ''}${!forming || reviewed ? documentReviewMarkup(doc.review_state) : ''}${requiring ? `<span class="au-document-decision">${h(name(list(state.graph?.nodes).find(node => node.node_id === requiring)))}</span>` : ''}</button>${evidence}</li>`;
    }).join('')}</ul>`;
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
    return rows.map(({result:action,receipt,scope,instanceId},index) => `<article class="au-action" data-au-action-scope="${scope}"><div class="au-action-heading"><strong>${h(name(action))}</strong><span>${h(statusLabel(action.status))}</span></div><p class="au-meta">${scope === 'current' ? 'Recorded in this run' : scope === 'historical' ? 'Recorded in an earlier run' : 'Recorded action · run association not recorded'}</p><p>${h(action.summary || action.reason || '')}</p>${sourceButtons(state,action,`action:${instanceId || actionInstanceIdentity(action,receipt,index)}`)}${Object.keys(receipt).length ? `<details class="au-receipt" data-au-disclosure="action:${h(instanceId || actionInstanceIdentity(action,receipt,index))}"><summary>Action receipt</summary>${Number.isSafeInteger(receipt.parent_revision) ? `<p>Recorded after revision ${h(receipt.parent_revision)}.</p>` : ''}${receipt.operation ? `<p>${h(words(receipt.operation))}</p>` : ''}<pre class="au-record-body">${h(JSON.stringify(receipt,null,2))}</pre></details>` : ''}<details class="au-technical-record" data-au-disclosure="action-record:${h(instanceId || actionInstanceIdentity(action,receipt,index))}"><summary>Full public action record</summary><pre class="au-record-body">${h(JSON.stringify({result:action,receipt,scope},null,2))}</pre></details></article>`).join('') || '<p class="au-empty">No action result recorded for this step.</p>';
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
      return {...base,type:'reused',label:'Qualified knowledge reused',title:`${words(knowledge.knowledge_id)} · version ${knowledge.version}`,summary:knowledge.reason || words(typeof knowledge.applicability === 'string' ? knowledge.applicability : knowledge.applicability?.summary),knowledge,citations:[],record:knowledge,itemId:`${knowledge.knowledge_id}:${knowledge.version}:${knowledge.knowledge_sha256 || knowledge.definition_sha256}`};
    }
    if (event.kind !== 'knowledge.published' || !list(state.knowledge_published).some(item => same(item,knowledge))) return null;
    const status = knowledge.qualification?.status;
    if (status !== 'qualified' && status !== 'quarantined' || knowledge.source_claim_id && knowledge.source_claim_id !== state.claim_id) return null;
    if (status === 'qualified' && (!Number.isSafeInteger(knowledge.version) || knowledge.version < 1 || !isHash(knowledge.knowledge_sha256))) return null;
    const supporting = [...citationRows(knowledge),...citationRows(knowledge.candidate),...list(knowledge.source_evidence).flatMap(item => item.artifact_id && item.quote ? [item] : citationRows(item))];
    return {...base,type:status === 'qualified' ? 'qualified' : 'withheld',label:status === 'qualified' ? 'Knowledge qualified' : 'Knowledge candidate withheld',title:status === 'qualified' ? `${name(knowledge) || words(knowledge.knowledge_id)} · version ${knowledge.version}` : name(knowledge.candidate) || words(knowledge.knowledge_id),summary:knowledge.qualification?.reason || knowledge.qualification?.summary || knowledge.summary || knowledge.candidate?.summary || '',knowledge,citations:citations({citations:supporting}),record:knowledge,itemId:knowledge.knowledge_sha256 || knowledge.knowledge_id};
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
    return `<details class="au-step-route" data-au-disclosure="route:${h(selected)}"><summary>Branch and prerequisites <span>${edges.length} connections</span></summary>${expression ? `<p class="au-branch-condition">Recorded condition: ${condition(expression) || 'No condition detail recorded'}.</p>` : ''}${currentNode?.activation ? `<p>Recorded applicability: ${h(statusLabel(currentNode.activation))}.</p>` : ''}<ul class="au-step-relations">${edges.map(edge => {
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
    return `<article class="au-fact" data-au-fact="${h(fact.fact_id)}"><strong>${h(name(fact) || words(fact.flag))}</strong><span>${h(statusLabel(fact.verdict || fact.status))}</span>${fact.summary || fact.reason ? `<p>${h(fact.summary || fact.reason)}</p>` : ''}${sourceButtons(state,fact)}${['unresolved','unknown','insufficient'].includes(fact.verdict || fact.status) ? button('Add evidence','data-au-add-files') : ''}<details class="au-technical-record" data-au-disclosure="fact-record:${h(fact.fact_id)}"><summary>Full fact record</summary><pre class="au-record-body">${h(JSON.stringify(fact,null,2))}</pre></details></article>`;
  }
  function evidencePathMarkup(state, selected, projection = {}, context = {}, forming = false) {
    const r = evidenceRelationships(state,selected,context), {node,fact,document:requirement,evaluation} = r;
    if (!node) return forming ? `<div class="au-reading-column au-opening-content" data-au-evidence-path>${originalText(state) ? `<h2>Original message</h2><pre class="au-original-message">${h(originalText(state))}</pre>` : ''}${acquiredContentMarkup(state,projection) || sourceListMarkup(state,list(state.source_descriptors),'originals',projection)}</div>` : openingContentMarkup(state,projection);
    const citations = citationRows(fact), capability = projection.node_capabilities?.[selected];
    const sources = citations.map(citation => `<button type="button" class="au-source-link au-evidence-source" data-au-source-identity="${h(sourceObjectIdentity(state,citation.artifact_id))}" data-au-source="${h(citation.artifact_id)}" data-au-citation="${h(JSON.stringify(citation))}" data-au-source-origin="path:${h(selected)}:${h(fact.fact_id)}"><span class="au-evidence-source-label">${h(sourceLabel(state,citation.artifact_id))}<span aria-hidden="true">↗</span></span>${citation.quote ? `<q>${h(citation.quote)}</q>` : '<span>Open cited source</span>'}</button>`).join('');
    const route = requirement?.route_state || requirement?.status || 'pending', review = requirement?.review_state;
    const timing = {needed_later:'Required after a requiring step is reached.',needed_now:'Required now in the recorded process.',held_behind_question:'May be needed',held_not_reviewed:'The file is available; its evidence remains unestablished.',not_needed:'This document is not required on the recorded route.'}[route] || statusLabel(route);
    const blocked = list(evaluation.blocked_by || evaluation.unresolved_dependencies);
    const branches = list(state.graph?.edges).filter(edge => edge.source_node_id === selected || edge.target_node_id === selected);
    return `<div class="au-reading-column" data-au-evidence-path data-au-selected-step="${h(selected)}">${sources ? `<section class="au-reading-passages"><h3 class="au-reading-label">From the sources</h3>${sources}</section>` : !list(state.facts).some(item => citationRows(item).length) ? acquiredContentMarkup(state,projection) : ''}${fact ? `<section class="au-reading-fact" data-au-fact="${h(fact.fact_id)}"><h3 class="au-reading-label">What this shows</h3><p class="au-fact-summary">${h(state.graph?.family === 'incoming_packet' ? 'This supplied file has not been assessed.' : factCaseText(fact))}</p>${forming && state.graph?.family !== 'incoming_packet' ? `<p class="au-fact-state">${h(statusLabel(fact.verdict || fact.status))}</p>` : ''}${r.facts.length > 1 ? `<h3 class="au-reading-label">Other questions</h3><div class="au-reading-objects" aria-label="Other questions for this decision">${r.facts.filter(item => item.fact_id !== fact.fact_id).map(item => `<button type="button" class="au-link" data-au-fact-select="${h(item.fact_id)}" data-au-fact-state="${h(item.verdict || item.status || '')}">${h(statusLabel(item.verdict || item.status))}: ${h(name(item))}</button>`).join('')}</div>` : ''}</section>` : ''}${requirement && !forming ? `<section class="au-reading-requirement" data-au-document="${h(requirement.document_type)}" data-au-obligation="${h(requirementIdentity(requirement))}" data-route="${h(route)}"><h3 class="au-reading-label">Document for this decision</h3><h3>${h(name(requirement))}</h3><p class="au-document-route">${h(timing)}</p>${documentReviewMarkup(review)}${r.documents.length > 1 ? `<div class="au-reading-objects" aria-label="Documents for this decision">${r.documents.filter(item => requirementIdentity(item) !== requirementIdentity(requirement)).map(item => `<button type="button" class="au-link" data-au-document-select="${h(item.document_type)}" data-au-obligation-select="${h(requirementIdentity(item))}">${h(name(item))}</button>`).join('')}</div>` : ''}</section>` : ''}${!forming ? `<section class="au-reading-decision"><h3 class="au-reading-label">Decision</h3><p class="au-step-status">${h(statusLabel(evaluation.execution_state || evaluation.state))}</p>${blocked.length ? `<p>Requires ${blocked.map(id => `<button type="button" class="au-link" data-au-select="${h(id)}">${h(name(list(state.graph?.nodes).find(item => item.node_id === id)) || words(id))}</button>`).join(', ')}.</p>` : ''}</section>` : ''}${!forming && (list(state.knowledge_uses).length || node.authority) ? `<section class="au-reading-procedure"><h3 class="au-reading-label">Procedure</h3>${list(state.knowledge_uses).map(use => `<p data-au-knowledge-use="${h(use.knowledge_sha256 || use.knowledge_id || use.version_id)}">${h(procedureLabel(use))} · version ${h(use.version || use.version_id)} ${knowledgeLink(use)}</p>`).join('')}${node.authority?.title ? `<p>${h(procedureLabel({family:state.graph?.family,title:node.authority.title}))}</p>` : ''}</section>` : ''}${!forming && branches.length ? `<nav class="au-reading-relations" aria-label="Connected decisions">${branches.map(edge => { const other = edge.source_node_id === selected ? edge.target_node_id : edge.source_node_id; return `<button type="button" class="au-link" data-au-select="${h(other)}">${edge.target_node_id === selected ? 'Requires' : 'Leads to'} ${h(name(list(state.graph?.nodes).find(item => item.node_id === other)) || words(other))}<span class="au-meta">${h(statusLabel(edgeState(state,edge.edge_id)))}</span></button>`; }).join('')}</nav>` : ''}${!forming && capability?.authorized === false ? `<p class="au-reading-limit">${h(capability.reason || 'Execution is unavailable for this step.')}</p>` : ''}</div>`;
  }

  function inspectorMarkup(state, selected, projection = {}, events = [], context = {}) {
    return evidencePathMarkup(state,selected,projection,context);
  }

  function eventLabel(event) {
    if (event.kind === 'knowledge.published') return event.payload?.knowledge?.qualification?.status === 'qualified' ? 'Qualified knowledge version published' : 'Knowledge candidate withheld';
    if (event.kind?.startsWith('reconciliation.')) return ({'reconciliation.started':'Saved-result reconciliation started','reconciliation.completed':'Saved-result reconciliation completed','reconciliation.failed':'Saved-result reconciliation failed'})[event.kind] || words(event.kind);
    return event.payload?.summary || event.payload?.reason || ({'intake':'Incoming packet saved', 'intake.received':'Incoming packet saved', 'work.started':'Autonomous investigation started', 'sources.acquired':'Original sources acquired', 'interpretation.accepted':'Source-grounded process accepted', 'graph.advanced':'Process advanced', 'action.completed':'Action result saved', 'outcome.recorded':'Operational outcome saved', 'work.completed':'Operational outcome saved', 'work.deferred':'Work deferred', 'knowledge.published':'Qualified knowledge version published', 'knowledge.used':'Qualified knowledge reused', 'knowledge.reused':'Qualified knowledge reused'})[event.kind] || words(event.kind);
  }
  function outcomeMarkup(state, outcome) {
    if (!outcome) return '';
    const gaps = list(outcome.missing_evidence).length, limits = list(outcome.authority_limits).length;
    const held = state.deferral ? [] : list(state.evaluation?.documents).filter(doc => doc.route_state === 'held_behind_question');
    const heldNodes = [...new Set(held.flatMap(doc => list(doc.required_at_node_ids)))];
    const question = list(state.evaluation?.nodes).find(node => heldNodes.includes(node.node_id) && node.activation === 'unresolved')?.node_id || heldNodes[0];
    const heldMarkup = held.length ? `<p>${!gaps ? 'No active document gaps are listed in this outcome. ' : ''}Unresolved questions still hold ${held.length} document requirement${held.length === 1 ? '' : 's'}; their applicability must be resolved before they can enter the active request.</p><div class="au-related">${button('Inspect document requirements','data-au-detail="documents"')}${question ? button('Inspect questions and prerequisites',`data-au-select="${h(question)}"`) : ''}</div>` : '';
    const summary = [claimStatusLabel(state.status,state), gaps ? `${gaps} evidence gap${gaps === 1 ? '' : 's'}` : '', held.length ? `${held.length} requirement${held.length === 1 ? '' : 's'} held by questions` : '', limits ? `${limits} execution limit${limits === 1 ? '' : 's'}` : ''].filter(Boolean).join(' · ');
    const reason = outcome.reason || outcome.authority_limits?.[0] || outcome.summary || outcome.title;
    return `<details class="au-outcome" data-status="${h(state.status)}" data-au-disclosure="outcome"><summary><strong>${h(summary)}</strong><span>${h(reason)}</span></summary><div class="au-outcome-body"><p class="au-eyebrow">${state.status === 'deferred' ? 'Why work stopped' : 'Recorded outcome'}</p><h2>${h(outcome.title || words(outcome.status) || claimStatusLabel(state.status,state))}</h2><p>${h(outcome.summary || outcome.reason || '')}</p>${list(outcome.authority_limits).map(reason => `<p>${h(reason)}</p>`).join('')}${gaps ? `<p><strong>Evidence still needed:</strong> ${h(outcome.missing_evidence.map(item => item.label || words(item.document_type)).join('; '))}.</p>${button('Add supporting files','data-au-add-files')}` : ''}${heldMarkup}${list(outcome.unresolved_facts).length ? `<p><strong>Unresolved:</strong> ${h(outcome.unresolved_facts.map(item => item.summary || words(item.fact_id)).join('; '))}.</p>` : ''}${outcome.next_action ? `<p>${h(outcome.next_action)}</p>` : ''}${sourceButtons(state,outcome)}${outcome.request_draft ? `<details data-au-disclosure="request-draft"><summary>Evidence request · ${h(statusLabel(outcome.request_draft.status))}</summary><p class="au-meta">This saved request draft covers active document requirements only. Requirements held by unresolved questions are excluded.</p><p><strong>${h(outcome.request_draft.subject)}</strong></p><pre class="au-draft-body">${h(outcome.request_draft.body)}</pre></details>` : ''}<details class="au-technical-record" data-au-disclosure="outcome-record"><summary>Full public ${state.deferral ? 'deferral' : 'outcome'} record</summary><pre class="au-record-body">${h(JSON.stringify(state.deferral || state.outcome || outcome,null,2))}</pre></details>${state.deferral && state.outcome ? `<details class="au-technical-record" data-au-disclosure="retained-outcome-record"><summary>Retained outcome record</summary><pre class="au-record-body">${h(JSON.stringify(state.outcome,null,2))}</pre></details>` : ''}</div></details>`;
  }
  function sourceListMarkup(state, sources = list(state.source_descriptors), origin = 'originals', projection = {}) {
    if (origin !== 'history') { const visible = new Set(currentSourceSelection(state,projection).map(source => source.artifact_id)); sources = sources.filter(source => visible.has(source.artifact_id)); }
    return `<ul class="au-source-list">${sources.map(source => {
      const acquired = list(state.acquired_sources).find(row => row.artifact_id === source.artifact_id), unassessed = assessmentFreshness(state).sources.some(row => row.artifact_id === source.artifact_id);
      const capability = acquired?.extraction === 'unsupported_metadata' ? 'Interpretation unsupported' : acquired && !acquired.complete ? 'Only part of the source is readable' : '';
      const context = [sourceKind(state,source,projection) === 'Synthetic demonstration document' ? 'Synthetic demonstration document' : '',capability,unassessed ? 'Awaiting assessment' : ''].filter(Boolean).join(' · ');
      return `<li data-au-source-arrival="${h(source.artifact_id)}"${unassessed ? ' data-au-source-freshness="unassessed"' : ''}>${button(source.file_name || name(source) || 'Original source',`data-au-source="${h(source.artifact_id)}" data-au-source-origin="${h(origin)}:${h(source.artifact_id)}"`)}${context ? `<span>${h(context)}</span>` : ''}${acquired?.reason || acquired?.limitation ? `<p>${h(acquired.reason || acquired.limitation)}</p>` : ''}</li>`;
    }).join('') || '<li>No original source recorded.</li>'}</ul>`;
  }

  function unassignedSourcesMarkup(state) {
    const assigned = new Set(list(state.graph?.document_catalog).flatMap(doc => list(doc.held_files).map(file => file.artifact_id)));
    const sources = currentSourceSelection(state).filter(source => source.role === 'supporting_document' && !assigned.has(source.artifact_id));
    return sources.length ? `<section class="au-supporting"><h3>Files awaiting a document assignment</h3>${sourceListMarkup(state,sources,'documents')}</section>` : '';
  }

  function sourcesMarkup(state, readOnly = false, projection = {}) {
    return `<section class="au-supporting au-originals"><h2>Sources</h2><p class="au-original-title">${h(state.title || 'Untitled claim')}</p>${originalText(state) ? `<pre class="au-original-message">${h(originalText(state))}</pre>` : ''}${sourceListMarkup(state,list(state.source_descriptors),'originals',projection)}${state.revision > 0 && !readOnly ? '<form data-au-arrival class="au-arrival"><label for="auAdditionalFiles">Add supporting files</label><input id="auAdditionalFiles" name="files" type="file" multiple required><button class="au-secondary" type="submit">Add files</button><p class="au-form-status" role="status"></p></form>' : ''}</section>`;
  }

  function historyLabel(event) {
    const labels = {'intake':'Case received','intake.received':'Case received','sources.arrived':'Supporting files added','sources.acquired':'Original source read','process.prepared':'Investigation opened','work.started':'Investigation started','interpretation.accepted':'Evidence assessment saved','graph.advanced':'Document requirements updated','action.completed':'Action result saved','outcome.recorded':'Investigation result saved','work.completed':'Investigation result saved','work.deferred':'Investigation stopped','knowledge.used':'Procedure reused','reconciliation.started':'Saved result review started','reconciliation.completed':'Saved result review finished','reconciliation.failed':'Saved result review failed'};
    if (event.kind === 'knowledge.published') return event.payload?.knowledge?.qualification?.status === 'qualified' ? 'Procedure qualified for reuse' : 'Procedure withheld from reuse';
    if (event.kind === 'work.phase') return ({acquiring:'Read original files',interpreting:'Assess the original evidence',verifying:'Check source support',progressing:'Apply the process'})[event.payload?.phase] || 'Recorded work';
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
    return `<section class="au-activity"><h2>History</h2>${recordButton('Case details','claim')}${earlier.length ? `<section class="au-history-record"><h3>Earlier documents</h3>${sourceListMarkup(state,earlier,'history',projection)}</section>` : ''}${state.outcome || state.deferral ? `<section class="au-history-outcome"><h3>${h(claimStatusLabel(state.status,state))}</h3><p>${h(state.deferral?.reason || state.outcome?.summary || state.outcome?.reason || '')}</p>${recordButton('Details','outcome')}</section>` : ''}${list(state.reconciliations).map(row => `<article class="au-history-record"><h3>${h(({started:'Saved result review started',completed:'Saved result review finished',failed:'Saved result review failed'})[row.status] || 'Saved result review')}</h3>${row.original_deferral?.reason ? `<p>Original execution failure: ${h(row.original_deferral.reason)}</p>` : ''}${row.failure_reason ? `<p>${h(row.failure_reason)}</p>` : ''}${recordButton('Details','reconciliation',row.reconciliation_id)}</article>`).join('')}<ol class="au-event-list">${events.slice().reverse().map(event => `<li><div><strong>${h(historyLabel(event))}</strong><time datetime="${h(event.timestamp || '')}">${h(dateLabel(event.timestamp))}</time>${recordButton('Details','event',event.seq)}</div></li>`).join('') || '<li>No accepted work recorded.</li>'}</ol>${actionRows(state,events).length ? `<section><h3>Recorded actions</h3>${actionRows(state,events).map((row,index) => `<article class="au-history-record" data-au-action-scope="${h(row.scope)}" data-au-action-instance="${h(row.instanceId)}"><strong>${h(actionLabel(state,row.result))}</strong><p class="au-meta">${row.scope === 'historical' ? 'Recorded in an earlier run' : row.scope === 'current' ? 'Recorded in this run' : 'Run association is not recorded'}</p>${row.result.reason ? `<p>${h(row.result.reason)}</p>` : ''}${sourceButtons(state,row.result,`action:${row.instanceId}`)}${recordButton('Details','action',row.instanceId)}</article>`).join('')}</section>` : ''}</section>`;
  }

  function eventCueMarkup(state, events) {
    const event = events.at(-1);
    if (!event) return '';
    const semantic = semanticEventRecord(state,event), identity = semantic?.id;
    const label = semantic ? `${semantic.label} · ${semantic.title}` : eventLabel(event);
    return `<button type="button" class="au-event-cue" data-au-detail="activity" data-au-event-seq="${h(event.seq)}"${identity ? ` data-au-semantic-event="${h(identity)}" data-au-semantic-kind="${h(event.kind)}"` : ''} title="${h(label)} · accepted revision ${h(event.seq)}"><span class="au-event-marker" aria-hidden="true">${semantic?.type === 'reused' ? '↺' : '·'}</span><span>${h(label.length > 180 ? label.slice(0,177) + '…' : label)}</span><span class="au-event-revision">↗</span></button>`;
  }
  function claimHeadingMarkup(state, extraClass = '') {
    const featured = featuredCase(state.claim_id);
    return `<h1 class="au-page-heading ${extraClass}" id="auClaimTitle" data-au-claim-title tabindex="-1">${h(featured?.label || state.title || 'Untitled claim')}</h1>`;
  }

  function readSkeletonMarkup(kind, title = '', claimId = '') {
    const featured = kind === 'claim' && featuredCase(claimId);
    return `<section class="au-read-skeleton" data-au-skeleton="${h(kind)}" aria-busy="true"><header class="au-work-head"><div><h1 class="au-page-heading" tabindex="-1">${h(featured?.label || title || (kind === 'knowledge' ? 'Knowledge' : 'Opening case'))}</h1></div></header></section>`;
  }

  function workMarkup(state, projection, selected, events, detail = 'step', context = {}, presentation = {}) {
    if (!presentation.operations && presentation.operationOpening) presentation = {...presentation,operations:{opening:true,rows:[],sources:new Map()}};
    const reference = referenceExecution(state), availability = claimAvailability(presentation.status || null,state,projection);
    const canWrite = !presentation.readOnly && presentation.writable !== false && writable(presentation.status) && presentation.mode !== 'replay';
    presentation = {...presentation,availability:{...presentation.availability,...(!intakeEligible(projection) || REFERENCE_DEMO_CASES.some(row => row.claim_id === state.claim_id) || !canWrite ? {ready:false,reason:availability.reason} : {})}};
    const fact = evidenceRelationships(state,selected,context).fact;
    const freshness = assessmentFreshness(state);
    const failure = state.deferral?.reason;
    const constraint = freshness.status === 'prior' ? 'Earlier findings · new sources await review.' : failure && failure !== factCaseText(fact) ? failure : '';
    const stageView = (Boolean(presentation.operations) || referenceAssessmentComplete(state)) && detail === 'step';
    const trace = presentation.operations, transportTrace = presentation.transportOperations || trace, resultAvailable = transportTrace?.buffer?.result?.exact_output_verified === true && transportTrace.buffer.result.state_sha256 === transportTrace.binding?.current_state_sha256 && transportTrace.buffer.result.current_event_sha256 === transportTrace.binding?.current_event_sha256;
    const receivedCount = list(transportTrace?.rows).length, totalCount = bufferedOperationCount(transportTrace), operationCount = totalCount || receivedCount, operationIndex = trace?.inspection ? presentation.inspectionIndex : trace?.finished ? Math.max(0,operationCount-1) : Math.max(0,list(transportTrace?.rows).findIndex(row => row.id === trace?.current?.id));
    const transport = trace ? `<div class="au-stage-transport" aria-label="Assessment playback">${presentation.playing ? button('Pause','data-au-demo-stop') : presentation.paused ? button('Play','data-au-demo-resume') : trace.inspection ? button('Result','data-au-inspection-clear') : ''}<label class="au-stage-scrubber" style="--au-operation-ticks:${Math.max(1,operationCount)}"><span class="au-visually-hidden">Inspect this step</span><input type="range" data-au-operation-scrub min="0" max="${Math.max(0,operationCount-1)}" step="1" value="${operationIndex}" aria-valuetext="Operation ${operationIndex+1} of ${operationCount}" aria-label="Inspect this step"${operationCount ? '' : ' disabled'}><span class="au-visually-hidden" data-au-scrub-position>${totalCount || transportTrace?.finished ? `${operationCount ? operationIndex+1 : 0} / ${operationCount}` : `${receivedCount} received`}</span></label>${resultAvailable && !transportTrace.finished ? button('Skip to result','data-au-operation-skip') : ''}</div>` : '';
    const playControls = stageView ? '' : (presentation.operations && !presentation.operations.finished ? button('Skip to result','data-au-operation-skip') : '') + (presentation.playing ? button('Pause','data-au-demo-stop') : presentation.paused ? button('Resume','data-au-demo-resume') : presentation.mode === 'replay' ? button(presentation.operations?.finished ? 'Play saved history' : 'Play','data-au-demo-play') : '');
    const panels = [['step','Process'],['documents','Documents'],['knowledge','Knowledge'],['sources','Sources'],['activity','History']];
    const chosen = panels.some(([id]) => id === detail) ? detail : 'step', publicationFocus = presentation.attention && (!presentation.inspectionHold || presentation.attention.retained) && formingPublication(state,events,presentation.attention), forming = chosen === 'step' && (formingWork(state,presentation) || Boolean(publicationFocus) || Boolean(presentation.operations));
    const body = chosen === 'step' ? forming ? formingMarkup(state,projection,selected,events,context,presentation.knowledge,presentation.attention,false,presentation.operations) + (!state.graph && !presentation.operations ? intakeMarkup(state,projection) : '') : !state.graph ? openingContentMarkup(state,projection) + intakeMarkup(state,projection) : referenceAssessmentComplete(state) ? formingMarkup(state,projection,selected,events,context,presentation.knowledge,undefined,true) : formingKnowledgeMarkup(state,presentation.knowledge,true) + inspectorMarkup(state,selected,projection,events,context) : chosen === 'documents' ? `<section class="au-documents"><h2>Document checklist</h2>${state.graph ? obligationMarkup(state,selected,undefined,context) + unassignedSourcesMarkup(state) : intakeMarkup(state,projection)}${canWrite && state.revision > 0 ? button('Add supporting files','data-au-add-files') : ''}</section>` : chosen === 'knowledge' ? claimKnowledgeMarkup(state,events) : chosen === 'sources' ? sourcesMarkup(state,!canWrite,projection) : `${operationHistoryMarkup(presentation.operations)}${activityMarkup(state,events,projection)}${presentation.replay ? recordButton('Playback details','replay') : ''}`;
    return `<section class="au-quiet-claim" data-au-revision="${h(state.revision)}" data-au-state-sha="${h(state.state_sha256)}"${stageView ? ' data-au-stage-view="true"' : ''}><header class="au-work-head au-focused-claim-head"><div><p class="au-eyebrow"><button type="button" class="au-back-work" data-au-nav="work">Cases</button>${!stageView && (featuredCase(state.claim_id) || state.origin === 'canonical_original') ? ' / Synthetic claim' : ''}${presentation.mode === 'replay' && !presentation.operations ? ' / Recorded investigation' : ''}</p>${claimHeadingMarkup(state)}${presentation.operations ? `<p class="au-reference-mode" data-au-operation-mode>${trace?.inspection ? `History · operation ${operationIndex+1} · accepted revision ${state.revision}` : presentation.operations.savedFallback ? 'Saved result' : presentation.operations.recorded || presentation.operations.binding?.mode === 'recorded_operations' ? 'Recorded replay' : 'Live rules-based check'} · Synthetic sources · No external action${presentation.operations.asOf || reference?.as_of ? ` · as of ${h(presentation.operations.asOf || reference?.as_of)}` : ''}</p>` : reference ? `<p class="au-reference-mode" data-au-reference-mode>Historical synthetic recording${reference.as_of ? ` · as of ${h(reference.as_of)}` : ''} · rules-based${stageView ? ' · No external action' : ''}</p>` : ''}<p class="au-claim-constraint"><span data-au-claim-status>${h(claimStatusLabel(state.status,state))}.</span>${constraint ? ` ${h(constraint)}` : ''}${state.outcome?.assessment_status === 'complete' && reference && state.outcome.status === 'deferred' ? ' Assessment only; no external action taken.' : ''} <span class="au-read-state" data-au-read-state-label></span></p></div><div class="au-work-controls">${canWrite ? state.revision === 0 || presentation.pendingStart ? `<button type="button" class="au-primary" data-au-start${presentation.availability?.ready ? '' : ' disabled'}>${presentation.pendingStart ? 'Retry start' : 'Start investigation'}</button>` : state.status === 'running' ? button('Pause work','data-au-pause') : state.deferral?.code === 'paused' ? button('Resume work','data-au-resume') : '' : ''}${playControls}${presentation.mode === 'replay' || stageView ? recordButton('Choose case','demo') : ''}<button type="button" class="au-link" data-au-detail="activity" aria-pressed="${chosen === 'activity'}" aria-controls="auPanel-activity">History</button></div></header>${state.revision === 0 && canWrite ? `<p class="au-meta" data-au-start-availability>${h(presentation.availability?.reason || 'Checking live execution availability…')}</p>` : ''}<section class="au-evidence-canvas" data-au-canvas><nav class="au-context-nav" aria-label="Case views">${panels.filter(([id]) => id !== 'activity').map(([id,label],index) => `<button type="button"${index > 2 ? ' class="au-context-utility"' : ''} data-au-detail="${id}" aria-pressed="${chosen === id}" aria-controls="auPanel-${id}">${label}</button>`).join('')}</nav><div class="au-evidence-stage" data-au-evidence-stage>${!stageView && chosen === 'step' && !active(state.status) && state.outcome?.summary ? `<div class="au-assessment-conclusion"><p>${h(state.outcome.summary)}</p>${legalBasisMarkup(state)}</div>` : !stageView && chosen === 'step' && !state.outcome ? legalBasisMarkup(state) : ''}${chosen === 'step' && !forming && !referenceAssessmentComplete(state) && list(state.graph?.nodes).some(node => node.node_id === selected) ? `<h2 class="au-process-question au-reading-question" tabindex="-1" data-au-inspector-heading="${h(selected)}">${h(name(list(state.graph.nodes).find(node => node.node_id === selected)))}</h2>` : ''}${chosen === 'step' && !forming && !referenceAssessmentComplete(state) && state.graph ? `<section class="au-process-hero au-evidence-process" aria-label="Decision neighborhood">${graphMarkup(state,selected,projection)}</section>` : ''}<div class="au-context-body" data-au-context="${h(chosen)}"><section class="au-context-view" id="auPanel-${chosen}" data-au-panel="${chosen}">${body}</section></div>${stageView ? transport : ''}</div></section></section>`;
  }

  function replayIdentityMarkup(record) {
    return `<details class="au-technical-record au-replay-identity"><summary>Verified replay · revision ${h(record.through_seq)} of ${h(record.current_revision)}</summary><dl class="au-chain"><div><dt>Recorded prefix · state</dt><dd class="au-hash">${h(record.state?.state_sha256)}</dd></div><div><dt>Current saved head</dt><dd class="au-hash">${h(record.current_state_sha256)}</dd></div></dl><pre class="au-record-body">${h(JSON.stringify(record.provenance,null,2))}</pre></details>`;
  }
  function knowledgeLink(use, label = 'Open procedure') {
    const id = use.knowledge_id || use.version_id, version = use.version || use.version_id;
    return id && version ? button(label,`data-au-knowledge="${h(id)}" data-au-version="${h(version)}" data-au-knowledge-sha="${h(use.knowledge_sha256 || '')}" data-au-definition-sha="${h(use.definition_sha256 || use.qualification?.definition_sha256 || '')}"`) : '';
  }
  function reuseDetails(use) {
    const applicability = typeof use.applicability === 'string' ? words(use.applicability) : use.applicability?.summary;
    const observed = [];
    if (Number.isSafeInteger(use.avoided_rule_compilations) && use.avoided_rule_compilations >= 0) observed.push(`${use.avoided_rule_compilations} rule compilation${use.avoided_rule_compilations === 1 ? '' : 's'} avoided`);
    if (Number.isSafeInteger(use.avoided_qualification_cases) && use.avoided_qualification_cases >= 0) observed.push(`${use.avoided_qualification_cases} qualification cases reused`);
    return `${use.reason || applicability ? `<p>${h(use.reason || applicability)}</p>` : ''}${observed.length ? `<p class="au-meta">${h(observed.join(' · '))}</p>` : ''}<details class="au-technical-record au-reuse-record" data-au-disclosure="reuse:${h(use.knowledge_id || use.version_id || '')}:${h(use.version || use.version_id || '')}:${h(use.workflow_id || use.claim_id || '')}"><summary>Public reuse record</summary><pre class="au-record-body">${h(JSON.stringify(use,null,2))}</pre></details>`;
  }
  function definitionMarkup(version) {
    const graph = version.graph || {nodes:[],edges:[]}, layout = layoutGraph(graph), facts = new Map(list(version.facts).map(fact => [fact.fact_id,fact]));
    const conditions = Object.entries(graph.conditions || {}), conditionalDocuments = list(graph.document_catalog).filter(item => item.condition || item.condition_flag);
    const applicability = conditions.length || conditionalDocuments.length ? `<section><h3>Applicability</h3><ul class="au-definition-list">${conditions.map(([flag]) => `<li>${h(name(facts.get(`condition:${flag}`)) || words(flag))}</li>`).join('')}${conditionalDocuments.map(item => `<li>${h(name(item))}${item.condition_flag ? ` · ${h(name(facts.get(`condition:${item.condition_flag}`)) || words(item.condition_flag))}` : ''}</li>`).join('')}</ul></section>` : '';
    const requiredFacts = `<section><h3>Facts to establish</h3><ul class="au-definition-list">${[...facts.values()].map(fact => `<li>${h(name(fact))}</li>`).join('') || '<li>No fact definition recorded.</li>'}</ul></section>`;
    const requirements = `<section><h3>Document requirements</h3><ul class="au-definition-list">${list(version.obligations).map(item => `<li><strong>${h(name(item))}</strong><p class="au-meta">${h(list(item.required_fact_ids).map(id => name(facts.get(id)) || words(id)).join('; '))}</p></li>`).join('') || '<li>No document requirements recorded.</li>'}</ul></section>`;
    const evidence = list(version.evidence_recipes).length ? `<section><h3>Evidence to look for</h3><ul class="au-definition-list">${version.evidence_recipes.map(recipe => `<li><strong>${h(words(recipe.document_type))}</strong><p>${h(recipe.summary)}</p><ul>${list(recipe.required_fields).map(field => `<li>${h(field)}</li>`).join('')}</ul></li>`).join('')}</ul></section>` : '';
    const process = `<section><h3>Process</h3><ol class="au-definition-steps">${layout.nodes.map(node => `<li><strong>${h(name(node))}</strong>${layout.parents.get(node.node_id).length ? `<p class="au-meta">Requires ${h(layout.parents.get(node.node_id).map(id => name(layout.byId.get(id))).join(' and '))}</p>` : ''}</li>`).join('') || '<li>No process definition recorded.</li>'}</ol></section>`;
    return `<div class="au-procedure-definition">${applicability}${requiredFacts}${requirements}${evidence}${process}</div>`;
  }
  function lineageMarkup(version, versions = []) {
    const parent = versions.find(item => item.knowledge_sha256 && item.knowledge_sha256 === version.parent_knowledge_sha256);
    return `<div class="au-lineage-summary">${version.change_reason ? `<p>${h(version.change_reason)}</p>` : ''}${version.parent_knowledge_sha256 ? `<p class="au-meta">${parent ? `Derived from version ${h(parent.version || parent.version_id)}` : 'Parent version is not in this record'}${parent?.source_claim_id ? ` · ${button('Open parent source claim',`data-au-claim="${h(parent.source_claim_id)}"`)}` : ''}</p>` : '<p class="au-meta">First recorded version</p>'}</div>`;
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
    if (facet === 'facts') return `<div class="au-procedure-facts"><h3>Facts to establish in each case</h3>${[...facts.values()].map(fact => `<p>${h(name(fact))}</p>`).join('') || '<p>No required facts are recorded.</p>'}</div>`;
    if (facet === 'documents') return `<div class="au-procedure-documents"><h3>Document requirements</h3>${list(version.obligations).map(item => `<article><h4>${h(name(item))}</h4>${list(item.required_fact_ids).length ? `<p>${h(item.required_fact_ids.map(id => name(facts.get(id)) || words(id)).join('; '))}</p>` : ''}</article>`).join('') || '<p>No document requirements are recorded.</p>'}</div>`;
    if (facet === 'exceptions') {
      const conditional = list(graph.document_catalog).filter(item => item.condition || item.condition_flag), conditions = Object.keys(graph.conditions || {});
      const conditionalEdges = list(graph.edges).filter(edge => edge.condition && conditionFlags(edge.condition).length);
      return `<div class="au-procedure-exceptions"><h3>Conditions and exceptions</h3>${conditions.map(flag => `<p>${h(name(facts.get(`condition:${flag}`)) || words(flag))}</p>`).join('')}${conditional.map(item => `<article><h4>${h(name(item))}</h4>${item.condition_flag ? `<p>${h(name(facts.get(`condition:${item.condition_flag}`)) || words(item.condition_flag))}</p>` : ''}</article>`).join('')}${conditionalEdges.map(edge => `<p>${h(name(layout.byId.get(edge.source_node_id)))} → ${h(name(layout.byId.get(edge.target_node_id)))} · ${h(conditionFlags(edge.condition).map(flag => name(facts.get(`condition:${flag}`)) || words(flag)).join('; '))}</p>`).join('')}${!conditions.length && !conditional.length && !conditionalEdges.length ? '<p>No conditional exception is recorded in this version.</p>' : ''}</div>`;
    }
    if (facet === 'changes') {
      const added = list(version.added_document_types), parent = list(versions).find(item => item.knowledge_sha256 === version.parent_knowledge_sha256);
      return `<div class="au-procedure-changes"><h3>What changed</h3>${parent ? `<p>From version ${h(parent.version || parent.version_id)} to version ${h(version.version || version.version_id)}.</p>` : '<p>First recorded version.</p>'}${added.map(type => { const recipe = list(version.evidence_recipes).find(item => item.document_type === type), requirement = list(version.obligations).find(item => item.document_type === type); return `<article><h4>${h(name(requirement) || words(type))}</h4>${recipe?.summary ? `<p>${h(recipe.summary)}</p>` : ''}${list(recipe?.required_fields).length ? `<p>${h(recipe.required_fields.map(field => words(field)).join('; '))}</p>` : ''}</article>`; }).join('')}${!added.length && parent ? '<p>No added document requirement is recorded for this version.</p>' : ''}</div>`;
    }
    return `<div class="au-procedure-process" aria-label="Reusable process">${layout.rows.map((row,rank) => `<div class="au-procedure-rank" data-au-procedure-rank="${rank}">${row.map(node => `<article class="au-procedure-stage" data-au-procedure-node="${h(node.node_id)}"><h3>${h(name(node))}</h3>${layout.parents.get(node.node_id).length ? `<p>${h(layout.parents.get(node.node_id).map(id => name(layout.byId.get(id))).join(' + '))}</p>` : ''}</article>`).join('')}</div>`).join('') || '<p>No process definition is recorded.</p>'}</div>`;
  }
  function readKnowledge(data) {
    if (!data || !Array.isArray(data.versions) || data.uses !== undefined && !Array.isArray(data.uses) || data.quarantined !== undefined && !Array.isArray(data.quarantined)) throw new Error('The recorded knowledge response is incomplete.');
    return data;
  }
  function knowledgeMarkup(data, claims = [], pin = null, facet = 'process') {
    const versions = [...list(data?.versions)].sort((a,b) => String(name(a)).localeCompare(String(name(b))) || Number(b.version) - Number(a.version)), groups = new Map();
    for (const version of versions) { const category = procedureScope(version); if (!groups.has(category)) groups.set(category,[]); groups.get(category).push(version); }
    const selected = pin ? versions.find(item => String(item.knowledge_id || item.version_id) === String(pin.knowledge_id) && String(item.version || item.version_id) === String(pin.version) && (!pin.knowledge_sha256 || item.knowledge_sha256 === pin.knowledge_sha256) && (!pin.definition_sha256 || (item.qualification?.definition_sha256 || item.definition_sha256) === pin.definition_sha256)) : versions[0];
    const claimLink = (id,label) => button(featuredCase(id)?.label || claims.find(row => row.claim_id === id)?.title || label,`data-au-claim="${h(id)}"`);
    const procedureLink = (version,label) => `<button type="button" class="au-procedure-open" data-au-knowledge="${h(version.knowledge_id || version.version_id)}" data-au-version="${h(version.version || version.version_id)}" data-au-knowledge-sha="${h(version.knowledge_sha256 || '')}" data-au-definition-sha="${h(version.qualification?.definition_sha256 || version.definition_sha256 || '')}" aria-pressed="${selected === version}">${h(label || procedureLabel(version))}</button>`;
    const receiving = selected ? knowledgeUses(selected,list(data?.uses)) : [], identity = selected ? `${selected.knowledge_id || selected.version_id}:${selected.version || selected.version_id}` : '';
    const facets = [['process','Process'],['facts','Facts'],['documents','Documents'],['exceptions','Exceptions'],['changes','Changes']];
    const chosen = facets.some(([id]) => id === facet) ? facet : 'process';
    const siblings = selected ? versions.filter(version => (version.knowledge_id || version.version_id) === (selected.knowledge_id || selected.version_id)) : [];
    return `<section class="au-quiet-knowledge"><header class="au-work-head"><h1 class="au-page-heading" tabindex="-1">Knowledge</h1><div><span class="au-read-state" data-au-knowledge-read-label></span>${recordButton('History','knowledge-index')}</div></header><div class="au-knowledge-layout"><nav class="au-procedure-list" aria-label="Reusable procedures">${[...groups].map(([category,rows]) => `<section>${new Set(rows.map(version => version.knowledge_id || version.version_id)).size > 1 ? `<h2>${h(category)}</h2>` : ''}${rows.filter((version,index) => rows.findIndex(item => (item.knowledge_id || item.version_id) === (version.knowledge_id || version.version_id)) === index).map(version => procedureLink(version,procedureLabel(version))).join('')}</section>`).join('') || '<p>No reusable procedure is recorded.</p>'}</nav>${selected ? `<article class="au-procedure-reading au-knowledge-version" data-au-version="${h(selected.version || selected.version_id)}" data-au-knowledge-identity="${h(identity)}"><h2>${h(procedureLabel(selected))}</h2>${selected.summary || selected.description ? `<p>${h(selected.summary || selected.description)}</p>` : ''}<nav class="au-procedure-versions" aria-label="Recorded versions">${siblings.map(version => procedureLink(version,`Version ${version.version || version.version_id}`)).join('')}</nav><nav class="au-procedure-facets" aria-label="Procedure details">${facets.map(([id,label]) => `<button type="button" data-au-knowledge-facet="${id}" aria-pressed="${chosen === id}">${label}</button>`).join('')}</nav><section class="au-procedure-facet" data-au-knowledge-facet-panel="${chosen}">${knowledgeFacetMarkup(selected,chosen,versions)}</section><section class="au-procedure-provenance"><h3>Source and receiving cases</h3>${selected.source_claim_id ? claimLink(selected.source_claim_id,'Open source case') : ''}${receiving.map(use => `<article>${use.claim_id ? claimLink(use.claim_id,'Open receiving case') : ''}</article>`).join('')}${!receiving.length ? '<p class="au-meta">No receiving case is recorded for this version.</p>' : ''}</section></article>` : ''}</div></section>`;
  }
  function collectionRows(claims, scope = 'all') {
    return list(claims).filter(claim => scope === 'all' || (scope === 'originals' ? claim.origin === 'canonical_original' : claim.origin !== 'canonical_original'));
  }
  function collectionFilters(rows) {
    return [...new Set(['all','not_started','working','deferred','investigation_complete',...rows.map(claim => statusFilter(claim.status,claim)).filter(status => status && !active(status))])];
  }
  function collectionCounts(rows, scope) {
    return [['In progress',rows.filter(claim => active(claim.status)).length],['Deferred',rows.filter(claim => statusFilter(claim.status,claim) === 'deferred').length],['Assessment complete',rows.filter(claim => statusFilter(claim.status,claim) === 'investigation_complete').length]];
  }
  function matchingClaims(claims, {search = '', filter = 'all', domain = 'all', scope = 'all'} = {}) {
    const terms = search.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    return collectionRows(claims,scope).filter(claim => (domain === 'all' || domainOf(claim) === domain) && (filter === 'all' || filter === 'working' && active(claim.status) || statusFilter(claim.status,claim) === statusFilter(filter)) && terms.every(term => [claim.claim_id,claim.title,originalText(claim),claim.language,claim.channel,claimStatusLabel(claim.status,claim),claim.phase,claim.phase_summary,claim.outcome?.summary,claim.outcome?.reason,claimConstraint(claim),claim.browse_metadata?.family_id].filter(Boolean).join(' ').toLocaleLowerCase().includes(term)));
  }
  function claimConstraint(claim) {
    const outcome = claim.outcome;
    const missing = list(outcome?.missing_evidence).map(item => item.label || words(item.document_type)).filter(Boolean);
    return outcome?.reason || (missing.length ? `Evidence needed: ${missing.join('; ')}` : '') || list(outcome?.authority_limits)[0] || outcome?.next_action || '';
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
    const excerpt = messagePreview(originalText(row)), featured = featuredCase(claimId);
    return `<section class="au-catalog-preview" data-au-preview="catalog" data-au-preview-claim="${h(row.claim_id)}" aria-busy="true"><header class="au-work-head"><div><p class="au-eyebrow"><button type="button" class="au-back-work" data-au-nav="work">Cases</button>${row.origin === 'canonical_original' ? ' / Synthetic claim' : ''}</p><h1 class="au-page-heading" data-au-catalog-title tabindex="-1">${h(featured?.label || row.title)}</h1>${featured ? `<p class="au-catalog-subject">${h(row.title)}</p>` : ''}</div></header>${excerpt ? `<section class="au-catalog-original"><h2>Original message excerpt</h2><pre class="au-original-message">${h(excerpt)}</pre></section>` : ''}</section>`;
  }
  function unknownClaimMarkup(claimId) {
    const featured = featuredCase(claimId);
    return `<section class="au-catalog-preview" data-au-preview="unknown" aria-busy="true">${featured ? `<h1 class="au-page-heading" tabindex="-1">${h(featured.label)}</h1>` : ''}${button('Choose a case','data-au-nav="work"')}</section>`;
  }
  function claimsMarkup(claims, options = {}) {
    const visible = options.page === undefined ? matchingClaims(claims,options) : collectionPage(claims,options).rows;
    return visible.map(claim => {
      const constraint = messagePreview(originalText(claim)) || list(claim.outcome?.unresolved_facts).find(fact => fact.summary)?.summary || claimConstraint(claim) || claim.deferral?.reason || claim.outcome?.summary;
      return `<article class="au-claim-row au-identity-claim-row" data-au-claim-row="${h(claim.claim_id)}"><button type="button" class="au-claim-open" data-au-claim="${h(claim.claim_id)}" title="${h(claim.title || 'Untitled claim')}"><strong>${h(featuredCase(claim.claim_id)?.label || claim.title || 'Untitled claim')}</strong>${constraint ? `<span class="au-claim-constraint">${h(constraint)}</span>` : ''}</button>${claim.status && !['not_started','not_run'].includes(claim.status) ? `<span class="au-claim-state">${h(claimStatusLabel(claim.status,claim))}</span>` : ''}</article>`;
    }).join('') || '<p class="au-empty">No cases match this search.</p>';
  }

  function domainMarkup(claims, domain = 'all') {
    return `<nav class="au-domain-browse" aria-label="Case domains"><button type="button" data-au-domain="all" aria-pressed="${domain === 'all'}">All cases</button>${DOMAINS.map(item => `<button type="button" data-au-domain="${item.id}" aria-pressed="${domain === item.id}">${h(item.label)}</button>`).join('')}</nav>`;
  }

  function collectionMarkup(claims, options = {}) {
    const {search = '',domain = 'all',scope = 'originals'} = options, filter = statusFilter(options.filter || 'all'), rows = collectionRows(claims,scope), page = collectionPage(rows,{...options,scope,filter});
    return `<section class="au-collection au-identity-collection"><header class="au-collection-head"><div><h1 class="au-page-heading" tabindex="-1">Cases</h1><p class="au-lead">${scope === 'added' ? 'Added cases' : '150 synthetic claims'}</p></div></header><nav class="au-collection-scope" aria-label="Case collection"><button type="button" data-au-collection-scope="originals" aria-pressed="${scope === 'originals'}">Original cases</button><button type="button" data-au-collection-scope="added" aria-pressed="${scope === 'added'}">Added cases</button></nav>${scope === 'originals' ? domainMarkup(rows,domain) : ''}<div class="au-collection-tools"><label for="auClaimSearch">Search cases<input id="auClaimSearch" type="search" data-au-claim-search value="${h(search)}" placeholder="Message, title or case ID" autocomplete="off"></label></div><nav class="au-case-filter" aria-label="Case status">${['all','not_started','working','deferred','investigation_complete'].map(value => `<button type="button" data-au-filter="${value}" aria-pressed="${filter === value}">${h(value === 'all' ? 'All statuses' : value === 'working' ? 'In progress' : value === 'investigation_complete' ? 'Assessment complete' : statusLabel(value))}</button>`).join('')}</nav><div class="au-claim-list" data-au-claims>${claimsMarkup(rows,{...options,scope,filter,page:page.page})}</div>${paginationMarkup(page)}</section>`;
  }

  function liveAvailability(status) {
    if (!writable(status)) return {ready:false,reason:'This workspace is read-only.'};
    if (!status) return {ready:false,reason:'Checking live execution availability…'};
    if (!status.enabled) return {ready:false,reason:'Live execution is disabled.'};
    if (!status.provider_ready) return {ready:false,reason:'Live inference is unavailable.'};
    if (status.limits?.autonomous_can_start === false) return {ready:false,reason:status.limits.autonomous_reason === 'call_limit_reached' ? 'The recorded call allowance is exhausted.' : status.limits.autonomous_reason === 'cost_limit_reached' ? 'The recorded cost allowance is exhausted.' : 'The recorded allowance does not permit new work.'};
    return {ready:true,reason:'One worker handles the live queue in sequence.'};
  }
  function demoItineraryMarkup(claims, position = null, current = null, roster = REFERENCE_DEMO_CASES) {
    return `<div class="au-demo-selection" aria-label="Presentation order of independent cases">${DOMAINS.map(domain => `<section data-au-demo-domain="${domain.id}"><div class="au-section-heading"><h2>${h(domain.label)}</h2><span>3 original cases</span></div><ol start="${roster.findIndex(row => row.domain === domain.id)+1}">${roster.filter(row => row.domain === domain.id).map(row => {
      const index = roster.indexOf(row), claim = current?.claim_id === row.claim_id ? current : claims.find(claim => claim.claim_id === row.claim_id), here = index === position;
      return `<li data-au-demo-case="${row.claim_id}"${here ? ' aria-current="step"' : ''}><span class="au-demo-order" aria-hidden="true">${String(index+1).padStart(2,'0')}</span><button type="button" data-au-claim="${row.claim_id}" title="${h(claim?.title || 'Original record')}" aria-label="${h(`Presentation case ${String(index+1).padStart(2,'0')}. ${row.label}. ${claim?.title || 'Original record'}`)}"><strong>${h(row.label)}</strong><span>${h(claim?.title || 'Original record')}</span></button>${claim?.status && !['not_started','not_run'].includes(claim.status) ? `<span class="au-status" data-tone="${tone(claim.status)}">${h(claimStatusLabel(claim.status,claim))}</span>` : ''}</li>`;
    }).join('')}</ol></section>`).join('')}</div>`;
  }
  function demonstrationMarkup(claims, status, mode = 'reference') {
    const availability = liveAvailability(status);
    if (mode === 'reference') return `<section class="au-demonstration"><header class="au-collection-head"><div><p class="au-eyebrow">Nine original cases · three domains</p><h1 class="au-page-heading" tabindex="-1">Follow the evidence.</h1><p class="au-lead">Historical synthetic recordings of the same cases and source files.</p></div></header><div class="au-demo-controls">${button('Play recorded work','data-au-demo-play',true)}<p class="au-meta" data-au-demo-availability>Verified recorded histories only. Unavailable assessments stop playback.</p>${recordButton('Earlier recordings','demo')}</div>${demoItineraryMarkup(claims)}</section>`;
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
  function operationLabel(operation) {
    if (operation?.kind === 'process.inspect') return 'Inspect working process';
    if (operation?.kind === 'fact.extract' && operation.result?.verification_required === false) return 'Inspect verified finding';
    if (operation?.kind === 'branch.activate' && operation.result?.activation === 'unresolved') return 'Evaluate unresolved branch';
    if (operation?.kind === 'node.evaluate') return 'Evaluate step';
    if (operation?.kind === 'dependency.evaluate') return 'Check dependency';
    if (operation?.kind === 'branch.evaluate') return 'Evaluate unresolved branch';
    return ({'source.open':'Open source','span.read':'Read passage','phrase.match':'Check source phrase','fact.extract':'Extract provisional finding','verification.check':'Verify source support','condition.evaluate':'Evaluate condition','branch.activate':'Activate branch','branch.drop':'Exclude branch','document.require':'Derive document requirement','document.check':'Check document source','decision':'Derive assessment','knowledge.reuse':'Procedure reused','knowledge.add':'Inspect historical addition','step.complete':'Complete recorded step'})[operation?.kind] || words(operation?.kind);
  }
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
    const topology = graph => ({family:graph.family,nodes:graph.nodes.map(row => ({id:row.node_id,label:name(row),documents:[...list(row.document_types)].sort()})),edges:graph.edges.map(row => ({id:row.edge_id,from:row.source_node_id,to:row.target_node_id})),documents:graph.document_catalog.map(row => ({id:row.document_type,label:name(row)}))});
    if (canonicalJSON(topology(plan.graph)) !== canonicalJSON(topology(admitted.graph))) return false;
    // Release supplements select this outline; only the current accepted
    // context can show that those exact sources belong to this investigation.
    const currentSources = list(context?.sources);
    if (release.source_sha256s.some(sha => !currentSources.some(row => row.sha256 === sha))) return false;
    const descriptor = currentSources.find(row => row.sha256 === pin.source_sha256 && row.file_name === pin.file_name), source = descriptor && list(state.acquired_sources).find(row => row.artifact_id === descriptor.artifact_id && row.sha256 === descriptor.sha256);
    return Boolean(source && source.text_sha256 === pin.text_sha256 && await digest(source.text) === pin.text_sha256 && Array.from(source.text).slice(pin.start_char,pin.end_char).join('') === pin.quote);
  }
  function releaseProcedurePreview(plan, mode = 'live') {
    const trace = {releasePlan:plan,rows:[],sources:new Map()};
    return `<section class="au-quiet-claim" data-au-stage-view="true" data-au-release-opening="${h(plan.claim_id)}"><header class="au-work-head au-focused-claim-head"><div><p class="au-eyebrow"><button type="button" class="au-back-work" data-au-nav="work">Cases</button></p><h1 class="au-page-heading" tabindex="-1">${h(featuredCase(plan.claim_id)?.label || 'Synthetic case')}</h1><p class="au-reference-mode">${mode === 'recorded' ? 'Recorded replay' : mode === 'pending' ? 'Opening investigation' : 'Live rules-based check'} · Synthetic sources · No external action</p></div></header><section class="au-evidence-canvas" data-au-canvas><div class="au-evidence-stage" data-au-evidence-stage>${operationStageMarkup(plan,{},null,trace)}<div class="au-stage-transport">${button('Pause','data-au-demo-stop')}</div></div></section></section>`;
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
    const nodes = catalog.nodes.map(node => ({node_id:node.node_id,label:name(node),document_types:catalog.documents.filter(row => list(row.required_at_node_ids).includes(node.node_id)).map(row => row.document_type)}));
    const topology = (nodes,edges) => ({nodes:nodes.map(node => ({id:node.node_id,label:name(node),documents:[...list(node.document_types)].sort()})),edges:edges.map(edge => ({id:edge.edge_id,from:edge.source_node_id,to:edge.target_node_id}))});
    // Comparing the entire pinned catalog prevents a case-pruned head from
    // silently dropping a branch from the early, unresolved plan.
    if (canonicalJSON(topology(nodes,catalog.transitions)) !== canonicalJSON(topology(graph.nodes,graph.edges))) return null;
    const ids = new Set(nodes.map(node => node.node_id));
    if (ids.size !== nodes.length || ids.has(undefined) || catalog.transitions.some(edge => !ids.has(edge.source_node_id) || !ids.has(edge.target_node_id))) return null;
    return {claim_id:state.claim_id,head_revision:state.revision,head_state_sha256:state.state_sha256,head_event_sha256:state.last_event_sha256,rule_pack_sha256:rulePackHash,
      procedure:use ? {knowledge_id:use.knowledge_id,version:use.version,definition_sha256:use.definition_sha256,knowledge_sha256:use.knowledge_sha256} : null,
      graph:{claim_id:state.claim_id,graph_sha256:graph.graph_sha256,family:graph.family,nodes,
        edges:catalog.transitions.map(edge => ({edge_id:edge.edge_id,source_node_id:edge.source_node_id,target_node_id:edge.target_node_id,label:edge.condition})),
        document_catalog:catalog.documents.map(row => ({document_type:row.document_type,label:name(row)}))},evaluation:{nodes:[],edges:[],documents:[]},facts:[],obligations:[]};
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
  function operationSourceTitle(source) { return words((source?.file_name || 'Original source').replace(/^\d+-/,'').replace(/\.[^.]+$/,'')); }
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
  function stageNodeContents(node, state, trace, working, map = false, plannedGraph = null) {
    const graph = plannedGraph || working?.graph || state.graph, rows = list(trace?.rows);
    const facts = [...(trace?.dockedFacts?.values() || [])].filter(row => row.node === node.node_id && (row.observed || list(state.facts).some(fact => fact.fact_id === row.operation.object.id)));
    const chips = facts.map(row => { const span = stageFactSpan(row.operation,true); return `<button type="button" class="au-stage-fact" data-au-fact-state="${row.operation.result.verification_required === false && list(state.facts).some(fact => fact.fact_id === row.operation.object.id) ? 'accepted' : 'observed'}" data-au-stage-fact="${h(row.operation.object.id)}" data-au-current-fact="${trace?.current?.id === row.operation.id}" data-au-fact-operation="${h(row.operation.id)}" data-au-dock-phase="${trace?.finished ? 'landed' : trace?.dockPhases?.get(row.operation.id) || 'landed'}" data-au-fact-start-char="${span.start_char}" data-au-fact-end-char="${span.end_char}" data-au-inspect="operation" data-au-record-id="${h(row.operation.id)}" aria-label="${h(stageFactLabel(row.operation,state,graph))}: ${h(span.quote)}"><span>${h(span.quote)}</span></button>`; }).join('');
    const accepted = new Map(list(state.evaluation?.documents).map(row => [row.document_type,row]));
    const observed = trace && stageDocumentIndex(rows);
    const activeRequirements = !plannedGraph && (trace ? [...observed.requirements.values()].reverse().filter(row => row.result.activation === 'true' && list(row.result.active_node_ids).includes(node.node_id) && list(node.document_types).includes(row.object.id)) : list(state.obligations).filter(row => requiringNodeIds(row,accepted.get(row.document_type)).includes(node.node_id))) || [];
    const requirements = list(node.document_types).map(type => activeRequirements.find(row => (row.object?.id || row.document_type) === type) || {document_type:type,planned:true});
    const slots = requirements.map(requirement => {
      const type = requirement.object?.id || requirement.document_type, doc = accepted.get(type), label = name(list(graph?.document_catalog).find(row => row.document_type === type)) || name(requirement) || words(type);
      const check = !requirement.planned && observed?.checks.get(type);
      const obligation = list(state.obligations).find(row => row.document_type === type);
      const citation = check?.source || (!trace && !requirement.planned ? list(obligation?.required_fact_ids).flatMap(id => citationRows(list(state.facts).find(row => row.fact_id === id)))[0] : null);
      const checked = !requirement.planned && doc?.review_state === 'sufficient' && (!trace || Boolean(check));
      const source = checked && citation && (trace?.sources.get(citation.artifact_id) || list(state.acquired_sources).find(row => row.artifact_id === citation.artifact_id));
      const preview = citation && stageFactSpan(check || {source:citation,object:{id:type}},true);
      const dockPhase = trace?.finished ? 'landed' : trace?.dockPhases?.get(check?.id) || 'landed';
      return `<div class="au-stage-slot" data-au-document="${h(type)}" data-au-stage-document="${h(type)}" data-au-document-active="${!requirement.planned}" data-au-document-planned="${Boolean(requirement.planned)}" data-au-document-supported="${Boolean(source)}" data-au-document-checked="${Boolean(source) && dockPhase === 'landed'}" data-au-document-focused="${trace?.current?.object.id === type || trace?.current?.object.id === `fact:${type}`}"${requirement.id ? ` data-au-working-document="${h(type)}" data-au-operation-id="${h(requirement.id)}" data-au-working-graph-sha="${h(requirement.result.graph_sha256)}" data-au-working-evaluation-sha="${h(requirement.result.evaluation_sha256)}"` : ''}>${map && source ? '' : `<span>${h(label)}</span>`}<div class="au-stage-landing">${source ? `<button type="button" class="au-stage-thumbnail" data-au-dock-phase="${dockPhase}" data-au-source="${h(source.artifact_id)}" data-au-source-origin="${check ? `operation:${h(check.id)}` : `requirement:${h(requirementIdentity(obligation))}`}" data-au-citation="${h(JSON.stringify(citation))}"${check ? ` data-au-check-operation="${h(check.id)}"` : ''} aria-label="${h(source.file_name || sourceLabel(state,source.artifact_id))} · Source checked" title="${h(source.file_name || sourceLabel(state,source.artifact_id))}"><span class="au-stage-source-name">${h(operationSourceTitle(source))}</span>${map ? '' : `<span class="au-stage-paper" aria-hidden="true">${h(preview.quote)}</span>`}<span class="au-stage-source-check" aria-label="Source checked">✓</span></button>` : ''}</div></div>`;
    }).join('');
    return chips+slots;
  }
  function operationStageMarkup(state, projection, selected, trace, settled = false) {
    const workingState = workingProcessState(trace), actual = workingState?.graph?.family !== 'incoming_packet' ? workingState : null;
    const availablePlan = trace?.plannedProcess || trace?.releasePlan;
    const planned = !settled && !trace?.finished && (!actual?.graph && (!state.graph || state.graph.family === 'incoming_packet' || state === trace?.releasePlan)) && availablePlan?.claim_id === state.claim_id ? availablePlan : null;
    const working = actual && trace.working, process = planned || actual || state;
    const graph = process.graph?.family !== 'incoming_packet' ? process.graph : null;
    const map = settled || trace?.finished || trace?.current?.kind === 'decision';
    const boundNode = graph && operationNodeId(trace?.current,graph,state,trace);
    const currentNode = boundNode || (list(graph?.nodes).some(row => row.node_id === selected) ? selected : null);
    const outcome = trace?.current?.kind === 'decision' && !trace.finished ? trace.current.result : state.outcome;
    const uses = list(state.knowledge_uses), use = uses.at(-1);
    const scope = working ? ` data-au-working-scope="${h(working.inspect.id)}" data-au-working-graph-sha="${h(graph?.graph_sha256)}" data-au-working-evaluation-sha="${h(working.inspect.result.evaluation_sha256)}" data-au-operation-stage="${h(working.stage)}"` : '';
    const sourceView = trace?.current && operationReading(trace)?.active ? operationReadingMarkup(trace,true) : '';
    const prefixIdentity = Number.isSafeInteger(state.revision) && isHash(state.state_sha256) ? ` data-au-forming-revision="${state.revision}" data-au-forming-sha="${h(state.state_sha256)}"` : '';
    const planAttributes = planned?.release ? ` data-au-release-plan="${h(planned.release.artifact_sha256)}" data-au-release-profile-sha="${h(planned.release.profile_sha256)}" data-au-release-catalog-sha="${h(planned.release.catalog_sha256)}" data-au-release-rule-pack-sha="${h(planned.release.rule_pack_sha256)}" data-au-release-authority="none"` : planned ? ` data-au-planned-process="${h(planned.head_state_sha256)}" data-au-planned-head-revision="${planned.head_revision}" data-au-planned-graph-sha="${h(graph.graph_sha256)}" data-au-planned-rule-pack-sha="${h(planned.rule_pack_sha256)}" data-au-planned-knowledge="${h(planned.procedure?.knowledge_id || '')}" data-au-planned-version="${planned.procedure?.version || ''}" data-au-planned-definition-sha="${h(planned.procedure?.definition_sha256 || '')}" data-au-planned-authority="none"` : '';
    const planLabel = planned?.release ? 'Procedure outline' : planned?.procedure ? knowledgeLink(planned.procedure,`${procedureLabel(planned.procedure)} · Version ${planned.procedure.version}`) : 'Recorded procedure · planned steps';

    return `<section class="au-forming-work au-operation-stage" data-au-stage-phase="${map ? 'map' : 'source'}" data-au-forming="${!map}"${prefixIdentity}><div class="au-forming-layout au-stage-layout">${!map && sourceView && !boundNode ? `<div class="au-forming-reading au-stage-source au-stage-unbound-source">${sourceView}</div>` : ''}${graph ? `<section class="au-forming-process au-evidence-process au-stage-process" aria-label="${planned?.release ? 'Procedure outline' : planned ? 'Planned recorded process' : 'Case process'}"${planAttributes}${scope}>${planned ? `<p class="au-stage-plan-label${planned.procedure ? ' au-stage-reuse' : ''}">${planLabel}</p>` : ''}${graphMarkup(process,currentNode,working ? {} : projection,{overview:true,working,stage:{state,trace,map,planned:Boolean(planned),excerpt:!map && boundNode ? sourceView : ''}})}</section>` : ''}</div>${map && outcome?.summary ? `<div class="au-stage-outcome" data-au-stage-outcome><p>${h(outcome.summary)}</p>${legalBasisMarkup({...state,outcome})}${use ? `<p class="au-stage-reuse">Procedure reused · ${knowledgeLink(use,`${procedureLabel(use)} · Version ${use.version || use.version_id}`)}</p>` : ''}</div>` : ''}</section>`;
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
    const result = trace?.buffer?.result, binding = trace?.binding;
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
    const objectLabel = operation.object.label || name(list(trace.working?.graph?.nodes).find(row => row.node_id === operation.object.id)) || name(list(trace.working?.graph?.document_catalog).find(row => row.document_type === operation.object.id)) || name(list(trace.state?.graph?.nodes).find(row => row.node_id === operation.object.id)) || name(list(trace.state?.facts).find(row => row.fact_id === operation.object.id)) || name(list(trace.state?.obligations).find(row => row.obligation_id === operation.object.id || row.document_type === operation.object.id)) || name(list(trace.state?.graph?.document_catalog).find(row => row.document_type === operation.object.id)) || '';
    const summary = operation.result?.summary || operation.result?.reason || (typeof operation.result?.matched === 'boolean' ? operation.result.matched ? 'Phrase found' : 'Phrase absent' : '');
    const sourceHTML = value => h(value).replace(/\r/g,'&#13;');
    const inkPin = pin ? stage && reading?.active ? stageFactSpan({...operation,source:pin},operation.kind === 'fact.extract' || operation.kind === 'document.check') : pin : stage && operation.kind === 'source.open' && source ? sourceBodySpan(source) : null;
    const body = stage && source && sourceBodySpan(source);
    const section = (start,end) => body && body.start_char >= start && body.start_char < end ? `${sourceHTML(chars.slice(start,body.start_char).join(''))}<span data-au-source-body-anchor></span>${sourceHTML(chars.slice(body.start_char,end).join(''))}` : sourceHTML(chars.slice(start,end).join(''));
    const passage = chars ? inkPin ? `${section(0,inkPin.start_char)}<${reading.active ? 'mark' : 'span'} ${reading.active ? 'data-au-operation-span' : 'data-au-operation-read-context'}="${h(reading.id)}" data-au-operation-start-char="${inkPin.start_char}" data-au-operation-end-char="${inkPin.end_char}">${section(inkPin.start_char,inkPin.end_char)}</${reading.active ? 'mark' : 'span'}>${section(inkPin.end_char,chars.length)}` : section(0,chars.length) : '';
    if (stage) {
      if (!source || !inkPin) return '';
      const sourceBody=sourceBodySpan(source), floor=Math.max(pin?.start_char || 0,sourceBody?.start_char || 0), ceiling=Math.min(chars.length,pin?.end_char ?? chars.length);
      let left=Math.max(floor,inkPin.start_char-48), right=Math.min(ceiling,inkPin.end_char+48);
      // Keep surrounding native words and the nearest sentence boundary whole.
      // Display normalization affects only this one context line, never a pin.
      while (left < inkPin.start_char && left > 0 && /\S/u.test(chars[left-1]) && /\S/u.test(chars[left])) left++;
      while (right > inkPin.end_char && right < chars.length && /\S/u.test(chars[right-1]) && /\S/u.test(chars[right])) right--;
      const before=chars.slice(left,inkPin.start_char).join(''), boundary=[...before.matchAll(/[.!?]\s+|[\r\n]+/gu)].at(-1);
      if (boundary) left+=Array.from(before.slice(0,boundary.index+boundary[0].length)).length;
      const after=chars.slice(inkPin.end_char,right).join(''), end=after.match(/[.!?](?=\s|$)|[\r\n]/u);
      if (end) right=inkPin.end_char+Array.from(after.slice(0,end.index+end[0].length)).length;
      const context = chars.slice(left,right).join('').replace(/\s+/gu,' ').trim();
      return `<section class="au-operation-reading" data-au-operation-object="${h(operation.object.id)}" data-au-object-type="${h(operation.object.type)}" data-au-object-id="${h(operation.object.id)}"><button type="button" class="au-stage-source-title" title="${h(source.file_name || 'Original source')}" data-au-source="${h(source.artifact_id)}" data-au-source-origin="operation:${h(reading.id)}"${pin ? ` data-au-citation="${h(JSON.stringify(pin))}"` : ''}>${h(source.file_name || 'Original source')}</button>${context ? `<p class="au-stage-excerpt-context">${h(context)}</p>` : ''}<pre class="au-operation-passage" data-au-compact-excerpt data-au-operation-source="${h(source.artifact_id)}" data-au-operation-text-sha="${h(source.text_sha256)}" data-au-source-active="${reading.active}"><${reading.active ? 'mark' : 'span'} ${reading.active ? 'data-au-operation-span' : 'data-au-operation-read-context'}="${h(reading.id)}" data-au-operation-start-char="${inkPin.start_char}" data-au-operation-end-char="${inkPin.end_char}" data-au-citation-start-char="${pin?.start_char ?? inkPin.start_char}" data-au-citation-end-char="${pin?.end_char ?? inkPin.end_char}">${sourceHTML(inkPin.quote)}</${reading.active ? 'mark' : 'span'}></pre></section>`;
    }
    return `<section class="au-operation-reading" data-au-operation-object="${h(operation.object.id)}" data-au-object-type="${h(operation.object.type)}" data-au-object-id="${h(operation.object.id)}"><p class="au-reading-label">${h(operationLabel(operation))}</p>${trace.previousCurrent?.id === operation.id && !trace.rows.some(row => row.id === operation.id) ? '<p class="au-meta">Earlier attempt stopped · waiting for the stored trace.</p>' : ''}${source ? `<button type="button" class="au-link" data-au-source="${h(source.artifact_id)}" data-au-source-origin="operation:${h(operation.id)}">${h(source.file_name || 'Original source')} ↗</button><pre class="au-operation-passage" data-au-operation-source="${h(source.artifact_id)}" data-au-operation-text-sha="${h(source.text_sha256)}">${passage}</pre>` : ''}${objectLabel || summary ? `<p class="au-operation-summary">${operation.object.type === 'source' ? '' : h(objectLabel)}${summary ? `${operation.object.type === 'source' || !objectLabel ? '' : ' · '}${h(summary)}` : ''}</p>` : ''}${operation.kind === 'fact.extract' && operation.result?.verification_required !== false ? '<p class="au-meta">Provisional finding · the saved process changes after verification.</p>' : operation.kind === 'knowledge.add' ? '<p class="au-meta">Historical addition · this demonstration saves no knowledge.</p>' : ''}<button type="button" class="au-link" data-au-inspect="operation" data-au-record-id="${h(operation.id)}">Inspect this step</button></section>`;
  }
  function operationHistoryMarkup(trace) {
    if (!trace?.binding && !trace?.previousAttempts?.length) return '';
    const previous = list(trace.previousAttempts).map((attempt,index) => `<section class="au-history-record"><h4>Earlier ${attempt.recorded ? 'recorded trace' : 'live assessment'} stopped</h4><p class="au-meta">${h(attempt.reason)}</p><ol class="au-event-list">${attempt.rows.slice().reverse().map(operation => `<li><button type="button" class="au-link" data-au-inspect="operation-attempt" data-au-record-id="${index}:${h(operation.id)}">${h(operationLabel(operation))} · ${h(operation.object.label || words(operation.object.id))}</button></li>`).join('')}</ol></section>`).join('');
    return `<section class="au-operation-history"><h3>Assessment operations</h3><p class="au-meta">${trace.savedFallback ? 'The attempted assessment stopped.' : !trace.binding ? 'Waiting for the stored operation trace.' : !trace.recorded && trace.binding.mode === 'historical_recomputed' ? 'Recomputed from the saved source packet.' : 'Recorded operation trace.'} Saved case history remains below.</p><ol class="au-event-list">${trace.rows.slice().reverse().map(operation => `<li><button type="button" class="au-link" data-au-inspect="operation" data-au-record-id="${h(operation.id)}">${h(operationLabel(operation))} · ${h(operation.object.label || words(operation.object.id))}</button></li>`).join('')}</ol>${previous}</section>`;
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
    let publicationAttention = null, inspectionHold = false, operationTrace = null, attentionMarker = null, attentionPosition = null, attentionAnimation = null, factToken = null, factTokenAnimation = null, factTokenOperation = null, stageMotionTimer = null, stageCameraAnimation = null, stageReadAnimations = [], stageScrollCancel = null, stageScrollTarget = null, stageChoreography = null, operationPeek = null;
    let disposed = false, epoch = 0, timer = null, selected = null, current = null, projection = {}, cursor = null, history = [], detail = 'step', view = 'work', disconnected = false, connectionFailed = false, busy = false, status = null, pendingIntake = null, pendingArrival = null, pendingControl = null, dialogReturn = null, recordReturn = null, recordSelection = null, sourceEpoch = 0, polling = null, claimRead = 0;
    let openingId = null, openingPreferences = {}, snapshotAvailable = null, presentationMode = 'saved', replayRecord = null, demoMode = 'reference', demoSession = null, demoTimer = null, pausedPresentation = null, pendingStart = null, nativeSourceURL = null;
    let evidenceContext = {}, selectionMotion = null, tetherGeometry = null, graphViewportWidth = null, interactionMotion = null, freshClaim = false, statusAuthority = null, readGeneration = 0;
    let knowledgeWarmGeneration = -1, knowledgeFacet = 'process', knowledgePin = null, lastCaseContext = null, collectionCache = null, knowledgeCache = null, statusCache = null, knowledgeRead = 0, renderedKnowledge = null;
    const snapshots = new Map(), sourcePreviews = new Map(), nativeBytes = new Map(), replayPrefixes = new Map(), inflightReads = new Map(), readOwners = new Map();
    const savedHeads = new Map(), warmQueue = [], warmAttempts = new Set(), warmIntents = new Set(), warmWorkers = new Set();
    let savedKnowledge = null, sessionRestore = null, storageWrite = 0, warmActive = 0, warmTicket = 0, warmIdle = null;
    let storage = null, apiIdentity = null;
    try { if (root.location?.href) { apiIdentity = new URL(base,root.location.href).href; storage = root.sessionStorage; } } catch (_) { /* Session storage is optional. */ }
    const controllers = new Set();
    let recordedPacket = null, packetVerification = null, packetLoadController = null;
    const reduced = root.matchMedia?.('(prefers-reduced-motion: reduce)');
    let motion = null, keyboard = false, examples = null, routedFragment = null, intakeForm = null, claims = [], claimsLoaded = false, claimsRead = 0, claimRenderComplete = false, renderedClaimId = null;
    const claimViews = new Map(), arrivalForms = new Map(), arrivals = new Map(), controls = new Map(), starts = new Map();
    const collection = {search:'',filter:'all',domain:'all',scope:'originals',page:1};
    container.classList.add('au-workspace');
    container.removeAttribute('data-au-keyboard');
    container.innerHTML = `<div class="au-shell au-identity-shell"><header class="au-identity-header"><a class="au-brand" href="#autonomous/cases">CasePath<span>Evidence into action</span></a>${publicReadOnly ? '' : '<button type="button" class="au-header-new" data-au-nav="intake">New claim <span aria-hidden="true">↗</span></button>'}<span class="au-access-label" data-au-public-access${publicReadOnly ? '' : ' hidden'}>Read-only</span><nav class="au-nav" aria-label="CasePath"><button type="button" data-au-nav="work" aria-current="page">Cases</button><button type="button" data-au-nav="demonstration">Demonstration</button><button type="button" data-au-nav="knowledge">Knowledge</button></nav><div class="au-case-return" data-au-case-return hidden></div></header><${mainTag} class="au-main"><div class="au-global-status" role="status" aria-live="polite"></div><div class="au-body" data-au-view data-au-view-state="work"></div></${mainTag}></div><dialog class="au-source-dialog" aria-labelledby="auSourceTitle"><header class="au-dialog-header"><div><p class="au-eyebrow">Original source</p><h2 id="auSourceTitle">Source</h2></div><button type="button" class="au-secondary" data-au-close>Close source</button></header><div data-au-source-content></div></dialog><dialog class="au-record-dialog" aria-labelledby="auRecordTitle"><header class="au-dialog-header"><h2 id="auRecordTitle">Record</h2><button type="button" class="au-secondary" data-au-close-record>Close</button></header><div data-au-record-content></div></dialog>`;
    const host = container.querySelector('[data-au-view]'), globalStatus = container.querySelector('.au-global-status'), dialog = container.querySelector('.au-source-dialog'), recordDialog = container.querySelector('.au-record-dialog');
    function notice(message, error = false) { globalStatus.textContent = message; globalStatus.classList.toggle('au-error', error); }
    function route(fragment, writeHistory = true) {
      if (writeHistory && root.location && root.location.hash !== fragment && root.history?.pushState) root.history.pushState(null,'',root.location.pathname + root.location.search + fragment);
      routedFragment = writeHistory ? fragment : root.location ? root.location.hash : fragment;
      if (dialog.open) { dialogReturn = null; sourceEpoch++; clearNativeSource(); dialog.close(); }
      if (recordDialog.open) { recordReturn = null; recordDialog.close(); }
    }
    function pendingRoute() { return Boolean(root.location && root.location.hash !== routedFragment); }
    function routeChanged() {
      if (disposed || busy || (!root.location && routedFragment !== null)) return;
      const fragment = root.location?.hash || '';
      if (fragment === routedFragment) return;
      if (fragment === '#autonomous/knowledge') showKnowledge(false);
      else if (fragment.startsWith('#autonomous/knowledge?')) { const params = new URLSearchParams(fragment.slice(fragment.indexOf('?')+1)); showKnowledge(false,{knowledge_id:params.get('knowledge'),version:params.get('version'),knowledge_sha256:params.get('sha256'),definition_sha256:params.get('definition')}); }
      else if (fragment.startsWith('#autonomous/claim/')) {
        try { const [encoded,query = ''] = fragment.slice('#autonomous/claim/'.length).split('?'), params = new URLSearchParams(query), id = decodeURIComponent(encoded); id ? openClaim(id,false,{mode:params.get('mode') === 'replay' ? 'replay' : 'saved',through:Number(params.get('through') || 0),collection:params.get('collection'),detail:params.get('detail'),node:params.get('node'),document:params.get('document'),obligation:params.get('obligation'),fact:params.get('fact'),trace:params.get('trace') === '1',operations:operationRoutePreference(fragment,root.location?.search)}) : showWork(false); }
        catch (_) { showWork(false); }
      } else if (fragment.startsWith('#autonomous/demonstration')) { const params = new URLSearchParams(fragment.split('?')[1] || ''); showDemonstration(false,params.get('collection') === 'legacy' ? 'legacy' : 'reference',operationRoutePreference(fragment,root.location?.search)); }
      else if (fragment.startsWith('#autonomous/cases?') || fragment.startsWith('#autonomous/work?')) {
        const params = new URLSearchParams(fragment.split('?')[1]); collection.search = params.get('q') || ''; collection.filter = statusFilter(params.get('status') || 'all'); collection.domain = params.get('domain') || 'all'; collection.scope = params.get('scope') === 'added' ? 'added' : 'originals'; collection.page = Number(params.get('page') || 1); showWork(false);
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
      const generation = readGeneration, write = ++storageWrite, now = Date.now();
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
      cancelWarmReads(); warmAttempts.clear(); warmIntents.clear(); storageWrite++; savedHeads.clear(); savedKnowledge = null;
      try { storage?.removeItem(READ_CACHE_CONTRACT); } catch (_) { /* Storage is optional. */ }
      readGeneration++; claimRead++; claimsRead++; knowledgeRead++; collectionCache = null; knowledgeCache = null; statusCache = null;
      if (id) snapshots.delete(id); else snapshots.clear();
      sourcePreviews.clear(); nativeBytes.clear(); replayPrefixes.clear();
      freshClaim = false; statusAuthority = null; synchronizeAuthority('refreshing');
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
        control.textContent = pending ? busy ? ({start:'Starting…',pause:'Pausing…',resume:'Resuming…'})[action] : `Retry ${action}` : action === 'start' ? 'Start investigation' : `${words(action)} work`;
        control.disabled = publicReadOnly || busy || !freshClaim || !writable(status) || presentationMode === 'replay' || control.hasAttribute('data-au-resume') && !intakeEligible(projection) || control.hasAttribute('data-au-start') && !canStartHere() && !pendingStart;
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
      if (readonly && inflightReads.has(identity)) { if (!quiet && readOwners.has(identity)) readOwners.get(identity).foreground = true; return inflightReads.get(identity); }
      const controller = new AbortController(); controllers.add(controller);
      const owner = {controller,foreground:!quiet}; if (readonly) readOwners.set(identity,owner);
      const timeout = root.setTimeout(() => controller.abort(),15000);
      const operation = (async () => {
        try {
          const response = await fetcher(base + path,{...init,signal:controller.signal,headers:{Accept:'application/json',...(init.body ? {'Content-Type':'application/json','X-CasePath-Agent-Work':'1'} : {}),...init.headers},cache:'no-store'});
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
        const timeout = root.setTimeout(() => controller.abort(),15000);
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
    function focusTitle() { if (!doc.hidden) host.querySelector('h1')?.focus({preventScroll:true}); }
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
      navigation.innerHTML = `<span class="au-case-return-label">${h(lastCaseContext.label)}</span><button type="button" class="au-link" data-au-return-case="step">Process</button><button type="button" class="au-link" data-au-return-case="documents">Documents</button>`;
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
    function drawEdges(navigation = false) {
      if (disposed) return;
      // Read every relevant rectangle before writing SVG geometry.
      const trace = operationPeek?.trace || operationTrace, prefix = operationPeek?.state || current, planned = Boolean(host.querySelector('[data-au-planned-process],[data-au-release-plan]')), displayed = planned ? trace.plannedProcess || trace.releasePlan : workingProcessState(trace) || prefix, graphSelected = planned ? null : operationNodeId(trace?.current,displayed?.graph,displayed) || operationPeek?.node || selected;
      const graph = host.querySelector('[data-au-graph]'), graphSvg = graph?.querySelector('svg'), frame = graph?.getBoundingClientRect?.();
      let graphPaths = null;
      if (graphSvg && frame?.width && frame.height && displayed?.graph) {
        const nodes = new Map([...graph.querySelectorAll('[data-au-node]')].map(element => {
          const junction = element.querySelector('[data-au-junction]') || element;
          return [element.dataset.auNode,{bounds:junction.getBoundingClientRect(),rank:Number(element.closest('.au-graph-rank').dataset.rank)}];
        }));
        const ranks = new Map([...graph.querySelectorAll('.au-graph-rank')].map(element => [Number(element.dataset.rank),element.getBoundingClientRect()]));
        graphPaths = list(displayed.graph.edges).map((edge,index) => {
          const from = nodes.get(edge.source_node_id), to = nodes.get(edge.target_node_id); if (!from || !to || !from.bounds.width || !from.bounds.height || !to.bounds.width || !to.bounds.height) return null;
          const vertical = graph.dataset.orientation === 'vertical';
          const x1=(vertical ? from.bounds.left+from.bounds.width/2 : from.bounds.right)-frame.left,y1=(vertical ? from.bounds.bottom : from.bounds.top+from.bounds.height/2)-frame.top,x2=(vertical ? to.bounds.left+to.bounds.width/2 : to.bounds.left)-frame.left,y2=(vertical ? to.bounds.top : to.bounds.top+to.bounds.height/2)-frame.top;
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
    function leaveView(keepAcquiredPacket = false) {
      if (!recordedPacket && !(keepAcquiredPacket && packetVerification)) packetLoadController?.abort();
      cancelWarmReads();
      motion?.cancel(); selectionMotion?.cancel(); interactionMotion?.cancel(); tetherGeometry = null;
      if (view === 'intake') { intakeForm = host.querySelector('[data-au-intake]') || intakeForm; intakeForm?.remove?.(); }
      if (view === 'work') { const main = container.querySelector('.au-main'); collection.scrollTop = host.scrollTop || 0; collection.mainTop = main?.scrollTop || 0; collection.mainLeft = main?.scrollLeft || 0; collection.scrollX = root.scrollX || 0; collection.scrollY = root.scrollY || 0; }
      preserveClaimView();
    }
    function setView(name) { if (name !== 'claim') { for (const attribute of ['data-au-current-operation','data-au-operation-run-mode','data-au-operation-presentation','data-au-operation-result-available','data-au-operation-result-verified']) host.removeAttribute?.(attribute); } view = name; renderedClaimId = null; freshClaim = false; statusAuthority = null; host.setAttribute?.('data-au-view-state',name); host.removeAttribute?.('data-au-read-state'); }
    function revealGraphNode(node, center = false) {
      const viewport = host.querySelector('.au-graph-viewport');
      const area = viewport?.getBoundingClientRect?.(), bounds = node?.getBoundingClientRect?.();
      if (!area || !bounds) return;
      if (center || bounds.left < area.left+8 || bounds.right > area.right-8) viewport.scrollLeft += bounds.left-area.left-(area.width-bounds.width)/2;
      if (center || bounds.top < area.top+8 || bounds.bottom > area.bottom-8) viewport.scrollTop += bounds.top-area.top-(area.height-bounds.height)/2;
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
    function renderClaim(changes = null, navigation = false) {
      const displayedState = operationPeek?.state || current, displayedProjection = operationPeek?.projection || projection, displayedTrace = operationPeek?.trace || operationTrace;
      if (!current || view !== 'claim') return;
      if (inspectionHold && pausedPresentation && host.querySelector('[data-au-release-opening]')) return;
      if (doc.hidden) { claimRenderComplete = false; return; }
      evidenceContext = evidenceSelection(current,selected,evidenceContext);
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
      const stageBefore = host.querySelector('.au-operation-stage'), priorStagePhase = stageBefore?.dataset.auStagePhase;
      const enteringMap = priorStagePhase === 'source' && (displayedTrace?.finished || displayedTrace?.current?.kind === 'decision');
      const priorProcessBounds = enteringMap && !doc.hidden && !inspectionHold && !reduced?.matches ? stageBefore.querySelector('.au-stage-process')?.getBoundingClientRect() : null;
      host.innerHTML = workMarkup(displayedState,displayedProjection,operationPeek?.node || selected,operationPeek?.events || history,detail,evidenceContext,{mode:presentationMode,readOnly:publicReadOnly,replay:replayRecord,knowledge:knowledgeCache?.value,attention:publicationAttention || {},inspectionHold,pendingStart:Boolean(pendingStart),operations:displayedTrace,transportOperations:operationTrace,inspectionIndex:operationPeek?.index,operationOpening:(demoSession || pausedPresentation)?.mode === 'operations',playing:Boolean(demoSession),paused:Boolean(pausedPresentation),position:demoSession?.index,claims,writable:writable(status),status,availability:pendingStart ? {ready:true,reason:'The start response is unconfirmed. Retry uses the same request.'} : claimAvailability(status,current,projection)});
      reuseSourceControls(host,sources);
      const stageAfter = host.querySelector('.au-operation-stage'), processAfter = stageAfter?.querySelector('.au-stage-process');
      if (priorStagePhase === 'source' && stageAfter?.dataset.auStagePhase === 'map' && priorProcessBounds && processAfter && !doc.hidden && !inspectionHold && !reduced?.matches) {
        const bounds = processAfter.getBoundingClientRect();
        stageCameraAnimation?.cancel(); stageCameraAnimation = processAfter.animate([{transform:`translate(${priorProcessBounds.left-bounds.left}px,${priorProcessBounds.top-bounds.top}px) scale(${priorProcessBounds.width/bounds.width},${priorProcessBounds.height/bounds.height})`,opacity:.5},{transform:'translate(0,0) scale(1,1)',opacity:1}],{duration:700,easing:'cubic-bezier(.18,.8,.25,1)',fill:'none'});
      }
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
      positionOperationSource();
      drawEdges(navigation);
      motion = animateTransition(host,changes,{hidden:doc.hidden,dialogOpen:dialog.open || recordDialog.open,reducedMotion:reduced?.matches,keyboard,inspecting:inspectionHold,activeElement:doc.activeElement,selected});
      synchronizeAuthority(); synchronizeRecord(); rememberLastCase(); positionOperationAttention();
      claimRenderComplete = true; renderedClaimId = current.claim_id;
    }
    function setGraphExpanded(expanded) {
      const viewport = host.querySelector('[data-au-graph-pan]'), control = host.querySelector('[data-au-expand-process]');
      if (!viewport || !control) return;
      viewport.dataset.auGraphExpanded = String(expanded);
      control.setAttribute('aria-expanded',String(expanded));
      const overview = viewport.dataset.auGraphOverview === 'true';
      control.textContent = overview ? expanded ? 'Close larger process' : 'Open larger process' : expanded ? 'Close full process' : 'Open full process';
      viewport.setAttribute('aria-label',expanded || overview ? 'Complete process; use arrow keys or scroll to explore' : 'Selected decision, its prerequisites and following decisions; open full process to explore the complete graph');
      host.querySelector('.au-evidence-process')?.setAttribute('aria-label',expanded || overview ? 'Complete process' : 'Decision neighborhood');
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
      drawEdges(navigation); interact(panel); rememberLastCase();
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
          if (!current) host.innerHTML = (catalogPreviewMarkup(claims.find(claim => claim.claim_id === id),id) || unknownClaimMarkup(id)) + button('Retry opening claim',`data-au-claim="${h(id)}"`);
          if (error.transientAdvance || !error.status || error.status >= 500) schedule();
        }
      }
    }
    function selectedClaimFragment() { return claimFragment(current.claim_id,{mode:presentationMode,collection:openingPreferences.collection,operations:openingPreferences.operations,through:replayRecord?.through_seq,detail,node:selected,...evidenceContext}); }
    function rememberSelectionRoute() { if (current) route(selectedClaimFragment()); }
    function paintSavedClaim(id, preferences) {
      const cached = cachedRead(snapshots,id);
      if (!cached) return false;
      const failed = host.getAttribute?.('data-au-read-state') === 'failed';
      current = cached.state; projection = cached.projection; cursor = cached.cursor; history = [...cached.history];
      const previous = claimViews.get(id); selected = preferredNode(current,preferences.node || previous?.selected,history); evidenceContext = preferredEvidenceContext(current,selected,history,preferences,previous); detail = preferences.detail || previous?.detail || 'step';
      renderClaim(); synchronizeAuthority(failed ? 'failed' : 'refreshing'); focusTitle(); if (!failed) notice('');
      return true;
    }
    async function openClaim(id, writeHistory = true, preferences = {}) {
      if (preferences.mode === 'replay') preferences = {...preferences,collection:replayCollection(id,preferences.collection)};
      if (!preferences.demo) stopPresentation();
      else { if (demoTimer) root.clearTimeout(demoTimer); demoTimer = null; if (demoSession) demoSession.preparing = null; }
      leaveView(Boolean(preferences.demo && demoSession?.mode === 'operations' && !doc.hidden)); route(claimFragment(id,preferences),writeHistory);
      operationPeek = null; host.removeAttribute?.('data-au-inspection-operation'); cancelStageMotion(); epoch++; const token = epoch; if (preferences.demo && demoSession) demoSession.epoch = token; cancelPoll(); motion?.cancel(); setView('claim'); publicationAttention = null; inspectionHold = Boolean(preferences.node || preferences.document || preferences.obligation || preferences.fact || ['sources','documents','knowledge','activity'].includes(preferences.detail)); operationTrace = null; factTokenOperation = null; factTokenAnimation?.cancel(); factToken?.remove?.(); attentionMarker?.remove?.(); attentionPosition = null; current = null; openingId = id; openingPreferences = preferences; selected = null; cursor = null; history = []; disconnected = false; connectionFailed = false; pendingArrival = arrivals.get(id) || null; pendingControl = controls.get(id) || null; pendingStart = starts.get(id) || null; presentationMode = preferences.mode || 'saved'; replayRecord = null; nav(preferences.demo || presentationMode === 'replay' ? 'demonstration' : 'work'); notice('');
      claimRenderComplete = false; detail = preferences.detail || 'step';
      for (const attribute of ['data-au-current-operation','data-au-operation-run-mode','data-au-operation-presentation','data-au-operation-result-available','data-au-operation-result-verified']) host.removeAttribute?.(attribute);
      if (presentationMode !== 'replay') serviceStatus(token,true).catch(error => { if (!disposed && token === epoch) { statusAuthority = null; synchronizeAuthority(); notice(`Live availability unavailable: ${error.message}`,true); } });
      let opening = preferences.demo && demoSession?.verifiedOpening?.claimId === id && demoSession.verifiedOpening.generation === readGeneration ? demoSession.verifiedOpening : null;
      const session = preferences.demo ? demoSession : null;
      const packetAtSelection = session?.mode === 'operations' ? recordedPacket || packetVerification : null;
      if (session?.mode === 'operations' && !packetAtSelection) packetLoadController?.abort();
      if (session?.mode === 'operations') { session.releasePlan = releaseOperationProcess(id); if (session.releasePlan) operationTrace = {releasePlan:session.releasePlan,rows:[],sources:new Map()}; }
      if (demoSession) demoSession.verifiedOpening = null;
      const cached = presentationMode !== 'replay' && paintSavedClaim(id,preferences);
      if (!doc.hidden && !cached && !opening) { host.innerHTML = session?.releasePlan ? releaseProcedurePreview(session.releasePlan,packetAtSelection ? 'pending' : session.operations) : catalogPreviewMarkup(claims.find(claim => claim.claim_id === id),id) || unknownClaimMarkup(id); focusTitle(); if (session?.releasePlan) drawEdges(); }
      interact(host);
      if (presentationMode !== 'replay') {
        sessionRestore?.then(() => { if (!disposed && token === epoch && !pendingRoute() && view === 'claim' && !current && id === openingId) paintSavedClaim(id,preferences); });
        return loadOpenedClaim(id,token,preferences);
      }
      if (session) session.preparing = token;
      if (session?.mode === 'operations') { cancelIdleReadOwners(); if (!opening?.referenceReady && !doc.hidden && !inspectionHold && !(packetAtSelection && session.useRecorded)) prepareOperationReads(session,id,token); }
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
        const previous = claimViews.get(id); selected = preferredNode(current,preferences.node || previous?.selected,history); evidenceContext = preferredEvidenceContext(current,selected,history,preferences,previous); detail = inspectionHold ? detail : preferences.detail || previous?.detail || 'step';
        renderClaim(); notice(''); if (!inspectionHold && !doc.hidden && !dialog.open && !recordDialog.open) focusTitle();
        primeClaimReads(token,!claimsLoaded);
        if (preferences.demo && ['replay','operations'].includes(session?.mode)) {
          session.replayHead = {claimId:id,revision:replayRecord.current_revision,state_sha256:replayRecord.current_state_sha256,event_sha256:replayRecord.current_event_sha256};
          session.referenceReady = Boolean(opening?.referenceReady);
          session.replayStart = through === 0 && session.collection !== 'legacy' ? incoming.replay.replay_start : null;
          session.verifiedReplayStart = opening?.verifiedReplayStart || null; session.verifiedJournal = opening?.verifiedJournal || null; session.referenceAsOf = opening?.referenceAsOf; session.operationBinding = opening?.operationBinding; session.plannedProcess = opening?.plannedProcess || null;
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
      queue.innerHTML = claims.slice(0,6).map(claim => `<button type="button" class="au-recent-claim" data-au-claim="${h(claim.claim_id)}"${current?.claim_id === claim.claim_id && view === 'claim' ? ' aria-current="page"' : ''}><strong>${h(claim.title || 'Untitled claim')}</strong><span data-tone="${tone(claim.status)}">${h(claimStatusLabel(claim.status,claim))}</span></button>`).join('') || '<p class="au-empty">No saved claims yet.</p>';
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
    function refreshCollection() {
      if (view !== 'work') return;
      const previousPage = collection.page, page = collectionPage(claims,collection); collection.page = page.page;
      if (previousPage !== page.page && !pendingRoute()) rememberCollectionRoute();
      const output = host.querySelector('[data-au-claims]'); if (output) output.innerHTML = claimsMarkup(claims,collection);
      const pagination = host.querySelector('[data-au-pagination]'); if (pagination) { const holder = doc.createElement?.('div'); if (holder) { holder.innerHTML = paginationMarkup(page); pagination.replaceWith(holder.firstElementChild); } }
      for (const control of host.querySelectorAll('[data-au-filter]')) control.setAttribute('aria-pressed',String(control.dataset.auFilter === collection.filter));
      const scoped = collectionRows(claims,collection.scope);
      const count = host.querySelector('[data-au-collection-count]'); if (count) count.textContent = `${matchingClaims(scoped,collection).length} of ${scoped.length}`;
      const summary = host.querySelector('.au-collection-summary');
      if (summary) summary.innerHTML = collectionCounts(scoped,collection.scope).map(([label,count]) => `<span><strong>${count}</strong> ${h(label)}</span>`).join('');
      for (const control of host.querySelectorAll('[data-au-collection-scope]')) {
        control.setAttribute('aria-pressed',String(collection.scope === control.dataset.auCollectionScope));
        const number = control.querySelector('span'); if (number) number.textContent = String(collectionRows(claims,control.dataset.auCollectionScope).length);
      }
      for (const control of host.querySelectorAll('[data-au-domain]')) {
        const id = control.dataset.auDomain, count = id === 'all' ? scoped.length : scoped.filter(claim => domainOf(claim) === id).length;
        control.setAttribute('aria-pressed',String(collection.domain === id)); control.disabled = id !== 'all' && !count;
        const number = control.querySelector('strong'); if (number) number.textContent = String(count);
      }
      const filter = host.querySelector('[data-au-claim-filter]');
      if (filter) filter.innerHTML = collectionFilters(scoped).map(value => `<option value="${h(value)}"${collection.filter === value ? ' selected' : ''}>${h(value === 'all' ? 'All statuses' : value === 'working' ? 'In progress' : value === 'investigation_complete' ? 'Assessment complete' : statusLabel(value))}</option>`).join('');
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
        if (JSON.stringify(data).length * 2 <= 8 * 1024 * 1024) knowledgeCache = {value:data};
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
      claimsLoaded = true; railClaims(); refreshCollection(); refreshDemonstration(); warmKnowledge(token); primeClaimReads(token);
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
        const start = host.querySelector('[data-au-start]'); if (start) start.disabled = busy || !freshClaim || !canStartHere() && !pendingStart;
        const availability = host.querySelector('[data-au-start-availability]'); if (availability) availability.textContent = claimAvailability(status,current,projection).reason;
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
      if (service) service.textContent = !writable(status) ? 'This workspace is read-only.' : !status.enabled ? 'Autonomous work is disabled.' : !status.provider_ready ? 'Inference is unavailable. New packets are saved with a named deferral.' : allowanceMessage ? `${allowanceMessage} You can still save a new claim; autonomous work will have a named deferral.` : 'Local evidence acquisition and document preparation are available. External dispatch is not configured.';
      if (view === 'intake' && !busy && !pendingIntake) idleIntakeSubmit(host.querySelector('[data-au-intake]'));
      if (view === 'intake' && !status.enabled && !pendingIntake) { const submit = host.querySelector('button[type="submit"]'); if (submit) submit.disabled = true; }
    }
    function collectionFragment() {
      const params = new URLSearchParams();
      if (collection.scope === 'added') params.set('scope','added');
      if (collection.search) params.set('q',collection.search);
      if (collection.filter !== 'all') params.set('status',collection.filter);
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
      const selection = host.querySelector('.au-demo-selection');
      if (selection) { const wrapper = doc.createElement?.('div'); if (wrapper) { wrapper.innerHTML = demonstrationMarkup(claims,status,demoMode); selection.innerHTML = wrapper.querySelector('.au-demo-selection').innerHTML; } }
      for (const choice of host.querySelectorAll('[data-au-demo-mode]')) choice.setAttribute('aria-pressed',String(choice.dataset.auDemoMode === demoMode));
      const play = host.querySelector('[data-au-demo-play]'); if (play) { play.textContent = demoMode === 'live' ? 'Start live presentation' : 'Play recorded work'; play.disabled = demoMode === 'live' && !liveAvailability(status).ready; }
      const availability = host.querySelector('[data-au-demo-availability]'); if (availability) availability.textContent = demoMode === 'live' ? liveAvailability(status).reason : 'Recorded executions only. Playback stops if no operational outcome was accepted.';
    }
    async function showDemonstration(writeHistory = true, collection = 'reference', operations = operationRoutePreference(root.location?.hash,root.location?.search)) {
      if (busy) return;
      stopPresentation(); demoMode = collection === 'legacy' ? 'replay' : 'reference';
      const chosen = claimFragment(demoCases(collection)[0].claim_id,{mode:'replay',collection,operations,through:0,detail:'step'});
      route(chosen,writeHistory);
      if (!writeHistory && root.history?.replaceState && root.location?.hash !== chosen) { root.history.replaceState(null,'',root.location.pathname + root.location.search + chosen); routedFragment = chosen; }
      demoSession = {mode:collection === 'legacy' ? 'replay' : 'operations',collection,index:0,operations,useRecorded:operations === 'recorded'};
      await openPresentationCase(demoSession,writeHistory);
    }
    function stopPresentation() {
      const session = demoSession || pausedPresentation;
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
    function positionOperationSource() {
      const pane = host.querySelector('.au-operation-passage');
      if (!pane) return;
      if (doc.hidden) return;
      if (pane.hasAttribute('data-au-compact-excerpt')) { const source=pane.closest('.au-stage-source'), step=pane.closest('.au-stage-step'); if (source && step) step.style.setProperty('--au-stage-excerpt-height',`${source.offsetHeight}px`); return; }
      const operation = (operationPeek?.trace || operationTrace)?.current, mark = pane.querySelector('[data-au-operation-span]');
      if (mark && mark.dataset.auOperationSpan === operation?.id) {
        const frame = pane.getBoundingClientRect(), bounds = mark.getBoundingClientRect(), body = pane.querySelector('[data-au-source-body-anchor]'), floor = body ? pane.scrollTop+body.getBoundingClientRect().top-frame.top-28 : 0, top = pane.scrollTop + bounds.top-frame.top-Math.max(28,(frame.height-bounds.height)/2);
        const target = Math.max(0,Math.min(pane.scrollHeight-pane.clientHeight,Math.max(floor,top))); stageScrollTarget = {pane,top:target};
        pane.scrollTo?.({top:target,behavior:operationPeek || inspectionHold || reduced?.matches ? 'instant' : 'smooth'});
      } else if (operation?.kind === 'source.open') { const body = pane.querySelector('[data-au-operation-read-context]'); const top = body ? pane.scrollTop+body.getBoundingClientRect().top-pane.getBoundingClientRect().top-30 : 0; pane.scrollTo?.({top:Math.max(0,top),behavior:'instant'}); }
    }
    function cancelStageRead() {
      stageScrollCancel?.(); stageScrollCancel = null;
      if (stageMotionTimer) root.clearTimeout(stageMotionTimer); stageMotionTimer = null;
      if (factTokenAnimation?.playState === 'running') factTokenOperation = null;
      attentionAnimation?.cancel(); factTokenAnimation?.cancel(); factToken?.remove?.(); attentionMarker?.remove?.();
      for (const animation of stageReadAnimations) animation.cancel(); stageReadAnimations = [];
      for (const trail of host.querySelectorAll('[data-au-read-trail]')) trail.remove();
      for (const chip of host.querySelectorAll('[data-au-fact-docking]')) { chip.style.opacity = ''; chip.removeAttribute('data-au-fact-docking'); }
      if (stageChoreography && !stageChoreography.complete) { stageChoreography.cancelled=true; stageChoreography.resolve(); }
    }
    function cancelStageMotion() { cancelStageRead(); stageCameraAnimation?.cancel(); }
    function afterSourceScroll(pane, callback) {
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
    function positionOperationAttention(animate = true, sourceReady = false, pending = null) {
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
      if (node) revealGraphNode(node.closest('.au-stage-step') || node,true);
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
        if (!canDock || operationTrace !== ownerTrace || ownerTrace.current !== operation || doc.hidden || inspectionHold || reduced?.matches || !dock.isConnected) { complete(); return; }
        factTokenOperation = operation.id; ownerTrace.dockPhases ||= new Map(); ownerTrace.dockPhases.set(operation.id,'transfer'); dock.dataset.auDockPhase='transfer';
        const next = local(dockRect.left,dockRect.top), span = stageFactSpan(operation,true);
        factToken = doc.createElement('span'); factToken.className = 'au-operation-fact-token'; factToken.dataset.auOperationId = operation.id; factToken.dataset.auObjectType = documentDock ? 'document' : 'fact'; factToken.dataset.auObjectId = operation.object.id; factToken.setAttribute('aria-hidden','true');
        if (documentDock) { const title=doc.createElement('strong'), quote=doc.createElement('span'); title.textContent=reading.source.file_name || 'Original source'; quote.textContent=span.quote; factToken.append(title,quote); } else factToken.textContent = span.quote;
        factToken.dataset.auSourceArtifact = operation.source.artifact_id; factToken.dataset.auSourceSha = operation.source.sha256;
        factToken.dataset.auSourceStartChar = span.start_char; factToken.dataset.auSourceEndChar = span.end_char; factToken.dataset.auCitationStartChar = operation.source.start_char; factToken.dataset.auCitationEndChar = operation.source.end_char;
        if (documentDock) factToken.dataset.auDocumentTransfer = operation.id;
        factToken.style.transform = transform(next); canvas.appendChild(factToken);
        dock.dataset.auFactDocking = operation.id; dock.style.opacity = '0';
        const flight = [{transform:`${transform(origin)} scale(.82)`,opacity:0,offset:0},{transform:`${transform(origin)} scale(1)`,opacity:1,offset:.18}];
        // Sample one cubic curve once, never on animation frames.
        const bend = Math.max(32,Math.min(100,Math.abs(next.x-origin.x)*.25));
        for (let step=1; step<=8; step++) { const t=step/8, u=1-t; const point={x:u*u*u*origin.x+3*u*u*t*(origin.x+bend)+3*u*t*t*(next.x-bend)+t*t*t*next.x,y:u*u*u*origin.y+3*u*u*t*(origin.y-24)+3*u*t*t*(next.y-24)+t*t*t*next.y}; flight.push({transform:transform(point),opacity:1,offset:.18+.82*t}); }
        factTokenAnimation = factToken.animate(flight,{duration:600,easing:'cubic-bezier(.18,.7,.25,1)',fill:'none'});
        const token = factToken; factTokenAnimation.onfinish = () => { token.remove(); if (operationTrace !== ownerTrace || ownerTrace.current !== operation) { complete(); return; } ownerTrace.dockPhases.set(operation.id,'landed'); if (dock.isConnected) { dock.dataset.auDockPhase='landed'; dock.style.opacity=''; dock.removeAttribute('data-au-fact-docking'); const slot=dock.closest('[data-au-stage-document]'); if (slot) slot.dataset.auDocumentChecked='true'; } complete(); };
        node.dataset.auOperationId = operation.id; attentionPosition = next;
      };
      if (factTokenAnimation?.playState === 'running') return;
      attentionMarker ||= doc.createElement('div'); attentionMarker.className = 'au-operation-attention'; attentionMarker.setAttribute('aria-hidden','true'); attentionMarker.dataset.auOperationAttention = operation.id; attentionMarker.dataset.auActor = reading?.active ? 'reading' : 'process'; delete attentionMarker.dataset.auReadPhase; attentionMarker.style.height='';
      canvas.appendChild(attentionMarker); attentionMarker.style.transform = transform(origin);
      if (animate && reading?.active && operationTrace.dockPhases?.get(operation.id) === 'transfer') { mark.dataset.auPhraseLocked=operation.id; transfer(); return; }
      if (animate && reading?.active && lineRects.length) {
        const visible = lineRects.filter(line => line.width > 0 && (!clip || line.top >= clip.top-1 && line.bottom <= clip.bottom+1)), duration = Math.min(1000,operationReadDuration(operation));
        if (visible.length) {
          const first=visible[0], point=local(first.left,first.top+2);
          attentionMarker.style.width=`${first.width}px`; attentionMarker.style.height=`${Math.max(18,first.height-4)}px`;
          attentionAnimation=attentionMarker.animate([{transform:`${transform(point)} scaleX(0)`,opacity:.2},{transform:`${transform(point)} scaleX(1)`,opacity:.55}],{duration,easing:'cubic-bezier(.18,.7,.25,1)',fill:'forwards'});
          for (const line of visible.slice(1)) {
            const at=local(line.left,line.top+2), trail=doc.createElement('span'); trail.className='au-operation-read-trail'; trail.dataset.auReadTrail=operation.id; trail.setAttribute('aria-hidden','true'); trail.style.width=`${line.width}px`; trail.style.height=`${Math.max(18,line.height-4)}px`; canvas.appendChild(trail);
            stageReadAnimations.push(trail.animate([{transform:`${transform(at)} scaleX(0)`,opacity:.2},{transform:`${transform(at)} scaleX(1)`,opacity:.55}],{duration,easing:'cubic-bezier(.18,.7,.25,1)',fill:'forwards'}));
          }
          attentionAnimation.onfinish=() => { if (operationTrace?.current !== operation || !mark.isConnected || doc.hidden || inspectionHold) { complete(); return; } attentionMarker.dataset.auReadPhase='locked'; mark.dataset.auPhraseLocked=operation.id; attentionMarker.style.opacity='0'; attentionAnimation.cancel(); for (const animation of stageReadAnimations) animation.cancel(); transfer(); };
        } else { attentionMarker.remove(); complete(); }
      } else if (animate && attentionPosition) attentionAnimation = attentionMarker.animate([{transform:transform(attentionPosition),opacity:.2},{transform:transform(origin),opacity:1}],{duration:480,easing:'cubic-bezier(.18,.8,.25,1)',fill:'none'});
      attentionPosition = origin; if (node) node.dataset.auOperationId = operation.id; if (!reading?.active) complete();
    }
    async function operationPresentationGate(session,token,operation) {
      while (operationActive(session,token) && operationTrace?.current === operation && !session.skip && !reduced?.matches) {
        if (!await operationGate(session,token)) return false;
        if (!operationReading(operationTrace)?.active) break;
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
    async function fallbackOperations(session, token, reason) {
      const response = await request(`/claims/${key(session.claimId)}/replay?through_seq=${session.replayHead.revision}`), incoming = readReplay(response,session.claimId,session.replayHead.revision);
      checkedReplayHead(incoming,session);
      if (!await operationGate(session,token)) return;
      current = incoming.state; projection = incoming.projection; cursor = incoming.accepted.cursor; history = incoming.accepted.events; replayRecord = incoming.replay;
      if (operationTrace) { operationTrace.finished = true; operationTrace.current = null; operationTrace.savedFallback = true; }
      stopPresentation(); renderClaim(); primeClaimReads(token); notice(`Live rules-based assessment unavailable: ${reason} Showing the verified saved result; its history remains available.`,true);
    }
    function prepareOperationReads(session, id, token) {
      if (!REFERENCE_DEMO_CASES.some(row => row.claim_id === id)) return null;
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
        if (controller.signal.aborted || disposed || token !== epoch || pendingRoute()) { await response.body?.cancel?.(); return null; }
        // The existing bounded wire buffer is untrusted until head admission.
        // No early result callback can paint or advertise an accepted result.
        return {response,buffer:response.ok ? bufferedOperations(response,controller.signal,result => prepared.resultAvailable?.(result)) : null};
      })();
      prepared.delivery.catch(() => {});
      return prepared;
    }
    async function startOperations(session, token) {
      if (!operationActive(session,token) || session.operationStarted) return;
      const prepared = session.operationPreparation?.claimId === session.claimId && !session.operationPreparation.controller.signal.aborted && session.operationPreparation.recorded === Boolean(session.useRecorded) ? session.operationPreparation : null;
      session.operationPreparation = null;
      session.operationStarted = true; session.operationController = prepared?.controller || new AbortController(); controllers.add(session.operationController);
      const operationController = session.operationController;
      if (!session.operationOpeningAnchor || session.operationOpeningAnchor.state.claim_id !== session.claimId) session.operationOpeningAnchor = {after_operation:0,state:current,projection,events:history,revision:current.revision,state_sha256:current.state_sha256,event_sha256:current.last_event_sha256,anchor:'verified_opening'};
      const previousAttempts = session.previousAttempts || [], previousCurrent = operationTrace?.current, previousSources = operationTrace?.sources, previousDisplaySource = operationTrace?.displaySource;
      operationTrace = {binding:null,recorded:Boolean(session.useRecorded || session.recorded),releasePlan:session.releasePlan,rows:[],bytes:previousAttempts.reduce((sum,attempt) => sum+attempt.bytes,0),sources:new Map(previousSources || []),current:previousCurrent || null,previousCurrent,displaySource:previousDisplaySource,journal:[],pinnedJournal:session.verifiedJournal || [],transportState:null,finished:false,frameHashes:[],visibleResults:new Map(),checkpoints:[session.operationOpeningAnchor],previousAttempts};
      const trace = operationTrace;
      try {
        if ((!session.referenceReady && !await verifyReferenceHead(session,prepared)) || !session.verifiedReplayStart) throw new Error('No current completed reference assessment is available.');
        if (!operationActive(session,token) || operationTrace !== trace) return;
        operationTrace.pinnedJournal = session.verifiedJournal || []; operationTrace.asOf = session.referenceAsOf; operationTrace.plannedProcess = session.plannedProcess; renderClaim();
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
          if (frame.type !== 'result') operationTrace.frameHashes.push(await digest(canonicalJSON(frame)));
          if (frame.type === 'binding') {
            if (operationTrace.binding) throw new Error('The stream repeated its operation binding.');
            operationTrace.binding = checkedOperationBinding(frame,{...session.replayHead,...session.operationBinding},session.verifiedReplayStart); renderClaim();
          } else if (frame.type === 'operation') {
            const operation = await checkedOperation(frame,operationTrace,current);
            if (!await operationGate(session,token)) return;
            applyWorkingOperation(operation,operationTrace,current);
            const graph = operationStageGraph(operationTrace,current), dockingNode = operationNodeId(operation,graph,current,operationTrace);
            const show = operationAttention(operation,operationTrace);
            if (show && ['fact.extract','document.check'].includes(operation.kind)) { operationTrace.dockPhases ||= new Map(); operationTrace.dockPhases.set(operation.id,'read'); }
            if (operation.kind === 'fact.extract' && operation.source && dockingNode) {
              operationTrace.dockedFacts ||= new Map(); operationTrace.dockedFacts.set(operation.object.id,{operation,node:dockingNode,observed:true});
            }
            operationTrace.consumed = operation;
            if (show && !session.skip && !reduced?.matches) {
              operationTrace.current = operation; operationTrace.inkRetired = false;
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
            const stageIdentity = canonicalJSON({graph:current.graph?.graph_sha256,facts:list(current.facts).map(row => row.fact_id),documents:current.evaluation?.documents?.map(row => [row.document_type,row.review_state]),completed:current.evaluation?.nodes?.filter(row => row.execution_state === 'completed').map(row => row.node_id)});
            if (operationTrace.stageStateIdentity !== stageIdentity && !session.skip && !reduced?.matches) { operationTrace.stageStateIdentity = stageIdentity; renderClaim(); }
          } else if (frame.type === 'result') {
            if (!operationTrace.binding || current.revision !== session.replayHead.revision || current.state_sha256 !== session.replayHead.state_sha256 ||
                frame.state_sha256 !== current.state_sha256 || frame.operation_count !== operationTrace.rows.length || frame.operation_chain_sha256 !== operationTrace.rows.at(-1)?.operation_sha256 || frame.exact_output_verified !== true || frame.trace_sha256 !== await digest(canonicalJSON(operationTrace.frameHashes))) throw new Error('The operation result differs from its pinned saved result.');
            operationTrace.finished = true; operationTrace.verifiedResult = true; operationTrace.current = null; selected = preferredNode(current,selected,history); renderClaim();
            const next = demoCases(session.collection)[session.index+1];
            if (next && !session.skip && !reduced?.matches) {
              presentationOpening(session,next.claim_id);
              if (!await operationGate(session,token,1000)) return;
              session.operationStarted = false; session.operationOpeningAnchor = null; session.previousAttempts = []; session.useRecorded = session.operations === 'recorded'; session.recorded = false; session.referenceReady = false; session.verifiedReplayStart = null; session.plannedProcess = null;
              await openPresentationCase(session,true,session.index+1); return;
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
          catch (fallback) { if (operationActive(session,token)) { stopPresentation(); renderClaim(); notice(`Assessment stopped: ${error.message} Saved result unavailable: ${fallback.message}`,true); } }
        }
      } finally { operationController.abort(); controllers.delete(operationController); }
    }
    function presentationFailed(session, message) {
      if (demoSession !== session) return;
      if (doc.hidden) { session.failure = message; return; }
      stopPresentation(); renderClaim(); notice(message,true);
    }
    function pausePresentation() {
      if (!demoSession) return false;
      if (demoSession.mode === 'replay' && !demoSession.replayHead) { inspectionHold = true; return false; }
      pausedPresentation = demoSession.mode === 'operations' ? demoSession : {...demoSession,preparing:null};
      if (demoTimer) root.clearTimeout(demoTimer);
      demoTimer = null; demoSession = null; pausedPresentation.operationWake?.(); replayPrefixes.clear();
      motion?.cancel(); selectionMotion?.cancel(); interactionMotion?.cancel(); cancelStageMotion(); const pane = host.querySelector('.au-operation-passage'); pane?.scrollTo?.({top:pane.scrollTop,behavior:'instant'});
      if (pausedPresentation?.mode === 'operations') host.setAttribute?.('data-au-operation-presentation','paused');
      if (!current && pausedPresentation?.releasePlan) {
        inspectionHold = true;
        const control = host.querySelector('[data-au-demo-stop]'); if (control) { control.removeAttribute('data-au-demo-stop'); control.setAttribute('data-au-demo-resume',''); control.textContent='Resume'; }
      }
      return true;
    }
    function pauseInspection() {
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
      const collection = openingPreferences.collection || (REFERENCE_DEMO_CASES.some(row => row.claim_id === current.claim_id) ? 'reference' : 'legacy');
      const index = demoCases(collection).findIndex(row => row.claim_id === current.claim_id);
      if (index < 0) { notice('This recorded case is outside the selected demonstration collection. Its verified history remains available for inspection.'); return; }
      inspectionHold = false;
      if (replayRecord.through_seq >= replayRecord.current_revision) {
        demoSession = {mode:'replay',collection,index}; await openPresentationCase(demoSession); return;
      }
      demoSession = {mode:'replay',collection,index,claimId:current.claim_id,epoch,replayHead:{claimId:current.claim_id,revision:replayRecord.current_revision,state_sha256:replayRecord.current_state_sha256,event_sha256:replayRecord.current_event_sha256},displayedAt:Date.now(),motionDuration:0};
      openingPreferences = {...openingPreferences,demo:true};
      renderClaim(); await startReplay(demoSession,epoch);
    }
    async function startReplay(session, token) {
      if (!replayActive(session,token) || doc.hidden || session.preparing) return;
      if (session.failure) { presentationFailed(session,session.failure); return; }
      if (inspectionHold) { pausePresentation(); renderClaim(); return; }
      if (dialog.open || recordDialog.open) return;
      if (session.collection !== 'legacy' && !session.referenceReady) {
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
      if (index >= demoCases(session.collection).length) { stopPresentation(); detail = 'step'; selected = preferredNode(current,selected,history); evidenceContext = evidenceSelection(current,selected,evidenceContext); notice('Recorded playback finished.'); renderClaim(); return; }
      const id = demoCases(session.collection)[index].claim_id;
      if (['replay','operations'].includes(session.mode) && current && replayRecord && session.claimId === current.claim_id && id !== current.claim_id) {
        const token = epoch, generation = readGeneration, priorId = current.claim_id, priorHash = current.state_sha256;
        session.preparing = token;
        try {
          const opening = await presentationOpening(session,id);
          if (demoSession !== session || disposed || token !== epoch || generation !== readGeneration || pendingRoute() || current?.claim_id !== priorId || current.state_sha256 !== priorHash || inspectionHold || doc.hidden || dialog.open || recordDialog.open) return;
          if (session.collection !== 'legacy' && !opening.referenceReady) {
            const verification = {replayHead:opening.head,replayStart:opening.response.replay_start};
            if (!await verifyReferenceHead(verification)) throw new Error('No completed recorded reference assessment is available.');
            opening.referenceReady = true; opening.verifiedReplayStart = verification.verifiedReplayStart;
            opening.referenceReady = true;
            if (demoSession !== session || disposed || token !== epoch || generation !== readGeneration || pendingRoute() || current?.claim_id !== priorId || current.state_sha256 !== priorHash || inspectionHold || doc.hidden || dialog.open || recordDialog.open) return;
          }
          session.verifiedOpening = opening;
          const remaining = Math.max(0,(session.mode === 'operations' ? 1000 : 4000) - (Date.now() - session.displayedAt));
          if (remaining) { demoTimer = root.setTimeout(() => { demoTimer = null; openPresentationCase(session,writeHistory,index); },remaining); return; }
        } catch (error) {
          if (demoSession === session && token === epoch && !disposed && !pendingRoute()) presentationFailed(session,`Next case ${featuredCase(id)?.label || id} is unavailable: ${error.message} The last verified case remains visible.`);
          return;
        }
        finally { if (session.preparing === token) session.preparing = null; }
      }
      session.index = index; session.claimId = id; session.startAttempted = false;
      await openClaim(id,writeHistory,{mode:session.mode === 'operations' ? 'replay' : session.mode,collection:session.collection || 'reference',operations:session.operations,through:0,detail:'step',demo:true});
      if (demoSession !== session || !current || disposed || pendingRoute()) return;
      if (['replay','operations'].includes(session.mode)) {
        if (!replayRecord.current_revision) { stopPresentation(); renderClaim(); notice('This original case has no recorded execution to replay. Its original sources remain available.'); return; }
      } else { resumeLivePresentation(); advanceLivePresentation(); }
    }
    function presentationOpening(session,id) {
      const token = epoch, generation = readGeneration, identity = `opening:${id}:0`;
      if (replayPrefixes.has(identity)) return replayPrefixes.get(identity);
      const promise = (async () => {
        const response = await request(`/claims/${key(id)}/replay?through_seq=0`), incoming = readReplay(response,id,0);
        const head = {claimId:id,revision:incoming.replay.current_revision,state_sha256:incoming.replay.current_state_sha256,event_sha256:incoming.replay.current_event_sha256};
        if (!head.revision) throw new Error('No recorded execution is available for this original case.');
        const verification = {replayHead:head,replayStart:response.replay_start};
        const referenceReady = session.collection !== 'legacy' && !doc.hidden && await verifyReferenceHead(verification);
        if (session.collection !== 'legacy' && !doc.hidden && !referenceReady) throw new Error('No completed recorded reference assessment is available.');
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
      if (!descriptor || disposed || doc.hidden || view !== 'work') return false;
      let verification;
      try {
        await new Promise(resolve => root.setTimeout(resolve,0));
        if (disposed || doc.hidden || view !== 'work') return false;
        const url = new URL(descriptor.url,root.location?.href || 'http://localhost/');
        if (url.origin !== new URL(root.location?.href || 'http://localhost/').origin || url.username || url.password || !Number.isSafeInteger(descriptor.bytes) || descriptor.bytes < 1 || descriptor.bytes > RECORDED_PACKET_BYTES) return false;
        packetLoadController = new AbortController();
        const response = await fetcher(url.href,{method:'GET',cache:'force-cache',credentials:'same-origin',redirect:'error',signal:packetLoadController.signal});
        if (!response.ok || !response.body?.getReader) return false;
        const reader = response.body.getReader(), chunks = []; let length = 0;
        const cancel = () => { reader.cancel().catch(() => {}); }; packetLoadController.signal.addEventListener('abort',cancel,{once:true});
        try { while (!packetLoadController.signal.aborted) { const chunk = await reader.read(); if (chunk.done) break; length += chunk.value.byteLength; if (length > descriptor.bytes) throw new Error('Recorded packet asset exceeds its bound.'); chunks.push(chunk.value); } }
        finally { packetLoadController.signal.removeEventListener('abort',cancel); await reader.cancel().catch(() => {}); reader.releaseLock?.(); }
        if (disposed || doc.hidden || packetLoadController.signal.aborted || view !== 'work') return false;
        const bytes = new Uint8Array(length); let offset = 0; for (const chunk of chunks) { bytes.set(chunk,offset); offset+=chunk.byteLength; }
        if (length !== descriptor.bytes) throw new Error('Recorded packet acquisition is incomplete.');
        verification = {controller:packetLoadController,promise:checkedRecordedPacket(bytes,descriptor,options.allowNativeRecordedPacket === true)}; packetVerification=verification;
        const packet = await verification.promise;
        if (disposed || doc.hidden || packetLoadController.signal.aborted || view !== 'work' && !(view === 'claim' && (demoSession || pausedPresentation)?.mode === 'operations')) return false;
        recordedPacket = packet; return true;
      } catch (_) { return false; }
      finally { if (packetVerification === verification) packetVerification=null; }
    }
    function operationRequest(prepared, path) {
      const identity = `${readGeneration}:${path}`, prior = readOwners.get(identity), promise = request(path), owner = readOwners.get(identity);
      if (owner && owner !== prior) prepared.readControllers.add(owner.controller);
      return promise;
    }
    function cancelPreparedOperationReads(prepared) {
      prepared.controller.abort(); for (const controller of prepared.readControllers) controller.abort();
    }
    async function chooseRecordedOpening(packet, session, id, token) {
      const prepared = session.operationPreparation, choice = new AbortController(); session.operationChoiceController = choice;
      const active = () => !disposed && token === epoch && !pendingRoute() && openingId === id && !choice.signal.aborted;
      const openingResult = (response, head, verification) => ({claimId:id,generation:readGeneration,response,head,referenceReady:true,verifiedHeadState:verification.verifiedHeadState,verifiedReplayStart:verification.verifiedReplayStart,verifiedJournal:verification.verifiedJournal,referenceAsOf:verification.referenceAsOf,operationBinding:verification.operationBinding,plannedProcess:verification.plannedProcess});
      let packetOpening = null;
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
      })(); packetCandidate.catch(() => {});
      if (!prepared) {
        let timer;
        await Promise.race([packetCandidate.catch(() => {}),new Promise(resolve => { timer=root.setTimeout(resolve,500); })]); root.clearTimeout(timer);
        if (!active()) throw new Error('The selected opening changed.');
        if (!packetOpening) { choice.abort(); return null; }
        return selectRecorded();
      }
      const liveOpening = operationRequest(prepared,`/claims/${key(id)}/replay?through_seq=0`);
      const liveCandidate = (async () => {
        const response = await liveOpening, incoming = readReplay(response,id,0), head = {claimId:id,revision:incoming.replay.current_revision,state_sha256:incoming.replay.current_state_sha256,event_sha256:incoming.replay.current_event_sha256};
        const verification = {replayHead:head,replayStart:incoming.replay.replay_start,operationOpeningAnchor:{state:incoming.state}};
        if (!await verifyReferenceHead(verification,prepared) || !verification.verifiedReplayStart) throw new Error('The live reference opening is incomplete.');
        const delivery = await prepared.delivery, first = await delivery?.buffer?.first;
        if (!first) throw new Error('The live operation binding is unavailable.');
        checkedOperationBinding(first,{...head,...verification.operationBinding},verification.verifiedReplayStart);
        if (disposed || token !== epoch || pendingRoute() || openingId !== id || prepared.controller.signal.aborted) throw new Error('The selected opening changed.');
        return openingResult(response,head,verification);
      })(); liveCandidate.catch(() => {});
      let timer;
      const winner = await Promise.race([liveCandidate.catch(() => new Promise(() => {})),new Promise(resolve => { timer=root.setTimeout(() => resolve(null),500); })]);
      root.clearTimeout(timer);
      if (!active()) throw new Error('The selected opening changed.');
      if (winner) { choice.abort(); return winner; }
      if (!packetOpening) {
        choice.abort(); const response = await liveOpening, incoming = readReplay(response,id,0);
        return {claimId:id,generation:readGeneration,response,head:{claimId:id,revision:incoming.replay.current_revision,state_sha256:incoming.replay.current_state_sha256,event_sha256:incoming.replay.current_event_sha256},referenceReady:false};
      }
      return selectRecorded();
      function selectRecorded() {
        if (prepared) cancelPreparedOperationReads(prepared);
        session.operations = 'recorded'; session.useRecorded = true; session.recorded = true; openingPreferences.operations = 'recorded';
        if (operationTrace) operationTrace.recorded = true;
        const controller = new AbortController(); controllers.add(controller); controller.signal.addEventListener('abort',() => controllers.delete(controller),{once:true}); session.operationController = controller;
        const response = new root.Response(packetOpening.bytes,{headers:{'Content-Type':'application/x-ndjson'}});
        session.operationPreparation = {claimId:id,controller,token,recorded:true,readControllers:new Set(),delivery:Promise.resolve({response,buffer:bufferedOperations(response,controller.signal)})};
        const fragment = claimFragment(id,{...openingPreferences,operations:'recorded'});
        if (root.history?.replaceState) { root.history.replaceState(null,'',root.location.pathname+root.location.search+fragment); routedFragment=fragment; }
        const label = host.querySelector('.au-reference-mode'); if (label) label.textContent='Recorded replay · Synthetic sources · No external action';
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
        incoming = readReplay(await request(`/claims/${key(head.claimId)}/replay?through_seq=${head.revision}`),head.claimId,head.revision);
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
        const next = demoCases(session.collection)[session.index+1];
        if (next) presentationOpening(session,next.claim_id);
        const remaining = Math.max(0,(session.mode === 'operations' ? 1000 : 4000) - (Date.now() - session.displayedAt));
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
      if (!session || session.mode !== 'live' || session.epoch !== epoch || disposed || pendingRoute() || doc.hidden || dialog.open || recordDialog.open || view !== 'claim' || presentationMode !== 'live' || !openingPreferences.demo || !current || !freshClaim || current.claim_id !== session.claimId || demoCases(session.collection)[session.index]?.claim_id !== session.claimId || current.revision !== 0 || busy || pendingStart || session.startAttempted || !canStartHere()) return;
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
      if (demoSession !== session || disposed || token !== epoch || pendingRoute() || session.epoch !== token || view !== 'claim' || presentationMode !== 'live' || current?.claim_id !== id || session.claimId !== id || demoCases(session.collection)[session.index]?.claim_id !== id || busy || pendingStart || active(current.status)) return;
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
    async function showWork(writeHistory = true) {
      stopPresentation(); leaveView(); route(collectionFragment(),writeHistory);
      epoch++; const token = epoch; cancelPoll(); setView('work'); nav('work'); current = null; notice('');
      host.innerHTML = collectionMarkup(claims,collection); interact(host);
      if (collection.scrollTop !== undefined) { host.scrollTop = collection.scrollTop; const main = container.querySelector('.au-main'); if (main) { main.scrollTop = collection.mainTop; main.scrollLeft = collection.mainLeft; } root.scrollTo?.({left:collection.scrollX,top:collection.scrollY,behavior:'instant'}); }
      if (!claimsLoaded) { const output = host.querySelector('[data-au-claims]'); if (output) output.innerHTML = ''; }
      const results = await Promise.allSettled([serviceStatus(token),loadClaims(token)]);
      if (!disposed && token === epoch) for (const result of results) if (result.status === 'rejected') notice(result.reason.message,true);
    }
    async function showIntake(writeHistory = true) {
      if (publicReadOnly) return showWork(writeHistory);
      if (view === 'intake' && host.querySelector('[data-au-intake]')) { route('#autonomous/new',writeHistory); return; }
      stopPresentation(); leaveView(); route('#autonomous/new',writeHistory);
      epoch++; const token = epoch; cancelPoll(); setView('intake'); nav('intake'); current = null; notice('');
      host.innerHTML = `<div class="au-intake-layout au-identity-intake"><section><p class="au-eyebrow">New claim</p><h1 class="au-page-heading" tabindex="-1">Start with the source.</h1><p class="au-lead">Add the original message and files. Evidence establishes the facts, process and document requirements.</p><p class="au-meta" data-au-service>Checking service availability…</p><form class="au-intake" data-au-intake><div class="au-examples" data-au-examples hidden><label for="auExample">Try a fictional claim</label><select id="auExample" data-au-example><option value="">Choose a fictional example</option></select></div><label for="auTitle">Claim title</label><input id="auTitle" name="title" required maxlength="300" autocomplete="off" placeholder="A short name for this claim"><label for="auMessage">Incoming message</label><textarea id="auMessage" name="message" required maxlength="100000" rows="7" placeholder="Paste the original message"></textarea><label class="au-upload" for="auFiles">Supporting files <span>Optional · original files stay available for inspection</span></label><input id="auFiles" name="files" type="file" multiple><div class="au-intake-controls"><button class="au-primary" type="submit">Start autonomous work <span aria-hidden="true">↗</span></button><button type="button" class="au-secondary" data-au-nav="work">Cancel</button></div><p class="au-form-status" role="status"></p></form></section></div>`;
      if (intakeForm) host.querySelector('[data-au-intake]')?.replaceWith?.(intakeForm);
      else intakeForm = host.querySelector('[data-au-intake]');
      if (pendingIntake && intakeForm) {
        intakeForm.elements.title.value = pendingIntake.body.title; intakeForm.elements.message.value = pendingIntake.body.message;
        lockForm(intakeForm,true,true); intakeForm.querySelector('.au-form-status').textContent = 'The prior response was not confirmed. Retry sends the same saved intake request.';
      } else if (!busy) idleIntakeSubmit(intakeForm);
      loadExamples(token); interact(host); focusTitle();
      try { await serviceStatus(token,true); } catch (error) { if (!disposed && token === epoch) notice(error.message,true); }
    }
    async function loadExamples(token) {
      const meta = doc.querySelector?.('meta[name="casepath-autonomous-demo-packets"]')?.content;
      if (!meta || !root.location) return;
      const controller = new AbortController(); controllers.add(controller);
      const timeout = root.setTimeout(() => controller.abort(), 15000);
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
      if (select.matches?.('[data-au-claim-filter]') && view === 'work') { collection.filter = select.value; refreshCollection(); rememberCollectionRoute(); return; }
      if (!select.matches?.('[data-au-example]') || view !== 'intake' || busy || pendingIntake || select.disabled || !/^\d+$/.test(select.value)) return;
      const packet = examples?.[Number(select.value)], form = host.querySelector('[data-au-intake]');
      if (!packet || !form) return;
      try { prefillExample(form,packet); form.querySelector('.au-form-status').textContent = 'Fictional example loaded. Start autonomous work when ready.'; }
      catch (error) { form.querySelector('.au-form-status').textContent = error.message; }
    }
    function synchronizeKnowledgeRead(value = host.getAttribute?.('data-au-read-state') || 'verified') {
      host.setAttribute?.('data-au-read-state',value);
      const label = host.querySelector('[data-au-knowledge-read-label]');
      if (label) label.textContent = value === 'verified' ? '' : value === 'failed' ? 'Saved copy · refresh failed' : 'Saved copy · refreshing';
    }
    function renderKnowledge(data, pin, initial = false) {
      const open = new Set([...host.querySelectorAll('details[open][data-au-disclosure]')].map(element => element.dataset.auDisclosure));
      const previous = host.querySelector('[data-au-knowledge-identity]');
      if (initial || !previous || renderedKnowledge !== canonicalJSON([data,pin,knowledgeFacet])) {
        host.innerHTML = knowledgeMarkup(data,claims,pin,knowledgeFacet);
        renderedKnowledge = canonicalJSON([data,pin,knowledgeFacet]); knowledgePin = pin;
        for (const disclosure of host.querySelectorAll('[data-au-disclosure]')) disclosure.open = open.has(disclosure.dataset.auDisclosure);
        drawEdges(); interact(host);
        if (initial) focusTitle();
      }
      synchronizeKnowledgeRead();
      host.querySelectorAll('[data-pinned]').forEach(row => row.removeAttribute('data-pinned'));
      if (!pin) return true;
      const version = list(data.versions).find(item => String(item.knowledge_id || item.version_id) === String(pin.knowledge_id) && String(item.version || item.version_id) === String(pin.version) && (!pin.knowledge_sha256 || item.knowledge_sha256 === pin.knowledge_sha256) && (!pin.definition_sha256 || (item.qualification?.definition_sha256 || item.definition_sha256) === pin.definition_sha256));
      if (!version) { notice('The exact reused knowledge version is not available in this record.',true); return false; }
      const row = [...host.querySelectorAll('[data-au-knowledge-identity]')].find(element => element.dataset.auKnowledgeIdentity === `${pin.knowledge_id}:${pin.version}`);
      if (row) { let parent = row.parentElement; while (parent && parent !== host) { if (parent.tagName === 'DETAILS') parent.open = true; parent = parent.parentElement; } row.setAttribute('data-pinned','true'); row.setAttribute('tabindex','-1'); row.focus({preventScroll:true}); row.scrollIntoView?.({block:'nearest',behavior:'instant'}); drawEdges(); }
      return true;
    }
    async function showKnowledge(writeHistory = true, pin = null) {
      knowledgeFacet = 'process'; knowledgePin = pin;
      stopPresentation(); leaveView();
      const fragment = pin ? `#autonomous/knowledge?knowledge=${key(pin.knowledge_id)}&version=${key(pin.version)}&sha256=${key(pin.knowledge_sha256 || '')}${pin.definition_sha256 ? `&definition=${key(pin.definition_sha256)}` : ''}` : '#autonomous/knowledge';
      route(fragment,writeHistory);
      epoch++; const token = epoch, read = ++knowledgeRead, generation = readGeneration;
      let awaitingFresh = true, freshReadFailed = false;
      cancelPoll(); setView('knowledge'); nav('knowledge'); current = null;
      if (knowledgeCache) { renderKnowledge(knowledgeCache.value,pin,true); synchronizeKnowledgeRead('refreshing'); notice(''); }
      else { host.innerHTML = readSkeletonMarkup('knowledge'); interact(host); focusTitle(); notice(''); }
      sessionRestore?.then(() => {
        if (!disposed && (awaitingFresh || freshReadFailed) && token === epoch && read === knowledgeRead && generation === readGeneration && !pendingRoute() && view === 'knowledge' && knowledgeCache && !host.querySelector('[data-au-knowledge-identity]')) {
          renderKnowledge(knowledgeCache.value,pin,true); synchronizeKnowledgeRead(freshReadFailed ? 'failed' : 'refreshing');
        }
      });
      // Claim titles enrich relationships independently; they never delay the
      // knowledge response or authorize its qualification.
      if (!claimsLoaded) loadClaims(token).catch(error => { if (!disposed && token === epoch) notice(`Case names unavailable: ${error.message}`,true); });
      try {
        const data = await request('/knowledge');
        if (disposed || token !== epoch || read !== knowledgeRead || generation !== readGeneration || pendingRoute()) return;
        readKnowledge(data);
        knowledgeCache = JSON.stringify(data).length * 2 <= 8 * 1024 * 1024 ? {value:data} : null;
        savedKnowledge = {at:Date.now(),value:data}; persistReadCache();
        awaitingFresh = false;
        synchronizeKnowledgeRead('verified');
        notice(''); renderKnowledge(data,pin,!host.querySelector('[data-au-knowledge-identity]'));
      } catch (error) { awaitingFresh = false; freshReadFailed = true; if (!disposed && token === epoch && read === knowledgeRead) { synchronizeKnowledgeRead('failed'); notice(knowledgeCache ? `Refresh failed: ${error.message} Recorded knowledge remains visible.` : error.message,true); } }
    }
    function idleIntakeSubmit(form) {
      const submit = form?.querySelector('button[type="submit"]');
      if (!submit) return;
      if (publicReadOnly) { submit.disabled = true; submit.textContent = 'Public workspace · read-only'; return; }
      submit.textContent = status?.enabled === true && (status.provider_ready === false || status.limits?.autonomous_can_start === false) ? 'Save claim' : 'Start autonomous work ↗';
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
    async function openSource(id, citation, trigger) {
      if (!current) return;
      const saved = operationPeek?.state || current, token = epoch, sourceToken = ++sourceEpoch, descriptor = list(saved.source_descriptors).find(source => source.artifact_id === id);
      if (!descriptor) { notice('This source is not part of the saved claim.',true); return; }
      dialogReturn = {element:trigger,token:focusToken(trigger)}; container.querySelector('#auSourceTitle').textContent = descriptor.file_name || 'Original source';
      const sourceEyebrow = dialog.querySelector?.('.au-eyebrow'); if (sourceEyebrow) sourceEyebrow.textContent = sourceKind(saved,descriptor,projection);
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
          else if (preview.blob) { nativeViewable = true; nativeMarkup = native === 'application/pdf' ? `<iframe class="au-native-document" src="${h(preview.blob)}" title="${h(descriptor.file_name || 'Original PDF')}"></iframe>` : `<img class="au-native-image" src="${h(preview.blob)}" alt="Original file: ${h(descriptor.file_name)}">`; }
        }
        if (disposed || token !== epoch || sourceToken !== sourceEpoch || !dialog.open) return;
        const unassessed = assessmentFreshness(current).sources.some(source => source.artifact_id === descriptor.artifact_id);
        const source = checked.source, unsupported = source.extraction === 'unsupported_metadata';
        const extraction = unsupported ? 'Received · interpretation unsupported' : source.complete ? 'Extracted text' : 'Extraction incomplete';
        const identity = `<details class="au-source-identity"><summary>Source identity and extraction</summary><p class="au-meta">${acquired ? 'Source text verified' : 'Read-only preview verified'}${checked.span ? ' · exact cited span verified' : ''} · ${h(extraction)}</p>${!acquired ? '<p class="au-meta">Preview does not admit evidence or establish understanding or sufficiency.</p>' : ''}<dl class="au-chain"><div><dt>Original filename</dt><dd>${h(descriptor.file_name)}</dd></div><div><dt>Media type</dt><dd>${h(descriptor.media_type)}</dd></div><div><dt>Original bytes · SHA-256</dt><dd class="au-hash">${h(descriptor.sha256)}</dd></div><div><dt>Extracted text · SHA-256</dt><dd class="au-hash">${h(source.text_sha256)}</dd></div>${!acquired ? `<div><dt>Preview · SHA-256</dt><dd class="au-hash">${h(source.preview_sha256)}</dd></div>` : ''}</dl><pre class="au-record-body">${h(JSON.stringify({descriptor,preview_only:source.preview_only,evidence_admitted:source.evidence_admitted,receipt_sha256:source.receipt_sha256,preview_sha256:source.preview_sha256,extraction:source.extraction,complete:source.complete,coverage:source.coverage,reason:source.reason,limitation:source.limitation},null,2))}</pre>${!source.text ? '<p class="au-meta">No readable text was extracted.</p>' : ''}</details>`;
        const unsupportedImage = unsupported && native?.startsWith('image/');
        body.innerHTML = (unassessed ? '<p class="au-assessment-freshness" data-au-source-freshness="unassessed"><strong>New source · awaiting assessment</strong></p>' : '') + (unsupportedImage ? `<div class="au-source-meta"><a href="${h(url)}" download="${h(descriptor.file_name || 'source')}">Download original</a></div><p class="au-source-capability">${nativeViewable ? 'Original image viewable.' : 'Original image preview unavailable.'} The agent cannot interpret this image.</p>${nativeMarkup}${identity}` : `<div class="au-source-meta"><span>${acquired ? 'Source text verified' : 'Read-only preview verified'}${checked.span ? ' · exact cited span verified' : ''}</span><span>${h(extraction)}</span><a href="${h(url)}" download="${h(descriptor.file_name || 'source')}">Download original</a></div>${nativeMarkup}${!acquired ? '<p class="au-meta">Preview does not admit evidence or establish understanding or sufficiency.</p>' : ''}${!source.complete ? `<p class="au-notice">${h(source.reason || source.limitation || words(source.coverage?.limitation) || 'This source does not have a complete text extraction.')}</p>` : ''}${source.text ? `<pre class="au-source-body">${checked.span ? `${h(checked.span.before)}<mark tabindex="-1">${h(checked.span.quote)}</mark>${h(checked.span.after)}` : h(source.text)}</pre>` : '<p class="au-meta">No readable text was extracted.</p>'}${identity}`);
        interact(body); body.querySelector('mark')?.scrollIntoView({block:'center',behavior:'instant'});
      } catch (error) { if (!disposed && token === epoch && sourceToken === sourceEpoch && dialog.open) body.innerHTML = `<div class="au-source-meta"><a href="${h(url)}" download="${h(descriptor.file_name || 'source')}">Download original</a></div>${nativeMarkup}<p class="au-error" role="alert">${h(error.message)}</p>`; }
    }
    function synchronizeRecord(opening = false) {
      if (!recordSelection || !opening && !recordDialog.open) return;
      const {kind,id} = recordSelection, body = recordDialog.querySelector('[data-au-record-content]');
      if (kind === 'demo') {
        const roster = (rows,collection) => DOMAINS.map(domain => `<section><h3>${h(domain.label)}</h3>${rows.filter(row => row.domain === domain.id).map(row => `<button type="button" class="au-demo-case-open" data-au-demo-case="${h(row.claim_id)}" data-au-demo-collection="${collection}">${h(row.label)}</button>${collection === 'reference' ? `<button type="button" class="au-link" data-au-demo-case="${h(row.claim_id)}" data-au-demo-collection="reference" data-au-demo-saved="true">Saved history</button>` : ''}`).join('')}</section>`).join('');
        body.innerHTML = `<div class="au-demo-picker"><h2>Demonstration cases</h2><p class="au-meta">Live rules-based assessments recompute saved synthetic source packets. Saved histories retain their original execution mode.</p>${roster(REFERENCE_DEMO_CASES,'reference')}<details data-au-disclosure="earlier-recordings"><summary>Earlier recordings</summary><p class="au-meta">Original recorded histories retain their execution modes and receipts.</p>${roster(DEMO_CASES,'legacy')}</details></div>`;
        return;
      }
      const record = ['operation','operation-attempt'].includes(kind) ? operationRecord(operationPeek?.trace || operationTrace,kind,id) : contextualRecord(operationPeek?.state || current,operationPeek?.projection || projection,operationPeek?.events || history,kind,id,knowledgeCache?.value || {},replayRecord);
      if (!body.querySelector('pre')) body.innerHTML = '<p class="au-record-context"></p><pre class="au-record-body"></pre>';
      const context = body.querySelector('.au-record-context'); if (context) { const checkpoint = kind === 'operation' && [...list(operationTrace?.checkpoints)].reverse().find(row => row.after_operation < record?.seq); context.textContent = kind === 'operation' ? `History · operation ${record?.seq || ''}${checkpoint ? ` · accepted revision ${checkpoint.revision} at this point` : ''}` : ''; }
      const pre = body.querySelector('pre'); pre.dataset.auRecordKind = kind; pre.dataset.auRecordId = id; pre.textContent = JSON.stringify(record ?? null,null,2);
    }
    function openRecord(target) {
      pauseInspection(); motion?.cancel(); selectionMotion?.cancel(); interactionMotion?.cancel();
      recordSelection = {kind:target.dataset.auInspect,id:target.dataset.auRecordId || ''};
      recordReturn = {element:target,token:focusToken(target)};
      recordDialog.querySelector('#auRecordTitle').textContent = recordSelection.kind === 'demo' ? 'Recorded investigations' : target.textContent.trim() || 'Details';
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
      const returning = recordReturn; recordReturn = null; restoreRecordFocus(returning);
    }
    function click(event) {
      const target = event.target.closest('button,[data-au-nav]'); if (!target || !container.contains(target)) return;
      if (target.hasAttribute('data-au-close-record')) closeRecord();
      else if (target.hasAttribute('data-au-return-case')) { if (!busy && lastCaseContext) openClaim(lastCaseContext.claim_id,true,{...lastCaseContext,detail:target.dataset.auReturnCase}); }
      else if (target.hasAttribute('data-au-knowledge-facet')) { if (view === 'knowledge' && ['process','facts','documents','exceptions','changes'].includes(target.dataset.auKnowledgeFacet) && knowledgeCache) { knowledgeFacet = target.dataset.auKnowledgeFacet; renderKnowledge(knowledgeCache.value,knowledgePin); host.querySelector(`[data-au-knowledge-facet="${knowledgeFacet}"]`)?.focus({preventScroll:true}); } }
      else if (target.hasAttribute('data-au-inspect')) openRecord(target);
      else if (target.hasAttribute('data-au-demo-case')) { const id = target.dataset.auDemoCase; recordReturn = null; recordDialog.close(); stopPresentation(); demoMode = 'replay'; const collection = target.dataset.auDemoCollection === 'legacy' ? 'legacy' : 'reference', index = demoCases(collection).findIndex(row => row.claim_id === id); if (index >= 0) { const operations=openingPreferences.operations || operationRoutePreference(root.location?.hash,root.location?.search); demoSession = {mode:collection === 'legacy' || target.dataset.auDemoSaved === 'true' ? 'replay' : 'operations',collection,index,operations,useRecorded:operations === 'recorded'}; openPresentationCase(demoSession); } }
      else if (target.hasAttribute('data-au-filter')) { collection.filter = target.dataset.auFilter; collection.page = 1; refreshCollection(); rememberCollectionRoute(true); for (const control of host.querySelectorAll('[data-au-filter]')) control.setAttribute('aria-pressed',String(control.dataset.auFilter === collection.filter)); }
      else if (target.hasAttribute('data-au-page')) { if (view === 'work' && !target.disabled) { collection.page = Number(target.dataset.auPage); refreshCollection(); rememberCollectionRoute(true); host.querySelector('[data-au-claims]')?.scrollIntoView?.({block:'start',behavior:'instant'}); } }
      else if (target.hasAttribute('data-au-nav')) { if (busy) return; target.dataset.auNav === 'knowledge' ? showKnowledge() : target.dataset.auNav === 'intake' ? showIntake() : target.dataset.auNav === 'demonstration' ? showDemonstration() : showWork(); }
      else if (target.hasAttribute('data-au-claim')) { if (!busy) openClaim(target.dataset.auClaim); }
      else if (target.hasAttribute('data-au-demo-mode')) { demoMode = !publicReadOnly && target.dataset.auDemoMode === 'live' ? 'live' : 'replay'; refreshDemonstration(); route(`#autonomous/demonstration?mode=${demoMode}`); }
      else if (target.hasAttribute('data-au-demo-play')) beginPresentation();
      else if (target.hasAttribute('data-au-inspection-clear')) { operationPeek = null; host.removeAttribute?.('data-au-inspection-operation'); renderClaim(); }
      else if (target.hasAttribute('data-au-operation-skip')) skipOperations();
      else if (target.hasAttribute('data-au-demo-stop')) { pausePresentation(); renderClaim(); }
      else if (target.hasAttribute('data-au-demo-resume')) resumePresentation();
      else if (target.hasAttribute('data-au-start')) startOriginal(target);
      else if (target.hasAttribute('data-au-refresh-claim')) { if (!busy && current) { pauseInspection(); if (presentationMode === 'replay') openClaim(current.claim_id,true,{mode:'replay',through:replayRecord.through_seq,detail,node:selected,...evidenceContext}); else { freshClaim = false; synchronizeAuthority('refreshing'); disconnected = true; cancelPoll(); serviceStatus(epoch,true).catch(() => {}); poll(); } } }
      else if (target.hasAttribute('data-au-collection-scope')) { if (busy) return; collection.scope = target.dataset.auCollectionScope === 'added' ? 'added' : 'originals'; collection.domain = 'all'; collection.search = ''; collection.filter = 'all'; collection.page = 1; showWork(); }
      else if (target.hasAttribute('data-au-domain')) { collection.domain = target.dataset.auDomain; collection.page = 1; refreshCollection(); rememberCollectionRoute(true); }
      else if (target.hasAttribute('data-au-pause')) controlWork(target,'pause');
      else if (target.hasAttribute('data-au-resume')) controlWork(target,'resume');
      else if (target.hasAttribute('data-au-refresh-claims')) { const token = epoch; loadClaims(token,true).catch(error => { if (!disposed && token === epoch) notice(error.message,true); }); }
      else if (target.hasAttribute('data-au-knowledge')) { if (!busy) showKnowledge(true,{knowledge_id:target.dataset.auKnowledge,version:target.dataset.auVersion,knowledge_sha256:target.dataset.auKnowledgeSha,definition_sha256:target.dataset.auDefinitionSha}); }
      else if (target.hasAttribute('data-au-add-files')) { pauseInspection(); setDetail('sources',true); }
      else if (target.hasAttribute('data-au-expand-process')) { pauseInspection(); setGraphExpanded(target.getAttribute('aria-expanded') !== 'true'); drawEdges(); }
      else if (target.hasAttribute('data-au-detail')) { pauseInspection(); setDetail(target.dataset.auDetail); }
      else if (target.hasAttribute('data-au-back-process')) {
        const node = [...host.querySelectorAll('[data-au-node]')].find(element => element.dataset.auNode === selected);
        node?.focus({preventScroll:true}); revealGraphNode(node); drawEdges();
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
        selected = node.node_id; evidenceContext = {}; setDetail('step',false,false); renderSelection(true); rememberSelectionRoute();
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
        const changed=selected !== id; selected=id; if (operationPeek) operationPeek.node=id;
        if (target.dataset.auSelectDocument) {
          const relations=evidenceRelationships(current,id), requirement=relations.documents.find(item => item.document_type === target.dataset.auSelectDocument && requirementIdentity(item) === target.dataset.auSelectObligation);
          if (requirement) evidenceContext={document:requirement.document_type,obligation:requirementIdentity(requirement),fact:list(requirement.required_fact_ids).includes(target.dataset.auSelectFact) ? target.dataset.auSelectFact : undefined};
          else evidenceContext={};
        } else if (changed) evidenceContext={};
        setDetail('step',false,false); renderSelection(changed); rememberSelectionRoute();
        const node=[...host.querySelectorAll('[data-au-node]')].find(element => element.dataset.auNode === selected);
        node?.focus({preventScroll:true});
      } else if (target.hasAttribute('data-au-source')) {
        let citation; try { citation = target.dataset.auCitation ? JSON.parse(target.dataset.auCitation) : null; } catch (_) { notice('The source reference is invalid.',true); return; }
        openSource(target.dataset.auSource,citation,target);
      } else if (target.hasAttribute('data-au-close')) closeSource();
    }
    function input(event) {
      if (event.isTrusted && event.target.hasAttribute?.('data-au-operation-scrub') && operationTrace) {
        pauseInspection(); operationPeek = operationInspection(operationTrace,Math.min(Number(event.target.value),operationTrace.rows.length-1));
        if (operationPeek) { host.setAttribute('data-au-inspection-operation',operationPeek.trace.current.id); renderClaim(); }
        return;
      }
      if (view === 'work' && event.target.matches?.('[data-au-claim-search]')) { collection.search = event.target.value; collection.page = 1; refreshCollection(); rememberCollectionRoute(); }
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
      if (doc.hidden && !recordedPacket) packetLoadController?.abort();
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
    function keyboardInput(event) { if (event.isTrusted && (event.key === 'Tab' || event.key?.startsWith('Arrow'))) { keyboard=true;container.setAttribute('data-au-keyboard','true');pauseInspection();motion?.cancel();selectionMotion?.cancel();interactionMotion?.cancel(); } }
    function pointerInput(event) {
      keyboard=false;container.removeAttribute('data-au-keyboard');
      const target = event?.isTrusted && event.target?.closest?.('.au-operation-passage,[data-au-operation-scrub],[data-au-inspect],[data-au-source],[data-au-node],[data-au-select],[data-au-detail],[data-au-fact-select],[data-au-document-select],[data-au-expand-process]');
      if (target && container.contains(target)) pauseInspection();
    }
    function sourceWheel(event) { if (event.isTrusted && event.target?.closest?.('.au-operation-passage')) { pauseInspection(); attentionMarker?.remove?.(); } }
    function motionPreference() { if (reduced?.matches) { skipOperations(); motion?.cancel();selectionMotion?.cancel();interactionMotion?.cancel(); } }
    doc.addEventListener('keydown',keyboardInput);container.addEventListener('pointerdown',pointerInput);reduced?.addEventListener?.('change',motionPreference);
    container.addEventListener('wheel',sourceWheel,{passive:true});
    function geometryEvent(event) { if (event.target?.matches?.('.au-operation-passage')) { if (host.querySelector('.au-operation-stage')) return; if (!doc.hidden && !inspectionHold) { positionOperationAttention(false); drawEdges(); } return; } if (event.type === 'toggle') { drawEdges(); if (event.target?.open) interact(event.target.querySelector(':scope > :not(summary)')); } else if (event.target?.hasAttribute?.('data-au-graph-pan')) drawEdges(); }
    container.addEventListener('scroll',geometryEvent,true);container.addEventListener('toggle',geometryEvent,true);
    doc.fonts?.ready?.then(() => { if (!disposed) drawEdges(); });
    container.addEventListener('click',click); container.addEventListener('pointerover',claimWarmIntent); container.addEventListener('focusin',claimWarmIntent); container.addEventListener('submit',submit); container.addEventListener('change',change); container.addEventListener('input',input); dialog.addEventListener('close',closed); recordDialog.addEventListener('close',closedRecord); doc.addEventListener('visibilitychange',visibility);
    root.addEventListener?.('hashchange',routeChanged); root.addEventListener?.('popstate',routeChanged);
    function resized() {
      if (host.querySelector('.au-operation-stage')) { cancelStageMotion(); drawEdges(); return; }
      const area=host.querySelector('.au-graph-viewport')?.getBoundingClientRect?.();
      if (!host.querySelector('[data-au-forming="true"]') && area && graphViewportWidth !== null && area.width !== graphViewportWidth) revealGraphNode([...host.querySelectorAll('[data-au-node]')].find(element => element.dataset.auNode === selected));
      drawEdges(); positionOperationAttention();
    }
    const resize = root.ResizeObserver ? new root.ResizeObserver(resized) : null; resize?.observe(host); root.addEventListener?.('resize',resized);
    const controller = {openClaim,showWork,showIntake,showKnowledge,showDemonstration,recordedPacketReady:Promise.resolve().then(loadRecordedPacket),refresh:poll,destroy() { if (disposed) return; disposed = true; packetLoadController?.abort(); cancelStageMotion(); epoch++; cancelWarmReads(); storageWrite++; cancelPoll(); stopPresentation(); clearNativeSource(); motion?.cancel(); selectionMotion?.cancel(); interactionMotion?.cancel(); snapshots.clear(); sourcePreviews.clear(); nativeBytes.clear(); replayPrefixes.clear(); inflightReads.clear();root.removeEventListener?.('resize',resized);root.removeEventListener?.('hashchange',routeChanged);root.removeEventListener?.('popstate',routeChanged);doc.removeEventListener('keydown',keyboardInput);container.removeEventListener('pointerdown',pointerInput);container.removeEventListener('wheel',sourceWheel);reduced?.removeEventListener?.('change',motionPreference); for (const controller of controllers) controller.abort(); resize?.disconnect();container.removeEventListener('scroll',geometryEvent,true);container.removeEventListener('toggle',geometryEvent,true); container.removeEventListener('click',click); container.removeEventListener('pointerover',claimWarmIntent); container.removeEventListener('focusin',claimWarmIntent); container.removeEventListener('submit',submit); container.removeEventListener('change',change); container.removeEventListener('input',input); dialog.removeEventListener('close',closed); recordDialog.removeEventListener('close',closedRecord); doc.removeEventListener('visibilitychange',visibility); if (dialog.open) dialog.close(); if (recordDialog.open) recordDialog.close(); mounts.delete(container); if (activeMount === controller) activeMount = null; container.innerHTML = ''; }};
    mounts.set(container,controller); activeMount = controller;
    sessionRestore = restoreReadCache();
    routeChanged();
    return controller;
  }
  function destroy(container) { (container ? mounts.get(container) : activeMount)?.destroy(); }
  return {checkedRecordedPacket,decodeRecordedSession,checkedAtomicOperationHead,RELEASE_PROCEDURE_OUTLINE,releaseOperationProcess,releaseOpeningMatches,releaseHeadMatches,releaseProcedurePreview,operationFrameYield,claimFragment,operationRoutePreference,plannedOperationProcess,operationStageGraph,operationReadDuration,bufferedOperationCount,operationInspection,sourceBodySpan,operationReading,stageFactSpan,stageFactText,operationStageMarkup,stageNodeContents,operationAttention,operationFrames,bufferedOperations,checkedOperationBinding,checkedOperation,checkedOperationCheckpoint,operationReadingMarkup,operationHistoryMarkup,operationRecord,operationLabel,currentSourceSelection,checkedReferenceReplayStart,checkedReferenceReplayOpening,enteredRequirementContext,formingRequirements,conditionLabel,legalBasisMarkup,sourceExcerpt,referenceSourcePin,REFERENCE_DEMO_CASES,referenceExecution,claimStatusLabel,intakeGate,intakeEligible,intakeMarkup,sourceKind,claimAvailability,formingPublication,formingRelations,formingWork,formingMarkup,formingKnowledgeMarkup,knowledgeOriginMarkup,documentReviewMarkup,checkedSavedSnapshot,checkedReadCache,factCaseText,readKnowledge,readableSourceText,collectionPage,paginationMarkup,catalogPreviewMarkup,unknownClaimMarkup,historyLabel,actionLabel,procedureScope,knowledgeFacetMarkup,sourceObjectIdentity,consequentialEventNode,replayContentPacing,procedureLabel,acquiredContentMarkup,contextualRecord,recordButton,claimKnowledgeMarkup,openingContentMarkup,acceptedEventNode,acceptedEventContext,preferredEvidenceContext,claimHeadingMarkup,eventCueMarkup,readSkeletonMarkup,assessmentFreshness,assessmentFreshnessMarkup,semanticEventRecord,lastSemanticEvent,semanticEventMarkup,evidenceSelection,requirementIdentity,DEMO_CASES,DOMAINS,replayCanAdvance,demoItineraryMarkup,canonicalJSON,workingOperationScope,applyWorkingOperation,workingProcessState,workingReadiness,operationNodeId,operationRelationship,checkedPreview,readSnapshot,readReplay,demonstrationMarkup,liveAvailability,preferredNode,evidenceRelationships,evidencePathMarkup,knowledgeUses,edgeState,mount,destroy,demoAssetURL,checkedExamples,prefillExample,progressModel,progressMarkup,transitionPlan,animateTransition,mediaType,readState,layoutGraph,acceptEvents,eventIdentity,changedTargets,conditionFlags,checkedSource,graphMarkup,obligationMarkup,inspectorMarkup,workMarkup,knowledgeMarkup,claimsMarkup,collectionMarkup,matchingClaims,actionRows};
});
