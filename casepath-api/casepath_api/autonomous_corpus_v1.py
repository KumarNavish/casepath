"""Read-only canonical originals for the autonomous product.

The immutable intake bundle owns source identity, not handling progress. Merely
listing, opening or extracting a preview creates no journal event or admitted
evidence. Only an explicit engine command may consume ``packet`` for admission.
No source registry, policy, navigation label or reference graph is consulted.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from hashlib import sha256
import re
from threading import RLock

from .autonomous_store_v1 import AutonomousStore, CONTRACT, SOURCE_CONTRACT
from .autonomous_taxonomy_v1 import DOMAIN_LABELS, TAXONOMY
from .workspace_corpus import (
    PublicCorpus, WORKSPACE_CORPUS_ID, WorkspaceCorpusError,
    default_workspace_corpus_root, digest_value,
)


ORIGINAL_BINDING_CONTRACT = "casepath.autonomous-original-binding/1.0.0"
_CLAIM_ID = re.compile(r"^clm_[0-9a-f]{16}$")
_FILE_FIELDS = frozenset({
    "artifact_id", "content_base64", "file_name", "media_type", "sha256", "size_bytes",
})
_SUBMISSION_FIELDS = frozenset({"canton", "channel", "claim_id", "language", "received_at"})
_MESSAGE_FIELDS = frozenset({
    "attachment_ids", "body", "from_role", "message_id", "raw_file", "sent_at", "subject", "to_role",
})


def _seal(value, key):
    return {**value, key: digest_value(value)}


def _file_metadata(value):
    """Project the original file metadata without retaining a second byte copy."""
    if not isinstance(value, dict) or set(value) != _FILE_FIELDS:
        raise WorkspaceCorpusError("original observable file fields differ")
    try:
        raw = base64.b64decode(value["content_base64"], validate=True)
    except (ValueError, TypeError) as exc:
        raise WorkspaceCorpusError("original observable file encoding differs") from exc
    if (type(value["size_bytes"]) is not int or len(raw) != value["size_bytes"]
            or sha256(raw).hexdigest() != value["sha256"]
            or base64.b64encode(raw).decode() != value["content_base64"]):
        raise WorkspaceCorpusError("original observable file identity differs")
    return {k: deepcopy(v) for k, v in value.items() if k != "content_base64"}


class CanonicalCorpus:
    """Immutable 150-case adapter; returned values are independent public copies.

    Metadata and revision-zero states are built once from observable claims.
    Every read checks the existing PublicCorpus inventory guard; summaries never
    read complete histories, extract content or reevaluate policy. Source bytes
    are read and hash checked only for downloads, previews or explicit packets.
    """

    def __init__(self, corpus: PublicCorpus | None = None):
        self._corpus = corpus if corpus is not None else PublicCorpus(default_workspace_corpus_root())
        if not isinstance(self._corpus, PublicCorpus) or self._corpus.corpus_id != WORKSPACE_CORPUS_ID:
            raise WorkspaceCorpusError("canonical collection requires the original synthetic-150 corpus")
        identity = self._corpus.identity
        if identity["claim_count"] != 150:
            raise WorkspaceCorpusError("canonical collection must contain all 150 originals")
        self._identity_token = self._corpus.runtime_identity_token()
        self._bindings = deepcopy(self._corpus.bindings)
        self._ids = tuple(sorted(self._bindings))
        if len(self._ids) != 150 or any(not _CLAIM_ID.fullmatch(cid) for cid in self._ids):
            raise WorkspaceCorpusError("canonical original claim identities differ")
        self._states, self._sources, self._summaries = {}, {}, []
        # The existing reader is a pure extraction cache. Deliberately avoid its
        # constructor, which creates journal/source directories for a real store.
        self._reader = AutonomousStore.__new__(AutonomousStore)
        self._reader._read_only = True
        self._reader._extractions, self._reader._extraction_lock = {}, RLock()
        for claim_id in self._ids:
            self._prepare(claim_id, identity)
        self._guard()

    def _guard(self):
        # Cached canonical metadata must detect edits immediately, including
        # while a running file watcher is waiting to deliver a debounced change.
        if self._corpus.runtime_identity_token() != self._identity_token:
            raise WorkspaceCorpusError("canonical corpus identity differs after initialization")

    @property
    def ids(self):
        self._guard()
        return self._ids

    @property
    def bindings(self):
        self._guard()
        return deepcopy(self._bindings)

    def contains(self, claim_id):
        if not isinstance(claim_id, str) or claim_id not in self._bindings:
            return False
        self._guard()
        return True

    def _require(self, claim_id):
        self._guard()
        if not isinstance(claim_id, str) or claim_id not in self._states:
            raise WorkspaceCorpusError("claim is outside the canonical original collection")

    def _prepare(self, claim_id, identity):
        binding = self._corpus.binding(claim_id)
        claim = self._corpus.claim(claim_id)
        submission, message, attachments = (claim.get(k) for k in (
            "submission", "customer_message", "attachments"))
        if (not isinstance(submission, dict) or set(submission) != _SUBMISSION_FIELDS
                or submission["claim_id"] != claim_id
                or not isinstance(message, dict) or set(message) != _MESSAGE_FIELDS
                or not isinstance(attachments, list) or len(attachments) > 2
                or not isinstance(message["body"], str) or not message["body"].strip()
                or len(message["body"]) > 100_000):
            raise WorkspaceCorpusError("canonical observable intake fields differ")
        if (message["subject"] != binding["subject"] or message["message_id"] != binding["message_id"]
                or submission["language"] != binding["language"]
                or submission["received_at"] != binding["received_at"]):
            raise WorkspaceCorpusError("canonical observable metadata differs from its binding")
        original_files = [_file_metadata(message["raw_file"])] + [_file_metadata(row) for row in attachments]
        if (message["message_id"] != original_files[0]["artifact_id"]
                or message["attachment_ids"] != [row["artifact_id"] for row in original_files[1:]]
                or len({row["artifact_id"] for row in original_files}) != len(original_files)):
            raise WorkspaceCorpusError("canonical original attachment relationships differ")
        observable = binding["observable_artifacts"]
        if not isinstance(observable, list) or len(observable) != len(original_files):
            raise WorkspaceCorpusError("canonical original source roster differs")
        sources, mapping, lookup = [], [], {}
        for index, (original, bound) in enumerate(zip(original_files, observable, strict=True)):
            original_role = "customer_message" if index == 0 else "attachment"
            if (bound.get("role") != original_role
                    or any(bound.get(k) != original[k] for k in original)):
                raise WorkspaceCorpusError("canonical native source differs from its binding")
            source_identity = {"claim_id": claim_id, "file_name": original["file_name"],
                               "media_type": original["media_type"], "sha256": original["sha256"],
                               "role": "customer_message" if index == 0 else "supporting_document"}
            descriptor = _seal({"contract": SOURCE_CONTRACT, **source_identity,
                                "size_bytes": original["size_bytes"],
                                "artifact_id": "src_" + digest_value(source_identity)[:32]}, "descriptor_sha256")
            if descriptor["artifact_id"] in lookup:
                raise WorkspaceCorpusError("canonical native source identity is duplicated")
            sources.append(descriptor)
            mapping.append({"original_artifact_id": original["artifact_id"],
                            "artifact_id": descriptor["artifact_id"], "sha256": descriptor["sha256"]})
            entry = (deepcopy(bound), descriptor)
            lookup[original["artifact_id"]] = lookup[descriptor["artifact_id"]] = entry
        intake_message = {k: deepcopy(v) for k, v in message.items() if k != "raw_file"}
        intake_message["raw_file"] = original_files[0]
        original_binding = _seal({
            "contract": ORIGINAL_BINDING_CONTRACT, "claim_id": claim_id,
            "corpus_id": self._corpus.corpus_id,
            "corpus_manifest_sha256": identity["manifest_sha256"],
            "claim_binding_sha256": binding["binding_sha256"],
            "static_template_sha256": binding["static_template_sha256"],
            "intake": {"submission": deepcopy(submission), "customer_message": intake_message,
                       "attachments": original_files[1:]},
            "source_map": mapping,
        }, "original_binding_sha256")
        state = {
            "contract": CONTRACT, "claim_id": claim_id, "title": message["subject"],
            "message": message["body"], "status": "not_started", "phase": "not_run",
            "mode": "unprocessed", "corpus_id": self._corpus.corpus_id,
            "original_binding": original_binding, "source_descriptors": sources,
            "source_roster_sha256": digest_value(sources), "acquired_sources": [],
            "graph": None, "evaluation": None, "facts": [], "obligations": [], "actions": [],
            "results": [], "outcome": None, "knowledge_uses": [], "knowledge_published": [],
            "events": [], "run_id": None, "policy_id": None, "deferral": None, "receipts": [],
            "intake_receipt": None, "revision": 0, "last_event_sha256": None, "updated_at": None,
        }
        self._states[claim_id] = _seal(state, "state_sha256")
        self._sources[claim_id] = lookup
        self._summaries.append({
            **{key: self._states[claim_id][key] for key in (
                "claim_id", "title", "status", "phase", "mode", "corpus_id", "revision",
                "state_sha256", "updated_at", "outcome")},
            "received_at": submission["received_at"], "language": submission["language"],
            "channel": submission["channel"], "source_count": len(sources),
            "attachment_count": len(attachments), "claim_binding_sha256": binding["binding_sha256"],
        })

    def preview_state(self, claim_id):
        self._require(claim_id)
        return deepcopy(self._states[claim_id])

    def summary_rows(self):
        self._guard()
        if set(TAXONOMY) != set(self._ids):
            raise WorkspaceCorpusError("browsing taxonomy differs from the canonical binding roster")
        rows = deepcopy(self._summaries)
        # Navigation labels and concise original-body excerpts are summary-only
        # projections. They never enter state hashes, bindings or engine packets.
        for row in rows:
            taxonomy = TAXONOMY[row["claim_id"]]
            row["browse_metadata"] = {"domain": taxonomy["domain"], "family_id": taxonomy["family_id"],
                                      "domain_label": DOMAIN_LABELS[taxonomy["domain"]], "browsing_only": True}
            row["source_preview"] = self._states[row["claim_id"]]["message"][:240]
        return rows

    def artifact(self, claim_id, artifact_id):
        """Return exact native bytes for either original or stable engine ID."""
        self._require(claim_id)
        if not isinstance(artifact_id, str) or artifact_id not in self._sources[claim_id]:
            raise WorkspaceCorpusError("source is outside the canonical claim binding")
        bound, descriptor = self._sources[claim_id][artifact_id]
        raw, current = self._corpus.artifact(claim_id, bound["artifact_id"])
        if (current != bound or len(raw) != descriptor["size_bytes"]
                or sha256(raw).hexdigest() != descriptor["sha256"]):
            raise WorkspaceCorpusError("canonical source differs from its original binding")
        return raw, deepcopy(descriptor)

    def packet(self, claim_id):
        """Server-only admission input; constructing it performs no admission."""
        state = self.preview_state(claim_id)
        return {"title": state["title"], "message": state["message"],
                "sources": state["source_descriptors"], "original_binding": state["original_binding"],
                "initial_state_sha256": state["state_sha256"],
                "source_bytes": {source["artifact_id"]: self.artifact(claim_id, source["artifact_id"])[0]
                                 for source in state["source_descriptors"]}}

    def source_preview(self, claim_id, artifact_id):
        """Derive a bounded preview, with no evidence-admission receipt."""
        raw, descriptor = self.artifact(claim_id, artifact_id)
        extraction = self._reader._extract(raw, descriptor["media_type"].split(";", 1)[0].strip().lower())
        state = self._states[claim_id]
        original = next(row["original_artifact_id"] for row in state["original_binding"]["source_map"]
                        if row["artifact_id"] == descriptor["artifact_id"])
        return _seal({**descriptor, **extraction, "reader_id": "casepath.operational-source-reader/1.0.0",
                      "original_artifact_id": original, "preview_only": True, "evidence_admitted": False,
                      "original_binding_sha256": state["original_binding"]["original_binding_sha256"]}, "preview_sha256")
