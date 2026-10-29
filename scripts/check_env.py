#!/usr/bin/env python
"""Print what the job can see: GPUs, CUDA, bf16 support, library versions, cached models."""
import importlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def version(mod):
    try:
        return importlib.import_module(mod).__version__
    except Exception as e:  # noqa: BLE001
        return f"missing ({type(e).__name__})"


def main() -> int:
    import torch

    print("python      ", sys.version.split()[0])
    for m in ["torch", "transformers", "accelerate", "huggingface_hub", "mistral_common", "torchvision", "kernels"]:
        print(f"{m:12s}", version(m))
    print("CUDA build  ", torch.version.cuda)
    print("CUDA usable ", torch.cuda.is_available())
    ok = torch.cuda.is_available()
    for i in range(torch.cuda.device_count()):
        prop = torch.cuda.get_device_properties(i)
        print(f"GPU {i}: {prop.name}, {prop.total_memory / 2**30:.1f} GiB, sm_{prop.major}{prop.minor}")
    if ok:
        x = torch.randn(256, 256, device="cuda", dtype=torch.bfloat16)
        print("bf16 matmul ", float((x @ x).float().abs().mean()) > 0, "| native bf16:", torch.cuda.is_bf16_supported())
    print("HF_HOME     ", os.environ.get("HF_HOME"))
    try:
        from huggingface_hub import scan_cache_dir

        info = scan_cache_dir()
        for repo in sorted(info.repos, key=lambda r: r.repo_id):
            print(f"  cached: {repo.repo_id:50s} {repo.size_on_disk / 1e9:6.1f} GB")
    except Exception as e:  # noqa: BLE001
        print("  (no HF cache yet)", type(e).__name__)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
