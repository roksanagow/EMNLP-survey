#!/bin/bash
# Runs the survey for one model. Normally submitted by scripts/submit.py, which sets
# the partition, GPUs, cores, memory and walltime per model and exports:
#   MODEL_KEY, RUN_NAME, EXTRA_ARGS, VENV, HF_HOME, PYTHON_MODULE
#
# To submit by hand (1 A100, 8 cores per GPU as Apocrita requires):
#   sbatch -p gpu -N 1 --gres=gpu:1 -n 8 --cpus-per-gpu=8 --mem-per-cpu=11G -t 12:0:0 \
#          --constraint=ampere --export=ALL,MODEL_KEY=llama-3.1-8b-instruct slurm/run_model.sbatch
#SBATCH -J survey
#SBATCH -o logs/%x.o%j

set -euo pipefail

: "${MODEL_KEY:?set MODEL_KEY}"
RUN_NAME="${RUN_NAME:-main}"
EXTRA_ARGS="${EXTRA_ARGS:-}"
VENV="${VENV:-$HOME/venvs/llm-survey}"
export HF_HOME="${HF_HOME:-/gpfs/scratch/$USER/hf_cache}"
export HF_HUB_OFFLINE=1            # weights must already be downloaded (scripts/download_models.py)
export TOKENIZERS_PARALLELISM=false
export PYTHONUNBUFFERED=1

module load "${PYTHON_MODULE:-python}"
unset PYTHONPATH                   # use only the venv's packages, not the python module's (see setup_env.sh)
source "$VENV/bin/activate"
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/..}"

echo "job $SLURM_JOB_ID on $(hostname) | model=$MODEL_KEY run=$RUN_NAME extra='$EXTRA_ARGS'"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv

# shellcheck disable=SC2086
python scripts/run_model.py --model "$MODEL_KEY" --run-name "$RUN_NAME" $EXTRA_ARGS
