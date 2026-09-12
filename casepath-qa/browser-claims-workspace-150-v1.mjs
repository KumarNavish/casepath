import { execFile, spawn } from 'node:child_process';
import { createHash, randomBytes } from 'node:crypto';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import {
  captureBrowserExecutionReceipt,
  captureCandidateSourceSnapshot,
} from './candidate-source-identity.mjs';
import { replayClaimLoopJournalV1 } from './independent-claim-loop-replay-v1.mjs';
import {
  MAIN_CARRYOVER_CLAIM_ID,
  NEGATIVE_CARRYOVER_CLAIM_ID,
  ORDERED_CARRYOVER_CLAIM_IDS,
  validateGate2Gate1Carryovers,
} from './gate2-gate1-carryover-v1.mjs';

const execFileAsync = promisify(execFile);
const BASE = (process.env.BASE_URL || 'http://127.0.0.1:4173').replace(/\/$/, '');
const BASE_ORIGIN = new URL(BASE).origin;
if (BASE_ORIGIN !== 'http://127.0.0.1:4173') throw new Error(`Gate 2 requires canonical localhost: ${BASE}`);
const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH;
if (executablePath !== '/Applications/ego lite.app/Contents/MacOS/ego lite') throw new Error('Gate 2 requires governed ego-browser');
const out = path.resolve(process.env.CASEPATH_WORKSPACE_150_QA_OUT || '');
if (path.basename(out) !== 'evidence' || !/^casepath-workspace-150-qa-real\.[A-Za-z0-9]{6,}$/.test(path.basename(path.dirname(out)))) {
  throw new Error(`Gate 2 evidence root is not fresh and dedicated: ${out}`);
}
if (!['/private/tmp', await fs.realpath(os.tmpdir())].includes(await fs.realpath(path.dirname(path.dirname(out))))) {
  throw new Error(`Gate 2 evidence root is outside the temporary authority: ${out}`);
}
await fs.mkdir(out, { recursive: false });

const gate1Root = path.resolve(process.env.CASEPATH_GATE1_QA_ROOT || '');
const repository = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const corpusRoot = path.join(repository, 'casepath-api/casepath_api/corpora/synthetic-150');
const corpusManifestPath = path.join(corpusRoot, 'manifest.json');
const ROLE_IDS = Object.freeze([
  'canonical_facts',
  'orchestrator_plan',
  'document_source_integrity',
  'process_decision_mapping',
  'evidence_checklist',
  'final_claim_brief_audit',
]);
const GATE_IDS = Object.freeze([
  'deterministic_process_gate',
  'deterministic_evidence_gate',
  'whole_playbook_gate',
]);
const EVIDENCE_CLASSES = Object.freeze(['received', 'missing', 'insufficient', 'conditional', 'irrelevant', 'unknown']);
const SORTS = Object.freeze(['priority', 'urgency', 'oldest_waiting', 'nearest_deadline', 'most_decision_ready', 'latest_update']);
const WORKSPACE_SESSION_ID = 'casepath-workspace-local';
const CLAIM_LOOP_SESSION_ID = 'casepath-workspace-claim-loop-v1';
const WORKSPACE_EVENT_CONTRACT = 'casepath.claim-workspace-journal-event/1.0.0';
const CLAIM_LOOP_EVENT_CONTRACT = 'casepath.claim-loop-event/1.0.0';
const REGISTRATION_BODY_FIELDS = Object.freeze([
  'schema', 'action_id', 'expected_revision', 'idempotency_key',
  'acquisition_intent_id', 'acquisition_receipt_id', 'content_b64',
]);
const RAW_STATUS_CLASS = Object.freeze({
  missing: 'missing',
  provided_insufficient: 'insufficient',
  conditional: 'conditional',
  not_applicable: 'irrelevant',
  present_unreviewed: 'unknown',
  conflicting: 'unknown',
  unknown: 'unknown',
});
const checks = [];
const browserErrors = [];
const browserNetwork = [];
const browserNetworkTasks = new Set();
const postMutationQueueSeconds = [];
const browserControlRoster = [];
const firstSafeActionTimings = [];
const sourceAcquisitionTimings = [];
const postEvidenceReplanTimings = [];
const seamResults = [];
const queueIsolationReceipts = [];

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
  return JSON.stringify(value);
}
function sha(value) {
  return createHash('sha256').update(Buffer.isBuffer(value) || typeof value === 'string' ? value : canonical(value)).digest('hex');
}
const CLAIM_LOOP_FLOAT_FIELDS = new Set(['confidence', 'deterministic_confidence', 'cost_usd']);
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
function check(name, passed, detail = '') {
  const row = { name, passed: Boolean(passed), detail };
  checks.push(row);
  if (!row.passed) throw new Error(`${name}: ${detail}`);
}
function p95(values) {
  const ordered = [...values].sort((left, right) => left - right);
  return ordered[Math.ceil(0.95 * ordered.length) - 1];
}
function independentP95(values) {
  const counts = new Map();
  for (const value of values) counts.set(value, (counts.get(value) || 0) + 1);
  const target = Math.ceil(values.length * 95 / 100);
  let seen = 0;
  for (const value of [...counts.keys()].sort((left, right) => left - right)) {
    seen += counts.get(value);
    if (seen >= target) return value;
  }
  throw new Error('independent p95 received no values');
}
function without(value, key) {
  return Object.fromEntries(Object.entries(value).filter(([name]) => name !== key));
}
function exactSha(value, field, { loop = false } = {}) {
  return value?.[field] === (loop ? claimLoopSha(without(value, field)) : sha(without(value, field)));
}
function hasExactKeys(value, keys) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
    && canonical(Object.keys(value).sort()) === canonical([...keys].sort());
}
function label(value) {
  return String(value ?? '').replaceAll('_', ' ').replace(/\b\w/g, character => character.toUpperCase());
}
function sortedByCanonical(values) {
  return [...values].sort((left, right) => canonical(left).localeCompare(canonical(right)));
}

function projectionSemanticSlice(projection) {
  return {
    current_process: projection.current_process,
    controlling_decision: projection.controlling_decision,
    evidence_items: projection.evidence_items,
    evidence_class_counts: projection.evidence_class_counts,
    workflow_state: projection.workflow_state,
    readiness_state: projection.readiness_state,
    principal_blocker: projection.principal_blocker,
    pending_evidence_count: projection.pending_evidence_count,
    next_state: projection.next_state,
    failure_or_unknown_effect: projection.failure_or_unknown_effect,
  };
}

function reconstructJournalSemantics(state) {
  const overlay = state.process?.current_overlay;
  const nodes = Array.isArray(state.process?.nodes) ? state.process.nodes : [];
  const currentNode = nodes.find(node => node.node_id === overlay?.current_node_id);
  if (!overlay || !currentNode) throw new Error(`${state.claim_id}: raw process overlay does not select an accepted node`);
  const facts = new Map((state.facts || []).map(fact => [fact.fact_id, fact]));
  const obligations = new Map((state.obligations || []).map(obligation => [obligation.obligation_id, obligation]));
  const provenanceTuples = new Set((state.provenance_edges || []).map(edge => canonical([
    edge.fact_id, edge.evidence_item_id, edge.source_ref_id,
  ])));
  const evidenceItems = [];
  const evidenceClassCounts = Object.fromEntries(EVIDENCE_CLASSES.map(name => [name, 0]));
  let controllingDecision = null;
  for (const item of state.checklist?.items || []) {
    const fact = facts.get(item.fact_id);
    const obligation = obligations.get(item.item_id);
    if (!fact || !obligation || obligation.fact_id !== item.fact_id) {
      throw new Error(`${state.claim_id}: raw evidence joins are not closed`);
    }
    const receivedHasAuthority = fact.state === 'known'
      && obligation.status === 'satisfied'
      && Array.isArray(obligation.source_ref_ids)
      && obligation.source_ref_ids.length > 0
      && obligation.source_ref_ids.every(sourceRefId => provenanceTuples.has(canonical([
        obligation.fact_id, obligation.obligation_id, sourceRefId,
      ])));
    const evidenceClass = item.status === 'provided_sufficient'
      ? (receivedHasAuthority ? 'received' : 'unknown')
      : RAW_STATUS_CLASS[item.status];
    if (!EVIDENCE_CLASSES.includes(evidenceClass)) {
      throw new Error(`${state.claim_id}: unknown raw evidence status ${item.status}`);
    }
    evidenceClassCounts[evidenceClass] += 1;
    const projected = {
      evidence_item_id: item.item_id,
      title: item.title,
      fact_id: item.fact_id,
      fact_state: fact.state,
      raw_status: item.status,
      evidence_class: evidenceClass,
      obligation_status: obligation.status,
      mandatory_now: obligation.mandatory_now,
      current_path: Boolean(item.current_path),
      source_ref_ids: [...obligation.source_ref_ids],
      provenance_edge_sha256s: (state.provenance_edges || [])
        .filter(edge => edge.evidence_item_id === item.item_id)
        .map(edge => sha({
          fact_id: edge.fact_id,
          evidence_item_id: edge.evidence_item_id,
          source_ref_id: edge.source_ref_id,
        }))
        .sort(),
    };
    evidenceItems.push(projected);
    if (!controllingDecision && (obligation.mandatory_now || obligation.status === 'contradicted')) {
      controllingDecision = {
        obligation_id: obligation.obligation_id,
        fact_id: item.fact_id,
        fact_state: fact.state,
        obligation_status: obligation.status,
        evidence_item_id: item.item_id,
        evidence_class: evidenceClass,
        title: item.title,
      };
    }
  }
  if (evidenceItems.length !== obligations.size) {
    throw new Error(`${state.claim_id}: raw obligation/checklist cardinalities differ`);
  }
  if (state.selected_action && controllingDecision
    && state.selected_action.evidence_item_id !== controllingDecision.evidence_item_id) {
    throw new Error(`${state.claim_id}: raw selected action differs from the controlling obligation`);
  }
  let workflowState;
  let readinessState;
  let principalBlocker;
  let nextState;
  if (state.phase === 'decision_ready') {
    workflowState = 'decision_ready';
    readinessState = 'decision_ready';
    principalBlocker = 'No current mandatory evidence obligation remains';
    nextState = { kind: 'decision_ready', title: 'Review certified decision-ready packet', action_id: null, action_sha256: null, terminal_mode: state.terminal_mode };
  } else if (state.phase === 'abstained') {
    workflowState = 'safe_abstention';
    readinessState = 'safe_abstention';
    principalBlocker = state.abstain_reason || 'Mandatory evidence remains unresolved';
    nextState = { kind: 'safe_abstention', title: 'Review safe abstention and unresolved evidence', action_id: null, action_sha256: null, terminal_mode: state.terminal_mode };
  } else if (state.phase === 'dispatching') {
    workflowState = 'dispatching';
    readinessState = 'blocked';
    principalBlocker = 'One bounded evidence action is in flight';
    nextState = {
      kind: 'processing',
      title: 'Reconcile the in-flight evidence action',
      action_id: state.selected_action?.action_id || null,
      action_sha256: state.selected_action?.action_sha256 || null,
      terminal_mode: null,
    };
  } else if (state.selected_action) {
    workflowState = 'waiting_for_evidence';
    readinessState = 'blocked';
    principalBlocker = controllingDecision
      ? `${controllingDecision.title} is ${controllingDecision.evidence_class}`
      : 'The selected evidence action remains unresolved';
    nextState = {
      kind: 'evidence_action',
      title: state.selected_action.title,
      action_id: state.selected_action.action_id,
      action_sha256: state.selected_action.action_sha256,
      terminal_mode: null,
    };
  } else {
    workflowState = 'in_review';
    readinessState = 'blocked';
    principalBlocker = controllingDecision
      ? `${controllingDecision.title} is ${controllingDecision.evidence_class}`
      : 'The accepted journal is deriving its next bounded action';
    nextState = { kind: 'processing', title: 'Derive the next bounded evidence action', action_id: null, action_sha256: null, terminal_mode: null };
  }
  const semanticProjection = {
    current_process: {
      node_id: overlay.current_node_id,
      node_title: currentNode.title,
      next_action_node_id: overlay.next_action_node_id,
      selected_branch_id: overlay.selected_branch_id,
      overlay_sha256: sha(overlay),
    },
    controlling_decision: controllingDecision,
    evidence_items: evidenceItems,
    evidence_class_counts: evidenceClassCounts,
    workflow_state: workflowState,
    readiness_state: readinessState,
    principal_blocker: principalBlocker,
    pending_evidence_count: new Set([
      ...(state.sufficiency?.unresolved_mandatory_obligation_ids || []),
      ...(state.sufficiency?.contradicted_obligation_ids || []),
    ]).size,
    next_state: nextState,
    failure_or_unknown_effect: (state.action_history || []).some(action => ['failed', 'unknown'].includes(action.outcome)),
  };
  return {
    semantic_projection: semanticProjection,
    raw_journal_values: {
      process: {
        current_overlay: overlay,
        current_node: currentNode,
      },
      facts: sortedByCanonical(state.facts || []),
      obligations: sortedByCanonical(state.obligations || []),
      checklist_items: sortedByCanonical(state.checklist?.items || []),
      provenance_edges: sortedByCanonical((state.provenance_edges || []).map(edge => ({
        ...edge,
        edge_sha256: sha({ fact_id: edge.fact_id, evidence_item_id: edge.evidence_item_id, source_ref_id: edge.source_ref_id }),
      }))),
      source_references: sortedByCanonical((state.observations || []).flatMap(observation =>
        (observation.source_refs || []).map(sourceRef => ({ observation_id: observation.observation_id, ...sourceRef })))),
      observations: sortedByCanonical(state.observations || []),
    },
  };
}

async function verifyManifest(root, label) {
  const stat = await fs.lstat(root);
  if (!stat.isDirectory() || stat.isSymbolicLink() || await fs.realpath(root) !== root) throw new Error(`${label} root is not canonical`);
  const manifestPath = path.join(root, 'MANIFEST.sha256');
  const raw = await fs.readFile(manifestPath, 'utf8');
  const names = [];
  for (const line of raw.trimEnd().split('\n')) {
    const match = line.match(/^([0-9a-f]{64})  ([A-Za-z0-9._-]+)$/);
    if (!match) throw new Error(`${label} manifest row is invalid`);
    const candidate = path.join(root, match[2]);
    const metadata = await fs.lstat(candidate);
    if (!metadata.isFile() || metadata.isSymbolicLink() || sha(await fs.readFile(candidate)) !== match[1]) throw new Error(`${label} manifest entry drifted: ${match[2]}`);
    names.push(match[2]);
  }
  const actual = (await fs.readdir(root, { withFileTypes: true }))
    .map(entry => {
      if (!entry.isFile() || entry.isSymbolicLink()) throw new Error(`${label} contains a non-file entry`);
      return entry.name;
    })
    .filter(name => name !== 'MANIFEST.sha256')
    .sort();
  if (canonical(actual) !== canonical([...names].sort()) || new Set(names).size !== names.length) throw new Error(`${label} manifest is not exact`);
  return { file_sha256: sha(raw), row_count: names.length };
}

async function apiRaw(pathname, options = {}, accepted = [200]) {
  // The 150-case browser sweep intentionally leaves this Node-side client idle
  // for longer than Uvicorn's keep-alive window. Never let a pooled socket that
  // expires at the same instant as the final authority read turn a completed
  // product proof into an ambiguous ECONNRESET.
  const headers = new Headers(options.headers || {});
  headers.set('Connection', 'close');
  const response = await fetch(`${BASE}${pathname}`, {...options, headers});
  const raw = Buffer.from(await response.arrayBuffer());
  let body = null;
  try { body = JSON.parse(raw.toString('utf8')); } catch (_) { /* binary response */ }
  if (!accepted.includes(response.status)) throw new Error(`${pathname}: ${response.status} ${raw.toString('utf8')}`);
  return { status: response.status, headers: response.headers, raw, body };
}
async function api(pathname, options = {}) {
  return (await apiRaw(pathname, options)).body;
}
function post(body, key) {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CasePath-Idempotency-Key': key },
    body: canonical(body),
  };
}

async function sourceSpanBinding(binding, acquisitionResponse) {
  const receipt = acquisitionResponse?.acquisition_receipt;
  const contentB64 = acquisitionResponse?.content_b64;
  const acquired = typeof contentB64 === 'string' ? Buffer.from(contentB64, 'base64') : Buffer.alloc(0);
  const matches = receipt
    ? binding.source_documents.filter(document => document.sha256 === receipt.source_artifact_sha256)
    : [];
  const document = matches.length === 1 ? matches[0] : null;
  const source = document ? await fs.readFile(path.join(corpusRoot, document.path)) : Buffer.alloc(0);
  const span = Number.isInteger(receipt?.byte_start) && Number.isInteger(receipt?.byte_end)
    ? source.subarray(receipt.byte_start, receipt.byte_end)
    : Buffer.alloc(0);
  return {
    passed: Boolean(document && matches.length === 1
      && source.length === document.size_bytes
      && sha(source) === document.sha256
      && acquired.length === receipt.content_length
      && sha(acquired) === receipt.content_sha256
      && Buffer.compare(acquired, span) === 0),
    source_document: document,
    content_b64: contentB64,
    text: acquired.toString('utf8'),
  };
}

async function performEvidenceSeam(claimId, binding, before) {
  const loopPath = `/api/claim-loops/v1/workspace/claims/${claimId}/loop`;
  const action = before.loop_state.selected_action;
  const intentKey = `gate2.evidence.${binding.binding_sha256}`;
  const intentBody = {
    action_id: action.action_id,
    expected_revision: before.loop_state.revision,
    idempotency_key: intentKey,
  };
  const sourceStarted = performance.now();
  const intent = await apiRaw(`${loopPath}/evidence/intents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: canonical(intentBody),
  });
  const acquisitionPath = `${loopPath}/evidence/intents/${intent.body.intent.intent_id}/acquire`;
  const acquisition = await apiRaw(acquisitionPath, { method: 'POST' });
  const registrationBody = {
    schema: before.input_contract.registration_schema,
    action_id: action.action_id,
    expected_revision: before.loop_state.revision,
    idempotency_key: intent.body.intent.idempotency_key,
    acquisition_intent_id: intent.body.intent.intent_id,
    acquisition_receipt_id: acquisition.body.acquisition_receipt.acquisition_receipt_id,
    content_b64: acquisition.body.content_b64,
  };
  const registration = await apiRaw(`${loopPath}/evidence`, post(registrationBody, registrationBody.idempotency_key));
  const staged = await apiRaw(loopPath);
  const sourceSeconds = (performance.now() - sourceStarted) / 1000;
  sourceAcquisitionTimings.push({
    claim_id: claimId,
    boundary: 'intent_post_through_acquisition_post_exact_registration_post_and_authoritative_stage_get',
    seconds: sourceSeconds,
  });

  const source = await sourceSpanBinding(binding, acquisition.body);
  check(`${claimId}: seam intent and acquisition are exact and self-hashed`,
    exactSha(intent.body, 'response_sha256', { loop: true })
      && exactSha(intent.body.intent, 'receipt_sha256', { loop: true })
      && intent.body.recovered_durable_acquisition === false
      && intent.body.intent.claim_id === claimId
      && intent.body.intent.action_id === action.action_id
      && intent.body.intent.expected_revision === before.loop_state.revision
      && exactSha(acquisition.body, 'response_sha256', { loop: true })
      && exactSha(acquisition.body.acquisition_receipt, 'receipt_sha256', { loop: true })
      && acquisition.body.acquisition_receipt.acquisition_intent_id === intent.body.intent.intent_id
      && acquisition.body.acquisition_receipt.action_sha256 === action.action_sha256
      && source.passed);
  check(`${claimId}: seam registers exactly seven server-interpreted fields`,
    canonical(Object.keys(registrationBody).sort()) === canonical([...REGISTRATION_BODY_FIELDS].sort())
      && canonical(before.input_contract.registration_body_fields) === canonical(REGISTRATION_BODY_FIELDS)
      && registrationBody.idempotency_key === intentKey
      && exactSha(registration.body, 'response_sha256', { loop: true })
      && exactSha(registration.body.stage_receipt, 'receipt_sha256', { loop: true })
      && registration.body.stage_receipt.acquisition_intent_id === intent.body.intent.intent_id
      && registration.body.stage_receipt.acquisition_receipt_id
        === acquisition.body.acquisition_receipt.acquisition_receipt_id
      && registration.body.stage_receipt.content_sha256 === acquisition.body.acquisition_receipt.content_sha256
      && staged.body.loop_state.state_sha256 === before.loop_state.state_sha256
      && staged.body.stage_receipt.receipt_sha256 === registration.body.stage_receipt.receipt_sha256);

  const advanceBody = {
    expected_revision: before.loop_state.revision,
    expected_state_sha256: before.loop_state.state_sha256,
    action_sha256: action.action_sha256,
    stage_receipt_sha256: registration.body.stage_receipt.receipt_sha256,
  };
  const advanceKey = `gate2.advance.${binding.binding_sha256}`;
  const replanStarted = performance.now();
  const advance = await apiRaw(`${loopPath}/advance`, post(advanceBody, advanceKey));
  const after = await apiRaw(loopPath);
  const replanSeconds = (performance.now() - replanStarted) / 1000;
  postEvidenceReplanTimings.push({
    claim_id: claimId,
    boundary: 'advance_post_through_authoritative_replan_get',
    seconds: replanSeconds,
  });
  check(`${claimId}: seam advance is exact, observed once, and replans safely`,
    after.body.loop_state.revision === before.loop_state.revision + 2
      && after.body.loop_state.observations.length === before.loop_state.observations.length + 1
      && after.body.loop_state.state_sha256 === advance.body.claim_loop_response.state_sha256
      && after.body.loop_state.last_event_sha256 === advance.body.claim_loop_response.last_event_sha256
      && after.body.outcome === 'next_action'
      && Boolean(after.body.loop_state.selected_action)
      && after.body.loop_state.selected_action.action_sha256 !== action.action_sha256);
  const observation = after.body.loop_state.observations.at(-1);
  const sourceRef = observation.source_refs[0];
  check(`${claimId}: admitted observation binds the exact acquired source span`,
    observation.evidence_item_id === action.evidence_item_id
      && observation.value === source.text
      && sourceRef.source_id === acquisition.body.acquisition_receipt.source_artifact_id
      && sourceRef.source_sha256 === acquisition.body.acquisition_receipt.source_artifact_sha256
      && sourceRef.span_sha256 === acquisition.body.acquisition_receipt.content_sha256
      && sourceRef.sanitized_excerpt === source.text);

  const intentReplay = await apiRaw(`${loopPath}/evidence/intents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: canonical(intentBody),
  });
  const acquisitionReplay = await apiRaw(acquisitionPath, { method: 'POST' });
  const registrationReplay = await apiRaw(`${loopPath}/evidence`, post(registrationBody, registrationBody.idempotency_key));
  const advanceReplay = await apiRaw(`${loopPath}/advance`, post(advanceBody, advanceKey));
  const afterReplay = await apiRaw(loopPath);
  check(`${claimId}: every seam command replays byte-identically with zero duplicate effect`,
    intentReplay.raw.equals(intent.raw)
      && acquisitionReplay.raw.equals(acquisition.raw)
      && registrationReplay.raw.equals(registration.raw)
      && advanceReplay.raw.equals(advance.raw)
      && afterReplay.body.loop_state.revision === after.body.loop_state.revision
      && afterReplay.body.loop_state.state_sha256 === after.body.loop_state.state_sha256
      && afterReplay.body.loop_state.observations.length === after.body.loop_state.observations.length);

  return {
    contract: 'casepath.gate2-claim-evidence-seam/1.0.0',
    claim_id: claimId,
    binding_sha256: binding.binding_sha256,
    initial_outcome: before.outcome,
    final_outcome: after.body.outcome,
    intent_request: intentBody,
    intent_response: intent.body,
    acquisition_response: acquisition.body,
    registration_request: registrationBody,
    registration_response: registration.body,
    staged_view_sha256: staged.body.view_sha256,
    advance_request: advanceBody,
    advance_response: advance.body,
    final_view_sha256: after.body.view_sha256,
    idempotency_replay: {
      intent_response_file_sha256: sha(intentReplay.raw),
      acquisition_response_file_sha256: sha(acquisitionReplay.raw),
      registration_response_file_sha256: sha(registrationReplay.raw),
      advance_response_file_sha256: sha(advanceReplay.raw),
      final_state_sha256: afterReplay.body.loop_state.state_sha256,
      duplicate_effect_count: 0,
    },
    source_binding: source,
    source_acquisition_seconds: sourceSeconds,
    post_evidence_replan_seconds: replanSeconds,
    after_view: after.body,
  };
}

function validateProjection(projection, claimId, workspaceState, loopState = null) {
  const projectionKeys = ['claim_id','claim_loop_prefix','contract','controlling_decision','current_process','evidence_class_counts','evidence_items','failure_or_unknown_effect','last_authoritative_update','next_state','pending_evidence_count','principal_blocker','projection_sha256','readiness_state','workflow_state','workspace_prefix'];
  const prefixKeys = ['last_event_at','last_event_sha256','loop_id','revision','state_sha256'];
  const loopPrefixKeys = [...prefixKeys, 'phase'];
  const processKeys = ['next_action_node_id','node_id','node_title','overlay_sha256','selected_branch_id'];
  const nextKeys = ['action_id','action_sha256','kind','terminal_mode','title'];
  const evidenceKeys = ['current_path','evidence_class','evidence_item_id','fact_id','fact_state','mandatory_now','obligation_status','provenance_edge_sha256s','raw_status','source_ref_ids','title'];
  check(`${claimId}: operational projection is closed and self-hashed`, hasExactKeys(projection, projectionKeys)
    && projection.contract === 'casepath.workspace-operational-projection/1.0.0'
    && exactSha(projection, 'projection_sha256', { loop: true })
    && hasExactKeys(projection.workspace_prefix, prefixKeys)
    && hasExactKeys(projection.next_state, nextKeys)
    && (!projection.current_process || hasExactKeys(projection.current_process, processKeys)));
  check(`${claimId}: operational projection binds workspace prefix`, projection.claim_id === claimId
    && projection.workspace_prefix.loop_id === workspaceState.loop_id
    && projection.workspace_prefix.revision === workspaceState.revision
    && projection.workspace_prefix.state_sha256 === workspaceState.state_sha256
    && projection.workspace_prefix.last_event_sha256 === workspaceState.last_event_sha256);
  const counted = Object.fromEntries(EVIDENCE_CLASSES.map(name => [name, 0]));
  const seenEvidence = new Set();
  const evidenceItemsValid = projection.evidence_items.every(item => {
    if (!hasExactKeys(item, evidenceKeys) || seenEvidence.has(item.evidence_item_id)
      || !EVIDENCE_CLASSES.includes(item.evidence_class) || !Array.isArray(item.source_ref_ids)
      || !Array.isArray(item.provenance_edge_sha256s)
      || !item.provenance_edge_sha256s.every(value => /^[0-9a-f]{64}$/.test(value))) return false;
    seenEvidence.add(item.evidence_item_id);
    counted[item.evidence_class] += 1;
    return true;
  });
  check(`${claimId}: evidence classes are exhaustive`, canonical(Object.keys(projection.evidence_class_counts).sort()) === canonical([...EVIDENCE_CLASSES].sort())
    && EVIDENCE_CLASSES.every(name => Number.isInteger(projection.evidence_class_counts[name]) && projection.evidence_class_counts[name] >= 0)
    && projection.evidence_items.length === EVIDENCE_CLASSES.reduce((sum, name) => sum + projection.evidence_class_counts[name], 0)
    && evidenceItemsValid && EVIDENCE_CLASSES.every(name => counted[name] === projection.evidence_class_counts[name]));
  if (loopState) {
    check(`${claimId}: operational projection binds ClaimLoop prefix`, hasExactKeys(projection.claim_loop_prefix, loopPrefixKeys)
      && projection.claim_loop_prefix.loop_id === loopState.loop_id
      && projection.claim_loop_prefix.revision === loopState.revision
      && projection.claim_loop_prefix.state_sha256 === loopState.state_sha256
      && projection.claim_loop_prefix.last_event_sha256 === loopState.last_event_sha256
      && projection.claim_loop_prefix.phase === loopState.phase);
  }
}

