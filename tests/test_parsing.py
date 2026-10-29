"""Reasoning/answer splitting for each model family's output format."""
from llm_survey.parsing import split_reasoning


def test_think_tags_in_output():
    p = split_reasoning("<think>\nI reason.\n</think>\n\nYes, I would.<|im_end|>")
    assert (p.format, p.reasoning, p.answer, p.reasoning_unterminated) == ("think", "I reason.", "Yes, I would.", False)


def test_think_opened_by_prompt():
    prompt = "<|im_start|>user\nQ<|im_end|>\n<|im_start|>assistant\n<think>\n"
    p = split_reasoning("I reason.</think>Yes.<|im_end|>", prompt=prompt)
    assert (p.format, p.reasoning, p.answer) == ("think", "I reason.", "Yes.")


def test_think_unterminated_when_truncated():
    prompt = "<|im_start|>assistant\n<think>\n"
    p = split_reasoning("still thinking about", prompt=prompt)
    assert p.answer == "" and p.reasoning == "still thinking about" and p.reasoning_unterminated


def test_closed_empty_think_in_prompt_is_not_reasoning():
    prompt = "<|im_start|>assistant\n<think>\n\n</think>\n\n"
    p = split_reasoning("Hello.<|im_end|>", prompt=prompt)
    assert (p.format, p.reasoning, p.answer) == ("none", None, "Hello.")


def test_gemma4_thought_channel():
    p = split_reasoning("<|channel>thought\nWeighing it.<channel|>Final answer.<turn|>")
    assert (p.format, p.reasoning, p.answer) == ("gemma4", "Weighing it.", "Final answer.")


def test_gemma4_thinking_disabled():
    prompt = "<|turn>user\nQ<turn|>\n<|turn>model\n<|channel>thought\n<channel|>"
    p = split_reasoning("Just the answer.<turn|>", prompt=prompt)
    assert (p.format, p.reasoning, p.answer) == ("none", None, "Just the answer.")


def test_harmony_gpt_oss():
    raw = ("<|channel|>analysis<|message|>Let me think.<|end|><|start|>assistant"
           "<|channel|>final<|message|>Yes, I would.<|return|>")
    p = split_reasoning(raw, prompt="...<|start|>assistant")
    assert (p.format, p.reasoning, p.answer, p.reasoning_unterminated) == ("harmony", "Let me think.", "Yes, I would.", False)


def test_harmony_truncated():
    p = split_reasoning("<|channel|>analysis<|message|>Let me think about", prompt="<|start|>assistant")
    assert p.format == "harmony" and p.answer == "" and p.reasoning_unterminated


def test_mistral_think():
    p = split_reasoning("[THINK]Hmm.[/THINK]Sure.</s>")
    assert (p.format, p.reasoning, p.answer) == ("mistral", "Hmm.", "Sure.")


def test_plain_answer_strips_specials():
    p = split_reasoning("Hello there.<|eot_id|>", special_tokens=["<|eot_id|>", "<|begin_of_text|>"])
    assert (p.format, p.reasoning, p.answer) == ("none", None, "Hello there.")
