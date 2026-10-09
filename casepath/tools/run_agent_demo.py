#!/usr/bin/env python3
"""Serve a bounded facts-role or autonomous demo from a verified capsule.

Requires a clean committed checkout and a successful normal local boot of that
same commit. The explicit --autonomous profile resumes saved autonomous work
under the preserved lifetime budget. A separate offline command can record the
single three-workflow capacity extension without starting inference. Dollar
limits remain unchanged. The default facts-role profile requires
manual review admission. Normal zero-credential boot history is preserved.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import signal
import socket
import stat
import subprocess
import sys
import time
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler
import uuid


MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./:+-]{2,180}")
POLICY = {"max_runs": 3, "max_provider_calls": 18,
          "total_cost_limit_usd": "0.10", "run_cost_limit_usd": "0.02"}
SERVICE = "CasePath OpenRouter demo"


class DemoError(RuntimeError):
    """Messages are fixed, public descriptions; never include child output."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(path, limit=16_000_000):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
                raise DemoError("A required local file is not regular or is too large.")
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise DemoError("A required local file exceeds its size limit.")
        return raw
    except OSError as exc:
        raise DemoError("A required local file is missing or unsafe.") from exc


def run_checked(argv, *, cwd, env):
    try:
        result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                                timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DemoError("A local verification command could not finish.") from exc
    if result.returncode:
        raise DemoError("Local verification failed. Run normal preparation and boot first.")
    return result.stdout


def clean_environment(runtime):
    return {"HOME": str(runtime / "home"), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            "PATH": f"{runtime}/venv/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONHASHSEED": "0", "PYTHONNOUSERSITE": "1", "PYTHONSAFEPATH": "1",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPYCACHEPREFIX": str(runtime / "pycache"),
            "SOURCE_DATE_EPOCH": "1786406400", "TMPDIR": str(runtime / "tmp"), "TZ": "UTC"}


