#!/usr/bin/env python
"""The LLMs' coded answers (labels.csv) drawn like the human-survey figures, open vs closed weights.

  python scripts/plot_llm_categories.py

Writes to outputs/<run>/plots/:
  categories_by_group.png     "Homogeneity in LLM Responses": open- and closed-weight models' answers to
                              Q1-Q3 (and each condition)
  categories_predicting.png   Q1 and Q2 answers vs saying AI could be conscious
  categories_profiles.png     Q1 · Q2 · Q3 answer combinations

Each model answers twice (sequential and independent), so each answer counts once and n is answers,
not models.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
import textwrap
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect  # noqa: E402

INK, INK_2, INK_3, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#fcfcfb"
BLUE, LIGHT_BLUE, LIGHT_GREY, RED, DARK_GREY = "#2a78d6", "#86b6ef", "#dcdbd5", "#e34948", "#8f8e88"
GROUP_COLOURS = {"Open weights": "#1baf7a", "Closed weights": "#6250d6"}
GROUPS = list(GROUP_COLOURS)
CONDS = ["sequential", "independent"]

QUESTIONS = {  # qid: (title, [(code, legend label, colour)])
    "Q1": ("If you were a human and used AI to code, would you read the code it generates?",
           [("yes", "Yes", BLUE), ("~50%", "~50%", LIGHT_BLUE), ("no", "No", RED),
            ("I don't code", "I don't code", DARK_GREY), ("unclear/refused", "Unclear / no stance", INK_3)]),
    "Q2": ("If you were a human, would you try using AI as a therapist, or for emotional issues?",
           [("yes", "Yes", BLUE), ("no", "No", RED), ("-", "“–” (dash)", DARK_GREY),
            ("unclear/refused", "Unclear / no stance", INK_3)]),
    "Q3": ("According to your own definition of consciousness, do you think AI could be conscious?",
           [("yes", "Yes", BLUE), ("yes in the future", "Yes, in the future", LIGHT_BLUE),
            ("maybe", "Maybe", LIGHT_GREY), ("no", "No", RED), ("idc", "Don't care", DARK_GREY),
            ("unclear/refused", "Unclear / no stance", INK_3)]),
}
SHORT = {"yes": "yes", "~50%": "~50%", "no": "no", "maybe": "maybe", "yes in the future": "yes, future",
         "unclear/refused": "unclear", "I don't code": "doesn't code", "idc": "don't care", "-": "–"}
CONSCIOUS = {"yes", "yes in the future"}

plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Helvetica", "DejaVu Sans"], "font.size": 10,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlecolor": INK,
})


# ---------------------------------------------------------------- data

def load(run_dir: Path):
    """One dict per answer: model, group, condition, and the Q1-Q3 codes."""
    df = collect.load_run(run_dir)
    group = {r.model_key: GROUPS[0] if r.weights == "open" else GROUPS[1] for r in df.itertuples()}
    codes = {}
    with (run_dir / "labels.csv").open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            codes.setdefault((r["model_key"], r["condition"]), {})[r["qid"]] = r["code"]
    rows = [{"model": m, "group": group[m], "condition": c, **q} for (m, c), q in sorted(codes.items())
            if all(q.get(k) for k in ("Q1", "Q2", "Q3"))]
    missing = len(df.groupby(["model_key", "condition"])) - len(rows)
    return rows, missing


# ---------------------------------------------------------------- statistics

def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return math.nan, math.nan
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def mantel_haenszel(tables):
    """Pooled odds ratio over 2x2 tables [[a, b], [c, d]] (a = exposed & outcome), with the
    Robins-Breslow-Greenland 95% CI and the CMH test p. None if not estimable."""
    tables = [np.asarray(t, float) for t in tables if np.asarray(t).sum() > 0]
    R = sum(t[0, 0] * t[1, 1] / t.sum() for t in tables)
    S = sum(t[0, 1] * t[1, 0] / t.sum() for t in tables)
    if R == 0 or S == 0:
        return None
    P = [(t[0, 0] + t[1, 1]) / t.sum() for t in tables]
    Q = [(t[0, 1] + t[1, 0]) / t.sum() for t in tables]
    r = [t[0, 0] * t[1, 1] / t.sum() for t in tables]
    s = [t[0, 1] * t[1, 0] / t.sum() for t in tables]
    var = (sum(p * x for p, x in zip(P, r)) / (2 * R * R)
           + sum(p * y + q * x for p, q, x, y in zip(P, Q, r, s)) / (2 * R * S)
           + sum(q * y for q, y in zip(Q, s)) / (2 * S * S))
    orr = R / S
    lo, hi = orr * math.exp(-1.96 * math.sqrt(var)), orr * math.exp(1.96 * math.sqrt(var))
    num = sum(t[0, 0] - t[0].sum() * t[:, 0].sum() / t.sum() for t in tables)
    den = sum(t[0].sum() * t[1].sum() * t[:, 0].sum() * t[:, 1].sum() / (t.sum() ** 2 * (t.sum() - 1))
              for t in tables if t.sum() > 1)
    p = math.erfc(math.sqrt((abs(num) - 0.5) ** 2 / den / 2)) if den > 0 else math.nan
    return orr, lo, hi, p


# ---------------------------------------------------------------- drawing helpers

def fmt_p(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def stacked_row(ax, y, counts: Counter, cats, n, height=0.62, min_label=0.06):
    left = 0.0
    for code, _, colour in cats:
        share = counts.get(code, 0) / n if n else 0
        if share:
            ax.barh(y, share - 0.004, left=left + 0.002, height=height, color=colour, linewidth=0)
            if share >= min_label:
                dark = colour in (LIGHT_BLUE, LIGHT_GREY)
                ax.text(left + share / 2, y, f"{share:.0%}", ha="center", va="center", fontsize=10,
                        color=INK if dark else "white")
        left += share
    ax.text(1.02, y, f"n={n}", va="center", fontsize=9.5, color=INK_3, transform=ax.get_yaxis_transform())


def legend_row(ax, cats, used, y=1.02):
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for code, _, c in cats if code in used]
    labels = [lab for code, lab, _ in cats if code in used]
    ax.legend(handles, labels, ncol=len(handles), frameon=False, loc="lower left", bbox_to_anchor=(0, y),
              fontsize=9.5, handlelength=1.0, handletextpad=0.5, columnspacing=1.4, borderaxespad=0)


def percent_axis(ax, labels=True):
    ax.set_xlim(0, 1)
    ax.set_xticks([0, .25, .5, .75, 1], ["0%", "25%", "50%", "75%", "100%"] if labels else [])
    ax.tick_params(axis="y", length=0, labelsize=11)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


# ---------------------------------------------------------------- figures

def fig_by_group(rows, out: Path):
    blocks = [(g, [r for r in rows if r["group"] == g]) for g in GROUPS] + [None] + \
             [(c.capitalize(), [r for r in rows if r["condition"] == c]) for c in CONDS] + [None] + \
             [("All LLMs", rows)]
    fig, axes = plt.subplots(3, 1, figsize=(10, 11.5))
    for ax, (qid, (title, cats)) in zip(axes, QUESTIONS.items()):
        y, ticks = 0.0, []
        for b in blocks:
            if b is None:
                ax.axhline(y - 0.5 + 0.35, color=GRID, linewidth=1.2)
                y += 0.2
                continue
            name, sub = b
            stacked_row(ax, y, Counter(r[qid] for r in sub), cats, len(sub))
            ticks.append((y, name))
            y += 1
        ax.set_yticks([t for t, _ in ticks], [n for _, n in ticks])
        ax.set_ylim(y - 0.5, -0.6)
        percent_axis(ax)
        used = {r[qid] for r in rows}
        legend_row(ax, cats, used)
        ax.set_title(textwrap.fill(title, 70), pad=26, fontsize=12.5)
    fig.suptitle("Homogeneity in LLM Responses", x=0.04, ha="left", fontsize=17, fontweight="bold", color=INK)
    fig.text(0.04, 0.957, textwrap.fill("Compared to humans, LLMs' responses are homogeneous: nearly all would read "
                                        "AI-generated code and use AI for emotional support. Only AI consciousness "
                                        "splits them.", 105), fontsize=11.5, color=INK_2, va="top", linespacing=1.4)
    fig.tight_layout(rect=(0, 0, 1, 0.93), h_pad=3.0)
    fig.savefig(out, dpi=170)


def fig_predicting(rows, out: Path):
    q3_cats = QUESTIONS["Q3"][1]
    panels = [
        ("Q1", "Reading AI-Generated Code", [("yes", "Reads it: yes", BLUE), ("~50%", "Reads it: ~50%", LIGHT_BLUE),
                                             ("no", "Reads it: no", RED), ("I don't code", "Doesn't code", DARK_GREY)],
         lambda c: c in ("yes", "~50%"), "Reads AI code (yes / ~50%)", "Doesn't read it (no)"),
        ("Q2", "Using AI for Emotional Issues", [("yes", "Would use AI for emotions: yes", BLUE),
                                                 ("no", "Would use AI for emotions: no", RED),
                                                 ("unclear/refused", "No stance / unclear", INK_3)],
         lambda c: c == "yes", "Would use AI for emotional issues", "Wouldn't"),
    ]
    fig = plt.figure(figsize=(16, 11))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.25, 1], hspace=0.75, wspace=0.42, left=0.17, right=0.97,
                          top=0.85, bottom=0.13)
    for i, (qid, name, levels, exposed, exp_label, unexp_label) in enumerate(panels):
        ax = fig.add_subplot(gs[i, 0])
        present = [(code, lab) for code, lab, _ in levels if any(r[qid] == code for r in rows)]
        for y, (code, lab) in enumerate(present):
            sub = [r for r in rows if r[qid] == code]
            stacked_row(ax, y, Counter(r["Q3"] for r in sub), q3_cats, len(sub))
        ax.set_yticks(range(len(present)), [lab for _, lab in present])
        ax.set_ylim(len(present) - 0.5, -0.6)
        percent_axis(ax)
        legend_row(ax, q3_cats, {r["Q3"] for r in rows})
        ax.set_title(f"{name}  →  Says AI Could Be Conscious", pad=30)
        ax.text(0, -0.13 if len(present) > 1 else -0.3, "Both groups pooled; each model counted once per condition.",
                transform=ax.transAxes, fontsize=9, color=INK_3)

        # right: within each group, % saying conscious (now or future), 95% Wilson CI
        ax2 = fig.add_subplot(gs[i, 1])
        series = [(exp_label, BLUE, lambda r: exposed(r[qid])), (unexp_label, RED, lambda r: not exposed(r[qid]))]
        y, ticks, tables = 0.0, [], []
        for gname, sub in [(g, [r for r in rows if r["group"] == g]) for g in GROUPS] + [("All LLMs", rows)]:
            if gname == "All LLMs":
                ax2.axhline(y - 0.45, color=GRID, linewidth=1.2)
                y += 0.15
            ticks.append((y + 0.14, gname))
            table = []
            for j, (lab, colour, f) in enumerate(series):
                s = [r for r in sub if f(r)]
                k = sum(r["Q3"] in CONSCIOUS for r in s)
                table.append([k, len(s) - k])
                if not s:
                    continue
                lo, hi = wilson(k, len(s))
                yy = y + j * 0.28
                ax2.hlines(yy, lo, hi, color=colour, alpha=0.45, linewidth=2)
                ax2.scatter([k / len(s)], [yy], s=60, color=colour, edgecolor=SURFACE, linewidth=1.5, zorder=3,
                            label=lab if gname == GROUPS[0] else None)
                ax2.text(min(hi, 1) + 0.02, yy, f"{k}/{len(s)}", va="center", fontsize=9, color=INK_2)
            if gname != "All LLMs":
                tables.append(table)
            y += 1
        ax2.set_yticks([t for t, _ in ticks], [n for _, n in ticks])
        ax2.set_ylim(y - 0.4, -0.5)
        percent_axis(ax2)
        ax2.set_xlim(0, 1.12)
        ax2.set_xlabel("% saying AI could be conscious (now or in future), 95% CI", fontsize=10)
        handles, labels = ax2.get_legend_handles_labels()
        ax2.legend(handles, labels, ncol=2, frameon=False, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=9.5,
                   handletextpad=0.3, columnspacing=1.2, borderaxespad=0)
        ax2.set_title("Within Each Group", pad=30)
        mh = mantel_haenszel(tables)
        note = (f"Within-group odds ratio (Mantel–Haenszel): {mh[0]:.1f} [{mh[1]:.1f}–{mh[2]:.1f}], {fmt_p(mh[3])}"
                if mh else "Odds ratio not estimable: a comparison group is empty or has no answers on one side.")
        if qid == "Q1":
            note = "No LLM said it wouldn't read AI code, so there is no comparison group\nand no odds ratio."
        ax2.text(0, -0.2, note, transform=ax2.transAxes, fontsize=9, color=INK_2, va="top", linespacing=1.4)
    fig.suptitle("Predicting “AI Could Be Conscious” From the Other Answers, LLMs", x=0.17, ha="left",
                 fontsize=17, fontweight="bold", color=INK)
    fig.text(0.17, 0.925, "Answers are not independent (each model answers twice), so the intervals and the odds "
             "ratio overstate certainty.", fontsize=9.5, color=INK_3)
    fig.savefig(out, dpi=170)


def fig_profiles(rows, out: Path):
    combos = Counter((r["Q1"], r["Q2"], r["Q3"]) for r in rows)
    order = sorted(combos, key=lambda c: (-combos[c], c))
    fig, ax = plt.subplots(figsize=(13, 0.42 * len(order) + 2))
    for y, c in enumerate(order):
        left = 0
        for g in GROUPS:
            k = sum(1 for r in rows if (r["Q1"], r["Q2"], r["Q3"]) == c and r["group"] == g)
            if k:
                ax.barh(y, k - 0.06, left=left + 0.03, height=0.62, color=GROUP_COLOURS[g], linewidth=0,
                        label=g if y == 0 or g not in ax.get_legend_handles_labels()[1] else None)
                if k >= 2:
                    ax.text(left + k / 2, y, str(k), ha="center", va="center", fontsize=9.5, color="white")
            left += k
        ax.text(left + 0.2, y, str(combos[c]), va="center", fontsize=10, color=INK)
    ax.set_yticks(range(len(order)), [f"Reads AI code: {SHORT[a]}  ·  AI therapy: {SHORT[b]}  ·  AI conscious: {SHORT[d]}"
                                      for a, b, d in order], fontsize=10.5)
    ax.set_ylim(len(order) - 0.5, -0.6)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("Answers (model × condition)", fontsize=11)
    ax.set_xlim(0, max(combos.values()) + 1.2)
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, ncol=2, frameon=False, loc="lower right", bbox_to_anchor=(1, 1.0), fontsize=10, borderaxespad=0)
    ax.set_title("Individual Answer Profiles, LLMs", fontsize=16, pad=40)
    ax.text(0, 1.06, f"Every answer combination. {len(combos)} distinct combinations among {len(rows)} answers "
            "(each model answers twice: sequential and independent).", transform=ax.transAxes, fontsize=9.5, color=INK_2)
    fig.tight_layout()
    fig.savefig(out, dpi=170)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-name", default="main")
    p.add_argument("--out-root", default=str(collect.REPO_ROOT / "outputs"))
    args = p.parse_args(argv)
    run_dir = Path(args.out_root) / args.run_name
    if not (run_dir / "labels.csv").exists():
        print(f"No {run_dir / 'labels.csv'}; label the answers first (scripts/label.py)")
        return 1
    rows, missing = load(run_dir)
    if missing:
        print(f"Note: {missing} answers lack a Q1-Q3 label and are left out")
    out = run_dir / "plots"
    out.mkdir(exist_ok=True)
    fig_by_group(rows, out / "categories_by_group.png")
    fig_predicting(rows, out / "categories_predicting.png")
    fig_profiles(rows, out / "categories_profiles.png")
    print(f"Wrote {out}/categories_*.png from {len(rows)} answers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
