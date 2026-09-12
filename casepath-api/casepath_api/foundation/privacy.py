from __future__ import annotations

import re
from dataclasses import dataclass

from .common import digest_text, digest_value
from .contracts import (
    IntakeAttachment,
    PrivacyIntake,
    PrivacyReceipt,
    PrivacyResult,
    PrivacyState,
    ReplacementReceipt,
    SeededIdentifier,
    SourceLocator,
)


@dataclass(frozen=True)
class _IdentifierPattern:
    name: str
    expression: re.Pattern[str]


HIGH_RISK_PATTERNS = (
    _IdentifierPattern(
        "email_address",
        re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    ),
    _IdentifierPattern(
        "policy_reference",
        re.compile(r"(?i)\b(?:LP|POL|CLAIM)[-_ ]?\d{4}[-_ ]?\d{4,}\b"),
    ),
    _IdentifierPattern(
        "iban",
        re.compile(r"(?i)\bCH\d{2}(?:[ ]?[A-Z0-9]){17}\b"),
    ),
    _IdentifierPattern(
        "phone_number",
        re.compile(r"(?<!\w)(?:\+41|0041|0)\s?(?:\d[ .-]?){8,10}(?!\w)"),
    ),
    _IdentifierPattern(
        "street_address",
        re.compile(
            r"\b(?:[A-ZÄÖÜ][\wÄÖÜäöüéèà.-]+\s+){0,3}"
            r"(?:[A-ZÄÖÜ][\wÄÖÜäöüéèà.-]*(?:strasse|straße|weg|gasse)|street|road)"
            r"\s+\d{1,4}[A-Za-z]?,?\s+"
            r"\d{4}\s+[A-ZÄÖÜ][\wÄÖÜäöüéèà.-]+\b",
            re.IGNORECASE,
        ),
    ),
)


def _ordered_identifiers(
    values: tuple[SeededIdentifier, ...],
) -> tuple[SeededIdentifier, ...]:
    identities = [value.identifier_id for value in values]
    if len(set(identities)) != len(identities):
        raise ValueError("seeded identifier IDs must be unique")
    raw_values = [value.value for value in values]
    if len(set(raw_values)) != len(raw_values):
        raise ValueError("seeded identifier values must be unique")
    return tuple(
        sorted(values, key=lambda value: (-len(value.value), value.identifier_id))
    )


def _replace(
    value: str, identifiers: tuple[SeededIdentifier, ...]
) -> tuple[str, dict[str, int]]:
    result = value
    counts = {identifier.identifier_id: 0 for identifier in identifiers}
    for identifier in identifiers:
        count = result.count(identifier.value)
        if count:
            result = result.replace(identifier.value, identifier.replacement_token)
            counts[identifier.identifier_id] += count
    return result, counts


def _sanitize_locator(
    locator: SourceLocator, identifiers: tuple[SeededIdentifier, ...]
) -> tuple[SourceLocator, dict[str, int]]:
    if locator.exact_text is None:
        return locator, {identifier.identifier_id: 0 for identifier in identifiers}
    sanitized, counts = _replace(locator.exact_text, identifiers)
    return locator.model_copy(update={"exact_text": sanitized}), counts


def _merge_counts(target: dict[str, int], update: dict[str, int]) -> None:
    for identifier_id, count in update.items():
        target[identifier_id] += count


