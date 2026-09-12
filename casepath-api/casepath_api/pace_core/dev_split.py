from __future__ import annotations

from collections import defaultdict
import hashlib
from pathlib import PurePosixPath
import re
from typing import Any, Literal
import unicodedata

from pydantic import Field, model_validator

from ..foundation.common import is_sha256
from ..pace_canonical import (
    canonical_pace_json_bytes_v1,
    pace_digest_v1,
    parse_canonical_pace_json_v1,
)
from ..pace_contracts import PACEModel


_MONTHS = ("2026-01", "2026-02", "2026-03", "2026-04")
_MONTH_COUNTS = (46, 56, 55, 50)
_TARGETS = (120, 43, 44)
_PARTITIONS: tuple[
    Literal["build", "challenge", "locked_dev_gate"],
    Literal["build", "challenge", "locked_dev_gate"],
    Literal["build", "challenge", "locked_dev_gate"],
] = ("build", "challenge", "locked_dev_gate")
_DOCKET = re.compile(r"^[0-9]{2}-[0-9]{4}(?:R[0-9]+)?$")
_FORBIDDEN_KEY_PARTS = frozenset(
    {
        "analysis",
        "conclusion",
        "order",
        "outcome",
        "label",
        "gold",
        "disposition",
        "target",
        "expected",
        "oracle",
        "evaluator",
        "hidden",
    }
)
_FORBIDDEN_OUTCOME_VALUES = frozenset(
    {"affirmed", "denied", "dismissed", "granted", "remanded", "reversed", "vacated"}
)


def _validate_official_metadata_locator(value: str) -> None:
    normalized = unicodedata.normalize("NFC", value).lower()
    if (
        not value
        or normalized != value.lower()
        or any(
            token in normalized
            for token in (
                "2026-05",
                "26-0247",
                ".pdf",
                "http://",
                "https://",
                "analysis",
                "conclusion",
                "final-order",
            )
        )
    ):
        raise ValueError("official census locator is not metadata-only")


class PACEM0AuthorityV1(PACEModel):
    contract: Literal["casepath.pace-m0-authority/1.0.0"] = (
        "casepath.pace-m0-authority/1.0.0"
    )
    predecessor_root_anchor_file_sha256: str
    directive_record_semantic_sha256: str
    coordinator_scope_file_sha256: str
    family_deriver_source_sha256: str
    expected_census_anchor_sha256: str | None = None
    expected_build_packet_anchor_sha256: str | None = None
    authority_origin: Literal["TEST_ONLY_SYNTHETIC", "EXTERNAL_ROOT_BOUND"]
    partition_algorithm: Literal["group_dp_nearest_counts_v1"] = (
        "group_dp_nearest_counts_v1"
    )
    target_counts: tuple[int, int, int] = _TARGETS
    expected_month_counts: tuple[int, int, int, int] = _MONTH_COUNTS
    authority_sha256: str

    @model_validator(mode="after")
    def validate_authority(self) -> PACEM0AuthorityV1:
        hashes = (
            self.predecessor_root_anchor_file_sha256,
            self.directive_record_semantic_sha256,
            self.coordinator_scope_file_sha256,
            self.family_deriver_source_sha256,
            self.authority_sha256,
        )
        if any(not is_sha256(value) for value in hashes):
            raise ValueError("M0 authority contains an invalid digest")
        if self.expected_census_anchor_sha256 is not None and not is_sha256(
            self.expected_census_anchor_sha256
        ):
            raise ValueError("expected census anchor identity is invalid")
        if self.expected_build_packet_anchor_sha256 is not None and not is_sha256(
            self.expected_build_packet_anchor_sha256
        ):
            raise ValueError("expected build-packet anchor identity is invalid")
        if (
            self.target_counts != _TARGETS
            or self.expected_month_counts != _MONTH_COUNTS
        ):
            raise ValueError("M0 frozen census/split counts drifted")
        payload = self.model_dump(mode="json", exclude={"authority_sha256"})
        if pace_digest_v1(payload) != self.authority_sha256:
            raise ValueError("M0 authority self-hash mismatch")
        return self


class PACEM0AuthorityExternalAnchorV1(PACEModel):
    contract: Literal["casepath.pace-m0-authority-external-anchor/1.0.0"] = (
        "casepath.pace-m0-authority-external-anchor/1.0.0"
    )
    predecessor_root_anchor_file_sha256: str
    directive_record_semantic_sha256: str
    coordinator_scope_file_sha256: str
    authority_file_sha256: str
    authority_semantic_sha256: str
    expected_build_packet_anchor_sha256: str
    publication_state: Literal["PREREGISTERED_BEFORE_READINESS"]
    anchor_sha256: str

    @model_validator(mode="after")
    def validate_anchor(self) -> PACEM0AuthorityExternalAnchorV1:
        hashes = (
            self.predecessor_root_anchor_file_sha256,
            self.directive_record_semantic_sha256,
            self.coordinator_scope_file_sha256,
            self.authority_file_sha256,
            self.authority_semantic_sha256,
            self.expected_build_packet_anchor_sha256,
            self.anchor_sha256,
        )
        if any(not is_sha256(value) for value in hashes):
            raise ValueError("M0 external authority anchor contains an invalid digest")
        payload = self.model_dump(mode="json", exclude={"anchor_sha256"})
        if pace_digest_v1(payload) != self.anchor_sha256:
            raise ValueError("M0 external authority anchor self-hash mismatch")
        return self


class PACEOfficialDevCensusRowV1(PACEModel):
    canonical_docket: str = Field(pattern=r"^[0-9]{2}-[0-9]{4}(?:R[0-9]+)?$")
    decision_month: Literal["2026-01", "2026-02", "2026-03", "2026-04"]
    official_ordinal: int = Field(ge=1, le=207)
    official_source_id: str = Field(min_length=1)
    official_source_version: str = Field(min_length=1)
    official_source_locator: str = Field(min_length=1)
    merit_decision: Literal[True] = True
    form_ab1: Literal[False] = False
    order_only_suffix: Literal[False] = False
    row_sha256: str

    @model_validator(mode="after")
    def validate_row(self) -> PACEOfficialDevCensusRowV1:
        if not _DOCKET.fullmatch(self.canonical_docket):
            raise ValueError("official docket is not canonical")
        if self.canonical_docket.split("R", maxsplit=1)[0] == "26-0247":
            raise ValueError("inspected holdout docket is prohibited")
        _validate_official_metadata_locator(self.official_source_locator)
        if not is_sha256(self.row_sha256):
            raise ValueError("official census row identity is invalid")
        payload = self.model_dump(mode="json", exclude={"row_sha256"})
        if pace_digest_v1(payload) != self.row_sha256:
            raise ValueError("official census row self-hash mismatch")
        return self


