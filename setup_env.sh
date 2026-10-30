#!/bin/bash
# One-off environment setup on Apocrita. Run on the login node from the repo root:
#   bash setup_env.sh
# Override with VENV=... HF_HOME=... PYTHON_MODULE=... TORCH_INDEX=... TORCH_SPEC=... bash setup_env.sh
#
# PyTorch: 2.15+ is published only for CUDA 13, which needs NVIDIA driver >= 580. Cluster
# drivers are often older, so by default we install PyTorch 2.14 built for CUDA 12.6 (the
# cu128 index stops at 2.11). If a GPU node's `nvidia-smi` shows driver >= 580 you can use
# the newest wheels instead:
#   TORCH_SPEC="torch torchvision" TORCH_INDEX=https://pypi.org/simple bash setup_env.sh

set -euo pipefail

PYTHON_MODULE="${PYTHON_MODULE:-python}"
VENV="${VENV:-$HOME/venvs/llm-survey}"
HF_HOME="${HF_HOME:-/gpfs/scratch/$USER/hf_cache}"
TORCH_SPEC="${TORCH_SPEC:-torch==2.14.* torchvision}"
TORCH_INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/cu126}"

module load "$PYTHON_MODULE"
python --version

if [ ! -d "$VENV" ]; then
  virtualenv "$VENV" 2>/dev/null || python -m venv "$VENV"
fi
source "$VENV/bin/activate"
pip install --upgrade pip
# torch + torchvision first, from one index, so requirements.txt doesn't swap them for CUDA 13 builds
# shellcheck disable=SC2086
pip install $TORCH_SPEC --index-url "$TORCH_INDEX"
pip install -r requirements.txt

mkdir -p "$HF_HOME" logs outputs
cat <<EOF

Environment ready: $VENV
Next:
  export HF_HOME=$HF_HOME
  hf auth login                     # needed for gated repos (Gemma 3, Llama 3.1)
  python scripts/download_models.py --tier core
  sbatch slurm/check_env.sbatch     # confirm the GPU and bf16 work
  python scripts/submit.py --smoke --models <key>   # 1-hour load-and-answer test
EOF
