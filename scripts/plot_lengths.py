#!/usr/bin/env python
"""How long are the answers? Words per answer by model, condition and question (reasoning ignored).

  python scripts/plot_lengths.py               # run "main"
  python scripts/plot_lengths.py --run-name smoke

Writes to outputs/<run>/plots/:
  lengths_by_model.png       mean words per model, sequential vs independent
  lengths_by_question.png    the same per question, one panel each
  lengths_question_bars.png  mean words per question, ± 1 SD, over every model and condition
  lengths_spread.png         every answer, by question and condition
  lengths_seq_vs_ind.png     sequential / independent length ratio per model, by question
  lengths.csv                the words per answer behind the plots
Needs matplotlib (pip install matplotlib).
"""
from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect  # noqa: E402
from label import GROUPS  # noqa: E402
from llm_survey.config import load_app_models  # noqa: E402

COND = {"sequential": "#2a78d6", "independent": "#eb6834"}   # categorical slots 1 and 2
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
QIDS = ["Q1", "Q2", "Q3", "Q4"]
ORGS = {"allenai": "Ai2", "deepseek-ai": "DeepSeek", "google": "Google", "meta-llama": "Meta", "mistralai": "Mistral",
        "nvidia": "NVIDIA", "openai": "OpenAI", "Qwen": "Qwen"}   # Hugging Face organisation -> family
SHORT = {"Q1":"read AI's code?", "Q2": "AI as therapist?", "Q3": "could AI be conscious?", "Q4": "define consciousness"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
})


def group_of(row) -> str:
    if row.source == "gpu":
        return GROUPS[0]
    return GROUPS[1] if row.weights == "open" else GROUPS[2]


def families(df) -> dict[str, str]:
    """model_key -> family: the lab for chat-app models, the Hugging Face organisation for GPU runs."""
    labs = {k: m["lab"] for k, m in load_app_models().items()}
    orgs = df.dropna(subset=["hf_id"]).groupby("model_key").hf_id.first().str.split("/").str[0]
    return {k: labs.get(k) or ORGS.get(orgs.get(k), orgs.get(k, "?")) for k in df.model_key.unique()}


def model_rows(df, family=None):
    """Models grouped as in label.py, with a heading row per group. Within a group: longest first, or,
    given {model_key: family}, by family with a small gap between families.

    Returns (keys, y position of each key, [(y, group heading)])."""
    mean = df.groupby("model_key").words.mean()
    group = df.groupby("model_key").group.first()
    keys, ys, heads, pos = [], [], [], 0.0
    for g in GROUPS:
        members = mean[group == g].sort_values(ascending=False).index.tolist()
        if not members:
            continue
        if family:
            members.sort(key=lambda k: (family[k].lower(), k))
        heads.append((pos, g))
        pos += 1.0
        for i, k in enumerate(members):
            if family and i and family[k] != family[members[i - 1]]:
                pos += 0.4
            keys.append(k)
            ys.append(pos)
            pos += 1
        pos += 0.4
    return keys, np.array(ys), heads