class PACEOfficialDevCensusRosterV1(PACEModel):
    contract: Literal["casepath.pace-official-dev-census/1.0.0"] = (
        "casepath.pace-official-dev-census/1.0.0"
    )
    rows: tuple[PACEOfficialDevCensusRowV1, ...] = Field(min_length=207, max_length=207)
    roster_semantic_sha256: str

    @model_validator(mode="after")
    def validate_roster(self) -> PACEOfficialDevCensusRosterV1:
        row_hashes = tuple(value.row_sha256 for value in self.rows)
        if row_hashes != tuple(sorted(set(row_hashes))):
            raise ValueError("official census rows must be hash-sorted and unique")
        for values, label in (
            (tuple(value.canonical_docket for value in self.rows), "docket"),
            (tuple(value.official_ordinal for value in self.rows), "ordinal"),
            (
                tuple(value.official_source_locator for value in self.rows),
                "locator",
            ),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"official census {label} values are not unique")
        counts = tuple(
            sum(value.decision_month == month for value in self.rows)
            for month in _MONTHS
        )
        if counts != _MONTH_COUNTS:
            raise ValueError("official census monthly counts are not 46/56/55/50")
        payload = self.model_dump(mode="json", exclude={"roster_semantic_sha256"})
        if pace_digest_v1(payload) != self.roster_semantic_sha256:
            raise ValueError("official census semantic hash mismatch")
        return self


class PACEDevCensusAnchorV1(PACEModel):
    contract: Literal["casepath.pace-dev-census-anchor/1.0.0"] = (
        "casepath.pace-dev-census-anchor/1.0.0"
    )
    source_kind: Literal["OFFICIAL_ECAB_INDEX_METADATA_ONLY"]
    roster_file_sha256: str
    roster_semantic_sha256: str
    row_sha256s: tuple[str, ...] = Field(min_length=207, max_length=207)
    month_counts: tuple[int, int, int, int] = _MONTH_COUNTS
    family_deriver_source_sha256: str
    source_registry_version: str = Field(min_length=1)
    anchor_sha256: str

    @model_validator(mode="after")
    def validate_anchor(self) -> PACEDevCensusAnchorV1:
        hashes = (
            self.roster_file_sha256,
            self.roster_semantic_sha256,
            self.family_deriver_source_sha256,
            self.anchor_sha256,
            *self.row_sha256s,
        )
        if any(not is_sha256(value) for value in hashes):
            raise ValueError("census anchor contains an invalid digest")
        if self.row_sha256s != tuple(sorted(set(self.row_sha256s))):
            raise ValueError("census anchor row identities are not canonical")
        if self.month_counts != _MONTH_COUNTS:
            raise ValueError("census anchor monthly counts drifted")
        payload = self.model_dump(mode="json", exclude={"anchor_sha256"})
        if pace_digest_v1(payload) != self.anchor_sha256:
            raise ValueError("census anchor self-hash mismatch")
        return self


class PACEAuthenticatedDevCensusRowV1(PACEModel):
    record_id: str
    family_id: str
    decision_month: Literal["2026-01", "2026-02", "2026-03", "2026-04"]
    row_sha256: str


class PACEAuthenticatedDevCensusV1(PACEModel):
    contract: Literal["casepath.pace-authenticated-dev-census/1.0.0"] = (
        "casepath.pace-authenticated-dev-census/1.0.0"
    )
    anchor_sha256: str
    roster_file_sha256: str
    roster_semantic_sha256: str
    rows: tuple[PACEAuthenticatedDevCensusRowV1, ...]
    authenticated_sha256: str

    @model_validator(mode="after")
    def validate_authenticated(self) -> PACEAuthenticatedDevCensusV1:
        if len(self.rows) != 207:
            raise ValueError("authenticated census must contain 207 rows")
        hashes = (
            self.anchor_sha256,
            self.roster_file_sha256,
            self.roster_semantic_sha256,
            self.authenticated_sha256,
            *(value.row_sha256 for value in self.rows),
        )
        if any(not is_sha256(value) for value in hashes):
            raise ValueError("authenticated census contains an invalid digest")
        if tuple(value.record_id for value in self.rows) != tuple(
            sorted(value.record_id for value in self.rows)
        ):
            raise ValueError("authenticated census rows are not record-sorted")
        counts = tuple(
            sum(value.decision_month == month for value in self.rows)
            for month in _MONTHS
        )
        if counts != _MONTH_COUNTS:
            raise ValueError("authenticated census monthly counts drifted")
        payload = self.model_dump(mode="json", exclude={"authenticated_sha256"})
        if pace_digest_v1(payload) != self.authenticated_sha256:
            raise ValueError("authenticated census self-hash mismatch")
        return self


class PACEDevSplitRowV1(PACEModel):
    record_id: str
    family_id: str
    decision_month: Literal["2026-01", "2026-02", "2026-03", "2026-04"]
    partition: Literal["build", "challenge", "locked_dev_gate"]
    row_sha256: str


class PACEDevSplitManifestV1(PACEModel):
    contract: Literal["casepath.pace-dev-split-manifest/1.0.0"] = (
        "casepath.pace-dev-split-manifest/1.0.0"
    )
    census_sha256: str
    partition_authority_sha256: str
    partition_algorithm: Literal["group_dp_nearest_counts_v1"]
    ordering_seed_sha256: str
    target_counts: tuple[int, int, int] = _TARGETS
    actual_counts: tuple[int, int, int]
    exact_target_achieved: bool
    rows: tuple[PACEDevSplitRowV1, ...]
    manifest_sha256: str

    @model_validator(mode="after")
    def validate_manifest(self) -> PACEDevSplitManifestV1:
        hashes = (
            self.census_sha256,
            self.partition_authority_sha256,
            self.ordering_seed_sha256,
            self.manifest_sha256,
            *(value.row_sha256 for value in self.rows),
        )
        if any(not is_sha256(value) for value in hashes):
            raise ValueError("split manifest contains an invalid digest")
        if len(self.rows) != 207:
            raise ValueError("split manifest must cover the complete census")
        if tuple(value.record_id for value in self.rows) != tuple(
            sorted(value.record_id for value in self.rows)
        ):
            raise ValueError("split rows are not record-sorted")
        families: dict[str, set[str]] = defaultdict(set)
        for row in self.rows:
            families[row.family_id].add(row.partition)
        if any(len(value) != 1 for value in families.values()):
            raise ValueError("a docket family crosses split partitions")
        counts = tuple(
            sum(value.partition == partition for value in self.rows)
            for partition in _PARTITIONS
        )
        if counts != self.actual_counts or self.exact_target_achieved != (
            counts == self.target_counts
        ):
            raise ValueError("split count fields disagree")
        month_counts = tuple(
            sum(value.decision_month == month for value in self.rows)
            for month in _MONTHS
        )
        if month_counts != _MONTH_COUNTS:
            raise ValueError("split manifest monthly counts drifted")
        payload = self.model_dump(mode="json", exclude={"manifest_sha256"})
        if pace_digest_v1(payload) != self.manifest_sha256:
            raise ValueError("split manifest self-hash mismatch")
        return self


class PACEM0InputNotReadyReceiptV1(PACEModel):
    contract: Literal["casepath.pace-m0-input-readiness/1.0.0"] = (
        "casepath.pace-m0-input-readiness/1.0.0"
    )
    classification: Literal["PACE_CORE_INPUT_NOT_READY"]
    authority_sha256: str
    authenticated_census_rows: Literal[0]
    required_census_rows: Literal[207]
    available_build_packets: Literal[0]
    required_build_packets: Literal[120]
    split_executed: Literal[False]
    reason_codes: tuple[
        Literal[
            "EXTERNAL_CENSUS_ANCHOR_ABSENT",
            "EXTERNAL_CENSUS_ROSTER_ABSENT",
        ],
        ...,
    ]
    empirical_coverage_claimed: Literal[False]
    receipt_sha256: str

    @model_validator(mode="after")
    def validate_receipt(self) -> PACEM0InputNotReadyReceiptV1:
        if not is_sha256(self.authority_sha256) or not is_sha256(self.receipt_sha256):
            raise ValueError("M0 readiness receipt contains an invalid digest")
        if self.reason_codes != tuple(sorted(set(self.reason_codes))):
            raise ValueError("M0 readiness reasons are not canonical")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if pace_digest_v1(payload) != self.receipt_sha256:
            raise ValueError("M0 readiness receipt self-hash mismatch")
        return self


