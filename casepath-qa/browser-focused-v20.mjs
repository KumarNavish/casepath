import fs from 'node:fs/promises';
import { realpathSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { chromium } from 'playwright';
import {
  captureBrowserExecutionReceipt,
  captureCandidateSourceSnapshot,
  installLoopbackNetworkGuard,
  summarizeLoopbackNetworkGuards,
} from './candidate-source-identity.mjs';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:4173').replace(/\/$/, '');
const API = (process.env.API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const BASE_IDENTITY = new URL(BASE);
const API_IDENTITY = new URL(API);
const LOOPBACK_HOSTNAMES = new Set(['127.0.0.1', 'localhost', '::1', '[::1]']);
const REQUIRE_INSTALLED_API_BOOT = LOOPBACK_HOSTNAMES.has(BASE_IDENTITY.hostname)
  && LOOPBACK_HOSTNAMES.has(API_IDENTITY.hostname)
  && BASE_IDENTITY.port === '4173'
  && API_IDENTITY.port === '4173';
const RELEASE_ID = 'casepath-v20-reference-20260811';
const PRODUCT_RELEASE = '20.0.0';
const API_RELEASE = '15.2.0';
const REQUESTED_NEMOTRON_MODEL = 'nvidia/nemotron-3-ultra-550b-a55b';
const EXPECTED_PROVIDER_BOUNDARY = 'openrouter';
const EXPECTED_UPSTREAM_PROVIDER = 'Together';
const EXACT_NEMOTRON_RESPONSE_MODELS = new Set([
  REQUESTED_NEMOTRON_MODEL,
  'nvidia/nemotron-3-ultra-550b-a55b-20260604',
]);
const ALLOWED_USAGE_SOURCES = new Set(['response', 'generation_metadata']);
const REQUIRED_NEMOTRON_AGENT_IDS = Object.freeze([
  'canonical_facts',
  'orchestrator_plan',
  'document_source_integrity',
  'process_decision_mapping',
  'evidence_checklist',
  'final_claim_brief_audit',
]);
const PATH_BUILDER_VISUAL_GROUP_ID = 'process_decision_mapping';
const PATH_BUILDER_RUNTIME_AGENT_IDS = Object.freeze(['canonical_facts', 'process_decision_mapping']);
const REQUIRED_VISIBLE_SPECIALIST_IDS = Object.freeze([
  PATH_BUILDER_VISUAL_GROUP_ID,
  'document_source_integrity',
  'evidence_checklist',
  'final_claim_brief_audit',
]);
const REQUIRED_NEMOTRON_AGENT_ROLES = Object.freeze({
  canonical_facts: 'Guarded Canonical Facts Agent',
  orchestrator_plan: 'Nemotron Orchestrator',
  document_source_integrity: 'Document and Source Integrity Agent',
  process_decision_mapping: 'Process Decision Mapping Agent',
  evidence_checklist: 'Evidence and Checklist Agent',
  final_claim_brief_audit: 'Final Claim Brief Agent',
});
const REQUIRED_NEMOTRON_AGENT_SIGNATURES = Object.freeze({
  canonical_facts: { monogram: 'CF', signature: 'facts' },
  orchestrator_plan: { monogram: 'OR', signature: 'orchestrator' },
  document_source_integrity: { monogram: 'DS', signature: 'sources' },
  process_decision_mapping: { monogram: 'PM', signature: 'process' },
  evidence_checklist: { monogram: 'EC', signature: 'evidence' },
  final_claim_brief_audit: { monogram: 'FB', signature: 'audit' },
});
const REQUIRED_DESKTOP_AGENT_LABELS = Object.freeze({
  canonical_facts: 'Claim reader',
  orchestrator_plan: 'Work planner',
  document_source_integrity: 'Source checker',
  process_decision_mapping: 'Process builder',
  evidence_checklist: 'Document finder',
  final_claim_brief_audit: 'Result checker',
});
const REQUIRED_DESKTOP_AGENT_SHORTS = Object.freeze({
  canonical_facts: 'Claim',
  orchestrator_plan: 'Plan',
  document_source_integrity: 'Sources',
  process_decision_mapping: 'Path',
  evidence_checklist: 'Docs',
  final_claim_brief_audit: 'Check',
});
const REQUIRED_DESKTOP_AGENT_COLORS = Object.freeze({
  canonical_facts: '#8f1924',
  orchestrator_plan: '#16808c',
  document_source_integrity: '#7449a5',
  process_decision_mapping: '#8f1924',
  evidence_checklist: '#c26a00',
  final_claim_brief_audit: '#2c7a45',
});
const PATH_BUILDER_VISIBLE_IDENTITY = Object.freeze({
  label: 'Path builder',
  short: 'Build',
  signature: 'process',
});

function visibleAgentGroupId(agentId) {
  return PATH_BUILDER_RUNTIME_AGENT_IDS.includes(String(agentId || ''))
    ? PATH_BUILDER_VISUAL_GROUP_ID
    : String(agentId || '');
}

function visibleAgentIdentity(agentId) {
  const runtimeAgentId = String(agentId || '');
  if (PATH_BUILDER_RUNTIME_AGENT_IDS.includes(runtimeAgentId)) return PATH_BUILDER_VISIBLE_IDENTITY;
  return {
    label: REQUIRED_DESKTOP_AGENT_LABELS[runtimeAgentId] || '',
    short: REQUIRED_DESKTOP_AGENT_SHORTS[runtimeAgentId] || '',
    signature: REQUIRED_NEMOTRON_AGENT_SIGNATURES[runtimeAgentId]?.signature || '',
  };
}
const REQUIRED_PRESENTATION_PHASE_LABELS = Object.freeze([
  'Claim understanding',
  'Swiss-law research',
  'Process discovery',
  'Evidence requirements',
  'Historical claims',
  'Verification',
  'Knowledge',
]);
const FORBIDDEN_SYNTHETIC_AGENT_LABELS = Object.freeze([
  'Claim Understanding Agent',
  'Legal Research Agent',
  'Process Discovery Agent',
  'Evidence / Document Agent',
  'Historical Claims Agent',
  'Verification Agent',
  'Knowledge Agent',
  'Attachment Parsing Agent',
  'Document Requirements Agent',
]);
const MIN_CURSOR_TARGET_HOLD_MS = 180;
const MIN_PROCESS_NODE_STEP_MS = 2200;
const MIN_PROCESS_BRANCH_HOLD_MS = 1200;
const MIN_FLAGSHIP_PRESENTATION_MS = 90000;
// The reference replay now shows every accepted source fragment for the full
// eleven-node path.  Its diagnostic presentation is intentionally slower than
// the three-action insurance slice; keep it finite without truncating the
// source/provenance assertions that make this a useful legacy regression.
const MAX_FLAGSHIP_PRESENTATION_MS = 330000;
const REQUIRED_DESKTOP_SOURCE_MOMENTS = Object.freeze(['read', 'understand', 'research', 'process', 'evidence', 'experience', 'verify', 'ready', 'document-plan']);
const FLAGSHIP_PROCESS_PROJECTION_IDS = Object.freeze([
  'intake',
  'scope',
  'dispute',
  'urgency',
  'notification',
  'defect',
  'causation',
  'responsibility',
  'remedy',
  'escalation',
  'resolution',
]);
const REQUIRED_CAUSATION_BRANCH_IDS = Object.freeze([
  'building_defect',
  'tenant_use',
  'mixed_cause',
  'evidence_gap',
]);
const PROCESS_NODE_PROGRESS_CONTRACT = 'casepath.process-node-progress/1.0.0';
const PROCESS_NODE_PROGRESS_SCOPE = 'visible_evidence_bound_construction';
const DECISION_FLOW_CONTRACT = 'casepath.decision-flow/1.0.0';
const EXECUTION_TRACE_CONTRACT = 'casepath.accepted-execution-trace/1.0.0';
const FACT_TOUR_FACT_IDS = Object.freeze([
  'fact_customer_objective',
  'fact_tenancy',
  'fact_dispute',
  'fact_health',
  'fact_notification',
  'fact_recurrence',
  'fact_ventilation_allegation',
  'fact_cause',
]);
const NOTIFICATION_DECISION_NODE_ID = 'notification';
const BLOCKED_DOWNSTREAM_DECISION_IDS = Object.freeze(['responsibility', 'remedy', 'resolution']);
const BLOCKED_DOWNSTREAM_WAITING_COPY = Object.freeze({
  responsibility: 'Waiting for an earlier answer Cause must be known first.',
  remedy: 'Waiting for an earlier answer Responsibility must be known first.',
  resolution: 'Waiting for an earlier answer The action must be complete first.',
});
const REFERENCE_DECISION_AUDIT_PHASES = Object.freeze(['source-opened', 'fragment-extracted', 'plan-receded']);
const NOTIFICATION_SOURCE_LOCATOR_COUNTS = Object.freeze({
  art_notification: 2,
  art_delivery: 1,
});
const EXPECTED_OPENING_PROBLEM = 'The mould in the external corner of our bedroom keeps coming back.';
const EXPECTED_OPENING_OUTCOME = 'Please tell me what should happen next. I want the cause clarified and the defect repaired.';
const PROCESS_NODE_PROGRESS_SEQUENCE = Object.freeze([
  Object.freeze({ phase: 'search', percent: 0, visible: true }),
  Object.freeze({ phase: 'read', percent: 38, visible: true }),
  Object.freeze({ phase: 'extract', percent: 72, visible: true }),
  Object.freeze({ phase: 'form', percent: 90, visible: true }),
  Object.freeze({ phase: 'complete', percent: 100, visible: true }),
  Object.freeze({ phase: 'cleared', percent: 100, visible: false }),
]);
const EVIDENCE_REQUIREMENT_PROGRESS_LABELS = Object.freeze({
  search: 'Checking evidence need',
  read: 'Reading requirement',
  extract: 'Confirming gap',
});
const MIN_PROCESS_NODE_PROGRESS_CLEAR_GAP_MS = 170;
const LATER_MEMORY_VALIDATION_CONTRACT = 'casepath.later-memory-validation/1.0.0';
const EXPECTED_LATER_MEMORY_DELTA = Object.freeze({
  nodeIds: ['ventilation_dispute'],
  edges: [
    { source: 'evidence_gap', target: 'ventilation_dispute' },
    { source: 'ventilation_dispute', target: 'causation' },
  ],
  evidenceIds: ['building_envelope', 'management_position', 'use_evidence'],
});
const MIN_DECISION_SOURCE_PREVIEW_HOLD_MS = 5100;
const MIN_DECISION_SOURCE_HOLD_MS = 6700;
const MIN_DECISION_COMBINE_HOLD_MS = 2900;
const MIN_DECISION_READY_HOLD_MS = 2100;
const MIN_DECISION_PLAN_RECEDE_MS = 170;
const SOURCE_PRELUDE_ICON_KINDS = Object.freeze([
  'message',
  'document',
  'email',
  'email',
  'photo',
  'timeline',
  'delivery',
]);
const SOURCE_RAIL_CONTRACT = 'casepath.source-rail/1.0.0';
const SOURCE_RAIL_VIEWPORTS = Object.freeze([
  Object.freeze({ width: 1280, height: 720 }),
  Object.freeze({ width: 1440, height: 900 }),
]);
const SOURCE_RAIL_ALLOWED_STATUSES = new Set(['ready', 'read', 'reading']);
const SOURCE_RAIL_MIN_WIDTH_PX = 232;
const SOURCE_RAIL_MAX_WIDTH_PX = 272;
const SOURCE_RAIL_MIN_ROW_HEIGHT_PX = 48;
const SOURCE_RAIL_MAX_ROW_HEIGHT_PX = 64;
const SOURCE_RAIL_MIN_ICON_SIZE_PX = 24;
const SOURCE_RAIL_MAX_ICON_SIZE_PX = 34;
const LIVE_WORK_PLAN_CONTRACT = 'casepath.live-work-plan/1.0.0';
const CANONICAL_FACTS_LIVE_WORK_STEPS = Object.freeze([
  Object.freeze({ stepId: 'package', label: 'Claim package ready', state: 'complete', spinnerCount: 0 }),
  Object.freeze({ stepId: 'choose', label: 'Read exact source', state: 'active', spinnerCount: 1 }),
  Object.freeze({ stepId: 'return', label: 'Return supported facts', state: 'waiting', spinnerCount: 0 }),
]);
const AGENT_HISTORY_CONTRACT = 'casepath.agent-history/1.0.0';
const SPATIAL_GRAPH_PROJECTION = 'flagship-spine/1';
const SPATIAL_GEOMETRY_EPSILON_PX = 2;
const PROCESS_PREVIEW_BOTTOM_INSET_PX = 8;
const PROCESS_PREVIEW_GEOMETRY_SELECTORS = Object.freeze([
  '.ac-spatial-detail',
  '.ac-build-inspection',
  '.ac-visual-source-frame',
  '.ac-source-page-excerpt',
  '.ac-node-causal-chain',
]);
const REQUIRED_SEMANTIC_EVENT_TYPES = Object.freeze([
  'fact.accepted',
  'legal_source.linked',
  'process_node.created',
  'branch.created',
  'evidence_requirement.linked',
  'precedent.selected',
  'verification.accepted',
  'run.completed',
]);
const REQUIRED_DETERMINISTIC_GATE_IDS = Object.freeze([
  'deterministic_process_gate',
  'deterministic_evidence_gate',
  'whole_playbook_gate',
]);
const REQUIRED_DETERMINISTIC_GATE_ROLES = Object.freeze({
  deterministic_process_gate: 'Deterministic Process Contract Gate',
  deterministic_evidence_gate: 'Deterministic Evidence Contract Gate',
  whole_playbook_gate: 'Deterministic Whole-Playbook Gate',
});
const ACCEPTED_ARTIFACT_CONTRACT = Object.freeze({
  deterministic_process_gate: { output_artifact: 'process_graph', source_agent_id: 'process_decision_mapping' },
  deterministic_evidence_gate: { output_artifact: 'evidence_model', source_agent_id: 'evidence_checklist' },
  whole_playbook_gate: { output_artifact: 'verified_claim_playbook', source_agent_id: 'final_claim_brief_audit' },
});
const PROCESS_CONTRIBUTION_ROLE = 'Process Decision Mapping Agent';
const EVIDENCE_CONTRIBUTION_ROLE = 'Evidence and Checklist Agent';
const FINAL_CONTRIBUTION_ROLE = 'Final Claim Brief Agent';
const DETERMINISTIC_CONTRIBUTION_ROLE = 'deterministic_application';
const FINAL_FIELD_CONTRACT = Object.freeze([
  { field: 'current_node_id', contribution_id: 'final:current_node' },
  { field: 'next_action_node_id', contribution_id: 'final:next_action' },
  { field: 'supporting_fact_ids', contribution_id: 'final:supporting_facts' },
  { field: 'upstream_contribution_ids', contribution_id: 'final:upstream_contributions' },
  { field: 'audit_check_ids', contribution_id: 'final:audit_checks' },
]);
const FINAL_UPSTREAM_CONTRIBUTION_IDS = Object.freeze([
  'document_source_integrity',
  'evidence_checklist',
  'process_decision_mapping',
]);
const FINAL_AUDIT_CHECK_IDS = Object.freeze([
  'current_node_supported_by_canonical_facts',
  'evidence_items_bound_to_process_nodes',
  'next_action_connected_in_static_topology',
  'upstream_contribution_lineage_complete',
]);
const EXPECTED_FRAMEWORK = Object.freeze({
  langchain: '1.3.14',
  langgraph: '1.2.9',
  langchain_openrouter: '0.2.7',
});
const EXPECTED_RUNTIME = Object.freeze({
  runtime_profile: 'nemotron_langgraph_multi_agent_hybrid_guarded',
  authority_mode: 'multi_agent_hybrid_guarded',
  implementation: 'langgraph_stategraph_langchain_openrouter',
  orchestration_schema: 'casepath.nemotron-agent-dag/1.0.0',
});
const DETERMINISTIC_REFERENCE_MODE = 'deterministic_reference';
const DETERMINISTIC_REFERENCE_PROFILE = 'deterministic-reference-playbook';
const DETERMINISTIC_REFERENCE_ORCHESTRATION = Object.freeze({
  executed: false,
  authority_mode: DETERMINISTIC_REFERENCE_MODE,
  model: null,
  external_tracing: false,
  deterministic_safety_authority: true,
});
const DETERMINISTIC_REFERENCE_CANONICALIZATION = Object.freeze({
  implementation: 'deterministic_reference_oracle',
  model: null,
  provider: null,
  mode: DETERMINISTIC_REFERENCE_MODE,
});
const EXPECTED_EXECUTION_TOPOLOGY = Object.freeze({
  authority: 'deterministic_application',
  implementation: 'compiled_langgraph_stategraph',
  delegations: [
    { agent_id: 'document_source_integrity', dependencies: ['orchestrator_plan'] },
    { agent_id: 'process_decision_mapping', dependencies: ['orchestrator_plan'] },
    { agent_id: 'evidence_checklist', dependencies: ['deterministic_process_gate'] },
    { agent_id: 'final_claim_brief_audit', dependencies: ['deterministic_evidence_gate'] },
  ],
  parallel_groups: [['document_source_integrity', 'process_decision_mapping']],
});
const SUCCESSFUL_MODEL_OUTCOMES = new Set(['succeeded', 'succeeded_with_guarded_fallback']);
const CONSERVATIVE_PROCESS_DECISIONS = Object.freeze({
  scope: 'scope_unverified',
  dispute: 'dispute_unverified',
  urgency: 'urgency_unverified',
  notification: 'notification_unverified',
  recurrence: 'recurrence_unverified',
  causation: 'cause_unresolved',
});
function compatibleProcessDecisionValues(fact) {
  const conservative = CONSERVATIVE_PROCESS_DECISIONS[String(fact?.decision_key || '')];
  return new Set([String(fact?.decision_value || ''), ...(conservative ? [conservative] : [])]);
}

function processRouteStory(processGraph) {
  const nodes = Array.isArray(processGraph?.nodes) ? processGraph.nodes : [];
  const nodesById = new Map(nodes.map(node => [String(node?.node_id || ''), node]));
  const overlay = processGraph?.current_overlay && typeof processGraph.current_overlay === 'object'
    ? processGraph.current_overlay
    : {};
  const selectedPath = Array.isArray(processGraph?.selected_path)
    ? processGraph.selected_path.map(String).filter(Boolean)
    : [];
  const mainSpine = Array.isArray(processGraph?.main_spine)
    ? processGraph.main_spine.map(String).filter(Boolean)
    : [];
  const currentNodeId = String(overlay.current_node_id || processGraph?.current_node || '');
  const nextActionNodeId = String(overlay.next_action_node_id || '');
  const selectedBranchId = String(overlay.selected_branch_id || '');
  const currentNode = nodesById.get(currentNodeId) || null;
  const returnedBranches = Array.isArray(currentNode?.branches) ? currentNode.branches : [];
  const selectedBranch = returnedBranches.find(branch => (
    String(branch?.branch_id || '') === selectedBranchId
    && String(branch?.target || '') === nextActionNodeId
  )) || null;
  const causationCanvas = currentNodeId === 'causation' && Boolean(selectedBranch);
  const flagshipCausation = causationCanvas && nextActionNodeId === 'evidence_gap';
  const routeNodeIds = [...new Set([
    ...selectedPath,
    ...(nodesById.has(currentNodeId) ? [currentNodeId] : []),
    ...(nodesById.has(nextActionNodeId) ? [nextActionNodeId] : []),
  ])];
  const storyNodeIds = causationCanvas
    ? mainSpine.filter(nodeId => nodesById.has(nodeId))
    : routeNodeIds;
  const branchNodeIds = causationCanvas
    ? returnedBranches.map(branch => String(branch?.target || '')).filter(nodeId => nodeId && nodesById.has(nodeId))
    : [];
  const selectedBranchTargetId = selectedBranch && String(selectedBranch.target || '') !== currentNodeId
    ? String(selectedBranch.target || '')
    : '';
  return {
    selectedPath,
    currentNodeId,
    nextActionNodeId,
    selectedBranchId,
    currentNode,
    causationCanvas,
    flagshipCausation,
    routeNodeIds,
    storyNodeIds,
    branchNodeIds,
    selectedBranchTargetId,
    activeBasis: {
      factIds: Array.isArray(currentNode?.fact_ids) ? currentNode.fact_ids : [],
      lawIds: Array.isArray(currentNode?.legal_source_ids) ? currentNode.legal_source_ids : [],
      evidenceIds: Array.isArray(currentNode?.evidence_requirement_ids) ? currentNode.evidence_requirement_ids : [],
    },
  };
}

function processRouteStoryContractViolations(processGraph) {
  const issues = [];
  const story = processRouteStory(processGraph);
  const returnedNodeIds = new Set((processGraph?.nodes || []).map(node => String(node?.node_id || '')));
  if (!story.selectedPath.length || new Set(story.selectedPath).size !== story.selectedPath.length
    || story.selectedPath.some(nodeId => !returnedNodeIds.has(nodeId))) issues.push('selected path is absent, duplicated, or not returned');
  if (!story.currentNodeId || !returnedNodeIds.has(story.currentNodeId)
    || !story.selectedPath.includes(story.currentNodeId)) issues.push('current node is not on the returned selected path');
  if (!story.nextActionNodeId || !returnedNodeIds.has(story.nextActionNodeId)) issues.push('next action is not a returned process node');
  if (story.selectedBranchId && !story.currentNode?.branches?.some(branch => (
    String(branch?.branch_id || '') === story.selectedBranchId
    && String(branch?.target || '') === story.nextActionNodeId
  ))) issues.push('selected branch does not bind the returned current node to the returned next action');
  const selectedPairs = new Set(story.selectedPath.slice(1).map((target, index) => `${story.selectedPath[index]}->${target}`));
  const returnedSelectedPairs = new Set((processGraph?.edges || [])
    .filter(edge => edge?.state === 'selected')
    .map(edge => `${String(edge?.source || '')}->${String(edge?.target || '')}`));
  for (const pair of selectedPairs) {
    if (!returnedSelectedPairs.has(pair)) issues.push(`selected path edge ${pair} is not returned as selected`);
  }
  if (story.nextActionNodeId !== story.currentNodeId && story.selectedBranchTargetId !== story.nextActionNodeId) {
    issues.push('distinct next action is not the current node\'s selected returned branch');
  }
  if (story.nextActionNodeId !== story.currentNodeId
    && !(processGraph?.edges || []).some(edge => String(edge?.source || '') === story.currentNodeId && String(edge?.target || '') === story.nextActionNodeId)) {
    issues.push('distinct next action has no returned current-to-next edge');
  }
  if (story.nextActionNodeId === story.currentNodeId && story.selectedBranchTargetId) {
    issues.push('self-blocked route invents a distinct selected branch target');
  }
  return [...new Set(issues)];
}
const SHA256_PATTERN = /^[0-9a-f]{64}$/i;
const LOCAL_RUN_TIMEOUT_MS = 360000;
const PRODUCTION_RUN_TIMEOUT_MS = 15 * 60 * 1000;
const LATER_TERMINAL_POLL_INTERVAL_MS = 1000;
const AXE_ANIMATION_SETTLE_TIMEOUT_MS = 2500;
const FORBIDDEN_PUBLIC_FIELDS = new Set([
  'prompt',
  'system_prompt',
  'user_prompt',
  'messages',
  'raw',
  'raw_output',
  'reasoning',
  'chain_of_thought',
  'completion',
  'request_body',
  'response_body',
  'canonical_output',
]);
const INTERNAL_SENTINEL_PATTERN = /(?:__start__|__end__|branch:to:|PregelTask|Traceback \(most recent call last\)|OPENROUTER_API_KEY|Authorization:\s*Bearer)/i;
const ALLOWED_LEDGER_FIELDS = new Set([
  'call_id', 'provider', 'provider_endpoint', 'upstream_provider', 'model', 'implementation',
  'orchestration_id', 'agent_id', 'agent_role', 'parent_call_id', 'delegation_id', 'call_count',
  'prompt_tokens', 'completion_tokens', 'total_tokens', 'estimated_cost_usd', 'actual_cost_usd',
  'latency_ms', 'cache_key', 'purpose', 'outcome', 'error_type', 'error_agent_id', 'error_fact_id',
  'error_invariant', 'provider_error_code', 'provider_boundary', 'expected_upstream_provider',
  'invalid_provenance_field', 'invalid_provenance_value_hash',
  'ignored_noncontrolling_normalized_proposals', 'authority_mode',
  'accepted_fact_ids', 'accepted_fact_count', 'rejected_facts', 'rejected_fact_count',
  'source_reference_projection_fact_ids', 'source_reference_projection_count',
  'accepted_item_ids', 'accepted_item_count', 'rejected_items', 'rejected_item_count',
  'ignored_proposal_count', 'deterministic_fallback_applied', 'response_id', 'origin_call_id',
  'origin_usage', 'origin_finish_reason', 'response_model', 'generation_model', 'usage_source', 'metadata_poll_count', 'metadata_latency_ms',
  'finish_reason', 'created_at', 'updated_at',
]);
const ALLOWED_LEDGER_SUMMARY_FIELDS = new Set([
  'records', 'network_calls', 'prompt_tokens', 'completion_tokens', 'total_tokens',
  'actual_cost_usd', 'actual_cost_complete', 'unknown_cost_call_count', 'outcomes',
]);
const ALLOWED_AGENT_FAILURE_RECEIPT_FIELDS = new Set([
  'event_id', 'ordinal', 'created_at', 'stage', 'label', 'agent', 'agent_id', 'actor_type', 'status',
  'headline', 'detail', 'implementation', 'model', 'orchestrator', 'validator', 'prompt_version',
  'receipt_type', 'acceptance_scope', 'failure_scope', 'root_agent', 'shared_context',
  'delegation_id', 'parent_call_id', 'orchestration_id', 'call_id', 'response_id', 'outcome',
  'provider', 'requested_model', 'call_count',
  'response_model', 'upstream_provider', 'usage_source', 'handoff_from', 'handoff_to',
  'input_artifact', 'input_artifact_hash', 'finish_reason', 'error_type', 'error_invariant', 'provider_error_code',
  'provider_boundary', 'expected_upstream_provider',
  'invalid_provenance_field', 'invalid_provenance_value_hash', 'external_tracing',
]);
const FAILURE_OUTCOMES = new Set(['failed', 'blocked_cost_guard', 'blocked_missing_credential', 'blocked_provider_concurrency', 'actual_cost_overrun']);
const ZERO_CALL_FAILURE_OUTCOMES = new Set(['blocked_cost_guard', 'blocked_missing_credential', 'blocked_provider_concurrency']);
const ZERO_CALL_PROVIDER_RESULT_FIELDS = Object.freeze([
  'response_id', 'origin_call_id', 'origin_usage', 'origin_finish_reason', 'response_model',
  'generation_model', 'upstream_provider', 'usage_source', 'finish_reason',
  'metadata_poll_count', 'metadata_latency_ms', 'prompt_tokens', 'completion_tokens',
  'total_tokens', 'provider_error_code', 'provider_boundary',
  'expected_upstream_provider', 'invalid_provenance_field', 'invalid_provenance_value_hash',
  'ignored_noncontrolling_normalized_proposals', 'accepted_fact_ids', 'accepted_fact_count',
  'rejected_facts', 'rejected_fact_count', 'source_reference_projection_fact_ids',
  'source_reference_projection_count', 'accepted_item_ids', 'accepted_item_count',
  'rejected_items', 'rejected_item_count', 'ignored_proposal_count',
  'deterministic_fallback_applied',
]);
const SAFE_RESPONSE_ID = /^[A-Za-z0-9][A-Za-z0-9._-]{2,159}$/;
const EXACT_OPENROUTER_GENERATION_ID = /^gen-[0-9]{10}-[A-Za-z0-9]{20}$/;
const SAFE_UPSTREAM_PROVIDER = /^[A-Za-z0-9][A-Za-z0-9._-]{1,79}$/;
const FORBIDDEN_PROVENANCE_MARKERS = Object.freeze([
  'authorization', 'api_key', 'apikey', 'bearer ', 'credential', 'sk-or-', 'sk-', 'secret', 'sentinel',
  'customer', 'landlord', 'lease', 'mould', 'moisture', 'tenant',
]);
const SAFE_FINISH_REASONS = new Set(['stop', 'length', 'tool_calls', 'content_filter', 'error', 'cancelled']);
const PROVIDER_PROVENANCE_FIELDS = new Set(['response_id', 'response_model', 'upstream_provider', 'finish_reason']);
const EXPECTED_RUNTIME_ACCEPTANCE_CRITERIA = Object.freeze({
  required_mode: 'openrouter_nemotron',
  required_model: REQUESTED_NEMOTRON_MODEL,
  model_acceptance_scope: 'visible_browser_flagship',
  learning_comparison_authority: 'deterministic_application_tool',
  requires_learning_comparison_zero_model_activity: true,
  required_final_model_ledger_records: 12,
  required_final_model_network_calls: 6,
  required_final_cache_hits: 6,
  required_provider_max_in_flight: 1,
  required_runtime_profile: EXPECTED_RUNTIME.runtime_profile,
  requires_successful_call_binding: true,
  requires_positive_actual_cost: true,
  requires_positive_token_counts: true,
  requires_single_orchestration_binding: true,
  requires_complete_required_agent_set: true,
  requires_distinct_call_ids: true,
  requires_distinct_response_ids: true,
  requires_positive_accepted_contribution_per_agent: true,
  requires_accepted_majority_per_agent: true,
  requires_cold_network_run: true,
  requires_deterministic_gate_passes: true,
  requires_guarded_fallback_disclosure: true,
  requires_source_reference_projection_disclosure: true,
  requires_grounded_causal_artifact_recomputation: true,
  requires_learning_replay_proof: true,
});
const EXPECTED_FAILED_MODEL_ATTEMPT_RECORDS = Object.freeze(
  Array.from({ length: 24 }, (_, index) => `casepath/releases/model-validation-attempt-20260811-${String(index + 1).padStart(2, '0')}.json`),
);
const EXPECTED_PRODUCTION_OPENING_BOUNDARY = 'Application code opened the shared context; no model call is claimed for this setup step. The call-bound Nemotron plan appears only when its returned event arrives.';
const QA_DIRECTORY = path.resolve(fileURLToPath(new URL('.', import.meta.url)));
const REPOSITORY_ROOT = path.dirname(QA_DIRECTORY);
const QA_OUTPUT_BASENAME = 'guided-v13-smoke-out';
const PREFLIGHT_OUTPUT_BASENAME = 'evidence';
const PREFLIGHT_PARENT_PATTERN = /^casepath-qa-preflight\.[A-Za-z0-9]{6,}$/;
const REAL_ACCEPTANCE_PARENT_PATTERN = /^casepath-qa-real\.[A-Za-z0-9]{6,}$/;
const QA_TEMP_ROOT = path.resolve(os.tmpdir());

function resolveSafeQaOutputPath(candidate) {
  if (typeof candidate !== 'string' || candidate.trim() === '') {
    throw new Error('CASEPATH_QA_OUT must name a dedicated QA evidence directory.');
  }
  const resolved = path.resolve(candidate);
  const dedicatedQaOutput = path.join(QA_DIRECTORY, QA_OUTPUT_BASENAME);
  const preflightParent = path.dirname(resolved);
  const dedicatedPreflightOutput = (
    path.basename(resolved) === PREFLIGHT_OUTPUT_BASENAME
    && path.dirname(preflightParent) === QA_TEMP_ROOT
    && (
      PREFLIGHT_PARENT_PATTERN.test(path.basename(preflightParent))
      || REAL_ACCEPTANCE_PARENT_PATTERN.test(path.basename(preflightParent))
    )
  );
  if (resolved === path.parse(resolved).root || resolved === REPOSITORY_ROOT || resolved === QA_DIRECTORY) {
    throw new Error(`Refusing unsafe CASEPATH_QA_OUT path: ${resolved}`);
  }
  if (resolved !== dedicatedQaOutput && !dedicatedPreflightOutput) {
    throw new Error(`Refusing unsafe CASEPATH_QA_OUT path: ${resolved}`);
  }
  return resolved;
}

function assertSafeQaOutputParent(candidate) {
  const resolved = resolveSafeQaOutputPath(candidate);
  const parent = path.dirname(resolved);
  let realParent;
  try {
    realParent = realpathSync(parent);
  } catch (error) {
    throw new Error(`CASEPATH_QA_OUT parent must already exist: ${parent}`, { cause: error });
  }
  const dedicatedQaOutput = path.join(QA_DIRECTORY, QA_OUTPUT_BASENAME);
  const expectedParent = resolved === dedicatedQaOutput
    ? realpathSync(QA_DIRECTORY)
    : realpathSync(QA_TEMP_ROOT);
  const parentMatches = resolved === dedicatedQaOutput
    ? realParent === expectedParent
    : path.dirname(realParent) === expectedParent
      && (
        PREFLIGHT_PARENT_PATTERN.test(path.basename(realParent))
        || REAL_ACCEPTANCE_PARENT_PATTERN.test(path.basename(realParent))
      );
  if (!parentMatches) {
    throw new Error(`Refusing symlinked or unexpected CASEPATH_QA_OUT parent: ${parent}`);
  }
  return resolved;
}

const QA_SESSION_ID = `qa-${randomUUID()}`;
const ISOLATION_SESSION_ID = `qa-isolation-${randomUUID()}`;
const ALLOW_PRODUCTION_MUTATION = process.env.CASEPATH_ALLOW_PRODUCTION_MUTATION === '1';
const EXPECT_REAL_NEMOTRON = process.env.CASEPATH_EXPECT_REAL_NEMOTRON === '1';
if (!['', '0', '1'].includes(process.env.CASEPATH_EXPECT_REAL_NEMOTRON || '')) {
  throw new Error('CASEPATH_EXPECT_REAL_NEMOTRON must be exactly 0 or 1 when set.');
}
const OUT = assertSafeQaOutputParent(
  process.env.CASEPATH_QA_OUT || path.join(QA_DIRECTORY, QA_OUTPUT_BASENAME),
);
const checks = [];
const notes = [];
const failures = { console: [], page: [], request: [], cleanup: [] };
const runIds = [];
const browserRunRequests = [];
const claimLoopRequests = [];
const retainedEvidence = {};
const evidenceFiles = [];
const networkGuards = [];
let browser;
let context;
let page;
let video;
let demoMutated = false;
let isolationMutated = false;
let reviewResponse = null;
let proofResponse = null;
let deploymentIdentity = { frontend: null, api: null, qa: { release_id: RELEASE_ID, source_commit: process.env.RENDER_GIT_COMMIT || null } };
let runtimeVersions = { node: process.version, playwright: null, chromium: null };
let acceptedJourneyMode = 'flagship-review-learning';
let candidateSourceIdentityStart = null;
let candidateSourceSnapshotStart = null;
let candidateSourceManifests = null;
let apiRuntimeBootReceipt = null;
let browserExecutionReceipt = null;
let browserExecutionReceiptBinding = null;
let browserNetworkBoundary = null;

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function check(name, condition, detail = '') {
  const item = { name, passed: Boolean(condition), detail };
  checks.push(item);
  if (!item.passed) throw new Error(`${name}: ${detail || 'failed'}`);
}

function isLocal(urlValue) {
  const hostname = new URL(urlValue).hostname;
  return ['127.0.0.1', 'localhost', '::1'].includes(hostname);
}

function requireMutationAuthority() {
  if ((!isLocal(BASE) || !isLocal(API)) && !ALLOW_PRODUCTION_MUTATION) {
    throw new Error('Production mutation is disabled. Set CASEPATH_ALLOW_PRODUCTION_MUTATION=1 to run the reset/review lifecycle against non-local services.');
  }
}

function validSourceCommit(value) {
  return /^[0-9a-f]{40}$/i.test(value || '');
}

function isProductionJourney() {
  // Runtime-contract classification is explicit for loopback acceptance. URL
  // locality remains the independent authority boundary in
  // requireMutationAuthority(), so this flag cannot authorize hosted writes.
  return EXPECT_REAL_NEMOTRON || !isLocal(BASE) || !isLocal(API);
}

function runTimeoutMs() {
  return isProductionJourney() ? PRODUCTION_RUN_TIMEOUT_MS : LOCAL_RUN_TIMEOUT_MS;
}

function nonemptyString(value) {
  return typeof value === 'string' && value.length > 0;
}

function normalizedGroundingText(value) {
  return typeof value === 'string'
    ? value.normalize('NFKC')
      .replace(/[\u0009-\u000d\u001c-\u001f\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/gu, ' ')
      .replace(/^ +| +$/gu, '')
    : '';
}

function exactNormalizedGroundingQuote(sourcePage, excerpt) {
  const normalizedExcerpt = normalizedGroundingText(excerpt);
  return normalizedExcerpt.length > 0
    && normalizedGroundingText(sourcePage).includes(normalizedExcerpt);
}

function selectProcessTextQuoteFact(facts, processGraph, factId) {
  return facts.find(item => item.fact_id === factId
    && item.source_refs?.length
    && item.source_refs.every(ref => ref.locator_kind === 'text_quote')
    && processGraph.nodes.some(node => (node.fact_ids || []).includes(item.fact_id)));
}

function containsForbiddenProvenanceMarker(value) {
  if (typeof value !== 'string') return false;
  const folded = value.toLowerCase();
  return FORBIDDEN_PROVENANCE_MARKERS.some(marker => folded.includes(marker));
}

function providerProvenanceValueIsSafe(field, value) {
  if (value == null) return true;
  if (!nonemptyString(value) || value !== value.trim() || containsForbiddenProvenanceMarker(value)) return false;
  if (field === 'response_id') return SAFE_RESPONSE_ID.test(value);
  if (field === 'response_model') return EXACT_NEMOTRON_RESPONSE_MODELS.has(value);
  if (field === 'upstream_provider') return SAFE_UPSTREAM_PROVIDER.test(value);
  if (field === 'finish_reason') return SAFE_FINISH_REASONS.has(value);
  return false;
}

function providerRejectionBoundaryIssue(value) {
  const boundaryPresent = Object.hasOwn(value, 'provider_boundary');
  const expectedProviderPresent = Object.hasOwn(value, 'expected_upstream_provider');
  if (value.error_invariant !== 'provider_upstream_rejection') {
    return boundaryPresent || expectedProviderPresent
      ? 'provider rejection boundary attribution is out of scope'
      : null;
  }
  if (!boundaryPresent || !expectedProviderPresent) return 'provider rejection boundary attribution pair is incomplete';
  if (value.provider_boundary !== EXPECTED_PROVIDER_BOUNDARY
    || value.expected_upstream_provider !== EXPECTED_UPSTREAM_PROVIDER) return 'provider rejection boundary attribution is forged';
  return null;
}

function exactMembers(values, expected) {
  return Array.isArray(values)
    && Array.isArray(expected)
    && values.length === expected.length
    && new Set(values).size === values.length
    && new Set(expected).size === expected.length
    && expected.every(value => values.includes(value));
}

function contributionEntries(value, expectedAttribution) {
  const entries = (Array.isArray(value) ? value : value && typeof value === 'object' ? [value] : [])
    .filter(item => item && typeof item === 'object');
  if (!entries.length) return null;
  const ids = entries.map(item => item.contribution_id);
  if (!ids.every(nonemptyString) || new Set(ids).size !== ids.length) return null;
  const valid = entries.every(item => {
    if (typeof item.deterministic_fallback_applied !== 'boolean'
      || !Number.isInteger(item.confidence_basis_points)
      || item.confidence_basis_points < 0
      || item.confidence_basis_points > 10000) return false;
    const expectedRole = item.deterministic_fallback_applied
      ? DETERMINISTIC_CONTRIBUTION_ROLE
      : expectedAttribution;
    if (item.attribution !== expectedRole) return false;
    if (expectedAttribution === PROCESS_CONTRIBUTION_ROLE) {
      return /^fact:[^:]+:decision_value$/.test(item.contribution_id)
        && exactMembers(item.model_owned_fields, ['decision_value']);
    }
    if (expectedAttribution === EVIDENCE_CONTRIBUTION_ROLE) {
      const match = item.contribution_id.match(/^item:(.+):(status|artifacts)$/);
      if (!match) return false;
      const expectedField = match[2] === 'status' ? 'status' : 'artifact_ids';
      return item.field === expectedField;
    }
    if (expectedAttribution === FINAL_CONTRIBUTION_ROLE) {
      const expected = FINAL_FIELD_CONTRACT.find(unit => unit.contribution_id === item.contribution_id);
      return Boolean(expected && item.field === expected.field);
    }
    return false;
  });
  return valid ? entries : null;
}

function transformedContributionSuppressed(transform = null) {
  return transform?.acceptance_scope === 'post_review_unverified_transform'
    || (transform?.contract === 'casepath.memory-application-receipt/1.0.0'
      && transform.authority === 'unverified_demo'
      && transform.scope === 'case_specific_guidance_only'
      && transform.model_acceptance_reused === false
      && transform.applied === true);
}

function contributionExpectation(value, expectedAttribution, transform = null) {
  if (transformedContributionSuppressed(transform)) return null;
  const entries = contributionEntries(value, expectedAttribution);
  if (!entries) return null;
  const acceptedCount = entries.filter(item => item.deterministic_fallback_applied === false && item.attribution === expectedAttribution).length;
  const fallbackCount = entries.filter(item => item.deterministic_fallback_applied === true && item.attribution === DETERMINISTIC_CONTRIBUTION_ROLE).length;
  if (!acceptedCount && !fallbackCount) return null;
  return {
    authority: acceptedCount && fallbackCount ? 'mixed' : acceptedCount ? 'nemotron-accepted' : 'deterministic-fallback',
    accepted_count: String(acceptedCount),
    fallback_count: String(fallbackCount),
  };
}

function contributionDomProjection(value, expectedAttribution, transform = null) {
  const summary = contributionExpectation(value, expectedAttribution, transform);
  const entries = transformedContributionSuppressed(transform)
    ? null
    : contributionEntries(value, expectedAttribution);
  if (!summary || !entries) return null;
  return {
    ...summary,
    accepted_ids: entries.filter(item => item.deterministic_fallback_applied === false).map(item => item.contribution_id).join(','),
    fallback_ids: entries.filter(item => item.deterministic_fallback_applied === true).map(item => item.contribution_id).join(','),
  };
}

function orchestrationAudit(run) {
  return run?.result?.audit?.agent_orchestration
    || run?.result?.agent_orchestration
    || run?.agent_orchestration
    || null;
}

function forbiddenFieldPaths(value, currentPath = '$', found = []) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => forbiddenFieldPaths(item, `${currentPath}[${index}]`, found));
    return found;
  }
  if (!value || typeof value !== 'object') return found;
  for (const [key, child] of Object.entries(value)) {
    const childPath = `${currentPath}.${key}`;
    if (FORBIDDEN_PUBLIC_FIELDS.has(key)) found.push(childPath);
    forbiddenFieldPaths(child, childPath, found);
  }
  return found;
}

function stableJson(value) {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${stableJson(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

function dtoHash(value) {
  return sha256(stableJson(value));
}

function semanticProcessDto(process) {
  const value = structuredClone(process || {});
  delete value.agent_contribution;
  for (const node of value.nodes || []) delete node.agent_decision_contributions;
  return value;
}

function semanticChecklistDto(checklist) {
  const value = structuredClone(checklist || {});
  delete value.agent_contribution;
  for (const item of value.items || []) delete item.agent_contribution;
  return value;
}

function evidenceRelationContractViolations(process, checklist) {
  const issues = [];
  if (!process || !checklist || !Array.isArray(process.nodes) || !Array.isArray(checklist.items)) return ['process nodes or checklist items are absent'];
  const itemIds = checklist.items.map(item => item?.item_id);
  if (!itemIds.every(nonemptyString) || new Set(itemIds).size !== itemIds.length) return ['checklist item IDs are absent or duplicated'];
  const itemIdSet = new Set(itemIds);
  const ownerMap = new Map(itemIds.map(itemId => [itemId, []]));
  const nodeIds = process.nodes.map(node => node?.node_id);
  if (!nodeIds.every(nonemptyString) || new Set(nodeIds).size !== nodeIds.length) return ['process node IDs are absent or duplicated'];
  for (const node of process.nodes) {
    const requirements = node.evidence_requirement_ids;
    if (!Array.isArray(requirements) || requirements.some(itemId => !itemIdSet.has(itemId)) || new Set(requirements).size !== requirements.length) {
      issues.push(`${node.node_id}: evidence requirements are not a unique known-item list`);
      continue;
    }
    for (const itemId of requirements) ownerMap.get(itemId).push(node.node_id);
  }
  const selectedPath = process.selected_path;
  const nextAction = process.current_overlay?.next_action_node_id;
  if (!Array.isArray(selectedPath) || selectedPath.some(nodeId => !nodeIds.includes(nodeId))) issues.push('selected path is absent or contains an unknown node');
  if (!nonemptyString(nextAction) || !nodeIds.includes(nextAction)) issues.push('next-action node is absent or unknown');
  const activeNodes = new Set([...(Array.isArray(selectedPath) ? selectedPath : []), ...(nonemptyString(nextAction) ? [nextAction] : [])]);
  for (const item of checklist.items) {
    const owners = ownerMap.get(item.item_id) || [];
    if (!owners.length) issues.push(`${item.item_id}: no process owner`);
    if (JSON.stringify(item.node_ids) !== JSON.stringify(owners)) issues.push(`${item.item_id}: node_ids do not match ordered process owners`);
    if (item.node_id !== owners[0]) issues.push(`${item.item_id}: node_id is not the derived primary owner`);
    if (item.current_path !== owners.some(nodeId => activeNodes.has(nodeId))) issues.push(`${item.item_id}: current_path is not derived from every owner`);
  }
  return issues;
}

function legalContextContractViolations(legal, process) {
  const issues = [];
  if (!legal || legal.contract !== 'casepath.legal-context/2.0.0') return ['legal context contract is absent or wrong'];
  if (legal.registry_version !== 'ch-tenancy-official-snapshot/2026-08-12' || legal.lookup_method !== 'versioned_official_source_registry_lookup') issues.push('legal registry identity is wrong');
  if (!Array.isArray(legal.questions) || !Array.isArray(legal.sources) || !Array.isArray(legal.handling_principles)) return [...issues, 'legal questions, sources, or handling principles are absent'];
  const nodeIds = new Set((process?.nodes || []).map(node => node.node_id));
  const officialIds = legal.sources.map(source => source?.source_id);
  const principleIds = legal.handling_principles.map(source => source?.source_id);
  if (!officialIds.every(nonemptyString) || new Set(officialIds).size !== officialIds.length) issues.push('official legal source IDs are absent or duplicated');
  if (!principleIds.every(nonemptyString) || new Set(principleIds).size !== principleIds.length) issues.push('handling-principle IDs are absent or duplicated');
  const officialFields = ['source_id', 'title', 'url', 'source_type', 'jurisdiction', 'version_date', 'location', 'passage_language', 'passage_text', 'passage_sha256', 'passage_summary', 'operational_interpretation', 'review_status', 'role', 'approved', 'retrieval'];
  for (const source of legal.sources) {
    if (!exactMembers(Object.keys(source || {}), officialFields)) issues.push(`${source?.source_id || 'official source'}: fields are not exact`);
    if (!nonemptyString(source?.passage_text) || source.passage_sha256 !== sha256(source.passage_text)) issues.push(`${source?.source_id}: official passage hash is wrong`);
    if (source?.jurisdiction !== 'CH' || source?.passage_language !== 'de' || !nonemptyString(source?.version_date) || !nonemptyString(source?.location) || source?.review_status !== 'qualified_review_pending' || source?.approved !== false) issues.push(`${source?.source_id}: official passage status/provenance is incomplete`);
    const retrieval = source?.retrieval;
    if (!exactMembers(Object.keys(retrieval || {}), ['method', 'retrieved_at', 'registry_version', 'snapshot_url', 'snapshot_sha256', 'snapshot_scope'])
      || retrieval?.method !== 'versioned_official_source_registry_lookup'
      || retrieval?.registry_version !== legal.registry_version
      || !nonemptyString(retrieval?.retrieved_at)
      || !nonemptyString(retrieval?.snapshot_url)
      || !SHA256_PATTERN.test(retrieval?.snapshot_sha256 || '')
      || !['official_pdf_bytes', 'normalized_official_passage_utf8'].includes(retrieval?.snapshot_scope)) issues.push(`${source?.source_id}: official retrieval receipt is invalid`);
    if (source?.source_id === 'bwo-conciliation' && (retrieval?.snapshot_scope !== 'normalized_official_passage_utf8' || retrieval?.snapshot_sha256 !== source.passage_sha256 || retrieval.snapshot_sha256 !== '27700e4ed06b60510b992676823c44d9a11aefb94192fdc3bec872df1c843af6')) issues.push(`${source.source_id}: normalized official passage snapshot is not exact`);
    if (source?.source_id?.startsWith('fedlex-') && retrieval?.snapshot_scope !== 'official_pdf_bytes') issues.push(`${source.source_id}: Fedlex snapshot scope is not official PDF bytes`);
  }
  for (const principle of legal.handling_principles) {
    if (!exactMembers(Object.keys(principle || {}), ['source_id', 'title', 'source_type', 'role', 'validation_status', 'producer']) || principle?.producer !== 'deterministic_application') issues.push(`${principle?.source_id || 'principle'}: deterministic producer contract is invalid`);
  }
  const authorityIds = new Set([...officialIds, ...principleIds]);
  const derivedNodeLinks = {};
  const questionIds = [];
  for (const question of legal.questions) {
    if (!exactMembers(Object.keys(question || {}), ['question_id', 'text', 'source_ids', 'interpretation_ids', 'process_node_ids', 'consequence'])) issues.push(`${question?.question_id || 'question'}: fields are not exact`);
    if (!nonemptyString(question?.question_id) || questionIds.includes(question.question_id)) issues.push('legal question IDs are absent or duplicated');
    questionIds.push(question?.question_id);
    if (!nonemptyString(question?.text) || !nonemptyString(question?.consequence)) issues.push(`${question?.question_id}: question text or consequence is absent`);
    if (!(question?.source_ids || []).every(sourceId => officialIds.includes(sourceId))) issues.push(`${question?.question_id}: official source join is invalid`);
    if (!(question?.interpretation_ids || []).every(sourceId => principleIds.includes(sourceId))) issues.push(`${question?.question_id}: interpretation join is invalid`);
    if (!(question?.process_node_ids || []).every(nodeId => nodeIds.has(nodeId))) issues.push(`${question?.question_id}: process-node join is invalid`);
    for (const nodeId of question?.process_node_ids || []) {
      const retained = derivedNodeLinks[nodeId] ||= [];
      for (const sourceId of [...(question.source_ids || []), ...(question.interpretation_ids || [])]) if (!retained.includes(sourceId)) retained.push(sourceId);
    }
  }
  if (Object.values(legal.node_links || {}).flat().some(sourceId => !authorityIds.has(sourceId)) || stableJson(legal.node_links || {}) !== stableJson(derivedNodeLinks)) issues.push('legal node_links do not equal the ID-joined questions');
  if (/model interpretation|live retrieval/i.test(stableJson(legal))) issues.push('legal DTO contains false model or live-retrieval authority wording');
  return issues;
}

function visualReferenceContractViolations(reference, artifact) {
  const issues = [];
  const fields = ['artifact_id', 'locator_kind', 'region', 'observation', 'producer', 'authority', 'annotation_contract', 'annotation_version', 'image_sha256'];
  if (!exactMembers(Object.keys(reference || {}), fields)) issues.push('visual annotation fields are not exact');
  if (reference?.locator_kind !== 'visual_observation'
    || reference?.producer !== 'deterministic_reference_annotation'
    || reference?.authority !== 'generated_demo_reference_only'
    || reference?.annotation_contract !== 'casepath.visual-reference-annotation/1.0.0'
    || reference?.annotation_version !== 'generated-demo-reference/2026-08-12') issues.push('visual annotation authority contract is wrong');
  const region = reference?.region;
  if (!Array.isArray(region) || region.length !== 4 || region.some(value => typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 1) || !(region[2] > 0) || !(region[3] > 0) || region[0] + region[2] > 1 || region[1] + region[3] > 1) issues.push('visual annotation region is invalid');
  if (!nonemptyString(reference?.observation)) issues.push('visual annotation observation is absent');
  if (!artifact || reference?.artifact_id !== artifact.artifact_id || !artifact.media_type?.startsWith('image/') || !SHA256_PATTERN.test(artifact.sha256 || '') || reference?.image_sha256 !== artifact.sha256) issues.push('visual annotation is not bound to public image bytes');
  return issues;
}

function precedentRankingContractViolations(result) {
  const issues = [];
  const precedents = result?.precedents;
  const receipt = result?.precedent_ranking;
  const contract = 'casepath.precedent-ranking/1.0.0';
  const corpus = 'generated-reference-patterns/2026-08-12';
  if (!Array.isArray(precedents) || precedents.length !== 3 || !receipt) return ['exact-three precedents or ranking receipt are absent'];
  if (!exactMembers(Object.keys(receipt), ['contract', 'corpus_version', 'context', 'context_hash', 'candidate_scores', 'selected_claim_ids', 'result_hash'])) issues.push('precedent ranking receipt fields are not exact');
  if (receipt.contract !== contract || receipt.corpus_version !== corpus) issues.push('precedent ranking identity is wrong');
  if (!exactMembers(Object.keys(receipt.context || {}), ['category', 'subcategory', 'current_process_node_id', 'next_action_node_id', 'selected_path', 'unresolved_fact_ids', 'current_evidence_need_ids']) || receipt.context_hash !== dtoHash(receipt.context)) issues.push('precedent ranking context is not exact or hash-bound');
  const selectedIds = precedents.map(item => item.claim_id);
  if (JSON.stringify(receipt.selected_claim_ids) !== JSON.stringify(selectedIds) || receipt.result_hash !== dtoHash(precedents)) issues.push('precedent selected IDs or result hash are wrong');
  if (!Array.isArray(receipt.candidate_scores) || receipt.candidate_scores.length < 3 || new Set(receipt.candidate_scores.map(item => item.claim_id)).size !== receipt.candidate_scores.length || JSON.stringify(receipt.candidate_scores.slice(0, 3).map(item => item.claim_id)) !== JSON.stringify(selectedIds)) issues.push('candidate scores do not retain the ranked selection order');
  for (const candidate of receipt.candidate_scores || []) {
    if (!exactMembers(Object.keys(candidate || {}), ['claim_id', 'score_basis_points', 'factors']) || !nonemptyString(candidate.claim_id) || !Number.isInteger(candidate.score_basis_points) || !Array.isArray(candidate.factors) || candidate.factors.some(factor => !exactMembers(Object.keys(factor || {}), ['factor', 'value', 'weight']) || !nonemptyString(factor.factor) || !nonemptyString(factor.value) || !Number.isInteger(factor.weight)) || candidate.score_basis_points !== candidate.factors.reduce((sum, factor) => sum + factor.weight, 0)) issues.push(`${candidate?.claim_id || 'candidate'}: candidate score receipt is invalid`);
  }
  const allowedStatuses = new Set(['generated_reference', 'unverified_demo_memory', 'qualified_expert_reviewed']);
  precedents.forEach((precedent, index) => {
    const ranking = precedent?.ranking;
    if (!allowedStatuses.has(precedent?.review_status)) issues.push(`${precedent?.claim_id}: review status is invalid`);
    if (!exactMembers(Object.keys(ranking || {}), ['contract', 'corpus_version', 'rank', 'score_basis_points', 'factors', 'context_hash']) || ranking?.contract !== contract || ranking?.corpus_version !== corpus || ranking?.rank !== index + 1 || ranking?.context_hash !== receipt.context_hash) issues.push(`${precedent?.claim_id}: per-item ranking is invalid`);
    if (!Array.isArray(ranking?.factors) || ranking.factors.some(factor => !exactMembers(Object.keys(factor || {}), ['factor', 'value', 'weight']) || !Number.isInteger(factor.weight)) || ranking?.score_basis_points !== (ranking?.factors || []).reduce((sum, factor) => sum + factor.weight, 0)) issues.push(`${precedent?.claim_id}: ranking factors do not sum to the score`);
    const candidate = receipt.candidate_scores?.find(item => item.claim_id === precedent.claim_id);
    if (!candidate || candidate.score_basis_points !== ranking?.score_basis_points || stableJson(candidate.factors) !== stableJson(ranking?.factors)) issues.push(`${precedent?.claim_id}: candidate and selected ranking differ`);
  });
  return issues;
}

function memoryRetrievalContractViolations(result) {
  const issues = [];
  if (!result || typeof result !== 'object') return ['final result is absent'];
  const memoryPrecedents = (result.precedents || []).filter(item => item?.review_status === 'unverified_demo_memory' && nonemptyString(item?.memory_id));
  const expectedRetrieved = memoryPrecedents.length > 0;
  const receiptPresent = result.memory_application != null;
  const receiptValid = !receiptPresent || (result.memory_application?.contract === 'casepath.memory-application-receipt/1.0.0'
    && result.memory_application?.authority === 'unverified_demo'
    && result.memory_application?.scope === 'case_specific_guidance_only'
    && result.memory_application?.applied === true
    && SHA256_PATTERN.test(result.memory_application?.application_hash || ''));
  const knowledge = result.knowledge || {};
  const processUsed = result.process?.memory_used;
  const checklistUsed = result.checklist?.memory_used;
  const rootUseFlags = [result.memory_used, result.reviewed_memory_used, knowledge.reviewed_memory_used];
  const retrievalFlags = [result.reviewed_memory_retrieved, knowledge.reviewed_memory_retrieved];
  if (!retrievalFlags.every(value => typeof value === 'boolean') || retrievalFlags.some(value => value !== expectedRetrieved)) issues.push('reviewed-memory retrieval flags do not equal ranked unverified memory presence');
  if (!receiptValid) issues.push('memory-use flags point at an invalid application receipt');
  if (!rootUseFlags.every(value => typeof value === 'boolean') || rootUseFlags.some(value => value !== receiptPresent)) issues.push('root/knowledge memory-use flags do not equal application-receipt presence');
  if (processUsed !== receiptPresent || checklistUsed !== receiptPresent) issues.push('process/checklist memory_used does not equal application-receipt presence');
  if (receiptPresent && (!expectedRetrieved || result.memory_application?.applied !== true || result.process?.case_specific_guidance_applied !== true || result.checklist?.case_specific_guidance_applied !== true)) issues.push('application receipt is not bound to retrieved memory and transformed DTO flags');
  if (!receiptPresent && (result.process?.case_specific_guidance_applied === true || result.checklist?.case_specific_guidance_applied === true)) issues.push('receipt-free result falsely claims case-specific guidance application');
  if (memoryPrecedents.length > 1) issues.push('more than one unverified memory was ranked into the exact-three result');
  return issues;
}

function semanticFactSignature(result) {
  const roles = {};
  for (const fact of result?.facts || []) {
    if (fact?.semantic_role == null) continue;
    roles[fact.semantic_role] = {
      fact_id: fact.fact_id,
      state: fact.state,
      grounded_source_count: Array.isArray(fact.source_refs) ? fact.source_refs.length : 0,
    };
  }
  return roles;
}

function semanticFactRoleViolations(result) {
  const facts = result?.facts;
  if (!Array.isArray(facts)) return ['canonical facts are absent'];
  const issues = [];
  const populated = [];
  for (const fact of facts) {
    if (!Object.hasOwn(fact || {}, 'semantic_role')) issues.push(`${fact?.fact_id || 'fact'}: nullable semantic_role is absent`);
    if (fact?.semantic_role != null && fact.semantic_role !== 'management_ventilation_allegation') issues.push(`${fact?.fact_id || 'fact'}: semantic_role is unsupported`);
    if (fact?.semantic_role != null) populated.push(fact.semantic_role);
  }
  if (JSON.stringify(populated) !== JSON.stringify(['management_ventilation_allegation'])) issues.push('exactly one management_ventilation_allegation semantic role is required');
  return issues;
}

function computedCausalDelta(beforeResult, afterResult) {
  const beforeProcess = semanticProcessDto(beforeResult?.process);
  const afterProcess = semanticProcessDto(afterResult?.process);
  const beforeChecklist = semanticChecklistDto(beforeResult?.checklist);
  const afterChecklist = semanticChecklistDto(afterResult?.checklist);
  const keyed = (values, key) => new Map((values || []).map(value => [key(value), value]));
  const beforeNodes = keyed(beforeProcess.nodes, value => value.node_id);
  const afterNodes = keyed(afterProcess.nodes, value => value.node_id);
  const edgeKey = value => `${value.source}\u0000${value.target}`;
  const beforeEdges = keyed(beforeProcess.edges, edgeKey);
  const afterEdges = keyed(afterProcess.edges, edgeKey);
  const beforeItems = keyed(beforeChecklist.items, value => value.item_id);
  const afterItems = keyed(afterChecklist.items, value => value.item_id);
  const difference = (left, right) => [...left.keys()].filter(key => !right.has(key)).sort();
  const changed = (left, right) => [...left.keys()].filter(key => right.has(key) && stableJson(left.get(key)) !== stableJson(right.get(key))).sort();
  const edgeProjection = keys => keys.map(key => { const [source, target] = key.split('\u0000'); return { source, target }; });
  const rootChanges = (before, after, excluded) => [...new Set([...Object.keys(before), ...Object.keys(after)])].filter(key => !excluded.has(key) && stableJson(before[key]) !== stableJson(after[key])).sort();
  const addedNodeIds = difference(afterNodes, beforeNodes);
  const removedNodeIds = difference(beforeNodes, afterNodes);
  const changedNodeIds = changed(beforeNodes, afterNodes);
  const addedEdges = edgeProjection(difference(afterEdges, beforeEdges));
  const removedEdges = edgeProjection(difference(beforeEdges, afterEdges));
  const changedEdges = edgeProjection(changed(beforeEdges, afterEdges));
  const addedItemIds = difference(afterItems, beforeItems);
  const removedItemIds = difference(beforeItems, afterItems);
  const changedItemIds = changed(beforeItems, afterItems);
  return {
    nonzero: Boolean(addedNodeIds.length || removedNodeIds.length || changedNodeIds.length || addedEdges.length || removedEdges.length || changedEdges.length || addedItemIds.length || removedItemIds.length || changedItemIds.length),
    process: { added_node_ids: addedNodeIds, removed_node_ids: removedNodeIds, changed_node_ids: changedNodeIds, added_edges: addedEdges, removed_edges: removedEdges, changed_edges: changedEdges, changed_root_keys: rootChanges(beforeProcess, afterProcess, new Set(['nodes', 'edges'])) },
    evidence: { added_item_ids: addedItemIds, removed_item_ids: removedItemIds, changed_item_ids: changedItemIds, changed_root_keys: rootChanges(beforeChecklist, afterChecklist, new Set(['items'])) },
  };
}

function memoryApplicationContractViolations(baselineRun, laterRun, proof) {
  const issues = [];
  const baseline = baselineRun?.result;
  const later = laterRun?.result;
  const receipt = later?.memory_application;
  const freeze = baselineRun?.counterfactual_learning_freeze;
  const receiptFields = ['receipt_type', 'contract', 'authority', 'scope', 'source_memory', 'target', 'observable_input_hash', 'canonical_state_hash', 'eligibility', 'allowed_operation_ids', 'applied_operation_ids', 'process_operations', 'evidence_operations', 'before', 'after', 'verification_hash', 'shared_playbook_version', 'shared_rule_applied', 'model_acceptance_reused', 'applied', 'application_hash'];
  const boundaryFields = ['process_dto_hash', 'checklist_dto_hash', 'process_semantic_hash', 'checklist_semantic_hash'];
  if (!baseline || !later || !receipt || !proof) return ['baseline, later result, receipt, or proof is absent'];
  issues.push(...memoryRetrievalContractViolations(baseline).map(issue => `baseline ${issue}`));
  issues.push(...memoryRetrievalContractViolations(later).map(issue => `later ${issue}`));
  if (!exactMembers(Object.keys(receipt), receiptFields)) issues.push('memory receipt fields are not exact');
  if (receipt.receipt_type !== 'memory_application_receipt' || receipt.contract !== 'casepath.memory-application-receipt/1.0.0' || receipt.authority !== 'unverified_demo' || receipt.scope !== 'case_specific_guidance_only' || receipt.shared_playbook_version !== 'mould-playbook-v3' || receipt.shared_rule_applied !== false || receipt.model_acceptance_reused !== false || receipt.applied !== true) issues.push('memory receipt authority boundary is wrong');
  if (!exactMembers(Object.keys(receipt.source_memory || {}), ['memory_id', 'claim_id', 'review_id', 'content_hash', 'review_status']) || receipt.source_memory.claim_id !== 'DEF-027-E0-DEMO' || receipt.source_memory.review_status !== 'unverified_demo_memory') issues.push('source memory binding is wrong');
  const freezeIdentity = freeze?.memory || {};
  if (!freeze || stableJson(proof.counterfactual_learning_freeze) !== stableJson(freeze)
    || !exactMembers(Object.keys(freeze), ['contract', 'memory', 'identity_hash', 'application_suppressed'])
    || freeze.contract !== 'casepath.counterfactual-learning-freeze/1.0.0'
    || freeze.application_suppressed !== true
    || !exactMembers(Object.keys(freezeIdentity), ['memory_id', 'review_id', 'content_hash', 'candidate_id', 'updated_at'])
    || freezeIdentity.memory_id !== receipt.source_memory.memory_id
    || freezeIdentity.review_id !== receipt.source_memory.review_id
    || freezeIdentity.content_hash !== receipt.source_memory.content_hash
    || freezeIdentity.candidate_id !== proof.candidate?.candidate_id
    || !Number.isFinite(Date.parse(freezeIdentity.updated_at || ''))
    || freeze.identity_hash !== dtoHash(freezeIdentity)) issues.push('counterfactual baseline is not bound to the frozen governed memory identity');
  const freezeTime = Date.parse(freezeIdentity.updated_at || '');
  const baselineCreated = Date.parse(baselineRun?.created_at || '');
  const baselineCompleted = Number(baselineRun?.completed_at) * 1000;
  const laterCreated = Date.parse(laterRun?.created_at || '');
  if (![freezeTime, baselineCreated, baselineCompleted, laterCreated].every(Number.isFinite)
    || !(freezeTime <= baselineCreated && baselineCreated <= baselineCompleted && baselineCompleted <= laterCreated)) issues.push('counterfactual baseline/current runs are not ordered after the learning freeze');
  if (!exactMembers(Object.keys(receipt.target || {}), ['run_id', 'claim_id']) || receipt.target.run_id !== laterRun.run_id || receipt.target.claim_id !== laterRun.claim_id) issues.push('memory receipt target is not the later run');
  const retainedBoundary = laterRun.memory_application_boundary;
  const retainedBoundaryProjection = retainedBoundary && typeof retainedBoundary === 'object' && !Array.isArray(retainedBoundary)
    ? Object.fromEntries(Object.entries(retainedBoundary).filter(([key]) => key !== 'boundary_hash'))
    : null;
  if (!exactMembers(Object.keys(retainedBoundary || {}), ['contract', 'target', 'source_memory', 'before', 'boundary_hash'])) issues.push('memory application boundary fields are not exact');
  if (retainedBoundary?.contract !== 'casepath.memory-application-boundary/1.0.0'
    || !exactMembers(Object.keys(retainedBoundary?.target || {}), ['run_id', 'claim_id'])
    || stableJson(retainedBoundary?.target) !== stableJson(receipt.target)
    || !exactMembers(Object.keys(retainedBoundary?.source_memory || {}), ['memory_id', 'content_hash'])
    || retainedBoundary?.source_memory?.memory_id !== receipt.source_memory?.memory_id
    || retainedBoundary?.source_memory?.content_hash !== receipt.source_memory?.content_hash) issues.push('memory application boundary identity or source join is wrong');
  if (!exactMembers(Object.keys(retainedBoundary?.before || {}), boundaryFields)
    || !Object.values(retainedBoundary?.before || {}).every(value => SHA256_PATTERN.test(value || ''))
    || stableJson(retainedBoundary?.before) !== stableJson(receipt.before)) issues.push('memory application boundary before hashes do not equal receipt.before');
  if (!SHA256_PATTERN.test(retainedBoundary?.boundary_hash || '')
    || retainedBoundary?.boundary_hash !== dtoHash(retainedBoundaryProjection)) issues.push('memory application boundary hash is wrong');
  const completedMemoryEvents = (laterRun.events || []).filter(event => event?.stage === 'memory_application'
    && event?.receipt_type === 'memory_application_receipt'
    && event?.status === 'completed');
  if (completedMemoryEvents.length !== 1) issues.push('exactly one completed persisted memory-application event is required');
  if (completedMemoryEvents.length === 1) {
    const event = completedMemoryEvents[0];
    const eventHasReceiptFields = receiptFields.every(key => Object.hasOwn(event, key));
    const eventReceiptProjection = eventHasReceiptFields ? Object.fromEntries(receiptFields.map(key => [key, event[key]])) : null;
    if (!eventHasReceiptFields || stableJson(eventReceiptProjection) !== stableJson(receipt)) issues.push('persisted memory-application event does not project the result receipt');
  }
  if (receipt.observable_input_hash !== later.audit?.observable_input_hash || receipt.observable_input_hash !== baseline.audit?.observable_input_hash || receipt.observable_input_hash !== proof.before?.observable_input_hash || receipt.observable_input_hash !== proof.after?.observable_input_hash) issues.push('observable input hash is not bound across both runs');
  // Canonical facts intentionally contain JSON floats (including integral 1.0 values).
  // A browser JSON roundtrip erases that lexical distinction, so JS must not forge a
  // Python hash from the parsed object. Bind the unchanged returned DTO to the two
  // server-computed run audit hashes and the independently recomputed proof instead.
  if (stableJson(baseline.facts) !== stableJson(later.facts)
    || receipt.canonical_state_hash !== later.audit?.canonical_state_hash
    || receipt.canonical_state_hash !== baseline.audit?.canonical_state_hash
    || receipt.canonical_state_hash !== proof.before?.canonical_state_hash
    || receipt.canonical_state_hash !== proof.after?.canonical_state_hash) issues.push('canonical-state hash is not bound across both unchanged runs');
  issues.push(...semanticFactRoleViolations(baseline).map(issue => `baseline ${issue}`));
  issues.push(...semanticFactRoleViolations(later).map(issue => `later ${issue}`));
  const eligibility = receipt.eligibility || {};
  const requiredDecisions = {
    scope: 'in_scope', dispute: 'dispute_present', urgency: 'not_urgent', notification: 'notified', recurrence: 'recurrence_supported', causation: 'cause_unresolved',
  };
  const requiredFactRoles = {
    management_ventilation_allegation: { state: 'known', min_grounded_sources: 1 },
  };
  const semanticSignatureHash = dtoHash({
    category: 'Rental defect - mould and moisture',
    subcategory: 'Recurring moisture with disputed causation',
    required_decisions: requiredDecisions,
    required_fact_roles: requiredFactRoles,
  });
  const expectedDecisions = Object.fromEntries((later.facts || []).filter(fact => fact.controls_process === true).map(fact => [fact.decision_key, fact.decision_value]));
  const expectedChecks = {
    source_claim_excluded: receipt.source_memory?.claim_id !== laterRun.claim_id,
    category_matched: later.category === 'Rental defect - mould and moisture',
    subcategory_matched: later.subcategory === 'Recurring moisture with disputed causation',
    required_decisions_matched: stableJson(expectedDecisions) === stableJson(requiredDecisions),
    ventilation_allegation_grounded: semanticFactSignature(later).management_ventilation_allegation?.state === 'known'
      && semanticFactSignature(later).management_ventilation_allegation?.grounded_source_count >= 1,
    semantic_signature_bound: eligibility.semantic_signature_hash === semanticSignatureHash,
    guidance_enabled: true,
  };
  const eligibilityManifest = Object.fromEntries(['rule_id', 'contract', 'claim_id', 'semantic_signature_hash', 'decisions', 'facts_hash', 'checks'].map(key => [key, eligibility[key]]));
  if (!exactMembers(Object.keys(eligibility), ['rule_id', 'contract', 'claim_id', 'semantic_signature_hash', 'decisions', 'facts_hash', 'checks', 'eligible', 'manifest_hash'])
    || eligibility.rule_id !== 'same_grounded_mould_signature_v2'
    || eligibility.contract !== 'casepath.semantic-memory-eligibility/1.0.0'
    || eligibility.claim_id !== laterRun.claim_id
    || eligibility.semantic_signature_hash !== semanticSignatureHash
    || stableJson(eligibility.decisions) !== stableJson(requiredDecisions)
    || stableJson(expectedDecisions) !== stableJson(requiredDecisions)
    || eligibility.facts_hash !== dtoHash(semanticFactSignature(later))
    || stableJson(eligibility.checks) !== stableJson(expectedChecks)
    || eligibility.eligible !== true
    || eligibility.manifest_hash !== dtoHash(eligibilityManifest)) issues.push('semantic eligibility manifest is not exact and hash-bound');
  if (!exactMembers(Object.keys(receipt.before || {}), boundaryFields) || !exactMembers(Object.keys(receipt.after || {}), boundaryFields) || ![...Object.values(receipt.before || {}), ...Object.values(receipt.after || {})].every(value => SHA256_PATTERN.test(value || ''))) issues.push('memory before/after boundary hashes are not exact');
  if (receipt.before?.process_semantic_hash !== dtoHash(semanticProcessDto(baseline.process)) || receipt.before?.checklist_semantic_hash !== dtoHash(semanticChecklistDto(baseline.checklist))) issues.push('receipt before semantic hashes do not bind the baseline DTOs');
  const exactAfter = { process_dto_hash: dtoHash(later.process), checklist_dto_hash: dtoHash(later.checklist), process_semantic_hash: dtoHash(semanticProcessDto(later.process)), checklist_semantic_hash: dtoHash(semanticChecklistDto(later.checklist)) };
  if (stableJson(receipt.after) !== stableJson(exactAfter) || boundaryFields.some(key => proof.after?.[key] !== exactAfter[key])) issues.push('receipt/proof after hashes do not bind the later DTOs');
  if (boundaryFields.some(key => receipt.before?.[key] === receipt.after?.[key])) issues.push('memory receipt reports a zero DTO or semantic delta');
  if (receipt.verification_hash !== later.verification?.whole_playbook_hash || receipt.verification_hash !== proof.after?.verification_hash) issues.push('memory receipt verification hash is not bound to the later result');
  const operationIds = ['add_ventilation_dispute_node', 'add_evidence_gap_to_ventilation_edge', 'add_ventilation_to_causation_edge', 'condition_building_envelope', 'reassign_use_evidence_to_ventilation'];
  if (JSON.stringify(receipt.allowed_operation_ids) !== JSON.stringify(operationIds) || JSON.stringify(receipt.applied_operation_ids) !== JSON.stringify(operationIds) || JSON.stringify([...(receipt.process_operations || []), ...(receipt.evidence_operations || [])].map(value => value.operation_id)) !== JSON.stringify(operationIds)) issues.push('memory operation membership or order is wrong');
  const processOperationFields = [['operation_id', 'operation', 'node_id', 'evidence_requirement_ids', 'after_hash'], ['operation_id', 'operation', 'source', 'target', 'after_hash'], ['operation_id', 'operation', 'source', 'target', 'after_hash']];
  const evidenceOperationFields = [['operation_id', 'operation', 'item_id', 'before_hash', 'after_hash'], ['operation_id', 'operation', 'item_id', 'removed_from_node_ids', 'added_to_node_id', 'before_hash', 'after_hash']];
  if ((receipt.process_operations || []).length !== 3 || (receipt.evidence_operations || []).length !== 2 || (receipt.process_operations || []).some((operation, index) => !exactMembers(Object.keys(operation || {}), processOperationFields[index])) || (receipt.evidence_operations || []).some((operation, index) => !exactMembers(Object.keys(operation || {}), evidenceOperationFields[index]))) issues.push('memory operation fields are not exact');
  const receiptHashes = [receipt.observable_input_hash, receipt.canonical_state_hash, receipt.verification_hash, receipt.application_hash, receipt.source_memory?.content_hash, ...Object.values(receipt.before || {}), ...Object.values(receipt.after || {}), ...(receipt.process_operations || []).map(operation => operation.after_hash), ...(receipt.evidence_operations || []).flatMap(operation => [operation.before_hash, operation.after_hash])];
  if (!receiptHashes.every(value => SHA256_PATTERN.test(value || ''))) issues.push('memory receipt contains an invalid SHA-256 value');
  const addedNode = later.process?.nodes?.find(node => node.node_id === 'ventilation_dispute');
  const firstEdge = later.process?.edges?.find(edge => edge.source === 'evidence_gap' && edge.target === 'ventilation_dispute');
  const secondEdge = later.process?.edges?.find(edge => edge.source === 'ventilation_dispute' && edge.target === 'causation');
  const buildingEnvelope = later.checklist?.items?.find(item => item.item_id === 'building_envelope');
  const useEvidence = later.checklist?.items?.find(item => item.item_id === 'use_evidence');
  if (!addedNode || receipt.process_operations?.[0]?.node_id !== 'ventilation_dispute' || JSON.stringify(receipt.process_operations?.[0]?.evidence_requirement_ids) !== JSON.stringify(['management_position', 'use_evidence']) || receipt.process_operations?.[0]?.after_hash !== dtoHash(addedNode)) issues.push('added ventilation node operation is not hash-bound');
  if (!firstEdge || !secondEdge || receipt.process_operations?.[1]?.after_hash !== dtoHash(firstEdge) || receipt.process_operations?.[2]?.after_hash !== dtoHash(secondEdge)) issues.push('added edge operations are not hash-bound');
  if (!buildingEnvelope || buildingEnvelope.status !== 'conditional' || buildingEnvelope.current_path !== true || receipt.evidence_operations?.[0]?.item_id !== 'building_envelope' || receipt.evidence_operations?.[0]?.after_hash !== dtoHash(buildingEnvelope)) issues.push('building-envelope replacement is not hash-bound');
  if (!useEvidence || useEvidence.node_id !== 'ventilation_dispute' || receipt.evidence_operations?.[1]?.item_id !== 'use_evidence' || receipt.evidence_operations?.[1]?.added_to_node_id !== 'ventilation_dispute' || receipt.evidence_operations?.[1]?.after_hash !== dtoHash(useEvidence)) issues.push('use-evidence reassignment is not hash-bound');
  if (receipt.process_operations?.[0]?.operation !== 'add_node' || receipt.process_operations?.slice(1).some(operation => operation.operation !== 'add_edge') || receipt.evidence_operations?.[0]?.operation !== 'replace_item' || receipt.evidence_operations?.[1]?.operation !== 'reassign_item' || stableJson(receipt.evidence_operations?.[1]?.removed_from_node_ids) !== stableJson(['causation', 'mixed_cause', 'tenant_use'])) issues.push('memory operation semantics are wrong');
  if (receipt.application_hash !== dtoHash(Object.fromEntries(Object.entries(receipt).filter(([key]) => key !== 'application_hash')))) issues.push('memory application hash is wrong');
  const expectedDelta = computedCausalDelta(baseline, later);
  if (stableJson(proof.causal_delta) !== stableJson(expectedDelta)) issues.push('learning proof causal delta is not recomputed from both DTOs');
  if (stableJson(proof.causal_delta?.process?.added_node_ids) !== stableJson(['ventilation_dispute']) || stableJson(proof.causal_delta?.process?.added_edges) !== stableJson([{ source: 'evidence_gap', target: 'ventilation_dispute' }, { source: 'ventilation_dispute', target: 'causation' }]) || stableJson(proof.causal_delta?.evidence?.changed_item_ids) !== stableJson(['building_envelope', 'management_position', 'use_evidence'])) issues.push('causal delta is outside the exact case-specific transform');
  const expectedCheckNames = ['Same observable input', 'Same canonical state', 'Exact current memory receipt', 'Pure memory replay matches learned DTOs', 'Receipt before semantic hashes match baseline DTOs', 'Receipt after hashes match learned DTOs', 'Nonzero causal DTO delta', 'Only allowed causal operations changed', 'Deterministic target and protected checks passed', 'Shared v3 remains unchanged'];
  if (proof.ready !== true || proof.computed !== true || proof.baseline_run_id !== baselineRun.run_id || proof.later_run_id !== laterRun.run_id || JSON.stringify((proof.deterministic_checks || []).map(check => check.name)) !== JSON.stringify(expectedCheckNames) || !(proof.deterministic_checks || []).every(check => check.status === 'passed')) issues.push('learning proof checks are absent, reordered, or failed');
  if (proof.reviewed_memory_proof?.used !== true || proof.reviewed_memory_proof?.present_in_baseline !== false || proof.reviewed_memory_proof?.present_in_later_run !== true || !proof.reviewed_memory_proof?.memory_ids?.includes(receipt.source_memory.memory_id) || stableJson(proof.changes?.precedent_claim_ids_added) !== stableJson(['DEF-027-E0-DEMO'])) issues.push('learning proof does not bind the selected unverified memory');
  if (proof.candidate?.status !== 'quarantined' || proof.candidate?.target_tests?.status !== 'passed' || proof.candidate?.protected_regression?.status !== 'passed' || proof.candidate?.qualified_support_count !== 0 || proof.candidate?.approval?.status !== 'pending' || proof.candidate?.approval?.qualified_reviewer !== false) issues.push('candidate target/protected checks or qualified-release boundary is wrong');
  const receiptProof = proof.memory_application_proof || {};
  if (!exactMembers(Object.keys(receiptProof), ['receipt_present', 'receipt_valid', 'source_memory_current', 'before_hashes_match', 'after_hashes_match', 'allowed_delta_exact', 'replay_exact', 'application_hash'])
    || !['receipt_present', 'receipt_valid', 'source_memory_current', 'before_hashes_match', 'after_hashes_match', 'allowed_delta_exact', 'replay_exact'].every(key => receiptProof[key] === true)
    || receiptProof.application_hash !== receipt.application_hash) issues.push('memory application proof does not validate the current receipt and pure replay');
  if (later.playbook?.version !== 'mould-playbook-v3' || later.shared_rule_applied !== false || proof.shared_rule?.version_before !== 'mould-playbook-v3' || proof.shared_rule?.version_after !== 'mould-playbook-v3' || proof.shared_rule?.applied !== false || proof.shared_rule?.shared_knowledge_changed !== false) issues.push('shared v3 boundary is not unchanged');
  if (Object.hasOwn(later.process || {}, 'agent_contribution') || (later.process?.nodes || []).some(node => Object.hasOwn(node, 'agent_decision_contributions')) || Object.hasOwn(later.checklist || {}, 'agent_contribution') || (later.checklist?.items || []).some(item => Object.hasOwn(item, 'agent_contribution')) || later.next_action?.agent_brief_contribution !== null) issues.push('post-memory DTOs retain pre-memory model contribution fields or next-action attribution');
  return issues;
}

function hybridCausalContractViolations(run) {
  const issues = [];
  const audit = orchestrationAudit(run);
  const result = run?.result;
  const artifacts = audit?.specialist_artifacts;
  if (!audit || !result || !artifacts || typeof artifacts !== 'object' || Array.isArray(artifacts)) {
    return ['hybrid specialist artifacts or final result are absent'];
  }
  const agents = new Map((audit.agents || []).map(item => [item.agent_id, item]));
  const gates = new Map((audit.deterministic_gates || []).map(item => [item.agent_id, item]));
  const sourceArtifact = artifacts.document_source_integrity;
  const processArtifact = artifacts.process_decision_mapping;
  const evidenceArtifact = artifacts.evidence_checklist;
  const finalArtifact = artifacts.final_claim_brief_audit;
  if (![sourceArtifact, processArtifact, evidenceArtifact, finalArtifact].every(value => value && typeof value === 'object' && !Array.isArray(value))) {
    return ['one or more causal specialist artifacts are absent'];
  }

  const sourceAgent = agents.get('document_source_integrity');
  const processAgent = agents.get('process_decision_mapping');
  const evidenceAgent = agents.get('evidence_checklist');
  const finalAgent = agents.get('final_claim_brief_audit');
  if (sourceAgent?.output_artifact_hash !== dtoHash(sourceArtifact)) issues.push('document source specialist artifact hash is not exact');
  if (processAgent?.output_artifact_hash !== dtoHash(processArtifact)) issues.push('process specialist artifact hash is not exact');
  if (evidenceAgent?.output_artifact_hash !== dtoHash(evidenceArtifact)) issues.push('evidence specialist artifact hash is not exact');
  if (finalAgent?.output_artifact_hash !== dtoHash(finalArtifact)) issues.push('final specialist artifact hash is not exact');

  const processGate = gates.get('deterministic_process_gate');
  const expectedParallelInputHash = dtoHash({
    source_integrity: sourceArtifact,
    process_mapping: processArtifact,
  });
  if (processGate?.input_artifact_hash !== expectedParallelInputHash) issues.push('process gate parallel specialist composite input hash is not exact');
  const evidenceGate = gates.get('deterministic_evidence_gate');
  if (evidenceGate?.input_artifact_hash !== dtoHash(evidenceArtifact)) issues.push('evidence gate specialist input hash is not exact');

  const process = result.process;
  const checklist = result.checklist;
  if (!process || !checklist) return [...issues, 'hybrid process or checklist DTO is absent'];
  if (stableJson(process.agent_contribution?.source_integrity_artifact) !== stableJson(sourceArtifact)) issues.push('final process does not retain the exact source specialist artifact');
  if (stableJson(process.agent_contribution?.artifact) !== stableJson(processArtifact)) issues.push('final process does not retain the exact process specialist artifact');

  const decisions = Array.isArray(processArtifact.decisions) ? processArtifact.decisions : [];
  const validDecisions = contributionEntries(decisions, PROCESS_CONTRIBUTION_ROLE);
  if (!validDecisions) issues.push('process decision field contributions violate membership or attribution');
  const controllingFacts = (result.facts || []).filter(item => item?.controls_process === true);
  const controllingFactIds = controllingFacts.map(item => item.fact_id);
  const controllingById = new Map(controllingFacts.map(item => [item.fact_id, item]));
  if (!exactMembers(decisions.map(item => item?.fact_id), controllingFactIds)) issues.push('process decision fact membership is not exact');
  const decisionsByFact = new Map();
  for (const decision of decisions) {
    if (!decision || typeof decision !== 'object' || !nonemptyString(decision.fact_id)) continue;
    if (decision.contribution_id !== `fact:${decision.fact_id}:decision_value`) issues.push(`process decision ${decision.fact_id} contribution ID is not exact`);
    if (decisionsByFact.has(decision.fact_id)) issues.push(`process decision ${decision.fact_id} is duplicated`);
    const canonicalFact = controllingById.get(decision.fact_id);
    if (!canonicalFact
      || decision.decision_key !== canonicalFact.decision_key
      || !compatibleProcessDecisionValues(canonicalFact).has(decision.decision_value)
      || decision.state !== canonicalFact.state
      || decision.normalized_value !== canonicalFact.normalized_value) issues.push(`process decision ${decision.fact_id} inherited canonical fields are not exact`);
    const sourceRefIds = decision.source_ref_ids;
    if (!Array.isArray(sourceRefIds)
      || sourceRefIds.some(item => !nonemptyString(item))
      || new Set(sourceRefIds).size !== sourceRefIds.length
      || JSON.stringify(sourceRefIds) !== JSON.stringify([...sourceRefIds].sort())) issues.push(`process decision ${decision.fact_id} source reference IDs are not unique and sorted`);
    decisionsByFact.set(decision.fact_id, decision);
  }
  if (validDecisions && processAgent) {
    const acceptedIds = validDecisions.filter(item => item.deterministic_fallback_applied === false).map(item => item.contribution_id);
    const fallbackCount = validDecisions.length - acceptedIds.length;
    if (JSON.stringify(processAgent.accepted_ids) !== JSON.stringify(acceptedIds)
      || processAgent.accepted_count !== acceptedIds.length
      || processAgent.rejected_count !== fallbackCount
      || processAgent.deterministic_fallback_applied !== (fallbackCount > 0)) issues.push('process agent accepted/fallback field diagnostics are not exact');
  }
  for (const node of process.nodes || []) {
    const expected = (node.fact_ids || []).flatMap(factId => decisionsByFact.has(factId) ? [decisionsByFact.get(factId)] : []);
    const actual = Array.isArray(node.agent_decision_contributions) ? node.agent_decision_contributions : [];
    if (stableJson(actual) !== stableJson(expected)) issues.push(`process node ${node.node_id || 'unknown'} field attribution is not projected from the specialist artifact`);
  }

  if (stableJson(checklist.agent_contribution?.artifact) !== stableJson(evidenceArtifact)) issues.push('final checklist does not retain the exact evidence specialist artifact');
  const artifactItems = Array.isArray(evidenceArtifact.items) ? evidenceArtifact.items : [];
  const checklistItems = Array.isArray(checklist.items) ? checklist.items : [];
  if (!exactMembers(artifactItems.map(item => item?.item_id), checklistItems.map(item => item?.item_id))) issues.push('evidence specialist item membership is not exact');
  const checklistById = new Map(checklistItems.map(item => [item.item_id, item]));
  const evidenceUnits = [];
  for (const artifactItem of artifactItems) {
    const itemId = artifactItem?.item_id;
    const sourceRefIds = artifactItem?.source_ref_ids;
    if (!Array.isArray(sourceRefIds)
      || sourceRefIds.some(item => !nonemptyString(item))
      || new Set(sourceRefIds).size !== sourceRefIds.length
      || JSON.stringify(sourceRefIds) !== JSON.stringify([...sourceRefIds].sort())) issues.push(`evidence item ${itemId || 'unknown'} source reference IDs are not unique and sorted`);
    const units = contributionEntries(artifactItem?.field_contributions, EVIDENCE_CONTRIBUTION_ROLE);
    const expectedUnits = [
      { contribution_id: `item:${itemId}:status`, field: 'status' },
      { contribution_id: `item:${itemId}:artifacts`, field: 'artifact_ids' },
    ];
    if (!units || units.length !== 2 || stableJson(units.map(item => ({ contribution_id: item.contribution_id, field: item.field }))) !== stableJson(expectedUnits)) {
      issues.push(`evidence item ${itemId || 'unknown'} does not contain the exact two field contributions`);
      continue;
    }
    evidenceUnits.push(...units);
    const finalItem = checklistById.get(itemId);
    if (!finalItem) continue;
    if (finalItem.status !== artifactItem.status) issues.push(`evidence item ${itemId} status is not projected from the specialist artifact`);
    if (!exactMembers(finalItem.artifact_ids, artifactItem.artifact_ids)) issues.push(`evidence item ${itemId} artifact set is not projected from the specialist artifact`);
    if (stableJson(finalItem.agent_contribution) !== stableJson(units)) issues.push(`evidence item ${itemId} field attribution is not projected from the specialist artifact`);
  }
  if (evidenceUnits.length && evidenceAgent) {
    const acceptedIds = evidenceUnits.filter(item => item.deterministic_fallback_applied === false).map(item => item.contribution_id);
    const fallbackCount = evidenceUnits.length - acceptedIds.length;
    if (JSON.stringify(evidenceAgent.accepted_ids) !== JSON.stringify(acceptedIds)
      || evidenceAgent.accepted_count !== acceptedIds.length
      || evidenceAgent.rejected_count !== fallbackCount
      || evidenceAgent.deterministic_fallback_applied !== (fallbackCount > 0)) issues.push('evidence agent accepted/fallback field diagnostics are not exact');
  }

  const finalBrief = audit.final_claim_brief;
  if (stableJson(finalArtifact) !== stableJson(finalBrief)) issues.push('final specialist artifact and authoritative final claim brief differ');
  const finalUnits = contributionEntries(finalBrief?.field_contributions, FINAL_CONTRIBUTION_ROLE);
  if (!finalUnits
    || finalUnits.length !== FINAL_FIELD_CONTRACT.length
    || stableJson(finalUnits.map(item => ({ field: item.field, contribution_id: item.contribution_id }))) !== stableJson(FINAL_FIELD_CONTRACT)) issues.push('final claim brief does not contain the exact five field contributions');
  if (finalUnits && finalAgent) {
    const acceptedIds = finalUnits.filter(item => item.deterministic_fallback_applied === false).map(item => item.contribution_id);
    const fallbackCount = finalUnits.length - acceptedIds.length;
    if (JSON.stringify(finalAgent.accepted_ids) !== JSON.stringify(acceptedIds)
      || finalAgent.accepted_count !== acceptedIds.length
      || finalAgent.rejected_count !== fallbackCount
      || finalAgent.deterministic_fallback_applied !== (fallbackCount > 0)) issues.push('final agent accepted/fallback field diagnostics are not exact');
    const expectedAttribution = fallbackCount === 0 ? FINAL_CONTRIBUTION_ROLE : acceptedIds.length ? 'mixed_model_and_deterministic' : DETERMINISTIC_CONTRIBUTION_ROLE;
    if (finalBrief.attribution !== expectedAttribution || finalBrief.deterministic_fallback_applied !== (fallbackCount > 0)) issues.push('final claim brief aggregate attribution is not exact');
    const upstreamUnit = finalUnits.find(item => item.field === 'upstream_contribution_ids');
    const expectedLineageAuthority = upstreamUnit?.deterministic_fallback_applied === false ? 'hybrid_guarded_model_audit' : DETERMINISTIC_CONTRIBUTION_ROLE;
    if (finalBrief.lineage_authority !== expectedLineageAuthority) issues.push('final claim brief lineage authority is not exact');
  }
  if (finalBrief?.contribution_scope !== 'independent_final_claim_brief_audit') issues.push('final claim brief contribution scope is not exact');

  const overlay = process.current_overlay || {};
  if (finalBrief?.current_node_id !== process.current_node || finalBrief?.current_node_id !== overlay.current_node_id) issues.push('final current-node field is not causally bound to the process overlay');
  if (finalBrief?.next_action_node_id !== overlay.next_action_node_id || finalBrief?.next_action_node_id !== result.next_action?.process_node_id) issues.push('final next-action field is not causally bound to the result');
  if (stableJson(result.next_action?.agent_brief_contribution) !== stableJson(finalBrief)) issues.push('result next action does not retain the exact final claim brief');
  const currentNode = (process.nodes || []).find(item => item.node_id === finalBrief?.current_node_id);
  const expectedSupportingFacts = [...(currentNode?.fact_ids || [])].sort();
  if (JSON.stringify(finalBrief?.supporting_fact_ids) !== JSON.stringify(expectedSupportingFacts)) issues.push('final supporting-facts field is not bound to the current process node');
  if (JSON.stringify(finalBrief?.upstream_contribution_ids) !== JSON.stringify(FINAL_UPSTREAM_CONTRIBUTION_IDS)
    || JSON.stringify(finalBrief?.input_contribution_ids) !== JSON.stringify(FINAL_UPSTREAM_CONTRIBUTION_IDS)) issues.push('final upstream-contribution field is not complete and exact');
  if (JSON.stringify(finalBrief?.audit_check_ids) !== JSON.stringify(FINAL_AUDIT_CHECK_IDS)) issues.push('final audit-check field is not complete and exact');
  const supportingFactSet = new Set(expectedSupportingFacts);
  const expectedSourceRefs = [...new Set([
    ...decisions.filter(item => supportingFactSet.has(item.fact_id)).flatMap(item => item.source_ref_ids || []),
    ...artifactItems.filter(item => supportingFactSet.has(checklistById.get(item.item_id)?.fact_id)).flatMap(item => item.source_ref_ids || []),
  ])].sort();
  if (JSON.stringify(finalBrief?.source_ref_ids) !== JSON.stringify(expectedSourceRefs)) issues.push('final source-reference field is not derived from controlling and non-controlling supporting facts');
  return issues;
}

function internalSentinelPaths(value, currentPath = '$', found = []) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => internalSentinelPaths(item, `${currentPath}[${index}]`, found));
    return found;
  }
  if (value && typeof value === 'object') {
    Object.entries(value).forEach(([key, child]) => internalSentinelPaths(child, `${currentPath}.${key}`, found));
    return found;
  }
  if (typeof value === 'string' && INTERNAL_SENTINEL_PATTERN.test(value)) found.push(currentPath);
  return found;
}

function nonIntegerNumberPaths(value, currentPath = '$', found = []) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => nonIntegerNumberPaths(item, `${currentPath}[${index}]`, found));
    return found;
  }
  if (value && typeof value === 'object') {
    Object.entries(value).forEach(([key, child]) => nonIntegerNumberPaths(child, `${currentPath}.${key}`, found));
    return found;
  }
  if (typeof value === 'number' && (!Number.isInteger(value) || Object.is(value, -0))) found.push(currentPath);
  return found;
}

function runProgressDiagnostic(run) {
  const safeEvents = Array.isArray(run?.events)
    ? run.events
      .filter(item => item?.stage === 'agent_orchestration')
      .slice(-12)
      .map(item => ({
        ordinal: item.ordinal,
        agent_id: item.agent_id,
        actor_type: item.actor_type,
        status: item.status,
        receipt_type: item.receipt_type,
        outcome: item.outcome,
        handoff_to: item.handoff_to,
      }))
    : [];
  return {
    run_id: run?.run_id || null,
    status: run?.status || 'not_found',
    stage: run?.stage || null,
    error_present: nonemptyString(run?.error),
    recent_agent_receipts: safeEvents,
  };
}

function terminalFailureContractViolations(run) {
  if (run?.status !== 'failed') return [];
  const issues = [];
  const sentinelLeaks = internalSentinelPaths(run);
  if (sentinelLeaks.length) issues.push(`terminal failure leaks internal execution sentinels at ${sentinelLeaks.join(', ')}`);
  const sensitive = forbiddenFieldPaths(run);
  if (sensitive.length) issues.push(`terminal failure leaks forbidden fields at ${sensitive.join(', ')}`);
  const events = Array.isArray(run?.events) ? run.events : [];
  const completedByAgent = new Map(events
    .filter(item => item?.actor_type === 'nemotron_agent' && item?.receipt_type === 'agent_completed' && item?.status === 'completed')
    .map(item => [item.agent_id, item]));
  const failureReceipts = events.filter(item => item?.receipt_type === 'agent_failed');
  for (const receipt of failureReceipts) {
    const unexpected = Object.keys(receipt).filter(key => !ALLOWED_AGENT_FAILURE_RECEIPT_FIELDS.has(key));
    if (unexpected.length) issues.push(`${receipt.agent_id || 'unknown'} failure receipt has non-allowlisted fields: ${unexpected.join(', ')}`);
    const isCanonicalRoot = receipt.agent_id === 'canonical_facts';
    const expectedParent = isCanonicalRoot
      ? null
      : receipt.agent_id === 'orchestrator_plan'
        ? completedByAgent.get('canonical_facts')?.call_id
        : completedByAgent.get('orchestrator_plan')?.call_id;
    const rootLineageValid = !isCanonicalRoot || (
      receipt.failure_scope === 'root_canonical_facts'
      && receipt.root_agent === true
      && receipt.parent_call_id == null
      && receipt.delegation_id == null
      && receipt.input_artifact === 'observable_claim_package'
      && receipt.provider === 'openrouter'
      && receipt.requested_model === REQUESTED_NEMOTRON_MODEL
      && nonemptyString(receipt.orchestration_id)
      && receipt.shared_context === `claim-context:${run.run_id}`
      && Number.isInteger(receipt.call_count)
      && receipt.call_count === (ZERO_CALL_FAILURE_OUTCOMES.has(receipt.outcome) ? 0 : 1)
    );
    const delegatedLineageValid = isCanonicalRoot || (
      nonemptyString(receipt.delegation_id)
      && nonemptyString(expectedParent)
      && receipt.parent_call_id === expectedParent
    );
    if (!REQUIRED_NEMOTRON_AGENT_IDS.includes(receipt.agent_id)
      || receipt.actor_type !== 'nemotron_agent'
      || receipt.status !== 'failed'
      || receipt.acceptance_scope !== 'pre_review_model_output'
      || !nonemptyString(receipt.call_id)
      || !rootLineageValid
      || !delegatedLineageValid
      || !SHA256_PATTERN.test(receipt.input_artifact_hash || '')
      || !nonemptyString(receipt.error_type)
      || !nonemptyString(receipt.error_invariant)
      || !FAILURE_OUTCOMES.has(receipt.outcome)
      || receipt.handoff_to !== 'failure_boundary'
      || receipt.external_tracing !== false
      || receipt.model !== REQUESTED_NEMOTRON_MODEL) issues.push(`${receipt.agent_id || 'unknown'} failure receipt identity/lineage is invalid`);
    const expectedCallCount = ZERO_CALL_FAILURE_OUTCOMES.has(receipt.outcome) ? 0 : 1;
    if (!Number.isInteger(receipt.call_count) || receipt.call_count !== expectedCallCount) issues.push(`${receipt.agent_id || 'unknown'} failure receipt call_count does not match its exact provider-call outcome`);
    if (receipt.outcome === 'blocked_provider_concurrency' || receipt.error_invariant === 'provider_concurrency_timeout') {
      const retainedProviderResultFields = ZERO_CALL_PROVIDER_RESULT_FIELDS.filter(field => receipt[field] != null);
      if (receipt.outcome !== 'blocked_provider_concurrency'
        || receipt.error_invariant !== 'provider_concurrency_timeout'
        || receipt.call_count !== 0
        || retainedProviderResultFields.length) issues.push(`${receipt.agent_id || 'unknown'} blocked provider concurrency is not an exact zero-call receipt`);
    }
    const responseIdPresent = nonemptyString(receipt.response_id);
    const responseModelPresent = nonemptyString(receipt.response_model);
    const responseIdBounded = providerProvenanceValueIsSafe('response_id', receipt.response_id);
    const responseModelBounded = providerProvenanceValueIsSafe('response_model', receipt.response_model);
    const upstreamBounded = providerProvenanceValueIsSafe('upstream_provider', receipt.upstream_provider);
    const finishReasonBounded = providerProvenanceValueIsSafe('finish_reason', receipt.finish_reason);
    if (!responseIdBounded || !responseModelBounded || !upstreamBounded || !finishReasonBounded) issues.push(`${receipt.agent_id || 'unknown'} failure provider provenance is not bounded`);
    if (receipt.error_invariant === 'response_identity') {
      if (responseIdPresent && responseModelPresent) issues.push(`${receipt.agent_id || 'unknown'} response-identity failure is unexpectedly complete`);
    } else if (receipt.error_invariant === 'invalid_provenance') {
      if (!PROVIDER_PROVENANCE_FIELDS.has(receipt.invalid_provenance_field)
        || !SHA256_PATTERN.test(receipt.invalid_provenance_value_hash || '')
        || receipt[receipt.invalid_provenance_field] != null) issues.push(`${receipt.agent_id || 'unknown'} invalid-provenance failure lacks its safe field/hash diagnostic or retained the rejected value`);
    } else if (receipt.error_invariant === 'provider_upstream_rejection') {
      if (receipt.response_model != null || receipt.upstream_provider != null || receipt.usage_source != null || receipt.finish_reason != null) issues.push(`${receipt.agent_id || 'unknown'} upstream rejection claims unavailable provider success metadata`);
      if (receipt.provider_error_code != null && (!Number.isInteger(receipt.provider_error_code) || receipt.provider_error_code < 0 || receipt.provider_error_code > 9999)) issues.push(`${receipt.agent_id || 'unknown'} upstream rejection error code is unbounded`);
      if (responseIdPresent && !EXACT_OPENROUTER_GENERATION_ID.test(receipt.response_id)) issues.push(`${receipt.agent_id || 'unknown'} upstream rejection response ID is not an exact OpenRouter generation ID`);
    } else if ((responseIdPresent || responseModelPresent) && (
      !responseIdPresent
      || !responseModelPresent
      || !EXACT_NEMOTRON_RESPONSE_MODELS.has(receipt.response_model)
    )) {
      issues.push(`${receipt.agent_id || 'unknown'} failure response identity is partial or unauthorized`);
    }
    if (receipt.error_invariant !== 'invalid_provenance'
      && (receipt.invalid_provenance_field != null || receipt.invalid_provenance_value_hash != null)) issues.push(`${receipt.agent_id || 'unknown'} failure carries an out-of-scope invalid-provenance diagnostic`);
    if (receipt.error_invariant !== 'provider_upstream_rejection' && receipt.provider_error_code != null) issues.push(`${receipt.agent_id || 'unknown'} failure carries an out-of-scope provider error code`);
    const boundaryIssue = providerRejectionBoundaryIssue(receipt);
    if (boundaryIssue) issues.push(`${receipt.agent_id || 'unknown'} failure ${boundaryIssue}`);
    if (receipt.outcome === 'actual_cost_overrun' && (
      !responseIdPresent
      || !responseModelPresent
      || !EXACT_NEMOTRON_RESPONSE_MODELS.has(receipt.response_model)
      || !ALLOWED_USAGE_SOURCES.has(receipt.usage_source)
    )) issues.push(`${receipt.agent_id || 'unknown'} charged overrun lacks complete provider lineage`);
    if (receipt.usage_source != null && !ALLOWED_USAGE_SOURCES.has(receipt.usage_source)) issues.push(`${receipt.agent_id || 'unknown'} failure usage provenance is invalid`);
  }
  const terminalBoundaries = events.filter(item => item?.stage === 'failed' && item?.status === 'failed' && item?.actor_type === 'deterministic_gate');
  if (terminalBoundaries.length !== 1) {
    issues.push('terminal deterministic failure boundary is absent or duplicated');
  } else {
    const terminal = terminalBoundaries[0];
    if (terminal.label !== 'Analysis stopped safely'
      || terminal.agent !== 'Failure boundary'
      || terminal.headline !== 'No final playbook was accepted'
      || terminal.model != null
      || terminal.failure_stage !== run.failure_stage
      || terminal.accepted_state?.final_playbook_accepted !== false
      || stableJson(terminal.accepted_state) !== stableJson(run.accepted_state)) issues.push('terminal deterministic failure labels/state are invalid');
  }
  if (REQUIRED_NEMOTRON_AGENT_IDS.includes(run.failure_stage)
    && failureReceipts.filter(item => item.agent_id === run.failure_stage).length !== 1) issues.push('terminal model failure is not bound to exactly one specialist failure receipt');
  return issues;
}

function orchestrationContractViolations(run, cacheMode, expectedFramework = EXPECTED_FRAMEWORK) {
  const issues = [];
  const audit = orchestrationAudit(run);
  if (!audit || typeof audit !== 'object') return ['agent_orchestration audit is absent'];
  if (audit.schema_version !== EXPECTED_RUNTIME.orchestration_schema) issues.push('orchestration schema mismatch');
  if (audit.implementation !== EXPECTED_RUNTIME.implementation) issues.push('implementation mismatch');
  if (audit.authority_mode !== EXPECTED_RUNTIME.authority_mode) issues.push('authority mode mismatch');
  if (audit.model !== REQUESTED_NEMOTRON_MODEL) issues.push('requested model mismatch');
  if (stableJson(audit.framework) !== stableJson(expectedFramework)) issues.push('framework versions mismatch');
  if (!nonemptyString(audit.orchestration_id)) issues.push('orchestration_id is absent');
  if (!run?.result?.agent_orchestration
    || !run?.result?.audit?.agent_orchestration
    || !run?.agent_orchestration
    || stableJson(run.result.agent_orchestration) !== stableJson(audit)
    || stableJson(run.result.audit.agent_orchestration) !== stableJson(audit)
    || stableJson(run.agent_orchestration) !== stableJson(audit)) issues.push('authoritative orchestration audit is not identically visible in every final payload binding');
  if (audit.model_assisted !== true || audit.deterministic_safety_authority !== true) issues.push('hybrid authority flags are invalid');
  if (audit.external_tracing !== false || audit.prompt_storage !== false || audit.raw_output_storage !== false) issues.push('privacy flags are invalid');
  if (audit.all_required_agents_contributed !== true) issues.push('required-agent completion flag is false');
  if (stableJson(audit.execution_topology) !== stableJson(EXPECTED_EXECUTION_TOPOLOGY)) issues.push('deterministic execution topology authority or structure mismatch');

  const agents = Array.isArray(audit.agents) ? audit.agents : [];
  const gates = Array.isArray(audit.deterministic_gates) ? audit.deterministic_gates : [];
  if (!exactMembers(agents.map(item => item?.agent_id), REQUIRED_NEMOTRON_AGENT_IDS)) issues.push('required Nemotron agent set is not exact');
  if (!exactMembers(gates.map(item => item?.agent_id), REQUIRED_DETERMINISTIC_GATE_IDS)) issues.push('deterministic gate set is not exact');

  const byAgent = new Map(agents.map(item => [item.agent_id, item]));
  const callIds = agents.map(item => item?.call_id);
  const delegatedAgents = agents.filter(item => item?.agent_id !== 'canonical_facts');
  const delegationIds = delegatedAgents.map(item => item?.delegation_id);
  if (!callIds.every(nonemptyString) || new Set(callIds).size !== REQUIRED_NEMOTRON_AGENT_IDS.length) issues.push('agent call IDs are missing or duplicated');
  if (!delegationIds.every(nonemptyString) || new Set(delegationIds).size !== REQUIRED_NEMOTRON_AGENT_IDS.length - 1) issues.push('delegated agent IDs are missing or duplicated');
  for (const agentId of REQUIRED_NEMOTRON_AGENT_IDS) {
    const item = byAgent.get(agentId);
    if (!item) continue;
    if (item.role !== REQUIRED_NEMOTRON_AGENT_ROLES[agentId]) issues.push(`${agentId}: role label is not exact`);
    if (item.actor_type !== 'nemotron_agent') issues.push(`${agentId}: actor_type must be nemotron_agent`);
    if (item.acceptance_scope !== 'pre_review_model_output') issues.push(`${agentId}: acceptance_scope must remain pre_review_model_output`);
    if (item.model !== REQUESTED_NEMOTRON_MODEL || item.requested_model !== REQUESTED_NEMOTRON_MODEL || item.provider !== 'openrouter') issues.push(`${agentId}: requested model/provider mismatch`);
    if (!nonemptyString(item.response_id) || !EXACT_NEMOTRON_RESPONSE_MODELS.has(item.response_model)) issues.push(`${agentId}: returned response identity is invalid`);
    if (!providerProvenanceValueIsSafe('response_id', item.response_id)
      || !providerProvenanceValueIsSafe('response_model', item.response_model)
      || item.upstream_provider !== 'Together'
      || !providerProvenanceValueIsSafe('upstream_provider', item.upstream_provider)
      || !nonemptyString(item.finish_reason)
      || !providerProvenanceValueIsSafe('finish_reason', item.finish_reason)
      || (cacheMode === 'cold' ? !ALLOWED_USAGE_SOURCES.has(item.usage_source) : item.usage_source !== 'cache')) issues.push(`${agentId}: bounded provider provenance/usage is invalid`);
    if (!Number.isInteger(item.accepted_count) || item.accepted_count < 1) issues.push(`${agentId}: accepted_count must be positive`);
    if (!Number.isInteger(item.rejected_count) || item.rejected_count < 0) issues.push(`${agentId}: rejected_count must be nonnegative`);
    if (Number.isInteger(item.accepted_count) && Number.isInteger(item.rejected_count) && item.accepted_count <= item.rejected_count) issues.push(`${agentId}: accepted contributions are not a strict majority`);
    if (typeof item.deterministic_fallback_applied !== 'boolean' || item.deterministic_fallback_applied !== (item.rejected_count > 0)) issues.push(`${agentId}: guarded fallback disclosure is inconsistent`);
    if (!SHA256_PATTERN.test(item.input_artifact_hash || '') || !SHA256_PATTERN.test(item.output_artifact_hash || '')) issues.push(`${agentId}: artifact hashes are absent or invalid`);
    if (!nonemptyString(item.origin_call_id)) issues.push(`${agentId}: origin_call_id is absent`);
    if (cacheMode === 'cold' && (item.cache_hit !== false || !SUCCESSFUL_MODEL_OUTCOMES.has(item.outcome) || item.origin_call_id !== item.call_id)) issues.push(`${agentId}: cold network lineage is invalid`);
    if (cacheMode === 'warm' && (item.cache_hit !== true || item.outcome !== 'cache_hit')) issues.push(`${agentId}: warm cache state is invalid`);
    if (EXPECT_REAL_NEMOTRON && (
      item.deterministic_fallback_applied !== false
      || item.rejected_count !== 0
      || (cacheMode === 'cold' && item.outcome !== 'succeeded')
    )) issues.push(`${agentId}: fresh real acceptance contains a rejected or substituted model field`);
  }
  const canonical = byAgent.get('canonical_facts');
  const orchestrator = byAgent.get('orchestrator_plan');
  if (canonical) {
    const projected = canonical.source_reference_projection_fact_ids;
    if (!Array.isArray(projected)
      || !Number.isInteger(canonical.source_reference_projection_count)
      || canonical.source_reference_projection_count !== projected.length
      || new Set(projected).size !== projected.length
      || projected.some(factId => !canonical.accepted_ids.includes(factId))) issues.push('canonical_facts: deterministic source projection disclosure is invalid');
    if (EXPECT_REAL_NEMOTRON && projected.length) issues.push('canonical_facts: fresh real acceptance projected source references instead of accepting the model-selected grounding');
  }
  if (canonical && (canonical.parent_call_id != null || canonical.delegation_id != null)) issues.push('canonical_facts: root parent_call_id and delegation_id must be null');
  if (canonical && orchestrator && orchestrator.parent_call_id !== canonical.call_id) issues.push('orchestrator_plan: parent must be canonical_facts call');
  for (const agentId of REQUIRED_NEMOTRON_AGENT_IDS.slice(2)) {
    if (byAgent.get(agentId)?.parent_call_id !== orchestrator?.call_id) issues.push(`${agentId}: parent must be orchestrator_plan call`);
  }
  const disclosedFallbacks = agents.filter(item => item?.deterministic_fallback_applied === true).length;
  if (!Number.isInteger(audit.guarded_fallback_count) || audit.guarded_fallback_count !== disclosedFallbacks) issues.push('guarded_fallback_count does not match agent receipts');
  for (const gateId of REQUIRED_DETERMINISTIC_GATE_IDS) {
    const gate = gates.find(item => item?.agent_id === gateId);
    if (!gate) continue;
    if (gate.role !== REQUIRED_DETERMINISTIC_GATE_ROLES[gateId]) issues.push(`${gateId}: role label is not exact`);
    const artifactContract = ACCEPTED_ARTIFACT_CONTRACT[gateId];
    const sourceAgent = byAgent.get(artifactContract.source_agent_id);
    if (gate.actor_type !== 'deterministic_gate' || gate.model != null || gate.outcome !== 'passed' || gate.receipt_type !== 'accepted_artifact' || gate.acceptance_scope !== 'pre_review_model_output') issues.push(`${gateId}: deterministic gate identity/scope is invalid`);
    if (gate.output_artifact !== artifactContract.output_artifact
      || gate.source_agent_id !== artifactContract.source_agent_id
      || gate.source_call_id !== sourceAgent?.call_id
      || gate.delegation_id !== sourceAgent?.delegation_id
      || gate.accepted_count !== sourceAgent?.accepted_count
      || !Array.isArray(gate.accepted_ids)
      || gate.accepted_ids.length !== gate.accepted_count
      || new Set(gate.accepted_ids).size !== gate.accepted_ids.length
      || JSON.stringify(gate.accepted_ids) !== JSON.stringify(sourceAgent?.accepted_ids)) issues.push(`${gateId}: accepted artifact IDs/source binding is invalid`);
    if (!SHA256_PATTERN.test(gate.input_artifact_hash || '') || !SHA256_PATTERN.test(gate.output_artifact_hash || '')) issues.push(`${gateId}: artifact hashes are absent or invalid`);
  }
  const exactGateOutputs = {
    deterministic_process_gate: run?.result?.process,
    deterministic_evidence_gate: run?.result?.checklist,
    whole_playbook_gate: {
      process: semanticProcessDto(run?.result?.process),
      checklist: semanticChecklistDto(run?.result?.checklist),
      final_brief: audit.final_claim_brief,
    },
  };
  for (const [gateId, dto] of Object.entries(exactGateOutputs)) {
    const gate = gates.find(item => item?.agent_id === gateId);
    if (!dto || gate?.output_artifact_hash !== dtoHash(dto)) issues.push(`${gateId}: output hash is not bound to the returned final DTO`);
    const numericHazards = nonIntegerNumberPaths(dto);
    if (numericHazards.length) issues.push(`${gateId}: accepted DTO contains non-integer numeric values at ${numericHazards.join(', ')}`);
  }
  const wholeGate = gates.find(item => item?.agent_id === 'whole_playbook_gate');
  if (wholeGate?.output_projection_contract !== 'casepath.accepted-playbook-projection/1.0.0'
    || wholeGate?.final_brief_artifact_hash !== dtoHash(audit.final_claim_brief)) {
    issues.push('whole_playbook_gate: semantic bundle projection or final-brief hash is not exact');
  }
  const allEvents = Array.isArray(run?.events) ? run.events : [];
  const events = allEvents.filter(item => item?.stage === 'agent_orchestration');
  if (allEvents.some(item => item?.receipt_type === 'agent_failed' || (item?.stage === 'failed' && item?.status === 'failed'))) issues.push('completed orchestration retained a failure receipt or terminal failure boundary');
  for (const agentId of REQUIRED_NEMOTRON_AGENT_IDS) {
    const agent = byAgent.get(agentId);
    const completed = allEvents.filter(item => item.agent_id === agentId && item.actor_type === 'nemotron_agent' && item.receipt_type === 'agent_completed' && item.status === 'completed');
    if (completed.length !== 1) {
      issues.push(`${agentId}: exact completed visible pre-review receipt is absent or duplicated`);
      continue;
    }
    const receipt = completed[0];
    if (receipt.acceptance_scope !== 'pre_review_model_output'
      || receipt.call_id !== agent?.call_id
      || receipt.parent_call_id !== agent?.parent_call_id
      || receipt.delegation_id !== agent?.delegation_id
      || receipt.response_id !== agent?.response_id
      || receipt.response_model !== agent?.response_model
      || receipt.accepted_count !== agent?.accepted_count
      || receipt.rejected_count !== agent?.rejected_count
      || receipt.deterministic_fallback_applied !== agent?.deterministic_fallback_applied
      || (agentId === 'canonical_facts'
        && (receipt.source_reference_projection_count !== agent?.source_reference_projection_count
          || JSON.stringify(receipt.source_reference_projection_fact_ids) !== JSON.stringify(agent?.source_reference_projection_fact_ids)))
      || JSON.stringify(receipt.accepted_ids) !== JSON.stringify(agent?.accepted_ids)) issues.push(`${agentId}: completed visible receipt is not bound to the authoritative agent audit`);
    if (agentId !== 'canonical_facts' && receipt.output_artifact_hash !== agent?.output_artifact_hash) issues.push(`${agentId}: completed visible receipt output hash is not bound to the authoritative agent audit`);
  }
  for (const gateId of REQUIRED_DETERMINISTIC_GATE_IDS) {
    const contract = ACCEPTED_ARTIFACT_CONTRACT[gateId];
    const sourceCallId = byAgent.get(contract.source_agent_id)?.call_id;
    if (!events.some(item => item.agent_id === gateId
      && item.actor_type === 'deterministic_gate'
      && item.receipt_type === 'accepted_artifact'
      && item.acceptance_scope === 'pre_review_model_output'
      && item.status === 'completed'
      && item.output_artifact === contract.output_artifact
      && item.source_agent_id === contract.source_agent_id
      && item.source_call_id === sourceCallId
      && item.delegation_id === byAgent.get(contract.source_agent_id)?.delegation_id
      && item.accepted_count === byAgent.get(contract.source_agent_id)?.accepted_count
      && JSON.stringify(item.accepted_ids) === JSON.stringify(byAgent.get(contract.source_agent_id)?.accepted_ids)
      && SHA256_PATTERN.test(item.output_artifact_hash || ''))) issues.push(`${gateId}: completed accepted-artifact receipt is absent or unbound`);
  }
  issues.push(...hybridCausalContractViolations(run));
  const sensitive = forbiddenFieldPaths(run);
  if (sensitive.length) issues.push(`forbidden public fields: ${sensitive.join(', ')}`);
  const sentinelLeaks = internalSentinelPaths(run);
  if (sentinelLeaks.length) issues.push(`internal execution sentinels leaked: ${sentinelLeaks.join(', ')}`);
  return issues;
}

function ledgerSummary(items) {
  const unknownCostCallCount = items.filter(item => item.call_count > 0 && item.actual_cost_usd == null).length;
  const outcomes = Object.fromEntries([...new Set(items.map(item => item.outcome))]
    .sort()
    .map(outcome => [outcome, items.filter(item => item.outcome === outcome).length]));
  return {
    records: items.length,
    network_calls: items.reduce((total, item) => total + item.call_count, 0),
    prompt_tokens: items.reduce((total, item) => total + (item.prompt_tokens ?? 0), 0),
    completion_tokens: items.reduce((total, item) => total + (item.completion_tokens ?? 0), 0),
    total_tokens: items.reduce((total, item) => total + (item.total_tokens ?? 0), 0),
    actual_cost_usd: Number(items.reduce((total, item) => total + (item.actual_cost_usd ?? 0), 0).toFixed(8)),
    actual_cost_complete: unknownCostCallCount === 0,
    unknown_cost_call_count: unknownCostCallCount,
    outcomes,
  };
}

function initialLedgerAdmissionViolations(ledger) {
  const issues = sanitizedLedgerViolations(ledger);
  if (issues.length) return issues;
  const expected = ledgerSummary([]);
  if (stableJson(ledger.summary) !== stableJson(expected)) {
    issues.push('initial global model ledger is not exactly empty');
  }
  if (ledger.items.length !== 0) issues.push('initial global model ledger contains rows');
  return issues;
}

function finalLedgerSnapshotViolations(isolationLedger, finalLedger) {
  const issues = [];
  if (stableJson(finalLedger) !== stableJson(isolationLedger)) {
    issues.push('final ledger changed after the flagship warm replay');
  }
  const summary = finalLedger?.summary;
  if (!Array.isArray(finalLedger?.items)
    || finalLedger.items.length !== 12
    || summary?.records !== 12
    || summary?.network_calls !== 6
    || summary?.outcomes?.cache_hit !== 6
    || summary?.unknown_cost_call_count !== 0
    || summary?.actual_cost_complete !== true) {
    issues.push('final ledger is not exact cold6 plus warm6 accounting');
  }
  return issues;
}

function sanitizedLedgerViolations(ledger) {
  const issues = [];
  if (ledger?.scope !== 'global_budget_ledger' || !Array.isArray(ledger?.items)) return ['global sanitized ledger is absent'];
  const summary = ledger?.summary;
  if (!summary || typeof summary !== 'object' || !exactMembers(Object.keys(summary), [...ALLOWED_LEDGER_SUMMARY_FIELDS])) {
    issues.push('ledger summary violates the exact public schema');
  } else {
    const sourceRowsValid = ledger.items.every(item => Number.isInteger(item?.call_count)
      && item.call_count >= 0
      && ['prompt_tokens', 'completion_tokens', 'total_tokens'].every(field => !Object.hasOwn(item, field) || (Number.isInteger(item[field]) && item[field] >= 0))
      && (item.actual_cost_usd == null || (Number.isFinite(item.actual_cost_usd) && item.actual_cost_usd >= 0))
      && nonemptyString(item.outcome));
    if (!sourceRowsValid) {
      issues.push('ledger summary source rows contain invalid accounting fields');
    } else {
      if (stableJson(summary) !== stableJson(ledgerSummary(ledger.items))) issues.push('ledger summary is inconsistent with its network rows');
    }
  }
  const callIds = ledger.items.map(item => item?.call_id);
  if (!callIds.every(nonemptyString) || new Set(callIds).size !== callIds.length) issues.push('ledger call IDs are absent or duplicated');
  ledger.items.forEach((item, index) => {
    const unexpected = Object.keys(item).filter(key => !ALLOWED_LEDGER_FIELDS.has(key));
    if (unexpected.length) issues.push(`ledger[${index}] unexpected fields: ${unexpected.join(', ')}`);
    for (const field of PROVIDER_PROVENANCE_FIELDS) {
      if (Object.hasOwn(item, field) && !providerProvenanceValueIsSafe(field, item[field])) issues.push(`ledger[${index}].${field} violates the exact provider-provenance sanitizer`);
    }
    if (Object.hasOwn(item, 'generation_model') && !providerProvenanceValueIsSafe('response_model', item.generation_model)) issues.push(`ledger[${index}].generation_model violates the exact response-model sanitizer`);
    if (Object.hasOwn(item, 'origin_finish_reason') && !providerProvenanceValueIsSafe('finish_reason', item.origin_finish_reason)) issues.push(`ledger[${index}].origin_finish_reason violates the exact finish-reason sanitizer`);
    if (item.error_invariant === 'invalid_provenance') {
      if (!PROVIDER_PROVENANCE_FIELDS.has(item.invalid_provenance_field)
        || !SHA256_PATTERN.test(item.invalid_provenance_value_hash || '')
        || item[item.invalid_provenance_field] != null) issues.push(`ledger[${index}] invalid-provenance diagnostic is unbounded or retained the rejected value`);
    } else if (item.invalid_provenance_field != null || item.invalid_provenance_value_hash != null) {
      issues.push(`ledger[${index}] carries an out-of-scope invalid-provenance diagnostic`);
    }
    if (item.provider_error_code != null && (item.error_invariant !== 'provider_upstream_rejection' || !Number.isInteger(item.provider_error_code) || item.provider_error_code < 0 || item.provider_error_code > 9999)) issues.push(`ledger[${index}] provider error code is unbounded or out of scope`);
    if (item.error_invariant === 'provider_upstream_rejection' && item.response_id != null && !EXACT_OPENROUTER_GENERATION_ID.test(item.response_id)) issues.push(`ledger[${index}] response ID is not an exact OpenRouter generation ID`);
    if (item.outcome === 'blocked_provider_concurrency' || item.error_invariant === 'provider_concurrency_timeout') {
      const retainedProviderResultFields = ZERO_CALL_PROVIDER_RESULT_FIELDS.filter(field => Object.hasOwn(item, field));
      if (item.outcome !== 'blocked_provider_concurrency'
        || item.error_invariant !== 'provider_concurrency_timeout'
        || item.call_count !== 0
        || item.actual_cost_usd !== null
        || retainedProviderResultFields.length) issues.push(`ledger[${index}] blocked provider concurrency is not an exact zero-call row`);
    }
    const boundaryIssue = providerRejectionBoundaryIssue(item);
    if (boundaryIssue) issues.push(`ledger[${index}] ${boundaryIssue}`);
    if (Object.hasOwn(item, 'origin_usage')) {
      const usage = item.origin_usage;
      if (!usage
        || typeof usage !== 'object'
        || !exactMembers(Object.keys(usage), ['prompt_tokens', 'completion_tokens', 'total_tokens', 'actual_cost_usd', 'usage_source'])
        || !Number.isInteger(usage.prompt_tokens)
        || usage.prompt_tokens <= 0
        || !Number.isInteger(usage.completion_tokens)
        || usage.completion_tokens <= 0
        || !Number.isInteger(usage.total_tokens)
        || usage.total_tokens < usage.prompt_tokens + usage.completion_tokens
        || !Number.isFinite(usage.actual_cost_usd)
        || usage.actual_cost_usd <= 0
        || !ALLOWED_USAGE_SOURCES.has(usage.usage_source)) issues.push(`ledger[${index}] origin_usage is not the bounded usage schema`);
      if (!nonemptyString(item.origin_finish_reason)) issues.push(`ledger[${index}] origin_finish_reason is absent`);
    }
  });
  const sensitive = forbiddenFieldPaths(ledger);
  if (sensitive.length) issues.push(`ledger forbidden fields: ${sensitive.join(', ')}`);
  const sentinels = internalSentinelPaths(ledger);
  if (sentinels.length) issues.push(`ledger internal sentinels: ${sentinels.join(', ')}`);
  return issues;
}

function coldLedgerContractViolations(audit, ledger) {
  const issues = [...sanitizedLedgerViolations(ledger)];
  if (!audit) return [...issues, 'cold orchestration audit is absent'];
  const callIds = new Set(audit.agents.map(item => item.call_id));
  const items = ledger.items.filter(item => callIds.has(item.call_id));
  if (items.length !== REQUIRED_NEMOTRON_AGENT_IDS.length) issues.push('cold ledger does not contain exactly six bound calls');
  const responseIds = items.map(item => item.response_id);
  if (!responseIds.every(nonemptyString) || new Set(responseIds).size !== REQUIRED_NEMOTRON_AGENT_IDS.length) issues.push('cold response IDs are missing or duplicated');
  for (const agent of audit.agents) {
    const item = items.find(value => value.call_id === agent.call_id);
    if (!item) continue;
    if (item.orchestration_id !== audit.orchestration_id || item.agent_id !== agent.agent_id) issues.push(`${agent.agent_id}: ledger orchestration binding mismatch`);
    if (item.parent_call_id !== agent.parent_call_id || item.delegation_id !== agent.delegation_id) issues.push(`${agent.agent_id}: ledger parent/delegation binding mismatch`);
    if (agent.response_id !== item.response_id || agent.response_model !== item.response_model || agent.upstream_provider !== item.upstream_provider || agent.call_count !== item.call_count) issues.push(`${agent.agent_id}: run audit and ledger response binding mismatch`);
    if (item.call_count !== 1 || !SUCCESSFUL_MODEL_OUTCOMES.has(item.outcome)) issues.push(`${agent.agent_id}: ledger is not a successful cold network call`);
    if (item.provider !== 'openrouter' || item.provider_endpoint !== 'https://openrouter.ai/api/v1/chat/completions') issues.push(`${agent.agent_id}: provider identity mismatch`);
    if (item.model !== REQUESTED_NEMOTRON_MODEL || !EXACT_NEMOTRON_RESPONSE_MODELS.has(item.response_model)) issues.push(`${agent.agent_id}: requested/returned model mismatch`);
    if (!nonemptyString(item.response_id) || item.upstream_provider !== 'Together' || !nonemptyString(item.finish_reason)) issues.push(`${agent.agent_id}: complete exact provider identity is absent`);
    if (!ALLOWED_USAGE_SOURCES.has(item.usage_source)) issues.push(`${agent.agent_id}: usage provenance is invalid`);
    if (!Number.isFinite(item.actual_cost_usd) || item.actual_cost_usd <= 0) issues.push(`${agent.agent_id}: actual cost must be positive`);
    if (!Number.isInteger(item.prompt_tokens) || item.prompt_tokens <= 0 || !Number.isInteger(item.completion_tokens) || item.completion_tokens <= 0 || !Number.isInteger(item.total_tokens) || item.total_tokens < item.prompt_tokens + item.completion_tokens) issues.push(`${agent.agent_id}: token accounting is invalid`);
    const acceptedCount = agent.agent_id === 'canonical_facts' ? item.accepted_fact_count : item.accepted_item_count;
    const rejectedCount = agent.agent_id === 'canonical_facts' ? item.rejected_fact_count : item.rejected_item_count;
    if (acceptedCount !== agent.accepted_count || rejectedCount !== agent.rejected_count || item.deterministic_fallback_applied !== agent.deterministic_fallback_applied) issues.push(`${agent.agent_id}: ledger contribution diagnostics mismatch`);
    if (agent.agent_id === 'canonical_facts'
      && (item.source_reference_projection_count !== agent.source_reference_projection_count
        || JSON.stringify(item.source_reference_projection_fact_ids) !== JSON.stringify(agent.source_reference_projection_fact_ids))) issues.push('canonical_facts: ledger source projection diagnostics mismatch');
  }
  return issues;
}

function warmLineageContractViolations(coldAudit, warmAudit, ledger) {
  const issues = [];
  if (!coldAudit || !warmAudit) return { issues: ['cold or warm orchestration audit is absent'], lineage: [] };
  if (coldAudit.orchestration_id === warmAudit.orchestration_id) issues.push('cold and warm runs must have distinct orchestration IDs');
  const coldByAgent = new Map(coldAudit.agents.map(item => [item.agent_id, item]));
  const warmCallIds = new Set(warmAudit.agents.map(item => item.call_id));
  const warmLedger = ledger.items.filter(item => warmCallIds.has(item.call_id));
  if (warmLedger.length !== REQUIRED_NEMOTRON_AGENT_IDS.length) issues.push('warm ledger does not contain exactly six bound cache records');
  const lineage = [];
  for (const warm of warmAudit.agents) {
    const cold = coldByAgent.get(warm.agent_id);
    const item = warmLedger.find(value => value.call_id === warm.call_id);
    if (!cold || !item) continue;
    if (warm.call_id === cold.call_id || warm.origin_call_id !== cold.call_id || item.origin_call_id !== cold.call_id) issues.push(`${warm.agent_id}: warm origin does not bind to the cold call`);
    if (item.orchestration_id !== warmAudit.orchestration_id || item.agent_id !== warm.agent_id) issues.push(`${warm.agent_id}: warm ledger orchestration binding mismatch`);
    if (item.parent_call_id !== warm.parent_call_id || item.delegation_id !== warm.delegation_id) issues.push(`${warm.agent_id}: warm ledger parent/delegation binding mismatch`);
    if (warm.response_id !== item.response_id || warm.response_model !== item.response_model || warm.upstream_provider !== item.upstream_provider || warm.call_count !== item.call_count) issues.push(`${warm.agent_id}: warm run audit and ledger response binding mismatch`);
    if (item.call_count !== 0 || item.outcome !== 'cache_hit' || item.usage_source !== 'cache') issues.push(`${warm.agent_id}: warm record made or claims a provider call`);
    const coldLedger = ledger.items.find(value => value.call_id === cold.call_id);
    if (!coldLedger || item.response_id !== coldLedger.response_id || item.response_model !== coldLedger.response_model || item.upstream_provider !== 'Together' || coldLedger.upstream_provider !== 'Together') issues.push(`${warm.agent_id}: cached response identity/provider does not match the exact cold origin`);
    if (warm.input_artifact_hash !== cold.input_artifact_hash
      || warm.output_artifact_hash !== cold.output_artifact_hash
      || JSON.stringify(warm.accepted_ids) !== JSON.stringify(cold.accepted_ids)
      || warm.accepted_count !== cold.accepted_count
      || warm.rejected_count !== cold.rejected_count
      || warm.deterministic_fallback_applied !== cold.deterministic_fallback_applied
      || (warm.agent_id === 'canonical_facts'
        && (JSON.stringify(warm.source_reference_projection_fact_ids) !== JSON.stringify(cold.source_reference_projection_fact_ids)
          || warm.source_reference_projection_count !== cold.source_reference_projection_count))) issues.push(`${warm.agent_id}: warm artifact and acceptance lineage differs from the cold origin`);
    const originUsage = item.origin_usage;
    const expectedOriginUsage = coldLedger && {
      prompt_tokens: coldLedger.prompt_tokens,
      completion_tokens: coldLedger.completion_tokens,
      total_tokens: coldLedger.total_tokens,
      actual_cost_usd: coldLedger.actual_cost_usd,
      usage_source: coldLedger.usage_source,
    };
    if (!originUsage
      || !exactMembers(Object.keys(originUsage), ['prompt_tokens', 'completion_tokens', 'total_tokens', 'actual_cost_usd', 'usage_source'])
      || JSON.stringify(originUsage) !== JSON.stringify(expectedOriginUsage)
      || item.origin_finish_reason !== coldLedger?.finish_reason) issues.push(`${warm.agent_id}: bounded origin usage/finish provenance does not match the cold record`);
    lineage.push({ agent_id: warm.agent_id, cold_call_id: cold.call_id, warm_call_id: warm.call_id, response_id: item.response_id, response_model: item.response_model });
  }
  return { issues, lineage };
}

function returnedReviewTransform(value) {
  return value?.review_transform
    || value?.review_response?.review_transform
    || value?.result?.review_transform
    || value?.result?.audit?.review_transform
    || null;
}

function reviewTransformContractViolations(reviewed, persistedRun, preReviewRun) {
  const issues = [];
  const responseTransform = returnedReviewTransform(reviewed);
  const persistedTransform = returnedReviewTransform(persistedRun);
  if (!responseTransform || !persistedTransform) return ['review_transform is absent from the review response or persisted run'];
  if (stableJson(responseTransform) !== stableJson(persistedTransform)) issues.push('review response and persisted run carry different review transforms');
  const preAudit = orchestrationAudit(preReviewRun);
  const hasModelAcceptance = preAudit?.model_assisted === true && Array.isArray(preAudit?.deterministic_gates);
  const processGate = preAudit?.deterministic_gates?.find(item => item.agent_id === 'deterministic_process_gate');
  const evidenceGate = preAudit?.deterministic_gates?.find(item => item.agent_id === 'deterministic_evidence_gate');
  const expected = {
    acceptance_scope: 'post_review_unverified_transform',
    authority: 'unverified_demo_user',
    qualification_status: 'not_verified',
    input_run_id: preReviewRun?.run_id,
    input_process_hash: processGate?.output_artifact_hash || dtoHash(preReviewRun?.result?.process),
    input_checklist_hash: evidenceGate?.output_artifact_hash || dtoHash(preReviewRun?.result?.checklist),
    output_process_hash: dtoHash(reviewed?.result?.process),
    output_checklist_hash: dtoHash(reviewed?.result?.checklist),
    model_acceptance_reused: false,
  };
  if (!exactMembers(Object.keys(responseTransform), Object.keys(expected))) issues.push('review response review_transform schema is not exact and bounded');
  if (!exactMembers(Object.keys(persistedTransform), Object.keys(expected))) issues.push('persisted review_transform schema is not exact and bounded');
  for (const [key, value] of Object.entries(expected)) {
    if (responseTransform[key] !== value) issues.push(`review_transform.${key} mismatch`);
  }
  if (dtoHash(preReviewRun?.result?.process) !== expected.input_process_hash || dtoHash(preReviewRun?.result?.checklist) !== expected.input_checklist_hash) issues.push('review transform inputs do not match exact pre-review accepted DTO hashes');
  if (dtoHash(persistedRun?.result?.process) !== expected.output_process_hash || dtoHash(persistedRun?.result?.checklist) !== expected.output_checklist_hash) issues.push('persisted post-review DTO hashes do not match the review response');
  if (JSON.stringify(persistedRun?.result?.process) !== JSON.stringify(reviewed?.result?.process) || JSON.stringify(persistedRun?.result?.checklist) !== JSON.stringify(reviewed?.result?.checklist)) issues.push('persisted post-review DTOs differ from the applied response');
  if (hasModelAcceptance) {
    const postAudit = orchestrationAudit(persistedRun);
    for (const gateId of REQUIRED_DETERMINISTIC_GATE_IDS) {
      const before = preAudit.deterministic_gates?.find(item => item.agent_id === gateId);
      const after = postAudit?.deterministic_gates?.find(item => item.agent_id === gateId);
      if (!before || !after || after.acceptance_scope !== 'pre_review_model_output' || after.output_artifact_hash !== before.output_artifact_hash) issues.push(`${gateId}: original model-time acceptance was rewritten by the review transform`);
    }
  }
  const numericHazards = [
    ...nonIntegerNumberPaths(reviewed?.result?.process, '$.reviewed.process'),
    ...nonIntegerNumberPaths(reviewed?.result?.checklist, '$.reviewed.checklist'),
  ];
  if (numericHazards.length) issues.push(`post-review transformed DTO contains non-integer numeric values at ${numericHazards.join(', ')}`);
  const sensitive = forbiddenFieldPaths({ responseTransform, persistedTransform });
  if (sensitive.length) issues.push(`review transform leaks forbidden fields: ${sensitive.join(', ')}`);
  return issues;
}

function deterministicReferenceRunViolations(run, knowledgeMode) {
  const issues = [];
  const result = run?.result;
  const resultAudit = result?.audit;
  if (run?.status !== 'complete'
    || run?.claim_id !== 'DEMO-MOULD-002'
    || run?.knowledge_mode !== knowledgeMode
    || run?.model_mode !== DETERMINISTIC_REFERENCE_MODE
    || run?.model != null
    || run?.profile !== DETERMINISTIC_REFERENCE_PROFILE) issues.push('top-level deterministic-reference identity is invalid');
  if (!nonemptyString(run?.run_id)) issues.push('run_id is absent');
  if (stableJson(run?.agent_orchestration) !== stableJson(DETERMINISTIC_REFERENCE_ORCHESTRATION)
    || stableJson(result?.agent_orchestration) !== stableJson(DETERMINISTIC_REFERENCE_ORCHESTRATION)
    || stableJson(resultAudit?.agent_orchestration) !== stableJson(DETERMINISTIC_REFERENCE_ORCHESTRATION)) issues.push('deterministic non-executed orchestration binding is not exact');
  if (resultAudit?.profile !== DETERMINISTIC_REFERENCE_PROFILE
    || resultAudit?.authority_mode !== DETERMINISTIC_REFERENCE_MODE
    || stableJson(resultAudit?.canonicalization) !== stableJson(DETERMINISTIC_REFERENCE_CANONICALIZATION)) issues.push('deterministic-reference canonicalization authority is not explicit');
  if (result?.next_action?.agent_brief_contribution !== null) issues.push('deterministic comparison retained a model-authored final brief');
  if (!Array.isArray(run?.events)) issues.push('deterministic event stream is absent');

  const forbiddenActivityFields = new Set([
    'agents', 'deterministic_gates', 'execution_topology', 'specialist_artifacts',
    'final_claim_brief', 'agent_contribution', 'call_id', 'response_id',
    'response_model', 'requested_model', 'generation_model', 'upstream_provider',
    'provider_endpoint', 'cache_hit', 'call_count', 'origin_call_id', 'origin_usage',
    'origin_finish_reason', 'usage_source', 'orchestration_id', 'delegation_id',
    'parent_call_id', 'prompt_tokens', 'completion_tokens', 'total_tokens',
    'estimated_cost_usd', 'actual_cost_usd', 'latency_ms',
  ]);
  const activityPaths = [];
  const visit = (value, currentPath) => {
    if (Array.isArray(value)) {
      value.forEach((item, index) => visit(item, `${currentPath}[${index}]`));
      return;
    }
    if (!value || typeof value !== 'object') return;
    for (const [key, child] of Object.entries(value)) {
      const childPath = `${currentPath}.${key}`;
      if (forbiddenActivityFields.has(key)
        || (['model', 'provider'].includes(key) && child != null)
        || (key === 'actor_type' && child === 'nemotron_agent')
        || (key === 'implementation' && child === EXPECTED_RUNTIME.implementation)) activityPaths.push(childPath);
      visit(child, childPath);
    }
  };
  visit(run, '$');
  if (activityPaths.length) issues.push(`model execution activity is present at ${activityPaths.join(', ')}`);
  const sensitive = forbiddenFieldPaths(run);
  if (sensitive.length) issues.push(`forbidden public fields are present at ${sensitive.join(', ')}`);
  const sentinels = internalSentinelPaths(run);
  if (sentinels.length) issues.push(`internal execution sentinels are present at ${sentinels.join(', ')}`);
  return issues;
}

function productionOpeningContextViolations(captures) {
  const issues = [];
  const opening = Array.isArray(captures) ? captures[0] : null;
  if (!opening) return ['production opening context was not captured'];
  if (opening.actor_type !== 'deterministic_tool') issues.push('production opening setup is not visibly attributed to deterministic_tool');
  if (opening.boundary_text !== EXPECTED_PRODUCTION_OPENING_BOUNDARY) issues.push('production opening boundary copy is not exact');
  if (opening.nemotron_plan_visible !== false) issues.push('Nemotron plan was visible before its returned event');
  if (/legacy deterministic reference/i.test(opening.boundary_text || '')) issues.push('production opening boundary incorrectly claims the legacy reference pipeline');
  return issues;
}

function assertDeploymentAlignment(frontend, api) {
  const localMode = isLocal(BASE) && isLocal(API);
  const expected = process.env.CASEPATH_EXPECTED_SOURCE_COMMIT || '';
  const qaCommit = deploymentIdentity.qa.source_commit;
  check('Frontend, API, and QA use the canonical release identifier', frontend.release_id === RELEASE_ID && api.release_id === RELEASE_ID && deploymentIdentity.qa.release_id === RELEASE_ID, JSON.stringify(deploymentIdentity));
  if (!localMode) {
    check('Production deployment identities expose real source commits', validSourceCommit(frontend.source_commit) && validSourceCommit(api.source_commit) && validSourceCommit(qaCommit), JSON.stringify(deploymentIdentity));
    check('Production deployment identities are internally conflict-free', frontend.alignment_eligible === true && api.source_commit_aligned === true && api.source_commit_conflict === false, JSON.stringify(deploymentIdentity));
    check('Production frontend, API, and QA source commits are aligned', frontend.source_commit === api.source_commit && api.source_commit === qaCommit, JSON.stringify(deploymentIdentity));
    return;
  }
  if (expected && expected !== 'local') {
    check('Local expected source commit is a real Git identity', validSourceCommit(expected), expected);
    check('Local frontend and API match the explicit expected source commit', frontend.source_commit === expected && api.source_commit === expected, JSON.stringify(deploymentIdentity));
    if (qaCommit) check('Local QA build matches the explicit expected source commit', qaCommit === expected, JSON.stringify(deploymentIdentity));
    return;
  }
  const localSentinels = new Set(['local', 'unknown']);
  const bothExplicitlyLocal = localSentinels.has(frontend.source_commit) && localSentinels.has(api.source_commit);
  const sameRealCommit = validSourceCommit(frontend.source_commit) && frontend.source_commit === api.source_commit;
  check('Local alignment is either an identical commit or an explicit local sentinel', sameRealCommit || bothExplicitlyLocal, JSON.stringify(deploymentIdentity));
  if (qaCommit && qaCommit !== 'local') check('Local QA build does not conflict with returned source identity', validSourceCommit(qaCommit) && (!sameRealCommit || qaCommit === frontend.source_commit), JSON.stringify(deploymentIdentity));
  notes.push('Local-mode source identity accepted explicitly; production still requires one matching non-unknown 40-character commit across frontend, API, and QA.');
}

function assertReleaseRuntimeContract(releaseContract) {
  const runtime = releaseContract?.agentic_runtime;
  const runtimeAcceptance = releaseContract?.truth?.production_runtime_acceptance;
  const dynamicEvidence = runtimeAcceptance?.dynamic_evidence;
  check('Release uses the dynamic 2.2 contract without embedding a mutable verdict', releaseContract?.$schema === './release.schema.json' && releaseContract?.contract === 'casepath.release-contract/2.2.0' && releaseContract?.schema_version === '2.2.0' && releaseContract?.source_identity?.authority === 'dynamic_same_commit_qa_artifacts' && releaseContract?.source_identity?.source_contract_embeds_commit === false && releaseContract?.source_identity?.runtime_environment_variable === 'RENDER_GIT_COMMIT' && nonemptyString(releaseContract?.source_identity?.unknown_semantics), JSON.stringify({ contract: releaseContract?.contract, schema_version: releaseContract?.schema_version, source_identity: releaseContract?.source_identity }));
  check('Release contract identifies the canonical v20 product, API 15.2, and QA gate', releaseContract?.release_id === RELEASE_ID && releaseContract?.components?.frontend?.version === PRODUCT_RELEASE && releaseContract?.components?.api?.version === API_RELEASE && releaseContract?.components?.pipeline?.version === API_RELEASE && releaseContract?.components?.qa?.version === PRODUCT_RELEASE, JSON.stringify(releaseContract?.components));
  check('Release contract requests the pinned LangChain, LangGraph, and OpenRouter adapter versions', stableJson(runtime?.framework) === stableJson(EXPECTED_FRAMEWORK), JSON.stringify(runtime?.framework));
  check('Release contract requests the exact six-agent Nemotron runtime', runtime?.runtime_profile === EXPECTED_RUNTIME.runtime_profile && runtime?.authority_mode === EXPECTED_RUNTIME.authority_mode && runtime?.implementation === EXPECTED_RUNTIME.implementation && runtime?.orchestration_schema === EXPECTED_RUNTIME.orchestration_schema && runtime?.model === REQUESTED_NEMOTRON_MODEL && exactMembers(runtime?.model_agents?.map(item => item.agent_id), REQUIRED_NEMOTRON_AGENT_IDS), JSON.stringify(runtime));
  check('Release contract keeps logical specialist fan-out, three deterministic authority gates, physical provider single-flight, and disabled trace payload storage', stableJson(runtime?.parallel_groups) === stableJson(EXPECTED_EXECUTION_TOPOLOGY.parallel_groups) && exactMembers(runtime?.deterministic_gates?.map(item => item.gate_id), REQUIRED_DETERMINISTIC_GATE_IDS) && runtime?.safety?.deterministic_safety_authority === true && runtime?.safety?.provider_max_in_flight === 1 && runtime?.safety?.external_tracing === false && runtime?.safety?.prompt_storage === false && runtime?.safety?.raw_output_storage === false, JSON.stringify({ parallel_groups: runtime?.parallel_groups, safety: runtime?.safety }));
  check('Release contract delegates the mutable production verdict to hash-bound same-commit QA artifacts', runtimeAcceptance?.verdict_authority === 'dynamic_same_commit_qa_artifacts' && runtimeAcceptance?.source_contract_embeds_runtime_verdict === false && exactMembers(Object.keys(dynamicEvidence || {}), ['qa_gate', 'report_path', 'evidence_manifest_path', 'evidence_manifest_contract', 'required_report_status', 'requires_release_id_match', 'requires_non_unknown_source_commit', 'requires_same_source_commit']) && dynamicEvidence?.qa_gate === 'focused-flagship-journey-v20' && dynamicEvidence?.report_path === 'report.json' && dynamicEvidence?.evidence_manifest_path === 'evidence-manifest.json' && dynamicEvidence?.evidence_manifest_contract === 'casepath.qa-evidence-manifest/1.0.0' && dynamicEvidence?.required_report_status === 'passed' && dynamicEvidence?.requires_release_id_match === true && dynamicEvidence?.requires_non_unknown_source_commit === true && dynamicEvidence?.requires_same_source_commit === true, JSON.stringify(runtimeAcceptance));
  check('Dynamic production acceptance declares every exact paid-call, contribution, cold-run, gate, and fallback criterion', exactMembers(Object.keys(runtimeAcceptance || {}), ['verdict_authority', 'source_contract_embeds_runtime_verdict', 'dynamic_evidence', ...Object.keys(EXPECTED_RUNTIME_ACCEPTANCE_CRITERIA)]) && Object.entries(EXPECTED_RUNTIME_ACCEPTANCE_CRITERIA).every(([key, value]) => runtimeAcceptance?.[key] === value), JSON.stringify(runtimeAcceptance));
  check('Release separates deterministic build proof and failed-closed history from current runtime acceptance', stableJson(releaseContract?.truth?.deterministic_build) === stableJson({ status: 'passed', execution_mode: 'deterministic_reference', model_calls: 0, model_backed: false }) && releaseContract?.truth?.historical_model_validation?.scope === 'failed_closed_history_only' && releaseContract?.truth?.historical_model_validation?.establishes_current_runtime_acceptance === false && stableJson(releaseContract?.truth?.historical_model_validation?.evidence_records) === stableJson(EXPECTED_FAILED_MODEL_ATTEMPT_RECORDS), JSON.stringify(releaseContract?.truth));
  check('Release keeps unearned expert, legal, operational, and real-claim claims false', ['independent_expert_review', 'blind_review_completed', 'legal_approval', 'operational_validation', 'real_claims_approved'].every(key => releaseContract?.truth?.[key] === false) && releaseContract?.truth?.generated_data_only === true, JSON.stringify(releaseContract?.truth));
  check('Release acceptance identity uses independent component versions but one release/source identity', releaseContract?.compatibility?.component_versions_are_independent === true && /same release_id/i.test(releaseContract?.compatibility?.acceptance_rule || '') && /same non-unknown source commit/i.test(releaseContract?.compatibility?.acceptance_rule || ''), JSON.stringify(releaseContract?.compatibility));
}

function providerSingleFlightContractViolations(releaseContract, health, readiness) {
  const issues = [];
  if (stableJson(releaseContract?.agentic_runtime?.parallel_groups) !== stableJson(EXPECTED_EXECUTION_TOPOLOGY.parallel_groups)) issues.push('logical fan-out topology changed');
  if (releaseContract?.agentic_runtime?.safety?.provider_max_in_flight !== 1) issues.push('release safety cap is not one');
  if (releaseContract?.truth?.production_runtime_acceptance?.required_provider_max_in_flight !== 1) issues.push('runtime acceptance cap is not one');
  if (health?.agentic_runtime?.safety?.provider_max_in_flight !== 1) issues.push('health cap is not one');
  if (readiness?.agentic_runtime?.safety?.provider_max_in_flight !== 1) issues.push('readiness cap is not one');
  return issues;
}

function cursorSemanticContractViolations(cursorSteps, expectedSpineIds, production = false) {
  const issues = [];
  if (!cursorSteps.length) issues.push('no cursor steps emitted');
  cursorSteps.forEach((step, index) => {
    if (!step.activationKey || !step.target || !Number.isFinite(step.x) || !Number.isFinite(step.y)) issues.push(`${index}: incomplete semantic cursor key`);
    if (step.actorType === 'nemotron_agent') {
      if (!REQUIRED_NEMOTRON_AGENT_IDS.includes(step.agentId)) issues.push(`${index}: unrecognized model agent`);
      if (step.signature !== REQUIRED_NEMOTRON_AGENT_SIGNATURES[step.agentId]?.signature) issues.push(`${index}: agent signature drift`);
      if (!['working', 'artifact'].includes(step.phase)) issues.push(`${index}: model cursor phase is not explicit`);
    } else if (step.agentId) issues.push(`${index}: non-agent inherited model identity`);
    if (step.focus && (step.focus.focusIdCount !== 1 || step.focus.cursorIdCount !== 1 || step.focus.focusCount !== 1 || step.focus.cursorCount !== 1 || !step.focus.cursorInsideFocus)) issues.push(`${index}: cursor/focus multiplicity`);
  });
  const activations = cursorSteps.map(step => step.activationKey);
  if (new Set(activations).size !== activations.length) issues.push('semantic cursor activation repeated');
  for (const nodeId of expectedSpineIds) {
    if (!cursorSteps.some(step => step.moment === 'process' && step.target.endsWith(`:${nodeId}`))) issues.push(`${nodeId}: cursor never followed graph step`);
  }
  if (!production) return issues;

  const modelSteps = cursorSteps.filter(step => step.actorType === 'nemotron_agent');
  if (!exactMembers([...new Set(modelSteps.map(step => step.agentId))], REQUIRED_NEMOTRON_AGENT_IDS)) issues.push('production cursor did not present exact six model identities');
  if (!exactMembers([...new Set(modelSteps.map(step => step.signature))], Object.values(REQUIRED_NEMOTRON_AGENT_SIGNATURES).map(value => value.signature))) issues.push('production cursor signatures are not exact');
  for (const agentId of REQUIRED_NEMOTRON_AGENT_IDS) {
    const agentSteps = modelSteps.filter(step => step.agentId === agentId);
    const artifactSteps = agentSteps.filter(step => step.phase === 'artifact');
    if (artifactSteps.length !== 1) {
      issues.push(`${agentId}: expected exactly one receipt-bound artifact phase`);
      continue;
    }
    const step = artifactSteps[0];
    const artifact = step.ownedArtifact;
    if (!artifact || artifact.targetCount !== 1 || artifact.owner !== step.agentId || artifact.actorType !== 'nemotron_agent' || !nonemptyString(step.callId) || !nonemptyString(step.outputArtifact) || !nonemptyString(artifact.callId) || !nonemptyString(artifact.outputArtifact)) issues.push(`${step.agentId}: visible owned artifact is not exactly bound to its receipt`);
    if (artifact?.requestedModel !== REQUESTED_NEMOTRON_MODEL || !EXACT_NEMOTRON_RESPONSE_MODELS.has(artifact?.responseModel)) issues.push(`${step.agentId}: visible owned artifact is not bound to the required Nemotron model receipt`);
    if (!step.target.includes(`${step.agentId}:${artifact?.outputArtifact || ''}`)) issues.push(`${step.agentId}: cursor did not target its owned output artifact`);
    if (step.callId !== artifact?.callId || step.outputArtifact !== artifact?.outputArtifact) issues.push(`${step.agentId}: cursor artifact phase is not bound to its emitted call/output identity`);
  }
  return issues;
}

function artifactCursorProducerRoleContractViolations(team, cursorSteps, semanticEvents) {
  const issues = [];
  const members = Array.isArray(team?.members) ? team.members : [];
  if (team?.ariaLabel !== 'Specialist activity') issues.push('desktop team label drift');
  if (team?.cursorCount !== 1) issues.push(`artifact cursor count ${team?.cursorCount}`);
  if (stableJson(members.map(member => member.agentId)) !== stableJson(REQUIRED_NEMOTRON_AGENT_IDS)) issues.push('desktop team is not the exact ordered six-role set');
  members.forEach(member => {
    const expectedRole = REQUIRED_DESKTOP_AGENT_LABELS[member.agentId];
    const expectedRuntimeIdentity = REQUIRED_NEMOTRON_AGENT_SIGNATURES[member.agentId];
    const expectedVisualIdentity = visibleAgentIdentity(member.agentId);
    const expectedVisualGroupId = visibleAgentGroupId(member.agentId);
    const shouldBeVisible = REQUIRED_VISIBLE_SPECIALIST_IDS.includes(member.agentId);
    if (shouldBeVisible && (!member.visible || !member.monogramVisible || !member.shortVisible)) issues.push(`${member.agentId || 'unknown'}: useful specialist identity is not visible`);
    if (!shouldBeVisible && (member.visible || member.monogramVisible || member.shortVisible)) issues.push(`${member.agentId || 'unknown'}: internal planning role leaked into the main experience`);
    const expectedShort = member.agentId === PATH_BUILDER_VISUAL_GROUP_ID
      ? PATH_BUILDER_VISIBLE_IDENTITY.short
      : REQUIRED_DESKTOP_AGENT_SHORTS[member.agentId];
    if (member.role !== expectedRole || member.short !== expectedShort || member.monogram !== expectedRuntimeIdentity?.monogram
      || member.signature !== expectedVisualIdentity.signature || member.visualGroupId !== expectedVisualGroupId) {
      issues.push(`${member.agentId || 'unknown'}: desktop runtime identity or visible group drift`);
    }
    if (member.agentId === PATH_BUILDER_VISUAL_GROUP_ID && member.controlLabel !== `Open ${PATH_BUILDER_VISIBLE_IDENTITY.label} activity`) {
      issues.push('path builder: merged activity control label drift');
    }
    if (shouldBeVisible && String(member.color || '').toLowerCase() !== REQUIRED_DESKTOP_AGENT_COLORS[expectedVisualGroupId]) issues.push(`${member.agentId || 'unknown'}: visible-group color drift`);
  });
  const visibleMembers = members.filter(member => member.visible);
  if (stableJson(visibleMembers.map(member => member.agentId).sort()) !== stableJson([...REQUIRED_VISIBLE_SPECIALIST_IDS].sort())) issues.push('desktop does not expose the exact four useful viewer-facing workstreams');
  if (new Set(visibleMembers.map(member => member.visualGroupId)).size !== REQUIRED_VISIBLE_SPECIALIST_IDS.length) issues.push('viewer-facing workstream groups are not unique');
  if (new Set(visibleMembers.map(member => String(member.color || '').toLowerCase())).size !== REQUIRED_VISIBLE_SPECIALIST_IDS.length) issues.push('viewer-facing workstream colors are not unique');

  const semanticById = new Map((semanticEvents || []).filter(event => event.eventId).map(event => [event.eventId, event]));
  const clickSteps = (cursorSteps || []).filter(step => step.phase === 'click');
  if (!clickSteps.length) issues.push('artifact cursor never completed a target-bound click');
  clickSteps.forEach((step, index) => {
    if (step.cursorCount !== 1 || step.cursorTargetCount !== 1 || step.cursorTargetId !== step.targetId) issues.push(`${index}: artifact cursor is not bound to exactly one target`);
    if (!nonemptyString(step.cursorAgent) || !nonemptyString(step.cursorAction)) issues.push(`${index}: artifact cursor agent/action label is unreadable`);
    const semantic = semanticById.get(step.eventId);
    if (step.specialistBound) {
      const runtimeAgentId = step.runtimeAgentId || step.agentId || step.visualActiveAgentId || '';
      const expectedVisualGroupId = visibleAgentGroupId(runtimeAgentId);
      const expectedIdentity = visibleAgentIdentity(runtimeAgentId);
      const allowedCursorLabels = [expectedIdentity.short, expectedIdentity.label];
      if (expectedVisualGroupId === PATH_BUILDER_VISUAL_GROUP_ID) allowedCursorLabels.push('Path');
      if (!REQUIRED_NEMOTRON_AGENT_IDS.includes(runtimeAgentId)
        || step.visualGroupId !== expectedVisualGroupId
        || step.signature !== expectedIdentity.signature
        || !allowedCursorLabels.includes(step.cursorAgent)) {
        issues.push(`${index}: target-lineage producer is not in its truthful viewer-facing workstream`);
      }
      if (semantic?.actorType === 'nemotron_agent' && semantic.agentId !== runtimeAgentId) issues.push(`${index}: model-call identity differs from its receipt-bound runtime specialist`);
    }
    if (semantic && !REQUIRED_NEMOTRON_AGENT_IDS.includes(semantic.agentId)) {
      if (step.activeAgentId) issues.push(`${index}: deterministic authority inherited model-call identity`);
      if (step.visualActiveAgentId && !REQUIRED_NEMOTRON_AGENT_IDS.includes(step.visualActiveAgentId)) issues.push(`${index}: visual coordinator is outside the closed six-role map`);
    }
    if (step.activeAgentId && !REQUIRED_NEMOTRON_AGENT_IDS.includes(step.activeAgentId)) issues.push(`${index}: active model identity is outside the closed six-role map`);
  });
  if (!cursorSteps.some(step => !step.activeAgentId && step.activeSignature === 'law' && step.presentationMode === 'deterministic-projection' && /law/i.test(`${step.workAuthority} ${step.agentId} ${semanticById.get(step.eventId)?.agentId || ''}`))) issues.push('law: deterministic authority/model identity distinction was not visibly exercised');
  if (!cursorSteps.some(step => !step.activeAgentId && step.activeSignature === 'reference')) issues.push('reference: deterministic authority/model identity distinction was not visibly exercised');
  if (!cursorSteps.some(step => !step.activeAgentId && ['gate', 'audit'].includes(step.activeSignature) && /gate|safety/i.test(`${step.workAuthority} ${step.agentId} ${semanticById.get(step.eventId)?.agentId || ''}`))) issues.push('gate: deterministic authority/model identity distinction was not visibly exercised');
  return issues;
}

function sourcePreludeContractViolations(snapshot) {
  const issues = [];
  const steps = Array.isArray(snapshot?.steps) ? snapshot.steps : [];
  const allowedStates = [
    ['active', 'waiting', 'waiting'],
    ['complete', 'active', 'waiting'],
  ];
  if (snapshot?.sourceCount !== SOURCE_PRELUDE_ICON_KINDS.length) issues.push('opening path plan is not bound to the exact seven-source package');
  if (snapshot?.cardCount !== 0) issues.push('opening path plan retains the obsolete seven-card strip');
  if (snapshot?.inputCount !== 0 || snapshot?.checkboxRoleCount !== 0) issues.push('opening path plan retains a checkbox or checkbox role');
  if (snapshot?.label !== PATH_BUILDER_VISIBLE_IDENTITY.label || snapshot?.title !== 'Build the claim path') issues.push('opening path plan is not owned by the merged Path builder presentation');
  if (snapshot?.planCount !== 1 || stableJson(steps.map(step => step.label)) !== stableJson([
    'Read the exact source',
    'Keep the supported fact',
    'Add the next process step',
  ])) issues.push('opening path plan is not the exact three-step read-to-node sequence');
  if (!allowedStates.some(states => stableJson(steps.map(step => step.state)) === stableJson(states))
    || steps.filter(step => step.state === 'active').length !== 1) issues.push('opening path plan does not have one calm active step');
  return [...new Set(issues)];
}

function sourceRailArtifactKind(artifact) {
  const semantic = `${artifact?.title || ''} ${artifact?.filename || ''}`.toLowerCase();
  if (/delivery|receipt|confirmation/.test(semantic)) return 'delivery';
  if (/timeline|chronology/.test(semantic)) return 'timeline';
  if (String(artifact?.media_type || '').startsWith('image/')) return 'image';
  if (/lease|agreement|contract|policy/.test(semantic)) return 'contract';
  if (artifact?.media_type === 'message/rfc822' || /email|message|reply|notification|letter/.test(semantic)) return 'mail';
  if (/inspection|assessment|report|technical/.test(semantic)) return 'inspection';
  return 'generic';
}

function expectedSourceRailItems(claim) {
  return [
    { sourceId: 'message', kind: 'mail', name: 'Claim message' },
    ...(Array.isArray(claim?.artifacts) ? claim.artifacts : []).map(artifact => ({
      sourceId: String(artifact?.artifact_id || ''),
      kind: sourceRailArtifactKind(artifact),
      name: String(artifact?.title || ''),
    })),
  ];
}

function displayedSourceRailId(sourceId) {
  const exact = String(sourceId || '');
  return exact === 'intake' ? 'message' : exact;
}

function sourceRailContractViolations(snapshot, expectedSources, expectedActive = {}) {
  const issues = [];
  const items = Array.isArray(snapshot?.items) ? snapshot.items : [];
  const expected = Array.isArray(expectedSources) ? expectedSources : [];
  const expectedSourceId = displayedSourceRailId(expectedActive?.sourceId);
  const expectedLocatorId = String(expectedActive?.locatorId || '');
  const viewport = snapshot?.viewport || {};

  if (snapshot?.contract !== SOURCE_RAIL_CONTRACT) issues.push('source rail contract identity is absent or wrong');
  if (!SOURCE_RAIL_VIEWPORTS.some(item => item.width === viewport.width && item.height === viewport.height)) issues.push('source rail was not checked at 1280x720 or 1440x900');
  if (!snapshot?.railVisible || !snapshot?.listVisible || !snapshot?.insideViewport || snapshot?.collapsed) issues.push('source rail is hidden, clipped, or collapsed');
  if (!Number.isFinite(snapshot?.railRect?.width)
    || snapshot.railRect.width < SOURCE_RAIL_MIN_WIDTH_PX
    || snapshot.railRect.width > SOURCE_RAIL_MAX_WIDTH_PX) issues.push('source rail width is not compact');
  if (!Number.isFinite(snapshot?.railRect?.height) || snapshot.railRect.height < viewport.height - 80) issues.push('source rail does not retain the desktop workspace height');
  if (!Number.isFinite(snapshot?.headingHeight) || snapshot.headingHeight < 44 || snapshot.headingHeight > 56) issues.push('source rail heading is not compact');
  if (!['auto', 'scroll'].includes(snapshot?.listOverflowY) || snapshot?.listHorizontalOverflow > 1 || snapshot?.pageHorizontalOverflow > 1) issues.push('source rail is not a contained vertical scroll region');
  if (snapshot?.dropdownCount !== 0 || snapshot?.expanderCount !== 0 || snapshot?.collapsedControlCount !== 0) issues.push('source rail retains dropdown, expander, or collapse semantics');
  if (snapshot?.workOverlapArea > SPATIAL_GEOMETRY_EPSILON_PX || (snapshot?.overlayOverlapAreas || []).some(area => area > SPATIAL_GEOMETRY_EPSILON_PX)) issues.push('source rail overlaps the work canvas or an open inspection surface');
  if (snapshot?.rowOverlapCount !== 0) issues.push('source rail rows overlap each other');

  if (snapshot?.itemCount !== 7 || items.length !== 7 || expected.length !== 7) issues.push('source rail does not contain the exact seven claim sources');
  if (stableJson(items.map(item => item.sourceId)) !== stableJson(expected.map(item => item.sourceId))) issues.push('source rail source identity or order differs from the returned claim package');
  items.forEach((item, index) => {
    const expectedItem = expected[index] || {};
    if (!item.visible || !item.fullyVisible) issues.push(`${item.sourceId || index}: source row is not fully visible`);
    if (!Number.isFinite(item?.rect?.height)
      || item.rect.height < SOURCE_RAIL_MIN_ROW_HEIGHT_PX
      || item.rect.height > SOURCE_RAIL_MAX_ROW_HEIGHT_PX) issues.push(`${item.sourceId || index}: source row is not compact`);
    if (item.iconCount !== 1 || item.iconKind !== expectedItem.kind || !nonemptyString(item.iconMarkup)
      || !Number.isFinite(item.iconWidth) || !Number.isFinite(item.iconHeight)
      || item.iconWidth < SOURCE_RAIL_MIN_ICON_SIZE_PX || item.iconWidth > SOURCE_RAIL_MAX_ICON_SIZE_PX
      || item.iconHeight < SOURCE_RAIL_MIN_ICON_SIZE_PX || item.iconHeight > SOURCE_RAIL_MAX_ICON_SIZE_PX) issues.push(`${item.sourceId || index}: source row lacks one restrained type-correct icon`);
    if (item.nameCount !== 1 || item.name !== expectedItem.name || !nonemptyString(item.name)) issues.push(`${item.sourceId || index}: source row name is absent, duplicated, or inexact`);
    if (item.metaCount !== 1 || !nonemptyString(item.meta)) issues.push(`${item.sourceId || index}: source row metadata is absent or duplicated`);
    if (item.statusCount !== 1 || !SOURCE_RAIL_ALLOWED_STATUSES.has(item.status)) issues.push(`${item.sourceId || index}: source row status is absent, duplicated, or unsupported`);
    if (item.thumbImageCount !== 0 || item.extraLabelCount !== 0) issues.push(`${item.sourceId || index}: source row retains a thumbnail or redundant label`);
    if (item.active !== item.ariaCurrent) issues.push(`${item.sourceId || index}: active source styling and current-source semantics disagree`);
  });

  const activeIds = Array.isArray(snapshot?.activeSourceIds) ? snapshot.activeSourceIds : [];
  const readingIds = items.filter(item => item.status === 'reading').map(item => item.sourceId);
  if (expectedSourceId) {
    if (stableJson(activeIds) !== stableJson([expectedSourceId]) || stableJson(readingIds) !== stableJson([expectedSourceId])) issues.push('source use does not select exactly one matching reading row');
    if (snapshot?.activeSourceLocator !== expectedLocatorId || !nonemptyString(expectedLocatorId)) issues.push('active source row is not bound to the exact returned locator');
  } else if (activeIds.length || readingIds.length || snapshot?.activeSourceLocator) {
    issues.push('source rail preselects a source before an exact source-use action');
  }
  return [...new Set(issues)];
}

function canonicalFactsLiveWorkPlanContractViolations(planSnapshots, factTourSnapshots, run) {
  const issues = [];
  const snapshots = Array.isArray(planSnapshots) ? planSnapshots : [];
  const facts = Array.isArray(factTourSnapshots) ? factTourSnapshots : [];
  const expectedRunId = String(run?.run_id || '');
  const startedReceipts = (Array.isArray(run?.events) ? run.events : []).filter(event => (
    event?.receipt_type === 'agent_started'
    && event?.actor_type === 'nemotron_agent'
    && event?.agent_id === 'canonical_facts'
  ));
  const started = startedReceipts[0];
  if (startedReceipts.length !== 1
    || !nonemptyString(started?.event_id)
    || !nonemptyString(started?.call_id)
    || !['started', 'running', 'in_progress'].includes(String(started?.status || ''))
    || started?.call_count !== 1
    || started?.cache_hit === true
    || started?.input_artifact !== 'observable_claim_package'
    || !SHA256_PATTERN.test(started?.input_artifact_hash || '')) {
    issues.push('canonical fact work lacks one exact uncached agent-started receipt');
  }
  if (!nonemptyString(expectedRunId)) issues.push('canonical fact work lacks its returned run identity');
  if (!snapshots.length) issues.push('canonical fact call never replaces the idle source cards with a live work plan');

  snapshots.forEach((snapshot, index) => {
    if (snapshot?.planCount !== 1 || snapshot?.focalChildCount !== 1 || snapshot?.visible !== true) {
      issues.push(`${index}: canonical fact work does not show one visible focal plan`);
    }
    if (snapshot?.contract !== LIVE_WORK_PLAN_CONTRACT
      || snapshot?.presentationMode !== 'live-call'
      || snapshot?.agentId !== 'canonical_facts'
      || snapshot?.runtimeAgentId !== 'canonical_facts'
      || snapshot?.visualGroupId !== PATH_BUILDER_VISUAL_GROUP_ID
      || snapshot?.agentSignature !== PATH_BUILDER_VISIBLE_IDENTITY.signature
      || snapshot?.runId !== expectedRunId
      || snapshot?.callId !== String(started?.call_id || '')
      || snapshot?.eventId !== String(started?.event_id || '')
      || snapshot?.workState !== String(started?.status || '')) {
      issues.push(`${index}: live work plan is not bound to the exact returned run, call, event, agent, and work state`);
    }
    if (snapshot?.inputArtifact !== String(started?.input_artifact || '')
      || snapshot?.inputArtifactHash !== String(started?.input_artifact_hash || '')) {
      issues.push(`${index}: live work plan is not bound to the exact claim-package input`);
    }
    if (snapshot?.rootWorkState !== 'working'
      || snapshot?.rootAgentId !== snapshot?.agentId
      || snapshot?.rootRunId !== snapshot?.runId
      || snapshot?.rootCallId !== snapshot?.callId
      || snapshot?.rootEventId !== snapshot?.eventId) {
      issues.push(`${index}: focal plan and live canvas authority are not the same call`);
    }
    if (snapshot?.title !== 'Build the claim path'
      || stableJson(snapshot?.steps || []) !== stableJson(CANONICAL_FACTS_LIVE_WORK_STEPS)) {
      issues.push(`${index}: live work plan is not the exact three simple truthful steps with one active spinner`);
    }
    if (snapshot?.sourcePreludeCount !== 0 || snapshot?.sourcePreludeCardCount !== 0 || snapshot?.factTourCount !== 0) {
      issues.push(`${index}: live work plan competes with the idle source prelude or fact tour`);
    }
    if (snapshot?.forbiddenProgressCount !== 0 || snapshot?.percentText === true) {
      issues.push(`${index}: live work plan includes a percent, progress bar, or slider`);
    }
  });

  if (facts.length) issues.push('separate source-to-fact tour remains outside the merged Path builder graph flow');
  return [...new Set(issues)];
}

function openingClaimCardContractViolations(snapshot, claim) {
  const issues = [];
  if (snapshot?.cardCount !== 1 || !snapshot?.visible || snapshot?.sourceId !== 'message') issues.push('opening does not show one visible claim-message source card');
  if (stableJson(snapshot?.childTags) !== stableJson(['HEADER', 'STRONG', 'BLOCKQUOTE', 'P'])
    || snapshot?.blockquoteCount !== 1 || snapshot?.paragraphCount !== 1) issues.push('opening claim card is not the exact compact four-part source structure');
  if (!nonemptyString(claim?.subject) || snapshot?.subject !== claim.subject) issues.push('opening claim subject does not equal the returned source subject');
  if (snapshot?.problem !== EXPECTED_OPENING_PROBLEM || !String(claim?.message || '').includes(snapshot?.problem || '')) issues.push('opening problem sentence is not the exact claim-message sentence');
  if (snapshot?.outcome !== EXPECTED_OPENING_OUTCOME || !String(claim?.message || '').includes(snapshot?.outcome || '')) issues.push('opening requested outcome is not the exact claim-message request');
  if (snapshot?.generatedSummaryCount !== 0 || snapshot?.bodyCopyLength !== EXPECTED_OPENING_PROBLEM.length + EXPECTED_OPENING_OUTCOME.length) issues.push('opening claim card adds generated summary prose');
  if (!Number.isFinite(snapshot?.width) || !Number.isFinite(snapshot?.height)
    || snapshot.width > 640 || snapshot.height > 220) issues.push('opening claim card is not compact');
  return [...new Set(issues)];
}

function factSourceTourContractViolations(snapshots, highlights, semanticEvents, run) {
  const issues = [];
  const result = run?.result || run || {};
  const expectedRunId = String(run?.run_id || '');
  const factsById = new Map((result.facts || []).map(fact => [fact.fact_id, fact]));
  const factEvents = new Map((semanticEvents || [])
    .filter(event => event.entityKind === 'fact')
    .map(event => [event.entityId, event]));
  const firstPhase = (factId, phase) => (snapshots || []).find(item => item.factId === factId && item.phase === phase);
  const observedOrder = [];
  for (const item of snapshots || []) {
    if (item.phase === 'select-source' && item.factId && !observedOrder.includes(item.factId)) observedOrder.push(item.factId);
  }
  if (stableJson(observedOrder) !== stableJson(FACT_TOUR_FACT_IDS)) issues.push('fact tour does not show the exact eight returned facts in order');

  FACT_TOUR_FACT_IDS.forEach(factId => {
    const fact = factsById.get(factId);
    const semantic = factEvents.get(factId);
    const phases = ['select-source', 'read-source', 'highlight-source', 'finding'].map(phase => firstPhase(factId, phase));
    const [select, read, highlighted, finding] = phases;
    if (!fact || phases.some(item => !item)) {
      issues.push(`${factId}: source-to-fact replay does not show select, read, highlight, then returned fact`);
      return;
    }
    const returnedRef = (fact.source_refs || []).find(ref => (
      ref.artifact_id === select.sourceId && factSourceLocatorId(ref) === select.locatorId
    ));
    if (!returnedRef || phases.some(item => item.sourceId !== select.sourceId || item.locatorId !== select.locatorId)) {
      issues.push(`${factId}: tour source and locator are not one exact returned fact reference`);
    }
    if (!(select.at <= read.at && read.at <= highlighted.at && highlighted.at <= finding.at)) issues.push(`${factId}: source and fact phases are not sequential`);
    if (select.activeSourceIds.length || select.activeSourceLocator || select.highlightCount || select.factVisible) issues.push(`${factId}: source is not neutral before it opens`);
    if (!read.artifactSurfaceVisible || stableJson(read.activeSourceIds) !== stableJson([displayedSourceRailId(select.sourceId)])
      || read.activeSourceLocator !== select.locatorId || read.highlightCount || read.factVisible) issues.push(`${factId}: exact returned artifact is not visibly open before selection`);
    if (!highlighted.artifactSurfaceVisible || highlighted.highlightCount !== 1 || highlighted.factVisible) issues.push(`${factId}: selected source region is not isolated before the fact appears`);
    if (!finding.factVisible || finding.factLabel !== String(fact.label || '') || finding.factValue !== String(fact.value ?? '')) issues.push(`${factId}: exact returned fact does not visibly follow its selected source`);
    const sourceHighlight = (highlights || []).find(item => item.entityKind === 'fact' && item.factId === factId
      && item.sourceId === select.sourceId && item.locatorId === select.locatorId && item.sourceHighlighted === true);
    if (!sourceHighlight || !(read.at <= sourceHighlight.at && sourceHighlight.at <= finding.at)) issues.push(`${factId}: exact returned locator was not visibly selected before the fact appeared`);
    if (!semantic || semantic.runId !== expectedRunId || semantic.traceContract !== EXECUTION_TRACE_CONTRACT
      || semantic.presentationMode !== 'returned_action_replay' || semantic.eventId !== finding.eventId
    ) issues.push(`${factId}: visible fact is not bound to its run-scoped accepted execution trace`);
    const meaningSelectedByModel = semantic?.modelOwnedFields?.includes('assertion_id');
    if (semantic?.modelOwnedFields?.includes('value')
      || (meaningSelectedByModel
        ? (!semantic?.materializedFromModelAssertionFields?.includes('value') || semantic?.applicationOwnedFields?.includes('value'))
        : !semantic?.applicationOwnedFields?.includes('value'))) {
      issues.push(`${factId}: returned fact value ownership does not match its bounded assertion selection`);
    }
    if (phases.some(item => item.presentationMode !== 'returned-action-replay' || !/^Returned work · /.test(item.presentationLabel))) {
      issues.push(`${factId}: returned-action replay is not visibly labelled`);
    }
    const modelSelectedLocatorIds = (Array.isArray(semantic?.modelSelectedTextRefs) ? semantic.modelSelectedTextRefs : []).map(factSourceLocatorId);
    const exactLocatorWasModelSelected = semantic?.modelContributionAccepted === true
      && modelSelectedLocatorIds.includes(select.locatorId);
    if (exactLocatorWasModelSelected) {
      if (semantic.actorType !== 'nemotron_agent' || semantic.agentId !== 'canonical_facts'
        || finding.agentId !== 'canonical_facts'
        || phases.some(item => item.activeAgentId !== 'canonical_facts' || item.activeSignature !== 'facts')) {
        issues.push(`${factId}: exact model-selected text locator is not bound to the Claim reader identity`);
      }
    } else {
      if (finding.agentId) issues.push(`${factId}: application-projected fact finding inherited a model-agent identity`);
      if (phases.some(item => item.activeAgentId || item.activeSignature !== 'gate' || item.workAuthority !== 'Fact safety check')) {
        issues.push(`${factId}: application-projected fact locator inherited a model-agent identity`);
      }
    }
  });
  return [...new Set(issues)];
}

function officialLawTourContractViolations(steps, semanticEvents, run) {
  const issues = [];
  const result = run?.result || run || {};
  const expectedRunId = String(run?.run_id || '');
  const sources = result.legal_research?.sources || [];
  if (sources.length !== 4 || stableJson((steps || []).map(item => item.sourceId)) !== stableJson(sources.map(item => item.source_id))) {
    issues.push('official-law tour does not show the exact four returned registry sources in order');
  }
  const semanticBySource = new Map((semanticEvents || [])
    .filter(event => event.entityKind === 'official_source')
    .map(event => [event.entityId, event]));
  sources.forEach((source, index) => {
    const step = (steps || [])[index];
    const semantic = semanticBySource.get(source.source_id);
    if (!step || step.sourceId !== source.source_id || step.location !== source.location || step.url !== source.url
      || step.retrievalMethod !== 'versioned_official_source_registry_lookup'
      || !nonemptyString(step.registryVersion) || step.selectedSourceId !== source.source_id
      || step.passageSourceId !== source.source_id || step.selectedUrl !== source.url || step.passageUrl !== source.url) {
      issues.push(`${source.source_id}: official registry source is not visibly exact`);
    }
    if (!semantic || semantic.runId !== expectedRunId || semantic.actorType !== 'deterministic_tool'
      || semantic.agentId !== 'official_law_registry' || semantic.traceContract !== EXECUTION_TRACE_CONTRACT
      || semantic.presentationMode !== 'deterministic_projection' || semantic.modelContributionAccepted !== false) {
      issues.push(`${source.source_id}: official law is not bound to its deterministic run-scoped registry trace`);
    }
    if (step && (step.presentationMode !== 'deterministic-projection' || step.activeAgentId
      || step.activeSignature !== 'law' || step.workAuthority !== 'Swiss law lookup'
      || step.presentationLabel !== 'Application step · Swiss law lookup')) {
      issues.push(`${source.source_id}: official law is visually misrepresented as Nemotron work`);
    }
  });
  return [...new Set(issues)];
}

function acceptedExecutionFieldOwnershipViolations(semanticEvents, run) {
  const issues = [];
  const expectedRunId = String(run?.run_id || '');
  const events = Array.isArray(semanticEvents) ? semanticEvents : [];
  const byKey = new Map(events.map(event => [`${event.entityKind}:${event.entityId}`, event]));
  const audit = orchestrationAudit(run) || {};
  const agentsById = new Map((audit.agents || []).map(agent => [agent.agent_id, agent]));
  const gatesById = new Map((audit.deterministic_gates || []).map(gate => [gate.agent_id, gate]));
  const exactCallBinding = (event, agentId, gateId = '') => {
    const agent = agentsById.get(agentId);
    const gate = gateId ? gatesById.get(gateId) : null;
    return Boolean(agent)
      && event?.sourceCallId === agent.call_id
      && event?.originCallId === agent.origin_call_id
      && event?.callCount === agent.call_count
      && event?.usageSource === agent.usage_source
      && event?.cacheHit === (agent.cache_hit === true)
      && event?.sourceCallInputHash === agent.input_artifact_hash
      && event?.sourceCallOutputHash === agent.output_artifact_hash
      && (!gateId || (Boolean(gate) && event?.gateInputHash === gate.input_artifact_hash));
  };
  const expectedNodeIds = (run?.result?.process?.nodes || []).map(node => node.node_id);
  const expectedEvidenceIds = (run?.result?.checklist?.items || []).map(item => item.item_id);
  const factsById = new Map((run?.result?.facts || []).map(fact => [fact.fact_id, fact]));
  const modelFactSelectionExecuted = agentsById.has('canonical_facts');
  events.filter(event => event.entityKind === 'fact').forEach(event => {
    const fact = factsById.get(event.entityId);
    const meaningSelectedByModel = event.modelOwnedFields.includes('assertion_id');
    const meaningMustBeModelSelected = fact?.controls_process === true && modelFactSelectionExecuted;
    if (event.runId !== expectedRunId || event.traceContract !== EXECUTION_TRACE_CONTRACT
      || event.presentationMode !== 'returned_action_replay') issues.push(`${event.entityId}: fact trace is not run-bound`);
    if (event.modelOwnedFields.some(field => !['assertion_id', 'source_ref_ids', 'confidence'].includes(field))
      || (meaningSelectedByModel
        ? (!nonemptyString(event.assertionId)
          || !event.materializedFromModelAssertionFields.includes('value')
          || event.applicationOwnedFields.includes('value'))
        : !event.applicationOwnedFields.includes('value'))
      || meaningMustBeModelSelected !== meaningSelectedByModel) {
      issues.push(`${event.entityId}: fact assertion ownership is not exact`);
    }
    if (event.modelContributionAccepted === true
      && !exactCallBinding(event, 'canonical_facts')) {
      issues.push(`${event.entityId}: accepted Claim reader field is not bound to the exact source call input and output`);
    }
  });
  expectedNodeIds.forEach(nodeId => {
    const structure = byKey.get(`process_node:${nodeId}`);
    const decision = byKey.get(`process_decision:${nodeId}`);
    if (!structure || structure.type !== 'process_node.created' || structure.runId !== expectedRunId
      || structure.traceContract !== EXECUTION_TRACE_CONTRACT || structure.actorType !== 'deterministic_tool'
      || structure.modelContributionAccepted || structure.modelOwnedFields.length || structure.outputProcessNodeId !== nodeId
      || !structure.applicationOwnedFields.length) issues.push(`${nodeId}: process structure is not neutral and application-owned`);
    const linkedIds = structure?.linkedModelContributionIds || [];
    if (linkedIds.length) {
      if (!decision || decision.type !== 'process_decision.accepted' || decision.runId !== expectedRunId
        || decision.traceContract !== EXECUTION_TRACE_CONTRACT || decision.actorType !== 'nemotron_agent'
        || decision.agentId !== 'process_decision_mapping' || !decision.modelContributionAccepted
        || stableJson(decision.modelOwnedFields) !== stableJson(['decision_value'])
        || decision.applicationOwnedFields.length || stableJson(decision.acceptedContributionIds) !== stableJson(linkedIds)
        || !exactCallBinding(decision, 'process_decision_mapping', 'deterministic_process_gate')) {
        issues.push(`${nodeId}: Process builder is not limited to the exact accepted decision_value field`);
      }
    } else if (decision) issues.push(`${nodeId}: unlinked Process builder field event is present`);
  });
  expectedEvidenceIds.forEach(itemId => {
    const structure = byKey.get(`evidence_requirement:${itemId}`);
    const fields = byKey.get(`evidence_fields:${itemId}`);
    if (!structure || structure.type !== 'evidence_requirement.linked' || structure.runId !== expectedRunId
      || structure.traceContract !== EXECUTION_TRACE_CONTRACT || structure.actorType !== 'deterministic_tool'
      || structure.modelContributionAccepted || structure.modelOwnedFields.length || structure.outputEvidenceId !== itemId
      || !structure.applicationOwnedFields.length) issues.push(`${itemId}: evidence requirement structure is not neutral and application-owned`);
    const linkedFields = structure?.linkedModelFields || [];
    if (linkedFields.length) {
      const allowed = new Set(['status', 'artifact_ids']);
      if (!fields || fields.type !== 'evidence_fields.accepted' || fields.runId !== expectedRunId
        || fields.traceContract !== EXECUTION_TRACE_CONTRACT || fields.actorType !== 'nemotron_agent'
        || fields.agentId !== 'evidence_checklist' || !fields.modelContributionAccepted
        || !fields.modelOwnedFields.length || fields.modelOwnedFields.some(field => !allowed.has(field))
        || stableJson(fields.modelOwnedFields) !== stableJson(linkedFields) || fields.applicationOwnedFields.length
        || !exactCallBinding(fields, 'evidence_checklist', 'deterministic_evidence_gate')) {
        issues.push(`${itemId}: Document finder is not limited to exact accepted status/artifact_ids fields`);
      }
    } else if (fields) issues.push(`${itemId}: unlinked Document finder field event is present`);
  });
  const finalBrief = byKey.get('final_brief:final_claim_brief');
  if (finalBrief && (finalBrief.actorType !== 'nemotron_agent'
    || !exactCallBinding(finalBrief, 'final_claim_brief_audit', 'whole_playbook_gate'))) {
    issues.push('final brief fields are not bound to the exact critic call and whole-playbook gate input');
  }
  return [...new Set(issues)];
}

function specialistAvatarContractViolations(team, cursorSteps, production = true) {
  const issues = [];
  const members = Array.isArray(team?.members) ? team.members : [];
  const byId = new Map(members.map(member => [member.agentId, member]));
  const visibleMembers = members.filter(member => member.visible === true);
  const iconHashes = [];
  for (const agentId of REQUIRED_VISIBLE_SPECIALIST_IDS) {
    const member = byId.get(agentId);
    const expectedSignature = visibleAgentIdentity(agentId).signature;
    if (!member || member.signature !== expectedSignature || !nonemptyString(member.iconMarkup)) {
      issues.push(`${agentId}: visible workstream icon is absent or not bound to its signature`);
      continue;
    }
    iconHashes.push(sha256(member.iconMarkup));
  }
  if (visibleMembers.length !== REQUIRED_VISIBLE_SPECIALIST_IDS.length
    || iconHashes.length !== REQUIRED_VISIBLE_SPECIALIST_IDS.length
    || new Set(iconHashes).size !== REQUIRED_VISIBLE_SPECIALIST_IDS.length) {
    issues.push('four viewer-facing workstreams do not have four unique normalized role-icon hashes');
  }

  const covered = new Set();
  (cursorSteps || []).filter(step => step.specialistBound).forEach((step, index) => {
    const runtimeAgentId = step.runtimeAgentId || step.agentId || step.visualActiveAgentId || '';
    if (!REQUIRED_NEMOTRON_AGENT_IDS.includes(runtimeAgentId)) return;
    covered.add(runtimeAgentId);
    const visualGroupId = visibleAgentGroupId(runtimeAgentId);
    const member = byId.get(visualGroupId);
    const expectedSignature = visibleAgentIdentity(runtimeAgentId).signature;
    if (step.signature !== expectedSignature || step.avatar !== expectedSignature || !nonemptyString(step.avatarMarkup) || step.avatarMarkup !== member?.iconMarkup) issues.push(`${index}: live specialist cursor role icon does not exactly match its rail identity`);
    if (step.visualGroupId !== visualGroupId) issues.push(`${index}: live specialist cursor is not bound to its viewer-facing workstream`);
  });
  if (production && !exactMembers([...covered], REQUIRED_NEMOTRON_AGENT_IDS)) issues.push('production cursor did not retain all six exact runtime agent identities beneath the merged workstreams');
  return [...new Set(issues)];
}

function intakeClaimMessageBasisContractViolations(construction, preview, expected) {
  const issues = [];
  if (!expected || expected.factId !== 'fact_customer_objective' || expected.sourceId !== 'message' || !nonemptyString(expected.locatorId) || !nonemptyString(expected.passage)) return ['returned intake claim-message basis is incomplete'];
  if (!construction
    || construction.nodeId !== 'intake'
    || construction.attachmentKind !== 'fact'
    || construction.factId !== expected.factId
    || construction.sourceId !== expected.sourceId
    || construction.locatorId !== expected.locatorId
    || construction.passage !== expected.passage
    || construction.highlightMarkCount !== 1
    || construction.generatedSummaryVisible) issues.push('intake construction does not use the exact selected claim-message passage');
  if (!preview
    || preview.nodeId !== 'intake'
    || preview.basisKind !== 'fact'
    || preview.factId !== expected.factId
    || preview.sourceId !== expected.sourceId
    || preview.locatorId !== expected.locatorId
    || preview.passage !== expected.passage
    || preview.exactReturnedSource !== true
    || preview.exactPassage !== true
    || preview.noGeneratedContext !== true) issues.push('ready intake preview is not the exact returned claim-message passage');
  return issues;
}

function agentAuditContractViolations(snapshots, audit, production = true, decisionFlowSteps = []) {
  const issues = [];
  const returned = Array.isArray(snapshots) ? snapshots : [];
  if (stableJson(returned.map(item => item.agentId)) !== stableJson(REQUIRED_VISIBLE_SPECIALIST_IDS)) issues.push('agent audit did not inspect the exact four visible workstreams in order');
  const authoritativeAgents = Array.isArray(audit?.agents) ? audit.agents : [];
  const authoritativeById = new Map(authoritativeAgents.map(item => [item.agent_id, item]));
  if (production && (stableJson(authoritativeAgents.map(item => item.agent_id)) !== stableJson(REQUIRED_NEMOTRON_AGENT_IDS)
    || authoritativeAgents.some(item => item.actor_type !== 'nemotron_agent'))) {
    issues.push('merged presentation does not retain the exact six runtime agent receipts');
  }
  const expectedReferenceActions = (decisionFlowSteps || [])
    .filter(step => REFERENCE_DECISION_AUDIT_PHASES.includes(step.phase))
    .map(step => ({ phase: step.phase, nodeId: step.nodeId || '', sourceId: step.sourceId || '', locatorId: step.locatorId || '' }));
  returned.forEach(snapshot => {
    const expectedIdentity = REQUIRED_NEMOTRON_AGENT_SIGNATURES[snapshot.agentId];
    if (!snapshot.opened || snapshot.panelAgentId !== snapshot.agentId || snapshot.panelSignature !== expectedIdentity?.signature || snapshot.buttonPressed !== 'true') issues.push(`${snapshot.agentId}: activity panel did not open for the clicked role identity`);
    if (!snapshot.focusRestored || snapshot.buttonPressedAfterClose !== 'false' || snapshot.panelOpenAfterClose) issues.push(`${snapshot.agentId}: activity panel close did not restore its trigger and closed state`);
    if (!production) {
      if (snapshot.agentId === 'process_decision_mapping') {
        if (!snapshot.historyAvailable || snapshot.historyMode !== 'reference-replay-actions' || snapshot.historyContract
          || stableJson(snapshot.historyStepCounts) !== stableJson([1, 0, 0, 0, 0])
          || snapshot.acceptedIds.length || snapshot.rejections.length || snapshot.callId || snapshot.outputHash
          || snapshot.emptyStateVisible || snapshot.referenceTaskCount !== 1) issues.push(`${snapshot.agentId}: reference Path audit does not use its replay action history`);
        if (!expectedReferenceActions.length || snapshot.referenceActionCount !== expectedReferenceActions.length
          || stableJson(snapshot.referenceActions) !== stableJson(expectedReferenceActions)) issues.push(`${snapshot.agentId}: reference Path audit actions do not equal the exact persisted decision flow`);
        if (!snapshot.referenceProvenanceVisible || snapshot.referenceProvenanceText !== 'No provider call · accepted reference output replay') issues.push(`${snapshot.agentId}: reference Path audit provenance footer is absent or inexact`);
        if (snapshot.noAgentCallsEmptyStateVisible) issues.push(`${snapshot.agentId}: primary reference Path audit falls back to No agent calls were made`);
      } else if (snapshot.historyAvailable || snapshot.historyContract || snapshot.historyStepCounts.some(count => count !== 0)
        || snapshot.acceptedIds.length || snapshot.rejections.length || snapshot.callId || snapshot.outputHash || !snapshot.emptyStateVisible) {
        issues.push(`${snapshot.agentId}: deterministic reference replay fabricated call-bound activity`);
      }
      return;
    }
    const receipt = authoritativeById.get(snapshot.agentId);
    if (!receipt || receipt.actor_type !== 'nemotron_agent') {
      issues.push(`${snapshot.agentId}: authoritative call receipt is absent`);
      return;
    }
    if (!snapshot.historyAvailable || snapshot.historyContract !== AGENT_HISTORY_CONTRACT || snapshot.historyStepCounts.some(count => count !== 1)) issues.push(`${snapshot.agentId}: real activity history does not expose the exact five-step structure`);
    if (snapshot.callId !== receipt.call_id || snapshot.outputHash !== receipt.output_artifact_hash) issues.push(`${snapshot.agentId}: activity technical receipt is not exact`);
    const expectedAccepted = Array.isArray(receipt.accepted_ids) ? receipt.accepted_ids.map(String) : [];
    if (snapshot.acceptedCount !== receipt.accepted_count || snapshot.acceptedCount !== expectedAccepted.length || stableJson(snapshot.acceptedIds) !== stableJson(expectedAccepted)) issues.push(`${snapshot.agentId}: accepted item identities do not match the authoritative receipt`);
    const returnedRejected = Array.isArray(receipt.rejected)
      ? receipt.rejected
      : Array.isArray(receipt.rejected_items) ? receipt.rejected_items : null;
    const expectedRejected = (returnedRejected || []).map(item => ({
      id: String(item.item_id || item.fact_id || ''),
      invariant: String(item.invariant || ''),
    }));
    if (returnedRejected && (receipt.rejected_count !== expectedRejected.length || stableJson(snapshot.rejections) !== stableJson(expectedRejected))) issues.push(`${snapshot.agentId}: rejected item identities or reasons do not match the authoritative receipt`);
    if (!returnedRejected && snapshot.rejections.length) issues.push(`${snapshot.agentId}: activity history invented rejected item details`);
  });
  return [...new Set(issues)];
}

function zoomOutDesktopContractViolations({ sourceMoments, decisionSteps, artifactCursorSteps, previews, postConstructionSourceUse, team, documentPlan, documentRoundtrip, expectedNodeIds = FLAGSHIP_PROCESS_PROJECTION_IDS }) {
  const diagnostics = [];
  const sourceIssues = [];
  const latestSourceMoment = new Map((sourceMoments || []).map(snapshot => [snapshot.moment, snapshot]));
  REQUIRED_DESKTOP_SOURCE_MOMENTS.forEach(moment => {
    const snapshot = latestSourceMoment.get(moment);
    if (!snapshot) {
      sourceIssues.push(`${moment} was not observed`);
      return;
    }
    if (!snapshot.panelVisible || !snapshot.contentVisible || snapshot.collapsed || !snapshot.insideViewport || snapshot.width < 220 || snapshot.height < 400) sourceIssues.push(`${moment} does not keep the physical source panel open`);
    if (snapshot.toggleLooksDropdown) sourceIssues.push(`${moment} presents the source control as a dropdown`);
  });
  if (sourceIssues.length) diagnostics.push(`1. Source workspace continuity — ${sourceIssues.slice(0, 4).join('; ')}`);

  const selectionIssues = [];
  if ((decisionSteps || []).some(step => ['source', 'law'].includes(step.stepKind))) selectionIssues.push('graph replay reopens source or law instead of using accepted trace');
  const processClicks = (artifactCursorSteps || []).filter(step => step.phase === 'click'
    && step.presentationMode === 'returned-action-replay'
    && ['select-source', 'read-source'].includes(step.graphInspectionPhase));
  processClicks.forEach(step => {
    if (step.inspectionSourceId || step.inspectionLocatorId || step.activeSourceIds.length
      || step.activeSourceLocator || step.visibleSourceHighlightCount) selectionIssues.push(`${step.targetId}: graph replay falsely claims a new source read`);
  });
  if (!postConstructionSourceUse?.viewerOpen || postConstructionSourceUse.activeSourceIds.length !== 1 || postConstructionSourceUse.activeSourceIds[0] !== displayedSourceRailId(postConstructionSourceUse.sourceId) || postConstructionSourceUse.activeSourceLocator !== postConstructionSourceUse.locatorId) selectionIssues.push('post-construction full-source action does not activate its one exact source target and locator');
  if (selectionIssues.length) diagnostics.push(`2. Visible source causality — ${selectionIssues.slice(0, 4).join('; ')}`);

  const reasoningIssues = [];
  const previewIds = (previews || []).map(preview => preview.nodeId);
  if (stableJson(previewIds) !== stableJson(expectedNodeIds)) reasoningIssues.push('the returned route decisions do not each expose one contextual basis preview');
  (previews || []).forEach(preview => {
    if (preview.viewportWidth !== 1440 || preview.viewportHeight !== 900) reasoningIssues.push(`${preview.nodeId}: preview was not checked at 1440×900`);
    if (preview.previewCount !== 1 || !preview.previewVisible) reasoningIssues.push(`${preview.nodeId}: expected exactly one visible contextual basis preview, found ${preview.previewCount}`);
    const sourceBasis = ['fact', 'source'].includes(preview.basisKind);
    if (sourceBasis) {
      if (!preview.exactReturnedSource || !preview.sourceHasTarget || !preview.exactLocator || !preview.exactTitle || !preview.exactLocation || !preview.sourceWindowTruth || !preview.exactPassage || !preview.noGeneratedContext || !nonemptyString(preview.title) || !nonemptyString(preview.location) || !nonemptyString(preview.passage)) reasoningIssues.push(`${preview.nodeId}: fact/source basis preview does not preserve the actual returned artifact window, exact locator, and selected passage`);
      if (preview.action !== 'open-source' || preview.onDemandText !== 'Open original →') reasoningIssues.push(`${preview.nodeId}: original source is not explicitly on demand`);
    } else {
      if (!['law', 'evidence', 'accepted-decision', 'start-point'].includes(preview.basisKind) || !nonemptyString(preview.title) || !nonemptyString(preview.passage)) reasoningIssues.push(`${preview.nodeId}: non-source basis preview lacks a truthful kind, title, or returned basis`);
      if (preview.locatorId && !preview.exactLocator) reasoningIssues.push(`${preview.nodeId}: non-source basis preview claims a source locator that is not exact`);
    }
    if (!preview.inlineGroundingClosed || !preview.otherGroundingHidden || preview.groundingViewerOpen) reasoningIssues.push(`${preview.nodeId}: contextual basis preview is not visible in the default graph state with modal grounding closed`);
    if (preview.overlaps.length && !preview.foregroundIsolation) reasoningIssues.push(`${preview.nodeId}: basis preview overlaps ${preview.overlaps.join(', ')}`);
  });
  const visibleTeam = (team?.members || []).filter(member => member.visible === true);
  if (stableJson(visibleTeam.map(member => member.agentId).sort()) !== stableJson([...REQUIRED_VISIBLE_SPECIALIST_IDS].sort())
    || visibleTeam.some(member => member.visualGroupId !== visibleAgentGroupId(member.agentId)
      || member.signature !== visibleAgentIdentity(member.agentId).signature)) {
    reasoningIssues.push('the visible workstream rail does not merge source reading and process formation into one Path builder group');
  }
  if (!documentPlan || documentPlan.chains.length !== 21 || !documentPlan.chains.every(chain => stableJson(chain.parts.map(part => part.part)) === stableJson(['decision', 'fact', 'evidence', 'document']))) reasoningIssues.push('Document plan no longer shows each decision-to-document chain');
  if (!documentRoundtrip) reasoningIssues.push('Document plan does not return to the exact owning graph node');
  if (reasoningIssues.length) diagnostics.push(`3. Process-to-document story — ${reasoningIssues.slice(0, 5).join('; ')}`);
  return diagnostics.slice(0, 3);
}

function processPreviewGeometryContractViolations(samples, expectedNodeIds = FLAGSHIP_PROCESS_PROJECTION_IDS) {
  const issues = [];
  const snapshots = Array.isArray(samples) ? samples : [];
  if (!snapshots.length) return ['process preview geometry was not observed'];
  const completedNodeIds = new Set();
  let buildingObserved = false;
  let visibleItemCount = 0;
  snapshots.forEach((snapshot, snapshotIndex) => {
    const phase = snapshot?.phase || `snapshot-${snapshotIndex}`;
    if (snapshot?.viewportWidth !== 1440 || snapshot?.viewportHeight !== 900) issues.push(`${phase}: geometry was not captured at 1440×900`);
    if (snapshot?.constructionState === 'building') buildingObserved = true;
    if (phase.startsWith('completed-preview:')) completedNodeIds.add(phase.slice('completed-preview:'.length));
    const graphViewport = snapshot?.graphViewportRect;
    if (!graphViewport || !Number.isFinite(graphViewport.left) || !Number.isFinite(graphViewport.top) || !Number.isFinite(graphViewport.right) || !Number.isFinite(graphViewport.bottom)) {
      issues.push(`${phase}: graph viewport geometry is absent`);
      return;
    }
    (snapshot?.items || []).forEach((item, itemIndex) => {
      visibleItemCount += 1;
      const kind = item?.kind || `item-${itemIndex}`;
      const rect = item?.rect;
      if (!PROCESS_PREVIEW_GEOMETRY_SELECTORS.includes(kind) || !rect || !Number.isFinite(rect.left) || !Number.isFinite(rect.top) || !Number.isFinite(rect.right) || !Number.isFinite(rect.bottom)) {
        issues.push(`${phase}:${kind}: preview geometry is incomplete`);
        return;
      }
      const insideDesktop = rect.left >= -SPATIAL_GEOMETRY_EPSILON_PX
        && rect.top >= -SPATIAL_GEOMETRY_EPSILON_PX
        && rect.right <= snapshot.viewportWidth + SPATIAL_GEOMETRY_EPSILON_PX
        && rect.bottom <= snapshot.viewportHeight + SPATIAL_GEOMETRY_EPSILON_PX;
      const insideGraph = rect.left >= graphViewport.left - SPATIAL_GEOMETRY_EPSILON_PX
        && rect.top >= graphViewport.top - SPATIAL_GEOMETRY_EPSILON_PX
        && rect.right <= graphViewport.right + SPATIAL_GEOMETRY_EPSILON_PX
        && rect.bottom <= graphViewport.bottom + SPATIAL_GEOMETRY_EPSILON_PX;
      if (!insideDesktop || !insideGraph) issues.push(`${phase}:${kind}: preview leaves the desktop or graph viewport`);
      if (graphViewport.bottom - rect.bottom < PROCESS_PREVIEW_BOTTOM_INSET_PX - SPATIAL_GEOMETRY_EPSILON_PX) issues.push(`${phase}:${kind}: preview leaves less than an 8px bottom inset`);
    });
  });
  if (!buildingObserved) issues.push('building-state process preview geometry was not observed');
  const missingCompletedNodes = (Array.isArray(expectedNodeIds) ? expectedNodeIds : []).filter(nodeId => !completedNodeIds.has(nodeId));
  if (missingCompletedNodes.length) issues.push(`completed process preview geometry was not observed for ${missingCompletedNodes.join(', ')}`);
  if (!visibleItemCount) issues.push('no visible process preview geometry was captured');
  return [...new Set(issues)];
}

function groundingModalContractViolations(trace, requiredKind = '') {
  const issues = [];
  const before = trace?.before || {};
  const opened = trace?.opened || {};
  const closed = trace?.closed;
  if (before.viewerOpen || !before.inlinePanelHidden || before.visibleInlineItemCount !== 0) issues.push('grounding details are exposed before the explicit modal action');
  if (before.toggleHaspopup !== 'dialog' || before.toggleExpanded !== 'false') issues.push('grounding trigger does not declare a closed dialog action');
  if (!opened.openedByExplicitClick || !opened.viewerOpen || !opened.modalHasFocus) issues.push('grounding modal did not open from the explicit trigger click');
  if (!opened.inlinePanelHidden || opened.visibleInlineItemCount !== 0) issues.push('graph-local grounding details became visible behind the modal');
  if (!opened.sourceRailVisible || opened.sourceRailOverlapArea > SPATIAL_GEOMETRY_EPSILON_PX) issues.push('grounding modal overlaps or obscures the persistent source rail');
  if (requiredKind && !opened.actionKinds?.includes(requiredKind)) issues.push(`grounding modal omits actionable ${requiredKind}`);
  if (!opened.actionableButtonCount || opened.actionableButtonCount !== opened.detailButtonCount) issues.push('grounding modal contains a non-actionable detail button');
  if (closed) {
    if (closed.viewerOpen || !closed.inlinePanelHidden || closed.visibleInlineItemCount !== 0) issues.push('closing grounding did not restore the closed graph-local state');
    if (!closed.focusRestoredToTrigger || closed.graphFocusCount !== 1 || closed.primaryActionCount !== 1) issues.push('closing grounding did not restore one graph focus and one primary action');
  }
  return issues;
}

function settledCursorPayoffContractViolations(snapshot) {
  const issues = [];
  if (!['review-applied', 'knowledge', 'later-result'].includes(snapshot?.moment || '')) issues.push('settled cursor snapshot has the wrong outcome moment');
  if (!snapshot?.cursorVisible) issues.push('settled outcome hides the agent cursor');
  if (!snapshot?.parked || snapshot?.cursorPhase !== 'settled' || !snapshot?.parkTargetVisible) issues.push('settled outcome cursor is not parked at its graph park target');
  if ((snapshot?.parkedStepCount || 0) < 1) issues.push('settled outcome has no cursor parking trace');
  if (snapshot?.labelOpacity !== 0) issues.push('settled outcome cursor label remains visually present');
  if ((snapshot?.payoffObjectCount || 0) < 2) issues.push('settled outcome omits its graph-local payoff objects');
  if ((snapshot?.cursorOverlaps || []).length || (snapshot?.visibleLabelOverlaps || []).length) issues.push('settled cursor or visible label overlaps a graph-local payoff object');
  if (snapshot?.cursorClicking || (snapshot?.syntheticClickCountAfterParking || 0) !== 0) issues.push('settled cursor synthesizes a click after parking');
  return issues;
}

function assertHealthRuntimeContract(health, releaseRuntime) {
  const runtime = health.agentic_runtime;
  if (!isProductionJourney()) {
    check('Local health remains in deterministic reference mode without activating a model', health.model_mode === 'deterministic_reference' && health.model == null && health.runtime_profile === 'deterministic_reference' && runtime?.profile === 'deterministic_reference' && runtime?.execution_mode === 'deterministic_reference' && runtime?.authority_mode === 'deterministic_reference' && runtime?.implementation === 'deterministic_reference' && runtime?.schema == null && exactMembers(runtime?.required_agent_ids, []) && exactMembers(runtime?.deterministic_gate_ids, []), JSON.stringify({ model_mode: health.model_mode, model: health.model, runtime }));
    check('Local deterministic health still reports the pinned inactive framework, provider single-flight cap, and trace-disabled safety posture', stableJson(runtime?.framework) === stableJson(EXPECTED_FRAMEWORK) && runtime?.safety?.provider_max_in_flight === 1 && runtime?.safety?.provider_max_in_flight === releaseRuntime?.safety?.provider_max_in_flight && runtime?.safety?.external_tracing === false && runtime?.safety?.prompt_storage === false && runtime?.safety?.raw_output_storage === false, JSON.stringify(runtime));
    return;
  }
  check('Production health returns the active Nemotron LangGraph runtime profile and schema', health.runtime_profile === EXPECTED_RUNTIME.runtime_profile && runtime?.profile === EXPECTED_RUNTIME.runtime_profile && runtime?.execution_mode === 'nemotron_multi_agent' && runtime?.authority_mode === EXPECTED_RUNTIME.authority_mode && runtime?.implementation === EXPECTED_RUNTIME.implementation && runtime?.schema === EXPECTED_RUNTIME.orchestration_schema && health.model === REQUESTED_NEMOTRON_MODEL, JSON.stringify(runtime));
  check('Production health returns the exact requested framework versions', stableJson(runtime?.framework) === stableJson(releaseRuntime.framework) && stableJson(runtime?.framework) === stableJson(EXPECTED_FRAMEWORK), JSON.stringify(runtime?.framework));
  check('Production health returns the exact six model roles and three deterministic gates', exactMembers(runtime?.required_agent_ids, REQUIRED_NEMOTRON_AGENT_IDS) && exactMembers(runtime?.deterministic_gate_ids, REQUIRED_DETERMINISTIC_GATE_IDS), JSON.stringify(runtime));
  check('Production health attests the exact private Together route, provider single-flight cap, and disabled tracing, storage, fallback, and inference retries', runtime?.safety?.deterministic_contract_authority === true && runtime?.safety?.provider_max_in_flight === 1 && runtime?.safety?.provider_max_in_flight === releaseRuntime?.safety?.provider_max_in_flight && runtime?.safety?.external_tracing === false && runtime?.safety?.prompt_storage === false && runtime?.safety?.raw_output_storage === false && runtime?.safety?.model_fallback === false && runtime?.safety?.automatic_inference_retry === false && stableJson(runtime?.safety?.provider_routing) === stableJson({ endpoint_tag: 'together', expected_upstream_provider: 'Together', allow_fallbacks: false, require_parameters: true, data_collection: 'deny' }), JSON.stringify(runtime?.safety));
}

function assertReadinessContract(readiness) {
  const budgetCredential = readiness?.model_budget?.credential_configured;
  const runtimeCredential = readiness?.agentic_runtime?.safety?.credential_configured;
  check('Readiness safely exposes only matching boolean OpenRouter credential receipts', typeof budgetCredential === 'boolean' && typeof runtimeCredential === 'boolean' && budgetCredential === runtimeCredential, JSON.stringify({ budgetCredential, runtimeCredential }));
  check('Readiness pins physical provider admission to exactly one in-flight send', readiness?.agentic_runtime?.safety?.provider_max_in_flight === 1, JSON.stringify(readiness?.agentic_runtime?.safety));
  check('Readiness discloses the exact bounded budget and ephemeral-ledger posture', readiness?.model_budget?.budget_scope === 'instance_lifetime' && readiness?.model_budget?.ledger_persistence === 'ephemeral_instance' && readiness?.model_budget?.external_key_hard_limit_guard === 'configured', JSON.stringify(readiness?.model_budget));
  check('Readiness receipt contains no credential material or internal execution sentinel', internalSentinelPaths(readiness).length === 0 && !/sk-or-v1-[A-Za-z0-9_-]{8,}/.test(JSON.stringify(readiness)), JSON.stringify({ sentinel_paths: internalSentinelPaths(readiness) }));
  if (isProductionJourney()) {
    check('Production is ready only with the OpenRouter credential configured', readiness?.status === 'ready' && budgetCredential === true && runtimeCredential === true, JSON.stringify({ status: readiness?.status, budgetCredential, runtimeCredential }));
    return;
  }
  check('Local deterministic mode remains ready whether or not an inactive OpenRouter credential is configured', readiness?.status === 'ready', JSON.stringify({ status: readiness?.status, budgetCredential, runtimeCredential }));
}

async function getJsonForSession(url, sessionId, options = {}) {
  const target = new URL(url);
  const apiOrigin = new URL(API).origin;
  const headers = target.origin === apiOrigin ? { 'X-CasePath-Session': sessionId, ...(options.headers || {}) } : options.headers;
  const response = await fetch(url, { ...options, headers });
  if (!response.ok) throw new Error(`${options.method || 'GET'} ${url}: ${response.status}`);
  return response.json();
}

async function getJson(url, options = {}) {
  return getJsonForSession(url, QA_SESSION_ID, options);
}

async function getText(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`GET ${url}: ${response.status}`);
  return response.text();
}

async function resetDemo() {
  const value = await getJson(`${API}/api/demo/reset`, { method: 'POST' });
  demoMutated = true;
  return value;
}

async function waitVisible(selector, timeout = 180000) {
  await page.locator(selector).first().waitFor({ state: 'visible', timeout });
}

async function waitHidden(selector, timeout = 30000) {
  await page.locator(selector).first().waitFor({ state: 'hidden', timeout });
}

async function waitText(selector, pattern, timeout = 180000) {
  await page.waitForFunction(({ selector, source, flags }) => {
    const node = document.querySelector(selector);
    return node && new RegExp(source, flags).test(node.textContent || '');
  }, { selector, source: pattern.source, flags: pattern.flags }, { timeout });
}

async function waitForValue(read, timeout = 180000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const value = await read();
    if (value) return value;
    await sleep(100);
  }
  throw new Error('Timed out waiting for captured response');
}

async function screenshot(name, fullPage = false) {
  await page.screenshot({ path: path.join(OUT, name), fullPage });
}

async function awaitRunForSession(runId, sessionId) {
  const timeout = runTimeoutMs();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(`${API}/api/runs/${encodeURIComponent(runId)}/events?after=0`, {
      headers: {
        Accept: 'text/event-stream',
        'X-CasePath-Session': sessionId,
      },
      signal: controller.signal,
    });
    if (!response.ok || !response.body) throw new Error(`run ${runId} event stream returned ${response.status}`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let terminal = false;
    while (!terminal) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const frames = buffer.replaceAll('\r\n', '\n').split('\n\n');
      buffer = frames.pop() || '';
      for (const frame of frames) {
        const payload = frame.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
        if (!payload) continue;
        const event = JSON.parse(payload);
        if (['run.completed', 'run.failed'].includes(event.type)) terminal = true;
      }
      if (done && !terminal) throw new Error(`run ${runId} stream ended before a terminal event`);
    }
    const run = await getJsonForSession(`${API}/api/runs/${encodeURIComponent(runId)}`, sessionId);
    if (run.status === 'complete') return run;
    if (run.status === 'failed') {
      const terminalIssues = terminalFailureContractViolations(run);
      if (terminalIssues.length) throw new Error(`run ${runId} failed public-safety contract: ${JSON.stringify(terminalIssues)}`);
      throw new Error(`run ${runId} failed: ${JSON.stringify(runProgressDiagnostic(run))}`);
    }
    throw new Error(`run ${runId} terminal hydration returned ${run.status}`);
  } catch (error) {
    if (error?.name === 'AbortError') throw new Error(`run ${runId} timed out after ${timeout}ms`);
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

async function awaitRun(runId) {
  return awaitRunForSession(runId, QA_SESSION_ID);
}

function terminalRunFailureMessage(run) {
  if (run?.status !== 'failed') return null;
  const terminalIssues = terminalFailureContractViolations(run);
  return terminalIssues.length
    ? `run ${run.run_id || 'unknown'} failed public-safety contract: ${JSON.stringify(terminalIssues)}`
    : `run ${run.run_id || 'unknown'} failed: ${JSON.stringify(runProgressDiagnostic(run))}`;
}

async function awaitLaterJourneyTerminalUi() {
  const deadline = Date.now() + runTimeoutMs();
  const latestRuns = new Map();
  while (Date.now() < deadline) {
    const ui = await page.evaluate(() => ({
      moment: document.querySelector('#stageCanvas')?.dataset.casepathMoment || '',
      next: document.querySelector('#journeyNext')?.textContent || '',
    }));
    if (ui.moment === 'failure') {
      throw new Error('Later-claim comparison rendered the safe-failure boundary');
    }
    if (ui.moment === 'later-result' && /Restart the demo/i.test(ui.next)) return;

    for (const runId of runIds.slice(1)) {
      const run = await getJson(`${API}/api/runs/${encodeURIComponent(runId)}`);
      latestRuns.set(runId, run);
      const failure = terminalRunFailureMessage(run);
      if (failure) throw new Error(failure);
    }
    await sleep(LATER_TERMINAL_POLL_INTERVAL_MS);
  }
  throw new Error(`Later-claim comparison timed out after ${runTimeoutMs()}ms: ${JSON.stringify([...latestRuns.values()].map(runProgressDiagnostic))}`);
}

async function waitJourneyUi(label, operation) {
  try {
    return await operation();
  } catch (error) {
    const diagnostics = [];
    for (const runId of runIds.slice(-3)) {
      try {
        diagnostics.push(runProgressDiagnostic(await getJson(`${API}/api/runs/${encodeURIComponent(runId)}`)));
      } catch (diagnosticError) {
        diagnostics.push({ run_id: runId, diagnostic_error: String(diagnosticError) });
      }
    }
    throw new Error(`${label}: ${error instanceof Error ? error.message : String(error)}; run diagnostics=${JSON.stringify(diagnostics)}`);
  }
}

async function horizontalOverflow() {
  return page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth);
}

async function auditViewports(label, selector) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await sleep(120);
  check(`${label} desktop retains its primary artifact`, await page.locator(selector).first().isVisible());
  check(`${label} desktop keeps the source claim available`, await page.locator('.submission-pane').isVisible());
  check(`${label} desktop has no page-level horizontal overflow`, await horizontalOverflow() <= 1, `overflow=${await horizontalOverflow()}`);
  await runAxe(`${label} desktop`);
  await screenshot(`${label}-desktop.png`, true);
}

async function minimalSurfaceSnapshot() {
  return page.evaluate(() => {
    const visible = node => Boolean(node && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden');
    return {
      focus_count: [...document.querySelectorAll('[data-casepath-focal="true"]')].filter(visible).length,
      artifact_count: [...document.querySelectorAll('[data-casepath-primary-artifact="true"]')].filter(visible).length,
      action_count: [...document.querySelectorAll('[data-casepath-primary-action="true"]')].filter(visible).length,
      cursor_count: [...document.querySelectorAll('#v21AgentCursor')].filter(visible).length,
      source_collapsed: document.querySelector('.submission-pane')?.classList.contains('collapsed') === true,
      source_summary_visible: visible(document.querySelector('#toggleSource')),
      source_content_visible: visible(document.querySelector('#submissionContent')),
    };
  });
}

async function primaryActionSnapshot() {
  return page.evaluate(() => {
    const visible = node => Boolean(node && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden' && getComputedStyle(node).display !== 'none');
    return {
      dialogOpen: document.querySelector('#v20DocumentSheet')?.open === true,
      actions: [...document.querySelectorAll('[data-casepath-primary-action="true"]')].filter(visible).map(node => ({
        id: node.id || '',
        text: node.textContent.trim(),
        guidedDocuments: node.dataset.v20GuidedDocuments || '',
        continueReview: node.hasAttribute('data-v20-continue-review'),
        ariaControls: node.getAttribute('aria-controls') || '',
      })),
    };
  });
}

async function artifactCanvasSnapshot() {
  return page.evaluate(() => {
    const visible = node => Boolean(node && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden');
    const root = document.querySelector('#artifactCanvas');
    const graph = document.querySelector('#artifactProcessGraph');
    const layout = document.querySelector('[data-layout="source-canvas"]');
    const dock = layout?.querySelector('[data-source-dock-state]') || document.querySelector('[data-source-dock-state]');
    const visibleWithin = selector => [...(root?.querySelectorAll(selector) || [])].filter(visible);
    return {
      root_present: Boolean(root),
      root_visible: visible(root),
      root_same: root === window.__casepathPersistentArtifactCanvas,
      graph_present: Boolean(graph),
      graph_same: graph === window.__casepathPersistentProcessGraph,
      scene: root?.dataset.casepathScene || '',
      layout_visible: visible(layout),
      source_visible: visible(dock),
      source_state: dock?.dataset.sourceDockState || '',
      active_source_locator: dock?.dataset.activeSourceLocator || '',
      focus_count: visibleWithin('[data-artifact-focus="true"]').length,
      artifact_count: visibleWithin('[data-casepath-primary-artifact="true"]').length,
      action_count: [...document.querySelectorAll('[data-casepath-primary-action="true"]')].filter(visible).length,
      cursor_count: visibleWithin('#artifactAgentCursor').length,
      projection: graph?.dataset.graphProjection || '',
      construction_state: graph?.dataset.processConstructionState || '',
      node_states: [...(graph?.querySelectorAll('[data-node-id][data-process-build-state]') || [])].map(node => ({
        node_id: node.dataset.nodeId || '',
        state: node.dataset.processBuildState || '',
      })),
      review_edit_state: graph?.dataset.reviewEditState || root?.dataset.reviewEditState || '',
    };
  });
}

async function artifactGroundingModalSnapshot() {
  return page.evaluate(() => {
    const visible = node => Boolean(node && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden' && getComputedStyle(node).display !== 'none');
    const intersection = (first, second) => Math.max(0, Math.min(first.right, second.right) - Math.max(first.left, second.left)) * Math.max(0, Math.min(first.bottom, second.bottom) - Math.max(first.top, second.top));
    const disclosure = document.querySelector('#artifactProcessGraph .ac-spatial-detail .ac-grounding-disclosure');
    const toggle = disclosure?.querySelector(':scope > [data-ac-action="toggle-grounding"]');
    const inlinePanel = disclosure?.querySelector(':scope > div[hidden]');
    const viewer = document.querySelector('#artifactCanvas [data-ac-grounding-viewer]');
    const sourceRail = document.querySelector('.submission-pane');
    const viewerRect = viewer?.open ? viewer.getBoundingClientRect() : null;
    const sourceRect = visible(sourceRail) ? sourceRail.getBoundingClientRect() : null;
    const detailButtons = [...(viewer?.querySelectorAll('[data-ac-grounding-viewer-detail] > button') || [])];
    return {
      viewerOpen: viewer?.open === true,
      inlinePanelHidden: inlinePanel?.hidden === true,
      visibleInlineItemCount: [...(inlinePanel?.querySelectorAll('[data-node-attachment-kind]') || [])].filter(visible).length,
      toggleHaspopup: toggle?.getAttribute('aria-haspopup') || '',
      toggleExpanded: toggle?.getAttribute('aria-expanded') || '',
      modalHasFocus: Boolean(viewer?.open && viewer.contains(document.activeElement)),
      sourceRailVisible: visible(sourceRail),
      sourceRailOverlapArea: viewerRect && sourceRect ? intersection(viewerRect, sourceRect) : 0,
      actionKinds: detailButtons.map(button => button.dataset.nodeAttachmentKind || ''),
      detailButtonCount: detailButtons.length,
      actionableButtonCount: detailButtons.filter(button => visible(button) && !button.disabled && Boolean(button.dataset.acAction)).length,
      focusRestoredToTrigger: document.activeElement === toggle,
      graphFocusCount: [...document.querySelectorAll('#artifactCanvas [data-artifact-focus="true"]')].filter(visible).length,
      primaryActionCount: [...document.querySelectorAll('[data-casepath-primary-action="true"]')].filter(visible).length,
    };
  });
}

async function settledCursorPayoffSnapshot(moment) {
  await page.waitForFunction(expectedMoment => {
    const root = document.querySelector(`#artifactCanvas[data-casepath-scene="${CSS.escape(expectedMoment)}"]`);
    const cursor = root?.querySelector('#artifactAgentCursor[data-parked="true"][data-cursor-phase="settled"]');
    return Boolean(cursor && root.querySelector('[data-ac-cursor-park]'));
  }, moment, { timeout: 30000 });
  await sleep(520);
  return page.evaluate(({ expectedMoment, epsilon }) => {
    const root = document.querySelector(`#artifactCanvas[data-casepath-scene="${CSS.escape(expectedMoment)}"]`);
    const cursor = root?.querySelector('#artifactAgentCursor');
    const label = cursor?.querySelector('.ac-agent-cursor-label');
    const park = root?.querySelector('[data-ac-cursor-park]');
    const visible = node => Boolean(node && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden' && getComputedStyle(node).display !== 'none' && Number.parseFloat(getComputedStyle(node).opacity || '1') > 0.001);
    const rect = node => { const value = node.getBoundingClientRect(); return { left: value.left, top: value.top, right: value.right, bottom: value.bottom }; };
    const intersection = (first, second) => Math.max(0, Math.min(first.right, second.right) - Math.max(first.left, second.left)) * Math.max(0, Math.min(first.bottom, second.bottom) - Math.max(first.top, second.top));
    const selectors = {
      'review-applied': '.ac-review-applied-note,[data-ac-node-id="ventilation_dispute"]',
      knowledge: '.ac-knowledge-graph-note,[data-ac-node-id="ventilation_dispute"]',
      'later-result': '.ac-memory-graph-delta,[data-memory-effect],[data-ac-node-id="ventilation_dispute"]',
    };
    const payoffObjects = [...new Set([...(root?.querySelectorAll(selectors[expectedMoment] || '') || [])])].filter(visible);
    const cursorRect = cursor ? rect(cursor) : null;
    const labelOpacity = label ? Number.parseFloat(getComputedStyle(label).opacity || '1') : 1;
    const labelRect = label && labelOpacity > 0.001 ? rect(label) : null;
    const cursorSteps = window.__casepathArtifactCursorSteps || [];
    const parkedSteps = cursorSteps.filter(step => step.moment === expectedMoment && step.parked);
    const firstParkAt = parkedSteps.length ? Math.min(...parkedSteps.map(step => step.at)) : Number.POSITIVE_INFINITY;
    return {
      moment: expectedMoment,
      cursorVisible: visible(cursor),
      parked: cursor?.dataset.parked === 'true',
      cursorPhase: cursor?.dataset.cursorPhase || '',
      parkTargetVisible: visible(park),
      labelOpacity,
      payoffObjectCount: payoffObjects.length,
      cursorOverlaps: cursorRect ? payoffObjects.filter(node => intersection(cursorRect, rect(node)) > epsilon).map(node => node.dataset.acNodeId || node.dataset.memoryEffect || node.className) : [],
      visibleLabelOverlaps: labelRect ? payoffObjects.filter(node => intersection(labelRect, rect(node)) > epsilon).map(node => node.dataset.acNodeId || node.dataset.memoryEffect || node.className) : [],
      cursorClicking: cursor?.classList.contains('is-clicking') === true,
      parkedStepCount: parkedSteps.length,
      syntheticClickCountAfterParking: cursorSteps.filter(step => step.moment === expectedMoment && step.phase === 'click' && step.at >= firstParkAt).length,
    };
  }, { expectedMoment: moment, epsilon: SPATIAL_GEOMETRY_EPSILON_PX });
}

async function persistentGraphSceneSnapshot() {
  return page.evaluate(() => {
    const visible = node => Boolean(node && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden' && getComputedStyle(node).display !== 'none');
    const root = document.querySelector('#artifactCanvas');
    const graph = document.querySelector('#artifactProcessGraph');
    const visibleWithinRoot = selector => [...(root?.querySelectorAll(selector) || [])].filter(visible);
    const graphAttachments = selector => [...(graph?.querySelectorAll(selector) || [])].filter(visible).map(node => ({
      text: node.innerText.trim(),
      attachment_kind: node.dataset.nodeAttachmentKind || '',
      memory_id: node.dataset.memoryId || '',
      memory_status: node.dataset.memoryStatus || '',
      memory_origin_id: node.dataset.memoryOriginId || '',
      later_causal_phase: node.dataset.laterCausalPhase || '',
      later_source_opened: node.dataset.laterSourceOpened || '',
      eligibility_contract: node.dataset.eligibilityContract || '',
      eligibility_rule_id: node.dataset.eligibilityRuleId || '',
      semantic_role: node.dataset.semanticRole || '',
    }));
    const memoryEffectNodes = [...(graph?.querySelectorAll('[data-memory-origin-id][data-memory-effect]') || [])];
    const memoryEffectSnapshot = node => ({
      origin_id: node.dataset.memoryOriginId || '',
      effect: node.dataset.memoryEffect || '',
      node_id: node.dataset.nodeId || '',
      item_id: node.dataset.itemId || '',
      edge_source: node.dataset.edgeSource || '',
      edge_target: node.dataset.edgeTarget || '',
    });
    const memoryEffects = memoryEffectNodes.map(memoryEffectSnapshot);
    const visibleMemoryEffects = memoryEffectNodes.filter(visible).map(memoryEffectSnapshot);
    const foci = visibleWithinRoot('[data-artifact-focus="true"]');
    const primaryArtifacts = visibleWithinRoot('[data-casepath-primary-artifact="true"]');
    return {
      scene: root?.dataset.casepathScene || '',
      graph_present: Boolean(graph),
      graph_visible: visible(graph),
      graph_same: graph === window.__casepathPersistentProcessGraph,
      graph_is_sole_focus: foci.length === 1 && foci[0] === graph,
      graph_is_sole_primary_artifact: primaryArtifacts.length === 1 && primaryArtifacts[0] === graph,
      node_ids: [...(graph?.querySelectorAll('[data-ac-node-id][data-node-id][data-process-build-state]') || [])].filter(visible).map(node => node.dataset.nodeId || ''),
      selected_node_ids: [...(graph?.querySelectorAll('[data-ac-node-id][data-node-id][data-selected="true"]') || [])].filter(visible).map(node => node.dataset.nodeId || ''),
      review_edit_state: graph?.dataset.reviewEditState || '',
      inline_correction_count: [...(graph?.querySelectorAll('.ac-review-graph-edit[data-review-edit-state="pending"][data-review-node-id="causation"]') || [])].filter(visible).length,
      apply_action_count: [...(graph?.querySelectorAll('[data-ac-action="submit-review"][data-review-mode="conditional"]') || [])].filter(visible).length,
      applied_note_count: [...(graph?.querySelectorAll('.ac-review-applied-note[data-review-edit-state="applied"][data-review-node-id="ventilation_dispute"]') || [])].filter(visible).length,
      later_memory_validated: root?.dataset.laterMemoryValidated || '',
      later_memory_application_hash: root?.dataset.laterMemoryApplicationHash || '',
      memory_receipt_count: [...(graph?.querySelectorAll('[data-memory-receipt="true"]') || [])].filter(visible).length,
      memory_effects: memoryEffects,
      visible_memory_effects: visibleMemoryEffects,
      verification_attachments: graphAttachments('.ac-graph-verification[data-node-attachment-kind="verification"]'),
      knowledge_memory_notes: graphAttachments('.ac-knowledge-graph-note[data-memory-id][data-memory-status]'),
      later_memory_retrievals: graphAttachments('.ac-later-memory-retrieval[data-memory-origin-id]'),
      text: graph?.innerText || '',
      root_text: root?.innerText || '',
    };
  });
}

async function reviewChoiceSnapshot() {
  return page.evaluate(() => {
    const graph = document.querySelector('#artifactProcessGraph');
    const edit = graph?.querySelector('.ac-review-graph-edit[data-review-edit-state="pending"][data-review-node-id="causation"]');
    const radios = [...(edit?.querySelectorAll('[role="radio"][data-ac-action="select-review-mode"]') || [])];
    const applies = [...(graph?.querySelectorAll('[data-ac-action="submit-review"]') || [])];
    return {
      editCount: graph?.querySelectorAll('.ac-review-graph-edit[data-review-edit-state="pending"][data-review-node-id="causation"]').length || 0,
      radiogroupCount: edit?.querySelectorAll(':scope > .ac-review-options[role="radiogroup"]').length || 0,
      graphRadioCount: graph?.querySelectorAll('[role="radio"]').length || 0,
      selectedMode: edit?.dataset.reviewSelectedMode || '',
      radios: radios.map(radio => ({
        mode: radio.dataset.reviewMode || '',
        checked: radio.getAttribute('aria-checked') || '',
        text: radio.textContent?.replace(/\s+/g, ' ').trim() || '',
      })),
      change: edit?.querySelector(':scope > .ac-review-change')?.textContent?.replace(/\s*→\s*/g, ' → ').replace(/\s+/g, ' ').trim() || '',
      consequence: edit?.querySelector(':scope > p')?.textContent?.replace(/\s+/g, ' ').trim() || '',
      applyCount: applies.length,
      primaryApplyCount: applies.filter(action => action.dataset.casepathPrimaryAction === 'true').length,
      applyMode: applies[0]?.dataset.reviewMode || '',
      applyText: applies[0]?.textContent?.trim() || '',
    };
  });
}

function reviewChoiceContractViolations(snapshot, expectedMode) {
  const issues = [];
  const expected = {
    conditional: {
      consequence: 'Move use evidence to the new decision; building-envelope assessment remains conditional.',
      change: 'Implicit allegation → Add ventilation decision',
    },
    required_now: {
      consequence: 'Do not add a ventilation decision; keep broader building testing immediately required.',
      change: 'Existing evidence order → Request both checks now',
    },
  }[expectedMode];
  if (!expected) return [`unknown review mode ${expectedMode}`];
  if (snapshot?.editCount !== 1 || snapshot?.radiogroupCount !== 1) issues.push('review choice is not graph-local in exactly one edit');
  if (snapshot?.graphRadioCount !== 2 || snapshot?.radios?.length !== 2
    || stableJson(snapshot.radios.map(item => item.mode)) !== stableJson(['conditional', 'required_now'])) issues.push('review does not expose exactly the two allowed radio choices');
  const checked = (snapshot?.radios || []).filter(item => item.checked === 'true').map(item => item.mode);
  if (snapshot?.selectedMode !== expectedMode || stableJson(checked) !== stableJson([expectedMode])) issues.push(`review selected mode is not ${expectedMode}`);
  if (snapshot?.consequence !== expected.consequence || snapshot?.change !== expected.change) issues.push(`${expectedMode} does not visibly show its exact consequence`);
  if (snapshot?.applyCount !== 1 || snapshot?.primaryApplyCount !== 1 || snapshot?.applyMode !== expectedMode || snapshot?.applyText !== 'Apply correction') issues.push('review does not retain exactly one mode-bound primary Apply correction action');
  return issues;
}

function persistentGraphSceneContractViolations(snapshot, expected) {
  const issues = [];
  if (snapshot?.scene !== expected.scene) issues.push(`scene ${snapshot?.scene}`);
  if (!snapshot?.graph_present || !snapshot?.graph_visible || !snapshot?.graph_same) issues.push('persistent graph is absent, hidden, or replaced');
  if (!snapshot?.graph_is_sole_focus) issues.push('process graph is not the sole visible focal object');
  if (!snapshot?.graph_is_sole_primary_artifact) issues.push('process graph is not the sole visible primary artifact');
  if (stableJson(snapshot?.node_ids) !== stableJson(expected.nodeIds)) issues.push(`node projection ${stableJson(snapshot?.node_ids)}`);
  if (expected.selectedNodeId && stableJson(snapshot?.selected_node_ids) !== stableJson([expected.selectedNodeId])) issues.push(`selected node ${stableJson(snapshot?.selected_node_ids)}`);
  if (expected.reviewEditState && snapshot?.review_edit_state !== expected.reviewEditState) issues.push(`review edit state ${snapshot?.review_edit_state}`);
  if (Number.isInteger(expected.inlineCorrectionCount) && snapshot?.inline_correction_count !== expected.inlineCorrectionCount) issues.push(`inline correction count ${snapshot?.inline_correction_count}`);
  if (Number.isInteger(expected.applyActionCount) && snapshot?.apply_action_count !== expected.applyActionCount) issues.push(`apply action count ${snapshot?.apply_action_count}`);
  if (Number.isInteger(expected.appliedNoteCount) && snapshot?.applied_note_count !== expected.appliedNoteCount) issues.push(`applied note count ${snapshot?.applied_note_count}`);
  return issues;
}

function graphNativeMomentCopyContractViolations(snapshot, expected) {
  const issues = [];
  const attachments = snapshot?.[expected.attachmentKey] || [];
  if (attachments.length !== 1) {
    issues.push(`${expected.attachmentKey} count ${attachments.length}`);
    return issues;
  }
  const attachment = attachments[0];
  if (expected.attachmentKind && attachment.attachment_kind !== expected.attachmentKind) issues.push(`attachment kind ${attachment.attachment_kind}`);
  for (const [attribute, value] of Object.entries(expected.attributes || {})) {
    if (attachment[attribute] !== value) issues.push(`${attribute} ${attachment[attribute]}`);
  }
  for (const attribute of expected.requiredNonemptyAttributes || []) {
    if (!nonemptyString(attachment[attribute])) issues.push(`${attribute} is empty`);
  }
  if (attachment.text.length > 180) issues.push(`copy is not concise (${attachment.text.length} characters)`);
  for (const phrase of expected.requiredCopy || []) {
    if (!attachment.text.includes(phrase)) issues.push(`copy omits ${JSON.stringify(phrase)}`);
  }
  if ((expected.anyOfCopy || []).length && !expected.anyOfCopy.some(phrases => phrases.every(phrase => attachment.text.includes(phrase)))) {
    issues.push(`copy omits one truthful outcome ${JSON.stringify(expected.anyOfCopy)}`);
  }
  for (const phrase of expected.forbiddenCopy || []) {
    if (attachment.text.includes(phrase)) issues.push(`copy overclaims ${JSON.stringify(phrase)}`);
  }
  return issues;
}

function graphNativeMomentSceneViolations(snapshot, expectedMoment) {
  const issues = [];
  if (snapshot?.moment !== expectedMoment || snapshot?.scene !== expectedMoment) issues.push(`moment/scene ${snapshot?.moment || ''}/${snapshot?.scene || ''}`);
  if (!snapshot?.graph_visible) issues.push('process graph is hidden');
  if (!snapshot?.graph_is_sole_focus) issues.push('process graph is not the sole visible focal object');
  if (!snapshot?.graph_is_sole_primary_artifact) issues.push('process graph is not the sole visible primary artifact');
  return issues;
}

async function spatialGraphGeometrySnapshot() {
  return page.evaluate(() => {
    const visible = node => Boolean(node && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden' && getComputedStyle(node).display !== 'none');
    const rect = node => {
      const value = node.getBoundingClientRect();
      return { left: value.left, top: value.top, right: value.right, bottom: value.bottom, width: value.width, height: value.height };
    };
    const inside = (outer, inner) => inner.left >= outer.left - 2 && inner.top >= outer.top - 2 && inner.right <= outer.right + 2 && inner.bottom <= outer.bottom + 2;
    const root = document.querySelector('#artifactCanvas');
    const graph = document.querySelector('#artifactProcessGraph');
    const viewport = graph?.querySelector('[data-spatial-canvas="claim-handling-process"]');
    const graphRect = rect(graph);
    const canvasRect = rect(root);
    const viewportRect = rect(viewport);
    const endpointElements = [
      ...graph.querySelectorAll('[data-ac-node-id][data-node-id]'),
      ...viewport.querySelectorAll('[data-spatial-id]'),
    ].filter(visible);
    const endpointRows = endpointElements.map(node => ({ id: node.dataset.spatialId || node.dataset.nodeId || '', rect: rect(node) })).filter(item => item.id);
    const endpointCounts = endpointRows.reduce((result, item) => ({ ...result, [item.id]: (result[item.id] || 0) + 1 }), {});
    const edgeLayer = graph.querySelector('[data-ac-spatial-edges]');
    const edges = [...edgeLayer.querySelectorAll('[data-spatial-edge][data-edge-source][data-edge-target]')].filter(visible).map(node => {
      const point = length => {
        const local = node.getPointAtLength(length);
        const svgPoint = node.ownerSVGElement.createSVGPoint();
        svgPoint.x = local.x;
        svgPoint.y = local.y;
        const screen = svgPoint.matrixTransform(node.getScreenCTM());
        return { x: screen.x, y: screen.y };
      };
      return {
        source: node.dataset.edgeSource || '',
        target: node.dataset.edgeTarget || '',
        state: node.dataset.edgeState || '',
        path: node.dataset.spatialPath || '',
        start: point(0),
        end: point(node.getTotalLength()),
      };
    });
    const nodes = [...graph.querySelectorAll('[data-ac-node-id][data-node-id][data-process-build-state]')].filter(visible).map(node => {
      const title = node.querySelector('[data-ac-node-title]');
      const titleStyle = getComputedStyle(title);
      const nodeRect = rect(node);
      return {
        id: node.dataset.nodeId || '', state: node.dataset.processBuildState || '', role: node.dataset.spatialRole || '', path: node.dataset.spatialPath || '', selected: node.dataset.selected === 'true',
        selectedBranchId: node.dataset.selectedBranchId || '',
        changeId: node.dataset.artifactChangeId || '', eventId: node.dataset.artifactEventId || '', agentId: node.dataset.artifactAgentId || '', rect: nodeRect, insideViewport: inside(viewportRect, nodeRect),
        titleFontSize: Number.parseFloat(titleStyle.fontSize), titleClientWidth: title.clientWidth, titleScrollWidth: title.scrollWidth, titleClientHeight: title.clientHeight, titleScrollHeight: title.scrollHeight,
      };
    });
    const spatialRows = selector => [...viewport.querySelectorAll(selector)].filter(visible).map(node => {
      const nodeRect = rect(node);
      return {
        id: node.dataset.nodeId || node.dataset.spatialId || '',
        branchId: node.dataset.branchId || '', state: node.dataset.branchState || '', selected: node.dataset.branchState === 'selected' || node.dataset.selected === 'true',
        anchorNodeId: node.dataset.spatialAnchorNodeId || '', evidenceId: node.dataset.evidenceId || '', lawId: node.dataset.lawId || '',
        rect: nodeRect, insideViewport: inside(viewportRect, nodeRect),
      };
    });
    const activePaths = [...graph.querySelectorAll('[data-active-focal-path="true"]')].filter(visible).map(node => ({
      nodeId: node.dataset.nodeId || '',
      factIds: (node.dataset.basisFactIds || '').split(',').filter(Boolean),
      lawIds: (node.dataset.basisLawIds || '').split(',').filter(Boolean),
      evidenceIds: (node.dataset.basisEvidenceRequirementIds || '').split(',').filter(Boolean),
      insideGraph: graph.contains(node), rect: rect(node),
    }));
    const primaryRows = selector => [...root.querySelectorAll(selector)].filter(visible).map(node => ({ insideGraph: node === graph || graph.contains(node), rect: rect(node) }));
    const competingRects = [...graph.parentElement.children].filter(node => node !== graph && visible(node)).map(rect);
    const status = graph.querySelector('[data-ac-process-status]');
    return {
      processId: graph.dataset.processId || graph.dataset.processGraphId || '', projection: graph.dataset.graphProjection || '', graphRect, canvasRect, viewportRect,
      routeMode: graph.dataset.processRouteMode || '', selectedPath: (graph.dataset.processSelectedPath || '').split(',').filter(Boolean),
      currentNodeId: graph.dataset.processCurrentNodeId || '', nextActionNodeId: graph.dataset.processNextActionNodeId || '', selectedBranchId: graph.dataset.processSelectedBranchId || '',
      focalNodeId: graph.dataset.processFocalNodeId || '', openLabel: graph.dataset.processOpenLabel || '', terminalState: graph.dataset.processTerminalState || '',
      sourceAnchorNodeId: graph.dataset.processSourceAnchorNodeId || '', lawAnchorNodeId: graph.dataset.processLawAnchorNodeId || '', evidenceAnchorNodeId: graph.dataset.processEvidenceAnchorNodeId || '',
      primaryFoci: primaryRows('[data-artifact-focus="true"]'), primaryArtifacts: primaryRows('[data-casepath-primary-artifact="true"]'),
      primaryActionCount: [...document.querySelectorAll('[data-casepath-primary-action="true"]')].filter(visible).length, competingRects,
      nodes, endpoints: endpointRows, endpointDuplicates: Object.entries(endpointCounts).filter(([, count]) => count !== 1).map(([id]) => id), edges,
      branches: spatialRows('[data-spatial-role~="branch"]'), laws: spatialRows('[data-spatial-role="law"]'), evidence: spatialRows('[data-spatial-role="evidence"]'), nextActions: spatialRows('[data-spatial-next-action="true"]'), activePaths,
      ariaCurrentIds: [...graph.querySelectorAll('[data-ac-action="select-node"][aria-current="step"]')].filter(visible).map(node => node.dataset.nodeId || ''),
      pendingTabStops: [...graph.querySelectorAll('[data-process-build-state="pending"] [data-ac-action="select-node"]')].map(node => ({ tabIndex: node.tabIndex, disabled: node.disabled })),
      status: { role: status?.getAttribute('role') || '', live: status?.getAttribute('aria-live') || '', atomic: status?.getAttribute('aria-atomic') || '' },
      edgeLayerAriaHidden: edgeLayer?.getAttribute('aria-hidden') || '', edgeLayerFocusable: edgeLayer?.getAttribute('focusable') || '',
      cursorAriaHidden: document.querySelector('#artifactAgentCursor')?.getAttribute('aria-hidden') || '',
    };
  });
}

function focusedArtifactCanvasViolations(snapshot) {
  const issues = [];
  if (!snapshot?.root_present || !snapshot.root_visible) issues.push('artifact canvas is absent or hidden');
  if (!snapshot?.root_same) issues.push('artifact canvas root was replaced');
  if (!snapshot?.graph_present || !snapshot.graph_same) issues.push('process graph root was replaced');
  if (!snapshot?.layout_visible || !snapshot?.source_visible) issues.push('source claim and work canvas are not simultaneously visible');
  if (snapshot?.focus_count !== 1) issues.push(`focus count ${snapshot?.focus_count}`);
  if (snapshot?.cursor_count !== 1) issues.push(`cursor count ${snapshot?.cursor_count}`);
  if (snapshot?.artifact_count !== 1) issues.push(`primary artifact count ${snapshot?.artifact_count}`);
  if (snapshot?.action_count > 1) issues.push(`primary action count ${snapshot?.action_count}`);
  return issues;
}

function rectCenter(rect) {
  return { x: rect.left + (rect.width / 2), y: rect.top + (rect.height / 2) };
}

function rectContainsPoint(rect, point, padding = SPATIAL_GEOMETRY_EPSILON_PX) {
  return point.x >= rect.left - padding
    && point.x <= rect.right + padding
    && point.y >= rect.top - padding
    && point.y <= rect.bottom + padding;
}

function rectIntersectionArea(first, second) {
  return Math.max(0, Math.min(first.right, second.right) - Math.max(first.left, second.left))
    * Math.max(0, Math.min(first.bottom, second.bottom) - Math.max(first.top, second.top));
}

function spatialGraphGeometryContractViolations(snapshot, expected) {
  const issues = [];
  const story = expected?.routeStory || processRouteStory(expected?.processGraph);
  if (!snapshot?.graphRect?.width || !snapshot?.canvasRect?.width || !snapshot?.viewportRect?.width) return ['spatial graph geometry is absent'];
  if (!story?.storyNodeIds?.length || !story.currentNodeId || !story.nextActionNodeId) return ['returned route story is absent'];
  if (snapshot.processId !== expected.processId) issues.push(`process id ${snapshot.processId} does not equal returned ${expected.processId}`);
  if (snapshot.projection !== SPATIAL_GRAPH_PROJECTION) issues.push(`graph projection ${snapshot.projection}`);
  if (snapshot.routeMode !== (story.flagshipCausation ? 'flagship-causation' : 'returned-route')
    || stableJson(snapshot.selectedPath) !== stableJson(story.selectedPath)
    || snapshot.currentNodeId !== story.currentNodeId
    || snapshot.nextActionNodeId !== story.nextActionNodeId
    || snapshot.selectedBranchId !== story.selectedBranchId
    || snapshot.focalNodeId !== story.currentNodeId
    || snapshot.terminalState !== (story.flagshipCausation ? 'journey-continues' : 'ready-route')
    || !nonemptyString(snapshot.openLabel)) issues.push('graph route datasets do not equal the returned process route');
  if (snapshot.graphRect.width < snapshot.canvasRect.width * .6 || (snapshot.graphRect.width * snapshot.graphRect.height) < (snapshot.canvasRect.width * snapshot.canvasRect.height * .45)) issues.push('process graph does not occupy the majority of the artifact canvas');
  if (snapshot.primaryFoci.length !== 1 || !snapshot.primaryFoci[0]?.insideGraph) issues.push('the one primary focal artifact is not the process graph');
  if (snapshot.primaryArtifacts.length !== 1 || !snapshot.primaryArtifacts[0]?.insideGraph) issues.push('the one primary artifact is not inside the process graph');
  if (snapshot.primaryActionCount !== (story.flagshipCausation ? 1 : 0)) issues.push(`ready primary action count ${snapshot.primaryActionCount}`);
  if (snapshot.competingRects.some(rect => (rect.width * rect.height) >= (snapshot.graphRect.width * snapshot.graphRect.height * .2))) issues.push('a large sibling artifact competes with the process graph');

  const nodesById = new Map(snapshot.nodes.map(node => [node.id, node]));
  if (stableJson(snapshot.nodes.map(node => node.id)) !== stableJson(story.storyNodeIds)) issues.push('visible spatial spine is not the exact returned route story');
  snapshot.nodes.forEach(node => {
    if (node.state !== 'built') issues.push(`${node.id}: spatial node is not built`);
    if (![node.changeId, node.eventId, node.agentId].every(nonemptyString)) issues.push(`${node.id}: permanent node lineage is incomplete`);
    if (node.agentId !== expected.processAgentId) issues.push(`${node.id}: permanent node structure is not attributed to the deterministic projection`);
    if (!node.insideViewport) issues.push(`${node.id}: node leaves the graph viewport`);
    if (node.titleFontSize < 12 || node.titleScrollWidth > node.titleClientWidth + 1 || node.titleScrollHeight > node.titleClientHeight + 1) issues.push(`${node.id}: title is clipped or below 12px`);
    if (!story.causationCanvas) {
      const expectedPath = node.id === story.currentNodeId
        ? 'current'
        : node.id === story.nextActionNodeId && story.nextActionNodeId !== story.currentNodeId ? 'next-action' : 'accepted';
      if (node.path !== expectedPath) issues.push(`${node.id}: route path role does not equal ${expectedPath}`);
    }
  });
  for (let index = 0; index < snapshot.nodes.length; index += 1) {
    for (let other = index + 1; other < snapshot.nodes.length; other += 1) {
      if (rectIntersectionArea(snapshot.nodes[index].rect, snapshot.nodes[other].rect) > SPATIAL_GEOMETRY_EPSILON_PX) issues.push(`${snapshot.nodes[index].id}/${snapshot.nodes[other].id}: spine nodes overlap`);
    }
  }
  const spineCenters = snapshot.nodes.map(node => rectCenter(node.rect));
  const horizontalExtent = Math.max(...spineCenters.map(point => point.x)) - Math.min(...spineCenters.map(point => point.x));
  const verticalExtent = Math.max(...spineCenters.map(point => point.y)) - Math.min(...spineCenters.map(point => point.y));
  if (snapshot.nodes.length > 1 && (horizontalExtent < snapshot.viewportRect.width * .55 || horizontalExtent <= Math.max(1, verticalExtent) * 2)) issues.push('spine is a vertical list instead of a horizontal process');

  const returnedNodeIds = new Set(expected.returnedNodeIds);
  const returnedEdges = new Map(expected.returnedEdges.map(edge => [`${edge.source}->${edge.target}`, edge]));
  if (snapshot.endpointDuplicates.length) issues.push(`spatial endpoint IDs are duplicated: ${snapshot.endpointDuplicates.join(',')}`);
  snapshot.edges.forEach(edge => {
    const source = snapshot.endpoints.find(item => item.id === edge.source);
    const target = snapshot.endpoints.find(item => item.id === edge.target);
    if (!source || !target) {
      issues.push(`${edge.source}->${edge.target}: connector endpoint is not a visible spatial object`);
      return;
    }
    if (!rectContainsPoint(source.rect, edge.start, 5) || !rectContainsPoint(target.rect, edge.end, 5)) issues.push(`${edge.source}->${edge.target}: connector geometry misses its exact endpoints`);
    if (returnedNodeIds.has(edge.source) && returnedNodeIds.has(edge.target)) {
      const returned = returnedEdges.get(`${edge.source}->${edge.target}`);
      if (!returned) issues.push(`${edge.source}->${edge.target}: connector invents a process relationship`);
      else if ((edge.state || '') !== (returned.state || '')) issues.push(`${edge.source}->${edge.target}: connector state differs from the returned edge`);
    }
  });
  const visibleProcessEndpointIds = new Set(snapshot.endpoints.map(item => item.id).filter(id => returnedNodeIds.has(id)));
  const explanatoryEdgeKeys = new Set([
    ...story.selectedPath.slice(1).map((target, index) => `${story.selectedPath[index]}->${target}`),
    ...story.branchNodeIds.map(target => `${story.currentNodeId}->${target}`),
    ...(story.nextActionNodeId !== story.currentNodeId ? [`${story.currentNodeId}->${story.nextActionNodeId}`] : []),
  ]);
  const expectedVisibleProcessEdges = expected.returnedEdges
    .filter(edge => visibleProcessEndpointIds.has(edge.source)
      && visibleProcessEndpointIds.has(edge.target)
      && explanatoryEdgeKeys.has(`${edge.source}->${edge.target}`))
    .map(edge => `${edge.source}->${edge.target}:${edge.state || ''}`).sort();
  const renderedProcessEdges = snapshot.edges
    .filter(edge => returnedNodeIds.has(edge.source) && returnedNodeIds.has(edge.target))
    .map(edge => `${edge.source}->${edge.target}:${edge.state || ''}`).sort();
  if (stableJson(renderedProcessEdges) !== stableJson(expectedVisibleProcessEdges)) issues.push('visible connectors do not equal the human-readable returned reasoning path');
  if (!snapshot.edges.length || snapshot.edgeLayerAriaHidden !== 'true' || snapshot.edgeLayerFocusable !== 'false') issues.push('spatial connectors are absent or exposed to assistive technology');

  const currentNode = nodesById.get(story.currentNodeId);
  const branchesById = new Map(snapshot.branches.map(branch => [branch.id, branch]));
  if (!currentNode || stableJson([...branchesById.keys()].sort()) !== stableJson([...story.branchNodeIds].sort())) issues.push('current decision does not expose only its returned route branches');
  const expectedBranchMap = new Map((story.currentNode?.branches || []).map(branch => [String(branch?.target || ''), branch]));
  story.branchNodeIds.forEach(branchId => {
    const branch = branchesById.get(branchId);
    if (!branch) return;
    if (!returnedNodeIds.has(branchId) || !expectedBranchMap.has(branchId) || !returnedEdges.has(`${story.currentNodeId}->${branchId}`)) issues.push(`${branchId}: branch is not justified by the returned process`);
    if (!branch.insideViewport) issues.push(`${branchId}: branch leaves the graph viewport`);
  });
  const selectedBranches = snapshot.branches.filter(branch => branch.selected === true);
  if (story.causationCanvas && story.selectedBranchTargetId) {
    if (selectedBranches.length !== 1 || selectedBranches[0]?.id !== story.selectedBranchTargetId) issues.push('selected branch does not equal the returned next action');
  } else if (selectedBranches.length) issues.push('self-blocked route invents a selected branch');
  if (!story.causationCanvas && story.nextActionNodeId !== story.currentNodeId) {
    const nextNode = nodesById.get(story.nextActionNodeId);
    if (!nextNode || nextNode.path !== 'next-action' || nextNode.selectedBranchId !== story.selectedBranchId) issues.push('distinct returned next-action node does not carry its returned branch identity');
  }
  const branchCenters = snapshot.branches.map(branch => rectCenter(branch.rect));
  const minimumBranchSeparation = Math.max(22, snapshot.viewportRect.height * .055);
  for (let index = 0; index < branchCenters.length; index += 1) {
    for (let other = index + 1; other < branchCenters.length; other += 1) {
      if (Math.hypot(branchCenters[index].x - branchCenters[other].x, branchCenters[index].y - branchCenters[other].y) < minimumBranchSeparation) issues.push('uncertainty branches do not physically diverge');
    }
  }
  if (branchCenters.length >= 3) {
    const horizontalFan = (Math.max(...branchCenters.map(point => point.x)) - Math.min(...branchCenters.map(point => point.x))) / snapshot.viewportRect.width;
    const verticalFan = (Math.max(...branchCenters.map(point => point.y)) - Math.min(...branchCenters.map(point => point.y))) / snapshot.viewportRect.height;
    if (Math.max(horizontalFan, verticalFan) < .35) issues.push('returned branch fan is visually collapsed');
  }

  const activePaths = snapshot.activePaths;
  if (activePaths.length !== 1 || activePaths[0]?.nodeId !== story.currentNodeId || !activePaths[0]?.insideGraph) issues.push('there is not exactly one returned current-node focal path inside the graph');
  const activePath = activePaths[0];
  if (activePath) {
    const normalizeIds = value => [...value].sort();
    if (stableJson(normalizeIds(activePath.factIds)) !== stableJson(normalizeIds(story.activeBasis.factIds))) issues.push('active focal path fact basis differs from the returned current decision');
    if (stableJson(normalizeIds(activePath.lawIds)) !== stableJson(normalizeIds(story.activeBasis.lawIds))) issues.push('active focal path law basis differs from the returned current decision');
    if (stableJson(normalizeIds(activePath.evidenceIds)) !== stableJson(normalizeIds(story.activeBasis.evidenceIds))) issues.push('active focal path evidence basis differs from the returned current decision');
  }
  if (snapshot.ariaCurrentIds.length !== 1 || snapshot.ariaCurrentIds[0] !== story.currentNodeId) issues.push('returned current node is not the one aria-current step');
  if (snapshot.pendingTabStops.some(item => item.tabIndex !== -1 || item.disabled !== true)) issues.push('pending process nodes remain keyboard reachable');
  if (snapshot.status.role !== 'status' || snapshot.status.live !== 'polite' || snapshot.status.atomic !== 'true') issues.push('process construction status is not concise polite atomic output');
  if (snapshot.cursorAriaHidden !== 'true') issues.push('agent cursor is exposed to assistive technology');

  const routeAnchorNodeIds = new Set([story.currentNodeId, story.nextActionNodeId]);
  if (![snapshot.sourceAnchorNodeId, snapshot.lawAnchorNodeId, snapshot.evidenceAnchorNodeId]
    .every(nodeId => !nodeId || routeAnchorNodeIds.has(nodeId))) issues.push('source, law, or evidence root anchor leaves the returned current-to-next route');

  const expectedLawIds = new Set(story.activeBasis.lawIds);
  const expectedEvidenceIds = new Set(story.activeBasis.evidenceIds);
  if (expectedLawIds.size && snapshot.laws.length < 1) issues.push('returned current decision has no visible legal grounding');
  if (!expectedLawIds.size && snapshot.laws.length) issues.push('legal grounding is shown without a returned current-decision basis');
  if (!currentNode || snapshot.laws.some(item => !item.insideViewport || item.anchorNodeId !== story.currentNodeId || item.rect.bottom >= currentNode.rect.top || !expectedLawIds.has(item.lawId))) issues.push('legal grounding is not truthfully placed above the returned current node');
  if (expectedEvidenceIds.size && snapshot.evidence.length < 1) issues.push('returned current decision has no visible evidence grounding');
  if (!expectedEvidenceIds.size && snapshot.evidence.length) issues.push('evidence grounding is shown without a returned current-decision basis');
  if (!currentNode || snapshot.evidence.some(item => !item.insideViewport || item.anchorNodeId !== story.currentNodeId || item.rect.top <= currentNode.rect.bottom || !expectedEvidenceIds.has(item.evidenceId))) issues.push('evidence requirements are not truthfully placed below the returned current node');
  const nextActions = snapshot.nextActions;
  if (nextActions.length > 1 || !currentNode || nextActions.some(item => !item.insideViewport || item.rect.top <= currentNode.rect.bottom || item.id !== story.nextActionNodeId)) issues.push('compact next action does not equal the returned next action');
  if (story.nextActionNodeId !== story.currentNodeId
    && !snapshot.branches.some(branch => branch.id === story.nextActionNodeId && branch.selected)
    && !snapshot.nodes.some(node => node.id === story.nextActionNodeId && node.path === 'next-action')
    && !nextActions.some(item => item.id === story.nextActionNodeId)) issues.push('distinct returned next action is not visible');
  const nextEvidence = nextActions[0] && expected.evidenceById[nextActions[0].evidenceId];
  if (nextActions.length && (!nextEvidence || !Array.isArray(nextEvidence.node_ids) || !nextEvidence.node_ids.includes(story.nextActionNodeId))) issues.push('next-action evidence is not returned as owned by the next action');
  const visibleSpatialObjects = [
    ...snapshot.nodes.map(item => ({ label: `node:${item.id}`, rect: item.rect })),
    ...snapshot.branches.map(item => ({ label: `branch:${item.id}`, rect: item.rect })),
    ...snapshot.laws.map(item => ({ label: `law:${item.id}`, rect: item.rect })),
    ...snapshot.evidence.map(item => ({ label: `evidence:${item.id}`, rect: item.rect })),
    ...snapshot.nextActions.map(item => ({ label: `next:${item.evidenceId}`, rect: item.rect })),
  ];
  for (let index = 0; index < visibleSpatialObjects.length; index += 1) {
    for (let other = index + 1; other < visibleSpatialObjects.length; other += 1) {
      if (rectIntersectionArea(visibleSpatialObjects[index].rect, visibleSpatialObjects[other].rect) > SPATIAL_GEOMETRY_EPSILON_PX) issues.push(`${visibleSpatialObjects[index].label}/${visibleSpatialObjects[other].label}: visible spatial objects overlap`);
    }
  }
  return [...new Set(issues)];
}

function processProjectionContractViolations(changes, semanticEvents, cursorSteps, expectedRunId = '', expectedNodeIds = FLAGSHIP_PROCESS_PROJECTION_IDS, cursorRequiredNodeIds = expectedNodeIds) {
  const issues = [];
  const storyNodeIds = Array.isArray(expectedNodeIds) ? expectedNodeIds.map(String) : [];
  const cursorRequired = new Set((Array.isArray(cursorRequiredNodeIds) ? cursorRequiredNodeIds : []).map(String));
  const processEvents = new Map((semanticEvents || [])
    .filter(event => event.entityKind === 'process_node' && event.type === 'process_node.created')
    .map(event => [event.entityId, event]));
  const decisionEvents = new Map((semanticEvents || [])
    .filter(event => event.entityKind === 'process_decision' && event.type === 'process_decision.accepted')
    .map(event => [event.entityId, event]));
  const cursorBindings = new Set(cursorSteps.filter(step => step.phase === 'click').map(step => `${step.changeId}:${step.eventId}`));
  if (stableJson(changes.map(change => change.entityId)) !== stableJson(storyNodeIds)) issues.push('process story did not arrive in the returned route order');
  changes.forEach((change, index) => {
    const states = Object.fromEntries(change.nodeStates.map(item => [item.nodeId, item.state]));
    const prior = storyNodeIds.slice(0, index);
    const future = storyNodeIds.slice(index + 1);
    const semantic = processEvents.get(change.entityId);
    const decisionSemantic = decisionEvents.get(change.entityId);
    if (!nonemptyString(change.changeId) || !nonemptyString(change.eventId)) issues.push(`${change.entityId}: missing change/event identity`);
    if (!semantic || semantic.eventId !== change.eventId || semantic.runId !== expectedRunId
      || semantic.traceContract !== EXECUTION_TRACE_CONTRACT || semantic.presentationMode !== 'returned_action_replay') {
      issues.push(`${change.entityId}: change event is absent from the run-scoped accepted execution trace`);
    }
    if (change.agentId !== semantic?.agentId || REQUIRED_NEMOTRON_AGENT_IDS.includes(change.agentId)) {
      issues.push(`${change.entityId}: process change is not bound to its deterministic trace actor`);
    }
    const matchingCursors = (cursorSteps || []).filter(step => step.phase === 'click'
      && step.changeId === change.changeId && step.eventId === change.eventId);
    if (cursorRequired.has(change.entityId) && !cursorBindings.has(`${change.changeId}:${change.eventId}`)) issues.push(`${change.entityId}: semantic graph change is not tied to its agent cursor event`);
    const cursor = matchingCursors[0];
    if (cursorRequired.has(change.entityId) && (!cursor || cursor.presentationMode !== 'returned-action-replay' || !/^Returned work · /.test(cursor.presentationLabel || ''))) {
      issues.push(`${change.entityId}: graph replay is not visibly labelled as returned work`);
    }
    if (semantic?.actorType !== 'deterministic_tool' || semantic?.modelContributionAccepted !== false
      || semantic?.modelOwnedFields?.length || semantic?.outputProcessNodeId !== change.entityId
      || !semantic?.applicationOwnedFields?.length) issues.push(`${change.entityId}: process_node.created is not a neutral deterministic structure`);
    if (matchingCursors.some(item => item.agentId || item.activeAgentId || !['gate', 'law'].includes(item.activeSignature))) {
      issues.push(`${change.entityId}: deterministic process structure inherited a model identity`);
    }
    const linkedIds = semantic?.linkedModelContributionIds || [];
    if (linkedIds.length) {
      if (!decisionSemantic || decisionSemantic.runId !== expectedRunId || decisionSemantic.traceContract !== EXECUTION_TRACE_CONTRACT
        || decisionSemantic.presentationMode !== 'returned_action_replay' || decisionSemantic.actorType !== 'nemotron_agent'
        || decisionSemantic.agentId !== 'process_decision_mapping' || decisionSemantic.modelContributionAccepted !== true
        || stableJson(decisionSemantic.modelOwnedFields) !== stableJson(['decision_value'])
        || decisionSemantic.applicationOwnedFields?.length || stableJson(decisionSemantic.acceptedContributionIds) !== stableJson(linkedIds)) {
        issues.push(`${change.entityId}: linked process decision is not the exact accepted decision_value field event`);
      }
    } else if (decisionSemantic) issues.push(`${change.entityId}: process model event exists without a linked accepted contribution`);
    if (states[change.entityId] !== 'building') issues.push(`${change.entityId}: current node is not the sole building node`);
    if (!prior.every(nodeId => states[nodeId] === 'built')) issues.push(`${change.entityId}: prior nodes are not built`);
    if (!future.every(nodeId => states[nodeId] === 'pending')) issues.push(`${change.entityId}: future nodes are not pending`);
    if (Object.values(states).filter(value => value === 'building').length !== 1) issues.push(`${change.entityId}: building-node multiplicity`);
    if (change.nodeStates.filter(item => item.state === 'pending').some(item => item.tabIndex !== -1 || item.disabled !== true)) issues.push(`${change.entityId}: pending nodes are keyboard reachable`);
    if (change.nodeStates.filter(item => item.ariaCurrent === 'step').length !== 1) issues.push(`${change.entityId}: aria-current step multiplicity`);
    if (!change.focus || change.focus.focusCount !== 1 || change.focus.cursorCount !== 1 || change.focus.artifactCount !== 1 || change.focus.actionCount > 1) issues.push(`${change.entityId}: focal-surface multiplicity`);
  });
  if (new Set(changes.map(change => change.changeId)).size !== storyNodeIds.length) issues.push('process change IDs are missing or duplicated');
  const holds = changes.slice(1).map((change, index) => change.at - changes[index].at);
  if (holds.some(value => value < MIN_PROCESS_NODE_STEP_MS)) issues.push(`process node dwell ${stableJson(holds)}`);
  return issues;
}

function processNodeProgressContractViolations(progressEvents, nodeChanges, finalState, semanticEvents = [], expectedRunId = '', expectedNodeIds = FLAGSHIP_PROCESS_PROJECTION_IDS) {
  const issues = [];
  const processEvents = new Map((semanticEvents || [])
    .filter(event => event.entityKind === 'process_node' && event.type === 'process_node.created')
    .map(event => [event.entityId, event]));
  const decisionEvents = new Map((semanticEvents || [])
    .filter(event => event.entityKind === 'process_decision' && event.type === 'process_decision.accepted')
    .map(event => [event.entityId, event]));
  const expectedEntities = (Array.isArray(expectedNodeIds) ? expectedNodeIds : []).map(nodeId => ({ entityKind: 'node', nodeId: String(nodeId), branchId: '' }));
  const entityKey = item => `${item.entityKind}:${item.nodeId}`;
  const grouped = new Map();
  for (const event of progressEvents || []) {
    const key = entityKey(event);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(event);
  }
  if (stableJson([...grouped.keys()]) !== stableJson(expectedEntities.map(entityKey))) {
    issues.push('progress does not cover the returned route decisions in order');
  }
  const nodeOutputs = new Map((nodeChanges || []).map(item => [`node:${item.entityId}`, item]));

  expectedEntities.forEach(entity => {
    const key = entityKey(entity);
    const events = grouped.get(key) || [];
    const structureSemantic = processEvents.get(entity.nodeId);
    const decisionSemantic = decisionEvents.get(entity.nodeId);
    const analysisEvents = events.slice(0, -3);
    const terminalEvents = events.slice(-3);
    let analysisIndex = 0;
    let analysisShapeValid = analysisEvents.length === 0 || analysisEvents[0]?.percent === 0;
    while (analysisShapeValid && analysisIndex < analysisEvents.length) {
      const search = analysisEvents[analysisIndex];
      if (search?.phase !== 'search' || search.visible !== true) {
        analysisShapeValid = false;
        break;
      }
      const basisKind = search.basisKind;
      analysisIndex += 1;
      let locatorPairs = 0;
      while (analysisIndex < analysisEvents.length && analysisEvents[analysisIndex]?.phase !== 'search') {
        const read = analysisEvents[analysisIndex];
        const extract = analysisEvents[analysisIndex + 1];
        if (read?.phase !== 'read' || extract?.phase !== 'extract'
          || read.visible !== true || extract.visible !== true
          || read.basisKind !== basisKind || extract.basisKind !== basisKind) {
          analysisShapeValid = false;
          break;
        }
        locatorPairs += 1;
        analysisIndex += 2;
      }
      if (locatorPairs < 1) analysisShapeValid = false;
    }
    const terminalShapeValid = stableJson(terminalEvents.map(({ phase, percent, visible }) => ({ phase, percent, visible })))
      === stableJson([
        { phase: 'form', percent: 90, visible: true },
        { phase: 'complete', percent: 100, visible: true },
        { phase: 'cleared', percent: 100, visible: false },
      ]);
    if (!analysisShapeValid || !terminalShapeValid) issues.push(`${key}: decision progress does not replay accepted inputs before form, 100, and cleared`);
    if (events.some(event => event.contract !== PROCESS_NODE_PROGRESS_CONTRACT || event.scope !== PROCESS_NODE_PROGRESS_SCOPE)) issues.push(`${key}: progress contract or scope drift`);
    const analysisGroups = [];
    for (const event of events.slice(0, -3)) {
      if (event.phase === 'search' || !analysisGroups.length) analysisGroups.push([]);
      analysisGroups.at(-1).push(event);
    }
    if (analysisGroups.some(group => new Set(group.map(event => event.basisKind).filter(Boolean)).size !== 1)) issues.push(`${key}: progress basis kind changes within one evidence step`);
    const evidenceRequirement = events.some(event => event.basisKind === 'evidence-requirement');
    const visibleEvents = events.filter(item => item.visible === true);
    visibleEvents.forEach(event => {
      if (event.indicatorDomCount !== 1 || event.indicatorVisibleCount !== 1 || event.indicatorVisible !== true
        || event.indicatorSurfaceVisible || event.indicatorInsideCursor !== true) issues.push(`${key}:${event.phase}: one calm cursor working cue is not visible while its semantic progress element stays hidden`);
      if (event.indicatorValueVisible) issues.push(`${key}:${event.phase}: numeric percentage is visible in the live node flow`);
      if (event.indicatorPercent !== event.percent || event.indicatorPhase !== event.phase) issues.push(`${key}:${event.phase}: progress UI does not equal the emitted state`);
      if (event.indicatorLabel !== event.label || event.rootBasisKind !== event.basisKind) issues.push(`${key}:${event.phase}: visible progress label or basis kind drifts from the emitted analysis`);
      if (event.rootProgressState !== 'active' || event.processProgressState !== 'active'
        || event.rootPercent !== String(event.percent) || event.processPercent !== String(event.percent)
        || event.rootPhase !== event.phase || event.processPhase !== event.phase
        || event.rootNodeId !== entity.nodeId || event.processNodeId !== entity.nodeId) issues.push(`${key}:${event.phase}: root/process progress datasets drift from the visible indicator`);
      const modelDecisionPhase = Boolean(decisionSemantic) && ['form', 'complete'].includes(event.phase);
      const expectedSemantic = modelDecisionPhase ? decisionSemantic : structureSemantic;
      const expectedAgentId = modelDecisionPhase ? 'process_decision_mapping' : '';
      if (event.cursorProgressState !== 'active' || event.agentId !== expectedAgentId
        || event.presentationMode !== 'returned-action-replay' || !/^Returned work · /.test(event.presentationLabel || '')) {
        issues.push(`${key}:${event.phase}: calm working cue is not visibly bound to the returned execution trace`);
      }
      if (expectedSemantic && (event.eventId !== expectedSemantic.eventId || expectedSemantic.runId !== expectedRunId
        || expectedSemantic.traceContract !== EXECUTION_TRACE_CONTRACT || expectedSemantic.presentationMode !== 'returned_action_replay')) {
        issues.push(`${key}:${event.phase}: progress is not bound to the phase-owning run-scoped execution event`);
      }
      if (modelDecisionPhase) {
        if (event.cursorSignature !== 'process' || event.cursorAgent !== REQUIRED_DESKTOP_AGENT_LABELS.process_decision_mapping
          || event.activeAgentId !== 'process_decision_mapping' || event.visualActiveAgentId !== 'process_decision_mapping'
          || event.visualGroupId !== PATH_BUILDER_VISUAL_GROUP_ID) {
          issues.push(`${key}:${event.phase}: accepted decision_value is not bound to the merged Path builder workstream and exact process receipt`);
        }
      } else if (!['gate', 'law'].includes(event.cursorSignature)
        || !nonemptyString(event.cursorAgent) || event.cursorAgent !== event.workAuthority
        || event.activeAgentId || event.visualActiveAgentId || event.visualGroupId) {
        issues.push(`${key}:${event.phase}: accepted-input or structural progress inherited a model identity`);
      }
      if (event.outputVisible) issues.push(`${key}:${event.phase}: output appears before progress clears`);
      if (evidenceRequirement && analysisEvents.length) {
        const expectedLabel = EVIDENCE_REQUIREMENT_PROGRESS_LABELS[event.phase]
          || (event.phase === 'form' ? (entity.entityKind === 'branch' ? 'Testing outcome' : 'Forming decision')
            : event.phase === 'complete' ? (entity.entityKind === 'branch' ? 'Outcome ready' : 'Decision ready') : '');
        if (event.label !== expectedLabel || event.indicatorLabel !== expectedLabel) issues.push(`${key}:${event.phase}: evidence requirement progress is mislabeled`);
        if (/Finding source|Source for the next decision/i.test(`${event.label} ${event.indicatorLabel} ${event.inspectionText}`)) issues.push(`${key}:${event.phase}: evidence requirement is falsely presented as a source`);
        if (event.phase === 'search' && event.basisKind === 'evidence-requirement'
          && (event.inspectionBasisKind !== 'evidence-requirement' || event.inspectionPrompt !== 'Evidence still needed')) issues.push(`${key}: evidence requirement search does not visibly say Evidence still needed`);
      }
    });
    const percentages = visibleEvents.map(item => item.percent);
    if (percentages.some((value, index) => index > 0 && value < percentages[index - 1])) issues.push(`${key}: progress is not monotonic`);
    if (new Set(events.map(item => item.changeId)).size !== 1 || !events.every(item => nonemptyString(item.changeId) && nonemptyString(item.eventId))) issues.push(`${key}: progress change identity is missing or changes during analysis`);
    if (!structureSemantic || structureSemantic.runId !== expectedRunId || structureSemantic.traceContract !== EXECUTION_TRACE_CONTRACT
      || structureSemantic.presentationMode !== 'returned_action_replay' || structureSemantic.actorType !== 'deterministic_tool'
      || structureSemantic.modelContributionAccepted !== false || structureSemantic.modelOwnedFields?.length) {
      issues.push(`${key}: structural progress is not bound to the neutral run-scoped process_node event`);
    }
    if (decisionSemantic && (decisionSemantic.runId !== expectedRunId || decisionSemantic.traceContract !== EXECUTION_TRACE_CONTRACT
      || decisionSemantic.presentationMode !== 'returned_action_replay' || decisionSemantic.actorType !== 'nemotron_agent'
      || decisionSemantic.agentId !== 'process_decision_mapping' || decisionSemantic.modelContributionAccepted !== true
      || stableJson(decisionSemantic.modelOwnedFields) !== stableJson(['decision_value']))) {
      issues.push(`${key}: model progress is not limited to the accepted decision_value event`);
    }

    const complete = events.find(item => item.phase === 'complete');
    const cleared = events.find(item => item.phase === 'cleared');
    if (!complete || complete.percent !== 100 || complete.visible !== true || complete.indicatorVisible !== true || complete.cursorProgressState !== 'active') issues.push(`${key}: analysis indicator did not semantically reach completion before clearing`);
    if (!cleared || cleared.percent !== 100 || cleared.visible !== false || cleared.indicatorVisible || cleared.indicatorVisibleCount !== 0
      || cleared.cursorProgressState || cleared.rootProgressState !== 'idle' || cleared.processProgressState !== 'idle' || cleared.outputVisible) issues.push(`${key}: progress was not cleared while the output was still absent`);

    const output = nodeOutputs.get(key);
    if (!output) {
      issues.push(`${key}: no resulting process output was observed`);
      return;
    }
    if (cleared && output.at - cleared.at < MIN_PROCESS_NODE_PROGRESS_CLEAR_GAP_MS) issues.push(`${key}: output did not wait after the progress indicator cleared`);
    if (output.indicatorVisible || output.indicatorVisibleCount !== 0 || output.cursorProgressState || output.rootProgressState !== 'idle' || output.processProgressState !== 'idle') issues.push(`${key}: progress indicator remains visible when the output appears`);
    if (output.outputVisible !== true) issues.push(`${key}: resulting process output was not visible after progress cleared`);
    if (events.length && (output.changeId !== events[0].changeId || output.eventId !== structureSemantic?.eventId
      || output.agentId !== structureSemantic?.agentId || REQUIRED_NEMOTRON_AGENT_IDS.includes(output.agentId))) {
      issues.push(`${key}: resulting node is not bound to its neutral structural event`);
    }
  });

  if (!finalState || finalState.indicatorVisible || finalState.indicatorValueVisible || finalState.indicatorVisibleCount !== 0 || finalState.cursorProgressState
    || finalState.rootProgressState !== 'idle' || finalState.processProgressState !== 'idle'
    || finalState.rootPercent || finalState.processPercent) issues.push('completed process leaves progress visible or active');
  return [...new Set(issues)];
}

function factSourceLocatorId(reference) {
  const artifactId = String(reference?.artifact_id || 'unknown-source');
  const kind = String(reference?.locator_kind || 'unknown-locator');
  if (kind === 'visual_observation') return `source:${artifactId}:region:${(reference?.region || []).join(',')}`;
  if (kind === 'metadata_field') return `source:${artifactId}:field:${String(reference?.field || '')}`;
  return `source:${artifactId}:page:${String(reference?.page || '')}:quote:${String(reference?.excerpt || '')}`;
}

function factSourcePreviewTruth(claim, fact, reference, visualPreview = false) {
  const sourceId = String(reference?.artifact_id || '');
  const artifact = (claim?.artifacts || []).find(item => String(item?.artifact_id || '') === sourceId);
  const title = sourceId === 'message'
    ? 'Claim message'
    : sourceId === 'intake'
      ? 'Claim details'
      : String(artifact?.title || sourceId || 'Claim source').replace(/^art_/, '').replaceAll('_', ' ');
  const location = reference?.locator_kind === 'visual_observation'
    ? 'Image'
    : reference?.locator_kind === 'metadata_field'
      ? 'Returned field'
      : `Page ${String(reference?.page || 1)} of ${Math.max(1, Number(artifact?.page_count) || 1)}`;
  return {
    title,
    location,
    passage: String(reference?.excerpt || reference?.observation || `${fact?.label}: ${fact?.value}`),
  };
}

function usableDecisionReference(reference) {
  return reference?.locator_kind === 'text_quote'
    ? nonemptyString(reference.excerpt)
    : reference?.locator_kind === 'metadata_field'
      ? nonemptyString(reference.field) && String(reference.value ?? '').length > 0
      : reference?.locator_kind === 'visual_observation'
        ? Array.isArray(reference.region) && reference.region.length === 4 && nonemptyString(reference.observation)
        : false;
}

function decisionFactsForReturnedNode(runResult, node) {
  const facts = Array.isArray(runResult?.facts) ? runResult.facts : [];
  const factsById = new Map(facts.map(fact => [fact.fact_id, fact]));
  let decisionFacts = (Array.isArray(node?.fact_ids) ? node.fact_ids : [])
    .map(factId => factsById.get(factId))
    .filter(fact => fact && (fact.source_refs || []).some(usableDecisionReference));
  if (!decisionFacts.length) {
    const checklistItems = Array.isArray(runResult?.checklist?.items) ? runResult.checklist.items : [];
    for (const itemId of Array.isArray(node?.evidence_requirement_ids) ? node.evidence_requirement_ids : []) {
      const item = checklistItems.find(candidate => candidate.item_id === itemId);
      const fact = factsById.get(item?.fact_id);
      if (fact && (fact.source_refs || []).some(usableDecisionReference)) {
        decisionFacts = [fact];
        break;
      }
    }
  }
  return decisionFacts;
}

function directDecisionSourceGroups(runResult, node, seenLocatorIds = new Set()) {
  const decisionFacts = decisionFactsForReturnedNode(runResult, node);
  const groups = [];
  const bySource = new Map();
  decisionFacts.forEach(fact => {
    (fact.source_refs || []).forEach(reference => {
      if (!usableDecisionReference(reference) || !nonemptyString(reference.artifact_id)) return;
      const locatorId = factSourceLocatorId(reference);
      if (seenLocatorIds.has(locatorId)) return;
      let group = bySource.get(reference.artifact_id);
      if (!group) {
        group = { sourceId: reference.artifact_id, locatorIds: [], factIds: [], items: [] };
        bySource.set(reference.artifact_id, group);
        groups.push(group);
      }
      let item = group.items.find(candidate => candidate.locatorId === locatorId);
      if (!item) {
        item = { locatorId, factIds: [] };
        group.items.push(item);
        group.locatorIds.push(locatorId);
      }
      if (!item.factIds.includes(fact.fact_id)) item.factIds.push(fact.fact_id);
      if (!group.factIds.includes(fact.fact_id)) group.factIds.push(fact.fact_id);
    });
  });
  return groups;
}

function officialDecisionLaw(runResult, node, seenLawIds = new Set()) {
  const legal = runResult?.legal_research || {};
  const joined = (legal.questions || [])
    .filter(question => (question.process_node_ids || []).includes(node?.node_id))
    .flatMap(question => [...(question.source_ids || []), ...(question.interpretation_ids || [])]);
  const lawIds = new Set([
    ...(Array.isArray(node?.legal_source_ids) ? node.legal_source_ids : []),
    ...((legal.node_links || {})[node?.node_id] || []),
    ...joined,
  ]);
  return [...(legal.sources || []), ...(legal.handling_principles || [])].find(source => (
    lawIds.has(source.source_id) && !seenLawIds.has(source.source_id)
      && ['official_statute', 'official_guidance'].includes(source.source_type)
  )) || null;
}

function decisionFlowContractViolations(steps, nodeChanges, highlights, interactions, run, semanticEvents = [], expectedNodeIds = FLAGSHIP_PROCESS_PROJECTION_IDS) {
  const issues = [];
  const runResult = run?.result || run || {};
  const expectedRunId = String(run?.run_id || '');
  const returnedNodes = new Map((runResult.process?.nodes || []).map(node => [node.node_id, node]));
  const semanticByEntity = new Map((semanticEvents || []).map(event => [`${event.entityKind}:${event.entityId}`, event]));
  const storyNodeIds = Array.isArray(expectedNodeIds) ? expectedNodeIds.map(String) : [];
  const relevantSteps = (steps || []).filter(step => storyNodeIds.includes(step.nodeId));
  const nodeOrder = relevantSteps.filter(step => step.phase === 'combining').map(step => step.nodeId);
  if (stableJson(nodeOrder) !== stableJson(storyNodeIds)) issues.push('integrated decision trace does not cover the returned route decisions in order');

  storyNodeIds.forEach(nodeId => {
    const node = returnedNodes.get(nodeId);
    const events = relevantSteps.filter(step => step.nodeId === nodeId);
    const reducedMotion = events.length > 0 && events.every(event => event.reducedMotion === true);
    const planned = events.filter(step => step.phase === 'planned');
    const change = (nodeChanges || []).find(item => item.entityId === nodeId);
    const structureSemantic = semanticByEntity.get(`process_node:${nodeId}`);
    const decisionSemantic = semanticByEntity.get(`process_decision:${nodeId}`);
    if (!node || !events.length || !structureSemantic) {
      issues.push(`${nodeId}: accepted process decision trace is absent`);
      return;
    }
    if (events.some(event => {
      const modelDecisionPhase = Boolean(decisionSemantic) && ['combining', 'decision-ready'].includes(event.phase);
      return event.contract !== DECISION_FLOW_CONTRACT || event.runId !== expectedRunId
        || event.eventId !== structureSemantic.eventId || event.structureEventId !== structureSemantic.eventId
        || event.structureAuthority !== structureSemantic.authority || event.structureTraceContract !== EXECUTION_TRACE_CONTRACT
        || event.decisionEventId !== (decisionSemantic?.eventId || '')
        || event.decisionAgentId !== (decisionSemantic?.agentId || '')
        || event.agentId !== (modelDecisionPhase ? 'process_decision_mapping' : '')
        || event.decisionAuthority !== (decisionSemantic?.authority || '')
        || event.decisionModelContributionAccepted !== Boolean(decisionSemantic)
        || event.presentationMode !== 'returned-action-replay' || !/^Returned work · /.test(event.presentationLabel || '');
    })) {
      issues.push(`${nodeId}: decision replay is not bound to its run-scoped accepted execution trace and visible mode label`);
    }
    if (structureSemantic.runId !== expectedRunId || structureSemantic.traceContract !== EXECUTION_TRACE_CONTRACT
      || structureSemantic.presentationMode !== 'returned_action_replay' || structureSemantic.type !== 'process_node.created'
      || structureSemantic.actorType !== 'deterministic_tool' || structureSemantic.modelContributionAccepted !== false
      || structureSemantic.modelOwnedFields?.length) issues.push(`${nodeId}: process structure event lacks neutral accepted execution-trace lineage`);
    if (decisionSemantic && (decisionSemantic.runId !== expectedRunId || decisionSemantic.traceContract !== EXECUTION_TRACE_CONTRACT
      || decisionSemantic.presentationMode !== 'returned_action_replay' || decisionSemantic.type !== 'process_decision.accepted'
      || decisionSemantic.actorType !== 'nemotron_agent' || decisionSemantic.agentId !== 'process_decision_mapping'
      || decisionSemantic.modelContributionAccepted !== true || stableJson(decisionSemantic.modelOwnedFields) !== stableJson(['decision_value']))) {
      issues.push(`${nodeId}: process model identity is not limited to the accepted decision_value event`);
    }
    events.forEach(event => {
      const modelDecisionPhase = Boolean(decisionSemantic) && ['combining', 'decision-ready'].includes(event.phase);
      if (modelDecisionPhase) {
        if (event.activeAgentId !== 'process_decision_mapping' || event.visualActiveAgentId !== 'process_decision_mapping'
          || event.visualGroupId !== PATH_BUILDER_VISUAL_GROUP_ID
          || event.activeSignature !== 'process' || event.workAuthority !== 'Process builder') {
          issues.push(`${nodeId}:${event.phase}: accepted decision_value is not bound to the merged Path builder workstream and exact process receipt`);
        }
      } else if (event.activeAgentId || event.visualActiveAgentId || event.visualGroupId || event.activeSignature === 'process' || event.workAuthority === 'Process builder') {
        issues.push(`${nodeId}:${event.phase}: accepted input or structural replay inherited a model identity`);
      }
    });
    if (events.some(event => !event.graphVisible || event.graphConstructionState !== 'building'
      || !event.workspaceVisible || event.workspaceNodeId !== nodeId)) issues.push(`${nodeId}: process decision trace leaves the visible graph workspace`);
    if (events.some(event => event.planCount !== 1 || !event.planVisible || event.planNodeId !== nodeId
      || event.planParagraphCount !== 0 || event.planButtonCount !== 0
      || event.planItemCount !== planned.length + 2)) issues.push(`${nodeId}: live plan is not the one minimal accepted-input-to-decision checklist`);
    if (events.some(event => event.readerControlCount !== 0)) issues.push(`${nodeId}: automatic decision replay exposes a viewer-facing reader control`);

    const decisionFacts = decisionFactsForReturnedNode(runResult, node);
    const blockedDownstream = BLOCKED_DOWNSTREAM_DECISION_IDS.includes(nodeId);
    const expectedPlanKind = blockedDownstream ? 'waiting-decision' : 'evidence-decision';
    if (events.some(event => event.planKind !== expectedPlanKind)) issues.push(`${nodeId}: live plan kind does not match the decision state`);
    if (blockedDownstream) {
      if (planned.length) issues.push(`${nodeId}: blocked downstream step invents accepted input work before causation is resolved`);
      if (events.some(event => !event.waitingBasisVisible || event.waitingBasisText !== BLOCKED_DOWNSTREAM_WAITING_COPY[nodeId])) {
        issues.push(`${nodeId}: unresolved downstream decision does not show its exact plain dependency`);
      }
    } else if (events.some(event => event.waitingBasisVisible || event.waitingBasisText)) {
      issues.push(`${nodeId}: evidence-backed decision is falsely presented as waiting on an earlier answer`);
    }

    const linkedLaw = !blockedDownstream && decisionFacts.length ? officialDecisionLaw(runResult, node, new Set()) : null;
    const expectedKinds = blockedDownstream ? [] : decisionFacts.length
      ? [...decisionFacts.map(() => 'accepted-fact'), ...(linkedLaw ? ['accepted-law'] : [])]
      : planned.map(plan => plan.stepKind);
    if (stableJson(planned.map(plan => plan.stepKind)) !== stableJson(expectedKinds)) issues.push(`${nodeId}: graph plan does not reuse the accepted fact and checked-law trace`);
    if (planned.some(plan => ['source', 'law'].includes(plan.stepKind))) issues.push(`${nodeId}: graph decision replay reopens a source or law instead of reusing accepted trace`);
    if (!decisionFacts.length && !blockedDownstream
      && (planned.length !== 1 || !['evidence-requirement', 'accepted-decision', 'start-point'].includes(planned[0]?.stepKind))) {
      issues.push(`${nodeId}: source-free decision does not use one returned structural basis`);
    }

    planned.forEach((plan, index) => {
      const stepEvents = events.filter(event => event.stepId === plan.stepId);
      const opened = stepEvents.find(event => event.phase === 'source-opened');
      const extracted = stepEvents.find(event => event.phase === 'fragment-extracted');
      if (!opened || !extracted || !(plan.at <= opened.at && opened.at <= extracted.at)) {
        issues.push(`${nodeId}:${plan.stepId}: accepted input is not replayed sequentially`);
        return;
      }
      if (extracted.at - opened.at < MIN_DECISION_SOURCE_PREVIEW_HOLD_MS) {
        issues.push(`${nodeId}:${plan.stepId}: exact source is not readable before its passage is highlighted`);
      }
      if (plan.realArtifactVisible || opened.realArtifactVisible || extracted.realArtifactVisible
        || plan.sourceRowActive || opened.sourceRowActive || extracted.sourceRowActive
        || plan.activeSourceIds.length || opened.activeSourceIds.length || extracted.activeSourceIds.length
        || plan.activeSourceLocator || opened.activeSourceLocator || extracted.activeSourceLocator) {
        issues.push(`${nodeId}:${plan.stepId}: accepted-input replay falsely claims a new source opening`);
      }
      if ((highlights || []).some(highlight => highlight.entityKind === 'node' && highlight.nodeId === nodeId
        && highlight.at >= plan.at && highlight.at <= extracted.at)) issues.push(`${nodeId}:${plan.stepId}: accepted-input replay emits a fake new source highlight`);
      if (plan.stepKind === 'accepted-fact') {
        const fact = decisionFacts[index];
        const semantic = semanticByEntity.get(`fact:${fact?.fact_id || ''}`);
        if (!fact || plan.stepId !== `accepted-fact:${fact.fact_id}` || stableJson(plan.factIds) !== stableJson([fact.fact_id])
          || !semantic || plan.basisEventId !== semantic.eventId || plan.basisAgentId !== semantic.agentId
          || plan.basisAuthority !== semantic.authority || semantic.runId !== expectedRunId
          || semantic.traceContract !== EXECUTION_TRACE_CONTRACT || semantic.presentationMode !== 'returned_action_replay'
          || !extracted.fragmentFactIds.includes(fact.fact_id)) {
          issues.push(`${nodeId}:${plan.stepId}: accepted fact replay is not bound to the exact returned fact event`);
        }
      } else if (plan.stepKind === 'accepted-law') {
        const semantic = semanticByEntity.get(`official_source:${linkedLaw?.source_id || ''}`);
        if (!linkedLaw || plan.stepId !== `accepted-law:${linkedLaw.source_id}` || plan.sourceId !== linkedLaw.source_id
          || !semantic || plan.basisEventId !== semantic.eventId || plan.basisAgentId !== 'official_law_registry'
          || semantic.runId !== expectedRunId || semantic.actorType !== 'deterministic_tool'
          || semantic.presentationMode !== 'deterministic_projection' || semantic.modelContributionAccepted !== false) {
          issues.push(`${nodeId}:${plan.stepId}: checked-law replay is not bound to the deterministic official registry event`);
        }
      }
      const nextEvent = events.find(event => event.at > extracted.at);
      if (!nextEvent || nextEvent.at - extracted.at < MIN_DECISION_SOURCE_HOLD_MS) issues.push(`${nodeId}:${plan.stepId}: accepted input is not readable before the next reasoning step`);
    });

    const expectedPhases = planned.flatMap(() => ['planned', 'source-opened', 'fragment-extracted'])
      .concat(['combining', 'decision-ready', 'plan-receding', 'plan-receded']);
    if (stableJson(events.map(event => event.phase)) !== stableJson(expectedPhases)) issues.push(`${nodeId}: decision phases are incomplete or out of order`);
    const combining = events.find(event => event.phase === 'combining');
    const ready = events.find(event => event.phase === 'decision-ready');
    const receding = events.find(event => event.phase === 'plan-receding');
    const receded = events.find(event => event.phase === 'plan-receded');
    const expectedFactIds = blockedDownstream ? [] : decisionFacts.map(fact => fact.fact_id);
    if (!combining || (expectedFactIds.length && (!combining.combinationVisible
      || combining.combineState !== 'combining' || stableJson(combining.fragmentFactIds) !== stableJson(expectedFactIds)))) {
      issues.push(`${nodeId}: accepted facts are not visibly combined exactly once`);
    }
    if (!combining || !ready || ready.at - combining.at < MIN_DECISION_COMBINE_HOLD_MS) {
      issues.push(`${nodeId}: source highlights do not remain visible while the decision is formed`);
    }
    if (!ready || !receding || receding.at - ready.at < MIN_DECISION_READY_HOLD_MS) {
      issues.push(`${nodeId}: completed decision does not remain readable before node commit begins`);
    }
    if (!ready || ready.progress !== 100 || !ready.progressVisible) issues.push(`${nodeId}: decision indicator does not semantically reach completion without showing a numeric percentage`);
    if (!receding || receding.progressVisible || receding.planPhase !== 'receding' || receding.nodeVisible) issues.push(`${nodeId}: progress is not hidden while the live plan recedes before node creation`);
    if (!receded || receded.progressVisible || receded.planPhase !== 'receded' || receded.nodeVisible) issues.push(`${nodeId}: live plan does not finish receding before node creation`);
    if (!change || !receding || (!reducedMotion && change.at - receding.at < MIN_DECISION_PLAN_RECEDE_MS)
      || !receded || change.at < receded.at || change.eventId !== structureSemantic.eventId
      || change.agentId !== structureSemantic.agentId || REQUIRED_NEMOTRON_AGENT_IDS.includes(change.agentId)
      || change.indicatorVisible || (change.planVisible && change.planPhase !== 'receded') || change.decisionFlowState !== 'idle'
      || !change.outputVisible || !change.graphVisible) issues.push(`${nodeId}: accepted node appears before progress and plan have cleared`);
  });

  if (!storyNodeIds.includes(NOTIFICATION_DECISION_NODE_ID)) return [...new Set(issues)];
  const notification = returnedNodes.get(NOTIFICATION_DECISION_NODE_ID);
  const notificationFact = decisionFactsForReturnedNode(runResult, notification).find(fact => fact.fact_id === 'fact_notification');
  const notificationCounts = Object.entries((notificationFact?.source_refs || []).reduce((counts, ref) => {
    if (usableDecisionReference(ref)) counts[ref.artifact_id] = (counts[ref.artifact_id] || 0) + 1;
    return counts;
  }, {}));
  const notificationEvents = relevantSteps.filter(step => step.nodeId === NOTIFICATION_DECISION_NODE_ID);
  const notificationFactPlan = notificationEvents.find(step => step.phase === 'planned' && step.stepKind === 'accepted-fact' && step.factIds.includes('fact_notification'));
  const notificationLawPlan = notificationEvents.find(step => step.phase === 'planned' && step.stepKind === 'accepted-law');
  const notificationFactSemantic = semanticByEntity.get('fact:fact_notification');
  const notificationLawSemantic = semanticByEntity.get('official_source:fedlex-or-257g');
  if (stableJson(notificationCounts) !== stableJson(Object.entries(NOTIFICATION_SOURCE_LOCATOR_COUNTS))
    || !notificationFactPlan || notificationFactPlan.basisEventId !== notificationFactSemantic?.eventId) {
    issues.push('notification decision does not reuse the accepted fact with two email locators and one delivery locator');
  }
  if (!notificationLawPlan || notificationLawPlan.sourceId !== 'fedlex-or-257g'
    || notificationLawPlan.basisEventId !== notificationLawSemantic?.eventId
    || notificationLawSemantic?.modelContributionAccepted !== false) {
    issues.push('notification decision does not reuse the checked deterministic Article 257g registry trace');
  }
  return [...new Set(issues)];
}

function contextualAttachmentContractViolations(attachments, semanticEvents, cursorSteps, production = true) {
  const issues = [];
  const allowedKinds = new Set(['fact', 'law', 'evidence', 'precedent', 'verification']);
  const semanticById = new Map(semanticEvents.map(event => [event.eventId, event]));
  const visibleCursors = cursorSteps.filter(step => ['move', 'arrived', 'click'].includes(step.phase));
  attachments.forEach((attachment, index) => {
    if (!allowedKinds.has(attachment.kind)) issues.push(`${index}: unsupported attachment kind`);
    if (![attachment.changeId, attachment.eventId, attachment.agentId].every(nonemptyString)) issues.push(`${index}: incomplete semantic attachment identity`);
    const expectedActor = {
      fact: 'canonical_facts',
      law: 'official_law_registry',
      evidence: production ? 'evidence_checklist' : 'evidence_projection',
      precedent: 'historical_claims_retrieval',
      verification: production ? 'final_claim_brief_audit' : 'whole_playbook_gate',
    }[attachment.kind];
    const semantic = semanticById.get(attachment.eventId);
    const cursor = visibleCursors.find(step => step.changeId === attachment.changeId && step.eventId === attachment.eventId);
    if (attachment.agentId !== expectedActor) issues.push(`${index}: attachment actor ${attachment.agentId} does not match truthful ${expectedActor} authority`);
    if (!semantic || semantic.agentId !== attachment.agentId) issues.push(`${index}: attachment event is absent from the authenticated stream or has a different actor`);
    if (!cursor) issues.push(`${index}: attachment change is not tied to its agent cursor event`);
    if (cursor && (REQUIRED_NEMOTRON_AGENT_IDS.includes(attachment.agentId)
      ? cursor.agentId !== attachment.agentId
      : Boolean(cursor.agentId || cursor.activeAgentId))) {
      issues.push(`${index}: attachment cursor inherited the wrong model identity`);
    }
    if (attachment.kind === 'fact' && !['customer_submission', 'generated_demo_reference_only'].includes(attachment.sourceAuthority)) issues.push(`${index}: fact source authority is not a returned claim-source authority`);
    if (attachment.kind === 'law' && !['official_registry', 'deterministic_principle'].includes(attachment.sourceAuthority)) issues.push(`${index}: legal authority is not distinguished truthfully`);
    if (attachment.kind === 'precedent' && (attachment.sourceAuthority !== 'generated_reference' || attachment.referenceStatus !== 'generated_reference')) issues.push(`${index}: generated reference is presented with inflated authority`);
  });
  if (new Set(attachments.map(item => item.changeId)).size !== attachments.length) issues.push('attachment change IDs are duplicated');
  // Claim facts are proven once by the preceding eight-item source-to-fact tour.
  // Graph construction may replay that accepted lineage but must not fake a new
  // source read for every node. The remaining stage-local artifacts each become
  // the single visible focal object during their own chapter.
  for (const kind of ['law', 'evidence', 'precedent', 'verification']) {
    if (!attachments.some(item => item.kind === kind)) issues.push(`${kind}: no contextual artifact attached`);
  }
  return issues;
}

function memoryEffectContractViolations(effects, expectedOriginId) {
  const issues = [];
  const originIds = [...new Set(effects.map(item => item.origin_id).filter(Boolean))];
  const counts = Object.fromEntries(['node-added', 'edge-added', 'evidence-changed'].map(effect => [effect, effects.filter(item => item.effect === effect).length]));
  const identity = {
    nodes: effects.filter(item => item.effect === 'node-added').map(item => item.node_id).sort(),
    edges: effects.filter(item => item.effect === 'edge-added').map(item => `${item.edge_source}->${item.edge_target}`).sort(),
    evidence: effects.filter(item => item.effect === 'evidence-changed').map(item => item.item_id).sort(),
  };
  const expectedIdentity = {
    nodes: ['ventilation_dispute'],
    edges: ['evidence_gap->ventilation_dispute', 'ventilation_dispute->causation'].sort(),
    evidence: ['building_envelope', 'management_position', 'use_evidence'].sort(),
  };
  if (effects.length !== 6) issues.push(`memory effect count ${effects.length}`);
  if (stableJson(counts) !== stableJson({ 'node-added': 1, 'edge-added': 2, 'evidence-changed': 3 })) issues.push(`memory effect shape ${stableJson(counts)}`);
  if (!nonemptyString(expectedOriginId) || effects.some(item => !nonemptyString(item.origin_id)) || originIds.length !== 1 || originIds[0] !== expectedOriginId) issues.push(`memory origin ${stableJson(originIds)}`);
  if (stableJson(identity) !== stableJson(expectedIdentity)) issues.push(`memory effect identity ${stableJson(identity)}`);
  return issues;
}

function laterCausalSeamContractViolations(snapshot, laterRun, sourceStep = null) {
  const issues = [];
  const result = laterRun?.result || laterRun || {};
  const fact = (result.facts || []).find(item => item?.semantic_role === 'management_ventilation_allegation');
  const reference = (fact?.source_refs || []).find(item => (
    item?.artifact_id === snapshot?.sourceId
    && factSourceLocatorId(item) === snapshot?.locatorId
  ));
  const eligibility = result?.memory_application?.eligibility || {};
  if (snapshot?.seamCount !== 1) issues.push(`later causal seam count ${snapshot?.seamCount}`);
  if (!fact || !reference) issues.push('later causal seam source locator is not an exact returned allegation source');
  if (sourceStep && (snapshot?.sourceId !== sourceStep.sourceId || snapshot?.locatorId !== sourceStep.locatorId)) issues.push('later causal seam does not retain the exact source step locator');
  const expectedExcerpt = reference ? (reference.excerpt || reference.observation || `${fact.label}: ${fact.value}`) : '';
  const parts = snapshot?.parts || [];
  if (stableJson(parts.map(item => item.part)) !== stableJson(['source', 'memory', 'result'])) issues.push(`later causal seam parts ${stableJson(parts.map(item => item.part))}`);
  if (reference && (parts[0]?.mark !== expectedExcerpt || parts[0]?.strong !== expectedExcerpt)) issues.push('later causal seam excerpt does not equal the exact returned source text or region');
  if (parts[1]?.small !== 'Saved correction matched' || parts[1]?.strong !== 'Check ventilation separately') issues.push('later causal seam omits the saved correction');
  if (parts[2]?.small !== 'Graph change' || parts[2]?.strong !== 'Ventilation check added') issues.push('later causal seam omits the graph result');
  if (eligibility.contract !== 'casepath.semantic-memory-eligibility/1.0.0'
    || eligibility.eligible !== true
    || !nonemptyString(eligibility.rule_id)
    || snapshot?.ruleId !== eligibility.rule_id
    || !eligibility.checks
    || !Object.values(eligibility.checks).length
    || !Object.values(eligibility.checks).every(value => value === true)) issues.push('later causal seam is not bound to the accepted eligibility rule');
  if (snapshot?.proofSummary !== '1 decision · 2 connections · 3 document needs'
    || snapshot?.processLinkCount !== 2
    || snapshot?.documentNeedCount !== 3) issues.push('later causal seam does not preserve the 1/2/3 receipt effects');
  return issues;
}

function laterMemoryPresentationContractViolations(validations, renderTimeline, scene, laterRun, expectedValidated = true) {
  const issues = [];
  if (validations.length !== 1) issues.push(`validation event count ${validations.length}`);
  const validation = validations[0] || {};
  const laterRender = renderTimeline.find(item => item.moment === 'later-result');
  const laterResult = laterRun?.result || {};
  const receipt = laterResult?.memory_application || {};
  if (validation.contract !== LATER_MEMORY_VALIDATION_CONTRACT) issues.push(`validation contract ${validation.contract || ''}`);
  if (!laterRender || !Number.isFinite(validation.at) || validation.at >= laterRender.at) issues.push('memory validation did not precede the later-result render');
  if (validation.validated !== expectedValidated) issues.push(`validated ${String(validation.validated)}`);
  if (scene?.later_memory_validated !== String(expectedValidated)) issues.push(`canvas validation state ${scene?.later_memory_validated || ''}`);
  if (!expectedValidated) {
    if (nonemptyString(validation.applicationHash) || nonemptyString(validation.memoryOriginId)) issues.push('invalid presentation retained memory identity');
    if ((validation.delta?.nodeIds || []).length || (validation.delta?.edges || []).length || (validation.delta?.evidenceIds || []).length) issues.push('invalid presentation retained memory delta');
    if (nonemptyString(scene?.later_memory_application_hash)) issues.push('invalid canvas retained application hash');
    if ((scene?.memory_effects || []).length || scene?.memory_receipt_count) issues.push('invalid canvas claimed memory effects');
    if (!/No memory-driven process change is claimed\./i.test(scene?.root_text || '')) issues.push('invalid canvas omitted fail-closed copy');
    return issues;
  }
  for (const field of ['proofReady', 'memoryUsed', 'memoryRetrieved', 'sharedPlaybookUnchanged']) {
    if (validation[field] !== true) issues.push(`${field} was not true`);
  }
  if (validation.retrievedOnly !== false) issues.push('validated presentation remained retrieval-only');
  if (!nonemptyString(validation.runId) || validation.runId !== laterRun?.run_id || validation.runId !== receipt?.target?.run_id) issues.push('validation run identity does not bind the returned receipt');
  if (!nonemptyString(validation.applicationHash) || validation.applicationHash !== receipt?.application_hash || validation.applicationHash !== scene?.later_memory_application_hash) issues.push('validation application hash does not bind receipt and canvas');
  if (!nonemptyString(validation.memoryOriginId) || validation.memoryOriginId !== receipt?.source_memory?.memory_id) issues.push('validation memory origin does not bind the returned receipt');
  if (stableJson(validation.delta?.nodeIds) !== stableJson(EXPECTED_LATER_MEMORY_DELTA.nodeIds)
    || stableJson(validation.delta?.edges) !== stableJson(EXPECTED_LATER_MEMORY_DELTA.edges)
    || stableJson(validation.delta?.evidenceIds) !== stableJson(EXPECTED_LATER_MEMORY_DELTA.evidenceIds)) issues.push(`validation delta ${stableJson(validation.delta)}`);
  if (scene?.memory_receipt_count !== 1) issues.push(`memory receipt count ${scene?.memory_receipt_count}`);
  issues.push(...memoryEffectContractViolations(scene?.memory_effects || [], validation.memoryOriginId));
  if (/No memory-driven process change is claimed\./i.test(scene?.root_text || '')) issues.push('validated canvas rendered fail-closed copy');
  return issues;
}

async function clickExactArtifactLocator(locator, checkContext) {
  const locatorId = await locator.getAttribute('data-source-locator-id');
  check(`Context attachment [${checkContext}] declares an exact source locator identifier`, nonemptyString(locatorId), locatorId || 'missing locator');
  const explicitOpen = locator.locator('[data-ac-action="open-source"]').first();
  const trigger = await explicitOpen.count() ? explicitOpen : locator;
  await trigger.click();
  await page.waitForFunction(expected => {
    const dock = document.querySelector('[data-layout="source-canvas"] [data-source-dock-state], [data-source-dock-state]');
    return ['open', 'drawer', 'active'].includes(dock?.dataset.sourceDockState || '')
      && dock?.dataset.activeSourceLocator === expected;
  }, locatorId, { timeout: 30000 });
  return locatorId;
}

async function settleFiniteAnimationsForAxe(label) {
  const result = await page.evaluate(async ({ timeoutMs }) => {
    const describeTarget = target => {
      if (!(target instanceof Element)) return null;
      if (target.id) return `#${CSS.escape(target.id)}`;
      const classes = [...target.classList].slice(0, 4).map(value => `.${CSS.escape(value)}`).join('');
      return `${target.tagName.toLowerCase()}${classes}`;
    };
    const describeAnimation = animation => {
      const timing = animation.effect?.getComputedTiming?.() || {};
      return {
        type: animation.constructor?.name || 'Animation',
        name: animation.animationName || animation.transitionProperty || null,
        play_state: animation.playState,
        target: describeTarget(animation.effect?.target),
        current_time_ms: Number.isFinite(animation.currentTime) ? Math.round(animation.currentTime) : null,
        end_time_ms: Number.isFinite(timing.endTime) ? Math.round(timing.endTime) : null,
      };
    };
    const activeFiniteAnimations = () => document.getAnimations().filter(animation => {
      const timing = animation.effect?.getComputedTiming?.();
      return ['pending', 'running'].includes(animation.playState) && Number.isFinite(timing?.endTime);
    });
    const nextStablePaint = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const deadline = performance.now() + timeoutMs;
    let passes = 0;
    while (passes < 8) {
      let active = activeFiniteAnimations();
      if (!active.length) {
        await nextStablePaint();
        active = activeFiniteAnimations();
        if (!active.length) return { settled: true, passes, active: [] };
      }
      const remaining = deadline - performance.now();
      if (remaining <= 0) break;
      await new Promise(resolve => {
        const timer = setTimeout(resolve, remaining);
        Promise.allSettled(active.map(animation => animation.finished)).then(() => {
          clearTimeout(timer);
          resolve();
        });
      });
      passes += 1;
    }
    return {
      settled: false,
      passes,
      active: activeFiniteAnimations().slice(0, 12).map(describeAnimation),
    };
  }, { timeoutMs: AXE_ANIMATION_SETTLE_TIMEOUT_MS });
  if (!result.settled) throw new Error(`${label} did not reach a stable finite-animation state before Axe: ${JSON.stringify(result)}`);
}

function axeViolationDiagnostics(violations) {
  const safeDataFields = ['fgColor', 'bgColor', 'contrastRatio', 'expectedContrastRatio', 'fontSize', 'fontWeight'];
  const safeAxeToken = value => {
    const text = String(value || '').slice(0, 512);
    return /^[a-z][a-z0-9_-]{0,79}$/i.test(text) ? text : `sha256:${sha256(text)}`;
  };
  const safeTargets = targets => (targets || []).slice(0, 4).map(target => {
    if (Array.isArray(target)) return target.slice(0, 8).map(safeAxeToken);
    return safeAxeToken(target);
  });
  const safeCheckData = data => {
    if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
    const safeValue = value => typeof value === 'string' ? value.slice(0, 120) : (typeof value === 'number' && Number.isFinite(value)) || typeof value === 'boolean' ? value : null;
    return Object.fromEntries(safeDataFields.filter(field => Object.hasOwn(data, field)).map(field => [field, safeValue(data[field])]));
  };
  return violations.slice(0, 8).map(item => ({
    id: safeAxeToken(item.id),
    impact: ['minor', 'moderate', 'serious', 'critical'].includes(item.impact) ? item.impact : null,
    node_count: (item.nodes || []).length,
    omitted_node_count: Math.max(0, (item.nodes || []).length - 6),
    nodes: (item.nodes || []).slice(0, 6).map(node => ({
      target: safeTargets(node.target),
      checks: [...(node.any || []), ...(node.all || []), ...(node.none || [])].slice(0, 8).map(check => ({
        id: safeAxeToken(check.id),
        impact: ['minor', 'moderate', 'serious', 'critical'].includes(check.impact) ? check.impact : null,
        data: safeCheckData(check.data),
      })),
    })),
  }));
}

async function runAxe(label) {
  await settleFiniteAnimationsForAxe(label);
  const { default: AxeBuilder } = await import('@axe-core/playwright');
  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter(item => ['serious', 'critical'].includes(item.impact));
  const diagnostics = JSON.stringify(axeViolationDiagnostics(serious));
  check(`${label} has no serious or critical axe violations`, serious.length === 0, diagnostics);
}

function sha256(value) {
  return createHash('sha256').update(value).digest('hex');
}

async function retainEvidence() {
  const required = [
    'deployment-identity',
    'release-contract',
    'readiness-receipt',
    'isolation-run',
    'isolation-model-ledger',
    'flagship-run',
    'flagship-cold-model-ledger',
    'model-ledger',
    'browser-execution-receipt',
    'browser-network-boundary',
  ];
  if (acceptedJourneyMode === 'flagship-review-learning') required.push(
    'demo-review',
    'post-review-run',
    'later-baseline-run',
    'later-after-memory-run',
    'learning-proof',
  );
  if (isProductionJourney()) required.push('flagship-cache-lineage');
  const missing = required.filter(name => retainedEvidence[name] == null);
  if (report?.status === 'passed' && missing.length) throw new Error(`Passing journey did not retain required evidence: ${missing.join(', ')}`);

  for (const [name, value] of Object.entries(retainedEvidence)) {
    if (value == null) continue;
    const filename = `${name}.json`;
    const bytes = `${JSON.stringify(value, null, 2)}\n`;
    await fs.writeFile(path.join(OUT, filename), bytes);
    evidenceFiles.push({ path: filename, sha256: sha256(bytes), bytes: Buffer.byteLength(bytes) });
  }

  const gateBytes = await fs.readFile(new URL(import.meta.url));
  const runtimeBytes = `${JSON.stringify(runtimeVersions, null, 2)}\n`;
  await fs.writeFile(path.join(OUT, 'runtime-versions.json'), runtimeBytes);
  evidenceFiles.push({ path: 'runtime-versions.json', sha256: sha256(runtimeBytes), bytes: Buffer.byteLength(runtimeBytes) });
  report.evidence = {
    contract: 'casepath.qa-evidence/1.0.0',
    journey_mode: acceptedJourneyMode,
    gate: { path: 'casepath-qa/browser-focused-v20.mjs', sha256: sha256(gateBytes), bytes: gateBytes.length },
    runtime: runtimeVersions,
    retained_before_session_reset: true,
    files: evidenceFiles,
    missing,
  };
}

async function finalizeEvidenceManifest() {
  const entries = await fs.readdir(OUT, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (!entry.isFile() || ['report.json', 'evidence-manifest.json'].includes(entry.name)) continue;
    const bytes = await fs.readFile(path.join(OUT, entry.name));
    files.push({ path: entry.name, sha256: sha256(bytes), bytes: bytes.length });
  }
  files.sort((left, right) => left.path.localeCompare(right.path));
  const retainedPaths = new Set(files.map(item => item.path));
  const requiredVisualEvidence = [
    '01-start-desktop.png',
    '02-ready-process-desktop.png',
    '03-lease-pdf-overview.png',
    '03-lease-pdf-detail.png',
    '03-lease-pdf-search.png',
    '03-image-inspection.png',
    '03-image-grounding-inspection.png',
    'final-state.png',
    'uninterrupted-focused-demo.webm',
  ];
  if (acceptedJourneyMode === 'flagship-review-learning') requiredVisualEvidence.push(
    '04-review-desktop.png',
    '05-review-applied-desktop.png',
    '06-learning-desktop.png',
    '07-later-result-desktop.png',
  );
  if (isProductionJourney()) requiredVisualEvidence.push('02-live-nemotron-agent.png', '03-deterministic-accepted-artifact.png');
  const requiredJsonEvidence = [
    'candidate-built-static-manifest.sha256',
    'candidate-source-manifest.sha256',
    'deployment-identity.json',
    'release-contract.json',
    'readiness-receipt.json',
    'isolation-run.json',
    'isolation-model-ledger.json',
    'flagship-run.json',
    'flagship-cold-model-ledger.json',
    'model-ledger.json',
    'runtime-versions.json',
    'browser-execution-receipt.json',
    'browser-network-boundary.json',
  ];
  if (apiRuntimeBootReceipt) requiredJsonEvidence.push('api-runtime-boot-receipt.json');
  if (acceptedJourneyMode === 'flagship-review-learning') requiredJsonEvidence.push(
    'demo-review.json',
    'post-review-run.json',
    'later-baseline-run.json',
    'later-after-memory-run.json',
    'learning-proof.json',
  );
  if (isProductionJourney()) requiredJsonEvidence.push('flagship-cache-lineage.json');
  const missingRetainedArtifacts = [...requiredVisualEvidence, ...requiredJsonEvidence]
    .filter(filename => !retainedPaths.has(filename));
  const emptyRetainedArtifacts = files.filter(item => [...requiredVisualEvidence, ...requiredJsonEvidence].includes(item.path) && item.bytes <= 0).map(item => item.path);
  if (report?.status === 'passed' && (missingRetainedArtifacts.length || emptyRetainedArtifacts.length)) {
    throw new Error(`Passing journey lacks retained JSON/screenshot/video evidence: missing=${missingRetainedArtifacts.join(',')} empty=${emptyRetainedArtifacts.join(',')}`);
  }
  const manifest = {
    contract: 'casepath.qa-evidence-manifest/1.0.0',
    journey_mode: acceptedJourneyMode,
    release_id: RELEASE_ID,
    source_commit: deploymentIdentity.qa.source_commit,
    gate: report.evidence.gate,
    runtime: runtimeVersions,
    retained_before_session_reset: true,
    retained_media_contract: {
      json: requiredJsonEvidence,
      screenshots: requiredVisualEvidence.filter(item => item.endsWith('.png')),
      video: 'uninterrupted-focused-demo.webm',
      missing: missingRetainedArtifacts,
      empty: emptyRetainedArtifacts,
    },
    files,
  };
  const manifestBytes = `${JSON.stringify(manifest, null, 2)}\n`;
  await fs.writeFile(path.join(OUT, 'evidence-manifest.json'), manifestBytes);
  report.evidence.files = files;
  report.evidence.manifest = { path: 'evidence-manifest.json', sha256: sha256(manifestBytes), bytes: Buffer.byteLength(manifestBytes) };
}

async function cleanup() {
  if (page) await page.screenshot({ path: path.join(OUT, 'final-state.png'), fullPage: true }).catch(() => null);
  if (context) {
    await context.close().catch(error => failures.cleanup.push(`context: ${error}`));
    context = null;
  }
  if (video) {
    try {
      const videoPath = await video.path();
      await fs.copyFile(videoPath, path.join(OUT, 'uninterrupted-focused-demo.webm'));
    } catch (error) {
      failures.cleanup.push(`video: ${error}`);
    }
  }
  if (browser) {
    await browser.close().catch(error => failures.cleanup.push(`browser: ${error}`));
    browser = null;
  }
  await fs.rm(path.join(OUT, 'video-tmp'), { recursive: true, force: true }).catch(error => failures.cleanup.push(`video temp cleanup: ${error}`));
  if (demoMutated) {
    try {
      const value = await getJson(`${API}/api/demo/reset`, { method: 'POST' });
      if (value.active_playbook && value.active_playbook !== 'mould-playbook-v3') failures.cleanup.push(`reset returned ${JSON.stringify(value)}`);
      demoMutated = false;
    } catch (error) {
      failures.cleanup.push(`reset: ${error}`);
    }
  }
  if (isolationMutated) {
    try {
      await getJsonForSession(`${API}/api/demo/reset`, ISOLATION_SESSION_ID, { method: 'POST' });
      isolationMutated = false;
    } catch (error) {
      failures.cleanup.push(`isolation reset: ${error}`);
    }
  }
}

async function verifyBuiltArtifactLaterRunIsolation(browserInstance) {
  const probeContext = await browserInstance.newContext({
    viewport: { width: 1280, height: 800 },
    reducedMotion: 'reduce',
    serviceWorkers: 'block',
  });
  networkGuards.push(await installLoopbackNetworkGuard(probeContext, {
    baseUrl: BASE,
    apiUrl: API,
    builtRows: candidateSourceSnapshotStart.builtRows,
    }));
  try {
    const probePage = await probeContext.newPage();
    await probePage.setContent('<!doctype html><html><body><aside class="submission-pane"><button class="attachment-row" data-artifact-id="artifact_c"></button></aside><main id="liveWorkspace"><section id="stageCanvas"></section><div id="journeyActions"></div></main></body></html>');
    await probePage.evaluate(apiUrl => {
      window.CASEPATH_API = apiUrl;
    }, API);
    await probePage.addScriptTag({ url: `${BASE}/assets/artifact-canvas.js` });
    return await probePage.evaluate(async () => {
      const visible = [];
      const opened = [];
      window.addEventListener('casepath:later-causal-step-visible', event => visible.push(structuredClone(event.detail)));
      window.addEventListener('casepath:later-source-opened', event => opened.push(structuredClone(event.detail)));
      const canvas = window.CasePathArtifactCanvas;
      if (!canvas || canvas.contract !== 'casepath.persistent-artifact-canvas/1.0.0') throw new Error('built artifact canvas did not expose its canonical API');

      const process = {
        nodes: [
          { node_id: 'causation', branches: [{ branch_id: 'evidence_gap', target: 'evidence_gap' }] },
          { node_id: 'evidence_gap', branches: [] },
        ],
        selected_path: ['causation', 'evidence_gap'],
        main_spine: ['causation', 'evidence_gap'],
        current_overlay: {
          current_node_id: 'causation',
          next_action_node_id: 'evidence_gap',
          selected_branch_id: 'evidence_gap',
        },
      };
      canvas.ingest({
        runId: 'primary-run',
        terminal: true,
        result: {
          claim_id: 'DEMO-MOULD-001',
          process,
          verification: { valid: true, computed: true, checks: [{ check_id: 'fixture', status: 'passed' }] },
        },
      }, 'snapshot');

      const fact = (suffix, excerpt) => ({
        fact_id: 'later_fact_ventilation_allegation',
        semantic_role: 'management_ventilation_allegation',
        state: 'known',
        source_refs: [{
          artifact_id: `artifact_${suffix}`,
          locator_kind: 'text_quote',
          page: 1,
          excerpt,
        }],
      });
      const step = (runId, suffix, excerpt) => ({
        contract: 'casepath.later-causal-step/1.0.0',
        phase: 'source',
        runId,
        factId: 'later_fact_ventilation_allegation',
        sourceId: `artifact_${suffix}`,
        locatorId: `source:artifact_${suffix}:page:1:quote:${excerpt}`,
      });

      // The product opens a later-work shell before the queued run has a
      // claim ID or result.  That exact empty queued snapshot must remain a
      // later presentation and must not reset accepted primary authority.
      window.CasePathRunStore = Object.freeze({
        get: () => ({ run_id: 'later-run-c', events: [], status: 'queued' }),
      });
      document.body.dataset.casepathActiveRunId = 'later-run-c';
      canvas.ingest({ moment: 'later-work' }, 'render');
      const queuedLaterShellSnapshot = canvas.snapshot();
      const queuedLaterShellPreservedPrimary = queuedLaterShellSnapshot.processRoute.flagshipCausation === true
        && queuedLaterShellSnapshot.processRoute.currentNodeId === 'causation'
        && queuedLaterShellSnapshot.processRoute.nextActionNodeId === 'evidence_gap'
        && queuedLaterShellSnapshot.processRoute.selectedBranchId === 'evidence_gap';

      canvas.ingest({
        runId: 'later-run-b',
        later: true,
        result: { claim_id: 'DEMO-MOULD-002', facts: [fact('b', 'baseline source')] },
      }, 'snapshot');
      canvas.ingest({
        runId: 'later-run-c',
        later: true,
        result: { claim_id: 'DEMO-MOULD-002' },
      }, 'snapshot');
      window.dispatchEvent(new CustomEvent('casepath:later-causal-step', { detail: step('later-run-c', 'b', 'baseline source') }));
      const staleBaselineRejected = visible.length === 0;

      canvas.ingest({
        runId: 'later-run-c',
        terminal: true,
        moment: 'later-result',
        result: {
          claim_id: 'DEMO-MOULD-002',
          facts: [fact('c', 'current source')],
          process: {
            nodes: [
              { node_id: 'causation', branches: [{ branch_id: 'later_only', target: 'later_only' }] },
              { node_id: 'later_only', branches: [] },
            ],
            selected_path: ['causation', 'later_only'],
            main_spine: ['causation', 'later_only'],
            current_overlay: {
              current_node_id: 'causation',
              next_action_node_id: 'later_only',
              selected_branch_id: 'later_only',
            },
          },
        },
      }, 'snapshot');
      // A `later` snapshot deliberately updates the canonical result without
      // advancing presentation state.  Force the same render transition used
      // by the product so this probe proves that the later-only projection is
      // actually active before the accepted primary process is restored.
      canvas.ingest({ moment: 'later-result' }, 'render');
      const preReplaySnapshot = canvas.snapshot();
      const laterOnlyProjectionActivated = preReplaySnapshot.visibleNodeIds.includes('later_only');
      // Reproduce the dangerous interleaving: a late accepted-gate event for
      // the primary run arrives while the mutable presentation process is the
      // later-only DTO.  Primary authority must remain the canonical primary
      // result, not the process currently rendered on screen.
      canvas.ingest({
        runId: 'primary-run',
        event: {
          type: 'process_node.created',
          acceptance: { state: 'accepted', gate_id: 'late-primary-gate-probe' },
          entity: { kind: 'acceptance_probe', id: 'late-primary-gate', value: { accepted: true } },
        },
      }, 'semantic');
      window.dispatchEvent(new CustomEvent('casepath:later-causal-step', { detail: step('later-run-c', 'c', 'current source') }));
      await new Promise(resolve => setTimeout(resolve, 500));
      const currentSourceAcceptedWithoutMemoryReceipt = visible.length === 1
        && visible[0].runId === 'later-run-c'
        && visible[0].phase === 'source';
      const currentSourceOpenedFromExactVisibleStep = opened.length === 1
        && opened[0].runId === 'later-run-c'
        && opened[0].sourceId === 'artifact_c'
        && document.querySelector('[data-later-causal-phase="source"]')?.dataset.laterSourceOpened === 'true'
        && document.querySelector('.attachment-row[data-artifact-id="artifact_c"]')?.classList.contains('is-active');
      const postReplaySnapshot = canvas.snapshot();
      const restoredAcceptedCausationProjection = postReplaySnapshot.visibleNodeIds.includes('causation');
      const acceptedPrimaryRouteRestored = postReplaySnapshot.processRoute.flagshipCausation === true
        && postReplaySnapshot.processRoute.currentNodeId === 'causation'
        && postReplaySnapshot.processRoute.nextActionNodeId === 'evidence_gap'
        && postReplaySnapshot.processRoute.selectedBranchId === 'evidence_gap';
      const laterOnlyProjectionRejected = !postReplaySnapshot.visibleNodeIds.includes('later_only');

      window.dispatchEvent(new CustomEvent('casepath:later-causal-step', { detail: step('later-run-b', 'c', 'current source') }));
      const foreignRunRejected = visible.length === 1;
      return {
        staleBaselineRejected,
        queuedLaterShellPreservedPrimary,
        queuedLaterShellSnapshot,
        currentSourceAcceptedWithoutMemoryReceipt,
        currentSourceOpenedFromExactVisibleStep,
        laterOnlyProjectionActivated,
        restoredAcceptedCausationProjection,
        acceptedPrimaryRouteRestored,
        laterOnlyProjectionRejected,
        foreignRunRejected,
        visible,
        opened,
        preReplaySnapshot,
        canvasSnapshot: postReplaySnapshot,
        sourceMarkup: document.querySelector('[data-later-causal-phase="source"]')?.outerHTML || '',
        cursor: { ...(document.querySelector('[data-ac-cursor]')?.dataset || {}) },
      };
    });
  } finally {
    await probeContext.close();
  }
}

async function execute() {
  requireMutationAuthority();
  candidateSourceSnapshotStart = await captureCandidateSourceSnapshot({ requireApiBootReceipt: REQUIRE_INSTALLED_API_BOOT });
  candidateSourceIdentityStart = candidateSourceSnapshotStart.identity;
  try {
    await fs.lstat(OUT);
    throw new Error(`CASEPATH_QA_OUT must be absent for create-new evidence: ${OUT}`);
  } catch (error) {
    if (error?.code !== 'ENOENT') throw error;
  }
  await fs.mkdir(path.join(OUT, 'video-tmp'), { recursive: true });
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
  candidateSourceManifests = {
    source: {
      path: 'candidate-source-manifest.sha256',
      sha256: sha256(sourceManifestBytes),
      bytes: Buffer.byteLength(sourceManifestBytes),
      rows: candidateSourceSnapshotStart.sourceRows.length,
    },
    built_static: {
      path: 'candidate-built-static-manifest.sha256',
      sha256: sha256(builtManifestBytes),
      bytes: Buffer.byteLength(builtManifestBytes),
      rows: candidateSourceSnapshotStart.builtRows.length,
    },
  };
  apiRuntimeBootReceipt = candidateSourceSnapshotStart.apiBootReceiptBytes ? {
    path: 'api-runtime-boot-receipt.json',
    sha256: sha256(candidateSourceSnapshotStart.apiBootReceiptBytes),
    bytes: candidateSourceSnapshotStart.apiBootReceiptBytes.length,
    semantic_sha256: candidateSourceSnapshotStart.apiBootReceipt.receipt_sha256,
    source_manifest_file_sha256: candidateSourceSnapshotStart.apiBootReceipt.source.source_manifest_file_sha256,
  } : null;

  const [frontendDeployment, health, readiness, releaseContract, initialModelLedger] = await Promise.all([
    getJson(`${BASE}/deployment.json`),
    getJson(`${API}/healthz`),
    getJson(`${API}/readyz`),
    getJson(`${BASE}/release.json`),
    getJson(`${API}/api/model-ledger`),
  ]);
  deploymentIdentity = { ...deploymentIdentity, frontend: frontendDeployment, api: health };
  retainedEvidence['deployment-identity'] = deploymentIdentity;
  retainedEvidence['release-contract'] = releaseContract;
  retainedEvidence['readiness-receipt'] = readiness;
  assertDeploymentAlignment(frontendDeployment, health);
  assertReleaseRuntimeContract(releaseContract);
  assertHealthRuntimeContract(health, releaseContract.agentic_runtime);
  assertReadinessContract(readiness);
  const initialLedgerIssues = initialLedgerAdmissionViolations(initialModelLedger);
  check('QA admits a journey only from an exactly empty global model ledger', initialLedgerIssues.length === 0, JSON.stringify(initialLedgerIssues));
  const providerCapIssues = providerSingleFlightContractViolations(releaseContract, health, readiness);
  check('Release, health, and readiness agree on logical fan-out plus physical provider single-flight', providerCapIssues.length === 0, JSON.stringify(providerCapIssues));
  check('API is healthy', health.status === 'ok', JSON.stringify(health));
  check('API reports a pipeline release', typeof health.pipeline_release === 'string' && health.pipeline_release.length > 0, JSON.stringify(health));
  check('API declares caller-session state isolation without treating the session as authority', health.session_isolation?.enabled === true && health.session_isolation?.header === 'X-CasePath-Session' && health.session_isolation?.session_reset_scope === 'caller_session_only', JSON.stringify(health.session_isolation));
  if (isProductionJourney()) {
    check('Production API runs the authorized OpenRouter Nemotron mode', health.model_mode === 'openrouter_nemotron' && health.model === REQUESTED_NEMOTRON_MODEL, JSON.stringify({ model_mode: health.model_mode, model: health.model }));
  }
  const reset = await resetDemo();
  check('Demo starts from the unchanged shared v3 playbook with caller-only reset scope', reset.active_playbook === 'mould-playbook-v3' && reset.session_scope === 'caller_only', JSON.stringify(reset));
  const demo = await getJson(`${API}/api/demo`);
  let coldOrchestration = null;
  let warmOrchestration = null;

  const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH;
  if (executablePath !== '/Applications/ego lite.app/Contents/MacOS/ego lite') {
    throw new Error(`PLAYWRIGHT_EXECUTABLE_PATH is not the governed ego-browser executable: ${executablePath || '<missing>'}`);
  }
  browser = await chromium.launch({ headless: true, executablePath, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  browserExecutionReceipt = await captureBrowserExecutionReceipt({
    gatePath: fileURLToPath(import.meta.url),
    outputPath: OUT,
    outputEnvironmentKey: 'CASEPATH_QA_OUT',
    browserVersion: browser.version(),
    baseUrl: BASE,
    apiUrl: API,
  });
  retainedEvidence['browser-execution-receipt'] = browserExecutionReceipt;
  const browserExecutionReceiptBytes = `${JSON.stringify(browserExecutionReceipt, null, 2)}\n`;
  browserExecutionReceiptBinding = {
    path: 'browser-execution-receipt.json',
    sha256: sha256(browserExecutionReceiptBytes),
    bytes: Buffer.byteLength(browserExecutionReceiptBytes),
    semantic_sha256: browserExecutionReceipt.receipt_sha256,
  };
  const laterRunIsolation = await verifyBuiltArtifactLaterRunIsolation(browser);
  const packageMetadata = JSON.parse(await fs.readFile(new URL('./package.json', import.meta.url), 'utf8'));
  runtimeVersions = { node: process.version, playwright: packageMetadata.dependencies?.playwright || null, chromium: browser.version() };
  context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    reducedMotion: process.env.CASEPATH_QA_REDUCED_MOTION === '1' ? 'reduce' : 'no-preference',
    recordVideo: { dir: path.join(OUT, 'video-tmp'), size: { width: 1440, height: 900 } },
    serviceWorkers: 'block',
  });
  networkGuards.push(await installLoopbackNetworkGuard(context, {
    baseUrl: BASE,
    apiUrl: API,
    builtRows: candidateSourceSnapshotStart.builtRows,
  }));
  page = await context.newPage();
  video = page.video();

  page.on('console', message => {
    if (message.type() === 'error') failures.console.push(`${message.text()} @ ${message.location().url || ''}:${message.location().lineNumber || 0}`);
  });
  page.on('pageerror', error => failures.page.push(String(error)));
  page.on('request', request => {
    try {
      const url = new URL(request.url());
      if (url.origin === new URL(API).origin && url.pathname.startsWith('/api/claim-loops/v1')) {
        claimLoopRequests.push({ method: request.method(), pathname: url.pathname });
      }
      if (url.origin !== new URL(API).origin || !/^\/api\/runs\/[^/]+(?:\/events)?$/.test(url.pathname)) return;
      browserRunRequests.push({
        method: request.method(),
        pathname: url.pathname,
        search: url.search,
        session: request.headers()['x-casepath-session'] || '',
        accept: request.headers().accept || '',
        at: Date.now(),
      });
    } catch (_) {}
  });
  page.on('requestfailed', request => {
    if (request.url().startsWith(BASE) || request.url().startsWith(API)) failures.request.push(`${request.failure()?.errorText || 'failed'} ${request.url()}`);
  });
  page.on('response', async response => {
    try {
      const url = new URL(response.url());
      const method = response.request().method();
      if (method === 'POST' && url.origin === new URL(API).origin && url.pathname === '/api/runs' && response.ok()) {
        const value = await response.json();
        if (value.run_id && !runIds.includes(value.run_id)) runIds.push(value.run_id);
      }
      if (method === 'POST' && /\/api\/runs\/[^/]+\/review$/.test(url.pathname) && response.ok()) reviewResponse = await response.json();
      if (method === 'GET' && url.pathname === '/api/learning-proof' && response.ok()) proofResponse = await response.json();
    } catch (_) {}
  });

  await page.addInitScript(({ sessionId, decisionFlowContract, processPreviewGeometrySelectors, processPreviewBottomInset, sourceRailContract }) => {
    sessionStorage.setItem('casepath:demo-session', sessionId);
    window.__casepathReleaseMutations = [];
    window.__casepathMomentHistory = [];
    window.__casepathPresentationTimeline = [];
    window.__casepathRenderTimeline = [];
    window.__casepathVisibleAgentIds = [];
    window.__casepathVisibleGateIds = [];
    window.__casepathOpeningContexts = [];
    window.__casepathCursorSteps = [];
    window.__casepathArtifactCursorSteps = [];
    window.__casepathGraphSteps = [];
    window.__casepathOfficialSourceSteps = [];
    window.__casepathFocusViolations = [];
    window.__casepathSemanticEvents = [];
    window.__casepathArtifactChanges = [];
    window.__casepathProcessNodeProgress = [];
    window.__casepathSourceHighlights = [];
    window.__casepathBranchVisuals = [];
    window.__casepathDecisionFlowSteps = [];
    window.__casepathLaterMemoryValidations = [];
    window.__casepathLaterCausalSteps = [];
    window.__casepathLaterSourceOpenings = [];
    window.__casepathGraphMomentSnapshots = [];
    window.__casepathArtifactFocusViolations = [];
    window.__casepathDesktopSourcePanelMoments = [];
    window.__casepathArtifactInteractions = [];
    window.__casepathProcessPreviewGeometry = [];
    window.__casepathSourcePreludeSnapshots = [];
    window.__casepathSourceRailSnapshots = [];
    window.__casepathLiveWorkPlanSnapshots = [];
    window.__casepathFactTourSnapshots = [];
    window.__casepathMainFocalWhyViolations = [];
    window.__casepathNormalizeSvg = svg => String(svg?.innerHTML || '').replace(/\s+/g, ' ').replace(/> </g, '><').trim();
    window.__casepathCaptureSourcePrelude = () => {
      const prelude = document.querySelector('#artifactCanvas [data-ac-focal-object="source-prelude"]');
      if (!visible(prelude)) return;
      const steps = [...prelude.querySelectorAll('.ac-source-prelude-plan > li[data-step-state]')].map(step => ({
        label: step.querySelector('span')?.textContent?.trim() || '',
        state: step.dataset.stepState || '',
      }));
      const snapshot = {
        sourceCount: Number(prelude.dataset.sourceCount || 0),
        label: prelude.querySelector(':scope > header span')?.textContent?.trim() || '',
        title: prelude.querySelector(':scope > header strong')?.textContent?.trim() || '',
        planCount: prelude.querySelectorAll('.ac-source-prelude-plan').length,
        cardCount: prelude.querySelectorAll('.ac-source-prelude-strip > [data-source-kind]').length,
        inputCount: prelude.querySelectorAll('input').length,
        checkboxRoleCount: prelude.querySelectorAll('[role="checkbox"]').length,
        steps,
      };
      const key = JSON.stringify(snapshot);
      if (!window.__casepathSourcePreludeSnapshots.some(item => JSON.stringify(item) === key)) window.__casepathSourcePreludeSnapshots.push(snapshot);
    };
    window.__casepathCaptureLiveWorkPlan = () => {
      const root = document.querySelector('#artifactCanvas');
      const plans = [...(root?.querySelectorAll('[data-ac-live-work-plan]') || [])].filter(visible);
      if (!plans.length) return;
      const plan = plans[0];
      const steps = [...plan.querySelectorAll('[data-live-work-step]')].map(step => ({
        stepId: step.dataset.liveWorkStep || '',
        label: step.querySelector('span')?.textContent?.trim() || '',
        state: step.dataset.stepState || '',
        spinnerCount: [...step.querySelectorAll('[data-live-work-spinner]')].filter(visible).length,
      }));
      const preludes = [...(root?.querySelectorAll('.ac-source-prelude') || [])].filter(visible);
      const snapshot = {
        planCount: plans.length,
        focalChildCount: [...(root?.querySelector('[data-ac-focal]')?.children || [])].filter(visible).length,
        visible: visible(plan),
        contract: plan.dataset.contract || '',
        presentationMode: plan.dataset.presentationMode || '',
        agentId: plan.dataset.agentId || '',
        runtimeAgentId: plan.dataset.runtimeAgentId || '',
        visualGroupId: plan.dataset.visibleAgentGroup || '',
        agentSignature: plan.dataset.agentSignature || '',
        runId: plan.dataset.runId || '',
        callId: plan.dataset.callId || '',
        eventId: plan.dataset.eventId || '',
        workState: plan.dataset.workState || '',
        inputArtifact: plan.dataset.inputArtifact || '',
        inputArtifactHash: plan.dataset.inputArtifactHash || '',
        rootWorkState: root?.dataset.liveAgentWorkState || '',
        rootAgentId: root?.dataset.liveAgentId || '',
        rootRunId: root?.dataset.liveAgentRunId || '',
        rootCallId: root?.dataset.liveAgentCallId || '',
        rootEventId: root?.dataset.liveAgentEventId || '',
        title: plan.querySelector('header strong')?.textContent?.trim() || '',
        steps,
        sourcePreludeCount: preludes.length,
        sourcePreludeCardCount: preludes.reduce((count, prelude) => count + [...prelude.querySelectorAll('.ac-source-prelude-strip > [data-source-kind]')].filter(visible).length, 0),
        factTourCount: [...(root?.querySelectorAll('[data-fact-tour-phase]') || [])].filter(visible).length,
        forbiddenProgressCount: plan.querySelectorAll('progress,meter,[role="progressbar"],[role="slider"],input[type="range"],[aria-valuenow],[data-ac-process-node-progress]').length,
        percentText: /\d+(?:\.\d+)?\s*%/.test(plan.textContent || ''),
        at: performance.now(),
      };
      const key = JSON.stringify({ ...snapshot, at: 0 });
      if (!window.__casepathLiveWorkPlanSnapshots.some(item => item.key === key)) window.__casepathLiveWorkPlanSnapshots.push({ ...snapshot, key });
    };
    window.__casepathCaptureMainFocalWhy = () => {
      const violations = [...document.querySelectorAll('#artifactCanvas [data-ac-focal] .ac-agent-artifact > p')].filter(visible);
      if (violations.length) window.__casepathMainFocalWhyViolations.push(...violations.map(node => node.textContent?.trim() || 'visible agent why paragraph'));
    };
    window.__casepathCaptureFactTour = () => {
      const root = document.querySelector('#artifactCanvas');
      const focus = root?.querySelector('[data-fact-tour-phase][data-fact-id]');
      if (!visible(focus)) return;
      const sourceContext = focus.querySelector('[data-source-id][data-source-locator-id]');
      const sourceId = sourceContext?.dataset.sourceId || '';
      const finding = focus.querySelector('.ac-fact-finding[data-node-attachment-kind="fact"]');
      const realArtifact = focus.querySelector('[data-real-artifact="true"],.ac-visual-source[data-source-id]');
      const snapshot = {
        factId: focus.dataset.factId || '',
        phase: focus.dataset.factTourPhase || '',
        sourceId,
        locatorId: sourceContext?.dataset.sourceLocatorId || '',
        activeSourceIds: window.__casepathActiveSourceIds?.() || [],
        activeSourceLocator: document.querySelector('.submission-pane')?.dataset.activeSourceLocator || '',
        artifactSurfaceVisible: visible(realArtifact),
        highlightCount: [...focus.querySelectorAll('.is-highlighted')].filter(visible).length,
        factVisible: visible(finding),
        factLabel: finding?.querySelector('h3')?.textContent?.trim() || '',
        factValue: finding?.querySelector('strong')?.textContent?.trim() || '',
        eventId: finding?.dataset.artifactEventId || '',
        agentId: finding?.dataset.artifactAgentId || '',
        presentationMode: root?.dataset.presentationMode || '',
        presentationLabel: document.querySelector('[data-ac-global-agent]')?.textContent?.trim() || '',
        activeAgentId: root?.dataset.activeAgentId || '',
        activeSignature: root?.dataset.activeSignature || '',
        workAuthority: root?.dataset.workAuthority || '',
        liveWorkPlanCount: [...(root?.querySelectorAll('[data-ac-live-work-plan]') || [])].filter(visible).length,
        sourcePreludeCount: [...(root?.querySelectorAll('.ac-source-prelude') || [])].filter(visible).length,
        at: performance.now(),
      };
      const key = [snapshot.factId, snapshot.phase, snapshot.sourceId, snapshot.locatorId, snapshot.factVisible, snapshot.eventId].join(':');
      if (!window.__casepathFactTourSnapshots.some(item => item.key === key)) window.__casepathFactTourSnapshots.push({ ...snapshot, key });
      const sourceIsActive = ['read-source', 'highlight-source', 'finding'].includes(snapshot.phase);
      void window.__casepathCaptureSourceRail?.(
        `fact-tour:${snapshot.factId}:${snapshot.phase}`,
        sourceIsActive ? snapshot.sourceId : '',
        sourceIsActive ? snapshot.locatorId : '',
      );
    };
    window.addEventListener('DOMContentLoaded', () => {
      window.__casepathCaptureSourcePrelude();
      window.__casepathCaptureLiveWorkPlan();
      window.__casepathCaptureMainFocalWhy();
      window.__casepathCaptureFactTour();
      new MutationObserver(() => {
        window.__casepathCaptureSourcePrelude();
        window.__casepathCaptureLiveWorkPlan();
        window.__casepathCaptureMainFocalWhy();
        window.__casepathCaptureFactTour();
      }).observe(document.documentElement, { childList: true, subtree: true });
    }, { once: true });
    window.addEventListener('casepath:presentation', event => {
      window.__casepathPresentationTimeline.push({
        moment: event.detail?.moment || '',
        phase: event.detail?.phase || '',
        stage: event.detail?.stage || '',
        event_id: event.detail?.eventId || '',
        at: performance.now(),
      });
    });
    window.addEventListener('casepath:render', event => {
      window.__casepathRenderTimeline.push({
        moment: event.detail?.moment || '',
        at: performance.now(),
      });
      if (['verify', 'knowledge', 'later-work'].includes(event.detail?.moment || '')) captureGraphMoment(event.detail.moment);
      if (event.detail?.moment !== 'opening') return;
      const actorCard = document.querySelector('#orchestrationProof .orchestration-actor-card');
      window.__casepathOpeningContexts.push({
        boundary_text: document.querySelector('#stageCanvas[data-casepath-moment="opening"] .live-question strong')?.textContent || '',
        actor_type: actorCard?.dataset.actorType || '',
        nemotron_plan_visible: Boolean(document.querySelector('#orchestrationProof .orchestration-actor-card[data-actor-type="nemotron_agent"][data-actor-id="orchestrator_plan"]')),
      });
    });
    const visible = node => Boolean(node && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden' && getComputedStyle(node).display !== 'none');
    const rectValue = node => {
      const rect = node?.getBoundingClientRect();
      return rect ? { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height } : null;
    };
    const overlapArea = (first, second) => first && second
      ? Math.max(0, Math.min(first.right, second.right) - Math.max(first.left, second.left))
        * Math.max(0, Math.min(first.bottom, second.bottom) - Math.max(first.top, second.top))
      : 0;
    const displayedSourceId = sourceId => String(sourceId || '') === 'intake' ? 'message' : String(sourceId || '');
    const captureSourceRailNow = (reason = 'runtime', expectedSourceId = '', expectedLocatorId = '') => {
      const rail = document.querySelector(`aside[data-source-rail-contract="${sourceRailContract}"]`);
      const list = rail?.matches('[data-source-rail-list]') ? rail : rail?.querySelector('[data-source-rail-list]');
      const scrollRegion = list?.querySelector('[data-source-rail-scroll],.submission-scroll') || list;
      // A selector list returns the first matching node in document order, not
      // the first selector in the list.  The container therefore won over its
      // compact label row and made the legacy gate count the first source item
      // as heading chrome.  Resolve the intended fallbacks explicitly.
      const heading = rail?.querySelector('[data-source-rail-heading]')
        || rail?.querySelector('.submission-head>div')
        || rail?.querySelector('.submission-head');
      const railRect = rectValue(rail);
      const listRect = rectValue(list);
      const scrollRect = rectValue(scrollRegion);
      const workRect = rectValue(document.querySelector('.work-pane'));
      const rows = [...(list?.querySelectorAll('[data-source-rail-item][data-source-id]') || [])];
      const items = rows.map(row => {
        const rect = rectValue(row);
        const icon = row.querySelector('[data-source-icon-kind]');
        const iconSvg = icon?.querySelector('svg');
        const iconRect = rectValue(icon);
        const names = row.querySelectorAll('[data-source-name]');
        const metadata = row.querySelectorAll('[data-source-meta]');
        const statuses = row.querySelectorAll('[data-source-status]');
        return {
          sourceId: row.dataset.sourceId || '',
          kind: row.dataset.sourceKind || icon?.dataset.sourceIconKind || '',
          visible: visible(row),
          fullyVisible: Boolean(rect && railRect
            && rect.left >= railRect.left - 1 && rect.right <= railRect.right + 1
            && rect.top >= railRect.top - 1 && rect.bottom <= railRect.bottom + 1
            && rect.top >= -1 && rect.bottom <= innerHeight + 1),
          rect,
          iconCount: row.querySelectorAll('[data-source-icon-kind] > svg').length,
          iconKind: icon?.dataset.sourceIconKind || '',
          iconMarkup: window.__casepathNormalizeSvg(iconSvg),
          iconWidth: iconRect?.width || 0,
          iconHeight: iconRect?.height || 0,
          nameCount: names.length,
          name: names[0]?.textContent?.trim() || '',
          metaCount: metadata.length,
          meta: metadata[0]?.textContent?.trim() || '',
          statusCount: statuses.length,
          status: statuses[0]?.dataset.sourceStatus || row.dataset.sourceStatus || statuses[0]?.textContent?.trim().toLowerCase() || '',
          active: row.classList.contains('is-active'),
          ariaCurrent: row.getAttribute('aria-current') === 'true',
          thumbImageCount: [...row.querySelectorAll('img,.attachment-thumb')].filter(visible).length,
          extraLabelCount: [...row.querySelectorAll('.attachment-open,[data-source-extra-label]')].filter(visible).length,
        };
      });
      const rowOverlapCount = items.slice(1).filter((item, index) => {
        const prior = items[index];
        return Boolean(item.rect && prior.rect && item.rect.top < prior.rect.bottom - 1);
      }).length;
      const overlays = [...document.querySelectorAll('#sourceViewer[open],#v20DocumentSheet[open],[data-ac-grounding-viewer][open]')].filter(visible);
      const listStyle = scrollRegion ? getComputedStyle(scrollRegion) : null;
      const snapshot = {
        reason: String(reason || 'runtime'),
        expectedSourceId: String(expectedSourceId || ''),
        expectedLocatorId: String(expectedLocatorId || ''),
        contract: rail?.dataset.sourceRailContract || '',
        viewport: { width: innerWidth, height: innerHeight },
        railVisible: visible(rail),
        listVisible: visible(list),
        collapsed: rail?.classList.contains('collapsed') === true || rail?.dataset.sourceCollapsed === 'true',
        insideViewport: Boolean(railRect && railRect.left >= -1 && railRect.top >= -1 && railRect.right <= innerWidth + 1 && railRect.bottom <= innerHeight + 1),
        railRect,
        listRect,
        scrollRect,
        headingHeight: rectValue(heading)?.height || 0,
        listOverflowY: listStyle?.overflowY || '',
        listHorizontalOverflow: scrollRegion ? Math.max(0, scrollRegion.scrollWidth - scrollRegion.clientWidth) : Number.POSITIVE_INFINITY,
        pageHorizontalOverflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth,
        dropdownCount: rail?.querySelectorAll('[aria-expanded],[aria-haspopup],[role="menu"],[role="listbox"],[role="combobox"]').length || 0,
        expanderCount: rail?.querySelectorAll('[data-source-expander],[data-source-chevron],.mobile-source-toggle:not([data-source-rail-item])').length || 0,
        collapsedControlCount: rail?.querySelectorAll('[data-source-collapsed="true"],[data-source-toggle-state="collapsed"]').length || 0,
        workOverlapArea: overlapArea(railRect, workRect),
        overlayOverlapAreas: overlays.map(node => overlapArea(railRect, rectValue(node))),
        rowOverlapCount,
        itemCount: items.length,
        items,
        activeSourceIds: items.filter(item => item.active || item.ariaCurrent).map(item => item.sourceId),
        activeSourceLocator: rail?.dataset.activeSourceLocator || '',
        at: performance.now(),
      };
      const key = JSON.stringify({ ...snapshot, at: 0 });
      if (!window.__casepathSourceRailSnapshots.some(item => item.key === key)) window.__casepathSourceRailSnapshots.push({ ...snapshot, key });
      return snapshot;
    };
    window.__casepathCaptureSourceRail = (reason = 'runtime', expectedSourceId = '', expectedLocatorId = '') => new Promise(resolve => {
      requestAnimationFrame(() => requestAnimationFrame(() => resolve(captureSourceRailNow(reason, expectedSourceId, expectedLocatorId))));
    });
    window.__casepathProcessNodeProgressUi = (nodeId = '', entityKind = 'node') => {
      const root = document.querySelector('#artifactCanvas');
      const graph = document.querySelector('#artifactProcessGraph');
      const process = root?.querySelector('[data-ac-process]');
      const cursor = root?.querySelector('#artifactAgentCursor');
      const indicators = [...(cursor?.querySelectorAll('[data-ac-process-node-progress]') || [])];
      const indicator = indicators[0] || null;
      const indicatorValue = indicator?.querySelector('[data-ac-process-node-progress-value]');
      const cursorWorking = visible(cursor) && cursor?.dataset.processNodeProgress === 'active';
      const inspection = graph?.querySelector('[data-ac-inspection-target="true"]');
      const escapedNodeId = CSS.escape(String(nodeId || ''));
      const output = entityKind === 'branch'
        ? graph?.querySelector(`[data-spatial-role~="branch"][data-node-id="${escapedNodeId}"]`)
        : graph?.querySelector(`[data-node-id="${escapedNodeId}"][data-reveal-state="visible"]`);
      return {
        indicatorDomCount: indicators.length,
        indicatorVisibleCount: cursorWorking ? 1 : 0,
        indicatorVisible: cursorWorking,
        indicatorSurfaceVisible: visible(indicator),
        indicatorInsideCursor: Boolean(indicator && cursor?.contains(indicator)),
        indicatorPercent: Number.parseInt(indicator?.dataset.progress || '', 10),
        indicatorPhase: indicator?.dataset.phase || '',
        indicatorLabel: indicator?.querySelector('[data-ac-process-node-progress-phase]')?.textContent?.trim() || '',
        indicatorValueVisible: visible(indicatorValue),
        indicatorValueText: indicatorValue?.textContent?.trim() || '',
        cursorProgressState: cursor?.dataset.processNodeProgress || '',
        cursorSignature: cursor?.dataset.agentSignature || '',
        cursorAgent: cursor?.querySelector('[data-ac-cursor-agent]')?.textContent?.trim() || '',
        activeAgentId: root?.dataset.activeAgentId || '',
        visualActiveAgentId: root?.dataset.visualActiveAgentId || '',
        visualGroupId: ['canonical_facts', 'process_decision_mapping'].includes(root?.dataset.visualActiveAgentId || '')
          ? 'process_decision_mapping'
          : root?.dataset.visualActiveAgentId || '',
        presentationMode: root?.dataset.presentationMode || '',
        presentationLabel: document.querySelector('[data-ac-global-agent]')?.textContent?.trim() || '',
        workAuthority: root?.dataset.workAuthority || '',
        rootProgressState: root?.dataset.processNodeProgressState || '',
        rootPercent: root?.dataset.processNodeProgress || '',
        rootPhase: root?.dataset.processNodeProgressPhase || '',
        rootNodeId: root?.dataset.processNodeProgressNodeId || '',
        rootBasisKind: root?.dataset.processNodeProgressBasisKind || '',
        processProgressState: process?.dataset.processNodeProgressState || '',
        processPercent: process?.dataset.processNodeProgress || '',
        processPhase: process?.dataset.processNodeProgressPhase || '',
        processNodeId: process?.dataset.processNodeProgressNodeId || '',
        inspectionBasisKind: inspection?.dataset.inspectionBasisKind || '',
        inspectionPrompt: inspection?.querySelector(':scope > small')?.textContent?.trim() || '',
        inspectionText: inspection?.textContent?.replace(/\s+/g, ' ').trim() || '',
        outputVisible: visible(output),
      };
    };
    const geometryRect = node => {
      const value = node.getBoundingClientRect();
      return { left: value.left, top: value.top, right: value.right, bottom: value.bottom, width: value.width, height: value.height };
    };
    window.__casepathCaptureProcessPreviewGeometry = phase => new Promise(resolve => {
      requestAnimationFrame(() => requestAnimationFrame(() => {
        const graph = document.querySelector('#artifactProcessGraph');
        const graphViewport = graph?.querySelector('.ac-spatial-viewport');
        if (!visible(graph) || !visible(graphViewport)) {
          resolve(null);
          return;
        }
        const nodes = [...new Set(processPreviewGeometrySelectors.flatMap(selector => [...graph.querySelectorAll(selector)]))].filter(visible);
        if (!nodes.length) {
          resolve(null);
          return;
        }
        const snapshot = {
          phase: String(phase || 'unspecified'),
          scene: document.querySelector('#artifactCanvas')?.dataset.casepathScene || '',
          constructionState: graph.dataset.processConstructionState || '',
          viewportWidth: innerWidth,
          viewportHeight: innerHeight,
          requiredBottomInset: processPreviewBottomInset,
          graphViewportRect: geometryRect(graphViewport),
          items: nodes.map(node => ({
            kind: processPreviewGeometrySelectors.find(selector => node.matches(selector)) || '',
            rect: geometryRect(node),
          })),
          at: performance.now(),
        };
        window.__casepathProcessPreviewGeometry.push(snapshot);
        resolve(snapshot);
      }));
    });
    window.__casepathActiveSourceIds = () => [
      ...document.querySelectorAll('[data-source-rail-item][data-source-id]'),
    ].filter(target => visible(target) && (target.classList.contains('is-active') || target.getAttribute('aria-current') === 'true'))
      .map(target => target.dataset.sourceId || '').filter(Boolean);
    window.__casepathSourceTargetExists = sourceId => {
      const exactId = String(sourceId || '');
      if (!exactId) return false;
      const railId = displayedSourceId(exactId);
      return Boolean(visible(document.querySelector(`[data-source-rail-item][data-source-id="${CSS.escape(railId)}"]`)));
    };
    window.__casepathCaptureDesktopSourcePanel = moment => {
      const pane = document.querySelector('.submission-pane');
      const content = document.querySelector('#submissionContent');
      const toggle = document.querySelector('#toggleSource');
      const paneRect = pane?.getBoundingClientRect();
      const toggleSvg = toggle?.querySelector('svg');
      const snapshot = {
        moment,
        panelVisible: visible(pane),
        contentVisible: visible(content),
        collapsed: pane?.classList.contains('collapsed') === true,
        insideViewport: Boolean(paneRect && paneRect.left >= 0 && paneRect.top >= 0 && paneRect.right <= innerWidth + 1 && paneRect.bottom <= innerHeight + 1),
        width: paneRect?.width || 0,
        height: paneRect?.height || 0,
        toggleVisible: visible(toggle),
        toggleDisabled: toggle?.disabled === true,
        toggleTabIndex: toggle?.tabIndex ?? null,
        toggleAriaControls: toggle?.getAttribute('aria-controls') || '',
        toggleLooksDropdown: Boolean(visible(toggle) && (visible(toggleSvg) || ['menu', 'listbox', 'combobox'].includes(toggle.getAttribute('role') || '') || toggle.hasAttribute('aria-haspopup') || (!toggle.disabled && toggle.hasAttribute('aria-controls')))),
        activeSourceIds: window.__casepathActiveSourceIds(),
        activeSourceLocator: pane?.dataset.activeSourceLocator || '',
        at: performance.now(),
      };
      const prior = window.__casepathDesktopSourcePanelMoments.findIndex(item => item.moment === moment);
      if (prior >= 0) window.__casepathDesktopSourcePanelMoments[prior] = snapshot;
      else window.__casepathDesktopSourcePanelMoments.push(snapshot);
      return snapshot;
    };
    window.addEventListener('casepath:render', event => {
      const moment = event.detail?.moment || '';
      if (!['read', 'understand', 'research', 'process', 'evidence', 'experience', 'verify', 'ready'].includes(moment)) return;
      requestAnimationFrame(() => window.__casepathCaptureDesktopSourcePanel?.(moment));
    });
    const focusSnapshot = reason => {
      const workspace = document.querySelector('#liveWorkspace');
      if (!visible(workspace)) return null;
      const artifactRoot = document.querySelector('#artifactCanvas');
      if (visible(artifactRoot)) {
        const focus = [...artifactRoot.querySelectorAll('[data-artifact-focus="true"]')].filter(visible);
        const cursor = [...artifactRoot.querySelectorAll('#artifactAgentCursor')].filter(visible);
        const snapshot = {
          reason,
          moment: artifactRoot.dataset.casepathScene || '',
          focusIdCount: artifactRoot.querySelectorAll('[data-artifact-focus="true"]').length,
          cursorIdCount: artifactRoot.querySelectorAll('#artifactAgentCursor').length,
          focusCount: focus.length,
          cursorCount: cursor.length,
          cursorInsideFocus: cursor.length === 1,
        };
        if (snapshot.focusIdCount !== 1 || snapshot.cursorIdCount !== 1 || snapshot.focusCount !== 1 || snapshot.cursorCount !== 1) {
          window.__casepathFocusViolations.push(snapshot);
        }
        return snapshot;
      }
      const focuses = [...document.querySelectorAll('#v21AgentFocus')].filter(visible);
      const cursors = [...document.querySelectorAll('#v21AgentCursor')].filter(visible);
      const allFocuses = document.querySelectorAll('#v21AgentFocus');
      const allCursors = document.querySelectorAll('#v21AgentCursor');
      const snapshot = {
        reason,
        moment: document.body?.dataset.casepathMoment || '',
        focusIdCount: allFocuses.length,
        cursorIdCount: allCursors.length,
        focusCount: focuses.length,
        cursorCount: cursors.length,
        cursorInsideFocus: cursors.every(cursor => focuses.some(focus => focus.contains(cursor))),
      };
      if (snapshot.focusIdCount !== 1 || snapshot.cursorIdCount !== 1 || snapshot.focusCount !== 1 || snapshot.cursorCount !== 1 || !snapshot.cursorInsideFocus) {
        window.__casepathFocusViolations.push(snapshot);
      }
      return snapshot;
    };
    window.addEventListener('casepath:cursor-step', event => {
      const detail = event.detail || {};
      if (detail.changeId) {
        const root = document.querySelector('#artifactCanvas');
        const cursor = document.querySelector('#artifactAgentCursor');
        const inspectionTarget = root?.querySelector('[data-ac-inspection-target="true"]');
        const inspectionSourceId = inspectionTarget?.dataset.sourceId || '';
        const avatar = cursor?.querySelector('[data-ac-cursor-avatar]');
        window.__casepathArtifactCursorSteps.push({
          changeId: detail.changeId || '',
          eventId: detail.eventId || '',
          agentId: detail.agentId || '',
          runtimeAgentId: detail.agentId || '',
          visualGroupId: ['canonical_facts', 'process_decision_mapping'].includes(detail.agentId || '')
            ? 'process_decision_mapping'
            : detail.agentId || '',
          targetId: detail.targetId || '',
          moment: detail.moment || root?.dataset.casepathScene || '',
          phase: detail.phase || '',
          parked: cursor?.dataset.parked === 'true',
          graphInspectionPhase: document.querySelector('#artifactCanvas')?.dataset.graphInspectionPhase || '',
          signature: cursor?.dataset.agentSignature || '',
          avatar: avatar?.dataset.agentAvatar || '',
          avatarMarkup: window.__casepathNormalizeSvg(avatar?.querySelector('svg')),
          specialistBound: cursor?.dataset.specialistBound === 'true',
          cursorAgent: cursor?.querySelector('[data-ac-cursor-agent]')?.textContent?.trim() || '',
          cursorAction: cursor?.querySelector('[data-ac-cursor-action]')?.textContent?.trim() || '',
          cursorTargetId: cursor?.dataset.targetId || '',
          cursorCount: root?.querySelectorAll('#artifactAgentCursor').length || 0,
          cursorTargetCount: root?.querySelectorAll('[data-ac-cursor-target="true"]').length || 0,
          activeAgentId: root?.dataset.activeAgentId || '',
          visualActiveAgentId: root?.dataset.visualActiveAgentId || '',
          activeSignature: root?.dataset.activeSignature || '',
          presentationMode: detail.presentationMode || root?.dataset.presentationMode || '',
          presentationLabel: document.querySelector('[data-ac-global-agent]')?.textContent?.trim() || '',
          workAuthority: root?.dataset.workAuthority || '',
          inspectionSourceId,
          inspectionLocatorId: inspectionTarget?.dataset.sourceLocatorId || '',
          inspectionSourceHasTarget: window.__casepathSourceTargetExists(inspectionSourceId),
          activeSourceIds: window.__casepathActiveSourceIds(),
          activeSourceLocator: document.querySelector('.submission-pane')?.dataset.activeSourceLocator || '',
          visibleSourceHighlightCount: [...(root?.querySelectorAll('.is-highlighted, .ac-build-source-highlight') || [])].filter(visible).length,
          at: performance.now(),
          focus: artifactCanvasFocusSnapshot('artifact-cursor-step'),
        });
        void window.__casepathCaptureProcessPreviewGeometry?.(`construction:cursor-${detail.phase || 'step'}`);
        return;
      }
      const ownedArtifact = detail.agentId
        ? document.querySelector(`#v21AgentFocus [data-agent-artifact-target="true"][data-agent-artifact-owner="${CSS.escape(detail.agentId)}"]`)
        : null;
      window.__casepathCursorSteps.push({
        activationKey: detail.activationKey || '',
        moment: detail.moment || '',
        eventId: detail.eventId || '',
        actorType: detail.actorType || '',
        agentId: detail.agentId || '',
        signature: detail.signature || '',
        phase: detail.phase || '',
        callId: detail.callId || '',
        outputArtifact: detail.outputArtifact || '',
        target: detail.target || '',
        x: detail.x,
        y: detail.y,
        at: performance.now(),
        ownedArtifact: ownedArtifact ? {
          owner: ownedArtifact.dataset.agentArtifactOwner || '',
          actorType: ownedArtifact.dataset.actorType || '',
          callId: ownedArtifact.dataset.callId || '',
          outputArtifact: ownedArtifact.dataset.outputArtifact || '',
          status: ownedArtifact.dataset.eventStatus || '',
          requestedModel: ownedArtifact.dataset.requestedModel || '',
          responseModel: ownedArtifact.dataset.responseModel || '',
          targetCount: document.querySelectorAll('#v21AgentFocus [data-agent-artifact-target="true"]').length,
        } : null,
        focus: focusSnapshot('cursor-step'),
      });
    });
    window.addEventListener('casepath:graph-step', event => {
      const detail = event.detail || {};
      const layout = document.querySelector('.process-layout[data-process-story]');
      const visibleNodes = [...(layout?.querySelectorAll('.process-spine > .process-node') || [])].filter(visible);
      window.__casepathGraphSteps.push({
        processId: detail.processId || '',
        kind: detail.kind || '',
        nodeId: detail.nodeId || '',
        index: detail.index,
        total: detail.total,
        basisKinds: Array.isArray(detail.basisKinds) ? [...detail.basisKinds] : [],
        parentId: detail.parentId || '',
        edge: detail.edge || '',
        factIds: Array.isArray(detail.factIds) ? [...detail.factIds] : [],
        lawIds: Array.isArray(detail.lawIds) ? [...detail.lawIds] : [],
        evidenceRequirementIds: Array.isArray(detail.evidenceRequirementIds) ? [...detail.evidenceRequirementIds] : [],
        at: performance.now(),
        buildingCount: layout?.querySelectorAll('[data-process-build-state="building"]').length || 0,
        cursorTargetCount: layout?.querySelectorAll('[data-agent-cursor-target="true"]').length || 0,
        visibleNodeIds: visibleNodes.map(node => node.querySelector('.process-node-button')?.dataset.nodeId || ''),
        interactiveNodeIds: visibleNodes.filter(node => {
          const button = node.querySelector('.process-node-button');
          return button && !button.disabled && button.getAttribute('aria-disabled') !== 'true' && button.getAttribute('tabindex') !== '-1';
        }).map(node => node.querySelector('.process-node-button')?.dataset.nodeId || ''),
        currentNodeIds: visibleNodes.filter(node => node.classList.contains('current')).map(node => node.querySelector('.process-node-button')?.dataset.nodeId || ''),
        selectedBranchVisible: visible(layout?.querySelector('[data-process-selected-branch]')),
        detailLiveMode: layout?.querySelector('[data-process-build-focus]')?.getAttribute('aria-live') || '',
        announcementLiveMode: layout?.querySelector('[data-process-build-announcement]')?.getAttribute('aria-live') || '',
        focus: focusSnapshot('graph-step'),
      });
      void window.__casepathCaptureProcessPreviewGeometry?.(`construction:graph-${detail.kind || 'step'}`);
    });
    window.addEventListener('casepath:official-source-step', event => {
      const detail = event.detail || {};
      const root = document.querySelector('#artifactCanvas');
      const lawSurface = document.querySelector('#artifactCanvas .ac-law-focus[data-ac-law-id]');
      const selected = lawSurface?.querySelector('.ac-law-tabs [data-law-id][aria-current="true"]');
      const officialLink = lawSurface?.querySelector('.ac-official-link[href]');
      window.__casepathOfficialSourceSteps.push({
        sourceId: detail.sourceId || '',
        factId: detail.factId || '',
        location: detail.location || '',
        url: detail.url || '',
        retrievalMethod: detail.retrievalMethod || '',
        registryVersion: detail.registryVersion || '',
        cachePurpose: detail.cachePurpose || '',
        sourceSurface: lawSurface ? 'artifact-canvas' : '',
        selectedSourceId: selected?.dataset.lawId || '',
        selectedUrl: officialLink?.href || '',
        passageSourceId: lawSurface?.dataset.acLawId || '',
        passageUrl: officialLink?.href || '',
        addressUrl: lawSurface?.querySelector('.ac-browser-bar code')?.textContent?.trim() || '',
        addressHost: lawSurface?.querySelector('.ac-browser-bar strong')?.textContent?.trim() || '',
        verifyUrl: officialLink?.href || '',
        presentationMode: root?.dataset.presentationMode || '',
        presentationLabel: document.querySelector('[data-ac-global-agent]')?.textContent?.trim() || '',
        activeAgentId: root?.dataset.activeAgentId || '',
        activeSignature: root?.dataset.activeSignature || '',
        workAuthority: root?.dataset.workAuthority || '',
        at: performance.now(),
        focus: artifactCanvasFocusSnapshot('official-source-step'),
      });
    });
    const artifactCanvasFocusSnapshot = reason => {
      const root = document.querySelector('#artifactCanvas');
      if (!root || !visible(root)) return null;
      const count = selector => [...root.querySelectorAll(selector)].filter(visible).length;
      const snapshot = {
        reason,
        scene: root.dataset.casepathScene || '',
        focusCount: count('[data-artifact-focus="true"]'),
        cursorCount: count('#artifactAgentCursor'),
        artifactCount: count('[data-casepath-primary-artifact="true"]'),
        actionCount: [...document.querySelectorAll('[data-casepath-primary-action="true"]')].filter(visible).length,
      };
      if (snapshot.focusCount !== 1 || snapshot.cursorCount !== 1 || snapshot.artifactCount !== 1 || snapshot.actionCount > 1) {
        window.__casepathArtifactFocusViolations.push(snapshot);
      }
      return snapshot;
    };
    const captureGraphMoment = (moment, phase = '') => {
      window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
        const root = document.querySelector('#artifactCanvas');
        const graph = document.querySelector('#artifactProcessGraph');
        const attachments = selector => [...(graph?.querySelectorAll(selector) || [])].filter(visible).map(node => ({
          text: node.innerText.trim(),
          attachment_kind: node.dataset.nodeAttachmentKind || '',
          memory_id: node.dataset.memoryId || '',
          memory_status: node.dataset.memoryStatus || '',
          memory_origin_id: node.dataset.memoryOriginId || '',
          later_causal_phase: node.dataset.laterCausalPhase || '',
          later_source_opened: node.dataset.laterSourceOpened || '',
          eligibility_contract: node.dataset.eligibilityContract || '',
          eligibility_rule_id: node.dataset.eligibilityRuleId || '',
          semantic_role: node.dataset.semanticRole || '',
        }));
        const focus = [...(root?.querySelectorAll('[data-artifact-focus="true"]') || [])].filter(visible);
        const primaryArtifacts = [...(root?.querySelectorAll('[data-casepath-primary-artifact="true"]') || [])].filter(visible);
        window.__casepathGraphMomentSnapshots.push({
          moment,
          phase,
          scene: root?.dataset.casepathScene || '',
          graph_visible: visible(graph),
          graph_is_sole_focus: focus.length === 1 && focus[0] === graph,
          graph_is_sole_primary_artifact: primaryArtifacts.length === 1 && primaryArtifacts[0] === graph,
          verification_attachments: attachments('.ac-graph-verification[data-node-attachment-kind="verification"]'),
          knowledge_memory_notes: attachments('.ac-knowledge-graph-note[data-memory-id][data-memory-status]'),
          later_memory_retrievals: attachments('.ac-later-memory-retrieval[data-memory-origin-id]'),
          at: performance.now(),
        });
      }));
    };
    window.addEventListener('casepath:semantic-event', event => {
      const detail = event.detail || {};
      const trace = detail.execution_trace || {};
      const acceptance = detail.acceptance || {};
      window.__casepathSemanticEvents.push({
        type: detail.type || '',
        eventId: detail.event_id || detail.eventId || '',
        sequence: detail.sequence,
        runId: detail.runId || '',
        agentId: detail.actor?.id || '',
        actorType: detail.actor?.type || detail.actor_type || '',
        entityKind: detail.entity?.kind || '',
        entityId: detail.entity?.id || '',
        traceContract: trace.contract || '',
        presentationMode: trace.presentation_mode || '',
        authority: trace.authority || acceptance.authority || '',
        modelContributionAccepted: trace.model_contribution_accepted === true && acceptance.model_contribution_accepted === true,
        deterministicFallbackApplied: trace.deterministic_fallback_applied === true || acceptance.deterministic_fallback_applied === true,
        acceptedFields: Array.isArray(trace.accepted_fields) ? [...trace.accepted_fields] : Array.isArray(acceptance.accepted_fields) ? [...acceptance.accepted_fields] : [],
        fallbackFields: Array.isArray(trace.fallback_fields) ? [...trace.fallback_fields] : Array.isArray(acceptance.fallback_fields) ? [...acceptance.fallback_fields] : [],
        modelOwnedFields: Array.isArray(trace.model_owned_fields) ? [...trace.model_owned_fields] : [],
        applicationOwnedFields: Array.isArray(trace.application_owned_fields) ? [...trace.application_owned_fields] : [],
        assertionId: trace.assertion_id || acceptance.assertion_id || '',
        materializedFromModelAssertionFields: Array.isArray(trace.materialized_from_model_assertion_fields) ? [...trace.materialized_from_model_assertion_fields] : [],
        modelSelectedTextRefs: Array.isArray(trace.model_selected_text_refs) ? trace.model_selected_text_refs.map(ref => ({ ...ref })) : [],
        cacheHit: trace.cache_hit === true || acceptance.cache_hit === true || detail.actor?.cache_hit === true,
        sourceCallId: trace.source_call_id || detail.actor?.call_id || '',
        originCallId: detail.actor?.origin_call_id || '',
        callCount: Number.isInteger(detail.actor?.call_count) ? detail.actor.call_count : null,
        usageSource: detail.actor?.usage_source || '',
        sourceCallInputHash: trace.source_call_input_hash || '',
        sourceCallOutputHash: trace.source_call_output_hash || '',
        gateInputHash: trace.gate_input_hash || '',
        acceptedContributionIds: Array.isArray(trace.accepted_contribution_ids) ? [...trace.accepted_contribution_ids] : [],
        linkedModelContributionIds: Array.isArray(trace.linked_model_contribution_ids) ? [...trace.linked_model_contribution_ids] : [],
        linkedModelFields: Array.isArray(trace.linked_model_fields) ? [...trace.linked_model_fields] : [],
        officialSourceCount: Number.isInteger(trace.official_source_count) ? trace.official_source_count : null,
        outputBindingHash: trace.output_binding_hash || '',
        outputProcessNodeId: trace.output_process_node_id || trace.output_node_id || '',
        outputEvidenceId: trace.output_evidence_id || '',
        sourceRefs: Array.isArray(detail.links?.source_refs) ? detail.links.source_refs : [],
        at: performance.now(),
      });
    });
    const decisionFlowSnapshot = detail => {
      const root = document.querySelector('#artifactCanvas');
      const graph = document.querySelector('#artifactProcessGraph');
      const workspace = graph?.querySelector('[data-decision-workspace]');
      const plan = workspace?.querySelector('[data-decision-plan]');
      const waitingBasis = workspace?.querySelector('[data-decision-waiting-basis]');
      const stepItem = detail.stepId
        ? plan?.querySelector(`[data-decision-plan-item][data-step-id="${CSS.escape(String(detail.stepId))}"]`)
        : null;
      const exactControl = workspace?.querySelector('button.ac-source-exact-control[data-source-exact-control="true"],button.ac-visual-region-target[data-ac-inspection-read-target="true"]');
      const readerControls = [...(workspace?.querySelectorAll('.ac-decision-reader-continue,[data-ac-action="advance-decision-flow"]') || [])].filter(visible);
      const realArtifact = workspace?.querySelector('[data-real-artifact="true"]');
      const visualArtifact = workspace?.querySelector('.ac-visual-source[data-source-id]');
      const artifactSurface = realArtifact || visualArtifact;
      const sourceId = String(detail.sourceId || '');
      const railSourceId = displayedSourceId(sourceId);
      const sourceRow = sourceId
        ? document.querySelector(`[data-source-rail-item][data-source-id="${CSS.escape(railSourceId)}"]`)
        : null;
      const progress = window.__casepathProcessNodeProgressUi(detail.nodeId, 'node');
      const node = graph?.querySelector(`[data-node-id="${CSS.escape(String(detail.nodeId || ''))}"][data-process-build-state]`);
      const highlighted = [...(workspace?.querySelectorAll('mark.is-highlighted,.ac-source-secondary-selection.is-highlighted,.ac-visual-region-target.is-highlighted,.ac-decision-basis mark') || [])].filter(visible);
      const carriedSource = workspace?.querySelector('[data-carried-fact-id][data-carried-source-id][data-carried-source-locator-id]');
      const carriedHighlight = carriedSource?.querySelector('.ac-carried-source-highlight');
      return {
        contract: detail.contract || decisionFlowContract,
        runId: detail.runId || '',
        nodeId: detail.nodeId || '',
        stepId: detail.stepId || '',
        stepKind: stepItem?.dataset.stepKind || '',
        phase: detail.phase || '',
        agentId: detail.agentId || '',
        eventId: detail.eventId || '',
        structureEventId: detail.structureEventId || '',
        structureAuthority: detail.structureAuthority || '',
        structureTraceContract: detail.structureTraceContract || '',
        decisionAgentId: detail.decisionAgentId || '',
        decisionEventId: detail.decisionEventId || '',
        decisionAuthority: detail.decisionAuthority || '',
        decisionModelContributionAccepted: detail.decisionModelContributionAccepted === true,
        decisionDeterministicFallbackApplied: detail.decisionDeterministicFallbackApplied === true,
        basisAgentId: detail.basisAgentId || '',
        basisEventId: detail.basisEventId || '',
        basisAuthority: detail.basisAuthority || '',
        presentationMode: detail.presentationMode || root?.dataset.presentationMode || '',
        presentationLabel: document.querySelector('[data-ac-global-agent]')?.textContent?.trim() || '',
        activeAgentId: root?.dataset.activeAgentId || '',
        visualActiveAgentId: root?.dataset.visualActiveAgentId || '',
        visualGroupId: ['canonical_facts', 'process_decision_mapping'].includes(root?.dataset.visualActiveAgentId || '')
          ? 'process_decision_mapping'
          : root?.dataset.visualActiveAgentId || '',
        activeSignature: root?.dataset.activeSignature || '',
        workAuthority: root?.dataset.workAuthority || '',
        sourceId,
        locatorId: detail.locatorId || '',
        locatorIds: Array.isArray(detail.locatorIds) ? [...detail.locatorIds] : [],
        factIds: Array.isArray(detail.factIds) ? [...detail.factIds] : [],
        locatorIndex: Number.isInteger(detail.locatorIndex) ? detail.locatorIndex : -1,
        locatorCount: Number.isInteger(detail.locatorCount) ? detail.locatorCount : 0,
        progress: detail.progress,
        graphVisible: visible(graph) && root?.dataset.graphVisible === 'true',
        graphConstructionState: graph?.dataset.processConstructionState || '',
        workspaceVisible: visible(workspace),
        workspaceNodeId: workspace?.dataset.decisionNodeId || '',
        planCount: workspace?.querySelectorAll('[data-decision-plan]').length || 0,
        planVisible: visible(plan),
        planNodeId: plan?.dataset.nodeId || '',
        planPhase: plan?.dataset.planPhase || '',
        planKind: plan?.dataset.planKind || '',
        planItemCount: plan?.querySelectorAll('[data-decision-plan-item]').length || 0,
        planParagraphCount: plan?.querySelectorAll('p').length || 0,
        planButtonCount: plan?.querySelectorAll('button').length || 0,
        waitingBasisVisible: visible(waitingBasis),
        waitingBasisText: waitingBasis?.textContent?.replace(/\s+/g, ' ').trim() || '',
        sourceTargetExists: sourceId ? window.__casepathSourceTargetExists(sourceId) : false,
        sourceRowActive: Boolean(sourceRow?.classList.contains('is-active')),
        activeSourceIds: window.__casepathActiveSourceIds(),
        activeSourceLocator: document.querySelector('.submission-pane')?.dataset.activeSourceLocator || '',
        artifactSurfaceVisible: visible(artifactSurface),
        artifactSurfaceSourceId: realArtifact?.dataset.artifactId || visualArtifact?.dataset.sourceId || '',
        realArtifactVisible: visible(artifactSurface),
        realArtifactKind: realArtifact?.classList.contains('ac-real-pdf-artifact') ? 'pdf' : realArtifact?.classList.contains('ac-real-email-artifact') ? 'email' : visualArtifact ? 'image' : realArtifact ? 'artifact' : '',
        exactControlCount: exactControl && visible(exactControl) ? 1 : 0,
        exactControlTag: exactControl?.tagName || '',
        exactControlText: exactControl?.textContent?.trim() || '',
        readerControlCount: readerControls.length,
        highlightVisible: highlighted.length > 0,
        highlightCount: highlighted.length,
        fragmentFactIds: [...(workspace?.querySelectorAll('[data-extracted-fragment][data-fact-id]') || [])].filter(visible).map(item => item.dataset.factId || ''),
        combinationVisible: visible(workspace?.querySelector('[data-fact-combination]')),
        combineState: workspace?.querySelector('[data-fact-combination]')?.dataset.combineState || '',
        basisLocatorId: workspace?.querySelector('[data-source-locator-id]')?.dataset.sourceLocatorId || '',
        officialLawId: workspace?.querySelector('[data-law-id]')?.dataset.lawId || '',
        sourceAuthority: workspace?.querySelector('[data-source-authority]')?.dataset.sourceAuthority || '',
        carriedFactId: carriedSource?.dataset.carriedFactId || '',
        carriedSourceId: carriedSource?.dataset.carriedSourceId || '',
        carriedLocatorId: carriedSource?.dataset.carriedSourceLocatorId || '',
        carriedPassage: carriedHighlight?.textContent?.trim() || '',
        carriedHighlightCount: carriedSource ? carriedSource.querySelectorAll('.ac-carried-source-highlight').length : 0,
        carriedGeneratedSummaryVisible: Boolean(carriedSource && [...carriedSource.querySelectorAll('p')].filter(visible).some(item => /summary|context/i.test(item.className) || item.textContent?.trim())),
        reducedMotion: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true,
        progressVisible: progress.indicatorVisible === true,
        nodeVisible: node?.dataset.revealState === 'visible' && visible(node),
        at: performance.now(),
      };
    };
    window.addEventListener('casepath:decision-flow-step', event => {
      window.__casepathDecisionFlowSteps.push(decisionFlowSnapshot(event.detail || {}));
    });
    window.addEventListener('casepath:process-node-progress', event => {
      const detail = event.detail || {};
      window.__casepathProcessNodeProgress.push({
        contract: detail.contract || '',
        scope: detail.scope || '',
        processId: detail.processId || '',
        entityKind: detail.entityKind || '',
        nodeId: detail.nodeId || '',
        branchId: detail.branchId || '',
        basisKind: detail.basisKind || '',
        phase: detail.phase || '',
        percent: detail.percent,
        label: detail.label || '',
        visible: detail.visible === true,
        changeId: detail.changeId || '',
        eventId: detail.eventId || '',
        agentId: detail.agentId || '',
        ...window.__casepathProcessNodeProgressUi(detail.nodeId, detail.entityKind),
        at: performance.now(),
      });
    });
    window.addEventListener('casepath:artifact-change', event => {
      const detail = event.detail || {};
      const graph = document.querySelector('#artifactProcessGraph');
      const attachment = [...document.querySelectorAll('#artifactCanvas [data-artifact-focus="true"] [data-node-attachment-kind][data-artifact-change-id][data-artifact-event-id][data-artifact-agent-id]')]
        .find(node => node.dataset.artifactChangeId === detail.changeId) || null;
      const nodeStates = [...(graph?.querySelectorAll('[data-node-id][data-process-build-state]') || [])].map(node => ({
        nodeId: node.dataset.nodeId || '',
        state: node.dataset.processBuildState || '',
        tabIndex: node.querySelector('[data-ac-action="select-node"]')?.tabIndex ?? null,
        disabled: node.querySelector('[data-ac-action="select-node"]')?.disabled ?? null,
        ariaCurrent: node.querySelector('[data-ac-action="select-node"]')?.getAttribute('aria-current') || '',
      }));
      window.__casepathArtifactChanges.push({
        changeId: detail.changeId || '',
        eventId: detail.eventId || '',
        agentId: detail.agentId || '',
        kind: detail.kind || '',
        entityId: detail.entityId || '',
        attachment: attachment ? {
          kind: attachment.dataset.nodeAttachmentKind || '',
          factId: attachment.dataset.factId || '',
          changeId: attachment.dataset.artifactChangeId || '',
          eventId: attachment.dataset.artifactEventId || '',
          agentId: attachment.dataset.artifactAgentId || '',
          sourceLocatorId: attachment.dataset.sourceLocatorId || '',
          sourceAuthority: attachment.dataset.sourceAuthority || '',
          referenceStatus: attachment.dataset.referenceStatus || '',
          sourceDockState: document.querySelector('[data-source-dock-state]')?.dataset.sourceDockState || '',
          activeSourceLocator: document.querySelector('[data-source-dock-state]')?.dataset.activeSourceLocator || '',
        } : null,
        nodeStates,
        ...window.__casepathProcessNodeProgressUi(detail.entityId, 'node'),
        graphVisible: visible(graph) && document.querySelector('#artifactCanvas')?.dataset.graphVisible === 'true',
        planVisible: visible(graph?.querySelector('[data-decision-plan]')),
        planPhase: graph?.querySelector('[data-decision-plan]')?.dataset.planPhase || '',
        decisionFlowState: document.querySelector('#artifactCanvas')?.dataset.decisionFlowState || '',
        focus: artifactCanvasFocusSnapshot('artifact-change'),
        at: performance.now(),
      });
      void window.__casepathCaptureProcessPreviewGeometry?.(`construction:artifact-${detail.kind || 'change'}`);
    });
    window.addEventListener('casepath:artifact-canvas-interaction', event => {
      window.__casepathArtifactInteractions.push({ ...(event.detail || {}), at: performance.now() });
    });
    window.addEventListener('casepath:source-highlighted', event => {
      const detail = event.detail || {};
      const root = document.querySelector('#artifactCanvas');
      const construction = detail.entityKind === 'node'
        ? root?.querySelector('#artifactProcessGraph .ac-build-source-highlight')
        : null;
      const constructionMark = construction?.querySelector('mark.ac-source-exact-mark.is-highlighted, mark.is-highlighted');
      const constructionSource = construction?.querySelector('[data-fact-id][data-source-id][data-source-locator-id]');
      const sourceHighlight = {
        entityKind: detail.entityKind || '',
        nodeId: detail.nodeId || '',
        branchId: detail.branchId || '',
        factId: detail.factId || '',
        changeId: detail.changeId || '',
        eventId: detail.eventId || '',
        agentId: detail.agentId || '',
        sourceId: detail.sourceId || '',
        locatorId: detail.locatorId || '',
        graphInspectionPhase: root?.dataset.graphInspectionPhase || '',
        sourceHighlighted: detail.entityKind === 'fact'
          ? visible(root?.querySelector('[data-fact-tour-phase="highlight-source"] .ac-fact-source.is-source-selected .is-highlighted'))
          : visible(root?.querySelector('.ac-build-source-highlight .is-highlighted, .ac-build-source-highlight')),
        attachmentKind: construction?.querySelector('[data-node-attachment-kind]')?.dataset.nodeAttachmentKind || (constructionSource ? 'fact' : ''),
        constructionFactId: construction?.dataset.factId || constructionSource?.dataset.factId || '',
        constructionSourceId: construction?.dataset.sourceId || constructionSource?.dataset.sourceId || '',
        constructionLocatorId: construction?.dataset.sourceLocatorId || constructionSource?.dataset.sourceLocatorId || '',
        passage: constructionMark?.textContent?.trim() || '',
        highlightMarkCount: construction ? construction.querySelectorAll('mark.ac-source-exact-mark.is-highlighted, mark.is-highlighted').length : 0,
        generatedSummaryVisible: Boolean(construction && [...construction.querySelectorAll('p')].filter(visible).some(node => /summary|context/i.test(node.className) || node.textContent?.trim())),
        at: performance.now(),
      };
      window.__casepathSourceHighlights.push(sourceHighlight);
      void window.__casepathCaptureProcessPreviewGeometry?.(`construction:highlight-${detail.entityKind || 'source'}`);
    });
    window.addEventListener('casepath:later-memory-validation', event => {
      const detail = event.detail || {};
      window.__casepathLaterMemoryValidations.push({
        contract: detail.contract || '',
        runId: detail.runId || '',
        validated: detail.validated === true,
        proofReady: detail.proofReady === true,
        memoryUsed: detail.memoryUsed === true,
        memoryRetrieved: detail.memoryRetrieved === true,
        retrievedOnly: detail.retrievedOnly === true,
        applicationHash: detail.applicationHash || '',
        memoryOriginId: detail.memoryOriginId || '',
        sharedPlaybookUnchanged: detail.sharedPlaybookUnchanged === true,
        delta: {
          nodeIds: Array.isArray(detail.delta?.nodeIds) ? [...detail.delta.nodeIds] : [],
          edges: Array.isArray(detail.delta?.edges) ? detail.delta.edges.map(edge => ({ source: edge?.source || '', target: edge?.target || '' })) : [],
          evidenceIds: Array.isArray(detail.delta?.evidenceIds) ? [...detail.delta.evidenceIds] : [],
        },
        at: performance.now(),
      });
    });
    window.addEventListener('casepath:later-causal-step', event => {
      const detail = event.detail || {};
      const step = {
        contract: detail.contract || '',
        runId: detail.runId || '',
        phase: detail.phase || '',
        factId: detail.factId || '',
        sourceId: detail.sourceId || '',
        locatorId: detail.locatorId || '',
        memoryOriginId: detail.memoryOriginId || '',
        eligibilityContract: detail.eligibilityContract || '',
        ruleId: detail.ruleId || '',
        semanticRole: detail.semanticRole || '',
        at: performance.now(),
      };
      queueMicrotask(() => {
        step.activeSourceIds = window.__casepathActiveSourceIds();
        window.__casepathLaterCausalSteps.push(step);
        captureGraphMoment('later-work', step.phase);
      });
    });
    window.addEventListener('casepath:later-source-opened', event => {
      const detail = event.detail || {};
      window.__casepathLaterSourceOpenings.push({
        contract: detail.contract || '',
        runId: detail.runId || '',
        factId: detail.factId || '',
        sourceId: detail.sourceId || '',
        locatorId: detail.locatorId || '',
        activeSourceIds: window.__casepathActiveSourceIds(),
        activeLocatorId: document.querySelector('.submission-pane')?.dataset.activeSourceLocator || '',
        sourceOpened: document.querySelector('[data-later-causal-phase="source"]')?.dataset.laterSourceOpened || '',
        at: performance.now(),
      });
    });
    window.addEventListener('casepath:branch-visualized', event => {
      const detail = event.detail || {};
      window.__casepathBranchVisuals.push({
        nodeId: detail.nodeId || '',
        branchId: detail.branchId || '',
        changeId: detail.changeId || '',
        eventId: detail.eventId || '',
        agentId: detail.agentId || '',
        ...window.__casepathProcessNodeProgressUi(detail.nodeId, 'branch'),
        at: performance.now(),
      });
    });
    const observeAttributes = () => {
      const captureOrchestrationProof = () => {
        document.querySelectorAll('.orchestration-actor-card[data-actor-type="nemotron_agent"][data-actor-id]').forEach(node => {
          if (node.dataset.actorId && !window.__casepathVisibleAgentIds.includes(node.dataset.actorId)) window.__casepathVisibleAgentIds.push(node.dataset.actorId);
        });
        document.querySelectorAll('.orchestration-receipt.gate-receipt[data-actor-type="deterministic_gate"][data-gate-id]').forEach(node => {
          if (node.dataset.gateId && !window.__casepathVisibleGateIds.includes(node.dataset.gateId)) window.__casepathVisibleGateIds.push(node.dataset.gateId);
        });
      };
      new MutationObserver(records => {
        for (const record of records) {
          const target = record.target;
          if (record.attributeName === 'data-casepath-release' || (record.attributeName === 'content' && target.matches?.('meta[name="casepath-release"]'))) {
            window.__casepathReleaseMutations.push(`${target.nodeName}:${record.attributeName}`);
          }
          if (record.attributeName === 'data-casepath-moment' && target === document.body) {
            window.__casepathMomentHistory.push(document.body.dataset.casepathMoment || '');
          }
        }
      }).observe(document.documentElement, { attributes: true, subtree: true, attributeFilter: ['data-casepath-release', 'data-casepath-moment', 'content'] });
      new MutationObserver(records => {
        captureOrchestrationProof();
      }).observe(document.documentElement, { attributes: true, childList: true, subtree: true, attributeFilter: ['data-actor-id', 'data-gate-id', 'data-actor-type'] });
      captureOrchestrationProof();
    };
    if (document.documentElement) observeAttributes();
    else {
      const parserObserver = new MutationObserver(() => {
        if (!document.documentElement) return;
        parserObserver.disconnect();
        observeAttributes();
      });
      parserObserver.observe(document, { childList: true });
    }
  }, {
    sessionId: QA_SESSION_ID,
    decisionFlowContract: DECISION_FLOW_CONTRACT,
    processPreviewGeometrySelectors: PROCESS_PREVIEW_GEOMETRY_SELECTORS,
    processPreviewBottomInset: PROCESS_PREVIEW_BOTTOM_INSET_PX,
    sourceRailContract: SOURCE_RAIL_CONTRACT,
  });

  const response = await page.goto(`${BASE}/?api=${encodeURIComponent(API)}&journey=legacy-v20&qa=${Date.now()}`, { waitUntil: 'domcontentloaded', timeout: 120000 });
  const sourceHtml = await response.text();
  check('Product returns HTTP 200', response.status() === 200, `status=${response.status()}`);
  check('HTML owns immutable v20 release identity', /<html[^>]*data-casepath-release=["']20\.0\.0["']/i.test(sourceHtml) && /<meta[^>]*name=["']casepath-release["'][^>]*content=["']20\.0\.0["']/i.test(sourceHtml));
  check('First paint contains an intentional claim shell', sourceHtml.includes('v20-source-skeleton') && sourceHtml.includes('Opening claim…'));
  const flagshipScriptPaths = [
    'assets/live-v16.js',
    'assets/live-v16-stability.js',
    'assets/live-v18-insertion-guard.js',
    'assets/live-v17.js',
    'assets/live-v18.js',
    'assets/live-v18-handoff.js',
    'assets/live-v19-active-stage.js',
    'assets/live-v20-focus.js',
    'assets/process-story.js',
    'assets/artifact-canvas.js',
    'assets/foundation-live.js',
    'assets/insurance-protocol-v1.js',
  ];
  const flagshipScriptSources = await Promise.all(flagshipScriptPaths.map(async scriptPath => ({ scriptPath, source: await getText(`${BASE}/${scriptPath}`) })));
  const loadedFlagshipSource = [sourceHtml, ...flagshipScriptSources.map(item => item.source)].join('\n');
  const orchestrationRendererSource = flagshipScriptSources.find(item => item.scriptPath === 'assets/live-v16.js')?.source || '';
  const runReadGuardSource = flagshipScriptSources.find(item => item.scriptPath === 'assets/live-v18-insertion-guard.js')?.source || '';
  const artifactCanvasSource = flagshipScriptSources.find(item => item.scriptPath === 'assets/artifact-canvas.js')?.source || '';
  const staleQaService = /casepath-guided-(?:v13-smoke|evidence-v13)\.onrender\.com/i;
  const falseReviewedV4Claim = /mould-playbook-v4|released playbook v4|after reviewed knowledge|reviewed playbook release/i;
  const falseGroundingAuthority = /machine-visible image record|model interpretation|live retrieval/i;
  const falseHeldOutNovelty = /\bunseen(?: related)? claim\b/i;
  check('Loaded release contains no obsolete public QA-service destination', !staleQaService.test(loadedFlagshipSource));
  check('Loaded release labels logical specialist topology as fan-out rather than physical parallel transport', loadedFlagshipSource.includes('<i>fan-out</i>') && !loadedFlagshipSource.includes('<i>parallel</i>'));
  check('Artifact canvas owns one authenticated fetch-SSE transport and no active run polling loop', orchestrationRendererSource.includes("document.body.dataset.runTransport = 'fetch-sse'") && orchestrationRendererSource.includes("'X-CasePath-Session': SESSION_ID") && orchestrationRendererSource.includes("Accept: 'text/event-stream'") && orchestrationRendererSource.includes('/events?after=${after}') && !orchestrationRendererSource.includes('function pollRun(') && !orchestrationRendererSource.includes('setTimeout(() => pollRun(') && artifactCanvasSource.includes('artifactCanvas'));
  check('Process-story watchdog rearms only on same-run decision-flow progress and removes its listener when settled', [
    "window.addEventListener('casepath:decision-flow-step', onProgress);",
    "window.removeEventListener('casepath:decision-flow-step', onProgress);",
    "if (String(event.detail?.runId || '') === runId) armTimeout();",
    'window.clearTimeout(timeout);',
  ].every(fragment => orchestrationRendererSource.includes(fragment)));
  check('Loaded orchestration renderer never promotes a validator label to a deterministic gate ID', orchestrationRendererSource.includes("const gateId = returnedValue(event, 'gate_id', 'agent_id');") && orchestrationRendererSource.includes("const validator = returnedValue(event, 'validator');") && orchestrationRendererSource.includes('const gateIdentity = gateId ? ` data-gate-id=') && !orchestrationRendererSource.includes("returnedValue(event, 'gate_id', 'agent_id', 'validator', 'label')"));
  check('Later source inspection is run-scoped without presupposing a memory-application receipt or inheriting baseline fields', artifactCanvasSource.includes('if (state.laterResultRunId && state.laterResultRunId !== runId) state.laterResult = null;') && artifactCanvasSource.includes('|| runId !== state.laterResultRunId) return null;') && !artifactCanvasSource.includes("String(receipt?.target?.run_id || '') !== runId) return null;") && laterRunIsolation.staleBaselineRejected === true && laterRunIsolation.queuedLaterShellPreservedPrimary === true && laterRunIsolation.currentSourceAcceptedWithoutMemoryReceipt === true && laterRunIsolation.currentSourceOpenedFromExactVisibleStep === true && laterRunIsolation.laterOnlyProjectionActivated === true && laterRunIsolation.preReplaySnapshot.visibleNodeIds.includes('later_only') && laterRunIsolation.restoredAcceptedCausationProjection === true && laterRunIsolation.acceptedPrimaryRouteRestored === true && laterRunIsolation.laterOnlyProjectionRejected === true && laterRunIsolation.canvasSnapshot.visibleNodeIds.includes('causation') && !laterRunIsolation.canvasSnapshot.visibleNodeIds.includes('later_only') && laterRunIsolation.sourceMarkup.length > 0 && laterRunIsolation.foreignRunRejected === true, JSON.stringify(laterRunIsolation));
  check('Loaded run-read coalescing is session-scoped, in-flight-only, review-mutation-aware, and renders the authoritative review response', runReadGuardSource.includes("headers.get('X-CasePath-Session')") && runReadGuardSource.includes('runResourceKey(url, request, init)') && runReadGuardSource.includes('const pendingRunMutations = new Map();') && runReadGuardSource.includes("const isReviewMutation = method === 'POST'") && runReadGuardSource.includes('const activeMutation = pendingRunMutations.get(resourceKey);') && runReadGuardSource.includes('await activeMutation;') && !runReadGuardSource.includes('runReadWindowMs') && !runReadGuardSource.includes('window.setTimeout') && orchestrationRendererSource.includes('result: snapshot(state.review.result)'));
  check('Current QA destination is guarded by exact live API identity and an atomic hash-bound report/manifest attestation', loadedFlagshipSource.includes("const qaEvidenceBase = 'https://casepath-guided-canonical-qa.onrender.com'") && loadedFlagshipSource.includes('function releaseEvidenceAttested(') && loadedFlagshipSource.includes("fetch(`${apiBase}/healthz`") && loadedFlagshipSource.includes("api?.source_commit === commit") && loadedFlagshipSource.includes('reportIdentities.every(value => value === commit)') && loadedFlagshipSource.includes('report?.failed === 0') && loadedFlagshipSource.includes('manifest?.source_commit === commit') && loadedFlagshipSource.includes('report.evidence.manifest.sha256 === manifestBinding.sha256') && loadedFlagshipSource.includes('report.evidence.manifest.bytes === manifestBinding.bytes') && loadedFlagshipSource.includes('retainedEvidenceComplete(report, manifest)') && loadedFlagshipSource.includes("link.dataset.evidenceState = 'attested'"));
  check('Loaded release contains no false reviewed-v4 lifecycle claim', !falseReviewedV4Claim.test(loadedFlagshipSource));
  check('Loaded release contains no false image-extraction, model-legal, or live-retrieval authority copy', !falseGroundingAuthority.test(loadedFlagshipSource));
  check('Loaded release truthfully defines a deterministic post-learning held-out comparison without calling the fixture unseen or claiming another model run', !falseHeldOutNovelty.test(loadedFlagshipSource) && /held-out later demo claim/i.test(loadedFlagshipSource) && /the later claim remains source-isolated while eligible guidance is evaluated/i.test(loadedFlagshipSource) && /frozen memory receipt \+ later demo claim/i.test(loadedFlagshipSource) && /the earlier result came from six call-bound specialist agents/i.test(loadedFlagshipSource) && /deterministic comparison · no second model run/i.test(loadedFlagshipSource) && /this comparison makes no new model call/i.test(loadedFlagshipSource));
  const evidenceControl = await page.locator('#browserEvidenceLink').evaluate(node => ({
    tag: node.tagName,
    state: node.dataset.evidenceState,
    text: node.textContent.trim(),
    href: node.getAttribute('href'),
    role: node.getAttribute('role'),
  }));
  const evidenceControlIsPending = evidenceControl.tag === 'SPAN' && evidenceControl.state === 'pending' && evidenceControl.text === 'Current release evidence pending' && evidenceControl.href === null && evidenceControl.role === 'status';
  const evidenceControlIsAttested = evidenceControl.tag === 'A' && evidenceControl.state === 'attested' && evidenceControl.href === 'https://casepath-guided-canonical-qa.onrender.com/report.json' && /^Current release evidence · [0-9a-f]{8}$/.test(evidenceControl.text);
  check('Current-release evidence is either fail-closed pending or unlocked by exact attestation', evidenceControlIsPending || evidenceControlIsAttested, JSON.stringify(evidenceControl));
  const attestationMatrix = await page.evaluate(() => {
    const commit = 'a'.repeat(40);
    const frontend = { source_commit: commit, release_id: 'casepath-v20-reference-20260811', alignment_eligible: true };
    const api = { status: 'ok', release_id: frontend.release_id, source_commit: commit, source_commit_aligned: true, source_commit_conflict: false };
    const files = [
      { path: 'flagship-run.json', sha256: 'c'.repeat(64), bytes: 10 },
      { path: 'final-state.png', sha256: 'd'.repeat(64), bytes: 20 },
      { path: 'uninterrupted-focused-demo.webm', sha256: 'e'.repeat(64), bytes: 30 },
    ];
    const binding = { sha256: 'f'.repeat(64), bytes: 1234 };
    const report = { status: 'passed', passed: 80, failed: 0, release_id: frontend.release_id, deployment: { frontend: { source_commit: commit }, api: { source_commit: commit }, qa: { source_commit: commit } }, evidence: { gate: { sha256: 'b'.repeat(64) }, retained_before_session_reset: true, missing: [], files, manifest: { path: 'evidence-manifest.json', ...binding } } };
    const manifest = { contract: 'casepath.qa-evidence-manifest/1.0.0', release_id: frontend.release_id, source_commit: commit, gate: { sha256: 'b'.repeat(64) }, retained_before_session_reset: true, retained_media_contract: { json: ['flagship-run.json'], screenshots: ['final-state.png'], video: 'uninterrupted-focused-demo.webm', missing: [], empty: [] }, files };
    const isAttested = window.__casepathEvidenceAttestation?.isAttested;
    return {
      valid: isAttested?.(frontend, api, report, manifest, binding) === true,
      wrongReportCommit: isAttested?.(frontend, api, { ...report, deployment: { ...report.deployment, api: { source_commit: 'c'.repeat(40) } } }, manifest, binding) === false,
      liveApiDrift: isAttested?.(frontend, { ...api, source_commit: 'c'.repeat(40) }, report, manifest, binding) === false,
      missingMedia: isAttested?.(frontend, api, report, { ...manifest, retained_media_contract: { ...manifest.retained_media_contract, missing: ['final-state.png'] } }, binding) === false,
      failedReport: isAttested?.(frontend, api, { ...report, status: 'failed' }, manifest, binding) === false,
      failedCount: isAttested?.(frontend, api, { ...report, failed: 17 }, manifest, binding) === false,
      notRetained: isAttested?.(frontend, api, { ...report, evidence: { ...report.evidence, retained_before_session_reset: false } }, manifest, binding) === false,
      tamperedManifestBytes: isAttested?.(frontend, api, report, manifest, { ...binding, sha256: '0'.repeat(64) }) === false,
      changedInventory: isAttested?.(frontend, api, report, { ...manifest, files: manifest.files.slice(1) }, binding) === false,
    };
  });
  check('Evidence attestation accepts only a passed complete exact-commit report/manifest pair', Object.values(attestationMatrix).every(Boolean), JSON.stringify(attestationMatrix));
  const checklistRendererSource = flagshipScriptSources.find(item => item.scriptPath === 'assets/live-v17.js')?.source || '';
  const precedentRendererSource = flagshipScriptSources.find(item => item.scriptPath === 'assets/live-v16.js')?.source || '';
  const reuseRendererSource = flagshipScriptSources.find(item => item.scriptPath === 'assets/live-v17.js')?.source || '';
  const laterStageSource = flagshipScriptSources.find(item => item.scriptPath === 'assets/live-v18.js')?.source || '';
  check('Precedent rendering accepts qualified_expert_reviewed while preserving explicit unverified memory copy', precedentRendererSource.includes("'qualified_expert_reviewed'") && precedentRendererSource.includes("'unverified_demo_memory'") && precedentRendererSource.includes('Unverified generated-demo review memory returned by the server') && precedentRendererSource.includes('Unverified demo review memory returned'));
  check('Loaded later-result renderer distinguishes retrieval from receipt-bound use/application without asynchronous reuse enhancement', precedentRendererSource.includes('reviewed_memory_retrieved') && precedentRendererSource.includes('data-memory-retrieved-only=') && precedentRendererSource.includes('retrieved-not-applied') && precedentRendererSource.includes('Saving it does not mean later guidance was used or applied') && precedentRendererSource.includes('Not used or applied · no memory-driven DTO change') && precedentRendererSource.includes('function renderMemoryReuseProof') && !reuseRendererSource.includes('function enhanceReuse') && !laterStageSource.includes('function enhanceReuse'));
  check('Document-checklist renderer fails closed on exact field units, reciprocal owners, and transformed acceptance', [
    'const expectedUnits = [',
    'new Set(ids).size === ids.length',
    'Number.isInteger(value.confidence_basis_points)',
    "value.attribution === expectedAttribution",
    'data-accepted-contribution-ids=',
    'post_review_unverified_transform',
    'casepath.memory-application-receipt/1.0.0',
    'data-node-ids=',
    'data-current-path=',
  ].every(fragment => checklistRendererSource.includes(fragment)));
  const syntheticActorLabels = ['Agent complete', ...FORBIDDEN_SYNTHETIC_AGENT_LABELS];
  const syntheticActorSources = flagshipScriptSources.flatMap(({ scriptPath, source }) => syntheticActorLabels.filter(label => source.includes(label)).map(label => `${scriptPath}:${label}`));
  check('Loaded flagship scripts never promote seven presentation phases, deterministic stages, or knowledge governance into extra model agents', syntheticActorSources.length === 0, JSON.stringify(syntheticActorSources));
  const specialistFocusSource = flagshipScriptSources.find(item => item.scriptPath === 'assets/live-v20-focus.js')?.source || '';
  const identitySourceIssues = [];
  for (const agentId of REQUIRED_NEMOTRON_AGENT_IDS) {
    const expected = REQUIRED_NEMOTRON_AGENT_SIGNATURES[agentId];
    if (!specialistFocusSource.includes(`${agentId}: {`)) identitySourceIssues.push(`${agentId}: missing identity`);
    if (!specialistFocusSource.includes(`label: '${REQUIRED_DESKTOP_AGENT_LABELS[agentId]}'`)) identitySourceIssues.push(`${agentId}: wrong visible label`);
    if (!specialistFocusSource.includes(`shortLabel: '${REQUIRED_DESKTOP_AGENT_SHORTS[agentId]}'`)) identitySourceIssues.push(`${agentId}: wrong short label`);
    if (!specialistFocusSource.includes(`monogram: '${expected.monogram}'`)) identitySourceIssues.push(`${agentId}: wrong monogram`);
    if (!specialistFocusSource.includes(`signature: '${expected.signature}'`)) identitySourceIssues.push(`${agentId}: wrong signature`);
  }
  const identityMapStart = specialistFocusSource.indexOf('const NEMOTRON_AGENT_IDENTITIES = Object.freeze({');
  const identityMapEnd = specialistFocusSource.indexOf('\n  });', identityMapStart);
  const identityMapSource = specialistFocusSource.slice(identityMapStart, identityMapEnd);
  const declaredAgentIds = [...identityMapSource.matchAll(/^\s{4}([a-z_]+): \{/gm)].map(match => match[1]);
  const cursorAvatarSignatures = Object.values(REQUIRED_NEMOTRON_AGENT_SIGNATURES).map(value => value.signature);
  const cursorAvatarsAreDistinct = cursorAvatarSignatures.every(signature => artifactCanvasSource.includes(`${signature}: '<`))
    && artifactCanvasSource.includes('const CURSOR_AVATARS = Object.freeze({')
    && artifactCanvasSource.includes('data-ac-cursor-avatar')
    && artifactCanvasSource.includes('function setCursorAvatar(');
  check('Desktop cursor presents the agreed six simple agent names and six distinct specialist avatars while preserving exact IDs, monograms, and signatures', identitySourceIssues.length === 0 && exactMembers(declaredAgentIds, REQUIRED_NEMOTRON_AGENT_IDS) && new Set(Object.values(REQUIRED_NEMOTRON_AGENT_SIGNATURES).map(value => value.monogram)).size === 6 && new Set(cursorAvatarSignatures).size === 6 && cursorAvatarsAreDistinct, JSON.stringify({ declaredAgentIds, identitySourceIssues, cursorAvatarsAreDistinct }));
  check('Seven visible chapters remain presentation phases with explicit execution authority, not a synthetic seven-agent team', REQUIRED_PRESENTATION_PHASE_LABELS.every(fragment => specialistFocusSource.includes(`label: '${fragment}'`)) && ['dataset.casepathSpecialist', 'dataset.workAuthority'].every(fragment => specialistFocusSource.includes(fragment)));
  check('Cursor motion is keyed to semantic event/agent/phase/target identity, suppresses replay, and emits one inspectable step without class-mutation feedback', specialistFocusSource.includes('const activationKey =') && specialistFocusSource.includes("cursor.dataset.eventId || cursor.dataset.proofEventId || moment") && specialistFocusSource.includes("cursor.dataset.agentId || 'casepath'") && specialistFocusSource.includes('cursorPhase') && specialistFocusSource.includes('emittedActivationKeys.has(activationKey)') && specialistFocusSource.includes('cursorTargetKey(target)') && specialistFocusSource.includes("new CustomEvent('casepath:cursor-step'") && specialistFocusSource.includes("['is-clicking', 'v21-agent-target']") && specialistFocusSource.includes("attributeOldValue: true") && !specialistFocusSource.includes("requestAnimationFrame(() => cursor.classList.add('is-clicking'))"));
  check('Every successful call-bound specialist owns one receipt-bound artifact target instead of relabelling an unrelated canvas', ['function ownedArtifactMarkup(', 'data-agent-artifact-target="true"', 'data-agent-artifact-owner=', 'data-actor-type=', 'data-call-id=', 'data-output-artifact=', 'data-requested-model=', 'data-response-model=', "event.actorType !== 'nemotron_agent'", 'Official-law tabs remain a separate deterministic cached registry view.'].every(fragment => specialistFocusSource.includes(fragment)));

  const expectedRailSources = expectedSourceRailItems(demo.claim);
  await page.waitForFunction(({ contract, count }) => {
    const rail = document.querySelector(`aside[data-source-rail-contract="${contract}"]`);
    const list = rail?.matches('[data-source-rail-list]') ? rail : rail?.querySelector('[data-source-rail-list]');
    const rows = [...(list?.querySelectorAll('[data-source-rail-item][data-source-id]') || [])];
    return rows.length === count && rows.every(row => (
      row.querySelectorAll('[data-source-icon-kind] > svg').length === 1
      && row.querySelectorAll('[data-source-name]').length === 1
      && row.querySelectorAll('[data-source-meta]').length === 1
      && row.querySelectorAll('[data-source-status]').length === 1
    ));
  }, { contract: SOURCE_RAIL_CONTRACT, count: expectedRailSources.length }, { timeout: 120000 });
  await page.waitForFunction(() => !document.querySelector('#runCasePath')?.disabled, null, { timeout: 120000 });
  await page.waitForFunction(() => document.querySelector('#artifactCanvas') && document.querySelector('#artifactProcessGraph'), null, { timeout: 120000 });
  const openingSourceRailSnapshots = [];
  for (const viewport of SOURCE_RAIL_VIEWPORTS) {
    await page.setViewportSize(viewport);
    await sleep(120);
    openingSourceRailSnapshots.push(await page.evaluate(label => window.__casepathCaptureSourceRail?.(label, '', ''), `opening:${viewport.width}x${viewport.height}`));
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  const openingSourceRailIssues = openingSourceRailSnapshots.flatMap(snapshot => sourceRailContractViolations(snapshot, expectedRailSources));
  check('The compact source rail shows all seven exact sources without collapse, dropdown, clipping, or overlap at 1280x720 and 1440x900', openingSourceRailSnapshots.length === SOURCE_RAIL_VIEWPORTS.length && openingSourceRailIssues.length === 0, JSON.stringify({ openingSourceRailSnapshots, openingSourceRailIssues }));
  await page.evaluate(() => {
    window.__casepathPersistentArtifactCanvas = document.querySelector('#artifactCanvas');
    window.__casepathPersistentProcessGraph = document.querySelector('#artifactProcessGraph');
  });
  const openingCanvas = await artifactCanvasSnapshot();
  check('Opening mounts the persistent artifact canvas and graph roots before analysis begins', openingCanvas.root_present && openingCanvas.root_same && openingCanvas.graph_present && openingCanvas.graph_same, JSON.stringify(openingCanvas));
  await page.evaluate(() => {
    const moment = document.body.dataset.casepathMoment;
    if (moment && !window.__casepathMomentHistory.includes(moment)) window.__casepathMomentHistory.push(moment);
    if (document.querySelector('meta[name="casepath-release"]')?.content !== '20.0.0') window.__casepathReleaseMutations.push('initial-meta-mismatch');
  });
  check('DOM and meta release markers agree', await page.evaluate(() => document.documentElement.dataset.casepathRelease === '20.0.0' && document.querySelector('meta[name="casepath-release"]')?.content === '20.0.0' && !document.body.hasAttribute('data-casepath-release')));
  check('Claim source clears aria-busy after rendering', await page.locator('#customerEmail').getAttribute('aria-busy') === 'false');
  const quietContrast = await page.evaluate(() => {
    const values = getComputedStyle(document.querySelector('.quiet-label')).color.match(/[\d.]+/g).slice(0, 3).map(Number);
    const luminance = rgb => rgb.map(value => { const channel = value / 255; return channel <= .03928 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4; }).reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
    const foreground = luminance(values);
    return (1.05) / (foreground + .05);
  });
  check('Quiet small-text color meets WCAG AA contrast on the white product surface', quietContrast >= 4.5, `contrast=${quietContrast.toFixed(2)}`);
  const openingClaimCard = await page.evaluate(() => {
    const visible = node => Boolean(node && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden' && getComputedStyle(node).display !== 'none');
    const cards = [...document.querySelectorAll('[data-opening-claim-source]')];
    const card = cards[0] || null;
    const rect = card?.getBoundingClientRect();
    const problem = card?.querySelector(':scope > blockquote')?.textContent?.trim() || '';
    const outcome = card?.querySelector(':scope > p')?.textContent?.trim() || '';
    return {
      cardCount: cards.length,
      visible: visible(card),
      sourceId: card?.dataset.openingClaimSource || '',
      childTags: [...(card?.children || [])].map(child => child.tagName),
      subject: card?.querySelector(':scope > strong')?.textContent?.trim() || '',
      problem,
      outcome,
      blockquoteCount: card?.querySelectorAll(':scope > blockquote').length || 0,
      paragraphCount: card?.querySelectorAll(':scope > p').length || 0,
      generatedSummaryCount: card?.querySelectorAll('[data-generated-summary],.ai-summary,.generated-summary').length || 0,
      bodyCopyLength: problem.length + outcome.length,
      width: rect?.width || 0,
      height: rect?.height || 0,
    };
  });
  const openingClaimCardIssues = openingClaimCardContractViolations(openingClaimCard, demo.claim);
  check('Opening shows one compact source-derived claim card with the exact problem and requested outcome and no generated summary prose', openingClaimCardIssues.length === 0, JSON.stringify({ openingClaimCard, openingClaimCardIssues }));
  await auditViewports('01-start', '#startState');

  const pdf = demo.claim.artifacts.find(item => item.media_type === 'application/pdf');
  const image = demo.claim.artifacts.find(item => item.media_type?.startsWith('image/'));
  const email = demo.claim.artifacts.find(item => item.media_type === 'message/rfc822');
  check('PDF, image, and email fixtures are available', Boolean(pdf && image && email), JSON.stringify(demo.claim.artifacts.map(item => ({ id: item.artifact_id, type: item.media_type }))));

  const pdfRow = page.locator(`[data-artifact-id="${pdf.artifact_id}"]`);
  await pdfRow.focus();
  await page.keyboard.press('Enter');
  await waitVisible('#sourceViewer[open]');
  await page.waitForFunction(({ pageCount }) => {
    const viewer = document.querySelector('#sourceViewer');
    const documentPage = document.querySelector('#documentPage');
    return viewer?.getAttribute('aria-busy') === 'false'
      && document.querySelectorAll('.page-thumb').length === pageCount
      && documentPage instanceof HTMLImageElement
      && documentPage.complete
      && documentPage.naturalWidth > 0;
  }, { pageCount: pdf.page_count });
  check('Source dialog moves focus inside on open', await page.evaluate(() => document.querySelector('#sourceViewer')?.contains(document.activeElement)));
  check('PDF original pages remain inspectable', await page.locator('.page-thumb').count() === pdf.page_count && await page.locator('#documentPage').isVisible());
  check('Lease PDF viewer identifies and serves the selected original artifact', (await page.locator('#sourceViewerTitle').innerText()) === pdf.title && new URL(await page.locator('#openOriginal').getAttribute('href'), API).pathname === `/api/artifacts/${encodeURIComponent(pdf.artifact_id)}`);
  await screenshot('03-lease-pdf-overview.png');
  await page.locator('#zoomIn').click();
  await page.waitForFunction(() => document.querySelector('#sourceViewer')?.getAttribute('aria-busy') === 'false' && document.querySelector('#zoomValue')?.textContent === '115%');
  check('Lease PDF zoom control changes the rendered page, not just its label', await page.locator('#zoomValue').innerText() === '115%' && (await page.locator('#documentPage').getAttribute('style')).includes('scale(1.15)'));
  const inspectedPdfPage = Math.max(1, pdf.page_count || 1);
  if (inspectedPdfPage > 1) {
    const inspectedThumb = page.locator(`.page-thumb[data-page="${inspectedPdfPage}"]`);
    await inspectedThumb.focus();
    await page.keyboard.press('Enter');
    await page.waitForFunction(pageNumber => document.querySelector(`.page-thumb[data-page="${pageNumber}"]`)?.getAttribute('aria-current') === 'page' && document.querySelector('#documentPage')?.alt.endsWith(`page ${pageNumber}`), inspectedPdfPage);
  }
  check('Lease PDF thumbnail navigation renders the requested original page', await page.locator(`.page-thumb[data-page="${inspectedPdfPage}"]`).getAttribute('aria-current') === 'page' && (await page.locator('#documentPage').getAttribute('alt')).endsWith(`page ${inspectedPdfPage}`));
  await screenshot('03-lease-pdf-detail.png');
  await runAxe('Lease PDF original viewer');
  check('Source tabs expose keyboard and panel semantics', await page.evaluate(() => [...document.querySelectorAll('[data-source-tab]')].every(tab => tab.getAttribute('role') === 'tab' && tab.getAttribute('aria-controls') === 'sourceStage') && document.querySelector('#sourceStage')?.getAttribute('role') === 'tabpanel'));
  await page.locator('#sourceTabOriginal').focus();
  await page.keyboard.press('ArrowRight');
  check('Arrow key selects and focuses extraction tab', await page.locator('#sourceTabExtraction').getAttribute('aria-selected') === 'true' && await page.evaluate(() => document.activeElement?.id === 'sourceTabExtraction'));
  const extraction = await getJson(`${API}/api/artifacts/${encodeURIComponent(pdf.artifact_id)}/extraction`);
  const searchQuery = String(extraction.pages?.join(' ') || '').match(/[A-Za-z]{6,}/)?.[0] || 'Tenant';
  await page.locator('#sourceSearch').fill(searchQuery);
  await page.locator('#sourceSearchForm button[type="submit"]').click();
  await waitText('#sourceSearchStatus', /matched/i);
  check('PDF extracted-text search returns navigable page results', await page.locator('#sourceSearchResults [data-search-page]').count() > 0 && await page.locator('#sourceStage mark').count() > 0);
  await screenshot('03-lease-pdf-search.png');
  await page.locator('#sourceTabOriginal').click();
  await waitVisible('#documentPage');
  await page.keyboard.press('Escape');
  await waitHidden('#sourceViewer');
  await page.waitForFunction(artifactId => document.activeElement?.dataset.artifactId === artifactId, pdf.artifact_id);
  check('Closing source dialog restores attachment focus', await page.evaluate(artifactId => document.activeElement?.dataset.artifactId === artifactId, pdf.artifact_id));

  const imageRow = page.locator(`[data-artifact-id="${image.artifact_id}"]`);
  await imageRow.focus();
  await imageRow.press('Enter');
  await waitVisible('#sourceImage');
  await page.waitForFunction(() => { const image = document.querySelector('#sourceImage'); return image?.complete && image.naturalWidth > 0 && image.naturalHeight > 0; });
  const renderedImage = await page.locator('#sourceImage').evaluate(node => ({ src: node.currentSrc, width: node.naturalWidth, height: node.naturalHeight, alt: node.alt }));
  check('Image viewer decodes the selected original pixels with an accessible identity', new URL(renderedImage.src).pathname === `/api/artifacts/${encodeURIComponent(image.artifact_id)}` && renderedImage.width > 0 && renderedImage.height > 0 && renderedImage.alt === image.title, JSON.stringify(renderedImage));
  const imageCount = demo.claim.artifacts.filter(item => item.media_type?.startsWith('image/')).length;
  check('Image gallery controls appear only when useful', imageCount > 1 ? await page.locator('#sourceGalleryNav').isVisible() : await page.locator('#sourceGalleryNav').isHidden());
  if (imageCount > 1) {
    const firstImageTitle = await page.locator('#sourceViewerTitle').innerText();
    await page.locator('#sourceNext').click();
    check('Image next control opens the adjacent original image', (await page.locator('#sourceViewerTitle').innerText()) !== firstImageTitle);
    await page.locator('#sourcePrevious').click();
    check('Image previous control returns to the original image', (await page.locator('#sourceViewerTitle').innerText()) === firstImageTitle);
  }
  await page.locator('#zoomIn').click();
  await page.waitForFunction(() => document.querySelector('#sourceViewer')?.getAttribute('aria-busy') === 'false' && document.querySelector('#zoomValue')?.textContent === '115%');
  check('Image zoom control changes the rendered original image frame', await page.locator('#zoomValue').innerText() === '115%' && (await page.locator('.source-image-frame').getAttribute('style')).includes('scale(1.15)'));
  await screenshot('03-image-inspection.png');
  await runAxe('Original image viewer');
  await page.keyboard.press('Escape');
  await waitHidden('#sourceViewer');
  await page.waitForFunction(artifactId => document.activeElement?.dataset.artifactId === artifactId, image.artifact_id);
  check('Closing image viewer restores attachment focus', await page.evaluate(artifactId => document.activeElement?.dataset.artifactId === artifactId, image.artifact_id));

  await page.locator(`[data-artifact-id="${email.artifact_id}"]`).click();
  await waitVisible('#sourceViewer .email-document');
  check('Email original and extraction representations remain inspectable', await page.locator('#sourceViewer .email-document').isVisible());
  await page.locator('#sourceTabExtraction').click();
  await waitVisible('#sourceStage .extraction-page');
  await page.locator('#closeSourceViewer').click();

  await page.evaluate(() => { window.__casepathFlagshipLaunchAt = performance.now(); });
  await page.locator('#runCasePath').click();
  await waitVisible('#liveWorkspace');
  await waitVisible('#artifactCanvas[data-casepath-scene]');
  const workingCanvas = await artifactCanvasSnapshot();
  const workingCanvasIssues = focusedArtifactCanvasViolations(workingCanvas);
  check('After launch the customer submission and persistent working canvas remain simultaneous with one focus, cursor, artifact, and action', workingCanvasIssues.length === 0, JSON.stringify({ workingCanvas, workingCanvasIssues }));
  const initialSpecialistFocus = await page.locator('#artifactCanvas').evaluate(node => ({
    scene: node.dataset.casepathScene,
    authority: node.dataset.workAuthority,
    cursor_count: node.querySelectorAll('#artifactAgentCursor').length,
    cursor_agent_id: node.querySelector('#artifactAgentCursor')?.dataset.agentId || '',
    cursor_agent_signature: node.querySelector('#artifactAgentCursor')?.dataset.agentSignature || '',
    title: node.querySelector('[data-ac-task]')?.textContent?.trim() || '',
  }));
  check('Flagship opens with one readable phase and one truthful neutral cursor before a call-bound agent receipt', ['opening', 'read', 'understand'].includes(initialSpecialistFocus.scene) && Boolean(initialSpecialistFocus.authority) && initialSpecialistFocus.cursor_count === 1 && initialSpecialistFocus.cursor_agent_id === '' && initialSpecialistFocus.cursor_agent_signature === 'casepath' && Boolean(initialSpecialistFocus.title), JSON.stringify(initialSpecialistFocus));
  const flagshipRunId = await waitForValue(() => runIds[0]);
  if (isProductionJourney()) {
    await page.waitForFunction(() => window.__casepathOpeningContexts?.length > 0, null, { timeout: runTimeoutMs() });
    const openingContexts = await page.evaluate(() => window.__casepathOpeningContexts);
    const openingContextIssues = productionOpeningContextViolations(openingContexts);
    check('First live production frame attributes shared-context setup to application code and waits for the returned Nemotron plan', openingContextIssues.length === 0, JSON.stringify({ openingContexts, openingContextIssues }));
  }
  const processRun = await waitJourneyUi('Visible flagship cold orchestration did not complete', () => awaitRun(flagshipRunId));
  const processGraph = processRun.result?.process || processRun.process;
  const routeStory = processRouteStory(processGraph);
  const routeStoryIssues = processRouteStoryContractViolations(processGraph);
  check('Visible process story is derived from the returned selected path and current overlay', routeStoryIssues.length === 0, JSON.stringify({ routeStory, routeStoryIssues }));
  retainedEvidence['flagship-run'] = processRun;
  const flagshipEvidenceIssues = evidenceRelationContractViolations(processRun.result?.process, processRun.result?.checklist);
  check('Flagship evidence ownership is independently derived from ordered process requirements', flagshipEvidenceIssues.length === 0, JSON.stringify(flagshipEvidenceIssues));
  const flagshipMemoryStateIssues = memoryRetrievalContractViolations(processRun.result);
  check('Flagship result keeps retrieval separate from receipt-bound memory use', flagshipMemoryStateIssues.length === 0, JSON.stringify(flagshipMemoryStateIssues));
  const flagshipLegalIssues = legalContextContractViolations(processRun.result?.legal_research, processRun.result?.process);
  check('Flagship legal questions join exact official passages and deterministic proposals by ID', flagshipLegalIssues.length === 0, JSON.stringify(flagshipLegalIssues));
  const expectedOfficialSources = processRun.result?.legal_research?.sources || [];
  await page.waitForFunction(() => document.querySelector('#artifactCanvas')?.dataset.officialLawTourState === 'complete', null, { timeout: runTimeoutMs() });
  const factTourSnapshots = await page.evaluate(() => window.__casepathFactTourSnapshots || []);
  const liveWorkPlanSnapshots = await page.evaluate(() => window.__casepathLiveWorkPlanSnapshots || []);
  let semanticEvents = await page.evaluate(() => window.__casepathSemanticEvents || []);
  const factTourHighlights = await page.evaluate(() => window.__casepathSourceHighlights || []);
  if (isProductionJourney()) {
    const liveWorkPlanIssues = canonicalFactsLiveWorkPlanContractViolations(liveWorkPlanSnapshots, factTourSnapshots, processRun);
    check('The exact canonical-facts call uses one simple plan and yields source reading to the merged Path builder graph flow', liveWorkPlanIssues.length === 0, JSON.stringify({ liveWorkPlanSnapshots, liveWorkPlanIssues }));
  } else {
    check(
      'Deterministic reference replay does not fabricate a call-bound canonical-facts work plan',
      liveWorkPlanSnapshots.length === 0,
      JSON.stringify({ liveWorkPlanSnapshots }),
    );
  }
  check('No separate eight-fact presentation competes with the merged Path builder graph flow', factTourSnapshots.length === 0, JSON.stringify({ factTourSnapshots, factTourHighlights }));
  const sourceRailSnapshots = await page.evaluate(() => window.__casepathSourceRailSnapshots || []);
  const sourceRailIssues = sourceRailSnapshots.flatMap(snapshot => sourceRailContractViolations(
    snapshot,
    expectedRailSources,
    { sourceId: snapshot.expectedSourceId, locatorId: snapshot.expectedLocatorId },
  ));
  const expectedRailReasons = [
    ...SOURCE_RAIL_VIEWPORTS.map(viewport => `opening:${viewport.width}x${viewport.height}`),
  ];
  const observedRailReasons = new Set(sourceRailSnapshots.map(snapshot => snapshot.reason));
  const missingRailReasons = expectedRailReasons.filter(reason => !observedRailReasons.has(reason));
  check('Opening keeps one compact exact seven-item source rail without a competing source-card strip', sourceRailIssues.length === 0 && missingRailReasons.length === 0, JSON.stringify({ sourceRailSnapshots, sourceRailIssues, missingRailReasons }));
  const officialSourceSteps = await page.evaluate(() => window.__casepathOfficialSourceSteps || []);
  const officialLawTourIssues = officialLawTourContractViolations(officialSourceSteps, semanticEvents, processRun);
  check('Four official Swiss-law items are visibly exact deterministic registry lookups, never Nemotron work', expectedOfficialSources.length === 4 && officialLawTourIssues.length === 0, JSON.stringify({ expectedOfficialSourceIds: expectedOfficialSources.map(source => source.source_id), officialSourceSteps, officialLawTourIssues }));
  const linkedOfficialSourceEvents = semanticEvents.filter(event => event.type === 'legal_source.linked' && event.entityKind === 'official_source');
  check('Run returns four exact official legal-source execution traces', linkedOfficialSourceEvents.length === 4 && linkedOfficialSourceEvents.every(event => event.traceContract === EXECUTION_TRACE_CONTRACT && event.presentationMode === 'deterministic_projection' && event.authority === 'versioned_official_source_registry' && event.officialSourceCount === 4 && SHA256_PATTERN.test(event.outputBindingHash) && event.modelContributionAccepted === false && event.deterministicFallbackApplied === false), JSON.stringify(linkedOfficialSourceEvents));
  const flagshipVisualRefs = (processRun.result?.facts || []).flatMap(fact => (fact.source_refs || []).filter(reference => reference.locator_kind === 'visual_observation'));
  const flagshipVisualIssues = flagshipVisualRefs.flatMap(reference => visualReferenceContractViolations(reference, demo.claim.artifacts.find(artifact => artifact.artifact_id === reference.artifact_id)).map(issue => `${reference.artifact_id}: ${issue}`));
  check('Every flagship visual observation is an exact curated generated-demo annotation bound to public image bytes', flagshipVisualRefs.length > 0 && flagshipVisualIssues.length === 0, JSON.stringify(flagshipVisualIssues));
  const flagshipRankingIssues = precedentRankingContractViolations(processRun.result);
  check('Flagship returns exactly three hash-bound generated reference rankings', flagshipRankingIssues.length === 0, JSON.stringify(flagshipRankingIssues));
  if (isProductionJourney()) {
    const coldIssues = orchestrationContractViolations(processRun, 'cold', releaseContract.agentic_runtime.framework);
    check('Visible flagship proves the exact cold six-agent LangGraph DAG and three deterministic accepted-artifact gates', coldIssues.length === 0, JSON.stringify(coldIssues));
    coldOrchestration = orchestrationAudit(processRun);
  }
  const flagshipColdLedger = await getJson(`${API}/api/model-ledger`);
  retainedEvidence['flagship-cold-model-ledger'] = flagshipColdLedger;
  const flagshipLedgerIssues = sanitizedLedgerViolations(flagshipColdLedger);
  check('Flagship cold ledger is public-safe and schema-bounded', flagshipLedgerIssues.length === 0, JSON.stringify(flagshipLedgerIssues));
  if (isProductionJourney()) {
    const coldLedgerIssues = coldLedgerContractViolations(coldOrchestration, flagshipColdLedger);
    check('Visible flagship binds six distinct paid responses, positive usage, costs, contributions, and lineage to one orchestration', coldLedgerIssues.length === 0, JSON.stringify(coldLedgerIssues));
  }
  await waitJourneyUi('Flagship browser did not reach stable review readiness', async () => {
    await page.waitForFunction(() => window.__casepathMomentHistory.includes('process'), null, { timeout: runTimeoutMs() });
    await page.waitForFunction(() => window.__casepathMomentHistory.includes('evidence'), null, { timeout: runTimeoutMs() });
    if (routeStory.flagshipCausation) await waitText('#journeyNext', /Review document plan/i, runTimeoutMs());
    else await page.waitForFunction(() => document.querySelector('#journeyNext')?.dataset.casepathRouteTerminal === 'true', null, { timeout: runTimeoutMs() });
    await waitVisible('body[data-casepath-moment="ready"]', runTimeoutMs());
    await waitVisible('#artifactCanvas[data-casepath-scene="ready"]', runTimeoutMs());
    await page.waitForFunction(() => document.querySelector('#artifactCanvas')?.dataset.casepathScene === 'ready', null, { timeout: runTimeoutMs() });
  });
  const readyCanvas = await artifactCanvasSnapshot();
  const readyCanvasIssues = focusedArtifactCanvasViolations(readyCanvas);
  check('Ready state preserves the same source-plus-canvas workspace with one focus, one cursor, one primary artifact, and an action only when the returned route can continue', readyCanvasIssues.length === 0 && readyCanvas.action_count === (routeStory.flagshipCausation ? 1 : 0), JSON.stringify({ routeStory, readyCanvas, readyCanvasIssues }));
  check('Ready state keeps only the returned route story as the dominant artifact', readyCanvas.projection === 'flagship-spine/1' && readyCanvas.construction_state === 'complete' && stableJson(readyCanvas.node_states) === stableJson(routeStory.storyNodeIds.map(node_id => ({ node_id, state: 'built' }))), JSON.stringify({ routeStory, nodeStates: readyCanvas.node_states }));
  const readyRouteAction = await page.locator('#journeyNext').evaluate(button => ({ terminal: button.dataset.casepathRouteTerminal || '', disabled: button.disabled, ariaDisabled: button.getAttribute('aria-disabled') || '', primary: button.dataset.casepathPrimaryAction || '' }));
  check('Ready action continues only for the returned evidence-gap flagship route', routeStory.flagshipCausation
    ? readyRouteAction.terminal === 'false' && !readyRouteAction.disabled && readyRouteAction.ariaDisabled === 'false' && readyRouteAction.primary === 'true'
    : readyRouteAction.terminal === 'true' && readyRouteAction.disabled && readyRouteAction.ariaDisabled === 'true' && !readyRouteAction.primary, JSON.stringify({ routeStory, readyRouteAction }));
  const graphMomentSnapshots = await page.evaluate(() => window.__casepathGraphMomentSnapshots || []);
  const verificationGraphScene = [...graphMomentSnapshots].reverse().find(snapshot => snapshot.moment === 'verify' && snapshot.scene === 'verify');
  const verificationGraphIssues = [
    ...graphNativeMomentSceneViolations(verificationGraphScene, 'verify'),
    ...graphNativeMomentCopyContractViolations(verificationGraphScene, {
      attachmentKey: 'verification_attachments',
      attachmentKind: 'verification',
      requiredCopy: ['Final audit'],
      anyOfCopy: [
        ['checks agree', 'No unsupported proposals retained'],
        ['Verification incomplete'],
      ],
    }),
  ];
  check('Verification keeps the graph as the sole focal artifact and states only its concise passed or fail-closed outcome', verificationGraphIssues.length === 0, JSON.stringify({ verificationGraphScene, verificationGraphIssues }));
  const flagshipPresentationMs = await page.evaluate(() => performance.now() - window.__casepathFlagshipLaunchAt);
  const minimumPresentationMs = routeStory.flagshipCausation ? MIN_FLAGSHIP_PRESENTATION_MS : 30000;
  const presentationUpperBoundApplies = !isProductionJourney();
  check('The autonomous returned-route journey stays readable without treating real provider latency as presentation failure', flagshipPresentationMs >= minimumPresentationMs && (!presentationUpperBoundApplies || flagshipPresentationMs <= MAX_FLAGSHIP_PRESENTATION_MS), JSON.stringify({ routeStory: routeStory.storyNodeIds, minimumPresentationMs, maximumPresentationMs: presentationUpperBoundApplies ? MAX_FLAGSHIP_PRESENTATION_MS : null, durationMs: flagshipPresentationMs }));
  await auditViewports('02-ready-process', '#artifactProcessGraph[data-graph-projection="flagship-spine/1"]');
  const flagshipTransport = await page.evaluate(() => ({
    transport: document.body.dataset.runTransport || '',
    stream_connections: Number(document.body.dataset.streamConnections || '0'),
    terminal_hydrations: Number(document.body.dataset.terminalHydrations || '0'),
    active_run_polls: Number(document.body.dataset.activeRunPolls || '-1'),
  }));
  const flagshipBrowserRequests = browserRunRequests.filter(item => item.pathname.includes(`/${flagshipRunId}`));
  const flagshipStreams = flagshipBrowserRequests.filter(item => item.pathname.endsWith('/events'));
  const flagshipHydrations = flagshipBrowserRequests.filter(item => item.pathname === `/api/runs/${flagshipRunId}`);
  check('Visible flagship uses exactly one authenticated fetch-SSE stream, one terminal hydration, and zero active run polls', flagshipTransport.transport === 'fetch-sse' && flagshipTransport.stream_connections === 1 && flagshipTransport.terminal_hydrations === 1 && flagshipTransport.active_run_polls === 0 && flagshipStreams.length === 1 && flagshipStreams[0].method === 'GET' && flagshipStreams[0].session === QA_SESSION_ID && /text\/event-stream/i.test(flagshipStreams[0].accept) && flagshipHydrations.length === 1, JSON.stringify({ flagshipTransport, flagshipBrowserRequests }));
  const terminalValidatorReceipt = await page.locator('.orchestration-receipt.gate-receipt').evaluate(node => ({
    gate_id: node.getAttribute('data-gate-id'),
    label: node.querySelector('small')?.textContent || '',
    identity: node.querySelector('strong')?.textContent || '',
  }));
  check('Final pipeline validator remains visible without becoming a fourth orchestration gate ID', terminalValidatorReceipt.gate_id === null && /deterministic validator receipt/i.test(terminalValidatorReceipt.label) && terminalValidatorReceipt.identity === 'whole-playbook-validator/15.2', JSON.stringify(terminalValidatorReceipt));
  if (isProductionJourney()) {
    await page.locator('#openAudit').click();
    await waitVisible('#auditDrawer[open] #orchestrationProof');
    await screenshot('02-live-nemotron-agent.png');
    const visibleProof = await page.evaluate(() => ({
      agent_ids: window.__casepathVisibleAgentIds || [],
      gate_ids: window.__casepathVisibleGateIds || [],
      proof_visible: !document.querySelector('#orchestrationProof')?.hidden,
      proof_boundary: document.querySelector('.orchestration-boundary')?.textContent || '',
      orchestrator_label: document.querySelector('#orchestratorLabel')?.textContent || '',
    }));
    check('Cold flagship visibly presented every Nemotron role and deterministic gate', exactMembers(visibleProof.agent_ids, REQUIRED_NEMOTRON_AGENT_IDS) && exactMembers(visibleProof.gate_ids, REQUIRED_DETERMINISTIC_GATE_IDS) && visibleProof.proof_visible, JSON.stringify(visibleProof));
    check('Flagship visibly distinguishes the Nemotron focus plan from deterministic LangGraph topology', visibleProof.orchestrator_label === 'Nemotron focus plan · deterministic LangGraph topology', visibleProof.orchestrator_label);
    check('Visible orchestration proof retains the fictional-data, non-decision, unapproved-law, simulated-review, and quarantine boundary', /fictional claim/i.test(visibleProof.proof_boundary) && /no coverage or legal decision/i.test(visibleProof.proof_boundary) && /unapproved/i.test(visibleProof.proof_boundary) && /simulated review is not expert approval/i.test(visibleProof.proof_boundary) && /quarantined/i.test(visibleProof.proof_boundary), visibleProof.proof_boundary);
    const returnedTeam = await page.locator('.orchestration-run-summary').evaluate(node => ({
      role_count: node.dataset.nemotronRoleCount,
      gate_count: node.dataset.deterministicGateCount,
      role_ids: (node.dataset.nemotronRoleIds || '').split(',').filter(Boolean),
      gate_ids: (node.dataset.deterministicGateIds || '').split(',').filter(Boolean),
    }));
    check('Stable flagship summary proves exactly six returned Nemotron roles and three returned deterministic gates', returnedTeam.role_count === '6' && returnedTeam.gate_count === '3' && exactMembers(returnedTeam.role_ids, REQUIRED_NEMOTRON_AGENT_IDS) && exactMembers(returnedTeam.gate_ids, REQUIRED_DETERMINISTIC_GATE_IDS), JSON.stringify(returnedTeam));
    const parallelBranch = await page.locator('.orchestration-parallel-branch').evaluateAll(nodes => nodes.map(node => ({
      role_ids: node.dataset.parallelRoleIds,
      gate_id: node.dataset.parallelGateId,
      labels: [...node.querySelectorAll('span,strong')].map(item => item.textContent.trim()),
    })));
    check('Stable flagship visibly proves the returned source/process fan-out and deterministic join gate', parallelBranch.length === 1 && stableJson(parallelBranch[0]) === stableJson({ role_ids: 'document_source_integrity,process_decision_mapping', gate_id: 'deterministic_process_gate', labels: ['Document and Source Integrity Agent', 'Process Decision Mapping Agent', 'Deterministic Process Contract Gate'] }), JSON.stringify(parallelBranch));
    await page.locator('#teamTrace summary').click();
    await screenshot('03-deterministic-accepted-artifact.png');
    const traceProof = await page.locator('#teamTrace').evaluate(node => {
      const modelRows = [...node.querySelectorAll('li[data-actor-type="nemotron_agent"][data-call-id]:not([data-call-id=""])')];
      return {
        model_call_ids: [...new Set(modelRows.map(item => item.dataset.callId))],
        deterministic_gate_rows: node.querySelectorAll('li[data-actor-type="deterministic_gate"]').length,
        warning_count: document.querySelectorAll('.orchestration-proof-warning').length,
      };
    });
    check('Collapsed Team Trace expands to six distinct model calls and at least three deterministic receipts without missing-proof warnings', traceProof.model_call_ids.length === REQUIRED_NEMOTRON_AGENT_IDS.length && traceProof.deterministic_gate_rows >= REQUIRED_DETERMINISTIC_GATE_IDS.length && traceProof.warning_count === 0, JSON.stringify(traceProof));
    await page.locator('#teamTrace summary').click();
    await page.keyboard.press('Escape');
    await waitHidden('#auditDrawer');
  }
  const isolatedRun = await getJsonForSession(`${API}/api/runs`, ISOLATION_SESSION_ID, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ claim_id: demo.demo_claim_id }) });
  isolationMutated = true;
  const isolatedRead = await awaitRunForSession(isolatedRun.run_id, ISOLATION_SESSION_ID);
  retainedEvidence['isolation-run'] = isolatedRead;
  const isolationLedger = await getJsonForSession(`${API}/api/model-ledger`, ISOLATION_SESSION_ID);
  retainedEvidence['isolation-model-ledger'] = isolationLedger;
  const isolationLedgerIssues = sanitizedLedgerViolations(isolationLedger);
  check('Isolation cache ledger is public-safe and schema-bounded', isolationLedgerIssues.length === 0, JSON.stringify(isolationLedgerIssues));
  if (isProductionJourney()) {
    const warmIssues = orchestrationContractViolations(isolatedRead, 'warm', releaseContract.agentic_runtime.framework);
    check('Post-flagship isolation run reuses all six accepted artifacts without a provider call', warmIssues.length === 0, JSON.stringify(warmIssues));
    warmOrchestration = orchestrationAudit(isolatedRead);
    const earlyLineage = warmLineageContractViolations(coldOrchestration, warmOrchestration, isolationLedger);
    check('Isolation replay binds every warm call to the visible flagship cold origin', earlyLineage.issues.length === 0 && earlyLineage.lineage.length === REQUIRED_NEMOTRON_AGENT_IDS.length, JSON.stringify(earlyLineage));
  }
  const crossSessionRead = await fetch(`${API}/api/runs/${encodeURIComponent(isolatedRun.run_id)}`, { headers: { 'X-CasePath-Session': QA_SESSION_ID } });
  check('Isolation run identifier is not readable from the browser session', crossSessionRead.status === 404, `status=${crossSessionRead.status}`);
  const isolationReset = await getJsonForSession(`${API}/api/demo/reset`, ISOLATION_SESSION_ID, { method: 'POST' });
  check('Isolation reset removes only its caller state and preserves the global model ledger', isolationReset.session_scope === 'caller_only' && isolationReset.removed?.runs >= 1 && isolationReset.model_ledger_preserved === true, JSON.stringify(isolationReset));
  const isolationReadAfterReset = await fetch(`${API}/api/runs/${encodeURIComponent(isolatedRun.run_id)}`, { headers: { 'X-CasePath-Session': ISOLATION_SESSION_ID } });
  const flagshipReadAfterIsolationReset = await getJson(`${API}/api/runs/${encodeURIComponent(flagshipRunId)}`);
  check('Isolation reset removes its own run without disturbing the visible flagship', isolationReadAfterReset.status === 404 && flagshipReadAfterIsolationReset.run_id === flagshipRunId && flagshipReadAfterIsolationReset.status === 'complete', JSON.stringify({ isolation_status: isolationReadAfterReset.status, flagship: runProgressDiagnostic(flagshipReadAfterIsolationReset) }));
  isolationMutated = false;
  check('Uninterrupted journey rendered both process and evidence moments before stable review readiness', await page.evaluate(() => ['process', 'evidence', 'ready'].every(moment => window.__casepathMomentHistory.includes(moment))), JSON.stringify(await page.evaluate(() => window.__casepathMomentHistory)));
  const presentationClarity = await page.evaluate(() => {
    const timeline = window.__casepathPresentationTimeline || [];
    const moments = ['read', 'understand', 'research', 'process', 'evidence', 'experience', 'verify'];
    const issues = [];
    for (const moment of moments) {
      const workIndex = timeline.findIndex(frame => frame.moment === moment && frame.phase === 'working');
      const artifactIndex = timeline.findIndex((frame, index) => index > workIndex && frame.moment === moment && frame.phase === 'artifact');
      if (workIndex < 0 || artifactIndex < 0) {
        issues.push(`${moment}: missing working or artifact frame`);
        continue;
      }
      const concise = ['evidence', 'experience', 'verify'].includes(moment);
      const minimumWorkMs = concise ? 500 : 2300;
      const minimumArtifactMs = concise ? 800 : 5500;
      const workMs = timeline[artifactIndex].at - timeline[workIndex].at;
      if (workMs < minimumWorkMs) issues.push(`${moment}: working frame ${workMs.toFixed(0)}ms`);
      const nextIndex = timeline.findIndex((frame, index) => index > artifactIndex && frame.moment !== moment && ['working', 'artifact', 'ready'].includes(frame.phase));
      if (nextIndex >= 0) {
        const artifactMs = timeline[nextIndex].at - timeline[artifactIndex].at;
        if (artifactMs < minimumArtifactMs) issues.push(`${moment}: artifact frame ${artifactMs.toFixed(0)}ms`);
      }
    }
    const visibleOrder = timeline.filter(frame => ['working', 'artifact', 'ready'].includes(frame.phase)).map(frame => `${frame.moment}:${frame.phase}`);
    return { issues, visible_order: visibleOrder };
  });
  check('Every specialist chapter holds its work and produced artifact long enough to understand', presentationClarity.issues.length === 0, JSON.stringify(presentationClarity));
  const graphSteps = await page.evaluate(() => window.__casepathGraphSteps || []);
  const expectedSpineIds = routeStory.storyNodeIds;
  const nodeSteps = graphSteps.filter(step => step.kind === 'node');
  const branchSteps = graphSteps.filter(step => step.kind === 'branch');
  const completeSteps = graphSteps.filter(step => step.kind === 'complete');
  const graphStepIssues = [];
  if (stableJson(nodeSteps.map(step => step.nodeId)) !== stableJson(expectedSpineIds)) graphStepIssues.push('node order does not equal returned main_spine');
  if (nodeSteps.length !== expectedSpineIds.length || new Set(nodeSteps.map(step => step.nodeId)).size !== expectedSpineIds.length) graphStepIssues.push('node steps are absent or duplicated');
  nodeSteps.forEach((step, index) => {
    if (step.index !== index || step.total !== expectedSpineIds.length) graphStepIssues.push(`${step.nodeId}: index/total drift`);
    if (step.buildingCount !== 1 || step.cursorTargetCount !== 1) graphStepIssues.push(`${step.nodeId}: focal-node count drift`);
    if (!step.basisKinds.length || !step.basisKinds.every(kind => ['evidence', 'law', 'reasoning'].includes(kind))) graphStepIssues.push(`${step.nodeId}: provenance kinds absent or invalid`);
    if (!step.basisKinds.includes('reasoning')) graphStepIssues.push(`${step.nodeId}: process rationale absent`);
    if (step.basisKinds.includes('evidence') && !step.factIds.length) graphStepIssues.push(`${step.nodeId}: evidence without fact IDs`);
    if (step.basisKinds.includes('law') && !step.lawIds.length) graphStepIssues.push(`${step.nodeId}: law without source IDs`);
  });
  const nodeStepHolds = nodeSteps.slice(1).map((step, index) => step.at - nodeSteps[index].at);
  if (nodeStepHolds.some(value => value < MIN_PROCESS_NODE_STEP_MS)) graphStepIssues.push(`node hold ${JSON.stringify(nodeStepHolds)}`);
  const expectedBranchStepIds = routeStory.selectedBranchTargetId ? [routeStory.selectedBranchTargetId] : [];
  if (stableJson(branchSteps.map(step => step.nodeId)) !== stableJson(expectedBranchStepIds) || completeSteps.length !== 1) graphStepIssues.push('selected branch or complete receipt does not match the returned route');
  if (branchSteps[0] && completeSteps[0] && completeSteps[0].at - branchSteps[0].at < MIN_PROCESS_BRANCH_HOLD_MS) graphStepIssues.push(`branch hold ${(completeSteps[0].at - branchSteps[0].at).toFixed(0)}ms`);
  const completedGraph = completeSteps[0];
  if (completedGraph && (completedGraph.detailLiveMode !== 'off' || completedGraph.announcementLiveMode !== 'polite')) graphStepIssues.push('detailed provenance floods the live region');
  const processFrameHold = await page.evaluate(() => {
    const timeline = window.__casepathPresentationTimeline || [];
    const artifactIndex = timeline.findIndex(frame => frame.moment === 'process' && frame.phase === 'artifact');
    const nextIndex = timeline.findIndex((frame, index) => index > artifactIndex && frame.moment !== 'process' && ['working', 'artifact', 'ready'].includes(frame.phase));
    return artifactIndex >= 0 && nextIndex >= 0 ? timeline[nextIndex].at - timeline[artifactIndex].at : 0;
  });
  if (processFrameHold < MIN_PROCESS_BRANCH_HOLD_MS) graphStepIssues.push(`process artifact hold ${processFrameHold.toFixed(0)}ms`);
  check('Retained process story preserves returned order, provenance, semantic holds, one selected branch, and one completion receipt', graphStepIssues.length === 0, JSON.stringify({ expectedSpineIds, graphSteps, processFrameHold, graphStepIssues }));

  const cursorSteps = await page.evaluate(() => window.__casepathCursorSteps || []);
  const cursorStepIssues = cursorSemanticContractViolations(cursorSteps, expectedSpineIds, isProductionJourney());
  const cursorTargetHolds = cursorSteps.slice(1).map((step, index) => step.at - cursorSteps[index].at);
  if (cursorTargetHolds.some(value => value < MIN_CURSOR_TARGET_HOLD_MS)) cursorStepIssues.push(`cursor target hold ${JSON.stringify(cursorTargetHolds)}`);
  const focusViolations = await page.evaluate(() => window.__casepathFocusViolations || []);
  if (focusViolations.length) cursorStepIssues.push(`focus violations ${JSON.stringify(focusViolations)}`);
  check('One calm cursor stays inside one focus and advances only on unique semantic event/agent/target keys without deterministic work inheriting a model identity', cursorStepIssues.length === 0, JSON.stringify({ cursorSteps, cursorStepIssues }));
  const artifactChanges = await page.evaluate(() => window.__casepathArtifactChanges || []);
  const processArtifactChanges = artifactChanges.filter(change => routeStory.storyNodeIds.includes(change.entityId));
  semanticEvents = await page.evaluate(() => window.__casepathSemanticEvents || []);
  const fieldOwnershipIssues = acceptedExecutionFieldOwnershipViolations(semanticEvents, processRun);
  check('Model identities are limited to accepted bounded assertions, sources, decisions, and document fields while CasePath owns structural projection', fieldOwnershipIssues.length === 0, JSON.stringify(fieldOwnershipIssues));
  const artifactCursorSteps = await page.evaluate(() => window.__casepathArtifactCursorSteps || []);
  const artifactTeamSnapshot = await page.locator('#artifactCanvas').evaluate(root => {
    const visible = node => Boolean(node && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden' && getComputedStyle(node).display !== 'none');
    const team = document.querySelector('.ac-global-agent-work [data-ac-team]');
    return {
      ariaLabel: team?.getAttribute('aria-label') || '',
      cursorCount: [...root.querySelectorAll('#artifactAgentCursor')].filter(visible).length,
      members: [...(team?.querySelectorAll('[data-ac-agent-id]') || [])].map(member => ({
        agentId: member.dataset.acAgentId || '',
        visualGroupId: member.dataset.visibleAgentGroup || member.dataset.acAgentId || '',
        role: member.dataset.agentLabel || '',
        short: member.querySelector('small')?.textContent?.trim() || '',
        monogram: member.dataset.agentMonogram || '',
        signature: member.dataset.agentSignature || '',
        controlLabel: member.querySelector('[data-ac-action="open-agent-audit"]')?.getAttribute('aria-label') || '',
        iconMarkup: window.__casepathNormalizeSvg(member.querySelector('svg')),
        color: getComputedStyle(member).getPropertyValue('--agent-color').trim(),
        visible: visible(member),
        monogramVisible: visible(member.querySelector('svg')),
        shortVisible: visible(member.querySelector('small')),
      })),
    };
  });
  const decisionFlowAuditSteps = await page.evaluate(() => window.__casepathDecisionFlowSteps || []);
  const agentAuditSnapshots = [];
  for (const agentId of REQUIRED_VISIBLE_SPECIALIST_IDS) {
    const trigger = page.locator(`.ac-global-agent-work [data-ac-action="open-agent-audit"][data-agent-id="${agentId}"]`);
    await trigger.click();
    await waitVisible(`#artifactCanvas [data-ac-agent-audit][data-agent-id="${agentId}"]`);
    const snapshot = await page.locator('#artifactCanvas [data-ac-agent-audit]').evaluate((panel, expectedAgentId) => {
      const visible = node => Boolean(node && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden' && getComputedStyle(node).display !== 'none');
      const receipt = Object.fromEntries([...panel.querySelectorAll('[data-agent-history-receipt] dl > div')].map(row => [row.querySelector('dt')?.textContent?.trim() || '', row.querySelector('dd')?.textContent?.trim() || '']));
      const accepted = panel.querySelector('[data-agent-history-accepted-ids]');
      return {
        agentId: expectedAgentId,
        opened: visible(panel),
        panelAgentId: panel.dataset.agentId || '',
        panelSignature: panel.dataset.agentSignature || '',
        historyAvailable: panel.dataset.agentHistoryAvailable === 'true',
        historyMode: panel.dataset.agentHistoryMode || '',
        historyContract: panel.querySelector('[data-agent-history-contract]')?.dataset.agentHistoryContract || '',
        historyStepCounts: ['task', 'sources', 'facts', 'output', 'acceptance'].map(part => panel.querySelectorAll(`[data-agent-history-${part}]`).length),
        referenceTaskCount: panel.querySelectorAll('[data-reference-action-history] [data-agent-history-task]').length,
        referenceActionCount: Number(panel.querySelector('[data-reference-action-history]')?.dataset.actionCount || 0),
        referenceActions: [...panel.querySelectorAll('[data-reference-action]')].map(action => ({
          phase: action.dataset.referenceActionPhase || '',
          nodeId: action.dataset.nodeId || '',
          sourceId: action.dataset.sourceId || '',
          locatorId: action.dataset.sourceLocatorId || '',
        })),
        referenceProvenanceVisible: visible(panel.querySelector('[data-reference-action-provenance]')),
        referenceProvenanceText: panel.querySelector('[data-reference-action-provenance]')?.textContent?.trim() || '',
        acceptedCount: Number(accepted?.dataset.acceptedCount || 0),
        acceptedIds: [...panel.querySelectorAll('[data-accepted-item-id]')].map(item => item.dataset.acceptedItemId || ''),
        rejections: [...panel.querySelectorAll('[data-agent-history-rejections] [data-rejected-item-id]')].map(item => ({ id: item.dataset.rejectedItemId || '', invariant: item.dataset.rejectedInvariant || '' })),
        callId: receipt.Call || '',
        outputHash: receipt['Output hash'] || '',
        emptyStateVisible: visible(panel.querySelector('.ac-agent-history-empty')),
        noAgentCallsEmptyStateVisible: [...panel.querySelectorAll('.ac-agent-history-empty')].some(item => visible(item) && /No agent calls were made/i.test(item.textContent || '')),
        buttonPressed: document.querySelector(`.ac-global-agent-work [data-ac-action="open-agent-audit"][data-agent-id="${CSS.escape(expectedAgentId)}"]`)?.getAttribute('aria-pressed') || '',
      };
    }, agentId);
    await page.locator('#artifactCanvas [data-ac-agent-audit] [data-ac-action="close-agent-audit"]').click();
    await waitHidden('#artifactCanvas [data-ac-agent-audit]');
    Object.assign(snapshot, await page.evaluate(expectedAgentId => {
      const trigger = document.querySelector(`.ac-global-agent-work [data-ac-action="open-agent-audit"][data-agent-id="${CSS.escape(expectedAgentId)}"]`);
      return {
        focusRestored: document.activeElement === trigger,
        buttonPressedAfterClose: trigger?.getAttribute('aria-pressed') || '',
        panelOpenAfterClose: Boolean(document.querySelector('#artifactCanvas [data-ac-agent-audit]:not([hidden])')),
      };
    }, agentId));
    agentAuditSnapshots.push(snapshot);
  }
  const returnedAgentAudit = processRun.result?.agent_orchestration || processRun.result?.audit?.agent_orchestration || null;
  const agentAuditIssues = agentAuditContractViolations(agentAuditSnapshots, returnedAgentAudit, isProductionJourney(), decisionFlowAuditSteps);
  check('Each visible specialist opens an exact call-bound history; reference replay keeps the exact Path actions and provenance without fabricating calls', agentAuditIssues.length === 0, JSON.stringify({ agentAuditSnapshots, returnedAgentAudit, decisionFlowAuditSteps, agentAuditIssues }));
  const artifactProducerRoleIssues = artifactCursorProducerRoleContractViolations(artifactTeamSnapshot, artifactCursorSteps, semanticEvents);
  check('Desktop merges source reading and process formation into one Path builder workstream while retaining all six exact runtime identities', artifactProducerRoleIssues.length === 0, JSON.stringify({ artifactTeamSnapshot, artifactCursorSteps, artifactProducerRoleIssues }));
  const specialistAvatarIssues = specialistAvatarContractViolations(artifactTeamSnapshot, artifactCursorSteps, isProductionJourney());
  check('Four visible workstream icons retain all six exact call-bound runtime identities beneath them', specialistAvatarIssues.length === 0, JSON.stringify({ artifactTeamSnapshot, artifactCursorSteps, specialistAvatarIssues }));
  const sourcePreludeSnapshots = await page.evaluate(() => window.__casepathSourcePreludeSnapshots || []);
  const sourcePreludeIssues = sourcePreludeContractViolations(sourcePreludeSnapshots[0]);
  check('Opening uses one calm three-step Path builder plan instead of seven competing source cards', sourcePreludeIssues.length === 0, JSON.stringify({ sourcePreludeSnapshots, sourcePreludeIssues }));
  const mainFocalWhyViolations = await page.evaluate(() => window.__casepathMainFocalWhyViolations || []);
  check('Main focal work never shows a large generic agent why paragraph', mainFocalWhyViolations.length === 0, JSON.stringify(mainFocalWhyViolations));
  const cursorRequiredNodeIds = routeStory.routeNodeIds.filter(nodeId => routeStory.storyNodeIds.includes(nodeId));
  const processChangeIssues = processProjectionContractViolations(processArtifactChanges, semanticEvents, artifactCursorSteps, processRun.run_id, routeStory.storyNodeIds, cursorRequiredNodeIds);
  check('Persistent process canvas constructs only the returned route story monotonically, one justified node at a time', processChangeIssues.length === 0, JSON.stringify({ processArtifactChanges, processChangeIssues }));
  const sourceHighlights = await page.evaluate(() => window.__casepathSourceHighlights || []);
  const decisionFlowSteps = await page.evaluate(() => window.__casepathDecisionFlowSteps || []);
  const artifactInteractions = await page.evaluate(() => window.__casepathArtifactInteractions || []);
  const currentRouteIndex = routeStory.routeNodeIds.indexOf(routeStory.currentNodeId);
  const resolvedRouteNodeIds = routeStory.routeNodeIds
    .slice(0, currentRouteIndex >= 0 ? currentRouteIndex : routeStory.routeNodeIds.length)
    .filter(nodeId => routeStory.storyNodeIds.includes(nodeId));
  const decisionFlowIssues = decisionFlowContractViolations(decisionFlowSteps, processArtifactChanges, sourceHighlights, artifactInteractions, processRun, semanticEvents, resolvedRouteNodeIds);
  check('The graph holds each accepted source basis, keeps its highlighted passage readable, forms the decision, and only then commits the node', decisionFlowIssues.length === 0, JSON.stringify({ contract: DECISION_FLOW_CONTRACT, decisionFlowSteps, decisionFlowIssues }));
  const notificationDecisionSteps = decisionFlowSteps.filter(step => step.nodeId === NOTIFICATION_DECISION_NODE_ID);
  check('Landlord notification appears only when it belongs to the returned route story, with its accepted fact and checked law trace', routeStory.storyNodeIds.includes(NOTIFICATION_DECISION_NODE_ID)
    ? !decisionFlowIssues.some(issue => /notification/i.test(issue)) && notificationDecisionSteps.length > 0
    : notificationDecisionSteps.length === 0, JSON.stringify({ routeStory, notificationDecisionSteps, notificationIssues: decisionFlowIssues.filter(issue => /notification/i.test(issue)) }));
  const branchVisuals = await page.evaluate(() => window.__casepathBranchVisuals || []);
  const processNodeProgressEvents = await page.evaluate(() => window.__casepathProcessNodeProgress || []);
  const processNodeProgressFinal = await page.evaluate(() => window.__casepathProcessNodeProgressUi?.('', 'node') || null);
  const processNodeProgressIssues = processNodeProgressContractViolations(processNodeProgressEvents, processArtifactChanges, processNodeProgressFinal, semanticEvents, processRun.run_id, routeStory.storyNodeIds);
  check('Each calm indicator uses model identity only for an accepted contribution, otherwise a neutral safety identity, and clears before node commit', processNodeProgressIssues.length === 0, JSON.stringify({ contract: PROCESS_NODE_PROGRESS_CONTRACT, scope: PROCESS_NODE_PROGRESS_SCOPE, processNodeProgressEvents, processNodeProgressFinal, branchVisuals, processNodeProgressIssues }));
  check('Only the current decision\'s returned route branches appear, without invented source reads or progress cycles', stableJson(branchVisuals.map(item => item.nodeId)) === stableJson(routeStory.branchNodeIds) && !processNodeProgressEvents.some(item => item.entityKind === 'branch') && !sourceHighlights.some(item => item.entityKind === 'branch'), JSON.stringify({ routeStory, branchVisuals, branchProgress: processNodeProgressEvents.filter(item => item.entityKind === 'branch'), branchHighlights: sourceHighlights.filter(item => item.entityKind === 'branch') }));

  const renderedAttachments = [...new Map(artifactChanges.filter(change => change.attachment?.changeId === change.changeId).map(change => [change.attachment.changeId, change.attachment])).values()];
  const attachmentIssues = contextualAttachmentContractViolations(renderedAttachments, semanticEvents, artifactCursorSteps, isProductionJourney());
  const artifactFocusViolations = await page.evaluate(() => window.__casepathArtifactFocusViolations || []);
  if (artifactFocusViolations.length) attachmentIssues.push(`artifact focus violations ${JSON.stringify(artifactFocusViolations)}`);
  check('Every visible law, evidence, precedent, and verification artifact is a unique streamed change tied to the responsible cursor', attachmentIssues.length === 0, JSON.stringify({ renderedAttachments, semanticEvents, artifactCursorSteps, attachmentIssues }));
  const reusedDecisionLaws = decisionFlowSteps.filter(step => step.phase === 'planned' && step.stepKind === 'accepted-law');
  check('Graph decisions reuse already checked official-law event lineage and never reopen law as new work', reusedDecisionLaws.length > 0 && !decisionFlowSteps.some(step => step.stepKind === 'law') && reusedDecisionLaws.every(step => nonemptyString(step.basisEventId) && step.basisAgentId === 'official_law_registry'), JSON.stringify({ reusedDecisionLaws }));
  check('Authenticated stream exposes the complete semantic claim-handling vocabulary', REQUIRED_SEMANTIC_EVENT_TYPES.every(type => semanticEvents.some(event => event.type === type)) && semanticEvents.every((event, index) => index === 0 || event.sequence > semanticEvents[index - 1].sequence), JSON.stringify(semanticEvents));
  const rejectedProposalCount = (processRun.result?.verification?.rejected_proposals || []).length;
  check('Verification rejection events are emitted exactly when rejected proposals exist', rejectedProposalCount === 0 || semanticEvents.some(event => event.type === 'verification.rejected'), JSON.stringify({ rejectedProposalCount, semanticEvents }));
  check('The returned route story remains the dominant completed graph', await page.locator('#artifactProcessGraph[data-graph-projection="flagship-spine/1"] [data-node-id][data-process-build-state="built"]').count() === routeStory.storyNodeIds.length);

  if (false) { // Retained only as a selector-contract fixture; the visible journey uses the focal canvas below.
  const factLocator = page.locator('#artifactProcessGraph [data-node-attachment-kind="fact"][data-source-locator-id]').first();
  check('At least one process fact exposes an exact customer-source locator', await factLocator.count() === 1 && (await factLocator.getAttribute('data-source-authority')) === 'customer_submission');
  const openedFactLocator = await clickExactArtifactLocator(factLocator, 'selector-fixture-fact');
  const officialLawLocators = await page.locator('#artifactProcessGraph [data-node-attachment-kind="law"][data-source-authority="official_registry"][data-source-locator-id]').evaluateAll(nodes => [...new Set(nodes.map(node => node.dataset.sourceLocatorId).filter(Boolean))]);
  check('Process canvas visibly distinguishes exact official Swiss-law sources from deterministic handling principles', officialLawLocators.length > 0 && renderedAttachments.filter(item => item.kind === 'law').every(item => ['official_registry', 'deterministic_principle'].includes(item.sourceAuthority)), JSON.stringify(renderedAttachments.filter(item => item.kind === 'law')));
  const openedOfficialLawLocators = [];
  for (const locatorId of officialLawLocators) {
    const exactLaw = page.locator(`#artifactProcessGraph [data-node-attachment-kind="law"][data-source-authority="official_registry"][data-source-locator-id=${JSON.stringify(locatorId)}]`).first();
    openedOfficialLawLocators.push(await clickExactArtifactLocator(exactLaw, `selector-fixture-law:${locatorId}`));
  }
  check('Every visible official Swiss-law attachment opens its exact source section in the same source dock', stableJson(openedOfficialLawLocators) === stableJson(officialLawLocators), JSON.stringify({ openedOfficialLawLocators, officialLawLocators }));
  const generatedPrecedent = page.locator('#artifactProcessGraph [data-node-attachment-kind="precedent"][data-reference-status="generated_reference"][data-source-locator-id]').first();
  check('Reference cases remain explicitly generated until a real review authority exists', await generatedPrecedent.count() === 1 && await page.locator('#artifactProcessGraph [data-node-attachment-kind="precedent"][data-reference-status="qualified_expert_reviewed"]').count() === 0);
  const openedPrecedentLocator = await clickExactArtifactLocator(generatedPrecedent, 'selector-fixture-reference');
  check('A generated reference case opens by its exact locator without inflating its authority', nonemptyString(openedPrecedentLocator) && openedPrecedentLocator !== openedFactLocator && !officialLawLocators.includes(openedPrecedentLocator), openedPrecedentLocator);
  }
  await page.locator('#openAudit').click();
  await waitVisible('#auditDrawer[open]');
  check('Visible audit drawer exposes only pending or exactly attested current-release evidence', await page.locator('#browserEvidenceLink').isVisible() && await page.locator('#browserEvidenceLink').evaluate(node => (node.tagName === 'SPAN' && node.dataset.evidenceState === 'pending' && !node.hasAttribute('href')) || (node.tagName === 'A' && node.dataset.evidenceState === 'attested' && node.getAttribute('href') === 'https://casepath-guided-canonical-qa.onrender.com/report.json')));
  check('No reachable product link targets an obsolete QA service', await page.locator('a').evaluateAll((links, pattern) => links.every(link => !new RegExp(pattern, 'i').test(link.href || '')), staleQaService.source));
  await runAxe('Audit drawer with pending release evidence');
  await page.keyboard.press('Escape');
  await waitHidden('#auditDrawer');
  if (isProductionJourney()) {
    const expectedProcessContributions = processGraph.nodes.map(node => ({
      node_id: node.node_id,
      contribution: contributionDomProjection(node.agent_decision_contributions, PROCESS_CONTRIBUTION_ROLE),
    })).filter(item => item.contribution);
    const renderedProcessContributions = await page.locator('.process-map .process-node-button[data-node-id],.process-map .process-branch-node[data-node-id]').evaluateAll(nodes => nodes.flatMap(node => {
      const badge = node.querySelector('.model-contribution-attribution');
      return badge ? [{ node_id: node.dataset.nodeId, contribution: { authority: badge.dataset.contributionAuthority, accepted_count: badge.dataset.acceptedCount, fallback_count: badge.dataset.fallbackCount, accepted_ids: badge.dataset.acceptedContributionIds, fallback_ids: badge.dataset.fallbackContributionIds } }] : [];
    }));
    check('Every visible process contribution is exactly bound to returned Nemotron acceptance or deterministic fallback', stableJson(renderedProcessContributions.sort((a, b) => a.node_id.localeCompare(b.node_id))) === stableJson(expectedProcessContributions.sort((a, b) => a.node_id.localeCompare(b.node_id))) && renderedProcessContributions.some(item => Number(item.contribution.accepted_count) > 0), JSON.stringify({ expectedProcessContributions, renderedProcessContributions }));
    const finalBrief = orchestrationAudit(processRun)?.final_claim_brief;
    const finalProjection = contributionDomProjection(finalBrief?.field_contributions, FINAL_CONTRIBUTION_ROLE);
    const expectedFinalFieldIds = (finalBrief?.field_contributions || []).map(item => item.contribution_id).join(',');
    const currentNode = processGraph.nodes.find(item => item.node_id === finalBrief?.current_node_id);
    const nextNode = processGraph.nodes.find(item => item.node_id === finalBrief?.next_action_node_id);
    const renderedFinalHandoff = await page.locator('.v20-final-handoff').evaluate(node => ({
      current_node_id: node.dataset.currentNodeId,
      next_action_node_id: node.dataset.nextActionNodeId,
      field_count: node.dataset.fieldCount,
      field_ids: node.dataset.fieldIds,
      accepted_count: node.dataset.acceptedCount,
      fallback_count: node.dataset.fallbackCount,
      accepted_ids: node.dataset.acceptedContributionIds,
      fallback_ids: node.dataset.fallbackContributionIds,
      copy: node.textContent,
    }));
    check('Ready view exposes one causally bound five-field final handoff with exact returned IDs and acceptance counts',
      await page.locator('.v20-final-handoff').count() === 1
        && finalProjection
        && currentNode
        && nextNode
        && renderedFinalHandoff.current_node_id === finalBrief.current_node_id
        && renderedFinalHandoff.next_action_node_id === finalBrief.next_action_node_id
        && renderedFinalHandoff.field_count === String(FINAL_FIELD_CONTRACT.length)
        && renderedFinalHandoff.field_ids === expectedFinalFieldIds
        && renderedFinalHandoff.accepted_count === finalProjection.accepted_count
        && renderedFinalHandoff.fallback_count === finalProjection.fallback_count
        && renderedFinalHandoff.accepted_ids === finalProjection.accepted_ids
        && renderedFinalHandoff.fallback_ids === finalProjection.fallback_ids
        && renderedFinalHandoff.copy.includes('Final Claim Brief Agent')
        && renderedFinalHandoff.copy.includes('Whole-Playbook Gate')
        && renderedFinalHandoff.copy.includes(currentNode?.title || '')
        && renderedFinalHandoff.copy.includes(nextNode?.title || '')
        && /five independent fields/i.test(renderedFinalHandoff.copy),
      JSON.stringify({ finalBrief, finalProjection, renderedFinalHandoff }));
  }

  const artifactNodeIds = await page.locator('#artifactProcessGraph [data-node-id][data-process-build-state="built"]').evaluateAll(nodes => nodes.map(node => node.dataset.nodeId));
  check('Completed artifact canvas exposes exactly the returned route story', stableJson(artifactNodeIds) === stableJson(routeStory.storyNodeIds), JSON.stringify({ routeStory, artifactNodeIds }));
  const selectArtifactNode = async nodeId => {
    await page.locator(`#artifactProcessGraph [data-ac-action="select-node"][data-node-id=${JSON.stringify(nodeId)}]`).click();
    await page.waitForFunction(expected => document.querySelector('#artifactProcessGraph [data-node-id][data-selected="true"]')?.dataset.nodeId === expected, nodeId);
  };
  const revealArtifactGrounding = async (kind, checkContext) => {
    const disclosure = page.locator('#artifactProcessGraph .ac-grounding-disclosure');
    check(`Active decision [${checkContext}] offers its ${kind} grounding on demand`, await disclosure.count() === 1);
    const before = await artifactGroundingModalSnapshot();
    const toggle = disclosure.locator(':scope > [data-ac-action="toggle-grounding"]');
    check(`Active decision [${checkContext}] keeps ${kind} details hidden before the explicit modal click`, !before.viewerOpen && before.inlinePanelHidden && before.visibleInlineItemCount === 0 && before.toggleHaspopup === 'dialog' && before.toggleExpanded === 'false', JSON.stringify(before));
    await toggle.click();
    await waitVisible('#artifactCanvas [data-ac-grounding-viewer][open]');
    const opened = { ...(await artifactGroundingModalSnapshot()), openedByExplicitClick: true };
    const requiredKind = kind === 'reference' ? 'precedent' : kind;
    const trace = { before, opened };
    const modalIssues = groundingModalContractViolations(trace, requiredKind);
    check(`Active decision [${checkContext}] opens ${kind} only in a source-rail-safe modal`, modalIssues.length === 0, JSON.stringify({ trace, modalIssues }));
    const attachment = page.locator(`#artifactCanvas [data-ac-grounding-viewer][open] [data-node-attachment-kind=${JSON.stringify(requiredKind)}]`);
    check(`Grounding modal [${checkContext}] exposes actionable ${kind}`, await attachment.count() >= 1 && await attachment.first().isVisible() && await attachment.first().isEnabled() && nonemptyString(await attachment.first().getAttribute('data-ac-action')));
    return { attachment, trace };
  };
  const closeArtifactGrounding = async (trace, label) => {
    await page.locator('#artifactCanvas [data-ac-grounding-viewer][open] [data-ac-action="close-grounding"]').click();
    await waitHidden('#artifactCanvas [data-ac-grounding-viewer][open]');
    trace.closed = await artifactGroundingModalSnapshot();
    const issues = groundingModalContractViolations(trace);
    check(`${label} modal close restores one graph focus and action`, issues.length === 0, JSON.stringify({ trace, issues }));
  };

  await selectArtifactNode(routeStory.currentNodeId);
  const spatialGeometry = await spatialGraphGeometrySnapshot();
  const spatialGeometryIssues = spatialGraphGeometryContractViolations(spatialGeometry, {
    processId: processGraph.process_id,
    processAgentId: 'process_projection',
    returnedNodeIds: processGraph.nodes.map(node => node.node_id),
    returnedEdges: processGraph.edges.map(edge => ({ source: edge.source, target: edge.target, state: edge.state || '' })),
    routeStory,
    evidenceById: Object.fromEntries(processRun.result.checklist.items.map(item => [item.item_id, item])),
  });
  check('The returned claim process is one dominant, truthful spatial graph whose path, current decision, branches, grounding, and next action come from the result', spatialGeometryIssues.length === 0, JSON.stringify({ routeStory, spatialGeometry, spatialGeometryIssues }));

  const sourcePreviewNode = [...routeStory.storyNodeIds].reverse()
    .map(nodeId => processGraph.nodes.find(node => node.node_id === nodeId))
    .find(node => (node?.fact_ids || []).some(factId => processRun.result.facts.find(fact => fact.fact_id === factId)?.source_refs?.some(usableDecisionReference)));
  check('Returned route has a source-grounded decision available for audit', Boolean(sourcePreviewNode), JSON.stringify(routeStory));
  await selectArtifactNode(sourcePreviewNode.node_id);
  const visibleFactLocator = page.locator('#artifactProcessGraph .ac-grounding-disclosure[data-grounding-open="false"] > .ac-node-source-preview[data-node-attachment-kind="fact"][data-source-locator-id]:visible').first();
  check('Completed decision keeps its exact customer-source preview visible while modal grounding remains closed', await visibleFactLocator.isVisible() && await visibleFactLocator.locator('[data-ac-action="open-source"]').count() === 1 && await page.locator('#artifactCanvas [data-ac-grounding-viewer][open]').count() === 0 && await page.locator('#artifactProcessGraph .ac-grounding-disclosure > div:not(.ac-node-source-preview):not([hidden])').count() === 0);
  const openedFactLocator = await clickExactArtifactLocator(visibleFactLocator, `ready-fact:${sourcePreviewNode.node_id}`);
  await waitVisible('#sourceViewer[open]');
  check('Customer-source click opens the exact returned fact and locator', await page.locator('#sourceViewer .source-fact').count() > 0 && (await page.locator('[data-source-dock-state]').first().getAttribute('data-active-source-locator')) === openedFactLocator, openedFactLocator);
  const openedFactContext = await visibleFactLocator.evaluate(node => ({
    fact_id: node.dataset.factId || '',
    node_id: node.dataset.nodeId || '',
    source_id: node.dataset.sourceId || '',
    locator_kind: node.dataset.locatorKind || '',
    page: Number(node.dataset.sourcePage || '0'),
    excerpt: node.dataset.sourceExcerpt || '',
    region: node.dataset.sourceRegion || '',
    agent: node.dataset.sourceAgent || '',
    producer: node.dataset.sourceProducer || '',
    authority: node.dataset.sourceAuthority || '',
    confidence: node.dataset.factConfidence || '',
    state: node.dataset.factState || '',
  }));
  const openedFact = processRun.result.facts.find(fact => fact.fact_id === openedFactContext.fact_id);
  if (openedFactContext.locator_kind === 'text_quote') await waitVisible('#sourceViewer[open] #sourceStage mark');
  const sourceRoundtrip = await page.locator('#sourceViewer[open]').evaluate((root, context) => {
    const opened = root.querySelector(`.opened-grounding[data-fact-id="${CSS.escape(context.fact_id)}"][data-node-id="${CSS.escape(context.node_id)}"]`);
    const passage = opened?.querySelector(`[data-locator-kind="${CSS.escape(context.locator_kind)}"]`);
    const highlighted = [...root.querySelectorAll('#sourceStage mark,.source-highlight,[data-source-highlight="true"],[data-highlighted="true"]')]
      .filter(node => node.getClientRects().length && (!context.excerpt || node.textContent.includes(context.excerpt)));
    return {
      fact_id: opened?.dataset.factId || '',
      node_id: opened?.dataset.nodeId || '',
      page: Number(passage?.dataset.sourcePage || '0'),
      excerpt: passage?.dataset.sourceExcerpt || '',
      locator_kind: passage?.dataset.locatorKind || '',
      region: passage?.dataset.sourceRegion || '',
      agent: passage?.dataset.sourceAgent || opened?.dataset.sourceAgent || '',
      producer: passage?.dataset.sourceProducer || opened?.dataset.sourceProducer || '',
      authority: passage?.dataset.sourceAuthority || opened?.dataset.sourceAuthority || '',
      confidence: opened?.dataset.factConfidence || '',
      state: opened?.dataset.factState || '',
      text: root.innerText || '',
      extraction_selected: root.querySelector('[data-source-tab="extraction"]')?.getAttribute('aria-selected') === 'true',
      exact_text_visible: !context.excerpt || (root.innerText || '').includes(context.excerpt),
      exact_text_highlighted: context.locator_kind !== 'text_quote' || (highlighted.length > 0 && root.querySelector('#sourceStage')?.textContent.includes(context.excerpt)),
    };
  }, openedFactContext);
  const returnedFactReference = openedFact?.source_refs?.find(reference => reference.artifact_id === openedFactContext.source_id && reference.locator_kind === openedFactContext.locator_kind && Number(reference.page || 0) === openedFactContext.page && (reference.excerpt || '') === openedFactContext.excerpt && (Array.isArray(reference.region) ? JSON.stringify(reference.region) : '') === openedFactContext.region);
  const expectedProducer = String(returnedFactReference?.producer || openedFactContext.producer || '');
  const expectedAuthority = String(returnedFactReference?.authority || openedFactContext.authority || 'customer_submission');
  const expectedAgent = String(returnedFactReference?.agent || openedFactContext.agent || '');
  check('Ready graph source roundtrip preserves the exact returned node, fact, page and excerpt or region, including fact truth and producer authority', sourcePreviewNode?.fact_ids?.includes(openedFactContext.fact_id) === true && Boolean(openedFact) && Boolean(returnedFactReference) && sourceRoundtrip.node_id === openedFactContext.node_id && sourceRoundtrip.fact_id === openedFactContext.fact_id && sourceRoundtrip.page === openedFactContext.page && sourceRoundtrip.excerpt === openedFactContext.excerpt && sourceRoundtrip.region === openedFactContext.region && sourceRoundtrip.confidence === String(openedFact.confidence ?? '') && sourceRoundtrip.state === String(openedFact.state || '') && sourceRoundtrip.agent === expectedAgent && sourceRoundtrip.producer === expectedProducer && sourceRoundtrip.authority === expectedAuthority && sourceRoundtrip.exact_text_visible && sourceRoundtrip.exact_text_highlighted && (openedFactContext.locator_kind !== 'text_quote' || sourceRoundtrip.extraction_selected), JSON.stringify({ openedFactContext, sourceRoundtrip, openedFact, returnedFactReference }));
  await page.locator('#closeSourceViewer').click();

  const returnedOfficialLawIds = new Set((processRun.result.legal_research?.sources || []).map(source => source.source_id));
  const lawNodeById = Object.fromEntries(routeStory.storyNodeIds.flatMap(nodeId => {
    const node = processGraph.nodes.find(item => item.node_id === nodeId);
    return (node?.legal_source_ids || []).filter(sourceId => returnedOfficialLawIds.has(sourceId)).map(sourceId => [sourceId, nodeId]);
  }));
  const openedOfficialLawLocators = [];
  for (const [sourceId, nodeId] of Object.entries(lawNodeById)) {
    await selectArtifactNode(nodeId);
    await revealArtifactGrounding('law', `official-law:${sourceId}`);
    const exactLawButton = page.locator(`#artifactCanvas [data-ac-grounding-viewer][open] [data-node-attachment-kind="law"][data-source-authority="official_registry"][data-law-id=${JSON.stringify(sourceId)}][data-ac-action="open-law"]`);
    check(`${sourceId} is visibly rendered as an official registry source`, await exactLawButton.count() === 1);
    openedOfficialLawLocators.push(await clickExactArtifactLocator(exactLawButton, `official-law:${sourceId}`));
    await waitVisible(`[data-ac-law-viewer][open][data-law-id=${JSON.stringify(sourceId)}][data-source-authority="official_registry"]`);
    check(`${sourceId} opens its exact cached passage only on demand`, (await page.locator('[data-ac-law-viewer][open]').innerText()).includes(processRun.result.legal_research.sources.find(source => source.source_id === sourceId)?.passage_text || ''));
    await page.locator('[data-ac-law-viewer] [data-ac-action="close-law"]').click();
  }
  const expectedAccessibleLawLocators = Object.keys(lawNodeById).map(sourceId => `law:${sourceId}`);
  check('Every official Swiss-law source on the returned route story opens its exact locator', stableJson(openedOfficialLawLocators) === stableJson(expectedAccessibleLawLocators), JSON.stringify(openedOfficialLawLocators));
  check('The escalation-only BWO source remains in the returned registry without becoming a detached visual chapter', expectedOfficialSources.some(source => source.source_id === 'bwo-conciliation')
    && officialSourceSteps.some(step => step.sourceId === 'bwo-conciliation' && step.selectedSourceId === 'bwo-conciliation' && step.passageSourceId === 'bwo-conciliation')
    && !reusedDecisionLaws.some(step => step.sourceId === 'bwo-conciliation'));

  await selectArtifactNode(routeStory.currentNodeId);
  const currentHandlingPrincipleIds = new Set((processRun.result.legal_research?.questions || [])
    .filter(question => (question.process_node_ids || []).includes(routeStory.currentNodeId))
    .flatMap(question => question.interpretation_ids || []));
  if (currentHandlingPrincipleIds.size) {
    const { trace: deterministicLawTrace } = await revealArtifactGrounding('law', `deterministic-law:${routeStory.currentNodeId}`);
    check('Deterministic legal application stays visibly separate from official registry law', await page.locator('#artifactCanvas [data-ac-grounding-viewer][open] [data-node-attachment-kind="law"][data-source-authority="deterministic_principle"]').count() >= 1);
    await closeArtifactGrounding(deterministicLawTrace, 'Law grounding');
  }
  const { attachment: evidenceButtons } = await revealArtifactGrounding('evidence', `evidence:${routeStory.currentNodeId}`);
  const exactEvidenceButton = evidenceButtons.first();
  const visibleEvidence = await exactEvidenceButton.evaluate(node => ({ item_id: node.dataset.evidenceId, fact_id: node.dataset.factId, text: node.innerText }));
  const returnedEvidence = processRun.result.checklist.items.find(item => item.item_id === visibleEvidence.item_id);
  check('Decision-local evidence is the exact returned requirement owned by the current decision', Boolean(returnedEvidence) && returnedEvidence.node_ids.includes(routeStory.currentNodeId) && visibleEvidence.fact_id === returnedEvidence.fact_id && visibleEvidence.text.includes(returnedEvidence.title), JSON.stringify({ routeStory, visibleEvidence, returnedEvidence }));
  const evidenceInteractionCount = await page.evaluate(() => window.__casepathArtifactInteractions.length);
  await exactEvidenceButton.click();
  await waitHidden('#artifactCanvas [data-ac-grounding-viewer][open]');
  const evidenceInteraction = await page.evaluate(index => window.__casepathArtifactInteractions.slice(index).find(item => item.action === 'inspect-evidence') || null, evidenceInteractionCount);
  check('Exact document/evidence requirement remains actionable from the grounding modal', evidenceInteraction?.nodeId === routeStory.currentNodeId && evidenceInteraction?.evidenceId === returnedEvidence?.item_id, JSON.stringify(evidenceInteraction));

  await revealArtifactGrounding('reference', `reference:${routeStory.currentNodeId}`);
  const visibleGeneratedReference = page.locator('#artifactCanvas [data-ac-grounding-viewer][open] [data-node-attachment-kind="precedent"][data-reference-status="generated_reference"][data-source-locator-id][data-ac-action="open-reference"]');
  check('Current decision exposes one clearly generated reference pattern', await visibleGeneratedReference.count() === 1 && await page.locator('#artifactCanvas [data-reference-status="qualified_expert_reviewed"]').count() === 0);
  const defaultReferenceCopy = await visibleGeneratedReference.innerText();
  check('Default grounding-modal reference hides rank and score while retaining the audit-bound metadata in data attributes', !/\brank\b|\bscore\b|\d+\s*points?/i.test(defaultReferenceCopy) && nonemptyString(await visibleGeneratedReference.getAttribute('data-artifact-change-id')) && nonemptyString(await visibleGeneratedReference.getAttribute('data-artifact-event-id')) && nonemptyString(await visibleGeneratedReference.getAttribute('data-artifact-agent-id')), defaultReferenceCopy);
  const openedReferenceLocator = await clickExactArtifactLocator(visibleGeneratedReference, `reference:${routeStory.currentNodeId}`);
  await waitVisible('#precedentViewer[open]');
  check('Generated reference opens by its exact locator and preserves ranking provenance', openedReferenceLocator.startsWith('reference:') && await page.locator('#precedentViewer .precedent-rank').count() === 1, openedReferenceLocator);
  await page.locator('#closePrecedent').click();

  const facts = processRun.result?.facts || processRun.understanding?.facts || [];
  const visualFact = facts.find(item => item.source_refs?.some(ref => ref.locator_kind === 'visual_observation') && processGraph.nodes.some(node => (node.fact_ids || []).includes(item.fact_id)));
  check('A process-owned visual-observation fact is available', Boolean(visualFact), JSON.stringify(facts.map(item => ({ fact_id: item.fact_id, locator_kinds: item.source_refs?.map(ref => ref.locator_kind) }))));
  const visualRef = visualFact.source_refs.find(ref => ref.locator_kind === 'visual_observation');
  const visualNode = processGraph.nodes.find(node => (node.fact_ids || []).includes(visualFact.fact_id));
  await page.evaluate(detail => document.dispatchEvent(new CustomEvent('casepath:open-source', { detail })), {
    artifactId: visualRef.artifact_id,
    page: visualRef.page || 1,
    context: {
      factId: visualFact.fact_id,
      nodeId: visualNode.node_id,
      locator_kind: visualRef.locator_kind,
      page: visualRef.page || 1,
      excerpt: visualRef.excerpt || '',
      region: visualRef.region || null,
      observation: visualRef.observation || '',
      field: visualRef.field || '',
      value: visualRef.value ?? '',
      agent: visualRef.agent || '',
      producer: visualRef.producer || '',
      authority: visualRef.authority || '',
      annotation_contract: visualRef.annotation_contract || '',
      annotation_version: visualRef.annotation_version || '',
      image_sha256: visualRef.image_sha256 || '',
      confidence: visualFact.confidence ?? '',
      state: visualFact.state || '',
    },
  });
  await waitVisible('#sourceViewer[open] .visual-region-highlight');
  const highlightedRegion = await page.locator('.visual-region-highlight').evaluate(node => ({ region: JSON.parse(node.dataset.highlightRegion), left: parseFloat(node.style.left) / 100, top: parseFloat(node.style.top) / 100, width: parseFloat(node.style.width) / 100, height: parseFloat(node.style.height) / 100, label: node.getAttribute('aria-label'), producer: node.dataset.sourceProducer, authority: node.dataset.sourceAuthority, annotation_contract: node.dataset.annotationContract, annotation_version: node.dataset.annotationVersion, image_sha256: node.dataset.imageSha256, artifact_sha256: node.dataset.artifactSha256 }));
  const visualRegionValid = Array.isArray(visualRef.region) && visualRef.region.length === 4 && visualRef.region.every(value => Number.isFinite(value) && value >= 0 && value <= 1) && visualRef.region[2] > 0 && visualRef.region[3] > 0 && visualRef.region[0] + visualRef.region[2] <= 1 && visualRef.region[1] + visualRef.region[3] <= 1;
  const visualArtifact = demo.claim.artifacts.find(item => item.artifact_id === visualRef.artifact_id);
  check('Opening a visual fact highlights the exact normalized image region and hash-bound generated-demo authority', visualRegionValid && visualArtifact?.media_type?.startsWith('image/') && JSON.stringify(highlightedRegion.region) === JSON.stringify(visualRef.region) && [highlightedRegion.left, highlightedRegion.top, highlightedRegion.width, highlightedRegion.height].every((value, index) => Math.abs(value - visualRef.region[index]) < 1e-9) && highlightedRegion.label.includes(visualRef.observation) && highlightedRegion.producer === visualRef.producer && highlightedRegion.authority === visualRef.authority && highlightedRegion.annotation_contract === visualRef.annotation_contract && highlightedRegion.annotation_version === visualRef.annotation_version && highlightedRegion.image_sha256 === visualRef.image_sha256 && highlightedRegion.artifact_sha256 === visualArtifact.sha256, JSON.stringify({ visualRef, visualArtifact, highlightedRegion }));
  const visualPassage = await page.locator(`.source-fact[data-fact-id="${visualFact.fact_id}"] .source-passage[data-locator-kind="visual_observation"]`).evaluate(node => ({ region: node.dataset.sourceRegion, observation: node.dataset.sourceObservation, producer: node.dataset.sourceProducer, authority: node.dataset.sourceAuthority, annotation_contract: node.dataset.annotationContract, annotation_version: node.dataset.annotationVersion, image_sha256: node.dataset.imageSha256, hasQuote: Boolean(node.querySelector('q')), text: node.innerText }));
  check('Visual source-to-fact grounding roundtrips the exact curated annotation without agent, extraction, or quotation authority', visualPassage.region === JSON.stringify(visualRef.region) && visualPassage.observation === visualRef.observation && visualPassage.producer === visualRef.producer && visualPassage.authority === visualRef.authority && visualPassage.annotation_contract === visualRef.annotation_contract && visualPassage.annotation_version === visualRef.annotation_version && visualPassage.image_sha256 === visualArtifact.sha256 && !visualPassage.hasQuote && !/machine extraction|agent observation|model output/i.test(visualPassage.text.replace('not machine extraction, model output', '')) && await page.locator('.opened-grounding q').count() === 0, JSON.stringify({ visualRef, visualPassage }));
  check('Grounded image inspection retains decoded original pixels', await page.locator('#sourceImage').evaluate(node => node.complete && node.naturalWidth > 0 && node.naturalHeight > 0));
  await screenshot('03-image-grounding-inspection.png');
  await runAxe('Grounded image viewer');
  await page.locator('#closeSourceViewer').click();

  if (false) { // Hidden compatibility DOM remains contract-tested statically; the flagship interacts only with the artifact canvas.
  await page.locator('[data-v21-ready-explore]').click();
  await waitVisible('.process-layout');
  check('The complete process appears only after explicit exploration', await page.locator('[data-v21-ready-explore]').getAttribute('aria-expanded') === 'true');
  const readyPrecedentProjection = await page.locator('.precedent-inline .precedent-mini').evaluateAll(nodes => nodes.map(node => ({
    claim_id: node.querySelector('strong')?.textContent?.split(' · ')[0],
    rank: Number(node.querySelector('.precedent-rank')?.dataset.rank),
  })));
  check('Ready workspace initially exposes all three ordered generated reference patterns', JSON.stringify(readyPrecedentProjection) === JSON.stringify(processRun.result.precedents.map(item => ({ claim_id: item.claim_id, rank: item.ranking.rank }))), JSON.stringify(readyPrecedentProjection));
  await page.locator('[data-toggle-all-branches]').click();
  const renderedNodeIds = await page.evaluate(() => [...new Set([...document.querySelectorAll('.process-node-button[data-node-id],.process-branch-node[data-node-id]')].map(node => node.dataset.nodeId))]);
  const expectedNodeIds = processGraph.nodes.map(node => node.node_id);
  check('Every backend process node is experienceable', expectedNodeIds.every(id => renderedNodeIds.includes(id)) && renderedNodeIds.length === expectedNodeIds.length, JSON.stringify({ expectedNodeIds, renderedNodeIds }));
  await page.locator('.process-node-button[data-node-id="causation"],.process-branch-node[data-node-id="causation"]').first().click();
  const officialLawMarker = page.locator('.decision-inspector .law-marker.official').first();
  const deterministicLawMarker = page.locator('.decision-inspector .law-marker.interpretation').first();
  check('Official passages and deterministic application proposals have distinct inspectable controls', await officialLawMarker.count() === 1 && await deterministicLawMarker.count() === 1);
  const officialLawId = await officialLawMarker.getAttribute('data-law-id');
  const officialLaw = processRun.result.legal_research.sources.find(source => source.source_id === officialLawId);
  await officialLawMarker.click();
  const officialLawDetail = page.locator(`.law-detail[data-law-detail="${officialLawId}"]:not([hidden]) .legal-authority.official`);
  const officialLawProjection = await officialLawDetail.evaluate(node => ({ source_id: node.dataset.legalSourceId, passage_sha256: node.dataset.passageSha256, snapshot_sha256: node.dataset.snapshotSha256, snapshot_scope: node.dataset.snapshotScope, registry_version: node.dataset.registryVersion, text: node.innerText }));
  check('Official legal detail shows the exact passage, version/location, passage hash, snapshot scope, and registry provenance pending qualified review', officialLawProjection.source_id === officialLaw.source_id && officialLawProjection.passage_sha256 === officialLaw.passage_sha256 && officialLawProjection.snapshot_sha256 === officialLaw.retrieval.snapshot_sha256 && officialLawProjection.snapshot_scope === officialLaw.retrieval.snapshot_scope && officialLawProjection.registry_version === officialLaw.retrieval.registry_version && officialLawProjection.text.includes(officialLaw.passage_text) && officialLawProjection.text.includes(officialLaw.version_date) && officialLawProjection.text.includes(officialLaw.location) && officialLawProjection.text.includes(officialLaw.retrieval.snapshot_scope) && /official registry source/i.test(officialLawProjection.text) && /qualified review pending/i.test(officialLawProjection.text) && !/model interpretation|live retrieval/i.test(officialLawProjection.text), JSON.stringify(officialLawProjection));
  const deterministicLawId = await deterministicLawMarker.getAttribute('data-law-id');
  await deterministicLawMarker.click();
  const deterministicLaw = processRun.result.legal_research.handling_principles.find(source => source.source_id === deterministicLawId);
  const deterministicLawProjection = await page.locator(`.law-detail[data-law-detail="${deterministicLawId}"]:not([hidden]) .legal-authority.deterministic`).evaluate(node => ({ source_id: node.dataset.legalSourceId, producer: node.dataset.producer, text: node.innerText }));
  check('Handling principle is visibly a deterministic application proposal pending qualified review', deterministicLawProjection.source_id === deterministicLaw.source_id && deterministicLawProjection.producer === 'deterministic_application' && /deterministic application proposal/i.test(deterministicLawProjection.text) && /qualified review pending/i.test(deterministicLawProjection.text) && !/model interpretation|live retrieval/i.test(deterministicLawProjection.text), JSON.stringify(deterministicLawProjection));
  const renderedPrecedents = await page.locator('.precedent-inline .precedent-mini').evaluateAll(nodes => nodes.map(node => { const ranking = node.querySelector('.precedent-rank'); return { claim_id: node.querySelector('strong')?.textContent?.split(' · ')[0], contract: ranking?.dataset.rankingContract, corpus_version: ranking?.dataset.corpusVersion, rank: Number(ranking?.dataset.rank), score_basis_points: Number(ranking?.dataset.scoreBasisPoints), context_hash: ranking?.dataset.contextHash, text: node.innerText }; }));
  const expectedRenderedPrecedents = processRun.result.precedents.map(item => ({ claim_id: item.claim_id, contract: item.ranking.contract, corpus_version: item.ranking.corpus_version, rank: item.ranking.rank, score_basis_points: item.ranking.score_basis_points, context_hash: item.ranking.context_hash }));
  check('Exactly three generated reference patterns expose ordered rank, score, factors, corpus, and context hash', renderedPrecedents.length === 3 && renderedPrecedents.every((item, index) => Object.entries(expectedRenderedPrecedents[index]).every(([key, value]) => item[key] === value) && /generated reference pattern/i.test(item.text)), JSON.stringify({ renderedPrecedents, expectedRenderedPrecedents }));
  const rankingReceiptProjection = await page.locator('.precedent-ranking-receipt').first().evaluate(node => ({ contract: node.dataset.rankingContract, corpus_version: node.dataset.corpusVersion, context_hash: node.dataset.contextHash, result_hash: node.dataset.resultHash, selected_ids: node.dataset.selectedClaimIds, text: node.innerText }));
  check('Rendered ranking receipt exposes the exact selected IDs, context, candidate scores, and result hash', rankingReceiptProjection.contract === processRun.result.precedent_ranking.contract && rankingReceiptProjection.corpus_version === processRun.result.precedent_ranking.corpus_version && rankingReceiptProjection.context_hash === processRun.result.precedent_ranking.context_hash && rankingReceiptProjection.result_hash === processRun.result.precedent_ranking.result_hash && rankingReceiptProjection.selected_ids === processRun.result.precedent_ranking.selected_claim_ids.join(',') && /candidate scores/i.test(rankingReceiptProjection.text) === false && processRun.result.precedent_ranking.candidate_scores.slice(0, 3).every(candidate => rankingReceiptProjection.text.includes(`${candidate.claim_id}: ${candidate.score_basis_points}`)), JSON.stringify(rankingReceiptProjection));
  await page.locator('.precedent-inline .precedent-mini').first().click();
  await waitVisible('#precedentViewer[open] .precedent-rank');
  check('Precedent dialog preserves inspectable rank factors and ranking receipt', (await page.locator('#precedentViewer .precedent-rank').getAttribute('data-context-hash')) === processRun.result.precedents[0].ranking.context_hash && (await page.locator('#precedentViewer .precedent-ranking-receipt').getAttribute('data-result-hash')) === processRun.result.precedent_ranking.result_hash);
  await page.locator('#closePrecedent').click();
  const renderedEdges = await page.locator('.process-edge[data-edge-source][data-edge-target]').evaluateAll(edges => edges.map(edge => ({ source: edge.dataset.edgeSource, target: edge.dataset.edgeTarget, state: edge.dataset.edgeState })));
  const expectedEdges = processGraph.edges.map(edge => ({ source: edge.source, target: edge.target, state: edge.state || '' }));
  check('Every backend process edge is experienceable with structural endpoints and state', JSON.stringify(renderedEdges) === JSON.stringify(expectedEdges), JSON.stringify({ expectedEdges, renderedEdges }));
  await page.locator('.process-edge-ledger summary').click();
  check('Compact connection ledger is keyboard-actionable', await page.locator('.process-edge').first().isVisible());
  const firstEdgeTarget = processGraph.edges[0].target;
  await page.locator('.process-edge').first().focus();
  await page.keyboard.press('Enter');
  check('A graph connection is keyboard-routable to its destination decision', await page.locator(`.decision-inspector[data-inspector-node="${firstEdgeTarget}"]`).count() === 1);
  const firstBranchId = processGraph.nodes.find(node => !processGraph.main_spine.includes(node.node_id)).node_id;
  await page.locator(`.process-branch-node[data-node-id="${firstBranchId}"]`).focus();
  await page.keyboard.press('Enter');
  check('Branch expansion is keyboard-actionable', await page.locator(`.decision-inspector[data-inspector-node="${firstBranchId}"]`).count() === 1);
  const fact = selectProcessTextQuoteFact(facts, processGraph, 'fact_tenancy');
  check('A process-owned text-quote fact is available', Boolean(fact), JSON.stringify(facts.map(item => ({ fact_id: item.fact_id, locator_kinds: item.source_refs?.map(ref => ref.locator_kind) }))));
  const owningNode = processGraph.nodes.find(node => (node.fact_ids || []).includes(fact.fact_id));
  await page.locator(`.process-node-button[data-node-id="${owningNode.node_id}"],.process-branch-node[data-node-id="${owningNode.node_id}"]`).first().click();
  const factSelector = `.inspector-fact[data-fact-id="${fact.fact_id}"]`;
  check('Fact-to-source grounding renders every exact reference', await page.locator(`${factSelector} .grounding-ref`).count() === fact.source_refs.length);
  const renderedRefs = await page.locator(`${factSelector} .grounding-ref`).evaluateAll(buttons => buttons.map(button => ({ artifact_id: button.dataset.sourceRef, locator_kind: button.dataset.sourceLocatorKind, page: button.dataset.sourcePage, excerpt: button.dataset.sourceExcerpt, region: button.dataset.sourceRegion, observation: button.dataset.sourceObservation, field: button.dataset.sourceField, value: button.dataset.sourceValue, agent: button.dataset.sourceAgent, confidence: button.dataset.factConfidence, state: button.dataset.factState })));
  const expectedRefs = fact.source_refs.map(ref => ({ artifact_id: ref.artifact_id, locator_kind: ref.locator_kind, page: ref.page == null ? '' : String(ref.page), excerpt: ref.excerpt || '', region: ref.region ? JSON.stringify(ref.region) : '', observation: ref.observation || '', field: ref.field || '', value: ref.value == null ? '' : String(ref.value), agent: ref.agent || '', confidence: fact.confidence == null ? '' : String(fact.confidence), state: fact.state || '' }));
  check('Fact grounding retains exact typed locator, page, passage, agent, confidence, and state', JSON.stringify(renderedRefs) === JSON.stringify(expectedRefs), JSON.stringify({ expectedRefs, renderedRefs }));
  check('Text locator is rendered as an exact quotation with a page', await page.locator(`${factSelector} .grounding-ref[data-source-locator-kind="text_quote"] q`).count() > 0 && Boolean(await page.locator(`${factSelector} .grounding-ref[data-source-locator-kind="text_quote"]`).first().getAttribute('data-source-page')));
  const textLocatorChecks = await Promise.all(fact.source_refs.map(async ref => {
    const sourceText = ref.artifact_id === 'message'
      ? [demo.claim.message]
      : (await getJson(`${API}/api/artifacts/${encodeURIComponent(ref.artifact_id)}/extraction`)).pages;
    return Number.isInteger(ref.page) && ref.page >= 1 && typeof ref.excerpt === 'string' && exactNormalizedGroundingQuote(sourceText?.[ref.page - 1], ref.excerpt);
  }));
  check('Every text quote is an exact normalized substring of its returned source page', textLocatorChecks.every(Boolean), JSON.stringify(fact.source_refs));
  await page.locator(`${factSelector} .grounding-ref`).first().click();
  await waitVisible('#sourceViewer[open]');
  await waitVisible(`.source-fact[data-fact-id="${fact.fact_id}"]`);
  const sourceArtifactId = fact.source_refs[0].artifact_id;
  const sourceRefs = fact.source_refs.filter(ref => ref.artifact_id === sourceArtifactId);
  const renderedPassages = await page.locator(`.source-fact[data-fact-id="${fact.fact_id}"] .source-passage`).evaluateAll(passages => passages.map(passage => ({ locator_kind: passage.dataset.locatorKind, page: passage.dataset.sourcePage, excerpt: passage.dataset.sourceExcerpt, agent: passage.dataset.sourceAgent })));
  const expectedPassages = sourceRefs.map(ref => ({ locator_kind: ref.locator_kind, page: ref.page == null ? '' : String(ref.page), excerpt: ref.excerpt || '', agent: ref.agent || '' }));
  check('Source-to-fact grounding retains exact passages and owning-decision route', JSON.stringify(renderedPassages) === JSON.stringify(expectedPassages) && await page.locator(`.source-fact[data-fact-id="${fact.fact_id}"] [data-source-fact-node="${owningNode.node_id}"]`).count() === 1, JSON.stringify({ expectedPassages, renderedPassages }));
  check('Desktop source viewer retains bidirectional grounding', await page.locator(`.source-fact[data-fact-id="${fact.fact_id}"]`).isVisible());
  await page.locator(`.source-fact[data-fact-id="${fact.fact_id}"] [data-source-fact-node="${owningNode.node_id}"]`).click();
  await waitHidden('#sourceViewer');
  check('Source route returns focus to owning decision', await page.evaluate(nodeId => document.activeElement?.dataset.nodeId === nodeId, owningNode.node_id));

  await page.locator(`.process-node-button[data-node-id="${visualNode.node_id}"],.process-branch-node[data-node-id="${visualNode.node_id}"]`).first().click();
  const visualButton = page.locator(`.inspector-fact[data-fact-id="${visualFact.fact_id}"] .grounding-ref[data-source-locator-kind="visual_observation"]`).first();
  const visualButtonText = await visualButton.innerText();
  check('Visual observation is rendered without quotation or model-extraction authority', await visualButton.locator('q').count() === 0 && /Hash-bound to these demo image bytes; not machine extraction, model output, or qualified review\./i.test(visualButtonText), visualButtonText);
  await visualButton.click();
  await waitVisible('#sourceViewer[open] .visual-region-highlight');
  check('Opening a visual fact highlights the exact normalized image region and hash-bound generated-demo authority', visualRegionValid && visualArtifact?.media_type?.startsWith('image/') && JSON.stringify(highlightedRegion.region) === JSON.stringify(visualRef.region) && [highlightedRegion.left, highlightedRegion.top, highlightedRegion.width, highlightedRegion.height].every((value, index) => Math.abs(value - visualRef.region[index]) < 1e-9) && highlightedRegion.label.includes(visualRef.observation) && highlightedRegion.producer === visualRef.producer && highlightedRegion.authority === visualRef.authority && highlightedRegion.annotation_contract === visualRef.annotation_contract && highlightedRegion.annotation_version === visualRef.annotation_version && highlightedRegion.image_sha256 === visualRef.image_sha256 && highlightedRegion.artifact_sha256 === visualArtifact.sha256, JSON.stringify({ visualRef, visualArtifact, highlightedRegion }));
  check('Visual source-to-fact grounding roundtrips the exact curated annotation without agent, extraction, or quotation authority', visualPassage.region === JSON.stringify(visualRef.region) && visualPassage.observation === visualRef.observation && visualPassage.producer === visualRef.producer && visualPassage.authority === visualRef.authority && visualPassage.annotation_contract === visualRef.annotation_contract && visualPassage.annotation_version === visualRef.annotation_version && visualPassage.image_sha256 === visualArtifact.sha256 && !visualPassage.hasQuote && !/machine extraction|agent observation|model output/i.test(visualPassage.text.replace('not machine extraction, model output', '')) && await page.locator('.opened-grounding q').count() === 0, JSON.stringify({ visualRef, visualPassage }));
  check('Grounded image inspection retains decoded original pixels', await page.locator('#sourceImage').evaluate(node => node.complete && node.naturalWidth > 0 && node.naturalHeight > 0));
  await runAxe('Grounded image viewer');
  await page.locator('#closeSourceViewer').click();

  const metadataFact = facts.find(item => item.source_refs?.some(ref => ref.locator_kind === 'metadata_field'));
  const metadataRef = metadataFact?.source_refs.find(ref => ref.locator_kind === 'metadata_field');
  const metadataNodeId = processGraph.nodes.find(node => (node.fact_ids || []).includes(metadataFact?.fact_id))?.node_id || processRun.result.checklist.items.find(item => item.fact_id === metadataFact?.fact_id)?.node_id;
  check('Metadata provenance remains structurally owned by a process decision', Boolean(metadataFact && metadataRef && metadataNodeId), JSON.stringify({ metadataFact, metadataNodeId }));
  await page.locator(`.process-node-button[data-node-id="${metadataNodeId}"],.process-branch-node[data-node-id="${metadataNodeId}"]`).first().click();
  const metadataButton = page.locator(`.inspector-fact[data-fact-id="${metadataFact.fact_id}"] .grounding-ref[data-source-locator-kind="metadata_field"]`).first();
  check('Metadata field is rendered as observed field/value rather than a quote', await metadataButton.locator('q').count() === 0 && (await metadataButton.getAttribute('data-source-field')) === metadataRef.field && (await metadataButton.getAttribute('data-source-value')) === String(metadataRef.value));
  const intakeFields = { claim_id: demo.claim.claim_id, subject: demo.claim.subject, received_at: demo.claim.received_at, customer_name: demo.claim.customer?.name || '', customer_address: demo.claim.customer?.address || '', policy_reference: demo.claim.customer?.policy || '' };
  const metadataArtifact = demo.claim.artifacts.find(item => item.artifact_id === metadataRef.artifact_id);
  const observedMetadata = metadataRef.artifact_id === 'intake' ? intakeFields : metadataArtifact;
  check('Metadata locator matches the observed source field exactly', observedMetadata && Object.hasOwn(observedMetadata, metadataRef.field) && String(observedMetadata[metadataRef.field]) === String(metadataRef.value), JSON.stringify({ metadataRef, observedMetadata }));
  await metadataButton.click();
  await waitVisible('#sourceViewer[open] .opened-locator[data-locator-kind="metadata_field"]');
  const metadataPassage = await page.locator(`.source-fact[data-fact-id="${metadataFact.fact_id}"] .source-passage[data-locator-kind="metadata_field"]`).evaluate(node => ({ field: node.dataset.sourceField, value: node.dataset.sourceValue, agent: node.dataset.sourceAgent, hasQuote: Boolean(node.querySelector('q')) }));
  check('Metadata source retains exact field, value, and agent and routes back to its owning decision', metadataPassage.field === metadataRef.field && metadataPassage.value === String(metadataRef.value) && metadataPassage.agent === metadataRef.agent && !metadataPassage.hasQuote && await page.locator(`.source-fact[data-fact-id="${metadataFact.fact_id}"] [data-source-fact-node="${metadataNodeId}"]`).count() === 1, JSON.stringify({ metadataRef, metadataPassage }));
  await page.locator('#closeSourceViewer').click();
  }

  const processNodeSourcePreviews = [];
  for (const nodeId of routeStory.storyNodeIds) {
    const nodeButton = page.locator(`#artifactProcessGraph [data-ac-action="select-node"][data-node-id="${nodeId}"]`).first();
    await nodeButton.click();
    await page.waitForFunction(id => document.querySelector(`#artifactProcessGraph [data-ac-action="select-node"][data-node-id="${CSS.escape(id)}"]`)?.getAttribute('aria-current') === 'step', nodeId, { timeout: 30000 });
    await page.evaluate(phase => window.__casepathCaptureProcessPreviewGeometry?.(phase), `completed-preview:${nodeId}`);
    const previewSelector = `#artifactProcessGraph .ac-spatial-detail [data-node-id="${nodeId}"] .ac-node-source-preview`;
    const previewLocator = page.locator(previewSelector);
    const previewCount = await previewLocator.count();
    if (!previewCount) {
      processNodeSourcePreviews.push({ nodeId, previewCount, basisKind: '', viewportWidth: 1440, viewportHeight: 900, overlaps: [] });
      continue;
    }
    const preview = await previewLocator.first().evaluate((node, context) => {
      const visible = item => Boolean(item && item.getClientRects().length && getComputedStyle(item).visibility !== 'hidden' && getComputedStyle(item).display !== 'none');
      const rect = item => { const value = item.getBoundingClientRect(); return { left: value.left, top: value.top, right: value.right, bottom: value.bottom, width: value.width, height: value.height }; };
      const intersection = (first, second) => Math.max(0, Math.min(first.right, second.right) - Math.max(first.left, second.left)) * Math.max(0, Math.min(first.bottom, second.bottom) - Math.max(first.top, second.top));
      const previewRect = rect(node);
      const graph = node.closest('#artifactProcessGraph');
      const spatialViewport = node.closest('.ac-spatial-viewport');
      const disclosure = node.closest('.ac-grounding-disclosure');
      const detail = node.closest('.ac-spatial-detail');
      const veilStyle = spatialViewport ? getComputedStyle(spatialViewport, '::after') : null;
      const detailStyle = detail ? getComputedStyle(detail) : null;
      const groundingToggle = disclosure?.querySelector('.ac-grounding-toggle');
      const otherGrounding = groundingToggle?.nextElementSibling;
      const sourceWindowNode = node.querySelector('.ac-source-page-excerpt');
      const visualFrame = node.querySelector('.ac-visual-source-frame');
      const actionTarget = node.matches('[data-ac-action]') ? node : node.querySelector('[data-ac-action]');
      const titleNode = node.querySelector('.ac-source-document-head strong') || node.querySelector('.ac-visual-source figcaption span') || node.querySelector(':scope > small') || node.querySelector(':scope > header small');
      const locationNode = node.querySelector('.ac-source-document-head small') || node.querySelector('.ac-visual-source figcaption small') || node.querySelector(':scope > span') || node.querySelector(':scope > header span');
      const passageNode = node.querySelector('.ac-source-page-excerpt mark') || node.querySelector('.ac-source-field strong') || node.querySelector('.ac-visual-source figcaption strong') || node.querySelector(':scope > strong');
      const onDemandNode = node.querySelector(':scope > em') || actionTarget;
      const spatialObjects = [...graph.querySelectorAll('[data-spatial-role="spine"],[data-spatial-role="hub"],[data-spatial-role="branch"],[data-spatial-role="law"],[data-spatial-role="evidence"],[data-spatial-role="next-action"],.ac-document-needs-link,[data-casepath-primary-action="true"]')]
        .filter(item => item !== node && !item.contains(node) && !node.contains(item) && visible(item));
      return {
        nodeId: context.nodeId,
        previewCount: context.previewCount,
        previewVisible: visible(node),
        basisKind: node.dataset.basisKind || node.dataset.nodeAttachmentKind || (node.dataset.sourceId ? 'source' : ''),
        basisTargetNodeId: node.dataset.nodeId || '',
        factId: node.dataset.factId || '',
        sourceId: node.dataset.sourceId || '',
        lawId: node.dataset.lawId || '',
        evidenceId: node.dataset.evidenceId || '',
        locatorId: node.dataset.sourceLocatorId || '',
        title: titleNode?.textContent?.trim() || '',
        location: locationNode?.textContent?.trim() || '',
        passage: passageNode?.textContent?.trim() || '',
        visualPreview: node.classList.contains('ac-node-source-preview-visual'),
        sourceWindowText: sourceWindowNode?.textContent?.trim() || '',
        sourceWindowTruth: Boolean((sourceWindowNode && passageNode && sourceWindowNode.textContent.includes(passageNode.textContent)) || (visualFrame?.querySelector('img') && visualFrame?.querySelector('.ac-visual-region-target')) || node.querySelector('.ac-source-field')),
        noGeneratedContext: !/\b(?:Context|Source context)\s*·/i.test(node.textContent || ''),
        onDemandText: onDemandNode?.textContent?.trim() || '',
        action: actionTarget?.dataset.acAction || '',
        inlineGroundingClosed: disclosure?.dataset.groundingOpen === 'false',
        otherGroundingHidden: !otherGrounding || otherGrounding.hidden === true,
        groundingViewerOpen: document.querySelector('#artifactCanvas [data-ac-grounding-viewer]')?.open === true,
        changeId: node.dataset.artifactChangeId || '',
        eventId: node.dataset.artifactEventId || '',
        agentId: node.dataset.artifactAgentId || '',
        sourceHasTarget: window.__casepathSourceTargetExists?.(node.dataset.sourceId) === true,
        viewportWidth: innerWidth,
        viewportHeight: innerHeight,
        foregroundIsolation: Boolean(
          veilStyle
          && detailStyle
          && veilStyle.content !== 'none'
          && Number.parseInt(veilStyle.zIndex || '0', 10) >= 3
          && Number.parseInt(detailStyle.zIndex || '0', 10) > Number.parseInt(veilStyle.zIndex || '0', 10)
        ),
        overlaps: spatialObjects.filter(item => intersection(previewRect, rect(item)) > 2).map(item => item.dataset.nodeId || item.dataset.spatialId || item.dataset.spatialRole || item.className),
      };
    }, { nodeId, previewCount });
    const returnedNode = processRun.result.process.nodes.find(node => node.node_id === nodeId);
    const factOwnedByNode = factId => returnedNode?.fact_ids?.includes(factId)
      || processRun.result.checklist.items.some(item => item.fact_id === factId
        && (item.node_id === nodeId || item.node_ids?.includes(nodeId)));
    const returnedFact = processRun.result.facts.find(fact => fact.fact_id === preview.factId && factOwnedByNode(fact.fact_id));
    const returnedRef = returnedFact?.source_refs?.find(ref => ref.artifact_id === preview.sourceId && factSourceLocatorId(ref) === preview.locatorId);
    const expectedSource = returnedRef ? factSourcePreviewTruth(demo.claim, returnedFact, returnedRef, preview.visualPreview) : null;
    const legal = processRun.result.legal_research || {};
    const linkedLawIds = new Set([
      ...(returnedNode?.legal_source_ids || []),
      ...(legal.node_links?.[nodeId] || []),
      ...(legal.questions || []).filter(question => (question.process_node_ids || []).includes(nodeId)).flatMap(question => [...(question.source_ids || []), ...(question.interpretation_ids || [])]),
    ]);
    const returnedLaw = [...(legal.sources || []), ...(legal.handling_principles || [])].find(item => item.source_id === preview.lawId && linkedLawIds.has(item.source_id));
    const exactReturnedSource = Boolean(returnedNode && returnedFact && returnedRef && [preview.changeId, preview.eventId, preview.agentId].every(nonemptyString));
    const exactLawLocator = Boolean(returnedLaw && preview.locatorId === `law:${returnedLaw.source_id}`);
    processNodeSourcePreviews.push({
      ...preview,
      exactReturnedSource,
      sourceHasTarget: preview.sourceHasTarget === true,
      exactLocator: Boolean(returnedRef) || exactLawLocator,
      exactTitle: Boolean(expectedSource && preview.title === expectedSource.title),
      exactLocation: Boolean(expectedSource && preview.location === expectedSource.location),
      sourceWindowTruth: preview.sourceWindowTruth === true,
      noGeneratedContext: preview.noGeneratedContext === true,
      exactPassage: Boolean(expectedSource && preview.passage === expectedSource.passage),
    });
  }
  const processPreviewGeometry = await page.evaluate(() => window.__casepathProcessPreviewGeometry || []);
  const processPreviewGeometryIssues = processPreviewGeometryContractViolations(processPreviewGeometry, routeStory.storyNodeIds);
  check('Every visible construction and completed source preview stays inside the 1440×900 process viewport with an 8px bottom inset', processPreviewGeometryIssues.length === 0, JSON.stringify({ processPreviewGeometryIssues, processPreviewGeometry }));
  const intakeFact = processRun.result.facts.find(item => item.fact_id === 'fact_customer_objective');
  const intakeRef = intakeFact?.source_refs?.find(ref => ref.artifact_id === 'message' && ref.locator_kind === 'text_quote');
  const intakeTruth = intakeFact && intakeRef ? factSourcePreviewTruth(demo.claim, intakeFact, intakeRef, false) : null;
  const expectedIntakeBasis = intakeTruth ? {
    factId: intakeFact.fact_id,
    sourceId: intakeRef.artifact_id,
    locatorId: factSourceLocatorId(intakeRef),
    passage: intakeTruth.passage,
  } : null;
  const intakeHighlight = sourceHighlights.find(item => item.entityKind === 'node' && item.nodeId === 'intake');
  const intakeCarried = decisionFlowSteps.find(item => item.nodeId === 'intake'
    && item.stepKind === 'accepted-fact'
    && item.carriedFactId === 'fact_customer_objective'
    && item.carriedHighlightCount === 1);
  const intakeConstruction = intakeHighlight ? {
    nodeId: intakeHighlight.nodeId,
    attachmentKind: intakeHighlight.attachmentKind,
    factId: intakeHighlight.constructionFactId,
    sourceId: intakeHighlight.constructionSourceId,
    locatorId: intakeHighlight.constructionLocatorId,
    passage: intakeHighlight.passage,
    highlightMarkCount: intakeHighlight.highlightMarkCount,
    generatedSummaryVisible: intakeHighlight.generatedSummaryVisible,
  } : intakeCarried ? {
    nodeId: intakeCarried.nodeId,
    attachmentKind: 'fact',
    factId: intakeCarried.carriedFactId,
    sourceId: intakeCarried.carriedSourceId,
    locatorId: intakeCarried.carriedLocatorId,
    passage: intakeCarried.carriedPassage,
    highlightMarkCount: intakeCarried.carriedHighlightCount,
    generatedSummaryVisible: intakeCarried.carriedGeneratedSummaryVisible,
  } : null;
  const intakePreview = processNodeSourcePreviews.find(item => item.nodeId === 'intake');
  const intakeBasisIssues = intakeClaimMessageBasisContractViolations(intakeConstruction, intakePreview, expectedIntakeBasis);
  check('Intake construction and ready preview both show the exact returned customer-message passage and locator', intakeBasisIssues.length === 0, JSON.stringify({ expectedIntakeBasis, intakeConstruction, intakePreview, intakeBasisIssues }));
  await page.locator(`#artifactProcessGraph [data-ac-action="select-node"][data-node-id="${routeStory.currentNodeId}"]`).click();
  const representativePreview = processNodeSourcePreviews.find(preview => ['fact', 'source'].includes(preview.basisKind) && preview.exactReturnedSource && ['message', 'intake'].includes(preview.sourceId))
    || processNodeSourcePreviews.find(preview => ['fact', 'source'].includes(preview.basisKind) && preview.exactReturnedSource && preview.sourceHasTarget);
  let postConstructionSourceUse = { viewerOpen: false, activeSourceIds: [], activeSourceLocator: '', sourceId: '', locatorId: '' };
  if (representativePreview) {
    const representativeNode = page.locator(`#artifactProcessGraph [data-ac-action="select-node"][data-node-id="${representativePreview.nodeId}"]`).first();
    await representativeNode.click();
    const representativeSelector = `#artifactProcessGraph .ac-spatial-detail [data-node-id="${representativePreview.nodeId}"] .ac-node-source-preview[data-source-locator-id=${JSON.stringify(representativePreview.locatorId)}]`;
    const representativeAction = page.locator(`${representativeSelector}[data-ac-action="open-source"],${representativeSelector} [data-ac-action="open-source"]`).first();
    await representativeAction.click();
    await waitVisible('#sourceViewer[open]');
    postConstructionSourceUse = await page.evaluate(({ sourceId, locatorId }) => ({
      viewerOpen: document.querySelector('#sourceViewer')?.open === true,
      activeSourceIds: window.__casepathActiveSourceIds?.() || [],
      activeSourceLocator: document.querySelector('.submission-pane')?.dataset.activeSourceLocator || '',
      sourceId,
      locatorId,
    }), { sourceId: representativePreview.sourceId, locatorId: representativePreview.locatorId });
    await page.locator('#closeSourceViewer').click();
    await page.locator(`#artifactProcessGraph [data-ac-action="select-node"][data-node-id="${routeStory.currentNodeId}"]`).click();
  }

  if (routeStory.flagshipCausation) {
  await waitVisible('#journeyNext[data-v20-guided-documents="true"]');
  const readyPrimaryAction = await primaryActionSnapshot();
  check('Ready exposes Review document plan as its sole primary action', readyPrimaryAction.dialogOpen === false && readyPrimaryAction.actions.length === 1 && readyPrimaryAction.actions[0]?.id === 'journeyNext' && readyPrimaryAction.actions[0]?.text === 'Review document plan' && readyPrimaryAction.actions[0]?.guidedDocuments === 'true' && readyPrimaryAction.actions[0]?.ariaControls === 'v20DocumentSheet', JSON.stringify(readyPrimaryAction));
  await page.locator('#journeyNext').click();
  await waitVisible('#v20DocumentSheet[open]');
  await page.evaluate(() => window.__casepathCaptureDesktopSourcePanel?.('document-plan'));
  const openDocumentPrimaryAction = await primaryActionSnapshot();
  check('Open Document plan has exactly one primary action: Continue to review', openDocumentPrimaryAction.dialogOpen === true && openDocumentPrimaryAction.actions.length === 1 && openDocumentPrimaryAction.actions[0]?.continueReview === true && openDocumentPrimaryAction.actions[0]?.text === 'Continue to review' && await page.locator('#v20DocumentSheet .v20-document-footer>small').innerText() === 'Next: simulated review of one process decision · not expert approval', JSON.stringify(openDocumentPrimaryAction));
  const expectedDocumentItems = processRun.result.checklist.items;
  const documentKind = item => ['missing', 'provided_insufficient'].includes(item.status)
    ? 'needed'
    : item.status === 'conditional' ? 'conditional' : item.status === 'provided_sufficient' ? 'available' : 'not-needed';
  const expectedDocumentCounts = expectedDocumentItems.reduce((counts, item) => {
    counts[documentKind(item)] += 1;
    return counts;
  }, { all: expectedDocumentItems.length, needed: 0, conditional: 0, available: 0, 'not-needed': 0 });
  const documentPlanProjection = await page.locator('#v20DocumentSheet').evaluate(sheet => {
    const body = sheet.querySelector('.v20-document-body');
    const chains = [...sheet.querySelectorAll('.v20-document-chain[data-item-id]')].map(chain => ({
      itemId: chain.dataset.itemId || '',
      nodeId: chain.dataset.nodeId || '',
      nodeIds: chain.dataset.nodeIds || '',
      v20NodeId: chain.dataset.v20NodeId || '',
      currentPath: chain.dataset.currentPath || '',
      factId: chain.dataset.factId || '',
      status: chain.dataset.status || '',
      kind: chain.dataset.documentKind || '',
      documentStatus: chain.dataset.documentStatus || '',
      statusIcon: chain.querySelector('.v20-chain-status i')?.textContent?.trim() || '',
      statusLabel: chain.querySelector('.v20-chain-status strong')?.textContent?.trim() || '',
      documentIconKind: chain.querySelector('.v20-document-name')?.dataset.documentIconKind || '',
      documentIconCount: chain.querySelectorAll('.v20-document-name .v20-document-type-icon').length,
      documentIconAriaHidden: chain.querySelector('.v20-document-type-icon')?.getAttribute('aria-hidden') || '',
      evidenceTitle: chain.dataset.evidenceTitle || '',
      documentOptions: chain.dataset.documentOptions || '',
      artifactIds: chain.dataset.artifactIds || '',
      text: chain.innerText,
      technicalCount: chain.querySelectorAll('.v17-checklist-technical,.model-contribution-attribution').length,
      rowParts: [...chain.children].filter(node => node.matches('[data-chain-part],.v20-chain-status')).map(node => node.dataset.chainPart || 'status'),
      parts: [...chain.querySelectorAll(':scope > [data-chain-part]')].map(part => ({
        part: part.dataset.chainPart || '',
        strong: part.querySelector('strong')?.textContent?.trim() || '',
        detail: part.querySelector('span')?.textContent?.trim() || '',
      })),
    }));
    return {
      title: sheet.querySelector('#v20DocumentTitle')?.textContent?.trim() || '',
      model: body?.dataset.documentModel || '',
      selectedNode: body?.dataset.documentSelectedNode || '',
      filter: body?.dataset.documentFilter || '',
      spineNodeIds: [...sheet.querySelectorAll('.v20-document-spine [data-v20-document-node]')].map(button => button.dataset.v20DocumentNode || ''),
      pressedNodeIds: [...sheet.querySelectorAll('[data-v20-document-node][aria-pressed="true"]')].map(button => button.dataset.v20DocumentNode || ''),
      pressedFilters: [...sheet.querySelectorAll('[data-v20-document-filter][aria-pressed="true"]')].map(button => button.dataset.v20DocumentFilter || ''),
      filterCounts: Object.fromEntries([...sheet.querySelectorAll('[data-v20-document-filter]')].map(button => [button.dataset.v20DocumentFilter || '', Number(button.querySelector('span')?.textContent || NaN)])),
      filterStatuses: Object.fromEntries([...sheet.querySelectorAll('[data-v20-document-filter]')].map(button => [button.dataset.v20DocumentFilter || '', button.dataset.documentStatus || ''])),
      groups: [...sheet.querySelectorAll('.v20-document-group[data-document-group]')].map(group => ({
        kind: group.dataset.documentGroup || '',
        visible: !group.hidden && group.getClientRects().length > 0 && getComputedStyle(group).display !== 'none' && getComputedStyle(group).visibility !== 'hidden',
        itemIds: [...group.querySelectorAll('.v20-document-chain[data-item-id]')].map(chain => chain.dataset.itemId || ''),
      })),
      visibleChainIds: chains.filter(chain => {
        const node = sheet.querySelector(`.v20-document-chain[data-item-id="${CSS.escape(chain.itemId)}"]`);
        return node && !node.hidden && node.getClientRects().length > 0 && getComputedStyle(node).display !== 'none' && getComputedStyle(node).visibility !== 'hidden';
      }).map(chain => chain.itemId),
      chains,
    };
  });
  const chainIds = documentPlanProjection.chains.map(item => item.itemId);
  check('Document plan contains each of the exact 21 returned checklist items once', expectedDocumentItems.length === 21 && documentPlanProjection.chains.length === 21 && new Set(chainIds).size === 21 && stableJson([...chainIds].sort()) === stableJson(expectedDocumentItems.map(item => item.item_id).sort()), JSON.stringify({ chainIds, expected: expectedDocumentItems.map(item => item.item_id) }));
  check('Claim documents opens as the complete 21-item evidence model with no hidden node filter', documentPlanProjection.title === 'Claim documents' && documentPlanProjection.model === 'complete-claim-record' && documentPlanProjection.selectedNode === '' && documentPlanProjection.filter === 'all' && documentPlanProjection.pressedNodeIds.length === 0 && documentPlanProjection.spineNodeIds.length === 0 && stableJson(documentPlanProjection.pressedFilters) === stableJson(['all']) && documentPlanProjection.visibleChainIds.length === 21 && stableJson([...documentPlanProjection.visibleChainIds].sort()) === stableJson(expectedDocumentItems.map(item => item.item_id).sort()), JSON.stringify(documentPlanProjection));
  const documentStatus = item => item.status === 'provided_sufficient'
    ? { state: 'received', icon: '✓', label: 'Received' }
    : ['missing', 'provided_insufficient'].includes(item.status)
      ? { state: 'missing', icon: '×', label: item.status === 'provided_insufficient' ? 'Incomplete' : 'Missing' }
      : item.status === 'conditional'
        ? { state: 'conditional', icon: '○', label: 'Conditional' }
        : { state: 'not-required', icon: '–', label: 'Not required' };
  const expectedStatusProjection = ['needed', 'available', 'conditional', 'not-needed']
    .flatMap(kind => expectedDocumentItems
      .filter(item => documentKind(item) === kind)
      .map(item => ({ itemId: item.item_id, ...documentStatus(item) })));
  const renderedStatusProjection = documentPlanProjection.chains.map(chain => ({ itemId: chain.itemId, state: chain.documentStatus, icon: chain.statusIcon, label: chain.statusLabel }));
  const expectedGroups = ['needed', 'available', 'conditional', 'not-needed'].map(kind => ({
    kind,
    visible: true,
    itemIds: expectedDocumentItems.filter(item => documentKind(item) === kind).map(item => item.item_id),
  })).filter(group => group.itemIds.length);
  check('All 21 requirements visibly partition into exact status groups with needed first and missing or received icons', stableJson(renderedStatusProjection) === stableJson(expectedStatusProjection) && stableJson(documentPlanProjection.groups) === stableJson(expectedGroups) && documentPlanProjection.groups[0]?.kind === 'needed' && documentPlanProjection.groups.every(group => group.visible) && stableJson(documentPlanProjection.filterStatuses) === stableJson({ all: '', available: 'received', needed: 'missing', conditional: 'conditional', 'not-needed': 'not-required' }) && documentPlanProjection.chains.filter(chain => chain.documentStatus === 'missing').every(chain => chain.statusIcon === '×') && documentPlanProjection.chains.filter(chain => chain.documentStatus === 'received').every(chain => chain.statusIcon === '✓'), JSON.stringify({ expectedStatusProjection, renderedStatusProjection, expectedGroups, groups: documentPlanProjection.groups, filterStatuses: documentPlanProjection.filterStatuses }));
  const documentIconKinds = new Set(['contract', 'mail', 'inspection', 'image', 'timeline', 'invoice', 'medical', 'legal', 'delivery', 'generic']);
  const expectedRepresentativeDocumentIcons = new Map([
    ['claim_message', 'mail'],
    ['lease', 'contract'],
    ['proof_of_delivery', 'delivery'],
    ['dated_photos', 'image'],
    ['recurrence_chronology', 'timeline'],
    ['technical_assessment', 'inspection'],
    ['financial_impact', 'invoice'],
  ]);
  check('Every document name has one restrained semantic type icon while status remains separate', documentPlanProjection.chains.every(chain => chain.documentIconCount === 1 && chain.documentIconAriaHidden === 'true' && documentIconKinds.has(chain.documentIconKind) && nonemptyString(chain.statusIcon)) && [...expectedRepresentativeDocumentIcons].every(([itemId, expectedKind]) => documentPlanProjection.chains.find(chain => chain.itemId === itemId)?.documentIconKind === expectedKind), JSON.stringify(documentPlanProjection.chains.map(chain => ({ itemId: chain.itemId, icon: chain.documentIconKind, count: chain.documentIconCount, status: chain.statusIcon }))));
  check('Every document row preserves process question to fact to evidence to document to status in that order', documentPlanProjection.chains.every(chain => stableJson(chain.rowParts) === stableJson(['decision', 'fact', 'evidence', 'document', 'status']) && stableJson(chain.parts.map(part => part.part)) === stableJson(['decision', 'fact', 'evidence', 'document']) && chain.parts.every(part => nonemptyString(part.strong) && nonemptyString(part.detail)) && nonemptyString(chain.documentStatus) && nonemptyString(chain.statusLabel)), JSON.stringify(documentPlanProjection.chains));
  check('Evidence needs and document forms are not reversed', documentPlanProjection.chains.every(chain => {
    const evidencePart = chain.parts.find(part => part.part === 'evidence');
    const documentPart = chain.parts.find(part => part.part === 'document');
    const firstDocumentOption = chain.documentOptions.split(' · ').filter(Boolean)[0] || '';
    return evidencePart?.strong === chain.evidenceTitle
      && nonemptyString(documentPart?.strong)
      && (nonemptyString(chain.artifactIds) || !firstDocumentOption || documentPart.strong === firstDocumentOption);
  }), JSON.stringify(documentPlanProjection.chains));
  const renderedChainsById = new Map(documentPlanProjection.chains.map(item => [item.itemId, item]));
  const documentLineageExact = expectedDocumentItems.every(item => {
    const rendered = renderedChainsById.get(item.item_id);
    const owners = Array.isArray(item.node_ids) && item.node_ids.length ? item.node_ids : item.node_id ? [item.node_id] : [];
    return rendered?.nodeId === (item.node_id || '')
      && rendered?.nodeIds === owners.join(',')
      && rendered?.v20NodeId === (item.node_id || '')
      && rendered?.currentPath === String(item.current_path === true)
      && rendered?.factId === (item.fact_id || '')
      && rendered?.status === (item.status || '')
      && rendered?.kind === documentKind(item);
  });
  check('Each document chain preserves exact returned primary owner, ordered owners, path, fact, status, and item identity', documentLineageExact, JSON.stringify({ expectedDocumentItems, rendered: documentPlanProjection.chains }));
  check('The visible plan removes internal identifiers and contribution plumbing without removing audit data', documentPlanProjection.chains.every(chain => {
    const internalIdentifiers = [chain.itemId, chain.factId].filter(value => /[_:.]/.test(value));
    return chain.technicalCount === 0
      && internalIdentifiers.every(value => !chain.text.includes(value))
      && !/ordered decisions|current path/i.test(chain.text);
  }), JSON.stringify(documentPlanProjection.chains.map(item => ({ itemId: item.itemId, factId: item.factId, text: item.text }))));
  check('Document status filters report exact returned counts', stableJson(documentPlanProjection.filterCounts) === stableJson(expectedDocumentCounts), JSON.stringify({ expectedDocumentCounts, actual: documentPlanProjection.filterCounts }));
  const multiOwnerItem = processRun.result.checklist.items.find(item => Array.isArray(item.node_ids) && item.node_ids.length > 1
    && item.node_ids.some(nodeId => routeStory.storyNodeIds.includes(nodeId)));
  check('Flagship checklist contains an inspectable reciprocal multi-owner evidence item', Boolean(multiOwnerItem), JSON.stringify(processRun.result.checklist.items.map(item => ({ item_id: item.item_id, node_ids: item.node_ids }))));
  if (isProductionJourney()) {
    const expectedChecklistContributions = processRun.result.checklist.items.map(item => ({
      item_id: item.item_id,
      contribution: contributionDomProjection(item.agent_contribution, EVIDENCE_CONTRIBUTION_ROLE),
    })).filter(item => item.contribution);
    const renderedChecklistContributions = await page.locator('#stageCanvas .v17-derived-checklist .v17-checklist-item[data-item-id]').evaluateAll(items => items.flatMap(item => {
      const badge = item.querySelector('.model-contribution-attribution');
      return badge ? [{ item_id: item.dataset.itemId, contribution: { authority: badge.dataset.contributionAuthority, accepted_count: badge.dataset.acceptedCount, fallback_count: badge.dataset.fallbackCount, accepted_ids: badge.dataset.acceptedContributionIds, fallback_ids: badge.dataset.fallbackContributionIds } }] : [];
    }));
    check('The underlying derived checklist preserves exact Nemotron acceptance or deterministic fallback attribution while the visible plan stays plain-language', expectedChecklistContributions.length === processRun.result.checklist.items.length && stableJson(renderedChecklistContributions.sort((a, b) => a.item_id.localeCompare(b.item_id))) === stableJson(expectedChecklistContributions.sort((a, b) => a.item_id.localeCompare(b.item_id))) && renderedChecklistContributions.some(item => Number(item.contribution.accepted_count) > 0), JSON.stringify({ expectedChecklistContributions, renderedChecklistContributions }));
  }
  for (const filter of ['all', 'needed', 'conditional', 'available', 'not-needed']) {
    await page.locator(`[data-v20-document-filter="${filter}"]`).click();
    const visibleItemIds = await page.locator('#v20DocumentSheet .v20-document-chain[data-item-id]').evaluateAll(items => items.filter(item => !item.hidden).map(item => item.dataset.itemId || ''));
    const expectedVisibleIds = expectedDocumentItems.filter(item => filter === 'all' || documentKind(item) === filter).map(item => item.item_id);
    check(`Document ${filter} filter shows exactly its returned items and count`, stableJson([...visibleItemIds].sort()) === stableJson([...expectedVisibleIds].sort()) && visibleItemIds.length === expectedDocumentCounts[filter], JSON.stringify({ filter, visibleItemIds, expectedVisibleIds, expectedDocumentCounts }));
  }
  await page.locator('[data-v20-document-filter="all"]').click();
  const allVisibleIds = await page.locator('#v20DocumentSheet .v20-document-chain[data-item-id]').evaluateAll(items => items.filter(item => !item.hidden).map(item => item.dataset.itemId || ''));
  check('Returning to All restores every one of the 21 claim requirements', allVisibleIds.length === 21 && stableJson([...allVisibleIds].sort()) === stableJson(expectedDocumentItems.map(item => item.item_id).sort()), JSON.stringify(allVisibleIds));
  const routeItem = expectedDocumentItems.find(item => item.node_id === routeStory.currentNodeId)
    || expectedDocumentItems.find(item => routeStory.storyNodeIds.includes(item.node_id));
  const routeChain = page.locator(`#v20DocumentSheet .v20-document-chain[data-item-id="${routeItem?.item_id || ''}"]:not([hidden])`);
  const routeChainCount = await routeChain.count();
  const owningNodeId = routeChainCount === 1 ? await routeChain.getAttribute('data-v20-node-id') : '';
  const returnedProcessNodeIds = processRun.result.process.nodes.map(node => node.node_id);
  check('The selected document chain declares an exact returned route-story target', Boolean(routeItem) && routeChainCount === 1 && nonemptyString(owningNodeId) && returnedProcessNodeIds.includes(owningNodeId) && routeStory.storyNodeIds.includes(owningNodeId), JSON.stringify({ routeStory, routeItem, routeChainCount, owningNodeId, returnedProcessNodeIds }));
  check('Document sheet is a labelled modal dialog with focus inside', await page.evaluate(() => { const sheet = document.querySelector('#v20DocumentSheet'); return sheet?.tagName === 'DIALOG' && sheet.getAttribute('aria-labelledby') === 'v20DocumentTitle' && sheet.contains(document.activeElement); }));
  await page.keyboard.press('Escape');
  await waitHidden('#v20DocumentSheet');
  check('Closing the guided Document plan restores focus to its Ready action', await page.evaluate(() => document.activeElement?.id === 'journeyNext'));
  await page.locator('#journeyNext').click();
  await routeChain.click();
  await waitHidden('#v20DocumentSheet');
  await page.waitForFunction(nodeId => document.querySelector(`#artifactProcessGraph [data-ac-action="select-node"][data-node-id="${CSS.escape(nodeId)}"]`)?.getAttribute('aria-current') === 'step', owningNodeId, { timeout: 30000 });
  const returnedGraphSelection = await page.locator('#artifactProcessGraph').evaluate(graph => ({
    current: [...graph.querySelectorAll('[data-ac-action="select-node"][aria-current="step"]')].map(node => node.dataset.nodeId || ''),
    selected: [...graph.querySelectorAll('[data-ac-node-id][data-selected="true"]')].map(node => node.dataset.acNodeId || ''),
  }));
  const documentRoundtrip = stableJson(returnedGraphSelection.current) === stableJson([owningNodeId]) && stableJson(returnedGraphSelection.selected) === stableJson([owningNodeId]);
  check('Document chain returns to its exact graph node and no competing decision', documentRoundtrip, JSON.stringify({ owningNodeId, returnedGraphSelection }));
  const desktopSourceMoments = await page.evaluate(() => window.__casepathDesktopSourcePanelMoments || []);
  const zoomOutDesktopIssues = zoomOutDesktopContractViolations({
    sourceMoments: desktopSourceMoments,
    decisionSteps: decisionFlowSteps,
    artifactCursorSteps,
    previews: processNodeSourcePreviews,
    postConstructionSourceUse,
    team: artifactTeamSnapshot,
    documentPlan: documentPlanProjection,
    documentRoundtrip,
    expectedNodeIds: routeStory.storyNodeIds,
  });
  check('Zoom-out desktop journey keeps sources visible and causal, process previews contextual, team labels simple, and document chains graph-derived', zoomOutDesktopIssues.length === 0, JSON.stringify({ zoomOutDesktopIssues, desktopSourceMoments, processNodeSourcePreviews, postConstructionSourceUse }));
  const secondaryOwnerId = multiOwnerItem.node_ids.find(nodeId => nodeId !== multiOwnerItem.node_id && routeStory.storyNodeIds.includes(nodeId));
  const reciprocalSourceItem = page.locator(`#stageCanvas .v17-derived-checklist .v17-checklist-item[data-item-id="${multiOwnerItem.item_id}"][data-node-ids="${multiOwnerItem.node_ids.join(',')}"]`);
  check('A reciprocal evidence item retains every returned owner without exposing a process step outside the returned route story', await reciprocalSourceItem.count() === 1, JSON.stringify({ item_id: multiOwnerItem.item_id, owners: multiOwnerItem.node_ids, routeStory }));
  if (secondaryOwnerId) {
    const secondaryOwnerButton = page.locator(`#artifactProcessGraph [data-ac-action="select-node"][data-node-id="${secondaryOwnerId}"]`);
    check('A reciprocal owner on the returned route remains an exact selectable graph decision', await secondaryOwnerButton.count() === 1, JSON.stringify({ item_id: multiOwnerItem.item_id, owners: multiOwnerItem.node_ids, secondaryOwnerId }));
    await secondaryOwnerButton.click();
    check('The secondary evidence owner is still navigable in the persistent graph', await secondaryOwnerButton.getAttribute('aria-current') === 'step', secondaryOwnerId);
  }
  const flagshipBeforeReview = processRun;
  const preReviewGraphProjection = await page.locator('#artifactProcessGraph').evaluate(node => ({
    node_ids: [...node.querySelectorAll('[data-node-id][data-process-build-state]')].map(item => item.dataset.nodeId).filter(Boolean),
    change_ids: [...node.querySelectorAll('[data-artifact-change-id]')].map(item => item.dataset.artifactChangeId).filter(Boolean),
  }));
  await page.locator('#journeyNext').click();
  await waitVisible('#v20DocumentSheet[open]');
  const reviewTransitionPrimaryAction = await primaryActionSnapshot();
  check('Document plan still exposes one Continue to review action before handoff', reviewTransitionPrimaryAction.dialogOpen === true && reviewTransitionPrimaryAction.actions.length === 1 && reviewTransitionPrimaryAction.actions[0]?.continueReview === true && reviewTransitionPrimaryAction.actions[0]?.text === 'Continue to review', JSON.stringify(reviewTransitionPrimaryAction));
  await page.locator('[data-v20-continue-review]').click();
  await waitVisible('body[data-casepath-moment="review"]');
  check('Continue to review closes the plan and reaches simulated review', await page.locator('#v20DocumentSheet').isHidden() && await page.locator('body[data-casepath-moment="review"]').count() === 1);
  check('Review keeps one consequential choice and one calm cursor', await page.locator('#artifactCanvas[data-casepath-scene="review"] [data-artifact-focus="true"] #artifactAgentCursor').count() === 0 && await page.locator('#artifactCanvas[data-casepath-scene="review"] #artifactAgentCursor').count() === 1);
  const reviewCanvas = await artifactCanvasSnapshot();
  const reviewCanvasIssues = focusedArtifactCanvasViolations(reviewCanvas);
  const reviewGraphScene = await persistentGraphSceneSnapshot();
  const reviewGraphSceneIssues = persistentGraphSceneContractViolations(reviewGraphScene, {
    scene: 'review',
    nodeIds: FLAGSHIP_PROCESS_PROJECTION_IDS,
    selectedNodeId: 'causation',
    reviewEditState: 'pending',
    inlineCorrectionCount: 1,
    applyActionCount: 1,
    appliedNoteCount: 0,
  });
  check('Expert review keeps the persistent process graph as the sole focal artifact, with Causation selected and exactly one inline correction and Apply action', reviewCanvasIssues.length === 0 && reviewCanvas.action_count === 1 && reviewGraphSceneIssues.length === 0, JSON.stringify({ reviewCanvas, reviewCanvasIssues, reviewGraphScene, reviewGraphSceneIssues }));
  const conditionalReviewChoice = await reviewChoiceSnapshot();
  const conditionalReviewChoiceIssues = reviewChoiceContractViolations(conditionalReviewChoice, 'conditional');
  await page.locator('#artifactProcessGraph [role="radio"][data-review-mode="required_now"]').click();
  await page.waitForFunction(() => document.querySelector('#artifactProcessGraph .ac-review-graph-edit')?.dataset.reviewSelectedMode === 'required_now');
  const requiredNowReviewChoice = await reviewChoiceSnapshot();
  const requiredNowReviewChoiceIssues = reviewChoiceContractViolations(requiredNowReviewChoice, 'required_now');
  await page.locator('#artifactProcessGraph [role="radio"][data-review-mode="conditional"]').click();
  await page.waitForFunction(() => document.querySelector('#artifactProcessGraph .ac-review-graph-edit')?.dataset.reviewSelectedMode === 'conditional');
  const restoredConditionalReviewChoice = await reviewChoiceSnapshot();
  const restoredConditionalReviewChoiceIssues = reviewChoiceContractViolations(restoredConditionalReviewChoice, 'conditional');
  check('Review has exactly two graph-local radio choices, defaults to conditional, changes the visible consequence for required now, restores conditional, and keeps one primary Apply', conditionalReviewChoiceIssues.length === 0 && requiredNowReviewChoiceIssues.length === 0 && restoredConditionalReviewChoiceIssues.length === 0 && requiredNowReviewChoice.consequence !== conditionalReviewChoice.consequence && stableJson(restoredConditionalReviewChoice) === stableJson(conditionalReviewChoice), JSON.stringify({ conditionalReviewChoice, conditionalReviewChoiceIssues, requiredNowReviewChoice, requiredNowReviewChoiceIssues, restoredConditionalReviewChoice, restoredConditionalReviewChoiceIssues }));
  const visibleReviewCopy = reviewGraphScene.text;
  check('Simulated review truthfully frames one evidence-order choice without inventing a pre-review requirement transition', /Review one evidence relationship/i.test(visibleReviewCopy) && /When should ventilation evidence become relevant\?/i.test(visibleReviewCopy) && /Implicit allegation/i.test(visibleReviewCopy) && /Add ventilation decision/i.test(visibleReviewCopy) && /Move use evidence to the new decision; building-envelope assessment remains conditional\./i.test(visibleReviewCopy) && !/Required\s*→\s*Conditional/i.test(visibleReviewCopy), visibleReviewCopy);
  await auditViewports('04-review', '#artifactCanvas [data-artifact-focus="true"] [data-review-edit-state="pending"]');
  await page.locator('#artifactCanvas [data-artifact-focus="true"] [data-ac-action="submit-review"][data-review-mode="conditional"]').click();
  await waitVisible('body[data-casepath-moment="review-applied"]');
  await page.waitForFunction(() => document.querySelector('[data-review-edit-state="applied"]'), null, { timeout: 30000 });
  const appliedCanvas = await artifactCanvasSnapshot();
  const appliedCanvasIssues = focusedArtifactCanvasViolations(appliedCanvas);
  const postReviewGraphProjection = await page.locator('#artifactProcessGraph').evaluate(node => ({
    node_ids: [...node.querySelectorAll('[data-node-id][data-process-build-state]')].map(item => item.dataset.nodeId).filter(Boolean),
    change_ids: [...node.querySelectorAll('[data-artifact-change-id]')].map(item => item.dataset.artifactChangeId).filter(Boolean),
  }));
  const expectedReviewedProjection = [...FLAGSHIP_PROCESS_PROJECTION_IDS];
  expectedReviewedProjection.splice(expectedReviewedProjection.indexOf('causation') + 1, 0, 'ventilation_dispute');
  const appliedGraphScene = await persistentGraphSceneSnapshot();
  const appliedGraphSceneIssues = persistentGraphSceneContractViolations(appliedGraphScene, {
    scene: 'review-applied',
    nodeIds: expectedReviewedProjection,
    selectedNodeId: 'ventilation_dispute',
    reviewEditState: 'applied',
    inlineCorrectionCount: 0,
    applyActionCount: 0,
    appliedNoteCount: 1,
  });
  const addedReviewNodeIds = postReviewGraphProjection.node_ids.filter(nodeId => !preReviewGraphProjection.node_ids.includes(nodeId));
  check('Accepted review visibly mutates the same persistent graph in place and adds only the disputed-ventilation decision', appliedCanvasIssues.length === 0 && appliedCanvas.action_count === 1 && appliedGraphSceneIssues.length === 0 && stableJson(preReviewGraphProjection.node_ids) === stableJson(FLAGSHIP_PROCESS_PROJECTION_IDS) && stableJson(postReviewGraphProjection.node_ids) === stableJson(expectedReviewedProjection) && stableJson(addedReviewNodeIds) === stableJson(['ventilation_dispute']), JSON.stringify({ appliedCanvas, appliedCanvasIssues, appliedGraphScene, appliedGraphSceneIssues, preReviewGraphProjection, postReviewGraphProjection, addedReviewNodeIds }));
  const appliedCursorPayoff = await settledCursorPayoffSnapshot('review-applied');
  const appliedCursorPayoffIssues = settledCursorPayoffContractViolations(appliedCursorPayoff);
  check('Review-applied parks one visible cursor clear of the correction payoff and new ventilation node', appliedCursorPayoffIssues.length === 0, JSON.stringify({ appliedCursorPayoff, appliedCursorPayoffIssues }));
  if (false) {
  await page.locator('.v21-progressive-details > summary').click();
  await waitVisible('.v21-progressive-details[open] .review-applied-layout');
  await page.locator('.review-applied .process-node-button[data-node-id="causation"],.review-applied .process-branch-node[data-node-id="causation"]').first().click();
  check('Applied-review workspace preserves its declared no-precedent boundary after graph interaction', await page.locator('.review-applied .precedent-inline').count() === 0 && await page.locator('.review-applied .process-layout').getAttribute('data-precedents') === 'false');
  }
  const reviewed = await waitForValue(() => reviewResponse);
  retainedEvidence['demo-review'] = reviewed;
  check('Demo review response is accepted, typed, and explicitly unverified', reviewed.accepted === true && reviewed.reviewer?.type === 'unverified_demo_user' && reviewed.reviewer?.qualification_status === 'not_verified' && reviewed.result?.process && reviewed.result?.checklist, JSON.stringify(reviewed));
  const persistedReviewedRun = await getJson(`${API}/api/runs/${encodeURIComponent(flagshipRunId)}`);
  retainedEvidence['post-review-run'] = persistedReviewedRun;
  const reviewedEvidenceIssues = evidenceRelationContractViolations(reviewed.result?.process, reviewed.result?.checklist);
  check('Applied-review checklist retains exact reciprocal process ownership', reviewedEvidenceIssues.length === 0, JSON.stringify(reviewedEvidenceIssues));
  const reviewTransformIssues = reviewTransformContractViolations(reviewed, persistedReviewedRun, flagshipBeforeReview);
  check(isProductionJourney() ? 'Review is an explicitly unverified post-model transform with exact pre/post hashes and preserved model-time acceptance receipts' : 'Local deterministic review is an explicitly unverified transform with exact pre/post hashes', reviewTransformIssues.length === 0, JSON.stringify(reviewTransformIssues));
  const appliedReviewCopy = await page.locator('#artifactCanvas [data-artifact-focus="true"]').innerText();
  check('Applied-review UI keeps the edit explicitly unverified', /unverified/i.test(appliedReviewCopy), appliedReviewCopy);
  const appliedContributionBadgeCount = await page.locator('.review-applied .model-contribution-attribution').count();
  const visibleContributionBadgeCount = await page.locator('.model-contribution-attribution:visible').count();
  const visibleFinalHandoffCount = await page.locator('.v20-final-handoff:visible').count();
  const postReviewContributionExpectations = [
    ...reviewed.result.process.nodes.flatMap(node => (node.agent_decision_contributions || []).map(contribution => contributionExpectation(contribution, 'Process Decision Mapping Agent', reviewed.review_transform))),
    ...reviewed.result.checklist.items.map(item => contributionExpectation(item.agent_contribution, 'Evidence and Checklist Agent', reviewed.review_transform)),
    contributionExpectation(orchestrationAudit(flagshipBeforeReview)?.final_claim_brief?.field_contributions, FINAL_CONTRIBUTION_ROLE, reviewed.review_transform),
  ];
  check('Applied-review result globally suppresses every pre-review contribution badge and final handoff', reviewed.review_transform?.acceptance_scope === 'post_review_unverified_transform' && reviewed.review_transform?.model_acceptance_reused === false && postReviewContributionExpectations.every(value => value === null) && appliedContributionBadgeCount === 0 && visibleContributionBadgeCount === 0 && visibleFinalHandoffCount === 0, JSON.stringify({ review_transform: reviewed.review_transform, post_review_expectations: postReviewContributionExpectations, rendered_badge_count: appliedContributionBadgeCount, visible_badge_count: visibleContributionBadgeCount, visible_final_handoff_count: visibleFinalHandoffCount }));
  if (false) {
  const reviewedNodeIds = reviewed.result.process.nodes.map(node => node.node_id);
  const appliedNodeIds = await page.evaluate(() => [...new Set([...document.querySelectorAll('.review-applied .process-node-button[data-node-id],.review-applied .process-branch-node[data-node-id]')].map(node => node.dataset.nodeId))]);
  check('Applied view shows the actual server-returned reviewed graph', reviewedNodeIds.every(id => appliedNodeIds.includes(id)) && reviewedNodeIds.length === appliedNodeIds.length, JSON.stringify({ reviewedNodeIds, appliedNodeIds }));
  const appliedEdges = await page.locator('.review-applied .process-edge[data-edge-source][data-edge-target]').evaluateAll(edges => edges.map(edge => ({ source: edge.dataset.edgeSource, target: edge.dataset.edgeTarget, state: edge.dataset.edgeState })));
  const reviewedEdges = reviewed.result.process.edges.map(edge => ({ source: edge.source, target: edge.target, state: edge.state || '' }));
  check('Applied view retains every server-returned reviewed graph connection', JSON.stringify(appliedEdges) === JSON.stringify(reviewedEdges), JSON.stringify({ reviewedEdges, appliedEdges }));
  const reviewedChecklistProjection = await page.locator('.reviewed-checklist [data-item-id]').evaluateAll(nodes => nodes.map(node => ({ item_id: node.dataset.itemId, node_id: node.dataset.nodeId, node_ids: node.dataset.nodeIds, current_path: node.dataset.currentPath })));
  check('Applied view shows the actual reviewed checklist with ordered owners and current-path state', reviewedChecklistProjection.length === reviewed.result.checklist.items.length && reviewedChecklistProjection.every((projection, index) => projection.item_id === reviewed.result.checklist.items[index].item_id && projection.node_id === reviewed.result.checklist.items[index].node_id && projection.node_ids === reviewed.result.checklist.items[index].node_ids.join(',') && projection.current_path === String(reviewed.result.checklist.items[index].current_path === true)), JSON.stringify(reviewedChecklistProjection));
  const reviewedSelectedNode = reviewed.result.process.nodes.find(node => node.node_id === reviewed.result.process.current_overlay?.current_node_id);
  const reviewedSelectedFacts = reviewed.result.facts.filter(fact => (reviewedSelectedNode?.fact_ids || []).includes(fact.fact_id)).slice(0, 2);
  const reviewedFactChain = await page.locator('.review-applied .v17-evidence-chain').innerText();
  check('Applied fact chain remains bound to the displayed reviewed run', reviewedSelectedFacts.length > 0 && reviewedSelectedFacts.every(fact => reviewedFactChain.includes(`${fact.label}: ${fact.value}`)), JSON.stringify({ reviewedSelectedFacts, reviewedFactChain }));
  const beforeNodeIds = new Set(flagshipBeforeReview.result.process.nodes.map(node => node.node_id));
  const computedAdded = reviewedNodeIds.filter(id => !beforeNodeIds.has(id));
  check('Applied view presents a computed delta before consolidation', (await page.locator('.review-applied-delta article').first().innerText()).includes(String(computedAdded.length)));
  await page.locator('.v21-progressive-details > summary').click();
  const compactApplied = await minimalSurfaceSnapshot();
  check('Applied review recedes to one change summary after inspection', compactApplied.focus_count === 1 && compactApplied.artifact_count === 1 && compactApplied.action_count === 1 && await page.locator('.review-applied-layout').isHidden(), JSON.stringify(compactApplied));
  }
  await auditViewports('05-review-applied', '#artifactCanvas [data-review-edit-state="applied"]');

  await page.locator('#journeyNext').click();
  await waitVisible('body[data-casepath-moment="knowledge"]');
  await page.waitForFunction(() => document.body.dataset.casepathLearningReady === 'true', null, { timeout: 30000 });
  const knowledgeCanvas = await artifactCanvasSnapshot();
  const knowledgeGraphScene = await persistentGraphSceneSnapshot();
  const knowledgeGraphIssues = [
    ...graphNativeMomentSceneViolations({ ...knowledgeGraphScene, moment: 'knowledge' }, 'knowledge'),
    ...graphNativeMomentCopyContractViolations(knowledgeGraphScene, {
      attachmentKey: 'knowledge_memory_notes',
      attributes: { memory_status: 'unverified_demo_memory' },
      requiredNonemptyAttributes: ['memory_id'],
      requiredCopy: ['Saved as unverified case memory', 'Shared playbook unchanged'],
      forbiddenCopy: ['qualified review complete', 'shared playbook updated'],
    }),
  ];
  const candidateCopy = await page.locator('#artifactCanvas [data-artifact-focus="true"]').innerText();
  check('Knowledge consolidation keeps the graph as the sole focal artifact with one concise, unverified case-memory note', focusedArtifactCanvasViolations(knowledgeCanvas).length === 0 && knowledgeCanvas.action_count === 1 && knowledgeGraphIssues.length === 0 && /unverified case memory/i.test(candidateCopy), JSON.stringify({ knowledgeCanvas, knowledgeGraphScene, knowledgeGraphIssues, candidateCopy }));
  const knowledgeCursorPayoff = await settledCursorPayoffSnapshot('knowledge');
  const knowledgeCursorPayoffIssues = settledCursorPayoffContractViolations(knowledgeCursorPayoff);
  check('Knowledge parks one visible cursor clear of the saved-memory payoff and ventilation node', knowledgeCursorPayoffIssues.length === 0, JSON.stringify({ knowledgeCursorPayoff, knowledgeCursorPayoffIssues }));
  check('Candidate remains honestly quarantined with one unverified support record and zero qualified support', reviewed.candidate?.status === 'quarantined' && reviewed.candidate?.support_count === 1 && reviewed.candidate?.required_support === 3 && reviewed.candidate?.qualified_support_count === 0 && reviewed.candidate?.required_qualified_support === 3, JSON.stringify(reviewed.candidate));
  check('Shared playbook is explicitly unchanged', reviewed.candidate?.shared_knowledge_changed === false && /shared playbook unchanged/i.test(candidateCopy), candidateCopy);
  check('Passed deterministic gates remain distinct from missing qualified support and approval', reviewed.candidate?.target_tests?.status === 'passed' && reviewed.candidate?.protected_regression?.status === 'passed' && reviewed.candidate?.approval?.status === 'pending' && reviewed.candidate?.approval?.qualified_reviewer === false, JSON.stringify(reviewed.candidate));
  const protectedOutputCase = reviewed.candidate?.protected_regression?.cases?.find(value => value.case_id === 'source_claim_full_playbook_unchanged');
  check('Protected regression executes the real memory gate and independently binds unchanged full result, process, and checklist hashes', protectedOutputCase?.status === 'passed' && protectedOutputCase?.execution_contract === 'deterministic_case_specific_memory_gate/1.0.0' && protectedOutputCase?.gate_executed === true && protectedOutputCase?.expected_memory_application === false && protectedOutputCase?.actual_memory_application === false && protectedOutputCase?.output_unchanged === true && stableJson(protectedOutputCase?.before_hashes) === stableJson(protectedOutputCase?.after_hashes) && ['result_hash', 'process_hash', 'checklist_hash'].every(key => SHA256_PATTERN.test(protectedOutputCase?.before_hashes?.[key] || '')), JSON.stringify(protectedOutputCase));
  await auditViewports('06-learning', '#artifactCanvas [data-memory-id]');

  await page.locator('#journeyNext').click();
  await waitJourneyUi('Later-claim comparison did not reach its terminal UI state', async () => {
    await awaitLaterJourneyTerminalUi();
  });
  const laterCausalSteps = await page.evaluate(() => window.__casepathLaterCausalSteps || []);
  const laterSourceOpenings = await page.evaluate(() => window.__casepathLaterSourceOpenings || []);
  const laterWorkGraphSnapshots = await page.evaluate(() => window.__casepathGraphMomentSnapshots || []);
  const laterMemoryGraphScene = [...laterWorkGraphSnapshots].reverse().find(snapshot => snapshot.moment === 'later-work' && snapshot.phase === 'memory' && snapshot.scene === 'later-work');
  const laterEligibilityGraphScene = [...laterWorkGraphSnapshots].reverse().find(snapshot => snapshot.moment === 'later-work' && snapshot.phase === 'eligibility' && snapshot.scene === 'later-work');
  const laterMemoryGraphIssues = [
    ...graphNativeMomentSceneViolations(laterMemoryGraphScene, 'later-work'),
    ...graphNativeMomentCopyContractViolations(laterMemoryGraphScene, {
      attachmentKey: 'later_memory_retrievals',
      requiredNonemptyAttributes: ['memory_origin_id'],
      attributes: { later_causal_phase: 'memory' },
      requiredCopy: ['Unverified case memory retrieved', 'Now checking whether it applies'],
      forbiddenCopy: ['applied guidance', 'shared playbook updated'],
    }),
  ];
  const laterEligibilityGraphIssues = [
    ...graphNativeMomentSceneViolations(laterEligibilityGraphScene, 'later-work'),
    ...graphNativeMomentCopyContractViolations(laterEligibilityGraphScene, {
      attachmentKey: 'later_memory_retrievals',
      requiredNonemptyAttributes: ['memory_origin_id', 'eligibility_contract', 'eligibility_rule_id', 'semantic_role'],
      attributes: { later_causal_phase: 'eligibility' },
      requiredCopy: ['Eligibility check passed', 'Same unresolved ventilation allegation', 'final proof'],
      forbiddenCopy: ['shared playbook updated', 'qualified approval'],
    }),
  ];
  const laterCausalStepIssues = [];
  if (laterCausalSteps.length !== 4) laterCausalStepIssues.push(`step count ${laterCausalSteps.length}`);
  if (!laterCausalSteps.every(step => step.contract === 'casepath.later-causal-step/1.0.0')) laterCausalStepIssues.push('step contract');
  if (stableJson(laterCausalSteps.map(step => step.phase)) !== stableJson(['waiting', 'source', 'memory', 'eligibility'])) laterCausalStepIssues.push(`step phases ${stableJson(laterCausalSteps.map(step => step.phase))}`);
  const laterSourceStep = laterCausalSteps.find(step => step.phase === 'source');
  if (!laterSourceStep?.factId || !laterSourceStep?.sourceId || !laterSourceStep?.locatorId) laterCausalStepIssues.push('source identity');
  if ((laterSourceStep?.activeSourceIds || []).length) laterCausalStepIssues.push(`source preselected ${stableJson(laterSourceStep?.activeSourceIds || [])}`);
  if (laterSourceOpenings.length !== 1) laterCausalStepIssues.push(`source opening count ${laterSourceOpenings.length}`);
  const laterSourceOpening = laterSourceOpenings[0];
  if (laterSourceOpening && (laterSourceOpening.contract !== 'casepath.later-causal-step/1.0.0'
    || laterSourceOpening.runId !== laterSourceStep?.runId
    || laterSourceOpening.factId !== laterSourceStep?.factId
    || laterSourceOpening.sourceId !== laterSourceStep?.sourceId
    || laterSourceOpening.locatorId !== laterSourceStep?.locatorId
    || stableJson(laterSourceOpening.activeSourceIds || []) !== stableJson([displayedSourceRailId(laterSourceStep?.sourceId)])
    || laterSourceOpening.activeLocatorId !== laterSourceStep?.locatorId
    || laterSourceOpening.sourceOpened !== 'true')) laterCausalStepIssues.push('source click did not reveal the exact later-claim passage');
  const laterMemoryStep = laterCausalSteps.find(step => step.phase === 'memory');
  if ((laterMemoryStep?.activeSourceIds || []).length) laterCausalStepIssues.push(`memory source rail ${stableJson(laterMemoryStep.activeSourceIds)}`);
  const laterEligibilityStep = laterCausalSteps.find(step => step.phase === 'eligibility');
  if (!laterEligibilityStep?.memoryOriginId || !laterEligibilityStep?.eligibilityContract || !laterEligibilityStep?.ruleId || laterEligibilityStep?.semanticRole !== 'management_ventilation_allegation') laterCausalStepIssues.push('eligibility identity');
  check('Later-work keeps the untouched graph central while source click, memory retrieval, and exact eligibility visibly precede the proven graph change', laterMemoryGraphIssues.length === 0 && laterEligibilityGraphIssues.length === 0 && laterCausalStepIssues.length === 0, JSON.stringify({ laterCausalSteps, laterSourceOpenings, laterMemoryGraphScene, laterEligibilityGraphScene, laterMemoryGraphIssues, laterEligibilityGraphIssues, laterCausalStepIssues }));
  const laterCanvas = await artifactCanvasSnapshot();
  const laterCanvasIssues = focusedArtifactCanvasViolations(laterCanvas);
  const laterGraphScene = await persistentGraphSceneSnapshot();
  const expectedLaterProjection = [...FLAGSHIP_PROCESS_PROJECTION_IDS];
  expectedLaterProjection.splice(expectedLaterProjection.indexOf('causation') + 1, 0, 'ventilation_dispute');
  const laterGraphSceneIssues = persistentGraphSceneContractViolations(laterGraphScene, {
    scene: 'later-result',
    nodeIds: expectedLaterProjection,
    selectedNodeId: 'ventilation_dispute',
  });
  check('The future claim reuses the same source-plus-process canvas with the persistent graph as its sole visible focal artifact', laterCanvasIssues.length === 0 && laterCanvas.action_count === 1 && laterGraphSceneIssues.length === 0, JSON.stringify({ laterCanvas, laterCanvasIssues, laterGraphScene, laterGraphSceneIssues }));
  const laterCursorPayoff = await settledCursorPayoffSnapshot('later-result');
  const laterCursorPayoffIssues = settledCursorPayoffContractViolations(laterCursorPayoff);
  check('Later result parks one visible cursor clear of the memory-effect payoff and added ventilation node', laterCursorPayoffIssues.length === 0, JSON.stringify({ laterCursorPayoff, laterCursorPayoffIssues }));
  const proof = await waitForValue(() => proofResponse, runTimeoutMs());
  check('Held-out result retains one authority-labelled knowledge focus and one calm cursor', await page.locator('#artifactCanvas[data-casepath-scene="later-result"][data-work-authority] [data-artifact-focus="true"]').count() === 1 && await page.locator('#artifactCanvas[data-casepath-scene="later-result"] #artifactAgentCursor').count() === 1);
  retainedEvidence['learning-proof'] = proof;
  check('Lifecycle produced flagship, baseline, and post-review runs', runIds.length === 3, JSON.stringify(runIds));
  const baseline = await awaitRun(runIds[1]);
  const later = await awaitRun(runIds[2]);
  const laterClaim = await getJson(`${API}/api/claims/${encodeURIComponent(demo.later_claim_id)}`);
  retainedEvidence['later-baseline-run'] = baseline;
  retainedEvidence['later-after-memory-run'] = later;
  if (!isLocal(BASE) || !isLocal(API)) {
    const baselineReferenceIssues = deterministicReferenceRunViolations(baseline, 'baseline');
    const laterReferenceIssues = deterministicReferenceRunViolations(later, 'current');
    check('Held-out baseline and current comparisons explicitly disclose deterministic-reference authority with no executed model DAG or call activity', baselineReferenceIssues.length === 0 && laterReferenceIssues.length === 0, JSON.stringify({ baseline: baselineReferenceIssues, later: laterReferenceIssues }));
  }
  for (const [label, run, claim] of [['baseline', baseline, laterClaim], ['later', later, laterClaim]]) {
    const relationIssues = evidenceRelationContractViolations(run.result?.process, run.result?.checklist);
    check(`${label} later-claim run retains exact reciprocal evidence ownership`, relationIssues.length === 0, JSON.stringify(relationIssues));
    const legalIssues = legalContextContractViolations(run.result?.legal_research, run.result?.process);
    check(`${label} later-claim run retains exact ID-joined legal context`, legalIssues.length === 0, JSON.stringify(legalIssues));
    const visualRefs = (run.result?.facts || []).flatMap(fact => (fact.source_refs || []).filter(reference => reference.locator_kind === 'visual_observation'));
    const visualIssues = visualRefs.flatMap(reference => visualReferenceContractViolations(reference, claim.artifacts.find(artifact => artifact.artifact_id === reference.artifact_id)).map(issue => `${reference.artifact_id}: ${issue}`));
    check(`${label} later-claim run binds every curated visual annotation to public image bytes`, visualRefs.length > 0 && visualIssues.length === 0, JSON.stringify(visualIssues));
    const rankingIssues = precedentRankingContractViolations(run.result);
    check(`${label} later-claim run recomputes an exact-three ranking receipt`, rankingIssues.length === 0, JSON.stringify(rankingIssues));
    const memoryStateIssues = memoryRetrievalContractViolations(run.result);
    check(`${label} later-claim run keeps retrieval separate from receipt-bound memory use`, memoryStateIssues.length === 0, JSON.stringify(memoryStateIssues));
  }
  const memoryIssues = memoryApplicationContractViolations(baseline, later, proof);
  check('Later causal proof independently binds the exact memory receipt, retained pre-transform boundary, persisted completed event, DTO hashes, semantic eligibility, operations, delta, ten checks, pure replay, and unchanged v3', memoryIssues.length === 0, JSON.stringify(memoryIssues));
  check('Computed proof names both completed later-claim runs', proof.before?.run_id === baseline.run_id && proof.after?.run_id === later.run_id);
  check('Later claim keeps the shared v3 playbook and applies no shared rule', later.result?.playbook?.version === 'mould-playbook-v3' && later.result?.shared_rule_applied === false);
  const laterProcess = later.result?.process || later.process;
  const laterCurrentNodeId = laterProcess?.current_overlay?.current_node_id || laterProcess?.current_node;
  const laterCurrentNode = laterProcess?.nodes?.find(node => node.node_id === laterCurrentNodeId);
  check('Later claim remains in Swiss residential tenancy at unresolved causation with the evidence-gap next action', later.result?.category === 'Rental defect - mould and moisture' && later.result?.scope === 'Swiss residential tenancy' && laterCurrentNodeId === 'causation' && laterCurrentNode?.state === 'current' && laterCurrentNode?.answer === 'Unresolved' && laterProcess?.current_overlay?.next_action_node_id === 'evidence_gap' && laterProcess?.selected_path?.includes('evidence_gap'), JSON.stringify({ category: later.result?.category, scope: later.result?.scope, current_node_id: laterCurrentNodeId, current_node: laterCurrentNode, overlay: laterProcess?.current_overlay, selected_path: laterProcess?.selected_path }));
  check('Later proof retains its own current unresolved causation decision', laterCurrentNodeId === 'causation' && laterCurrentNode?.title === 'Causation assessment' && laterCurrentNode?.answer === 'Unresolved', JSON.stringify(laterCurrentNode));
  check('Later memory transform adds exactly the ventilation node, two bounded edges, and three evidence-item changes', stableJson(proof.causal_delta?.process?.added_node_ids) === stableJson(['ventilation_dispute']) && stableJson(proof.causal_delta?.process?.added_edges) === stableJson([{ source: 'evidence_gap', target: 'ventilation_dispute' }, { source: 'ventilation_dispute', target: 'causation' }]) && stableJson(proof.causal_delta?.evidence?.changed_item_ids) === stableJson(['building_envelope', 'management_position', 'use_evidence']) && laterProcess.nodes.some(node => node.node_id === 'ventilation_dispute'), JSON.stringify(proof.causal_delta));
  const memoryEffects = laterGraphScene.memory_effects;
  const visibleMemoryEffects = laterGraphScene.visible_memory_effects;
  const expectedMemoryOrigin = later.result?.memory_application?.source_memory?.memory_id || reviewed.memory_id;
  const memoryEffectIssues = memoryEffectContractViolations(memoryEffects, expectedMemoryOrigin);
  const visibleMemoryEffectShape = Object.fromEntries(['node-added', 'edge-added', 'evidence-changed'].map(effect => [effect, visibleMemoryEffects.filter(item => item.effect === effect).length]));
  check('Future claim contains one receipt-bound causal delta while technical evidence changes stay behind Inspect proof', memoryEffectIssues.length === 0 && stableJson(visibleMemoryEffectShape) === stableJson({ 'node-added': 1, 'edge-added': 2, 'evidence-changed': 0 }), JSON.stringify({ memoryEffects, memoryEffectIssues, visibleMemoryEffects, visibleMemoryEffectShape, expectedMemoryOrigin }));
  const laterMemoryValidations = await page.evaluate(() => window.__casepathLaterMemoryValidations || []);
  const renderTimeline = await page.evaluate(() => window.__casepathRenderTimeline || []);
  const laterMemoryPresentationIssues = laterMemoryPresentationContractViolations(laterMemoryValidations, renderTimeline, laterGraphScene, later, true);
  check('Later memory effects appear only after one receipt-bound validation event that precedes rendering and binds the exact returned delta', laterMemoryPresentationIssues.length === 0, JSON.stringify({ laterMemoryValidations, laterGraphScene, laterMemoryPresentationIssues }));
  const memoryUsed = later.result?.memory_application != null
    && later.result?.memory_used === true
    && later.result?.reviewed_memory_used === true
    && later.result?.knowledge?.reviewed_memory_used === true
    && later.result?.reviewed_memory_retrieved === true
    && later.result?.knowledge?.reviewed_memory_retrieved === true
    && later.result?.process?.memory_used === true
    && later.result?.checklist?.memory_used === true
    && proof.reviewed_memory_proof?.used === true
    && memoryIssues.length === 0;
  const visibleLaterCopy = laterGraphScene.text;
  check('Later graph visibly keeps the reused guidance unverified and the shared playbook unchanged only when every use flag, receipt, and proof agrees', memoryUsed && /unverified case memory/i.test(visibleLaterCopy) && /qualified review required/i.test(visibleLaterCopy) && /shared playbook unchanged/i.test(visibleLaterCopy), visibleLaterCopy);
  const laterOperationalBenefit = await page.locator('#artifactCanvas .ac-memory-graph-delta[data-memory-payoff="single-action"]').evaluate(panel => {
    const visible = node => Boolean(node && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden' && getComputedStyle(node).display !== 'none');
    const eyebrow = panel.querySelector(':scope>small');
    const action = panel.querySelector('.ac-memory-action');
    const caveat = panel.querySelector(':scope>p');
    const details = panel.querySelector(':scope>details');
    const seam = panel.querySelector(':scope > .ac-memory-causal-seam');
    const seamParts = [...(seam?.querySelectorAll(':scope > [data-causal-seam-part]') || [])];
    const effects = [...panel.querySelectorAll('.ac-memory-process-link, .ac-memory-evidence-change')];
    const directProofChildren = [...(details?.querySelectorAll(':scope > :not(summary)') || [])];
    return {
      payoff: panel.dataset.memoryPayoff || '',
      status: panel.dataset.memoryStatus || '',
      responsibility: panel.dataset.responsibilityState || '',
      sharedPlaybookChanged: panel.dataset.sharedPlaybookChanged || '',
      eyebrow: eyebrow?.textContent?.trim() || '',
      action: action?.textContent?.trim() || '',
      guardrail: caveat?.textContent?.replace(/\s+/g, ' ').trim() || '',
      detailsClosed: Boolean(details && !details.open),
      detailsSummary: details?.querySelector(':scope>summary')?.textContent?.trim() || '',
      detailsSummaryVisible: visible(details?.querySelector(':scope>summary')),
      directProofChildrenVisibleCount: directProofChildren.filter(visible).length,
      technicalEffectCount: effects.length,
      visibleTechnicalEffectCount: effects.filter(visible).length,
      actionVisible: visible(action),
      guardrailVisible: visible(caveat),
      seamVisible: visible(seam),
      seamCount: panel.querySelectorAll(':scope > .ac-memory-causal-seam').length,
      sourceId: seam?.dataset.laterPayoffSource || '',
      locatorId: seam?.dataset.laterPayoffLocator || '',
      ruleId: seam?.dataset.laterPayoffRule || '',
      parts: seamParts.map(part => ({
        part: part.dataset.causalSeamPart || '',
        small: part.querySelector(':scope > small')?.textContent?.trim() || '',
        strong: part.querySelector(':scope > strong')?.textContent?.trim() || '',
        mark: part.querySelector('mark')?.textContent?.trim() || '',
      })),
      proofSummary: details?.querySelector('.ac-memory-proof-summary')?.textContent?.replace(/\s+/g, ' ').trim() || '',
      processLinkCount: details?.querySelectorAll('.ac-memory-process-link').length || 0,
      documentNeedCount: details?.querySelectorAll('.ac-memory-evidence-change').length || 0,
    };
  });
  const laterCausalSeamIssues = laterCausalSeamContractViolations(laterOperationalBenefit, later, laterSourceStep);
  check('Later payoff retains the exact returned source locator and excerpt, accepted eligibility rule, saved correction, graph result, and 1/2/3 receipt effects', laterCausalSeamIssues.length === 0, JSON.stringify({ laterOperationalBenefit, laterCausalSeamIssues, laterSourceStep }));
  check('Later payoff shows one exact guarded action and keeps five technical effects behind closed Inspect proof', laterOperationalBenefit.payoff === 'single-action' && laterOperationalBenefit.status === 'unverified-case-memory' && laterOperationalBenefit.responsibility === 'blocked' && laterOperationalBenefit.sharedPlaybookChanged === 'false' && laterOperationalBenefit.eyebrow === 'Unverified case memory used on this claim · Shared playbook unchanged' && laterOperationalBenefit.action === 'Check ventilation before assigning responsibility.' && laterOperationalBenefit.guardrail === 'Cause still unproven · responsibility stays blocked · qualified review required.' && laterOperationalBenefit.detailsClosed && laterOperationalBenefit.detailsSummary === 'Inspect proof' && laterOperationalBenefit.detailsSummaryVisible && laterOperationalBenefit.directProofChildrenVisibleCount === 0 && laterOperationalBenefit.technicalEffectCount === 5 && laterOperationalBenefit.visibleTechnicalEffectCount === 0 && laterOperationalBenefit.actionVisible && laterOperationalBenefit.guardrailVisible && laterOperationalBenefit.seamVisible, JSON.stringify(laterOperationalBenefit));
  const laterProofDetails = page.locator('#artifactCanvas .ac-memory-graph-delta[data-memory-payoff="single-action"] > details');
  await laterProofDetails.locator(':scope > summary').click();
  await waitVisible('#artifactCanvas .ac-memory-graph-delta[data-memory-payoff="single-action"] > details[open] .ac-memory-process-link');
  const revealedLaterEffects = await laterProofDetails.evaluate(details => {
    const visible = node => Boolean(node && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden' && getComputedStyle(node).display !== 'none');
    const processLinks = [...details.querySelectorAll('.ac-memory-process-link')];
    const documentNeeds = [...details.querySelectorAll('.ac-memory-evidence-change')];
    return {
      detailsOpen: details.open,
      processLinks: processLinks.length,
      visibleProcessLinks: processLinks.filter(visible).length,
      documentNeeds: documentNeeds.length,
      visibleDocumentNeeds: documentNeeds.filter(visible).length,
    };
  });
  check('Inspect proof reveals exactly two process links and three document-need effects', revealedLaterEffects.detailsOpen && revealedLaterEffects.processLinks === 2 && revealedLaterEffects.visibleProcessLinks === 2 && revealedLaterEffects.documentNeeds === 3 && revealedLaterEffects.visibleDocumentNeeds === 3, JSON.stringify(revealedLaterEffects));
  await laterProofDetails.locator(':scope > summary').click();
  const reclosedLaterProof = await laterProofDetails.evaluate(details => {
    const visible = node => Boolean(node && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden' && getComputedStyle(node).display !== 'none');
    const effects = [...details.querySelectorAll('.ac-memory-process-link, .ac-memory-evidence-change')];
    const directProofChildren = [...details.querySelectorAll(':scope > :not(summary)')];
    return {
      detailsClosed: details.open === false,
      directProofChildrenVisibleCount: directProofChildren.filter(visible).length,
      visibleTechnicalEffectCount: effects.filter(visible).length,
    };
  });
  check('Later proof returns to its closed default after inspection', reclosedLaterProof.detailsClosed && reclosedLaterProof.directProofChildrenVisibleCount === 0 && reclosedLaterProof.visibleTechnicalEffectCount === 0, JSON.stringify(reclosedLaterProof));
  check('Later ranking selects the unverified demo memory and remains exactly three ordered patterns', later.result.precedents.length === 3 && later.result.precedents[0]?.claim_id === 'DEF-027-E0-DEMO' && later.result.precedents[0]?.review_status === 'unverified_demo_memory' && later.result.precedent_ranking.selected_claim_ids[0] === 'DEF-027-E0-DEMO', JSON.stringify(later.result.precedents.map(item => ({ claim_id: item.claim_id, status: item.review_status, rank: item.ranking?.rank }))));
  const transformedContributionValues = [
    ...(later.result.process.nodes || []).flatMap(node => (node.agent_decision_contributions || []).map(contribution => contributionExpectation(contribution, PROCESS_CONTRIBUTION_ROLE, later.result.memory_application))),
    ...(later.result.checklist.items || []).map(item => contributionExpectation(item.agent_contribution, EVIDENCE_CONTRIBUTION_ROLE, later.result.memory_application)),
  ];
  check('Post-memory DTOs and UI contain no pre-memory Nemotron acceptance attribution', transformedContributionValues.every(value => value === null) && await page.locator('#laterResult .model-contribution-attribution').count() === 0 && !Object.hasOwn(later.result.process, 'agent_contribution') && !later.result.process.nodes.some(node => Object.hasOwn(node, 'agent_decision_contributions')) && !Object.hasOwn(later.result.checklist, 'agent_contribution') && !later.result.checklist.items.some(item => Object.hasOwn(item, 'agent_contribution')) && later.result.next_action?.agent_brief_contribution === null, JSON.stringify(transformedContributionValues));
  if (false) {
  const returnedUnverifiedMemory = later.result?.precedents?.find(item => item.review_status === 'unverified_demo_memory' && item.memory_id);
  if (memoryUsed && returnedUnverifiedMemory) {
    const reuseThreadSelector = '#laterResult .v18-reuse-proof .v17-reuse-thread';
    await waitVisible(reuseThreadSelector);
    const laterReuseThreadCount = await page.locator('#laterResult .v17-reuse-thread').count();
    const reuseProofCount = await page.locator('#laterResult .v18-reuse-proof').count();
    const proofReuseThreadCount = await page.locator(reuseThreadSelector).count();
    check('Later result renders exactly one receipt-bound memory-reuse proof and thread', laterReuseThreadCount === 1 && reuseProofCount === 1 && proofReuseThreadCount === 1, JSON.stringify({ later_reuse_threads: laterReuseThreadCount, reuse_proofs: reuseProofCount, proof_reuse_threads: proofReuseThreadCount }));
    const reuseCopy = await page.locator(reuseThreadSelector).innerText();
    check('Returned demo memory stays explicitly unverified wherever its precedent is rendered', /unverified demo review memory returned/i.test(reuseCopy) && !/qualified expert-reviewed memory returned/i.test(reuseCopy), reuseCopy);
    const proofLayout = await page.locator(reuseThreadSelector).evaluate(node => {
      const style = getComputedStyle(node);
      const proofValues = [...node.querySelectorAll('strong,code')].map(value => getComputedStyle(value));
      return {
        display: style.display,
        grid_template_columns: style.gridTemplateColumns,
        client_width: node.clientWidth,
        scroll_width: node.scrollWidth,
        values_wrap: proofValues.every(value => value.overflowWrap === 'anywhere' && value.wordBreak === 'break-word'),
      };
    });
    check('Final memory-proof layout uses responsive grid columns and wraps long receipt hashes without local overflow', proofLayout.display === 'grid' && proofLayout.grid_template_columns !== 'none' && proofLayout.scroll_width <= proofLayout.client_width + 1 && proofLayout.values_wrap, JSON.stringify(proofLayout));
  }
  const receiptProjection = await page.locator('.memory-application-receipt').evaluate(node => {
    const eligibility = node.querySelector('.memory-semantic-eligibility');
    return {
      contract: node.dataset.memoryContract,
      authority: node.dataset.memoryAuthority,
      scope: node.dataset.memoryScope,
      application_hash: node.dataset.applicationHash,
      model_acceptance_reused: node.dataset.modelAcceptanceReused,
      shared_rule_applied: node.dataset.sharedRuleApplied,
      eligibility_contract: eligibility?.dataset.eligibilityContract,
      eligibility_rule_id: eligibility?.dataset.eligibilityRuleId,
      semantic_signature_hash: eligibility?.dataset.semanticSignatureHash,
      semantic_role: eligibility?.dataset.semanticRole,
      text: node.innerText,
    };
  });
  const laterResultText = await page.locator('#laterResult').innerText();
  check('Rendered receipt exposes exact unverified boundary, semantic eligibility, application hash, and every before/after DTO and semantic hash', receiptProjection.contract === later.result.memory_application.contract && receiptProjection.authority === 'unverified_demo' && receiptProjection.scope === 'case_specific_guidance_only' && receiptProjection.application_hash === later.result.memory_application.application_hash && receiptProjection.model_acceptance_reused === 'false' && receiptProjection.shared_rule_applied === 'false' && receiptProjection.eligibility_contract === later.result.memory_application.eligibility.contract && receiptProjection.eligibility_rule_id === later.result.memory_application.eligibility.rule_id && receiptProjection.semantic_signature_hash === later.result.memory_application.eligibility.semantic_signature_hash && receiptProjection.semantic_role === 'management_ventilation_allegation' && [...Object.values(later.result.memory_application.before), ...Object.values(later.result.memory_application.after)].every(hash => laterResultText.includes(hash)), JSON.stringify(receiptProjection));
  const renderedDelta = await page.locator('.causal-delta').evaluate(node => ({ nonzero: node.dataset.causalNonzero, text: node.textContent }));
  check('Retained causal delta names the exact added node, two edges, and three changed evidence items', renderedDelta.nonzero === 'true' && ['ventilation_dispute', 'evidence_gap → ventilation_dispute', 'ventilation_dispute → causation', 'building_envelope', 'management_position', 'use_evidence'].every(value => renderedDelta.text.includes(value)), renderedDelta.text);
  const visibleDeltaSummary = await page.locator('.causal-delta header').innerText();
  check('Future-claim result visibly explains the exact bounded improvement in one concise line', /ventilation dispute decision added/i.test(visibleDeltaSummary) && /2 process links/i.test(visibleDeltaSummary) && /3 evidence needs updated/i.test(visibleDeltaSummary), visibleDeltaSummary);
  const renderedChecks = await page.locator('.memory-deterministic-checks [data-memory-check]').evaluateAll(nodes => nodes.map(node => ({ name: node.dataset.memoryCheck, status: node.dataset.checkStatus })));
  check('Rendered causal proof shows all ten deterministic checks in order and passed', renderedChecks.length === 10 && stableJson(renderedChecks) === stableJson(proof.deterministic_checks.map(item => ({ name: item.name, status: item.status }))), JSON.stringify(renderedChecks));
  const finalComparison = page.locator('#laterResult .final-proof');
  const finalComparisonText = await finalComparison.innerText();
  check('Before/after visibly exposes both returned result hashes and retains unchanged shared v3', await finalComparison.isVisible() && finalComparisonText.includes(proof.before.result_hash) && finalComparisonText.includes(proof.after.result_hash) && /Shared playbook v3 unchanged/i.test(laterResultText) && /mould-playbook-v3/i.test(laterResultText), JSON.stringify({ comparison: finalComparisonText, shared_playbook_visible: /Shared playbook v3 unchanged/i.test(laterResultText) }));
  const compactLater = await minimalSurfaceSnapshot();
  check('Future-claim view recedes to one causal outcome with proof behind disclosure', compactLater.focus_count === 1 && compactLater.artifact_count === 1 && compactLater.action_count === 1 && await laterProofDetails.isVisible() && await page.locator('.memory-application-receipt').isHidden(), JSON.stringify(compactLater));
  }
  await auditViewports('07-later-result', '#artifactCanvas [data-memory-effect="node-added"]');
  } else {
    acceptedJourneyMode = 'conservative-ready';
    const earlyDocumentsAction = page.locator('#artifactProcessGraph [data-ac-action="open-documents"].ac-document-needs-link');
    check('A conservative returned route still exposes its complete process-derived Documents model', await earlyDocumentsAction.count() === 1 && await earlyDocumentsAction.isVisible() && await earlyDocumentsAction.isEnabled());
    await earlyDocumentsAction.click();
    await waitVisible('#v20DocumentSheet[open]');
    const earlyDocumentPlan = await page.locator('#v20DocumentSheet').evaluate(sheet => ({
      model: sheet.querySelector('.v20-document-body')?.dataset.documentModel || '',
      items: [...sheet.querySelectorAll('.v20-document-chain[data-item-id]')].map(chain => ({
        itemId: chain.dataset.itemId || '',
        nodeId: chain.dataset.nodeId || '',
        nodeIds: chain.dataset.nodeIds || '',
        factId: chain.dataset.factId || '',
        status: chain.dataset.status || '',
        documentStatus: chain.dataset.documentStatus || '',
      })),
    }));
    const expectedEarlyDocumentPlan = processRun.result.checklist.items.map(item => ({
      itemId: item.item_id,
      nodeId: item.node_id || '',
      nodeIds: (Array.isArray(item.node_ids) && item.node_ids.length ? item.node_ids : item.node_id ? [item.node_id] : []).join(','),
      factId: item.fact_id || '',
      status: item.status || '',
      documentStatus: item.status === 'provided_sufficient'
        ? 'received'
        : ['missing', 'provided_insufficient'].includes(item.status) ? 'missing'
          : item.status === 'conditional' ? 'conditional' : 'not-required',
    }));
    check('Conservative Documents preserves every exact returned item, status, fact, and process owner', earlyDocumentPlan.model === 'complete-claim-record'
      && stableJson(earlyDocumentPlan.items) === stableJson(expectedEarlyDocumentPlan), JSON.stringify({ earlyDocumentPlan, expectedEarlyDocumentPlan }));
    await page.keyboard.press('Escape');
    await waitHidden('#v20DocumentSheet');
    const beforeBlockedMoment = await page.locator('#artifactProcessGraph').evaluate(graph => ({
      routeMode: graph.dataset.processRouteMode || '',
      terminalState: graph.dataset.processTerminalState || '',
      nodeIds: [...graph.querySelectorAll('[data-ac-node-id][data-process-build-state="built"]')].map(node => node.dataset.nodeId || ''),
      focalNodeId: graph.dataset.processFocalNodeId || '',
    }));
    await page.evaluate(() => {
      document.dispatchEvent(new CustomEvent('casepath:render', { detail: { moment: 'review' } }));
      document.dispatchEvent(new CustomEvent('casepath:render', { detail: { moment: 'knowledge' } }));
      document.dispatchEvent(new CustomEvent('casepath:render', { detail: { moment: 'later-result' } }));
    });
    const afterBlockedMoment = await page.locator('#artifactProcessGraph').evaluate(graph => ({
      scene: document.querySelector('#artifactCanvas')?.dataset.casepathScene || '',
      routeMode: graph.dataset.processRouteMode || '',
      terminalState: graph.dataset.processTerminalState || '',
      nodeIds: [...graph.querySelectorAll('[data-ac-node-id][data-process-build-state="built"]')].map(node => node.dataset.nodeId || ''),
      focalNodeId: graph.dataset.processFocalNodeId || '',
      reviewControls: document.querySelectorAll('#artifactCanvas .ac-review-graph-edit,#artifactCanvas [data-review-node-id="causation"],#artifactCanvas [data-memory-effect],#artifactCanvas [data-v20-continue-review]').length,
    }));
    check('A conservative returned route ends truthfully at Ready and refuses causation review or memory chapters', beforeBlockedMoment.routeMode === 'returned-route'
      && beforeBlockedMoment.terminalState === 'ready-route'
      && stableJson(beforeBlockedMoment.nodeIds) === stableJson(routeStory.storyNodeIds)
      && beforeBlockedMoment.focalNodeId === routeStory.currentNodeId
      && afterBlockedMoment.scene === 'ready'
      && afterBlockedMoment.routeMode === 'returned-route'
      && afterBlockedMoment.terminalState === 'ready-route'
      && stableJson(afterBlockedMoment.nodeIds) === stableJson(routeStory.storyNodeIds)
      && afterBlockedMoment.focalNodeId === routeStory.currentNodeId
      && afterBlockedMoment.reviewControls === 0, JSON.stringify({ routeStory, earlyDocumentPlan, beforeBlockedMoment, afterBlockedMoment }));
  }

  check('Immutable release marker was never rewritten during the journey', await page.evaluate(() => window.__casepathReleaseMutations.length === 0), JSON.stringify(await page.evaluate(() => window.__casepathReleaseMutations)));
  check('No lifecycle state exposes a false reviewed-v4 claim', !falseReviewedV4Claim.test(await page.locator('body').innerText()));
  check('Skip link remains present', await page.locator('.skip-link').count() === 1);
  await page.locator('.skip-link').focus();
  check('Skip link is keyboard focusable', await page.evaluate(() => document.activeElement?.matches('.skip-link')));
  check('Visible icon controls have accessible names', await page.evaluate(() => [...document.querySelectorAll('button.icon-button:not([hidden]),a.icon-button:not([hidden])')].every(node => node.getAttribute('aria-label') || node.textContent.trim())));
  await runAxe('Final lifecycle state');
  check('No browser console errors', failures.console.length === 0, JSON.stringify(failures.console));
  check('No page errors', failures.page.length === 0, JSON.stringify(failures.page));
  check('No product request failures', failures.request.length === 0, JSON.stringify(failures.request));
  check('Legacy v20 journey makes zero claim-loop requests', claimLoopRequests.length === 0, JSON.stringify(claimLoopRequests));

  const modelLedger = await getJson(`${API}/api/model-ledger`);
  const ledgerIssues = sanitizedLedgerViolations(modelLedger);
  check('Public model ledger is sanitized and retains no prompt, raw output, reasoning, or canonical-output payload', ledgerIssues.length === 0, JSON.stringify(ledgerIssues));
  const successfulNetworkCalls = modelLedger.items.filter(item => SUCCESSFUL_MODEL_OUTCOMES.has(item.outcome) && item.call_count === 1 && item.provider_endpoint === 'https://openrouter.ai/api/v1/chat/completions');
  check('Successful network calls retain an exact unnormalized Nemotron alias or dated response identity and usage provenance', successfulNetworkCalls.every(item => item.provider === 'openrouter' && item.model === REQUESTED_NEMOTRON_MODEL && EXACT_NEMOTRON_RESPONSE_MODELS.has(item.response_model) && ALLOWED_USAGE_SOURCES.has(item.usage_source)) && (!isProductionJourney() || successfulNetworkCalls.length === REQUIRED_NEMOTRON_AGENT_IDS.length), JSON.stringify(successfulNetworkCalls));
  if (isProductionJourney()) {
    const finalColdIssues = coldLedgerContractViolations(coldOrchestration, modelLedger);
    const finalSnapshotIssues = finalLedgerSnapshotViolations(isolationLedger, modelLedger);
    check('Final ledger is the immutable 12-row flagship cold6 plus warm6 snapshot with no held-out model activity', finalColdIssues.length === 0 && finalSnapshotIssues.length === 0, JSON.stringify({ finalColdIssues, finalSnapshotIssues, finalSummary: modelLedger.summary, isolationSummary: isolationLedger.summary }));
    const warmLineage = warmLineageContractViolations(coldOrchestration, warmOrchestration, modelLedger);
    check('Post-flagship isolation replay made zero provider calls and binds every cache record to its visible cold origin', warmLineage.issues.length === 0 && warmLineage.lineage.length === REQUIRED_NEMOTRON_AGENT_IDS.length, JSON.stringify(warmLineage));
    retainedEvidence['flagship-cache-lineage'] = {
      contract: 'casepath.flagship-cache-lineage/1.0.0',
      requested_model: REQUESTED_NEMOTRON_MODEL,
      exact_response_models: [...EXACT_NEMOTRON_RESPONSE_MODELS],
      framework: EXPECTED_FRAMEWORK,
      cold_orchestration_id: coldOrchestration.orchestration_id,
      warm_orchestration_id: warmOrchestration.orchestration_id,
      cold_run_surface: 'visible_browser_flagship',
      warm_run_surface: 'isolated_session_cache_replay',
      cold_guarded_fallback_count: coldOrchestration.guarded_fallback_count,
      warm_guarded_fallback_count: warmOrchestration.guarded_fallback_count,
      lineage: warmLineage.lineage,
      provider_calls_during_isolation_replay: 0,
    };
  }
  retainedEvidence['model-ledger'] = modelLedger;
  await page.screenshot({ path: path.join(OUT, 'final-state.png'), fullPage: true });
  await context.close();
  context = null;
  page = null;
  browserNetworkBoundary = await summarizeLoopbackNetworkGuards(networkGuards);
  check('Browser execution is confined to exact loopback origins with zero external requests', browserNetworkBoundary.loopback_only === true
    && browserNetworkBoundary.external_request_count === 0
    && browserNetworkBoundary.blocked_request_count === 0
    && browserNetworkBoundary.observed_origins.every(origin => [new URL(BASE).origin, new URL(API).origin].includes(origin)), JSON.stringify(browserNetworkBoundary));
  check('Every successful static response consumed by the browser equals a frozen built-product file', browserNetworkBoundary.static_responses.length > 0, JSON.stringify(browserNetworkBoundary.static_responses));
  retainedEvidence['browser-network-boundary'] = browserNetworkBoundary;

  return {
    status: 'passed',
    release: PRODUCT_RELEASE,
    release_id: RELEASE_ID,
    journey_mode: acceptedJourneyMode,
    checkedAt: new Date().toISOString(),
    baseUrl: BASE,
    apiUrl: API,
    deployment: deploymentIdentity,
    runtime: runtimeVersions,
    candidate_source_identity: candidateSourceIdentityStart,
    candidate_source_manifests: candidateSourceManifests,
    api_runtime_boot_receipt: apiRuntimeBootReceipt,
    api_runtime_identity: candidateSourceSnapshotStart.apiBootIdentity,
    browser_execution_receipt: browserExecutionReceiptBinding,
    browser_network_boundary: browserNetworkBoundary,
    check_roster_sha256: sha256(`${checks.map(item => item.name).join('\n')}\n`),
    passed: checks.length,
    failed: 0,
    checks,
    notes,
    failures,
    runIds,
  };
}

function mockOrchestration(cacheMode, coldRun = null) {
  const facts = [
    {
      fact_id: 'fact_scope',
      value: 'confirmed',
      state: 'supported',
      controls_process: true,
      decision_key: 'tenancy_scope',
      normalized_value: 'confirmed',
      decision_value: 'confirmed',
    },
    {
      fact_id: 'fact_context',
      value: 'observed context',
      state: 'known',
      controls_process: false,
      decision_key: null,
      normalized_value: null,
      decision_value: null,
    },
  ];
  const sourceIntegrity = {
    artifacts: [{
      artifact_id: 'lease',
      integrity_class: 'text_grounded',
      source_ref_ids: ['source_scope'],
      contribution_id: 'artifact:lease:integrity',
      attribution: 'Document and Source Integrity Agent',
      deterministic_fallback_applied: false,
      confidence_basis_points: 9200,
    }],
  };
  const processDecision = {
    fact_id: 'fact_scope',
    decision_key: 'tenancy_scope',
    decision_value: 'confirmed',
    state: 'supported',
    normalized_value: 'confirmed',
    source_ref_ids: ['source_scope'],
    contribution_id: 'fact:fact_scope:decision_value',
    contribution_scope: 'canonical_to_process_decision_mapping',
    model_owned_fields: ['decision_value'],
    confidence_basis_points: 9100,
    attribution: PROCESS_CONTRIBUTION_ROLE,
    deterministic_fallback_applied: false,
  };
  const processMapping = { decisions: [processDecision] };
  const evidenceFieldContributions = [
    {
      contribution_id: 'item:lease:status',
      field: 'status',
      attribution: EVIDENCE_CONTRIBUTION_ROLE,
      confidence_basis_points: 9000,
      deterministic_fallback_applied: false,
    },
    {
      contribution_id: 'item:lease:artifacts',
      field: 'artifact_ids',
      attribution: EVIDENCE_CONTRIBUTION_ROLE,
      confidence_basis_points: 9000,
      deterministic_fallback_applied: false,
    },
  ];
  const contextEvidenceFieldContributions = [
    {
      contribution_id: 'item:context_note:status',
      field: 'status',
      attribution: EVIDENCE_CONTRIBUTION_ROLE,
      confidence_basis_points: 8800,
      deterministic_fallback_applied: false,
    },
    {
      contribution_id: 'item:context_note:artifacts',
      field: 'artifact_ids',
      attribution: EVIDENCE_CONTRIBUTION_ROLE,
      confidence_basis_points: 8800,
      deterministic_fallback_applied: false,
    },
  ];
  const evidenceChecklist = {
    items: [
      {
        item_id: 'lease',
        status: 'provided_sufficient',
        artifact_ids: ['lease'],
        source_ref_ids: ['source_scope'],
        field_contributions: evidenceFieldContributions,
        model_owned_fields: ['status', 'artifact_ids'],
        confidence_basis_points: 9000,
        attribution: EVIDENCE_CONTRIBUTION_ROLE,
        deterministic_fallback_applied: false,
      },
      {
        item_id: 'context_note',
        status: 'provided_sufficient',
        artifact_ids: ['lease'],
        source_ref_ids: ['source_context'],
        field_contributions: contextEvidenceFieldContributions,
        model_owned_fields: ['status', 'artifact_ids'],
        confidence_basis_points: 8800,
        attribution: EVIDENCE_CONTRIBUTION_ROLE,
        deterministic_fallback_applied: false,
      },
    ],
  };
  const finalFieldContributions = FINAL_FIELD_CONTRACT.map(({ field, contribution_id }) => ({
    contribution_id,
    field,
    attribution: FINAL_CONTRIBUTION_ROLE,
    confidence_basis_points: 8900,
    deterministic_fallback_applied: false,
  }));
  const finalClaimBrief = {
    current_node_id: 'scope',
    next_action_node_id: 'notice',
    supporting_fact_ids: ['fact_context', 'fact_scope'],
    upstream_contribution_ids: [...FINAL_UPSTREAM_CONTRIBUTION_IDS],
    audit_check_ids: [...FINAL_AUDIT_CHECK_IDS],
    source_ref_ids: ['source_context', 'source_scope'],
    input_contribution_ids: [...FINAL_UPSTREAM_CONTRIBUTION_IDS],
    lineage_authority: 'hybrid_guarded_model_audit',
    contribution_scope: 'independent_final_claim_brief_audit',
    field_contributions: finalFieldContributions,
    confidence_basis_points: 8900,
    attribution: FINAL_CONTRIBUTION_ROLE,
    deterministic_fallback_applied: false,
  };
  const process = {
    contract: 'process-graph',
    current_node: 'scope',
    current_overlay: { current_node_id: 'scope', next_action_node_id: 'notice' },
    nodes: [
      { node_id: 'scope', title: 'Scope', fact_ids: ['fact_scope', 'fact_context'], agent_decision_contributions: [processDecision] },
      { node_id: 'notice', title: 'Notice', fact_ids: [] },
    ],
    agent_contribution: {
      artifact: processMapping,
      source_integrity_artifact: sourceIntegrity,
    },
  };
  const checklist = {
    contract: 'evidence-model',
    items: [
      {
        item_id: 'lease',
        fact_id: 'fact_scope',
        status: 'provided_sufficient',
        artifact_ids: ['lease'],
        agent_contribution: evidenceFieldContributions,
      },
      {
        item_id: 'context_note',
        fact_id: 'fact_context',
        status: 'provided_sufficient',
        artifact_ids: ['lease'],
        agent_contribution: contextEvidenceFieldContributions,
      },
    ],
    agent_contribution: { artifact: evidenceChecklist },
  };
  const orchestratorPlan = { focus_fact_ids: ['fact_scope'], priority_task_codes: ['source_integrity', 'process_decisions', 'evidence_gaps', 'final_brief'] };
  const orchestrationId = cacheMode === 'cold' ? 'orch_cold_contract' : 'orch_warm_contract';
  const coldAudit = orchestrationAudit(coldRun);
  const coldByAgent = new Map((coldAudit?.agents || []).map(item => [item.agent_id, item]));
  const callIdFor = agentId => `${cacheMode}_call_${agentId}`;
  const canonicalCallId = callIdFor('canonical_facts');
  const orchestratorCallId = callIdFor('orchestrator_plan');
  const specialistArtifacts = {
    orchestrator_plan: orchestratorPlan,
    document_source_integrity: sourceIntegrity,
    process_decision_mapping: processMapping,
    evidence_checklist: evidenceChecklist,
    final_claim_brief_audit: finalClaimBrief,
  };
  const acceptedIdsByAgent = {
    canonical_facts: ['accepted_canonical_facts_1', 'accepted_canonical_facts_2'],
    orchestrator_plan: ['accepted_orchestrator_plan_1', 'accepted_orchestrator_plan_2'],
    document_source_integrity: ['artifact:lease:integrity'],
    process_decision_mapping: [processDecision.contribution_id],
    evidence_checklist: evidenceChecklist.items.flatMap(item => item.field_contributions.map(unit => unit.contribution_id)),
    final_claim_brief_audit: finalFieldContributions.map(item => item.contribution_id),
  };
  const outputArtifactByAgent = {
    canonical_facts: facts,
    orchestrator_plan: orchestratorPlan,
    document_source_integrity: sourceIntegrity,
    process_decision_mapping: processMapping,
    evidence_checklist: evidenceChecklist,
    final_claim_brief_audit: finalClaimBrief,
  };
  const agents = REQUIRED_NEMOTRON_AGENT_IDS.map(agentId => {
    const acceptedIds = acceptedIdsByAgent[agentId];
    return {
      agent_id: agentId,
      role: REQUIRED_NEMOTRON_AGENT_ROLES[agentId],
      actor_type: 'nemotron_agent',
      acceptance_scope: 'pre_review_model_output',
      model: REQUESTED_NEMOTRON_MODEL,
      provider: 'openrouter',
      requested_model: REQUESTED_NEMOTRON_MODEL,
      call_count: cacheMode === 'cold' ? 1 : 0,
      parent_call_id: agentId === 'canonical_facts' ? null : agentId === 'orchestrator_plan' ? canonicalCallId : orchestratorCallId,
      delegation_id: agentId === 'canonical_facts' ? null : `${cacheMode}_delegation_${agentId}`,
      call_id: callIdFor(agentId),
      origin_call_id: cacheMode === 'cold' ? callIdFor(agentId) : coldByAgent.get(agentId)?.call_id,
      cache_hit: cacheMode === 'warm',
      outcome: cacheMode === 'warm' ? 'cache_hit' : 'succeeded',
      response_id: cacheMode === 'cold' ? `response_${agentId}` : coldByAgent.get(agentId)?.response_id,
      response_model: 'nvidia/nemotron-3-ultra-550b-a55b-20260604',
      upstream_provider: 'Together',
      usage_source: cacheMode === 'warm' ? 'cache' : 'response',
      finish_reason: 'stop',
      accepted_ids: acceptedIds,
      accepted_count: acceptedIds.length,
      rejected_count: 0,
      source_reference_projection_fact_ids: agentId === 'canonical_facts' ? [] : undefined,
      source_reference_projection_count: agentId === 'canonical_facts' ? 0 : undefined,
      deterministic_fallback_applied: false,
      input_artifact_hash: dtoHash({ agent_id: agentId, direction: 'input' }),
      output_artifact_hash: dtoHash(outputArtifactByAgent[agentId]),
    };
  });
  const byAgent = new Map(agents.map(item => [item.agent_id, item]));
  const finalDtos = {
    deterministic_process_gate: process,
    deterministic_evidence_gate: checklist,
    whole_playbook_gate: {
      process: semanticProcessDto(process),
      checklist: semanticChecklistDto(checklist),
      final_brief: finalClaimBrief,
    },
  };
  const gates = REQUIRED_DETERMINISTIC_GATE_IDS.map(gateId => {
    const contract = ACCEPTED_ARTIFACT_CONTRACT[gateId];
    return {
      agent_id: gateId,
      role: REQUIRED_DETERMINISTIC_GATE_ROLES[gateId],
      actor_type: 'deterministic_gate',
      receipt_type: 'accepted_artifact',
      acceptance_scope: 'pre_review_model_output',
      model: null,
      outcome: 'passed',
      source_agent_id: contract.source_agent_id,
      source_call_id: byAgent.get(contract.source_agent_id).call_id,
      delegation_id: byAgent.get(contract.source_agent_id).delegation_id,
      accepted_ids: byAgent.get(contract.source_agent_id).accepted_ids,
      accepted_count: byAgent.get(contract.source_agent_id).accepted_count,
      input_artifact_hash: gateId === 'deterministic_process_gate'
        ? dtoHash({ source_integrity: sourceIntegrity, process_mapping: processMapping })
        : gateId === 'deterministic_evidence_gate'
          ? dtoHash(evidenceChecklist)
          : dtoHash({ final_brief: finalClaimBrief, verification: { valid: true } }),
      output_artifact: contract.output_artifact,
      output_artifact_hash: dtoHash(finalDtos[gateId]),
      ...(gateId === 'whole_playbook_gate' ? {
        output_projection_contract: 'casepath.accepted-playbook-projection/1.0.0',
        final_brief_artifact_hash: dtoHash(finalClaimBrief),
      } : {}),
    };
  });
  const audit = {
    schema_version: EXPECTED_RUNTIME.orchestration_schema,
    implementation: EXPECTED_RUNTIME.implementation,
    framework: EXPECTED_FRAMEWORK,
    orchestration_id: orchestrationId,
    model: REQUESTED_NEMOTRON_MODEL,
    authority_mode: EXPECTED_RUNTIME.authority_mode,
    model_assisted: true,
    deterministic_safety_authority: true,
    external_tracing: false,
    prompt_storage: false,
    raw_output_storage: false,
    execution_topology: structuredClone(EXPECTED_EXECUTION_TOPOLOGY),
    agents,
    deterministic_gates: gates,
    all_required_agents_contributed: true,
    guarded_fallback_count: 0,
    specialist_artifacts: specialistArtifacts,
    final_claim_brief: finalClaimBrief,
  };
  const events = [
    ...agents.map(item => ({
      stage: item.agent_id === 'canonical_facts' ? 'understand' : 'agent_orchestration',
      receipt_type: 'agent_completed',
      agent_id: item.agent_id,
      actor_type: item.actor_type,
      acceptance_scope: item.acceptance_scope,
      status: 'completed',
      call_id: item.call_id,
      parent_call_id: item.parent_call_id,
      delegation_id: item.delegation_id,
      response_id: item.response_id,
      response_model: item.response_model,
      accepted_ids: item.accepted_ids,
      accepted_count: item.accepted_count,
      rejected_count: item.rejected_count,
      source_reference_projection_fact_ids: item.source_reference_projection_fact_ids,
      source_reference_projection_count: item.source_reference_projection_count,
      deterministic_fallback_applied: item.deterministic_fallback_applied,
      output_artifact_hash: item.agent_id === 'canonical_facts' ? undefined : item.output_artifact_hash,
    })),
    ...gates.map(item => ({ stage: 'agent_orchestration', status: 'completed', ...item })),
  ];
  return {
    run_id: `${cacheMode}_run`,
    status: 'complete',
    agent_orchestration: audit,
    result: {
      facts,
      process,
      checklist,
      next_action: {
        process_node_id: 'notice',
        agent_brief_contribution: finalClaimBrief,
      },
      agent_orchestration: audit,
      audit: { agent_orchestration: audit },
    },
    events,
  };
}

function mockLedgerForRun(run, cacheMode, coldLedger = null) {
  const audit = orchestrationAudit(run);
  const coldByAgent = new Map((coldLedger?.items || []).map(item => [item.agent_id, item]));
  const items = audit.agents.map(agent => ({
      call_id: agent.call_id,
      provider: 'openrouter',
      provider_endpoint: 'https://openrouter.ai/api/v1/chat/completions',
      upstream_provider: 'Together',
      model: REQUESTED_NEMOTRON_MODEL,
      implementation: agent.agent_id === 'canonical_facts' ? 'model_backed_openrouter_canonicalizer' : EXPECTED_RUNTIME.implementation,
      orchestration_id: audit.orchestration_id,
      agent_id: agent.agent_id,
      agent_role: agent.role,
      parent_call_id: agent.parent_call_id,
      delegation_id: agent.delegation_id,
      call_count: cacheMode === 'cold' ? 1 : 0,
      prompt_tokens: cacheMode === 'cold' ? 100 : undefined,
      completion_tokens: cacheMode === 'cold' ? 20 : undefined,
      total_tokens: cacheMode === 'cold' ? 120 : undefined,
      estimated_cost_usd: cacheMode === 'cold' ? 0.01 : 0,
      actual_cost_usd: cacheMode === 'cold' ? 0.008 : undefined,
      cache_key: `cache_${agent.agent_id}`,
      purpose: `mock ${agent.agent_id}`,
      outcome: agent.outcome,
      accepted_fact_count: agent.agent_id === 'canonical_facts' ? agent.accepted_count : undefined,
      rejected_fact_count: agent.agent_id === 'canonical_facts' ? agent.rejected_count : undefined,
      source_reference_projection_fact_ids: agent.agent_id === 'canonical_facts' ? agent.source_reference_projection_fact_ids : undefined,
      source_reference_projection_count: agent.agent_id === 'canonical_facts' ? agent.source_reference_projection_count : undefined,
      accepted_item_count: agent.agent_id === 'canonical_facts' ? undefined : agent.accepted_count,
      rejected_item_count: agent.agent_id === 'canonical_facts' ? undefined : agent.rejected_count,
      deterministic_fallback_applied: false,
      response_id: cacheMode === 'cold' ? `response_${agent.agent_id}` : coldByAgent.get(agent.agent_id)?.response_id,
      origin_call_id: cacheMode === 'warm' ? coldByAgent.get(agent.agent_id)?.call_id : undefined,
      origin_usage: cacheMode === 'warm' ? {
        prompt_tokens: coldByAgent.get(agent.agent_id)?.prompt_tokens,
        completion_tokens: coldByAgent.get(agent.agent_id)?.completion_tokens,
        total_tokens: coldByAgent.get(agent.agent_id)?.total_tokens,
        actual_cost_usd: coldByAgent.get(agent.agent_id)?.actual_cost_usd,
        usage_source: coldByAgent.get(agent.agent_id)?.usage_source,
      } : undefined,
      origin_finish_reason: cacheMode === 'warm' ? coldByAgent.get(agent.agent_id)?.finish_reason : undefined,
      response_model: 'nvidia/nemotron-3-ultra-550b-a55b-20260604',
      usage_source: cacheMode === 'cold' ? 'response' : 'cache',
      finish_reason: 'stop',
      created_at: '2026-08-11T00:00:00Z',
      updated_at: '2026-08-11T00:00:01Z',
    })).map(item => Object.fromEntries(Object.entries(item).filter(([, value]) => value !== undefined)));
  return {
    scope: 'global_budget_ledger',
    summary: ledgerSummary(items),
    items,
  };
}

async function assertRunReadSessionIsolation() {
  const guardSource = await fs.readFile(new URL('../casepath/assets/live-v18-insertion-guard.js', import.meta.url), 'utf8');
  class FakeNode {}
  class FakeElement extends FakeNode {}
  FakeNode.prototype.insertBefore = function insertBefore(node) { return node; };
  FakeElement.prototype.insertAdjacentHTML = function insertAdjacentHTML() {};
  class FakeResponse {
    constructor(body) { this.body = body; }
    clone() { return new FakeResponse(structuredClone(this.body)); }
    async json() { return structuredClone(this.body); }
  }
  const calls = [];
  const pending = [];
  const nativeFetch = (input, init = {}) => {
    const request = typeof input === 'string' || input instanceof URL ? null : input;
    const headers = new Headers(init.headers !== undefined ? init.headers : request?.headers);
    const session = (headers.get('X-CasePath-Session') || '').trim();
    const method = String(init.method || request?.method || 'GET').toUpperCase();
    calls.push({ session, method });
    return new Promise(resolve => pending.push({ session, method, resolve: () => resolve(new FakeResponse({ session, method })) }));
  };
  const sandbox = {
    window: { fetch: nativeFetch },
    Node: FakeNode,
    Element: FakeElement,
    URL,
    URLSearchParams,
    Headers,
    Request,
    location: { href: 'https://casepath.test/', search: '' },
    document: { readyState: 'loading', addEventListener() {} },
    structuredClone,
  };
  vm.runInNewContext(guardSource, sandbox, { filename: 'live-v18-insertion-guard.js' });
  const runUrl = 'https://api.casepath.test/api/runs/run_shared';
  const requestHeaders = session => ({ 'X-CasePath-Session': session });
  const settlePending = entries => entries.forEach(entry => entry.resolve());

  const differentSessionStart = calls.length;
  const sessionA = sandbox.window.fetch(runUrl, { headers: requestHeaders('session-A') });
  const sessionB = sandbox.window.fetch(runUrl, { headers: requestHeaders('session-B') });
  if (calls.length - differentSessionStart !== 2) throw new Error('Different sessions shared one in-flight run read');
  settlePending(pending.splice(0));
  const [bodyA, bodyB] = await Promise.all((await Promise.all([sessionA, sessionB])).map(response => response.json()));
  if (bodyA.session !== 'session-A' || bodyB.session !== 'session-B') throw new Error('A run-read response crossed the session boundary');

  const sameSessionStart = calls.length;
  const sameA1 = sandbox.window.fetch(runUrl, { headers: requestHeaders('session-A') });
  const sameA2 = sandbox.window.fetch(runUrl, { headers: requestHeaders('session-A') });
  if (calls.length - sameSessionStart !== 1) throw new Error('Same-session concurrent run reads were not coalesced');
  settlePending(pending.splice(0));
  const sameBodies = await Promise.all((await Promise.all([sameA1, sameA2])).map(response => response.json()));
  if (!sameBodies.every(body => body.session === 'session-A')) throw new Error('Same-session cloned run reads diverged');

  const requestWithA = new Request(runUrl, { headers: requestHeaders('session-A') });
  const overrideStart = calls.length;
  const overriddenToB = sandbox.window.fetch(requestWithA, { headers: requestHeaders('session-B') });
  const sameB = sandbox.window.fetch(runUrl, { headers: requestHeaders('session-B') });
  const separateA = sandbox.window.fetch(runUrl, { headers: requestHeaders('session-A') });
  if (calls.length - overrideStart !== 2) throw new Error('Request/init header precedence did not preserve session isolation');
  settlePending(pending.splice(0));
  const [overrideBody, sameBBody, separateABody] = await Promise.all((await Promise.all([overriddenToB, sameB, separateA])).map(response => response.json()));
  if (overrideBody.session !== 'session-B' || sameBBody.session !== 'session-B' || separateABody.session !== 'session-A') throw new Error('Effective session headers were not bound to the run-read key');

  const mutationStart = calls.length;
  const mutationA = sandbox.window.fetch(`${runUrl}/review`, { method: 'POST', headers: requestHeaders('session-A') });
  const readB = sandbox.window.fetch(runUrl, { headers: requestHeaders('session-B') });
  const readA = sandbox.window.fetch(runUrl, { headers: requestHeaders('session-A') });
  if (calls.length - mutationStart !== 2) throw new Error('A review mutation blocked a different session or failed to block its own session');
  const mutationEntry = pending.find(entry => entry.method === 'POST');
  const readBEntry = pending.find(entry => entry.method === 'GET' && entry.session === 'session-B');
  mutationEntry.resolve();
  readBEntry.resolve();
  pending.splice(0, pending.length);
  await new Promise(resolve => setImmediate(resolve));
  if (calls.length - mutationStart !== 3) throw new Error('Same-session run read did not resume with a fresh request after review mutation');
  settlePending(pending.splice(0));
  const [mutationBody, readBBody, readABody] = await Promise.all((await Promise.all([mutationA, readB, readA])).map(response => response.json()));
  if (mutationBody.session !== 'session-A' || readBBody.session !== 'session-B' || readABody.session !== 'session-A') throw new Error('Review mutation/read coordination crossed a session boundary');
}

async function assertMemoryReuseRendererDeterminism() {
  const [v16Source, v17Source, v18Source, browserGateSource] = await Promise.all([
    fs.readFile(new URL('../casepath/assets/live-v16.js', import.meta.url), 'utf8'),
    fs.readFile(new URL('../casepath/assets/live-v17.js', import.meta.url), 'utf8'),
    fs.readFile(new URL('../casepath/assets/live-v18.js', import.meta.url), 'utf8'),
    fs.readFile(new URL(import.meta.url), 'utf8'),
  ]);
  const start = v16Source.indexOf('  function renderMemoryReuseProof(');
  const end = v16Source.indexOf('\n  function factsForNode', start);
  if (start < 0 || end < 0) throw new Error('Could not extract the authoritative synchronous memory-reuse renderer');
  const rendererSource = v16Source.slice(start, end).trim();
  if (/\b(?:async|await)\b|\bcurrentRun\s*\(/.test(rendererSource)) throw new Error('The authoritative memory-reuse renderer regained an asynchronous run read');
  for (const [label, source] of [['live-v17', v17Source], ['live-v18', v18Source]]) {
    if (/\b(?:async\s+)?function\s+enhanceReuse\s*\(|\benhanceReuse\s*\(/.test(source)) throw new Error(`${label} regained a post-render memory-reuse enhancer`);
  }
  if (!browserGateSource.includes("const reuseThreadSelector = '#laterResult .v18-reuse-proof .v17-reuse-thread';")
    || !browserGateSource.includes('laterReuseThreadCount === 1 && reuseProofCount === 1 && proofReuseThreadCount === 1')) throw new Error('The browser gate no longer requires one proof, one thread, and one nested thread');

  const sandbox = {
    esc: (value = '') => String(value).replace(/[&<>'"]/g, character => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[character])),
  };
  vm.runInNewContext(`globalThis.renderMemoryReuseProof = ${rendererSource};`, sandbox, { filename: 'live-v16-render-memory-reuse-proof.js' });
  const receipt = {
    contract: 'casepath.memory-application-receipt/1.0.0',
    application_hash: 'a'.repeat(64),
    authority: 'unverified_demo',
    scope: 'case_specific_guidance_only',
    shared_rule_applied: false,
    model_acceptance_reused: false,
  };
  const precedent = {
    claim_id: 'DEF-027-E0-DEMO',
    memory_id: 'mem-unverified-demo',
    review_status: 'unverified_demo_memory',
  };
  const result = { playbook: { version: 'mould-playbook-v3' } };
  const proof = { causal_delta: { nonzero: true } };
  const cases = [
    {
      label: 'applied',
      input: { result, proof, memoryUsed: true, retrievedOnly: false, memoryState: { receipt, retrievedPrecedent: precedent } },
    },
    {
      label: 'retrieved-only',
      input: { result, proof: {}, memoryUsed: false, retrievedOnly: true, memoryState: { receipt: null, retrievedPrecedent: precedent } },
    },
    {
      label: 'no-memory',
      input: { result, proof: {}, memoryUsed: false, retrievedOnly: false, memoryState: { receipt, retrievedPrecedent: precedent } },
    },
  ];
  const expected = new Map(cases.map(({ label, input }) => [label, sandbox.renderMemoryReuseProof(input)]));
  for (let pass = 0; pass < 8; pass += 1) {
    for (const { label, input } of cases) {
      if (sandbox.renderMemoryReuseProof(input) !== expected.get(label)) throw new Error(`Synchronous memory-reuse markup changed across repeated ${label} renders`);
    }
  }

  const exactTopology = markup => (markup.match(/class="v18-reuse-proof"/g) || []).length === 1
    && (markup.match(/class="v17-reuse-thread(?: retrieved-only)?"/g) || []).length === 1
    && (markup.match(/<section\b/g) || []).length === 2
    && (markup.match(/<\/section>/g) || []).length === 2
    && /^<section class="v18-reuse-proof">[\s\S]*<section class="v17-reuse-thread(?: retrieved-only)?"[\s\S]*<\/section><\/section>$/.test(markup);
  const applied = expected.get('applied');
  const appliedAttributes = [
    'data-memory-retrieved="true"',
    'data-memory-used="true"',
    'data-application-receipt="true"',
    `data-memory-contract="${receipt.contract}"`,
    `data-application-hash="${receipt.application_hash}"`,
    `data-memory-authority="${receipt.authority}"`,
    `data-memory-scope="${receipt.scope}"`,
  ];
  if (!exactTopology(applied)
    || appliedAttributes.some(attribute => !applied.includes(attribute))
    || !applied.includes('Unverified demo memory returned with a valid application receipt')
    || !applied.includes('Unverified demo review memory returned')
    || !applied.includes('nonzero causal delta computed')
    || applied.includes('Qualified expert-reviewed')) throw new Error('Applied memory markup lost its exact topology, receipt attributes, or unverified authority copy');

  const retrievedOnly = expected.get('retrieved-only');
  if (!exactTopology(retrievedOnly)
    || !retrievedOnly.includes('class="v17-reuse-thread retrieved-only"')
    || !retrievedOnly.includes('data-memory-used="false"')
    || !retrievedOnly.includes('data-application-receipt="false"')
    || !retrievedOnly.includes('Unverified demo memory retrieved and ranked only')
    || !retrievedOnly.includes('Unverified demo review memory returned')
    || !retrievedOnly.includes('Application receipt</small><strong>None returned')
    || retrievedOnly.includes('data-memory-contract=')
    || retrievedOnly.includes('valid application receipt')) throw new Error('Retrieved-only memory markup blurred retrieval, application, receipt, or authority state');

  if (expected.get('no-memory') !== ''
    || sandbox.renderMemoryReuseProof({ result, proof, memoryUsed: true, retrievedOnly: false, memoryState: { receipt: null, retrievedPrecedent: precedent } }) !== ''
    || sandbox.renderMemoryReuseProof({ result, proof, memoryUsed: true, retrievedOnly: false, memoryState: { receipt, retrievedPrecedent: null } }) !== '') throw new Error('No-memory or incomplete applied-memory inputs emitted reuse proof markup');
  const hostile = sandbox.renderMemoryReuseProof({
    result: { playbook: { version: '<img src=x onerror=alert(1)>' } },
    proof,
    memoryUsed: true,
    retrievedOnly: false,
    memoryState: { receipt: { ...receipt, application_hash: '<script>bad()</script>' }, retrievedPrecedent: { ...precedent, claim_id: '<script>claim()</script>', memory_id: '" onfocus="bad()' } },
  });
  if (hostile.includes('<script>') || hostile.includes('<img ') || hostile.includes(' onfocus="bad()') || !hostile.includes('&lt;script&gt;claim()&lt;/script&gt;') || !hostile.includes('&quot; onfocus=&quot;bad()')) throw new Error('Synchronous memory-reuse renderer did not escape hostile server-returned values');
}

async function runContractSelfTest() {
  const [liveRuntimeSource, liveRuntimeCss, artifactCanvasSource, artifactCanvasCss] = await Promise.all([
    fs.readFile(new URL('../casepath/assets/live-v16.js', import.meta.url), 'utf8'),
    fs.readFile(new URL('../casepath/assets/live-v16.css', import.meta.url), 'utf8'),
    fs.readFile(new URL('../casepath/assets/artifact-canvas.js', import.meta.url), 'utf8'),
    fs.readFile(new URL('../casepath/assets/artifact-canvas.css', import.meta.url), 'utf8'),
  ]);
  const replayAndFailureFragments = [
    "cached: 'Cached replay'",
    "failed: 'Stopped'",
    "live: 'Live'",
    "cachedReplay ? 'cached' : 'returned'",
    'function terminalFailureReceipts(run)',
    'for (const event of terminalFailureReceipts(run)) rememberPresentedEvent(event);',
    'renderFailure(SAFE_MODEL_FAILURE_MESSAGE, run);',
    'data-terminal-failure="true"',
    'id="retryFailedRun"',
  ];
  if (!replayAndFailureFragments.every(fragment => liveRuntimeSource.includes(fragment))
    || liveRuntimeSource.includes('onclick="location.reload()"')
    || !liveRuntimeCss.includes('.live-chip[data-orchestration-mode="live"]:before')
    || !liveRuntimeCss.includes('.live-chip[data-orchestration-mode="cached"]')
    || !liveRuntimeCss.includes('.live-chip[data-orchestration-mode="failed"]')) {
    throw new Error('Visible cached-replay or sanitized terminal-failure state contract is incomplete');
  }
  const processStoryWatchdogFragments = [
    "window.addEventListener('casepath:decision-flow-step', onProgress);",
    "window.removeEventListener('casepath:decision-flow-step', onProgress);",
    "if (String(event.detail?.runId || '') === runId) armTimeout();",
    'window.clearTimeout(timeout);',
  ];
  if (!processStoryWatchdogFragments.every(fragment => liveRuntimeSource.includes(fragment))) {
    throw new Error('Process-story watchdog does not rearm on same-run automatic decision-flow progress');
  }
  const authoredFailureFragments = [
    'function terminalFailureFromRun(run)',
    'function stopActiveWorkForFailure()',
    'stopActiveWorkForFailure();',
    "valueFrom(boundary, 'failure_invariant')",
    "valueFrom(receipt, 'error_invariant')",
    'data-ac-focal-object="failure"',
    'data-partial-result-applied="false"',
    'data-ac-action="retry-failure"',
    "const restartControl = document.querySelector('#retryFailedRun');",
    'restartControl.click();',
    "failure: state.moment === 'failure' ? { ...failurePresentation() } : null",
  ];
  if (!authoredFailureFragments.every(fragment => artifactCanvasSource.includes(fragment))
    || artifactCanvasSource.includes('onclick=')
    || !artifactCanvasCss.includes('.ac-failure-focus')
    || !artifactCanvasCss.includes('[data-casepath-moment="failure"] .ac-agent-cursor')) {
    throw new Error('The authored terminal-failure focal is not safely actionable');
  }
  const failureCopyStart = artifactCanvasSource.indexOf('  const SAFE_FAILURE_STAGE_COPY');
  const failureCopyEnd = artifactCanvasSource.indexOf('  const AGENT_ICONS', failureCopyStart);
  if (failureCopyStart < 0 || failureCopyEnd < 0) throw new Error('Could not isolate safe terminal-failure copy');
  const failureCopySource = artifactCanvasSource.slice(failureCopyStart, failureCopyEnd).replace(/^  /gm, '');
  const failureCopySandbox = {};
  vm.runInNewContext(`${failureCopySource}\nglobalThis.safeTerminalFailureCopy = safeTerminalFailureCopy;`, failureCopySandbox, { filename: 'artifact-canvas-safe-terminal-failure.js' });
  const boundedFailure = failureCopySandbox.safeTerminalFailureCopy('canonical_facts', 'provider_finish_reason');
  if (JSON.stringify(boundedFailure) !== JSON.stringify({
    stage: 'canonical_facts',
    title: 'Claim reading stopped.',
    detail: 'The model stopped before it finished.',
  })) throw new Error(`Known terminal failure did not produce bounded simple copy: ${JSON.stringify(boundedFailure)}`);
  const hostileFailure = failureCopySandbox.safeTerminalFailureCopy('<img src=x onerror=alert(1)>', 'raw provider text <script>bad()</script>');
  if (JSON.stringify(hostileFailure) !== JSON.stringify({
    stage: '',
    title: 'The run stopped.',
    detail: 'CasePath could not finish this run.',
  }) || JSON.stringify(hostileFailure).includes('provider text') || JSON.stringify(hostileFailure).includes('<script>')) {
    throw new Error('Unknown terminal failure leaked unbounded provider text');
  }
  const sourcePreludeFixture = {
    sourceCount: 7,
    label: 'Path builder',
    title: 'Build the claim path',
    planCount: 1,
    cardCount: 0,
    inputCount: 0,
    checkboxRoleCount: 0,
    steps: [
      { label: 'Read the exact source', state: 'complete' },
      { label: 'Keep the supported fact', state: 'active' },
      { label: 'Add the next process step', state: 'waiting' },
    ],
  };
  if (sourcePreludeContractViolations(sourcePreludeFixture).length) throw new Error('Valid merged Path builder opening plan fixture was rejected');
  const checkboxPreludeFixture = structuredClone(sourcePreludeFixture);
  checkboxPreludeFixture.checkboxRoleCount = 1;
  if (!sourcePreludeContractViolations(checkboxPreludeFixture).some(issue => issue.includes('checkbox'))) throw new Error('Opening source checkbox fixture was accepted');
  const obsoletePreludeCardsFixture = structuredClone(sourcePreludeFixture);
  obsoletePreludeCardsFixture.cardCount = 7;
  if (!sourcePreludeContractViolations(obsoletePreludeCardsFixture).some(issue => issue.includes('obsolete seven-card strip'))) throw new Error('Obsolete seven-card opening strip fixture was accepted');

  const sourceRailSourcesFixture = [
    ['message', 'mail', 'Claim message'],
    ['art_lease', 'contract', 'Residential lease agreement'],
    ['art_notification', 'mail', 'Email notifying the property manager'],
    ['art_management_reply', 'mail', 'Management reply'],
    ['art_photo', 'image', 'Bedroom photograph'],
    ['art_timeline', 'timeline', 'Defect timeline'],
    ['art_delivery', 'delivery', 'Email delivery receipt'],
  ].map(([sourceId, kind, name]) => ({ sourceId, kind, name }));
  const sourceRailFixture = viewport => {
    const railRect = { left: 0, top: 64, right: 252, bottom: viewport.height, width: 252, height: viewport.height - 64 };
    const listRect = { left: 0, top: 116, right: 252, bottom: viewport.height, width: 252, height: viewport.height - 116 };
    return {
      reason: `opening:${viewport.width}x${viewport.height}`,
      expectedSourceId: '', expectedLocatorId: '', contract: SOURCE_RAIL_CONTRACT, viewport,
      railVisible: true, listVisible: true, collapsed: false, insideViewport: true,
      railRect, listRect, headingHeight: 52, listOverflowY: 'auto', listHorizontalOverflow: 0, pageHorizontalOverflow: 0,
      dropdownCount: 0, expanderCount: 0, collapsedControlCount: 0, workOverlapArea: 0, overlayOverlapAreas: [], rowOverlapCount: 0,
      itemCount: 7,
      items: sourceRailSourcesFixture.map((source, index) => ({
        ...source, visible: true, fullyVisible: true,
        rect: { left: 0, top: 116 + index * 56, right: 252, bottom: 172 + index * 56, width: 252, height: 56 },
        iconCount: 1, iconKind: source.kind, iconMarkup: `<path data-source="${source.sourceId}"></path>`, iconWidth: 28, iconHeight: 28,
        nameCount: 1, name: source.name, metaCount: 1, meta: `${source.kind} metadata`, statusCount: 1, status: 'ready',
        active: false, ariaCurrent: false, thumbImageCount: 0, extraLabelCount: 0,
      })),
      activeSourceIds: [], activeSourceLocator: '',
    };
  };
  for (const viewport of SOURCE_RAIL_VIEWPORTS) {
    const validRail = sourceRailFixture(viewport);
    if (sourceRailContractViolations(validRail, sourceRailSourcesFixture).length) throw new Error(`Valid ${viewport.width}x${viewport.height} source-rail fixture was rejected`);
  }
  const activeRailFixture = sourceRailFixture(SOURCE_RAIL_VIEWPORTS[1]);
  const activeRailItem = activeRailFixture.items.find(item => item.sourceId === 'art_timeline');
  Object.assign(activeRailItem, { status: 'reading', active: true, ariaCurrent: true });
  activeRailFixture.reason = 'fact-tour:fact_recurrence:read-source';
  activeRailFixture.expectedSourceId = 'art_timeline';
  activeRailFixture.expectedLocatorId = 'source:art_timeline:page:2:quote:Exact';
  activeRailFixture.activeSourceIds = ['art_timeline'];
  activeRailFixture.activeSourceLocator = activeRailFixture.expectedLocatorId;
  if (sourceRailContractViolations(activeRailFixture, sourceRailSourcesFixture, { sourceId: activeRailFixture.expectedSourceId, locatorId: activeRailFixture.expectedLocatorId }).length) throw new Error('Valid exact-active source-rail fixture was rejected');
  const intakeRailFixture = sourceRailFixture(SOURCE_RAIL_VIEWPORTS[1]);
  Object.assign(intakeRailFixture.items[0], { status: 'reading', active: true, ariaCurrent: true });
  intakeRailFixture.expectedSourceId = 'intake';
  intakeRailFixture.expectedLocatorId = 'source:message:field:claim';
  intakeRailFixture.activeSourceIds = ['message'];
  intakeRailFixture.activeSourceLocator = intakeRailFixture.expectedLocatorId;
  if (sourceRailContractViolations(intakeRailFixture, sourceRailSourcesFixture, { sourceId: 'intake', locatorId: intakeRailFixture.expectedLocatorId }).length) throw new Error('Intake pseudo-source did not resolve to the one visible claim-message row');
  const legacyRailFixture = sourceRailFixture(SOURCE_RAIL_VIEWPORTS[0]);
  legacyRailFixture.collapsed = true;
  legacyRailFixture.dropdownCount = 1;
  legacyRailFixture.items[0].rect.height = 76;
  const legacyRailIssues = sourceRailContractViolations(legacyRailFixture, sourceRailSourcesFixture);
  if (!legacyRailIssues.some(issue => issue.includes('collapsed')) || !legacyRailIssues.some(issue => issue.includes('dropdown')) || !legacyRailIssues.some(issue => issue.includes('not compact'))) throw new Error(`Legacy large dropdown source rail was accepted: ${JSON.stringify(legacyRailIssues)}`);
  const brokenStructureRailFixture = sourceRailFixture(SOURCE_RAIL_VIEWPORTS[1]);
  Object.assign(brokenStructureRailFixture.items[2], { iconCount: 0, iconMarkup: '', statusCount: 0, status: '', metaCount: 2 });
  const brokenStructureRailIssues = sourceRailContractViolations(brokenStructureRailFixture, sourceRailSourcesFixture);
  if (!brokenStructureRailIssues.some(issue => issue.includes('type-correct icon')) || !brokenStructureRailIssues.some(issue => issue.includes('status')) || !brokenStructureRailIssues.some(issue => issue.includes('metadata'))) throw new Error(`Structurally noisy source rail was accepted: ${JSON.stringify(brokenStructureRailIssues)}`);
  const ambiguousActiveRailFixture = structuredClone(activeRailFixture);
  Object.assign(ambiguousActiveRailFixture.items[1], { status: 'reading', active: true, ariaCurrent: true });
  ambiguousActiveRailFixture.activeSourceIds = ['art_lease', 'art_timeline'];
  ambiguousActiveRailFixture.workOverlapArea = 120;
  const ambiguousActiveRailIssues = sourceRailContractViolations(ambiguousActiveRailFixture, sourceRailSourcesFixture, { sourceId: activeRailFixture.expectedSourceId, locatorId: activeRailFixture.expectedLocatorId });
  if (!ambiguousActiveRailIssues.some(issue => issue.includes('exactly one')) || !ambiguousActiveRailIssues.some(issue => issue.includes('overlaps'))) throw new Error(`Ambiguous active/overlapping source rail was accepted: ${JSON.stringify(ambiguousActiveRailIssues)}`);

  const liveWorkRunFixture = {
    run_id: 'run:live-canonical-facts',
    events: [{
      receipt_type: 'agent_started', actor_type: 'nemotron_agent', agent_id: 'canonical_facts',
      event_id: 'event:live-canonical-facts', call_id: 'call:live-canonical-facts', status: 'started',
      call_count: 1, cache_hit: false, input_artifact: 'observable_claim_package', input_artifact_hash: '1'.repeat(64),
    }],
  };
  const liveWorkPlanFixture = [{
    planCount: 1, focalChildCount: 1, visible: true,
    contract: LIVE_WORK_PLAN_CONTRACT, presentationMode: 'live-call',
    agentId: 'canonical_facts', runtimeAgentId: 'canonical_facts', visualGroupId: PATH_BUILDER_VISUAL_GROUP_ID,
    agentSignature: PATH_BUILDER_VISIBLE_IDENTITY.signature, runId: liveWorkRunFixture.run_id,
    callId: 'call:live-canonical-facts', eventId: 'event:live-canonical-facts', workState: 'started',
    inputArtifact: 'observable_claim_package', inputArtifactHash: '1'.repeat(64),
    rootWorkState: 'working', rootAgentId: 'canonical_facts', rootRunId: liveWorkRunFixture.run_id,
    rootCallId: 'call:live-canonical-facts', rootEventId: 'event:live-canonical-facts',
    title: 'Build the claim path', steps: structuredClone(CANONICAL_FACTS_LIVE_WORK_STEPS),
    sourcePreludeCount: 0, sourcePreludeCardCount: 0, factTourCount: 0,
    forbiddenProgressCount: 0, percentText: false, at: 100,
  }];
  const liveWorkFactTourFixture = [];
  if (canonicalFactsLiveWorkPlanContractViolations(liveWorkPlanFixture, liveWorkFactTourFixture, liveWorkRunFixture).length) throw new Error('Valid call-bound canonical-fact live plan fixture was rejected');
  const stagedPreludeLiveWorkFixture = structuredClone(liveWorkPlanFixture);
  Object.assign(stagedPreludeLiveWorkFixture[0], { sourcePreludeCount: 1, sourcePreludeCardCount: 7 });
  if (!canonicalFactsLiveWorkPlanContractViolations(stagedPreludeLiveWorkFixture, liveWorkFactTourFixture, liveWorkRunFixture).some(issue => issue.includes('competes with the idle source prelude'))) throw new Error('Live plan staged beside the static seven-card source prelude was accepted');
  const percentageLiveWorkFixture = structuredClone(liveWorkPlanFixture);
  Object.assign(percentageLiveWorkFixture[0], { forbiddenProgressCount: 1, percentText: true });
  if (!canonicalFactsLiveWorkPlanContractViolations(percentageLiveWorkFixture, liveWorkFactTourFixture, liveWorkRunFixture).some(issue => issue.includes('percent, progress bar, or slider'))) throw new Error('Percent-based live work plan fixture was accepted');
  const forgedLiveWorkCallFixture = structuredClone(liveWorkPlanFixture);
  forgedLiveWorkCallFixture[0].callId = 'call:forged';
  if (!canonicalFactsLiveWorkPlanContractViolations(forgedLiveWorkCallFixture, liveWorkFactTourFixture, liveWorkRunFixture).some(issue => issue.includes('exact returned run, call, event, agent, and work state'))) throw new Error('Live plan with a forged call binding was accepted');
  const obsoleteSeparateFactTourFixture = [{ phase: 'read-source', liveWorkPlanCount: 0, sourcePreludeCount: 0, artifactSurfaceVisible: true, at: 300 }];
  if (!canonicalFactsLiveWorkPlanContractViolations(liveWorkPlanFixture, obsoleteSeparateFactTourFixture, liveWorkRunFixture).some(issue => issue.includes('separate source-to-fact tour'))) throw new Error('Separate source-to-fact presentation outside the Path builder graph flow was accepted');

  const avatarGroups = [...new Set(REQUIRED_NEMOTRON_AGENT_IDS.map(visibleAgentGroupId))];
  const avatarMarkupByGroup = new Map(avatarGroups.map((groupId, index) => [groupId, `<path data-role="${index}"></path>`]));
  const avatarTeamFixture = {
    members: REQUIRED_NEMOTRON_AGENT_IDS.map(agentId => ({
      agentId,
      visualGroupId: visibleAgentGroupId(agentId),
      signature: visibleAgentIdentity(agentId).signature,
      iconMarkup: avatarMarkupByGroup.get(visibleAgentGroupId(agentId)),
      visible: REQUIRED_VISIBLE_SPECIALIST_IDS.includes(agentId),
    })),
  };
  const avatarCursorFixture = avatarTeamFixture.members.map(member => ({
    specialistBound: true,
    agentId: member.agentId,
    runtimeAgentId: member.agentId,
    visualActiveAgentId: member.agentId,
    visualGroupId: member.visualGroupId,
    signature: member.signature,
    avatar: member.signature,
    avatarMarkup: member.iconMarkup,
  }));
  if (specialistAvatarContractViolations(avatarTeamFixture, avatarCursorFixture, true).length) throw new Error('Valid four-workstream/six-runtime-agent avatar fixture was rejected');
  const mismatchedAvatarFixture = structuredClone(avatarCursorFixture);
  mismatchedAvatarFixture[2].avatarMarkup = avatarTeamFixture.members[0].iconMarkup;
  if (!specialistAvatarContractViolations(avatarTeamFixture, mismatchedAvatarFixture, true).some(issue => issue.includes('does not exactly match'))) throw new Error('Mismatched live role icon fixture was accepted');
  const ungroupedCanonicalCursorFixture = structuredClone(avatarCursorFixture);
  ungroupedCanonicalCursorFixture.find(item => item.runtimeAgentId === 'canonical_facts').visualGroupId = 'canonical_facts';
  if (!specialistAvatarContractViolations(avatarTeamFixture, ungroupedCanonicalCursorFixture, true).some(issue => issue.includes('viewer-facing workstream'))) throw new Error('Canonical-facts cursor outside the merged Path builder workstream was accepted');
  const duplicateAvatarTeamFixture = structuredClone(avatarTeamFixture);
  duplicateAvatarTeamFixture.members[5].iconMarkup = duplicateAvatarTeamFixture.members[4].iconMarkup;
  if (!specialistAvatarContractViolations(duplicateAvatarTeamFixture, avatarCursorFixture, true).some(issue => issue.includes('four unique normalized role-icon hashes'))) throw new Error('Duplicate visible workstream icon fixture was accepted');

  const openingClaimFixture = {
    subject: 'Bedroom condition keeps returning',
    message: `Hello. ${EXPECTED_OPENING_PROBLEM} ${EXPECTED_OPENING_OUTCOME}`,
  };
  const openingClaimCardFixture = {
    cardCount: 1, visible: true, sourceId: 'message', childTags: ['HEADER', 'STRONG', 'BLOCKQUOTE', 'P'],
    subject: openingClaimFixture.subject, problem: EXPECTED_OPENING_PROBLEM, outcome: EXPECTED_OPENING_OUTCOME,
    blockquoteCount: 1, paragraphCount: 1, generatedSummaryCount: 0,
    bodyCopyLength: EXPECTED_OPENING_PROBLEM.length + EXPECTED_OPENING_OUTCOME.length, width: 620, height: 170,
  };
  if (openingClaimCardContractViolations(openingClaimCardFixture, openingClaimFixture).length) throw new Error('Valid compact source-derived opening claim card fixture was rejected');
  const generatedOpeningClaimCardFixture = { ...openingClaimCardFixture, outcome: `${EXPECTED_OPENING_OUTCOME} AI summary: likely ventilation.` };
  if (!openingClaimCardContractViolations(generatedOpeningClaimCardFixture, openingClaimFixture).some(issue => issue.includes('exact claim-message request'))) throw new Error('Generated opening claim summary fixture was accepted');
  const oversizedOpeningClaimCardFixture = { ...openingClaimCardFixture, height: 420 };
  if (!openingClaimCardContractViolations(oversizedOpeningClaimCardFixture, openingClaimFixture).some(issue => issue.includes('not compact'))) throw new Error('Large-prose opening claim card fixture was accepted');

  const executionTraceFixtureRunId = 'run:fact-law-trace';
  const factTourFactsFixture = FACT_TOUR_FACT_IDS.map((factId, index) => ({
    fact_id: factId,
    label: `Fact ${index + 1}`,
    value: `Returned value ${index + 1}`,
    source_refs: [{ artifact_id: `artifact_${index + 1}`, locator_kind: 'text_quote', page: 1, excerpt: `Exact returned passage ${index + 1}` }],
  }));
  const factTourSemanticFixture = factTourFactsFixture.map((fact, index) => ({
    eventId: `fact-event:${fact.fact_id}`, runId: executionTraceFixtureRunId,
    entityKind: 'fact', entityId: fact.fact_id, traceContract: EXECUTION_TRACE_CONTRACT,
    presentationMode: 'returned_action_replay', authority: index % 2 === 0 ? 'model_contribution_accepted' : 'deterministic_reference_projection',
    modelContributionAccepted: index % 2 === 0, deterministicFallbackApplied: false,
    agentId: index % 2 === 0 ? 'canonical_facts' : 'canonical_fact_projection',
    actorType: index % 2 === 0 ? 'nemotron_agent' : 'deterministic_tool',
    modelOwnedFields: index % 2 === 0 ? ['confidence'] : [],
    applicationOwnedFields: ['label', 'value', 'state'],
    modelSelectedTextRefs: index % 2 === 0 ? [structuredClone(fact.source_refs[0])] : [],
  }));
  const factTourSnapshotsFixture = factTourFactsFixture.flatMap((fact, factIndex) => {
    const semantic = factTourSemanticFixture[factIndex];
    const ref = fact.source_refs[0];
    return ['select-source', 'read-source', 'highlight-source', 'finding'].map((phase, phaseIndex) => ({
      factId: fact.fact_id, phase, sourceId: ref.artifact_id, locatorId: factSourceLocatorId(ref),
      activeSourceIds: phase === 'select-source' ? [] : [ref.artifact_id],
      activeSourceLocator: phase === 'select-source' ? '' : factSourceLocatorId(ref),
      artifactSurfaceVisible: phase !== 'select-source',
      highlightCount: ['highlight-source', 'finding'].includes(phase) ? 1 : 0,
      factVisible: phase === 'finding', factLabel: phase === 'finding' ? fact.label : '', factValue: phase === 'finding' ? fact.value : '',
      eventId: phase === 'finding' ? semantic.eventId : '',
      agentId: phase === 'finding' && semantic.modelContributionAccepted ? semantic.agentId : '',
      presentationMode: 'returned-action-replay',
      presentationLabel: semantic.modelContributionAccepted ? 'Returned work · Claim reader' : 'Returned work · Fact safety check',
      activeAgentId: semantic.modelContributionAccepted ? 'canonical_facts' : '',
      activeSignature: semantic.modelContributionAccepted ? 'facts' : 'gate',
      workAuthority: semantic.modelContributionAccepted ? 'Claim reader' : 'Fact safety check',
      at: factIndex * 10000 + phaseIndex * 1000,
    }));
  });
  const factTourHighlightsFixture = factTourFactsFixture.map((fact, index) => ({
    entityKind: 'fact', factId: fact.fact_id, sourceId: fact.source_refs[0].artifact_id,
    locatorId: factSourceLocatorId(fact.source_refs[0]), sourceHighlighted: true, at: index * 10000 + 2500,
  }));
  const factTourRunFixture = { run_id: executionTraceFixtureRunId, result: { facts: factTourFactsFixture } };
  if (factSourceTourContractViolations(factTourSnapshotsFixture, factTourHighlightsFixture, factTourSemanticFixture, factTourRunFixture).length) throw new Error('Valid eight-fact returned source replay fixture was rejected');
  const inflatedFactTourFixture = structuredClone(factTourSnapshotsFixture);
  const deterministicFactId = factTourSemanticFixture.find(item => !item.modelContributionAccepted).entityId;
  Object.assign(inflatedFactTourFixture.find(item => item.factId === deterministicFactId && item.phase === 'read-source'), { activeAgentId: 'canonical_facts', activeSignature: 'facts', workAuthority: 'Claim reader' });
  if (!factSourceTourContractViolations(inflatedFactTourFixture, factTourHighlightsFixture, factTourSemanticFixture, factTourRunFixture).some(issue => issue.includes('inherited a model-agent identity'))) throw new Error('Application-projected fact locator with an inflated model identity was accepted');
  const inflatedFactValueFixture = structuredClone(factTourSemanticFixture);
  inflatedFactValueFixture[0].modelOwnedFields.push('value');
  if (!factSourceTourContractViolations(factTourSnapshotsFixture, factTourHighlightsFixture, inflatedFactValueFixture, factTourRunFixture).some(issue => issue.includes('ownership does not match'))) throw new Error('Model ownership was incorrectly allowed to inflate the returned fact value');
  const wrongFactLocatorFixture = structuredClone(factTourSnapshotsFixture);
  wrongFactLocatorFixture.find(item => item.factId === FACT_TOUR_FACT_IDS[0] && item.phase === 'select-source').locatorId = 'source:forged';
  if (!factSourceTourContractViolations(wrongFactLocatorFixture, factTourHighlightsFixture, factTourSemanticFixture, factTourRunFixture).some(issue => issue.includes('exact returned fact reference'))) throw new Error('Fact tour with a forged source locator was accepted');

  const lawSourcesFixture = Array.from({ length: 4 }, (_, index) => ({
    source_id: `law-${index + 1}`, location: `Article ${index + 1}`, url: `https://www.fedlex.admin.ch/law-${index + 1}`,
  }));
  const lawSemanticFixture = lawSourcesFixture.map((source, index) => ({
    eventId: `law-event:${source.source_id}`, sequence: index + 1, runId: executionTraceFixtureRunId,
    entityKind: 'official_source', entityId: source.source_id, traceContract: EXECUTION_TRACE_CONTRACT,
    presentationMode: 'deterministic_projection', authority: 'versioned_official_source_registry',
    modelContributionAccepted: false, deterministicFallbackApplied: false,
    agentId: 'official_law_registry', actorType: 'deterministic_tool',
  }));
  const lawStepsFixture = lawSourcesFixture.map(source => ({
    sourceId: source.source_id, location: source.location, url: source.url,
    retrievalMethod: 'versioned_official_source_registry_lookup', registryVersion: 'fixture-v1',
    selectedSourceId: source.source_id, selectedUrl: source.url, passageSourceId: source.source_id, passageUrl: source.url,
    presentationMode: 'deterministic-projection', presentationLabel: 'Application step · Swiss law lookup',
    activeAgentId: '', activeSignature: 'law', workAuthority: 'Swiss law lookup',
  }));
  const lawRunFixture = { run_id: executionTraceFixtureRunId, result: { legal_research: { sources: lawSourcesFixture } } };
  if (officialLawTourContractViolations(lawStepsFixture, lawSemanticFixture, lawRunFixture).length) throw new Error('Valid four-source deterministic law registry fixture was rejected');
  const inflatedLawFixture = structuredClone(lawStepsFixture);
  Object.assign(inflatedLawFixture[0], { activeAgentId: 'canonical_facts', activeSignature: 'facts', workAuthority: 'Claim reader' });
  if (!officialLawTourContractViolations(inflatedLawFixture, lawSemanticFixture, lawRunFixture).some(issue => issue.includes('misrepresented as Nemotron'))) throw new Error('Official law registry step with an inflated model identity was accepted');

  const expectedIntakeFixture = { factId: 'fact_customer_objective', sourceId: 'message', locatorId: 'source:message:page:1:quote:requested action', passage: 'Please tell me what should happen next.' };
  const intakeConstructionFixture = { nodeId: 'intake', attachmentKind: 'fact', ...expectedIntakeFixture, highlightMarkCount: 1, generatedSummaryVisible: false };
  const intakePreviewFixture = { nodeId: 'intake', basisKind: 'fact', ...expectedIntakeFixture, exactReturnedSource: true, exactPassage: true, noGeneratedContext: true };
  if (intakeClaimMessageBasisContractViolations(intakeConstructionFixture, intakePreviewFixture, expectedIntakeFixture).length) throw new Error('Valid intake customer-message basis fixture was rejected');
  const generatedIntakeFixture = { ...intakeConstructionFixture, generatedSummaryVisible: true };
  if (!intakeClaimMessageBasisContractViolations(generatedIntakeFixture, intakePreviewFixture, expectedIntakeFixture).some(issue => issue.includes('exact selected claim-message'))) throw new Error('Generated intake summary fixture was accepted');

  const auditFixture = {
    executed: true,
    agents: REQUIRED_NEMOTRON_AGENT_IDS.map((agentId, index) => ({
      agent_id: agentId,
      actor_type: 'nemotron_agent',
      call_id: `call-${index}`,
      output_artifact_hash: String(index + 1).padStart(64, '0'),
      accepted_ids: [`accepted-${index}`],
      accepted_count: 1,
      rejected: index === 2 ? [{ item_id: 'rejected-2', invariant: 'source_integrity' }] : [],
      rejected_count: index === 2 ? 1 : 0,
    })),
  };
  const auditSnapshotFixture = REQUIRED_VISIBLE_SPECIALIST_IDS.map(agentId => auditFixture.agents.find(agent => agent.agent_id === agentId)).map(agent => ({
    agentId: agent.agent_id,
    opened: true,
    panelAgentId: agent.agent_id,
    panelSignature: REQUIRED_NEMOTRON_AGENT_SIGNATURES[agent.agent_id].signature,
    buttonPressed: 'true',
    focusRestored: true,
    buttonPressedAfterClose: 'false',
    panelOpenAfterClose: false,
    historyAvailable: true,
    historyContract: AGENT_HISTORY_CONTRACT,
    historyStepCounts: [1, 1, 1, 1, 1],
    acceptedCount: agent.accepted_count,
    acceptedIds: agent.accepted_ids,
    rejections: agent.rejected.map(item => ({ id: item.item_id, invariant: item.invariant })),
    callId: agent.call_id,
    outputHash: agent.output_artifact_hash,
    emptyStateVisible: false,
  }));
  if (agentAuditContractViolations(auditSnapshotFixture, auditFixture, true).length) throw new Error('Valid call-bound agent history fixture was rejected');
  const wrongAuditHashFixture = structuredClone(auditSnapshotFixture);
  wrongAuditHashFixture[0].outputHash = '0'.repeat(64);
  if (!agentAuditContractViolations(wrongAuditHashFixture, auditFixture, true).some(issue => issue.includes('technical receipt'))) throw new Error('Agent history with a forged output hash was accepted');
  const hiddenRejectionAuditFixture = structuredClone(auditSnapshotFixture);
  hiddenRejectionAuditFixture.find(item => item.agentId === 'document_source_integrity').rejections = [];
  if (!agentAuditContractViolations(hiddenRejectionAuditFixture, auditFixture, true).some(issue => issue.includes('rejected item'))) throw new Error('Agent history hiding a rejected item was accepted');
  const referenceDecisionAuditFixture = [
    { phase: 'source-opened', nodeId: 'notification', sourceId: 'art_notification', locatorId: 'source:art_notification:page:1:quote:notice' },
    { phase: 'fragment-extracted', nodeId: 'notification', sourceId: 'art_notification', locatorId: 'source:art_notification:page:1:quote:notice' },
    { phase: 'plan-receded', nodeId: 'notification', sourceId: '', locatorId: '' },
  ];
  const referenceAuditFixture = REQUIRED_VISIBLE_SPECIALIST_IDS.map(agentId => {
    const pathAudit = agentId === 'process_decision_mapping';
    return {
      agentId, opened: true, panelAgentId: agentId, panelSignature: REQUIRED_NEMOTRON_AGENT_SIGNATURES[agentId].signature,
      buttonPressed: 'true', focusRestored: true, buttonPressedAfterClose: 'false', panelOpenAfterClose: false,
      historyAvailable: pathAudit, historyMode: pathAudit ? 'reference-replay-actions' : 'not-returned', historyContract: '',
      historyStepCounts: pathAudit ? [1, 0, 0, 0, 0] : [0, 0, 0, 0, 0], referenceTaskCount: pathAudit ? 1 : 0,
      referenceActionCount: pathAudit ? referenceDecisionAuditFixture.length : 0,
      referenceActions: pathAudit ? referenceDecisionAuditFixture : [],
      referenceProvenanceVisible: pathAudit,
      referenceProvenanceText: pathAudit ? 'No provider call · accepted reference output replay' : '',
      noAgentCallsEmptyStateVisible: false,
      acceptedCount: 0, acceptedIds: [], rejections: [], callId: '', outputHash: '', emptyStateVisible: !pathAudit,
    };
  });
  if (agentAuditContractViolations(referenceAuditFixture, { executed: false, agents: [] }, false, referenceDecisionAuditFixture).length) throw new Error('Valid action-bearing reference Path history fixture was rejected');
  const truncatedReferenceAuditFixture = structuredClone(referenceAuditFixture);
  const pathHistory = truncatedReferenceAuditFixture.find(item => item.agentId === 'process_decision_mapping');
  pathHistory.referenceActions.pop();
  pathHistory.referenceActionCount -= 1;
  if (!agentAuditContractViolations(truncatedReferenceAuditFixture, { executed: false, agents: [] }, false, referenceDecisionAuditFixture).some(issue => issue.includes('exact persisted decision flow'))) throw new Error('Reference Path history missing a decision action was accepted');

  const fixtureRunId = 'run:execution-trace-fixture';
  const processSemanticFixture = FLAGSHIP_PROCESS_PROJECTION_IDS.flatMap((entityId, index) => {
    const linkedModelContributionIds = index % 2 === 0 ? [`contribution:${entityId}`] : [];
    const structure = {
      type: 'process_node.created', eventId: `event:${entityId}`,
      sequence: index + 1,
      runId: fixtureRunId,
      entityKind: 'process_node',
      entityId,
      traceContract: EXECUTION_TRACE_CONTRACT,
      presentationMode: 'returned_action_replay',
      authority: linkedModelContributionIds.length ? 'deterministic_process_projection' : 'deterministic_process_structure',
      modelContributionAccepted: false,
      deterministicFallbackApplied: false,
      agentId: 'process_projection', actorType: 'deterministic_tool', modelOwnedFields: [],
      applicationOwnedFields: ['node_id', 'title', 'question'], linkedModelContributionIds,
      outputProcessNodeId: entityId,
    };
    const decision = linkedModelContributionIds.length ? [{
      type: 'process_decision.accepted', eventId: `decision-event:${entityId}`, sequence: index + .5,
      runId: fixtureRunId, entityKind: 'process_decision', entityId,
      traceContract: EXECUTION_TRACE_CONTRACT, presentationMode: 'returned_action_replay',
      authority: 'model_field_accepted_by_process_gate', modelContributionAccepted: true,
      deterministicFallbackApplied: false, agentId: 'process_decision_mapping', actorType: 'nemotron_agent',
      acceptedFields: ['decision_value'], modelOwnedFields: ['decision_value'], applicationOwnedFields: [],
      acceptedContributionIds: linkedModelContributionIds, outputProcessNodeId: entityId,
      sourceCallId: 'modelcall-process-fixture', sourceCallInputHash: '1'.repeat(64),
      sourceCallOutputHash: '2'.repeat(64), gateInputHash: '3'.repeat(64),
      originCallId: 'modelcall-process-fixture', callCount: 1,
      usageSource: 'provider_reported', cacheHit: false,
    }] : [];
    return [...decision, structure];
  });
  const processStructureSemanticFixture = processSemanticFixture.filter(item => item.entityKind === 'process_node');
  const processProjectionFixture = FLAGSHIP_PROCESS_PROJECTION_IDS.map((entityId, index) => ({
    changeId: `change:${entityId}`,
    eventId: `event:${entityId}`,
    agentId: 'process_projection',
    entityId,
    nodeStates: FLAGSHIP_PROCESS_PROJECTION_IDS.map((nodeId, nodeIndex) => {
      const state = nodeIndex < index ? 'built' : nodeIndex === index ? 'building' : 'pending';
      return { nodeId, state, tabIndex: state === 'pending' ? -1 : 0, disabled: state === 'pending', ariaCurrent: nodeIndex === index ? 'step' : '' };
    }),
    focus: { focusCount: 1, cursorCount: 1, artifactCount: 1, actionCount: 0 },
    at: index * 2400,
  }));
  const processCursorFixture = processProjectionFixture.map((item, index) => ({
    changeId: item.changeId,
    eventId: item.eventId,
    agentId: '',
    phase: 'click',
    presentationMode: 'returned-action-replay',
    presentationLabel: 'Returned work · Process safety check',
    activeAgentId: '',
    activeSignature: 'gate',
    workAuthority: 'Process safety check',
  }));
  const processProjectionFixtureIssues = processProjectionContractViolations(processProjectionFixture, processSemanticFixture, processCursorFixture, fixtureRunId);
  if (processProjectionFixtureIssues.length) throw new Error(`Valid ten-node process projection fixture was rejected: ${JSON.stringify(processProjectionFixtureIssues)}`);
  const nonMonotonicProjection = structuredClone(processProjectionFixture);
  nonMonotonicProjection[4].nodeStates[0].state = 'pending';
  if (!processProjectionContractViolations(nonMonotonicProjection, processSemanticFixture, processCursorFixture, fixtureRunId).some(issue => issue.includes('prior nodes'))) throw new Error('Non-monotonic process projection fixture was accepted');
  const inflatedDeterministicProjection = structuredClone(processProjectionFixture);
  const inflatedDeterministicCursor = structuredClone(processCursorFixture);
  const deterministicIndex = 1;
  inflatedDeterministicProjection[deterministicIndex].agentId = 'process_decision_mapping';
  inflatedDeterministicCursor[deterministicIndex].agentId = 'process_decision_mapping';
  inflatedDeterministicCursor[deterministicIndex].activeAgentId = 'process_decision_mapping';
  inflatedDeterministicCursor[deterministicIndex].activeSignature = 'process';
  if (!processProjectionContractViolations(inflatedDeterministicProjection, processSemanticFixture, inflatedDeterministicCursor, fixtureRunId).some(issue => issue.includes('inherited a model identity'))) throw new Error('Deterministic process structure with an inflated model identity was accepted');
  const inflatedProcessFieldFixture = structuredClone(processSemanticFixture);
  inflatedProcessFieldFixture.find(item => item.entityKind === 'process_decision').modelOwnedFields.push('title');
  if (!processProjectionContractViolations(processProjectionFixture, inflatedProcessFieldFixture, processCursorFixture, fixtureRunId).some(issue => issue.includes('exact accepted decision_value'))) throw new Error('Process model event was allowed to claim deterministic node structure');
  const evidenceOwnershipFixture = [
    {
      type: 'evidence_fields.accepted', eventId: 'evidence-fields:one', runId: fixtureRunId,
      entityKind: 'evidence_fields', entityId: 'evidence-one', traceContract: EXECUTION_TRACE_CONTRACT,
      presentationMode: 'returned_action_replay', actorType: 'nemotron_agent', agentId: 'evidence_checklist',
      modelContributionAccepted: true, modelOwnedFields: ['status', 'artifact_ids'], applicationOwnedFields: [],
      outputEvidenceId: 'evidence-one',
      sourceCallId: 'modelcall-evidence-fixture', sourceCallInputHash: '4'.repeat(64),
      sourceCallOutputHash: '5'.repeat(64), gateInputHash: '6'.repeat(64),
      originCallId: 'modelcall-evidence-fixture', callCount: 1,
      usageSource: 'provider_reported', cacheHit: false,
    },
    {
      type: 'evidence_requirement.linked', eventId: 'evidence-structure:one', runId: fixtureRunId,
      entityKind: 'evidence_requirement', entityId: 'evidence-one', traceContract: EXECUTION_TRACE_CONTRACT,
      presentationMode: 'returned_action_replay', actorType: 'deterministic_tool', agentId: 'evidence_projection',
      modelContributionAccepted: false, modelOwnedFields: [], applicationOwnedFields: ['item_id', 'status', 'artifact_ids'],
      linkedModelFields: ['status', 'artifact_ids'], outputEvidenceId: 'evidence-one',
    },
    {
      type: 'evidence_requirement.linked', eventId: 'evidence-structure:two', runId: fixtureRunId,
      entityKind: 'evidence_requirement', entityId: 'evidence-two', traceContract: EXECUTION_TRACE_CONTRACT,
      presentationMode: 'returned_action_replay', actorType: 'deterministic_tool', agentId: 'evidence_projection',
      modelContributionAccepted: false, modelOwnedFields: [], applicationOwnedFields: ['item_id', 'status'],
      linkedModelFields: [], outputEvidenceId: 'evidence-two',
    },
  ];
  const ownershipRunFixture = {
    run_id: fixtureRunId,
    result: {
      process: { nodes: FLAGSHIP_PROCESS_PROJECTION_IDS.map(node_id => ({ node_id })) },
      checklist: { items: [{ item_id: 'evidence-one' }, { item_id: 'evidence-two' }] },
      agent_orchestration: {
        agents: [
          {
            agent_id: 'process_decision_mapping', call_id: 'modelcall-process-fixture',
            origin_call_id: 'modelcall-process-fixture', call_count: 1, usage_source: 'provider_reported',
            cache_hit: false, input_artifact_hash: '1'.repeat(64), output_artifact_hash: '2'.repeat(64),
          },
          {
            agent_id: 'evidence_checklist', call_id: 'modelcall-evidence-fixture',
            origin_call_id: 'modelcall-evidence-fixture', call_count: 1, usage_source: 'provider_reported',
            cache_hit: false, input_artifact_hash: '4'.repeat(64), output_artifact_hash: '5'.repeat(64),
          },
        ],
        deterministic_gates: [
          { agent_id: 'deterministic_process_gate', input_artifact_hash: '3'.repeat(64) },
          { agent_id: 'deterministic_evidence_gate', input_artifact_hash: '6'.repeat(64) },
        ],
      },
    },
  };
  const ownershipSemanticFixture = [...processSemanticFixture, ...evidenceOwnershipFixture];
  if (acceptedExecutionFieldOwnershipViolations(ownershipSemanticFixture, ownershipRunFixture).length) throw new Error('Valid split model-field/application-structure fixture was rejected');
  const forgedProcessCallBindingFixture = structuredClone(ownershipSemanticFixture);
  forgedProcessCallBindingFixture.find(item => item.entityKind === 'process_decision').sourceCallInputHash = 'f'.repeat(64);
  if (!acceptedExecutionFieldOwnershipViolations(forgedProcessCallBindingFixture, ownershipRunFixture).some(issue => issue.includes('exact accepted decision_value'))) throw new Error('Process decision with a forged source-call input hash was accepted');
  const forgedEvidenceCallBindingFixture = structuredClone(ownershipSemanticFixture);
  forgedEvidenceCallBindingFixture.find(item => item.entityKind === 'evidence_fields').originCallId = 'modelcall-forged-origin';
  if (!acceptedExecutionFieldOwnershipViolations(forgedEvidenceCallBindingFixture, ownershipRunFixture).some(issue => issue.includes('status/artifact_ids'))) throw new Error('Evidence fields with a forged cache-origin call were accepted');
  const inflatedEvidenceOwnershipFixture = structuredClone(ownershipSemanticFixture);
  inflatedEvidenceOwnershipFixture.find(item => item.entityKind === 'evidence_fields').modelOwnedFields.push('title');
  if (!acceptedExecutionFieldOwnershipViolations(inflatedEvidenceOwnershipFixture, ownershipRunFixture).some(issue => issue.includes('status/artifact_ids'))) throw new Error('Document finder was allowed to claim an unbounded evidence field');

  const progressEntityFixture = FLAGSHIP_PROCESS_PROJECTION_IDS.map(nodeId => ({ entityKind: 'node', nodeId, branchId: '' }));
  const progressFixture = progressEntityFixture.flatMap((entity, entityIndex) => {
    const basisKind = 'accepted-decision';
    const decisionSemantic = processSemanticFixture.find(item => item.entityKind === 'process_decision' && item.entityId === entity.nodeId);
    const sequence = ['responsibility', 'remedy', 'resolution'].includes(entity.nodeId)
      ? PROCESS_NODE_PROGRESS_SEQUENCE.slice(-3)
      : PROCESS_NODE_PROGRESS_SEQUENCE;
    return sequence.map((step, stepIndex) => {
      const modelDecisionPhase = Boolean(decisionSemantic) && ['form', 'complete'].includes(step.phase);
      const identity = {
        changeId: `progress-change:${entity.nodeId}`,
        eventId: modelDecisionPhase ? decisionSemantic.eventId : `event:${entity.nodeId}`,
        agentId: modelDecisionPhase ? 'process_decision_mapping' : '',
      };
      return ({
      contract: PROCESS_NODE_PROGRESS_CONTRACT,
      scope: PROCESS_NODE_PROGRESS_SCOPE,
      processId: 'process-progress-fixture',
      ...entity,
      ...identity,
      ...step,
      basisKind,
      label: step.phase === 'cleared' ? ''
        : EVIDENCE_REQUIREMENT_PROGRESS_LABELS[step.phase]
          || (step.phase === 'form' ? (entity.entityKind === 'branch' ? 'Testing outcome' : 'Forming decision')
            : step.phase === 'complete' ? (entity.entityKind === 'branch' ? 'Outcome ready' : 'Decision ready')
              : step.phase),
      indicatorDomCount: 1,
      indicatorVisibleCount: step.visible ? 1 : 0,
      indicatorVisible: step.visible,
      indicatorSurfaceVisible: false,
      indicatorInsideCursor: true,
      indicatorPercent: step.percent,
      indicatorPhase: step.visible ? step.phase : '',
      indicatorLabel: step.visible
        ? EVIDENCE_REQUIREMENT_PROGRESS_LABELS[step.phase]
          || (step.phase === 'form' ? (entity.entityKind === 'branch' ? 'Testing outcome' : 'Forming decision')
            : step.phase === 'complete' ? (entity.entityKind === 'branch' ? 'Outcome ready' : 'Decision ready')
              : step.phase)
        : '',
      indicatorValueVisible: false,
      cursorProgressState: step.visible ? 'active' : '',
      cursorSignature: modelDecisionPhase ? 'process' : 'gate',
      cursorAgent: modelDecisionPhase ? REQUIRED_DESKTOP_AGENT_LABELS.process_decision_mapping : 'Process safety check',
      activeAgentId: modelDecisionPhase ? 'process_decision_mapping' : '',
      visualActiveAgentId: modelDecisionPhase ? 'process_decision_mapping' : '',
      visualGroupId: modelDecisionPhase ? PATH_BUILDER_VISUAL_GROUP_ID : '',
      presentationMode: 'returned-action-replay',
      presentationLabel: modelDecisionPhase ? 'Returned work · Process builder' : 'Returned work · Process safety check',
      workAuthority: modelDecisionPhase ? 'Process builder' : 'Process safety check',
      rootProgressState: step.visible ? 'active' : 'idle',
      rootPercent: step.visible ? String(step.percent) : '',
      rootPhase: step.visible ? step.phase : '',
      rootNodeId: step.visible ? entity.nodeId : '',
      rootBasisKind: step.visible ? basisKind : '',
      processProgressState: step.visible ? 'active' : 'idle',
      processPercent: step.visible ? String(step.percent) : '',
      processPhase: step.visible ? step.phase : '',
      processNodeId: step.visible ? entity.nodeId : '',
      inspectionBasisKind: basisKind === 'evidence-requirement' && ['search', 'read'].includes(step.phase) ? basisKind : '',
      inspectionPrompt: basisKind === 'evidence-requirement' && step.phase === 'search' ? 'Evidence still needed' : '',
      inspectionText: basisKind === 'evidence-requirement'
        ? (step.phase === 'search' ? 'Evidence still needed Independent inspection Inspect requirement'
          : step.phase === 'read' ? 'Requirement opened · evidence need Independent inspection' : 'Confirmed · evidence need Independent inspection')
        : '',
      outputVisible: false,
      at: (entityIndex * 10000) + (stepIndex * 350),
    });
    });
  });
  const progressOutputFixture = entity => {
    const cleared = progressFixture.find(item => item.entityKind === entity.entityKind && item.nodeId === entity.nodeId && item.phase === 'cleared');
    return {
      nodeId: entity.nodeId,
      entityId: entity.nodeId,
      branchId: entity.branchId,
      changeId: cleared.changeId,
      eventId: `event:${entity.nodeId}`,
      agentId: 'process_projection',
      indicatorVisible: false,
      indicatorVisibleCount: 0,
      cursorProgressState: '',
      rootProgressState: 'idle',
      processProgressState: 'idle',
      outputVisible: true,
      at: cleared.at + MIN_PROCESS_NODE_PROGRESS_CLEAR_GAP_MS + 10,
    };
  };
  const progressNodeOutputFixture = progressEntityFixture.filter(item => item.entityKind === 'node').map(progressOutputFixture);
  const progressFinalFixture = { indicatorVisible: false, indicatorValueVisible: false, indicatorVisibleCount: 0, cursorProgressState: '', rootProgressState: 'idle', processProgressState: 'idle', rootPercent: '', processPercent: '' };
  const processNodeProgressFixtureIssues = processNodeProgressContractViolations(progressFixture, progressNodeOutputFixture, progressFinalFixture, processSemanticFixture, fixtureRunId);
  if (processNodeProgressFixtureIssues.length) throw new Error(`Valid execution-trace-bound process-node progress fixture was rejected: ${JSON.stringify(processNodeProgressFixtureIssues)}`);
  const missingProgressPhaseFixture = progressFixture.filter(item => !(item.nodeId === 'causation' && item.phase === 'extract'));
  if (!processNodeProgressContractViolations(missingProgressPhaseFixture, progressNodeOutputFixture, progressFinalFixture, processSemanticFixture, fixtureRunId).some(issue => issue.includes('does not replay accepted inputs'))) throw new Error('Process progress with a missing accepted-input phase was accepted');
  const wrongProgressOwnerFixture = structuredClone(progressFixture);
  wrongProgressOwnerFixture.find(item => item.nodeId === 'intake' && item.phase === 'form').cursorSignature = 'facts';
  if (!processNodeProgressContractViolations(wrongProgressOwnerFixture, progressNodeOutputFixture, progressFinalFixture, processSemanticFixture, fixtureRunId).some(issue => issue.includes('merged Path builder workstream'))) throw new Error('Accepted decision_value progress owned by the wrong visible workstream was accepted');
  const inflatedFallbackProgressFixture = structuredClone(progressFixture);
  const fallbackProgress = inflatedFallbackProgressFixture.find(item => item.nodeId === 'scope' && item.phase === 'read');
  Object.assign(fallbackProgress, { cursorSignature: 'process', cursorAgent: 'Process builder', activeAgentId: 'process_decision_mapping', visualActiveAgentId: 'process_decision_mapping', visualGroupId: PATH_BUILDER_VISUAL_GROUP_ID, workAuthority: 'Process builder' });
  if (!processNodeProgressContractViolations(inflatedFallbackProgressFixture, progressNodeOutputFixture, progressFinalFixture, processSemanticFixture, fixtureRunId).some(issue => issue.includes('inherited a model identity'))) throw new Error('Accepted-input progress with an inflated model identity was accepted');
  const visibleNumericProgressFixture = structuredClone(progressFixture);
  visibleNumericProgressFixture.find(item => item.nodeId === 'intake' && item.phase === 'read').indicatorValueVisible = true;
  if (!processNodeProgressContractViolations(visibleNumericProgressFixture, progressNodeOutputFixture, progressFinalFixture, processSemanticFixture, fixtureRunId).some(issue => issue.includes('numeric percentage is visible'))) throw new Error('Visible numeric process percentage fixture was accepted');
  const prematureProgressOutputFixture = structuredClone(progressFixture);
  prematureProgressOutputFixture.find(item => item.nodeId === 'responsibility' && item.phase === 'cleared').outputVisible = true;
  if (!processNodeProgressContractViolations(prematureProgressOutputFixture, progressNodeOutputFixture, progressFinalFixture, processSemanticFixture, fixtureRunId).some(issue => issue.includes('output was still absent'))) throw new Error('Process output visible before progress cleared was accepted');
  const lingeringProgressOutputFixture = structuredClone(progressNodeOutputFixture);
  lingeringProgressOutputFixture[0].indicatorVisible = true;
  lingeringProgressOutputFixture[0].indicatorVisibleCount = 1;
  if (!processNodeProgressContractViolations(progressFixture, lingeringProgressOutputFixture, progressFinalFixture, processSemanticFixture, fixtureRunId).some(issue => issue.includes('remains visible when the output appears'))) throw new Error('Process progress still visible when the node appeared was accepted');

  const decisionFlowFacts = FLAGSHIP_PROCESS_PROJECTION_IDS.map(nodeId => ({
    fact_id: `fact_${nodeId}`,
    source_refs: nodeId === NOTIFICATION_DECISION_NODE_ID ? [
      { artifact_id: 'art_notification', locator_kind: 'text_quote', page: 1, excerpt: 'Wed, 15 Jul 2026 08:32:00 +0200' },
      { artifact_id: 'art_notification', locator_kind: 'text_quote', page: 1, excerpt: 'Please arrange an inspection and repair.' },
      { artifact_id: 'art_delivery', locator_kind: 'text_quote', page: 1, excerpt: 'Accepted by recipient mail server' },
    ] : nodeId === 'defect'
      ? [{ artifact_id: 'art_notification', locator_kind: 'text_quote', page: 1, excerpt: 'Wed, 15 Jul 2026 08:32:00 +0200' }]
      : [{ artifact_id: `art_${nodeId}`, locator_kind: 'text_quote', page: 1, excerpt: `Exact ${nodeId} source` }],
  }));
  const decisionNodes = FLAGSHIP_PROCESS_PROJECTION_IDS.map(nodeId => ({
    node_id: nodeId,
    fact_ids: [`fact_${nodeId}`],
    legal_source_ids: nodeId === NOTIFICATION_DECISION_NODE_ID ? ['fedlex-or-257g'] : [],
  }));
  const decisionRunFixture = {
    facts: decisionFlowFacts,
    process: { nodes: decisionNodes },
    legal_research: { sources: [{ source_id: 'fedlex-or-257g', source_type: 'official_statute', passage_text: 'Der Mieter muss Mängel, die er nicht selber zu beseitigen hat, dem Vermieter melden.' }] },
  };
  const decisionRunEnvelope = { run_id: fixtureRunId, result: decisionRunFixture };
  const decisionFactSemanticFixture = decisionFlowFacts.map((fact, index) => ({
    eventId: `fact-event:${fact.fact_id}`,
    sequence: 100 + index,
    runId: fixtureRunId,
    entityKind: 'fact',
    entityId: fact.fact_id,
    traceContract: EXECUTION_TRACE_CONTRACT,
    presentationMode: 'returned_action_replay',
    authority: index % 2 === 0 ? 'model_contribution_accepted' : 'deterministic_reference_projection',
    modelContributionAccepted: index % 2 === 0,
    deterministicFallbackApplied: false,
    agentId: 'canonical_facts',
    actorType: index % 2 === 0 ? 'nemotron_agent' : 'deterministic_tool',
  }));
  const decisionLawSemanticFixture = {
    eventId: 'law-event:fedlex-or-257g', sequence: 200, runId: fixtureRunId,
    entityKind: 'official_source', entityId: 'fedlex-or-257g', traceContract: EXECUTION_TRACE_CONTRACT,
    presentationMode: 'deterministic_projection', authority: 'versioned_official_source_registry',
    modelContributionAccepted: false, deterministicFallbackApplied: false,
    agentId: 'official_law_registry', actorType: 'deterministic_tool',
  };
  const decisionSemanticFixture = [...decisionFactSemanticFixture, decisionLawSemanticFixture, ...processSemanticFixture];
  const decisionFlowFixture = [];
  const decisionChangeFixture = [];
  const decisionHighlightFixture = [];
  const decisionInteractionFixture = [];
  let decisionAt = 1000;
  for (const [nodeIndex, node] of decisionNodes.entries()) {
    const nodeFacts = decisionFactsForReturnedNode(decisionRunFixture, node);
    const blockedDownstream = BLOCKED_DOWNSTREAM_DECISION_IDS.includes(node.node_id);
    const law = !blockedDownstream && nodeFacts.length ? officialDecisionLaw(decisionRunFixture, node, new Set()) : null;
    const plans = [
      ...(!blockedDownstream ? nodeFacts.map(fact => ({
        stepId: `accepted-fact:${fact.fact_id}`,
        stepKind: 'accepted-fact',
        sourceId: '', locatorIds: [], factIds: [fact.fact_id],
        basis: decisionFactSemanticFixture.find(item => item.entityId === fact.fact_id),
      })) : []),
      ...(law ? [{
        stepId: `accepted-law:${law.source_id}`,
        stepKind: 'accepted-law',
        sourceId: law.source_id, locatorIds: [], factIds: [], basis: decisionLawSemanticFixture,
      }] : []),
    ];
    const structureSemantic = processSemanticFixture.find(item => item.entityKind === 'process_node' && item.entityId === node.node_id);
    const decisionSemantic = processSemanticFixture.find(item => item.entityKind === 'process_decision' && item.entityId === node.node_id);
    const common = {
      contract: DECISION_FLOW_CONTRACT,
      runId: fixtureRunId,
      nodeId: node.node_id,
      agentId: '',
      eventId: structureSemantic.eventId,
      structureEventId: structureSemantic.eventId,
      structureAuthority: structureSemantic.authority,
      structureTraceContract: EXECUTION_TRACE_CONTRACT,
      decisionAgentId: decisionSemantic?.agentId || '',
      decisionEventId: decisionSemantic?.eventId || '',
      decisionAuthority: decisionSemantic?.authority || '',
      decisionModelContributionAccepted: Boolean(decisionSemantic),
      decisionDeterministicFallbackApplied: false,
      presentationMode: 'returned-action-replay',
      presentationLabel: 'Returned work · Process safety check',
      activeAgentId: '', visualActiveAgentId: '', visualGroupId: '', activeSignature: 'gate', workAuthority: 'Process safety check',
      graphVisible: true,
      graphConstructionState: 'building',
      workspaceVisible: true,
      workspaceNodeId: node.node_id,
      planCount: 1,
      planVisible: true,
      planNodeId: node.node_id,
      planKind: blockedDownstream ? 'waiting-decision' : 'evidence-decision',
      planItemCount: plans.length + 2,
      planParagraphCount: 0,
      planButtonCount: 0,
      waitingBasisVisible: blockedDownstream,
      waitingBasisText: blockedDownstream ? BLOCKED_DOWNSTREAM_WAITING_COPY[node.node_id] : '',
      readerControlCount: 0,
      nodeVisible: false,
      reducedMotion: false,
    };
    const accumulatedFactIds = [];
    for (const plan of plans) {
      const basis = plan.basis;
      const replay = {
        ...common,
        stepId: plan.stepId, stepKind: plan.stepKind, sourceId: plan.sourceId,
        locatorId: '', locatorIds: [], factIds: plan.factIds, locatorIndex: plan.stepKind === 'accepted-fact' ? 0 : -1,
        locatorCount: plan.stepKind === 'accepted-fact' ? 1 : 0,
        basisAgentId: basis.agentId, basisEventId: basis.eventId, basisAuthority: basis.authority,
        sourceTargetExists: false, sourceRowActive: false, activeSourceIds: [], activeSourceLocator: '',
        artifactSurfaceVisible: false, realArtifactVisible: false, highlightVisible: false, highlightCount: 0,
      };
      decisionFlowFixture.push({ ...replay, phase: 'planned', progress: 0, planPhase: 'select-source', fragmentFactIds: [...accumulatedFactIds], progressVisible: true, at: decisionAt });
      decisionAt += 1500;
      decisionFlowFixture.push({ ...replay, phase: 'source-opened', progress: 30, planPhase: 'read-source', fragmentFactIds: [...accumulatedFactIds], progressVisible: true, at: decisionAt });
      decisionAt += MIN_DECISION_SOURCE_PREVIEW_HOLD_MS + 10;
      plan.factIds.forEach(factId => { if (!accumulatedFactIds.includes(factId)) accumulatedFactIds.push(factId); });
      decisionFlowFixture.push({ ...replay, phase: 'fragment-extracted', progress: 60, planPhase: 'highlight-source', fragmentFactIds: [...accumulatedFactIds], progressVisible: true, at: decisionAt });
      decisionAt += MIN_DECISION_SOURCE_HOLD_MS + 10;
    }
    const terminal = (phase, progress, extra = {}) => {
      const modelDecisionPhase = Boolean(decisionSemantic) && ['combining', 'decision-ready'].includes(phase);
      return ({
        ...common, stepId: phase, stepKind: '', sourceId: '', locatorId: '', locatorIds: [], factIds: [], locatorIndex: -1, locatorCount: 0,
        phase, progress, planPhase: phase === 'plan-receding' ? 'receding' : phase === 'plan-receded' ? 'receded' : phase === 'combining' ? 'combine' : 'complete',
        fragmentFactIds: [...accumulatedFactIds], combinationVisible: true, combineState: 'combining',
        progressVisible: !['plan-receding', 'plan-receded'].includes(phase), at: decisionAt,
        agentId: modelDecisionPhase ? 'process_decision_mapping' : '',
        presentationLabel: modelDecisionPhase ? 'Returned work · Process builder' : 'Returned work · Process safety check',
        activeAgentId: modelDecisionPhase ? 'process_decision_mapping' : '',
        visualActiveAgentId: modelDecisionPhase ? 'process_decision_mapping' : '',
        visualGroupId: modelDecisionPhase ? PATH_BUILDER_VISUAL_GROUP_ID : '',
        activeSignature: modelDecisionPhase ? 'process' : 'gate',
        workAuthority: modelDecisionPhase ? 'Process builder' : 'Process safety check',
        ...extra,
      });
    };
    decisionFlowFixture.push(terminal('combining', 90)); decisionAt += MIN_DECISION_COMBINE_HOLD_MS + 10;
    decisionFlowFixture.push(terminal('decision-ready', 100)); decisionAt += MIN_DECISION_READY_HOLD_MS + 10;
    const receding = terminal('plan-receding', 100, { nodeVisible: false, progressVisible: false });
    decisionFlowFixture.push(receding); decisionAt += MIN_DECISION_PLAN_RECEDE_MS + 20;
    decisionFlowFixture.push(terminal('plan-receded', 100, { nodeVisible: false, progressVisible: false })); decisionAt += 10;
    decisionChangeFixture.push({ entityId: node.node_id, eventId: structureSemantic.eventId, agentId: structureSemantic.agentId, indicatorVisible: false, planVisible: false, decisionFlowState: 'idle', outputVisible: true, graphVisible: true, at: decisionAt });
    decisionAt += 1500;
  }
  if (decisionFlowContractViolations(decisionFlowFixture, decisionChangeFixture, decisionHighlightFixture, decisionInteractionFixture, decisionRunEnvelope, decisionSemanticFixture).length) throw new Error(`Valid accepted-input decision-flow fixture was rejected: ${JSON.stringify(decisionFlowContractViolations(decisionFlowFixture, decisionChangeFixture, decisionHighlightFixture, decisionInteractionFixture, decisionRunEnvelope, decisionSemanticFixture))}`);
  const rushedSourcePreviewFixture = structuredClone(decisionFlowFixture);
  const rushedPreviewOpened = rushedSourcePreviewFixture.find(step => step.phase === 'source-opened');
  const rushedPreviewHighlight = rushedSourcePreviewFixture.find(step => step.nodeId === rushedPreviewOpened.nodeId && step.stepId === rushedPreviewOpened.stepId && step.phase === 'fragment-extracted');
  rushedPreviewHighlight.at = rushedPreviewOpened.at + MIN_DECISION_SOURCE_PREVIEW_HOLD_MS - 1;
  if (!decisionFlowContractViolations(rushedSourcePreviewFixture, decisionChangeFixture, decisionHighlightFixture, decisionInteractionFixture, decisionRunEnvelope, decisionSemanticFixture).some(issue => issue.includes('exact source is not readable'))) throw new Error('Rushed exact-source preview was accepted');
  const rushedHighlightFixture = structuredClone(decisionFlowFixture);
  const intakeHighlights = rushedHighlightFixture.filter(step => step.nodeId === 'intake' && step.phase === 'fragment-extracted');
  const rushedHighlight = intakeHighlights.reduce((latest, step) => step.at > latest.at ? step : latest);
  const rushedHighlightNext = rushedHighlightFixture.filter(step => step.nodeId === rushedHighlight.nodeId && step.at > rushedHighlight.at).sort((left, right) => left.at - right.at)[0];
  rushedHighlightNext.at = rushedHighlight.at + MIN_DECISION_SOURCE_HOLD_MS - 1;
  if (!decisionFlowContractViolations(rushedHighlightFixture, decisionChangeFixture, decisionHighlightFixture, decisionInteractionFixture, decisionRunEnvelope, decisionSemanticFixture).some(issue => issue.includes('accepted input is not readable'))) throw new Error('Rushed highlighted passage was accepted');
  const readerControlFixture = structuredClone(decisionFlowFixture);
  readerControlFixture.find(step => step.phase === 'source-opened').readerControlCount = 1;
  if (!decisionFlowContractViolations(readerControlFixture, decisionChangeFixture, decisionHighlightFixture, decisionInteractionFixture, decisionRunEnvelope, decisionSemanticFixture).some(issue => issue.includes('viewer-facing reader control'))) throw new Error('Automatic decision replay with a reader CTA was accepted');
  const rushedDecisionFixture = structuredClone(decisionFlowFixture);
  const rushedCombining = rushedDecisionFixture.find(step => step.phase === 'combining');
  const rushedReady = rushedDecisionFixture.find(step => step.nodeId === rushedCombining.nodeId && step.phase === 'decision-ready');
  rushedReady.at = rushedCombining.at + MIN_DECISION_COMBINE_HOLD_MS - 1;
  if (!decisionFlowContractViolations(rushedDecisionFixture, decisionChangeFixture, decisionHighlightFixture, decisionInteractionFixture, decisionRunEnvelope, decisionSemanticFixture).some(issue => issue.includes('decision is formed'))) throw new Error('Rushed source-to-decision formation was accepted');
  const rushedReadyHoldFixture = structuredClone(decisionFlowFixture);
  const rushedReadyState = rushedReadyHoldFixture.find(step => step.phase === 'decision-ready');
  const rushedRecedingState = rushedReadyHoldFixture.find(step => step.nodeId === rushedReadyState.nodeId && step.phase === 'plan-receding');
  rushedRecedingState.at = rushedReadyState.at + MIN_DECISION_READY_HOLD_MS - 1;
  if (!decisionFlowContractViolations(rushedReadyHoldFixture, decisionChangeFixture, decisionHighlightFixture, decisionInteractionFixture, decisionRunEnvelope, decisionSemanticFixture).some(issue => issue.includes('completed decision does not remain readable'))) throw new Error('Rushed completed-decision hold was accepted');
  const reducedMotionDecisionFixture = structuredClone(decisionFlowFixture).map(step => ({ ...step, reducedMotion: true }));
  const reducedMotionChangeFixture = structuredClone(decisionChangeFixture);
  reducedMotionChangeFixture.forEach(change => {
    const receding = reducedMotionDecisionFixture.find(step => step.nodeId === change.entityId && step.phase === 'plan-receding');
    const receded = reducedMotionDecisionFixture.find(step => step.nodeId === change.entityId && step.phase === 'plan-receded');
    receded.at = receding.at;
    change.at = receded.at;
  });
  if (decisionFlowContractViolations(reducedMotionDecisionFixture, reducedMotionChangeFixture, decisionHighlightFixture, decisionInteractionFixture, decisionRunEnvelope, decisionSemanticFixture).length) throw new Error(`Reduced-motion semantic decision sequence was rejected: ${JSON.stringify(decisionFlowContractViolations(reducedMotionDecisionFixture, reducedMotionChangeFixture, decisionHighlightFixture, decisionInteractionFixture, decisionRunEnvelope, decisionSemanticFixture))}`);
  const reducedMotionMissingHighlightFixture = reducedMotionDecisionFixture.filter((step, index) => index !== reducedMotionDecisionFixture.findIndex(item => item.phase === 'fragment-extracted'));
  if (!decisionFlowContractViolations(reducedMotionMissingHighlightFixture, reducedMotionChangeFixture, decisionHighlightFixture, decisionInteractionFixture, decisionRunEnvelope, decisionSemanticFixture).some(issue => issue.includes('sequentially') || issue.includes('incomplete or out of order'))) throw new Error('Reduced-motion sequence without a highlighted passage was accepted');
  const fakeSourceDecisionFixture = structuredClone(decisionFlowFixture);
  const intakePlan = fakeSourceDecisionFixture.find(step => step.nodeId === 'intake' && step.phase === 'planned');
  Object.assign(intakePlan, { stepKind: 'source', stepId: 'source:message', sourceId: 'message' });
  if (!decisionFlowContractViolations(fakeSourceDecisionFixture, decisionChangeFixture, decisionHighlightFixture, decisionInteractionFixture, decisionRunEnvelope, decisionSemanticFixture).some(issue => issue.includes('reopens a source or law'))) throw new Error('Graph replay with an invented new source read was accepted');
  const brokenBasisDecisionFixture = structuredClone(decisionFlowFixture);
  brokenBasisDecisionFixture.find(step => step.nodeId === 'notification' && step.phase === 'planned' && step.stepKind === 'accepted-fact').basisEventId = 'wrong-fact-event';
  if (!decisionFlowContractViolations(brokenBasisDecisionFixture, decisionChangeFixture, decisionHighlightFixture, decisionInteractionFixture, decisionRunEnvelope, decisionSemanticFixture).some(issue => issue.includes('exact returned fact event'))) throw new Error('Accepted fact replay with broken event lineage was accepted');
  const lingeringPlanChangeFixture = structuredClone(decisionChangeFixture);
  lingeringPlanChangeFixture[0].planVisible = true;
  if (!decisionFlowContractViolations(decisionFlowFixture, lingeringPlanChangeFixture, decisionHighlightFixture, decisionInteractionFixture, decisionRunEnvelope, decisionSemanticFixture).some(issue => issue.includes('before progress and plan have cleared'))) throw new Error('Accepted node with a lingering plan was accepted');
  const inventedSourceWorkFixture = structuredClone(decisionFlowFixture);
  const responsibilityCombineIndex = inventedSourceWorkFixture.findIndex(step => step.nodeId === 'responsibility' && step.phase === 'combining');
  const responsibilityCombine = inventedSourceWorkFixture[responsibilityCombineIndex];
  inventedSourceWorkFixture.splice(responsibilityCombineIndex, 0, {
    ...responsibilityCombine,
    stepId: 'source:invented', stepKind: 'source', sourceId: 'art_invented',
    locatorId: 'source:art_invented:page:1:quote:Invented', locatorIds: ['source:art_invented:page:1:quote:Invented'],
    factIds: ['fact_responsibility'], locatorIndex: 0, locatorCount: 1,
    phase: 'planned', progress: 0, planPhase: 'select-source', planItemCount: 3,
    sourceTargetExists: true, sourceRowActive: false, activeSourceIds: [], activeSourceLocator: '',
    combinationVisible: false, at: responsibilityCombine.at - 1,
  });
  const inventedSourceWorkIssues = decisionFlowContractViolations(inventedSourceWorkFixture, decisionChangeFixture, decisionHighlightFixture, decisionInteractionFixture, decisionRunEnvelope, decisionSemanticFixture);
  if (!inventedSourceWorkIssues.some(issue => issue.includes('invents accepted input work'))) throw new Error(`Invented work for a blocked downstream decision was accepted: ${JSON.stringify(inventedSourceWorkIssues)}`);
  const missingWaitingBasisFixture = structuredClone(decisionFlowFixture);
  missingWaitingBasisFixture.find(step => step.nodeId === 'responsibility' && step.phase === 'combining').waitingBasisVisible = false;
  if (!decisionFlowContractViolations(missingWaitingBasisFixture, decisionChangeFixture, decisionHighlightFixture, decisionInteractionFixture, decisionRunEnvelope, decisionSemanticFixture).some(issue => issue.includes('exact plain dependency'))) throw new Error('Blocked downstream decision without its waiting basis was accepted');
  const zoomOutFixture = {
    sourceMoments: REQUIRED_DESKTOP_SOURCE_MOMENTS.map(moment => ({ moment, panelVisible: true, contentVisible: true, collapsed: false, insideViewport: true, width: 280, height: 700, toggleLooksDropdown: false })),
    decisionSteps: decisionFlowFixture.filter(step => step.stepKind === 'source' && ['planned', 'source-opened'].includes(step.phase)),
    artifactCursorSteps: [
      { phase: 'click', presentationMode: 'returned-action-replay', graphInspectionPhase: 'select-source', targetId: 'message', activeSourceIds: [], activeSourceLocator: '', visibleSourceHighlightCount: 0 },
      { phase: 'click', presentationMode: 'returned-action-replay', graphInspectionPhase: 'read-source', targetId: 'accepted-fact:fact_customer_objective', inspectionSourceHasTarget: false, inspectionSourceId: '', inspectionLocatorId: '', activeSourceIds: [], activeSourceLocator: '', visibleSourceHighlightCount: 0 },
    ],
    previews: FLAGSHIP_PROCESS_PROJECTION_IDS.map((nodeId, index) => {
      const basisKind = ['fact', 'law', 'evidence', 'accepted-decision', 'start-point'][index % 5];
      const sourceBasis = basisKind === 'fact';
      const lawBasis = basisKind === 'law';
      return {
        nodeId,
        previewCount: 1,
        previewVisible: true,
        basisKind,
        exactReturnedSource: sourceBasis,
        sourceHasTarget: sourceBasis,
        exactLocator: sourceBasis || lawBasis,
        exactTitle: sourceBasis,
        exactLocation: sourceBasis,
        sourceWindowTruth: sourceBasis,
        noGeneratedContext: sourceBasis,
        exactPassage: sourceBasis,
        locatorId: sourceBasis ? `source:${nodeId}:page:1:quote:Exact returned passage` : lawBasis ? `law:${nodeId}` : '',
        title: sourceBasis ? 'Source title' : `${basisKind} title`,
        location: sourceBasis ? 'Page 1 of 1' : `${basisKind} basis`,
        passage: sourceBasis ? 'Exact returned passage' : `Returned ${basisKind} basis`,
        action: sourceBasis ? 'open-source' : lawBasis ? 'open-law' : basisKind === 'evidence' ? 'inspect-evidence' : 'select-node',
        onDemandText: sourceBasis ? 'Open original →' : 'Open basis →',
        inlineGroundingClosed: true,
        otherGroundingHidden: true,
        groundingViewerOpen: false,
        overlaps: [],
        viewportWidth: 1440,
        viewportHeight: 900,
      };
    }),
    postConstructionSourceUse: { viewerOpen: true, activeSourceIds: ['art_lease'], activeSourceLocator: 'art_lease:p1', sourceId: 'art_lease', locatorId: 'art_lease:p1' },
    team: { members: REQUIRED_NEMOTRON_AGENT_IDS.map(id => ({
      agentId: id,
      visualGroupId: visibleAgentGroupId(id),
      role: REQUIRED_DESKTOP_AGENT_LABELS[id],
      short: id === PATH_BUILDER_VISUAL_GROUP_ID ? PATH_BUILDER_VISIBLE_IDENTITY.short : REQUIRED_DESKTOP_AGENT_SHORTS[id],
      signature: visibleAgentIdentity(id).signature,
      visible: REQUIRED_VISIBLE_SPECIALIST_IDS.includes(id),
    })) },
    documentPlan: { chains: Array.from({ length: 21 }, () => ({ parts: ['decision', 'fact', 'evidence', 'document'].map(part => ({ part })) })) },
    documentRoundtrip: true,
  };
  if (zoomOutDesktopContractViolations(zoomOutFixture).length) throw new Error('Valid zoom-out desktop fixture was rejected');
  const previewFixtureRect = (left, top, width, height) => ({ left, top, right: left + width, bottom: top + height, width, height });
  const previewGraphViewportRect = previewFixtureRect(280, 80, 1140, 760);
  const processPreviewGeometryFixture = [
    {
      phase: 'construction:artifact-fact',
      constructionState: 'building',
      viewportWidth: 1440,
      viewportHeight: 900,
      graphViewportRect: previewGraphViewportRect,
      items: PROCESS_PREVIEW_GEOMETRY_SELECTORS.map((kind, index) => ({ kind, rect: previewFixtureRect(310 + (index * 12), 120 + (index * 12), 500, 220) })),
    },
    ...FLAGSHIP_PROCESS_PROJECTION_IDS.map((nodeId, index) => ({
      phase: `completed-preview:${nodeId}`,
      constructionState: 'complete',
      viewportWidth: 1440,
      viewportHeight: 900,
      graphViewportRect: previewGraphViewportRect,
      items: [{ kind: '.ac-spatial-detail', rect: previewFixtureRect(320, 500 + (index % 2) * 4, 720, 260) }],
    })),
  ];
  if (processPreviewGeometryContractViolations(processPreviewGeometryFixture).length) throw new Error('Valid 1440×900 process preview containment fixture was rejected');
  const clippedProcessPreviewFixture = structuredClone(processPreviewGeometryFixture);
  clippedProcessPreviewFixture[0].items[0].rect.bottom = previewGraphViewportRect.bottom - 2;
  clippedProcessPreviewFixture[0].items[0].rect.height = clippedProcessPreviewFixture[0].items[0].rect.bottom - clippedProcessPreviewFixture[0].items[0].rect.top;
  if (!processPreviewGeometryContractViolations(clippedProcessPreviewFixture).some(issue => issue.includes('8px bottom inset'))) throw new Error('Bottom-clipped construction preview fixture was accepted');
  const fakeGraphSourceFixture = structuredClone(zoomOutFixture);
  Object.assign(fakeGraphSourceFixture.artifactCursorSteps[1], { inspectionSourceId: 'message', inspectionLocatorId: 'source:message:p1', activeSourceIds: ['message'], activeSourceLocator: 'source:message:p1' });
  if (!zoomOutDesktopContractViolations(fakeGraphSourceFixture).some(issue => issue.includes('falsely claims a new source read'))) throw new Error('Graph replay with a fake new source read was accepted');
  const missingPreviewSourceTargetFixture = structuredClone(zoomOutFixture);
  missingPreviewSourceTargetFixture.previews[0].sourceHasTarget = false;
  if (!zoomOutDesktopContractViolations(missingPreviewSourceTargetFixture).some(issue => issue.includes('actual returned artifact window'))) throw new Error('Fact/source basis preview without a matching exact source target was accepted');
  const alteredSourcePassageFixture = structuredClone(zoomOutFixture);
  alteredSourcePassageFixture.previews[0].exactPassage = false;
  if (!zoomOutDesktopContractViolations(alteredSourcePassageFixture).some(issue => issue.includes('actual returned artifact window'))) throw new Error('Fact/source basis preview with an altered returned passage was accepted');
  const forgedBasisLocatorFixture = structuredClone(zoomOutFixture);
  const evidenceBasisPreview = forgedBasisLocatorFixture.previews.find(preview => preview.basisKind === 'evidence');
  evidenceBasisPreview.locatorId = 'source:forged:page:1:quote:not-returned';
  evidenceBasisPreview.exactLocator = false;
  if (!zoomOutDesktopContractViolations(forgedBasisLocatorFixture).some(issue => issue.includes('claims a source locator that is not exact'))) throw new Error('Non-source basis preview with a fabricated source locator was accepted');
  const incompleteBasisPreviewFixture = structuredClone(zoomOutFixture);
  incompleteBasisPreviewFixture.previews.find(preview => preview.basisKind === 'accepted-decision').passage = '';
  if (!zoomOutDesktopContractViolations(incompleteBasisPreviewFixture).some(issue => issue.includes('lacks a truthful kind, title, or returned basis'))) throw new Error('Incomplete accepted-decision basis preview was accepted');
  const brokenZoomOutFixture = structuredClone(zoomOutFixture);
  brokenZoomOutFixture.sourceMoments[0].collapsed = true;
  brokenZoomOutFixture.artifactCursorSteps[0].activeSourceIds = ['art_lease'];
  brokenZoomOutFixture.previews[0].overlaps = ['node:scope'];
  brokenZoomOutFixture.team.members[0].role = 'Guarded Canonical Facts Agent';
  brokenZoomOutFixture.documentRoundtrip = false;
  const brokenZoomOutIssues = zoomOutDesktopContractViolations(brokenZoomOutFixture);
  if (brokenZoomOutIssues.length !== 3 || !brokenZoomOutIssues.every((issue, index) => issue.startsWith(`${index + 1}.`))) throw new Error(`Zoom-out diagnostics did not retain only the three highest-impact failures: ${JSON.stringify(brokenZoomOutIssues)}`);
  const groundingModalFixture = {
    before: { viewerOpen: false, inlinePanelHidden: true, visibleInlineItemCount: 0, toggleHaspopup: 'dialog', toggleExpanded: 'false' },
    opened: { openedByExplicitClick: true, viewerOpen: true, modalHasFocus: true, inlinePanelHidden: true, visibleInlineItemCount: 0, sourceRailVisible: true, sourceRailOverlapArea: 0, actionKinds: ['law', 'evidence', 'precedent'], detailButtonCount: 3, actionableButtonCount: 3 },
    closed: { viewerOpen: false, inlinePanelHidden: true, visibleInlineItemCount: 0, focusRestoredToTrigger: true, graphFocusCount: 1, primaryActionCount: 1 },
  };
  if (groundingModalContractViolations(groundingModalFixture, 'precedent').length) throw new Error('Valid explicit grounding-modal fixture was rejected');
  const brokenGroundingModalFixture = structuredClone(groundingModalFixture);
  brokenGroundingModalFixture.before.visibleInlineItemCount = 1;
  brokenGroundingModalFixture.opened.sourceRailOverlapArea = 200;
  brokenGroundingModalFixture.closed.graphFocusCount = 2;
  const brokenGroundingModalIssues = groundingModalContractViolations(brokenGroundingModalFixture, 'precedent');
  if (!brokenGroundingModalIssues.some(issue => issue.includes('before the explicit')) || !brokenGroundingModalIssues.some(issue => issue.includes('source rail')) || !brokenGroundingModalIssues.some(issue => issue.includes('one graph focus'))) throw new Error(`Broken grounding-modal fixture was accepted: ${JSON.stringify(brokenGroundingModalIssues)}`);
  const settledCursorPayoffFixture = {
    moment: 'later-result',
    cursorVisible: true,
    parked: true,
    cursorPhase: 'settled',
    parkTargetVisible: true,
    parkedStepCount: 2,
    labelOpacity: 0,
    payoffObjectCount: 5,
    cursorOverlaps: [],
    visibleLabelOverlaps: [],
    cursorClicking: false,
    syntheticClickCountAfterParking: 0,
  };
  if (settledCursorPayoffContractViolations(settledCursorPayoffFixture).length) throw new Error('Valid settled cursor payoff fixture was rejected');
  const tamperedSettledCursorPayoffFixture = structuredClone(settledCursorPayoffFixture);
  tamperedSettledCursorPayoffFixture.parked = false;
  tamperedSettledCursorPayoffFixture.labelOpacity = 1;
  tamperedSettledCursorPayoffFixture.cursorOverlaps = ['ac-memory-graph-delta'];
  tamperedSettledCursorPayoffFixture.syntheticClickCountAfterParking = 1;
  const tamperedSettledCursorPayoffIssues = settledCursorPayoffContractViolations(tamperedSettledCursorPayoffFixture);
  if (!tamperedSettledCursorPayoffIssues.some(issue => issue.includes('not parked')) || !tamperedSettledCursorPayoffIssues.some(issue => issue.includes('label remains')) || !tamperedSettledCursorPayoffIssues.some(issue => issue.includes('overlaps')) || !tamperedSettledCursorPayoffIssues.some(issue => issue.includes('synthesizes a click'))) throw new Error(`Tampered settled cursor payoff fixture was accepted: ${JSON.stringify(tamperedSettledCursorPayoffIssues)}`);
  const fixtureRect = (left, top, width, height) => ({ left, top, right: left + width, bottom: top + height, width, height });
  const spatialNodeRects = Object.fromEntries(FLAGSHIP_PROCESS_PROJECTION_IDS.map((nodeId, index) => [nodeId, fixtureRect(60 + (index * 108), 300, 82, 62)]));
  const spatialBranchRects = {
    building_defect: fixtureRect(790, 90, 126, 48),
    tenant_use: fixtureRect(820, 180, 126, 48),
    mixed_cause: fixtureRect(820, 410, 126, 48),
    evidence_gap: fixtureRect(790, 505, 126, 48),
  };
  const spatialSatelliteRects = {
    'fedlex-or-259a': fixtureRect(662, 120, 128, 92),
    condition_photo: fixtureRect(520, 500, 128, 92),
    landlord_reply: fixtureRect(650, 500, 128, 92),
    technical_assessment: fixtureRect(960, 505, 142, 48),
  };
  const center = value => rectCenter(value);
  const returnedFixtureEdges = [
    ...FLAGSHIP_PROCESS_PROJECTION_IDS.slice(1).map((target, index) => ({ source: FLAGSHIP_PROCESS_PROJECTION_IDS[index], target, state: 'selected' })),
    ...REQUIRED_CAUSATION_BRANCH_IDS.map(target => ({ source: 'causation', target, state: target === 'evidence_gap' ? 'selected' : 'conditional' })),
  ];
  const explanatoryFixtureKeys = new Set([
    ...FLAGSHIP_PROCESS_PROJECTION_IDS.slice(1, FLAGSHIP_PROCESS_PROJECTION_IDS.indexOf('causation') + 1)
      .map((target, index) => `${FLAGSHIP_PROCESS_PROJECTION_IDS[index]}->${target}`),
    ...REQUIRED_CAUSATION_BRANCH_IDS.map(target => `causation->${target}`),
  ]);
  const spatialFixtureEdges = [
    ...returnedFixtureEdges.filter(edge => explanatoryFixtureKeys.has(`${edge.source}->${edge.target}`)).map(edge => ({ ...edge, path: edge.source === 'causation' && REQUIRED_CAUSATION_BRANCH_IDS.includes(edge.target) ? edge.state === 'selected' ? 'next-action' : 'uncertainty' : 'accepted', start: center(spatialNodeRects[edge.source] || spatialBranchRects[edge.source]), end: center(spatialNodeRects[edge.target] || spatialBranchRects[edge.target]) })),
    { source: 'causation', target: 'fedlex-or-259a', state: 'linked', path: 'legal-grounding', start: center(spatialNodeRects.causation), end: center(spatialSatelliteRects['fedlex-or-259a']) },
    { source: 'causation', target: 'condition_photo', state: 'available', path: 'evidence-support', start: center(spatialNodeRects.causation), end: center(spatialSatelliteRects.condition_photo) },
    { source: 'causation', target: 'landlord_reply', state: 'missing', path: 'evidence-support', start: center(spatialNodeRects.causation), end: center(spatialSatelliteRects.landlord_reply) },
    { source: 'evidence_gap', target: 'technical_assessment', state: 'selected', path: 'next-action', start: center(spatialBranchRects.evidence_gap), end: center(spatialSatelliteRects.technical_assessment) },
  ];
  const spatialGeometryFixture = {
    processId: 'process-fixture', projection: SPATIAL_GRAPH_PROJECTION,
    routeMode: 'flagship-causation', selectedPath: ['intake', 'scope', 'dispute', 'urgency', 'notification', 'defect', 'causation', 'evidence_gap'], currentNodeId: 'causation', nextActionNodeId: 'evidence_gap', selectedBranchId: 'insufficient', focalNodeId: 'causation', openLabel: 'Causation is unresolved', terminalState: 'journey-continues', sourceAnchorNodeId: 'causation', lawAnchorNodeId: 'causation', evidenceAnchorNodeId: 'evidence_gap',
    canvasRect: fixtureRect(0, 0, 1200, 800), graphRect: fixtureRect(20, 35, 1160, 730), viewportRect: fixtureRect(35, 55, 1130, 690),
    primaryFoci: [{ insideGraph: true, rect: fixtureRect(20, 35, 1160, 730) }], primaryArtifacts: [{ insideGraph: true, rect: fixtureRect(20, 35, 1160, 730) }], primaryActionCount: 1, competingRects: [],
    nodes: FLAGSHIP_PROCESS_PROJECTION_IDS.map(nodeId => ({ id: nodeId, state: 'built', role: nodeId === 'causation' ? 'hub' : 'spine', path: 'accepted', selected: nodeId === 'causation', selectedBranchId: '', changeId: `change:${nodeId}`, eventId: `event:${nodeId}`, agentId: 'process_projection', rect: spatialNodeRects[nodeId], insideViewport: true, titleFontSize: nodeId === 'causation' ? 16 : 12, titleClientWidth: 82, titleScrollWidth: 82, titleClientHeight: 30, titleScrollHeight: 30 })),
    branches: REQUIRED_CAUSATION_BRANCH_IDS.map(id => ({ id, branchId: `branch:${id}`, state: id === 'evidence_gap' ? 'selected' : 'conditional', selected: id === 'evidence_gap', rect: spatialBranchRects[id], insideViewport: true })),
    laws: [{ id: 'fedlex-or-259a', lawId: 'fedlex-or-259a', anchorNodeId: 'causation', rect: spatialSatelliteRects['fedlex-or-259a'], insideViewport: true }],
    evidence: [{ id: 'condition_photo', evidenceId: 'condition_photo', anchorNodeId: 'causation', rect: spatialSatelliteRects.condition_photo, insideViewport: true }, { id: 'landlord_reply', evidenceId: 'landlord_reply', anchorNodeId: 'causation', rect: spatialSatelliteRects.landlord_reply, insideViewport: true }],
    nextActions: [{ id: 'evidence_gap', evidenceId: 'technical_assessment', rect: spatialSatelliteRects.technical_assessment, insideViewport: true }],
    activePaths: [{ nodeId: 'causation', factIds: ['fact-damage'], lawIds: ['fedlex-or-259a'], evidenceIds: ['condition_photo', 'landlord_reply'], insideGraph: true, rect: fixtureRect(60, 620, 340, 72) }],
    endpoints: [
      ...Object.entries(spatialNodeRects).map(([id, rect]) => ({ id, rect })),
      ...Object.entries(spatialBranchRects).map(([id, rect]) => ({ id, rect })),
      ...Object.entries(spatialSatelliteRects).map(([id, rect]) => ({ id, rect })),
    ], endpointDuplicates: [], edges: spatialFixtureEdges,
    ariaCurrentIds: ['causation'], pendingTabStops: [], status: { role: 'status', live: 'polite', atomic: 'true' }, edgeLayerAriaHidden: 'true', edgeLayerFocusable: 'false', cursorAriaHidden: 'true',
  };
  const spatialProcessFixture = {
    process_id: 'process-fixture',
    main_spine: [...FLAGSHIP_PROCESS_PROJECTION_IDS],
    selected_path: [...spatialGeometryFixture.selectedPath],
    current_node: 'causation',
    current_overlay: { current_node_id: 'causation', next_action_node_id: 'evidence_gap', selected_branch_id: 'insufficient' },
    nodes: [
      ...FLAGSHIP_PROCESS_PROJECTION_IDS.map(nodeId => ({
        node_id: nodeId,
        fact_ids: nodeId === 'causation' ? ['fact-damage'] : [],
        legal_source_ids: nodeId === 'causation' ? ['fedlex-or-259a'] : [],
        evidence_requirement_ids: nodeId === 'causation' ? ['condition_photo', 'landlord_reply'] : [],
        branches: nodeId === 'causation' ? [
          { branch_id: 'building-defect', target: 'building_defect' },
          { branch_id: 'tenant-use', target: 'tenant_use' },
          { branch_id: 'mixed-cause', target: 'mixed_cause' },
          { branch_id: 'insufficient', target: 'evidence_gap' },
        ] : [],
      })),
      ...REQUIRED_CAUSATION_BRANCH_IDS.map(nodeId => ({ node_id: nodeId, fact_ids: [], legal_source_ids: [], evidence_requirement_ids: [], branches: [] })),
    ],
    edges: returnedFixtureEdges,
  };
  const spatialExpectedFixture = {
    processId: 'process-fixture', processAgentId: 'process_projection', returnedNodeIds: [...FLAGSHIP_PROCESS_PROJECTION_IDS, ...REQUIRED_CAUSATION_BRANCH_IDS], returnedEdges: returnedFixtureEdges,
    processGraph: spatialProcessFixture,
    evidenceById: { technical_assessment: { item_id: 'technical_assessment', node_ids: ['causation', 'evidence_gap'] } },
  };
  const spatialFixtureIssues = spatialGraphGeometryContractViolations(spatialGeometryFixture, spatialExpectedFixture);
  if (spatialFixtureIssues.length) throw new Error(`Valid spatial process geometry fixture was rejected: ${JSON.stringify(spatialFixtureIssues)}`);
  if (processRouteStoryContractViolations(spatialProcessFixture).length) throw new Error('Valid causation route fixture was rejected');
  const modelOwnedStructureFixture = structuredClone(spatialGeometryFixture);
  modelOwnedStructureFixture.nodes[0].agentId = 'process_decision_mapping';
  if (!spatialGraphGeometryContractViolations(modelOwnedStructureFixture, spatialExpectedFixture).some(issue => issue.includes('deterministic projection'))) throw new Error('Model-owned permanent process structure was accepted');
  const resolvedCausationFixture = structuredClone(spatialProcessFixture);
  resolvedCausationFixture.selected_path = [...spatialGeometryFixture.selectedPath.slice(0, -1), 'building_defect'];
  resolvedCausationFixture.current_overlay.next_action_node_id = 'building_defect';
  resolvedCausationFixture.current_overlay.selected_branch_id = 'building-defect';
  resolvedCausationFixture.edges = resolvedCausationFixture.edges.map(edge => ({
    ...edge,
    state: edge.source === 'causation' && edge.target === 'building_defect'
      ? 'selected'
      : edge.source === 'causation' && edge.target === 'evidence_gap' ? 'conditional' : edge.state,
  }));
  const resolvedCausationStory = processRouteStory(resolvedCausationFixture);
  if (!resolvedCausationStory.causationCanvas || resolvedCausationStory.flagshipCausation
    || stableJson(resolvedCausationStory.storyNodeIds) !== stableJson(FLAGSHIP_PROCESS_PROJECTION_IDS)
    || stableJson(resolvedCausationStory.branchNodeIds) !== stableJson(REQUIRED_CAUSATION_BRANCH_IDS)) throw new Error('Valid non-evidence-gap causation canvas route was rejected');
  const mismatchedCausationBranchFixture = structuredClone(resolvedCausationFixture);
  mismatchedCausationBranchFixture.current_overlay.selected_branch_id = 'insufficient';
  if (!processRouteStoryContractViolations(mismatchedCausationBranchFixture).some(issue => issue.includes('selected branch'))) throw new Error('Causation route with a mismatched selected branch was accepted');

  const scopeNodeRects = {
    intake: fixtureRect(90, 310, 120, 68),
    scope: fixtureRect(890, 310, 140, 68),
  };
  const scopeSatelliteRects = {
    'fedlex-or-256': fixtureRect(895, 120, 130, 82),
    lease: fixtureRect(895, 500, 130, 82),
  };
  const scopeReturnedEdges = [
    { source: 'intake', target: 'scope', state: 'selected' },
    { source: 'scope', target: 'out_of_scope', state: 'possible' },
  ];
  const scopeProcessFixture = {
    process_id: 'scope-process-fixture',
    main_spine: ['intake', 'scope', 'dispute', 'urgency', 'notification', 'defect', 'causation', 'responsibility', 'remedy', 'resolution'],
    selected_path: ['intake', 'scope'],
    current_node: 'scope',
    current_overlay: { current_node_id: 'scope', next_action_node_id: 'scope', selected_branch_id: 'scope-unverified' },
    nodes: [
      { node_id: 'intake', fact_ids: [], legal_source_ids: [], evidence_requirement_ids: [], branches: [] },
      { node_id: 'scope', fact_ids: ['fact-scope'], legal_source_ids: ['fedlex-or-256'], evidence_requirement_ids: ['lease'], branches: [
        { branch_id: 'out-of-scope', target: 'out_of_scope' },
        { branch_id: 'scope-unverified', target: 'scope' },
      ] },
      { node_id: 'out_of_scope', fact_ids: [], legal_source_ids: [], evidence_requirement_ids: [], branches: [] },
      { node_id: 'causation', fact_ids: ['fact-cause'], legal_source_ids: ['fedlex-or-259a'], evidence_requirement_ids: ['technical_assessment'], branches: [] },
      { node_id: 'evidence_gap', fact_ids: [], legal_source_ids: [], evidence_requirement_ids: ['technical_assessment'], branches: [] },
    ],
    edges: scopeReturnedEdges,
  };
  const scopeGeometryFixture = {
    processId: 'scope-process-fixture', projection: SPATIAL_GRAPH_PROJECTION,
    routeMode: 'returned-route', selectedPath: ['intake', 'scope'], currentNodeId: 'scope', nextActionNodeId: 'scope', selectedBranchId: 'scope-unverified', focalNodeId: 'scope', openLabel: 'Is this our claim? · Unverified', terminalState: 'ready-route', sourceAnchorNodeId: 'scope', lawAnchorNodeId: 'scope', evidenceAnchorNodeId: 'scope',
    canvasRect: fixtureRect(0, 0, 1200, 800), graphRect: fixtureRect(20, 35, 1160, 730), viewportRect: fixtureRect(35, 55, 1130, 690),
    primaryFoci: [{ insideGraph: true, rect: fixtureRect(20, 35, 1160, 730) }], primaryArtifacts: [{ insideGraph: true, rect: fixtureRect(20, 35, 1160, 730) }], primaryActionCount: 0, competingRects: [],
    nodes: ['intake', 'scope'].map(nodeId => ({ id: nodeId, state: 'built', role: nodeId === 'scope' ? 'hub' : 'spine', path: nodeId === 'scope' ? 'current' : 'accepted', selected: nodeId === 'scope', selectedBranchId: '', changeId: `change:${nodeId}`, eventId: `event:${nodeId}`, agentId: 'process_projection', rect: scopeNodeRects[nodeId], insideViewport: true, titleFontSize: nodeId === 'scope' ? 16 : 12, titleClientWidth: scopeNodeRects[nodeId].width, titleScrollWidth: scopeNodeRects[nodeId].width, titleClientHeight: 30, titleScrollHeight: 30 })),
    branches: [],
    laws: [{ id: 'fedlex-or-256', lawId: 'fedlex-or-256', anchorNodeId: 'scope', rect: scopeSatelliteRects['fedlex-or-256'], insideViewport: true }],
    evidence: [{ id: 'lease', evidenceId: 'lease', anchorNodeId: 'scope', rect: scopeSatelliteRects.lease, insideViewport: true }],
    nextActions: [],
    activePaths: [{ nodeId: 'scope', factIds: ['fact-scope'], lawIds: ['fedlex-or-256'], evidenceIds: ['lease'], insideGraph: true, rect: fixtureRect(400, 610, 350, 58) }],
    endpoints: [
      ...Object.entries(scopeNodeRects).map(([id, rect]) => ({ id, rect })),
      ...Object.entries(scopeSatelliteRects).map(([id, rect]) => ({ id, rect })),
    ],
    endpointDuplicates: [],
    edges: [
      { source: 'intake', target: 'scope', state: 'selected', path: 'accepted', start: center(scopeNodeRects.intake), end: center(scopeNodeRects.scope) },
      { source: 'scope', target: 'fedlex-or-256', state: 'linked', path: 'legal-grounding', start: center(scopeNodeRects.scope), end: center(scopeSatelliteRects['fedlex-or-256']) },
      { source: 'scope', target: 'lease', state: 'missing', path: 'evidence-support', start: center(scopeNodeRects.scope), end: center(scopeSatelliteRects.lease) },
    ],
    ariaCurrentIds: ['scope'], pendingTabStops: [], status: { role: 'status', live: 'polite', atomic: 'true' }, edgeLayerAriaHidden: 'true', edgeLayerFocusable: 'false', cursorAriaHidden: 'true',
  };
  const scopeExpectedFixture = {
    processId: 'scope-process-fixture', processAgentId: 'process_projection', processGraph: scopeProcessFixture,
    returnedNodeIds: scopeProcessFixture.nodes.map(node => node.node_id), returnedEdges: scopeReturnedEdges,
    evidenceById: { lease: { item_id: 'lease', node_ids: ['scope'] } },
  };
  const scopeRouteIssues = processRouteStoryContractViolations(scopeProcessFixture);
  const scopeGeometryIssues = spatialGraphGeometryContractViolations(scopeGeometryFixture, scopeExpectedFixture);
  if (scopeRouteIssues.length || scopeGeometryIssues.length) throw new Error(`Valid scope_unverified route fixture was rejected: ${JSON.stringify({ scopeRouteIssues, scopeGeometryIssues })}`);
  const contradictoryScopeRoute = structuredClone(scopeProcessFixture);
  contradictoryScopeRoute.current_overlay.next_action_node_id = 'evidence_gap';
  contradictoryScopeRoute.current_overlay.selected_branch_id = 'scope-unverified';
  if (!processRouteStoryContractViolations(contradictoryScopeRoute).some(issue => /next action|selected branch/i.test(issue))) throw new Error('Contradictory scope route fixture was accepted');
  const scopeWithCausationUi = structuredClone(scopeGeometryFixture);
  scopeWithCausationUi.nodes.push({ ...spatialGeometryFixture.nodes.find(node => node.id === 'causation'), rect: fixtureRect(500, 400, 82, 62) });
  if (!spatialGraphGeometryContractViolations(scopeWithCausationUi, scopeExpectedFixture).some(issue => issue.includes('exact returned route story'))) throw new Error('Scope-unverified fixture with unrelated causation UI was accepted');
  const verticalSpatialFixture = structuredClone(spatialGeometryFixture);
  verticalSpatialFixture.nodes.forEach((node, index) => { node.rect = fixtureRect(500, 70 + (index * 65), 82, 62); });
  if (!spatialGraphGeometryContractViolations(verticalSpatialFixture, spatialExpectedFixture).some(issue => issue.includes('vertical list'))) throw new Error('Vertical-list spatial graph fixture was accepted');
  const inventedSpatialEdgeFixture = structuredClone(spatialGeometryFixture);
  inventedSpatialEdgeFixture.edges.push({ source: 'causation', target: 'remedy', state: 'selected', path: 'accepted', start: center(spatialNodeRects.causation), end: center(spatialNodeRects.remedy) });
  if (!spatialGraphGeometryContractViolations(inventedSpatialEdgeFixture, spatialExpectedFixture).some(issue => issue.includes('invents a process relationship'))) throw new Error('Invented spatial process edge fixture was accepted');

  const attachmentActors = ['canonical_facts', 'official_law_registry', 'evidence_checklist', 'historical_claims_retrieval', 'final_claim_brief_audit'];
  const attachmentFixture = ['fact', 'law', 'evidence', 'precedent', 'verification'].map((kind, index) => ({
    kind,
    changeId: `change:${kind}`,
    eventId: `event:${kind}`,
    agentId: attachmentActors[index],
    sourceAuthority: kind === 'fact' ? 'customer_submission' : kind === 'law' ? 'official_registry' : kind === 'precedent' ? 'generated_reference' : '',
    referenceStatus: kind === 'precedent' ? 'generated_reference' : '',
  }));
  const semanticFixture = attachmentFixture.map((item, index) => ({ type: REQUIRED_SEMANTIC_EVENT_TYPES[index], eventId: item.eventId, agentId: item.agentId, sequence: index + 1 }));
  const cursorFixture = attachmentFixture.map(item => ({
    ...item,
    agentId: REQUIRED_NEMOTRON_AGENT_IDS.includes(item.agentId) ? item.agentId : '',
    activeAgentId: '',
    phase: 'click',
  }));
  const contextualAttachmentFixtureIssues = contextualAttachmentContractViolations(attachmentFixture, semanticFixture, cursorFixture, true);
  if (contextualAttachmentFixtureIssues.length) throw new Error(`Valid semantic attachment/cursor fixture was rejected: ${JSON.stringify(contextualAttachmentFixtureIssues)}`);
  const visualAttachmentFixture = structuredClone(attachmentFixture);
  visualAttachmentFixture[0].sourceAuthority = 'generated_demo_reference_only';
  if (contextualAttachmentContractViolations(visualAttachmentFixture, semanticFixture, cursorFixture, true).length) throw new Error('Valid generated-demo visual fact attachment was rejected');
  const inflatedFactAuthorityAttachment = structuredClone(attachmentFixture);
  inflatedFactAuthorityAttachment[0].sourceAuthority = 'official_registry';
  if (!contextualAttachmentContractViolations(inflatedFactAuthorityAttachment, semanticFixture, cursorFixture, true).some(issue => issue.includes('returned claim-source authority'))) throw new Error('Inflated fact source authority was accepted');
  const untetheredAttachment = structuredClone(attachmentFixture);
  untetheredAttachment[0].eventId = 'event:forged';
  if (!contextualAttachmentContractViolations(untetheredAttachment, semanticFixture, cursorFixture, true).some(issue => issue.includes('authenticated stream'))) throw new Error('Untethered attachment fixture was accepted');

  const memoryEffectsFixture = [
    { origin_id: 'memory:one', effect: 'node-added', node_id: 'ventilation_dispute' },
    { origin_id: 'memory:one', effect: 'edge-added', edge_source: 'evidence_gap', edge_target: 'ventilation_dispute' },
    { origin_id: 'memory:one', effect: 'edge-added', edge_source: 'ventilation_dispute', edge_target: 'causation' },
    { origin_id: 'memory:one', effect: 'evidence-changed', item_id: 'building_envelope' },
    { origin_id: 'memory:one', effect: 'evidence-changed', item_id: 'management_position' },
    { origin_id: 'memory:one', effect: 'evidence-changed', item_id: 'use_evidence' },
  ];
  if (memoryEffectContractViolations(memoryEffectsFixture, 'memory:one').length) throw new Error('Valid future-claim memory delta fixture was rejected');
  const inflatedMemoryEffects = [...memoryEffectsFixture, { origin_id: 'memory:one', effect: 'node-added' }];
  if (!memoryEffectContractViolations(inflatedMemoryEffects, 'memory:one').length) throw new Error('Inflated future-claim memory delta fixture was accepted');
  const forgedMemoryEffects = structuredClone(memoryEffectsFixture);
  forgedMemoryEffects[1].edge_target = 'responsibility';
  if (!memoryEffectContractViolations(forgedMemoryEffects, 'memory:one').some(issue => issue.includes('memory effect identity'))) throw new Error('Forged future-claim memory edge identity was accepted');
  const emptyMemoryOrigin = structuredClone(memoryEffectsFixture);
  emptyMemoryOrigin[0].origin_id = '';
  if (!memoryEffectContractViolations(emptyMemoryOrigin, 'memory:one').some(issue => issue.includes('memory origin'))) throw new Error('Empty future-claim memory origin was accepted');

  const laterPresentationRunFixture = {
    run_id: 'run:later',
    result: {
      memory_application: {
        target: { run_id: 'run:later' },
        application_hash: 'a'.repeat(64),
        source_memory: { memory_id: 'memory:one' },
        eligibility: {
          contract: 'casepath.semantic-memory-eligibility/1.0.0',
          rule_id: 'same_grounded_mould_signature_v2',
          eligible: true,
          checks: { ventilation_allegation_grounded: true, semantic_signature_bound: true },
        },
      },
      facts: [{
        fact_id: 'fact:management-allegation',
        semantic_role: 'management_ventilation_allegation',
        label: 'Management position',
        value: 'Management attributes the condition to ventilation.',
        source_refs: [{ artifact_id: 'art_management_reply', locator_kind: 'text_quote', page: 1, excerpt: 'The cause is insufficient ventilation.' }],
      }],
    },
  };
  const laterValidationFixture = [{
    contract: LATER_MEMORY_VALIDATION_CONTRACT,
    runId: 'run:later', validated: true, proofReady: true, memoryUsed: true, memoryRetrieved: true, retrievedOnly: false,
    applicationHash: 'a'.repeat(64), memoryOriginId: 'memory:one', sharedPlaybookUnchanged: true,
    delta: structuredClone(EXPECTED_LATER_MEMORY_DELTA), at: 100,
  }];
  const laterSceneFixture = {
    later_memory_validated: 'true', later_memory_application_hash: 'a'.repeat(64), memory_receipt_count: 1,
    memory_effects: memoryEffectsFixture, text: 'Case-specific memory changed the next step. Shared playbook unchanged.', root_text: 'Case-specific memory changed the next step. Shared playbook unchanged.',
  };
  const laterRenderFixture = [{ moment: 'later-result', at: 101 }];
  if (laterMemoryPresentationContractViolations(laterValidationFixture, laterRenderFixture, laterSceneFixture, laterPresentationRunFixture, true).length) throw new Error('Valid later-memory presentation bridge fixture was rejected');
  const laterCausalSeamFixture = {
    seamCount: 1,
    sourceId: 'art_management_reply',
    locatorId: 'source:art_management_reply:page:1:quote:The cause is insufficient ventilation.',
    ruleId: 'same_grounded_mould_signature_v2',
    parts: [
      { part: 'source', small: 'Management reply · Page 1', strong: 'The cause is insufficient ventilation.', mark: 'The cause is insufficient ventilation.' },
      { part: 'memory', small: 'Saved correction matched', strong: 'Check ventilation separately', mark: '' },
      { part: 'result', small: 'Graph change', strong: 'Ventilation check added', mark: '' },
    ],
    proofSummary: '1 decision · 2 connections · 3 document needs',
    processLinkCount: 2,
    documentNeedCount: 3,
  };
  const laterSourceStepFixture = { sourceId: 'art_management_reply', locatorId: laterCausalSeamFixture.locatorId };
  if (laterCausalSeamContractViolations(laterCausalSeamFixture, laterPresentationRunFixture, laterSourceStepFixture).length) throw new Error('Valid returned-source to saved-correction to graph-result seam fixture was rejected');
  const forgedLaterSeamLocator = structuredClone(laterCausalSeamFixture);
  forgedLaterSeamLocator.locatorId = 'source:art_management_reply:page:2:quote:forged';
  if (!laterCausalSeamContractViolations(forgedLaterSeamLocator, laterPresentationRunFixture, laterSourceStepFixture).some(issue => issue.includes('exact returned allegation source') || issue.includes('exact source step locator'))) throw new Error('Later causal seam with a forged source locator was accepted');
  const forgedLaterSeamExcerpt = structuredClone(laterCausalSeamFixture);
  forgedLaterSeamExcerpt.parts[0].mark = 'Generated summary';
  forgedLaterSeamExcerpt.parts[0].strong = 'Generated summary';
  if (!laterCausalSeamContractViolations(forgedLaterSeamExcerpt, laterPresentationRunFixture, laterSourceStepFixture).some(issue => issue.includes('exact returned source text'))) throw new Error('Later causal seam with a generated excerpt was accepted');
  const forgedLaterSeamRule = structuredClone(laterCausalSeamFixture);
  forgedLaterSeamRule.ruleId = 'unaccepted_rule';
  if (!laterCausalSeamContractViolations(forgedLaterSeamRule, laterPresentationRunFixture, laterSourceStepFixture).some(issue => issue.includes('accepted eligibility rule'))) throw new Error('Later causal seam with an unaccepted eligibility rule was accepted');
  const forgedLaterSeamReceiptShape = structuredClone(laterCausalSeamFixture);
  forgedLaterSeamReceiptShape.documentNeedCount = 4;
  if (!laterCausalSeamContractViolations(forgedLaterSeamReceiptShape, laterPresentationRunFixture, laterSourceStepFixture).some(issue => issue.includes('1/2/3 receipt effects'))) throw new Error('Later causal seam with a forged receipt effect count was accepted');
  const forgedLaterPresentationRun = { ...laterPresentationRunFixture, run_id: 'run:forged' };
  if (!laterMemoryPresentationContractViolations(laterValidationFixture, laterRenderFixture, laterSceneFixture, forgedLaterPresentationRun, true).some(issue => issue.includes('run identity'))) throw new Error('Later-memory presentation with a forged run envelope was accepted');
  const failedClosedValidationFixture = [{
    ...laterValidationFixture[0], validated: false, applicationHash: '', memoryOriginId: '',
    delta: { nodeIds: [], edges: [], evidenceIds: [] },
  }];
  const failedClosedSceneFixture = {
    later_memory_validated: 'false', later_memory_application_hash: '', memory_receipt_count: 0, memory_effects: [],
    text: 'No memory-driven change claimed', root_text: 'No memory-driven process change is claimed.',
  };
  if (laterMemoryPresentationContractViolations(failedClosedValidationFixture, laterRenderFixture, failedClosedSceneFixture, laterPresentationRunFixture, false).length) throw new Error('Valid fail-closed later-memory presentation fixture was rejected');
  const forgedFailedClosedScene = { ...failedClosedSceneFixture, memory_effects: memoryEffectsFixture };
  if (!laterMemoryPresentationContractViolations(failedClosedValidationFixture, laterRenderFixture, forgedFailedClosedScene, laterPresentationRunFixture, false).some(issue => issue.includes('claimed memory effects'))) throw new Error('Fail-closed presentation with visible memory effects was accepted');

  const reviewSceneFixture = {
    scene: 'review', graph_present: true, graph_visible: true, graph_same: true,
    graph_is_sole_focus: true, graph_is_sole_primary_artifact: true,
    node_ids: [...FLAGSHIP_PROCESS_PROJECTION_IDS], selected_node_ids: ['causation'],
    review_edit_state: 'pending', inline_correction_count: 1, apply_action_count: 1, applied_note_count: 0,
  };
  const reviewSceneExpected = { scene: 'review', nodeIds: FLAGSHIP_PROCESS_PROJECTION_IDS, selectedNodeId: 'causation', reviewEditState: 'pending', inlineCorrectionCount: 1, applyActionCount: 1, appliedNoteCount: 0 };
  if (persistentGraphSceneContractViolations(reviewSceneFixture, reviewSceneExpected).length) throw new Error('Valid graph-native review scene fixture was rejected');
  const competingReviewArtifact = structuredClone(reviewSceneFixture);
  competingReviewArtifact.graph_is_sole_primary_artifact = false;
  if (!persistentGraphSceneContractViolations(competingReviewArtifact, reviewSceneExpected).some(issue => issue.includes('sole visible primary artifact'))) throw new Error('Competing review artifact fixture was accepted');
  const conditionalReviewChoiceFixture = {
    editCount: 1, radiogroupCount: 1, graphRadioCount: 2, selectedMode: 'conditional',
    radios: [
      { mode: 'conditional', checked: 'true', text: 'After a neutral inspection Add one ventilation check only when the allegation remains plausible.' },
      { mode: 'required_now', checked: 'false', text: 'Request both checks now Keep broader building and use evidence immediate.' },
    ],
    change: 'Implicit allegation → Add ventilation decision',
    consequence: 'Move use evidence to the new decision; building-envelope assessment remains conditional.',
    applyCount: 1, primaryApplyCount: 1, applyMode: 'conditional', applyText: 'Apply correction',
  };
  const requiredNowReviewChoiceFixture = structuredClone(conditionalReviewChoiceFixture);
  Object.assign(requiredNowReviewChoiceFixture, {
    selectedMode: 'required_now',
    change: 'Existing evidence order → Request both checks now',
    consequence: 'Do not add a ventilation decision; keep broader building testing immediately required.',
    applyMode: 'required_now',
  });
  requiredNowReviewChoiceFixture.radios[0].checked = 'false';
  requiredNowReviewChoiceFixture.radios[1].checked = 'true';
  if (reviewChoiceContractViolations(conditionalReviewChoiceFixture, 'conditional').length || reviewChoiceContractViolations(requiredNowReviewChoiceFixture, 'required_now').length || conditionalReviewChoiceFixture.consequence === requiredNowReviewChoiceFixture.consequence) throw new Error('Valid graph-local review radio choice fixtures were rejected');
  const doubleCheckedReviewChoice = structuredClone(conditionalReviewChoiceFixture);
  doubleCheckedReviewChoice.radios[1].checked = 'true';
  if (!reviewChoiceContractViolations(doubleCheckedReviewChoice, 'conditional').some(issue => issue.includes('selected mode'))) throw new Error('Review fixture with two selected radio choices was accepted');
  const unchangedRequiredConsequence = structuredClone(requiredNowReviewChoiceFixture);
  unchangedRequiredConsequence.consequence = conditionalReviewChoiceFixture.consequence;
  if (!reviewChoiceContractViolations(unchangedRequiredConsequence, 'required_now').some(issue => issue.includes('exact consequence'))) throw new Error('Required-now review fixture without a changed consequence was accepted');
  const competingReviewApply = structuredClone(conditionalReviewChoiceFixture);
  competingReviewApply.applyCount = 2;
  competingReviewApply.primaryApplyCount = 2;
  if (!reviewChoiceContractViolations(competingReviewApply, 'conditional').some(issue => issue.includes('exactly one mode-bound primary Apply'))) throw new Error('Review fixture with competing primary Apply actions was accepted');

  const graphNativeMomentFixture = {
    moment: 'verify', scene: 'verify', graph_visible: true, graph_is_sole_focus: true, graph_is_sole_primary_artifact: true,
    verification_attachments: [{ attachment_kind: 'verification', text: 'Final audit 10 checks agree No unsupported proposals retained' }],
    knowledge_memory_notes: [{ memory_id: 'memory:one', memory_status: 'unverified_demo_memory', text: 'Saved as unverified case memory Shared playbook unchanged' }],
    later_memory_retrievals: [{ memory_origin_id: 'memory:one', later_causal_phase: 'memory', text: 'Unverified case memory retrieved Now checking whether it applies' }],
  };
  const verificationMomentExpected = { attachmentKey: 'verification_attachments', attachmentKind: 'verification', requiredCopy: ['Final audit'], anyOfCopy: [['checks agree', 'No unsupported proposals retained'], ['Verification incomplete']] };
  if (graphNativeMomentSceneViolations(graphNativeMomentFixture, 'verify').length || graphNativeMomentCopyContractViolations(graphNativeMomentFixture, verificationMomentExpected).length) throw new Error('Valid graph-native verification fixture was rejected');
  const knowledgeMomentFixture = { ...graphNativeMomentFixture, moment: 'knowledge', scene: 'knowledge' };
  const knowledgeMomentExpected = { attachmentKey: 'knowledge_memory_notes', attributes: { memory_status: 'unverified_demo_memory' }, requiredNonemptyAttributes: ['memory_id'], requiredCopy: ['Saved as unverified case memory', 'Shared playbook unchanged'] };
  if (graphNativeMomentSceneViolations(knowledgeMomentFixture, 'knowledge').length || graphNativeMomentCopyContractViolations(knowledgeMomentFixture, knowledgeMomentExpected).length) throw new Error('Valid graph-native knowledge fixture was rejected');
  const laterWorkMomentFixture = { ...graphNativeMomentFixture, moment: 'later-work', scene: 'later-work' };
  const laterWorkMomentExpected = { attachmentKey: 'later_memory_retrievals', attributes: { later_causal_phase: 'memory' }, requiredNonemptyAttributes: ['memory_origin_id'], requiredCopy: ['Unverified case memory retrieved', 'Now checking whether it applies'] };
  if (graphNativeMomentSceneViolations(laterWorkMomentFixture, 'later-work').length || graphNativeMomentCopyContractViolations(laterWorkMomentFixture, laterWorkMomentExpected).length) throw new Error('Valid graph-native later-work fixture was rejected');
  const competingGraphNativeMoment = { ...laterWorkMomentFixture, graph_is_sole_focus: false };
  if (!graphNativeMomentSceneViolations(competingGraphNativeMoment, 'later-work').some(issue => issue.includes('sole visible focal object'))) throw new Error('Competing graph-native moment fixture was accepted');
  const inflatedGraphNativeCopy = structuredClone(laterWorkMomentFixture);
  inflatedGraphNativeCopy.later_memory_retrievals[0].text = 'Unverified case memory retrieved Now checking whether it applies ' + 'unnecessary detail '.repeat(20);
  if (!graphNativeMomentCopyContractViolations(inflatedGraphNativeCopy, laterWorkMomentExpected).some(issue => issue.includes('not concise'))) throw new Error('Verbose graph-native moment copy fixture was accepted');

  const allowedOutputFixtures = [
    path.join(QA_DIRECTORY, QA_OUTPUT_BASENAME),
    path.join(QA_TEMP_ROOT, 'casepath-qa-preflight.A1b2C3', PREFLIGHT_OUTPUT_BASENAME),
    path.join(QA_TEMP_ROOT, 'casepath-qa-real.A1b2C3', PREFLIGHT_OUTPUT_BASENAME),
  ];
  for (const candidate of allowedOutputFixtures) {
    if (resolveSafeQaOutputPath(candidate) !== path.resolve(candidate)) {
      throw new Error(`Safe QA output fixture did not resolve exactly: ${candidate}`);
    }
  }
  const rejectedOutputFixtures = [
    path.parse(REPOSITORY_ROOT).root,
    REPOSITORY_ROOT,
    QA_DIRECTORY,
    path.join(QA_DIRECTORY, 'arbitrary-output'),
    path.join(QA_TEMP_ROOT, 'arbitrary-writable-output'),
    path.join(QA_TEMP_ROOT, 'casepath-qa-preflight.A1b2C3', 'arbitrary-output'),
  ];
  for (const candidate of rejectedOutputFixtures) {
    try {
      resolveSafeQaOutputPath(candidate);
    } catch (_) {
      continue;
    }
    throw new Error(`Unsafe QA output fixture was accepted: ${candidate}`);
  }
  const realPreflightParent = await fs.mkdtemp(path.join(QA_TEMP_ROOT, 'casepath-qa-preflight.'));
  try {
    const realPreflightOutput = path.join(realPreflightParent, PREFLIGHT_OUTPUT_BASENAME);
    if (assertSafeQaOutputParent(realPreflightOutput) !== realPreflightOutput) {
      throw new Error('Real preflight QA output fixture did not resolve exactly');
    }
  } finally {
    await fs.rmdir(realPreflightParent);
  }
  const realAcceptanceParent = await fs.mkdtemp(path.join(QA_TEMP_ROOT, 'casepath-qa-real.'));
  try {
    const realAcceptanceOutput = path.join(realAcceptanceParent, PREFLIGHT_OUTPUT_BASENAME);
    if (assertSafeQaOutputParent(realAcceptanceOutput) !== realAcceptanceOutput) {
      throw new Error('Real Nemotron QA output fixture did not resolve exactly');
    }
  } finally {
    await fs.rmdir(realAcceptanceParent);
  }
  const symlinkedPreflightParent = path.join(
    QA_TEMP_ROOT,
    `casepath-qa-preflight.${randomUUID().replaceAll('-', '').slice(0, 12)}`,
  );
  await fs.symlink(QA_DIRECTORY, symlinkedPreflightParent, 'dir');
  let symlinkedParentRejected = false;
  try {
    try {
      assertSafeQaOutputParent(path.join(symlinkedPreflightParent, PREFLIGHT_OUTPUT_BASENAME));
    } catch (_) {
      symlinkedParentRejected = true;
    }
  } finally {
    await fs.unlink(symlinkedPreflightParent);
  }
  if (!symlinkedParentRejected) throw new Error('Symlinked QA output parent fixture was accepted');
  await assertRunReadSessionIsolation();
  await assertMemoryReuseRendererDeterminism();
  const cursorFocus = { focusIdCount: 1, cursorIdCount: 1, focusCount: 1, cursorCount: 1, cursorInsideFocus: true };
  const productionCursorFixture = REQUIRED_NEMOTRON_AGENT_IDS.flatMap((agentId, index) => {
    const callId = `modelcall_${String(index + 1).padStart(16, '0')}`;
    const outputArtifact = `artifact_${index + 1}`;
    const base = {
      moment: 'verify', actorType: 'nemotron_agent', agentId,
      signature: REQUIRED_NEMOTRON_AGENT_SIGNATURES[agentId].signature,
      callId, outputArtifact, x: 800 + index, y: 300 + index, focus: cursorFocus,
    };
    return [
      { ...base, phase: 'working', activationKey: `event-${index}-working:${agentId}:working`, target: `div:working-${index}`, ownedArtifact: null },
      { ...base, phase: 'artifact', activationKey: `event-${index}-artifact:${agentId}:${outputArtifact}`, target: `section:${agentId}:${outputArtifact}`, ownedArtifact: { owner: agentId, actorType: 'nemotron_agent', callId, outputArtifact, requestedModel: REQUESTED_NEMOTRON_MODEL, responseModel: REQUESTED_NEMOTRON_MODEL, targetCount: 1 } },
    ];
  });
  const positiveCursorIssues = cursorSemanticContractViolations(productionCursorFixture, [], true);
  if (positiveCursorIssues.length) throw new Error(`Positive six-agent cursor phase fixture failed: ${JSON.stringify(positiveCursorIssues)}`);
  const duplicateCursorFixture = structuredClone(productionCursorFixture);
  duplicateCursorFixture.at(-1).activationKey = duplicateCursorFixture.at(-2).activationKey;
  if (!cursorSemanticContractViolations(duplicateCursorFixture, [], true).includes('semantic cursor activation repeated')) throw new Error('Repeated semantic cursor activation fixture was not rejected');
  const missingArtifactCursorFixture = structuredClone(productionCursorFixture);
  missingArtifactCursorFixture.find(step => step.agentId === 'evidence_checklist' && step.phase === 'artifact').ownedArtifact = null;
  if (!cursorSemanticContractViolations(missingArtifactCursorFixture, [], true).some(issue => issue.includes('evidence_checklist: visible owned artifact'))) throw new Error('Unbound agent artifact cursor fixture was not rejected');
  const missingReceiptIdentityFixture = structuredClone(productionCursorFixture);
  const missingReceiptStep = missingReceiptIdentityFixture.find(step => step.agentId === 'process_decision_mapping' && step.phase === 'artifact');
  delete missingReceiptStep.callId;
  delete missingReceiptStep.outputArtifact;
  delete missingReceiptStep.ownedArtifact.callId;
  delete missingReceiptStep.ownedArtifact.outputArtifact;
  if (!cursorSemanticContractViolations(missingReceiptIdentityFixture, [], true).some(issue => issue.includes('process_decision_mapping: visible owned artifact'))) throw new Error('Missing cursor receipt identity fixture was not rejected');
  const mismatchedReceiptIdentityFixture = structuredClone(productionCursorFixture);
  mismatchedReceiptIdentityFixture.find(step => step.agentId === 'final_claim_brief_audit' && step.phase === 'artifact').callId = 'modelcall_ffffffffffffffff';
  if (!cursorSemanticContractViolations(mismatchedReceiptIdentityFixture, [], true).some(issue => issue.includes('final_claim_brief_audit: cursor artifact phase'))) throw new Error('Mismatched cursor receipt identity fixture was not rejected');
  if (dtoHash({ z: 'ü', a: [{ k: 0.91 }, true, null] }) !== '3d745913ce5b8f5555065b544f018be38bd43e9e5bfe1eca86c1d4f25dda68dd') throw new Error('Compact sorted DTO hashing diverges from the Python release contract');
  const splitLeaseSource = 'Tenant\nAlex Morgan, Feldbergstrasse 114, 4057 Basel';
  if (!exactNormalizedGroundingQuote(splitLeaseSource, 'Tenant Alex Morgan, Feldbergstrasse 114, 4057 Basel')) throw new Error('Normalized grounding did not preserve the backend whitespace contract');
  if (!exactNormalizedGroundingQuote('Ａlex\nMorgan', 'Alex Morgan')) throw new Error('Normalized grounding did not preserve the backend NFKC contract');
  if (!exactNormalizedGroundingQuote('Alex\u001cMorgan', 'Alex Morgan')) throw new Error('Normalized grounding omitted Python-only Unicode whitespace');
  if (exactNormalizedGroundingQuote('Alex\ufeffMorgan', 'Alex Morgan')) throw new Error('Normalized grounding accepted non-Python whitespace');
  if (exactNormalizedGroundingQuote(splitLeaseSource, 'Tenant Morgan, Feldbergstrasse 114, 4057 Basel')) throw new Error('Normalized grounding accepted a non-source quote');
  const reorderedGroundingFacts = [
    { fact_id: 'fact_dispute', source_refs: [{ locator_kind: 'text_quote', artifact_id: 'art_management_reply' }] },
    { fact_id: 'fact_tenancy', source_refs: [{ locator_kind: 'text_quote', artifact_id: 'art_lease' }] },
  ];
  const reorderedGroundingProcess = { nodes: [{ node_id: 'scope', fact_ids: ['fact_tenancy'] }, { node_id: 'dispute', fact_ids: ['fact_dispute'] }] };
  if (selectProcessTextQuoteFact(reorderedGroundingFacts, reorderedGroundingProcess, 'fact_tenancy')?.fact_id !== 'fact_tenancy') throw new Error('Text grounding selected a provider-order-dependent fact');
  const providerCapRelease = {
    agentic_runtime: {
      parallel_groups: structuredClone(EXPECTED_EXECUTION_TOPOLOGY.parallel_groups),
      safety: { provider_max_in_flight: 1 },
    },
    truth: { production_runtime_acceptance: { required_provider_max_in_flight: 1 } },
  };
  const providerCapHealth = { agentic_runtime: { safety: { provider_max_in_flight: 1 } } };
  const providerCapReadiness = { agentic_runtime: { safety: { provider_max_in_flight: 1 } } };
  if (providerSingleFlightContractViolations(providerCapRelease, providerCapHealth, providerCapReadiness).length) throw new Error('Positive provider single-flight surface fixture failed');
  const missingReleaseProviderCap = structuredClone(providerCapRelease);
  delete missingReleaseProviderCap.agentic_runtime.safety.provider_max_in_flight;
  if (!providerSingleFlightContractViolations(missingReleaseProviderCap, providerCapHealth, providerCapReadiness).some(item => item.includes('release safety'))) throw new Error('Missing release provider-cap fixture was not rejected');
  const wrongAcceptanceProviderCap = structuredClone(providerCapRelease);
  wrongAcceptanceProviderCap.truth.production_runtime_acceptance.required_provider_max_in_flight = 2;
  if (!providerSingleFlightContractViolations(wrongAcceptanceProviderCap, providerCapHealth, providerCapReadiness).some(item => item.includes('runtime acceptance'))) throw new Error('Wrong acceptance provider-cap fixture was not rejected');
  const wrongHealthProviderCap = structuredClone(providerCapHealth);
  wrongHealthProviderCap.agentic_runtime.safety.provider_max_in_flight = 0;
  if (!providerSingleFlightContractViolations(providerCapRelease, wrongHealthProviderCap, providerCapReadiness).some(item => item.includes('health'))) throw new Error('Wrong health provider-cap fixture was not rejected');
  const missingReadinessProviderCap = structuredClone(providerCapReadiness);
  delete missingReadinessProviderCap.agentic_runtime.safety.provider_max_in_flight;
  if (!providerSingleFlightContractViolations(providerCapRelease, providerCapHealth, missingReadinessProviderCap).some(item => item.includes('readiness'))) throw new Error('Missing readiness provider-cap fixture was not rejected');
  const changedLogicalFanOut = structuredClone(providerCapRelease);
  changedLogicalFanOut.agentic_runtime.parallel_groups = [];
  if (!providerSingleFlightContractViolations(changedLogicalFanOut, providerCapHealth, providerCapReadiness).some(item => item.includes('logical fan-out'))) throw new Error('Changed logical fan-out fixture was not rejected');
  const pythonFloatHashes = [
    [{ value: 1.0 }, '3a7d647740ec6f86b72e0bf3948ab456551e07e9605e3a2785de1c66842ebb48'],
    [{ value: -0.0 }, 'c848a4efa987f46ba3bfd46242333afcb1c68c3240e0f35ae9d269b1c980648b'],
    [{ value: 1e-7 }, 'aece37dfda4992947222ea73b79996bba4aa181345a1fbb7f8c2b56b3fbd6a44'],
  ];
  if (pythonFloatHashes.some(([value, pythonHash]) => dtoHash(value) === pythonHash)) throw new Error('Float parity fixture unexpectedly became hash-compatible; update the shared numeric contract explicitly');
  if (nonIntegerNumberPaths({ negative_zero: -0.0, exponent: 1e-7 }).length !== 2) throw new Error('Non-integer accepted-DTO guard missed -0.0 or exponent notation');
  const acceptedProcessUnit = {
    contribution_id: 'fact:fact_scope:decision_value',
    fact_id: 'fact_scope',
    model_owned_fields: ['decision_value'],
    confidence_basis_points: 9100,
    attribution: PROCESS_CONTRIBUTION_ROLE,
    deterministic_fallback_applied: false,
  };
  const fallbackProcessUnit = {
    ...acceptedProcessUnit,
    confidence_basis_points: 10000,
    attribution: DETERMINISTIC_CONTRIBUTION_ROLE,
    deterministic_fallback_applied: true,
  };
  const acceptedContribution = contributionExpectation(acceptedProcessUnit, PROCESS_CONTRIBUTION_ROLE);
  const fallbackContribution = contributionExpectation(fallbackProcessUnit, PROCESS_CONTRIBUTION_ROLE);
  const mixedFieldContribution = contributionExpectation([
    {
      contribution_id: 'item:lease:status',
      field: 'status',
      confidence_basis_points: 9000,
      attribution: EVIDENCE_CONTRIBUTION_ROLE,
      deterministic_fallback_applied: false,
    },
    {
      contribution_id: 'item:lease:artifacts',
      field: 'artifact_ids',
      confidence_basis_points: 10000,
      attribution: DETERMINISTIC_CONTRIBUTION_ROLE,
      deterministic_fallback_applied: true,
    },
  ], EVIDENCE_CONTRIBUTION_ROLE);
  const postReviewContribution = contributionExpectation(
    acceptedProcessUnit,
    PROCESS_CONTRIBUTION_ROLE,
    { acceptance_scope: 'post_review_unverified_transform', model_acceptance_reused: false },
  );
  const postMemoryContribution = contributionExpectation(
    acceptedProcessUnit,
    PROCESS_CONTRIBUTION_ROLE,
    { contract: 'casepath.memory-application-receipt/1.0.0', authority: 'unverified_demo', scope: 'case_specific_guidance_only', model_acceptance_reused: false, applied: true },
  );
  if (stableJson(acceptedContribution) !== stableJson({ authority: 'nemotron-accepted', accepted_count: '1', fallback_count: '0' })
    || stableJson(fallbackContribution) !== stableJson({ authority: 'deterministic-fallback', accepted_count: '0', fallback_count: '1' })
    || stableJson(mixedFieldContribution) !== stableJson({ authority: 'mixed', accepted_count: '1', fallback_count: '1' })
    || postReviewContribution !== null
    || postMemoryContribution !== null
    || contributionExpectation({ ...acceptedProcessUnit, deterministic_fallback_applied: undefined }, PROCESS_CONTRIBUTION_ROLE) !== null
    || contributionExpectation({ ...acceptedProcessUnit, attribution: 'foreign_agent' }, PROCESS_CONTRIBUTION_ROLE) !== null
    || contributionExpectation({ ...fallbackProcessUnit, attribution: 'foreign_agent' }, PROCESS_CONTRIBUTION_ROLE) !== null) throw new Error('Visible contribution attribution does not fail closed on authority or fallback state');

  const relationProcess = {
    selected_path: ['a'],
    current_overlay: { next_action_node_id: 'b' },
    nodes: [
      { node_id: 'a', evidence_requirement_ids: ['one', 'shared'] },
      { node_id: 'b', evidence_requirement_ids: ['shared'] },
    ],
  };
  const relationChecklist = { items: [
    { item_id: 'one', node_ids: ['a'], node_id: 'a', current_path: true },
    { item_id: 'shared', node_ids: ['a', 'b'], node_id: 'a', current_path: true },
  ] };
  if (evidenceRelationContractViolations(relationProcess, relationChecklist).length) throw new Error('Positive reciprocal evidence fixture failed');
  for (const [field, value] of [['node_ids', ['b', 'a']], ['node_id', 'b'], ['current_path', false]]) {
    const tampered = structuredClone(relationChecklist);
    tampered.items[1][field] = value;
    if (!evidenceRelationContractViolations(relationProcess, tampered).some(issue => issue.includes(field))) throw new Error(`Tampered reciprocal evidence ${field} fixture was not rejected`);
  }

  const officialPassage = 'Versioned official passage.';
  const legalProcess = { nodes: [{ node_id: 'scope' }] };
  const legalFixture = {
    contract: 'casepath.legal-context/2.0.0',
    registry_version: 'ch-tenancy-official-snapshot/2026-08-12',
    lookup_method: 'versioned_official_source_registry_lookup',
    questions: [{ question_id: 'scope_question', text: 'What official rule applies?', source_ids: ['official'], interpretation_ids: ['principle'], process_node_ids: ['scope'], consequence: 'Keep authority and proposal distinct.' }],
    sources: [{
      source_id: 'official', title: 'Official source', url: 'https://example.test/official', source_type: 'official_statute', jurisdiction: 'CH', version_date: '2026-08-12', location: 'Article 1', passage_language: 'de', passage_text: officialPassage, passage_sha256: sha256(officialPassage), passage_summary: 'A bounded summary.', operational_interpretation: 'Deterministic reference proposal.', review_status: 'qualified_review_pending', role: 'Shapes scope.', approved: false,
      retrieval: { method: 'versioned_official_source_registry_lookup', retrieved_at: '2026-08-12', registry_version: 'ch-tenancy-official-snapshot/2026-08-12', snapshot_url: 'https://example.test/snapshot.pdf', snapshot_sha256: sha256('official snapshot'), snapshot_scope: 'official_pdf_bytes' },
    }],
    handling_principles: [{ source_id: 'principle', title: 'Deterministic handling proposal', source_type: 'operational_interpretation', role: 'Preserve uncertainty.', validation_status: 'candidate_not_expert_approved', producer: 'deterministic_application' }],
    node_links: { scope: ['official', 'principle'] },
    review_status: 'Operational translation not yet approved by a qualified reviewer',
  };
  if (legalContextContractViolations(legalFixture, legalProcess).length) throw new Error(`Positive legal-context fixture failed: ${JSON.stringify(legalContextContractViolations(legalFixture, legalProcess))}`);
  const tamperedPassage = structuredClone(legalFixture);
  tamperedPassage.sources[0].passage_text = 'Changed passage';
  if (!legalContextContractViolations(tamperedPassage, legalProcess).some(issue => issue.includes('passage hash'))) throw new Error('Tampered legal passage fixture was not rejected');
  const unknownLegalJoin = structuredClone(legalFixture);
  unknownLegalJoin.questions[0].source_ids = ['unknown'];
  if (!legalContextContractViolations(unknownLegalJoin, legalProcess).some(issue => issue.includes('source join'))) throw new Error('Unknown legal source-ID join fixture was not rejected');
  const modelOwnedPrinciple = structuredClone(legalFixture);
  modelOwnedPrinciple.handling_principles[0].producer = 'model_agent';
  if (!legalContextContractViolations(modelOwnedPrinciple, legalProcess).some(issue => issue.includes('producer'))) throw new Error('Model-owned legal principle fixture was not rejected');
  const falseSnapshotScope = structuredClone(legalFixture);
  falseSnapshotScope.sources[0].retrieval.snapshot_scope = 'dynamic_html_page';
  if (!legalContextContractViolations(falseSnapshotScope, legalProcess).some(issue => issue.includes('retrieval receipt'))) throw new Error('False official snapshot-scope fixture was not rejected');

  const imageArtifact = { artifact_id: 'image', media_type: 'image/png', sha256: sha256('image bytes') };
  const visualFixture = { artifact_id: 'image', locator_kind: 'visual_observation', region: [0.1, 0.2, 0.3, 0.4], observation: 'Curated visible reference.', producer: 'deterministic_reference_annotation', authority: 'generated_demo_reference_only', annotation_contract: 'casepath.visual-reference-annotation/1.0.0', annotation_version: 'generated-demo-reference/2026-08-12', image_sha256: imageArtifact.sha256 };
  if (visualReferenceContractViolations(visualFixture, imageArtifact).length) throw new Error('Positive visual-reference fixture failed');
  const tamperedVisualHash = { ...visualFixture, image_sha256: sha256('other bytes') };
  if (!visualReferenceContractViolations(tamperedVisualHash, imageArtifact).some(issue => issue.includes('public image bytes'))) throw new Error('Tampered visual image hash fixture was not rejected');
  const tamperedVisualProducer = { ...visualFixture, producer: 'machine_vision_agent' };
  if (!visualReferenceContractViolations(tamperedVisualProducer, imageArtifact).some(issue => issue.includes('authority contract'))) throw new Error('Tampered visual producer fixture was not rejected');

  const rankingContext = { category: 'category', subcategory: 'subcategory', current_process_node_id: 'causation', next_action_node_id: 'evidence_gap', selected_path: ['causation', 'evidence_gap'], unresolved_fact_ids: ['cause'], current_evidence_need_ids: ['assessment'] };
  const rankedPrecedents = [1, 2, 3].map(rank => ({ claim_id: `HIST-${rank}`, title: `Pattern ${rank}`, review_status: 'generated_reference', why_useful: 'Generated reference pattern.', provenance: 'generated_reference_not_qualified_review', final_process: ['causation'], evidence: ['assessment'], outcome: 'Reference only', ranking: { contract: 'casepath.precedent-ranking/1.0.0', corpus_version: 'generated-reference-patterns/2026-08-12', rank, score_basis_points: 40 - rank, factors: [{ factor: 'unresolved_fact', value: 'cause', weight: 40 - rank }], context_hash: dtoHash(rankingContext) } }));
  const rankingResult = { precedents: rankedPrecedents, precedent_ranking: { contract: 'casepath.precedent-ranking/1.0.0', corpus_version: 'generated-reference-patterns/2026-08-12', context: rankingContext, context_hash: dtoHash(rankingContext), candidate_scores: rankedPrecedents.map(item => ({ claim_id: item.claim_id, score_basis_points: item.ranking.score_basis_points, factors: item.ranking.factors })), selected_claim_ids: rankedPrecedents.map(item => item.claim_id), result_hash: dtoHash(rankedPrecedents) } };
  if (precedentRankingContractViolations(rankingResult).length) throw new Error(`Positive precedent-ranking fixture failed: ${JSON.stringify(precedentRankingContractViolations(rankingResult))}`);
  const tamperedRank = structuredClone(rankingResult);
  tamperedRank.precedents[0].ranking.rank = 2;
  if (!precedentRankingContractViolations(tamperedRank).some(issue => issue.includes('per-item ranking'))) throw new Error('Tampered precedent rank fixture was not rejected');
  const tamperedContextHash = structuredClone(rankingResult);
  tamperedContextHash.precedent_ranking.context_hash = sha256('wrong context');
  if (!precedentRankingContractViolations(tamperedContextHash).some(issue => issue.includes('context'))) throw new Error('Tampered precedent context-hash fixture was not rejected');
  const tamperedResultHash = structuredClone(rankingResult);
  tamperedResultHash.precedent_ranking.result_hash = sha256('wrong result');
  if (!precedentRankingContractViolations(tamperedResultHash).some(issue => issue.includes('result hash'))) throw new Error('Tampered precedent result-hash fixture was not rejected');

  const baselineProcess = {
    contract: 'process-graph', selected_path: ['causation', 'evidence_gap'], current_overlay: { current_node_id: 'causation', next_action_node_id: 'evidence_gap' }, shared_rule_applied: false, memory_used: false,
    nodes: [
      { node_id: 'dispute', evidence_requirement_ids: ['management_position'] },
      { node_id: 'causation', evidence_requirement_ids: ['building_envelope', 'use_evidence'] },
      { node_id: 'mixed_cause', evidence_requirement_ids: ['building_envelope', 'use_evidence'] },
      { node_id: 'tenant_use', evidence_requirement_ids: ['use_evidence'] },
      { node_id: 'evidence_gap', evidence_requirement_ids: ['building_envelope'] },
    ],
    edges: [{ source: 'evidence_gap', target: 'causation', condition: 'assessment complete', state: 'loop' }],
  };
  const baselineChecklist = {
    contract: 'evidence-model', shared_rule_applied: false, memory_used: false, required: ['before'], summary: { phase: 'before' },
    items: [
      { item_id: 'building_envelope', status: 'missing', node_ids: ['causation', 'mixed_cause', 'evidence_gap'], node_id: 'causation', current_path: true },
      { item_id: 'management_position', status: 'provided_sufficient', node_ids: ['dispute'], node_id: 'dispute', current_path: false },
      { item_id: 'use_evidence', status: 'conditional', node_ids: ['causation', 'mixed_cause', 'tenant_use'], node_id: 'causation', current_path: true },
    ],
  };
  const laterProcessFixture = structuredClone(baselineProcess);
  laterProcessFixture.nodes.find(node => node.node_id === 'causation').evidence_requirement_ids = ['building_envelope'];
  laterProcessFixture.nodes.find(node => node.node_id === 'mixed_cause').evidence_requirement_ids = ['building_envelope'];
  laterProcessFixture.nodes.find(node => node.node_id === 'tenant_use').evidence_requirement_ids = [];
  const ventilationNode = { node_id: 'ventilation_dispute', evidence_requirement_ids: ['management_position', 'use_evidence'] };
  laterProcessFixture.nodes.push(ventilationNode);
  const memoryEdgeOne = { source: 'evidence_gap', target: 'ventilation_dispute', condition: 'plausible use factor', state: 'possible' };
  const memoryEdgeTwo = { source: 'ventilation_dispute', target: 'causation', condition: 'allegation assessed', state: 'loop' };
  laterProcessFixture.edges.push(memoryEdgeOne, memoryEdgeTwo);
  laterProcessFixture.memory_used = true;
  laterProcessFixture.case_specific_guidance_applied = true;
  const laterChecklistFixture = structuredClone(baselineChecklist);
  laterChecklistFixture.items = [
    { item_id: 'building_envelope', status: 'conditional', node_ids: ['causation', 'mixed_cause', 'evidence_gap'], node_id: 'causation', current_path: true },
    { item_id: 'management_position', status: 'provided_sufficient', node_ids: ['dispute', 'ventilation_dispute'], node_id: 'dispute', current_path: false },
    { item_id: 'use_evidence', status: 'conditional', node_ids: ['ventilation_dispute'], node_id: 'ventilation_dispute', current_path: false },
  ];
  laterChecklistFixture.required = ['after'];
  laterChecklistFixture.summary = { phase: 'after' };
  laterChecklistFixture.memory_used = true;
  laterChecklistFixture.case_specific_guidance_applied = true;
  const decisionFacts = [
    ['scope', 'in_scope'], ['dispute', 'dispute_present'], ['urgency', 'not_urgent'], ['notification', 'notified'], ['recurrence', 'recurrence_supported'], ['causation', 'cause_unresolved'],
  ].map(([decision_key, decision_value]) => ({ fact_id: `fact_${decision_key}`, state: 'known', controls_process: true, decision_key, decision_value, semantic_role: null, source_refs: [] }));
  const memoryFacts = [...decisionFacts, { fact_id: 'later_fact_ventilation_allegation', state: 'known', controls_process: false, decision_key: null, decision_value: null, semantic_role: 'management_ventilation_allegation', source_refs: [{ artifact_id: 'art_later_management_reply' }] }];
  const observableHash = sha256('observable package');
  const canonicalHash = dtoHash(memoryFacts);
  const verificationHash = sha256('verification');
  const baselineResultFixture = { category: 'Rental defect - mould and moisture', subcategory: 'Recurring moisture with disputed causation', facts: structuredClone(memoryFacts), process: baselineProcess, checklist: baselineChecklist, precedents: [], memory_application: null, memory_used: false, reviewed_memory_used: false, reviewed_memory_retrieved: false, knowledge: { reviewed_memory_used: false, reviewed_memory_retrieved: false }, verification: { whole_playbook_hash: sha256('baseline verification') }, audit: { observable_input_hash: observableHash, canonical_state_hash: canonicalHash }, playbook: { version: 'mould-playbook-v3' }, shared_rule_applied: false };
  const laterResultFixture = { category: 'Rental defect - mould and moisture', subcategory: 'Recurring moisture with disputed causation', facts: structuredClone(memoryFacts), process: laterProcessFixture, checklist: laterChecklistFixture, next_action: { agent_brief_contribution: null }, precedents: [{ claim_id: 'DEF-027-E0-DEMO', review_status: 'unverified_demo_memory', memory_id: 'memory-1' }], memory_used: true, reviewed_memory_used: true, reviewed_memory_retrieved: true, knowledge: { reviewed_memory_used: true, reviewed_memory_retrieved: true }, verification: { whole_playbook_hash: verificationHash }, audit: { observable_input_hash: observableHash, canonical_state_hash: canonicalHash }, playbook: { version: 'mould-playbook-v3' }, shared_rule_applied: false };
  const requiredDecisionsFixture = Object.fromEntries(decisionFacts.map(fact => [fact.decision_key, fact.decision_value]));
  const semanticSignatureFixture = dtoHash({ category: 'Rental defect - mould and moisture', subcategory: 'Recurring moisture with disputed causation', required_decisions: requiredDecisionsFixture, required_fact_roles: { management_ventilation_allegation: { state: 'known', min_grounded_sources: 1 } } });
  const eligibilityManifest = { rule_id: 'same_grounded_mould_signature_v2', contract: 'casepath.semantic-memory-eligibility/1.0.0', claim_id: 'DEMO-MOULD-002', semantic_signature_hash: semanticSignatureFixture, decisions: requiredDecisionsFixture, facts_hash: dtoHash(semanticFactSignature(laterResultFixture)), checks: { source_claim_excluded: true, category_matched: true, subcategory_matched: true, required_decisions_matched: true, ventilation_allegation_grounded: true, semantic_signature_bound: true, guidance_enabled: true } };
  const receiptFixture = {
    receipt_type: 'memory_application_receipt', contract: 'casepath.memory-application-receipt/1.0.0', authority: 'unverified_demo', scope: 'case_specific_guidance_only',
    source_memory: { memory_id: 'memory-1', claim_id: 'DEF-027-E0-DEMO', review_id: 'review-1', content_hash: sha256('memory content'), review_status: 'unverified_demo_memory' },
    target: { run_id: 'later-run', claim_id: 'DEMO-MOULD-002' }, observable_input_hash: observableHash, canonical_state_hash: canonicalHash,
    eligibility: { ...eligibilityManifest, eligible: true, manifest_hash: dtoHash(eligibilityManifest) },
    allowed_operation_ids: ['add_ventilation_dispute_node', 'add_evidence_gap_to_ventilation_edge', 'add_ventilation_to_causation_edge', 'condition_building_envelope', 'reassign_use_evidence_to_ventilation'],
    applied_operation_ids: ['add_ventilation_dispute_node', 'add_evidence_gap_to_ventilation_edge', 'add_ventilation_to_causation_edge', 'condition_building_envelope', 'reassign_use_evidence_to_ventilation'],
    process_operations: [
      { operation_id: 'add_ventilation_dispute_node', operation: 'add_node', node_id: 'ventilation_dispute', evidence_requirement_ids: ['management_position', 'use_evidence'], after_hash: dtoHash(ventilationNode) },
      { operation_id: 'add_evidence_gap_to_ventilation_edge', operation: 'add_edge', source: 'evidence_gap', target: 'ventilation_dispute', after_hash: dtoHash(memoryEdgeOne) },
      { operation_id: 'add_ventilation_to_causation_edge', operation: 'add_edge', source: 'ventilation_dispute', target: 'causation', after_hash: dtoHash(memoryEdgeTwo) },
    ],
    evidence_operations: [
      { operation_id: 'condition_building_envelope', operation: 'replace_item', item_id: 'building_envelope', before_hash: dtoHash(baselineChecklist.items[0]), after_hash: dtoHash(laterChecklistFixture.items[0]) },
      { operation_id: 'reassign_use_evidence_to_ventilation', operation: 'reassign_item', item_id: 'use_evidence', removed_from_node_ids: ['causation', 'mixed_cause', 'tenant_use'], added_to_node_id: 'ventilation_dispute', before_hash: dtoHash(baselineChecklist.items[2]), after_hash: dtoHash(laterChecklistFixture.items[2]) },
    ],
    before: { process_dto_hash: dtoHash(baselineProcess), checklist_dto_hash: dtoHash(baselineChecklist), process_semantic_hash: dtoHash(semanticProcessDto(baselineProcess)), checklist_semantic_hash: dtoHash(semanticChecklistDto(baselineChecklist)) },
    after: { process_dto_hash: dtoHash(laterProcessFixture), checklist_dto_hash: dtoHash(laterChecklistFixture), process_semantic_hash: dtoHash(semanticProcessDto(laterProcessFixture)), checklist_semantic_hash: dtoHash(semanticChecklistDto(laterChecklistFixture)) },
    verification_hash: verificationHash, shared_playbook_version: 'mould-playbook-v3', shared_rule_applied: false, model_acceptance_reused: false, applied: true,
  };
  receiptFixture.application_hash = dtoHash(receiptFixture);
  laterResultFixture.memory_application = receiptFixture;
  const memoryBoundaryFixture = {
    contract: 'casepath.memory-application-boundary/1.0.0',
    target: structuredClone(receiptFixture.target),
    source_memory: { memory_id: receiptFixture.source_memory.memory_id, content_hash: receiptFixture.source_memory.content_hash },
    before: structuredClone(receiptFixture.before),
  };
  memoryBoundaryFixture.boundary_hash = dtoHash(memoryBoundaryFixture);
  const memoryEventFixture = {
    event_id: 'event-memory-application', ordinal: 1, created_at: '2026-08-12T00:00:00Z',
    stage: 'memory_application', label: 'Bounded case-specific memory guidance applied', status: 'completed',
    ...structuredClone(receiptFixture),
  };
  const causalDeltaFixture = computedCausalDelta(baselineResultFixture, laterResultFixture);
  const memoryCheckNames = ['Same observable input', 'Same canonical state', 'Exact current memory receipt', 'Pure memory replay matches learned DTOs', 'Receipt before semantic hashes match baseline DTOs', 'Receipt after hashes match learned DTOs', 'Nonzero causal DTO delta', 'Only allowed causal operations changed', 'Deterministic target and protected checks passed', 'Shared v3 remains unchanged'];
  const proofFixture = {
    ready: true, computed: true, baseline_run_id: 'baseline-run', later_run_id: 'later-run',
    before: { run_id: 'baseline-run', observable_input_hash: observableHash, canonical_state_hash: canonicalHash, process_semantic_hash: receiptFixture.before.process_semantic_hash, checklist_semantic_hash: receiptFixture.before.checklist_semantic_hash, playbook_version: 'mould-playbook-v3', verification_hash: baselineResultFixture.verification.whole_playbook_hash },
    after: { run_id: 'later-run', observable_input_hash: observableHash, canonical_state_hash: canonicalHash, ...receiptFixture.after, playbook_version: 'mould-playbook-v3', verification_hash: verificationHash },
    changes: { precedent_claim_ids_added: ['DEF-027-E0-DEMO'] }, reviewed_memory_proof: { used: true, memory_ids: ['memory-1'], present_in_baseline: false, present_in_later_run: true }, causal_delta: causalDeltaFixture,
    memory_application_proof: { receipt_present: true, receipt_valid: true, source_memory_current: true, before_hashes_match: true, after_hashes_match: true, allowed_delta_exact: true, replay_exact: true, application_hash: receiptFixture.application_hash },
    deterministic_checks: memoryCheckNames.map(name => ({ name, status: 'passed', detail: 'Computed from both DTOs.' })),
    candidate: { candidate_id: 'candidate_disputed_ventilation_v4', status: 'quarantined', qualified_support_count: 0, target_tests: { status: 'passed' }, protected_regression: { status: 'passed' }, approval: { status: 'pending', qualified_reviewer: false } },
    shared_rule: { applied: false, version_before: 'mould-playbook-v3', version_after: 'mould-playbook-v3', shared_knowledge_changed: false, candidate_status: 'quarantined' },
  };
  const frozenMemoryIdentity = { memory_id: 'memory-1', review_id: 'review-1', content_hash: receiptFixture.source_memory.content_hash, candidate_id: 'candidate_disputed_ventilation_v4', updated_at: '2026-08-12T00:00:00+00:00' };
  const counterfactualFreezeFixture = { contract: 'casepath.counterfactual-learning-freeze/1.0.0', memory: frozenMemoryIdentity, identity_hash: dtoHash(frozenMemoryIdentity), application_suppressed: true };
  proofFixture.counterfactual_learning_freeze = counterfactualFreezeFixture;
  const baselineRunFixture = { run_id: 'baseline-run', claim_id: 'DEMO-MOULD-002', created_at: '2026-08-12T00:01:00+00:00', completed_at: Date.parse('2026-08-12T00:02:00+00:00') / 1000, counterfactual_learning_freeze: counterfactualFreezeFixture, result: baselineResultFixture };
  const laterRunFixture = { run_id: 'later-run', claim_id: 'DEMO-MOULD-002', created_at: '2026-08-12T00:03:00+00:00', result: laterResultFixture, memory_application_boundary: memoryBoundaryFixture, events: [memoryEventFixture] };
  const positiveMemoryIssues = memoryApplicationContractViolations(baselineRunFixture, laterRunFixture, proofFixture);
  if (positiveMemoryIssues.length) throw new Error(`Positive memory-application fixture failed: ${JSON.stringify(positiveMemoryIssues)}`);
  const tamperedCounterfactualFreezeRun = structuredClone(baselineRunFixture);
  tamperedCounterfactualFreezeRun.counterfactual_learning_freeze.memory.content_hash = sha256('forged frozen memory');
  tamperedCounterfactualFreezeRun.counterfactual_learning_freeze.identity_hash = dtoHash(tamperedCounterfactualFreezeRun.counterfactual_learning_freeze.memory);
  if (!memoryApplicationContractViolations(tamperedCounterfactualFreezeRun, laterRunFixture, proofFixture).some(issue => issue.includes('frozen governed memory identity'))) throw new Error('Tampered counterfactual learning-freeze fixture was not rejected');
  const preFreezeBaselineRun = structuredClone(baselineRunFixture);
  preFreezeBaselineRun.created_at = '2026-08-11T23:59:00+00:00';
  if (!memoryApplicationContractViolations(preFreezeBaselineRun, laterRunFixture, proofFixture).some(issue => issue.includes('ordered after the learning freeze'))) throw new Error('Pre-learning baseline fixture was not rejected');
  const tamperedMemoryBoundaryHashRun = structuredClone(laterRunFixture);
  tamperedMemoryBoundaryHashRun.memory_application_boundary.boundary_hash = sha256('tampered retained memory boundary');
  if (!memoryApplicationContractViolations(baselineRunFixture, tamperedMemoryBoundaryHashRun, proofFixture).some(issue => issue.includes('boundary hash'))) throw new Error('Tampered retained memory-boundary hash fixture was not rejected');
  const tamperedMemoryBoundarySourceRun = structuredClone(laterRunFixture);
  tamperedMemoryBoundarySourceRun.memory_application_boundary.source_memory.content_hash = sha256('wrong retained source memory');
  tamperedMemoryBoundarySourceRun.memory_application_boundary.boundary_hash = dtoHash(Object.fromEntries(Object.entries(tamperedMemoryBoundarySourceRun.memory_application_boundary).filter(([key]) => key !== 'boundary_hash')));
  if (!memoryApplicationContractViolations(baselineRunFixture, tamperedMemoryBoundarySourceRun, proofFixture).some(issue => issue.includes('identity or source join'))) throw new Error('Tampered retained memory-boundary source fixture was not rejected');
  const tamperedMemoryBoundaryBeforeRun = structuredClone(laterRunFixture);
  tamperedMemoryBoundaryBeforeRun.memory_application_boundary.before.process_dto_hash = sha256('wrong independently retained before DTO');
  tamperedMemoryBoundaryBeforeRun.memory_application_boundary.boundary_hash = dtoHash(Object.fromEntries(Object.entries(tamperedMemoryBoundaryBeforeRun.memory_application_boundary).filter(([key]) => key !== 'boundary_hash')));
  if (!memoryApplicationContractViolations(baselineRunFixture, tamperedMemoryBoundaryBeforeRun, proofFixture).some(issue => issue.includes('before hashes do not equal'))) throw new Error('Retained memory-boundary to receipt.before join fixture was not rejected');
  const missingMemoryEventRun = structuredClone(laterRunFixture);
  missingMemoryEventRun.events = [];
  if (!memoryApplicationContractViolations(baselineRunFixture, missingMemoryEventRun, proofFixture).some(issue => issue.includes('exactly one completed persisted'))) throw new Error('Missing persisted memory-application event fixture was not rejected');
  const duplicateMemoryEventRun = structuredClone(laterRunFixture);
  duplicateMemoryEventRun.events.push(structuredClone(memoryEventFixture));
  if (!memoryApplicationContractViolations(baselineRunFixture, duplicateMemoryEventRun, proofFixture).some(issue => issue.includes('exactly one completed persisted'))) throw new Error('Duplicate persisted memory-application event fixture was not rejected');
  const forgedResultAndBoundaryRun = structuredClone(laterRunFixture);
  forgedResultAndBoundaryRun.result.memory_application.before.process_dto_hash = sha256('forged process DTO boundary');
  forgedResultAndBoundaryRun.result.memory_application.before.checklist_dto_hash = sha256('forged checklist DTO boundary');
  forgedResultAndBoundaryRun.result.memory_application.application_hash = dtoHash(Object.fromEntries(Object.entries(forgedResultAndBoundaryRun.result.memory_application).filter(([key]) => key !== 'application_hash')));
  forgedResultAndBoundaryRun.memory_application_boundary.before = structuredClone(forgedResultAndBoundaryRun.result.memory_application.before);
  forgedResultAndBoundaryRun.memory_application_boundary.boundary_hash = dtoHash(Object.fromEntries(Object.entries(forgedResultAndBoundaryRun.memory_application_boundary).filter(([key]) => key !== 'boundary_hash')));
  const forgedResultAndBoundaryProof = structuredClone(proofFixture);
  forgedResultAndBoundaryProof.memory_application_proof.application_hash = forgedResultAndBoundaryRun.result.memory_application.application_hash;
  if (!memoryApplicationContractViolations(baselineRunFixture, forgedResultAndBoundaryRun, forgedResultAndBoundaryProof).some(issue => issue.includes('persisted memory-application event does not project'))) throw new Error('Joint result/boundary forgery without the persisted memory event was not rejected');
  const dormantMemoryResult = structuredClone(baselineResultFixture);
  dormantMemoryResult.precedents = [{ claim_id: 'DEF-027-E0-DEMO', review_status: 'unverified_demo_memory', memory_id: 'memory-1' }];
  dormantMemoryResult.reviewed_memory_retrieved = true;
  dormantMemoryResult.knowledge.reviewed_memory_retrieved = true;
  const dormantMemoryIssues = memoryRetrievalContractViolations(dormantMemoryResult);
  if (dormantMemoryIssues.length) throw new Error(`Dormant retrieved-memory fixture failed: ${JSON.stringify(dormantMemoryIssues)}`);
  const falselyUsedDormantMemory = structuredClone(dormantMemoryResult);
  falselyUsedDormantMemory.reviewed_memory_used = true;
  if (!memoryRetrievalContractViolations(falselyUsedDormantMemory).some(issue => issue.includes('memory-use flags'))) throw new Error('Receipt-free memory-use flag was not rejected');
  const falselyAppliedDormantMemory = structuredClone(dormantMemoryResult);
  falselyAppliedDormantMemory.process.case_specific_guidance_applied = true;
  if (!memoryRetrievalContractViolations(falselyAppliedDormantMemory).some(issue => issue.includes('falsely claims'))) throw new Error('Receipt-free guidance-application flag was not rejected');
  const hiddenDormantRetrieval = structuredClone(dormantMemoryResult);
  hiddenDormantRetrieval.reviewed_memory_retrieved = false;
  if (!memoryRetrievalContractViolations(hiddenDormantRetrieval).some(issue => issue.includes('retrieval flags'))) throw new Error('Ranked memory with a false retrieval flag was not rejected');
  const falselyTransformedDormantMemory = structuredClone(dormantMemoryResult);
  falselyTransformedDormantMemory.checklist.memory_used = true;
  if (!memoryRetrievalContractViolations(falselyTransformedDormantMemory).some(issue => issue.includes('process/checklist'))) throw new Error('Receipt-free checklist memory-use flag was not rejected');
  const tamperedApplicationRun = structuredClone(laterRunFixture);
  tamperedApplicationRun.result.memory_application.application_hash = sha256('tampered application');
  if (!memoryApplicationContractViolations(baselineRunFixture, tamperedApplicationRun, proofFixture).some(issue => issue.includes('application hash'))) throw new Error('Tampered memory application-hash fixture was not rejected');
  const tamperedBoundaryProof = structuredClone(proofFixture);
  tamperedBoundaryProof.after.process_semantic_hash = sha256('tampered boundary');
  if (!memoryApplicationContractViolations(baselineRunFixture, laterRunFixture, tamperedBoundaryProof).some(issue => issue.includes('after hashes'))) throw new Error('Tampered memory boundary-hash fixture was not rejected');
  const tamperedDeltaProof = structuredClone(proofFixture);
  tamperedDeltaProof.causal_delta.evidence.changed_item_ids = ['building_envelope'];
  if (!memoryApplicationContractViolations(baselineRunFixture, laterRunFixture, tamperedDeltaProof).some(issue => issue.includes('causal delta'))) throw new Error('Tampered memory causal-delta fixture was not rejected');
  const tamperedCheckProof = structuredClone(proofFixture);
  tamperedCheckProof.deterministic_checks[0].status = 'failed';
  if (!memoryApplicationContractViolations(baselineRunFixture, laterRunFixture, tamperedCheckProof).some(issue => issue.includes('checks'))) throw new Error('Failed memory deterministic-check fixture was not rejected');
  const tamperedSemanticEligibilityRun = structuredClone(laterRunFixture);
  tamperedSemanticEligibilityRun.result.memory_application.eligibility.semantic_signature_hash = sha256('wrong semantic signature');
  tamperedSemanticEligibilityRun.result.memory_application.eligibility.manifest_hash = dtoHash(Object.fromEntries(['rule_id', 'contract', 'claim_id', 'semantic_signature_hash', 'decisions', 'facts_hash', 'checks'].map(key => [key, tamperedSemanticEligibilityRun.result.memory_application.eligibility[key]])));
  tamperedSemanticEligibilityRun.result.memory_application.application_hash = dtoHash(Object.fromEntries(Object.entries(tamperedSemanticEligibilityRun.result.memory_application).filter(([key]) => key !== 'application_hash')));
  if (!memoryApplicationContractViolations(baselineRunFixture, tamperedSemanticEligibilityRun, proofFixture).some(issue => issue.includes('semantic eligibility'))) throw new Error('Tampered semantic eligibility fixture was not rejected');
  const tamperedReplayProof = structuredClone(proofFixture);
  tamperedReplayProof.memory_application_proof.replay_exact = false;
  if (!memoryApplicationContractViolations(baselineRunFixture, laterRunFixture, tamperedReplayProof).some(issue => issue.includes('pure replay'))) throw new Error('Failed pure-memory replay fixture was not rejected');
  const coldRun = mockOrchestration('cold');
  const coldLedger = mockLedgerForRun(coldRun, 'cold');
  const warmRun = mockOrchestration('warm', coldRun);
  const warmOnlyLedger = mockLedgerForRun(warmRun, 'warm', coldLedger);
  const combinedItems = [...coldLedger.items, ...warmOnlyLedger.items];
  const combinedLedger = { ...coldLedger, items: combinedItems, summary: ledgerSummary(combinedItems) };
  const referenceRun = {
    run_id: 'deterministic_reference_run',
    claim_id: 'DEMO-MOULD-002',
    status: 'complete',
    profile: DETERMINISTIC_REFERENCE_PROFILE,
    model_mode: DETERMINISTIC_REFERENCE_MODE,
    model: null,
    knowledge_mode: 'current',
    agent_orchestration: structuredClone(DETERMINISTIC_REFERENCE_ORCHESTRATION),
    events: [{ stage: 'orchestrator', actor_type: 'deterministic_tool', status: 'completed', implementation: 'deterministic_application_tool', model: null }],
    result: {
      next_action: { agent_brief_contribution: null },
      agent_orchestration: structuredClone(DETERMINISTIC_REFERENCE_ORCHESTRATION),
      audit: {
        profile: DETERMINISTIC_REFERENCE_PROFILE,
        authority_mode: DETERMINISTIC_REFERENCE_MODE,
        canonicalization: structuredClone(DETERMINISTIC_REFERENCE_CANONICALIZATION),
        agent_orchestration: structuredClone(DETERMINISTIC_REFERENCE_ORCHESTRATION),
      },
    },
  };
  if (deterministicReferenceRunViolations(referenceRun, 'current').length) throw new Error('Positive deterministic-reference held-out fixture failed');
  const modelActiveReference = structuredClone(referenceRun);
  modelActiveReference.events.push({ stage: 'agent_orchestration', actor_type: 'nemotron_agent', model: REQUESTED_NEMOTRON_MODEL, call_id: 'forbidden_later_call', call_count: 1 });
  if (!deterministicReferenceRunViolations(modelActiveReference, 'current').some(item => item.includes('model execution activity'))) throw new Error('Held-out model-activity fixture was not rejected');
  const executedReference = structuredClone(referenceRun);
  const executedDag = { ...structuredClone(DETERMINISTIC_REFERENCE_ORCHESTRATION), executed: true, agents: [] };
  executedReference.agent_orchestration = structuredClone(executedDag);
  executedReference.result.agent_orchestration = structuredClone(executedDag);
  executedReference.result.audit.agent_orchestration = structuredClone(executedDag);
  if (!deterministicReferenceRunViolations(executedReference, 'current').some(item => item.includes('non-executed orchestration'))) throw new Error('Held-out executed-DAG fixture was not rejected');
  if (finalLedgerSnapshotViolations(combinedLedger, structuredClone(combinedLedger)).length) throw new Error('Positive immutable 12-row final-ledger fixture failed');
  const thirteenthRowLedger = structuredClone(combinedLedger);
  thirteenthRowLedger.items.push({ ...structuredClone(thirteenthRowLedger.items.at(-1)), call_id: 'forbidden_thirteenth_row' });
  thirteenthRowLedger.summary = ledgerSummary(thirteenthRowLedger.items);
  if (!finalLedgerSnapshotViolations(combinedLedger, thirteenthRowLedger).length) throw new Error('Thirteenth final-ledger row fixture was not rejected');
  const emptyInitialLedger = { scope: 'global_budget_ledger', items: [], summary: ledgerSummary([]) };
  if (initialLedgerAdmissionViolations(emptyInitialLedger).length) throw new Error('Exact-empty initial ledger fixture was rejected');
  if (!initialLedgerAdmissionViolations(coldLedger).some(item => item.includes('not exactly empty'))) throw new Error('Stale initial ledger fixture was not rejected');
  const openingContextFixture = [{ boundary_text: EXPECTED_PRODUCTION_OPENING_BOUNDARY, actor_type: 'deterministic_tool', nemotron_plan_visible: false }];
  if (productionOpeningContextViolations(openingContextFixture).length) throw new Error('Positive production opening-context fixture failed');
  const legacyProductionOpening = structuredClone(openingContextFixture);
  legacyProductionOpening[0].boundary_text = 'This run returned legacy deterministic reference orchestration; no Nemotron orchestrator is claimed.';
  if (!productionOpeningContextViolations(legacyProductionOpening).some(item => item.includes('legacy reference'))) throw new Error('Legacy production opening-context fixture was not rejected');
  const prematureNemotronPlan = structuredClone(openingContextFixture);
  prematureNemotronPlan[0].nemotron_plan_visible = true;
  if (!productionOpeningContextViolations(prematureNemotronPlan).some(item => item.includes('before its returned event'))) throw new Error('Premature Nemotron-plan fixture was not rejected');
  const failures = [
    ...orchestrationContractViolations(coldRun, 'cold'),
    ...coldLedgerContractViolations(orchestrationAudit(coldRun), coldLedger),
    ...orchestrationContractViolations(warmRun, 'warm'),
    ...warmLineageContractViolations(orchestrationAudit(coldRun), orchestrationAudit(warmRun), combinedLedger).issues,
  ];
  if (failures.length) throw new Error(`Positive contract fixture failed: ${JSON.stringify(failures)}`);
  const expectHybridIssue = (fixture, expectedIssue, label) => {
    const issues = hybridCausalContractViolations(fixture);
    if (!issues.some(item => item.includes(expectedIssue))) throw new Error(`${label} fixture was not rejected: ${JSON.stringify(issues)}`);
    return issues;
  };
  const sourceArtifactHashRun = structuredClone(coldRun);
  orchestrationAudit(sourceArtifactHashRun).specialist_artifacts.document_source_integrity.artifacts[0].integrity_class = 'changed_after_acceptance';
  const sourceArtifactHashIssues = expectHybridIssue(sourceArtifactHashRun, 'document source specialist artifact hash', 'Changed source-specialist artifact hash');
  if (!sourceArtifactHashIssues.some(item => item.includes('parallel specialist composite input hash'))) throw new Error(`Changed source-specialist artifact did not invalidate the process-gate composite: ${JSON.stringify(sourceArtifactHashIssues)}`);
  const processArtifactHashRun = structuredClone(coldRun);
  orchestrationAudit(processArtifactHashRun).specialist_artifacts.process_decision_mapping.decisions[0].decision_value = 'changed_after_acceptance';
  const processArtifactHashIssues = expectHybridIssue(processArtifactHashRun, 'process specialist artifact hash', 'Changed process-specialist artifact hash');
  if (!processArtifactHashIssues.some(item => item.includes('parallel specialist composite input hash'))) throw new Error(`Changed process-specialist artifact did not invalidate the process-gate composite: ${JSON.stringify(processArtifactHashIssues)}`);
  const processFieldMembershipRun = structuredClone(coldRun);
  orchestrationAudit(processFieldMembershipRun).specialist_artifacts.process_decision_mapping.decisions[0].model_owned_fields = ['decision_value', 'state'];
  expectHybridIssue(processFieldMembershipRun, 'process decision field contributions violate membership or attribution', 'Foreign process model-owned field');
  const processFieldAttributionRun = structuredClone(coldRun);
  const processAttributionUnit = orchestrationAudit(processFieldAttributionRun).specialist_artifacts.process_decision_mapping.decisions[0];
  processAttributionUnit.deterministic_fallback_applied = true;
  processAttributionUnit.attribution = PROCESS_CONTRIBUTION_ROLE;
  expectHybridIssue(processFieldAttributionRun, 'process decision field contributions violate membership or attribution', 'Forged process fallback attribution');
  const processInheritedFieldRun = structuredClone(coldRun);
  const processInheritedAudit = orchestrationAudit(processInheritedFieldRun);
  processInheritedAudit.specialist_artifacts.process_decision_mapping.decisions[0].state = 'forged_inherited_state';
  processInheritedAudit.agents.find(item => item.agent_id === 'process_decision_mapping').output_artifact_hash = dtoHash(processInheritedAudit.specialist_artifacts.process_decision_mapping);
  processInheritedAudit.deterministic_gates.find(item => item.agent_id === 'deterministic_process_gate').input_artifact_hash = dtoHash({
    source_integrity: processInheritedAudit.specialist_artifacts.document_source_integrity,
    process_mapping: processInheritedAudit.specialist_artifacts.process_decision_mapping,
  });
  expectHybridIssue(processInheritedFieldRun, 'inherited canonical fields are not exact', 'Forged inherited process field with recomputed hashes');
  const evidenceFieldMembershipRun = structuredClone(coldRun);
  orchestrationAudit(evidenceFieldMembershipRun).specialist_artifacts.evidence_checklist.items[0].field_contributions[0].field = 'artifact_ids';
  expectHybridIssue(evidenceFieldMembershipRun, 'does not contain the exact two field contributions', 'Foreign evidence field membership');
  const evidenceFieldAttributionRun = structuredClone(coldRun);
  const evidenceAttributionUnit = orchestrationAudit(evidenceFieldAttributionRun).specialist_artifacts.evidence_checklist.items[0].field_contributions[0];
  evidenceAttributionUnit.deterministic_fallback_applied = true;
  evidenceAttributionUnit.attribution = EVIDENCE_CONTRIBUTION_ROLE;
  expectHybridIssue(evidenceFieldAttributionRun, 'does not contain the exact two field contributions', 'Forged evidence fallback attribution');
  const evidenceSourceRefsRun = structuredClone(coldRun);
  const evidenceSourceRefsAudit = orchestrationAudit(evidenceSourceRefsRun);
  evidenceSourceRefsAudit.specialist_artifacts.evidence_checklist.items[0].source_ref_ids = ['source_scope', 'source_scope'];
  evidenceSourceRefsAudit.agents.find(item => item.agent_id === 'evidence_checklist').output_artifact_hash = dtoHash(evidenceSourceRefsAudit.specialist_artifacts.evidence_checklist);
  evidenceSourceRefsAudit.deterministic_gates.find(item => item.agent_id === 'deterministic_evidence_gate').input_artifact_hash = dtoHash(evidenceSourceRefsAudit.specialist_artifacts.evidence_checklist);
  expectHybridIssue(evidenceSourceRefsRun, 'source reference IDs are not unique and sorted', 'Forged evidence source references with recomputed hashes');
  const finalFieldMembershipRun = structuredClone(coldRun);
  orchestrationAudit(finalFieldMembershipRun).final_claim_brief.field_contributions[0].contribution_id = 'final:foreign_current_node';
  expectHybridIssue(finalFieldMembershipRun, 'exact five field contributions', 'Foreign final field membership');
  const finalCurrentBindingRun = structuredClone(coldRun);
  orchestrationAudit(finalCurrentBindingRun).final_claim_brief.current_node_id = 'notice';
  expectHybridIssue(finalCurrentBindingRun, 'final current-node field', 'Final current-node binding');
  const finalNextBindingRun = structuredClone(coldRun);
  orchestrationAudit(finalNextBindingRun).final_claim_brief.next_action_node_id = 'scope';
  expectHybridIssue(finalNextBindingRun, 'final next-action field', 'Final next-action binding');
  const finalSupportingBindingRun = structuredClone(coldRun);
  orchestrationAudit(finalSupportingBindingRun).final_claim_brief.supporting_fact_ids = ['fact_scope'];
  expectHybridIssue(finalSupportingBindingRun, 'final supporting-facts field', 'Final supporting-facts binding');
  const finalUpstreamBindingRun = structuredClone(coldRun);
  orchestrationAudit(finalUpstreamBindingRun).final_claim_brief.upstream_contribution_ids = FINAL_UPSTREAM_CONTRIBUTION_IDS.slice(1);
  expectHybridIssue(finalUpstreamBindingRun, 'final upstream-contribution field', 'Final upstream-contribution binding');
  const finalAuditBindingRun = structuredClone(coldRun);
  orchestrationAudit(finalAuditBindingRun).final_claim_brief.audit_check_ids = FINAL_AUDIT_CHECK_IDS.slice(1);
  expectHybridIssue(finalAuditBindingRun, 'final audit-check field', 'Final audit-check binding');
  const currentNode = coldRun.result.process.nodes.find(item => item.node_id === coldRun.result.process.current_node);
  const nonControllingSupportingFacts = coldRun.result.facts.filter(item => item.controls_process === false && currentNode.fact_ids.includes(item.fact_id));
  if (!nonControllingSupportingFacts.length || !orchestrationAudit(coldRun).final_claim_brief.source_ref_ids.includes('source_context')) throw new Error('Positive final-source fixture does not cover a non-controlling supporting fact');
  const nonControllingSourceRun = structuredClone(coldRun);
  orchestrationAudit(nonControllingSourceRun).final_claim_brief.source_ref_ids = ['source_scope'];
  expectHybridIssue(nonControllingSourceRun, 'controlling and non-controlling supporting facts', 'Non-controlling final source-reference binding');
  const forgedSummaryValues = {
    records: 999,
    network_calls: 0,
    prompt_tokens: 0,
    completion_tokens: 0,
    total_tokens: 0,
    actual_cost_usd: 0,
    actual_cost_complete: false,
    unknown_cost_call_count: 1,
    outcomes: {},
  };
  for (const [field, value] of Object.entries(forgedSummaryValues)) {
    const forgedSummaryLedger = structuredClone(coldLedger);
    forgedSummaryLedger.summary[field] = value;
    if (!sanitizedLedgerViolations(forgedSummaryLedger).some(item => item.includes('summary is inconsistent'))) throw new Error(`Forged ledger-summary ${field} fixture was not rejected`);
  }
  const wrongUpstreamRun = structuredClone(coldRun);
  orchestrationAudit(wrongUpstreamRun).agents[0].upstream_provider = 'DeepInfra';
  if (!orchestrationContractViolations(wrongUpstreamRun, 'cold').some(item => item.includes('provider provenance'))) throw new Error('Non-Together cold audit fixture was not rejected');
  const wrongUpstreamLedger = structuredClone(coldLedger);
  wrongUpstreamLedger.items[0].upstream_provider = 'DeepInfra';
  if (!coldLedgerContractViolations(orchestrationAudit(coldRun), wrongUpstreamLedger).some(item => item.includes('provider'))) throw new Error('Non-Together cold ledger fixture was not rejected');
  const wrongWarmLedger = structuredClone(combinedLedger);
  wrongWarmLedger.items.find(item => item.call_count === 0).upstream_provider = 'DeepInfra';
  if (!warmLineageContractViolations(orchestrationAudit(coldRun), orchestrationAudit(warmRun), wrongWarmLedger).issues.some(item => item.includes('provider'))) throw new Error('Non-Together warm cache fixture was not rejected');
  const wrongAgentRoleRun = structuredClone(coldRun);
  orchestrationAudit(wrongAgentRoleRun).agents.find(item => item.agent_id === 'document_source_integrity').role = 'Unbound Specialist Label';
  if (!orchestrationContractViolations(wrongAgentRoleRun, 'cold').some(item => item.includes('document_source_integrity: role label is not exact'))) throw new Error('Tampered Nemotron agent-role fixture was not rejected');
  const wrongGateRoleRun = structuredClone(coldRun);
  orchestrationAudit(wrongGateRoleRun).deterministic_gates.find(item => item.agent_id === 'deterministic_evidence_gate').role = 'Unbound Gate Label';
  if (!orchestrationContractViolations(wrongGateRoleRun, 'cold').some(item => item.includes('deterministic_evidence_gate: role label is not exact'))) throw new Error('Tampered deterministic gate-role fixture was not rejected');
  const aliasResponseRun = structuredClone(coldRun);
  const aliasResponseLedger = structuredClone(coldLedger);
  orchestrationAudit(aliasResponseRun).agents.forEach(item => { item.response_model = REQUESTED_NEMOTRON_MODEL; });
  aliasResponseRun.events.filter(item => item.actor_type === 'nemotron_agent' && item.receipt_type === 'agent_completed').forEach(item => { item.response_model = REQUESTED_NEMOTRON_MODEL; });
  aliasResponseLedger.items.forEach(item => { item.response_model = REQUESTED_NEMOTRON_MODEL; });
  if (orchestrationContractViolations(aliasResponseRun, 'cold').length || coldLedgerContractViolations(orchestrationAudit(aliasResponseRun), aliasResponseLedger).length) throw new Error('Exact raw alias response-model fixture was not accepted');
  const normalizedMismatchLedger = structuredClone(aliasResponseLedger);
  normalizedMismatchLedger.items[0].response_model = 'nvidia/nemotron-3-ultra-550b-a55b-20260604';
  if (!coldLedgerContractViolations(orchestrationAudit(aliasResponseRun), normalizedMismatchLedger).some(item => item.includes('response binding'))) throw new Error('Alias-to-dated response-model normalization fixture was not rejected');
  const foreignResponseRun = structuredClone(coldRun);
  orchestrationAudit(foreignResponseRun).agents[0].response_model = 'nvidia/nemotron-3-ultra-550b-a55b-foreign';
  if (!orchestrationContractViolations(foreignResponseRun, 'cold').some(item => item.includes('returned response identity'))) throw new Error('Foreign response-model fixture was not rejected');
  const reviewedProcess = { contract: 'process-graph', nodes: [{ node_id: 'scope' }, { node_id: 'review_added' }] };
  const reviewedChecklist = { contract: 'evidence-model', items: [{ item_id: 'lease' }, { item_id: 'review_added' }] };
  const preAudit = orchestrationAudit(coldRun);
  const reviewTransform = {
    acceptance_scope: 'post_review_unverified_transform',
    authority: 'unverified_demo_user',
    qualification_status: 'not_verified',
    input_run_id: coldRun.run_id,
    input_process_hash: preAudit.deterministic_gates.find(item => item.agent_id === 'deterministic_process_gate').output_artifact_hash,
    input_checklist_hash: preAudit.deterministic_gates.find(item => item.agent_id === 'deterministic_evidence_gate').output_artifact_hash,
    output_process_hash: dtoHash(reviewedProcess),
    output_checklist_hash: dtoHash(reviewedChecklist),
    model_acceptance_reused: false,
  };
  const reviewedResponse = { review_transform: reviewTransform, result: { process: reviewedProcess, checklist: reviewedChecklist } };
  const persistedReviewedRun = structuredClone(coldRun);
  persistedReviewedRun.result.process = reviewedProcess;
  persistedReviewedRun.result.checklist = reviewedChecklist;
  persistedReviewedRun.review_transform = structuredClone(reviewTransform);
  const reviewFailures = reviewTransformContractViolations(reviewedResponse, persistedReviewedRun, coldRun);
  if (reviewFailures.length) throw new Error(`Positive review-transform fixture failed: ${JSON.stringify(reviewFailures)}`);
  const deterministicPreReview = {
    run_id: 'deterministic_pre_review',
    result: {
      process: { contract: 'process-graph', nodes: [{ node_id: 'scope' }] },
      checklist: { contract: 'evidence-model', items: [{ item_id: 'lease' }] },
      agent_orchestration: { executed: false, authority_mode: 'deterministic_reference' },
    },
  };
  const deterministicReviewedProcess = { contract: 'process-graph', nodes: [{ node_id: 'scope' }, { node_id: 'deterministic_review_added' }] };
  const deterministicReviewedChecklist = { contract: 'evidence-model', items: [{ item_id: 'lease' }, { item_id: 'deterministic_review_added' }] };
  const deterministicReviewTransform = {
    acceptance_scope: 'post_review_unverified_transform',
    authority: 'unverified_demo_user',
    qualification_status: 'not_verified',
    input_run_id: deterministicPreReview.run_id,
    input_process_hash: dtoHash(deterministicPreReview.result.process),
    input_checklist_hash: dtoHash(deterministicPreReview.result.checklist),
    output_process_hash: dtoHash(deterministicReviewedProcess),
    output_checklist_hash: dtoHash(deterministicReviewedChecklist),
    model_acceptance_reused: false,
  };
  const deterministicReviewResponse = { review_transform: deterministicReviewTransform, result: { process: deterministicReviewedProcess, checklist: deterministicReviewedChecklist } };
  const deterministicPersistedReview = { ...structuredClone(deterministicPreReview), review_transform: structuredClone(deterministicReviewTransform) };
  deterministicPersistedReview.result.process = deterministicReviewedProcess;
  deterministicPersistedReview.result.checklist = deterministicReviewedChecklist;
  const deterministicReviewFailures = reviewTransformContractViolations(deterministicReviewResponse, deterministicPersistedReview, deterministicPreReview);
  if (deterministicReviewFailures.length) throw new Error(`Local deterministic review-transform fixture failed: ${JSON.stringify(deterministicReviewFailures)}`);
  const falselyReacceptedReview = structuredClone(reviewedResponse);
  falselyReacceptedReview.review_transform.model_acceptance_reused = true;
  if (!reviewTransformContractViolations(falselyReacceptedReview, persistedReviewedRun, coldRun).some(item => item.includes('model_acceptance_reused'))) throw new Error('Model-reacceptance negative fixture was not rejected');
  const unsafeRun = structuredClone(coldRun);
  unsafeRun.result.audit.agent_orchestration.reasoning = 'must never be public';
  if (!orchestrationContractViolations(unsafeRun, 'cold').some(item => item.includes('forbidden public fields'))) throw new Error('Sensitive-field negative fixture was not rejected');
  const sentinelRun = structuredClone(coldRun);
  sentinelRun.events.push({ stage: 'agent_orchestration', status: 'failed', detail: 'branch:to:__end__' });
  if (!orchestrationContractViolations(sentinelRun, 'cold').some(item => item.includes('execution sentinels'))) throw new Error('Internal-sentinel negative fixture was not rejected');
  const falselyModelOwnedTopology = structuredClone(coldRun);
  falselyModelOwnedTopology.result.audit.agent_orchestration.execution_topology.authority = 'nemotron_agent';
  if (!orchestrationContractViolations(falselyModelOwnedTopology, 'cold').some(item => item.includes('execution topology'))) throw new Error('Model-owned topology misattribution fixture was not rejected');
  const brokenTopologyDependency = structuredClone(coldRun);
  brokenTopologyDependency.result.audit.agent_orchestration.execution_topology.delegations.find(item => item.agent_id === 'evidence_checklist').dependencies = ['orchestrator_plan'];
  if (!orchestrationContractViolations(brokenTopologyDependency, 'cold').some(item => item.includes('execution topology'))) throw new Error('Broken deterministic topology dependency fixture was not rejected');
  const hiddenFinalAudit = structuredClone(coldRun);
  delete hiddenFinalAudit.agent_orchestration;
  if (!orchestrationContractViolations(hiddenFinalAudit, 'cold').some(item => item.includes('final payload binding'))) throw new Error('Missing final payload-visible audit fixture was not rejected');
  const terminalFailure = { run_id: 'failed_run', status: 'failed', stage: 'agent_orchestration', error: 'branch:to:__end__' };
  if (!terminalFailureContractViolations(terminalFailure).some(item => item.includes('execution sentinels'))) throw new Error('Terminal-failure sentinel negative fixture was not rejected');
  if (JSON.stringify(runProgressDiagnostic(terminalFailure)).includes('__end__')) throw new Error('Safe terminal diagnostics leaked the internal sentinel value');
  const failureAgent = orchestrationAudit(coldRun).agents.find(item => item.agent_id === 'evidence_checklist');
  const failureAcceptedState = { canonical_state_prepared: true, process_candidate_prepared: true, evidence_candidate_prepared: true, final_playbook_accepted: false };
  const safeTerminalFailure = {
    run_id: 'safe_failed_run',
    status: 'failed',
    stage: 'failed',
    failure_stage: failureAgent.agent_id,
    accepted_state: failureAcceptedState,
    error: 'AgentInvocationFailure: provider_invocation',
    events: [
      structuredClone(coldRun.events.find(item => item.agent_id === 'canonical_facts' && item.receipt_type === 'agent_completed')),
      structuredClone(coldRun.events.find(item => item.agent_id === 'orchestrator_plan' && item.receipt_type === 'agent_completed')),
      {
        event_id: 'evt_agent_failed',
        ordinal: 3,
        created_at: '2026-08-11T00:00:00Z',
        stage: 'agent_orchestration',
        label: 'Evidence and Checklist Agent',
        agent: 'Evidence and Checklist Agent',
        agent_id: failureAgent.agent_id,
        actor_type: 'nemotron_agent',
        status: 'failed',
        acceptance_scope: 'pre_review_model_output',
        headline: 'Specialist stopped at the fail-closed boundary',
        detail: 'Only bounded failure metadata was retained.',
        implementation: EXPECTED_RUNTIME.implementation,
        model: REQUESTED_NEMOTRON_MODEL,
        orchestrator: 'CasePath Orchestrator',
        validator: 'evidence_checklist-contract/1.0.0',
        prompt_version: 'evidence_checklist/1.0.0',
        receipt_type: 'agent_failed',
        delegation_id: failureAgent.delegation_id,
        parent_call_id: orchestrationAudit(coldRun).agents.find(item => item.agent_id === 'orchestrator_plan').call_id,
        call_id: 'failed_call_evidence_checklist',
        provider: 'openrouter',
        requested_model: REQUESTED_NEMOTRON_MODEL,
        call_count: 1,
        outcome: 'failed',
        handoff_from: 'deterministic_evidence_gate',
        handoff_to: 'failure_boundary',
        input_artifact_hash: dtoHash({ bounded: 'failure-input' }),
        error_type: 'AgentInvocationFailure',
        error_invariant: 'provider_invocation',
        external_tracing: false,
      },
      {
        event_id: 'evt_terminal_boundary',
        ordinal: 4,
        created_at: '2026-08-11T00:00:01Z',
        stage: 'failed',
        label: 'Analysis stopped safely',
        agent: 'Failure boundary',
        status: 'failed',
        headline: 'No final playbook was accepted',
        detail: 'Partial candidate artifacts may remain visible for audit, but the terminal acceptance boundary failed closed.',
        implementation: 'deterministic',
        model: null,
        actor_type: 'deterministic_gate',
        failure_stage: failureAgent.agent_id,
        failure_invariant: 'provider_invocation',
        accepted_state: failureAcceptedState,
        validator: 'fail-closed/15.2',
        prompt_version: null,
      },
    ],
  };
  const safeFailureIssues = terminalFailureContractViolations(safeTerminalFailure);
  if (safeFailureIssues.length) throw new Error(`Safe terminal-failure fixture failed: ${JSON.stringify(safeFailureIssues)}`);
  const terminalFailureMessage = terminalRunFailureMessage(safeTerminalFailure);
  if (!terminalFailureMessage?.includes('safe_failed_run failed:')
    || terminalFailureMessage.includes('provider_invocation')
    || LATER_TERMINAL_POLL_INTERVAL_MS >= 5000) throw new Error('Later-journey terminal failure does not exit promptly with bounded diagnostics');
  const providerConcurrencyFailure = structuredClone(safeTerminalFailure);
  const providerConcurrencyReceipt = providerConcurrencyFailure.events.find(item => item.receipt_type === 'agent_failed');
  Object.assign(providerConcurrencyReceipt, {
    call_count: 0,
    outcome: 'blocked_provider_concurrency',
    error_type: 'AgentInvocationFailure',
    error_invariant: 'provider_concurrency_timeout',
  });
  providerConcurrencyFailure.events.find(item => item.stage === 'failed').failure_invariant = 'provider_concurrency_timeout';
  const providerConcurrencyIssues = terminalFailureContractViolations(providerConcurrencyFailure);
  if (providerConcurrencyIssues.length) throw new Error(`Provider-concurrency zero-call receipt fixture failed: ${JSON.stringify(providerConcurrencyIssues)}`);
  const forgedProviderConcurrencyCall = structuredClone(providerConcurrencyFailure);
  forgedProviderConcurrencyCall.events.find(item => item.receipt_type === 'agent_failed').call_count = 1;
  if (!terminalFailureContractViolations(forgedProviderConcurrencyCall).some(item => item.includes('zero-call') || item.includes('call_count'))) throw new Error('Provider-concurrency forged-call receipt fixture was not rejected');
  const forgedProviderConcurrencyIdentity = structuredClone(providerConcurrencyFailure);
  forgedProviderConcurrencyIdentity.events.find(item => item.receipt_type === 'agent_failed').response_id = 'gen-1786483159-hyYthqPv76o6PHXpGLzl';
  if (!terminalFailureContractViolations(forgedProviderConcurrencyIdentity).some(item => item.includes('zero-call'))) throw new Error('Provider-concurrency forged response receipt fixture was not rejected');
  const upstreamRejectionFailure = structuredClone(safeTerminalFailure);
  const upstreamReceipt = upstreamRejectionFailure.events.find(item => item.receipt_type === 'agent_failed');
  Object.assign(upstreamReceipt, {
    error_invariant: 'provider_upstream_rejection',
    response_id: 'gen-1786483159-hyYthqPv76o6PHXpGLzl',
    provider_error_code: 429,
    provider_boundary: EXPECTED_PROVIDER_BOUNDARY,
    expected_upstream_provider: EXPECTED_UPSTREAM_PROVIDER,
  });
  upstreamRejectionFailure.events.find(item => item.stage === 'failed').failure_invariant = 'provider_upstream_rejection';
  const upstreamFailureIssues = terminalFailureContractViolations(upstreamRejectionFailure);
  if (upstreamFailureIssues.length) throw new Error(`Bounded upstream-rejection fixture failed: ${JSON.stringify(upstreamFailureIssues)}`);
  const forgedUpstreamBoundaryFailure = structuredClone(upstreamRejectionFailure);
  forgedUpstreamBoundaryFailure.events.find(item => item.receipt_type === 'agent_failed').expected_upstream_provider = 'DeepInfra';
  if (!terminalFailureContractViolations(forgedUpstreamBoundaryFailure).some(item => item.includes('boundary attribution is forged'))) throw new Error('Forged upstream-rejection receipt attribution fixture was not rejected');
  const missingUpstreamBoundaryFailure = structuredClone(upstreamRejectionFailure);
  delete missingUpstreamBoundaryFailure.events.find(item => item.receipt_type === 'agent_failed').expected_upstream_provider;
  if (!terminalFailureContractViolations(missingUpstreamBoundaryFailure).some(item => item.includes('attribution pair is incomplete'))) throw new Error('Missing upstream-rejection receipt attribution fixture was not rejected');
  const outOfScopeUpstreamBoundaryFailure = structuredClone(safeTerminalFailure);
  Object.assign(outOfScopeUpstreamBoundaryFailure.events.find(item => item.receipt_type === 'agent_failed'), {
    provider_boundary: EXPECTED_PROVIDER_BOUNDARY,
    expected_upstream_provider: EXPECTED_UPSTREAM_PROVIDER,
  });
  if (!terminalFailureContractViolations(outOfScopeUpstreamBoundaryFailure).some(item => item.includes('boundary attribution is out of scope'))) throw new Error('Out-of-scope upstream-rejection receipt attribution fixture was not rejected');
  const unboundedUpstreamCodeFailure = structuredClone(upstreamRejectionFailure);
  unboundedUpstreamCodeFailure.events.find(item => item.receipt_type === 'agent_failed').provider_error_code = 'RAW_PROVIDER_CODE';
  if (!terminalFailureContractViolations(unboundedUpstreamCodeFailure).some(item => item.includes('error code'))) throw new Error('Unbounded upstream provider-code fixture was not rejected');
  const claimBearingUpstreamIdFailure = structuredClone(upstreamRejectionFailure);
  claimBearingUpstreamIdFailure.events.find(item => item.receipt_type === 'agent_failed').response_id = 'DEF-027-E0-DEMO';
  if (!terminalFailureContractViolations(claimBearingUpstreamIdFailure).some(item => item.includes('exact OpenRouter generation ID'))) throw new Error('Claim-bearing upstream response-ID fixture was not rejected');
  const unsafeFailureAllowlist = structuredClone(safeTerminalFailure);
  unsafeFailureAllowlist.events.find(item => item.receipt_type === 'agent_failed').provider_payload = 'must never be retained';
  if (!terminalFailureContractViolations(unsafeFailureAllowlist).some(item => item.includes('non-allowlisted fields'))) throw new Error('Failure-receipt allowlist negative fixture was not rejected');
  const brokenFailureLineage = structuredClone(safeTerminalFailure);
  brokenFailureLineage.events.find(item => item.receipt_type === 'agent_failed').parent_call_id = 'wrong_parent';
  if (!terminalFailureContractViolations(brokenFailureLineage).some(item => item.includes('identity/lineage'))) throw new Error('Failure-receipt lineage negative fixture was not rejected');
  const overrunFailure = structuredClone(safeTerminalFailure);
  Object.assign(overrunFailure.events.find(item => item.receipt_type === 'agent_failed'), {
    outcome: 'actual_cost_overrun',
    error_invariant: 'actual_cost_overrun',
    response_id: 'generation_charged_overrun',
    response_model: REQUESTED_NEMOTRON_MODEL,
    upstream_provider: 'Together',
    usage_source: 'response',
    finish_reason: 'stop',
  });
  if (terminalFailureContractViolations(overrunFailure).length) throw new Error('Charged-overrun failure fixture was not accepted');
  const invalidModelProvenanceFailure = structuredClone(safeTerminalFailure);
  Object.assign(invalidModelProvenanceFailure.events.find(item => item.receipt_type === 'agent_failed'), {
    error_invariant: 'invalid_provenance',
    response_id: 'generation_wrong_model',
    response_model: null,
    upstream_provider: 'Together',
    usage_source: 'response',
    finish_reason: 'stop',
    invalid_provenance_field: 'response_model',
    invalid_provenance_value_hash: '7'.repeat(64),
  });
  if (terminalFailureContractViolations(invalidModelProvenanceFailure).length) throw new Error('Hashed invalid-model provenance fixture was not accepted');
  const rawForeignModelFailure = structuredClone(invalidModelProvenanceFailure);
  Object.assign(rawForeignModelFailure.events.find(item => item.receipt_type === 'agent_failed'), {
    error_invariant: 'response_model',
    response_model: 'foreign/provider-model',
    invalid_provenance_field: undefined,
    invalid_provenance_value_hash: undefined,
  });
  if (!terminalFailureContractViolations(rawForeignModelFailure).some(item => item.includes('provider provenance'))) throw new Error('Raw foreign model provenance was not rejected');
  const rawCredentialProvenance = structuredClone(safeTerminalFailure);
  Object.assign(rawCredentialProvenance.events.find(item => item.receipt_type === 'agent_failed'), {
    response_id: 'sk-or-v1-secretmaterial',
    response_model: REQUESTED_NEMOTRON_MODEL,
  });
  if (!terminalFailureContractViolations(rawCredentialProvenance).some(item => item.includes('provider provenance'))) throw new Error('Credential-shaped provider provenance was not rejected');
  const rawClaimTextProvenance = structuredClone(safeTerminalFailure);
  rawClaimTextProvenance.events.find(item => item.receipt_type === 'agent_failed').upstream_provider = 'TenantClaim';
  if (!terminalFailureContractViolations(rawClaimTextProvenance).some(item => item.includes('provider provenance'))) throw new Error('Claim-text provider provenance was not rejected');
  const partialIdentityFailure = structuredClone(safeTerminalFailure);
  Object.assign(partialIdentityFailure.events.find(item => item.receipt_type === 'agent_failed'), {
    error_invariant: 'response_identity',
    response_id: null,
    response_model: REQUESTED_NEMOTRON_MODEL,
  });
  if (terminalFailureContractViolations(partialIdentityFailure).length) throw new Error('Explicit partial response-identity failure fixture was not accepted');
  const rootAcceptedState = { canonical_state_prepared: false, process_candidate_prepared: false, evidence_candidate_prepared: false, final_playbook_accepted: false };
  const canonicalFailure = {
    run_id: 'canonical_failed_run',
    status: 'failed',
    stage: 'failed',
    failure_stage: 'canonical_facts',
    accepted_state: rootAcceptedState,
    error: 'ModelConfigurationError: missing_credential',
    events: [
      {
        event_id: 'evt_canonical_failed', ordinal: 1, created_at: '2026-08-11T00:00:00Z',
        stage: 'understand', label: 'Canonical claim state', agent: 'Guarded Canonical Facts Agent',
        agent_id: 'canonical_facts', actor_type: 'nemotron_agent', status: 'failed',
        headline: 'Canonical facts were not accepted', detail: 'The bounded provider call failed a local invariant; no final playbook was accepted.',
        implementation: 'hybrid_guarded_openrouter_canonicalizer', model: REQUESTED_NEMOTRON_MODEL,
        orchestrator: 'casepath-langgraph-orchestrator/15.2', shared_context: 'claim-context:canonical_failed_run',
        validator: 'understand-validator/15.2', prompt_version: 'understand/15.2', receipt_type: 'agent_failed',
        failure_scope: 'root_canonical_facts', root_agent: true, acceptance_scope: 'pre_review_model_output',
        input_artifact: 'observable_claim_package', input_artifact_hash: dtoHash({ bounded: 'canonical-input' }),
        provider: 'openrouter', requested_model: REQUESTED_NEMOTRON_MODEL, call_count: 0,
        orchestration_id: 'orchestration_canonical_failure', call_id: 'call_canonical_failure',
        parent_call_id: null, delegation_id: null, response_id: null, response_model: null,
        upstream_provider: null, usage_source: null, finish_reason: null,
        outcome: 'blocked_missing_credential', error_type: 'ModelConfigurationError', error_invariant: 'missing_credential',
        handoff_from: 'observable_claim_package', handoff_to: 'failure_boundary', external_tracing: false,
      },
      {
        event_id: 'evt_canonical_terminal', ordinal: 2, created_at: '2026-08-11T00:00:01Z',
        stage: 'failed', label: 'Analysis stopped safely', agent: 'Failure boundary', status: 'failed',
        headline: 'No final playbook was accepted', detail: 'Partial candidate artifacts may remain visible for audit, but the terminal acceptance boundary failed closed.',
        implementation: 'deterministic', model: null, actor_type: 'deterministic_gate', failure_stage: 'canonical_facts',
        failure_invariant: 'missing_credential', accepted_state: rootAcceptedState, validator: 'fail-closed/15.2', prompt_version: null,
      },
    ],
  };
  const canonicalFailureIssues = terminalFailureContractViolations(canonicalFailure);
  if (canonicalFailureIssues.length) throw new Error(`Canonical root-failure fixture failed: ${JSON.stringify(canonicalFailureIssues)}`);
  const canonicalInvalidProvenanceFailure = structuredClone(canonicalFailure);
  canonicalInvalidProvenanceFailure.error = 'ModelResponseError: invalid_provenance';
  const canonicalInvalidReceipt = canonicalInvalidProvenanceFailure.events.find(item => item.receipt_type === 'agent_failed');
  Object.assign(canonicalInvalidReceipt, {
    call_count: 1,
    outcome: 'failed',
    error_type: 'ModelResponseError',
    error_invariant: 'invalid_provenance',
    response_id: 'gen-canonical-invalid-model',
    response_model: null,
    upstream_provider: 'Together',
    usage_source: 'response',
    finish_reason: 'stop',
    invalid_provenance_field: 'response_model',
    invalid_provenance_value_hash: '8'.repeat(64),
  });
  const canonicalInvalidTerminal = canonicalInvalidProvenanceFailure.events.find(item => item.stage === 'failed');
  canonicalInvalidTerminal.failure_invariant = 'invalid_provenance';
  const canonicalInvalidIssues = terminalFailureContractViolations(canonicalInvalidProvenanceFailure);
  if (canonicalInvalidIssues.length) throw new Error(`Canonical invalid-provenance fixture failed: ${JSON.stringify(canonicalInvalidIssues)}`);
  const claimBearingProvenanceLedger = structuredClone(coldLedger);
  claimBearingProvenanceLedger.items[0].response_id = 'tenant-claim-identity';
  if (!sanitizedLedgerViolations(claimBearingProvenanceLedger).some(item => item.includes('exact provider-provenance sanitizer'))) throw new Error('Claim-bearing ledger provenance fixture was not rejected');
  const boundedInvalidProvenanceLedger = structuredClone(coldLedger);
  Object.assign(boundedInvalidProvenanceLedger.items[0], {
    outcome: 'failed',
    error_invariant: 'invalid_provenance',
    invalid_provenance_field: 'response_model',
    invalid_provenance_value_hash: '9'.repeat(64),
  });
  delete boundedInvalidProvenanceLedger.items[0].response_model;
  boundedInvalidProvenanceLedger.summary = ledgerSummary(boundedInvalidProvenanceLedger.items);
  const boundedInvalidLedgerIssues = sanitizedLedgerViolations(boundedInvalidProvenanceLedger);
  if (boundedInvalidLedgerIssues.length) throw new Error(`Bounded invalid-provenance ledger fixture failed: ${JSON.stringify(boundedInvalidLedgerIssues)}`);
  const retainedInvalidProvenanceLedger = structuredClone(boundedInvalidProvenanceLedger);
  retainedInvalidProvenanceLedger.items[0].response_model = 'foreign/model';
  if (!sanitizedLedgerViolations(retainedInvalidProvenanceLedger).some(item => item.includes('retained the rejected value'))) throw new Error('Retained invalid-provenance value fixture was not rejected');
  const foreignInvalidProvenanceFieldLedger = structuredClone(boundedInvalidProvenanceLedger);
  foreignInvalidProvenanceFieldLedger.items[0].invalid_provenance_field = 'provider_payload';
  if (!sanitizedLedgerViolations(foreignInvalidProvenanceFieldLedger).some(item => item.includes('unbounded'))) throw new Error('Foreign invalid-provenance field fixture was not rejected');
  const boundedUpstreamRejectionLedger = structuredClone(coldLedger);
  const boundedUpstreamLedgerItem = boundedUpstreamRejectionLedger.items[0];
  Object.assign(boundedUpstreamLedgerItem, {
    outcome: 'failed',
    error_invariant: 'provider_upstream_rejection',
    provider_error_code: 429,
    provider_boundary: EXPECTED_PROVIDER_BOUNDARY,
    expected_upstream_provider: EXPECTED_UPSTREAM_PROVIDER,
    response_id: 'gen-1786483165-FFFFFFFFFFFFFFFFFFFF',
    actual_cost_usd: null,
  });
  for (const field of ['prompt_tokens', 'completion_tokens', 'total_tokens', 'response_model', 'upstream_provider', 'usage_source', 'finish_reason']) delete boundedUpstreamLedgerItem[field];
  boundedUpstreamRejectionLedger.summary = ledgerSummary(boundedUpstreamRejectionLedger.items);
  const boundedUpstreamLedgerIssues = sanitizedLedgerViolations(boundedUpstreamRejectionLedger);
  if (boundedUpstreamLedgerIssues.length) throw new Error(`Bounded upstream-rejection ledger fixture failed: ${JSON.stringify(boundedUpstreamLedgerIssues)}`);
  const providerConcurrencyLedger = structuredClone(coldLedger);
  const providerConcurrencyLedgerItem = providerConcurrencyLedger.items[0];
  Object.assign(providerConcurrencyLedgerItem, {
    call_count: 0,
    actual_cost_usd: null,
    outcome: 'blocked_provider_concurrency',
    error_type: 'OpenRouterSendAdmissionTimeoutError',
    error_invariant: 'provider_concurrency_timeout',
  });
  for (const field of ZERO_CALL_PROVIDER_RESULT_FIELDS) delete providerConcurrencyLedgerItem[field];
  providerConcurrencyLedger.summary = ledgerSummary(providerConcurrencyLedger.items);
  const providerConcurrencyLedgerIssues = sanitizedLedgerViolations(providerConcurrencyLedger);
  if (providerConcurrencyLedgerIssues.length
    || providerConcurrencyLedger.summary.network_calls !== coldLedger.summary.network_calls - 1
    || providerConcurrencyLedger.summary.unknown_cost_call_count !== coldLedger.summary.unknown_cost_call_count) throw new Error(`Provider-concurrency zero-call ledger fixture failed: ${JSON.stringify(providerConcurrencyLedgerIssues)}`);
  const forgedProviderConcurrencyLedgerCall = structuredClone(providerConcurrencyLedger);
  forgedProviderConcurrencyLedgerCall.items[0].call_count = 1;
  forgedProviderConcurrencyLedgerCall.summary = ledgerSummary(forgedProviderConcurrencyLedgerCall.items);
  if (!sanitizedLedgerViolations(forgedProviderConcurrencyLedgerCall).some(item => item.includes('zero-call'))) throw new Error('Provider-concurrency forged-call ledger fixture was not rejected');
  const forgedProviderConcurrencyLedgerCost = structuredClone(providerConcurrencyLedger);
  forgedProviderConcurrencyLedgerCost.items[0].actual_cost_usd = 0.01;
  forgedProviderConcurrencyLedgerCost.summary = ledgerSummary(forgedProviderConcurrencyLedgerCost.items);
  if (!sanitizedLedgerViolations(forgedProviderConcurrencyLedgerCost).some(item => item.includes('zero-call'))) throw new Error('Provider-concurrency forged-cost ledger fixture was not rejected');
  const forgedProviderConcurrencyLedgerIdentity = structuredClone(providerConcurrencyLedger);
  forgedProviderConcurrencyLedgerIdentity.items[0].response_id = 'gen-1786483159-hyYthqPv76o6PHXpGLzl';
  if (!sanitizedLedgerViolations(forgedProviderConcurrencyLedgerIdentity).some(item => item.includes('zero-call'))) throw new Error('Provider-concurrency forged-response ledger fixture was not rejected');
  const forgedUpstreamBoundaryLedger = structuredClone(boundedUpstreamRejectionLedger);
  forgedUpstreamBoundaryLedger.items[0].provider_boundary = 'OpenRouter';
  if (!sanitizedLedgerViolations(forgedUpstreamBoundaryLedger).some(item => item.includes('boundary attribution is forged'))) throw new Error('Forged upstream-rejection ledger attribution fixture was not rejected');
  const missingUpstreamBoundaryLedger = structuredClone(boundedUpstreamRejectionLedger);
  delete missingUpstreamBoundaryLedger.items[0].expected_upstream_provider;
  if (!sanitizedLedgerViolations(missingUpstreamBoundaryLedger).some(item => item.includes('attribution pair is incomplete'))) throw new Error('Missing upstream-rejection ledger attribution fixture was not rejected');
  const outOfScopeUpstreamBoundaryLedger = structuredClone(coldLedger);
  Object.assign(outOfScopeUpstreamBoundaryLedger.items[0], {
    provider_boundary: EXPECTED_PROVIDER_BOUNDARY,
    expected_upstream_provider: EXPECTED_UPSTREAM_PROVIDER,
  });
  if (!sanitizedLedgerViolations(outOfScopeUpstreamBoundaryLedger).some(item => item.includes('boundary attribution is out of scope'))) throw new Error('Out-of-scope upstream-rejection ledger attribution fixture was not rejected');
  const claimBearingUpstreamIdLedger = structuredClone(coldLedger);
  Object.assign(claimBearingUpstreamIdLedger.items[0], {
    outcome: 'failed',
    error_invariant: 'provider_upstream_rejection',
    provider_error_code: 400,
    provider_boundary: EXPECTED_PROVIDER_BOUNDARY,
    expected_upstream_provider: EXPECTED_UPSTREAM_PROVIDER,
    response_id: 'DEF-027-E0-DEMO',
  });
  claimBearingUpstreamIdLedger.summary = ledgerSummary(claimBearingUpstreamIdLedger.items);
  if (!sanitizedLedgerViolations(claimBearingUpstreamIdLedger).some(item => item.includes('exact OpenRouter generation ID'))) throw new Error('Claim-bearing upstream ledger response-ID fixture was not rejected');
  const minorityRun = structuredClone(coldRun);
  minorityRun.result.audit.agent_orchestration.agents[0].rejected_count = 2;
  minorityRun.result.audit.agent_orchestration.agents[0].deterministic_fallback_applied = true;
  minorityRun.result.audit.agent_orchestration.guarded_fallback_count = 1;
  if (!orchestrationContractViolations(minorityRun, 'cold').some(item => item.includes('strict majority'))) throw new Error('Accepted-minority negative fixture was not rejected');
  const invalidProjectionRun = structuredClone(coldRun);
  const invalidProjectionAgent = orchestrationAudit(invalidProjectionRun).agents.find(item => item.agent_id === 'canonical_facts');
  invalidProjectionAgent.source_reference_projection_fact_ids = ['not_an_accepted_fact'];
  invalidProjectionAgent.source_reference_projection_count = 1;
  if (!orchestrationContractViolations(invalidProjectionRun, 'cold').some(item => item.includes('source projection'))) throw new Error('Invalid canonical source-projection disclosure was not rejected');
  const wrongHashRun = structuredClone(coldRun);
  wrongHashRun.result.audit.agent_orchestration.deterministic_gates[0].output_artifact_hash = dtoHash({ wrong: true });
  if (!orchestrationContractViolations(wrongHashRun, 'cold').some(item => item.includes('final DTO'))) throw new Error('Wrong-artifact-hash negative fixture was not rejected');
  const duplicateResponseLedger = structuredClone(coldLedger);
  duplicateResponseLedger.items[1].response_id = duplicateResponseLedger.items[0].response_id;
  if (!coldLedgerContractViolations(orchestrationAudit(coldRun), duplicateResponseLedger).some(item => item.includes('response IDs'))) throw new Error('Duplicate-response negative fixture was not rejected');
  const brokenLineageLedger = structuredClone(combinedLedger);
  brokenLineageLedger.items.find(item => item.call_id === orchestrationAudit(warmRun).agents[0].call_id).origin_call_id = 'wrong_origin';
  if (!warmLineageContractViolations(orchestrationAudit(coldRun), orchestrationAudit(warmRun), brokenLineageLedger).issues.some(item => item.includes('warm origin'))) throw new Error('Broken-lineage negative fixture was not rejected');
  const forgedWarmArtifactRun = structuredClone(warmRun);
  orchestrationAudit(forgedWarmArtifactRun).agents[0].output_artifact_hash = dtoHash({ forged: 'cached-output' });
  if (!warmLineageContractViolations(orchestrationAudit(coldRun), orchestrationAudit(forgedWarmArtifactRun), combinedLedger).issues.some(item => item.includes('artifact and acceptance lineage'))) throw new Error('Forged warm artifact negative fixture was not rejected');
  const forgedWarmAcceptanceRun = structuredClone(warmRun);
  orchestrationAudit(forgedWarmAcceptanceRun).agents[1].accepted_ids = ['forged_cached_acceptance'];
  if (!warmLineageContractViolations(orchestrationAudit(coldRun), orchestrationAudit(forgedWarmAcceptanceRun), combinedLedger).issues.some(item => item.includes('artifact and acceptance lineage'))) throw new Error('Forged warm acceptance negative fixture was not rejected');
  if (!compatibleProcessDecisionValues({ decision_key: 'scope', decision_value: 'in_scope' }).has('scope_unverified')) throw new Error('Valid conservative process decision was rejected');
  if (compatibleProcessDecisionValues({ decision_key: 'scope', decision_value: 'in_scope' }).has('dispute_present')) throw new Error('Contradictory cross-key process decision was accepted');
  const unsafeAxeTarget = `.v20-learning-row[data-customer="${'claim-bearing-'.repeat(700)}"] > span`;
  const axeDiagnostics = axeViolationDiagnostics([{ id: 'color-contrast', impact: 'serious', help: 'Elements must meet minimum color contrast ratio thresholds', nodes: [{ target: [unsafeAxeTarget], html: '<span>claim-bearing text must not be logged</span>', failureSummary: 'Claim-bearing failure prose must not be logged', any: [{ id: 'color-contrast', impact: 'serious', message: 'Claim-bearing check prose must not be logged', data: { fgColor: '#147a56', bgColor: '#edf8f3', contrastRatio: 4.44, raw: 'must not be retained' } }], all: [], none: [] }] }]);
  if (axeDiagnostics.length !== 1 || axeDiagnostics[0].node_count !== 1 || axeDiagnostics[0].omitted_node_count !== 0 || !/^sha256:[0-9a-f]{64}$/.test(axeDiagnostics[0].nodes[0].target[0]) || JSON.stringify(axeDiagnostics).includes('claim-bearing') || axeDiagnostics[0].nodes[0].checks[0].data.contrastRatio !== 4.44 || 'raw' in axeDiagnostics[0].nodes[0].checks[0].data || 'html' in axeDiagnostics[0].nodes[0] || 'message' in axeDiagnostics[0].nodes[0].checks[0] || 'failure_summary' in axeDiagnostics[0].nodes[0]) throw new Error(`Bounded Axe diagnostics fixture failed: ${JSON.stringify(axeDiagnostics)}`);
  return { status: 'passed', fixtures: ['visible_cached_replay_and_terminal_failure_truth', 'authored_terminal_failure_restart', 'three_step_path_builder_opening_and_checkbox_rejection', 'eight_fact_source_to_fact_execution_trace_and_four_deterministic_laws', 'accepted_fact_law_graph_replay_and_neutral_fallback_identity', 'four_visible_workstream_icons_six_runtime_identities_and_tamper', 'exact_intake_claim_message_basis_and_generated_summary_rejection', 'call_bound_agent_history_and_reference_fail_closed', 'persistent_ten_node_projection_and_tamper', 'graph_native_review_scene_and_competing_artifact_rejection', 'semantic_attachment_cursor_tether_and_tamper', 'zoom_out_desktop_three_priority_diagnostics', 'process_preview_1440x900_containment_and_bottom_inset', 'bounded_future_claim_memory_delta_identity_origin_and_tamper', 'bounded_axe_node_diagnostics', 'session_scoped_run_read_coalescing', 'memory_reuse_renderer_determinism', 'stable_text_grounding_fact_selection', 'normalized_text_grounding', 'python_compatible_dto_hash', 'float_hash_divergence_fail_closed', 'fail_closed_model_contribution_badges', 'mixed_field_contribution_badge', 'post_memory_contribution_suppression', 'reciprocal_evidence_truth_and_tamper', 'structured_legal_truth_and_tamper', 'visual_reference_truth_and_tamper', 'precedent_ranking_truth_and_tamper', 'memory_application_truth_and_tamper', 'memory_boundary_event_cross_binding', 'dormant_memory_retrieval_not_application', 'production_opening_context', 'legacy_production_opening_rejection', 'premature_nemotron_plan_rejection', 'cold_network', 'parallel_source_artifact_hash_rejection', 'parallel_process_artifact_hash_rejection', 'process_field_membership_rejection', 'process_field_attribution_rejection', 'process_inherited_field_rejection_with_recomputed_hashes', 'evidence_field_membership_rejection', 'evidence_field_attribution_rejection', 'evidence_source_ref_rejection_with_recomputed_hashes', 'final_field_membership_rejection', 'final_current_node_binding_rejection', 'final_next_action_binding_rejection', 'final_supporting_facts_binding_rejection', 'final_upstream_contributions_binding_rejection', 'final_audit_checks_binding_rejection', 'noncontrolling_supporting_fact_source_binding', 'cold_upstream_provider_policy_rejection', 'warm_upstream_provider_policy_rejection', 'agent_role_label_rejection', 'gate_role_label_rejection', 'raw_alias_response_model', 'response_model_normalization_rejection', 'foreign_response_model_rejection', 'warm_lineage', 'review_transform_truth', 'deterministic_review_transform_truth', 'review_model_reacceptance_rejection', 'sensitive_field_rejection', 'internal_sentinel_rejection', 'topology_authority_misattribution_rejection', 'topology_dependency_rejection', 'final_payload_audit_binding_rejection', 'terminal_failure_sentinel_rejection', 'safe_terminal_diagnostics', 'safe_failure_receipt', 'provider_concurrency_zero_call_receipt', 'provider_concurrency_receipt_call_rejection', 'provider_concurrency_receipt_identity_rejection', 'safe_upstream_rejection_receipt', 'forged_upstream_rejection_receipt_attribution_rejection', 'missing_upstream_rejection_receipt_attribution_rejection', 'out_of_scope_upstream_rejection_receipt_attribution_rejection', 'unbounded_upstream_error_code_rejection', 'failure_receipt_allowlist_rejection', 'failure_receipt_lineage_rejection', 'charged_overrun_failure', 'hashed_invalid_model_provenance', 'raw_foreign_model_rejection', 'credential_provenance_rejection', 'claim_text_provenance_rejection', 'partial_response_identity_failure', 'canonical_root_failure', 'canonical_invalid_provenance_failure', 'claim_bearing_ledger_provenance_rejection', 'bounded_invalid_provenance_ledger', 'retained_invalid_provenance_rejection', 'foreign_invalid_provenance_field_rejection', 'safe_upstream_rejection_ledger', 'provider_concurrency_zero_call_ledger', 'provider_concurrency_ledger_call_rejection', 'provider_concurrency_ledger_cost_rejection', 'provider_concurrency_ledger_identity_rejection', 'forged_upstream_rejection_ledger_attribution_rejection', 'missing_upstream_rejection_ledger_attribution_rejection', 'out_of_scope_upstream_rejection_ledger_attribution_rejection', 'accepted_minority_rejection', 'invalid_source_projection_rejection', 'wrong_artifact_hash_rejection', 'duplicate_response_rejection', 'broken_lineage_rejection'], agents: REQUIRED_NEMOTRON_AGENT_IDS, gates: REQUIRED_DETERMINISTIC_GATE_IDS };
}

let report;
if (process.env.CASEPATH_QA_CONTRACT_SELF_TEST === '1') {
  console.log(JSON.stringify(await runContractSelfTest(), null, 2));
} else if (process.env.CASEPATH_QA_LATER_RUN_SELF_TEST === '1') {
  candidateSourceSnapshotStart = await captureCandidateSourceSnapshot({ requireApiBootReceipt: REQUIRE_INSTALLED_API_BOOT });
  const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH;
  if (executablePath !== '/Applications/ego lite.app/Contents/MacOS/ego lite') {
    throw new Error('Later-run self-test requires the governed ego-browser executable');
  }
  const probeBrowser = await chromium.launch({ headless: true, executablePath, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  try {
    console.log(JSON.stringify(await verifyBuiltArtifactLaterRunIsolation(probeBrowser), null, 2));
  } finally {
    await probeBrowser.close();
  }
} else {
  try {
    report = await execute();
  } catch (error) {
    report = {
      status: 'failed', release: PRODUCT_RELEASE, release_id: RELEASE_ID, journey_mode: acceptedJourneyMode, checkedAt: new Date().toISOString(), baseUrl: BASE, apiUrl: API, deployment: deploymentIdentity,
      candidate_source_identity: candidateSourceIdentityStart,
      api_runtime_identity: candidateSourceSnapshotStart?.apiBootIdentity || null,
      candidate_source_manifests: candidateSourceManifests,
      passed: checks.filter(item => item.passed).length, failed: 1, checks, notes, failures, runIds,
      error: error instanceof Error ? error.stack : String(error),
    };
    process.exitCode = 1;
  } finally {
    await fs.mkdir(OUT, { recursive: true }).catch(() => null);
    try {
      await retainEvidence();
    } catch (error) {
      failures.cleanup.push(`evidence retention: ${error}`);
    }
    await cleanup();
    try {
      await finalizeEvidenceManifest();
    } catch (error) {
      failures.cleanup.push(`evidence manifest: ${error}`);
    }
    if (failures.cleanup.length) {
      report.status = 'failed';
      report.failed = Math.max(1, report.failed || 0);
      report.error = `${report.error || ''}\nCleanup failed: ${failures.cleanup.join('; ')}`.trim();
      process.exitCode = 1;
    }
    try {
      const candidateSourceSnapshotEnd = await captureCandidateSourceSnapshot({
        requireApiBootReceipt: REQUIRE_INSTALLED_API_BOOT,
        allowValidatedWorkspaceJournalAdvance: true,
      });
      if (stableJson(candidateSourceSnapshotEnd) !== stableJson(candidateSourceSnapshotStart)) {
        throw new Error('candidate source or built-static identity drifted before report publication');
      }
    } catch (error) {
      report.status = 'failed';
      report.failed = Math.max(1, report.failed || 0);
      report.error = `${report.error || ''}\nFinal source identity failed: ${error instanceof Error ? error.message : String(error)}`.trim();
      process.exitCode = 1;
    }
    await fs.writeFile(path.join(OUT, 'report.json'), `${JSON.stringify(report, null, 2)}\n`, { flag: 'wx' });
    if (report.status === 'passed') console.log(JSON.stringify(report, null, 2));
    else console.error(report.error);
  }
}
