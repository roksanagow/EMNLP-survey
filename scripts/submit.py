#!/usr/bin/env python
"""Submit one Slurm job per model, sized from config/models.yaml and config/cluster.yaml.

  python scripts/submit.py --dry-run                       # print the sbatch commands
  python scripts/submit.py                                 # all enabled models, A100s, partition gpu
  python scripts/submit.py --gpu-type h100 --partition sae
  python scripts/submit.py --smoke                         # 1-hour gpushort check of every model
  python scripts/submit.py --models gpt-oss-20b --conditions independent
"""
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from llm_survey.config import REPO_ROOT, expand, load_cluster, load_models  # noqa: E402


def build_command(spec, args, cluster) -> tuple[list[str], dict[str, str]]:
    part = cluster["partitions"][args.partition]
    gtype = cluster["gpu_types"][args.gpu_type]
    n_gpu = int(spec.gpus[args.gpu_type])
    cpg = int(part["cpus_per_gpu"])
    time = part.get("fixed_time") or args.time or spec.time
    run_name = "smoke" if args.smoke else args.run_name
    extra = []
    if args.smoke:
        extra.append("--smoke")
    if args.conditions:
        extra += ["--conditions", *args.conditions]
    if args.max_new_tokens:
        extra += ["--max-new-tokens", str(args.max_new_tokens)]
    if args.overwrite:
        extra.append("--overwrite")
    defaults = cluster.get("defaults", {})
    env = {
        "MODEL_KEY": spec.key,
        "RUN_NAME": run_name,
        "EXTRA_ARGS": " ".join(extra),
        "VENV": expand(args.venv or defaults.get("venv", "$HOME/venvs/llm-survey")),
        "HF_HOME": expand(args.hf_home or defaults.get("hf_home", "/gpfs/scratch/$USER/hf_cache")),
        "PYTHON_MODULE": defaults.get("python_module", "python"),
    }
    cmd = [
        "sbatch",
        "-J", f"survey-{spec.key}",
        "-o", str(REPO_ROOT / "logs" / "%x.o%j"),
        "-p", args.partition,
        "-N", "1",              # device_map="auto" splits a model across the GPUs of one node only
        "--gres", f"gpu:{n_gpu}",
        "-n", str(n_gpu * cpg),
        "--cpus-per-gpu", str(cpg),
        "--mem-per-cpu", str(part["mem_per_cpu"]),
        "-t", time,
    ]
    if gtype.get("constraint") and part.get("use_constraint", True):
        cmd += ["--constraint", gtype["constraint"]]
    bad = [k for k, v in env.items() if "," in v]
    if bad:
        raise ValueError(f"values for {bad} contain commas, which sbatch --export cannot carry")
    cmd += ["--export", "ALL," + ",".join(f"{k}={v}" for k, v in env.items()),
            str(REPO_ROOT / "slurm" / "run_model.sbatch")]
    return cmd, env


def main(argv=None) -> int:
    cluster = load_cluster()
    d = cluster.get("defaults", {})
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--models", nargs="*", help="model keys (default: all enabled)")
    p.add_argument("--tier", choices=["core", "optional"])
    p.add_argument("--gpu-type", choices=list(cluster["gpu_types"]), default=d.get("gpu_type", "a100"))
    p.add_argument("--partition", choices=list(cluster["partitions"]), default=d.get("partition", "gpu"))
    p.add_argument("--time", default=None, help="walltime override, e.g. 24:0:0")
    p.add_argument("--run-name", default="main")
    p.add_argument("--conditions", nargs="+", choices=["sequential", "independent"])
    p.add_argument("--max-new-tokens", type=int)
    p.add_argument("--smoke", action="store_true", help="Q1 only, 64 tokens, on gpushort for 1 hour")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--venv")
    p.add_argument("--hf-home")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    if args.smoke:
        args.partition = "gpushort"

    specs = load_models()
    keys = args.models or [k for k, s in specs.items() if s.enabled and args.tier in (None, s.tier)]
    unknown = [k for k in keys if k not in specs]
    if unknown:
        p.error(f"unknown model keys: {unknown}")
    (REPO_ROOT / "logs").mkdir(exist_ok=True)

    for key in keys:
        spec = specs[key]
        try:
            cmd, _ = build_command(spec, args, cluster)
        except ValueError as e:
            p.error(str(e))
        print(" ".join(shlex.quote(c) for c in cmd))
        if not args.dry_run:
            # run_model.sbatch cds to $SLURM_SUBMIT_DIR, so submit from the repo root wherever we were called from
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
            print("   ", (res.stdout or res.stderr).strip())
            if res.returncode != 0:
                return res.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
