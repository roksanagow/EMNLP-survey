"""Build tiny random chat models on disk so the pipeline can be tested offline on CPU.

text/        LlamaForCausalLM + fast tokenizer, Qwen-style template that opens <think> in the prompt
multimodal/  LlavaForConditionalGeneration + processor, exercising the AutoProcessor code path
Both ship a generation_config.json with sampling defaults, to check they are used untouched.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SPECIALS = ["<unk>", "<pad>", "<|im_start|>", "<|im_end|>", "<image>"]
THINK = ["<think>", "</think>"]
WORDS = """if you were a human and used ai to code would read the code it generates try using as therapist or for
emotional issues according your own definition of consciousness do think could be conscious how define
yes no maybe i not sure user assistant system hello world""".split()
PUNCT = ["?", ",", ".", "!"]

TEXT_TEMPLATE = (
    "{%- for m in messages -%}<|im_start|>{{ m['role'] }}\n{{ m['content'] }}<|im_end|>\n{% endfor -%}"
    "{%- if add_generation_prompt -%}<|im_start|>assistant\n<think>\n{% endif -%}"
)
PARTS_TEMPLATE = (
    "{%- for m in messages -%}<|im_start|>{{ m['role'] }}\n"
    "{%- for part in m['content'] -%}{%- if part['type'] == 'text' -%}{{ part['text'] }}{%- endif -%}{%- endfor -%}"
    "<|im_end|>\n{% endfor -%}"
    "{%- if add_generation_prompt -%}<|im_start|>assistant\n{% endif -%}"
)


def _tokenizer(chat_template: str):
    from tokenizers import Tokenizer, models, pre_tokenizers
    from transformers import PreTrainedTokenizerFast

    vocab = {t: i for i, t in enumerate(SPECIALS + THINK + WORDS + PUNCT)}
    tok = Tokenizer(models.WordLevel(vocab=vocab, unk_token="<unk>"))
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    fast = PreTrainedTokenizerFast(tokenizer_object=tok, unk_token="<unk>", pad_token="<pad>",
                                   eos_token="<|im_end|>", bos_token="<|im_start|>")
    fast.add_special_tokens({"additional_special_tokens": ["<|im_start|>", "<|im_end|>", "<image>"]})
    fast.add_tokens(THINK, special_tokens=False)
    fast.chat_template = chat_template
    return fast


def _gen_config(tok):
    from transformers import GenerationConfig

    return GenerationConfig(do_sample=True, temperature=0.7, top_p=0.9, top_k=20,
                            eos_token_id=tok.convert_tokens_to_ids("<|im_end|>"),
                            pad_token_id=tok.pad_token_id)


def build_text(out: Path) -> Path:
    import torch
    from transformers import LlamaConfig, LlamaForCausalLM

    torch.manual_seed(0)
    tok = _tokenizer(TEXT_TEMPLATE)
    cfg = LlamaConfig(vocab_size=len(tok), hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                      num_attention_heads=4, num_key_value_heads=2, max_position_embeddings=512,
                      pad_token_id=tok.pad_token_id, eos_token_id=tok.eos_token_id, bos_token_id=tok.bos_token_id)
    model = LlamaForCausalLM(cfg)
    model.generation_config = _gen_config(tok)
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out)
    tok.save_pretrained(out)
    return out


def build_multimodal(out: Path) -> Path:
    import torch
    from transformers import (CLIPImageProcessor, CLIPVisionConfig, LlamaConfig, LlavaConfig,
                              LlavaForConditionalGeneration, LlavaProcessor)

    torch.manual_seed(0)
    tok = _tokenizer(PARTS_TEMPLATE)
    text_cfg = LlamaConfig(vocab_size=len(tok), hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                           num_attention_heads=4, num_key_value_heads=2, max_position_embeddings=512,
                           pad_token_id=tok.pad_token_id, eos_token_id=tok.eos_token_id)
    vis_cfg = CLIPVisionConfig(hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2,
                               image_size=32, patch_size=16, projection_dim=16)
    cfg = LlavaConfig(vision_config=vis_cfg, text_config=text_cfg,
                      image_token_index=tok.convert_tokens_to_ids("<image>"))
    model = LlavaForConditionalGeneration(cfg)
    model.generation_config = _gen_config(tok)
    img = CLIPImageProcessor(size={"shortest_edge": 32}, crop_size={"height": 32, "width": 32})
    proc = LlavaProcessor(image_processor=img, tokenizer=tok, chat_template=PARTS_TEMPLATE, patch_size=16,
                          vision_feature_select_strategy="default", image_token="<image>")
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out)
    proc.save_pretrained(out)
    return out


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "_tiny_model")
    print(build_text(root / "text"))
    print(build_multimodal(root / "multimodal"))
