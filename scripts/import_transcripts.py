#!/usr/bin/env python
"""Turn conversations pasted from chat apps into the same JSON as the GPU runs.

  python scripts/import_transcripts.py --new claude-opus-5-5   # templates to paste into
  python scripts/import_transcripts.py                         # every transcript -> outputs/main/
  python scripts/import_transcripts.py claude-opus-5-5         # just this model

Models are listed in config/app_models.yaml. --new writes transcripts/<key>/sequential.md and
independent.md, with the questions in order and a header for the app's settings. Paste each reply
under its question's "answer" marker (the app's copy button keeps the formatting), and the app's
thinking summary under "reasoning" if it shows one. Importing again after an edit replaces the
JSON; a transcript with answers still missing is saved as "partial", so label.py shows what is there.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from llm_survey.config import (  # noqa: E402
    CONFIG_DIR, REPO_ROOT, load_app_models, load_questions, questions_sha256,
)

CONDITIONS = ("sequential", "independent")
SETTINGS = {  # filled in by hand in each transcript's header
    "date": "YYYY-MM-DD of the conversation",
    "plan": "e.g. Plus, Pro, free",
    "model_label": "exactly what the model picker showed",
    "thinking": "what the app showed: off, on, extended, ...",
    "temporary_chat": "yes if it was a temporary/incognito chat with memory and custom instructions off",
    "web_search": "off, or on if the app searched the web",
}
HOW = {
    "sequential": "Sequential: ask Q1 to Q4 in this order, all in ONE new chat.",
    "independent": "Independent: ask each question in its OWN new chat.",
}
# HTML comments: hidden in a Markdown preview, and never part of a model's reply
MARK_Q = re.compile(r"^<!-- (Q\d+) -->[ \t]*$", re.M)
MARK_ANSWER = re.compile(r"^<!-- answer\b.*?-->[ \t]*$", re.M)
MARK_REASONING = re.compile(r"^<!-- reasoning\b.*?-->[ \t]*$", re.M)


def template(model: dict, condition: str, questions) -> str:
    head = {k: model[k] for k in ("key", "name", "lab", "weights", "app")}
    lines = ["---", yaml.safe_dump({**head, "condition": condition}, sort_keys=False).strip(), "# fill in:"]
    lines += [f"{k + ':':<16}# {hint}" for k, hint in SETTINGS.items()]
    lines += ["---", "", HOW[condition], ""]
    for q in questions:
        lines += [f"<!-- {q.id} -->", f"### {q.id}", q.text, "",
                  "<!-- answer: paste the reply below this line -->", "", "",
                  "<!-- reasoning (optional): paste the app's thinking summary below, if it shows one -->", "", ""]
    return "\n".join(lines)


def parse(path: Path, questions) -> tuple[dict, dict[str, dict], list[str]]:
    """The header, {qid: {answer, reasoning}} for every question block, and problems worth a warning."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise ValueError(f"{path}: the settings header (between the --- lines) is missing")
    head = yaml.safe_load(m.group(1)) or {}
    texts = {q.id: q.text for q in questions}
    found, problems = {}, []
    parts = MARK_Q.split(text[m.end():])  # [preamble, "Q1", block, "Q2", block, ...]
    for qid, block in zip(parts[1::2], parts[2::2]):
        a = MARK_ANSWER.search(block)
        if qid not in texts or not a:
            problems.append(f"{qid}: {'not a survey question' if qid not in texts else 'answer marker missing'}")
            continue
        if texts[qid] not in block[:a.start()]:
            problems.append(f"{qid}: the question text was edited; make sure the app got the exact wording")
        rest = block[a.end():]
        r = MARK_REASONING.search(rest)
        found[qid] = {"answer": (rest[:r.start()] if r else rest).strip(),
                      "reasoning": rest[r.end():].strip() if r else ""}
    unfilled = [k for k in SETTINGS if head.get(k) in (None, "")]
    if unfilled:
        problems.append(f"settings not filled in: {', '.join(unfilled)}")
    return head, found, problems


