#!/usr/bin/env python
"""Gather every saved answer into files for coding.

  python scripts/collect.py                 # run "main"
  python scripts/collect.py --run-name smoke

Writes to outputs/<run>/:
  answers_long.csv       one row per (model, condition, question), with answer and reasoning
  coding_workbook.xlsx   "Blind coding": answers grouped by question, shuffled, with model and
                         condition hidden and a dropdown of the human-survey categories;
                         "All answers": the same answers with labels, for reading
  blind_key.csv          blind_id -> model / condition (keep closed while coding)
Then run scripts/unblind.py to join your codes back to the labels.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from llm_survey.config import REPO_ROOT  # noqa: E402

# Same categories used to classify the human answers.
CODEBOOK = {
    "Q1": ["yes", "~50%", "no", "I don't code", "unclear/refused"],
    "Q2": ["yes", "no", "-", "unclear/refused"],
    "Q3": ["yes", "yes in the future", "maybe", "no", "idc", "unclear/refused"],
    "Q4": None,  # free-text definition; code themes as you like
}
CODE_HELP = {
    "Q1": "As in the human survey: reads AI code yes / about half the time / no / doesn't code.",
    "Q2": "As in the human survey: would use AI for therapy or emotional issues yes / no; '-' as used for humans.",
    "Q3": "As in the human survey: yes / yes in the future / maybe / no / doesn't care.",
    "Q4": "Free text: summarise the definition (e.g. subjective experience, self-awareness, information integration...).",
}


def load_run(run_dir: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(run_dir.glob("*/*.json")):
        rec = json.loads(path.read_text())
        for t in rec.get("turns", []):
            rows.append({
                "model_key": rec["model_key"],
                "weights": rec.get("weights", "open"),   # GPU runs are all open-weight models
                "source": rec.get("source", "gpu"),      # gpu, or chat_app (scripts/import_transcripts.py)
                "hf_id": rec.get("hf_id"),
                "revision": rec.get("revision_resolved"),
                "condition": rec["condition"],
                "status": rec.get("status"),
                "qid": t["qid"],
                "question": t["question"],
                "answer": t["answer"],
                "reasoning": t.get("reasoning"),
                "reasoning_format": t.get("reasoning_format"),
                "answer_chars": len(t["answer"] or ""),
                "reasoning_chars": len(t.get("reasoning") or ""),
                "n_output_tokens": t["n_output_tokens"],
                "finish_reason": t["finish_reason"],
                "reasoning_unterminated": t["reasoning_unterminated"],
                "seconds": t["seconds"],
                "sampling": json.dumps(rec.get("sampling")),
                "file": str(path.relative_to(run_dir)),
            })
    return pd.DataFrame(rows)


def write_workbook(df: pd.DataFrame, out: Path, key_path: Path, seed: int) -> None:
    rng = random.Random(seed)
    df = df.copy()
    order = []
    for qid in sorted(df.qid.unique()):
        idx = list(df.index[df.qid == qid])
        rng.shuffle(idx)
        order += idx
    blind = df.loc[order].reset_index()
    blind["blind_id"] = [f"A{i + 1:03d}" for i in range(len(blind))]
    blind[["blind_id", "model_key", "condition", "qid", "file"]].to_csv(key_path, index=False)

    wb = Workbook()
    hdr_font, hdr_fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F3A5F")
    wrap = Alignment(wrap_text=True, vertical="top")

    ws = wb.active
    ws.title = "Blind coding"
    cols = ["blind_id", "qid", "question", "answer", "code", "notes"]
    ws.append(cols)
    for r in blind.itertuples():
        ws.append([r.blind_id, r.qid, r.question, r.answer, None, None])
    for c in ws[1]:
        c.font, c.fill = hdr_font, hdr_fill
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = wrap
    for col, w in zip("ABCDEF", [10, 6, 40, 90, 18, 30]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    for qid, options in CODEBOOK.items():
        rows = [i + 2 for i, q in enumerate(blind.qid) if q == qid]
        if not options or not rows:
            continue
        dv = DataValidation(type="list", formula1='"' + ",".join(options) + '"', allow_blank=True,
                            showErrorMessage=False)
        dv.prompt, dv.promptTitle = CODE_HELP[qid], f"{qid} code"
        ws.add_data_validation(dv)
        dv.add(f"E{min(rows)}:E{max(rows)}")

    ws2 = wb.create_sheet("All answers")
    cols2 = ["model_key", "condition", "qid", "question", "answer", "finish_reason", "reasoning_chars",
             "n_output_tokens", "reasoning"]
    ws2.append(cols2)
    for r in df.sort_values(["model_key", "condition", "qid"]).itertuples():
        # missing reasoning is NaN, not None, in pandas >= 3; Excel cell limit is 32,767 characters
        reasoning = "" if pd.isna(r.reasoning) else r.reasoning[:32000]
        ws2.append([r.model_key, r.condition, r.qid, r.question, r.answer, r.finish_reason, r.reasoning_chars,
                    r.n_output_tokens, reasoning])
    for c in ws2[1]:
        c.font, c.fill = hdr_font, hdr_fill
    for row in ws2.iter_rows(min_row=2):
        for c in row:
            c.alignment = wrap
    for col, w in zip("ABCDEFGHI", [26, 12, 6, 40, 80, 12, 14, 14, 60]):
        ws2.column_dimensions[col].width = w
    ws2.freeze_panes = "A2"

    ws3 = wb.create_sheet("Codebook")
    ws3.append(["qid", "categories", "guidance"])
    for qid, options in CODEBOOK.items():
        ws3.append([qid, ", ".join(options) if options else "free text", CODE_HELP[qid]])
    for c in ws3[1]:
        c.font, c.fill = hdr_font, hdr_fill
    ws3.column_dimensions["B"].width = 60
    ws3.column_dimensions["C"].width = 90
    wb.save(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-name", default="main")
    p.add_argument("--out-root", default=str(REPO_ROOT / "outputs"))
    p.add_argument("--seed", type=int, default=7, help="shuffle seed for the blind sheet")
    p.add_argument("--force", action="store_true", help="overwrite an existing coding workbook")
    args = p.parse_args(argv)

    run_dir = Path(args.out_root) / args.run_name
    df = load_run(run_dir)
    if df.empty:
        print(f"No answers found under {run_dir}")
        return 1
    df.to_csv(run_dir / "answers_long.csv", index=False)
    wb_path, key_path = run_dir / "coding_workbook.xlsx", run_dir / "blind_key.csv"
    if wb_path.exists() and not args.force:
        print(f"{wb_path} exists (it may hold your codes); use --force to rebuild it")
    else:
        write_workbook(df, wb_path, key_path, args.seed)
        print(f"Wrote {wb_path} and {key_path}")

    summary = df.groupby(["model_key", "condition"]).agg(
        answers=("qid", "count"), complete=("status", lambda s: (s == "complete").all()),
        truncated=("finish_reason", lambda s: int((s == "length").sum())),
        empty=("answer_chars", lambda s: int((s == 0).sum())),
    )
    print(summary.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
