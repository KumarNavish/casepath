from __future__ import annotations

import argparse
import sys

from ..foundation.common import is_sha256
from ..pace_canonical import canonical_pace_json_bytes_v1, pace_digest_v1
from .compiler import compile_pace_v1
from .invariant_fixture import build_invariant_request_v1
from .verifier import verify_certificate_v1


def build_fixture_validation_receipt_v1(
    *,
    compiler_source_sha256: str,
    verifier_source_sha256: str,
) -> dict[str, object]:
    if not is_sha256(compiler_source_sha256) or not is_sha256(
        verifier_source_sha256
    ):
        raise ValueError("fixture validation source identity is invalid")
    request = build_invariant_request_v1()
    first = compile_pace_v1(
        request,
        compiler_source_sha256=compiler_source_sha256,
        verifier_source_sha256=verifier_source_sha256,
    )
    second = compile_pace_v1(
        request,
        compiler_source_sha256=compiler_source_sha256,
        verifier_source_sha256=verifier_source_sha256,
    )
    if first != second or first.certificate is None:
        raise ValueError("PACE fixture replay drifted or emitted no certificate")
    verification = verify_certificate_v1(
        request,
        first.certificate,
        expected_compiler_source_sha256=compiler_source_sha256,
        verifier_source_sha256=verifier_source_sha256,
    )
    if not verification.valid:
        raise ValueError("PACE fixture certificate failed independent verification")
    if first.certificate.action_id != "action.acquire_causation":
        raise ValueError("PACE fixture selected the wrong semantic action")
    payload: dict[str, object] = {
        "contract": "casepath.pace-invariant-validation/1.0.0",
        "fixture_id": "SYNTHETIC-PACE-INVARIANT-001",
        "request_sha256": request.request_sha256,
        "compiler_source_sha256": compiler_source_sha256,
        "verifier_source_sha256": verifier_source_sha256,
        "result_sha256": first.result_sha256,
        "certificate_sha256": first.certificate.certificate_sha256,
        "verification_receipt_sha256": verification.receipt_sha256,
        "checked_world_count": verification.checked_world_count,
        "selected_action_id": first.certificate.action_id,
        "rejected_action_reasons": list(first.rejected_action_reasons),
        "replay_count": 2,
        "replay_byte_identical": True,
        "hidden_oracle_inputs_read": False,
        "activity": {
            "model_calls": 0,
            "provider_calls": 0,
            "credential_reads": 0,
            "may_identities_read": 0,
            "may_contents_read": 0,
            "outcomes_read": 0,
            "spend_usd_micros": 0,
        },
        "status": "PASS",
    }
    return {**payload, "fixture_receipt_sha256": pace_digest_v1(payload)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler-source-sha256", required=True)
    parser.add_argument("--verifier-source-sha256", required=True)
    args = parser.parse_args()
    receipt = build_fixture_validation_receipt_v1(
        compiler_source_sha256=args.compiler_source_sha256,
        verifier_source_sha256=args.verifier_source_sha256,
    )
    sys.stdout.buffer.write(canonical_pace_json_bytes_v1(receipt) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