def acquire_lease(path, stack):
    # macOS lockf(1), like Linux flock(1), uses BSD flock locks. The same files
    # and ordering therefore exclude normal dev/test/seed/replay processes.
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        stack.callback(os.close, fd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise DemoError("The shared runtime lease is unsafe.")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except OSError as exc:
        raise DemoError("The normal runtime or another demo holds the shared lease.") from exc


def reserve_origin(stack):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    stack.callback(listener.close)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listener.bind(("127.0.0.1", 4173))
        listener.listen(64)
    except OSError as exc:
        raise DemoError("Port 4173 is occupied. Stop its owned CasePath server first.") from exc
    return listener


def preflight(repository):
    runtime = repository / ".runtime/casepath-dev-v2"
    data = repository / ".runtime/casepath-data-v1"
    env = clean_environment(runtime)
    if run_checked(["/usr/bin/git", "status", "--porcelain"], cwd=repository, env=env).strip():
        raise DemoError("The checkout has authored changes. Seal, test and commit before the demo.")
    head = run_checked(["/usr/bin/git", "rev-parse", "HEAD"], cwd=repository, env=env).decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise DemoError("The checkout has no exact source commit.")
    env["CASEPATH_SOURCE_COMMIT"] = head
    manifest_sha = sha(regular(repository / "casepath/source-manifest.json"))
    capsule = runtime / "source-capsules" / manifest_sha
    boot_raw = regular(runtime / "runtime-boot-receipt.json", 64_000_000)
    try:
        boot = json.loads(boot_raw)
        source = boot["source"]
        identity = boot["runtime"]
        if (boot["contract"] != "casepath.local-runtime-boot/2.2.0"
                or source["repository"] != str(repository)
                or source["git_head"] != head
                or source["source_manifest_file_sha256"] != manifest_sha
                or source["execution_root"] != str(capsule)):
            raise DemoError("Run normal dev successfully for this exact prepared commit first.")
        python = runtime / "venv/bin/python"
        if (identity["python_path"] != str(python)
                or str(python.resolve()) != identity["python_real_path"]
                or sha(regular(python.resolve(), 100_000_000)) != identity["python_file_sha256"]):
            raise DemoError("The pinned Python identity differs from the verified normal boot.")
    except (KeyError, TypeError, ValueError) as exc:
        raise DemoError("The normal boot receipt is missing required identity.") from exc
    isolated = [str(python), "-I", "-S", "-B", "-P"]
    # Verify both trees before loading any product module from the capsule.
    # The release verifier needs the pinned site-packages; only the runtime
    # history verifier below is stdlib-only and can disable site initialization.
    for root in (repository, capsule):
        run_checked([str(python), "-I", "-B", "-P", str(root / "casepath/tools/casepath_release.py"), "verify"],
                    cwd=repository, env=env)
    run_checked([str(python), "-I", "-B", "-P", "-c",
                 'import runpy,sys; sys.path.insert(0,sys.argv.pop(1)); '
                 'sys.argv[0]="validate_journal"; runpy.run_module("casepath_api.validate_journal",run_name="__main__",alter_sys=True)',
                 str(capsule / "casepath-api"), str(data / "casepath.db")], cwd=repository, env=env)
    # This rechecks every historical boot against its own capsule and verifies
    # current interpreter/site-packages bytes. --verify-only cannot promote a pointer.
    run_checked([*isolated, str(capsule / "casepath/tools/validate_local_runtime_history.py"),
                 "--verify-only", str(runtime), str(data), str(repository)], cwd=repository, env=env)
    if sha(regular(runtime / "runtime-boot-receipt.json", 64_000_000)) != sha(boot_raw):
        raise DemoError("The normal boot identity changed during verification.")
    info = {"repository": repository, "runtime": runtime, "data": data, "capsule": capsule,
            "python": python, "head": head, "manifest_sha256": manifest_sha,
            "normal_boot_file_sha256": sha(boot_raw), "normal_boot_id": boot["boot_id"], "env": env}
    verify_preserved_provider_budget(info)
    return info


def prior_demo_budgets(root):
    """Read sealed observations; None retains a launch with unobserved usage."""
    if not root.exists() and not root.is_symlink():
        return []
    if root.is_symlink() or not root.is_dir():
        raise DemoError("The prior demo receipt directory is unsafe.")
    observations = []
    for launch in sorted(root.iterdir()):
        if launch.is_symlink():
            raise DemoError("The prior demo history contains an unsafe path.")
        if not launch.is_dir():
            continue  # Operator-supplied catalogue and endpoint snapshots.
        for name, field in (("ready.json", "readiness"), ("stopped.json", "last_observed_readiness")):
            path = launch / name
            if not path.exists() and not path.is_symlink():
                continue
            try:
                raw = regular(path)
                receipt = json.loads(raw)
                material = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
                if (receipt["receipt_sha256"] != sha(canonical(material))
                        or raw != canonical(receipt) + b"\n"
                        or receipt["contract"] != "casepath.explicit-agent-demo-boot/1.0.0"
                        or receipt["launch_id"] != launch.name or receipt["policy"] != POLICY):
                    raise ValueError
                observed = receipt[field]
                if observed is None and name == "stopped.json":
                    observations.append(None)  # The child may have resumed work before readiness.
                    continue
                budget = observed["budget"]
                if any(budget[k] != v for k, v in POLICY.items()):
                    raise ValueError
                for key in ("runs_used", "provider_calls_used", "autonomous_workflows_used", "autonomous_provider_calls_used",
                            "autonomous_grant_workflows_used", "autonomous_grant_provider_calls_used",
                            "original_nine_workflows_used", "original_nine_provider_calls_used"):
                    if key in budget and (type(budget[key]) is not int or budget[key] < 0):
                        raise ValueError
                for key in ("runs_used", "provider_calls_used", "actual_cost_usd"):
                    if key not in budget:
                        raise ValueError
                cost = Decimal(budget["actual_cost_usd"])
                if not cost.is_finite() or cost < 0:
                    raise ValueError
                for key in ("run_grant_sha256", "autonomous_policy_sha256", "autonomous_capacity_grant_sha256", "original_nine_grant_sha256"):
                    if budget.get(key) is not None and re.fullmatch(r"[0-9a-f]{64}", budget[key]) is None:
                        raise ValueError
                if budget.get("effective_max_runs", 3) not in (3, 4):
                    raise ValueError
                effective_calls = budget.get("effective_autonomous_max_provider_calls", 18)
                if (type(effective_calls) is not int or effective_calls not in (18, 24, 42)
                        or (budget.get("autonomous_capacity_grant_sha256") is None) != (effective_calls == 18)
                        or (budget.get("original_nine_grant_sha256") is not None) != (effective_calls == 42)
                        or budget.get("autonomous_grant_workflows_used", 0) > 3
                        or budget.get("autonomous_grant_provider_calls_used", 0) > 6
                        or not 0 <= budget.get("original_nine_workflows_used",0) <= 9
                        or not budget.get("original_nine_workflows_used",0) <= budget.get("original_nine_provider_calls_used",0) <= 2 * budget.get("original_nine_workflows_used",0)):
                    raise ValueError
                observations.append(budget)
            except (AttributeError, KeyError, TypeError, ValueError, InvalidOperation):
                raise DemoError("A prior demo receipt cannot establish its saved provider budget.") from None
    return observations


def read_only_provider_budget(info):
    """Replay an existing ledger in memory; never initialize its on-disk schema."""
    database = info["data"] / "agent-work-v1.sqlite3"
    try:
        descriptor = os.open(database, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise OSError
        # Opening a WAL database even in mode=ro may create sidecars. Copy the
        # DB and its WAL under the shared data lease before SQLite opens either.
        # Legacy schema additions are applied only to the in-memory snapshot.
        command = [str(info["python"]), "-I", "-B", "-P", "-c", '''
import json, os, shutil, sqlite3, stat, sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from casepath_api.agent_work.store import WorkStore, SCHEMA
database = Path(sys.argv[2])
with tempfile.TemporaryDirectory(prefix="casepath-budget-check-") as temporary:
    copied = Path(temporary) / "work.sqlite3"
    for suffix in ("", "-wal"):
        original = Path(str(database) + suffix)
        if suffix and not original.exists() and not original.is_symlink():
            continue
        descriptor = os.open(original, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ValueError("unsafe work ledger file")
            with Path(str(copied) + suffix).open("xb") as target:
                shutil.copyfileobj(source, target)
    with sqlite3.connect(copied) as source, sqlite3.connect(":memory:") as snapshot:
        if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("invalid work ledger")
        source.backup(snapshot)
        snapshot.executescript(SCHEMA)
        snapshot.row_factory = sqlite3.Row
        store = object.__new__(WorkStore)
        print(json.dumps(store._external_budget(snapshot), sort_keys=True, separators=(",", ":")))
''', str(info["capsule"] / "casepath-api"), str(database)]
        result = json.loads(run_checked(command, cwd=info["repository"], env=info["env"]))
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (OSError, ValueError, DemoError):
        raise DemoError("The previously used provider ledger is missing or invalid; its allowance cannot be recreated.") from None


def verify_preserved_provider_budget(info):
    observations = prior_demo_budgets(info["repository"] / ".runtime/casepath-openrouter-demo")
    if not observations:
        return
    current = read_only_provider_budget(info)
    try:
        if any(current[k] != v for k, v in POLICY.items()):
            raise ValueError
        grant_sha = verified_run_grant(current["run_grant"]) if current.get("run_grant") else None
        policy_sha = verified_autonomous_policy(current["autonomous_policy"]) if current.get("autonomous_policy") else None
        capacity = verified_autonomous_capacity(current)
        for prior in observations:
            if prior is None:
                continue  # Existence and complete replay are still required above.
            for key in ("runs_used", "provider_calls_used", "autonomous_workflows_used", "autonomous_provider_calls_used",
                        "autonomous_grant_workflows_used", "autonomous_grant_provider_calls_used",
                        "original_nine_workflows_used", "original_nine_provider_calls_used"):
                if key in prior and (type(current.get(key)) is not int or current[key] < prior[key]):
                    raise ValueError
            if Decimal(current["actual_cost_usd"]) < Decimal(prior["actual_cost_usd"]):
                raise ValueError
            if (current["effective_max_runs"] < prior.get("effective_max_runs", 3)
                    or prior.get("run_grant_sha256") is not None and prior["run_grant_sha256"] != grant_sha
                    or prior.get("autonomous_policy_sha256") is not None and prior["autonomous_policy_sha256"] != policy_sha
                    or capacity["effective_autonomous_max_provider_calls"] < prior.get("effective_autonomous_max_provider_calls", 18)
                    or prior.get("autonomous_capacity_grant_sha256") is not None and
                       prior["autonomous_capacity_grant_sha256"] != capacity["autonomous_capacity_grant_sha256"]
                    or prior.get("original_nine_grant_sha256") is not None and
                       prior["original_nine_grant_sha256"] != capacity.get("original_nine_grant_sha256")):
                raise ValueError
        # Reservations and unknown counts may decrease when retained requests
        # settle. Their current validity is checked by WorkStore's full replay.
    except (DemoError, KeyError, TypeError, ValueError, InvalidOperation):
        raise DemoError("The provider ledger rolled back behind a saved demo budget; no new allowance was opened.") from None


def catalogue_snapshot(path, model):
    if not MODEL.fullmatch(model) or model.startswith("openrouter/"):
        raise DemoError("Select one concrete model identifier.")
    raw = regular(path, 2_000_000)
    try:
        packet = json.loads(raw)
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(packet["fetched_at"])).total_seconds()
        if not 0 <= age <= 86400 or sha(canonical(packet["catalogue"])) != packet["catalogue_sha256"]:
            raise ValueError
        matches = [row for row in packet["catalogue"]["data"] if row.get("id") == model]
        if len(matches) != 1:
            raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise DemoError("Use a valid local catalogue snapshot from the preceding 24 hours containing this model.") from exc
    return raw


def endpoint_snapshot(path, model, *, autonomous=False):
    """Check actual routing capabilities, not only catalogue-level tool support."""
    raw = regular(path, 2_000_000)
    try:
        packet = json.loads(raw)
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(packet["at"])).total_seconds()
        data = packet["response"]["data"]
        if not 0 <= age <= 86400 or packet["status"] != 200 or data["id"] != model["id"]:
            raise ValueError
        required = {"response_format", "structured_outputs", "max_tokens"} if autonomous else {"tools", "tool_choice", "max_tokens"}
        if autonomous and not required.issubset(model["supported_parameters"]):
            raise ValueError
        if "reasoning" in model["supported_parameters"]:
            required.add("reasoning")
        ceiling = {key: Decimal(str(model["pricing"][key])) for key in ("prompt", "completion")}
        if autonomous:
            ceiling["request"] = Decimal(str(model["pricing"].get("request", "0")))
            for tier in model["pricing"].get("overrides", []):
                if tier["min_prompt_tokens"] <= 64000:
                    for key in ceiling:
                        ceiling[key] = max(ceiling[key], Decimal(str(tier.get(key, ceiling[key]))))
        if any(not value.is_finite() or value < 0 for value in ceiling.values()):
            raise ValueError
        for endpoint in data["endpoints"]:
            if (type(endpoint.get("status")) is not int or endpoint["status"] != 0
                    or (not autonomous and endpoint.get("supports_tool_choice", {}).get("required") is not True)
                    or not required.issubset(endpoint.get("supported_parameters", []))):
                continue
            prices = endpoint["pricing"]
            if not {"prompt", "completion"}.issubset(prices):
                continue
            applicable = [prices, *(tier for tier in prices.get("overrides", [])
                                   if tier["min_prompt_tokens"] <= (64000 if autonomous else 24000))]
            if all(all(Decimal(str(tier.get(key, prices.get(key, "0")))).is_finite()
                       and 0 <= Decimal(str(tier.get(key, prices.get(key, "0")))) <= ceiling[key]
                       for key in ceiling) for tier in applicable):
                return raw
    except (KeyError, TypeError, ValueError, InvalidOperation):
        pass
    raise DemoError("Use a recent endpoint snapshot with the profile's required request parameters within the catalogue price ceiling.")


