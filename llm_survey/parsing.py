"""Separate a model's reasoning trace from its final answer.

Each model family marks reasoning differently. We always keep the raw decoded
output, so nothing is lost if a format is misread; this module only decides what
counts as "the answer" (which is what goes back into the chat history and what
you code).

Formats handled
  harmony  gpt-oss:      <|channel|>analysis<|message|>...<|end|><|start|>assistant<|channel|>final<|message|>...<|return|>
  gemma4   Gemma 4:      <|channel>thought ... <channel|> answer
  mistral  Magistral:    [THINK] ... [/THINK] answer
  think    Qwen, OLMo-Think, DeepSeek-R1 distills, Nemotron:  <think> ... </think> answer
Templates that open the reasoning block inside the prompt (e.g. "...assistant\n<think>\n")
are handled by passing the rendered prompt: an unclosed opener at its end is
treated as the start of the output.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

BLOCK_FORMATS = [
    # name, opener, closer
    ("gemma4", "<|channel>thought", "<channel|>"),
    ("mistral", "[THINK]", "[/THINK]"),
    ("think", "<think>", "</think>"),
]

HARMONY_SEGMENT = re.compile(
    r"<\|channel\|>(?P<channel>\w+)[^<]*<\|message\|>(?P<text>.*?)"
    r"(?=<\|end\|>|<\|return\|>|<\|call\|>|<\|start\|>|$)",
    flags=re.S,
)

# Markers stripped from answers even if the tokenizer does not list them as special.
FALLBACK_SPECIALS = [
    "<|return|>", "<|end|>", "<|endoftext|>", "<|im_end|>", "<|eot_id|>", "<|end_of_text|>",
    "<turn|>", "<|turn>", "<end_of_turn>", "<eos>", "</s>", "<|end▁of▁sentence|>",
    "<｜end▁of▁sentence｜>", "<|assistant|>", "<|user|>",
]


@dataclass
class Parsed:
    answer: str
    reasoning: str | None
    format: str
    reasoning_unterminated: bool = False


def _prompt_left_open(prompt: str, opener: str, closer: str) -> bool:
    idx = prompt.rfind(opener)
    return idx != -1 and closer not in prompt[idx + len(opener):]


def clean_answer(text: str, special_tokens: list[str] | None = None) -> str:
    tokens = sorted(set((special_tokens or []) + FALLBACK_SPECIALS), key=len, reverse=True)
    for tok in tokens:
        if tok:
            text = text.replace(tok, "")
    return text.strip()


def split_reasoning(raw: str, prompt: str = "", special_tokens: list[str] | None = None) -> Parsed:
    """Split decoded output (special tokens kept) into reasoning and answer."""
    if "<|channel|>" in raw or prompt.rstrip().endswith("<|start|>assistant"):
        segs = [(m.group("channel"), m.group("text")) for m in HARMONY_SEGMENT.finditer(raw)]
        if segs:
            analysis = "\n".join(t.strip() for c, t in segs if c == "analysis").strip()
            final = [t for c, t in segs if c == "final"]
            return Parsed(
                answer=clean_answer("\n".join(final), special_tokens),
                reasoning=analysis or None,
                format="harmony",
                reasoning_unterminated=not final,
            )

    for name, opener, closer in BLOCK_FORMATS:
        text = raw
        if _prompt_left_open(prompt, opener, closer) and not raw.lstrip().startswith(opener):
            text = opener + raw
        if closer in text:
            before, after = text.split(closer, 1)
            reasoning = before.split(opener, 1)[1] if opener in before else before
            reasoning = clean_answer(reasoning, special_tokens)
            return Parsed(answer=clean_answer(after, special_tokens), reasoning=reasoning or None, format=name)
        if opener in text:
            reasoning = clean_answer(text.split(opener, 1)[1], special_tokens)
            return Parsed(answer="", reasoning=reasoning or None, format=name, reasoning_unterminated=True)

    return Parsed(answer=clean_answer(raw, special_tokens), reasoning=None, format="none")
