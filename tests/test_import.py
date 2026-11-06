"""Chat-app transcripts -> the same JSON as the GPU runs (no models needed)."""
import json

import collect
import import_transcripts
import label
from llm_survey.config import load_questions

QUESTIONS = load_questions()
APPS = ("models:\n"
        "  - {key: big-open, name: Big Open, lab: L1, weights: open, app: chat.one, tier: core}\n"
        "  - {key: closed-1, name: Closed One, lab: L2, weights: closed, app: chat.two, tier: core}\n")


def _args(tmp_path, *extra):
    return ["--transcripts", str(tmp_path / "transcripts"), "--out-root", str(tmp_path / "out"),
            "--run-name", "t", "--app-models", str(tmp_path / "app_models.yaml"), *extra]


def _fill(path, answers, settings="2026-10-31"):
    """Paste answers under each question's answer marker, as a person would."""
    text = path.read_text().replace("date:  ", f"date: {settings}  ", 1)
    for q in QUESTIONS:
        if q.id not in answers:
            continue
        reply, thinking = answers[q.id]
        block_start = text.index(f"<!-- {q.id} -->")
        a = text.index("<!-- answer", block_start)
        a = text.index("\n", a) + 1
        text = text[:a] + reply + "\n" + text[a:]
        if thinking:
            r = text.index("<!-- reasoning", a)
            r = text.index("\n", r) + 1
            text = text[:r] + thinking + "\n" + text[r:]
    path.write_text(text)


def test_templates_import_and_read_back(tmp_path, capsys):
    (tmp_path / "app_models.yaml").write_text(APPS)
    assert import_transcripts.main(_args(tmp_path, "--new", "big-open", "closed-1")) == 0
    seq = tmp_path / "transcripts" / "big-open" / "sequential.md"
    assert all(q.text in seq.read_text() for q in QUESTIONS)
    seq.write_text(seq.read_text() + "\n")  # templates are never overwritten
    import_transcripts.main(_args(tmp_path, "--new", "big-open"))
    assert seq.read_text().endswith("\n\n")

    # answers can hold their own Markdown headings and rules
    _fill(seq, {q.id: (f"### Heading\nAnswer to {q.id}\n\n---\nmore", "thought about it" if q.id == "Q3" else "")
                for q in QUESTIONS})
    _fill(tmp_path / "transcripts" / "closed-1" / "independent.md", {"Q1": ("Only Q1", "")})
    assert import_transcripts.main(_args(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "big-open/sequential: complete" in out and "closed-1/independent: partial, 1 of 4 answers" in out
    assert "settings not filled in: plan" in out

    rec = json.loads((tmp_path / "out" / "t" / "big-open" / "sequential.json").read_text())
    assert rec["status"] == "complete" and rec["source"] == "chat_app" and rec["weights"] == "open"
    assert rec["app_settings"]["date"] == "2026-10-31"
    t1, t3 = rec["turns"][0], rec["turns"][2]
    assert t1["answer"] == "### Heading\nAnswer to Q1\n\n---\nmore" and t1["reasoning"] is None
    assert t3["reasoning"] == "thought about it" and t3["reasoning_format"] == "app_summary"
    assert not (tmp_path / "out" / "t" / "big-open" / "independent.json").exists()  # nothing pasted yet

    (tmp_path / "models.yaml").write_text("models: []\n")
    models, answers = label.load_run(tmp_path / "out" / "t", tmp_path / "models.yaml", tmp_path / "app_models.yaml")
    assert [(m["key"], m["group"]) for m in models] == [("big-open", label.GROUPS[1]), ("closed-1", label.GROUPS[2])]
    assert len(answers) == 5 and answers[0]["n_output_tokens"] is None
    df = collect.load_run(tmp_path / "out" / "t")
    assert set(zip(df.model_key, df.weights, df.source)) == {("big-open", "open", "chat_app"),
                                                             ("closed-1", "closed", "chat_app")}


def test_never_overwrites_a_gpu_run(tmp_path, capsys):
    (tmp_path / "app_models.yaml").write_text(APPS)
    import_transcripts.main(_args(tmp_path, "--new", "big-open"))
    _fill(tmp_path / "transcripts" / "big-open" / "sequential.md", {"Q1": ("An answer", "")})
    gpu = tmp_path / "out" / "t" / "big-open" / "sequential.json"
    gpu.parent.mkdir(parents=True)
    gpu.write_text(json.dumps({"status": "complete", "turns": []}))
    assert import_transcripts.main(_args(tmp_path)) == 1
    assert "holds a GPU run" in capsys.readouterr().out
    assert json.loads(gpu.read_text()) == {"status": "complete", "turns": []}
    assert import_transcripts.main(_args(tmp_path, "--new", "nope")) == 1