def keychain_credential():
    if sys.platform != "darwin":
        raise DemoError("This demo credential loader requires macOS Keychain.")
    account = pwd.getpwuid(os.getuid())
    try:
        result = subprocess.run(["/usr/bin/security", "find-generic-password", "-w", "-s", SERVICE,
                                 "-a", account.pw_name], capture_output=True, timeout=30,
                                env={"HOME": account.pw_dir, "PATH": "/usr/bin:/bin"}, check=False)
        key = result.stdout.decode().strip()
    except (OSError, UnicodeDecodeError, subprocess.TimeoutExpired) as exc:
        raise DemoError("The configured Keychain credential could not be read.") from exc
    if result.returncode or not key.startswith("sk-or-") or any(c.isspace() for c in key):
        raise DemoError("The configured Keychain credential is unavailable or invalid.")
    return key


def child_environment(info, catalogue, model, credential, *, autonomous=False):
    # Do not inherit arbitrary provider/tracing/Python settings or an old
    # zero-credential receipt pointer. Only this child receives the credential.
    return {**info["env"], "CASEPATH_MODEL_MODE": "deterministic_reference",
            "CASEPATH_SOURCE_COMMIT": info["head"], "CASEPATH_DB_PATH": str(info["data"] / "casepath.db"),
            "CASEPATH_ARTIFACT_REGISTRY_PATH": str(info["data"] / "artifact-registry"),
            "CASEPATH_LOCAL_STATIC_ROOT": str(info["capsule"] / "casepath-public"),
            "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING": "false", "LANGCHAIN_TRACING_V2": "false",
            "CASEPATH_AGENT_WORK_EXTERNAL_FACTS": "1", "CASEPATH_AGENT_WORK_DEMO": "1",
            "CASEPATH_AGENT_WORK_MODEL": model, "CASEPATH_AGENT_WORK_CATALOGUE": str(catalogue),
            "CASEPATH_AGENT_WORK_MAX_EXTERNAL_RUNS": "3", "CASEPATH_AGENT_WORK_MAX_PROVIDER_CALLS": "18",
            "CASEPATH_AGENT_WORK_TOTAL_COST_USD": "0.10", "CASEPATH_AGENT_WORK_RUN_COST_USD": "0.02",
            "OPENROUTER_API_KEY": credential, **({"CASEPATH_AUTONOMOUS_ENABLED": "1"} if autonomous else {})}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise DemoError("A local readiness endpoint attempted a redirect.")


