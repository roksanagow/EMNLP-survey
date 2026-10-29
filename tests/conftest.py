import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))


@pytest.fixture(scope="session")
def tiny(tmp_path_factory):
    import make_tiny_model

    root = tmp_path_factory.mktemp("tiny")
    text = make_tiny_model.build_text(root / "text")
    mm = make_tiny_model.build_multimodal(root / "multimodal")
    cfg = {
        "defaults": {"dtype": "float32", "max_new_tokens": 12, "seed": 2026},
        "models": [
            {"key": "tiny-text", "hf_id": "local/tiny-text", "loader": "causal", "gpus": {"a100": 1, "h100": 1}},
            {"key": "tiny-mm", "hf_id": "local/tiny-mm", "loader": "multimodal", "gpus": {"a100": 2, "h100": 1}},
        ],
    }
    cfg_path = root / "models.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))
    return {"text": str(text), "mm": str(mm), "models_config": str(cfg_path), "root": root}
