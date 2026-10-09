"""Canonical originals are browsing inputs, never implicit lifecycle events."""
from copy import deepcopy
from email import policy
from email.parser import BytesParser
from hashlib import sha256
from collections import Counter
import json
import os
from pathlib import Path

import pytest

from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.autonomous_store_v1 import AutonomousStore, SOURCE_CONTRACT
from casepath_api.workspace_corpus import (
    PublicCorpus, WorkspaceCorpusError, default_public_corpus_root,
    default_workspace_corpus_root, digest_value,
)


@pytest.fixture(scope="module")
def public():
    return PublicCorpus(default_workspace_corpus_root())


@pytest.fixture(scope="module")
def canonical(public):
    return CanonicalCorpus(public)


def _public_keys(value):
    if isinstance(value, dict):
        return set(value).union(*(_public_keys(child) for child in value.values()))
    if isinstance(value, (list, tuple)):
        return set().union(*(_public_keys(child) for child in value))
    return set()


def test_all_150_previews_are_source_bound_and_never_investigated(public, canonical):
    assert canonical.ids == tuple(sorted(public.bindings))
    assert len(canonical.ids) == 150
    for claim_id in canonical.ids:
        original = public.claim(claim_id)
        state = canonical.preview_state(claim_id)
        assert state["claim_id"] == claim_id
        assert state["title"] == original["customer_message"]["subject"]
        assert state["message"] == original["customer_message"]["body"]
        assert (state["revision"], state["status"], state["phase"], state["mode"]) == (
            0, "not_started", "not_run", "unprocessed")
        assert state["graph"] is state["evaluation"] is None
        assert state["intake_receipt"] is None
        assert state["last_event_sha256"] is None
        assert all(state[key] == [] for key in (
            "acquired_sources", "facts", "obligations", "actions", "results", "events",
            "knowledge_uses", "knowledge_published", "receipts"))
        assert state["state_sha256"] == digest_value({
            k: v for k, v in state.items() if k != "state_sha256"})
        bound = state["original_binding"]
        assert bound["claim_binding_sha256"] == public.binding(claim_id)["binding_sha256"]
        assert bound["original_binding_sha256"] == digest_value({
            k: v for k, v in bound.items() if k != "original_binding_sha256"})


def test_all_original_artifact_bytes_media_and_relationships_survive(public, canonical):
    messages, attachments, media = 0, 0, {}
    for claim_id in canonical.ids:
        original = public.claim(claim_id)
        state = canonical.preview_state(claim_id)
        intake = state["original_binding"]["intake"]
        assert intake["submission"] == original["submission"]
        expected_message = deepcopy(original["customer_message"])
        expected_message["raw_file"].pop("content_base64")
        assert intake["customer_message"] == expected_message
        expected_attachments = deepcopy(original["attachments"])
        for row in expected_attachments:
            row.pop("content_base64")
        assert intake["attachments"] == expected_attachments
        assert intake["customer_message"]["attachment_ids"] == [
            row["artifact_id"] for row in intake["attachments"]]
        assert len(state["source_descriptors"]) == 1 + len(expected_attachments)
        source_map = state["original_binding"]["source_map"]
        for row, descriptor, mapping in zip(public.binding(claim_id)["observable_artifacts"],
                                             state["source_descriptors"], source_map, strict=True):
            raw, original_row = public.artifact(claim_id, row["artifact_id"])
            assert canonical.artifact(claim_id, row["artifact_id"]) == (raw, descriptor)
            assert canonical.artifact(claim_id, descriptor["artifact_id"]) == (raw, descriptor)
            assert descriptor["contract"] == SOURCE_CONTRACT
            assert descriptor["file_name"] == original_row["file_name"]
            assert descriptor["media_type"] == original_row["media_type"]
            assert descriptor["sha256"] == sha256(raw).hexdigest() == mapping["sha256"]
            assert descriptor["size_bytes"] == len(raw)
            identity = {k: descriptor[k] for k in ("claim_id", "file_name", "media_type", "sha256", "role")}
            assert descriptor["artifact_id"] == "src_" + digest_value(identity)[:32]
            assert mapping == {"artifact_id": descriptor["artifact_id"],
                               "original_artifact_id": row["artifact_id"], "sha256": row["sha256"]}
            if row["role"] == "customer_message":
                messages += 1
            else:
                attachments += 1
                media[row["media_type"]] = media.get(row["media_type"], 0) + 1
    assert (messages, attachments) == (150, 57)
    assert media == {"application/pdf": 47, "image/jpeg": 10}


