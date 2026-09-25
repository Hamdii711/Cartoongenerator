"""Create and manage a project's character assets.

Each character in `projects/<project>/characters/<name>/` has:
  - profile.json  (name, physical_description, personality, role)
  - neutral.png   (idle pose, mouth closed)
  - talk.png      (idle pose, mouth open - used for the talking animation)
  - blink.png     (idle pose, eyes closed - used for the occasional blink)

The three images are cutouts (transparent background) so they can be
composited straight onto a scene background.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict

import numpy as np
from PIL import Image

from config import get_project_dir
from providers.base import ImageProvider
from providers.prompts import build_character_prompt

POSES = ("neutral", "talk", "blink")


def _key_white_to_alpha(img: Image.Image, threshold: int = 235, soft_range: int = 30) -> Image.Image:
    """Turn a (near-)white background into real transparency.

    Used for providers (e.g. Gemini/Imagen) that cannot natively return an
    alpha channel: we ask for a plain white backdrop and key it out here.
    Pixels whose minimum channel value is >= `threshold` become fully
    transparent; pixels below `threshold - soft_range` stay fully opaque;
    values in between fade linearly, to avoid a hard jagged edge.
    """
    rgba = img.convert("RGBA")
    arr = np.array(rgba).astype(np.int16)
    whiteness = arr[..., :3].min(axis=-1)
    alpha = np.clip((threshold - whiteness) / max(1, soft_range) * 255.0, 0, 255)
    arr[..., 3] = np.minimum(arr[..., 3], alpha).astype(np.int16)
    return Image.fromarray(arr.astype(np.uint8))


def _ensure_alpha(png_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    alpha_channel = np.array(img)[..., 3]
    # If the image came back fully opaque, it has no real alpha yet - key
    # out the (assumed) plain white background ourselves.
    if alpha_channel.min() >= 250:
        img = _key_white_to_alpha(img)
    return img


def character_dir(project: str, name: str) -> Path:
    return get_project_dir(project) / "characters" / name


def add_character(
    project: str,
    name: str,
    physical_description: str,
    personality: str,
    role: str,
    image_provider: ImageProvider,
) -> Dict[str, Any]:
    """Generate the 3 pose assets for a character and save its profile."""
    proj_dir = get_project_dir(project, create=True)
    c_dir = proj_dir / "characters" / name
    c_dir.mkdir(parents=True, exist_ok=True)

    profile = {
        "name": name,
        "physical_description": physical_description,
        "personality": personality,
        "role": role,
    }
    with open(c_dir / "profile.json", "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    paths: Dict[str, str] = {}
    for pose in POSES:
        prompt = build_character_prompt(physical_description, personality, pose)
        raw = image_provider.generate_image(prompt, transparent_bg=True)
        img = _ensure_alpha(raw)
        out_path = c_dir / f"{pose}.png"
        img.save(out_path)
        paths[pose] = str(out_path)

    return {"name": name, "dir": str(c_dir), "paths": paths, "profile": profile}


def load_profile(project: str, name: str) -> Dict[str, Any]:
    path = character_dir(project, name) / "profile.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_characters(project: str) -> list[str]:
    chars_dir = get_project_dir(project) / "characters"
    if not chars_dir.exists():
        return []
    return sorted(p.name for p in chars_dir.iterdir() if p.is_dir())


def load_character_assets(project: str, name: str) -> Dict[str, Image.Image]:
    """Load the pose images for one character as PIL RGBA images."""
    c_dir = character_dir(project, name)
    assets = {}
    for pose in POSES:
        path = c_dir / f"{pose}.png"
        if path.exists():
            assets[pose] = Image.open(path).convert("RGBA")
    if "neutral" not in assets:
        raise FileNotFoundError(
            f"Character {name!r} in project {project!r} has no neutral.png - "
            f"run `character add` first."
        )
    # Fall back to neutral for any pose that wasn't generated.
    for pose in POSES:
        assets.setdefault(pose, assets["neutral"])
    return assets
