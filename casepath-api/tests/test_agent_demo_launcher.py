"""Demo startup boundaries; no Keychain access, HTTP request or server is real."""
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "casepath/tools/run_agent_demo.py"
spec = importlib.util.spec_from_file_location("casepath_agent_demo_launcher", SCRIPT)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    runtime = repo / ".runtime/casepath-dev-v2"
    (runtime / "venv/bin").mkdir(parents=True)
    (repo / "casepath").mkdir()
    (repo / "casepath/source-manifest.json").write_bytes(b"sealed manifest")
    python = runtime / "venv/bin/python"
    python.write_bytes(b"pinned interpreter")
    head = "a" * 40
    manifest = demo.sha(b"sealed manifest")
    capsule = runtime / "source-capsules" / manifest
    boot = {"contract": "casepath.local-runtime-boot/2.2.0", "boot_id": "boot-test",
            "source": {"repository": str(repo), "git_head": head, "source_manifest_file_sha256": manifest,
                       "execution_root": str(capsule)},
            "runtime": {"python_path": str(python), "python_real_path": str(python),
                        "python_file_sha256": demo.sha(python.read_bytes())}}
    path = runtime / "runtime-boot-receipt.json"
    path.write_text(json.dumps(boot))
    calls = []
    def checked(argv, **kw):
        calls.append((argv, {**kw, "env": dict(kw["env"])}))
        if argv[1:3] == ["rev-parse", "HEAD"]:
            return head.encode()
        return b""
    monkeypatch.setattr(demo, "run_checked", checked)
    return SimpleNamespace(repo=repo, runtime=runtime, capsule=capsule, boot=boot,
                           path=path, python=python, head=head, calls=calls)


def test_preflight_reuses_exact_capsule_and_read_only_history_closure(prepared, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "never-inherit-this-value")
    info = demo.preflight(prepared.repo)
    assert info["capsule"] == prepared.capsule
    commands = [call[0] for call in prepared.calls]
    assert any("validate_journal" in " ".join(command) for command in commands)
    history = next(command for command in commands if any("validate_local_runtime_history.py" in x for x in command))
    assert "--verify-only" in history
    assert str(prepared.capsule / "casepath/tools/validate_local_runtime_history.py") in history
    assert all("OPENROUTER_API_KEY" not in kw["env"] for _, kw in prepared.calls)
    assert len([c for c in commands if c[-1] == "verify"]) == 2


@pytest.mark.parametrize("inherited", [None, "b" * 40, "unknown"])
def test_preflight_binds_every_verifier_to_validated_git_head(prepared, monkeypatch, inherited):
    if inherited is None:
        monkeypatch.delenv("CASEPATH_SOURCE_COMMIT", raising=False)
    else:
        monkeypatch.setenv("CASEPATH_SOURCE_COMMIT", inherited)
    info = demo.preflight(prepared.repo)
    assert info["env"]["CASEPATH_SOURCE_COMMIT"] == prepared.head
    assert all("CASEPATH_SOURCE_COMMIT" not in options["env"]
               for _, options in prepared.calls[:2])
    assert len(prepared.calls[2:]) == 4  # Both trees, journal, and history.
    assert all(options["env"]["CASEPATH_SOURCE_COMMIT"] == prepared.head
               for _, options in prepared.calls[2:])


def test_invalid_git_head_cannot_fall_back_to_inherited_commit(prepared, monkeypatch):
    monkeypatch.setenv("CASEPATH_SOURCE_COMMIT", prepared.head)
    checked = demo.run_checked
    def invalid_head(argv, **options):
        result = checked(argv, **options)
        return b"unknown" if argv[1:3] == ["rev-parse", "HEAD"] else result
    monkeypatch.setattr(demo, "run_checked", invalid_head)
    with pytest.raises(demo.DemoError, match="no exact source commit"):
        demo.preflight(prepared.repo)
    assert len(prepared.calls) == 2
    assert all("CASEPATH_SOURCE_COMMIT" not in options["env"]
               for _, options in prepared.calls)


