#!/bin/bash
# One small array on scicore-fast: tasks 0-9 build the S1 decision tables (15
# claims each), task 10 runs the S2 scalability benchmark. 1 CPU, 1 GB, 10 min.
#SBATCH --job-name=casepath-tmis
#SBATCH --partition=scicore-fast
#SBATCH --qos=30min
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --array=0-10
#SBATCH --output=logs/%x_%A_%a.out
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
export PYTHONDONTWRITEBYTECODE=1
if [ "$SLURM_ARRAY_TASK_ID" -lt 10 ]; then
  python3 research/tmis2026/scicore/s1_tables.py "$SLURM_ARRAY_TASK_ID" 10 out
else
  python3 research/tmis2026/scicore/s2_scalability.py out/s2_scalability.json
fi
