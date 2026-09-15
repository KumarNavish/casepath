"""Thin adapter to the existing CasePath claim and evidence authorities.

There is no alternate claim store here. `start` and `ensure` remain the only
setup mutations, with the original expected revisions and idempotency keys.
No tool in this extension approves a claim, sends a request, or admits evidence.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Callable, Protocol
import json
from threading import RLock

PDF_READ_LOCK = RLock()

from .contracts import digest

MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_TEXT_CHARS = 24_000


class AuthorityError(RuntimeError):
    pass


class SourceChanged(AuthorityError):
    pass


class ClaimAuthority(Protocol):
    def context(self, claim_id: str) -> dict[str, Any]: ...
    def list_sources(self, claim_id: str) -> list[dict[str, Any]]: ...
    def read_source(self, claim_id: str, source_id: str) -> dict[str, Any]: ...
    def prepare(self, claim_id: str, run_id: str, expected_context: dict[str, Any]) -> dict[str, Any]: ...
    def snapshot(self, claim_id: str) -> dict[str, Any]: ...


def _hash(value):
    return isinstance(value, str) and len(value) == 64 and set(value) <= set("0123456789abcdef")


def normalize_loop(view: dict[str, Any]) -> dict[str, Any]:
    state = view.get("loop_state")
    projection = view.get("operational_projection")
    if not isinstance(state, dict) or not isinstance(projection, dict) or not _hash(state.get("state_sha256")):
        raise AuthorityError("existing authority returned an incomplete loop view")
    if view.get("claim_id") != state.get("claim_id") or projection.get("claim_id") != state.get("claim_id"):
        raise AuthorityError("claim identities differ across the authority view")
    process = state.get("process", {})
    nodes = process.get("nodes", [])
    evidence = projection.get("evidence_items", [])
    if not isinstance(nodes, list) or not nodes or not isinstance(evidence, list):
        raise AuthorityError("the existing process or evidence projection is unavailable")
    if len({n.get("node_id") for n in nodes}) != len(nodes):
        raise AuthorityError("process nodes are not uniquely identified")
    branches = []
    for node in nodes:
        for index, branch in enumerate(node.get("branches", [])):
            branches.append({**branch, "object_id": f"{node['node_id']}.branch.{index}", "from_node_id": node["node_id"]})
    return {
        "claim_id": state["claim_id"], "state_sha256": state["state_sha256"],
        "revision": state["revision"], "workspace_state_sha256": view.get("workspace_state_sha256"),
        "process": process, "branches": branches,
        "evidence": evidence, "checklist": state.get("checklist", {}).get("items", []),
        "readiness": {"state": projection["readiness_state"], "scope": projection["readiness_scope"],
                      "blocker": projection["principal_blocker"], "next_action": projection.get("next_state"),
                      "pending_evidence_count": projection.get("pending_evidence_count")},
        "cycle_receipt": state.get("six_agent_cycle_receipt"),
        "compilation_receipt": view.get("compilation_receipt"),
        "observation_count": len(state.get("observations", [])),
    }


class ExistingCasePathAuthority:
    """Configured with the original app's service factories, never caller code."""
    def __init__(self, workspace_getter: Callable, loop_getter: Callable):
        self._workspace = workspace_getter
        self._loop = loop_getter

    def _detail(self, claim_id):
        detail = self._workspace().detail(claim_id)
        if detail.get("claim_id", detail.get("state", {}).get("claim_id")) != claim_id:
            raise AuthorityError("claim detail identity mismatch")
        return detail

    def context(self, claim_id):
        detail = self._detail(claim_id)
        state = detail["state"]
        sources = self.list_sources(claim_id)
        if not _hash(state.get("state_sha256")):
            raise AuthorityError("saved claim state has no content identity")
        loop = self._optional_view(claim_id) if state["workflow_state"] != "received" else None
        return {"claim_id": claim_id, "state_sha256": state["state_sha256"], "revision": state["revision"],
                "claim_loop_state_sha256": loop["loop_state"]["state_sha256"] if loop else None,
                "binding_sha256": state["binding"]["binding_sha256"], "workflow_state": state["workflow_state"],
                "source_roster_sha256": digest(sources), "subject": detail["message"]["subject"],
                "source_count": len(sources), "mode": "existing_casepath_authority"}

    def list_sources(self, claim_id):
        detail = self._detail(claim_id)
        return [{"source_id": a["artifact_id"], "source_sha256": a["sha256"], "filename": a["file_name"],
                 "media_type": a["media_type"], "size_bytes": a["size_bytes"], "role": a["role"]}
                for a in detail["artifacts"]]

    def read_source(self, claim_id, source_id):
        detail = self._detail(claim_id)
        metadata = next((a for a in detail["artifacts"] if a["artifact_id"] == source_id), None)
        if metadata is None:
            raise AuthorityError("source is outside this claim")
        raw, bound = self._workspace().corpus.artifact(claim_id, source_id)
        if len(raw) != metadata["size_bytes"] or sha256(raw).hexdigest() != metadata["sha256"] or bound["sha256"] != metadata["sha256"]:
            raise SourceChanged("the original source bytes no longer match the binding")
        if len(raw) > MAX_SOURCE_BYTES:
            raise AuthorityError("source exceeds the bounded reading limit")
        media = metadata["media_type"].split(";")[0].lower().strip()
        complete, extraction, coverage = True, "utf8", None
        if metadata["role"] == "customer_message":
            # Read original bytes first; then use the existing validated message
            # projection, never pretend it is the raw email representation.
            text, extraction = detail["message"]["body"], "message_body"
        elif media == "application/pdf":
            import fitz
            with PDF_READ_LOCK, fitz.open(stream=raw, filetype="pdf") as document:
                if document.is_encrypted:
                    raise AuthorityError("PDF is locked")
                count = min(len(document), 30)
                pages = [document[i].get_text("text") for i in range(count)]
                unread = [index + 1 for index, page_text in enumerate(pages) if not page_text.strip()]
                image_pages = [index + 1 for index in range(count) if document[index].get_images(full=True)]
                text = "\n\f\n".join(pages)
                # Opening a scanned page is not reading its image. Blank or
                # image-only pages remain explicitly outside text coverage.
                complete = len(document) <= count and count > 0 and not unread and not image_pages
                extraction = "pdf_text"
                coverage = {"pages_total": len(document), "pages_examined": count,
                            "pages_with_text": count - len(unread), "pages_without_text": unread,
                            "pages_with_images": image_pages,
                            "visual_interpretation_performed": False}
        elif media.startswith("text/") or media in {"application/json", "message/rfc822"}:
            try:
                text = raw.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise AuthorityError("source is not supported UTF-8 text") from exc
        elif media.startswith("image/"):
            text, extraction, complete = "", "image_metadata", False
        else:
            # An unsupported format is visible as unread, not silently converted
            # into an assertion or described as having been interpreted.
            text, extraction, complete = "", "image_metadata", False
        full_text_hash = sha256(text.encode()).hexdigest()
        if len(text) > MAX_TEXT_CHARS:
            text, complete = text[:MAX_TEXT_CHARS], False
        return {"source_id": source_id, "source_sha256": metadata["sha256"],
                "text_sha256": sha256(text.encode()).hexdigest(), "full_text_sha256": full_text_hash,
                "text": text, "extraction": extraction, "complete": complete,
                "filename": metadata["file_name"], "media_type": metadata["media_type"],
                "role": metadata["role"], "claim_id": claim_id, **({"coverage": coverage} if coverage is not None else {})}

    def _optional_view(self, claim_id):
        try:
            return self._loop().view(claim_id)
        except ValueError as exc:
            # Do not reinterpret arbitrary 409/corruption failures as absence.
            if str(exc) == "claim loop does not exist":
                return None
            raise

    def prepare(self, claim_id, run_id, expected_context):
        before = self.context(claim_id)
        if before["binding_sha256"] != expected_context["binding_sha256"] or before["source_roster_sha256"] != expected_context["source_roster_sha256"]:
            raise SourceChanged("the packet changed after work was requested")
        existing = self._optional_view(claim_id) if before["workflow_state"] != "received" else None
        if existing is not None:
            if (before["state_sha256"] != expected_context["state_sha256"]
                    or before.get("claim_loop_state_sha256") != expected_context.get("claim_loop_state_sha256")):
                raise SourceChanged("claim state changed before process mapping; refresh the work request")
            result = normalize_loop(existing)
            return {**result, "setup_changed": False, "before_context": before}
        if before["state_sha256"] != expected_context["state_sha256"]:
            raise SourceChanged("claim state changed before setup; request a fresh review")
        detail = self._detail(claim_id)
        state = detail["state"]
        started = False
        if state["workflow_state"] == "received":
            reply = self._workspace().start(claim_id, idempotency_key=run_id + ".start", expected_revision=state["revision"])
            state = reply["state"]
            started = True
            check = self._detail(claim_id)["state"]
            if check["state_sha256"] != state["state_sha256"]:
                raise SourceChanged("the saved claim differs after setup")
        if state["workflow_state"] != "in_review":
            raise AuthorityError("this claim cannot enter setup in its current state")
        response = self._loop().ensure(claim_id, expected_workspace_revision=state["revision"],
                                      expected_workspace_state_sha256=state["state_sha256"],
                                      idempotency_key=run_id + ".ensure")
        confirmed = self._loop().view(claim_id)
        if response["loop_state"]["state_sha256"] != confirmed["loop_state"]["state_sha256"]:
            raise SourceChanged("the evidence loop was not confirmed exactly")
        return {**normalize_loop(confirmed), "setup_changed": True, "start_changed": started, "before_context": before}

    def snapshot(self, claim_id):
        return normalize_loop(self._loop().view(claim_id))
