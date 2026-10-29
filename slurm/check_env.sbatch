#!/bin/bash
# First job to run: confirms PyTorch sees the GPU, bf16 works, and the libraries import.
#   sbatch slurm/check_env.sbatch
#SBATCH -J survey-check
#SBATCH -o logs/%x.o%j
#SBATCH -p gpushort
#SBATCH -t 1:0:0
#SBATCH -N 1
#SBATCH --gres=gpu:1
#SBATCH -n 8
#SBATCH --cpus-per-gpu=8
#SBATCH --mem-per-cpu=11G
#SBATCH --constraint=ampere

set -euo pipefail
module load "${PYTHON_MODULE:-python}"
source "${VENV:-$HOME/venvs/llm-survey}/bin/activate"
export HF_HOME="${HF_HOME:-/gpfs/scratch/$USER/hf_cache}"
cd "${SLURM_SUBMIT_DIR:-.}"
nvidia-smi
python scripts/check_env.py
