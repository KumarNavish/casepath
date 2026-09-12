import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import {
  captureBrowserExecutionReceipt,
  captureCandidateSourceSnapshot,
  installLoopbackNetworkGuard,
  summarizeLoopbackNetworkGuards,
} from './candidate-source-identity.mjs';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:4173').replace(/\/$/, '');
const API = (process.env.API_URL || BASE).replace(/\/$/, '');
if (new URL(BASE).origin !== new URL(API).origin) {
  throw new Error(`Insurance product gate requires one same-origin UI/API: ${BASE} != ${API}`);
}
if (new URL(BASE).origin !== 'http://127.0.0.1:4173') {
  throw new Error(`Insurance product gate requires the canonical launcher origin: ${BASE}`);
}
const RUN_ID = process.env.CASEPATH_QA_RUN_ID;
if (typeof RUN_ID !== 'string' || !/^[a-z0-9][a-z0-9-]{2,47}$/.test(RUN_ID)) {
  throw new Error(`CASEPATH_QA_RUN_ID is not a canonical test-run identifier: ${RUN_ID}`);
}
const INSURANCE_OUTPUT_PARENT = /^casepath-insurance-qa-real\.[A-Za-z0-9]{6,}$/;

async function resolveSafeOutput() {
  const candidate = process.env.CASEPATH_INSURANCE_QA_OUT;
  if (typeof candidate !== 'string' || candidate.trim() === '') {
    throw new Error('CASEPATH_INSURANCE_QA_OUT must name a fresh dedicated evidence directory');
  }
  const resolved = path.resolve(candidate);
  const parent = path.dirname(resolved);
  if (path.basename(resolved) !== 'evidence' || !INSURANCE_OUTPUT_PARENT.test(path.basename(parent))) {
    throw new Error(`Refusing noncanonical insurance evidence path: ${resolved}`);
  }
  const parentStat = await fs.lstat(parent);
  if (!parentStat.isDirectory() || parentStat.isSymbolicLink()) {
    throw new Error(`Insurance evidence parent is not a regular directory: ${parent}`);
  }
  const realParent = await fs.realpath(parent);
  const permittedRoots = new Set(await Promise.all(['/private/tmp', os.tmpdir()].map(root => fs.realpath(root))));
  if (!permittedRoots.has(path.dirname(realParent))) {
    throw new Error(`Insurance evidence parent is outside a permitted temporary root: ${realParent}`);
  }
  try {
    await fs.lstat(resolved);
    throw new Error(`Insurance evidence path must be absent: ${resolved}`);
  } catch (error) {
    if (error?.code !== 'ENOENT') throw error;
  }
  return resolved;
}

const OUT = await resolveSafeOutput();
const checks = [];
const timings = {
  warm_first_safe_action_seconds: [],
  post_upload_replan_seconds: [],
  clean_endpoint_seconds: [],
  correction_seconds: [],
};
const networkGuards = [];
let candidateSourceSnapshotStart;

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

function check(name, passed, detail = '') {
  checks.push({ name, passed: Boolean(passed), detail });
  if (!passed) throw new Error(`${name}: ${detail}`);
}

async function apiJson(pathname, sessionId = null) {
  const headers = { Accept: 'application/json' };
  if (sessionId) headers['X-CasePath-Session'] = sessionId;
  const response = await fetch(`${API}${pathname}`, { headers });
  if (!response.ok) throw new Error(`${pathname} returned ${response.status}`);
  return response.json();
}

async function newJourney(browser, sessionId, contextOptions = {}) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block', ...contextOptions });
  networkGuards.push(await installLoopbackNetworkGuard(context, {
    baseUrl: BASE,
    apiUrl: API,
    builtRows: candidateSourceSnapshotStart.builtRows,
  }));
  await context.addInitScript(value => {
    if (!sessionStorage.getItem('casepath:demo-session')) {
      sessionStorage.setItem('casepath:demo-session', value);
    }
  }, sessionId);
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  page.on('console', message => {
    if (message.type() === 'error') errors.push(message.text());
  });
  await page.goto(`${BASE}/?ui=final&journey=insurance-v1`, { waitUntil: 'domcontentloaded' });
  check(`Journey ${sessionId} has no hidden API parameter`, !new URL(page.url()).searchParams.has('api'), page.url());
  return { context, page, errors };
}

async function waitForProposal(page) {
  await page.locator('#artifactCanvas').getByText('Add a neutral technical assessment').waitFor({ timeout: 120000 });
}

function evidenceDocument(sessionId) {
  return `${canonicalJson({
    schema: 'casepath.synthetic-neutral-assessment/1.0.0',
    document_kind: 'neutral_assessment',
    evidence_item_id: 'technical_assessment',
    finding: 'building',
    basis: `Synthetic handler-authored technical basis for browser session ${sessionId}.`,
  })}`;
}

async function provideEvidence(page, sessionId) {
  const content = evidenceDocument(sessionId);
  await page.locator('#protocolEvidenceFile').setInputFiles({
    name: `${sessionId}-neutral-assessment.txt`,
    mimeType: 'text/plain',
    buffer: Buffer.from(content, 'utf8'),
  });
  await page.locator('#protocolEvidenceContent').waitFor();
  await page.waitForFunction(
    expected => document.querySelector('#protocolEvidenceContent')?.value === expected,
    content,
  );
  check(`Journey ${sessionId} loaded genuine evidence bytes`, await page.locator('#protocolEvidenceContent').inputValue() === content);
  return content;
}

