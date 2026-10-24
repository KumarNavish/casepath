"""Provider-free browser fixture for the real review journal and its production UI.

The fixture starts two original synthetic intakes. It never fabricates reviewed
corrections, approvals, fragment versions, or source sufficiency. Tests perform
explicitly named Test handler actions against an isolated disposable database.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "casepath-api"), str(ROOT / "casepath-api/tests")]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=4194)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use an unprivileged loopback port.")
    if args.data_root.exists() and any(args.data_root.iterdir()):
        parser.error("The fixture requires a new empty data root.")
    args.data_root.mkdir(parents=True, exist_ok=True)
    os.environ["CASEPATH_AGENT_WORK_EXTERNAL_FACTS"] = "0"

    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    import uvicorn
    from test_workspace_claim_loop_v1 import _system
    from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root
    from casepath_api.claim_loop_router import create_claim_loop_router
    from casepath_api.workspace_packet_preview import create_packet_preview_router
    from casepath_api.agent_work.authority import ExistingCasePathAuthority
    from casepath_api.agent_work.service import AgentWorkService
    from casepath_api.agent_work.store import WorkStore
    from casepath_api.agent_work.api import create_agent_work_router
    from casepath_api.agent_desk_v1 import AgentDeskServiceV1, create_agent_desk_router

    storage, workspace, normal, facade = _system(
        args.data_root, corpus=PublicCorpus(default_workspace_corpus_root()))
    workspace.seed()
    cases = ("clm_f69b1747447bc221", "clm_0e538990cc6ba7ef")
    for claim_id in cases:
        state = workspace.store.recover(claim_id)
        workspace.start(claim_id, expected_revision=state["revision"],
                        idempotency_key="northstar.fixture.start." + claim_id,
                        process_model="casepath.causal-process/1.0.0")
    work = AgentWorkService(
        WorkStore(args.data_root / "work.sqlite3"),
        ExistingCasePathAuthority(lambda: workspace, lambda: facade),
        facts_worker=None, external_configuration_status="disabled")
    desk = AgentDeskServiceV1(workspace, work)
    app = FastAPI()
    app.include_router(create_packet_preview_router(lambda: workspace))
    app.include_router(create_agent_work_router(lambda: work))
    app.include_router(create_agent_desk_router(lambda: desk))
    app.include_router(create_claim_loop_router(
        lambda: storage, service_getter=lambda: normal,
        workspace_service_getter=lambda: workspace,
        workspace_loop_service_getter=lambda: facade,
        accepted_process_hook=lambda claim_id, result: desk.process_accepted(claim_id, result, dispatch=False)))

    @app.get("/healthz")
    def health():
        return {"status": "ok", "fixture": "review-northstar-v1",
                "model_mode": "deterministic_reference", "external_facts_enabled": False, "cases": list(cases),
                "review_actions_at_startup": 0}

    app.add_event_handler("shutdown", work.shutdown)
    app.mount("/", StaticFiles(directory=ROOT / "casepath", html=True), name="review-ui")
    print(json.dumps({"fixture": "review-northstar-v1", "port": args.port,
                      "data_root": str(args.data_root), "cases": cases,
                      "review_actions_at_startup": 0}), flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)

if __name__ == "__main__":
    main()
