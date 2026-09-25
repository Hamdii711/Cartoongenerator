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
from PIL import Image, ImageDraw

from config import get_project_dir
from providers.base import ImageProvider
from providers.prompts import build_character_prompt

POSES = ("neutral", "talk", "blink")
# Optional walking frames (e.g. left foot forward / right foot forward),
# alternated while a character walks into the scene. Without them the
# character hops in its neutral pose, cutout style.
WALK_POSES = ("walk_1", "walk_2")


def _key_white_to_alpha(img: Image.Image, threshold: int = 235, soft_range: int = 30) -> Image.Image:
    """Turn a plain (near-)white *background* into real transparency.

    Used for images without a native alpha channel (Gemini/Imagen, or
    pictures made by hand in ChatGPT/Gemini): the character is drawn on a
    plain white backdrop and we key that backdrop out here.

    Only near-white pixels connected to the image border are removed, so
    white areas enclosed by the character's outline (a white t-shirt, the
    whites of the eyes, sneakers...) stay opaque. Within that background
    region, pixels whose minimum channel is >= `threshold` become fully
    transparent and those between `threshold - soft_range` and `threshold`
    fade linearly, to avoid a hard jagged edge along the outline.
    """
    rgba = img.convert("RGBA")
    arr = np.array(rgba).astype(np.int16)
    whiteness = arr[..., :3].min(axis=-1)

    near_white = whiteness >= threshold - soft_range
    # Pad with a 1px near-white frame so a single flood fill from a corner
    # reaches every near-white region touching any edge of the image.
    mask = np.pad(near_white, 1, constant_values=True).astype(np.uint8) * 255
    # .copy(): fromarray can share a read-only buffer that floodfill silently ignores
    mask_img = Image.fromarray(mask).copy()
    ImageDraw.floodfill(mask_img, (0, 0), 128)
    background = (np.array(mask_img) == 128)[1:-1, 1:-1]

    soft_alpha = np.clip((threshold - whiteness) / max(1, soft_range) * 255.0, 0, 255)
    alpha = np.where(background, soft_alpha, 255)
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


def import_character(
    project: str,
    name: str,
    physical_description: str,
    personality: str,
    role: str,
    pose_images: Dict[str, str],
) -> Dict[str, Any]:
    """Create a character from image files made elsewhere (e.g. by hand in
    ChatGPT or Gemini) instead of calling an image provider.

    `pose_images` maps a pose ("neutral", "talk", "blink") to a local image
    path. Only "neutral" is required; missing poses fall back to it at
    render time. Opaque images get their plain white background keyed out,
    exactly like provider-generated ones.
    """
    if "neutral" not in pose_images:
        raise ValueError("A 'neutral' image is required to import a character")
    allowed = POSES + WALK_POSES
    unknown = set(pose_images) - set(allowed)
    if unknown:
        raise ValueError(f"Unknown pose(s) {sorted(unknown)}; expected some of {list(allowed)}")

    c_dir = get_project_dir(project, create=True) / "characters" / name
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
    for pose, src in pose_images.items():
        img = _ensure_alpha(Path(src).read_bytes())
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
    """Load the pose images for one character as PIL RGBA images.

    All poses are cropped to the union of their visible (non-transparent)
    bounding boxes: this drops the empty margins around the figure, so the
    character is scaled by its real height, while keeping the exact same
    crop for every pose, so the figure doesn't jump when switching between
    neutral/talk/blink.
    """
    c_dir = character_dir(project, name)
    assets = {}
    for pose in POSES + WALK_POSES:
        path = c_dir / f"{pose}.png"
        if path.exists():
            assets[pose] = Image.open(path).convert("RGBA")
    if "neutral" not in assets:
        raise FileNotFoundError(
            f"Character {name!r} in project {project!r} has no neutral.png - "
            f"run `character add` or `character import` first."
        )

    # Poses made separately can differ slightly in size; align them on neutral.
    base_size = assets["neutral"].size
    for pose, img in assets.items():
        if img.size != base_size:
            assets[pose] = img.resize(base_size, Image.LANCZOS)

    boxes = [img.getchannel("A").getbbox() for img in assets.values()]
    boxes = [b for b in boxes if b]
    if boxes:
        union = (
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        )
        assets = {pose: img.crop(union) for pose, img in assets.items()}

    # Fall back to neutral for any core pose that wasn't generated. Walk
    # poses stay absent when not provided: the renderer checks for them.
    for pose in POSES:
        assets.setdefault(pose, assets["neutral"])
    return assets
