"""Render each scene of a project's story into a short mp4 clip.

No TTS: each line's on-screen duration is estimated from its text length,
the speaking character's mouth alternates neutral/talk during their line,
idle characters blink occasionally, the background gets a simple Ken-Burns
style camera move, and the dialogue is burned in as a caption bar.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import VideoClip

from config import get_project_dir, load_config
from pipeline import rig as rig_module
from pipeline.character_studio import load_character_assets
from providers.base import ImageProvider
from providers.prompts import build_background_prompt

Size = Tuple[int, int]


# ---------------------------------------------------------------------------
# Backgrounds
# ---------------------------------------------------------------------------

def missing_backgrounds(project: str, story: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Scenes whose background image doesn't exist on disk yet."""
    bg_dir = get_project_dir(project) / "backgrounds"
    return [s for s in story["scenes"] if not (bg_dir / f"scene_{s['id']}.png").exists()]


def ensure_backgrounds(project: str, story: Dict[str, Any], image_provider: ImageProvider) -> None:
    """Generate any missing background image for the story's scenes.

    Idempotent: a background is only (re)generated if the file doesn't
    already exist, so a user can hand-replace a background and re-run
    `render` without losing their edit.
    """
    bg_dir = get_project_dir(project) / "backgrounds"
    bg_dir.mkdir(parents=True, exist_ok=True)
    for scene in missing_backgrounds(project, story):
        out_path = bg_dir / f"scene_{scene['id']}.png"
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


def _build_timeline(
    scene: Dict[str, Any], cfg: dict, start_offset: float = 0.0
) -> Tuple[List[Tuple[float, float, str, str]], float]:
    """Return (timeline, total_duration).

    timeline entries are (start, end, speaker, text) windows during which
    that line is "showing" (spoken + captioned).
    """
    t = max(cfg["scene_intro_pad"], start_offset)
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
# Camera
#
# The scene is composed in "world" space: the background is oversampled so
# the camera has room to zoom/pan, and characters are placed ON that world
# (feet on the floor). Each frame, the camera crops a window of the world
# and scales it to the output size - so characters move exactly with the
# background instead of floating over it.
# ---------------------------------------------------------------------------

OVERSAMPLE = 1.25
MAX_ZOOM = 1.15
BASE_ZOOM = 1.05


def _camera_box(camera: str, p: float, world_size: Size, out_size: Size) -> Tuple[float, float, float, float]:
    """Crop window (x, y, width, height) in world pixels at progress p in [0, 1]."""
    bw, bh = world_size
    w, h = out_size
    if camera == "zoom_in":
        zoom = 1.0 + (MAX_ZOOM - 1.0) * p
    elif camera == "zoom_out":
        zoom = MAX_ZOOM - (MAX_ZOOM - 1.0) * p
    else:
        zoom = BASE_ZOOM
    crop_w = min(bw, w / zoom)
    crop_h = min(bh, h / zoom)
    if camera == "pan_left":
        x = (bw - crop_w) * (1 - p)
    elif camera == "pan_right":
        x = (bw - crop_w) * p
    else:
        x = (bw - crop_w) / 2
    y = (bh - crop_h) / 2
    return x, y, crop_w, crop_h


# ---------------------------------------------------------------------------
# Characters
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


def _floor_y(world_size: Size, out_size: Size) -> float:
    """World y of the characters' feet: near the bottom of the screen, and
    still visible at the camera's tightest zoom."""
    _, bh = world_size
    _, h = out_size
    return bh / 2 + (h / MAX_ZOOM) * 0.45


def _slot_centers(count: int, world_size: Size, out_size: Size) -> List[float]:
    """World x of each character, spread over the part of the world that
    stays on screen for every camera move (so nobody gets panned out)."""
    bw, _ = world_size
    w, _ = out_size
    safe_w = w / MAX_ZOOM - (bw - w / BASE_ZOOM)  # visible in every pan position
    safe_w = max(safe_w, w / MAX_ZOOM * 0.5)
    left = (bw - safe_w) / 2
    return [left + safe_w * (i + 0.5) / count for i in range(count)]