def test_release_verifier_loads_real_dependencies_in_isolated_pinned_python(prepared):
    demo.preflight(prepared.repo)
    verifiers = [(argv, options) for argv, options in prepared.calls if argv[-1] == "verify"]
    assert len(verifiers) == 2
    for argv, options in verifiers:
        # Exercise the actual release module and its yaml/PIL/pypdf imports.
        # --help stops before artifact verification or any output generation.
        completed = subprocess.run(
            [sys.executable, *argv[1:-2], str(SCRIPT.with_name("casepath_release.py")), "--help"],
            cwd=prepared.repo, env=options["env"], capture_output=True, timeout=30, check=False,
        )
        assert completed.returncode == 0, completed.stderr.decode()
        assert b"prepare-artifacts" in completed.stdout
        assert argv[1:-2] == ["-I", "-B", "-P"]
    history = next(argv for argv, _ in prepared.calls
                   if any("validate_local_runtime_history.py" in part for part in argv))
    assert history[1:5] == ["-I", "-S", "-B", "-P"]


def test_dirty_checkout_stops_before_verifiers_and_credentials(prepared, monkeypatch):
    monkeypatch.setattr(demo, "run_checked", lambda *a, **kw: b" M casepath/index.html\n")
    monkeypatch.setattr(demo, "keychain_credential", lambda: pytest.fail("credential read"))
    with pytest.raises(demo.DemoError, match="authored changes"):
        demo.preflight(prepared.repo)


@pytest.mark.parametrize("field,value", [("git_head", "b" * 40),
    ("source_manifest_file_sha256", "b" * 64), ("execution_root", "/another/capsule")])
def test_boot_from_another_commit_or_capsule_is_refused(prepared, field, value):
    prepared.boot["source"][field] = value
    prepared.path.write_text(json.dumps(prepared.boot))
    with pytest.raises(demo.DemoError, match="exact prepared commit"):
        demo.preflight(prepared.repo)


def test_interpreter_drift_is_refused_before_product_import(prepared):
    prepared.python.write_bytes(b"changed interpreter")
    with pytest.raises(demo.DemoError, match="Python identity"):
        demo.preflight(prepared.repo)
    assert len(prepared.calls) == 2  # git only; no product verifier imported


def test_history_failure_is_not_silenced(prepared, monkeypatch):
    prior = demo.run_checked
    def fail_history(argv, **kw):
        if any("validate_local_runtime_history.py" in x for x in argv):
            raise demo.DemoError("history rejected")
        return prior(argv, **kw)
    monkeypatch.setattr(demo, "run_checked", fail_history)
    with pytest.raises(demo.DemoError, match="history rejected"):
        demo.preflight(prepared.repo)


def test_shared_kernel_lease_blocks_second_process_entry(tmp_path):
    path = tmp_path / "environment.lock"
    with ExitStack() as first, ExitStack() as second:
        demo.acquire_lease(path, first)
        with pytest.raises(demo.DemoError, match="shared lease"):
            demo.acquire_lease(path, second)
    with ExitStack() as third:
        assert demo.acquire_lease(path, third) >= 0


def test_symlink_and_external_hardlink_files_are_refused(tmp_path):
    original = tmp_path / "file"
    original.write_bytes(b"contents")
    link = tmp_path / "link"
    link.symlink_to(original)
    with pytest.raises(demo.DemoError):
        demo.regular(link)
    link.unlink()
    os.link(original, link)
    with pytest.raises(demo.DemoError):
        demo.regular(original)


def catalogue(tmp_path, *, age=0, model="vendor/model"):
    value = {"data": [{"id": model, "pricing": {"prompt": "0.0000001", "completion": "0.0000004"},
                       "supported_parameters": ["tools", "tool_choice", "max_tokens"]}]}
    packet = {"catalogue": value, "catalogue_sha256": demo.sha(demo.canonical(value)),
              "fetched_at": (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat()}
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps(packet))
    return path