function validateLoopView(view, claimId, workspaceState) {
  check(`${claimId}: loop view is closed and self-hashed`, view.contract === 'casepath.workspace-claim-loop-view/2.0.0'
    && view.claim_id === claimId && exactSha(view, 'view_sha256', { loop: true }));
  const state = view.loop_state;
  check(`${claimId}: loop state is self-hashed and outer-bound`, state.claim_id === claimId
    && view.revision === state.revision && view.state_sha256 === state.state_sha256
    && exactSha(state, 'state_sha256', { loop: true }));
  const accepted = state.accepted_cycle_artifacts;
  check(`${claimId}: accepted cycle artifacts are raw-state-bound`, Boolean(accepted)
    && exactSha(accepted, 'receipt_sha256', { loop: true })
    && state.accepted_cycle_artifacts_sha256 === accepted.receipt_sha256
    && canonical(state.facts) === canonical(accepted.facts)
    && canonical(state.process) === canonical(accepted.process)
    && canonical(state.checklist) === canonical(accepted.checklist));
  const cycle = state.six_agent_cycle_receipt;
  check(`${claimId}: six exact deterministic roles are bound`, canonical(cycle.agent_ids) === canonical(ROLE_IDS)
    && cycle.agent_receipt_sha256s.length === 6 && cycle.execution_implementation === 'compiled_langgraph_stategraph'
    && cycle.transport_mode === 'deterministic_test_double');
  check(`${claimId}: three exact gates are bound`, canonical(cycle.deterministic_gate_ids) === canonical(GATE_IDS) && cycle.gate_receipt_sha256s.length === 3);
  check(`${claimId}: cycle receipt is self-hashed and provider-free`, exactSha(cycle, 'receipt_sha256', { loop: true })
    && cycle.model_calls === 0 && cycle.provider_calls === 0 && cycle.credential_access_status === 'none_due_to_zero_provider_calls'
    && cycle.cost_status === 'exact' && cycle.cost_usd === 0);
  check(`${claimId}: loop audit is exact zero-activity`, exactSha(view.audit, 'receipt_sha256', { loop: true })
    && view.audit.event_count === state.revision && view.audit.last_event_sha256 === state.last_event_sha256
    && view.audit.state_sha256 === state.state_sha256
    && view.audit.model_calls === 0 && view.audit.provider_calls === 0 && view.audit.provider_credentials_read === false
    && view.audit.cost_status === 'exact' && view.audit.cost_usd === 0);
  const expectedOutcome = state.phase === 'decision_ready' ? 'decision_ready'
    : state.phase === 'abstained' ? 'abstain'
      : state.phase === 'awaiting_observation' && state.selected_action ? 'next_action' : 'processing';
  const expectedTerminalMode = state.phase === 'decision_ready' ? 'finalize' : state.phase === 'abstained' ? 'abstain' : null;
  const packet = view.decision_packet;
  check(`${claimId}: loop reaches one honest safe state`, ['next_action', 'decision_ready', 'abstain'].includes(view.outcome)
    && view.outcome === expectedOutcome && state.terminal_mode === expectedTerminalMode
    && (view.outcome !== 'next_action' || Boolean(state.selected_action))
    && (['decision_ready', 'abstain'].includes(view.outcome) === Boolean(packet)));
  if (packet) {
    check(`${claimId}: terminal packet is exact and state-bound`, packet.contract === 'casepath.decision-ready-packet/1.0.0'
      && exactSha(packet, 'packet_sha256', { loop: true }) && packet.claim_id === claimId
      && packet.loop_id === state.loop_id && packet.source_state_sha256 === state.state_sha256
      && packet.phase === state.phase && packet.terminal_mode === state.terminal_mode
      && packet.six_agent_cycle_receipt_sha256 === cycle.receipt_sha256);
  }
  validateProjection(view.operational_projection, claimId, workspaceState, state);
  const journalSemantics = reconstructJournalSemantics(state);
  const productSemantics = projectionSemanticSlice(view.operational_projection);
  check(`${claimId}: product semantics equal an independent raw-journal reconstruction`,
    canonical(productSemantics) === canonical(journalSemantics.semantic_projection));
  return {
    claim_id: claimId,
    binding_sha256: workspaceState.binding.binding_sha256,
    workspace_prefix: view.operational_projection.workspace_prefix,
    claim_loop_prefix: view.operational_projection.claim_loop_prefix,
    view_sha256: view.view_sha256,
    operational_projection_sha256: view.operational_projection.projection_sha256,
    cycle_receipt_sha256: cycle.receipt_sha256,
    audit_receipt_sha256: view.audit.receipt_sha256,
    current_process: view.operational_projection.current_process,
    controlling_decision: view.operational_projection.controlling_decision,
    evidence_class_counts: view.operational_projection.evidence_class_counts,
    outcome: view.outcome,
    next_state: view.operational_projection.next_state,
    terminal_packet_sha256: view.decision_packet?.packet_sha256 || null,
    journal_semantics: journalSemantics,
    product_semantics: productSemantics,
  };
}

async function queueAll(parameters = {}) {
  const base = new URLSearchParams({ ...parameters, limit: String(parameters.limit || 17) });
  let cursor = null;
  let expectedTotal = null;
  const items = [];
  do {
    const query = new URLSearchParams(base);
    if (cursor) query.set('cursor', cursor);
    const page = await api(`/api/claim-loops/v1/workspace/claims?${query}`);
    check(`queue ${canonical(parameters)}: page is self-hashed`, page.contract === 'casepath.claim-queue-projection/2.0.0' && exactSha(page, 'projection_sha256'));
    expectedTotal ??= page.total_count;
    check(`queue ${canonical(parameters)}: snapshot count stays fixed`, page.total_count === expectedTotal);
    for (const row of page.items) {
      check(`${row.claim_id}: queue row is self-hashed`, exactSha(row, 'row_sha256'));
      validateProjection(row.operational_projection, row.claim_id, {
        loop_id: row.operational_projection.workspace_prefix.loop_id,
        revision: row.revision,
        state_sha256: row.state_sha256,
        last_event_sha256: row.operational_projection.workspace_prefix.last_event_sha256,
      });
      items.push(row);
    }
    cursor = page.next_cursor;
  } while (cursor);
  check(`queue ${canonical(parameters)}: pagination is complete and disjoint`, items.length === expectedTotal && new Set(items.map(row => row.claim_id)).size === items.length);
  return items;
}

function queueRowsByClaim(rows) {
  return new Map(rows.map(row => [row.claim_id, row]));
}

function queueRosterSha256(rows, excludedClaimId = null) {
  return sha(rows
    .filter(row => row.claim_id !== excludedClaimId)
    .sort((left, right) => left.claim_id.localeCompare(right.claim_id)));
}

function compareTuple(left, right) {
  for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
    if (left[index] < right[index]) return -1;
    if (left[index] > right[index]) return 1;
  }
  return 0;
}
function sortKey(row, mode) {
  const tuple = Object.fromEntries(row.priority_tuple.map(value => [value.dimension, value.value]));
  const readinessRank = { decision_ready: 3, safe_abstention: 2, blocked: 1, not_assessed: 0 }[row.readiness_state];
  const urgencyRank = { high: 3, elevated: 2, normal: 1 }[row.urgency];
  if (mode === 'priority') return [tuple.safety, row.deadline_at || '9999-12-31T23:59:59+00:00', tuple.failed_or_unknown_effect, tuple.unresolved_critical_obligation, -tuple.waiting_age_days, 1, -readinessRank, row.claim_id];
  if (mode === 'urgency') return [-urgencyRank, row.received_at, row.claim_id];
  if (mode === 'oldest_waiting') return [row.received_at, row.claim_id];
  if (mode === 'nearest_deadline') return [row.deadline_at || '9999-12-31T23:59:59+00:00', row.received_at, row.claim_id];
  if (mode === 'most_decision_ready') return [-readinessRank, row.received_at, row.claim_id];
  if (mode === 'latest_update') return [-Date.parse(row.last_authoritative_update), row.claim_id];
  throw new Error(`unknown sort ${mode}`);
}

function parseEmbeddedSeedReceipt(snapshot, labelName) {
  const encoded = snapshot.apiBootReceipt?.attestation?.workspace_seed_receipt_base64;
  const bytes = Buffer.from(encoded || '', 'base64');
  let wrapper;
  try { wrapper = JSON.parse(bytes.toString('utf8')); } catch (_) { throw new Error(`${labelName}: embedded seed receipt is not JSON`); }
  check(`${labelName}: embedded seed wrapper and receipt are exact`, bytes.toString('base64') === encoded
    && sha(bytes) === snapshot.apiBootReceipt.attestation.workspace_seed_receipt_file_sha256
    && hasExactKeys(wrapper, ['contract', 'seed_receipt', 'source_authority', 'receipt_sha256'])
    && wrapper.contract === 'casepath.sealed-workspace-seed/1.0.0'
    && exactSha(wrapper, 'receipt_sha256')
    && hasExactKeys(wrapper.seed_receipt, ['contract', 'corpus_identity', 'claim_count', 'new_import_count', 'replayed_import_count', 'event_roster_sha256', 'timestamp', 'model_calls', 'provider_calls', 'credential_reads', 'cost_usd', 'receipt_sha256'])
    && wrapper.seed_receipt.contract === 'casepath.claim-workspace-seed/1.0.0'
    && exactSha(wrapper.seed_receipt, 'receipt_sha256')
    && wrapper.seed_receipt.claim_count === 150
    && wrapper.seed_receipt.new_import_count + wrapper.seed_receipt.replayed_import_count === 150
    && ['model_calls', 'provider_calls', 'credential_reads', 'cost_usd'].every(field => wrapper.seed_receipt[field] === 0));
  return wrapper.seed_receipt;
}

async function readRawJournalRows(databasePath) {
  const sql = `SELECT session_id,loop_id,sequence,idempotency_key,command_sha256,event_sha256,event_json,created_at
    FROM claim_loop_events
    WHERE session_id IN ('${WORKSPACE_SESSION_ID}','${CLAIM_LOOP_SESSION_ID}')
    ORDER BY session_id,loop_id,sequence`;
  const { stdout, stderr } = await execFileAsync('/usr/bin/sqlite3', ['-readonly', '-json', databasePath, sql], {
    encoding: 'utf8',
    maxBuffer: 256 * 1024 * 1024,
  });
  if (stderr.trim()) throw new Error(`sqlite raw journal read emitted stderr: ${stderr.trim()}`);
  return JSON.parse(stdout || '[]').map(row => ({ ...row, event: JSON.parse(row.event_json) }));
}