def local_json(path):
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open("http://127.0.0.1:4173" + path, timeout=3) as response:
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise DemoError("A local readiness response exceeds its size limit.")
        return json.loads(raw)


def verified_run_grant(grant):
    """Validate the fixed additive allowance without accepting a new base policy."""
    try:
        fields = {"contract", "additional_runs", "base_policy_sha256", "prior_budget_sha256",
                  "prior_budget", "actor", "reason", "idempotency_key", "granted_at", "grant_sha256"}
        prior = grant["prior_budget"]
        base_sha = sha(canonical(POLICY))
        if (set(grant) != fields or grant["contract"] != "casepath.external-run-grant/1.0.0"
                or type(grant["additional_runs"]) is not int or grant["additional_runs"] != 1
                or grant["base_policy_sha256"] != base_sha
                or prior["base_policy_sha256"] != base_sha
                or any(prior[k] != POLICY[k] for k in POLICY)
                or prior["effective_max_runs"] != 3 or prior["runs_used"] != 3
                or prior["run_grant"] is not None
                or grant["prior_budget_sha256"] != sha(canonical(prior))
                or grant["grant_sha256"] != sha(canonical({k:v for k,v in grant.items() if k != "grant_sha256"}))):
            raise ValueError
        return grant["grant_sha256"]
    except (KeyError, TypeError, ValueError):
        raise DemoError("The extra review allowance has no valid preserved approval receipt.") from None


def verified_autonomous_policy(policy):
    """The mode activation changes workflow admission, never lifetime caps."""
    try:
        fields = {"contract", "base_policy_sha256", "prior_budget_sha256", "prior_budget", "actor", "reason",
                  "idempotency_key", "activated_at", "max_calls_per_workflow", "workflow_cost_limit_usd", "policy_sha256"}
        prior = policy["prior_budget"]
        base_sha = sha(canonical(POLICY))
        if (set(policy) != fields or policy["contract"] != "casepath.autonomous-budget-policy/1.0.0"
                or policy["base_policy_sha256"] != base_sha or prior["base_policy_sha256"] != base_sha
                or any(prior[k] != v for k, v in POLICY.items()) or "autonomous_policy" in prior
                or prior["in_flight"] is not False
                or policy["prior_budget_sha256"] != sha(canonical(prior))
                or type(policy["max_calls_per_workflow"]) is not int or policy["max_calls_per_workflow"] != 2
                or policy["workflow_cost_limit_usd"] != POLICY["run_cost_limit_usd"]
                or datetime.fromisoformat(policy["activated_at"]).utcoffset() != timezone.utc.utcoffset(None)
                or any(not isinstance(policy[k], str) or not policy[k].strip() or not policy[k].isprintable()
                       for k in ("actor", "reason", "idempotency_key"))
                or policy["policy_sha256"] != sha(canonical({k: v for k, v in policy.items() if k != "policy_sha256"}))):
            raise ValueError
        return policy["policy_sha256"]
    except (KeyError, TypeError, ValueError):
        raise DemoError("The autonomous profile has no valid preserved budget activation.") from None


def verified_autonomous_capacity_grant(grant):
    """Verify the fixed extension and the frozen base allowance it preserves."""
    try:
        fields = {"contract", "additional_workflows", "additional_provider_calls", "base_policy_sha256",
                  "autonomous_policy_sha256", "prior_budget_sha256", "prior_budget", "prior_workflows",
                  "actor", "reason", "idempotency_key", "granted_at", "grant_sha256"}
        prior, roster = grant["prior_budget"], grant["prior_workflows"]
        base_sha = sha(canonical(POLICY))
        if (set(grant) != fields or grant["contract"] != "casepath.autonomous-capacity-grant/1.0.0"
                or any(type(grant[k]) is not int or grant[k] != v for k, v in
                       (("additional_workflows", 3), ("additional_provider_calls", 6)))
                or grant["base_policy_sha256"] != base_sha or prior["base_policy_sha256"] != base_sha
                or any(prior[k] != v for k, v in POLICY.items())
                or verified_autonomous_policy(prior["autonomous_policy"]) != grant["autonomous_policy_sha256"]
                or prior["autonomous_capacity_grant"] is not None
                or type(prior["provider_calls_used"]) is not int or prior["provider_calls_used"] not in (17, 18)
                or any(type(prior[k]) is not int or prior[k] != v for k, v in
                       (("effective_autonomous_max_provider_calls", 18),
                        ("autonomous_grant_workflows_used", 0), ("autonomous_grant_provider_calls_used", 0)))
                or prior["in_flight"] is not False or prior["automatic_retry"] is not False
                or prior["autonomous_can_start"] is not False or prior["autonomous_reason"] != "call_limit_reached"
                or grant["prior_budget_sha256"] != sha(canonical(prior))
                or type(prior["autonomous_provider_calls_used"]) is not int
                or not 0 <= prior["autonomous_provider_calls_used"] <= 18
                or not isinstance(roster, list) or type(prior["autonomous_workflows_used"]) is not int
                or len(roster) != prior["autonomous_workflows_used"] or len(roster) > 18
                or any(set(item) != {"workflow_id", "workflow_sha256"}
                       or not isinstance(item["workflow_id"], str) or not 1 <= len(item["workflow_id"]) <= 180
                       or re.fullmatch(r"[0-9a-f]{64}", item["workflow_sha256"]) is None for item in roster)
                or [item["workflow_id"] for item in roster] != sorted({item["workflow_id"] for item in roster})
                or datetime.fromisoformat(grant["granted_at"]).utcoffset() != timezone.utc.utcoffset(None)
                or any(not isinstance(grant[k], str) or not minimum <= len(grant[k]) <= maximum
                       or grant[k] != grant[k].strip() or not grant[k].isprintable()
                       for k, minimum, maximum in (("actor", 1, 180), ("reason", 1, 2000), ("idempotency_key", 8, 128)))
                or grant["grant_sha256"] != sha(canonical({k:v for k,v in grant.items() if k != "grant_sha256"}))):
            raise ValueError
        money = [Decimal(prior[k]) for k in ("actual_cost_usd", "reserved_cost_usd", "remaining_cost_usd")]
        if any(not v.is_finite() or v < 0 for v in money) or sum(money) != Decimal("0.10") or money[2] < Decimal("0.06"):
            raise ValueError
        return grant["grant_sha256"]
    except (DemoError, AttributeError, KeyError, TypeError, ValueError, InvalidOperation):
        raise DemoError("The autonomous capacity extension has no valid preserved grant receipt.") from None


