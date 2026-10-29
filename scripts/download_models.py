#!/usr/bin/env python
"""Download model weights into $HF_HOME and pin the exact commit of each.

Run where there is internet access (the login node, or a CPU job if compute nodes
can reach the Hub). Writes config/revisions.lock.yaml; later runs load exactly
those commits with HF_HUB_OFFLINE=1.

  python scripts/download_models.py                 # every enabled model
  python scripts/download_models.py --models gpt-oss-20b qwen3.8-27b
  python scripts/download_models.py --tier core
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from llm_survey.config import LOCK_FILE, load_models, load_yaml  # noqa: E402

# Skip duplicate/irrelevant weight formats (e.g. Llama's original/*.pth, gpt-oss metal/ and original/).
IGNORE = ["original/*", "metal/*", "*.gguf", "*.pth", "consolidated*.safetensors"]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--models", nargs="*", help="model keys (default: all enabled)")
    p.add_argument("--tier", choices=["core", "optional"])
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    specs = load_models()
    keys = args.models or [k for k, s in specs.items() if s.enabled and (args.tier in (None, s.tier))]
    lock = load_yaml(LOCK_FILE) if LOCK_FILE.exists() else {}
    failures = []
    for key in keys:
        spec = specs[key]
        print(f"== {key}: {spec.hf_id} (revision={spec.revision or 'latest'})", flush=True)
        if args.dry_run:
            continue
        from huggingface_hub import snapshot_download

        try:
            path = snapshot_download(spec.hf_id, revision=spec.revision, ignore_patterns=IGNORE)
            sha = Path(path).name
            lock[key] = sha
            LOCK_FILE.write_text(yaml.safe_dump(lock, sort_keys=True))
            print(f"   -> {path}", flush=True)
        except Exception as e:  # keep going; report at the end
            failures.append((key, repr(e)))
            print(f"   !! failed: {e!r}", flush=True)
    if args.dry_run:
        return 0
    if failures:
        print("\nFailed downloads (gated repos need `hf auth login` and accepting the licence on the model page):")
        for k, e in failures:
            print(f"  {k}: {e}")
        return 1
    print(f"\nPinned revisions written to {LOCK_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
