import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import {
  captureBrowserExecutionReceipt,
  captureCandidateSourceSnapshot,
} from './candidate-source-identity.mjs';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:4173').replace(/\/$/, '');
if (new URL(BASE).origin !== 'http://127.0.0.1:4173') {
  throw new Error(`Workspace gate requires canonical same-origin localhost: ${BASE}`);
}
const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH;
if (executablePath !== '/Applications/ego lite.app/Contents/MacOS/ego lite') {
  throw new Error('Workspace gate requires the governed ego-browser executable');
}
const out = path.resolve(process.env.CASEPATH_WORKSPACE_QA_OUT || '');
if (path.basename(out) !== 'evidence' || !/^casepath-workspace-qa-real\.[A-Za-z0-9]{6,}$/.test(path.basename(path.dirname(out)))) {
  throw new Error(`Workspace evidence path is not a fresh dedicated root: ${out}`);
}
if (!['/private/tmp', await fs.realpath(os.tmpdir())].includes(await fs.realpath(path.dirname(path.dirname(out))))) {
  throw new Error(`Workspace evidence parent is outside a temporary root: ${out}`);
}
await fs.mkdir(out, { recursive: false });

const repository = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const corpusRoot = path.join(repository, 'casepath-api/casepath_api/corpora/synthetic-dev-60');
const corpusManifestPath = path.join(corpusRoot, 'manifest.json');
const corpusManifestFile = await fs.readFile(corpusManifestPath);
const corpusManifest = JSON.parse(corpusManifestFile);
const corpusManifestMaterial = {...corpusManifest};
delete corpusManifestMaterial.manifest_sha256;
const corpusClaimCount = corpusManifest.aggregate?.claim_count;
if (
  corpusManifestFile.toString('utf8') !== canonical(corpusManifest)
  || corpusManifest.contract !== 'casepath.public-observable-corpus/1.0.0'
  || corpusManifest.corpus_id !== 'synthetic-dev-60'
  || corpusManifest.contains_expected_outputs !== false
  || corpusManifest.contains_sealed_targets !== false
  || corpusClaimCount !== 60
  || !Array.isArray(corpusManifest.claims)
  || corpusManifest.claims.length !== corpusClaimCount
  || new Set(corpusManifest.claims.map(binding => binding.claim_id)).size !== corpusClaimCount
  || corpusManifest.manifest_sha256 !== sha(corpusManifestMaterial)
) {
  throw new Error('Workspace gate requires the exact canonical 60-claim public-development corpus manifest');
}
const corpusBindingsByClaimId = new Map(corpusManifest.claims.map(binding => [binding.claim_id, binding]));
const REGISTRATION_BODY_FIELDS = [
  'schema',
  'action_id',
  'expected_revision',
  'idempotency_key',
  'acquisition_intent_id',
  'acquisition_receipt_id',
  'content_b64',
];
const FORBIDDEN_BROWSER_SEMANTIC_FIELDS = [
  'attestation',
  'basis',
  'decision_key',
  'document_kind',
  'evidence_item_id',
  'evidence_status',
  'fact_state',
  'finding',
  'normalized_value',
  'operator_note',
  'source_entry_sha256',
  'value',
];
const checks = [];
const network = [];
const browserErrors = [];
const firstSafeActionSeconds = [];
const postEvidenceReplanSeconds = [];
const candidateSourceSnapshotStart = await captureCandidateSourceSnapshot({ requireApiBootReceipt: true });
const sourceManifestBytes = `${candidateSourceSnapshotStart.sourceRows.join('\n')}\n`;
const builtManifestBytes = `${candidateSourceSnapshotStart.builtRows.join('\n')}\n`;
await fs.writeFile(path.join(out, 'candidate-source-manifest.sha256'), sourceManifestBytes, { flag: 'wx' });
await fs.writeFile(path.join(out, 'candidate-built-static-manifest.sha256'), builtManifestBytes, { flag: 'wx' });
if (!candidateSourceSnapshotStart.apiBootReceiptBytes) throw new Error('Workspace gate lacks an installed runtime boot receipt');
await fs.writeFile(
  path.join(out, 'api-runtime-boot-receipt.json'),
  candidateSourceSnapshotStart.apiBootReceiptBytes,
  { flag: 'wx' },
);

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
  return JSON.stringify(value);
}
function sha(value) {
  return createHash('sha256').update(typeof value === 'string' || Buffer.isBuffer(value) ? value : canonical(value)).digest('hex');
}
const CLAIM_LOOP_FLOAT_FIELDS = new Set(['confidence', 'cost_usd']);
function claimLoopCanonical(value, field = null) {
  if (value === null || typeof value !== 'object') {
    if (typeof value === 'number' && Number.isInteger(value) && CLAIM_LOOP_FLOAT_FIELDS.has(field)) return value.toFixed(1);
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(item => claimLoopCanonical(item)).join(',')}]`;
  return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${claimLoopCanonical(value[key], key)}`).join(',')}}`;
}
function claimLoopSha(value) {
  return createHash('sha256').update(claimLoopCanonical(value)).digest('hex');
}
async function acquiredSourceBinding(claimId, acquisitionResponse) {
  const binding = corpusBindingsByClaimId.get(claimId);
  const receipt = acquisitionResponse?.acquisition_receipt;
  const contentB64 = acquisitionResponse?.content_b64;
  const acquiredBytes = typeof contentB64 === 'string' ? Buffer.from(contentB64, 'base64') : Buffer.alloc(0);
  const sourceDocuments = binding && receipt
    ? binding.source_documents.filter(document => document.sha256 === receipt.source_artifact_sha256)
    : [];
  const sourceDocument = sourceDocuments.length === 1 ? sourceDocuments[0] : null;
  const sourceBytes = sourceDocument
    ? await fs.readFile(path.join(corpusRoot, sourceDocument.path))
    : Buffer.alloc(0);
  const byteStart = receipt?.byte_start;
  const byteEnd = receipt?.byte_end;
  const sourceSpan = Number.isInteger(byteStart) && Number.isInteger(byteEnd)
    ? sourceBytes.subarray(byteStart, byteEnd)
    : Buffer.alloc(0);
  return {
    acquiredBytes,
    binding,
    passed: Boolean(
      binding
      && receipt
      && sourceDocument
      && sourceDocuments.length === 1
      && sourceBytes.length === sourceDocument.size_bytes
      && sha(sourceBytes) === sourceDocument.sha256
      && contentB64 === acquiredBytes.toString('base64')
      && acquiredBytes.length > 0
      && acquiredBytes.length === receipt.content_length
      && sha(acquiredBytes) === receipt.content_sha256
      && byteStart >= 0
      && byteEnd > byteStart
      && byteEnd <= sourceBytes.length
      && byteEnd - byteStart === receipt.content_length
      && Buffer.compare(sourceSpan, acquiredBytes) === 0
    ),
    receipt,
    sourceDocument,
    sourceSpan,
    text: acquiredBytes.toString('utf8'),
  };
}
function check(name, passed, detail = '') {
  checks.push({ name, passed: Boolean(passed), detail });
  if (!passed) throw new Error(`${name}: ${detail}`);
}
function p95(values) {
  const ordered = [...values].sort((a, b) => a - b);
  return ordered[Math.ceil(ordered.length * 0.95) - 1];
}
async function api(pathname, options = {}) {
  const response = await fetch(`${BASE}${pathname}`, options);
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(`${pathname}: ${response.status} ${canonical(body)}`);
  return body;
}
async function contextFor(browser, name) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  context.on('page', page => {
    page.on('pageerror', error => browserErrors.push({ scenario: name, kind: 'pageerror', message: String(error) }));
    page.on('console', message => {
      if (['error', 'warning'].includes(message.type())) browserErrors.push({ scenario: name, kind: message.type() === 'warning' ? 'warning' : 'console', message: message.text() });
    });
  });
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    network.push({ scenario: name, method: route.request().method(), url: url.href });
    if (url.origin !== new URL(BASE).origin) {
      await route.abort('blockedbyclient');
      return;
    }
    await route.continue();
  });
  return context;
}
async function waitWorkspace(page) {
  await page.waitForSelector('[data-claim-id]', { timeout: 30000 });
  await page.waitForFunction(expectedClaimCount => {
    const rows = [...document.querySelectorAll('[data-claim-id]')];
    const actions = [...document.querySelectorAll('[data-claim-id] td[data-label="Next action"] strong')];
    return rows.length === Math.min(25, expectedClaimCount)
      && document.querySelector('#cwTotal')?.textContent === String(expectedClaimCount)
      && actions.length === rows.length
      && actions.every(node => node.textContent.trim().length > 0);
  }, corpusClaimCount);
}
async function openClaim(page, claimId) {
  await page.locator('#cwSearch').fill(claimId);
  await page.waitForFunction(id => document.querySelectorAll('[data-claim-id]').length === 1 && document.querySelector('[data-claim-id]')?.dataset.claimId === id, claimId);
  await page.locator(`[data-claim-id="${claimId}"]`).click();
  await page.locator('#cwDetailPanel').waitFor({ state: 'visible' });
  await page.waitForFunction(id => document.querySelector('.cw-detail-title small')?.textContent === id, claimId);
}
async function pending(page, claimId, kind) {
  return page.evaluate(({ id, operation }) => sessionStorage.getItem(`casepath:workspace-command:${id}:${operation}`), { id: claimId, operation: kind });
}
async function serverDetail(claimId) {
  return api(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(claimId)}`);
}
async function serverLoop(claimId) {
  return api(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(claimId)}/loop`);
}
async function waitEvidenceWorkbench(page, checkPrefix) {
  if (typeof checkPrefix !== 'string' || checkPrefix.length === 0) {
    throw new Error('Evidence workbench check requires a unique non-empty prefix');
  }
  await page.waitForSelector('#cwEvidenceForm', { timeout: 30000 });
  await page.waitForFunction(() => {
    const proposal = document.querySelector('#cwLoopProposal');
    const commit = document.querySelector('#cwLoopCommit');
    return Boolean(proposal?.dataset.actionSha256 && commit);
  });
  check(`${checkPrefix}: Evidence workbench has no browser semantic or source-authority controls`, await page.locator('#cwEvidenceFinding,#cwEvidenceBasis,#cwEvidenceSource,#cwEvidenceNote,#cwEvidenceAttested,#cwEvidenceForm input,#cwEvidenceForm select,#cwEvidenceForm textarea').count() === 0);
}
async function prepareSourceAcquisition(page, loop) {
  const checkPrefix = `${loop.claim_id} revision ${loop.loop_state.revision}`;
  await waitEvidenceWorkbench(page, checkPrefix);
  const contract = loop.input_contract;
  check(`${checkPrefix}: server exposes one closed byte-acquisition contract`, contract?.contract === 'casepath.server-interpreted-evidence-input/1.0.0'
    && contract.registration_schema === 'casepath.workspace-evidence-registration/3.0.0'
    && contract.adapter_id === 'loopback-source-byte-acquisition-v1'
    && contract.server_interpretation_only === true
    && canonical(contract.registration_body_fields) === canonical(REGISTRATION_BODY_FIELDS)
    && contract.action_id === loop.loop_state.selected_action.action_id
    && contract.expected_revision === loop.loop_state.revision
    && Array.isArray(loop.finding_options) && loop.finding_options.length === 0
    && ['finding_values','unresolved_finding','decision_key','document_kind','basis_max_characters'].every(key => !(key in contract)));
}
async function commitAndConfirmReplan(page, claimId, beforeLoop) {
  const beforeActionSha = beforeLoop.loop_state.selected_action?.action_sha256 || '';
  const beforeRevision = beforeLoop.loop_state.revision;
  const checkPrefix = `${claimId} replan from revision ${beforeRevision}`;
  const transport = [];
  const capture = request => {
    const url = new URL(request.url());
    const loopPath = `/api/claim-loops/v1/workspace/claims/${claimId}/loop`;
    if (url.pathname === loopPath || url.pathname === `${loopPath}/evidence` || url.pathname === `${loopPath}/evidence/intents` || url.pathname.startsWith(`${loopPath}/evidence/intents/`) || url.pathname === `${loopPath}/advance`) {
      transport.push({ method: request.method(), path: url.pathname, body: request.postData(), idempotencyKey: request.headers()['x-casepath-idempotency-key'] || null });
    }
  };
  const responsePromises = [];
  const captureResponse = response => {
    const url = new URL(response.url());
    const loopPath = `/api/claim-loops/v1/workspace/claims/${claimId}/loop`;
    if (url.pathname === loopPath || url.pathname === `${loopPath}/evidence` || url.pathname === `${loopPath}/evidence/intents` || url.pathname.startsWith(`${loopPath}/evidence/intents/`) || url.pathname === `${loopPath}/advance`) {
      responsePromises.push(response.json().then(body => ({ method: response.request().method(), path: url.pathname, status: response.status(), body })));
    }
  };
  page.on('request', capture);
  page.on('response', captureResponse);
  const started = performance.now();
  await page.locator('#cwLoopCommit').click();
  await page.waitForFunction(
    ({ actionSha, revision }) => {
      const workbench = document.querySelector('#cwLoopWorkbench');
      const proposal = document.querySelector('#cwLoopProposal');
      const status = document.querySelector('#cwCommandStatus')?.textContent || '';
      const finished = status.includes('Observation committed once.');
      const changed = (proposal?.dataset.actionSha256 || '') !== actionSha
        || workbench?.dataset.outcome === 'abstain'
        || workbench?.dataset.outcome === 'decision_ready';
      return finished && changed && Number.isInteger(revision);
    },
    { actionSha: beforeActionSha, revision: beforeRevision },
    { timeout: 30000 },
  );
  const seconds = (performance.now() - started) / 1000;
  page.off('request', capture);
  page.off('response', captureResponse);
  const responses = await Promise.all(responsePromises);
  const after = await serverLoop(claimId);
  const loopPath = `/api/claim-loops/v1/workspace/claims/${claimId}/loop`;
  const acquisitionPathPattern = new RegExp(`^${loopPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}/evidence/intents/intent\\.[0-9a-f]{64}/acquire$`);
  check(`${checkPrefix}: exact six-request acquisition and replan sequence`, transport.length === 6
    && transport[0].method === 'POST' && transport[0].path === `${loopPath}/evidence/intents`
    && transport[1].method === 'POST' && acquisitionPathPattern.test(transport[1].path)
    && transport[2].method === 'POST' && transport[2].path === `${loopPath}/evidence`
    && transport[3].method === 'GET' && transport[3].path === loopPath
    && transport[4].method === 'POST' && transport[4].path === `${loopPath}/advance`
    && transport[5].method === 'GET' && transport[5].path === loopPath,
  canonical(transport));
  const intentBody = JSON.parse(transport[0].body);
  const registrationBody = JSON.parse(transport[2].body);
  const advanceBody = JSON.parse(transport[4].body);
  const intentResponse = responses[0]?.body;
  const acquisitionResponse = responses[1]?.body;
  const registrationResponse = responses[2]?.body;
  const intent = intentResponse?.intent;
  const acquisitionReceipt = acquisitionResponse?.acquisition_receipt;
  const registrationReceipt = registrationResponse?.stage_receipt;
  check(`${checkPrefix}: registration transports exactly the seven allowlisted V2 fields`, canonical(Object.keys(registrationBody).sort()) === canonical([...REGISTRATION_BODY_FIELDS].sort())
    && canonical(Object.keys(intentBody).sort()) === canonical(['action_id','expected_revision','idempotency_key'].sort())
    && registrationBody.schema === beforeLoop.input_contract.registration_schema
    && registrationBody.action_id === beforeLoop.loop_state.selected_action.action_id
    && registrationBody.expected_revision === beforeRevision
    && registrationBody.idempotency_key === intentBody.idempotency_key
    && registrationBody.idempotency_key === intent?.idempotency_key
    && registrationBody.acquisition_intent_id === intent?.intent_id
    && registrationBody.acquisition_receipt_id === acquisitionReceipt?.acquisition_receipt_id
    && transport[1].path === `${loopPath}/evidence/intents/${intent?.intent_id}/acquire`
    && transport[1].body === null
    && transport[2].idempotencyKey === registrationBody.idempotency_key
    && typeof registrationBody.content_b64 === 'string' && registrationBody.content_b64.length > 0
    && FORBIDDEN_BROWSER_SEMANTIC_FIELDS.every(field => !(field in registrationBody)), canonical({ intentBody, registrationBody, registrationHeaders: { idempotencyKey: transport[2].idempotencyKey } }));
  const sourceBinding = await acquiredSourceBinding(claimId, acquisitionResponse);
  check(`${checkPrefix}: acquired bytes are an exact claim-scoped source-artifact span`, sourceBinding.passed
    && acquisitionReceipt.adapter_id === 'loopback-source-byte-acquisition-v1'
    && acquisitionReceipt.channel === 'public-corpus-source-span-loopback-v1'
    && acquisitionReceipt.server_sniffed_media_type === 'text/plain; charset=utf-8'
    && acquisitionReceipt.claim_id === claimId
    && acquisitionReceipt.expected_revision === beforeRevision
    && acquisitionReceipt.expected_state_sha256 === beforeLoop.loop_state.state_sha256
    && acquisitionReceipt.action_id === beforeLoop.loop_state.selected_action.action_id
    && acquisitionReceipt.action_sha256 === beforeActionSha
    && acquisitionReceipt.acquisition_intent_id === intent.intent_id
    && acquisitionReceipt.idempotency_key === intent.idempotency_key,
  canonical({ receipt: acquisitionReceipt, sourceDocument: sourceBinding.sourceDocument }));
  check(`${checkPrefix}: advance binds exact parent and registration receipt`, advanceBody.expected_revision === beforeRevision
    && advanceBody.expected_state_sha256 === beforeLoop.loop_state.state_sha256
    && advanceBody.action_sha256 === beforeActionSha
    && /^[0-9a-f]{64}$/.test(advanceBody.stage_receipt_sha256)
    && typeof transport[4].idempotencyKey === 'string'
    && transport[4].idempotencyKey.length >= 8);
  check(`${checkPrefix}: responses and registration-to-advance lineage are exact`, responses.length === 6
    && canonical(responses.map(({ method, path }) => ({ method, path }))) === canonical([
      { method: 'POST', path: `${loopPath}/evidence/intents` },
      { method: 'POST', path: `${loopPath}/evidence/intents/${intent.intent_id}/acquire` },
      { method: 'POST', path: `${loopPath}/evidence` },
      { method: 'GET', path: loopPath },
      { method: 'POST', path: `${loopPath}/advance` },
      { method: 'GET', path: loopPath },
    ])
    && responses.every(row => row.status === 200)
    && registrationReceipt.receipt_sha256 === responses[3].body.stage_receipt.receipt_sha256
    && responses[3].body.loop_state.state_sha256 === beforeLoop.loop_state.state_sha256
    && advanceBody.stage_receipt_sha256 === registrationReceipt.receipt_sha256
    && responses[4].body.claim_loop_response.state_sha256 === responses[5].body.loop_state.state_sha256,
  canonical(responses));
  check(`${checkPrefix}: intent, acquisition, and registration receipts are independently content-addressed`, intentResponse.response_sha256 === claimLoopSha(Object.fromEntries(Object.entries(intentResponse).filter(([key]) => key !== 'response_sha256')))
    && intent.receipt_sha256 === claimLoopSha(Object.fromEntries(Object.entries(intent).filter(([key]) => key !== 'receipt_sha256')))
    && acquisitionResponse.response_sha256 === claimLoopSha(Object.fromEntries(Object.entries(acquisitionResponse).filter(([key]) => key !== 'response_sha256')))
    && acquisitionReceipt.receipt_sha256 === claimLoopSha(Object.fromEntries(Object.entries(acquisitionReceipt).filter(([key]) => key !== 'receipt_sha256')))
    && registrationResponse.response_sha256 === claimLoopSha(Object.fromEntries(Object.entries(registrationResponse).filter(([key]) => key !== 'response_sha256')))
    && registrationReceipt.receipt_sha256 === claimLoopSha(Object.fromEntries(Object.entries(registrationReceipt).filter(([key]) => key !== 'receipt_sha256')))
    && registrationReceipt.idempotency_key === registrationBody.idempotency_key
    && registrationReceipt.acquisition_intent_id === registrationBody.acquisition_intent_id
    && registrationReceipt.acquisition_receipt_id === registrationBody.acquisition_receipt_id
    && registrationReceipt.content_sha256 === acquisitionReceipt.content_sha256
    && registrationReceipt.content_length === acquisitionReceipt.content_length);
  check(`${checkPrefix}: GET confirms exact two-event authoritative transition`, after.loop_state.revision === beforeRevision + 2 && after.loop_state.state_sha256 !== beforeLoop.loop_state.state_sha256, canonical({ before: beforeRevision, after: after.loop_state.revision }));
  const observation = after.loop_state.observations.at(-1);
  const source = observation?.source_refs?.[0];
  check(`${checkPrefix}: admitted observation binds the exact acquired source bytes`, Boolean(source)
    && source.adapter_id === 'loopback-source-byte-acquisition-v1'
    && source.source_id === acquisitionReceipt.source_artifact_id
    && source.source_sha256 === acquisitionReceipt.source_artifact_sha256
    && source.source_version === acquisitionReceipt.source_version
    && source.locator_kind === 'text_quote'
    && source.page === 1
    && source.text_start === acquisitionReceipt.text_start
    && source.text_end === acquisitionReceipt.text_end
    && source.field === null
    && source.value === null
    && source.span_sha256 === acquisitionReceipt.content_sha256
    && source.sanitized_excerpt === sourceBinding.text
    && observation.value === sourceBinding.text
    && observation.evidence_item_id === beforeLoop.loop_state.selected_action.evidence_item_id);
  check(`${checkPrefix}: rendered outcome equals authoritative outcome`, await page.locator('#cwLoopWorkbench').getAttribute('data-outcome') === after.outcome, after.outcome);
  check(`${checkPrefix}: six role and three gate receipts remain visible`, await page.locator('#cwAgentReceipts li').count() === 6 && await page.locator('#cwGateReceipts li').count() === 3);
  return { after, seconds, transport, responses, acquisitionReceipt, registrationBody, sourceBinding };
}

let browser;
try {
  const roster = [];
  const seenCursors = new Set();
  let cursor = null;
  do {
    const query = new URLSearchParams({ limit: '100', sort: 'priority' });
    if (cursor !== null) query.set('cursor', cursor);
    const rosterPage = await api(`/api/claim-loops/v1/workspace/claims?${query}`);
    if (!Array.isArray(rosterPage.items)) throw new Error('Workspace roster page lacks an item array');
    roster.push(...rosterPage.items);
    const nextCursor = rosterPage.next_cursor;
    if (nextCursor === null || nextCursor === undefined || nextCursor === '') break;
    if (typeof nextCursor !== 'string' || seenCursors.has(nextCursor)) {
      throw new Error('Workspace roster pagination returned an invalid or repeated cursor');
    }
    seenCursors.add(nextCursor);
    cursor = nextCursor;
  } while (true);
  check(`API exposes exactly ${corpusClaimCount} unique public-development claims`, roster.length === corpusClaimCount && new Set(roster.map(row => row.claim_id)).size === corpusClaimCount, `count=${roster.length}`);
  check('API roster equals the source-bound corpus manifest', canonical(roster.map(row => row.claim_id).sort()) === canonical(corpusManifest.claims.map(row => row.claim_id).sort()));
  // A previous interrupted fault run may leave the coarse workflow/readiness
  // labels unchanged while still committing an owner or journal revision.  Such
  // a claim is not pristine and must never be reused as fresh fault input.
  const fresh = roster.filter(row => {
    const operational = row.operational_projection || {};
    const workspacePrefix = operational.workspace_prefix || {};
    return row.workflow_state === 'received'
      && row.readiness_state === 'not_assessed'
      && row.revision === 1
      && row.owner === null
      && workspacePrefix.revision === 1
      && operational.claim_loop_prefix === null
      && Array.isArray(operational.evidence_items)
      && operational.evidence_items.length === 0
      && operational.next_state?.kind === 'start_processing';
  });
  check('Fault gate has at least 31 pristine claims', fresh.length >= 31, `fresh=${fresh.length}`);

  const ledgerBefore = await api('/api/model-ledger');
  browser = await chromium.launch({ executablePath, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const browserExecutionReceipt = await captureBrowserExecutionReceipt({
    gatePath: fileURLToPath(import.meta.url),
    outputPath: out,
    outputEnvironmentKey: 'CASEPATH_WORKSPACE_QA_OUT',
    browserVersion: browser.version(),
    baseUrl: BASE,
    apiUrl: BASE,
  });
  const browserExecutionReceiptBytes = `${JSON.stringify(browserExecutionReceipt, null, 2)}\n`;
  await fs.writeFile(path.join(out, 'browser-execution-receipt.json'), browserExecutionReceiptBytes, { flag: 'wx' });

  // Real source-bound handler journey.
  {
    const claimId = fresh[0].claim_id;
    const context = await contextFor(browser, 'source-flow');
    const page = await context.newPage();
    await page.goto(`${BASE}/?ui=final`, { waitUntil: 'domcontentloaded' });
    await waitWorkspace(page);
    check('The user-facing final URL is the claims workspace', await page.title() === 'CasePath — Claims workspace' && await page.locator('#cwTotal').textContent() === String(corpusClaimCount));
    check('No hidden API selector is present', !new URL(page.url()).searchParams.has('api'));
    await page.screenshot({ path: path.join(out, 'workspace-desktop-queue.png'), fullPage: true });
    await openClaim(page, claimId);
    const binding = corpusManifest.claims.find(row => row.claim_id === claimId);
    const sourceClaim = JSON.parse(await fs.readFile(path.join(corpusRoot, binding.claim.path), 'utf8'));
    check('Browser shows exact customer subject', await page.locator('.cw-detail-title h2').textContent() === sourceClaim.customer_message.subject);
    check('Browser shows exact customer body', await page.locator('.cw-body-copy').textContent() === sourceClaim.customer_message.body);
    const artifactRows = await page.locator('.cw-artifact').evaluateAll(async anchors => Promise.all(anchors.map(async anchor => {
      const response = await fetch(anchor.href, { cache: 'no-store' });
      const bytes = await response.arrayBuffer();
      const digest = await crypto.subtle.digest('SHA-256', bytes);
      return { path: new URL(anchor.href).pathname, status: response.status, ok: response.ok, bytes: bytes.byteLength, sha256: [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, '0')).join('') };
    })));
    const expectedArtifactRows = binding.observable_artifacts.map(expected => ({
      path: `/api/claim-loops/v1/workspace/claims/${claimId}/artifacts/${expected.artifact_id}`,
      status: 200,
      ok: true,
      bytes: expected.size_bytes,
      sha256: expected.sha256,
    })).sort((left, right) => left.path.localeCompare(right.path));
    artifactRows.sort((left, right) => left.path.localeCompare(right.path));
    check('Displayed artifact roster exactly equals admitted bytes', canonical(artifactRows) === canonical(expectedArtifactRows), canonical({ actual: artifactRows, expected: expectedArtifactRows }));
    const accessibility = await new AxeBuilder({ page }).analyze();
    check('Workspace/detail has no serious accessibility violation', !accessibility.violations.some(row => ['critical', 'serious'].includes(row.impact)), canonical(accessibility.violations));
    await page.locator('#cwOwnerInput').fill('North Star Handler');
    await page.locator('#cwOwnerForm button').click();
    await page.waitForFunction(() => document.querySelector('#cwCommandStatus')?.textContent.includes('Assignment journaled'));
    const beforeStart = await serverDetail(claimId);
    const firstSafeStarted = performance.now();
    await page.locator('#cwStart').click();
    await waitEvidenceWorkbench(page, 'primary journey initial action');
    const initialLoop = await serverLoop(claimId);
    firstSafeActionSeconds.push((performance.now() - firstSafeStarted) / 1000);
    const after = await serverDetail(claimId);
    check('Real action reaches honest bounded state', after.state.revision === beforeStart.state.revision + 1 && after.state.workflow_state === 'in_review' && after.state.readiness_state === 'blocked' && after.state.intake_assessment && after.state.failure_or_unknown_effect === false, canonical(after.state));
    check('Compiler is explicitly zero-activity', canonical(after.state.intake_assessment.activity) === canonical({ model_calls: 0, provider_calls: 0, credential_reads: 0, cost_usd: 0 }));
    check('Initial action exposes one bounded genuine-evidence contract', initialLoop.input_contract.contract === 'casepath.server-interpreted-evidence-input/1.0.0'
      && initialLoop.input_contract.adapter_id === 'loopback-source-byte-acquisition-v1'
      && initialLoop.input_contract.server_interpretation_only === true
      && canonical(initialLoop.input_contract.registration_body_fields) === canonical(REGISTRATION_BODY_FIELDS)
      && initialLoop.input_contract.evidence_item_id === initialLoop.loop_state.selected_action.evidence_item_id
      && Array.isArray(initialLoop.finding_options) && initialLoop.finding_options.length === 0);
    await prepareSourceAcquisition(page, initialLoop);
    const firstReplan = await commitAndConfirmReplan(page, claimId, initialLoop);
    postEvidenceReplanSeconds.push(firstReplan.seconds);
    check('First observation is bound to exact server-acquired source bytes', firstReplan.after.loop_state.observations.length === 1
      && firstReplan.after.loop_state.observations[0].source_refs[0].adapter_id === 'loopback-source-byte-acquisition-v1'
      && firstReplan.after.loop_state.observations[0].source_refs[0].source_id === firstReplan.acquisitionReceipt.source_artifact_id
      && firstReplan.after.loop_state.observations[0].source_refs[0].source_sha256 === firstReplan.acquisitionReceipt.source_artifact_sha256
      && firstReplan.after.loop_state.observations[0].source_refs[0].span_sha256 === firstReplan.acquisitionReceipt.content_sha256
      && firstReplan.after.loop_state.observations[0].source_refs[0].sanitized_excerpt === firstReplan.sourceBinding.text,
    canonical(firstReplan.after.loop_state.observations));
    check('First source-grounded observation yields one different bounded action', firstReplan.after.outcome === 'next_action'
      && firstReplan.after.loop_state.selected_action.action_sha256 !== initialLoop.loop_state.selected_action.action_sha256,
    canonical(firstReplan.after.loop_state.selected_action));
    check('Next action remains bounded to a different evidence obligation', firstReplan.after.input_contract.evidence_item_id === firstReplan.after.loop_state.selected_action.evidence_item_id);
    await prepareSourceAcquisition(page, firstReplan.after);
    const secondReplan = await commitAndConfirmReplan(page, claimId, firstReplan.after);
    check('First specialist attempt replans from acquire to validate', secondReplan.after.outcome === 'next_action'
      && secondReplan.after.loop_state.observations.length === 2
      && secondReplan.after.loop_state.selected_action.action_kind === 'validate'
      && secondReplan.after.loop_state.selected_action.evidence_item_id === firstReplan.after.loop_state.selected_action.evidence_item_id);
    check('Second observation remains bound to its exact acquired source bytes', secondReplan.after.loop_state.observations[1].source_refs[0].source_sha256 === secondReplan.acquisitionReceipt.source_artifact_sha256
      && secondReplan.after.loop_state.observations[1].source_refs[0].span_sha256 === secondReplan.acquisitionReceipt.content_sha256
      && secondReplan.after.loop_state.observations[1].source_refs[0].sanitized_excerpt === secondReplan.sourceBinding.text);
    await prepareSourceAcquisition(page, secondReplan.after);
    const terminalReplan = await commitAndConfirmReplan(page, claimId, secondReplan.after);
    check('Bounded unresolved evidence terminates in safe abstention', terminalReplan.after.outcome === 'abstain'
      && terminalReplan.after.loop_state.phase === 'abstained'
      && terminalReplan.after.loop_state.terminal_mode === 'abstain'
      && terminalReplan.after.loop_state.selected_action === null
      && terminalReplan.after.loop_state.observations.length === 3
      && terminalReplan.after.loop_state.abstain_reason === 'mandatory evidence is unresolved and no bounded action remains'
      && terminalReplan.after.decision_packet.source_state_sha256 === terminalReplan.after.loop_state.state_sha256,
    canonical(terminalReplan.after.loop_state));
    check('Terminal observation remains bound to its exact acquired source bytes', terminalReplan.after.loop_state.observations[2].source_refs[0].source_sha256 === terminalReplan.acquisitionReceipt.source_artifact_sha256
      && terminalReplan.after.loop_state.observations[2].source_refs[0].span_sha256 === terminalReplan.acquisitionReceipt.content_sha256
      && terminalReplan.after.loop_state.observations[2].source_refs[0].sanitized_excerpt === terminalReplan.sourceBinding.text);
    const terminalPacket = terminalReplan.after.decision_packet;
    check('Terminal packet is independently hash-bound to the accepted cycle and state', terminalPacket.packet_sha256 === claimLoopSha(Object.fromEntries(Object.entries(terminalPacket).filter(([key]) => key !== 'packet_sha256')))
      && terminalPacket.source_state_sha256 === terminalReplan.after.loop_state.state_sha256
      && terminalPacket.six_agent_cycle_receipt_sha256 === terminalReplan.after.loop_state.six_agent_cycle_receipt.receipt_sha256
      && terminalPacket.deterministic_gate_receipt_sha256 === terminalReplan.after.loop_state.deterministic_gate_receipt.receipt_sha256
      && terminalPacket.accepted_cycle_artifacts_sha256 === terminalReplan.after.loop_state.accepted_cycle_artifacts.receipt_sha256
      && canonical(terminalPacket.current_overlay) === canonical(terminalReplan.after.loop_state.process.current_overlay)
      && canonical(terminalPacket.obligations) === canonical(terminalReplan.after.loop_state.obligations)
      && canonical(terminalPacket.provenance_edges) === canonical(terminalReplan.after.loop_state.provenance_edges)
      && canonical(terminalPacket.sufficiency) === canonical(terminalReplan.after.loop_state.sufficiency));
    const specialistHistory = terminalReplan.after.loop_state.action_history.filter(row => row.action.evidence_item_id === firstReplan.after.loop_state.selected_action.evidence_item_id);
    check('Specialist history is exactly acquire then validate, both observed', canonical(specialistHistory.map(row => ({ kind: row.action.action_kind, outcome: row.outcome }))) === canonical([
      { kind: 'acquire', outcome: 'observed' },
      { kind: 'validate', outcome: 'observed' },
    ]), canonical(specialistHistory));
    check('Terminal UI exposes a certified packet and explicit safety boundary', await page.locator('.cw-terminal-receipt').count() === 1
      && (await page.locator('.cw-safety-boundary').textContent()).includes('stopped rather than infer'));
    const terminalPacketSha = terminalReplan.after.decision_packet.packet_sha256;
    let reloadMutationPosts = 0;
    const countReloadMutations = request => {
      if (request.method() === 'POST' && new URL(request.url()).pathname.includes(`/workspace/claims/${claimId}/loop`)) reloadMutationPosts += 1;
    };
    page.on('request', countReloadMutations);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await waitWorkspace(page);
    await page.locator('#cwDetailPanel').waitFor({ state: 'visible' });
    await page.waitForFunction(id => document.querySelector('.cw-detail-title small')?.textContent === id, claimId);
    const reloadedLoop = await serverLoop(claimId);
    check('Reload preserves exact terminal packet and state identity', reloadedLoop.outcome === 'abstain'
      && reloadedLoop.decision_packet.packet_sha256 === terminalPacketSha
      && reloadedLoop.loop_state.state_sha256 === terminalReplan.after.loop_state.state_sha256
      && await page.locator('#cwLoopWorkbench').getAttribute('data-outcome') === 'abstain'
      && (await page.locator('.cw-terminal-receipt').textContent()).includes(terminalPacketSha.slice(0, 16))
      && (await page.locator('.cw-safety-boundary').textContent()).includes('stopped rather than infer')
      && !await pending(page, claimId, 'evidence-intent')
      && !await pending(page, claimId, 'evidence')
      && !await pending(page, claimId, 'advance')
      && reloadMutationPosts === 0);
    page.off('request', countReloadMutations);
    await page.screenshot({ path: path.join(out, 'workspace-terminal-desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    const mobile = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth, panel: document.querySelector('#cwDetailPanel').getBoundingClientRect().width, viewport: innerWidth }));
    check('Mobile workbench stays inside 390px viewport', mobile.overflow <= 1 && mobile.panel <= mobile.viewport + 1, canonical(mobile));
    await page.screenshot({ path: path.join(out, 'workspace-source-flow.png'), fullPage: true });
    const terminalLoopUrl = `${BASE}/api/claim-loops/v1/workspace/claims/${claimId}/loop`;
    await page.route(terminalLoopUrl, async route => {
      const real = await route.fetch();
      const forged = await real.json();
      forged.decision_packet.current_overlay = { forged_terminal_basis: true };
      forged.decision_packet.packet_sha256 = claimLoopSha(Object.fromEntries(Object.entries(forged.decision_packet).filter(([key]) => key !== 'packet_sha256')));
      forged.view_sha256 = claimLoopSha(Object.fromEntries(Object.entries(forged).filter(([key]) => key !== 'view_sha256')));
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(forged) });
    });
    await page.reload({ waitUntil: 'domcontentloaded' });
    await waitWorkspace(page);
    await page.waitForSelector('#cwDetailPanel .cw-error');
    check('A self-consistent terminal packet with a forged decision basis fails closed', (await page.locator('#cwDetailPanel .cw-error').textContent()).includes('terminal packet failed authority validation')
      && await page.locator('.cw-terminal-receipt').count() === 0);
    await page.unroute(terminalLoopUrl);
    await context.close();
  }

  // A lost registration response must reuse the same admitted bytes and commit once.
  {
    const claimId = fresh[1].claim_id;
    const context = await contextFor(browser, 'evidence-registration-response-drop');
    const page = await context.newPage();
    await page.goto(BASE); await waitWorkspace(page); await openClaim(page, claimId);
    await page.locator('#cwStart').click(); await waitEvidenceWorkbench(page, 'evidence-registration-response-drop initial action');
    const before = await serverLoop(claimId);
    await prepareSourceAcquisition(page, before);
    const loopPath = `/api/claim-loops/v1/workspace/claims/${claimId}/loop`;
    const registrationUrl = `${BASE}${loopPath}/evidence`;
    const advanceUrl = `${BASE}/api/claim-loops/v1/workspace/claims/${claimId}/loop/advance`;
    const requestBodies = [];
    const advanceBodies = [];
    let intentPosts = 0;
    let acquisitionPosts = 0;
    const countAcquisitionRequests = request => {
      const pathname = new URL(request.url()).pathname;
      if (request.method() === 'POST' && pathname === `${loopPath}/evidence/intents`) intentPosts += 1;
      if (request.method() === 'POST' && pathname.startsWith(`${loopPath}/evidence/intents/`) && pathname.endsWith('/acquire')) acquisitionPosts += 1;
    };
    page.on('request', countAcquisitionRequests);
    let dropResponse = true;
    await page.route(registrationUrl, async route => {
      if (route.request().method() !== 'POST') return route.continue();
      requestBodies.push(route.request().postData());
      if (dropResponse) {
        dropResponse = false;
        await route.fetch();
        return route.abort('connectionaborted');
      }
      return route.continue();
    });
    await page.route(advanceUrl, async route => {
      if (route.request().method() === 'POST') advanceBodies.push(route.request().postData());
      return route.continue();
    });
    await page.locator('#cwLoopCommit').click();
    await page.waitForFunction(() => document.querySelector('#cwCommandStatus')?.textContent.includes('No valid completion receipt was received'));
    const pendingIntent = await pending(page, claimId, 'evidence-intent');
    const pendingRegistration = await pending(page, claimId, 'evidence');
    const registrationBody = JSON.parse(requestBodies[0]);
    check('Lost registration response retains exact intent and registration commands', Boolean(pendingIntent) && Boolean(pendingRegistration)
      && requestBodies.length === 1
      && canonical(Object.keys(registrationBody).sort()) === canonical([...REGISTRATION_BODY_FIELDS].sort())
      && JSON.parse(pendingIntent).key === registrationBody.idempotency_key
      && JSON.parse(pendingRegistration).key === registrationBody.idempotency_key);
    const registered = await serverLoop(claimId);
    check('Lost registration response changes no domain state', registered.loop_state.state_sha256 === before.loop_state.state_sha256 && Boolean(registered.stage_receipt));
    const registrationReceiptSha = registered.stage_receipt.receipt_sha256;
    await page.reload({ waitUntil: 'domcontentloaded' });
    await waitWorkspace(page);
    await page.locator('#cwDetailPanel').waitFor({ state: 'visible' });
    await page.waitForFunction(id => document.querySelector('.cw-detail-title small')?.textContent === id, claimId);
    await page.waitForFunction(() => document.querySelector('#cwCommandStatus')?.textContent.includes('Observation committed once.'));
    const confirmed = await serverLoop(claimId);
    check('Reload reuses the exact registration receipt without reacquisition or a second registration POST', requestBodies.length === 1
      && intentPosts === 1
      && acquisitionPosts === 1
      && confirmed.loop_state.observations.length === 1
      && !await pending(page, claimId, 'evidence-intent')
      && !await pending(page, claimId, 'evidence')
      && !await pending(page, claimId, 'advance')
      && advanceBodies.length === 1
      && JSON.parse(advanceBodies[0]).stage_receipt_sha256 === registrationReceiptSha);
    page.off('request', countAcquisitionRequests);
    await context.close();
  }

  // A browser crash after durable acquisition, with all browser command storage
  // erased, must recover the one server acquisition and commit it exactly once.
  {
    const claimId = fresh[9].claim_id;
    const scenario = 'crash-after-acquisition-storage-cleared';
    const context = await contextFor(browser, scenario);
    const page = await context.newPage();
    const loopPath = `/api/claim-loops/v1/workspace/claims/${claimId}/loop`;
    const registrationUrl = `${BASE}${loopPath}/evidence`;
    const intentRequests = [];
    const acquisitionRequests = [];
    const registrationRequests = [];
    const intentResponsePromises = [];
    const acquisitionResponsePromises = [];
    const captureRequest = request => {
      const url = new URL(request.url());
      if (request.method() !== 'POST') return;
      if (url.pathname === `${loopPath}/evidence/intents`) {
        intentRequests.push(JSON.parse(request.postData()));
      } else if (url.pathname.startsWith(`${loopPath}/evidence/intents/`) && url.pathname.endsWith('/acquire')) {
        acquisitionRequests.push(url.pathname);
      } else if (url.pathname === `${loopPath}/evidence`) {
        registrationRequests.push({
          body: request.postData(),
          idempotencyKey: request.headers()['x-casepath-idempotency-key'] || null,
        });
      }
    };
    const captureResponse = response => {
      const url = new URL(response.url());
      if (response.request().method() !== 'POST' || response.status() !== 200) return;
      if (url.pathname === `${loopPath}/evidence/intents`) {
        intentResponsePromises.push(response.json());
      } else if (url.pathname.startsWith(`${loopPath}/evidence/intents/`) && url.pathname.endsWith('/acquire')) {
        acquisitionResponsePromises.push(response.json());
      }
    };
    const attachCapture = target => {
      target.on('request', captureRequest);
      target.on('response', captureResponse);
    };
    attachCapture(page);
    await page.goto(BASE); await waitWorkspace(page); await openClaim(page, claimId);
    await page.locator('#cwStart').click(); await waitEvidenceWorkbench(page, `${scenario} initial action`);
    const before = await serverLoop(claimId);
    await prepareSourceAcquisition(page, before);
    let registrationAborted = false;
    await page.route(registrationUrl, async route => {
      if (!registrationAborted && route.request().method() === 'POST') {
        registrationAborted = true;
        return route.abort('connectionaborted');
      }
      return route.continue();
    });
    await page.locator('#cwLoopCommit').click();
    await page.waitForFunction(() => document.querySelector('#cwCommandStatus')?.textContent.includes('No valid completion receipt was received'));
    const durableOnly = await serverLoop(claimId);
    const pendingIntentBeforeCrash = await pending(page, claimId, 'evidence-intent');
    const pendingEvidenceBeforeCrash = await pending(page, claimId, 'evidence');
    const firstIntentResponses = await Promise.all(intentResponsePromises);
    const firstAcquisitionResponses = await Promise.all(acquisitionResponsePromises);
    check('Crash boundary occurs after exactly one durable acquisition and before registration', registrationAborted
      && intentRequests.length === 1
      && acquisitionRequests.length === 1
      && registrationRequests.length === 1
      && firstIntentResponses.length === 1
      && firstIntentResponses[0].recovered_durable_acquisition === false
      && firstAcquisitionResponses.length === 1
      && Boolean(pendingIntentBeforeCrash)
      && Boolean(pendingEvidenceBeforeCrash)
      && durableOnly.stage_receipt === null
      && durableOnly.loop_state.observations.length === 0,
    canonical({ intentRequests, acquisitionRequests, registrationRequests, durableOnly }));
    const clearedStorageEntries = await page.evaluate(() => {
      sessionStorage.clear();
      return sessionStorage.length;
    });
    check('Browser crash simulation explicitly clears all session command storage', clearedStorageEntries === 0
      && !await pending(page, claimId, 'evidence-intent')
      && !await pending(page, claimId, 'evidence')
      && !await pending(page, claimId, 'advance'));
    await page.close();

    const recoveredPage = await context.newPage();
    attachCapture(recoveredPage);
    await recoveredPage.goto(BASE); await waitWorkspace(recoveredPage); await openClaim(recoveredPage, claimId);
    await waitEvidenceWorkbench(recoveredPage, `${scenario} recovered action`);
    check('Replacement browser page begins without any recoverable client command', !await pending(recoveredPage, claimId, 'evidence-intent')
      && !await pending(recoveredPage, claimId, 'evidence')
      && !await pending(recoveredPage, claimId, 'advance'));
    await recoveredPage.locator('#cwLoopCommit').click();
    await recoveredPage.waitForFunction(() => document.querySelector('#cwCommandStatus')?.textContent.includes('Observation committed once.'), null, { timeout: 30000 });
    const recovered = await serverLoop(claimId);
    const intentResponses = await Promise.all(intentResponsePromises);
    const acquisitionResponses = await Promise.all(acquisitionResponsePromises);
    const originalIntent = intentResponses[0]?.intent;
    const recoveryIntent = intentResponses[1]?.intent;
    const originalRegistration = JSON.parse(registrationRequests[0]?.body || 'null');
    const recoveredRegistration = JSON.parse(registrationRequests[1]?.body || 'null');
    const sourceBinding = await acquiredSourceBinding(claimId, acquisitionResponses[1]);
    check('Storage-free browser recovery adopts the exact durable server intent', intentRequests.length === 2
      && intentRequests[0].idempotency_key !== intentRequests[1].idempotency_key
      && intentResponses.length === 2
      && intentResponses[1].recovered_durable_acquisition === true
      && canonical(recoveryIntent) === canonical(originalIntent)
      && recoveryIntent.idempotency_key === intentRequests[0].idempotency_key
      && recoveryIntent.idempotency_key !== intentRequests[1].idempotency_key,
    canonical({ intentRequests, intentResponses }));
    check('Storage-free browser recovery replays one exact acquired byte receipt', acquisitionRequests.length === 2
      && acquisitionRequests[0] === acquisitionRequests[1]
      && acquisitionResponses.length === 2
      && canonical(acquisitionResponses[0]) === canonical(acquisitionResponses[1])
      && sourceBinding.passed,
    canonical({ acquisitionRequests, acquisitionResponses }));
    check('Recovered acquisition registers and advances exactly once', registrationRequests.length === 2
      && registrationRequests[0].body === registrationRequests[1].body
      && registrationRequests[0].idempotencyKey === originalIntent.idempotency_key
      && registrationRequests[1].idempotencyKey === originalIntent.idempotency_key
      && canonical(Object.keys(recoveredRegistration).sort()) === canonical([...REGISTRATION_BODY_FIELDS].sort())
      && canonical(recoveredRegistration) === canonical(originalRegistration)
      && recovered.loop_state.observations.length === 1
      && !await pending(recoveredPage, claimId, 'evidence-intent')
      && !await pending(recoveredPage, claimId, 'evidence')
      && !await pending(recoveredPage, claimId, 'advance'),
    canonical({ registrationRequests, recovered }));
    await context.close();
  }

  // A lost advance response is reconciled after reload without a second effect.
  {
    const claimId = fresh[2].claim_id;
    const context = await contextFor(browser, 'advance-response-drop');
    const page = await context.newPage();
    await page.goto(BASE); await waitWorkspace(page); await openClaim(page, claimId);
    await page.locator('#cwStart').click(); await waitEvidenceWorkbench(page, 'advance-response-drop initial action');
    const before = await serverLoop(claimId);
    await prepareSourceAcquisition(page, before);
    const advanceUrl = `${BASE}/api/claim-loops/v1/workspace/claims/${claimId}/loop/advance`;
    const requestBodies = [];
    let dropResponse = true;
    await page.route(advanceUrl, async route => {
      if (route.request().method() !== 'POST') return route.continue();
      requestBodies.push(route.request().postData());
      if (dropResponse) {
        dropResponse = false;
        await route.fetch();
        return route.abort('connectionaborted');
      }
      return route.continue();
    });
    await page.locator('#cwLoopCommit').click();
    await page.waitForFunction(() => document.querySelector('#cwCommandStatus')?.textContent.includes('No valid completion receipt was received'));
    const committed = await serverLoop(claimId);
    check('Lost advance response commits exactly one observation', committed.loop_state.observations.length === 1
      && committed.loop_state.state_sha256 !== before.loop_state.state_sha256
      && !await pending(page, claimId, 'evidence-intent')
      && !await pending(page, claimId, 'evidence')
      && Boolean(await pending(page, claimId, 'advance')));
    await page.reload({ waitUntil: 'domcontentloaded' });
    await waitWorkspace(page);
    await page.locator('#cwDetailPanel').waitFor({ state: 'visible' });
    await page.waitForFunction(id => document.querySelector('.cw-detail-title small')?.textContent === id, claimId);
    await page.waitForFunction(() => !sessionStorage.getItem(`casepath:workspace-command:${document.querySelector('.cw-detail-title small')?.textContent}:advance`));
    const recovered = await serverLoop(claimId);
    check('Reload replays the same advance identity without duplicate effect', requestBodies.length === 2
      && requestBodies[0] === requestBodies[1]
      && recovered.loop_state.state_sha256 === committed.loop_state.state_sha256
      && recovered.loop_state.observations.length === 1
      && !await pending(page, claimId, 'evidence-intent')
      && !await pending(page, claimId, 'evidence'));
    await context.close();
  }

  // A forged 200 from advance remains provisional until authoritative GET reconciliation.
  {
    const claimId = fresh[3].claim_id;
    const context = await contextFor(browser, 'forged-advance-200');
    const page = await context.newPage();
    await page.goto(BASE); await waitWorkspace(page); await openClaim(page, claimId);
    await page.locator('#cwStart').click(); await waitEvidenceWorkbench(page, 'forged-advance-200 initial action');
    const before = await serverLoop(claimId);
    await prepareSourceAcquisition(page, before);
    const advanceUrl = `${BASE}/api/claim-loops/v1/workspace/claims/${claimId}/loop/advance`;
    await page.route(advanceUrl, async route => {
      if (route.request().method() !== 'POST') return route.continue();
      const real = await route.fetch();
      const forged = await real.json();
      forged.claim_loop_response.state_sha256 = '0'.repeat(64);
      const outer = Object.fromEntries(Object.entries(forged).filter(([key]) => key !== 'response_sha256'));
      forged.response_sha256 = claimLoopSha(outer);
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(forged) });
    });
    await page.locator('#cwLoopCommit').click();
    await page.waitForFunction(() => document.querySelector('#cwCommandStatus')?.textContent.includes('No valid completion receipt was received'));
    check('Forged advance 200 never renders unconfirmed state', await page.locator('#cwLoopProposal').getAttribute('data-action-sha256') === before.loop_state.selected_action.action_sha256
      && !await pending(page, claimId, 'evidence-intent')
      && !await pending(page, claimId, 'evidence')
      && Boolean(await pending(page, claimId, 'advance')));
    const committed = await serverLoop(claimId);
    await page.unroute(advanceUrl);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await waitWorkspace(page);
    await page.locator('#cwDetailPanel').waitFor({ state: 'visible' });
    await page.waitForFunction(id => document.querySelector('.cw-detail-title small')?.textContent === id, claimId);
    await page.waitForFunction(id => {
      const status = document.querySelector('#cwCommandStatus')?.textContent || '';
      return status.includes('Observation committed once.')
        && !sessionStorage.getItem(`casepath:workspace-command:${id}:advance`);
    }, claimId);
    check('Reload reconciles forged-response ambiguity only from authoritative state', (await serverLoop(claimId)).loop_state.state_sha256 === committed.loop_state.state_sha256
      && !await pending(page, claimId, 'evidence-intent')
      && !await pending(page, claimId, 'evidence')
      && !await pending(page, claimId, 'advance'));
    await context.close();
  }

  // Closing a claim during an in-flight advance cannot leak busy state or stale rendering.
  {
    const claimId = fresh[4].claim_id;
    const otherClaimId = fresh[6].claim_id;
    const context = await contextFor(browser, 'close-midflight');
    const page = await context.newPage();
    await page.goto(BASE); await waitWorkspace(page); await openClaim(page, claimId);
    await page.locator('#cwStart').click(); await waitEvidenceWorkbench(page, 'close-midflight initial action');
    const before = await serverLoop(claimId);
    await prepareSourceAcquisition(page, before);
    const advanceUrl = `${BASE}/api/claim-loops/v1/workspace/claims/${claimId}/loop/advance`;
    let releaseRoute;
    let markEntered;
    const requestBodies = [];
    const requestKeys = [];
    const entered = new Promise(resolve => { markEntered = resolve; });
    const released = new Promise(resolve => { releaseRoute = resolve; });
    await page.route(advanceUrl, async route => {
      if (route.request().method() !== 'POST') return route.continue();
      requestBodies.push(route.request().postData());
      requestKeys.push(await route.request().headerValue('x-casepath-idempotency-key'));
      markEntered();
      await released;
      return route.continue();
    });
    await page.locator('#cwLoopCommit').click();
    await entered;
    await page.locator('[data-close-detail]').first().click();
    check('Close remains available during mutation and returns to the queue', await page.locator('#cwDetail').isHidden() && !(await page.locator('.cw-shell').evaluate(node => node.hasAttribute('inert'))));
    await openClaim(page, otherClaimId);
    check('A different claim opens while the original effect is pending', await page.locator('.cw-detail-title small').textContent() === otherClaimId);
    const delayedAdvanceResponse = page.waitForResponse(response =>
      response.url() === advanceUrl
        && response.request().method() === 'POST'
        && response.status() === 200,
    );
    releaseRoute();
    const firstAdvanceResponse = await delayedAdvanceResponse;
    const firstAdvanceBytes = await firstAdvanceResponse.body();
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    check('Old in-flight completion cannot overwrite the new claim DOM', await page.locator('.cw-detail-title small').textContent() === otherClaimId
      && !(await page.locator('#cwDetailPanel').textContent()).includes(claimId));
    await page.locator('[data-close-detail]').first().click();
    const retryAdvanceResponsePromise = page.waitForResponse(response =>
      response.url() === advanceUrl
        && response.request().method() === 'POST',
    );
    await openClaim(page, claimId);
    const retryAdvanceResponse = await retryAdvanceResponsePromise;
    const retryAdvanceBytes = await retryAdvanceResponse.body();
    await page.waitForFunction(id => document.querySelector('.cw-detail-title small')?.textContent === id, claimId);
    await page.waitForFunction(id => !sessionStorage.getItem(`casepath:workspace-command:${id}:advance`), claimId);
    const recovered = await serverLoop(claimId);
    check('Midflight completion belongs only to its original claim context', recovered.loop_state.observations.length === 1
      && await page.locator('.cw-detail-title small').textContent() === claimId
      && await page.locator('#cwLoopWorkbench').getAttribute('data-outcome') === recovered.outcome
      && !await pending(page, claimId, 'evidence-intent')
      && !await pending(page, claimId, 'evidence')
      && requestBodies.length === 2
      && requestBodies[0] === requestBodies[1]
      && requestKeys.length === 2
      && requestKeys[0] === requestKeys[1]
      && firstAdvanceResponse.status() === 200
      && retryAdvanceResponse.status() === 200
      && Buffer.compare(firstAdvanceBytes, retryAdvanceBytes) === 0);
    await context.close();
  }

  // Post-commit transport loss must recover without a second POST.
  {
    const claimId = fresh[5].claim_id;
    const context = await contextFor(browser, 'post-commit-drop');
    const page = await context.newPage();
    await page.goto(BASE); await waitWorkspace(page); await openClaim(page, claimId);
    const before = await serverDetail(claimId);
    let postCount = 0;
    let dropResponse = true;
    const startUrl = `${BASE}/api/claim-loops/v1/workspace/claims/${claimId}/start`;
    await page.route(startUrl, async route => {
      if (route.request().method() !== 'POST') return route.continue();
      postCount += 1;
      if (dropResponse) {
        dropResponse = false;
        await route.fetch();
        await route.abort('connectionaborted');
        return;
      }
      await route.continue();
    });
    await page.locator('#cwStart').click();
    await page.waitForFunction(() => document.querySelector('#cwCommandStatus')?.textContent.includes('Outcome is unknown'));
    check('Lost-response command identity remains durable in session', Boolean(await pending(page, claimId, 'start')));
    const committed = await serverDetail(claimId);
    check('Lost response committed exactly one journal event', committed.state.revision === before.state.revision + 1 && postCount === 1);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => document.querySelector('#cwCommandStatus')?.textContent.includes('Recovered the committed assessment'));
    check('Reload reconciles without redispatch', !await pending(page, claimId, 'start') && postCount === 1 && (await serverDetail(claimId)).state.state_sha256 === committed.state.state_sha256);
    await context.close();
  }

  // A self-consistent forged 200 is provisional and must never render.
  {
    const claimId = fresh[6].claim_id;
    const context = await contextFor(browser, 'forged-200');
    const page = await context.newPage();
    await page.goto(BASE); await waitWorkspace(page); await openClaim(page, claimId);
    await page.evaluate(() => {
      window.__workspaceSawFalseReady = false;
      new MutationObserver(() => {
        if (document.querySelector('#cwDetailPanel')?.textContent.includes('Decision Ready')) window.__workspaceSawFalseReady = true;
      }).observe(document.querySelector('#cwDetailPanel'), { subtree: true, childList: true, characterData: true });
    });
    const startUrl = `${BASE}/api/claim-loops/v1/workspace/claims/${claimId}/start`;
    await page.route(startUrl, async route => {
      if (route.request().method() !== 'POST') return route.continue();
      const real = await route.fetch();
      const forged = await real.json();
      forged.state.readiness_state = 'decision_ready';
      const stateMaterial = Object.fromEntries(Object.entries(forged.state).filter(([key]) => key !== 'state_sha256'));
      forged.state.state_sha256 = sha(stateMaterial);
      const responseMaterial = Object.fromEntries(Object.entries(forged).filter(([key]) => key !== 'response_sha256'));
      forged.response_sha256 = sha(responseMaterial);
      await route.fulfill({ status: 200, contentType: 'application/json', body: canonical(forged) });
    });
    await page.locator('#cwStart').click();
    await page.waitForFunction(() => document.querySelector('#cwCommandStatus')?.textContent.includes('Outcome is unknown'));
    check('Self-consistent forged readiness never renders', !(await page.evaluate(() => window.__workspaceSawFalseReady)) && !(await page.locator('#cwDetailPanel').textContent()).includes('Decision Ready'));
    check('Unconfirmed 200 keeps exact retry authority', Boolean(await pending(page, claimId, 'start')) && await page.locator('#cwStart').isDisabled());
    await context.close();
  }

  // Pre-commit gateway failure retains the exact request and can retry once.
  {
    const claimId = fresh[7].claim_id;
    const context = await contextFor(browser, 'gateway-502');
    const page = await context.newPage();
    await page.goto(BASE); await waitWorkspace(page); await openClaim(page, claimId);
    const before = await serverDetail(claimId);
    const startUrl = `${BASE}/api/claim-loops/v1/workspace/claims/${claimId}/start`;
    let injected = false;
    await page.route(startUrl, async route => {
      if (!injected && route.request().method() === 'POST') {
        injected = true;
        return route.fulfill({ status: 502, contentType: 'application/json', body: '{"detail":"QA_INJECTED_502"}' });
      }
      return route.continue();
    });
    await page.locator('#cwStart').click();
    await page.waitForFunction(() => document.querySelector('#cwCommandStatus')?.textContent.includes('Outcome is unknown'));
    const identity = await pending(page, claimId, 'start');
    check('Gateway failure makes no journal change and retains command', (await serverDetail(claimId)).state.state_sha256 === before.state.state_sha256 && Boolean(identity));
    await page.locator('#cwStart').click();
    await waitEvidenceWorkbench(page, 'gateway-502 retry action');
    check('Exact gateway retry commits once and clears slot', (await serverDetail(claimId)).state.revision === before.state.revision + 1 && !await pending(page, claimId, 'start'));
    await context.close();
  }

  // Genuine stale CAS plus failed refresh remains disabled until reload.
  {
    const claimId = fresh[8].claim_id;
    const context = await contextFor(browser, 'stale-409-refresh-drop');
    const page = await context.newPage();
    await page.goto(BASE); await waitWorkspace(page); await openClaim(page, claimId);
    const prior = await serverDetail(claimId);
    await api(`/api/claim-loops/v1/workspace/claims/${claimId}/owner`, {
      method: 'POST', headers: { 'content-type': 'application/json', 'x-casepath-idempotency-key': `qa-competitor-${claimId}` },
      body: JSON.stringify({ owner: 'Concurrent Handler', expected_revision: prior.state.revision }),
    });
    const detailUrl = `${BASE}/api/claim-loops/v1/workspace/claims/${claimId}`;
    let droppedGet = false;
    await page.route(detailUrl, async route => {
      if (!droppedGet && route.request().method() === 'GET') { droppedGet = true; return route.abort('connectionaborted'); }
      return route.continue();
    });
    await page.locator('#cwOwnerInput').fill('Stale Handler');
    await page.locator('#cwOwnerForm button').click();
    await page.waitForFunction(() => document.querySelector('#cwCommandStatus')?.textContent.includes('Authoritative state could not be reloaded'));
    check('Definitive stale request clears pending command', !await pending(page, claimId, 'assign'));
    check('Failed authoritative refresh leaves all mutations disabled', await page.locator('#cwOwnerForm button').isDisabled() && await page.locator('#cwStart').isDisabled());
    check('Only competing mutation entered journal', (await serverDetail(claimId)).state.owner === 'Concurrent Handler' && (await serverDetail(claimId)).state.revision === prior.state.revision + 1);
    await page.unroute(detailUrl);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await waitWorkspace(page);
    await page.locator('#cwDetailPanel').waitFor({ state: 'visible' });
    await page.waitForFunction(id => document.querySelector('.cw-detail-title small')?.textContent === id, claimId);
    check('Stale reload restores the exact deep-linked claim', await page.locator('.cw-detail-title small').textContent() === claimId);
    check('Stale reload restores exact authoritative owner', await page.locator('#cwOwnerInput').inputValue() === 'Concurrent Handler');
    check('Stale reload re-enables lawful controls', !(await page.locator('#cwOwnerForm button').isDisabled()) && !(await page.locator('#cwStart').isDisabled()));
    await context.close();
  }

  // A real server-acquired observation can be withdrawn only through one
  // server-enumerated, previewed, case-local correction.
  {
    const claimId = fresh[30].claim_id;
    const context = await contextFor(browser, 'scoped-correction');
    const page = await context.newPage();
    await page.goto(BASE); await waitWorkspace(page); await openClaim(page, claimId);
    await page.locator('#cwStart').click(); await waitEvidenceWorkbench(page, 'scoped-correction initial action');
    const before = await serverLoop(claimId);
    await prepareSourceAcquisition(page, before);
    const observed = await commitAndConfirmReplan(page, claimId, before);
    check('Observed state exposes exactly one server-owned correction option', observed.after.correction_candidates.length === 1 && observed.after.correction_count === 0);
    const eventRevisionBeforePreview = observed.after.loop_state.revision;
    const stateBeforePreview = observed.after.loop_state.state_sha256;
    const correctionTransport = [];
    const captureCorrection = request => {
      const url = new URL(request.url());
      if (url.pathname.includes(`/workspace/claims/${claimId}/loop/corrections`)) correctionTransport.push({ method:request.method(), path:url.pathname, body:request.postData() });
    };
    page.on('request', captureCorrection);
    let droppedCorrectionApply = false;
    let committedCorrectionResponse = null;
    const correctionApplyPath = `/api/claim-loops/v1/workspace/claims/${claimId}/loop/corrections`;
    await page.route(`**${correctionApplyPath}`, async route => {
      if (!droppedCorrectionApply && route.request().method() === 'POST') {
        const committed = await route.fetch();
        committedCorrectionResponse = await committed.json();
        droppedCorrectionApply = true;
        return route.abort('connectionaborted');
      }
      return route.continue();
    });
    await page.locator('#cwCorrectionReview').click();
    await page.waitForSelector('#cwCorrectionPreview');
    check('Correction preview leaves the domain journal unchanged', (await serverLoop(claimId)).loop_state.revision === eventRevisionBeforePreview && (await serverLoop(claimId)).loop_state.state_sha256 === stateBeforePreview);
    check('Correction preview shows affected and unchanged hashes', (await page.locator('#cwCorrectionPreview').textContent()).includes('unchanged') && await page.locator('#cwCorrectionPreview code').count() === 3);
    await page.locator('#cwCorrectionConfirm').click();
    await page.waitForFunction(() => document.querySelector('#cwCommandStatus')?.textContent.includes('No valid correction completion receipt was received'));
    page.off('request', captureCorrection);
    const corrected = await serverLoop(claimId);
    const delta = corrected.latest_correction;
    const pendingCorrectionRaw = await pending(page, claimId, 'correction-apply');
    const pendingCorrection = pendingCorrectionRaw ? JSON.parse(pendingCorrectionRaw) : null;
    check('Lost correction response leaves one durable effect and exact retry identity', droppedCorrectionApply
      && canonical(JSON.parse(pendingCorrection?.body || 'null')) === canonical({correction_id:delta.correction_id})
      && committedCorrectionResponse?.state_sha256 === corrected.loop_state.state_sha256
      && committedCorrectionResponse?.revision === corrected.loop_state.revision
      && committedCorrectionResponse?.command_receipt?.event_sha256 === delta.event_sha256
      && committedCorrectionResponse?.command_receipt?.idempotency_key === pendingCorrection?.key);
    check('Correction commits one fresh six-role/three-gate replan', corrected.correction_count === 1
      && corrected.correction_candidates.length === 0
      && corrected.loop_state.revision === eventRevisionBeforePreview + 1
      && corrected.loop_state.six_agent_cycle_receipt.cycle_kind === 'correction'
      && corrected.loop_state.six_agent_cycle_receipt.agent_ids.length === 6
      && corrected.loop_state.six_agent_cycle_receipt.deterministic_gate_ids.length === 3
      && corrected.audit.model_calls === 0 && corrected.audit.provider_calls === 0 && corrected.audit.cost_usd === 0);
    check('Correction changes only the target and preserves unrelated facts', delta.before_fact_sha256 !== delta.after_fact_sha256
      && delta.before_evidence_sha256 !== delta.after_evidence_sha256
      && delta.unrelated_facts_before_sha256 === delta.unrelated_facts_after_sha256
      && corrected.loop_state.facts.find(value => value.fact_id === delta.fact_id)?.state === 'unknown'
      && corrected.loop_state.checklist.items.find(value => value.item_id === delta.evidence_item_id)?.status === 'provided_insufficient');
    check('Browser cannot mint correction scope or effect', correctionTransport.length === 2
      && canonical(JSON.parse(correctionTransport[0].body)) === canonical({candidate_sha256:observed.after.correction_candidates[0].candidate_sha256,expected_revision:eventRevisionBeforePreview,expected_state_sha256:stateBeforePreview})
      && canonical(JSON.parse(correctionTransport[1].body)) === canonical({correction_id:delta.correction_id}));
    const correctionDeltaSha = delta.delta_sha256;
    let correctionReplayPosts = 0;
    const countCorrectionReplay = request => {
      if (request.method() === 'POST' && new URL(request.url()).pathname === correctionApplyPath) correctionReplayPosts += 1;
    };
    page.on('request', countCorrectionReplay);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await waitWorkspace(page);
    await page.locator('#cwDetailPanel').waitFor({ state: 'visible' });
    await page.waitForSelector('#cwCorrectionResult');
    const renderedDelta = await page.locator('#cwCorrectionResult').textContent();
    check('Correction delta survives exact browser reload', (await serverLoop(claimId)).latest_correction.delta_sha256 === correctionDeltaSha
      && await page.locator('#cwCorrectionResult [data-delta-sha256]').getAttribute('data-delta-sha256') === correctionDeltaSha
      && renderedDelta.includes(`${delta.before_fact_sha256.slice(0,12)}… → ${delta.after_fact_sha256.slice(0,12)}…`)
      && renderedDelta.includes(`${delta.before_evidence_sha256.slice(0,12)}… → ${delta.after_evidence_sha256.slice(0,12)}…`)
      && renderedDelta.includes(`${delta.unrelated_facts_after_sha256.slice(0,16)}… unchanged`)
      && await page.locator('#cwCorrectionReview').count() === 0
      && !await pending(page, claimId, 'correction-preview')
      && !await pending(page, claimId, 'correction-apply')
      && correctionReplayPosts === 0);
    page.off('request', countCorrectionReplay);
    await page.unroute(`**${correctionApplyPath}`);
    await page.screenshot({ path: path.join(out, 'workspace-scoped-correction.png'), fullPage: true });
    await context.close();
  }

  // Twenty real first-safe-action and post-acquisition evidence-replan samples.
  for (let index = postEvidenceReplanSeconds.length; index < 20; index += 1) {
    const claimId = fresh[10 + index].claim_id;
    const context = await contextFor(browser, `latency-replan-${index}`);
    const page = await context.newPage();
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
    await waitWorkspace(page);
    await openClaim(page, claimId);
    const firstSafeStarted = performance.now();
    await page.locator('#cwStart').click();
    await waitEvidenceWorkbench(page, `latency-replan-${index + 1} initial action`);
    const before = await serverLoop(claimId);
    firstSafeActionSeconds.push((performance.now() - firstSafeStarted) / 1000);
    await prepareSourceAcquisition(page, before);
    const confirmed = await commitAndConfirmReplan(page, claimId, before);
    postEvidenceReplanSeconds.push(confirmed.seconds);
    check(`Latency replan ${index + 1} is exact`, confirmed.after.loop_state.observations.length === 1
      && confirmed.after.loop_state.state_sha256 !== before.loop_state.state_sha256
      && confirmed.after.outcome === 'next_action');
    await context.close();
  }
  check('First-safe-action p95 is at most 10 seconds', p95(firstSafeActionSeconds) <= 10, canonical(firstSafeActionSeconds));
  check('Post-evidence replan p95 is at most 10 seconds', p95(postEvidenceReplanSeconds) <= 10, canonical(postEvidenceReplanSeconds));

  const ledgerAfter = await api('/api/model-ledger');
  check('Model ledger is byte-identical and empty', canonical(ledgerAfter) === canonical(ledgerBefore) && ledgerAfter.summary.records === 0 && ledgerAfter.summary.network_calls === 0, canonical(ledgerAfter));
  check('Browser attempted only canonical localhost origin', network.every(row => new URL(row.url).origin === new URL(BASE).origin));
  const expectedFaultConsole = [
    { scenario: 'advance-response-drop', kind: 'console', message: 'Failed to load resource: net::ERR_CONNECTION_ABORTED' },
    { scenario: 'crash-after-acquisition-storage-cleared', kind: 'console', message: 'Failed to load resource: net::ERR_CONNECTION_ABORTED' },
    { scenario: 'evidence-registration-response-drop', kind: 'console', message: 'Failed to load resource: net::ERR_CONNECTION_ABORTED' },
    { scenario: 'gateway-502', kind: 'console', message: 'Failed to load resource: the server responded with a status of 502 (Bad Gateway)' },
    { scenario: 'post-commit-drop', kind: 'console', message: 'Failed to load resource: net::ERR_CONNECTION_ABORTED' },
    { scenario: 'post-commit-drop', kind: 'console', message: 'Failed to load resource: the server responded with a status of 404 (Not Found)' },
    { scenario: 'scoped-correction', kind: 'console', message: 'Failed to load resource: net::ERR_CONNECTION_ABORTED' },
    { scenario: 'stale-409-refresh-drop', kind: 'console', message: 'Failed to load resource: net::ERR_CONNECTION_ABORTED' },
    { scenario: 'stale-409-refresh-drop', kind: 'console', message: 'Failed to load resource: the server responded with a status of 409 (Conflict)' },
  ].sort((left, right) => canonical(left).localeCompare(canonical(right)));
  const actualFaultConsole = [...browserErrors].sort((left, right) => canonical(left).localeCompare(canonical(right)));
  check('Browser journey has the exact expected fault-console roster', canonical(actualFaultConsole) === canonical(expectedFaultConsole), canonical({ actual: actualFaultConsole, expected: expectedFaultConsole }));
  check('All browser assertions passed', checks.every(row => row.passed), `${checks.filter(row => !row.passed).length} failures`);

  const candidateSourceSnapshotEnd = await captureCandidateSourceSnapshot({
    requireApiBootReceipt: true,
    allowValidatedWorkspaceJournalAdvance: true,
  });
  if (canonical(candidateSourceSnapshotEnd) !== canonical(candidateSourceSnapshotStart)) {
    throw new Error('Candidate installed source/runtime identity drifted during workspace browser gate');
  }
  const material = {
    contract: 'casepath.claims-workspace-browser-acceptance/1.0.0',
    base_url: BASE,
    corpus_manifest_sha256: sha(corpusManifestFile),
    claim_count: corpusClaimCount,
    checks,
    expected_fault_console_roster: expectedFaultConsole,
    timing: {
      clock: 'node_performance_monotonic',
      method: 'nearest_rank_p95',
      first_safe_action_seconds: firstSafeActionSeconds,
      first_safe_action_p95_seconds: p95(firstSafeActionSeconds),
      first_safe_action_budget_seconds: 10,
      first_safe_action_boundary: 'start_assessment_click_through_authoritative_evidence_action_rendered_and_confirmed_by_loop_get',
      post_evidence_replan_boundary: 'commit_click_through_intent_post_acquisition_post_exact_registration_post_registration_get_advance_post_authoritative_get_and_matching_dom',
      post_evidence_replan_seconds: postEvidenceReplanSeconds,
      post_evidence_replan_p95_seconds: p95(postEvidenceReplanSeconds),
      post_evidence_replan_budget_seconds: 10,
    },
    network_request_count: network.length,
    expected_fault_console: expectedFaultConsole,
    model_ledger_before_sha256: sha(ledgerBefore),
    model_ledger_after_sha256: sha(ledgerAfter),
    model_calls: 0,
    provider_calls: 0,
    credential_reads: 0,
    cost_usd: 0,
    candidate_source_identity: candidateSourceSnapshotStart.identity,
    api_runtime_identity: candidateSourceSnapshotStart.apiBootIdentity,
    candidate_source_manifests: {
      source: { path: 'candidate-source-manifest.sha256', sha256: sha(sourceManifestBytes), bytes: Buffer.byteLength(sourceManifestBytes), rows: candidateSourceSnapshotStart.sourceRows.length },
      built_static: { path: 'candidate-built-static-manifest.sha256', sha256: sha(builtManifestBytes), bytes: Buffer.byteLength(builtManifestBytes), rows: candidateSourceSnapshotStart.builtRows.length },
    },
    api_runtime_boot_receipt: {
      path: 'api-runtime-boot-receipt.json',
      sha256: sha(candidateSourceSnapshotStart.apiBootReceiptBytes),
      bytes: candidateSourceSnapshotStart.apiBootReceiptBytes.length,
      semantic_sha256: candidateSourceSnapshotStart.apiBootReceipt.receipt_sha256,
    },
    browser_execution_receipt: {
      path: 'browser-execution-receipt.json',
      sha256: sha(browserExecutionReceiptBytes),
      bytes: Buffer.byteLength(browserExecutionReceiptBytes),
      semantic_sha256: browserExecutionReceipt.receipt_sha256,
    },
  };
  const report = { ...material, receipt_sha256: sha(material) };
  const bytes = `${JSON.stringify(report, null, 2)}\n`;
  await fs.writeFile(path.join(out, 'report.json'), bytes, { flag: 'wx' });
  const manifestRows = [];
  for (const entry of (await fs.readdir(out, { withFileTypes: true })).sort((left, right) => left.name.localeCompare(right.name))) {
    if (!entry.isFile() || entry.isSymbolicLink() || entry.name === 'MANIFEST.sha256') {
      throw new Error(`Workspace evidence contains a noncanonical entry: ${entry.name}`);
    }
    const entryBytes = await fs.readFile(path.join(out, entry.name));
    manifestRows.push(`${sha(entryBytes)}  ${entry.name}`);
  }
  await fs.writeFile(path.join(out, 'MANIFEST.sha256'), `${manifestRows.join('\n')}\n`, { flag: 'wx' });
  console.log(JSON.stringify({ result: 'PASS', report_sha256: sha(bytes), receipt_sha256: report.receipt_sha256, checks: checks.length, timing: report.timing }));
} finally {
  await browser?.close();
}
