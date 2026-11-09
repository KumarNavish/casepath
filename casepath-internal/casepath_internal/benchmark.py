"""Benchmark cases with known answers, to show what CasePath gets right and wrong on cases it has never seen.

A benchmark case is one JSON file (``casepath.benchmark-case/1``): the documents of a made-up case, written as the
synthetic renderer expects them, and its truth:

- ``workflow``: the process family the case belongs to;
- ``facts``: the value of each workflow fact the documents settle, or null where the files leave it open;
- ``evidence``: for each settled fact, a sentence copied from the documents that settles it;
- ``outcome``: the process outcome the case reaches, or null when it stops at a question;
- ``documents``: each workflow document need as present or missing;
- ``case_documents``: documents this case needs beyond its workflow, which CasePath should find for itself, matched by
  keywords in the title CasePath gives them (``optional``: need not be asked for, but must not be claimed present);
  ``not_required``: documents it must not demand;
- ``deadlines``, ``next_actions`` (by keywords), and ``flags`` (text addressed to the AI, facts the files contradict).

The validator checks that a case is well formed, that its truth uses the workflow's own ids and values, and that every
evidence sentence occurs in the documents, so the truth itself rests on the files.

    python -m casepath_internal.benchmark check <suite-dir> [--catalogue <dir>]
"""
import argparse
import json
from pathlib import Path
import re
import sys

from .evidence import normalise
from .synthetic import BLOCKS, FEATURES, KINDS, LAYOUTS, render_case

FORMAT = "casepath.benchmark-case/1"
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ID = re.compile(r"^[A-Z][A-Z0-9]{1,3}-[a-z0-9-]{3,60}$")


class BenchmarkError(ValueError):
    pass


def load_suite(directory):
    cases = []
    for path in sorted(Path(directory).glob("*/case.json")):
        case = json.loads(path.read_text())
        case["_dir"] = str(path.parent)
        cases.append(case)
    return cases


def case_text(case):
    return "\n".join(f"{d['sender']} {d['recipient']} {d['title']}\n" + "\n".join(b["text"] for b in d["blocks"]) for d in case["documents"])


def _matchers(items, where):
    if not isinstance(items, list):
        raise BenchmarkError(f"{where} must be a list")
    for item in items:
        if not item.get("label") or not isinstance(item.get("match"), list) or not item["match"]:
            raise BenchmarkError(f"{where}: each entry needs a label and match keywords")


def validate_case(case, catalogue=None):
    """Raise BenchmarkError for anything malformed; return the list of problems that are only warnings."""
    if case.get("format") != FORMAT:
        raise BenchmarkError(f"format must be {FORMAT}")
    if not ID.match(str(case.get("id"))):
        raise BenchmarkError(f"id {case.get('id')!r} must look like B07-employment-sick-leave")
    for key in ("title", "scenario"):
        if not case.get(key):
            raise BenchmarkError(f"{case['id']}: {key} is required")
    documents = case.get("documents")
    if not isinstance(documents, list) or not documents:
        raise BenchmarkError(f"{case['id']}: documents are required")
    for index, d in enumerate(documents):
        where = f"{case['id']} document {index + 1}"
        if d.get("kind") not in KINDS or d.get("layout") not in LAYOUTS or not DATE.match(str(d.get("date"))):
            raise BenchmarkError(f"{where}: kind, layout and date (YYYY-MM-DD) must be valid")
        if not d.get("title") or not isinstance(d.get("blocks"), list) or not d["blocks"]:
            raise BenchmarkError(f"{where}: title and blocks are required")
        if any(f not in FEATURES for f in d.get("features", [])) or any(b.get("type") not in BLOCKS for b in d["blocks"]):
            raise BenchmarkError(f"{where}: unknown feature or block type")
    truth = case.get("truth") or {}
    workflow = (catalogue or {}).get(truth.get("workflow")) if catalogue else None
    if catalogue and workflow is None:
        raise BenchmarkError(f"{case['id']}: workflow {truth.get('workflow')!r} is not in the catalogue")
    text = normalise(case_text(case))
    warnings = []
    if workflow:
        facts = {f["id"]: f for f in workflow["facts"]}
        for fact, value in (truth.get("facts") or {}).items():
            if fact not in facts:
                raise BenchmarkError(f"{case['id']}: fact {fact!r} is not in {workflow['id']}")
            kind = facts[fact]["type"]
            if value is not None and ((kind == "enum" and value not in facts[fact]["values"]) or (kind == "boolean" and type(value) is not bool)
                                      or (kind == "date" and not DATE.match(str(value)))):
                raise BenchmarkError(f"{case['id']}: value {value!r} does not fit fact {fact!r} ({kind})")
        needs = {d["id"] for d in workflow["documents"]}
        for need, status in (truth.get("documents") or {}).items():
            if need not in needs or status not in {"present", "missing", "unusable"}:
                raise BenchmarkError(f"{case['id']}: document need {need!r} or its status {status!r} is not valid")
        outcomes = {o["id"] for o in workflow.get("outcomes", [])}
        if truth.get("outcome") not in outcomes | {None}:
            raise BenchmarkError(f"{case['id']}: outcome {truth.get('outcome')!r} is not in {workflow['id']}")
        for fact in (truth.get("flags") or {}).get("conflict_facts", []):
            if fact not in facts:
                raise BenchmarkError(f"{case['id']}: conflict fact {fact!r} is not in {workflow['id']}")
    for fact, quote in (truth.get("evidence") or {}).items():
        if normalise(quote) not in text:
            raise BenchmarkError(f"{case['id']}: the evidence for {fact!r} is not in the documents: {quote[:80]!r}")
    for fact, value in (truth.get("facts") or {}).items():
        if value is not None and fact not in (truth.get("evidence") or {}) and fact not in {"rechtsgebiet", "login", "personalien"}:
            warnings.append(f"{case['id']}: fact {fact!r} has a value but no evidence sentence")
    _matchers(truth.get("case_documents", []), f"{case['id']} case_documents")
    _matchers(truth.get("not_required", []), f"{case['id']} not_required")
    _matchers(truth.get("next_actions", []), f"{case['id']} next_actions")
    if any(item.get("status") not in {"present", "missing"} for item in truth.get("case_documents", [])):
        raise BenchmarkError(f"{case['id']}: case_documents status must be present or missing")
    if any(not DATE.match(str(d)) for d in truth.get("deadlines", [])):
        raise BenchmarkError(f"{case['id']}: deadlines must be YYYY-MM-DD")
    return warnings


