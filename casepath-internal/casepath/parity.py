"""What a deployment runs, as hashes, so two deployments can be compared without sharing any case data.

    python -m casepath parity [--catalogue <dir>] [--knowledge <json file>]

prints a JSON manifest: the hash of the package source tree actually imported (every file under casepath,
except caches, by relative path and content), the git commit when the package sits in a checkout, the hash of each
workflow file in the catalogue, the hash of each Knowledge item, the model provider and name, and every setting that
differs from the default. Secrets are never read: settings that hold credentials are not part of the configuration.
Two deployments run the same code when their ``source_tree_sha256`` values are equal.
"""
from dataclasses import asdict, fields
import hashlib
import json
from pathlib import Path
import subprocess

from .config import load_settings

PACKAGE = Path(__file__).resolve().parent


def source_tree(root=PACKAGE):
    """sha256 over the sorted (relative path, file sha256) pairs of the package, caches excluded."""
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}:
            rows.append(f"{path.relative_to(root).as_posix()} {hashlib.sha256(path.read_bytes()).hexdigest()}")
    return hashlib.sha256("\n".join(rows).encode()).hexdigest(), len(rows)


def git_commit(root=PACKAGE):
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", "."], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return {"commit": out.stdout.strip(), "package_modified": bool(dirty.stdout.strip())}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def non_default_settings(settings):
    default = load_settings({})
    out = {}
    for f in fields(settings):
        if f.name in {"model", "data_dir", "catalogue_dir"}:
            continue
        mine, theirs = getattr(settings, f.name), getattr(default, f.name)
        if mine != theirs:
            # who may sign in is personal data: only how many people are named
            out[f.name] = f"{len(mine)} named users" if f.name == "allowed_users" else sorted(mine) if isinstance(mine, frozenset) else mine
    if settings.model is not None:
        for key, value in asdict(settings.model).items():
            if key in {"endpoint", "deployment", "provider", "reading_deployment"}:
                continue
            out[f"model.{key}"] = list(value) if isinstance(value, tuple) else value
    return out


def manifest(settings=None, catalogue_dir=None, knowledge=None, extra=None):
    settings = settings or load_settings()
    tree, count = source_tree()
    catalogue = Path(catalogue_dir) if catalogue_dir else settings.catalogue_dir
    workflows = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(catalogue).glob("*.json"))} if catalogue else {}
    model = settings.model
    return {
        "format": "casepath.parity/1",
        "package": "casepath",
        "source_tree_sha256": tree, "source_files": count,
        "git": git_commit(),
        "workflows": workflows,
        # By content fields only, so use statistics and history do not change it (study review point 7).
        "knowledge": {k["id"]: {"version": k.get("version"), "status": k.get("status"),
                                "sha256": _digest({f: k.get(f) for f in ("kind", "family", "content", "applies_when", "status", "version")})}
                      for k in knowledge or []},
        "model": None if model is None else {"provider": model.provider, "name": model.deployment, "api": model.api,
                                             "reading": model.reading_deployment, "endpoint_host": model.endpoint.split("/")[2]},
        "interface_language_default": "de",
        "settings_not_default": non_default_settings(settings),
        **(extra or {}),
    }


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="python -m casepath parity")
    ap.add_argument("--catalogue", default=None)
    ap.add_argument("--knowledge", default=None, help="a JSON file with a list of Knowledge items")
    args = ap.parse_args(argv)
    knowledge = json.loads(Path(args.knowledge).read_text()) if args.knowledge else None
    print(json.dumps(manifest(catalogue_dir=args.catalogue, knowledge=knowledge), indent=1, ensure_ascii=False, default=str))
