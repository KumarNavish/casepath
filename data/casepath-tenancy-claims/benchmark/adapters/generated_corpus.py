"""Leakage-safe adapter for the 150-claim generated development corpus."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

EXPECTED_CORPUS_SHA256 = "08038a328c99659ed82a1f0367f16be9bd543bb49c99cfd1f37185adf00a07a3"
EXPECTED_ROWS = 150
OBSERVABLE_RELATIVE_PATH = Path("complete-package/inference/observable-claim.json")


@dataclass(frozen=True)
class DevelopmentPacket:
    claim_id: str
    language: str
    observable_path: Path
    observable_sha256: str

    def load_observable(self) -> dict[str, Any]:
        payload = json.loads(self.observable_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("observable claim must be a JSON object")
        return cast(dict[str, Any], payload)


class GeneratedCorpusAdapter:
    """Expose only observable packets; evaluator/reference assets never cross this API."""

    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path.resolve()
        self.root = self.manifest_path.parent
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self._validate_manifest()

    def _validate_manifest(self) -> None:
        if self.manifest.get("contract") != "casepath.private-candidate-corpus/1.0.0":
            raise ValueError("unexpected generated-corpus contract")
        if self.manifest.get("corpus_sha256") != EXPECTED_CORPUS_SHA256:
            raise ValueError("generated-corpus digest does not match the published identity")
        entries = self.manifest.get("entries")
        if not isinstance(entries, list) or len(entries) != EXPECTED_ROWS:
            raise ValueError(f"expected exactly {EXPECTED_ROWS} generated entries")
        if self.manifest.get("row_count") != EXPECTED_ROWS:
            raise ValueError("generated-corpus row_count is inconsistent")
        if self.manifest.get("language_counts") != {"de-CH": 75, "en": 75}:
            raise ValueError("generated-corpus language balance changed")
        if self.manifest.get("publication_eligible") is not False:
            raise ValueError("generated corpus must not be represented as publication gold")
        if self.manifest.get("independent_review_status") != "not_performed":
            raise ValueError("adapter assumptions require the dated unreviewed corpus identity")

    def packets(self) -> tuple[DevelopmentPacket, ...]:
        packets: list[DevelopmentPacket] = []
        claim_ids: set[str] = set()
        for entry in self.manifest["entries"]:
            claim_id = entry["claim_id"]
            if claim_id in claim_ids:
                raise ValueError(f"duplicate generated claim_id: {claim_id}")
            claim_ids.add(claim_id)
            path = (self.root / entry["relative_path"] / OBSERVABLE_RELATIVE_PATH).resolve()
            if self.root not in path.parents or not path.is_file():
                raise ValueError(f"missing or escaped observable packet: {claim_id}")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            packets.append(
                DevelopmentPacket(
                    claim_id=claim_id,
                    language=entry["language"],
                    observable_path=path,
                    observable_sha256=digest,
                )
            )
        return tuple(packets)