@pytest.mark.parametrize("age,model", [(86401, "vendor/model"), (-60, "vendor/model"),
                                      (0, "vendor/missing"), (0, "openrouter/auto")])
def test_stale_or_unselected_catalogue_refused_without_download(tmp_path, age, model):
    path = catalogue(tmp_path, age=age)
    with pytest.raises(demo.DemoError):
        demo.catalogue_snapshot(path, model)


def test_catalogue_identity_tampering_rejected(tmp_path):
    path = catalogue(tmp_path)
    packet = json.loads(path.read_text())
    packet["catalogue"]["data"].append({"id": "vendor/other"})
    path.write_text(json.dumps(packet))
    with pytest.raises(demo.DemoError):
        demo.catalogue_snapshot(path, "vendor/model")


def endpoint_inputs(tmp_path):
    model = {"id": "vendor/model", "pricing": {"prompt": "0.0000001", "completion": "0.0000004"},
             "supported_parameters": ["tools", "tool_choice", "max_tokens"]}
    endpoint = {"status": 0, "tag": "vendor", "pricing": model["pricing"].copy(),
                "supported_parameters": model["supported_parameters"].copy(),
                "supports_tool_choice": {"required": True}}
    packet = {"at": datetime.now(timezone.utc).isoformat(), "status": 200,
              "response": {"data": {"id": model["id"], "endpoints": [endpoint]}}}
    path = tmp_path / "endpoints.json"
    path.write_text(json.dumps(packet))
    return model, packet, path


