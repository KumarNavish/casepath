"""One command line for everything: ``python -m casepath <command>``; ``python -m casepath`` lists them.

``contract`` prints the case API as OpenAPI (``--write`` saves it to docs/contracts/case-api.openapi.json); a test keeps
the saved contract and the code in step. ``seed`` loads synthetic cases (a benchmark suite) into ``CASEPATH_DATA_DIR``;
``serve`` does the same at start when ``CASEPATH_SEED_SUITE`` names a suite, keeping cases already there. ``purge``
deletes every case unchanged for the given number of days, with everything derived from it, and keeps a content-free
deletion record for each.
"""
import argparse
import importlib
import os
import sys

# Commands that live with their module: name -> (module, function, what it does).
DELEGATED = {
    "prepare": ("read.prepare", "main", "make prepared cases (text, page images) from files, without a model"),
    "reader-check": ("read.pdfread", "main", "compare the built-in PDF reader with pypdf/PDFium on PDFs (content-free)"),
    "batch": ("web.batch", "main", "import a folder into a running CasePath and prepare the cases one by one"),
    "benchmark": ("quality.benchmark", "main", "check, render or prepare a benchmark suite"),
    "evaluate": ("quality.evaluate", "main", "run, rescore, report or compare the benchmark against CasePath"),
    "scorecard": ("quality.scorecard", "main", "content-free scorecard of a case store"),
    "synthetic": ("quality.synthetic", "main", "make and judge synthetic cases inside Mobiliar"),
    "example": ("quality.examples", "main", "add the made-up example case to a case store"),
    "drawio": ("process.drawio", "main", "turn a draw.io process diagram into a draft workflow"),
    "mining": ("process.mining", "main", "reconstruct each real case's course and the pattern across cases"),
    "job": ("agents.core", "main", "run one agent job from JSON, as a queue worker would"),
    "parity": ("parity", "main", "what this deployment runs, as hashes, for comparison with another deployment"),
}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] in DELEGATED:
        module, function, _ = DELEGATED[argv[0]]
        return getattr(importlib.import_module(f"casepath.{module}"), function)(argv[1:])
    parser = argparse.ArgumentParser(prog="python -m casepath", description="CasePath: prepare cases with agents, grounded in quotes.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="<command>")
    serve = commands.add_parser("serve", help="the workspace and its API")
    serve.add_argument("--host", default="127.0.0.1")
    # The port a platform assigns (CASEPATH_PORT, PORT or DATABRICKS_APP_PORT), else 8765.
    serve.add_argument("--port", type=int, default=int(os.environ.get("CASEPATH_PORT") or os.environ.get("PORT")
                                                       or os.environ.get("DATABRICKS_APP_PORT") or 8765))
    commands.add_parser("check-catalogue", help="validate a workflow catalogue").add_argument("directory")
    commands.add_parser("contract", help="print (or --write) the case API as OpenAPI").add_argument("--write", action="store_true")
    commands.add_parser("seed", help="load a synthetic suite into the case store").add_argument("suite")
    purge = commands.add_parser("purge", help="delete cases unchanged for N days")
    purge.add_argument("--older-than-days", type=int, required=True)
    purge.add_argument("--dry-run", action="store_true")
    for name, (_, _, what) in DELEGATED.items():
        commands.add_parser(name, help=what, add_help=False)
    if not argv:
        parser.print_help()
        return
    args = parser.parse_args(argv)
    if args.command == "seed":
        from .config import load_settings
        from .quality.benchmark import seed as load
        from .web.store import CaseStore

        store = CaseStore(load_settings().data_dir)
        print(f"{load(store, args.suite)} synthetic case(s) added")
        store.close()
        return
    if args.command == "purge":
        import json
        from datetime import datetime, timedelta, timezone

        from .config import load_settings
        from .web.store import CaseStore

        before = (datetime.now(timezone.utc) - timedelta(days=args.older_than_days)).isoformat(timespec="seconds")
        print(json.dumps({"before": before, **CaseStore(load_settings().data_dir).purge(before, dry_run=args.dry_run)}))
        return
    if args.command == "contract":
        from .web.app import CONTRACT, case_api_contract

        text = case_api_contract()
        CONTRACT.write_text(text) if args.write else print(text, end="")
        return
    if args.command == "check-catalogue":
        from .process.workflows import Catalogue, CatalogueError

        try:
            catalogue = Catalogue.load(args.directory)
        except CatalogueError as error:
            sys.exit(f"catalogue invalid: {error}")
        for workflow in catalogue.workflows:
            print(f"{workflow['id']} {workflow['version']} {workflow['status']}: {len(workflow['steps'])} steps, "
                  f"{len(workflow['documents'])} documents, {len(workflow.get('open_questions', []))} open questions")
        return
    import uvicorn

    from .config import load_settings
    from .web.app import create_app, volume_mirror
    settings = load_settings()
    mirror = volume_mirror(settings) if settings.volume else None
    if mirror is not None:
        mirror.restore()  # the volume's cases first, so seeding never starts a second, empty store
    if os.environ.get("CASEPATH_SEED_SUITE"):
        main(["seed", os.environ["CASEPATH_SEED_SUITE"]])
    uvicorn.run(create_app(settings, mirror=mirror), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
