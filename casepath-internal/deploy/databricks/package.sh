#!/usr/bin/env bash
# Assemble the folder a Databricks App runs from: the package, the workflow catalogue, the synthetic cases, app.yaml
# and requirements.txt. Run from the repository root of the internal copy; the result goes to <out-dir>.
set -euo pipefail
out="${1:?usage: deploy/databricks/package.sh <out-dir>}"
here="$(cd "$(dirname "$0")/../.." && pwd)"
rm -rf "$out" && mkdir -p "$out"
cp -r "$here/casepath_internal" "$out/"
find "$out" -name __pycache__ -type d -prune -exec rm -rf {} +
cp "$here/deploy/databricks/app.yaml" "$here/deploy/databricks/requirements.txt" "$out/"
mkdir -p "$out/check" && cp "$here/deploy/databricks/smoke.py" "$out/check/"   # the model capability check, for a notebook
[ -d "$here/catalogue" ] && cp -r "$here/catalogue" "$out/catalogue" || echo "note: no catalogue/ here (the GitLab copy has it)" >&2
if [ -d "$here/benchmark" ]; then
  for d in "$here"/benchmark/*/; do mkdir -p "$out/benchmark/$(basename "$d")" && cp "$d/case.json" "$out/benchmark/$(basename "$d")/"; done
fi
echo "$out: $(find "$out" -type f | wc -l) files"