def _unresolved_values(
    texts: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    classes: set[str] = set()
    hashes: set[str] = set()
    for text in texts:
        for pattern in HIGH_RISK_PATTERNS:
            for match in pattern.expression.finditer(text):
                classes.add(pattern.name)
                hashes.add(digest_text(match.group(0)))
    return tuple(sorted(classes)), tuple(sorted(hashes))


def privacy_gate(intake: PrivacyIntake) -> PrivacyResult:
    """Deterministically sanitize seeded identifiers and fail closed on detected residue.

    This gate is deliberately conservative and fixture-scoped. It is not a claim of
    general PII detection or production anonymization safety.
    """

    identifiers = _ordered_identifiers(intake.seeded_identifiers)
    counts = {identifier.identifier_id: 0 for identifier in identifiers}
    sanitized_message, message_counts = _replace(intake.claim_message, identifiers)
    _merge_counts(counts, message_counts)

    sanitized_attachments: list[IntakeAttachment] = []
    scanned_texts = [sanitized_message]
    for attachment in intake.attachments:
        filename, filename_counts = _replace(attachment.filename, identifiers)
        text, text_counts = _replace(attachment.text, identifiers)
        _merge_counts(counts, filename_counts)
        _merge_counts(counts, text_counts)
        locators: list[SourceLocator] = []
        for locator in attachment.locators:
            sanitized_locator, locator_counts = _sanitize_locator(locator, identifiers)
            _merge_counts(counts, locator_counts)
            locators.append(sanitized_locator)
            if sanitized_locator.exact_text is not None:
                scanned_texts.append(sanitized_locator.exact_text)
        sanitized_attachments.append(
            attachment.model_copy(
                update={"filename": filename, "text": text, "locators": tuple(locators)}
            )
        )
        scanned_texts.extend((filename, text))

    sanitized_source_locators: list[SourceLocator] = []
    for locator in intake.source_locators:
        sanitized_locator, locator_counts = _sanitize_locator(locator, identifiers)
        _merge_counts(counts, locator_counts)
        sanitized_source_locators.append(sanitized_locator)
        if sanitized_locator.exact_text is not None:
            scanned_texts.append(sanitized_locator.exact_text)

    unresolved_classes, unresolved_hashes = _unresolved_values(tuple(scanned_texts))
    replacements = tuple(
        ReplacementReceipt(
            identifier_id=identifier.identifier_id,
            kind=identifier.kind,
            value_sha256=digest_text(identifier.value),
            replacement_token=identifier.replacement_token,
            replacement_count=counts[identifier.identifier_id],
        )
        for identifier in identifiers
    )
    sanitized_payload = {
        "case_id": intake.case_id,
        "language": intake.language,
        "claim_message": sanitized_message,
        "attachments": [
            value.model_dump(mode="json") for value in sanitized_attachments
        ],
        "source_locators": [
            value.model_dump(mode="json") for value in sanitized_source_locators
        ],
    }
    lineage = {
        "case_id": intake.case_id,
        "attachments": [
            {
                "artifact_id": value.artifact_id,
                "source_sha256": value.source_sha256,
                "locator_artifact_ids": [
                    locator.artifact_id for locator in value.locators
                ],
            }
            for value in intake.attachments
        ],
        "source_locator_artifact_ids": [
            value.artifact_id for value in intake.source_locators
        ],
    }
    if unresolved_classes and not intake.declared_synthetic_or_anonymized:
        state = PrivacyState.BLOCKED_FOR_UNRESOLVED_IDENTIFIERS
    elif intake.declared_synthetic_or_anonymized:
        state = PrivacyState.ALREADY_SYNTHETIC_OR_ANONYMIZED
    else:
        state = PrivacyState.SAFE_TO_PROCESS

    receipt_payload = {
        "contract": "casepath.privacy-receipt/1.0.0",
        "case_id": intake.case_id,
        "state": state.value,
        "input_sha256": digest_value(intake.model_dump(mode="json")),
        "sanitized_payload_sha256": digest_value(sanitized_payload),
        "source_lineage_sha256": digest_value(lineage),
        "replacements": [value.model_dump(mode="json") for value in replacements],
        "unresolved_identifier_classes": unresolved_classes,
        "unresolved_value_hashes": unresolved_hashes,
        "fail_closed": state == PrivacyState.BLOCKED_FOR_UNRESOLVED_IDENTIFIERS,
        "fixture_scope_only": True,
        "safety_nonclaim": (
            "Passing seeded synthetic fixtures does not establish general anonymization safety."
        ),
    }
    receipt = PrivacyReceipt.model_validate(
        {**receipt_payload, "receipt_sha256": digest_value(receipt_payload)}
    )
    return PrivacyResult(
        state=state,
        sanitized_message=(
            None
            if state == PrivacyState.BLOCKED_FOR_UNRESOLVED_IDENTIFIERS
            else sanitized_message
        ),
        sanitized_attachments=(
            ()
            if state == PrivacyState.BLOCKED_FOR_UNRESOLVED_IDENTIFIERS
            else tuple(sanitized_attachments)
        ),
        source_locators=(
            ()
            if state == PrivacyState.BLOCKED_FOR_UNRESOLVED_IDENTIFIERS
            else tuple(sanitized_source_locators)
        ),
        receipt=receipt,
    )
