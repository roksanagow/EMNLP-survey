"""The labelling server: serves the answers and writes labels.csv (no models needed)."""
import csv
import json
import threading
import urllib.error
import urllib.request

import pytest

import label

TURNS = [{"qid": q, "question": f"question {q}", "answer": f"answer {q}", "reasoning": None,
          "reasoning_format": "none", "reasoning_unterminated": False, "finish_reason": "stop",
          "n_output_tokens": 5, "seconds": 1.0} for q in ("Q1", "Q2", "Q3", "Q4")]


@pytest.fixture
def server(tmp_path):
    run = tmp_path / "main"
    for cond in ("sequential", "independent"):
        (run / "m1").mkdir(parents=True, exist_ok=True)
        (run / "m1" / f"{cond}.json").write_text(json.dumps(
            {"status": "complete", "model_key": "m1", "condition": cond, "hf_id": "org/m1",
             "sampling": {"do_sample": False}, "turns": TURNS}))
    cfg = tmp_path / "models.yaml"
    cfg.write_text("models:\n  - {key: m1, hf_id: org/m1}\n  - {key: m2, hf_id: org/m2}\n")
    apps = tmp_path / "app_models.yaml"
    apps.write_text("models:\n  - {key: c1, name: C1, lab: L, weights: closed, app: chat.example, tier: core}\n")
    srv = label.make_server(run, 0, cfg, apps)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}", run
    srv.shutdown()
    srv.server_close()


def post(url, item, ctype="application/json"):
    req = urllib.request.Request(url + "/api/label", data=json.dumps(item).encode(), method="POST",
                                 headers={"Content-Type": ctype})
    return json.load(urllib.request.urlopen(req))


def test_data_lists_answers_and_models_without_output(server):
    url, _ = server
    d = json.load(urllib.request.urlopen(url + "/api/data"))
    assert len(d["answers"]) == 8
    assert [(m["key"], m["group"]) for m in d["models"]] == [
        ("m1", label.GROUPS[0]), ("m2", label.GROUPS[0]), ("c1", label.GROUPS[2])]
    assert d["models"][1]["status"] == {}
    assert d["codebook"]["Q1"][0] == "yes" and d["codebook"]["Q4"] is None
    assert "<title>" in urllib.request.urlopen(url + "/").read().decode()


def test_labels_are_saved_validated_and_cleared(server):
    url, run = server
    base = {"model_key": "m1", "condition": "sequential", "notes": "", "answer_sha": label.answer_sha("answer Q1")}
    assert post(url, {**base, "qid": "Q1", "code": "no", "notes": "skims it"})["code"] == "no"
    post(url, {**base, "qid": "Q4", "code": "subjective experience; self-awareness"})
    rows = list(csv.DictReader((run / "labels.csv").open()))
    assert [(r["qid"], r["code"], r["notes"]) for r in rows] == [
        ("Q1", "no", "skims it"), ("Q4", "subjective experience; self-awareness", "")]
    assert rows[0]["answer_sha"] == base["answer_sha"] and rows[0]["labelled_at"]

    for bad, ctype in [({**base, "qid": "Q1", "code": "definitely"}, "application/json"),
                       ({**base, "qid": "Q9", "code": ""}, "application/json"),
                       ({**base, "qid": "Q1", "code": "yes"}, "text/plain")]:
        with pytest.raises(urllib.error.HTTPError):
            post(url, bad, ctype)

    assert post(url, {**base, "qid": "Q1", "code": ""}) is None  # no code and no notes: row removed
    labels = json.load(urllib.request.urlopen(url + "/api/data"))["labels"]
    assert list(labels) == ["m1|sequential|Q4"]