def verified_autonomous_capacity(budget):
    """Check native usage and return only the public extension identity/counters."""
    try:
        nine = budget.get("original_nine_grant")
        if nine is not None:
            # Reuse the native pin/bounds validator without constructing a
            # database, provider or approval application. The complete ledger
            # ancestry is independently validated by WorkStore readback.
            native_root = str(Path(__file__).resolve().parents[2] / "casepath-api")
            sys.path.insert(0,native_root)
            try:
                from casepath_api.agent_work.store import WorkStore, WorkStoreError
                try:
                    WorkStore.validate_original_nine_preflight(nine["preflight"])
                except WorkStoreError:
                    raise ValueError from None
            finally:
                sys.path.remove(native_root)
            prior, command = nine["prior_budget"], nine["approval_command"]
            new_works, new_calls = budget["original_nine_workflows_used"], budget["original_nine_provider_calls_used"]
            if (nine["contract"] != "casepath.original-nine-capacity-grant/1.0.0"
                    or nine["grant_sha256"] != sha(canonical({k:v for k,v in nine.items() if k != "grant_sha256"}))
                    or prior != nine["preflight"]["prior_budget"]
                    or nine["prior_budget_sha256"] != sha(canonical(prior))
                    or command["expected_budget_sha256"] != nine["prior_budget_sha256"]
                    or command["acknowledged_preflight_sha256"] != nine["preflight"]["preflight_sha256"]
                    or not isinstance(command["human_approval_reference"],str) or not command["human_approval_reference"].strip()
                    or command["monetary_option"] not in {"existing_010","new_018_total_022"}
                    or nine["effective_total_cost_limit_usd"] != ("0.10" if command["monetary_option"] == "existing_010" else "0.22")
                    or budget["effective_total_cost_limit_usd"] != nine["effective_total_cost_limit_usd"]
                    or nine["max_new_workflow_reservations_usd"] != "0.18"
                    or type(new_works) is not int or not 0 <= new_works <= 9
                    or type(new_calls) is not int or not new_works <= new_calls <= 2 * new_works
                    or budget["effective_autonomous_max_provider_calls"] != 42
                    or prior["provider_calls_used"] != 24 or prior["effective_autonomous_max_provider_calls"] != 24
                    or budget["autonomous_capacity_grant"] != prior["autonomous_capacity_grant"]
                    or nine["old_capacity_grant_sha256"] != prior["autonomous_capacity_grant"]["grant_sha256"]
                    or nine["base_policy_sha256"] != sha(canonical(POLICY))
                    or nine["autonomous_policy_sha256"] != verified_autonomous_policy(prior["autonomous_policy"])):
                raise ValueError
            old_budget = dict(budget)
            old_budget.pop("original_nine_grant")
            old_budget["effective_autonomous_max_provider_calls"] = 24
            for key,count in (("provider_calls_used",new_calls),("autonomous_provider_calls_used",new_calls),("autonomous_workflows_used",new_works)):
                old_budget[key] -= count
            selected = verified_autonomous_capacity(old_budget)
            selected.update(original_nine_grant_sha256=nine["grant_sha256"],
                effective_autonomous_max_provider_calls=42, original_nine_workflows_used=new_works,
                original_nine_provider_calls_used=new_calls, effective_total_cost_limit_usd=budget["effective_total_cost_limit_usd"])
            return selected
        grant = budget.get("autonomous_capacity_grant")
        effective = budget.get("effective_autonomous_max_provider_calls", 18)
        workflows = budget.get("autonomous_grant_workflows_used", 0)
        calls = budget.get("autonomous_grant_provider_calls_used", 0)
        if (type(effective) is not int or effective != (24 if grant else 18)
                or type(workflows) is not int or not 0 <= workflows <= 3
                or type(calls) is not int or not workflows <= calls <= 2 * workflows
                or (grant is None and (workflows or calls))):
            raise ValueError
        grant_sha = verified_autonomous_capacity_grant(grant) if grant is not None else None
        if grant is not None:
            prior = grant["prior_budget"]
            if (budget["autonomous_policy"] != prior["autonomous_policy"]
                    or any(budget[k] != v for k, v in POLICY.items())
                    or budget["provider_calls_used"] != prior["provider_calls_used"] + calls
                    or budget["autonomous_provider_calls_used"] != prior["autonomous_provider_calls_used"] + calls
                    or budget["autonomous_workflows_used"] != prior["autonomous_workflows_used"] + workflows):
                raise ValueError
        return {"autonomous_capacity_grant_sha256": grant_sha, "effective_autonomous_max_provider_calls": effective,
                "autonomous_grant_workflows_used": workflows, "autonomous_grant_provider_calls_used": calls}
    except (DemoError, KeyError, TypeError, ValueError):
        raise DemoError("The autonomous capacity usage differs from its sealed extension.") from None