def dumbbells(ax, table, rows, label_groups=True):
    """One row per model: a thin line between the sequential and independent values, a dot for each.
    The sequential dot is drawn larger, so it still shows when the two are equal."""
    keys, y, heads = rows
    seq, ind = table.reindex(keys)["sequential"], table.reindex(keys)["independent"]
    ax.hlines(y, np.minimum(seq, ind), np.maximum(seq, ind), color=GRID, linewidth=2, zorder=1)
    ax.scatter(seq, y, s=70, color=COND["sequential"], edgecolor=SURFACE, linewidth=1.5, zorder=2, label="sequential")
    ax.scatter(ind, y, s=30, color=COND["independent"], edgecolor=SURFACE, linewidth=1, zorder=3, label="independent")
    ax.set_yticks(y, keys)
    ax.set_ylim(y[-1] + 0.7, -0.7)
    ax.grid(axis="y", visible=False)
    for hy, g in heads[1:]:
        ax.axhline(hy - 0.2, color=INK_2, linewidth=0.6)
    if label_groups:
        for hy, g in heads:
            ax.text(0, hy + 0.2, g, transform=ax.get_yaxis_transform(), fontsize=9,
                    fontweight="bold", color=INK_2, va="center")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-name", default="main")
    p.add_argument("--out-root", default=str(collect.REPO_ROOT / "outputs"))
    args = p.parse_args(argv)

    run_dir = Path(args.out_root) / args.run_name
    df = collect.load_run(run_dir)
    if df.empty:
        print(f"No answers under {run_dir}")
        return 1
    df["words"] = df.answer.fillna("").str.split().str.len()
    df["group"] = df.apply(group_of, axis=1)
    out = run_dir / "plots"
    out.mkdir(exist_ok=True)
    df[["model_key", "group", "condition", "qid", "words", "answer_chars"]].to_csv(out / "lengths.csv", index=False)
    rows = model_rows(df)
    height = 0.3 * (rows[1][-1] + 1) + 2

    # 1. mean words per model, models ordered by family
    table = df.pivot_table(index="model_key", columns="condition", values="words", aggfunc="mean")
    by_family = model_rows(df, families(df))
    fig, ax = plt.subplots(figsize=(8, 0.3 * (by_family[1][-1] + 1) + 2))
    dumbbells(ax, table, by_family)
    ax.set_xlim(0, table.max().max() * 1.05)
    ax.set_xlabel("Mean words per answer (Q1–Q4)")
    ax.set_title("Answer length by model", pad=26)
    ax.legend(ncol=2, frameon=False, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "lengths_by_model.png", dpi=160)

    # 2. the same, per question
    fig, axes = plt.subplots(1, 4, figsize=(15, height), sharey=True)
    for i, (ax, qid) in enumerate(zip(axes, QIDS)):
        q = df[df.qid == qid].pivot_table(index="model_key", columns="condition", values="words")
        dumbbells(ax, q, rows, label_groups=i == 0)
        ax.set_title(f"{qid} · {SHORT[qid]}", pad=8)
        ax.set_xlim(0, df.words.max() * 1.05)
        ax.set_xlabel("Words")
    axes[0].legend(ncol=2, frameon=False, loc="lower left", bbox_to_anchor=(0, 1.06), fontsize=9)
    fig.suptitle("Answer length by question", x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.tight_layout()
    fig.savefig(out / "lengths_by_question.png", dpi=160)

    # 2b. mean ± SD per question
    stats = df.groupby("qid").words.agg(["mean", "std", "count"]).reindex(QIDS)
    fig, ax = plt.subplots(figsize=(4.5, 3.2))
    ax.bar(range(4), stats["mean"], width=0.6, color=COND["sequential"])
    ax.errorbar(range(4), stats["mean"], yerr=stats["std"], fmt="none", ecolor=INK, elinewidth=1.2, capsize=4)
    ax.set_xticks(range(4), [f"{q}\n{textwrap.fill(SHORT[q], 13)}" for q in QIDS], fontsize=8)
    ax.tick_params(axis="x", colors=INK, length=0)
    ax.grid(axis="x", visible=False)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("Words per answer")
    ax.set_title(f"Mean answer length ± SD (n = {stats['count'].iloc[0]} each)", fontsize=10)
    fig.tight_layout()
    fig.savefig(out / "lengths_question_bars.png", dpi=160)

    # 3. every answer, by question and condition
    rng = np.random.default_rng(0)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for i, qid in enumerate(QIDS):
        for dx, cond in ((-0.18, "sequential"), (0.18, "independent")):
            w = df[(df.qid == qid) & (df.condition == cond)].words
            x = i + dx + rng.uniform(-0.09, 0.09, len(w))
            ax.scatter(x, w, s=30, color=COND[cond], alpha=0.75, edgecolor=SURFACE, linewidth=1,
                       label=cond if i == 0 else None)
            ax.hlines(w.median(), i + dx - 0.14, i + dx + 0.14, color=INK, linewidth=2)
    ax.set_xticks(range(4), [f"{q}\n{SHORT[q]}" for q in QIDS], fontsize=9)
    ax.tick_params(axis="x", colors=INK)
    ax.grid(axis="x", visible=False)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("Words per answer")
    ax.set_title("Every answer, by question (black bar = median)", pad=26)
    ax.legend(ncol=2, frameon=False, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "lengths_spread.png", dpi=160)

    # 4. does asking in one chat change the length? log2(sequential / independent), per model
    wide = df.pivot_table(index=["model_key", "qid"], columns="condition", values="words")
    wide["ratio"] = np.log2(wide["sequential"] / wide["independent"])
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.axhline(0, color=INK_2, linewidth=1)
    for i, qid in enumerate(QIDS):
        r = wide.xs(qid, level="qid").ratio
        ax.scatter(i + rng.uniform(-0.12, 0.12, len(r)), r, s=30, color=COND["sequential"], alpha=0.75,
                   edgecolor=SURFACE, linewidth=1)
        ax.hlines(r.median(), i - 0.2, i + 0.2, color=INK, linewidth=2)
        for key in (r.idxmax(), r.idxmin()):
            if abs(r[key]) >= 0.5:
                ax.annotate(key, (i + 0.14, r[key]), fontsize=7, color=INK_2, va="center")
    ticks = [-2, -1, 0, 1, 2]
    ax.set_yticks(ticks, ["¼×", "½×", "same", "2×", "4×"])
    lim = max(2.2, np.nanmax(np.abs(wide.ratio)) + 0.2)
    ax.set_ylim(-lim, lim)
    ax.set_xticks(range(4), [f"{q}\n{SHORT[q]}" for q in QIDS], fontsize=9)
    ax.tick_params(axis="x", colors=INK)
    ax.grid(axis="x", visible=False)
    ax.set_xlim(-0.5, 3.9)
    ax.set_ylabel("Sequential length ÷ independent length")
    ax.set_title("Asked in one chat vs separately (one dot per model, bar = median)", pad=10)
    fig.tight_layout()
    fig.savefig(out / "lengths_seq_vs_ind.png", dpi=160)

    # numbers to read alongside the plots
    print("Mean words per answer by group and condition:")
    print(df.pivot_table(index="group", columns="condition", values="words").round(0).reindex(GROUPS).dropna(how="all").to_string())
    print("\nMedian words by question and condition:")
    print(df.pivot_table(index="qid", columns="condition", values="words", aggfunc="median").to_string())
    print("\nMedian sequential/independent ratio by question:")
    print(wide.groupby(level="qid").ratio.median().rpow(2).round(2).to_string())
    print(f"\nWrote {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