def test_packet_uses_original_native_sources_and_has_no_admission(public, canonical):
    for claim_id in canonical.ids:
        packet = canonical.packet(claim_id)
        state = canonical.preview_state(claim_id)
        assert set(packet) == {"title", "message", "sources", "original_binding", "source_bytes", "initial_state_sha256"}
        assert packet["title"] == state["title"]
        assert packet["message"] == state["message"]
        assert packet["sources"] == state["source_descriptors"]
        assert packet["original_binding"] == state["original_binding"]
        assert packet["initial_state_sha256"] == state["state_sha256"]
        assert not {"browse_metadata", "browsing_only", "source_preview", "domain", "domain_label", "family_id"}.intersection(
            _public_keys(packet) | _public_keys(state))
        assert set(packet["source_bytes"]) == {row["artifact_id"] for row in packet["sources"]}
        for descriptor in packet["sources"]:
            raw = packet["source_bytes"][descriptor["artifact_id"]]
            assert raw == canonical.artifact(claim_id, descriptor["artifact_id"])[0]
            assert sha256(raw).hexdigest() == descriptor["sha256"]
        assert canonical.preview_state(claim_id) == state


def test_native_email_headers_previewed_without_an_evidence_receipt(public, canonical):
    claim_id = next(cid for cid in canonical.ids
                    if public.binding(cid)["observable_artifacts"][0]["media_type"] == "message/rfc822")
    state = canonical.preview_state(claim_id)
    descriptor = state["source_descriptors"][0]
    raw, _ = canonical.artifact(claim_id, descriptor["artifact_id"])
    mail = BytesParser(policy=policy.default).parsebytes(raw)
    preview = canonical.source_preview(claim_id, descriptor["artifact_id"])
    assert preview["preview_only"] is True
    assert preview["evidence_admitted"] is False
    assert "receipt_sha256" not in preview
    assert preview["sha256"] == sha256(raw).hexdigest()
    assert preview["extraction"] == "email_plain_text"
    for header in ("From", "To", "Subject", "Date", "Message-ID"):
        if mail[header] is not None:
            assert str(mail[header]) in preview["text"]
    assert canonical.preview_state(claim_id) == state


def test_text_charset_and_visual_limits_are_explicit(public, canonical):
    text_claim = next(cid for cid in canonical.ids if
                      public.binding(cid)["observable_artifacts"][0]["media_type"].startswith("text/plain;"))
    source = canonical.preview_state(text_claim)["source_descriptors"][0]
    raw, _ = canonical.artifact(text_claim, source["artifact_id"])
    preview = canonical.source_preview(text_claim, source["artifact_id"])
    assert preview["media_type"] == source["media_type"]
    assert preview["text"] == raw.decode("utf-8")
    assert preview["extraction"] == "utf8"
    image_claim, image = next((cid, row) for cid in canonical.ids
                             for row in canonical.preview_state(cid)["source_descriptors"]
                             if row["media_type"] == "image/jpeg")
    image_preview = canonical.source_preview(image_claim, image["artifact_id"])
    assert image_preview["complete"] is False
    assert image_preview["coverage"]["visual_interpretation_performed"] is False
    assert image_preview["coverage"]["limitation"] == "unsupported_visual_or_binary_source"
    assert canonical.preview_state(image_claim)["acquired_sources"] == []


def test_collection_is_cached_metadata_without_extraction_or_registry(public, monkeypatch):
    monkeypatch.setattr(public, "source_registry", lambda *_: pytest.fail("registry is not operational intake"))
    monkeypatch.setattr(public, "static_policy", lambda *_: pytest.fail("browsing cannot evaluate policy"))
    adapter = CanonicalCorpus(public)
    monkeypatch.setattr(public, "claim", lambda *_: pytest.fail("warm summaries cannot reload claim bodies"))
    monkeypatch.setattr(public, "artifact", lambda *_: pytest.fail("summaries cannot read source bytes"))
    monkeypatch.setattr(adapter._reader, "_extract", lambda *_: pytest.fail("browsing cannot extract"))
    for _ in range(2):
        rows = adapter.summary_rows()
        assert len(rows) == 150
        for row in rows:
            state = adapter.preview_state(row["claim_id"])
            assert row["state_sha256"] == state["state_sha256"]
            assert row["source_count"] == len(state["source_descriptors"])
            assert row["attachment_count"] == row["source_count"] - 1
            assert row["channel"] == state["original_binding"]["intake"]["submission"]["channel"]