def readiness(info, model, request=local_json, *, autonomous=False):
    health = request("/healthz")
    deploy = request("/deployment.json")
    api = request("/deployment-health")
    ready = request("/readyz")
    caps = request("/api/agent-work/v1/capabilities")
    try:
        budget = caps["external_budget"]
        auto = request("/api/claim-loops/v1/autonomous/status") if autonomous else None
        if autonomous:
            # This later projection may include work resumed since the earlier
            # capability read. Compare immutable identities, not moving counts.
            if (auto["enabled"] is not True or auto["provider_ready"] is not True
                    or auto["policy_id"] != "casepath.autonomous-local/1.0.0"
                    or auto["automatic_inference_retry"] is not False
                    or any(auto["limits"][k] != budget[k] for k in POLICY)
                    or auto["limits"]["base_policy_sha256"] != budget["base_policy_sha256"]
                    or auto["limits"].get("autonomous_capacity_grant") != budget.get("autonomous_capacity_grant")
                    or auto["limits"].get("effective_autonomous_max_provider_calls", 18) != budget.get("effective_autonomous_max_provider_calls", 18)):
                raise DemoError("The autonomous service is unavailable or differs from the shared budget.")
            budget = auto["limits"]
        if (any(value.get("source_commit") != info["head"] for value in (health, deploy, api))
                or health.get("source_commit_aligned") is not True
                or health.get("source_commit_conflict") is not False
                or deploy.get("alignment_eligible") is not True
                or ready.get("status") != "ready"
                or ready.get("model_budget", {}).get("credential_configured") is not True
                or caps.get("external_configuration_status") != "ready"
                or "external_facts" not in caps.get("facts_workers", [])
                or caps["external"]["model"] != model
                or Decimal(caps["external"]["cost_limit_usd"]) != Decimal("0.02")
                or budget["scope"] != "persistent_local_demo"
                or any(budget[k] != POLICY[k] for k in ("max_runs", "max_provider_calls"))
                or any(Decimal(budget[k]) != Decimal(POLICY[k]) for k in ("total_cost_limit_usd", "run_cost_limit_usd"))
                or budget["automatic_retry"] is not False):
            raise DemoError("The demo source, provider capability or persisted budget does not match its profile.")
        reasons = {None, "provider_cost_bound_exceeded", "provider_outcome_pending", "run_limit_reached",
                   "call_limit_reached", "cost_limit_reached"}
        if (any(type(budget[k]) is not int or budget[k] < 0
                for k in ("runs_used", "provider_calls_used", "unknown_calls"))
                or type(budget["can_start"]) is not bool or budget["reason"] not in reasons):
            raise DemoError("The demo usage projection has invalid public fields.")
        for key in ("actual_cost_usd", "reserved_cost_usd", "remaining_cost_usd"):
            amount = Decimal(budget[key])
            if not amount.is_finite() or amount < 0:
                raise DemoError("The demo usage projection has invalid cost fields.")
        effective = budget.get("effective_max_runs", POLICY["max_runs"])
        grant = budget.get("run_grant")
        if (type(effective) is not int or effective not in (3, 4)
                or (grant is None) != (effective == 3)
                or budget.get("base_policy_sha256", sha(canonical(POLICY))) != sha(canonical(POLICY))):
            raise DemoError("The effective review allowance differs from its preserved base policy.")
        grant_sha = verified_run_grant(grant) if grant is not None else None
        # Only fixed public fields leave this function; no environment or raw
        # provider message is copied into a receipt.
        selected = {k: budget[k] for k in (*POLICY, "runs_used", "provider_calls_used", "actual_cost_usd",
                    "reserved_cost_usd", "remaining_cost_usd", "unknown_calls", "can_start", "reason")}
        selected.update(effective_max_runs=effective, run_grant_sha256=grant_sha)
        selected.update(verified_autonomous_capacity(budget))
        result = {"source_commit": info["head"], "model": model, "budget": selected,
                  "credential_configured": True, "automatic_provider_start": autonomous}
        if autonomous:
            config = auto["model"]
            policy_sha = verified_autonomous_policy(budget["autonomous_policy"])
            if (config["model"] != model or config["catalogue_entry_sha256"] != info["autonomous_catalogue_entry_sha256"]
                    or config["protocol"] != "strict_json_schema" or config["adapter_version"] != "casepath.autonomous-model/1.0.0"
                    or any(type(config[k]) is not int or config[k] != v for k, v in
                           (("max_request_bytes", 64000), ("max_output_tokens", 3500), ("max_calls_per_workflow", 2)))
                    or any(type(budget[k]) is not int or budget[k] < 0 for k in
                           ("autonomous_workflows_used", "autonomous_provider_calls_used"))
                    or type(budget["autonomous_can_start"]) is not bool or budget["autonomous_reason"] not in reasons - {"run_limit_reached"}):
                raise DemoError("The autonomous model or usage bounds differ from the explicit profile.")
            selected.update({k: budget[k] for k in ("autonomous_workflows_used", "autonomous_provider_calls_used", "autonomous_can_start", "autonomous_reason")})
            selected["autonomous_policy_sha256"] = policy_sha
            result["autonomous_model_sha256"] = sha(canonical(config))
        return result
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise DemoError("The demo readiness projection is incomplete.") from exc


