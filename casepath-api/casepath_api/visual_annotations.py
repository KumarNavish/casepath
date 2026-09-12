from __future__ import annotations

import re
from typing import Any


VISUAL_ANNOTATION_CONTRACT = "casepath.visual-reference-annotation/1.0.0"
VISUAL_ANNOTATION_VERSION = "generated-demo-reference/2026-08-12"
VISUAL_ANNOTATION_PRODUCER = "deterministic_reference_annotation"
VISUAL_ANNOTATION_AUTHORITY = "generated_demo_reference_only"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class VisualAnnotationError(ValueError):
    """Raised when a deterministic reference annotation loses byte identity."""


def visual_annotation_ref(
    *,
    artifact_id: str,
    image_sha256: str,
    region: list[float],
    observation: str,
) -> dict[str, Any]:
    """Build a curated demo annotation without claiming machine extraction.

    The annotation is useful for the bidirectional source viewer, but its
    authority remains a generated-demo reference. The exact image hash is part
    of the locator so replacing the pixels invalidates the annotation.
    """

    value = {
        "artifact_id": artifact_id,
        "locator_kind": "visual_observation",
        "region": region,
        "observation": observation,
        "producer": VISUAL_ANNOTATION_PRODUCER,
        "authority": VISUAL_ANNOTATION_AUTHORITY,
        "annotation_contract": VISUAL_ANNOTATION_CONTRACT,
        "annotation_version": VISUAL_ANNOTATION_VERSION,
        "image_sha256": image_sha256,
    }
    validate_visual_annotation(value, image_sha256=image_sha256)
    return value


def validate_visual_annotation(
    value: dict[str, Any],
    *,
    image_sha256: str,
) -> None:
    expected_keys = {
        "artifact_id",
        "locator_kind",
        "region",
        "observation",
        "producer",
        "authority",
        "annotation_contract",
        "annotation_version",
        "image_sha256",
    }
    if set(value) != expected_keys:
        raise VisualAnnotationError("visual annotation fields are not exact")
    if value.get("locator_kind") != "visual_observation":
        raise VisualAnnotationError("visual annotation locator kind is invalid")
    if value.get("producer") != VISUAL_ANNOTATION_PRODUCER:
        raise VisualAnnotationError("visual annotation producer is invalid")
    if value.get("authority") != VISUAL_ANNOTATION_AUTHORITY:
        raise VisualAnnotationError("visual annotation authority is invalid")
    if value.get("annotation_contract") != VISUAL_ANNOTATION_CONTRACT:
        raise VisualAnnotationError("visual annotation contract is invalid")
    if value.get("annotation_version") != VISUAL_ANNOTATION_VERSION:
        raise VisualAnnotationError("visual annotation version is invalid")
    if not isinstance(image_sha256, str) or not _SHA256.fullmatch(image_sha256):
        raise VisualAnnotationError("observable image hash is invalid")
    if value.get("image_sha256") != image_sha256:
        raise VisualAnnotationError("visual annotation does not match observable image bytes")
    region = value.get("region")
    valid_region = (
        isinstance(region, list)
        and len(region) == 4
        and all(
            isinstance(number, (int, float))
            and not isinstance(number, bool)
            and 0 <= number <= 1
            for number in region
        )
        and region[2] > 0
        and region[3] > 0
        and region[0] + region[2] <= 1
        and region[1] + region[3] <= 1
    )
    if not valid_region:
        raise VisualAnnotationError("visual annotation region is invalid")
    observation = value.get("observation")
    if not isinstance(observation, str) or not observation.strip():
        raise VisualAnnotationError("visual annotation observation is invalid")


__all__ = [
    "VISUAL_ANNOTATION_AUTHORITY",
    "VISUAL_ANNOTATION_CONTRACT",
    "VISUAL_ANNOTATION_PRODUCER",
    "VISUAL_ANNOTATION_VERSION",
    "VisualAnnotationError",
    "validate_visual_annotation",
    "visual_annotation_ref",
]
