"""Bounded review milestones from a verified work packet, never private reasoning.

The four stages describe review work. They do not assert that a customer's
statement caused a legal process step; only recorded object links are exposed.
"""
from copy import deepcopy

STAGES = (
    ("sources", "Sources", "sources read", {"document_source_integrity"}),
    ("findings", "Findings", "reported statements", {"canonical_facts"}),
    ("process", "Process", "steps mapped", {"process_decision_mapping"}),
    ("documents", "Documents", "requirements checked", {"evidence_checklist"}),
)
OPERATIONS = {
    "SOURCE_OPENED": "sources", "SOURCE_SPAN_SELECTED": "sources",
    "ASSERTION_PROPOSED": "findings", "ASSERTION_REVISED": "findings",
    "CONTRADICTION_FOUND": "findings", "PROCESS_NODE_PROPOSED": "process",
    "BRANCH_PROPOSED": "process", "BRANCH_ACTIVATED": "process", "BRANCH_REJECTED": "process",
    "OBLIGATION_PROPOSED": "documents", "DOCUMENT_REQUIREMENT_PROPOSED": "documents",
    "DOCUMENT_STATE_CHANGED": "documents", "SOURCE_LINK_ADDED": "documents",
}
ROLE_STAGE = {"canonical_facts": "findings", "document_source_integrity": "sources",
              "process_decision_mapping": "process", "evidence_checklist": "documents"}
ROLE_INTENT = {"canonical_facts": "Reading exact source statements",
               "orchestrator_plan": "Checking the review handoffs",
               "document_source_integrity": "Checking the source links",
               "process_decision_mapping": "Mapping the saved handling process",
               "evidence_checklist": "Deriving documents from process steps",
               "final_claim_brief_audit": "Checking the handoff to your review"}


