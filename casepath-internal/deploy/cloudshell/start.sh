#!/usr/bin/env bash
# Run CasePath inside an Azure Cloud Shell session (ephemeral, no storage account).
#
#   bash deploy/cloudshell/start.sh <resource-endpoint> <deployment-name> [port]
#
# The endpoint and deployment are given on the command line, so they never live in code.
# Sign-in uses the Cloud Shell identity of the person running it. Open the app with
# Cloud Shell's "Web preview" on the port printed at the end. Everything, including
# uploaded case files, disappears when the Cloud Shell session ends.
set -euo pipefail

endpoint="${1:?resource endpoint, e.g. https://<resource>.openai.azure.com}"
deployment="${2:?exact deployment name}"
port="${3:-8080}"
here="$(cd "$(dirname "$0")/../.." && pwd)"
home="$HOME/.casepath"
mkdir -p "$home/data" "$home/catalogue"

python3 -m venv "$home/venv"
"$home/venv/bin/pip" install --quiet --upgrade pip
"$home/venv/bin/pip" install --quiet -e "$here[azure]"
"$home/venv/bin/python" -m unittest discover -s "$here/tests" -t "$here" 2>&1 | tail -1

[ -d "$here/catalogue" ] && cp -n "$here"/catalogue/*.json "$home/catalogue/" 2>/dev/null || true
cat > "$home/env" <<EOF
CASEPATH_DEV_USER=${USER:-cloudshell}
CASEPATH_DATA_DIR=$home/data
CASEPATH_WORKFLOW_CATALOGUE=$home/catalogue
CASEPATH_AZURE_OPENAI_ENDPOINT=$endpoint
CASEPATH_AZURE_OPENAI_DEPLOYMENT=$deployment
CASEPATH_MODEL_REASONING=true
EOF
"$home/venv/bin/python" -m casepath_internal check-catalogue "$home/catalogue" || true

if [ "${CASEPATH_CHECK_MODEL:-0}" = "1" ]; then
  (set -a; . "$home/env"; set +a; "$home/venv/bin/python" "$here/deploy/workspace/check_model.py")
fi

(set -a; . "$home/env"; set +a; cd "$here"; nohup "$home/venv/bin/python" -m casepath_internal serve --host 127.0.0.1 --port "$port" > "$home/casepath.log" 2>&1 &)
sleep 3
curl -s "http://127.0.0.1:$port/api/health" && echo
echo "CasePath is running. Open it with Web preview → Configure → port $port."