async function selectAndRegister(page, sessionId, { reloadDraft = false } = {}) {
  await page.locator('#journeyNext').click();
  await page.locator('#artifactCanvas').getByText('Provide synthetic assessment evidence').waitFor();
  const content = await provideEvidence(page, sessionId);
  if (reloadDraft) {
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('#artifactCanvas').getByText('Provide synthetic assessment evidence').waitFor({ timeout: 120000 });
    await page.waitForFunction(
      expected => document.querySelector('#protocolEvidenceContent')?.value === expected,
      content,
    );
    check(`Journey ${sessionId} reload preserves the exact unadmitted draft`, await page.locator('#protocolEvidenceContent').inputValue() === content);
  }
  const startedAt = performance.now();
  const [registrationResponse] = await Promise.all([
    page.waitForResponse(response => {
      const url = new URL(response.url());
      return response.request().method() === 'POST'
        && /^\/api\/claim-loops\/v1\/[^/]+\/protocol\/registrations$/.test(url.pathname);
    }, { timeout: 120000 }),
    page.locator('#journeyNext').click(),
  ]);
  const registrationBody = await registrationResponse.json();
  await page.locator('#artifactCanvas').getByText('Registration accepted and replanned').waitFor({ timeout: 120000 });
  return { seconds: (performance.now() - startedAt) / 1000, content, registrationBody };
}

function p95(values) {
  const ordered = [...values].sort((left, right) => left - right);
  return ordered[Math.max(0, Math.ceil(ordered.length * 0.95) - 1)];
}

async function assertViewportBounds(page, label) {
  const result = await page.evaluate(() => {
    const roots = ['#artifactCanvas', '#journeyActions', '.appbar'];
    const elements = roots.flatMap(selector => {
      const root = document.querySelector(selector);
      return root ? [root, ...root.querySelectorAll('*')] : [];
    });
    const seen = new Set();
    return elements.filter(element => {
      if (seen.has(element)) return false;
      seen.add(element);
      const style = getComputedStyle(element);
      return style.display !== 'none' && style.visibility !== 'hidden' && element.getClientRects().length > 0;
    }).map(element => {
      const rect = element.getBoundingClientRect();
      const protocolSurface = element.matches('#artifactCanvas, #journeyActions, .appbar, .insurance-protocol-card, .insurance-protocol-diff, .insurance-protocol-hashes, .insurance-protocol-passages, .insurance-protocol-evidence-roster, .insurance-protocol-work-event, .insurance-protocol-correction-choice, .insurance-protocol-secondary-actions');
      return { selector: element.id ? `#${element.id}` : element.className || element.tagName, left: rect.left, right: rect.right, width: rect.width, viewport: innerWidth, client_width: element.clientWidth, scroll_width: element.scrollWidth, protocol_surface: protocolSurface };
    });
  });
  check(label, result.length > 3 && result.every(row => row.left >= -0.5 && row.right <= row.viewport + 0.5 && row.width <= row.viewport + 1 && (!row.protocol_surface || row.scroll_width <= row.client_width + 1)), canonicalJson(result.filter(row => row.left < -0.5 || row.right > row.viewport + 0.5 || row.width > row.viewport + 1 || (row.protocol_surface && row.scroll_width > row.client_width + 1))));
}

function stableRegistrationSemantics(protocol) {
  const records = protocol.record_set || {};
  const thin = protocol.thin_waist_record_set || {};
  return {
    protocol_status: protocol.protocol_status,
    terminal_mode: protocol.terminal_mode,
    next_action: protocol.next_action ? {
      action_kind: protocol.next_action.action_kind,
      evidence_item_id: protocol.next_action.evidence_item_id,
      fact_id: protocol.next_action.fact_id,
      bounded_tool_id: protocol.next_action.bounded_tool_id,
    } : null,
    intent: records.intent ? {
      capability_id: records.intent.capability_id,
      adapter_id: records.intent.adapter_id,
    } : null,
    action_receipt: records.action_receipt ? {
      status: records.action_receipt.status,
      capability_id: records.action_receipt.capability_id,
      adapter_id: records.action_receipt.adapter_id,
    } : null,
    assertion: thin.normalized_assertion ? {
      fact_id: thin.normalized_assertion.fact_id,
      evidence_item_id: thin.normalized_assertion.evidence_item_id,
      fact_state: thin.normalized_assertion.fact_state,
    } : null,
    interpretation_status: thin.interpretation?.status || null,
  };
}

