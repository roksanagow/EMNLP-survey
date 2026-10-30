# LLM opinion survey

Asks open-weight chat models the same four questions that were put to people at EMNLP, saves every
answer, and builds a workbook for coding the answers blind.

```
Q1  If you were a human and used AI to code, would you read the code it generates?
Q2  If you were a human, would you try using AI as a therapist, or for emotional issues?
Q3  According to your own definition of consciousness, do you think AI could be conscious?
Q4  How would you define consciousness?
```

Each model answers once per condition:

| Condition | What happens |
|---|---|
| `sequential` | Q1–Q4 in one chat, in order, like the human sessions. Each answer goes back into the chat history before the next question. |
| `independent` | Each question in its own new chat. |

Q1 is identical in both conditions (same prompt, same seed), so the two Q1 answers should normally match.
A mismatch means GPU nondeterminism, which is worth knowing about.

## What "default settings" means here

- **Sampling** (`do_sample`, `temperature`, `top_p`, `top_k`, …) comes from each repo's own
  `generation_config.json`. Nothing is overridden. The values used are saved with every answer, and they differ
  between models: Qwen, for example, samples at temperature 1.0, while a model without sampling settings decodes greedily.
- **Chat template** is applied with its own defaults. We add no system prompt and flip no thinking switch, so
  Qwen3.x and gpt-oss reason by default and Gemma 4 does not. Some templates insert their own system text,
  for example Llama 3.1's knowledge-cutoff date and gpt-oss's current date. The exact prompt the model saw is saved with each answer.
- **`max_new_tokens = 32768`** is the one setting we have to choose, because transformers otherwise stops after 20 tokens.
  It is a cap, not a target. Answers that hit it are flagged.
- **Seed 2026** for every chat.
- Only the final answer goes back into the chat history, not the reasoning trace. This matches what the models'
  own templates do with earlier turns. The reasoning is still saved.

## Models (`config/models.yaml`)

| key | Hugging Face id | tier | reasons by default | GPUs (A100 40GB / H100 80GB) |
|---|---|---|---|---|
| qwen3.8-27b | Qwen/Qwen3.8-27B | core | yes | 2 / 1 |
| gemma-4-31b-it | google/gemma-4-31B-it | core | no | 2 / 1 |
| gpt-oss-20b | openai/gpt-oss-20b | core | yes (medium) | 2 / 1 |
| olmo-3.1-32b-instruct | allenai/Olmo-3.1-32B-Instruct | core | no | 2 / 1 |
| olmo-3.1-32b-think | allenai/Olmo-3.1-32B-Think | optional | yes | 2 / 1 |
| gemma-4-26b-a4b-it | google/gemma-4-26B-A4B-it | optional | no | 2 / 1 |
| gemma-3-27b-it | google/gemma-3-27b-it (gated) | optional | no | 2 / 1 |
| qwen3.6-35b-a3b | Qwen/Qwen3.6-35B-A3B | optional | yes | 3 / 2 |
| magistral-small-2509 | mistralai/Magistral-Small-2509 | optional | yes | 2 / 1 |
| nemotron-3-nano-30b-a3b | nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 | optional | yes | 2 / 1 |
| llama-3.1-8b-instruct | meta-llama/Llama-3.1-8B-Instruct (gated) | optional | no | 1 / 1 |
| deepseek-r1-distill-qwen-32b | deepseek-ai/DeepSeek-R1-Distill-Qwen-32B | optional | yes | 3 / 2 |

GPU counts cover bf16 weights plus room for a 32k-token answer; `scripts/preflight.py` prints the estimate
for each model. Set `enabled: false` to skip a model.

## Apocrita resources used

