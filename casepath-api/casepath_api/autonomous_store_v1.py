"""Operational intake and accepted autonomous events in the claim-loop journal.

This namespace never rewrites corpus bindings or human review events. Source
availability is distinct from acquisition; extraction never claims sufficiency.
The controller owns semantic verification and calls these bounded commands.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile
from threading import RLock
import unicodedata
from urllib.parse import quote

from .causal_process_v1 import evaluate, seal_graph, validate_graph
from .claim_loop_store import ClaimLoopStore
from .workspace_corpus import digest_value


SESSION_ID = "casepath-autonomous-local-v1"
CONTRACT = "casepath.autonomous-claim/1.0.0"
EVENT_CONTRACT = "casepath.autonomous-event/1.0.0"
SOURCE_CONTRACT = "casepath.autonomous-source/1.0.0"
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_PACKET_BYTES = 32 * 1024 * 1024
MAX_TEXT_CHARS = 48_000
INCOMPLETE_STATUSES = frozenset({"received", "running"})
_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,180}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_PDF_LOCK = RLock()


class AutonomousStoreError(ValueError):
    pass


def _copy(value):
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(encoded.encode()) > 4 * 1024 * 1024:
            raise ValueError("event exceeds the supported size")
        return json.loads(encoded)
    except (TypeError, ValueError, RecursionError) as exc:
        raise AutonomousStoreError("invalid bounded JSON: " + str(exc)) from exc


def _seal(value, key):
    return {**value, key: digest_value(value)}


def _text(value, label, maximum=1000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\x00" in value:
        raise AutonomousStoreError(label + " is invalid")
    return value


def _identifier(value, label):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise AutonomousStoreError(label + " is invalid")
    return value


def _fields(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        raise AutonomousStoreError("event fields are invalid")


def _receipt(value, *, interpretation=False):
    if not isinstance(value, dict):
        raise AutonomousStoreError("verification receipt is missing")
    required = {"gate_sha256", "policy_id", "receipt_sha256"}
    if interpretation:
        required |= {"proposal_sha256", "verifier_sha256"}
    if not required <= value.keys():
        raise AutonomousStoreError("verification receipt fields are missing")
    _text(value["policy_id"], "verification policy", 180)
    for key in required - {"policy_id"}:
        if not isinstance(value[key], str) or not _HASH.fullmatch(value[key]):
            raise AutonomousStoreError("verification receipt hash is invalid")
    if value["receipt_sha256"] != digest_value({k: v for k, v in value.items() if k != "receipt_sha256"}):
        raise AutonomousStoreError("verification receipt seal differs")


class AutonomousStore:
    def __init__(self, storage_or_path, source_root=None):
        self._read_only = False
        self.storage = storage_or_path if hasattr(storage_or_path, "path") else None
        path = Path(self.storage.path if self.storage is not None else storage_or_path)
        if path.is_symlink():
            raise AutonomousStoreError("journal path must not be a symlink")
        self.journal = ClaimLoopStore(path)
        self.path = self.journal.path
        if self.storage is not None and hasattr(self.storage, "protected_session_ids"):
            # The shared Storage instance's generic reset/write APIs cannot own
            # this namespace. Pass this same instance to the controller.
            with self.storage.lock:
                self.storage.protected_session_ids = frozenset({*self.storage.protected_session_ids, SESSION_ID})
        root = Path(source_root) if source_root is not None else self.path.parent / "autonomous-sources-v1"
        if root.is_symlink():
            raise AutonomousStoreError("source root must not be a symlink")
        root.mkdir(parents=True, exist_ok=True)
        self.source_root = root.resolve()
        self._extractions = {}
        self._extraction_lock = RLock()

    @classmethod
    def open_read_only(cls, path, source_root=None):
        """Replay existing events and source bytes without schema or path writes."""
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise AutonomousStoreError("read-only journal is not an existing regular file")
        path = path.resolve()
        root = Path(source_root) if source_root is not None else path.parent / "autonomous-sources-v1"
        if root.is_symlink() or not root.is_dir():
            raise AutonomousStoreError("read-only source root is not an existing regular directory")

        class ReadOnlyJournal:
            def __init__(self, database):
                self.path = database

            def connect(self):
                connection = sqlite3.connect(f"file:{quote(str(self.path), safe='/')}?mode=ro",
                                             uri=True, timeout=30, isolation_level=None)
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA query_only=ON")
                return connection

        value = cls.__new__(cls)
        value._read_only, value.storage = True, None
        value.path, value.journal, value.source_root = path, ReadOnlyJournal(path), root.resolve()
        value._extractions, value._extraction_lock = {}, RLock()
        return value

    def _blob(self, digest):
        if not isinstance(digest, str) or not _HASH.fullmatch(digest):
            raise AutonomousStoreError("source hash is invalid")
        path = self.source_root / digest
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "rb") as source:
                metadata = os.fstat(source.fileno())
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_FILE_BYTES:
                    raise AutonomousStoreError("source bytes are not a bounded regular file")
                raw = source.read(MAX_FILE_BYTES + 1)
        except OSError as exc:
            raise AutonomousStoreError("source bytes are unavailable") from exc
        if sha256(raw).hexdigest() != digest:
            raise AutonomousStoreError("source bytes differ from their hash")
        return raw

    def _publish(self, raw):
        if self._read_only:
            raise AutonomousStoreError("read-only replay cannot publish sources")
        digest = sha256(raw).hexdigest()
        path = self.source_root / digest
        # Publish only a fully fsynced inode. Concurrent exact retries never see
        # a partially written final blob, and a crash leaves at most a temp file.
        fd, temporary = tempfile.mkstemp(prefix=".source-", dir=self.source_root)
        try:
            with os.fdopen(fd, "wb") as target:
                target.write(raw)
                target.flush()
                os.fsync(target.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if self._blob(digest) != raw:
                    raise AutonomousStoreError("source byte collision")
            directory = os.open(self.source_root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            os.unlink(temporary)
        return digest

    @staticmethod
    def _file(value):
        _fields(value, {"file_name", "media_type", "content_base64"})
        name = _text(value["file_name"], "file name", 240)
        if name in {".", ".."} or "/" in name or "\\" in name or any(ord(c) < 32 or ord(c) == 127 for c in name):
            raise AutonomousStoreError("unsafe file name")
        name = unicodedata.normalize("NFC", name)
        media = _text(value["media_type"], "media type", 120).split(";", 1)[0].strip().lower()
        if not re.fullmatch(r"[a-z0-9.+-]+/[a-z0-9.+-]+", media):
            raise AutonomousStoreError("invalid media type")
        content = value["content_base64"]
        if not isinstance(content, str) or len(content) > (MAX_FILE_BYTES + 2) // 3 * 4:
            raise AutonomousStoreError("source content exceeds the size limit")
        try:
            raw = base64.b64decode(content, validate=True)
        except (ValueError, TypeError) as exc:
            raise AutonomousStoreError("invalid source base64") from exc
        if not raw or len(raw) > MAX_FILE_BYTES or base64.b64encode(raw).decode() != content:
            raise AutonomousStoreError("source bytes are empty, oversized or noncanonical")
        if raw.startswith(b"%PDF-"):
            media = "application/pdf"
        elif raw.startswith(b"\x89PNG\r\n\x1a\n"):
            media = "image/png"
        elif raw.startswith(b"\xff\xd8\xff"):
            media = "image/jpeg"
        elif media == "application/pdf" or media.startswith("image/"):
            # A declared format does not invent readable content.
            media = "application/octet-stream"
        return name, media, raw

    def _descriptor(self, claim_id, name, media, raw, role):
        digest = self._publish(raw)
        identity = {"claim_id": claim_id, "file_name": name, "media_type": media, "sha256": digest, "role": role}
        return _seal({"contract": SOURCE_CONTRACT, **identity, "size_bytes": len(raw),
                      "artifact_id": "src_" + digest_value(identity)[:32]}, "descriptor_sha256")

    def _validate_descriptor(self, value, claim_id):
        fields = {"contract", "claim_id", "file_name", "media_type", "sha256", "role", "size_bytes", "artifact_id", "descriptor_sha256"}
        _fields(value, fields)
        if value["contract"] != SOURCE_CONTRACT or value["claim_id"] != claim_id or value["role"] not in {"customer_message", "supporting_document"}:
            raise AutonomousStoreError("source descriptor belongs to another claim")
        if value["descriptor_sha256"] != digest_value({k: v for k, v in value.items() if k != "descriptor_sha256"}):
            raise AutonomousStoreError("source descriptor seal differs")
        identity = {k: value[k] for k in ("claim_id", "file_name", "media_type", "sha256", "role")}
        if value["artifact_id"] != "src_" + digest_value(identity)[:32] or type(value["size_bytes"]) is not int:
            raise AutonomousStoreError("source descriptor identity differs")
        raw = self._blob(value["sha256"])
        if len(raw) != value["size_bytes"]:
            raise AutonomousStoreError("source size differs")
        return raw

    def _extract(self, raw, media):
        key = (sha256(raw).hexdigest(), media)
        with self._extraction_lock:
            if key in self._extractions:
                return deepcopy(self._extractions[key])
        text, extraction, complete = "", "unsupported_metadata", False
        coverage = {"visual_interpretation_performed": False}
        if media == "application/pdf":
            import fitz
            extraction = "pdf_text"
            try:
                with _PDF_LOCK, fitz.open(stream=raw, filetype="pdf") as pdf:
                    if pdf.is_encrypted:
                        coverage["limitation"] = "encrypted_pdf"
                    else:
                        count = min(len(pdf), 30)
                        pages = [pdf[i].get_text("text") for i in range(count)]
                        images = [i + 1 for i in range(count) if pdf[i].get_images(full=True)]
                        blank = [i + 1 for i, page in enumerate(pages) if not page.strip()]
                        text = "\n\f\n".join(pages)
                        complete = count > 0 and len(pdf) == count and not images and not blank
                        coverage.update(pages_total=len(pdf), pages_examined=count, pages_without_text=blank, pages_with_images=images)
            except (ValueError, RuntimeError):
                coverage["limitation"] = "invalid_pdf"
        elif media == "message/rfc822":
            extraction = "email_plain_text"
            try:
                message = BytesParser(policy=policy.default).parsebytes(raw)
                parts, omitted, blocks, parse_defects = [], 0, [], 0
                for part in message.walk():
                    decoded_headers = list(part.items())
                    header_text = "\n".join(f"{name}: {value}" for name, value in decoded_headers)
                    block = header_text
                    if part.is_multipart():
                        pass
                    elif part.get_content_type() == "text/plain" and part.get_content_disposition() != "attachment":
                        body = part.get_content()
                        parts.append(body)
                        block += "\n\n" + body
                    else:
                        omitted += 1
                    blocks.append(block)
                    # Decoding a child body can add defects to that child rather
                    # than the root message. Headers also carry parser defects.
                    parse_defects += len(part.defects) + sum(len(getattr(value, "defects", ())) for _, value in decoded_headers)
                text = "\n\n".join(blocks)
                complete = bool(parts) and omitted == 0 and parse_defects == 0 and "\ufffd" not in text
                coverage.update(plain_text_parts=len(parts), omitted_parts=omitted, parse_defects=parse_defects,
                                header_blocks=len(blocks), includes_decoded_headers=True)
            except (ValueError, LookupError, UnicodeError, TypeError):
                coverage["limitation"] = "email_decode_failed"
        elif media in {"text/plain", "text/markdown", "text/csv", "application/json"}:
            extraction = "utf8"
            try:
                text = raw.decode("utf-8", errors="strict")
                complete = "\x00" not in text
                if not complete:
                    text = ""
                    coverage["limitation"] = "binary_text"
            except UnicodeDecodeError:
                coverage["limitation"] = "unsupported_text_encoding"
        else:
            coverage["limitation"] = "unsupported_visual_or_binary_source"
        coverage["full_text_sha256"] = sha256(text.encode()).hexdigest()
        coverage["characters_total"] = len(text)
        if len(text) > MAX_TEXT_CHARS:
            text, complete = text[:MAX_TEXT_CHARS], False
            coverage["limitation"] = "text_limit"
        coverage["characters_read"] = len(text)
        result = {"text": text, "text_sha256": sha256(text.encode()).hexdigest(),
                  "extraction": extraction, "complete": bool(complete), "coverage": coverage}
        with self._extraction_lock:
            if len(self._extractions) >= 128:
                self._extractions.pop(next(iter(self._extractions)))
            self._extractions[key] = deepcopy(result)
        return result

    def _source_receipt(self, descriptor):
        raw = self._validate_descriptor(descriptor, descriptor["claim_id"])
        return _seal({**descriptor, **self._extract(raw, descriptor["media_type"]),
                      "reader_id": "casepath.operational-source-reader/1.0.0"}, "receipt_sha256")

    def artifact(self, claim_id, artifact_id):
        state = self.get(claim_id)
        descriptor = next((d for d in state["source_descriptors"] if d["artifact_id"] == artifact_id), None)
        if descriptor is None:
            raise AutonomousStoreError("source is outside this claim")
        return self._validate_descriptor(descriptor, claim_id), descriptor

    def acquire(self, claim_id, artifact_id):
        """Read exact available bytes; only sources.acquired admits this receipt."""
        _, descriptor = self.artifact(claim_id, artifact_id)
        return self._source_receipt(descriptor)

    def intake(self, packet, idempotency_key):
        _identifier(idempotency_key, "idempotency key")
        _fields(packet, {"title", "message"}, {"files"})
        title = _text(packet["title"], "claim title", 300)
        message = _text(packet["message"], "claim message", 100_000)
        files = packet.get("files", [])
        if not isinstance(files, list) or len(files) > 20:
            raise AutonomousStoreError("at most twenty supporting files are allowed")
        parsed = [self._file(item) for item in files]
        message_raw = message.encode("utf-8")
        if sum(len(item[2]) for item in parsed) + len(message_raw) > MAX_PACKET_BYTES:
            raise AutonomousStoreError("intake packet is too large")
        claim_id = "auto_" + digest_value({"session": SESSION_ID, "idempotency_key": idempotency_key})[:24]
        descriptors = [self._descriptor(claim_id, "customer-message.txt", "text/plain", message_raw, "customer_message")]
        descriptors += [self._descriptor(claim_id, name, media, raw, "supporting_document") for name, media, raw in parsed]
        if len({d["artifact_id"] for d in descriptors}) != len(descriptors):
            raise AutonomousStoreError("duplicate intake source")
        source = self._source_receipt(descriptors[0])
        payload = {"title": title, "message": message, "sources": descriptors, "acquired_sources": [source]}
        return self.append(claim_id, "intake", payload, expected_revision=0, expected_state_sha256=None, idempotency_key=idempotency_key)

    def add_sources(self, claim_id, files, *, expected_revision, expected_state_sha256, idempotency_key):
        if not isinstance(files, list) or not 1 <= len(files) <= 20:
            raise AutonomousStoreError("supply one to twenty supporting files")
        self.get(claim_id)
        parsed = [self._file(item) for item in files]
        if sum(len(item[2]) for item in parsed) > MAX_PACKET_BYTES:
            raise AutonomousStoreError("source packet is too large")
        sources = [self._descriptor(claim_id, name, media, raw, "supporting_document") for name, media, raw in parsed]
        return self.append(claim_id, "sources.arrived", {"sources": sources}, expected_revision=expected_revision,
                           expected_state_sha256=expected_state_sha256, idempotency_key=idempotency_key)

    def _rows(self, connection, claim_id):
        _identifier(claim_id, "claim identity")
        return connection.execute("SELECT * FROM claim_loop_events WHERE session_id=? AND loop_id=? ORDER BY sequence",
                                  (SESSION_ID, "autonomous." + claim_id)).fetchall()

    def _graph(self, value, claim_id):
        if not isinstance(value, dict) or value.get("claim_id") != claim_id:
            raise AutonomousStoreError("graph belongs to another claim")
        try:
            # Sealing supplies defaults, but reject extra fields before sealing
            # can discard them. The accepted graph must already be canonical.
            validate_graph(value)
            sealed = seal_graph(value)
            if sealed != value:
                raise ValueError("graph must carry its exact canonical seal")
            assessment = evaluate(sealed)
        except (KeyError, TypeError, ValueError) as exc:
            raise AutonomousStoreError("invalid accepted graph: " + str(exc)) from exc
        if assessment["inconsistent_completed_node_ids"]:
            raise AutonomousStoreError("graph contains unsupported completed steps")
        return sealed, assessment

    @staticmethod
    def _bound_receipt(receipt, state, graph=None):
        expected = {"parent_revision": state["revision"], "parent_state_sha256": state["state_sha256"],
                    "before_graph_sha256": (state.get("graph") or {}).get("graph_sha256")}
        if graph is not None:
            expected["after_graph_sha256"] = graph["graph_sha256"]
        if any(key in receipt and receipt[key] != value for key, value in expected.items()):
            raise AutonomousStoreError("verification receipt is not bound to its parent or graph")

    @staticmethod
    def _graph_sources(graph, facts, sources):
        """Check provenance independently of the controller's semantic verifier."""
        available = {s["artifact_id"]: s for s in sources}
        records = [*facts, *graph["conditions"].values()]
        for record in records:
            if not isinstance(record, dict):
                raise AutonomousStoreError("fact record is invalid")
            citations = record.get("citations", [])
            if not isinstance(citations, list) or len(citations) > 100:
                raise AutonomousStoreError("fact citation roster is invalid")
            for citation in citations:
                source = available.get(citation.get("artifact_id")) if isinstance(citation, dict) else None
                quote = citation.get("quote") if isinstance(citation, dict) else None
                if source is None or not isinstance(quote, str) or not quote or quote not in source["text"]:
                    raise AutonomousStoreError("fact citation is not an acquired claim source")
                if citation.get("sha256", source["sha256"]) != source["sha256"] or citation.get("text_sha256", source["text_sha256"]) != source["text_sha256"]:
                    raise AutonomousStoreError("fact citation source hash differs")
                if "start_char" in citation or "end_char" in citation:
                    start, end = citation.get("start_char"), citation.get("end_char")
                    if type(start) is not int or type(end) is not int or start < 0 or end <= start or source["text"][start:end] != quote:
                        raise AutonomousStoreError("fact citation span differs")
        for document in graph["document_catalog"]:
            for item in document["held_files"]:
                source = available.get(item["artifact_id"])
                if source is None or item.get("sha256", source["sha256"]) != source["sha256"]:
                    raise AutonomousStoreError("graph document is not acquired in this claim")
                quote = item.get("source_quote", "")
                if not isinstance(quote, str):
                    raise AutonomousStoreError("graph document quote is invalid")
                if quote and quote not in source["text"]:
                    raise AutonomousStoreError("graph document quote differs from its source")
                if item.get("review") == "sufficient" and (not quote or not source["complete"] or source["role"] == "customer_message"):
                    raise AutonomousStoreError("document sufficiency requires a complete supporting source")

    def _reduce(self, state, event):
        kind, payload, claim_id = event["kind"], event["payload"], event["claim_id"]
        if state is None:
            if kind != "intake":
                raise AutonomousStoreError("journal must begin with intake")
            _fields(payload, {"title", "message", "sources", "acquired_sources"})
            sources = payload["sources"]
            if not isinstance(sources, list) or not 1 <= len(sources) <= 21:
                raise AutonomousStoreError("intake source roster is invalid")
            for descriptor in sources:
                self._validate_descriptor(descriptor, claim_id)
            if len({s["artifact_id"] for s in sources}) != len(sources) or sources[0]["role"] != "customer_message":
                raise AutonomousStoreError("intake source identities are invalid")
            _text(payload["message"], "claim message", 100_000)
            if self._blob(sources[0]["sha256"]) != payload["message"].encode():
                raise AutonomousStoreError("intake message differs from immutable source")
            if payload["acquired_sources"] != [self._source_receipt(sources[0])]:
                raise AutonomousStoreError("intake acquired source differs")
            state = {"contract": CONTRACT, "claim_id": claim_id, "title": _text(payload["title"], "title", 300),
                     "message": payload["message"], "status": "received", "source_descriptors": deepcopy(sources),
                     "acquired_sources": deepcopy(payload["acquired_sources"]), "graph": None, "evaluation": None,
                     "facts": [], "obligations": [], "actions": [], "results": [], "outcome": None,
                     "knowledge_uses": [], "knowledge_published": [], "events": [], "run_id": None,
                     "policy_id": None, "phase": "received", "deferral": None, "receipts": []}
            state["intake_receipt"] = _seal({"claim_id": claim_id, "packet_sha256": digest_value(payload),
                                              "source_roster_sha256": digest_value(sources)}, "receipt_sha256")
            state["source_roster_sha256"] = digest_value(sources)
        elif kind == "intake":
            raise AutonomousStoreError("claim already has an intake")
        else:
            state = deepcopy(state)
            if kind == "work.started":
                _fields(payload, {"run_id", "policy_id"})
                state.update(status="running", run_id=_identifier(payload["run_id"], "run id"),
                             policy_id=_text(payload["policy_id"], "policy id", 180), deferral=None, outcome=None)
            elif kind == "work.phase":
                _fields(payload, {"phase", "summary"})
                state.update(phase=_identifier(payload["phase"], "phase"), phase_summary=_text(payload["summary"], "phase summary"))
            elif kind == "work.context":
                _fields(payload, {"workflow_id", "context"})
                workflow = _identifier(payload["workflow_id"], "workflow id")
                context = payload["context"]
                if not isinstance(context, dict) or context.get("claim_id") != claim_id:
                    raise AutonomousStoreError("semantic context belongs to another claim")
                contexts = state.setdefault("semantic_contexts", {})
                if workflow in contexts:
                    raise AutonomousStoreError("semantic context is already frozen")
                contexts[workflow] = deepcopy(context)
            elif kind == "work.resumed":
                _fields(payload, {"reason"})
                _text(payload["reason"], "resume reason")
                if (state.get("deferral") or {}).get("code") != "paused":
                    raise AutonomousStoreError("only explicitly paused work can be resumed")
                state.update(status="running", phase="queued", deferral=None)
            elif kind == "sources.arrived":
                _fields(payload, {"sources"})
                sources = payload["sources"]
                if not isinstance(sources, list) or not 1 <= len(sources) <= 20:
                    raise AutonomousStoreError("source arrival roster is invalid")
                known = {s["artifact_id"] for s in state["source_descriptors"]}
                for descriptor in sources:
                    self._validate_descriptor(descriptor, claim_id)
                    if descriptor["artifact_id"] in known or descriptor["role"] != "supporting_document":
                        raise AutonomousStoreError("source arrival is duplicate or invalid")
                    known.add(descriptor["artifact_id"])
                if len(known) > 100:
                    raise AutonomousStoreError("claim source limit reached")
                state["source_descriptors"].extend(deepcopy(sources))
                state["source_roster_sha256"] = digest_value(state["source_descriptors"])
                if (state.get("deferral") or {}).get("code") != "paused":
                    state.update(status="received", phase="evidence_arrived", deferral=None, outcome=None)
            elif kind == "sources.acquired":
                _fields(payload, {"sources"})
                sources = payload["sources"]
                if not isinstance(sources, list) or not 1 <= len(sources) <= 20:
                    raise AutonomousStoreError("source acquisition roster is invalid")
                known = {s["artifact_id"]: s for s in state["source_descriptors"]}
                acquired = {s["artifact_id"] for s in state["acquired_sources"]}
                for receipt in sources:
                    descriptor = known.get(receipt.get("artifact_id")) if isinstance(receipt, dict) else None
                    if descriptor is None or receipt != self._source_receipt(descriptor):
                        raise AutonomousStoreError("source acquisition receipt differs from exact claim bytes")
                    if receipt["artifact_id"] in acquired:
                        raise AutonomousStoreError("source already acquired")
                    acquired.add(receipt["artifact_id"])
                    state["acquired_sources"].append(deepcopy(receipt))
            elif kind in {"process.prepared", "interpretation.accepted"}:
                _fields(payload, {"graph", "facts", "obligations", "receipt"})
                _receipt(payload["receipt"], interpretation=kind == "interpretation.accepted")
                if any(not isinstance(payload[field], list) or len(payload[field]) > 200 for field in ("facts", "obligations")):
                    raise AutonomousStoreError("fact or obligation roster is invalid")
                graph, evaluation = self._graph(payload["graph"], claim_id)
                self._bound_receipt(payload["receipt"], state, graph)
                self._graph_sources(graph, payload["facts"], state["acquired_sources"])
                state.update(graph=graph, evaluation=evaluation, facts=deepcopy(payload["facts"]), obligations=deepcopy(payload["obligations"]))
                state["receipts"].append({"kind": kind, "receipt": deepcopy(payload["receipt"])})
            elif kind == "action.completed":
                _fields(payload, {"graph", "result", "receipt"})
                _receipt(payload["receipt"])
                if not isinstance(payload["result"], dict) or not payload["result"]:
                    raise AutonomousStoreError("action result is invalid")
                graph, evaluation = self._graph(payload["graph"], claim_id)
                self._bound_receipt(payload["receipt"], state, graph)
                facts = graph["assessment_context"].get("facts", state["facts"])
                obligations = graph["assessment_context"].get("obligations", state["obligations"])
                if any(not isinstance(value, list) or len(value) > 200 for value in (facts, obligations)):
                    raise AutonomousStoreError("action fact or obligation roster is invalid")
                self._graph_sources(graph, facts, state["acquired_sources"])
                state.update(graph=graph, evaluation=evaluation, facts=deepcopy(facts), obligations=deepcopy(obligations))
                result = deepcopy(payload["result"])
                state["actions"].append({"result": result, "receipt": deepcopy(payload["receipt"])})
                state["results"].append(result)
            elif kind == "outcome.recorded":
                _fields(payload, {"outcome", "receipt"})
                _receipt(payload["receipt"])
                self._bound_receipt(payload["receipt"], state)
                outcome = payload["outcome"]
                if not isinstance(outcome, dict) or outcome.get("status") not in {"resolved", "deferred"}:
                    raise AutonomousStoreError("outcome must be resolved or deferred")
                if outcome["status"] == "resolved" and (state["evaluation"] is None or state["evaluation"]["process_status"] != "complete"):
                    raise AutonomousStoreError("resolution requires a complete verified process")
                state.update(status=outcome["status"], phase=outcome["status"], outcome=deepcopy(outcome))
                state["receipts"].append({"kind": kind, "receipt": deepcopy(payload["receipt"])})
            elif kind in {"knowledge.used", "knowledge.published"}:
                _fields(payload, {"knowledge"})
                if not isinstance(payload["knowledge"], dict) or not payload["knowledge"]:
                    raise AutonomousStoreError("knowledge receipt is invalid")
                state["knowledge_uses" if kind == "knowledge.used" else "knowledge_published"].append(deepcopy(payload["knowledge"]))
            elif kind == "work.deferred":
                _fields(payload, {"reason", "code"}, {"details"})
                _text(payload["reason"], "deferral reason", 2000)
                _identifier(payload["code"], "deferral code")
                state.update(status="deferred", phase="deferred", deferral=deepcopy(payload))
            else:
                raise AutonomousStoreError("unsupported autonomous event kind")
        state.update(revision=event["sequence"], last_event_sha256=event["event_sha256"], updated_at=event["created_at"])
        state["events"].append({k: event[k] for k in ("sequence", "kind", "created_at", "event_sha256")})
        state.pop("state_sha256", None)
        return _seal(state, "state_sha256")

    def _replay(self, rows, *, with_history=False):
        state, events, states = None, [], []
        previous = None
        for sequence, row in enumerate(rows, 1):
            try:
                event = json.loads(row["event_json"])
                material = {k: v for k, v in event.items() if k not in {"event_sha256", "resulting_state_sha256"}}
                command = {k: event[k] for k in ("kind", "payload", "expected_revision", "expected_state_sha256")}
                if (event["contract"] != EVENT_CONTRACT or row["session_id"] != SESSION_ID
                    or row["loop_id"] != "autonomous." + event["claim_id"] or event["session_id"] != SESSION_ID
                    or event["sequence"] != sequence or row["sequence"] != sequence
                    or event["previous_event_sha256"] != previous or event["expected_revision"] != sequence - 1
                    or event["expected_state_sha256"] != (state["state_sha256"] if state else None)
                    or event["command_sha256"] != digest_value(command) or row["command_sha256"] != event["command_sha256"]
                    or event["event_sha256"] != digest_value(material) or row["event_sha256"] != event["event_sha256"]
                    or row["idempotency_key"] != event["idempotency_key"] or row["created_at"] != event["created_at"]):
                    raise AutonomousStoreError("journal event identity or hash differs")
                state = self._reduce(state, event)
                if state["state_sha256"] != event["resulting_state_sha256"]:
                    raise AutonomousStoreError("journal resulting state differs")
                previous = event["event_sha256"]
                events.append(event)
                if with_history:
                    states.append(state)
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                raise AutonomousStoreError("journal event is malformed") from exc
        if state:
            for descriptor in state["source_descriptors"]:
                self._validate_descriptor(descriptor, state["claim_id"])
        return state, events, states

    def get(self, claim_id):
        with self.journal.connect() as connection:
            state, _, _ = self._replay(self._rows(connection, claim_id))
        if state is None:
            raise AutonomousStoreError("claim does not exist")
        return state

    def list(self, *, statuses=None):
        with self.journal.connect() as connection:
            rows = connection.execute("SELECT DISTINCT loop_id FROM claim_loop_events WHERE session_id=? ORDER BY loop_id", (SESSION_ID,)).fetchall()
            values = [self._replay(self._rows(connection, row["loop_id"].removeprefix("autonomous.")))[0] for row in rows]
        return [s for s in values if statuses is None or s["status"] in statuses]

    def events(self, claim_id, after=0):
        if type(after) is not int or after < 0:
            raise AutonomousStoreError("event cursor is invalid")
        with self.journal.connect() as connection:
            state, events, _ = self._replay(self._rows(connection, claim_id))
        if state is None:
            raise AutonomousStoreError("claim does not exist")
        return events[after:]

    def append(self, claim_id, kind, payload, *, expected_revision, expected_state_sha256, idempotency_key):
        if self._read_only:
            raise AutonomousStoreError("read-only replay cannot append events")
        _identifier(claim_id, "claim identity")
        _identifier(kind, "event kind")
        _identifier(idempotency_key, "idempotency key")
        if type(expected_revision) is not int or expected_revision < 0:
            raise AutonomousStoreError("expected revision is invalid")
        payload = _copy(payload)
        command = {"kind": kind, "payload": payload, "expected_revision": expected_revision, "expected_state_sha256": expected_state_sha256}
        command_hash = digest_value(command)
        with self.journal.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = self._rows(connection, claim_id)
            state, events, states = self._replay(rows, with_history=True)
            existing = next((e for e in events if e["idempotency_key"] == idempotency_key), None)
            if existing:
                if existing["command_sha256"] != command_hash:
                    raise AutonomousStoreError("idempotency key binds different input")
                return deepcopy(states[existing["sequence"] - 1])
            if expected_revision != len(events) or expected_state_sha256 != (state["state_sha256"] if state else None):
                raise AutonomousStoreError("stale claim revision or state hash")
            if len(events) >= 2000:
                raise AutonomousStoreError("claim event limit reached")
            event = _seal({"contract": EVENT_CONTRACT, "session_id": SESSION_ID, "claim_id": claim_id,
                           **command, "sequence": expected_revision + 1, "command_sha256": command_hash,
                           "idempotency_key": idempotency_key, "previous_event_sha256": state["last_event_sha256"] if state else None,
                           "created_at": datetime.now(timezone.utc).isoformat()}, "event_sha256")
            result = self._reduce(state, event)
            event["resulting_state_sha256"] = result["state_sha256"]
            connection.execute("INSERT INTO claim_loop_events (session_id,loop_id,sequence,idempotency_key,command_sha256,event_sha256,event_json,created_at) VALUES (?,?,?,?,?,?,?,?)",
                               (SESSION_ID, "autonomous." + claim_id, event["sequence"], idempotency_key, command_hash,
                                event["event_sha256"], json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")), event["created_at"]))
            return result
