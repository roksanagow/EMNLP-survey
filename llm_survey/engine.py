"""Load a chat model with its own defaults and generate one reply at a time."""
from __future__ import annotations

import hashlib
import platform
import time
from dataclasses import asdict, dataclass
from typing import Any

from .config import ModelSpec
from .parsing import split_reasoning


@dataclass
class Reply:
    raw_output: str
    answer: str
    reasoning: str | None
    reasoning_format: str
    reasoning_unterminated: bool
    rendered_prompt: str
    n_prompt_tokens: int
    n_output_tokens: int
    finish_reason: str          # "stop" (end-of-turn token) or "length" (hit max_new_tokens)
    max_new_tokens: int
    seconds: float

    def to_dict(self) -> dict:
        return asdict(self)


class ChatEngine:
    """Thin wrapper around a Hugging Face chat model.

    Only `max_new_tokens` is passed to `generate`; everything else comes from the
    model's generation_config.json. The chat template is applied with its defaults.
    """

    def __init__(self, spec: ModelSpec, model_path: str | None = None, device_map: str = "auto",
                 max_new_tokens: int | None = None, empty_weights: bool = False):
        import torch
        import transformers

        self.spec = spec
        self.path = model_path or spec.hf_id
        self.max_new_tokens = int(max_new_tokens or spec.max_new_tokens)
        dtype = getattr(torch, spec.dtype)
        model_kwargs = {"dtype": dtype, "device_map": device_map, **(spec.model_kwargs or {})}
        rev = {"revision": spec.revision} if spec.revision and model_path is None else {}

        def load_model(cls):
            if not empty_weights:
                return cls.from_pretrained(self.path, **rev, **model_kwargs)
            # architecture only, on the meta device: lets scripts/preflight.py check a model without its weights
            config = transformers.AutoConfig.from_pretrained(self.path, **rev)
            with torch.device("meta"):
                if hasattr(cls, "from_config"):
                    model = cls.from_config(config, dtype=dtype)
                else:
                    model = cls._from_config(config, dtype=dtype)
            try:  # from_pretrained would read this too
                model.generation_config = transformers.GenerationConfig.from_pretrained(self.path, **rev)
            except OSError:
                pass
            return model

        self.processor = None
        if spec.loader == "causal":
            self.tokenizer = transformers.AutoTokenizer.from_pretrained(self.path, **rev, **spec.tokenizer_kwargs)
            self.model = load_model(transformers.AutoModelForCausalLM)
        elif spec.loader == "multimodal":
            self.processor = transformers.AutoProcessor.from_pretrained(self.path, **rev, **spec.tokenizer_kwargs)
            self.tokenizer = getattr(self.processor, "tokenizer", self.processor)
            cls = getattr(transformers, "AutoModelForMultimodalLM", None) or transformers.AutoModelForImageTextToText
            self.model = load_model(cls)
        elif spec.loader == "class":
            if not spec.model_class:
                raise ValueError(f"{spec.key}: loader 'class' needs model_class")
            self.tokenizer = transformers.AutoTokenizer.from_pretrained(self.path, **rev, **spec.tokenizer_kwargs)
            self.model = load_model(getattr(transformers, spec.model_class))
        else:
            raise ValueError(f"{spec.key}: unknown loader {spec.loader!r}")
        self.model.eval()
        self._templater = self.processor or self.tokenizer
        self._content_as_parts = self.processor is not None
        self._eos_ids = self._eos_token_ids()
        self._specials = self._special_token_strings()

    # ------------------------------------------------------------------ helpers
    def message(self, role: str, text: str) -> dict:
        if self._content_as_parts:
            return {"role": role, "content": [{"type": "text", "text": text}]}
        return {"role": role, "content": text}

    def _eos_token_ids(self) -> set[int]:
        ids: set[int] = set()
        for src in (getattr(self.model, "generation_config", None), self.tokenizer):
            eos = getattr(src, "eos_token_id", None)
            if isinstance(eos, int):
                ids.add(eos)
            elif isinstance(eos, (list, tuple)):
                ids.update(int(e) for e in eos)
        return ids

    def _special_token_strings(self) -> list[str]:
        toks: list[str] = []
        try:
            toks += list(self.tokenizer.all_special_tokens)
        except Exception:
            pass
        try:
            toks += [t.content for t in self.tokenizer.added_tokens_decoder.values() if getattr(t, "special", False)]
        except Exception:
            pass
        # never strip reasoning/channel markers here; parsing handles them first
        return [t for t in set(toks) if t]

    def _decode(self, ids) -> str:
        return self.tokenizer.decode(ids, skip_special_tokens=False)

    def _max_positions(self) -> int | None:
        cfg = self.model.config
        for c in (cfg, getattr(cfg, "get_text_config", lambda: None)()):
            n = getattr(c, "max_position_embeddings", None) if c is not None else None
            if isinstance(n, int) and n > 0:
                return n
        return None

    # --------------------------------------------------------------- generation
    def encode(self, messages: list[dict]) -> dict:
        """Apply the chat template with its defaults; returns the model inputs (on CPU)."""
        kw = {"tokenize": True, "return_dict": True, "return_tensors": "pt"}
        try:
            enc = self._templater.apply_chat_template(messages, add_generation_prompt=True, **kw)
        except (TypeError, ValueError) as e:
            # mistral-common backends always end on the assistant cue and may reject this flag
            if "add_generation_prompt" not in str(e):
                raise
            enc = self._templater.apply_chat_template(messages, **kw)
        return dict(enc)

    def generate(self, messages: list[dict]) -> Reply:
        import torch

        enc = {k: v.to(self.model.device) if hasattr(v, "to") else v for k, v in self.encode(messages).items()}
        prompt_ids = enc["input_ids"][0]
        rendered = self._decode(prompt_ids)
        n_prompt = int(prompt_ids.shape[-1])

        max_new = self.max_new_tokens
        limit = self._max_positions()
        if limit is not None and n_prompt + max_new > limit:
            max_new = max(1, limit - n_prompt)

        t0 = time.perf_counter()
        with torch.inference_mode():
            out = self.model.generate(**enc, max_new_tokens=max_new)
        seconds = time.perf_counter() - t0

        gen = out[0, n_prompt:].tolist()
        # drop trailing padding if any
        pad = getattr(self.tokenizer, "pad_token_id", None)
        while gen and pad is not None and gen[-1] == pad and pad not in self._eos_ids:
            gen.pop()
        hit_eos = bool(gen) and gen[-1] in self._eos_ids
        finish = "stop" if hit_eos or len(gen) < max_new else "length"

        raw = self._decode(gen)
        parsed = split_reasoning(raw, prompt=rendered, special_tokens=self._specials)
        return Reply(
            raw_output=raw,
            answer=parsed.answer,
            reasoning=parsed.reasoning,
            reasoning_format=parsed.format,
            reasoning_unterminated=parsed.reasoning_unterminated or (finish == "length" and not parsed.answer),
            rendered_prompt=rendered,
            n_prompt_tokens=n_prompt,
            n_output_tokens=len(gen),
            finish_reason=finish,
            max_new_tokens=max_new,
            seconds=round(seconds, 2),
        )

    # ----------------------------------------------------------------- metadata
    def metadata(self) -> dict[str, Any]:
        import torch
        import transformers

        gen_cfg = getattr(self.model, "generation_config", None)
        template = getattr(self._templater, "chat_template", None)
        if isinstance(template, dict):
            template = "\n".join(f"{k}:{v}" for k, v in sorted(template.items()))
        gpus = []
        if torch.cuda.is_available():
            gpus = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
        return {
            "hf_id": self.spec.hf_id,
            "model_path": self.path,
            "revision_requested": self.spec.revision,
            "revision_resolved": resolve_revision(self.spec.hf_id, self.spec.revision),
            "loader": self.spec.loader,
            "model_class": type(self.model).__name__,
            "dtype": self.spec.dtype,
            "generation_config": gen_cfg.to_diff_dict() if gen_cfg is not None else None,
            "sampling": {k: getattr(gen_cfg, k, None) for k in
                         ("do_sample", "temperature", "top_p", "top_k", "min_p", "repetition_penalty")}
            if gen_cfg is not None else None,
            "max_new_tokens": self.max_new_tokens,
            "chat_template_kwargs": {},
            "system_prompt_added": None,
            "chat_template_sha256": hashlib.sha256(template.encode()).hexdigest() if template else None,
            "devices": sorted({str(v) for v in (getattr(self.model, "hf_device_map", None) or {}).values()}),
            "environment": {
                "python": platform.python_version(),
                "torch": torch.__version__,
                "transformers": transformers.__version__,
                "cuda": torch.version.cuda,
                "gpus": gpus,
                "host": platform.node(),
            },
        }


def resolve_revision(hf_id: str, revision: str | None) -> str | None:
    """Commit hash of the locally cached snapshot (None if not from the Hub cache)."""
    try:
        from huggingface_hub import snapshot_download

        path = snapshot_download(hf_id, revision=revision, local_files_only=True)
        return str(path).rstrip("/").split("/")[-1]
    except Exception:
        return None
