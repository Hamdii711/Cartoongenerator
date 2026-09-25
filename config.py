"""Configuration loading for the cartoon generator.

- Secrets (API keys) come from `.env` (via python-dotenv) or the real
  environment.
- Everything else (default providers, video settings, timing) comes from
  `config.yaml` if present, merged over sane defaults.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
import yaml

BASE_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = BASE_DIR / "projects"

# Load .env once at import time (does not override real env vars already set).
load_dotenv(BASE_DIR / ".env")

DEFAULT_CONFIG: Dict[str, Any] = {
    "default_llm_provider": "openai",
    "default_image_provider": "openai",
    "fps": 24,
    "resolution": [1280, 720],
    "min_line_seconds": 2.0,
    "chars_per_second": 15.0,
    "scene_intro_pad": 0.4,
    "scene_outro_pad": 0.4,
    "mouth_flap_interval": 0.2,
    "blink_interval": 4.0,
    "blink_duration": 0.15,
    "scene_transition_fade": 0.3,
    "character_height": 0.55,
    "walk_in_duration": 1.4,
    "step_duration": 0.25,
    "walk_swing_degrees": 22.0,
    "idle_sway_degrees": 4.0,
    "idle_sway_period": 2.2,
}


def load_config() -> Dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    config_path = BASE_DIR / "config.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        cfg.update(user_cfg)
    return cfg


def get_api_key(env_var: str) -> str:
    val = os.getenv(env_var)
    if not val:
        raise RuntimeError(
            f"Missing {env_var}. Set it in cartoon_generator/.env "
            f"(copy from .env.example) or in your shell environment."
        )
    return val


def get_project_dir(project: str, create: bool = False) -> Path:
    path = PROJECTS_DIR / project
    if create:
        (path / "characters").mkdir(parents=True, exist_ok=True)
        (path / "backgrounds").mkdir(parents=True, exist_ok=True)
        (path / "scenes").mkdir(parents=True, exist_ok=True)
    return path