class PACEBuildFactualHistorySpanV1(PACEModel):
    section_role: Literal["FACTUAL_HISTORY"]
    source_id: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    locator_id: str = Field(min_length=1)
    normalized_text: str = Field(min_length=1)
    text_sha256: str
    span_sha256: str

    @model_validator(mode="after")
    def validate_span(self) -> PACEBuildFactualHistorySpanV1:
        if (
            not is_sha256(self.text_sha256)
            or not is_sha256(self.span_sha256)
            or hashlib.sha256(self.normalized_text.encode("utf-8")).hexdigest()
            != self.text_sha256
        ):
            raise ValueError("factual-history span text identity mismatch")
        payload = self.model_dump(mode="json", exclude={"span_sha256"})
        if pace_digest_v1(payload) != self.span_sha256:
            raise ValueError("factual-history span self-hash mismatch")
        return self


class PACEBuildSourceSpanRowV1(PACEModel):
    record_id: str = Field(min_length=1)
    source_registry_sha256: str
    span: PACEBuildFactualHistorySpanV1
    row_sha256: str

    @model_validator(mode="after")
    def validate_row(self) -> PACEBuildSourceSpanRowV1:
        if not is_sha256(self.source_registry_sha256) or not is_sha256(
            self.row_sha256
        ):
            raise ValueError("factual-history source row contains an invalid digest")
        payload = self.model_dump(mode="json", exclude={"row_sha256"})
        if pace_digest_v1(payload) != self.row_sha256:
            raise ValueError("factual-history source row self-hash mismatch")
        return self


class PACEBuildSourceRosterV1(PACEModel):
    contract: Literal["casepath.pace-build-source-roster/1.0.0"] = (
        "casepath.pace-build-source-roster/1.0.0"
    )
    rows: tuple[PACEBuildSourceSpanRowV1, ...] = Field(min_length=120)
    roster_semantic_sha256: str

    @model_validator(mode="after")
    def validate_roster(self) -> PACEBuildSourceRosterV1:
        keys = tuple(
            (
                value.record_id,
                value.span.source_id,
                value.span.source_version,
                value.span.locator_id,
            )
            for value in self.rows
        )
        if keys != tuple(sorted(set(keys))):
            raise ValueError("factual-history source roster is not canonical")
        record_ids = {value.record_id for value in self.rows}
        if len(record_ids) != 120:
            raise ValueError("factual-history source roster must cover 120 records")
        registries: dict[str, set[str]] = defaultdict(set)
        for row in self.rows:
            registries[row.record_id].add(row.source_registry_sha256)
        if any(len(values) != 1 for values in registries.values()):
            raise ValueError("a record has multiple source-registry identities")
        if not is_sha256(self.roster_semantic_sha256):
            raise ValueError("factual-history source roster identity is invalid")
        payload = self.model_dump(mode="json", exclude={"roster_semantic_sha256"})
        if pace_digest_v1(payload) != self.roster_semantic_sha256:
            raise ValueError("factual-history source roster self-hash mismatch")
        return self


class PACEBuildFactualHistoryPacketV1(PACEModel):
    contract: Literal["casepath.pace-outcome-blind-factual-history/1.0.0"] = (
        "casepath.pace-outcome-blind-factual-history/1.0.0"
    )
    record_id: str = Field(min_length=1)
    source_registry_sha256: str
    spans: tuple[PACEBuildFactualHistorySpanV1, ...] = Field(min_length=1)
    packet_sha256: str

    @model_validator(mode="after")
    def validate_packet(self) -> PACEBuildFactualHistoryPacketV1:
        if not is_sha256(self.source_registry_sha256) or not is_sha256(
            self.packet_sha256
        ):
            raise ValueError("factual-history packet contains an invalid digest")
        span_keys = tuple(
            (value.source_id, value.source_version, value.locator_id)
            for value in self.spans
        )
        if span_keys != tuple(sorted(set(span_keys))):
            raise ValueError("factual-history spans must be sorted and unique")
        payload = self.model_dump(mode="json", exclude={"packet_sha256"})
        assert_outcome_blind_packet_v1(payload)
        if pace_digest_v1(payload) != self.packet_sha256:
            raise ValueError("factual-history packet self-hash mismatch")
        return self


class PACEBuildPacketManifestRowV1(PACEModel):
    record_id: str = Field(min_length=1)
    split_row_sha256: str
    packet_relative_path: str = Field(min_length=1)
    packet_file_sha256: str
    packet_semantic_sha256: str
    source_registry_sha256: str
    allowed_span_sha256s: tuple[str, ...] = Field(min_length=1)
    row_sha256: str

    @model_validator(mode="after")
    def validate_row(self) -> PACEBuildPacketManifestRowV1:
        hashes = (
            self.split_row_sha256,
            self.packet_file_sha256,
            self.packet_semantic_sha256,
            self.source_registry_sha256,
            self.row_sha256,
            *self.allowed_span_sha256s,
        )
        if any(not is_sha256(value) for value in hashes):
            raise ValueError("build-packet manifest row contains an invalid digest")
        validate_public_dev_relative_path_v1(self.packet_relative_path)
        if self.allowed_span_sha256s != tuple(
            sorted(set(self.allowed_span_sha256s))
        ):
            raise ValueError("allowed factual-history spans are not canonical")
        payload = self.model_dump(mode="json", exclude={"row_sha256"})
        if pace_digest_v1(payload) != self.row_sha256:
            raise ValueError("build-packet manifest row self-hash mismatch")
        return self


class PACEBuildPacketManifestV1(PACEModel):
    contract: Literal["casepath.pace-build-packet-manifest/1.0.0"] = (
        "casepath.pace-build-packet-manifest/1.0.0"
    )
    split_manifest_sha256: str
    rows: tuple[PACEBuildPacketManifestRowV1, ...] = Field(
        min_length=120, max_length=120
    )
    manifest_semantic_sha256: str

    @model_validator(mode="after")
    def validate_manifest(self) -> PACEBuildPacketManifestV1:
        if not is_sha256(self.split_manifest_sha256) or not is_sha256(
            self.manifest_semantic_sha256
        ):
            raise ValueError("build-packet manifest contains an invalid digest")
        record_ids = tuple(value.record_id for value in self.rows)
        paths = tuple(value.packet_relative_path for value in self.rows)
        if record_ids != tuple(sorted(set(record_ids))) or len(paths) != len(
            set(paths)
        ):
            raise ValueError("build-packet manifest roster is not canonical")
        payload = self.model_dump(mode="json", exclude={"manifest_semantic_sha256"})
        if pace_digest_v1(payload) != self.manifest_semantic_sha256:
            raise ValueError("build-packet manifest self-hash mismatch")
        return self


