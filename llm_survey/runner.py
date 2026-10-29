"""The two survey conditions and how results are written to disk."""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Callable

from .config import Question, questions_sha256

CONDITIONS = ("sequential", "independent")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def set_seed(seed: int) -> None:
    from transformers import set_seed as hf_set_seed

    hf_set_seed(seed)


def _turn(qid: str, question: str, reply, chat_index: int) -> dict:
    return {"qid": qid, "question": question, "chat_index": chat_index, **reply.to_dict()}


def run_sequential(engine, questions: list[Question], seed: int, on_turn: Callable[[dict], None]) -> list[dict]:
    """All questions in one chat, in order; each answer is fed back as the assistant turn."""
    set_seed(seed)
    messages: list[dict] = []
    for q in questions:
        messages.append(engine.message("user", q.text))
        reply = engine.generate(messages)
        messages.append(engine.message("assistant", reply.answer))
        on_turn(_turn(q.id, q.text, reply, chat_index=0))
    return messages


def run_independent(engine, questions: list[Question], seed: int, on_turn: Callable[[dict], None]) -> list[list[dict]]:
    """Each question in its own fresh chat (same seed for every chat)."""
    chats = []
    for i, q in enumerate(questions):
        set_seed(seed)
        messages = [engine.message("user", q.text)]
        reply = engine.generate(messages)
        messages.append(engine.message("assistant", reply.answer))
        on_turn(_turn(q.id, q.text, reply, chat_index=i))
        chats.append(messages)
    return chats


class ResultWriter:
    """Writes outputs/<run>/<model>/<condition>.json (updated after every answer) and a .md transcript."""

    def __init__(self, out_dir: Path, model_key: str, condition: str, meta: dict, questions: list[Question],
                 seed: int, overwrite: bool = False):
        self.dir = Path(out_dir) / model_key
        self.dir.mkdir(parents=True, exist_ok=True)
        self.json_path = self.dir / f"{condition}.json"
        self.md_path = self.dir / f"{condition}.md"
        if self.json_path.exists() and not overwrite:
            existing = json.loads(self.json_path.read_text())
            if existing.get("status") == "complete":
                raise FileExistsError(f"{self.json_path} is complete; use --overwrite or a new --run-name")
        self.record = {
            "status": "running",
            "model_key": model_key,
            "condition": condition,
            "seed": seed,
            "started": now(),
            "finished": None,
            "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
            "questions_sha256": questions_sha256(questions),
            "questions": [{"id": q.id, "text": q.text} for q in questions],
            **meta,
            "turns": [],
            "messages": None,
        }
        self.flush()

    def add_turn(self, turn: dict) -> None:
        self.record["turns"].append(turn)
        self.flush()

    def finish(self, messages) -> None:
        self.record["messages"] = messages
        self.record["status"] = "complete"
        self.record["finished"] = now()
        self.flush()

    def flush(self) -> None:
        tmp = self.json_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.record, indent=2, ensure_ascii=False))
        tmp.replace(self.json_path)
        self.md_path.write_text(render_markdown(self.record))


def render_markdown(rec: dict) -> str:
    lines = [
        f"# {rec['model_key']} — {rec['condition']}",
        "",
        f"- Model: `{rec.get('hf_id')}` @ `{rec.get('revision_resolved') or rec.get('revision_requested') or 'unpinned'}`",
        f"- Status: {rec['status']} (started {rec['started']}, finished {rec['finished']})",
        f"- Seed: {rec['seed']}; max_new_tokens: {rec.get('max_new_tokens')}",
        f"- Sampling (from generation_config.json): `{json.dumps(rec.get('sampling'))}`",
        "",
    ]
    if rec["condition"] == "sequential":
        lines.append("All questions asked in one chat, in order.\n")
    else:
        lines.append("Each question asked in a fresh chat.\n")
    for t in rec["turns"]:
        lines += [f"## {t['qid']}: {t['question']}", ""]
        flags = []
        if t["finish_reason"] == "length":
            flags.append("hit max_new_tokens")
        if t["reasoning_unterminated"]:
            flags.append("reasoning not closed")
        if flags:
            lines += [f"> ⚠ {'; '.join(flags)}", ""]
        lines += [t["answer"] or "_(empty answer)_", ""]
        if t.get("reasoning"):
            lines += [
                f"<details><summary>Reasoning ({len(t['reasoning'])} chars, format: {t['reasoning_format']})</summary>",
                "",
                t["reasoning"],
                "",
                "</details>",
                "",
            ]
        lines += [f"_{t['n_output_tokens']} tokens, {t['seconds']} s_", ""]
    return "\n".join(lines)
