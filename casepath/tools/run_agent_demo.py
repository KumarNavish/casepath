#!/usr/bin/env python3
"""Serve an explicitly enabled, bounded facts-role demo from a verified capsule.

Requires a clean committed checkout and a successful normal local boot of that
same commit. No provider request starts at launch. The normal launcher and its
zero-credential boot history remain unchanged.
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
    for root in (repository, capsule):
        run_checked([*isolated, str(root / "casepath/tools/casepath_release.py"), "verify"],
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
    return {"repository": repository, "runtime": runtime, "data": data, "capsule": capsule,
            "python": python, "head": head, "manifest_sha256": manifest_sha,
            "normal_boot_file_sha256": sha(boot_raw), "normal_boot_id": boot["boot_id"], "env": env}


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


def child_environment(info, catalogue, model, credential):
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
            "OPENROUTER_API_KEY": credential}


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


def readiness(info, model, request=local_json):
    health = request("/healthz")
    deploy = request("/deployment.json")
    api = request("/deployment-health")
    ready = request("/readyz")
    caps = request("/api/agent-work/v1/capabilities")
    try:
        budget = caps["external_budget"]
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
        # Only fixed public fields leave this function; no environment or raw
        # provider message is copied into a receipt.
        selected = {k: budget[k] for k in (*POLICY, "runs_used", "provider_calls_used", "actual_cost_usd",
                    "reserved_cost_usd", "remaining_cost_usd", "unknown_calls", "can_start", "reason")}
        return {"source_commit": info["head"], "model": model, "budget": selected,
                "credential_configured": True, "automatic_provider_start": False}
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


def serve(repository, catalogue, model):
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
        demo_root = repository / ".runtime/casepath-openrouter-demo"
        private_directory(demo_root)
        launch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
        launch = demo_root / launch_id
        private_directory(launch)
        snapshot = launch / "catalogue.json"
        fd = os.open(snapshot, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
        with os.fdopen(fd, "wb") as stream:
            stream.write(catalogue_raw)
        env = child_environment(info, snapshot, model, keychain_credential())
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
                   "catalogue_file_sha256": sha(catalogue_raw), "url": "http://127.0.0.1:4173/",
                   "profile": "manual_openrouter_facts_role", "model": model, "policy": POLICY,
                   "credential_source": "macOS Keychain", "credential_names": ["OPENROUTER_API_KEY"],
                   "process": {"pid": child.pid, "argv": command, "workers": 1},
                   "normal_boot_history_modified": False, "provider_requests_started_by_launcher": 0}
        def stop_signal(_signal, _frame):
            raise KeyboardInterrupt
        prior_signals = {sig: signal.signal(sig, stop_signal) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            observed = None
            for _ in range(240):
                if child.poll() is not None:
                    raise DemoError("The demo server exited before readiness; no provider run was started by the launcher.")
                try:
                    observed = readiness(info, model)
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
            print(f"CasePath manual facts demo: http://127.0.0.1:4173/\nReceipt: {launch / 'ready.json'}", flush=True)
            child.wait()
            if child.returncode:
                raise DemoError("The demo server stopped with an error; inspect saved work before retrying a run.")
        except KeyboardInterrupt:
            pass
        finally:
            final = None
            if child.poll() is None:
                try:
                    final = readiness(info, model)
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
    parser.add_argument("--model", required=True, help="Exact concrete model ID from the local catalogue")
    parser.add_argument("--catalogue", type=Path, help="Locally acquired catalogue snapshot; no download occurs here")
    args = parser.parse_args(argv)
    repository = Path(__file__).resolve().parents[2]
    catalogue = args.catalogue or repository / ".runtime/casepath-openrouter-demo/catalogue.json"
    try:
        serve(repository, catalogue.absolute(), args.model)
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
