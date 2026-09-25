"""Render each scene of a project's story into a short mp4 clip.

No TTS: each line's on-screen duration is estimated from its text length,
the speaking character's mouth alternates neutral/talk during their line,
idle characters blink occasionally, the background gets a simple Ken-Burns
style camera move, and the dialogue is burned in as a caption bar.
"""

from __future__ import annotations

import math
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import VideoClip

from config import get_project_dir, load_config
from pipeline.character_studio import load_character_assets
from providers.base import ImageProvider
from providers.prompts import build_background_prompt

Size = Tuple[int, int]


# ---------------------------------------------------------------------------
# Backgrounds
# ---------------------------------------------------------------------------

def ensure_backgrounds(project: str, story: Dict[str, Any], image_provider: ImageProvider) -> None:
    """Generate any missing background image for the story's scenes.

    Idempotent: a background is only (re)generated if the file doesn't
    already exist, so a user can hand-replace a background and re-run
    `render` without losing their edit.
    """
    bg_dir = get_project_dir(project) / "backgrounds"
    bg_dir.mkdir(parents=True, exist_ok=True)
    for scene in story["scenes"]:
        out_path = bg_dir / f"scene_{scene['id']}.png"
        if out_path.exists():
            continue
        prompt = build_background_prompt(scene["background_desc"])
        raw = image_provider.generate_image(prompt, transparent_bg=False, size="1536x1024")
        img = Image.open(_bytes_io(raw)).convert("RGB")
        img.save(out_path)


def _bytes_io(data: bytes):
    import io

    return io.BytesIO(data)


def _load_background(project: str, scene_id: int) -> Image.Image:
    path = get_project_dir(project) / "backgrounds" / f"scene_{scene_id}.png"
    return Image.open(path).convert("RGB")


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

def _line_duration(text: str, cfg: dict) -> float:
    return max(cfg["min_line_seconds"], len(text) / cfg["chars_per_second"])


def _build_timeline(scene: Dict[str, Any], cfg: dict) -> Tuple[List[Tuple[float, float, str, str]], float]:
    """Return (timeline, total_duration).

    timeline entries are (start, end, speaker, text) windows during which
    that line is "showing" (spoken + captioned).
    """
    t = cfg["scene_intro_pad"]
    timeline = []
    for line in scene.get("lines", []):
        dur = _line_duration(line["text"], cfg)
        timeline.append((t, t + dur, line["speaker"], line["text"]))
        t += dur
    t += cfg["scene_outro_pad"]
    if not timeline:
        t = max(t, 3.0)
    return timeline, t


def _active_line(timeline, t: float):
    for start, end, speaker, text in timeline:
        if start <= t < end:
            return speaker, text
    return None, None


# ---------------------------------------------------------------------------
# Background camera motion (Ken Burns style)
# ---------------------------------------------------------------------------

def _make_background_frame_fn(bg_img: Image.Image, size: Size, camera: str, duration: float):
    w, h = size
    oversample = 1.25
    big = bg_img.resize((int(w * oversample), int(h * oversample)), Image.LANCZOS)
    bw, bh = big.size

    def frame_at(t: float) -> np.ndarray:
        p = min(1.0, t / duration) if duration > 0 else 0.0
        if camera == "zoom_in":
            scale = 1.0 + 0.15 * p
        elif camera == "zoom_out":
            scale = 1.15 - 0.15 * p
        else:
            scale = 1.05
        crop_w = min(bw, max(1, int(w / scale)))
        crop_h = min(bh, max(1, int(h / scale)))
        if camera == "pan_left":
            x = int((bw - crop_w) * (1 - p))
        elif camera == "pan_right":
            x = int((bw - crop_w) * p)
        else:
            x = (bw - crop_w) // 2
        y = (bh - crop_h) // 2
        crop = big.crop((x, y, x + crop_w, y + crop_h)).resize((w, h), Image.LANCZOS)
        return np.array(crop)

    return frame_at


# ---------------------------------------------------------------------------
# Character pose / placement
# ---------------------------------------------------------------------------

