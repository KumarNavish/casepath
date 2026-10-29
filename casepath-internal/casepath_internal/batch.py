"""Bring real case files into a running CasePath and work through them one case at a time.

    python -m casepath_internal.batch import <folder> [--workflow <id>] [--url http://127.0.0.1:8080]
    python -m casepath_internal.batch next [--synthetic] [--url ...]
    python -m casepath_internal.batch retry [--workflow <id>] [--url ...]
    python -m casepath_internal.batch trace <case id or its last 8 characters> [--url ...]

``import`` creates one case per PDF in the folder (titled by its file name) and uploads the file; with ``--workflow``
the case worker's choice of process is set instead of routing from the documents. ``next`` starts the next case that
has not been prepared and waits for it (with ``--synthetic``, the next synthetic case instead). ``retry`` runs the first case whose last run failed, was interrupted or found
no process, optionally choosing the process first; pages already read are not read again. Each command prints one
content-free line: run status, pages read, documents found in the dossier, where the case stands in its workflow, and
the tokens used. One case per command keeps an interactive session (such as Cloud Shell) active between cases.
``trace`` breaks a case's last run down by agent (turns, tokens, seconds, tools, delegations) and lists each fact and
document need with its status, check and origin, by id only, to see where a run spends its effort and what it missed.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time
import urllib.request
import uuid


def call(url, path, method="GET", body=None, raw=None, content_type=None):
    data, headers = None, {}
    if raw is not None:
        data, headers = raw, {"Content-Type": content_type}
    elif body is not None:
        data, headers = json.dumps(body).encode(), {"Content-Type": "application/json"}
    request = urllib.request.Request(url + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.loads(response.read() or b"null")


def upload(url, case_id, path):
    boundary = uuid.uuid4().hex
    content = path.read_bytes()
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
            f"Content-Type: application/pdf\r\n\r\n").encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return call(url, f"/api/cases/{case_id}/files", "POST", raw=body, content_type=f"multipart/form-data; boundary={boundary}")


def import_folder(url, folder, workflow=None):
    existing = {c["title"] for c in call(url, "/api/cases")["cases"]}
    created = 0
    for path in sorted(Path(folder).rglob("*.pdf")):
        title = path.stem
        if title in existing:
            continue
        case = call(url, "/api/cases", "POST", {"title": title, "intake": {"source": "imported"}})
        if workflow:
            call(url, f"/api/cases/{case['id']}/workflow", "PUT", {"workflow_id": workflow})
        upload(url, case["id"], path)
        created += 1
    print(json.dumps({"imported": created, "skipped_existing": len(existing)}))


def line(url, case, run):
    detail = call(url, f"/api/cases/{case['id']}")
    files = detail["files"]
    result = run.get("result") or {}
    evaluation = detail.get("evaluation") or {}
    usage = result.get("usage") or []
    learned = result.get("learned") or {}
    outcomes = {}
    for row in learned.get("outcomes") or []:
        outcomes[row["outcome"]] = outcomes.get(row["outcome"], 0) + 1
    return {"case": case["id"][-8:], "status": run["status"], "error_kind": (run.get("error") or "").split(":", 1)[0] or None,
            "pages": sum(f["extraction"].get("pages") or 0 for f in files),
            "pages_read_from_images": sum(len(f["extraction"].get("pages_transcribed") or []) for f in files),
            "pages_unread": sum(len(f["extraction"].get("pages_without_text") or []) for f in files),
            "documents_in_dossiers": sum(len(f["extraction"].get("segments") or []) for f in files),
            "routing": (run.get("routing") or {}).get("status"), "workflow": run.get("workflow_id"),
            "current_step": (evaluation.get("current") or {}).get("step"), "outcome": (evaluation.get("outcome") or {}).get("id"),
            "facts_accepted": sum(1 for f in result.get("facts", []) if f.get("verdict") == "accepted"),
            "documents_present": sum(1 for d in evaluation.get("documents", []) if d["status"] == "present"),
            "documents_missing": sum(1 for d in evaluation.get("documents", []) if d["status"] == "missing" and d["required"] == "yes"),
            "knowledge_applied": sum(1 for k in (result.get("provenance") or {}).get("knowledge", []) if k.get("applied")),
            "knowledge_outcomes": outcomes, "knowledge_proposed": len(learned.get("proposals") or []),
            "knowledge_refinements": sum(1 for p in learned.get("proposals") or [] if p.get("action") == "refine"),
            "model_turns": len(usage), "input_tokens": sum(u.get("input_tokens", 0) for u in usage),
            "output_tokens": sum(u.get("output_tokens", 0) for u in usage)}


def trace(url, case_ref):
    """Where a run's effort went and what it found, by agent and by id; guarded as content-free."""
    from .scorecard import guard

    case = next(c for c in call(url, "/api/cases")["cases"] if c["id"] == case_ref or c["id"].endswith(case_ref))
    detail = call(url, f"/api/cases/{case['id']}")
    run = call(url, f"/api/runs/{detail['run']['id']}")
    result = run.get("result") or {}
    agents = {}
    for row in result.get("usage") or []:
        a = agents.setdefault(row.get("agent", "model"), {"turns": 0, "input_tokens": 0, "output_tokens": 0, "seconds": 0, "tools": {}})
        a["turns"] += 1
        a["input_tokens"] += row.get("input_tokens", 0)
        a["output_tokens"] += row.get("output_tokens", 0)
    started, order, rejected = {}, [], {}
    for event in run.get("events") or []:
        agent, kind = event.get("agent", "model"), event.get("kind", "")
        a = agents.setdefault(agent, {"turns": 0, "input_tokens": 0, "output_tokens": 0, "seconds": 0, "tools": {}})
        if kind == "agent.start":
            started[agent] = datetime.fromisoformat(event["at"])
        elif kind == "agent.end" and agent in started:
            a["seconds"] += round((datetime.fromisoformat(event["at"]) - started.pop(agent)).total_seconds())
        elif kind == "tool":
            a["tools"][event["tool"]] = a["tools"].get(event["tool"], 0) + 1
        elif kind == "delegate":
            order.append(event["to"])
        if kind.endswith(".rejected"):
            rejected[kind] = rejected.get(kind, 0) + 1
    process = {d["id"]: d for d in (detail.get("process") or {}).get("documents", [])}
    found = {d["document"]: d for d in result.get("documents") or []}
    documents = {}
    for d in (detail.get("evaluation") or {}).get("documents", []):
        need, row = process.get(d["document"], {}), found.get(d["document"], {})
        documents[d["document"]] = {"status": d["status"], "required": d["required"], "recorded": row.get("status"),
                                    "check": row.get("verdict"), "origin": "knowledge" if need.get("knowledge") else ("agent" if str(need.get("edit")).startswith("pb") else "case_worker")
                                    if need.get("edit") else "workflow"}
    print(json.dumps(guard({"case": case["id"][-8:], "status": run["status"], "agents": agents, "delegations": order,
                            "facts": {f["fact"]: [f["status"], f.get("verdict")] for f in result.get("facts") or []},
                            "documents": documents, "agent_edits": [e["op"] for e in result.get("agent_edits") or []],
                            "rejected": rejected}), indent=1))


