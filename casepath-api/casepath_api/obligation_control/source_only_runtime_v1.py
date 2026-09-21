"""Provider-free product mechanics and exact study-reservation arithmetic.

Loading a pack reads four allowlisted source/preparation JSON files, never a
benchmark, a target bundle, a demo answer or historical predictions. Upstream
semantic assessments remain trusted, provenance-labelled inputs, not certified
truth. Canonical admission and experimental execution are intentionally absent.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_CEILING
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

from .obligation_control_v1 import Graph, Invalid, Truth, fields, truth
from .evidence_demand_v1 import capabilities, evidence_state, plan
from .native150_export_v1 import export

CONTRACT = "casepath.source-only-runtime/1.0.0"
FILES = {"control": "control.json", "capabilities": "capabilities.json",
         "native_binding": "native_binding.json", "source_registry": "source_registry.json"}
MAX_FILE_BYTES = 2 * 1024 * 1024


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def decode(raw: bytes) -> Any:
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise Invalid("duplicate JSON object key")
            out[key] = value
        return out
    def bad(value):
        raise Invalid("nonfinite JSON constant: " + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)


def regular_bytes(path: Path, limit: int) -> bytes:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise Invalid("pack input is not a regular file")
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise Invalid("pack input exceeds size bound")
    return raw


def hash_string(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


class SourceOnlyRuntime:
    def __init__(self, control: dict, capability_rows: list, native_binding: dict, registry: dict):
        control, capability_rows, native_binding, registry = copy.deepcopy((control, capability_rows, native_binding, registry))
        if not isinstance(registry, dict) or not registry or len(registry) > 4096:
            raise Invalid("source registry must be a nonempty bounded map")
        locator_keys = {"artifact_id", "artifact_sha256", "locator_kind", "page", "exact_text", "text_start", "text_end",
                        "image_region", "source_version", "effective_date", "json_pointer", "canonical_value_sha256"}
        for ref, row in registry.items():
            if not isinstance(ref, str) or not ref:
                raise Invalid("invalid source reference")
            fields(row, {"locator", "text"})
            loc = fields(row["locator"], {"artifact_id", "artifact_sha256", "locator_kind"}, locator_keys - {"artifact_id", "artifact_sha256", "locator_kind"})
            if not hash_string(loc["artifact_sha256"]):
                raise Invalid("invalid locator artifact hash")
            kind = loc["locator_kind"]
            if kind in {"text_span", "authority_passage"}:
                if not isinstance(row["text"], str) or not isinstance(loc.get("exact_text"), str) or not loc["exact_text"] or loc["exact_text"] not in row["text"]:
                    raise Invalid("quote does not occur in its own supplied passage")
                if type(loc.get("page")) is not int or loc["page"] < 1:
                    raise Invalid("text locator lacks page")
                start, end = loc.get("text_start"), loc.get("text_end")
                if (start is None) != (end is None):
                    raise Invalid("partial text offsets")
                if start is not None and (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(row["text"]) or row["text"][start:end] != loc["exact_text"]):
                    raise Invalid("source text offsets do not resolve")
            elif kind == "json_pointer":
                if not isinstance(loc.get("json_pointer"), str) or not loc["json_pointer"].startswith("/") or not hash_string(loc.get("canonical_value_sha256")):
                    raise Invalid("invalid JSON locator")
            elif kind not in {"whole_artifact", "image_region"}:
                raise Invalid("unknown locator kind")
            if kind == "image_region":
                region = loc.get("image_region")
                if type(loc.get("page")) is not int or loc["page"] < 1 or not isinstance(region, list) or len(region) != 4 or any(type(v) not in {int, float} or not 0 <= v <= 1 for v in region) or not region[0] < region[2] or not region[1] < region[3]:
                    raise Invalid("invalid image coordinates")
        self.graph = Graph.parse(control, set(registry))
        self.capabilities = capabilities(capability_rows, set(registry))
        self.binding, self.registry = native_binding, registry
        self.pack_identity = digest({"control": control, "capabilities": capability_rows,
                                     "native_binding": native_binding, "source_registry": registry})

    @classmethod
    def load(cls, directory: Path, expected_manifest_sha256: str) -> SourceOnlyRuntime:
        directory = Path(directory)
        if directory.is_symlink() or not directory.is_dir() or not hash_string(expected_manifest_sha256):
            raise Invalid("invalid pack directory or expected manifest identity")
        raw = regular_bytes(directory / "PACK_MANIFEST.json", 65536)
        if hashlib.sha256(raw).hexdigest() != expected_manifest_sha256:
            raise Invalid("source-only manifest identity mismatch")
        manifest = fields(decode(raw), {"contract", "files"})
        if manifest["contract"] != "casepath.source-only-pack/1.0.0" or not isinstance(manifest["files"], dict) or set(manifest["files"]) != set(FILES):
            raise Invalid("source pack contains missing/extra roles")
        # Validate the COMPLETE allowlist before opening any declared payload.
        for role, name in FILES.items():
            rec = fields(manifest["files"][role], {"path", "bytes", "sha256"})
            if rec["path"] != name or not hash_string(rec["sha256"]) or type(rec["bytes"]) is not int or not 0 < rec["bytes"] <= MAX_FILE_BYTES:
                raise Invalid("invalid payload path, size or identity")
        values = {}
        for role, name in FILES.items():
            payload = regular_bytes(directory / name, MAX_FILE_BYTES)
            record = manifest["files"][role]
            if len(payload) != record["bytes"] or hashlib.sha256(payload).hexdigest() != record["sha256"]:
                raise Invalid("source payload identity mismatch")
            values[role] = decode(payload)
        return cls(values["control"], values["capabilities"], values["native_binding"], values["source_registry"])

    def run(self, case: dict, *, execution_mode: str = "graph") -> dict:
        fields(case, {"contract", "case_id", "materials", "guard_verdicts", "evidence", "origin", "inference_receipt_sha256"})
        if case["contract"] != "casepath.observation-state/1.0.0" or case["origin"] not in {"engineering_fixture", "model_execution"}:
            raise Invalid("invalid observation contract/origin")
        if case["origin"] == "model_execution" and not hash_string(case["inference_receipt_sha256"]):
            raise Invalid("model-derived observations require a receipt identity")
        materials = case["materials"]
        if not isinstance(materials, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in materials.items()):
            raise Invalid("materials must be source-id/text pairs")
        if not isinstance(case["guard_verdicts"], dict) or set(case["guard_verdicts"]) - set(self.graph.variables):
            raise Invalid("unknown guard observations")
        observations = {}
        for name, row in case["guard_verdicts"].items():
            fields(row, {"value", "source_id", "quote"})
            value = truth(row["value"])
            if value != Truth.UNKNOWN and (row["source_id"] not in materials or not isinstance(row["quote"], str) or not row["quote"] or row["quote"] not in materials[row["source_id"]]):
                raise Invalid("guard verdict needs exact quote from its named case material")
            observations[name] = row["value"]
        evidence = evidence_state(case["evidence"], self.capabilities, set(materials))
        result = plan(self.graph, self.capabilities, observations, evidence, execution_mode=execution_mode)
        native = export(self.graph, self.capabilities, result, evidence, self.binding, self.registry, case["case_id"])
        return {"contract": CONTRACT, "case_id": case["case_id"], "execution_mode": execution_mode, "pack_identity": self.pack_identity,
                "observation_identity": digest(case), "origin": case["origin"],
                "inference_receipt_sha256": case["inference_receipt_sha256"],
                "planning": result, "native_artifact": native,
                "provider_calls_by_this_runtime": 0, "native_scoring_performed": False,
                "calibration_claim_supported": False,
                "source_check": "exact_locator_and_quote_resolution_not_semantic_entailment",
                "receipt_validation": "identity_recorded_only; gateway collector must authenticate actual inference"}


def cost_bound(config: dict) -> dict:
    """Worst-case reservation from PROPOSED aggregate token/call ceilings.

    Cache read/write rates are added for every input token, conservatively avoiding
    assumptions about whether the provider bills them instead of or in addition to
    ordinary input. No browsing/tools are permitted in this configuration.
    """
    pricing = config["price_snapshot"]
    def money(key):
        x = Decimal(pricing[key])
        if not x.is_finite() or x < 0:
            raise Invalid("invalid price")
        return x
    input_price = money("prompt") + money("input_cache_read") + money("input_cache_write")
    output_price = money("completion")
    rows, total = [], Decimal(0)
    for bucket in config["reservation_buckets"]:
        keys = ("units", "max_requests_per_unit", "max_input_tokens_per_request", "max_output_tokens_per_request",
                "max_total_input_tokens_per_unit", "max_total_output_tokens_per_unit")
        if any(type(bucket[k]) is not int or bucket[k] < 0 for k in keys):
            raise Invalid("invalid reservation count")
        if bucket["max_input_tokens_per_request"] >= pricing["long_context_threshold"]:
            raise Invalid("long-context tier is outside this bound")
        if bucket["max_total_input_tokens_per_unit"] > bucket["max_requests_per_unit"] * bucket["max_input_tokens_per_request"] or bucket["max_total_output_tokens_per_unit"] > bucket["max_requests_per_unit"] * bucket["max_output_tokens_per_request"]:
            raise Invalid("aggregate exceeds declared physical request capacity")
        value = bucket["units"] * (bucket["max_total_input_tokens_per_unit"] * input_price + bucket["max_total_output_tokens_per_unit"] * output_price)
        total += value
        rows.append({"name": bucket["name"], "reserved_usd": str(value), "physical_request_ceiling": bucket["units"] * bucket["max_requests_per_unit"]})
    rounded = total.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
    if rounded > Decimal(config["proposed_hard_ceiling_usd"]):
        raise Invalid("proposal ceiling does not cover complete schedule")
    if config["provider_execution_enabled"] is not False or Decimal(config["authorized_additional_spend_usd"]) != 0:
        raise Invalid("this construction configuration grants no provider authority")
    return {"contract": "casepath.proposed-reservation/1.0.0", "buckets": rows,
            "exact_usd": str(total), "rounded_up_usd": str(rounded),
            "charged_input_rate_per_token": str(input_price), "charged_output_rate_per_token": str(output_price),
            "provider_execution_enabled": False, "authorized_additional_spend_usd": "0",
            "interpretation": "capacity ceiling, not expected bill or authorization; no unpriced services allowed"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Provider-free reservation calculation only")
    parser.add_argument("--cost-config", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(cost_bound(decode(regular_bytes(args.cost_config, MAX_FILE_BYTES))), indent=2))


if __name__ == "__main__":
    main()