class PACEBuildPacketAnchorV1(PACEModel):
    contract: Literal["casepath.pace-build-packet-anchor/1.0.0"] = (
        "casepath.pace-build-packet-anchor/1.0.0"
    )
    split_manifest_sha256: str
    packet_manifest_file_sha256: str
    packet_manifest_semantic_sha256: str
    manifest_row_sha256s: tuple[str, ...] = Field(min_length=120, max_length=120)
    source_roster_file_sha256: str
    source_roster_semantic_sha256: str
    source_roster_row_sha256s: tuple[str, ...] = Field(min_length=120)
    anchor_sha256: str

    @model_validator(mode="after")
    def validate_anchor(self) -> PACEBuildPacketAnchorV1:
        hashes = (
            self.split_manifest_sha256,
            self.packet_manifest_file_sha256,
            self.packet_manifest_semantic_sha256,
            self.source_roster_file_sha256,
            self.source_roster_semantic_sha256,
            self.anchor_sha256,
            *self.manifest_row_sha256s,
            *self.source_roster_row_sha256s,
        )
        if any(not is_sha256(value) for value in hashes):
            raise ValueError("build-packet anchor contains an invalid digest")
        if self.manifest_row_sha256s != tuple(
            sorted(set(self.manifest_row_sha256s))
        ):
            raise ValueError("build-packet anchor row identities are not canonical")
        if self.source_roster_row_sha256s != tuple(
            sorted(set(self.source_roster_row_sha256s))
        ):
            raise ValueError("source-roster anchor identities are not canonical")
        payload = self.model_dump(mode="json", exclude={"anchor_sha256"})
        if pace_digest_v1(payload) != self.anchor_sha256:
            raise ValueError("build-packet anchor self-hash mismatch")
        return self


class PACEBuildInputInventoryRowV1(PACEModel):
    scope: Literal["census", "build_factual_history"]
    record_id: str | None = None
    split_row_sha256: str | None = None
    status: Literal["AVAILABLE", "MISSING", "REJECTED"]
    reason_code: str = Field(min_length=1)
    required_count: int = Field(ge=1, le=207)
    available_count: int = Field(ge=0, le=207)
    packet_file_sha256: str | None = None
    packet_semantic_sha256: str | None = None
    packet_anchor_sha256: str | None = None
    source_registry_sha256: str | None = None


class PACEBuildInputReadinessReceiptV1(PACEModel):
    contract: Literal["casepath.pace-build-input-readiness/1.0.0"] = (
        "casepath.pace-build-input-readiness/1.0.0"
    )
    classification: Literal[
        "PACE_CORE_INPUT_READY_120_TEST_ONLY",
        "PACE_CORE_INPUT_NOT_READY",
    ]
    empirical_readiness_gate: Literal[
        "DISABLED_PENDING_SEPARATELY_ROOTED_ACQUISITION_V2"
    ] = "DISABLED_PENDING_SEPARATELY_ROOTED_ACQUISITION_V2"
    authority_sha256: str
    authority_origin: Literal["TEST_ONLY_SYNTHETIC", "EXTERNAL_ROOT_BOUND"]
    authority_external_anchor_sha256: str | None
    authority_verification_status: Literal[
        "TEST_ONLY_SYNTHETIC",
        "EXTERNAL_ROOT_VERIFIED",
        "EXTERNAL_ROOT_MISSING",
    ]
    census_anchor_sha256: str | None
    census_roster_file_sha256: str | None
    authenticated_census_sha256: str | None
    split_manifest_sha256: str | None
    split_exact_target_achieved: bool
    assigned_build_rows: int = Field(ge=0, le=207)
    required_build_packets: Literal[120] = 120
    available_build_packets: int = Field(ge=0, le=120)
    missing_build_packets: int = Field(ge=0, le=120)
    rejected_build_packets: int = Field(ge=0, le=120)
    packet_manifest_file_sha256: str | None
    packet_manifest_semantic_sha256: str | None
    packet_anchor_sha256: str | None
    source_roster_file_sha256: str | None
    source_roster_semantic_sha256: str | None
    build_record_ids_sha256: str | None
    build_split_row_sha256s_sha256: str | None
    denial_guard_status: Literal["PASS", "NOT_EXECUTED"]
    missing_input_inventory: tuple[PACEBuildInputInventoryRowV1, ...]
    empirical_coverage_claimed: Literal[False] = False
    receipt_sha256: str

    @model_validator(mode="after")
    def validate_readiness(self) -> PACEBuildInputReadinessReceiptV1:
        required_hashes = (self.authority_sha256, self.receipt_sha256)
        optional_hashes = (
            self.census_anchor_sha256,
            self.census_roster_file_sha256,
            self.authenticated_census_sha256,
            self.split_manifest_sha256,
            self.packet_manifest_file_sha256,
            self.packet_manifest_semantic_sha256,
            self.packet_anchor_sha256,
            self.source_roster_file_sha256,
            self.source_roster_semantic_sha256,
            self.build_record_ids_sha256,
            self.build_split_row_sha256s_sha256,
            self.authority_external_anchor_sha256,
        )
        if any(not is_sha256(value) for value in required_hashes) or any(
            value is not None and not is_sha256(value) for value in optional_hashes
        ):
            raise ValueError("build-input readiness contains an invalid digest")
        if (
            self.available_build_packets
            + self.missing_build_packets
            + self.rejected_build_packets
            != self.required_build_packets
        ):
            raise ValueError("build-input readiness counts are not exhaustive")
        build_inventory = tuple(
            value
            for value in self.missing_input_inventory
            if value.scope == "build_factual_history"
        )
        keys = tuple(value.record_id for value in build_inventory)
        if len(keys) != len(set(keys)):
            raise ValueError("build-input inventory contains duplicate records")
        if sum(value.required_count for value in build_inventory) != 120:
            raise ValueError("build-input inventory does not cover 120 requirements")
        if self.assigned_build_rows == 120:
            record_ids = tuple(value.record_id for value in build_inventory)
            split_rows = tuple(value.split_row_sha256 for value in build_inventory)
            exact_record_ids = tuple(
                value for value in record_ids if value is not None
            )
            exact_split_rows = tuple(value for value in split_rows if value is not None)
            if (
                len(build_inventory) != 120
                or any(value.required_count != 1 for value in build_inventory)
                or len(exact_record_ids) != 120
                or exact_record_ids != tuple(sorted(set(exact_record_ids)))
                or len(exact_split_rows) != 120
                or any(not is_sha256(value) for value in exact_split_rows)
                or self.build_record_ids_sha256
                != pace_digest_v1(list(exact_record_ids))
                or self.build_split_row_sha256s_sha256
                != pace_digest_v1(list(exact_split_rows))
            ):
                raise ValueError("build-input inventory is not the exact 120-row roster")
        elif (
            self.build_record_ids_sha256 is not None
            or self.build_split_row_sha256s_sha256 is not None
        ):
            raise ValueError("off-target readiness cannot claim a build roster")
        if sum(value.available_count for value in build_inventory) != (
            self.available_build_packets
        ):
            raise ValueError("build-input inventory availability count disagrees")
        if sum(
            value.required_count
            for value in build_inventory
            if value.status == "MISSING"
        ) != self.missing_build_packets or sum(
            value.required_count
            for value in build_inventory
            if value.status == "REJECTED"
        ) != self.rejected_build_packets:
            raise ValueError("build-input inventory status counts disagree")
        for value in build_inventory:
            hashes = (
                value.packet_file_sha256,
                value.packet_semantic_sha256,
                value.packet_anchor_sha256,
                value.source_registry_sha256,
            )
            if value.status == "AVAILABLE":
                if value.available_count != value.required_count or any(
                    item is None or not is_sha256(item) for item in hashes
                ):
                    raise ValueError("available build input lacks exact identities")
            elif value.available_count != 0:
                raise ValueError("unavailable build input has a positive count")
            if self.packet_anchor_sha256 is None:
                if value.packet_anchor_sha256 is not None:
                    raise ValueError("inventory row has an unbound packet anchor")
            elif value.packet_anchor_sha256 != self.packet_anchor_sha256:
                raise ValueError("inventory row packet anchor disagrees")
        structurally_ready = (
            self.split_exact_target_achieved
            and self.assigned_build_rows == 120
            and self.available_build_packets == 120
            and self.missing_build_packets == 0
            and self.rejected_build_packets == 0
            and self.denial_guard_status == "PASS"
        )
        test_ready = (
            structurally_ready
            and self.authority_origin == "TEST_ONLY_SYNTHETIC"
            and self.authority_verification_status == "TEST_ONLY_SYNTHETIC"
        )
        if test_ready != (
            self.classification == "PACE_CORE_INPUT_READY_120_TEST_ONLY"
        ):
            raise ValueError("test-only readiness classification is inconsistent")
        if not test_ready and self.classification != (
            "PACE_CORE_INPUT_NOT_READY"
        ):
            raise ValueError("non-ready input has a ready classification")
        payload = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if pace_digest_v1(payload) != self.receipt_sha256:
            raise ValueError("build-input readiness self-hash mismatch")
        return self