def test_endpoint_snapshot_checks_actual_request_capabilities(tmp_path):
    model, packet, path = endpoint_inputs(tmp_path)
    raw = path.read_bytes()
    assert demo.endpoint_snapshot(path, model) == raw
    # A stale snapshot cannot establish present routing even with a valid model.
    packet["at"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    path.write_text(json.dumps(packet))
    with pytest.raises(demo.DemoError):
        demo.endpoint_snapshot(path, model)


@pytest.mark.parametrize("failure", ["model", "required", "max_tokens", "price", "reasoning", "status", "malformed"])
def test_endpoint_snapshot_rejects_unroutable_request(tmp_path, failure):
    model, packet, path = endpoint_inputs(tmp_path)
    endpoint = packet["response"]["data"]["endpoints"][0]
    if failure == "model": packet["response"]["data"]["id"] = "vendor/other"
    if failure == "required": endpoint["supports_tool_choice"]["required"] = False
    if failure == "max_tokens": endpoint["supported_parameters"].remove("max_tokens")
    if failure == "price": endpoint["pricing"]["prompt"] = "0.0000002"
    if failure == "reasoning": model["supported_parameters"].append("reasoning")
    if failure == "status": endpoint["status"] = 1
    if failure == "malformed": endpoint["pricing"]["prompt"] = "NaN"
    path.write_text(json.dumps(packet))
    with pytest.raises(demo.DemoError):
        demo.endpoint_snapshot(path, model)


def test_keychain_error_output_never_escapes(monkeypatch):
    secret = "sk-or-test-secret-never-persist"
    monkeypatch.setattr(demo.sys, "platform", "darwin")
    calls = []
    def invoke(argv, **kw):
        calls.append((argv, kw))
        return subprocess.CompletedProcess(argv, 1, secret.encode(), secret.encode())
    monkeypatch.setattr(demo.subprocess, "run", invoke)
    with pytest.raises(demo.DemoError) as error:
        demo.keychain_credential()
    assert secret not in str(error.value)
    assert secret not in repr(calls)
    assert demo.SERVICE in calls[0][0]


def test_child_environment_has_only_explicit_credentials_and_no_normal_receipt(prepared, monkeypatch):
    monkeypatch.setenv("LANGSMITH_API_KEY", "unrequested")
    monkeypatch.setenv("OPENROUTER_API_KEY", "inherited-must-be-ignored")
    info = demo.preflight(prepared.repo)
    env = demo.child_environment(info, Path("/local/catalogue.json"), "vendor/model", "sk-or-explicit")
    assert env["OPENROUTER_API_KEY"] == "sk-or-explicit"
    assert "LANGSMITH_API_KEY" not in env
    assert "CASEPATH_LOCAL_RUNTIME_RECEIPT" not in env
    assert env["CASEPATH_MODEL_MODE"] == "deterministic_reference"
    assert env["CASEPATH_AGENT_WORK_DEMO"] == "1"
    assert env["CASEPATH_AGENT_WORK_MAX_EXTERNAL_RUNS"] == "3"
    assert env["CASEPATH_AGENT_WORK_TOTAL_COST_USD"] == "0.10"


def ready_packet(head, *, secret=None):
    budget = {**demo.POLICY, "scope": "persistent_local_demo", "runs_used": 0, "provider_calls_used": 0,
              "actual_cost_usd": "0", "reserved_cost_usd": "0", "remaining_cost_usd": "0.10",
              "unknown_calls": 0, "can_start": True, "reason": None, "automatic_retry": False}
    return {"/healthz": {"source_commit": head, "source_commit_aligned": True, "source_commit_conflict": False},
            "/deployment.json": {"source_commit": head, "alignment_eligible": True},
            "/deployment-health": {"source_commit": head},
            "/readyz": {"status": "ready", "model_budget": {"credential_configured": True}},
            "/api/agent-work/v1/capabilities": {"external_configuration_status": "ready",
                "facts_workers": ["reference", "external_facts"], "external": {"model": "vendor/model", "cost_limit_usd": "0.02"},
                "external_budget": budget, "untrusted_extra": secret}}


@pytest.mark.parametrize("change", ["head", "credential", "model", "budget", "retry", "cost", "reason", "count"])
def test_readiness_refuses_misalignment_or_false_budget(prepared, change):
    info = demo.preflight(prepared.repo)
    packet = ready_packet(info["head"])
    caps = packet["/api/agent-work/v1/capabilities"]
    if change == "head": packet["/deployment.json"]["source_commit"] = "b" * 40
    if change == "credential": packet["/readyz"]["model_budget"]["credential_configured"] = False
    if change == "model": caps["external"]["model"] = "other/model"
    if change == "budget": caps["external_budget"]["total_cost_limit_usd"] = "1.00"
    if change == "retry": caps["external_budget"]["automatic_retry"] = True
    if change == "cost": caps["external_budget"]["actual_cost_usd"] = "NaN"
    if change == "reason": caps["external_budget"]["reason"] = "sk-or-must-not-be-persisted"
    if change == "count": caps["external_budget"]["provider_calls_used"] = True
    with pytest.raises(demo.DemoError):
        demo.readiness(info, "vendor/model", request=packet.__getitem__)


def test_only_public_readiness_fields_are_saved_and_receipt_is_append_only(prepared, tmp_path):
    info = demo.preflight(prepared.repo)
    secret = "sk-or-test-secret-never-persist"
    packet = ready_packet(info["head"], secret=secret)
    output = demo.readiness(info, "vendor/model", request=packet.__getitem__)
    path = tmp_path / "ready.json"
    demo.write_receipt(path, output)
    assert secret not in path.read_text()
    saved = json.loads(path.read_text())
    digest = saved.pop("receipt_sha256")
    assert digest == demo.sha(demo.canonical(saved))
    with pytest.raises(FileExistsError):
        demo.write_receipt(path, output)


def allowance_fixture():
    base = ready_packet('a' * 40)['/api/agent-work/v1/capabilities']['external_budget']
    base.update(base_policy_sha256=demo.sha(demo.canonical(demo.POLICY)), effective_max_runs=3,
                run_grant=None, runs_used=3, can_start=False, reason='run_limit_reached')
    grant = {'contract':'casepath.external-run-grant/1.0.0', 'additional_runs':1,
             'base_policy_sha256':base['base_policy_sha256'],
             'prior_budget_sha256':demo.sha(demo.canonical(base)), 'prior_budget':base,
             'actor':'Authorized operator', 'reason':'One explicitly approved review after the bounded correction.',
             'idempotency_key':'allowance-fixture', 'granted_at':'2026-10-08T17:00:00+00:00'}
    return {**grant, 'grant_sha256':demo.sha(demo.canonical(grant))}


def test_readiness_retains_only_verified_extra_run_identity(prepared):
    info = demo.preflight(prepared.repo)
    packet = ready_packet(info['head'])
    budget = packet['/api/agent-work/v1/capabilities']['external_budget']
    grant = allowance_fixture()
    budget.update(effective_max_runs=4, run_grant=grant, base_policy_sha256=grant['base_policy_sha256'])
    result = demo.readiness(info, 'vendor/model', request=packet.__getitem__)
    assert result['budget']['effective_max_runs'] == 4
    assert result['budget']['run_grant_sha256'] == grant['grant_sha256']
    assert 'reason' not in result['budget'].get('run_grant', {})


@pytest.mark.parametrize('change', ['missing', 'tampered', 'too_many', 'wrong_base'])
def test_readiness_refuses_unproven_extra_allowance(prepared, change):
    info = demo.preflight(prepared.repo)
    packet = ready_packet(info['head'])
    budget = packet['/api/agent-work/v1/capabilities']['external_budget']
    grant = allowance_fixture()
    budget.update(effective_max_runs=4, run_grant=grant, base_policy_sha256=grant['base_policy_sha256'])
    if change == 'missing': budget['run_grant'] = None
    if change == 'tampered': grant['actor'] = 'Different operator'
    if change == 'too_many': budget['effective_max_runs'] = 5
    if change == 'wrong_base': budget['base_policy_sha256'] = 'f' * 64
    with pytest.raises(demo.DemoError):
        demo.readiness(info, 'vendor/model', request=packet.__getitem__)


def test_extra_allowance_is_explicit_and_uses_no_credential_or_server(prepared, monkeypatch):
    info = demo.preflight(prepared.repo)
    database = info['data'] / 'agent-work-v1.sqlite3'
    database.parent.mkdir(parents=True)
    database.write_bytes(b'fixture only; child is mocked')
    monkeypatch.setattr(demo, 'preflight', lambda repository: info)
    locks = []
    monkeypatch.setattr(demo, 'acquire_lease', lambda path, stack: locks.append(path) or 7)
    monkeypatch.setattr(demo, 'reserve_origin', lambda stack: None)
    monkeypatch.setattr(demo, 'keychain_credential', lambda: pytest.fail('credential access'))
    monkeypatch.setattr(demo.subprocess, 'Popen', lambda *a, **k: pytest.fail('server startup'))
    grant = allowance_fixture(); calls = []
    def child(argv, **options):
        calls.append((argv, options))
        return demo.canonical(grant)
    monkeypatch.setattr(demo, 'run_checked', child)
    result = demo.grant_extra_run(prepared.repo, expected_budget_sha256=grant['prior_budget_sha256'],
                                 actor=grant['actor'], reason=grant['reason'], idempotency_key=grant['idempotency_key'])
    assert result['grant'] == grant and result['source_commit'] == info['head']
    assert result['provider_requests_started'] == 0
    assert locks == [prepared.runtime/'environment.lock', prepared.repo/'.runtime/casepath-data-v1.lock']
    argv, options = calls[0]
    assert argv[:4] == [str(info['python']), '-I', '-B', '-P']
    assert str(database) in argv and str(info['capsule']/'casepath-api') in argv
    assert 'OPENROUTER_API_KEY' not in options['env']
    assert json.loads(argv[-1])['expected_budget_sha256'] == grant['prior_budget_sha256']


def test_allowance_cli_never_implicitly_starts_a_review(monkeypatch):
    calls=[]
    monkeypatch.setattr(demo, 'grant_extra_run', lambda repository, **kwargs: calls.append(kwargs) or {'grant':'fixture'})
    monkeypatch.setattr(demo, 'serve', lambda *a, **k: pytest.fail('server startup'))
    assert demo.main(['--grant-one-extra-run', '--expected-budget-sha256', 'a'*64,
                      '--actor','Authorized operator','--reason','One approved review',
                      '--idempotency-key','grant-fixture']) == 0
    assert len(calls) == 1
    with pytest.raises(SystemExit): demo.main(['--grant-one-extra-run'])


def test_port_busy_fails_before_keychain_or_product_verification(prepared, monkeypatch):
    def occupied(_stack):
        raise demo.DemoError("Port 4173 is occupied")
    monkeypatch.setattr(demo, "reserve_origin", occupied)
    monkeypatch.setattr(demo, "preflight", lambda *a: pytest.fail("product verification"))
    monkeypatch.setattr(demo, "keychain_credential", lambda: pytest.fail("credential read"))
    with pytest.raises(demo.DemoError, match="Port 4173"):
        demo.serve(prepared.repo, Path("unused"), "vendor/model")


def test_serve_passes_shared_leases_and_socket_without_persisting_secret(prepared, tmp_path, monkeypatch):
    info = demo.preflight(prepared.repo)
    monkeypatch.setattr(demo, "preflight", lambda *a: info)
    path = catalogue(tmp_path)
    _, _, endpoints = endpoint_inputs(tmp_path)
    secret = "sk-or-test-secret-never-persist"
    monkeypatch.setattr(demo, "keychain_credential", lambda: secret)
    monkeypatch.setattr(demo, "reserve_origin", lambda stack: SimpleNamespace(fileno=lambda: 99))
    monkeypatch.setattr(demo, "readiness", lambda *a: demo.readiness_result)
    demo.readiness_result = {"source_commit": info["head"], "credential_configured": True}
    calls = []
    class Child:
        pid = 321
        returncode = None
        def poll(self): return self.returncode
        def wait(self, **kw): self.returncode = 0
    def child(argv, **kw):
        calls.append((argv, {**kw, "env": dict(kw["env"])}))
        return Child()
    monkeypatch.setattr(demo.subprocess, "Popen", child)
    demo.serve(prepared.repo, path, "vendor/model")
    argv, options = calls[0]
    assert secret not in repr(argv)
    assert options["env"]["OPENROUTER_API_KEY"] == secret
    assert len(options["pass_fds"]) == 3 and options["pass_fds"][-1] == 99
    assert options["stdout"] == subprocess.DEVNULL and options["stderr"] == subprocess.DEVNULL
    for output in (prepared.repo / ".runtime/casepath-openrouter-demo").rglob("*"):
        if output.is_file(): assert secret not in output.read_text()
    assert json.loads(prepared.path.read_text()) == prepared.boot
    assert not (prepared.runtime / "boots").exists()
    launch = next((prepared.repo / ".runtime/casepath-openrouter-demo").iterdir())
    assert (launch / "endpoints.json").read_bytes() == endpoints.read_bytes()
    assert json.loads((launch / "ready.json").read_text())["endpoint_file_sha256"] == demo.sha(endpoints.read_bytes())


def test_incompatible_endpoint_stops_before_credential_or_child(prepared, tmp_path, monkeypatch):
    path = catalogue(tmp_path)
    _, packet, endpoints = endpoint_inputs(tmp_path)
    packet["response"]["data"]["endpoints"][0]["supports_tool_choice"]["required"] = False
    endpoints.write_text(json.dumps(packet))
    monkeypatch.setattr(demo, "reserve_origin", lambda stack: SimpleNamespace(fileno=lambda: 99))
    monkeypatch.setattr(demo, "keychain_credential", lambda: pytest.fail("credential read"))
    monkeypatch.setattr(demo.subprocess, "Popen", lambda *a, **kw: pytest.fail("server start"))
    with pytest.raises(demo.DemoError, match="endpoint snapshot"):
        demo.serve(prepared.repo, path, "vendor/model")
