"""Verify one deployed original JPEG and decode the exact bytes locally."""
if not __debug__:
    raise RuntimeError("Assertions required.")
from pathlib import Path
from io import BytesIO
from datetime import datetime, timezone
import hashlib, json, sys, urllib.parse
import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parent
SOURCE = sys.argv[1]
assert len(sys.argv) == 2 and len(SOURCE) == 40
from require_completed_gate import require_completed_gate
require_completed_gate(BASE, SOURCE)
SITE = "https://casepath-autonomous.kumarnavish.chatgpt.site"
CLAIM = "clm_14970d755f5b88ed"
ARTIFACT = "upl_535854833181406554dce563"
manifest_path = ROOT / "casepath-api/casepath_api/corpora/synthetic-150/manifest.json"
manifest = json.loads(manifest_path.read_text())
claim = next(row for row in manifest["claims"] if row["claim_id"] == CLAIM)
descriptor = next(row for row in claim["observable_artifacts"] if row["artifact_id"] == ARTIFACT)
assert descriptor["sha256"] == "2ab3a31917da3787a4fc3e334b609afe2da52bba7a9bda1d9356b70215ce14c1"
assert descriptor["size_bytes"] == 201417 and descriptor["media_type"] == "image/jpeg"
with httpx.Client(timeout=30, trust_env=False, follow_redirects=False) as client:
    identity = client.get(SITE + "/deployment.json")
    identity.raise_for_status()
    assert identity.json()["source_commit"] == SOURCE
    response = client.get(SITE + "/api/claim-loops/v1/autonomous/sources/" + CLAIM + "/" + ARTIFACT)
    response.raise_for_status()
assert response.status_code == 200
raw = response.content
digest = hashlib.sha256(raw).hexdigest()
assert len(raw) == descriptor["size_bytes"] and digest == descriptor["sha256"]
assert response.headers["content-type"].split(";")[0] == "image/jpeg"
assert "attachment" in response.headers["content-disposition"]
assert descriptor["file_name"] in urllib.parse.unquote(response.headers["content-disposition"])
header_hash = response.headers.get("x-content-sha256")
assert header_hash is None or header_hash == digest
assert Image.__version__ == "13.0.0"
with Image.open(BytesIO(raw)) as image:
    image.load()
    dimensions, mode, decoded_format = list(image.size), image.mode, image.format
assert decoded_format == "JPEG" and all(value > 0 for value in dimensions)
receipt = {
    "source_commit": SOURCE, "passed": True, "observed_at": datetime.now(timezone.utc).isoformat(),
    "site": SITE, "claim_id": CLAIM, "artifact_id": ARTIFACT,
    "http_status": response.status_code, "bytes": len(raw), "sha256": digest,
    "matches_sealed_original": True, "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    "content_type": response.headers["content-type"], "content_disposition": response.headers["content-disposition"],
    "header_sha256": header_hash, "local_pillow": Image.__version__,
    "decoded_format": decoded_format, "dimensions": dimensions, "mode": mode,
    "server_decoder_exercised": False,
    "coverage": "Deployed exact-original delivery and local Pillow13 compatibility. Hosted download serves bytes; it does not invoke Pillow.",
    "methods": ["GET"], "provider_calls": 0,
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
with (BASE / "public-image-verified.json").open("x") as target:
    json.dump(receipt, target, indent=2)
    target.write("\n")
print(json.dumps(receipt), flush=True)

