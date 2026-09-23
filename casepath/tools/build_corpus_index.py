#!/usr/bin/env python3
"""Build a read-only browser index from the frozen observable intake packets."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "casepath-api/casepath_api/corpora/synthetic-150"
OUTPUT = ROOT / "casepath/assets/corpus-index.json"


def build() -> bytes:
    manifest_bytes = (CORPUS / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("contains_expected_outputs") is not False or manifest.get("contains_sealed_targets") is not False:
        raise ValueError("the browser index requires an input-only corpus")

    rows = []
    for binding in manifest["claims"]:
        path = CORPUS / binding["claim"]["path"]
        claim_bytes = path.read_bytes()
        if hashlib.sha256(claim_bytes).hexdigest() != binding["claim"]["sha256"]:
            raise ValueError(f"claim binding changed: {binding['claim_id']}")
        claim = json.loads(claim_bytes)
        if claim["submission"]["claim_id"] != binding["claim_id"]:
            raise ValueError(f"claim identity mismatch: {binding['claim_id']}")
        message = claim["customer_message"]
        rows.append({
            "claim_id": binding["claim_id"],
            "binding_sha256": binding["binding_sha256"],
            "subject": message["subject"],
            "message": message["body"],
            "language": binding["language"],
            "received_at": binding["received_at"],
            "attachments": [
                {"name": item["file_name"], "media_type": item["media_type"], "size_bytes": item["size_bytes"]}
                for item in claim["attachments"]
            ],
        })

    if len(rows) != 150 or len({row["claim_id"] for row in rows}) != 150:
        raise ValueError("the browser index must contain the complete 150-claim roster")
    if sum(len(row["attachments"]) for row in rows) != 57:
        raise ValueError("the observable attachment count changed")
    if Counter(row["language"] for row in rows) != {"en": 75, "de-CH": 75}:
        raise ValueError("the observable language counts changed")
    if Counter(file["media_type"] for row in rows for file in row["attachments"]) != {"application/pdf": 47, "image/jpeg": 10}:
        raise ValueError("the observable attachment types changed")
    payload = {
        "contract": "casepath.observable-corpus-index/1.0.0",
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "contains_reference_labels": False,
        "claims": rows,
    }
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the committed index without writing it")
    args = parser.parse_args()
    expected = build()
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != expected:
            raise SystemExit("corpus index is missing or differs from the frozen intake packets")
        print("corpus index matches all 150 input packets")
    else:
        OUTPUT.write_bytes(expected)
        print(f"wrote {OUTPUT} ({len(expected)} bytes)")


if __name__ == "__main__":
    main()