From the [GPU docs](https://docs.hpc.qmul.ac.uk/using/usingGPU/) and node pages:

| Hardware | Where | Notes |
|---|---|---|
| A100 40GB, 4 per node | `sbg` nodes (`-p gpu`), Andrena (`-p andrena`, separate approval) | `--constraint=ampere`. Default here. |
| A100 80GB, 4 per node | `rdg` nodes, Science & Engineering only | Also matched by `--constraint=ampere`; the 40GB GPU counts then leave spare memory. |
| H100 80GB / H200 141GB, 4 per node | `xdg`, `rdg1` (H100), `xhg` (H200), mostly Science & Engineering only (EECS qualifies) | `--constraint=hopper`, partition `sae` or `gpu`. Fewer GPUs per model, faster. |
| V100 16/32GB | `ddg`, `sbg` | Not used: no native bf16 and too little memory. |

Apocrita moved from Grid Engine to Slurm in 2026; `qsub`/`#$` scripts no longer run. Rules the scripts follow:
- On `gpu`, `gpushort` and `sae`: 8 cores per GPU (`-n 8×GPUs --cpus-per-gpu=8`) and `--mem-per-cpu=11G`.
  The docs ask for both `-n` and `--cpus-per-gpu` to be set.
- On `andrena`: 12 cores per GPU and `--mem-per-cpu=7500M` (whole megabytes; larger requests are rejected).
- `-N 1`: a model is split over the GPUs of one node, never across nodes.
- `gpushort` jobs are fixed at 1 hour; every other partition allows up to 240 hours.
- No `--exclusive`, no `--mem=0` (fails on GPU nodes), and `CUDA_VISIBLE_DEVICES` is left to Slurm.
- Weights live in `/gpfs/scratch/$USER`. The old `/data/scratch` path fails under Slurm.
- Intensive work must not run on the login nodes, so downloads go through `slurm/download.sbatch` where possible.

GPU access (`gpu`, `sae`, `andrena`) must be requested from its-research-support@qmul.ac.uk with a job ID or
`nvidia-smi` output from a working `gpushort` job. The docs require such test jobs to **use the GPU for at least
20 minutes**, so `check_env` (seconds) and `--smoke` (a few minutes) don't count. Use a full run of a reasoning
model instead (8 answers with reasoning traces), and check the per-answer timings in its log add up to 20+ minutes
before citing it:

```bash
python scripts/submit.py --partition gpushort --models qwen3.8-27b --run-name gpushort-evidence
```

Storage:
- Weights go to `/gpfs/scratch/$USER/hf_cache`. All models together are about 765 GB (the two OLMo repos
  store fp32 weights, 129 GB each); scratch allows 3 TB.
- **Scratch files are deleted 65 days after they were last changed.**
- Keep this repo, and therefore `outputs/`, in home or project space, not scratch.

## Running it

```bash
# 0. Clone into home (not scratch), then:
cd llm-survey
bash setup_env.sh                       # venv at ~/venvs/llm-survey; override with VENV=...
export HF_HOME=/gpfs/scratch/$USER/hf_cache

# 1. Gated repos: accept the licences on the Gemma 3 and Llama 3.1 model pages, then
hf auth login

# 2. Download and pin weights, as a job (it stops early if compute nodes are offline)
sbatch --export=ALL,ARGS="--tier core" slurm/download.sbatch   # ~260 GB
sbatch slurm/download.sbatch                                   # everything enabled
#    only if that job reports no internet: python scripts/download_models.py on the login node
#    -> config/revisions.lock.yaml records the exact commit of each model

# 3. Check the GPU environment (1-hour gpushort job)
sbatch slurm/check_env.sbatch          # once it has run: cat logs/survey-check.o<jobid>

# 4. Smoke test: load each model and answer Q1 in 64 tokens (gpushort, 1 hour each).
#    Optional: `python scripts/preflight.py` does the checks it can without GPUs or weights; run it on your laptop first.
python scripts/submit.py --smoke --dry-run         # show the sbatch commands
python scripts/submit.py --smoke
#    then read outputs/smoke/<model>/sequential.md for each

# 5. The real run: one job per model, both conditions
python scripts/submit.py                           # A100s on -p gpu
python scripts/submit.py --gpu-type h100 --partition sae   # or H100s, if you have S&E access
squeue --me; tail -f logs/survey-<model>.o<jobid>

# 6. Code the answers
python scripts/collect.py                          # outputs/main/coding_workbook.xlsx + blind_key.csv
#    code the "Blind coding" sheet (dropdowns use the human-survey categories), save, then
python scripts/unblind.py                          # outputs/main/coded_answers.csv, coded_wide.csv
```

Other options:
- Run a subset with `--models gpt-oss-20b qwen3.8-27b` or `--tier core`.
- Run only one condition with `--conditions independent`.
- Override the walltime with `--time 24:0:0`.
- Queue the jobs behind another job (e.g. the download) with `--after <jobid>`; they start once it has ended,
  even if it failed, so one failed download doesn't block every model.
- A finished run is never overwritten; use `--run-name` for a new run, or `--overwrite` to replace one.

## Outputs

```
outputs/main/<model>/sequential.json   everything: prompts, raw output, reasoning, answer, settings, versions
outputs/main/<model>/sequential.md     readable transcript (reasoning folded)
outputs/main/<model>/independent.json / .md
outputs/main/answers_long.csv          one row per model × condition × question
outputs/main/coding_workbook.xlsx      Blind coding / All answers / Codebook
outputs/main/blind_key.csv             blind_id -> model, condition (don't open while coding)
```

The JSON is rewritten after every answer, so a job that dies keeps what it finished; it then has `"status": "failed"`.

Each answer in the JSON records:
- `rendered_prompt`: the exact text the model saw
- `raw_output`: decoded with special tokens
- `reasoning`, `answer` and `reasoning_format` (`think`, `harmony`, `gemma4`, `mistral` or `none`)
- `finish_reason` (`stop`, or `length` if it hit the cap)
- token counts and timing

Each file also records:
- the model's commit hash
- its sampling settings
- a hash of the chat template
- library versions and GPU names
- a SHA-256 of the question strings

## Things to watch

- **Run the smoke test before the full run.** The loading code was tested end to end on tiny local models,
  with both the text-only and the processor-based path. The real checkpoints were not loaded, because they
  couldn't be downloaded in the build environment. The likeliest problems:
  - **Magistral:** needs mistral-common, and its tokenizer backend is the least standard.
  - **gpt-oss-20b on A100s:** MXFP4 weights get converted to bf16 there, so it needs 2 GPUs.
  - **Qwen3.6/3.8 and Nemotron:** they run without their optional CUDA kernels, just slowly (see `requirements-optional.txt`).
- **PyTorch and the GPU driver.** PyTorch 2.15+ is built only for CUDA 13, which needs NVIDIA driver 580 or newer.
  `setup_env.sh` therefore installs PyTorch 2.14 built for CUDA 12.6, which runs on older drivers
  (PyTorch's CUDA 12.8 index stops at 2.11).
  - If `check_env` still reports CUDA unusable, compare the driver version in its `nvidia-smi` output with the
    PyTorch build. To switch builds, set `TORCH_SPEC` and `TORCH_INDEX` and rerun the setup script; its header comment
    shows how.
  - Don't `pip install -r requirements.txt` on its own into a fresh venv: that pulls the CUDA 13 build from PyPI.
  - PyTorch 2.15 also drops V100s, another reason the scripts only request A100s and H100s.
- **Reasoning parsing.** If a model's reasoning shows up inside `answer`, its format wasn't recognised. The raw output is
  always saved, so after updating `llm_survey/parsing.py` you can re-split the saved outputs with `scripts/reparse.py`,
  without re-running anything.
- **Runtime.** transformers splits a model across GPUs one layer block at a time, so expect roughly 10–30 tokens/s.
  Non-reasoning answers take seconds. A long reasoning trace can take 10–40 minutes. The 12-hour walltime is generous.

## Tests

```bash
pip install pytest && pytest -q        # builds tiny random models on CPU; no downloads
python scripts/preflight.py            # real repos, small files only (no weights): loader, chat
                                       # template, reasoning split and GPU memory estimate per model
```