def prepare(url, case, poll):
    run = call(url, f"/api/cases/{case['id']}/runs", "POST")
    while run["status"] in ("queued", "running"):
        time.sleep(poll)
        run = call(url, f"/api/runs/{run['id']}")
    print(json.dumps(line(url, case, run)))


def run_next(url, poll=5, synthetic=False):
    for case in call(url, "/api/cases")["cases"]:
        if bool((case.get("intake") or {}).get("synthetic")) != synthetic or case.get("run_status"):
            continue
        return prepare(url, case, poll)
    print(json.dumps({"next": None, "note": "every case has been prepared"}))


def retry(url, workflow=None, poll=5):
    for case in call(url, "/api/cases")["cases"]:
        if (case.get("intake") or {}).get("synthetic") or case.get("run_status") in (None, "queued", "running"):
            continue
        run = call(url, f"/api/cases/{case['id']}")["run"]
        if run["status"] == "completed" and run.get("workflow_id"):
            continue
        if workflow:
            call(url, f"/api/cases/{case['id']}/workflow", "PUT", {"workflow_id": workflow})
        return prepare(url, case, poll)
    print(json.dumps({"retry": None, "note": "no case needs another run"}))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="casepath_internal.batch")
    parser.add_argument("command", choices=["import", "next", "retry", "trace"])
    parser.add_argument("folder", nargs="?")
    parser.add_argument("--workflow")
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    args = parser.parse_args(argv)
    if args.command == "import":
        if not args.folder:
            sys.exit("import needs a folder")
        import_folder(args.url, args.folder, args.workflow)
    elif args.command == "retry":
        retry(args.url, args.workflow)
    elif args.command == "trace":
        if not args.folder:
            sys.exit("trace needs a case id")
        trace(args.url, args.folder)
    else:
        run_next(args.url, synthetic=args.synthetic)


if __name__ == "__main__":
    main()