def assert_outcome_blind_packet_v1(value: Any) -> None:
    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                normalized = unicodedata.normalize("NFC", str(key)).lower()
                tokens = set(re.split(r"[^a-z0-9]+", normalized))
                if tokens.intersection(_FORBIDDEN_KEY_PARTS) or any(
                    part in normalized for part in _FORBIDDEN_KEY_PARTS
                ):
                    raise ValueError(f"forbidden outcome-bearing field: {key}")
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)
        elif isinstance(item, str):
            normalized = unicodedata.normalize("NFC", item).lower()
            if (
                "2026-05" in normalized
                or "26-0247" in normalized
                or ".pdf" in normalized
                or "http://" in normalized
                or "https://" in normalized
                or normalized.strip() in _FORBIDDEN_OUTCOME_VALUES
            ):
                raise ValueError("packet contains a prohibited holdout/path value")

    visit(value)


def validate_public_dev_relative_path_v1(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    normalized = value.lower()
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.suffix != ".json"
        or any(
            token in normalized
            for token in ("2026-05", "may", "26-0247", "gold", "evaluator", ".pdf")
        )
    ):
        raise ValueError("public-development path is outside the frozen allowlist")
    return path


def authenticate_dev_census_v1(
    roster_bytes: bytes,
    anchor: PACEDevCensusAnchorV1,
    authority: PACEM0AuthorityV1,
) -> PACEAuthenticatedDevCensusV1:
    parse_canonical_pace_json_v1(roster_bytes)
    roster = PACEOfficialDevCensusRosterV1.model_validate_json(roster_bytes)
    file_sha = hashlib.sha256(roster_bytes).hexdigest()
    if (
        authority.expected_census_anchor_sha256 != anchor.anchor_sha256
        or authority.expected_census_anchor_sha256 is None
        or file_sha != anchor.roster_file_sha256
        or roster.roster_semantic_sha256 != anchor.roster_semantic_sha256
        or tuple(value.row_sha256 for value in roster.rows) != anchor.row_sha256s
        or authority.family_deriver_source_sha256 != anchor.family_deriver_source_sha256
    ):
        raise ValueError("official census does not match its external anchor")
    rows = tuple(
        sorted(
            (
                PACEAuthenticatedDevCensusRowV1(
                    record_id=pace_digest_v1(
                        ["casepath.pace-record/1.0.0", value.canonical_docket]
                    ),
                    family_id=pace_digest_v1(
                        [
                            "casepath.pace-family/1.0.0",
                            value.canonical_docket.split("R", maxsplit=1)[0],
                        ]
                    ),
                    decision_month=value.decision_month,
                    row_sha256=value.row_sha256,
                )
                for value in roster.rows
            ),
            key=lambda value: value.record_id,
        )
    )
    payload = {
        "contract": "casepath.pace-authenticated-dev-census/1.0.0",
        "anchor_sha256": anchor.anchor_sha256,
        "roster_file_sha256": file_sha,
        "roster_semantic_sha256": roster.roster_semantic_sha256,
        "rows": [value.model_dump(mode="json") for value in rows],
    }
    return PACEAuthenticatedDevCensusV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**payload, "authenticated_sha256": pace_digest_v1(payload)}
        )
    )


def _split_seed(
    census: PACEAuthenticatedDevCensusV1,
    authority: PACEM0AuthorityV1,
) -> str:
    return pace_digest_v1(
        {
            "domain": "casepath.pace-m0-group-split-seed/1.0.0",
            "predecessor_root_anchor_file_sha256": (
                authority.predecessor_root_anchor_file_sha256
            ),
            "directive_record_semantic_sha256": (
                authority.directive_record_semantic_sha256
            ),
            "coordinator_scope_file_sha256": authority.coordinator_scope_file_sha256,
            "census_anchor_sha256": census.anchor_sha256,
            "census_roster_semantic_sha256": census.roster_semantic_sha256,
            "family_deriver_source_sha256": authority.family_deriver_source_sha256,
            "partition_algorithm": authority.partition_algorithm,
            "target_counts": list(authority.target_counts),
        }
    )


def _partition_authority_sha256_v1(authority: PACEM0AuthorityV1) -> str:
    """Commit only split inputs, avoiding a packet-anchor commitment cycle."""

    return pace_digest_v1(
        {
            "contract": "casepath.pace-m0-partition-authority/1.0.0",
            "predecessor_root_anchor_file_sha256": (
                authority.predecessor_root_anchor_file_sha256
            ),
            "directive_record_semantic_sha256": (
                authority.directive_record_semantic_sha256
            ),
            "coordinator_scope_file_sha256": authority.coordinator_scope_file_sha256,
            "family_deriver_source_sha256": authority.family_deriver_source_sha256,
            "expected_census_anchor_sha256": (
                authority.expected_census_anchor_sha256
            ),
            "partition_algorithm": authority.partition_algorithm,
            "target_counts": list(authority.target_counts),
            "expected_month_counts": list(authority.expected_month_counts),
        }
    )


