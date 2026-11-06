#!/usr/bin/env python
"""Human and LLM answers as points in a rotatable 3D space (one axis per question), as an HTML page.

  python scripts/plot_answers_3d.py --human ~/Downloads/EMNLP_survey_responses.csv

Each question becomes an ordinal scale:
  Q1 reads AI code       no < ~50% < yes
  Q2 AI for emotions     no < yes
  Q3 AI could be conscious  no < maybe < yes, in the future < yes
Answers off those scales ("I don't code", "idc", "-", blank) and the Opening session's tally-only
responses can't be placed, so they are left out and counted in the page's notes.

Humans are coloured by session; LLM answers (outputs/<run>/labels.csv) are diamonds, coloured by
open/closed weights or by condition. Writes outputs/<run>/plots/answers_3d.html (Plotly from a CDN).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect  # noqa: E402

Q1 = {"no": 0, "~50%": 1, "yes": 2}
Q2 = {"no": 0, "yes": 1}
Q3 = {"no": 0, "maybe": 1, "yes in the future": 2, "yes": 3}


def load_humans(path: Path):
    people, skipped = [], Counter()
    with path.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["ID"] == ".":
                skipped["recorded only as tallies"] += sum(int(float(r[k])) for k in r if k.startswith("Code: ") and r[k])
                continue
            a = {"q1": r["Code"].strip(), "q2": r["Therapy"].strip(), "q3": r["Conscious"].strip()}
            if a["q1"] in Q1 and a["q2"] in Q2 and a["q3"] in Q3:
                people.append({"group": r["Session name"], "id": f'{r["Session name"]} {r["ID"]}', **a})
            else:
                reason = ("doesn't code" if a["q1"] == "I don't code" else
                          "Q3 'don't care' or blank" if a["q3"] not in Q3 else
                          "Q2 '–' or blank" if a["q2"] not in Q2 else "Q1 blank")
                skipped[reason] += 1
    return people, skipped


def load_llms(run_dir: Path):
    df = collect.load_run(run_dir)
    weights = {r.model_key: r.weights for r in df.itertuples()}
    codes = {}
    with (run_dir / "labels.csv").open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            codes.setdefault((r["model_key"], r["condition"]), {})[r["qid"]] = r["code"]
    out, skipped = [], 0
    for (model, cond), c in sorted(codes.items()):
        a = {"q1": c.get("Q1"), "q2": c.get("Q2"), "q3": c.get("Q3")}
        if a["q1"] in Q1 and a["q2"] in Q2 and a["q3"] in Q3:
            out.append({"model": model, "weights": weights.get(model, "open"), "condition": cond, **a})
        else:
            skipped += 1
    return out, skipped


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--human", required=True, help="the survey responses CSV (Session name, ID, Code, Therapy, Conscious)")
    p.add_argument("--run-name", default="main")
    p.add_argument("--out-root", default=str(collect.REPO_ROOT / "outputs"))
    args = p.parse_args(argv)

    run_dir = Path(args.out_root) / args.run_name
    humans, h_skipped = load_humans(Path(args.human).expanduser())
    llms, l_skipped = load_llms(run_dir)
    data = {"humans": humans, "humanSkipped": dict(h_skipped), "llms": llms, "llmSkipped": l_skipped,
            "llmModels": len({r["model"] for r in llms})}
    out = run_dir / "plots" / "answers_3d.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(PAGE.replace("/*DATA*/null", json.dumps(data, ensure_ascii=False)), encoding="utf-8")
    sessions = Counter(h["group"] for h in humans)
    print(f"Wrote {out}: {len(humans)} people ({dict(sessions)}), skipped {dict(h_skipped)}; "
          f"{len(llms)} LLM answers from {data['llmModels']} models")
    return 0


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Survey Answer Space</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400&display=swap">
<style>
/* Layout: title and controls above one large rotatable 3D plot; scale and exclusion notes below.
   One deliberate look: black, with bright points that glow, in either OS theme. */
:root {
  --bg: #000000; --surface: #000000; --fg: #f2f2f0; --muted: #9b9a94; --border: #262624; --grid: #2a2a28;
  --axis: #4a4a46; --hover: #111110; --accent: #4ea1ff;
  --opening: #a597ff; --industry: #2fd8a0; --breaks: #ffc233;
  --llm-a: #4ea1ff; --llm-b: #ff5c8d;
  --font-sans: "Geist", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "Geist Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  color-scheme: dark;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 14px/1.5 var(--font-sans); }
.page { max-width: 1100px; margin: 0 auto; padding-block: 28px 48px;
        padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
        display: grid; gap: 18px; }
h1 { margin: 0; font-size: 22px; font-weight: 600; letter-spacing: -0.01em; text-wrap: balance; }
.sub { margin: 4px 0 0; color: var(--muted); max-width: 75ch; }
.controls { display: flex; flex-wrap: wrap; gap: 10px 28px; align-items: center; }
.ctl { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.ctl > span { color: var(--muted); font-size: 13px; }
.switch { display: flex; align-items: center; gap: 8px; cursor: pointer; font-weight: 500; }
.switch input { width: 16px; height: 16px; accent-color: var(--accent); margin: 0; }
.seg { display: inline-flex; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: var(--surface); }
.seg input { position: absolute; opacity: 0; pointer-events: none; }
.seg label { padding: 5px 12px; font-size: 13px; cursor: pointer; color: var(--muted); border-left: 1px solid var(--border); }
.seg label:first-of-type { border-left: 0; }
.seg input:checked + label { background: var(--fg); color: var(--bg); }
.seg input:focus-visible + label { outline: 2px solid var(--accent); outline-offset: -2px; }
.seg.off { opacity: 0.45; pointer-events: none; }
.plot-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
#plot { width: 100%; height: min(78vh, 760px); min-height: 460px; }
.notes { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px 32px; font-size: 13px; color: var(--muted); }
.notes h2 { margin: 0 0 4px; font-size: 13px; font-weight: 600; color: var(--fg); }
.notes p, .notes ul { margin: 0; }
.notes ul { padding-left: 18px; }
.notes b { color: var(--fg); font-weight: 500; }
.mono { font-family: var(--font-mono); font-size: 12px; }
</style>
</head>
<body>
<div class="page">
  <header>
    <h1>Survey answer space</h1>
    <p class="sub">Each axis is one question as a graded scale. Dot size is the number of respondents with exactly that set of answers. Drag to rotate, scroll to zoom, hover a dot for its answers, and click a legend entry to hide that group.</p>
  </header>

  <div class="controls">
    <label class="switch"><input type="checkbox" id="show-llm" checked> Show LLM answers</label>
    <div class="ctl">
      <span>Colour LLMs by</span>
      <div class="seg" id="llm-colour">
        <input type="radio" name="llm-colour" id="by-weights" value="weights" checked><label for="by-weights">Open / closed weights</label>
        <input type="radio" name="llm-colour" id="by-condition" value="condition"><label for="by-condition">Sequential / independent</label>
      </div>
    </div>
    <div class="ctl">
      <span>Overlapping answers</span>
      <div class="seg" id="mode">
        <input type="radio" name="mode" id="mode-size" value="size" checked><label for="mode-size">Size by count</label>
        <input type="radio" name="mode" id="mode-jitter" value="jitter"><label for="mode-jitter">One dot each, jittered</label>
      </div>
    </div>
  </div>

  <div class="plot-card"><div id="plot" role="img" aria-label="3D scatter of survey answers"></div></div>

  <section class="notes">
    <div>
      <h2>Scales</h2>
      <ul>
        <li><b>Reads AI code:</b> no → ~50% → yes</li>
        <li><b>AI for emotional issues:</b> no → yes</li>
        <li><b>AI could be conscious:</b> no → maybe → yes, in the future → yes</li>
      </ul>
    </div>
    <div>
      <h2>Who is plotted</h2>
      <p id="who"></p>
    </div>
    <div>
      <h2>Reading it</h2>
      <p>Humans are circles, LLMs are diamonds. Where several groups share the same answers, each group's dot is shifted slightly, always in the same direction, so none hides another. Humans were asked whether they <i>have</i> used AI for emotional issues; LLMs were asked whether, as a human, they <i>would</i>. Each LLM answered twice (sequential and independent), so it can appear as two answers.</p>
    </div>
  </section>
</div>

<script src="https://cdn.jsdelivr.net/npm/plotly.js-gl3d-dist-min@2.35.2/plotly-gl3d.min.js"></script>
<script>
const DATA = /*DATA*/null;
const Q1 = { "no": 0, "~50%": 1, "yes": 2 }, Q2 = { "no": 0, "yes": 1 };
const Q3 = { "no": 0, "maybe": 1, "yes in the future": 2, "yes": 3 };
const LABEL = { q1: { "no": "No", "~50%": "~50%", "yes": "Yes" }, q2: { "no": "No", "yes": "Yes" },
                q3: { "no": "No", "maybe": "Maybe", "yes in the future": "Yes, in the future", "yes": "Yes" } };
const HUMAN_GROUPS = ["Opening", "Industry", "Breaks"];
const LLM_GROUPS = {
  weights: [["open", "LLM · open weights"], ["closed", "LLM · closed weights"]],
  condition: [["sequential", "LLM · sequential chat"], ["independent", "LLM · independent chats"]],
};
// Fixed dodge directions in the Q1-Q2 plane: one per group, so toggling groups never moves the others.
const SLOT = { Opening: 90, Industry: 162, Breaks: 234, llmA: 306, llmB: 18 };
const R = 0.17;

const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const state = { showLlm: true, llmColour: "weights", mode: "size" };

function rng(seed) {   // mulberry32: same jitter on every redraw
  return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
                 t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}

function trace(name, rows, slot, colour, symbol, describe, seed) {
  const a = SLOT[slot] * Math.PI / 180, dx = R * Math.cos(a), dy = R * Math.sin(a) * 0.75;
  const base = r => [Q1[r.q1] + dx, Q2[r.q2] + dy, Q3[r.q3]];
  const answers = r => `Reads AI code: ${LABEL.q1[r.q1]}<br>AI for emotional issues: ${LABEL.q2[r.q2]}<br>AI could be conscious: ${LABEL.q3[r.q3]}`;
  let x = [], y = [], z = [], size = [], text = [];
  if (state.mode === "size") {
    const cells = new Map();
    for (const r of rows) {
      const k = `${r.q1}|${r.q2}|${r.q3}`;
      if (!cells.has(k)) cells.set(k, []);
      cells.get(k).push(r);
    }
    for (const members of cells.values()) {
      const [px, py, pz] = base(members[0]);
      x.push(px); y.push(py); z.push(pz);
      size.push(7 + 6.5 * Math.sqrt(members.length));
      text.push(`<b>${name}</b> · ${describe(members)}<br>${answers(members[0])}`);
    }
  } else {
    const rand = rng(seed);
    for (const r of rows) {
      const [px, py, pz] = base(r);
      x.push(px + (rand() - 0.5) * 0.22); y.push(py + (rand() - 0.5) * 0.22); z.push(pz + (rand() - 0.5) * 0.22);
      size.push(7);
      text.push(`<b>${name}</b> · ${describe([r])}<br>${answers(r)}`);
    }
  }
  // Glow: two larger, faint copies drawn underneath, in the same legend group so they hide together.
  const halo = (scale, opacity) => ({
    type: "scatter3d", mode: "markers", name, legendgroup: name, showlegend: false, hoverinfo: "skip", x, y, z,
    marker: { size: size.map(s => s * scale), color: colour, symbol: "circle", opacity, line: { width: 0 } },
  });
  return [halo(2.4, 0.1), halo(1.6, 0.22), {
    type: "scatter3d", mode: "markers", name, legendgroup: name, x, y, z, text, hovertemplate: "%{text}<extra></extra>",
    marker: { size, color: colour, symbol, opacity: 1, line: { color: css("--bg"), width: 0.5 } },
  }];
}

function describePeople(ms) { return ms.length === 1 ? "1 person" : `${ms.length} people`; }
function describeLlms(ms) {
  if (ms.length === 1) return `${ms[0].model} (${ms[0].condition})`;
  const by = new Map();
  for (const m of ms) by.set(m.model, [...(by.get(m.model) || []), m.condition.slice(0, 3)]);
  return `${ms.length} answers<br>` + [...by].map(([k, c]) => `${k} (${c.join(", ")})`).join("<br>");
}

function axis(title, vals, labels, range) {
  return { title: { text: title, font: { size: 13, color: css("--fg") } }, tickvals: vals, ticktext: labels, range,
           tickfont: { size: 11, color: css("--muted") }, gridcolor: css("--grid"), zeroline: false,
           showline: true, linecolor: css("--axis"), showbackground: false, showspikes: false };
}

function draw() {
  const traces = HUMAN_GROUPS.flatMap((g, i) => trace(g, DATA.humans.filter(h => h.group === g), g,
    css("--" + g.toLowerCase()), "circle", describePeople, 11 + i));
  if (state.showLlm) {
    LLM_GROUPS[state.llmColour].forEach(([key, name], i) => {
      const rows = DATA.llms.filter(r => (state.llmColour === "weights" ? r.weights : r.condition) === key);
      traces.push(...trace(name, rows, i ? "llmB" : "llmA", css(i ? "--llm-b" : "--llm-a"), "diamond", describeLlms, 31 + i));
    });
  }
  const layout = {
    uirevision: "keep",
    paper_bgcolor: css("--surface"), plot_bgcolor: css("--surface"),
    font: { family: css("--font-sans"), color: css("--fg") },
    margin: { l: 0, r: 0, t: 10, b: 0 },
    legend: { orientation: "h", x: 0.02, y: 0.99, font: { size: 12 }, itemsizing: "constant", bgcolor: "rgba(0,0,0,0)" },
    hoverlabel: { bgcolor: css("--hover"), bordercolor: css("--axis"), font: { color: css("--fg"), size: 12 } },
    scene: {
      xaxis: axis("Reads AI code", [0, 1, 2], ["No", "~50%", "Yes"], [-0.5, 2.5]),
      yaxis: axis("AI for emotional issues", [0, 1], ["No", "Yes"], [-0.5, 1.5]),
      zaxis: axis("AI could be conscious", [0, 1, 2, 3], ["No", "Maybe", "Yes, future", "Yes"], [-0.5, 3.5]),
      aspectmode: "manual", aspectratio: { x: 1.1, y: 0.8, z: 1.1 },
      camera: { eye: { x: 1.55, y: -1.55, z: 0.95 } },
    },
  };
  Plotly.react("plot", traces, layout, { responsive: true, displaylogo: false,
    modeBarButtonsToRemove: ["resetCameraLastSave3d"], toImageButtonOptions: { filename: "survey-answer-space", scale: 2 } });
  document.getElementById("llm-colour").classList.toggle("off", !state.showLlm);
}

function notes() {
  const n = g => DATA.humans.filter(h => h.group === g).length;
  const skipped = Object.entries(DATA.humanSkipped).map(([k, v]) => `${v} ${k}`).join(", ");
  document.getElementById("who").innerHTML =
    `<b>${DATA.humans.length} people</b> who answered all three questions on the scales ` +
    `(Opening ${n("Opening")}, Industry ${n("Industry")}, Breaks ${n("Breaks")}). Left out: ${skipped || "none"}. ` +
    `<b>${DATA.llms.length} LLM answers</b> from ${DATA.llmModels} models, two per model` +
    (DATA.llmSkipped ? ` (${DATA.llmSkipped} without labels left out).` : ".");
}

if (window.Plotly) {
  notes();
  draw();
  document.getElementById("show-llm").addEventListener("change", e => { state.showLlm = e.target.checked; draw(); });
  document.querySelectorAll("input[name=llm-colour]").forEach(el => el.addEventListener("change", e => { state.llmColour = e.target.value; draw(); }));
  document.querySelectorAll("input[name=mode]").forEach(el => el.addEventListener("change", e => { state.mode = e.target.value; draw(); }));
} else {
  notes();
  document.getElementById("plot").innerHTML = '<p style="padding:24px">The plotting library didn\'t load; this page needs an internet connection.</p>';
}
</script>
</body>
</html>
"""

if __name__ == "__main__":
    sys.exit(main())
