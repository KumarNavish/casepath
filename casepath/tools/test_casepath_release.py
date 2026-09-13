from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest


TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import casepath_release as release_tool  # noqa: E402
from casepath_api.canonicalizer import (  # noqa: E402
    observable_source_reference_registry,
)


def _content_bound_asset_locator(asset_name: str) -> str:
    asset = release_tool.REPOSITORY / "casepath" / "assets" / asset_name
    return f"assets/{asset_name}?sha256={hashlib.sha256(asset.read_bytes()).hexdigest()}"


@pytest.mark.parametrize(
    ("text", "marker"),
    [
        ("generated attachment", "generated"),
        ("fictional document", "fictional"),
        ("sample record", "sample"),
        ("dummy value", "dummy"),
        ("benchmark answer", "benchmark"),
        ("hidden labels", "hidden_label"),
        ("service@company.example", "example_domain"),
        ("CasePath demo", "demo"),
    ],
)
def test_required_leakage_markers_are_detected(text: str, marker: str) -> None:
    findings = release_tool.scan_text("unit-test", text)
    assert marker in {finding["marker"] for finding in findings}


def test_release_contract_and_manifests_are_current() -> None:
    release_tool.verify_release_contract()
    assert release_tool.load_json(release_tool.ARTIFACT_MANIFEST_PATH) == (
        release_tool.build_artifact_manifest()
    )
    assert release_tool.load_json(release_tool.SOURCE_MANIFEST_PATH) == (
        release_tool.source_manifest_payload()
    )


def test_source_manifest_requires_exact_known_commit_static_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_commit = "25fe0b603360696d412a0ba4992651dd2291dc5d"
    monkeypatch.setenv("CASEPATH_SOURCE_COMMIT", source_commit)
    expected = release_tool.build_deployment_identity.build_payload(dict(os.environ))
    deployment_path = tmp_path / "deployment.json"
    deployment_path.write_text(
        json.dumps(expected, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(release_tool, "STATIC_DEPLOYMENT_PATH", deployment_path)
    assert release_tool.verify_static_deployment_identity() == expected

    forged = dict(expected)
    forged["source_commit"] = "unknown"
    forged["source_commit_source"] = "unavailable_or_invalid"
    forged["alignment_eligible"] = False
    deployment_path.write_text(
        json.dumps(forged, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        release_tool.VerificationError,
        match="differs from source/release authority",
    ):
        release_tool.verify_static_deployment_identity()


def test_root_knowledge_transfer_is_inventoried_as_release_source() -> None:
    assert ".gitignore" in release_tool.EXTRA_SOURCE_FILES
    assert "AGENTS.md" in release_tool.EXTRA_SOURCE_FILES
    assert "CASEPATH_MASTER_KNOWLEDGE_TRANSFER.md" in (
        release_tool.EXTRA_SOURCE_FILES
    )
    inventoried_paths = {
        item["path"] for item in release_tool.source_manifest_payload()["files"]
    }
    assert ".gitignore" in inventoried_paths
    assert "AGENTS.md" in inventoried_paths
    assert "CASEPATH_MASTER_KNOWLEDGE_TRANSFER.md" in inventoried_paths


def test_source_manifest_keeps_runtime_commit_outside_self_excluded_bytes() -> None:
    payload = release_tool.source_manifest_payload()
    assert payload["contract"] == "casepath.source-manifest/2.1.0"
    assert "source_commit" not in payload


def test_prepare_artifacts_keeps_sealed_source_manifest_immutable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_manifest = {"file_count": 2}
    source_manifest = {"contract": "casepath.source-manifest/2.1.0"}
    writes: list[tuple[Path, dict[str, object]]] = []
    monkeypatch.setattr(release_tool, "verify_release_contract", lambda: None)
    monkeypatch.setattr(
        release_tool, "build_artifact_manifest", lambda: artifact_manifest
    )
    monkeypatch.setattr(
        release_tool, "write_json", lambda path, value: writes.append((path, value))
    )
    monkeypatch.setattr(release_tool, "load_json", lambda _path: source_manifest)
    monkeypatch.setattr(
        release_tool, "source_manifest_payload", lambda: source_manifest
    )

    release_tool.prepare_artifacts()

    assert writes == [(release_tool.ARTIFACT_MANIFEST_PATH, artifact_manifest)]


def test_browser_gate_pins_complete_runtime_acceptance_criteria() -> None:
    source = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")
    start = source.index("const EXPECTED_RUNTIME_ACCEPTANCE_CRITERIA")
    end = source.index("\n});", start)
    criteria = source[start:end]
    assert "requires_grounded_causal_artifact_recomputation: true" in criteria
    assert "requires_learning_replay_proof: true" in criteria


def test_local_preflight_is_loopback_deterministic_and_zero_provider() -> None:
    wrapper = (
        release_tool.REPOSITORY / "casepath-qa" / "run-local-preflight-v20.sh"
    ).read_text(encoding="utf-8")

    assert 'parsed.hostname not in {"127.0.0.1", "localhost", "::1"}' in wrapper
    assert 'frontend.port != 4173' in wrapper
    assert 'health.get("model_mode") != "deterministic_reference"' in wrapper
    assert 'get("credential_configured") is not False' in wrapper
    assert "CASEPATH_ALLOW_PRODUCTION_MUTATION=0" in wrapper
    assert 'CASEPATH_QA_SERVICE_ROOT="${CASEPATH_QA_SERVICE_ROOT:-}"' in wrapper
    assert "/usr/local/bin/node browser-focused-v20.mjs" in wrapper
    assert "/usr/local/bin/node browser-insurance-protocol-v1.mjs" in wrapper
    assert "verify-runtime-causal-evidence" in wrapper
    assert "local model ledger is not fresh" in wrapper
    assert "post-journey model ledger is not exactly empty" in wrapper
    assert "Run returns four exact official legal-source execution traces" in wrapper
    assert "browser report lacks four accepted official legal-source traces" in wrapper


def test_candidate_source_identity_supports_manifest_closed_archives() -> None:
    helper = (
        release_tool.REPOSITORY / "casepath-qa" / "candidate-source-identity.mjs"
    ).read_text(encoding="utf-8")
    assert "async function archiveSourceIdentity()" in helper
    assert "candidate archive source manifest schema is invalid" in helper
    assert "candidate archive source row drifted: ${row.path}" in helper
    assert "candidate archive source rows are duplicated or out of order" in helper
    assert "if (error?.code === 'ENOENT') return archiveSourceIdentity();" in helper
    assert "candidate source archive requires an exact runtime source commit" in helper
    assert "git: { branch: 'source-archive', head: runtimeCommit }" in helper
    assert "const source = await sourceIdentity();" in helper
    assert "git: source.git" in helper
    assert "async function validateClosedInstalledTree(" in helper
    assert "candidate live listener working directory differs" in helper
    assert "candidate live listener command differs" in helper
    assert "CASEPATH_QA_SERVICE_ROOT is required with an installed boot receipt" in helper
    assert "candidate path has a symlinked ancestor" in helper
    assert "candidate live listener start time is inconsistent" in helper
    assert "candidate live listener executable text differs" in helper
    assert "await executableIdentity('/usr/sbin/lsof', 'system lsof')" in helper
    assert "BigInt(mappedPythonRecord.device) !== runtimePythonRealStat.dev" in helper
    assert "candidate live listener is not bound to the exact persistent launchd job" in helper
    assert "await executableIdentity('/bin/launchctl', 'system launchctl')" in helper
    assert "`${label} root is not an immutable runtime-bearing directory`" in helper
    assert "installed_non_runtime_roster: installedRosterIdentity" in helper


def test_all_local_browser_gates_bind_the_installed_runtime_identity() -> None:
    repository = release_tool.REPOSITORY
    workspace = (repository / "casepath-qa/browser-claims-workspace-v1.mjs").read_text(
        encoding="utf-8"
    )
    insurance = (repository / "casepath-qa/browser-insurance-protocol-v1.mjs").read_text(
        encoding="utf-8"
    )
    legacy = (repository / "casepath-qa/browser-focused-v20.mjs").read_text(
        encoding="utf-8"
    )

    assert "requireApiBootReceipt: true" in workspace
    assert "api_runtime_identity: candidateSourceSnapshotStart.apiBootIdentity" in workspace
    assert "requireApiBootReceipt: true" in insurance
    assert "api_runtime_identity: candidateSourceSnapshotStart.apiBootIdentity" in insurance
    assert "REQUIRE_INSTALLED_API_BOOT" in legacy
    assert "const LOOPBACK_HOSTNAMES = new Set(['127.0.0.1', 'localhost', '::1', '[::1]']);" in legacy
    assert "BASE_IDENTITY.port === '4173'" in legacy
    assert "API_IDENTITY.port === '4173'" in legacy
    assert "api_runtime_identity: candidateSourceSnapshotStart.apiBootIdentity" in legacy


def test_local_real_nemotron_acceptance_is_explicit_fresh_and_single_pass() -> None:
    wrapper = (
        release_tool.REPOSITORY
        / "casepath-qa"
        / "run-local-real-nemotron-v20.sh"
    ).read_text(encoding="utf-8")
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")

    authorization = '"${CASEPATH_AUTHORIZE_REAL_NEMOTRON:-}" != "1"'
    preflight = 'bash "$qa_directory/run-local-preflight-v20.sh"'
    real_runtime = "export CASEPATH_MODEL_MODE=openrouter_nemotron"
    browser_journey = "node browser-guided-v13-smoke.mjs"
    assert authorization in wrapper
    assert wrapper.index(preflight) < wrapper.index(real_runtime)
    assert "CASEPATH_EXPECT_REAL_NEMOTRON=0" in wrapper[: wrapper.index(real_runtime)]
    assert 'preflight_frontend_url="${CASEPATH_LOCAL_PREFLIGHT_FRONTEND_URL:-http://127.0.0.1:4173}"' in wrapper
    assert 'CASEPATH_LOCAL_FRONTEND_URL="$preflight_frontend_url"' in wrapper
    assert 'preflight_api_port="$("$python_command" - <<\'PY\'' in wrapper
    assert 'CASEPATH_LOCAL_API_URL="http://127.0.0.1:$preflight_api_port"' in wrapper
    assert 'CASEPATH_LOCAL_API_URL="http://127.0.0.1:8002"' not in wrapper
    assert 'frontend_url="http://127.0.0.1:$frontend_port"' in wrapper
    assert '"$python_command" -m http.server "$frontend_port"' in wrapper
    assert "Isolated commit-bound frontend" in wrapper
    assert "Port 4173 is serving a different frontend" not in wrapper
    assert wrapper.count(browser_journey) == 1
    assert "CASEPATH_EXPECT_REAL_NEMOTRON=1" in wrapper
    assert "CASEPATH_ALLOW_PRODUCTION_MUTATION=0" in wrapper
    assert 'database_path="$acceptance_root/fresh-real-nemotron.db"' in wrapper
    assert 'if [[ -e "$database_path" ]]' in wrapper
    assert "initial-model-ledger.json" in wrapper
    assert 'assert ledger.get("items") == []' in wrapper
    assert 'assert len(items) == 12 and summary.get("records") == 12' in wrapper
    assert 'assert summary.get("network_calls") == 6' in wrapper
    assert 'assert summary.get("outcomes", {}).get("cache_hit") == 6' in wrapper
    assert 'assert all(item.get("outcome") == "succeeded" for item in cold)' in wrapper
    assert "capture_runtime_diagnostics" in wrapper
    assert 'final-health.json' in wrapper
    assert 'final-readiness.json' in wrapper
    assert 'final-model-ledger.json' in wrapper
    assert 'final-run.json' in wrapper
    assert '"SELECT payload FROM events "' in wrapper
    assert '"WHERE session_id=? AND run_id=? ORDER BY ordinal"' in wrapper
    assert "events=events" in wrapper
    assert wrapper.index("capture_runtime_diagnostics") < wrapper.index('terminate_process "$api_pid"', wrapper.index("finish()"))
    assert (
        'assert all(item.get("deterministic_fallback_applied") is False for item in cold)'
        in wrapper
    )
    assert 'assert all(item.get("rejected_fact_count", 0) == 0 for item in cold)' in wrapper
    assert 'assert all(item.get("rejected_item_count", 0) == 0 for item in cold)' in wrapper
    assert (
        'assert all(item.get("source_reference_projection_count", 0) == 0 for item in cold)'
        in wrapper
    )
    assert "verify-runtime-causal-evidence" in wrapper
    assert "CASEPATH_MODEL_CUMULATIVE_USD_CAP=1" in wrapper
    assert "automatic_inference_retry" in wrapper
    assert "REAL_ACCEPTANCE_PARENT_PATTERN" in browser_gate
    assert "return EXPECT_REAL_NEMOTRON || !isLocal(BASE) || !isLocal(API);" in browser_gate
    assert "if (EXPECT_REAL_NEMOTRON && (" in browser_gate
    assert "item.deterministic_fallback_applied !== false" in browser_gate
    assert "item.rejected_count !== 0" in browser_gate
    assert "(cacheMode === 'cold' && item.outcome !== 'succeeded')" in browser_gate
    assert "if (EXPECT_REAL_NEMOTRON && projected.length)" in browser_gate
    assert (
        "if ((!isLocal(BASE) || !isLocal(API)) && !ALLOW_PRODUCTION_MUTATION)"
        in browser_gate
    )
    assert "presentationMode !== 'returned-action-replay'" in browser_gate
    assert "returned-action replay is not visibly labelled" in browser_gate
    assert "graph replay is not visibly labelled as returned work" in browser_gate


def test_sites_delivery_is_same_origin_and_streaming_proxy_safe(tmp_path: Path, monkeypatch) -> None:
    worker = (
        release_tool.REPOSITORY / "casepath" / "tools" / "sites_worker.mjs"
    ).read_text(encoding="utf-8")
    builder = (
        release_tool.REPOSITORY / "casepath" / "tools" / "build_sites_site.py"
    ).read_text(encoding="utf-8")
    # This standalone repository has no hosting installation. Validate the
    # bundle in a temporary local fixture without inventing a deployment target.
    import build_sites_site as sites
    import build_static_site as static
    public = tmp_path / "casepath-public"
    monkeypatch.setattr(static, "DEFAULT_OUTPUT", public)
    static.build_static_site(public, {})
    monkeypatch.setattr(sites, "REPOSITORY", tmp_path)
    monkeypatch.setattr(sites, "PUBLIC_ROOT", public)
    monkeypatch.setattr(sites, "OUTPUT_ROOT", tmp_path / "dist")
    sites.build()
    assert (tmp_path / "dist/server/index.js").read_text() == worker
    assert sites.API_CONFIGURATION in (tmp_path / "dist/client/index.html").read_text()
    assert static.inventory(tmp_path / "dist/client")[0] == static.PUBLIC_INVENTORY
    assert not (tmp_path / ".openai").exists()
    assert "https://casepath-agentic-api.onrender.com" in worker
    assert 'pathname.startsWith("/api/")' in worker
    assert '"/healthz"' in worker and '"/readyz"' in worker
    assert "return fetch(upstreamRequest)" in worker
    assert "request.body" in worker
    assert "window.CASEPATH_API = window.location.origin" in worker
    assert "API_CONFIGURATION" in builder
    assert "API_SCRIPT_MARKER" in builder
    assert "index_path.write_text" in builder
    assert 'staging / "server" / "index.js"' in builder
    assert 'shutil.copytree(PUBLIC_ROOT, staging / "client")' in builder


def test_loaded_precedent_renderers_preserve_exact_review_authority() -> None:
    assets = release_tool.REPOSITORY / "casepath" / "assets"
    precedent_renderer = (assets / "live-v16.js").read_text(encoding="utf-8")
    assert "'qualified_expert_reviewed'" in precedent_renderer
    assert "'unverified_demo_memory'" in precedent_renderer
    assert "Unverified generated-demo review memory returned by the server" in (
        precedent_renderer
    )
    assert "Unverified demo review memory returned" in precedent_renderer


def test_memory_reuse_proof_is_synchronous_authoritative_and_receipt_scoped() -> None:
    assets = release_tool.REPOSITORY / "casepath" / "assets"
    flagship_renderer = (assets / "live-v16.js").read_text(encoding="utf-8")
    reuse_renderer = (assets / "live-v17.js").read_text(encoding="utf-8")
    reuse_wrapper = (assets / "live-v18.js").read_text(encoding="utf-8")
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")
    function_start = flagship_renderer.index("  function renderMemoryReuseProof(")
    function_end = flagship_renderer.index("\n  function factsForNode(", function_start)
    function_source = flagship_renderer[function_start:function_end]
    later_result_start = flagship_renderer.index("  function renderLaterResult()")
    later_result_end = flagship_renderer.index("\n  function restartDemo()", later_result_start)
    later_result_source = flagship_renderer[later_result_start:later_result_end]
    assert "currentRun" not in function_source
    assert "v18-reuse-proof" in function_source
    assert "v17-reuse-thread" in function_source
    assert "memoryUsed && !receipt" in function_source
    assert "data-memory-contract=" in function_source
    assert "data-application-hash=" in function_source
    assert "data-memory-authority=" in function_source
    assert "data-memory-scope=" in function_source
    assert "renderMemoryReuseProof({ result, proof, memoryUsed, retrievedOnly, memoryState: returnedMemoryState })" in later_result_source
    assert "proof.causal_delta?.nonzero === true" in later_result_source
    assert "${reuseProofMarkup}<div class=\"before-after\">" in later_result_source
    assert "function enhanceReuse" not in reuse_renderer
    assert "function enhanceReuse" not in reuse_wrapper
    assert "const validMemoryReceipt = receipt =>" in reuse_renderer
    assert "validMemoryReceipt(transform)" in reuse_renderer
    assert (
        "const reuseThreadSelector = '#laterResult .v18-reuse-proof .v17-reuse-thread';"
        in browser_gate
    )
    assert "laterReuseThreadCount === 1 && reuseProofCount === 1 && proofReuseThreadCount === 1" in browser_gate
    assert "page.locator('.v17-reuse-thread').innerText()" not in browser_gate


def test_loaded_orchestration_renderer_keeps_validator_identity_out_of_gate_ids() -> None:
    source = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v16.js"
    ).read_text(encoding="utf-8")
    assert "const gateId = returnedValue(event, 'gate_id', 'agent_id');" in source
    assert "const validator = returnedValue(event, 'validator');" in source
    assert "const gateIdentity = gateId ? ` data-gate-id=" in source
    assert (
        "returnedValue(event, 'gate_id', 'agent_id', 'validator', 'label')"
        not in source
    )


def test_process_workspace_interactions_preserve_declared_capabilities() -> None:
    source = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v16.js"
    ).read_text(encoding="utf-8")
    assert '<div class="process-layout" data-evidence="${esc(String(evidence))}" ' in source
    assert 'data-precedents="${esc(String(precedents))}"' in source
    assert "const layout = button.closest('.process-layout');" in source
    assert "if (!layout) return;" in source
    assert "evidence: layout.dataset.evidence === 'true'" in source
    assert "precedents: layout.dataset.precedents === 'true'" in source
    assert "precedents: state.stageMode === 'experience'" not in source


def test_visual_grounding_qa_matches_rendered_authority_copy() -> None:
    renderer = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v16.js"
    ).read_text(encoding="utf-8")
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")
    authority_copy = (
        "Hash-bound to these demo image bytes; not machine extraction, model "
        "output, or qualified review."
    )
    assert authority_copy in renderer
    assert authority_copy.replace(".", r"\.") in browser_gate
    assert "/not an exact quote/i" not in browser_gate


def test_document_plan_exposes_all_items_as_graph_derived_chains() -> None:
    focus = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v20-focus.js"
    ).read_text(encoding="utf-8")
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")
    assert "Review document plan" in focus
    assert "data-v20-guided-documents" in focus
    assert "data-v20-continue-review" in focus
    assert "Continue to review" in focus
    assert "Next: simulated review of one process decision · not expert approval" in focus
    assert "function continueToExpertReview()" in focus
    assert "new CustomEvent('casepath:begin-review')" in focus
    assert "await waitText('#journeyNext', /Review document plan/i" in browser_gate
    assert "await waitText('#journeyNext', /Review the proposed playbook/i" not in browser_gate
    assert "Ready exposes Review document plan as its sole primary action" in browser_gate
    assert "Open Document plan has exactly one primary action: Continue to review" in browser_gate
    assert "Continue to review closes the plan and reaches simulated review" in browser_gate
    assert "Document plan contains each of the exact 21 returned checklist items once" in browser_gate
    assert "Every document row preserves process question to fact to evidence to document to status in that order" in browser_gate
    assert "Each document chain preserves exact returned primary owner, ordered owners, path, fact, status, and item identity" in browser_gate
    assert "Document status filters report exact returned counts" in browser_gate
    assert ".v20-document-chain[data-item-id]" in browser_gate


def test_v20_review_keeps_the_unverified_authority_disclosure_visible() -> None:
    focus = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v20-focus.js"
    ).read_text(encoding="utf-8")
    focus_css = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v20-focus.css"
    ).read_text(encoding="utf-8")
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")
    assert "Simulated demo review only; this is not qualified expert approval." in focus
    assert '.review-panel>p:not(.v20-review-note)' in focus_css
    assert 'body[data-casepath-moment="review"] .v20-review-note{' in focus_css
    assert 'body[data-casepath-moment="review"] .v19-review-branch-preview' in focus_css
    assert '[data-ac-action="submit-review"]' in browser_gate
    assert "const visibleReviewCopy" in browser_gate
    assert "[data-review-edit-state=\"applied\"]" in browser_gate
    assert "/unverified/i" in browser_gate
    assert "Applied-review UI keeps the edit explicitly unverified" in browser_gate


def test_north_star_review_and_learning_remain_graph_native() -> None:
    assets = release_tool.REPOSITORY / "casepath" / "assets"
    canvas = (assets / "artifact-canvas.js").read_text(encoding="utf-8")
    flagship_renderer = (assets / "live-v16.js").read_text(encoding="utf-8")
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")

    review_start = canvas.index("  function reviewGraphEditMarkup()")
    review_end = canvas.index("\n  function reviewAppliedMarkup()", review_start)
    review_markup = canvas[review_start:review_end]

    assert (
        "const GRAPH_MOMENTS = new Set(['process', 'evidence', 'experience', "
        "'verify', 'ready', 'review', 'review-applied', 'knowledge', 'later-work', "
        "'later-result']);"
    ) in canvas
    assert "function reviewGraphEditMarkup()" in canvas
    assert 'class="ac-review-graph-edit"' in canvas
    assert 'data-review-node-id="causation"' in canvas
    assert 'data-ac-action="submit-review"' in canvas
    assert "Review one evidence relationship" in review_markup
    assert "When should ventilation evidence become relevant?" in review_markup
    assert 'data-review-selected-mode="${esc(state.reviewMode)}"' in review_markup
    assert 'role="radiogroup"' in review_markup
    assert review_markup.count('role="radio"') == 2
    assert 'data-review-mode="conditional"' in review_markup
    assert 'data-review-mode="required_now"' in review_markup
    assert "After a neutral inspection" in review_markup
    assert "Request both checks now" in review_markup
    assert "Implicit allegation" in review_markup
    assert "Add ventilation decision" in review_markup
    assert (
        "Move use evidence to the new decision; building-envelope assessment "
        "remains conditional."
    ) in review_markup
    assert (
        "Do not add a ventilation decision; keep broader building testing "
        "immediately required."
    ) in review_markup
    assert review_markup.count('data-ac-action="submit-review"') == 1
    assert review_markup.count('data-casepath-primary-action="true"') == 1
    assert "function reviewChoiceContractViolations" in browser_gate
    assert "defaults to conditional, changes the visible consequence for required now" in browser_gate
    assert "Review fixture with two selected radio choices was accepted" in browser_gate
    assert "Required-now review fixture without a changed consequence was accepted" in browser_gate
    assert "Review fixture with competing primary Apply actions was accepted" in browser_gate
    assert "Required</span>" not in review_markup
    assert "Building-envelope testing becomes conditional" not in flagship_renderer
    assert (
        "Move use evidence to the new decision; building-envelope testing "
        "remains conditional."
    ) in flagship_renderer
    assert "Unverified demo correction · model acceptance not reused" in canvas
    assert "function reviewAppliedTruth()" in canvas
    assert "data-review-delta-verified" in canvas
    assert "No correction is claimed" in canvas
    assert "function reviewAppliedMarkup()" in canvas
    assert "function laterMemoryDeltaMarkup()" in canvas
    assert 'data-memory-payoff="single-action"' in canvas
    assert 'data-memory-status="unverified-case-memory"' in canvas
    assert 'data-responsibility-state="blocked"' in canvas
    assert 'data-shared-playbook-changed="false"' in canvas
    assert "Unverified case memory used on this claim" in canvas
    assert "Check ventilation before assigning responsibility." in canvas
    assert "Why the next handler is safer" not in canvas
    assert "Cause still unproven · responsibility stays blocked · qualified review required." in canvas
    assert "1 decision · 2 connections · 3 document needs" in canvas
    assert 'class="ac-memory-causal-seam"' in canvas
    assert 'data-later-payoff-source="${esc(source.ref.artifact_id)}"' in canvas
    assert 'data-later-payoff-locator="${esc(sourceLocatorId(source.ref))}"' in canvas
    assert 'data-later-payoff-rule="${esc(eligibility.ruleId)}"' in canvas
    assert 'data-causal-seam-part="source"' in canvas
    assert 'data-causal-seam-part="memory"' in canvas
    assert 'data-causal-seam-part="result"' in canvas
    assert "Saved correction matched" in canvas
    assert "Check ventilation separately" in canvas
    assert "Graph change" in canvas
    assert "Ventilation check added" in canvas
    assert "function laterCausalSeamContractViolations" in browser_gate
    assert "exact returned source locator and excerpt, accepted eligibility rule" in browser_gate
    assert "Later causal seam with a forged source locator was accepted" in browser_gate
    assert "Later causal seam with a generated excerpt was accepted" in browser_gate
    assert "Later causal seam with an unaccepted eligibility rule was accepted" in browser_gate
    assert "Later causal seam with a forged receipt effect count was accepted" in browser_gate
    assert "Later payoff shows one exact guarded action and keeps five technical effects behind closed Inspect proof" in browser_gate
    assert "function verificationGraphMarkup(anchorNodeId = 'causation')" in canvas
    assert "verificationGraphMarkup(current.node_id)" in canvas
    assert 'data-spatial-anchor-node-id="${esc(anchorNodeId)}"' in canvas
    assert 'class="ac-graph-verification"' in canvas
    assert 'data-node-attachment-kind="verification"' in canvas
    assert "Final audit" in canvas
    assert "No unsupported proposals retained" in canvas
    assert "Verification incomplete" in canvas
    assert "function knowledgeGraphMarkup()" in canvas
    assert 'class="ac-knowledge-graph-note"' in canvas
    assert 'data-memory-id="${esc(memory.memoryId)}"' in canvas
    assert 'data-memory-status="${memory.available ? \'unverified_demo_memory\' : \'not-confirmed\'}"' in canvas
    assert "Saved as unverified case memory" in canvas
    assert "Check ventilation allegations separately" in canvas
    assert "function laterCausalGraphMarkup()" in canvas
    assert 'class="ac-later-memory-retrieval"' in canvas
    assert 'data-later-causal-phase="memory"' in canvas
    assert 'data-later-causal-phase="eligibility"' in canvas
    assert 'data-later-source-opened="false"' in canvas
    assert 'data-later-source-opened="true"' in canvas
    assert 'data-memory-origin-id="${esc(step.memoryOriginId)}"' in canvas
    assert "Unverified case memory retrieved" in canvas
    assert 'item.dataset.memoryCandidate = \'true\'' in canvas
    assert "Check ventilation allegations separately · Now checking whether it applies" in canvas
    assert "Now checking whether it applies to this claim." in canvas
    assert "casepath.later-causal-step/1.0.0" in canvas
    assert "casepath:later-causal-step" in canvas
    assert "const LATER_CAUSAL_STEP_CONTRACT = 'casepath.later-causal-step/1.0.0';" in flagship_renderer
    assert "const LATER_CAUSAL_SOURCE_HOLD_MS = reduceMotion ? 2400 : 5200;" in flagship_renderer
    assert "const LATER_CAUSAL_MEMORY_HOLD_MS = reduceMotion ? 1800 : 3000;" in flagship_renderer
    assert "const LATER_CAUSAL_ELIGIBILITY_HOLD_MS = reduceMotion ? 1800 : 2800;" in flagship_renderer
    assert "casepath:later-source-opened" in flagship_renderer
    assert "casepath:later-causal-step-visible" in flagship_renderer
    assert "await presentLaterCausalStep(sourceStep" in flagship_renderer
    assert "await waitForTwoPaints()" in flagship_renderer
    assert "[data-later-causal-phase=\"source\"] mark.is-highlighted" in flagship_renderer
    assert ".attachment-row.is-active, .v21-source-summary-toggle.is-active" in flagship_renderer
    assert "[data-later-causal-phase=\"memory\"]" in flagship_renderer
    assert "[data-later-causal-phase=\"eligibility\"]" in flagship_renderer
    assert "function dispatchLaterCausalStep(detail)" in flagship_renderer
    assert "new CustomEvent('casepath:later-causal-step'" in flagship_renderer
    assert "phase: 'waiting'" in flagship_renderer
    assert "phase: 'source'" in flagship_renderer
    assert "phase: 'memory'" in flagship_renderer
    assert "phase: 'eligibility'" in flagship_renderer
    assert "Match confirmed" in canvas
    assert "Same unresolved ventilation allegation" in canvas
    assert "fact.semantic_role !== 'management_ventilation_allegation'" in canvas
    assert "String(receipt.target?.run_id || '') !== runId" in canvas
    assert "clearActiveSource();" in canvas
    assert "markSubmissionSource(step.ref.artifact_id);" in canvas
    assert "casepath:later-source-opened" in canvas
    assert "Unverified case memory used on this claim" in canvas
    assert "casepathLearningReady === 'true'" in browser_gate
    assert "laterSourceStep?.activeSourceIds" in browser_gate
    assert 'data-memory-effect="node-added"' in canvas
    assert 'data-memory-effect="edge-added"' in canvas
    assert 'data-memory-effect="evidence-changed"' in canvas
    assert "Shared playbook unchanged." in canvas
    assert "function persistentGraphSceneSnapshot()" in browser_gate
    assert "function persistentGraphSceneContractViolations" in browser_gate
    assert "process graph is not the sole visible focal object" in browser_gate
    assert "process graph is not the sole visible primary artifact" in browser_gate
    assert "function graphNativeMomentCopyContractViolations" in browser_gate
    assert "function graphNativeMomentSceneViolations" in browser_gate
    assert "Verification keeps the graph as the sole focal artifact" in browser_gate
    assert "Knowledge consolidation keeps the graph as the sole focal artifact" in browser_gate
    assert "Later-work keeps the untouched graph central" in browser_gate
    assert "casepath.later-causal-step/1.0.0" in browser_gate
    assert "queueMicrotask(() => {" in browser_gate
    assert "step.activeSourceIds = window.__casepathActiveSourceIds();" in browser_gate
    assert "memory effect identity" in browser_gate
    assert "exact returned node, fact, page and excerpt or region" in browser_gate
    assert "later causal seam source locator is not an exact returned allegation source" in browser_gate
    assert "later causal seam does not retain the exact source step locator" in browser_gate
    assert "Unresolved allegation" in canvas
    assert "Missing-fact basis" in canvas
    assert "sourceContextAttributes" in canvas
    assert "page: detail.page || 1," in canvas


def test_later_memory_presentation_fails_closed_without_validated_bridge() -> None:
    assets = release_tool.REPOSITORY / "casepath" / "assets"
    canvas = (assets / "artifact-canvas.js").read_text(encoding="utf-8")
    flagship_renderer = (assets / "live-v16.js").read_text(encoding="utf-8")
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")
    later_result_start = flagship_renderer.index("  function renderLaterResult()")
    later_result_end = flagship_renderer.index(
        "\n  function restartDemo()", later_result_start
    )
    later_result = flagship_renderer[later_result_start:later_result_end]

    assert "casepath:later-memory-validation" in flagship_renderer
    assert "casepath.later-memory-validation/1.0.0" in flagship_renderer
    assert "validatedMemoryPresentation ? applicationHash : ''" in flagship_renderer
    assert "validatedMemoryPresentation ? memoryOriginId : ''" in flagship_renderer
    assert "? { nodeIds: normalizedNodeIds, edges: normalizedEdges, evidenceIds: normalizedEvidenceIds }" in flagship_renderer
    assert later_result.index("casepath:later-memory-validation") < later_result.index(
        "announceRender('later-result')"
    )
    assert "function validatedLaterMemory()" in canvas
    assert "root.dataset.laterMemoryValidated = String(Boolean(validatedMemory));" in canvas
    assert "root.dataset.laterMemoryApplicationHash = validatedMemory?.applicationHash || '';" in canvas
    assert "No memory-driven process change is claimed." in canvas
    assert "state.moment === 'later-result' && receipt && memoryOriginId" in canvas
    assert "function laterMemoryPresentationContractViolations" in browser_gate
    assert "const laterResult = laterRun?.result || {};" in browser_gate
    assert "laterGraphScene, later, true" in browser_gate
    assert "Later-memory presentation with a forged run envelope was accepted" in browser_gate
    assert "Fail-closed presentation with visible memory effects was accepted" in browser_gate


def test_process_decisions_integrate_exact_sources_law_and_node_commit() -> None:
    assets = release_tool.REPOSITORY / "casepath" / "assets"
    canvas = (assets / "artifact-canvas.js").read_text(encoding="utf-8")
    canvas_css = (assets / "artifact-canvas.css").read_text(encoding="utf-8")
    live_events = (
        release_tool.REPOSITORY / "casepath-api" / "casepath_api" / "live_events.py"
    ).read_text(encoding="utf-8")
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")

    assert "casepath.decision-flow/1.0.0" in canvas
    assert "function directFactsForNode(node)" in canvas
    assert "function nodeDecisionTrace(node)" in canvas
    assert "if (['responsibility', 'remedy', 'escalation', 'resolution'].includes(node?.node_id)) return [];" in canvas
    assert "const steps = nodeDecisionTrace(node);" in canvas
    assert "stepKind: 'accepted-fact'" in canvas
    assert "stepKind: 'accepted-law'" in canvas
    assert "function carriedAcceptedFactSourceMarkup(fact, ref)" in canvas
    assert "Source already checked · carried forward with this fact" in canvas
    assert 'data-carried-source-locator-id' in canvas
    assert ".ac-carried-source-highlight" in canvas_css
    assert ".ac-decision-basis.has-verified-source" in canvas_css
    assert "presentationMode: 'returned-action-replay'" in canvas
    assert "decisionModelContributionAccepted" in canvas
    assert "basisEventId" in canvas
    assert "const structureLineage = lineageFor('process_node', node?.node_id);" in canvas
    assert "const decisionLineage = lineageFor('process_decision', node?.node_id);" in canvas
    assert "const decisionAgentVisible = ['combining', 'decision-ready'].includes(phase)" in canvas
    assert "structureEventId: structureLineage?.eventId || ''" in canvas
    assert '"type": "process_decision.accepted"' in live_events
    assert '"model_owned_fields": ["decision_value"]' in live_events
    assert '"type": "process_node.created"' in live_events
    assert '"type": "evidence_fields.accepted"' in live_events
    assert '"type": "evidence_requirement.linked"' in live_events
    assert 'data-decision-workspace' in canvas
    assert 'data-decision-plan' in canvas
    assert 'data-decision-plan-item' in canvas
    assert "data-plan-kind=\"${waitingCopy ? 'waiting-decision' : 'evidence-decision'}\"" in canvas
    assert 'data-decision-waiting-basis' in canvas
    assert "responsibility: ['Waiting for an earlier answer', 'Cause must be known first.']" in canvas
    assert "remedy: ['Waiting for an earlier answer', 'Responsibility must be known first.']" in canvas
    assert "resolution: ['Waiting for an earlier answer', 'The action must be complete first.']" in canvas
    assert 'data-real-artifact="true"' in canvas
    assert 'data-extracted-fragment' in canvas
    assert 'data-fact-combination' in canvas
    assert "state.decisionFlowPhase = 'read-source'" in canvas
    assert "state.decisionFlowPhase = 'highlight-source'" in canvas
    assert "emitInteraction('confirm-source', inspectionTarget)" in canvas
    assert "casepath:source-highlighted" in canvas
    assert "casepath:decision-flow-step" in canvas
    assert "const DECISION_SOURCE_PREVIEW_HOLD_MS = 5200;" in canvas
    assert "const DECISION_SOURCE_HOLD_MS = 6800;" in canvas
    assert "const DECISION_SOURCE_MAX_HOLD_MS = 11200;" in canvas
    assert 'data-ac-action="advance-decision-flow"' not in canvas
    assert "const DECISION_COMBINE_HOLD_MS = 3000;" in canvas
    assert "const DECISION_READY_HOLD_MS = 2200;" in canvas
    assert "const MIN_DECISION_SOURCE_PREVIEW_HOLD_MS = 5100;" in browser_gate
    assert "const MIN_DECISION_SOURCE_HOLD_MS = 6700;" in browser_gate
    assert "const MIN_DECISION_COMBINE_HOLD_MS = 2900;" in browser_gate
    assert "const MIN_DECISION_READY_HOLD_MS = 2100;" in browser_gate
    assert "Numeric progress remains machine-readable only." in canvas_css
    assert ".casepath-artifact-canvas .ac-process-node-progress{\n  display:none!important;" in canvas_css
    assert '.ac-agent-cursor[data-process-node-progress="active"]>.ac-cursor-role-icon:after' in canvas_css
    assert (
        '.casepath-artifact-canvas[data-graph-inspecting="true"] '
        '.ac-process-track li[data-process-build-state="built"]{' in canvas_css
    )
    assert (
        '.casepath-artifact-canvas[data-graph-inspecting="true"] '
        '.ac-spatial-edges path:not([data-source-proof="true"]){' in canvas_css
    )
    assert (
        '.casepath-artifact-canvas .ac-spatial-viewport:has('
        '.ac-spatial-detail .ac-node-source-preview[data-node-attachment-kind="fact"])::after{'
        in canvas_css
    )
    assert 'height:78%;\n  background:linear-gradient(to bottom' in canvas_css
    complete_start = canvas.index("      const completeDecision = () => {")
    complete_end = canvas.index("      const prepareStep = index => {", complete_start)
    complete_flow = canvas[complete_start:complete_end]
    assert complete_flow.index("clearProcessNodeProgress();") < complete_flow.index(
        "state.decisionFlowPhase = 'receding';"
    )
    after_recede_start = complete_flow.index("              const afterRecede = () => {")
    after_recede_end = complete_flow.index("              plan.addEventListener('transitionend'", after_recede_start)
    after_recede = complete_flow[after_recede_start:after_recede_end]
    assert after_recede.index("plan.dataset.planPhase = 'receded';") < after_recede.index(
        "emitDecisionFlowStep(node, null, 'plan-receded', 100)"
    ) < after_recede.index("commitNode();")
    receding_start = complete_flow.index(
        "              window.requestAnimationFrame(() => {\n                state.decisionFlowPhase = 'receding';"
    )
    receding_flow = complete_flow[receding_start:]
    assert receding_flow.index("plan.dataset.planPhase = 'receding';") < receding_flow.index(
        "emitDecisionFlowStep(node, null, 'plan-receding', 100)"
    ) < receding_flow.index("window.setTimeout(afterRecede")
    assert "event.target === plan && event.propertyName === 'opacity'" in complete_flow

    assert "function decisionFlowContractViolations" in browser_gate
    assert "function factSourceTourContractViolations" in browser_gate
    assert "function officialLawTourContractViolations" in browser_gate
    assert "function acceptedExecutionFieldOwnershipViolations" in browser_gate
    assert "window.__casepathDecisionFlowSteps = []" in browser_gate
    assert "window.__casepathFactTourSnapshots = []" in browser_gate
    assert "window.__casepathCaptureFactTour" in browser_gate
    assert "window.addEventListener('casepath:decision-flow-step'" in browser_gate
    assert "fact tour does not show the exact eight returned facts in order" in browser_gate
    assert "official-law tour does not show the exact four returned registry sources in order" in browser_gate
    assert "graph plan does not reuse the accepted fact and checked-law trace" in browser_gate
    assert "graph decision replay reopens a source or law instead of reusing accepted trace" in browser_gate
    assert "accepted fact replay is not bound to the exact returned fact event" in browser_gate
    assert "checked-law replay is not bound to the deterministic official registry event" in browser_gate
    assert "decision replay is not bound to its run-scoped accepted execution trace and visible mode label" in browser_gate
    assert "process structure event lacks neutral accepted execution-trace lineage" in browser_gate
    assert "process model identity is not limited to the accepted decision_value event" in browser_gate
    assert "accepted decision_value is not bound to the merged Path builder workstream and exact process receipt" in browser_gate
    assert "accepted input or structural replay inherited a model identity" in browser_gate
    assert "fact assertion ownership is not exact" in browser_gate
    assert "Document finder is not limited to exact accepted status/artifact_ids fields" in browser_gate
    assert "modelSelectedTextRefs" in browser_gate
    assert "linkedModelContributionIds" in browser_gate
    assert "linkedModelFields" in browser_gate
    assert "structureEventId: detail.structureEventId || ''" in browser_gate
    assert "blocked downstream step invents accepted input work before causation is resolved" in browser_gate
    assert "live plan kind does not match the decision state" in browser_gate
    assert "unresolved downstream decision does not show its exact plain dependency" in browser_gate
    assert "source is not neutral before it opens" in browser_gate
    assert "exact returned artifact is not visibly open before selection" in browser_gate
    assert "exact returned locator was not visibly selected before the fact appeared" in browser_gate
    assert "exact returned fact does not visibly follow its selected source" in browser_gate
    assert "live plan is not the one minimal accepted-input-to-decision checklist" in browser_gate
    assert "progress is not hidden while the live plan recedes before node creation" in browser_gate
    assert "live plan does not finish receding before node creation" in browser_gate
    assert "accepted node appears before progress and plan have cleared" in browser_gate
    assert "notification decision does not reuse the accepted fact with two email locators and one delivery locator" in browser_gate
    assert "notification decision does not reuse the checked deterministic Article 257g registry trace" in browser_gate
    assert "Wed, 15 Jul 2026 08:32:00 +0200" in browser_gate
    assert "Please arrange an inspection and repair." in browser_gate
    assert "Accepted by recipient mail server" in browser_gate
    assert "Valid accepted-input decision-flow fixture was rejected" in browser_gate
    assert "Graph replay with an invented new source read was accepted" in browser_gate
    assert "Valid eight-fact returned source replay fixture was rejected" in browser_gate
    assert "Fact tour with a forged source locator was accepted" in browser_gate
    assert "Accepted node with a lingering plan was accepted" in browser_gate
    assert "Blocked downstream decision without its waiting basis was accepted" in browser_gate
    assert "function factSourceCinematicContractViolations" not in browser_gate


def test_decision_pacing_automatically_holds_source_highlight_and_reasoning() -> None:
    repository = release_tool.REPOSITORY
    canvas = (repository / "casepath" / "assets" / "artifact-canvas.js").read_text(
        encoding="utf-8"
    )
    canvas_css = (
        repository / "casepath" / "assets" / "artifact-canvas.css"
    ).read_text(encoding="utf-8")
    browser_gate = (
        repository / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")
    runtime = (repository / "casepath" / "assets" / "live-v16.js").read_text(
        encoding="utf-8"
    )

    assert "function decisionSourceHoldMs(...values)" in canvas
    assert "function decisionCombineHoldMs(stepCount, fragmentCount)" in canvas
    assert "const sourceHoldMs = decisionSourceHoldMs(" in canvas
    assert "}, sourceHoldMs);" in canvas
    assert "const settleDelayMs = isDecisionSourceReading" in canvas
    assert "const baseSettleDelayMs = REDUCED_MOTION ? 0 : CURSOR_SETTLE_MS;" in canvas
    assert "? DECISION_SOURCE_PREVIEW_HOLD_MS + baseSettleDelayMs" in canvas
    assert "? decisionCombineHoldMs(steps.length, state.decisionFlowFragments.length)" in canvas
    assert 'class="ac-decision-reader-continue"' not in canvas
    assert 'data-ac-action="advance-decision-flow"' not in canvas
    assert "const expectedPhases = planned.flatMap(() => ['planned', 'source-opened', 'fragment-extracted'])" in browser_gate
    assert "MIN_DECISION_SOURCE_PREVIEW_HOLD_MS" in browser_gate
    assert "MIN_DECISION_SOURCE_HOLD_MS" in browser_gate
    assert "MIN_DECISION_COMBINE_HOLD_MS" in browser_gate
    assert "MIN_DECISION_READY_HOLD_MS" in browser_gate
    assert "exact source is not readable before its passage is highlighted" in browser_gate
    assert "accepted input is not readable before the next reasoning step" in browser_gate
    assert "source highlights do not remain visible while the decision is formed" in browser_gate
    assert "completed decision does not remain readable before node commit begins" in browser_gate
    assert "keeps its highlighted passage readable, forms the decision, and only then commits the node" in browser_gate
    assert "Rushed exact-source preview was accepted" in browser_gate
    assert "Rushed highlighted passage was accepted" in browser_gate
    assert "Rushed source-to-decision formation was accepted" in browser_gate
    assert "Rushed completed-decision hold was accepted" in browser_gate
    assert "Automatic decision replay with a reader CTA was accepted" in browser_gate
    assert "Reduced-motion semantic decision sequence was rejected" in browser_gate
    assert "Reduced-motion sequence without a highlighted passage was accepted" in browser_gate
    assert "reducedMotion: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true" in browser_gate
    assert "window.addEventListener('casepath:decision-flow-step', onProgress);" in runtime
    assert "window.removeEventListener('casepath:decision-flow-step', onProgress);" in runtime
    assert "if (String(event.detail?.runId || '') === runId) armTimeout();" in runtime
    assert '--ac-decision-chapter:"1 of 3  ·  Read the exact source"' in canvas_css
    assert '--ac-decision-chapter:"2 of 3  ·  Keep only what the source proves"' in canvas_css
    assert '--ac-decision-chapter:"3 of 3  ·  Form the decision"' in canvas_css
    assert '--ac-decision-chapter:"Decision ready  ·  Add the grounded node"' in canvas_css
    assert "@media(prefers-reduced-motion:reduce)" in canvas_css
    assert "animation:none!important;" in canvas_css


def test_opening_claim_card_is_compact_and_source_derived() -> None:
    repository = release_tool.REPOSITORY
    index = (repository / "casepath" / "index.html").read_text(encoding="utf-8")
    canvas_css = (repository / "casepath" / "assets" / "artifact-canvas.css").read_text(encoding="utf-8")
    demo_data = (repository / "casepath-api" / "casepath_api" / "data.py").read_text(encoding="utf-8")
    browser_gate = (repository / "casepath-qa" / "browser-focused-v20.mjs").read_text(encoding="utf-8")

    card_start = index.index('<article class="start-claim-source" data-opening-claim-source="message"')
    card_end = index.index("</article>", card_start)
    card = index[card_start:card_end]
    subject = "Bedroom condition keeps returning"
    problem = "The mould in the external corner of our bedroom keeps coming back."
    outcome = "Please tell me what should happen next. I want the cause clarified and the defect repaired."
    assert f"<strong>{subject}</strong>" in card
    assert f"<blockquote>{problem}</blockquote>" in card
    assert f"<p>{outcome}</p>" in card
    assert card.count("<blockquote>") == 1
    assert card.count("<p>") == 1
    assert all(value in demo_data for value in (subject, problem, outcome))
    assert "Opening truth: two exact source excerpts, not a generated claim summary." in canvas_css
    assert "width:min(620px,100%);" in canvas_css
    assert "function openingClaimCardContractViolations" in browser_gate
    assert "opening problem sentence is not the exact claim-message sentence" in browser_gate
    assert "opening requested outcome is not the exact claim-message request" in browser_gate
    assert "opening claim card adds generated summary prose" in browser_gate
    assert "Opening shows one compact source-derived claim card" in browser_gate
    assert "Generated opening claim summary fixture was accepted" in browser_gate
    assert "Large-prose opening claim card fixture was accepted" in browser_gate


def test_reference_path_audit_persists_exact_decision_actions() -> None:
    repository = release_tool.REPOSITORY
    canvas = (repository / "casepath" / "assets" / "artifact-canvas.js").read_text(encoding="utf-8")
    canvas_css = (repository / "casepath" / "assets" / "artifact-canvas.css").read_text(encoding="utf-8")
    browser_gate = (repository / "casepath-qa" / "browser-focused-v20.mjs").read_text(encoding="utf-8")

    assert "decisionFlowAuditEvents: []" in canvas
    assert "state.decisionFlowAuditEvents = [];" in canvas
    assert "if (['source-opened', 'fragment-extracted', 'plan-receded'].includes(phase))" in canvas
    assert "state.decisionFlowAuditEvents.push({ ...detail });" in canvas
    assert "function referenceReplayHistoryMarkup(agentId)" in canvas
    assert "if (agentId !== 'process_decision_mapping') return '';" in canvas
    assert "data-reference-action-history" in canvas
    assert "data-reference-action-phase=" in canvas
    assert "data-source-locator-id=" in canvas
    assert "data-reference-action-provenance" in canvas
    assert "No provider call · accepted reference output replay" in canvas
    assert "reference-replay-actions" in canvas
    assert "No agent calls were made" not in canvas
    assert ".casepath-artifact-canvas .ac-reference-action-history{" in canvas_css
    assert ".casepath-artifact-canvas .ac-reference-action-provenance{" in canvas_css
    assert "reference Path audit actions do not equal the exact persisted decision flow" in browser_gate
    assert "reference Path audit provenance footer is absent or inexact" in browser_gate
    assert "primary reference Path audit falls back to No agent calls were made" in browser_gate
    assert "Reference Path history missing a decision action was accepted" in browser_gate


def test_claim_reader_live_wait_uses_one_call_bound_plan() -> None:
    repository = release_tool.REPOSITORY
    canvas = (repository / "casepath" / "assets" / "artifact-canvas.js").read_text(encoding="utf-8")
    canvas_css = (repository / "casepath" / "assets" / "artifact-canvas.css").read_text(encoding="utf-8")
    live = (repository / "casepath" / "assets" / "live-v16.js").read_text(encoding="utf-8")
    browser_gate = (repository / "casepath-qa" / "browser-focused-v20.mjs").read_text(encoding="utf-8")

    assert "const LIVE_WORK_PLAN_CONTRACT = 'casepath.live-work-plan/1.0.0';" in canvas
    assert "liveModelCall: null" in canvas
    assert "function liveWorkingCall()" in canvas
    assert "function liveWorkPlanMarkup()" in canvas
    assert "data-ac-live-work-plan" in canvas
    assert 'data-contract="${LIVE_WORK_PLAN_CONTRACT}"' in canvas
    assert 'data-run-id="${esc(call.runId)}"' in canvas
    assert 'data-call-id="${esc(call.callId)}"' in canvas
    assert 'data-event-id="${esc(call.eventId)}"' in canvas
    assert "['package', 'Claim package ready', 'complete']" in canvas
    assert "['choose', 'Read exact source', 'active']" in canvas
    assert "['return', 'Return supported facts', 'waiting']" in canvas
    assert 'data-visible-agent-group="${esc(visibleAgentGroupId(call.agentId))}"' in canvas
    assert "state.currentEvent = null;" in canvas
    assert "if (!agent || !SUCCESS_STATES.has(eventStatus(event))) return '';" in canvas
    assert 'data-work-state="${esc(call.status)}"' in canvas
    assert ".ac-live-work-plan" in canvas_css
    assert "inputArtifact: returnedValue(event, 'input_artifact')" in live
    assert "function canonicalFactsLiveWorkPlanContractViolations" in browser_gate
    assert "separate source-to-fact tour remains outside the merged Path builder graph flow" in browser_gate
    live_plan_start = canvas.index("  function liveWorkPlanMarkup()")
    live_plan_end = canvas.index("\n  function stageFocalMarkup()", live_plan_start)
    live_plan = canvas[live_plan_start:live_plan_end]
    assert "%" not in live_plan
    assert "progressbar" not in live_plan
    assert "sourcePreludeMarkup" not in live_plan


def test_default_reference_surface_hides_ranking_numbers_but_keeps_audit_truth() -> None:
    assets = release_tool.REPOSITORY / "casepath" / "assets"
    canvas = (assets / "artifact-canvas.js").read_text(encoding="utf-8")
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")

    reference_start = canvas.index("  function referenceStageMarkup(copy)")
    reference_end = canvas.index("\n  function agentArtifactMarkup()", reference_start)
    reference_surface = canvas[reference_start:reference_end]
    graph_reference_start = canvas.index("  function graphReferenceDetailMarkup(node)")
    graph_reference_end = canvas.index("\n  function spatialDetailMarkup(node)", graph_reference_start)
    graph_reference_surface = canvas[graph_reference_start:graph_reference_end]
    assert "data-ranking-contract=" in reference_surface
    assert "data-ranking-rank=" in reference_surface
    assert "data-ranking-score-basis-points=" in reference_surface
    assert "data-ranking-context-hash=" in reference_surface
    assert "Rank ${esc(" not in reference_surface
    assert "points</strong>" not in reference_surface
    assert "data-ranking-contract=" in graph_reference_surface
    assert "data-ranking-rank=" in graph_reference_surface
    assert "data-ranking-score-basis-points=" in graph_reference_surface
    assert "Rank ${esc(" not in graph_reference_surface
    assert "points</strong>" not in graph_reference_surface
    assert "precedentRankingContractViolations" in browser_gate
    assert "candidate_scores" in browser_gate
    assert "score_basis_points" in browser_gate


def test_flagship_timing_gate_keeps_readable_holds_without_capping_provider_latency() -> None:
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")
    assert "const MIN_FLAGSHIP_PRESENTATION_MS = 90000;" in browser_gate
    assert "const MAX_FLAGSHIP_PRESENTATION_MS = 330000;" in browser_gate
    assert "MIN_PRODUCTION_FLAGSHIP_PRESENTATION_MS" not in browser_gate
    assert "routeStory.flagshipCausation ? MIN_FLAGSHIP_PRESENTATION_MS : 30000" in browser_gate
    assert "const presentationUpperBoundApplies = !isProductionJourney();" in browser_gate
    assert "!presentationUpperBoundApplies || flagshipPresentationMs <= MAX_FLAGSHIP_PRESENTATION_MS" in browser_gate
    assert "without treating real provider latency as presentation failure" in browser_gate


def test_flagship_surface_is_one_persistent_source_plus_artifact_canvas() -> None:
    assets = release_tool.REPOSITORY / "casepath" / "assets"
    canvas = (assets / "artifact-canvas.js").read_text(encoding="utf-8")
    canvas_css = (assets / "artifact-canvas.css").read_text(encoding="utf-8")
    runtime = (assets / "live-v16.js").read_text(encoding="utf-8")
    index = (release_tool.REPOSITORY / "casepath" / "index.html").read_text(
        encoding="utf-8"
    )
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")

    assert "const ROOT_ID = 'artifactCanvas'" in canvas
    assert "root.id = ROOT_ID" in canvas
    assert 'id="artifactProcessGraph"' in canvas
    assert "root.dataset.layout = 'source-canvas'" in canvas
    assert "dataArtifactFocus" in canvas or "data-artifact-focus" in canvas
    assert "dataCasepathPrimaryArtifact" in canvas or "data-casepath-primary-artifact" in canvas
    assert "dataCasepathPrimaryAction" in canvas or "data-casepath-primary-action" in canvas
    assert "journeyNext.dataset.casepathPrimaryAction = 'true'" in canvas
    assert "!node.closest('#artifactCanvas')" in (
        assets / "live-v20-focus.js"
    ).read_text(encoding="utf-8")
    assert "valueFrom(memory?.source_memory, 'memory_id')" in canvas
    assert "flagship-spine/1" in canvas
    assert all(node_id in canvas for node_id in (
        "intake", "scope", "dispute", "urgency", "notification", "defect",
        "causation", "responsibility", "remedy", "resolution",
    ))
    assert "pending" in canvas and "building" in canvas and "built" in canvas
    assert "window.addEventListener('casepath:graph-step'" not in canvas
    assert "!state.graphRevealRunning && !state.graphDwell" in canvas
    assert "source-canvas" in canvas_css
    assert ".casepath-artifact-canvas" in canvas_css
    assert '.casepath-artifact-canvas .ac-team{\n  display:flex;' in canvas_css
    assert '[data-casepath-moment="start"] .email-body' in canvas_css
    assert ".customer-email," in canvas_css
    assert "display:none!important" in canvas_css
    assert "start-claim-summary" not in index
    assert "Management alleges insufficient ventilation and declines inspection" not in index
    assert "assets/artifact-canvas.css" in index
    assert "assets/artifact-canvas.js" in index
    assert "location.protocol === 'file:'" in index
    assert 'id="localFileLaunch"' in index
    assert 'href="http://127.0.0.1:4173/"' in index
    assert "./bin/casepath dev" in index
    assert "Claim sources are still loading." in runtime
    assert _content_bound_asset_locator("artifact-canvas.css") in index
    assert _content_bound_asset_locator("artifact-canvas.js") in index
    assert "state.moment === 'understand' && state.factTourRunning" in canvas
    assert "finishFactSourceTour(items);" in canvas
    assert "return factSourceStageMarkup(copy);" in canvas
    assert "const CURSOR_AVATARS = Object.freeze({" in canvas
    assert "data-ac-cursor-avatar" in canvas
    assert "function setCursorAvatar(" in canvas
    assert all(f"{signature}: '<" in canvas for signature in (
        "facts", "orchestrator", "sources", "process", "evidence", "audit",
    ))
    assert "const SOURCE_TYPE_ICONS = Object.freeze({" in canvas
    assert "const staticAttachmentCount = document.querySelectorAll('.attachment-row[data-artifact-id]').length;" in canvas
    assert "const sourceCount = (artifacts.length || staticAttachmentCount) + 1;" in canvas
    assert 'class="ac-source-prelude-plan"' in canvas
    assert "ac-source-prelude-strip" not in canvas[canvas.index("  function sourcePreludeMarkup("):canvas.index("\n  function sourceTrailKind(")]
    assert 'data-source-exact-control="true"' in canvas
    assert 'data-source-exact-mark="true"' in canvas
    assert '<p>${esc(agent.why)}</p>' not in canvas
    assert 'data-agent-history-accepted-ids' in canvas
    assert 'data-agent-history-rejections' in canvas
    assert 'data-rejected-item-id=' in canvas
    assert "Opening uses one calm three-step Path builder plan instead of seven competing source cards" in browser_gate
    assert "Four visible workstream icons retain all six exact call-bound runtime identities beneath them" in browser_gate
    assert "Each visible specialist opens an exact call-bound history; reference replay keeps the exact Path actions" in browser_gate
    assert "Main focal work never shows a large generic agent why paragraph" in browser_gate
    assert "No separate eight-fact presentation competes with the merged Path builder graph flow" in browser_gate
    assert "Separate source-to-fact presentation outside the Path builder graph flow was accepted" in browser_gate
    assert 'data-decision-workspace' in canvas
    assert 'data-decision-plan' in canvas
    assert ".ac-decision-workspace" in canvas_css
    assert ".ac-decision-plan" in canvas_css
    assert '.ac-source-page-excerpt>button.ac-source-exact-control[data-source-exact-control="true"]' in canvas_css
    assert '.ac-source-page-excerpt>mark.ac-source-exact-mark.is-highlighted[data-source-exact-mark="true"]' in canvas_css
    assert "separate source-to-fact tour remains outside the merged Path builder graph flow" in browser_gate
    assert "graph decision replay reopens a source or law instead of reusing accepted trace" in browser_gate
    assert index.index("assets/process-story.js") < index.index("assets/artifact-canvas.js")
    assert "source claim and work canvas are not simultaneously visible" in browser_gate
    assert "artifact canvas root was replaced" in browser_gate
    assert "process graph root was replaced" in browser_gate
    assert "primary artifact count" in browser_gate
    assert "primary action count" in browser_gate
    assert "only the returned route story monotonically" in browser_gate


def test_flagship_process_is_a_truthful_accessible_spatial_graph() -> None:
    assets = release_tool.REPOSITORY / "casepath" / "assets"
    canvas = (assets / "artifact-canvas.js").read_text(encoding="utf-8")
    canvas_css = (assets / "artifact-canvas.css").read_text(encoding="utf-8")
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")

    assert "SPATIAL_SPINE_POSITIONS" in canvas
    assert "CAUSATION_BRANCH_LAYOUT" in canvas
    assert all(branch_id in canvas for branch_id in (
        "building_defect", "tenant_use", "mixed_cause", "evidence_gap",
    ))
    assert 'data-spatial-canvas="claim-handling-process"' in canvas
    assert 'data-spatial-role="branch"' in canvas
    assert 'data-spatial-role="law"' in canvas
    assert 'data-spatial-role="evidence"' in canvas
    assert 'data-spatial-next-action="true"' in canvas
    assert "data-spatial-edge" in canvas
    assert "data-edge-source" in canvas and "data-edge-target" in canvas
    assert "state.process?.edges" in canvas
    assert "data-active-focal-path" in canvas
    assert "data-basis-fact-ids" in canvas
    assert "data-basis-law-ids" in canvas
    assert "data-basis-evidence-requirement-ids" in canvas
    assert 'role="status" aria-live="polite" aria-atomic="true"' in canvas
    assert "setAttribute('aria-current', 'step')" in canvas
    assert "tabIndex = state.visibleNodeIds.has(node.node_id) ? 0 : -1" in canvas
    assert 'aria-hidden="true" focusable="false" data-ac-spatial-edges' in canvas
    assert "const GRAPH_NODE_DWELL_MS = 900;" in canvas
    assert "const GRAPH_SOURCE_DWELL_MS = 1900;" in canvas
    assert "const GRAPH_BRANCH_SOURCE_DWELL_MS = 1900;" in canvas
    assert "casepath.process-node-progress/1.0.0" in canvas
    assert "visible_evidence_bound_construction" in canvas
    assert "casepath:process-node-progress" in canvas
    assert "data-ac-process-node-progress" in canvas
    assert ".ac-process-node-progress" in canvas_css
    assert '.ac-spatial-branch:not([data-branch-state="selected"]){\n  opacity:1;' in canvas_css
    assert "border-color:#d4d8de;\n  color:#626873;" in canvas_css
    assert canvas_css.count("color:#6b727c;") >= 3
    assert "setProcessNodeProgress('search', searchProgress" in canvas
    assert "setProcessNodeProgress('read', progress)" in canvas
    assert "setProcessNodeProgress('extract', progress)" in canvas
    assert "setProcessNodeProgress('form', 90" in canvas
    assert "setProcessNodeProgress('complete', 100" in canvas
    progress_finish = canvas.index("function finishProcessNodeProgress")
    progress_clear = canvas.index("clearProcessNodeProgress();", progress_finish)
    progress_commit = canvas.index("window.setTimeout(commit, clearGapMs);", progress_finish)
    assert progress_clear < progress_commit
    assert 'data-ac-inspection-target="true"' in canvas
    assert 'data-inspection-phase="${esc(state.graphInspectionPhase)}"' in canvas
    assert "state.graphInspectionPhase = 'highlight-source'" in canvas
    assert "casepath:source-highlighted" in canvas
    assert "casepath:source-inspection" in canvas
    assert "casepath:branch-visualized" in canvas
    assert "ac-grounding-disclosure" in canvas
    assert 'class="ac-node-source-preview' in canvas
    assert "function sourceTextWindow(ref)" in canvas
    assert "/api/artifacts/${encodeURIComponent(sourceId)}/extraction" in canvas
    assert "sourceWindow.before" in canvas and "sourceWindow.after" in canvas
    assert "artifact?.description" not in canvas
    assert "Context ·" not in canvas
    assert "const packageActive = ['message', 'intake'].includes(sourceId);" in canvas
    assert "sourcePackage.dataset.activeSourceId = sourceId;" in canvas
    assert "sourcePackage.setAttribute('aria-current', 'true');" in canvas
    assert "Open original →" in canvas
    assert "data-ac-action=\"toggle-grounding\"" in canvas
    assert 'data-grounding-open="false"' in canvas
    assert 'aria-haspopup="dialog" aria-expanded="false"' in canvas
    assert 'data-ac-grounding-viewer' in canvas
    assert "detail.innerHTML = panel.innerHTML;" in canvas
    assert "if (!viewer.open) viewer.showModal();" in canvas
    assert "state.root.querySelector('[data-ac-grounding-viewer]')?.close();" in canvas
    assert "data-ac-law-viewer" in canvas
    assert "Cached official Swiss-law passage · qualified review pending" in canvas
    assert ".ac-law-viewer" in canvas_css
    assert "if (state.moment === 'experience') return graphReferenceDetailMarkup(node)" in canvas
    assert "Inspect this generated pattern" in canvas
    assert "['verify', 'review', 'review-applied', 'knowledge', 'later-work', 'later-result']" in canvas
    assert "['official_statute', 'official_guidance'].includes(law?.source_type)" in canvas
    assert "const CURSOR_TRAVEL_MS = 620;" in canvas
    assert "const FACT_NEUTRAL_READ_DWELL_MS = 900;" in canvas
    assert "sourceRailTarget(target.dataset.sourceId)" in canvas
    assert "x > viewportWidth * .56" in canvas
    assert "position:fixed;" in canvas_css
    assert "state.lastCursorKey = '';\n        scheduleCursor();" in canvas
    assert 'class="ac-authority-line"' not in canvas
    assert "data-ac-proof" not in canvas
    assert "renderProofLine" not in canvas
    assert ".ac-authority-line" not in canvas_css
    assert canvas.count("document.querySelectorAll('.is-agent-clicked').forEach") >= 2
    assert "const CURSOR_SETTLE_MS = 260;" in canvas
    assert canvas.count("REDUCED_MOTION ? 0 : CURSOR_TRAVEL_MS") == 1
    assert canvas.count("REDUCED_MOTION ? 0 : CURSOR_SETTLE_MS") == 1
    assert 'class="ac-cursor-park"' in canvas
    assert "const parked = ['review-applied', 'knowledge', 'later-result'].includes(state.moment);" in canvas
    assert "cursor.dataset.parked = String(parked);" in canvas
    assert "if (parked) return;" in canvas
    assert ".casepath-artifact-canvas .ac-process>.ac-cursor-park{" in canvas_css
    assert '.casepath-artifact-canvas .ac-agent-cursor[data-parked="true"] .ac-agent-cursor-label{\n  opacity:0;' in canvas_css
    assert 'data-ac-action="open-documents"' in canvas
    assert "Documents created by this decision" in canvas
    assert "Causation is unresolved" in canvas
    assert "See all ${checklistCount} across the process" in canvas
    assert "const CONCISE_GRAPH_STAGES = new Set(['evidence', 'experience', 'verify']);" in (
        assets / "live-v16.js"
    ).read_text(encoding="utf-8")
    assert "const concise = ['evidence', 'experience', 'verify'].includes(moment);" in browser_gate
    live_v17 = (assets / "live-v17.js").read_text(encoding="utf-8")
    focus_v20 = (assets / "live-v20-focus.js").read_text(encoding="utf-8")
    assert "toggle.dataset.sourceIds = 'message,intake';" in focus_v20
    assert live_v17.index("title: 'Needed next'") < live_v17.index("title: 'Already available'")
    assert "Only if a branch becomes relevant" in live_v17
    assert 'class="v17-checklist-technical"' in live_v17
    assert "<small>Process question</small>" in focus_v20
    assert "<small>Fact to establish</small>" in focus_v20
    assert "<small>Evidence needed</small>" in focus_v20
    assert "<small>Document or record</small>" in focus_v20
    assert 'data-document-model="complete-claim-record"' in focus_v20
    assert 'data-document-group="${esc(kind)}"' in focus_v20
    assert "const groupMarkup = ['needed', 'available', 'conditional', 'not-needed']" in focus_v20
    assert 'data-document-status="${esc(statusPresentation.state)}"' in focus_v20
    assert "{ state: 'received', icon: '✓', label: 'Received' }" in focus_v20
    assert "{ state: 'missing', icon: '×', label: status === 'provided_insufficient' ? 'Incomplete' : 'Missing' }" in focus_v20
    assert "copy.className = 'v17-checklist-item v20-document-chain'" in focus_v20
    assert 'data-evidence-title=' in live_v17
    assert 'data-document-options=' in live_v17
    assert 'data-artifact-ids=' in live_v17
    assert "const evidenceTitle = copy.dataset.evidenceTitle" in focus_v20
    assert "const documentChoices = returnedDocuments.length ? returnedDocuments : documentOptions" in focus_v20
    assert 'data-chain-part="decision"' in focus_v20
    assert 'data-chain-part="fact"' in focus_v20
    assert 'data-chain-part="evidence"' in focus_v20
    assert 'data-chain-part="document"' in focus_v20
    assert 'data-v20-document-filter="needed"' in focus_v20
    assert "const selectedNodeId = '';" in focus_v20
    assert '#artifactProcessGraph [data-ac-action="select-node"]' in focus_v20
    assert "Document plan contains each of the exact 21 returned checklist items once" in browser_gate
    assert "Claim documents opens as the complete 21-item evidence model with no hidden node filter" in browser_gate
    assert "All 21 requirements visibly partition into exact status groups with needed first and missing or received icons" in browser_gate
    assert "Every document row preserves process question to fact to evidence to document to status in that order" in browser_gate
    assert "Evidence needs and document forms are not reversed" in browser_gate
    assert "Each document chain preserves exact returned primary owner, ordered owners, path, fact, status, and item identity" in browser_gate
    assert "Document chain returns to its exact graph node and no competing decision" in browser_gate
    assert "function zoomOutDesktopContractViolations" in browser_gate
    assert "REQUIRED_DESKTOP_SOURCE_MOMENTS" in browser_gate
    assert "window.__casepathCaptureDesktopSourcePanel" in browser_gate
    assert "toggleLooksDropdown" in browser_gate
    assert "processNodeSourcePreviews" in browser_gate
    assert "postConstructionSourceUse" in browser_gate
    assert "document.querySelectorAll('[data-source-rail-item][data-source-id]')" in browser_gate
    assert "target.classList.contains('is-active')" in browser_gate
    assert "window.__casepathActiveSourceIds" in browser_gate
    assert "window.__casepathSourceTargetExists" in browser_gate
    assert "inspectionSourceHasTarget" in browser_gate
    assert "sourceHasTarget" in browser_gate
    assert "basisKind" in browser_gate
    assert "exactLocator" in browser_gate
    assert "exactTitle" in browser_gate
    assert "exactLocation" in browser_gate
    assert "sourceWindowTruth" in browser_gate
    assert "noGeneratedContext" in browser_gate
    assert "exactPassage" in browser_gate
    assert "Graph replay with a fake new source read was accepted" in browser_gate
    assert "Fact/source basis preview without a matching exact source target was accepted" in browser_gate
    assert "Fact/source basis preview with an altered returned passage was accepted" in browser_gate
    assert "Intake construction and ready preview both show the exact returned customer-message passage and locator" in browser_gate
    assert "intakeClaimMessageBasisContractViolations" in browser_gate
    assert "Generated intake summary fixture was accepted" in browser_gate
    assert "Non-source basis preview with a fabricated source locator was accepted" in browser_gate
    assert "Incomplete accepted-decision basis preview was accepted" in browser_gate
    assert "contextual basis preview is not visible in the default graph state with modal grounding closed" in browser_gate
    assert "human-readable returned reasoning path" in browser_gate
    assert "basis preview overlaps" in browser_gate
    assert "function processPreviewGeometryContractViolations" in browser_gate
    assert "PROCESS_PREVIEW_BOTTOM_INSET_PX = 8" in browser_gate
    for selector in (
        ".ac-spatial-detail",
        ".ac-build-inspection",
        ".ac-visual-source-frame",
        ".ac-source-page-excerpt",
        ".ac-node-causal-chain",
    ):
        assert selector in browser_gate
    assert "window.__casepathCaptureProcessPreviewGeometry" in browser_gate
    assert "Every visible construction and completed source preview stays inside the 1440×900 process viewport with an 8px bottom inset" in browser_gate
    assert "Bottom-clipped construction preview fixture was accepted" in browser_gate
    assert "function groundingModalContractViolations" in browser_gate
    assert "async function artifactGroundingModalSnapshot" in browser_gate
    assert "grounding modal overlaps or obscures the persistent source rail" in browser_gate
    assert "closing grounding did not restore one graph focus and one primary action" in browser_gate
    assert "Exact document/evidence requirement remains actionable from the grounding modal" in browser_gate
    assert "function settledCursorPayoffContractViolations" in browser_gate
    assert "async function settledCursorPayoffSnapshot" in browser_gate
    assert "syntheticClickCountAfterParking" in browser_gate
    assert "Review-applied parks one visible cursor clear of the correction payoff and new ventilation node" in browser_gate
    assert "Knowledge parks one visible cursor clear of the saved-memory payoff and ventilation node" in browser_gate
    assert "Later result parks one visible cursor clear of the memory-effect payoff and added ventilation node" in browser_gate
    assert "Tampered settled cursor payoff fixture was accepted" in browser_gate
    assert 'data-grounding-open="true"' not in browser_gate
    assert "return diagnostics.slice(0, 3);" in browser_gate
    assert "Zoom-out desktop journey keeps sources visible and causal" in browser_gate
    assert ".ac-spatial-viewport" in canvas_css
    assert ".casepath-artifact-canvas .ac-source-page-excerpt{" in canvas_css
    assert "max-height:9.5em!important" in canvas_css
    assert ".casepath-artifact-canvas .ac-grounding-viewer{" in canvas_css
    assert "width:min(760px,calc(100vw - 332px));" in canvas_css
    assert "body[data-casepath-artifact-canvas=\"ready\"] .v21-source-summary-toggle.is-active" in canvas_css
    assert '.ac-process-track li[data-spatial-role="hub"]' in canvas_css
    assert '.ac-spatial-edges path[data-spatial-path="uncertainty"]' in canvas_css
    assert ".ac-spatial-law-marker" in canvas_css and ".ac-evidence-relationship" in canvas_css
    assert "function spatialGraphGeometryContractViolations" in browser_gate
    assert "function spatialGraphGeometrySnapshot" in browser_gate
    assert "function processRouteStory(" in browser_gate
    assert "function processRouteStoryContractViolations(" in browser_gate
    assert "Valid scope_unverified route fixture was rejected" in browser_gate
    assert "Contradictory scope route fixture was accepted" in browser_gate
    assert "Scope-unverified fixture with unrelated causation UI was accepted" in browser_gate
    assert "Valid non-evidence-gap causation canvas route was rejected" in browser_gate
    assert "Model-owned permanent process structure was accepted" in browser_gate
    assert "Conservative Documents preserves every exact returned item, status, fact, and process owner" in browser_gate
    assert "processRegion.dataset.processRouteMode" in canvas
    assert "processRegion.dataset.processSelectedPath" in canvas
    assert "processRegion.dataset.processCurrentNodeId" in canvas
    assert "processRegion.dataset.processNextActionNodeId" in canvas
    assert "processRegion.dataset.processSelectedBranchId" in canvas
    assert "processRegion.dataset.processFocalNodeId" in canvas
    assert "processRegion.dataset.processTerminalState" in canvas
    assert "journeyNext.dataset.casepathRouteTerminal" in canvas
    assert "process graph does not occupy the majority of the artifact canvas" in browser_gate
    assert "spine is a vertical list instead of a horizontal process" in browser_gate
    assert "uncertainty branches do not physically diverge" in browser_gate
    assert "connector invents a process relationship" in browser_gate
    assert "visible connectors do not equal the human-readable returned reasoning path" in browser_gate
    assert "visible spatial objects overlap" in browser_gate
    assert "permanent node lineage is incomplete" in browser_gate
    assert "title is clipped or below 12px" in browser_gate
    assert "legal grounding is not truthfully placed above the returned current node" in browser_gate
    assert "evidence requirements are not truthfully placed below the returned current node" in browser_gate
    assert "compact next action does not equal the returned next action" in browser_gate
    assert "decisionFlowContractViolations" in browser_gate
    assert "integrated decision trace does not cover the returned route decisions in order" in browser_gate
    assert "graph plan does not reuse the accepted fact and checked-law trace" in browser_gate
    assert "accepted input is not replayed sequentially" in browser_gate
    assert "accepted-input replay falsely claims a new source opening" in browser_gate
    assert "progress is not hidden while the live plan recedes before node creation" in browser_gate
    assert "accepted node appears before progress and plan have cleared" in browser_gate
    assert "factId: detail.factId || ''" in browser_gate
    assert "blocked downstream step invents accepted input work before causation is resolved" in browser_gate
    assert "Invented work for a blocked downstream decision was accepted" in browser_gate
    assert "returned route branches appear, without invented source reads or progress cycles" in browser_gate
    assert "function processNodeProgressContractViolations" in browser_gate
    assert "window.__casepathProcessNodeProgress = []" in browser_gate
    assert "window.addEventListener('casepath:process-node-progress'" in browser_gate
    assert "progress does not cover the returned route decisions in order" in browser_gate
    assert "decision progress does not replay accepted inputs before form, 100, and cleared" in browser_gate
    assert "one calm cursor working cue is not visible while its semantic progress element stays hidden" in browser_gate
    assert "analysis indicator did not semantically reach completion before clearing" in browser_gate
    assert "numeric percentage is visible in the live node flow" in browser_gate
    assert "progress was not cleared while the output was still absent" in browser_gate
    assert "progress indicator remains visible when the output appears" in browser_gate
    assert "completed process leaves progress visible or active" in browser_gate
    assert "Valid execution-trace-bound process-node progress fixture was rejected" in browser_gate
    assert "Process progress with a missing accepted-input phase was accepted" in browser_gate
    assert "Accepted decision_value progress owned by the wrong visible workstream was accepted" in browser_gate
    assert "Accepted-input progress with an inflated model identity was accepted" in browser_gate
    assert "Visible numeric process percentage fixture was accepted" in browser_gate
    assert "Blocked downstream decision without its waiting basis was accepted" in browser_gate
    assert "Process output visible before progress cleared was accepted" in browser_gate
    assert "Process progress still visible when the node appeared was accepted" in browser_gate
    assert "basisKind: detail.basisKind || ''" in browser_gate
    assert "node.dataset.artifactChangeId === detail.changeId" in browser_gate
    assert "for (const kind of ['law', 'evidence', 'precedent', 'verification'])" in browser_gate
    assert "casepath:artifact-process-complete" in canvas
    assert "casepath:artifact-process-started" in canvas
    assert "function evidenceStageMarkup(copy)" in canvas
    assert "Number(item.ranking?.rank) === 1" in canvas
    assert "focal.dataset.artifactFocus === 'true'" in canvas
    assert "state.officialLawTourVisitedIds.has(String(entityId || ''))" in canvas
    assert "if (button.dataset.acInspectionTarget !== 'true')" in canvas
    assert "const focus = root?.querySelector('[data-artifact-focus=\"true\"]');" in canvas
    assert "focus?.querySelector('[data-ac-cursor-target=\"true\"]')" in canvas
    assert canvas.count("Number(item.ranking?.rank) === 1") >= 2
    assert "data-node-attachment-kind=\"precedent\"" in canvas
    assert "emitGraphContextualArtifact(detail, satellites);" in canvas
    assert "emitArtifactChange(kind, entityId);" in canvas
    assert "evaluate((root, context) =>" in browser_gate
    assert '#artifactCanvas [data-artifact-focus="true"] [data-ac-action="submit-review"]' in browser_gate
    assert "Active decision [${checkContext}] offers its ${kind} grounding on demand" in browser_gate
    assert "#artifactProcessGraph .ac-grounding-disclosure" in browser_gate
    compatibility_block = browser_gate.index(
        "if (false) { // Hidden compatibility DOM remains contract-tested statically"
    )
    assert browser_gate.index(
        "await auditViewports('02-ready-process', '#artifactProcessGraph"
    ) < compatibility_block
    assert browser_gate.index(
        "await screenshot('03-image-grounding-inspection.png');"
    ) < compatibility_block
    assert "await page.evaluate(detail => document.dispatchEvent(new CustomEvent('casepath:open-source'" in browser_gate
    assert "Valid spatial process geometry fixture was rejected" in browser_gate
    assert "Vertical-list spatial graph fixture was accepted" in browser_gate
    assert "Invented spatial process edge fixture was accepted" in browser_gate


def test_flagship_presentation_holds_work_and_artifacts_for_clarity() -> None:
    renderer = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v16.js"
    ).read_text(encoding="utf-8")
    canvas = (
        release_tool.REPOSITORY / "casepath" / "assets" / "artifact-canvas.js"
    ).read_text(encoding="utf-8")
    api_app = (
        release_tool.REPOSITORY / "casepath-api" / "casepath_api" / "app.py"
    ).read_text(encoding="utf-8")
    assert "const PROCESS_STORY_TIMEOUT_MS = 120000;" in renderer
    assert "const OFFICIAL_LAW_TOUR_TIMEOUT_MS = 120000;" in renderer
    assert "const AGENT_RECEIPT_BEAT_MS = reduceMotion ? 20 : 800;" in renderer
    assert "function waitForProcessStory()" in renderer
    assert "function waitForProcessStoryOnce()" in renderer
    assert "function processStoryDrawing()" in renderer
    assert "if (processStoryWaitPromise) return processStoryWaitPromise;" in renderer
    assert "const onStarted = event => {" in renderer
    assert "if (String(event.detail?.runId || '') === runId) armTimeout();" in renderer
    assert "window.addEventListener('casepath:artifact-process-started', onStarted);" in renderer
    assert "      armTimeout();" in renderer
    assert "const noteDelay = () => {" in renderer
    assert "The accepted process trace did not complete. Nothing was substituted." in renderer
    process_wait = renderer[
        renderer.index("  function waitForProcessStory()") : renderer.index(
            "\n  function waitForProcessStoryOnce()"
        )
    ]
    assert "finish('timed-out')" in process_wait
    assert "if (!processStoryComplete()) {" in renderer
    assert "window.removeEventListener('casepath:artifact-process-started', onStarted);" in renderer
    assert "const acceptedProjectionComplete = projectedProcessNodeIds().every" in canvas
    assert "const acceptedProjectionComplete = SIMPLIFIED_SPINE_IDS.every" not in canvas
    assert "function projectedProcessNodeIds(" in canvas
    assert "function processProjectionReady()" in canvas
    assert "acceptedProjectionComplete ? 'complete' : 'pending'" in canvas
    assert "if (nodeId && !state.graphRevealRunning) state.selectedNodeId = nodeId;" in canvas
    assert "state.pendingGraphNodeId || state.pendingBranchNodeId || state.selectedNodeId" in canvas
    assert "casepath:artifact-process-timeout" in renderer
    assert "[data-process-build-state=\"built\"]').length >= 10" in renderer
    assert "function waitsForCompletedProcess(event)" in renderer
    assert "await waitForProcessStoryOnce();" in renderer
    assert "if (processArtifact) {" in renderer
    assert "const processStoryStatus = await waitForProcessStoryOnce();" in renderer
    focus = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v20-focus.js"
    ).read_text(encoding="utf-8")
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")

    assert "const WORKING_FRAME_MS = 2300;" in renderer
    assert "const ARTIFACT_FRAME_MS = 5500;" in renderer
    assert "const RESEARCH_ARTIFACT_FRAME_MS = 9000;" in renderer
    assert "const PROCESS_ARTIFACT_FRAME_MS" not in renderer
    assert "phase === 'receipt'" in renderer
    agent_completion_start = renderer.index(
        "    if (event.stage === 'agent_orchestration'"
    )
    agent_completion_end = renderer.index(
        "    const stage = STAGES.find(item => item.id === event.stage);",
        agent_completion_start,
    )
    agent_completion = renderer[agent_completion_start:agent_completion_end]
    assert "return 'receipt';" in agent_completion
    assert "return 'background';" not in agent_completion
    assert "announceRender" not in agent_completion
    assert "held_out_pipeline = ClaimPipeline(" in api_app
    assert "model_mode=MODEL_MODE_REFERENCE," in api_app
    assert "pace_seconds=0," in api_app
    assert "const BACKGROUND_BEAT_MS = reduceMotion ? 20 : 120;" in renderer
    assert "const CURSOR_TARGET_MIN_HOLD_MS = 220;" in focus
    assert "const PRESENTABLE_STAGE_STATES = new Set([...SUCCESS_EVENT_STATES, 'candidate_prepared']);" in renderer
    assert "run?.process_candidate" in renderer
    assert "run?.checklist_candidate" in renderer
    assert "state.run?.verification_candidate" in renderer
    assert "casepath:presentation" in renderer
    assert 'data-retrieval-method="versioned_official_source_registry_lookup"' in renderer
    assert "Cached exact official source" in renderer
    assert "Verify on official website ↗" in renderer
    assert "function waitForOfficialLawTour()" in renderer
    assert "if (phase === 'artifact' && entry.event.stage === 'research') {" in renderer
    assert "const lawTourStatus = await waitForOfficialLawTour();" in renderer
    assert "casepath:official-source-tour-complete" in renderer
    assert "function startOfficialLawTour()" in canvas
    assert "presentation: 'deterministic-projection'" in canvas
    assert "function nodeDecisionTrace(node)" in canvas
    assert "emitDecisionFlowStep(node, step, 'source-opened', progress)" in canvas
    assert "function officialLawTourContractViolations" in browser_gate
    assert "official-law tour does not show the exact four returned registry sources in order" in browser_gate
    assert "official law is visually misrepresented as Nemotron work" in browser_gate
    assert "checked-law replay is not bound to the deterministic official registry event" in browser_gate
    assert "Why it matters" in focus
    assert "Doing now" in focus
    assert "Unsupported conclusions must fail closed before review." in focus
    assert "window.__casepathPresentationTimeline" in browser_gate
    assert "working frame ${workMs.toFixed(0)}ms" in browser_gate
    assert "artifact frame ${artifactMs.toFixed(0)}ms" in browser_gate
    assert "const minimumWorkMs = concise ? 500 : 2300;" in browser_gate
    assert "const minimumArtifactMs = concise ? 800 : 5500;" in browser_gate


def test_unified_audit_preserves_the_live_orchestration_proof() -> None:
    stability = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v16-stability.js"
    ).read_text(encoding="utf-8")
    index = (release_tool.REPOSITORY / "casepath" / "index.html").read_text(
        encoding="utf-8"
    )

    handler = stability[stability.index("async function openUnifiedAudit") :]
    assert handler.index("shell.insertBefore(proof, content);") < handler.index(
        "content.innerHTML ="
    )
    assert "proof.hidden = false;" in handler
    assert "proof.classList.add('v21-audit-proof');" in handler
    assert _content_bound_asset_locator("live-v16-stability.js") in index


def test_process_story_builds_grounded_nodes_at_a_readable_rate() -> None:
    renderer = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v16.js"
    ).read_text(encoding="utf-8")
    controller = (
        release_tool.REPOSITORY / "casepath" / "assets" / "process-story.js"
    ).read_text(encoding="utf-8")
    styles = (
        release_tool.REPOSITORY / "casepath" / "assets" / "process-story.css"
    ).read_text(encoding="utf-8")
    index = (release_tool.REPOSITORY / "casepath" / "index.html").read_text(
        encoding="utf-8"
    )

    assert "const PROCESS_NODE_INTERVAL_MS = 2500;" in controller
    assert "const PROCESS_BRANCH_HOLD_MS = 2500;" in controller
    assert "const PROCESS_ARTIFACT_FRAME_MS" not in renderer
    assert "phase === 'artifact' && entry.event.stage === 'process'" in renderer
    assert "const processArtifact = phase === 'artifact' && entry.event.stage === 'process';" in renderer
    assert "if (!processArtifact) await wait(frameMs);" in renderer
    assert "casepath:graph-step" in controller
    assert "basisKinds" in controller
    assert "factIds" in controller
    assert "lawIds" in controller
    assert "parentId" in controller
    assert "evidenceRequirementIds" in controller
    assert "if (completedStories.has(key))" in controller
    assert "completedStories.has(key) || reduceMotion" not in controller
    assert 'data-process-story="${story ? \'grounded-node-sequence/1.0.0\' : \'\'}"' in renderer
    assert "data-basis-fact-ids" in renderer
    assert "data-basis-law-ids" in renderer
    assert "data-basis-evidence-requirement-ids" in renderer
    assert "Claim evidence" in renderer
    assert "Swiss law" in renderer
    assert "Process rationale" in renderer
    assert "process-selected-branch" in renderer
    assert 'aria-live="off" data-process-build-focus' in renderer
    assert 'aria-live="polite" aria-atomic="true" data-process-build-announcement' in renderer
    assert "Decision ${index + 1} of ${total}: ${title}." in controller
    assert '[data-process-construction-state="complete"] .process-node{\n  display:none;' in styles
    assert '[data-process-story-expanded="true"] .process-node{\n  display:block;' in styles
    assert '[data-process-construction-state="complete"] .process-node.current .process-node-button' in styles
    assert '[data-process-construction-state="complete"] .process-selected-branch[data-process-build-state="built"]' in styles
    assert 'data-process-build-state="building"' in styles
    assert _content_bound_asset_locator("process-story.css") in index
    assert _content_bound_asset_locator("process-story.js") in index


def test_cursor_exposes_exact_six_call_bound_agents_without_synthetic_seven() -> None:
    assets = release_tool.REPOSITORY / "casepath" / "assets"
    focus = (assets / "live-v20-focus.js").read_text(encoding="utf-8")
    focus_css = (assets / "live-v20-focus.css").read_text(encoding="utf-8")
    canvas = (assets / "artifact-canvas.js").read_text(encoding="utf-8")
    canvas_css = (assets / "artifact-canvas.css").read_text(encoding="utf-8")
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")
    identities = {
        "canonical_facts": ("Guarded Canonical Facts Agent", "Claim", "CF", "facts"),
        "orchestrator_plan": ("Nemotron Orchestrator", "Plan", "OR", "orchestrator"),
        "document_source_integrity": (
            "Document and Source Integrity Agent",
            "Sources",
            "DS",
            "sources",
        ),
        "process_decision_mapping": (
            "Process Decision Mapping Agent",
            "Path",
            "PM",
            "process",
        ),
        "evidence_checklist": (
            "Evidence and Checklist Agent",
            "Docs",
            "EC",
            "evidence",
        ),
        "final_claim_brief_audit": ("Final Claim Brief Agent", "Check", "FB", "audit"),
    }
    visible_labels = {
        "canonical_facts": "Claim reader",
        "orchestrator_plan": "Work planner",
        "document_source_integrity": "Source checker",
        "process_decision_mapping": "Process builder",
        "evidence_checklist": "Document finder",
        "final_claim_brief_audit": "Result checker",
    }
    identity_start = focus.index("const NEMOTRON_AGENT_IDENTITIES = Object.freeze({")
    identity_end = focus.index("\n  });", identity_start)
    identity_source = focus[identity_start:identity_end]
    assert identity_source.count("order:") == 6
    for agent_id, (role, _short, monogram, signature) in identities.items():
        agent_start = identity_source.index(f"    {agent_id}: {{")
        following = [
            position
            for other_id in identities
            if other_id != agent_id
            and (position := identity_source.find(f"    {other_id}: {{", agent_start + 1))
            >= 0
        ]
        agent_end = min(following, default=len(identity_source))
        block = identity_source[agent_start:agent_end]
        assert f"label: '{visible_labels[agent_id]}'" in block
        assert f"monogram: '{monogram}'" in block
        assert f"signature: '{signature}'" in block
        assert f"{agent_id}: '{role}'" in browser_gate
    assert "data-agent-id=\"${esc(currentIdentity ? currentEvent.actorId : '')}\"" in focus
    assert "currentEvent.actorType === 'nemotron_agent'" in focus
    assert "NEMOTRON_AGENT_IDENTITIES[currentEvent.actorId] || null" in focus
    for phase in (
        "Claim understanding",
        "Swiss-law research",
        "Process discovery",
        "Evidence requirements",
        "Historical claims",
        "Verification",
        "Knowledge",
    ):
        assert f"label: '{phase}'" in focus
        assert f"{phase} Agent" not in focus
    assert focus_css.count('.v21-agent-cursor[data-agent-signature="') == 6
    assert "@keyframes v21" not in focus_css
    assert "requestAnimationFrame(() => cursor.classList.add('is-clicking'))" not in focus
    assert "const activationKey =" in focus
    assert "const rawProofEventId = currentEvent.eventId || '';" in focus
    assert "const cursorPhase = ownedArtifact ? 'artifact' : 'working';" in focus
    assert 'data-cursor-phase="${cursorPhase}"' in focus
    assert 'data-proof-event-id="${esc(rawProofEventId)}"' in focus
    assert "cursor.dataset.eventId || cursor.dataset.proofEventId || moment" in focus
    assert "cursorMotion.emittedActivationKeys.has(activationKey)" in focus
    assert "cursorMotion.emittedActivationKeys.add(activationKey)" in focus
    assert "phase: cursorPhase" in focus
    assert "callId: cursor.dataset.callId || ''" in focus
    assert "outputArtifact: cursor.dataset.outputArtifact || ''" in focus
    assert "cursorTargetKey(target)" in focus
    assert "casepath:cursor-step" in focus
    assert "cursorDecorationMutation" in focus
    assert "attributeOldValue: true" in focus
    assert "graphStepTarget" in focus
    assert "casepath:graph-step" in focus
    canvas_identity_start = canvas.index("  const AGENTS = Object.freeze({")
    canvas_identity_end = canvas.index("\n  });", canvas_identity_start)
    canvas_identity_source = canvas[canvas_identity_start:canvas_identity_end]
    assert canvas_identity_source.count("order:") == 6
    assert canvas.count('id="artifactAgentCursor"') == 1
    assert 'aria-label="Specialist activity"' in canvas
    assert 'aria-label="Six Nemotron specialist roles"' not in canvas
    assert '[data-ac-agent-id="orchestrator_plan"]' in canvas_css
    assert "display:none" in canvas_css
    assert "data-ac-cursor-agent" in canvas
    assert "data-ac-cursor-action" in canvas
    assert "function specialistForCursorTarget(target)" in canvas
    assert "const agentId = AGENTS[lineage?.agentId]" in canvas
    assert "lineage.modelSelectedLocatorIds.includes(locatorId)" in canvas
    assert "cursor.dataset.specialistBound = String(Boolean(specialist));" in canvas
    assert "cursorActionLabel(identityTarget, specialist)" in canvas
    for agent_id, (_audit_role, short, monogram, signature) in identities.items():
        agent_start = canvas_identity_source.index(f"    {agent_id}: {{")
        following = [
            position
            for other_id in identities
            if other_id != agent_id
            and (position := canvas_identity_source.find(
                f"    {other_id}: {{", agent_start + 1
            ))
            >= 0
        ]
        agent_end = min(following, default=len(canvas_identity_source))
        block = canvas_identity_source[agent_start:agent_end]
        assert f"label: '{visible_labels[agent_id]}'" in block
        assert f"short: '{short}'" in block
        assert f"monogram: '{monogram}'" in block
        assert f"signature: '{signature}'" in block
    signature_colors = {
        "facts": "#a81f22",
        "orchestrator": "#3a4b66",
        "sources": "#166b82",
        "process": "#6947a8",
        "evidence": "#9b6514",
        "audit": "#207a54",
    }
    for signature, color in signature_colors.items():
        assert (
            f'.casepath-artifact-canvas .ac-team li[data-agent-signature="{signature}"]'
            f'{{--agent-color:{color}}}'
        ) in canvas_css
        assert (
            f'.casepath-artifact-canvas .ac-agent-cursor[data-agent-signature="{signature}"]'
            f'{{--cursor-color:{color}}}'
        ) in canvas_css
    assert len(set(signature_colors.values())) == 6
    assert '.casepath-artifact-canvas .ac-team{\n  display:flex;' in canvas_css
    assert '.ac-agent-cursor[data-agent-signature="law"]' in canvas_css
    assert '.ac-agent-cursor[data-agent-signature="reference"]' in canvas_css
    assert '.ac-agent-cursor[data-agent-signature="gate"]' in canvas_css
    assert "deterministic authority inherited model-call identity" in browser_gate
    assert "visualActiveAgentId" in browser_gate
    assert "root.dataset.activeAgentId = neutral ? '' : effectiveAgentId;" in canvas
    assert "root.dataset.visualActiveAgentId = neutral?.visualAgentId" in canvas
    assert "target-lineage producer is not in its truthful viewer-facing workstream" in browser_gate
    assert "Desktop cursor presents the agreed six simple agent names" in browser_gate
    assert "production cursor did not present exact six model identities" in browser_gate


def test_browser_gate_observes_single_focus_graph_steps_and_integrated_law_truth() -> None:
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")
    renderer = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v16.js"
    ).read_text(encoding="utf-8")
    controller = (
        release_tool.REPOSITORY / "casepath" / "assets" / "process-story.js"
    ).read_text(encoding="utf-8")

    assert "window.__casepathCursorSteps = [];" in browser_gate
    assert "window.__casepathGraphSteps = [];" in browser_gate
    assert "window.__casepathOfficialSourceSteps = [];" in browser_gate
    assert "window.__casepathSemanticEvents = [];" in browser_gate
    assert "window.__casepathArtifactChanges = [];" in browser_gate
    assert "window.__casepathArtifactFocusViolations = [];" in browser_gate
    assert "focusIdCount" in browser_gate
    assert "cursorIdCount" in browser_gate
    assert "cursorInsideFocus" in browser_gate
    assert "semantic cursor activation repeated" in browser_gate
    assert "cursor never followed graph step" in browser_gate
    assert "process story did not arrive in the returned route order" in browser_gate
    assert "provenance kinds absent or invalid" in browser_gate
    assert "process rationale absent" in browser_gate
    assert "process artifact hold" in browser_gate
    assert "The complete process appears only after explicit exploration" in browser_gate
    assert "detailed provenance floods the live region" in browser_gate
    assert "window.__casepathDecisionFlowSteps = [];" in browser_gate
    assert "window.addEventListener('casepath:decision-flow-step'" in browser_gate
    assert "function officialLawTourContractViolations" in browser_gate
    assert "official-law tour does not show the exact four returned registry sources in order" in browser_gate
    assert "official law is visually misrepresented as Nemotron work" in browser_gate
    assert "graph decision replay reopens a source or law instead of reusing accepted trace" in browser_gate
    assert "checked-law replay is not bound to the deterministic official registry event" in browser_gate
    assert "versioned_official_source_registry_lookup" in browser_gate
    assert "data-official-source-url" in renderer
    assert "data-official-source-panel" in renderer
    assert "data-official-browser-url" in renderer
    assert "Verify on official website ↗" in renderer
    assert "data-agent-cursor-target" in controller
    assert "casepath:graph-step" in controller
    assert "casepath:artifact-change" in browser_gate
    assert "data-node-attachment-kind" in browser_gate
    assert "data-artifact-change-id" in browser_gate
    assert "data-artifact-event-id" in browser_gate
    assert "data-artifact-agent-id" in browser_gate
    assert "data-source-locator-id" in browser_gate
    assert "customer_submission" in browser_gate
    assert "official_registry" in browser_gate
    assert "deterministic_principle" in browser_gate
    assert "generated_reference" in browser_gate
    assert "attachment change is not tied to its agent cursor event" in browser_gate
    assert "Every visible official Swiss-law attachment opens its exact source section" in browser_gate
    assert "Authenticated stream exposes the complete semantic claim-handling vocabulary" in browser_gate


def test_compact_persistent_source_rail_is_runtime_guarded() -> None:
    repository = release_tool.REPOSITORY
    browser_gate = (repository / "casepath-qa" / "browser-focused-v20.mjs").read_text(
        encoding="utf-8"
    )
    product_source = "\n".join(
        (repository / path).read_text(encoding="utf-8")
        for path in (
            "casepath/index.html",
            "casepath/assets/live-v16.js",
            "casepath/assets/live-v20-focus.js",
            "casepath/assets/artifact-canvas.css",
        )
    )

    assert "const SOURCE_RAIL_CONTRACT = 'casepath.source-rail/1.0.0';" in browser_gate
    assert "const SOURCE_RAIL_VIEWPORTS = Object.freeze([" in browser_gate
    assert "Object.freeze({ width: 1280, height: 720 })" in browser_gate
    assert "Object.freeze({ width: 1440, height: 900 })" in browser_gate
    assert "function sourceRailContractViolations(" in browser_gate
    assert "window.__casepathCaptureSourceRail" in browser_gate
    assert "String(sourceId || '') === 'intake' ? 'message'" in browser_gate
    assert "requestAnimationFrame(() => requestAnimationFrame(() => resolve(captureSourceRailNow" in browser_gate
    assert "source rail retains dropdown, expander, or collapse semantics" in browser_gate
    assert "source use does not select exactly one matching reading row" in browser_gate
    assert "source rail overlaps the work canvas or an open inspection surface" in browser_gate
    assert "legacyRailFixture.dropdownCount = 1;" in browser_gate
    assert "ambiguousActiveRailFixture.workOverlapArea = 120;" in browser_gate
    assert "casepath.source-rail/1.0.0" in product_source
    assert "data-source-rail-contract" in product_source
    assert "data-source-rail-list" in product_source
    assert "data-source-rail-item" in product_source
    assert "data-source-icon-kind" in product_source
    assert "data-source-name" in product_source
    assert "data-source-meta" in product_source
    assert "data-source-status" in product_source


def test_browser_gate_requires_authenticated_sse_and_causal_memory_delta() -> None:
    repository = release_tool.REPOSITORY
    renderer = (repository / "casepath" / "assets" / "live-v16.js").read_text(
        encoding="utf-8"
    )
    api = (repository / "casepath-api" / "casepath_api" / "app.py").read_text(
        encoding="utf-8"
    )
    browser_gate = (
        repository / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")

    assert 'media_type="text/event-stream"' in api
    assert '"X-Accel-Buffering": "no"' in api
    assert "stream_run_events" in api
    assert "document.body.dataset.runTransport = 'fetch-sse'" in renderer
    assert "document.body.dataset.activeRunPolls = '0'" in renderer
    assert "'X-CasePath-Session': SESSION_ID" in renderer
    assert "Accept: 'text/event-stream'" in renderer
    assert "function pollRun(" not in renderer
    assert "setTimeout(() => pollRun(" not in renderer
    assert "flagshipStreams.length === 1" in browser_gate
    assert "flagshipHydrations.length === 1" in browser_gate
    assert "flagshipTransport.active_run_polls === 0" in browser_gate
    assert "'node-added': 1" in browser_gate
    assert "'edge-added': 2" in browser_gate
    assert "'evidence-changed': 3" in browser_gate
    assert "originIds.length !== 1 || originIds[0] !== expectedOriginId" in browser_gate
    assert "same persistent graph in place" in browser_gate
    assert "REQUIRED_NEMOTRON_AGENT_IDS" in browser_gate
    assert "REQUIRED_DETERMINISTIC_GATE_IDS" in browser_gate


def test_first_paint_contains_the_complete_flagship_claim_shell() -> None:
    index = (release_tool.REPOSITORY / "casepath" / "index.html").read_text(
        encoding="utf-8"
    )
    renderer = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v16.js"
    ).read_text(encoding="utf-8")
    focus_renderer = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v20-focus.js"
    ).read_text(encoding="utf-8")

    assert 'rel="preconnect" href="https://casepath-agentic-api.onrender.com"' not in index
    assert "casepath-agentic-api.onrender.com" not in index
    assert 'id="headerClaimTitle">Bedroom condition keeps returning<' in index
    assert 'id="attachmentCount">6 files<' in index
    assert all(
        f'data-artifact-id="{artifact_id}"' in index
        for artifact_id in (
            "art_lease",
            "art_notification",
            "art_management_reply",
            "art_photo",
            "art_timeline",
            "art_delivery",
        )
    )
    assert 'class="v20-source-skeleton" aria-hidden="true" hidden' in index
    assert 'class="v20-attachment-skeleton" aria-hidden="true" hidden' in index
    wake_start = index.index("// Begin the read-only demo hydration")
    wake_script = index[wake_start : index.index("</script>", wake_start)]
    assert "window.CASEPATH_API = location.origin;" in wake_script
    assert "window.__CASEPATH_DEMO_REQUEST = workspaceMode" in wake_script
    assert "? Promise.resolve(null)" in wake_script
    assert ": fetch(" in wake_script
    assert "const wakePath = foundationMode ? '/healthz' : '/api/demo';" in wake_script
    assert r"${wakeBase.replace(/\/$/, '')}${wakePath}`" in wake_script
    assert "'X-CasePath-Session': sessionId" in wake_script
    assert ".catch(() => null)" in wake_script
    assert "await " not in wake_script
    assert index.index("// Begin the read-only demo hydration") < index.index(
        'rel="stylesheet"'
    )

    request_start = renderer.index("  function requestDemo()")
    request_end = renderer.index("\n  function beginStartupNotice", request_start)
    request_source = renderer[request_start:request_end]
    assert "if (!demoRequest)" in request_source
    assert "window.__CASEPATH_DEMO_REQUEST" in request_source
    assert ".then(demo => demo || api('/api/demo'))" in request_source
    assert "demoRequest = null;" in request_source
    assert renderer.count("api('/api/demo')") == 1

    boot_start = renderer.index("  async function boot()")
    boot_end = renderer.index("\n  function renderClaim", boot_start)
    boot_source = renderer[boot_start:boot_end]
    assert boot_source.index("bindGlobalInteractions();") < boot_source.index(
        "const demo = await requestDemo();"
    )
    assert boot_source.index("$('#runCasePath').disabled = false;") < boot_source.index(
        "const demo = await requestDemo();"
    )
    assert "$('#runCasePath').disabled = false;" in boot_source
    assert "if (state.starting || state.journey !== 'start') return;" in boot_source
    assert "state.polling || state.starting || state.journey !== 'start'" in renderer

    start_run_start = renderer.index("  async function startFlagshipRun()")
    start_run_end = renderer.index("\n  function parseSseFrames", start_run_start)
    start_run_source = renderer[start_run_start:start_run_end]
    before_first_await = start_run_source.split("await ", 1)[0]
    assert "$('#startState').hidden = true;" in before_first_await
    assert "$('#liveWorkspace').hidden = false;" in before_first_await
    assert "document.body.dataset.casepathStartup = 'waking';" in before_first_await
    assert "setOrchestrator('Preparing the source-grounded review');" in before_first_await
    assert "beginStartupNotice();" in before_first_await
    assert "state.demo = state.demo || await requestDemo();" in start_run_source

    notice_start = renderer.index("  function beginStartupNotice()")
    notice_end = renderer.index("\n  function endStartupNotice", notice_start)
    notice_source = renderer[notice_start:notice_end]
    assert "setTimeout(() =>" in notice_source
    assert "}, 2400);" in notice_source
    assert (
        "First visit: waking the secure analysis service · sources remain available"
        in notice_source
    )

    rollback_source = start_run_source[start_run_source.index("    } catch (error) {") :]
    assert "state.starting = false;" in rollback_source
    assert "endStartupNotice();" in rollback_source
    assert "delete document.body.dataset.casepathStartup;" in rollback_source
    assert "$('#startState').hidden = false;" in rollback_source
    assert "$('#liveWorkspace').hidden = true;" in rollback_source
    assert "button.disabled = false;" in rollback_source
    assert "button.querySelector('span').textContent = 'Analyse claim';" in rollback_source
    assert "toast(`Could not start: ${error.message}`);" in rollback_source
    assert "const starting = /Opening the claim context/i.test" in focus_renderer
    assert "if (!starting && button.disabled === ready)" in focus_renderer


def test_later_result_keeps_returned_comparison_hashes_visible() -> None:
    focus_css = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v20-focus.css"
    ).read_text(encoding="utf-8")
    focus_js = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v20-focus.js"
    ).read_text(encoding="utf-8")
    renderer = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v16.js"
    ).read_text(encoding="utf-8")
    canvas = (
        release_tool.REPOSITORY / "casepath" / "assets" / "artifact-canvas.js"
    ).read_text(encoding="utf-8")
    index = (release_tool.REPOSITORY / "casepath" / "index.html").read_text(
        encoding="utf-8"
    )
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")
    hidden_later_result_rule = next(
        line
        for line in focus_css.splitlines()
        if 'body[data-casepath-moment="later-result"] .later-source-banner' in line
        and "display:none!important" in line
    )
    assert ".final-proof" not in hidden_later_result_rule
    assert _content_bound_asset_locator("live-v20-focus.css") in index
    assert 'id="stageCanvas" aria-busy="false" tabindex="0" aria-label="CasePath work canvas"' in index
    assert '.stage-canvas:focus-visible' in focus_css
    assert 'v20-artifact-header:has([data-v20-open-documents])' in focus_css
    assert 'justify-content:flex-end' in focus_css
    assert _content_bound_asset_locator("live-v20-focus.js") in index
    compact_held_out_truth = "\n".join((renderer, focus_js, canvas))
    assert "held-out later demo claim" in compact_held_out_truth
    assert "The later claim remains source-isolated while eligible guidance is evaluated." in compact_held_out_truth
    assert "Frozen memory receipt + later demo claim" in compact_held_out_truth
    assert "The earlier result came from six call-bound specialist agents." in compact_held_out_truth
    assert "Deterministic comparison · no second model run" in compact_held_out_truth
    assert "This comparison makes no new model call." in compact_held_out_truth
    assert "excluded from the simulated review and memory construction" not in compact_held_out_truth
    assert "flagship above is the live six-agent nemotron analysis" not in compact_held_out_truth
    assert "the later claim remains source-isolated while eligible guidance is evaluated" in browser_gate
    assert "const CURSOR_TARGET_MIN_HOLD_MS = 220;" in focus_js
    assert "elapsed < CURSOR_TARGET_MIN_HOLD_MS" in focus_js
    assert "const finalComparison = page.locator('#laterResult .final-proof');" in browser_gate
    assert "await finalComparison.isVisible()" in browser_gate
    assert "finalComparisonText.includes(proof.before.result_hash)" in browser_gate
    assert "finalComparisonText.includes(proof.after.result_hash)" in browser_gate
    assert "Later payoff shows one exact guarded action and keeps five technical effects behind closed Inspect proof" in browser_gate
    assert "Inspect proof reveals exactly two process links and three document-need effects" in browser_gate
    assert "await laterProofDetails.locator(':scope > summary').click();" in browser_gate
    assert "await page.locator('.v21-progressive-details > summary').click();" in browser_gate
    assert "await page.locator('.v21-progressive-details summary').click();" not in browser_gate


def test_document_names_use_a_semantic_reusable_icon_resolver() -> None:
    focus_js = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v20-focus.js"
    ).read_text(encoding="utf-8")
    focus_css = (
        release_tool.REPOSITORY / "casepath" / "assets" / "live-v20-focus.css"
    ).read_text(encoding="utf-8")
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa" / "browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")
    assert "const DOCUMENT_TYPE_ICONS = Object.freeze({" in focus_js
    assert "const DOCUMENT_ICON_RULES = Object.freeze([" in focus_js
    assert "function documentIconKey(semanticValue)" in focus_js
    assert "function resolveDocumentIcon(documentName, ...semanticContext)" in focus_js
    assert "documentIconKey(documentName) || documentIconKey(semanticContext.filter(Boolean).join(' ')) || 'generic'" in focus_js
    for icon_kind in (
        "contract",
        "mail",
        "inspection",
        "image",
        "timeline",
        "invoice",
        "medical",
        "legal",
        "delivery",
        "generic",
    ):
        assert f"{icon_kind}: '" in focus_js
    assert 'data-document-icon-kind="${esc(icon.key)}"' in focus_js
    assert 'class="v20-document-type-icon"' in focus_js
    assert ".v20-document-type-icon" in focus_css
    assert "stroke-width:1.55" in focus_css
    assert "Every document name has one restrained semantic type icon while status remains separate" in browser_gate
    assert "expectedRepresentativeDocumentIcons" in browser_gate


def test_every_observable_claim_artifact_is_model_visible_and_scanned() -> None:
    api_root = release_tool.REPOSITORY / "casepath-api"
    if str(api_root) not in sys.path:
        sys.path.insert(0, str(api_root))
    from casepath_api.data import ARTIFACTS, CLAIMS

    observable_files = {
        ARTIFACTS[artifact_id]["filename"]
        for claim in CLAIMS.values()
        for artifact_id in claim["artifact_ids"]
    }
    assert observable_files <= release_tool.MODEL_VISIBLE_FILES

    manifest_files = {
        item["path"]: item
        for item in release_tool.build_artifact_manifest()["files"]
    }
    assert all(manifest_files[path]["model_visible"] for path in observable_files)
    assert all(
        manifest_files[path]["leakage_scan"] == "passed"
        for path in observable_files
    )


def test_every_observable_claim_package_string_is_leakage_scanned() -> None:
    api_root = release_tool.REPOSITORY / "casepath-api"
    if str(api_root) not in sys.path:
        sys.path.insert(0, str(api_root))
    from casepath_api.data import CLAIMS, observable_claim_package

    def strings(value, path="$"):
        if isinstance(value, str):
            if path != "$.schema":
                yield path, value
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                yield from strings(item, f"{path}[{index}]")
            return
        if isinstance(value, dict):
            for key, item in value.items():
                yield from strings(item, f"{path}.{key}")

    findings = []
    for claim_id, claim in CLAIMS.items():
        package = observable_claim_package(claim)
        for path, value in strings(package):
            findings.extend(
                release_tool.scan_text(
                    f"observable_claim_package[{claim_id}]{path}", value
                )
            )
    assert findings == []


def test_generated_artifact_timeline_and_metadata_are_temporally_coherent() -> None:
    timeline = release_tool.PdfReader(
        release_tool.ARTIFACT_ROOT / "defect-timeline.pdf"
    )
    timeline_text = "\n".join(page.extract_text() or "" for page in timeline.pages)
    assert "Written notice sent; no attachment recorded." in timeline_text
    assert "Email + receipt" in timeline_text
    assert "with one photograph" not in timeline_text

    primary_reply = (
        release_tool.ARTIFACT_ROOT / "management-reply.eml"
    ).read_text(encoding="utf-8")
    later_reply = (
        release_tool.ARTIFACT_ROOT / "later-management-reply.eml"
    ).read_text(encoding="utf-8")
    assert "Based on your description" in primary_reply
    assert "Based on your description" in later_reply
    assert "Based on the photograph" not in primary_reply + later_reply

    window = release_tool.PdfReader(
        release_tool.ARTIFACT_ROOT / "window-replacement-notice.pdf"
    )
    window_text = "\n".join(page.extract_text() or "" for page in window.pages)
    assert window.metadata.title == "Window Replacement Completion Record"
    assert window.metadata.creation_date.isoformat().startswith("2026-05-22T17:00:00")
    assert "Works completed 18-22 May 2026" in window_text
    assert "were replaced between 18 and 22 May 2026" in window_text

    lease = release_tool.PdfReader(
        release_tool.ARTIFACT_ROOT / "lease-agreement.pdf"
    )
    lease_text = "\n".join(page.extract_text() or "" for page in lease.pages)
    assert lease.metadata.creation_date.isoformat().startswith("2024-01-30T17:30:00")
    assert "Agreement dated 18 January 2024" in lease_text
    assert "Recorded condition on 30 January 2024" in lease_text


def test_archive_release_record_keeps_external_limits_explicit() -> None:
    record_path = (
        release_tool.REPOSITORY
        / "casepath"
        / "releases"
        / "casepath-defects-expert-ready-1.0.0.json"
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["archive"]["sha256"] == (
        "770ef2e68222aa237c71ad273628d306211de3290b075d408cbb978516c14533"
    )
    assert record["verification"]["tests_passed"] == 1721
    assert record["source_commit_resolution"]["status"] == "unresolved"
    assert record["clean_environment_reproduction"]["overall_status"].startswith(
        "blocked_"
    )
    assert record["truth"]["independent_expert_review_completed"] is False


def test_later_scenario_precedes_release_and_has_no_stale_active_markers() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    assert contract["artifact_policy"]["scenario_dates"] == {
        "flagship_received_on": "2026-08-01",
        "later_photo_on": "2026-08-08",
        "later_claim_received_on": "2026-08-10",
    }
    release_tool.verify_release_contract()


def test_model_truth_is_scoped_and_failed_attempt_history_is_not_accepted() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    truth = contract["truth"]
    assert truth["deterministic_build"] == {
        "status": "passed",
        "execution_mode": "deterministic_reference",
        "model_calls": 0,
        "model_backed": False,
    }
    runtime = truth["production_runtime_acceptance"]
    assert "status" not in runtime
    assert "model_backed_accepted" not in runtime
    assert runtime["verdict_authority"] == "dynamic_same_commit_qa_artifacts"
    assert runtime["source_contract_embeds_runtime_verdict"] is False
    assert runtime["required_provider_max_in_flight"] == 1
    assert runtime["model_acceptance_scope"] == "visible_browser_flagship"
    assert runtime["learning_comparison_authority"] == "deterministic_application_tool"
    assert runtime["requires_learning_comparison_zero_model_activity"] is True
    assert runtime["required_final_model_ledger_records"] == 12
    assert runtime["required_final_model_network_calls"] == 6
    assert runtime["required_final_cache_hits"] == 6
    assert runtime["dynamic_evidence"] == {
        "qa_gate": "focused-flagship-journey-v20",
        "report_path": "report.json",
        "evidence_manifest_path": "evidence-manifest.json",
        "evidence_manifest_contract": "casepath.qa-evidence-manifest/1.0.0",
        "required_report_status": "passed",
        "requires_release_id_match": True,
        "requires_non_unknown_source_commit": True,
        "requires_same_source_commit": True,
    }
    assert truth["historical_model_validation"] == {
        "scope": "failed_closed_history_only",
        "evidence_records": list(release_tool.HISTORICAL_MODEL_VALIDATION_RECORDS),
        "establishes_current_runtime_acceptance": False,
    }
    assert contract["source_identity"]["source_contract_embeds_commit"] is False

    attempts = {
        number: release_tool.load_json(
            release_tool.REPOSITORY
            / f"casepath/releases/model-validation-attempt-20260811-{number:02d}.json"
        )
        for number in range(1, 25)
    }
    (
        attempt_1,
        attempt_2,
        attempt_3,
        attempt_4,
        attempt_5,
        attempt_6,
        attempt_7,
        attempt_8,
        attempt_9,
        attempt_10,
        attempt_11,
        attempt_12,
        attempt_13,
        attempt_14,
        attempt_15,
        attempt_16,
        attempt_17,
        attempt_18,
        attempt_19,
        attempt_20,
        attempt_21,
        attempt_22,
        attempt_23,
        attempt_24,
    ) = (attempts[number] for number in range(1, 25))
    for evidence in attempts.values():
        assert evidence["status"] == "failed_closed"
        assert evidence["acceptance_passed"] is False
        assert evidence["model_backed_release_evidence"] is False
        assert evidence["accepted_ledger_record"] is None

    assert attempt_1["provider_observation"] == {
        "canonical_model_id": "nvidia/nemotron-3-ultra-550b-a55b-20260604",
        "upstream_provider": "DeepInfra",
        "actual_cost_usd": 0.00756,
        "prompt_tokens": 3629,
        "completion_tokens": 2625,
        "total_tokens": 6254,
        "finish_reason": "stop",
    }
    assert attempt_2["provider_observation"] == {
        "provider": "openrouter",
        "provider_outcome": "succeeded",
        "upstream_provider": "DeepInfra",
        "response_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "response_id": "gen-1786461118-3rFP3Fq1fNjl0lrXGKNE",
        "actual_cost_usd": 0.0058589,
        "prompt_tokens": 4641,
        "completion_tokens": 1620,
        "total_tokens": 6261,
        "finish_reason": "stop",
    }
    assert attempt_2["application_result"] == {
        "outcome": "rejected",
        "failure_type": "non_controlling_normalized_value",
        "successful_ledger_call_bound": False,
        "ledger_call_id": "modelcall_80e9a1f447e1a026",
        "ledger_outcome": "failed",
        "canonical_result_accepted": False,
    }
    assert attempt_3["provider_observation"] == {
        "provider": "openrouter",
        "provider_outcome": "structured_content_returned",
        "synchronous_usage_cost_present": False,
        "new_openrouter_log_generation_observed": False,
        "provider_cache_replay_assessment": "likely_unconfirmed",
        "charge_status": "unknown_unconfirmed",
        "charge_included_in_known_aggregate": False,
    }
    assert attempt_3["application_result"] == {
        "outcome": "rejected",
        "failure_type": "usage_metadata_completeness",
        "successful_ledger_call_bound": False,
        "ledger_call_id": None,
        "canonical_result_accepted": False,
    }
    assert attempt_4["provider_observation"] == {
        "provider": "openrouter",
        "provider_outcome": "succeeded",
        "upstream_provider": "DeepInfra",
        "response_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "response_id": "gen-1786463260-Xe8T7jBgOLjFhr82uaon",
        "actual_cost_usd": 0.0058281,
        "prompt_tokens": 4641,
        "completion_tokens": 1606,
        "total_tokens": 6247,
        "finish_reason": "stop",
    }
    assert attempt_4["application_result"] == {
        "outcome": "rejected",
        "failure_type": "fact_dispute/source_reference_set",
        "successful_ledger_call_bound": False,
        "ledger_call_id": "modelcall_29c9c7fde86d9fcf",
        "ledger_outcome": "failed",
        "canonical_result_accepted": False,
    }
    assert attempt_5["provider_observation"] == {
        "provider": "openrouter",
        "provider_outcome": "succeeded",
        "response_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "response_id": "gen-1786475792-xFaK7MHwa5i0FStRHruR",
        "actual_cost_usd": 0.0157931,
        "prompt_tokens": 23141,
        "completion_tokens": 1931,
        "total_tokens": 25072,
        "finish_reason": "stop",
    }
    assert attempt_5["application_result"] == {
        "outcome": "rejected",
        "failure_type": "hybrid_model_contribution_strict_majority",
        "successful_ledger_call_bound": False,
        "ledger_call_id": "modelcall_ef72cb958e5c9e63",
        "ledger_outcome": "failed",
        "canonical_result_accepted": False,
        "accepted_fact_count": 7,
        "rejected_fact_count": 11,
        "rejected_invariants": {
            "source_reference_set": 10,
            "canonical_state": 1,
        },
    }
    assert attempt_6["execution_observation"] == {
        "source_commit": "697a19fa0be541f46af85d9f31dd5cbda96b2bb8",
        "qa_deploy_id": "dep-d9tnp72jobas73df6jmg",
        "qa_deploy_outcome": "build_failed",
        "qa_run_id": "run_b67c7356cac2cf12",
        "orchestration_id": "orch_2d81acf782aa379b",
        "failed_agent_id": "canonical_facts",
        "provider_response_count": 1,
        "downstream_model_calls": 0,
        "deterministic_gate_receipts": 0,
    }
    assert attempt_6["provider_observation"] == {
        "provider": "openrouter",
        "provider_outcome": "succeeded",
        "response_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "response_id": "gen-1786477748-NYzcfF7sy7RQ71QO780m",
        "actual_cost_usd": 0.0177709,
        "prompt_tokens": 23163,
        "completion_tokens": 2825,
        "total_tokens": 25988,
        "finish_reason": "stop",
        "usage_source": "response",
        "latency_ms": 25786.994,
    }
    assert attempt_6["application_result"] == {
        "outcome": "rejected",
        "failure_type": "post_validation_missing_upstream_provider_persistence",
        "error_type": "KeyError",
        "successful_ledger_call_bound": False,
        "ledger_call_id": "modelcall_0263759a564abb00",
        "ledger_outcome": "failed",
        "canonical_result_accepted": False,
        "upstream_provider_persisted": False,
        "contribution_diagnostics_retained": False,
    }
    for unavailable_count in (
        "accepted_fact_count",
        "rejected_fact_count",
        "source_reference_projection_count",
    ):
        assert unavailable_count not in attempt_6["application_result"]
    assert attempt_7["execution_observation"] == {
        "source_commit": "7e87f40bc866444f16fd837fa3e6a999faa1c7e0",
        "frontend_deploy_id": "dep-d9to4r942hec738ntcdg",
        "api_deploy_id": "dep-d9to4qqjnfac73cc5seg",
        "qa_deploy_id": "dep-d9to5onavr4c73c9lh3g",
        "qa_deploy_outcome": "build_failed",
        "qa_run_id": "run_a4ce02e0125690b2",
        "orchestration_id": "orch_60c6c6a9508c39f9",
        "failed_agent_id": "canonical_facts",
        "provider_response_count": 1,
        "downstream_model_calls": 0,
        "deterministic_gate_receipts": 0,
    }
    assert attempt_7["provider_observation"] == {
        "provider": "openrouter",
        "provider_outcome": "http_200_response_schema_rejected_by_sdk",
        "response_http_status": 200,
        "sdk": "openrouter",
        "sdk_version": "0.11.46",
        "sdk_error_type": "ResponseValidationError",
        "response_identity_status": "unknown_unverified",
        "synchronous_usage_cost_present": False,
        "new_openrouter_log_generation_observed": False,
        "openrouter_log_check_performed": False,
        "provider_cache_replay_assessment": "not_assessed",
        "charge_status": "unknown_unconfirmed",
        "charge_included_in_known_aggregate": False,
        "estimated_cost_reservation_usd": 0.027645,
        "estimated_reservation_is_actual_charge": False,
        "latency_ms": 28814.669,
    }
    assert attempt_7["application_result"] == {
        "outcome": "rejected",
        "failure_type": "openrouter_sdk_chat_result_response_validation",
        "error_type": "ResponseValidationError",
        "successful_ledger_call_bound": False,
        "ledger_call_id": "modelcall_2c6614b3bc53305b",
        "ledger_outcome": "failed",
        "canonical_result_accepted": False,
        "response_identity_retained": False,
        "usage_metadata_retained": False,
        "contribution_diagnostics_retained": False,
    }
    assert attempt_8["execution_observation"] == {
        "source_commit": "2ab71f600f1e523388dec62e11da4c85b9a15be7",
        "qa_deploy_id": "dep-d9tont6gekts7394fu50",
        "qa_deploy_outcome": "build_failed",
        "qa_deploy_started_at": "2026-08-11T20:54:12.154773Z",
        "qa_error_at": "2026-08-11T20:54:57.057789659Z",
        "qa_build_failed_at": "2026-08-11T20:54:57.157747982Z",
        "qa_deploy_finished_at": "2026-08-11T20:54:58.013224Z",
        "qa_run_id": "run_06fb240a468fd0c8",
        "orchestration_id": "orch_0083b550d06c4b83",
        "failed_agent_id": "canonical_facts",
        "provider_response_count": 1,
        "downstream_model_calls": 0,
        "downstream_agent_receipts": 0,
        "deterministic_gate_receipts": 0,
    }
    assert attempt_8["provider_observation"] == {
        "provider": "openrouter",
        "provider_outcome": "succeeded",
        "requested_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "response_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "response_id": "gen-1786481671-XHJr7oDjH1PtrUL2kNg3",
        "actual_cost_usd": 0.0179293,
        "prompt_tokens": 23163,
        "completion_tokens": 2897,
        "total_tokens": 26060,
        "finish_reason": "stop",
        "latency_ms": 25938.06,
        "bounded_generation_metadata_lookup": "not_available_before_deadline",
        "later_generation_metadata_observation": {
            "read_only": True,
            "response_id": "gen-1786481671-XHJr7oDjH1PtrUL2kNg3",
            "model": "nvidia/nemotron-3-ultra-550b-a55b-20260604",
            "provider_name": "DeepInfra",
            "actual_cost_usd": 0.0179293,
            "prompt_tokens": 23163,
            "completion_tokens": 2897,
            "total_tokens": 26060,
            "finish_reason": "stop",
            "same_generation_confirmed": True,
            "available_after_bounded_lookup": True,
        },
    }
    assert attempt_8["application_result"] == {
        "outcome": "rejected",
        "failure_type": "same_generation_metadata_not_available_within_bounded_lookup",
        "error_type": "ModelResponseError",
        "error_invariant": "generation_metadata_completeness",
        "successful_ledger_call_bound": False,
        "ledger_call_id": "modelcall_58f841d20124e35f",
        "ledger_outcome": "failed",
        "canonical_result_accepted": False,
        "response_identity_retained": True,
        "usage_metadata_retained": True,
        "later_generation_metadata_verified": True,
        "contribution_diagnostics_retained": False,
    }
    assert attempt_9["execution_observation"] == {
        "source_commit": "1464e482503f2b22bebffaa01a9cff84e70113ff",
        "qa_deploy_id": "dep-d9tp3fjncjis739pbnrg",
        "qa_deploy_outcome": "build_failed",
        "qa_deploy_created_at": "2026-08-11T21:18:54.833304Z",
        "qa_deploy_finished_at": "2026-08-11T21:19:50.743049Z",
        "qa_run_id": "run_3abf4f5dcf955488",
        "ledger_created_at": "2026-08-11T21:19:16.695619+00:00",
        "ledger_updated_at": "2026-08-11T21:19:45.558899+00:00",
        "orchestration_id": "orch_16fbcb9e76eaff90",
        "failed_agent_id": "canonical_facts",
        "network_call_count": 1,
        "downstream_model_calls": 0,
    }
    assert attempt_9["provider_observation"] == {
        "provider": "openrouter",
        "provider_outcome": "upstream_rejected",
        "requested_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "response_identity_status": "upstream_request_only_no_generation",
        "routing_diagnosis": {
            "attempt_09_policy": "default_provider_routing",
            "prior_deepinfra_request_status": 200,
            "exact_internal_provider_error_message_observed": False,
        },
        "upstream_request_log_observation": {
            "read_only": True,
            "displayed_at_local": "2026-08-11 23:19 Europe/Zurich",
            "request_id": "gen-1786483159-hyYthqPv76o6PHXpGLzl",
            "final_provider": "Together",
            "upstream_status": 400,
            "router_attempts": 2,
            "router_latency_ms": 759,
        },
        "generation_metadata_lookup": {
            "read_only": True,
            "request_id": "gen-1786483159-hyYthqPv76o6PHXpGLzl",
            "http_status": 404,
            "generation_recovered": False,
        },
        "synchronous_usage_cost_present": False,
        "openrouter_upstream_request_log_observed": True,
        "new_openrouter_log_generation_observed": False,
        "openrouter_log_check_performed": True,
        "provider_cache_replay_assessment": "not_applicable_upstream_rejected",
        "charge_status": "unknown_unconfirmed",
        "charge_included_in_known_aggregate": False,
        "estimated_cost_reservation_usd": 0.027645,
        "estimated_reservation_is_actual_charge": False,
        "latency_ms": 28858.701,
    }
    assert attempt_9["application_result"] == {
        "outcome": "rejected",
        "failure_type": "provider_response_envelope",
        "error_type": "ModelResponseError",
        "error_invariant": "provider_response_envelope",
        "successful_ledger_call_bound": False,
        "ledger_call_id": "modelcall_eda1fe14d069e2d4",
        "ledger_outcome": "failed",
        "canonical_result_accepted": False,
        "response_identity_retained": False,
        "usage_metadata_retained": False,
        "accepted_generation_recovered": False,
        "contribution_diagnostics_retained": False,
    }
    assert attempt_10["execution_observation"] == {
        "source_commit": "0c73193688db85be2e84a8a83b73e311581e3874",
        "qa_deploy_id": "dep-d9tq5bmgekts73978kdg",
        "qa_deploy_outcome": "build_failed",
        "qa_deploy_created_at": "2026-08-11T22:31:10.431539Z",
        "qa_deploy_started_at": "2026-08-11T22:31:10.393462Z",
        "qa_error_at": "2026-08-11T22:33:15.916134259Z",
        "qa_deploy_finished_at": "2026-08-11T22:33:20.129521Z",
        "qa_run_id": "run_d2c28f11f5a4b30e",
        "ledger_created_at": "2026-08-11T22:31:31.379439+00:00",
        "ledger_updated_at": "2026-08-11T22:33:13.302269+00:00",
        "orchestration_id": "orch_4306b740e7a14b00",
        "failed_agent_id": "orchestrator_plan",
        "network_call_count": 2,
        "completed_model_calls": 1,
        "failed_model_calls": 1,
        "downstream_model_calls_after_failure": 0,
        "deterministic_gate_receipts": 0,
    }
    assert attempt_10["provider_observation"] == {
        "provider": "openrouter",
        "provider_outcome": "partial_success_then_length_rejected",
        "requested_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "upstream_provider": "DeepInfra",
        "network_call_count": 2,
        "actual_cost_usd": 0.0307499,
        "actual_cost_complete": True,
        "unknown_cost_call_count": 0,
        "prompt_tokens": 43197,
        "completion_tokens": 4183,
        "total_tokens": 47380,
        "calls": [
            {
                "call_id": "modelcall_1079d5361af8d6b8",
                "agent_id": "canonical_facts",
                "outcome": "succeeded_with_guarded_fallback",
                "response_id": "gen-1786487495-uThNkWVHk7bkiuVb8vaP",
                "response_model": "nvidia/nemotron-3-ultra-550b-a55b",
                "upstream_provider": "DeepInfra",
                "finish_reason": "stop",
                "actual_cost_usd": 0.0198785,
                "prompt_tokens": 23163,
                "completion_tokens": 3783,
                "total_tokens": 26946,
                "latency_ms": 85972.266,
                "created_at": "2026-08-11T22:31:31.379439+00:00",
                "updated_at": "2026-08-11T22:32:57.367156+00:00",
                "deterministic_fallback_applied": True,
                "accepted_fact_count": 17,
                "rejected_fact_count": 1,
                "source_reference_projection_count": 10,
            },
            {
                "call_id": "modelcall_0be219e96b14ec27",
                "agent_id": "orchestrator_plan",
                "outcome": "failed",
                "response_id": "gen-1786487581-HBwGLlRWSJnrBZXAU3Y9",
                "response_model": "nvidia/nemotron-3-ultra-550b-a55b",
                "upstream_provider": "DeepInfra",
                "finish_reason": "length",
                "actual_cost_usd": 0.0108714,
                "prompt_tokens": 20034,
                "completion_tokens": 400,
                "total_tokens": 20434,
                "latency_ms": 12309.811,
                "created_at": "2026-08-11T22:33:00.980714+00:00",
                "updated_at": "2026-08-11T22:33:13.302269+00:00",
                "error_type": "AgentBoundaryError",
                "error_invariant": "provider_finish_reason",
            },
        ],
    }
    assert attempt_10["application_result"] == {
        "outcome": "rejected",
        "failure_type": "orchestrator_plan_truncated_at_output_limit",
        "error_type": "AgentBoundaryError",
        "error_invariant": "provider_finish_reason",
        "successful_ledger_call_bound": False,
        "ledger_call_id": "modelcall_0be219e96b14ec27",
        "ledger_outcome": "failed",
        "canonical_stage_completed": True,
        "canonical_stage_outcome": "succeeded_with_guarded_fallback",
        "canonical_stage_call_id": "modelcall_1079d5361af8d6b8",
        "canonical_guarded_fallback_applied": True,
        "canonical_contribution_diagnostics_retained": True,
        "orchestrator_plan_accepted": False,
        "full_orchestration_accepted": False,
        "runtime_acceptance_established": False,
        "downstream_execution_started": False,
    }
    assert attempt_11["execution_observation"] == {
        "source_commit": "d59978be2f1824f6d769f6f2e32fb7a13e3843e7",
        "qa_deploy_id": "dep-d9tqd4ht0dsc73bthmgg",
        "qa_deploy_outcome": "build_failed",
        "qa_deploy_created_at": "2026-08-11T22:47:46.251804Z",
        "qa_deploy_started_at": "2026-08-11T22:47:46.222303Z",
        "qa_error_at": "2026-08-11T22:48:48.17386701Z",
        "qa_build_failed_at": "2026-08-11T22:48:48.211155358Z",
        "qa_deploy_finished_at": "2026-08-11T22:48:49.788544Z",
        "qa_run_id": "run_bdd1832d34d2188f",
        "ledger_created_at": "2026-08-11T22:48:07.570335+00:00",
        "ledger_updated_at": "2026-08-11T22:48:45.892252+00:00",
        "orchestration_id": "orch_6ca09d18eed0e3f6",
        "failed_agent_id": "orchestrator_plan",
        "network_call_count": 2,
        "completed_model_calls": 1,
        "failed_model_calls": 1,
        "downstream_model_calls_after_failure": 0,
        "deterministic_gate_receipts": 0,
    }
    assert attempt_11["provider_observation"] == {
        "provider": "openrouter",
        "provider_outcome": "partial_success_then_length_rejected",
        "requested_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "upstream_provider": "DeepInfra",
        "network_call_count": 2,
        "actual_cost_usd": 0.0286577,
        "actual_cost_complete": True,
        "unknown_cost_call_count": 0,
        "prompt_tokens": 43197,
        "completion_tokens": 3232,
        "total_tokens": 46429,
        "calls": [
            {
                "call_id": "modelcall_0e3ac23f5327d9de",
                "agent_id": "canonical_facts",
                "outcome": "succeeded_with_guarded_fallback",
                "response_id": "gen-1786488490-tndMk9aYrOZRx6zRO0bs",
                "response_model": "nvidia/nemotron-3-ultra-550b-a55b",
                "upstream_provider": "DeepInfra",
                "finish_reason": "stop",
                "actual_cost_usd": 0.0169063,
                "prompt_tokens": 23163,
                "completion_tokens": 2432,
                "total_tokens": 25595,
                "latency_ms": 25695.53,
                "created_at": "2026-08-11T22:48:07.570335+00:00",
                "updated_at": "2026-08-11T22:48:33.279294+00:00",
                "deterministic_fallback_applied": True,
                "accepted_fact_count": 17,
                "rejected_fact_count": 1,
                "source_reference_projection_count": 10,
            },
            {
                "call_id": "modelcall_72e43889f3f0bece",
                "agent_id": "orchestrator_plan",
                "outcome": "failed",
                "response_id": "gen-1786488517-b5k43pHtTXGdyxrtSIP8",
                "response_model": "nvidia/nemotron-3-ultra-550b-a55b",
                "upstream_provider": "DeepInfra",
                "finish_reason": "length",
                "actual_cost_usd": 0.0117514,
                "prompt_tokens": 20034,
                "completion_tokens": 800,
                "total_tokens": 20834,
                "latency_ms": 9017.156,
                "created_at": "2026-08-11T22:48:36.865710+00:00",
                "updated_at": "2026-08-11T22:48:45.892252+00:00",
                "error_type": "AgentBoundaryError",
                "error_invariant": "provider_finish_reason",
            },
        ],
    }
    assert attempt_11["application_result"] == {
        "outcome": "rejected",
        "failure_type": "orchestrator_plan_truncated_at_output_limit",
        "error_type": "AgentBoundaryError",
        "error_invariant": "provider_finish_reason",
        "successful_ledger_call_bound": False,
        "ledger_call_id": "modelcall_72e43889f3f0bece",
        "ledger_outcome": "failed",
        "canonical_stage_completed": True,
        "canonical_stage_outcome": "succeeded_with_guarded_fallback",
        "canonical_stage_call_id": "modelcall_0e3ac23f5327d9de",
        "canonical_guarded_fallback_applied": True,
        "canonical_contribution_diagnostics_retained": True,
        "orchestrator_plan_accepted": False,
        "full_orchestration_accepted": False,
        "runtime_acceptance_established": False,
        "downstream_execution_started": False,
    }
    assert attempt_12["execution_observation"] == {
        "source_commit": "a839ff99870f5be11f232d1bfc818854202bd2dd",
        "qa_deploy_id": "dep-d9tqqlfavr4c73cfqb0g",
        "qa_deploy_outcome": "build_failed",
        "qa_deploy_created_at": "2026-08-11T23:16:37.178532Z",
        "qa_deploy_started_at": "2026-08-11T23:16:37.149773Z",
        "qa_error_at": "2026-08-11T23:18:55.342617058Z",
        "qa_build_failed_at": "2026-08-11T23:18:55.38377292Z",
        "qa_deploy_finished_at": "2026-08-11T23:18:56.810953Z",
        "qa_run_id": "run_403c755cd290a3dc",
        "ledger_created_at": "2026-08-11T23:16:52.937497+00:00",
        "ledger_updated_at": "2026-08-11T23:18:45.865871+00:00",
        "orchestration_id": "orch_bdc09ac146345588",
        "failed_agent_id": "process_decision_mapping",
        "network_call_count": 4,
        "completed_model_calls": 3,
        "failed_model_calls": 1,
        "downstream_model_calls_after_failure": 0,
        "deterministic_gate_receipts": 0,
    }
    assert attempt_12["provider_observation"] == {
        "provider": "openrouter",
        "provider_outcome": "three_successes_then_process_majority_rejected",
        "requested_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "upstream_provider": "DeepInfra",
        "network_call_count": 4,
        "actual_cost_usd": 0.0332561,
        "actual_cost_complete": True,
        "unknown_cost_call_count": 0,
        "prompt_tokens": 44585,
        "completion_tokens": 5030,
        "total_tokens": 49615,
        "calls": [
            {
                "call_id": "modelcall_f738b46b703992a2",
                "agent_id": "canonical_facts",
                "outcome": "succeeded_with_guarded_fallback",
                "response_id": "gen-1786490215-0nOpYjNjTeMxtSF7ZbzI",
                "response_model": "nvidia/nemotron-3-ultra-550b-a55b",
                "upstream_provider": "DeepInfra",
                "finish_reason": "stop",
                "actual_cost_usd": 0.0175791,
                "prompt_tokens": 23171,
                "completion_tokens": 2736,
                "total_tokens": 25907,
                "latency_ms": 44011.294,
                "created_at": "2026-08-11T23:16:52.937497+00:00",
                "updated_at": "2026-08-11T23:17:36.966427+00:00",
                "deterministic_fallback_applied": True,
                "accepted_fact_count": 17,
                "rejected_fact_count": 1,
                "source_reference_projection_count": 11,
            },
            {
                "call_id": "modelcall_19ca5512d3d071b2",
                "agent_id": "orchestrator_plan",
                "outcome": "succeeded",
                "response_id": "gen-1786490261-TMfcJt5jr492iTT2dA6M",
                "response_model": "nvidia/nemotron-3-ultra-550b-a55b",
                "upstream_provider": "DeepInfra",
                "finish_reason": "stop",
                "actual_cost_usd": 0.0003892,
                "prompt_tokens": 438,
                "completion_tokens": 89,
                "total_tokens": 527,
                "latency_ms": 3256.765,
                "created_at": "2026-08-11T23:17:40.626131+00:00",
                "updated_at": "2026-08-11T23:17:43.894060+00:00",
                "deterministic_fallback_applied": False,
                "accepted_item_count": 1,
                "rejected_item_count": 0,
                "ignored_proposal_count": 0,
            },
            {
                "call_id": "modelcall_1acb408e46e5998b",
                "agent_id": "document_source_integrity",
                "outcome": "succeeded",
                "response_id": "gen-1786490265-IreIMO88mFsoshGiYAxN",
                "response_model": "nvidia/nemotron-3-ultra-550b-a55b",
                "upstream_provider": "DeepInfra",
                "finish_reason": "stop",
                "actual_cost_usd": 0.0011036,
                "prompt_tokens": 736,
                "completion_tokens": 346,
                "total_tokens": 1082,
                "latency_ms": 12820.868,
                "created_at": "2026-08-11T23:17:43.910751+00:00",
                "updated_at": "2026-08-11T23:17:56.744034+00:00",
                "deterministic_fallback_applied": False,
                "accepted_item_count": 6,
                "rejected_item_count": 0,
                "ignored_proposal_count": 0,
            },
            {
                "call_id": "modelcall_0a572660847e0df6",
                "agent_id": "process_decision_mapping",
                "outcome": "failed",
                "response_id": "gen-1786490266-bA9bYAcZ5u9sx20mRS4t",
                "response_model": "nvidia/nemotron-3-ultra-550b-a55b",
                "upstream_provider": "DeepInfra",
                "finish_reason": "stop",
                "actual_cost_usd": 0.0141842,
                "prompt_tokens": 20240,
                "completion_tokens": 1859,
                "total_tokens": 22099,
                "latency_ms": 61943.078,
                "created_at": "2026-08-11T23:17:43.914769+00:00",
                "updated_at": "2026-08-11T23:18:45.865871+00:00",
                "error_type": "AgentBoundaryError",
                "error_invariant": "model_contribution_majority",
            },
        ],
    }
    assert attempt_12["application_result"] == {
        "outcome": "rejected",
        "failure_type": "process_decision_mapping_model_contribution_majority",
        "error_type": "AgentBoundaryError",
        "error_invariant": "model_contribution_majority",
        "successful_ledger_call_bound": False,
        "ledger_call_id": "modelcall_0a572660847e0df6",
        "ledger_outcome": "failed",
        "canonical_stage_completed": True,
        "canonical_stage_outcome": "succeeded_with_guarded_fallback",
        "canonical_stage_call_id": "modelcall_f738b46b703992a2",
        "canonical_guarded_fallback_applied": True,
        "canonical_contribution_diagnostics_retained": True,
        "orchestrator_plan_accepted": True,
        "orchestrator_plan_call_id": "modelcall_19ca5512d3d071b2",
        "document_source_integrity_accepted": True,
        "document_source_integrity_call_id": "modelcall_1acb408e46e5998b",
        "process_decision_mapping_accepted": False,
        "full_orchestration_accepted": False,
        "runtime_acceptance_established": False,
        "downstream_execution_started": True,
        "later_model_calls_after_failure": False,
    }
    assert attempt_13["execution_observation"] == {
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
    }
    assert attempt_13["provider_observation"] == {
        "provider": "openrouter",
        "provider_outcome": "deepinfra_http_429",
        "requested_model": "nvidia/nemotron-3-ultra-550b-a55b",
        "upstream_provider": "DeepInfra",
        "network_call_count": 1,
        "response_identity_status": "upstream_request_only_no_generation",
        "synchronous_usage_cost_present": False,
        "new_openrouter_log_generation_observed": False,
        "openrouter_log_check_performed": True,
        "openrouter_upstream_request_log_observed": True,
        "provider_cache_replay_assessment": "not_applicable_upstream_rejected",
        "charge_status": "unknown_unconfirmed",
        "charge_included_in_known_aggregate": False,
        "actual_cost_complete": False,
        "unknown_cost_call_count": 1,
        "upstream_request_log_observation": {
            "read_only": True,
            "displayed_at_local": "2026-08-12 02:49 Europe/Zurich",
            "request_id": "gen-1786495797-wwTpDFx93vAismEWwWvY",
            "final_provider": "DeepInfra",
            "upstream_status": 429,
            "router_attempts": 1,
            "router_latency_ms": 235,
        },
        "application_ledger_observation": {
            "call_id": "modelcall_f97afa2a05079468",
            "orchestration_id": "orch_bbf7ee808dc04f57",
            "agent_id": "canonical_facts",
            "outcome": "failed",
            "error_type": "TooManyRequestsResponseError",
            "latency_ms": 2777.996,
            "response_identity_retained": False,
            "response_model_retained": False,
            "upstream_provider_retained": False,
            "provider_error_code_retained": False,
            "usage_metadata_retained": False,
            "actual_cost_retained": False,
        },
        "failure_attribution": {
            "classification": "external_deepinfra_http_429",
            "cause_detail": "unknown",
            "router_origin_established": False,
            "key_or_account_hard_limit_reached": False,
        },
        "key_account_capacity_observation": {
            "read_only": True,
            "configured_key_limit_usd": 25,
            "key_used_percent": 0.6536316,
            "key_hard_limit_reached": False,
            "account_credit_status": "healthy",
        },
    }
    assert attempt_13["application_result"] == {
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
    }
    assert {
        section: release_tool._historical_json_sha256(attempt_14[section])
        for section in release_tool._HISTORICAL_ATTEMPT_14_SECTION_SHA256
    } == release_tool._HISTORICAL_ATTEMPT_14_SECTION_SHA256
    assert attempt_14["execution_observation"]["source_commit"] == (
        "765c610378e7acdc224e200c0e7bbbc65c697c6b"
    )
    assert attempt_14["execution_observation"]["qa_deploy_id"] == (
        "dep-d9u0jnbm8hqs73e7kj3g"
    )
    assert attempt_14["execution_observation"]["qa_run_id"] == (
        "run_3010703608cef786"
    )
    assert attempt_14["execution_observation"]["orchestration_id"] == (
        "orch_5c8e411d9ccf1b05"
    )
    assert attempt_14["execution_observation"]["failed_agent_ids"] == [
        "process_decision_mapping",
        "document_source_integrity",
    ]
    attempt_14_calls = attempt_14["provider_observation"]["calls"]
    assert [item["call_id"] for item in attempt_14_calls] == [
        "modelcall_b5582c002c6f20bb",
        "modelcall_47529c6d5a49d7cc",
        "modelcall_509e1d20d5f03da7",
        "modelcall_17477d1f8a445c6f",
    ]
    assert [item["outcome"] for item in attempt_14_calls] == [
        "succeeded",
        "succeeded",
        "failed",
        "failed",
    ]
    assert all(
        item["upstream_provider"] == "DeepInfra" for item in attempt_14_calls[:2]
    )
    assert all(
        item["expected_upstream_provider"] == "DeepInfra"
        and item["upstream_provider_retained"] is False
        for item in attempt_14_calls[2:]
    )
    assert attempt_14["provider_observation"]["actual_cost_usd"] == pytest.approx(
        0.016428
    )
    assert attempt_14["provider_observation"]["actual_cost_complete"] is False
    assert attempt_14["provider_observation"]["unknown_cost_call_count"] == 2
    assert attempt_14["application_result"]["runtime_acceptance_established"] is False
    assert attempt_14["application_result"][
        "failed_call_upstream_identity_retained"
    ] is False
    assert attempt_14["capture_provenance"]["public_api_model_ledger"] == {
        "path": "/api/model-ledger",
        "http_status": 200,
        "response_bytes": 5577,
        "response_sha256": (
            "37980deb2c5408af9801a1b464a868c3c4b122addff275fc1e159df7d14a7aec"
        ),
    }
    assert attempt_14["capture_provenance"]["public_qa_origin"]["classification"] == (
        "stale_previous_deploy_not_attempt_14"
    )
    assert {
        section: release_tool._historical_json_sha256(attempt_15[section])
        for section in release_tool._HISTORICAL_ATTEMPT_15_SECTION_SHA256
    } == release_tool._HISTORICAL_ATTEMPT_15_SECTION_SHA256
    assert attempt_15["execution_observation"]["source_commit"] == (
        "c030f041566b1b318a030dca85e672717efd489f"
    )
    assert attempt_15["execution_observation"]["qa_deploy_id"] == (
        "dep-d9u2s2bm8hqs73ecqik0"
    )
    assert attempt_15["execution_observation"]["qa_run_id"] == (
        "run_5f6b88f669bb0316"
    )
    assert attempt_15["execution_observation"]["orchestration_id"] == (
        "orch_47fcf18494e7c1ec"
    )
    attempt_15_calls = attempt_15["provider_observation"]["calls"]
    assert [item["agent_id"] for item in attempt_15_calls] == [
        "canonical_facts",
        "orchestrator_plan",
        "document_source_integrity",
        "process_decision_mapping",
        "evidence_checklist",
        "final_claim_brief_audit",
    ]
    assert [item["outcome"] for item in attempt_15_calls] == [
        "succeeded_with_guarded_fallback",
        "succeeded",
        "succeeded",
        "succeeded",
        "succeeded_with_guarded_fallback",
        "succeeded",
    ]
    assert all(item["upstream_provider"] == "DeepInfra" for item in attempt_15_calls)
    assert [item["orchestration_id"] for item in attempt_15_calls] == [
        "orch_47fcf18494e7c1ec"
    ] * 6
    assert [item["parent_call_id"] for item in attempt_15_calls] == [
        None,
        "modelcall_c64fbe8b2fe28c2d",
        "modelcall_02505ca6820a00f5",
        "modelcall_02505ca6820a00f5",
        "modelcall_02505ca6820a00f5",
        "modelcall_02505ca6820a00f5",
    ]
    assert attempt_15_calls[0]["accepted_fact_count"] == 17
    assert attempt_15_calls[0]["rejected_fact_count"] == 1
    assert attempt_15_calls[0]["source_reference_projection_count"] == 10
    assert attempt_15_calls[0]["ignored_noncontrolling_normalized_proposals"] == 6
    assert attempt_15_calls[0]["updated_at"] < attempt_15_calls[1]["created_at"]
    assert attempt_15_calls[1]["updated_at"] < attempt_15_calls[2]["created_at"]
    assert max(call["updated_at"] for call in attempt_15_calls[2:4]) < (
        attempt_15_calls[4]["created_at"]
    )
    assert attempt_15_calls[4]["updated_at"] < attempt_15_calls[5]["created_at"]
    assert attempt_15["provider_observation"]["actual_cost_usd"] == pytest.approx(
        0.0254122
    )
    assert attempt_15["provider_observation"]["actual_cost_complete"] is True
    assert attempt_15["provider_observation"]["unknown_cost_call_count"] == 0
    assert attempt_15["application_result"]["outcome"] == "accepted"
    assert attempt_15["application_result"]["full_orchestration_accepted"] is True
    assert attempt_15["application_result"]["deterministic_gates_complete"] is True
    assert attempt_15["application_result"]["runtime_acceptance_established"] is False
    assert attempt_15["qa_result"]["outcome"] == "rejected"
    assert attempt_15["qa_result"]["visible_gate_ids"] == [
        "deterministic_process_gate",
        "deterministic_evidence_gate",
        "whole_playbook_gate",
        "whole-playbook-validator/15.2",
    ]
    assert attempt_15["qa_result"]["current_report_retained"] is False
    assert attempt_15["qa_result"]["current_evidence_manifest_retained"] is False
    assert attempt_15["capture_provenance"]["public_qa_origin"]["classification"] == (
        "stale_previous_deploy_not_attempt_15"
    )
    assert {
        section: release_tool._historical_json_sha256(attempt_16[section])
        for section in release_tool._HISTORICAL_ATTEMPT_16_SECTION_SHA256
    } == release_tool._HISTORICAL_ATTEMPT_16_SECTION_SHA256
    assert attempt_16["execution_observation"]["source_commit"] == (
        "c325c8a0ec27fe0e3fcec5c24407d7b578df2356"
    )
    assert attempt_16["execution_observation"]["cold_run_id"] == (
        "run_67fa8a8b0607c476"
    )
    assert attempt_16["execution_observation"]["warm_run_id"] == (
        "run_5b434ab92b9fe4a6"
    )
    attempt_16_calls = attempt_16["provider_observation"]["calls"]
    warm_calls = attempt_16["warm_cache_result"]["calls"]
    assert [call["agent_id"] for call in attempt_16_calls] == [
        "canonical_facts",
        "orchestrator_plan",
        "process_decision_mapping",
        "document_source_integrity",
        "evidence_checklist",
        "final_claim_brief_audit",
    ]
    assert attempt_16["provider_observation"]["actual_cost_usd"] == pytest.approx(
        0.0236984
    )
    assert attempt_16["provider_observation"]["actual_cost_complete"] is True
    assert attempt_16["application_result"]["full_orchestration_accepted"] is True
    assert attempt_16["warm_cache_result"]["full_orchestration_accepted"] is True
    assert attempt_16["warm_cache_result"]["provider_network_call_count"] == 0
    assert all(call["outcome"] == "cache_hit" for call in warm_calls)
    assert all(call["cache_hit"] is True for call in warm_calls)
    assert all(call["call_count"] == 0 for call in warm_calls)
    assert [call["orchestration_id"] for call in warm_calls] == [
        attempt_16["execution_observation"]["warm_orchestration_id"]
    ] * 6
    assert [call["origin_call_id"] for call in warm_calls] == [
        call["call_id"] for call in attempt_16_calls
    ]
    assert [call["response_id"] for call in warm_calls] == [
        call["response_id"] for call in attempt_16_calls
    ]
    assert [call["origin_finish_reason"] for call in warm_calls] == [
        call["finish_reason"] for call in attempt_16_calls
    ]
    assert [call["origin_usage"] for call in warm_calls] == [
        {
            "prompt_tokens": call["prompt_tokens"],
            "completion_tokens": call["completion_tokens"],
            "total_tokens": call["total_tokens"],
            "actual_cost_usd": call["actual_cost_usd"],
            "usage_source": call["usage_source"],
        }
        for call in attempt_16_calls
    ]
    assert attempt_16["qa_result"]["initial_precedent_cards_exact"] is True
    assert attempt_16["qa_result"]["rendered_precedents_after_interaction"] == []
    assert (
        attempt_16["qa_result"]["terminal_validator_excluded_from_gate_identity"]
        is True
    )
    assert attempt_16["qa_result"]["runtime_acceptance_established"] is False
    assert attempt_16["capture_provenance"]["public_qa_origin"]["classification"] == (
        "stale_previous_deploy_not_attempt_16"
    )
    assert {
        section: release_tool._historical_json_sha256(attempt_17[section])
        for section in release_tool._HISTORICAL_ATTEMPT_17_SECTION_SHA256
    } == release_tool._HISTORICAL_ATTEMPT_17_SECTION_SHA256
    assert attempt_17["execution_observation"]["source_commit"] == (
        "580974b0844f3a7e66ba3d324685cd3290798114"
    )
    assert attempt_17["execution_observation"]["qa_run_id"] == (
        "run_020a11fbd8dc3231"
    )
    assert attempt_17["execution_observation"]["orchestration_id"] == (
        "orch_03c1bbb4a9e4269b"
    )
    attempt_17_calls = attempt_17["provider_observation"]["calls"]
    assert [call["agent_id"] for call in attempt_17_calls] == [
        "canonical_facts",
        "orchestrator_plan",
        "document_source_integrity",
        "process_decision_mapping",
        "evidence_checklist",
    ]
    assert [call["outcome"] for call in attempt_17_calls] == [
        "succeeded",
        "succeeded",
        "succeeded",
        "succeeded",
        "failed",
    ]
    failed_evidence = attempt_17_calls[-1]
    expected_rejections = [
        {"item_id": f"item:{item_id}:{field}", "invariant": "evidence_contract"}
        for item_id in release_tool._HISTORICAL_ATTEMPT_17_EVIDENCE_ITEM_IDS
        for field in ("status", "artifacts")
    ]
    assert failed_evidence["accepted_item_ids"] == []
    assert failed_evidence["accepted_item_count"] == 0
    assert failed_evidence["rejected_items"] == expected_rejections
    assert failed_evidence["rejected_item_count"] == 42
    assert failed_evidence["ignored_proposal_count"] == 0
    assert failed_evidence["error_type"] == "AgentBoundaryError"
    assert failed_evidence["error_invariant"] == "model_contribution_majority"
    assert attempt_17["provider_observation"]["actual_cost_usd"] == pytest.approx(
        0.0201973
    )
    assert attempt_17["provider_observation"]["actual_cost_complete"] is True
    assert attempt_17["provider_observation"]["unknown_cost_call_count"] == 0
    assert attempt_17["application_result"]["outcome"] == "rejected"
    assert (
        attempt_17["application_result"]["deterministic_process_gate_passed"]
        is True
    )
    assert attempt_17["application_result"]["evidence_checklist_accepted"] is False
    assert (
        attempt_17["application_result"]["deterministic_evidence_gate_started"]
        is False
    )
    assert attempt_17["application_result"]["final_model_role_started"] is False
    assert attempt_17["application_result"]["whole_playbook_gate_started"] is False
    assert attempt_17["application_result"]["warm_replay_started"] is False
    assert attempt_17["application_result"]["runtime_acceptance_established"] is False
    assert attempt_17["capture_provenance"]["public_qa_origin"]["classification"] == (
        "stale_previous_deploy_not_attempt_17"
    )
    assert {
        section: release_tool._historical_json_sha256(attempt_18[section])
        for section in release_tool._HISTORICAL_ATTEMPT_18_SECTION_SHA256
    } == release_tool._HISTORICAL_ATTEMPT_18_SECTION_SHA256
    assert attempt_18["execution_observation"]["source_commit"] == (
        "df4db4872e0854af7dbe97e5c86833ab827a1c1b"
    )
    assert attempt_18["execution_observation"]["qa_run_id"] == (
        "run_b7e02e168c3217ac"
    )
    assert attempt_18["execution_observation"]["orchestration_id"] == (
        "orch_2ca291c7f62ef75a"
    )
    attempt_18_calls = attempt_18["provider_observation"]["calls"]
    assert [call["agent_id"] for call in attempt_18_calls] == [
        "canonical_facts",
        "orchestrator_plan",
        "document_source_integrity",
        "process_decision_mapping",
    ]
    assert [call["outcome"] for call in attempt_18_calls] == [
        "succeeded",
        "succeeded",
        "failed",
        "succeeded",
    ]
    failed_document = attempt_18_calls[2]
    assert failed_document["finish_reason"] == "length"
    assert failed_document["completion_tokens"] == 4096
    assert failed_document["semantic_scoring_started"] is False
    assert failed_document["deterministic_fallback_applied"] is False
    assert failed_document["error_type"] == "AgentBoundaryError"
    assert failed_document["error_invariant"] == "provider_finish_reason"
    assert attempt_18_calls[3]["accepted_item_ids"] == [
        "fact:fact_tenancy:decision_value",
        "fact:fact_dispute:decision_value",
        "fact:fact_recurrence:decision_value",
        "fact:fact_notification:decision_value",
        "fact:fact_cause:decision_value",
        "fact:fact_health:decision_value",
    ]
    assert attempt_18["provider_observation"]["actual_cost_usd"] == pytest.approx(
        0.0273757
    )
    assert attempt_18["provider_observation"]["actual_cost_complete"] is True
    assert attempt_18["provider_observation"]["unknown_cost_call_count"] == 0
    assert attempt_18["execution_observation"]["deterministic_gate_receipts"] == 0
    assert attempt_18["execution_observation"]["receipt_sequence"] == [
        {"ordinal": 16, "agent_id": "orchestrator_plan", "state": "started"},
        {"ordinal": 17, "agent_id": "orchestrator_plan", "state": "completed"},
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
    assert attempt_18["execution_observation"][
        "process_output_succeeded_after_failure"
    ] is True
    assert attempt_18["execution_observation"][
        "process_completed_receipt_observed"
    ] is False
    assert attempt_18["application_result"]["deterministic_process_gate_started"] is False
    assert attempt_18["application_result"]["evidence_checklist_started"] is False
    assert attempt_18["application_result"]["runtime_acceptance_established"] is False
    assert attempt_18["capture_provenance"]["public_qa_origin"]["classification"] == (
        "stale_previous_deploy_not_attempt_18"
    )
    assert {
        section: release_tool._historical_json_sha256(attempt_19[section])
        for section in release_tool._HISTORICAL_ATTEMPT_19_SECTION_SHA256
    } == release_tool._HISTORICAL_ATTEMPT_19_SECTION_SHA256
    attempt_19_calls = attempt_19["provider_observation"]["calls"]
    attempt_19_warm_calls = attempt_19["warm_cache_result"]["calls"]
    assert attempt_19["execution_observation"]["source_commit"] == (
        "72b2527b05e2fc4e25c3b8655d4fe9f2da266580"
    )
    assert attempt_19["execution_observation"]["deterministic_gate_ids"] == [
        "deterministic_process_gate",
        "deterministic_evidence_gate",
        "whole_playbook_gate",
    ]
    assert len(attempt_19_calls) == len(attempt_19_warm_calls) == 6
    assert [call["origin_call_id"] for call in attempt_19_warm_calls] == [
        call["call_id"] for call in attempt_19_calls
    ]
    assert [call["response_id"] for call in attempt_19_warm_calls] == [
        call["response_id"] for call in attempt_19_calls
    ]
    assert attempt_19["provider_observation"]["actual_cost_usd"] == pytest.approx(
        0.0256894
    )
    assert attempt_19["qa_result"]["failure_type"] == (
        "normalized_grounding_text_quote_not_exact_substring"
    )
    assert attempt_19["qa_result"]["failed_source_line"] == 2371
    assert attempt_19["capture_provenance"]["public_qa_origin"]["classification"] == (
        "stale_previous_deploy_not_attempt_19"
    )
    assert {
        section: release_tool._historical_json_sha256(attempt_20[section])
        for section in release_tool._HISTORICAL_ATTEMPT_20_SECTION_SHA256
    } == release_tool._HISTORICAL_ATTEMPT_20_SECTION_SHA256
    attempt_20_calls = attempt_20["provider_observation"]["calls"]
    attempt_20_warm_calls = attempt_20["warm_cache_result"]["calls"]
    assert attempt_20["execution_observation"]["source_commit"] == (
        "2ab81d4c717c36f86717867230948ffe5c4875f8"
    )
    assert attempt_20["execution_observation"]["cold_run_id"] == (
        "run_e48f3dfa041155f6"
    )
    assert attempt_20["execution_observation"]["warm_run_id"] == (
        "run_2ad603cb2a686137"
    )
    assert len(attempt_20_calls) == len(attempt_20_warm_calls) == 6
    assert {
        call["agent_id"]: call["origin_call_id"] for call in attempt_20_warm_calls
    } == {call["agent_id"]: call["call_id"] for call in attempt_20_calls}
    assert attempt_20["provider_observation"]["global_ledger_summary"] == {
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
    assert attempt_20["application_result"][
        "deterministic_gate_progression_observed"
    ] is True
    assert attempt_20["application_result"][
        "deterministic_gate_artifact_hashes_recoverable"
    ] is False
    assert attempt_20["qa_result"]["failure_type"] == (
        "visual_authority_copy_wording_drift"
    )
    assert attempt_20["qa_result"]["visual_quote_element_count"] == 0
    assert attempt_20["capture_provenance"]["public_qa_origin"]["classification"] == (
        "stale_previous_deploy_not_attempt_20"
    )
    assert {
        section: release_tool._historical_json_sha256(attempt_21[section])
        for section in release_tool._HISTORICAL_ATTEMPT_21_SECTION_SHA256
    } == release_tool._HISTORICAL_ATTEMPT_21_SECTION_SHA256
    attempt_21_calls = attempt_21["provider_observation"]["calls"]
    attempt_21_warm_calls = attempt_21["warm_cache_result"]["calls"]
    assert attempt_21["execution_observation"]["source_commit"] == (
        "eb5568a1973f63fdbf0ebd0b3f7cd152c73a29cf"
    )
    assert attempt_21["execution_observation"]["cold_run_id"] == (
        "run_b33e288771f5734e"
    )
    assert attempt_21["execution_observation"]["warm_run_id"] == (
        "run_57307719ce42f9e9"
    )
    assert len(attempt_21_calls) == len(attempt_21_warm_calls) == 6
    assert {
        call["agent_id"]: call["origin_call_id"] for call in attempt_21_warm_calls
    } == {call["agent_id"]: call["call_id"] for call in attempt_21_calls}
    assert attempt_21["provider_observation"]["global_ledger_summary"] == {
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
    assert attempt_21["application_result"][
        "deterministic_gate_progression_observed"
    ] is True
    assert attempt_21["application_result"][
        "deterministic_gate_artifact_hashes_recoverable"
    ] is False
    assert attempt_21["qa_result"]["failure_type"] == (
        "document_sheet_multi_owner_item_not_expanded"
    )
    assert attempt_21["qa_result"]["rendered_text"] == ""
    assert attempt_21["qa_result"]["secondary_relationship_copy_present"] is False
    assert attempt_21["capture_provenance"]["public_qa_origin"]["classification"] == (
        "stale_previous_deploy_not_attempt_21"
    )
    assert {
        section: release_tool._historical_json_sha256(attempt_22[section])
        for section in release_tool._HISTORICAL_ATTEMPT_22_SECTION_SHA256
    } == release_tool._HISTORICAL_ATTEMPT_22_SECTION_SHA256
    assert attempt_22["execution_observation"]["source_commit"] == (
        "0db743a2a7a06c56bd5f011cc5928ef39efe424d"
    )
    assert attempt_22["execution_observation"]["production_browser_passed_checks"] == 218
    assert attempt_22["provider_observation"]["global_ledger_summary"] == {
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
    assert attempt_22["qa_result"] == {
        "outcome": "rejected",
        "failure_type": "authoritative_runtime_verifier_contract_drift",
        "browser_report_status": "passed",
        "browser_report_passed": 218,
        "browser_report_failed": 0,
        "retained_json_count": 15,
        "retained_png_count": 14,
        "retained_webm_count": 1,
        "current_report_retained": True,
        "current_evidence_manifest_retained": True,
        "runtime_acceptance_established": False,
    }
    assert {
        section: release_tool._historical_json_sha256(attempt_23[section])
        for section in release_tool._HISTORICAL_ATTEMPT_23_SECTION_SHA256
    } == release_tool._HISTORICAL_ATTEMPT_23_SECTION_SHA256
    assert attempt_23["execution_observation"]["qa_run_id"] == (
        "run_34f1c86b5ee01ca8"
    )
    assert attempt_23["execution_observation"]["orchestration_id"] == (
        "orch_a6c4d159c78e6a4d"
    )
    assert attempt_23["provider_observation"]["call"]["accepted_fact_ids"] == [
        "fact_date_conflict"
    ]
    assert attempt_23["provider_observation"]["call"]["rejected_fact_count"] == 17
    assert {
        item["invariant"]
        for item in attempt_23["provider_observation"]["call"]["rejected_facts"]
    } == {"canonical_state"}
    assert attempt_23["capture_provenance"]["public_qa_atomic_state"][
        "classification"
    ] == "unchanged_attempt_22_exact_bundle"
    assert {
        section: release_tool._historical_json_sha256(attempt_24[section])
        for section in release_tool._HISTORICAL_ATTEMPT_24_SECTION_SHA256
    } == release_tool._HISTORICAL_ATTEMPT_24_SECTION_SHA256
    assert attempt_24["execution_observation"]["qa_deploy_id"] == (
        "dep-d9uclg7lk1mc73eh3ehg"
    )
    assert attempt_24["execution_observation"]["flagship_cold_run_id"] == (
        "run_ee90220be9719ea4"
    )
    assert attempt_24["execution_observation"]["flagship_warm_run_id"] == (
        "run_13f7827167f7c7f1"
    )
    assert attempt_24["execution_observation"]["later_cold_run_id"] == (
        "run_2a4e9d56700e7549"
    )
    assert attempt_24["capture_provenance"]["public_model_ledger"] == {
        "bytes": 24882,
        "sha256": "d91b9fac36f05aafa92aa83a996fbaee798289a8c0c368fb2ed109017271c386",
        "records": 14,
        "network_calls": 8,
        "prompt_tokens": 46747,
        "completion_tokens": 4676,
        "total_tokens": 51423,
        "actual_cost_usd": 0.0336607,
        "actual_cost_complete": False,
        "unknown_cost_call_count": 1,
        "outcomes": {
            "cache_hit": 6,
            "failed": 1,
            "succeeded": 6,
            "succeeded_with_guarded_fallback": 1,
        },
    }
    failed_attempt_24_call = attempt_24["provider_observation"]["calls"][-1]
    assert failed_attempt_24_call["call_id"] == "modelcall_b5cbda5d8b277ba3"
    assert failed_attempt_24_call["actual_cost_usd"] is None
    assert failed_attempt_24_call["provider_error_code"] == 429
    assert "response_id" not in failed_attempt_24_call
    assert "prompt_tokens" not in failed_attempt_24_call
    assert attempt_24["capture_provenance"]["public_qa_atomic_state"][
        "classification"
    ] == "unchanged_attempt_22_exact_bundle_after_attempt_24_failure"
    assert sum(
        attempt["provider_observation"]["actual_cost_usd"]
        for attempt in attempts.values()
        if "actual_cost_usd" in attempt["provider_observation"]
    ) == pytest.approx(0.4629168)
    assert "actual_cost_usd" not in attempt_3["provider_observation"]
    assert "prompt_tokens" not in attempt_3["provider_observation"]
    assert attempt_3["provider_observation"]["charge_status"] == "unknown_unconfirmed"
    assert "actual_cost_usd" not in attempt_7["provider_observation"]
    assert "prompt_tokens" not in attempt_7["provider_observation"]
    assert attempt_7["provider_observation"]["charge_status"] == "unknown_unconfirmed"
    assert (
        attempt_7["provider_observation"]["estimated_reservation_is_actual_charge"]
        is False
    )
    assert "actual_cost_usd" not in attempt_9["provider_observation"]
    assert "prompt_tokens" not in attempt_9["provider_observation"]
    assert attempt_9["provider_observation"]["charge_status"] == "unknown_unconfirmed"
    assert (
        attempt_9["provider_observation"]["charge_included_in_known_aggregate"] is False
    )
    assert (
        attempt_9["provider_observation"]["estimated_reservation_is_actual_charge"]
        is False
    )
    assert "actual_cost_usd" not in attempt_13["provider_observation"]
    assert "prompt_tokens" not in attempt_13["provider_observation"]
    assert attempt_13["provider_observation"]["actual_cost_complete"] is False
    assert attempt_13["provider_observation"]["unknown_cost_call_count"] == 1
    assert attempt_14["provider_observation"]["known_cost_included_in_aggregate"] is True
    assert attempt_14["provider_observation"]["unknown_cost_excluded_from_aggregate"] is True
    for attempt in attempts.values():
        release_tool.verify_failed_model_attempt_evidence(contract, attempt)

    incomplete_usage = deepcopy(attempt_3)
    incomplete_usage["provider_observation"]["actual_cost_usd"] = 0.01
    with pytest.raises(release_tool.VerificationError, match="exact bounded schema"):
        release_tool.verify_failed_model_attempt_evidence(contract, incomplete_usage)

    mislabeled_estimate = deepcopy(attempt_7)
    mislabeled_estimate["provider_observation"][
        "estimated_reservation_is_actual_charge"
    ] = True
    with pytest.raises(release_tool.VerificationError, match="exact bounded schema"):
        release_tool.verify_failed_model_attempt_evidence(contract, mislabeled_estimate)

    unbound_upstream_log = deepcopy(attempt_9)
    unbound_upstream_log["provider_observation"][
        "openrouter_upstream_request_log_observed"
    ] = False
    with pytest.raises(release_tool.VerificationError, match="exact bounded schema"):
        release_tool.verify_failed_model_attempt_evidence(
            contract, unbound_upstream_log
        )

    privacy_mutations = []
    raw_provider_message = deepcopy(attempt_9)
    raw_provider_message["provider_observation"]["provider_message"] = (
        "RAW provider cause: claim DEF-027-E0-DEMO was rejected"
    )
    privacy_mutations.append(raw_provider_message)

    arbitrary_nested_metadata = deepcopy(attempt_9)
    arbitrary_nested_metadata["provider_observation"]["routing_diagnosis"][
        "customer_reference"
    ] = "DOC-8842-INSPECTION"
    privacy_mutations.append(arbitrary_nested_metadata)

    claim_prose_value = deepcopy(attempt_9)
    claim_prose_value["provider_observation"]["provider_outcome"] = (
        "claim DEF-027-E0-DEMO rejected because of a pipe burst"
    )
    privacy_mutations.append(claim_prose_value)

    nested_provider_message = deepcopy(attempt_10)
    nested_provider_message["provider_observation"]["calls"][1]["provider_message"] = (
        "RAW provider output for a private claim"
    )
    privacy_mutations.append(nested_provider_message)

    for unsafe_attempt in privacy_mutations:
        with pytest.raises(
            release_tool.VerificationError,
            match="exact bounded schema",
        ) as caught:
            release_tool.verify_failed_model_attempt_evidence(contract, unsafe_attempt)
        message = str(caught.value)
        assert "DEF-027-E0-DEMO" not in message
        assert "DOC-8842-INSPECTION" not in message
        assert "pipe burst" not in message

    numeric_type_aliases = []
    boolean_execution_count = deepcopy(attempt_6)
    boolean_execution_count["execution_observation"]["provider_response_count"] = True
    numeric_type_aliases.append(boolean_execution_count)

    float_http_status = deepcopy(attempt_7)
    float_http_status["provider_observation"]["response_http_status"] = 200.0
    numeric_type_aliases.append(float_http_status)

    float_nested_http_status = deepcopy(attempt_9)
    float_nested_http_status["provider_observation"]["routing_diagnosis"][
        "prior_deepinfra_request_status"
    ] = 200.0
    numeric_type_aliases.append(float_nested_http_status)

    boolean_rejected_count = deepcopy(attempt_5)
    boolean_rejected_count["application_result"]["rejected_invariants"][
        "canonical_state"
    ] = True
    numeric_type_aliases.append(boolean_rejected_count)

    boolean_unknown_cost_count = deepcopy(attempt_10)
    boolean_unknown_cost_count["provider_observation"]["unknown_cost_call_count"] = (
        False
    )
    numeric_type_aliases.append(boolean_unknown_cost_count)

    for aliased_attempt in numeric_type_aliases:
        with pytest.raises(
            release_tool.VerificationError,
            match="exact bounded schema",
        ):
            release_tool.verify_failed_model_attempt_evidence(contract, aliased_attempt)

    mismatched_attempt_10_aggregate = deepcopy(attempt_10)
    mismatched_attempt_10_aggregate["provider_observation"]["actual_cost_usd"] += 0.01
    with pytest.raises(
        release_tool.VerificationError,
        match="exact bounded schema",
    ):
        release_tool.verify_failed_model_attempt_evidence(
            contract,
            mismatched_attempt_10_aggregate,
        )

    mismatched_attempt_11_output_limit = deepcopy(attempt_11)
    mismatched_attempt_11_output_limit["provider_observation"]["calls"][1][
        "completion_tokens"
    ] = 799
    mismatched_attempt_11_output_limit["provider_observation"]["calls"][1][
        "total_tokens"
    ] = 20833
    mismatched_attempt_11_output_limit["provider_observation"]["completion_tokens"] = (
        3231
    )
    mismatched_attempt_11_output_limit["provider_observation"]["total_tokens"] = 46428
    with pytest.raises(
        release_tool.VerificationError,
        match="exact bounded schema",
    ):
        release_tool.verify_failed_model_attempt_evidence(
            contract,
            mismatched_attempt_11_output_limit,
        )

    mismatched_attempt_12_majority = deepcopy(attempt_12)
    mismatched_attempt_12_majority["provider_observation"]["calls"][3][
        "error_invariant"
    ] = "provider_finish_reason"
    with pytest.raises(
        release_tool.VerificationError,
        match="exact bounded schema",
    ):
        release_tool.verify_failed_model_attempt_evidence(
            contract,
            mismatched_attempt_12_majority,
        )

    unbound_attempt_12_document_call = deepcopy(attempt_12)
    unbound_attempt_12_document_call["application_result"][
        "document_source_integrity_call_id"
    ] = "modelcall_0000000000000000"
    with pytest.raises(
        release_tool.VerificationError,
        match="exact bounded schema",
    ):
        release_tool.verify_failed_model_attempt_evidence(
            contract,
            unbound_attempt_12_document_call,
        )

    inconsistent_attempt_12_aggregate = deepcopy(attempt_12)
    inconsistent_attempt_12_aggregate["provider_observation"]["actual_cost_usd"] += 0.01
    with pytest.raises(
        release_tool.VerificationError,
        match="exact bounded schema",
    ):
        release_tool.verify_failed_model_attempt_evidence(
            contract,
            inconsistent_attempt_12_aggregate,
        )

    forged_attempt_13_records = []

    wrong_attempt_13_status = deepcopy(attempt_13)
    wrong_attempt_13_status["provider_observation"]["upstream_request_log_observation"][
        "upstream_status"
    ] = 200
    forged_attempt_13_records.append(wrong_attempt_13_status)

    wrong_attempt_13_commit = deepcopy(attempt_13)
    wrong_attempt_13_commit["execution_observation"]["source_commit"] = "0" * 40
    forged_attempt_13_records.append(wrong_attempt_13_commit)

    wrong_attempt_13_request = deepcopy(attempt_13)
    wrong_attempt_13_request["provider_observation"][
        "upstream_request_log_observation"
    ]["request_id"] = "gen-1786495797-AAAAAAAAAAAAAAAAAAAA"
    forged_attempt_13_records.append(wrong_attempt_13_request)

    wrong_attempt_13_provider = deepcopy(attempt_13)
    wrong_attempt_13_provider["provider_observation"][
        "upstream_request_log_observation"
    ]["final_provider"] = "Together"
    forged_attempt_13_records.append(wrong_attempt_13_provider)

    wrong_attempt_13_attempt_count = deepcopy(attempt_13)
    wrong_attempt_13_attempt_count["provider_observation"][
        "upstream_request_log_observation"
    ]["router_attempts"] = 2
    forged_attempt_13_records.append(wrong_attempt_13_attempt_count)

    forged_attempt_13_identity = deepcopy(attempt_13)
    forged_attempt_13_identity["provider_observation"][
        "application_ledger_observation"
    ]["response_identity_retained"] = True
    forged_attempt_13_records.append(forged_attempt_13_identity)

    forged_attempt_13_error_code = deepcopy(attempt_13)
    forged_attempt_13_error_code["provider_observation"][
        "application_ledger_observation"
    ]["provider_error_code_retained"] = True
    forged_attempt_13_records.append(forged_attempt_13_error_code)

    forged_attempt_13_hard_limit = deepcopy(attempt_13)
    forged_attempt_13_hard_limit["provider_observation"][
        "key_account_capacity_observation"
    ]["key_hard_limit_reached"] = True
    forged_attempt_13_records.append(forged_attempt_13_hard_limit)

    forged_attempt_13_router_origin = deepcopy(attempt_13)
    forged_attempt_13_router_origin["provider_observation"]["failure_attribution"][
        "router_origin_established"
    ] = True
    forged_attempt_13_records.append(forged_attempt_13_router_origin)

    forged_attempt_13_cost = deepcopy(attempt_13)
    forged_attempt_13_cost["provider_observation"]["actual_cost_complete"] = True
    forged_attempt_13_records.append(forged_attempt_13_cost)

    unbound_attempt_13_call = deepcopy(attempt_13)
    unbound_attempt_13_call["application_result"]["ledger_call_id"] = (
        "modelcall_0000000000000000"
    )
    forged_attempt_13_records.append(unbound_attempt_13_call)

    unbound_attempt_13_orchestration = deepcopy(attempt_13)
    unbound_attempt_13_orchestration["provider_observation"][
        "application_ledger_observation"
    ]["orchestration_id"] = "orch_0000000000000000"
    forged_attempt_13_records.append(unbound_attempt_13_orchestration)

    for forged_attempt in forged_attempt_13_records:
        with pytest.raises(
            release_tool.VerificationError,
            match="exact bounded schema",
        ) as caught:
            release_tool.verify_failed_model_attempt_evidence(contract, forged_attempt)
        message = str(caught.value)
        assert "gen-1786495797-wwTpDFx93vAismEWwWvY" not in message
        assert "modelcall_f97afa2a05079468" not in message

    forged_attempt_14_records = []
    wrong_attempt_14_commit = deepcopy(attempt_14)
    wrong_attempt_14_commit["execution_observation"]["source_commit"] = "0" * 40
    forged_attempt_14_records.append(wrong_attempt_14_commit)

    wrong_attempt_14_deploy = deepcopy(attempt_14)
    wrong_attempt_14_deploy["execution_observation"]["qa_deploy_id"] = (
        "dep-d9u0jnbm8hqs73e7kj3h"
    )
    forged_attempt_14_records.append(wrong_attempt_14_deploy)

    wrong_attempt_14_failure_order = deepcopy(attempt_14)
    wrong_attempt_14_failure_order["execution_observation"]["failed_agent_ids"].reverse()
    forged_attempt_14_records.append(wrong_attempt_14_failure_order)

    wrong_attempt_14_call = deepcopy(attempt_14)
    wrong_attempt_14_call["provider_observation"]["calls"][2]["call_id"] = (
        "modelcall_0000000000000000"
    )
    forged_attempt_14_records.append(wrong_attempt_14_call)

    wrong_attempt_14_lineage = deepcopy(attempt_14)
    wrong_attempt_14_lineage["provider_observation"]["calls"][3]["parent_call_id"] = (
        "modelcall_b5582c002c6f20bb"
    )
    forged_attempt_14_records.append(wrong_attempt_14_lineage)

    forged_attempt_14_failed_upstream = deepcopy(attempt_14)
    forged_attempt_14_failed_upstream["provider_observation"]["calls"][2][
        "upstream_provider"
    ] = "DeepInfra"
    forged_attempt_14_records.append(forged_attempt_14_failed_upstream)

    wrong_attempt_14_error = deepcopy(attempt_14)
    wrong_attempt_14_error["provider_observation"]["calls"][2][
        "provider_error_code"
    ] = 500
    forged_attempt_14_records.append(wrong_attempt_14_error)

    wrong_attempt_14_cost = deepcopy(attempt_14)
    wrong_attempt_14_cost["provider_observation"]["actual_cost_complete"] = True
    forged_attempt_14_records.append(wrong_attempt_14_cost)

    forged_attempt_14_runtime = deepcopy(attempt_14)
    forged_attempt_14_runtime["application_result"][
        "runtime_acceptance_established"
    ] = True
    forged_attempt_14_records.append(forged_attempt_14_runtime)

    wrong_attempt_14_capture_hash = deepcopy(attempt_14)
    wrong_attempt_14_capture_hash["capture_provenance"]["public_api_model_ledger"][
        "response_sha256"
    ] = "0" * 64
    forged_attempt_14_records.append(wrong_attempt_14_capture_hash)

    forged_attempt_14_current_report = deepcopy(attempt_14)
    forged_attempt_14_current_report["capture_provenance"]["public_qa_origin"][
        "classification"
    ] = "current_attempt_14_acceptance"
    forged_attempt_14_records.append(forged_attempt_14_current_report)

    for forged_attempt in forged_attempt_14_records:
        with pytest.raises(
            release_tool.VerificationError,
            match="exact bounded schema",
        ) as caught:
            release_tool.verify_failed_model_attempt_evidence(contract, forged_attempt)
        message = str(caught.value)
        assert "gen-1786513914-oQ9RsMSIInmknRyHgohy" not in message
        assert "modelcall_509e1d20d5f03da7" not in message

    forged_attempt_15_records = []
    wrong_attempt_15_commit = deepcopy(attempt_15)
    wrong_attempt_15_commit["execution_observation"]["source_commit"] = "0" * 40
    forged_attempt_15_records.append(wrong_attempt_15_commit)

    wrong_attempt_15_role_order = deepcopy(attempt_15)
    wrong_attempt_15_role_order["execution_observation"][
        "required_model_agent_ids"
    ].reverse()
    forged_attempt_15_records.append(wrong_attempt_15_role_order)

    wrong_attempt_15_response = deepcopy(attempt_15)
    wrong_attempt_15_response["provider_observation"]["calls"][4]["response_id"] = (
        "gen-1786523198-AAAAAAAAAAAAAAAAAAAA"
    )
    forged_attempt_15_records.append(wrong_attempt_15_response)

    wrong_attempt_15_orchestration = deepcopy(attempt_15)
    wrong_attempt_15_orchestration["provider_observation"]["calls"][3][
        "orchestration_id"
    ] = "orch_0000000000000000"
    forged_attempt_15_records.append(wrong_attempt_15_orchestration)

    wrong_attempt_15_parent = deepcopy(attempt_15)
    wrong_attempt_15_parent["provider_observation"]["calls"][4]["parent_call_id"] = (
        "modelcall_c64fbe8b2fe28c2d"
    )
    forged_attempt_15_records.append(wrong_attempt_15_parent)

    wrong_attempt_15_timestamp = deepcopy(attempt_15)
    wrong_attempt_15_timestamp["provider_observation"]["calls"][4]["created_at"] = (
        "2026-08-12T08:26:37.000000+00:00"
    )
    forged_attempt_15_records.append(wrong_attempt_15_timestamp)

    wrong_attempt_15_fact_count = deepcopy(attempt_15)
    wrong_attempt_15_fact_count["provider_observation"]["calls"][0][
        "accepted_fact_count"
    ] = 18
    forged_attempt_15_records.append(wrong_attempt_15_fact_count)

    wrong_attempt_15_cost = deepcopy(attempt_15)
    wrong_attempt_15_cost["provider_observation"]["actual_cost_usd"] = 0.0254121
    forged_attempt_15_records.append(wrong_attempt_15_cost)

    wrong_attempt_15_fallback = deepcopy(attempt_15)
    wrong_attempt_15_fallback["provider_observation"]["calls"][4][
        "deterministic_fallback_applied"
    ] = False
    forged_attempt_15_records.append(wrong_attempt_15_fallback)

    wrong_attempt_15_application = deepcopy(attempt_15)
    wrong_attempt_15_application["application_result"][
        "full_orchestration_accepted"
    ] = False
    forged_attempt_15_records.append(wrong_attempt_15_application)

    forged_attempt_15_runtime = deepcopy(attempt_15)
    forged_attempt_15_runtime["application_result"][
        "runtime_acceptance_established"
    ] = True
    forged_attempt_15_records.append(forged_attempt_15_runtime)

    wrong_attempt_15_visible_gates = deepcopy(attempt_15)
    wrong_attempt_15_visible_gates["qa_result"]["visible_gate_ids"].pop()
    forged_attempt_15_records.append(wrong_attempt_15_visible_gates)

    forged_attempt_15_report = deepcopy(attempt_15)
    forged_attempt_15_report["qa_result"]["current_report_retained"] = True
    forged_attempt_15_records.append(forged_attempt_15_report)

    wrong_attempt_15_capture = deepcopy(attempt_15)
    wrong_attempt_15_capture["capture_provenance"]["public_api_model_ledger"][
        "response_sha256"
    ] = "0" * 64
    forged_attempt_15_records.append(wrong_attempt_15_capture)

    for forged_attempt in forged_attempt_15_records:
        with pytest.raises(
            release_tool.VerificationError,
            match="exact bounded schema",
        ) as caught:
            release_tool.verify_failed_model_attempt_evidence(contract, forged_attempt)
        message = str(caught.value)
        assert "gen-1786523198-A8vhBZHdAYRjUqqokm6I" not in message
        assert "modelcall_164106a7469fa643" not in message

    forged_attempt_16_records = []
    forged_attempt_16_warm_call = deepcopy(attempt_16)
    forged_attempt_16_warm_call["warm_cache_result"]["calls"][0]["call_count"] = 1
    forged_attempt_16_records.append(forged_attempt_16_warm_call)

    forged_attempt_16_origin = deepcopy(attempt_16)
    forged_attempt_16_origin["warm_cache_result"]["calls"][2]["origin_call_id"] = (
        "modelcall_0000000000000000"
    )
    forged_attempt_16_records.append(forged_attempt_16_origin)

    forged_attempt_16_origin_usage = deepcopy(attempt_16)
    forged_attempt_16_origin_usage["warm_cache_result"]["calls"][2][
        "origin_usage"
    ]["total_tokens"] += 1
    forged_attempt_16_records.append(forged_attempt_16_origin_usage)

    forged_attempt_16_orchestration = deepcopy(attempt_16)
    forged_attempt_16_orchestration["warm_cache_result"]["calls"][2][
        "orchestration_id"
    ] = "orch_0000000000000000"
    forged_attempt_16_records.append(forged_attempt_16_orchestration)

    forged_attempt_16_qa = deepcopy(attempt_16)
    forged_attempt_16_qa["qa_result"]["rendered_precedents_after_interaction"] = [
        {"claim_id": "HIST-MOULD-014", "rank": 1, "score": 146}
    ]
    forged_attempt_16_records.append(forged_attempt_16_qa)

    forged_attempt_16_runtime = deepcopy(attempt_16)
    forged_attempt_16_runtime["warm_cache_result"]["runtime_acceptance_established"] = (
        True
    )
    forged_attempt_16_records.append(forged_attempt_16_runtime)

    for forged_attempt in forged_attempt_16_records:
        with pytest.raises(
            release_tool.VerificationError,
            match="exact bounded schema",
        ) as caught:
            release_tool.verify_failed_model_attempt_evidence(contract, forged_attempt)
        message = str(caught.value)
        assert "gen-1786526081-TnJHzHHIomfoMLN0kUMr" not in message
        assert "modelcall_9f92e9bc170b700f" not in message

    forged_attempt_17_records = []
    forged_attempt_17_rejection = deepcopy(attempt_17)
    forged_attempt_17_rejection["provider_observation"]["calls"][-1][
        "rejected_items"
    ].pop()
    forged_attempt_17_records.append(forged_attempt_17_rejection)

    forged_attempt_17_cost = deepcopy(attempt_17)
    forged_attempt_17_cost["provider_observation"]["actual_cost_usd"] = 0.0201972
    forged_attempt_17_records.append(forged_attempt_17_cost)

    forged_attempt_17_gate = deepcopy(attempt_17)
    forged_attempt_17_gate["application_result"][
        "deterministic_evidence_gate_started"
    ] = True
    forged_attempt_17_records.append(forged_attempt_17_gate)

    forged_attempt_17_capture = deepcopy(attempt_17)
    forged_attempt_17_capture["capture_provenance"]["public_api_model_ledger"][
        "response_sha256"
    ] = "0" * 64
    forged_attempt_17_records.append(forged_attempt_17_capture)

    for forged_attempt in forged_attempt_17_records:
        with pytest.raises(
            release_tool.VerificationError,
            match="exact bounded schema",
        ) as caught:
            release_tool.verify_failed_model_attempt_evidence(contract, forged_attempt)
        message = str(caught.value)
        assert "gen-1786529324-2J6kUN6zNOoL7vpGLPFq" not in message
        assert "modelcall_a91022b32cf47215" not in message

    forged_attempt_18_records = []
    forged_attempt_18_finish = deepcopy(attempt_18)
    forged_attempt_18_finish["provider_observation"]["calls"][2][
        "finish_reason"
    ] = "stop"
    forged_attempt_18_records.append(forged_attempt_18_finish)

    forged_attempt_18_process_ids = deepcopy(attempt_18)
    forged_attempt_18_process_ids["provider_observation"]["calls"][3][
        "accepted_item_ids"
    ].pop()
    forged_attempt_18_records.append(forged_attempt_18_process_ids)

    forged_attempt_18_receipt = deepcopy(attempt_18)
    forged_attempt_18_receipt["execution_observation"][
        "process_completed_receipt_observed"
    ] = True
    forged_attempt_18_records.append(forged_attempt_18_receipt)

    forged_attempt_18_capture = deepcopy(attempt_18)
    forged_attempt_18_capture["capture_provenance"]["public_api_model_ledger"][
        "response_sha256"
    ] = "0" * 64
    forged_attempt_18_records.append(forged_attempt_18_capture)

    for forged_attempt in forged_attempt_18_records:
        with pytest.raises(
            release_tool.VerificationError,
            match="exact bounded schema",
        ) as caught:
            release_tool.verify_failed_model_attempt_evidence(contract, forged_attempt)
        message = str(caught.value)
        assert "gen-1786532401-OHjtmk6aiCms72NZ62rn" not in message
        assert "modelcall_4abdccd0ab5d8d6f" not in message

    forged_attempt_19_records = []
    for section, mutate in (
        ("execution_observation", lambda item: item.__setitem__("network_call_count", 7)),
        (
            "provider_observation",
            lambda item: item["calls"][0].__setitem__("accepted_fact_count", 17),
        ),
        (
            "application_result",
            lambda item: item.__setitem__("runtime_acceptance_established", True),
        ),
        (
            "warm_cache_result",
            lambda item: item["calls"][0].__setitem__(
                "origin_call_id", "modelcall_0000000000000000"
            ),
        ),
        ("qa_result", lambda item: item.__setitem__("failed_source_line", 2372)),
        (
            "capture_provenance",
            lambda item: item["public_api_model_ledger"].__setitem__(
                "response_sha256", "0" * 64
            ),
        ),
    ):
        forged_attempt = deepcopy(attempt_19)
        mutate(forged_attempt[section])
        forged_attempt_19_records.append(forged_attempt)

    for forged_attempt in forged_attempt_19_records:
        with pytest.raises(
            release_tool.VerificationError,
            match="exact bounded schema",
        ):
            release_tool.verify_failed_model_attempt_evidence(contract, forged_attempt)

    forged_attempt_20_records = []
    for section, mutate in (
        (
            "provider_observation",
            lambda item: item["global_ledger_summary"].__setitem__(
                "network_calls", 7
            ),
        ),
        (
            "application_result",
            lambda item: item.__setitem__(
                "deterministic_gate_artifact_hashes_recoverable", True
            ),
        ),
        ("qa_result", lambda item: item.__setitem__("visual_quote_element_count", 1)),
        (
            "capture_provenance",
            lambda item: item["gate_progression_capture"].__setitem__(
                "gate_artifact_hashes_recoverable", True
            ),
        ),
    ):
        forged_attempt = deepcopy(attempt_20)
        mutate(forged_attempt[section])
        forged_attempt_20_records.append(forged_attempt)

    for forged_attempt in forged_attempt_20_records:
        with pytest.raises(
            release_tool.VerificationError,
            match="exact bounded schema",
        ):
            release_tool.verify_failed_model_attempt_evidence(contract, forged_attempt)

    forged_attempt_21_records = []
    for section, mutate in (
        ("execution_observation", lambda item: item.__setitem__("network_call_count", 7)),
        (
            "provider_observation",
            lambda item: item["global_ledger_summary"].__setitem__("network_calls", 7),
        ),
        (
            "application_result",
            lambda item: item.__setitem__(
                "deterministic_gate_artifact_hashes_recoverable", True
            ),
        ),
        (
            "warm_cache_result",
            lambda item: item["calls"][0].__setitem__(
                "origin_call_id", "modelcall_0000000000000000"
            ),
        ),
        (
            "qa_result",
            lambda item: item.__setitem__("secondary_relationship_copy_present", True),
        ),
        (
            "capture_provenance",
            lambda item: item["public_api_model_ledger"].__setitem__(
                "response_sha256", "0" * 64
            ),
        ),
    ):
        forged_attempt = deepcopy(attempt_21)
        mutate(forged_attempt[section])
        forged_attempt_21_records.append(forged_attempt)

    for forged_attempt in forged_attempt_21_records:
        with pytest.raises(
            release_tool.VerificationError,
            match="exact bounded schema",
        ):
            release_tool.verify_failed_model_attempt_evidence(contract, forged_attempt)

    for attempt, section, mutate in (
        (
            attempt_22,
            "provider_observation",
            lambda item: item["global_ledger_summary"].__setitem__("records", 23),
        ),
        (
            attempt_22,
            "capture_provenance",
            lambda item: item["evidence_manifest"].__setitem__("sha256", "0" * 64),
        ),
        (
            attempt_23,
            "provider_observation",
            lambda item: item["call"].__setitem__("accepted_fact_count", 2),
        ),
        (
            attempt_23,
            "capture_provenance",
            lambda item: item["public_qa_atomic_state"].__setitem__(
                "served_source_commit", "0" * 40
            ),
        ),
        (
            attempt_24,
            "provider_observation",
            lambda item: item["calls"][7].__setitem__(
                "origin_call_id", "modelcall_0000000000000000"
            ),
        ),
        (
            attempt_24,
            "provider_observation",
            lambda item: item["calls"][-1].__setitem__("actual_cost_usd", 0),
        ),
        (
            attempt_24,
            "capture_provenance",
            lambda item: item["public_qa_atomic_state"].__setitem__(
                "served_source_commit", "0" * 40
            ),
        ),
    ):
        forged_attempt = deepcopy(attempt)
        mutate(forged_attempt[section])
        with pytest.raises(
            release_tool.VerificationError,
            match="exact bounded schema",
        ):
            release_tool.verify_failed_model_attempt_evidence(contract, forged_attempt)


def _ledger_summary(items: list[dict]) -> dict:
    unknown_cost_call_count = sum(
        item["call_count"] > 0 and item.get("actual_cost_usd") is None for item in items
    )
    outcomes = {
        outcome: sum(item["outcome"] == outcome for item in items)
        for outcome in sorted({item["outcome"] for item in items})
    }
    return {
        "records": len(items),
        "network_calls": sum(item["call_count"] for item in items),
        "prompt_tokens": sum(item.get("prompt_tokens", 0) for item in items),
        "completion_tokens": sum(item.get("completion_tokens", 0) for item in items),
        "total_tokens": sum(item.get("total_tokens", 0) for item in items),
        "actual_cost_usd": round(
            sum(item.get("actual_cost_usd") or 0 for item in items), 8
        ),
        "actual_cost_complete": unknown_cost_call_count == 0,
        "unknown_cost_call_count": unknown_cost_call_count,
        "outcomes": outcomes,
    }


def successful_dynamic_qa_evidence(contract: dict) -> tuple[dict, dict, dict, bytes]:
    orchestration_id = "orch_release_acceptance_test"
    required_agents = contract["agentic_runtime"]["model_agents"]
    call_ids = {
        item["agent_id"]: f"modelcall_{index:02d}_release_acceptance"
        for index, item in enumerate(required_agents, start=1)
    }
    def source_ref(index: int) -> str:
        return f"src_{index:024x}"

    def canonical_fact(
        fact_id: str,
        *,
        label: str,
        value: str,
        state: str,
        source_refs: list[dict],
        decision_key: str | None = None,
        normalized_value: str | None = None,
        decision_value: str | None = None,
        semantic_role: str | None = None,
    ) -> dict:
        return {
            "fact_id": fact_id,
            "label": label,
            "value": value,
            "state": state,
            "explanation": "Bounded release-acceptance fixture fact.",
            "source_refs": source_refs,
            "confidence": 0.91,
            "controls_process": decision_key is not None,
            "decision_key": decision_key,
            "normalized_value": normalized_value,
            "decision_value": decision_value,
            "semantic_role": semantic_role,
        }

    fixture_agent = "Canonical Claim Preparation Tool"
    def message_ref(excerpt: str) -> dict:
        return {
            "artifact_id": "message",
            "locator_kind": "text_quote",
            "page": 1,
            "excerpt": excerpt,
            "agent": fixture_agent,
        }
    metadata_ref = {
        "artifact_id": "intake",
        "locator_kind": "metadata_field",
        "field": "policy_reference",
        "value": "LP-2024-08317",
        "agent": fixture_agent,
    }
    visual_ref = {
        "artifact_id": "art_photo",
        "locator_kind": "visual_observation",
        "region": [0.12, 0.1, 0.42, 0.38],
        "observation": "Visible dark marks at the bedroom external-wall corner.",
        "producer": release_tool.VISUAL_ANNOTATION_PRODUCER,
        "authority": release_tool.VISUAL_ANNOTATION_AUTHORITY,
        "annotation_contract": release_tool.VISUAL_ANNOTATION_CONTRACT,
        "annotation_version": release_tool.VISUAL_ANNOTATION_VERSION,
        "image_sha256": release_tool.CASEPATH_ARTIFACTS["art_photo"]["sha256"],
    }
    canonical_facts = [
        canonical_fact(
            "fact_tenancy",
            label="Tenant-law scope",
            value="Swiss residential tenancy",
            state="known",
            source_refs=[metadata_ref],
            decision_key="scope",
            normalized_value="supported_in_scope",
            decision_value="in_scope",
        ),
        canonical_fact(
            "fact_dispute",
            label="Concrete dispute",
            value="Management refused inspection and the tenant disagrees",
            state="known",
            source_refs=[message_ref("I disagree because the problem keeps returning.")],
            decision_key="dispute",
            normalized_value="present",
            decision_value="dispute_present",
        ),
        canonical_fact(
            "fact_health",
            label="Urgency",
            value="No acute concern reported",
            state="known",
            source_refs=[message_ref("There are no current health symptoms and no urgent deadline.")],
            decision_key="urgency",
            normalized_value="not_urgent",
            decision_value="not_urgent",
        ),
        canonical_fact(
            "fact_notification",
            label="Notification",
            value="Management notified on 15 July",
            state="known",
            source_refs=[message_ref("I notified the property manager by email on 15 July.")],
            decision_key="notification",
            normalized_value="notified",
            decision_value="notified",
        ),
        canonical_fact(
            "fact_recurrence",
            label="Recurrence",
            value="Condition returns after cleaning",
            state="known",
            source_refs=[message_ref("The mould in the external corner of our bedroom keeps coming back.")],
            decision_key="recurrence",
            normalized_value="supported",
            decision_value="recurrence_supported",
        ),
        canonical_fact(
            "fact_cause",
            label="Technical cause",
            value="Unresolved",
            state="unknown",
            source_refs=[message_ref("They replied that the cause was insufficient ventilation")],
            decision_key="causation",
            normalized_value="unresolved",
            decision_value="cause_unresolved",
        ),
        canonical_fact(
            "fact_ventilation_allegation",
            label="Management ventilation allegation",
            value="Insufficient ventilation alleged",
            state="known",
            source_refs=[
                {
                    "artifact_id": "art_management_reply",
                    "locator_kind": "text_quote",
                    "page": 1,
                    "excerpt": "the marks appear consistent with insufficient ventilation",
                    "agent": fixture_agent,
                }
            ],
            semantic_role="management_ventilation_allegation",
        ),
        canonical_fact(
            "fact_visible_mould",
            label="Visible condition",
            value="Dark marks visible at the external corner",
            state="known",
            source_refs=[visual_ref],
        ),
    ]
    required_primary_fact_ids = {
        fact_id
        for values in release_tool.RELEASE_PROCESS_FACT_IDS_BY_CLAIM[
            "DEF-027-E0-DEMO"
        ].values()
        for fact_id in values
    } | set(
        release_tool.RELEASE_EVIDENCE_FACT_ID_BY_CLAIM[
            "DEF-027-E0-DEMO"
        ].values()
    )
    existing_primary_fact_ids = {fact["fact_id"] for fact in canonical_facts}
    canonical_facts.extend(
        canonical_fact(
            fact_id,
            label=fact_id.replace("_", " ").title(),
            value="Not yet established",
            state="unknown",
            source_refs=[],
        )
        for fact_id in sorted(required_primary_fact_ids - existing_primary_fact_ids)
    )
    source_registry = observable_source_reference_registry(
        release_tool.observable_claim_package(
            release_tool.CASEPATH_CLAIMS["DEF-027-E0-DEMO"]
        )
    )
    text_ref_by_artifact = {
        entry["artifact_id"]: {
            "artifact_id": entry["artifact_id"],
            "locator_kind": "text_quote",
            "page": entry["page"],
            "excerpt": entry["excerpt"],
            "agent": fixture_agent,
        }
        for entry in reversed(source_registry)
    }
    bounded_artifact_ids_by_fact: dict[str, set[str]] = {}
    for item_id, fact_id in release_tool.RELEASE_EVIDENCE_FACT_ID_BY_CLAIM[
        "DEF-027-E0-DEMO"
    ].items():
        bounded_artifact_ids_by_fact.setdefault(fact_id, set()).update(
            release_tool.RELEASE_EVIDENCE_ARTIFACT_IDS_BY_CLAIM[
                "DEF-027-E0-DEMO"
            ][item_id]
        )
    for fact in canonical_facts:
        existing_artifact_ids = {
            ref["artifact_id"] for ref in fact["source_refs"]
        }
        for artifact_id in sorted(
            bounded_artifact_ids_by_fact.get(fact["fact_id"], set())
            - existing_artifact_ids
        ):
            if artifact_id == "intake":
                fact["source_refs"].append(deepcopy(metadata_ref))
            elif artifact_id == "art_photo":
                fact["source_refs"].append(deepcopy(visual_ref))
            else:
                fact["source_refs"].append(
                    deepcopy(text_ref_by_artifact[artifact_id])
                )
    canonical_diagnostics = {
        "authority_mode": "hybrid_guarded",
        "accepted_fact_ids": [fact["fact_id"] for fact in canonical_facts],
        "accepted_fact_count": len(canonical_facts),
        "rejected_facts": [],
        "rejected_fact_count": 0,
        "source_reference_projection_fact_ids": [],
        "source_reference_projection_count": 0,
        "deterministic_fallback_applied": False,
        "ignored_noncontrolling_normalized_proposals": 0,
    }
    assertion_selections = [
        {
            "fact_id": fact["fact_id"],
            "assertion_id": release_tool._canonical_assertion_id(
                fact, "fixture.canonical_fact"
            ),
            "model_owned_fields": (
                ["assertion_id", "source_ref_ids", "confidence"]
                if fact["controls_process"]
                else ["source_ref_ids", "confidence"]
            ),
            "materialized_fields": deepcopy(
                release_tool.CANONICAL_ASSERTION_MATERIALIZED_FIELDS
            ),
            "attribution": "OpenRouter Nemotron Canonicalizer",
            "deterministic_fallback_applied": False,
        }
        for fact in canonical_facts
    ]

    source_artifact = {
        "artifacts": [
            {
                "artifact_id": "art_notice",
                "integrity_class": "text_grounded",
                "source_ref_ids": [source_ref(1)],
                "confidence_basis_points": 9100,
                "attribution": "Document and Source Integrity Agent",
                "deterministic_fallback_applied": False,
            },
            {
                "artifact_id": "art_reply",
                "integrity_class": "text_grounded",
                "source_ref_ids": [source_ref(2)],
                "confidence_basis_points": 9000,
                "attribution": "Document and Source Integrity Agent",
                "deterministic_fallback_applied": False,
            },
            {
                "artifact_id": "art_photo",
                "integrity_class": "visual_only",
                "source_ref_ids": [],
                "confidence_basis_points": 9500,
                "attribution": "Document and Source Integrity Agent",
                "deterministic_fallback_applied": False,
            },
        ]
    }
    decision_specs = [
        (
            "fact_tenancy",
            "scope",
            "in_scope",
            "known",
            "supported_in_scope",
            [source_ref(1)],
        ),
        (
            "fact_dispute",
            "dispute",
            "dispute_present",
            "known",
            "present",
            [source_ref(2)],
        ),
        (
            "fact_health",
            "urgency",
            "not_urgent",
            "known",
            "not_urgent",
            [],
        ),
        (
            "fact_notification",
            "notification",
            "notified",
            "known",
            "notified",
            [source_ref(3)],
        ),
        (
            "fact_recurrence",
            "recurrence",
            "recurrence_supported",
            "known",
            "supported",
            [source_ref(4)],
        ),
        (
            "fact_cause",
            "causation",
            "cause_unresolved",
            "unknown",
            "unresolved",
            [source_ref(5), source_ref(6)],
        ),
    ]
    process_decisions = []
    for index, (
        fact_id,
        decision_key,
        decision_value,
        state,
        normalized_value,
        source_ref_ids,
    ) in enumerate(decision_specs):
        fallback = False
        process_decisions.append(
            {
                "fact_id": fact_id,
                "decision_key": decision_key,
                "decision_value": decision_value,
                "state": state,
                "normalized_value": normalized_value,
                "source_ref_ids": source_ref_ids,
                "contribution_id": f"fact:{fact_id}:decision_value",
                "contribution_scope": "canonical_to_process_decision_mapping",
                "model_owned_fields": ["decision_value"],
                "confidence_basis_points": 10_000 if fallback else 8800 + index * 100,
                "attribution": (
                    "deterministic_application"
                    if fallback
                    else "Process Decision Mapping Agent"
                ),
                "deterministic_fallback_applied": fallback,
            }
        )
    process_artifact = {"decisions": process_decisions}

    evidence_specs = [
        ("claim_message", "fact_scope", "provided_sufficient", ["message"], [source_ref(1)], False),
        ("source_integrity", "fact_scope", "provided_sufficient", ["art_lease"], [source_ref(2)], False),
        ("lease", "fact_scope", "provided_sufficient", ["art_lease"], [source_ref(3)], False),
        ("policy_reference", "fact_scope", "provided_sufficient", ["intake"], [source_ref(4)], False),
        ("customer_objective", "fact_dispute", "provided_sufficient", ["message"], [source_ref(5)], False),
        ("management_position", "fact_ventilation_allegation", "provided_sufficient", ["art_management_reply"], [source_ref(7)], False),
        ("health_safety_statement", "fact_urgency", "provided_sufficient", ["message"], [source_ref(8)], False),
        ("defect_notice", "fact_notification", "provided_sufficient", ["art_notification"], [source_ref(9)], True),
        ("proof_of_delivery", "fact_notification", "provided_sufficient", ["art_delivery"], [source_ref(10)], False),
        ("dated_photos", "fact_visible_mould", "provided_sufficient", ["art_photo"], [source_ref(11)], False),
        ("recurrence_chronology", "fact_recurrence", "provided_insufficient", ["art_timeline"], [source_ref(12)], False),
        ("technical_assessment", "fact_cause", "missing", [], [source_ref(5), source_ref(6)], False),
        ("moisture_measurements", "fact_cause", "conditional", [], [source_ref(13)], False),
        ("building_envelope", "fact_cause", "conditional", [], [source_ref(14)], False),
        ("repair_history", "fact_cause", "conditional", [], [source_ref(16)], False),
        ("use_evidence", "fact_ventilation_allegation", "not_applicable", [], [source_ref(15)], False),
        ("remediation_plan", "fact_cause", "not_applicable", [], [source_ref(17)], False),
        ("financial_impact", "fact_cause", "conditional", [], [source_ref(18)], False),
        ("settlement_proposal", "fact_dispute", "conditional", [], [source_ref(19)], False),
        ("conciliation_bundle", "fact_dispute", "conditional", [], [source_ref(20)], False),
        ("completion_record", "fact_dispute", "not_applicable", [], [source_ref(21)], False),
    ]
    evidence_specs = [
        (
            item_id,
            release_tool.RELEASE_EVIDENCE_FACT_ID_BY_CLAIM[
                "DEF-027-E0-DEMO"
            ][item_id],
            release_tool.RELEASE_BASE_EVIDENCE_STATUS_BY_CLAIM[
                "DEF-027-E0-DEMO"
            ][item_id],
            release_tool.RELEASE_EVIDENCE_ARTIFACT_IDS_BY_CLAIM[
                "DEF-027-E0-DEMO"
            ][item_id],
            source_ref_ids,
            False,
        )
        for (
            item_id,
            _fact_id,
            status,
            artifact_ids,
            source_ref_ids,
            fallback,
        ) in evidence_specs
    ]
    evidence_items = []
    for item_id, fact_id, status, artifact_ids, source_ref_ids, status_fallback in (
        evidence_specs
    ):
        field_contributions = [
            {
                "contribution_id": f"item:{item_id}:status",
                "field": "status",
                "attribution": (
                    "deterministic_application"
                    if status_fallback
                    else "Evidence and Checklist Agent"
                ),
                "confidence_basis_points": 10_000 if status_fallback else 9000,
                "deterministic_fallback_applied": status_fallback,
            },
            {
                "contribution_id": f"item:{item_id}:artifacts",
                "field": "artifact_ids",
                "attribution": "Evidence and Checklist Agent",
                "confidence_basis_points": 9000,
                "deterministic_fallback_applied": False,
            },
        ]
        evidence_items.append(
            {
                "item_id": item_id,
                "status": status,
                "artifact_ids": sorted(artifact_ids),
                "source_ref_ids": source_ref_ids,
                "field_contributions": field_contributions,
                "model_owned_fields": ["status", "artifact_ids"],
                "confidence_basis_points": 9000,
                "attribution": (
                    "mixed_model_and_deterministic"
                    if status_fallback
                    else "Evidence and Checklist Agent"
                ),
                "deterministic_fallback_applied": status_fallback,
            }
        )
    evidence_artifact = {"items": evidence_items}
    plan_artifact = {
        "model_priority_fact_ids": [
            "fact_cause",
            "fact_notification",
            "fact_dispute",
        ],
        "model_priority_task_codes": [
            "source_integrity",
            "process_decisions",
            "evidence_gaps",
            "final_brief",
        ],
        "priority_task_codes": [
            "source_integrity",
            "process_decisions",
            "evidence_gaps",
            "final_brief",
        ],
        "model_priority_attribution": "Nemotron Orchestrator",
        "deterministic_coverage": {
            "fact_ids": [
                "fact_scope",
                "fact_urgency",
                "fact_recurrence",
                "fact_ventilation_allegation",
                "fact_visible_mould",
            ],
            "source_ref_ids": [source_ref(1), source_ref(2)],
            "required_text_artifact_ids": ["art_notice", "art_reply"],
            "attribution": "deterministic_application",
        },
        "focus_fact_ids": [
            "fact_cause",
            "fact_notification",
            "fact_dispute",
            "fact_scope",
            "fact_urgency",
            "fact_recurrence",
            "fact_ventilation_allegation",
            "fact_visible_mould",
        ],
        "focus_source_ref_ids": [source_ref(1), source_ref(2)],
        "contribution_type": "constrained_focus_prioritization",
    }
    fixture_priority_fact_ids = plan_artifact["model_priority_fact_ids"]
    fixture_deterministic_fact_ids = [
        fact["fact_id"]
        for fact in canonical_facts
        if fact["fact_id"] not in fixture_priority_fact_ids
    ]
    plan_artifact["deterministic_coverage"]["fact_ids"] = (
        fixture_deterministic_fact_ids
    )
    plan_artifact["focus_fact_ids"] = [
        *fixture_priority_fact_ids,
        *fixture_deterministic_fact_ids,
    ]
    final_fields = [
        ("current_node_id", "final:current_node", False),
        ("next_action_node_id", "final:next_action", False),
        ("supporting_fact_ids", "final:supporting_facts", False),
        (
            "upstream_contribution_ids",
            "final:upstream_contributions",
            False,
        ),
        ("audit_check_ids", "final:audit_checks", False),
    ]
    final_claim_brief = {
        "current_node_id": "causation",
        "next_action_node_id": "evidence_gap",
        "supporting_fact_ids": ["fact_cause", "fact_ventilation_allegation"],
        "upstream_contribution_ids": list(
            release_tool.FINAL_UPSTREAM_CONTRIBUTION_IDS
        ),
        "audit_check_ids": list(release_tool.FINAL_AUDIT_CHECK_IDS),
        "source_ref_ids": [source_ref(5), source_ref(6), source_ref(7)],
        "input_contribution_ids": list(
            release_tool.FINAL_UPSTREAM_CONTRIBUTION_IDS
        ),
        "lineage_authority": "hybrid_guarded_model_audit",
        "contribution_scope": "independent_final_claim_brief_audit",
        "field_contributions": [
            {
                "contribution_id": contribution_id,
                "field": field,
                "attribution": (
                    "deterministic_application"
                    if fallback
                    else "Final Claim Brief Agent"
                ),
                "confidence_basis_points": 10_000 if fallback else 9200,
                "deterministic_fallback_applied": fallback,
            }
            for field, contribution_id, fallback in final_fields
        ],
        "confidence_basis_points": 9200,
        "attribution": "Final Claim Brief Agent",
        "deterministic_fallback_applied": False,
    }
    specialist_artifacts = {
        "orchestrator_plan": plan_artifact,
        "document_source_integrity": source_artifact,
        "process_decision_mapping": process_artifact,
        "evidence_checklist": evidence_artifact,
        "final_claim_brief_audit": final_claim_brief,
    }

    accepted_by_agent = {
        "canonical_facts": [fact["fact_id"] for fact in canonical_facts],
        "orchestrator_plan": ["model_priority_order"],
        "document_source_integrity": [
            item["artifact_id"] for item in source_artifact["artifacts"]
        ],
        "process_decision_mapping": [
            item["contribution_id"]
            for item in process_decisions
            if item["deterministic_fallback_applied"] is False
        ],
        "evidence_checklist": [
            field["contribution_id"]
            for item in evidence_items
            for field in item["field_contributions"]
            if field["deterministic_fallback_applied"] is False
        ],
        "final_claim_brief_audit": [
            field["contribution_id"]
            for field in final_claim_brief["field_contributions"]
            if field["deterministic_fallback_applied"] is False
        ],
    }
    rejected_by_agent = {
        "canonical_facts": 0,
        "orchestrator_plan": 0,
        "document_source_integrity": 0,
        "process_decision_mapping": 0,
        "evidence_checklist": 0,
        "final_claim_brief_audit": 0,
    }
    records = []
    for index, item in enumerate(required_agents, start=1):
        agent_id = item["agent_id"]
        if agent_id == "canonical_facts":
            parent_call_id = None
            delegation_id = None
        elif agent_id == "orchestrator_plan":
            parent_call_id = call_ids["canonical_facts"]
            delegation_id = f"delegation_{index:02d}"
        else:
            parent_call_id = call_ids["orchestrator_plan"]
            delegation_id = f"delegation_{index:02d}"
        records.append(
            {
                "agent_id": agent_id,
                "role": item["role"],
                "actor_type": "nemotron_agent",
                "acceptance_scope": "pre_review_model_output",
                "model": release_tool.REQUIRED_PRODUCTION_MODEL,
                "provider": "openrouter",
                "upstream_provider": "Together",
                "requested_model": release_tool.REQUIRED_PRODUCTION_MODEL,
                "response_model": release_tool.REQUIRED_PRODUCTION_MODEL,
                "finish_reason": "stop",
                "usage_source": "response",
                "call_id": call_ids[agent_id],
                "origin_call_id": call_ids[agent_id],
                "response_id": f"generation_runtime_proof_{index:02d}",
                "parent_call_id": parent_call_id,
                "delegation_id": delegation_id,
                "call_count": 1,
                "cache_hit": False,
                "outcome": (
                    "succeeded_with_guarded_fallback"
                    if rejected_by_agent[agent_id]
                    else "succeeded"
                ),
                "accepted_ids": accepted_by_agent[agent_id],
                "accepted_count": len(accepted_by_agent[agent_id]),
                "rejected_count": rejected_by_agent[agent_id],
                "source_reference_projection_fact_ids": (
                    [] if agent_id == "canonical_facts" else None
                ),
                "source_reference_projection_count": (
                    0 if agent_id == "canonical_facts" else None
                ),
                "deterministic_fallback_applied": bool(
                    rejected_by_agent[agent_id]
                ),
                "input_artifact_hash": f"{index:064x}",
                "output_artifact": (
                    "canonical_claim_state"
                    if agent_id == "canonical_facts"
                    else release_tool.SPECIALIST_OUTPUT_ARTIFACTS[agent_id]
                ),
                "output_artifact_hash": (
                    f"{index + 100:064x}"
                    if agent_id == "canonical_facts"
                    else release_tool.accepted_artifact_hash(
                        specialist_artifacts[agent_id]
                    )
                ),
            }
        )
    runtime = contract["agentic_runtime"]
    by_agent = {record["agent_id"]: record for record in records}
    lineage_fields = release_tool.ACCEPTED_LINEAGE_FIELDS

    def lineage(agent_id: str) -> dict:
        agent = by_agent[agent_id]
        return {field: agent[field] for field in lineage_fields if field in agent}

    legal = release_tool.governed_legal_context()
    assert len(decision_specs) == len(process_decisions)
    decisions_by_fact = {item["fact_id"]: item for item in process_decisions}
    facts_by_node = release_tool.RELEASE_PROCESS_FACT_IDS_BY_CLAIM[
        "DEF-027-E0-DEMO"
    ]
    requirements_by_node = {
        node_id: [
            item_id
            for item_id, owners in release_tool.BASE_EVIDENCE_NODE_IDS.items()
            if node_id in owners
        ]
        for node_id in release_tool.BASE_PROCESS_NODE_IDS
    }
    completed_nodes = ["intake", "scope", "dispute", "urgency", "notification", "defect"]
    process_nodes = []
    for node_id in release_tool.BASE_PROCESS_NODE_IDS:
        if node_id in completed_nodes:
            state = "complete"
        elif node_id == "causation":
            state = "current"
        elif node_id == "evidence_gap":
            state = "next"
        elif node_id in {"responsibility", "remedy"}:
            state = "blocked"
        elif node_id in {
            "out_of_scope",
            "no_dispute",
            "urgent_escalation",
            "formal_notice",
            "building_defect",
            "tenant_use",
            "mixed_cause",
        }:
            state = "inactive"
        else:
            state = "future"
        node = {
            "node_id": node_id,
            "title": node_id.replace("_", " ").title(),
            "question": f"What is the governed state of {node_id.replace('_', ' ')}?",
            "state": state,
            "answer": "Unresolved" if node_id == "causation" else "Fixture state",
            "why": "Bounded release-acceptance fixture process relationship.",
            "kind": "decision",
            "main_spine": node_id
            in {
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
            },
            "fact_ids": facts_by_node.get(node_id, []),
            "legal_source_ids": legal["node_links"].get(node_id, []),
            "evidence_requirement_ids": requirements_by_node[node_id],
            "branches": [],
            "activation": "always",
        }
        accepted_decisions = [
            decisions_by_fact[fact_id]
            for fact_id in node["fact_ids"]
            if fact_id in decisions_by_fact
        ]
        if accepted_decisions:
            node["agent_decision_contributions"] = accepted_decisions
        process_nodes.append(node)
    selected_path = [
        "intake",
        "scope",
        "dispute",
        "urgency",
        "notification",
        "defect",
        "causation",
        "evidence_gap",
    ]
    process = {
        "contract": "casepath.process-graph/15.2",
        "title": "Complete recurring-moisture claim-handling process",
        "playbook_version": "mould-playbook-v3",
        "current_node": "causation",
        "main_spine": [
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
        ],
        "selected_path": selected_path,
        "current_overlay": {
            "completed_node_ids": completed_nodes,
            "current_node_id": "causation",
            "selected_branch_id": "insufficient",
            "blocked_node_ids": ["responsibility", "remedy"],
            "inactive_branch_ids": [],
            "next_action_node_id": "evidence_gap",
            "decisions": {
                item["decision_key"]: item["decision_value"]
                for item in process_decisions
            },
        },
        "nodes": process_nodes,
        "edges": [
            {
                "source": source,
                "target": target,
                "condition": "governed fixture transition",
                "state": (
                    "selected"
                    if (source, target) in set(zip(selected_path, selected_path[1:]))
                    else "loop"
                    if (source, target) == ("evidence_gap", "causation")
                    else "possible"
                ),
            }
            for source, target in release_tool.BASE_PROCESS_EDGE_PAIRS
        ],
        "memory_used": False,
        "shared_rule_applied": False,
        "agent_contribution": {
            "authority": "hybrid_guarded_model_contribution",
            "model_owned_fields": ["decision_value"],
            "deterministic_fallback_fields": [],
            "deterministic_fallback_count": 0,
            "derived_from": "accepted_or_fallback_specialist_artifact",
            "artifact": process_artifact,
            "provenance": lineage("process_decision_mapping"),
            "source_integrity_artifact": source_artifact,
            "source_integrity_provenance": lineage(
                "document_source_integrity"
            ),
        },
    }
    fixture_projection = release_tool.decision_projection(
        [
            {
                "controls_process": True,
                "decision_key": item["decision_key"],
                "decision_value": item["decision_value"],
            }
            for item in process_decisions
        ]
    )
    process["current_node"] = fixture_projection["current_node"]
    process["selected_path"] = fixture_projection["selected_path"]
    process["current_overlay"] = release_tool.apply_process_projection(
        process["nodes"],
        process["edges"],
        fixture_projection,
        process["main_spine"],
    )
    public_evidence_items = []
    fact_by_evidence_item = {item_id: fact_id for item_id, fact_id, *_ in evidence_specs}
    active_nodes = set(selected_path)
    for item in evidence_items:
        item_id = item["item_id"]
        owners = list(release_tool.BASE_EVIDENCE_NODE_IDS[item_id])
        status = item["status"]
        public_evidence_items.append(
            {
                "item_id": item_id,
                "title": item_id.replace("_", " ").title(),
                "status": status,
                "node_ids": owners,
                "node_id": owners[0],
                "fact_id": fact_by_evidence_item[item_id],
                "why": "Bounded fixture evidence relationship.",
                "legal_basis_ids": release_tool.EVIDENCE_LEGAL_BASIS_IDS[item_id],
                "artifact_ids": deepcopy(
                    release_tool.RELEASE_EVIDENCE_ARTIFACT_IDS_BY_CLAIM[
                        "DEF-027-E0-DEMO"
                    ][item_id]
                ),
                "acceptable_alternatives": [],
                "current_path": bool(active_nodes.intersection(owners)),
                "applies_when": (
                    "The accepted process reaches this node"
                    if status == "conditional"
                    else "always"
                ),
                "required_level": (
                    "conditional" if status in {"conditional", "not_applicable"} else "mandatory"
                ),
                "agent_contribution": item["field_contributions"],
            }
        )
    final_claim_brief["source_ref_ids"] = sorted(
        {
            source_id
            for fact_id in final_claim_brief["supporting_fact_ids"]
            for source_id in [
                *next(
                    (
                        decision["source_ref_ids"]
                        for decision in process_decisions
                        if decision["fact_id"] == fact_id
                    ),
                    [],
                ),
                *[
                    source_id
                    for evidence in evidence_items
                    if fact_by_evidence_item[evidence["item_id"]] == fact_id
                    for source_id in evidence["source_ref_ids"]
                ],
            ]
        }
    )
    by_agent["final_claim_brief_audit"]["output_artifact_hash"] = (
        release_tool.accepted_artifact_hash(final_claim_brief)
    )
    derived = release_tool._checklist_derived_sections(public_evidence_items)
    checklist = {
        "contract": "casepath.evidence-model/15.2",
        "title": "Complete process-grounded evidence model",
        "items": public_evidence_items,
        **derived,
        "playbook_version": "mould-playbook-v3",
        "memory_used": False,
        "shared_rule_applied": False,
        "agent_contribution": {
            "authority": "hybrid_guarded_model_contribution",
            "model_owned_fields": ["status", "artifact_ids"],
            "deterministic_fallback_fields": [],
            "deterministic_fallback_count": 0,
            "derived_from": "accepted_or_fallback_specialist_artifact",
            "artifact": evidence_artifact,
            "provenance": lineage("evidence_checklist"),
        },
    }
    process["validator"] = {
        "valid": True,
        "computed": True,
        "checks": ["Graph integrity", "Law-to-process linkage", "Current-state safety"],
    }
    checklist["validator"] = {
        "valid": True,
        "computed": True,
        "checks": [
            "Process-to-evidence linkage",
            "Law-to-process linkage",
            "Current-state safety",
        ],
    }
    ranked = release_tool.rank_precedents(
        current_claim_id="DEF-027-E0-DEMO",
        understanding={
            "category": "Rental defect - mould and moisture",
            "subcategory": "Recurring moisture with disputed causation",
            "facts": canonical_facts,
        },
        process=process,
        checklist=checklist,
        memories=[],
        corpus=release_tool.GOVERNED_PRECEDENT_CORPUS,
    )
    verification = {
        "valid": True,
        "computed": True,
        "contract_version": "casepath.playbook-contracts/1.2.0",
        "checks": [
            {"name": name, "status": "passed", "detail": "Recomputed fixture check."}
            for name in release_tool.REQUIRED_PLAYBOOK_CHECKS
        ],
        "rejected_proposals": [],
        "accepted_artifacts": [
            "canonical_claim_state",
            "legal_context",
            "process_graph",
            "evidence_model",
            "precedents",
        ],
        "whole_playbook_hash": "c" * 64,
    }
    gate_bindings = {
        "deterministic_process_gate": (
            "process_graph",
            process,
            "process_decision_mapping",
        ),
        "deterministic_evidence_gate": (
            "evidence_model",
            checklist,
            "evidence_checklist",
        ),
        "whole_playbook_gate": (
            "verified_claim_playbook",
            {
                "process": release_tool._semantic_process_dto(process),
                "checklist": release_tool._semantic_checklist_dto(checklist),
                "final_brief": final_claim_brief,
            },
            "final_claim_brief_audit",
        ),
    }
    audit = {
        "orchestration_id": orchestration_id,
        "schema_version": runtime["orchestration_schema"],
        "implementation": runtime["implementation"],
        "authority_mode": runtime["authority_mode"],
        "model": runtime["model"],
        "framework": runtime["framework"],
        "model_assisted": True,
        "all_required_agents_contributed": True,
        "external_tracing": False,
        "prompt_storage": False,
        "raw_output_storage": False,
        "deterministic_safety_authority": True,
        "execution_topology": deepcopy(release_tool.REQUIRED_EXECUTION_TOPOLOGY),
        "guarded_fallback_count": 0,
        "agents": records,
        "deterministic_gates": [
            {
                "agent_id": gate_id,
                "role": next(
                    item["role"]
                    for item in release_tool.REQUIRED_DETERMINISTIC_GATES
                    if item["gate_id"] == gate_id
                ),
                "actor_type": "deterministic_gate",
                "receipt_type": "accepted_artifact",
                "acceptance_scope": "pre_review_model_output",
                "model": None,
                "outcome": "passed",
                "source_agent_id": source_agent_id,
                "source_call_id": by_agent[source_agent_id]["call_id"],
                "delegation_id": by_agent[source_agent_id]["delegation_id"],
                "accepted_ids": by_agent[source_agent_id]["accepted_ids"],
                "accepted_count": by_agent[source_agent_id]["accepted_count"],
                "input_artifact_hash": (
                    release_tool.accepted_artifact_hash(
                        {
                            "source_integrity": source_artifact,
                            "process_mapping": process_artifact,
                        }
                    )
                    if gate_id == "deterministic_process_gate"
                    else release_tool.accepted_artifact_hash(evidence_artifact)
                    if gate_id == "deterministic_evidence_gate"
                    else release_tool.accepted_artifact_hash(
                        {
                            "final_brief": final_claim_brief,
                            "verification": verification,
                        }
                    )
                ),
                "output_artifact": output_artifact,
                "output_artifact_hash": release_tool.accepted_artifact_hash(
                    artifact_value
                ),
                **(
                    {
                        "output_projection_contract": (
                            release_tool.WHOLE_PLAYBOOK_OUTPUT_PROJECTION_CONTRACT
                        ),
                        "final_brief_artifact_hash": release_tool.accepted_artifact_hash(
                            final_claim_brief
                        ),
                        "verification_report_hash": release_tool.accepted_artifact_hash(
                            verification
                        ),
                        "verification_whole_playbook_hash": verification[
                            "whole_playbook_hash"
                        ],
                        "accepted_verification_ids": [
                            item["name"] for item in verification["checks"]
                        ],
                    }
                    if gate_id == "whole_playbook_gate"
                    else {}
                ),
            }
            for index, (
                gate_id,
                (output_artifact, artifact_value, source_agent_id),
            ) in enumerate(gate_bindings.items(), start=1)
        ],
        "specialist_artifacts": specialist_artifacts,
        "final_claim_brief": final_claim_brief,
    }
    flagship_run = {
        "run_id": "flagship-run",
        "claim_id": "DEF-027-E0-DEMO",
        "status": "complete",
        "model_mode": release_tool.REQUIRED_PRODUCTION_MODE,
        "model": release_tool.REQUIRED_PRODUCTION_MODEL,
        "agent_orchestration": audit,
        "result": {
            "claim_id": "DEF-027-E0-DEMO",
            "summary": "Recurring mould with disputed causation.",
            "scope": "Swiss residential tenancy",
            "category": "Rental defect - mould and moisture",
            "subcategory": "Recurring moisture with disputed causation",
            "dispute": "Concrete dispute appears to exist",
            "issues": [],
            "process": process,
            "checklist": checklist,
            "legal_research": legal,
            "precedents": ranked["results"],
            "precedent_ranking": ranked["receipt"],
            "verification": verification,
            "current_overlay": process["current_overlay"],
            "facts": canonical_facts,
            "next_action": {
                "title": "Resolve the evidence gap",
                "detail": "Obtain the missing independent assessment.",
                "requires_expert_approval": True,
                "process_node_id": "evidence_gap",
                "agent_brief_contribution": final_claim_brief,
            },
            "agent_orchestration": audit,
            "audit": {
                "agent_orchestration": audit,
                "canonicalization": {
                    "mode": release_tool.REQUIRED_PRODUCTION_MODE,
                    "authority_mode": release_tool.REQUIRED_AUTHORITY_MODE,
                    "diagnostics": canonical_diagnostics,
                    "assertion_selections": assertion_selections,
                },
            },
        },
    }
    flagship_result = flagship_run["result"]
    flagship_run.update(
        {
            "understanding": {
                "summary": flagship_result["summary"],
                "category": flagship_result["category"],
                "subcategory": flagship_result["subcategory"],
                "scope": flagship_result["scope"],
                "dispute": flagship_result["dispute"],
                "facts": flagship_result["facts"],
                "issues": flagship_result["issues"],
                "observable_only": True,
                "canonicalization": flagship_result["audit"]["canonicalization"],
            },
            "process": flagship_result["process"],
            "checklist": flagship_result["checklist"],
            "precedents": flagship_result["precedents"],
            "precedent_ranking": flagship_result["precedent_ranking"],
            "verification": flagship_result["verification"],
        }
    )
    _refresh_causal_artifact_hashes({"flagship-run.json": flagship_run})
    by_agent["canonical_facts"]["output_artifact_hash"] = (
        release_tool.runtime_artifact_hash(flagship_run["result"]["facts"])
    )
    ledger = {
        "scope": "global_budget_ledger",
        "budget_scope": "instance_lifetime",
        "ledger_persistence": "ephemeral_instance",
        "items": [
            {
                "call_id": agent["call_id"],
                "orchestration_id": orchestration_id,
                "agent_id": agent["agent_id"],
                "parent_call_id": agent["parent_call_id"],
                "delegation_id": agent["delegation_id"],
                "cache_key": hashlib.sha256(
                    f"{orchestration_id}:{agent['agent_id']}".encode()
                ).hexdigest(),
                "call_count": 1,
                "estimated_cost_usd": 0.01,
                "provider": "openrouter",
                "provider_endpoint": "https://openrouter.ai/api/v1/chat/completions",
                "model": release_tool.REQUIRED_PRODUCTION_MODEL,
                "response_id": agent["response_id"],
                "response_model": agent["response_model"],
                "outcome": agent["outcome"],
                "upstream_provider": "Together",
                "usage_source": "response",
                "finish_reason": "stop",
                "prompt_tokens": 100 + index,
                "completion_tokens": 20 + index,
                "total_tokens": 120 + index * 2,
                "actual_cost_usd": 0.001 + index / 100_000,
                "deterministic_fallback_applied": agent[
                    "deterministic_fallback_applied"
                ],
                **(
                    {
                        "accepted_fact_ids": agent["accepted_ids"],
                        "accepted_fact_count": agent["accepted_count"],
                        "rejected_fact_count": agent["rejected_count"],
                        "source_reference_projection_fact_ids": agent[
                            "source_reference_projection_fact_ids"
                        ],
                        "source_reference_projection_count": agent[
                            "source_reference_projection_count"
                        ],
                    }
                    if agent["agent_id"] == "canonical_facts"
                    else {
                        "accepted_item_ids": agent["accepted_ids"],
                        "accepted_item_count": agent["accepted_count"],
                        "rejected_item_count": agent["rejected_count"],
                    }
                ),
            }
            for index, agent in enumerate(records, start=1)
        ],
    }
    ledger["summary"] = _ledger_summary(ledger["items"])
    for agent, item in zip(records, ledger["items"], strict=True):
        agent["usage"] = {
            "prompt_tokens": item["prompt_tokens"],
            "completion_tokens": item["completion_tokens"],
            "total_tokens": item["total_tokens"],
            "actual_cost_usd": item["actual_cost_usd"],
            "usage_source": item["usage_source"],
        }

    memory_id = "memory_release_replay"
    review_id = "review_release_replay"
    memory_content_hash = "9" * 64
    observable_hash = "8" * 64
    later_fact_id_map = {
        "fact_tenancy": "later_fact_tenancy",
        "fact_dispute": "later_fact_dispute",
        "fact_health": "later_fact_health",
        "fact_notification": "later_fact_notification",
        "fact_recurrence": "later_fact_recurrence",
        "fact_cause": "later_fact_cause",
        "fact_ventilation_allegation": "later_fact_ventilation_allegation",
    }
    later_facts = []
    for fact in canonical_facts:
        if fact["fact_id"] not in later_fact_id_map:
            continue
        later_fact = deepcopy(fact)
        later_fact["fact_id"] = later_fact_id_map[fact["fact_id"]]
        later_facts.append(later_fact)
    required_later_fact_ids = {
        fact_id
        for values in release_tool.RELEASE_PROCESS_FACT_IDS_BY_CLAIM[
            "DEMO-MOULD-002"
        ].values()
        for fact_id in values
    } | set(
        release_tool.RELEASE_EVIDENCE_FACT_ID_BY_CLAIM[
            "DEMO-MOULD-002"
        ].values()
    )
    existing_later_fact_ids = {fact["fact_id"] for fact in later_facts}
    later_facts.extend(
        canonical_fact(
            fact_id,
            label=fact_id.replace("_", " ").title(),
            value="Not yet established",
            state="unknown",
            source_refs=[],
        )
        for fact_id in sorted(required_later_fact_ids - existing_later_fact_ids)
    )
    later_facts[-1]["confidence"] = 0.0
    canonical_hash = release_tool.runtime_artifact_hash(later_facts)
    # The hosted QA writer parses and reserializes JSON, so JavaScript writes
    # an integral 0.0 as 0. The server hash remains authoritative and is bound
    # across the two runs and proof, while retained fact equality remains exact.
    later_facts[-1]["confidence"] = 0
    baseline_process = release_tool._semantic_process_dto(process)
    for node in baseline_process["nodes"]:
        node["fact_ids"] = deepcopy(
            release_tool.RELEASE_PROCESS_FACT_IDS_BY_CLAIM["DEMO-MOULD-002"][
                node["node_id"]
            ]
        )
    baseline_checklist = release_tool._semantic_checklist_dto(checklist)
    baseline_items_by_id = {
        item["item_id"]: item for item in baseline_checklist["items"]
    }
    baseline_checklist["items"] = [
        baseline_items_by_id[item_id]
        for item_id in release_tool.EVIDENCE_ITEM_IDS_BY_CLAIM["DEMO-MOULD-002"]
    ]
    for item in baseline_checklist["items"]:
        item["fact_id"] = release_tool.RELEASE_EVIDENCE_FACT_ID_BY_CLAIM[
            "DEMO-MOULD-002"
        ][item["item_id"]]
        item["artifact_ids"] = deepcopy(
            release_tool.RELEASE_EVIDENCE_ARTIFACT_IDS_BY_CLAIM[
                "DEMO-MOULD-002"
            ][item["item_id"]]
        )
        item["status"] = release_tool.RELEASE_BASE_EVIDENCE_STATUS_BY_CLAIM[
            "DEMO-MOULD-002"
        ][item["item_id"]]
    baseline_checklist.update(
        release_tool._checklist_derived_sections(baseline_checklist["items"])
    )
    baseline_result = {
        "claim_id": "DEMO-MOULD-002",
        "category": "Rental defect - mould and moisture",
        "subcategory": "Recurring moisture with disputed causation",
        "facts": deepcopy(later_facts),
        "process": baseline_process,
        "checklist": baseline_checklist,
        "precedents": deepcopy(ranked["results"]),
        "verification": {"valid": True, "whole_playbook_hash": "7" * 64},
        "audit": {
            "observable_input_hash": observable_hash,
            "canonical_state_hash": canonical_hash,
        },
        "reviewed_memory_used": False,
        "memory_application": None,
        "shared_rule_applied": False,
        "playbook": {"version": "mould-playbook-v3"},
        "next_action": {"agent_brief_contribution": None},
    }
    later_process = release_tool._semantic_process_dto(baseline_process)
    later_checklist = release_tool._semantic_checklist_dto(baseline_checklist)
    building_before = deepcopy(
        next(
            item
            for item in baseline_checklist["items"]
            if item["item_id"] == "building_envelope"
        )
    )
    use_before = deepcopy(
        next(
            item
            for item in baseline_checklist["items"]
            if item["item_id"] == "use_evidence"
        )
    )
    replay = release_tool._replay_memory_transform(
        later_process,
        later_checklist,
        "later_fact_ventilation_allegation",
    )
    later_verification = {"valid": True, "whole_playbook_hash": "6" * 64}
    later_result = {
        "claim_id": "DEMO-MOULD-002",
        "category": "Rental defect - mould and moisture",
        "subcategory": "Recurring moisture with disputed causation",
        "facts": deepcopy(later_facts),
        "process": later_process,
        "checklist": later_checklist,
        "precedents": [
            {
                "claim_id": "DEF-027-E0-DEMO",
                "memory_id": memory_id,
                "review_status": "unverified_demo_memory",
            },
            *deepcopy(ranked["results"][:2]),
        ],
        "verification": later_verification,
        "audit": {
            "observable_input_hash": observable_hash,
            "canonical_state_hash": canonical_hash,
        },
        "reviewed_memory_used": True,
        "shared_rule_applied": False,
        "playbook": {"version": "mould-playbook-v3"},
        "next_action": {"agent_brief_contribution": None},
    }
    fact_signature = release_tool._semantic_fact_signature(
        later_result["facts"], "fixture.later.facts"
    )
    semantic_signature_hash = release_tool.runtime_artifact_hash(
        {
            "category": "Rental defect - mould and moisture",
            "subcategory": "Recurring moisture with disputed causation",
            "required_decisions": release_tool.MEMORY_REQUIRED_DECISIONS,
            "required_fact_roles": release_tool.MEMORY_REQUIRED_FACT_ROLES,
        }
    )
    eligibility_checks = {
        "source_claim_excluded": True,
        "category_matched": True,
        "subcategory_matched": True,
        "required_decisions_matched": True,
        "ventilation_allegation_grounded": True,
        "semantic_signature_bound": True,
        "guidance_enabled": True,
    }
    eligibility_manifest = {
        "rule_id": "same_grounded_mould_signature_v2",
        "contract": "casepath.semantic-memory-eligibility/1.0.0",
        "claim_id": "DEMO-MOULD-002",
        "semantic_signature_hash": semantic_signature_hash,
        "decisions": deepcopy(release_tool.MEMORY_REQUIRED_DECISIONS),
        "facts_hash": release_tool.runtime_artifact_hash(fact_signature),
        "checks": eligibility_checks,
    }
    eligibility = {
        **eligibility_manifest,
        "eligible": True,
        "manifest_hash": release_tool.runtime_artifact_hash(eligibility_manifest),
    }
    baseline_boundary = {
        "process_dto_hash": release_tool.runtime_artifact_hash(baseline_process),
        "checklist_dto_hash": release_tool.runtime_artifact_hash(baseline_checklist),
        "process_semantic_hash": release_tool.runtime_artifact_hash(
            release_tool._semantic_process_dto(baseline_process)
        ),
        "checklist_semantic_hash": release_tool.runtime_artifact_hash(
            release_tool._semantic_checklist_dto(baseline_checklist)
        ),
    }
    before_boundary = {
        "process_dto_hash": "1" * 64,
        "checklist_dto_hash": "2" * 64,
        "process_semantic_hash": baseline_boundary["process_semantic_hash"],
        "checklist_semantic_hash": baseline_boundary["checklist_semantic_hash"],
    }
    after_boundary = {
        "process_dto_hash": release_tool.runtime_artifact_hash(later_process),
        "checklist_dto_hash": release_tool.runtime_artifact_hash(later_checklist),
        "process_semantic_hash": release_tool.runtime_artifact_hash(later_process),
        "checklist_semantic_hash": release_tool.runtime_artifact_hash(later_checklist),
    }
    receipt = {
        "receipt_type": "memory_application_receipt",
        "contract": "casepath.memory-application-receipt/1.0.0",
        "authority": "unverified_demo",
        "scope": "case_specific_guidance_only",
        "source_memory": {
            "memory_id": memory_id,
            "claim_id": "DEF-027-E0-DEMO",
            "review_id": review_id,
            "content_hash": memory_content_hash,
            "review_status": "unverified_demo_memory",
        },
        "target": {"run_id": "later-run", "claim_id": "DEMO-MOULD-002"},
        "observable_input_hash": observable_hash,
        "canonical_state_hash": canonical_hash,
        "eligibility": eligibility,
        "allowed_operation_ids": list(release_tool.MEMORY_OPERATION_IDS),
        "applied_operation_ids": list(release_tool.MEMORY_OPERATION_IDS),
        "process_operations": [
            {
                "operation_id": "add_ventilation_dispute_node",
                "operation": "add_node",
                "node_id": "ventilation_dispute",
                "evidence_requirement_ids": ["management_position", "use_evidence"],
                "after_hash": release_tool.runtime_artifact_hash(
                    replay["ventilation_node"]
                ),
            },
            {
                "operation_id": "add_evidence_gap_to_ventilation_edge",
                "operation": "add_edge",
                "source": "evidence_gap",
                "target": "ventilation_dispute",
                "after_hash": release_tool.runtime_artifact_hash(
                    replay["first_edge"]
                ),
            },
            {
                "operation_id": "add_ventilation_to_causation_edge",
                "operation": "add_edge",
                "source": "ventilation_dispute",
                "target": "causation",
                "after_hash": release_tool.runtime_artifact_hash(
                    replay["second_edge"]
                ),
            },
        ],
        "evidence_operations": [
            {
                "operation_id": "condition_building_envelope",
                "operation": "replace_item",
                "item_id": "building_envelope",
                "before_hash": release_tool.runtime_artifact_hash(building_before),
                "after_hash": release_tool.runtime_artifact_hash(
                    replay["building_envelope"]
                ),
            },
            {
                "operation_id": "reassign_use_evidence_to_ventilation",
                "operation": "reassign_item",
                "item_id": "use_evidence",
                "removed_from_node_ids": sorted(replay["removed_from"]),
                "added_to_node_id": "ventilation_dispute",
                "before_hash": release_tool.runtime_artifact_hash(use_before),
                "after_hash": release_tool.runtime_artifact_hash(
                    replay["use_evidence"]
                ),
            },
        ],
        "before": before_boundary,
        "after": after_boundary,
        "verification_hash": later_verification["whole_playbook_hash"],
        "shared_playbook_version": "mould-playbook-v3",
        "shared_rule_applied": False,
        "model_acceptance_reused": False,
        "applied": True,
    }
    receipt["application_hash"] = release_tool.runtime_artifact_hash(receipt)
    later_result["memory_application"] = receipt
    memory_boundary = {
        "contract": release_tool.MEMORY_BOUNDARY_CONTRACT,
        "target": deepcopy(receipt["target"]),
        "source_memory": {
            "memory_id": memory_id,
            "content_hash": memory_content_hash,
        },
        "before": deepcopy(before_boundary),
    }
    memory_boundary["boundary_hash"] = release_tool.runtime_artifact_hash(
        memory_boundary
    )
    memory_event = {
        "stage": "memory_application",
        "label": "Bounded case-specific memory guidance applied",
        "agent": "Deterministic Memory Application Gate",
        "actor_type": "deterministic_gate",
        "status": "completed",
        "implementation": "deterministic_case_specific_memory_transform",
        "model": None,
        "orchestrator": "casepath-langgraph-orchestrator/15.2",
        "validator": "casepath.memory-application-receipt/1.0.0",
        "prompt_version": None,
        "output_artifact": "case_specific_memory_guidance",
        **deepcopy(receipt),
    }
    baseline_run = {
        "run_id": "baseline-run",
        "claim_id": "DEMO-MOULD-002",
        "status": "complete",
        "profile": release_tool.DETERMINISTIC_REFERENCE_PROFILE,
        "model_mode": release_tool.DETERMINISTIC_REFERENCE_MODE,
        "model": None,
        "knowledge_mode": "baseline",
        "created_at": "2026-08-12T00:01:00+00:00",
        "completed_at": 1786492920.0,
        "events": [
            {
                "stage": "orchestrator",
                "label": "Deterministic reference comparison opened",
                "agent": "Claim Context Initialization Tool",
                "actor_type": "deterministic_tool",
                "status": "completed",
                "implementation": "deterministic_application_tool",
                "model": None,
            }
        ],
        "result": baseline_result,
    }
    later_run = {
        "run_id": "later-run",
        "claim_id": "DEMO-MOULD-002",
        "status": "complete",
        "profile": release_tool.DETERMINISTIC_REFERENCE_PROFILE,
        "model_mode": release_tool.DETERMINISTIC_REFERENCE_MODE,
        "model": None,
        "knowledge_mode": "current",
        "created_at": "2026-08-12T00:03:00+00:00",
        "completed_at": 1786493100.0,
        "memory_application_boundary": memory_boundary,
        "events": [memory_event],
        "result": later_result,
    }
    causal_delta = release_tool._keyed_dto_delta(baseline_result, later_result)
    candidate = {
        "candidate_id": "candidate_disputed_ventilation_v4",
        "status": "quarantined",
        "qualified_support_count": 0,
        "target_tests": {"status": "passed"},
        "protected_regression": {"status": "passed"},
        "approval": {"status": "pending", "qualified_reviewer": False},
    }
    freeze_memory = {
        "memory_id": memory_id,
        "review_id": review_id,
        "content_hash": memory_content_hash,
        "candidate_id": candidate["candidate_id"],
        "updated_at": "2026-08-12T00:00:00+00:00",
    }
    counterfactual_freeze = {
        "contract": "casepath.counterfactual-learning-freeze/1.0.0",
        "memory": freeze_memory,
        "identity_hash": release_tool.runtime_artifact_hash(freeze_memory),
        "application_suppressed": True,
    }
    baseline_run["counterfactual_learning_freeze"] = counterfactual_freeze

    def clone_warm_audit_and_ledger(
        cold_audit: dict,
        cold_items: list[dict],
        *,
        target_orchestration_id: str,
        namespace: str,
    ) -> tuple[dict, list[dict]]:
        warm_audit = deepcopy(cold_audit)
        warm_audit["orchestration_id"] = target_orchestration_id
        cold_by_agent = {item["agent_id"]: item for item in cold_audit["agents"]}
        cold_items_by_agent = {item["agent_id"]: item for item in cold_items}
        warm_call_id_by_agent = {
            item["agent_id"]: f"modelcall_{namespace}_{index:02d}"
            for index, item in enumerate(cold_audit["agents"], start=1)
        }
        warm_items = []
        for index, warm_agent in enumerate(warm_audit["agents"], start=1):
            agent_id = warm_agent["agent_id"]
            cold_agent = cold_by_agent[agent_id]
            cold_item = cold_items_by_agent[agent_id]
            parent_agent_id = next(
                (
                    candidate["agent_id"]
                    for candidate in cold_audit["agents"]
                    if candidate["call_id"] == cold_agent["parent_call_id"]
                ),
                None,
            )
            origin_usage = {
                "prompt_tokens": cold_item["prompt_tokens"],
                "completion_tokens": cold_item["completion_tokens"],
                "total_tokens": cold_item["total_tokens"],
                "actual_cost_usd": cold_item["actual_cost_usd"],
                "usage_source": cold_item["usage_source"],
            }
            warm_agent.update(
                {
                    "call_id": warm_call_id_by_agent[agent_id],
                    "origin_call_id": cold_agent["call_id"],
                    "parent_call_id": (
                        warm_call_id_by_agent[parent_agent_id]
                        if parent_agent_id is not None
                        else None
                    ),
                    "delegation_id": (
                        None
                        if cold_agent["delegation_id"] is None
                        else f"delegation_{namespace}_{index:02d}"
                    ),
                    "call_count": 0,
                    "cache_hit": True,
                    "outcome": "cache_hit",
                    "usage_source": "cache",
                    "usage": origin_usage,
                    "response_id": cold_agent["response_id"],
                    "response_model": cold_agent["response_model"],
                }
            )
            warm_item = deepcopy(cold_item)
            for field in (
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "latency_ms",
            ):
                warm_item.pop(field, None)
            warm_item.update(
                {
                    "call_id": warm_agent["call_id"],
                    "orchestration_id": target_orchestration_id,
                    "parent_call_id": warm_agent["parent_call_id"],
                    "delegation_id": warm_agent["delegation_id"],
                    "call_count": 0,
                    "estimated_cost_usd": 0,
                    "actual_cost_usd": None,
                    "outcome": "cache_hit",
                    "origin_call_id": cold_agent["call_id"],
                    "response_id": cold_agent["response_id"],
                    "response_model": cold_agent["response_model"],
                    "upstream_provider": "Together",
                    "origin_usage": origin_usage,
                    "origin_finish_reason": cold_item["finish_reason"],
                    "usage_source": "cache",
                    "finish_reason": cold_item["finish_reason"],
                }
            )
            warm_items.append(warm_item)
        warm_by_agent = {
            item["agent_id"]: item for item in warm_audit["agents"]
        }
        for gate in warm_audit["deterministic_gates"]:
            source_agent = warm_by_agent[gate["source_agent_id"]]
            gate["source_call_id"] = source_agent["call_id"]
            gate["delegation_id"] = source_agent["delegation_id"]
        return warm_audit, warm_items

    isolation_audit, isolation_warm_items = clone_warm_audit_and_ledger(
        audit,
        ledger["items"],
        target_orchestration_id="orch_release_acceptance_isolation",
        namespace="isolation",
    )
    isolation_run = deepcopy(flagship_run)
    isolation_run["run_id"] = "isolation-run"
    isolation_run["agent_orchestration"] = isolation_audit
    isolation_run["result"]["agent_orchestration"] = isolation_audit
    isolation_run["result"]["audit"]["agent_orchestration"] = isolation_audit
    isolation_ledger = {
        "scope": "global_budget_ledger",
        "budget_scope": "instance_lifetime",
        "ledger_persistence": "ephemeral_instance",
        "items": [*deepcopy(ledger["items"]), *isolation_warm_items],
    }
    isolation_ledger["summary"] = _ledger_summary(isolation_ledger["items"])

    deterministic_orchestration = {
        "executed": False,
        "authority_mode": release_tool.DETERMINISTIC_REFERENCE_MODE,
        "model": None,
        "external_tracing": False,
        "deterministic_safety_authority": True,
    }
    deterministic_canonicalization = {
        "implementation": "deterministic_reference_oracle",
        "model": None,
        "provider": None,
        "mode": release_tool.DETERMINISTIC_REFERENCE_MODE,
    }
    for run, result in (
        (baseline_run, baseline_result),
        (later_run, later_result),
    ):
        run["agent_orchestration"] = deepcopy(deterministic_orchestration)
        result["agent_orchestration"] = deepcopy(deterministic_orchestration)
        result["audit"].update(
            {
                "profile": release_tool.DETERMINISTIC_REFERENCE_PROFILE,
                "authority_mode": release_tool.DETERMINISTIC_REFERENCE_MODE,
                "canonicalization": deepcopy(deterministic_canonicalization),
                "agent_orchestration": deepcopy(deterministic_orchestration),
            }
        )
    causal_delta = release_tool._keyed_dto_delta(baseline_result, later_result)

    final_model_ledger = deepcopy(isolation_ledger)
    cache_lineage = {
        "contract": "casepath.flagship-cache-lineage/1.0.0",
        "requested_model": release_tool.REQUIRED_PRODUCTION_MODEL,
        "exact_response_models": sorted(
            release_tool.ACCEPTED_PRODUCTION_RESPONSE_MODELS
        ),
        "framework": deepcopy(release_tool.REQUIRED_FRAMEWORK),
        "cold_orchestration_id": audit["orchestration_id"],
        "warm_orchestration_id": isolation_audit["orchestration_id"],
        "cold_run_surface": "visible_browser_flagship",
        "warm_run_surface": "isolated_session_cache_replay",
        "cold_guarded_fallback_count": audit["guarded_fallback_count"],
        "warm_guarded_fallback_count": isolation_audit[
            "guarded_fallback_count"
        ],
        "lineage": [
            {
                "agent_id": cold_agent["agent_id"],
                "cold_call_id": cold_agent["call_id"],
                "warm_call_id": warm_agent["call_id"],
                "response_id": cold_agent["response_id"],
                "response_model": cold_agent["response_model"],
            }
            for cold_agent, warm_agent in zip(
                audit["agents"],
                isolation_audit["agents"],
                strict=True,
            )
        ],
        "provider_calls_during_isolation_replay": 0,
    }

    def learning_snapshot(run: dict, result: dict) -> dict:
        return {
            "run_id": run["run_id"],
            "completed_at": run["completed_at"],
            "result_hash": release_tool.runtime_artifact_hash(result),
            "verification_hash": result["verification"]["whole_playbook_hash"],
            "verification_valid": True,
            "observable_input_hash": observable_hash,
            "canonical_state_hash": canonical_hash,
            "process_dto_hash": release_tool.runtime_artifact_hash(result["process"]),
            "checklist_dto_hash": release_tool.runtime_artifact_hash(
                result["checklist"]
            ),
            "process_semantic_hash": release_tool.runtime_artifact_hash(
                release_tool._semantic_process_dto(result["process"])
            ),
            "checklist_semantic_hash": release_tool.runtime_artifact_hash(
                release_tool._semantic_checklist_dto(result["checklist"])
            ),
            "process_node_ids": [
                node["node_id"] for node in result["process"]["nodes"]
            ],
            "process_edge_pairs": [
                [edge["source"], edge["target"]]
                for edge in result["process"]["edges"]
            ],
            "current_node_id": result["process"]["current_node"],
            "required_now_item_ids": [
                item["item_id"]
                for item in result["checklist"]["required"]
                if item["status"] == "still_needed"
            ],
            "conditional_item_ids": [
                item["item_id"]
                for item in result["checklist"]["required"]
                if item["status"] == "conditional"
            ],
            "precedents": [
                {
                    "claim_id": item["claim_id"],
                    "memory_id": item.get("memory_id"),
                    "review_status": item["review_status"],
                }
                for item in result["precedents"]
            ],
            "reviewed_memory_used": result.get("reviewed_memory_used") is True,
            "memory_application": deepcopy(result.get("memory_application")),
            "shared_rule_applied": result.get("shared_rule_applied") is True,
            "playbook_version": result["playbook"]["version"],
        }

    proof = {
        "ready": True,
        "computed": True,
        "claim_id": "DEMO-MOULD-002",
        "baseline_run_id": "baseline-run",
        "later_run_id": "later-run",
        "counterfactual_learning_freeze": deepcopy(counterfactual_freeze),
        "before": learning_snapshot(baseline_run, baseline_result),
        "after": learning_snapshot(later_run, later_result),
        "changes": {"precedent_claim_ids_added": ["DEF-027-E0-DEMO"]},
        "reviewed_memory_proof": {
            "used": True,
            "memory_ids": [memory_id],
            "present_in_baseline": False,
            "present_in_later_run": True,
        },
        "causal_delta": causal_delta,
        "memory_application_proof": {
            "receipt_present": True,
            "receipt_valid": True,
            "source_memory_current": True,
            "before_hashes_match": True,
            "after_hashes_match": True,
            "allowed_delta_exact": True,
            "replay_exact": True,
            "application_hash": receipt["application_hash"],
        },
        "deterministic_checks": [
            {
                "name": name,
                "status": "passed",
                "detail": "Computed from the retained fixture DTOs.",
            }
            for name in release_tool.REQUIRED_LEARNING_CHECKS
        ],
        "candidate": candidate,
        "shared_rule": {
            "applied": False,
            "version_before": "mould-playbook-v3",
            "version_after": "mould-playbook-v3",
            "shared_knowledge_changed": False,
            "candidate_status": "quarantined",
        },
    }
    demo_review = {
        "accepted": True,
        "review_id": review_id,
        "memory_id": memory_id,
        "reviewer": {
            "type": "unverified_demo_user",
            "qualification_status": "not_verified",
        },
        "candidate": candidate,
    }
    review_record = {
        "decision": "approve_with_edit",
        "building_envelope_mode": "conditional",
        "confidence": 0.9,
        "justification": "Apply the neutral-assessment-first unverified demo edit.",
        "reviewer": deepcopy(demo_review["reviewer"]),
        "operations": [
            {"op": "fixture", "pointer": "/process/nodes/ventilation_dispute"}
        ],
        "authority": "unverified_demo",
    }
    reviewed_result = {
        "claim_id": "DEF-027-E0-DEMO",
        "category": "Rental defect - mould and moisture",
        "subcategory": "Recurring moisture with disputed causation",
        "current_blocker": "Technical cause remains unresolved",
        "facts": deepcopy(canonical_facts),
        "process": deepcopy(later_process),
        "checklist": deepcopy(later_checklist),
        "verification": {"valid": True, "whole_playbook_hash": "5" * 64},
        "next_action": {"agent_brief_contribution": None},
        "review": deepcopy(review_record),
    }
    review_transform = {
        "acceptance_scope": "post_review_unverified_transform",
        "authority": demo_review["reviewer"]["type"],
        "qualification_status": demo_review["reviewer"]["qualification_status"],
        "input_run_id": "flagship-run",
        "input_process_hash": "4" * 64,
        "input_checklist_hash": "3" * 64,
        "output_process_hash": release_tool.runtime_artifact_hash(
            reviewed_result["process"]
        ),
        "output_checklist_hash": release_tool.runtime_artifact_hash(
            reviewed_result["checklist"]
        ),
        "model_acceptance_reused": False,
    }
    reviewed_result["review_transform"] = review_transform
    demo_review.update(
        {
            "result": reviewed_result,
            "review": deepcopy(review_record),
            "review_transform": review_transform,
        }
    )
    post_review_run = {
        "run_id": "flagship-run",
        "claim_id": "DEF-027-E0-DEMO",
        "review_id": review_id,
        "memory_id": memory_id,
        "result": reviewed_result,
        "review_response": demo_review,
        "candidate": candidate,
        "events": [
            {
                "receipt_type": "knowledge_consolidation_receipt",
                "memory_id": memory_id,
                "memory_content_hash": memory_content_hash,
                "qualified_reviewer": False,
                "shared_knowledge_changed": False,
            }
        ],
    }
    commit = "a" * 40
    public_agentic_runtime = release_tool._expected_public_agentic_runtime()
    session_isolation = {
        "enabled": True,
        "header": "X-CasePath-Session",
        "format": "8-128 characters; ASCII letters, digits, dot, underscore, colon, or hyphen",
        "state_scope": "caller_session",
        "model_ledger_scope": "global",
        "session_reset_scope": "caller_session_only",
    }
    deployment = {
        "frontend": {
            "contract": "casepath.deployment-identity/1.0.0",
            "component": "frontend",
            "component_contract": contract["components"]["frontend"]["contract"],
            "component_version": contract["components"]["frontend"]["version"],
            "release_id": contract["release_id"],
            "source_commit": commit,
            "source_commit_source": "RENDER_GIT_COMMIT",
            "alignment_eligible": True,
            "service": contract["services"]["frontend"],
            "release_contract_sha256": None,
        },
        "api": {
            "status": "ok",
            "release_id": contract["release_id"],
            "release": contract["components"]["api"]["version"],
            "pipeline_release": contract["components"]["pipeline"]["version"],
            "source_commit": commit,
            "source_commit_aligned": True,
            "source_commit_conflict": False,
            "model_mode": release_tool.REQUIRED_PRODUCTION_MODE,
            "model": release_tool.REQUIRED_PRODUCTION_MODEL,
            "configured_model_identity": release_tool.REQUIRED_PRODUCTION_MODEL,
            "model_provider": "openrouter",
            "runtime_profile": release_tool.REQUIRED_RUNTIME_PROFILE,
            "agentic_runtime": deepcopy(public_agentic_runtime),
            "session_isolation": session_isolation,
            "generated_data_only": True,
            "real_claims_approved": False,
        },
        "qa": {
            "release_id": contract["release_id"],
            "source_commit": commit,
        },
    }
    gate = {
        "path": "browser-focused-v20.mjs",
        "sha256": "b" * 64,
        "bytes": 1234,
    }
    runtime_versions = {"node": "v24.14.1", "playwright": "1.55.0", "chromium": "140"}
    readiness = {
        "status": "ready",
        "database": "sqlite-demo",
        "claims": len(contract["claims"]),
        "artifacts": 12,
        "active_playbook": "mould-playbook-v3",
        "model_budget": {
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
        },
        "agentic_runtime": deepcopy(public_agentic_runtime),
    }
    release_contract_bytes = f"{json.dumps(contract, indent=2)}\n".encode()
    files = []
    for index, path in enumerate(
        sorted(release_tool.REQUIRED_QA_EVIDENCE_FILES),
        start=1,
    ):
        files.append(
            {
                "path": path,
                "sha256": (
                    hashlib.sha256(release_contract_bytes).hexdigest()
                    if path == "release-contract.json"
                    else f"{index:064x}"
                ),
                "bytes": (
                    len(release_contract_bytes)
                    if path == "release-contract.json"
                    else 100 + index
                ),
            }
        )
    deployment["frontend"]["release_contract_sha256"] = next(
        item["sha256"]
        for item in files
        if item["path"] == "release-contract.json"
    )
    manifest = {
        "contract": release_tool.QA_EVIDENCE_MANIFEST_CONTRACT,
        "release_id": contract["release_id"],
        "source_commit": commit,
        "gate": gate,
        "runtime": runtime_versions,
        "retained_before_session_reset": True,
        "retained_media_contract": {
            "json": list(release_tool.REQUIRED_QA_JSON_EVIDENCE_FILES),
            "screenshots": list(
                release_tool.REQUIRED_QA_SCREENSHOT_EVIDENCE_FILES
            ),
            "video": release_tool.REQUIRED_QA_VIDEO_EVIDENCE_FILE,
            "missing": [],
            "empty": [],
        },
        "files": files,
    }
    manifest_bytes = f"{json.dumps(manifest, indent=2)}\n".encode()
    report_checks = [
        {
            "name": "Eight returned facts each show their exact source first, then the accepted fact, with run-bound replay lineage",
            "passed": True,
            "detail": "Returned semantic work is visibly labelled and bound to the cold run.",
        },
        {
            "name": "The visible graph replays accepted facts and checked law without inventing new source reads, then clears its plan before each node",
            "passed": True,
            "detail": "Cached graph actions are visibly labelled returned-action replay.",
        },
        *[
        {
            "name": f"Production browser acceptance check {index:03d}",
            "passed": True,
            "detail": "Verified by the production-shaped runtime fixture.",
        }
        for index in range(3, 219)
        ],
    ]
    report = {
        "status": "passed",
        "release": contract["components"]["frontend"]["version"],
        "release_id": contract["release_id"],
        "baseUrl": contract["services"]["frontend"],
        "apiUrl": contract["services"]["api"],
        "passed": len(report_checks),
        "failed": 0,
        "checks": report_checks,
        "failures": {"console": [], "page": [], "request": [], "cleanup": []},
        "runIds": [
            flagship_run["run_id"],
            baseline_run["run_id"],
            later_run["run_id"],
        ],
        "deployment": deployment,
        "runtime": runtime_versions,
        "evidence": {
            "contract": "casepath.qa-evidence/1.0.0",
            "gate": gate,
            "files": files,
            "retained_before_session_reset": True,
            "manifest": {
                "path": "evidence-manifest.json",
                "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "bytes": len(manifest_bytes),
            },
        },
    }
    retained = {
        "deployment-identity.json": deepcopy(deployment),
        "release-contract.json": deepcopy(contract),
        "readiness-receipt.json": readiness,
        "isolation-run.json": isolation_run,
        "isolation-model-ledger.json": isolation_ledger,
        "flagship-run.json": flagship_run,
        "flagship-cold-model-ledger.json": ledger,
        "demo-review.json": demo_review,
        "post-review-run.json": post_review_run,
        "later-baseline-run.json": baseline_run,
        "later-after-memory-run.json": later_run,
        "learning-proof.json": proof,
        "model-ledger.json": final_model_ledger,
        "runtime-versions.json": deepcopy(runtime_versions),
        "flagship-cache-lineage.json": cache_lineage,
    }
    assert set(retained) == set(release_tool.REQUIRED_QA_JSON_EVIDENCE_FILES)
    assert len(manifest["files"]) == 30
    return report, manifest, retained, manifest_bytes


def _runtime_result_and_audit(retained: dict) -> tuple[dict, dict]:
    result = retained["flagship-run.json"]["result"]
    return result, result["audit"]["agent_orchestration"]


def _swap_parallel_agent_records(records: list[dict]) -> None:
    """Reproduce the valid nondeterministic completion order of the fan-out."""

    positions = {item["agent_id"]: index for index, item in enumerate(records)}
    document_index = positions["document_source_integrity"]
    process_index = positions["process_decision_mapping"]
    records[document_index], records[process_index] = (
        records[process_index],
        records[document_index],
    )


def _refresh_causal_artifact_hashes(retained: dict) -> None:
    """Re-sign fixture joins so a negative reaches the intended invariant."""

    result, audit = _runtime_result_and_audit(retained)
    artifacts = audit["specialist_artifacts"]
    agents = {item["agent_id"]: item for item in audit["agents"]}
    for agent_id in release_tool.SPECIALIST_ARTIFACT_IDS:
        agents[agent_id]["output_artifact_hash"] = (
            release_tool.accepted_artifact_hash(artifacts[agent_id])
        )

    process_artifact = artifacts["process_decision_mapping"]
    source_artifact = artifacts["document_source_integrity"]
    process_contribution = result["process"]["agent_contribution"]
    process_contribution["artifact"] = process_artifact
    process_contribution["source_integrity_artifact"] = source_artifact
    decisions = {
        item["fact_id"]: item for item in process_artifact["decisions"]
    }
    for node in result["process"]["nodes"]:
        expected = [
            decisions[fact_id]
            for fact_id in node.get("fact_ids", [])
            if fact_id in decisions
        ]
        if expected:
            node["agent_decision_contributions"] = expected
        else:
            node.pop("agent_decision_contributions", None)

    evidence_artifact = artifacts["evidence_checklist"]
    result["checklist"]["agent_contribution"]["artifact"] = evidence_artifact
    evidence_by_id = {
        item["item_id"]: item for item in evidence_artifact["items"]
    }
    expected_public_artifacts = (
        release_tool.RELEASE_EVIDENCE_ARTIFACT_IDS_BY_CLAIM[result["claim_id"]]
    )
    for item in result["checklist"]["items"]:
        accepted = evidence_by_id[item["item_id"]]
        item["status"] = accepted["status"]
        governed_order = expected_public_artifacts[item["item_id"]]
        item["artifact_ids"] = (
            deepcopy(governed_order)
            if sorted(governed_order) == accepted["artifact_ids"]
            else list(accepted["artifact_ids"])
        )
        item["agent_contribution"] = accepted["field_contributions"]
    result["checklist"].update(
        release_tool._checklist_derived_sections(result["checklist"]["items"])
    )

    final_artifact = artifacts["final_claim_brief_audit"]
    audit["final_claim_brief"] = final_artifact
    result["next_action"]["agent_brief_contribution"] = final_artifact
    gates = {item["agent_id"]: item for item in audit["deterministic_gates"]}
    gates["deterministic_process_gate"]["input_artifact_hash"] = (
        release_tool.accepted_artifact_hash(
            {
                "source_integrity": source_artifact,
                "process_mapping": process_artifact,
            }
        )
    )
    gates["deterministic_evidence_gate"]["input_artifact_hash"] = (
        release_tool.accepted_artifact_hash(evidence_artifact)
    )
    gates["deterministic_process_gate"]["output_artifact_hash"] = (
        release_tool.accepted_artifact_hash(result["process"])
    )
    gates["deterministic_evidence_gate"]["output_artifact_hash"] = (
        release_tool.accepted_artifact_hash(result["checklist"])
    )
    result["verification"]["whole_playbook_hash"] = (
        release_tool.runtime_artifact_hash(
            {
                "understanding": {
                    "summary": result["summary"],
                    "category": result["category"],
                    "subcategory": result["subcategory"],
                    "scope": result["scope"],
                    "dispute": result["dispute"],
                    "facts": release_tool._runtime_canonical_facts_value(
                        result["facts"], "fixture.result.facts"
                    ),
                    "issues": result["issues"],
                    "observable_only": True,
                    "canonicalization": result["audit"]["canonicalization"],
                },
                "legal": result["legal_research"],
                "process": result["process"],
                "checklist": result["checklist"],
                "precedents": result["precedents"],
                "precedent_ranking": result["precedent_ranking"],
            }
        )
    )
    accepted_bundle = {
        "process": release_tool._semantic_process_dto(result["process"]),
        "checklist": release_tool._semantic_checklist_dto(result["checklist"]),
        "final_brief": final_artifact,
    }
    gates["whole_playbook_gate"]["output_artifact_hash"] = (
        release_tool.accepted_artifact_hash(accepted_bundle)
    )
    gates["whole_playbook_gate"]["final_brief_artifact_hash"] = (
        release_tool.accepted_artifact_hash(final_artifact)
    )
    gates["whole_playbook_gate"]["verification_report_hash"] = (
        release_tool.accepted_artifact_hash(result["verification"])
    )
    gates["whole_playbook_gate"]["verification_whole_playbook_hash"] = result[
        "verification"
    ]["whole_playbook_hash"]
    run = retained["flagship-run.json"]
    run["understanding"] = {
        "summary": result["summary"],
        "category": result["category"],
        "subcategory": result["subcategory"],
        "scope": result["scope"],
        "dispute": result["dispute"],
        "facts": result["facts"],
        "issues": result["issues"],
        "observable_only": True,
        "canonicalization": result["audit"]["canonicalization"],
    }
    for key in (
        "process",
        "checklist",
        "precedents",
        "precedent_ranking",
        "verification",
    ):
        run[key] = result[key]


def test_dynamic_runtime_acceptance_passes_without_source_promotion() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    original = deepcopy(contract)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result = release_tool.verify_dynamic_runtime_acceptance(
        contract,
        report,
        manifest,
        retained,
        evidence_manifest_bytes=manifest_bytes,
    )
    assert result == {
        "release_id": contract["release_id"],
        "source_commit": "a" * 40,
        "orchestration_id": "orch_release_acceptance_test",
        "model_agents": 6,
        "deterministic_gates": 3,
        "status": "passed",
        "verdict_source": "dynamic_same_commit_qa_artifacts",
    }
    retained_facts = retained["later-baseline-run.json"]["result"]["facts"]
    assert (
        retained["learning-proof.json"]["before"]["canonical_state_hash"]
        != release_tool.runtime_artifact_hash(retained_facts)
    )
    assert contract == original


def test_release_assertion_id_matches_backend_versioned_algorithm() -> None:
    canonicalizer_path = (
        release_tool.API_SOURCE_ROOT / "casepath_api" / "canonicalizer.py"
    )
    tree = ast.parse(canonicalizer_path.read_text(encoding="utf-8"))
    schema_version = next(
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "SCHEMA_VERSION"
            for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
    )
    assertion_function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_assertion_id"
    )
    isolated_module = ast.fix_missing_locations(
        ast.Module(body=[assertion_function], type_ignores=[])
    )
    backend: dict[str, object] = {"json": json, "sha256": hashlib.sha256}
    exec(compile(isolated_module, str(canonicalizer_path), "exec"), backend)
    backend_assertion_id = backend["_assertion_id"]

    fact = {
        "fact_id": "fact_unicode",
        "state": "known",
        "value": "Mould observed in Zürich",
        "normalized_value": "supported",
    }
    assert release_tool.CANONICAL_ASSERTION_ID_CONTRACT == (
        f"{schema_version}#assertion-id"
    )
    assert release_tool._canonical_assertion_id(fact, "fixture.fact") == (
        backend_assertion_id(
            fact_id=fact["fact_id"],
            state=fact["state"],
            value=fact["value"],
            normalized_value=fact["normalized_value"],
        )
    )


@pytest.mark.parametrize(
    ("tamper", "expected_path"),
    [
        ("forged_id", r"canonicalization\.assertion_selections"),
        ("missing_receipt", r"assertion_selections\.fact_membership"),
        ("duplicate_receipt", r"assertion_selections"),
        ("controlling_fields", r"canonicalization\.assertion_selections"),
        ("noncontrolling_fields", r"canonicalization\.assertion_selections"),
        ("materialized_fields", r"canonicalization\.assertion_selections"),
        ("attribution", r"canonicalization\.assertion_selections"),
        ("fallback", r"canonicalization\.assertion_selections"),
        ("diagnostics", r"canonicalization\.diagnostics\.fact_membership"),
    ],
)
def test_dynamic_runtime_rejects_forged_assertion_selection_receipt(
    tamper: str,
    expected_path: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, _audit = _runtime_result_and_audit(retained)
    canonicalization = result["audit"]["canonicalization"]
    selections = canonicalization["assertion_selections"]
    controlling = next(
        item
        for item in selections
        if next(
            fact
            for fact in result["facts"]
            if fact["fact_id"] == item["fact_id"]
        )["controls_process"]
    )
    noncontrolling = next(
        item
        for item in selections
        if not next(
            fact
            for fact in result["facts"]
            if fact["fact_id"] == item["fact_id"]
        )["controls_process"]
    )
    if tamper == "forged_id":
        controlling["assertion_id"] = "assert_" + "f" * 24
    elif tamper == "missing_receipt":
        selections.pop()
    elif tamper == "duplicate_receipt":
        selections.append(deepcopy(selections[0]))
    elif tamper == "controlling_fields":
        controlling["model_owned_fields"] = ["source_ref_ids", "confidence"]
    elif tamper == "noncontrolling_fields":
        noncontrolling["model_owned_fields"] = [
            "assertion_id",
            "source_ref_ids",
            "confidence",
        ]
    elif tamper == "materialized_fields":
        controlling["materialized_fields"] = ["value", "state"]
    elif tamper == "attribution":
        controlling["attribution"] = "deterministic_application"
    elif tamper == "fallback":
        controlling["deterministic_fallback_applied"] = True
    elif tamper == "diagnostics":
        canonicalization["diagnostics"]["accepted_fact_ids"].pop()
        canonicalization["diagnostics"]["accepted_fact_count"] -= 1
    else:  # pragma: no cover - parametrization is the closed mutation catalog
        raise AssertionError(tamper)

    with pytest.raises(release_tool.VerificationError, match=expected_path):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def _apply_fixture_process_decisions(result: dict, decisions: list[dict]) -> None:
    projection = release_tool.decision_projection(
        [
            {
                "controls_process": True,
                "decision_key": item["decision_key"],
                "decision_value": item["decision_value"],
            }
            for item in decisions
        ]
    )
    process = result["process"]
    process["current_node"] = projection["current_node"]
    process["selected_path"] = projection["selected_path"]
    process["current_overlay"] = release_tool.apply_process_projection(
        process["nodes"], process["edges"], projection, process["main_spine"]
    )


def test_process_verifier_accepts_key_specific_conservative_route() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    _report, _manifest, retained, _manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, audit = _runtime_result_and_audit(retained)
    decisions = audit["specialist_artifacts"]["process_decision_mapping"][
        "decisions"
    ]
    scope = next(item for item in decisions if item["decision_key"] == "scope")
    scope["decision_value"] = "scope_unverified"
    _apply_fixture_process_decisions(result, decisions)
    _refresh_causal_artifact_hashes(retained)
    agents = {item["agent_id"]: item for item in audit["agents"]}
    returned = release_tool._verify_process_artifact(
        result,
        audit["specialist_artifacts"]["process_decision_mapping"],
        audit["specialist_artifacts"]["document_source_integrity"],
        agents["process_decision_mapping"],
        agents["document_source_integrity"],
    )
    assert next(item for item in returned if item["decision_key"] == "scope")[
        "decision_value"
    ] == "scope_unverified"
    assert result["process"]["current_overlay"]["decisions"]["scope"] == (
        "scope_unverified"
    )


def test_process_verifier_rejects_contradictory_bounded_route() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    _report, _manifest, retained, _manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, audit = _runtime_result_and_audit(retained)
    decisions = audit["specialist_artifacts"]["process_decision_mapping"][
        "decisions"
    ]
    next(item for item in decisions if item["decision_key"] == "scope")[
        "decision_value"
    ] = "out_of_scope"
    _refresh_causal_artifact_hashes(retained)
    agents = {item["agent_id"]: item for item in audit["agents"]}
    with pytest.raises(
        release_tool.VerificationError,
        match=r"process_decision_mapping\.decisions\[\]\.decision_value",
    ):
        release_tool._verify_process_artifact(
            result,
            audit["specialist_artifacts"]["process_decision_mapping"],
            audit["specialist_artifacts"]["document_source_integrity"],
            agents["process_decision_mapping"],
            agents["document_source_integrity"],
        )


def test_evidence_verifier_accepts_alternate_bounded_status() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    _report, _manifest, retained, _manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, audit = _runtime_result_and_audit(retained)
    item = next(
        value
        for value in audit["specialist_artifacts"]["evidence_checklist"]["items"]
        if value["item_id"] == "claim_message"
    )
    item["status"] = "provided_insufficient"
    _refresh_causal_artifact_hashes(retained)
    agent = next(
        value for value in audit["agents"] if value["agent_id"] == "evidence_checklist"
    )
    returned = release_tool._verify_evidence_artifact(
        result,
        audit["specialist_artifacts"]["evidence_checklist"],
        agent,
    )
    assert next(value for value in returned if value["item_id"] == "claim_message")[
        "status"
    ] == "provided_insufficient"


def _set_bounded_claim_message_status(run: dict, status: str) -> None:
    result = run["result"]
    audit = result["audit"]["agent_orchestration"]
    item = next(
        value
        for value in audit["specialist_artifacts"]["evidence_checklist"]["items"]
        if value["item_id"] == "claim_message"
    )
    item["status"] = status
    wrapper = {"flagship-run.json": run}
    _refresh_causal_artifact_hashes(wrapper)
    ranked = release_tool.rank_precedents(
        current_claim_id=result["claim_id"],
        understanding={
            "category": result["category"],
            "subcategory": result["subcategory"],
            "facts": result["facts"],
        },
        process=result["process"],
        checklist=result["checklist"],
        memories=[],
        corpus=release_tool.GOVERNED_PRECEDENT_CORPUS,
    )
    result["precedents"] = ranked["results"]
    result["precedent_ranking"] = ranked["receipt"]
    _refresh_causal_artifact_hashes(wrapper)


def test_dynamic_runtime_acceptance_allows_alternate_bounded_evidence_end_to_end() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    _set_bounded_claim_message_status(
        retained["flagship-run.json"], "provided_insufficient"
    )
    _set_bounded_claim_message_status(
        retained["isolation-run.json"], "provided_insufficient"
    )
    accepted = release_tool.verify_dynamic_runtime_acceptance(
        contract,
        report,
        manifest,
        retained,
        evidence_manifest_bytes=manifest_bytes,
    )
    assert accepted["status"] == "passed"
    assert next(
        item
        for item in retained["flagship-run.json"]["result"]["checklist"]["items"]
        if item["item_id"] == "claim_message"
    )["status"] == "provided_insufficient"


@pytest.mark.parametrize("tamper", ["artifact", "status", "branch", "derived"])
def test_evidence_verifier_rejects_contradictory_bounded_fields(tamper: str) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    _report, _manifest, retained, _manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, audit = _runtime_result_and_audit(retained)
    artifact_item = next(
        value
        for value in audit["specialist_artifacts"]["evidence_checklist"]["items"]
        if value["item_id"] == "claim_message"
    )
    if tamper == "artifact":
        artifact_item["artifact_ids"] = ["art_photo"]
    elif tamper == "status":
        artifact_item["status"] = "missing"
    _refresh_causal_artifact_hashes(retained)
    if tamper == "branch":
        public_item = next(
            value
            for value in result["checklist"]["items"]
            if value["item_id"] == "technical_assessment"
        )
        public_item["current_path"] = False
    elif tamper == "derived":
        result["checklist"]["summary"]["provided_sufficient"] += 1
    agent = next(
        value for value in audit["agents"] if value["agent_id"] == "evidence_checklist"
    )
    with pytest.raises(release_tool.VerificationError):
        release_tool._verify_evidence_artifact(
            result,
            audit["specialist_artifacts"]["evidence_checklist"],
            agent,
        )


def test_whole_playbook_gate_keeps_four_exact_distinct_hash_domains() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    _report, _manifest, retained, _manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, audit = _runtime_result_and_audit(retained)
    whole_gate = next(
        gate
        for gate in audit["deterministic_gates"]
        if gate["agent_id"] == "whole_playbook_gate"
    )
    accepted_bundle = {
        "process": release_tool._semantic_process_dto(result["process"]),
        "checklist": release_tool._semantic_checklist_dto(result["checklist"]),
        "final_brief": audit["final_claim_brief"],
    }
    assert whole_gate["output_projection_contract"] == (
        release_tool.WHOLE_PLAYBOOK_OUTPUT_PROJECTION_CONTRACT
    )
    assert whole_gate["output_artifact_hash"] == (
        release_tool.accepted_artifact_hash(accepted_bundle)
    )
    assert whole_gate["final_brief_artifact_hash"] == (
        release_tool.accepted_artifact_hash(audit["final_claim_brief"])
    )
    assert whole_gate["verification_report_hash"] == (
        release_tool.accepted_artifact_hash(result["verification"])
    )
    assert whole_gate["verification_whole_playbook_hash"] == result["verification"][
        "whole_playbook_hash"
    ]
    assert len(
        {
            whole_gate["output_artifact_hash"],
            whole_gate["final_brief_artifact_hash"],
            whole_gate["verification_report_hash"],
            result["verification"]["whole_playbook_hash"],
        }
    ) == 4


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("understanding", r"run\.understanding"),
        ("precedents", r"run\.precedents"),
        ("precedent_ranking", r"run\.precedent_ranking"),
    ],
)
def test_dynamic_runtime_rejects_stale_top_level_accepted_siblings(
    field: str,
    expected: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    flagship = retained["flagship-run.json"]
    if field == "understanding":
        flagship[field] = {**flagship[field], "summary": "stale stage snapshot"}
    elif field == "precedents":
        flagship[field] = list(reversed(flagship[field]))
    else:
        flagship[field] = {**flagship[field], "context_hash": "0" * 64}

    with pytest.raises(release_tool.VerificationError, match=expected):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


@pytest.mark.parametrize(
    ("forgery", "expected"),
    [
        ("bundle", r"whole_playbook_gate\.output_artifact_hash"),
        ("brief", r"whole_playbook_gate\.final_brief_artifact_hash"),
        ("report", r"whole_playbook_gate\.verification_report_hash"),
        (
            "gate_whole",
            r"whole_playbook_gate\.verification_whole_playbook_hash",
        ),
        ("whole", r"result\.verification\.whole_playbook_hash"),
        ("projection", r"whole_playbook_gate\.output_projection_contract"),
    ],
)
def test_dynamic_runtime_rejects_conflated_whole_playbook_hashes(
    forgery: str,
    expected: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, audit = _runtime_result_and_audit(retained)
    whole_gate = next(
        gate
        for gate in audit["deterministic_gates"]
        if gate["agent_id"] == "whole_playbook_gate"
    )
    if forgery == "bundle":
        whole_gate["output_artifact_hash"] = whole_gate["final_brief_artifact_hash"]
    elif forgery == "brief":
        whole_gate["final_brief_artifact_hash"] = whole_gate["output_artifact_hash"]
    elif forgery == "report":
        whole_gate["verification_report_hash"] = result["verification"][
            "whole_playbook_hash"
        ]
    elif forgery == "gate_whole":
        whole_gate["verification_whole_playbook_hash"] = whole_gate[
            "output_artifact_hash"
        ]
    elif forgery == "whole":
        result["verification"]["whole_playbook_hash"] = whole_gate[
            "output_artifact_hash"
        ]
        whole_gate["verification_report_hash"] = release_tool.accepted_artifact_hash(
            result["verification"]
        )
    else:
        whole_gate["output_projection_contract"] = "ambiguous-full-dto"

    with pytest.raises(release_tool.VerificationError, match=expected):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


@pytest.mark.parametrize(
    "forgery",
    ["agent_outcome", "agent_rejection", "agent_fallback", "source_projection", "ledger_outcome"],
)
def test_dynamic_runtime_requires_six_clean_model_calls(forgery: str) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, audit = _runtime_result_and_audit(retained)
    canonical = next(
        agent for agent in audit["agents"] if agent["agent_id"] == "canonical_facts"
    )
    if forgery == "agent_outcome":
        canonical["outcome"] = "succeeded_with_guarded_fallback"
    elif forgery == "agent_rejection":
        canonical["rejected_count"] = 1
    elif forgery == "agent_fallback":
        canonical["deterministic_fallback_applied"] = True
    elif forgery == "source_projection":
        canonical["source_reference_projection_fact_ids"] = [canonical["accepted_ids"][0]]
        canonical["source_reference_projection_count"] = 1
    else:
        retained["flagship-cold-model-ledger.json"]["items"][0]["outcome"] = (
            "succeeded_with_guarded_fallback"
        )

    with pytest.raises(release_tool.VerificationError):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_requires_visible_returned_action_replay_checks() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    report["checks"][0]["name"] = "Generic semantic replay check"
    with pytest.raises(release_tool.VerificationError, match="report integrity"):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


@pytest.mark.parametrize(
    ("artifact", "claim_id", "expected"),
    [
        ("flagship-run.json", "DEF-027-E0-DEMO", r"result\.checklist\.items"),
        (
            "later-baseline-run.json",
            "DEMO-MOULD-002",
            r"learning\.baseline\.checklist\.items",
        ),
    ],
)
def test_dynamic_runtime_acceptance_enforces_claim_specific_checklist_order(
    artifact: str,
    claim_id: str,
    expected: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result = retained[artifact]["result"]
    item_ids = [item["item_id"] for item in result["checklist"]["items"]]
    assert tuple(item_ids) == release_tool.EVIDENCE_ITEM_IDS_BY_CLAIM[claim_id]
    result["checklist"]["items"][-1], result["checklist"]["items"][-2] = (
        result["checklist"]["items"][-2],
        result["checklist"]["items"][-1],
    )
    if artifact == "flagship-run.json":
        _refresh_causal_artifact_hashes(retained)
    with pytest.raises(release_tool.VerificationError, match=expected):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


@pytest.mark.parametrize("forgery", ["missing_field", "current_node", "edge_pair"])
def test_dynamic_runtime_acceptance_rejects_forged_learning_snapshot(
    forgery: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    before = retained["learning-proof.json"]["before"]
    if forgery == "missing_field":
        del before["result_hash"]
        expected = r"learning\.proof\.before"
    elif forgery == "current_node":
        before["current_node_id"] = "forged"
        expected = r"learning\.proof\.before"
    else:
        before["process_edge_pairs"][0] = ["intake", "forged"]
        expected = r"learning\.proof\.before"
    with pytest.raises(release_tool.VerificationError, match=expected):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_rejects_self_consistent_semantic_fact_rebind() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, _audit = _runtime_result_and_audit(retained)
    forged_fact_id = "fact_forged_ventilation_allegation"
    semantic_fact = next(
        fact
        for fact in result["facts"]
        if fact["semantic_role"] == release_tool.SEMANTIC_MEMORY_ROLE
    )
    semantic_fact["fact_id"] = forged_fact_id
    causation = next(
        node for node in result["process"]["nodes"] if node["node_id"] == "causation"
    )
    causation["fact_ids"] = [
        forged_fact_id if fact_id == "fact_ventilation_allegation" else fact_id
        for fact_id in causation["fact_ids"]
    ]
    _refresh_causal_artifact_hashes(retained)

    with pytest.raises(
        release_tool.VerificationError,
        match=r"result\.fact_relationships",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


@pytest.mark.parametrize(
    "forgery",
    [
        "same_fact_source_swap",
        "fact_unbound_capability",
        "artifact_append",
        "status_promotion",
    ],
)
def test_dynamic_runtime_acceptance_rejects_self_consistent_evidence_forgery(
    forgery: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, audit = _runtime_result_and_audit(retained)
    by_id = {
        item["item_id"]: item
        for item in audit["specialist_artifacts"]["evidence_checklist"]["items"]
    }
    if forgery == "same_fact_source_swap":
        by_id["defect_notice"]["artifact_ids"] = ["art_delivery"]
    elif forgery == "fact_unbound_capability":
        by_id["customer_objective"]["artifact_ids"] = [
            "art_notification",
            "message",
        ]
        public_item = next(
            item
            for item in result["checklist"]["items"]
            if item["item_id"] == "customer_objective"
        )
        public_item["artifact_ids"] = ["art_notification", "message"]
    elif forgery == "artifact_append":
        by_id["technical_assessment"]["artifact_ids"] = ["art_photo"]
    else:
        by_id["technical_assessment"]["status"] = "provided_sufficient"
    _refresh_causal_artifact_hashes(retained)
    ranked = release_tool.rank_precedents(
        current_claim_id=result["claim_id"],
        understanding={
            "category": result["category"],
            "subcategory": result["subcategory"],
            "facts": result["facts"],
        },
        process=result["process"],
        checklist=result["checklist"],
        memories=[],
        corpus=release_tool.GOVERNED_PRECEDENT_CORPUS,
    )
    result["precedents"] = ranked["results"]
    result["precedent_ranking"] = ranked["receipt"]
    _refresh_causal_artifact_hashes(retained)

    with pytest.raises(
        release_tool.VerificationError,
        match=r"evidence_checklist\.items\[.*\]\.coherence",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


@pytest.mark.parametrize("forgery", ["node_ids", "current_path"])
def test_dynamic_runtime_acceptance_rejects_forged_reciprocal_evidence_path(
    forgery: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, _audit = _runtime_result_and_audit(retained)
    item = next(
        value
        for value in result["checklist"]["items"]
        if value["item_id"] == "technical_assessment"
    )
    if forgery == "node_ids":
        item["node_ids"] = list(reversed(item["node_ids"]))
        item["node_id"] = item["node_ids"][0]
    else:
        item["current_path"] = not item["current_path"]
    _refresh_causal_artifact_hashes(retained)

    with pytest.raises(
        release_tool.VerificationError,
        match=r"result\.checklist\.items\[",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


@pytest.mark.parametrize("forgery", ["passage_hashes", "snapshot_scope", "node_join"])
def test_dynamic_runtime_acceptance_rejects_self_consistent_law_registry_forgery(
    forgery: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, _audit = _runtime_result_and_audit(retained)
    legal = result["legal_research"]
    bwo = next(
        source
        for source in legal["sources"]
        if source["source_id"] == "bwo-conciliation"
    )
    if forgery == "passage_hashes":
        bwo["passage_text"] += " Forged but internally rehashed."
        forged_hash = hashlib.sha256(bwo["passage_text"].encode()).hexdigest()
        bwo["passage_sha256"] = forged_hash
        bwo["retrieval"]["snapshot_sha256"] = forged_hash
    elif forgery == "snapshot_scope":
        bwo["retrieval"]["snapshot_scope"] = "official_pdf_bytes"
    else:
        legal["node_links"]["scope"] = []
        scope = next(
            node for node in result["process"]["nodes"] if node["node_id"] == "scope"
        )
        scope["legal_source_ids"] = []
    _refresh_causal_artifact_hashes(retained)

    with pytest.raises(
        release_tool.VerificationError,
        match=r"result\.legal_research",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


@pytest.mark.parametrize("field", ["producer", "image_sha256"])
def test_dynamic_runtime_acceptance_rejects_forged_visual_annotation(
    field: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, _audit = _runtime_result_and_audit(retained)
    visual_ref = next(
        ref
        for fact in result["facts"]
        for ref in fact["source_refs"]
        if ref["locator_kind"] == "visual_observation"
    )
    visual_ref[field] = "forged-producer" if field == "producer" else "f" * 64

    with pytest.raises(
        release_tool.VerificationError,
        match=r"result\.facts\[",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_rejects_rehashed_precedent_ranking_forgery() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, _audit = _runtime_result_and_audit(retained)
    result["precedents"][0]["title"] = "Forged precedent title"
    result["precedent_ranking"]["result_hash"] = release_tool.runtime_artifact_hash(
        result["precedents"]
    )

    with pytest.raises(
        release_tool.VerificationError,
        match=r"result\.precedents",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


@pytest.mark.parametrize(
    "forgery",
    [
        "replay_exact",
        "check_status",
        "check_order",
        "before_hash",
        "canonical_baseline",
    ],
)
def test_dynamic_runtime_acceptance_rejects_forged_learning_proof(
    forgery: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    proof = retained["learning-proof.json"]
    if forgery == "replay_exact":
        proof["memory_application_proof"]["replay_exact"] = False
        expected = r"learning\.proof\.memory_application_proof"
    elif forgery == "check_status":
        proof["deterministic_checks"][0]["status"] = "failed"
        expected = r"learning\.proof\.deterministic_checks"
    elif forgery == "check_order":
        proof["deterministic_checks"] = list(
            reversed(proof["deterministic_checks"])
        )
        expected = r"learning\.proof\.deterministic_checks"
    elif forgery == "before_hash":
        later = retained["later-after-memory-run.json"]["result"]
        receipt = later["memory_application"]
        forged_hash = "f" * 64
        receipt["before"]["process_dto_hash"] = forged_hash
        proof["before"]["process_dto_hash"] = forged_hash
        receipt_without_hash = {
            key: value for key, value in receipt.items() if key != "application_hash"
        }
        receipt["application_hash"] = release_tool.runtime_artifact_hash(
            receipt_without_hash
        )
        proof["memory_application_proof"]["application_hash"] = receipt[
            "application_hash"
        ]
        expected = r"learning\.later\.memory_application_boundary"
    else:
        baseline = retained["later-baseline-run.json"]["result"]
        nonsemantic_fact = next(
            fact for fact in baseline["facts"] if fact["semantic_role"] is None
        )
        nonsemantic_fact["value"] = "Forged baseline canonical state"
        expected = r"learning\.input_and_canonical_binding"

    with pytest.raises(release_tool.VerificationError, match=expected):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("label", "FORGED LABEL"),
        ("explanation", "FORGED EXPLANATION"),
        ("confidence", 0.123456),
    ],
)
def test_dynamic_runtime_acceptance_hash_binds_json_normalized_facts(
    field: str,
    forged_value: object,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    baseline_facts = retained["later-baseline-run.json"]["result"]["facts"]
    later_facts = retained["later-after-memory-run.json"]["result"]["facts"]
    assert any(fact["confidence"] == 0 for fact in baseline_facts)
    assert release_tool.runtime_artifact_hash(baseline_facts) != retained[
        "later-baseline-run.json"
    ]["result"]["audit"]["canonical_state_hash"]
    for facts in (baseline_facts, later_facts):
        target = next(fact for fact in facts if fact["semantic_role"] is None)
        target[field] = forged_value

    with pytest.raises(
        release_tool.VerificationError,
        match=r"learning\.input_and_canonical_binding",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_runtime_canonical_facts_hash_restores_only_declared_float_fields() -> None:
    retained = [
        {
            "fact_id": "fact_numeric_round_trip",
            "label": "Exact label remains bound",
            "explanation": "Exact explanation remains bound",
            "confidence": 1,
            "source_refs": [
                {
                    "locator_kind": "visual_observation",
                    "region": [0, 0, 1, 1],
                }
            ],
        }
    ]
    server = deepcopy(retained)
    server[0]["confidence"] = 1.0
    server[0]["source_refs"][0]["region"] = [0.0, 0.0, 1.0, 1.0]
    assert release_tool._runtime_canonical_facts_hash(
        retained, "fixture.facts"
    ) == release_tool.runtime_artifact_hash(server)


def test_dynamic_runtime_acceptance_allows_integral_fact_float_round_trip() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, audit = _runtime_result_and_audit(retained)
    fact = result["facts"][0]
    fact["confidence"] = 1
    _refresh_causal_artifact_hashes(retained)
    server_facts = deepcopy(result["facts"])
    server_facts[0]["confidence"] = 1.0
    canonical_agent = next(
        agent
        for agent in audit["agents"]
        if agent["agent_id"] == "canonical_facts"
    )
    canonical_agent["output_artifact_hash"] = release_tool.runtime_artifact_hash(
        server_facts
    )
    isolation_audit = retained["isolation-run.json"]["agent_orchestration"]
    isolation_canonical_agent = next(
        agent
        for agent in isolation_audit["agents"]
        if agent["agent_id"] == "canonical_facts"
    )
    isolation_canonical_agent["output_artifact_hash"] = canonical_agent[
        "output_artifact_hash"
    ]

    assert release_tool.verify_dynamic_runtime_acceptance(
        contract,
        report,
        manifest,
        retained,
        evidence_manifest_bytes=manifest_bytes,
    )["status"] == "passed"


@pytest.mark.parametrize("forgery", ["target", "source_memory", "before"])
def test_dynamic_runtime_acceptance_rejects_rehashed_memory_boundary_forgery(
    forgery: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    later_run = retained["later-after-memory-run.json"]
    boundary = later_run["memory_application_boundary"]
    if forgery == "target":
        boundary["target"]["claim_id"] = "FORGED-CLAIM"
    elif forgery == "source_memory":
        boundary["source_memory"]["content_hash"] = "f" * 64
    else:
        boundary["before"]["process_dto_hash"] = "f" * 64
    boundary_without_hash = {
        key: value for key, value in boundary.items() if key != "boundary_hash"
    }
    boundary["boundary_hash"] = release_tool.runtime_artifact_hash(
        boundary_without_hash
    )

    with pytest.raises(
        release_tool.VerificationError,
        match=r"learning\.later\.memory_application_boundary",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_rejects_result_and_boundary_forgery_not_in_event() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    baseline = retained["later-baseline-run.json"]["result"]
    later_run = retained["later-after-memory-run.json"]
    later = later_run["result"]
    proof = retained["learning-proof.json"]
    receipt = later["memory_application"]
    boundary = later_run["memory_application_boundary"]
    baseline["process"]["title"] = "Rehashed forged pre-transform title"
    exact_before = {
        "process_dto_hash": release_tool.runtime_artifact_hash(baseline["process"]),
        "checklist_dto_hash": release_tool.runtime_artifact_hash(
            baseline["checklist"]
        ),
        "process_semantic_hash": release_tool.runtime_artifact_hash(
            release_tool._semantic_process_dto(baseline["process"])
        ),
        "checklist_semantic_hash": release_tool.runtime_artifact_hash(
            release_tool._semantic_checklist_dto(baseline["checklist"])
        ),
    }
    receipt["before"] = deepcopy(exact_before)
    boundary["before"] = deepcopy(exact_before)
    proof["before"].update(exact_before)
    receipt_without_hash = {
        key: value for key, value in receipt.items() if key != "application_hash"
    }
    receipt["application_hash"] = release_tool.runtime_artifact_hash(
        receipt_without_hash
    )
    proof["memory_application_proof"]["application_hash"] = receipt[
        "application_hash"
    ]
    boundary_without_hash = {
        key: value for key, value in boundary.items() if key != "boundary_hash"
    }
    boundary["boundary_hash"] = release_tool.runtime_artifact_hash(
        boundary_without_hash
    )

    with pytest.raises(
        release_tool.VerificationError,
        match=r"learning\.later\.memory_application_event",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_rejects_duplicate_memory_application_event() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    later_run = retained["later-after-memory-run.json"]
    later_run["events"].append(deepcopy(later_run["events"][0]))

    with pytest.raises(
        release_tool.VerificationError,
        match=r"learning\.later\.memory_application_event",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_rejects_required_now_reusable_authority_forgery() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    demo_review = retained["demo-review.json"]
    reviewed_result = demo_review["result"]
    reviewed_result["review"]["building_envelope_mode"] = "required_now"
    demo_review["review"]["building_envelope_mode"] = "required_now"

    with pytest.raises(
        release_tool.VerificationError,
        match=r"learning\.source_memory",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_rejects_rehashed_non_replay_learning_change() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    baseline = retained["later-baseline-run.json"]["result"]
    later = retained["later-after-memory-run.json"]["result"]
    proof = retained["learning-proof.json"]
    receipt = later["memory_application"]
    ventilation = next(
        node
        for node in later["process"]["nodes"]
        if node["node_id"] == "ventilation_dispute"
    )
    ventilation["answer"] = "Forged learned answer outside the pure replay transform."
    semantic_process = release_tool._semantic_process_dto(later["process"])
    semantic_checklist = release_tool._semantic_checklist_dto(later["checklist"])
    after_boundary = {
        "process_dto_hash": release_tool.runtime_artifact_hash(later["process"]),
        "checklist_dto_hash": release_tool.runtime_artifact_hash(later["checklist"]),
        "process_semantic_hash": release_tool.runtime_artifact_hash(semantic_process),
        "checklist_semantic_hash": release_tool.runtime_artifact_hash(
            semantic_checklist
        ),
    }
    receipt["after"] = deepcopy(after_boundary)
    proof["after"].update(after_boundary)
    proof["causal_delta"] = release_tool._keyed_dto_delta(baseline, later)
    receipt_without_hash = {
        key: value for key, value in receipt.items() if key != "application_hash"
    }
    receipt["application_hash"] = release_tool.runtime_artifact_hash(
        receipt_without_hash
    )
    proof["memory_application_proof"]["application_hash"] = receipt[
        "application_hash"
    ]
    memory_event = retained["later-after-memory-run.json"]["events"][0]
    for key, value in receipt.items():
        memory_event[key] = deepcopy(value)
    proof["after"]["memory_application"] = deepcopy(receipt)
    proof["after"]["result_hash"] = release_tool.runtime_artifact_hash(later)

    with pytest.raises(
        release_tool.VerificationError,
        match=r"learning\.pure_replay",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_rejects_self_consistent_learned_evidence_topology() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    later = retained["later-after-memory-run.json"]["result"]
    ventilation = next(
        node
        for node in later["process"]["nodes"]
        if node["node_id"] == "ventilation_dispute"
    )
    ventilation["evidence_requirement_ids"] = ["use_evidence"]
    management = next(
        item
        for item in later["checklist"]["items"]
        if item["item_id"] == "management_position"
    )
    management["node_ids"] = ["dispute"]
    management["node_id"] = "dispute"
    management["current_path"] = True

    with pytest.raises(
        release_tool.VerificationError,
        match=r"learning\.later\.checklist\.items\[",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_rejects_forged_specialist_hash() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    _result, audit = _runtime_result_and_audit(retained)
    agent = next(
        item
        for item in audit["agents"]
        if item["agent_id"] == "document_source_integrity"
    )
    agent["output_artifact_hash"] = "f" * 64

    with pytest.raises(
        release_tool.VerificationError,
        match=r"audit\.agents\.document_source_integrity\.output_artifact_hash",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_rejects_forged_specialist_artifact() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    _result, audit = _runtime_result_and_audit(retained)
    private_sentinel = "private-forged-artifact-value"
    audit["specialist_artifacts"]["orchestrator_plan"][
        "contribution_type"
    ] = private_sentinel

    with pytest.raises(release_tool.VerificationError) as caught:
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )
    assert "audit.agents.orchestrator_plan.output_artifact_hash" in str(caught.value)
    assert private_sentinel not in str(caught.value)


def test_dynamic_runtime_acceptance_rejects_forged_canonical_fact() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, _audit = _runtime_result_and_audit(retained)
    private_sentinel = "private-forged-canonical-value"
    result["facts"][-1]["value"] = private_sentinel

    with pytest.raises(release_tool.VerificationError) as caught:
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )
    assert "audit.agents.canonical_facts.output_artifact_hash" in str(caught.value)
    assert private_sentinel not in str(caught.value)


def test_dynamic_runtime_acceptance_rejects_forged_orchestrator_unit() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    _result, audit = _runtime_result_and_audit(retained)
    plan = audit["specialist_artifacts"]["orchestrator_plan"]
    plan["deterministic_coverage"]["fact_ids"] = []
    _refresh_causal_artifact_hashes(retained)

    with pytest.raises(
        release_tool.VerificationError,
        match=r"orchestrator_plan\.focus_fact_ids",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_rejects_unbound_plan_source_handoff() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    _result, audit = _runtime_result_and_audit(retained)
    plan = audit["specialist_artifacts"]["orchestrator_plan"]
    forged_ref = "src_eeeeeeeeeeeeeeeeeeeeeeee"
    plan["focus_source_ref_ids"][1] = forged_ref
    plan["deterministic_coverage"]["source_ref_ids"][1] = forged_ref
    _refresh_causal_artifact_hashes(retained)

    with pytest.raises(
        release_tool.VerificationError,
        match=r"orchestrator_plan\.focus_source_ref_ids",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_rejects_forged_process_gate_input() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    _result, audit = _runtime_result_and_audit(retained)
    process_gate = next(
        item
        for item in audit["deterministic_gates"]
        if item["agent_id"] == "deterministic_process_gate"
    )
    process_gate["input_artifact_hash"] = "f" * 64

    with pytest.raises(
        release_tool.VerificationError,
        match=r"deterministic_process_gate\.input_artifact_hash",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_rejects_forged_inherited_process_field() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    _result, audit = _runtime_result_and_audit(retained)
    private_sentinel = "private-forged-process-state"
    audit["specialist_artifacts"]["process_decision_mapping"]["decisions"][0][
        "state"
    ] = private_sentinel
    _refresh_causal_artifact_hashes(retained)

    with pytest.raises(release_tool.VerificationError) as caught:
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )
    assert "process_decision_mapping.decisions[].state" in str(caught.value)
    assert private_sentinel not in str(caught.value)


def test_dynamic_runtime_acceptance_rejects_forged_evidence_fact_binding() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, _audit = _runtime_result_and_audit(retained)
    item = next(
        value
        for value in result["checklist"]["items"]
        if value["item_id"] == "management_position"
    )
    item["fact_id"] = "fact_cause"
    _refresh_causal_artifact_hashes(retained)

    with pytest.raises(
        release_tool.VerificationError,
        match=r"result\.fact_relationships",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_rejects_forged_evidence_source_ref() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    _result, audit = _runtime_result_and_audit(retained)
    evidence_item = next(
        item
        for item in audit["specialist_artifacts"]["evidence_checklist"]["items"]
        if item["item_id"] == "technical_assessment"
    )
    evidence_item["source_ref_ids"] = ["src_ffffffffffffffffffffffff"]
    _refresh_causal_artifact_hashes(retained)

    with pytest.raises(
        release_tool.VerificationError,
        match=r"final_claim_brief_audit\.source_ref_ids",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("current_node_id", "scope"),
        ("next_action_node_id", "scope"),
        ("supporting_fact_ids", ["fact_cause"]),
        (
            "upstream_contribution_ids",
            ["document_source_integrity", "process_decision_mapping"],
        ),
        (
            "audit_check_ids",
            [
                "current_node_supported_by_canonical_facts",
                "next_action_connected_in_static_topology",
            ],
        ),
    ],
)
def test_dynamic_runtime_acceptance_rejects_forged_final_field(
    field: str,
    forged_value: object,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    _result, audit = _runtime_result_and_audit(retained)
    audit["specialist_artifacts"]["final_claim_brief_audit"][field] = forged_value
    _refresh_causal_artifact_hashes(retained)

    with pytest.raises(
        release_tool.VerificationError,
        match=rf"final_claim_brief_audit\.{field}",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_rejects_forged_field_unit() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    _result, audit = _runtime_result_and_audit(retained)
    field = audit["specialist_artifacts"]["evidence_checklist"]["items"][0][
        "field_contributions"
    ][0]
    field["contribution_id"] = "item:claim_message:forged"
    _refresh_causal_artifact_hashes(retained)

    with pytest.raises(
        release_tool.VerificationError,
        match=r"evidence_checklist\.items\[0\]\.field_contributions\[0\]",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_rejects_forged_projection_lineage() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, audit = _runtime_result_and_audit(retained)
    private_sentinel = "private-forged-lineage-call"
    result["process"]["agent_contribution"]["provenance"][
        "call_id"
    ] = private_sentinel
    process_gate = next(
        item
        for item in audit["deterministic_gates"]
        if item["agent_id"] == "deterministic_process_gate"
    )
    process_gate["output_artifact_hash"] = release_tool.accepted_artifact_hash(
        result["process"]
    )

    with pytest.raises(release_tool.VerificationError) as caught:
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )
    assert "result.process.agent_contribution.provenance" in str(caught.value)
    assert private_sentinel not in str(caught.value)


def test_dynamic_runtime_acceptance_rejects_unbound_final_next_action() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    result, _audit = _runtime_result_and_audit(retained)
    result["next_action"]["process_node_id"] = "scope"

    with pytest.raises(
        release_tool.VerificationError,
        match=r"result\.next_action\.process_node_id",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


@pytest.mark.parametrize(
    ("actor", "expected_path"),
    [
        ("agent", "Dynamic flagship agent orchestrator_plan role"),
        ("gate", r"Dynamic flagship gate deterministic_process_gate\.role"),
    ],
)
def test_dynamic_runtime_acceptance_rejects_relabelled_runtime_roles(
    actor: str,
    expected_path: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    _result, audit = _runtime_result_and_audit(retained)
    if actor == "agent":
        target = next(
            item
            for item in audit["agents"]
            if item["agent_id"] == "orchestrator_plan"
        )
    else:
        target = next(
            item
            for item in audit["deterministic_gates"]
            if item["agent_id"] == "deterministic_process_gate"
        )
    target["role"] = "Relabelled Runtime Actor"

    with pytest.raises(release_tool.VerificationError, match=expected_path):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def _append_realistic_warm_ledger_item(retained: dict) -> dict:
    ledger = retained["flagship-cold-model-ledger.json"]
    cold_item = ledger["items"][0]
    warm_item = {
        "call_id": "modelcall_isolation_cache_replay_01",
        "provider": "openrouter",
        "provider_endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "upstream_provider": cold_item["upstream_provider"],
        "model": release_tool.REQUIRED_PRODUCTION_MODEL,
        "implementation": "model_backed_openrouter_canonicalizer",
        "orchestration_id": "orch_isolation_cache_replay",
        "agent_id": "canonical_facts",
        "agent_role": "Guarded Canonical Facts Agent",
        "parent_call_id": None,
        "delegation_id": None,
        "call_count": 0,
        "estimated_cost_usd": 0,
        "latency_ms": 1.25,
        "cache_key": "cache_isolation_canonical_facts",
        "purpose": "isolated cache replay",
        "outcome": "cache_hit",
        "authority_mode": "hybrid_guarded",
        "accepted_fact_ids": ["fact_safe_identifier"],
        "accepted_fact_count": 1,
        "rejected_facts": [],
        "rejected_fact_count": 0,
        "ignored_noncontrolling_normalized_proposals": 0,
        "deterministic_fallback_applied": False,
        "response_id": cold_item["response_id"],
        "origin_call_id": cold_item["call_id"],
        "origin_usage": {
            "prompt_tokens": cold_item["prompt_tokens"],
            "completion_tokens": cold_item["completion_tokens"],
            "total_tokens": cold_item["total_tokens"],
            "actual_cost_usd": cold_item["actual_cost_usd"],
            "usage_source": cold_item["usage_source"],
        },
        "origin_finish_reason": cold_item["finish_reason"],
        "response_model": cold_item["response_model"],
        "usage_source": "cache",
        "finish_reason": cold_item["finish_reason"],
        "created_at": "2026-08-11T00:00:00Z",
        "updated_at": "2026-08-11T00:00:01Z",
    }
    ledger["items"].append(warm_item)
    ledger["summary"] = _ledger_summary(ledger["items"])
    return warm_item


def test_public_ledger_accepts_warm_shape_but_cold_artifact_rejects_it() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    _append_realistic_warm_ledger_item(retained)
    release_tool._verify_public_model_ledger(
        retained["flagship-cold-model-ledger.json"],
        "fixture",
    )

    with pytest.raises(
        release_tool.VerificationError,
        match="exact cold six",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_rejects_forbidden_retained_run_field() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    unsafe_value = "private provider narrative must not be retained"
    retained["flagship-run.json"]["reasoning"] = unsafe_value

    with pytest.raises(
        release_tool.VerificationError,
        match=r"forbidden public field at \$\.flagship_run\.reasoning",
    ) as caught:
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )
    assert unsafe_value not in str(caught.value)


def test_dynamic_runtime_acceptance_rejects_non_allowlisted_ledger_field() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    unsafe_value = "private provider trace must not be retained"
    retained["flagship-cold-model-ledger.json"]["items"][0][
        "provider_trace_excerpt"
    ] = unsafe_value

    with pytest.raises(
        release_tool.VerificationError,
        match=r"items\[0\]\.provider_trace_excerpt",
    ) as caught:
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )
    assert unsafe_value not in str(caught.value)


def test_dynamic_runtime_acceptance_rejects_nonexact_origin_usage_schema() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    warm_item = _append_realistic_warm_ledger_item(retained)
    warm_item["origin_usage"]["provider_trace_excerpt"] = "not retained"

    with pytest.raises(
        release_tool.VerificationError,
        match=r"items\[6\]\.origin_usage violates the exact origin-usage schema",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("response_id", "r" * 160),
        ("response_model", release_tool.REQUIRED_PRODUCTION_MODEL),
        (
            "response_model",
            "nvidia/nemotron-3-ultra-550b-a55b-20260604",
        ),
        ("upstream_provider", "P" * 80),
        ("finish_reason", "tool_calls"),
    ],
)
def test_successful_provider_provenance_accepts_exact_bounded_values(
    field: str,
    value: str,
) -> None:
    assert release_tool._provider_provenance_value_is_safe(field, value)


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    [
        ("response_id", "sk" + "-or-unit-test-placeholder"),
        ("response_id", "api_key_unit_test_placeholder"),
        ("response_id", "tenant-moisture-claim-42"),
        ("response_id", "r" * 161),
        ("upstream_provider", "landlord-claim"),
        ("upstream_provider", "P" * 81),
        ("finish_reason", "tenant stopped payment"),
        ("response_model", "nvidia/another-model"),
    ],
)
def test_dynamic_runtime_acceptance_rejects_unsafe_successful_provenance(
    field: str,
    unsafe_value: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    agent = retained["flagship-run.json"]["result"]["audit"]["agent_orchestration"][
        "agents"
    ][0]
    ledger_item = retained["flagship-cold-model-ledger.json"]["items"][0]
    agent[field] = unsafe_value
    ledger_item[field] = unsafe_value

    with pytest.raises(
        release_tool.VerificationError,
        match=rf"{field} violates the provider-provenance sanitizer",
    ) as caught:
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )
    assert unsafe_value not in str(caught.value)


def test_dynamic_runtime_acceptance_rejects_unsafe_ledger_only_provenance() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    unsafe_value = "credential-provider-unit-test"
    retained["flagship-cold-model-ledger.json"]["items"][0]["upstream_provider"] = (
        unsafe_value
    )

    with pytest.raises(
        release_tool.VerificationError,
        match="upstream_provider violates the provider-provenance sanitizer",
    ) as caught:
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )
    assert unsafe_value not in str(caught.value)


def test_dynamic_runtime_acceptance_rejects_valid_but_unpinned_upstream() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    audit_agent = retained["flagship-run.json"]["result"]["audit"][
        "agent_orchestration"
    ]["agents"][0]
    audit_agent["upstream_provider"] = "DeepInfra"

    with pytest.raises(
        release_tool.VerificationError,
        match="upstream_provider must be 'Together'",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_public_ledger_accepts_bounded_unknown_cost_upstream_rejection() -> None:
    ledger = {
        "scope": "global_budget_ledger",
        "summary": {
            "records": 1,
            "network_calls": 1,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "actual_cost_usd": 0,
            "actual_cost_complete": False,
            "unknown_cost_call_count": 1,
            "outcomes": {"failed": 1},
        },
        "items": [
            {
                "call_id": "modelcall-upstream-rejected",
                "orchestration_id": "orch_upstream_rejected",
                "agent_id": "canonical_facts",
                "provider": "openrouter",
                "provider_endpoint": "https://openrouter.ai/api/v1/chat/completions",
                "model": "nvidia/nemotron-3-ultra-550b-a55b",
                "call_count": 1,
                "outcome": "failed",
                "error_type": "OpenRouterUpstreamRejectionError",
                "error_invariant": "provider_upstream_rejection",
                "response_id": "gen-1786483159-hyYthqPv76o6PHXpGLzl",
                "provider_error_code": 429,
                "provider_boundary": "openrouter",
                "expected_upstream_provider": "Together",
                "latency_ms": 2777.996,
                "actual_cost_usd": None,
                "created_at": "2026-08-12T00:49:55.141493+00:00",
                "updated_at": "2026-08-12T00:49:57.927268+00:00",
            }
        ],
    }

    release_tool._verify_public_model_ledger(ledger, "fixture")
    boolean_forged = deepcopy(ledger)
    boolean_forged["summary"] = {
        "records": True,
        "network_calls": True,
        "prompt_tokens": False,
        "completion_tokens": False,
        "total_tokens": False,
        "actual_cost_usd": False,
        "actual_cost_complete": False,
        "unknown_cost_call_count": True,
        "outcomes": {"failed": True},
    }
    with pytest.raises(
        release_tool.VerificationError,
        match="summary has invalid",
    ):
        release_tool._verify_public_model_ledger(boolean_forged, "fixture")

    ledger["items"][0]["provider_error_code"] = "RAW_PROVIDER_CODE"
    with pytest.raises(
        release_tool.VerificationError,
        match="provider_error_code is unbounded or out of scope",
    ):
        release_tool._verify_public_model_ledger(ledger, "fixture")

    ledger["items"][0]["provider_error_code"] = 429
    unsafe_response_id = "DEF-027-E0-DEMO"
    ledger["items"][0]["response_id"] = unsafe_response_id
    with pytest.raises(
        release_tool.VerificationError,
        match="exact OpenRouter generation ID",
    ) as caught:
        release_tool._verify_public_model_ledger(ledger, "fixture")
    assert unsafe_response_id not in str(caught.value)

    ledger["items"][0]["response_id"] = "gen-1786483159-hyYthqPv76o6PHXpGLzl"
    for missing_field in ("provider_boundary", "expected_upstream_provider"):
        missing_pair = deepcopy(ledger)
        missing_pair["items"][0].pop(missing_field)
        with pytest.raises(
            release_tool.VerificationError,
            match="provider_boundary pair is invalid or out of scope",
        ):
            release_tool._verify_public_model_ledger(missing_pair, "fixture")

    for field, forged_value in (
        ("provider_boundary", "provider-router"),
        ("expected_upstream_provider", "provider-unit-test"),
    ):
        forged_pair = deepcopy(ledger)
        forged_pair["items"][0][field] = forged_value
        with pytest.raises(
            release_tool.VerificationError,
            match="provider_boundary pair is invalid or out of scope",
        ) as caught:
            release_tool._verify_public_model_ledger(forged_pair, "fixture")
        assert forged_value not in str(caught.value)

    out_of_scope_pair = deepcopy(ledger)
    out_of_scope_pair["items"][0]["error_invariant"] = "provider_invocation"
    out_of_scope_pair["items"][0].pop("provider_error_code")
    with pytest.raises(
        release_tool.VerificationError,
        match="provider_boundary pair is invalid or out of scope",
    ):
        release_tool._verify_public_model_ledger(out_of_scope_pair, "fixture")

    absent_pair = deepcopy(ledger)
    absent_pair["items"][0].pop("provider_boundary")
    absent_pair["items"][0].pop("expected_upstream_provider")
    with pytest.raises(
        release_tool.VerificationError,
        match="provider_boundary pair is invalid or out of scope",
    ):
        release_tool._verify_public_model_ledger(absent_pair, "fixture")


def test_public_ledger_rejects_every_forged_summary_field() -> None:
    ledger = {
        "scope": "global_budget_ledger",
        "items": [
            {
                "call_id": "modelcall-summary-known",
                "call_count": 1,
                "prompt_tokens": 17,
                "completion_tokens": 5,
                "total_tokens": 22,
                "actual_cost_usd": 0.0042,
                "outcome": "succeeded",
            },
            {
                "call_id": "modelcall-summary-unknown",
                "call_count": 1,
                "actual_cost_usd": None,
                "outcome": "failed",
            },
            {
                "call_id": "modelcall-summary-cache",
                "call_count": 0,
                "outcome": "cache_hit",
            },
        ],
    }
    ledger["summary"] = _ledger_summary(ledger["items"])
    release_tool._verify_public_model_ledger(ledger, "fixture")

    forged_values = {
        "records": 999,
        "network_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "actual_cost_usd": 0,
        "actual_cost_complete": True,
        "unknown_cost_call_count": 0,
        "outcomes": {},
    }
    for field, forged_value in forged_values.items():
        forged = deepcopy(ledger)
        forged["summary"][field] = forged_value
        with pytest.raises(
            release_tool.VerificationError,
            match="summary is inconsistent with ledger rows",
        ):
            release_tool._verify_public_model_ledger(forged, "fixture")


def _fixture_evidence_payload(
    filename: str,
    retained: dict[str, dict],
    *,
    label: str,
) -> bytes:
    if filename in retained:
        return f"{json.dumps(retained[filename], indent=2)}\n".encode()
    if filename.endswith(".png"):
        return b"\x89PNG\r\n\x1a\n" + f"{label}: {filename}\n".encode()
    if filename.endswith(".webm"):
        return b"\x1aE\xdf\xa3" + f"{label}: {filename}\n".encode()
    return f"{label}: {filename}\n".encode()


def _write_fixture_evidence_pair(
    tmp_path: Path,
    report: dict,
    manifest: dict,
    retained: dict[str, dict],
    *,
    inventory: set[str] | frozenset[str],
    payload_overrides: dict[str, bytes] | None = None,
) -> tuple[Path, Path]:
    overrides = payload_overrides or {}
    records = []
    for filename in sorted(inventory):
        payload = overrides.get(
            filename,
            _fixture_evidence_payload(
                filename,
                retained,
                label="retained fixture evidence",
            ),
        )
        (tmp_path / filename).write_bytes(payload)
        records.append(
            {
                "path": filename,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
        )
    manifest["files"] = records
    report["evidence"]["files"] = records
    manifest_bytes = f"{json.dumps(manifest, indent=2)}\n".encode()
    manifest_path = tmp_path / "evidence-manifest.json"
    manifest_path.write_bytes(manifest_bytes)
    report["evidence"]["manifest"] = {
        "path": "evidence-manifest.json",
        "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "bytes": len(manifest_bytes),
    }
    report_path = tmp_path / "report.json"
    report_path.write_text(
        f"{json.dumps(report, indent=2)}\n",
        encoding="utf-8",
    )
    return report_path, manifest_path


def test_dynamic_runtime_evidence_paths_verify_the_atomic_artifact_pair(
    tmp_path: Path,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, _ = successful_dynamic_qa_evidence(contract)
    records = []
    for filename in sorted(release_tool.REQUIRED_QA_EVIDENCE_FILES):
        payload = _fixture_evidence_payload(
            filename,
            retained,
            label="retained evidence",
        )
        (tmp_path / filename).write_bytes(payload)
        records.append(
            {
                "path": filename,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
        )
    manifest["files"] = records
    report["evidence"]["files"] = records
    manifest_bytes = f"{json.dumps(manifest, indent=2)}\n".encode()
    (tmp_path / "evidence-manifest.json").write_bytes(manifest_bytes)
    report["evidence"]["manifest"] = {
        "path": "evidence-manifest.json",
        "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "bytes": len(manifest_bytes),
    }
    (tmp_path / "report.json").write_text(
        f"{json.dumps(report, indent=2)}\n",
        encoding="utf-8",
    )

    result = release_tool.verify_dynamic_runtime_acceptance_paths(
        tmp_path / "report.json",
        tmp_path / "evidence-manifest.json",
    )
    assert result["status"] == "passed"
    assert result["source_commit"] == "a" * 40


def test_dynamic_causal_evidence_paths_verify_exact_preflight_inventory(
    tmp_path: Path,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, _ = successful_dynamic_qa_evidence(contract)
    records = []
    for filename in sorted(release_tool.REQUIRED_CAUSAL_QA_EVIDENCE_FILES):
        payload = _fixture_evidence_payload(
            filename,
            retained,
            label="deterministic retained evidence",
        )
        (tmp_path / filename).write_bytes(payload)
        records.append(
            {
                "path": filename,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
        )
    manifest["files"] = records
    manifest["retained_media_contract"] = {
        "json": list(release_tool.REQUIRED_CAUSAL_QA_RETAINED_JSON_EVIDENCE_FILES),
        "screenshots": list(
            release_tool.REQUIRED_CAUSAL_QA_RETAINED_SCREENSHOT_EVIDENCE_FILES
        ),
        "video": release_tool.REQUIRED_QA_VIDEO_EVIDENCE_FILE,
        "missing": [],
        "empty": [],
    }
    report["evidence"]["files"] = records
    manifest_bytes = f"{json.dumps(manifest, indent=2)}\n".encode()
    (tmp_path / "evidence-manifest.json").write_bytes(manifest_bytes)
    report["evidence"]["manifest"] = {
        "path": "evidence-manifest.json",
        "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "bytes": len(manifest_bytes),
    }
    (tmp_path / "report.json").write_text(
        f"{json.dumps(report, indent=2)}\n",
        encoding="utf-8",
    )

    result = release_tool.verify_dynamic_causal_evidence_paths(
        tmp_path / "report.json",
        tmp_path / "evidence-manifest.json",
    )
    assert result == {
        "release_id": contract["release_id"],
        "status": "passed",
        "verdict_source": "deterministic_retained_causal_preflight",
    }


@pytest.mark.parametrize("forgery", ["duplicate", "zero_bytes"])
def test_dynamic_causal_evidence_paths_reject_invalid_file_records(
    tmp_path: Path,
    forgery: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, _ = successful_dynamic_qa_evidence(contract)
    records = []
    for filename in sorted(release_tool.REQUIRED_CAUSAL_QA_EVIDENCE_FILES):
        payload = _fixture_evidence_payload(
            filename,
            retained,
            label="deterministic retained evidence",
        )
        (tmp_path / filename).write_bytes(payload)
        records.append(
            {
                "path": filename,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
        )
    if forgery == "duplicate":
        records.append(deepcopy(records[0]))
    else:
        records[0]["bytes"] = 0
    manifest["files"] = records
    manifest["retained_media_contract"] = {
        "json": list(release_tool.REQUIRED_CAUSAL_QA_RETAINED_JSON_EVIDENCE_FILES),
        "screenshots": list(
            release_tool.REQUIRED_CAUSAL_QA_RETAINED_SCREENSHOT_EVIDENCE_FILES
        ),
        "video": release_tool.REQUIRED_QA_VIDEO_EVIDENCE_FILE,
        "missing": [],
        "empty": [],
    }
    report["evidence"]["files"] = records
    manifest_bytes = f"{json.dumps(manifest, indent=2)}\n".encode()
    (tmp_path / "evidence-manifest.json").write_bytes(manifest_bytes)
    report["evidence"]["manifest"] = {
        "path": "evidence-manifest.json",
        "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "bytes": len(manifest_bytes),
    }
    (tmp_path / "report.json").write_text(
        f"{json.dumps(report, indent=2)}\n",
        encoding="utf-8",
    )

    expected = (
        "Duplicate dynamic QA evidence path"
        if forgery == "duplicate"
        else "file record is invalid"
    )
    with pytest.raises(release_tool.VerificationError, match=expected):
        release_tool.verify_dynamic_causal_evidence_paths(
            tmp_path / "report.json",
            tmp_path / "evidence-manifest.json",
        )


def test_successful_dynamic_evidence_fixture_matches_production_bundle_shape() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, _ = successful_dynamic_qa_evidence(contract)

    assert set(retained) == set(release_tool.REQUIRED_QA_JSON_EVIDENCE_FILES)
    assert len(manifest["files"]) == 30
    assert report["runIds"] == ["flagship-run", "baseline-run", "later-run"]
    assert report["passed"] == len(report["checks"]) == 218
    assert report["failed"] == 0
    assert report["failures"] == {
        "console": [],
        "page": [],
        "request": [],
        "cleanup": [],
    }
    cold = retained["flagship-cold-model-ledger.json"]
    isolation = retained["isolation-model-ledger.json"]
    final = retained["model-ledger.json"]
    assert cold["summary"]["records"] == 6
    assert cold["summary"]["network_calls"] == 6
    assert isolation["summary"]["records"] == 12
    assert isolation["summary"]["network_calls"] == 6
    assert isolation["summary"]["outcomes"]["cache_hit"] == 6
    assert final == isolation
    assert final["summary"]["records"] == 12
    assert final["summary"]["network_calls"] == 6
    assert final["summary"]["outcomes"]["cache_hit"] == 6
    assert final["summary"]["actual_cost_complete"] is True
    for filename, knowledge_mode in (
        ("later-baseline-run.json", "baseline"),
        ("later-after-memory-run.json", "current"),
    ):
        run = retained[filename]
        assert run["knowledge_mode"] == knowledge_mode
        assert run["model_mode"] == release_tool.DETERMINISTIC_REFERENCE_MODE
        assert run["model"] is None
        assert run["agent_orchestration"]["executed"] is False
        assert run["result"]["audit"]["canonicalization"] == {
            "implementation": "deterministic_reference_oracle",
            "model": None,
            "provider": None,
            "mode": release_tool.DETERMINISTIC_REFERENCE_MODE,
        }


def test_dynamic_runtime_evidence_paths_reject_extra_manifest_file(
    tmp_path: Path,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, _ = successful_dynamic_qa_evidence(contract)
    inventory = set(release_tool.REQUIRED_QA_EVIDENCE_FILES)
    inventory.add("unexpected-retained-artifact.txt")
    report_path, manifest_path = _write_fixture_evidence_pair(
        tmp_path,
        report,
        manifest,
        retained,
        inventory=inventory,
    )

    with pytest.raises(
        release_tool.VerificationError,
        match="manifest inventory is not exact",
    ):
        release_tool.verify_dynamic_runtime_acceptance_paths(
            report_path,
            manifest_path,
        )


@pytest.mark.parametrize(
    "filename",
    release_tool.REQUIRED_QA_JSON_EVIDENCE_FILES,
)
def test_dynamic_runtime_evidence_paths_reject_empty_required_json_object(
    tmp_path: Path,
    filename: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, _ = successful_dynamic_qa_evidence(contract)
    report_path, manifest_path = _write_fixture_evidence_pair(
        tmp_path,
        report,
        manifest,
        retained,
        inventory=release_tool.REQUIRED_QA_EVIDENCE_FILES,
        payload_overrides={filename: b"{}\n"},
    )

    with pytest.raises(release_tool.VerificationError):
        release_tool.verify_dynamic_runtime_acceptance_paths(
            report_path,
            manifest_path,
        )


def test_dynamic_runtime_evidence_paths_reject_malformed_required_json(
    tmp_path: Path,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, _ = successful_dynamic_qa_evidence(contract)
    report_path, manifest_path = _write_fixture_evidence_pair(
        tmp_path,
        report,
        manifest,
        retained,
        inventory=release_tool.REQUIRED_QA_EVIDENCE_FILES,
        payload_overrides={"deployment-identity.json": b"{malformed"},
    )

    with pytest.raises(
        release_tool.VerificationError,
        match="Cannot read retained deployment-identity.json",
    ):
        release_tool.verify_dynamic_runtime_acceptance_paths(
            report_path,
            manifest_path,
        )


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("01-start-desktop.png", "is not PNG"),
        ("uninterrupted-focused-demo.webm", "video is not WebM"),
    ],
)
def test_dynamic_runtime_evidence_paths_reject_wrong_media_magic(
    tmp_path: Path,
    filename: str,
    expected: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, _ = successful_dynamic_qa_evidence(contract)
    report_path, manifest_path = _write_fixture_evidence_pair(
        tmp_path,
        report,
        manifest,
        retained,
        inventory=release_tool.REQUIRED_QA_EVIDENCE_FILES,
        payload_overrides={filename: b"not-the-declared-media-format\n"},
    )

    with pytest.raises(release_tool.VerificationError, match=expected):
        release_tool.verify_dynamic_runtime_acceptance_paths(
            report_path,
            manifest_path,
        )


def test_dynamic_runtime_acceptance_rejects_extra_flagship_cold_row() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    cold_ledger = retained["flagship-cold-model-ledger.json"]
    extra = deepcopy(cold_ledger["items"][-1])
    extra.update(
        {
            "call_id": "modelcall_unbound_extra_cold",
            "orchestration_id": "orch_unbound_extra_cold",
            "response_id": "generation_unbound_extra_cold",
        }
    )
    cold_ledger["items"].append(extra)
    cold_ledger["summary"] = _ledger_summary(cold_ledger["items"])

    with pytest.raises(release_tool.VerificationError):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


@pytest.mark.parametrize(
    "permuted_surfaces",
    [
        ("ledger",),
        ("audit", "lineage"),
        ("audit", "ledger", "lineage"),
    ],
)
def test_dynamic_runtime_acceptance_allows_parallel_warm_completion_order_swap(
    permuted_surfaces: tuple[str, ...],
) -> None:
    """A valid cache replay may finish the two independent fan-out agents either way."""

    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    warm_run = retained["isolation-run.json"]
    if "audit" in permuted_surfaces:
        _swap_parallel_agent_records(warm_run["agent_orchestration"]["agents"])
    if "ledger" in permuted_surfaces:
        for ledger_name in (
            "isolation-model-ledger.json",
            "model-ledger.json",
        ):
            warm_items = retained[ledger_name]["items"][6:]
            _swap_parallel_agent_records(warm_items)
            retained[ledger_name]["items"][6:] = warm_items
    if "lineage" in permuted_surfaces:
        _swap_parallel_agent_records(
            retained["flagship-cache-lineage.json"]["lineage"]
        )

    release_tool.verify_dynamic_runtime_acceptance(
        contract,
        report,
        manifest,
        retained,
        evidence_manifest_bytes=manifest_bytes,
    )


@pytest.mark.parametrize(
    "surface",
    ["cold_audit", "warm_audit", "cold_ledger", "warm_ledger", "cache_lineage"],
)
def test_dynamic_runtime_acceptance_rejects_non_topological_agent_order(
    surface: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    collections = {
        "cold_audit": retained["flagship-run.json"]["agent_orchestration"]["agents"],
        "warm_audit": retained["isolation-run.json"]["agent_orchestration"]["agents"],
        "cold_ledger": retained["flagship-cold-model-ledger.json"]["items"],
        "warm_ledger": retained["isolation-model-ledger.json"]["items"][6:],
        "cache_lineage": retained["flagship-cache-lineage.json"]["lineage"],
    }
    collections[surface].reverse()

    if surface == "cache_lineage":
        with pytest.raises(
            release_tool.VerificationError,
            match="cache-lineage receipt",
        ):
            release_tool.verify_dynamic_runtime_acceptance(
                contract,
                report,
                manifest,
                retained,
                evidence_manifest_bytes=manifest_bytes,
            )
    else:
        with pytest.raises(
            release_tool.VerificationError,
            match="violates the execution topology",
        ):
            release_tool._verify_cold_warm_model_pair(
                cold_run=retained["flagship-run.json"],
                warm_run=retained["isolation-run.json"],
                cold_items=(
                    collections["cold_ledger"]
                    if surface == "cold_ledger"
                    else retained["flagship-cold-model-ledger.json"]["items"]
                ),
                warm_items=(
                    collections["warm_ledger"]
                    if surface == "warm_ledger"
                    else retained["isolation-model-ledger.json"]["items"][6:]
                ),
                label="Adversarial cache pair",
            )


@pytest.mark.parametrize("surface", ["warm_audit", "warm_ledger", "cache_lineage"])
@pytest.mark.parametrize("mutation", ["duplicate", "missing", "foreign"])
def test_dynamic_runtime_acceptance_rejects_non_exact_warm_agent_membership(
    surface: str,
    mutation: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    warm_run = retained["isolation-run.json"]
    collections = {
        "warm_audit": warm_run["agent_orchestration"]["agents"],
        "warm_ledger": retained["isolation-model-ledger.json"]["items"][6:],
        "cache_lineage": retained["flagship-cache-lineage.json"]["lineage"],
    }
    records = collections[surface]
    process_index = next(
        index
        for index, item in enumerate(records)
        if item["agent_id"] == "process_decision_mapping"
    )
    if mutation == "duplicate":
        records[process_index]["agent_id"] = "document_source_integrity"
    elif mutation == "missing":
        records.pop(process_index)
    else:
        records[process_index]["agent_id"] = "foreign_agent"

    if surface == "cache_lineage":
        with pytest.raises(
            release_tool.VerificationError,
            match="cache-lineage receipt",
        ):
            release_tool.verify_dynamic_runtime_acceptance(
                contract,
                report,
                manifest,
                retained,
                evidence_manifest_bytes=manifest_bytes,
            )
    else:
        with pytest.raises(
            release_tool.VerificationError,
            match=(
                rf"{surface.replace('_', ' ')} "
                r"(?:does not contain exactly six agents|agent membership is not exact)"
            ),
        ):
            release_tool._verify_cold_warm_model_pair(
                cold_run=retained["flagship-run.json"],
                warm_run=warm_run,
                cold_items=retained["flagship-cold-model-ledger.json"]["items"],
                warm_items=(
                    records
                    if surface == "warm_ledger"
                    else retained["isolation-model-ledger.json"]["items"][6:]
                ),
                label="Adversarial cache pair",
            )


@pytest.mark.parametrize("surface", ["audit_origin", "ledger_origin", "ledger_call"])
def test_cold_warm_pair_rejects_cross_agent_lineage_bindings(
    surface: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    _, _, retained, _ = successful_dynamic_qa_evidence(contract)
    cold_run = retained["flagship-run.json"]
    warm_run = retained["isolation-run.json"]
    cold_agents = {
        item["agent_id"]: item for item in cold_run["agent_orchestration"]["agents"]
    }
    warm_agents = {
        item["agent_id"]: item for item in warm_run["agent_orchestration"]["agents"]
    }
    warm_items = retained["isolation-model-ledger.json"]["items"][6:]
    warm_items_by_agent = {item["agent_id"]: item for item in warm_items}
    process_agent = warm_agents["process_decision_mapping"]
    process_item = warm_items_by_agent["process_decision_mapping"]
    if surface == "audit_origin":
        process_agent["origin_call_id"] = cold_agents[
            "document_source_integrity"
        ]["call_id"]
    elif surface == "ledger_origin":
        process_item["origin_call_id"] = cold_agents[
            "document_source_integrity"
        ]["call_id"]
    else:
        process_item["call_id"] = warm_agents[
            "document_source_integrity"
        ]["call_id"]

    with pytest.raises(
        release_tool.VerificationError,
        match=(
            r"process_decision_mapping warm "
            r"(?:agent lineage|ledger lineage) is invalid"
        ),
    ):
        release_tool._verify_cold_warm_model_pair(
            cold_run=cold_run,
            warm_run=warm_run,
            cold_items=retained["flagship-cold-model-ledger.json"]["items"],
            warm_items=warm_items,
            label="Adversarial cache pair",
        )


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("input_artifact_hash", "a" * 64),
        ("output_artifact_hash", "b" * 64),
        ("accepted_ids", ["forged_cached_acceptance"]),
    ],
)
def test_cold_warm_pair_rejects_changed_cached_artifact(
    field: str,
    forged_value: object,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    _, _, retained, _ = successful_dynamic_qa_evidence(contract)
    cold_run = retained["flagship-run.json"]
    warm_run = retained["isolation-run.json"]
    process_agent = next(
        item
        for item in warm_run["agent_orchestration"]["agents"]
        if item["agent_id"] == "process_decision_mapping"
    )
    process_agent[field] = forged_value

    with pytest.raises(
        release_tool.VerificationError,
        match=r"process_decision_mapping warm agent lineage is invalid",
    ):
        release_tool._verify_cold_warm_model_pair(
            cold_run=cold_run,
            warm_run=warm_run,
            cold_items=retained["flagship-cold-model-ledger.json"]["items"],
            warm_items=retained["isolation-model-ledger.json"]["items"][6:],
            label="Adversarial cache pair",
        )


def test_dynamic_runtime_acceptance_rejects_cache_lineage_tamper() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    retained["flagship-cache-lineage.json"]["lineage"][0][
        "warm_call_id"
    ] = "modelcall_forged_warm_lineage"

    with pytest.raises(release_tool.VerificationError, match="cache-lineage receipt"):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_rejects_thirteenth_final_ledger_row() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    final_ledger = retained["model-ledger.json"]
    extra = deepcopy(final_ledger["items"][-1])
    extra.update(
        {
            "call_id": "modelcall_forbidden_later_row",
            "orchestration_id": "orch_forbidden_later_activity",
        }
    )
    final_ledger["items"].append(extra)
    final_ledger["summary"] = _ledger_summary(final_ledger["items"])

    with pytest.raises(
        release_tool.VerificationError,
        match="exact immutable ordered 6/12/12 snapshots",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


@pytest.mark.parametrize(
    "activity",
    ["model_mode", "canonicalizer", "executed_dag", "model_event"],
)
def test_dynamic_runtime_acceptance_rejects_later_model_activity(
    activity: str,
) -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )
    run = retained["later-after-memory-run.json"]
    if activity == "model_mode":
        run["model_mode"] = release_tool.REQUIRED_PRODUCTION_MODE
        run["model"] = release_tool.REQUIRED_PRODUCTION_MODEL
    elif activity == "canonicalizer":
        run["result"]["audit"]["canonicalization"] = {
            "implementation": "model_backed_openrouter_canonicalizer",
            "model": release_tool.REQUIRED_PRODUCTION_MODEL,
            "provider": "openrouter",
            "mode": release_tool.REQUIRED_PRODUCTION_MODE,
        }
    elif activity == "executed_dag":
        forged = {
            **run["agent_orchestration"],
            "executed": True,
            "agents": [],
        }
        run["agent_orchestration"] = deepcopy(forged)
        run["result"]["agent_orchestration"] = deepcopy(forged)
        run["result"]["audit"]["agent_orchestration"] = deepcopy(forged)
    else:
        run["events"].append(
            {
                "stage": "agent_orchestration",
                "actor_type": "nemotron_agent",
                "status": "completed",
                "model": release_tool.REQUIRED_PRODUCTION_MODEL,
                "call_id": "modelcall_forbidden_later_event",
                "call_count": 1,
            }
        )

    with pytest.raises(
        release_tool.VerificationError,
        match="deterministic-reference comparison run|model execution activity",
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_dynamic_runtime_acceptance_requires_exact_retained_media_inventory() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, _ = successful_dynamic_qa_evidence(contract)

    assert len(release_tool.REQUIRED_QA_JSON_EVIDENCE_FILES) == 15
    assert len(release_tool.REQUIRED_QA_SCREENSHOT_EVIDENCE_FILES) == 14
    assert (
        "03-lease-pdf-search.png"
        in release_tool.REQUIRED_QA_SCREENSHOT_EVIDENCE_FILES
    )
    assert release_tool.REQUIRED_QA_EVIDENCE_FILES == frozenset(
        (
            *release_tool.REQUIRED_QA_JSON_EVIDENCE_FILES,
            *release_tool.REQUIRED_QA_SCREENSHOT_EVIDENCE_FILES,
            release_tool.REQUIRED_QA_VIDEO_EVIDENCE_FILE,
        )
    )

    invalid_contracts = (
        (
            {
                **manifest["retained_media_contract"],
                "json": list(release_tool.REQUIRED_QA_JSON_EVIDENCE_FILES[:-1]),
            },
            "retained JSON inventory is not exact",
        ),
        (
            {
                **manifest["retained_media_contract"],
                "screenshots": list(
                    release_tool.REQUIRED_QA_SCREENSHOT_EVIDENCE_FILES[:-1]
                ),
            },
            "retained screenshot inventory is not exact",
        ),
        (
            {
                **manifest["retained_media_contract"],
                "screenshots": list(
                    reversed(release_tool.REQUIRED_QA_SCREENSHOT_EVIDENCE_FILES)
                ),
            },
            "retained screenshot inventory is not exact",
        ),
        (
            {
                **manifest["retained_media_contract"],
                "video": "replacement.webm",
            },
            "retained video inventory is not exact",
        ),
        (
            {
                **manifest["retained_media_contract"],
                "unexpected": [],
            },
            "retained-media contract fields are not exact",
        ),
    )
    for retained_media_contract, message in invalid_contracts:
        invalid_manifest = deepcopy(manifest)
        invalid_manifest["retained_media_contract"] = retained_media_contract
        invalid_manifest_bytes = f"{json.dumps(invalid_manifest, indent=2)}\n".encode()
        invalid_report = deepcopy(report)
        invalid_report["evidence"]["manifest"] = {
            "path": "evidence-manifest.json",
            "sha256": hashlib.sha256(invalid_manifest_bytes).hexdigest(),
            "bytes": len(invalid_manifest_bytes),
        }
        with pytest.raises(release_tool.VerificationError, match=message):
            release_tool.verify_dynamic_runtime_acceptance(
                contract,
                invalid_report,
                invalid_manifest,
                retained,
                evidence_manifest_bytes=invalid_manifest_bytes,
            )


def test_dynamic_runtime_acceptance_rejects_weak_or_unbound_proof() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    report, manifest, retained, manifest_bytes = successful_dynamic_qa_evidence(
        contract
    )

    misaligned = deepcopy(report)
    misaligned["deployment"]["api"]["source_commit"] = "d" * 40
    with pytest.raises(release_tool.VerificationError, match="commits are not aligned"):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            misaligned,
            manifest,
            retained,
            evidence_manifest_bytes=manifest_bytes,
        )

    duplicate_response = deepcopy(retained)
    agents = duplicate_response["flagship-run.json"]["result"]["audit"][
        "agent_orchestration"
    ]["agents"]
    agents[1]["response_id"] = agents[0]["response_id"]
    with pytest.raises(
        release_tool.VerificationError, match="response IDs must be distinct"
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            duplicate_response,
            evidence_manifest_bytes=manifest_bytes,
        )

    weak_contribution = deepcopy(retained)
    agent = weak_contribution["flagship-run.json"]["result"]["audit"][
        "agent_orchestration"
    ]["agents"][3]
    agent.update(
        {
            "accepted_count": 1,
            "rejected_count": 1,
            "deterministic_fallback_applied": True,
        }
    )
    with pytest.raises(
        release_tool.VerificationError, match="strict accepted majority"
    ):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            weak_contribution,
            evidence_manifest_bytes=manifest_bytes,
        )

    traced = deepcopy(retained)
    traced["flagship-run.json"]["result"]["audit"]["agent_orchestration"][
        "external_tracing"
    ] = True
    with pytest.raises(release_tool.VerificationError, match="external_tracing"):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            traced,
            evidence_manifest_bytes=manifest_bytes,
        )

    forged_hash = deepcopy(retained)
    forged_gates = forged_hash["flagship-run.json"]["result"]["audit"][
        "agent_orchestration"
    ]["deterministic_gates"]
    forged_gates[0]["output_artifact_hash"] = "f" * 64
    with pytest.raises(release_tool.VerificationError, match="output_artifact_hash"):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            forged_hash,
            evidence_manifest_bytes=manifest_bytes,
        )

    missing_dto = deepcopy(retained)
    del missing_dto["flagship-run.json"]["result"]["checklist"]
    with pytest.raises(release_tool.VerificationError, match="accepted DTO is missing"):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            missing_dto,
            evidence_manifest_bytes=manifest_bytes,
        )

    forged_topology = deepcopy(retained)
    topology = forged_topology["flagship-run.json"]["result"]["audit"][
        "agent_orchestration"
    ]["execution_topology"]
    topology["delegations"][0]["dependencies"] = ["canonical_facts"]
    with pytest.raises(release_tool.VerificationError, match="execution_topology"):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            forged_topology,
            evidence_manifest_bytes=manifest_bytes,
        )

    legacy_topology = deepcopy(retained)
    legacy_audit = legacy_topology["flagship-run.json"]["result"]["audit"][
        "agent_orchestration"
    ]
    del legacy_audit["execution_topology"]
    legacy_audit["parallel_groups"] = [
        ["document_source_integrity", "process_decision_mapping"]
    ]
    with pytest.raises(release_tool.VerificationError, match="execution_topology"):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            legacy_topology,
            evidence_manifest_bytes=manifest_bytes,
        )

    forged_accepted_ids = deepcopy(retained)
    gate = forged_accepted_ids["flagship-run.json"]["result"]["audit"][
        "agent_orchestration"
    ]["deterministic_gates"][1]
    gate["accepted_ids"] = ["unbound"] * gate["accepted_count"]
    with pytest.raises(release_tool.VerificationError, match="accepted_ids"):
        release_tool.verify_dynamic_runtime_acceptance(
            contract,
            report,
            manifest,
            forged_accepted_ids,
            evidence_manifest_bytes=manifest_bytes,
        )


def test_accepted_artifact_hash_matches_backend_and_rejects_floats() -> None:
    artifact = {"z": "ü", "a": [{"basis_points": 9100}, True, None]}
    expected = "a0d744bb4829b2124b022b17dd45499e7012bd19dd95940d1a8a3aed474e42c3"
    assert release_tool.accepted_artifact_hash(artifact) == expected
    assert release_tool.runtime_artifact_hash(artifact) == expected
    assert (
        release_tool.runtime_artifact_hash({"confidence": 0.91})
        == "917ee2f800c6299c798234ab12ba84a416bd6439dd70b1fad1cab3f4a775662a"
    )
    with pytest.raises(release_tool.VerificationError, match="contains a float"):
        release_tool.accepted_artifact_hash({"confidence": 0.91})


def test_static_contract_rejects_an_embedded_runtime_verdict() -> None:
    contract = deepcopy(release_tool.load_json(release_tool.RELEASE_PATH))
    contract["truth"]["production_runtime_acceptance"]["status"] = "passed"
    with pytest.raises(release_tool.VerificationError, match="must not embed"):
        release_tool.verify_static_runtime_acceptance_contract(contract)


def test_agentic_runtime_contract_is_exact_and_tracing_is_disabled() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    runtime = contract["agentic_runtime"]
    assert runtime == release_tool.expected_agentic_runtime()
    assert runtime["framework"] == {
        "langchain": "1.3.14",
        "langgraph": "1.2.9",
        "langchain_openrouter": "0.2.7",
    }
    assert runtime["safety"]["external_tracing"] is False
    assert runtime["safety"]["provider_max_in_flight"] == 1
    assert runtime["parallel_groups"] == [
        ["document_source_integrity", "process_decision_mapping"]
    ]
    assert contract["truth"]["production_runtime_acceptance"][
        "required_provider_max_in_flight"
    ] == 1
    assert [item["agent_id"] for item in runtime["model_agents"]] == [
        "canonical_facts",
        "orchestrator_plan",
        "document_source_integrity",
        "process_decision_mapping",
        "evidence_checklist",
        "final_claim_brief_audit",
    ]


@pytest.mark.parametrize("value", [None, 0, 2])
def test_provider_single_flight_release_contract_rejects_tampering(value) -> None:
    contract = deepcopy(release_tool.load_json(release_tool.RELEASE_PATH))
    if value is None:
        del contract["agentic_runtime"]["safety"]["provider_max_in_flight"]
    else:
        contract["agentic_runtime"]["safety"]["provider_max_in_flight"] = value
    with pytest.raises(release_tool.VerificationError, match="Agentic runtime"):
        release_tool.verify_static_runtime_acceptance_contract(contract)


@pytest.mark.parametrize("value", [None, 0, 2])
def test_provider_single_flight_acceptance_criterion_rejects_tampering(value) -> None:
    contract = deepcopy(release_tool.load_json(release_tool.RELEASE_PATH))
    runtime_acceptance = contract["truth"]["production_runtime_acceptance"]
    if value is None:
        del runtime_acceptance["required_provider_max_in_flight"]
    else:
        runtime_acceptance["required_provider_max_in_flight"] = value
    with pytest.raises(
        release_tool.VerificationError,
        match="required_provider_max_in_flight",
    ):
        release_tool.verify_static_runtime_acceptance_contract(contract)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("model_acceptance_scope", "all_journey_runs"),
        ("learning_comparison_authority", "model_dag"),
        ("requires_learning_comparison_zero_model_activity", False),
        ("required_final_model_ledger_records", 24),
        ("required_final_model_network_calls", 12),
        ("required_final_cache_hits", 12),
    ],
)
def test_flagship_only_model_acceptance_contract_rejects_tampering(
    field: str,
    value,
) -> None:
    contract = deepcopy(release_tool.load_json(release_tool.RELEASE_PATH))
    contract["truth"]["production_runtime_acceptance"][field] = value
    with pytest.raises(release_tool.VerificationError, match=field):
        release_tool.verify_static_runtime_acceptance_contract(contract)


def test_render_uses_curated_frontend_and_model_aware_readiness_probe() -> None:
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    release_tool.verify_render_runtime_contract(contract)
    blueprint = release_tool.yaml.safe_load(
        (release_tool.REPOSITORY / release_tool.LEGACY_RENDER_BLUEPRINT_PATH).read_text(
            encoding="utf-8"
        )
    )
    frontend_service = next(
        item
        for item in blueprint["services"]
        if item.get("name") == "casepath-swiss-claim-lab"
    )
    assert frontend_service["buildCommand"] == (
        "python3 casepath/tools/build_static_site.py --require-known-commit"
    )
    assert frontend_service["staticPublishPath"] == "casepath-public"
    api_service = next(
        item
        for item in blueprint["services"]
        if item.get("name") == "casepath-agentic-api"
    )
    assert api_service["healthCheckPath"] == "/readyz"
    qa_service = next(
        item
        for item in blueprint["services"]
        if item.get("name") == "casepath-guided-canonical-qa"
    )
    assert qa_service["buildCommand"] == release_tool.DEFINITIVE_QA_BUILD_COMMAND
    assert qa_service["startCommand"] == release_tool.DEFINITIVE_QA_START_COMMAND
    assert qa_service["autoDeployTrigger"] == "off"


def test_definitive_qa_runs_zero_provider_browser_preflight_before_production() -> None:
    script = (release_tool.REPOSITORY / "casepath-qa/run-definitive-v20.sh").read_text(
        encoding="utf-8"
    )
    browser_gate = (release_tool.REPOSITORY / "casepath-qa/browser-focused-v20.mjs").read_text(
        encoding="utf-8"
    )
    preflight_marker = "Running mandatory zero-provider full-browser preflight."
    production_marker = "starting the one authorized production journey."
    assert script.index(preflight_marker) < script.index(production_marker)
    assert script.index("CASEPATH_ALLOW_PRODUCTION_MUTATION=0") < script.index(
        production_marker
    )
    assert script.index("BASE_URL=https://casepath.kumarnavish.chatgpt.site") > script.index(
        production_marker
    )
    assert "unset OPENROUTER_API_KEY" in script
    assert "QA Python must be" in script
    assert "CASEPATH_MODEL_MODE=deterministic_reference" in script
    assert "CASEPATH_ALLOW_PRODUCTION_MUTATION=0" in script
    assert script.index("casepath-api/generate_artifacts.py") < script.index(
        "Running mandatory zero-provider full-browser preflight."
    )
    assert script.index("casepath-api/replace_photographic_evidence.py .") < script.index(
        "Running mandatory zero-provider full-browser preflight."
    )
    causal_verifier = "verify-runtime-causal-evidence"
    full_verifier = "verify-runtime-evidence"
    assert script.index(causal_verifier) < script.index(production_marker)
    assert script.index(full_verifier) > script.index(production_marker)
    assert '--report "$preflight_output/report.json"' in script
    assert '--report "$qa_output/report.json"' in script
    assert "test -s \"$repository_root/casepath-api/artifacts/$required_artifact\"" in script
    assert 'summary["network_calls"] == 0' in script
    assert 'summary["actual_cost_usd"] == 0' in script
    assert "bash casepath-qa/run-definitive-v20.sh" in release_tool.DEFINITIVE_QA_BUILD_COMMAND
    assert "const OUT = assertSafeQaOutputParent(" in browser_gate
    assert "path.parse(REPOSITORY_ROOT).root" in browser_gate
    assert "resolved === REPOSITORY_ROOT || resolved === QA_DIRECTORY" in browser_gate
    assert "PREFLIGHT_PARENT_PATTERN.test(path.basename(preflightParent))" in browser_gate
    assert "realParent = realpathSync(parent)" in browser_gate
    assert "Symlinked QA output parent fixture was accepted" in browser_gate
    deterministic_browser_start = script.index(
        "Running mandatory zero-provider full-browser preflight."
    )
    production_start = script.index(production_marker)
    deterministic_browser = script[deterministic_browser_start:production_start]
    assert "exec env -i \\" in deterministic_browser
    for forbidden_name in (
        "OPENROUTER_API_KEY",
        "CASEPATH_AGENT_RUNTIME_PROFILE",
        "CASEPATH_SOURCE_COMMIT",
        "CASEPATH_MODEL_MODE",
        "CASEPATH_MODEL_CUMULATIVE_USD_CAP",
    ):
        assert forbidden_name not in deterministic_browser
    assert browser_gate.index("initialLedgerAdmissionViolations(initialModelLedger)") < browser_gate.index(
        "const reset = await resetDemo()"
    )


def test_review_mutation_cannot_reuse_a_stale_coalesced_run_read() -> None:
    guard = (
        release_tool.REPOSITORY / "casepath/assets/live-v18-insertion-guard.js"
    ).read_text(encoding="utf-8")
    renderer = (release_tool.REPOSITORY / "casepath/assets/live-v16.js").read_text(
        encoding="utf-8"
    )
    assert "const pendingRunMutations = new Map();" in guard
    assert "function effectiveSessionId(request, init)" in guard
    assert "init.headers !== undefined ? init.headers : request?.headers" in guard
    assert "headers.get('X-CasePath-Session')" in guard
    assert "runResourceKey(url, request, init)" in guard
    assert "const isReviewMutation = method === 'POST'" in guard
    assert guard.index("pendingRunReads.delete(resourceKey);") < guard.index(
        "const mutation = nativeFetch(input, init);"
    )
    assert "const activeMutation = pendingRunMutations.get(resourceKey);" in guard
    assert "await activeMutation;" in guard
    assert "runReadWindowMs" not in guard
    assert "window.setTimeout" not in guard
    assert "window.CASEPATH_INSERTION_GUARD = '19.0.2';" in guard
    applied_renderer = renderer[
        renderer.index("function showReviewApplied()") : renderer.index(
            "async function submitReview"
        )
    ]
    assert "result: snapshot(state.review.result)" in applied_renderer
    assert applied_renderer.index("result: snapshot(state.review.result)") < applied_renderer.index(
        "renderProcessWorkspace({ evidence: true, precedents: false })"
    )


def test_accessibility_audit_waits_for_stable_animations_and_keeps_diagnostics() -> None:
    browser_gate = (
        release_tool.REPOSITORY / "casepath-qa/browser-focused-v20.mjs"
    ).read_text(encoding="utf-8")
    focus_css = (
        release_tool.REPOSITORY / "casepath/assets/live-v20-focus.css"
    ).read_text(encoding="utf-8")
    keyframe_start = focus_css.index("@keyframes v20-rise")
    keyframe = focus_css[keyframe_start : focus_css.index("}", keyframe_start) + 1]
    assert "opacity" not in keyframe
    assert "async function settleFiniteAnimationsForAxe(label)" in browser_gate
    assert "Number.isFinite(timing?.endTime)" in browser_gate
    assert "document.getAnimations()" in browser_gate
    assert browser_gate.index("await settleFiniteAnimationsForAxe(label);") < browser_gate.index(
        "new AxeBuilder({ page }).analyze()"
    )
    assert "function axeViolationDiagnostics(violations)" in browser_gate
    assert "const safeAxeToken" in browser_gate
    assert "sha256:${sha256(text)}" in browser_gate
    assert "safeCheckData(check.data)" in browser_gate
    assert "failure_summary:" not in browser_gate
    assert "message: String(check.message" not in browser_gate
    assert "axeViolationDiagnostics(serious)" in browser_gate
    viewport_start = browser_gate.index("async function auditViewports(label, selector)")
    viewport_end = browser_gate.index(
        "\nasync function settleFiniteAnimationsForAxe", viewport_start
    )
    viewport_source = browser_gate[viewport_start:viewport_end]
    assert viewport_source.index("1440, height: 900") < viewport_source.index(
        "runAxe(`${label} desktop`)"
    )
    assert "runAxe(`${label} desktop`)" in viewport_source
    assert "width: 390" not in viewport_source
    assert "width: 320" not in viewport_source
    assert "observeDeferredMobile" not in viewport_source
    assert "screenshot(`${label}-desktop.png`, true)" in viewport_source
    assert "03-lease-pdf-mobile.png" not in browser_gate
    search_check = browser_gate.index(
        "PDF extracted-text search returns navigable page results"
    )
    search_capture = browser_gate.index(
        "await screenshot('03-lease-pdf-search.png');"
    )
    original_tab_return = browser_gate.index(
        "await page.locator('#sourceTabOriginal').click();", search_capture
    )
    assert search_check < search_capture < original_tab_return
    assert browser_gate.count("'03-lease-pdf-search.png'") == 2
    required_visual_start = browser_gate.index("const requiredVisualEvidence = [")
    required_visual_end = browser_gate.index("];", required_visual_start)
    required_visual_source = browser_gate[
        required_visual_start:required_visual_end
    ]
    assert required_visual_source.count(".png'") == 8
    assert "acceptedJourneyMode === 'flagship-review-learning'" in browser_gate
    assert all(
        filename in browser_gate
        for filename in (
            "04-review-desktop.png",
            "05-review-applied-desktop.png",
            "06-learning-desktop.png",
            "07-later-result-desktop.png",
        )
    )
    assert "requiredVisualEvidence.push('02-live-nemotron-agent.png', '03-deterministic-accepted-artifact.png')" in browser_gate
    assert "setViewportSize({ width: 390" not in browser_gate
    assert "setViewportSize({ width: 320" not in browser_gate


def test_handoff_continuity_uses_structured_moments_without_translucent_text() -> None:
    continuity_renderer = (
        release_tool.REPOSITORY / "casepath/assets/live-v17.js"
    ).read_text(encoding="utf-8")
    continuity_css = (
        release_tool.REPOSITORY / "casepath/assets/live-v17-continuity.css"
    ).read_text(encoding="utf-8")
    runtime_css = (
        release_tool.REPOSITORY / "casepath/assets/live-v16.css"
    ).read_text(encoding="utf-8")
    function_start = continuity_renderer.index(
        "function preserveProcessDuringHandoff(canvas)"
    )
    function_end = continuity_renderer.index(
        "\n  async function enhanceLaw(canvas)", function_start
    )
    function_source = continuity_renderer[function_start:function_end]
    assert "const continuityByMoment" in function_source
    assert "canvas.dataset.casepathMoment" in function_source
    assert all(
        f"{moment}: {{" in function_source
        for moment in ("evidence", "experience", "verify")
    )
    assert "canvas.querySelector('.v17-continuity')?.remove();" in function_source
    assert "canvas.textContent" not in function_source
    assert "/verif" not in function_source
    process_block_start = continuity_css.index(".v17-continuity .process-layout")
    process_block_end = continuity_css.index("}", process_block_start)
    process_block = continuity_css[process_block_start : process_block_end + 1]
    assert "opacity" not in process_block
    assert ".v17-continuity .decision-inspector" not in continuity_css
    assert ".process-node.future{opacity:" not in runtime_css
    assert ".before-after section:first-child{opacity:" not in runtime_css
    index = (release_tool.REPOSITORY / "casepath/index.html").read_text(
        encoding="utf-8"
    )
    assert _content_bound_asset_locator("live-v17-continuity.css") in index
    assert _content_bound_asset_locator("live-v16.js") in index
    live_runtime = (
        release_tool.REPOSITORY / "casepath/assets/live-v16.js"
    ).read_text(encoding="utf-8")
    assert "state.eventQueue = state.eventQueue.filter(entry => entry.later !== later);" in live_runtime
    assert "if (activeRun?.status === 'failed')" in live_runtime
    assert "if (updatedRun?.status === 'failed')" in live_runtime
    assert "function terminalFailureReceipts(run)" in live_runtime
    assert "function showTerminalFailure(run, later = false)" in live_runtime
    assert "for (const event of terminalFailureReceipts(run)) rememberPresentedEvent(event);" in live_runtime
    assert "renderFailure(SAFE_MODEL_FAILURE_MESSAGE, run);" in live_runtime
    assert "cached: 'Cached replay'" in live_runtime
    assert "failed: 'Stopped'" in live_runtime
    assert "live: 'Live'" in live_runtime
    assert "cachedReplay ? 'cached' : 'returned'" in live_runtime
    assert 'data-terminal-failure="true"' in live_runtime
    assert 'id="retryFailedRun"' in live_runtime
    assert 'onclick="location.reload()"' not in live_runtime
    assert _content_bound_asset_locator("live-v17.js") in index
    assert _content_bound_asset_locator("live-v18.js") in index
    assert _content_bound_asset_locator("live-v16.css") in index
    assert '.live-chip[data-orchestration-mode="live"]:before' in runtime_css
    assert '.live-chip[data-orchestration-mode="cached"]' in runtime_css
    assert '.live-chip[data-orchestration-mode="failed"]' in runtime_css


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("buildCommand", "node paid-first.mjs", "deterministic browser preflight"),
        ("startCommand", "python3 -m http.server", "hash-bound evidence"),
        ("autoDeployTrigger", "commit", "manual release gate"),
        ("envVars", [], "environment must exactly pin"),
    ],
)
def test_render_definitive_qa_contract_rejects_tampering(
    field,
    value,
    message,
    monkeypatch,
    tmp_path,
) -> None:
    blueprint = release_tool.yaml.safe_load(
        (release_tool.REPOSITORY / release_tool.LEGACY_RENDER_BLUEPRINT_PATH).read_text(
            encoding="utf-8"
        )
    )
    qa_service = next(
        item
        for item in blueprint["services"]
        if item.get("name") == "casepath-guided-canonical-qa"
    )
    qa_service[field] = value
    fixture_path = tmp_path / release_tool.LEGACY_RENDER_BLUEPRINT_PATH
    fixture_path.parent.mkdir(parents=True)
    fixture_path.write_text(
        release_tool.yaml.safe_dump(blueprint),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_tool, "REPOSITORY", tmp_path)
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    with pytest.raises(release_tool.VerificationError, match=message):
        release_tool.verify_render_runtime_contract(contract)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("buildCommand", "echo unsafe", "curated static builder"),
        ("staticPublishPath", "casepath", "curated static output"),
    ],
)
def test_render_curated_frontend_contract_rejects_tampering(
    field,
    value,
    message,
    monkeypatch,
    tmp_path,
) -> None:
    blueprint = release_tool.yaml.safe_load(
        (release_tool.REPOSITORY / release_tool.LEGACY_RENDER_BLUEPRINT_PATH).read_text(
            encoding="utf-8"
        )
    )
    frontend_service = next(
        item
        for item in blueprint["services"]
        if item.get("name") == "casepath-swiss-claim-lab"
    )
    frontend_service[field] = value
    fixture_path = tmp_path / release_tool.LEGACY_RENDER_BLUEPRINT_PATH
    fixture_path.parent.mkdir(parents=True)
    fixture_path.write_text(
        release_tool.yaml.safe_dump(blueprint),
        encoding="utf-8",
    )
    monkeypatch.setattr(release_tool, "REPOSITORY", tmp_path)
    contract = release_tool.load_json(release_tool.RELEASE_PATH)
    with pytest.raises(release_tool.VerificationError, match=message):
        release_tool.verify_render_runtime_contract(contract)
