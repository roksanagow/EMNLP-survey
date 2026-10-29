"""End-to-end checks on tiny random models (CPU, offline)."""
import json
from pathlib import Path

import pandas as pd
import pytest
import torch
from openpyxl import load_workbook

import collect
import run_model
import unblind
from llm_survey.config import load_models, load_questions
from llm_survey.engine import ChatEngine
from llm_survey.runner import run_independent, run_sequential

QUESTIONS = load_questions()


def _run(tiny, out, key, path):
    rc = run_model.main(["--model", key, "--model-path", path, "--models-config", tiny["models_config"],
                         "--out-root", str(out), "--run-name", "t"])
    assert rc == 0
    return {c: json.loads((out / "t" / key / f"{c}.json").read_text()) for c in ("sequential", "independent")}


def test_text_model_end_to_end(tiny, tmp_path):
    recs = _run(tiny, tmp_path, "tiny-text", tiny["text"])
    for cond, rec in recs.items():
        assert rec["status"] == "complete"
        assert [t["qid"] for t in rec["turns"]] == ["Q1", "Q2", "Q3", "Q4"]
        assert rec["sampling"]["do_sample"] is True
        assert rec["sampling"]["temperature"] == pytest.approx(0.7)
        assert rec["sampling"]["top_k"] == 20
        assert rec["chat_template_kwargs"] == {} and rec["system_prompt_added"] is None
        assert (tmp_path / "t" / "tiny-text" / f"{cond}.md").exists()
    seq, ind = recs["sequential"]["turns"], recs["independent"]["turns"]
    # sequential: the chat grows turn by turn; independent: every chat holds one question
    for i, t in enumerate(seq):
        assert t["n_prompt_tokens"] > (seq[i - 1]["n_prompt_tokens"] if i else 0)
    for t in ind:
        assert t["rendered_prompt"].count("<|im_start|>") == 2  # one user turn + generation prompt
    assert seq[3]["rendered_prompt"].count("<|im_start|>") == 8  # 4 user + 3 assistant + generation prompt
    # Q1 is asked identically (same prompt, same seed) in both conditions
    assert seq[0]["rendered_prompt"] == ind[0]["rendered_prompt"]
    assert seq[0]["raw_output"] == ind[0]["raw_output"]


def test_generate_passes_only_max_new_tokens(tiny):
    spec = load_models(tiny["models_config"])["tiny-text"]
    eng = ChatEngine(spec, model_path=tiny["text"], max_new_tokens=5)
    seen = {}
    real = eng.model.generate

    def spy(**kw):
        seen.update(kw)
        return real(**kw)

    eng.model.generate = spy
    eng.generate([eng.message("user", "hello")])
    assert set(seen) - {"input_ids", "attention_mask"} == {"max_new_tokens"}


def _fixed_output(eng, text):
    ids = eng.tokenizer(text, add_special_tokens=False, return_tensors="pt")["input_ids"]

    def fake_generate(input_ids, **kw):
        return torch.cat([input_ids, ids.to(input_ids.device)], dim=1)

    eng.model.generate = fake_generate


def test_answer_not_reasoning_goes_back_into_history(tiny):
    spec = load_models(tiny["models_config"])["tiny-text"]
    eng = ChatEngine(spec, model_path=tiny["text"])
    _fixed_output(eng, "maybe not sure </think> yes i would <|im_end|>")
    turns = []
    messages = run_sequential(eng, QUESTIONS[:2], seed=1, on_turn=turns.append)
    assert turns[0]["reasoning"] == "maybe not sure"
    assert turns[0]["answer"] == "yes i would"
    assert turns[0]["reasoning_format"] == "think" and turns[0]["finish_reason"] == "stop"
    assert messages[1] == {"role": "assistant", "content": "yes i would"}
    assert "yes i would" in turns[1]["rendered_prompt"] and "maybe not sure" not in turns[1]["rendered_prompt"]


def test_truncated_reasoning_is_flagged(tiny):
    spec = load_models(tiny["models_config"])["tiny-text"]
    eng = ChatEngine(spec, model_path=tiny["text"], max_new_tokens=3)
    _fixed_output(eng, "maybe not sure")
    turns = []
    run_independent(eng, QUESTIONS[:1], seed=1, on_turn=turns.append)
    t = turns[0]
    assert t["finish_reason"] == "length" and t["answer"] == "" and t["reasoning_unterminated"]


def test_multimodal_loader_text_only(tiny, tmp_path):
    recs = _run(tiny, tmp_path, "tiny-mm", tiny["mm"])
    rec = recs["sequential"]
    assert rec["status"] == "complete" and len(rec["turns"]) == 4
    assert rec["messages"][0]["content"] == [{"type": "text", "text": QUESTIONS[0].text}]
    assert rec["model_class"] == "LlavaForConditionalGeneration"


def test_smoke_mode(tiny, tmp_path):
    rc = run_model.main(["--model", "tiny-text", "--model-path", tiny["text"], "--models-config", tiny["models_config"],
                         "--out-root", str(tmp_path), "--smoke"])
    assert rc == 0
    rec = json.loads((tmp_path / "smoke" / "tiny-text" / "sequential.json").read_text())
    assert [t["qid"] for t in rec["turns"]] == ["Q1"] and rec["max_new_tokens"] == 64


def test_refuses_to_overwrite_complete_run(tiny, tmp_path):
    _run(tiny, tmp_path, "tiny-text", tiny["text"])
    with pytest.raises(FileExistsError):
        _run(tiny, tmp_path, "tiny-text", tiny["text"])


def test_collect_and_unblind(tiny, tmp_path):
    _run(tiny, tmp_path, "tiny-text", tiny["text"])
    _run(tiny, tmp_path, "tiny-mm", tiny["mm"])
    assert collect.main(["--run-name", "t", "--out-root", str(tmp_path)]) == 0
    run_dir = tmp_path / "t"
    long = pd.read_csv(run_dir / "answers_long.csv")
    assert len(long) == 2 * 2 * 4
    wb = load_workbook(run_dir / "coding_workbook.xlsx")
    assert wb.sheetnames == ["Blind coding", "All answers", "Codebook"]
    ws = wb["Blind coding"]
    header = [c.value for c in ws[1]]
    assert "model_key" not in header and "condition" not in header
    qids = [ws.cell(r, 2).value for r in range(2, ws.max_row + 1)]
    assert qids == sorted(qids)  # grouped by question
    for r in range(2, ws.max_row + 1):
        ws.cell(r, 5).value = "no"
    wb.save(run_dir / "coding_workbook.xlsx")
    assert unblind.main(["--run-name", "t", "--out-root", str(tmp_path)]) == 0
    coded = pd.read_csv(run_dir / "coded_answers.csv")
    assert len(coded) == 16 and (coded.code == "no").all()
    assert set(coded.model_key) == {"tiny-text", "tiny-mm"}
