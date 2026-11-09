#!/usr/bin/env bash
# Local rendering launcher: synthetic catalogue + data, model = OpenRouter gpt-6-luna via the container proxy.
set -euo pipefail
S=/tmp/claude-0/-home-user-casepath/ef865128-25b1-5a5b-af7f-a334bf6c5b16/scratchpad/ui
cd /home/user/work/casepath-ui2/casepath-internal
export CASEPATH_DATA_DIR=$S/r2/data CASEPATH_WORKFLOW_CATALOGUE=$S/r2/catalogue CASEPATH_DEV_USER="Case handler (demo)"
export CASEPATH_MODEL_PROVIDER=databricks CASEPATH_MODEL_ENDPOINT=https://openrouter.ai CASEPATH_MODEL=gpt-6-luna
export CASEPATH_MODEL_GATEWAY_HOSTS=openrouter.ai CASEPATH_CHAT_PATH=/api/v1/chat/completions CASEPATH_MODEL_API=chat
export CASEPATH_CA_BUNDLE=/root/.ccr/ca-bundle.crt CASEPATH_MODEL_MAX_OUTPUT_TOKENS=8000
export DATABRICKS_TOKEN=proxy-injected
exec $S/venv/bin/python -m casepath_internal serve --host 127.0.0.1 --port 8765