def write_receipt(path, payload):
    payload = {**payload, "receipt_sha256": sha(canonical(payload))}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, "wb") as stream:
        stream.write(canonical(payload) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def private_directory(path):
    if path.is_symlink():
        raise DemoError("The demo directory cannot be a symlink.")
    path.mkdir(mode=0o700, exist_ok=True)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise DemoError("The demo directory must be private to the current account.")


def grant_extra_run(repository, *, expected_budget_sha256, actor, reason, idempotency_key):
    """Explicit offline operation. Never reads credentials or starts a server."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_budget_sha256):
        raise DemoError("Provide the exact saved budget hash for the approved extra review.")
    runtime = repository / ".runtime/casepath-dev-v2"
    if any(path.is_symlink() or not path.is_dir() for path in (repository / ".runtime", runtime)):
        raise DemoError("Prepare and boot the normal local runtime first.")
    request = {"expected_budget_sha256": expected_budget_sha256, "actor": actor,
               "reason": reason, "idempotency_key": idempotency_key}
    with ExitStack() as stack:
        acquire_lease(runtime / "environment.lock", stack)
        acquire_lease(repository / ".runtime/casepath-data-v1.lock", stack)
        reserve_origin(stack)
        info = preflight(repository)
        database = info["data"] / "agent-work-v1.sqlite3"
        try:
            fd = os.open(database, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            stack.callback(os.close, fd)
            file_info = os.fstat(fd)
            if not stat.S_ISREG(file_info.st_mode) or file_info.st_nlink != 1:
                raise OSError
        except OSError:
            raise DemoError("The existing work database is unavailable; no allowance was created.") from None
        command = [str(info["python"]), "-I", "-B", "-P", "-c",
                   'import json,sys; sys.path.insert(0,sys.argv[1]); '
                   'from casepath_api.agent_work.store import WorkStore; '
                   'result=WorkStore(sys.argv[2]).grant_one_external_run(**json.loads(sys.argv[3])); '
                   'print(json.dumps(result,sort_keys=True,separators=(",",":")))',
                   str(info["capsule"] / "casepath-api"), str(database), canonical(request).decode()]
        try:
            grant = json.loads(run_checked(command, cwd=repository, env=info["env"]))
            verified_run_grant(grant)
            if any(grant[k] != request[k] for k in ("actor", "reason", "idempotency_key")) or grant["prior_budget_sha256"] != expected_budget_sha256:
                raise ValueError
        except (DemoError, KeyError, TypeError, ValueError):
            raise DemoError("The allowance result could not be confirmed. Inspect its saved receipt before retrying; no provider request was started.") from None
        return {"contract": "casepath.explicit-agent-demo-allowance/1.0.0", "source_commit": info["head"],
                "source_manifest_sha256": info["manifest_sha256"], "grant": grant,
                "provider_requests_started": 0}


def grant_autonomous_capacity(repository, *, expected_budget_sha256, actor, reason, idempotency_key):
    """Record the one three-workflow extension offline, then replay its ledger."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_budget_sha256):
        raise DemoError("Provide the exact saved budget hash for the autonomous capacity extension.")
    runtime = repository / ".runtime/casepath-dev-v2"
    if any(path.is_symlink() or not path.is_dir() for path in (repository / ".runtime", runtime)):
        raise DemoError("Prepare and boot the normal local runtime first.")
    request = {"expected_budget_sha256": expected_budget_sha256, "actor": actor,
               "reason": reason, "idempotency_key": idempotency_key}
    with ExitStack() as stack:
        acquire_lease(runtime / "environment.lock", stack)
        acquire_lease(repository / ".runtime/casepath-data-v1.lock", stack)
        reserve_origin(stack)
        info = preflight(repository)
        database = info["data"] / "agent-work-v1.sqlite3"
        try:
            fd = os.open(database, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            stack.callback(os.close, fd)
            metadata = os.fstat(fd)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise OSError
        except OSError:
            raise DemoError("The existing work database is unavailable; no capacity extension was created.") from None
        command = [str(info["python"]), "-I", "-B", "-P", "-c",
                   'import json,sys; sys.path.insert(0,sys.argv[1]); '
                   'from casepath_api.agent_work.store import WorkStore; '
                   'store=WorkStore(sys.argv[2]); '
                   'result=store.grant_three_autonomous_workflows(**json.loads(sys.argv[3])); store.close(); '
                   'print(json.dumps(result,sort_keys=True,separators=(",",":")))',
                   str(info["capsule"] / "casepath-api"), str(database), canonical(request).decode()]
        try:
            grant = json.loads(run_checked(command, cwd=repository, env=info["env"]))
            grant_sha = verified_autonomous_capacity_grant(grant)
            if any(grant[k] != request[k] for k in ("actor", "reason", "idempotency_key")) or grant["prior_budget_sha256"] != expected_budget_sha256:
                raise ValueError
            budget = read_only_provider_budget(info)
            if (budget["autonomous_capacity_grant"] != grant
                    or verified_autonomous_capacity(budget)["autonomous_capacity_grant_sha256"] != grant_sha):
                raise ValueError
        except (DemoError, KeyError, TypeError, ValueError):
            raise DemoError("The capacity extension result could not be confirmed. Inspect its saved receipt before retrying; no provider request was started.") from None
        return {"contract": "casepath.explicit-autonomous-capacity-grant/1.0.0", "source_commit": info["head"],
                "source_manifest_sha256": info["manifest_sha256"], "normal_boot_id": info["normal_boot_id"],
                "normal_boot_file_sha256": info["normal_boot_file_sha256"], "grant": grant, "budget": budget,
                "provider_requests_started": 0}


def serve(repository, catalogue, model, endpoints=None, *, autonomous=False):
    runtime = repository / ".runtime/casepath-dev-v2"
    for directory in (repository / ".runtime", runtime):
        if directory.is_symlink() or not directory.is_dir():
            raise DemoError("Prepare and boot the normal local runtime first.")
    with ExitStack() as stack:
        leases = [acquire_lease(runtime / "environment.lock", stack),
                  acquire_lease(repository / ".runtime/casepath-data-v1.lock", stack)]
        listener = reserve_origin(stack)
        info = preflight(repository)
        catalogue_raw = catalogue_snapshot(catalogue, model)
        selected = next(row for row in json.loads(catalogue_raw)["catalogue"]["data"] if row["id"] == model)
        endpoint_raw = endpoint_snapshot(endpoints or catalogue.with_name("endpoints.json"), selected, autonomous=autonomous)
        if autonomous:
            info["autonomous_catalogue_entry_sha256"] = sha(canonical(selected))
        demo_root = repository / ".runtime/casepath-openrouter-demo"
        private_directory(demo_root)
        launch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
        launch = demo_root / launch_id
        private_directory(launch)
        snapshot = launch / "catalogue.json"
        fd = os.open(snapshot, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
        with os.fdopen(fd, "wb") as stream:
            stream.write(catalogue_raw)
        endpoint_copy = launch / "endpoints.json"
        fd = os.open(endpoint_copy, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
        with os.fdopen(fd, "wb") as stream:
            stream.write(endpoint_raw)
        env = child_environment(info, snapshot, model, keychain_credential(), autonomous=autonomous)
        command = [str(info["python"]), "-I", "-B", "-P", "-m", "uvicorn", "casepath_api.app:app",
                   "--app-dir", str(info["capsule"] / "casepath-api"), "--fd", str(listener.fileno()),
                   "--host", "127.0.0.1", "--port", "4173", "--no-access-log", "--log-level", "warning"]
        child = subprocess.Popen(command, cwd=repository, env=env, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 pass_fds=(*leases, listener.fileno()))
        env.pop("OPENROUTER_API_KEY", None)
        receipt = {"contract": "casepath.explicit-agent-demo-boot/1.0.0", "launch_id": launch_id,
                   "source_commit": info["head"], "source_manifest_sha256": info["manifest_sha256"],
                   "execution_root": str(info["capsule"]), "normal_boot_id": info["normal_boot_id"],
                   "normal_boot_file_sha256": info["normal_boot_file_sha256"],
                   "catalogue_file_sha256": sha(catalogue_raw), "endpoint_file_sha256": sha(endpoint_raw),
                   "url": "http://127.0.0.1:4173/",
                   "profile": "bounded_autonomous_claims" if autonomous else "manual_openrouter_facts_role", "model": model, "policy": POLICY,
                   "credential_source": "macOS Keychain", "credential_names": ["OPENROUTER_API_KEY"],
                   "process": {"pid": child.pid, "argv": command, "workers": 1},
                   "normal_boot_history_modified": False, "provider_requests_started_by_launcher": 0}
        if autonomous:
            receipt.update(automatic_saved_work_resume=True,
                           provider_start_scope="the server may resume saved workflows under the persistent budget")
        def stop_signal(_signal, _frame):
            raise KeyboardInterrupt
        prior_signals = {sig: signal.signal(sig, stop_signal) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            observed = None
            for _ in range(240):
                if child.poll() is not None:
                    raise DemoError("The demo server exited before readiness; inspect saved provider intents before restarting.")
                try:
                    observed = readiness(info, model, autonomous=True) if autonomous else readiness(info, model)
                    break
                except DemoError:
                    raise
                except (OSError, ValueError):
                    time.sleep(0.25)
            if observed is None:
                raise DemoError("The demo server did not become ready.")
            # Historical verifier includes a live interpreter/venv/capsule
            # recheck. Reuse it after startup without the child's credential.
            run_checked([str(info["python"]), "-I", "-S", "-B", "-P",
                         str(info["capsule"] / "casepath/tools/validate_local_runtime_history.py"),
                         "--verify-only", str(runtime), str(info["data"]), str(repository)],
                        cwd=repository, env=info["env"])
            write_receipt(launch / "ready.json", {**receipt, "ready_at_utc": datetime.now(timezone.utc).isoformat(),
                          "readiness": observed})
            label = "autonomous claims" if autonomous else "manual facts"
            print(f"CasePath {label} demo: http://127.0.0.1:4173/\nReceipt: {launch / 'ready.json'}", flush=True)
            child.wait()
            if child.returncode:
                raise DemoError("The demo server stopped with an error; inspect saved work before retrying a run.")
        except KeyboardInterrupt:
            pass
        finally:
            final = None
            if child.poll() is None:
                try:
                    final = readiness(info, model, autonomous=True) if autonomous else readiness(info, model)
                except Exception:
                    pass
                child.terminate()
                try:
                    child.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            write_receipt(launch / "stopped.json", {**receipt, "stopped_at_utc": datetime.now(timezone.utc).isoformat(),
                          "exit_code": child.returncode,
                          "last_observed_readiness": final, "outcome_scope": "last observed before shutdown; run journals remain authority"})
            for sig, handler in prior_signals.items():
                signal.signal(sig, handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="Exact concrete model ID from the local catalogue")
    parser.add_argument("--catalogue", type=Path, help="Locally acquired catalogue snapshot; no download occurs here")
    parser.add_argument("--endpoints", type=Path, help="Recent model endpoint snapshot; defaults to endpoints.json beside the catalogue")
    parser.add_argument("--autonomous", action="store_true", help="Enable durable autonomous intake under the preserved budget and any sealed capacity extension")
    parser.add_argument("--grant-one-extra-run", action="store_true", help="Record one explicitly approved extra review; no server or provider request starts")
    parser.add_argument("--grant-three-autonomous-workflows", action="store_true", help="Record the single three-workflow/six-call extension after base exhaustion; dollar caps unchanged, no inference starts")
    parser.add_argument("--expected-budget-sha256")
    parser.add_argument("--actor")
    parser.add_argument("--reason")
    parser.add_argument("--idempotency-key")
    args = parser.parse_args(argv)
    grant_args = (args.expected_budget_sha256, args.actor, args.reason, args.idempotency_key)
    if args.grant_one_extra_run and args.grant_three_autonomous_workflows:
        parser.error("Choose only one separate allowance operation.")
    if args.grant_one_extra_run or args.grant_three_autonomous_workflows:
        if not all(grant_args) or any((args.model, args.catalogue, args.endpoints, args.autonomous)):
            parser.error("An extra review requires its budget hash, actor, reason and idempotency key, without serving options.")
    elif not args.model or any(grant_args):
        parser.error("Choose a model to serve, or the separate explicit allowance operation.")
    repository = Path(__file__).resolve().parents[2]
    catalogue = args.catalogue or repository / ".runtime/casepath-openrouter-demo/catalogue.json"
    try:
        if args.grant_one_extra_run:
            result = grant_extra_run(repository, expected_budget_sha256=args.expected_budget_sha256,
                                     actor=args.actor, reason=args.reason, idempotency_key=args.idempotency_key)
            print(canonical(result).decode())
        elif args.grant_three_autonomous_workflows:
            result = grant_autonomous_capacity(repository, expected_budget_sha256=args.expected_budget_sha256,
                                               actor=args.actor, reason=args.reason, idempotency_key=args.idempotency_key)
            print(canonical(result).decode())
        else:
            serve(repository, catalogue.absolute(), args.model, args.endpoints.absolute() if args.endpoints else None,
                  **({"autonomous": True} if args.autonomous else {}))
    except DemoError as exc:
        print(f"CasePath demo: {exc}", file=sys.stderr)
        return 2
    except Exception:
        # Do not surface arbitrary child/provider/credential exception text.
        print("CasePath demo: local startup failed; no automatic provider retry was made.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
