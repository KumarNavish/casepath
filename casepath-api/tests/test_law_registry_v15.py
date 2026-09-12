from __future__ import annotations

from hashlib import sha256

from casepath_api.law_registry import (
    BWO_CONCILIATION_SNAPSHOT_SHA256,
    FEDLEX_OR_SNAPSHOT_SHA256,
    HANDLING_PRINCIPLES,
    LAW_REGISTRY_CONTRACT,
    LAW_REGISTRY_VERSION,
    LAW_SOURCES,
    LEGAL_QUESTIONS,
    legal_context,
)


def test_official_law_registry_has_reproducible_passages_and_snapshots():
    assert LAW_REGISTRY_CONTRACT == "casepath.legal-context/2.0.0"
    assert LAW_REGISTRY_VERSION == "ch-tenancy-official-snapshot/2026-08-12"
    assert FEDLEX_OR_SNAPSHOT_SHA256 == (
        "6a958ae86cf67f71b1d36b798775b1659f06a9f0130fb9649f6ef045ce409966"
    )
    assert BWO_CONCILIATION_SNAPSHOT_SHA256 == (
        "27700e4ed06b60510b992676823c44d9a11aefb94192fdc3bec872df1c843af6"
    )
    assert {source["source_id"] for source in LAW_SOURCES} == {
        "fedlex-or-256",
        "fedlex-or-257g",
        "fedlex-or-259a",
        "bwo-conciliation",
    }
    for source in LAW_SOURCES:
        assert source["source_type"] in {"official_statute", "official_guidance"}
        assert source["jurisdiction"] == "CH"
        assert source["approved"] is False
        assert source["review_status"] == "qualified_review_pending"
        assert source["passage_language"] == "de"
        assert source["passage_sha256"] == sha256(
            source["passage_text"].encode("utf-8")
        ).hexdigest()
        assert source["retrieval"] == {
            "method": "versioned_official_source_registry_lookup",
            "retrieved_at": "2026-08-12",
            "registry_version": LAW_REGISTRY_VERSION,
            "snapshot_url": source["retrieval"]["snapshot_url"],
            "snapshot_sha256": source["retrieval"]["snapshot_sha256"],
            "snapshot_scope": source["retrieval"]["snapshot_scope"],
        }
        assert len(source["retrieval"]["snapshot_sha256"]) == 64
        if source["source_id"] == "bwo-conciliation":
            assert source["retrieval"]["snapshot_scope"] == (
                "normalized_official_passage_utf8"
            )
            assert source["retrieval"]["snapshot_sha256"] == source[
                "passage_sha256"
            ]
        else:
            assert source["retrieval"]["snapshot_scope"] == "official_pdf_bytes"


def test_legal_questions_are_explicit_reciprocal_joins_not_position_zipped():
    source_ids = {source["source_id"] for source in LAW_SOURCES}
    interpretation_ids = {
        principle["source_id"] for principle in HANDLING_PRINCIPLES
    }
    question_ids = [question["question_id"] for question in LEGAL_QUESTIONS]
    assert len(question_ids) == len(set(question_ids)) == 5
    assert all(principle["producer"] == "deterministic_application" for principle in HANDLING_PRINCIPLES)
    assert all("model" not in principle["title"].lower() for principle in HANDLING_PRINCIPLES)
    for question in LEGAL_QUESTIONS:
        assert set(question) == {
            "question_id",
            "text",
            "source_ids",
            "interpretation_ids",
            "process_node_ids",
            "consequence",
        }
        assert question["text"].strip()
        assert question["consequence"].strip()
        assert question["process_node_ids"]
        assert set(question["source_ids"]) <= source_ids
        assert set(question["interpretation_ids"]) <= interpretation_ids
        assert question["source_ids"] or question["interpretation_ids"]
    joined_source_ids = {
        source_id for question in LEGAL_QUESTIONS for source_id in question["source_ids"]
    }
    joined_interpretation_ids = {
        source_id
        for question in LEGAL_QUESTIONS
        for source_id in question["interpretation_ids"]
    }
    assert joined_source_ids == source_ids
    assert joined_interpretation_ids == interpretation_ids


def test_legal_context_returns_an_isolated_serializable_contract():
    first = legal_context()
    second = legal_context()
    assert first == second
    assert first is not second
    assert first["contract"] == LAW_REGISTRY_CONTRACT
    assert first["registry_version"] == LAW_REGISTRY_VERSION
    assert first["lookup_method"] == "versioned_official_source_registry_lookup"
    first["questions"][0]["source_ids"].append("tampered")
    assert "tampered" not in second["questions"][0]["source_ids"]