def to_record(model: dict, condition: str, head: dict, found: dict, questions, path: Path) -> dict:
    settings = {k: head.get(k).isoformat() if isinstance(head.get(k), dt.date) else head.get(k) for k in SETTINGS}
    turns = []
    for i, q in enumerate(questions):
        got = found.get(q.id)
        if not got or not got["answer"]:
            continue
        turns.append({
            "qid": q.id,
            "question": q.text,
            "chat_index": 0 if condition == "sequential" else i,
            "answer": got["answer"],
            "reasoning": got["reasoning"] or None,
            "reasoning_format": "app_summary" if got["reasoning"] else "none",
            "reasoning_unterminated": False,
            "finish_reason": None,   # the apps don't say whether a reply hit a length limit
            "n_output_tokens": None,
            "seconds": None,
        })
    complete = len(turns) == len(questions)
    return {
        "status": "complete" if complete else "partial",
        "source": "chat_app",
        "model_key": model["key"],
        "condition": condition,
        "model_name": model["name"],
        "lab": model["lab"],
        "weights": model["weights"],
        "app": model["app"],
        "app_settings": settings,
        "hf_id": None,
        "revision_resolved": None,
        "sampling": None,
        "started": settings["date"],
        "finished": settings["date"] if complete else None,
        "questions_sha256": questions_sha256(questions),
        "questions": [{"id": q.id, "text": q.text} for q in questions],
        "transcript": f"transcripts/{model['key']}/{path.name}",
        "transcript_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "turns": turns,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("keys", nargs="*", help="models to import (default: every folder under transcripts/)")
    p.add_argument("--new", metavar="KEY", nargs="+", help="write empty transcript templates for these models")
    p.add_argument("--run-name", default="main")
    p.add_argument("--out-root", default=str(REPO_ROOT / "outputs"))
    p.add_argument("--transcripts", default=str(REPO_ROOT / "transcripts"))
    p.add_argument("--app-models", default=str(CONFIG_DIR / "app_models.yaml"))
    args = p.parse_args(argv)

    models, questions, root = load_app_models(args.app_models), load_questions(), Path(args.transcripts)
    unknown = [k for k in (args.new or args.keys) if k not in models]
    if unknown:
        print(f"Not in {args.app_models}: {', '.join(unknown)}. Add them there first.")
        return 1

    if args.new:
        for key in args.new:
            for cond in CONDITIONS:
                path = root / key / f"{cond}.md"
                if path.exists():
                    print(f"{path} exists; left as it is")
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(template(models[key], cond, questions), encoding="utf-8")
                print(f"wrote {path}")
        return 0

    keys = args.keys or (sorted(d.name for d in root.iterdir() if d.is_dir() and d.name in models)
                         if root.exists() else [])
    if not keys:
        print(f"No transcripts under {root}; start one with --new <key>")
        return 1
    rc = 0
    for key in keys:
        for cond in CONDITIONS:
            path = root / key / f"{cond}.md"
            if not path.exists():
                continue
            head, found, problems = parse(path, questions)
            rec = to_record(models[key], cond, head, found, questions, path)
            if not rec["turns"]:
                print(f"{key}/{cond}: no answers pasted yet")
                continue
            out = Path(args.out_root) / args.run_name / key / f"{cond}.json"
            if out.exists() and json.loads(out.read_text(encoding="utf-8")).get("source") != "chat_app":
                print(f"{key}/{cond}: {out} holds a GPU run; not overwriting it")
                rc = 1
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
            have = {t["qid"] for t in rec["turns"]}
            missing = [q.id for q in questions if q.id not in have]
            print(f"{key}/{cond}: {rec['status']}, {len(have)} of {len(questions)} answers"
                  + (f" (missing {', '.join(missing)})" if missing else ""))
            for problem in problems:
                print(f"    {problem}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
