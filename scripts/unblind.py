#!/usr/bin/env python
"""Join your codes from the blind sheet back to model and condition.

  python scripts/unblind.py                     # run "main"

Reads outputs/<run>/coding_workbook.xlsx ("Blind coding" sheet) and blind_key.csv,
writes outputs/<run>/coded_answers.csv with one row per (model, condition, question)
and a wide table (models x condition x question) in coded_wide.csv.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from llm_survey.config import REPO_ROOT  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-name", default="main")
    p.add_argument("--out-root", default=str(REPO_ROOT / "outputs"))
    args = p.parse_args(argv)

    run_dir = Path(args.out_root) / args.run_name
    coded = pd.read_excel(run_dir / "coding_workbook.xlsx", sheet_name="Blind coding")
    key = pd.read_csv(run_dir / "blind_key.csv")
    merged = key.merge(coded[["blind_id", "code", "notes"]], on="blind_id", how="left")
    answers = pd.read_csv(run_dir / "answers_long.csv")
    merged = merged.merge(answers[["model_key", "condition", "qid", "question", "answer"]],
                          on=["model_key", "condition", "qid"], how="left")
    missing = merged.code.isna().sum()
    merged.sort_values(["model_key", "condition", "qid"]).to_csv(run_dir / "coded_answers.csv", index=False)
    wide = merged.pivot_table(index="model_key", columns=["condition", "qid"], values="code", aggfunc="first")
    wide.to_csv(run_dir / "coded_wide.csv")
    print(wide.to_string())
    print(f"\nWrote coded_answers.csv and coded_wide.csv ({missing} answers still uncoded)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