def short_id(case):
    return case["id"].split("-", 1)[0]


def uploads(case, rendered):
    """What a case worker would upload: one dossier named by case number, or the separate files; scans named as scans."""
    if case.get("bundle") or case["truth"].get("bundle"):
        return [(f"{short_id(case)}_Dossier.pdf", (Path(rendered) / "dossier.pdf").read_bytes())]
    manifest = json.loads((Path(rendered) / "case.json").read_text())
    files = []
    for index, row in enumerate(manifest["files"], 1):
        name = f"Scan_{index:02d}.pdf" if row["scanned"] else row["file"][3:]
        files.append((name, (Path(rendered) / "documents" / row["file"]).read_bytes()))
    return files


def seed(store, directory, user="synthetisch"):
    """Load the suite's cases into a store as synthetic cases anyone can open and prepare; cases already there are kept.

    The title names only the case number and its first document, never the truth, so the agents see a case as a case
    worker would. Returns the number of cases added."""
    import tempfile

    from .extract import extract

    existing = {c["title"] for c in store.list_cases()}
    added = 0
    with tempfile.TemporaryDirectory() as scratch:
        for case in load_suite(directory):
            title = f"Synthetischer Fall {short_id(case)}: {case['documents'][0]['title']}"[:300]
            if title in existing:
                continue
            rendered = Path(scratch) / case["id"]
            render(case, rendered)
            created = store.create_case(title, {"synthetic": True, "source": "synthetic"}, user)
            for name, data in uploads(case, rendered):
                row = extract(name, "application/pdf", data)
                store.add_file(created["id"], name, row["media_type"], row["kind"], data, row, user)
            added += 1
    return added


def render(case, directory):
    """Write the case's documents as PDFs (scanned where the layout says so) and one combined dossier."""
    documents = [{"language": "de", "features": [], "meets_needs": [], "sender": "", "recipient": "", **d} for d in case["documents"]]
    return render_case({"title": case["title"], "documents": documents, "truth": case["truth"]}, directory)


def main(argv=None):
    from .workflows import Catalogue

    parser = argparse.ArgumentParser(prog="casepath_internal.benchmark")
    parser.add_argument("command", choices=["check"])
    parser.add_argument("suite")
    parser.add_argument("--catalogue")
    args = parser.parse_args(argv)
    catalogue = {w["id"]: w for w in Catalogue.load(args.catalogue).latest()} if args.catalogue else None
    failed = 0
    for case in load_suite(args.suite):
        try:
            warnings = validate_case(case, catalogue)
            render(case, Path(case["_dir"]) / "rendered")
            print(f"ok   {case['id']}" + "".join(f"\n     warning: {w}" for w in warnings))
        except BenchmarkError as error:
            failed += 1
            print(f"FAIL {case.get('id')}: {error}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