def _partition_authenticated_census_v1(
    census: PACEAuthenticatedDevCensusV1,
    authority: PACEM0AuthorityV1,
) -> PACEDevSplitManifestV1:
    census = PACEAuthenticatedDevCensusV1.model_validate_json(
        canonical_pace_json_bytes_v1(census.model_dump(mode="json"))
    )
    authority = PACEM0AuthorityV1.model_validate_json(
        canonical_pace_json_bytes_v1(authority.model_dump(mode="json"))
    )
    if (
        authority.expected_census_anchor_sha256 is None
        or census.anchor_sha256 != authority.expected_census_anchor_sha256
    ):
        raise ValueError("authenticated census is outside the frozen M0 authority")
    groups_by_id: dict[str, list[PACEAuthenticatedDevCensusRowV1]] = defaultdict(list)
    for row in census.rows:
        groups_by_id[row.family_id].append(row)
    seed = _split_seed(census, authority)
    groups = sorted(
        groups_by_id.items(),
        key=lambda item: (pace_digest_v1([seed, item[0]]), item[0]),
    )
    states: dict[tuple[int, int], tuple[int, ...]] = {(0, 0): ()}
    for _, group_rows in groups:
        size = len(group_rows)
        next_states: dict[tuple[int, int], tuple[int, ...]] = {}
        for (build_count, challenge_count), assignment in states.items():
            for index in range(3):
                key = (
                    build_count + (size if index == 0 else 0),
                    challenge_count + (size if index == 1 else 0),
                )
                if key[0] <= 207 and key[1] <= 207 and sum(key) <= 207:
                    candidate = (*assignment, index)
                    previous = next_states.get(key)
                    if previous is None or candidate < previous:
                        next_states[key] = candidate
        states = next_states
    best_counts, best_assignment = min(
        states.items(),
        key=lambda item: (
            abs(item[0][0] - _TARGETS[0])
            + abs(item[0][1] - _TARGETS[1])
            + abs((207 - sum(item[0])) - _TARGETS[2]),
            item[1],
        ),
    )
    partition_by_family = {
        family_id: _PARTITIONS[index]
        for index, (family_id, _) in zip(best_assignment, groups, strict=True)
    }
    split_rows = tuple(
        PACEDevSplitRowV1(
            record_id=value.record_id,
            family_id=value.family_id,
            decision_month=value.decision_month,
            partition=partition_by_family[value.family_id],
            row_sha256=value.row_sha256,
        )
        for value in census.rows
    )
    actual = (best_counts[0], best_counts[1], 207 - sum(best_counts))
    payload = {
        "contract": "casepath.pace-dev-split-manifest/1.0.0",
        "census_sha256": census.authenticated_sha256,
        "partition_authority_sha256": _partition_authority_sha256_v1(authority),
        "partition_algorithm": authority.partition_algorithm,
        "ordering_seed_sha256": seed,
        "target_counts": list(_TARGETS),
        "actual_counts": list(actual),
        "exact_target_achieved": actual == _TARGETS,
        "rows": [value.model_dump(mode="json") for value in split_rows],
    }
    return PACEDevSplitManifestV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**payload, "manifest_sha256": pace_digest_v1(payload)}
        )
    )


def build_group_aware_split_v1(
    *,
    census_roster_bytes: bytes,
    census_anchor: PACEDevCensusAnchorV1,
    authority: PACEM0AuthorityV1,
) -> PACEDevSplitManifestV1:
    """Authenticate external bytes before any group assignment can execute."""

    census = authenticate_dev_census_v1(
        census_roster_bytes,
        census_anchor,
        authority,
    )
    return _partition_authenticated_census_v1(census, authority)


def assess_m0_v1(
    *,
    authority: PACEM0AuthorityV1,
    census_anchor: PACEDevCensusAnchorV1 | None,
    census_roster_bytes: bytes | None,
) -> PACEM0InputNotReadyReceiptV1 | PACEDevSplitManifestV1:
    reasons = []
    if census_anchor is None or authority.expected_census_anchor_sha256 is None:
        reasons.append("EXTERNAL_CENSUS_ANCHOR_ABSENT")
    if census_roster_bytes is None:
        reasons.append("EXTERNAL_CENSUS_ROSTER_ABSENT")
    if reasons:
        payload = {
            "contract": "casepath.pace-m0-input-readiness/1.0.0",
            "classification": "PACE_CORE_INPUT_NOT_READY",
            "authority_sha256": authority.authority_sha256,
            "authenticated_census_rows": 0,
            "required_census_rows": 207,
            "available_build_packets": 0,
            "required_build_packets": 120,
            "split_executed": False,
            "reason_codes": sorted(reasons),
            "empirical_coverage_claimed": False,
        }
        return PACEM0InputNotReadyReceiptV1.model_validate_json(
            canonical_pace_json_bytes_v1(
                {**payload, "receipt_sha256": pace_digest_v1(payload)}
            )
        )
    assert census_anchor is not None and census_roster_bytes is not None
    return build_group_aware_split_v1(
        census_roster_bytes=census_roster_bytes,
        census_anchor=census_anchor,
        authority=authority,
    )


def _build_readiness_receipt(
    payload: dict[str, Any],
) -> PACEBuildInputReadinessReceiptV1:
    payload = {
        **payload,
        "empirical_readiness_gate": (
            "DISABLED_PENDING_SEPARATELY_ROOTED_ACQUISITION_V2"
        ),
    }
    return PACEBuildInputReadinessReceiptV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            {**payload, "receipt_sha256": pace_digest_v1(payload)}
        )
    )


def _verify_m0_authority_origin_v1(
    *,
    authority: PACEM0AuthorityV1,
    authority_bytes: bytes | None,
    authority_external_anchor: PACEM0AuthorityExternalAnchorV1 | None,
    expected_authority_external_anchor_sha256: str | None,
) -> tuple[str | None, Literal[
    "TEST_ONLY_SYNTHETIC",
    "EXTERNAL_ROOT_VERIFIED",
    "EXTERNAL_ROOT_MISSING",
]]:
    if authority_bytes is not None:
        parse_canonical_pace_json_v1(authority_bytes)
        parsed = PACEM0AuthorityV1.model_validate_json(authority_bytes)
        if parsed != authority:
            raise ValueError("M0 authority bytes disagree with the supplied authority")
    if authority.authority_origin == "TEST_ONLY_SYNTHETIC":
        if (
            authority_external_anchor is not None
            or expected_authority_external_anchor_sha256 is not None
        ):
            raise ValueError("test-only authority cannot claim an external root")
        return None, "TEST_ONLY_SYNTHETIC"
    if (
        authority_bytes is None
        or authority_external_anchor is None
        or expected_authority_external_anchor_sha256 is None
    ):
        return None, "EXTERNAL_ROOT_MISSING"
    external = PACEM0AuthorityExternalAnchorV1.model_validate_json(
        canonical_pace_json_bytes_v1(
            authority_external_anchor.model_dump(mode="json")
        )
    )
    if (
        external.anchor_sha256 != expected_authority_external_anchor_sha256
        or external.authority_file_sha256
        != hashlib.sha256(authority_bytes).hexdigest()
        or external.authority_semantic_sha256 != authority.authority_sha256
        or external.predecessor_root_anchor_file_sha256
        != authority.predecessor_root_anchor_file_sha256
        or external.directive_record_semantic_sha256
        != authority.directive_record_semantic_sha256
        or external.coordinator_scope_file_sha256
        != authority.coordinator_scope_file_sha256
        or external.expected_build_packet_anchor_sha256
        != authority.expected_build_packet_anchor_sha256
    ):
        raise ValueError("M0 authority does not match its external root")
    return external.anchor_sha256, "EXTERNAL_ROOT_VERIFIED"