def _character_pose(name: str, t: float, speaker: str | None, cfg: dict) -> str:
    if name == speaker:
        return "talk" if int(t / cfg["mouth_flap_interval"]) % 2 == 0 else "neutral"
    # deterministic per-character blink phase so characters don't blink in sync
    phase = (sum(ord(c) for c in name) % 100) / 100.0 * cfg["blink_interval"]
    cycle_t = (t + phase) % cfg["blink_interval"]
    if cycle_t < cfg["blink_duration"]:
        return "blink"
    return "neutral"


def _character_render_size(char_img: Image.Image, frame_size: Size) -> Size:
    _, h = frame_size
    target_h = int(h * 0.55)
    scale = target_h / char_img.height
    return max(1, int(char_img.width * scale)), target_h


def _character_position(
    idx: int, count: int, frame_size: Size, char_size: Size, t: float
) -> Tuple[int, int]:
    w, h = frame_size
    cw, ch = char_size
    slot_w = w / count
    base_x = int(slot_w * idx + (slot_w - cw) / 2)
    base_y = h - ch  # feet at the bottom edge

    entrance = min(1.0, t / 0.5)
    ease = 1 - (1 - entrance) ** 2
    offscreen_x = -cw if idx < count / 2 else w
    x = int(offscreen_x + (base_x - offscreen_x) * ease)
    return x, base_y


# ---------------------------------------------------------------------------
# Captions
# ---------------------------------------------------------------------------

def _load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _caption_overlay(speaker: str, text: str, size: Size) -> Image.Image:
    w, h = size
    bar_h = max(60, int(h * 0.16))
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bar = Image.new("RGBA", (w, bar_h), (0, 0, 0, 170))
    draw = ImageDraw.Draw(bar)
    font_size = max(16, bar_h // 4)
    font = _load_font(font_size)
    label = f"{speaker}: {text}"
    wrapped = textwrap.fill(label, width=max(20, w // (font_size // 2)))
    draw.multiline_text((20, bar_h // 2), wrapped, font=font, fill=(255, 255, 255, 255), anchor="lm", spacing=4)
    overlay.paste(bar, (0, h - bar_h), bar)
    return overlay


# ---------------------------------------------------------------------------
# Scene rendering
# ---------------------------------------------------------------------------

def render_scene(
    project: str,
    scene: Dict[str, Any],
    cfg: dict | None = None,
) -> Path:
    cfg = cfg or load_config()
    size: Size = tuple(cfg["resolution"])

    bg_img = _load_background(project, scene["id"])
    timeline, duration = _build_timeline(scene, cfg)
    bg_frame_fn = _make_background_frame_fn(bg_img, size, scene.get("camera", "static"), duration)

    scene_characters = list(dict.fromkeys(line["speaker"] for line in scene.get("lines", [])))
    if not scene_characters:
        scene_characters = list(scene.get("characters", []))
    char_assets = {name: load_character_assets(project, name) for name in scene_characters}
    char_render_sizes = {
        name: _character_render_size(assets["neutral"], size) for name, assets in char_assets.items()
    }

    def make_frame(t: float) -> np.ndarray:
        frame = Image.fromarray(bg_frame_fn(t)).convert("RGBA")
        speaker, text = _active_line(timeline, t)

        for idx, name in enumerate(scene_characters):
            pose = _character_pose(name, t, speaker, cfg)
            char_img = char_assets[name][pose]
            render_size = char_render_sizes[name]
            resized = char_img.resize(render_size, Image.LANCZOS)
            x, y = _character_position(idx, len(scene_characters), size, render_size, t)
            frame.alpha_composite(resized, (x, y))

        if text:
            frame.alpha_composite(_caption_overlay(speaker, text, size))

        return np.array(frame.convert("RGB"))

    out_dir = get_project_dir(project) / "scenes"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"scene_{scene['id']}.mp4"

    clip = VideoClip(make_frame, duration=duration)
    clip.write_videofile(
        str(out_path),
        fps=cfg["fps"],
        codec="libx264",
        audio=False,
        logger=None,
    )
    clip.close()
    return out_path


def render_project(project: str, story: Dict[str, Any], cfg: dict | None = None) -> List[Path]:
    cfg = cfg or load_config()
    return [render_scene(project, scene, cfg) for scene in story["scenes"]]
