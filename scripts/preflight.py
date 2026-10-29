#!/usr/bin/env python
"""Check each model as far as possible without GPUs or weights (runs on a laptop).

Downloads only each repo's small files (config, tokenizer, chat template, generation
config, weight index: a few MB per model) into the Hugging Face cache, then per model:
  * loads the tokenizer/processor and builds the model class on the meta device with the
    code the cluster job uses (ChatEngine), so an architecture the installed transformers
    doesn't support fails here rather than on a GPU node;
  * renders both conditions through the chat template (4-turn sequential chat, fresh Q1);
  * checks that a reply in the model's reasoning format splits into reasoning and answer;
  * estimates GPU memory (weights + KV cache for a full-length answer) against the GPUs
    requested in config/models.yaml, for each GPU type in config/cluster.yaml.

  python scripts/preflight.py                        # every enabled model
  python scripts/preflight.py --models gpt-oss-20b --show-prompt
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from llm_survey.config import load_cluster, load_models, load_questions  # noqa: E402
from llm_survey.parsing import _prompt_left_open, split_reasoning  # noqa: E402

SMALL_FILES = ["*.json", "*.jinja", "*.model", "*.txt", "*.tiktoken"]
IGNORE = ["original/*", "metal/*"]

# reasoning format -> (marker that identifies it in the vocabulary, synthetic reply with {r}easoning and {a}nswer)
FORMATS = [
    ("harmony", "<|channel|>", "<|channel|>analysis<|message|>{r}<|end|><|start|>assistant<|channel|>final<|message|>{a}"),
    ("gemma4", "<|channel>", "<|channel>thought\n{r}<channel|>{a}"),
    ("mistral", "[THINK]", "[THINK]{r}[/THINK]{a}"),
    ("think", "<think>", "<think>\n{r}\n</think>\n\n{a}"),
]
OPENERS = {"gemma4": ("<|channel>thought", "<channel|>"), "mistral": ("[THINK]", "[/THINK]"),
           "think": ("<think>", "</think>")}
REASONING, ANSWER = "Weighing both sides first.", "Yes, I would read it."
GPU_OVERHEAD_GB = 1.5   # GiB per GPU for CUDA context, allocator slack and activations
FILL = 0.85             # plan to use at most this share of GPU memory


def detect_format(engine, prompt: str) -> str:
    """Reasoning format from the markers in the vocabulary, chat template or rendered prompt."""
    template = getattr(engine._templater, "chat_template", None) or ""
    if isinstance(template, dict):
        template = "\n".join(template.values())
    try:
        vocab = engine.tokenizer.get_vocab()
    except Exception:  # noqa: BLE001
        vocab = {}
    for name, marker, _ in FORMATS:
        if marker in vocab or marker in template or marker in prompt:
            return name
    return "none"


def check_reasoning(engine, fmt: str, prompt: str) -> str:
    """Round-trip a synthetic reply through the tokenizer and parse it the way a real reply is parsed."""
    if engine.spec.reasoning == "on":
        if fmt == "none":
            raise AssertionError("config says the model reasons, but no known reasoning marker is in its vocabulary")
        text = dict((n, s) for n, _, s in FORMATS)[fmt].format(r=REASONING, a=ANSWER)
        if fmt in OPENERS and _prompt_left_open(prompt, *OPENERS[fmt]):
            text = text.split(OPENERS[fmt][0], 1)[1]   # the template already opened the block
        expected = (fmt, REASONING, ANSWER)
    else:
        text, expected = ANSWER, ("none", None, ANSWER)
    eos = "<|return|>" if fmt == "harmony" else (engine.tokenizer.eos_token or "")
    text += eos
    try:
        ids = engine.tokenizer.encode(text, add_special_tokens=False)
        decoded = engine._decode(ids)
    except Exception:  # noqa: BLE001  (some backends can't encode control tokens from text)
        decoded = text
    p = split_reasoning(decoded, prompt=prompt, special_tokens=engine._specials)
    got = (p.format, p.reasoning, p.answer)
    if engine.spec.reasoning != "on" and p.format == "none" and p.answer == ANSWER:
        return f"{fmt if fmt != 'none' else 'no'} reasoning markers; plain reply parses to the answer"
    if got != expected:
        raise AssertionError(f"synthetic reply {decoded!r} parsed as {got}, expected {expected}")
    opened = " (opened by the template)" if fmt in OPENERS and _prompt_left_open(prompt, *OPENERS[fmt]) else ""
    return f"{fmt}{opened}: synthetic reply splits into reasoning and answer"


def kv_gib(config, tokens: int) -> float:
    """KV cache in GiB (bf16) for `tokens` tokens; only attention layers keep a growing cache."""
    tc = config.get_text_config() if hasattr(config, "get_text_config") else config
    types = getattr(tc, "layer_types", None) or getattr(tc, "layers_block_type", None)
    if not types and getattr(tc, "hybrid_override_pattern", None):   # Nemotron-H: "*" marks attention
        types = ["attention" if c == "*" else "other" for c in tc.hybrid_override_pattern]
    types = types or ["full_attention"] * tc.num_hidden_layers
    per_layer = getattr(tc, "per_layer_config", None)   # Gemma 4: head counts and sizes differ by layer

    def attr(i, name):
        return getattr(per_layer[i] if per_layer is not None else tc, name, None)

    total = 0
    for i, t in enumerate(types):
        if t in ("full_attention", "attention"):
            length = tokens
        elif t == "sliding_attention":
            length = min(attr(i, "sliding_window") or tokens, tokens)
        else:   # linear attention, Mamba, MLP/MoE blocks: fixed-size or no cache
            continue
        heads = attr(i, "num_key_value_heads") or tc.num_attention_heads
        head_dim = attr(i, "head_dim") or tc.hidden_size // tc.num_attention_heads
        total += 2 * heads * head_dim * 2 * length
    return total / 2**30


def memory_lines(engine, cluster) -> tuple[list[str], list[str]]:
    weights = sum(p.numel() * p.element_size() for p in engine.model.parameters()) / 2**30
    n_params = sum(p.numel() for p in engine.model.parameters()) / 1e9
    kv = kv_gib(engine.model.config, engine.max_new_tokens + 4096)
    lines = [f"{n_params:.1f}B params -> {weights:.1f} GiB weights ({engine.spec.dtype}); "
             f"KV cache for {engine.max_new_tokens + 4096} tokens ~{kv:.1f} GiB"]
    problems = []
    for gtype, info in cluster["gpu_types"].items():
        n = int(engine.spec.gpus[gtype])
        mem = float(info["memory_gib"])
        need = weights + kv + GPU_OVERHEAD_GB * n
        share = need / (n * mem)
        fewest = next(k for k in range(1, 9) if weights + kv + GPU_OVERHEAD_GB * k <= FILL * k * mem)
        verdict = "ok" if share <= FILL else ("tight" if share <= 1 else "DOES NOT FIT")
        note = f"; {fewest} would do" if fewest < n else ""
        lines.append(f"{gtype}: {n} x {mem:.0f} GiB, needs ~{need:.0f} GiB ({share:.0%}) {verdict}{note}")
        if share > 1 or fewest > n:
            problems.append(f"{gtype}: requested {n} GPU(s) but needs ~{fewest}")
    return lines, problems


def download_size_gb(snapshot: Path) -> float | None:
    for name in ("model.safetensors.index.json", "consolidated.safetensors.index.json"):
        f = snapshot / name
        if f.exists():
            size = json.loads(f.read_text()).get("metadata", {}).get("total_size")
            if size:
                return size / 1e9
    return None


def check_model(spec, questions, cluster, show_prompt: bool) -> list[str]:
    from huggingface_hub import snapshot_download

    from llm_survey.engine import ChatEngine

    snapshot = Path(snapshot_download(spec.hf_id, revision=spec.revision, allow_patterns=SMALL_FILES,
                                      ignore_patterns=IGNORE))
    print(f"   repo       ok, commit {snapshot.name[:12]}"
          + (f", weights ~{download_size_gb(snapshot):.0f} GB to download" if download_size_gb(snapshot) else ""))

    engine = ChatEngine(spec, model_path=str(snapshot), empty_weights=True)
    tok_name = type(engine.processor or engine.tokenizer).__name__
    print(f"   loader     {spec.loader}: {type(engine.model).__name__} + {tok_name}")
    meta = engine.metadata()
    print(f"   sampling   {meta['sampling']}")
    if not engine._eos_ids:
        raise AssertionError("no end-of-turn token ids: generation would only stop at max_new_tokens")

    # sequential: four questions in one chat with placeholder answers; independent: Q1 alone
    messages = []
    for i, q in enumerate(questions):
        if i:
            messages.append(engine.message("assistant", f"Placeholder answer to {questions[i - 1].id}."))
        messages.append(engine.message("user", q.text))
    seq_prompt = engine._decode(engine.encode(messages)["input_ids"][0])
    ind_ids = engine.encode([engine.message("user", questions[0].text)])["input_ids"][0]
    ind_prompt = engine._decode(ind_ids)
    n_seq = len(engine.tokenizer.encode(seq_prompt, add_special_tokens=False))
    missing = [q.id for q in questions if q.text not in seq_prompt] + \
              [f"answer {q.id}" for q in questions[:-1] if f"Placeholder answer to {q.id}." not in seq_prompt]
    if missing:
        raise AssertionError(f"chat template dropped {missing} from the sequential prompt")
    print(f"   prompts    sequential Q4 ~{n_seq} tokens, independent Q1 {len(ind_ids)} tokens; "
          f"generation cue {ind_prompt[-40:]!r}")
    if show_prompt:
        print("   ---- sequential prompt at Q4 ----\n" + seq_prompt + "\n   ---------------------------------")
    limit = engine._max_positions()
    if limit is not None and n_seq + engine.max_new_tokens > limit:
        print(f"   positions  ! context {limit} < prompt + max_new_tokens; the cap will be lowered to fit")

    print(f"   reasoning  {check_reasoning(engine, detect_format(engine, ind_prompt), ind_prompt)}")
    lines, problems = memory_lines(engine, cluster)
    print("   memory     " + "\n              ".join(lines))
    return problems


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--models", nargs="*", help="model keys (default: all enabled)")
    p.add_argument("--tier", choices=["core", "optional"])
    p.add_argument("--show-prompt", action="store_true", help="print the rendered sequential prompt")
    args = p.parse_args(argv)

    specs = load_models()
    keys = args.models or [k for k, s in specs.items() if s.enabled and args.tier in (None, s.tier)]
    unknown = [k for k in keys if k not in specs]
    if unknown:
        p.error(f"unknown model keys: {unknown}")
    questions, cluster = load_questions(), load_cluster()

    results = {}
    for key in keys:
        spec = specs[key]
        print(f"\n== {key}: {spec.hf_id} (revision={spec.revision or 'latest'})", flush=True)
        try:
            problems = check_model(spec, questions, cluster, args.show_prompt)
            results[key] = "WARN: " + "; ".join(problems) if problems else "ok"
        except Exception as e:  # noqa: BLE001  (keep going; report at the end)
            traceback.print_exc(limit=-3)
            results[key] = f"FAIL: {type(e).__name__}: {str(e).splitlines()[0][:200] if str(e) else ''}"
        print(f"   => {results[key]}", flush=True)

    print("\nSummary")
    for key, res in results.items():
        print(f"  {key:30s} {res}")
    return 1 if any(r.startswith("FAIL") for r in results.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
