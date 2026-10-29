#!/bin/bash
# Downloads weights as a CPU job. Apocrita's usage policy forbids intensive work on the
# login nodes and asks for long transfers to run as jobs, so try this first. It stops
# within a minute if compute nodes can't reach huggingface.co; only then fall back to
# `python scripts/download_models.py` on the login node.
#   sbatch slurm/download.sbatch                   # every enabled model (~650 GB)
#   sbatch --export=ALL,ARGS="--tier core" slurm/download.sbatch
#SBATCH -J survey-download
#SBATCH -o logs/%x.o%j
#SBATCH -p compute
#SBATCH -n 2
#SBATCH --mem-per-cpu=4G
#SBATCH -t 24:0:0

set -euo pipefail
module load "${PYTHON_MODULE:-python}"
source "${VENV:-$HOME/venvs/llm-survey}/bin/activate"
export HF_HOME="${HF_HOME:-/gpfs/scratch/$USER/hf_cache}"
cd "${SLURM_SUBMIT_DIR:-.}"
if ! curl -sSf -m 30 -o /dev/null https://huggingface.co/api/models/openai/gpt-oss-20b; then
  echo "This compute node can't reach huggingface.co; run scripts/download_models.py on the login node instead." >&2
  exit 1
fi
# shellcheck disable=SC2086
python scripts/download_models.py ${ARGS:-}
