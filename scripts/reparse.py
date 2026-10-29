#!/usr/bin/env python
"""Re-split saved raw outputs into reasoning and answer with the current llm_survey/parsing.py.

Use this if a model's reasoning format was misread (e.g. its reasoning appears inside
`answer`). Nothing is re-generated. In the sequential condition the model already saw
whatever answer was fed back at the time; that is recorded in `messages` and is not changed.

  python scripts/reparse.py --models magistral-small-2509        # show what would change
  python scripts/reparse.py --models magistral-small-2509 --write  # rewrite JSON/MD (keeps .bak)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from llm_survey.config import REPO_ROOT  # noqa: E402
from llm_survey.parsing import split_reasoning  # noqa: E402
from llm_survey.runner import render_markdown  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-name", default="main")
    p.add_argument("--out-root", default=str(REPO_ROOT / "outputs"))
    p.add_argument("--models", nargs="*")
    p.add_argument("--write", action="store_true")
    args = p.parse_args(argv)

    run_dir = Path(args.out_root) / args.run_name
    for path in sorted(run_dir.glob("*/*.json")):
        if args.models and path.parent.name not in args.models:
            continue
        rec = json.loads(path.read_text())
        changed = 0
        for t in rec.get("turns", []):
            new = split_reasoning(t["raw_output"], prompt=t["rendered_prompt"])
            if (new.answer, new.reasoning) != (t["answer"], t.get("reasoning")):
                changed += 1
                print(f"{path.parent.name}/{rec['condition']} {t['qid']}: format {t['reasoning_format']} -> {new.format}")
                print(f"    old answer: {t['answer'][:120]!r}\n    new answer: {new.answer[:120]!r}")
                t.update(answer=new.answer, reasoning=new.reasoning, reasoning_format=new.format,
                         reasoning_unterminated=new.reasoning_unterminated or t["reasoning_unterminated"])
        if changed and args.write:
            shutil.copy(path, path.with_suffix(".json.bak"))
            rec["reparsed"] = True
            path.write_text(json.dumps(rec, indent=2, ensure_ascii=False))
            path.with_suffix(".md").write_text(render_markdown(rec))
    if not args.write:
        print("\n(dry run; add --write to save)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