await fs.mkdir(OUT);
let browser;
try {
  candidateSourceSnapshotStart = await captureCandidateSourceSnapshot({ requireApiBootReceipt: true });
  const gateBytes = await fs.readFile(new URL(import.meta.url));
  const gate = {
    path: 'casepath-qa/browser-insurance-protocol-v1.mjs',
    sha256: createHash('sha256').update(gateBytes).digest('hex'),
    bytes: gateBytes.length,
  };
  const sourceManifestBytes = `${candidateSourceSnapshotStart.sourceRows.join('\n')}\n`;
  const builtManifestBytes = `${candidateSourceSnapshotStart.builtRows.join('\n')}\n`;
  await fs.writeFile(path.join(OUT, 'candidate-source-manifest.sha256'), sourceManifestBytes, { flag: 'wx' });
  await fs.writeFile(path.join(OUT, 'candidate-built-static-manifest.sha256'), builtManifestBytes, { flag: 'wx' });
  if (candidateSourceSnapshotStart.apiBootReceiptBytes) {
    await fs.writeFile(
      path.join(OUT, 'api-runtime-boot-receipt.json'),
      candidateSourceSnapshotStart.apiBootReceiptBytes,
      { flag: 'wx' },
    );
  }
  const candidateSourceManifests = {
    source: {
      path: 'candidate-source-manifest.sha256',
      sha256: createHash('sha256').update(sourceManifestBytes).digest('hex'),
      bytes: Buffer.byteLength(sourceManifestBytes),
      rows: candidateSourceSnapshotStart.sourceRows.length,
    },
    built_static: {
      path: 'candidate-built-static-manifest.sha256',
      sha256: createHash('sha256').update(builtManifestBytes).digest('hex'),
      bytes: Buffer.byteLength(builtManifestBytes),
      rows: candidateSourceSnapshotStart.builtRows.length,
    },
  };
  const apiRuntimeBootReceipt = candidateSourceSnapshotStart.apiBootReceiptBytes ? {
    path: 'api-runtime-boot-receipt.json',
    sha256: createHash('sha256').update(candidateSourceSnapshotStart.apiBootReceiptBytes).digest('hex'),
    bytes: candidateSourceSnapshotStart.apiBootReceiptBytes.length,
    semantic_sha256: candidateSourceSnapshotStart.apiBootReceipt.receipt_sha256,
    source_manifest_file_sha256: candidateSourceSnapshotStart.apiBootReceipt.source.source_manifest_file_sha256,
  } : null;
  const beforeLedger = await apiJson('/api/model-ledger');
  check('Pre-journey model ledger is empty', beforeLedger.items?.length === 0 && beforeLedger.summary?.network_calls === 0, JSON.stringify(beforeLedger.summary));

  const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH;
  if (executablePath !== '/Applications/ego lite.app/Contents/MacOS/ego lite') {
    throw new Error(`PLAYWRIGHT_EXECUTABLE_PATH is not the governed ego-browser executable: ${executablePath || '<missing>'}`);
  }
  browser = await chromium.launch({ executablePath, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const browserExecutionReceipt = await captureBrowserExecutionReceipt({
    gatePath: fileURLToPath(import.meta.url),
    outputPath: OUT,
    outputEnvironmentKey: 'CASEPATH_INSURANCE_QA_OUT',
    browserVersion: browser.version(),
    baseUrl: BASE,
    apiUrl: API,
  });
  const browserExecutionReceiptBytes = `${JSON.stringify(browserExecutionReceipt, null, 2)}\n`;
  await fs.writeFile(path.join(OUT, 'browser-execution-receipt.json'), browserExecutionReceiptBytes, { flag: 'wx' });
  const browserExecutionReceiptBinding = {
    path: 'browser-execution-receipt.json',
    sha256: createHash('sha256').update(browserExecutionReceiptBytes).digest('hex'),
    bytes: Buffer.byteLength(browserExecutionReceiptBytes),
    semantic_sha256: browserExecutionReceipt.receipt_sha256,
  };

  const cleanSession = `${RUN_ID}-clean-0001`;
  const clean = await newJourney(browser, cleanSession);
  const cleanStartedAt = performance.now();
  const firstSafeActionStartedAt = performance.now();
  await clean.page.locator('#runCasePath').click();
  await waitForProposal(clean.page);
  timings.warm_first_safe_action_seconds.push((performance.now() - firstSafeActionStartedAt) / 1000);
  check('PACE UI states the claim-wide authority boundary', (await clean.page.locator('#artifactCanvas').innerText()).includes('ClaimLoop remains the claim-wide authority'));
  const cleanRegistration = await selectAndRegister(clean.page, cleanSession, { reloadDraft: true });
  timings.post_upload_replan_seconds.push(cleanRegistration.seconds);
  const productJavascript = await fs.readFile(
    new URL('../casepath/assets/insurance-protocol-v1.js', import.meta.url),
    'utf8',
  );
  check('Handler evidence bytes are absent from product source', !productJavascript.includes(cleanRegistration.content));
  timings.clean_endpoint_seconds.push((performance.now() - cleanStartedAt) / 1000);
  const cleanActions = Number(await clean.page.locator('body').getAttribute('data-insurance-action-count'));
  check('Clean base registration uses exactly three tracked workflow actions, excluding native file selection', cleanActions === 3, `actions=${cleanActions}`);
  const cleanLoopId = await clean.page.locator('body').getAttribute('data-casepath-active-loop-id');
  const cleanProtocol = await apiJson(`/api/claim-loops/v1/${encodeURIComponent(cleanLoopId)}/protocol-state`, cleanSession);
  const cleanState = await apiJson(`/api/claim-loops/v1/${encodeURIComponent(cleanLoopId)}`, cleanSession);
  check('Registration mutation omits the full state and same-tab hydration binds the canonical pair',
    !Object.hasOwn(cleanRegistration.registrationBody, 'state')
      && canonicalJson(cleanRegistration.registrationBody.protocol_state) === canonicalJson(cleanProtocol)
      && (await clean.page.locator('#artifactCanvas').textContent()).includes(cleanProtocol.projection_sha256)
      && (await clean.page.locator('#artifactCanvas').textContent()).includes(cleanState.state_sha256),
    canonicalJson({ registration: cleanRegistration.registrationBody, protocol: cleanProtocol, state_sha256: cleanState.state_sha256 }));
  check('Honest endpoint is a bounded recurrence action, not a manufactured terminal', cleanProtocol.protocol_status === 'replanned' && cleanProtocol.terminal_mode === null && cleanProtocol.next_action?.action_kind === 'clarify' && cleanProtocol.next_action?.evidence_item_id === 'recurrence_chronology' && cleanProtocol.decision_ready_packet_sha256 === null, JSON.stringify(cleanProtocol.next_action));
  const cleanTextContent = await clean.page.locator('#artifactCanvas').textContent();
  check('Rendered state, intent, and registry identities equal the API', cleanTextContent.includes(cleanProtocol.projection_sha256) && cleanTextContent.includes(cleanProtocol.record_set.intent.intent_sha256) && cleanTextContent.includes(cleanProtocol.record_set.action_receipt.receipt_sha256));
  check('UI and API agree that no decision packet exists yet', cleanProtocol.decision_ready_packet_sha256 === null && await clean.page.locator('#protocolPacket').count() === 0);
  check('Primary CTA truthfully reports the certified next action and cannot imply another transition', await clean.page.locator('#journeyNext').isDisabled()
    && (await clean.page.locator('#journeyNext').innerText()) === `Next action certified: ${cleanProtocol.next_action.title}`);
  check('Admitted source bytes and provenance equal the handler-selected file', cleanProtocol.record_set?.source_observation?.content_sha256 === createHash('sha256').update(cleanRegistration.content).digest('hex')
    && cleanProtocol.record_set?.source_observation?.exact_text_sha256 === createHash('sha256').update(cleanRegistration.content).digest('hex')
    && cleanProtocol.record_set?.normalized_assertion?.claim_observation?.source_refs?.[0]?.sanitized_excerpt === cleanRegistration.content
    && cleanProtocol.thin_waist_record_set?.normalized_assertion?.claim_observation_sha256 === cleanProtocol.record_set?.normalized_assertion?.claim_observation?.observation_sha256);
  check('Fresh replan traversed exact six roles and three deterministic gates', cleanState.six_agent_cycle_receipt?.cycle_kind === 'observation'
    && canonicalJson(cleanState.six_agent_cycle_receipt?.agent_ids) === canonicalJson(['canonical_facts', 'orchestrator_plan', 'document_source_integrity', 'process_decision_mapping', 'evidence_checklist', 'final_claim_brief_audit'])
    && canonicalJson(cleanState.six_agent_cycle_receipt?.deterministic_gate_ids) === canonicalJson(['deterministic_process_gate', 'deterministic_evidence_gate', 'whole_playbook_gate'])
    && cleanState.six_agent_cycle_receipt?.agent_receipt_sha256s?.length === 6
    && cleanState.six_agent_cycle_receipt?.gate_receipt_sha256s?.length === 3
    && cleanState.six_agent_cycle_receipt?.transport_mode === 'deterministic_test_double'
    && cleanState.six_agent_cycle_receipt?.model_calls === 0
    && cleanState.six_agent_cycle_receipt?.provider_calls === 0
    && cleanState.six_agent_cycle_receipt?.credential_access_status === 'none_due_to_zero_provider_calls'
    && cleanState.six_agent_cycle_receipt?.cost_status === 'exact'
    && cleanState.six_agent_cycle_receipt?.cost_usd === 0);
  const cleanArtifactCanvasHtml = await clean.page.locator('#artifactCanvas').innerHTML();
  const cleanWorkbenchText = await clean.page.locator('#artifactCanvas').innerText();
  const handlerHeadings = ['Current state', 'Why', 'Next action', 'Evidence', 'What changed'];
  const handlerHeadingIndexes = handlerHeadings.map(heading => cleanWorkbenchText.indexOf(heading));
  check('Handler workbench exposes the five operational questions in order', handlerHeadingIndexes.every((value, index) => value >= 0 && (index === 0 || handlerHeadingIndexes[index - 1] < value)), cleanWorkbenchText);
  const controllingFact = cleanState.facts.find(value => value.fact_id === cleanProtocol.next_action?.fact_id);
  const controllingExcerpts = (controllingFact?.source_refs || []).map(value => value.excerpt).filter(Boolean).slice(0, 3);
  check('Handler workbench exposes exact controlling source passages', controllingExcerpts.length >= 2 && controllingExcerpts.every(value => cleanWorkbenchText.includes(value)), canonicalJson(controllingExcerpts));
  check('Six persisted work events expose the full factual contract', await clean.page.locator('.insurance-protocol-work-event').count() === 6
    && ['Worker:', 'Actual input artifact', 'Actual typed output', 'Source references', 'Gate result', 'Duration', 'Terminal status'].every(label => cleanWorkbenchText.includes(label))
    && cleanState.six_agent_graph_audit.agents.every(agent => cleanWorkbenchText.includes(agent.input_artifact_hash) && cleanWorkbenchText.includes(agent.output_artifact_hash)), cleanWorkbenchText);
  check('Three persisted deterministic gate events are rendered', await clean.page.locator('.insurance-protocol-work > ul > li').count() === 3
    && cleanState.six_agent_graph_audit.deterministic_gates.every(gate => cleanWorkbenchText.includes(gate.role) && cleanWorkbenchText.includes(gate.input_artifact_hash) && cleanWorkbenchText.includes(gate.output_artifact_hash)));

  const actionsBeforeCorrection = Number(await clean.page.locator('body').getAttribute('data-insurance-action-count'));
  const correctionStartedAt = performance.now();
  await clean.page.locator('#protocolCorrection').click();
  await clean.page.getByText('Select the exact assertion and semantic change').waitFor({ timeout: 120000 });
  const correctionOptions = await apiJson(`/api/claim-loops/v1/${encodeURIComponent(cleanLoopId)}/protocol/corrections/options`, cleanSession);
  const selectedCorrection = correctionOptions.candidates?.[0];
  await clean.page.locator('#protocolCorrectionChoice').check();
  const correctionProposalRequestPromise = clean.page.waitForRequest(request => {
    const url = new URL(request.url());
    return request.method() === 'POST'
      && /^\/api\/claim-loops\/v1\/[^/]+\/protocol\/corrections\/proposal$/.test(url.pathname);
  }, { timeout: 120000 });
  await clean.page.locator('#journeyNext').click();
  const correctionProposalRequest = await correctionProposalRequestPromise;
  const correctionProposalBody = correctionProposalRequest.postDataJSON();
  const expectedCorrectionProposalBody = {
    candidate_sha256: selectedCorrection?.candidate_sha256,
    target_assertion_sha256: selectedCorrection?.target_assertion_sha256,
    target_interpretation_sha256: selectedCorrection?.target_interpretation_sha256,
    semantic_delta_id: selectedCorrection?.semantic_delta_id,
    expected_revision: selectedCorrection?.revision,
  };
  check('Correction preview sends the exact selected five-field JSON body',
    correctionProposalRequest.headers()['content-type'] === 'application/json'
      && canonicalJson(Object.keys(correctionProposalBody).sort()) === canonicalJson(Object.keys(expectedCorrectionProposalBody).sort())
      && canonicalJson(correctionProposalBody) === canonicalJson(expectedCorrectionProposalBody),
    canonicalJson({ headers: correctionProposalRequest.headers(), body: correctionProposalBody, expected: expectedCorrectionProposalBody }));
  await clean.page.getByText('Correction preview · not yet applied').waitFor({ timeout: 120000 });
  const previewProtocol = await apiJson(`/api/claim-loops/v1/${encodeURIComponent(cleanLoopId)}/protocol-state`, cleanSession);
  check('Correction preview changes no authoritative journal state', previewProtocol.correction_count === 0 && previewProtocol.projection_sha256 === cleanProtocol.projection_sha256);
  const previewText = await clean.page.locator('#artifactCanvas').textContent();
  check('Correction preview exposes affected, unaffected, and rollback commitments', previewText.includes('Unrelated objects: unchanged') && previewText.includes('Rollback fact') && previewText.includes('Rollback evidence'));
  await clean.page.reload({ waitUntil: 'domcontentloaded' });
  await clean.page.getByText('Correction preview · not yet applied').waitFor({ timeout: 120000 });
  await clean.page.locator('#journeyNext').click();
  await clean.page.locator('[data-correction-receipt]').waitFor({ timeout: 120000 });
  timings.correction_seconds.push((performance.now() - correctionStartedAt) / 1000);
  const correctedProtocol = await apiJson(`/api/claim-loops/v1/${encodeURIComponent(cleanLoopId)}/protocol-state`, cleanSession);
  check('Correction is material, local, and receipt-bound', correctedProtocol.correction_count === 1 && correctedProtocol.latest_correction.before_fact_sha256 !== correctedProtocol.latest_correction.after_fact_sha256 && correctedProtocol.latest_correction.unrelated_facts_before_sha256 === correctedProtocol.latest_correction.unrelated_facts_after_sha256);
  const correctedBeforeReloadHtml = await clean.page.locator('#artifactCanvas').innerHTML();
  const actionsAfterCorrection = Number(await clean.page.locator('body').getAttribute('data-insurance-action-count'));
  check('Correction uses exactly three tracked workflow actions, excluding the native radio selection', actionsAfterCorrection - actionsBeforeCorrection === 3, `delta=${actionsAfterCorrection - actionsBeforeCorrection}`);
  check('Applied correction exposes the exact rollback path', await clean.page.locator('#protocolCorrection').count() === 1 && (await clean.page.locator('#protocolCorrection').innerText()) === 'Roll back this correction');
  await clean.page.reload({ waitUntil: 'domcontentloaded' });
  await clean.page.locator('[data-correction-receipt]').waitFor({ timeout: 120000 });
  const correctedProtocolReloaded = await apiJson(`/api/claim-loops/v1/${encodeURIComponent(cleanLoopId)}/protocol-state`, cleanSession);
  check('Reload preserves exact correction receipt', await clean.page.locator('[data-correction-receipt]').getAttribute('data-correction-receipt') === correctedProtocol.latest_correction.delta_sha256 && canonicalJson(correctedProtocolReloaded) === canonicalJson(correctedProtocol));
  check('Reload reproduces the exact correction workbench bytes', await clean.page.locator('#artifactCanvas').innerHTML() === correctedBeforeReloadHtml);
  await clean.page.locator('#openAudit').click();
  await clean.page.locator('#auditDrawer[open]').waitFor();
  const auditText = await clean.page.locator('#auditContent').innerText();
  check('Header audit renders authoritative current and correction hashes', auditText.includes(correctedProtocol.projection_sha256)
    && auditText.includes(correctedProtocol.thin_waist_record_set.action_receipt.receipt_sha256)
    && auditText.includes(correctedProtocol.latest_correction.event_sha256)
    && auditText.includes(correctedProtocol.latest_correction.delta_sha256));
  const correctedArtifactCanvasHtml = await clean.page.locator('#artifactCanvas').innerHTML();
  const axe = await new AxeBuilder({ page: clean.page }).analyze();
  check('Insurance journey has no serious or critical accessibility violations', axe.violations.every(value => !['serious', 'critical'].includes(value.impact)), JSON.stringify(axe.violations.map(value => ({ id: value.id, impact: value.impact, targets: value.nodes.map(node => node.target) }))));
  check('Clean browser emitted no page or console errors', clean.errors.length === 0, JSON.stringify(clean.errors));
  await clean.context.close();

  const repeatedSession = `${RUN_ID}-clean-0002`;
  const repeatedClean = await newJourney(browser, repeatedSession);
  const repeatedCleanStartedAt = performance.now();
  const repeatedSafeActionStartedAt = performance.now();
  await repeatedClean.page.locator('#runCasePath').click();
  await waitForProposal(repeatedClean.page);
  timings.warm_first_safe_action_seconds.push((performance.now() - repeatedSafeActionStartedAt) / 1000);
  timings.post_upload_replan_seconds.push((await selectAndRegister(repeatedClean.page, repeatedSession)).seconds);
  timings.clean_endpoint_seconds.push((performance.now() - repeatedCleanStartedAt) / 1000);
  const repeatedLoopId = await repeatedClean.page.locator('body').getAttribute('data-casepath-active-loop-id');
  const repeatedProtocol = await apiJson(`/api/claim-loops/v1/${encodeURIComponent(repeatedLoopId)}/protocol-state`, repeatedSession);
  check('Repeated clean runs have identical stable registration semantics', canonicalJson(stableRegistrationSemantics(repeatedProtocol)) === canonicalJson(stableRegistrationSemantics(cleanProtocol)));
  check('Repeated clean browser emitted no page or console errors', repeatedClean.errors.length === 0, JSON.stringify(repeatedClean.errors));
  await repeatedClean.context.close();

  const accessibleSession = `${RUN_ID}-accessible-0001`;
  const accessible = await newJourney(browser, accessibleSession, {
    viewport: { width: 390, height: 844 },
    reducedMotion: 'reduce',
  });
  const accessibleStartedAt = performance.now();
  const accessibleSafeStartedAt = performance.now();
  await accessible.page.locator('#runCasePath').focus();
  await accessible.page.keyboard.press('Enter');
  await waitForProposal(accessible.page);
  check('390px proposal has no horizontal overflow', await accessible.page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
  await assertViewportBounds(accessible.page, '390px proposal keeps all primary surfaces in viewport');
  timings.warm_first_safe_action_seconds.push((performance.now() - accessibleSafeStartedAt) / 1000);
  await accessible.page.locator('#journeyNext').focus();
  await accessible.page.keyboard.press('Enter');
  await accessible.page.locator('#artifactCanvas').getByText('Provide synthetic assessment evidence').waitFor();
  await provideEvidence(accessible.page, accessibleSession);
  check('390px genuine evidence intake has no horizontal overflow', await accessible.page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
  await assertViewportBounds(accessible.page, '390px genuine evidence intake keeps all primary surfaces in viewport');
  const accessibleReplanStartedAt = performance.now();
  await accessible.page.locator('#journeyNext').focus();
  await accessible.page.keyboard.press('Enter');
  await accessible.page.locator('#artifactCanvas').getByText('Registration accepted and replanned').waitFor({ timeout: 120000 });
  timings.post_upload_replan_seconds.push((performance.now() - accessibleReplanStartedAt) / 1000);
  timings.clean_endpoint_seconds.push((performance.now() - accessibleStartedAt) / 1000);
  const accessibleLoopId = await accessible.page.locator('body').getAttribute('data-casepath-active-loop-id');
  const accessibleProtocol = await apiJson(`/api/claim-loops/v1/${encodeURIComponent(accessibleLoopId)}/protocol-state`, accessibleSession);
  check('Keyboard-only path reaches the authoritative replanned result', accessibleProtocol.protocol_status === 'replanned' && (await accessible.page.locator('#artifactCanvas').innerText()).includes(accessibleProtocol.next_action.title));
  check('Keyboard-only path preserves the exact clean endpoint semantics', canonicalJson(stableRegistrationSemantics(accessibleProtocol)) === canonicalJson(stableRegistrationSemantics(cleanProtocol)));
  check('Reduced-motion preference is active', await accessible.page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches));
  check('390px journey has no horizontal overflow', await accessible.page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
  await assertViewportBounds(accessible.page, '390px result keeps all primary surfaces in viewport');
  await accessible.page.locator('#protocolCorrection').focus();
  await accessible.page.keyboard.press('Enter');
  await accessible.page.getByText('Select the exact assertion and semantic change').waitFor({ timeout: 120000 });
  check('390px correction selection has no horizontal overflow', await accessible.page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
  await assertViewportBounds(accessible.page, '390px correction selection keeps all primary surfaces in viewport');
  await accessible.page.locator('#protocolCorrectionChoice').focus();
  await accessible.page.keyboard.press('Space');
  await accessible.page.locator('#journeyNext').focus();
  await accessible.page.keyboard.press('Enter');
  await accessible.page.getByText('Correction preview · not yet applied').waitFor({ timeout: 120000 });
  check('390px correction preview has no horizontal overflow', await accessible.page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
  await assertViewportBounds(accessible.page, '390px correction preview keeps all primary surfaces in viewport');
  await accessible.page.locator('#journeyNext').focus();
  await accessible.page.keyboard.press('Enter');
  await accessible.page.locator('[data-correction-receipt]').waitFor({ timeout: 120000 });
  check('390px correction result has no horizontal overflow', await accessible.page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
  await assertViewportBounds(accessible.page, '390px correction result keeps all primary surfaces in viewport');
  await accessible.page.reload({ waitUntil: 'domcontentloaded' });
  await accessible.page.locator('[data-correction-receipt]').waitFor({ timeout: 120000 });
  check('390px correction reload has no horizontal overflow', await accessible.page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
  await assertViewportBounds(accessible.page, '390px correction reload keeps all primary surfaces in viewport');
  check('390px keyboard journey emits no browser errors', accessible.errors.length === 0, JSON.stringify(accessible.errors));
  await accessible.context.close();

  for (let sample = 4; sample <= 20; sample += 1) {
    const benchmarkSession = `${RUN_ID}-latency-${String(sample).padStart(4, '0')}`;
    const benchmark = await newJourney(browser, benchmarkSession);
    const endpointStartedAt = performance.now();
    const safeActionStartedAt = performance.now();
    await benchmark.page.locator('#runCasePath').click();
    await waitForProposal(benchmark.page);
    timings.warm_first_safe_action_seconds.push((performance.now() - safeActionStartedAt) / 1000);
    timings.post_upload_replan_seconds.push((await selectAndRegister(benchmark.page, benchmarkSession)).seconds);
    timings.clean_endpoint_seconds.push((performance.now() - endpointStartedAt) / 1000);
    const benchmarkLoopId = await benchmark.page.locator('body').getAttribute('data-casepath-active-loop-id');
    const benchmarkProtocol = await apiJson(`/api/claim-loops/v1/${encodeURIComponent(benchmarkLoopId)}/protocol-state`, benchmarkSession);
    check(`Latency sample ${sample} preserves stable semantics`, canonicalJson(stableRegistrationSemantics(benchmarkProtocol)) === canonicalJson(stableRegistrationSemantics(cleanProtocol)));
    check(`Latency sample ${sample} emits no browser errors`, benchmark.errors.length === 0, JSON.stringify(benchmark.errors));
    await benchmark.context.close();
  }

  const droppedCreateSession = `${RUN_ID}-create-recovery-0001`;
  const droppedCreate = await newJourney(browser, droppedCreateSession);
  let createDropped = false;
  let committedCreateResponse = null;
  await droppedCreate.page.route(`${API}/api/claim-loops/v1/bootstrap/generated-mould`, async route => {
    if (!createDropped) {
      createDropped = true;
      const response = await route.fetch();
      committedCreateResponse = await response.json();
      await route.abort('failed');
      return;
    }
    await route.continue();
  });
  await droppedCreate.page.locator('#runCasePath').click();
  await droppedCreate.page.locator('#artifactCanvas').getByText('Stopped safely').waitFor({ timeout: 120000 });
  check('Dropped create is described as unconfirmed rather than rejected', (await droppedCreate.page.locator('#artifactCanvas').innerText()).includes('Outcome unconfirmed'));
  check('Dropped create surfaces exactly the injected transport failure', droppedCreate.errors.length === 1 && droppedCreate.errors[0].includes('net::ERR_FAILED'), JSON.stringify(droppedCreate.errors));
  droppedCreate.errors.length = 0;
  await droppedCreate.page.reload({ waitUntil: 'domcontentloaded' });
  await waitForProposal(droppedCreate.page);
  const recoveredCreateLoopId = await droppedCreate.page.locator('body').getAttribute('data-casepath-active-loop-id');
  const recoveredCreateProtocol = await apiJson(`/api/claim-loops/v1/${encodeURIComponent(recoveredCreateLoopId)}/protocol-state`, droppedCreateSession);
  const recoveredCreateProposal = await apiJson(`/api/claim-loops/v1/${encodeURIComponent(recoveredCreateLoopId)}/protocol/proposal`, droppedCreateSession);
  const recoveredCreateMarkup = await droppedCreate.page.locator('#artifactCanvas').textContent();
  check('Dropped create response recovers the exact one persistent loop', committedCreateResponse?.loop_id === recoveredCreateLoopId
    && recoveredCreateProtocol.loop_id === recoveredCreateLoopId
    && recoveredCreateProtocol.protocol_status === 'not_started'
    && recoveredCreateProtocol.record_set === null
    && recoveredCreateProposal.contract === 'casepath.insurance-proposal-response/1.0.0'
    && recoveredCreateProposal.loop_id === recoveredCreateLoopId
    && /^[0-9a-f]{64}$/.test(recoveredCreateProposal.proposal_sha256)
    && recoveredCreateProposal.proposal_sha256 === recoveredCreateProposal.proposal?.proposal_sha256
    && recoveredCreateProposal.revision === recoveredCreateProtocol.base_revision
    && recoveredCreateProposal.state_sha256 === recoveredCreateProtocol.base_state_sha256
    && recoveredCreateMarkup.includes(recoveredCreateProposal.proposal_sha256), canonicalJson({ committedCreateResponse, recoveredCreateLoopId, recoveredCreateProtocol, recoveredCreateProposal, recoveredCreateMarkup }));
  check('Create recovery emits no additional browser error', droppedCreate.errors.length === 0, JSON.stringify(droppedCreate.errors));
  await droppedCreate.context.close();

  const droppedRegisterSession = `${RUN_ID}-register-recovery-0001`;
  const droppedRegister = await newJourney(browser, droppedRegisterSession);
  await droppedRegister.page.locator('#runCasePath').click();
  await waitForProposal(droppedRegister.page);
  await droppedRegister.page.locator('#journeyNext').click();
  await provideEvidence(droppedRegister.page, droppedRegisterSession);
  let registrationDropped = false;
  let committedRegistrationResponse = null;
  await droppedRegister.page.route(/\/api\/claim-loops\/v1\/[^/]+\/protocol\/registrations$/, async route => {
    if (!registrationDropped) {
      registrationDropped = true;
      const response = await route.fetch();
      committedRegistrationResponse = await response.json();
      await route.abort('failed');
      return;
    }
    await route.continue();
  });
  await droppedRegister.page.locator('#journeyNext').click();
  await droppedRegister.page.locator('#artifactCanvas').getByText('Stopped safely').waitFor({ timeout: 120000 });
  check('Dropped registration is described as unconfirmed rather than rejected', (await droppedRegister.page.locator('#artifactCanvas').innerText()).includes('Outcome unconfirmed'));
  check('Dropped registration surfaces exactly the injected transport failure', droppedRegister.errors.length === 1 && droppedRegister.errors[0].includes('net::ERR_FAILED'), JSON.stringify(droppedRegister.errors));
  droppedRegister.errors.length = 0;
  await droppedRegister.page.locator('#journeyNext').click();
  await droppedRegister.page.locator('#artifactCanvas').getByText('Registration accepted and replanned').waitFor({ timeout: 120000 });
  const recoveredLoopId = await droppedRegister.page.locator('body').getAttribute('data-casepath-active-loop-id');
  const recoveredProtocol = await apiJson(`/api/claim-loops/v1/${encodeURIComponent(recoveredLoopId)}/protocol-state`, droppedRegisterSession);
  const committedProtocol = committedRegistrationResponse?.protocol_state;
  check('Dropped registration response hydrates the exact one-effect committed lineage', committedProtocol?.loop_id === recoveredLoopId
    && committedProtocol?.projection_sha256 === recoveredProtocol.projection_sha256
    && committedProtocol?.record_set?.intent?.intent_sha256 === recoveredProtocol.record_set?.intent?.intent_sha256
    && committedProtocol?.record_set?.action_receipt?.receipt_sha256 === recoveredProtocol.record_set?.action_receipt?.receipt_sha256
    && committedProtocol?.thin_waist_record_set?.action_receipt?.receipt_sha256 === recoveredProtocol.thin_waist_record_set?.action_receipt?.receipt_sha256
    && canonicalJson(committedProtocol?.protocol_event_sha256s) === canonicalJson(recoveredProtocol.protocol_event_sha256s)
    && recoveredProtocol.protocol_status === 'replanned', canonicalJson({ committedProtocol, recoveredProtocol }));
  check('Dropped-response browser emitted no page errors', droppedRegister.errors.length === 0, JSON.stringify(droppedRegister.errors));
  await droppedRegister.context.close();

  const afterLedger = await apiJson('/api/model-ledger');
  check('All browser paths preserve zero model/provider activity and cost', afterLedger.items?.length === 0 && afterLedger.summary?.records === 0 && afterLedger.summary?.network_calls === 0 && afterLedger.summary?.actual_cost_usd === 0, JSON.stringify(afterLedger.summary));
  const networkBoundary = await summarizeLoopbackNetworkGuards(networkGuards);
  check('Every browser context is confined to exact loopback origins with zero external requests', networkBoundary.loopback_only === true
    && networkBoundary.external_request_count === 0
    && networkBoundary.blocked_request_count === 0
    && networkBoundary.observed_origins.length === 1
    && networkBoundary.observed_origins[0] === new URL(BASE).origin, canonicalJson(networkBoundary));
  check('Every successful static response consumed by the insurance journey equals a frozen built-product file', networkBoundary.static_responses.length > 0, canonicalJson(networkBoundary.static_responses));
  const criticalStaticPaths = ['index.html', 'assets/insurance-protocol-v1.js', 'assets/insurance-protocol-v1.css'];
  check('Browser consumed the exact built index, insurance JavaScript, and insurance CSS', criticalStaticPaths.every(pathname => networkBoundary.static_responses.some(row => row.path === pathname)), canonicalJson(networkBoundary.static_responses));
  const latency = {
    warm_first_safe_action_p95_seconds: p95(timings.warm_first_safe_action_seconds),
    post_upload_replan_p95_seconds: p95(timings.post_upload_replan_seconds),
    clean_endpoint_p95_seconds: p95(timings.clean_endpoint_seconds),
    correction_observed_seconds: timings.correction_seconds[0],
    samples: timings,
  };
  check('Latency gate uses twenty clean browser samples', timings.warm_first_safe_action_seconds.length === 20 && timings.post_upload_replan_seconds.length === 20 && timings.clean_endpoint_seconds.length === 20, canonicalJson(latency));
  check('Warm first safe action p95 is within ten seconds', latency.warm_first_safe_action_p95_seconds <= 10, canonicalJson(latency));
  check('Provider-free post-upload replan p95 is within ten seconds', latency.post_upload_replan_p95_seconds <= 10, canonicalJson(latency));
  check('Clean bounded endpoint p95 is within three minutes', latency.clean_endpoint_p95_seconds <= 180, canonicalJson(latency));

  const transcriptPayload = {
    contract: 'casepath.insurance-protocol-browser-transcript/1.0.0',
    run_id: RUN_ID,
    session_id: cleanSession,
    loop_id: cleanLoopId,
    checkpoints: [
      {
        checkpoint: 'registration_replanned',
        protocol_response: cleanProtocol,
        protocol_response_sha256: createHash('sha256').update(canonicalJson(cleanProtocol)).digest('hex'),
        artifact_canvas_html: cleanArtifactCanvasHtml,
        artifact_canvas_html_sha256: createHash('sha256').update(cleanArtifactCanvasHtml).digest('hex'),
      },
      {
        checkpoint: 'correction_reloaded',
        protocol_response: correctedProtocolReloaded,
        protocol_response_sha256: createHash('sha256').update(canonicalJson(correctedProtocolReloaded)).digest('hex'),
        artifact_canvas_html: correctedArtifactCanvasHtml,
        artifact_canvas_html_sha256: createHash('sha256').update(correctedArtifactCanvasHtml).digest('hex'),
      },
    ],
    receipt_bindings: {
      decision_record_sha256: cleanProtocol.record_set.decision.decision_sha256,
      intent_sha256: cleanProtocol.record_set.intent.intent_sha256,
      action_receipt_sha256: cleanProtocol.record_set.action_receipt.receipt_sha256,
      thin_waist_action_receipt_sha256: cleanProtocol.thin_waist_record_set.action_receipt.receipt_sha256,
      correction_delta_sha256: correctedProtocol.latest_correction.delta_sha256,
    },
    activity: {
      before: beforeLedger.summary,
      after: afterLedger.summary,
    },
    browser_execution_receipt: browserExecutionReceiptBinding,
    network_boundary: networkBoundary,
  };
  const transcriptSemanticSha = createHash('sha256').update(canonicalJson(transcriptPayload)).digest('hex');
  const transcript = { ...transcriptPayload, transcript_sha256: transcriptSemanticSha };
  const transcriptBytes = `${JSON.stringify(transcript, null, 2)}\n`;
  await fs.writeFile(path.join(OUT, 'insurance-browser-transcript.json'), transcriptBytes, { flag: 'wx' });
  const journeyTranscript = {
    path: 'insurance-browser-transcript.json',
    sha256: createHash('sha256').update(transcriptBytes).digest('hex'),
    bytes: Buffer.byteLength(transcriptBytes),
    semantic_sha256: transcriptSemanticSha,
  };

  const reportPayload = {
    contract: 'casepath.insurance-protocol-browser-report/1.0.0',
    status: 'passed',
    base_url: BASE,
    api_url: API,
    checks,
    clean_loop_id: cleanLoopId,
    clean_projection_sha256: cleanProtocol.projection_sha256,
    corrected_projection_sha256: correctedProtocol.projection_sha256,
    correction_delta_sha256: correctedProtocol.latest_correction.delta_sha256,
    latency,
    activity: afterLedger.summary,
    gate,
    api_runtime_boot_receipt: apiRuntimeBootReceipt,
    api_runtime_identity: candidateSourceSnapshotStart.apiBootIdentity,
    browser_execution_receipt: browserExecutionReceiptBinding,
    browser_network_boundary: networkBoundary,
    journey_transcript: journeyTranscript,
    candidate_source_identity: candidateSourceSnapshotStart.identity,
    candidate_source_manifests: candidateSourceManifests,
  };
  const candidateSourceSnapshotEnd = await captureCandidateSourceSnapshot({
    requireApiBootReceipt: true,
    allowValidatedWorkspaceJournalAdvance: true,
  });
  if (canonicalJson(candidateSourceSnapshotEnd) !== canonicalJson(candidateSourceSnapshotStart)) {
    throw new Error(`Candidate source or built-static identity drifted during browser gate: ${canonicalJson({ candidateSourceSnapshotStart, candidateSourceSnapshotEnd })}`);
  }
  const canonical = canonicalJson(reportPayload);
  const report = { ...reportPayload, report_sha256: createHash('sha256').update(canonical).digest('hex') };
  await fs.writeFile(path.join(OUT, 'insurance-browser-report.json'), `${JSON.stringify(report, null, 2)}\n`, { flag: 'wx' });
  process.stdout.write(`${JSON.stringify({ status: 'passed', checks: checks.length, report_sha256: report.report_sha256 })}\n`);
} finally {
  if (browser) await browser.close();
}