def live_work(claim_id, packet, *, paused=False):
    if not packet:
        return None
    summary, events = packet["summary"], packet["events"]
    if summary["claim_id"] != claim_id or any(e["claim_id"] != claim_id or e["run_id"] != summary["run_id"] for e in events):
        raise ValueError("live work crosses the verified claim or run")
    status, currentness = summary["status"], summary["currentness"]
    active_role = (summary.get("current_role") or {}).get("id")
    running = status in {"queued", "running"} and currentness not in {"historical", "unconfirmed"}
    completed = {e.get("role") for e in events if e["operation"] == "AGENT_COMPLETED"}
    filenames, nodes, obligations, counts, latest, details, milestones = {}, {}, {}, {s[0]: set() for s in STAGES}, {}, {}, []
    for event in events:
        operation, value = event["operation"], event.get("after") or {}
        stage = OPERATIONS.get(operation)
        if not stage:
            continue
        if operation == "SOURCE_OPENED":
            filenames[event["object_id"]] = value.get("filename", "Original source")
            counts["sources"].add(event["object_id"])
        elif operation in {"ASSERTION_PROPOSED", "ASSERTION_REVISED"}:
            counts["findings"].add(event["object_id"])
        elif operation == "PROCESS_NODE_PROPOSED":
            nodes[value["node_id"]] = value.get("title") or value.get("label") or value["node_id"]
            counts["process"].add(value["node_id"])
        elif operation == "OBLIGATION_PROPOSED":
            obligations[value["evidence_item_id"]] = value
        elif operation == "DOCUMENT_REQUIREMENT_PROPOSED":
            counts["documents"].add(value["evidence_item_id"])
        sources = [{**deepcopy(source), "artifact_id": source["source_id"], "claim_id": claim_id,
                    "file_name": filenames.get(source["source_id"], "Original source")}
                   for source in event.get("sources", [])[:2]]
        milestone = {"sequence": event["sequence"], "event_sha256": event["event_sha256"],
            "timestamp": event["timestamp"], "stage": stage, "type": operation,
            "object_id": event["object_id"], "summary": event["message"],
            "sources": sources, "nodes": [], "documents": [], "connections": []}
        if operation in {"ASSERTION_PROPOSED", "ASSERTION_REVISED"}:
            milestone["summary"] = "Reported in the source; factual truth still needs review."
            if value.get("span_id") in event.get("links", []):
                milestone["connections"].append({"from": value["span_id"], "to": event["object_id"], "relation": "exact_quotation"})
        if operation == "PROCESS_NODE_PROPOSED":
            milestone["nodes"] = [{"node_id": value["node_id"], "label": nodes[value["node_id"]]}]
            milestone["summary"] = "Mapped from the saved handling rules; this does not validate the step."
        if operation in {"OBLIGATION_PROPOSED", "DOCUMENT_REQUIREMENT_PROPOSED", "DOCUMENT_STATE_CHANGED", "SOURCE_LINK_ADDED"}:
            requirement_id = value.get("evidence_item_id") or value.get("requirement_id")
            item = value if "evidence_item_id" in value else obligations.get(requirement_id)
            if item:
                document = {"requirement_id": requirement_id, "label": item.get("title") or requirement_id,
                            "state": item["evidence_class"], "needed_now": item["mandatory_now"]}
                # This prefix is the authority adapter's explicit document identity.
                if requirement_id.startswith("process_document."):
                    document["document_type"] = requirement_id[len("process_document."):]
                milestone["documents"].append(document)
            if operation == "SOURCE_LINK_ADDED":
                node_id = value.get("process_node_id")
                if node_id in nodes and isinstance(requirement_id, str) and {"node:" + node_id, "obligation:" + requirement_id} <= set(event.get("links", [])):
                    milestone["nodes"] = [{"node_id": node_id, "label": nodes[node_id]}]
                    milestone["connections"].append({"from": "node:" + node_id, "to": "obligation:" + requirement_id,
                        "relation": "required_by_process"})
                    # The relation records provenance, not current necessity.
                    # Conditional includes optional/later records; raw rule prose
                    # cannot recover a more precise timing than the typed state.
                    milestone["summary"] = (
                        "The saved step requires this document now." if item and item["mandatory_now"] is True
                        else "The saved step lists this document; it is not required now." if item
                        else "The saved step is linked to this document."
                    )
        milestones.append(milestone)
        latest[stage] = milestone
        # Later integrity reads and branch receipts must not erase the last
        # inspectable passage or mapped step. Their actual recency is retained
        # separately; this does not associate that passage with another object.
        preferred = {"sources": "sources", "process": "nodes"}.get(stage)
        if not preferred or milestone[preferred] or not details.get(stage, {}).get(preferred):
            details[stage] = milestone
    detail_labels = {}
    if status == "completed":
        document_timing = {d["requirement_id"]: d["needed_now"] for m in milestones for d in m["documents"]}
        required = next((m for m in reversed(milestones)
                         if m["type"] == "SOURCE_LINK_ADDED" and m["connections"] and m["documents"]
                         and all(d["needed_now"] is True and document_timing[d["requirement_id"]] is True
                                 for d in m["documents"])), None)
        if required:
            # Retain the mapped node referenced by this exact recorded link.
            # The independently selected source passage gains no relationship.
            node_id = required["nodes"][0]["node_id"]
            mapped = next(m for m in reversed(milestones)
                          if m["type"] == "PROCESS_NODE_PROPOSED" and m["sequence"] < required["sequence"]
                          and m["nodes"][0]["node_id"] == node_id)
            details.update(documents=required, process=mapped)
            detail_labels = {"documents": "Required in this review", "process": "Step with a required document"}
    # Keep each stage's inspectable detail and the actual most recent arrivals.
    # No historical event is delayed to simulate live work.
    selected = {m["sequence"]: m for m in [*milestones[-8:], *details.values()]}
    stages = []
    active_stage = ROLE_STAGE.get(active_role)
    if active_role == "canonical_facts" and milestones and milestones[-1]["stage"] in {"sources", "findings"}:
        active_stage = milestones[-1]["stage"]
    for key, label, unit, roles in STAGES:
        state = "complete" if roles <= completed else "recorded" if key in latest else "waiting"
        if running and active_stage == key:
            state = "working"
        elif active_stage == key and status in {"blocked", "failed", "interrupted", "unconfirmed"}:
            state = "paused" if paused else "needs_review"
        stages.append({"id": key, "label": label, "state": state, "count": len(counts[key]), "unit": unit,
                       "milestone_sequence": details.get(key, {}).get("sequence"),
                       "latest_milestone_sequence": latest.get(key, {}).get("sequence"),
                       **({"detail_label": detail_labels[key]} if key in detail_labels else {})})
    headline = ROLE_INTENT.get(active_role, "Waiting for the next recorded check") if running else {
        "completed": "Review recorded. Your decision comes next.", "cancelled": "Review stopped. Recorded work is preserved.",
        "interrupted": "Review paused at its saved checkpoint.", "blocked": "A check needs your attention.",
        "failed": "The review could not finish.", "unconfirmed": "The work status needs verification.",
    }.get(status, "Review is queued.")
    if paused and not running:
        headline = "Review paused. Recorded work is preserved."
    if currentness == "historical":
        headline = "Earlier review. The saved claim has changed."
    elif currentness == "unconfirmed":
        headline = "This review's currentness needs verification."
    provider_events = [e for e in events if e["operation"] == "PROVIDER_RESPONSE_RECEIVED"]
    model = (provider_events[-1].get("after") or {}).get("response_model") if provider_events else None
    return {"claim_id": claim_id, "run_id": summary["run_id"], "status": status, "currentness": currentness,
            "last_sequence": summary["last_sequence"], "last_event_sha256": summary.get("last_event_sha256"),
            "headline": headline, "active_stage": active_stage if running else None, "stages": stages,
            "milestones": [selected[key] for key in sorted(selected)],
            "reader": {"kind": "model" if summary.get("facts_worker") == "external_facts" else "reference",
                       "model": model, "provider_requests": summary.get("provider_requests", 0),
                       "provider_cost_usd": summary.get("provider_cost_usd")},
            "scope": "recorded_review_work_not_claim_authority"}
