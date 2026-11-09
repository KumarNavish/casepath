#!/usr/bin/env bash
# Assemble the folder a Databricks App runs from: the package, the workflow catalogue, the synthetic cases (with their
# PDFs already drawn), app.yaml, requirements.txt and the wheels of the PDF libraries.
#
# The workspace's package index may be unreachable from app builds. The two PDF libraries (and, only for a runtime
# that lacks them, Pillow and python-multipart) are therefore downloaded here, checked against PyPI's published
# SHA-256, and installed from the folder with --no-index. Run from the internal copy's root with its venv's python:
#   PYTHON=~/.casepath/venv/bin/python deploy/databricks/package.sh <out-dir>
set -euo pipefail
out="${1:?usage: deploy/databricks/package.sh <out-dir>}"
python="${PYTHON:-python3}"
pip="${PIP:-$python -m pip}"   # any pip can download; the python must run casepath_internal
here="$(cd "$(dirname "$0")/../.." && pwd)"
rm -rf "$out" && mkdir -p "$out"
cp -r "$here/casepath_internal" "$out/"
find "$out" -name __pycache__ -type d -prune -exec rm -rf {} +
cp "$here/deploy/databricks/app.yaml" "$out/"
mkdir -p "$out/check" && cp "$here/deploy/databricks/smoke.py" "$out/check/"   # the model capability check, for a notebook
[ -d "$here/catalogue" ] && cp -r "$here/catalogue" "$out/catalogue" || echo "note: no catalogue/ here (the GitLab copy has it)" >&2
if [ -d "$here/benchmark" ]; then
  for d in "$here"/benchmark/*/; do mkdir -p "$out/benchmark/$(basename "$d")" && cp "$d/case.json" "$out/benchmark/$(basename "$d")/"; done
  (cd "$out" && "$python" -m casepath_internal.benchmark render benchmark)
fi

# The wheels, for the app runtime (Python 3.11 on Linux, x86_64 or arm64), pinned to the versions tested.
PINS="pypdf==5.9.0 pypdfium2==5.14.0 pillow==13.0.0 python-multipart==0.0.20"
mkdir -p "$out/wheels"
for platform in "manylinux_2_28_x86_64 manylinux_2_17_x86_64 manylinux2014_x86_64" "manylinux_2_28_aarch64 manylinux_2_17_aarch64 manylinux2014_aarch64"; do
  flags=(); for p in $platform; do flags+=(--platform "$p"); done
  $pip download --quiet --only-binary=:all: --no-deps --python-version 3.11 --implementation cp "${flags[@]}" -d "$out/wheels" $PINS
done
"$python" - "$out/wheels" <<'PY'
import hashlib, json, pathlib, sys, urllib.request
for wheel in sorted(pathlib.Path(sys.argv[1]).glob("*.whl")):
    name, version = wheel.name.split("-")[:2]
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=60) as response:
        published = {f["filename"]: f["digests"]["sha256"] for f in json.load(response)["urls"]}
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if published.get(wheel.name) != digest:
        sys.exit(f"{wheel.name}: its SHA-256 does not match PyPI's; not packaged")
    print(f"ok  {wheel.name}  {digest[:16]}")
PY
cat > "$out/requirements.txt" <<'REQ'
--no-index
--find-links wheels
fastapi>=0.115
uvicorn>=0.30
httpx>=0.27
pypdf==5.9.0
pypdfium2==5.14.0
pillow>=10.1
python-multipart>=0.0.9
REQ
echo "$out: $(find "$out" -type f | wc -l) files, $(du -sh "$out/wheels" | cut -f1) of wheels"
