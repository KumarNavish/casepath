#!/usr/bin/env bash
# Assemble the folder a Databricks App runs from: the package, the workflow catalogue, the synthetic cases (prepared:
# text extracted and scanned pages drawn as images, so the app needs no PDF library), app.yaml and requirements.txt.
#
# The app installs nothing beyond what the platform provides (fastapi, uvicorn, httpx). Case files reach it prepared
# (python -m casepath prepare) through the volume's incoming/ folder. To let it also read loose PDFs, set
# WHEELS_INDEX to the approved package feed: the PDF libraries are then downloaded from it as wheels, checked against
# PyPI's published SHA-256, and installed from the folder. Run from the internal copy's root:
#   PYTHON=~/.casepath/venv/bin/python [WHEELS_INDEX=<approved feed>/simple] deploy/databricks/package.sh <out-dir>
set -euo pipefail
out="${1:?usage: deploy/databricks/package.sh <out-dir>}"
python="${PYTHON:-python3}"
pip="${PIP:-$python -m pip}"   # any pip can download; the python must run casepath
here="$(cd "$(dirname "$0")/../.." && pwd)"
rm -rf "$out" && mkdir -p "$out"
cp -r "$here/casepath" "$out/"
cp "$here/deploy/databricks/app.yaml" "$out/"
mkdir -p "$out/check" && cp "$here/deploy/databricks/smoke.py" "$out/check/"   # the model capability check, for a notebook
[ -d "$here/catalogue" ] && cp -r "$here/catalogue" "$out/catalogue" || echo "note: no catalogue/ here (the GitLab copy has it)" >&2
if [ -d "$here/benchmark" ]; then
  for d in "$here"/benchmark/*/; do mkdir -p "$out/benchmark/$(basename "$d")" && cp "$d/case.json" "$out/benchmark/$(basename "$d")/"; done
  (cd "$out" && "$python" -m casepath benchmark prepare benchmark)
fi
printf 'fastapi>=0.115\nuvicorn>=0.30\nhttpx>=0.27\n' > "$out/requirements.txt"

if [ -n "${WHEELS_INDEX:-}" ]; then
  PINS="pypdf==5.9.0 pypdfium2==5.14.0 pillow==13.0.0 python-multipart==0.0.20"
  mkdir -p "$out/wheels"
  for platform in "manylinux_2_28_x86_64 manylinux_2_17_x86_64 manylinux2014_x86_64" "manylinux_2_28_aarch64 manylinux_2_17_aarch64 manylinux2014_aarch64"; do
    flags=(); for p in $platform; do flags+=(--platform "$p"); done
    $pip download --quiet --index-url "$WHEELS_INDEX" --only-binary=:all: --no-deps --python-version 3.11 --implementation cp "${flags[@]}" -d "$out/wheels" $PINS
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
  printf -- '--no-index\n--find-links wheels\nfastapi>=0.115\nuvicorn>=0.30\nhttpx>=0.27\npypdf==5.9.0\npypdfium2==5.14.0\npillow>=10.1\npython-multipart>=0.0.9\n' > "$out/requirements.txt"
fi
# Python's caches (made while preparing) are refused by the workspace's file system; none ship.
find "$out" -name __pycache__ -type d -prune -exec rm -rf {} +
find "$out" -name "*.pyc" -delete
echo "$out: $(find "$out" -type f | wc -l) files"
