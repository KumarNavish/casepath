"""Turn a draw.io process diagram into a draft workflow, without interpretation.

Every step, branch, role and outcome in the draft points back to the diagram
cell it came from. Decision shapes become facts whose values are the labels on
their outgoing arrows. Nothing is inferred from wording: document requirements
and routing conditions are left for a reviewer to add with their own sources,
and anything the diagram leaves ambiguous becomes an open question.

Run inside the approved environment that holds the diagram:

    python -m casepath_internal.drawio case_mold.drawio --version 2026-07-23 > case_mold.json
"""
import argparse
import base64
import html
import json
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
import zlib

from .workflows import FORMAT, validate_workflow


def _decode_page(diagram):
    model = diagram.find("mxGraphModel")
    if model is not None:
        return model
    packed = (diagram.text or "").strip()
    if not packed:
        raise ValueError(f"page {diagram.get('name')!r} is empty")
    inflated = zlib.decompress(base64.b64decode(packed), -15).decode("utf-8")
    return ET.fromstring(urllib.parse.unquote(inflated))


def _label(raw):
    text = re.sub(r"<br\s*/?>|</(div|p|li)>", "\n", raw or "", flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"[ \t ]+", " ", re.sub(r"\s*\n\s*", " / ", text.strip())).strip(" /")


def _style(raw):
    parts = {}
    for item in (raw or "").split(";"):
        key, _, value = item.partition("=")
        if key:
            parts[key.strip()] = value.strip() if _ else True
    return parts


def _cells(model):
    root = model.find("root")
    if root is None:
        raise ValueError("diagram page has no root")
    cells = {}
    for node in root:
        if node.tag == "mxCell":
            cell, label = node, node.get("value")
        elif node.tag in {"object", "UserObject"}:
            cell, label = node.find("mxCell"), node.get("label")
            if cell is None:
                continue
        else:
            continue
        geometry = cell.find("mxGeometry")
        cells[node.get("id")] = {
            "id": node.get("id"), "label": _label(label), "style": _style(cell.get("style")),
            "parent": cell.get("parent"), "vertex": cell.get("vertex") == "1", "edge": cell.get("edge") == "1",
            "source": cell.get("source"), "target": cell.get("target"),
            "y": float(geometry.get("y", 0)) if geometry is not None else 0.0,
            "x": float(geometry.get("x", 0)) if geometry is not None else 0.0,
        }
    return cells


def _slug(value, used):
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:60] or "cell"
    candidate, counter = base, 2
    while candidate in used:
        candidate, counter = f"{base}-{counter}", counter + 1
    used.add(candidate)
    return candidate


def _kind(cell):
    style = cell["style"]
    shape = str(style.get("shape", ""))
    if "swimlane" in style or shape in {"swimlane", "table"} or "pool" in shape or "lane" in shape:
        return "lane"
    if "text" in style or "edgeLabel" in style or shape == "note":
        return "note"
    if "group" in style:
        return "group"
    if "rhombus" in style or "gateway" in shape:
        return "decision"
    if "ellipse" in style or "event" in shape:
        return "event"
    return "step"