def test_browsing_never_constructs_a_journal_or_invokes_admission(public, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("read-only browsing invoked a store mutation")
    for name in ("__init__", "_publish", "intake", "append", "acquire"):
        monkeypatch.setattr(AutonomousStore, name, forbidden)
    adapter = CanonicalCorpus(public)
    before = adapter.summary_rows()
    for cid in adapter.ids:
        state = adapter.preview_state(cid)
        for source in state["source_descriptors"]:
            preview = adapter.source_preview(cid, source["artifact_id"])
            assert preview["preview_only"] is True
            assert preview["evidence_admitted"] is False
            assert "receipt_sha256" not in preview
            assert preview["text_sha256"] == sha256(preview["text"].encode()).hexdigest()
        assert adapter.preview_state(cid) == state
    assert adapter.summary_rows() == before


def test_nonobservable_top_level_fields_cannot_enter_the_operational_packet(public, monkeypatch):
    original_claim = public.claim
    def with_nonobservable_fields(cid):
        claim = original_claim(cid)
        claim.update(split="sealed", gold={"expected": "invented answer"},
                     evaluation={"score": 1}, reference_graph={"nodes": ["fabricated"]},
                     domain="navigation only", scenario_family="navigation only")
        return claim
    monkeypatch.setattr(public, "claim", with_nonobservable_fields)
    adapter = CanonicalCorpus(public)
    for cid in adapter.ids:
        intake = adapter.preview_state(cid)["original_binding"]["intake"]
        assert set(intake) == {"submission", "customer_message", "attachments"}
        assert not {"split", "gold", "evaluation", "reference_graph", "domain", "scenario_family"}.intersection(intake)
    bad_claim = original_claim(adapter.ids[0])
    bad_claim["submission"]["split"] = "sealed"
    monkeypatch.setattr(public, "claim", lambda *_: deepcopy(bad_claim))
    with pytest.raises(WorkspaceCorpusError):
        CanonicalCorpus(public)


def test_unknown_and_cross_claim_ids_fail_closed(canonical):
    claim_id, other = canonical.ids[:2]
    foreign = canonical.preview_state(other)["source_descriptors"][0]["artifact_id"]
    assert canonical.contains(claim_id) is True
    for unknown in ("auto_historical", "clm_missing", "../manifest.json", None, []):
        assert canonical.contains(unknown) is False
        with pytest.raises(WorkspaceCorpusError):
            canonical.preview_state(unknown)
        with pytest.raises(WorkspaceCorpusError):
            canonical.packet(unknown)
    for unknown_source in (foreign, "source_missing", "../manifest.json", None, []):
        with pytest.raises(WorkspaceCorpusError):
            canonical.artifact(claim_id, unknown_source)


def test_returns_copies_and_identity_is_deterministic(public, canonical):
    cid = canonical.ids[0]
    before = canonical.preview_state(cid)
    changed = canonical.preview_state(cid)
    changed["original_binding"]["intake"]["customer_message"]["body"] = "caller rewrite"
    changed["source_descriptors"].clear()
    bindings = canonical.bindings
    bindings[cid]["subject"] = "caller rewrite"
    canonical.summary_rows()[0]["title"] = "caller rewrite"
    assert canonical.preview_state(cid) == before
    another = CanonicalCorpus(public)
    assert another.preview_state(cid) == before
    assert another.summary_rows() == canonical.summary_rows()


@pytest.mark.parametrize("stale_watcher_token", [False, True])
def test_cached_projection_rejects_changed_original_bytes(tmp_path, writable_corpus_copy,
                                                         monkeypatch, stale_watcher_token):
    root = writable_corpus_copy(default_workspace_corpus_root(), tmp_path / "corpus")
    public = PublicCorpus(root)
    if stale_watcher_token:
        # Model the watcher's debounce window: its observed token still says
        # unchanged while the synchronous immutable inventory sees the edit.
        monkeypatch.setattr(public, "observed_runtime_identity_token",
                            lambda: public.admitted_runtime_identity_token)
    adapter = CanonicalCorpus(public)
    cid = adapter.ids[0]
    source = adapter.preview_state(cid)["source_descriptors"][0]
    receipt = adapter.bindings[cid]["observable_artifacts"][0]
    file = root / receipt["path"]
    metadata = file.stat()
    raw = file.read_bytes()
    file.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    os.utime(file, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
    for read in (adapter.summary_rows, lambda: adapter.preview_state(cid),
                 lambda: adapter.artifact(cid, source["artifact_id"]), lambda: adapter.packet(cid)):
        with pytest.raises(WorkspaceCorpusError):
            read()


def test_legacy_60_profile_cannot_be_silently_used_as_complete():
    with pytest.raises(WorkspaceCorpusError):
        CanonicalCorpus(PublicCorpus(default_public_corpus_root()))


def test_taxonomy_is_exact_authorized_manifest_projection_and_immutable(canonical):
    from casepath_api.autonomous_taxonomy_v1 import (
        DOMAIN_LABELS, SOURCE_MANIFEST_SHA256, SOURCE_PROVENANCE, TAXONOMY,
    )
    source = Path(__file__).resolve().parents[2] / "data/casepath-tenancy-claims/benchmark/manifest.json"
    raw = source.read_bytes()
    assert sha256(raw).hexdigest() == SOURCE_MANIFEST_SHA256 == (
        "638630886a1d291dfe9009839eb0519130e56700bb4d454277ce2e45c6044f4c")
    # Only these three explicitly authorized source fields are inspected.
    projected = [{key: row[key] for key in ("case_id", "domain", "family_id")}
                 for row in json.loads(raw)["cases"]]
    assert len(projected) == len({row["case_id"] for row in projected}) == 150
    assert dict(TAXONOMY) == {row["case_id"]: {key: row[key] for key in ("domain", "family_id")}
                              for row in projected}
    assert set(TAXONOMY) == set(canonical.ids)
    assert Counter(row["domain"] for row in TAXONOMY.values()) == {
        "defect_mold_heating": 50, "lease_termination_dispute": 50, "rent_increase_dispute": 50}
    assert len({row["family_id"] for row in TAXONOMY.values()}) == 28
    assert dict(DOMAIN_LABELS) == {"defect_mold_heating": "Defects & repairs",
                                  "lease_termination_dispute": "Lease termination",
                                  "rent_increase_dispute": "Rent changes"}
    assert SOURCE_PROVENANCE["source_manifest_file_sha256"] == SOURCE_MANIFEST_SHA256
    assert SOURCE_PROVENANCE["projected_case_fields"] == ("case_id", "domain", "family_id")
    assert SOURCE_PROVENANCE["browsing_only"] is True
    with pytest.raises(TypeError):
        TAXONOMY[canonical.ids[0]]["domain"] = "caller rewrite"
    with pytest.raises(TypeError):
        TAXONOMY["made-up-id"] = {}
    with pytest.raises(TypeError):
        SOURCE_PROVENANCE["browsing_only"] = False


def test_browsing_taxonomy_and_short_source_preview_are_summary_only(canonical):
    from casepath_api.autonomous_taxonomy_v1 import DOMAIN_LABELS, TAXONOMY
    rows = canonical.summary_rows()
    for row in rows:
        state = canonical.preview_state(row["claim_id"])
        expected = TAXONOMY[row["claim_id"]]
        assert row["browse_metadata"] == {"domain": expected["domain"], "family_id": expected["family_id"],
                                           "domain_label": DOMAIN_LABELS[expected["domain"]], "browsing_only": True}
        assert isinstance(row["source_preview"], str)
        assert row["source_preview"] == state["message"][:240]
        assert len(row["source_preview"]) <= 240
        assert not {"browse_metadata", "browsing_only", "source_preview", "domain", "domain_label", "family_id"}.intersection(
            _public_keys(state))
        assert row["state_sha256"] == state["state_sha256"]
    rows[0]["browse_metadata"]["domain"] = "caller rewrite"
    assert canonical.summary_rows()[0]["browse_metadata"]["domain"] != "caller rewrite"


def test_browsing_taxonomy_must_cover_exact_canonical_binding_ids(canonical, monkeypatch):
    from casepath_api import autonomous_corpus_v1 as adapter_module
    from casepath_api.autonomous_taxonomy_v1 import TAXONOMY
    changed = dict(TAXONOMY)
    changed["clm_not_an_original"] = changed.pop(canonical.ids[0])
    monkeypatch.setattr(adapter_module, "TAXONOMY", changed)
    with pytest.raises(WorkspaceCorpusError):
        canonical.summary_rows()
