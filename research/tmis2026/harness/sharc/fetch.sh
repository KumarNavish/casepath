#!/usr/bin/env bash
# Fetch the official ShARC 1.0 archive into a NEW empty directory and verify its SHA-256.
# Only the train split is used by this pilot; the dev split is reserved for a later pre-registered test.
# Usage: harness/sharc/fetch.sh <empty-dir>
set -euo pipefail
DEST=${1:?usage: fetch.sh <empty-dir>}
mkdir -p "$DEST"; [ -z "$(ls -A "$DEST")" ] || { echo "$DEST is not empty" >&2; exit 1; }
curl -sSfL -o "$DEST/sharc.zip" https://sharc-data.github.io/data/sharc1-official.zip
echo "72dca3f4f3ba73b1d796b40e952a80d53cd2011ef90b2168b8bcaa818f5edd1e  $DEST/sharc.zip" | sha256sum -c -
(cd "$DEST" && unzip -q sharc.zip sharc1-official/json/sharc_train.json sharc1-official/README.md)
echo "train split: $DEST/sharc1-official/json/sharc_train.json"
