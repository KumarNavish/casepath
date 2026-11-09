"""Command line: serve the workspace or check a workflow catalogue.

    python -m casepath_internal serve [--host 127.0.0.1] [--port 8765]
    python -m casepath_internal seed <suite-dir>
    python -m casepath_internal check-catalogue <directory>
    python -m casepath_internal contract [--write]
    python -m casepath_internal purge --older-than-days <n> [--dry-run]

``contract`` prints the case API as OpenAPI (``--write`` saves it to docs/contracts/case-api.openapi.json). Another
implementation of the case service, or a gateway in front of it, can be checked against this contract; a test keeps
the saved contract and the code in step. ``seed`` loads synthetic cases (a benchmark suite) into ``CASEPATH_DATA_DIR`` for everyone to open; ``serve`` does the
same at start when ``CASEPATH_SEED_SUITE`` names a suite. Cases already there are kept. ``purge`` deletes every case of ``CASEPATH_DATA_DIR`` that has not changed
for the given number of days, with everything derived from it, and keeps a content-free deletion record for each.
"""
import argparse
import sys

from .workflows import Catalogue, CatalogueError


def main(argv=None):
    parser = argparse.ArgumentParser(prog="casepath_internal")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    check = commands.add_parser("check-catalogue")
    check.add_argument("directory")
    contract = commands.add_parser("contract")
    contract.add_argument("--write", action="store_true")
    seed = commands.add_parser("seed")
    seed.add_argument("suite")
    purge = commands.add_parser("purge")
    purge.add_argument("--older-than-days", type=int, required=True)
    purge.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "seed":
        from .benchmark import seed as load
        from .config import load_settings
        from .store import CaseStore

        store = CaseStore(load_settings().data_dir)
        print(f"{load(store, args.suite)} synthetic case(s) added")
        store.close()
        return
    if args.command == "purge":
        import json
        from datetime import datetime, timedelta, timezone

        from .config import load_settings
        from .store import CaseStore

        before = (datetime.now(timezone.utc) - timedelta(days=args.older_than_days)).isoformat(timespec="seconds")
        print(json.dumps({"before": before, **CaseStore(load_settings().data_dir).purge(before, dry_run=args.dry_run)}))
        return
    if args.command == "contract":
        from .app import CONTRACT, case_api_contract

        text = case_api_contract()
        CONTRACT.write_text(text) if args.write else print(text, end="")
        return
    if args.command == "check-catalogue":
        try:
            catalogue = Catalogue.load(args.directory)
        except CatalogueError as error:
            sys.exit(f"catalogue invalid: {error}")
        for workflow in catalogue.workflows:
            print(f"{workflow['id']} {workflow['version']} {workflow['status']}: {len(workflow['steps'])} steps, "
                  f"{len(workflow['documents'])} documents, {len(workflow.get('open_questions', []))} open questions")
        return
    import os

    import uvicorn
    from .app import create_app
    if os.environ.get("CASEPATH_SEED_SUITE"):
        main(["seed", os.environ["CASEPATH_SEED_SUITE"]])
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
