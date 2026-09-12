import { createHash } from 'node:crypto';
import { execFile } from 'node:child_process';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import {
  captureBrowserExecutionReceipt,
  captureCandidateSourceSnapshot,
} from './candidate-source-identity.mjs';
import {
  canonicalQueueValue as canonical,
  queueSnapshotIsConsistent,
} from './claim-queue-snapshot-consistency-v1.mjs';
import { selectQualifiedGate1Witness } from './qualified-gate1-witness-v1.mjs';
import { evaluateCorrectionResponsePredicates } from './correction-response-validator-v1.mjs';
import { evaluateScopedCorrectionPredicates } from './scoped-correction-validator-v1.mjs';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:4173').replace(/\/$/, '');
const BASE_ORIGIN = new URL(BASE).origin;
if (BASE_ORIGIN !== 'http://127.0.0.1:4173') {
  throw new Error(`Gate 1 requires canonical same-origin localhost: ${BASE}`);
}
const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH;
if (executablePath !== '/Applications/ego lite.app/Contents/MacOS/ego lite') {
  throw new Error('Gate 1 requires the governed ego-browser executable');
}
const out = path.resolve(process.env.CASEPATH_WORKSPACE_QA_OUT || '');
if (path.basename(out) !== 'evidence'
  || !/^casepath-workspace-qa-real\.[A-Za-z0-9]{6,}$/.test(path.basename(path.dirname(out)))) {
  throw new Error(`Gate 1 evidence path is not a fresh dedicated root: ${out}`);
}
if (!['/private/tmp', await fs.realpath(os.tmpdir())].includes(await fs.realpath(path.dirname(path.dirname(out))))) {
  throw new Error(`Gate 1 evidence parent is outside a temporary root: ${out}`);
}
await fs.mkdir(out, { recursive: false });

const repository = path.resolve(fileURLToPath(new URL('..', import.meta.url)));
const corpusRoot = path.join(repository, 'casepath-api/casepath_api/corpora/synthetic-150');
const corpusManifestPath = path.join(corpusRoot, 'manifest.json');
const corpusManifestRaw = await fs.readFile(corpusManifestPath);
const corpusManifest = JSON.parse(corpusManifestRaw);
const bindings = new Map(corpusManifest.claims.map(binding => [binding.claim_id, binding]));
const REGISTRATION_BODY_FIELDS = Object.freeze([
  'schema',
  'action_id',
  'expected_revision',
  'idempotency_key',
  'acquisition_intent_id',
  'acquisition_receipt_id',
  'content_b64',
]);
const FORBIDDEN_BROWSER_SEMANTIC_FIELDS = Object.freeze([
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
]);
const checks = [];
const browserErrors = [];
const browserNetwork = [];
const mutationPosts = [];
const timingRows = [];
const queuePageReceipts = [];
const execFileAsync = promisify(execFile);
const pageScenarios = new WeakMap();

const RAW_AUTHORITY_TABLES = Object.freeze([
  { name: 'runs', columns: ['run_id', 'session_id', 'claim_id', 'status', 'payload', 'created_at', 'updated_at'], primary_key: ['run_id'] },
  { name: 'events', columns: ['event_id', 'session_id', 'run_id', 'ordinal', 'payload', 'created_at'], primary_key: ['event_id'] },
  { name: 'reviews', columns: ['review_id', 'session_id', 'run_id', 'claim_id', 'payload', 'created_at'], primary_key: ['review_id'] },
  { name: 'memories', columns: ['memory_id', 'session_id', 'claim_id', 'payload', 'created_at', 'updated_at'], primary_key: ['memory_id'] },
  { name: 'candidates', columns: ['session_id', 'candidate_id', 'payload', 'created_at', 'updated_at'], primary_key: ['session_id', 'candidate_id'] },
  { name: 'model_calls', columns: ['call_id', 'run_id', 'provider', 'model', 'cache_key', 'purpose', 'call_count', 'estimated_cost_usd', 'actual_cost_usd', 'outcome', 'payload', 'created_at', 'updated_at'], primary_key: ['call_id'] },
  { name: 'run_stream_events', columns: ['event_id', 'session_id', 'run_id', 'sequence', 'dedupe_key', 'event_type', 'payload', 'created_at'], primary_key: ['event_id'] },
  { name: 'claim_loop_events', columns: ['session_id', 'loop_id', 'sequence', 'idempotency_key', 'command_sha256', 'event_sha256', 'event_json', 'created_at'], primary_key: ['session_id', 'loop_id', 'sequence'] },
  { name: 'claim_loop_checkpoints', columns: ['session_id', 'loop_id', 'revision', 'last_event_sha256', 'state_sha256', 'state_json', 'created_at', 'updated_at'], primary_key: ['session_id', 'loop_id'] },
  { name: 'claim_loop_client_requests', columns: ['session_id', 'loop_id', 'idempotency_key', 'request_type', 'request_sha256', 'request_json', 'created_at', 'status', 'result_event_idempotency_key', 'result_event_sha256', 'result_revision', 'result_state_sha256', 'response_sha256', 'response_json', 'completed_at', 'dispatch_started_at', 'dispatch_expires_at', 'dispatch_generation', 'reserved_event_idempotency_key', 'reserved_event_sha256', 'reserved_revision', 'reserved_state_sha256'], primary_key: ['session_id', 'loop_id', 'idempotency_key'] },
  { name: 'claim_loop_acquisitions', columns: ['receipt_sha256', 'session_id', 'loop_id', 'action_id', 'dispatch_sha256', 'status', 'acquisition_json', 'raw_payload', 'created_at'], primary_key: ['receipt_sha256'] },
  { name: 'claim_loop_tool_artifacts', columns: ['receipt_sha256', 'session_id', 'loop_id', 'action_id', 'dispatch_sha256', 'artifact_json', 'created_at'], primary_key: ['receipt_sha256'] },
  { name: 'claim_loop_corrections', columns: ['correction_id', 'correction_sha256', 'source_session_id', 'source_loop_id', 'correction_json', 'created_at'], primary_key: ['correction_id'] },
  { name: 'claim_loop_correction_artifacts', columns: ['receipt_sha256', 'session_id', 'loop_id', 'parent_state_sha256', 'artifact_json', 'created_at'], primary_key: ['receipt_sha256'] },
]);
const RAW_TABLE_BY_NAME = new Map(RAW_AUTHORITY_TABLES.map((value, index) => [value.name, { ...value, rank: index }]));

function sha(value) {
  return createHash('sha256')
    .update(Buffer.isBuffer(value) || typeof value === 'string' ? value : canonical(value))
    .digest('hex');
}

function lengthFrame(value) {
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(String(value), 'utf8');
  return Buffer.concat([Buffer.from(`${bytes.length}:`, 'ascii'), bytes]);
}

function framedHash(domain, label, values = []) {
  const digest = createHash('sha256');
  digest.update(lengthFrame(domain));
  digest.update(lengthFrame(label));
  for (const value of values) digest.update(lengthFrame(value));
  return digest.digest('hex');
}

function rawRowBytes(row) {
  const parts = [lengthFrame(row.table)];
  for (const cell of row.cells) {
    parts.push(lengthFrame(cell.name), lengthFrame(cell.sql_type));
    parts.push(lengthFrame(cell.value === null ? 'NULL' : cell.value));
  }
  return Buffer.concat(parts);
}

function merkleRoot(domain, rows) {
  let level = rows.map(row => Buffer.from(framedHash(domain, 'leaf', [rawRowBytes(row)]), 'hex'));
  if (level.length === 0) return framedHash(domain, 'empty');
  while (level.length > 1) {
    const next = [];
    for (let index = 0; index < level.length; index += 2) {
      const left = level[index];
      const right = level[index + 1] || left;
      next.push(Buffer.from(framedHash(domain, 'node', [left, right]), 'hex'));
    }
    level = next;
  }
  return framedHash(domain, 'root', [level[0]]);
}

function rawCell(row, name) {
  return row?.cells?.find(cell => cell.name === name)?.value ?? null;
}

function rawJson(row, name) {
  const value = rawCell(row, name);
  if (typeof value !== 'string') return null;
  try { return JSON.parse(value); } catch (_) { return null; }
}

function rawNumber(row, name) {
  const value = rawCell(row, name);
  return value === null ? null : Number(value);
}

function collectKnownClaimIds(value, knownClaimIds, found = new Set()) {
  if (typeof value === 'string') {
    if (knownClaimIds.has(value)) found.add(value);
    return found;
  }
  if (Array.isArray(value)) {
    for (const child of value) collectKnownClaimIds(child, knownClaimIds, found);
    return found;
  }
  if (value && typeof value === 'object') {
    for (const child of Object.values(value)) collectKnownClaimIds(child, knownClaimIds, found);
  }
  return found;
}

async function readRawAuthorityTables(databasePath) {
  const selects = RAW_AUTHORITY_TABLES.map((table, rank) => {
    const jsonFields = table.columns.flatMap(column => [
      `'${column}__type'`, `typeof("${column}")`,
      `'${column}__value'`, `CASE WHEN typeof("${column}")='null' THEN NULL WHEN typeof("${column}")='blob' THEN hex("${column}") ELSE CAST("${column}" AS TEXT) END`,
    ]).join(',');
    const ordering = table.primary_key.map(column => `"${column}"`).join(',');
    return `SELECT ${rank} AS table_rank,'${table.name}' AS table_name,row_number() OVER (ORDER BY ${ordering}) AS row_ordinal,json_object(${jsonFields}) AS row_json FROM "${table.name}"`;
  });
  const sql = `SELECT table_rank,table_name,row_ordinal,row_json FROM (${selects.join(' UNION ALL ')}) ORDER BY table_rank,row_ordinal`;
  const { stdout, stderr } = await execFileAsync('/usr/bin/sqlite3', ['-readonly', '-json', databasePath, sql], {
    encoding: 'utf8',
    maxBuffer: 256 * 1024 * 1024,
  });
  if (stderr.trim()) throw new Error(`Gate 1 raw authority read emitted stderr: ${stderr.trim()}`);
  return JSON.parse(stdout || '[]').map(value => {
    const table = RAW_TABLE_BY_NAME.get(value.table_name);
    const material = JSON.parse(value.row_json);
    const cells = table.columns.map(name => ({
      name,
      sql_type: material[`${name}__type`],
      value: material[`${name}__value`] ?? null,
    }));
    const row = {
      table: table.name,
      table_rank: table.rank,
      primary_key: Object.fromEntries(table.primary_key.map(name => [name, cells.find(cell => cell.name === name)?.value ?? null])),
      cells,
    };
    return { ...row, framed_sha256: sha(rawRowBytes(row)) };
  });
}

async function readRawAuthoritySchema(databasePath) {
  const selects = RAW_AUTHORITY_TABLES.map((table, rank) => (
    `SELECT ${rank} AS table_rank,'${table.name}' AS table_name,cid,name,type,"notnull" AS not_null,dflt_value,pk FROM pragma_table_info('${table.name}')`
  ));
  const sql = `SELECT table_rank,table_name,cid,name,type,not_null,dflt_value,pk FROM (${selects.join(' UNION ALL ')}) ORDER BY table_rank,cid`;
  const { stdout, stderr } = await execFileAsync('/usr/bin/sqlite3', ['-readonly', '-json', databasePath, sql], {
    encoding: 'utf8',
    maxBuffer: 16 * 1024 * 1024,
  });
  if (stderr.trim()) throw new Error(`Gate 1 raw authority schema read emitted stderr: ${stderr.trim()}`);
  return JSON.parse(stdout || '[]');
}

async function readRawAuthorityCatalog(databasePath) {
  const sql = `SELECT name,type,sql FROM sqlite_master
    WHERE type='table' AND name NOT LIKE 'sqlite_%'
    ORDER BY name`;
  const { stdout, stderr } = await execFileAsync('/usr/bin/sqlite3', ['-readonly', '-json', databasePath, sql], {
    encoding: 'utf8',
    maxBuffer: 16 * 1024 * 1024,
  });
  if (stderr.trim()) throw new Error(`Gate 1 raw authority catalog read emitted stderr: ${stderr.trim()}`);
  return JSON.parse(stdout || '[]');
}

function rawAuthorityCatalogIsExact(rows) {
  return canonical(rows.map(row => ({ name: row.name, type: row.type })))
    === canonical(RAW_AUTHORITY_TABLES.map(table => ({ name: table.name, type: 'table' }))
      .sort((left, right) => left.name.localeCompare(right.name)));
}

function rawAuthoritySchemaIsExact(rows) {
  return RAW_AUTHORITY_TABLES.every(table => {
    const actual = rows.filter(row => row.table_name === table.name);
    const primaryKey = actual.filter(row => Number(row.pk) > 0)
      .sort((left, right) => Number(left.pk) - Number(right.pk))
      .map(row => row.name);
    return canonical(actual.map(row => row.name)) === canonical(table.columns)
      && canonical(primaryKey) === canonical(table.primary_key);
  }) && new Set(rows.map(row => row.table_name)).size === RAW_AUTHORITY_TABLES.length;
}

function assignRawRows(rows, claimIds) {
  const knownClaimIds = new Set(claimIds);
  const runClaims = new Map();
  const loopClaims = new Map();
  const loopClaimBasis = new Map();
  const loopKey = row => `${rawCell(row, 'session_id')}\u0000${rawCell(row, 'loop_id')}`;
  for (const row of rows.filter(value => value.table === 'runs')) {
    const claimId = rawCell(row, 'claim_id');
    if (knownClaimIds.has(claimId)) runClaims.set(rawCell(row, 'run_id'), claimId);
  }
  for (const row of rows.filter(value => value.table === 'claim_loop_events')) {
    const loopId = rawCell(row, 'loop_id');
    if (loopId.startsWith('workspace.')) {
      const claimId = loopId.slice('workspace.'.length);
      if (knownClaimIds.has(claimId)) {
        loopClaims.set(loopKey(row), claimId);
        loopClaimBasis.set(loopKey(row), 'workspace.loop_id.claim_id');
      }
    }
    const event = rawJson(row, 'event_json');
    if (event?.event_type === 'LOOP_CREATED' && knownClaimIds.has(event?.command?.claim_id)) {
      loopClaims.set(loopKey(row), event.command.claim_id);
      loopClaimBasis.set(loopKey(row), 'loop.LOOP_CREATED.command.claim_id');
    }
  }
  for (const row of rows.filter(value => value.table === 'claim_loop_checkpoints')) {
    if (loopClaims.has(loopKey(row))) continue;
    const candidates = collectKnownClaimIds(rawJson(row, 'state_json'), knownClaimIds);
    if (candidates.size === 1) {
      loopClaims.set(loopKey(row), [...candidates][0]);
      loopClaimBasis.set(loopKey(row), 'loop.checkpoint.accepted-claim-fallback');
    }
  }
  for (const row of rows) {
    if (!rawCell(row, 'session_id') || !rawCell(row, 'loop_id') || loopClaims.has(loopKey(row))) continue;
    const jsonColumns = ['event_json', 'state_json', 'request_json', 'response_json', 'acquisition_json', 'artifact_json'];
    const candidates = collectKnownClaimIds(jsonColumns.map(column => rawJson(row, column)), knownClaimIds);
    if (candidates.size === 1) {
      loopClaims.set(loopKey(row), [...candidates][0]);
      loopClaimBasis.set(loopKey(row), 'loop.accepted-authority-fallback');
    }
  }
  const bundles = new Map(claimIds.map(claimId => [claimId, []]));
  const unscoped = [];
  const assignments = [];
  for (const row of rows) {
    let claimId = null;
    let basis = null;
    if (row.table === 'runs' || row.table === 'reviews' || row.table === 'memories') {
      const direct = rawCell(row, 'claim_id');
      if (knownClaimIds.has(direct)) {
        claimId = direct;
        basis = 'legacy.claim_id';
      }
    } else if (['events', 'model_calls', 'run_stream_events'].includes(row.table)) {
      claimId = runClaims.get(rawCell(row, 'run_id')) || null;
      basis = claimId ? 'legacy.runs.claim_id' : null;
    } else if (row.table === 'claim_loop_corrections') {
      const key = `${rawCell(row, 'source_session_id')}\u0000${rawCell(row, 'source_loop_id')}`;
      claimId = loopClaims.get(key) || null;
      basis = claimId ? `correction.source:${loopClaimBasis.get(key)}` : null;
    } else if (row.table.startsWith('claim_loop_')) {
      const key = loopKey(row);
      claimId = loopClaims.get(key) || null;
      basis = claimId ? loopClaimBasis.get(key) : null;
    }
    if (claimId) bundles.get(claimId).push(row);
    else unscoped.push(row);
    assignments.push({ table: row.table, primary_key: row.primary_key, claim_id: claimId, basis: basis || 'unscoped' });
  }
  return { bundles, unscoped, assignments, loopClaims, loopClaimBasis, runClaims };
}

async function snapshotRawAuthority(databasePath, queueRows, claimIds) {
  const rows = await readRawAuthorityTables(databasePath);
  const assigned = assignRawRows(rows, claimIds);
  const queueByClaim = new Map((queueRows || []).map(row => [row.claim_id, row]));
  const claims = claimIds.map(claimId => {
    const bundle = assigned.bundles.get(claimId);
    const queue = queueByClaim.get(claimId) || null;
    return {
      claim_id: claimId,
      row_count: bundle.length,
      table_counts: Object.fromEntries(RAW_AUTHORITY_TABLES.map(table => [table.name, bundle.filter(row => row.table === table.name).length])),
      bundle_merkle_root: merkleRoot(`casepath.gate1.raw-authority.claim/${claimId}`, bundle),
      queue_sha256: queue === null ? null : framedHash(`casepath.gate1.queue.claim/${claimId}`, 'row', [canonical(queue)]),
    };
  });
  const summaryRows = claims.map(row => ({
    table: 'claim_bundle_roots',
    cells: [
      { name: 'claim_id', sql_type: 'text', value: row.claim_id },
      { name: 'bundle_merkle_root', sql_type: 'text', value: row.bundle_merkle_root },
      { name: 'queue_sha256', sql_type: row.queue_sha256 === null ? 'null' : 'text', value: row.queue_sha256 },
    ],
  }));
  const bundleRootRows = claims.map(row => ({
    table: 'claim_bundle_roots',
    cells: [
      { name: 'claim_id', sql_type: 'text', value: row.claim_id },
      { name: 'bundle_merkle_root', sql_type: 'text', value: row.bundle_merkle_root },
    ],
  }));
  const queueRootRows = claims.map(row => ({
    table: 'claim_queue_roots',
    cells: [
      { name: 'claim_id', sql_type: 'text', value: row.claim_id },
      { name: 'queue_sha256', sql_type: row.queue_sha256 === null ? 'null' : 'text', value: row.queue_sha256 },
    ],
  }));
  return {
    rows,
    bundles: assigned.bundles,
    unscoped: assigned.unscoped,
    assignments: assigned.assignments,
    queueByClaim,
    claims,
    table_counts: Object.fromEntries(RAW_AUTHORITY_TABLES.map(table => [table.name, rows.filter(row => row.table === table.name).length])),
    unscoped_merkle_root: merkleRoot('casepath.gate1.raw-authority.unscoped', assigned.unscoped),
    claims_merkle_root: merkleRoot('casepath.gate1.raw-authority.claim-roster', summaryRows),
    bundle_roster_merkle_root: merkleRoot('casepath.gate1.raw-authority.bundle-roster', bundleRootRows),
    queue_roster_merkle_root: merkleRoot('casepath.gate1.queue.roster', queueRootRows),
  };
}

function rawRowDelta(beforeRows, afterRows) {
  const key = row => `${row.table}\u0000${canonical(row.primary_key)}`;
  const before = new Map(beforeRows.map(row => [key(row), row]));
  const after = new Map(afterRows.map(row => [key(row), row]));
  const keys = [...new Set([...before.keys(), ...after.keys()])].sort();
  return keys.flatMap(identity => {
    const prior = before.get(identity) || null;
    const next = after.get(identity) || null;
    if (prior?.framed_sha256 === next?.framed_sha256) return [];
    return [{
      change: prior === null ? 'created' : next === null ? 'deleted' : 'updated',
      table: (next || prior).table,
      primary_key: (next || prior).primary_key,
      before: prior,
      after: next,
    }];
  });
}

function compactRawRow(row) {
  if (row === null) return null;
  return {
    table: row.table,
    primary_key: row.primary_key,
    framed_sha256: row.framed_sha256,
    cells: row.cells.map(cell => {
      const bytes = cell.value === null
        ? Buffer.alloc(0)
        : Buffer.from(cell.sql_type === 'blob' ? cell.value : cell.value, cell.sql_type === 'blob' ? 'hex' : 'utf8');
      return {
        name: cell.name,
        sql_type: cell.sql_type,
        value_length_bytes: bytes.length,
        value_sha256: cell.value === null ? null : sha(bytes),
        ...(cell.value !== null && bytes.length <= 512 && cell.sql_type !== 'blob' ? { value: cell.value } : {}),
      };
    }),
  };
}

