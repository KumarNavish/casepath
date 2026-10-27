"""Command line: serve the workspace or check a workflow catalogue.

    python -m casepath_internal serve [--host 127.0.0.1] [--port 8765]
    python -m casepath_internal check-catalogue <directory>
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
    args = parser.parse_args(argv)
    if args.command == "check-catalogue":
        try:
            catalogue = Catalogue.load(args.directory)
        except CatalogueError as error:
            sys.exit(f"catalogue invalid: {error}")
        for workflow in catalogue.workflows:
            print(f"{workflow['id']} {workflow['version']} {workflow['status']}: {len(workflow['steps'])} steps, "
                  f"{len(workflow['documents'])} documents, {len(workflow.get('open_questions', []))} open questions")
        return
    import uvicorn
    from .app import create_app
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
