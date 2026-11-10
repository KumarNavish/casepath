#!/usr/bin/env bash
# Study 2 confirmatory run (ANALYSIS_PLAN_STUDY2.md). DO NOT START before the plan is committed: run.py and
# evolve.py refuse --data fresh otherwise. Each model runs in its own processes with its own cap: the model's
# v2 spend at launch plus its allowance (gpt-6-luna USD 2.50, gpt-6.1-terra USD 7.00). Provider errors are
# retried with back-off and never kept as answers (common.py); run.py is resumable (completed keys are skipped,
# provider failures are retried), so the script can simply be started again after an interruption.
set -euo pipefail
cd "$(dirname "$0")"

cap() {  # current v2 spend of model $1 plus allowance $2
  python3 - "$1" "$2" <<'PY'
import json, sys
from pathlib import Path
p = Path(".").resolve().parents[1] / "runs" / "v2" / f"ledger_{sys.argv[1]}.jsonl"
spent = sum(float(json.loads(l).get("cost") or 0) for l in p.read_text().splitlines()) if p.exists() else 0.0
print(f"{spent + float(sys.argv[2]):.4f}")
PY
}

LUNA_CAP=$(cap gpt-6-luna 2.50)
TERRA_CAP=$(cap gpt-6.1-terra 7.00)
echo "caps: gpt-6-luna ${LUNA_CAP} USD, gpt-6.1-terra ${TERRA_CAP} USD"

luna()  { TMIS_MODEL=openai/gpt-6-luna    TMIS_BUDGET_USD="$LUNA_CAP"  "$@"; }
terra() { TMIS_MODEL=openai/gpt-6.1-terra TMIS_BUDGET_USD="$TERRA_CAP" "$@"; }

# 1. gpt-6-luna
luna python3 run.py tenancy --data fresh --split heldout --k 3 --designs CPv2p,B1v2p,CPv1 --workers 8
luna python3 run.py theft   --data fresh --split heldout --k 3 --designs CPv2p,Rv2p,R,CPv1 --workers 8
luna python3 evolve.py theft --data fresh --train-stories 4 --eval-stories 5,6,7 --eval-runs 0,1,2
luna python3 ablate.py --data fresh --model gpt-6-luna --split heldout

# 2. gpt-6.1-terra
terra python3 run.py tenancy --data fresh --split heldout --k 3 --designs CPv2p,B1v2p --workers 6
terra python3 run.py theft   --data fresh --split heldout --k 3 --designs CPv2p,Rv2p,R --workers 6
echo "done"
