#!/usr/bin/env python
"""Ask one model the survey, in both conditions, and save every answer.

Examples
  python scripts/run_model.py --model gpt-oss-20b
  python scripts/run_model.py --model gpt-oss-20b --smoke          # Q1 only, 64 tokens -> outputs/smoke/
  python scripts/run_model.py --model gpt-oss-20b --conditions independent
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm_survey.config import REPO_ROOT, load_models, load_questions  # noqa: E402
from llm_survey.runner import CONDITIONS, ResultWriter, run_independent, run_sequential  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", required=True, help="model key from config/models.yaml")
    p.add_argument("--conditions", nargs="+", choices=CONDITIONS, default=list(CONDITIONS))
    p.add_argument("--run-name", default="main", help="outputs go to outputs/<run-name>/<model>/")
    p.add_argument("--out-root", default=str(REPO_ROOT / "outputs"))
    p.add_argument("--max-new-tokens", type=int, default=None, help="override the cap from models.yaml")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--smoke", action="store_true", help="load-and-answer check: Q1 only, 64 tokens, run-name 'smoke'")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--model-path", default=None, help="load from a local directory instead of the Hub id (testing)")
    p.add_argument("--models-config", default=str(REPO_ROOT / "config" / "models.yaml"))
    p.add_argument("--questions-config", default=str(REPO_ROOT / "config" / "questions.yaml"))
    args = p.parse_args(argv)

    specs = load_models(args.models_config)
    if args.model not in specs:
        p.error(f"unknown model {args.model!r}; choose from: {', '.join(specs)}")
    spec = specs[args.model]
    questions = load_questions(args.questions_config)
    max_new = args.max_new_tokens
    run_name = args.run_name
    if args.smoke:
        questions, max_new = questions[:1], max_new or 64
        run_name = "smoke" if args.run_name == "main" else args.run_name
        args.overwrite = True
    seed = args.seed if args.seed is not None else spec.seed

    from llm_survey.engine import ChatEngine

    print(f"[{spec.key}] loading {args.model_path or spec.hf_id} (revision={spec.revision})", flush=True)
    engine = ChatEngine(spec, model_path=args.model_path, max_new_tokens=max_new)
    meta = engine.metadata()
    print(f"[{spec.key}] sampling from generation_config: {meta['sampling']}", flush=True)
    out_dir = Path(args.out_root) / run_name

    failed = False
    for condition in args.conditions:
        writer = ResultWriter(out_dir, spec.key, condition, meta, questions, seed, overwrite=args.overwrite)
        runner = run_sequential if condition == "sequential" else run_independent

        def log(turn, _w=writer, _c=condition):
            _w.add_turn(turn)
            print(f"[{spec.key}/{_c}] {turn['qid']}: {turn['n_output_tokens']} tokens, {turn['seconds']} s, "
                  f"finish={turn['finish_reason']}, reasoning={turn['reasoning_format']}\n"
                  f"    answer: {turn['answer'][:300]!r}", flush=True)

        try:
            messages = runner(engine, questions, seed, log)
            writer.finish(messages)
            print(f"[{spec.key}/{condition}] saved {writer.json_path}", flush=True)
        except Exception:
            failed = True
            writer.record["status"] = "failed"
            writer.record["error"] = traceback.format_exc()
            writer.flush()
            traceback.print_exc()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
