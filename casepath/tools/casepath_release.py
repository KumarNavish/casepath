#!/usr/bin/env python3
"""Generate and verify CasePath source and artifact release manifests."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
import math
import mimetypes
import os
import re
import stat
import subprocess
import sys
from datetime import date, datetime
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Iterable

import yaml
from PIL import Image
from pypdf import PdfReader


REPOSITORY = Path(__file__).resolve().parents[2]
TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))
API_SOURCE_ROOT = REPOSITORY / "casepath-api"
if str(API_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(API_SOURCE_ROOT))

import build_deployment_identity  # noqa: E402
from casepath_api.data import (  # noqa: E402
    ARTIFACTS as CASEPATH_ARTIFACTS,
    CLAIMS as CASEPATH_CLAIMS,
    HISTORICAL_CASES as GOVERNED_PRECEDENT_CORPUS,
    observable_claim_package,
)
from casepath_api.evidence_relations import (  # noqa: E402
    BASE_EVIDENCE_NODE_IDS,
    EVIDENCE_ITEM_IDS_BY_CLAIM,
)
from casepath_api.law_registry import legal_context as governed_legal_context  # noqa: E402
from casepath_api.precedent_ranking import rank_precedents  # noqa: E402
from casepath_api.projections import (  # noqa: E402
    apply_process_projection,
    decision_projection,
)
from casepath_api.validation import (  # noqa: E402
    LEARNING_SNAPSHOT_FIELDS,
    REQUIRED_PLAYBOOK_CHECK_NAMES,
)

RELEASE_PATH = REPOSITORY / "casepath" / "release.json"
SOURCE_MANIFEST_PATH = REPOSITORY / "casepath" / "source-manifest.json"
ARTIFACT_ROOT = REPOSITORY / "casepath-api" / "artifacts"
ARTIFACT_MANIFEST_PATH = ARTIFACT_ROOT / "artifact-manifest.json"
STATIC_DEPLOYMENT_PATH = REPOSITORY / "casepath-public" / "deployment.json"
LEGACY_RENDER_BLUEPRINT_PATH = Path(
    "casepath/tools/fixtures/render-legacy-20260811.yaml"
)
SOURCE_DATE_EPOCH = int(os.environ.get("SOURCE_DATE_EPOCH", "1786406400"))
RELEASE_CONTRACT = "casepath.release-contract/2.2.0"
CURATED_STATIC_BUILD_COMMAND = (
    "python3 casepath/tools/build_static_site.py --require-known-commit"
)
CURATED_STATIC_PUBLISH_PATH = "casepath-public"
DEFINITIVE_QA_BUILD_COMMAND = (
    "cd casepath-qa && npm ci --no-audit --no-fund && "
    "npx playwright install chromium && cd .. && "
    "bash casepath-qa/run-definitive-v20.sh"
)
DEFINITIVE_QA_START_COMMAND = "node casepath-qa/serve-evidence.mjs"
REQUIRED_PRODUCTION_MODE = "openrouter_nemotron"
REQUIRED_PRODUCTION_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
REQUIRED_PROVIDER_ENDPOINT_TAG = "together"
REQUIRED_UPSTREAM_PROVIDER = "Together"
DETERMINISTIC_REFERENCE_MODE = "deterministic_reference"
DETERMINISTIC_REFERENCE_PROFILE = "deterministic-reference-playbook"
ACCEPTED_PRODUCTION_RESPONSE_MODELS = {
    REQUIRED_PRODUCTION_MODEL,
    "nvidia/nemotron-3-ultra-550b-a55b-20260604",
}
PROVIDER_PROVENANCE_LIMITS = {
    "response_id": 160,
    "response_model": 160,
    "upstream_provider": 80,
}
PROVIDER_PROVENANCE_PATTERNS = {
    "response_id": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,159}$"),
    "upstream_provider": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,79}$"),
}
OPENROUTER_GENERATION_ID_PATTERN = re.compile(
    r"^gen-[0-9]{10}-[A-Za-z0-9]{20}$"
)
FORBIDDEN_PROVIDER_PROVENANCE_MARKERS = (
    "authorization",
    "api_key",
    "apikey",
    "bearer ",
    "credential",
    "sk-or-",
    "sk-",
    "secret",
    "sentinel",
    "customer",
    "landlord",
    "lease",
    "mould",
    "moisture",
    "tenant",
)
ACCEPTED_FINISH_REASONS = {
    "stop",
    "length",
    "tool_calls",
    "content_filter",
    "error",
    "cancelled",
}
PROVIDER_PROVENANCE_FIELDS = {
    "response_id",
    "response_model",
    "upstream_provider",
    "finish_reason",
}
ACCEPTED_USAGE_SOURCES = {"response", "generation_metadata"}
FORBIDDEN_PUBLIC_FIELDS = {
    "api_key",
    "canonical_output",
    "chain_of_thought",
    "completion",
    "messages",
    "private_reference",
    "prompt",
    "provider_credential",
    "raw",
    "raw_output",
    "raw_prompt",
    "reasoning",
    "request_body",
    "response_body",
    "system_prompt",
    "user_prompt",
}
ALLOWED_MODEL_LEDGER_FIELDS = {
    "call_id",
    "provider",
    "provider_endpoint",
    "upstream_provider",
    "model",
    "implementation",
    "orchestration_id",
    "agent_id",
    "agent_role",
    "parent_call_id",
    "delegation_id",
    "call_count",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "estimated_cost_usd",
    "actual_cost_usd",
    "latency_ms",
    "cache_key",
    "purpose",
    "outcome",
    "error_type",
    "error_agent_id",
    "error_fact_id",
    "error_invariant",
    "provider_error_code",
    "provider_boundary",
    "expected_upstream_provider",
    "invalid_provenance_field",
    "invalid_provenance_value_hash",
    "ignored_noncontrolling_normalized_proposals",
    "authority_mode",
    "accepted_fact_ids",
    "accepted_fact_count",
    "rejected_facts",
    "rejected_fact_count",
    "source_reference_projection_fact_ids",
    "source_reference_projection_count",
    "accepted_item_ids",
    "accepted_item_count",
    "rejected_items",
    "rejected_item_count",
    "ignored_proposal_count",
    "deterministic_fallback_applied",
    "response_id",
    "origin_call_id",
    "origin_usage",
    "origin_finish_reason",
    "response_model",
    "generation_model",
    "usage_source",
    "metadata_poll_count",
    "metadata_latency_ms",
    "finish_reason",
    "created_at",
    "updated_at",
}
MODEL_LEDGER_SUMMARY_FIELDS = {
    "records",
    "network_calls",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "actual_cost_usd",
    "actual_cost_complete",
    "unknown_cost_call_count",
    "outcomes",
}
ORIGIN_USAGE_FIELDS = {
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "actual_cost_usd",
    "usage_source",
}
REQUIRED_RUNTIME_PROFILE = "nemotron_langgraph_multi_agent_hybrid_guarded"
REQUIRED_ORCHESTRATION_SCHEMA = "casepath.nemotron-agent-dag/1.0.0"
REQUIRED_AUTHORITY_MODE = "multi_agent_hybrid_guarded"
REQUIRED_AGENT_IMPLEMENTATION = "langgraph_stategraph_langchain_openrouter"
REQUIRED_FRAMEWORK = {
    "langchain": "1.3.14",
    "langgraph": "1.2.9",
    "langchain_openrouter": "0.2.7",
}
REQUIRED_MODEL_AGENTS = (
    {
        "agent_id": "canonical_facts",
        "role": "Guarded Canonical Facts Agent",
        "stage": "canonicalization",
    },
    {
        "agent_id": "orchestrator_plan",
        "role": "Nemotron Orchestrator",
        "stage": "orchestration_plan",
    },
    {
        "agent_id": "document_source_integrity",
        "role": "Document and Source Integrity Agent",
        "stage": "parallel_specialist",
    },
    {
        "agent_id": "process_decision_mapping",
        "role": "Process Decision Mapping Agent",
        "stage": "parallel_specialist",
    },
    {
        "agent_id": "evidence_checklist",
        "role": "Evidence and Checklist Agent",
        "stage": "post_process_gate",
    },
    {
        "agent_id": "final_claim_brief_audit",
        "role": "Final Claim Brief Agent",
        "stage": "post_evidence_gate",
    },
)
REQUIRED_DETERMINISTIC_GATES = (
    {
        "gate_id": "deterministic_process_gate",
        "role": "Deterministic Process Contract Gate",
    },
    {
        "gate_id": "deterministic_evidence_gate",
        "role": "Deterministic Evidence Contract Gate",
    },
    {
        "gate_id": "whole_playbook_gate",
        "role": "Deterministic Whole-Playbook Gate",
    },
)
WHOLE_PLAYBOOK_OUTPUT_PROJECTION_CONTRACT = (
    "casepath.accepted-playbook-projection/1.0.0"
)
SPECIALIST_ARTIFACT_IDS = (
    "orchestrator_plan",
    "document_source_integrity",
    "process_decision_mapping",
    "evidence_checklist",
    "final_claim_brief_audit",
)
SPECIALIST_OUTPUT_ARTIFACTS = {
    "orchestrator_plan": "bounded_orchestration_focus",
    "document_source_integrity": "source_integrity_contribution",
    "process_decision_mapping": "process_mapping_contribution",
    "evidence_checklist": "evidence_checklist_contribution",
    "final_claim_brief_audit": "final_claim_brief_contribution",
}
FINAL_FIELD_CONTRIBUTION_IDS = {
    "current_node_id": "final:current_node",
    "next_action_node_id": "final:next_action",
    "supporting_fact_ids": "final:supporting_facts",
    "upstream_contribution_ids": "final:upstream_contributions",
    "audit_check_ids": "final:audit_checks",
}
FINAL_UPSTREAM_CONTRIBUTION_IDS = (
    "document_source_integrity",
    "evidence_checklist",
    "process_decision_mapping",
)
FINAL_AUDIT_CHECK_IDS = (
    "current_node_supported_by_canonical_facts",
    "evidence_items_bound_to_process_nodes",
    "next_action_connected_in_static_topology",
    "upstream_contribution_lineage_complete",
)
ACCEPTED_EVIDENCE_STATUSES = {
    "provided_sufficient",
    "provided_insufficient",
    "missing",
    "conditional",
    "not_applicable",
}
CANONICAL_ASSERTION_ID_CONTRACT = "casepath.canonical-facts/1.8.0#assertion-id"
CANONICAL_ASSERTION_MATERIALIZED_FIELDS = [
    "value",
    "state",
    "explanation",
    "normalized_value",
    "decision_value",
]
RELEASE_DECISION_OPTIONS = {
    "scope": {
        "supported_in_scope": "in_scope",
        "supported_out_of_scope": "out_of_scope",
        "unverified": "scope_unverified",
    },
    "dispute": {
        "present": "dispute_present",
        "absent": "no_dispute",
        "unverified": "dispute_unverified",
    },
    "urgency": {
        "urgent": "urgent",
        "not_urgent": "not_urgent",
        "unverified": "urgency_unverified",
    },
    "notification": {
        "notified": "notified",
        "not_notified": "not_notified",
        "unverified": "notification_unverified",
    },
    "recurrence": {
        "supported": "recurrence_supported",
        "not_supported": "recurrence_not_supported",
        "unverified": "recurrence_unverified",
    },
    "causation": {
        "building": "cause_building",
        "tenant_use": "cause_tenant_use",
        "mixed": "cause_mixed",
        "unresolved": "cause_unresolved",
    },
}
RELEASE_CONSERVATIVE_DECISIONS = {
    "scope": "scope_unverified",
    "dispute": "dispute_unverified",
    "urgency": "urgency_unverified",
    "notification": "notification_unverified",
    "recurrence": "recurrence_unverified",
    "causation": "cause_unresolved",
}
RELEASE_EVIDENCE_ARTIFACT_CAPABILITIES = {
    "claim_message": frozenset({"claim_message"}),
    "source_integrity": frozenset({"submitted_source"}),
    "lease": frozenset({"lease"}),
    "policy_reference": frozenset({"policy_reference"}),
    "customer_objective": frozenset(
        {"claim_message", "customer_correspondence"}
    ),
    "management_position": frozenset({"management_correspondence"}),
    "health_safety_statement": frozenset(
        {"claim_message", "customer_correspondence", "medical"}
    ),
    "defect_notice": frozenset({"defect_notice", "customer_correspondence"}),
    "proof_of_delivery": frozenset({"delivery_proof"}),
    "dated_photos": frozenset({"photo"}),
    "recurrence_chronology": frozenset({"timeline"}),
    "technical_assessment": frozenset({"technical_report", "inspection_report"}),
    "moisture_measurements": frozenset({"measurement_report"}),
    "building_envelope": frozenset({"building_report", "technical_report"}),
    "repair_history": frozenset(
        {"maintenance_record", "management_correspondence"}
    ),
    "use_evidence": frozenset({"use_log", "utility_record"}),
    "remediation_plan": frozenset({"remediation_plan", "maintenance_record"}),
    "financial_impact": frozenset({"invoice", "financial_record"}),
    "settlement_proposal": frozenset({"settlement_record", "correspondence"}),
    "conciliation_bundle": frozenset({"legal_filing"}),
    "completion_record": frozenset({"completion_record", "maintenance_record"}),
}
ACCEPTED_SOURCE_INTEGRITY_CLASSES = {
    "text_grounded",
    "visual_only",
    "metadata_only",
}
ACCEPTED_LINEAGE_FIELDS = (
    "agent_id",
    "call_id",
    "origin_call_id",
    "response_id",
    "delegation_id",
    "parent_call_id",
    "outcome",
    "accepted_ids",
    "accepted_count",
    "rejected_count",
    "deterministic_fallback_applied",
)
REQUIRED_PARALLEL_GROUPS = (("document_source_integrity", "process_decision_mapping"),)
REQUIRED_EXECUTION_TOPOLOGY = {
    "authority": "deterministic_application",
    "implementation": "compiled_langgraph_stategraph",
    "delegations": [
        {
            "agent_id": "document_source_integrity",
            "dependencies": ["orchestrator_plan"],
        },
        {
            "agent_id": "process_decision_mapping",
            "dependencies": ["orchestrator_plan"],
        },
        {
            "agent_id": "evidence_checklist",
            "dependencies": ["deterministic_process_gate"],
        },
        {
            "agent_id": "final_claim_brief_audit",
            "dependencies": ["deterministic_evidence_gate"],
        },
    ],
    "parallel_groups": [
        ["document_source_integrity", "process_decision_mapping"],
    ],
}
REQUIRED_RUNTIME_ACCEPTANCE_FLAGS = (
    "requires_successful_call_binding",
    "requires_positive_actual_cost",
    "requires_positive_token_counts",
    "requires_single_orchestration_binding",
    "requires_complete_required_agent_set",
    "requires_distinct_call_ids",
    "requires_distinct_response_ids",
    "requires_positive_accepted_contribution_per_agent",
    "requires_accepted_majority_per_agent",
    "requires_cold_network_run",
    "requires_deterministic_gate_passes",
    "requires_guarded_fallback_disclosure",
    "requires_source_reference_projection_disclosure",
    "requires_grounded_causal_artifact_recomputation",
    "requires_learning_replay_proof",
    "requires_learning_comparison_zero_model_activity",
)
RUNTIME_VERDICT_AUTHORITY = "dynamic_same_commit_qa_artifacts"
QA_REPORT_PATH = "report.json"
QA_EVIDENCE_MANIFEST_PATH = "evidence-manifest.json"
QA_EVIDENCE_MANIFEST_CONTRACT = "casepath.qa-evidence-manifest/1.0.0"
HISTORICAL_MODEL_VALIDATION_RECORDS = tuple(
    f"casepath/releases/model-validation-attempt-20260811-{number:02d}.json"
    for number in range(1, 25)
)
_HISTORICAL_TOP_FIELDS = frozenset(
    {
        "contract",
        "release_id",
        "attempt_id",
        "status",
        "acceptance_passed",
        "model_backed_release_evidence",
        "requested_runtime",
        "provider_observation",
        "accepted_ledger_record",
        "application_result",
        "sanitization",
    }
)
_HISTORICAL_EXECUTION_FIELDS = {
    "production-flagship-20260811-06": frozenset(
        "source_commit qa_deploy_id qa_deploy_outcome qa_run_id orchestration_id "
        "failed_agent_id provider_response_count downstream_model_calls "
        "deterministic_gate_receipts".split()
    ),
    "production-flagship-20260811-07": frozenset(
        "source_commit frontend_deploy_id api_deploy_id qa_deploy_id "
        "qa_deploy_outcome qa_run_id orchestration_id failed_agent_id "
        "provider_response_count downstream_model_calls deterministic_gate_receipts".split()
    ),
    "production-flagship-20260811-08": frozenset(
        "source_commit qa_deploy_id qa_deploy_outcome qa_deploy_started_at "
        "qa_error_at qa_build_failed_at qa_deploy_finished_at qa_run_id "
        "orchestration_id failed_agent_id provider_response_count "
        "downstream_model_calls downstream_agent_receipts deterministic_gate_receipts".split()
    ),
    "production-flagship-20260811-09": frozenset(
        "source_commit qa_deploy_id qa_deploy_outcome qa_deploy_created_at "
        "qa_deploy_finished_at qa_run_id ledger_created_at ledger_updated_at "
        "orchestration_id failed_agent_id network_call_count downstream_model_calls".split()
    ),
    "production-flagship-20260811-10": frozenset(
        "source_commit qa_deploy_id qa_deploy_outcome qa_deploy_created_at "
        "qa_deploy_started_at qa_error_at qa_deploy_finished_at qa_run_id "
        "ledger_created_at ledger_updated_at orchestration_id failed_agent_id "
        "network_call_count completed_model_calls failed_model_calls "
        "downstream_model_calls_after_failure deterministic_gate_receipts".split()
    ),
    "production-flagship-20260811-11": frozenset(
        "source_commit qa_deploy_id qa_deploy_outcome qa_deploy_created_at "
        "qa_deploy_started_at qa_error_at qa_build_failed_at "
        "qa_deploy_finished_at qa_run_id ledger_created_at ledger_updated_at "
        "orchestration_id failed_agent_id network_call_count "
        "completed_model_calls failed_model_calls downstream_model_calls_after_failure "
        "deterministic_gate_receipts".split()
    ),
    "production-flagship-20260811-12": frozenset(
        "source_commit qa_deploy_id qa_deploy_outcome qa_deploy_created_at "
        "qa_deploy_started_at qa_error_at qa_build_failed_at "
        "qa_deploy_finished_at qa_run_id ledger_created_at ledger_updated_at "
        "orchestration_id failed_agent_id network_call_count "
        "completed_model_calls failed_model_calls downstream_model_calls_after_failure "
        "deterministic_gate_receipts".split()
    ),
    "production-flagship-20260812-13": frozenset(
        "source_commit qa_service_id qa_deploy_id qa_deploy_outcome "
        "qa_deploy_created_at qa_deploy_started_at qa_deploy_finished_at "
        "orchestration_id failed_agent_id network_call_count "
        "completed_model_calls failed_model_calls downstream_model_calls_after_failure "
        "downstream_agent_receipts deterministic_gate_receipts".split()
    ),
    "production-flagship-20260812-14": frozenset(
        "source_commit frontend_service_id frontend_deploy_id "
        "frontend_deploy_outcome frontend_deploy_created_at "
        "frontend_deploy_started_at frontend_deploy_finished_at "
        "api_service_id api_deploy_id api_deploy_outcome "
        "api_deploy_created_at api_deploy_started_at api_deploy_finished_at "
        "qa_service_id qa_deploy_id qa_deploy_outcome qa_deploy_created_at "
        "qa_deploy_started_at qa_deploy_finished_at qa_error_at "
        "qa_build_failed_at qa_run_id qa_run_request_accepted_at "
        "ledger_created_at ledger_updated_at orchestration_id failed_agent_id "
        "failed_agent_ids network_call_count completed_model_calls "
        "failed_model_calls downstream_model_calls_after_failure "
        "downstream_agent_receipts later_model_roles_started "
        "deterministic_gate_receipts".split()
    ),
    "production-flagship-20260812-15": frozenset(
        "source_commit frontend_service_id frontend_deploy_id "
        "frontend_deploy_outcome frontend_deploy_created_at "
        "frontend_deploy_started_at frontend_deploy_finished_at "
        "api_service_id api_deploy_id api_deploy_outcome "
        "api_deploy_created_at api_deploy_started_at api_deploy_finished_at "
        "qa_service_id qa_deploy_id qa_deploy_outcome qa_deploy_created_at "
        "qa_deploy_started_at qa_deploy_finished_at qa_error_at "
        "qa_build_failed_at qa_run_id qa_run_request_accepted_at "
        "ledger_created_at ledger_updated_at orchestration_id "
        "network_call_count completed_model_calls failed_model_calls "
        "guarded_fallback_model_calls required_model_agent_ids "
        "deterministic_gate_receipts deterministic_gate_ids".split()
    ),
    "production-flagship-20260812-16": frozenset(
        "source_commit frontend_service_id frontend_deploy_id "
        "frontend_deploy_outcome frontend_deploy_created_at "
        "frontend_deploy_started_at frontend_deploy_finished_at "
        "api_service_id api_deploy_id api_deploy_outcome "
        "api_deploy_created_at api_deploy_started_at api_deploy_finished_at "
        "qa_service_id qa_deploy_id qa_deploy_outcome qa_deploy_created_at "
        "qa_deploy_started_at qa_deploy_finished_at qa_error_at "
        "qa_build_failed_at cold_run_id cold_run_request_accepted_at "
        "cold_orchestration_id warm_run_id warm_run_request_accepted_at "
        "warm_orchestration_id ledger_created_at ledger_updated_at "
        "network_call_count cold_model_calls warm_cache_calls "
        "failed_model_calls guarded_fallback_model_calls "
        "required_model_agent_ids deterministic_gate_receipts "
        "deterministic_gate_ids".split()
    ),
    "production-flagship-20260812-17": frozenset(
        "source_commit frontend_service_id frontend_deploy_id "
        "frontend_deploy_outcome frontend_deploy_started_at "
        "frontend_deploy_finished_at "
        "api_service_id api_deploy_id api_deploy_outcome api_deploy_started_at "
        "api_deploy_finished_at "
        "qa_service_id qa_deploy_id qa_deploy_outcome qa_deploy_created_at "
        "qa_deploy_started_at qa_deploy_finished_at qa_error_at "
        "qa_run_id qa_run_request_accepted_at ledger_created_at ledger_updated_at "
        "orchestration_id failed_agent_id network_call_count "
        "completed_model_calls failed_model_calls downstream_model_calls_after_failure "
        "deterministic_gate_receipts completed_deterministic_gate_ids "
        "deterministic_evidence_gate_started final_model_role_started "
        "whole_playbook_gate_started warm_replay_started".split()
    ),
    "production-flagship-20260812-18": frozenset(
        "source_commit frontend_service_id frontend_deploy_id "
        "frontend_deploy_outcome frontend_deploy_created_at "
        "frontend_deploy_started_at frontend_deploy_finished_at "
        "api_service_id api_deploy_id api_deploy_outcome api_deploy_created_at "
        "api_deploy_started_at api_deploy_finished_at "
        "qa_service_id qa_deploy_id qa_deploy_outcome qa_deploy_created_at "
        "qa_deploy_started_at qa_deploy_finished_at qa_error_at qa_build_failed_at "
        "qa_run_id qa_run_request_accepted_at ledger_created_at ledger_updated_at "
        "orchestration_id failed_agent_id network_call_count completed_model_calls "
        "failed_model_calls downstream_model_calls_after_failure "
        "deterministic_gate_receipts completed_deterministic_gate_ids "
        "evidence_checklist_started final_model_role_started "
        "whole_playbook_gate_started warm_replay_started receipt_sequence "
        "process_output_succeeded_after_failure "
        "process_completed_receipt_observed".split()
    ),
    "production-flagship-20260812-19": frozenset(
        "source_commit frontend_service_id frontend_deploy_id "
        "frontend_deploy_outcome frontend_deploy_created_at "
        "frontend_deploy_started_at frontend_deploy_finished_at "
        "api_service_id api_deploy_id api_deploy_outcome api_deploy_created_at "
        "api_deploy_started_at api_deploy_finished_at "
        "qa_service_id qa_deploy_id qa_deploy_outcome qa_deploy_created_at "
        "qa_deploy_started_at qa_deploy_finished_at qa_error_at "
        "qa_build_failed_at cold_run_id cold_run_request_accepted_at "
        "cold_orchestration_id warm_run_id warm_run_request_accepted_at "
        "warm_orchestration_id ledger_created_at ledger_updated_at "
        "network_call_count cold_model_calls warm_cache_calls "
        "failed_model_calls guarded_fallback_model_calls "
        "required_model_agent_ids deterministic_gate_receipts "
        "deterministic_gate_ids".split()
    ),
    "production-flagship-20260812-20": frozenset(
        "source_commit frontend_service_id frontend_deploy_id "
        "frontend_deploy_outcome frontend_deploy_created_at "
        "frontend_deploy_started_at frontend_deploy_finished_at "
        "api_service_id api_deploy_id api_deploy_outcome api_deploy_created_at "
        "api_deploy_started_at api_deploy_finished_at "
        "qa_service_id qa_deploy_id qa_deploy_outcome qa_deploy_created_at "
        "qa_deploy_started_at qa_deploy_finished_at qa_error_at "
        "qa_build_failed_at cold_run_id cold_run_request_accepted_at "
        "cold_orchestration_id warm_run_id warm_run_request_accepted_at "
        "warm_orchestration_id ledger_created_at ledger_updated_at "
        "network_call_count cold_model_calls warm_cache_calls "
        "failed_model_calls guarded_fallback_model_calls "
        "required_model_agent_ids deterministic_gate_receipts "
        "deterministic_gate_ids".split()
    ),
    "production-flagship-20260812-21": frozenset(
        "source_commit frontend_service_id frontend_deploy_id "
        "frontend_deploy_outcome frontend_deploy_created_at "
        "frontend_deploy_started_at frontend_deploy_finished_at "
        "api_service_id api_deploy_id api_deploy_outcome api_deploy_created_at "
        "api_deploy_started_at api_deploy_finished_at "
        "qa_service_id qa_deploy_id qa_deploy_outcome qa_deploy_created_at "
        "qa_deploy_started_at qa_deploy_finished_at qa_error_at "
        "qa_build_failed_at cold_run_id cold_run_request_accepted_at "
        "cold_orchestration_id warm_run_id warm_run_request_accepted_at "
        "warm_orchestration_id ledger_created_at ledger_updated_at "
        "network_call_count cold_model_calls warm_cache_calls "
        "failed_model_calls guarded_fallback_model_calls "
        "required_model_agent_ids deterministic_gate_receipts "
        "deterministic_gate_ids".split()
    ),
    "production-flagship-20260812-22": frozenset(
        "source_commit frontend_service_id frontend_deploy_id "
        "frontend_deploy_outcome frontend_deploy_created_at "
        "frontend_deploy_started_at frontend_deploy_finished_at "
        "api_service_id api_deploy_id api_deploy_outcome api_deploy_created_at "
        "api_deploy_started_at api_deploy_finished_at "
        "qa_service_id qa_deploy_id qa_deploy_outcome qa_deploy_created_at "
        "qa_deploy_started_at qa_deploy_finished_at deterministic_preflight_status "
        "deterministic_preflight_passed_checks deterministic_preflight_failed_checks "
        "production_browser_status production_browser_passed_checks "
        "production_browser_failed_checks flagship_cold_run_id "
        "flagship_cold_orchestration_id flagship_warm_run_id "
        "flagship_warm_orchestration_id later_cold_run_id "
        "later_cold_orchestration_id later_warm_run_id "
        "later_warm_orchestration_id network_call_count cache_hit_count "
        "global_ledger_record_count deterministic_gate_receipts "
        "deterministic_gate_ids".split()
    ),
    "production-flagship-20260812-23": frozenset(
        "source_commit frontend_service_id frontend_deploy_id "
        "frontend_deploy_outcome frontend_deploy_created_at "
        "frontend_deploy_started_at frontend_deploy_finished_at "
        "api_service_id api_deploy_id api_deploy_outcome api_deploy_created_at "
        "api_deploy_started_at api_deploy_finished_at "
        "qa_service_id qa_deploy_id qa_deploy_outcome qa_deploy_created_at "
        "qa_deploy_started_at qa_deploy_finished_at deterministic_preflight_status "
        "deterministic_preflight_passed_checks deterministic_preflight_failed_checks "
        "causal_preflight_verifier_passed production_marker_emitted_at qa_run_id "
        "orchestration_id ledger_created_at ledger_updated_at qa_error_at "
        "network_call_count completed_model_calls failed_model_calls "
        "downstream_model_calls_after_failure deterministic_gate_receipts "
        "warm_replay_started".split()
    ),
    "production-flagship-20260812-24": frozenset(
        "source_commit frontend_service_id frontend_deploy_id "
        "frontend_deploy_outcome frontend_deploy_created_at "
        "frontend_deploy_started_at frontend_deploy_finished_at "
        "api_service_id api_deploy_id api_deploy_outcome api_deploy_created_at "
        "api_deploy_started_at api_deploy_finished_at "
        "qa_service_id qa_deploy_id qa_deploy_outcome qa_deploy_created_at "
        "qa_deploy_started_at qa_deploy_finished_at "
        "deterministic_preflight_started_at deterministic_preflight_status "
        "deterministic_preflight_passed_checks deterministic_preflight_failed_checks "
        "causal_preflight_verifier_passed causal_preflight_verifier_passed_at "
        "deterministic_zero_provider_confirmed_at production_marker_emitted_at "
        "production_initial_ledger_checked_at production_initial_ledger_records "
        "production_initial_ledger_network_calls production_initial_ledger_actual_cost_usd "
        "production_initial_ledger_checked_before_first_run_post "
        "first_production_run_post_accepted_at flagship_cold_run_id "
        "flagship_cold_orchestration_id flagship_warm_run_id "
        "flagship_warm_orchestration_id later_cold_run_id "
        "later_cold_orchestration_id later_warm_run_started ledger_created_at "
        "ledger_updated_at qa_error_at global_ledger_record_count network_call_count "
        "cache_hit_count completed_network_model_calls failed_model_calls "
        "flagship_model_roles_complete flagship_deterministic_gate_receipts "
        "later_model_roles_complete later_downstream_model_calls_after_failure "
        "later_deterministic_gate_receipts".split()
    ),
}
_HISTORICAL_PROVIDER_FIELDS = {
    "authorized-smoke-20260811-01": frozenset(
        "canonical_model_id upstream_provider actual_cost_usd prompt_tokens "
        "completion_tokens total_tokens finish_reason".split()
    ),
    "authorized-smoke-20260811-02": frozenset(
        "provider provider_outcome upstream_provider response_model response_id "
        "actual_cost_usd prompt_tokens completion_tokens total_tokens finish_reason".split()
    ),
    "authorized-smoke-20260811-03": frozenset(
        "provider provider_outcome synchronous_usage_cost_present "
        "new_openrouter_log_generation_observed provider_cache_replay_assessment "
        "charge_status charge_included_in_known_aggregate".split()
    ),
    "authorized-smoke-20260811-04": frozenset(
        "provider provider_outcome upstream_provider response_model response_id "
        "actual_cost_usd prompt_tokens completion_tokens total_tokens finish_reason".split()
    ),
    "production-flagship-20260811-05": frozenset(
        "provider provider_outcome response_model response_id actual_cost_usd "
        "prompt_tokens completion_tokens total_tokens finish_reason".split()
    ),
    "production-flagship-20260811-06": frozenset(
        "provider provider_outcome response_model response_id actual_cost_usd "
        "prompt_tokens completion_tokens total_tokens finish_reason usage_source latency_ms".split()
    ),
    "production-flagship-20260811-07": frozenset(
        "provider provider_outcome response_http_status sdk sdk_version sdk_error_type "
        "response_identity_status synchronous_usage_cost_present "
        "new_openrouter_log_generation_observed openrouter_log_check_performed "
        "provider_cache_replay_assessment charge_status "
        "charge_included_in_known_aggregate estimated_cost_reservation_usd "
        "estimated_reservation_is_actual_charge latency_ms".split()
    ),
    "production-flagship-20260811-08": frozenset(
        "provider provider_outcome requested_model response_model response_id "
        "actual_cost_usd prompt_tokens completion_tokens total_tokens finish_reason "
        "latency_ms bounded_generation_metadata_lookup "
        "later_generation_metadata_observation".split()
    ),
    "production-flagship-20260811-09": frozenset(
        "provider provider_outcome requested_model response_identity_status "
        "routing_diagnosis upstream_request_log_observation generation_metadata_lookup "
        "synchronous_usage_cost_present openrouter_upstream_request_log_observed "
        "new_openrouter_log_generation_observed openrouter_log_check_performed "
        "provider_cache_replay_assessment charge_status "
        "charge_included_in_known_aggregate estimated_cost_reservation_usd "
        "estimated_reservation_is_actual_charge latency_ms".split()
    ),
    "production-flagship-20260811-10": frozenset(
        "provider provider_outcome requested_model upstream_provider network_call_count "
        "actual_cost_usd actual_cost_complete unknown_cost_call_count prompt_tokens "
        "completion_tokens total_tokens calls".split()
    ),
    "production-flagship-20260811-11": frozenset(
        "provider provider_outcome requested_model upstream_provider network_call_count "
        "actual_cost_usd actual_cost_complete unknown_cost_call_count prompt_tokens "
        "completion_tokens total_tokens calls".split()
    ),
    "production-flagship-20260811-12": frozenset(
        "provider provider_outcome requested_model upstream_provider network_call_count "
        "actual_cost_usd actual_cost_complete unknown_cost_call_count prompt_tokens "
        "completion_tokens total_tokens calls".split()
    ),
    "production-flagship-20260812-13": frozenset(
        "provider provider_outcome requested_model upstream_provider network_call_count "
        "response_identity_status synchronous_usage_cost_present "
        "new_openrouter_log_generation_observed openrouter_log_check_performed "
        "openrouter_upstream_request_log_observed provider_cache_replay_assessment "
        "charge_status charge_included_in_known_aggregate actual_cost_complete "
        "unknown_cost_call_count upstream_request_log_observation "
        "application_ledger_observation failure_attribution "
        "key_account_capacity_observation".split()
    ),
    "production-flagship-20260812-14": frozenset(
        "provider provider_outcome requested_model successful_upstream_provider "
        "failed_call_expected_upstream_provider "
        "failed_call_upstream_provider_identity_status network_call_count "
        "actual_cost_usd actual_cost_complete unknown_cost_call_count "
        "prompt_tokens completion_tokens total_tokens "
        "known_cost_included_in_aggregate unknown_cost_excluded_from_aggregate "
        "calls".split()
    ),
    "production-flagship-20260812-15": frozenset(
        "provider provider_outcome requested_model upstream_provider "
        "network_call_count actual_cost_usd actual_cost_complete "
        "unknown_cost_call_count prompt_tokens completion_tokens total_tokens "
        "outcomes physical_provider_max_in_flight application_retry_count calls".split()
    ),
    "production-flagship-20260812-16": frozenset(
        "provider provider_outcome requested_model upstream_provider "
        "network_call_count actual_cost_usd actual_cost_complete "
        "unknown_cost_call_count prompt_tokens completion_tokens total_tokens "
        "outcomes physical_provider_max_in_flight application_retry_count calls".split()
    ),
    "production-flagship-20260812-17": frozenset(
        "provider provider_outcome requested_model upstream_provider "
        "network_call_count actual_cost_usd actual_cost_complete "
        "unknown_cost_call_count prompt_tokens completion_tokens total_tokens "
        "outcomes physical_provider_max_in_flight application_retry_count calls".split()
    ),
    "production-flagship-20260812-18": frozenset(
        "provider provider_outcome requested_model upstream_provider "
        "network_call_count actual_cost_usd actual_cost_complete "
        "unknown_cost_call_count prompt_tokens completion_tokens total_tokens "
        "outcomes physical_provider_max_in_flight application_retry_count calls".split()
    ),
    "production-flagship-20260812-19": frozenset(
        "provider provider_outcome requested_model upstream_provider "
        "network_call_count actual_cost_usd actual_cost_complete "
        "unknown_cost_call_count prompt_tokens completion_tokens total_tokens "
        "outcomes physical_provider_max_in_flight application_retry_count calls".split()
    ),
    "production-flagship-20260812-20": frozenset(
        "provider provider_outcome requested_model upstream_provider "
        "network_call_count actual_cost_usd actual_cost_complete "
        "unknown_cost_call_count prompt_tokens completion_tokens total_tokens "
        "outcomes global_ledger_summary physical_provider_max_in_flight "
        "application_retry_count calls".split()
    ),
    "production-flagship-20260812-21": frozenset(
        "provider provider_outcome requested_model upstream_provider "
        "network_call_count actual_cost_usd actual_cost_complete "
        "unknown_cost_call_count prompt_tokens completion_tokens total_tokens "
        "outcomes global_ledger_summary physical_provider_max_in_flight "
        "application_retry_count calls".split()
    ),
    "production-flagship-20260812-22": frozenset(
        "provider provider_outcome requested_model upstream_provider "
        "network_call_count actual_cost_usd actual_cost_complete "
        "unknown_cost_call_count prompt_tokens completion_tokens total_tokens "
        "outcomes global_ledger_summary physical_provider_max_in_flight "
        "application_retry_count orchestration_summaries".split()
    ),
    "production-flagship-20260812-23": frozenset(
        "provider provider_outcome requested_model upstream_provider "
        "network_call_count actual_cost_usd actual_cost_complete "
        "unknown_cost_call_count prompt_tokens completion_tokens total_tokens "
        "outcomes physical_provider_max_in_flight application_retry_count call".split()
    ),
    "production-flagship-20260812-24": frozenset(
        "provider provider_outcome requested_model successful_upstream_provider "
        "failed_call_expected_upstream_provider "
        "failed_call_upstream_provider_identity_status network_call_count "
        "actual_cost_usd actual_cost_complete unknown_cost_call_count prompt_tokens "
        "completion_tokens total_tokens outcomes prior_cumulative_known_actual_cost_usd "
        "cumulative_known_actual_cost_usd physical_provider_max_in_flight "
        "application_retry_count calls".split()
    ),
}
_HISTORICAL_APPLICATION_FIELDS = {
    "authorized-smoke-20260811-01": frozenset(
        "outcome failure_type successful_ledger_call_bound ledger_call_id".split()
    ),
    "authorized-smoke-20260811-02": frozenset(
        "outcome failure_type successful_ledger_call_bound ledger_call_id "
        "ledger_outcome canonical_result_accepted".split()
    ),
    "authorized-smoke-20260811-03": frozenset(
        "outcome failure_type successful_ledger_call_bound ledger_call_id "
        "canonical_result_accepted".split()
    ),
    "authorized-smoke-20260811-04": frozenset(
        "outcome failure_type successful_ledger_call_bound ledger_call_id "
        "ledger_outcome canonical_result_accepted".split()
    ),
    "production-flagship-20260811-05": frozenset(
        "outcome failure_type successful_ledger_call_bound ledger_call_id ledger_outcome "
        "canonical_result_accepted accepted_fact_count rejected_fact_count "
        "rejected_invariants".split()
    ),
    "production-flagship-20260811-06": frozenset(
        "outcome failure_type error_type successful_ledger_call_bound ledger_call_id "
        "ledger_outcome canonical_result_accepted upstream_provider_persisted "
        "contribution_diagnostics_retained".split()
    ),
    "production-flagship-20260811-07": frozenset(
        "outcome failure_type error_type successful_ledger_call_bound ledger_call_id "
        "ledger_outcome canonical_result_accepted response_identity_retained "
        "usage_metadata_retained contribution_diagnostics_retained".split()
    ),
    "production-flagship-20260811-08": frozenset(
        "outcome failure_type error_type error_invariant successful_ledger_call_bound "
        "ledger_call_id ledger_outcome canonical_result_accepted "
        "response_identity_retained usage_metadata_retained "
        "later_generation_metadata_verified contribution_diagnostics_retained".split()
    ),
    "production-flagship-20260811-09": frozenset(
        "outcome failure_type error_type error_invariant successful_ledger_call_bound "
        "ledger_call_id ledger_outcome canonical_result_accepted "
        "response_identity_retained usage_metadata_retained "
        "accepted_generation_recovered contribution_diagnostics_retained".split()
    ),
    "production-flagship-20260811-10": frozenset(
        "outcome failure_type error_type error_invariant successful_ledger_call_bound "
        "ledger_call_id ledger_outcome canonical_stage_completed "
        "canonical_stage_outcome canonical_stage_call_id "
        "canonical_guarded_fallback_applied "
        "canonical_contribution_diagnostics_retained orchestrator_plan_accepted "
        "full_orchestration_accepted runtime_acceptance_established "
        "downstream_execution_started".split()
    ),
    "production-flagship-20260811-11": frozenset(
        "outcome failure_type error_type error_invariant successful_ledger_call_bound "
        "ledger_call_id ledger_outcome canonical_stage_completed "
        "canonical_stage_outcome canonical_stage_call_id "
        "canonical_guarded_fallback_applied "
        "canonical_contribution_diagnostics_retained orchestrator_plan_accepted "
        "full_orchestration_accepted runtime_acceptance_established "
        "downstream_execution_started".split()
    ),
    "production-flagship-20260811-12": frozenset(
        "outcome failure_type error_type error_invariant successful_ledger_call_bound "
        "ledger_call_id ledger_outcome canonical_stage_completed "
        "canonical_stage_outcome canonical_stage_call_id "
        "canonical_guarded_fallback_applied "
        "canonical_contribution_diagnostics_retained orchestrator_plan_accepted "
        "orchestrator_plan_call_id document_source_integrity_accepted "
        "document_source_integrity_call_id process_decision_mapping_accepted "
        "full_orchestration_accepted runtime_acceptance_established "
        "downstream_execution_started later_model_calls_after_failure".split()
    ),
    "production-flagship-20260812-13": frozenset(
        "outcome failure_type error_type error_invariant_retained "
        "successful_ledger_call_bound ledger_call_id ledger_outcome "
        "canonical_result_accepted canonical_stage_completed "
        "response_identity_retained usage_metadata_retained actual_cost_retained "
        "full_orchestration_accepted runtime_acceptance_established "
        "downstream_execution_started deterministic_gates_started "
        "external_cause_detail".split()
    ),
    "production-flagship-20260812-14": frozenset(
        "outcome failure_type error_type error_invariant "
        "successful_ledger_call_bound ledger_call_id ledger_outcome "
        "failed_ledger_call_ids canonical_stage_completed "
        "canonical_stage_outcome canonical_stage_call_id "
        "canonical_guarded_fallback_applied "
        "canonical_contribution_diagnostics_retained orchestrator_plan_accepted "
        "orchestrator_plan_call_id parallel_specialists_started "
        "document_source_integrity_accepted document_source_integrity_call_id "
        "process_decision_mapping_accepted process_decision_mapping_call_id "
        "later_model_calls_after_failure deterministic_gates_started "
        "full_orchestration_accepted runtime_acceptance_established "
        "failed_call_upstream_identity_retained external_cause_detail".split()
    ),
    "production-flagship-20260812-15": frozenset(
        "outcome successful_ledger_calls_bound required_model_roles_complete "
        "complete_model_call_ids deterministic_gates_complete "
        "complete_deterministic_gate_ids full_orchestration_accepted "
        "runtime_acceptance_established".split()
    ),
    "production-flagship-20260812-16": frozenset(
        "outcome successful_ledger_calls_bound required_model_roles_complete "
        "complete_model_call_ids deterministic_gates_complete "
        "complete_deterministic_gate_ids full_orchestration_accepted "
        "runtime_acceptance_established".split()
    ),
    "production-flagship-20260812-17": frozenset(
        "outcome failure_type error_type error_invariant "
        "successful_ledger_call_bound ledger_call_id ledger_outcome "
        "canonical_stage_completed canonical_stage_call_id "
        "orchestrator_plan_accepted orchestrator_plan_call_id "
        "document_source_integrity_accepted document_source_integrity_call_id "
        "process_decision_mapping_accepted process_decision_mapping_call_id "
        "deterministic_process_gate_passed evidence_checklist_accepted "
        "evidence_checklist_call_id evidence_contribution_diagnostics_retained "
        "evidence_accepted_item_count evidence_rejected_item_count "
        "deterministic_evidence_gate_started final_model_role_started "
        "whole_playbook_gate_started warm_replay_started "
        "full_orchestration_accepted runtime_acceptance_established "
        "downstream_execution_started later_model_calls_after_failure".split()
    ),
    "production-flagship-20260812-18": frozenset(
        "outcome failure_type error_type error_invariant "
        "successful_ledger_call_bound ledger_call_id ledger_outcome "
        "canonical_stage_completed canonical_stage_call_id "
        "orchestrator_plan_accepted orchestrator_plan_call_id "
        "parallel_specialists_started document_source_integrity_accepted "
        "document_source_integrity_call_id document_semantic_scoring_started "
        "document_deterministic_fallback_applied "
        "process_decision_mapping_output_succeeded "
        "process_decision_mapping_call_id process_completion_receipt_observed "
        "deterministic_process_gate_started evidence_checklist_started "
        "final_model_role_started whole_playbook_gate_started warm_replay_started "
        "full_orchestration_accepted runtime_acceptance_established "
        "downstream_execution_started later_model_calls_after_failure".split()
    ),
    "production-flagship-20260812-19": frozenset(
        "outcome successful_ledger_calls_bound required_model_roles_complete "
        "complete_model_call_ids deterministic_gates_complete "
        "complete_deterministic_gate_ids full_orchestration_accepted "
        "runtime_acceptance_established".split()
    ),
    "production-flagship-20260812-20": frozenset(
        "outcome successful_ledger_calls_bound required_model_roles_complete "
        "complete_model_call_ids deterministic_gates_complete "
        "complete_deterministic_gate_ids deterministic_gate_progression_observed "
        "deterministic_gate_artifact_hashes_retained "
        "deterministic_gate_artifact_hashes_recoverable "
        "full_orchestration_accepted runtime_acceptance_established".split()
    ),
    "production-flagship-20260812-21": frozenset(
        "outcome successful_ledger_calls_bound required_model_roles_complete "
        "complete_model_call_ids deterministic_gates_complete "
        "complete_deterministic_gate_ids deterministic_gate_progression_observed "
        "deterministic_gate_artifact_hashes_retained "
        "deterministic_gate_artifact_hashes_recoverable "
        "full_orchestration_accepted runtime_acceptance_established".split()
    ),
    "production-flagship-20260812-22": frozenset(
        "outcome successful_ledger_calls_bound required_model_roles_complete "
        "cold_model_call_count warm_cache_hit_count deterministic_gates_complete "
        "complete_deterministic_gate_ids full_orchestration_accepted "
        "runtime_acceptance_established".split()
    ),
    "production-flagship-20260812-23": frozenset(
        "outcome failure_type error_type error_invariant "
        "successful_ledger_call_bound ledger_call_id ledger_outcome "
        "canonical_result_accepted accepted_fact_count rejected_fact_count "
        "downstream_execution_started warm_replay_started "
        "full_orchestration_accepted runtime_acceptance_established".split()
    ),
    "production-flagship-20260812-24": frozenset(
        "outcome failure_type error_type error_invariant "
        "successful_ledger_call_bound ledger_call_id ledger_outcome "
        "flagship_cold_accepted "
        "flagship_cold_call_ids flagship_model_roles_complete "
        "flagship_deterministic_gates_complete "
        "complete_flagship_deterministic_gate_ids flagship_warm_cache_accepted "
        "later_canonical_result_accepted later_canonical_call_id "
        "later_canonical_accepted_fact_count later_canonical_rejected_fact_count "
        "later_orchestrator_plan_accepted failed_ledger_call_id "
        "failed_ledger_outcome later_downstream_execution_started "
        "later_deterministic_gates_started later_warm_replay_started "
        "full_production_journey_accepted runtime_acceptance_established".split()
    ),
}
_HISTORICAL_FAILURE_TYPES = {
    "authorized-smoke-20260811-01": "exact_private_reference_mismatch",
    "authorized-smoke-20260811-02": "non_controlling_normalized_value",
    "authorized-smoke-20260811-03": "usage_metadata_completeness",
    "authorized-smoke-20260811-04": "fact_dispute/source_reference_set",
    "production-flagship-20260811-05": "hybrid_model_contribution_strict_majority",
    "production-flagship-20260811-06": "post_validation_missing_upstream_provider_persistence",
    "production-flagship-20260811-07": "openrouter_sdk_chat_result_response_validation",
    "production-flagship-20260811-08": "same_generation_metadata_not_available_within_bounded_lookup",
    "production-flagship-20260811-09": "provider_response_envelope",
    "production-flagship-20260811-10": "orchestrator_plan_truncated_at_output_limit",
    "production-flagship-20260811-11": "orchestrator_plan_truncated_at_output_limit",
    "production-flagship-20260811-12": "process_decision_mapping_model_contribution_majority",
    "production-flagship-20260812-13": "external_deepinfra_http_429",
    "production-flagship-20260812-14": (
        "parallel_specialist_provider_upstream_rejection"
    ),
    "production-flagship-20260812-17": (
        "evidence_checklist_model_contribution_majority"
    ),
    "production-flagship-20260812-18": (
        "document_source_integrity_truncated_at_output_limit"
    ),
    "production-flagship-20260812-23": (
        "canonical_facts_hybrid_model_contribution"
    ),
    "production-flagship-20260812-24": (
        "later_orchestrator_upstream_429_followed_by_terminal_ui_timeout"
    ),
}
_HISTORICAL_PROVIDER_OUTCOMES = {
    "authorized-smoke-20260811-02": "succeeded",
    "authorized-smoke-20260811-03": "structured_content_returned",
    "authorized-smoke-20260811-04": "succeeded",
    "production-flagship-20260811-05": "succeeded",
    "production-flagship-20260811-06": "succeeded",
    "production-flagship-20260811-07": "http_200_response_schema_rejected_by_sdk",
    "production-flagship-20260811-08": "succeeded",
    "production-flagship-20260811-09": "upstream_rejected",
    "production-flagship-20260811-10": "partial_success_then_length_rejected",
    "production-flagship-20260811-11": "partial_success_then_length_rejected",
    "production-flagship-20260811-12": "three_successes_then_process_majority_rejected",
    "production-flagship-20260812-13": "deepinfra_http_429",
    "production-flagship-20260812-14": (
        "two_successes_then_parallel_upstream_429"
    ),
    "production-flagship-20260812-17": (
        "four_successes_then_evidence_majority_rejected"
    ),
    "production-flagship-20260812-18": (
        "three_successes_one_document_length_rejected"
    ),
    "production-flagship-20260812-19": "six_roles_succeeded",
    "production-flagship-20260812-20": "six_roles_succeeded",
    "production-flagship-20260812-21": "six_roles_succeeded",
    "production-flagship-20260812-22": "twelve_network_calls_succeeded",
    "production-flagship-20260812-23": "canonical_facts_contribution_rejected",
    "production-flagship-20260812-24": (
        "seven_successes_six_cache_hits_then_later_orchestrator_upstream_429"
    ),
}
_HISTORICAL_ERROR_TYPES = {
    "production-flagship-20260811-06": "KeyError",
    "production-flagship-20260811-07": "ResponseValidationError",
    "production-flagship-20260811-08": "ModelResponseError",
    "production-flagship-20260811-09": "ModelResponseError",
    "production-flagship-20260811-10": "AgentBoundaryError",
    "production-flagship-20260811-11": "AgentBoundaryError",
    "production-flagship-20260811-12": "AgentBoundaryError",
    "production-flagship-20260812-13": "TooManyRequestsResponseError",
    "production-flagship-20260812-14": "OpenRouterUpstreamRejectionError",
    "production-flagship-20260812-17": "AgentBoundaryError",
    "production-flagship-20260812-18": "AgentBoundaryError",
    "production-flagship-20260812-23": "ModelResponseError",
    "production-flagship-20260812-24": "OpenRouterUpstreamRejectionError",
}
_HISTORICAL_ERROR_INVARIANTS = {
    "production-flagship-20260811-08": "generation_metadata_completeness",
    "production-flagship-20260811-09": "provider_response_envelope",
    "production-flagship-20260811-10": "provider_finish_reason",
    "production-flagship-20260811-11": "provider_finish_reason",
    "production-flagship-20260811-12": "model_contribution_majority",
    "production-flagship-20260812-14": "provider_upstream_rejection",
    "production-flagship-20260812-17": "model_contribution_majority",
    "production-flagship-20260812-18": "provider_finish_reason",
    "production-flagship-20260812-23": "hybrid_model_contribution",
    "production-flagship-20260812-24": "provider_upstream_rejection",
}
_HISTORICAL_TWO_CALL_FIELDS = {
    "canonical_facts": frozenset(
        "call_id agent_id outcome response_id response_model upstream_provider "
        "finish_reason actual_cost_usd prompt_tokens completion_tokens total_tokens "
        "latency_ms created_at updated_at deterministic_fallback_applied "
        "accepted_fact_count rejected_fact_count source_reference_projection_count".split()
    ),
    "orchestrator_plan": frozenset(
        "call_id agent_id outcome response_id response_model upstream_provider "
        "finish_reason actual_cost_usd prompt_tokens completion_tokens total_tokens "
        "latency_ms created_at updated_at error_type error_invariant".split()
    ),
}
_HISTORICAL_TWO_CALL_OUTPUT_LIMITS = {
    "production-flagship-20260811-10": 400,
    "production-flagship-20260811-11": 800,
}
_HISTORICAL_ATTEMPT_12_CALL_FIELDS = {
    "canonical_facts": _HISTORICAL_TWO_CALL_FIELDS["canonical_facts"],
    "orchestrator_plan": frozenset(
        "call_id agent_id outcome response_id response_model upstream_provider "
        "finish_reason actual_cost_usd prompt_tokens completion_tokens total_tokens "
        "latency_ms created_at updated_at deterministic_fallback_applied "
        "accepted_item_count rejected_item_count ignored_proposal_count".split()
    ),
    "document_source_integrity": frozenset(
        "call_id agent_id outcome response_id response_model upstream_provider "
        "finish_reason actual_cost_usd prompt_tokens completion_tokens total_tokens "
        "latency_ms created_at updated_at deterministic_fallback_applied "
        "accepted_item_count rejected_item_count ignored_proposal_count".split()
    ),
    "process_decision_mapping": frozenset(
        "call_id agent_id outcome response_id response_model upstream_provider "
        "finish_reason actual_cost_usd prompt_tokens completion_tokens total_tokens "
        "latency_ms created_at updated_at error_type error_invariant".split()
    ),
}
_HISTORICAL_ATTEMPT_14_CALL_FIELDS = {
    "canonical_facts": frozenset(
        "call_id agent_id parent_call_id delegation_id outcome response_id "
        "response_model upstream_provider finish_reason actual_cost_usd "
        "estimated_cost_usd prompt_tokens completion_tokens total_tokens "
        "usage_source latency_ms created_at updated_at "
        "deterministic_fallback_applied accepted_fact_count rejected_fact_count "
        "source_reference_projection_count "
        "ignored_noncontrolling_normalized_proposals".split()
    ),
    "orchestrator_plan": frozenset(
        "call_id agent_id parent_call_id delegation_id outcome response_id "
        "response_model upstream_provider finish_reason actual_cost_usd "
        "estimated_cost_usd prompt_tokens completion_tokens total_tokens "
        "usage_source latency_ms created_at updated_at "
        "deterministic_fallback_applied accepted_item_count rejected_item_count "
        "ignored_proposal_count".split()
    ),
    "process_decision_mapping": frozenset(
        "call_id agent_id parent_call_id delegation_id outcome estimated_cost_usd "
        "actual_cost_usd provider_error_code provider_boundary "
        "expected_upstream_provider response_identity_retained "
        "response_model_retained upstream_provider_retained "
        "usage_metadata_retained actual_cost_retained latency_ms error_type "
        "error_invariant created_at updated_at".split()
    ),
    "document_source_integrity": frozenset(
        "call_id agent_id parent_call_id delegation_id outcome estimated_cost_usd "
        "actual_cost_usd provider_error_code provider_boundary "
        "expected_upstream_provider response_identity_retained "
        "response_model_retained upstream_provider_retained "
        "usage_metadata_retained actual_cost_retained latency_ms error_type "
        "error_invariant created_at updated_at".split()
    ),
}
_HISTORICAL_ATTEMPT_15_COMMON_CALL_FIELDS = frozenset(
    "call_id orchestration_id agent_id parent_call_id delegation_id outcome "
    "response_id response_model "
    "upstream_provider finish_reason actual_cost_usd prompt_tokens "
    "completion_tokens total_tokens usage_source latency_ms created_at updated_at "
    "deterministic_fallback_applied".split()
)
_HISTORICAL_ATTEMPT_15_CALL_FIELDS = {
    "canonical_facts": _HISTORICAL_ATTEMPT_15_COMMON_CALL_FIELDS
    | frozenset(
        "accepted_fact_count rejected_fact_count source_reference_projection_count "
        "ignored_noncontrolling_normalized_proposals".split()
    ),
    "orchestrator_plan": _HISTORICAL_ATTEMPT_15_COMMON_CALL_FIELDS
    | frozenset("accepted_item_count rejected_item_count ignored_proposal_count".split()),
    "document_source_integrity": _HISTORICAL_ATTEMPT_15_COMMON_CALL_FIELDS
    | frozenset("accepted_item_count rejected_item_count ignored_proposal_count".split()),
    "process_decision_mapping": _HISTORICAL_ATTEMPT_15_COMMON_CALL_FIELDS
    | frozenset("accepted_item_count rejected_item_count ignored_proposal_count".split()),
    "evidence_checklist": _HISTORICAL_ATTEMPT_15_COMMON_CALL_FIELDS
    | frozenset("accepted_item_count rejected_item_count ignored_proposal_count".split()),
    "final_claim_brief_audit": _HISTORICAL_ATTEMPT_15_COMMON_CALL_FIELDS
    | frozenset("accepted_item_count rejected_item_count".split()),
}
_HISTORICAL_ATTEMPT_16_WARM_CALL_FIELDS = frozenset(
    "call_id orchestration_id agent_id parent_call_id delegation_id outcome "
    "cache_hit call_count "
    "origin_call_id response_id response_model upstream_provider finish_reason "
    "usage_source actual_cost_usd origin_usage origin_finish_reason "
    "created_at updated_at".split()
)
_HISTORICAL_ATTEMPT_17_FAILED_CALL_FIELDS = (
    _HISTORICAL_ATTEMPT_15_COMMON_CALL_FIELDS
    - frozenset("deterministic_fallback_applied".split())
    | frozenset(
        "error_type error_invariant authority_mode accepted_item_ids "
        "accepted_item_count rejected_items rejected_item_count "
        "ignored_proposal_count".split()
    )
)
_HISTORICAL_ATTEMPT_18_FAILED_CALL_FIELDS = (
    _HISTORICAL_ATTEMPT_15_COMMON_CALL_FIELDS
    | frozenset("semantic_scoring_started error_type error_invariant".split())
)
_HISTORICAL_ATTEMPT_18_PROCESS_CALL_FIELDS = (
    _HISTORICAL_ATTEMPT_15_CALL_FIELDS["process_decision_mapping"]
    | frozenset({"accepted_item_ids"})
)
_HISTORICAL_ATTEMPT_19_COLD_COMMON_CALL_FIELDS = frozenset(
    "call_id orchestration_id agent_id parent_call_id delegation_id call_count "
    "outcome response_id response_model upstream_provider finish_reason "
    "estimated_cost_usd actual_cost_usd prompt_tokens completion_tokens "
    "total_tokens usage_source latency_ms created_at updated_at "
    "deterministic_fallback_applied".split()
)
_HISTORICAL_ATTEMPT_19_COLD_CALL_FIELDS = {
    "canonical_facts": _HISTORICAL_ATTEMPT_19_COLD_COMMON_CALL_FIELDS
    | frozenset(
        "accepted_fact_count rejected_fact_count source_reference_projection_count "
        "ignored_noncontrolling_normalized_proposals".split()
    ),
    "orchestrator_plan": _HISTORICAL_ATTEMPT_19_COLD_COMMON_CALL_FIELDS
    | frozenset(
        "accepted_item_ids accepted_item_count rejected_items rejected_item_count "
        "ignored_proposal_count".split()
    ),
    "document_source_integrity": _HISTORICAL_ATTEMPT_19_COLD_COMMON_CALL_FIELDS
    | frozenset(
        "accepted_item_ids accepted_item_count rejected_items rejected_item_count "
        "ignored_proposal_count".split()
    ),
    "process_decision_mapping": _HISTORICAL_ATTEMPT_19_COLD_COMMON_CALL_FIELDS
    | frozenset(
        "accepted_item_ids accepted_item_count rejected_items rejected_item_count "
        "ignored_proposal_count".split()
    ),
    "evidence_checklist": _HISTORICAL_ATTEMPT_19_COLD_COMMON_CALL_FIELDS
    | frozenset(
        "accepted_item_ids accepted_item_count rejected_items rejected_item_count "
        "ignored_proposal_count".split()
    ),
    "final_claim_brief_audit": _HISTORICAL_ATTEMPT_19_COLD_COMMON_CALL_FIELDS
    | frozenset(
        "accepted_item_ids accepted_item_count rejected_items rejected_item_count".split()
    ),
}
_HISTORICAL_ATTEMPT_19_WARM_COMMON_CALL_FIELDS = frozenset(
    "call_id orchestration_id agent_id parent_call_id delegation_id outcome "
    "call_count origin_call_id response_id response_model upstream_provider "
    "finish_reason usage_source estimated_cost_usd actual_cost_usd origin_usage "
    "origin_finish_reason deterministic_fallback_applied created_at updated_at".split()
)
_HISTORICAL_ATTEMPT_19_WARM_CALL_FIELDS = {
    agent_id: _HISTORICAL_ATTEMPT_19_WARM_COMMON_CALL_FIELDS
    | (
        frozenset(
            "accepted_fact_count rejected_fact_count source_reference_projection_count "
            "ignored_noncontrolling_normalized_proposals".split()
        )
        if agent_id == "canonical_facts"
        else frozenset(
            "accepted_item_ids accepted_item_count rejected_items rejected_item_count".split()
        )
        | (
            frozenset({"ignored_proposal_count"})
            if agent_id != "final_claim_brief_audit"
            else frozenset()
        )
    )
    for agent_id in _HISTORICAL_ATTEMPT_19_COLD_CALL_FIELDS
}
_HISTORICAL_ATTEMPT_20_COLD_COMMON_CALL_FIELDS = (
    _HISTORICAL_ATTEMPT_19_COLD_COMMON_CALL_FIELDS
    | frozenset(
        "provider provider_endpoint model implementation agent_role cache_key purpose "
        "authority_mode".split()
    )
)
_HISTORICAL_ATTEMPT_20_COLD_CALL_FIELDS = {
    agent_id: (_HISTORICAL_ATTEMPT_20_COLD_COMMON_CALL_FIELDS | (fields - _HISTORICAL_ATTEMPT_19_COLD_COMMON_CALL_FIELDS))
    for agent_id, fields in _HISTORICAL_ATTEMPT_19_COLD_CALL_FIELDS.items()
}
_HISTORICAL_ATTEMPT_20_COLD_CALL_FIELDS["canonical_facts"] |= frozenset(
    "accepted_fact_ids rejected_facts source_reference_projection_fact_ids".split()
)
_HISTORICAL_ATTEMPT_20_WARM_COMMON_CALL_FIELDS = (
    _HISTORICAL_ATTEMPT_19_WARM_COMMON_CALL_FIELDS
    | frozenset(
        "provider provider_endpoint model implementation agent_role cache_key purpose "
        "authority_mode".split()
    )
)
_HISTORICAL_ATTEMPT_20_WARM_CALL_FIELDS = {
    agent_id: (_HISTORICAL_ATTEMPT_20_WARM_COMMON_CALL_FIELDS | (fields - _HISTORICAL_ATTEMPT_19_WARM_COMMON_CALL_FIELDS))
    for agent_id, fields in _HISTORICAL_ATTEMPT_19_WARM_CALL_FIELDS.items()
}
_HISTORICAL_ATTEMPT_20_WARM_CALL_FIELDS["canonical_facts"] |= frozenset(
    "accepted_fact_ids rejected_facts source_reference_projection_fact_ids".split()
)
_HISTORICAL_ATTEMPT_21_COLD_CALL_FIELDS = {
    agent_id: frozenset(fields)
    for agent_id, fields in _HISTORICAL_ATTEMPT_20_COLD_CALL_FIELDS.items()
}
_HISTORICAL_ATTEMPT_21_COLD_CALL_FIELDS["final_claim_brief_audit"] |= frozenset(
    {"ignored_proposal_count"}
)
_HISTORICAL_ATTEMPT_21_WARM_CALL_FIELDS = {
    agent_id: frozenset(fields)
    for agent_id, fields in _HISTORICAL_ATTEMPT_20_WARM_CALL_FIELDS.items()
}
_HISTORICAL_ATTEMPT_21_WARM_CALL_FIELDS["final_claim_brief_audit"] |= frozenset(
    {"ignored_proposal_count"}
)
_HISTORICAL_SOURCE_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_HISTORICAL_DEPLOY_ID_PATTERN = re.compile(r"^dep-[a-z0-9]{12,40}$")
_HISTORICAL_SERVICE_ID_PATTERN = re.compile(r"^srv-[a-z0-9]{12,40}$")
_HISTORICAL_RUN_ID_PATTERN = re.compile(r"^run_[0-9a-f]{16}$")
_HISTORICAL_ORCHESTRATION_ID_PATTERN = re.compile(r"^orch_[0-9a-f]{16}$")
_HISTORICAL_CALL_ID_PATTERN = re.compile(r"^modelcall_[0-9a-f]{16}$")
_HISTORICAL_DELEGATION_ID_PATTERN = re.compile(r"^dlg_[0-9a-f]{20}$")
_HISTORICAL_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_HISTORICAL_WORKSPACE_ID_PATTERN = re.compile(r"^tea-[a-z0-9]{12,40}$")
_HISTORICAL_ATTEMPT_14_SECTION_SHA256 = {
    "execution_observation": (
        "920a365975ec1fbc90c832477bdd32dc604ba0745b1accf24a0047e5a4da3120"
    ),
    "provider_observation": (
        "29c09cbdc10d106c86ce552ee80bf65f2f1559065f9aaae1c0718f2cb7ae0272"
    ),
    "application_result": (
        "a1c07368cfeeebda1adba483b1cbb8860b7a071eafd63a49de4d846ae64b5fd6"
    ),
    "capture_provenance": (
        "54bb3141a1cca99e610b2dd648671cc66e071cd11d11430c8cbd57f8841235ea"
    ),
}
_HISTORICAL_ATTEMPT_15_SECTION_SHA256 = {
    "execution_observation": (
        "b2aded93ddfebd441eb11a43e2c8a6b258965880244e4bcb63d3ddd8a62f2e7a"
    ),
    "provider_observation": (
        "978aa78d7bb250052c2491271039348de3c6c721bb646bd58b66311f3617e443"
    ),
    "application_result": (
        "fcfa4ab33da7041173bf9014c5ba4e9dfebb89abf14652c52b442b3580e08ab1"
    ),
    "qa_result": "b9f0f982d166ee162cfa7785b6a805297b79891ac3c7f05c200e149d8fc973bc",
    "capture_provenance": (
        "ee3d8467b2a7b3ed31a0291e609c2228df308f1055ebaa0e7ac7dcb891509bc4"
    ),
}
_HISTORICAL_ATTEMPT_16_SECTION_SHA256 = {
    "execution_observation": (
        "53af89277eec3069236dfa7c754294d6d81b3e85c8137c9fef5a4d505dcee6c0"
    ),
    "provider_observation": (
        "f72067c621204a7de3b24fae414bc88739c39286b973d36267b5417c75ecdc8f"
    ),
    "application_result": (
        "96d43d6fe0dbfbc2425a8005ccf77c257976c761b7b4abc7e444432e950b43ee"
    ),
    "warm_cache_result": (
        "71e80a0ca13b263dcba1e331fb7221aa9d34ea375a492238c7866c6eb06df0ad"
    ),
    "qa_result": "cdb0cdc0d051d5d1ef49a483ebfe8ba6a412a7406721b6f48d619d59d9cc80b1",
    "capture_provenance": (
        "213b8297b40a1019b82fb560c335ce48fc9a607357ed151674510fbc2f603d43"
    ),
}
_HISTORICAL_ATTEMPT_17_SECTION_SHA256 = {
    "execution_observation": (
        "69cc0a0858d6b8def005044541de65d56239ca1bcb144e6786294de455c72491"
    ),
    "provider_observation": (
        "1c7842ebdc2bb34d788ad2fdd441628ab475ed8618fa55a87ec3e1de24b9fbca"
    ),
    "application_result": (
        "61bfdec28dfac55c6954c12924edd15a3e37de51a033c59a6122b0c55e6cae9c"
    ),
    "capture_provenance": (
        "5926701a006f6d70065a5d2a7c2bc86c7832d197865b7973fbaf4f2ec6443e99"
    ),
}
_HISTORICAL_ATTEMPT_18_SECTION_SHA256 = {
    "execution_observation": (
        "8a52185caf3f5169f733fbdde605901a72e4c86438468c3e4ec1d48e43b3418b"
    ),
    "provider_observation": (
        "428e441df85a887bf5b7ab00f17851f5416445d4fba2ba7032e742f3f35a4ce1"
    ),
    "application_result": (
        "a7a8be4f7cdb5ad055623acbf3dc62fb12d35b5c2c6a3b4f13900fee1e83efa4"
    ),
    "capture_provenance": (
        "0e12018abd219f0ce8342d78362ed9645b3976333c1aa077e9625953e04ab01b"
    ),
}
_HISTORICAL_ATTEMPT_19_SECTION_SHA256 = {
    "execution_observation": (
        "b75afdf2f0d1f0f7e3a1c3d30e2b6a00917dbbdcf948050679b142711614d431"
    ),
    "provider_observation": (
        "920642ece2da89c485eb9be574b5329708d8d31ced1880ed739cfa27790e6361"
    ),
    "application_result": (
        "059a4c76f5edc1a643edeb7604c91451f66285d6c1bb1e79e41bef65cf174b14"
    ),
    "warm_cache_result": (
        "af925d99c6ca2fe031be9ec979187ebd71bc2ee40b6d327df7e108c8c928ab31"
    ),
    "qa_result": "c606d6b5f9e44d91ec9f4bde2de6323453f42e365514a9ee653a6453c1d95871",
    "capture_provenance": (
        "0570c7b4721e668f655b7d488b5bd21d092c56da200ce235750e72707f5cff58"
    ),
}
_HISTORICAL_ATTEMPT_20_SECTION_SHA256 = {
    "execution_observation": (
        "d187d20d066f2e84d78d668dd55fda99ae02edbcb972cc2e4ad1ebdf6da0ea96"
    ),
    "provider_observation": (
        "675f4d68d5e8564bc69cc0029a77ed3eccd7ac37677b3fa58d3e99c20facc7d7"
    ),
    "application_result": (
        "655b3bbd5fa5e67a3e4137bfae6507c53fd39f6f84a9140ca232b9338b0edcbe"
    ),
    "warm_cache_result": (
        "aaad0404659c09030c8132afc7eb756b8e83c278b5de3a722fa559f9d304afc0"
    ),
    "qa_result": "254f80b7f0d292330258564f837180bb2dae121ad2c7c349a0b2b64a78b45674",
    "capture_provenance": (
        "e7e870cef329e07cf71cfd1dbe39643126faade7f6ca667dd93d18824d20dd1e"
    ),
}
_HISTORICAL_ATTEMPT_21_SECTION_SHA256 = {
    "execution_observation": (
        "ca5abcfff1a1b4703ac443928c7f00ddaf85950c6615894ad7c396e02a2e8e63"
    ),
    "provider_observation": (
        "8732b07b96b00c1d0be7655ba9b2c86119002c4538c6101f58c8357f04831049"
    ),
    "application_result": (
        "da1d50dcd3b510915843a2128600640fc5798b07d956a827021fc5d71c84a06e"
    ),
    "warm_cache_result": (
        "35ba0cca51d69572ab1587e72d61b56e3f2bc57f72c3669b3440026dbbb0352a"
    ),
    "qa_result": "3548a82e805286611c26bf9a85642d94b68e32bbf53fb787ac28224eeabba5d1",
    "capture_provenance": (
        "a02d9a3f48b2af9c21feed103bf5b0bcbcc4d45cd1e62ec496c1b7ac0d1b02f2"
    ),
}
_HISTORICAL_ATTEMPT_22_SECTION_SHA256 = {
    "execution_observation": (
        "56f8f7dfc7d2f5ee8d9ded288591ec674dd328bba5d9e82a71aa3e8139139dcb"
    ),
    "provider_observation": (
        "f28f02f9a86163b908d5189bb29361e81747724e7121db182e4bea46cf1e23e3"
    ),
    "application_result": (
        "ea338067f7740d6d6c65812e93ec672d575206bba2d84ac6216faa7ced42affe"
    ),
    "warm_cache_result": (
        "ce155115ca9174ed671a32a413a478d7938ece5e2869342a419b6d4d28eadf5f"
    ),
    "qa_result": "2d93797fdcbc7ac3f8ce6bef53c84658d898b0749fd93d67da6e81fceee3198f",
    "capture_provenance": (
        "bb6742d67aebdbe8cb9ae5fb340bc2690d65671deb1e6ec0a0e7554a58934134"
    ),
}
_HISTORICAL_ATTEMPT_23_SECTION_SHA256 = {
    "execution_observation": (
        "3f127e63be33bd89af0db93d4e742680cbe97ad23dd01bad153beb7792d856aa"
    ),
    "provider_observation": (
        "2965544dd19e09b79e8cc581c6e414f326e3936a02c67c508de18b712e05ea0a"
    ),
    "application_result": (
        "c505321bd063ac737bdd58e7bdd4478c4e74d954c57d96423576cac2b94dabe6"
    ),
    "capture_provenance": (
        "256e44abde42250617deea5dc79fea6122bb396df77c40c5b286e1429a68aa89"
    ),
}
_HISTORICAL_ATTEMPT_24_SECTION_SHA256 = {
    "execution_observation": (
        "1c9d8aaf67389db8f078bcfd860f0ebf5c93356b3e15f96f38efe6f78798c7a6"
    ),
    "provider_observation": (
        "52d3093a6b560c13914d8ffbf9b84456ddaa1d3d0b17c1de00264c29d8d97c10"
    ),
    "application_result": (
        "0b5d61fca74f2cd7168ddbbfc4476da3464da4c86627efee9a96e8d3383a5071"
    ),
    "warm_cache_result": (
        "06252150022ef6a4ff8b8fce3619ea982df60b66891f2a1cf9b32556435b2119"
    ),
    "qa_result": "d29de0d6110fa3e61d72aad3489440b3ad799c1750aff9c23c1ab660e8ad3507",
    "capture_provenance": (
        "6034fa4ac68ced760c0dcb368ebd3ee862b63c16ae627125802043783ea3b667"
    ),
}
_HISTORICAL_ATTEMPT_17_EVIDENCE_ITEM_IDS = (
    "claim_message",
    "source_integrity",
    "lease",
    "policy_reference",
    "customer_objective",
    "management_position",
    "health_safety_statement",
    "defect_notice",
    "proof_of_delivery",
    "dated_photos",
    "recurrence_chronology",
    "technical_assessment",
    "moisture_measurements",
    "building_envelope",
    "repair_history",
    "use_evidence",
    "remediation_plan",
    "financial_impact",
    "settlement_proposal",
    "conciliation_bundle",
    "completion_record",
)
_HISTORICAL_LOCAL_TIME_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2} Europe/Zurich$"
)
REQUIRED_QA_JSON_EVIDENCE_FILES = (
    "deployment-identity.json",
    "release-contract.json",
    "readiness-receipt.json",
    "isolation-run.json",
    "isolation-model-ledger.json",
    "flagship-run.json",
    "flagship-cold-model-ledger.json",
    "demo-review.json",
    "post-review-run.json",
    "later-baseline-run.json",
    "later-after-memory-run.json",
    "learning-proof.json",
    "model-ledger.json",
    "runtime-versions.json",
    "flagship-cache-lineage.json",
)
REQUIRED_QA_SCREENSHOT_EVIDENCE_FILES = (
    "01-start-desktop.png",
    "02-ready-process-desktop.png",
    "03-lease-pdf-overview.png",
    "03-lease-pdf-detail.png",
    "03-lease-pdf-search.png",
    "03-image-inspection.png",
    "03-image-grounding-inspection.png",
    "04-review-desktop.png",
    "05-review-applied-desktop.png",
    "06-learning-desktop.png",
    "07-later-result-desktop.png",
    "final-state.png",
    "02-live-nemotron-agent.png",
    "03-deterministic-accepted-artifact.png",
)
REQUIRED_QA_VIDEO_EVIDENCE_FILE = "uninterrupted-focused-demo.webm"
REQUIRED_CAUSAL_QA_JSON_EVIDENCE_FILES = REQUIRED_QA_JSON_EVIDENCE_FILES[:-1]
REQUIRED_CAUSAL_QA_SCREENSHOT_EVIDENCE_FILES = (
    REQUIRED_QA_SCREENSHOT_EVIDENCE_FILES[:-2]
)
REQUIRED_CAUSAL_QA_RETAINED_SCREENSHOT_EVIDENCE_FILES = (
    *REQUIRED_QA_SCREENSHOT_EVIDENCE_FILES[:7],
    "final-state.png",
    *REQUIRED_QA_SCREENSHOT_EVIDENCE_FILES[7:11],
)
REQUIRED_CAUSAL_QA_PROVENANCE_EVIDENCE_FILES = (
    "api-runtime-boot-receipt.json",
    "browser-execution-receipt.json",
    "browser-network-boundary.json",
    "candidate-built-static-manifest.sha256",
    "candidate-source-manifest.sha256",
)
REQUIRED_CAUSAL_QA_RETAINED_JSON_EVIDENCE_FILES = (
    "candidate-built-static-manifest.sha256",
    "candidate-source-manifest.sha256",
    "deployment-identity.json",
    "release-contract.json",
    "readiness-receipt.json",
    "isolation-run.json",
    "isolation-model-ledger.json",
    "flagship-run.json",
    "flagship-cold-model-ledger.json",
    "model-ledger.json",
    "runtime-versions.json",
    "browser-execution-receipt.json",
    "browser-network-boundary.json",
    "api-runtime-boot-receipt.json",
    "demo-review.json",
    "post-review-run.json",
    "later-baseline-run.json",
    "later-after-memory-run.json",
    "learning-proof.json",
)
REQUIRED_CAUSAL_QA_EVIDENCE_FILES = frozenset(
    (
        *REQUIRED_CAUSAL_QA_JSON_EVIDENCE_FILES,
        *REQUIRED_CAUSAL_QA_SCREENSHOT_EVIDENCE_FILES,
        *REQUIRED_CAUSAL_QA_PROVENANCE_EVIDENCE_FILES,
        REQUIRED_QA_VIDEO_EVIDENCE_FILE,
    )
)
REQUIRED_QA_EVIDENCE_FILES = frozenset(
    (
        *REQUIRED_QA_JSON_EVIDENCE_FILES,
        *REQUIRED_QA_SCREENSHOT_EVIDENCE_FILES,
        REQUIRED_QA_VIDEO_EVIDENCE_FILE,
    )
)

BASE_PROCESS_NODE_IDS = (
    "intake",
    "scope",
    "dispute",
    "urgency",
    "notification",
    "defect",
    "causation",
    "responsibility",
    "remedy",
    "escalation",
    "resolution",
    "out_of_scope",
    "no_dispute",
    "urgent_escalation",
    "formal_notice",
    "building_defect",
    "tenant_use",
    "mixed_cause",
    "evidence_gap",
)
BASE_PROCESS_EDGE_PAIRS = (
    ("intake", "scope"),
    ("scope", "dispute"),
    ("scope", "out_of_scope"),
    ("dispute", "urgency"),
    ("dispute", "no_dispute"),
    ("urgency", "urgent_escalation"),
    ("urgency", "notification"),
    ("notification", "defect"),
    ("notification", "formal_notice"),
    ("defect", "causation"),
    ("causation", "building_defect"),
    ("causation", "tenant_use"),
    ("causation", "mixed_cause"),
    ("causation", "evidence_gap"),
    ("evidence_gap", "causation"),
    ("building_defect", "responsibility"),
    ("tenant_use", "responsibility"),
    ("mixed_cause", "responsibility"),
    ("responsibility", "remedy"),
    ("remedy", "resolution"),
    ("remedy", "escalation"),
    ("escalation", "resolution"),
)
VISUAL_ANNOTATION_CONTRACT = "casepath.visual-reference-annotation/1.0.0"
VISUAL_ANNOTATION_VERSION = "generated-demo-reference/2026-08-12"
VISUAL_ANNOTATION_PRODUCER = "deterministic_reference_annotation"
VISUAL_ANNOTATION_AUTHORITY = "generated_demo_reference_only"
RELEASE_VISUAL_IMAGE_SHA256_BY_ARTIFACT = {
    "art_photo": "b8de375c0a951e3970f4b4a392b5af348ea35b30f5750974fa1d9411da179860",
}
RELEASE_LAW_CONTRACT = "casepath.legal-context/2.0.0"
RELEASE_LAW_REGISTRY_VERSION = "ch-tenancy-official-snapshot/2026-08-12"
RELEASE_LAW_SOURCE_CONTRACTS = {
    "fedlex-or-256": {
        "passage_sha256": (
            "100d0abd42d621949be8a6e4953b0de6f46bf13cea78b46921cef6f6725f53f9"
        ),
        "snapshot_sha256": (
            "6a958ae86cf67f71b1d36b798775b1659f06a9f0130fb9649f6ef045ce409966"
        ),
        "snapshot_scope": "official_pdf_bytes",
    },
    "fedlex-or-257g": {
        "passage_sha256": (
            "ab9316ed8dada48c26b63f566492bd4fdb1bd271b46c3305e6ebde78ca61a268"
        ),
        "snapshot_sha256": (
            "6a958ae86cf67f71b1d36b798775b1659f06a9f0130fb9649f6ef045ce409966"
        ),
        "snapshot_scope": "official_pdf_bytes",
    },
    "fedlex-or-259a": {
        "passage_sha256": (
            "c3f25dae4586691caedb9ad49e256bcc80b28dc92d51d5df76bd3dc6197e8605"
        ),
        "snapshot_sha256": (
            "6a958ae86cf67f71b1d36b798775b1659f06a9f0130fb9649f6ef045ce409966"
        ),
        "snapshot_scope": "official_pdf_bytes",
    },
    "bwo-conciliation": {
        "passage_sha256": (
            "27700e4ed06b60510b992676823c44d9a11aefb94192fdc3bec872df1c843af6"
        ),
        "snapshot_sha256": (
            "27700e4ed06b60510b992676823c44d9a11aefb94192fdc3bec872df1c843af6"
        ),
        "snapshot_scope": "normalized_official_passage_utf8",
    },
}
RELEASE_LAW_NODE_LINKS = {
    "scope": ["fedlex-or-256"],
    "defect": ["fedlex-or-256"],
    "building_defect": ["fedlex-or-256", "fedlex-or-259a"],
    "notification": ["fedlex-or-257g"],
    "formal_notice": ["fedlex-or-257g"],
    "causation": [
        "fedlex-or-256",
        "handling-causation",
        "handling-evidence-order",
    ],
    "responsibility": [
        "fedlex-or-256",
        "handling-causation",
        "handling-evidence-order",
        "fedlex-or-259a",
    ],
    "evidence_gap": [
        "fedlex-or-256",
        "handling-causation",
        "handling-evidence-order",
    ],
    "remedy": ["fedlex-or-259a"],
    "escalation": ["bwo-conciliation"],
}
RELEASE_LAW_QUESTION_JOINS = {
    "tenancy_scope_and_fitness": {
        "source_ids": ["fedlex-or-256"],
        "interpretation_ids": [],
        "process_node_ids": ["scope", "defect", "building_defect"],
    },
    "defect_notification": {
        "source_ids": ["fedlex-or-257g"],
        "interpretation_ids": [],
        "process_node_ids": ["notification", "formal_notice"],
    },
    "causation_before_responsibility": {
        "source_ids": ["fedlex-or-256"],
        "interpretation_ids": [
            "handling-causation",
            "handling-evidence-order",
        ],
        "process_node_ids": ["causation", "responsibility", "evidence_gap"],
    },
    "defect_remedies": {
        "source_ids": ["fedlex-or-259a"],
        "interpretation_ids": [],
        "process_node_ids": ["building_defect", "responsibility", "remedy"],
    },
    "conciliation_route": {
        "source_ids": ["bwo-conciliation"],
        "interpretation_ids": [],
        "process_node_ids": ["escalation"],
    },
}

CANONICAL_FACT_FIELDS = {
    "fact_id",
    "label",
    "value",
    "state",
    "explanation",
    "source_refs",
    "confidence",
    "controls_process",
    "decision_key",
    "normalized_value",
    "decision_value",
    "semantic_role",
}
SEMANTIC_MEMORY_ROLE = "management_ventilation_allegation"
VISUAL_REFERENCE_FIELDS = {
    "artifact_id",
    "locator_kind",
    "region",
    "observation",
    "producer",
    "authority",
    "annotation_contract",
    "annotation_version",
    "image_sha256",
}
REQUIRED_PLAYBOOK_CHECKS = REQUIRED_PLAYBOOK_CHECK_NAMES
REQUIRED_LEARNING_CHECKS = (
    "Same observable input",
    "Same canonical state",
    "Exact current memory receipt",
    "Pure memory replay matches learned DTOs",
    "Receipt before semantic hashes match baseline DTOs",
    "Receipt after hashes match learned DTOs",
    "Nonzero causal DTO delta",
    "Only allowed causal operations changed",
    "Deterministic target and protected checks passed",
    "Shared v3 remains unchanged",
)
MEMORY_OPERATION_IDS = (
    "add_ventilation_dispute_node",
    "add_evidence_gap_to_ventilation_edge",
    "add_ventilation_to_causation_edge",
    "condition_building_envelope",
    "reassign_use_evidence_to_ventilation",
)
MEMORY_BOUNDARY_CONTRACT = "casepath.memory-application-boundary/1.0.0"
MEMORY_REQUIRED_DECISIONS = {
    "scope": "in_scope",
    "dispute": "dispute_present",
    "urgency": "not_urgent",
    "notification": "notified",
    "recurrence": "recurrence_supported",
    "causation": "cause_unresolved",
}
MEMORY_REQUIRED_FACT_ROLES = {
    SEMANTIC_MEMORY_ROLE: {"state": "known", "min_grounded_sources": 1}
}
EVIDENCE_LEGAL_BASIS_IDS = {
    "claim_message": [],
    "source_integrity": [],
    "lease": ["fedlex-or-256"],
    "policy_reference": [],
    "customer_objective": [],
    "management_position": [],
    "health_safety_statement": [],
    "defect_notice": ["fedlex-or-257g"],
    "proof_of_delivery": ["fedlex-or-257g"],
    "dated_photos": [],
    "recurrence_chronology": [],
    "technical_assessment": ["fedlex-or-256", "handling-causation"],
    "moisture_measurements": ["handling-causation"],
    "building_envelope": ["handling-evidence-order"],
    "use_evidence": [],
    "repair_history": ["fedlex-or-256"],
    "remediation_plan": ["fedlex-or-259a"],
    "financial_impact": ["fedlex-or-259a"],
    "settlement_proposal": ["fedlex-or-259a"],
    "conciliation_bundle": ["bwo-conciliation"],
    "completion_record": [],
}
RELEASE_PROCESS_FACT_IDS_BY_CLAIM = {
    "DEF-027-E0-DEMO": {
        "intake": [],
        "scope": ["fact_tenancy"],
        "dispute": ["fact_dispute"],
        "urgency": ["fact_health"],
        "notification": ["fact_notification"],
        "defect": ["fact_recurrence"],
        "causation": ["fact_cause", "fact_ventilation_allegation"],
        "responsibility": [],
        "remedy": [],
        "escalation": [],
        "resolution": [],
        "out_of_scope": [],
        "no_dispute": [],
        "urgent_escalation": [],
        "formal_notice": [],
        "building_defect": [],
        "tenant_use": [],
        "mixed_cause": [],
        "evidence_gap": [],
    },
    "DEMO-MOULD-002": {
        "intake": [],
        "scope": ["later_fact_tenancy"],
        "dispute": ["later_fact_dispute"],
        "urgency": ["later_fact_health"],
        "notification": ["later_fact_notification"],
        "defect": ["later_fact_recurrence", "later_fact_recent_window_work"],
        "causation": [
            "later_fact_cause",
            "later_fact_ventilation_allegation",
            "later_fact_recent_window_work",
        ],
        "responsibility": [],
        "remedy": [],
        "escalation": [],
        "resolution": [],
        "out_of_scope": [],
        "no_dispute": [],
        "urgent_escalation": [],
        "formal_notice": [],
        "building_defect": [],
        "tenant_use": [],
        "mixed_cause": [],
        "evidence_gap": [],
    },
}
RELEASE_EVIDENCE_FACT_ID_BY_CLAIM = {
    "DEF-027-E0-DEMO": {
        "claim_message": "fact_customer_objective",
        "source_integrity": "fact_source_integrity",
        "lease": "fact_tenancy",
        "policy_reference": "fact_policy_route",
        "customer_objective": "fact_customer_objective",
        "management_position": "fact_dispute",
        "health_safety_statement": "fact_health",
        "defect_notice": "fact_notification",
        "proof_of_delivery": "fact_notification",
        "dated_photos": "fact_recurrence",
        "recurrence_chronology": "fact_date_conflict",
        "technical_assessment": "fact_cause",
        "moisture_measurements": "fact_cause",
        "building_envelope": "fact_cause",
        "repair_history": "fact_repair_history",
        "use_evidence": "fact_tenant_use_cause",
        "remediation_plan": "fact_remedy_plan",
        "financial_impact": "fact_financial_remedy",
        "settlement_proposal": "fact_settlement_proposal",
        "conciliation_bundle": "fact_escalation_ready",
        "completion_record": "fact_resolution_complete",
    },
    "DEMO-MOULD-002": {
        "claim_message": "later_fact_customer_objective",
        "source_integrity": "later_fact_source_integrity",
        "lease": "later_fact_tenancy",
        "policy_reference": "later_fact_policy_route",
        "customer_objective": "later_fact_customer_objective",
        "management_position": "later_fact_dispute",
        "health_safety_statement": "later_fact_health",
        "defect_notice": "later_fact_notification",
        "proof_of_delivery": "later_fact_notification",
        "dated_photos": "later_fact_recurrence",
        "recurrence_chronology": "later_fact_recurrence",
        "repair_history": "later_fact_recent_window_work",
        "technical_assessment": "later_fact_cause",
        "moisture_measurements": "later_fact_cause",
        "building_envelope": "later_fact_cause",
        "use_evidence": "later_fact_ventilation_allegation",
        "remediation_plan": "later_fact_remedy_plan",
        "financial_impact": "later_fact_financial_remedy",
        "settlement_proposal": "later_fact_settlement_proposal",
        "conciliation_bundle": "later_fact_escalation_ready",
        "completion_record": "later_fact_resolution_complete",
    },
}
RELEASE_EVIDENCE_ARTIFACT_IDS_BY_CLAIM = {
    "DEF-027-E0-DEMO": {
        "claim_message": ["message"],
        "source_integrity": [
            "art_lease",
            "art_notification",
            "art_management_reply",
            "art_photo",
            "art_timeline",
            "art_delivery",
        ],
        "lease": ["art_lease"],
        "policy_reference": ["intake"],
        "customer_objective": ["message"],
        "management_position": ["art_management_reply"],
        "health_safety_statement": ["message"],
        "defect_notice": ["art_notification"],
        "proof_of_delivery": ["art_delivery"],
        "dated_photos": ["art_photo"],
        "recurrence_chronology": ["art_timeline"],
        "technical_assessment": [],
        "moisture_measurements": [],
        "building_envelope": [],
        "repair_history": ["art_management_reply"],
        "use_evidence": [],
        "remediation_plan": [],
        "financial_impact": [],
        "settlement_proposal": [],
        "conciliation_bundle": [],
        "completion_record": [],
    },
    "DEMO-MOULD-002": {
        "claim_message": ["art_later_email"],
        "source_integrity": [
            "art_later_email",
            "art_later_photo",
            "art_window_notice",
            "art_later_lease",
            "art_later_notification",
            "art_later_management_reply",
        ],
        "lease": ["art_later_lease"],
        "policy_reference": ["intake"],
        "customer_objective": ["art_later_email"],
        "management_position": ["art_later_management_reply"],
        "health_safety_statement": ["art_later_email"],
        "defect_notice": ["art_later_notification"],
        "proof_of_delivery": ["art_later_management_reply"],
        "dated_photos": ["art_later_photo"],
        "recurrence_chronology": [
            "art_later_notification",
            "art_later_photo",
        ],
        "repair_history": ["art_window_notice"],
        "technical_assessment": [],
        "moisture_measurements": [],
        "building_envelope": [],
        "use_evidence": [],
        "remediation_plan": [],
        "financial_impact": [],
        "settlement_proposal": [],
        "conciliation_bundle": [],
        "completion_record": [],
    },
}
RELEASE_BASE_EVIDENCE_STATUS_BY_CLAIM = {
    "DEF-027-E0-DEMO": {
        "claim_message": "provided_sufficient",
        "source_integrity": "provided_sufficient",
        "lease": "provided_sufficient",
        "policy_reference": "provided_sufficient",
        "customer_objective": "provided_sufficient",
        "management_position": "provided_sufficient",
        "health_safety_statement": "provided_sufficient",
        "defect_notice": "provided_sufficient",
        "proof_of_delivery": "provided_sufficient",
        "dated_photos": "provided_sufficient",
        "recurrence_chronology": "provided_insufficient",
        "technical_assessment": "missing",
        "moisture_measurements": "conditional",
        "building_envelope": "conditional",
        "repair_history": "conditional",
        "use_evidence": "not_applicable",
        "remediation_plan": "not_applicable",
        "financial_impact": "conditional",
        "settlement_proposal": "conditional",
        "conciliation_bundle": "conditional",
        "completion_record": "not_applicable",
    },
    "DEMO-MOULD-002": {
        "claim_message": "provided_sufficient",
        "source_integrity": "provided_sufficient",
        "lease": "provided_sufficient",
        "policy_reference": "provided_sufficient",
        "customer_objective": "provided_sufficient",
        "management_position": "provided_sufficient",
        "health_safety_statement": "provided_sufficient",
        "defect_notice": "provided_sufficient",
        "proof_of_delivery": "provided_sufficient",
        "dated_photos": "provided_sufficient",
        "recurrence_chronology": "provided_insufficient",
        "repair_history": "provided_sufficient",
        "technical_assessment": "missing",
        "moisture_measurements": "conditional",
        "building_envelope": "missing",
        "use_evidence": "conditional",
        "remediation_plan": "not_applicable",
        "financial_impact": "conditional",
        "settlement_proposal": "conditional",
        "conciliation_bundle": "conditional",
        "completion_record": "not_applicable",
    },
}
RELEASE_SEMANTIC_FACT_ID_BY_CLAIM = {
    "DEF-027-E0-DEMO": {
        SEMANTIC_MEMORY_ROLE: "fact_ventilation_allegation"
    },
    "DEMO-MOULD-002": {
        SEMANTIC_MEMORY_ROLE: "later_fact_ventilation_allegation"
    },
}

SOURCE_ROOTS = ("casepath", "casepath-api", "casepath-qa", "docs", "examples")
EXTRA_SOURCE_FILES = (
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "bin/casepath",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "THIRD_PARTY_NOTICES.md",
    "CASEPATH_MASTER_KNOWLEDGE_TRANSFER.md",
)
SOURCE_EXCLUSIONS = {
    "casepath/deployment.json",
    "casepath/source-manifest.json",
}
OBSOLETE_CLAIM_IDS = {
    "BS-DEF-2026-041",
    "BS-RENT-2026-073",
    "BS-TERM-2026-088",
}
OBSOLETE_ACTIVE_MARKERS = {
    "later-window-condensation-2026-08-12.jpg",
    "2026-08-14T09:46:00Z",
    "Fri, 14 Aug 2026 09:46:00 +0200",
    "20260814-094600-SK",
    "Source photograph dated 12 August 2026.",
}
ACTIVE_SCENARIO_FILES = (
    "casepath/release.json",
    "casepath-api/generate_artifacts.py",
    "casepath-api/prepare_runtime_v12.py",
    "casepath-api/replace_photographic_evidence.py",
    "casepath-api/render-build.sh",
    "casepath-api/casepath_api/data.py",
)
EXPECTED_ARTIFACTS = {
    "bedroom-corner-2026-07-27.jpg",
    "defect-timeline.pdf",
    "delivery-receipt.pdf",
    "later-claim-email.eml",
    "later-lease-agreement.pdf",
    "later-management-reply.eml",
    "later-notification-email.eml",
    "window-corner-2026-08-08.jpg",
    "lease-agreement.pdf",
    "management-reply.eml",
    "notification-email.eml",
    "window-replacement-notice.pdf",
}
MODEL_VISIBLE_FILES = EXPECTED_ARTIFACTS
MODEL_VISIBLE_PREFIXES = ("pages/",)
SOURCE_ASSET_HASHES = {
    "casepath-api/source-assets/flagship-bedroom-corner.png":
        "70645bf156c85d3d6f8117aaa94fe359f3e685c5576173bc0037dd3452dfd65e",
    "casepath-api/source-assets/later-window-condensation.png":
        "ab2e71da9706f8dcf54a65fae5d6dbab65f4790c708b0f05996b75e80a0fbff8",
}

LEAKAGE_PATTERNS = {
    "generated": re.compile(r"\bgenerated\b", re.IGNORECASE),
    "fictional": re.compile(r"\bfictional\b", re.IGNORECASE),
    "sample": re.compile(r"\bsample\b", re.IGNORECASE),
    "dummy": re.compile(r"\bdummy\b", re.IGNORECASE),
    "benchmark": re.compile(r"\bbenchmark\b", re.IGNORECASE),
    "demo": re.compile(r"\bdemo\b", re.IGNORECASE),
    "casepath": re.compile(r"\bcasepath\b", re.IGNORECASE),
    "hidden_label": re.compile(r"\bhidden[ _-]+labels?\b", re.IGNORECASE),
    "ground_truth": re.compile(r"\bground[ _-]+truths?\b", re.IGNORECASE),
    "expected_action": re.compile(r"\bexpected[ _-]+actions?\b", re.IGNORECASE),
    "reference_answer": re.compile(r"\breference[ _-]+answers?\b", re.IGNORECASE),
    "scenario_template": re.compile(r"\bscenario[ _-]+templates?\b", re.IGNORECASE),
    "example_domain": re.compile(r"(?:\.example\b|\bexample\.(?:com|net|org|test)\b)", re.IGNORECASE),
}


class VerificationError(RuntimeError):
    """Raised when a release invariant is not satisfied."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(REPOSITORY).as_posix()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    os.utime(path, (SOURCE_DATE_EPOCH, SOURCE_DATE_EPOCH))


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"Cannot read valid JSON from {relative(path)}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"Expected an object in {relative(path)}")
    return value


def exact_git_worktree() -> bool:
    try:
        top_level = subprocess.check_output(
            ["git", "-C", str(REPOSITORY), "rev-parse", "--show-toplevel"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return False
    try:
        return Path(top_level).resolve(strict=True) == REPOSITORY.resolve(strict=True)
    except OSError:
        return False


def _manifest_archive_inventory() -> list[str]:
    try:
        manifest = json.loads(SOURCE_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(
            "Source archive has no valid immutable source manifest"
        ) from exc
    expected_keys = {
        "artifact_manifest",
        "contract",
        "file_count",
        "files",
        "gate_count",
        "gates",
        "inventory_policy",
        "release_id",
    }
    if not isinstance(manifest, dict) or set(manifest) != expected_keys:
        raise VerificationError("Source archive manifest schema is not closed")
    files = manifest.get("files")
    if manifest.get("contract") != "casepath.source-manifest/2.1.0" or not isinstance(files, list):
        raise VerificationError("Source archive manifest contract is invalid")
    paths: list[str] = []
    for row in files:
        if not isinstance(row, dict) or set(row) != {"executable", "path", "sha256", "size_bytes"}:
            raise VerificationError("Source archive file row schema is not closed")
        path_text = row.get("path")
        if (
            not isinstance(path_text, str)
            or not path_text
            or "\\" in path_text
            or Path(path_text).is_absolute()
            or Path(path_text).as_posix() != path_text
            or any(part in {"", ".", ".."} for part in Path(path_text).parts)
        ):
            raise VerificationError("Source archive manifest contains a noncanonical path")
        allowed = path_text in EXTRA_SOURCE_FILES or any(
            path_text == root or path_text.startswith(f"{root}/")
            for root in SOURCE_ROOTS
        )
        if not allowed or path_text in SOURCE_EXCLUSIONS or path_text.startswith("casepath-api/artifacts/"):
            raise VerificationError(f"Source archive manifest path is outside its policy: {path_text}")
        path = REPOSITORY / path_text
        try:
            mode = path.lstat().st_mode
        except OSError as exc:
            raise VerificationError(f"Source archive file is absent: {path_text}") from exc
        if path.is_symlink() or not stat.S_ISREG(mode):
            raise VerificationError(f"Source archive path is not a regular file: {path_text}")
        actual = source_file_record(path_text)
        if actual != row:
            raise VerificationError(f"Source archive file identity diverged: {path_text}")
        paths.append(path_text)
    if (
        len(paths) != len(set(paths))
        or paths != sorted(paths)
        or manifest.get("file_count") != len(paths)
    ):
        raise VerificationError("Source archive manifest roster is duplicate, unordered, or miscounted")
    actual_paths: list[str] = []
    for root in SOURCE_ROOTS:
        root_path = REPOSITORY / root
        if root_path.is_symlink() or not root_path.is_dir():
            raise VerificationError(f"Source archive root is invalid: {root}")
        for candidate in sorted(root_path.rglob("*")):
            path_text = candidate.relative_to(REPOSITORY).as_posix()
            if candidate.is_symlink():
                raise VerificationError(f"Source archive contains a symlink: {path_text}")
            if candidate.is_dir():
                continue
            if not candidate.is_file():
                raise VerificationError(f"Source archive contains a special file: {path_text}")
            if (
                path_text in SOURCE_EXCLUSIONS
                or path_text.startswith("casepath-api/artifacts/")
                or "__pycache__" in candidate.parts
                or candidate.suffix in {".pyc", ".pyo"}
            ):
                continue
            actual_paths.append(path_text)
    for path_text in EXTRA_SOURCE_FILES:
        path = REPOSITORY / path_text
        if path.is_symlink() or not path.is_file():
            raise VerificationError(f"Source archive extra file is invalid: {path_text}")
        actual_paths.append(path_text)
    if sorted(actual_paths) != paths:
        missing = sorted(set(paths) - set(actual_paths))
        extra = sorted(set(actual_paths) - set(paths))
        raise VerificationError(
            f"Source archive roster diverged; missing={missing}, extra={extra}"
        )
    return paths


def git_inventory() -> list[str]:
    if not exact_git_worktree():
        return _manifest_archive_inventory()
    command = [
        "git",
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "--",
        *SOURCE_ROOTS,
        *EXTRA_SOURCE_FILES,
    ]
    try:
        output = subprocess.check_output(command, cwd=REPOSITORY, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise VerificationError(f"Unable to inventory repository files: {exc}") from exc

    paths: list[str] = []
    for candidate in output.splitlines():
        normalized = Path(candidate).as_posix()
        if normalized in SOURCE_EXCLUSIONS:
            continue
        if normalized.startswith("casepath-api/artifacts/"):
            continue
        full_path = REPOSITORY / normalized
        if full_path.is_file():
            paths.append(normalized)
    return sorted(set(paths))


def source_file_record(path_text: str) -> dict[str, Any]:
    path = REPOSITORY / path_text
    mode = path.stat().st_mode
    return {
        "executable": bool(mode & stat.S_IXUSR),
        "path": path_text,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def verify_static_deployment_identity() -> dict[str, Any]:
    """Bind the generated public deployment identity to release authority.

    ``casepath-public/deployment.json`` is generated rather than authored and is
    therefore intentionally absent from the source-file roster.  Release
    generation must still verify its exact bytes before minting the content
    address; otherwise an unknown-commit build and a known-commit build can
    collide on one source-manifest identity.
    """

    expected = build_deployment_identity.build_payload(os.environ)
    if expected.get("alignment_eligible") is not True:
        raise VerificationError(
            "Static deployment identity requires an exact known source commit"
        )
    if not STATIC_DEPLOYMENT_PATH.is_file() or STATIC_DEPLOYMENT_PATH.is_symlink():
        raise VerificationError(
            "Curated static deployment identity is not a regular file"
        )
    actual = load_json(STATIC_DEPLOYMENT_PATH)
    if actual != expected:
        raise VerificationError(
            "Curated static deployment identity differs from source/release authority"
        )
    return actual


def is_gate(path_text: str) -> bool:
    path = Path(path_text)
    return (
        path_text.startswith("casepath-qa/")
        and path.suffix in {".mjs", ".py"}
        and path.name.startswith(("browser-", "check-", "reset-", "patch_"))
    )


def is_model_visible(path_text: str) -> bool:
    return path_text in MODEL_VISIBLE_FILES or path_text.startswith(MODEL_VISIBLE_PREFIXES)


def scan_text(surface: str, text: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for marker, pattern in LEAKAGE_PATTERNS.items():
        match = pattern.search(text)
        if match:
            start = max(0, match.start() - 32)
            end = min(len(text), match.end() + 32)
            context = " ".join(text[start:end].split())
            findings.append({"marker": marker, "surface": surface, "context": context})
    return findings


def artifact_surfaces(path: Path) -> Iterable[tuple[str, str]]:
    yield "filename", path.name
    raw = path.read_bytes()
    yield "raw_bytes", raw.decode("latin-1", errors="ignore")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(path)
        metadata = reader.metadata or {}
        for key, value in metadata.items():
            yield f"pdf_metadata:{key}", str(value)
        for index, page in enumerate(reader.pages, start=1):
            yield f"pdf_page:{index}", page.extract_text() or ""
    elif suffix == ".eml":
        message = BytesParser(policy=policy.default).parsebytes(raw)
        for key, value in message.items():
            yield f"email_header:{key}", str(value)
        body = message.get_body(preferencelist=("plain",))
        if body is not None:
            yield "email_body", body.get_content()
    elif suffix in {".jpg", ".jpeg", ".png"}:
        with Image.open(path) as image:
            yield "image_info", json.dumps(image.info, sort_keys=True, default=str)
            exif = image.getexif()
            if exif:
                yield "image_exif", json.dumps(dict(exif), sort_keys=True, default=str)


def scan_artifact(path: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for surface, text in artifact_surfaces(path):
        findings.extend(scan_text(surface, text))
    return findings


def media_type(path: Path) -> str:
    if path.suffix.lower() == ".eml":
        return "message/rfc822"
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def verify_source_assets() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path_text, expected_sha in sorted(SOURCE_ASSET_HASHES.items()):
        path = REPOSITORY / path_text
        if not path.is_file():
            raise VerificationError(f"Missing source image: {path_text}")
        actual_sha = sha256_file(path)
        if actual_sha != expected_sha:
            raise VerificationError(
                f"Source image hash mismatch for {path_text}: expected {expected_sha}, got {actual_sha}"
            )
        with Image.open(path) as image:
            records.append({
                "dimensions": [image.width, image.height],
                "path": path_text,
                "sha256": actual_sha,
            })
    return records


def verify_runtime_jpeg_metadata(path: Path) -> None:
    with Image.open(path) as image:
        if image.format != "JPEG":
            raise VerificationError(f"Runtime image is not JPEG: {relative(path)}")
        if image.getexif():
            raise VerificationError(f"Runtime image retains EXIF metadata: {relative(path)}")
        forbidden_keys = {"comment", "exif", "icc_profile", "photoshop"}.intersection(image.info)
        if forbidden_keys:
            raise VerificationError(
                f"Runtime image retains metadata {sorted(forbidden_keys)}: {relative(path)}"
            )


def build_artifact_manifest() -> dict[str, Any]:
    if not ARTIFACT_ROOT.is_dir():
        raise VerificationError("Artifact directory does not exist; run the artifact generators first")

    source_assets = verify_source_assets()
    files: list[dict[str, Any]] = []
    discovered_primary: set[str] = set()
    for path in sorted(ARTIFACT_ROOT.rglob("*")):
        if not path.is_file() or path == ARTIFACT_MANIFEST_PATH:
            continue
        path_text = path.relative_to(ARTIFACT_ROOT).as_posix()
        visible = is_model_visible(path_text)
        if path_text in EXPECTED_ARTIFACTS:
            discovered_primary.add(path_text)
        if path.suffix.lower() in {".jpg", ".jpeg"} and visible:
            verify_runtime_jpeg_metadata(path)
        findings = scan_artifact(path) if visible else []
        if findings:
            raise VerificationError(
                f"Model-visible leakage in {path_text}: {json.dumps(findings, ensure_ascii=False)}"
            )
        if int(path.stat().st_mtime) != SOURCE_DATE_EPOCH:
            raise VerificationError(
                f"Non-deterministic filesystem timestamp for {path_text}: "
                f"expected {SOURCE_DATE_EPOCH}, got {int(path.stat().st_mtime)}"
            )
        files.append({
            "leakage_scan": "passed" if visible else "not_model_visible",
            "media_type": media_type(path),
            "model_visible": visible,
            "path": path_text,
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        })

    missing = sorted(EXPECTED_ARTIFACTS - discovered_primary)
    unexpected = sorted(discovered_primary - EXPECTED_ARTIFACTS)
    if missing or unexpected:
        raise VerificationError(f"Artifact set mismatch: missing={missing}, unexpected={unexpected}")

    return {
        "contract": "casepath.artifact-manifest/1.0.0",
        "file_count": len(files),
        "files": files,
        "leakage_policy": {
            "markers": sorted(LEAKAGE_PATTERNS),
            "model_visible_files_scanned": sum(1 for item in files if item["model_visible"]),
            "status": "passed",
            "surfaces": [
                "raw bytes",
                "PDF extracted text and metadata",
                "email headers and body",
                "image metadata",
            ],
        },
        "release_id": load_json(RELEASE_PATH)["release_id"],
        "source_assets": source_assets,
        "source_date_epoch": SOURCE_DATE_EPOCH,
    }


def source_manifest_payload() -> dict[str, Any]:
    verify_static_deployment_identity()
    release = load_json(RELEASE_PATH)
    paths = git_inventory()
    files = [source_file_record(path) for path in paths]
    gates = [
        {"path": item["path"], "sha256": item["sha256"]}
        for item in files
        if is_gate(item["path"])
    ]

    artifact_manifest = load_json(ARTIFACT_MANIFEST_PATH)
    model_visible_artifacts = [
        {"path": item["path"], "sha256": item["sha256"]}
        for item in artifact_manifest["files"]
        if item["model_visible"]
    ]
    return {
        "artifact_manifest": {
            "model_visible_files": model_visible_artifacts,
            "path": relative(ARTIFACT_MANIFEST_PATH),
            "sha256": sha256_file(ARTIFACT_MANIFEST_PATH),
        },
        "contract": "casepath.source-manifest/2.1.0",
        "file_count": len(files),
        "files": files,
        "gate_count": len(gates),
        "gates": gates,
        "inventory_policy": {
            "includes_nonignored_pending_files": True,
            "roots": [*SOURCE_ROOTS, *EXTRA_SOURCE_FILES],
            "self_output_excluded": relative(SOURCE_MANIFEST_PATH),
        },
        "release_id": release["release_id"],
    }


def expected_agentic_runtime() -> dict[str, Any]:
    """Return the exact production architecture claimed by this release."""

    return {
        "runtime_profile": REQUIRED_RUNTIME_PROFILE,
        "execution_mode": REQUIRED_PRODUCTION_MODE,
        "provider": "openrouter",
        "model": REQUIRED_PRODUCTION_MODEL,
        "orchestration_schema": REQUIRED_ORCHESTRATION_SCHEMA,
        "authority_mode": REQUIRED_AUTHORITY_MODE,
        "implementation": REQUIRED_AGENT_IMPLEMENTATION,
        "framework": REQUIRED_FRAMEWORK,
        "model_agents": [dict(item) for item in REQUIRED_MODEL_AGENTS],
        "deterministic_gates": [dict(item) for item in REQUIRED_DETERMINISTIC_GATES],
        "parallel_groups": [list(item) for item in REQUIRED_PARALLEL_GROUPS],
        "safety": {
            "deterministic_safety_authority": True,
            "external_tracing": False,
            "provider_max_in_flight": 1,
            "prompt_storage": False,
            "raw_output_storage": False,
        },
    }


def verify_agentic_runtime_contract(release: dict[str, Any]) -> None:
    runtime = release.get("agentic_runtime")
    expected = expected_agentic_runtime()
    if runtime != expected:
        raise VerificationError(
            "Agentic runtime must exactly declare the guarded LangChain/LangGraph "
            f"Nemotron architecture; expected {expected!r}, got {runtime!r}"
        )


def verify_render_runtime_contract(release: dict[str, Any]) -> None:
    """Validate the archived 2026-08-11 Blueprint as historical evidence."""

    blueprint_path = REPOSITORY / LEGACY_RENDER_BLUEPRINT_PATH
    try:
        blueprint = yaml.safe_load(blueprint_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise VerificationError(
            f"Cannot read valid historical Render Blueprint fixture: {exc}"
        ) from exc
    services = blueprint.get("services") if isinstance(blueprint, dict) else None
    if not isinstance(services, list):
        raise VerificationError("Render Blueprint services must be a list")
    frontend_services = [
        item
        for item in services
        if isinstance(item, dict) and item.get("name") == "casepath-swiss-claim-lab"
    ]
    if len(frontend_services) != 1:
        raise VerificationError(
            "Render Blueprint must declare the canonical frontend exactly once"
        )
    frontend_service = frontend_services[0]
    if frontend_service.get("runtime") != "static":
        raise VerificationError("Canonical frontend Render runtime must remain static")
    if frontend_service.get("buildCommand") != CURATED_STATIC_BUILD_COMMAND:
        raise VerificationError(
            "Canonical frontend Render build must use the curated static builder "
            "with a known commit"
        )
    if frontend_service.get("staticPublishPath") != CURATED_STATIC_PUBLISH_PATH:
        raise VerificationError(
            "Canonical frontend Render publish path must be the curated static output"
        )
    api_services = [
        item
        for item in services
        if isinstance(item, dict) and item.get("name") == "casepath-agentic-api"
    ]
    if len(api_services) != 1:
        raise VerificationError("Render Blueprint must declare the canonical API exactly once")
    api_service = api_services[0]
    if api_service.get("healthCheckPath") != "/readyz":
        raise VerificationError(
            "Canonical API Render health check must use the model-aware /readyz endpoint"
        )
    env_records = api_service.get("envVars")
    if not isinstance(env_records, list):
        raise VerificationError("Canonical API Render environment must be a list")
    env_by_key: dict[str, dict[str, Any]] = {}
    for record in env_records:
        if not isinstance(record, dict) or not isinstance(record.get("key"), str):
            raise VerificationError("Canonical API Render environment entries must name a key")
        key = record["key"]
        if key in env_by_key:
            raise VerificationError(f"Duplicate canonical API Render environment key: {key}")
        env_by_key[key] = record
    expected_values = {
        "PYTHON_VERSION": "3.13.9",
        "CASEPATH_MODEL_MODE": REQUIRED_PRODUCTION_MODE,
        "CASEPATH_AGENT_RUNTIME_PROFILE": REQUIRED_RUNTIME_PROFILE,
        "CASEPATH_RELEASE_ID": release.get("release_id"),
        "CASEPATH_MODEL_CUMULATIVE_USD_CAP": "25",
        "LANGSMITH_TRACING": "false",
    }
    for key, expected in expected_values.items():
        if env_by_key.get(key) != {"key": key, "value": expected}:
            raise VerificationError(
                f"Canonical API Render environment {key} must be {expected!r}"
            )
    if env_by_key.get("OPENROUTER_API_KEY") != {
        "key": "OPENROUTER_API_KEY",
        "sync": False,
    }:
        raise VerificationError(
            "OpenRouter credential must remain an unsynchronized Render secret reference"
        )
    qa_services = [
        item
        for item in services
        if isinstance(item, dict) and item.get("name") == "casepath-guided-canonical-qa"
    ]
    if len(qa_services) != 1:
        raise VerificationError("Render Blueprint must declare canonical QA exactly once")
    qa_service = qa_services[0]
    if qa_service.get("buildCommand") != DEFINITIVE_QA_BUILD_COMMAND:
        raise VerificationError(
            "Canonical QA build must run the deterministic browser preflight before production"
        )
    if qa_service.get("startCommand") != DEFINITIVE_QA_START_COMMAND:
        raise VerificationError("Canonical QA must serve hash-bound evidence with the Node server")
    if qa_service.get("autoDeployTrigger") != "off":
        raise VerificationError("Canonical QA must remain an explicit manual release gate")
    qa_env_records = qa_service.get("envVars")
    if not isinstance(qa_env_records, list):
        raise VerificationError("Canonical QA Render environment must be a list")
    qa_env = {
        record.get("key"): record
        for record in qa_env_records
        if isinstance(record, dict) and isinstance(record.get("key"), str)
    }
    if len(qa_env) != len(qa_env_records):
        raise VerificationError("Canonical QA Render environment keys must be unique strings")
    expected_qa_env = {
        "NODE_VERSION": {"key": "NODE_VERSION", "value": "24.14.1"},
        "PYTHON_VERSION": {"key": "PYTHON_VERSION", "value": "3.13.9"},
        "CASEPATH_ALLOW_PRODUCTION_MUTATION": {
            "key": "CASEPATH_ALLOW_PRODUCTION_MUTATION",
            "value": "1",
        },
    }
    if qa_env != expected_qa_env:
        raise VerificationError(
            "Canonical QA environment must exactly pin Node and production mutation authority"
        )


def _reject_accepted_artifact_floats(value: Any, *, path: str = "$") -> None:
    if isinstance(value, float):
        raise VerificationError(f"Accepted artifact contains a float at {path}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _reject_accepted_artifact_floats(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_accepted_artifact_floats(child, path=f"{path}[{index}]")


def accepted_artifact_hash(value: Any) -> str:
    """Match the backend's compact sorted UTF-8 hash after rejecting all floats."""

    _reject_accepted_artifact_floats(value)
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise VerificationError(f"Accepted artifact is not canonical JSON: {exc}") from exc
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _verify_positive_usage(record: Any, label: str) -> None:
    if not isinstance(record, dict):
        raise VerificationError(f"{label} must be an object")
    actual_cost = record.get("actual_cost_usd")
    prompt_tokens = record.get("prompt_tokens")
    completion_tokens = record.get("completion_tokens")
    total_tokens = record.get("total_tokens")
    if (
        not isinstance(actual_cost, (int, float))
        or isinstance(actual_cost, bool)
        or not math.isfinite(actual_cost)
        or actual_cost <= 0
    ):
        raise VerificationError(f"{label} must have positive finite actual cost")
    token_values = (prompt_tokens, completion_tokens, total_tokens)
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value <= 0
        for value in token_values
    ):
        raise VerificationError(f"{label} must have positive integer token counts")
    if total_tokens < prompt_tokens + completion_tokens:
        raise VerificationError(f"{label} total tokens are internally inconsistent")


def _provider_provenance_value_is_safe(field: str, value: Any) -> bool:
    """Match the runtime/QA sanitizer without returning provider-authored input."""

    if not isinstance(value, str) or not value or value != value.strip():
        return False
    if any(marker in value.casefold() for marker in FORBIDDEN_PROVIDER_PROVENANCE_MARKERS):
        return False
    if field == "response_id":
        return (
            len(value) <= PROVIDER_PROVENANCE_LIMITS[field]
            and PROVIDER_PROVENANCE_PATTERNS[field].fullmatch(value) is not None
        )
    if field == "response_model":
        return value in ACCEPTED_PRODUCTION_RESPONSE_MODELS
    if field == "upstream_provider":
        return (
            len(value) <= PROVIDER_PROVENANCE_LIMITS[field]
            and PROVIDER_PROVENANCE_PATTERNS[field].fullmatch(value) is not None
        )
    if field == "finish_reason":
        return value in ACCEPTED_FINISH_REASONS
    return False


def _verify_successful_provider_provenance(record: Any, label: str) -> None:
    """Require complete sanitized provenance while keeping rejected values private."""

    if not isinstance(record, Mapping):
        raise VerificationError(f"{label} must be an object")
    for field in (
        "response_id",
        "response_model",
        "upstream_provider",
        "finish_reason",
    ):
        if not _provider_provenance_value_is_safe(field, record.get(field)):
            raise VerificationError(
                f"{label} {field} violates the provider-provenance sanitizer"
            )
    if record.get("upstream_provider") != REQUIRED_UPSTREAM_PROVIDER:
        raise VerificationError(
            f"{label} upstream_provider must be '{REQUIRED_UPSTREAM_PROVIDER}'"
        )


def _verify_bounded_origin_usage(value: Any, label: str) -> None:
    if not isinstance(value, dict) or set(value) != ORIGIN_USAGE_FIELDS:
        raise VerificationError(f"{label} violates the exact origin-usage schema")
    _verify_positive_usage(value, label)
    if value.get("usage_source") not in ACCEPTED_USAGE_SOURCES:
        raise VerificationError(f"{label}.usage_source is not allowed")


def _verify_public_model_ledger(ledger: Any, label: str) -> None:
    """Validate every retained public ledger item, not only acceptance-bound calls."""

    if (
        not isinstance(ledger, dict)
        or ledger.get("scope") != "global_budget_ledger"
        or not isinstance(ledger.get("items"), list)
    ):
        raise VerificationError(f"{label} is absent or unsanitized")
    call_ids: list[str] = []
    summary = ledger.get("summary")
    if not isinstance(summary, dict) or set(summary) != MODEL_LEDGER_SUMMARY_FIELDS:
        raise VerificationError(f"{label}.summary violates the exact public schema")
    summary_count_fields = (
        "records",
        "network_calls",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "unknown_cost_call_count",
    )
    if any(
        not isinstance(summary.get(field), int)
        or isinstance(summary.get(field), bool)
        or summary[field] < 0
        for field in summary_count_fields
    ):
        raise VerificationError(f"{label}.summary has invalid count fields")
    summary_cost = summary.get("actual_cost_usd")
    if (
        not isinstance(summary_cost, (int, float))
        or isinstance(summary_cost, bool)
        or not math.isfinite(float(summary_cost))
        or summary_cost < 0
    ):
        raise VerificationError(f"{label}.summary has invalid actual cost")
    if not isinstance(summary.get("actual_cost_complete"), bool):
        raise VerificationError(f"{label}.summary has invalid cost completeness")
    summary_outcomes = summary.get("outcomes")
    if not isinstance(summary_outcomes, dict) or any(
        not isinstance(outcome, str)
        or not outcome
        or not isinstance(count, int)
        or isinstance(count, bool)
        or count <= 0
        for outcome, count in summary_outcomes.items()
    ):
        raise VerificationError(f"{label}.summary has invalid outcome counts")
    for index, item in enumerate(ledger["items"]):
        item_path = f"{label}.items[{index}]"
        if not isinstance(item, dict):
            raise VerificationError(f"{item_path} must be an object")
        unexpected = sorted(set(item) - ALLOWED_MODEL_LEDGER_FIELDS)
        if unexpected:
            raise VerificationError(
                f"Non-allowlisted public field at {item_path}.{unexpected[0]}"
            )
        call_id = item.get("call_id")
        if not isinstance(call_id, str) or not call_id:
            raise VerificationError(f"{item_path}.call_id is absent")
        call_ids.append(call_id)
        for field in PROVIDER_PROVENANCE_FIELDS:
            if (
                field in item
                and item[field] is not None
                and not _provider_provenance_value_is_safe(field, item[field])
            ):
                raise VerificationError(
                    f"{item_path}.{field} violates the provider-provenance sanitizer"
                )
        if (
            item.get("generation_model") is not None
            and not _provider_provenance_value_is_safe(
                "response_model", item["generation_model"]
            )
        ):
            raise VerificationError(
                f"{item_path}.generation_model violates the provider-provenance sanitizer"
            )
        if (
            item.get("origin_finish_reason") is not None
            and not _provider_provenance_value_is_safe(
                "finish_reason", item["origin_finish_reason"]
            )
        ):
            raise VerificationError(
                f"{item_path}.origin_finish_reason violates the provider-provenance sanitizer"
            )
        if item.get("error_invariant") == "invalid_provenance":
            invalid_field = item.get("invalid_provenance_field")
            if (
                invalid_field not in PROVIDER_PROVENANCE_FIELDS
                or not re.fullmatch(
                    r"[0-9a-f]{64}",
                    str(item.get("invalid_provenance_value_hash", "")),
                )
                or item.get(invalid_field) is not None
            ):
                raise VerificationError(
                    f"{item_path}.invalid_provenance_field has an unbounded diagnostic"
                )
        elif (
            item.get("invalid_provenance_field") is not None
            or item.get("invalid_provenance_value_hash") is not None
        ):
            raise VerificationError(
                f"{item_path}.invalid_provenance_field is out of scope"
            )
        provider_error_code = item.get("provider_error_code")
        if provider_error_code is not None and (
            item.get("error_invariant") != "provider_upstream_rejection"
            or not isinstance(provider_error_code, int)
            or isinstance(provider_error_code, bool)
            or not 0 <= provider_error_code <= 9_999
        ):
            raise VerificationError(
                f"{item_path}.provider_error_code is unbounded or out of scope"
            )
        boundary_present = "provider_boundary" in item
        expected_provider_present = "expected_upstream_provider" in item
        upstream_rejection = item.get("error_invariant") == "provider_upstream_rejection"
        if (
            boundary_present != expected_provider_present
            or upstream_rejection != boundary_present
            or (
                upstream_rejection
                and (
                    item.get("provider_boundary") != "openrouter"
                    or item.get("expected_upstream_provider")
                    != REQUIRED_UPSTREAM_PROVIDER
                )
            )
        ):
            raise VerificationError(
                f"{item_path}.provider_boundary pair is invalid or out of scope"
            )
        if (
            item.get("error_invariant") == "provider_upstream_rejection"
            and item.get("response_id") is not None
            and (
                not isinstance(item["response_id"], str)
                or OPENROUTER_GENERATION_ID_PATTERN.fullmatch(item["response_id"])
                is None
            )
        ):
            raise VerificationError(
                f"{item_path}.response_id is not an exact OpenRouter generation ID"
            )
        if "origin_usage" in item:
            _verify_bounded_origin_usage(
                item["origin_usage"],
                f"{item_path}.origin_usage",
            )
            if not _provider_provenance_value_is_safe(
                "finish_reason", item.get("origin_finish_reason")
            ):
                raise VerificationError(
                    f"{item_path}.origin_finish_reason is absent or invalid"
                )
    if len(set(call_ids)) != len(call_ids):
        raise VerificationError(f"{label}.items contain duplicate call_id fields")
    token_fields = ("prompt_tokens", "completion_tokens", "total_tokens")
    network_calls = 0
    token_totals = {field: 0 for field in token_fields}
    confirmed_costs: list[float] = []
    unknown_cost_call_count = 0
    outcomes: dict[str, int] = {}
    for item in ledger["items"]:
        call_count = item.get("call_count")
        if (
            not isinstance(call_count, int)
            or isinstance(call_count, bool)
            or call_count < 0
        ):
            raise VerificationError(f"{label}.summary source call_count is invalid")
        network_calls += call_count
        for field in token_fields:
            value = item.get(field, 0)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise VerificationError(f"{label}.summary source {field} is invalid")
            token_totals[field] += value
        actual_cost = item.get("actual_cost_usd")
        if actual_cost is None:
            if call_count > 0:
                unknown_cost_call_count += 1
        elif (
            not isinstance(actual_cost, (int, float))
            or isinstance(actual_cost, bool)
            or not math.isfinite(float(actual_cost))
            or actual_cost < 0
        ):
            raise VerificationError(f"{label}.summary source actual cost is invalid")
        else:
            confirmed_costs.append(float(actual_cost))
        outcome = item.get("outcome")
        if not isinstance(outcome, str) or not outcome:
            raise VerificationError(f"{label}.summary source outcome is invalid")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    expected_summary = {
        "records": len(ledger["items"]),
        "network_calls": network_calls,
        **token_totals,
        "actual_cost_usd": round(sum(confirmed_costs), 8),
        "actual_cost_complete": unknown_cost_call_count == 0,
        "unknown_cost_call_count": unknown_cost_call_count,
        "outcomes": {key: outcomes[key] for key in sorted(outcomes)},
    }
    if summary != expected_summary:
        raise VerificationError(f"{label}.summary is inconsistent with ledger rows")


def _historical_schema_error(section: str) -> None:
    """Fail without echoing a provider-authored key or value."""

    raise VerificationError(
        f"Historical model validation {section} violates its exact bounded schema"
    )


def _require_historical_fields(
    value: Any,
    expected: frozenset[str],
    section: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        _historical_schema_error(section)
    return value


def _is_historical_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not 20 <= len(value) <= 40:
        return False
    # Render timestamps can carry nanoseconds while ``datetime`` accepts at most
    # microseconds.  Preserve strict ISO/offset validation without rejecting the
    # additional bounded precision in a retained deployment receipt.
    normalized = re.sub(r"(\.\d{6})\d+(?=Z|[+-]\d{2}:\d{2}$)", r"\1", value)
    normalized = re.sub(
        r"\.(\d{1,5})(?=Z|[+-]\d{2}:\d{2}$)",
        lambda match: f".{match.group(1).ljust(6, '0')}",
        normalized,
    )
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _is_bounded_historical_number(
    value: Any,
    *,
    minimum: float = 0,
    maximum: float = 180_000,
) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and minimum <= float(value) <= maximum
    )


def _is_exact_historical_int(value: Any, expected: int) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value == expected
    )


def _historical_json_sha256(value: Any) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError):
        _historical_schema_error("record hash")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _verify_historical_execution(
    attempt_id: str,
    execution: Any,
) -> None:
    expected_fields = _HISTORICAL_EXECUTION_FIELDS.get(attempt_id)
    if expected_fields is None:
        if execution is not None:
            _historical_schema_error("execution observation")
        return
    values = _require_historical_fields(
        execution,
        expected_fields,
        "execution observation",
    )
    patterns = {
        "source_commit": _HISTORICAL_SOURCE_COMMIT_PATTERN,
        "frontend_deploy_id": _HISTORICAL_DEPLOY_ID_PATTERN,
        "api_deploy_id": _HISTORICAL_DEPLOY_ID_PATTERN,
        "qa_deploy_id": _HISTORICAL_DEPLOY_ID_PATTERN,
        "frontend_service_id": _HISTORICAL_SERVICE_ID_PATTERN,
        "api_service_id": _HISTORICAL_SERVICE_ID_PATTERN,
        "qa_service_id": _HISTORICAL_SERVICE_ID_PATTERN,
        "qa_run_id": _HISTORICAL_RUN_ID_PATTERN,
        "orchestration_id": _HISTORICAL_ORCHESTRATION_ID_PATTERN,
        "cold_run_id": _HISTORICAL_RUN_ID_PATTERN,
        "warm_run_id": _HISTORICAL_RUN_ID_PATTERN,
        "cold_orchestration_id": _HISTORICAL_ORCHESTRATION_ID_PATTERN,
        "warm_orchestration_id": _HISTORICAL_ORCHESTRATION_ID_PATTERN,
    }
    for field, pattern in patterns.items():
        if field in values and (
            not isinstance(values[field], str)
            or pattern.fullmatch(values[field]) is None
        ):
            _historical_schema_error("execution observation")
    if attempt_id == "production-flagship-20260812-22":
        for field in values:
            if field.endswith("_at") and not _is_historical_timestamp(values[field]):
                _historical_schema_error("execution observation")
        if (
            values["qa_deploy_outcome"] != "live"
            or values["deterministic_preflight_status"] != "passed"
            or values["production_browser_status"] != "passed"
            or not _is_exact_historical_int(
                values["deterministic_preflight_passed_checks"], 197
            )
            or not _is_exact_historical_int(
                values["deterministic_preflight_failed_checks"], 0
            )
            or not _is_exact_historical_int(
                values["production_browser_passed_checks"], 218
            )
            or not _is_exact_historical_int(
                values["production_browser_failed_checks"], 0
            )
            or not _is_exact_historical_int(values["network_call_count"], 12)
            or not _is_exact_historical_int(values["cache_hit_count"], 12)
            or not _is_exact_historical_int(values["global_ledger_record_count"], 24)
            or not _is_exact_historical_int(values["deterministic_gate_receipts"], 6)
        ):
            _historical_schema_error("execution observation")
        return
    if attempt_id == "production-flagship-20260812-23":
        for field in values:
            if field.endswith("_at") and not _is_historical_timestamp(values[field]):
                _historical_schema_error("execution observation")
        if (
            values["qa_deploy_outcome"] != "build_failed"
            or values["deterministic_preflight_status"] != "passed"
            or values["causal_preflight_verifier_passed"] is not True
            or not _is_exact_historical_int(
                values["deterministic_preflight_passed_checks"], 197
            )
            or not _is_exact_historical_int(
                values["deterministic_preflight_failed_checks"], 0
            )
            or not _is_exact_historical_int(values["network_call_count"], 1)
            or not _is_exact_historical_int(values["completed_model_calls"], 0)
            or not _is_exact_historical_int(values["failed_model_calls"], 1)
            or not _is_exact_historical_int(
                values["downstream_model_calls_after_failure"], 0
            )
            or not _is_exact_historical_int(values["deterministic_gate_receipts"], 0)
            or values["warm_replay_started"] is not False
        ):
            _historical_schema_error("execution observation")
        return
    if attempt_id == "production-flagship-20260812-24":
        for field in values:
            if field.endswith("_at") and not _is_historical_timestamp(values[field]):
                _historical_schema_error("execution observation")
        exact_id_patterns = {
            "flagship_cold_run_id": _HISTORICAL_RUN_ID_PATTERN,
            "flagship_warm_run_id": _HISTORICAL_RUN_ID_PATTERN,
            "later_cold_run_id": _HISTORICAL_RUN_ID_PATTERN,
            "flagship_cold_orchestration_id": _HISTORICAL_ORCHESTRATION_ID_PATTERN,
            "flagship_warm_orchestration_id": _HISTORICAL_ORCHESTRATION_ID_PATTERN,
            "later_cold_orchestration_id": _HISTORICAL_ORCHESTRATION_ID_PATTERN,
        }
        if any(
            not isinstance(values[field], str)
            or pattern.fullmatch(values[field]) is None
            for field, pattern in exact_id_patterns.items()
        ):
            _historical_schema_error("execution observation")
        if (
            values["qa_deploy_outcome"] != "build_failed"
            or values["deterministic_preflight_status"] != "passed"
            or values["causal_preflight_verifier_passed"] is not True
            or not _is_exact_historical_int(
                values["deterministic_preflight_passed_checks"], 197
            )
            or not _is_exact_historical_int(
                values["deterministic_preflight_failed_checks"], 0
            )
            or not _is_exact_historical_int(values["production_initial_ledger_records"], 0)
            or not _is_exact_historical_int(
                values["production_initial_ledger_network_calls"], 0
            )
            or values["production_initial_ledger_actual_cost_usd"] != 0
            or values["production_initial_ledger_checked_before_first_run_post"] is not True
            or not _is_exact_historical_int(values["global_ledger_record_count"], 14)
            or not _is_exact_historical_int(values["network_call_count"], 8)
            or not _is_exact_historical_int(values["cache_hit_count"], 6)
            or not _is_exact_historical_int(values["completed_network_model_calls"], 7)
            or not _is_exact_historical_int(values["failed_model_calls"], 1)
            or not _is_exact_historical_int(values["flagship_model_roles_complete"], 6)
            or not _is_exact_historical_int(
                values["flagship_deterministic_gate_receipts"], 3
            )
            or not _is_exact_historical_int(values["later_model_roles_complete"], 1)
            or not _is_exact_historical_int(
                values["later_downstream_model_calls_after_failure"], 0
            )
            or not _is_exact_historical_int(
                values["later_deterministic_gate_receipts"], 0
            )
            or values["later_warm_run_started"] is not False
            or not (
                values["production_marker_emitted_at"]
                < values["production_initial_ledger_checked_at"]
                < values["first_production_run_post_accepted_at"]
            )
        ):
            _historical_schema_error("execution observation")
        return
    if values.get("qa_deploy_outcome") != "build_failed":
        _historical_schema_error("execution observation")
    if attempt_id == "production-flagship-20260812-15":
        for field in values:
            if field.endswith("_at") and not _is_historical_timestamp(values[field]):
                _historical_schema_error("execution observation")
        if values != {
            "source_commit": "c030f041566b1b318a030dca85e672717efd489f",
            "frontend_service_id": "srv-d9q3ndvavr4c73ao86r0",
            "frontend_deploy_id": "dep-d9u2pg142hec739dtd1g",
            "frontend_deploy_outcome": "live",
            "frontend_deploy_created_at": "2026-08-12T08:20:16.27268Z",
            "frontend_deploy_started_at": "2026-08-12T08:20:16.270719Z",
            "frontend_deploy_finished_at": "2026-08-12T08:20:56.917824Z",
            "api_service_id": "srv-d9r4v4e417fc73bda92g",
            "api_deploy_id": "dep-d9u2oi6417fc73fjto3g",
            "api_deploy_outcome": "live",
            "api_deploy_created_at": "2026-08-12T08:18:16.30452Z",
            "api_deploy_started_at": "2026-08-12T08:18:16.274952Z",
            "api_deploy_finished_at": "2026-08-12T08:19:53.930629Z",
            "qa_service_id": "srv-d9se2bh42hec73c54sjg",
            "qa_deploy_id": "dep-d9u2s2bm8hqs73ecqik0",
            "qa_deploy_outcome": "build_failed",
            "qa_deploy_created_at": "2026-08-12T08:25:45.871622Z",
            "qa_deploy_started_at": "2026-08-12T08:25:45.842746Z",
            "qa_deploy_finished_at": "2026-08-12T08:26:52.180067Z",
            "qa_error_at": "2026-08-12T08:26:50.058780742Z",
            "qa_build_failed_at": "2026-08-12T08:26:50.117797905Z",
            "qa_run_id": "run_5f6b88f669bb0316",
            "qa_run_request_accepted_at": "2026-08-12T08:26:06.393323468Z",
            "ledger_created_at": "2026-08-12T08:26:07.454775+00:00",
            "ledger_updated_at": "2026-08-12T08:26:44.924203+00:00",
            "orchestration_id": "orch_47fcf18494e7c1ec",
            "network_call_count": 6,
            "completed_model_calls": 6,
            "failed_model_calls": 0,
            "guarded_fallback_model_calls": 2,
            "required_model_agent_ids": [
                "canonical_facts",
                "orchestrator_plan",
                "document_source_integrity",
                "process_decision_mapping",
                "evidence_checklist",
                "final_claim_brief_audit",
            ],
            "deterministic_gate_receipts": 3,
            "deterministic_gate_ids": [
                "deterministic_process_gate",
                "deterministic_evidence_gate",
                "whole_playbook_gate",
            ],
        }:
            _historical_schema_error("execution observation")
        return
    if attempt_id == "production-flagship-20260812-16":
        for field in values:
            if field.endswith("_at") and not _is_historical_timestamp(values[field]):
                _historical_schema_error("execution observation")
        if (
            values["source_commit"] != "c325c8a0ec27fe0e3fcec5c24407d7b578df2356"
            or values["frontend_deploy_outcome"] != "live"
            or values["api_deploy_outcome"] != "live"
            or not _is_exact_historical_int(values["network_call_count"], 6)
            or not _is_exact_historical_int(values["cold_model_calls"], 6)
            or not _is_exact_historical_int(values["warm_cache_calls"], 6)
            or not _is_exact_historical_int(values["failed_model_calls"], 0)
            or not _is_exact_historical_int(values["guarded_fallback_model_calls"], 2)
            or not _is_exact_historical_int(values["deterministic_gate_receipts"], 3)
            or values["required_model_agent_ids"]
            != [
                "canonical_facts",
                "orchestrator_plan",
                "document_source_integrity",
                "process_decision_mapping",
                "evidence_checklist",
                "final_claim_brief_audit",
            ]
            or values["deterministic_gate_ids"]
            != [
                "deterministic_process_gate",
                "deterministic_evidence_gate",
                "whole_playbook_gate",
            ]
        ):
            _historical_schema_error("execution observation")
        return
    if attempt_id == "production-flagship-20260812-17":
        for field in values:
            if field.endswith("_at") and not _is_historical_timestamp(values[field]):
                _historical_schema_error("execution observation")
        if values != {
            "source_commit": "580974b0844f3a7e66ba3d324685cd3290798114",
            "frontend_service_id": "srv-d9q3ndvavr4c73ao86r0",
            "frontend_deploy_id": "dep-d9u49i7lk1mc73fhl4f0",
            "frontend_deploy_outcome": "live",
            "frontend_deploy_started_at": "2026-08-12T10:02:48.153838Z",
            "frontend_deploy_finished_at": "2026-08-12T10:03:27.240993Z",
            "api_service_id": "srv-d9r4v4e417fc73bda92g",
            "api_deploy_id": "dep-d9u49ibm8hqs73eg67ug",
            "api_deploy_outcome": "live",
            "api_deploy_started_at": "2026-08-12T10:02:49.586009Z",
            "api_deploy_finished_at": "2026-08-12T10:04:25.397510Z",
            "qa_service_id": "srv-d9se2bh42hec73c54sjg",
            "qa_deploy_id": "dep-d9u4bqjncjis73ag4iag",
            "qa_deploy_outcome": "build_failed",
            "qa_deploy_created_at": "2026-08-12T10:07:38.148836Z",
            "qa_deploy_started_at": "2026-08-12T10:07:38.116981Z",
            "qa_deploy_finished_at": "2026-08-12T10:08:48.161549Z",
            "qa_error_at": "2026-08-12T10:08:46.548627198Z",
            "qa_run_id": "run_020a11fbd8dc3231",
            "qa_run_request_accepted_at": "2026-08-12T10:07:57.045614253Z",
            "ledger_created_at": "2026-08-12T10:07:58.159274+00:00",
            "ledger_updated_at": "2026-08-12T10:08:45.308131+00:00",
            "orchestration_id": "orch_03c1bbb4a9e4269b",
            "failed_agent_id": "evidence_checklist",
            "network_call_count": 5,
            "completed_model_calls": 4,
            "failed_model_calls": 1,
            "downstream_model_calls_after_failure": 0,
            "deterministic_gate_receipts": 1,
            "completed_deterministic_gate_ids": ["deterministic_process_gate"],
            "deterministic_evidence_gate_started": False,
            "final_model_role_started": False,
            "whole_playbook_gate_started": False,
            "warm_replay_started": False,
        }:
            _historical_schema_error("execution observation")
        return
    if attempt_id == "production-flagship-20260812-18":
        for field in values:
            if field.endswith("_at") and not _is_historical_timestamp(values[field]):
                _historical_schema_error("execution observation")
        if (
            values["source_commit"]
            != "df4db4872e0854af7dbe97e5c86833ab827a1c1b"
            or values["frontend_deploy_outcome"] != "live"
            or values["api_deploy_outcome"] != "live"
            or values["failed_agent_id"] != "document_source_integrity"
            or not _is_exact_historical_int(values["network_call_count"], 4)
            or not _is_exact_historical_int(values["completed_model_calls"], 3)
            or not _is_exact_historical_int(values["failed_model_calls"], 1)
            or not _is_exact_historical_int(
                values["downstream_model_calls_after_failure"], 0
            )
            or not _is_exact_historical_int(values["deterministic_gate_receipts"], 0)
            or values["completed_deterministic_gate_ids"] != []
            or values["evidence_checklist_started"] is not False
            or values["final_model_role_started"] is not False
            or values["whole_playbook_gate_started"] is not False
            or values["warm_replay_started"] is not False
            or values["receipt_sequence"]
            != [
                {"ordinal": 16, "agent_id": "orchestrator_plan", "state": "started"},
                {
                    "ordinal": 17,
                    "agent_id": "orchestrator_plan",
                    "state": "completed",
                },
                {
                    "ordinal": 18,
                    "agent_id": "document_source_integrity",
                    "state": "started",
                },
                {
                    "ordinal": 19,
                    "agent_id": "process_decision_mapping",
                    "state": "started",
                },
                {
                    "ordinal": 20,
                    "agent_id": "document_source_integrity",
                    "state": "failed",
                },
            ]
            or values["process_output_succeeded_after_failure"] is not True
            or values["process_completed_receipt_observed"] is not False
        ):
            _historical_schema_error("execution observation")
        return
    if attempt_id == "production-flagship-20260812-19":
        for field in values:
            if field.endswith("_at") and not _is_historical_timestamp(values[field]):
                _historical_schema_error("execution observation")
        if (
            values["source_commit"]
            != "72b2527b05e2fc4e25c3b8655d4fe9f2da266580"
            or values["frontend_deploy_outcome"] != "live"
            or values["api_deploy_outcome"] != "live"
            or not _is_exact_historical_int(values["network_call_count"], 6)
            or not _is_exact_historical_int(values["cold_model_calls"], 6)
            or not _is_exact_historical_int(values["warm_cache_calls"], 6)
            or not _is_exact_historical_int(values["failed_model_calls"], 0)
            or not _is_exact_historical_int(
                values["guarded_fallback_model_calls"], 1
            )
            or not _is_exact_historical_int(values["deterministic_gate_receipts"], 3)
            or values["required_model_agent_ids"]
            != [
                "canonical_facts",
                "orchestrator_plan",
                "document_source_integrity",
                "process_decision_mapping",
                "evidence_checklist",
                "final_claim_brief_audit",
            ]
            or values["deterministic_gate_ids"]
            != [
                "deterministic_process_gate",
                "deterministic_evidence_gate",
                "whole_playbook_gate",
            ]
        ):
            _historical_schema_error("execution observation")
        return
    if attempt_id == "production-flagship-20260812-20":
        for field in values:
            if field.endswith("_at") and not _is_historical_timestamp(values[field]):
                _historical_schema_error("execution observation")
        if (
            values["source_commit"]
            != "2ab81d4c717c36f86717867230948ffe5c4875f8"
            or values["frontend_deploy_outcome"] != "live"
            or values["api_deploy_outcome"] != "live"
            or not _is_exact_historical_int(values["network_call_count"], 6)
            or not _is_exact_historical_int(values["cold_model_calls"], 6)
            or not _is_exact_historical_int(values["warm_cache_calls"], 6)
            or not _is_exact_historical_int(values["failed_model_calls"], 0)
            or not _is_exact_historical_int(
                values["guarded_fallback_model_calls"], 2
            )
            or not _is_exact_historical_int(values["deterministic_gate_receipts"], 3)
            or values["required_model_agent_ids"]
            != [
                "canonical_facts",
                "orchestrator_plan",
                "document_source_integrity",
                "process_decision_mapping",
                "evidence_checklist",
                "final_claim_brief_audit",
            ]
            or values["deterministic_gate_ids"]
            != [
                "deterministic_process_gate",
                "deterministic_evidence_gate",
                "whole_playbook_gate",
            ]
        ):
            _historical_schema_error("execution observation")
        return
    if attempt_id == "production-flagship-20260812-21":
        for field in values:
            if field.endswith("_at") and not _is_historical_timestamp(values[field]):
                _historical_schema_error("execution observation")
        if values != {
            "source_commit": "eb5568a1973f63fdbf0ebd0b3f7cd152c73a29cf",
            "frontend_service_id": "srv-d9q3ndvavr4c73ao86r0",
            "frontend_deploy_id": "dep-d9u6mubm8hqs73elmuk0",
            "frontend_deploy_outcome": "live",
            "frontend_deploy_created_at": "2026-08-12T12:47:53.677842Z",
            "frontend_deploy_started_at": "2026-08-12T12:47:53.67581Z",
            "frontend_deploy_finished_at": "2026-08-12T12:48:14.420369Z",
            "api_service_id": "srv-d9r4v4e417fc73bda92g",
            "api_deploy_id": "dep-d9u6msvavr4c73eklnf0",
            "api_deploy_outcome": "live",
            "api_deploy_created_at": "2026-08-12T12:47:47.693301Z",
            "api_deploy_started_at": "2026-08-12T12:47:47.667861Z",
            "api_deploy_finished_at": "2026-08-12T12:49:28.841769Z",
            "qa_service_id": "srv-d9se2bh42hec73c54sjg",
            "qa_deploy_id": "dep-d9u6okf40ujc73flp1o0",
            "qa_deploy_outcome": "build_failed",
            "qa_deploy_created_at": "2026-08-12T12:51:29.954139Z",
            "qa_deploy_started_at": "2026-08-12T12:51:29.918727Z",
            "qa_deploy_finished_at": "2026-08-12T12:54:39.158068Z",
            "qa_error_at": "2026-08-12T12:54:37.489228893Z",
            "qa_build_failed_at": "2026-08-12T12:54:37.531067695Z",
            "cold_run_id": "run_b33e288771f5734e",
            "cold_run_request_accepted_at": "2026-08-12T12:51:52.729191788Z",
            "cold_orchestration_id": "orch_41c7d6d772421ec1",
            "warm_run_id": "run_57307719ce42f9e9",
            "warm_run_request_accepted_at": "2026-08-12T12:53:06.126764967Z",
            "warm_orchestration_id": "orch_9189d783e3d07e04",
            "ledger_created_at": "2026-08-12T12:51:53.812313+00:00",
            "ledger_updated_at": "2026-08-12T12:53:11.613119+00:00",
            "network_call_count": 6,
            "cold_model_calls": 6,
            "warm_cache_calls": 6,
            "failed_model_calls": 0,
            "guarded_fallback_model_calls": 2,
            "required_model_agent_ids": [
                "canonical_facts",
                "orchestrator_plan",
                "document_source_integrity",
                "process_decision_mapping",
                "evidence_checklist",
                "final_claim_brief_audit",
            ],
            "deterministic_gate_receipts": 3,
            "deterministic_gate_ids": [
                "deterministic_process_gate",
                "deterministic_evidence_gate",
                "whole_playbook_gate",
            ],
        }:
            _historical_schema_error("execution observation")
        return
    if attempt_id in {
        "production-flagship-20260811-12",
        "production-flagship-20260812-14",
    }:
        expected_failed_agent = "process_decision_mapping"
    elif attempt_id in _HISTORICAL_TWO_CALL_OUTPUT_LIMITS:
        expected_failed_agent = "orchestrator_plan"
    else:
        expected_failed_agent = "canonical_facts"
    if values.get("failed_agent_id") != expected_failed_agent:
        _historical_schema_error("execution observation")
    for field in values:
        if field.endswith("_at") and not _is_historical_timestamp(values[field]):
            _historical_schema_error("execution observation")
    for field in ("provider_response_count", "network_call_count"):
        expected_count = 1
        if field == "network_call_count":
            if attempt_id in {
                "production-flagship-20260811-12",
                "production-flagship-20260812-14",
            }:
                expected_count = 4
            elif attempt_id in _HISTORICAL_TWO_CALL_OUTPUT_LIMITS:
                expected_count = 2
        if field in values and not _is_exact_historical_int(
            values[field], expected_count
        ):
            _historical_schema_error("execution observation")
    for field in (
        "downstream_model_calls",
        "downstream_model_calls_after_failure",
        "downstream_agent_receipts",
        "later_model_roles_started",
        "deterministic_gate_receipts",
    ):
        expected_count = (
            3
            if attempt_id == "production-flagship-20260812-14"
            and field == "downstream_agent_receipts"
            else 0
        )
        if field in values and not _is_exact_historical_int(
            values[field], expected_count
        ):
            _historical_schema_error("execution observation")
    for field in ("completed_model_calls", "failed_model_calls"):
        if attempt_id == "production-flagship-20260812-14":
            expected_count = 2
        elif (
            attempt_id == "production-flagship-20260811-12"
            and field == "completed_model_calls"
        ):
            expected_count = 3
        elif (
            attempt_id == "production-flagship-20260812-13"
            and field == "completed_model_calls"
        ):
            expected_count = 0
        else:
            expected_count = 1
        if field in values and not _is_exact_historical_int(
            values[field], expected_count
        ):
            _historical_schema_error("execution observation")
    if attempt_id == "production-flagship-20260812-13" and values != {
        "source_commit": "690f99e63a6eab4120ad75b83671cffe0f9e62af",
        "qa_service_id": "srv-d9se2bh42hec73c54sjg",
        "qa_deploy_id": "dep-d9ts68ht0dsc73c0nj5g",
        "qa_deploy_outcome": "build_failed",
        "qa_deploy_created_at": "2026-08-12T00:49:39.049742Z",
        "qa_deploy_started_at": "2026-08-12T00:49:39.025093Z",
        "qa_deploy_finished_at": "2026-08-12T00:50:00.690848Z",
        "orchestration_id": "orch_bbf7ee808dc04f57",
        "failed_agent_id": "canonical_facts",
        "network_call_count": 1,
        "completed_model_calls": 0,
        "failed_model_calls": 1,
        "downstream_model_calls_after_failure": 0,
        "downstream_agent_receipts": 0,
        "deterministic_gate_receipts": 0,
    }:
        _historical_schema_error("execution observation")
    if attempt_id == "production-flagship-20260812-14" and values != {
        "source_commit": "765c610378e7acdc224e200c0e7bbbc65c697c6b",
        "frontend_service_id": "srv-d9q3ndvavr4c73ao86r0",
        "frontend_deploy_id": "dep-d9u0ihe417fc73fescgg",
        "frontend_deploy_outcome": "live",
        "frontend_deploy_created_at": "2026-08-12T05:48:53.960022Z",
        "frontend_deploy_started_at": "2026-08-12T05:48:53.958262Z",
        "frontend_deploy_finished_at": "2026-08-12T05:49:16.168679Z",
        "api_service_id": "srv-d9r4v4e417fc73bda92g",
        "api_deploy_id": "dep-d9u0ihh42hec7398pnm0",
        "api_deploy_outcome": "live",
        "api_deploy_created_at": "2026-08-12T05:48:54.447829Z",
        "api_deploy_started_at": "2026-08-12T05:48:54.420543Z",
        "api_deploy_finished_at": "2026-08-12T05:50:34.763754Z",
        "qa_service_id": "srv-d9se2bh42hec73c54sjg",
        "qa_deploy_id": "dep-d9u0jnbm8hqs73e7kj3g",
        "qa_deploy_outcome": "build_failed",
        "qa_deploy_created_at": "2026-08-12T05:51:25.689876Z",
        "qa_deploy_started_at": "2026-08-12T05:51:25.662198Z",
        "qa_deploy_finished_at": "2026-08-12T05:53:05.203502Z",
        "qa_error_at": "2026-08-12T05:53:04.010394007Z",
        "qa_build_failed_at": "2026-08-12T05:53:04.067610832Z",
        "qa_run_id": "run_3010703608cef786",
        "qa_run_request_accepted_at": "2026-08-12T05:51:50.213421033Z",
        "ledger_created_at": "2026-08-12T05:51:51.268843+00:00",
        "ledger_updated_at": "2026-08-12T05:53:02.763202+00:00",
        "orchestration_id": "orch_5c8e411d9ccf1b05",
        "failed_agent_id": "process_decision_mapping",
        "failed_agent_ids": [
            "process_decision_mapping",
            "document_source_integrity",
        ],
        "network_call_count": 4,
        "completed_model_calls": 2,
        "failed_model_calls": 2,
        "downstream_model_calls_after_failure": 0,
        "downstream_agent_receipts": 3,
        "later_model_roles_started": 0,
        "deterministic_gate_receipts": 0,
    }:
        _historical_schema_error("execution observation")


def _verify_two_call_provider_observation(
    attempt_id: str,
    values: dict[str, Any],
) -> None:
    calls = values.get("calls")
    if (
        not isinstance(calls, list)
        or len(calls) != 2
        or [item.get("agent_id") if isinstance(item, dict) else None for item in calls]
        != ["canonical_facts", "orchestrator_plan"]
    ):
        _historical_schema_error("provider call observations")

    verified_calls: list[dict[str, Any]] = []
    for call in calls:
        agent_id = call["agent_id"]
        call = _require_historical_fields(
            call,
            _HISTORICAL_TWO_CALL_FIELDS[agent_id],
            "provider call observation",
        )
        if (
            not isinstance(call["call_id"], str)
            or _HISTORICAL_CALL_ID_PATTERN.fullmatch(call["call_id"]) is None
            or not isinstance(call["response_id"], str)
            or OPENROUTER_GENERATION_ID_PATTERN.fullmatch(call["response_id"])
            is None
            or call["response_model"] not in ACCEPTED_PRODUCTION_RESPONSE_MODELS
            or call["upstream_provider"] != "DeepInfra"
            or not _is_bounded_historical_number(call["latency_ms"], minimum=0.001)
            or not _is_historical_timestamp(call["created_at"])
            or not _is_historical_timestamp(call["updated_at"])
        ):
            _historical_schema_error("provider call observation")
        _verify_positive_usage(call, "Historical provider call observation")
        if call["total_tokens"] != call["prompt_tokens"] + call["completion_tokens"]:
            _historical_schema_error("provider call observation")
        verified_calls.append(call)

    canonical, orchestrator = verified_calls
    if (
        canonical["outcome"] != "succeeded_with_guarded_fallback"
        or canonical["finish_reason"] != "stop"
        or canonical["deterministic_fallback_applied"] is not True
        or not _is_exact_historical_int(canonical["accepted_fact_count"], 17)
        or not _is_exact_historical_int(canonical["rejected_fact_count"], 1)
        or not _is_exact_historical_int(
            canonical["source_reference_projection_count"], 10
        )
        or orchestrator["outcome"] != "failed"
        or orchestrator["finish_reason"] != "length"
        or not _is_exact_historical_int(
            orchestrator["completion_tokens"],
            _HISTORICAL_TWO_CALL_OUTPUT_LIMITS[attempt_id],
        )
        or orchestrator["error_type"] != "AgentBoundaryError"
        or orchestrator["error_invariant"] != "provider_finish_reason"
    ):
        _historical_schema_error("provider call observations")

    if (
        not _is_exact_historical_int(values.get("network_call_count"), 2)
        or values.get("actual_cost_complete") is not True
        or not _is_exact_historical_int(values.get("unknown_cost_call_count"), 0)
        or values["prompt_tokens"] != sum(call["prompt_tokens"] for call in verified_calls)
        or values["completion_tokens"]
        != sum(call["completion_tokens"] for call in verified_calls)
        or values["total_tokens"] != sum(call["total_tokens"] for call in verified_calls)
        or not math.isclose(
            values["actual_cost_usd"],
            sum(call["actual_cost_usd"] for call in verified_calls),
            rel_tol=0,
            abs_tol=1e-10,
        )
    ):
        _historical_schema_error("provider call aggregate")


def _verify_attempt_12_provider_observation(values: dict[str, Any]) -> None:
    calls = values.get("calls")
    expected_agents = [
        "canonical_facts",
        "orchestrator_plan",
        "document_source_integrity",
        "process_decision_mapping",
    ]
    if (
        not isinstance(calls, list)
        or len(calls) != 4
        or [item.get("agent_id") if isinstance(item, dict) else None for item in calls]
        != expected_agents
    ):
        _historical_schema_error("provider call observations")

    verified_calls: list[dict[str, Any]] = []
    for call in calls:
        agent_id = call["agent_id"]
        call = _require_historical_fields(
            call,
            _HISTORICAL_ATTEMPT_12_CALL_FIELDS[agent_id],
            "provider call observation",
        )
        if (
            not isinstance(call["call_id"], str)
            or _HISTORICAL_CALL_ID_PATTERN.fullmatch(call["call_id"]) is None
            or not isinstance(call["response_id"], str)
            or OPENROUTER_GENERATION_ID_PATTERN.fullmatch(call["response_id"])
            is None
            or call["response_model"] not in ACCEPTED_PRODUCTION_RESPONSE_MODELS
            or call["upstream_provider"] != "DeepInfra"
            or call["finish_reason"] != "stop"
            or not _is_bounded_historical_number(call["latency_ms"], minimum=0.001)
            or not _is_historical_timestamp(call["created_at"])
            or not _is_historical_timestamp(call["updated_at"])
        ):
            _historical_schema_error("provider call observation")
        _verify_positive_usage(call, "Historical provider call observation")
        if call["total_tokens"] != call["prompt_tokens"] + call["completion_tokens"]:
            _historical_schema_error("provider call observation")
        verified_calls.append(call)

    canonical, orchestrator, document_source, process_mapping = verified_calls
    if (
        canonical["outcome"] != "succeeded_with_guarded_fallback"
        or canonical["deterministic_fallback_applied"] is not True
        or not _is_exact_historical_int(canonical["accepted_fact_count"], 17)
        or not _is_exact_historical_int(canonical["rejected_fact_count"], 1)
        or not _is_exact_historical_int(
            canonical["source_reference_projection_count"], 11
        )
    ):
        _historical_schema_error("provider call observations")
    for call, accepted_count in ((orchestrator, 1), (document_source, 6)):
        if (
            call["outcome"] != "succeeded"
            or call["deterministic_fallback_applied"] is not False
            or not _is_exact_historical_int(
                call["accepted_item_count"], accepted_count
            )
            or not _is_exact_historical_int(call["rejected_item_count"], 0)
            or not _is_exact_historical_int(call["ignored_proposal_count"], 0)
        ):
            _historical_schema_error("provider call observations")
    if (
        process_mapping["outcome"] != "failed"
        or process_mapping["error_type"] != "AgentBoundaryError"
        or process_mapping["error_invariant"] != "model_contribution_majority"
    ):
        _historical_schema_error("provider call observations")

    if (
        not _is_exact_historical_int(values.get("network_call_count"), 4)
        or values.get("actual_cost_complete") is not True
        or not _is_exact_historical_int(values.get("unknown_cost_call_count"), 0)
        or values["prompt_tokens"] != sum(call["prompt_tokens"] for call in calls)
        or values["completion_tokens"]
        != sum(call["completion_tokens"] for call in calls)
        or values["total_tokens"] != sum(call["total_tokens"] for call in calls)
        or not math.isclose(
            values["actual_cost_usd"],
            sum(call["actual_cost_usd"] for call in calls),
            rel_tol=0,
            abs_tol=1e-10,
        )
    ):
        _historical_schema_error("provider call aggregate")


def _verify_attempt_13_provider_observation(values: dict[str, Any]) -> None:
    ledger = _require_historical_fields(
        values.get("application_ledger_observation"),
        frozenset(
            "call_id orchestration_id agent_id outcome error_type latency_ms "
            "response_identity_retained response_model_retained "
            "upstream_provider_retained provider_error_code_retained "
            "usage_metadata_retained "
            "actual_cost_retained".split()
        ),
        "application ledger observation",
    )
    if (
        ledger["call_id"] != "modelcall_f97afa2a05079468"
        or ledger["orchestration_id"] != "orch_bbf7ee808dc04f57"
        or ledger["agent_id"] != "canonical_facts"
        or ledger["outcome"] != "failed"
        or ledger["error_type"] != "TooManyRequestsResponseError"
        or not _is_bounded_historical_number(ledger["latency_ms"], minimum=0.001)
    ):
        _historical_schema_error("application ledger observation")
    for field in (
        "response_identity_retained",
        "response_model_retained",
        "upstream_provider_retained",
        "provider_error_code_retained",
        "usage_metadata_retained",
        "actual_cost_retained",
    ):
        if ledger[field] is not False:
            _historical_schema_error("application ledger observation")
    if not math.isclose(ledger["latency_ms"], 2777.996, rel_tol=0, abs_tol=1e-9):
        _historical_schema_error("application ledger observation")

    attribution = _require_historical_fields(
        values.get("failure_attribution"),
        frozenset(
            "classification cause_detail router_origin_established "
            "key_or_account_hard_limit_reached".split()
        ),
        "failure attribution",
    )
    if attribution != {
        "classification": "external_deepinfra_http_429",
        "cause_detail": "unknown",
        "router_origin_established": False,
        "key_or_account_hard_limit_reached": False,
    }:
        _historical_schema_error("failure attribution")

    capacity = _require_historical_fields(
        values.get("key_account_capacity_observation"),
        frozenset(
            "read_only configured_key_limit_usd key_used_percent "
            "key_hard_limit_reached account_credit_status".split()
        ),
        "key and account capacity observation",
    )
    if (
        capacity["read_only"] is not True
        or not _is_exact_historical_int(capacity["configured_key_limit_usd"], 25)
        or not _is_bounded_historical_number(
            capacity["key_used_percent"], minimum=0, maximum=100
        )
        or not math.isclose(
            capacity["key_used_percent"], 0.6536316, rel_tol=0, abs_tol=1e-10
        )
        or capacity["key_hard_limit_reached"] is not False
        or capacity["account_credit_status"] != "healthy"
    ):
        _historical_schema_error("key and account capacity observation")

    if (
        not _is_exact_historical_int(values.get("network_call_count"), 1)
        or values.get("actual_cost_complete") is not False
        or not _is_exact_historical_int(values.get("unknown_cost_call_count"), 1)
    ):
        _historical_schema_error("provider call aggregate")


def _verify_attempt_14_provider_observation(values: dict[str, Any]) -> None:
    calls = values.get("calls")
    expected_agents = [
        "canonical_facts",
        "orchestrator_plan",
        "process_decision_mapping",
        "document_source_integrity",
    ]
    if (
        not isinstance(calls, list)
        or len(calls) != 4
        or [item.get("agent_id") if isinstance(item, dict) else None for item in calls]
        != expected_agents
    ):
        _historical_schema_error("provider call observations")

    verified_calls: list[dict[str, Any]] = []
    for call in calls:
        agent_id = call["agent_id"]
        verified = _require_historical_fields(
            call,
            _HISTORICAL_ATTEMPT_14_CALL_FIELDS[agent_id],
            "provider call observation",
        )
        if (
            not isinstance(verified["call_id"], str)
            or _HISTORICAL_CALL_ID_PATTERN.fullmatch(verified["call_id"]) is None
            or not _is_historical_timestamp(verified["created_at"])
            or not _is_historical_timestamp(verified["updated_at"])
            or not _is_bounded_historical_number(
                verified["latency_ms"], minimum=0.001
            )
            or not _is_bounded_historical_number(
                verified["estimated_cost_usd"], minimum=0.000_000_01, maximum=25
            )
        ):
            _historical_schema_error("provider call observation")
        delegation_id = verified["delegation_id"]
        if agent_id == "canonical_facts":
            if verified["parent_call_id"] is not None or delegation_id is not None:
                _historical_schema_error("provider call observation")
        elif (
            not isinstance(verified["parent_call_id"], str)
            or _HISTORICAL_CALL_ID_PATTERN.fullmatch(verified["parent_call_id"])
            is None
            or not isinstance(delegation_id, str)
            or _HISTORICAL_DELEGATION_ID_PATTERN.fullmatch(delegation_id) is None
        ):
            _historical_schema_error("provider call observation")
        verified_calls.append(verified)

    canonical, orchestrator, process_mapping, document_source = verified_calls
    for call in (canonical, orchestrator):
        if (
            call["outcome"] != "succeeded"
            or not isinstance(call["response_id"], str)
            or OPENROUTER_GENERATION_ID_PATTERN.fullmatch(call["response_id"])
            is None
            or call["response_model"] not in ACCEPTED_PRODUCTION_RESPONSE_MODELS
            or call["upstream_provider"] != "DeepInfra"
            or call["finish_reason"] != "stop"
            or call["usage_source"] != "response"
            or call["deterministic_fallback_applied"] is not False
        ):
            _historical_schema_error("provider call observation")
        _verify_positive_usage(call, "Historical provider call observation")
        if call["total_tokens"] != call["prompt_tokens"] + call["completion_tokens"]:
            _historical_schema_error("provider call observation")

    if (
        canonical["call_id"] != "modelcall_b5582c002c6f20bb"
        or canonical["response_id"] != "gen-1786513914-oQ9RsMSIInmknRyHgohy"
        or not math.isclose(
            canonical["actual_cost_usd"], 0.0160784, rel_tol=0, abs_tol=1e-10
        )
        or (canonical["prompt_tokens"], canonical["completion_tokens"], canonical["total_tokens"])
        != (23188, 2050, 25238)
        or canonical["accepted_fact_count"] != 18
        or canonical["rejected_fact_count"] != 0
        or canonical["source_reference_projection_count"] != 12
        or canonical["ignored_noncontrolling_normalized_proposals"] != 1
        or orchestrator["call_id"] != "modelcall_47529c6d5a49d7cc"
        or orchestrator["parent_call_id"] != canonical["call_id"]
        or orchestrator["response_id"] != "gen-1786513974-UDX9yxmzmSgZf0S3irqg"
        or not math.isclose(
            orchestrator["actual_cost_usd"], 0.0003496, rel_tol=0, abs_tol=1e-10
        )
        or (orchestrator["prompt_tokens"], orchestrator["completion_tokens"], orchestrator["total_tokens"])
        != (438, 71, 509)
        or orchestrator["accepted_item_count"] != 1
        or orchestrator["rejected_item_count"] != 0
        or orchestrator["ignored_proposal_count"] != 0
    ):
        _historical_schema_error("provider call observations")

    failed_calls = (process_mapping, document_source)
    expected_failed_ids = (
        "modelcall_509e1d20d5f03da7",
        "modelcall_17477d1f8a445c6f",
    )
    expected_latencies = (1790.019, 2183.34)
    expected_estimates = (0.0153431, 0.01517435)
    for call, expected_id, expected_latency, expected_estimate in zip(
        failed_calls,
        expected_failed_ids,
        expected_latencies,
        expected_estimates,
    ):
        if (
            call["call_id"] != expected_id
            or call["parent_call_id"] != orchestrator["call_id"]
            or call["outcome"] != "failed"
            or call["actual_cost_usd"] is not None
            or not _is_exact_historical_int(call["provider_error_code"], 429)
            or call["provider_boundary"] != "openrouter"
            or call["expected_upstream_provider"] != "DeepInfra"
            or call["error_type"] != "OpenRouterUpstreamRejectionError"
            or call["error_invariant"] != "provider_upstream_rejection"
            or not math.isclose(
                call["latency_ms"], expected_latency, rel_tol=0, abs_tol=1e-9
            )
            or not math.isclose(
                call["estimated_cost_usd"], expected_estimate, rel_tol=0, abs_tol=1e-10
            )
        ):
            _historical_schema_error("provider call observation")
        for field in (
            "response_identity_retained",
            "response_model_retained",
            "upstream_provider_retained",
            "usage_metadata_retained",
            "actual_cost_retained",
        ):
            if call[field] is not False:
                _historical_schema_error("provider call observation")

    if (
        values["successful_upstream_provider"] != "DeepInfra"
        or values["failed_call_expected_upstream_provider"] != "DeepInfra"
        or values["failed_call_upstream_provider_identity_status"] != "not_retained"
        or not _is_exact_historical_int(values["network_call_count"], 4)
        or values["actual_cost_complete"] is not False
        or not _is_exact_historical_int(values["unknown_cost_call_count"], 2)
        or values["known_cost_included_in_aggregate"] is not True
        or values["unknown_cost_excluded_from_aggregate"] is not True
        or values["prompt_tokens"] != sum(call.get("prompt_tokens", 0) for call in calls)
        or values["completion_tokens"]
        != sum(call.get("completion_tokens", 0) for call in calls)
        or values["total_tokens"] != sum(call.get("total_tokens", 0) for call in calls)
        or values["total_tokens"] != values["prompt_tokens"] + values["completion_tokens"]
        or not math.isclose(
            values["actual_cost_usd"],
            sum(call.get("actual_cost_usd") or 0 for call in calls),
            rel_tol=0,
            abs_tol=1e-10,
        )
        or not math.isclose(values["actual_cost_usd"], 0.016428, rel_tol=0, abs_tol=1e-10)
    ):
        _historical_schema_error("provider call aggregate")


def _verify_attempt_15_provider_observation(values: dict[str, Any]) -> None:
    calls = values.get("calls")
    expected_agents = [
        "canonical_facts",
        "orchestrator_plan",
        "document_source_integrity",
        "process_decision_mapping",
        "evidence_checklist",
        "final_claim_brief_audit",
    ]
    expected_call_ids = [
        "modelcall_c64fbe8b2fe28c2d",
        "modelcall_02505ca6820a00f5",
        "modelcall_14ab428aed1c371d",
        "modelcall_57134fd6cc869742",
        "modelcall_164106a7469fa643",
        "modelcall_f117ef17925abdbb",
    ]
    expected_response_ids = [
        "gen-1786523170-cbsi6GuD1BusAnLIkxY3",
        "gen-1786523191-pY2PouJLTPlJHM5L57sE",
        "gen-1786523193-5WojdGHhBpNtrzRt1g3p",
        "gen-1786523196-zzjK26QI8SbXjXljzH3J",
        "gen-1786523198-A8vhBZHdAYRjUqqokm6I",
        "gen-1786523203-DUJCR6mmrhQUlr2ymXFf",
    ]
    expected_outcomes = [
        "succeeded_with_guarded_fallback",
        "succeeded",
        "succeeded",
        "succeeded",
        "succeeded_with_guarded_fallback",
        "succeeded",
    ]
    expected_created_at = [
        "2026-08-12T08:26:07.454775+00:00",
        "2026-08-12T08:26:29.966629+00:00",
        "2026-08-12T08:26:32.053252+00:00",
        "2026-08-12T08:26:32.057627+00:00",
        "2026-08-12T08:26:38.055861+00:00",
        "2026-08-12T08:26:42.359232+00:00",
    ]
    expected_updated_at = [
        "2026-08-12T08:26:26.358042+00:00",
        "2026-08-12T08:26:32.017882+00:00",
        "2026-08-12T08:26:36.265838+00:00",
        "2026-08-12T08:26:37.864052+00:00",
        "2026-08-12T08:26:42.307834+00:00",
        "2026-08-12T08:26:44.924203+00:00",
    ]
    if (
        not isinstance(calls, list)
        or len(calls) != 6
        or [item.get("agent_id") if isinstance(item, dict) else None for item in calls]
        != expected_agents
        or [item.get("call_id") if isinstance(item, dict) else None for item in calls]
        != expected_call_ids
        or [item.get("response_id") if isinstance(item, dict) else None for item in calls]
        != expected_response_ids
        or [item.get("outcome") if isinstance(item, dict) else None for item in calls]
        != expected_outcomes
        or [item.get("created_at") if isinstance(item, dict) else None for item in calls]
        != expected_created_at
        or [item.get("updated_at") if isinstance(item, dict) else None for item in calls]
        != expected_updated_at
    ):
        _historical_schema_error("provider call observations")

    call_ids: set[str] = set()
    response_ids: set[str] = set()
    fallback_count = 0
    for call in calls:
        agent_id = call["agent_id"]
        verified = _require_historical_fields(
            call,
            _HISTORICAL_ATTEMPT_15_CALL_FIELDS[agent_id],
            "provider call observation",
        )
        if (
            not isinstance(verified["call_id"], str)
            or _HISTORICAL_CALL_ID_PATTERN.fullmatch(verified["call_id"]) is None
            or not isinstance(verified["response_id"], str)
            or OPENROUTER_GENERATION_ID_PATTERN.fullmatch(verified["response_id"])
            is None
            or verified["response_model"] not in ACCEPTED_PRODUCTION_RESPONSE_MODELS
            or verified["upstream_provider"] != "DeepInfra"
            or verified["finish_reason"] != "stop"
            or verified["usage_source"] != "response"
            or not _is_bounded_historical_number(
                verified["latency_ms"], minimum=0.001
            )
            or not _is_historical_timestamp(verified["created_at"])
            or not _is_historical_timestamp(verified["updated_at"])
            or verified["orchestration_id"] != "orch_47fcf18494e7c1ec"
        ):
            _historical_schema_error("provider call observation")
        delegation_id = verified["delegation_id"]
        parent_call_id = verified["parent_call_id"]
        if agent_id == "canonical_facts":
            if delegation_id is not None or parent_call_id is not None:
                _historical_schema_error("provider call observation")
        elif (
            parent_call_id
            != (
                expected_call_ids[0]
                if agent_id == "orchestrator_plan"
                else expected_call_ids[1]
            )
            or not isinstance(delegation_id, str)
            or _HISTORICAL_DELEGATION_ID_PATTERN.fullmatch(delegation_id) is None
        ):
            _historical_schema_error("provider call observation")
        _verify_positive_usage(verified, "Historical provider call observation")
        if verified["total_tokens"] != (
            verified["prompt_tokens"] + verified["completion_tokens"]
        ):
            _historical_schema_error("provider call observation")
        guarded = verified["outcome"] == "succeeded_with_guarded_fallback"
        if verified["deterministic_fallback_applied"] is not guarded:
            _historical_schema_error("provider call observation")
        fallback_count += int(guarded)
        if agent_id == "canonical_facts" and (
            not _is_exact_historical_int(verified["accepted_fact_count"], 17)
            or not _is_exact_historical_int(verified["rejected_fact_count"], 1)
            or not _is_exact_historical_int(
                verified["source_reference_projection_count"], 10
            )
            or not _is_exact_historical_int(
                verified["ignored_noncontrolling_normalized_proposals"], 6
            )
        ):
            _historical_schema_error("provider call observation")
        if "accepted_item_count" in verified:
            accepted = verified["accepted_item_count"]
            rejected = verified["rejected_item_count"]
            if (
                not isinstance(accepted, int)
                or isinstance(accepted, bool)
                or not isinstance(rejected, int)
                or isinstance(rejected, bool)
                or accepted <= rejected
                or accepted <= 0
                or rejected < 0
                or (
                    "ignored_proposal_count" in verified
                    and not _is_exact_historical_int(
                        verified["ignored_proposal_count"], 0
                    )
                )
            ):
                _historical_schema_error("provider call observation")
        call_ids.add(verified["call_id"])
        response_ids.add(verified["response_id"])

    stage_handoff_sequence_valid = (
        expected_updated_at[0] < expected_created_at[1]
        and expected_updated_at[1] < expected_created_at[2]
        and expected_updated_at[2] < expected_created_at[4]
        and expected_updated_at[3] < expected_created_at[4]
        and expected_updated_at[4] < expected_created_at[5]
    )

    if (
        len(call_ids) != 6
        or len(response_ids) != 6
        or not stage_handoff_sequence_valid
        or fallback_count != 2
        or values["provider_outcome"] != "six_roles_succeeded"
        or values["upstream_provider"] != "DeepInfra"
        or not _is_exact_historical_int(values["network_call_count"], 6)
        or values["actual_cost_complete"] is not True
        or not _is_exact_historical_int(values["unknown_cost_call_count"], 0)
        or values["outcomes"]
        != {"succeeded": 4, "succeeded_with_guarded_fallback": 2}
        or not _is_exact_historical_int(values["physical_provider_max_in_flight"], 1)
        or not _is_exact_historical_int(values["application_retry_count"], 0)
        or values["prompt_tokens"]
        != sum(call["prompt_tokens"] for call in calls)
        or values["completion_tokens"]
        != sum(call["completion_tokens"] for call in calls)
        or values["total_tokens"] != sum(call["total_tokens"] for call in calls)
        or values["total_tokens"] != values["prompt_tokens"] + values["completion_tokens"]
        or not math.isclose(
            values["actual_cost_usd"],
            sum(call["actual_cost_usd"] for call in calls),
            rel_tol=0,
            abs_tol=1e-10,
        )
        or not math.isclose(
            values["actual_cost_usd"], 0.0254122, rel_tol=0, abs_tol=1e-10
        )
    ):
        _historical_schema_error("provider call aggregate")


def _verify_attempt_16_provider_observation(values: dict[str, Any]) -> None:
    calls = values.get("calls")
    expected_agents = [
        "canonical_facts",
        "orchestrator_plan",
        "process_decision_mapping",
        "document_source_integrity",
        "evidence_checklist",
        "final_claim_brief_audit",
    ]
    expected_call_ids = [
        "modelcall_1c8ccf51b4340523",
        "modelcall_ddc79b44a3f08471",
        "modelcall_485aad43dae0a528",
        "modelcall_1487c7a90b4ff77d",
        "modelcall_56141d8df3daeabc",
        "modelcall_a6940ff6be1cbfae",
    ]
    expected_response_ids = [
        "gen-1786526050-6NkNwFzkBUYXYEWjxQ7Q",
        "gen-1786526070-7hgCfawPRrXaORA70hFG",
        "gen-1786526073-Lqo3rPH9Zc2agNTwEthu",
        "gen-1786526075-rhtKDJ8yL3umOMjU8eFx",
        "gen-1786526081-TnJHzHHIomfoMLN0kUMr",
        "gen-1786526088-Q66dLOMyj4Mtnd7wS5wm",
    ]
    if (
        not isinstance(calls, list)
        or len(calls) != 6
        or [item.get("agent_id") if isinstance(item, dict) else None for item in calls]
        != expected_agents
        or [item.get("call_id") if isinstance(item, dict) else None for item in calls]
        != expected_call_ids
        or [
            item.get("response_id") if isinstance(item, dict) else None
            for item in calls
        ]
        != expected_response_ids
    ):
        _historical_schema_error("provider call observations")

    for index, call in enumerate(calls):
        agent_id = call["agent_id"]
        verified = _require_historical_fields(
            call,
            _HISTORICAL_ATTEMPT_15_CALL_FIELDS[agent_id],
            "provider call observation",
        )
        guarded = index in {0, 4}
        expected_parent = (
            None if index == 0 else expected_call_ids[0 if index == 1 else 1]
        )
        if (
            verified["orchestration_id"] != "orch_b3474368efacacda"
            or verified["parent_call_id"] != expected_parent
            or (index == 0 and verified["delegation_id"] is not None)
            or (
                index > 0
                and (
                    not isinstance(verified["delegation_id"], str)
                    or _HISTORICAL_DELEGATION_ID_PATTERN.fullmatch(
                        verified["delegation_id"]
                    )
                    is None
                )
            )
            or verified["outcome"]
            != ("succeeded_with_guarded_fallback" if guarded else "succeeded")
            or verified["deterministic_fallback_applied"] is not guarded
            or verified["response_model"] not in ACCEPTED_PRODUCTION_RESPONSE_MODELS
            or verified["upstream_provider"] != "DeepInfra"
            or verified["finish_reason"] != "stop"
            or verified["usage_source"] != "response"
            or not _is_bounded_historical_number(verified["latency_ms"], minimum=0.001)
            or not _is_historical_timestamp(verified["created_at"])
            or not _is_historical_timestamp(verified["updated_at"])
        ):
            _historical_schema_error("provider call observation")
        _verify_positive_usage(verified, "Historical provider call observation")
        if verified["total_tokens"] != (
            verified["prompt_tokens"] + verified["completion_tokens"]
        ):
            _historical_schema_error("provider call observation")
        if agent_id == "canonical_facts" and (
            not _is_exact_historical_int(verified["accepted_fact_count"], 17)
            or not _is_exact_historical_int(verified["rejected_fact_count"], 1)
            or not _is_exact_historical_int(
                verified["source_reference_projection_count"], 10
            )
            or not _is_exact_historical_int(
                verified["ignored_noncontrolling_normalized_proposals"], 0
            )
        ):
            _historical_schema_error("provider call observation")
        if "accepted_item_count" in verified and (
            not isinstance(verified["accepted_item_count"], int)
            or isinstance(verified["accepted_item_count"], bool)
            or verified["accepted_item_count"] <= verified["rejected_item_count"]
            or verified["rejected_item_count"] < 0
            or (
                "ignored_proposal_count" in verified
                and not _is_exact_historical_int(verified["ignored_proposal_count"], 0)
            )
        ):
            _historical_schema_error("provider call observation")

    if (
        values["provider_outcome"] != "six_roles_succeeded"
        or values["upstream_provider"] != "DeepInfra"
        or not _is_exact_historical_int(values["network_call_count"], 6)
        or values["actual_cost_complete"] is not True
        or not _is_exact_historical_int(values["unknown_cost_call_count"], 0)
        or values["outcomes"] != {"succeeded": 4, "succeeded_with_guarded_fallback": 2}
        or not _is_exact_historical_int(values["physical_provider_max_in_flight"], 1)
        or not _is_exact_historical_int(values["application_retry_count"], 0)
        or values["prompt_tokens"] != sum(call["prompt_tokens"] for call in calls)
        or values["completion_tokens"]
        != sum(call["completion_tokens"] for call in calls)
        or values["total_tokens"] != sum(call["total_tokens"] for call in calls)
        or values["total_tokens"]
        != values["prompt_tokens"] + values["completion_tokens"]
        or not math.isclose(
            values["actual_cost_usd"],
            sum(call["actual_cost_usd"] for call in calls),
            rel_tol=0,
            abs_tol=1e-10,
        )
        or not math.isclose(
            values["actual_cost_usd"], 0.0236984, rel_tol=0, abs_tol=1e-10
        )
    ):
        _historical_schema_error("provider call aggregate")


def _verify_attempt_17_provider_observation(values: dict[str, Any]) -> None:
    calls = values.get("calls")
    expected_agents = [
        "canonical_facts",
        "orchestrator_plan",
        "document_source_integrity",
        "process_decision_mapping",
        "evidence_checklist",
    ]
    expected_call_ids = [
        "modelcall_1a86f535db81984c",
        "modelcall_ef480b12358d325e",
        "modelcall_012b7a5523628d6b",
        "modelcall_9e3ada6a84519278",
        "modelcall_a91022b32cf47215",
    ]
    expected_response_ids = [
        "gen-1786529280-uGzNPF2ZCY54LcsTZEbS",
        "gen-1786529306-pWJvW6D5enjRbiwXKd8Q",
        "gen-1786529315-nBI3kJ2WJJyP1RnuoQ2A",
        "gen-1786529312-N1598aWPxvOS8ERprQvw",
        "gen-1786529324-2J6kUN6zNOoL7vpGLPFq",
    ]
    if (
        not isinstance(calls, list)
        or len(calls) != 5
        or [call.get("agent_id") if isinstance(call, dict) else None for call in calls]
        != expected_agents
        or [call.get("call_id") if isinstance(call, dict) else None for call in calls]
        != expected_call_ids
        or [call.get("response_id") if isinstance(call, dict) else None for call in calls]
        != expected_response_ids
    ):
        _historical_schema_error("provider call observations")

    for index, call in enumerate(calls):
        agent_id = call["agent_id"]
        fields = (
            _HISTORICAL_ATTEMPT_17_FAILED_CALL_FIELDS
            if agent_id == "evidence_checklist"
            else _HISTORICAL_ATTEMPT_15_CALL_FIELDS[agent_id]
        )
        verified = _require_historical_fields(
            call, fields, "provider call observation"
        )
        expected_parent = None if index == 0 else expected_call_ids[0 if index == 1 else 1]
        if (
            verified["orchestration_id"] != "orch_03c1bbb4a9e4269b"
            or verified["parent_call_id"] != expected_parent
            or (index == 0 and verified["delegation_id"] is not None)
            or (
                index > 0
                and (
                    not isinstance(verified["delegation_id"], str)
                    or _HISTORICAL_DELEGATION_ID_PATTERN.fullmatch(
                        verified["delegation_id"]
                    )
                    is None
                )
            )
            or verified["outcome"] != ("failed" if index == 4 else "succeeded")
            or verified["response_model"] not in ACCEPTED_PRODUCTION_RESPONSE_MODELS
            or verified["upstream_provider"] != "DeepInfra"
            or verified["finish_reason"] != "stop"
            or verified["usage_source"] != "response"
            or not _is_bounded_historical_number(verified["latency_ms"], minimum=0.001)
            or not _is_historical_timestamp(verified["created_at"])
            or not _is_historical_timestamp(verified["updated_at"])
        ):
            _historical_schema_error("provider call observation")
        _verify_positive_usage(verified, "Historical provider call observation")
        if verified["total_tokens"] != (
            verified["prompt_tokens"] + verified["completion_tokens"]
        ):
            _historical_schema_error("provider call observation")

    canonical = calls[0]
    if (
        canonical["deterministic_fallback_applied"] is not False
        or not _is_exact_historical_int(canonical["accepted_fact_count"], 18)
        or not _is_exact_historical_int(canonical["rejected_fact_count"], 0)
        or not _is_exact_historical_int(
            canonical["source_reference_projection_count"], 11
        )
        or not _is_exact_historical_int(
            canonical["ignored_noncontrolling_normalized_proposals"], 1
        )
    ):
        _historical_schema_error("provider call observation")
    for call, accepted in zip(calls[1:4], (1, 6, 6)):
        if (
            call["deterministic_fallback_applied"] is not False
            or not _is_exact_historical_int(call["accepted_item_count"], accepted)
            or not _is_exact_historical_int(call["rejected_item_count"], 0)
            or not _is_exact_historical_int(call["ignored_proposal_count"], 0)
        ):
            _historical_schema_error("provider call observation")

    rejected_items = [
        {"item_id": f"item:{item_id}:{field}", "invariant": "evidence_contract"}
        for item_id in _HISTORICAL_ATTEMPT_17_EVIDENCE_ITEM_IDS
        for field in ("status", "artifacts")
    ]
    evidence = calls[4]
    if (
        evidence["error_type"] != "AgentBoundaryError"
        or evidence["error_invariant"] != "model_contribution_majority"
        or evidence["authority_mode"] != "multi_agent_hybrid_guarded"
        or evidence["accepted_item_ids"] != []
        or not _is_exact_historical_int(evidence["accepted_item_count"], 0)
        or evidence["rejected_items"] != rejected_items
        or not _is_exact_historical_int(evidence["rejected_item_count"], 42)
        or not _is_exact_historical_int(evidence["ignored_proposal_count"], 0)
    ):
        _historical_schema_error("provider call observation")

    if (
        calls[0]["updated_at"] >= calls[1]["created_at"]
        or calls[1]["updated_at"] >= min(
            calls[2]["created_at"], calls[3]["created_at"]
        )
        or max(calls[2]["updated_at"], calls[3]["updated_at"])
        >= calls[4]["created_at"]
        or values["provider_outcome"]
        != "four_successes_then_evidence_majority_rejected"
        or values["upstream_provider"] != "DeepInfra"
        or not _is_exact_historical_int(values["network_call_count"], 5)
        or values["actual_cost_complete"] is not True
        or not _is_exact_historical_int(values["unknown_cost_call_count"], 0)
        or values["outcomes"] != {"succeeded": 4, "failed": 1}
        or not _is_exact_historical_int(values["physical_provider_max_in_flight"], 1)
        or not _is_exact_historical_int(values["application_retry_count"], 0)
        or values["prompt_tokens"] != sum(call["prompt_tokens"] for call in calls)
        or values["completion_tokens"]
        != sum(call["completion_tokens"] for call in calls)
        or values["total_tokens"] != sum(call["total_tokens"] for call in calls)
        or values["total_tokens"]
        != values["prompt_tokens"] + values["completion_tokens"]
        or not math.isclose(
            values["actual_cost_usd"],
            sum(call["actual_cost_usd"] for call in calls),
            rel_tol=0,
            abs_tol=1e-10,
        )
        or not math.isclose(
            values["actual_cost_usd"], 0.0201973, rel_tol=0, abs_tol=1e-10
        )
    ):
        _historical_schema_error("provider call aggregate")


def _verify_attempt_18_provider_observation(values: dict[str, Any]) -> None:
    calls = values.get("calls")
    expected_agents = [
        "canonical_facts",
        "orchestrator_plan",
        "document_source_integrity",
        "process_decision_mapping",
    ]
    expected_call_ids = [
        "modelcall_9bd92468cc8f038c",
        "modelcall_9a169372b9992d0c",
        "modelcall_4abdccd0ab5d8d6f",
        "modelcall_179aca2903b5588c",
    ]
    expected_response_ids = [
        "gen-1786532378-C6etEzhbHwQVX9VzhCWB",
        "gen-1786532398-Fq3t3Lh1cWcEQjbJ6XdS",
        "gen-1786532401-OHjtmk6aiCms72NZ62rn",
        "gen-1786532428-rqSoDh7EoPG9mZJWj7PJ",
    ]
    if (
        not isinstance(calls, list)
        or len(calls) != 4
        or [call.get("agent_id") if isinstance(call, dict) else None for call in calls]
        != expected_agents
        or [call.get("call_id") if isinstance(call, dict) else None for call in calls]
        != expected_call_ids
        or [call.get("response_id") if isinstance(call, dict) else None for call in calls]
        != expected_response_ids
    ):
        _historical_schema_error("provider call observations")

    expected_parents = [
        None,
        expected_call_ids[0],
        expected_call_ids[1],
        expected_call_ids[1],
    ]
    for index, call in enumerate(calls):
        agent_id = call["agent_id"]
        if agent_id == "document_source_integrity":
            fields = _HISTORICAL_ATTEMPT_18_FAILED_CALL_FIELDS
        elif agent_id == "process_decision_mapping":
            fields = _HISTORICAL_ATTEMPT_18_PROCESS_CALL_FIELDS
        else:
            fields = _HISTORICAL_ATTEMPT_15_CALL_FIELDS[agent_id]
        verified = _require_historical_fields(
            call, fields, "provider call observation"
        )
        if (
            verified["orchestration_id"] != "orch_2ca291c7f62ef75a"
            or verified["parent_call_id"] != expected_parents[index]
            or (index == 0 and verified["delegation_id"] is not None)
            or (
                index > 0
                and (
                    not isinstance(verified["delegation_id"], str)
                    or _HISTORICAL_DELEGATION_ID_PATTERN.fullmatch(
                        verified["delegation_id"]
                    )
                    is None
                )
            )
            or verified["outcome"] != ("failed" if index == 2 else "succeeded")
            or verified["response_model"] not in ACCEPTED_PRODUCTION_RESPONSE_MODELS
            or verified["upstream_provider"] != "DeepInfra"
            or verified["finish_reason"] != ("length" if index == 2 else "stop")
            or verified["usage_source"] != "response"
            or not _is_bounded_historical_number(
                verified["latency_ms"], minimum=0.001
            )
            or not _is_historical_timestamp(verified["created_at"])
            or not _is_historical_timestamp(verified["updated_at"])
        ):
            _historical_schema_error("provider call observation")
        _verify_positive_usage(verified, "Historical provider call observation")
        if verified["total_tokens"] != (
            verified["prompt_tokens"] + verified["completion_tokens"]
        ):
            _historical_schema_error("provider call observation")

    canonical, plan, document, process = calls
    if (
        canonical["deterministic_fallback_applied"] is not False
        or not _is_exact_historical_int(canonical["accepted_fact_count"], 18)
        or not _is_exact_historical_int(canonical["rejected_fact_count"], 0)
        or not _is_exact_historical_int(
            canonical["source_reference_projection_count"], 11
        )
        or not _is_exact_historical_int(
            canonical["ignored_noncontrolling_normalized_proposals"], 1
        )
        or plan["deterministic_fallback_applied"] is not False
        or not _is_exact_historical_int(plan["accepted_item_count"], 1)
        or not _is_exact_historical_int(plan["rejected_item_count"], 0)
        or not _is_exact_historical_int(plan["ignored_proposal_count"], 0)
        or document["deterministic_fallback_applied"] is not False
        or document["semantic_scoring_started"] is not False
        or document["error_type"] != "AgentBoundaryError"
        or document["error_invariant"] != "provider_finish_reason"
        or not _is_exact_historical_int(document["completion_tokens"], 4096)
        or process["deterministic_fallback_applied"] is not False
        or process["accepted_item_ids"]
        != [
            "fact:fact_tenancy:decision_value",
            "fact:fact_dispute:decision_value",
            "fact:fact_recurrence:decision_value",
            "fact:fact_notification:decision_value",
            "fact:fact_cause:decision_value",
            "fact:fact_health:decision_value",
        ]
        or not _is_exact_historical_int(process["accepted_item_count"], 6)
        or not _is_exact_historical_int(process["rejected_item_count"], 0)
        or not _is_exact_historical_int(process["ignored_proposal_count"], 0)
    ):
        _historical_schema_error("provider call observation")

    if (
        canonical["updated_at"] >= plan["created_at"]
        or plan["updated_at"] >= min(document["created_at"], process["created_at"])
        or document["created_at"] >= process["created_at"]
        or document["updated_at"] >= process["updated_at"]
        or values["provider_outcome"]
        != "three_successes_one_document_length_rejected"
        or values["upstream_provider"] != "DeepInfra"
        or not _is_exact_historical_int(values["network_call_count"], 4)
        or values["actual_cost_complete"] is not True
        or not _is_exact_historical_int(values["unknown_cost_call_count"], 0)
        or values["outcomes"] != {"succeeded": 3, "failed": 1}
        or not _is_exact_historical_int(values["physical_provider_max_in_flight"], 1)
        or not _is_exact_historical_int(values["application_retry_count"], 0)
        or values["prompt_tokens"] != sum(call["prompt_tokens"] for call in calls)
        or values["completion_tokens"]
        != sum(call["completion_tokens"] for call in calls)
        or values["total_tokens"] != sum(call["total_tokens"] for call in calls)
        or values["total_tokens"]
        != values["prompt_tokens"] + values["completion_tokens"]
        or not math.isclose(
            values["actual_cost_usd"],
            sum(call["actual_cost_usd"] for call in calls),
            rel_tol=0,
            abs_tol=1e-10,
        )
        or not math.isclose(
            values["actual_cost_usd"], 0.0273757, rel_tol=0, abs_tol=1e-10
        )
    ):
        _historical_schema_error("provider call aggregate")


def _verify_historical_provider_observation(
    attempt_id: str,
    provider: Any,
) -> None:
    values = _require_historical_fields(
        provider,
        _HISTORICAL_PROVIDER_FIELDS[attempt_id],
        "provider observation",
    )
    if "provider" in values and values["provider"] != "openrouter":
        _historical_schema_error("provider observation")
    expected_outcome = _HISTORICAL_PROVIDER_OUTCOMES.get(attempt_id)
    if expected_outcome is not None and values.get("provider_outcome") != expected_outcome:
        _historical_schema_error("provider observation")
    for field in ("canonical_model_id", "model"):
        if field in values and values[field] != (
            "nvidia/nemotron-3-ultra-550b-a55b-20260604"
        ):
            _historical_schema_error("provider observation")
    if "requested_model" in values and values["requested_model"] != REQUIRED_PRODUCTION_MODEL:
        _historical_schema_error("provider observation")
    if (
        "response_model" in values
        and values["response_model"] not in ACCEPTED_PRODUCTION_RESPONSE_MODELS
    ):
        _historical_schema_error("provider observation")
    if "response_id" in values and (
        not isinstance(values["response_id"], str)
        or OPENROUTER_GENERATION_ID_PATTERN.fullmatch(values["response_id"]) is None
    ):
        _historical_schema_error("provider observation")
    if "upstream_provider" in values and values["upstream_provider"] != "DeepInfra":
        _historical_schema_error("provider observation")
    if "finish_reason" in values and values["finish_reason"] != "stop":
        _historical_schema_error("provider observation")
    if "usage_source" in values and values["usage_source"] != "response":
        _historical_schema_error("provider observation")
    present_usage = {
        "actual_cost_usd",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    }.intersection(values)
    if present_usage:
        _verify_positive_usage(values, "Historical provider observation")
        if values["actual_cost_usd"] > 25 or values["total_tokens"] > 10_000_000:
            _historical_schema_error("provider observation")
    if attempt_id in _HISTORICAL_TWO_CALL_OUTPUT_LIMITS:
        _verify_two_call_provider_observation(attempt_id, values)
    if attempt_id == "production-flagship-20260811-12":
        _verify_attempt_12_provider_observation(values)
    if attempt_id == "production-flagship-20260812-13":
        _verify_attempt_13_provider_observation(values)
    if attempt_id == "production-flagship-20260812-14":
        _verify_attempt_14_provider_observation(values)
    if attempt_id == "production-flagship-20260812-15":
        _verify_attempt_15_provider_observation(values)
    if attempt_id == "production-flagship-20260812-16":
        _verify_attempt_16_provider_observation(values)
    if attempt_id == "production-flagship-20260812-17":
        _verify_attempt_17_provider_observation(values)
    if attempt_id == "production-flagship-20260812-18":
        _verify_attempt_18_provider_observation(values)
    if "latency_ms" in values and not _is_bounded_historical_number(
        values["latency_ms"], minimum=0.001
    ):
        _historical_schema_error("provider observation")
    if "estimated_cost_reservation_usd" in values and not _is_bounded_historical_number(
        values["estimated_cost_reservation_usd"], minimum=0.000_000_01, maximum=25
    ):
        _historical_schema_error("provider observation")
    expected_booleans = {
        "synchronous_usage_cost_present": False,
        "new_openrouter_log_generation_observed": False,
        "charge_included_in_known_aggregate": False,
        "estimated_reservation_is_actual_charge": False,
        "openrouter_upstream_request_log_observed": True,
    }
    for field, expected in expected_booleans.items():
        if field in values and values[field] is not expected:
            _historical_schema_error("provider observation")
    if "openrouter_log_check_performed" in values:
        expected = attempt_id in {
            "production-flagship-20260811-09",
            "production-flagship-20260812-13",
        }
        if values["openrouter_log_check_performed"] is not expected:
            _historical_schema_error("provider observation")
    expected_cache_assessment = {
        "authorized-smoke-20260811-03": "likely_unconfirmed",
        "production-flagship-20260811-07": "not_assessed",
        "production-flagship-20260811-09": "not_applicable_upstream_rejected",
        "production-flagship-20260812-13": "not_applicable_upstream_rejected",
    }.get(attempt_id)
    if (
        expected_cache_assessment is not None
        and values.get("provider_cache_replay_assessment") != expected_cache_assessment
    ):
        _historical_schema_error("provider observation")
    if "charge_status" in values and values["charge_status"] != "unknown_unconfirmed":
        _historical_schema_error("provider observation")
    if "response_http_status" in values and not _is_exact_historical_int(
        values["response_http_status"], 200
    ):
        _historical_schema_error("provider observation")
    if "sdk" in values and values["sdk"] != "openrouter":
        _historical_schema_error("provider observation")
    if "sdk_version" in values and values["sdk_version"] != "0.11.46":
        _historical_schema_error("provider observation")
    if "sdk_error_type" in values and values["sdk_error_type"] != "ResponseValidationError":
        _historical_schema_error("provider observation")
    expected_identity_status = {
        "production-flagship-20260811-07": "unknown_unverified",
        "production-flagship-20260811-09": "upstream_request_only_no_generation",
        "production-flagship-20260812-13": "upstream_request_only_no_generation",
    }.get(attempt_id)
    if (
        expected_identity_status is not None
        and values.get("response_identity_status") != expected_identity_status
    ):
        _historical_schema_error("provider observation")
    if "bounded_generation_metadata_lookup" in values and values[
        "bounded_generation_metadata_lookup"
    ] != "not_available_before_deadline":
        _historical_schema_error("provider observation")

    later = values.get("later_generation_metadata_observation")
    if later is not None:
        later = _require_historical_fields(
            later,
            frozenset(
                "read_only response_id model provider_name actual_cost_usd prompt_tokens "
                "completion_tokens total_tokens finish_reason same_generation_confirmed "
                "available_after_bounded_lookup".split()
            ),
            "later generation observation",
        )
        if (
            later["read_only"] is not True
            or later["response_id"] != values.get("response_id")
            or later["model"] != "nvidia/nemotron-3-ultra-550b-a55b-20260604"
            or later["provider_name"] != "DeepInfra"
            or later["finish_reason"] != "stop"
            or later["same_generation_confirmed"] is not True
            or later["available_after_bounded_lookup"] is not True
        ):
            _historical_schema_error("later generation observation")
        _verify_positive_usage(later, "Historical later generation observation")
        for field in (
            "actual_cost_usd",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
        ):
            if later[field] != values[field]:
                _historical_schema_error("later generation observation")

    routing = values.get("routing_diagnosis")
    if routing is not None:
        routing = _require_historical_fields(
            routing,
            frozenset(
                {
                    "attempt_09_policy",
                    "prior_deepinfra_request_status",
                    "exact_internal_provider_error_message_observed",
                }
            ),
            "routing diagnosis",
        )
        if (
            routing["attempt_09_policy"] != "default_provider_routing"
            or not _is_exact_historical_int(
                routing["prior_deepinfra_request_status"], 200
            )
            or routing["exact_internal_provider_error_message_observed"] is not False
        ):
            _historical_schema_error("routing diagnosis")

    upstream_log = values.get("upstream_request_log_observation")
    if upstream_log is not None:
        upstream_log = _require_historical_fields(
            upstream_log,
            frozenset(
                "read_only displayed_at_local request_id final_provider upstream_status "
                "router_attempts router_latency_ms".split()
            ),
            "upstream request observation",
        )
        expected_upstream = {
            "production-flagship-20260811-09": ("Together", 400, 2, 759),
            "production-flagship-20260812-13": ("DeepInfra", 429, 1, 235),
        }.get(attempt_id)
        if (
            expected_upstream is None
            or upstream_log["read_only"] is not True
            or not isinstance(upstream_log["displayed_at_local"], str)
            or _HISTORICAL_LOCAL_TIME_PATTERN.fullmatch(
                upstream_log["displayed_at_local"]
            )
            is None
            or not isinstance(upstream_log["request_id"], str)
            or OPENROUTER_GENERATION_ID_PATTERN.fullmatch(upstream_log["request_id"])
            is None
            or upstream_log["final_provider"] != expected_upstream[0]
            or not _is_exact_historical_int(
                upstream_log["upstream_status"], expected_upstream[1]
            )
            or not _is_exact_historical_int(
                upstream_log["router_attempts"], expected_upstream[2]
            )
            or not _is_bounded_historical_number(upstream_log["router_latency_ms"])
            or not math.isclose(
                upstream_log["router_latency_ms"],
                expected_upstream[3],
                rel_tol=0,
                abs_tol=1e-9,
            )
        ):
            _historical_schema_error("upstream request observation")
        if attempt_id == "production-flagship-20260812-13" and (
            upstream_log["displayed_at_local"]
            != "2026-08-12 02:49 Europe/Zurich"
            or upstream_log["request_id"]
            != "gen-1786495797-wwTpDFx93vAismEWwWvY"
        ):
            _historical_schema_error("upstream request observation")

    generation_lookup = values.get("generation_metadata_lookup")
    if generation_lookup is not None:
        generation_lookup = _require_historical_fields(
            generation_lookup,
            frozenset("read_only request_id http_status generation_recovered".split()),
            "generation lookup",
        )
        if (
            generation_lookup["read_only"] is not True
            or upstream_log is None
            or generation_lookup["request_id"] != upstream_log["request_id"]
            or not _is_exact_historical_int(generation_lookup["http_status"], 404)
            or generation_lookup["generation_recovered"] is not False
        ):
            _historical_schema_error("generation lookup")


def _verify_historical_application_result(
    attempt_id: str,
    result: Any,
) -> None:
    values = _require_historical_fields(
        result,
        _HISTORICAL_APPLICATION_FIELDS[attempt_id],
        "application result",
    )
    if attempt_id == "production-flagship-20260812-22":
        if values != {
            "outcome": "accepted",
            "successful_ledger_calls_bound": True,
            "required_model_roles_complete": True,
            "cold_model_call_count": 12,
            "warm_cache_hit_count": 12,
            "deterministic_gates_complete": True,
            "complete_deterministic_gate_ids": [
                "deterministic_process_gate",
                "deterministic_evidence_gate",
                "whole_playbook_gate",
            ],
            "full_orchestration_accepted": True,
            "runtime_acceptance_established": False,
        }:
            _historical_schema_error("application result")
        return
    if attempt_id == "production-flagship-20260812-23":
        if values != {
            "outcome": "rejected",
            "failure_type": "canonical_facts_hybrid_model_contribution",
            "error_type": "ModelResponseError",
            "error_invariant": "hybrid_model_contribution",
            "successful_ledger_call_bound": False,
            "ledger_call_id": "modelcall_08eaec8a9743413e",
            "ledger_outcome": "failed",
            "canonical_result_accepted": False,
            "accepted_fact_count": 1,
            "rejected_fact_count": 17,
            "downstream_execution_started": False,
            "warm_replay_started": False,
            "full_orchestration_accepted": False,
            "runtime_acceptance_established": False,
        }:
            _historical_schema_error("application result")
        return
    if attempt_id == "production-flagship-20260812-24":
        if values != {
            "outcome": "rejected",
            "failure_type": (
                "later_orchestrator_upstream_429_followed_by_terminal_ui_timeout"
            ),
            "error_type": "OpenRouterUpstreamRejectionError",
            "error_invariant": "provider_upstream_rejection",
            "successful_ledger_call_bound": False,
            "ledger_call_id": "modelcall_b5cbda5d8b277ba3",
            "ledger_outcome": "failed",
            "flagship_cold_accepted": True,
            "flagship_cold_call_ids": [
                "modelcall_c903756dd0188c53",
                "modelcall_a0246daa7e5c6e76",
                "modelcall_0a9b5eaa94b54481",
                "modelcall_b9d68d39d9608e31",
                "modelcall_ee9cd0b8a8e50df4",
                "modelcall_7db7c54ed4c7ea3e",
            ],
            "flagship_model_roles_complete": True,
            "flagship_deterministic_gates_complete": True,
            "complete_flagship_deterministic_gate_ids": [
                "deterministic_process_gate",
                "deterministic_evidence_gate",
                "whole_playbook_gate",
            ],
            "flagship_warm_cache_accepted": True,
            "later_canonical_result_accepted": True,
            "later_canonical_call_id": "modelcall_5b379786dee0e98e",
            "later_canonical_accepted_fact_count": 16,
            "later_canonical_rejected_fact_count": 0,
            "later_orchestrator_plan_accepted": False,
            "failed_ledger_call_id": "modelcall_b5cbda5d8b277ba3",
            "failed_ledger_outcome": "failed",
            "later_downstream_execution_started": False,
            "later_deterministic_gates_started": False,
            "later_warm_replay_started": False,
            "full_production_journey_accepted": False,
            "runtime_acceptance_established": False,
        }:
            _historical_schema_error("application result")
        return
    if attempt_id == "production-flagship-20260812-21":
        if values != {
            "outcome": "accepted",
            "successful_ledger_calls_bound": True,
            "required_model_roles_complete": True,
            "complete_model_call_ids": [
                "modelcall_65445b4325a63b55",
                "modelcall_72b8a981b6761fbb",
                "modelcall_f26eb00dd83bee2e",
                "modelcall_16f7a39f9e7468e7",
                "modelcall_64a68452108c1398",
                "modelcall_8336fe1cb9af025c",
            ],
            "deterministic_gates_complete": True,
            "complete_deterministic_gate_ids": [
                "deterministic_process_gate",
                "deterministic_evidence_gate",
                "whole_playbook_gate",
            ],
            "deterministic_gate_progression_observed": True,
            "deterministic_gate_artifact_hashes_retained": False,
            "deterministic_gate_artifact_hashes_recoverable": False,
            "full_orchestration_accepted": True,
            "runtime_acceptance_established": False,
        }:
            _historical_schema_error("application result")
        return
    if attempt_id == "production-flagship-20260812-20":
        if values != {
            "outcome": "accepted",
            "successful_ledger_calls_bound": True,
            "required_model_roles_complete": True,
            "complete_model_call_ids": [
                "modelcall_807d4dbfef8e02f8",
                "modelcall_c656a74f55c31f5f",
                "modelcall_97a8da9ae5b2b143",
                "modelcall_4c301e098305395a",
                "modelcall_c6f4a5905bd26363",
                "modelcall_9f906ebed62d1b21",
            ],
            "deterministic_gates_complete": True,
            "complete_deterministic_gate_ids": [
                "deterministic_process_gate",
                "deterministic_evidence_gate",
                "whole_playbook_gate",
            ],
            "deterministic_gate_progression_observed": True,
            "deterministic_gate_artifact_hashes_retained": False,
            "deterministic_gate_artifact_hashes_recoverable": False,
            "full_orchestration_accepted": True,
            "runtime_acceptance_established": False,
        }:
            _historical_schema_error("application result")
        return
    if attempt_id == "production-flagship-20260812-19":
        if values != {
            "outcome": "accepted",
            "successful_ledger_calls_bound": True,
            "required_model_roles_complete": True,
            "complete_model_call_ids": [
                "modelcall_21d1532faf37c5ea",
                "modelcall_bd9a2ae01500cde7",
                "modelcall_9bd09c6d93c753e8",
                "modelcall_8895dc310a584324",
                "modelcall_50b326c4e791cc61",
                "modelcall_82808efe99c0563c",
            ],
            "deterministic_gates_complete": True,
            "complete_deterministic_gate_ids": [
                "deterministic_process_gate",
                "deterministic_evidence_gate",
                "whole_playbook_gate",
            ],
            "full_orchestration_accepted": True,
            "runtime_acceptance_established": False,
        }:
            _historical_schema_error("application result")
        return
    if attempt_id == "production-flagship-20260812-15":
        if values != {
            "outcome": "accepted",
            "successful_ledger_calls_bound": True,
            "required_model_roles_complete": True,
            "complete_model_call_ids": [
                "modelcall_c64fbe8b2fe28c2d",
                "modelcall_02505ca6820a00f5",
                "modelcall_14ab428aed1c371d",
                "modelcall_57134fd6cc869742",
                "modelcall_164106a7469fa643",
                "modelcall_f117ef17925abdbb",
            ],
            "deterministic_gates_complete": True,
            "complete_deterministic_gate_ids": [
                "deterministic_process_gate",
                "deterministic_evidence_gate",
                "whole_playbook_gate",
            ],
            "full_orchestration_accepted": True,
            "runtime_acceptance_established": False,
        }:
            _historical_schema_error("application result")
        return
    if attempt_id == "production-flagship-20260812-18":
        if values != {
            "outcome": "rejected",
            "failure_type": "document_source_integrity_truncated_at_output_limit",
            "error_type": "AgentBoundaryError",
            "error_invariant": "provider_finish_reason",
            "successful_ledger_call_bound": False,
            "ledger_call_id": "modelcall_4abdccd0ab5d8d6f",
            "ledger_outcome": "failed",
            "canonical_stage_completed": True,
            "canonical_stage_call_id": "modelcall_9bd92468cc8f038c",
            "orchestrator_plan_accepted": True,
            "orchestrator_plan_call_id": "modelcall_9a169372b9992d0c",
            "parallel_specialists_started": True,
            "document_source_integrity_accepted": False,
            "document_source_integrity_call_id": "modelcall_4abdccd0ab5d8d6f",
            "document_semantic_scoring_started": False,
            "document_deterministic_fallback_applied": False,
            "process_decision_mapping_output_succeeded": True,
            "process_decision_mapping_call_id": "modelcall_179aca2903b5588c",
            "process_completion_receipt_observed": False,
            "deterministic_process_gate_started": False,
            "evidence_checklist_started": False,
            "final_model_role_started": False,
            "whole_playbook_gate_started": False,
            "warm_replay_started": False,
            "full_orchestration_accepted": False,
            "runtime_acceptance_established": False,
            "downstream_execution_started": True,
            "later_model_calls_after_failure": False,
        }:
            _historical_schema_error("application result")
        return
    if attempt_id == "production-flagship-20260812-17":
        if values != {
            "outcome": "rejected",
            "failure_type": "evidence_checklist_model_contribution_majority",
            "error_type": "AgentBoundaryError",
            "error_invariant": "model_contribution_majority",
            "successful_ledger_call_bound": False,
            "ledger_call_id": "modelcall_a91022b32cf47215",
            "ledger_outcome": "failed",
            "canonical_stage_completed": True,
            "canonical_stage_call_id": "modelcall_1a86f535db81984c",
            "orchestrator_plan_accepted": True,
            "orchestrator_plan_call_id": "modelcall_ef480b12358d325e",
            "document_source_integrity_accepted": True,
            "document_source_integrity_call_id": "modelcall_012b7a5523628d6b",
            "process_decision_mapping_accepted": True,
            "process_decision_mapping_call_id": "modelcall_9e3ada6a84519278",
            "deterministic_process_gate_passed": True,
            "evidence_checklist_accepted": False,
            "evidence_checklist_call_id": "modelcall_a91022b32cf47215",
            "evidence_contribution_diagnostics_retained": True,
            "evidence_accepted_item_count": 0,
            "evidence_rejected_item_count": 42,
            "deterministic_evidence_gate_started": False,
            "final_model_role_started": False,
            "whole_playbook_gate_started": False,
            "warm_replay_started": False,
            "full_orchestration_accepted": False,
            "runtime_acceptance_established": False,
            "downstream_execution_started": True,
            "later_model_calls_after_failure": False,
        }:
            _historical_schema_error("application result")
        return
    if attempt_id == "production-flagship-20260812-16":
        if values != {
            "outcome": "accepted",
            "successful_ledger_calls_bound": True,
            "required_model_roles_complete": True,
            "complete_model_call_ids": [
                "modelcall_1c8ccf51b4340523",
                "modelcall_ddc79b44a3f08471",
                "modelcall_485aad43dae0a528",
                "modelcall_1487c7a90b4ff77d",
                "modelcall_56141d8df3daeabc",
                "modelcall_a6940ff6be1cbfae",
            ],
            "deterministic_gates_complete": True,
            "complete_deterministic_gate_ids": [
                "deterministic_process_gate",
                "deterministic_evidence_gate",
                "whole_playbook_gate",
            ],
            "full_orchestration_accepted": True,
            "runtime_acceptance_established": False,
        }:
            _historical_schema_error("application result")
        return
    if (
        values["outcome"] != "rejected"
        or values["failure_type"] != _HISTORICAL_FAILURE_TYPES[attempt_id]
        or values["successful_ledger_call_bound"] is not False
    ):
        _historical_schema_error("application result")
    expected_error_type = _HISTORICAL_ERROR_TYPES.get(attempt_id)
    if expected_error_type is not None and values.get("error_type") != expected_error_type:
        _historical_schema_error("application result")
    expected_invariant = _HISTORICAL_ERROR_INVARIANTS.get(attempt_id)
    if expected_invariant is not None and values.get("error_invariant") != expected_invariant:
        _historical_schema_error("application result")
    ledger_call_id = values.get("ledger_call_id")
    if ledger_call_id is not None and (
        not isinstance(ledger_call_id, str)
        or _HISTORICAL_CALL_ID_PATTERN.fullmatch(ledger_call_id) is None
    ):
        _historical_schema_error("application result")
    if "ledger_outcome" in values and values["ledger_outcome"] != "failed":
        _historical_schema_error("application result")
    expected_booleans: dict[str, bool] = {
        "canonical_result_accepted": False,
        "upstream_provider_persisted": False,
        "contribution_diagnostics_retained": False,
        "accepted_generation_recovered": False,
    }
    if attempt_id in {
        "production-flagship-20260811-07",
        "production-flagship-20260811-08",
        "production-flagship-20260811-09",
    }:
        retained = attempt_id == "production-flagship-20260811-08"
        expected_booleans["response_identity_retained"] = retained
        expected_booleans["usage_metadata_retained"] = retained
    if "later_generation_metadata_verified" in values:
        expected_booleans["later_generation_metadata_verified"] = True
    if attempt_id in _HISTORICAL_TWO_CALL_OUTPUT_LIMITS:
        expected_booleans.update(
            {
                "canonical_stage_completed": True,
                "canonical_guarded_fallback_applied": True,
                "canonical_contribution_diagnostics_retained": True,
                "orchestrator_plan_accepted": False,
                "full_orchestration_accepted": False,
                "runtime_acceptance_established": False,
                "downstream_execution_started": False,
            }
        )
        canonical_call_id = values.get("canonical_stage_call_id")
        if (
            values.get("canonical_stage_outcome")
            != "succeeded_with_guarded_fallback"
            or not isinstance(canonical_call_id, str)
            or _HISTORICAL_CALL_ID_PATTERN.fullmatch(canonical_call_id) is None
        ):
            _historical_schema_error("application result")
    if attempt_id == "production-flagship-20260811-12":
        expected_booleans.update(
            {
                "canonical_stage_completed": True,
                "canonical_guarded_fallback_applied": True,
                "canonical_contribution_diagnostics_retained": True,
                "orchestrator_plan_accepted": True,
                "document_source_integrity_accepted": True,
                "process_decision_mapping_accepted": False,
                "full_orchestration_accepted": False,
                "runtime_acceptance_established": False,
                "downstream_execution_started": True,
                "later_model_calls_after_failure": False,
            }
        )
        if values.get("canonical_stage_outcome") != "succeeded_with_guarded_fallback":
            _historical_schema_error("application result")
        for field in (
            "canonical_stage_call_id",
            "orchestrator_plan_call_id",
            "document_source_integrity_call_id",
        ):
            call_id = values.get(field)
            if (
                not isinstance(call_id, str)
                or _HISTORICAL_CALL_ID_PATTERN.fullmatch(call_id) is None
            ):
                _historical_schema_error("application result")
    if attempt_id == "production-flagship-20260812-13":
        expected_booleans.update(
            {
                "error_invariant_retained": False,
                "canonical_stage_completed": False,
                "response_identity_retained": False,
                "usage_metadata_retained": False,
                "actual_cost_retained": False,
                "full_orchestration_accepted": False,
                "runtime_acceptance_established": False,
                "downstream_execution_started": False,
                "deterministic_gates_started": False,
            }
        )
        if values.get("external_cause_detail") != "unknown":
            _historical_schema_error("application result")
        if values != {
            "outcome": "rejected",
            "failure_type": "external_deepinfra_http_429",
            "error_type": "TooManyRequestsResponseError",
            "error_invariant_retained": False,
            "successful_ledger_call_bound": False,
            "ledger_call_id": "modelcall_f97afa2a05079468",
            "ledger_outcome": "failed",
            "canonical_result_accepted": False,
            "canonical_stage_completed": False,
            "response_identity_retained": False,
            "usage_metadata_retained": False,
            "actual_cost_retained": False,
            "full_orchestration_accepted": False,
            "runtime_acceptance_established": False,
            "downstream_execution_started": False,
            "deterministic_gates_started": False,
            "external_cause_detail": "unknown",
        }:
            _historical_schema_error("application result")
    if attempt_id == "production-flagship-20260812-14":
        expected_booleans.update(
            {
                "canonical_stage_completed": True,
                "canonical_guarded_fallback_applied": False,
                "canonical_contribution_diagnostics_retained": True,
                "orchestrator_plan_accepted": True,
                "parallel_specialists_started": True,
                "document_source_integrity_accepted": False,
                "process_decision_mapping_accepted": False,
                "later_model_calls_after_failure": False,
                "deterministic_gates_started": False,
                "full_orchestration_accepted": False,
                "runtime_acceptance_established": False,
                "failed_call_upstream_identity_retained": False,
            }
        )
        if values != {
            "outcome": "rejected",
            "failure_type": "parallel_specialist_provider_upstream_rejection",
            "error_type": "OpenRouterUpstreamRejectionError",
            "error_invariant": "provider_upstream_rejection",
            "successful_ledger_call_bound": False,
            "ledger_call_id": "modelcall_509e1d20d5f03da7",
            "ledger_outcome": "failed",
            "failed_ledger_call_ids": [
                "modelcall_509e1d20d5f03da7",
                "modelcall_17477d1f8a445c6f",
            ],
            "canonical_stage_completed": True,
            "canonical_stage_outcome": "succeeded",
            "canonical_stage_call_id": "modelcall_b5582c002c6f20bb",
            "canonical_guarded_fallback_applied": False,
            "canonical_contribution_diagnostics_retained": True,
            "orchestrator_plan_accepted": True,
            "orchestrator_plan_call_id": "modelcall_47529c6d5a49d7cc",
            "parallel_specialists_started": True,
            "document_source_integrity_accepted": False,
            "document_source_integrity_call_id": "modelcall_17477d1f8a445c6f",
            "process_decision_mapping_accepted": False,
            "process_decision_mapping_call_id": "modelcall_509e1d20d5f03da7",
            "later_model_calls_after_failure": False,
            "deterministic_gates_started": False,
            "full_orchestration_accepted": False,
            "runtime_acceptance_established": False,
            "failed_call_upstream_identity_retained": False,
            "external_cause_detail": "unknown",
        }:
            _historical_schema_error("application result")
    for field, expected in expected_booleans.items():
        if field in values and values[field] is not expected:
            _historical_schema_error("application result")
    if "accepted_fact_count" in values:
        rejected = values.get("rejected_invariants")
        if (
            not _is_exact_historical_int(values["accepted_fact_count"], 7)
            or not _is_exact_historical_int(values.get("rejected_fact_count"), 11)
            or not isinstance(rejected, dict)
            or set(rejected) != {"source_reference_set", "canonical_state"}
            or not _is_exact_historical_int(rejected.get("source_reference_set"), 10)
            or not _is_exact_historical_int(rejected.get("canonical_state"), 1)
        ):
            _historical_schema_error("application result")


def _verify_attempt_14_capture_provenance(capture: Any) -> None:
    values = _require_historical_fields(
        capture,
        frozenset(
            "capture_mode captured_at render_workspace_id public_api_model_ledger "
            "public_api_ready public_qa_origin".split()
        ),
        "capture provenance",
    )
    if (
        values.get("capture_mode")
        != "read_only_render_connector_and_public_sanitized_endpoints"
        or not _is_historical_timestamp(values.get("captured_at"))
        or not isinstance(values.get("render_workspace_id"), str)
        or _HISTORICAL_WORKSPACE_ID_PATTERN.fullmatch(values["render_workspace_id"])
        is None
    ):
        _historical_schema_error("capture provenance")

    endpoint_fields = frozenset(
        "path http_status response_bytes response_sha256".split()
    )
    model_ledger = _require_historical_fields(
        values.get("public_api_model_ledger"),
        endpoint_fields,
        "capture provenance",
    )
    ready = _require_historical_fields(
        values.get("public_api_ready"),
        endpoint_fields,
        "capture provenance",
    )
    _require_historical_fields(
        values.get("public_qa_origin"),
        frozenset(
            "report_path report_http_status report_response_at "
            "report_last_modified_at report_bytes report_sha256 report_status "
            "report_passed report_failed report_release_identity_present "
            "evidence_manifest_path evidence_manifest_http_status classification".split()
        ),
        "capture provenance",
    )
    for endpoint in (model_ledger, ready):
        if (
            not _is_exact_historical_int(endpoint.get("http_status"), 200)
            or not isinstance(endpoint.get("response_bytes"), int)
            or isinstance(endpoint.get("response_bytes"), bool)
            or endpoint["response_bytes"] <= 0
            or not isinstance(endpoint.get("response_sha256"), str)
            or _HISTORICAL_SHA256_PATTERN.fullmatch(endpoint["response_sha256"])
            is None
        ):
            _historical_schema_error("capture provenance")
    if values != {
        "capture_mode": "read_only_render_connector_and_public_sanitized_endpoints",
        "captured_at": "2026-08-12T05:59:34Z",
        "render_workspace_id": "tea-d9q2kkht0dsc73c50jog",
        "public_api_model_ledger": {
            "path": "/api/model-ledger",
            "http_status": 200,
            "response_bytes": 5577,
            "response_sha256": (
                "37980deb2c5408af9801a1b464a868c3c4b122addff275fc1e159df7d14a7aec"
            ),
        },
        "public_api_ready": {
            "path": "/readyz",
            "http_status": 200,
            "response_bytes": 1871,
            "response_sha256": (
                "8317ef739aa55b9a85a1d4e560306049e3148889456087bb645fd7de8421723d"
            ),
        },
        "public_qa_origin": {
            "report_path": "/report.json",
            "report_http_status": 200,
            "report_response_at": "2026-08-12T05:55:33Z",
            "report_last_modified_at": "2026-08-11T10:08:32Z",
            "report_bytes": 7291,
            "report_sha256": (
                "946d6ebd24da538dbf5f7416f93fc27cd653d5dd724015c325b6a845a1cbe425"
            ),
            "report_status": "passed",
            "report_passed": 57,
            "report_failed": 0,
            "report_release_identity_present": False,
            "evidence_manifest_path": "/evidence-manifest.json",
            "evidence_manifest_http_status": 404,
            "classification": "stale_previous_deploy_not_attempt_14",
        },
    }:
        _historical_schema_error("capture provenance")


def _verify_attempt_15_qa_result(result: Any) -> None:
    values = _require_historical_fields(
        result,
        frozenset(
            "outcome failure_type failed_check expected_agent_ids visible_agent_ids "
            "expected_gate_ids visible_gate_ids validator_label proof_visible "
            "orchestrator_label_exact production_boundary_exact "
            "current_report_retained current_evidence_manifest_retained "
            "runtime_acceptance_established".split()
        ),
        "QA result",
    )
    if values != {
        "outcome": "rejected",
        "failure_type": "validator_label_promoted_to_gate_identity",
        "failed_check": (
            "Cold flagship visibly presented every Nemotron role and deterministic gate"
        ),
        "expected_agent_ids": [
            "canonical_facts",
            "orchestrator_plan",
            "document_source_integrity",
            "process_decision_mapping",
            "evidence_checklist",
            "final_claim_brief_audit",
        ],
        "visible_agent_ids": [
            "canonical_facts",
            "orchestrator_plan",
            "document_source_integrity",
            "process_decision_mapping",
            "evidence_checklist",
            "final_claim_brief_audit",
        ],
        "expected_gate_ids": [
            "deterministic_process_gate",
            "deterministic_evidence_gate",
            "whole_playbook_gate",
        ],
        "visible_gate_ids": [
            "deterministic_process_gate",
            "deterministic_evidence_gate",
            "whole_playbook_gate",
            "whole-playbook-validator/15.2",
        ],
        "validator_label": "whole-playbook-validator/15.2",
        "proof_visible": True,
        "orchestrator_label_exact": True,
        "production_boundary_exact": True,
        "current_report_retained": False,
        "current_evidence_manifest_retained": False,
        "runtime_acceptance_established": False,
    }:
        _historical_schema_error("QA result")


def _verify_attempt_15_capture_provenance(capture: Any) -> None:
    values = _require_historical_fields(
        capture,
        frozenset(
            "capture_mode captured_at render_workspace_id public_api_model_ledger "
            "public_api_ready public_qa_origin".split()
        ),
        "capture provenance",
    )
    endpoint_fields = frozenset(
        "path http_status response_bytes response_sha256".split()
    )
    for endpoint_name in ("public_api_model_ledger", "public_api_ready"):
        endpoint = _require_historical_fields(
            values.get(endpoint_name), endpoint_fields, "capture provenance"
        )
        if (
            not _is_exact_historical_int(endpoint.get("http_status"), 200)
            or not isinstance(endpoint.get("response_bytes"), int)
            or isinstance(endpoint.get("response_bytes"), bool)
            or endpoint["response_bytes"] <= 0
            or not isinstance(endpoint.get("response_sha256"), str)
            or _HISTORICAL_SHA256_PATTERN.fullmatch(endpoint["response_sha256"])
            is None
        ):
            _historical_schema_error("capture provenance")
    _require_historical_fields(
        values.get("public_qa_origin"),
        frozenset(
            "report_path report_http_status report_response_at "
            "report_last_modified_at report_bytes report_sha256 report_status "
            "report_passed report_failed report_release_identity_present "
            "evidence_manifest_path evidence_manifest_http_status classification".split()
        ),
        "capture provenance",
    )
    if (
        not _is_historical_timestamp(values.get("captured_at"))
        or not isinstance(values.get("render_workspace_id"), str)
        or _HISTORICAL_WORKSPACE_ID_PATTERN.fullmatch(values["render_workspace_id"])
        is None
        or values
        != {
            "capture_mode": (
                "read_only_render_connector_and_public_sanitized_endpoints"
            ),
            "captured_at": "2026-08-12T08:34:50Z",
            "render_workspace_id": "tea-d9q2kkht0dsc73c50jog",
            "public_api_model_ledger": {
                "path": "/api/model-ledger",
                "http_status": 200,
                "response_bytes": 10869,
                "response_sha256": (
                    "c2c1a1db80bc7f8afef6034a1f8f538f891f5b70a4c1fa2287555c3f68a83945"
                ),
            },
            "public_api_ready": {
                "path": "/readyz",
                "http_status": 200,
                "response_bytes": 1923,
                "response_sha256": (
                    "fdaf75ed266d22ab9691fde2559ce8ba55d48d3c9005e18ef9af07fc2d384911"
                ),
            },
            "public_qa_origin": {
                "report_path": "/report.json",
                "report_http_status": 200,
                "report_response_at": "2026-08-12T08:34:50Z",
                "report_last_modified_at": "2026-08-11T10:08:32Z",
                "report_bytes": 7291,
                "report_sha256": (
                    "946d6ebd24da538dbf5f7416f93fc27cd653d5dd724015c325b6a845a1cbe425"
                ),
                "report_status": "passed",
                "report_passed": 57,
                "report_failed": 0,
                "report_release_identity_present": False,
                "evidence_manifest_path": "/evidence-manifest.json",
                "evidence_manifest_http_status": 404,
                "classification": "stale_previous_deploy_not_attempt_15",
            },
        }
    ):
        _historical_schema_error("capture provenance")


def _verify_attempt_16_warm_cache_result(result: Any) -> None:
    values = _require_historical_fields(
        result,
        frozenset(
            "outcome orchestration_id provider_network_call_count cache_hit_count "
            "required_model_roles_complete full_orchestration_accepted "
            "runtime_acceptance_established calls".split()
        ),
        "warm cache result",
    )
    calls = values["calls"]
    expected_agents = [
        "canonical_facts",
        "orchestrator_plan",
        "process_decision_mapping",
        "document_source_integrity",
        "evidence_checklist",
        "final_claim_brief_audit",
    ]
    expected_call_ids = [
        "modelcall_071a992872e4c1a7",
        "modelcall_2fa95149e52f7ca1",
        "modelcall_99b60ec408792962",
        "modelcall_20ff775cf6c7b59a",
        "modelcall_9f92e9bc170b700f",
        "modelcall_abae670318f1010c",
    ]
    expected_origins = [
        "modelcall_1c8ccf51b4340523",
        "modelcall_ddc79b44a3f08471",
        "modelcall_485aad43dae0a528",
        "modelcall_1487c7a90b4ff77d",
        "modelcall_56141d8df3daeabc",
        "modelcall_a6940ff6be1cbfae",
    ]
    if (
        values["outcome"] != "accepted"
        or values["orchestration_id"] != "orch_bb0033c34697657c"
        or not _is_exact_historical_int(values["provider_network_call_count"], 0)
        or not _is_exact_historical_int(values["cache_hit_count"], 6)
        or values["required_model_roles_complete"] is not True
        or values["full_orchestration_accepted"] is not True
        or values["runtime_acceptance_established"] is not False
        or not isinstance(calls, list)
        or len(calls) != 6
        or [call.get("agent_id") if isinstance(call, dict) else None for call in calls]
        != expected_agents
        or [call.get("call_id") if isinstance(call, dict) else None for call in calls]
        != expected_call_ids
        or [
            call.get("origin_call_id") if isinstance(call, dict) else None
            for call in calls
        ]
        != expected_origins
    ):
        _historical_schema_error("warm cache result")
    response_ids: set[str] = set()
    for index, call in enumerate(calls):
        call = _require_historical_fields(
            call,
            _HISTORICAL_ATTEMPT_16_WARM_CALL_FIELDS,
            "warm cache call",
        )
        origin_usage = _require_historical_fields(
            call["origin_usage"],
            frozenset(
                "prompt_tokens completion_tokens total_tokens actual_cost_usd "
                "usage_source".split()
            ),
            "warm cache origin usage",
        )
        expected_parent = (
            None if index == 0 else expected_call_ids[0 if index == 1 else 1]
        )
        if (
            call["orchestration_id"] != values["orchestration_id"]
            or call["parent_call_id"] != expected_parent
            or (index == 0 and call["delegation_id"] is not None)
            or (
                index > 0
                and (
                    not isinstance(call["delegation_id"], str)
                    or _HISTORICAL_DELEGATION_ID_PATTERN.fullmatch(
                        call["delegation_id"]
                    )
                    is None
                )
            )
            or call["outcome"] != "cache_hit"
            or call["cache_hit"] is not True
            or not _is_exact_historical_int(call["call_count"], 0)
            or call["response_model"] not in ACCEPTED_PRODUCTION_RESPONSE_MODELS
            or call["upstream_provider"] != "DeepInfra"
            or call["finish_reason"] != "stop"
            or call["usage_source"] != "cache"
            or call["actual_cost_usd"] is not None
            or call["origin_finish_reason"] != "stop"
            or not all(
                isinstance(origin_usage[field], int)
                and not isinstance(origin_usage[field], bool)
                and origin_usage[field] >= 0
                for field in ("prompt_tokens", "completion_tokens", "total_tokens")
            )
            or origin_usage["total_tokens"]
            != origin_usage["prompt_tokens"] + origin_usage["completion_tokens"]
            or not isinstance(origin_usage["actual_cost_usd"], (int, float))
            or isinstance(origin_usage["actual_cost_usd"], bool)
            or origin_usage["actual_cost_usd"] <= 0
            or origin_usage["usage_source"] != "response"
            or not isinstance(call["response_id"], str)
            or OPENROUTER_GENERATION_ID_PATTERN.fullmatch(call["response_id"]) is None
            or not _is_historical_timestamp(call["created_at"])
            or not _is_historical_timestamp(call["updated_at"])
        ):
            _historical_schema_error("warm cache call")
        response_ids.add(call["response_id"])
    if len(response_ids) != 6:
        _historical_schema_error("warm cache result")


def _verify_attempt_16_qa_result(result: Any) -> None:
    values = _require_historical_fields(
        result,
        frozenset(
            "outcome failure_type failed_check precedent_contract corpus_version "
            "ranking_context_hash expected_precedents initial_precedent_cards_exact "
            "rendered_precedents_after_interaction six_visible_model_roles_exact "
            "three_visible_deterministic_gates_exact "
            "terminal_validator_excluded_from_gate_identity "
            "warm_cache_lineage_exact current_report_retained "
            "current_evidence_manifest_retained runtime_acceptance_established".split()
        ),
        "QA result",
    )
    expected = [
        {"claim_id": "HIST-MOULD-014", "rank": 1, "score": 146},
        {"claim_id": "HIST-MOULD-022", "rank": 2, "score": 146},
        {"claim_id": "HIST-MOULD-009", "rank": 3, "score": 136},
    ]
    if (
        values["outcome"] != "rejected"
        or values["failure_type"] != "precedent_cards_lost_after_process_interaction"
        or values["failed_check"]
        != "Exactly three generated reference patterns expose ordered rank, score, factors, corpus, and context hash"
        or values["precedent_contract"] != "casepath.precedent-ranking/1.0.0"
        or values["corpus_version"] != "generated-reference-patterns/2026-08-12"
        or not isinstance(values["ranking_context_hash"], str)
        or _HISTORICAL_SHA256_PATTERN.fullmatch(values["ranking_context_hash"]) is None
        or values["expected_precedents"] != expected
        or values["rendered_precedents_after_interaction"] != []
        or any(
            values[field] is not expected_value
            for field, expected_value in {
                "initial_precedent_cards_exact": True,
                "six_visible_model_roles_exact": True,
                "three_visible_deterministic_gates_exact": True,
                "terminal_validator_excluded_from_gate_identity": True,
                "warm_cache_lineage_exact": True,
                "current_report_retained": False,
                "current_evidence_manifest_retained": False,
                "runtime_acceptance_established": False,
            }.items()
        )
    ):
        _historical_schema_error("QA result")


def _verify_attempt_16_capture_provenance(capture: Any) -> None:
    values = _require_historical_fields(
        capture,
        frozenset(
            "capture_mode captured_at render_workspace_id public_api_model_ledger "
            "public_api_ready public_qa_origin".split()
        ),
        "capture provenance",
    )
    endpoint_fields = frozenset(
        "path http_status response_bytes response_sha256".split()
    )
    for endpoint_name in ("public_api_model_ledger", "public_api_ready"):
        endpoint = _require_historical_fields(
            values[endpoint_name], endpoint_fields, "capture provenance"
        )
        if (
            not _is_exact_historical_int(endpoint["http_status"], 200)
            or not isinstance(endpoint["response_bytes"], int)
            or isinstance(endpoint["response_bytes"], bool)
            or endpoint["response_bytes"] <= 0
            or not isinstance(endpoint["response_sha256"], str)
            or _HISTORICAL_SHA256_PATTERN.fullmatch(endpoint["response_sha256"]) is None
        ):
            _historical_schema_error("capture provenance")
    origin = _require_historical_fields(
        values["public_qa_origin"],
        frozenset(
            "report_path report_http_status report_response_at report_last_modified_at "
            "report_bytes report_sha256 report_status report_passed report_failed "
            "report_checked_at report_release_identity_present served_deploy_id "
            "served_source_commit evidence_manifest_path evidence_manifest_http_status "
            "evidence_manifest_response_bytes evidence_manifest_response_sha256 "
            "access_control_allow_origin_present server_header classification".split()
        ),
        "capture provenance",
    )
    if (
        values["capture_mode"]
        != "read_only_render_connector_and_public_sanitized_endpoints"
        or not _is_historical_timestamp(values["captured_at"])
        or values["render_workspace_id"] != "tea-d9q2kkht0dsc73c50jog"
        or origin["classification"] != "stale_previous_deploy_not_attempt_16"
        or origin["report_release_identity_present"] is not False
        or not _is_exact_historical_int(origin["evidence_manifest_http_status"], 404)
        or origin["access_control_allow_origin_present"] is not False
        or not isinstance(origin["evidence_manifest_response_sha256"], str)
        or _HISTORICAL_SHA256_PATTERN.fullmatch(
            origin["evidence_manifest_response_sha256"]
        )
        is None
    ):
        _historical_schema_error("capture provenance")


def _verify_attempt_17_capture_provenance(capture: Any) -> None:
    values = _require_historical_fields(
        capture,
        frozenset(
            "capture_mode captured_at render_workspace_id public_api_model_ledger "
            "public_api_ready public_qa_origin".split()
        ),
        "capture provenance",
    )
    endpoint_fields = frozenset(
        "path http_status response_bytes response_sha256".split()
    )
    model_ledger = _require_historical_fields(
        values["public_api_model_ledger"], endpoint_fields, "capture provenance"
    )
    ready = _require_historical_fields(
        values["public_api_ready"], endpoint_fields, "capture provenance"
    )
    origin = _require_historical_fields(
        values["public_qa_origin"],
        frozenset(
            "report_path report_http_status report_response_at report_last_modified_at "
            "report_bytes report_sha256 report_status report_passed report_failed "
            "report_checked_at report_release_identity_present served_deploy_id "
            "served_source_commit evidence_manifest_path evidence_manifest_http_status "
            "evidence_manifest_response_bytes evidence_manifest_response_sha256 "
            "access_control_allow_origin_present server_header classification".split()
        ),
        "capture provenance",
    )
    if values != {
        "capture_mode": "read_only_render_connector_and_public_sanitized_endpoints",
        "captured_at": "2026-08-12T10:14:52Z",
        "render_workspace_id": "tea-d9q2kkht0dsc73c50jog",
        "public_api_model_ledger": model_ledger,
        "public_api_ready": ready,
        "public_qa_origin": origin,
    }:
        _historical_schema_error("capture provenance")
    if model_ledger != {
        "path": "/api/model-ledger",
        "http_status": 200,
        "response_bytes": 10854,
        "response_sha256": (
            "d151ff5bc1d0d28a6e2e0f3d59d0a519eb4fc217854e4ad1bb70e4e730155592"
        ),
    } or ready != {
        "path": "/readyz",
        "http_status": 200,
        "response_bytes": 1898,
        "response_sha256": (
            "08ea34d9979140200439f9a8b8f4f2d4e93f97ab29a13cd513052e2100218860"
        ),
    }:
        _historical_schema_error("capture provenance")
    if origin != {
        "report_path": "/report.json",
        "report_http_status": 200,
        "report_response_at": "2026-08-12T10:14:52Z",
        "report_last_modified_at": "2026-08-11T10:08:32Z",
        "report_bytes": 7291,
        "report_sha256": (
            "946d6ebd24da538dbf5f7416f93fc27cd653d5dd724015c325b6a845a1cbe425"
        ),
        "report_status": "passed",
        "report_passed": 57,
        "report_failed": 0,
        "report_checked_at": "2026-08-11T10:08:31.706Z",
        "report_release_identity_present": False,
        "served_deploy_id": "dep-d9tf8se417fc73e9bkv0",
        "served_source_commit": "7be18c72f353366930cd5dcace637884e06e63a7",
        "evidence_manifest_path": "/evidence-manifest.json",
        "evidence_manifest_http_status": 404,
        "evidence_manifest_response_bytes": 335,
        "evidence_manifest_response_sha256": (
            "860b53ed6ea6a0cf602fae632cfcd28dbcf637f85a8bee28d2ee9c6cc9081669"
        ),
        "access_control_allow_origin_present": False,
        "server_header": "SimpleHTTP/0.6",
        "classification": "stale_previous_deploy_not_attempt_17",
    }:
        _historical_schema_error("capture provenance")


def _verify_attempt_18_capture_provenance(capture: Any) -> None:
    values = _require_historical_fields(
        capture,
        frozenset(
            "capture_mode captured_at render_workspace_id public_api_model_ledger "
            "public_api_ready public_qa_origin".split()
        ),
        "capture provenance",
    )
    endpoint_fields = frozenset(
        "path http_status response_bytes response_sha256".split()
    )
    model_ledger = _require_historical_fields(
        values["public_api_model_ledger"], endpoint_fields, "capture provenance"
    )
    ready = _require_historical_fields(
        values["public_api_ready"], endpoint_fields, "capture provenance"
    )
    origin = _require_historical_fields(
        values["public_qa_origin"],
        frozenset(
            "report_path report_http_status report_response_at report_last_modified_at "
            "report_bytes report_sha256 report_status report_passed report_failed "
            "report_checked_at report_release_identity_present served_deploy_id "
            "served_source_commit evidence_manifest_path evidence_manifest_http_status "
            "evidence_manifest_response_bytes evidence_manifest_response_sha256 "
            "access_control_allow_origin_present server_header classification".split()
        ),
        "capture provenance",
    )
    if values != {
        "capture_mode": "read_only_render_connector_and_public_sanitized_endpoints",
        "captured_at": "2026-08-12T11:03:29Z",
        "render_workspace_id": "tea-d9q2kkht0dsc73c50jog",
        "public_api_model_ledger": model_ledger,
        "public_api_ready": ready,
        "public_qa_origin": origin,
    }:
        _historical_schema_error("capture provenance")
    if model_ledger != {
        "path": "/api/model-ledger",
        "http_status": 200,
        "response_bytes": 6131,
        "response_sha256": (
            "7e12ae02ff728beffd85576f614e2ecc46e99913d2d40a8302a8798359b64846"
        ),
    } or ready != {
        "path": "/readyz",
        "http_status": 200,
        "response_bytes": 1898,
        "response_sha256": (
            "605064d0a10937011bcc5ecf8e12da3cccd60a4e0e95b5798ca3250242298aa0"
        ),
    }:
        _historical_schema_error("capture provenance")
    if origin != {
        "report_path": "/report.json",
        "report_http_status": 200,
        "report_response_at": "2026-08-12T11:03:29Z",
        "report_last_modified_at": "2026-08-11T10:08:32Z",
        "report_bytes": 7291,
        "report_sha256": (
            "946d6ebd24da538dbf5f7416f93fc27cd653d5dd724015c325b6a845a1cbe425"
        ),
        "report_status": "passed",
        "report_passed": 57,
        "report_failed": 0,
        "report_checked_at": "2026-08-11T10:08:31.706Z",
        "report_release_identity_present": False,
        "served_deploy_id": "dep-d9tf8se417fc73e9bkv0",
        "served_source_commit": "7be18c72f353366930cd5dcace637884e06e63a7",
        "evidence_manifest_path": "/evidence-manifest.json",
        "evidence_manifest_http_status": 404,
        "evidence_manifest_response_bytes": 335,
        "evidence_manifest_response_sha256": (
            "860b53ed6ea6a0cf602fae632cfcd28dbcf637f85a8bee28d2ee9c6cc9081669"
        ),
        "access_control_allow_origin_present": False,
        "server_header": "SimpleHTTP/0.6",
        "classification": "stale_previous_deploy_not_attempt_18",
    }:
        _historical_schema_error("capture provenance")


def _verify_attempt_21_evidence(evidence: dict[str, Any]) -> None:
    execution = evidence["execution_observation"]
    provider = evidence["provider_observation"]
    result = evidence["application_result"]
    provider_calls = provider.get("calls")
    warm = _require_historical_fields(
        evidence.get("warm_cache_result"),
        frozenset(
            "outcome orchestration_id provider_network_call_count cache_hit_count "
            "required_model_roles_complete full_orchestration_accepted "
            "runtime_acceptance_established calls".split()
        ),
        "warm cache result",
    )
    warm_calls = warm.get("calls")
    expected_agents = set(execution["required_model_agent_ids"])
    if (
        not isinstance(provider_calls, list)
        or not isinstance(warm_calls, list)
        or len(provider_calls) != 6
        or len(warm_calls) != 6
        or {call.get("agent_id") for call in provider_calls} != expected_agents
        or {call.get("agent_id") for call in warm_calls} != expected_agents
        or [call.get("call_id") for call in provider_calls]
        != result["complete_model_call_ids"]
    ):
        _historical_schema_error("attempt binding")

    cold_by_agent: dict[str, dict[str, Any]] = {}
    for call in provider_calls:
        agent_id = call.get("agent_id")
        fields = _HISTORICAL_ATTEMPT_21_COLD_CALL_FIELDS.get(agent_id)
        if fields is None:
            _historical_schema_error("provider call observation")
        verified = _require_historical_fields(
            call, fields, "provider call observation"
        )
        _verify_positive_usage(verified, "Historical provider call observation")
        if (
            verified["provider"] != "openrouter"
            or verified["provider_endpoint"]
            != "https://openrouter.ai/api/v1/chat/completions"
            or verified["model"] != REQUIRED_PRODUCTION_MODEL
            or verified["orchestration_id"] != execution["cold_orchestration_id"]
            or not _is_exact_historical_int(verified["call_count"], 1)
            or verified["response_model"] not in ACCEPTED_PRODUCTION_RESPONSE_MODELS
            or verified["upstream_provider"] != "DeepInfra"
            or verified["finish_reason"] != "stop"
            or verified["usage_source"] != "response"
            or verified["total_tokens"]
            != verified["prompt_tokens"] + verified["completion_tokens"]
            or _HISTORICAL_CALL_ID_PATTERN.fullmatch(verified["call_id"]) is None
            or _HISTORICAL_SHA256_PATTERN.fullmatch(verified["cache_key"]) is None
            or not _is_historical_timestamp(verified["created_at"])
            or not _is_historical_timestamp(verified["updated_at"])
        ):
            _historical_schema_error("provider call observation")
        cold_by_agent[agent_id] = verified

    expected_summary = {
        "records": 12,
        "network_calls": 6,
        "prompt_tokens": 35274,
        "completion_tokens": 7165,
        "total_tokens": 42439,
        "actual_cost_usd": 0.0332464,
        "actual_cost_complete": True,
        "unknown_cost_call_count": 0,
        "outcomes": {
            "cache_hit": 6,
            "succeeded": 4,
            "succeeded_with_guarded_fallback": 2,
        },
    }
    if (
        provider["network_call_count"] != 6
        or provider["actual_cost_complete"] is not True
        or provider["unknown_cost_call_count"] != 0
        or provider["prompt_tokens"] != 35274
        or provider["completion_tokens"] != 7165
        or provider["total_tokens"] != 42439
        or provider["prompt_tokens"]
        != sum(call["prompt_tokens"] for call in provider_calls)
        or provider["completion_tokens"]
        != sum(call["completion_tokens"] for call in provider_calls)
        or provider["total_tokens"]
        != sum(call["total_tokens"] for call in provider_calls)
        or not math.isclose(
            provider["actual_cost_usd"],
            sum(call["actual_cost_usd"] for call in provider_calls),
            rel_tol=0,
            abs_tol=1e-10,
        )
        or not math.isclose(
            provider["actual_cost_usd"], 0.0332464, rel_tol=0, abs_tol=1e-10
        )
        or provider["outcomes"]
        != {"succeeded": 4, "succeeded_with_guarded_fallback": 2}
        or provider["global_ledger_summary"] != expected_summary
        or provider["physical_provider_max_in_flight"] != 1
        or provider["application_retry_count"] != 0
    ):
        _historical_schema_error("provider call aggregate")

    for call in warm_calls:
        agent_id = call.get("agent_id")
        fields = _HISTORICAL_ATTEMPT_21_WARM_CALL_FIELDS.get(agent_id)
        if fields is None:
            _historical_schema_error("warm cache call observation")
        verified = _require_historical_fields(
            call, fields, "warm cache call observation"
        )
        cold = cold_by_agent[agent_id]
        if (
            verified["provider"] != "openrouter"
            or verified["provider_endpoint"]
            != "https://openrouter.ai/api/v1/chat/completions"
            or verified["model"] != REQUIRED_PRODUCTION_MODEL
            or verified["orchestration_id"] != execution["warm_orchestration_id"]
            or verified["outcome"] != "cache_hit"
            or not _is_exact_historical_int(verified["call_count"], 0)
            or verified["actual_cost_usd"] is not None
            or verified["origin_call_id"] != cold["call_id"]
            or verified["response_id"] != cold["response_id"]
            or verified["origin_finish_reason"] != cold["finish_reason"]
            or verified["origin_usage"]
            != {
                "prompt_tokens": cold["prompt_tokens"],
                "completion_tokens": cold["completion_tokens"],
                "total_tokens": cold["total_tokens"],
                "actual_cost_usd": cold["actual_cost_usd"],
                "usage_source": cold["usage_source"],
            }
            or _HISTORICAL_CALL_ID_PATTERN.fullmatch(verified["call_id"]) is None
            or _HISTORICAL_SHA256_PATTERN.fullmatch(verified["cache_key"]) is None
            or not _is_historical_timestamp(verified["created_at"])
            or not _is_historical_timestamp(verified["updated_at"])
        ):
            _historical_schema_error("warm cache call observation")

    if warm != {
        "outcome": "accepted",
        "orchestration_id": execution["warm_orchestration_id"],
        "provider_network_call_count": 0,
        "cache_hit_count": 6,
        "required_model_roles_complete": True,
        "full_orchestration_accepted": True,
        "runtime_acceptance_established": False,
        "calls": warm_calls,
    }:
        _historical_schema_error("warm cache result")

    qa_result = _require_historical_fields(
        evidence.get("qa_result"),
        frozenset(
            "outcome failure_type failed_check item_id primary_node_id ordered_node_ids "
            "current_path rendered_node_id rendered_node_ids rendered_current_path "
            "rendered_text secondary_relationship_copy_present current_report_retained "
            "current_evidence_manifest_retained runtime_acceptance_established".split()
        ),
        "QA result",
    )
    if qa_result != {
        "outcome": "rejected",
        "failure_type": "document_sheet_multi_owner_item_not_expanded",
        "failed_check": (
            "Document sheet preserves exact owner order, primary owner, current-path "
            "state, and secondary relationships"
        ),
        "item_id": "defect_notice",
        "primary_node_id": "notification",
        "ordered_node_ids": ["notification", "formal_notice"],
        "current_path": True,
        "rendered_node_id": "notification",
        "rendered_node_ids": "notification,formal_notice",
        "rendered_current_path": "true",
        "rendered_text": "",
        "secondary_relationship_copy_present": False,
        "current_report_retained": False,
        "current_evidence_manifest_retained": False,
        "runtime_acceptance_established": False,
    }:
        _historical_schema_error("QA result")

    capture = _require_historical_fields(
        evidence.get("capture_provenance"),
        frozenset(
            "capture_mode captured_at render_workspace_id frontend_deployment "
            "frontend_release public_api_health public_api_ready "
            "public_api_model_ledger gate_progression_capture public_qa_origin".split()
        ),
        "capture provenance",
    )
    endpoint_fields = frozenset("path http_status response_bytes response_sha256".split())
    expected_endpoints = {
        "frontend_deployment": (
            "/deployment.json", 602,
            "bef0d16b6adcb4238c38c276cb232b68777ca663c4577b0f9870c025216a90ca",
        ),
        "frontend_release": (
            "/release.json", 7824,
            "5e11002e75d0067b03e70a4a8feff75a68c4c14103e8f22d7d3800c74be95ac8",
        ),
        "public_api_health": (
            "/healthz", 2496,
            "2921cd0517380153f5191b29c1cdcb1ef75e9c7b6c0e0c204aa94de15b88879f",
        ),
        "public_api_ready": (
            "/readyz", 1938,
            "d494f6a661438c4a79fbffee5aadb58b76526fee3d31ba68fa926fd8e6a2eb17",
        ),
        "public_api_model_ledger": (
            "/api/model-ledger", 22011,
            "ad87a2605fd39741fb5d7d8995f72cc58854e0376476d5d89fc8a97227190400",
        ),
    }
    for name, (path, response_bytes, response_sha256) in expected_endpoints.items():
        endpoint = _require_historical_fields(
            capture[name], endpoint_fields, "capture provenance"
        )
        if endpoint != {
            "path": path,
            "http_status": 200,
            "response_bytes": response_bytes,
            "response_sha256": response_sha256,
        }:
            _historical_schema_error("capture provenance")

    gate_capture = _require_historical_fields(
        capture["gate_progression_capture"],
        frozenset(
            "source cold_run_complete warm_run_complete deterministic_gate_ids "
            "deterministic_gate_outcome gate_artifact_hashes_retained "
            "gate_artifact_hashes_recoverable run_bodies_recoverable_after_cleanup".split()
        ),
        "gate progression capture",
    )
    if gate_capture != {
        "source": "qa_control_flow_and_api_request_logs_before_caller_cleanup",
        "cold_run_complete": True,
        "warm_run_complete": True,
        "deterministic_gate_ids": execution["deterministic_gate_ids"],
        "deterministic_gate_outcome": "passed",
        "gate_artifact_hashes_retained": False,
        "gate_artifact_hashes_recoverable": False,
        "run_bodies_recoverable_after_cleanup": False,
    }:
        _historical_schema_error("gate progression capture")

    qa_origin = _require_historical_fields(
        capture["public_qa_origin"],
        frozenset(
            "report_path report_http_status report_response_at report_last_modified_at "
            "report_bytes report_sha256 report_status report_passed report_failed "
            "report_checked_at report_release_identity_present served_deploy_id "
            "served_source_commit evidence_manifest_path evidence_manifest_http_status "
            "evidence_manifest_response_bytes evidence_manifest_response_sha256 "
            "stale_video_path stale_video_http_status stale_video_bytes "
            "stale_video_sha256 final_state_path final_state_http_status "
            "access_control_allow_origin_present cache_control_no_store_present "
            "server_header classification".split()
        ),
        "public QA origin",
    )
    if (
        capture["capture_mode"]
        != "read_only_render_connector_and_public_sanitized_endpoints"
        or capture["captured_at"] != "2026-08-12T12:57:34Z"
        or capture["render_workspace_id"] != "tea-d9q2kkht0dsc73c50jog"
        or qa_origin["classification"] != "stale_previous_deploy_not_attempt_21"
        or qa_origin["served_deploy_id"] != "dep-d9tf8se417fc73e9bkv0"
        or qa_origin["served_source_commit"]
        != "7be18c72f353366930cd5dcace637884e06e63a7"
        or qa_origin["report_release_identity_present"] is not False
        or qa_origin["evidence_manifest_http_status"] != 404
        or qa_origin["final_state_http_status"] != 404
        or qa_origin["access_control_allow_origin_present"] is not False
        or qa_origin["cache_control_no_store_present"] is not False
    ):
        _historical_schema_error("capture provenance")

    if (
        execution["ledger_created_at"] != provider_calls[0]["created_at"]
        or execution["ledger_updated_at"] != warm_calls[-1]["updated_at"]
        or result["complete_deterministic_gate_ids"]
        != execution["deterministic_gate_ids"]
    ):
        _historical_schema_error("attempt binding")
    for section, expected_sha256 in _HISTORICAL_ATTEMPT_21_SECTION_SHA256.items():
        if _historical_json_sha256(evidence[section]) != expected_sha256:
            _historical_schema_error("record hash")


def _verify_attempt_22_or_23_evidence(evidence: dict[str, Any]) -> None:
    attempt_id = evidence["attempt_id"]
    section_hashes = (
        _HISTORICAL_ATTEMPT_22_SECTION_SHA256
        if attempt_id == "production-flagship-20260812-22"
        else _HISTORICAL_ATTEMPT_23_SECTION_SHA256
    )
    for section, expected_sha256 in section_hashes.items():
        if _historical_json_sha256(evidence[section]) != expected_sha256:
            _historical_schema_error("record hash")

    execution = evidence["execution_observation"]
    provider = evidence["provider_observation"]
    application = evidence["application_result"]
    if attempt_id == "production-flagship-20260812-22":
        summary = provider["global_ledger_summary"]
        expected_summary = {
            "records": 24,
            "network_calls": 12,
            "prompt_tokens": 58845,
            "completion_tokens": 7642,
            "total_tokens": 66487,
            "actual_cost_usd": 0.0459277,
            "actual_cost_complete": True,
            "unknown_cost_call_count": 0,
            "outcomes": {
                "cache_hit": 12,
                "succeeded": 8,
                "succeeded_with_guarded_fallback": 4,
            },
        }
        orchestration_summaries = provider["orchestration_summaries"]
        expected_bindings = [
            (
                "flagship_cold_run_id",
                "flagship_cold_orchestration_id",
                6,
                0,
            ),
            (
                "flagship_warm_run_id",
                "flagship_warm_orchestration_id",
                0,
                6,
            ),
            ("later_cold_run_id", "later_cold_orchestration_id", 6, 0),
            ("later_warm_run_id", "later_warm_orchestration_id", 0, 6),
        ]
        if (
            summary != expected_summary
            or provider["total_tokens"]
            != provider["prompt_tokens"] + provider["completion_tokens"]
            or provider["outcomes"]
            != {"succeeded": 8, "succeeded_with_guarded_fallback": 4}
            or len(orchestration_summaries) != 4
            or any(
                row["run_id"] != execution[run_field]
                or row["orchestration_id"] != execution[orchestration_field]
                or row["network_calls"] != network_calls
                or row["cache_hits"] != cache_hits
                for row, (
                    run_field,
                    orchestration_field,
                    network_calls,
                    cache_hits,
                ) in zip(orchestration_summaries, expected_bindings, strict=True)
            )
            or evidence["qa_result"]["browser_report_status"] != "passed"
            or evidence["qa_result"]["failure_type"]
            != "authoritative_runtime_verifier_contract_drift"
            or application["runtime_acceptance_established"] is not False
        ):
            _historical_schema_error("attempt binding")
        return

    call = provider["call"]
    rejected = call["rejected_facts"]
    capture_summary = evidence["capture_provenance"]["public_model_ledger"]
    if (
        call["call_id"] != application["ledger_call_id"]
        or call["orchestration_id"] != execution["orchestration_id"]
        or execution["ledger_created_at"] != call["created_at"]
        or execution["ledger_updated_at"] != call["updated_at"]
        or call["accepted_fact_ids"] != ["fact_date_conflict"]
        or call["accepted_fact_count"] != 1
        or len(rejected) != 17
        or call["rejected_fact_count"] != 17
        or any(item != {"fact_id": item["fact_id"], "invariant": "canonical_state"} for item in rejected)
        or provider["network_call_count"] != call["call_count"]
        or provider["prompt_tokens"] != call["prompt_tokens"]
        or provider["completion_tokens"] != call["completion_tokens"]
        or provider["total_tokens"] != call["total_tokens"]
        or not math.isclose(
            provider["actual_cost_usd"],
            call["actual_cost_usd"],
            rel_tol=0,
            abs_tol=1e-10,
        )
        or capture_summary
        != {
            "records": 1,
            "network_calls": 1,
            "prompt_tokens": 23188,
            "completion_tokens": 4767,
            "total_tokens": 27955,
            "actual_cost_usd": 0.0220558,
            "actual_cost_complete": True,
            "unknown_cost_call_count": 0,
            "outcomes": {"failed": 1},
        }
        or evidence["capture_provenance"]["public_qa_atomic_state"][
            "served_source_commit"
        ]
        != "0db743a2a7a06c56bd5f011cc5928ef39efe424d"
    ):
        _historical_schema_error("attempt binding")


def _verify_attempt_24_evidence(evidence: dict[str, Any]) -> None:
    for section, expected_sha256 in _HISTORICAL_ATTEMPT_24_SECTION_SHA256.items():
        if _historical_json_sha256(evidence[section]) != expected_sha256:
            _historical_schema_error("record hash")

    execution = evidence["execution_observation"]
    provider = evidence["provider_observation"]
    application = evidence["application_result"]
    calls = provider["calls"]
    if not isinstance(calls, list) or len(calls) != 14:
        _historical_schema_error("attempt binding")
    call_ids = [call.get("call_id") for call in calls if isinstance(call, dict)]
    if (
        len(call_ids) != 14
        or len(set(call_ids)) != 14
        or any(_HISTORICAL_CALL_ID_PATTERN.fullmatch(call_id or "") is None for call_id in call_ids)
    ):
        _historical_schema_error("attempt binding")

    cold, warm, later = calls[:6], calls[6:12], calls[12:]
    required_agents = [item["agent_id"] for item in REQUIRED_MODEL_AGENTS]
    cold_ids = [call["call_id"] for call in cold]
    expected_origins = dict(zip(required_agents, cold_ids, strict=True))
    successful_network = [
        call
        for call in calls
        if call.get("call_count") == 1 and call.get("outcome") != "failed"
    ]
    failed = calls[-1]
    known_network = [
        call
        for call in calls
        if call.get("call_count") == 1 and call.get("actual_cost_usd") is not None
    ]
    outcomes = Counter(call.get("outcome") for call in calls)
    if (
        [call.get("agent_id") for call in cold] != required_agents
        or any(call.get("orchestration_id") != execution["flagship_cold_orchestration_id"] for call in cold)
        or any(call.get("call_count") != 1 for call in cold)
        or any(call.get("agent_id") not in expected_origins for call in warm)
        or [call.get("agent_id") for call in warm] != required_agents
        or any(call.get("orchestration_id") != execution["flagship_warm_orchestration_id"] for call in warm)
        or any(call.get("call_count") != 0 or call.get("outcome") != "cache_hit" for call in warm)
        or any(call.get("origin_call_id") != expected_origins[call["agent_id"]] for call in warm)
        or any(
            call.get("response_id")
            != cold[required_agents.index(call["agent_id"])].get("response_id")
            for call in warm
        )
        or [call.get("agent_id") for call in later]
        != ["canonical_facts", "orchestrator_plan"]
        or any(call.get("orchestration_id") != execution["later_cold_orchestration_id"] for call in later)
        or len(successful_network) != 7
        or any(
            call.get("upstream_provider") != "DeepInfra"
            or call.get("response_model") not in ACCEPTED_PRODUCTION_RESPONSE_MODELS
            or OPENROUTER_GENERATION_ID_PATTERN.fullmatch(call.get("response_id", "")) is None
            or call.get("finish_reason") != "stop"
            for call in successful_network
        )
        or failed.get("call_id") != application["failed_ledger_call_id"]
        or failed.get("outcome") != "failed"
        or failed.get("actual_cost_usd") is not None
        or failed.get("error_type") != "OpenRouterUpstreamRejectionError"
        or failed.get("error_invariant") != "provider_upstream_rejection"
        or failed.get("provider_error_code") != 429
        or failed.get("provider_boundary") != "openrouter"
        or failed.get("expected_upstream_provider") != "DeepInfra"
        or any(
            field in failed
            for field in (
                "response_id",
                "response_model",
                "upstream_provider",
                "finish_reason",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
            )
        )
        or provider["network_call_count"] != 8
        or provider["unknown_cost_call_count"] != 1
        or provider["actual_cost_complete"] is not False
        or provider["outcomes"] != dict(outcomes)
        or provider["prompt_tokens"] != sum(call["prompt_tokens"] for call in known_network)
        or provider["completion_tokens"] != sum(call["completion_tokens"] for call in known_network)
        or provider["total_tokens"] != sum(call["total_tokens"] for call in known_network)
        or provider["total_tokens"] != provider["prompt_tokens"] + provider["completion_tokens"]
        or not math.isclose(
            provider["actual_cost_usd"],
            sum(call["actual_cost_usd"] for call in known_network),
            rel_tol=0,
            abs_tol=1e-10,
        )
        or not math.isclose(provider["actual_cost_usd"], 0.0336607, rel_tol=0, abs_tol=1e-10)
        or not math.isclose(
            provider["prior_cumulative_known_actual_cost_usd"],
            0.4292561,
            rel_tol=0,
            abs_tol=1e-10,
        )
        or not math.isclose(
            provider["cumulative_known_actual_cost_usd"],
            provider["prior_cumulative_known_actual_cost_usd"] + provider["actual_cost_usd"],
            rel_tol=0,
            abs_tol=1e-10,
        )
        or cold_ids != application["flagship_cold_call_ids"]
        or later[0].get("call_id") != application["later_canonical_call_id"]
        or later[0].get("accepted_fact_count") != 16
        or later[0].get("rejected_fact_count") != 0
        or execution["ledger_created_at"] != cold[0].get("created_at")
        or execution["ledger_updated_at"] != failed.get("updated_at")
    ):
        _historical_schema_error("attempt binding")

    warm_result = evidence["warm_cache_result"]
    qa_result = evidence["qa_result"]
    capture = evidence["capture_provenance"]
    summary = capture["public_model_ledger"]
    public_qa = capture["public_qa_atomic_state"]
    if (
        warm_result
        != {
            "outcome": "accepted_flagship_only",
            "run_id": execution["flagship_warm_run_id"],
            "cold_orchestration_id": execution["flagship_cold_orchestration_id"],
            "warm_orchestration_id": execution["flagship_warm_orchestration_id"],
            "provider_network_call_count": 0,
            "cache_hit_count": 6,
            "exact_origin_lineage": True,
            "later_warm_replay_started": False,
            "runtime_acceptance_established": False,
        }
        or qa_result.get("terminal_timeout_ms") != 900000
        or qa_result.get("provider_failure_observed_before_timeout") is not True
        or qa_result.get("current_report_retained") is not False
        or qa_result.get("current_evidence_manifest_retained") is not False
        or summary.get("records") != 14
        or summary.get("network_calls") != 8
        or summary.get("unknown_cost_call_count") != 1
        or summary.get("actual_cost_complete") is not False
        or summary.get("sha256")
        != "d91b9fac36f05aafa92aa83a996fbaee798289a8c0c368fb2ed109017271c386"
        or public_qa.get("served_source_commit")
        != "0db743a2a7a06c56bd5f011cc5928ef39efe424d"
        or public_qa.get("report_sha256")
        != "0cf3d1ee2efec1e4bd78a82c2a70dcffe637aa198535445e48b26222332ed5f9"
        or public_qa.get("evidence_manifest_sha256")
        != "215279d8d2b7a4fbf31536a288c496ae4e1f8ba983a539fdfdd8fc6d0b51bbf8"
        or public_qa.get("report_manifest_binding_sha256")
        != public_qa.get("evidence_manifest_sha256")
        or public_qa.get("report_manifest_binding_bytes")
        != public_qa.get("evidence_manifest_bytes")
        or public_qa.get("report_status") != "passed"
        or public_qa.get("report_passed") != 218
        or public_qa.get("report_failed") != 0
        or public_qa.get("retained_total_count") != 30
        or public_qa.get("missing") != []
        or public_qa.get("empty") != []
        or capture["first_exact_failure"]["actual_cost_usd"] is not None
        or capture["first_exact_failure"]["response_identity_retained"] is not False
        or capture["first_exact_failure"]["usage_retained"] is not False
        or not math.isclose(
            capture["cumulative_known_actual_cost_usd"],
            0.4629168,
            rel_tol=0,
            abs_tol=1e-10,
        )
        or capture["cumulative_unknown_cost_call_count"] != 1
    ):
        _historical_schema_error("attempt binding")


def _verify_historical_attempt_schema(evidence: Any) -> None:
    if not isinstance(evidence, dict):
        _historical_schema_error("record")
    attempt_id = evidence.get("attempt_id")
    if attempt_id not in _HISTORICAL_PROVIDER_FIELDS:
        _historical_schema_error("record identity")
    expected_top = _HISTORICAL_TOP_FIELDS
    if attempt_id in _HISTORICAL_EXECUTION_FIELDS:
        expected_top = expected_top | {"execution_observation"}
    if attempt_id in {
        "production-flagship-20260812-14",
        "production-flagship-20260812-15",
        "production-flagship-20260812-16",
        "production-flagship-20260812-17",
        "production-flagship-20260812-18",
        "production-flagship-20260812-19",
        "production-flagship-20260812-20",
        "production-flagship-20260812-21",
        "production-flagship-20260812-22",
        "production-flagship-20260812-23",
        "production-flagship-20260812-24",
    }:
        expected_top = expected_top | {"capture_provenance"}
    if attempt_id in {
        "production-flagship-20260812-15",
        "production-flagship-20260812-16",
        "production-flagship-20260812-19",
        "production-flagship-20260812-20",
        "production-flagship-20260812-21",
        "production-flagship-20260812-22",
        "production-flagship-20260812-24",
    }:
        expected_top = expected_top | {"qa_result"}
    if attempt_id in {
        "production-flagship-20260812-16",
        "production-flagship-20260812-19",
        "production-flagship-20260812-20",
        "production-flagship-20260812-21",
        "production-flagship-20260812-22",
        "production-flagship-20260812-24",
    }:
        expected_top = expected_top | {"warm_cache_result"}
    _require_historical_fields(evidence, frozenset(expected_top), "record")
    requested_runtime = _require_historical_fields(
        evidence.get("requested_runtime"),
        frozenset({"mode", "model"}),
        "requested runtime",
    )
    if requested_runtime != {
        "mode": REQUIRED_PRODUCTION_MODE,
        "model": REQUIRED_PRODUCTION_MODEL,
    }:
        _historical_schema_error("requested runtime")
    _verify_historical_execution(attempt_id, evidence.get("execution_observation"))
    _verify_historical_provider_observation(
        attempt_id,
        evidence.get("provider_observation"),
    )
    _verify_historical_application_result(
        attempt_id,
        evidence.get("application_result"),
    )
    if attempt_id == "production-flagship-20260812-14":
        _verify_attempt_14_capture_provenance(evidence.get("capture_provenance"))
    if attempt_id == "production-flagship-20260812-15":
        _verify_attempt_15_qa_result(evidence.get("qa_result"))
        _verify_attempt_15_capture_provenance(evidence.get("capture_provenance"))
    if attempt_id == "production-flagship-20260812-16":
        _verify_attempt_16_warm_cache_result(evidence.get("warm_cache_result"))
        _verify_attempt_16_qa_result(evidence.get("qa_result"))
        _verify_attempt_16_capture_provenance(evidence.get("capture_provenance"))
    if attempt_id == "production-flagship-20260812-17":
        _verify_attempt_17_capture_provenance(evidence.get("capture_provenance"))
    if attempt_id == "production-flagship-20260812-18":
        _verify_attempt_18_capture_provenance(evidence.get("capture_provenance"))
    if attempt_id == "production-flagship-20260812-21":
        _verify_attempt_21_evidence(evidence)
    if attempt_id in {
        "production-flagship-20260812-22",
        "production-flagship-20260812-23",
    }:
        _verify_attempt_22_or_23_evidence(evidence)
    if attempt_id == "production-flagship-20260812-24":
        _verify_attempt_24_evidence(evidence)
    if attempt_id in _HISTORICAL_TWO_CALL_OUTPUT_LIMITS:
        provider_calls = evidence["provider_observation"]["calls"]
        result = evidence["application_result"]
        execution = evidence["execution_observation"]
        if (
            result["canonical_stage_call_id"] != provider_calls[0]["call_id"]
            or result["ledger_call_id"] != provider_calls[1]["call_id"]
            or execution["ledger_created_at"] != provider_calls[0]["created_at"]
            or execution["ledger_updated_at"] != provider_calls[1]["updated_at"]
        ):
            _historical_schema_error("attempt binding")
    if attempt_id == "production-flagship-20260811-12":
        provider_calls = evidence["provider_observation"]["calls"]
        result = evidence["application_result"]
        execution = evidence["execution_observation"]
        if (
            result["canonical_stage_call_id"] != provider_calls[0]["call_id"]
            or result["orchestrator_plan_call_id"] != provider_calls[1]["call_id"]
            or result["document_source_integrity_call_id"]
            != provider_calls[2]["call_id"]
            or result["ledger_call_id"] != provider_calls[3]["call_id"]
            or execution["ledger_created_at"] != provider_calls[0]["created_at"]
            or execution["ledger_updated_at"] != provider_calls[3]["updated_at"]
        ):
            _historical_schema_error("attempt binding")
    if attempt_id == "production-flagship-20260812-13":
        provider = evidence["provider_observation"]
        ledger = provider["application_ledger_observation"]
        upstream = provider["upstream_request_log_observation"]
        result = evidence["application_result"]
        execution = evidence["execution_observation"]
        if (
            result["ledger_call_id"] != ledger["call_id"]
            or execution["orchestration_id"] != ledger["orchestration_id"]
            or execution["failed_agent_id"] != ledger["agent_id"]
            or provider["upstream_provider"] != upstream["final_provider"]
            or result["error_type"] != ledger["error_type"]
            or result["external_cause_detail"]
            != provider["failure_attribution"]["cause_detail"]
        ):
            _historical_schema_error("attempt binding")
    if attempt_id == "production-flagship-20260812-14":
        provider_calls = evidence["provider_observation"]["calls"]
        result = evidence["application_result"]
        execution = evidence["execution_observation"]
        if (
            execution["source_commit"]
            != "765c610378e7acdc224e200c0e7bbbc65c697c6b"
            or result["canonical_stage_call_id"] != provider_calls[0]["call_id"]
            or result["orchestrator_plan_call_id"] != provider_calls[1]["call_id"]
            or result["process_decision_mapping_call_id"]
            != provider_calls[2]["call_id"]
            or result["document_source_integrity_call_id"]
            != provider_calls[3]["call_id"]
            or result["ledger_call_id"] != provider_calls[2]["call_id"]
            or result["failed_ledger_call_ids"]
            != [provider_calls[2]["call_id"], provider_calls[3]["call_id"]]
            or execution["failed_agent_ids"]
            != [provider_calls[2]["agent_id"], provider_calls[3]["agent_id"]]
            or execution["ledger_created_at"] != provider_calls[0]["created_at"]
            or execution["ledger_updated_at"] != provider_calls[3]["updated_at"]
        ):
            _historical_schema_error("attempt binding")
        for section, expected_sha256 in _HISTORICAL_ATTEMPT_14_SECTION_SHA256.items():
            if _historical_json_sha256(evidence[section]) != expected_sha256:
                _historical_schema_error("record hash")
    if attempt_id == "production-flagship-20260812-15":
        provider_calls = evidence["provider_observation"]["calls"]
        result = evidence["application_result"]
        execution = evidence["execution_observation"]
        qa_result = evidence["qa_result"]
        if (
            execution["source_commit"]
            != "c030f041566b1b318a030dca85e672717efd489f"
            or execution["required_model_agent_ids"]
            != [call["agent_id"] for call in provider_calls]
            or result["complete_model_call_ids"]
            != [call["call_id"] for call in provider_calls]
            or result["complete_deterministic_gate_ids"]
            != execution["deterministic_gate_ids"]
            or qa_result["expected_agent_ids"]
            != execution["required_model_agent_ids"]
            or qa_result["visible_agent_ids"]
            != execution["required_model_agent_ids"]
            or qa_result["expected_gate_ids"]
            != execution["deterministic_gate_ids"]
            or qa_result["visible_gate_ids"][:-1]
            != execution["deterministic_gate_ids"]
            or qa_result["visible_gate_ids"][-1] != qa_result["validator_label"]
        ):
            _historical_schema_error("attempt binding")
        for section, expected_sha256 in _HISTORICAL_ATTEMPT_15_SECTION_SHA256.items():
            if _historical_json_sha256(evidence[section]) != expected_sha256:
                _historical_schema_error("record hash")
    if attempt_id == "production-flagship-20260812-16":
        provider_calls = evidence["provider_observation"]["calls"]
        warm_calls = evidence["warm_cache_result"]["calls"]
        result = evidence["application_result"]
        execution = evidence["execution_observation"]
        if (
            result["complete_model_call_ids"]
            != [call["call_id"] for call in provider_calls]
            or [call["origin_call_id"] for call in warm_calls]
            != result["complete_model_call_ids"]
            or [call["response_id"] for call in warm_calls]
            != [call["response_id"] for call in provider_calls]
            or [call["orchestration_id"] for call in warm_calls]
            != [execution["warm_orchestration_id"]] * 6
            or [call["origin_finish_reason"] for call in warm_calls]
            != [call["finish_reason"] for call in provider_calls]
            or [call["origin_usage"] for call in warm_calls]
            != [
                {
                    "prompt_tokens": call["prompt_tokens"],
                    "completion_tokens": call["completion_tokens"],
                    "total_tokens": call["total_tokens"],
                    "actual_cost_usd": call["actual_cost_usd"],
                    "usage_source": call["usage_source"],
                }
                for call in provider_calls
            ]
            or execution["cold_orchestration_id"]
            != provider_calls[0]["orchestration_id"]
            or execution["warm_orchestration_id"]
            != evidence["warm_cache_result"]["orchestration_id"]
            or execution["ledger_created_at"] != provider_calls[0]["created_at"]
            or execution["ledger_updated_at"] != warm_calls[-1]["updated_at"]
            or result["complete_deterministic_gate_ids"]
            != execution["deterministic_gate_ids"]
        ):
            _historical_schema_error("attempt binding")
        for section, expected_sha256 in _HISTORICAL_ATTEMPT_16_SECTION_SHA256.items():
            if _historical_json_sha256(evidence[section]) != expected_sha256:
                _historical_schema_error("record hash")
    if attempt_id == "production-flagship-20260812-17":
        provider_calls = evidence["provider_observation"]["calls"]
        result = evidence["application_result"]
        execution = evidence["execution_observation"]
        if (
            execution["source_commit"]
            != "580974b0844f3a7e66ba3d324685cd3290798114"
            or execution["orchestration_id"]
            != provider_calls[0]["orchestration_id"]
            or execution["ledger_created_at"] != provider_calls[0]["created_at"]
            or execution["ledger_updated_at"] != provider_calls[-1]["updated_at"]
            or execution["failed_agent_id"] != provider_calls[-1]["agent_id"]
            or result["ledger_call_id"] != provider_calls[-1]["call_id"]
            or result["evidence_checklist_call_id"]
            != provider_calls[-1]["call_id"]
            or result["canonical_stage_call_id"] != provider_calls[0]["call_id"]
            or result["orchestrator_plan_call_id"] != provider_calls[1]["call_id"]
            or result["document_source_integrity_call_id"]
            != provider_calls[2]["call_id"]
            or result["process_decision_mapping_call_id"]
            != provider_calls[3]["call_id"]
            or execution["completed_deterministic_gate_ids"]
            != ["deterministic_process_gate"]
        ):
            _historical_schema_error("attempt binding")
        for section, expected_sha256 in _HISTORICAL_ATTEMPT_17_SECTION_SHA256.items():
            if _historical_json_sha256(evidence[section]) != expected_sha256:
                _historical_schema_error("record hash")
    if attempt_id == "production-flagship-20260812-18":
        provider_calls = evidence["provider_observation"]["calls"]
        result = evidence["application_result"]
        execution = evidence["execution_observation"]
        if (
            execution["source_commit"]
            != "df4db4872e0854af7dbe97e5c86833ab827a1c1b"
            or execution["orchestration_id"]
            != provider_calls[0]["orchestration_id"]
            or execution["ledger_created_at"] != provider_calls[0]["created_at"]
            or execution["ledger_updated_at"] != provider_calls[-1]["updated_at"]
            or execution["failed_agent_id"] != provider_calls[2]["agent_id"]
            or result["ledger_call_id"] != provider_calls[2]["call_id"]
            or result["canonical_stage_call_id"] != provider_calls[0]["call_id"]
            or result["orchestrator_plan_call_id"] != provider_calls[1]["call_id"]
            or result["document_source_integrity_call_id"]
            != provider_calls[2]["call_id"]
            or result["process_decision_mapping_call_id"]
            != provider_calls[3]["call_id"]
            or execution["completed_deterministic_gate_ids"] != []
        ):
            _historical_schema_error("attempt binding")
        for section, expected_sha256 in _HISTORICAL_ATTEMPT_18_SECTION_SHA256.items():
            if _historical_json_sha256(evidence[section]) != expected_sha256:
                _historical_schema_error("record hash")
    if attempt_id == "production-flagship-20260812-19":
        provider = evidence["provider_observation"]
        provider_calls = provider["calls"]
        warm = evidence["warm_cache_result"]
        warm_calls = warm["calls"]
        result = evidence["application_result"]
        execution = evidence["execution_observation"]
        expected_agents = list(execution["required_model_agent_ids"])
        expected_call_ids = list(result["complete_model_call_ids"])
        if (
            len(provider_calls) != 6
            or len(warm_calls) != 6
            or [call.get("agent_id") for call in provider_calls] != expected_agents
            or [call.get("call_id") for call in provider_calls] != expected_call_ids
            or [call.get("agent_id") for call in warm_calls] != expected_agents
        ):
            _historical_schema_error("attempt binding")
        for call in provider_calls:
            verified = _require_historical_fields(
                call,
                _HISTORICAL_ATTEMPT_19_COLD_CALL_FIELDS[call["agent_id"]],
                "provider call observation",
            )
            _verify_positive_usage(verified, "Historical provider call observation")
            if (
                verified["orchestration_id"] != execution["cold_orchestration_id"]
                or not _is_exact_historical_int(verified["call_count"], 1)
                or verified["response_model"]
                not in ACCEPTED_PRODUCTION_RESPONSE_MODELS
                or verified["upstream_provider"] != "DeepInfra"
                or verified["finish_reason"] != "stop"
                or verified["usage_source"] != "response"
                or verified["total_tokens"]
                != verified["prompt_tokens"] + verified["completion_tokens"]
                or not _is_historical_timestamp(verified["created_at"])
                or not _is_historical_timestamp(verified["updated_at"])
            ):
                _historical_schema_error("provider call observation")
        if (
            provider["network_call_count"] != 6
            or provider["actual_cost_complete"] is not True
            or provider["unknown_cost_call_count"] != 0
            or provider["prompt_tokens"]
            != sum(call["prompt_tokens"] for call in provider_calls)
            or provider["completion_tokens"]
            != sum(call["completion_tokens"] for call in provider_calls)
            or provider["total_tokens"] != sum(call["total_tokens"] for call in provider_calls)
            or not math.isclose(
                provider["actual_cost_usd"],
                sum(call["actual_cost_usd"] for call in provider_calls),
                rel_tol=0,
                abs_tol=1e-10,
            )
            or provider["outcomes"]
            != {"succeeded": 5, "succeeded_with_guarded_fallback": 1}
            or provider["physical_provider_max_in_flight"] != 1
            or provider["application_retry_count"] != 0
        ):
            _historical_schema_error("provider call aggregate")
        for index, call in enumerate(warm_calls):
            verified = _require_historical_fields(
                call,
                _HISTORICAL_ATTEMPT_19_WARM_CALL_FIELDS[call["agent_id"]],
                "warm cache call observation",
            )
            cold = provider_calls[index]
            if (
                verified["orchestration_id"] != execution["warm_orchestration_id"]
                or verified["outcome"] != "cache_hit"
                or not _is_exact_historical_int(verified["call_count"], 0)
                or verified["origin_call_id"] != cold["call_id"]
                or verified["response_id"] != cold["response_id"]
                or verified["origin_finish_reason"] != cold["finish_reason"]
                or verified["origin_usage"]
                != {
                    "prompt_tokens": cold["prompt_tokens"],
                    "completion_tokens": cold["completion_tokens"],
                    "total_tokens": cold["total_tokens"],
                    "actual_cost_usd": cold["actual_cost_usd"],
                    "usage_source": cold["usage_source"],
                }
                or not _is_historical_timestamp(verified["created_at"])
                or not _is_historical_timestamp(verified["updated_at"])
            ):
                _historical_schema_error("warm cache call observation")
        if (
            warm["orchestration_id"] != execution["warm_orchestration_id"]
            or warm["provider_network_call_count"] != 0
            or warm["cache_hit_count"] != 6
            or execution["ledger_created_at"] != provider_calls[0]["created_at"]
            or execution["ledger_updated_at"] != warm_calls[-1]["updated_at"]
            or result["complete_deterministic_gate_ids"]
            != execution["deterministic_gate_ids"]
        ):
            _historical_schema_error("attempt binding")
        for section, expected_sha256 in _HISTORICAL_ATTEMPT_19_SECTION_SHA256.items():
            if _historical_json_sha256(evidence[section]) != expected_sha256:
                _historical_schema_error("record hash")
    if attempt_id == "production-flagship-20260812-20":
        provider = evidence["provider_observation"]
        provider_calls = provider["calls"]
        warm = evidence["warm_cache_result"]
        warm_calls = warm["calls"]
        result = evidence["application_result"]
        execution = evidence["execution_observation"]
        expected_agents = set(execution["required_model_agent_ids"])
        if (
            len(provider_calls) != 6
            or len(warm_calls) != 6
            or {call.get("agent_id") for call in provider_calls} != expected_agents
            or {call.get("agent_id") for call in warm_calls} != expected_agents
            or [call.get("call_id") for call in provider_calls]
            != result["complete_model_call_ids"]
        ):
            _historical_schema_error("attempt binding")
        cold_by_agent = {}
        for call in provider_calls:
            agent_id = call.get("agent_id")
            verified = _require_historical_fields(
                call,
                _HISTORICAL_ATTEMPT_20_COLD_CALL_FIELDS[agent_id],
                "provider call observation",
            )
            _verify_positive_usage(verified, "Historical provider call observation")
            if (
                verified["provider"] != "openrouter"
                or verified["provider_endpoint"]
                != "https://openrouter.ai/api/v1/chat/completions"
                or verified["model"] != REQUIRED_PRODUCTION_MODEL
                or verified["orchestration_id"] != execution["cold_orchestration_id"]
                or not _is_exact_historical_int(verified["call_count"], 1)
                or verified["response_model"]
                not in ACCEPTED_PRODUCTION_RESPONSE_MODELS
                or verified["upstream_provider"] != "DeepInfra"
                or verified["finish_reason"] != "stop"
                or verified["usage_source"] != "response"
                or verified["total_tokens"]
                != verified["prompt_tokens"] + verified["completion_tokens"]
                or _HISTORICAL_CALL_ID_PATTERN.fullmatch(verified["call_id"]) is None
                or _HISTORICAL_SHA256_PATTERN.fullmatch(verified["cache_key"]) is None
                or not _is_historical_timestamp(verified["created_at"])
                or not _is_historical_timestamp(verified["updated_at"])
            ):
                _historical_schema_error("provider call observation")
            cold_by_agent[agent_id] = verified
        expected_summary = {
            "records": 12,
            "network_calls": 6,
            "prompt_tokens": 35300,
            "completion_tokens": 3784,
            "total_tokens": 39084,
            "actual_cost_usd": 0.0258212,
            "actual_cost_complete": True,
            "unknown_cost_call_count": 0,
            "outcomes": {
                "cache_hit": 6,
                "succeeded": 4,
                "succeeded_with_guarded_fallback": 2,
            },
        }
        if (
            provider["network_call_count"] != 6
            or provider["actual_cost_complete"] is not True
            or provider["unknown_cost_call_count"] != 0
            or provider["prompt_tokens"]
            != sum(call["prompt_tokens"] for call in provider_calls)
            or provider["completion_tokens"]
            != sum(call["completion_tokens"] for call in provider_calls)
            or provider["total_tokens"] != sum(call["total_tokens"] for call in provider_calls)
            or not math.isclose(
                provider["actual_cost_usd"],
                sum(call["actual_cost_usd"] for call in provider_calls),
                rel_tol=0,
                abs_tol=1e-10,
            )
            or provider["outcomes"]
            != {"succeeded": 4, "succeeded_with_guarded_fallback": 2}
            or provider["global_ledger_summary"] != expected_summary
            or provider["physical_provider_max_in_flight"] != 1
            or provider["application_retry_count"] != 0
        ):
            _historical_schema_error("provider call aggregate")
        for call in warm_calls:
            agent_id = call.get("agent_id")
            verified = _require_historical_fields(
                call,
                _HISTORICAL_ATTEMPT_20_WARM_CALL_FIELDS[agent_id],
                "warm cache call observation",
            )
            cold = cold_by_agent[agent_id]
            if (
                verified["provider"] != "openrouter"
                or verified["provider_endpoint"]
                != "https://openrouter.ai/api/v1/chat/completions"
                or verified["model"] != REQUIRED_PRODUCTION_MODEL
                or verified["orchestration_id"] != execution["warm_orchestration_id"]
                or verified["outcome"] != "cache_hit"
                or not _is_exact_historical_int(verified["call_count"], 0)
                or verified["origin_call_id"] != cold["call_id"]
                or verified["response_id"] != cold["response_id"]
                or verified["origin_finish_reason"] != cold["finish_reason"]
                or verified["origin_usage"]
                != {
                    "prompt_tokens": cold["prompt_tokens"],
                    "completion_tokens": cold["completion_tokens"],
                    "total_tokens": cold["total_tokens"],
                    "actual_cost_usd": cold["actual_cost_usd"],
                    "usage_source": cold["usage_source"],
                }
                or not _is_historical_timestamp(verified["created_at"])
                or not _is_historical_timestamp(verified["updated_at"])
            ):
                _historical_schema_error("warm cache call observation")
        gate_capture = evidence["capture_provenance"]["gate_progression_capture"]
        qa_result = evidence["qa_result"]
        if (
            warm["orchestration_id"] != execution["warm_orchestration_id"]
            or warm["provider_network_call_count"] != 0
            or warm["cache_hit_count"] != 6
            or execution["ledger_created_at"] != provider_calls[0]["created_at"]
            or execution["ledger_updated_at"] != warm_calls[-1]["updated_at"]
            or result["complete_deterministic_gate_ids"]
            != execution["deterministic_gate_ids"]
            or result["deterministic_gate_artifact_hashes_retained"] is not False
            or result["deterministic_gate_artifact_hashes_recoverable"] is not False
            or gate_capture["gate_artifact_hashes_retained"] is not False
            or gate_capture["gate_artifact_hashes_recoverable"] is not False
            or qa_result["failure_type"] != "visual_authority_copy_wording_drift"
            or qa_result["visual_quote_element_count"] != 0
            or qa_result["asserted_phrase_present"] is not False
        ):
            _historical_schema_error("attempt binding")
        for section, expected_sha256 in _HISTORICAL_ATTEMPT_20_SECTION_SHA256.items():
            if _historical_json_sha256(evidence[section]) != expected_sha256:
                _historical_schema_error("record hash")


def _verify_sanitized_evidence(value: Any, label: str) -> None:
    def walk(current: Any, path: str) -> None:
        if isinstance(current, dict):
            for key, child in current.items():
                child_path = f"{path}.{key}"
                if key in FORBIDDEN_PUBLIC_FIELDS:
                    raise VerificationError(
                        f"{label} contains forbidden public field at {child_path}"
                    )
                walk(child, child_path)
        elif isinstance(current, list):
            for index, child in enumerate(current):
                walk(child, f"{path}[{index}]")

    walk(value, "$")


def verify_failed_model_attempt_evidence(
    release: dict[str, Any],
    evidence: dict[str, Any],
) -> None:
    """Verify one retained provider attempt without treating it as acceptance."""

    _verify_historical_attempt_schema(evidence)
    if evidence.get("contract") != "casepath.model-validation-evidence/1.0.0":
        raise VerificationError("Unsupported historical model validation evidence contract")
    if evidence.get("release_id") != release.get("release_id"):
        raise VerificationError("Historical model validation release ID does not match")
    requested_runtime = evidence.get("requested_runtime")
    if not isinstance(requested_runtime, dict) or {
        "mode": requested_runtime.get("mode"),
        "model": requested_runtime.get("model"),
    } != {
        "mode": REQUIRED_PRODUCTION_MODE,
        "model": REQUIRED_PRODUCTION_MODEL,
    }:
        raise VerificationError("Historical model attempt does not name the authorized runtime")
    if evidence.get("status") != "failed_closed":
        raise VerificationError("Historical model attempts must remain failed closed")
    if evidence.get("acceptance_passed") is not False:
        raise VerificationError("Historical model attempts cannot record release acceptance")
    if evidence.get("model_backed_release_evidence") is not False:
        raise VerificationError("Historical model attempts cannot establish release evidence")
    if evidence.get("accepted_ledger_record") is not None:
        raise VerificationError(
            "Historical model attempts cannot retain a release-accepted ledger record"
        )
    expected_sanitization = {
        "private_reference_included": False,
        "provider_credential_included": False,
        "raw_output_included": False,
        "raw_prompt_included": False,
    }
    if evidence.get("sanitization") != expected_sanitization:
        raise VerificationError("Historical model validation sanitization is incomplete")
    _verify_sanitized_evidence(evidence, "Historical model validation evidence")

    result = evidence.get("application_result")
    if evidence.get("attempt_id") in {
        "production-flagship-20260812-15",
        "production-flagship-20260812-16",
        "production-flagship-20260812-19",
        "production-flagship-20260812-20",
        "production-flagship-20260812-21",
        "production-flagship-20260812-22",
    }:
        qa_result = evidence.get("qa_result")
        if (
            not isinstance(result, dict)
            or result.get("outcome") != "accepted"
            or result.get("full_orchestration_accepted") is not True
            or result.get("runtime_acceptance_established") is not False
            or not isinstance(qa_result, dict)
            or qa_result.get("outcome") != "rejected"
            or qa_result.get("runtime_acceptance_established") is not False
        ):
            raise VerificationError(
                "Historical accepted application must remain separate from QA rejection"
            )
    else:
        if not isinstance(result, dict) or result.get("outcome") != "rejected":
            raise VerificationError("Historical failed-closed evidence must record rejection")
        if result.get("successful_ledger_call_bound") is not False:
            raise VerificationError("Historical evidence cannot bind a successful ledger call")
        if result.get("ledger_outcome") not in {None, "failed"}:
            raise VerificationError("Historical evidence cannot record a successful ledger outcome")
        if result.get("canonical_result_accepted") not in {None, False}:
            raise VerificationError("Historical evidence cannot accept a canonical result")
        ledger_call_id = result.get("ledger_call_id")
        if ledger_call_id is not None and (
            not isinstance(ledger_call_id, str) or not ledger_call_id
        ):
            raise VerificationError("Historical ledger call ID must be null or non-empty")

    provider_observation = evidence.get("provider_observation")
    if not isinstance(provider_observation, dict):
        raise VerificationError("Historical provider observation must be an object")
    usage_fields = {
        "actual_cost_usd",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    }
    present_usage_fields = usage_fields.intersection(provider_observation)
    if present_usage_fields == usage_fields:
        _verify_positive_usage(provider_observation, "Historical provider observation")
    elif present_usage_fields:
        raise VerificationError(
            "Historical provider usage must be complete or explicitly unavailable"
        )
    else:
        expected_unknown_usage = {
            "charge_included_in_known_aggregate": False,
            "charge_status": "unknown_unconfirmed",
            "new_openrouter_log_generation_observed": False,
            "synchronous_usage_cost_present": False,
        }
        for key, expected in expected_unknown_usage.items():
            if provider_observation.get(key) != expected:
                raise VerificationError(
                    f"Unknown historical usage requires {key}={expected!r}"
                )
        cache_assessment = provider_observation.get("provider_cache_replay_assessment")
        if cache_assessment not in {
            "likely_unconfirmed",
            "not_assessed",
            "not_applicable_upstream_rejected",
        }:
            raise VerificationError(
                "Unknown historical usage requires a bounded cache-replay assessment"
            )
        if (
            cache_assessment == "not_assessed"
            and provider_observation.get("openrouter_log_check_performed") is not False
        ):
            raise VerificationError(
                "A non-assessed cache replay requires openrouter_log_check_performed=false"
            )
        if cache_assessment == "not_applicable_upstream_rejected" and (
            provider_observation.get("provider_outcome")
            not in {"upstream_rejected", "deepinfra_http_429"}
            or provider_observation.get("openrouter_log_check_performed") is not True
            or provider_observation.get("openrouter_upstream_request_log_observed") is not True
        ):
            raise VerificationError(
                "An upstream-rejected cache assessment requires a checked upstream request log"
            )
        estimated_reservation = provider_observation.get(
            "estimated_cost_reservation_usd"
        )
        if estimated_reservation is not None:
            if (
                not isinstance(estimated_reservation, (int, float))
                or isinstance(estimated_reservation, bool)
                or not math.isfinite(estimated_reservation)
                or estimated_reservation <= 0
            ):
                raise VerificationError(
                    "Historical estimated cost reservation must be positive and finite"
                )
            if provider_observation.get("estimated_reservation_is_actual_charge") is not False:
                raise VerificationError(
                    "Historical estimated reservation must not be represented as actual charge"
                )
        if "response_id" in provider_observation or "response_model" in provider_observation:
            raise VerificationError(
                "Unknown historical usage cannot retain an unobserved response identity"
            )


def verify_static_runtime_acceptance_contract(release: dict[str, Any]) -> None:
    """Verify immutable criteria and history; never infer a deployment verdict."""

    verify_agentic_runtime_contract(release)
    verify_render_runtime_contract(release)
    truth = release.get("truth")
    if not isinstance(truth, dict):
        raise VerificationError("Release contract truth must be an object")
    expected_build = {
        "execution_mode": "deterministic_reference",
        "model_backed": False,
        "model_calls": 0,
        "status": "passed",
    }
    if truth.get("deterministic_build") != expected_build:
        raise VerificationError(
            f"Deterministic build evidence must remain {expected_build!r}"
        )

    runtime = truth.get("production_runtime_acceptance")
    if not isinstance(runtime, dict):
        raise VerificationError("Production runtime acceptance criteria must be an object")
    if "status" in runtime or "model_backed_accepted" in runtime:
        raise VerificationError(
            "The tracked criteria contract must not embed a mutable runtime verdict"
        )
    expected_dynamic_evidence = {
        "qa_gate": "focused-flagship-journey-v20",
        "report_path": QA_REPORT_PATH,
        "evidence_manifest_path": QA_EVIDENCE_MANIFEST_PATH,
        "evidence_manifest_contract": QA_EVIDENCE_MANIFEST_CONTRACT,
        "required_report_status": "passed",
        "requires_release_id_match": True,
        "requires_non_unknown_source_commit": True,
        "requires_same_source_commit": True,
    }
    if runtime.get("verdict_authority") != RUNTIME_VERDICT_AUTHORITY:
        raise VerificationError("Runtime verdict authority must be the dynamic QA artifacts")
    if runtime.get("source_contract_embeds_runtime_verdict") is not False:
        raise VerificationError("The source contract must remain verdict-free")
    if runtime.get("dynamic_evidence") != expected_dynamic_evidence:
        raise VerificationError(
            "Runtime criteria must point to the exact report and evidence-manifest pair"
        )
    for key in REQUIRED_RUNTIME_ACCEPTANCE_FLAGS:
        if runtime.get(key) is not True:
            raise VerificationError(f"Production runtime acceptance must require {key}")
    expected_runtime = {
        "required_mode": REQUIRED_PRODUCTION_MODE,
        "required_model": REQUIRED_PRODUCTION_MODEL,
        "model_acceptance_scope": "visible_browser_flagship",
        "learning_comparison_authority": "deterministic_application_tool",
        "required_final_model_ledger_records": 12,
        "required_final_model_network_calls": 6,
        "required_final_cache_hits": 6,
        "required_provider_max_in_flight": 1,
        "required_runtime_profile": REQUIRED_RUNTIME_PROFILE,
    }
    for key, expected in expected_runtime.items():
        if runtime.get(key) != expected:
            raise VerificationError(f"Production runtime {key} must be {expected!r}")

    history = truth.get("historical_model_validation")
    expected_history = {
        "scope": "failed_closed_history_only",
        "evidence_records": list(HISTORICAL_MODEL_VALIDATION_RECORDS),
        "establishes_current_runtime_acceptance": False,
    }
    if history != expected_history:
        raise VerificationError(
            "Historical model validation must retain exactly twenty-four failed-closed records"
        )
    for path_text in HISTORICAL_MODEL_VALIDATION_RECORDS:
        verify_failed_model_attempt_evidence(
            release,
            load_json(REPOSITORY / path_text),
        )


def _orchestration_audit(run: dict[str, Any]) -> dict[str, Any] | None:
    result = run.get("result")
    if not isinstance(result, dict):
        return None
    audit_container = result.get("audit")
    if isinstance(audit_container, dict) and isinstance(
        audit_container.get("agent_orchestration"), dict
    ):
        return audit_container["agent_orchestration"]
    direct = result.get("agent_orchestration")
    return direct if isinstance(direct, dict) else None


def _causal_failure(path: str) -> None:
    """Fail without echoing retained claim or provider values."""

    raise VerificationError(f"Dynamic flagship causal proof is invalid at {path}")


def _causal_hash(value: Any, path: str) -> str:
    try:
        return accepted_artifact_hash(value)
    except VerificationError:
        _causal_failure(path)


def runtime_artifact_hash(value: Any) -> str:
    """Match the backend's internal hash for JSON DTOs that may contain floats."""

    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise VerificationError("Runtime artifact is not finite canonical JSON") from exc
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _runtime_canonical_facts_value(facts: list[Any], path: str) -> list[Any]:
    """Rebuild the backend fact hash after a JSON/JavaScript round trip.

    JavaScript serializes integral floats such as ``0.0`` as ``0``.  The
    backend fact schema owns two numeric float surfaces (fact confidence and
    visual-reference region coordinates), so restore only those declared
    fields before hashing.  Every claim-bearing string and all other fields
    remain byte-for-byte hash bound.  The normalized value is also reused by
    composite runtime hashes so JSON's ``1.0`` to ``1`` round trip cannot
    create a false mismatch.
    """

    normalized = deepcopy(facts)
    for fact_index, raw_fact in enumerate(normalized):
        fact_path = f"{path}[{fact_index}]"
        fact = _causal_mapping(raw_fact, fact_path)
        confidence = fact.get("confidence")
        if (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not math.isfinite(confidence)
            or not 0 <= confidence <= 1
        ):
            _causal_failure(f"{fact_path}.confidence")
        fact["confidence"] = float(confidence)
        refs = _causal_list(fact.get("source_refs"), f"{fact_path}.source_refs")
        for ref_index, raw_ref in enumerate(refs):
            ref_path = f"{fact_path}.source_refs[{ref_index}]"
            ref = _causal_mapping(raw_ref, ref_path)
            if ref.get("locator_kind") != "visual_observation":
                continue
            region = _causal_list(ref.get("region"), f"{ref_path}.region")
            if (
                len(region) != 4
                or any(
                    not isinstance(coordinate, (int, float))
                    or isinstance(coordinate, bool)
                    or not math.isfinite(coordinate)
                    or not 0 <= coordinate <= 1
                    for coordinate in region
                )
            ):
                _causal_failure(f"{ref_path}.region")
            ref["region"] = [float(coordinate) for coordinate in region]
    return normalized


def _runtime_canonical_facts_hash(facts: list[Any], path: str) -> str:
    return runtime_artifact_hash(_runtime_canonical_facts_value(facts, path))


def _causal_runtime_hash(value: Any, path: str) -> str:
    try:
        return runtime_artifact_hash(value)
    except VerificationError:
        _causal_failure(path)


def _causal_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _causal_failure(path)
    return value


def _causal_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _causal_failure(path)
    return value


def _causal_text_list(
    value: Any,
    path: str,
    *,
    sorted_values: bool = False,
    source_refs: bool = False,
) -> list[str]:
    values = _causal_list(value, path)
    if (
        any(not isinstance(item, str) or not item for item in values)
        or len(set(values)) != len(values)
        or (sorted_values and values != sorted(values))
        or (
            source_refs
            and any(re.fullmatch(r"src_[0-9a-f]{24}", item) is None for item in values)
        )
    ):
        _causal_failure(path)
    return values


def _causal_basis_points(value: Any, path: str) -> None:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 0 <= value <= 10_000
    ):
        _causal_failure(path)


def _normalized_grounding_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _observable_metadata_value(
    package: Mapping[str, Any], artifact_id: str, field: str
) -> Any:
    if artifact_id == "intake":
        current: Any = package.get("intake_metadata")
    elif artifact_id == "message":
        current = package.get("customer_message")
    else:
        current = next(
            (
                item
                for item in package.get("artifacts", [])
                if isinstance(item, Mapping)
                and item.get("artifact_id") == artifact_id
            ),
            None,
        )
    for part in field.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _observable_text_values(
    package: Mapping[str, Any], artifact_id: str, page: int
) -> list[str]:
    if artifact_id == "message" and page == 1:
        message = package.get("customer_message")
        if isinstance(message, Mapping):
            return [
                value
                for key in ("subject", "body")
                if isinstance((value := message.get(key)), str)
            ]
        return []
    artifact = next(
        (
            item
            for item in package.get("artifacts", [])
            if isinstance(item, Mapping) and item.get("artifact_id") == artifact_id
        ),
        None,
    )
    if not isinstance(artifact, Mapping):
        return []
    if artifact.get("media_type") == "application/pdf":
        page_value = next(
            (
                item
                for item in artifact.get("extracted_pages", [])
                if isinstance(item, Mapping) and item.get("page") == page
            ),
            None,
        )
        text_value = page_value.get("text") if isinstance(page_value, Mapping) else None
        return [text_value] if isinstance(text_value, str) else []
    if artifact.get("media_type") == "message/rfc822" and page == 1:
        email = artifact.get("parsed_email")
        if isinstance(email, Mapping):
            return [value for value in email.values() if isinstance(value, str)]
    return []


def _verify_grounding_ref(
    ref: Mapping[str, Any], package: Mapping[str, Any], path: str
) -> None:
    artifact_id = ref.get("artifact_id")
    locator_kind = ref.get("locator_kind")
    package_artifacts = {
        item.get("artifact_id"): item
        for item in package.get("artifacts", [])
        if isinstance(item, Mapping)
    }
    if artifact_id not in {"message", "intake", *package_artifacts}:
        _causal_failure(f"{path}.artifact_id")
    if locator_kind == "text_quote":
        if set(ref) != {"artifact_id", "locator_kind", "page", "excerpt", "agent"}:
            _causal_failure(path)
        page = ref.get("page")
        excerpt = ref.get("excerpt")
        agent = ref.get("agent")
        if (
            not isinstance(page, int)
            or isinstance(page, bool)
            or page < 1
            or not isinstance(excerpt, str)
            or not excerpt.strip()
            or not isinstance(agent, str)
            or not agent.strip()
        ):
            _causal_failure(path)
        candidates = _observable_text_values(package, str(artifact_id), page)
        normalized_excerpt = _normalized_grounding_text(excerpt)
        if not any(
            normalized_excerpt in _normalized_grounding_text(candidate)
            for candidate in candidates
        ):
            _causal_failure(f"{path}.excerpt")
        return
    if locator_kind == "metadata_field":
        if set(ref) != {"artifact_id", "locator_kind", "field", "value", "agent"}:
            _causal_failure(path)
        field = ref.get("field")
        agent = ref.get("agent")
        if (
            not isinstance(field, str)
            or not field.strip()
            or not isinstance(agent, str)
            or not agent.strip()
            or _observable_metadata_value(package, str(artifact_id), field)
            != ref.get("value")
        ):
            _causal_failure(path)
        return
    if locator_kind != "visual_observation" or set(ref) != VISUAL_REFERENCE_FIELDS:
        _causal_failure(path)
    artifact = package_artifacts.get(artifact_id)
    expected_artifact = CASEPATH_ARTIFACTS.get(artifact_id)
    release_image_sha256 = RELEASE_VISUAL_IMAGE_SHA256_BY_ARTIFACT.get(artifact_id)
    region = ref.get("region")
    if (
        not isinstance(artifact, Mapping)
        or not str(artifact.get("media_type", "")).startswith("image/")
        or not isinstance(expected_artifact, Mapping)
        or not isinstance(release_image_sha256, str)
        or artifact.get("sha256") != release_image_sha256
        or expected_artifact.get("sha256") != release_image_sha256
        or ref.get("image_sha256") != release_image_sha256
        or ref.get("producer") != VISUAL_ANNOTATION_PRODUCER
        or ref.get("authority") != VISUAL_ANNOTATION_AUTHORITY
        or ref.get("annotation_contract") != VISUAL_ANNOTATION_CONTRACT
        or ref.get("annotation_version") != VISUAL_ANNOTATION_VERSION
        or not isinstance(ref.get("observation"), str)
        or not ref.get("observation", "").strip()
        or not isinstance(region, list)
        or len(region) != 4
        or any(
            not isinstance(number, (int, float))
            or isinstance(number, bool)
            or not math.isfinite(number)
            or not 0 <= number <= 1
            for number in region
        )
        or region[2] <= 0
        or region[3] <= 0
        or region[0] + region[2] > 1
        or region[1] + region[3] > 1
    ):
        _causal_failure(path)


def _verify_governed_law_contract(
    legal: Mapping[str, Any], process: Mapping[str, Any]
) -> None:
    expected = governed_legal_context()
    if (
        legal != expected
        or legal.get("contract") != RELEASE_LAW_CONTRACT
        or legal.get("registry_version") != RELEASE_LAW_REGISTRY_VERSION
        or legal.get("node_links") != RELEASE_LAW_NODE_LINKS
    ):
        _causal_failure("result.legal_research")
    questions = legal.get("questions")
    if not isinstance(questions, list):
        _causal_failure("result.legal_research.questions")
    actual_question_joins = {
        question.get("question_id"): {
            field: question.get(field)
            for field in ("source_ids", "interpretation_ids", "process_node_ids")
        }
        for question in questions
        if isinstance(question, Mapping)
    }
    if (
        len(actual_question_joins) != len(questions)
        or actual_question_joins != RELEASE_LAW_QUESTION_JOINS
    ):
        _causal_failure("result.legal_research.questions")
    sources = legal.get("sources")
    if not isinstance(sources, list):
        _causal_failure("result.legal_research.sources")
    source_mappings = [
        _causal_mapping(source, f"result.legal_research.sources[{index}]")
        for index, source in enumerate(sources)
    ]
    if [source.get("source_id") for source in source_mappings] != list(
        RELEASE_LAW_SOURCE_CONTRACTS
    ):
        _causal_failure("result.legal_research.sources")
    for index, source in enumerate(source_mappings):
        path = f"result.legal_research.sources[{index}]"
        source_contract = RELEASE_LAW_SOURCE_CONTRACTS.get(source.get("source_id"))
        passage = source.get("passage_text")
        retrieval = source.get("retrieval")
        if (
            not isinstance(source_contract, Mapping)
            or not isinstance(passage, str)
            or hashlib.sha256(passage.encode("utf-8")).hexdigest()
            != source.get("passage_sha256")
            or source.get("passage_sha256")
            != source_contract.get("passage_sha256")
            or not isinstance(retrieval, Mapping)
            or set(retrieval)
            != {
                "method",
                "retrieved_at",
                "registry_version",
                "snapshot_url",
                "snapshot_sha256",
                "snapshot_scope",
            }
            or retrieval.get("registry_version") != RELEASE_LAW_REGISTRY_VERSION
            or retrieval.get("snapshot_sha256")
            != source_contract.get("snapshot_sha256")
            or retrieval.get("snapshot_scope")
            != source_contract.get("snapshot_scope")
        ):
            _causal_failure(path)
        scope = retrieval.get("snapshot_scope")
        if source.get("source_id") == "bwo-conciliation":
            if (
                scope != "normalized_official_passage_utf8"
                or retrieval.get("snapshot_sha256") != source.get("passage_sha256")
            ):
                _causal_failure(f"{path}.retrieval")
        elif scope != "official_pdf_bytes":
            _causal_failure(f"{path}.retrieval.snapshot_scope")
    node_links = legal.get("node_links")
    if not isinstance(node_links, Mapping):
        _causal_failure("result.legal_research.node_links")
    nodes = _causal_list(process.get("nodes"), "result.process.nodes")
    for index, raw_node in enumerate(nodes):
        node = _causal_mapping(raw_node, f"result.process.nodes[{index}]")
        node_id = node.get("node_id")
        if node.get("legal_source_ids") != node_links.get(node_id, []):
            _causal_failure(f"result.process.nodes[{index}].legal_source_ids")


def _verify_reciprocal_evidence_contract(
    process: Mapping[str, Any],
    checklist: Mapping[str, Any],
    *,
    claim_id: str,
    include_memory_extension: bool = False,
    path: str = "result",
) -> None:
    nodes = _causal_list(process.get("nodes"), f"{path}.process.nodes")
    node_ids = [
        node.get("node_id") if isinstance(node, Mapping) else None for node in nodes
    ]
    expected_node_ids = list(BASE_PROCESS_NODE_IDS)
    if include_memory_extension:
        expected_node_ids.append("ventilation_dispute")
    if (
        any(not isinstance(node_id, str) or not node_id for node_id in node_ids)
        or len(set(node_ids)) != len(node_ids)
        or node_ids != expected_node_ids
    ):
        _causal_failure(f"{path}.process.nodes[].node_id")
    edges = _causal_list(process.get("edges"), f"{path}.process.edges")
    edge_pairs = [
        (edge.get("source"), edge.get("target"))
        if isinstance(edge, Mapping)
        else (None, None)
        for edge in edges
    ]
    expected_edge_pairs = list(BASE_PROCESS_EDGE_PAIRS)
    if include_memory_extension:
        expected_edge_pairs.extend(
            [
                ("evidence_gap", "ventilation_dispute"),
                ("ventilation_dispute", "causation"),
            ]
        )
    if len(set(edge_pairs)) != len(edge_pairs) or edge_pairs != expected_edge_pairs:
        _causal_failure(f"{path}.process.edges")
    items = _causal_list(checklist.get("items"), f"{path}.checklist.items")
    item_ids = [
        item.get("item_id") if isinstance(item, Mapping) else None for item in items
    ]
    expected_item_ids = EVIDENCE_ITEM_IDS_BY_CLAIM.get(claim_id)
    if (
        expected_item_ids is None
        or any(not isinstance(item_id, str) or not item_id for item_id in item_ids)
        or len(set(item_ids)) != len(item_ids)
        or item_ids != list(expected_item_ids)
    ):
        _causal_failure(f"{path}.checklist.items[].item_id")
    owners: dict[str, list[str]] = {str(item_id): [] for item_id in item_ids}
    for index, raw_node in enumerate(nodes):
        node = _causal_mapping(raw_node, f"{path}.process.nodes[{index}]")
        requirements = _causal_text_list(
            node.get("evidence_requirement_ids"),
            f"{path}.process.nodes[{index}].evidence_requirement_ids",
        )
        if any(item_id not in owners for item_id in requirements):
            _causal_failure(
                f"{path}.process.nodes[{index}].evidence_requirement_ids"
            )
        for item_id in requirements:
            owners[item_id].append(str(node["node_id"]))
    selected_path = _causal_text_list(
        process.get("selected_path"), f"{path}.process.selected_path"
    )
    overlay = _causal_mapping(
        process.get("current_overlay"), f"{path}.process.current_overlay"
    )
    next_action = overlay.get("next_action_node_id")
    if not isinstance(next_action, str) or next_action not in node_ids:
        _causal_failure(f"{path}.process.current_overlay.next_action_node_id")
    active_nodes = {*selected_path, next_action}
    expected_owners = deepcopy(BASE_EVIDENCE_NODE_IDS)
    if include_memory_extension:
        expected_owners["management_position"] = (
            "dispute",
            "ventilation_dispute",
        )
        expected_owners["use_evidence"] = ("ventilation_dispute",)
    for index, raw_item in enumerate(items):
        item = _causal_mapping(raw_item, f"{path}.checklist.items[{index}]")
        item_id = str(item["item_id"])
        item_owners = owners[item_id]
        if (
            tuple(item_owners) != expected_owners[item_id]
            or item.get("node_ids") != item_owners
            or item.get("node_id") != item_owners[0]
            or item.get("current_path")
            is not bool(active_nodes.intersection(item_owners))
            or item.get("legal_basis_ids") != EVIDENCE_LEGAL_BASIS_IDS[item_id]
        ):
            _causal_failure(f"{path}.checklist.items[{index}]")


def _verify_release_fact_relationships(
    *,
    claim_id: str,
    facts: list[Any],
    process: Mapping[str, Any],
    checklist: Mapping[str, Any],
    include_memory_extension: bool,
    path: str,
) -> None:
    expected_process = deepcopy(RELEASE_PROCESS_FACT_IDS_BY_CLAIM.get(claim_id))
    expected_evidence = RELEASE_EVIDENCE_FACT_ID_BY_CLAIM.get(claim_id)
    expected_roles = RELEASE_SEMANTIC_FACT_ID_BY_CLAIM.get(claim_id)
    if (
        not isinstance(expected_process, dict)
        or not isinstance(expected_evidence, dict)
        or not isinstance(expected_roles, dict)
    ):
        _causal_failure(f"{path}.claim_id")
    if include_memory_extension:
        expected_process["ventilation_dispute"] = [
            expected_roles[SEMANTIC_MEMORY_ROLE]
        ]
    actual_process = {
        node.get("node_id"): node.get("fact_ids")
        for node in process.get("nodes", [])
        if isinstance(node, Mapping)
    }
    actual_evidence = {
        item.get("item_id"): item.get("fact_id")
        for item in checklist.get("items", [])
        if isinstance(item, Mapping)
    }
    actual_roles = {
        fact.get("semantic_role"): fact.get("fact_id")
        for fact in facts
        if isinstance(fact, Mapping) and fact.get("semantic_role") is not None
    }
    fact_ids = {
        fact.get("fact_id") for fact in facts if isinstance(fact, Mapping)
    }
    referenced_fact_ids = {
        fact_id for values in expected_process.values() for fact_id in values
    } | set(expected_evidence.values()) | set(expected_roles.values())
    if (
        actual_process != expected_process
        or actual_evidence != expected_evidence
        or actual_roles != expected_roles
        or not referenced_fact_ids <= fact_ids
    ):
        _causal_failure(f"{path}.fact_relationships")


def _verify_grounded_flagship_contract(result: Mapping[str, Any]) -> None:
    claim_id = result.get("claim_id")
    if claim_id != "DEF-027-E0-DEMO":
        _causal_failure("result.claim_id")
    package = observable_claim_package(CASEPATH_CLAIMS[claim_id])
    facts = _causal_list(result.get("facts"), "result.facts")
    semantic_roles: list[str] = []
    fact_ids: set[str] = set()
    for index, raw_fact in enumerate(facts):
        path = f"result.facts[{index}]"
        fact = _causal_mapping(raw_fact, path)
        fact_id = fact.get("fact_id")
        confidence = fact.get("confidence")
        semantic_role = fact.get("semantic_role")
        if (
            set(fact) != CANONICAL_FACT_FIELDS
            or not isinstance(fact_id, str)
            or not fact_id
            or fact_id in fact_ids
            or not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not math.isfinite(confidence)
            or not 0 <= confidence <= 1
            or semantic_role not in {None, SEMANTIC_MEMORY_ROLE}
        ):
            _causal_failure(path)
        fact_ids.add(fact_id)
        refs = _causal_list(fact.get("source_refs"), f"{path}.source_refs")
        for ref_index, raw_ref in enumerate(refs):
            ref = _causal_mapping(raw_ref, f"{path}.source_refs[{ref_index}]")
            _verify_grounding_ref(ref, package, f"{path}.source_refs[{ref_index}]")
        if semantic_role is not None:
            semantic_roles.append(semantic_role)
            if fact.get("state") != "known" or not refs:
                _causal_failure(f"{path}.semantic_role")
    if semantic_roles != [SEMANTIC_MEMORY_ROLE]:
        _causal_failure("result.facts[].semantic_role")

    process = _causal_mapping(result.get("process"), "result.process")
    checklist = _causal_mapping(result.get("checklist"), "result.checklist")
    legal = _causal_mapping(result.get("legal_research"), "result.legal_research")
    _verify_governed_law_contract(legal, process)
    _verify_reciprocal_evidence_contract(
        process,
        checklist,
        claim_id=claim_id,
    )
    _verify_release_fact_relationships(
        claim_id=claim_id,
        facts=facts,
        process=process,
        checklist=checklist,
        include_memory_extension=False,
        path="result",
    )

    precedents = _causal_list(result.get("precedents"), "result.precedents")
    receipt = _causal_mapping(
        result.get("precedent_ranking"), "result.precedent_ranking"
    )
    expected_ranking = rank_precedents(
        current_claim_id=claim_id,
        understanding={
            "category": result.get("category"),
            "subcategory": result.get("subcategory"),
            "facts": facts,
        },
        process=dict(process),
        checklist=dict(checklist),
        memories=[],
        corpus=GOVERNED_PRECEDENT_CORPUS,
    )
    if precedents != expected_ranking["results"]:
        _causal_failure("result.precedents")
    if receipt != expected_ranking["receipt"]:
        _causal_failure("result.precedent_ranking")

    verification = _causal_mapping(result.get("verification"), "result.verification")
    checks = _causal_list(verification.get("checks"), "result.verification.checks")
    names = [
        check.get("name") if isinstance(check, Mapping) else None for check in checks
    ]
    if (
        verification.get("valid") is not True
        or verification.get("computed") is not True
        or names != list(REQUIRED_PLAYBOOK_CHECKS)
        or any(
            not isinstance(check, Mapping) or check.get("status") != "passed"
            for check in checks
        )
    ):
        _causal_failure("result.verification.checks")


def _semantic_process_dto(process: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(process))
    value.pop("agent_contribution", None)
    for node in value.get("nodes", []):
        if isinstance(node, dict):
            node.pop("agent_decision_contributions", None)
    return value


def _semantic_checklist_dto(checklist: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(checklist))
    value.pop("agent_contribution", None)
    for item in value.get("items", []):
        if isinstance(item, dict):
            item.pop("agent_contribution", None)
    return value


def _semantic_fact_signature(facts: list[Any], path: str) -> dict[str, Any]:
    roles: dict[str, Any] = {}
    for index, raw_fact in enumerate(facts):
        fact = _causal_mapping(raw_fact, f"{path}[{index}]")
        role = fact.get("semantic_role")
        if role is None:
            continue
        if role != SEMANTIC_MEMORY_ROLE or role in roles:
            _causal_failure(f"{path}[{index}].semantic_role")
        refs = _causal_list(fact.get("source_refs"), f"{path}[{index}].source_refs")
        roles[role] = {
            "fact_id": fact.get("fact_id"),
            "state": fact.get("state"),
            "grounded_source_count": len(refs),
        }
    if set(roles) != {SEMANTIC_MEMORY_ROLE}:
        _causal_failure(f"{path}.semantic_role")
    return roles


def _verify_learning_snapshot_projection(
    snapshot: Mapping[str, Any],
    run: Mapping[str, Any],
    result: Mapping[str, Any],
    path: str,
) -> None:
    process = _causal_mapping(result.get("process"), f"{path}.process")
    checklist = _causal_mapping(result.get("checklist"), f"{path}.checklist")
    verification = _causal_mapping(
        result.get("verification"), f"{path}.verification"
    )
    expected = {
        "run_id": run.get("run_id"),
        "completed_at": run.get("completed_at"),
        "verification_hash": verification.get("whole_playbook_hash"),
        "verification_valid": True,
        "process_node_ids": [
            node.get("node_id") for node in process.get("nodes", [])
        ],
        "process_edge_pairs": [
            [edge.get("source"), edge.get("target")]
            for edge in process.get("edges", [])
        ],
        "current_node_id": process.get("current_node"),
        "required_now_item_ids": [
            item.get("item_id")
            for item in checklist.get("required", [])
            if item.get("status") == "still_needed"
        ],
        "conditional_item_ids": [
            item.get("item_id")
            for item in checklist.get("required", [])
            if item.get("status") == "conditional"
        ],
        "precedents": [
            {
                "claim_id": item.get("claim_id"),
                "memory_id": item.get("memory_id"),
                "review_status": item.get("review_status"),
            }
            for item in result.get("precedents", [])
        ],
        "reviewed_memory_used": result.get("reviewed_memory_used") is True,
        "memory_application": result.get("memory_application"),
        "shared_rule_applied": result.get("shared_rule_applied") is True,
        "playbook_version": result.get("playbook", {}).get("version"),
    }
    if (
        any(snapshot.get(key) != value for key, value in expected.items())
        or not re.fullmatch(r"[0-9a-f]{64}", str(snapshot.get("result_hash", "")))
    ):
        _causal_failure(path)


def _apply_release_evidence_relations(
    process: dict[str, Any], checklist: dict[str, Any]
) -> None:
    items = checklist.get("items")
    if not isinstance(items, list):
        _causal_failure("learning_replay.checklist.items")
    owners: dict[str, list[str]] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("item_id"), str):
            _causal_failure("learning_replay.checklist.items")
        owners[item["item_id"]] = []
    for node in process.get("nodes", []):
        if not isinstance(node, dict) or not isinstance(node.get("node_id"), str):
            _causal_failure("learning_replay.process.nodes")
        requirements = node.get("evidence_requirement_ids")
        if not isinstance(requirements, list):
            _causal_failure("learning_replay.process.nodes.evidence_requirement_ids")
        for item_id in requirements:
            if item_id not in owners:
                _causal_failure("learning_replay.process.nodes.evidence_requirement_ids")
            owners[item_id].append(node["node_id"])
    overlay = process.get("current_overlay")
    if not isinstance(overlay, dict):
        _causal_failure("learning_replay.process.current_overlay")
    active = set(process.get("selected_path", []))
    active.add(overlay.get("next_action_node_id"))
    for item in items:
        item_owners = owners[item["item_id"]]
        if not item_owners:
            _causal_failure("learning_replay.checklist.items.node_ids")
        item["node_ids"] = item_owners
        item["node_id"] = item_owners[0]
        item["current_path"] = bool(active.intersection(item_owners))


def _replay_memory_transform(
    process: dict[str, Any], checklist: dict[str, Any], ventilation_fact_id: str
) -> dict[str, Any]:
    if any(
        isinstance(node, Mapping) and node.get("node_id") == "ventilation_dispute"
        for node in process.get("nodes", [])
    ):
        _causal_failure("learning_replay.process.nodes")
    items = {
        item.get("item_id"): item
        for item in checklist.get("items", [])
        if isinstance(item, dict)
    }
    if not {"building_envelope", "use_evidence"} <= set(items):
        _causal_failure("learning_replay.checklist.items")
    ventilation_node = {
        "node_id": "ventilation_dispute",
        "title": "Test the ventilation allegation",
        "question": "What exactly is alleged, and does competent evidence support it?",
        "state": "inactive",
        "answer": (
            "Preserve as disputed; test only if competent assessment leaves a "
            "plausible use-related branch"
        ),
        "why": (
            "Unverified demo memory guidance keeps the allegation explicit without "
            "treating it as technical cause."
        ),
        "kind": "action",
        "main_spine": False,
        "fact_ids": [ventilation_fact_id],
        "legal_source_ids": ["handling-causation", "handling-evidence-order"],
        "evidence_requirement_ids": ["management_position", "use_evidence"],
        "branches": [],
        "activation": "recurrence + ventilation allegation + cause unresolved",
    }
    first_edge = {
        "source": "evidence_gap",
        "target": "ventilation_dispute",
        "condition": "neutral inspection leaves a plausible use-related factor",
        "state": "possible",
    }
    second_edge = {
        "source": "ventilation_dispute",
        "target": "causation",
        "condition": "allegation evidence assessed",
        "state": "loop",
    }
    process["nodes"].append(ventilation_node)
    process["edges"].extend([first_edge, second_edge])
    removed_from: list[str] = []
    for node in process["nodes"]:
        if node["node_id"] == "ventilation_dispute":
            continue
        requirements = node.get("evidence_requirement_ids", [])
        if "use_evidence" in requirements:
            node["evidence_requirement_ids"] = [
                item_id for item_id in requirements if item_id != "use_evidence"
            ]
            removed_from.append(node["node_id"])
    process["memory_used"] = True
    process["case_specific_guidance_applied"] = True
    process["shared_rule_applied"] = False
    items["building_envelope"].update(
        {
            "status": "conditional",
            "required_level": "conditional",
            "applies_when": (
                "The neutral first assessment is inconclusive or indicates an "
                "envelope issue"
            ),
            "why": (
                "Unverified demo memory guidance keeps broader building-envelope "
                "testing conditional on the first competent assessment."
            ),
        }
    )
    items["use_evidence"].update(
        {
            "status": "conditional",
            "required_level": "conditional",
            "applies_when": (
                "A competent assessment leaves a plausible use-related branch"
            ),
            "why": (
                "Unverified demo memory guidance requests use-related evidence only "
                "if competent assessment leaves that branch plausible."
            ),
        }
    )
    _apply_release_evidence_relations(process, checklist)
    checklist.update(_checklist_derived_sections(checklist["items"]))
    _apply_release_evidence_relations(process, checklist)
    checklist["memory_used"] = True
    checklist["case_specific_guidance_applied"] = True
    checklist["shared_rule_applied"] = False
    return {
        "ventilation_node": ventilation_node,
        "first_edge": first_edge,
        "second_edge": second_edge,
        "removed_from": removed_from,
        "building_envelope": items["building_envelope"],
        "use_evidence": items["use_evidence"],
    }


def _keyed_dto_delta(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, Any]:
    before_process = _semantic_process_dto(
        _causal_mapping(before.get("process"), "learning.baseline.process")
    )
    after_process = _semantic_process_dto(
        _causal_mapping(after.get("process"), "learning.later.process")
    )
    before_checklist = _semantic_checklist_dto(
        _causal_mapping(before.get("checklist"), "learning.baseline.checklist")
    )
    after_checklist = _semantic_checklist_dto(
        _causal_mapping(after.get("checklist"), "learning.later.checklist")
    )

    def keyed(values: Any, key: Any, path: str) -> dict[Any, Any]:
        if not isinstance(values, list):
            _causal_failure(path)
        result: dict[Any, Any] = {}
        for value in values:
            if not isinstance(value, Mapping):
                _causal_failure(path)
            item_key = key(value)
            if item_key in result:
                _causal_failure(path)
            result[item_key] = value
        return result

    before_nodes = keyed(
        before_process.get("nodes"), lambda value: value.get("node_id"), "learning.baseline.process.nodes"
    )
    after_nodes = keyed(
        after_process.get("nodes"), lambda value: value.get("node_id"), "learning.later.process.nodes"
    )
    before_edges = keyed(
        before_process.get("edges"),
        lambda value: (value.get("source"), value.get("target")),
        "learning.baseline.process.edges",
    )
    after_edges = keyed(
        after_process.get("edges"),
        lambda value: (value.get("source"), value.get("target")),
        "learning.later.process.edges",
    )
    before_items = keyed(
        before_checklist.get("items"), lambda value: value.get("item_id"), "learning.baseline.checklist.items"
    )
    after_items = keyed(
        after_checklist.get("items"), lambda value: value.get("item_id"), "learning.later.checklist.items"
    )

    def added(left: Mapping[Any, Any], right: Mapping[Any, Any]) -> list[Any]:
        return sorted(set(right) - set(left))

    def removed(left: Mapping[Any, Any], right: Mapping[Any, Any]) -> list[Any]:
        return sorted(set(left) - set(right))

    def changed(left: Mapping[Any, Any], right: Mapping[Any, Any]) -> list[Any]:
        return sorted(key for key in set(left) & set(right) if left[key] != right[key])

    def root_changes(
        left: Mapping[str, Any], right: Mapping[str, Any], excluded: set[str]
    ) -> list[str]:
        return sorted(
            key
            for key in set(left) | set(right)
            if key not in excluded and left.get(key) != right.get(key)
        )

    added_edge_pairs = added(before_edges, after_edges)
    removed_edge_pairs = removed(before_edges, after_edges)
    changed_edge_pairs = changed(before_edges, after_edges)
    process_delta = {
        "added_node_ids": added(before_nodes, after_nodes),
        "removed_node_ids": removed(before_nodes, after_nodes),
        "changed_node_ids": changed(before_nodes, after_nodes),
        "added_edges": [
            {"source": source, "target": target}
            for source, target in added_edge_pairs
        ],
        "removed_edges": [
            {"source": source, "target": target}
            for source, target in removed_edge_pairs
        ],
        "changed_edges": [
            {"source": source, "target": target}
            for source, target in changed_edge_pairs
        ],
        "changed_root_keys": root_changes(
            before_process, after_process, {"nodes", "edges"}
        ),
    }
    evidence_delta = {
        "added_item_ids": added(before_items, after_items),
        "removed_item_ids": removed(before_items, after_items),
        "changed_item_ids": changed(before_items, after_items),
        "changed_root_keys": root_changes(
            before_checklist, after_checklist, {"items"}
        ),
    }
    return {
        "nonzero": any(
            process_delta[key]
            for key in (
                "added_node_ids",
                "removed_node_ids",
                "changed_node_ids",
                "added_edges",
                "removed_edges",
                "changed_edges",
            )
        )
        or any(
            evidence_delta[key]
            for key in ("added_item_ids", "removed_item_ids", "changed_item_ids")
        ),
        "process": process_delta,
        "evidence": evidence_delta,
    }


def _verify_learning_replay_contract(
    *,
    demo_review: Mapping[str, Any],
    post_review_run: Mapping[str, Any],
    baseline_run: Mapping[str, Any],
    later_run: Mapping[str, Any],
    proof: Mapping[str, Any],
) -> None:
    if (
        baseline_run.get("status") != "complete"
        or later_run.get("status") != "complete"
        or baseline_run.get("claim_id") != "DEMO-MOULD-002"
        or later_run.get("claim_id") != "DEMO-MOULD-002"
        or baseline_run.get("knowledge_mode") != "baseline"
        or later_run.get("knowledge_mode") != "current"
        or baseline_run.get("run_id") == later_run.get("run_id")
    ):
        _causal_failure("learning.runs")
    freeze = _causal_mapping(
        baseline_run.get("counterfactual_learning_freeze"),
        "learning.baseline.counterfactual_learning_freeze",
    )
    proof_freeze = _causal_mapping(
        proof.get("counterfactual_learning_freeze"),
        "learning.proof.counterfactual_learning_freeze",
    )
    baseline = _causal_mapping(
        baseline_run.get("result"), "learning.baseline.result"
    )
    later = _causal_mapping(later_run.get("result"), "learning.later.result")
    receipt = _causal_mapping(
        later.get("memory_application"), "learning.later.memory_application"
    )
    receipt_fields = {
        "receipt_type",
        "contract",
        "authority",
        "scope",
        "source_memory",
        "target",
        "observable_input_hash",
        "canonical_state_hash",
        "eligibility",
        "allowed_operation_ids",
        "applied_operation_ids",
        "process_operations",
        "evidence_operations",
        "before",
        "after",
        "verification_hash",
        "shared_playbook_version",
        "shared_rule_applied",
        "model_acceptance_reused",
        "applied",
        "application_hash",
    }
    if (
        set(receipt) != receipt_fields
        or receipt.get("receipt_type") != "memory_application_receipt"
        or receipt.get("contract")
        != "casepath.memory-application-receipt/1.0.0"
        or receipt.get("authority") != "unverified_demo"
        or receipt.get("scope") != "case_specific_guidance_only"
        or receipt.get("shared_playbook_version") != "mould-playbook-v3"
        or receipt.get("shared_rule_applied") is not False
        or receipt.get("model_acceptance_reused") is not False
        or receipt.get("applied") is not True
    ):
        _causal_failure("learning.later.memory_application")
    source_memory = _causal_mapping(
        receipt.get("source_memory"), "learning.later.memory_application.source_memory"
    )
    freeze_memory = _causal_mapping(
        freeze.get("memory"),
        "learning.baseline.counterfactual_learning_freeze.memory",
    )
    reviewer = _causal_mapping(
        demo_review.get("reviewer"), "learning.demo_review.reviewer"
    )
    reviewed_result = _causal_mapping(
        demo_review.get("result"), "learning.demo_review.result"
    )
    review_record = _causal_mapping(
        demo_review.get("review"), "learning.demo_review.review"
    )
    response_guidance = _causal_mapping(
        reviewed_result.get("review"), "learning.demo_review.result.review"
    )
    review_transform = _causal_mapping(
        reviewed_result.get("review_transform"),
        "learning.demo_review.result.review_transform",
    )
    if (
        set(source_memory)
        != {"memory_id", "claim_id", "review_id", "content_hash", "review_status"}
        or source_memory.get("claim_id") != "DEF-027-E0-DEMO"
        or source_memory.get("review_status") != "unverified_demo_memory"
        or not re.fullmatch(r"[0-9a-f]{64}", str(source_memory.get("content_hash", "")))
        or demo_review.get("accepted") is not True
        or demo_review.get("memory_id") != source_memory.get("memory_id")
        or demo_review.get("review_id") != source_memory.get("review_id")
        or demo_review.get("accepted") is not True
        or post_review_run.get("run_id") != review_transform.get("input_run_id")
        or post_review_run.get("claim_id") != source_memory.get("claim_id")
        or post_review_run.get("memory_id") != source_memory.get("memory_id")
        or post_review_run.get("review_id") != source_memory.get("review_id")
        or post_review_run.get("review_response") != demo_review
        or post_review_run.get("result") != reviewed_result
        or post_review_run.get("candidate") != demo_review.get("candidate")
        or demo_review.get("review") != review_record
        or demo_review.get("review_transform") != review_transform
        or set(review_record)
        != {
            "decision",
            "building_envelope_mode",
            "confidence",
            "justification",
            "reviewer",
            "operations",
            "authority",
        }
        or review_record.get("decision") != "approve_with_edit"
        or review_record.get("building_envelope_mode") != "conditional"
        or not isinstance(review_record.get("confidence"), (int, float))
        or isinstance(review_record.get("confidence"), bool)
        or not isinstance(review_record.get("justification"), str)
        or not review_record.get("justification", "").strip()
        or not isinstance(review_record.get("operations"), list)
        or not review_record.get("operations")
        or review_record.get("reviewer") != reviewer
        or review_record.get("authority") != "unverified_demo"
        or response_guidance != review_record
        or set(review_transform)
        != {
            "acceptance_scope",
            "authority",
            "qualification_status",
            "input_run_id",
            "input_process_hash",
            "input_checklist_hash",
            "output_process_hash",
            "output_checklist_hash",
            "model_acceptance_reused",
        }
        or review_transform.get("acceptance_scope")
        != "post_review_unverified_transform"
        or review_transform.get("authority") != reviewer.get("type")
        or review_transform.get("qualification_status")
        != reviewer.get("qualification_status")
        or review_transform.get("output_process_hash")
        != runtime_artifact_hash(reviewed_result.get("process"))
        or review_transform.get("output_checklist_hash")
        != runtime_artifact_hash(reviewed_result.get("checklist"))
        or review_transform.get("model_acceptance_reused") is not False
    ):
        _causal_failure("learning.source_memory")
    if (
        set(freeze)
        != {
            "contract",
            "memory",
            "identity_hash",
            "application_suppressed",
        }
        or freeze.get("contract")
        != "casepath.counterfactual-learning-freeze/1.0.0"
        or freeze.get("application_suppressed") is not True
        or proof_freeze != freeze
        or set(freeze_memory)
        != {
            "memory_id",
            "review_id",
            "content_hash",
            "candidate_id",
            "updated_at",
        }
        or freeze_memory.get("memory_id") != source_memory.get("memory_id")
        or freeze_memory.get("review_id") != source_memory.get("review_id")
        or freeze_memory.get("content_hash") != source_memory.get("content_hash")
        or freeze_memory.get("candidate_id")
        != demo_review.get("candidate", {}).get("candidate_id")
        or not _is_historical_timestamp(freeze_memory.get("updated_at"))
        or freeze.get("identity_hash") != runtime_artifact_hash(freeze_memory)
    ):
        _causal_failure("learning.counterfactual_learning_freeze")
    try:
        freeze_time = datetime.fromisoformat(
            str(freeze_memory["updated_at"]).replace("Z", "+00:00")
        ).timestamp()
        baseline_created = datetime.fromisoformat(
            str(baseline_run["created_at"]).replace("Z", "+00:00")
        ).timestamp()
        baseline_completed = float(baseline_run["completed_at"])
        later_created = datetime.fromisoformat(
            str(later_run["created_at"]).replace("Z", "+00:00")
        ).timestamp()
    except (KeyError, TypeError, ValueError):
        _causal_failure("learning.counterfactual_temporal_order")
    if not (
        freeze_time
        <= baseline_created
        <= baseline_completed
        <= later_created
    ):
        _causal_failure("learning.counterfactual_temporal_order")
    if (
        reviewer.get("type") != "unverified_demo_user"
        or reviewer.get("qualification_status") != "not_verified"
    ):
        _causal_failure("learning.demo_review.reviewer")
    consolidation_events = [
        event
        for event in post_review_run.get("events", [])
        if isinstance(event, Mapping)
        and event.get("receipt_type") == "knowledge_consolidation_receipt"
    ]
    if (
        len(consolidation_events) != 1
        or consolidation_events[0].get("memory_id") != source_memory.get("memory_id")
        or consolidation_events[0].get("memory_content_hash")
        != source_memory.get("content_hash")
        or consolidation_events[0].get("qualified_reviewer") is not False
        or consolidation_events[0].get("shared_knowledge_changed") is not False
    ):
        _causal_failure("learning.post_review_run.events")

    target = _causal_mapping(receipt.get("target"), "learning.receipt.target")
    baseline_audit = _causal_mapping(
        baseline.get("audit"), "learning.baseline.result.audit"
    )
    later_audit = _causal_mapping(later.get("audit"), "learning.later.result.audit")
    baseline_facts = _causal_list(baseline.get("facts"), "learning.baseline.facts")
    later_facts = _causal_list(later.get("facts"), "learning.later.facts")
    baseline_signature = _semantic_fact_signature(
        baseline_facts, "learning.baseline.facts"
    )
    later_signature = _semantic_fact_signature(later_facts, "learning.later.facts")
    canonical_hash = receipt.get("canonical_state_hash")
    before_proof = _causal_mapping(proof.get("before"), "learning.proof.before")
    after_proof = _causal_mapping(proof.get("after"), "learning.proof.after")
    if (
        set(target) != {"run_id", "claim_id"}
        or target.get("run_id") != later_run.get("run_id")
        or target.get("claim_id") != later_run.get("claim_id")
        or receipt.get("observable_input_hash")
        != baseline_audit.get("observable_input_hash")
        or receipt.get("observable_input_hash")
        != later_audit.get("observable_input_hash")
        or receipt.get("observable_input_hash")
        != before_proof.get("observable_input_hash")
        or receipt.get("observable_input_hash")
        != after_proof.get("observable_input_hash")
        or receipt.get("canonical_state_hash") != canonical_hash
        or receipt.get("canonical_state_hash")
        != baseline_audit.get("canonical_state_hash")
        or receipt.get("canonical_state_hash")
        != later_audit.get("canonical_state_hash")
        or receipt.get("canonical_state_hash")
        != before_proof.get("canonical_state_hash")
        or receipt.get("canonical_state_hash")
        != after_proof.get("canonical_state_hash")
        or not re.fullmatch(r"[0-9a-f]{64}", str(canonical_hash or ""))
        or _runtime_canonical_facts_hash(
            baseline_facts, "learning.baseline.facts"
        )
        != canonical_hash
        or _runtime_canonical_facts_hash(later_facts, "learning.later.facts")
        != canonical_hash
        or baseline_facts != later_facts
        or baseline_signature != later_signature
    ):
        _causal_failure("learning.input_and_canonical_binding")

    decisions = {
        fact.get("decision_key"): fact.get("decision_value")
        for fact in later_facts
        if isinstance(fact, Mapping) and fact.get("controls_process") is True
    }
    semantic_signature_hash = runtime_artifact_hash(
        {
            "category": "Rental defect - mould and moisture",
            "subcategory": "Recurring moisture with disputed causation",
            "required_decisions": MEMORY_REQUIRED_DECISIONS,
            "required_fact_roles": MEMORY_REQUIRED_FACT_ROLES,
        }
    )
    eligibility = _causal_mapping(
        receipt.get("eligibility"), "learning.receipt.eligibility"
    )
    eligibility_checks = {
        "source_claim_excluded": source_memory.get("claim_id")
        != later_run.get("claim_id"),
        "category_matched": later.get("category")
        == "Rental defect - mould and moisture",
        "subcategory_matched": later.get("subcategory")
        == "Recurring moisture with disputed causation",
        "required_decisions_matched": decisions == MEMORY_REQUIRED_DECISIONS,
        "ventilation_allegation_grounded": (
            later_signature[SEMANTIC_MEMORY_ROLE].get("state") == "known"
            and later_signature[SEMANTIC_MEMORY_ROLE].get("grounded_source_count", 0)
            >= 1
        ),
        "semantic_signature_bound": eligibility.get("semantic_signature_hash")
        == semantic_signature_hash,
        "guidance_enabled": True,
    }
    eligibility_manifest = {
        "rule_id": eligibility.get("rule_id"),
        "contract": eligibility.get("contract"),
        "claim_id": eligibility.get("claim_id"),
        "semantic_signature_hash": eligibility.get("semantic_signature_hash"),
        "decisions": eligibility.get("decisions"),
        "facts_hash": eligibility.get("facts_hash"),
        "checks": eligibility.get("checks"),
    }
    if (
        set(eligibility)
        != {
            "rule_id",
            "contract",
            "claim_id",
            "semantic_signature_hash",
            "decisions",
            "facts_hash",
            "checks",
            "eligible",
            "manifest_hash",
        }
        or eligibility.get("rule_id") != "same_grounded_mould_signature_v2"
        or eligibility.get("contract")
        != "casepath.semantic-memory-eligibility/1.0.0"
        or eligibility.get("claim_id") != later_run.get("claim_id")
        or eligibility.get("semantic_signature_hash") != semantic_signature_hash
        or eligibility.get("decisions") != MEMORY_REQUIRED_DECISIONS
        or eligibility.get("facts_hash") != runtime_artifact_hash(later_signature)
        or eligibility.get("checks") != eligibility_checks
        or eligibility.get("eligible") is not True
        or eligibility.get("manifest_hash")
        != runtime_artifact_hash(eligibility_manifest)
    ):
        _causal_failure("learning.receipt.eligibility")

    baseline_process = _causal_mapping(
        baseline.get("process"), "learning.baseline.process"
    )
    baseline_checklist = _causal_mapping(
        baseline.get("checklist"), "learning.baseline.checklist"
    )
    later_process = _causal_mapping(later.get("process"), "learning.later.process")
    later_checklist = _causal_mapping(
        later.get("checklist"), "learning.later.checklist"
    )
    _verify_reciprocal_evidence_contract(
        baseline_process,
        baseline_checklist,
        claim_id="DEMO-MOULD-002",
        path="learning.baseline",
    )
    _verify_reciprocal_evidence_contract(
        later_process,
        later_checklist,
        claim_id="DEMO-MOULD-002",
        include_memory_extension=True,
        path="learning.later",
    )
    _verify_release_fact_relationships(
        claim_id="DEMO-MOULD-002",
        facts=baseline_facts,
        process=baseline_process,
        checklist=baseline_checklist,
        include_memory_extension=False,
        path="learning.baseline",
    )
    _verify_release_fact_relationships(
        claim_id="DEMO-MOULD-002",
        facts=later_facts,
        process=later_process,
        checklist=later_checklist,
        include_memory_extension=True,
        path="learning.later",
    )
    semantic_before_process = _semantic_process_dto(baseline_process)
    semantic_before_checklist = _semantic_checklist_dto(baseline_checklist)
    semantic_after_process = _semantic_process_dto(later_process)
    semantic_after_checklist = _semantic_checklist_dto(later_checklist)
    boundaries = {"process_dto_hash", "checklist_dto_hash", "process_semantic_hash", "checklist_semantic_hash"}
    proof_boundary_fields = LEARNING_SNAPSHOT_FIELDS
    receipt_before = _causal_mapping(receipt.get("before"), "learning.receipt.before")
    receipt_after = _causal_mapping(receipt.get("after"), "learning.receipt.after")
    exact_baseline = {
        "process_dto_hash": runtime_artifact_hash(baseline_process),
        "checklist_dto_hash": runtime_artifact_hash(baseline_checklist),
        "process_semantic_hash": runtime_artifact_hash(semantic_before_process),
        "checklist_semantic_hash": runtime_artifact_hash(semantic_before_checklist),
    }
    expected_receipt_before_semantics = {
        "process_semantic_hash": exact_baseline["process_semantic_hash"],
        "checklist_semantic_hash": exact_baseline["checklist_semantic_hash"],
    }
    exact_after = {
        "process_dto_hash": runtime_artifact_hash(later_process),
        "checklist_dto_hash": runtime_artifact_hash(later_checklist),
        "process_semantic_hash": runtime_artifact_hash(semantic_after_process),
        "checklist_semantic_hash": runtime_artifact_hash(semantic_after_checklist),
    }
    boundary = _causal_mapping(
        later_run.get("memory_application_boundary"),
        "learning.later.memory_application_boundary",
    )
    boundary_source = _causal_mapping(
        boundary.get("source_memory"),
        "learning.later.memory_application_boundary.source_memory",
    )
    boundary_before = _causal_mapping(
        boundary.get("before"),
        "learning.later.memory_application_boundary.before",
    )
    boundary_without_hash = {
        key: value for key, value in boundary.items() if key != "boundary_hash"
    }
    if (
        set(boundary)
        != {"contract", "target", "source_memory", "before", "boundary_hash"}
        or boundary.get("contract") != MEMORY_BOUNDARY_CONTRACT
        or boundary.get("target") != receipt.get("target")
        or boundary_source
        != {
            "memory_id": source_memory.get("memory_id"),
            "content_hash": source_memory.get("content_hash"),
        }
        or boundary_before != receipt_before
        or set(receipt_before) != boundaries
        or any(
            not re.fullmatch(r"[0-9a-f]{64}", str(value))
            for value in receipt_before.values()
        )
        or any(
            receipt_before.get(key) != value
            for key, value in expected_receipt_before_semantics.items()
        )
        or boundary.get("boundary_hash")
        != runtime_artifact_hash(boundary_without_hash)
    ):
        _causal_failure("learning.later.memory_application_boundary")
    later_events = _causal_list(later_run.get("events"), "learning.later.events")
    memory_events = [
        event
        for event in later_events
        if isinstance(event, Mapping)
        and event.get("stage") == "memory_application"
        and event.get("receipt_type") == "memory_application_receipt"
        and event.get("status") == "completed"
    ]
    if len(memory_events) != 1:
        _causal_failure("learning.later.memory_application_event")
    event = memory_events[0]
    if any(key not in event for key in receipt):
        _causal_failure("learning.later.memory_application_event")
    event_receipt = {key: deepcopy(event[key]) for key in receipt}
    if event_receipt != receipt or event_receipt.get("before") != boundary_before:
        _causal_failure("learning.later.memory_application_event")
    _verify_learning_snapshot_projection(
        before_proof,
        baseline_run,
        baseline,
        "learning.proof.before",
    )
    _verify_learning_snapshot_projection(
        after_proof,
        later_run,
        later,
        "learning.proof.after",
    )
    if (
        set(before_proof) != proof_boundary_fields
        or set(after_proof) != proof_boundary_fields
        or set(receipt_after) != boundaries
        or receipt_after != exact_after
        or any(receipt_before.get(key) == receipt_after.get(key) for key in boundaries)
        or any(before_proof.get(key) != value for key, value in exact_baseline.items())
        or any(after_proof.get(key) != value for key, value in exact_after.items())
        or before_proof.get("verification_hash")
        != baseline.get("verification", {}).get("whole_playbook_hash")
    ):
        _causal_failure("learning.receipt.boundaries")

    replay_process = deepcopy(semantic_before_process)
    replay_checklist = deepcopy(semantic_before_checklist)
    replay = _replay_memory_transform(
        replay_process,
        replay_checklist,
        str(later_signature[SEMANTIC_MEMORY_ROLE]["fact_id"]),
    )
    if replay_process != semantic_after_process or replay_checklist != semantic_after_checklist:
        _causal_failure("learning.pure_replay")

    process_operations = _causal_list(
        receipt.get("process_operations"), "learning.receipt.process_operations"
    )
    evidence_operations = _causal_list(
        receipt.get("evidence_operations"), "learning.receipt.evidence_operations"
    )
    if (
        receipt.get("allowed_operation_ids") != list(MEMORY_OPERATION_IDS)
        or receipt.get("applied_operation_ids") != list(MEMORY_OPERATION_IDS)
        or [
            operation.get("operation_id")
            for operation in [*process_operations, *evidence_operations]
            if isinstance(operation, Mapping)
        ]
        != list(MEMORY_OPERATION_IDS)
        or len(process_operations) != 3
        or len(evidence_operations) != 2
    ):
        _causal_failure("learning.receipt.operations")
    expected_operation_fields = (
        {"operation_id", "operation", "node_id", "evidence_requirement_ids", "after_hash"},
        {"operation_id", "operation", "source", "target", "after_hash"},
        {"operation_id", "operation", "source", "target", "after_hash"},
        {"operation_id", "operation", "item_id", "before_hash", "after_hash"},
        {
            "operation_id",
            "operation",
            "item_id",
            "removed_from_node_ids",
            "added_to_node_id",
            "before_hash",
            "after_hash",
        },
    )
    operations = [*process_operations, *evidence_operations]
    if any(
        not isinstance(operation, Mapping)
        or set(operation) != expected_operation_fields[index]
        for index, operation in enumerate(operations)
    ):
        _causal_failure("learning.receipt.operations")
    if (
        process_operations[0].get("operation") != "add_node"
        or process_operations[0].get("node_id") != "ventilation_dispute"
        or process_operations[0].get("evidence_requirement_ids")
        != ["management_position", "use_evidence"]
        or process_operations[0].get("after_hash")
        != runtime_artifact_hash(replay["ventilation_node"])
        or any(operation.get("operation") != "add_edge" for operation in process_operations[1:])
        or process_operations[1].get("after_hash")
        != runtime_artifact_hash(replay["first_edge"])
        or process_operations[2].get("after_hash")
        != runtime_artifact_hash(replay["second_edge"])
        or evidence_operations[0].get("operation") != "replace_item"
        or evidence_operations[0].get("item_id") != "building_envelope"
        or evidence_operations[0].get("after_hash")
        != runtime_artifact_hash(replay["building_envelope"])
        or evidence_operations[1].get("operation") != "reassign_item"
        or evidence_operations[1].get("item_id") != "use_evidence"
        or evidence_operations[1].get("removed_from_node_ids")
        != sorted(replay["removed_from"])
        or evidence_operations[1].get("added_to_node_id") != "ventilation_dispute"
        or evidence_operations[1].get("after_hash")
        != runtime_artifact_hash(replay["use_evidence"])
    ):
        _causal_failure("learning.receipt.operations")
    receipt_without_hash = {
        key: value for key, value in receipt.items() if key != "application_hash"
    }
    if receipt.get("application_hash") != runtime_artifact_hash(receipt_without_hash):
        _causal_failure("learning.receipt.application_hash")
    verification = _causal_mapping(
        later.get("verification"), "learning.later.verification"
    )
    if (
        receipt.get("verification_hash") != verification.get("whole_playbook_hash")
        or receipt.get("verification_hash") != after_proof.get("verification_hash")
    ):
        _causal_failure("learning.receipt.verification_hash")

    causal_delta = _keyed_dto_delta(baseline, later)
    if (
        proof.get("causal_delta") != causal_delta
        or causal_delta.get("process", {}).get("added_node_ids")
        != ["ventilation_dispute"]
        or causal_delta.get("process", {}).get("added_edges")
        != [
            {"source": "evidence_gap", "target": "ventilation_dispute"},
            {"source": "ventilation_dispute", "target": "causation"},
        ]
        or causal_delta.get("evidence", {}).get("changed_item_ids")
        != ["building_envelope", "management_position", "use_evidence"]
    ):
        _causal_failure("learning.proof.causal_delta")
    deterministic_checks = _causal_list(
        proof.get("deterministic_checks"), "learning.proof.deterministic_checks"
    )
    if (
        proof.get("ready") is not True
        or proof.get("computed") is not True
        or proof.get("baseline_run_id") != baseline_run.get("run_id")
        or proof.get("later_run_id") != later_run.get("run_id")
        or [
            check.get("name") if isinstance(check, Mapping) else None
            for check in deterministic_checks
        ]
        != list(REQUIRED_LEARNING_CHECKS)
        or any(
            not isinstance(check, Mapping) or check.get("status") != "passed"
            for check in deterministic_checks
        )
    ):
        _causal_failure("learning.proof.deterministic_checks")
    receipt_proof = _causal_mapping(
        proof.get("memory_application_proof"),
        "learning.proof.memory_application_proof",
    )
    proof_flags = {
        "receipt_present",
        "receipt_valid",
        "source_memory_current",
        "before_hashes_match",
        "after_hashes_match",
        "allowed_delta_exact",
        "replay_exact",
    }
    if (
        set(receipt_proof) != {*proof_flags, "application_hash"}
        or any(receipt_proof.get(key) is not True for key in proof_flags)
        or receipt_proof.get("application_hash") != receipt.get("application_hash")
    ):
        _causal_failure("learning.proof.memory_application_proof")
    reviewed_memory = _causal_mapping(
        proof.get("reviewed_memory_proof"), "learning.proof.reviewed_memory_proof"
    )
    candidate = _causal_mapping(proof.get("candidate"), "learning.proof.candidate")
    shared_rule = _causal_mapping(
        proof.get("shared_rule"), "learning.proof.shared_rule"
    )
    if (
        reviewed_memory.get("used") is not True
        or reviewed_memory.get("present_in_baseline") is not False
        or reviewed_memory.get("present_in_later_run") is not True
        or source_memory.get("memory_id") not in reviewed_memory.get("memory_ids", [])
        or proof.get("changes", {}).get("precedent_claim_ids_added")
        != ["DEF-027-E0-DEMO"]
        or candidate.get("status") != "quarantined"
        or candidate.get("target_tests", {}).get("status") != "passed"
        or candidate.get("protected_regression", {}).get("status") != "passed"
        or candidate.get("qualified_support_count") != 0
        or candidate.get("approval")
        != {"status": "pending", "qualified_reviewer": False}
        or later.get("playbook", {}).get("version") != "mould-playbook-v3"
        or later.get("shared_rule_applied") is not False
        or shared_rule.get("applied") is not False
        or shared_rule.get("version_before") != "mould-playbook-v3"
        or shared_rule.get("version_after") != "mould-playbook-v3"
        or shared_rule.get("shared_knowledge_changed") is not False
    ):
        _causal_failure("learning.proof.governance")
    if (
        "agent_contribution" in later_process
        or any(
            isinstance(node, Mapping) and "agent_decision_contributions" in node
            for node in later_process.get("nodes", [])
        )
        or "agent_contribution" in later_checklist
        or any(
            isinstance(item, Mapping) and "agent_contribution" in item
            for item in later_checklist.get("items", [])
        )
        or later.get("next_action", {}).get("agent_brief_contribution") is not None
    ):
        _causal_failure("learning.later.model_attribution")


def _accepted_lineage(agent: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: agent[field]
        for field in ACCEPTED_LINEAGE_FIELDS
        if field in agent
    }


def _verify_unit_accounting(
    agent: Mapping[str, Any],
    accepted_ids: list[str],
    rejected_count: int,
    path: str,
) -> None:
    if (
        agent.get("accepted_ids") != accepted_ids
        or agent.get("accepted_count") != len(accepted_ids)
        or agent.get("rejected_count") != rejected_count
        or agent.get("deterministic_fallback_applied") is not bool(rejected_count)
    ):
        _causal_failure(path)


def _canonical_assertion_id(fact: Mapping[str, Any], path: str) -> str:
    """Mirror canonicalizer._assertion_id under the canonical-facts 1.6 contract."""

    fact_id = fact.get("fact_id")
    state = fact.get("state")
    value = fact.get("value")
    normalized_value = fact.get("normalized_value")
    if (
        not isinstance(fact_id, str)
        or not fact_id
        or not isinstance(state, str)
        or not state
        or not isinstance(value, str)
        or normalized_value is not None
        and not isinstance(normalized_value, str)
    ):
        _causal_failure(path)
    material = {
        "fact_id": fact_id,
        "state": state,
        "value": value,
        "normalized_value": normalized_value,
    }
    encoded = json.dumps(
        material,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"assert_{hashlib.sha256(encoded).hexdigest()[:24]}"


def _verify_assertion_selection_receipts(
    result: Mapping[str, Any],
    canonical_agent: Mapping[str, Any],
) -> None:
    path = "result.audit.canonicalization"
    result_audit = _causal_mapping(result.get("audit"), "result.audit")
    canonicalization = _causal_mapping(
        result_audit.get("canonicalization"), path
    )
    diagnostics = _causal_mapping(
        canonicalization.get("diagnostics"), f"{path}.diagnostics"
    )
    facts = _causal_list(result.get("facts"), "result.facts")
    facts_by_id: dict[str, Mapping[str, Any]] = {}
    for index, raw_fact in enumerate(facts):
        fact = _causal_mapping(raw_fact, f"result.facts[{index}]")
        fact_id = fact.get("fact_id")
        if (
            not isinstance(fact_id, str)
            or not fact_id
            or fact_id in facts_by_id
        ):
            _causal_failure(f"result.facts[{index}].fact_id")
        facts_by_id[fact_id] = fact

    accepted_ids = _causal_text_list(
        diagnostics.get("accepted_fact_ids"),
        f"{path}.diagnostics.accepted_fact_ids",
    )
    rejected_values = _causal_list(
        diagnostics.get("rejected_facts"),
        f"{path}.diagnostics.rejected_facts",
    )
    rejected_ids: list[str] = []
    for index, raw_rejection in enumerate(rejected_values):
        rejection_path = f"{path}.diagnostics.rejected_facts[{index}]"
        rejection = _causal_mapping(raw_rejection, rejection_path)
        fact_id = rejection.get("fact_id")
        if (
            set(rejection) != {"fact_id", "invariant"}
            or not isinstance(fact_id, str)
            or not fact_id
            or fact_id in rejected_ids
            or not isinstance(rejection.get("invariant"), str)
            or not rejection["invariant"]
        ):
            _causal_failure(rejection_path)
        rejected_ids.append(fact_id)
    if (
        set(accepted_ids) & set(rejected_ids)
        or set(accepted_ids) | set(rejected_ids) != set(facts_by_id)
        or diagnostics.get("accepted_fact_count") != len(accepted_ids)
        or diagnostics.get("rejected_fact_count") != len(rejected_ids)
        or diagnostics.get("deterministic_fallback_applied")
        is not bool(rejected_ids)
        or canonical_agent.get("accepted_ids") != accepted_ids
        or canonical_agent.get("accepted_count") != len(accepted_ids)
        or canonical_agent.get("rejected_count") != len(rejected_ids)
        or canonical_agent.get("deterministic_fallback_applied")
        is not bool(rejected_ids)
    ):
        _causal_failure(f"{path}.diagnostics.fact_membership")

    selections = _causal_list(
        canonicalization.get("assertion_selections"),
        f"{path}.assertion_selections",
    )
    exact_fields = {
        "fact_id",
        "assertion_id",
        "model_owned_fields",
        "materialized_fields",
        "attribution",
        "deterministic_fallback_applied",
    }
    by_fact: dict[str, Mapping[str, Any]] = {}
    for index, raw_selection in enumerate(selections):
        selection_path = f"{path}.assertion_selections[{index}]"
        selection = _causal_mapping(raw_selection, selection_path)
        fact_id = selection.get("fact_id")
        if (
            set(selection) != exact_fields
            or not isinstance(fact_id, str)
            or fact_id not in facts_by_id
            or fact_id in by_fact
        ):
            _causal_failure(selection_path)
        by_fact[fact_id] = selection
    if len(selections) != len(facts) or set(by_fact) != set(facts_by_id):
        _causal_failure(f"{path}.assertion_selections.fact_membership")

    accepted = set(accepted_ids)
    for fact_id, fact in facts_by_id.items():
        selection = by_fact[fact_id]
        selection_path = f"{path}.assertion_selections[{fact_id}]"
        expected_model_fields = (
            ["assertion_id", "source_ref_ids", "confidence"]
            if fact.get("controls_process") is True
            else ["source_ref_ids", "confidence"]
        )
        is_accepted = fact_id in accepted
        if (
            selection.get("assertion_id")
            != _canonical_assertion_id(fact, f"{selection_path}.assertion_id")
            or selection.get("model_owned_fields") != expected_model_fields
            or selection.get("materialized_fields")
            != CANONICAL_ASSERTION_MATERIALIZED_FIELDS
            or any(field not in fact for field in CANONICAL_ASSERTION_MATERIALIZED_FIELDS)
            or selection.get("attribution")
            != (
                "OpenRouter Nemotron Canonicalizer"
                if is_accepted
                else "deterministic_application"
            )
            or selection.get("deterministic_fallback_applied")
            is not (not is_accepted)
        ):
            _causal_failure(selection_path)


def _compatible_release_process_decisions(
    fact: Mapping[str, Any], path: str
) -> tuple[str, set[str]]:
    decision_key = fact.get("decision_key")
    normalized_value = fact.get("normalized_value")
    try:
        exact = RELEASE_DECISION_OPTIONS[decision_key][normalized_value]
        conservative = RELEASE_CONSERVATIVE_DECISIONS[decision_key]
    except (KeyError, TypeError):
        _causal_failure(path)
    return exact, {exact, conservative}


def _verify_accepted_process_projection(
    process: Mapping[str, Any],
    decisions: list[Mapping[str, Any]],
) -> None:
    path = "result.process"
    projection_facts = [
        {
            "controls_process": True,
            "decision_key": item["decision_key"],
            "decision_value": item["decision_value"],
        }
        for item in decisions
    ]
    try:
        projection = decision_projection(projection_facts)
        expected_nodes = deepcopy(_causal_list(process.get("nodes"), f"{path}.nodes"))
        expected_edges = deepcopy(_causal_list(process.get("edges"), f"{path}.edges"))
        expected_overlay = apply_process_projection(
            expected_nodes,
            expected_edges,
            projection,
            list(_causal_list(process.get("main_spine"), f"{path}.main_spine")),
        )
    except (KeyError, TypeError, ValueError):
        _causal_failure(f"{path}.accepted_decision_projection")
    if (
        process.get("current_node") != projection["current_node"]
        or process.get("selected_path") != projection["selected_path"]
        or process.get("current_overlay") != expected_overlay
        or process.get("nodes") != expected_nodes
        or process.get("edges") != expected_edges
    ):
        _causal_failure(f"{path}.accepted_decision_projection")


def _release_artifact_capabilities(artifact: Mapping[str, Any]) -> set[str]:
    """Mirror the reusable backend capability resolver without claim-ID oracles."""

    artifact_id = str(artifact.get("artifact_id", "")).casefold()
    filename = str(artifact.get("filename", "")).casefold()
    media_type = str(artifact.get("media_type", "")).casefold()
    text = f"{artifact_id} {filename}"
    capabilities = {"submitted_source"}
    if artifact_id == "message":
        capabilities.update(
            {"claim_message", "customer_correspondence", "correspondence"}
        )
    if artifact_id == "intake":
        capabilities.add("policy_reference")
    if media_type.startswith("image/") or any(
        word in text for word in ("photo", "image", "photograph")
    ):
        capabilities.add("photo")
    if any(
        word in text for word in ("lease", "tenancy", "rental_agreement", "contract")
    ):
        capabilities.add("lease")
    if any(word in text for word in ("delivery", "receipt", "registered_mail")):
        capabilities.add("delivery_proof")
    if any(word in text for word in ("timeline", "chronology")):
        capabilities.add("timeline")
    if any(word in text for word in ("notification", "notice", "reported_defect")):
        capabilities.update(
            {"defect_notice", "customer_correspondence", "correspondence"}
        )
    if any(
        word in text
        for word in ("management_reply", "landlord_reply", "property_manager")
    ):
        capabilities.update({"management_correspondence", "correspondence"})
    if any(
        word in text for word in ("inspection", "technical", "expert", "building_physics")
    ):
        capabilities.update({"technical_report", "inspection_report"})
    if any(
        word in text for word in ("moisture", "humidity", "temperature", "measurement")
    ):
        capabilities.add("measurement_report")
    if any(
        word in text for word in ("envelope", "facade", "window_seal", "thermal_bridge")
    ):
        capabilities.add("building_report")
    if any(
        word in text for word in ("maintenance", "repair", "work_order", "contractor")
    ):
        capabilities.add("maintenance_record")
    if any(
        word in text for word in ("ventilation_log", "heating", "occupancy", "use_log")
    ):
        capabilities.add("use_log")
    if any(word in text for word in ("utility", "energy_bill")):
        capabilities.add("utility_record")
    if any(word in text for word in ("remediation_plan", "scope_of_work")):
        capabilities.add("remediation_plan")
    if any(word in text for word in ("invoice", "rent_record", "financial", "loss")):
        capabilities.update({"invoice", "financial_record"})
    if any(word in text for word in ("settlement", "mediation", "proposal")):
        capabilities.add("settlement_record")
    if any(word in text for word in ("conciliation", "court", "filing")):
        capabilities.add("legal_filing")
    if any(word in text for word in ("completion", "closure", "completed")):
        capabilities.add("completion_record")
    if any(word in text for word in ("medical", "doctor", "health_report")):
        capabilities.add("medical")
    return capabilities


def _release_evidence_candidates(claim_id: str) -> dict[str, list[str]]:
    claim = CASEPATH_CLAIMS.get(claim_id)
    if not isinstance(claim, Mapping):
        _causal_failure("result.claim_id")
    package = observable_claim_package(claim)
    inventory: list[Mapping[str, Any]] = [
        {
            "artifact_id": "message",
            "filename": "Claim message",
            "media_type": "text/plain",
        },
        {
            "artifact_id": "intake",
            "filename": "Claim intake",
            "media_type": "application/casepath-intake+json",
        },
        *_causal_list(package.get("artifacts"), "result.observable_package.artifacts"),
    ]
    by_id: dict[str, set[str]] = {}
    for index, raw_artifact in enumerate(inventory):
        path = f"result.observable_package.artifacts[{index}]"
        artifact = _causal_mapping(raw_artifact, path)
        artifact_id = artifact.get("artifact_id")
        if (
            not isinstance(artifact_id, str)
            or not artifact_id
            or artifact_id in by_id
            or not isinstance(artifact.get("filename"), str)
            or not artifact["filename"]
            or not isinstance(artifact.get("media_type"), str)
            or not artifact["media_type"]
        ):
            _causal_failure(path)
        by_id[artifact_id] = _release_artifact_capabilities(artifact)

    candidates: dict[str, list[str]] = {}
    synthetic_allowed = {
        "claim_message",
        "policy_reference",
        "customer_objective",
        "health_safety_statement",
        "defect_notice",
    }
    for item_id, required_capabilities in RELEASE_EVIDENCE_ARTIFACT_CAPABILITIES.items():
        candidates[item_id] = sorted(
            artifact_id
            for artifact_id, capabilities in by_id.items()
            if required_capabilities & capabilities
            and (
                item_id == "source_integrity"
                and artifact_id not in {"message", "intake"}
                or artifact_id not in {"message", "intake"}
                or item_id in synthetic_allowed
            )
        )
    return candidates


def _checklist_derived_sections(items: list[Mapping[str, Any]]) -> dict[str, Any]:
    present: list[dict[str, Any]] = []
    required: list[dict[str, Any]] = []
    for evidence in items:
        status = evidence["status"]
        if status.startswith("provided"):
            artifact_ids = evidence["artifact_ids"]
            present.append(
                {
                    "item_id": evidence["item_id"],
                    "title": evidence["title"],
                    "status": (
                        "available"
                        if status == "provided_sufficient"
                        else "insufficient"
                    ),
                    "node_id": evidence["node_id"],
                    "fact": evidence["fact_id"],
                    "why": evidence["why"],
                    "artifact_id": artifact_ids[0] if artifact_ids else None,
                }
            )
        elif status in {"missing", "conditional"} and evidence["current_path"]:
            required.append(
                {
                    "item_id": evidence["item_id"],
                    "title": evidence["title"],
                    "status": "still_needed" if status == "missing" else "conditional",
                    "node_id": evidence["node_id"],
                    "fact": evidence["fact_id"],
                    "why": evidence["why"],
                    "mandatory": (
                        "now" if status == "missing" else evidence["applies_when"]
                    ),
                    "already_supplied": False,
                }
            )
    return {
        "present": present,
        "required": required,
        "summary": {
            "provided_sufficient": sum(
                item["status"] == "provided_sufficient" for item in items
            ),
            "provided_insufficient": sum(
                item["status"] == "provided_insufficient" for item in items
            ),
            "missing": sum(item["status"] == "missing" for item in items),
            "conditional": sum(item["status"] == "conditional" for item in items),
            "not_applicable": sum(
                item["status"] == "not_applicable" for item in items
            ),
            "process_nodes_covered": len(
                {
                    node_id
                    for item in items
                    for node_id in item.get("node_ids", [item["node_id"]])
                }
            ),
        },
    }


def _verify_source_integrity_artifact(
    artifact: Mapping[str, Any],
    agent: Mapping[str, Any],
) -> None:
    path = "audit.specialist_artifacts.document_source_integrity"
    items = _causal_list(artifact.get("artifacts"), f"{path}.artifacts")
    accepted_ids: list[str] = []
    seen_ids: set[str] = set()
    rejected_count = 0
    exact_fields = {
        "artifact_id",
        "integrity_class",
        "source_ref_ids",
        "confidence_basis_points",
        "attribution",
        "deterministic_fallback_applied",
    }
    for index, raw_item in enumerate(items):
        item_path = f"{path}.artifacts[{index}]"
        item = _causal_mapping(raw_item, item_path)
        artifact_id = item.get("artifact_id")
        fallback = item.get("deterministic_fallback_applied")
        if (
            set(item) != exact_fields
            or not isinstance(artifact_id, str)
            or not artifact_id
            or artifact_id in seen_ids
            or item.get("integrity_class") not in ACCEPTED_SOURCE_INTEGRITY_CLASSES
            or not isinstance(fallback, bool)
        ):
            _causal_failure(item_path)
        seen_ids.add(artifact_id)
        source_ids = _causal_text_list(
            item.get("source_ref_ids"),
            f"{item_path}.source_ref_ids",
            source_refs=True,
        )
        if (item["integrity_class"] == "text_grounded") is not bool(source_ids):
            _causal_failure(f"{item_path}.source_ref_ids")
        _causal_basis_points(
            item.get("confidence_basis_points"),
            f"{item_path}.confidence_basis_points",
        )
        expected_attribution = (
            "deterministic_application"
            if fallback
            else "Document and Source Integrity Agent"
        )
        if item.get("attribution") != expected_attribution:
            _causal_failure(f"{item_path}.attribution")
        if fallback:
            rejected_count += 1
        else:
            accepted_ids.append(artifact_id)
    _verify_unit_accounting(agent, accepted_ids, rejected_count, path)


def _verify_orchestrator_plan_artifact(
    result: Mapping[str, Any],
    artifact: Mapping[str, Any],
    agent: Mapping[str, Any],
) -> None:
    path = "audit.specialist_artifacts.orchestrator_plan"
    exact_fields = {
        "model_priority_fact_ids",
        "model_priority_task_codes",
        "priority_task_codes",
        "model_priority_attribution",
        "deterministic_coverage",
        "focus_fact_ids",
        "focus_source_ref_ids",
        "contribution_type",
    }
    if set(artifact) != exact_fields:
        _causal_failure(path)
    priority_fact_ids = _causal_text_list(
        artifact.get("model_priority_fact_ids"),
        f"{path}.model_priority_fact_ids",
    )
    if not 1 <= len(priority_fact_ids) <= 6:
        _causal_failure(f"{path}.model_priority_fact_ids")
    task_codes = _causal_text_list(
        artifact.get("model_priority_task_codes"),
        f"{path}.model_priority_task_codes",
    )
    expected_task_codes = {
        "source_integrity",
        "process_decisions",
        "evidence_gaps",
        "final_brief",
    }
    if (
        len(task_codes) != 4
        or set(task_codes) != expected_task_codes
        or artifact.get("priority_task_codes") != task_codes
        or artifact.get("model_priority_attribution") != "Nemotron Orchestrator"
        or artifact.get("contribution_type")
        != "constrained_focus_prioritization"
    ):
        _causal_failure(f"{path}.model_priority_task_codes")
    coverage = _causal_mapping(
        artifact.get("deterministic_coverage"), f"{path}.deterministic_coverage"
    )
    if set(coverage) != {
        "fact_ids",
        "source_ref_ids",
        "required_text_artifact_ids",
        "attribution",
    } or coverage.get("attribution") != "deterministic_application":
        _causal_failure(f"{path}.deterministic_coverage")
    deterministic_fact_ids = _causal_text_list(
        coverage.get("fact_ids"), f"{path}.deterministic_coverage.fact_ids"
    )
    focus_fact_ids = _causal_text_list(
        artifact.get("focus_fact_ids"), f"{path}.focus_fact_ids"
    )
    facts = _causal_list(result.get("facts"), "result.facts")
    canonical_fact_ids = [
        item.get("fact_id") if isinstance(item, Mapping) else None for item in facts
    ]
    if (
        any(not isinstance(item, str) or not item for item in canonical_fact_ids)
        or len(set(canonical_fact_ids)) != len(canonical_fact_ids)
        or deterministic_fact_ids
        != [
            fact_id
            for fact_id in canonical_fact_ids
            if fact_id not in priority_fact_ids
        ]
        or focus_fact_ids != [*priority_fact_ids, *deterministic_fact_ids]
    ):
        _causal_failure(f"{path}.focus_fact_ids")
    source_ids = _causal_text_list(
        coverage.get("source_ref_ids"),
        f"{path}.deterministic_coverage.source_ref_ids",
        source_refs=True,
    )
    if artifact.get("focus_source_ref_ids") != source_ids:
        _causal_failure(f"{path}.focus_source_ref_ids")
    _causal_text_list(
        coverage.get("required_text_artifact_ids"),
        f"{path}.deterministic_coverage.required_text_artifact_ids",
        sorted_values=True,
    )
    _verify_unit_accounting(agent, ["model_priority_order"], 0, path)


def _verify_process_artifact(
    result: Mapping[str, Any],
    artifact: Mapping[str, Any],
    source_artifact: Mapping[str, Any],
    process_agent: Mapping[str, Any],
    source_agent: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    path = "audit.specialist_artifacts.process_decision_mapping"
    decisions = _causal_list(artifact.get("decisions"), f"{path}.decisions")
    accepted_ids: list[str] = []
    rejected_count = 0
    by_fact: dict[str, Mapping[str, Any]] = {}
    exact_fields = {
        "fact_id",
        "decision_key",
        "decision_value",
        "state",
        "normalized_value",
        "source_ref_ids",
        "contribution_id",
        "contribution_scope",
        "model_owned_fields",
        "confidence_basis_points",
        "attribution",
        "deterministic_fallback_applied",
    }
    for index, raw_decision in enumerate(decisions):
        item_path = f"{path}.decisions[{index}]"
        decision = _causal_mapping(raw_decision, item_path)
        fact_id = decision.get("fact_id")
        contribution_id = decision.get("contribution_id")
        fallback = decision.get("deterministic_fallback_applied")
        if (
            set(decision) != exact_fields
            or not isinstance(fact_id, str)
            or not fact_id
            or fact_id in by_fact
            or contribution_id != f"fact:{fact_id}:decision_value"
            or decision.get("contribution_scope")
            != "canonical_to_process_decision_mapping"
            or decision.get("model_owned_fields") != ["decision_value"]
            or any(
                not isinstance(decision.get(field), str)
                or not decision.get(field)
                for field in (
                    "decision_key",
                    "decision_value",
                    "state",
                    "normalized_value",
                )
            )
            or not isinstance(fallback, bool)
        ):
            _causal_failure(item_path)
        by_fact[fact_id] = decision
        _causal_text_list(
            decision.get("source_ref_ids"),
            f"{item_path}.source_ref_ids",
            sorted_values=True,
            source_refs=True,
        )
        _causal_basis_points(
            decision.get("confidence_basis_points"),
            f"{item_path}.confidence_basis_points",
        )
        expected_attribution = (
            "deterministic_application"
            if fallback
            else "Process Decision Mapping Agent"
        )
        if decision.get("attribution") != expected_attribution:
            _causal_failure(f"{item_path}.attribution")
        if fallback:
            rejected_count += 1
        else:
            accepted_ids.append(contribution_id)
    _verify_unit_accounting(process_agent, accepted_ids, rejected_count, path)

    facts = _causal_list(result.get("facts"), "result.facts")
    controlling_facts: dict[str, Mapping[str, Any]] = {}
    for index, raw_fact in enumerate(facts):
        fact_path = f"result.facts[{index}]"
        fact = _causal_mapping(raw_fact, fact_path)
        fact_id = fact.get("fact_id")
        if fact.get("controls_process") is True:
            if (
                not isinstance(fact_id, str)
                or not fact_id
                or fact_id in controlling_facts
            ):
                _causal_failure(f"{fact_path}.fact_id")
            controlling_facts[fact_id] = fact
    if set(controlling_facts) != set(by_fact):
        _causal_failure(f"{path}.decisions[].fact_id")
    for fact_id, decision in by_fact.items():
        fact = controlling_facts[fact_id]
        for field in ("decision_key", "state", "normalized_value"):
            if decision.get(field) != fact.get(field):
                _causal_failure(f"{path}.decisions[].{field}")
        exact, compatible = _compatible_release_process_decisions(
            fact, f"{path}.decisions[].decision_value"
        )
        if (
            decision.get("decision_value") not in compatible
            or decision.get("deterministic_fallback_applied") is True
            and decision.get("decision_value") != exact
        ):
            _causal_failure(f"{path}.decisions[].decision_value")

    process = _causal_mapping(result.get("process"), "result.process")
    contribution = _causal_mapping(
        process.get("agent_contribution"), "result.process.agent_contribution"
    )
    fallback_fields = [
        f"{item['fact_id']}.decision_value"
        for item in decisions
        if item["deterministic_fallback_applied"] is True
    ]
    expected_pairs = {
        "authority": "hybrid_guarded_model_contribution",
        "model_owned_fields": ["decision_value"],
        "deterministic_fallback_fields": fallback_fields,
        "deterministic_fallback_count": len(fallback_fields),
        "derived_from": "accepted_or_fallback_specialist_artifact",
        "artifact": artifact,
        "provenance": _accepted_lineage(process_agent),
        "source_integrity_artifact": source_artifact,
        "source_integrity_provenance": _accepted_lineage(source_agent),
    }
    if set(contribution) != set(expected_pairs):
        _causal_failure("result.process.agent_contribution")
    for field, expected in expected_pairs.items():
        if contribution.get(field) != expected:
            _causal_failure(f"result.process.agent_contribution.{field}")

    nodes = _causal_list(process.get("nodes"), "result.process.nodes")
    attached_fact_ids: set[str] = set()
    for index, raw_node in enumerate(nodes):
        node_path = f"result.process.nodes[{index}]"
        node = _causal_mapping(raw_node, node_path)
        fact_ids = _causal_text_list(node.get("fact_ids", []), f"{node_path}.fact_ids")
        expected = [by_fact[fact_id] for fact_id in fact_ids if fact_id in by_fact]
        if expected:
            if node.get("agent_decision_contributions") != expected:
                _causal_failure(f"{node_path}.agent_decision_contributions")
            attached_fact_ids.update(item["fact_id"] for item in expected)
        elif "agent_decision_contributions" in node:
            _causal_failure(f"{node_path}.agent_decision_contributions")
    if attached_fact_ids != set(by_fact):
        _causal_failure("result.process.nodes.agent_decision_contributions")
    _verify_accepted_process_projection(process, decisions)
    return decisions


def _verify_evidence_artifact(
    result: Mapping[str, Any],
    artifact: Mapping[str, Any],
    agent: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    path = "audit.specialist_artifacts.evidence_checklist"
    items = _causal_list(artifact.get("items"), f"{path}.items")
    by_id: dict[str, Mapping[str, Any]] = {}
    accepted_ids: list[str] = []
    rejected_count = 0
    exact_item_fields = {
        "item_id",
        "status",
        "artifact_ids",
        "source_ref_ids",
        "field_contributions",
        "model_owned_fields",
        "confidence_basis_points",
        "attribution",
        "deterministic_fallback_applied",
    }
    contribution_ids = {
        "status": lambda item_id: f"item:{item_id}:status",
        "artifact_ids": lambda item_id: f"item:{item_id}:artifacts",
    }
    for index, raw_item in enumerate(items):
        item_path = f"{path}.items[{index}]"
        item = _causal_mapping(raw_item, item_path)
        item_id = item.get("item_id")
        if (
            set(item) != exact_item_fields
            or not isinstance(item_id, str)
            or not item_id
            or item_id in by_id
            or item.get("status") not in ACCEPTED_EVIDENCE_STATUSES
            or item.get("model_owned_fields") != ["status", "artifact_ids"]
            or not isinstance(item.get("deterministic_fallback_applied"), bool)
        ):
            _causal_failure(item_path)
        by_id[item_id] = item
        _causal_text_list(
            item.get("artifact_ids"),
            f"{item_path}.artifact_ids",
            sorted_values=True,
        )
        _causal_text_list(
            item.get("source_ref_ids"),
            f"{item_path}.source_ref_ids",
            sorted_values=True,
            source_refs=True,
        )
        _causal_basis_points(
            item.get("confidence_basis_points"),
            f"{item_path}.confidence_basis_points",
        )
        fields = _causal_list(
            item.get("field_contributions"), f"{item_path}.field_contributions"
        )
        if len(fields) != 2:
            _causal_failure(f"{item_path}.field_contributions")
        fields_by_name: dict[str, Mapping[str, Any]] = {}
        for field_index, raw_field in enumerate(fields):
            field_path = f"{item_path}.field_contributions[{field_index}]"
            field = _causal_mapping(raw_field, field_path)
            field_name = field.get("field")
            fallback = field.get("deterministic_fallback_applied")
            if (
                set(field)
                != {
                    "contribution_id",
                    "field",
                    "attribution",
                    "confidence_basis_points",
                    "deterministic_fallback_applied",
                }
                or field_name not in contribution_ids
                or field_name in fields_by_name
                or field.get("contribution_id")
                != contribution_ids[field_name](item_id)
                or not isinstance(fallback, bool)
            ):
                _causal_failure(field_path)
            fields_by_name[field_name] = field
            _causal_basis_points(
                field.get("confidence_basis_points"),
                f"{field_path}.confidence_basis_points",
            )
            expected_attribution = (
                "deterministic_application"
                if fallback
                else "Evidence and Checklist Agent"
            )
            if field.get("attribution") != expected_attribution:
                _causal_failure(f"{field_path}.attribution")
            if fallback:
                rejected_count += 1
            else:
                accepted_ids.append(field["contribution_id"])
        fallback_count = sum(
            field["deterministic_fallback_applied"] for field in fields
        )
        expected_attribution = (
            "Evidence and Checklist Agent"
            if fallback_count == 0
            else "mixed_model_and_deterministic"
            if fallback_count == 1
            else "deterministic_application"
        )
        if (
            item.get("deterministic_fallback_applied") is not bool(fallback_count)
            or item.get("attribution") != expected_attribution
        ):
            _causal_failure(f"{item_path}.attribution")
    _verify_unit_accounting(agent, accepted_ids, rejected_count, path)

    checklist = _causal_mapping(result.get("checklist"), "result.checklist")
    contribution = _causal_mapping(
        checklist.get("agent_contribution"), "result.checklist.agent_contribution"
    )
    fallback_fields = sorted(
        field["contribution_id"]
        for item in items
        for field in item["field_contributions"]
        if field["deterministic_fallback_applied"] is True
    )
    expected_pairs = {
        "authority": "hybrid_guarded_model_contribution",
        "model_owned_fields": ["status", "artifact_ids"],
        "deterministic_fallback_fields": fallback_fields,
        "deterministic_fallback_count": len(fallback_fields),
        "derived_from": "accepted_or_fallback_specialist_artifact",
        "artifact": artifact,
        "provenance": _accepted_lineage(agent),
    }
    if set(contribution) != set(expected_pairs):
        _causal_failure("result.checklist.agent_contribution")
    for field, expected in expected_pairs.items():
        if contribution.get(field) != expected:
            _causal_failure(f"result.checklist.agent_contribution.{field}")

    public_items = _causal_list(checklist.get("items"), "result.checklist.items")
    if len(public_items) != len(items):
        _causal_failure("result.checklist.items")
    public_by_id: dict[str, Mapping[str, Any]] = {}
    for index, raw_item in enumerate(public_items):
        item_path = f"result.checklist.items[{index}]"
        item = _causal_mapping(raw_item, item_path)
        item_id = item.get("item_id")
        if not isinstance(item_id, str) or item_id in public_by_id:
            _causal_failure(f"{item_path}.item_id")
        public_by_id[item_id] = item
    if set(public_by_id) != set(by_id):
        _causal_failure("result.checklist.items.item_id")
    candidates = _release_evidence_candidates(str(result.get("claim_id", "")))
    facts_by_id: dict[str, Mapping[str, Any]] = {}
    for index, raw_fact in enumerate(
        _causal_list(result.get("facts"), "result.facts")
    ):
        fact_path = f"result.facts[{index}]"
        fact = _causal_mapping(raw_fact, fact_path)
        fact_id = fact.get("fact_id")
        if not isinstance(fact_id, str) or not fact_id or fact_id in facts_by_id:
            _causal_failure(f"{fact_path}.fact_id")
        facts_by_id[fact_id] = fact
    process = _causal_mapping(result.get("process"), "result.process")
    selected_path = set(
        _causal_text_list(process.get("selected_path"), "result.process.selected_path")
    )
    overlay = _causal_mapping(
        process.get("current_overlay"), "result.process.current_overlay"
    )
    next_action_node_id = overlay.get("next_action_node_id")
    if not isinstance(next_action_node_id, str) or not next_action_node_id:
        _causal_failure("result.process.current_overlay.next_action_node_id")
    active_nodes = {*selected_path, next_action_node_id}
    for item_id, accepted_item in by_id.items():
        public_item = public_by_id[item_id]
        public_artifact_ids = _causal_text_list(
            public_item.get("artifact_ids"),
            "result.checklist.items[].artifact_ids",
        )
        artifact_ids = accepted_item["artifact_ids"]
        required_level = public_item.get("required_level")
        status = accepted_item["status"]
        owner_node_ids = _causal_text_list(
            public_item.get("node_ids"), "result.checklist.items[].node_ids"
        )
        fact_id = public_item.get("fact_id")
        fact = facts_by_id.get(fact_id) if isinstance(fact_id, str) else None
        if fact is None:
            _causal_failure("result.checklist.items[].fact_id")
        fact_artifact_ids = {
            ref.get("artifact_id")
            for ref in (
                _causal_mapping(raw_ref, "result.facts[].source_refs[]")
                for raw_ref in _causal_list(
                    fact.get("source_refs"), "result.facts[].source_refs"
                )
            )
            if isinstance(ref.get("artifact_id"), str)
        }
        grounded_candidates = set(candidates.get(item_id, [])) & fact_artifact_ids
        expected_current_path = bool(active_nodes.intersection(owner_node_ids))
        if artifact_ids:
            coherent_statuses = {
                "provided_sufficient",
                "provided_insufficient",
            }
            if required_level == "conditional":
                coherent_statuses.add("conditional")
        elif required_level == "mandatory":
            coherent_statuses = {"missing"}
        elif required_level == "conditional":
            coherent_statuses = {"conditional", "not_applicable"}
        else:
            _causal_failure("result.checklist.items[].required_level")
        if (
            item_id not in candidates
            or set(artifact_ids) - grounded_candidates
            or status not in coherent_statuses
            or public_item.get("current_path") is not expected_current_path
            or status == "missing"
            and not expected_current_path
            or status == "conditional"
            and public_item.get("applies_when") in {None, "", "always"}
        ):
            _causal_failure(
                f"audit.specialist_artifacts.evidence_checklist.items[{item_id}].coherence"
            )
        if (
            public_item.get("status") != accepted_item["status"]
            or sorted(public_artifact_ids) != accepted_item["artifact_ids"]
            or public_item.get("agent_contribution")
            != accepted_item["field_contributions"]
        ):
            _causal_failure("result.checklist.items[].agent_contribution")
    try:
        derived = _checklist_derived_sections(public_items)
    except (KeyError, TypeError):
        _causal_failure("result.checklist.items")
    for field, expected in derived.items():
        if checklist.get(field) != expected:
            _causal_failure(f"result.checklist.{field}")
    return items


def _verify_final_artifact(
    result: Mapping[str, Any],
    artifact: Mapping[str, Any],
    process_decisions: list[Mapping[str, Any]],
    evidence_items: list[Mapping[str, Any]],
    agent: Mapping[str, Any],
) -> None:
    path = "audit.specialist_artifacts.final_claim_brief_audit"
    exact_fields = {
        *FINAL_FIELD_CONTRIBUTION_IDS,
        "source_ref_ids",
        "input_contribution_ids",
        "lineage_authority",
        "contribution_scope",
        "field_contributions",
        "confidence_basis_points",
        "attribution",
        "deterministic_fallback_applied",
    }
    if set(artifact) != exact_fields:
        _causal_failure(path)
    fields = _causal_list(
        artifact.get("field_contributions"), f"{path}.field_contributions"
    )
    if len(fields) != len(FINAL_FIELD_CONTRIBUTION_IDS):
        _causal_failure(f"{path}.field_contributions")
    accepted_ids: list[str] = []
    rejected_count = 0
    seen_fields: set[str] = set()
    for index, raw_field in enumerate(fields):
        field_path = f"{path}.field_contributions[{index}]"
        field = _causal_mapping(raw_field, field_path)
        field_name = field.get("field")
        fallback = field.get("deterministic_fallback_applied")
        if (
            set(field)
            != {
                "contribution_id",
                "field",
                "attribution",
                "confidence_basis_points",
                "deterministic_fallback_applied",
            }
            or field_name not in FINAL_FIELD_CONTRIBUTION_IDS
            or field_name in seen_fields
            or field.get("contribution_id")
            != FINAL_FIELD_CONTRIBUTION_IDS[field_name]
            or not isinstance(fallback, bool)
        ):
            _causal_failure(field_path)
        seen_fields.add(field_name)
        _causal_basis_points(
            field.get("confidence_basis_points"),
            f"{field_path}.confidence_basis_points",
        )
        expected_attribution = (
            "deterministic_application" if fallback else "Final Claim Brief Agent"
        )
        if field.get("attribution") != expected_attribution:
            _causal_failure(f"{field_path}.attribution")
        if fallback:
            rejected_count += 1
        else:
            accepted_ids.append(field["contribution_id"])
    _verify_unit_accounting(agent, accepted_ids, rejected_count, path)
    _causal_basis_points(
        artifact.get("confidence_basis_points"), f"{path}.confidence_basis_points"
    )
    expected_attribution = (
        "Final Claim Brief Agent"
        if rejected_count == 0
        else "mixed_model_and_deterministic"
        if accepted_ids
        else "deterministic_application"
    )
    if (
        artifact.get("deterministic_fallback_applied") is not bool(rejected_count)
        or artifact.get("attribution") != expected_attribution
    ):
        _causal_failure(f"{path}.attribution")

    process = _causal_mapping(result.get("process"), "result.process")
    overlay = _causal_mapping(
        process.get("current_overlay"), "result.process.current_overlay"
    )
    current_id = overlay.get("current_node_id")
    next_id = overlay.get("next_action_node_id")
    if (
        not isinstance(current_id, str)
        or artifact.get("current_node_id") != current_id
        or process.get("current_node") != current_id
    ):
        _causal_failure(f"{path}.current_node_id")
    if (
        not isinstance(next_id, str)
        or artifact.get("next_action_node_id") != next_id
    ):
        _causal_failure(f"{path}.next_action_node_id")
    nodes = _causal_list(process.get("nodes"), "result.process.nodes")
    matching_nodes = [
        item
        for item in nodes
        if isinstance(item, Mapping) and item.get("node_id") == current_id
    ]
    if len(matching_nodes) != 1:
        _causal_failure("result.process.current_node")
    expected_supporting = sorted(
        _causal_text_list(
            matching_nodes[0].get("fact_ids", []),
            "result.process.current_node.fact_ids",
        )
    )
    supporting = _causal_text_list(
        artifact.get("supporting_fact_ids"),
        f"{path}.supporting_fact_ids",
        sorted_values=True,
    )
    if supporting != expected_supporting:
        _causal_failure(f"{path}.supporting_fact_ids")

    upstream = _causal_text_list(
        artifact.get("upstream_contribution_ids"),
        f"{path}.upstream_contribution_ids",
        sorted_values=True,
    )
    audit_checks = _causal_text_list(
        artifact.get("audit_check_ids"),
        f"{path}.audit_check_ids",
        sorted_values=True,
    )
    if upstream != list(FINAL_UPSTREAM_CONTRIBUTION_IDS):
        _causal_failure(f"{path}.upstream_contribution_ids")
    if artifact.get("input_contribution_ids") != upstream:
        _causal_failure(f"{path}.input_contribution_ids")
    if audit_checks != list(FINAL_AUDIT_CHECK_IDS):
        _causal_failure(f"{path}.audit_check_ids")
    upstream_field = next(
        field for field in fields if field["field"] == "upstream_contribution_ids"
    )
    expected_lineage_authority = (
        "deterministic_application"
        if upstream_field["deterministic_fallback_applied"]
        else "hybrid_guarded_model_audit"
    )
    if (
        artifact.get("lineage_authority") != expected_lineage_authority
        or artifact.get("contribution_scope")
        != "independent_final_claim_brief_audit"
    ):
        _causal_failure(f"{path}.lineage_authority")

    refs_by_fact: dict[str, set[str]] = {}
    for item in process_decisions:
        fact_id = item.get("fact_id")
        source_ids = item.get("source_ref_ids")
        if isinstance(fact_id, str) and isinstance(source_ids, list):
            refs_by_fact.setdefault(fact_id, set()).update(source_ids)
    checklist = _causal_mapping(result.get("checklist"), "result.checklist")
    public_items = _causal_list(checklist.get("items"), "result.checklist.items")
    public_fact_by_item: dict[str, str] = {}
    for index, raw_item in enumerate(public_items):
        item_path = f"result.checklist.items[{index}]"
        item = _causal_mapping(raw_item, item_path)
        item_id = item.get("item_id")
        fact_id = item.get("fact_id")
        if (
            not isinstance(item_id, str)
            or not item_id
            or item_id in public_fact_by_item
            or not isinstance(fact_id, str)
            or not fact_id
        ):
            _causal_failure(f"{item_path}.fact_id")
        public_fact_by_item[item_id] = fact_id
    for index, item in enumerate(evidence_items):
        item_id = item.get("item_id")
        if item_id not in public_fact_by_item:
            _causal_failure(
                f"audit.specialist_artifacts.evidence_checklist.items[{index}].item_id"
            )
        refs_by_fact.setdefault(public_fact_by_item[item_id], set()).update(
            item["source_ref_ids"]
        )
    expected_source_ids = sorted(
        {
            source_id
            for fact_id in supporting
            for source_id in refs_by_fact.get(fact_id, set())
        }
    )
    source_ids = _causal_text_list(
        artifact.get("source_ref_ids"),
        f"{path}.source_ref_ids",
        sorted_values=True,
        source_refs=True,
    )
    if source_ids != expected_source_ids:
        _causal_failure(f"{path}.source_ref_ids")

    if result.get("current_overlay") != overlay:
        _causal_failure("result.current_overlay")
    next_action = _causal_mapping(result.get("next_action"), "result.next_action")
    if next_action.get("process_node_id") != next_id:
        _causal_failure("result.next_action.process_node_id")
    if next_action.get("agent_brief_contribution") != artifact:
        _causal_failure("result.next_action.agent_brief_contribution")


def _verify_hybrid_causal_artifacts(
    result: Mapping[str, Any],
    audit: Mapping[str, Any],
    by_agent: Mapping[str, Mapping[str, Any]],
    gates_by_id: Mapping[str, Mapping[str, Any]],
) -> None:
    _verify_grounded_flagship_contract(result)
    facts = _causal_list(result.get("facts"), "result.facts")
    canonical_agent = by_agent["canonical_facts"]
    fact_ids = {
        item.get("fact_id")
        for item in facts
        if isinstance(item, Mapping) and isinstance(item.get("fact_id"), str)
    }
    if (
        len(fact_ids) != len(facts)
        or not set(canonical_agent.get("accepted_ids", [])) <= fact_ids
        or canonical_agent.get("accepted_count", 0)
        + canonical_agent.get("rejected_count", 0)
        != len(facts)
    ):
        _causal_failure("audit.agents.canonical_facts.accepted_ids")
    if canonical_agent.get("output_artifact") != "canonical_claim_state":
        _causal_failure("audit.agents.canonical_facts.output_artifact")
    if canonical_agent.get("output_artifact_hash") != _runtime_canonical_facts_hash(
        facts, "result.facts"
    ):
        _causal_failure("audit.agents.canonical_facts.output_artifact_hash")
    _verify_assertion_selection_receipts(result, canonical_agent)

    artifacts = _causal_mapping(
        audit.get("specialist_artifacts"), "audit.specialist_artifacts"
    )
    if set(artifacts) != set(SPECIALIST_ARTIFACT_IDS):
        _causal_failure("audit.specialist_artifacts")
    for agent_id in SPECIALIST_ARTIFACT_IDS:
        artifact = _causal_mapping(
            artifacts.get(agent_id), f"audit.specialist_artifacts.{agent_id}"
        )
        agent = by_agent[agent_id]
        if agent.get("output_artifact") != SPECIALIST_OUTPUT_ARTIFACTS[agent_id]:
            _causal_failure(f"audit.agents.{agent_id}.output_artifact")
        expected_hash = _causal_hash(
            artifact, f"audit.specialist_artifacts.{agent_id}"
        )
        if agent.get("output_artifact_hash") != expected_hash:
            _causal_failure(f"audit.agents.{agent_id}.output_artifact_hash")

    source_artifact = artifacts["document_source_integrity"]
    process_artifact = artifacts["process_decision_mapping"]
    evidence_artifact = artifacts["evidence_checklist"]
    final_artifact = artifacts["final_claim_brief_audit"]
    _verify_orchestrator_plan_artifact(
        result, artifacts["orchestrator_plan"], by_agent["orchestrator_plan"]
    )
    _verify_source_integrity_artifact(
        source_artifact, by_agent["document_source_integrity"]
    )
    coverage = artifacts["orchestrator_plan"]["deterministic_coverage"]
    source_items = source_artifact["artifacts"]
    text_artifact_ids = sorted(
        item["artifact_id"]
        for item in source_items
        if item["integrity_class"] == "text_grounded"
    )
    source_focus_ids = {
        source_id
        for item in source_items
        for source_id in item["source_ref_ids"]
    }
    plan_focus_ids = artifacts["orchestrator_plan"]["focus_source_ref_ids"]
    if coverage["required_text_artifact_ids"] != text_artifact_ids:
        _causal_failure(
            "audit.specialist_artifacts.orchestrator_plan."
            "deterministic_coverage.required_text_artifact_ids"
        )
    if (
        len(plan_focus_ids) != len(text_artifact_ids)
        or any(
            len(item["source_ref_ids"]) != 1
            for item in source_items
            if item["integrity_class"] == "text_grounded"
        )
        or source_focus_ids != set(plan_focus_ids)
    ):
        _causal_failure(
            "audit.specialist_artifacts.orchestrator_plan.focus_source_ref_ids"
        )
    process_decisions = _verify_process_artifact(
        result,
        process_artifact,
        source_artifact,
        by_agent["process_decision_mapping"],
        by_agent["document_source_integrity"],
    )
    evidence_items = _verify_evidence_artifact(
        result, evidence_artifact, by_agent["evidence_checklist"]
    )
    if audit.get("final_claim_brief") != final_artifact:
        _causal_failure("audit.final_claim_brief")
    _verify_final_artifact(
        result,
        final_artifact,
        process_decisions,
        evidence_items,
        by_agent["final_claim_brief_audit"],
    )
    if result.get("agent_orchestration") != audit:
        _causal_failure("result.agent_orchestration")

    process_gate = gates_by_id["deterministic_process_gate"]
    evidence_gate = gates_by_id["deterministic_evidence_gate"]
    expected_process_input = _causal_hash(
        {
            "source_integrity": source_artifact,
            "process_mapping": process_artifact,
        },
        "audit.deterministic_gates.deterministic_process_gate.input_artifact_hash",
    )
    if process_gate.get("input_artifact_hash") != expected_process_input:
        _causal_failure(
            "audit.deterministic_gates.deterministic_process_gate.input_artifact_hash"
        )
    expected_evidence_input = _causal_hash(
        evidence_artifact,
        "audit.deterministic_gates.deterministic_evidence_gate.input_artifact_hash",
    )
    if evidence_gate.get("input_artifact_hash") != expected_evidence_input:
        _causal_failure(
            "audit.deterministic_gates.deterministic_evidence_gate.input_artifact_hash"
        )

    verification = _causal_mapping(result.get("verification"), "result.verification")
    whole_gate = gates_by_id["whole_playbook_gate"]
    process = _causal_mapping(result.get("process"), "result.process")
    checklist = _causal_mapping(result.get("checklist"), "result.checklist")
    accepted_bundle = {
        "process": _semantic_process_dto(process),
        "checklist": _semantic_checklist_dto(checklist),
        "final_brief": final_artifact,
    }
    expected_bundle_hash = _causal_hash(
        accepted_bundle,
        "audit.deterministic_gates.whole_playbook_gate.output_artifact_hash",
    )
    expected_final_brief_hash = _causal_hash(
        final_artifact,
        "audit.deterministic_gates.whole_playbook_gate.final_brief_artifact_hash",
    )
    expected_verification_report_hash = _causal_hash(
        verification,
        "audit.deterministic_gates.whole_playbook_gate.verification_report_hash",
    )
    result_audit = _causal_mapping(result.get("audit"), "result.audit")
    canonicalization = _causal_mapping(
        result_audit.get("canonicalization"),
        "result.audit.canonicalization",
    )
    effective_understanding = {
        "summary": result.get("summary"),
        "category": result.get("category"),
        "subcategory": result.get("subcategory"),
        "scope": result.get("scope"),
        "dispute": result.get("dispute"),
        "facts": _runtime_canonical_facts_value(
            _causal_list(result.get("facts"), "result.facts"),
            "result.facts",
        ),
        "issues": result.get("issues"),
        "observable_only": True,
        "canonicalization": canonicalization,
    }
    expected_whole_playbook_hash = _causal_runtime_hash(
        {
            "understanding": effective_understanding,
            "legal": result.get("legal_research"),
            "process": process,
            "checklist": checklist,
            "precedents": result.get("precedents"),
            "precedent_ranking": result.get("precedent_ranking"),
        },
        "result.verification.whole_playbook_hash",
    )
    if whole_gate.get("output_artifact_hash") != expected_bundle_hash:
        _causal_failure(
            "audit.deterministic_gates.whole_playbook_gate.output_artifact_hash"
        )
    if (
        whole_gate.get("output_projection_contract")
        != WHOLE_PLAYBOOK_OUTPUT_PROJECTION_CONTRACT
    ):
        _causal_failure(
            "audit.deterministic_gates.whole_playbook_gate.output_projection_contract"
        )
    if whole_gate.get("final_brief_artifact_hash") != expected_final_brief_hash:
        _causal_failure(
            "audit.deterministic_gates.whole_playbook_gate.final_brief_artifact_hash"
        )
    if whole_gate.get("verification_report_hash") != expected_verification_report_hash:
        _causal_failure(
            "audit.deterministic_gates.whole_playbook_gate.verification_report_hash"
        )
    if (
        whole_gate.get("verification_whole_playbook_hash")
        != expected_whole_playbook_hash
    ):
        _causal_failure(
            "audit.deterministic_gates.whole_playbook_gate.verification_whole_playbook_hash"
        )
    if verification.get("whole_playbook_hash") != expected_whole_playbook_hash:
        _causal_failure("result.verification.whole_playbook_hash")
    if len(
        {
            expected_bundle_hash,
            expected_final_brief_hash,
            expected_verification_report_hash,
            expected_whole_playbook_hash,
        }
    ) != 4:
        _causal_failure(
            "audit.deterministic_gates.whole_playbook_gate.distinct_hash_domains"
        )
    checks = _causal_list(verification.get("checks"), "result.verification.checks")
    check_ids = [
        item.get("name") if isinstance(item, Mapping) else None for item in checks
    ]
    if (
        any(not isinstance(item, str) or not item for item in check_ids)
        or len(set(check_ids)) != len(check_ids)
        or whole_gate.get("accepted_verification_ids") != check_ids
    ):
        _causal_failure(
            "audit.deterministic_gates.whole_playbook_gate.accepted_verification_ids"
        )


def _verify_cold_flagship_evidence(
    run: dict[str, Any],
    ledger: dict[str, Any],
) -> str:
    if run.get("status") != "complete":
        raise VerificationError("Dynamic flagship run must be complete")
    audit = _orchestration_audit(run)
    if not isinstance(audit, dict):
        raise VerificationError("Dynamic flagship run lacks an orchestration audit")
    if run.get("agent_orchestration") != audit:
        _causal_failure("run.agent_orchestration")
    expected_audit = {
        "schema_version": REQUIRED_ORCHESTRATION_SCHEMA,
        "implementation": REQUIRED_AGENT_IMPLEMENTATION,
        "framework": REQUIRED_FRAMEWORK,
        "model": REQUIRED_PRODUCTION_MODEL,
        "authority_mode": REQUIRED_AUTHORITY_MODE,
        "model_assisted": True,
        "deterministic_safety_authority": True,
        "external_tracing": False,
        "prompt_storage": False,
        "raw_output_storage": False,
        "execution_topology": REQUIRED_EXECUTION_TOPOLOGY,
        "all_required_agents_contributed": True,
    }
    for key, expected in expected_audit.items():
        if audit.get(key) != expected:
            raise VerificationError(
                f"Dynamic flagship orchestration {key} must be {expected!r}"
            )
    orchestration_id = audit.get("orchestration_id")
    if not isinstance(orchestration_id, str) or not orchestration_id:
        raise VerificationError("Dynamic flagship orchestration ID is absent")

    agents = audit.get("agents")
    if not isinstance(agents, list) or len(agents) != len(REQUIRED_MODEL_AGENTS):
        raise VerificationError("Dynamic flagship must contain exactly six model agents")
    by_agent: dict[str, dict[str, Any]] = {}
    for agent in agents:
        agent_id = agent.get("agent_id") if isinstance(agent, dict) else None
        if not isinstance(agent_id, str) or agent_id in by_agent:
            raise VerificationError("Dynamic flagship agent IDs must be present and distinct")
        by_agent[agent_id] = agent
    expected_agent_ids = [item["agent_id"] for item in REQUIRED_MODEL_AGENTS]
    if set(by_agent) != set(expected_agent_ids):
        raise VerificationError("Dynamic flagship agent set is not the required six-role set")
    if not _has_valid_parallel_agent_order(agents):
        raise VerificationError("Dynamic flagship agent order violates the execution topology")

    call_ids: list[str] = []
    response_ids: list[str] = []
    delegation_ids: list[str] = []
    fallback_count = 0
    for expected_agent in REQUIRED_MODEL_AGENTS:
        agent_id = expected_agent["agent_id"]
        agent = by_agent[agent_id]
        expected_pairs = {
            "role": expected_agent["role"],
            "actor_type": "nemotron_agent",
            "acceptance_scope": "pre_review_model_output",
            "model": REQUIRED_PRODUCTION_MODEL,
            "provider": "openrouter",
            "requested_model": REQUIRED_PRODUCTION_MODEL,
            "call_count": 1,
            "cache_hit": False,
        }
        for key, expected in expected_pairs.items():
            if agent.get(key) != expected:
                raise VerificationError(
                    f"Dynamic flagship agent {agent_id} {key} must be {expected!r}"
                )
        if agent.get("outcome") != "succeeded":
            raise VerificationError(
                f"Dynamic flagship agent {agent_id} must be a clean succeeded call"
            )
        _verify_successful_provider_provenance(
            agent,
            f"Dynamic flagship agent {agent_id}",
        )
        if (
            agent.get("origin_call_id") != agent.get("call_id")
            or agent.get("usage_source") not in ACCEPTED_USAGE_SOURCES
            or agent.get("finish_reason") != "stop"
        ):
            _causal_failure(f"audit.agents.{agent_id}.origin_call_id")
        for key in ("call_id",):
            value = agent.get(key)
            if not isinstance(value, str) or not value:
                raise VerificationError(f"Dynamic flagship agent {agent_id} lacks {key}")
        for key in ("input_artifact_hash", "output_artifact_hash"):
            if not re.fullmatch(r"[0-9a-f]{64}", str(agent.get(key, ""))):
                raise VerificationError(f"Dynamic flagship agent {agent_id} lacks {key}")
        accepted_count = agent.get("accepted_count")
        rejected_count = agent.get("rejected_count")
        if (
            not isinstance(accepted_count, int)
            or isinstance(accepted_count, bool)
            or accepted_count < 1
            or not isinstance(rejected_count, int)
            or isinstance(rejected_count, bool)
            or rejected_count != 0
        ):
            raise VerificationError(
                f"Dynamic flagship agent {agent_id} lacks a strict accepted majority"
            )
        accepted_ids = agent.get("accepted_ids")
        if (
            not isinstance(accepted_ids, list)
            or len(accepted_ids) != accepted_count
            or len(set(accepted_ids)) != len(accepted_ids)
            or any(not isinstance(item, str) or not item for item in accepted_ids)
        ):
            raise VerificationError(
                f"Dynamic flagship agent {agent_id} accepted IDs are unbound"
            )
        fallback_applied = agent.get("deterministic_fallback_applied")
        if fallback_applied is not False:
            raise VerificationError(
                f"Dynamic flagship agent {agent_id} must not use deterministic fallback"
            )
        fallback_count += int(fallback_applied)
        if agent_id == "canonical_facts":
            projected = agent.get("source_reference_projection_fact_ids")
            projection_count = agent.get("source_reference_projection_count")
            if (
                not isinstance(projected, list)
                or len(set(projected)) != len(projected)
                or projected != []
                or projection_count != 0
            ):
                raise VerificationError(
                    "Canonical facts source-reference projection disclosure is invalid"
                )
        call_ids.append(agent["call_id"])
        response_ids.append(agent["response_id"])

        canonical_call_id = by_agent["canonical_facts"].get("call_id")
        orchestrator_call_id = by_agent["orchestrator_plan"].get("call_id")
        parent_call_id = agent.get("parent_call_id")
        delegation_id = agent.get("delegation_id")
        if agent_id == "canonical_facts":
            if parent_call_id is not None or delegation_id is not None:
                raise VerificationError("Canonical facts must be the root model call")
        elif agent_id == "orchestrator_plan":
            if parent_call_id != canonical_call_id:
                raise VerificationError("Nemotron orchestrator must follow canonical facts")
        elif parent_call_id != orchestrator_call_id:
            raise VerificationError(f"Specialist {agent_id} must follow the orchestrator")
        if agent_id != "canonical_facts":
            if not isinstance(delegation_id, str) or not delegation_id:
                raise VerificationError(f"Dynamic flagship agent {agent_id} lacks delegation")
            delegation_ids.append(delegation_id)

    if len(set(call_ids)) != len(call_ids):
        raise VerificationError("Dynamic flagship call IDs must be distinct")
    if len(set(response_ids)) != len(response_ids):
        raise VerificationError("Dynamic flagship response IDs must be distinct")
    if len(set(delegation_ids)) != len(delegation_ids):
        raise VerificationError("Dynamic flagship delegation IDs must be distinct")
    if audit.get("guarded_fallback_count") != fallback_count:
        raise VerificationError("Dynamic flagship fallback count is not exact")

    gates = audit.get("deterministic_gates")
    if not isinstance(gates, list) or len(gates) != len(REQUIRED_DETERMINISTIC_GATES):
        raise VerificationError("Dynamic flagship must contain exactly three deterministic gates")
    gates_by_id: dict[str, dict[str, Any]] = {}
    for gate in gates:
        gate_id = gate.get("agent_id") if isinstance(gate, dict) else None
        if not isinstance(gate_id, str) or gate_id in gates_by_id:
            raise VerificationError("Dynamic flagship gate IDs must be present and distinct")
        gates_by_id[gate_id] = gate
    if set(gates_by_id) != {item["gate_id"] for item in REQUIRED_DETERMINISTIC_GATES}:
        raise VerificationError("Dynamic flagship gate set is not the required three-gate set")
    gate_roles = {
        item["gate_id"]: item["role"] for item in REQUIRED_DETERMINISTIC_GATES
    }
    result = run["result"]
    if not isinstance(result.get("process"), Mapping) or not isinstance(
        result.get("checklist"), Mapping
    ):
        raise VerificationError("Dynamic flagship accepted DTO is missing")
    result_audit = _causal_mapping(result.get("audit"), "result.audit")
    expected_understanding = {
        "summary": result.get("summary"),
        "category": result.get("category"),
        "subcategory": result.get("subcategory"),
        "scope": result.get("scope"),
        "dispute": result.get("dispute"),
        "facts": result.get("facts"),
        "issues": result.get("issues"),
        "observable_only": True,
        "canonicalization": result_audit.get("canonicalization"),
    }
    if run.get("understanding") != expected_understanding:
        _causal_failure("run.understanding")
    for key in (
        "process",
        "checklist",
        "precedents",
        "precedent_ranking",
        "verification",
    ):
        if run.get(key) != result.get(key):
            _causal_failure(f"run.{key}")
    accepted_bundle = {
        "process": _semantic_process_dto(result.get("process")),
        "checklist": _semantic_checklist_dto(result.get("checklist")),
        "final_brief": audit.get("final_claim_brief"),
    }
    gate_bindings = {
        "deterministic_process_gate": (
            "process_graph",
            result.get("process"),
            "process_decision_mapping",
        ),
        "deterministic_evidence_gate": (
            "evidence_model",
            result.get("checklist"),
            "evidence_checklist",
        ),
        "whole_playbook_gate": (
            "verified_claim_playbook",
            accepted_bundle,
            "final_claim_brief_audit",
        ),
    }
    for gate_id, (output_artifact, artifact_value, source_agent_id) in gate_bindings.items():
        if not isinstance(artifact_value, Mapping):
            raise VerificationError(
                f"Dynamic flagship {gate_id} accepted DTO is missing"
            )
        gate = gates_by_id[gate_id]
        source_agent = by_agent[source_agent_id]
        expected_pairs = {
            "role": gate_roles[gate_id],
            "actor_type": "deterministic_gate",
            "receipt_type": "accepted_artifact",
            "acceptance_scope": "pre_review_model_output",
            "model": None,
            "outcome": "passed",
            "source_agent_id": source_agent_id,
            "source_call_id": source_agent["call_id"],
            "delegation_id": source_agent["delegation_id"],
            "accepted_ids": source_agent["accepted_ids"],
            "accepted_count": source_agent["accepted_count"],
            "output_artifact": output_artifact,
            "output_artifact_hash": accepted_artifact_hash(artifact_value),
        }
        if gate_id == "whole_playbook_gate":
            expected_pairs["output_projection_contract"] = (
                WHOLE_PLAYBOOK_OUTPUT_PROJECTION_CONTRACT
            )
        for key, expected in expected_pairs.items():
            if gate.get(key) != expected:
                raise VerificationError(
                    f"Dynamic flagship gate {gate_id}.{key} must be {expected!r}"
                )
        if not re.fullmatch(r"[0-9a-f]{64}", str(gate.get("input_artifact_hash", ""))):
            raise VerificationError(f"Dynamic flagship gate {gate_id} lacks an input hash")

    _verify_hybrid_causal_artifacts(result, audit, by_agent, gates_by_id)

    _verify_public_model_ledger(ledger, "Dynamic flagship ledger")
    ledger_call_ids = [item.get("call_id") for item in ledger["items"]]
    ledger_agent_ids = [item.get("agent_id") for item in ledger["items"]]
    if (
        len(ledger["items"]) != len(REQUIRED_MODEL_AGENTS)
        or len(set(ledger_call_ids)) != len(call_ids)
        or set(ledger_call_ids) != set(call_ids)
        or len(set(ledger_agent_ids)) != len(expected_agent_ids)
        or set(ledger_agent_ids) != set(expected_agent_ids)
        or not _has_valid_parallel_agent_order(ledger["items"])
        or ledger["summary"].get("records") != len(REQUIRED_MODEL_AGENTS)
        or ledger["summary"].get("network_calls") != len(REQUIRED_MODEL_AGENTS)
        or ledger["summary"].get("unknown_cost_call_count") != 0
        or ledger["summary"].get("actual_cost_complete") is not True
        or ledger["summary"].get("outcomes", {}).get("cache_hit", 0) != 0
    ):
        raise VerificationError("Dynamic flagship ledger is not the exact cold six-agent set")
    ledger_by_call = {
        item.get("call_id"): item
        for item in ledger["items"]
        if isinstance(item, dict) and item.get("call_id") in call_ids
    }
    if len(ledger_by_call) != len(REQUIRED_MODEL_AGENTS):
        raise VerificationError("Dynamic flagship ledger lacks six bound cold calls")
    ledger_response_ids: list[str] = []
    for agent_id in expected_agent_ids:
        agent = by_agent[agent_id]
        item = ledger_by_call[agent["call_id"]]
        expected_pairs = {
            "orchestration_id": orchestration_id,
            "agent_id": agent_id,
            "parent_call_id": agent.get("parent_call_id"),
            "delegation_id": agent.get("delegation_id"),
            "call_count": 1,
            "provider": "openrouter",
            "provider_endpoint": "https://openrouter.ai/api/v1/chat/completions",
            "model": REQUIRED_PRODUCTION_MODEL,
            "response_id": agent["response_id"],
            "response_model": agent["response_model"],
            "deterministic_fallback_applied": agent["deterministic_fallback_applied"],
        }
        for key, expected in expected_pairs.items():
            if item.get(key) != expected:
                raise VerificationError(
                    f"Dynamic flagship ledger {agent_id} {key} must be {expected!r}"
                )
        if item.get("outcome") != "succeeded":
            raise VerificationError(
                f"Dynamic flagship ledger {agent_id} must be a clean succeeded call"
            )
        _verify_successful_provider_provenance(
            item,
            f"Dynamic flagship ledger {agent_id}",
        )
        if item.get("usage_source") not in {"response", "generation_metadata"}:
            raise VerificationError(f"Dynamic flagship ledger {agent_id} lacks usage provenance")
        _verify_positive_usage(item, f"Dynamic flagship ledger {agent_id}")
        accepted_key = (
            "accepted_fact_count" if agent_id == "canonical_facts" else "accepted_item_count"
        )
        rejected_key = (
            "rejected_fact_count" if agent_id == "canonical_facts" else "rejected_item_count"
        )
        if (
            item.get(accepted_key) != agent["accepted_count"]
            or item.get(rejected_key) != agent["rejected_count"]
        ):
            raise VerificationError(
                f"Dynamic flagship ledger {agent_id} contribution counts are unbound"
            )
        if agent_id == "canonical_facts" and (
            item.get("source_reference_projection_fact_ids")
            != agent["source_reference_projection_fact_ids"]
            or item.get("source_reference_projection_count")
            != agent["source_reference_projection_count"]
        ):
            raise VerificationError(
                "Dynamic flagship ledger canonical source projection is unbound"
            )
        ledger_response_ids.append(item["response_id"])
    if len(set(ledger_response_ids)) != len(ledger_response_ids):
        raise VerificationError("Dynamic flagship ledger response IDs must be distinct")
    _verify_sanitized_evidence(
        {"flagship_run": run, "flagship_cold_model_ledger": ledger},
        "Dynamic flagship evidence",
    )
    return orchestration_id


def _verify_runtime_ledger_envelope(ledger: Mapping[str, Any], label: str) -> None:
    expected_fields = {
        "scope",
        "budget_scope",
        "ledger_persistence",
        "summary",
        "items",
    }
    if (
        set(ledger) != expected_fields
        or ledger.get("scope") != "global_budget_ledger"
        or ledger.get("budget_scope") != "instance_lifetime"
        or ledger.get("ledger_persistence") != "ephemeral_instance"
    ):
        raise VerificationError(f"{label} envelope is not exact")


def _bound_runtime_audit(
    run: Mapping[str, Any],
    label: str,
) -> dict[str, Any]:
    result = run.get("result")
    audit = _orchestration_audit(dict(run))
    audit_container = result.get("audit") if isinstance(result, Mapping) else None
    if (
        run.get("status") != "complete"
        or run.get("model_mode") != REQUIRED_PRODUCTION_MODE
        or run.get("model") != REQUIRED_PRODUCTION_MODEL
        or not isinstance(run.get("run_id"), str)
        or not run.get("run_id")
        or not isinstance(run.get("claim_id"), str)
        or not run.get("claim_id")
        or not isinstance(result, Mapping)
        or not isinstance(audit, dict)
        or run.get("agent_orchestration") != audit
        or result.get("agent_orchestration") != audit
        or not isinstance(audit_container, Mapping)
        or audit_container.get("agent_orchestration") != audit
    ):
        raise VerificationError(f"{label} run/audit binding is invalid")
    expected_audit = {
        "schema_version": REQUIRED_ORCHESTRATION_SCHEMA,
        "implementation": REQUIRED_AGENT_IMPLEMENTATION,
        "framework": REQUIRED_FRAMEWORK,
        "model": REQUIRED_PRODUCTION_MODEL,
        "authority_mode": REQUIRED_AUTHORITY_MODE,
        "model_assisted": True,
        "deterministic_safety_authority": True,
        "external_tracing": False,
        "prompt_storage": False,
        "raw_output_storage": False,
        "execution_topology": REQUIRED_EXECUTION_TOPOLOGY,
        "all_required_agents_contributed": True,
    }
    if any(audit.get(key) != value for key, value in expected_audit.items()):
        raise VerificationError(f"{label} orchestration architecture is invalid")
    orchestration_id = audit.get("orchestration_id")
    if not isinstance(orchestration_id, str) or not orchestration_id:
        raise VerificationError(f"{label} orchestration ID is absent")
    return audit


def _has_valid_parallel_agent_order(values: list[Any]) -> bool:
    """Allow only the declared document/process fan-out to finish in either order."""

    agent_ids = [
        value.get("agent_id") if isinstance(value, Mapping) else None
        for value in values
    ]
    required = [item["agent_id"] for item in REQUIRED_MODEL_AGENTS]
    swapped = [*required]
    swapped[2], swapped[3] = swapped[3], swapped[2]
    return agent_ids in (required, swapped)


def _verify_cold_warm_model_pair(
    *,
    cold_run: Mapping[str, Any],
    warm_run: Mapping[str, Any],
    cold_items: list[Any],
    warm_items: list[Any],
    label: str,
) -> tuple[list[dict[str, Any]], str, str]:
    """Verify one exact six-call network run and its six-call cache replay."""

    cold_audit = _bound_runtime_audit(cold_run, f"{label} cold")
    warm_audit = _bound_runtime_audit(warm_run, f"{label} warm")
    cold_orchestration_id = cold_audit["orchestration_id"]
    warm_orchestration_id = warm_audit["orchestration_id"]
    if (
        warm_run.get("claim_id") != cold_run.get("claim_id")
        or warm_run.get("run_id") == cold_run.get("run_id")
        or warm_orchestration_id == cold_orchestration_id
    ):
        raise VerificationError(f"{label} cold/warm run identity is invalid")

    expected_agent_ids = [item["agent_id"] for item in REQUIRED_MODEL_AGENTS]
    expected_agent_id_set = set(expected_agent_ids)
    cold_agents = cold_audit.get("agents")
    warm_agents = warm_audit.get("agents")

    def exact_agent_map(values: Any, surface: str) -> dict[str, Mapping[str, Any]]:
        if not isinstance(values, list) or len(values) != len(expected_agent_ids):
            raise VerificationError(f"{label} {surface} does not contain exactly six agents")
        keyed: dict[str, Mapping[str, Any]] = {}
        for value in values:
            if not isinstance(value, Mapping):
                raise VerificationError(f"{label} {surface} agent evidence is not an object")
            agent_id = value.get("agent_id")
            if (
                not isinstance(agent_id, str)
                or agent_id not in expected_agent_id_set
                or agent_id in keyed
            ):
                raise VerificationError(f"{label} {surface} agent membership is not exact")
            keyed[agent_id] = value
        if set(keyed) != expected_agent_id_set:
            raise VerificationError(f"{label} {surface} agent membership is not exact")
        if not _has_valid_parallel_agent_order(values):
            raise VerificationError(f"{label} {surface} violates the execution topology")
        return keyed

    cold_agents_by_id = exact_agent_map(cold_agents, "cold audit")
    warm_agents_by_id = exact_agent_map(warm_agents, "warm audit")
    cold_items_by_id = exact_agent_map(cold_items, "cold ledger")
    warm_items_by_id = exact_agent_map(warm_items, "warm ledger")

    audit_dynamic_fields = {"orchestration_id", "agents", "deterministic_gates"}
    cold_static_audit = {
        key: value for key, value in cold_audit.items() if key not in audit_dynamic_fields
    }
    warm_static_audit = {
        key: value for key, value in warm_audit.items() if key not in audit_dynamic_fields
    }
    if cold_static_audit != warm_static_audit:
        raise VerificationError(f"{label} warm replay changed cached orchestration output")
    if (
        cold_audit.get("guarded_fallback_count") != 0
        or warm_audit.get("guarded_fallback_count") != 0
    ):
        raise VerificationError(f"{label} must contain zero guarded fallbacks")

    agent_dynamic_fields = {
        "call_id",
        "call_count",
        "cache_hit",
        "outcome",
        "usage_source",
        "parent_call_id",
        "delegation_id",
        "input_artifact_hash",
        "output_artifact_hash",
    }
    ledger_dynamic_fields = {
        "call_id",
        "orchestration_id",
        "parent_call_id",
        "delegation_id",
        "call_count",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "estimated_cost_usd",
        "actual_cost_usd",
        "latency_ms",
        "outcome",
        "origin_call_id",
        "origin_usage",
        "origin_finish_reason",
        "usage_source",
        "created_at",
        "updated_at",
    }
    all_call_ids: list[str] = []
    cold_response_ids: list[str] = []
    cold_delegation_ids: list[str] = []
    warm_delegation_ids: list[str] = []
    expected_lineage: list[dict[str, Any]] = []
    cold_by_id: dict[str, Mapping[str, Any]] = cold_agents_by_id
    warm_by_id: dict[str, Mapping[str, Any]] = warm_agents_by_id
    for expected_agent in REQUIRED_MODEL_AGENTS:
        agent_id = expected_agent["agent_id"]
        cold_agent = cold_agents_by_id[agent_id]
        warm_agent = warm_agents_by_id[agent_id]
        cold_item = cold_items_by_id[agent_id]
        warm_item = warm_items_by_id[agent_id]

        cold_call_id = cold_agent.get("call_id")
        warm_call_id = warm_agent.get("call_id")
        cold_usage = cold_agent.get("usage")
        expected_cold_agent = {
            "role": expected_agent["role"],
            "actor_type": "nemotron_agent",
            "acceptance_scope": "pre_review_model_output",
            "model": REQUIRED_PRODUCTION_MODEL,
            "provider": "openrouter",
            "requested_model": REQUIRED_PRODUCTION_MODEL,
            "call_count": 1,
            "cache_hit": False,
        }
        if (
            any(cold_agent.get(key) != value for key, value in expected_cold_agent.items())
            or cold_agent.get("outcome") != "succeeded"
            or not isinstance(cold_call_id, str)
            or not cold_call_id
            or cold_agent.get("origin_call_id") != cold_call_id
            or cold_agent.get("usage_source") not in ACCEPTED_USAGE_SOURCES
            or cold_agent.get("finish_reason") != "stop"
            or not isinstance(cold_usage, dict)
            or set(cold_usage) != ORIGIN_USAGE_FIELDS
            or cold_usage.get("usage_source") != cold_agent.get("usage_source")
        ):
            raise VerificationError(f"{label} {agent_id} cold agent is invalid")
        _verify_successful_provider_provenance(cold_agent, f"{label} {agent_id} cold agent")
        _verify_bounded_origin_usage(cold_usage, f"{label} {agent_id} cold usage")
        accepted_ids = cold_agent.get("accepted_ids")
        accepted_count = cold_agent.get("accepted_count")
        rejected_count = cold_agent.get("rejected_count")
        if (
            not isinstance(accepted_ids, list)
            or not isinstance(accepted_count, int)
            or isinstance(accepted_count, bool)
            or accepted_count < 1
            or len(accepted_ids) != accepted_count
            or len(set(accepted_ids)) != len(accepted_ids)
            or any(not isinstance(value, str) or not value for value in accepted_ids)
            or not isinstance(rejected_count, int)
            or isinstance(rejected_count, bool)
            or rejected_count != 0
            or cold_agent.get("deterministic_fallback_applied") is not False
            or any(
                re.fullmatch(r"[0-9a-f]{64}", str(cold_agent.get(field, "")))
                is None
                for field in ("input_artifact_hash", "output_artifact_hash")
            )
        ):
            raise VerificationError(f"{label} {agent_id} cold contribution is invalid")
        if agent_id == "canonical_facts" and (
            cold_agent.get("source_reference_projection_fact_ids") != []
            or cold_agent.get("source_reference_projection_count") != 0
        ):
            raise VerificationError(
                f"{label} canonical facts must contain zero source projections"
            )

        cold_static_agent = {
            key: value
            for key, value in cold_agent.items()
            if key not in agent_dynamic_fields
        }
        warm_static_agent = {
            key: value
            for key, value in warm_agent.items()
            if key not in agent_dynamic_fields
        }
        expected_warm_agent = {
            "call_count": 0,
            "cache_hit": True,
            "outcome": "cache_hit",
            "usage_source": "cache",
            "origin_call_id": cold_call_id,
            "response_id": cold_agent.get("response_id"),
            "response_model": cold_agent.get("response_model"),
            "upstream_provider": cold_agent.get("upstream_provider"),
            "finish_reason": cold_agent.get("finish_reason"),
            "usage": cold_usage,
        }
        if (
            cold_static_agent != warm_static_agent
            or warm_agent.get("input_artifact_hash")
            != cold_agent.get("input_artifact_hash")
            or warm_agent.get("output_artifact_hash")
            != cold_agent.get("output_artifact_hash")
            or not isinstance(warm_call_id, str)
            or not warm_call_id
            or warm_call_id == cold_call_id
            or any(warm_agent.get(key) != value for key, value in expected_warm_agent.items())
        ):
            raise VerificationError(f"{label} {agent_id} warm agent lineage is invalid")
        _verify_successful_provider_provenance(warm_agent, f"{label} {agent_id} warm agent")

        cold_parent = None if agent_id == "canonical_facts" else (
            cold_by_id["canonical_facts"].get("call_id")
            if agent_id == "orchestrator_plan"
            else cold_by_id["orchestrator_plan"].get("call_id")
        )
        warm_parent = None if agent_id == "canonical_facts" else (
            warm_by_id["canonical_facts"].get("call_id")
            if agent_id == "orchestrator_plan"
            else warm_by_id["orchestrator_plan"].get("call_id")
        )
        cold_delegation = cold_agent.get("delegation_id")
        warm_delegation = warm_agent.get("delegation_id")
        if (
            cold_agent.get("parent_call_id") != cold_parent
            or warm_agent.get("parent_call_id") != warm_parent
            or (
                agent_id == "canonical_facts"
                and (cold_delegation is not None or warm_delegation is not None)
            )
            or (
                agent_id != "canonical_facts"
                and (
                    not isinstance(cold_delegation, str)
                    or not cold_delegation
                    or not isinstance(warm_delegation, str)
                    or not warm_delegation
                )
            )
        ):
            raise VerificationError(f"{label} {agent_id} delegation lineage is invalid")
        if agent_id != "canonical_facts":
            cold_delegation_ids.append(cold_delegation)
            warm_delegation_ids.append(warm_delegation)

        accepted_key = (
            "accepted_fact_ids" if agent_id == "canonical_facts" else "accepted_item_ids"
        )
        accepted_count_key = (
            "accepted_fact_count"
            if agent_id == "canonical_facts"
            else "accepted_item_count"
        )
        rejected_count_key = (
            "rejected_fact_count"
            if agent_id == "canonical_facts"
            else "rejected_item_count"
        )
        expected_cold_item = {
            "call_id": cold_call_id,
            "orchestration_id": cold_orchestration_id,
            "agent_id": agent_id,
            "parent_call_id": cold_parent,
            "delegation_id": cold_delegation,
            "provider": "openrouter",
            "provider_endpoint": "https://openrouter.ai/api/v1/chat/completions",
            "model": REQUIRED_PRODUCTION_MODEL,
            "call_count": 1,
            "outcome": cold_agent.get("outcome"),
            "response_id": cold_agent.get("response_id"),
            "response_model": cold_agent.get("response_model"),
            "upstream_provider": REQUIRED_UPSTREAM_PROVIDER,
            "finish_reason": "stop",
            "usage_source": cold_usage.get("usage_source"),
            "prompt_tokens": cold_usage.get("prompt_tokens"),
            "completion_tokens": cold_usage.get("completion_tokens"),
            "total_tokens": cold_usage.get("total_tokens"),
            "actual_cost_usd": cold_usage.get("actual_cost_usd"),
            accepted_key: accepted_ids,
            accepted_count_key: accepted_count,
            rejected_count_key: rejected_count,
            "deterministic_fallback_applied": cold_agent.get(
                "deterministic_fallback_applied"
            ),
        }
        if (
            any(cold_item.get(key) != value for key, value in expected_cold_item.items())
            or any(
                key in cold_item
                for key in ("origin_call_id", "origin_usage", "origin_finish_reason")
            )
            or re.fullmatch(r"[0-9a-f]{64}", str(cold_item.get("cache_key", "")))
            is None
        ):
            raise VerificationError(f"{label} {agent_id} cold ledger binding is invalid")
        _verify_successful_provider_provenance(cold_item, f"{label} {agent_id} cold ledger")
        _verify_positive_usage(cold_item, f"{label} {agent_id} cold ledger")

        cold_static_item = {
            key: value
            for key, value in cold_item.items()
            if key not in ledger_dynamic_fields
        }
        warm_static_item = {
            key: value
            for key, value in warm_item.items()
            if key not in ledger_dynamic_fields
        }
        origin_usage = {
            "prompt_tokens": cold_item.get("prompt_tokens"),
            "completion_tokens": cold_item.get("completion_tokens"),
            "total_tokens": cold_item.get("total_tokens"),
            "actual_cost_usd": cold_item.get("actual_cost_usd"),
            "usage_source": cold_item.get("usage_source"),
        }
        expected_warm_item = {
            "call_id": warm_call_id,
            "orchestration_id": warm_orchestration_id,
            "agent_id": agent_id,
            "parent_call_id": warm_parent,
            "delegation_id": warm_delegation,
            "call_count": 0,
            "estimated_cost_usd": 0,
            "actual_cost_usd": None,
            "outcome": "cache_hit",
            "origin_call_id": cold_call_id,
            "response_id": cold_item.get("response_id"),
            "response_model": cold_item.get("response_model"),
            "upstream_provider": REQUIRED_UPSTREAM_PROVIDER,
            "origin_usage": origin_usage,
            "origin_finish_reason": cold_item.get("finish_reason"),
            "usage_source": "cache",
            "finish_reason": cold_item.get("finish_reason"),
        }
        if (
            cold_static_item != warm_static_item
            or any(warm_item.get(key) != value for key, value in expected_warm_item.items())
            or any(
                key in warm_item
                for key in ("prompt_tokens", "completion_tokens", "total_tokens", "latency_ms")
            )
        ):
            raise VerificationError(f"{label} {agent_id} warm ledger lineage is invalid")

        all_call_ids.extend((cold_call_id, warm_call_id))
        cold_response_ids.append(cold_agent["response_id"])
        expected_lineage.append(
            {
                "agent_id": agent_id,
                "cold_call_id": cold_call_id,
                "warm_call_id": warm_call_id,
                "response_id": cold_agent.get("response_id"),
                "response_model": cold_agent.get("response_model"),
            }
        )

    if (
        len(set(all_call_ids)) != len(all_call_ids)
        or len(set(cold_response_ids)) != len(cold_response_ids)
        or len(set(cold_delegation_ids)) != len(cold_delegation_ids)
        or len(set(warm_delegation_ids)) != len(warm_delegation_ids)
    ):
        raise VerificationError(f"{label} call, response, or delegation IDs are not distinct")

    gate_source_agents = {
        "deterministic_process_gate": "process_decision_mapping",
        "deterministic_evidence_gate": "evidence_checklist",
        "whole_playbook_gate": "final_claim_brief_audit",
    }
    gate_roles = {item["gate_id"]: item["role"] for item in REQUIRED_DETERMINISTIC_GATES}
    for audit, agents_by_id, surface in (
        (cold_audit, cold_by_id, "cold"),
        (warm_audit, warm_by_id, "warm"),
    ):
        gates = audit.get("deterministic_gates")
        expected_gate_ids = [item["gate_id"] for item in REQUIRED_DETERMINISTIC_GATES]
        if (
            not isinstance(gates, list)
            or [gate.get("agent_id") if isinstance(gate, Mapping) else None for gate in gates]
            != expected_gate_ids
        ):
            raise VerificationError(f"{label} {surface} deterministic gates are not exact")
        for gate in gates:
            gate_id = gate["agent_id"]
            source_agent_id = gate_source_agents[gate_id]
            source_agent = agents_by_id[source_agent_id]
            expected_gate = {
                "role": gate_roles[gate_id],
                "actor_type": "deterministic_gate",
                "model": None,
                "outcome": "passed",
                "receipt_type": "accepted_artifact",
                "acceptance_scope": "pre_review_model_output",
                "source_agent_id": source_agent_id,
                "source_call_id": source_agent.get("call_id"),
                "delegation_id": source_agent.get("delegation_id"),
                "accepted_ids": source_agent.get("accepted_ids"),
                "accepted_count": source_agent.get("accepted_count"),
            }
            if gate_id == "whole_playbook_gate":
                expected_gate["output_projection_contract"] = (
                    WHOLE_PLAYBOOK_OUTPUT_PROJECTION_CONTRACT
                )
            if (
                any(gate.get(key) != value for key, value in expected_gate.items())
                or any(
                    re.fullmatch(r"[0-9a-f]{64}", str(gate.get(field, "")))
                    is None
                    for field in ("input_artifact_hash", "output_artifact_hash")
                )
            ):
                raise VerificationError(f"{label} {surface} {gate_id} binding is invalid")

    return expected_lineage, cold_orchestration_id, warm_orchestration_id


def _verify_deterministic_learning_run(
    run: Mapping[str, Any],
    *,
    knowledge_mode: str,
    label: str,
) -> None:
    """Require a held-out comparison run with no model-execution surface."""

    result = run.get("result")
    result_audit = result.get("audit") if isinstance(result, Mapping) else None
    next_action = result.get("next_action") if isinstance(result, Mapping) else None
    expected_orchestration = {
        "executed": False,
        "authority_mode": DETERMINISTIC_REFERENCE_MODE,
        "model": None,
        "external_tracing": False,
        "deterministic_safety_authority": True,
    }
    expected_canonicalization = {
        "implementation": "deterministic_reference_oracle",
        "model": None,
        "provider": None,
        "mode": DETERMINISTIC_REFERENCE_MODE,
    }
    if (
        run.get("status") != "complete"
        or run.get("claim_id") != "DEMO-MOULD-002"
        or run.get("knowledge_mode") != knowledge_mode
        or run.get("model_mode") != DETERMINISTIC_REFERENCE_MODE
        or run.get("model") is not None
        or run.get("profile") != DETERMINISTIC_REFERENCE_PROFILE
        or not isinstance(run.get("run_id"), str)
        or not run.get("run_id")
        or not isinstance(result, Mapping)
        or not isinstance(result_audit, Mapping)
        or not isinstance(next_action, Mapping)
        or run.get("agent_orchestration") != expected_orchestration
        or result.get("agent_orchestration") != expected_orchestration
        or result_audit.get("agent_orchestration") != expected_orchestration
        or result_audit.get("profile") != DETERMINISTIC_REFERENCE_PROFILE
        or result_audit.get("authority_mode") != DETERMINISTIC_REFERENCE_MODE
        or result_audit.get("canonicalization") != expected_canonicalization
        or next_action.get("agent_brief_contribution") is not None
    ):
        raise VerificationError(
            f"{label} is not an exact deterministic-reference comparison run"
        )

    events = run.get("events")
    if not isinstance(events, list):
        raise VerificationError(f"{label} deterministic event stream is absent")
    forbidden_activity_fields = {
        "agents",
        "deterministic_gates",
        "execution_topology",
        "specialist_artifacts",
        "final_claim_brief",
        "agent_contribution",
        "call_id",
        "response_id",
        "response_model",
        "requested_model",
        "generation_model",
        "upstream_provider",
        "provider_endpoint",
        "cache_hit",
        "call_count",
        "origin_call_id",
        "origin_usage",
        "origin_finish_reason",
        "usage_source",
        "orchestration_id",
        "delegation_id",
        "parent_call_id",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "estimated_cost_usd",
        "actual_cost_usd",
        "latency_ms",
    }
    activity_paths: list[str] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                if key in forbidden_activity_fields:
                    activity_paths.append(child_path)
                elif key in {"model", "provider"} and child is not None:
                    activity_paths.append(child_path)
                elif key == "actor_type" and child == "nemotron_agent":
                    activity_paths.append(child_path)
                elif key == "implementation" and child == REQUIRED_AGENT_IMPLEMENTATION:
                    activity_paths.append(child_path)
                visit(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(run, label)
    if activity_paths:
        raise VerificationError(f"{label} contains model execution activity")
    _verify_sanitized_evidence({"run": run}, label)


def _verify_warm_cache_lineage(
    *,
    flagship_run: Mapping[str, Any],
    isolation_run: Mapping[str, Any],
    baseline_run: Mapping[str, Any],
    later_run: Mapping[str, Any],
    cold_ledger: Mapping[str, Any],
    isolation_ledger: Mapping[str, Any],
    final_ledger: Mapping[str, Any],
    lineage_receipt: Mapping[str, Any],
) -> None:
    """Bind one cold/warm flagship pair and deterministic held-out replay."""

    for ledger, label in (
        (cold_ledger, "Dynamic flagship ledger"),
        (isolation_ledger, "Dynamic isolation ledger"),
        (final_ledger, "Dynamic final ledger"),
    ):
        _verify_runtime_ledger_envelope(ledger, label)
    cold_items = cold_ledger.get("items")
    isolation_items = isolation_ledger.get("items")
    final_items = final_ledger.get("items")
    if (
        not isinstance(cold_items, list)
        or not isinstance(isolation_items, list)
        or not isinstance(final_items, list)
        or len(cold_items) != 6
        or len(isolation_items) != 12
        or len(final_items) != 12
        or isolation_items[:6] != cold_items
        or final_items != isolation_items
    ):
        raise VerificationError(
            "Dynamic model ledgers are not exact immutable ordered 6/12/12 snapshots"
        )

    flagship_lineage, flagship_cold_orch, flagship_warm_orch = (
        _verify_cold_warm_model_pair(
            cold_run=flagship_run,
            warm_run=isolation_run,
            cold_items=cold_items,
            warm_items=isolation_items[6:12],
            label="Dynamic flagship cache",
        )
    )
    _verify_deterministic_learning_run(
        baseline_run,
        knowledge_mode="baseline",
        label="Dynamic later-claim baseline",
    )
    _verify_deterministic_learning_run(
        later_run,
        knowledge_mode="current",
        label="Dynamic later-claim current",
    )
    if flagship_cold_orch == flagship_warm_orch:
        raise VerificationError("Dynamic flagship orchestration IDs are not distinct")

    cold_summary = cold_ledger.get("summary")
    isolation_summary = isolation_ledger.get("summary")
    final_summary = final_ledger.get("summary")
    if (
        not all(isinstance(value, Mapping) for value in (
            cold_summary,
            isolation_summary,
            final_summary,
        ))
        or cold_summary.get("records") != 6
        or cold_summary.get("network_calls") != 6
        or cold_summary.get("outcomes", {}).get("cache_hit", 0) != 0
        or isolation_summary.get("records") != 12
        or isolation_summary.get("network_calls") != 6
        or isolation_summary.get("outcomes", {}).get("cache_hit") != 6
        or final_summary != isolation_summary
        or final_summary.get("records") != 12
        or final_summary.get("network_calls") != 6
        or final_summary.get("outcomes", {}).get("cache_hit") != 6
        or any(
            summary.get("unknown_cost_call_count") != 0
            or summary.get("actual_cost_complete") is not True
            for summary in (cold_summary, isolation_summary, final_summary)
        )
    ):
        raise VerificationError(
            "Dynamic model-ledger summaries do not prove exact 6/12/12 use"
        )

    expected_lineage_fields = {
        "contract",
        "requested_model",
        "exact_response_models",
        "framework",
        "cold_orchestration_id",
        "warm_orchestration_id",
        "cold_run_surface",
        "warm_run_surface",
        "cold_guarded_fallback_count",
        "warm_guarded_fallback_count",
        "lineage",
        "provider_calls_during_isolation_replay",
    }
    exact_response_models = lineage_receipt.get("exact_response_models")
    lineage = lineage_receipt.get("lineage")
    expected_agent_ids = [item["agent_id"] for item in REQUIRED_MODEL_AGENTS]
    expected_agent_id_set = set(expected_agent_ids)
    lineage_by_agent: dict[str, Mapping[str, Any]] = {}
    if (
        isinstance(lineage, list)
        and len(lineage) == len(expected_agent_ids)
        and _has_valid_parallel_agent_order(lineage)
    ):
        for item in lineage:
            if not isinstance(item, Mapping):
                lineage_by_agent = {}
                break
            agent_id = item.get("agent_id")
            if (
                not isinstance(agent_id, str)
                or agent_id not in expected_agent_id_set
                or agent_id in lineage_by_agent
            ):
                lineage_by_agent = {}
                break
            lineage_by_agent[agent_id] = item
    normalized_lineage = (
        [lineage_by_agent[agent_id] for agent_id in expected_agent_ids]
        if set(lineage_by_agent) == expected_agent_id_set
        else None
    )
    if (
        set(lineage_receipt) != expected_lineage_fields
        or lineage_receipt.get("contract")
        != "casepath.flagship-cache-lineage/1.0.0"
        or lineage_receipt.get("requested_model") != REQUIRED_PRODUCTION_MODEL
        or not isinstance(exact_response_models, list)
        or len(exact_response_models) != len(ACCEPTED_PRODUCTION_RESPONSE_MODELS)
        or set(exact_response_models) != ACCEPTED_PRODUCTION_RESPONSE_MODELS
        or lineage_receipt.get("framework") != REQUIRED_FRAMEWORK
        or lineage_receipt.get("cold_orchestration_id") != flagship_cold_orch
        or lineage_receipt.get("warm_orchestration_id") != flagship_warm_orch
        or lineage_receipt.get("cold_run_surface") != "visible_browser_flagship"
        or lineage_receipt.get("warm_run_surface")
        != "isolated_session_cache_replay"
        or lineage_receipt.get("cold_guarded_fallback_count")
        != flagship_run["agent_orchestration"].get("guarded_fallback_count")
        or lineage_receipt.get("warm_guarded_fallback_count")
        != isolation_run["agent_orchestration"].get("guarded_fallback_count")
        or lineage_receipt.get("provider_calls_during_isolation_replay") != 0
        or normalized_lineage != flagship_lineage
    ):
        raise VerificationError("Dynamic flagship cache-lineage receipt is invalid")


def _verify_dynamic_report_integrity(
    report: Mapping[str, Any],
    *,
    flagship_run: Mapping[str, Any],
    baseline_run: Mapping[str, Any],
    later_run: Mapping[str, Any],
) -> None:
    checks = report.get("checks")
    failures = report.get("failures")
    required_visible_replay_checks = {
        "Eight returned facts each show their exact source first, then the accepted fact, with run-bound replay lineage",
        "The visible graph replays accepted facts and checked law without inventing new source reads, then clears its plan before each node",
    }
    check_names = (
        {
            check.get("name")
            for check in checks
            if isinstance(check, Mapping)
        }
        if isinstance(checks, list)
        else set()
    )
    if (
        not isinstance(checks, list)
        or not checks
        or report.get("passed") != len(checks)
        or report.get("failed") != 0
        or any(
            not isinstance(check, Mapping)
            or set(check) != {"name", "passed", "detail"}
            or not isinstance(check.get("name"), str)
            or not check.get("name")
            or check.get("passed") is not True
            or not isinstance(check.get("detail"), str)
            for check in checks
        )
        or len({check["name"] for check in checks}) != len(checks)
        or not isinstance(failures, Mapping)
        or set(failures) != {"console", "page", "request", "cleanup"}
        or any(failures.get(key) != [] for key in failures)
        or report.get("runIds")
        != [
            flagship_run.get("run_id"),
            baseline_run.get("run_id"),
            later_run.get("run_id"),
        ]
        or not required_visible_replay_checks.issubset(check_names)
    ):
        raise VerificationError("Dynamic QA report integrity or run lineage is invalid")


def _expected_public_agentic_runtime() -> dict[str, Any]:
    return {
        "profile": REQUIRED_RUNTIME_PROFILE,
        "compiled_profile": REQUIRED_RUNTIME_PROFILE,
        "configured_profile": REQUIRED_RUNTIME_PROFILE,
        "profile_aligned": True,
        "trace_policy_aligned": True,
        "execution_mode": "nemotron_multi_agent",
        "authority_mode": REQUIRED_AUTHORITY_MODE,
        "implementation": REQUIRED_AGENT_IMPLEMENTATION,
        "schema": REQUIRED_ORCHESTRATION_SCHEMA,
        "framework": REQUIRED_FRAMEWORK,
        "required_agent_ids": [item["agent_id"] for item in REQUIRED_MODEL_AGENTS],
        "deterministic_gate_ids": [
            item["gate_id"] for item in REQUIRED_DETERMINISTIC_GATES
        ],
        "safety": {
            "deterministic_contract_authority": True,
            "external_tracing": False,
            "prompt_storage": False,
            "raw_output_storage": False,
            "model_fallback": False,
            "automatic_inference_retry": False,
            "provider_max_in_flight": 1,
            "ledger_persistence": "ephemeral_instance",
            "budget_scope": "instance_lifetime",
            "cache_scope": "instance_lifetime",
            "external_key_hard_limit_guard": "configured",
            "credential_configured": True,
            "provider_routing": {
                "endpoint_tag": REQUIRED_PROVIDER_ENDPOINT_TAG,
                "expected_upstream_provider": REQUIRED_UPSTREAM_PROVIDER,
                "allow_fallbacks": False,
                "require_parameters": True,
                "data_collection": "deny",
            },
        },
    }


def _verify_dynamic_identity_bundle(
    *,
    release: Mapping[str, Any],
    report: Mapping[str, Any],
    evidence_manifest: Mapping[str, Any],
    files_by_path: Mapping[str, Mapping[str, Any]],
    deployment_identity: Any,
    release_contract: Any,
    readiness: Any,
    runtime_versions: Any,
    source_commit: str,
) -> None:
    deployment = report.get("deployment")
    expected_runtime = _expected_public_agentic_runtime()
    if (
        not isinstance(deployment, Mapping)
        or deployment_identity != deployment
        or release_contract != release
        or not isinstance(readiness, Mapping)
        or not isinstance(runtime_versions, Mapping)
        or runtime_versions != report.get("runtime")
        or runtime_versions != evidence_manifest.get("runtime")
    ):
        raise VerificationError("Dynamic QA retained identity bundle is not cross-bound")

    frontend = deployment.get("frontend")
    api = deployment.get("api")
    qa = deployment.get("qa")
    services = release.get("services")
    components = release.get("components")
    release_record = files_by_path.get("release-contract.json")
    if not all(
        isinstance(value, Mapping)
        for value in (frontend, api, qa, services, components, release_record)
    ):
        raise VerificationError("Dynamic QA deployment identity is incomplete")
    frontend_component = components.get("frontend")
    api_component = components.get("api")
    pipeline_component = components.get("pipeline")
    if not all(
        isinstance(value, Mapping)
        for value in (frontend_component, api_component, pipeline_component)
    ):
        raise VerificationError("Dynamic QA release component identity is incomplete")

    frontend_expected = {
        "contract": "casepath.deployment-identity/1.0.0",
        "component": "frontend",
        "component_contract": frontend_component.get("contract"),
        "component_version": frontend_component.get("version"),
        "release_id": release.get("release_id"),
        "source_commit": source_commit,
        "source_commit_source": "RENDER_GIT_COMMIT",
        "alignment_eligible": True,
        "service": services.get("frontend"),
        "release_contract_sha256": release_record.get("sha256"),
    }
    api_expected = {
        "status": "ok",
        "release_id": release.get("release_id"),
        "release": api_component.get("version"),
        "pipeline_release": pipeline_component.get("version"),
        "source_commit": source_commit,
        "source_commit_aligned": True,
        "source_commit_conflict": False,
        "model_mode": REQUIRED_PRODUCTION_MODE,
        "model": REQUIRED_PRODUCTION_MODEL,
        "configured_model_identity": REQUIRED_PRODUCTION_MODEL,
        "model_provider": "openrouter",
        "runtime_profile": REQUIRED_RUNTIME_PROFILE,
        "agentic_runtime": expected_runtime,
        "generated_data_only": True,
        "real_claims_approved": False,
    }
    if (
        any(frontend.get(key) != value for key, value in frontend_expected.items())
        or any(api.get(key) != value for key, value in api_expected.items())
        or qa
        != {
            "release_id": release.get("release_id"),
            "source_commit": source_commit,
        }
        or report.get("release") != frontend_component.get("version")
        or report.get("baseUrl") != services.get("frontend")
        or report.get("apiUrl") != services.get("api")
    ):
        raise VerificationError("Dynamic QA deployment identity contradicts the release")

    expected_session_isolation = {
        "enabled": True,
        "header": "X-CasePath-Session",
        "format": "8-128 characters; ASCII letters, digits, dot, underscore, colon, or hyphen",
        "state_scope": "caller_session",
        "model_ledger_scope": "global",
        "session_reset_scope": "caller_session_only",
    }
    if api.get("session_isolation") != expected_session_isolation:
        raise VerificationError("Dynamic QA API session isolation is not exact")

    expected_readiness_fields = {
        "status",
        "database",
        "claims",
        "artifacts",
        "active_playbook",
        "model_budget",
        "agentic_runtime",
    }
    budget = readiness.get("model_budget")
    expected_budget = {
        "cumulative_usd_cap": 25,
        "budget_scope": "instance_lifetime",
        "ledger_persistence": "ephemeral_instance",
        "external_key_hard_limit_guard": "configured",
        "credential_configured": True,
        "records": 0,
        "network_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "actual_cost_usd": 0,
        "actual_cost_complete": True,
        "unknown_cost_call_count": 0,
        "outcomes": {},
    }
    if (
        set(readiness) != expected_readiness_fields
        or readiness.get("status") != "ready"
        or readiness.get("database") != "sqlite-demo"
        or readiness.get("claims") != len(release.get("claims", {}))
        or not isinstance(readiness.get("artifacts"), int)
        or isinstance(readiness.get("artifacts"), bool)
        or readiness.get("artifacts", 0) <= 0
        or readiness.get("active_playbook") != "mould-playbook-v3"
        or budget != expected_budget
        or readiness.get("agentic_runtime") != expected_runtime
    ):
        raise VerificationError("Dynamic QA readiness receipt is not an exact zero-ledger start")

    if (
        set(runtime_versions) != {"node", "playwright", "chromium"}
        or runtime_versions.get("node") != "v24.14.1"
        or runtime_versions.get("playwright") != "1.55.0"
        or re.fullmatch(r"[0-9]+(?:\.[0-9]+){0,3}", str(runtime_versions.get("chromium", "")))
        is None
    ):
        raise VerificationError("Dynamic QA runtime versions are not pinned and bound")


def verify_dynamic_runtime_acceptance(
    release: dict[str, Any],
    report: dict[str, Any],
    evidence_manifest: dict[str, Any],
    retained_evidence: dict[str, dict[str, Any]],
    *,
    evidence_manifest_bytes: bytes,
) -> dict[str, Any]:
    """Decide runtime acceptance from one same-commit QA artifact pair."""

    verify_static_runtime_acceptance_contract(release)
    criteria = release["truth"]["production_runtime_acceptance"]
    dynamic = criteria["dynamic_evidence"]
    if report.get("status") != dynamic["required_report_status"]:
        raise VerificationError("Dynamic QA report did not pass")
    if report.get("release_id") != release.get("release_id"):
        raise VerificationError("Dynamic QA report release ID does not match")
    if report.get("failed") != 0:
        raise VerificationError("Dynamic QA report contains failures")
    deployment = report.get("deployment")
    if not isinstance(deployment, dict):
        raise VerificationError("Dynamic QA report lacks deployment identity")
    source_commits: list[str] = []
    for component in ("frontend", "api", "qa"):
        identity = deployment.get(component)
        if not isinstance(identity, dict):
            raise VerificationError(f"Dynamic QA report lacks {component} identity")
        if identity.get("release_id") != release.get("release_id"):
            raise VerificationError(f"Dynamic QA {component} release ID does not match")
        source_commit = identity.get("source_commit")
        if not isinstance(source_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", source_commit):
            raise VerificationError(
                f"Dynamic QA {component} source commit is absent, unknown, or malformed"
            )
        source_commits.append(source_commit)
    if len(set(source_commits)) != 1:
        raise VerificationError("Dynamic QA frontend, API, and QA commits are not aligned")
    source_commit = source_commits[0]

    if evidence_manifest.get("contract") != dynamic["evidence_manifest_contract"]:
        raise VerificationError("Dynamic QA evidence manifest contract is unsupported")
    if evidence_manifest.get("release_id") != release.get("release_id"):
        raise VerificationError("Dynamic QA evidence manifest release ID does not match")
    if evidence_manifest.get("source_commit") != source_commit:
        raise VerificationError("Dynamic QA evidence manifest is not from the aligned commit")
    if evidence_manifest.get("retained_before_session_reset") is not True:
        raise VerificationError("Dynamic QA evidence was not retained before reset")
    report_evidence = report.get("evidence")
    if not isinstance(report_evidence, dict):
        raise VerificationError("Dynamic QA report lacks its evidence binding")
    if report_evidence.get("contract") != "casepath.qa-evidence/1.0.0":
        raise VerificationError("Dynamic QA report evidence contract is unsupported")
    if report_evidence.get("retained_before_session_reset") is not True:
        raise VerificationError("Dynamic QA report evidence was not retained before reset")
    if evidence_manifest.get("gate") != report_evidence.get("gate"):
        raise VerificationError("Dynamic QA gate identity differs between report and manifest")
    if evidence_manifest.get("runtime") != report.get("runtime"):
        raise VerificationError("Dynamic QA runtime differs between report and manifest")
    manifest_binding = report_evidence.get("manifest")
    if not isinstance(manifest_binding, dict) or manifest_binding.get("path") != dynamic[
        "evidence_manifest_path"
    ]:
        raise VerificationError("Dynamic QA report does not bind evidence-manifest.json")
    expected_hash = hashlib.sha256(evidence_manifest_bytes).hexdigest()
    if manifest_binding.get("sha256") != expected_hash:
        raise VerificationError("Dynamic QA report evidence-manifest hash does not match")
    if manifest_binding.get("bytes") != len(evidence_manifest_bytes):
        raise VerificationError("Dynamic QA report evidence-manifest size does not match")

    files = evidence_manifest.get("files")
    if not isinstance(files, list):
        raise VerificationError("Dynamic QA evidence manifest files must be a list")
    if report_evidence.get("files") != files:
        raise VerificationError("Dynamic QA report and manifest file inventories differ")
    files_by_path: dict[str, dict[str, Any]] = {}
    for record in files:
        path_text = record.get("path") if isinstance(record, dict) else None
        if not isinstance(path_text, str) or not path_text or path_text in files_by_path:
            raise VerificationError("Dynamic QA evidence paths must be present and distinct")
        if not re.fullmatch(r"[0-9a-f]{64}", str(record.get("sha256", ""))):
            raise VerificationError(f"Dynamic QA evidence {path_text} lacks a SHA-256")
        if not isinstance(record.get("bytes"), int) or record["bytes"] <= 0:
            raise VerificationError(f"Dynamic QA evidence {path_text} is empty")
        files_by_path[path_text] = record
    if set(files_by_path) != REQUIRED_QA_EVIDENCE_FILES:
        raise VerificationError("Dynamic QA evidence manifest inventory is not exact")
    if set(retained_evidence) != set(REQUIRED_QA_JSON_EVIDENCE_FILES):
        raise VerificationError("Dynamic QA retained JSON evidence inventory is not exact")
    media_contract = evidence_manifest.get("retained_media_contract")
    if not isinstance(media_contract, dict):
        raise VerificationError("Dynamic QA retained-media contract is incomplete")
    expected_media_fields = {"json", "screenshots", "video", "missing", "empty"}
    if set(media_contract) != expected_media_fields:
        raise VerificationError("Dynamic QA retained-media contract fields are not exact")
    if media_contract.get("json") != list(REQUIRED_QA_JSON_EVIDENCE_FILES):
        raise VerificationError("Dynamic QA retained JSON inventory is not exact")
    if media_contract.get("screenshots") != list(
        REQUIRED_QA_SCREENSHOT_EVIDENCE_FILES
    ):
        raise VerificationError("Dynamic QA retained screenshot inventory is not exact")
    if media_contract.get("video") != REQUIRED_QA_VIDEO_EVIDENCE_FILE:
        raise VerificationError("Dynamic QA retained video inventory is not exact")
    if media_contract.get("missing") != [] or media_contract.get("empty") != []:
        raise VerificationError("Dynamic QA retained-media contract is incomplete")

    flagship_run = retained_evidence.get("flagship-run.json")
    flagship_ledger = retained_evidence.get("flagship-cold-model-ledger.json")
    if not isinstance(flagship_run, dict) or not isinstance(flagship_ledger, dict):
        raise VerificationError("Dynamic QA pair lacks retained flagship run or cold ledger")
    orchestration_id = _verify_cold_flagship_evidence(flagship_run, flagship_ledger)
    learning_files = {
        name: retained_evidence.get(name)
        for name in (
            "demo-review.json",
            "post-review-run.json",
            "later-baseline-run.json",
            "later-after-memory-run.json",
            "learning-proof.json",
        )
    }
    if any(not isinstance(value, dict) for value in learning_files.values()):
        raise VerificationError(
            "Dynamic QA pair lacks the retained review and learning replay bundle"
        )
    _verify_learning_replay_contract(
        demo_review=learning_files["demo-review.json"],
        post_review_run=learning_files["post-review-run.json"],
        baseline_run=learning_files["later-baseline-run.json"],
        later_run=learning_files["later-after-memory-run.json"],
        proof=learning_files["learning-proof.json"],
    )
    baseline_run = learning_files["later-baseline-run.json"]
    later_run = learning_files["later-after-memory-run.json"]
    _verify_dynamic_report_integrity(
        report,
        flagship_run=flagship_run,
        baseline_run=baseline_run,
        later_run=later_run,
    )
    deployment_identity = retained_evidence.get("deployment-identity.json")
    release_contract = retained_evidence.get("release-contract.json")
    readiness = retained_evidence.get("readiness-receipt.json")
    runtime_versions = retained_evidence.get("runtime-versions.json")
    isolation_run = retained_evidence.get("isolation-run.json")
    isolation_ledger = retained_evidence.get("isolation-model-ledger.json")
    final_ledger = retained_evidence.get("model-ledger.json")
    lineage_receipt = retained_evidence.get("flagship-cache-lineage.json")
    if not all(
            isinstance(value, Mapping)
            for value in (
                isolation_run,
                isolation_ledger,
                final_ledger,
                lineage_receipt,
            )
    ):
        raise VerificationError("Dynamic QA retained identity/readiness bundle is invalid")
    _verify_dynamic_identity_bundle(
        release=release,
        report=report,
        evidence_manifest=evidence_manifest,
        files_by_path=files_by_path,
        deployment_identity=deployment_identity,
        release_contract=release_contract,
        readiness=readiness,
        runtime_versions=runtime_versions,
        source_commit=source_commit,
    )
    _verify_public_model_ledger(isolation_ledger, "Dynamic isolation ledger")
    _verify_public_model_ledger(final_ledger, "Dynamic final model ledger")
    _verify_warm_cache_lineage(
        flagship_run=flagship_run,
        isolation_run=isolation_run,
        baseline_run=baseline_run,
        later_run=later_run,
        cold_ledger=flagship_ledger,
        isolation_ledger=isolation_ledger,
        final_ledger=final_ledger,
        lineage_receipt=lineage_receipt,
    )
    _verify_sanitized_evidence(
        {"retained_learning_evidence": learning_files},
        "Dynamic retained learning evidence",
    )
    _verify_sanitized_evidence(
        {"retained_runtime_evidence": retained_evidence},
        "Dynamic retained runtime evidence",
    )
    return {
        "release_id": release["release_id"],
        "source_commit": source_commit,
        "orchestration_id": orchestration_id,
        "model_agents": len(REQUIRED_MODEL_AGENTS),
        "deterministic_gates": len(REQUIRED_DETERMINISTIC_GATES),
        "status": "passed",
        "verdict_source": RUNTIME_VERDICT_AUTHORITY,
    }


def _load_dynamic_runtime_evidence_paths(
    report_path: Path,
    evidence_manifest_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]], bytes]:
    """Load one hash-verified retained QA output directory."""

    if report_path.name != QA_REPORT_PATH:
        raise VerificationError(f"Dynamic QA report must be named {QA_REPORT_PATH}")
    if evidence_manifest_path.name != QA_EVIDENCE_MANIFEST_PATH:
        raise VerificationError(
            f"Dynamic QA evidence manifest must be named {QA_EVIDENCE_MANIFEST_PATH}"
        )
    if report_path.parent.resolve() != evidence_manifest_path.parent.resolve():
        raise VerificationError("Dynamic QA report and evidence manifest must share a directory")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        manifest_bytes = evidence_manifest_path.read_bytes()
        evidence_manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"Cannot read dynamic QA evidence: {exc}") from exc
    if not isinstance(report, dict) or not isinstance(evidence_manifest, dict):
        raise VerificationError("Dynamic QA report and evidence manifest must be objects")

    evidence_root = evidence_manifest_path.parent
    files = evidence_manifest.get("files")
    if not isinstance(files, list):
        raise VerificationError("Dynamic QA evidence manifest files must be a list")
    seen_paths: set[str] = set()
    for record in files:
        if (
            not isinstance(record, dict)
            or set(record) != {"path", "sha256", "bytes"}
            or not isinstance(record.get("path"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", str(record.get("sha256", "")))
            or not isinstance(record.get("bytes"), int)
            or isinstance(record.get("bytes"), bool)
            or record["bytes"] <= 0
        ):
            raise VerificationError("Dynamic QA evidence manifest file record is invalid")
        if record["path"] in seen_paths:
            raise VerificationError(
                f"Duplicate dynamic QA evidence path: {record['path']}"
            )
        seen_paths.add(record["path"])
        relative_path = Path(record["path"])
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise VerificationError(f"Unsafe dynamic QA evidence path: {record['path']!r}")
        artifact_path = evidence_root / relative_path
        if not artifact_path.is_file():
            raise VerificationError(f"Missing dynamic QA evidence file: {record['path']}")
        if sha256_file(artifact_path) != record.get("sha256"):
            raise VerificationError(f"Dynamic QA evidence hash mismatch: {record['path']}")
        if artifact_path.stat().st_size != record.get("bytes"):
            raise VerificationError(f"Dynamic QA evidence size mismatch: {record['path']}")

    for filename in seen_paths & set(REQUIRED_QA_SCREENSHOT_EVIDENCE_FILES):
        if not (evidence_root / filename).read_bytes().startswith(
            b"\x89PNG\r\n\x1a\n"
        ):
            raise VerificationError(f"Dynamic QA evidence is not PNG: {filename}")
    if (
        REQUIRED_QA_VIDEO_EVIDENCE_FILE in seen_paths
        and not (evidence_root / REQUIRED_QA_VIDEO_EVIDENCE_FILE)
        .read_bytes()
        .startswith(b"\x1aE\xdf\xa3")
    ):
        raise VerificationError("Dynamic QA evidence video is not WebM")

    retained_evidence = {}
    for filename in sorted(seen_paths & set(REQUIRED_QA_JSON_EVIDENCE_FILES)):
        try:
            value = json.loads((evidence_root / filename).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VerificationError(f"Cannot read retained {filename}: {exc}") from exc
        if not isinstance(value, dict):
            raise VerificationError(f"Retained {filename} must be an object")
        retained_evidence[filename] = value
    return report, evidence_manifest, retained_evidence, manifest_bytes


def verify_dynamic_causal_evidence_paths(
    report_path: Path,
    evidence_manifest_path: Path,
) -> dict[str, Any]:
    """Verify deterministic causal DTOs before any production provider call."""

    report, evidence_manifest, retained_evidence, manifest_bytes = (
        _load_dynamic_runtime_evidence_paths(report_path, evidence_manifest_path)
    )
    if report.get("status") != "passed" or report.get("failed") != 0:
        raise VerificationError("Dynamic causal QA report did not pass")
    report_evidence = report.get("evidence")
    files = evidence_manifest.get("files")
    manifest_binding = (
        report_evidence.get("manifest") if isinstance(report_evidence, dict) else None
    )
    if (
        not isinstance(report_evidence, dict)
        or not isinstance(manifest_binding, dict)
        or report_evidence.get("files") != files
        or manifest_binding.get("sha256")
        != hashlib.sha256(manifest_bytes).hexdigest()
        or manifest_binding.get("bytes") != len(manifest_bytes)
    ):
        raise VerificationError("Dynamic causal QA report and manifest are not atomically bound")
    file_paths = {
        record.get("path") for record in files or [] if isinstance(record, dict)
    }
    if file_paths != REQUIRED_CAUSAL_QA_EVIDENCE_FILES:
        raise VerificationError("Dynamic causal QA evidence inventory is not exact")
    media_contract = evidence_manifest.get("retained_media_contract")
    if (
        not isinstance(media_contract, dict)
        or media_contract
        != {
            "json": list(REQUIRED_CAUSAL_QA_RETAINED_JSON_EVIDENCE_FILES),
            "screenshots": list(
                REQUIRED_CAUSAL_QA_RETAINED_SCREENSHOT_EVIDENCE_FILES
            ),
            "video": REQUIRED_QA_VIDEO_EVIDENCE_FILE,
            "missing": [],
            "empty": [],
        }
    ):
        raise VerificationError("Dynamic causal QA retained-media contract is not exact")

    flagship = retained_evidence["flagship-run.json"]
    result = flagship.get("result")
    if not isinstance(result, Mapping):
        raise VerificationError("Dynamic causal QA flagship result is absent")
    _verify_grounded_flagship_contract(result)
    _verify_learning_replay_contract(
        demo_review=retained_evidence["demo-review.json"],
        post_review_run=retained_evidence["post-review-run.json"],
        baseline_run=retained_evidence["later-baseline-run.json"],
        later_run=retained_evidence["later-after-memory-run.json"],
        proof=retained_evidence["learning-proof.json"],
    )
    _verify_sanitized_evidence(
        {"retained_causal_evidence": retained_evidence},
        "Dynamic retained causal evidence",
    )
    return {
        "release_id": report.get("release_id"),
        "status": "passed",
        "verdict_source": "deterministic_retained_causal_preflight",
    }


def verify_dynamic_runtime_acceptance_paths(
    report_path: Path,
    evidence_manifest_path: Path,
) -> dict[str, Any]:
    """Verify a retained QA output directory without mutating release source."""

    report, evidence_manifest, retained_evidence, manifest_bytes = (
        _load_dynamic_runtime_evidence_paths(report_path, evidence_manifest_path)
    )
    return verify_dynamic_runtime_acceptance(
        load_json(RELEASE_PATH),
        report,
        evidence_manifest,
        retained_evidence,
        evidence_manifest_bytes=manifest_bytes,
    )


def verify_release_contract() -> None:
    release = load_json(RELEASE_PATH)
    required_pairs = {
        ("contract",): RELEASE_CONTRACT,
        ("schema_version",): "2.2.0",
        ("release_id",): "casepath-v20-reference-20260811",
        ("components", "frontend", "version"): "20.0.0",
        ("components", "api", "version"): "15.2.0",
        ("components", "pipeline", "version"): "15.2.0",
        ("components", "qa", "version"): "20.0.0",
        ("claims", "flagship"): "DEF-027-E0-DEMO",
        ("claims", "later_claim"): "DEMO-MOULD-002",
        ("truth", "deterministic_build", "execution_mode"): "deterministic_reference",
        ("truth", "deterministic_build", "model_calls"): 0,
        ("truth", "deterministic_build", "model_backed"): False,
        ("truth", "production_runtime_acceptance", "required_mode"): REQUIRED_PRODUCTION_MODE,
        ("truth", "production_runtime_acceptance", "required_model"): REQUIRED_PRODUCTION_MODEL,
        (
            "truth",
            "production_runtime_acceptance",
            "model_acceptance_scope",
        ): "visible_browser_flagship",
        (
            "truth",
            "production_runtime_acceptance",
            "learning_comparison_authority",
        ): "deterministic_application_tool",
        (
            "truth",
            "production_runtime_acceptance",
            "required_final_model_ledger_records",
        ): 12,
        (
            "truth",
            "production_runtime_acceptance",
            "required_final_model_network_calls",
        ): 6,
        (
            "truth",
            "production_runtime_acceptance",
            "required_final_cache_hits",
        ): 6,
        (
            "truth",
            "production_runtime_acceptance",
            "required_runtime_profile",
        ): REQUIRED_RUNTIME_PROFILE,
        ("truth", "independent_expert_review"): False,
        ("truth", "legal_approval"): False,
        ("truth", "operational_validation"): False,
        ("compatibility", "component_versions_are_independent"): True,
        ("artifact_policy", "scenario_dates", "flagship_received_on"): "2026-08-01",
        ("artifact_policy", "scenario_dates", "later_photo_on"): "2026-08-08",
        ("artifact_policy", "scenario_dates", "later_claim_received_on"): "2026-08-10",
    }
    for keys, expected in required_pairs.items():
        value: Any = release
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                raise VerificationError(f"Release contract is missing {'.'.join(keys)}")
            value = value[key]
        if value != expected:
            raise VerificationError(
                f"Release contract {'.'.join(keys)} must be {expected!r}, got {value!r}"
            )

    verify_static_runtime_acceptance_contract(release)

    release_text = RELEASE_PATH.read_text(encoding="utf-8")
    present_obsolete = sorted(
        identifier for identifier in OBSOLETE_CLAIM_IDS if identifier in release_text
    )
    if present_obsolete:
        raise VerificationError(f"Release contract contains obsolete claim IDs: {present_obsolete}")

    for path_text in ACTIVE_SCENARIO_FILES:
        path = REPOSITORY / path_text
        source = path.read_text(encoding="utf-8")
        stale = sorted(marker for marker in OBSOLETE_ACTIVE_MARKERS if marker in source)
        if stale:
            raise VerificationError(
                f"Active scenario file {path_text} contains stale markers: {stale}"
            )

    scenario_dates = release["artifact_policy"]["scenario_dates"]
    try:
        flagship_received = date.fromisoformat(scenario_dates["flagship_received_on"])
        later_photo = date.fromisoformat(scenario_dates["later_photo_on"])
        later_claim_received = date.fromisoformat(scenario_dates["later_claim_received_on"])
        released_on = date.fromisoformat(release["released_on"])
    except (KeyError, TypeError, ValueError) as exc:
        raise VerificationError(f"Invalid scenario date policy: {exc}") from exc
    if not flagship_received < later_photo < later_claim_received <= released_on:
        raise VerificationError(
            "Scenario dates must satisfy flagship_received < later_photo < "
            "later_claim_received <= released_on"
        )

    expected_source_identity = {
        "authority": RUNTIME_VERDICT_AUTHORITY,
        "source_contract_embeds_commit": False,
        "runtime_environment_variable": "RENDER_GIT_COMMIT",
        "unknown_semantics": (
            "A dynamic production acceptance result must fail when any service or evidence "
            "artifact reports an absent, unknown, or malformed source commit."
        ),
    }
    if release.get("source_identity") != expected_source_identity:
        raise VerificationError(
            "Release source identity must delegate commit truth to dynamic same-commit QA artifacts"
        )

    marker_checks = [
        (
            REPOSITORY / "casepath" / "index.html",
            re.compile(r'<meta\s+name="casepath-release"\s+content="20\.0\.0">'),
            "frontend 20.0.0 release meta",
        ),
        (
            REPOSITORY / "casepath-api" / "casepath_api" / "__init__.py",
            re.compile(r'__version__\s*=\s*"15\.2\.0"'),
            "API 15.2.0 version",
        ),
        (
            REPOSITORY / "casepath-api" / "casepath_api" / "pipeline_v15.py",
            re.compile(r'RELEASE\s*=\s*"15\.2\.0"'),
            "pipeline 15.2.0 release",
        ),
        (
            REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs",
            re.compile(r"const\s+PRODUCT_RELEASE\s*=\s*'20\.0\.0'"),
            "QA 20.0.0 report marker",
        ),
    ]
    for path, pattern, label in marker_checks:
        if not path.is_file() or not pattern.search(path.read_text(encoding="utf-8")):
            raise VerificationError(f"Missing {label} in {relative(path)}")

    exact_static_contract_markers = {
        REPOSITORY / "casepath-qa" / "run-local-real-nemotron-v20.sh": (
            'assert all(item.get("outcome") == "succeeded" for item in cold)',
            'assert all(item.get("deterministic_fallback_applied") is False for item in cold)',
            'assert all(item.get("rejected_fact_count", 0) == 0 for item in cold)',
            'assert all(item.get("rejected_item_count", 0) == 0 for item in cold)',
            'assert all(item.get("source_reference_projection_count", 0) == 0 for item in cold)',
        ),
        REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs": (
            "if (EXPECT_REAL_NEMOTRON && (",
            "item.deterministic_fallback_applied !== false",
            "item.rejected_count !== 0",
            "(cacheMode === 'cold' && item.outcome !== 'succeeded')",
            "if (EXPECT_REAL_NEMOTRON && projected.length)",
            "presentationMode !== 'returned-action-replay'",
            "returned-action replay is not visibly labelled",
            "graph replay is not visibly labelled as returned work",
        ),
    }
    for path, markers in exact_static_contract_markers.items():
        source = path.read_text(encoding="utf-8") if path.is_file() else ""
        missing = [marker for marker in markers if marker not in source]
        if missing:
            raise VerificationError(
                f"Static real-run/replay contract is incomplete in {relative(path)}: {missing}"
            )

    def pinned_requirements(path: Path) -> dict[str, str]:
        pins: dict[str, str] = {}
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "==" not in line:
                raise VerificationError(f"Unpinned dependency in {relative(path)}: {line}")
            package, version = line.split("==", 1)
            normalized = package.split("[", 1)[0].strip().lower().replace("_", "-")
            if normalized in pins:
                raise VerificationError(
                    f"Duplicate dependency pin in {relative(path)}: {normalized}"
                )
            pins[normalized] = version.strip()
        return pins

    direct_path = REPOSITORY / "casepath-api" / "requirements.txt"
    lock_path = REPOSITORY / "casepath-api" / "requirements.lock"
    direct = pinned_requirements(direct_path)
    locked = pinned_requirements(lock_path)
    inconsistent = {
        package: {"direct": version, "lock": locked.get(package)}
        for package, version in direct.items()
        if locked.get(package) != version
    }
    if inconsistent:
        raise VerificationError(f"Dependency lock is inconsistent: {inconsistent}")
    required_framework_pins = {
        "langchain": REQUIRED_FRAMEWORK["langchain"],
        "langgraph": REQUIRED_FRAMEWORK["langgraph"],
        "langchain-openrouter": REQUIRED_FRAMEWORK["langchain_openrouter"],
    }
    inconsistent_framework = {
        package: {"required": version, "locked": locked.get(package)}
        for package, version in required_framework_pins.items()
        if locked.get(package) != version
    }
    if inconsistent_framework:
        raise VerificationError(
            f"Agent framework lock is inconsistent: {inconsistent_framework}"
        )
    required_resolved_packages = {
        "distro",
        "jsonpatch",
        "jsonpath-python",
        "jsonpointer",
        "langchain-core",
        "langchain-protocol",
        "langgraph-checkpoint",
        "langgraph-prebuilt",
        "langgraph-sdk",
        "langsmith",
        "openrouter",
        "orjson",
        "ormsgpack",
        "requests",
        "requests-toolbelt",
        "sniffio",
        "tenacity",
        "urllib3",
        "uuid-utils",
        "xxhash",
        "zstandard",
    }
    missing_resolved = sorted(required_resolved_packages - locked.keys())
    if missing_resolved:
        raise VerificationError(
            f"Agent framework transitive lock is incomplete: {missing_resolved}"
        )


def generate() -> None:
    verify_release_contract()
    artifact_manifest = build_artifact_manifest()
    write_json(ARTIFACT_MANIFEST_PATH, artifact_manifest)
    source_payload = source_manifest_payload()
    if exact_git_worktree():
        write_json(SOURCE_MANIFEST_PATH, source_payload)
    elif load_json(SOURCE_MANIFEST_PATH) != source_payload:
        raise VerificationError(
            "Source archive regeneration diverged from its immutable source manifest"
        )
    verify()


def prepare_artifacts() -> None:
    """Rebuild ignored artifacts while keeping the sealed source manifest immutable."""

    verify_release_contract()
    artifact_manifest = build_artifact_manifest()
    write_json(ARTIFACT_MANIFEST_PATH, artifact_manifest)
    if load_json(SOURCE_MANIFEST_PATH) != source_manifest_payload():
        raise VerificationError(
            "Prepared artifacts differ from the sealed source manifest"
        )
    print(
        json.dumps(
            {
                "artifact_files": artifact_manifest["file_count"],
                "status": "prepared",
            },
            indent=2,
            sort_keys=True,
        )
    )


def verify() -> None:
    verify_release_contract()

    expected_artifact = build_artifact_manifest()
    actual_artifact = load_json(ARTIFACT_MANIFEST_PATH)
    if actual_artifact != expected_artifact:
        raise VerificationError(
            "Artifact manifest is stale; run `python casepath/tools/casepath_release.py generate`"
        )

    expected_source = source_manifest_payload()
    actual_source = load_json(SOURCE_MANIFEST_PATH)
    if actual_source != expected_source:
        raise VerificationError(
            "Source manifest is stale; run `python casepath/tools/casepath_release.py generate`"
        )

    print(
        json.dumps(
            {
                "artifact_files": expected_artifact["file_count"],
                "leakage_scan": expected_artifact["leakage_policy"]["status"],
                "model_visible_artifacts": expected_artifact["leakage_policy"][
                    "model_visible_files_scanned"
                ],
                "release_id": actual_source["release_id"],
                "source_commit": verify_static_deployment_identity()["source_commit"],
                "source_files": actual_source["file_count"],
                "status": "verified",
            },
            indent=2,
            sort_keys=True,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "generate",
            "prepare-artifacts",
            "verify",
            "verify-runtime-causal-evidence",
            "verify-runtime-evidence",
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Path to the dynamic QA report.json",
    )
    parser.add_argument(
        "--evidence-manifest",
        type=Path,
        help="Path to the dynamic QA evidence-manifest.json",
    )
    args = parser.parse_args()
    if args.command.startswith("verify-runtime-") and (
        args.report is None or args.evidence_manifest is None
    ):
        parser.error(
            f"{args.command} requires --report and --evidence-manifest"
        )
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.command == "generate":
            generate()
        elif args.command == "prepare-artifacts":
            prepare_artifacts()
        elif args.command == "verify":
            verify()
        elif args.command == "verify-runtime-causal-evidence":
            result = verify_dynamic_causal_evidence_paths(
                args.report,
                args.evidence_manifest,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            result = verify_dynamic_runtime_acceptance_paths(
                args.report,
                args.evidence_manifest,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
    except VerificationError as exc:
        print(f"release verification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
