"""Loading the YAML configs (questions, models, cluster, pinned revisions)."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
LOCK_FILE = CONFIG_DIR / "revisions.lock.yaml"


@dataclass(frozen=True)
class Question:
    id: str
    text: str


@dataclass
class ModelSpec:
    key: str
    hf_id: str
    loader: str = "causal"
    model_class: str | None = None
    tokenizer_kwargs: dict[str, Any] = field(default_factory=dict)
    model_kwargs: dict[str, Any] = field(default_factory=dict)
    gpus: dict[str, int] = field(default_factory=lambda: {"a100": 1, "h100": 1})
    reasoning: str = "none"
    tier: str = "optional"
    enabled: bool = True
    revision: str | None = None
    dtype: str = "bfloat16"
    max_new_tokens: int = 32768
    seed: int = 2026
    time: str = "12:0:0"
    notes: str = ""


def load_yaml(path: str | os.PathLike) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_questions(path: str | os.PathLike = CONFIG_DIR / "questions.yaml") -> list[Question]:
    data = load_yaml(path)
    qs = [Question(id=str(q["id"]), text=str(q["text"])) for q in data["questions"]]
    ids = [q.id for q in qs]
    if len(set(ids)) != len(ids):
        raise ValueError(f"Duplicate question ids in {path}: {ids}")
    return qs


def questions_sha256(questions: list[Question]) -> str:
    blob = "\n".join(f"{q.id}\t{q.text}" for q in questions).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def load_models(path: str | os.PathLike = CONFIG_DIR / "models.yaml",
                lock_path: str | os.PathLike = LOCK_FILE) -> dict[str, ModelSpec]:
    data = load_yaml(path)
    defaults = data.get("defaults", {})
    lock = load_yaml(lock_path) if Path(lock_path).exists() else {}
    specs: dict[str, ModelSpec] = {}
    for entry in data["models"]:
        merged = {**defaults, **entry}
        spec = ModelSpec(**{k: v for k, v in merged.items() if k in ModelSpec.__dataclass_fields__})
        if isinstance(spec.reasoning, bool):  # YAML reads a bare on/off as a boolean
            spec.reasoning = "on" if spec.reasoning else "off"
        if spec.revision is None and spec.key in lock:
            spec.revision = lock[spec.key]
        if spec.key in specs:
            raise ValueError(f"Duplicate model key: {spec.key}")
        specs[spec.key] = spec
    return specs


def load_cluster(path: str | os.PathLike = CONFIG_DIR / "cluster.yaml") -> dict:
    return load_yaml(path)


def expand(value: str) -> str:
    """Expand ${VAR} / $VAR and ~ in a path string."""
    return os.path.expanduser(os.path.expandvars(value))