async function snapshotRegularFiles(root) {
  const files = [];
  async function visit(directory) {
    for (const entry of (await fs.readdir(directory, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
      const absolute = path.join(directory, entry.name);
      const metadata = await fs.lstat(absolute);
      if (metadata.isSymbolicLink()) throw new Error(`authority snapshot contains a symlink: ${absolute}`);
      if (metadata.isDirectory()) await visit(absolute);
      else if (metadata.isFile()) {
        const bytes = await fs.readFile(absolute);
        files.push({ relative_path: path.relative(root, absolute), sha256: sha(bytes), size_bytes: bytes.length });
      } else throw new Error(`authority snapshot contains a special entry: ${absolute}`);
    }
  }
  await visit(root);
  return files;
}

const ADMITTED_AUTHORITY_KINDS = Object.freeze([
  'intents',
  'source-blobs',
  'acquisitions',
  'acquisition-by-intent',
  'claim-content-registry',
  'registrations',
  'proposals',
  'proposal-by-acquisition',
  'admissions',
  'admission-by-interpretation',
  'outcome-by-acquisition',
]);

function authorityPath(kind, ...parts) {
  return path.join('authority-v3', kind, ...parts);
}

async function readAuthorityDeltaResource(root, rowByPath, usedPaths, relativePath, kind) {
  const row = rowByPath.get(relativePath);
  if (!row || usedPaths.has(relativePath)) {
    throw new Error(`Gate 2 authority resource is absent or duplicated: ${relativePath}`);
  }
  const bytes = await fs.readFile(path.join(root, relativePath));
  if (bytes.length !== row.size_bytes || sha(bytes) !== row.sha256) {
    throw new Error(`Gate 2 authority resource bytes differ: ${relativePath}`);
  }
  usedPaths.add(relativePath);
  if (kind === 'source-blobs') return { row, bytes, value: null };
  let value;
  try { value = JSON.parse(bytes.toString('utf8')); } catch (_) {
    throw new Error(`Gate 2 authority JSON is malformed: ${relativePath}`);
  }
  const hashField = kind === 'proposals' ? 'proposal_sha256' : 'receipt_sha256';
  if (bytes.toString('utf8') !== canonical(value)
    || value[hashField] !== sha(without(value, hashField))) {
    throw new Error(`Gate 2 authority JSON is not canonical/self-hashed: ${relativePath}`);
  }
  return { row, bytes, value };
}

async function readRecordedAuthorityResource(root, relativePath, kind) {
  const absolute = path.join(root, relativePath);
  const metadata = await fs.lstat(absolute);
  if (!metadata.isFile() || metadata.isSymbolicLink()) {
    throw new Error(`Independent replay authority resource is not a regular file: ${relativePath}`);
  }
  const bytes = await fs.readFile(absolute);
  if (kind === 'source-blobs') return { bytes, value: null };
  let value;
  try { value = JSON.parse(bytes.toString('utf8')); } catch (_) {
    throw new Error(`Independent replay authority JSON is malformed: ${relativePath}`);
  }
  const hashField = kind === 'proposals' ? 'proposal_sha256' : 'receipt_sha256';
  if (bytes.toString('utf8') !== canonical(value)
    || value[hashField] !== sha(without(value, hashField))) {
    throw new Error(`Independent replay authority JSON is not canonical/self-hashed: ${relativePath}`);
  }
  return { bytes, value };
}

async function loadIndependentAuthorityPrimitives(root, rawRows, executionRoot) {
  const expectedInterpreterSourceSha256 = sha(await fs.readFile(path.join(
    executionRoot, 'casepath-api/casepath_api/workspace_evidence_authority_v1.py',
  )));
  const expectedAuthoritySourceSha256 = sha(await fs.readFile(path.join(
    executionRoot, 'casepath-api/casepath_api/workspace_evidence_independent_authority_v1.py',
  )));
  const claimByLoopId = new Map(rawRows
    .filter(row => row.session_id === CLAIM_LOOP_SESSION_ID && row.event.event_type === 'LOOP_CREATED')
    .map(row => [row.loop_id, row.event.command.claim_id]));
  const byAcquisition = new Map();
  for (const row of rawRows.filter(value => (
    value.session_id === CLAIM_LOOP_SESSION_ID
      && ['OBSERVATION_INGESTED', 'EVIDENCE_PROPOSAL_REJECTED'].includes(value.event.event_type)
  ))) {
    const claimId = claimByLoopId.get(row.loop_id);
    const rejected = row.event.event_type === 'EVIDENCE_PROPOSAL_REJECTED';
    const artifact = rejected ? null : row.event.command.tool_artifact_receipt;
    const acquisition = rejected ? row.event.command.acquisition_receipt : artifact.acquisition_receipt;
    const binding = rejected ? null : row.event.command.evidence_authority_binding;
    const parts = acquisition.source_locator.split(':');
    if (!claimId || parts.length !== 4 || parts[0] !== 'loopback-source-span') {
      throw new Error(`${claimId || row.loop_id}: independent replay acquisition locator is invalid`);
    }
    const [, intentId, sourceAcquisitionId] = parts;
    const intent = (await readRecordedAuthorityResource(
      root, authorityPath('intents', `${sha(intentId)}.json`), 'intents',
    )).value;
    const sourceAcquisition = (await readRecordedAuthorityResource(
      root, authorityPath('acquisitions', `${sha(sourceAcquisitionId)}.json`), 'acquisitions',
    )).value;
    const acquisitionIndex = (await readRecordedAuthorityResource(
      root,
      authorityPath('acquisition-by-intent', `${sha(intentId)}.json`),
      'acquisition-by-intent',
    )).value;
    const sourceBlob = await readRecordedAuthorityResource(
      root,
      authorityPath('source-blobs', sha(claimId), `${sourceAcquisition.content_sha256}.bin`),
      'source-blobs',
    );
    const claimRegistry = (await readRecordedAuthorityResource(
      root,
      authorityPath(
        'claim-content-registry',
        sha(claimId),
        `${sourceAcquisition.content_sha256}.json`,
      ),
      'claim-content-registry',
    )).value;
    const registrationIdentity = sha({
      contract: 'casepath.workspace-evidence-registration-resource/1.0.0',
      session_id: sourceAcquisition.session_id,
      loop_id: sourceAcquisition.loop_id,
      parent_revision: sourceAcquisition.expected_revision,
      action_sha256: sourceAcquisition.action_sha256,
    });
    const registration = (await readRecordedAuthorityResource(
      root, authorityPath('registrations', `${registrationIdentity}.json`), 'registrations',
    )).value;
    const outcome = (await readRecordedAuthorityResource(
      root,
      authorityPath('outcome-by-acquisition', `${acquisition.receipt_sha256}.json`),
      'outcome-by-acquisition',
    )).value;
    const common = {
      intent,
      source_acquisition: sourceAcquisition,
      acquisition_index: acquisitionIndex,
      claim_registry: claimRegistry,
      registration,
      outcome,
      source_blob_base64: sourceBlob.bytes.toString('base64'),
      expected_interpreter_source_sha256: expectedInterpreterSourceSha256,
      expected_authority_source_sha256: expectedAuthoritySourceSha256,
    };
    if (byAcquisition.has(acquisition.receipt_sha256)) {
      throw new Error(`${claimId}: independent replay authority chain is ambiguous`);
    }
    if (rejected) {
      const rejectionIndex = (await readRecordedAuthorityResource(
        root,
        authorityPath('rejection-by-acquisition', `${acquisition.receipt_sha256}.json`),
        'rejection-by-acquisition',
      )).value;
      const rejection = (await readRecordedAuthorityResource(
        root, authorityPath('rejections', `${rejectionIndex.rejection_receipt_sha256}.json`), 'rejections',
      )).value;
      if (canonical(row.event.command.authority_rejection_receipt) !== canonical(rejection)
        || row.event.command.authority_rejection_receipt_sha256 !== rejection.receipt_sha256
        || outcome.decision !== 'rejected'
        || outcome.authority_receipt_sha256 !== rejection.receipt_sha256) {
        throw new Error(`${claimId}: independent replay rejection authority differs`);
      }
      byAcquisition.set(acquisition.receipt_sha256, {
        ...common,
        decision:'rejected',
        rejection_index:rejectionIndex,
        rejection,
      });
    } else {
      const proposalIndex = (await readRecordedAuthorityResource(
        root,
        authorityPath('proposal-by-acquisition', `${acquisition.receipt_sha256}.json`),
        'proposal-by-acquisition',
      )).value;
      const proposal = (await readRecordedAuthorityResource(
        root, authorityPath('proposals', `${proposalIndex.proposal_sha256}.json`), 'proposals',
      )).value;
      const admissionIndex = (await readRecordedAuthorityResource(
        root,
        authorityPath('admission-by-interpretation', `${artifact.interpretation.receipt_sha256}.json`),
        'admission-by-interpretation',
      )).value;
      const admission = (await readRecordedAuthorityResource(
        root, authorityPath('admissions', `${admissionIndex.admission_receipt_sha256}.json`), 'admissions',
      )).value;
      if (binding.proposal_sha256 !== proposal.proposal_sha256
        || binding.admission_receipt_sha256 !== admission.receipt_sha256) {
        throw new Error(`${claimId}: independent replay admission authority differs`);
      }
      byAcquisition.set(acquisition.receipt_sha256, {
        ...common,
        decision:'admitted',
        proposal_index: proposalIndex,
        proposal,
        admission_index: admissionIndex,
        admission,
      });
    }
  }
  return byAcquisition;
}

async function auditGate2AuthorityDelta({
  root,
  delta,
  seams,
  sidecars,
  rawJournalRows,
  carryoverClaimIds,
}) {
  const carryoverSet = new Set(carryoverClaimIds);
  const actionable = seams.filter(row => !carryoverSet.has(row.claim_id));
  const rowByPath = new Map(delta.map(row => [row.relative_path, row]));
  const kindCounts = Object.fromEntries(ADMITTED_AUTHORITY_KINDS.map(kind => [kind, 0]));
  for (const row of delta) {
    const parts = row.relative_path.split('/');
    const kind = parts[0] === 'authority-v3' ? parts[1] : null;
    if (!(kind in kindCounts)) {
      throw new Error(`Gate 2 authority delta has a forbidden kind: ${row.relative_path}`);
    }
    kindCounts[kind] += 1;
  }
  if (delta.length !== actionable.length * ADMITTED_AUTHORITY_KINDS.length
    || !ADMITTED_AUTHORITY_KINDS.every(kind => kindCounts[kind] === actionable.length)) {
    throw new Error('Gate 2 authority delta kind cardinalities differ');
  }

  const usedPaths = new Set();
  const auditRows = [];
  for (const seam of actionable) {
    const claimId = seam.claim_id;
    const intent = seam.intent_response.intent;
    const sourceAcquisition = seam.acquisition_response.acquisition_receipt;
    const registration = seam.registration_response.stage_receipt;
    const sourceBytes = Buffer.from(seam.acquisition_response.content_b64, 'base64');
    const observationRows = rawJournalRows.filter(row => row.event.event_type === 'OBSERVATION_INGESTED'
      && row.event.command?.tool_artifact_receipt?.acquisition_receipt?.loop_id === sourceAcquisition.loop_id);
    const acquisitionRows = sidecars.filter(row => row.kind === 'acquisition'
      && row.loop_id === sourceAcquisition.loop_id);
    const artifactRows = sidecars.filter(row => row.kind === 'tool_artifact'
      && row.loop_id === sourceAcquisition.loop_id);
    if (observationRows.length !== 1 || acquisitionRows.length !== 1 || artifactRows.length !== 1) {
      throw new Error(`${claimId}: Gate 2 journal/sidecar authority is not one-to-one`);
    }
    const observationCommand = observationRows[0].event.command;
    const acquisitionSidecar = acquisitionRows[0];
    const artifactSidecar = artifactRows[0];
    const artifact = observationCommand.tool_artifact_receipt;
    const authorityBinding = observationCommand.evidence_authority_binding;
    if (canonical(artifactSidecar.payload) !== canonical(artifact)
      || canonical(acquisitionSidecar.payload) !== canonical(artifact.acquisition_receipt)
      || acquisitionSidecar.receipt_sha256 !== artifact.acquisition_receipt.receipt_sha256
      || artifactSidecar.receipt_sha256 !== artifact.receipt_sha256
      || observationCommand.artifact_receipt_sha256 !== artifact.receipt_sha256
      || artifact.interpretation.receipt_sha256 !== authorityBinding.interpretation_receipt_sha256
      || Buffer.compare(Buffer.from(acquisitionSidecar.raw_payload_hex, 'hex'), sourceBytes) !== 0) {
      throw new Error(`${claimId}: Gate 2 SQLite and journal sidecars differ`);
    }

    const intentResource = await readAuthorityDeltaResource(
      root, rowByPath, usedPaths,
      authorityPath('intents', `${sha(intent.intent_id)}.json`), 'intents',
    );
    const blobResource = await readAuthorityDeltaResource(
      root, rowByPath, usedPaths,
      authorityPath('source-blobs', sha(claimId), `${sourceAcquisition.content_sha256}.bin`),
      'source-blobs',
    );
    const acquisitionResource = await readAuthorityDeltaResource(
      root, rowByPath, usedPaths,
      authorityPath('acquisitions', `${sha(sourceAcquisition.acquisition_receipt_id)}.json`),
      'acquisitions',
    );
    const acquisitionIndexResource = await readAuthorityDeltaResource(
      root, rowByPath, usedPaths,
      authorityPath('acquisition-by-intent', `${sha(intent.intent_id)}.json`),
      'acquisition-by-intent',
    );
    const claimRegistryResource = await readAuthorityDeltaResource(
      root, rowByPath, usedPaths,
      authorityPath('claim-content-registry', sha(claimId), `${sourceAcquisition.content_sha256}.json`),
      'claim-content-registry',
    );
    const registrationIdentity = sha({
      contract: 'casepath.workspace-evidence-registration-resource/1.0.0',
      session_id: registration.session_id,
      loop_id: registration.loop_id,
      parent_revision: registration.parent_revision,
      action_sha256: registration.action_sha256,
    });
    const registrationResource = await readAuthorityDeltaResource(
      root, rowByPath, usedPaths,
      authorityPath('registrations', `${registrationIdentity}.json`), 'registrations',
    );
    const proposalIndexResource = await readAuthorityDeltaResource(
      root, rowByPath, usedPaths,
      authorityPath(
        'proposal-by-acquisition',
        `${acquisitionSidecar.receipt_sha256}.json`,
      ),
      'proposal-by-acquisition',
    );
    const proposalSha256 = proposalIndexResource.value.proposal_sha256;
    const proposalResource = await readAuthorityDeltaResource(
      root, rowByPath, usedPaths,
      authorityPath('proposals', `${proposalSha256}.json`), 'proposals',
    );
    const admissionIndexResource = await readAuthorityDeltaResource(
      root, rowByPath, usedPaths,
      authorityPath(
        'admission-by-interpretation',
        `${authorityBinding.interpretation_receipt_sha256}.json`,
      ),
      'admission-by-interpretation',
    );
    const admissionSha256 = admissionIndexResource.value.admission_receipt_sha256;
    const admissionResource = await readAuthorityDeltaResource(
      root, rowByPath, usedPaths,
      authorityPath('admissions', `${admissionSha256}.json`), 'admissions',
    );
    const outcomeResource = await readAuthorityDeltaResource(
      root, rowByPath, usedPaths,
      authorityPath(
        'outcome-by-acquisition',
        `${acquisitionSidecar.receipt_sha256}.json`,
      ),
      'outcome-by-acquisition',
    );

    const acquisitionIndex = acquisitionIndexResource.value;
    const claimRegistry = claimRegistryResource.value;
    const proposal = proposalResource.value;
    const admissionIndex = admissionIndexResource.value;
    const admission = admissionResource.value;
    const outcome = outcomeResource.value;
    const resourceBindingsExact = canonical(intentResource.value) === canonical(intent)
      && canonical(acquisitionResource.value) === canonical(sourceAcquisition)
      && canonical(registrationResource.value) === canonical(registration)
      && Buffer.compare(blobResource.bytes, sourceBytes) === 0
      && sourceBytes.length === sourceAcquisition.content_length
      && sha(sourceBytes) === sourceAcquisition.content_sha256
      && acquisitionIndex.contract === 'casepath.workspace-acquisition-intent-index/1.0.0'
      && acquisitionIndex.acquisition_intent_id === intent.intent_id
      && acquisitionIndex.acquisition_receipt_id === sourceAcquisition.acquisition_receipt_id
      && acquisitionIndex.source_acquisition_receipt_sha256 === sourceAcquisition.receipt_sha256
      && claimRegistry.contract === 'casepath.workspace-claim-content-first-seen/1.0.0'
      && claimRegistry.claim_id === claimId
      && claimRegistry.content_sha256 === sourceAcquisition.content_sha256
      && claimRegistry.acquisition_intent_id === intent.intent_id
      && claimRegistry.intent_receipt_sha256 === intent.receipt_sha256
      && claimRegistry.claim_registry_watermark_sha256 === intent.claim_registry_watermark_sha256
      && claimRegistry.source_entry_sha256 === sourceAcquisition.source_entry_sha256
      && claimRegistry.receipt_sha256 === sourceAcquisition.claim_first_seen_receipt_sha256
      && proposalIndexResource.value.contract === 'casepath.workspace-proposal-acquisition-index/1.0.0'
      && proposalIndexResource.value.acquisition_receipt_sha256 === acquisitionSidecar.receipt_sha256
      && proposalIndexResource.value.proposal_sha256 === proposal.proposal_sha256
      && proposal.proposal_sha256 === proposalSha256
      && proposal.claim_id === claimId
      && proposal.acquisition_receipt_sha256 === acquisitionSidecar.receipt_sha256
      && proposal.source_acquisition_receipt_sha256 === sourceAcquisition.receipt_sha256
      && proposal.registration_receipt_sha256 === registration.receipt_sha256
      && proposal.intent_receipt_sha256 === intent.receipt_sha256
      && proposal.interpretation_receipt_sha256 === artifact.interpretation.receipt_sha256
      && admissionIndex.contract === 'casepath.workspace-admission-interpretation-index/1.0.0'
      && admissionIndex.interpretation_receipt_sha256 === artifact.interpretation.receipt_sha256
      && admissionIndex.admission_receipt_sha256 === admission.receipt_sha256
      && admission.receipt_sha256 === admissionSha256
      && admission.proposal_sha256 === proposal.proposal_sha256
      && admission.acquisition_receipt_sha256 === acquisitionSidecar.receipt_sha256
      && admission.source_acquisition_receipt_sha256 === sourceAcquisition.receipt_sha256
      && admission.registration_receipt_sha256 === registration.receipt_sha256
      && admission.interpretation_receipt_sha256 === artifact.interpretation.receipt_sha256
      && admission.decision === 'admitted'
      && outcome.contract === 'casepath.workspace-authority-outcome-index/1.0.0'
      && outcome.acquisition_receipt_sha256 === acquisitionSidecar.receipt_sha256
      && outcome.authority_receipt_sha256 === admission.receipt_sha256
      && outcome.decision === 'admitted'
      && authorityBinding.proposal_sha256 === proposal.proposal_sha256
      && authorityBinding.admission_receipt_sha256 === admission.receipt_sha256
      && authorityBinding.acquisition_receipt_sha256 === acquisitionSidecar.receipt_sha256
      && authorityBinding.registration_receipt_sha256 === registration.receipt_sha256
      && authorityBinding.binding_sha256 === sha(without(authorityBinding, 'binding_sha256'));
    if (!resourceBindingsExact) {
      throw new Error(`${claimId}: Gate 2 authority resource chain differs`);
    }
    auditRows.push({
      contract: 'casepath.gate2-authority-chain-audit/1.0.0',
      claim_id: claimId,
      loop_id: sourceAcquisition.loop_id,
      intent_receipt_sha256: intent.receipt_sha256,
      source_acquisition_receipt_sha256: sourceAcquisition.receipt_sha256,
      content_sha256: sourceAcquisition.content_sha256,
      registration_receipt_sha256: registration.receipt_sha256,
      generic_acquisition_receipt_sha256: acquisitionSidecar.receipt_sha256,
      tool_artifact_receipt_sha256: artifactSidecar.receipt_sha256,
      proposal_sha256: proposal.proposal_sha256,
      interpretation_receipt_sha256: artifact.interpretation.receipt_sha256,
      admission_receipt_sha256: admission.receipt_sha256,
      authority_binding_sha256: authorityBinding.binding_sha256,
      outcome_receipt_sha256: outcome.receipt_sha256,
      authority_path_roster_sha256: sha([
        intentResource.row.relative_path,
        blobResource.row.relative_path,
        acquisitionResource.row.relative_path,
        acquisitionIndexResource.row.relative_path,
        claimRegistryResource.row.relative_path,
        registrationResource.row.relative_path,
        proposalResource.row.relative_path,
        proposalIndexResource.row.relative_path,
        admissionResource.row.relative_path,
        admissionIndexResource.row.relative_path,
        outcomeResource.row.relative_path,
      ].sort()),
    });
  }
  if (usedPaths.size !== delta.length || auditRows.length !== actionable.length) {
    throw new Error('Gate 2 authority resource coverage is incomplete');
  }
  const receiptMaterial = {
    contract: 'casepath.gate2-authority-delta-audit/1.0.0',
    claim_count: auditRows.length,
    used_path_count: usedPaths.size,
    kind_counts: kindCounts,
    chain_roster_sha256: sha(auditRows),
    path_roster_sha256: sha([...usedPaths].sort()),
  };
  return {
    auditRows,
    kindCounts,
    usedPathCount: usedPaths.size,
    receipt: { ...receiptMaterial, receipt_sha256: sha(receiptMaterial) },
  };
}

async function readAuthoritySidecars(databasePath) {
  const sql = `SELECT 'acquisition' AS kind,receipt_sha256,session_id,loop_id,action_id,dispatch_sha256,status,
      acquisition_json AS payload_json,hex(raw_payload) AS raw_payload_hex,created_at
    FROM claim_loop_acquisitions
    UNION ALL
    SELECT 'tool_artifact' AS kind,receipt_sha256,session_id,loop_id,action_id,dispatch_sha256,NULL AS status,
      artifact_json AS payload_json,NULL AS raw_payload_hex,created_at
    FROM claim_loop_tool_artifacts
    ORDER BY kind,loop_id,created_at,receipt_sha256`;
  const { stdout, stderr } = await execFileAsync('/usr/bin/sqlite3', ['-readonly', '-json', databasePath, sql], {
    encoding: 'utf8',
    maxBuffer: 256 * 1024 * 1024,
  });
  if (stderr.trim()) throw new Error(`sqlite authority-sidecar read emitted stderr: ${stderr.trim()}`);
  return JSON.parse(stdout || '[]').map(row => ({ ...row, payload: JSON.parse(row.payload_json) }));
}

async function auditRawJournals(databasePath, claimIds) {
  const database = await fs.lstat(databasePath);
  check('Raw journal audit uses the exact regular runtime database', database.isFile() && !database.isSymbolicLink()
    && path.resolve(databasePath) === databasePath);
  const rows = await readRawJournalRows(databasePath);
  const journals = new Map();
  for (const row of rows) {
    const key = `${row.session_id}\u0000${row.loop_id}`;
    if (!journals.has(key)) journals.set(key, []);
    journals.get(key).push(row);
  }
  const roster = new Set(claimIds);
  const workspaceByClaim = new Map();
  const claimLoopByClaim = new Map();
  let duplicateEffectCount = 0;
  let chainValid = true;
  for (const events of journals.values()) {
    const sessionId = events[0].session_id;
    const expectedContracts = sessionId === WORKSPACE_SESSION_ID
      ? new Set([WORKSPACE_EVENT_CONTRACT])
      : new Set([CLAIM_LOOP_EVENT_CONTRACT, 'casepath.claim-loop-protocol-event/1.0.0', 'casepath.claim-loop-protocol-event/2.0.0']);
    const effectKeys = new Set();
    const idempotencyKeys = new Set();
    const eventHashes = new Set();
    let previous = null;
    for (let index = 0; index < events.length; index += 1) {
      const row = events[index];
      const event = row.event;
      const eventMaterial = without(without(event, 'event_sha256'), 'resulting_state_sha256');
      const digest = sessionId === CLAIM_LOOP_SESSION_ID ? claimLoopSha : sha;
      const valid = hasExactKeys(event, ['contract','session_id','loop_id','sequence','previous_event_sha256','event_type','idempotency_key','command_sha256','command','created_at','event_sha256','resulting_state_sha256'])
        && expectedContracts.has(event.contract)
        && event.session_id === row.session_id && event.loop_id === row.loop_id
        && event.sequence === row.sequence && row.sequence === index + 1
        && event.previous_event_sha256 === previous
        && event.idempotency_key === row.idempotency_key
        && event.command_sha256 === row.command_sha256
        && event.event_sha256 === row.event_sha256
        && event.created_at === row.created_at
        && event.command_sha256 === digest(event.command)
        && event.event_sha256 === digest(eventMaterial)
        && row.event_json === (sessionId === CLAIM_LOOP_SESSION_ID
          ? claimLoopCanonical(event) : canonical(event))
        && /^[0-9a-f]{64}$/.test(event.resulting_state_sha256);
      chainValid &&= valid;
      previous = event.event_sha256;
      const duplicate = effectKeys.has(event.resulting_state_sha256)
        || idempotencyKeys.has(event.idempotency_key) || eventHashes.has(event.event_sha256);
      if (duplicate) duplicateEffectCount += 1;
      effectKeys.add(event.resulting_state_sha256);
      idempotencyKeys.add(event.idempotency_key);
      eventHashes.add(event.event_sha256);
    }
    const first = events[0].event;
    if (sessionId === WORKSPACE_SESSION_ID) {
      const claimId = events[0].loop_id.startsWith('workspace.') ? events[0].loop_id.slice('workspace.'.length) : null;
      if (claimId && roster.has(claimId)) workspaceByClaim.set(claimId, events);
      chainValid &&= first.event_type === 'WORKSPACE_CLAIM_IMPORTED';
    } else {
      const claimId = first.command?.claim_id || first.command?.accepted_artifacts?.claim_id || null;
      if (claimId && roster.has(claimId)) claimLoopByClaim.set(claimId, events);
      chainValid &&= first.event_type === 'LOOP_CREATED';
    }
  }
  const allWorkspaceJournals = [...journals.values()].filter(events => events[0].session_id === WORKSPACE_SESSION_ID);
  const allClaimLoopJournals = [...journals.values()].filter(events => events[0].session_id === CLAIM_LOOP_SESSION_ID);
  const perClaim = Object.fromEntries(claimIds.map(claimId => {
    const workspaceEvents = workspaceByClaim.get(claimId) || [];
    const loopEvents = claimLoopByClaim.get(claimId) || [];
    return [claimId, {
      workspace_loop_id: workspaceEvents[0]?.loop_id || null,
      workspace_event_count: workspaceEvents.length,
      workspace_event_types: workspaceEvents.map(row => row.event.event_type),
      workspace_import_count: workspaceEvents.filter(row => row.event.event_type === 'WORKSPACE_CLAIM_IMPORTED').length,
      workspace_final_state_sha256: workspaceEvents.at(-1)?.event.resulting_state_sha256 || null,
      claim_loop_id: loopEvents[0]?.loop_id || null,
      claim_loop_event_count: loopEvents.length,
      claim_loop_event_types: loopEvents.map(row => row.event.event_type),
      claim_loop_create_count: loopEvents.filter(row => row.event.event_type === 'LOOP_CREATED').length,
      claim_loop_final_state_sha256: loopEvents.at(-1)?.event.resulting_state_sha256 || null,
    }];
  }));
  const duplicateLifecycleCount = Object.values(perClaim).reduce((sum, value) => sum
    + Math.max(0, value.workspace_import_count - 1) + Math.max(0, value.claim_loop_create_count - 1), 0);
  check('All 300 raw journals have exact, contiguous, self-hashed event chains', chainValid
    && journals.size === 300 && allWorkspaceJournals.length === 150 && allClaimLoopJournals.length === 150,
  canonical({ journals: journals.size, workspace: allWorkspaceJournals.length, claim_loops: allClaimLoopJournals.length }));
  check('Raw journal lifecycle roster is exactly the 150 public claims', workspaceByClaim.size === 150
    && claimLoopByClaim.size === 150
    && canonical([...workspaceByClaim.keys()].sort()) === canonical(claimIds)
    && canonical([...claimLoopByClaim.keys()].sort()) === canonical(claimIds));
  check('Every raw claim journal has exactly one initial lifecycle and no duplicate effect', duplicateLifecycleCount === 0
    && duplicateEffectCount === 0
    && Object.values(perClaim).every(value => value.workspace_import_count === 1 && value.claim_loop_create_count === 1));
  return {
    database_path: databasePath,
    observed_event_count: rows.length,
    workspace_loop_count: allWorkspaceJournals.length,
    claim_loop_count: allClaimLoopJournals.length,
    workspace_import_count: Object.values(perClaim).reduce((sum, value) => sum + value.workspace_import_count, 0),
    claim_loop_create_count: Object.values(perClaim).reduce((sum, value) => sum + value.claim_loop_create_count, 0),
    duplicate_lifecycle_count: duplicateLifecycleCount,
    duplicate_effect_count: duplicateEffectCount,
    per_claim: perClaim,
    raw_rows: rows,
  };
}

function replayWorkspaceEvents(events, claimId) {
  let state = null;
  const effects = [];
  for (const row of events) {
    const event = row.event;
    const command = event.command;
    if (state === null) {
      if (event.event_type !== 'WORKSPACE_CLAIM_IMPORTED' || event.sequence !== 1) {
        throw new Error(`${claimId}: independent workspace replay lacks its import`);
      }
      const binding = structuredClone(command.binding);
      const material = {
        contract: 'casepath.claim-workspace-state/1.0.0',
        claim_id: binding.claim_id,
        loop_id: `workspace.${claimId}`,
        binding,
        static_template_sha256: binding.static_template_sha256,
        intake_assessment: null,
        owner: null,
        workflow_state: 'received',
        readiness_state: 'not_assessed',
        claim_type: 'unclassified_intake',
        deadline_at: null,
        principal_blocker: 'Deterministic assessment has not started',
        pending_evidence_count: null,
        next_safe_action: 'Start deterministic assessment',
        failure_or_unknown_effect: false,
        revision: event.sequence,
        last_event_sha256: event.event_sha256,
        last_authoritative_update: event.created_at,
      };
      state = { ...material, state_sha256: sha(material) };
    } else {
      const material = without(state, 'state_sha256');
      material.revision = event.sequence;
      material.last_event_sha256 = event.event_sha256;
      material.last_authoritative_update = event.created_at;
      if (event.event_type === 'WORKSPACE_OWNER_ASSIGNED') {
        material.owner = command.owner.trim();
      } else if (event.event_type === 'WORKSPACE_PROCESSING_STARTED') {
        const assessment = structuredClone(command.intake_assessment);
        const node = assessment.current_node;
        Object.assign(material, {
          workflow_state: 'in_review',
          readiness_state: 'blocked',
          claim_type: assessment.claim_type,
          intake_assessment: assessment,
          principal_blocker: `${node.label} is not yet established from admitted evidence`,
          next_safe_action: node.label,
        });
      } else if (event.event_type === 'WORKSPACE_UNKNOWN_RECONCILED') {
        Object.assign(material, {
          failure_or_unknown_effect: false,
          workflow_state: 'waiting',
          principal_blocker: 'Unknown effect reconciled; review required',
          next_safe_action: 'Resume deterministic assessment',
        });
      } else {
        throw new Error(`${claimId}: independent workspace replay saw ${event.event_type}`);
      }
      state = { ...material, state_sha256: sha(material) };
    }
    check(`${claimId}: independent workspace replay matches event ${event.sequence}`,
      state.state_sha256 === event.resulting_state_sha256);
    effects.push({
      claim_id: claimId,
      session_id: row.session_id,
      sequence: row.sequence,
      event_type: event.event_type,
      event_sha256: event.event_sha256,
      resulting_state_sha256: state.state_sha256,
      effect: event.event_type === 'WORKSPACE_CLAIM_IMPORTED' ? 'lifecycle_created'
        : event.event_type === 'WORKSPACE_PROCESSING_STARTED' ? 'intake_started'
          : event.event_type === 'WORKSPACE_OWNER_ASSIGNED' ? 'owner_changed' : 'unknown_effect_cleared',
    });
  }
  return { state, effects };
}

function acceptedArtifactsFromCreate(command) {
  const source = command.accepted_result;
  const keys = [
    'claim_id', 'facts', 'legal_research', 'process', 'checklist', 'verification',
    'next_action', 'agent_orchestration', 'playbook_template',
  ];
  const accepted = Object.fromEntries(keys.map(key => [key, structuredClone(source[key] ?? {})]));
  if (source.playbook_template_record !== undefined) accepted.playbook_template_record = structuredClone(source.playbook_template_record);
  if (source.observable_package !== undefined) accepted.observable_package = structuredClone(source.observable_package);
  return accepted;
}

function rawSourceRefId(value) {
  return `source-ref.${claimLoopSha(value)}`;
}

function deriveRawLoopProjection(events, claimId) {
  const created = events.find(row => row.event.event_type === 'LOOP_CREATED')?.event;
  if (!created) throw new Error(`${claimId}: independent loop replay lacks LOOP_CREATED`);
  const accepted = acceptedArtifactsFromCreate(created.command);
  let cycle = structuredClone(created.command.accepted_cycle_artifacts);
  const observations = [];
  const corrections = [];
  const history = [];
  const effects = [];
  const cycleReceipts = [created.command.six_agent_cycle_receipt];
  const artifactReceipts = [];
  let activeDispatch = null;
  for (const row of events) {
    const event = row.event;
    const command = event.command;
    if (event.event_type === 'ACTION_DISPATCH_STARTED') {
      activeDispatch = {
        event_sha256: event.event_sha256,
        action_id: command.action_id,
        action_sha256: command.action_sha256,
        adapter_id: command.adapter_id,
      };
      effects.push({
        claim_id: claimId,
        sequence: event.sequence,
        event_type: event.event_type,
        effect: 'dispatch_started',
        dispatch_sha256: event.event_sha256,
        action_sha256: command.action_sha256,
      });
    } else if (event.event_type === 'OBSERVATION_INGESTED') {
      const observation = command.observation;
      const receipt = command.tool_artifact_receipt;
      const authority = command.evidence_authority_binding;
      const nextCycle = command.accepted_cycle_artifacts;
      const beforeFacts = cycle.facts;
      const afterFacts = nextCycle.facts;
      const beforeTarget = beforeFacts.find(fact => fact.fact_id === observation.fact_id);
      const afterTarget = afterFacts.find(fact => fact.fact_id === observation.fact_id);
      const beforeUnrelated = beforeFacts.filter(fact => fact.fact_id !== observation.fact_id);
      const afterUnrelated = afterFacts.filter(fact => fact.fact_id !== observation.fact_id);
      check(`${claimId}: raw observation ${event.sequence} is self- and dispatch-bound`,
        observation.observation_sha256 === claimLoopSha(without(observation, 'observation_sha256'))
          && receipt.receipt_sha256 === claimLoopSha(without(receipt, 'receipt_sha256'))
          && receipt.action_id === activeDispatch?.action_id
          && receipt.action_sha256 === activeDispatch?.action_sha256
          && receipt.dispatch_sha256 === activeDispatch?.event_sha256
          && command.dispatch_sha256 === activeDispatch?.event_sha256
          && command.artifact_receipt_sha256 === receipt.receipt_sha256
          && authority.binding_sha256 === claimLoopSha(without(authority, 'binding_sha256'))
          && authority.interpretation_receipt_sha256 === receipt.interpretation.receipt_sha256
          && nextCycle.receipt_sha256 === claimLoopSha(without(nextCycle, 'receipt_sha256'))
          && canonical(beforeUnrelated) === canonical(afterUnrelated));
      observations.push(structuredClone(observation));
      history.push({ evidence_item_id: observation.evidence_item_id, outcome: 'observed' });
      artifactReceipts.push(receipt);
      cycleReceipts.push(command.six_agent_cycle_receipt);
      effects.push({
        claim_id: claimId,
        sequence: event.sequence,
        event_type: event.event_type,
        effect: 'one_observation_ingested',
        fact_id: observation.fact_id,
        evidence_item_id: observation.evidence_item_id,
        observation_sha256: observation.observation_sha256,
        before_fact_sha256: claimLoopSha(beforeTarget),
        after_fact_sha256: claimLoopSha(afterTarget),
        unrelated_facts_before_sha256: claimLoopSha(beforeUnrelated),
        unrelated_facts_after_sha256: claimLoopSha(afterUnrelated),
        authority_binding_sha256: authority.binding_sha256,
      });
      cycle = structuredClone(nextCycle);
      activeDispatch = null;
    } else if (event.event_type === 'CORRECTION_APPLIED') {
      const correction = command.correction;
      const correctionArtifact = command.correction_artifact_receipt;
      const nextCycle = command.accepted_cycle_artifacts;
      check(`${claimId}: raw correction ${event.sequence} is self-hashed and case-local`,
        correction.correction_sha256 === claimLoopSha(without(without(correction, 'correction_id'), 'correction_sha256'))
          && nextCycle.receipt_sha256 === claimLoopSha(without(nextCycle, 'receipt_sha256'))
          && correctionArtifact.receipt_sha256 === claimLoopSha(without(correctionArtifact, 'receipt_sha256'))
          && correctionArtifact.unrelated_facts_before_sha256 === correctionArtifact.unrelated_facts_after_sha256
          && canonical(command.after_semantics) === canonical(correction.effect));
      corrections.push(structuredClone(correction));
      cycleReceipts.push(command.six_agent_cycle_receipt);
      effects.push({
        claim_id: claimId,
        sequence: event.sequence,
        event_type: event.event_type,
        effect: 'scoped_correction_applied',
        correction_sha256: correction.correction_sha256,
        fact_id: correction.effect.fact_id,
        evidence_item_id: correction.effect.evidence_item_id,
        before_semantics: command.before_semantics,
        after_semantics: command.after_semantics,
        unrelated_facts_before_sha256: correctionArtifact.unrelated_facts_before_sha256,
        unrelated_facts_after_sha256: correctionArtifact.unrelated_facts_after_sha256,
      });
      cycle = structuredClone(nextCycle);
    } else if (event.event_type === 'LOOP_CREATED') {
      effects.push({ claim_id: claimId, sequence: event.sequence, event_type: event.event_type, effect: 'loop_created' });
    } else if (event.event_type === 'ACTION_SELECTED') {
      effects.push({ claim_id: claimId, sequence: event.sequence, event_type: event.event_type, effect: 'bounded_action_selected' });
    } else {
      throw new Error(`${claimId}: unexpected happy-path raw event ${event.event_type}`);
    }
  }

  const facts = cycle.facts;
  const process = cycle.process;
  const checklist = cycle.checklist;
  const factById = new Map(facts.map(fact => [fact.fact_id, fact]));
  const acceptedFactById = new Map(accepted.facts.map(fact => [fact.fact_id, fact]));
  const provenance = [];
  for (const item of checklist.items) {
    const acceptedFact = acceptedFactById.get(item.fact_id) || {};
    for (const sourceRef of acceptedFact.source_refs || []) {
      provenance.push({
        fact_id: item.fact_id,
        evidence_item_id: item.item_id,
        source_ref_id: rawSourceRefId(sourceRef),
      });
    }
  }
  for (const observation of observations) {
    for (const sourceRef of observation.source_refs || []) {
      provenance.push({
        fact_id: observation.fact_id,
        evidence_item_id: observation.evidence_item_id,
        source_ref_id: rawSourceRefId(sourceRef),
      });
    }
  }
  for (const correction of corrections) {
    provenance.push({
      fact_id: correction.effect.fact_id,
      evidence_item_id: correction.effect.evidence_item_id,
      source_ref_id: rawSourceRefId(correction.source_ref),
    });
  }
  const provenanceSet = new Set(provenance.map(edge => canonical([edge.fact_id, edge.evidence_item_id, edge.source_ref_id])));
  const obligations = checklist.items.map(item => {
    const fact = factById.get(item.fact_id);
    let status;
    if (fact.state === 'conflicting') status = 'contradicted';
    else if (item.status === 'provided_sufficient' && fact.state === 'known') status = 'satisfied';
    else if (item.status === 'conditional') status = 'conditional';
    else if (!item.current_path || item.status === 'not_applicable') status = 'blocked';
    else status = 'active';
    const acceptedSourceIds = (acceptedFactById.get(item.fact_id)?.source_refs || []).map(rawSourceRefId);
    const sourceRefIds = [...new Set([...acceptedSourceIds, ...(item.loop_source_ref_ids || [])])];
    return {
      obligation_id: item.item_id,
      fact_id: item.fact_id,
      status,
      evidence_status: item.status,
      mandatory_now: Boolean(item.current_path) && item.required_level === 'mandatory' && ['active', 'contradicted'].includes(status),
      source_ref_ids: sourceRefIds,
    };
  });
  const obligationById = new Map(obligations.map(value => [value.obligation_id, value]));
  const evidenceClassCounts = Object.fromEntries(EVIDENCE_CLASSES.map(name => [name, 0]));
  const evidenceItems = [];
  let controllingDecision = null;
  for (const item of checklist.items) {
    const fact = factById.get(item.fact_id);
    const obligation = obligationById.get(item.item_id);
    const received = fact.state === 'known' && obligation.status === 'satisfied'
      && obligation.source_ref_ids.length > 0
      && obligation.source_ref_ids.every(sourceId => provenanceSet.has(canonical([fact.fact_id, item.item_id, sourceId])));
    const evidenceClass = item.status === 'provided_sufficient' ? (received ? 'received' : 'unknown') : RAW_STATUS_CLASS[item.status];
    evidenceClassCounts[evidenceClass] += 1;
    evidenceItems.push({
      evidence_item_id: item.item_id,
      title: item.title,
      fact_id: item.fact_id,
      fact_state: fact.state,
      raw_status: item.status,
      evidence_class: evidenceClass,
      obligation_status: obligation.status,
      mandatory_now: obligation.mandatory_now,
      current_path: Boolean(item.current_path),
      source_ref_ids: obligation.source_ref_ids,
      provenance_edge_sha256s: provenance.filter(edge => edge.evidence_item_id === item.item_id)
        .map(edge => sha(edge)).sort(),
    });
    if (!controllingDecision && (obligation.mandatory_now || obligation.status === 'contradicted')) {
      controllingDecision = {
        obligation_id: obligation.obligation_id,
        fact_id: item.fact_id,
        fact_state: fact.state,
        obligation_status: obligation.status,
        evidence_item_id: item.item_id,
        evidence_class: evidenceClass,
        title: item.title,
      };
    }
  }
  const withinAttemptBound = ([item]) => {
    const bound = item.max_observed_attempts;
    return bound === undefined || history.filter(row => row.evidence_item_id === item.item_id && row.outcome === 'observed').length < bound;
  };
  const mandatory = checklist.items.map(item => [item, obligationById.get(item.item_id)])
    .filter(([, obligation]) => obligation.mandatory_now).filter(withinAttemptBound);
  const conditional = checklist.items.map(item => [item, obligationById.get(item.item_id)])
    .filter(([item, obligation]) => obligation.status === 'conditional'
      && (item.node_ids || [item.node_id]).includes(process.current_overlay.next_action_node_id)).filter(withinAttemptBound);
  const eligible = mandatory.length ? mandatory : conditional;
  let selectedAction = null;
  if (eligible.length) {
    const [item, obligation] = eligible[0];
    const actionKind = obligation.status === 'contradicted' ? 'clarify'
      : item.status === 'provided_insufficient' ? 'validate' : 'acquire';
    const payload = {
      contract: 'casepath.evidence-action/1.0.0',
      action_kind: actionKind,
      process_node_id: process.current_overlay.next_action_node_id,
      evidence_item_id: item.item_id,
      fact_id: item.fact_id,
      title: item.title,
      bounded_tool_id: item.bounded_tool_id || 'unavailable-evidence-tool-v1',
    };
    const actionSha = claimLoopSha(payload);
    selectedAction = { ...payload, action_id: `action.${actionSha}`, action_sha256: actionSha };
  }
  const unresolvedIds = obligations.filter(row => row.mandatory_now).map(row => row.obligation_id);
  const contradictedIds = obligations.filter(row => row.status === 'contradicted').map(row => row.obligation_id);
  const provenanceComplete = obligations.filter(row => row.status === 'satisfied').every(row => row.source_ref_ids.length > 0
    && row.source_ref_ids.every(sourceId => provenanceSet.has(canonical([row.fact_id, row.obligation_id, sourceId]))));
  const uncertainty = facts.filter(fact => ['unknown', 'conflicting'].includes(fact.state)).map(fact => fact.fact_id);
  const controllingFactIds = new Set(facts.filter(fact => fact.controls_process === true).map(fact => fact.fact_id));
  const blockingUncertainty = uncertainty.filter(factId => obligations.some(row => row.fact_id === factId && row.mandatory_now) || controllingFactIds.has(factId));
  const decisionReady = unresolvedIds.length === 0 && contradictedIds.length === 0 && blockingUncertainty.length === 0 && provenanceComplete;
  const outcome = decisionReady ? 'decision_ready' : selectedAction ? 'next_action' : 'abstain';
  const overlay = process.current_overlay;
  const currentNode = process.nodes.find(node => node.node_id === overlay.current_node_id);
  const workflowState = outcome === 'decision_ready' ? 'decision_ready' : outcome === 'abstain' ? 'safe_abstention' : 'waiting_for_evidence';
  const readinessState = outcome === 'decision_ready' ? 'decision_ready' : outcome === 'abstain' ? 'safe_abstention' : 'blocked';
  const blocker = outcome === 'decision_ready' ? 'No current mandatory evidence obligation remains'
    : outcome === 'abstain' ? 'mandatory evidence is unresolved and no bounded action remains'
      : controllingDecision ? `${controllingDecision.title} is ${controllingDecision.evidence_class}` : 'The selected evidence action remains unresolved';
  const nextState = outcome === 'decision_ready'
    ? { kind: 'decision_ready', title: 'Review certified decision-ready packet', action_id: null, action_sha256: null, terminal_mode: 'finalize' }
    : outcome === 'abstain'
      ? { kind: 'safe_abstention', title: 'Review safe abstention and unresolved evidence', action_id: null, action_sha256: null, terminal_mode: 'abstain' }
      : { kind: 'evidence_action', title: selectedAction.title, action_id: selectedAction.action_id, action_sha256: selectedAction.action_sha256, terminal_mode: null };
  const semanticProjection = {
    current_process: {
      node_id: overlay.current_node_id,
      node_title: currentNode.title,
      next_action_node_id: overlay.next_action_node_id,
      selected_branch_id: overlay.selected_branch_id,
      overlay_sha256: sha(overlay),
    },
    controlling_decision: controllingDecision,
    evidence_items: evidenceItems,
    evidence_class_counts: evidenceClassCounts,
    workflow_state: workflowState,
    readiness_state: readinessState,
    principal_blocker: blocker,
    pending_evidence_count: new Set([...unresolvedIds, ...contradictedIds]).size,
    next_state: nextState,
    failure_or_unknown_effect: false,
  };
  const activity = {
    cycle_receipt_sha256s: cycleReceipts.map(receipt => receipt.receipt_sha256),
    graph_traversal_count: cycleReceipts.length,
    model_calls: cycleReceipts.reduce((sum, receipt) => sum + receipt.model_calls, 0),
    provider_calls: cycleReceipts.reduce((sum, receipt) => sum + receipt.provider_calls, 0),
    credential_access_receipt_sha256s: cycleReceipts.flatMap(receipt => receipt.credential_access_receipt_sha256s),
    credential_reads: cycleReceipts.some(receipt => receipt.credential_access_status !== 'none_due_to_zero_provider_calls') ? null : 0,
    cost_usd: cycleReceipts.every(receipt => receipt.cost_status === 'exact')
      ? cycleReceipts.reduce((sum, receipt) => sum + receipt.cost_usd, 0) : null,
    artifact_receipt_sha256s: artifactReceipts.map(receipt => receipt.receipt_sha256),
    artifact_model_calls: artifactReceipts.reduce((sum, receipt) => sum + receipt.interpretation.model_calls, 0),
    artifact_provider_calls: artifactReceipts.reduce((sum, receipt) => sum + receipt.interpretation.provider_calls, 0),
  };
  return {
    semantic_projection: semanticProjection,
    selected_action: selectedAction,
    outcome,
    accepted_artifacts_sha256: claimLoopSha(accepted),
    accepted_cycle_artifacts_sha256: cycle.receipt_sha256,
    observations,
    corrections,
    effects,
    activity,
  };
}

async function independentReplayRawJournals(
  rawRows,
  claimIds,
  apiAuthority,
  authorityRoot,
  executionRoot,
) {
  const byJournal = new Map();
  for (const row of rawRows) {
    const key = `${row.session_id}\u0000${row.loop_id}`;
    if (!byJournal.has(key)) byJournal.set(key, []);
    byJournal.get(key).push(row);
  }
  const replayRows = [];
  const effectRows = [];
  const activityRows = [];
  const stateReceiptRows = [];
  const artifactReceiptRows = [];
  const workspaceStates = new Map();
  const workspaceEventsByClaim = new Map();
  const loopEventsByClaim = new Map();
  const authorityByAcquisition = await loadIndependentAuthorityPrimitives(
    authorityRoot,
    rawRows,
    executionRoot,
  );
  for (const claimId of claimIds) {
    const workspaceEvents = byJournal.get(`${WORKSPACE_SESSION_ID}\u0000workspace.${claimId}`) || [];
    const loopEvents = [...byJournal.values()].find(events => events[0].session_id === CLAIM_LOOP_SESSION_ID
      && events[0].event.command.claim_id === claimId) || [];
    const workspace = replayWorkspaceEvents(workspaceEvents, claimId);
    const loopReplay = replayClaimLoopJournalV1(loopEvents, claimId, { authorityByAcquisition });
    const loopState = loopReplay.final_state;
    const journalSemantics = reconstructJournalSemantics(loopState);
    const artifactReceipts = loopReplay.artifact_receipts;
    const activity = {
      upstream_source_run: loopState.upstream_source_run_activity,
      source_acceptance: loopState.source_acceptance_activity,
      incremental_loop: loopState.incremental_loop_activity,
      total_bound: loopState.total_bound_activity,
      artifact_receipt_sha256s: artifactReceipts.map(value => value.receipt_sha256),
      artifact_model_calls: artifactReceipts.reduce((sum, value) => sum + value.interpretation.model_calls, 0),
      artifact_provider_calls: artifactReceipts.reduce((sum, value) => sum + value.interpretation.provider_calls, 0),
      artifact_cost_usd: artifactReceipts.reduce((sum, value) => sum + value.interpretation.cost_usd, 0),
    };
    const authority = apiAuthority.get(claimId);
    check(`${claimId}: independent raw-event semantic replay equals the product projection`,
      canonical(journalSemantics.semantic_projection) === canonical(projectionSemanticSlice(authority.view.operational_projection))
        && workspace.state.state_sha256 === authority.detail.state.state_sha256
        && loopState.state_sha256 === authority.view.loop_state.state_sha256
        && loopEvents.at(-1).event.resulting_state_sha256 === loopState.state_sha256);
    check(`${claimId}: journal-derived activity is exactly provider-free`,
      activity.total_bound.graph_traversal_count > 0
        && activity.total_bound.model_calls === 0
        && activity.total_bound.provider_calls === 0
        && activity.total_bound.credential_access_status === 'none_due_to_zero_provider_calls'
        && activity.total_bound.credential_access_receipt_sha256s.length === 0
        && activity.total_bound.cost_status === 'exact'
        && activity.total_bound.cost_usd === 0
        && activity.artifact_model_calls === 0
        && activity.artifact_provider_calls === 0
        && activity.artifact_cost_usd === 0);
    workspaceStates.set(claimId, workspace.state);
    workspaceEventsByClaim.set(claimId, workspaceEvents.map(row => row.event));
    loopEventsByClaim.set(claimId, loopEvents.map(row => row.event));
    replayRows.push({
      contract: 'casepath.gate2-independent-journal-replay/1.0.0',
      claim_id: claimId,
      workspace_state: workspace.state,
      claim_loop_final_state: loopState,
      claim_loop_final_state_sha256: loopState.state_sha256,
      semantic_projection: journalSemantics.semantic_projection,
      semantic_projection_sha256: sha(journalSemantics.semantic_projection),
      selected_action: loopState.selected_action,
      outcome: authority.view.outcome,
      accepted_artifacts_sha256: loopState.accepted_artifacts_sha256,
      accepted_cycle_artifacts_sha256: loopState.accepted_cycle_artifacts_sha256,
      observation_sha256s: loopState.observations.map(value => value.observation_sha256),
      correction_sha256s: loopState.corrections.map(value => value.correction_sha256),
      state_receipts: loopReplay.state_receipts,
      artifact_receipt_sha256s: activity.artifact_receipt_sha256s,
    });
    effectRows.push(...workspace.effects, ...loopReplay.effects);
    activityRows.push({ claim_id: claimId, ...activity });
    stateReceiptRows.push(...workspace.effects.map(value => ({
      claim_id: claimId,
      session_id: WORKSPACE_SESSION_ID,
      sequence: value.sequence,
      event_type: value.event_type,
      event_sha256: value.event_sha256,
      recomputed_state_sha256: value.resulting_state_sha256,
      expected_state_sha256: value.resulting_state_sha256,
    })), ...loopReplay.state_receipts.map(value => ({ ...value, session_id: CLAIM_LOOP_SESSION_ID })));
    artifactReceiptRows.push(...artifactReceipts.map(value => ({ claim_id: claimId, ...value })));
  }
  return {
    replayRows,
    effectRows,
    activityRows,
    stateReceiptRows,
    artifactReceiptRows,
    workspaceStates,
    workspaceEventsByClaim,
    loopEventsByClaim,
  };
}

async function auditPythonRuntimeClosure(candidate) {
  const pythonPath = path.resolve(candidate.apiBootReceipt.runtime.python_path);
  const venvRoot = path.dirname(path.dirname(pythonPath));
  const libRoot = path.join(venvRoot, 'lib');
  const sitePackageCandidates = [];
  for (const entry of await fs.readdir(libRoot, { withFileTypes: true })) {
    const candidatePath = path.join(libRoot, entry.name, 'site-packages');
    if (entry.isDirectory()) {
      try {
        if ((await fs.lstat(candidatePath)).isDirectory()) sitePackageCandidates.push(candidatePath);
      } catch (error) {
        if (error.code !== 'ENOENT') throw error;
      }
    }
  }
  check('Python runtime has one exact venv site-packages closure', sitePackageCandidates.length === 1);
  const sitePackages = sitePackageCandidates[0];
  const entries = [];
  async function visit(absolute) {
    for (const entry of (await fs.readdir(absolute, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
      const entryPath = path.join(absolute, entry.name);
      const metadata = await fs.lstat(entryPath);
      const relativePath = path.relative(venvRoot, entryPath).split(path.sep).join('/');
      if (metadata.isDirectory()) {
        entries.push({ path: relativePath, kind: 'directory', mode: metadata.mode & 0o7777 });
        await visit(entryPath);
      } else if (metadata.isFile()) {
        const bytes = await fs.readFile(entryPath);
        entries.push({
          path: relativePath,
          kind: 'file',
          mode: metadata.mode & 0o7777,
          size_bytes: bytes.length,
          sha256: sha(bytes),
        });
      } else if (metadata.isSymbolicLink()) {
        const link_target = await fs.readlink(entryPath);
        const resolved_target = await fs.realpath(entryPath);
        const targetMetadata = await fs.lstat(resolved_target);
        entries.push({
          path: relativePath,
          kind: 'symlink',
          mode: metadata.mode & 0o7777,
          link_target,
          resolved_target,
          target_kind: targetMetadata.isFile() ? 'file' : targetMetadata.isDirectory() ? 'directory' : 'special',
          target_size_bytes: targetMetadata.isFile() ? targetMetadata.size : null,
          target_sha256: targetMetadata.isFile() ? sha(await fs.readFile(resolved_target)) : null,
        });
      } else {
        throw new Error(`Python closure contains a special entry: ${relativePath}`);
      }
    }
  }
  await visit(sitePackages);
  for (const bootstrapPath of [path.join(venvRoot, 'pyvenv.cfg'), pythonPath]) {
    const metadata = await fs.lstat(bootstrapPath);
    const relativePath = path.relative(venvRoot, bootstrapPath).split(path.sep).join('/');
    if (metadata.isSymbolicLink()) {
      const resolvedTarget = await fs.realpath(bootstrapPath);
      const bytes = await fs.readFile(resolvedTarget);
      entries.push({
        path: relativePath,
        kind: 'symlink',
        mode: metadata.mode & 0o7777,
        link_target: await fs.readlink(bootstrapPath),
        resolved_target: resolvedTarget,
        target_kind: 'file',
        target_size_bytes: bytes.length,
        target_sha256: sha(bytes),
      });
    } else {
      const bytes = await fs.readFile(bootstrapPath);
      entries.push({ path: relativePath, kind: 'file', mode: metadata.mode & 0o7777, size_bytes: bytes.length, sha256: sha(bytes) });
    }
  }
  entries.sort((left, right) => left.path.localeCompare(right.path));
  const pthFiles = [];
  for (const entry of entries.filter(value => value.kind === 'file' && value.path.endsWith('.pth'))) {
    const absolute = path.join(venvRoot, entry.path);
    const text = await fs.readFile(absolute, 'utf8');
    pthFiles.push({
      path: entry.path,
      sha256: entry.sha256,
      executable_lines: text.split(/\r?\n/).filter(line => line.trimStart().startsWith('import ')),
      path_lines: text.split(/\r?\n/).map(line => line.trim()).filter(line => line && !line.startsWith('#') && !line.startsWith('import ')),
    });
  }
  const customizers = entries.filter(value => /(^|\/)(sitecustomize|usercustomize)\.py$/.test(value.path));
  const recordFiles = entries.filter(value => value.kind === 'file' && /\.dist-info\/RECORD$/.test(value.path));
  const distributionRoster = candidate.apiBootReceipt.runtime.installed_distributions;
  check('Python closure binds distribution metadata, .pth execution, and customizer presence exactly',
    Array.isArray(distributionRoster)
      && recordFiles.length === distributionRoster.length
      && pthFiles.every(value => value.executable_lines.every(line => /^import [A-Za-z0-9_., ]+$/.test(line)))
      && customizers.every(value => value.kind === 'file'));
  const rosterSha256 = sha(entries);
  return {
    contract: 'casepath.gate2-python-runtime-closure/1.0.0',
    venv_root: venvRoot,
    site_packages_root: sitePackages,
    python_path: pythonPath,
    python_real_path: await fs.realpath(pythonPath),
    python_file_sha256: candidate.apiBootReceipt.runtime.python_file_sha256,
    requirements_lock_sha256: candidate.apiBootReceipt.runtime.requirements_lock_sha256,
    installed_distributions: distributionRoster,
    installed_distributions_sha256: candidate.apiBootReceipt.runtime.installed_distributions_sha256,
    entry_count: entries.length,
    roster_sha256: rosterSha256,
    record_file_count: recordFiles.length,
    record_roster_sha256: sha(recordFiles),
    pth_files: pthFiles,
    customizer_files: customizers,
    entries,
  };
}

async function auditRuntimeClosure(candidate, claimIds) {
  const serviceRoot = candidate.apiBootIdentity.service_root;
  const files = [];
  async function visit(directory) {
    for (const entry of (await fs.readdir(directory, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
      if (directory === serviceRoot && entry.name === '.runtime') continue;
      const absolute = path.join(directory, entry.name);
      const metadata = await fs.lstat(absolute);
      const relative = path.relative(serviceRoot, absolute).split(path.sep).join('/');
      if (metadata.isSymbolicLink()) throw new Error(`installed closure contains a symlink: ${relative}`);
      if (metadata.isDirectory()) {
        check(`installed directory ${relative} is immutable`, (metadata.mode & 0o7777) === 0o500);
        await visit(absolute);
      } else if (metadata.isFile()) {
        const bytes = await fs.readFile(absolute);
        const mode = metadata.mode & 0o7777;
        if ((mode & 0o222) !== 0 || metadata.nlink !== 1) throw new Error(`installed closure file is mutable or linked: ${relative}`);
        files.push({
          executable: Boolean(mode & 0o111),
          path: relative,
          sha256: sha(bytes),
          size_bytes: bytes.length,
          mode,
          bytes,
        });
      } else {
        throw new Error(`installed closure contains a special entry: ${relative}`);
      }
    }
  }
  await visit(serviceRoot);
  files.sort((a, b) => a.path.localeCompare(b.path));
  const rosterRows = files.map(({ bytes: _bytes, ...row }) => row);
  check('Full installed non-runtime roster independently matches the boot authority',
    rosterRows.length === candidate.apiBootIdentity.installed_non_runtime_roster.file_count
      && sha(rosterRows) === candidate.apiBootIdentity.installed_non_runtime_roster.roster_sha256);

  const encodedIds = new Map(claimIds.flatMap(claimId => [
    [claimId, { claim_id: claimId, encoding: 'raw' }],
    [Buffer.from(claimId).toString('base64'), { claim_id: claimId, encoding: 'base64' }],
    [sha(claimId), { claim_id: claimId, encoding: 'sha256' }],
  ]));
  const classify = relative => {
    if (relative.startsWith('casepath-api/casepath_api/corpora/synthetic-150/')
      && !relative.includes('/policy/')) return 'public-claim-data';
    if ((relative.startsWith('casepath-api/casepath_api/') && relative.endsWith('.py'))
      || relative.startsWith('casepath/assets/')
      || relative.startsWith('casepath-public/')
      || relative === 'casepath/index.html'
      || relative === 'bin/casepath'
      || relative === 'casepath/tools/fixtures/render-legacy-20260811.yaml'
      || relative === 'casepath-api/requirements.lock'
      || relative.includes('/corpora/synthetic-150/policy/')) return 'runtime-control';
    return 'source-bound-support';
  };
  const classified = files.map(row => {
    const text = row.bytes.toString('utf8');
    const hits = [];
    for (const [literal, identity] of encodedIds) {
      if (text.includes(literal)) hits.push(identity);
    }
    const genericIds = [...new Set([...text.matchAll(/\bclm_[0-9a-f]{16}\b/g)].map(match => match[0]))];
    return {
      path: row.path,
      sha256: row.sha256,
      size_bytes: row.size_bytes,
      mode: row.mode,
      executable: row.executable,
      role: classify(row.path),
      corpus_identity_hits: hits,
      generic_claim_id_literals: genericIds,
    };
  });
  const runtimeFindings = classified.filter(row => row.role === 'runtime-control'
    && (row.corpus_identity_hits.length > 0 || row.generic_claim_id_literals.length > 0));
  const supportFindings = classified.filter(row => row.role === 'source-bound-support'
    && (row.corpus_identity_hits.length > 0 || row.generic_claim_id_literals.length > 0));
  check('Full runtime code, assets, static build, and config contain no claim lookup literal',
    classified.filter(row => row.role === 'runtime-control').length > 0 && runtimeFindings.length === 0,
  canonical(runtimeFindings));
  return {
    definition: 'complete immutable installed non-runtime tree, role-classified into runtime control, public claim data, and source-bound support',
    service_root: serviceRoot,
    file_count: rosterRows.length,
    file_roster_sha256: sha(rosterRows),
    boot_roster_sha256: candidate.apiBootIdentity.installed_non_runtime_roster.roster_sha256,
    runtime_control_file_count: classified.filter(row => row.role === 'runtime-control').length,
    public_claim_data_file_count: classified.filter(row => row.role === 'public-claim-data').length,
    source_bound_support_file_count: classified.filter(row => row.role === 'source-bound-support').length,
    corpus_claim_id_literal_count: runtimeFindings.reduce((sum, row) => sum + row.corpus_identity_hits.length, 0),
    corpus_roster_lookup_table_count: runtimeFindings.filter(row => row.corpus_identity_hits.length > 1).length,
    support_identity_findings: supportFindings,
    files: classified,
  };
}

async function runProductionProjectionPermutation(candidate, replay, claimIds, apiAuthority, carryoverProofs) {
  const aliasNonceSha256 = sha(randomBytes(32));
  const aliases = new Map(claimIds.map(claimId => [
    claimId,
    `clm_${sha({
      contract: 'casepath.projection-permutation-alias/1.0.0',
      claim_id: claimId,
      alias_nonce_sha256: aliasNonceSha256,
    }).slice(0, 16)}`,
  ]));
  check('Permutation aliases are unique, unseen, and claim-shaped',
    new Set(aliases.values()).size === claimIds.length
      && [...aliases.values()].every(value => /^clm_[0-9a-f]{16}$/.test(value) && !claimIds.includes(value)));
  const inputRows = claimIds.map(claimId => {
    const completeEvents = replay.loopEventsByClaim.get(claimId);
    const carryoverProof = carryoverProofs.get(claimId);
    const events = carryoverProof
      ? completeEvents.slice(0, carryoverProof.loop_event_count)
      : completeEvents;
    const workspaceEvents = replay.workspaceEventsByClaim.get(claimId);
    const workspaceState = replay.workspaceStates.get(claimId);
    const replayRow = replay.replayRows.find(value => value.claim_id === claimId);
    const expectedProjection = carryoverProof?.view.operational_projection
      || apiAuthority.get(claimId).view.operational_projection;
    const expectedLoopStateSha256 = carryoverProof?.view.loop_state.state_sha256
      || replayRow.claim_loop_final_state_sha256;
    const tail = events.at(-1);
    return {
      claim_id: claimId,
      alias_claim_id: aliases.get(claimId),
      alias_nonce_sha256: aliasNonceSha256,
      permutation_scope:carryoverProof?.scope || 'complete_four_event_gate2_seam',
      forbidden_identity_values: claimIds,
      workspace_state: workspaceState,
      workspace_events: workspaceEvents,
      loop_events: events,
      loop_journal_prefix: {
        revision: tail.sequence,
        last_event_sha256: tail.event_sha256,
        last_event_at: tail.created_at,
      },
      expected_original_projection: expectedProjection,
      independent_replay_receipt: {
        contract: 'casepath.gate2-independent-permutation-binding/1.0.0',
        claim_id: claimId,
        workspace_state_sha256: workspaceState.state_sha256,
        workspace_event_roster_sha256: sha(workspaceEvents),
        claim_loop_state_sha256: expectedLoopStateSha256,
        claim_loop_event_roster_sha256: sha(events),
        expected_projection_sha256: expectedProjection.projection_sha256,
      },
    };
  });
  const executionRoot = candidate.apiBootIdentity.execution_root;
  const helperPath = path.join(executionRoot, 'casepath-qa/production-projection-permutation-v1.py');
  const apiRoot = path.join(executionRoot, 'casepath-api');
  const pythonPath = candidate.apiBootReceipt.runtime.python_path;
  const dataRoot = candidate.apiBootReceipt.runtime.data_root;
  const permutationBootstrap = 'import runpy,sys; sys.path.insert(0,sys.argv.pop(1)); runpy.run_path(sys.argv.pop(1),run_name="__main__")';
  const childArguments = [
    '-B', '-I', '-P', '-c', permutationBootstrap, apiRoot, helperPath,
  ];
  const expectedChildEnvironment = {
    HOME: path.join(candidate.apiBootIdentity.service_root, '.runtime/casepath-dev-v2/home'),
    LANG: 'C.UTF-8',
    LC_ALL: 'C.UTF-8',
    PATH: `${path.dirname(pythonPath)}:/usr/bin:/bin:/usr/sbin:/sbin`,
    PYTHONHASHSEED: '0',
    PYTHONNOUSERSITE: '1',
    PYTHONSAFEPATH: '1',
    PYTHONDONTWRITEBYTECODE: '1',
    TZ: 'UTC',
  };
  const frozenPermutationLaunch = candidate.apiBootIdentity.permutation_subprocess;
  const helperBytes = await fs.readFile(helperPath);
  check('Permutation subprocess invocation is exactly the boot-sealed launch authority',
    canonical(frozenPermutationLaunch?.argv) === canonical([pythonPath, ...childArguments])
      && frozenPermutationLaunch?.cwd === candidate.apiBootIdentity.service_root
      && canonical(frozenPermutationLaunch?.environment) === canonical(expectedChildEnvironment)
      && frozenPermutationLaunch?.environment_sha256 === sha(expectedChildEnvironment)
      && frozenPermutationLaunch?.helper?.kind === 'file'
      && frozenPermutationLaunch?.helper?.path === helperPath
      && frozenPermutationLaunch?.helper?.size_bytes === helperBytes.length
      && frozenPermutationLaunch?.helper?.sha256 === sha(helperBytes));
  const beforeFiles = await snapshotRegularFiles(dataRoot);
  const child = spawn(pythonPath, childArguments, {
    cwd: candidate.apiBootIdentity.service_root,
    env: expectedChildEnvironment,
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  let stdout = '';
  let stderr = '';
  child.stdout.setEncoding('utf8');
  child.stderr.setEncoding('utf8');
  child.stdout.on('data', chunk => { stdout += chunk; });
  child.stderr.on('data', chunk => { stderr += chunk; });
  child.stdin.end(`${inputRows.map(row => canonical(row)).join('\n')}\n`);
  const exitCode = await new Promise((resolve, reject) => {
    child.on('error', reject);
    child.on('close', resolve);
  });
  if (exitCode !== 0 || stderr.trim()) throw new Error(`production projection probe failed (${exitCode}): ${stderr}`);
  const results = stdout.trimEnd().split('\n').filter(Boolean).map(line => JSON.parse(line));
  const afterFiles = await snapshotRegularFiles(dataRoot);
  const expectedModulePath = path.join(executionRoot, 'casepath-api/casepath_api/workspace_operational_projection_v1.py');
  const expectedModuleSha = sha(await fs.readFile(expectedModulePath));
  const expectedPythonRealPath = await fs.realpath(pythonPath);
  const frozenPythonRuntime = candidate.apiBootIdentity.python_runtime;
  const childRuntimeCanonical = canonical(results[0]?.child_runtime);
  const auditPolicyCanonical = canonical(results[0]?.audit_policy);
  check('Production-path permutation validates 148 complete seams and two declared carryover scopes without authority mutation',
    results.length === 150
      && new Set(results.map(row => row.claim_id)).size === 150
      && new Set(results.map(row => row.alias_claim_id)).size === 150
      && canonical(beforeFiles) === canonical(afterFiles)
      && results.every(row => row.contract === 'casepath.production-projection-permutation-result/1.0.0'
        && row.receipt_sha256 === sha(without(row, 'receipt_sha256'))
        && row.alias_claim_id === aliases.get(row.claim_id)
        && row.permutation_scope === inputRows.find(value => value.claim_id === row.claim_id).permutation_scope
        && row.identity_neutral_semantics_equal === true
        && row.original_semantic_sha256 === row.permuted_semantic_sha256
        && row.expected_original_projection_exact_equal === true
        && row.original_detail_compact_exact_equal === true
        && row.permuted_detail_compact_exact_equal === true
        && row.identity_permutation?.bijective === true
        && row.identity_permutation?.full_structure_inverse_equal === true
        && row.identity_permutation?.full_projection_inverse_equal === true
        && row.identity_permutation?.original_claim_occurrence_count_after === 0
        && row.identity_permutation?.alias_occurrence_count_before === 0
        && row.external_nonrenamable_identities?.every_identity_classified === true
        && row.external_nonrenamable_identities?.disjoint_from_changed_identity_domain === true
        && row.negative_controls?.contract === 'casepath.identity-permutation-negative-controls/1.0.0'
        && row.negative_controls?.control_count === 2
        && row.negative_controls?.all_rejected_before_acceptance === true
        && canonical(row.negative_controls.controls.map(value => value.name).sort())
          === canonical(['colliding_claim_key_rename', 'incomplete_primary_identity_rename'])
        && row.negative_controls.controls.every(value => value.rejected === true)
        && row.audit_policy?.hook_installed_before_production_imports === true
        && canonical(row.audit_policy) === auditPolicyCanonical
        && Number.isInteger(row.audit_policy?.denied_attempt_count)
        && row.audit_policy.denied_attempt_count >= 0
        && Object.values(row.audit_policy.denied_event_counts || {}).reduce(
          (sum, value) => sum + value,
          0,
        ) === row.audit_policy.denied_attempt_count
        && Object.keys(row.audit_policy.denied_event_counts || {}).every(
          value => row.audit_policy.denied_exact_events.includes(value)
            || row.audit_policy.denied_prefixes.some(prefix => value.startsWith(prefix)),
        )
        && row.audit_policy?.sqlite_denied === true
        && row.audit_policy?.filesystem_mutation_denied === true
        && row.audit_policy?.subprocess_denied === true
        && row.audit_policy?.network_denied === true
        && row.runtime_source_closure?.literal_hit_count === 0
        && row.runtime_source_closure?.forbidden_identity_count === 150
        && row.runtime_source_closure?.forbidden_identity_roster_sha256 === sha(claimIds)
        && row.child_runtime?.contract === 'casepath.production-permutation-child-runtime/1.0.0'
        && row.child_runtime?.receipt_sha256 === sha(without(row.child_runtime, 'receipt_sha256'))
        && canonical(row.child_runtime) === childRuntimeCanonical
        && row.child_runtime?.sys_executable === path.resolve(pythonPath)
        && row.child_runtime?.sys_executable_realpath === expectedPythonRealPath
        && row.child_runtime?.sys_executable === frozenPythonRuntime?.stated_path
        && row.child_runtime?.sys_executable_realpath === frozenPythonRuntime?.real_path
        && row.child_runtime?.python_version === frozenPythonRuntime?.python_version
        && canonical(row.child_runtime?.python_version_info) === canonical(frozenPythonRuntime?.version_info)
        && canonical(row.child_runtime?.python_build) === canonical(frozenPythonRuntime?.python_build)
        && row.child_runtime?.python_compiler === frozenPythonRuntime?.python_compiler
        && row.child_runtime?.python_implementation?.toLowerCase() === frozenPythonRuntime?.implementation
        && row.child_runtime?.implementation_cache_tag === frozenPythonRuntime?.cache_tag
        && row.child_runtime?.cwd === candidate.apiBootIdentity.service_root
        && canonical(row.child_runtime?.sys_flags) === canonical({
          isolated: 1,
          safe_path: true,
          dont_write_bytecode: 1,
          no_user_site: 1,
          ignore_environment: 1,
        })
        && row.child_runtime?.ordered_sys_path?.[0] === apiRoot
        && row.child_runtime?.ordered_sys_path_sha256 === sha(row.child_runtime.ordered_sys_path)
        && Object.entries(expectedChildEnvironment).every(
          ([key, value]) => row.child_runtime.allowlisted_environment?.[key] === value,
        )
        && Object.keys(row.child_runtime.allowlisted_environment || {}).every(
          key => Object.hasOwn(expectedChildEnvironment, key) || key === '__CF_USER_TEXT_ENCODING',
        )
        && row.child_runtime?.allowlisted_environment_sha256
          === sha(row.child_runtime.allowlisted_environment)
        && row.child_runtime?.loaded_casepath_api_module_file_count
          === row.runtime_source_closure?.module_file_count
        && row.child_runtime?.loaded_casepath_api_module_roster_sha256
          === row.runtime_source_closure?.module_roster_sha256
        && row.module_path === expectedModulePath
        && row.module_sha256 === expectedModuleSha
        && canonical(row.independent_replay_binding)
          === canonical(inputRows.find(value => value.claim_id === row.claim_id).independent_replay_receipt)
        && row.input_receipt_sha256
          === sha(inputRows.find(value => value.claim_id === row.claim_id))
        && row.replayed_state_sha256 === inputRows.find(
          value => value.claim_id === row.claim_id,
        ).independent_replay_receipt.claim_loop_state_sha256));
  return {
    aliasNonceSha256,
    inputRows,
    results,
    beforeFiles,
    afterFiles,
    childRuntime: results[0].child_runtime,
    frozenPermutationLaunch,
  };
}

async function visibleQueueRows(page) {
  return page.locator('[data-claim-id]').evaluateAll(rows => rows.map(row => {
    const stateCell = row.querySelector('td[data-label="State"]');
    const evidenceCell = row.querySelector('td[data-label="Evidence"]');
    const evidenceSmall = [...(evidenceCell?.querySelectorAll('small') || [])];
    return {
      claim_id: row.dataset.claimId,
      subject: row.querySelector('.cw-claim-cell strong')?.textContent || '',
      owner: row.querySelector('td[data-label="Handler"] strong')?.textContent || '',
      readiness: stateCell?.querySelector('.cw-pill')?.textContent || '',
      workflow: stateCell?.querySelector('small')?.textContent || '',
      effect: stateCell?.querySelector('.cw-effect-warning,.cw-effect-clear')?.textContent || '',
      pending: evidenceCell?.querySelector('strong')?.textContent || '',
      progress_copy: evidenceCell?.querySelector('.cw-progress-copy')?.textContent || '',
      principal_blocker: evidenceSmall.at(-1)?.textContent || '',
      next_action: row.querySelector('td[data-label="Next action"] strong')?.textContent || '',
    };
  }));
}

async function waitForBrowserQueue(page, { scenario, expectedRows, action, requestMatches = () => true, expectedResponseOffset = 0, expectedVisibleRows = expectedRows.slice(0, 25) }) {
  const responsePromise = page.waitForResponse(response => {
    const url = new URL(response.url());
    return response.request().method() === 'GET'
      && url.origin === BASE_ORIGIN
      && url.pathname === '/api/claim-loops/v1/workspace/claims'
      && requestMatches(url.searchParams);
  }, { timeout: 30_000 });
  await action();
  const response = await responsePromise;
  const responseBody = await response.json();
  const responseIds = expectedRows.slice(expectedResponseOffset, expectedResponseOffset + 25).map(row => row.claim_id);
  const visibleIds = expectedVisibleRows.map(row => row.claim_id);
  await page.waitForFunction(({ ids, total }) => {
    const actual = [...document.querySelectorAll('[data-claim-id]')].map(row => row.dataset.claimId);
    const totalText = document.querySelector('#cwTotal')?.textContent || '';
    return JSON.stringify(actual) === JSON.stringify(ids)
      && Number(totalText.replace(/[^0-9]/g, '') || 0) === total;
  }, { ids: visibleIds, total: expectedRows.length }, { timeout: 30_000 });
  const domRows = await visibleQueueRows(page);
  const pageStatus = await page.locator('#cwPageStatus').textContent();
  const requestUrl = new URL(response.url());
  const valid = response.ok()
    && responseBody.contract === 'casepath.claim-queue-projection/2.0.0'
    && exactSha(responseBody, 'projection_sha256')
    && responseBody.total_count === expectedRows.length
    && canonical(responseBody.items.map(row => row.claim_id)) === canonical(responseIds)
    && canonical(domRows.map(row => row.claim_id)) === canonical(visibleIds)
    && pageStatus === (expectedVisibleRows.length ? `Showing ${expectedVisibleRows.length} of ${expectedRows.length}` : 'No claims match these filters');
  check(`Browser queue control ${scenario} renders exact visible rows`, valid, canonical({
    request: requestUrl.search,
    expected_total: expectedRows.length,
    response_ids: responseBody.items.map(row => row.claim_id),
    visible_ids: domRows.map(row => row.claim_id),
    page_status: pageStatus,
  }));
  const receipt = {
    scenario,
    request_parameters: Object.fromEntries([...requestUrl.searchParams.entries()].sort()),
    expected_total: expectedRows.length,
    response_item_ids: responseBody.items.map(row => row.claim_id),
    visible_item_ids: domRows.map(row => row.claim_id),
    visible_rows: domRows,
    response_projection_sha256: responseBody.projection_sha256,
  };
  browserControlRoster.push(receipt);
  return receipt;
}

async function resetBrowserQueue(page, baseline, scenario) {
  return waitForBrowserQueue(page, {
    scenario,
    expectedRows: baseline,
    action: () => page.goto(`${BASE}/?ui=final`, { waitUntil: 'domcontentloaded', timeout: 30_000 }),
    requestMatches: parameters => parameters.get('sort') === 'priority'
      && parameters.get('limit') === '25' && !parameters.has('cursor') && !parameters.has('q'),
  });
}

function filteredRows(baseline, parameter, value) {
  if (parameter === 'state') return baseline.filter(row => row.workflow_state === value);
  if (parameter === 'readiness') return baseline.filter(row => row.readiness_state === value);
  if (parameter === 'claim_type') return baseline.filter(row => row.claim_type === value);
  if (parameter === 'owner') return baseline.filter(row => value === 'unassigned' ? !row.owner : row.owner === value);
  if (parameter === 'urgency') return baseline.filter(row => row.urgency === value);
  if (parameter === 'failure') return baseline.filter(row => row.failure_or_unknown_effect === (value === 'true'));
  if (parameter === 'pending_evidence') {
    return baseline.filter(row => value === 'unknown' ? row.pending_evidence_count === null
      : value === 'none' ? row.pending_evidence_count === 0 : row.pending_evidence_count > 0);
  }
  throw new Error(`unknown browser filter ${parameter}`);
}

async function driveBrowserSearch(page, baseline, query, expectedRows, scenario) {
  return waitForBrowserQueue(page, {
    scenario,
    expectedRows,
    action: () => page.locator('#cwSearch').fill(query),
    requestMatches: parameters => parameters.get('q') === query
      && parameters.get('sort') === 'priority' && parameters.get('limit') === '25' && !parameters.has('cursor'),
  });
}

async function exerciseBrowserQueueControls(page, baseline) {
  const matrix = { sorts: [], filters: [], searches: [], pagination: [] };
  await resetBrowserQueue(page, baseline, 'initial-priority-sort');
  for (const mode of [...SORTS.filter(value => value !== 'priority'), 'priority']) {
    const expected = [...baseline].sort((left, right) => compareTuple(sortKey(left, mode), sortKey(right, mode)));
    const receipt = await waitForBrowserQueue(page, {
      scenario: `sort:${mode}`,
      expectedRows: expected,
      action: () => page.locator('#cwSort').selectOption(mode),
      requestMatches: parameters => parameters.get('sort') === mode
        && parameters.get('limit') === '25' && !parameters.has('cursor'),
    });
    matrix.sorts.push(receipt);
  }
  await resetBrowserQueue(page, baseline, 'pagination:initial');
  let visibleCount = 25;
  while (visibleCount < baseline.length) {
    const nextCount = Math.min(visibleCount + 25, baseline.length);
    const receipt = await waitForBrowserQueue(page, {
      scenario: `pagination:${visibleCount}-${nextCount}`,
      expectedRows: baseline,
      expectedResponseOffset: visibleCount,
      expectedVisibleRows: baseline.slice(0, nextCount),
      action: () => page.locator('#cwMore').click(),
      requestMatches: parameters => parameters.get('sort') === 'priority'
        && parameters.get('limit') === '25' && parameters.has('cursor'),
    });
    matrix.pagination.push(receipt);
    visibleCount = nextCount;
  }
  check('Browser load-more exhausts 150 unique claims and hides the cursor control',
    visibleCount === 150 && await page.locator('[data-claim-id]').count() === 150
    && new Set((await visibleQueueRows(page)).map(row => row.claim_id)).size === 150
    && await page.locator('#cwMore').isHidden());

  const filterControls = [
    ['state', '#cwState'], ['readiness', '#cwReadiness'], ['claim_type', '#cwClaimType'],
    ['owner', '#cwOwner'], ['urgency', '#cwUrgency'], ['failure', '#cwFailure'],
    ['pending_evidence', '#cwPendingEvidence'],
  ];
  for (const [parameter, selector] of filterControls) {
    await resetBrowserQueue(page, baseline, `filter:${parameter}:options`);
    const values = await page.locator(`${selector} option`).evaluateAll(options => options.map(option => option.value).filter(Boolean));
    const observations = [];
    for (const value of values) {
      await resetBrowserQueue(page, baseline, `filter:${parameter}:${value}:reset`);
      const expected = filteredRows(baseline, parameter, value);
      const receipt = await waitForBrowserQueue(page, {
        scenario: `filter:${parameter}:${value}`,
        expectedRows: expected,
        action: () => page.locator(selector).selectOption(value),
        requestMatches: parameters => parameters.get(parameter) === value
          && parameters.get('sort') === 'priority' && parameters.get('limit') === '25' && !parameters.has('cursor'),
      });
      observations.push({ value, match_count: expected.length, excluded_count: baseline.length - expected.length });
      matrix.filters.push(receipt);
    }
    const truthfulSingleValueOwner = parameter === 'owner'
      && canonical(values) === canonical(['unassigned'])
      && baseline.every(row => row.owner === null);
    check(`Browser filter ${parameter} has exact corpus-supported coverage`, values.length > 0
      && observations.some(row => row.match_count > 0)
      && (truthfulSingleValueOwner
        || observations.some(row => row.match_count === 0 || row.excluded_count > 0)), canonical(observations));
  }

  await resetBrowserQueue(page, baseline, 'search:subject:reset');
  const subjectCandidate = baseline.map(row => ({ query: row.subject, rows: baseline.filter(candidate => [candidate.claim_id, candidate.subject, candidate.owner || ''].some(value => value.toLowerCase().includes(row.subject.toLowerCase()))) }))
    .find(value => value.query && value.rows.length > 0 && value.rows.length < baseline.length);
  check('Subject search has a non-vacuous corpus query', Boolean(subjectCandidate));
  matrix.searches.push(await driveBrowserSearch(page, baseline, subjectCandidate.query, subjectCandidate.rows, 'search:subject'));

  await resetBrowserQueue(page, baseline, 'search:owner:reset');
  const ownerCandidate = baseline.map(row => row.owner).find(owner => owner
    && baseline.some(candidate => candidate.owner !== owner));
  const ownerRows = ownerCandidate
    ? baseline.filter(row => [row.claim_id, row.subject, row.owner || ''].some(value => value.toLowerCase().includes(ownerCandidate.toLowerCase())))
    : [];
  if (ownerCandidate) {
    matrix.searches.push(await driveBrowserSearch(page, baseline, ownerCandidate, ownerRows, 'search:owner'));
  } else {
    check('Owner search dimension is truthfully unassigned-only', baseline.every(row => row.owner === null));
    matrix.searches.push({
      scenario: 'search:owner:vacuous-unassigned-only',
      corpus_owner_values: ['unassigned'],
      expected_total: null,
      request_not_issued: true,
    });
  }

  await resetBrowserQueue(page, baseline, 'search:negative:reset');
  const negativeQuery = 'gate2-no-claim-subject-or-owner-can-match-this-value';
  matrix.searches.push(await driveBrowserSearch(page, baseline, negativeQuery, [], 'search:negative'));
  check('Browser subject/owner searches include positive and zero-result negative cases',
    subjectCandidate.rows.length > 0
      && (ownerCandidate ? ownerRows.length > 0 : baseline.every(row => row.owner === null))
      && matrix.searches.at(-1).expected_total === 0);
  await resetBrowserQueue(page, baseline, 'browser-controls:final-reset');
  return matrix;
}

async function captureClaimDom(page) {
  return page.evaluate(() => {
    const parse = value => JSON.parse(value || 'null');
    const classes = [...document.querySelectorAll('[data-evidence-class]')].map(section => ({
      name: section.dataset.evidenceClass,
      count: Number(section.querySelector('header span')?.textContent),
      items: [...section.querySelectorAll('[data-evidence-item-id]')].map(item => ({
        evidence_item_id: item.dataset.evidenceItemId,
        title: item.querySelector('strong')?.textContent || '',
        detail: item.querySelector('small')?.textContent || '',
        fact_id: item.dataset.factId,
        fact_state: item.dataset.factState,
        raw_status: item.dataset.rawStatus,
        obligation_status: item.dataset.obligationStatus,
        mandatory_now: item.dataset.mandatoryNow === 'true',
        current_path: item.dataset.currentPath === 'true',
        source_ref_ids: parse(item.dataset.sourceRefIds),
        provenance_edge_sha256s: parse(item.dataset.provenanceEdgeSha256s),
      })),
    }));
    return {
      claim_id: document.querySelector('.cw-detail-title small')?.textContent || null,
      title: document.querySelector('.cw-detail-title h2')?.textContent || '',
      body: document.querySelector('.cw-body-copy')?.textContent || '',
      outcome: document.querySelector('#cwLoopWorkbench')?.dataset.outcome,
      proposal: document.querySelector('#cwLoopProposal')?.textContent || '',
      status: document.querySelector('#cwLoopWorkbench > .cw-status')?.textContent || '',
      projection_sha256: document.querySelector('#cwCurrentProcess')?.dataset.operationalProjectionSha256,
      action_sha256: document.querySelector('#cwLoopProposal')?.dataset.actionSha256 || null,
      current_process_cells: [...document.querySelectorAll('#cwCurrentProcess .cw-state-item')].map(cell => ({
        label: cell.querySelector('span')?.textContent || '',
        value: cell.querySelector('strong')?.textContent || '',
        detail: cell.querySelector('small')?.textContent || '',
      })),
      principal_blocker: document.querySelector('#cwPrincipalBlocker')?.dataset.principalBlocker || null,
      next_state: parse(document.querySelector('#cwNextState')?.dataset.nextState),
      role_receipts: [...document.querySelectorAll('#cwAgentReceipts [data-agent-id]')].map(row => ({
        id: row.dataset.agentId,
        receipt_sha256: row.dataset.receiptSha256,
        text: row.textContent || '',
      })),
      gate_receipts: [...document.querySelectorAll('#cwGateReceipts [data-gate-id]')].map(row => ({
        id: row.dataset.gateId,
        receipt_sha256: row.dataset.receiptSha256,
        text: row.textContent || '',
      })),
      classes,
      observations: [...document.querySelectorAll('#cwEvidencePresent [data-observation-sha256]')].map(row => ({
        observation_sha256: row.dataset.observationSha256,
        fact_id: row.dataset.factId,
        evidence_item_id: row.dataset.evidenceItemId,
        fact_state: row.dataset.factState,
        normalized_value: row.dataset.normalizedValue || null,
        evidence_status: row.dataset.evidenceStatus,
        source_ref: parse(row.dataset.sourceRef),
        explanation: row.querySelector('strong')?.textContent || '',
        value: row.querySelector('blockquote')?.textContent || '',
        source_copy: row.querySelector('span')?.textContent || '',
      })),
      evidence_readiness: document.querySelector('#cwEvidenceProgress header span')?.textContent || '',
      progress_copy: document.querySelector('#cwEvidenceProgress .cw-progress-copy')?.textContent || '',
      progress_present: Boolean(document.querySelector('#cwEvidenceProgress [role="progressbar"]')),
      progress_now: document.querySelector('#cwEvidenceProgress [role="progressbar"]')?.getAttribute('aria-valuenow'),
      safety_boundary: document.querySelector('.cw-safety-boundary span')?.textContent || '',
      verified_line: document.querySelector('.cw-verified-line')?.textContent || '',
      terminal_receipt: document.querySelector('.cw-terminal-receipt')?.textContent || '',
      diagnostics: parse(document.querySelector('#cwDiagnostics pre')?.dataset.receiptJson),
      detail_panel_text: document.querySelector('#cwDetailPanel')?.innerText || '',
    };
  });
}

async function waitForExactCandidateRestart(preBoot, expectedIdentity) {
  const deadline = Date.now() + 180_000;
  let last = '';
  while (Date.now() < deadline) {
    let snapshot = null;
    try {
      const response = await fetch(`${BASE}/readyz`, { cache: 'no-store' });
      last = await response.text();
      if (response.ok && JSON.parse(last).status === 'ready') {
        snapshot = await captureCandidateSourceSnapshot({ requireApiBootReceipt: true });
      }
    } catch (error) {
      last = String(error);
    }
    if (snapshot) {
      const liveBoot = snapshot.apiBootIdentity;
      if (liveBoot.receipt_file_sha256 === preBoot.receipt_file_sha256) {
        last = 'pre-restart boot is still serving';
      } else {
        if (liveBoot.prior_boot_receipt_file_sha256 !== preBoot.receipt_file_sha256) {
          throw new Error('replacement boot does not extend the exact pre-restart receipt');
        }
        if (canonical(snapshot.identity) !== canonical(expectedIdentity)
          || liveBoot.source_manifest_file_sha256 !== preBoot.source_manifest_file_sha256
          || liveBoot.capsule_roster_sha256 !== preBoot.capsule_roster_sha256
          || liveBoot.static_roster_sha256 !== preBoot.static_roster_sha256) {
          throw new Error('replacement boot changed the candidate source/build identity');
        }
        return snapshot;
      }
    }
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  throw new Error(`exact replacement boot did not become ready: ${last}`);
}

let browser;
try {
  const gate1Manifest = await verifyManifest(gate1Root, 'Gate 1');
  const gate1ReportRaw = await fs.readFile(path.join(gate1Root, 'report.json'));
  const gate1Report = JSON.parse(gate1ReportRaw);
  const gate1NegativeControlRaw = await fs.readFile(path.join(gate1Root, 'negative-rejection-control.json'));
  const gate1NegativeControl = JSON.parse(gate1NegativeControlRaw);
  const gate1QualifiedSelectionRaw = await fs.readFile(path.join(gate1Root, 'qualified-witness-selection.json'));
  const gate1QualifiedSelection = JSON.parse(gate1QualifiedSelectionRaw);
  const gate1AuthorityChainRaw = await fs.readFile(path.join(gate1Root, 'authority-chain.json'));
  const gate1AuthorityChain = JSON.parse(gate1AuthorityChainRaw);
  check('Gate 1 prerequisite is an exact all-pass browser journey', gate1Report.contract === 'casepath.claims-workspace-browser-acceptance/1.0.0'
    && gate1Report.claim_count === 150 && exactSha(gate1Report, 'receipt_sha256')
    && gate1Report.status === 'PASS'
    && gate1Report.mutated_claim_count === 2
    && canonical(gate1Report.mutated_claim_ids) === canonical(ORDERED_CARRYOVER_CLAIM_IDS)
    && Array.isArray(gate1Report.checks) && gate1Report.checks.length > 0
    && new Set(gate1Report.checks.map(row => row.name)).size === gate1Report.checks.length
    && gate1Report.checks.every(row => row.passed));
  check('Gate 1 binds the exact qualified witness and safe-rejection evidence files',
    gate1Report.qualified_witness_selection?.path === 'qualified-witness-selection.json'
      && gate1Report.qualified_witness_selection.sha256 === sha(gate1QualifiedSelectionRaw)
      && gate1Report.qualified_witness_selection.semantic_sha256 === gate1QualifiedSelection.receipt_sha256
      && exactSha(gate1QualifiedSelection, 'receipt_sha256')
      && gate1QualifiedSelection.selected_claim_id === MAIN_CARRYOVER_CLAIM_ID
      && gate1Report.negative_rejection_control?.path === 'negative-rejection-control.json'
      && gate1Report.negative_rejection_control.sha256 === sha(gate1NegativeControlRaw)
      && gate1Report.negative_rejection_control.semantic_sha256 === gate1NegativeControl.receipt_sha256
      && exactSha(gate1NegativeControl, 'receipt_sha256')
      && gate1NegativeControl.control_claim_id === NEGATIVE_CARRYOVER_CLAIM_ID);
  check('Gate 1 report binds the full main-witness authority chain used for permutation carryover',
    gate1Report.authority_chain?.path === 'authority-chain.json'
      && gate1Report.authority_chain.sha256 === sha(gate1AuthorityChainRaw)
      && gate1AuthorityChain.claim_id === MAIN_CARRYOVER_CLAIM_ID
      && gate1AuthorityChain.crash_recovery?.after?.loop_state?.observations?.length === 1);
  check('Gate 1 exports the qualified-witness first-safe-action sample',
    Number.isFinite(gate1Report.timing?.first_safe_action_seconds)
      && gate1Report.timing.first_safe_action_seconds >= 0
      && gate1Report.timing.first_safe_action_seconds <= 10);
  firstSafeActionTimings.push({
    claim_id: MAIN_CARRYOVER_CLAIM_ID,
    boundary: 'start_click_through_authoritative_first_safe_loop_view',
    evidence_origin: 'sealed_gate1_qualified_witness',
    seconds: gate1Report.timing.first_safe_action_seconds,
  });

  const candidateStart = await captureCandidateSourceSnapshot({
    requireApiBootReceipt: true,
    allowValidatedWorkspaceJournalAdvance: true,
  });
  check('Gate 1 and Gate 2 use the exact same source/build candidate', canonical(gate1Report.candidate_source_identity) === canonical(candidateStart.identity));
  check('Gate 1 and Gate 2 use the exact same installed runtime', canonical(gate1Report.api_runtime_identity) === canonical(candidateStart.apiBootIdentity));
  const firstSeedReceipt = parseEmbeddedSeedReceipt(candidateStart, 'First fresh-root seed');
  check('First fresh-root seed imports all 150 claims exactly once', firstSeedReceipt.new_import_count === 150
    && firstSeedReceipt.replayed_import_count === 0 && firstSeedReceipt.claim_count === 150);

  const corpusManifestRaw = await fs.readFile(corpusManifestPath);
  const corpusManifest = JSON.parse(corpusManifestRaw);
  check('Public corpus is exact, 150-claim, and outcome-blind', corpusManifest.contract === 'casepath.public-observable-corpus/1.0.0'
    && corpusManifest.aggregate.claim_count === 150 && corpusManifest.claims.length === 150
    && corpusManifest.contains_sealed_targets === false && corpusManifest.contains_expected_outputs === false
    && corpusManifest.static_template.claim_roster_in_policy_identity === false
    && exactSha(corpusManifest, 'manifest_sha256'));
  const claimIds = corpusManifest.claims.map(row => row.claim_id).sort();
  check('Public corpus claim roster is unique', new Set(claimIds).size === 150);
  check('Gate 2 carryover receipt is canonical and self-hashed',
    exactSha(gate1Report.gate2_carryovers, 'receipt_sha256'));
  const carryoverPlan = validateGate2Gate1Carryovers({
    claimIds,
    gate1Report,
    negativeControl:gate1NegativeControl,
    qualifiedSelection:gate1QualifiedSelection,
  });
  const carryoverRowsByClaim = new Map(gate1Report.gate2_carryovers.rows.map(row => [row.claim_id, row]));
  const negativeEvidence = gate1NegativeControl.evidence;
  firstSafeActionTimings.push({
    claim_id:NEGATIVE_CARRYOVER_CLAIM_ID,
    boundary:'start_click_through_authoritative_first_safe_loop_view',
    evidence_origin:'sealed_gate1_safe_rejection_control',
    seconds:negativeEvidence.timing.first_safe_action_seconds,
  });
  sourceAcquisitionTimings.push({
    claim_id:NEGATIVE_CARRYOVER_CLAIM_ID,
    boundary:'commit_click_through_advance_request_after_exact_source_acquisition',
    evidence_origin:'sealed_gate1_safe_rejection_control',
    seconds:negativeEvidence.timing.source_acquisition_seconds,
  });
  postEvidenceReplanTimings.push({
    claim_id:NEGATIVE_CARRYOVER_CLAIM_ID,
    boundary:'advance_request_through_authoritative_rejection_replan_get',
    evidence_origin:'sealed_gate1_safe_rejection_control',
    seconds:negativeEvidence.timing.post_evidence_replan_seconds,
  });
  postMutationQueueSeconds.push({ ...negativeEvidence.post_mutation_queue_timing });
  const installedRuntimeClosureAudit = await auditRuntimeClosure(candidateStart, claimIds);
  const pythonRuntimeClosureBefore = await auditPythonRuntimeClosure(candidateStart);

  const ledgerBeforeResponse = await apiRaw('/api/model-ledger');
  const ledgerBefore = ledgerBeforeResponse.body;
  const initialRoster = await queueAll({ sort: 'priority', limit: 100 });
  check('Initial API roster equals the source-bound corpus', canonical(initialRoster.map(row => row.claim_id).sort()) === canonical(claimIds));
  const initialRowsByClaim = queueRowsByClaim(initialRoster);
  const initiallyActiveClaimIds = initialRoster
    .filter(row => row.workflow_state !== 'received')
    .map(row => row.claim_id)
    .sort();
  check('Read-only preflight admits exactly two typed carryovers and 148 pristine claims before any Gate 2 mutation',
    canonical(initiallyActiveClaimIds) === canonical([...carryoverPlan.ordered_carryover_claim_ids].sort())
      && carryoverPlan.fresh_claim_ids.every(claimId => initialRowsByClaim.get(claimId)?.workflow_state === 'received')
      && carryoverPlan.fresh_claim_ids.length === 148);
  for (const carryoverClaimId of carryoverPlan.ordered_carryover_claim_ids) {
    const expected = carryoverRowsByClaim.get(carryoverClaimId);
    const queueRow = initialRowsByClaim.get(carryoverClaimId);
    const [detail, view] = await Promise.all([
      api(`/api/claim-loops/v1/workspace/claims/${carryoverClaimId}`),
      api(`/api/claim-loops/v1/workspace/claims/${carryoverClaimId}/loop`),
    ]);
    check(`${carryoverClaimId}: read-only preflight binds queue, detail, and loop to Gate 1`,
      queueRow.row_sha256 === expected.queue_row_sha256
        && queueRow.state_sha256 === expected.workspace_state_sha256
        && queueRow.operational_projection.claim_loop_prefix.state_sha256 === expected.loop_state_sha256
        && detail.state.state_sha256 === expected.workspace_state_sha256
        && detail.state.workflow_state === 'in_review'
        && view.loop_state.revision === expected.loop_revision
        && view.loop_state.state_sha256 === expected.loop_state_sha256
        && view.outcome === expected.final_outcome
        && view.loop_state.observations.length === expected.observation_count
        && (carryoverClaimId === NEGATIVE_CARRYOVER_CLAIM_ID
          ? view.loop_state.selected_action?.action_sha256 === expected.selected_action_sha256
            && expected.authoritative_semantic_effect === false
          : view.loop_state.selected_action === null && expected.typed_abstention === true));
  }
  let previousMutationQueue = initialRoster;
  let previousQueueIsolationReceiptSha256 = null;

  const databasePath = path.resolve(candidateStart.apiBootReceipt.runtime.database_path);
  const authorityRoot = path.join(candidateStart.apiBootReceipt.runtime.data_root, 'workspace-evidence-v1');
  const gate2JournalBeforeRows = await readRawJournalRows(databasePath);
  const gate2AuthorityBefore = await snapshotRegularFiles(authorityRoot);
  const gate2SidecarsBefore = await readAuthoritySidecars(databasePath);
  const preRestart = new Map();
  const sortedBindings = [...corpusManifest.claims].sort((left, right) => left.claim_id.localeCompare(right.claim_id));
  for (const binding of sortedBindings) {
    const claimId = binding.claim_id;
    let detail = await api(`/api/claim-loops/v1/workspace/claims/${claimId}`);
    check(`${claimId}: detail is source- and journal-bound`, detail.contract === 'casepath.claim-workspace-detail/1.0.0' && exactSha(detail, 'detail_sha256')
      && detail.state.binding.binding_sha256 === binding.binding_sha256);
    const sourceClaim = JSON.parse(await fs.readFile(path.join(corpusRoot, binding.claim.path), 'utf8'));
    check(`${claimId}: customer message is exact source content`, detail.message.subject === sourceClaim.customer_message.subject && detail.message.body === sourceClaim.customer_message.body);
    check(`${claimId}: artifact roster is exact`, canonical(detail.artifacts.map(row => ({ artifact_id: row.artifact_id, sha256: row.sha256, size_bytes: row.size_bytes })).sort((a, b) => a.artifact_id.localeCompare(b.artifact_id)))
      === canonical(binding.observable_artifacts.map(row => ({ artifact_id: row.artifact_id, sha256: row.sha256, size_bytes: row.size_bytes })).sort((a, b) => a.artifact_id.localeCompare(b.artifact_id))));
    for (const artifact of binding.observable_artifacts) {
      const response = await apiRaw(`/api/claim-loops/v1/workspace/claims/${claimId}/artifacts/${artifact.artifact_id}`);
      check(`${claimId}/${artifact.artifact_id}: artifact bytes are exact`, response.raw.length === artifact.size_bytes && sha(response.raw) === artifact.sha256
        && response.headers.get('etag') === `"${artifact.sha256}"`
        && (response.headers.get('content-type') || '').toLowerCase().startsWith(artifact.media_type.toLowerCase()));
    }
    let initialView;
    if (detail.state.workflow_state === 'received') {
      const firstSafeStarted = performance.now();
      await api(`/api/claim-loops/v1/workspace/claims/${claimId}/start`, post({ expected_revision: detail.state.revision }, `gate2.start.v1.${binding.binding_sha256}`));
      detail = await api(`/api/claim-loops/v1/workspace/claims/${claimId}`);
      const ensureBody = {
        expected_workspace_revision: detail.state.revision,
        expected_workspace_state_sha256: detail.state.state_sha256,
      };
      const ensureKey = `gate2.ensure.v1.${binding.binding_sha256}`;
      const first = await apiRaw(`/api/claim-loops/v1/workspace/claims/${claimId}/loop`, post(ensureBody, ensureKey));
      const replay = await apiRaw(`/api/claim-loops/v1/workspace/claims/${claimId}/loop`, post(ensureBody, ensureKey));
      check(`${claimId}: ensure replay is byte-identical`, first.raw.equals(replay.raw));
      initialView = await api(`/api/claim-loops/v1/workspace/claims/${claimId}/loop`);
      firstSafeActionTimings.push({
        claim_id: claimId,
        boundary: 'start_post_through_authoritative_first_safe_loop_view',
        evidence_origin: 'gate2_api_journey',
        seconds: (performance.now() - firstSafeStarted) / 1000,
      });
    } else {
      const carryover = carryoverRowsByClaim.get(claimId);
      check(`${claimId}: only an exact typed Gate 1 carryover is already active`,
        Boolean(carryover) && carryoverPlan.ordered_carryover_claim_ids.includes(claimId));
      initialView = await api(`/api/claim-loops/v1/workspace/claims/${claimId}/loop`);
      check(`${claimId}: live carryover state is byte-bound to the sealed Gate 1 receipt`,
        detail.state.state_sha256 === carryover.workspace_state_sha256
          && initialView.operational_projection.workspace_prefix.state_sha256 === carryover.workspace_state_sha256
          && initialView.loop_state.revision === carryover.loop_revision
          && initialView.loop_state.state_sha256 === carryover.loop_state_sha256
          && initialView.outcome === carryover.final_outcome
          && initialView.loop_state.observations.length === carryover.observation_count);
    }
    check(`${claimId}: deterministic intake is accepted`, detail.state.workflow_state === 'in_review' && Boolean(detail.state.intake_assessment));
    validateLoopView(initialView, claimId, detail.state);
    let canonicalView = initialView;
    if (claimId === NEGATIVE_CARRYOVER_CLAIM_ID) {
      const negativeCarryover = carryoverRowsByClaim.get(claimId);
      check(`${claimId}: Gate 1 safe rejection is imported with zero new Gate 2 mutation`,
        initialView.outcome === 'next_action'
          && negativeCarryover.typed_safe_rejection === true
          && negativeCarryover.authoritative_semantic_effect === false
          && initialView.loop_state.observations.length === 0
          && initialView.loop_state.selected_action.action_sha256 === negativeCarryover.selected_action_sha256
          && gate1NegativeControl.evidence.rejection_receipt.authoritative_semantic_effect === false);
      seamResults.push({
        contract:'casepath.gate2-claim-evidence-seam/1.0.0',
        claim_id:claimId,
        binding_sha256:binding.binding_sha256,
        initial_outcome:'next_action',
        final_outcome:'next_action',
        carryover_origin:'sealed_gate1_safe_rejection_control',
        typed_safe_rejection:true,
        authoritative_semantic_effect:false,
        gate1_negative_control_receipt_sha256:gate1NegativeControl.receipt_sha256,
        rejection_receipt_sha256:gate1NegativeControl.evidence.rejection_receipt.receipt_sha256,
        final_view_sha256:initialView.view_sha256,
      });
    } else if (initialView.outcome === 'next_action') {
      const seam = await performEvidenceSeam(claimId, binding, initialView);
      canonicalView = seam.after_view;
      seamResults.push(Object.fromEntries(Object.entries(seam).filter(([key]) => key !== 'after_view')));
      const started = performance.now();
      const postMutationQueue = await queueAll({ sort: 'priority', limit: 100 });
      const beforeByClaim = queueRowsByClaim(previousMutationQueue);
      const afterByClaim = queueRowsByClaim(postMutationQueue);
      const changedClaimIds = claimIds.filter(value => (
        canonical(beforeByClaim.get(value)) !== canonical(afterByClaim.get(value))
      ));
      const nonfocalBeforeSha256 = queueRosterSha256(previousMutationQueue, claimId);
      const nonfocalAfterSha256 = queueRosterSha256(postMutationQueue, claimId);
      check(`${claimId}: chained queue snapshot replaces exactly its one focal row`,
        beforeByClaim.size === 150
          && afterByClaim.size === 150
          && canonical(changedClaimIds) === canonical([claimId])
          && beforeByClaim.get(claimId).row_sha256 !== afterByClaim.get(claimId).row_sha256
          && nonfocalBeforeSha256 === nonfocalAfterSha256
          && claimIds.filter(value => value !== claimId).every(value => (
            beforeByClaim.get(value).row_sha256 === afterByClaim.get(value).row_sha256
              && canonical(beforeByClaim.get(value)) === canonical(afterByClaim.get(value))
          )));
      const queueIsolationMaterial = {
        contract: 'casepath.gate2-chained-queue-isolation/1.0.0',
        sequence: queueIsolationReceipts.length + 1,
        previous_receipt_sha256: previousQueueIsolationReceiptSha256,
        claim_id: claimId,
        before_roster_sha256: queueRosterSha256(previousMutationQueue),
        after_roster_sha256: queueRosterSha256(postMutationQueue),
        before_focal_row_sha256: beforeByClaim.get(claimId).row_sha256,
        after_focal_row_sha256: afterByClaim.get(claimId).row_sha256,
        changed_claim_ids: changedClaimIds,
        unchanged_nonfocal_count: 149,
        nonfocal_before_sha256: nonfocalBeforeSha256,
        nonfocal_after_sha256: nonfocalAfterSha256,
      };
      const queueIsolationReceipt = {
        ...queueIsolationMaterial,
        receipt_sha256: sha(queueIsolationMaterial),
      };
      queueIsolationReceipts.push(queueIsolationReceipt);
      previousQueueIsolationReceiptSha256 = queueIsolationReceipt.receipt_sha256;
      previousMutationQueue = postMutationQueue;
      postMutationQueueSeconds.push({
        claim_id: claimId,
        row_count: postMutationQueue.length,
        unique_claim_count: new Set(postMutationQueue.map(value => value.claim_id)).size,
        mutation_visible: postMutationQueue.some(value => value.claim_id === claimId
          && value.state_sha256 === canonicalView.operational_projection.workspace_prefix.state_sha256
          && value.operational_projection.claim_loop_prefix.state_sha256 === canonicalView.loop_state.state_sha256),
        state_roster_sha256: sha(postMutationQueue.map(value => ({
          claim_id: value.claim_id,
          workspace_state_sha256: value.state_sha256,
          claim_loop_state_sha256: value.operational_projection.claim_loop_prefix?.state_sha256 || null,
        })).sort((left, right) => left.claim_id.localeCompare(right.claim_id))),
        seconds: (performance.now() - started) / 1000,
      });
    } else {
      check(`${claimId}: the only non-actionable seam is the qualified Gate 1 typed abstention`,
        initialView.outcome === 'abstain' && claimId === MAIN_CARRYOVER_CLAIM_ID
          && carryoverRowsByClaim.get(claimId)?.typed_abstention === true);
      seamResults.push({
        contract: 'casepath.gate2-claim-evidence-seam/1.0.0',
        claim_id: claimId,
        binding_sha256: binding.binding_sha256,
        initial_outcome: initialView.outcome,
        final_outcome: initialView.outcome,
        carryover_origin:'sealed_gate1_qualified_witness',
        typed_abstention: true,
        final_view_sha256: initialView.view_sha256,
      });
    }
    const row = validateLoopView(canonicalView, claimId, detail.state);
    row.detail_sha256 = detail.detail_sha256;
    row.message_sha256 = sha({ subject: detail.message.subject, body: detail.message.body });
    row.artifact_roster_sha256 = sha(binding.observable_artifacts.map(value => ({ artifact_id: value.artifact_id, sha256: value.sha256, size_bytes: value.size_bytes })));
    preRestart.set(claimId, { row, view: canonicalView, detail });
  }
  const seamOutcomeCounts = Object.fromEntries(['next_action', 'decision_ready', 'abstain'].map(outcome => [
    outcome, seamResults.filter(row => row.final_outcome === outcome).length,
  ]));
  check('The 148 fresh seams plus two typed carryovers yield exactly 149 next actions and one abstention',
    seamResults.length === 150
      && new Set(seamResults.map(row => row.claim_id)).size === 150
      && seamOutcomeCounts.next_action === 149
      && seamOutcomeCounts.decision_ready === 0
      && seamOutcomeCounts.abstain === 1
      && seamResults.find(row => row.final_outcome === 'abstain')?.claim_id === MAIN_CARRYOVER_CLAIM_ID
      && seamResults.find(row => row.typed_safe_rejection === true)?.claim_id === NEGATIVE_CARRYOVER_CLAIM_ID);
  check('Claim-bound timing arrays have exact 150/149/149 coverage',
    firstSafeActionTimings.length === 150
      && sourceAcquisitionTimings.length === 149
      && postEvidenceReplanTimings.length === 149
      && new Set(firstSafeActionTimings.map(row => row.claim_id)).size === 150
      && new Set(sourceAcquisitionTimings.map(row => row.claim_id)).size === 149
      && new Set(postEvidenceReplanTimings.map(row => row.claim_id)).size === 149
      && canonical(sourceAcquisitionTimings.map(row => row.claim_id).sort())
        === canonical([NEGATIVE_CARRYOVER_CLAIM_ID, ...carryoverPlan.fresh_claim_ids].sort())
      && canonical(postEvidenceReplanTimings.map(row => row.claim_id).sort())
        === canonical([NEGATIVE_CARRYOVER_CLAIM_ID, ...carryoverPlan.fresh_claim_ids].sort()));
  check('Independent p95 implementations agree and all seam latencies are within 10 seconds',
    p95(firstSafeActionTimings.map(row => row.seconds)) === independentP95(firstSafeActionTimings.map(row => row.seconds))
      && p95(sourceAcquisitionTimings.map(row => row.seconds)) === independentP95(sourceAcquisitionTimings.map(row => row.seconds))
      && p95(postEvidenceReplanTimings.map(row => row.seconds)) === independentP95(postEvidenceReplanTimings.map(row => row.seconds))
      && p95(firstSafeActionTimings.map(row => row.seconds)) <= 10
      && p95(sourceAcquisitionTimings.map(row => row.seconds)) <= 10
      && p95(postEvidenceReplanTimings.map(row => row.seconds)) <= 10);
  check('The Gate 1 rejection plus 148 fresh mutations have claim-bound 150-row queue timings', postMutationQueueSeconds.length === 149
    && new Set(postMutationQueueSeconds.map(row => row.claim_id)).size === 149
    && canonical(postMutationQueueSeconds.map(row => row.claim_id).sort())
      === canonical([NEGATIVE_CARRYOVER_CLAIM_ID, ...carryoverPlan.fresh_claim_ids].sort())
    && postMutationQueueSeconds.every(row => row.row_count === 150
      && row.unique_claim_count === 150 && row.mutation_visible === true), canonical(postMutationQueueSeconds));
  check('All 148 fresh Gate 2 queue mutations have a closed one-row replacement chain',
    queueIsolationReceipts.length === 148
      && new Set(queueIsolationReceipts.map(row => row.claim_id)).size === 148
      && canonical(queueIsolationReceipts.map(row => row.claim_id).sort())
        === canonical([...carryoverPlan.fresh_claim_ids].sort())
      && queueIsolationReceipts.every((row, index) => (
        row.sequence === index + 1
          && row.previous_receipt_sha256 === (index === 0
            ? null : queueIsolationReceipts[index - 1].receipt_sha256)
          && row.changed_claim_ids.length === 1
          && row.changed_claim_ids[0] === row.claim_id
          && row.unchanged_nonfocal_count === 149
          && row.nonfocal_before_sha256 === row.nonfocal_after_sha256
          && row.receipt_sha256 === sha(without(row, 'receipt_sha256'))
      ))
      && negativeEvidence.queue_isolation.claim_id === NEGATIVE_CARRYOVER_CLAIM_ID
      && negativeEvidence.queue_isolation.unchanged_nonfocal_count === 149
      && negativeEvidence.queue_isolation.nonfocal_before_sha256
        === negativeEvidence.queue_isolation.nonfocal_after_sha256,
  canonical({ fresh:queueIsolationReceipts, imported_gate1:negativeEvidence.queue_isolation }));
  check('Post-mutation 150-claim queue p95 independently agrees and is at most 300 ms',
    p95(postMutationQueueSeconds.map(row => row.seconds)) === independentP95(postMutationQueueSeconds.map(row => row.seconds))
      && p95(postMutationQueueSeconds.map(row => row.seconds)) <= 0.300,
  canonical(postMutationQueueSeconds));

  const baseline = await queueAll({ sort: 'priority', limit: 17 });
  for (const mode of SORTS) {
    const actual = await queueAll({ sort: mode, limit: 17 });
    const expected = [...baseline].sort((left, right) => compareTuple(sortKey(left, mode), sortKey(right, mode)));
    check(`Queue sort ${mode} matches independent ordering`, canonical(actual.map(row => row.claim_id)) === canonical(expected.map(row => row.claim_id)));
  }
  const filterFields = [
    ['state', 'workflow_state'], ['readiness', 'readiness_state'], ['claim_type', 'claim_type'], ['urgency', 'urgency'],
  ];
  for (const [parameter, field] of filterFields) {
    for (const value of [...new Set(baseline.map(row => row[field]))].sort()) {
      const actual = await queueAll({ [parameter]: value, sort: 'priority', limit: 17 });
      check(`Queue filter ${parameter}=${value} is exact`, actual.every(row => row[field] === value) && actual.length === baseline.filter(row => row[field] === value).length);
    }
  }
  for (const value of [false, true]) {
    const actual = await queueAll({ failure: String(value), sort: 'priority', limit: 17 });
    check(`Queue failure=${value} is exact`, actual.every(row => row.failure_or_unknown_effect === value) && actual.length === baseline.filter(row => row.failure_or_unknown_effect === value).length);
  }
  for (const value of ['unknown', 'none', 'some']) {
    const predicate = value === 'unknown' ? row => row.pending_evidence_count === null : value === 'none' ? row => row.pending_evidence_count === 0 : row => row.pending_evidence_count > 0;
    const actual = await queueAll({ pending_evidence: value, sort: 'priority', limit: 17 });
    check(`Queue pending_evidence=${value} is exact`, actual.every(predicate) && actual.length === baseline.filter(predicate).length);
  }
  for (const claimId of claimIds) {
    const actual = await queueAll({ q: claimId, sort: 'priority', limit: 17 });
    check(`${claimId}: exact search finds only the claim`, actual.length === 1 && actual[0].claim_id === claimId);
  }
  const cursorPage = await api('/api/claim-loops/v1/workspace/claims?sort=priority&limit=17');
  const changedCursor = await apiRaw(`/api/claim-loops/v1/workspace/claims?sort=urgency&limit=17&cursor=${encodeURIComponent(cursorPage.next_cursor)}`, {}, [409]);
  check('Queue cursor is request-bound', changedCursor.status === 409);
  const tampered = `${cursorPage.next_cursor.slice(0, -1)}${cursorPage.next_cursor.endsWith('A') ? 'B' : 'A'}`;
  const tamperedCursor = await apiRaw(`/api/claim-loops/v1/workspace/claims?sort=priority&limit=17&cursor=${encodeURIComponent(tampered)}`, {}, [409]);
  check('Queue cursor tamper fails closed', tamperedCursor.status === 409);
  const rebuild = await api('/api/claim-loops/v1/workspace/rebuild', { method: 'POST' });
  check('Longitudinal rebuild binds all 150 workspace and ClaimLoop journals', rebuild.contract === 'casepath.workspace-operational-rebuild/1.0.0'
    && rebuild.claim_count === 150 && rebuild.expected_claim_count === 150 && rebuild.authority === 'workspace_and_claim_loop_events'
    && exactSha(rebuild, 'receipt_sha256'));

  const candidateBeforeRestart = await captureCandidateSourceSnapshot({
    requireApiBootReceipt: true,
    allowValidatedWorkspaceJournalAdvance: true,
  });
  check('Executable runtime closure stays exact before the deliberate restart',
    canonical(candidateBeforeRestart.identity) === canonical(candidateStart.identity)
      && canonical(candidateBeforeRestart.apiBootIdentity) === canonical(candidateStart.apiBootIdentity)
      && candidateBeforeRestart.apiBootIdentity.runtime_closure_sha256
        === candidateStart.apiBootIdentity.runtime_closure_sha256);
  const preBoot = candidateBeforeRestart.apiBootIdentity;
  if (path.resolve(preBoot.service_root) === repository) {
    process.kill(preBoot.process_pid, 'SIGTERM');
    const replacement = spawn('/usr/bin/env', [
      '-i',
      `HOME=${process.env.HOME}`,
      'PATH=/usr/bin:/bin:/usr/sbin:/sbin',
      'LANG=C.UTF-8',
      'LC_ALL=C.UTF-8',
      'TZ=UTC',
      `CASEPATH_UV=${path.join(process.env.HOME, '.local/bin/uv')}`,
      'UV_OFFLINE=1',
      'UV_NO_PYTHON_DOWNLOADS=1',
      path.join(repository, 'bin/casepath'),
      'dev',
    ], {
      cwd: repository,
      detached: true,
      stdio: 'ignore',
    });
    replacement.unref();
  } else {
    await execFileAsync('/bin/launchctl', ['kickstart', '-k', `gui/${process.getuid()}/com.casepath.local-product`], { timeout: 30_000 });
  }
  const candidateAfterRestart = await waitForExactCandidateRestart(preBoot, candidateStart.identity);
  check('Restart changes boot identity but preserves source/build', candidateAfterRestart.apiBootIdentity.receipt_file_sha256 !== preBoot.receipt_file_sha256
    && candidateAfterRestart.apiBootIdentity.prior_boot_receipt_file_sha256 === preBoot.receipt_file_sha256
    && canonical(candidateAfterRestart.identity) === canonical(candidateStart.identity)
    && candidateAfterRestart.apiBootIdentity.source_manifest_file_sha256 === preBoot.source_manifest_file_sha256
    && candidateAfterRestart.apiBootIdentity.capsule_roster_sha256 === preBoot.capsule_roster_sha256
    && candidateAfterRestart.apiBootIdentity.static_roster_sha256 === preBoot.static_roster_sha256);
  const pythonRuntimeClosureAfter = await auditPythonRuntimeClosure(candidateAfterRestart);
  check('Restart preserves the exact Python module, .pth, customizer, and metadata closure',
    pythonRuntimeClosureBefore.roster_sha256 === pythonRuntimeClosureAfter.roster_sha256
      && pythonRuntimeClosureBefore.record_roster_sha256 === pythonRuntimeClosureAfter.record_roster_sha256
      && canonical(pythonRuntimeClosureBefore.pth_files) === canonical(pythonRuntimeClosureAfter.pth_files)
      && canonical(pythonRuntimeClosureBefore.customizer_files) === canonical(pythonRuntimeClosureAfter.customizer_files));
  const runtimeClosureAudit = {
    contract: 'casepath.gate2-runtime-closure/1.0.0',
    executable_runtime_authority: {
      candidate_start: {
        closure_sha256: candidateStart.apiBootIdentity.runtime_closure_sha256,
        subordinate_closure_sha256: candidateStart.apiBootIdentity.runtime_subordinate_closure_sha256,
        boot_phases: candidateStart.apiBootReceipt.runtime_closure.phases,
      },
      before_restart: {
        closure_sha256: candidateBeforeRestart.apiBootIdentity.runtime_closure_sha256,
        subordinate_closure_sha256: candidateBeforeRestart.apiBootIdentity.runtime_subordinate_closure_sha256,
        boot_phases: candidateBeforeRestart.apiBootReceipt.runtime_closure.phases,
      },
      after_restart: {
        closure_sha256: candidateAfterRestart.apiBootIdentity.runtime_closure_sha256,
        subordinate_closure_sha256: candidateAfterRestart.apiBootIdentity.runtime_subordinate_closure_sha256,
        boot_phases: candidateAfterRestart.apiBootReceipt.runtime_closure.phases,
      },
      gate2_end: null,
      exact_phase_restart_and_end_match: false,
    },
    installed_non_runtime: installedRuntimeClosureAudit,
    python_environment: {
      before: pythonRuntimeClosureBefore,
      after: pythonRuntimeClosureAfter,
      exact_restart_match: canonical(pythonRuntimeClosureBefore.entries) === canonical(pythonRuntimeClosureAfter.entries),
    },
  };
  const secondSeedReceipt = parseEmbeddedSeedReceipt(candidateAfterRestart, 'Second fresh-root seed');
  check('Second seed replays all 150 imports without duplicating lifecycle effects',
    firstSeedReceipt.event_roster_sha256 === secondSeedReceipt.event_roster_sha256
    && secondSeedReceipt.new_import_count === 0 && secondSeedReceipt.replayed_import_count === 150);
  const journalAudit = await auditRawJournals(candidateAfterRestart.apiBootReceipt.runtime.database_path, claimIds);
  check('Raw journal terminal state hashes bind every pre-restart projection', claimIds.every(claimId => {
    const lifecycle = journalAudit.per_claim[claimId];
    const authority = preRestart.get(claimId).row;
    return lifecycle.workspace_final_state_sha256 === authority.workspace_prefix.state_sha256
      && lifecycle.claim_loop_final_state_sha256 === authority.claim_loop_prefix.state_sha256;
  }));
  const beforeEventHashes = new Set(gate2JournalBeforeRows.map(row => row.event_sha256));
  const gate2AddedEvents = journalAudit.raw_rows.filter(row => !beforeEventHashes.has(row.event_sha256));
  const loopIdToClaim = new Map(claimIds.map(claimId => [journalAudit.per_claim[claimId].claim_loop_id, claimId]));
  const gate2LoopDeltaByClaim = Object.fromEntries(claimIds.map(claimId => [claimId, gate2AddedEvents
    .filter(row => row.session_id === CLAIM_LOOP_SESSION_ID && loopIdToClaim.get(row.loop_id) === claimId)
    .map(row => row.event.event_type)]));
  const gate2WorkspaceDeltaByClaim = Object.fromEntries(claimIds.map(claimId => [claimId, gate2AddedEvents
    .filter(row => row.session_id === WORKSPACE_SESSION_ID && row.loop_id === `workspace.${claimId}`)
    .map(row => row.event.event_type)]));
  const carryoverClaimIds = carryoverPlan.ordered_carryover_claim_ids;
  const carryoverClaimIdSet = new Set(carryoverClaimIds);
  const afterRowsByPrimaryKey = new Map(journalAudit.raw_rows.map(row => [
    `${row.session_id}\u0000${row.loop_id}\u0000${row.sequence}`,
    row,
  ]));
  check('Gate 2 raw journal delta is exactly 148 fresh start/ensure/evidence seams and zero carryover effect',
    gate2AddedEvents.length === 740
      && gate2AddedEvents.filter(row => row.session_id === CLAIM_LOOP_SESSION_ID).length === 592
      && gate2AddedEvents.filter(row => row.session_id === WORKSPACE_SESSION_ID).length === 148
      && carryoverClaimIds.every(claimId => canonical(gate2LoopDeltaByClaim[claimId]) === canonical([])
        && canonical(gate2WorkspaceDeltaByClaim[claimId]) === canonical([]))
      && claimIds.filter(value => !carryoverClaimIdSet.has(value)).every(claimId => canonical(gate2LoopDeltaByClaim[claimId]) === canonical([
        'LOOP_CREATED',
        'ACTION_SELECTED',
        'ACTION_DISPATCH_STARTED',
        'OBSERVATION_INGESTED',
      ]) && canonical(gate2WorkspaceDeltaByClaim[claimId]) === canonical(['WORKSPACE_PROCESSING_STARTED'])));
  check('Both Gate 1 carryover prefixes and every pre-Gate-2 journal row survive restart byte-identically',
    gate2JournalBeforeRows.every(row => canonical(afterRowsByPrimaryKey.get(
      `${row.session_id}\u0000${row.loop_id}\u0000${row.sequence}`,
    )) === canonical(row))
      && carryoverClaimIds.every(carryoverClaimId => gate2JournalBeforeRows.filter(row => (
        row.loop_id === `workspace.${carryoverClaimId}`
          || (row.session_id === CLAIM_LOOP_SESSION_ID && loopIdToClaim.get(row.loop_id) === carryoverClaimId)
      )).length > 2));

  const gate2AuthorityAfter = await snapshotRegularFiles(authorityRoot);
  const authorityBeforeByPath = new Map(gate2AuthorityBefore.map(row => [row.relative_path, row]));
  const authorityAfterByPath = new Map(gate2AuthorityAfter.map(row => [row.relative_path, row]));
  const gate2AuthorityDelta = gate2AuthorityAfter.filter(row => !authorityBeforeByPath.has(row.relative_path));
  check('Gate 2 filesystem authority is append-only and records every actionable claim',
    gate2AuthorityBefore.every(row => canonical(authorityAfterByPath.get(row.relative_path)) === canonical(row))
      && gate2AuthorityDelta.length > 0
      && gate2AuthorityDelta.every(row => row.relative_path.startsWith('authority-v3/')));
  const gate2SidecarsAfter = await readAuthoritySidecars(databasePath);
  const beforeSidecarHashes = new Set(gate2SidecarsBefore.map(row => `${row.kind}:${row.receipt_sha256}`));
  const sidecarDelta = gate2SidecarsAfter.filter(row => !beforeSidecarHashes.has(`${row.kind}:${row.receipt_sha256}`));
  const actionableLoopIds = new Set(claimIds.filter(value => !carryoverClaimIdSet.has(value)).map(claimId => preRestart.get(claimId).view.loop_state.loop_id));
  check('Gate 2 sidecars bind exactly 148 fresh acquisitions and 148 fresh tool artifacts',
    sidecarDelta.length === 296
      && sidecarDelta.filter(row => row.kind === 'acquisition').length === 148
      && sidecarDelta.filter(row => row.kind === 'tool_artifact').length === 148
      && new Set(sidecarDelta.map(row => row.loop_id)).size === 148
      && sidecarDelta.every(row => actionableLoopIds.has(row.loop_id)
        && row.payload.receipt_sha256 === claimLoopSha(without(row.payload, 'receipt_sha256')))
      && sidecarDelta.filter(row => row.kind === 'acquisition').every(row => {
        const raw = Buffer.from(row.raw_payload_hex, 'hex');
        return row.status === 'observed'
          && row.payload.status === 'observed'
          && row.payload.raw_byte_count === raw.length
          && row.payload.raw_bytes_sha256 === sha(raw)
          && row.payload.sanitized_content === raw.toString('utf8');
      }));
  const authorityDeltaAudit = await auditGate2AuthorityDelta({
    root: authorityRoot,
    delta: gate2AuthorityDelta,
    seams: seamResults,
    sidecars: sidecarDelta,
    rawJournalRows: journalAudit.raw_rows,
    carryoverClaimIds,
  });
  check('Every Gate 2 authority file is uniquely and transitively bound to one seam',
    authorityDeltaAudit.auditRows.length === 148
      && authorityDeltaAudit.usedPathCount === 148 * ADMITTED_AUTHORITY_KINDS.length
      && ADMITTED_AUTHORITY_KINDS.every(
        kind => authorityDeltaAudit.kindCounts[kind] === 148,
      )
      && authorityDeltaAudit.receipt.receipt_sha256
        === sha(without(authorityDeltaAudit.receipt, 'receipt_sha256')));

  const rawReplay = await independentReplayRawJournals(
    journalAudit.raw_rows,
    claimIds,
    preRestart,
    authorityRoot,
    candidateAfterRestart.apiBootIdentity.execution_root,
  );
  const rawEventReceiptKeys = new Set(journalAudit.raw_rows.map(row => canonical([
    row.session_id, row.loop_id, row.sequence, row.event_sha256, row.event.resulting_state_sha256,
  ])));
  check('Independent replay emits one exact state receipt per raw journal event',
    rawReplay.stateReceiptRows.length === journalAudit.raw_rows.length
      && new Set(rawReplay.stateReceiptRows.map(row => canonical([
        row.session_id,
        row.session_id === WORKSPACE_SESSION_ID ? `workspace.${row.claim_id}`
          : journalAudit.per_claim[row.claim_id].claim_loop_id,
        row.sequence,
        row.event_sha256,
        row.recomputed_state_sha256,
      ]))).size === journalAudit.raw_rows.length
      && rawReplay.stateReceiptRows.every(row => row.recomputed_state_sha256 === row.expected_state_sha256
        && rawEventReceiptKeys.has(canonical([
          row.session_id,
          row.session_id === WORKSPACE_SESSION_ID ? `workspace.${row.claim_id}`
            : journalAudit.per_claim[row.claim_id].claim_loop_id,
          row.sequence,
          row.event_sha256,
          row.expected_state_sha256,
        ]))));
  const journalRowsForClaim = claimId => journalAudit.raw_rows.filter(row => (
    (row.session_id === WORKSPACE_SESSION_ID && row.loop_id === `workspace.${claimId}`)
      || (row.session_id === CLAIM_LOOP_SESSION_ID
        && row.loop_id === journalAudit.per_claim[claimId].claim_loop_id)
  ));
  check('Gate 2 replays the exact original Gate 1 carryover journals without truncation or synthesis',
    canonical(journalRowsForClaim(NEGATIVE_CARRYOVER_CLAIM_ID))
      === canonical(gate1NegativeControl.evidence.journal_after)
      && canonical(journalRowsForClaim(MAIN_CARRYOVER_CLAIM_ID))
        === canonical(gate1AuthorityChain.raw_journal_after));
  const carryoverPermutationProofs = new Map([
    [NEGATIVE_CARRYOVER_CLAIM_ID, {
      scope:'gate1_pre_rejection_selected_prefix_plus_zero_effect_rejection_proof',
      loop_event_count:2,
      view:gate1NegativeControl.evidence.before,
    }],
    [MAIN_CARRYOVER_CLAIM_ID, {
      scope:'gate1_first_admitted_seam_prefix_plus_full_terminal_replay',
      loop_event_count:4,
      view:gate1AuthorityChain.crash_recovery.after,
    }],
  ]);
  check('Carryover identity-permutation prefixes are exact and separately backed by full journal replay',
    canonical(rawReplay.loopEventsByClaim.get(NEGATIVE_CARRYOVER_CLAIM_ID).slice(0, 2).map(row => row.event_type))
      === canonical(['LOOP_CREATED', 'ACTION_SELECTED'])
      && canonical(rawReplay.loopEventsByClaim.get(MAIN_CARRYOVER_CLAIM_ID).slice(0, 4).map(row => row.event_type))
        === canonical(['LOOP_CREATED', 'ACTION_SELECTED', 'ACTION_DISPATCH_STARTED', 'OBSERVATION_INGESTED'])
      && carryoverPermutationProofs.get(NEGATIVE_CARRYOVER_CLAIM_ID).view.loop_state.state_sha256
        === rawReplay.loopEventsByClaim.get(NEGATIVE_CARRYOVER_CLAIM_ID)[1].resulting_state_sha256
      && carryoverPermutationProofs.get(MAIN_CARRYOVER_CLAIM_ID).view.loop_state.state_sha256
        === rawReplay.loopEventsByClaim.get(MAIN_CARRYOVER_CLAIM_ID)[3].resulting_state_sha256
      && rawReplay.replayRows.find(row => row.claim_id === NEGATIVE_CARRYOVER_CLAIM_ID)
        .claim_loop_final_state_sha256 === preRestart.get(NEGATIVE_CARRYOVER_CLAIM_ID).view.loop_state.state_sha256
      && rawReplay.replayRows.find(row => row.claim_id === MAIN_CARRYOVER_CLAIM_ID)
        .claim_loop_final_state_sha256 === preRestart.get(MAIN_CARRYOVER_CLAIM_ID).view.loop_state.state_sha256);
  const productionPermutation = await runProductionProjectionPermutation(
    candidateAfterRestart,
    rawReplay,
    claimIds,
    preRestart,
    carryoverPermutationProofs,
  );
  runtimeClosureAudit.permutation_subprocess = {
    frozen_launch: productionPermutation.frozenPermutationLaunch,
    child_runtime: productionPermutation.childRuntime,
    exact_boot_closure_binding:
      productionPermutation.childRuntime.sys_executable
        === candidateAfterRestart.apiBootIdentity.python_runtime.stated_path
      && productionPermutation.childRuntime.sys_executable_realpath
        === candidateAfterRestart.apiBootIdentity.python_runtime.real_path
      && productionPermutation.frozenPermutationLaunch.helper.sha256
        === sha(await fs.readFile(path.join(
          candidateAfterRestart.apiBootIdentity.execution_root,
          'casepath-qa/production-projection-permutation-v1.py',
        ))),
  };
  check('Permutation child runtime and helper are bound to the executable boot closure',
    runtimeClosureAudit.permutation_subprocess.exact_boot_closure_binding === true);
  for (const result of productionPermutation.results) {
    const value = preRestart.get(result.claim_id).row;
    value.identity_permutation = result;
    value.independent_journal_replay = rawReplay.replayRows.find(row => row.claim_id === result.claim_id);
  }
  check('All 150 claims have raw-event replay and production-path identity permutation proof',
    rawReplay.replayRows.length === 150
      && productionPermutation.results.length === 150
      && productionPermutation.results.filter(row => row.permutation_scope === 'complete_four_event_gate2_seam').length === 148
      && productionPermutation.results.filter(row => row.permutation_scope.startsWith('gate1_')).length === 2
      && [...preRestart.values()].every(value => value.row.identity_permutation?.identity_neutral_semantics_equal === true
        && value.row.independent_journal_replay?.semantic_projection_sha256));
  const carryoverPermutationBindings = carryoverClaimIds.map(claimId => {
    const loopId = journalAudit.per_claim[claimId].claim_loop_id;
    const fullJournal = journalRowsForClaim(claimId);
    const replayResult = rawReplay.replayRows.find(row => row.claim_id === claimId);
    const permutationResult = productionPermutation.results.find(row => row.claim_id === claimId);
    const sidecars = gate2SidecarsBefore.filter(row => row.loop_id === loopId);
    const material = {
      contract:'casepath.gate2-carryover-permutation-binding/1.0.0',
      claim_id:claimId,
      role:claimId === NEGATIVE_CARRYOVER_CLAIM_ID
        ? 'safe_rejection_zero_effect'
        : 'qualified_correction_terminal_abstention',
      gate1_source_receipt:{
        path:claimId === NEGATIVE_CARRYOVER_CLAIM_ID
          ? 'negative-rejection-control.json'
          : 'authority-chain.json',
        file_sha256:claimId === NEGATIVE_CARRYOVER_CLAIM_ID
          ? sha(gate1NegativeControlRaw)
          : sha(gate1AuthorityChainRaw),
      },
      full_raw_event_count:fullJournal.length,
      full_raw_event_roster_sha256:sha(fullJournal),
      authority_state:{
        workspace_state_sha256:preRestart.get(claimId).detail.state.state_sha256,
        claim_loop_state_sha256:preRestart.get(claimId).view.loop_state.state_sha256,
        operational_projection_sha256:preRestart.get(claimId).view.operational_projection.projection_sha256,
      },
      pre_gate2_sidecars:{
        row_count:sidecars.length,
        acquisition_count:sidecars.filter(row => row.kind === 'acquisition').length,
        tool_artifact_count:sidecars.filter(row => row.kind === 'tool_artifact').length,
        roster_sha256:sha(sidecars),
      },
      complete_terminal_replay:{
        result_sha256:sha(replayResult),
        final_state_sha256:replayResult.claim_loop_final_state_sha256,
        semantic_projection_sha256:replayResult.semantic_projection_sha256,
      },
      topology_scoped_permutation:{
        scope:permutationResult.permutation_scope,
        input_receipt_sha256:permutationResult.input_receipt_sha256,
        result_receipt_sha256:permutationResult.receipt_sha256,
        identity_neutral_semantics_equal:permutationResult.identity_neutral_semantics_equal,
      },
    };
    return { ...material, receipt_sha256:sha(material) };
  });
  check('Both carryovers bind original events, authority state, sidecars, full replay, and truthful permutation scope',
    carryoverPermutationBindings.length === 2
      && carryoverPermutationBindings.every(row => row.receipt_sha256 === sha(without(row, 'receipt_sha256'))
        && row.complete_terminal_replay.final_state_sha256 === row.authority_state.claim_loop_state_sha256
        && row.topology_scoped_permutation.identity_neutral_semantics_equal === true)
      && carryoverPermutationBindings.find(row => row.claim_id === NEGATIVE_CARRYOVER_CLAIM_ID)
        .pre_gate2_sidecars.acquisition_count === 1
      && carryoverPermutationBindings.find(row => row.claim_id === NEGATIVE_CARRYOVER_CLAIM_ID)
        .pre_gate2_sidecars.tool_artifact_count === 0
      && carryoverPermutationBindings.find(row => row.claim_id === MAIN_CARRYOVER_CLAIM_ID)
        .pre_gate2_sidecars.acquisition_count > 0
      && carryoverPermutationBindings.find(row => row.claim_id === MAIN_CARRYOVER_CLAIM_ID)
        .pre_gate2_sidecars.acquisition_count
        === carryoverPermutationBindings.find(row => row.claim_id === MAIN_CARRYOVER_CLAIM_ID)
          .pre_gate2_sidecars.tool_artifact_count);

  browser = await chromium.launch({ executablePath, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const browserReceipt = await captureBrowserExecutionReceipt({
    gatePath: fileURLToPath(import.meta.url),
    outputPath: out,
    outputEnvironmentKey: 'CASEPATH_WORKSPACE_150_QA_OUT',
    browserVersion: browser.version(),
    baseUrl: BASE,
    apiUrl: BASE,
  });
  const browserReceiptRaw = Buffer.from(`${JSON.stringify(browserReceipt, null, 2)}\n`);
  await fs.writeFile(path.join(out, 'browser-execution-receipt.json'), browserReceiptRaw, { flag: 'wx' });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  context.on('page', page => {
    page.on('pageerror', error => browserErrors.push({ kind: 'pageerror', message: String(error) }));
    page.on('console', message => { if (message.type() === 'error') browserErrors.push({ kind: 'console', message: message.text() }); });
    page.on('response', response => {
      const task = (async () => {
        const url = new URL(response.url());
        try {
          const body = Buffer.from(await response.body());
          browserNetwork.push({
            kind: 'response',
            method: response.request().method(),
            resource_type: response.request().resourceType(),
            url: url.href,
            status: response.status(),
            content_type: response.headers()['content-type'] || null,
            body_size_bytes: body.length,
            body_sha256: sha(body),
          });
        } catch (error) {
          browserNetwork.push({
            kind: 'response',
            method: response.request().method(),
            resource_type: response.request().resourceType(),
            url: url.href,
            status: response.status(),
            body_error: String(error),
          });
        }
      })();
      browserNetworkTasks.add(task);
      task.finally(() => browserNetworkTasks.delete(task));
    });
  });
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    const body = route.request().postDataBuffer();
    browserNetwork.push({
      kind: 'request',
      method: route.request().method(),
      resource_type: route.request().resourceType(),
      url: url.href,
      body_size_bytes: body?.length || 0,
      body_sha256: body ? sha(body) : null,
    });
    if (url.origin !== BASE_ORIGIN) return route.abort('blockedbyclient');
    return route.continue();
  });
  const page = await context.newPage();
  const firstPriorityPageIds = new Set(baseline.slice(0, 25).map(row => row.claim_id));
  const deepLinkClaimId = baseline.at(-1).claim_id;
  const expectedDeepLinkPriority = baseline.at(-1).priority_tuple;
  check('Deep-link regression target is outside the initial 25-row priority page', !firstPriorityPageIds.has(deepLinkClaimId));
  let releaseBroadQueue;
  let releaseTargetedPriority;
  let markBroadQueueEntered;
  let markTargetedPriorityEntered;
  let broadQueuePending = true;
  let targetedPriorityPending = true;
  const broadQueueReleased = new Promise(resolve => { releaseBroadQueue = resolve; });
  const targetedPriorityReleased = new Promise(resolve => { releaseTargetedPriority = resolve; });
  const broadQueueEntered = new Promise(resolve => { markBroadQueueEntered = resolve; });
  const targetedPriorityEntered = new Promise(resolve => { markTargetedPriorityEntered = resolve; });
  const initialQueuePattern = `${BASE}/api/claim-loops/v1/workspace/claims?*`;
  const holdInitialQueue = async route => {
    if (route.request().method() === 'GET') {
      const url = new URL(route.request().url());
      const targeted = url.searchParams.get('q') === deepLinkClaimId && url.searchParams.get('limit') === '1';
      const broad = !url.searchParams.has('q') && url.searchParams.get('limit') === '25'
        && url.searchParams.get('sort') === 'priority' && !url.searchParams.has('cursor');
      if (targeted) {
        if (targetedPriorityPending) {
          targetedPriorityPending = false;
          markTargetedPriorityEntered();
        }
        await targetedPriorityReleased;
      } else if (broad) {
        if (broadQueuePending) {
          broadQueuePending = false;
          markBroadQueueEntered();
        }
        await broadQueueReleased;
      }
    }
    await route.fallback();
  };
  await context.route(initialQueuePattern, holdInitialQueue);
  try {
    await page.goto(`${BASE}/?ui=final#claim=${encodeURIComponent(deepLinkClaimId)}`, { waitUntil: 'domcontentloaded', timeout: 30_000 });
    await Promise.race([
      Promise.all([broadQueueEntered, targetedPriorityEntered]),
      new Promise((_, reject) => setTimeout(() => reject(new Error('broad and targeted priority requests were not both issued')), 10_000)),
    ]);
    await page.waitForFunction(id => document.querySelector('.cw-detail-title small')?.textContent === id
      && Boolean(document.querySelector('#cwLoopWorkbench')?.dataset.outcome), deepLinkClaimId, { timeout: 10_000 });
    check('Deep-linked claim opens independently of full queue hydration', await page.locator('.cw-detail-title small').textContent() === deepLinkClaimId
      && Boolean(await page.locator('#cwLoopWorkbench').getAttribute('data-outcome')));
    check('Broad queue remains unavailable before targeted lookup', await page.locator('[data-claim-id]').count() === 0);
    const ownerSentinel = 'typed-input-survives-priority-hydration';
    await page.locator('#cwOwnerInput').evaluate((input, value) => { input.value = value; }, ownerSentinel);
    releaseTargetedPriority();
    await page.waitForFunction(() => document.querySelectorAll('#cwExplainablePriority [data-priority-dimension]').length > 0, null, { timeout: 10_000 });
    const targetedPriority = await page.locator('#cwExplainablePriority [data-priority-dimension]').evaluateAll(rows => rows.map(row => ({
      dimension: row.dataset.priorityDimension,
      value: JSON.parse(row.dataset.priorityValueJson),
    })));
    check('Off-page targeted lookup renders the exact typed priority tuple while the broad queue is blocked', canonical(targetedPriority) === canonical(expectedDeepLinkPriority)
      && await page.locator('[data-claim-id]').count() === 0);
    check('Targeted priority hydration preserves an existing input value', await page.locator('#cwOwnerInput').inputValue() === ownerSentinel);
    releaseBroadQueue();
    await page.waitForFunction(() => document.querySelectorAll('[data-claim-id]').length === 25, null, { timeout: 30_000 });
    const hydratedPriority = await page.locator('#cwExplainablePriority [data-priority-dimension]').evaluateAll(rows => rows.map(row => ({
      dimension: row.dataset.priorityDimension,
      value: JSON.parse(row.dataset.priorityValueJson),
    })));
    check('Broad queue hydration preserves the off-page priority tuple and user input', canonical(hydratedPriority) === canonical(expectedDeepLinkPriority)
      && await page.locator('#cwOwnerInput').inputValue() === ownerSentinel);
  } finally {
    releaseTargetedPriority();
    releaseBroadQueue();
    await context.unroute(initialQueuePattern, holdInitialQueue);
  }
  const negativeClaimId = baseline.at(-2).claim_id;
  check('Priority lookup failure target is outside the initial 25-row page', !firstPriorityPageIds.has(negativeClaimId));
  const negativePage = await context.newPage();
  let releaseRejectedPriority;
  let markRejectedPriorityEntered;
  const rejectedPriorityReleased = new Promise(resolve => { releaseRejectedPriority = resolve; });
  const rejectedPriorityEntered = new Promise(resolve => { markRejectedPriorityEntered = resolve; });
  let rejectedPriorityPending = true;
  const rejectTargetedPriority = async route => {
    const url = new URL(route.request().url());
    if (route.request().method() === 'GET' && url.searchParams.get('q') === negativeClaimId && url.searchParams.get('limit') === '1') {
      if (rejectedPriorityPending) {
        rejectedPriorityPending = false;
        markRejectedPriorityEntered();
      }
      await rejectedPriorityReleased;
      const upstream = await route.fetch();
      const forged = await upstream.json();
      forged.items[0].priority_tuple[0].value = forged.items[0].priority_tuple[0].value === 0 ? 1 : 0;
      forged.items[0].row_sha256 = sha(without(forged.items[0], 'row_sha256'));
      forged.projection_sha256 = sha(without(forged, 'projection_sha256'));
      await route.fulfill({response:upstream, json:forged});
      return;
    }
    await route.fallback();
  };
  await context.route(initialQueuePattern, rejectTargetedPriority);
  try {
    await negativePage.goto(`${BASE}/?ui=final#claim=${encodeURIComponent(negativeClaimId)}`, { waitUntil: 'domcontentloaded', timeout: 30_000 });
    await Promise.race([
      rejectedPriorityEntered,
      new Promise((_, reject) => setTimeout(() => reject(new Error('negative targeted priority request was not issued')), 10_000)),
    ]);
    await negativePage.waitForFunction(id => document.querySelector('.cw-detail-title small')?.textContent === id
      && Boolean(document.querySelector('#cwLoopWorkbench')?.dataset.outcome), negativeClaimId, { timeout: 10_000 });
    const negativeSentinel = 'typed-input-survives-rejected-priority';
    await negativePage.locator('#cwOwnerInput').evaluate((input, value) => { input.value = value; }, negativeSentinel);
    releaseRejectedPriority();
    await negativePage.waitForFunction(() => document.querySelector('#cwExplainablePriority [data-priority-status]')?.textContent
      === 'Explainable priority is unavailable because its authoritative queue receipt could not be verified.', null, { timeout: 10_000 });
    check('Self-hashed but semantically contradictory priority fails closed without input loss', await negativePage.locator('#cwExplainablePriority [data-priority-dimension]').count() === 0
      && await negativePage.locator('#cwOwnerInput').inputValue() === negativeSentinel);
  } finally {
    releaseRejectedPriority();
    await context.unroute(initialQueuePattern, rejectTargetedPriority);
    await negativePage.close();
  }
  const browserControlMatrix = await exerciseBrowserQueueControls(page, baseline);
  check('Browser exercises every sort/filter/pagination dimension and all corpus-supported searches',
    browserControlMatrix.sorts.length === SORTS.length
      && new Set(browserControlMatrix.sorts.map(row => row.request_parameters.sort)).size === SORTS.length
      && new Set(browserControlMatrix.sorts.map(row => canonical(row.response_item_ids))).size > 1
      && browserControlMatrix.pagination.length === Math.ceil(150 / 25) - 1
      && browserControlMatrix.pagination.at(-1)?.visible_item_ids.length === 150
      && new Set(browserControlMatrix.filters.map(row => Object.keys(row.request_parameters)
        .find(key => ['state','readiness','claim_type','owner','urgency','failure','pending_evidence'].includes(key))))
        .size === 7
      && browserControlMatrix.searches.some(row => row.scenario === 'search:subject' && row.expected_total > 0)
      && browserControlMatrix.searches.some(row => row.scenario === 'search:owner' && row.expected_total > 0
        || row.scenario === 'search:owner:vacuous-unassigned-only' && row.request_not_issued === true)
      && browserControlMatrix.searches.some(row => row.expected_total === 0),
  canonical(browserControlMatrix));
  for (const claimId of claimIds) {
    const before = preRestart.get(claimId);
    const detail = await api(`/api/claim-loops/v1/workspace/claims/${claimId}`);
    const view = await api(`/api/claim-loops/v1/workspace/claims/${claimId}/loop`);
    const after = validateLoopView(view, claimId, detail.state);
    const binding = corpusManifest.claims.find(row => row.claim_id === claimId);
    after.detail_sha256 = detail.detail_sha256;
    after.message_sha256 = sha({ subject: detail.message.subject, body: detail.message.body });
    after.artifact_roster_sha256 = sha(binding.observable_artifacts.map(value => ({
      artifact_id: value.artifact_id,
      sha256: value.sha256,
      size_bytes: value.size_bytes,
    })));
    const preRestartAuthority = without(without(before.row, 'identity_permutation'), 'independent_journal_replay');
    check(`${claimId}: restart replay is byte-identical by authority hashes`,
      detail.detail_sha256 === before.detail.detail_sha256
        && canonical(after) === canonical(preRestartAuthority));
    await page.goto(`${BASE}/?ui=final#claim=${encodeURIComponent(claimId)}`, { waitUntil: 'domcontentloaded', timeout: 30_000 });
    await page.waitForFunction(id => document.querySelector('.cw-detail-title small')?.textContent === id && Boolean(document.querySelector('#cwLoopWorkbench')?.dataset.outcome), claimId, { timeout: 30_000 });
    const dom = await captureClaimDom(page);
    const sourceClaim = JSON.parse(await fs.readFile(path.join(corpusRoot, corpusManifest.claims.find(row => row.claim_id === claimId).claim.path), 'utf8'));
    check(`${claimId}: fresh browser shows exact source and authority`, dom.title === sourceClaim.customer_message.subject && dom.body === sourceClaim.customer_message.body
      && dom.claim_id === claimId && dom.outcome === view.outcome && dom.projection_sha256 === view.operational_projection.projection_sha256
      && dom.action_sha256 === (view.loop_state.selected_action?.action_sha256 || null)
      && dom.proposal === (view.loop_state.selected_action?.title || label(view.outcome))
      && dom.current_process_cells[0]?.value === view.operational_projection.current_process.node_title
      && dom.current_process_cells[1]?.value === (view.operational_projection.controlling_decision?.title || 'No controlling uncertainty')
      && dom.current_process_cells[2]?.value === label(view.operational_projection.workflow_state)
      && dom.principal_blocker === view.operational_projection.principal_blocker
      && canonical(dom.next_state) === canonical(view.operational_projection.next_state)
      && canonical(dom.role_receipts.map(row => ({ id: row.id, receipt_sha256: row.receipt_sha256 }))) === canonical(ROLE_IDS.map((id, index) => ({
        id, receipt_sha256: view.loop_state.six_agent_cycle_receipt.agent_receipt_sha256s[index],
      })))
      && canonical(dom.gate_receipts.map(row => ({ id: row.id, receipt_sha256: row.receipt_sha256 }))) === canonical(GATE_IDS.map((id, index) => ({
        id, receipt_sha256: view.loop_state.six_agent_cycle_receipt.gate_receipt_sha256s[index],
      }))));
    const classCounts = Object.fromEntries(dom.classes.map(row => [row.name, row.count]));
    check(`${claimId}: browser exposes all six exact evidence classes`, dom.classes.length === 6 && canonical(Object.keys(classCounts).sort()) === canonical([...EVIDENCE_CLASSES].sort())
      && canonical(classCounts) === canonical(view.operational_projection.evidence_class_counts));
    const actualEvidenceItems = dom.classes.flatMap(row => row.items.map(item => ({
      evidence_item_id: item.evidence_item_id,
      title: item.title,
      fact_id: item.fact_id,
      fact_state: item.fact_state,
      raw_status: item.raw_status,
      evidence_class: row.name,
      obligation_status: item.obligation_status,
      mandatory_now: item.mandatory_now,
      current_path: item.current_path,
      source_ref_ids: item.source_ref_ids,
      provenance_edge_sha256s: item.provenance_edge_sha256s,
    }))).sort((left, right) => left.evidence_item_id.localeCompare(right.evidence_item_id));
    const expectedEvidenceItems = [...view.operational_projection.evidence_items]
      .sort((left, right) => left.evidence_item_id.localeCompare(right.evidence_item_id));
    check(`${claimId}: browser evidence semantics and provenance match authority`,
      new Set(actualEvidenceItems.map(row => row.evidence_item_id)).size === actualEvidenceItems.length
        && canonical(actualEvidenceItems) === canonical(expectedEvidenceItems));
    const expectedObservations = view.loop_state.observations.map(observation => ({
      observation_sha256: observation.observation_sha256,
      fact_id: observation.fact_id,
      evidence_item_id: observation.evidence_item_id,
      fact_state: observation.fact_state,
      normalized_value: observation.normalized_value,
      evidence_status: observation.evidence_status,
      source_ref: observation.source_refs[0],
      explanation: observation.explanation,
      value: observation.source_refs[0]?.sanitized_excerpt || observation.value,
      source_copy: `Immutable source SHA ${observation.source_refs[0]?.source_sha256.slice(0, 16)}…`,
    }));
    check(`${claimId}: browser admitted observations expose exact source authority`,
      canonical(dom.observations) === canonical(expectedObservations));
    const totalEvidence = EVIDENCE_CLASSES.reduce((sum, name) => sum + classCounts[name], 0);
    const resolvedEvidence = classCounts.received + classCounts.irrelevant;
    const expectedProgressCopy = `${resolvedEvidence} of ${totalEvidence} resolved · ${classCounts.received} received · ${classCounts.irrelevant} irrelevant · ${classCounts.missing} missing · ${classCounts.insufficient} insufficient · ${classCounts.conditional} conditional · ${classCounts.unknown} unknown`;
    const expectedDiagnostics = {
      loop_id: view.loop_state.loop_id,
      revision: view.loop_state.revision,
      state_sha256: view.loop_state.state_sha256,
      last_event_sha256: view.loop_state.last_event_sha256,
      cycle_receipt_sha256: view.loop_state.six_agent_cycle_receipt.receipt_sha256,
      audit_sha256: view.audit.receipt_sha256,
      model_calls: view.audit.model_calls,
      provider_calls: view.audit.provider_calls,
      cost_usd: view.audit.cost_usd,
    };
    const expectedStatus = view.outcome === 'decision_ready'
      ? 'The six-role traversal and three deterministic gates certify a decision-ready packet.'
      : view.outcome === 'abstain'
        ? `The system abstained safely: ${view.loop_state.abstain_reason || 'the required evidence is unresolved'}`
        : view.loop_state.selected_action
          ? 'CasePath selected one bounded evidence obligation. Request one admitted source span; the server alone selects, interprets, and authorizes its meaning.'
          : 'The journal is processing the accepted transition.';
    const expectedSafetyBoundary = view.outcome === 'decision_ready'
      ? 'The packet is evidence-ready, but CasePath still cannot approve, deny, pay, or close the claim.'
      : view.outcome === 'abstain'
        ? 'Mandatory evidence remains unresolved. CasePath stopped rather than infer an unsupported fact.'
        : view.outcome === 'processing'
          ? 'One journaled transition is in flight. No second action is available until its receipt is reconciled.'
          : 'This action records one exact evidence object. It cannot approve, deny, pay, or close the claim.';
    check(`${claimId}: progress, status, safety, and activity receipts are exact`, totalEvidence > 0 && dom.progress_present
      && Number(dom.progress_now) === Math.round((resolvedEvidence / totalEvidence) * 100)
      && dom.evidence_readiness === `${view.operational_projection.pending_evidence_count} current mandatory unresolved`
      && dom.progress_copy === expectedProgressCopy
      && canonical(dom.diagnostics) === canonical(expectedDiagnostics)
      && dom.verified_line === 'Verified: 6 roles · 3 gates · zero provider calls.'
      && dom.status === expectedStatus
      && dom.safety_boundary === expectedSafetyBoundary
      && (view.decision_packet
        ? dom.terminal_receipt.includes(view.decision_packet.packet_sha256.slice(0, 16))
        : dom.terminal_receipt === ''));
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30_000 });
    await page.waitForFunction(id => document.querySelector('.cw-detail-title small')?.textContent === id
      && Boolean(document.querySelector('#cwLoopWorkbench')?.dataset.outcome), claimId, { timeout: 30_000 });
    const reloadedDom = await captureClaimDom(page);
    check(`${claimId}: real page reload preserves the exact rendered authority`,
      canonical(reloadedDom) === canonical(dom));
    before.row.visible_dom = dom;
    before.row.visible_dom_sha256 = sha(dom);
    before.row.reloaded_dom_sha256 = sha(reloadedDom);
  }
  await page.waitForFunction(() => document.querySelectorAll('[data-claim-id]').length === 25, null, { timeout: 30_000 });
  check('Final browser queue settles before the terminal authority snapshot', await page.locator('[data-claim-id]').count() === 25);
  const ledgerAfterResponse = await apiRaw('/api/model-ledger');
  const ledgerAfter = ledgerAfterResponse.body;
  await Promise.all([...browserNetworkTasks]);
  await context.close();
  check('All 150 browser claims stayed on canonical localhost with exact response evidence', browserNetwork.length > 0
    && browserNetwork.every(row => new URL(row.url).origin === BASE_ORIGIN)
    && browserNetwork.filter(row => row.kind === 'request').length > 0
    && browserNetwork.filter(row => row.kind === 'response').length > 0
    && browserNetwork.filter(row => row.kind === 'response').every(row => Number.isInteger(row.status)
      && /^[0-9a-f]{64}$/.test(row.body_sha256 || '') && !row.body_error));
  check('All 150 post-restart browser inspections had zero runtime errors', browserErrors.length === 0, canonical(browserErrors));

  const candidateEnd = await captureCandidateSourceSnapshot({
    requireApiBootReceipt: true,
    allowValidatedWorkspaceJournalAdvance: true,
  });
  check('Source/build/runtime identity stayed exact through the full Gate 2 journey', canonical(candidateEnd.identity) === canonical(candidateAfterRestart.identity)
    && canonical(candidateEnd.apiBootIdentity) === canonical(candidateAfterRestart.apiBootIdentity));
  runtimeClosureAudit.executable_runtime_authority.gate2_end = {
    closure_sha256: candidateEnd.apiBootIdentity.runtime_closure_sha256,
    subordinate_closure_sha256: candidateEnd.apiBootIdentity.runtime_subordinate_closure_sha256,
    boot_phases: candidateEnd.apiBootReceipt.runtime_closure.phases,
  };
  const executableClosurePhases = Object.values(runtimeClosureAudit.executable_runtime_authority)
    .filter(value => value && typeof value === 'object');
  runtimeClosureAudit.executable_runtime_authority.exact_phase_restart_and_end_match =
    executableClosurePhases.length === 4
    && executableClosurePhases.every(value => value.closure_sha256
      === candidateStart.apiBootIdentity.runtime_closure_sha256
      && canonical(value.subordinate_closure_sha256)
        === canonical(candidateStart.apiBootIdentity.runtime_subordinate_closure_sha256)
      && value.boot_phases.length === 3
      && value.boot_phases.every(phase => phase.closure_sha256 === value.closure_sha256));
  check('Boot phases, pre-restart runtime, restarted runtime, and Gate 2 end share one exact executable closure',
    runtimeClosureAudit.executable_runtime_authority.exact_phase_restart_and_end_match === true);

  check('Gate 2 performs zero model/provider activity', canonical(ledgerAfter) === canonical(ledgerBefore)
    && ledgerAfterResponse.raw.equals(ledgerBeforeResponse.raw));
  const caseRows = claimIds.map(claimId => preRestart.get(claimId).row);
  check('All 150 case records persist raw semantics, product semantics, scope-declared identity permutation, and visible DOM values', caseRows.length === 150
    && caseRows.every(row => row.journal_semantics?.raw_journal_values
      && canonical(row.journal_semantics.semantic_projection) === canonical(row.product_semantics)
      && row.identity_permutation?.identity_neutral_semantics_equal === true
      && row.visible_dom && row.visible_dom_sha256 === sha(row.visible_dom)));
  check('Every executed acceptance check passed before sealing', checks.length > 0
    && checks.every(row => row.passed));
  const caseBytes = Buffer.from(`${caseRows.map(row => canonical(row)).join('\n')}\n`);
  await fs.writeFile(path.join(out, 'case-results.ndjson'), caseBytes, { flag: 'wx' });
  const seedReceiptsRaw = Buffer.from(`${JSON.stringify({
    contract: 'casepath.gate2-seed-receipts/1.0.0',
    first_fresh_root_seed: firstSeedReceipt,
    second_restart_seed: secondSeedReceipt,
  }, null, 2)}\n`);
  await fs.writeFile(path.join(out, 'seed-receipts.json'), seedReceiptsRaw, { flag: 'wx' });
  const journalAuditSummary = without(journalAudit, 'raw_rows');
  const journalAuditRaw = Buffer.from(`${JSON.stringify(journalAuditSummary, null, 2)}\n`);
  await fs.writeFile(path.join(out, 'raw-journal-audit.json'), journalAuditRaw, { flag: 'wx' });
  const journalEventsRaw = Buffer.from(`${journalAudit.raw_rows.map(row => canonical(row)).join('\n')}\n`);
  await fs.writeFile(path.join(out, 'journal-events.ndjson'), journalEventsRaw, { flag: 'wx' });
  const journalReplayRaw = Buffer.from(`${rawReplay.replayRows.map(row => canonical(without(row, 'state_receipts'))).join('\n')}\n`);
  await fs.writeFile(path.join(out, 'journal-replay-results.ndjson'), journalReplayRaw, { flag: 'wx' });
  const journalStateReceiptsRaw = Buffer.from(`${rawReplay.stateReceiptRows.map(row => canonical(row)).join('\n')}\n`);
  await fs.writeFile(path.join(out, 'journal-state-receipts.ndjson'), journalStateReceiptsRaw, { flag: 'wx' });
  const journalEffectsRaw = Buffer.from(`${rawReplay.effectRows.map(row => canonical(row)).join('\n')}\n`);
  await fs.writeFile(path.join(out, 'journal-effects.ndjson'), journalEffectsRaw, { flag: 'wx' });
  const journalActivityMaterial = {
    contract: 'casepath.gate2-journal-derived-activity/1.0.0',
    per_claim: rawReplay.activityRows,
    graph_traversal_count: rawReplay.activityRows.reduce((sum, row) => sum + row.total_bound.graph_traversal_count, 0),
    model_calls: rawReplay.activityRows.reduce((sum, row) => sum + row.total_bound.model_calls + row.artifact_model_calls, 0),
    provider_calls: rawReplay.activityRows.reduce((sum, row) => sum + row.total_bound.provider_calls + row.artifact_provider_calls, 0),
    credential_reads: rawReplay.activityRows.every(row => row.total_bound.credential_access_status === 'none_due_to_zero_provider_calls'
      && row.total_bound.credential_access_receipt_sha256s.length === 0) ? 0 : null,
    cost_usd: rawReplay.activityRows.reduce((sum, row) => sum + row.total_bound.cost_usd + row.artifact_cost_usd, 0),
    browser_external_network_calls: browserNetwork.filter(row => new URL(row.url).origin !== BASE_ORIGIN).length,
    model_ledger_before_file_sha256: sha(ledgerBeforeResponse.raw),
    model_ledger_after_file_sha256: sha(ledgerAfterResponse.raw),
  };
  const journalActivityReceipt = { ...journalActivityMaterial, receipt_sha256: sha(journalActivityMaterial) };
  const journalActivityRaw = Buffer.from(`${JSON.stringify(journalActivityReceipt, null, 2)}\n`);
  await fs.writeFile(path.join(out, 'journal-activity-receipt.json'), journalActivityRaw, { flag: 'wx' });
  const seamResultsRaw = Buffer.from(`${seamResults.map(row => canonical(row)).join('\n')}\n`);
  await fs.writeFile(path.join(out, 'seam-results.ndjson'), seamResultsRaw, { flag: 'wx' });
  const queueIsolationRaw = Buffer.from(`${queueIsolationReceipts.map(row => canonical(row)).join('\n')}\n`);
  await fs.writeFile(path.join(out, 'queue-isolation-receipts.ndjson'), queueIsolationRaw, { flag: 'wx' });
  const authoritySidecarsRaw = Buffer.from(`${gate2SidecarsAfter.map(row => canonical(row)).join('\n')}\n`);
  await fs.writeFile(path.join(out, 'authority-sidecars.ndjson'), authoritySidecarsRaw, { flag: 'wx' });
  const authorityFilesRaw = Buffer.from(`${JSON.stringify({
    contract: 'casepath.gate2-authority-files/1.0.0',
    before: gate2AuthorityBefore,
    after: gate2AuthorityAfter,
    delta: gate2AuthorityDelta,
    delta_kind_counts: authorityDeltaAudit.kindCounts,
    chain_audit_rows: authorityDeltaAudit.auditRows,
    delta_audit_receipt: authorityDeltaAudit.receipt,
  }, null, 2)}\n`);
  await fs.writeFile(path.join(out, 'authority-files.json'), authorityFilesRaw, { flag: 'wx' });
  const permutationInputsRaw = Buffer.from(`${productionPermutation.inputRows.map(row => canonical(row)).join('\n')}\n`);
  await fs.writeFile(path.join(out, 'permutation-inputs.ndjson'), permutationInputsRaw, { flag: 'wx' });
  const permutationResultsRaw = Buffer.from(`${productionPermutation.results.map(row => canonical(row)).join('\n')}\n`);
  await fs.writeFile(path.join(out, 'permutation-results.ndjson'), permutationResultsRaw, { flag: 'wx' });
  const permutationReceiptMaterial = {
    contract: 'casepath.gate2-production-permutation-receipt/1.0.0',
    result_count: productionPermutation.results.length,
    topology_scoped_result_count:150,
    complete_final_four_event_gate2_permutation_count:148,
    carryover_scoped_prefix_permutation_count:2,
    complete_terminal_raw_event_replay_count:rawReplay.replayRows.length,
    carryover_terminal_histories_fully_permuted:false,
    carryover_binding_receipt_sha256s:carryoverPermutationBindings.map(row => row.receipt_sha256),
    alias_nonce_sha256: productionPermutation.aliasNonceSha256,
    input_roster_sha256: sha(productionPermutation.inputRows),
    result_roster_sha256: sha(productionPermutation.results),
    negative_control_count: productionPermutation.results.reduce(
      (sum, value) => sum + value.negative_controls.control_count,
      0,
    ),
    child_runtime_receipt_sha256: productionPermutation.childRuntime.receipt_sha256,
    child_module_roster_sha256:
      productionPermutation.childRuntime.loaded_casepath_api_module_roster_sha256,
    authority_before_sha256: sha(productionPermutation.beforeFiles),
    authority_after_sha256: sha(productionPermutation.afterFiles),
    authority_unchanged: canonical(productionPermutation.beforeFiles) === canonical(productionPermutation.afterFiles),
  };
  const permutationReceipt = { ...permutationReceiptMaterial, receipt_sha256: sha(permutationReceiptMaterial) };
  const permutationReceiptRaw = Buffer.from(`${JSON.stringify(permutationReceipt, null, 2)}\n`);
  await fs.writeFile(path.join(out, 'permutation-receipt.json'), permutationReceiptRaw, { flag: 'wx' });
  const browserNetworkRaw = Buffer.from(`${browserNetwork.map(row => canonical(row)).join('\n')}\n`);
  await fs.writeFile(path.join(out, 'browser-network.ndjson'), browserNetworkRaw, { flag: 'wx' });
  const browserErrorsRaw = Buffer.from(`${browserErrors.map(row => canonical(row)).join('\n')}${browserErrors.length ? '\n' : ''}`);
  await fs.writeFile(path.join(out, 'browser-errors.ndjson'), browserErrorsRaw, { flag: 'wx' });
  const latencyMaterial = {
    contract: 'casepath.gate2-latency-results/1.0.0',
    clock: 'node_performance_monotonic',
    method: 'nearest_rank_p95',
    first_safe_action: { rows: firstSafeActionTimings, nearest_rank_p95_seconds: p95(firstSafeActionTimings.map(row => row.seconds)) },
    source_acquisition: { rows: sourceAcquisitionTimings, nearest_rank_p95_seconds: p95(sourceAcquisitionTimings.map(row => row.seconds)) },
    post_evidence_replan: { rows: postEvidenceReplanTimings, nearest_rank_p95_seconds: p95(postEvidenceReplanTimings.map(row => row.seconds)) },
    post_mutation_queue: { rows: postMutationQueueSeconds, nearest_rank_p95_seconds: p95(postMutationQueueSeconds.map(row => row.seconds)) },
  };
  const latencyResults = { ...latencyMaterial, receipt_sha256: sha(latencyMaterial) };
  const latencyRaw = Buffer.from(`${JSON.stringify(latencyResults, null, 2)}\n`);
  await fs.writeFile(path.join(out, 'latency-results.json'), latencyRaw, { flag: 'wx' });
  const bootBeforeRaw = Buffer.from(candidateStart.apiBootReceiptBytes);
  const bootAfterRaw = Buffer.from(candidateAfterRestart.apiBootReceiptBytes);
  await fs.writeFile(path.join(out, 'boot-receipt-before.json'), bootBeforeRaw, { flag: 'wx' });
  await fs.writeFile(path.join(out, 'boot-receipt-after.json'), bootAfterRaw, { flag: 'wx' });
  await fs.writeFile(path.join(out, 'model-ledger-before.json'), ledgerBeforeResponse.raw, { flag: 'wx' });
  await fs.writeFile(path.join(out, 'model-ledger-after.json'), ledgerAfterResponse.raw, { flag: 'wx' });
  const runtimeClosureRaw = Buffer.from(`${JSON.stringify(runtimeClosureAudit, null, 2)}\n`);
  await fs.writeFile(path.join(out, 'runtime-closure-audit.json'), runtimeClosureRaw, { flag: 'wx' });
  const browserControlsRaw = Buffer.from(`${JSON.stringify({
    contract: 'casepath.gate2-browser-control-matrix/1.0.0',
    matrix: browserControlMatrix,
    executed_request_roster: browserControlRoster,
  }, null, 2)}\n`);
  await fs.writeFile(path.join(out, 'browser-control-results.json'), browserControlsRaw, { flag: 'wx' });
  const executedChecks = checks.map((row, index) => ({ sequence: index + 1, ...row }));
  const executedChecksRaw = Buffer.from(`${executedChecks.map(row => canonical(row)).join('\n')}\n`);
  await fs.writeFile(path.join(out, 'executed-checks.ndjson'), executedChecksRaw, { flag: 'wx' });
  const sourceRows = `${candidateStart.sourceRows.join('\n')}\n`;
  const builtRows = `${candidateStart.builtRows.join('\n')}\n`;
  await fs.writeFile(path.join(out, 'candidate-source-manifest.sha256'), sourceRows, { flag: 'wx' });
  await fs.writeFile(path.join(out, 'candidate-built-static-manifest.sha256'), builtRows, { flag: 'wx' });
  const reportMaterial = {
    contract: 'casepath.claims-workspace-150-acceptance/1.0.0',
    status: 'PASS',
    gate1_prerequisite: {
      root: gate1Root,
      manifest: gate1Manifest,
      report_file_sha256:sha(gate1ReportRaw),
      report_semantic_sha256:gate1Report.receipt_sha256,
      qualified_witness_selection_file_sha256:sha(gate1QualifiedSelectionRaw),
      qualified_witness_selection_receipt_sha256:gate1QualifiedSelection.receipt_sha256,
      negative_rejection_control_file_sha256:sha(gate1NegativeControlRaw),
      negative_rejection_control_receipt_sha256:gate1NegativeControl.receipt_sha256,
    },
    gate1_carryover_accounting:{
      plan:carryoverPlan,
      gate1_receipt_sha256:gate1Report.gate2_carryovers.receipt_sha256,
      zero_gate2_mutation_claim_ids:carryoverClaimIds,
      fresh_gate2_claim_count:148,
      gate2_journal_delta:{total:740, claim_loop:592, workspace:148},
      gate2_sidecar_delta:{total:296, acquisition:148, tool_artifact:148},
      aggregate_outcomes:seamOutcomeCounts,
    },
    source_authority: { corpus_manifest_file_sha256: sha(corpusManifestRaw), corpus_manifest_semantic_sha256: corpusManifest.manifest_sha256, claim_count: 150 },
    runtime_restart: { before: preBoot, after: candidateAfterRestart.apiBootIdentity },
    coverage: {
      authoritative_workflow: [150, 150], source_exact: [150, 150], same_workbench: [150, 150], safe_next_or_terminal: [150, 150],
      evidence_class_exhaustive: [150, 150], restart_exact: [150, 150], semantic_reconstruction_exact: [150, 150],
      identity_permutation_exact: [150, 150], visible_dom_persisted: [150, 150],
      identity_permutation_definition:'exact within each declared per-row permutation_scope; the two carryover terminal histories are not claimed as fully permuted',
      complete_final_four_event_identity_permutation:[148, 148],
      carryover_topology_scoped_identity_permutation:[2, 2],
      complete_terminal_raw_event_replay:[150, 150],
      duplicate_lifecycle_count: journalAudit.duplicate_lifecycle_count, duplicate_effect_count: journalAudit.duplicate_effect_count,
    },
    progress: {
      numerator_definition: 'received_plus_irrelevant_evidence_items',
      denominator_definition: 'all_current_checklist_evidence_items',
      per_claim_counts_bound_in: 'case-results.ndjson',
    },
    post_mutation_queue_timing: {
      clock: 'node_performance_monotonic', method: 'nearest_rank_p95', claim_bound_rows: postMutationQueueSeconds,
      nearest_rank_p95_seconds: p95(postMutationQueueSeconds.map(row => row.seconds)),
      independent_nearest_rank_p95_seconds: independentP95(postMutationQueueSeconds.map(row => row.seconds)),
      budget_seconds: 0.300,
    },
    queue_matrix: {
      sorts: SORTS, filters: ['state','readiness','claim_type','owner','urgency','failure','pending_evidence'],
      browser_control_receipt_count: browserControlRoster.length, subject_search: true, owner_search: true,
      full_pagination: true, all_claim_id_searches: 150, cursor_request_mismatch_rejected: true, cursor_tamper_rejected: true,
      chained_one_row_isolation: {
        path: 'queue-isolation-receipts.ndjson',
        sha256: sha(queueIsolationRaw),
        rows: queueIsolationReceipts.length,
        terminal_receipt_sha256: queueIsolationReceipts.at(-1)?.receipt_sha256 || null,
        scope:'148_fresh_gate2_mutations',
        imported_gate1_safe_rejection_receipt_sha256:negativeEvidence.queue_isolation.receipt_sha256,
        aggregate_mutation_coverage:149,
      },
    },
    rebuild_receipt: rebuild,
    case_roster_sha256: sha(caseRows.map(row => row.claim_id)),
    case_results: { path: 'case-results.ndjson', sha256: sha(caseBytes), rows: caseRows.length },
    seed_receipts: { path: 'seed-receipts.json', sha256: sha(seedReceiptsRaw), first_new_imports: firstSeedReceipt.new_import_count, second_replayed_imports: secondSeedReceipt.replayed_import_count },
    raw_journal_audit: { path: 'raw-journal-audit.json', sha256: sha(journalAuditRaw), workspace_loops: journalAudit.workspace_loop_count, claim_loops: journalAudit.claim_loop_count },
    journal_evidence: {
      events: { path: 'journal-events.ndjson', sha256: sha(journalEventsRaw), rows: journalAudit.raw_rows.length },
      replay_results: { path: 'journal-replay-results.ndjson', sha256: sha(journalReplayRaw), rows: rawReplay.replayRows.length },
      state_receipts: { path: 'journal-state-receipts.ndjson', sha256: sha(journalStateReceiptsRaw), rows: rawReplay.stateReceiptRows.length },
      effects: { path: 'journal-effects.ndjson', sha256: sha(journalEffectsRaw), rows: rawReplay.effectRows.length },
      activity: { path: 'journal-activity-receipt.json', sha256: sha(journalActivityRaw), semantic_sha256: journalActivityReceipt.receipt_sha256 },
    },
    seam_results: { path: 'seam-results.ndjson', sha256: sha(seamResultsRaw), rows: seamResults.length },
    authority_evidence: {
      sidecars: { path: 'authority-sidecars.ndjson', sha256: sha(authoritySidecarsRaw), rows: gate2SidecarsAfter.length, delta_rows: sidecarDelta.length },
      files: {
        path: 'authority-files.json',
        sha256: sha(authorityFilesRaw),
        before: gate2AuthorityBefore.length,
        after: gate2AuthorityAfter.length,
        delta: gate2AuthorityDelta.length,
        chain_rows: authorityDeltaAudit.auditRows.length,
        per_kind_count: 148,
        delta_audit_receipt_sha256: authorityDeltaAudit.receipt.receipt_sha256,
      },
    },
    permutation_evidence: {
      inputs: { path: 'permutation-inputs.ndjson', sha256: sha(permutationInputsRaw), rows: productionPermutation.inputRows.length },
      results: { path: 'permutation-results.ndjson', sha256: sha(permutationResultsRaw), rows: productionPermutation.results.length },
      receipt: { path: 'permutation-receipt.json', sha256: sha(permutationReceiptRaw), semantic_sha256: permutationReceipt.receipt_sha256 },
      scope_authority:{
        clarification_file_sha256:'277067884daf00c82f6ba6716e57403386e4805850f1fb166b7e3501c52690af',
        clarification_manifest_file_sha256:'09ef1f1f2cc8eb344494bab85aad4114abb43825987a29e232d7b6d5774588ba',
      },
      scope_accounting:{
        topology_scoped_results:[150, 150],
        complete_final_four_event_gate2_permutations:[148, 148],
        gate1_rejection_selected_prefix:[1, 1],
        gate1_main_first_admitted_seam:[1, 1],
        complete_terminal_raw_event_replays:[150, 150],
        carryover_terminal_histories_fully_permuted:false,
        definition:'148 fresh histories are completely permuted; each carryover has one explicitly scoped prefix permutation plus an independently bound complete terminal replay',
      },
      carryover_bindings:carryoverPermutationBindings,
    },
    browser_network: { path: 'browser-network.ndjson', sha256: sha(browserNetworkRaw), rows: browserNetwork.length, errors_path: 'browser-errors.ndjson', errors_sha256: sha(browserErrorsRaw), error_rows: browserErrors.length },
    latency_results: { path: 'latency-results.json', sha256: sha(latencyRaw), semantic_sha256: latencyResults.receipt_sha256 },
    runtime_receipts: {
      before: { path: 'boot-receipt-before.json', sha256: sha(bootBeforeRaw) },
      after: { path: 'boot-receipt-after.json', sha256: sha(bootAfterRaw) },
      model_ledger_before: { path: 'model-ledger-before.json', sha256: sha(ledgerBeforeResponse.raw) },
      model_ledger_after: { path: 'model-ledger-after.json', sha256: sha(ledgerAfterResponse.raw) },
    },
    runtime_closure_audit: {
      path: 'runtime-closure-audit.json',
      sha256: sha(runtimeClosureRaw),
      installed_files: installedRuntimeClosureAudit.file_count,
      python_entries: pythonRuntimeClosureBefore.entry_count,
      claim_id_literals: installedRuntimeClosureAudit.corpus_claim_id_literal_count,
      roster_lookup_tables: installedRuntimeClosureAudit.corpus_roster_lookup_table_count,
      python_restart_exact: runtimeClosureAudit.python_environment.exact_restart_match,
      executable_phase_restart_end_exact:
        runtimeClosureAudit.executable_runtime_authority.exact_phase_restart_and_end_match,
      permutation_child_boot_bound:
        runtimeClosureAudit.permutation_subprocess.exact_boot_closure_binding,
    },
    browser_control_results: { path: 'browser-control-results.json', sha256: sha(browserControlsRaw), receipts: browserControlRoster.length },
    executed_checks: { path: 'executed-checks.ndjson', sha256: sha(executedChecksRaw), rows: executedChecks.length, passed: executedChecks.filter(row => row.passed).length },
    browser_execution_receipt: { path: 'browser-execution-receipt.json', sha256: sha(browserReceiptRaw), semantic_sha256: browserReceipt.receipt_sha256 },
    candidate_source_identity: candidateStart.identity,
    activity: {
      graph_traversal_count: journalActivityReceipt.graph_traversal_count,
      model_calls: journalActivityReceipt.model_calls,
      provider_calls: journalActivityReceipt.provider_calls,
      credential_reads: journalActivityReceipt.credential_reads,
      external_network_calls: journalActivityReceipt.browser_external_network_calls,
      cost_usd: journalActivityReceipt.cost_usd,
      receipt_sha256: journalActivityReceipt.receipt_sha256,
    },
    later_gate_boundary: 'GATE_3_NOT_RUN_OR_AUTHORIZED',
  };
  const report = { ...reportMaterial, receipt_sha256: sha(reportMaterial) };
  const reportRaw = Buffer.from(`${JSON.stringify(report, null, 2)}\n`);
  await fs.writeFile(path.join(out, 'report.json'), reportRaw, { flag: 'wx' });
  const manifestRows = [];
  for (const entry of (await fs.readdir(out, { withFileTypes: true })).sort((left, right) => left.name.localeCompare(right.name))) {
    if (!entry.isFile() || entry.isSymbolicLink() || entry.name === 'MANIFEST.sha256') throw new Error(`Gate 2 evidence contains noncanonical entry: ${entry.name}`);
    manifestRows.push(`${sha(await fs.readFile(path.join(out, entry.name)))}  ${entry.name}`);
  }
  await fs.writeFile(path.join(out, 'MANIFEST.sha256'), `${manifestRows.join('\n')}\n`, { flag: 'wx' });
  console.log(JSON.stringify({ result: 'PASS', receipt_sha256: report.receipt_sha256, report_file_sha256: sha(reportRaw), claims: 150, post_mutation_queue_p95_seconds: p95(postMutationQueueSeconds.map(row => row.seconds)) }));
} finally {
  await browser?.close();
}
