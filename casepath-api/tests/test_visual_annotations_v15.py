from __future__ import annotations

import pytest

from casepath_api.visual_annotations import (
    VISUAL_ANNOTATION_AUTHORITY,
    VISUAL_ANNOTATION_CONTRACT,
    VISUAL_ANNOTATION_PRODUCER,
    VISUAL_ANNOTATION_VERSION,
    VisualAnnotationError,
    validate_visual_annotation,
    visual_annotation_ref,
)


IMAGE_HASH = "a" * 64


def annotation() -> dict:
    return visual_annotation_ref(
        artifact_id="art_photo",
        image_sha256=IMAGE_HASH,
        region=[0.42, 0.10, 0.20, 0.70],
        observation="Visible dark spotting is concentrated along the wall corner.",
    )


def test_reference_annotation_is_explicitly_non_agent_and_byte_bound():
    value = annotation()
    assert value == {
        "artifact_id": "art_photo",
        "locator_kind": "visual_observation",
        "region": [0.42, 0.10, 0.20, 0.70],
        "observation": "Visible dark spotting is concentrated along the wall corner.",
        "producer": VISUAL_ANNOTATION_PRODUCER,
        "authority": VISUAL_ANNOTATION_AUTHORITY,
        "annotation_contract": VISUAL_ANNOTATION_CONTRACT,
        "annotation_version": VISUAL_ANNOTATION_VERSION,
        "image_sha256": IMAGE_HASH,
    }
    assert "agent" not in value
    assert "model" not in value["producer"]


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("producer", "Visual Evidence Agent"),
        ("authority", "qualified_expert_reviewed"),
        ("annotation_contract", "forged"),
        ("annotation_version", "forged"),
        ("image_sha256", "b" * 64),
        ("region", [0.9, 0.9, 0.2, 0.2]),
        ("observation", ""),
    ],
)
def test_forged_reference_annotation_fails_closed(field: str, replacement):
    value = annotation()
    value[field] = replacement
    with pytest.raises(VisualAnnotationError):
        validate_visual_annotation(value, image_sha256=IMAGE_HASH)


def test_swapped_or_modified_image_invalidates_reference_annotation():
    with pytest.raises(
        VisualAnnotationError,
        match="does not match observable image bytes",
    ):
        validate_visual_annotation(annotation(), image_sha256="c" * 64)


def test_unallowlisted_annotation_field_fails_closed():
    value = annotation()
    value["raw_pixels"] = "forbidden"
    with pytest.raises(VisualAnnotationError, match="fields are not exact"):
        validate_visual_annotation(value, image_sha256=IMAGE_HASH)
