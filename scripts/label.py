#!/usr/bin/env python
"""Read the answers in the browser, with model and condition shown, and label each one.

  python scripts/label.py                    # run "main"; opens http://127.0.0.1:8765
  python scripts/label.py --run-name smoke --port 8800 --no-browser

The non-blind alternative to the "Blind coding" sheet from scripts/collect.py, with the same
human-survey categories. Every click is written straight to outputs/<run>/labels.csv (one row
per model, condition and question). After rsyncing new outputs, reload the page.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collect import CODE_HELP, CODEBOOK  # noqa: E402
from llm_survey.config import CONFIG_DIR, REPO_ROOT, load_app_models, load_models, load_questions  # noqa: E402

PAGE = Path(__file__).with_name("label.html")
FIELDS = ["model_key", "condition", "qid", "code", "notes", "answer_sha", "labelled_at"]
CONDITIONS = ("sequential", "independent")
GROUPS = ["Open weights · our GPUs", "Open weights · via an app", "Closed weights · chat app", "Other"]


def answer_sha(text: str | None) -> str:
    """Short hash of an answer, stored with its label so a re-run answer shows up as changed."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:12]


def load_run(run_dir: Path, models_config: Path, app_models_config: Path) -> tuple[list[dict], list[dict]]:
    """Every configured model, grouped as in GROUPS (including ones with no output yet), and every saved answer."""
    def blank(key, **kw):
        return {"key": key, "hf_id": None, "reasoning": None, "sampling": None, "status": {},
                "app": None, "app_settings": {}, "group": GROUPS[-1], **kw}

    models = {k: blank(k, hf_id=s.hf_id, reasoning=s.reasoning, group=GROUPS[0])
              for k, s in load_models(models_config).items() if s.enabled}
    for k, m in load_app_models(app_models_config).items():
        models[k] = blank(k, app=m["app"], group=GROUPS[1] if m["weights"] == "open" else GROUPS[2])
    answers = []
    for path in sorted(run_dir.glob("*/*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        m = models.setdefault(rec["model_key"], blank(rec["model_key"], hf_id=rec.get("hf_id")))
        m["sampling"] = rec.get("sampling")
        m["status"][rec["condition"]] = rec.get("status")
        if rec.get("app_settings"):
            m["app_settings"][rec["condition"]] = rec["app_settings"]
        for t in rec.get("turns", []):
            answers.append({
                "model_key": rec["model_key"],
                "condition": rec["condition"],
                "qid": t["qid"],
                "question": t["question"],
                "answer": t["answer"],
                "reasoning": t.get("reasoning"),
                "reasoning_format": t.get("reasoning_format"),
                "reasoning_unterminated": t.get("reasoning_unterminated"),
                "finish_reason": t["finish_reason"],
                "n_output_tokens": t["n_output_tokens"],
                "seconds": t["seconds"],
                "answer_sha": answer_sha(t["answer"]),
            })
    ordered = sorted(models.values(), key=lambda m: GROUPS.index(m["group"]))  # stable: config order within a group
    return ordered, answers


class Labels:
    """labels.csv, kept in memory and rewritten in full (atomically) on every change."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self.rows: dict[tuple[str, str, str], dict] = {}
        if path.exists():
            with path.open(newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    self.rows[(r["model_key"], r["condition"], r["qid"])] = {k: r.get(k) or "" for k in FIELDS}

    def as_dict(self) -> dict[str, dict]:
        with self.lock:
            return {"|".join(k): dict(r) for k, r in self.rows.items()}

    def set(self, item: dict) -> dict | None:
        key = (item["model_key"], item["condition"], item["qid"])
        with self.lock:
            if item["code"] or item["notes"]:
                self.rows[key] = {**{k: item.get(k, "") for k in FIELDS},
                                  "labelled_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            else:  # both cleared: drop the row rather than keep an empty label
                self.rows.pop(key, None)
            tmp = self.path.with_name(self.path.name + ".tmp")
            with tmp.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, FIELDS)
                w.writeheader()
                w.writerows(self.rows[k] for k in sorted(self.rows))
            os.replace(tmp, self.path)
            return self.rows.get(key)


def parse_label(body: bytes) -> dict:
    item = json.loads(body)
    out = {k: item.get(k) for k in ("model_key", "condition", "qid", "code", "notes", "answer_sha")}
    if not all(isinstance(v, str) for v in out.values()):
        raise ValueError("every field must be a string")
    if out["condition"] not in CONDITIONS or out["qid"] not in CODEBOOK or not out["model_key"]:
        raise ValueError(f"unknown answer {out['model_key']}/{out['condition']}/{out['qid']}")
    out["code"], out["notes"] = out["code"].strip(), out["notes"].strip()
    options = CODEBOOK[out["qid"]]
    if options and out["code"] and out["code"] not in options:
        raise ValueError(f"{out['code']!r} is not a {out['qid']} category: {options}")
    return out


def make_server(run_dir: Path, port: int, models_config: Path = CONFIG_DIR / "models.yaml",
                app_models_config: Path = CONFIG_DIR / "app_models.yaml") -> ThreadingHTTPServer:
    labels = Labels(run_dir / "labels.csv")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                self.reply(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/data":
                # read from disk on every load, so a reload picks up newly rsynced outputs
                models, answers = load_run(run_dir, models_config, app_models_config)
                data = {"run": run_dir.name, "codebook": CODEBOOK, "help": CODE_HELP,
                        "questions": [{"id": q.id, "text": q.text} for q in load_questions()],
                        "models": models, "answers": answers, "labels": labels.as_dict()}
                self.reply(200, json.dumps(data).encode("utf-8"), "application/json")
            else:
                self.reply(404, b"not found", "text/plain")

        def do_POST(self):
            # requiring a JSON content type means another website can't post labels without a CORS preflight
            if self.path != "/api/label" or self.headers.get("Content-Type") != "application/json":
                return self.reply(404, b"not found", "text/plain")
            try:
                item = parse_label(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            except (ValueError, json.JSONDecodeError) as e:
                return self.reply(400, str(e).encode("utf-8"), "text/plain")
            self.reply(200, json.dumps(labels.set(item)).encode("utf-8"), "application/json")

        def reply(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-name", default="main")
    p.add_argument("--out-root", default=str(REPO_ROOT / "outputs"))
    p.add_argument("--models-config", default=str(CONFIG_DIR / "models.yaml"))
    p.add_argument("--app-models", default=str(CONFIG_DIR / "app_models.yaml"))
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    args = p.parse_args(argv)

    run_dir = Path(args.out_root) / args.run_name
    if not any(run_dir.glob("*/*.json")):
        print(f"No answers found under {run_dir}")
        return 1
    try:
        server = make_server(run_dir, args.port, Path(args.models_config), Path(args.app_models))
    except OSError as e:
        print(f"Can't listen on port {args.port} ({e.strerror}); try --port {args.port + 1}")
        return 1
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Labelling {run_dir} at {url}\nLabels go to {run_dir / 'labels.csv'}. Ctrl-C to stop.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
