# The one cell of the "casepath frozen check" notebook, a read task before a deploy: does every frozen study case keep its
# item list under the build about to be deployed (casepath/quality/frozen.py)? Model-free and read only: the build's
# package is imported from its folder on the volume (uploaded there for the deploy notebook), the case store is copied
# from the volume's database into a temporary folder, the candidate's own startup runs on that copy as a deploy would run
# it (create_app: the Knowledge the build seeds, no network, no model, no volume), and only then are the hashes recomputed.
# Nothing on the volume changes. The startup needs the app's own packages (fastapi) in this notebook.
# It reads one notebook parameter, "check" (made with Edit > Add parameter), which must read
# "frozen <build> <files> <tree hash>" for the build on the volume, as for the deploy notebook (package.sh prints the tree
# hash). Empty or malformed: nothing happens. It prints the content-free receipt casepath.frozen-check/1: the build, each
# frozen case and study copy by id «equal» or «unequal» (and why), the counts. Any «unequal»: no deploy.
# Keep this as the notebook's only cell.
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import types

VOLUME = "FILL-IN: /Volumes/<catalog>/<schema>/<volume>"  # as in the deploy notebook: filled in here only, never in Git


def listing(root):
    return sorted(os.path.relpath(os.path.join(a, f), root) for a, _, fs in os.walk(root) for f in fs)


def tree(root):
    """The build's identity, as package.sh prints it: every file's path and bytes, app.yaml excluded."""
    h = hashlib.sha256()
    for rel in listing(root):
        if rel != "app.yaml":
            with open(os.path.join(root, rel), "rb") as handle:
                h.update(rel.encode() + b"\0" + handle.read())
    return h.hexdigest()[:12]


def check(volume, phrase):
    """The receipt for the build the phrase names, on a copy of the volume's case store."""
    match = re.fullmatch(r"frozen ([0-9a-f]{7,40}) (\d+) ([0-9a-f]{12})", (phrase or "").strip())
    assert match, "check must read: frozen <build> <files> <tree hash>"
    assert not volume.startswith("FILL-IN"), "fill in VOLUME in this cell first"
    build = f"{volume.rstrip('/')}/casepath-app-{match.group(1)}/casepath-app"
    assert os.path.isdir(build), "this build is not on the volume"
    assert len(listing(build)) == int(match.group(2)) and tree(build) == match.group(3), ("the volume copy differs", len(listing(build)), tree(build))
    database = f"{volume.rstrip('/')}/casepath.db"
    assert os.path.isfile(database), "no case store on the volume"
    scratch = tempfile.mkdtemp(prefix="casepath-frozen-check-")
    stub, bytecode = False, sys.dont_write_bytecode
    try:
        shutil.copyfile(database, os.path.join(scratch, "casepath.db"))  # read from a copy: the volume stays as it was
        for name in [m for m in sys.modules if m == "casepath" or m.startswith("casepath.")]:
            del sys.modules[name]  # a package an earlier run of this cell imported
        # no cache files beside the build's sources: the volume copy keeps its tree hash for the deploy notebook
        sys.dont_write_bytecode = True
        sys.path.insert(0, build)
        try:
            import httpx  # noqa: F401  (the package imports it for its model clients)
        except ImportError:  # nothing here calls a model or the network, so an empty module may stand in for it
            sys.modules["httpx"], stub = types.ModuleType("httpx"), True
        import casepath
        assert os.path.realpath(casepath.__file__).startswith(os.path.realpath(build) + os.sep), "the package did not come from the build"
        try:
            import fastapi  # noqa: F401  (the candidate's startup is the app's own: create_app)
        except ImportError:
            raise AssertionError("the candidate's startup needs the app's packages in this notebook (fastapi): install them, "
                                 "then run the cell again; nothing was checked") from None
        from casepath import parity
        from casepath.process.workflows import Catalogue
        from casepath.quality import frozen

        catalogue = Catalogue.load(f"{build}/catalogue" if os.path.isdir(f"{build}/catalogue") else None)  # as the app loads it
        out = frozen.preflight(scratch, catalogue, match.group(3), source=parity.source_tree()[0][:12])
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        sys.dont_write_bytecode = bytecode
        if build in sys.path:
            sys.path.remove(build)
        if stub:
            del sys.modules["httpx"]
    print("\n".join(frozen.lines(out)))
    print(json.dumps(out, ensure_ascii=False, sort_keys=True))
    return out


if "dbutils" in globals():
    check(VOLUME, dbutils.widgets.get("check"))  # noqa: F821  (Databricks provides dbutils)