function tableRows(snapshot, claimId, table) {
  return snapshot.bundles.get(claimId).filter(row => row.table === table);
}

function terminalPacketAuthorityIsExact(view, claimId) {
  const state = view?.loop_state;
  const packet = view?.decision_packet;
  return Boolean(state && packet
    && state.contract === 'casepath.claim-loop-state/1.0.0'
    && state.claim_id === claimId
    && packet.contract === 'casepath.decision-ready-packet/1.0.0'
    && exactLoopSha(packet, 'packet_sha256')
    && exactLoopSha(state.six_agent_cycle_receipt, 'receipt_sha256')
    && exactLoopSha(state.deterministic_gate_receipt, 'receipt_sha256')
    && exactLoopSha(state.accepted_cycle_artifacts, 'receipt_sha256')
    && exactLoopSha(state.accepted_cycle_artifacts?.role_artifacts, 'receipt_sha256')
    && state.accepted_cycle_artifacts_sha256 === state.accepted_cycle_artifacts.receipt_sha256
    && state.six_agent_cycle_receipt.accepted_cycle_artifacts_sha256 === state.accepted_cycle_artifacts.receipt_sha256
    && canonical(state.facts) === canonical(state.accepted_cycle_artifacts.facts)
    && canonical(state.process) === canonical(state.accepted_cycle_artifacts.process)
    && canonical(state.checklist) === canonical(state.accepted_cycle_artifacts.checklist)
    && packet.claim_id === claimId
    && packet.loop_id === state.loop_id
    && packet.phase === state.phase
    && packet.terminal_mode === state.terminal_mode
    && packet.sufficiency?.status === (state.terminal_mode === 'abstain' ? 'abstain' : 'decision_ready')
    && packet.selected_action === null
    && packet.source_state_sha256 === state.state_sha256
    && packet.six_agent_cycle_receipt_sha256 === state.six_agent_cycle_receipt.receipt_sha256
    && packet.deterministic_gate_receipt_sha256 === state.deterministic_gate_receipt.receipt_sha256
    && packet.accepted_cycle_artifacts_sha256 === state.accepted_cycle_artifacts.receipt_sha256
    && canonical(packet.current_overlay) === canonical(state.process?.current_overlay)
    && canonical(packet.obligations) === canonical(state.obligations)
    && canonical(packet.sufficiency) === canonical(state.sufficiency)
    && canonical(packet.provenance_edges) === canonical(state.provenance_edges)
    && canonical(packet.accepted_cycle_artifacts) === canonical(state.accepted_cycle_artifacts));
}

const CLAIM_LOOP_FLOAT_FIELDS = new Set(['confidence', 'cost_usd']);
function claimLoopCanonical(value, field = null) {
  if (value === null || typeof value !== 'object') {
    if (typeof value === 'number' && Number.isInteger(value) && CLAIM_LOOP_FLOAT_FIELDS.has(field)) {
      return value.toFixed(1);
    }
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(item => claimLoopCanonical(item)).join(',')}]`;
  return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${claimLoopCanonical(value[key], key)}`).join(',')}}`;
}

function claimLoopSha(value) {
  return createHash('sha256').update(claimLoopCanonical(value)).digest('hex');
}

function without(value, key) {
  return Object.fromEntries(Object.entries(value).filter(([name]) => name !== key));
}

function exactLoopSha(value, field) {
  return Boolean(value && typeof value === 'object'
    && value[field] === claimLoopSha(without(value, field)));
}

function check(name, passed, detail = '') {
  const row = { sequence: checks.length + 1, name, passed: Boolean(passed), detail };
  checks.push(row);
  if (!row.passed) throw new Error(`${name}: ${detail}`);
}

function qualifiedWitnessQueueProjection(row) {
  return {
    claim_id: row.claim_id,
    subject: row.subject,
    language: row.language,
    owner: row.owner,
    workflow_state: row.workflow_state,
    readiness_state: row.readiness_state,
    revision: row.revision,
    state_sha256: row.state_sha256,
    operational_projection: {
      claim_id: row.operational_projection.claim_id,
      workspace_prefix: {
        revision: row.operational_projection.workspace_prefix.revision,
        state_sha256: row.operational_projection.workspace_prefix.state_sha256,
      },
      claim_loop_prefix: row.operational_projection.claim_loop_prefix,
      next_state: { kind: row.operational_projection.next_state.kind },
      projection_sha256: row.operational_projection.projection_sha256,
    },
  };
}

function loopBusinessProjection(state) {
  const checklist = structuredClone(state.checklist);
  for (const row of checklist.items) {
    delete row.artifact_ids;
    delete row.loop_source_ref_ids;
  }
  return {
    facts: state.facts.map(row => Object.fromEntries([
      'fact_id', 'state', 'controls_process', 'decision_key', 'normalized_value', 'decision_value',
    ].map(key => [key, structuredClone(row[key])]))),
    checklist,
    process: structuredClone(state.process),
    sufficiency: structuredClone(state.sufficiency),
    phase: state.phase,
    terminal_mode: state.terminal_mode,
    abstain_reason: state.abstain_reason,
    blocking_uncertainty_fact_ids: structuredClone(state.blocking_uncertainty_fact_ids),
  };
}

function loopStateWithoutAuthorityPrefix(state) {
  return Object.fromEntries(Object.entries(structuredClone(state)).filter(([key]) => ![
    'last_event_sha256', 'revision', 'state_sha256',
  ].includes(key)));
}

function queueRosterSha256(rows, excludedClaimId = null) {
  return sha(rows
    .filter(row => row.claim_id !== excludedClaimId)
    .sort((left, right) => left.claim_id.localeCompare(right.claim_id)));
}

function queueBusinessProjection(value) {
  const result = Object.fromEntries(Object.entries(structuredClone(value)).filter(([key]) => ![
    'last_authoritative_update', 'operational_projection', 'revision', 'row_sha256', 'state_sha256',
  ].includes(key)));
  const semantic = Object.fromEntries(Object.entries(structuredClone(value.operational_projection)).filter(([key]) => ![
    'claim_loop_prefix', 'last_authoritative_update', 'projection_sha256', 'workspace_prefix',
  ].includes(key)));
  delete semantic.current_process?.overlay_sha256;
  for (const row of semantic.evidence_items || []) {
    delete row.provenance_edge_sha256s;
    delete row.source_ref_ids;
  }
  result.operational_projection = semantic;
  return result;
}

async function apiRaw(pathname, options = {}, accepted = [200]) {
  const headers = new Headers(options.headers || {});
  headers.set('Connection', 'close');
  const response = await fetch(`${BASE}${pathname}`, { ...options, headers });
  const raw = Buffer.from(await response.arrayBuffer());
  let body = null;
  try { body = JSON.parse(raw.toString('utf8')); } catch (_) { /* binary body */ }
  if (!accepted.includes(response.status)) {
    throw new Error(`${pathname}: ${response.status} ${raw.toString('utf8')}`);
  }
  return { status: response.status, headers: response.headers, raw, body };
}

async function api(pathname, options = {}) {
  return (await apiRaw(pathname, options)).body;
}

async function queueAll(label) {
  const claims = [];
  const pages = [];
  let cursor = null;
  do {
    const query = new URLSearchParams({ limit: '100', sort: 'priority' });
    if (cursor) query.set('cursor', cursor);
    const page = await api(`/api/claim-loops/v1/workspace/claims?${query}`);
    const invalidRows = page.items.filter(row => !row.operational_projection
      || row.operational_projection.contract !== 'casepath.workspace-operational-projection/1.0.0'
      || !exactLoopSha(row.operational_projection, 'projection_sha256')
      || !exactLoopSha(row, 'row_sha256')
      || row.claim_id !== row.operational_projection.claim_id
      || row.revision !== row.operational_projection.workspace_prefix?.revision
      || row.state_sha256 !== row.operational_projection.workspace_prefix?.state_sha256
      || row.workflow_state !== row.operational_projection.workflow_state
      || row.readiness_state !== row.operational_projection.readiness_state);
    check(`queue ${label} page ${pages.length + 1}: envelope and every operational row are self-hashed`,
      page.contract === 'casepath.claim-queue-projection/2.0.0'
        && page.authority === 'claim_loop_events'
        && page.total_count === 150
        && page.page_count === page.items.length
        && page.items.length > 0
        && exactLoopSha(page, 'projection_sha256')
        && invalidRows.length === 0,
    canonical({ page: without(page, 'items'), invalid_claim_ids: invalidRows.map(row => row.claim_id) }));
    pages.push(page);
    claims.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);
  const first = pages[0];
  check(`queue ${label}: pagination is one exact snapshot with no duplicate or missing row`,
    queueSnapshotIsConsistent(pages, {
      pageLimit: 100,
      stateRosterSha256: claimLoopSha,
    }),
  canonical(pages.map(page => ({
    projection_sha256: page.projection_sha256,
    page_count: page.page_count,
    total_count: page.total_count,
    generated_at: page.generated_at,
    state_roster_sha256: page.state_roster_sha256,
  }))));
  queuePageReceipts.push({
    label,
    page_count: pages.length,
    total_count: claims.length,
    request_sha256: first.request_sha256,
    state_roster_sha256: first.state_roster_sha256,
    page_projection_sha256s: pages.map(page => page.projection_sha256),
    row_sha256s_sha256: claimLoopSha(claims.map(row => row.row_sha256)),
    operational_projection_sha256s_sha256: claimLoopSha(
      claims.map(row => row.operational_projection.projection_sha256),
    ),
  });
  return claims;
}

async function readClaimJournal(databasePath, claimId) {
  const escapedClaimId = claimId.replaceAll("'", "''");
  const sql = `SELECT session_id,loop_id,sequence,idempotency_key,command_sha256,event_sha256,event_json,created_at
    FROM claim_loop_events
    WHERE (session_id='casepath-workspace-local' AND loop_id='workspace.${escapedClaimId}')
       OR (session_id='casepath-workspace-claim-loop-v1' AND loop_id IN (
         SELECT loop_id FROM claim_loop_events
         WHERE session_id='casepath-workspace-claim-loop-v1'
           AND json_extract(event_json,'$.event_type')='LOOP_CREATED'
           AND json_extract(event_json,'$.command.claim_id')='${escapedClaimId}'
       ))
    ORDER BY session_id,loop_id,sequence`;
  const { stdout, stderr } = await execFileAsync('/usr/bin/sqlite3', ['-readonly', '-json', databasePath, sql], {
    encoding: 'utf8',
    maxBuffer: 128 * 1024 * 1024,
  });
  if (stderr.trim()) throw new Error(`Gate 1 journal read emitted stderr: ${stderr.trim()}`);
  return JSON.parse(stdout || '[]').map(row => ({ ...row, event: JSON.parse(row.event_json) }));
}

async function snapshotAuthority(root) {
  const files = [];
  async function visit(directory) {
    for (const entry of (await fs.readdir(directory, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
      const absolute = path.join(directory, entry.name);
      const metadata = await fs.lstat(absolute);
      if (metadata.isSymbolicLink()) throw new Error(`Gate 1 authority contains a symlink: ${absolute}`);
      if (metadata.isDirectory()) {
        await visit(absolute);
      } else if (metadata.isFile()) {
        const bytes = await fs.readFile(absolute);
        files.push({
          relative_path: path.relative(root, absolute),
          sha256: sha(bytes),
          size_bytes: bytes.length,
          content_b64: bytes.toString('base64'),
        });
      } else {
        throw new Error(`Gate 1 authority contains a non-file: ${absolute}`);
      }
    }
  }
  await visit(root);
  return files;
}

function authorityDelta(before, after) {
  const beforeByPath = new Map(before.map(row => [row.relative_path, row]));
  const afterByPath = new Map(after.map(row => [row.relative_path, row]));
  return {
    created_or_changed: after.filter(row => beforeByPath.get(row.relative_path)?.sha256 !== row.sha256),
    deleted: before.filter(row => !afterByPath.has(row.relative_path)),
  };
}

function buildAuthorityDeltaRoster(delta, claimIds) {
  const knownClaimIds = new Set(claimIds);
  const claimHash = new Map(claimIds.map(claimId => [sha(claimId), claimId]));
  const contracts = {
    'acquisition-by-intent': 'casepath.workspace-acquisition-intent-index/1.0.0',
    acquisitions: 'casepath.workspace-source-acquisition/1.0.0',
    'admission-by-interpretation': 'casepath.workspace-admission-interpretation-index/1.0.0',
    admissions: 'casepath.workspace-evidence-authority-admission/1.0.0',
    'claim-content-registry': 'casepath.workspace-claim-content-first-seen/1.0.0',
    intents: 'casepath.workspace-acquisition-intent/1.0.0',
    'outcome-by-acquisition': 'casepath.workspace-authority-outcome-index/1.0.0',
    'proposal-by-acquisition': 'casepath.workspace-proposal-acquisition-index/1.0.0',
    proposals: 'casepath.workspace-server-interpretation-proposal/1.0.0',
    registrations: 'casepath.workspace-evidence-registration-receipt/1.0.0',
    'rejection-by-acquisition': 'casepath.workspace-rejection-acquisition-index/1.0.0',
    rejections: 'casepath.workspace-authority-rejection/1.0.0',
  };
  const typedKey = (type, value) => `${type}\u0000${value}`;
  const rows = delta.created_or_changed.map((file, rowIndex) => {
    const parts = file.relative_path.split('/');
    const bytes = Buffer.from(file.content_b64, 'base64');
    let parsed = null;
    if (file.relative_path.endsWith('.json')) {
      try { parsed = JSON.parse(bytes.toString('utf8')); } catch (_) { /* rejected below */ }
    }
    const kind = parts[1] || null;
    const identities = [];
    const references = [];
    const directSeeds = [];
    let pathBindingValid = parts[0] === 'authority-v3';
    const addIdentity = (type, field, value) => {
      if (typeof value !== 'string' || value.length === 0) {
        pathBindingValid = false;
        return;
      }
      identities.push({ type, field, value, key: typedKey(type, value) });
    };
    const addReference = (type, field, value) => {
      if (typeof value !== 'string' || value.length === 0) {
        pathBindingValid = false;
        return;
      }
      references.push({ type, field, value, key: typedKey(type, value) });
    };
    const addJsonClaimSeed = relation => {
      if (!knownClaimIds.has(parsed?.claim_id)) {
        pathBindingValid = false;
        return;
      }
      directSeeds.push({ claim_id: parsed.claim_id, relation });
    };
    const exactJsonPath = expected => {
      pathBindingValid = pathBindingValid && parts.length === 3 && parts[2] === expected;
    };
    switch (kind) {
      case 'intents':
        addJsonClaimSeed('json.claim_id');
        addIdentity('workspace-intent-id', 'intent_id', parsed?.intent_id);
        addIdentity('workspace-intent-receipt', 'receipt_sha256', parsed?.receipt_sha256);
        exactJsonPath(`${sha(parsed?.intent_id || '')}.json`);
        break;
      case 'source-blobs': {
        const claimId = claimHash.get(parts[2]);
        const contentSha256 = parts[3]?.endsWith('.bin') ? parts[3].slice(0, -4) : null;
        if (!claimId || !/^[0-9a-f]{64}$/.test(contentSha256 || '') || parts.length !== 4) {
          pathBindingValid = false;
        } else {
          directSeeds.push({ claim_id: claimId, relation: 'path.claim-id-sha256' });
          addIdentity('source-content-bytes', 'path.claim-content', `${claimId}:${contentSha256}`);
          pathBindingValid = pathBindingValid && file.sha256 === contentSha256;
        }
        break;
      }
      case 'claim-content-registry':
        addJsonClaimSeed('json.claim_id');
        addIdentity('claim-content-reservation', 'claim_id+content_sha256', `${parsed?.claim_id}:${parsed?.content_sha256}`);
        addIdentity('claim-first-seen-receipt', 'receipt_sha256', parsed?.receipt_sha256);
        addReference('workspace-intent-id', 'acquisition_intent_id', parsed?.acquisition_intent_id);
        addReference('workspace-intent-receipt', 'intent_receipt_sha256', parsed?.intent_receipt_sha256);
        pathBindingValid = pathBindingValid
          && parts.length === 4
          && parts[2] === sha(parsed?.claim_id || '')
          && parts[3] === `${parsed?.content_sha256}.json`;
        break;
      case 'acquisitions':
        addJsonClaimSeed('json.claim_id');
        addIdentity('source-acquisition-id', 'acquisition_receipt_id', parsed?.acquisition_receipt_id);
        addIdentity('source-acquisition-receipt', 'receipt_sha256', parsed?.receipt_sha256);
        addReference('workspace-intent-id', 'acquisition_intent_id', parsed?.acquisition_intent_id);
        addReference('workspace-intent-receipt', 'intent_receipt_sha256', parsed?.intent_receipt_sha256);
        addReference('claim-first-seen-receipt', 'claim_first_seen_receipt_sha256', parsed?.claim_first_seen_receipt_sha256);
        addReference('source-content-bytes', 'claim_id+content_sha256', `${parsed?.claim_id}:${parsed?.content_sha256}`);
        exactJsonPath(`${sha(parsed?.acquisition_receipt_id || '')}.json`);
        break;
      case 'acquisition-by-intent':
        addIdentity('acquisition-intent-index', 'acquisition_intent_id', parsed?.acquisition_intent_id);
        addReference('workspace-intent-id', 'acquisition_intent_id', parsed?.acquisition_intent_id);
        addReference('source-acquisition-id', 'acquisition_receipt_id', parsed?.acquisition_receipt_id);
        addReference('source-acquisition-receipt', 'source_acquisition_receipt_sha256', parsed?.source_acquisition_receipt_sha256);
        exactJsonPath(`${sha(parsed?.acquisition_intent_id || '')}.json`);
        break;
      case 'registrations': {
        addJsonClaimSeed('json.claim_id');
        addIdentity('registration-receipt', 'receipt_sha256', parsed?.receipt_sha256);
        addReference('workspace-intent-id', 'acquisition_intent_id', parsed?.acquisition_intent_id);
        addReference('workspace-intent-receipt', 'intent_receipt_sha256', parsed?.intent_receipt_sha256);
        addReference('source-acquisition-id', 'acquisition_receipt_id', parsed?.acquisition_receipt_id);
        addReference('source-acquisition-receipt', 'source_acquisition_receipt_sha256', parsed?.source_acquisition_receipt_sha256);
        addReference('source-content-bytes', 'claim_id+content_sha256', `${parsed?.claim_id}:${parsed?.content_sha256}`);
        const registrationIdentity = claimLoopSha({
          contract: 'casepath.workspace-evidence-registration-resource/1.0.0',
          session_id: parsed?.session_id,
          loop_id: parsed?.loop_id,
          parent_revision: parsed?.parent_revision,
          action_sha256: parsed?.action_sha256,
        });
        exactJsonPath(`${registrationIdentity}.json`);
        break;
      }
      case 'proposals':
        addJsonClaimSeed('json.claim_id');
        addIdentity('interpretation-proposal', 'proposal_sha256', parsed?.proposal_sha256);
        addReference('generic-acquisition-receipt', 'acquisition_receipt_sha256', parsed?.acquisition_receipt_sha256);
        addReference('registration-receipt', 'registration_receipt_sha256', parsed?.registration_receipt_sha256);
        addReference('workspace-intent-receipt', 'intent_receipt_sha256', parsed?.intent_receipt_sha256);
        addReference('source-acquisition-receipt', 'source_acquisition_receipt_sha256', parsed?.source_acquisition_receipt_sha256);
        exactJsonPath(`${parsed?.proposal_sha256}.json`);
        break;
      case 'proposal-by-acquisition':
        addIdentity('generic-acquisition-receipt', 'acquisition_receipt_sha256', parsed?.acquisition_receipt_sha256);
        addReference('interpretation-proposal', 'proposal_sha256', parsed?.proposal_sha256);
        exactJsonPath(`${parsed?.acquisition_receipt_sha256}.json`);
        break;
      case 'admissions':
        addIdentity('authority-admission-receipt', 'receipt_sha256', parsed?.receipt_sha256);
        addReference('interpretation-proposal', 'proposal_sha256', parsed?.proposal_sha256);
        addReference('interpretation-receipt', 'interpretation_receipt_sha256', parsed?.interpretation_receipt_sha256);
        addReference('generic-acquisition-receipt', 'acquisition_receipt_sha256', parsed?.acquisition_receipt_sha256);
        addReference('registration-receipt', 'registration_receipt_sha256', parsed?.registration_receipt_sha256);
        addReference('workspace-intent-receipt', 'intent_receipt_sha256', parsed?.intent_receipt_sha256);
        addReference('source-acquisition-receipt', 'source_acquisition_receipt_sha256', parsed?.source_acquisition_receipt_sha256);
        exactJsonPath(`${parsed?.receipt_sha256}.json`);
        break;
      case 'admission-by-interpretation':
        addIdentity('interpretation-receipt', 'interpretation_receipt_sha256', parsed?.interpretation_receipt_sha256);
        addReference('authority-admission-receipt', 'admission_receipt_sha256', parsed?.admission_receipt_sha256);
        exactJsonPath(`${parsed?.interpretation_receipt_sha256}.json`);
        break;
      case 'rejections':
        addJsonClaimSeed('json.claim_id');
        addIdentity('authority-rejection-receipt', 'receipt_sha256', parsed?.receipt_sha256);
        addReference('generic-acquisition-receipt', 'acquisition_receipt_sha256', parsed?.acquisition_receipt_sha256);
        if (parsed?.proposal_sha256 !== null) {
          addReference('interpretation-proposal', 'proposal_sha256', parsed?.proposal_sha256);
        }
        if (parsed?.acquisition_intent_id !== null) {
          addReference('workspace-intent-id', 'acquisition_intent_id', parsed?.acquisition_intent_id);
        }
        if (parsed?.source_acquisition_receipt_sha256 !== null) {
          addReference('source-acquisition-receipt', 'source_acquisition_receipt_sha256', parsed?.source_acquisition_receipt_sha256);
        }
        exactJsonPath(`${parsed?.receipt_sha256}.json`);
        break;
      case 'rejection-by-acquisition':
        addIdentity('generic-acquisition-receipt', 'acquisition_receipt_sha256', parsed?.acquisition_receipt_sha256);
        addReference('authority-rejection-receipt', 'rejection_receipt_sha256', parsed?.rejection_receipt_sha256);
        exactJsonPath(`${parsed?.acquisition_receipt_sha256}.json`);
        break;
      case 'outcome-by-acquisition':
        addIdentity('authority-outcome', 'acquisition_receipt_sha256', parsed?.acquisition_receipt_sha256);
        addReference('generic-acquisition-receipt', 'acquisition_receipt_sha256', parsed?.acquisition_receipt_sha256);
        addReference(
          parsed?.decision === 'rejected' ? 'authority-rejection-receipt' : 'authority-admission-receipt',
          'authority_receipt_sha256',
          parsed?.authority_receipt_sha256,
        );
        exactJsonPath(`${parsed?.acquisition_receipt_sha256}.json`);
        break;
      default:
        pathBindingValid = false;
    }
    const jsonValid = kind === 'source-blobs' || parsed !== null;
    const contractValid = kind === 'source-blobs' || parsed?.contract === contracts[kind];
    const selfHashField = kind === 'proposals' ? 'proposal_sha256' : 'receipt_sha256';
    const selfHashValid = kind === 'source-blobs'
      ? pathBindingValid
      : exactLoopSha(parsed, selfHashField);
    const canonicalBytesValid = kind === 'source-blobs'
      || bytes.equals(Buffer.from(claimLoopCanonical(parsed), 'utf8'));
    return {
      row_index: rowIndex,
      relative_path: file.relative_path,
      kind,
      sha256: file.sha256,
      size_bytes: file.size_bytes,
      direct_claim_ids: [...new Set(directSeeds.map(seed => seed.claim_id))].sort(),
      direct_seeds: directSeeds,
      identity_keys: identities,
      reference_keys: references,
      resolved_claim_paths: new Map(directSeeds.map(seed => [seed.claim_id, [{
        relation: seed.relation,
        from: null,
        to: file.relative_path,
      }]])),
      reference_issues: [],
      json_valid: jsonValid,
      contract_valid: contractValid,
      self_hash_valid: selfHashValid,
      canonical_bytes_valid: canonicalBytesValid,
      path_binding_valid: pathBindingValid,
    };
  });

  const identityOwners = new Map();
  for (const row of rows) {
    for (const identity of row.identity_keys) {
      if (!identityOwners.has(identity.key)) identityOwners.set(identity.key, []);
      identityOwners.get(identity.key).push(row.row_index);
    }
  }
  const adjacency = rows.map(() => []);
  for (const row of rows) {
    for (const reference of row.reference_keys) {
      const targets = identityOwners.get(reference.key) || [];
      if (targets.length !== 1) {
        row.reference_issues.push({ type: reference.type, field: reference.field, matches: targets.length });
        continue;
      }
      const targetIndex = targets[0];
      const edge = { type: reference.type, field: reference.field, value: reference.value };
      adjacency[row.row_index].push({ row_index: targetIndex, edge });
      adjacency[targetIndex].push({ row_index: row.row_index, edge });
    }
  }
  const pending = rows.flatMap(row => [...row.resolved_claim_paths].map(([claimId]) => ({
    row_index: row.row_index,
    claim_id: claimId,
  })));
  for (let cursor = 0; cursor < pending.length; cursor += 1) {
    const current = pending[cursor];
    const currentRow = rows[current.row_index];
    for (const linked of adjacency[current.row_index]) {
      const target = rows[linked.row_index];
      if (target.resolved_claim_paths.has(current.claim_id)) continue;
      target.resolved_claim_paths.set(current.claim_id, [
        ...currentRow.resolved_claim_paths.get(current.claim_id),
        {
          relation: `typed-reference.${linked.edge.type}`,
          field: linked.edge.field,
          from: currentRow.relative_path,
          to: target.relative_path,
        },
      ]);
      pending.push({ row_index: target.row_index, claim_id: current.claim_id });
    }
  }
  return rows.map(row => ({
    relative_path: row.relative_path,
    kind: row.kind,
    sha256: row.sha256,
    size_bytes: row.size_bytes,
    direct_claim_ids: row.direct_claim_ids,
    resolved_claim_ids: [...row.resolved_claim_paths.keys()].sort(),
    mapping: row.direct_claim_ids.length > 0 ? 'direct' : 'transitive',
    json_valid: row.json_valid,
    contract_valid: row.contract_valid,
    self_hash_valid: row.self_hash_valid,
    canonical_bytes_valid: row.canonical_bytes_valid,
    path_binding_valid: row.path_binding_valid,
    identity_keys: row.identity_keys.map(({ key, ...identity }) => identity),
    reference_keys: row.reference_keys.map(({ key, ...reference }) => reference),
    reference_issues: row.reference_issues,
    derivation_path: row.resolved_claim_paths.size === 1
      ? row.resolved_claim_paths.values().next().value
      : [],
    lineage_valid: row.json_valid
      && row.contract_valid
      && row.self_hash_valid
      && row.canonical_bytes_valid
      && row.path_binding_valid
      && row.identity_keys.length > 0
      && row.reference_issues.length === 0
      && row.resolved_claim_paths.size === 1
      && row.resolved_claim_paths.values().next().value.length > 0,
  }));
}

function journalChainsAreExact(rows) {
  const journals = new Map();
  for (const row of rows) {
    const key = `${row.session_id}\u0000${row.loop_id}`;
    if (!journals.has(key)) journals.set(key, []);
    journals.get(key).push(row);
  }
  for (const events of journals.values()) {
    let previous = null;
    for (let index = 0; index < events.length; index += 1) {
      const row = events[index];
      const event = row.event;
      const digest = row.session_id === 'casepath-workspace-local' ? sha
        : row.session_id === 'casepath-workspace-claim-loop-v1' ? claimLoopSha : null;
      if (!digest || event.session_id !== row.session_id || event.loop_id !== row.loop_id) return false;
      if (event.sequence !== index + 1
        || row.sequence !== event.sequence
        || event.previous_event_sha256 !== previous
        || event.event_sha256 !== row.event_sha256
        || event.command_sha256 !== row.command_sha256
        || event.command_sha256 !== digest(event.command)
        || event.event_sha256 !== digest(without(without(event, 'event_sha256'), 'resulting_state_sha256'))
        || !/^[0-9a-f]{64}$/.test(event.resulting_state_sha256)) return false;
      previous = event.event_sha256;
    }
  }
  return true;
}

async function serverDetail(claimId) {
  return api(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(claimId)}`);
}

