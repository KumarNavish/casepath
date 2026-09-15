"""Native source-prefix assembly and a dormant metered Codex transport boundary.

This module accepts only already-admitted raw bytes and renderer products.  It
does not decide what the sources mean, dispatch requests, or run a model.  A
caller must inject an explicitly authorized transport before ``invoke`` can do
anything beyond building a reproducible request.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SCHEMA_VERSION = "casepath.native-live-entry/1"
PRIOR_FIELDS = (
    "need_id", "description", "answer", "warrant_refs", "evidence", "state", "until",
)
STATES = {
    "missing", "partial", "pending", "received", "contested", "conditional",
    "withdrawn", "uncertain",
}
EVIDENCE_ROLES = {"support", "contrary", "correction", "context"}
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MINI_MODEL = "openai/gpt-5.4-mini"
OPENROUTER_MINI_PROVIDER = "OpenAI"
OPENROUTER_RESPONSE_LIMIT_BYTES = 1_000_000
OPENROUTER_INPUT_USD_PER_MILLION_TOKENS = 0.75
OPENROUTER_OUTPUT_USD_PER_MILLION_TOKENS = 4.50
OPENROUTER_HIGH_DETAIL_IMAGE_TOKEN_UPPER_BOUND = 3_001
OPENROUTER_IMAGE_TOKEN_SOURCE = (
    "https://developers.openai.com/api/docs/guides/images-vision"
    "#patch-based-image-tokenization"
)


def canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def aware_instant(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include an offset")
    return parsed


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 200:
        raise ValueError(f"invalid {label}")
    return value


@dataclass(frozen=True)
class TextUnit:
    """One addressable renderer unit within a complete text view."""

    text: str
    start: int
    end: int

    def validate(self, enclosing_text: str) -> None:
        if (
            type(self.start) is not int
            or type(self.end) is not int
            or self.start < 0
            or self.end <= self.start
            or self.end > len(enclosing_text)
            or enclosing_text[self.start : self.end] != self.text
        ):
            raise ValueError("text unit is not an exact span of its enclosing view")


@dataclass(frozen=True)
class RenderedTextView:
    source_id: str
    view_id: str
    media_type: str
    text: str
    text_sha256: str
    raw_artifact_sha256: str
    units: tuple[TextUnit, ...]
    first_observed_at: str

    def validate(self, artifact_sha256: str, observed_at: str) -> None:
        _identifier(self.source_id, "source_id")
        _identifier(self.view_id, "view_id")
        if not self.media_type.startswith("text/"):
            raise ValueError("rendered text view must declare text media type")
        if sha256_bytes(self.text.encode("utf-8")) != self.text_sha256:
            raise ValueError("rendered text hash mismatch")
        if self.raw_artifact_sha256 != artifact_sha256:
            raise ValueError("text view is not bound to admitted raw artifact")
        if aware_instant(self.first_observed_at) > aware_instant(observed_at):
            raise ValueError("future text view")
        if not self.units:
            raise ValueError("text view has no addressable units")
        previous_end = 0
        for unit in self.units:
            unit.validate(self.text)
            if unit.start != previous_end:
                raise ValueError("text units must form a contiguous partition of the full view")
            previous_end = unit.end
        if previous_end != len(self.text):
            raise ValueError("text units must include the full view suffix")


@dataclass(frozen=True)
class NativeImageView:
    """Exact bytes sent to a multimodal reader.

    For a PDF this is an existing rendered page image tied to the raw PDF hash;
    for a JPEG it is the admitted JPEG itself.
    """

    source_id: str
    view_id: str
    media_type: str
    image_bytes: bytes
    image_sha256: str
    raw_artifact_sha256: str
    first_observed_at: str
    page_index: int | None = None

    def validate(self, artifact_sha256: str, artifact_media_type: str, observed_at: str) -> None:
        _identifier(self.source_id, "source_id")
        _identifier(self.view_id, "view_id")
        if self.media_type not in {"image/jpeg", "image/png"}:
            raise ValueError("unsupported native image media type")
        if sha256_bytes(self.image_bytes) != self.image_sha256:
            raise ValueError("native image byte hash mismatch")
        if self.raw_artifact_sha256 != artifact_sha256:
            raise ValueError("native image is not bound to admitted raw artifact")
        if artifact_media_type.startswith("image/") and self.image_sha256 != artifact_sha256:
            raise ValueError("native image artifact must pass its admitted raw bytes unchanged")
        if artifact_media_type == "application/pdf" and self.page_index is None:
            raise ValueError("PDF page image requires page_index")
        if self.page_index is not None and (type(self.page_index) is not int or self.page_index < 0):
            raise ValueError("invalid page_index")
        if aware_instant(self.first_observed_at) > aware_instant(observed_at):
            raise ValueError("future native image view")


@dataclass(frozen=True)
class AdmittedRawSource:
    """Server-admitted raw bytes plus renderer outputs from those bytes."""

    artifact_id: str
    media_type: str
    raw_bytes: bytes
    raw_sha256: str
    text_views: tuple[RenderedTextView, ...] = ()
    native_views: tuple[NativeImageView, ...] = ()
    admission_receipt: Mapping[str, Any] = field(default_factory=dict)

    def validate(self, observed_at: str) -> None:
        _identifier(self.artifact_id, "artifact_id")
        if sha256_bytes(self.raw_bytes) != self.raw_sha256:
            raise ValueError("admitted raw artifact hash mismatch")
        if not self.text_views and not self.native_views:
            raise ValueError("admitted source has no observable renderer output")
        for view in self.text_views:
            view.validate(self.raw_sha256, observed_at)
        for view in self.native_views:
            view.validate(self.raw_sha256, self.media_type, observed_at)


@dataclass(frozen=True)
class PreparedInference:
    messages: tuple[Mapping[str, Any], ...]
    input_identity: str
    source_prefix_sha256: str
    source_receipts: tuple[Mapping[str, Any], ...]
    image_receipts: tuple[Mapping[str, Any], ...]
    observed_at: str


class SourcePrefixAssembler:
    """Build the existing native actor message schema from current source state."""

    def __init__(self, asset_directory: str | Path):
        self.asset_directory = Path(asset_directory)

    def assemble(
        self,
        *,
        sources: Sequence[AdmittedRawSource],
        observed_at: str,
        prior_self: Sequence[Mapping[str, Any]],
        system_prompt: str,
        public_context: Mapping[str, Any] | None = None,
    ) -> PreparedInference:
        aware_instant(observed_at)
        if not isinstance(system_prompt, str) or not system_prompt:
            raise ValueError("system prompt is required")
        if not sources:
            raise ValueError("at least one admitted source is required")
        for source in sources:
            source.validate(observed_at)

        prior = self._public_prior(prior_self)
        text_payload: list[dict[str, Any]] = []
        image_payload: list[dict[str, Any]] = []
        image_parts: list[dict[str, Any]] = []
        source_receipts: list[dict[str, Any]] = []
        image_receipts: list[dict[str, Any]] = []
        text_alias = 0
        image_alias = 0
        seen_views: set[tuple[str, str]] = set()

        self.asset_directory.mkdir(parents=True, exist_ok=True)
        for source in sources:
            source_receipts.append(
                {
                    "artifact_id": source.artifact_id,
                    "media_type": source.media_type,
                    "raw_sha256": source.raw_sha256,
                    "size_bytes": len(source.raw_bytes),
                    "admission_receipt": dict(source.admission_receipt),
                }
            )
            for view in source.text_views:
                key = (view.source_id, view.view_id)
                if key in seen_views:
                    raise ValueError("duplicate source/view identity")
                seen_views.add(key)
                units = []
                for unit in view.units:
                    units.append({"ref": f"t{text_alias}", "text": unit.text})
                    text_alias += 1
                text_payload.append(
                    {
                        "source_id": view.source_id,
                        "view_id": view.view_id,
                        "first_observed_at": view.first_observed_at,
                        "units": units,
                    }
                )
            for view in source.native_views:
                key = (view.source_id, view.view_id)
                if key in seen_views:
                    raise ValueError("duplicate source/view identity")
                seen_views.add(key)
                alias = f"p{image_alias}"
                image_alias += 1
                suffix = ".jpg" if view.media_type == "image/jpeg" else ".png"
                path = self.asset_directory / f"{view.image_sha256}{suffix}"
                self._write_exact(path, view.image_bytes)
                image_payload.append(
                    {
                        "ref": alias,
                        "source_id": view.source_id,
                        "view_id": view.view_id,
                        "page_index": view.page_index,
                        "first_observed_at": view.first_observed_at,
                    }
                )
                image_parts.extend(
                    [
                        {
                            "type": "text",
                            "text": f"Physical image view {alias} ({view.source_id}, {view.view_id})",
                        },
                        {
                            "type": "image",
                            "image_path": str(path),
                            "sha256": view.image_sha256,
                            "image_id": alias,
                        },
                    ]
                )
                image_receipts.append(
                    {
                        "image_id": alias,
                        "source_id": view.source_id,
                        "view_id": view.view_id,
                        "image_path": str(path),
                        "sha256": view.image_sha256,
                        "size_bytes": len(view.image_bytes),
                        "media_type": view.media_type,
                        "raw_artifact_sha256": view.raw_artifact_sha256,
                        "page_index": view.page_index,
                    }
                )

        context = dict(public_context or {})
        reserved = {"text_views", "image_views", "observed_at", "prior_self"}
        if reserved & set(context):
            raise ValueError("public context shadows native source fields")
        payload = {
            "text_views": text_payload,
            "image_views": image_payload,
            "observed_at": observed_at,
            "prior_self": prior,
            **context,
        }
        content: list[dict[str, Any]] = [{"type": "text", "text": canonical(payload)}]
        content.extend(image_parts)
        messages: tuple[Mapping[str, Any], ...] = (
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        )
        source_prefix = {
            "schema_version": SCHEMA_VERSION,
            "text_views": [
                {
                    **row,
                    "units": row["units"],
                }
                for row in text_payload
            ],
            "image_views": [
                {
                    **row,
                    "sha256": image_receipts[index]["sha256"],
                    "raw_artifact_sha256": image_receipts[index]["raw_artifact_sha256"],
                }
                for index, row in enumerate(image_payload)
            ],
            "source_receipts": [
                {key: row[key] for key in ("artifact_id", "media_type", "raw_sha256", "size_bytes")}
                for row in source_receipts
            ],
        }
        source_prefix_sha256 = digest(source_prefix)
        identity_material = {
            "schema_version": SCHEMA_VERSION,
            "source_prefix_sha256": source_prefix_sha256,
            "observed_at": observed_at,
            "prior_self": prior,
            "public_context": context,
            "system_sha256": sha256_bytes(system_prompt.encode("utf-8")),
            "image_order": [r["sha256"] for r in image_receipts],
        }
        return PreparedInference(
            messages=messages,
            input_identity=digest(identity_material),
            source_prefix_sha256=source_prefix_sha256,
            source_receipts=tuple(source_receipts),
            image_receipts=tuple(image_receipts),
            observed_at=observed_at,
        )

    @staticmethod
    def _public_prior(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, Mapping) or set(row) != set(PRIOR_FIELDS):
                raise ValueError("prior_self must contain only the public actor fields")
            item = {key: row[key] for key in PRIOR_FIELDS}
            if not isinstance(item["need_id"], str) or not item["need_id"] or item["need_id"] in seen:
                raise ValueError("invalid or duplicate prior need_id")
            seen.add(item["need_id"])
            if item["state"] not in STATES:
                raise ValueError("invalid prior state")
            if item["until"] is not None:
                aware_instant(item["until"])
            if item["answer"] is not None and not isinstance(item["answer"], str):
                raise ValueError("prior answer must be string or null")
            if not isinstance(item["warrant_refs"], list) or not isinstance(item["evidence"], list):
                raise ValueError("invalid prior source references")
            result.append(item)
        return result

    @staticmethod
    def _write_exact(path: Path, raw: bytes) -> None:
        if path.exists():
            if not path.is_file() or sha256_bytes(path.read_bytes()) != sha256_bytes(raw):
                raise ValueError("materialized native asset collision")
            return
        # The destination is content-addressed, so two threads or two processes may legitimately
        # materialize the same asset at once. A temporary name shared between writers let one overwrite
        # another's bytes mid-write; the first writer then read back the other's bytes and failed its own
        # check. The name is unique per writer for that reason, and per the convention in local_data_root.
        temporary = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4()}.tmp"
        try:
            temporary.write_bytes(raw)
            if sha256_bytes(temporary.read_bytes()) != sha256_bytes(raw):
                raise ValueError("native asset materialization failed")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class ProviderConfig:
    output_schema_path: str
    working_directory: str
    final_output_path: str
    model: str = "gpt-5.6-sol"
    reasoning_effort: str = "xhigh"
    codex_executable: str = "codex"
    timeout_seconds: int = 300
    transport_kind: str = "codex"
    endpoint: str | None = None
    max_input_tokens: int = 16_384
    max_output_tokens: int = 3_072
    maximum_call_cost_usd: float | None = None


@dataclass(frozen=True)
class TransportRequest:
    argv: tuple[str, ...]
    stdin: str
    timeout_seconds: int
    cwd: str
    inference_identity: str
    input_identity: str
    image_receipts: tuple[Mapping[str, Any], ...]
    transport_kind: str = "codex"
    endpoint: str | None = None
    http_payload: Mapping[str, Any] | None = None
    estimated_input_tokens_upper_bound: int | None = None
    reserved_max_cost_usd: float | None = None
    image_token_upper_bound: int | None = None


@dataclass(frozen=True)
class TransportResponse:
    returncode: int | None
    stdout: str
    stderr: str
    final_output: str | None
    timed_out: bool = False
    http_status: int | None = None


Transport = Callable[[TransportRequest], TransportResponse]


class MeteredCodexProvider:
    """A transport-injected provider with no default command execution path."""

    def __init__(
        self,
        config: ProviderConfig,
        transport: Transport | None = None,
        *,
        output_validator: Callable[[Any], None] | None = None,
    ):
        self.config = config
        self.transport = transport
        self.output_validator = output_validator or validate_actor_output
        self._attempts: list[dict[str, Any]] = []

    def build_request(self, prepared: PreparedInference) -> TransportRequest:
        if self.config.transport_kind == "openrouter":
            return self._build_openrouter_request(prepared)
        if self.config.transport_kind != "codex":
            raise ValueError("unsupported native provider transport")
        if len(prepared.messages) != 2:
            raise ValueError("expected system and user messages")
        system, user = prepared.messages
        if system.get("role") != "system" or user.get("role") != "user":
            raise ValueError("invalid message roles")
        schema_path = Path(self.config.output_schema_path)  # deliberately not .resolve()
        schema_raw = schema_path.read_bytes()
        json.loads(schema_raw)
        text_parts: list[str] = []
        image_paths: list[str] = []
        for part in user["content"]:
            if part.get("type") == "text":
                text_parts.append(part["text"])
            elif part.get("type") == "image":
                path = Path(part["image_path"])
                raw = path.read_bytes()
                if sha256_bytes(raw) != part["sha256"]:
                    raise ValueError("native image drift before provider handoff")
                image_paths.append(str(path))
            else:
                raise ValueError("unsupported message content")
        stdin = "\n\n".join(text_parts)
        workdir = Path(self.config.working_directory)  # deliberately not .resolve()
        argv = [
            self.config.codex_executable,
            "exec",
            "--json",
            "--ignore-user-config",
            "--ignore-rules",
            "--strict-config",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--cd",
            str(workdir),
            "--model",
            self.config.model,
            "--config",
            "model_reasoning_effort=" + json.dumps(self.config.reasoning_effort),
            "--config",
            "developer_instructions=" + json.dumps(system["content"], ensure_ascii=True),
        ]
        for image_path in image_paths:
            argv.extend(["--image", image_path])
        final_output_path = Path(self.config.final_output_path)  # deliberately not .resolve()
        argv.extend(
            [
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(final_output_path),
                "-",
            ]
        )
        invocation_material = {
            "input_identity": prepared.input_identity,
            "stdin_sha256": sha256_bytes(stdin.encode("utf-8")),
            "schema_sha256": sha256_bytes(schema_raw),
            "model": self.config.model,
            "reasoning_effort": self.config.reasoning_effort,
            "images": [row["sha256"] for row in prepared.image_receipts],
        }
        return TransportRequest(
            argv=tuple(argv),
            stdin=stdin,
            timeout_seconds=self.config.timeout_seconds,
            cwd=str(workdir),
            inference_identity=digest(invocation_material),
            input_identity=prepared.input_identity,
            image_receipts=prepared.image_receipts,
        )

    def _build_openrouter_request(
        self, prepared: PreparedInference
    ) -> TransportRequest:
        if len(prepared.messages) != 2:
            raise ValueError("expected system and user messages")
        system, user = prepared.messages
        if system.get("role") != "system" or user.get("role") != "user":
            raise ValueError("invalid message roles")
        if self.config.model != OPENROUTER_MINI_MODEL:
            raise ValueError("native OpenRouter model is not the pinned mini model")
        if self.config.reasoning_effort != "low":
            raise ValueError("native OpenRouter reasoning effort must be low")
        if (
            type(self.config.max_input_tokens) is not int
            or not 1 <= self.config.max_input_tokens <= 32_768
            or type(self.config.max_output_tokens) is not int
            or not 1 <= self.config.max_output_tokens <= 3_072
        ):
            raise ValueError("native OpenRouter token bounds are invalid")
        if (
            self.config.maximum_call_cost_usd is None
            or not 0 < self.config.maximum_call_cost_usd <= 0.05
        ):
            raise ValueError("native OpenRouter call cost bound is absent or invalid")
        schema_path = Path(self.config.output_schema_path)
        schema_raw = schema_path.read_bytes()
        schema = json.loads(schema_raw)
        if not isinstance(schema, dict):
            raise ValueError("native output schema must be an object")

        user_parts: list[dict[str, Any]] = []
        text_parts: list[str] = []
        image_index = 0
        for part in user["content"]:
            if part.get("type") == "text":
                text = part.get("text")
                if not isinstance(text, str) or not text:
                    raise ValueError("native user text is empty")
                text_parts.append(text)
                user_parts.append({"type": "text", "text": text})
                continue
            if part.get("type") != "image":
                raise ValueError("unsupported message content")
            path = Path(part["image_path"])
            raw = path.read_bytes()
            if sha256_bytes(raw) != part["sha256"]:
                raise ValueError("native image drift before provider handoff")
            if image_index >= len(prepared.image_receipts):
                raise ValueError("native image receipt is absent")
            receipt = prepared.image_receipts[image_index]
            image_index += 1
            if receipt.get("sha256") != part["sha256"]:
                raise ValueError("native image order differs from its receipt")
            media_type = receipt.get("media_type")
            if media_type not in {"image/jpeg", "image/png"}:
                raise ValueError("native image media type is invalid")
            user_parts.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "detail": "high",
                        "url": (
                            f"data:{media_type};base64,"
                            + base64.b64encode(raw).decode("ascii")
                        )
                    },
                }
            )
        if image_index != len(prepared.image_receipts):
            raise ValueError("native image receipts are not fully represented")
        stdin = "\n\n".join(text_parts)
        payload = {
            "model": self.config.model,
            "provider": {
                "only": ["openai"],
                "order": ["openai"],
                "allow_fallbacks": False,
                "require_parameters": True,
            },
            "reasoning": {"effort": self.config.reasoning_effort},
            "max_tokens": self.config.max_output_tokens,
            "messages": [
                {"role": "system", "content": system["content"]},
                {"role": "user", "content": user_parts},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "casepath_native_actor_v1",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        endpoint = self.config.endpoint or OPENROUTER_ENDPOINT
        if endpoint != OPENROUTER_ENDPOINT:
            raise ValueError("native OpenRouter endpoint is not pinned")
        # The transport's base64 bytes are replaced by stable markers for text
        # metering because image content is billed through the separate patch
        # bound. Counting every remaining UTF-8 byte as a token deliberately
        # over-reserves the complete schema, instructions, sources, and JSON
        # framing without relying on a tokenizer approximation.
        metering_payload = json.loads(canonical(payload))
        metering_user_parts = metering_payload["messages"][1]["content"]
        metered_images = 0
        for metering_part in metering_user_parts:
            if metering_part.get("type") != "image_url":
                continue
            receipt = prepared.image_receipts[metered_images]
            metered_images += 1
            metering_part["image_url"]["url"] = (
                "data:"
                + str(receipt["media_type"])
                + ";base64,[native-image-sha256:"
                + str(receipt["sha256"])
                + "]"
            )
        structured_text_byte_upper_bound = len(
            canonical(metering_payload).encode("utf-8")
        )
        image_token_upper_bound = (
            metered_images * OPENROUTER_HIGH_DETAIL_IMAGE_TOKEN_UPPER_BOUND
        )
        estimated_input_tokens = (
            structured_text_byte_upper_bound + image_token_upper_bound
        )
        if estimated_input_tokens > self.config.max_input_tokens:
            raise ValueError(
                "native OpenRouter input exceeds its conservative token bound"
            )
        reserved_max_cost_usd = (
            self.config.max_input_tokens
            * OPENROUTER_INPUT_USD_PER_MILLION_TOKENS
            + self.config.max_output_tokens
            * OPENROUTER_OUTPUT_USD_PER_MILLION_TOKENS
        ) / 1_000_000
        if reserved_max_cost_usd > float(self.config.maximum_call_cost_usd):
            raise ValueError(
                "native OpenRouter call cost cap cannot cover token bounds"
            )
        invocation_material = {
            "input_identity": prepared.input_identity,
            "payload_sha256": sha256_bytes(canonical(payload).encode("utf-8")),
            "model": self.config.model,
            "reasoning_effort": self.config.reasoning_effort,
            "maximum_call_cost_usd": self.config.maximum_call_cost_usd,
            "estimated_input_tokens_upper_bound": estimated_input_tokens,
            "reserved_max_cost_usd": reserved_max_cost_usd,
            "images": [row["sha256"] for row in prepared.image_receipts],
        }
        return TransportRequest(
            argv=(),
            stdin=stdin,
            timeout_seconds=self.config.timeout_seconds,
            cwd=str(Path(self.config.working_directory)),
            inference_identity=digest(invocation_material),
            input_identity=prepared.input_identity,
            image_receipts=prepared.image_receipts,
            transport_kind="openrouter",
            endpoint=endpoint,
            http_payload=payload,
            estimated_input_tokens_upper_bound=estimated_input_tokens,
            reserved_max_cost_usd=reserved_max_cost_usd,
            image_token_upper_bound=image_token_upper_bound,
        )

    def invoke(self, request: TransportRequest) -> Mapping[str, Any]:
        """Invoke only an injected transport; default construction is inert."""

        if self.transport is None:
            raise RuntimeError("provider is dormant: inject an authorized transport")
        started = time.monotonic()
        try:
            response = self.transport(request)
            if not isinstance(response, TransportResponse):
                raise TypeError("transport returned the wrong response type")
            receipt = self._receipt(request, response, time.monotonic() - started)
        except Exception as exc:
            receipt = {
                "inference_identity": request.inference_identity,
                "qualified": False,
                "attempted": True,
                "wall_latency_seconds": time.monotonic() - started,
                "transport_error": {"type": type(exc).__name__, "message": str(exc)},
                "usage": None,
            }
        self._attempts.append(receipt)
        return receipt

    def _receipt(
        self, request: TransportRequest, response: TransportResponse, elapsed: float
    ) -> dict[str, Any]:
        if request.transport_kind == "openrouter":
            return self._openrouter_receipt(request, response, elapsed)
        events: list[dict[str, Any]] = []
        parse_errors: list[dict[str, Any]] = []
        for line_number, line in enumerate(response.stdout.splitlines(), 1):
            try:
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("event is not an object")
                events.append(value)
            except Exception as exc:
                parse_errors.append({"line": line_number, "error": str(exc)})
        disallowed = []
        for event in events:
            item = event.get("item")
            item_type = item.get("type") if isinstance(item, dict) else None
            if item_type is not None and item_type not in {"reasoning", "agent_message"}:
                disallowed.append({"event_type": event.get("type"), "item_type": item_type})
        completed = [event for event in events if event.get("type") == "turn.completed"]
        event_errors = [event for event in events if event.get("type") in {"error", "turn.failed"}]
        agent_messages = [
            (index, event["item"].get("text"))
            for index, event in enumerate(events)
            if event.get("type") == "item.completed"
            and isinstance(event.get("item"), dict)
            and event["item"].get("type") == "agent_message"
        ]
        terminal_order_valid = (
            len(agent_messages) == 1
            and len(completed) == 1
            and agent_messages[0][0] == len(events) - 2
            and events[-1] is completed[0]
        )
        agent_message_text = agent_messages[0][1] if len(agent_messages) == 1 else None
        agent_message_valid = isinstance(agent_message_text, str) and bool(agent_message_text.strip())
        final_matches_agent_message = (
            agent_message_valid
            and response.final_output is not None
            and response.final_output == agent_message_text
        )
        usage = completed[0].get("usage") if len(completed) == 1 else None
        usage_fields = {
            key: usage.get(key) if isinstance(usage, dict) else None
            for key in (
                "input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"
            )
        }
        usage_complete = all(type(value) is int and value >= 0 for value in usage_fields.values())
        final_valid = False
        final_error = None
        if response.final_output is not None:
            try:
                self.output_validator(json.loads(response.final_output))
                final_valid = True
            except Exception as exc:
                final_error = str(exc)
        else:
            final_error = "final output absent"
        qualified = all(
            (
                response.returncode == 0,
                not response.timed_out,
                not parse_errors,
                not disallowed,
                not event_errors,
                len(completed) == 1,
                agent_message_valid,
                final_matches_agent_message,
                terminal_order_valid,
                usage_complete,
                final_valid,
            )
        )
        return {
            "inference_identity": request.inference_identity,
            "qualified": qualified,
            "attempted": True,
            "wall_latency_seconds": elapsed,
            "returncode": response.returncode,
            "timed_out": response.timed_out,
            "usage": usage_fields,
            "usage_complete": usage_complete,
            "trace": {
                "event_count": len(events),
                "parse_errors": parse_errors,
                "disallowed_tool_or_item_events": disallowed,
                "event_errors": event_errors,
                "completed_agent_message_count": len(agent_messages),
                "agent_message_nonempty": agent_message_valid,
                "final_output_exactly_matches_agent_message": final_matches_agent_message,
                "terminal_order_valid": terminal_order_valid,
            },
            "transport_error": None,
            "stderr_sha256": sha256_bytes(response.stderr.encode("utf-8")),
            "raw_stdout_sha256": sha256_bytes(response.stdout.encode("utf-8")),
            "raw_stdout": response.stdout,
            "raw_stderr": response.stderr,
            "final_output": response.final_output,
            "final_output_sha256": (
                sha256_bytes(response.final_output.encode("utf-8"))
                if response.final_output is not None
                else None
            ),
            "final_schema_valid": final_valid,
            "source_pointer_semantics_validated": False,
            "final_error": final_error,
        }

    def _openrouter_receipt(
        self, request: TransportRequest, response: TransportResponse, elapsed: float
    ) -> dict[str, Any]:
        envelope: Any = None
        parse_error: str | None = None
        try:
            envelope = json.loads(response.stdout)
            if not isinstance(envelope, dict):
                raise ValueError("provider response is not an object")
        except Exception as exc:
            parse_error = str(exc)
        choices = envelope.get("choices") if isinstance(envelope, dict) else None
        choice = choices[0] if isinstance(choices, list) and len(choices) == 1 else None
        message = choice.get("message") if isinstance(choice, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
        response_identity = {
            "response_id": envelope.get("id") if isinstance(envelope, dict) else None,
            "model": envelope.get("model") if isinstance(envelope, dict) else None,
            "provider": envelope.get("provider") if isinstance(envelope, dict) else None,
            "finish_reason": finish_reason,
        }
        identity_valid = (
            isinstance(response_identity["response_id"], str)
            and bool(response_identity["response_id"].strip())
            and response_identity["model"] == OPENROUTER_MINI_MODEL
            and response_identity["provider"] == OPENROUTER_MINI_PROVIDER
            and finish_reason == "stop"
        )
        final_matches = (
            isinstance(content, str)
            and bool(content.strip())
            and response.final_output == content
        )
        usage_raw = envelope.get("usage") if isinstance(envelope, dict) else None
        prompt_details = (
            usage_raw.get("prompt_tokens_details", {})
            if isinstance(usage_raw, dict)
            else {}
        )
        completion_details = (
            usage_raw.get("completion_tokens_details", {})
            if isinstance(usage_raw, dict)
            else {}
        )
        usage_fields = {
            "input_tokens": (
                usage_raw.get("prompt_tokens") if isinstance(usage_raw, dict) else None
            ),
            "cached_input_tokens": (
                prompt_details.get("cached_tokens")
                if isinstance(prompt_details, dict)
                else None
            ),
            "output_tokens": (
                usage_raw.get("completion_tokens")
                if isinstance(usage_raw, dict)
                else None
            ),
            "reasoning_output_tokens": (
                completion_details.get("reasoning_tokens")
                if isinstance(completion_details, dict)
                else None
            ),
            "total_tokens": (
                usage_raw.get("total_tokens") if isinstance(usage_raw, dict) else None
            ),
        }
        token_usage_complete = all(
            type(value) is int and value >= 0 for value in usage_fields.values()
        ) and usage_fields["total_tokens"] == (
            usage_fields["input_tokens"] + usage_fields["output_tokens"]
        )
        actual_cost = usage_raw.get("cost") if isinstance(usage_raw, dict) else None
        cost_known = (
            isinstance(actual_cost, (int, float))
            and not isinstance(actual_cost, bool)
            and float(actual_cost) >= 0
        )
        cost_within_bound = cost_known and float(actual_cost) <= float(
            self.config.maximum_call_cost_usd or 0
        )
        usage_with_cost = {**usage_fields, "cost": actual_cost}
        final_valid = False
        final_error: str | None = None
        if response.final_output is not None:
            try:
                self.output_validator(json.loads(response.final_output))
                final_valid = True
            except Exception as exc:
                final_error = str(exc)
        else:
            final_error = "final output absent"
        qualified = all(
            (
                response.returncode == 0,
                response.http_status == 200,
                not response.timed_out,
                parse_error is None,
                identity_valid,
                final_matches,
                token_usage_complete,
                cost_within_bound,
                final_valid,
            )
        )
        return {
            "inference_identity": request.inference_identity,
            "transport_kind": "openrouter_http_once",
            "qualified": qualified,
            "attempted": True,
            "wall_latency_seconds": elapsed,
            "returncode": response.returncode,
            "http_status": response.http_status,
            "timed_out": response.timed_out,
            "usage": usage_with_cost,
            "usage_complete": token_usage_complete and cost_known,
            "actual_cost_usd": float(actual_cost) if cost_known else None,
            "provider_identity": response_identity,
            "trace": {
                "request_count": 1,
                "response_parse_error": parse_error,
                "identity_valid": identity_valid,
                "final_output_exactly_matches_provider_message": final_matches,
                "token_usage_complete": token_usage_complete,
                "cost_known": cost_known,
                "cost_within_call_bound": cost_within_bound,
            },
            "transport_error": None,
            "stderr_sha256": sha256_bytes(response.stderr.encode("utf-8")),
            "raw_stdout_sha256": sha256_bytes(response.stdout.encode("utf-8")),
            "raw_stdout": response.stdout,
            "raw_stderr": response.stderr,
            "final_output": response.final_output,
            "final_output_sha256": (
                sha256_bytes(response.final_output.encode("utf-8"))
                if response.final_output is not None
                else None
            ),
            "final_schema_valid": final_valid,
            "source_pointer_semantics_validated": False,
            "final_error": final_error,
        }

    def ledger(self) -> Mapping[str, Any]:
        totals = {
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_output_tokens": 0,
        }
        for receipt in self._attempts:
            usage = receipt.get("usage")
            if isinstance(usage, Mapping):
                for key in totals:
                    value = usage.get(key)
                    if type(value) is int:
                        totals[key] += value
        return {
            "attempt_count": len(self._attempts),
            "qualified_count": sum(bool(x.get("qualified")) for x in self._attempts),
            "transport_error_count": sum(x.get("transport_error") is not None for x in self._attempts),
            "usage_unknown_attempt_count": sum(
                not bool(x.get("usage_complete")) for x in self._attempts
            ),
            "usage_totals": totals,
            "attempts": list(self._attempts),
        }


MeteredNativeProvider = MeteredCodexProvider


def openrouter_http_once_transport(request: TransportRequest) -> TransportResponse:
    """Execute exactly one pinned OpenRouter HTTP request.

    Credentials are read only at send time and never enter the request object,
    journal material, response body, or error text retained by this boundary.
    """

    if (
        request.transport_kind != "openrouter"
        or request.endpoint != OPENROUTER_ENDPOINT
        or not isinstance(request.http_payload, Mapping)
    ):
        raise ValueError("invalid OpenRouter transport request")
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OpenRouter transport credential is not configured")
    body = canonical(dict(request.http_payload)).encode("utf-8")
    outbound = Request(
        request.endpoint,
        data=body,
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            "HTTP-Referer": "https://casepath.local",
            "X-Title": "CasePath local native research",
        },
        method="POST",
    )
    try:
        with urlopen(outbound, timeout=request.timeout_seconds) as response:  # noqa: S310
            raw = response.read(OPENROUTER_RESPONSE_LIMIT_BYTES + 1)
            status = int(response.status)
    except HTTPError as exc:
        raw = exc.read(OPENROUTER_RESPONSE_LIMIT_BYTES + 1)
        if len(raw) > OPENROUTER_RESPONSE_LIMIT_BYTES:
            raw = b""
        return TransportResponse(
            returncode=1,
            stdout=raw.decode("utf-8", errors="replace"),
            stderr=f"OpenRouter HTTP status {exc.code}",
            final_output=None,
            http_status=int(exc.code),
        )
    except URLError as exc:
        raise RuntimeError("OpenRouter transport failed before a response") from exc
    if len(raw) > OPENROUTER_RESPONSE_LIMIT_BYTES:
        raise RuntimeError("OpenRouter response exceeds the byte limit")
    stdout = raw.decode("utf-8")
    final_output: str | None = None
    try:
        envelope = json.loads(stdout)
        choices = envelope.get("choices") if isinstance(envelope, dict) else None
        choice = choices[0] if isinstance(choices, list) and len(choices) == 1 else None
        message = choice.get("message") if isinstance(choice, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str):
            final_output = content
    except Exception:
        pass
    return TransportResponse(
        returncode=0 if status == 200 else 1,
        stdout=stdout,
        stderr="",
        final_output=final_output,
        http_status=status,
    )


def validate_actor_output(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {"needs"}:
        raise ValueError("actor output must contain only needs")
    if not isinstance(value["needs"], list) or len(value["needs"]) > 8:
        raise ValueError("needs must be a list of at most eight rows")
    required = set(PRIOR_FIELDS)
    need_ids: set[str] = set()
    for row in value["needs"]:
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError("actor need has invalid fields")
        if (
            not isinstance(row["need_id"], str)
            or not row["need_id"]
            or len(row["need_id"]) > 32
            or not row["need_id"][0].isalpha()
            or any(not (character.isalnum() or character in "_-") for character in row["need_id"])
            or row["need_id"] in need_ids
        ):
            raise ValueError("actor need identity is invalid")
        need_ids.add(row["need_id"])
        if not isinstance(row["description"], str) or not row["description"].strip():
            raise ValueError("actor need description is empty")
        if row["state"] not in STATES:
            raise ValueError("actor need state is invalid")
        if row["answer"] is not None and not isinstance(row["answer"], str):
            raise ValueError("actor answer is invalid")
        if (
            not isinstance(row["warrant_refs"], list)
            or not row["warrant_refs"]
            or not all(_valid_public_ref(ref) for ref in row["warrant_refs"])
            or not isinstance(row["evidence"], list)
        ):
            raise ValueError("actor references are invalid")
        for evidence in row["evidence"]:
            if (
                not isinstance(evidence, dict)
                or set(evidence) != {"ref", "role"}
                or not _valid_public_ref(evidence["ref"])
                or evidence["role"] not in EVIDENCE_ROLES
            ):
                raise ValueError("actor evidence is invalid")
        if row["until"] is not None:
            aware_instant(row["until"])


def _valid_public_ref(value: Any) -> bool:
    return isinstance(value, str) and len(value) > 1 and value[0] in "tp" and value[1:].isdigit()


def admitted_from_public_corpus(
    corpus: Any,
    claim_id: str,
    artifact_id: str,
    *,
    text_views: Iterable[RenderedTextView] = (),
    native_views: Iterable[NativeImageView] = (),
) -> AdmittedRawSource:
    """Mount the canonical ``PublicCorpus.artifact`` byte boundary.

    Rendering remains a separate server operation.  Every supplied renderer
    product must carry the hash returned by ``PublicCorpus.artifact`` and will
    be checked again by ``SourcePrefixAssembler``.  No private corpus method is
    used.
    """

    raw, row = corpus.artifact(claim_id, artifact_id)
    identity = corpus.identity
    return AdmittedRawSource(
        artifact_id=artifact_id,
        media_type=str(row["media_type"]),
        raw_bytes=raw,
        raw_sha256=str(row["sha256"]),
        text_views=tuple(text_views),
        native_views=tuple(native_views),
        admission_receipt={
            "authority": "PublicCorpus.artifact",
            "claim_id": claim_id,
            "artifact_id": artifact_id,
            "corpus_manifest_sha256": identity["manifest_sha256"],
        },
    )