def convert_page(model, *, workflow_id, version, title, source_title, page_name):
    cells = _cells(model)
    source = "diagram"
    page = re.sub(r"[^A-Za-z0-9_.-]+", "-", page_name or "page")

    def ref(cell_id):
        return f"{source}#{page}:{cell_id}"

    edge_labels = {}
    for cell in cells.values():
        if cell["vertex"] and cell["parent"] in cells and cells[cell["parent"]]["edge"] and cell["label"]:
            edge_labels.setdefault(cell["parent"], []).append(cell["label"])
    nodes = {cid: c for cid, c in cells.items()
             if c["vertex"] and _kind(c) in {"step", "decision", "event"} and not (c["parent"] in cells and cells[c["parent"]]["edge"])}

    def role(cell):
        seen, current = set(), cells.get(cell["parent"])
        while current is not None and current["id"] not in seen:
            seen.add(current["id"])
            if _kind(current) == "lane" and current["label"]:
                return current["label"]
            current = cells.get(current["parent"])
        return None

    questions, ids = [], set()
    step_ids = {cid: "s-" + _slug(c["label"] or cid, ids) for cid, c in sorted(nodes.items(), key=lambda kv: (kv[1]["y"], kv[1]["x"]))}
    outgoing, incoming = {cid: [] for cid in nodes}, {cid: 0 for cid in nodes}
    for cell in cells.values():
        if not cell["edge"]:
            continue
        if cell["source"] not in nodes or cell["target"] not in nodes:
            questions.append({"text": "An arrow is not connected to two process shapes.", "source_refs": [ref(cell["id"])]})
            continue
        label = cell["label"] or " ".join(edge_labels.get(cell["id"], []))
        outgoing[cell["source"]].append({"edge": cell["id"], "to": cell["target"], "label": label})
        incoming[cell["target"]] += 1
    starts = sorted((cid for cid in nodes if incoming[cid] == 0), key=lambda c: (nodes[c]["y"], nodes[c]["x"]))
    preferred = [cid for cid in starts if _kind(nodes[cid]) == "event"] or starts
    if not preferred:
        preferred = sorted(nodes, key=lambda c: (nodes[c]["y"], nodes[c]["x"]))
    if not preferred:
        raise ValueError(f"page {page_name!r} has no process shapes")
    start = preferred[0]
    if len(starts) > 1:
        others = ", ".join(f"“{nodes[c]['label'] or c}”" for c in starts if c != start)
        questions.append({"text": f"The diagram has more than one starting shape; the draft starts at “{nodes[start]['label'] or start}”. Also starting: {others}.",
                          "source_refs": [ref(c) for c in starts]})
    facts, steps, outcomes, fact_ids = [], [], [], set()
    for cid, cell in nodes.items():
        edges = outgoing[cid]
        step = {"id": step_ids[cid], "title": cell["label"] or f"(unlabelled shape {cid})", "role": role(cell),
                "source_refs": [ref(cid)], "documents": [], "next": []}
        if not cell["label"]:
            questions.append({"text": f"Shape {cid} has no label.", "source_refs": [ref(cid)]})
        if len(edges) == 1:
            step["next"] = [{"to": step_ids[edges[0]["to"]], "label": edges[0]["label"] or None, "when": True}]
        elif len(edges) > 1:
            fact_id = "d-" + _slug(cell["label"] or cid, fact_ids)
            values, used = [], set()
            for index, edge in enumerate(edges, 1):
                value = edge["label"] or f"route {index}: {nodes[edge['to']]['label'] or edge['to']}"
                if value in used:
                    value = f"{value} ({index})"
                used.add(value)
                values.append(value)
                step["next"].append({"to": step_ids[edge["to"]], "label": edge["label"] or None,
                                     "when": {"fact": fact_id, "is": value}})
                if not edge["label"]:
                    questions.append({"text": f"An arrow from “{step['title']}” has no label; confirm whether the paths are alternatives or run in parallel.",
                                      "source_refs": [ref(edge["edge"])]})
            facts.append({"id": fact_id, "type": "enum", "values": values,
                          "question": cell["label"] if _kind(cell) == "decision" else f"Which path follows “{step['title']}”?",
                          "source_refs": [ref(cid)] + [ref(e["edge"]) for e in edges]})
        elif _kind(cell) == "event":
            outcome_id = "o-" + step_ids[cid][2:]
            outcomes.append({"id": outcome_id, "title": step["title"], "source_refs": [ref(cid)]})
            step["outcome"] = outcome_id
        steps.append(step)
    for cell in cells.values():
        if cell["vertex"] and _kind(cell) == "note" and cell["label"] and not (cell["parent"] in cells and cells[cell["parent"]]["edge"]):
            questions.append({"text": f"Diagram note: {cell['label']}", "source_refs": [ref(cell["id"])]})
    reachable, frontier = set(), [step_ids[start]]
    by_id = {s["id"]: s for s in steps}
    while frontier:
        current = frontier.pop()
        if current not in reachable:
            reachable.add(current)
            frontier.extend(e["to"] for e in by_id[current]["next"])
    dropped = [s for s in steps if s["id"] not in reachable]
    if dropped:
        questions.append({"text": "Not connected to the start, so left out of this draft: " + ", ".join(f"“{s['title']}”" for s in dropped) + ".",
                          "source_refs": [r for s in dropped for r in s["source_refs"]]})
    kept_facts = {c["fact"] for s in steps if s["id"] in reachable for e in s["next"] if isinstance(e["when"], dict) for c in [e["when"]]}
    kept_outcomes = {s.get("outcome") for s in steps if s["id"] in reachable}
    workflow = {
        "format": FORMAT, "id": workflow_id, "version": version, "title": title, "status": "draft",
        "sources": [{"id": source, "kind": "process_diagram", "title": source_title, "locator": source_title}],
        "applies_when": None, "facts": [f for f in facts if f["id"] in kept_facts], "start": step_ids[start],
        "steps": [s for s in steps if s["id"] in reachable], "documents": [],
        "outcomes": [o for o in outcomes if o["id"] in kept_outcomes], "open_questions": questions,
    }
    return validate_workflow(workflow)


def convert(data, *, source_title, version, workflow_id=None, title=None):
    tree = ET.fromstring(data)
    pages = [tree] if tree.tag == "mxGraphModel" else tree.findall("diagram")
    if not pages:
        raise ValueError("no diagram pages found")
    base = workflow_id or re.sub(r"[^a-z0-9]+", "-", source_title.lower().rsplit(".", 1)[0]).strip("-")
    workflows = []
    for index, page in enumerate(pages, 1):
        name = page.get("name") or f"Page {index}"
        model = page if page.tag == "mxGraphModel" else _decode_page(page)
        workflows.append(convert_page(model, workflow_id=base if len(pages) == 1 else f"{base}-p{index}", version=version,
                                      title=title or name, source_title=source_title, page_name=name))
    return workflows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("diagram")
    parser.add_argument("--version", required=True, help="the diagram's date or version, recorded with every rule")
    parser.add_argument("--id")
    parser.add_argument("--title")
    args = parser.parse_args(argv)
    with open(args.diagram, "rb") as handle:
        data = handle.read()
    name = args.diagram.replace("\\", "/").rsplit("/", 1)[-1]
    rows = convert(data, source_title=name, version=args.version, workflow_id=args.id, title=args.title)
    json.dump(rows[0] if len(rows) == 1 else rows, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