# ---------------------------------------------------------------------------
# Speech bubble
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


def _wrap_to_width(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    """Greedy word wrap using the font's real rendered width."""
    lines: List[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and font.getlength(candidate) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines



def _draw_speech_bubble(frame: Image.Image, text: str, anchor_x: float, anchor_y: float) -> None:
    """Comic speech bubble whose tail points at (anchor_x, anchor_y) - the
    top of the speaker's head, in screen pixels."""
    w, h = frame.size
    font_size = max(16, h // 26)
    pad = font_size // 2 + 4
    max_text_w = int(min(w * 0.42, 560))

    while True:
        font = _load_font(font_size)
        lines = _wrap_to_width(text, font, max_text_w)
        line_h = int(font_size * 1.25)
        if len(lines) <= 4 or font_size <= 12:
            break
        font_size -= 2

    text_w = max(font.getlength(line) for line in lines)
    box_w = int(text_w + 2 * pad)
    box_h = int(len(lines) * line_h + 2 * pad)
    tail_h = max(14, h // 30)

    left = int(min(max(anchor_x - box_w / 2, 10), w - box_w - 10))
    top = int(max(anchor_y - tail_h - box_h - 6, 10))
    bottom = top + box_h

    draw = ImageDraw.Draw(frame)
    outline = max(2, h // 240)
    radius = min(box_h // 2, font_size)
    draw.rounded_rectangle((left, top, left + box_w, bottom), radius=radius,
                           fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=outline)

    tail_x = min(max(anchor_x, left + radius + 12), left + box_w - radius - 12)
    tip = (anchor_x, max(anchor_y - 6, bottom + 4))
    base_l = (tail_x - 12, bottom - outline)
    base_r = (tail_x + 12, bottom - outline)
    draw.polygon([base_l, tip, base_r], fill=(255, 255, 255, 255))
    draw.line([base_l, tip, base_r], fill=(0, 0, 0, 255), width=outline)

    y = top + pad
    for line in lines:
        draw.text((left + pad, y), line, font=font, fill=(0, 0, 0, 255))
        y += line_h


# ---------------------------------------------------------------------------
# Scene rendering
# ---------------------------------------------------------------------------

def render_scene(
    project: str,
    scene: Dict[str, Any],
    cfg: dict | None = None,
    walk_in: List[str] | None = None,
) -> Path:
    """Render one scene to scenes/scene_<id>.mp4.

    `walk_in` lists characters that walk into frame at the start of this
    scene (typically their first appearance in the episode); everyone else
    is already standing in place when the scene starts.
    """
    cfg = cfg or load_config()
    size: Size = tuple(cfg["resolution"])
    w, h = size
    walk_in = walk_in or []

    scene_characters = list(dict.fromkeys(line["speaker"] for line in scene.get("lines", [])))
    if not scene_characters:
        scene_characters = list(scene.get("characters", []))

    walk_time = cfg["walk_in_duration"] if any(n in walk_in for n in scene_characters) else 0.0
    timeline, duration = _build_timeline(scene, cfg, start_offset=walk_time)

    world_size: Size = (int(w * OVERSAMPLE), int(h * OVERSAMPLE))
    world_bg = _load_background(project, scene["id"]).resize(world_size, Image.LANCZOS).convert("RGBA")
    camera = scene.get("camera", "static")
    floor_y = _floor_y(world_size, size)
    slots = _slot_centers(len(scene_characters), world_size, size)

    # Load each character once: either a rigged skeleton (real leg/arm
    # rotation) or a flat pose sprite set (whole-image swap), whichever that
    # character has. A rigged sprite() call composes a fresh frame; a flat
    # one just looks up the pose image - both return a bottom-anchored RGBA
    # image whose bottom edge is exactly the standing feet line.
    char_h = int(h * cfg["character_height"])
    animators: Dict[str, Any] = {}
    for name in scene_characters:
        if rig_module.is_rigged(project, name):
            animators[name] = rig_module.load_rig(project, name, char_h)
        else:
            assets = load_character_assets(project, name)
            scale = char_h / assets["neutral"].height
            animators[name] = {
                pose: img.resize((max(1, int(img.width * scale)), char_h), Image.LANCZOS)
                for pose, img in assets.items()
            }

    def _rig_sprite(rig: "rig_module.LoadedRig", name: str, t: float, speaker: str | None, walking: bool) -> Image.Image:
        head_variant = _character_pose(name, t, speaker, cfg)
        phase = (sum(ord(c) for c in name) % 100) / 100.0 * 2 * math.pi
        if walking:
            amp = cfg["walk_swing_degrees"]
            leg_l = rig_module.walk_leg_angle(t, cfg["step_duration"], amp, 0.0)
            leg_r = rig_module.walk_leg_angle(t, cfg["step_duration"], amp, math.pi)
            arm_l, arm_r = -leg_l, -leg_r
        else:
            sway = rig_module.idle_sway_angle(t, cfg["idle_sway_period"], cfg["idle_sway_degrees"], phase)
            leg_l = leg_r = 0.0
            arm_l, arm_r = sway, -sway
        return rig.compose(head_variant, leg_l, leg_r, arm_l, arm_r)

    def get_sprite(name: str, t: float, speaker: str | None, walking: bool) -> Image.Image:
        animator = animators[name]
        if isinstance(animator, rig_module.LoadedRig):
            return _rig_sprite(animator, name, t, speaker, walking)
        if walking:
            walk_poses = [p for p in ("walk_1", "walk_2") if p in animator]
            if walk_poses:
                return animator[walk_poses[int(t / cfg["step_duration"]) % len(walk_poses)]]
            return animator["neutral"]
        return animator[_character_pose(name, t, speaker, cfg)]

    def character_state(idx: int, name: str, t: float, speaker: str | None):
        """(sprite, world_x_center, world_feet_y) of a character at time t."""
        target_x = slots[idx]
        walking = name in walk_in and t < walk_time
        if walking:
            progress = t / walk_time
            sprite_w = char_h  # rough estimate is fine, only used to place the offscreen start
            from_left = idx < len(scene_characters) / 2
            start_x = -sprite_w if from_left else world_size[0] + sprite_w
            x = start_x + (target_x - start_x) * progress
            sprite = get_sprite(name, t, speaker, walking=True)
            return sprite, x, floor_y
        sprite = get_sprite(name, t, speaker, walking=False)
        return sprite, target_x, floor_y

    def make_frame(t: float) -> np.ndarray:
        speaker, text = _active_line(timeline, t)
        world = world_bg.copy()
        head_positions = {}
        for idx, name in enumerate(scene_characters):
            sprite, cx, feet_y = character_state(idx, name, t, speaker)
            x = int(cx - sprite.width / 2)
            y = int(feet_y - sprite.height)
            if -sprite.width < x < world_size[0]:
                world.alpha_composite(sprite, (max(x, 0), y), source=(max(-x, 0), 0))
            head_positions[name] = (cx, y)

        p = min(1.0, t / duration) if duration > 0 else 0.0
        cx0, cy0, cw, ch = _camera_box(camera, p, world_size, size)
        frame = world.resize(size, Image.BILINEAR, box=(cx0, cy0, cx0 + cw, cy0 + ch))

        if text and speaker in head_positions:
            hx, hy = head_positions[speaker]
            sx = (hx - cx0) * w / cw
            sy = (hy - cy0) * h / ch
            _draw_speech_bubble(frame, text, sx, sy)

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
    """Render every scene. A character walks in the first time they appear
    in the episode, and is already in place in later scenes."""
    cfg = cfg or load_config()
    seen: set[str] = set()
    paths = []
    for scene in story["scenes"]:
        present = list(dict.fromkeys(line["speaker"] for line in scene.get("lines", [])))
        walk_in = [name for name in present if name not in seen]
        seen.update(present)
        paths.append(render_scene(project, scene, cfg, walk_in=walk_in))
    return paths
