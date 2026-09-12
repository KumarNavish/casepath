#!/usr/bin/env bash
set -euo pipefail

export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1786406400}"
export PYTHONPATH="casepath-api${PYTHONPATH:+:$PYTHONPATH}"

python -m pip install --no-cache-dir -r casepath-api/requirements.lock

# Build all model-visible documents from fixed inputs, then convert the two
# project source images into metadata-free runtime JPEGs. Neither step mutates
# tracked application source.
python casepath-api/generate_artifacts.py
python casepath-api/replace_photographic_evidence.py .

# Bind source, browser gates and artifact bytes to the release contract. The
# verifier also performs the exact construction-marker scan.
python casepath/tools/casepath_release.py generate
python casepath/tools/casepath_release.py verify

casepath_build_tmp="$(mktemp -d /tmp/casepath-build.XXXXXX)"
trap 'rm -rf -- "$casepath_build_tmp"' EXIT

python -m compileall -q casepath-api/casepath_api casepath/tools/casepath_release.py
CASEPATH_MODEL_MODE=deterministic_reference \
CASEPATH_DB_PATH="$casepath_build_tmp/tests.db" \
python -m pytest -q casepath-api/tests casepath/tools/test_*.py

test -f casepath-api/artifacts/lease-agreement.pdf
test -f casepath-api/artifacts/bedroom-corner-2026-07-27.jpg
test -f casepath-api/artifacts/window-corner-2026-08-08.jpg
test -f casepath-api/artifacts/IMAGE_PROVENANCE.json
test -f casepath-api/artifacts/artifact-manifest.json

CASEPATH_MODEL_MODE=deterministic_reference \
CASEPATH_DB_PATH="$casepath_build_tmp/smoke.db" \
python - <<'PY'
import hashlib
import json
from pathlib import Path

from casepath_api.app import app, healthz, readyz
from casepath_api.data import ARTIFACTS, CLAIMS, DEMO_CLAIM

assert app is not None
health = healthz()
readiness = readyz()
assert health["status"] == "ok"
assert health["model_mode"] == "deterministic_reference"
assert readiness["status"] == "ready"
assert readiness["model_budget"]["network_calls"] == 0
assert DEMO_CLAIM["claim_id"] == "DEF-027-E0-DEMO"
assert len(CLAIMS) == 2
assert len(ARTIFACTS) == 12

artifact_root = Path("casepath-api/artifacts")
manifest = json.loads((artifact_root / "artifact-manifest.json").read_text(encoding="utf-8"))
assert manifest["leakage_policy"]["status"] == "passed"
manifest_hashes = {item["path"]: item["sha256"] for item in manifest["files"]}

for artifact in ARTIFACTS.values():
    artifact_path = Path(artifact["path"])
    actual_sha = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    assert artifact["sha256"] == actual_sha
    assert manifest_hashes[artifact_path.name] == actual_sha

print("CasePath deterministic API build smoke passed")
PY