async function serverLoop(claimId) {
  return api(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(claimId)}/loop`);
}

async function waitWorkspace(page) {
  await page.waitForFunction(() => {
    const rows = [...document.querySelectorAll('[data-claim-id]')];
    const actions = [...document.querySelectorAll('[data-claim-id] td[data-label="Next action"] strong')];
    return rows.length === 25
      && document.querySelector('#cwTotal')?.textContent === '150'
      && actions.length === rows.length
      && actions.every(node => node.textContent.trim().length > 0);
  }, null, { timeout: 30_000 });
}

async function openClaim(page, claimId) {
  await page.locator('#cwSearch').fill(claimId);
  await page.waitForFunction(id => document.querySelectorAll('[data-claim-id]').length === 1
    && document.querySelector('[data-claim-id]')?.dataset.claimId === id, claimId);
  await page.locator(`[data-claim-id="${claimId}"]`).click();
  await page.locator('#cwDetailPanel').waitFor({ state: 'visible' });
  await page.waitForFunction(id => document.querySelector('.cw-detail-title small')?.textContent === id, claimId);
}

async function pending(page, claimId, operation) {
  return page.evaluate(({ id, kind }) => sessionStorage.getItem(`casepath:workspace-command:${id}:${kind}`), {
    id: claimId,
    kind: operation,
  });
}

async function waitEvidenceWorkbench(page, prefix) {
  await page.waitForSelector('#cwEvidenceForm', { timeout: 30_000 });
  await page.waitForFunction(() => Boolean(
    document.querySelector('#cwLoopProposal')?.dataset.actionSha256
      && document.querySelector('#cwLoopCommit'),
  ));
  check(`${prefix}: browser has no semantic or source-authority controls`,
    await page.locator('#cwEvidenceFinding,#cwEvidenceBasis,#cwEvidenceSource,#cwEvidenceNote,#cwEvidenceAttested,#cwEvidenceForm input,#cwEvidenceForm select,#cwEvidenceForm textarea').count() === 0);
}

function validateInputContract(view, prefix) {
  const contract = view.input_contract;
  check(`${prefix}: server exposes one closed byte-acquisition contract`,
    contract?.contract === 'casepath.server-interpreted-evidence-input/1.0.0'
      && contract.registration_schema === 'casepath.workspace-evidence-registration/3.0.0'
      && contract.adapter_id === 'loopback-source-byte-acquisition-v1'
      && contract.server_interpretation_only === true
      && canonical(contract.registration_body_fields) === canonical(REGISTRATION_BODY_FIELDS)
      && contract.action_id === view.loop_state.selected_action.action_id
      && contract.expected_revision === view.loop_state.revision
      && Array.isArray(view.finding_options) && view.finding_options.length === 0);
}

async function acquiredSourceBinding(claimId, acquisitionResponse) {
  const binding = bindings.get(claimId);
  const receipt = acquisitionResponse?.acquisition_receipt;
  const contentB64 = acquisitionResponse?.content_b64;
  const acquiredBytes = typeof contentB64 === 'string' ? Buffer.from(contentB64, 'base64') : Buffer.alloc(0);
  const sourceDocuments = binding && receipt
    ? binding.source_documents.filter(document => document.sha256 === receipt.source_artifact_sha256)
    : [];
  const sourceDocument = sourceDocuments.length === 1 ? sourceDocuments[0] : null;
  const sourceBytes = sourceDocument ? await fs.readFile(path.join(corpusRoot, sourceDocument.path)) : Buffer.alloc(0);
  const sourceSpan = Number.isInteger(receipt?.byte_start) && Number.isInteger(receipt?.byte_end)
    ? sourceBytes.subarray(receipt.byte_start, receipt.byte_end)
    : Buffer.alloc(0);
  const passed = Boolean(binding && receipt && sourceDocument
    && sourceBytes.length === sourceDocument.size_bytes
    && sha(sourceBytes) === sourceDocument.sha256
    && acquiredBytes.length === receipt.content_length
    && sha(acquiredBytes) === receipt.content_sha256
    && Buffer.compare(acquiredBytes, sourceSpan) === 0);
  return {
    passed,
    binding_sha256: binding?.binding_sha256 || null,
    source_document: sourceDocument,
    receipt,
    content_b64: contentB64,
    text: acquiredBytes.toString('utf8'),
  };
}

function validateReceiptHashes(intentResponse, acquisitionResponse, registrationResponse, prefix) {
  const intent = intentResponse.intent;
  const acquisition = acquisitionResponse.acquisition_receipt;
  const stage = registrationResponse.stage_receipt;
  check(`${prefix}: intent, acquisition, and registration receipts are content-addressed`,
    exactLoopSha(intentResponse, 'response_sha256')
      && exactLoopSha(intent, 'receipt_sha256')
      && exactLoopSha(acquisitionResponse, 'response_sha256')
      && exactLoopSha(acquisition, 'receipt_sha256')
      && exactLoopSha(registrationResponse, 'response_sha256')
      && exactLoopSha(stage, 'receipt_sha256'));
}

async function captureEvidenceTransition(page, claimId, before, prefix) {
  const loopPath = `/api/claim-loops/v1/workspace/claims/${claimId}/loop`;
  const requestRows = [];
  const responsePromises = [];
  const requestListener = request => {
    const url = new URL(request.url());
    if (url.pathname === loopPath
      || url.pathname === `${loopPath}/evidence`
      || url.pathname === `${loopPath}/evidence/intents`
      || (url.pathname.startsWith(`${loopPath}/evidence/intents/`) && url.pathname.endsWith('/acquire'))
      || url.pathname === `${loopPath}/advance`) {
      requestRows.push({
        method: request.method(),
        path: url.pathname,
        body: request.postData(),
        idempotency_key: request.headers()['x-casepath-idempotency-key'] || null,
      });
    }
  };
  const responseListener = response => {
    const url = new URL(response.url());
    if (url.pathname === loopPath
      || url.pathname === `${loopPath}/evidence`
      || url.pathname === `${loopPath}/evidence/intents`
      || (url.pathname.startsWith(`${loopPath}/evidence/intents/`) && url.pathname.endsWith('/acquire'))
      || url.pathname === `${loopPath}/advance`) {
      responsePromises.push(response.body().then(raw => ({
        method: response.request().method(),
        path: url.pathname,
        status: response.status(),
        body: JSON.parse(raw.toString('utf8')),
      })));
    }
  };
  page.on('request', requestListener);
  page.on('response', responseListener);
  const started = performance.now();
  await page.locator('#cwLoopCommit').click();
  await page.waitForFunction(actionSha => {
    const proposal = document.querySelector('#cwLoopProposal');
    const outcome = document.querySelector('#cwLoopWorkbench')?.dataset.outcome;
    return document.querySelector('#cwCommandStatus')?.textContent.includes('Observation committed once.')
      && ((proposal?.dataset.actionSha256 || '') !== actionSha || ['abstain', 'decision_ready'].includes(outcome));
  }, before.loop_state.selected_action.action_sha256, { timeout: 30_000 });
  const seconds = (performance.now() - started) / 1000;
  page.off('request', requestListener);
  page.off('response', responseListener);
  const responses = await Promise.all(responsePromises);
  const after = await serverLoop(claimId);
  const paths = requestRows.map(row => `${row.method} ${row.path}`);
  check(`${prefix}: browser executes the exact six-request evidence seam`, requestRows.length === 6
    && paths[0] === `POST ${loopPath}/evidence/intents`
    && /^POST .*\/evidence\/intents\/intent\.[0-9a-f]{64}\/acquire$/.test(paths[1])
    && paths[2] === `POST ${loopPath}/evidence`
    && paths[3] === `GET ${loopPath}`
    && paths[4] === `POST ${loopPath}/advance`
    && paths[5] === `GET ${loopPath}`, canonical(requestRows));
  const intentBody = JSON.parse(requestRows[0].body);
  const registrationBody = JSON.parse(requestRows[2].body);
  const advanceBody = JSON.parse(requestRows[4].body);
  const intentResponse = responses.find(row => row.method === 'POST' && row.path === `${loopPath}/evidence/intents`)?.body;
  const acquisitionResponse = responses.find(row => row.method === 'POST' && row.path.endsWith('/acquire'))?.body;
  const registrationResponse = responses.find(row => row.method === 'POST' && row.path === `${loopPath}/evidence`)?.body;
  const source = await acquiredSourceBinding(claimId, acquisitionResponse);
  check(`${prefix}: registration contains exactly the seven allowlisted fields`,
    canonical(Object.keys(registrationBody).sort()) === canonical([...REGISTRATION_BODY_FIELDS].sort())
      && registrationBody.schema === before.input_contract.registration_schema
      && registrationBody.action_id === before.loop_state.selected_action.action_id
      && registrationBody.expected_revision === before.loop_state.revision
      && registrationBody.idempotency_key === intentBody.idempotency_key
      && requestRows[2].idempotency_key === registrationBody.idempotency_key
      && FORBIDDEN_BROWSER_SEMANTIC_FIELDS.every(field => !(field in registrationBody)));
  check(`${prefix}: acquired bytes exactly match the claim-bound public source span`, source.passed
    && source.receipt.claim_id === claimId
    && source.receipt.action_sha256 === before.loop_state.selected_action.action_sha256
    && source.receipt.expected_state_sha256 === before.loop_state.state_sha256);
  check(`${prefix}: advance is bound to the admitted registration receipt`,
    advanceBody.expected_revision === before.loop_state.revision
      && advanceBody.expected_state_sha256 === before.loop_state.state_sha256
      && advanceBody.action_sha256 === before.loop_state.selected_action.action_sha256
      && advanceBody.stage_receipt_sha256 === registrationResponse.stage_receipt.receipt_sha256);
  check(`${prefix}: one observation and one advance change state exactly once`,
    after.loop_state.revision === before.loop_state.revision + 2
      && after.loop_state.observations.length === before.loop_state.observations.length + 1
      && after.loop_state.state_sha256 !== before.loop_state.state_sha256
      && responses.length === 6 && responses.every(row => row.status === 200));
  validateReceiptHashes(intentResponse, acquisitionResponse, registrationResponse, prefix);
  timingRows.push({ claim_id: claimId, boundary: 'commit_to_authoritative_replan', seconds });
  return {
    before,
    after,
    requests: requestRows,
    responses,
    intent_body: intentBody,
    registration_body: registrationBody,
    advance_body: advanceBody,
    source,
    seconds,
  };
}

async function captureRejectedEvidenceRecovery(
  page,
  claimId,
  before,
  databasePath,
  authorityRoot,
  claimIds,
  queueRowsBefore,
  firstSafeActionSeconds,
) {
  const prefix = `${claimId}: safe-rejection lost-response recovery`;
  const loopPath = `/api/claim-loops/v1/workspace/claims/${claimId}/loop`;
  const advanceUrl = `${BASE}${loopPath}/advance`;
  const requestRows = [];
  const responsePromises = [];
  let advanceRequestStartedAt = null;
  const requestListener = request => {
    const url = new URL(request.url());
    if (request.method() === 'POST' && (
      url.pathname === `${loopPath}/evidence/intents`
      || (url.pathname.startsWith(`${loopPath}/evidence/intents/`) && url.pathname.endsWith('/acquire'))
      || url.pathname === `${loopPath}/evidence`
      || url.pathname === `${loopPath}/advance`
    )) {
      if (url.pathname === `${loopPath}/advance` && advanceRequestStartedAt === null) {
        advanceRequestStartedAt = performance.now();
      }
      requestRows.push({
        method: request.method(),
        path: url.pathname,
        body: request.postData(),
        idempotency_key: request.headers()['x-casepath-idempotency-key'] || null,
      });
    }
  };
  const responseListener = response => {
    const url = new URL(response.url());
    if (response.request().method() === 'POST' && (
      url.pathname === `${loopPath}/evidence/intents`
      || (url.pathname.startsWith(`${loopPath}/evidence/intents/`) && url.pathname.endsWith('/acquire'))
      || url.pathname === `${loopPath}/evidence`
      || url.pathname === `${loopPath}/advance`
    )) responsePromises.push(response.body().then(raw => ({
      method: response.request().method(),
      path: url.pathname,
      status: response.status(),
      body: JSON.parse(raw.toString('utf8')),
    })));
  };
  page.on('request', requestListener);
  page.on('response', responseListener);
  const journalBefore = await readClaimJournal(databasePath, claimId);
  const rawBefore = await snapshotRawAuthority(databasePath, null, claimIds);
  const filesBefore = await snapshotAuthority(authorityRoot);
  let droppedAdvanceResponse = null;
  let drop = true;
  await page.route(advanceUrl, async route => {
    if (route.request().method() !== 'POST' || !drop) return route.continue();
    drop = false;
    const real = await route.fetch();
    droppedAdvanceResponse = await real.json();
    return route.abort('connectionaborted');
  });

  const commitStartedAt = performance.now();
  await page.locator('#cwLoopCommit').click();
  await page.waitForFunction(() => document.querySelector('#cwCommandStatus')?.textContent
    .includes('No valid completion receipt was received'), null, { timeout: 30_000 });
  const ambiguousCopy = await page.locator('#cwCommandStatus').textContent();
  const pendingAdvanceRaw = await pending(page, claimId, 'advance');
  const pendingAdvance = JSON.parse(pendingAdvanceRaw || 'null');
  const committed = await serverLoop(claimId);
  const authoritativeReplanObservedAt = performance.now();
  const committedJournal = await readClaimJournal(databasePath, claimId);
  const committedRaw = await snapshotRawAuthority(databasePath, null, claimIds);
  const committedFiles = await snapshotAuthority(authorityRoot);
  check(`${prefix}: dropped response retains one hash-bound pre-advance recovery identity`,
    drop === false
      && ambiguousCopy.includes('No valid completion receipt was received')
      && pendingAdvance?.before_loop_state?.state_sha256 === before.loop_state.state_sha256
      && pendingAdvance.before_loop_state.revision === before.loop_state.revision
      && pendingAdvance.before_loop_state.observations.length === before.loop_state.observations.length
      && exactLoopSha(pendingAdvance.before_loop_state, 'state_sha256'));
  check(`${prefix}: authority rejects without admitting an observation`,
    committed.outcome === 'next_action'
      && committed.loop_state.revision === before.loop_state.revision + 2
      && committed.loop_state.observations.length === before.loop_state.observations.length
      && canonical(loopStateWithoutAuthorityPrefix(committed.loop_state))
        === canonical(loopStateWithoutAuthorityPrefix(before.loop_state))
      && canonical(loopBusinessProjection(committed.loop_state)) === canonical(loopBusinessProjection(before.loop_state))
      && committed.loop_state.active_dispatch_sha256 === null
      && committed.loop_state.state_sha256 !== before.loop_state.state_sha256);

  await page.unroute(advanceUrl);
  pageScenarios.set(page, 'negative-rejection-recovery');
  await page.reload({ waitUntil: 'domcontentloaded' });
  await waitWorkspace(page);
  await page.locator('#cwDetailPanel').waitFor({ state: 'visible' });
  await page.waitForFunction(({id, copy}) => document.querySelector('.cw-detail-title small')?.textContent === id
    && document.querySelector('#cwCommandStatus')?.textContent === copy
    && !sessionStorage.getItem(`casepath:workspace-command:${id}:advance`), {
    id:claimId,
    copy:'Evidence was safely rejected; no observation was added. CasePath kept the bounded action open.',
  }, { timeout: 30_000 });
  const recoveredCopy = await page.locator('#cwCommandStatus').textContent();
  const recovered = await serverLoop(claimId);
  const recoveredJournal = await readClaimJournal(databasePath, claimId);
  const recoveredRaw = await snapshotRawAuthority(databasePath, null, claimIds);
  const recoveredFiles = await snapshotAuthority(authorityRoot);
  const queueStartedAt = performance.now();
  const queueRowsAfter = await queueAll('after-negative-rejection-recovery');
  const postMutationQueueSeconds = (performance.now() - queueStartedAt) / 1000;
  const queueBefore = queueRowsBefore.find(row => row.claim_id === claimId);
  const queueAfter = queueRowsAfter.find(row => row.claim_id === claimId);
  page.off('request', requestListener);
  page.off('response', responseListener);
  const responses = await Promise.all(responsePromises);
  const intentResponse = responses.find(row => row.path === `${loopPath}/evidence/intents`)?.body;
  const acquisitionResponse = responses.find(row => row.path.endsWith('/acquire'))?.body;
  const registrationResponse = responses.find(row => row.path === `${loopPath}/evidence`)?.body;
  const replayedAdvanceResponse = responses.find(row => row.path === `${loopPath}/advance`)?.body;
  const intentRequest = requestRows.find(row => row.path === `${loopPath}/evidence/intents`);
  const registrationRequest = requestRows.find(row => row.path === `${loopPath}/evidence`);
  const advanceRequests = requestRows.filter(row => row.path === `${loopPath}/advance`);
  const intentBody = JSON.parse(intentRequest?.body || 'null');
  const registrationBody = JSON.parse(registrationRequest?.body || 'null');
  const advanceBodies = advanceRequests.map(row => JSON.parse(row.body || 'null'));
  const source = await acquiredSourceBinding(claimId, acquisitionResponse);
  validateReceiptHashes(intentResponse, acquisitionResponse, registrationResponse, prefix);
  check(`${prefix}: source and browser envelopes remain exact and non-semantic`,
    source.passed
      && source.receipt.source_entry_sha256 === '209f1c5d8df5d62a87b6bcdab9a3475b42ad93ea1888a61fa2f65fa08648b0ff'
      && source.receipt.source_artifact_sha256 === '15658046287f229aef7ae098ae90c26a1ba9dae7e65dcaf794588328c757357b'
      && source.receipt.text_start === 7
      && source.receipt.text_end === 91
      && source.receipt.byte_start === 7
      && source.receipt.byte_end === 91
      && source.receipt.content_sha256 === '586ce587692b4dd5ea241ee4fd44f7c043c106c272fe48a1d274d47385a7f2f9'
      && source.receipt.evidence_item_id === 'workspace_evidence.dh_intake'
      && before.loop_state.selected_action.process_node_id === 'workspace_evidence_gap.dh_intake'
      && source.text === "As I understand it: My ceiling and the downstairs neighbour's ceiling are wet again;"
      && source.receipt.claim_id === claimId
      && canonical(Object.keys(registrationBody).sort()) === canonical([...REGISTRATION_BODY_FIELDS].sort())
      && registrationBody.idempotency_key === intentBody.idempotency_key
      && FORBIDDEN_BROWSER_SEMANTIC_FIELDS.every(field => !(field in registrationBody)));
  check(`${prefix}: reload replays only the identical advance and renders exact rejection copy`,
    requestRows.filter(row => row.path === `${loopPath}/evidence/intents`).length === 1
      && requestRows.filter(row => row.path.endsWith('/acquire')).length === 1
      && requestRows.filter(row => row.path === `${loopPath}/evidence`).length === 1
      && advanceRequests.length === 2
      && advanceRequests[0].body === advanceRequests[1].body
      && advanceRequests[0].idempotency_key === advanceRequests[1].idempotency_key
      && canonical(droppedAdvanceResponse) === canonical(replayedAdvanceResponse)
      && advanceBodies[0].expected_revision === before.loop_state.revision
      && advanceBodies[0].expected_state_sha256 === before.loop_state.state_sha256
      && advanceBodies[0].action_sha256 === before.loop_state.selected_action.action_sha256
      && advanceBodies[0].stage_receipt_sha256 === registrationResponse.stage_receipt.receipt_sha256
      && recoveredCopy === 'Evidence was safely rejected; no observation was added. CasePath kept the bounded action open.'
      && !recoveredCopy.includes('Observation committed once.')
      && !await pending(page, claimId, 'evidence-intent')
      && !await pending(page, claimId, 'evidence')
      && !await pending(page, claimId, 'advance'));
  check(`${prefix}: replay is mutation-free and preserves the queue business projection`,
    recovered.loop_state.state_sha256 === committed.loop_state.state_sha256
      && canonical(recoveredJournal) === canonical(committedJournal)
      && rawRowDelta(committedRaw.rows, recoveredRaw.rows).length === 0
      && authorityDelta(committedFiles, recoveredFiles).created_or_changed.length === 0
      && authorityDelta(committedFiles, recoveredFiles).deleted.length === 0
      && canonical(recoveredFiles) === canonical(committedFiles)
      && canonical(queueBusinessProjection(queueAfter)) === canonical(queueBusinessProjection(queueBefore)));

  const loopEvents = committedJournal.filter(row => row.session_id === 'casepath-workspace-claim-loop-v1');
  const workspaceEvents = committedJournal.filter(row => row.session_id === 'casepath-workspace-local');
  const priorJournalRowsPreserved = journalBefore.every(prior => canonical(committedJournal.find(row => (
    row.session_id === prior.session_id
      && row.loop_id === prior.loop_id
      && row.sequence === prior.sequence
  ))) === canonical(prior));
  const dispatchEvent = loopEvents.at(-2)?.event;
  const rejectionEvent = loopEvents.at(-1)?.event;
  const rejection = loopEvents.at(-1)?.event.command.authority_rejection_receipt;
  const rejectedAcquisition = rejectionEvent?.command.acquisition_receipt;
  const expectedRejectionCommandKeys = [
    'action_id', 'action_sha256', 'dispatch_sha256', 'acquisition_receipt_sha256',
    'acquisition_receipt', 'authority_rejection_receipt_sha256',
    'authority_rejection_receipt', 'advance_request_sha256',
  ];
  const expectedRejectionReceiptKeys = [
    'contract', 'session_id', 'loop_id', 'claim_id', 'record_version',
    'parent_revision', 'parent_state_sha256', 'action_id', 'action_sha256',
    'dispatch_sha256', 'acquisition_receipt_sha256', 'acquisition_intent_id',
    'source_acquisition_receipt_sha256', 'source_entry_sha256', 'content_sha256',
    'proposal_sha256', 'authority_id', 'authority_source_sha256', 'reason',
    'rejected_at', 'authoritative_semantic_effect', 'receipt_sha256',
  ];
  check(`${prefix}: typed journal closes one dispatch with a self-hashed zero-effect rejection`,
    journalChainsAreExact(committedJournal)
      && priorJournalRowsPreserved
      && committedJournal.length === journalBefore.length + 2
      && canonical(workspaceEvents.map(row => row.event.event_type))
        === canonical(['WORKSPACE_CLAIM_IMPORTED', 'WORKSPACE_PROCESSING_STARTED'])
      && canonical(loopEvents.map(row => row.event.event_type)) === canonical([
        'LOOP_CREATED', 'ACTION_SELECTED', 'ACTION_DISPATCH_STARTED', 'EVIDENCE_PROPOSAL_REJECTED',
      ])
      && rejection?.contract === 'casepath.workspace-authority-rejection/1.0.0'
      && canonical(Object.keys(rejectionEvent.command).sort()) === canonical(expectedRejectionCommandKeys.sort())
      && canonical(Object.keys(rejection).sort()) === canonical(expectedRejectionReceiptKeys.sort())
      && rejection.authoritative_semantic_effect === false
      && rejection.proposal_sha256 === null
      && rejection.reason === 'health source span is ambiguous, negated, or contradictory'
      && rejection.authority_id === 'casepath.independent-evidence-authority/1.0.0'
      && /^[0-9a-f]{64}$/.test(rejection.authority_source_sha256)
      && exactLoopSha(rejection, 'receipt_sha256')
      && dispatchEvent.sequence === before.loop_state.revision + 1
      && dispatchEvent.previous_event_sha256 === before.loop_state.last_event_sha256
      && dispatchEvent.command.action_id === before.loop_state.selected_action.action_id
      && dispatchEvent.command.action_sha256 === before.loop_state.selected_action.action_sha256
      && rejectionEvent.sequence === before.loop_state.revision + 2
      && rejectionEvent.previous_event_sha256 === dispatchEvent.event_sha256
      && rejectionEvent.command.dispatch_sha256 === dispatchEvent.event_sha256
      && rejectionEvent.command.action_sha256 === before.loop_state.selected_action.action_sha256
      && rejectionEvent.command.acquisition_receipt_sha256
        === rejectionEvent.command.acquisition_receipt.receipt_sha256
      && rejection.session_id === before.loop_state.session_id
      && rejection.loop_id === before.loop_state.loop_id
      && rejection.claim_id === claimId
      && rejection.record_version === before.loop_state.record_version
      && rejection.parent_revision === before.loop_state.revision + 1
      && rejection.parent_state_sha256 === dispatchEvent.resulting_state_sha256
      && rejection.action_id === before.loop_state.selected_action.action_id
      && rejection.action_sha256 === before.loop_state.selected_action.action_sha256
      && rejection.dispatch_sha256 === dispatchEvent.event_sha256
      && rejection.acquisition_receipt_sha256 === rejectedAcquisition.receipt_sha256
      && rejection.acquisition_intent_id === source.receipt.acquisition_intent_id
      && rejection.source_acquisition_receipt_sha256 === source.receipt.receipt_sha256
      && rejection.source_entry_sha256 === source.receipt.source_entry_sha256
      && rejection.content_sha256 === rejectedAcquisition.sanitized_content_sha256
      && rejection.rejected_at === rejectedAcquisition.acquired_at
      && rejectionEvent.command.authority_rejection_receipt_sha256 === rejection.receipt_sha256
      && rejectionEvent.resulting_state_sha256 === committed.loop_state.state_sha256);

  const clientRequests = tableRows(committedRaw, claimId, 'claim_loop_client_requests');
  const requestTypeCounts = Object.fromEntries([...new Set(clientRequests.map(row => rawCell(row, 'request_type')))].sort()
    .map(type => [type, clientRequests.filter(row => rawCell(row, 'request_type') === type).length]));
  const acquisitions = tableRows(committedRaw, claimId, 'claim_loop_acquisitions');
  const toolArtifacts = tableRows(committedRaw, claimId, 'claim_loop_tool_artifacts');
  const rawBeforeClaim = rawBefore.claims.find(row => row.claim_id === claimId);
  const rawCommittedClaim = committedRaw.claims.find(row => row.claim_id === claimId);
  const expectedBeforeTableCounts = Object.fromEntries(RAW_AUTHORITY_TABLES.map(table => [table.name, 0]));
  Object.assign(expectedBeforeTableCounts, {
    runs:1,
    run_stream_events:2,
    claim_loop_events:4,
    claim_loop_checkpoints:1,
    claim_loop_client_requests:3,
  });
  const expectedCommittedTableCounts = {
    ...expectedBeforeTableCounts,
    claim_loop_events:6,
    claim_loop_client_requests:4,
    claim_loop_acquisitions:1,
  };
  const rejectionRawDelta = rawRowDelta(
    rawBefore.bundles.get(claimId),
    committedRaw.bundles.get(claimId),
  );
  const rejectionRawDeltaCounts = Object.fromEntries([...new Set(rejectionRawDelta.map(row => (
    `${row.table}:${row.change}`
  )))].sort().map(key => [key, rejectionRawDelta.filter(row => `${row.table}:${row.change}` === key).length]));
  const actualRejectionDeltaIdentities = rejectionRawDelta.map(row => ({
    table:row.table,
    change:row.change,
    primary_key:row.primary_key,
  })).sort((left, right) => canonical(left).localeCompare(canonical(right)));
  const expectedRejectionDeltaIdentities = [
    {
      table:'claim_loop_events',
      change:'created',
      primary_key:{ session_id:before.loop_state.session_id, loop_id:before.loop_state.loop_id, sequence:String(before.loop_state.revision + 1) },
    },
    {
      table:'claim_loop_events',
      change:'created',
      primary_key:{ session_id:before.loop_state.session_id, loop_id:before.loop_state.loop_id, sequence:String(before.loop_state.revision + 2) },
    },
    {
      table:'claim_loop_checkpoints',
      change:'updated',
      primary_key:{ session_id:before.loop_state.session_id, loop_id:before.loop_state.loop_id },
    },
    {
      table:'claim_loop_client_requests',
      change:'created',
      primary_key:{
        session_id:before.loop_state.session_id,
        loop_id:before.loop_state.loop_id,
        idempotency_key:advanceRequests[0].idempotency_key,
      },
    },
    {
      table:'claim_loop_acquisitions',
      change:'created',
      primary_key:{ receipt_sha256:rejectionEvent.command.acquisition_receipt_sha256 },
    },
  ].sort((left, right) => canonical(left).localeCompare(canonical(right)));
  check(`${prefix}: durable SQL authority has one completed advance, one acquisition, and zero tool artifacts`,
    canonical(requestTypeCounts) === canonical({advance:1, create:1, select_action:1, workspace_ensure:1})
      && clientRequests.every(row => rawCell(row, 'status') === 'COMPLETED')
      && acquisitions.length === 1
      && rawCell(acquisitions[0], 'status') === 'observed'
      && toolArtifacts.length === 0
      && rawBeforeClaim.row_count === 11
      && canonical(rawBeforeClaim.table_counts) === canonical(expectedBeforeTableCounts)
      && rawCommittedClaim.row_count === 15
      && canonical(rawCommittedClaim.table_counts) === canonical(expectedCommittedTableCounts)
      && rejectionRawDelta.length === 5
      && canonical(rejectionRawDeltaCounts) === canonical({
        'claim_loop_acquisitions:created':1,
        'claim_loop_checkpoints:updated':1,
        'claim_loop_client_requests:created':1,
        'claim_loop_events:created':2,
      })
      && canonical(actualRejectionDeltaIdentities) === canonical(expectedRejectionDeltaIdentities)
      && rejectionRawDelta.every(row => row.before === null || row.change === 'updated'));

  const fileDelta = authorityDelta(filesBefore, committedFiles);
  const fileRoster = buildAuthorityDeltaRoster(fileDelta, claimIds);
  const expectedKinds = [
    'acquisition-by-intent', 'acquisitions', 'claim-content-registry', 'intents',
    'outcome-by-acquisition', 'registrations', 'rejection-by-acquisition', 'rejections',
    'source-blobs',
  ];
  const directKinds = new Set([
    'acquisitions', 'claim-content-registry', 'intents', 'registrations', 'rejections', 'source-blobs',
  ]);
  const forbiddenKinds = new Set([
    'admission-by-interpretation', 'admissions', 'proposal-by-acquisition', 'proposals',
  ]);
  check(`${prefix}: filesystem authority contains only the exact rejection lineage`,
    fileDelta.deleted.length === 0
      && canonical([...new Set(fileRoster.map(row => row.kind))].sort()) === canonical(expectedKinds)
      && expectedKinds.every(kind => fileRoster.filter(row => row.kind === kind).length === 1)
      && fileRoster.every(row => row.json_valid && row.lineage_valid
        && row.mapping === (directKinds.has(row.kind) ? 'direct' : 'transitive')
        && canonical(row.resolved_claim_ids) === canonical([claimId]))
      && fileRoster.every(row => !forbiddenKinds.has(row.kind)));
  const rejectionPath = `authority-v3/rejections/${rejection.receipt_sha256}.json`;
  const rejectionIndexPath = `authority-v3/rejection-by-acquisition/${rejectedAcquisition.receipt_sha256}.json`;
  const outcomePath = `authority-v3/outcome-by-acquisition/${rejectedAcquisition.receipt_sha256}.json`;
  const parsedAuthorityValue = relativePath => JSON.parse(Buffer.from(
    fileDelta.created_or_changed.find(row => row.relative_path === relativePath)?.content_b64 || '',
    'base64',
  ).toString('utf8'));
  const durableRejection = parsedAuthorityValue(rejectionPath);
  const rejectionIndex = parsedAuthorityValue(rejectionIndexPath);
  const rejectedOutcome = parsedAuthorityValue(outcomePath);
  check(`${prefix}: rejection file, index, and exclusive outcome bind the exact same authority receipt`,
    canonical(durableRejection) === canonical(rejection)
      && rejectionIndex.contract === 'casepath.workspace-rejection-acquisition-index/1.0.0'
      && rejectionIndex.acquisition_receipt_sha256 === rejectedAcquisition.receipt_sha256
      && rejectionIndex.rejection_receipt_sha256 === rejection.receipt_sha256
      && exactLoopSha(rejectionIndex, 'receipt_sha256')
      && rejectedOutcome.contract === 'casepath.workspace-authority-outcome-index/1.0.0'
      && rejectedOutcome.acquisition_receipt_sha256 === rejectedAcquisition.receipt_sha256
      && rejectedOutcome.decision === 'rejected'
      && rejectedOutcome.authority_receipt_sha256 === rejection.receipt_sha256
      && exactLoopSha(rejectedOutcome, 'receipt_sha256'));
  const queueBeforeByClaim = new Map(queueRowsBefore.map(row => [row.claim_id, row]));
  const queueAfterByClaim = new Map(queueRowsAfter.map(row => [row.claim_id, row]));
  const changedQueueClaimIds = claimIds.filter(id => (
    canonical(queueBeforeByClaim.get(id)) !== canonical(queueAfterByClaim.get(id))
  ));
  const queueIsolationMaterial = {
    contract:'casepath.gate1-negative-queue-isolation/1.0.0',
    claim_id:claimId,
    before_roster_sha256:queueRosterSha256(queueRowsBefore),
    after_roster_sha256:queueRosterSha256(queueRowsAfter),
    before_focal_row_sha256:queueBefore.row_sha256,
    after_focal_row_sha256:queueAfter.row_sha256,
    changed_claim_ids:changedQueueClaimIds,
    unchanged_nonfocal_count:149,
    nonfocal_before_sha256:queueRosterSha256(queueRowsBefore, claimId),
    nonfocal_after_sha256:queueRosterSha256(queueRowsAfter, claimId),
  };
  const queueIsolation = {
    ...queueIsolationMaterial,
    receipt_sha256:sha(queueIsolationMaterial),
  };
  const postMutationQueueTiming = {
    claim_id:claimId,
    boundary:'authoritative_rejection_recovery_through_full_queue_read',
    evidence_origin:'sealed_gate1_safe_rejection_control',
    row_count:queueRowsAfter.length,
    unique_claim_count:new Set(queueRowsAfter.map(row => row.claim_id)).size,
    mutation_visible:queueRowsAfter.some(row => row.claim_id === claimId
      && row.state_sha256 === recovered.operational_projection.workspace_prefix.state_sha256
      && row.operational_projection.claim_loop_prefix.state_sha256 === recovered.loop_state.state_sha256),
    state_roster_sha256:sha(queueRowsAfter.map(row => ({
      claim_id:row.claim_id,
      workspace_state_sha256:row.state_sha256,
      claim_loop_state_sha256:row.operational_projection.claim_loop_prefix?.state_sha256 || null,
    })).sort((left, right) => left.claim_id.localeCompare(right.claim_id))),
    seconds:postMutationQueueSeconds,
  };
  const sourceAcquisitionSeconds = (advanceRequestStartedAt - commitStartedAt) / 1000;
  const postEvidenceReplanSeconds = (authoritativeReplanObservedAt - advanceRequestStartedAt) / 1000;
  check(`${prefix}: carryover timings and 150-row queue isolation are exact`,
    Number.isFinite(firstSafeActionSeconds) && firstSafeActionSeconds >= 0 && firstSafeActionSeconds <= 10
      && Number.isFinite(sourceAcquisitionSeconds) && sourceAcquisitionSeconds >= 0 && sourceAcquisitionSeconds <= 10
      && Number.isFinite(postEvidenceReplanSeconds) && postEvidenceReplanSeconds >= 0 && postEvidenceReplanSeconds <= 10
      && Number.isFinite(postMutationQueueSeconds) && postMutationQueueSeconds >= 0 && postMutationQueueSeconds <= 0.300
      && queueRowsBefore.length === 150
      && queueRowsAfter.length === 150
      && queueBeforeByClaim.size === 150
      && queueAfterByClaim.size === 150
      && postMutationQueueTiming.row_count === 150
      && postMutationQueueTiming.unique_claim_count === 150
      && postMutationQueueTiming.mutation_visible === true
      && canonical(changedQueueClaimIds) === canonical([claimId])
      && queueBefore.row_sha256 !== queueAfter.row_sha256
      && queueIsolation.nonfocal_before_sha256 === queueIsolation.nonfocal_after_sha256
      && queueIsolation.receipt_sha256 === sha(without(queueIsolation, 'receipt_sha256')));
  await page.screenshot({ path:path.join(out, 'workspace-rejection-control.png'), fullPage:true });
  return {
    claim_id: claimId,
    before,
    committed,
    recovered,
    ambiguous_copy: ambiguousCopy,
    recovered_copy: recoveredCopy,
    pending_advance_after_drop: pendingAdvance,
    requests: requestRows,
    responses,
    dropped_advance_response: droppedAdvanceResponse,
    source,
    queue_before: queueBefore,
    queue_after: queueAfter,
    journal_before: journalBefore,
    journal_after: committedJournal,
    raw_before_claim: rawBefore.claims.find(row => row.claim_id === claimId),
    raw_after_claim: committedRaw.claims.find(row => row.claim_id === claimId),
    authority_files_before: filesBefore,
    authority_files_after: committedFiles,
    authority_files_after_replay: recoveredFiles,
    authority_file_delta: fileDelta,
    authority_delta_roster: fileRoster,
    rejection_receipt: rejection,
    request_type_counts: requestTypeCounts,
    timing: {
      first_safe_action_seconds: firstSafeActionSeconds,
      source_acquisition_seconds: sourceAcquisitionSeconds,
      post_evidence_replan_seconds: postEvidenceReplanSeconds,
      post_mutation_queue_seconds: postMutationQueueSeconds,
    },
    post_mutation_queue_timing:postMutationQueueTiming,
    queue_isolation: queueIsolation,
  };
}

async function crashAfterDurableAcquisition(context, page, claimId, before, databasePath, authorityRoot, claimIds) {
  const prefix = `${claimId}: crash-after-durable-acquisition`;
  pageScenarios.set(page, 'crash-pre-acquisition');
  const loopPath = `/api/claim-loops/v1/workspace/claims/${claimId}/loop`;
  const registrationUrl = `${BASE}${loopPath}/evidence`;
  const requests = [];
  const responsePromises = [];
  const attach = target => {
    target.on('request', request => {
      const url = new URL(request.url());
      if (request.method() !== 'POST') return;
      if (url.pathname === `${loopPath}/evidence/intents`
        || url.pathname === `${loopPath}/evidence`
        || (url.pathname.startsWith(`${loopPath}/evidence/intents/`) && url.pathname.endsWith('/acquire'))
        || url.pathname === `${loopPath}/advance`) {
        requests.push({
          page: target === page ? 'pre-crash' : 'replacement',
          method: request.method(),
          path: url.pathname,
          body: request.postData(),
          idempotency_key: request.headers()['x-casepath-idempotency-key'] || null,
        });
      }
    });
    target.on('response', response => {
      const url = new URL(response.url());
      if (response.request().method() !== 'POST') return;
      if (url.pathname === `${loopPath}/evidence/intents`
        || url.pathname === `${loopPath}/evidence`
        || (url.pathname.startsWith(`${loopPath}/evidence/intents/`) && url.pathname.endsWith('/acquire'))
        || url.pathname === `${loopPath}/advance`) {
        responsePromises.push(response.body().then(raw => ({
          page: target === page ? 'pre-crash' : 'replacement',
          path: url.pathname,
          status: response.status(),
          body: JSON.parse(raw.toString('utf8')),
        })));
      }
    });
  };
  attach(page);
  const crashJournalBefore = await readClaimJournal(databasePath, claimId);
  const crashRawAuthorityBefore = await snapshotRawAuthority(databasePath, null, claimIds);
  const crashFilesBefore = await snapshotAuthority(authorityRoot);
  let aborted = false;
  await page.route(registrationUrl, async route => {
    if (!aborted && route.request().method() === 'POST') {
      aborted = true;
      return route.abort('connectionaborted');
    }
    return route.continue();
  });
  await page.locator('#cwLoopCommit').click();
  await page.waitForFunction(() => document.querySelector('#cwCommandStatus')?.textContent
    .includes('No valid completion receipt was received'), null, { timeout: 30_000 });
  const durableOnly = await serverLoop(claimId);
  const crashJournalAfter = await readClaimJournal(databasePath, claimId);
  const crashRawAuthorityAfter = await snapshotRawAuthority(databasePath, null, claimIds);
  const crashFilesAfter = await snapshotAuthority(authorityRoot);
  const crashFileDelta = authorityDelta(crashFilesBefore, crashFilesAfter);
  const crashFileRoster = buildAuthorityDeltaRoster(crashFileDelta, claimIds);
  const crashGlobalRawDelta = rawRowDelta(crashRawAuthorityBefore.rows, crashRawAuthorityAfter.rows);
  const crashFocalRawDelta = rawRowDelta(
    crashRawAuthorityBefore.bundles.get(claimId),
    crashRawAuthorityAfter.bundles.get(claimId),
  );
  const preCrashIntent = await pending(page, claimId, 'evidence-intent');
  const preCrashRegistration = await pending(page, claimId, 'evidence');
  const firstResponses = await Promise.all(responsePromises);
  check(`${prefix}: boundary has one durable acquisition and no domain effect`, aborted
    && requests.filter(row => row.path === `${loopPath}/evidence/intents`).length === 1
    && requests.filter(row => row.path.endsWith('/acquire')).length === 1
    && requests.filter(row => row.path === `${loopPath}/evidence`).length === 1
    && firstResponses.filter(row => row.path === `${loopPath}/evidence/intents`).length === 1
    && firstResponses.find(row => row.path === `${loopPath}/evidence/intents`)?.body.recovered_durable_acquisition === false
    && firstResponses.filter(row => row.path.endsWith('/acquire')).length === 1
    && durableOnly.stage_receipt === null
    && durableOnly.loop_state.state_sha256 === before.loop_state.state_sha256
    && durableOnly.loop_state.observations.length === before.loop_state.observations.length
    && canonical(crashJournalAfter) === canonical(crashJournalBefore)
    && crashGlobalRawDelta.length === 0
    && canonical(crashGlobalRawDelta) === canonical(crashFocalRawDelta)
    && crashFileDelta.deleted.length === 0
    && canonical([...new Set(crashFileRoster.map(row => row.kind))].sort()) === canonical([
      'acquisition-by-intent',
      'acquisitions',
      'claim-content-registry',
      'intents',
      'source-blobs',
    ])
    && crashFileRoster.length === 5
    && [...new Set(crashFileRoster.map(row => row.kind))]
      .every(kind => crashFileRoster.filter(row => row.kind === kind).length === 1)
    && crashFileRoster.every(row => row.json_valid
      && row.lineage_valid
      && row.derivation_path.length > 0
      && row.mapping === (row.kind === 'acquisition-by-intent' ? 'transitive' : 'direct')
      && canonical(row.resolved_claim_ids) === canonical([claimId]))
    && Boolean(preCrashIntent) && Boolean(preCrashRegistration), canonical({ requests, firstResponses, durableOnly }));
  const cleared = await page.evaluate(async () => {
    sessionStorage.clear();
    localStorage.clear();
    for (const cacheName of await caches.keys()) await caches.delete(cacheName);
    const databases = typeof indexedDB.databases === 'function' ? await indexedDB.databases() : [];
    await Promise.all(databases.filter(value => value.name).map(value => new Promise((resolve, reject) => {
      const request = indexedDB.deleteDatabase(value.name);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
      request.onblocked = () => reject(new Error(`IndexedDB deletion blocked: ${value.name}`));
    })));
    return {
      session_storage: sessionStorage.length,
      local_storage: localStorage.length,
      caches: (await caches.keys()).length,
      indexed_databases: typeof indexedDB.databases === 'function' ? (await indexedDB.databases()).length : 0,
    };
  });
  await context.clearCookies();

  check(`${prefix}: crash erases all browser storage before page replacement`,
    canonical(cleared) === canonical({ session_storage: 0, local_storage: 0, caches: 0, indexed_databases: 0 })
    && !await pending(page, claimId, 'evidence-intent')
    && !await pending(page, claimId, 'evidence')
    && !await pending(page, claimId, 'advance'));
  await page.close();

  const replacement = await context.newPage();
  pageScenarios.set(replacement, 'crash-replacement-page');
  attach(replacement);
  await replacement.goto(`${BASE}/?ui=final`, { waitUntil: 'domcontentloaded' });
  await waitWorkspace(replacement);
  await openClaim(replacement, claimId);
  await waitEvidenceWorkbench(replacement, `${prefix}: replacement`);
  check(`${prefix}: replacement starts with no browser command`,
    !await pending(replacement, claimId, 'evidence-intent')
      && !await pending(replacement, claimId, 'evidence')
      && !await pending(replacement, claimId, 'advance'));
  const started = performance.now();
  await replacement.locator('#cwLoopCommit').click();
  await replacement.waitForFunction(() => document.querySelector('#cwCommandStatus')?.textContent
    .includes('Observation committed once.'), null, { timeout: 30_000 });
  const seconds = (performance.now() - started) / 1000;
  const after = await serverLoop(claimId);
  const responses = await Promise.all(responsePromises);
  const intents = responses.filter(row => row.path === `${loopPath}/evidence/intents`).map(row => row.body);
  const acquisitions = responses.filter(row => row.path.endsWith('/acquire')).map(row => row.body);
  const registrations = requests.filter(row => row.path === `${loopPath}/evidence`);
  const originalRegistration = JSON.parse(registrations[0]?.body || 'null');
  const recoveredRegistration = JSON.parse(registrations[1]?.body || 'null');
  const registrationResponse = responses.find(row => row.page === 'replacement' && row.path === `${loopPath}/evidence`)?.body;
  const advanceRequest = JSON.parse(requests.find(row => row.page === 'replacement' && row.path === `${loopPath}/advance`)?.body || 'null');
  const advanceResponse = responses.find(row => row.page === 'replacement' && row.path === `${loopPath}/advance`)?.body;
  const source = await acquiredSourceBinding(claimId, acquisitions[1]);
  const requestPathRoster = requests.map(row => `${row.page}:${row.path}`);
  const responsePathRoster = responses.map(row => `${row.page}:${row.path}`);
  check(`${prefix}: request and response rosters prove the exact interrupted seam`,
    canonical(requestPathRoster) === canonical([
      `pre-crash:${loopPath}/evidence/intents`,
      `pre-crash:${loopPath}/evidence/intents/${intents[0]?.intent?.intent_id}/acquire`,
      `pre-crash:${loopPath}/evidence`,
      `replacement:${loopPath}/evidence/intents`,
      `replacement:${loopPath}/evidence/intents/${intents[1]?.intent?.intent_id}/acquire`,
      `replacement:${loopPath}/evidence`,
      `replacement:${loopPath}/advance`,
    ])
      && canonical(responsePathRoster) === canonical([
        `pre-crash:${loopPath}/evidence/intents`,
        `pre-crash:${loopPath}/evidence/intents/${intents[0]?.intent?.intent_id}/acquire`,
        `replacement:${loopPath}/evidence/intents`,
        `replacement:${loopPath}/evidence/intents/${intents[1]?.intent?.intent_id}/acquire`,
        `replacement:${loopPath}/evidence`,
        `replacement:${loopPath}/advance`,
      ])
      && responses.every(row => row.status === 200), canonical({ requestPathRoster, responsePathRoster }));
  check(`${prefix}: server recovers the exact durable intent without client state`, intents.length === 2
    && intents[0].recovered_durable_acquisition === false
    && intents[1].recovered_durable_acquisition === true
    && canonical(intents[0].intent) === canonical(intents[1].intent)
    && JSON.parse(requests.filter(row => row.path === `${loopPath}/evidence/intents`)[0].body).idempotency_key
      !== JSON.parse(requests.filter(row => row.path === `${loopPath}/evidence/intents`)[1].body).idempotency_key);
  check(`${prefix}: recovered acquisition is exact and registers once`, acquisitions.length === 2
    && canonical(acquisitions[0]) === canonical(acquisitions[1])
    && source.passed
    && registrations.length === 2
    && canonical(originalRegistration) === canonical(recoveredRegistration)
    && registrations[0].idempotency_key === intents[0].intent.idempotency_key
      && registrations[1].idempotency_key === intents[0].intent.idempotency_key
      && canonical(Object.keys(recoveredRegistration).sort()) === canonical([...REGISTRATION_BODY_FIELDS].sort()));
  validateReceiptHashes(intents[1], acquisitions[1], registrationResponse, prefix);
  check(`${prefix}: recovered receipts and the sole advance are exactly state-bound`,
    exactLoopSha(intents[0], 'response_sha256')
      && exactLoopSha(intents[0].intent, 'receipt_sha256')
      && exactLoopSha(acquisitions[0], 'response_sha256')
      && exactLoopSha(acquisitions[0].acquisition_receipt, 'receipt_sha256')
      && exactLoopSha(advanceResponse, 'response_sha256')
      && advanceRequest.expected_revision === before.loop_state.revision
      && advanceRequest.expected_state_sha256 === before.loop_state.state_sha256
      && advanceRequest.action_sha256 === before.loop_state.selected_action.action_sha256
      && advanceRequest.stage_receipt_sha256 === registrationResponse.stage_receipt.receipt_sha256);
  check(`${prefix}: replacement advances the authoritative loop exactly once`,
    after.loop_state.revision === before.loop_state.revision + 2
      && after.loop_state.observations.length === before.loop_state.observations.length + 1
      && !await pending(replacement, claimId, 'evidence-intent')
      && !await pending(replacement, claimId, 'evidence')
      && !await pending(replacement, claimId, 'advance'));
  timingRows.push({ claim_id: claimId, boundary: 'replacement_commit_to_authoritative_replan', seconds });
  return {
    page: replacement,
    before,
    durable_only: durableOnly,
    crash_journal_before: crashJournalBefore,
    crash_journal_after: crashJournalAfter,
    crash_raw_delta: [],
    crash_authority_delta_roster: crashFileRoster,
    after,
    requests,
    responses,
    source,
    seconds,
  };
}

async function applyScopedCorrection(page, claimId, observed, databasePath, claimIds) {
  const prefix = `${claimId}: scoped correction`;
  check(`${prefix}: server enumerates exactly one correction candidate`,
    observed.correction_count === 0 && observed.correction_candidates.length === 1);
  const candidate = observed.correction_candidates[0];
  const priorRevision = observed.loop_state.revision;
  const priorStateSha = observed.loop_state.state_sha256;
  const correctionPath = `/api/claim-loops/v1/workspace/claims/${claimId}/loop/corrections`;
  const requests = [];
  const capture = request => {
    const url = new URL(request.url());
    if (url.pathname === correctionPath || url.pathname === `${correctionPath}/preview`) {
      requests.push({ method: request.method(), path: url.pathname, body: request.postData() });
    }
  };
  page.on('request', capture);
  const previewJournalBefore = await readClaimJournal(databasePath, claimId);
  const previewQueueBefore = await queueAll('correction-preview-before');
  const previewAuthorityBefore = await snapshotRawAuthority(databasePath, null, claimIds);
  let committedResponse = null;
  let dropped = false;
  await page.route(`**${correctionPath}`, async route => {
    if (!dropped && route.request().method() === 'POST') {
      const committed = await route.fetch();
      committedResponse = await committed.json();
      dropped = true;
      return route.abort('connectionaborted');
    }
    return route.continue();
  });
  await page.locator('#cwCorrectionReview').click();
  await page.waitForSelector('#cwCorrectionPreview');
  const afterPreview = await serverLoop(claimId);
  const previewJournalAfter = await readClaimJournal(databasePath, claimId);
  const previewQueueAfter = await queueAll('correction-preview-after');
  const previewAuthorityAfter = await snapshotRawAuthority(databasePath, null, claimIds);
  const previewGlobalRawDelta = rawRowDelta(previewAuthorityBefore.rows, previewAuthorityAfter.rows);
  const previewRawDelta = rawRowDelta(
    previewAuthorityBefore.bundles.get(claimId),
    previewAuthorityAfter.bundles.get(claimId),
  );
  check(`${prefix}: preview is mutation-free and shows locality hashes`,
    afterPreview.loop_state.revision === priorRevision
      && afterPreview.loop_state.state_sha256 === priorStateSha
      && canonical(previewJournalAfter) === canonical(previewJournalBefore)
      && canonical(previewQueueAfter) === canonical(previewQueueBefore)
      && (await page.locator('#cwCorrectionPreview').textContent()).includes('unchanged')
      && await page.locator('#cwCorrectionPreview code').count() === 3);
  check(`${prefix}: preview persists only its focal preparation authority`,
    previewRawDelta.length === 3
      && previewGlobalRawDelta.length === 3
      && canonical(previewGlobalRawDelta) === canonical(previewRawDelta)
      && previewRawDelta.every(row => row.change === 'created')
      && canonical(previewRawDelta.map(row => row.table).sort()) === canonical([
        'claim_loop_client_requests',
        'claim_loop_correction_artifacts',
        'claim_loop_corrections',
      ])
      && rawCell(previewRawDelta.find(row => row.table === 'claim_loop_client_requests').after, 'request_type')
        === 'workspace_prepare_correction'
      && rawCell(previewRawDelta.find(row => row.table === 'claim_loop_client_requests').after, 'status')
        === 'COMPLETED', canonical(previewRawDelta));
  await page.locator('#cwCorrectionConfirm').click();
  await page.waitForFunction(() => document.querySelector('#cwCommandStatus')?.textContent
    .includes('No valid correction completion receipt was received'), null, { timeout: 30_000 });
  page.off('request', capture);
  const corrected = await serverLoop(claimId);
  const delta = corrected.latest_correction;
  const priorFact = observed.loop_state.facts.find(row => row.fact_id === delta.fact_id);
  const priorEvidence = observed.loop_state.checklist.items.find(row => row.item_id === delta.evidence_item_id);
  const correctedFact = corrected.loop_state.facts.find(row => row.fact_id === delta.fact_id);
  const correctedEvidence = corrected.loop_state.checklist.items.find(row => row.item_id === delta.evidence_item_id);
  const actualAfterSemantics = {
    fact_state: correctedFact?.state,
    normalized_value: correctedFact?.normalized_value,
    value: correctedFact?.value,
    explanation: correctedFact?.explanation,
    evidence_status: correctedEvidence?.status,
  };
  const pendingRaw = await pending(page, claimId, 'correction-apply');
  const pendingCommand = pendingRaw ? JSON.parse(pendingRaw) : null;
  const correctionResponseValidation = evaluateCorrectionResponsePredicates({
    dropped,
    corrected,
    priorRevision,
    committedResponse,
    delta,
    pendingCommand,
    exactLoopSha,
    canonical,
  });
  process.stdout.write(`${JSON.stringify({
    check:`${prefix}: lost response leaves one durable case-local effect`,
    ...correctionResponseValidation,
  })}\n`);
  check(`${prefix}: lost response leaves one durable case-local effect`,
    correctionResponseValidation.passed, canonical(correctionResponseValidation));
  const correctionLocalityValidation = evaluateScopedCorrectionPredicates({
    observedState:observed.loop_state,
    correctedState:corrected.loop_state,
    candidate,
    delta,
    priorFact,
    priorEvidence,
    correctedFact,
    correctedEvidence,
    actualAfterSemantics,
    claimLoopSha,
    canonical,
  });
  process.stdout.write(`${JSON.stringify({
    check:`${prefix}: authoritative delta changes only the target fact/evidence`,
    ...correctionLocalityValidation,
  })}\n`);
  check(`${prefix}: authoritative delta changes only the target fact/evidence`,
    correctionLocalityValidation.passed, canonical(correctionLocalityValidation));
  check(`${prefix}: browser cannot mint correction scope or effect`, requests.length === 2
    && canonical(JSON.parse(requests[0].body)) === canonical({
      candidate_sha256: candidate.candidate_sha256,
      expected_revision: priorRevision,
      expected_state_sha256: priorStateSha,
    })
    && canonical(JSON.parse(requests[1].body)) === canonical({ correction_id: delta.correction_id }));
  const reloadJournalBefore = await readClaimJournal(databasePath, claimId);
  const reloadAuthorityBefore = await snapshotRawAuthority(databasePath, null, claimIds);
  const reloadMutationPostCount = mutationPosts.length;
  const reloadBrowserPostCount = browserNetwork.filter(row => row.kind === 'request' && row.method === 'POST').length;
  await page.reload({ waitUntil: 'domcontentloaded' });
  await waitWorkspace(page);
  await page.waitForFunction(id => document.querySelector('.cw-detail-title small')?.textContent === id, claimId);
  await page.waitForSelector('#cwCorrectionResult');
  const rendered = await page.locator('#cwCorrectionResult').textContent();
  const renderedBeforeSemantics = await page.locator('#cwCorrectionResult .cw-correction-semantics').getAttribute('data-before-semantics');
  const renderedAfterSemantics = await page.locator('#cwCorrectionResult .cw-correction-semantics').getAttribute('data-after-semantics');
  const reloaded = await serverLoop(claimId);
  const reloadJournalAfter = await readClaimJournal(databasePath, claimId);
  const reloadAuthorityAfter = await snapshotRawAuthority(databasePath, null, claimIds);
  check(`${prefix}: reload confirms exact correction without duplicate effect`,
    reloaded.latest_correction.delta_sha256 === delta.delta_sha256
      && reloaded.loop_state.state_sha256 === corrected.loop_state.state_sha256
      && await page.locator('#cwCorrectionResult [data-delta-sha256]').getAttribute('data-delta-sha256') === delta.delta_sha256
      && canonical(JSON.parse(renderedBeforeSemantics)) === canonical(candidate.current_semantics)
      && canonical(JSON.parse(renderedAfterSemantics)) === canonical(actualAfterSemantics)
      && rendered.includes(`${delta.unrelated_facts_after_sha256.slice(0, 16)}… unchanged`)
      && !await pending(page, claimId, 'correction-preview')
      && !await pending(page, claimId, 'correction-apply')
      && mutationPosts.length === reloadMutationPostCount
      && browserNetwork.filter(row => row.kind === 'request' && row.method === 'POST').length === reloadBrowserPostCount
      && canonical(reloadJournalAfter) === canonical(reloadJournalBefore)
      && rawRowDelta(reloadAuthorityBefore.rows, reloadAuthorityAfter.rows).length === 0);
  await page.unroute(`**${correctionPath}`);
  await page.screenshot({ path: path.join(out, 'workspace-scoped-correction.png'), fullPage: true });
  return {
    before: observed,
    candidate,
    requests,
    preview_journal_before: previewJournalBefore,
    preview_journal_after: previewJournalAfter,
    preview_queue_before_sha256: sha(previewQueueBefore),
    preview_queue_after_sha256: sha(previewQueueAfter),
    preview_raw_delta: previewRawDelta,
    committed_response: committedResponse,
    corrected,
    delta,
    actual_after_semantics: actualAfterSemantics,
    reload_journal_before: reloadJournalBefore,
    reload_journal_after: reloadJournalAfter,
    reloaded,
  };
}

async function visibleAuthority(page) {
  return page.evaluate(() => ({
    claim_id: document.querySelector('.cw-detail-title small')?.textContent || null,
    title: document.querySelector('.cw-detail-title h2')?.textContent || '',
    body: document.querySelector('.cw-body-copy')?.textContent || '',
    outcome: document.querySelector('#cwLoopWorkbench')?.dataset.outcome || null,
    projection_sha256: document.querySelector('#cwCurrentProcess')?.dataset.operationalProjectionSha256 || null,
    current_process: [...document.querySelectorAll('#cwCurrentProcess .cw-state-item')].map(cell => ({
      label: cell.querySelector('span')?.textContent || '',
      value: cell.querySelector('strong')?.textContent || '',
      detail: cell.querySelector('small')?.textContent || '',
    })),
    proposal: document.querySelector('#cwLoopProposal')?.textContent || '',
    action_sha256: document.querySelector('#cwLoopProposal')?.dataset.actionSha256 || null,
    evidence_classes: [...document.querySelectorAll('[data-evidence-class]')].map(section => ({
      evidence_class: section.dataset.evidenceClass,
      count: Number(section.querySelector('header span')?.textContent),
      items: [...section.querySelectorAll('[data-evidence-item-id]')].map(item => ({
        evidence_item_id: item.dataset.evidenceItemId,
        text: item.textContent || '',
      })),
    })),
    role_receipts: [...document.querySelectorAll('#cwAgentReceipts [data-agent-id]')].map(row => ({ id: row.dataset.agentId, text: row.textContent || '' })),
    gate_receipts: [...document.querySelectorAll('#cwGateReceipts [data-gate-id]')].map(row => ({ id: row.dataset.gateId, text: row.textContent || '' })),
    evidence_readiness: document.querySelector('#cwEvidenceProgress header span')?.textContent || '',
    progress_copy: document.querySelector('#cwEvidenceProgress .cw-progress-copy')?.textContent || '',
    progress_now: document.querySelector('#cwEvidenceProgress [role="progressbar"]')?.getAttribute('aria-valuenow') || null,
    verified_line: document.querySelector('.cw-verified-line')?.textContent || '',
    terminal_receipt: document.querySelector('.cw-terminal-receipt')?.textContent || '',
    safety_boundary: document.querySelector('.cw-safety-boundary')?.textContent || '',
  }));
}

const candidateStart = await captureCandidateSourceSnapshot({ requireApiBootReceipt: true });
const sourceRowsRaw = Buffer.from(`${candidateStart.sourceRows.join('\n')}\n`);
const builtRowsRaw = Buffer.from(`${candidateStart.builtRows.join('\n')}\n`);
await fs.writeFile(path.join(out, 'candidate-source-manifest.sha256'), sourceRowsRaw, { flag: 'wx' });
await fs.writeFile(path.join(out, 'candidate-built-static-manifest.sha256'), builtRowsRaw, { flag: 'wx' });
await fs.writeFile(path.join(out, 'boot-receipt-before.json'), candidateStart.apiBootReceiptBytes, { flag: 'wx' });

let browser;
try {
  const roster = await queueAll('before-focal-selection');
  check('Gate 1 sees exactly the source-bound 150-claim roster', roster.length === 150
    && new Set(roster.map(row => row.claim_id)).size === 150
    && canonical(roster.map(row => row.claim_id).sort()) === canonical(corpusManifest.claims.map(row => row.claim_id).sort()));
  const claimIds = corpusManifest.claims.map(row => row.claim_id).sort();
  const databasePath = path.resolve(candidateStart.apiBootReceipt.runtime.database_path);
  const authorityRoot = path.join(path.dirname(databasePath), 'workspace-evidence-v1');
  const rawAuthorityCatalog = await readRawAuthorityCatalog(databasePath);
  check('Gate 1 raw-authority sqlite_master contains exactly the allowed user tables',
    rawAuthorityCatalogIsExact(rawAuthorityCatalog), canonical(rawAuthorityCatalog));
  const rawAuthoritySchema = await readRawAuthoritySchema(databasePath);
  check('Gate 1 raw-authority table coverage exactly matches the live schema and real primary keys',
    rawAuthoritySchemaIsExact(rawAuthoritySchema), canonical(rawAuthoritySchema));
  const rawAuthorityPristine = await snapshotRawAuthority(databasePath, roster, claimIds);
  check('Gate 1 commits the exact pre-selection queue and raw authority for all 150 claims',
    rawAuthorityPristine.claims.length === 150
      && rawAuthorityPristine.queueByClaim.size === 150,
  canonical({ table_counts: rawAuthorityPristine.table_counts, unscoped_rows: rawAuthorityPristine.unscoped.length }));
  const claimFilesById = new Map();
  const registryFilesById = new Map();
  await Promise.all(corpusManifest.claims.map(async binding => {
    const [claimRaw, registryRaw] = await Promise.all([
      fs.readFile(path.join(corpusRoot, binding.claim.path)),
      fs.readFile(path.join(corpusRoot, binding.source_registry.path)),
    ]);
    claimFilesById.set(binding.claim_id, claimRaw);
    registryFilesById.set(binding.claim_id, registryRaw);
  }));
  const staticPolicyRaw = await fs.readFile(path.join(corpusRoot, 'policy/static-rule-templates-v3.json'));
  const witnessSelection = selectQualifiedGate1Witness({
    queueRows: roster.map(qualifiedWitnessQueueProjection),
    corpusManifestFile: corpusManifestRaw,
    claimFilesById,
    registryFilesById,
    staticPolicyFile: staticPolicyRaw,
  });
  const selectorSourcePath = path.join(repository, 'casepath-qa/qualified-gate1-witness-v1.mjs');
  const selectorSourceRaw = await fs.readFile(selectorSourcePath);
  const witnessReceiptMaterial = {
    ...witnessSelection,
    selector_source_path: 'casepath-qa/qualified-gate1-witness-v1.mjs',
    selector_source_sha256: sha(selectorSourceRaw),
    publication_boundary: 'written-before-any-gate1-claim-mutation',
  };
  const witnessReceipt = { ...witnessReceiptMaterial, receipt_sha256: sha(witnessReceiptMaterial) };
  const witnessReceiptRaw = Buffer.from(`${JSON.stringify(witnessReceipt, null, 2)}\n`);
  await fs.writeFile(path.join(out, 'qualified-witness-selection.json'), witnessReceiptRaw, { flag:'wx' });
  check('Gate 1 prospective selector independently freezes the exact 44-claim qualified roster',
    witnessSelection.eligible_claim_ids.length === 44
      && witnessSelection.grammar_sha256 === '8635c2bc36b7223579f3a8b4860c4bd582fd02dff8c3035565910d9c59715f00'
      && witnessSelection.eligible_roster_sha256 === '1d4bb069772ab2ee99f0d82563cfc210c0d4cff9e0778003917a5e87faa9541e'
      && witnessSelection.selected_claim_id === witnessSelection.eligible_claim_ids[0]
      && witnessSelection.selected_source_entry_sha256 === 'cf1ea83886665172e146cc1a2af6f69046644dc8b40df05735a2a81f24aa9cb7'
      && witnessSelection.eligible_claims[0].predicted_initial_action.action_sha256 === '9ca6fde3470d2d0efce6cc86601701382fd7269bfe6ab6c4cea88fabc6d05e91'
      && witnessSelection.selected_qualification_sha256 === witnessSelection.eligible_claims[0].qualification_sha256
      && witnessSelection.selection_sha256 === 'd6ace476c8d39f4251c11c1cb652df2ea0862983e2963a11cb445b66fda9f7e4'
      && witnessSelection.selection_sha256 === sha(without(witnessSelection, 'selection_sha256')),
  canonical(witnessSelection));
  const claimId = witnessSelection.selected_claim_id;
  check('Gate 1 qualified selector reproduces the contract witness before any start',
    claimId === 'clm_0c1a91bc008f8747');
  const negativeClaimId = 'clm_a62c178195d21648';
  check('Gate 1 negative control is public, pristine, distinct, and selector-ineligible',
    bindings.has(negativeClaimId)
      && negativeClaimId !== claimId
      && !witnessSelection.eligible_claim_ids.includes(negativeClaimId)
      && roster.some(row => row.claim_id === negativeClaimId));
  const binding = bindings.get(claimId);
  const sourceClaim = JSON.parse(await fs.readFile(path.join(corpusRoot, binding.claim.path), 'utf8'));
  const ledgerBefore = await api('/api/model-ledger');

  browser = await chromium.launch({ executablePath, headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const browserReceipt = await captureBrowserExecutionReceipt({
    gatePath: fileURLToPath(import.meta.url),
    outputPath: out,
    outputEnvironmentKey: 'CASEPATH_WORKSPACE_QA_OUT',
    browserVersion: browser.version(),
    baseUrl: BASE,
    apiUrl: BASE,
  });
  const browserReceiptRaw = Buffer.from(`${JSON.stringify(browserReceipt, null, 2)}\n`);
  await fs.writeFile(path.join(out, 'browser-execution-receipt.json'), browserReceiptRaw, { flag: 'wx' });

  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  context.on('page', page => {
    page.on('pageerror', error => browserErrors.push({ scenario: pageScenarios.get(page) || 'unattributed', kind: 'pageerror', message: String(error) }));
    page.on('console', message => {
      if (['error', 'warning'].includes(message.type())) {
        browserErrors.push({ scenario: pageScenarios.get(page) || 'unattributed', kind: message.type(), message: message.text() });
      }
    });
    page.on('request', request => {
      const url = new URL(request.url());
      const row = {
        kind: 'request',
        scenario: pageScenarios.get(page) || 'unattributed',
        method: request.method(),
        url: url.href,
        body: request.postData(),
      };
      browserNetwork.push(row);
      const mutationMatch = request.method() === 'POST'
        ? url.pathname.match(/^\/api\/claim-loops\/v1\/workspace\/claims\/([^/]+)\/(?:owner|start|loop(?:\/.*)?)$/)
        : null;
      if (mutationMatch) mutationPosts.push({ ...row, claim_id: decodeURIComponent(mutationMatch[1]) });
    });
    page.on('response', response => {
      const url = new URL(response.url());
      browserNetwork.push({
        kind: 'response',
        scenario: pageScenarios.get(page) || 'unattributed',
        method: response.request().method(),
        url: url.href,
        status: response.status(),
      });
    });
  });
  await context.route('**/*', async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== BASE_ORIGIN) return route.abort('blockedbyclient');
    return route.continue();
  });

  let page = await context.newPage();
  pageScenarios.set(page, 'negative-rejection-control');
  await page.goto(`${BASE}/?ui=final`, { waitUntil:'domcontentloaded' });
  await waitWorkspace(page);
  await openClaim(page, negativeClaimId);
  const negativeDetailBefore = await serverDetail(negativeClaimId);
  const negativeFirstSafeStartedAt = performance.now();
  await page.locator('#cwStart').click();
  await waitEvidenceWorkbench(page, `${negativeClaimId}: rejection-control initial action`);
  const negativeFirstSafeActionSeconds = (performance.now() - negativeFirstSafeStartedAt) / 1000;
  const negativeBefore = await serverLoop(negativeClaimId);
  validateInputContract(negativeBefore, `${negativeClaimId}: rejection-control initial action`);
  const negativeQueueRowsBefore = await queueAll('negative-control-before-advance');
  check(`${negativeClaimId}: negative control starts one honest bounded review`,
    negativeDetailBefore.state.workflow_state === 'received'
      && negativeBefore.outcome === 'next_action'
      && negativeBefore.loop_state.observations.length === 0
      && negativeBefore.loop_state.action_history.length === 0);
  const negativeControl = await captureRejectedEvidenceRecovery(
    page,
    negativeClaimId,
    negativeBefore,
    databasePath,
    authorityRoot,
    claimIds,
    negativeQueueRowsBefore,
    negativeFirstSafeActionSeconds,
  );
  await page.close();

  const rosterBefore = await queueAll('main-witness-baseline-after-negative-control');
  const rawAuthorityBefore = await snapshotRawAuthority(databasePath, rosterBefore, claimIds);
  const initialDetail = await serverDetail(claimId);
  const journalBefore = await readClaimJournal(databasePath, claimId);
  const authorityBefore = await snapshotAuthority(authorityRoot);
  check(`${claimId}: selected main witness remains pristine after the isolated negative control`,
    journalBefore.length === 1
      && journalBefore[0].event.event_type === 'WORKSPACE_CLAIM_IMPORTED'
      && journalChainsAreExact(journalBefore)
      && canonical(rawAuthorityBefore.bundles.get(claimId)) === canonical(rawAuthorityPristine.bundles.get(claimId)),
  canonical({ journal_before:journalBefore, authority_file_count:authorityBefore.length }));

  page = await context.newPage();
  pageScenarios.set(page, 'initial-load');
  await page.goto(`${BASE}/?ui=final`, { waitUntil: 'domcontentloaded' });
  await waitWorkspace(page);
  await openClaim(page, claimId);
  check(`${claimId}: browser shows exact public customer message`,
    await page.locator('.cw-detail-title h2').textContent() === sourceClaim.customer_message.subject
      && await page.locator('.cw-body-copy').textContent() === sourceClaim.customer_message.body);
  const artifactRows = await page.locator('.cw-artifact').evaluateAll(async anchors => Promise.all(anchors.map(async anchor => {
    const response = await fetch(anchor.href, { cache: 'no-store' });
    const bytes = await response.arrayBuffer();
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    return {
      artifact_id: decodeURIComponent(new URL(anchor.href).pathname.split('/').at(-1)),
      status: response.status,
      size_bytes: bytes.byteLength,
      sha256: [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, '0')).join(''),
    };
  })));
  check(`${claimId}: browser artifact bytes exactly match the source binding`, canonical(artifactRows.sort((a, b) => a.artifact_id.localeCompare(b.artifact_id)))
    === canonical(binding.observable_artifacts.map(row => ({
      artifact_id: row.artifact_id,
      status: 200,
      size_bytes: row.size_bytes,
      sha256: row.sha256,
    })).sort((a, b) => a.artifact_id.localeCompare(b.artifact_id))));
  const accessibility = await new AxeBuilder({ page }).analyze();
  check(`${claimId}: workspace has no serious accessibility violation`,
    !accessibility.violations.some(row => ['critical', 'serious'].includes(row.impact)), canonical(accessibility.violations));
  await page.screenshot({ path: path.join(out, 'workspace-before.png'), fullPage: true });

  const startAt = performance.now();
  await page.locator('#cwStart').click();
  await waitEvidenceWorkbench(page, `${claimId}: initial action`);
  const firstSafeSeconds = (performance.now() - startAt) / 1000;
  timingRows.push({ claim_id: claimId, boundary: 'start_click_to_authoritative_first_safe_action', seconds: firstSafeSeconds });
  const postStartDetail = await serverDetail(claimId);
  const initialLoop = await serverLoop(claimId);
  validateInputContract(initialLoop, `${claimId}: initial action`);
  check(`${claimId}: start reaches an honest blocked review state`,
    postStartDetail.state.workflow_state === 'in_review'
      && postStartDetail.state.readiness_state === 'blocked'
      && postStartDetail.state.revision === initialDetail.state.revision + 1
      && postStartDetail.state.failure_or_unknown_effect === false
      && canonical(postStartDetail.state.intake_assessment.activity)
        === canonical({ model_calls: 0, provider_calls: 0, credential_reads: 0, cost_usd: 0 }));

  const crashed = await crashAfterDurableAcquisition(
    context,
    page,
    claimId,
    initialLoop,
    databasePath,
    authorityRoot,
    claimIds,
  );
  check(`${claimId}: first authentic acquisition matches the prospective selector proof`,
    crashed.source.receipt.source_entry_sha256 === witnessSelection.selected_source_entry_sha256
      && crashed.source.receipt.content_sha256 === witnessSelection.eligible_claims[0].adapter_candidate.span_sha256
      && crashed.source.receipt.text_start === witnessSelection.eligible_claims[0].adapter_candidate.text_start
      && crashed.source.receipt.text_end === witnessSelection.eligible_claims[0].adapter_candidate.text_end
      && crashed.source.text === witnessSelection.eligible_claims[0].adapter_candidate.exact_text);
  page = crashed.page;
  let current = crashed.after;
  const preCorrectionTransitions = [];
  for (let attempt = 1; current.outcome === 'next_action' && attempt <= 4; attempt += 1) {
    validateInputContract(current, `${claimId}: pre-correction evidence action ${attempt}`);
    const transition = await captureEvidenceTransition(
      page,
      claimId,
      current,
      `${claimId}: pre-correction evidence action ${attempt}`,
    );
    preCorrectionTransitions.push(transition);
    current = transition.after;
  }
  const terminalT0 = preCorrectionTransitions.at(-1);
  check(`${claimId}: the one authentic journey reaches typed safe abstention T0`,
    preCorrectionTransitions.length >= 1
      && terminalT0.after.outcome === 'abstain'
      && terminalT0.after.loop_state.phase === 'abstained'
      && terminalT0.after.loop_state.terminal_mode === 'abstain'
      && terminalT0.after.loop_state.selected_action === null
      && terminalT0.after.loop_state.abstain_reason === 'mandatory evidence is unresolved and no bounded action remains'
      && terminalT0.after.loop_state.action_history.length === terminalT0.after.loop_state.observations.length
      && terminalT0.after.loop_state.action_history.every(row => row.outcome === 'observed')
      && terminalT0.after.loop_state.action_history.some(row => row.action.action_kind === 'validate')
      && terminalPacketAuthorityIsExact(terminalT0.after, claimId));
  pageScenarios.set(page, 'scoped-correction');
  const correction = await applyScopedCorrection(page, claimId, terminalT0.after, databasePath, claimIds);
  pageScenarios.set(page, 'post-correction-journey');
  current = correction.reloaded;
  const postCorrectionTransitions = [];
  for (let attempt = 1; current.outcome === 'next_action' && attempt <= 4; attempt += 1) {
    validateInputContract(current, `${claimId}: post-correction evidence action ${attempt}`);
    const transition = await captureEvidenceTransition(
      page,
      claimId,
      current,
      `${claimId}: post-correction evidence action ${attempt}`,
    );
    postCorrectionTransitions.push(transition);
    current = transition.after;
  }
  const terminal = postCorrectionTransitions.at(-1);
  check(`${claimId}: scoped correction reterminalizes in typed safe abstention T1`,
    postCorrectionTransitions.length >= 1
      && terminal.after.outcome === 'abstain'
      && terminal.after.loop_state.phase === 'abstained'
      && terminal.after.loop_state.terminal_mode === 'abstain'
      && terminal.after.loop_state.selected_action === null
      && terminal.after.loop_state.abstain_reason === 'mandatory evidence is unresolved and no bounded action remains'
      && terminalPacketAuthorityIsExact(terminal.after, claimId));
  check(`${claimId}: every bounded specialist action is observed and the path includes validation`,
    terminal.after.loop_state.action_history.length === terminal.after.loop_state.observations.length
      && terminal.after.loop_state.action_history.every(row => row.outcome === 'observed')
      && terminal.after.loop_state.action_history.some(row => row.action.action_kind === 'validate'));
  check(`${claimId}: terminal packet is content- and authority-bound`,
    exactLoopSha(terminal.after.decision_packet, 'packet_sha256')
      && terminal.after.decision_packet.six_agent_cycle_receipt_sha256
        === terminal.after.loop_state.six_agent_cycle_receipt.receipt_sha256
      && terminal.after.decision_packet.deterministic_gate_receipt_sha256
        === terminal.after.loop_state.deterministic_gate_receipt.receipt_sha256
      && terminal.after.decision_packet.accepted_cycle_artifacts_sha256
        === terminal.after.loop_state.accepted_cycle_artifacts.receipt_sha256
      && canonical(terminal.after.decision_packet.provenance_edges)
        === canonical(terminal.after.loop_state.provenance_edges));

  const dom = await visibleAuthority(page);
  check(`${claimId}: terminal DOM exposes the same outcome, projection, evidence, and safety boundary`,
    dom.claim_id === claimId
      && dom.title === sourceClaim.customer_message.subject
      && dom.body === sourceClaim.customer_message.body
      && dom.outcome === terminal.after.outcome
      && dom.projection_sha256 === terminal.after.operational_projection.projection_sha256
      && dom.evidence_classes.length === 6
      && dom.role_receipts.length === 6
      && dom.gate_receipts.length === 3
      && dom.terminal_receipt.includes(terminal.after.decision_packet.packet_sha256.slice(0, 16))
      && dom.safety_boundary.includes('stopped rather than infer'));
  await page.screenshot({ path: path.join(out, 'workspace-terminal.png'), fullPage: true });
  const terminalReloadJournalBefore = await readClaimJournal(databasePath, claimId);
  const terminalReloadAuthorityBefore = await snapshotRawAuthority(databasePath, null, claimIds);
  const terminalReloadMutationPostCount = mutationPosts.length;
  const terminalReloadBrowserPostCount = browserNetwork.filter(row => row.kind === 'request' && row.method === 'POST').length;
  pageScenarios.set(page, 'terminal-reload');
  await page.reload({ waitUntil: 'domcontentloaded' });
  await waitWorkspace(page);
  await page.waitForFunction(id => document.querySelector('.cw-detail-title small')?.textContent === id, claimId);
  const reloaded = await serverLoop(claimId);
  const terminalReloadJournalAfter = await readClaimJournal(databasePath, claimId);
  const terminalReloadAuthorityAfter = await snapshotRawAuthority(databasePath, null, claimIds);
  check(`${claimId}: terminal state reload is mutation-free and byte-stable`,
    reloaded.loop_state.state_sha256 === terminal.after.loop_state.state_sha256
      && reloaded.decision_packet.packet_sha256 === terminal.after.decision_packet.packet_sha256
      && reloaded.correction_count === 1
      && reloaded.latest_correction.delta_sha256 === correction.delta.delta_sha256
      && reloaded.loop_state.observations.length === terminal.after.loop_state.observations.length
      && await page.locator('#cwLoopWorkbench').getAttribute('data-outcome') === 'abstain'
      && !await pending(page, claimId, 'evidence-intent')
      && !await pending(page, claimId, 'evidence')
      && !await pending(page, claimId, 'advance')
      && mutationPosts.length === terminalReloadMutationPostCount
      && browserNetwork.filter(row => row.kind === 'request' && row.method === 'POST').length === terminalReloadBrowserPostCount
      && canonical(terminalReloadJournalAfter) === canonical(terminalReloadJournalBefore)
      && rawRowDelta(terminalReloadAuthorityBefore.rows, terminalReloadAuthorityAfter.rows).length === 0);
  await context.close();

  const rosterAfter = await queueAll('after-terminal-context-close');
  const rawAuthorityCatalogAfter = await readRawAuthorityCatalog(databasePath);
  check('Gate 1 raw-authority sqlite_master remains exact and byte-identical after the journey',
    rawAuthorityCatalogIsExact(rawAuthorityCatalogAfter)
      && canonical(rawAuthorityCatalogAfter) === canonical(rawAuthorityCatalog),
  canonical(rawAuthorityCatalogAfter));
  const rawAuthorityAfter = await snapshotRawAuthority(databasePath, rosterAfter, claimIds);
  check('Gate 1 terminal queue remains the exact source-bound 150-claim roster',
    rosterAfter.length === 150
      && new Set(rosterAfter.map(row => row.claim_id)).size === 150
      && canonical(rosterAfter.map(row => row.claim_id).sort()) === canonical(claimIds));

  const mutatedClaimIds = [...new Set(mutationPosts.map(row => row.claim_id))].sort();
  check('Gate 1 mutates exactly the prospective witness and required negative control', mutationPosts.length > 0
    && canonical(mutatedClaimIds) === canonical([claimId, negativeClaimId].sort()), canonical(mutationPosts));
  check('Gate 1 browser traffic stays on canonical localhost', browserNetwork.length > 0
    && browserNetwork.every(row => new URL(row.url).origin === BASE_ORIGIN));
  const expectedBrowserErrors = [
    { scenario: 'crash-pre-acquisition', kind: 'error', message: 'Failed to load resource: net::ERR_CONNECTION_ABORTED' },
    { scenario: 'negative-rejection-control', kind: 'error', message: 'Failed to load resource: net::ERR_CONNECTION_ABORTED' },
    { scenario: 'scoped-correction', kind: 'error', message: 'Failed to load resource: net::ERR_CONNECTION_ABORTED' },
  ];
  check('Gate 1 has exactly the three scenario-attributed intentional aborted-resource console errors',
    canonical([...browserErrors].sort((a, b) => canonical(a).localeCompare(canonical(b))))
      === canonical([...expectedBrowserErrors].sort((a, b) => canonical(a).localeCompare(canonical(b)))),
  canonical(browserErrors));
  const ledgerAfter = await api('/api/model-ledger');
  check('Gate 1 model ledger is byte-identical and empty', canonical(ledgerAfter) === canonical(ledgerBefore)
    && ledgerAfter.summary.records === 0 && ledgerAfter.summary.network_calls === 0);

  const beforeClaimRoots = new Map(rawAuthorityBefore.claims.map(row => [row.claim_id, row]));
  const afterClaimRoots = new Map(rawAuthorityAfter.claims.map(row => [row.claim_id, row]));
  const changedBundleClaimIds = claimIds.filter(id => canonical(rawAuthorityBefore.bundles.get(id))
    !== canonical(rawAuthorityAfter.bundles.get(id)));
  const changedQueueClaimIds = claimIds.filter(id => canonical(rawAuthorityBefore.queueByClaim.get(id))
    !== canonical(rawAuthorityAfter.queueByClaim.get(id)));
  const overallChangedBundleClaimIds = claimIds.filter(id => canonical(rawAuthorityPristine.bundles.get(id))
    !== canonical(rawAuthorityAfter.bundles.get(id)));
  const overallChangedQueueClaimIds = claimIds.filter(id => canonical(rawAuthorityPristine.queueByClaim.get(id))
    !== canonical(rawAuthorityAfter.queueByClaim.get(id)));
  check('Gate 1 pristine-to-terminal raw authority changes exactly the two declared controls',
    canonical(overallChangedBundleClaimIds) === canonical([claimId, negativeClaimId].sort())
      && canonical(overallChangedQueueClaimIds) === canonical([claimId, negativeClaimId].sort()),
  canonical({overallChangedBundleClaimIds, overallChangedQueueClaimIds}));
  const unchangedClaimIds = claimIds.filter(id => id !== claimId);
  check('Gate 1 raw authority proves 149 claim bundles and queue rows are byte-identical',
    unchangedClaimIds.length === 149
      && unchangedClaimIds.every(id => canonical(rawAuthorityBefore.bundles.get(id))
        === canonical(rawAuthorityAfter.bundles.get(id)))
      && unchangedClaimIds.every(id => beforeClaimRoots.get(id).bundle_merkle_root
        === afterClaimRoots.get(id).bundle_merkle_root)
      && unchangedClaimIds.every(id => canonical(rawAuthorityBefore.queueByClaim.get(id))
        === canonical(rawAuthorityAfter.queueByClaim.get(id)))
      && unchangedClaimIds.every(id => beforeClaimRoots.get(id).queue_sha256
        === afterClaimRoots.get(id).queue_sha256));
  check('Gate 1 raw authority and queue change only the focal claim',
    canonical(changedBundleClaimIds) === canonical([claimId])
      && canonical(changedQueueClaimIds) === canonical([claimId])
      && beforeClaimRoots.get(claimId).bundle_merkle_root !== afterClaimRoots.get(claimId).bundle_merkle_root
      && beforeClaimRoots.get(claimId).queue_sha256 !== afterClaimRoots.get(claimId).queue_sha256
      && rawAuthorityBefore.bundle_roster_merkle_root !== rawAuthorityAfter.bundle_roster_merkle_root
      && rawAuthorityBefore.queue_roster_merkle_root !== rawAuthorityAfter.queue_roster_merkle_root,
  canonical({ changedBundleClaimIds, changedQueueClaimIds }));
  check('Gate 1 unscoped raw SQL authority is byte-identical',
    canonical(rawAuthorityAfter.unscoped) === canonical(rawAuthorityBefore.unscoped)
      && rawAuthorityAfter.unscoped_merkle_root === rawAuthorityBefore.unscoped_merkle_root);

  const focalRawDelta = rawRowDelta(
    rawAuthorityBefore.bundles.get(claimId),
    rawAuthorityAfter.bundles.get(claimId),
  );
  const focalAssignmentBasisCounts = Object.fromEntries([...new Set(rawAuthorityAfter.assignments
    .filter(row => row.claim_id === claimId).map(row => row.basis))].sort().map(basis => [
    basis,
    rawAuthorityAfter.assignments.filter(row => row.claim_id === claimId && row.basis === basis).length,
  ]));
  const legacyRuns = tableRows(rawAuthorityAfter, claimId, 'runs');
  const legacyStream = tableRows(rawAuthorityAfter, claimId, 'run_stream_events')
    .sort((left, right) => rawNumber(left, 'sequence') - rawNumber(right, 'sequence'));
  const emptyLegacyTables = ['events', 'reviews', 'memories', 'candidates', 'model_calls'];
  const focalDeltaTables = [...new Set(focalRawDelta.map(row => row.table))].sort();
  check(`${claimId}: focal raw SQL delta is typed, length-framed, and confined to the exact authority tables`,
    focalRawDelta.every(row => row.change !== 'deleted'
      && /^[0-9a-f]{64}$/.test((row.after || row.before).framed_sha256)
      && (row.after || row.before).cells.every(cell => ['null', 'integer', 'real', 'text', 'blob'].includes(cell.sql_type)))
      && canonical(focalDeltaTables) === canonical([
        'claim_loop_acquisitions',
        'claim_loop_checkpoints',
        'claim_loop_client_requests',
        'claim_loop_correction_artifacts',
        'claim_loop_corrections',
        'claim_loop_events',
        'claim_loop_tool_artifacts',
        'run_stream_events',
        'runs',
      ]), canonical(focalDeltaTables));
  check(`${claimId}: legacy execution authority is exactly one completed run and its two terminal stream events`,
    rawAuthorityAfter.table_counts.runs === rawAuthorityBefore.table_counts.runs + 1
      && legacyRuns.length === 1
      && rawCell(legacyRuns[0], 'session_id') === 'casepath-workspace-claim-loop-v1'
      && rawCell(legacyRuns[0], 'claim_id') === claimId
      && rawCell(legacyRuns[0], 'status') === 'complete'
      && rawAuthorityAfter.table_counts.run_stream_events === rawAuthorityBefore.table_counts.run_stream_events + 2
      && legacyStream.length === 2
      && legacyStream.every(row => rawCell(row, 'session_id') === 'casepath-workspace-claim-loop-v1'
        && rawCell(row, 'run_id') === rawCell(legacyRuns[0], 'run_id'))
      && canonical(legacyStream.map(row => rawNumber(row, 'sequence'))) === canonical([1, 2])
      && canonical(legacyStream.map(row => rawCell(row, 'event_type')))
        === canonical(['run.queued', 'run.completed'])
      && emptyLegacyTables.every(table => rawAuthorityAfter.table_counts[table] === 0),
  canonical({ runs: legacyRuns, run_stream_events: legacyStream, table_counts: rawAuthorityAfter.table_counts }));

  const clientRequests = tableRows(rawAuthorityAfter, claimId, 'claim_loop_client_requests');
  const requestTypeCounts = Object.fromEntries([...new Set(clientRequests.map(row => rawCell(row, 'request_type')))]
    .sort().map(type => [type, clientRequests.filter(row => rawCell(row, 'request_type') === type).length]));
  const observationCount = terminal.after.loop_state.observations.length;
  check(`${claimId}: terminal client-request authority has the exact completed enum multiset`,
    clientRequests.every(row => rawCell(row, 'session_id') === 'casepath-workspace-claim-loop-v1'
      && rawCell(row, 'loop_id') === terminal.after.loop_state.loop_id
      && rawCell(row, 'status') === 'COMPLETED'
      && rawCell(row, 'completed_at') !== null
      && rawCell(row, 'response_sha256') !== null
      && rawCell(row, 'response_json') !== null
      && rawCell(row, 'request_sha256') === claimLoopSha(rawJson(row, 'request_json'))
      && rawCell(row, 'response_sha256') === claimLoopSha(rawJson(row, 'response_json')))
      && canonical(requestTypeCounts) === canonical({
        advance: observationCount,
        apply_correction: 1,
        create: 1,
        select_action: 1,
        workspace_ensure: 1,
        workspace_prepare_correction: 1,
      }), canonical({ requestTypeCounts, statuses: clientRequests.map(row => rawCell(row, 'status')) }));
  const acquisitions = tableRows(rawAuthorityAfter, claimId, 'claim_loop_acquisitions');
  const toolArtifacts = tableRows(rawAuthorityAfter, claimId, 'claim_loop_tool_artifacts');
  const corrections = tableRows(rawAuthorityAfter, claimId, 'claim_loop_corrections');
  const correctionArtifacts = tableRows(rawAuthorityAfter, claimId, 'claim_loop_correction_artifacts');
  check(`${claimId}: acquisition, artifact, and correction authority counts are exact`,
    acquisitions.length === observationCount
      && toolArtifacts.length === observationCount
      && corrections.length === 1
      && correctionArtifacts.length === 1
      && acquisitions.every(row => {
        const receipt = rawJson(row, 'acquisition_json');
        const payloadHex = rawCell(row, 'raw_payload');
        const payload = Buffer.from(payloadHex || '', 'hex');
        return row.cells.find(cell => cell.name === 'raw_payload')?.sql_type === 'blob'
          && /^[0-9A-F]+$/.test(payloadHex)
          && rawCell(row, 'receipt_sha256') === receipt?.receipt_sha256
          && rawCell(row, 'session_id') === receipt?.session_id
          && rawCell(row, 'loop_id') === receipt?.loop_id
          && rawCell(row, 'action_id') === receipt?.action_id
          && rawCell(row, 'dispatch_sha256') === receipt?.dispatch_sha256
          && rawCell(row, 'status') === receipt?.status
          && receipt?.status === 'observed'
          && exactLoopSha(receipt, 'receipt_sha256')
          && payload.length === receipt.raw_byte_count
          && sha(payload) === receipt.raw_bytes_sha256
          && payload.toString('utf8') === receipt.sanitized_content;
      })
      && toolArtifacts.every(row => {
        const receipt = rawJson(row, 'artifact_json');
        return rawCell(row, 'receipt_sha256') === receipt?.receipt_sha256
          && rawCell(row, 'session_id') === receipt?.session_id
          && rawCell(row, 'loop_id') === receipt?.loop_id
          && rawCell(row, 'action_id') === receipt?.action_id
          && rawCell(row, 'dispatch_sha256') === receipt?.dispatch_sha256
          && exactLoopSha(receipt, 'receipt_sha256')
          && exactLoopSha(receipt?.acquisition_receipt, 'receipt_sha256')
          && receipt?.acquisition_receipt_sha256 === receipt?.acquisition_receipt?.receipt_sha256;
      })
      && corrections.every(row => {
        const correctionValue = rawJson(row, 'correction_json');
        return rawCell(row, 'correction_id') === correctionValue?.correction_id
          && rawCell(row, 'correction_sha256') === correctionValue?.correction_sha256
          && correctionValue?.correction_id === `correction.${correctionValue?.correction_sha256}`
          && correctionValue?.correction_sha256
            === claimLoopSha(without(without(correctionValue, 'correction_sha256'), 'correction_id'));
      })
      && correctionArtifacts.every(row => {
        const artifact = rawJson(row, 'artifact_json');
        return rawCell(row, 'receipt_sha256') === artifact?.receipt_sha256
          && rawCell(row, 'parent_state_sha256') === artifact?.parent_state_sha256
          && exactLoopSha(artifact, 'receipt_sha256');
      }));

  const journalAfter = await readClaimJournal(databasePath, claimId);
  const authorityAfter = await snapshotAuthority(authorityRoot);
  const fileDelta = authorityDelta(authorityBefore, authorityAfter);
  const authorityDeltaRoster = buildAuthorityDeltaRoster(fileDelta, claimIds);
  const workspaceEvents = journalAfter.filter(row => row.session_id === 'casepath-workspace-local');
  const loopEvents = journalAfter.filter(row => row.session_id === 'casepath-workspace-claim-loop-v1');
  const authorityClaimIdLiterals = new Set(fileDelta.created_or_changed.flatMap(row => {
    if (!row.relative_path.endsWith('.json')) return [];
    const text = Buffer.from(row.content_b64, 'base64').toString('utf8');
    return [...text.matchAll(/\bclm_[0-9a-f]{16}\b/g)].map(match => match[0]);
  }));
  const loopEventTypes = loopEvents.map(row => row.event.event_type);
  const focalEventDelta = rawRowDelta(
    tableRows(rawAuthorityBefore, claimId, 'claim_loop_events'),
    tableRows(rawAuthorityAfter, claimId, 'claim_loop_events'),
  );
  const beforeJournalKeys = new Set(journalBefore.map(row => `${row.session_id}\u0000${row.loop_id}`));
  const rawEventPrefixesExact = [...beforeJournalKeys].every(key => {
    const [sessionId, loopId] = key.split('\u0000');
    const beforeRows = journalBefore.filter(row => row.session_id === sessionId && row.loop_id === loopId);
    const afterRows = journalAfter.filter(row => row.session_id === sessionId && row.loop_id === loopId);
    return canonical(afterRows.slice(0, beforeRows.length)) === canonical(beforeRows);
  });
  const correctionEventIndex = loopEventTypes.indexOf('CORRECTION_APPLIED');
  const beforeCorrectionTypes = loopEventTypes.slice(2, correctionEventIndex);
  const afterCorrectionTypes = loopEventTypes.slice(correctionEventIndex + 1);
  check(`${claimId}: raw journals contain one lifecycle, one correction, and the exact admitted observations`,
    journalChainsAreExact(journalAfter)
      && rawEventPrefixesExact
      && focalEventDelta.every(row => row.change === 'created' && row.before === null)
      && canonical(workspaceEvents.map(row => row.event.event_type))
        === canonical(['WORKSPACE_CLAIM_IMPORTED', 'WORKSPACE_PROCESSING_STARTED'])
      && loopEventTypes[0] === 'LOOP_CREATED'
      && loopEventTypes[1] === 'ACTION_SELECTED'
      && beforeCorrectionTypes.length === terminalT0.after.loop_state.observations.length * 2
      && beforeCorrectionTypes.every((value, index) => value === (index % 2 === 0
        ? 'ACTION_DISPATCH_STARTED' : 'OBSERVATION_INGESTED'))
      && loopEventTypes.filter(value => value === 'CORRECTION_APPLIED').length === 1
      && afterCorrectionTypes.length === postCorrectionTransitions.length * 2
      && afterCorrectionTypes.every((value, index) => value === (index % 2 === 0
        ? 'ACTION_DISPATCH_STARTED' : 'OBSERVATION_INGESTED'))
      && loopEventTypes.filter(value => value === 'OBSERVATION_INGESTED').length
        === terminal.after.loop_state.observations.length
      && loopEvents.at(-1).event.resulting_state_sha256 === terminal.after.loop_state.state_sha256
      && workspaceEvents.at(-1).event.resulting_state_sha256 === postStartDetail.state.state_sha256,
  canonical(journalAfter.map(row => ({ session_id: row.session_id, sequence: row.sequence, event_type: row.event.event_type }))));
  const focalCheckpoints = tableRows(rawAuthorityAfter, claimId, 'claim_loop_checkpoints');
  check(`${claimId}: both checkpoint rows exactly bind their typed journal tails`,
    focalCheckpoints.length === 2
      && canonical(focalCheckpoints.map(row => `${rawCell(row, 'session_id')}\u0000${rawCell(row, 'loop_id')}`).sort())
        === canonical([
          `casepath-workspace-claim-loop-v1\u0000${terminal.after.loop_state.loop_id}`,
          `casepath-workspace-local\u0000workspace.${claimId}`,
        ])
      && focalCheckpoints.every(row => {
        const sessionId = rawCell(row, 'session_id');
        const loopId = rawCell(row, 'loop_id');
        const state = rawJson(row, 'state_json');
        const events = journalAfter.filter(event => event.session_id === sessionId && event.loop_id === loopId);
        const tail = events.at(-1)?.event;
        const digest = claimLoopSha;
        return state
          && rawNumber(row, 'revision') === state.revision
          && rawCell(row, 'state_sha256') === state.state_sha256
          && rawCell(row, 'last_event_sha256') === tail?.event_sha256
          && state.state_sha256 === tail?.resulting_state_sha256
          && state.state_sha256 === digest(without(state, 'state_sha256'));
      }), canonical(focalCheckpoints));
  check(`${claimId}: filesystem authority delta is immutable, nonempty, and claim-scoped`,
    fileDelta.deleted.length === 0
      && fileDelta.created_or_changed.length > 0
      && fileDelta.created_or_changed.every(row => row.relative_path.startsWith('authority-v3/'))
      && canonical([...authorityClaimIdLiterals].sort()) === canonical([claimId])
      && authorityDeltaRoster.every(row => row.json_valid
        && row.lineage_valid
        && row.derivation_path.length > 0
        && canonical(row.resolved_claim_ids) === canonical([claimId])));
  const expectedAuthorityKinds = [
    'acquisition-by-intent',
    'acquisitions',
    'admission-by-interpretation',
    'admissions',
    'claim-content-registry',
    'intents',
    'outcome-by-acquisition',
    'proposal-by-acquisition',
    'proposals',
    'registrations',
    'source-blobs',
  ];
  const actualAuthorityKinds = [...new Set(authorityDeltaRoster.map(row => row.kind))].sort();
  const authorityKindCounts = Object.fromEntries(expectedAuthorityKinds.map(kind => [
    kind,
    authorityDeltaRoster.filter(row => row.kind === kind).length,
  ]));
  const transitiveAuthorityKinds = new Set([
    'acquisition-by-intent',
    'admission-by-interpretation',
    'admissions',
    'outcome-by-acquisition',
    'proposal-by-acquisition',
  ]);
  check(`${claimId}: filesystem authority contains exactly admitted path kinds with no rejection or unassigned file`,
    canonical(actualAuthorityKinds) === canonical(expectedAuthorityKinds)
      && expectedAuthorityKinds.every(kind => authorityKindCounts[kind] === observationCount)
      && authorityDeltaRoster.every(row => row.kind !== 'rejections'
        && row.kind !== 'rejection-by-acquisition'
        && row.resolved_claim_ids.length === 1
        && row.lineage_valid
        && row.mapping === (transitiveAuthorityKinds.has(row.kind) ? 'transitive' : 'direct')
        && row.derivation_path.length > 0),
  canonical({
    actualAuthorityKinds,
    expected_count_per_kind: observationCount,
    authorityKindCounts,
    transitive_kinds: [...transitiveAuthorityKinds].sort(),
    unassigned_or_invalid: authorityDeltaRoster.filter(row => row.resolved_claim_ids.length !== 1
      || !row.lineage_valid || row.derivation_path.length === 0),
  }));

  const candidateEnd = await captureCandidateSourceSnapshot({
    requireApiBootReceipt: true,
    allowValidatedWorkspaceJournalAdvance: true,
  });
  check('Gate 1 source/build/runtime identity is stable', canonical(candidateEnd) === canonical(candidateStart));
  await fs.writeFile(path.join(out, 'boot-receipt-after.json'), candidateEnd.apiBootReceiptBytes, { flag: 'wx' });

  const isolationMaterial = {
    contract: 'casepath.gate1-single-claim-isolation/1.0.0',
    claim_id: claimId,
    capture: {
      sqlite_cli: '/usr/bin/sqlite3',
      read_only: true,
      immutable: false,
      wal_included: true,
      sqlite_master_sha256: sha(rawAuthorityCatalog),
      sqlite_master: rawAuthorityCatalog,
      sqlite_master_after_sha256: sha(rawAuthorityCatalogAfter),
      live_schema_sha256: sha(rawAuthoritySchema),
      live_schema: rawAuthoritySchema,
      canonical_row_encoding: 'sql-type-plus-utf8-length-frame-v1; BLOB=uppercase-hex',
      primary_key_order: Object.fromEntries(RAW_AUTHORITY_TABLES.map(row => [row.name, row.primary_key])),
      queue_page_receipts: queuePageReceipts,
      merkle_domains: {
        claim: 'casepath.gate1.raw-authority.claim/<claim_id>',
        queue: 'casepath.gate1.queue.claim/<claim_id>',
        roster: 'casepath.gate1.raw-authority.claim-roster',
        bundle_roster: 'casepath.gate1.raw-authority.bundle-roster',
        queue_roster: 'casepath.gate1.queue.roster',
        unscoped: 'casepath.gate1.raw-authority.unscoped',
      },
    },
    before: {
      table_counts: rawAuthorityBefore.table_counts,
      claims_merkle_root: rawAuthorityBefore.claims_merkle_root,
      bundle_roster_merkle_root: rawAuthorityBefore.bundle_roster_merkle_root,
      queue_roster_merkle_root: rawAuthorityBefore.queue_roster_merkle_root,
      unscoped_merkle_root: rawAuthorityBefore.unscoped_merkle_root,
      unscoped_row_count: rawAuthorityBefore.unscoped.length,
      claim_roots: rawAuthorityBefore.claims,
    },
    after: {
      table_counts: rawAuthorityAfter.table_counts,
      claims_merkle_root: rawAuthorityAfter.claims_merkle_root,
      bundle_roster_merkle_root: rawAuthorityAfter.bundle_roster_merkle_root,
      queue_roster_merkle_root: rawAuthorityAfter.queue_roster_merkle_root,
      unscoped_merkle_root: rawAuthorityAfter.unscoped_merkle_root,
      unscoped_row_count: rawAuthorityAfter.unscoped.length,
      claim_roots: rawAuthorityAfter.claims,
    },
    isolation: {
      unchanged_claim_count: unchangedClaimIds.length,
      unchanged_claim_ids: unchangedClaimIds,
      changed_bundle_claim_ids: changedBundleClaimIds,
      changed_queue_claim_ids: changedQueueClaimIds,
      unscoped_byte_identical: canonical(rawAuthorityBefore.unscoped) === canonical(rawAuthorityAfter.unscoped),
      focal_queue_before: rawAuthorityBefore.queueByClaim.get(claimId),
      focal_queue_after: rawAuthorityAfter.queueByClaim.get(claimId),
    },
    focal: {
      raw_delta: focalRawDelta.map(row => ({
        change: row.change,
        table: row.table,
        primary_key: row.primary_key,
        before: compactRawRow(row.before),
        after: compactRawRow(row.after),
      })),
      client_request_type_counts: requestTypeCounts,
      observations: observationCount,
      acquisitions: acquisitions.length,
      tool_artifacts: toolArtifacts.length,
      corrections: corrections.length,
      correction_artifacts: correctionArtifacts.length,
      checkpoint_count: focalCheckpoints.length,
      assignment_basis_counts: focalAssignmentBasisCounts,
      authority_expected_count_per_kind: observationCount,
      authority_kind_counts: authorityKindCounts,
    },
  };
  const singleClaimIsolation = { ...isolationMaterial, receipt_sha256: sha(isolationMaterial) };
  const isolationRaw = Buffer.from(`${JSON.stringify(singleClaimIsolation, null, 2)}\n`);
  const focalEventDeltaRaw = Buffer.from(`${focalEventDelta.map(row => canonical({
    contract: 'casepath.gate1-focal-event-delta-row/1.0.0',
    change: row.change,
    table: row.table,
    primary_key: row.primary_key,
    framed_sha256: row.after.framed_sha256,
    cells: row.after.cells,
  })).join('\n')}\n`);
  const authorityDeltaRosterRaw = Buffer.from(`${authorityDeltaRoster.map(row => canonical({
    contract: 'casepath.gate1-authority-delta-roster-row/1.0.0',
    ...row,
    row_sha256: sha(row),
  })).join('\n')}\n`);
  const negativeControlMaterial = {
    contract:'casepath.gate1-safe-rejection-negative-control/1.0.0',
    control_claim_id:negativeClaimId,
    expected_semantic_effect:false,
    exact_ui_copy:'Evidence was safely rejected; no observation was added. CasePath kept the bounded action open.',
    pristine_claim_root:rawAuthorityPristine.claims.find(row => row.claim_id === negativeClaimId),
    evidence:negativeControl,
  };
  const negativeControlReceipt = {
    ...negativeControlMaterial,
    receipt_sha256:sha(negativeControlMaterial),
  };
  const negativeControlRaw = Buffer.from(`${JSON.stringify(negativeControlReceipt, null, 2)}\n`);
  await fs.writeFile(path.join(out, 'single-claim-isolation.json'), isolationRaw, { flag: 'wx' });
  await fs.writeFile(path.join(out, 'focal-event-delta.ndjson'), focalEventDeltaRaw, { flag: 'wx' });
  await fs.writeFile(path.join(out, 'authority-delta-roster.ndjson'), authorityDeltaRosterRaw, { flag: 'wx' });
  await fs.writeFile(path.join(out, 'negative-rejection-control.json'), negativeControlRaw, { flag:'wx' });

  const authorityChain = {
    contract: 'casepath.gate1-single-claim-authority-chain/1.0.0',
    claim_id: claimId,
    qualified_witness_selection: {
      path:'qualified-witness-selection.json',
      sha256:sha(witnessReceiptRaw),
      receipt_sha256:witnessReceipt.receipt_sha256,
    },
    negative_rejection_control: {
      path:'negative-rejection-control.json',
      sha256:sha(negativeControlRaw),
      receipt_sha256:negativeControlReceipt.receipt_sha256,
    },
    corpus_binding: binding,
    source_claim: sourceClaim,
    initial_detail: initialDetail,
    post_start_detail: postStartDetail,
    initial_loop: initialLoop,
    crash_recovery: without(crashed, 'page'),
    terminal_t0_transition: terminalT0,
    pre_correction_transitions: preCorrectionTransitions,
    scoped_correction: correction,
    post_correction_transitions: postCorrectionTransitions,
    terminal_transition: terminal,
    reloaded_loop: reloaded,
    terminal_dom: dom,
    mutation_posts: mutationPosts,
    raw_journal_before: journalBefore,
    raw_journal_after: journalAfter,
    authority_files_before: authorityBefore,
    authority_files_after: authorityAfter,
    authority_file_delta: fileDelta,
    single_claim_isolation: { path: 'single-claim-isolation.json', sha256: sha(isolationRaw), receipt_sha256: singleClaimIsolation.receipt_sha256 },
    focal_event_delta: { path: 'focal-event-delta.ndjson', sha256: sha(focalEventDeltaRaw), rows: focalEventDelta.length },
    authority_delta_roster: { path: 'authority-delta-roster.ndjson', sha256: sha(authorityDeltaRosterRaw), rows: authorityDeltaRoster.length },
    terminal_reload_journal_before: terminalReloadJournalBefore,
    terminal_reload_journal_after: terminalReloadJournalAfter,
  };
  const authorityRaw = Buffer.from(`${JSON.stringify(authorityChain, null, 2)}\n`);
  const networkRaw = Buffer.from(`${browserNetwork.map(row => canonical(row)).join('\n')}\n`);
  const timingRaw = Buffer.from(`${JSON.stringify({
    contract: 'casepath.gate1-claim-bound-latency/1.0.0',
    clock: 'node_performance_monotonic',
    rows: timingRows,
  }, null, 2)}\n`);
  await fs.writeFile(path.join(out, 'authority-chain.json'), authorityRaw, { flag: 'wx' });
  const journalRaw = Buffer.from(`${journalAfter.map(row => canonical(row)).join('\n')}\n`);
  const authorityFilesRaw = Buffer.from(`${JSON.stringify({
    contract: 'casepath.gate1-authority-files/1.0.0',
    root: authorityRoot,
    before: authorityBefore,
    after: authorityAfter,
    delta: fileDelta,
  }, null, 2)}\n`);
  await fs.writeFile(path.join(out, 'raw-journal-events.ndjson'), journalRaw, { flag: 'wx' });
  await fs.writeFile(path.join(out, 'authority-files.json'), authorityFilesRaw, { flag: 'wx' });
  await fs.writeFile(path.join(out, 'browser-network.ndjson'), networkRaw, { flag: 'wx' });
  await fs.writeFile(path.join(out, 'latency-results.json'), timingRaw, { flag: 'wx' });

  const negativeCarryoverQueueRow = rosterAfter.find(row => row.claim_id === negativeClaimId);
  const mainCarryoverQueueRow = rosterAfter.find(row => row.claim_id === claimId);
  const gate2CarryoverMaterial = {
    contract:'casepath.gate1-gate2-carryovers/1.0.0',
    ordered_claim_ids:[negativeClaimId, claimId],
    rows:[
      {
        role:'safe_rejection_zero_effect',
        claim_id:negativeClaimId,
        final_outcome:'next_action',
        typed_safe_rejection:true,
        authoritative_semantic_effect:false,
        loop_revision:negativeControl.recovered.loop_state.revision,
        loop_state_sha256:negativeControl.recovered.loop_state.state_sha256,
        workspace_state_sha256:negativeControl.recovered.operational_projection.workspace_prefix.state_sha256,
        observation_count:negativeControl.recovered.loop_state.observations.length,
        selected_action_sha256:negativeControl.recovered.loop_state.selected_action.action_sha256,
        queue_row_sha256:negativeCarryoverQueueRow?.row_sha256 || null,
        negative_control_receipt_sha256:negativeControlReceipt.receipt_sha256,
      },
      {
        role:'qualified_typed_abstention',
        claim_id:claimId,
        final_outcome:'abstain',
        typed_abstention:true,
        loop_revision:reloaded.loop_state.revision,
        loop_state_sha256:reloaded.loop_state.state_sha256,
        workspace_state_sha256:reloaded.operational_projection.workspace_prefix.state_sha256,
        observation_count:reloaded.loop_state.observations.length,
        selected_action_sha256:null,
        queue_row_sha256:mainCarryoverQueueRow?.row_sha256 || null,
        qualified_witness_selection_receipt_sha256:witnessReceipt.receipt_sha256,
      },
    ],
    aggregate_claim_count:150,
    fresh_gate2_claim_count:148,
    expected_outcomes:{next_action:149, decision_ready:0, abstain:1},
    expected_gate2_journal_delta:{total:740, claim_loop:592, workspace:148},
    expected_gate2_sidecar_delta:{total:296, acquisition:148, tool_artifact:148},
    expected_gate2_admitted_authority_per_kind:148,
  };
  const gate2Carryovers = {
    ...gate2CarryoverMaterial,
    receipt_sha256:sha(gate2CarryoverMaterial),
  };
  check('Gate 1 exports exactly the ordered rejection and abstention carryovers for Gate 2',
    negativeCarryoverQueueRow?.state_sha256 === gate2Carryovers.rows[0].workspace_state_sha256
      && mainCarryoverQueueRow?.state_sha256 === gate2Carryovers.rows[1].workspace_state_sha256
      && canonical(gate2Carryovers.ordered_claim_ids) === canonical([negativeClaimId, claimId])
      && gate2Carryovers.rows[0].observation_count === 0
      && gate2Carryovers.rows[1].final_outcome === 'abstain'
      && gate2Carryovers.receipt_sha256 === sha(without(gate2Carryovers, 'receipt_sha256')));
  const checksRaw = Buffer.from(`${checks.map(row => canonical(row)).join('\n')}\n`);
  await fs.writeFile(path.join(out, 'executed-checks.ndjson'), checksRaw, { flag: 'wx' });

  const reportMaterial = {
    contract: 'casepath.claims-workspace-browser-acceptance/1.0.0',
    status: 'PASS',
    base_url: BASE,
    claim_count: 150,
    mutated_claim_count: 2,
    mutated_claim_ids: [negativeClaimId, claimId],
    selected_claim_binding_sha256: binding.binding_sha256,
    qualified_witness_selection: { path:'qualified-witness-selection.json', sha256:sha(witnessReceiptRaw), semantic_sha256:witnessReceipt.receipt_sha256 },
    negative_rejection_control: { path:'negative-rejection-control.json', sha256:sha(negativeControlRaw), semantic_sha256:negativeControlReceipt.receipt_sha256 },
    gate2_carryovers:gate2Carryovers,
    corpus_manifest_file_sha256: sha(corpusManifestRaw),
    checks,
    timing: {
      first_safe_action_seconds: firstSafeSeconds,
      first_safe_action_budget_seconds: 10,
      evidence_transition_rows: timingRows.filter(row => row.boundary.includes('replan')),
      evidence_transition_budget_seconds: 10,
    },
    authority_chain: { path: 'authority-chain.json', sha256: sha(authorityRaw) },
    single_claim_isolation: { path: 'single-claim-isolation.json', sha256: sha(isolationRaw), semantic_sha256: singleClaimIsolation.receipt_sha256 },
    focal_event_delta: { path: 'focal-event-delta.ndjson', sha256: sha(focalEventDeltaRaw), rows: focalEventDelta.length },
    authority_delta_roster: { path: 'authority-delta-roster.ndjson', sha256: sha(authorityDeltaRosterRaw), rows: authorityDeltaRoster.length },
    raw_journal_events: { path: 'raw-journal-events.ndjson', sha256: sha(journalRaw), rows: journalAfter.length },
    authority_files: { path: 'authority-files.json', sha256: sha(authorityFilesRaw), delta_files: fileDelta.created_or_changed.length },
    browser_network: { path: 'browser-network.ndjson', sha256: sha(networkRaw), rows: browserNetwork.length },
    executed_checks: { path: 'executed-checks.ndjson', sha256: sha(checksRaw), rows: checks.length, passed: checks.length },
    latency_results: { path: 'latency-results.json', sha256: sha(timingRaw), rows: timingRows.length },
    candidate_source_identity: candidateStart.identity,
    api_runtime_identity: candidateStart.apiBootIdentity,
    browser_execution_receipt: {
      path: 'browser-execution-receipt.json',
      sha256: sha(browserReceiptRaw),
      semantic_sha256: browserReceipt.receipt_sha256,
    },
    activity: { model_calls: 0, provider_calls: 0, credential_reads: 0, external_network_calls: 0, cost_usd: 0 },
    later_gate_boundary: 'GATE_2_AND_GATE_3_NOT_RUN',
  };
  const report = { ...reportMaterial, receipt_sha256: sha(reportMaterial) };
  const reportRaw = Buffer.from(`${JSON.stringify(report, null, 2)}\n`);
  await fs.writeFile(path.join(out, 'report.json'), reportRaw, { flag: 'wx' });
  const manifestRows = [];
  for (const entry of (await fs.readdir(out, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
    if (!entry.isFile() || entry.isSymbolicLink() || entry.name === 'MANIFEST.sha256') {
      throw new Error(`Gate 1 evidence contains a noncanonical entry: ${entry.name}`);
    }
    manifestRows.push(`${sha(await fs.readFile(path.join(out, entry.name)))}  ${entry.name}`);
  }
  await fs.writeFile(path.join(out, 'MANIFEST.sha256'), `${manifestRows.join('\n')}\n`, { flag: 'wx' });
  console.log(JSON.stringify({
    result: 'PASS',
    receipt_sha256: report.receipt_sha256,
    report_file_sha256: sha(reportRaw),
    mutated_claim_ids: [negativeClaimId, claimId],
    checks: checks.length,
  }));
} finally {
  await browser?.close();
}