def _build_roster_commitments_v1(
    rows: tuple[PACEDevSplitRowV1, ...],
) -> tuple[str | None, str | None]:
    if len(rows) != 120:
        return None, None
    return (
        pace_digest_v1([value.record_id for value in rows]),
        pace_digest_v1([value.row_sha256 for value in rows]),
    )


def assess_build_input_readiness_v1(
    *,
    authority: PACEM0AuthorityV1,
    census_roster_bytes: bytes | None,
    census_anchor: PACEDevCensusAnchorV1 | None,
    split_manifest: PACEDevSplitManifestV1 | None,
    packet_manifest_bytes: bytes | None,
    packet_anchor: PACEBuildPacketAnchorV1 | None,
    packet_bytes_by_path: dict[str, bytes],
    source_roster_bytes: bytes | None = None,
    authority_bytes: bytes | None = None,
    authority_external_anchor: PACEM0AuthorityExternalAnchorV1 | None = None,
    expected_authority_external_anchor_sha256: str | None = None,
) -> PACEBuildInputReadinessReceiptV1:
    """Assess factual-history packets after, and independently from, splitting."""

    authority = PACEM0AuthorityV1.model_validate_json(
        canonical_pace_json_bytes_v1(authority.model_dump(mode="json"))
    )
    external_authority_sha, authority_status = _verify_m0_authority_origin_v1(
        authority=authority,
        authority_bytes=authority_bytes,
        authority_external_anchor=authority_external_anchor,
        expected_authority_external_anchor_sha256=(
            expected_authority_external_anchor_sha256
        ),
    )
    authority_fields = {
        "authority_sha256": authority.authority_sha256,
        "authority_origin": authority.authority_origin,
        "authority_external_anchor_sha256": external_authority_sha,
        "authority_verification_status": authority_status,
    }
    if (
        split_manifest is None
        or census_roster_bytes is None
        or census_anchor is None
    ):
        pre_split_inventory = (
            PACEBuildInputInventoryRowV1(
                scope="census",
                status="MISSING",
                reason_code="EXTERNAL_CENSUS_OR_SPLIT_NOT_FROZEN",
                required_count=207,
                available_count=0,
            ),
            PACEBuildInputInventoryRowV1(
                scope="build_factual_history",
                status="MISSING",
                reason_code="SPLIT_NOT_FROZEN",
                required_count=120,
                available_count=0,
            ),
        )
        return _build_readiness_receipt(
            {
                "contract": "casepath.pace-build-input-readiness/1.0.0",
                "classification": "PACE_CORE_INPUT_NOT_READY",
                **authority_fields,
                "census_anchor_sha256": None,
                "census_roster_file_sha256": None,
                "authenticated_census_sha256": None,
                "split_manifest_sha256": None,
                "split_exact_target_achieved": False,
                "assigned_build_rows": 0,
                "required_build_packets": 120,
                "available_build_packets": 0,
                "missing_build_packets": 120,
                "rejected_build_packets": 0,
                "packet_manifest_file_sha256": None,
                "packet_manifest_semantic_sha256": None,
                "packet_anchor_sha256": None,
                "source_roster_file_sha256": None,
                "source_roster_semantic_sha256": None,
                "build_record_ids_sha256": None,
                "build_split_row_sha256s_sha256": None,
                "denial_guard_status": "NOT_EXECUTED",
                "missing_input_inventory": [
                    value.model_dump(mode="json") for value in pre_split_inventory
                ],
                "empirical_coverage_claimed": False,
            }
        )
    census = authenticate_dev_census_v1(
        census_roster_bytes,
        census_anchor,
        authority,
    )
    split = PACEDevSplitManifestV1.model_validate_json(
        canonical_pace_json_bytes_v1(split_manifest.model_dump(mode="json"))
    )
    derived_split = _partition_authenticated_census_v1(census, authority)
    if (
        split.census_sha256 != census.authenticated_sha256
        or split.partition_authority_sha256
        != _partition_authority_sha256_v1(authority)
        or split.model_dump(mode="json") != derived_split.model_dump(mode="json")
    ):
        raise ValueError("build readiness split is outside the authenticated census")
    build_rows = tuple(value for value in split.rows if value.partition == "build")
    build_record_ids_sha, build_split_rows_sha = _build_roster_commitments_v1(
        build_rows
    )
    if len(build_rows) != 120:
        off_target = (
            PACEBuildInputInventoryRowV1(
                scope="build_factual_history",
                status="REJECTED",
                reason_code="GROUP_AWARE_TARGET_120_UNACHIEVABLE",
                required_count=120,
                available_count=0,
            ),
        )
        return _build_readiness_receipt(
            {
                "contract": "casepath.pace-build-input-readiness/1.0.0",
                "classification": "PACE_CORE_INPUT_NOT_READY",
                **authority_fields,
                "census_anchor_sha256": census.anchor_sha256,
                "census_roster_file_sha256": census.roster_file_sha256,
                "authenticated_census_sha256": census.authenticated_sha256,
                "split_manifest_sha256": split.manifest_sha256,
                "split_exact_target_achieved": False,
                "assigned_build_rows": len(build_rows),
                "required_build_packets": 120,
                "available_build_packets": 0,
                "missing_build_packets": 0,
                "rejected_build_packets": 120,
                "packet_manifest_file_sha256": None,
                "packet_manifest_semantic_sha256": None,
                "packet_anchor_sha256": None,
                "source_roster_file_sha256": None,
                "source_roster_semantic_sha256": None,
                "build_record_ids_sha256": build_record_ids_sha,
                "build_split_row_sha256s_sha256": build_split_rows_sha,
                "denial_guard_status": "NOT_EXECUTED",
                "missing_input_inventory": [
                    value.model_dump(mode="json") for value in off_target
                ],
                "empirical_coverage_claimed": False,
            }
        )
    if (
        packet_manifest_bytes is None
        or packet_anchor is None
        or source_roster_bytes is None
        or authority.expected_build_packet_anchor_sha256 is None
    ):
        missing_packet_inventory = tuple(
            PACEBuildInputInventoryRowV1(
                scope="build_factual_history",
                record_id=value.record_id,
                split_row_sha256=value.row_sha256,
                status="MISSING",
                reason_code="EXTERNAL_PACKET_MANIFEST_ANCHOR_OR_SOURCE_ROSTER_ABSENT",
                required_count=1,
                available_count=0,
            )
            for value in build_rows
        )
        return _build_readiness_receipt(
            {
                "contract": "casepath.pace-build-input-readiness/1.0.0",
                "classification": "PACE_CORE_INPUT_NOT_READY",
                **authority_fields,
                "census_anchor_sha256": census.anchor_sha256,
                "census_roster_file_sha256": census.roster_file_sha256,
                "authenticated_census_sha256": census.authenticated_sha256,
                "split_manifest_sha256": split.manifest_sha256,
                "split_exact_target_achieved": split.exact_target_achieved,
                "assigned_build_rows": len(build_rows),
                "required_build_packets": 120,
                "available_build_packets": 0,
                "missing_build_packets": 120,
                "rejected_build_packets": 0,
                "packet_manifest_file_sha256": None,
                "packet_manifest_semantic_sha256": None,
                "packet_anchor_sha256": None,
                "source_roster_file_sha256": None,
                "source_roster_semantic_sha256": None,
                "build_record_ids_sha256": build_record_ids_sha,
                "build_split_row_sha256s_sha256": build_split_rows_sha,
                "denial_guard_status": "NOT_EXECUTED",
                "missing_input_inventory": [
                    value.model_dump(mode="json")
                    for value in missing_packet_inventory
                ],
                "empirical_coverage_claimed": False,
            }
        )
    parse_canonical_pace_json_v1(packet_manifest_bytes)
    manifest = PACEBuildPacketManifestV1.model_validate_json(packet_manifest_bytes)
    manifest_file_sha = hashlib.sha256(packet_manifest_bytes).hexdigest()
    parse_canonical_pace_json_v1(source_roster_bytes)
    source_roster = PACEBuildSourceRosterV1.model_validate_json(source_roster_bytes)
    source_roster_file_sha = hashlib.sha256(source_roster_bytes).hexdigest()
    anchor = PACEBuildPacketAnchorV1.model_validate_json(
        canonical_pace_json_bytes_v1(packet_anchor.model_dump(mode="json"))
    )
    if (
        anchor.anchor_sha256 != authority.expected_build_packet_anchor_sha256
        or anchor.split_manifest_sha256 != split.manifest_sha256
        or manifest.split_manifest_sha256 != split.manifest_sha256
        or anchor.packet_manifest_file_sha256 != manifest_file_sha
        or anchor.packet_manifest_semantic_sha256
        != manifest.manifest_semantic_sha256
        or anchor.manifest_row_sha256s
        != tuple(sorted(value.row_sha256 for value in manifest.rows))
        or anchor.source_roster_file_sha256 != source_roster_file_sha
        or anchor.source_roster_semantic_sha256
        != source_roster.roster_semantic_sha256
        or anchor.source_roster_row_sha256s
        != tuple(sorted(value.row_sha256 for value in source_roster.rows))
    ):
        raise ValueError("build packet manifest does not match its external anchor")
    split_by_record = {value.record_id: value for value in build_rows}
    manifest_by_record = {value.record_id: value for value in manifest.rows}
    if set(split_by_record) != set(manifest_by_record):
        raise ValueError("build packet manifest does not cover the exact build split")
    source_rows_by_record: dict[str, list[PACEBuildSourceSpanRowV1]] = defaultdict(
        list
    )
    for row in source_roster.rows:
        source_rows_by_record[row.record_id].append(row)
    if set(source_rows_by_record) != set(split_by_record):
        raise ValueError("source roster does not cover the exact build split")
    inventory_rows: list[PACEBuildInputInventoryRowV1] = []
    for record_id in sorted(split_by_record):
        split_row = split_by_record[record_id]
        binding = manifest_by_record[record_id]
        status: Literal["AVAILABLE", "MISSING", "REJECTED"]
        reason: str
        packet_bytes = packet_bytes_by_path.get(binding.packet_relative_path)
        if packet_bytes is None:
            status, reason = "MISSING", "PACKET_BYTES_ABSENT"
        else:
            try:
                if binding.split_row_sha256 != split_row.row_sha256:
                    raise ValueError("split row mismatch")
                parse_canonical_pace_json_v1(packet_bytes)
                packet = PACEBuildFactualHistoryPacketV1.model_validate_json(
                    packet_bytes
                )
                if (
                    packet.record_id != record_id
                    or hashlib.sha256(packet_bytes).hexdigest()
                    != binding.packet_file_sha256
                    or packet.packet_sha256 != binding.packet_semantic_sha256
                    or packet.source_registry_sha256
                    != binding.source_registry_sha256
                    or tuple(sorted(value.span_sha256 for value in packet.spans))
                    != binding.allowed_span_sha256s
                ):
                    raise ValueError("packet binding mismatch")
                source_rows = source_rows_by_record[record_id]
                if (
                    packet.source_registry_sha256
                    != source_rows[0].source_registry_sha256
                    or tuple(
                        value.model_dump(mode="json") for value in packet.spans
                    )
                    != tuple(value.span.model_dump(mode="json") for value in source_rows)
                ):
                    raise ValueError("packet spans are not externally source-bound")
                assert_outcome_blind_packet_v1(packet.model_dump(mode="json"))
            except (ValueError, TypeError):
                status, reason = "REJECTED", "PACKET_BINDING_OR_DENIAL_GUARD_FAILED"
            else:
                status, reason = "AVAILABLE", "AUTHENTICATED_OUTCOME_BLIND_PACKET"
        inventory_rows.append(
            PACEBuildInputInventoryRowV1(
                scope="build_factual_history",
                record_id=record_id,
                split_row_sha256=split_row.row_sha256,
                status=status,
                reason_code=reason,
                required_count=1,
                available_count=1 if status == "AVAILABLE" else 0,
                packet_file_sha256=(
                    binding.packet_file_sha256 if status == "AVAILABLE" else None
                ),
                packet_semantic_sha256=(
                    binding.packet_semantic_sha256 if status == "AVAILABLE" else None
                ),
                packet_anchor_sha256=anchor.anchor_sha256,
                source_registry_sha256=(
                    binding.source_registry_sha256 if status == "AVAILABLE" else None
                ),
            )
        )
    available = sum(value.status == "AVAILABLE" for value in inventory_rows)
    missing = sum(value.status == "MISSING" for value in inventory_rows)
    rejected = sum(value.status == "REJECTED" for value in inventory_rows)
    structurally_ready = (
        split.exact_target_achieved
        and len(build_rows) == available == 120
        and not missing
        and not rejected
    )
    if structurally_ready and authority_status == "TEST_ONLY_SYNTHETIC":
        classification = "PACE_CORE_INPUT_READY_120_TEST_ONLY"
    else:
        classification = "PACE_CORE_INPUT_NOT_READY"
    return _build_readiness_receipt(
        {
            "contract": "casepath.pace-build-input-readiness/1.0.0",
            "classification": classification,
            "empirical_readiness_gate": (
                "DISABLED_PENDING_SEPARATELY_ROOTED_ACQUISITION_V2"
            ),
            **authority_fields,
            "census_anchor_sha256": census.anchor_sha256,
            "census_roster_file_sha256": census.roster_file_sha256,
            "authenticated_census_sha256": census.authenticated_sha256,
            "split_manifest_sha256": split.manifest_sha256,
            "split_exact_target_achieved": split.exact_target_achieved,
            "assigned_build_rows": len(build_rows),
            "required_build_packets": 120,
            "available_build_packets": available,
            "missing_build_packets": missing,
            "rejected_build_packets": rejected,
            "packet_manifest_file_sha256": manifest_file_sha,
            "packet_manifest_semantic_sha256": manifest.manifest_semantic_sha256,
            "packet_anchor_sha256": anchor.anchor_sha256,
            "source_roster_file_sha256": source_roster_file_sha,
            "source_roster_semantic_sha256": source_roster.roster_semantic_sha256,
            "build_record_ids_sha256": build_record_ids_sha,
            "build_split_row_sha256s_sha256": build_split_rows_sha,
            "denial_guard_status": "PASS",
            "missing_input_inventory": [
                value.model_dump(mode="json") for value in inventory_rows
            ],
            "empirical_coverage_claimed": False,
        }
    )
