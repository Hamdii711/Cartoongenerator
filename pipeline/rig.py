"""Articulated cutout character rigs.

Instead of swapping a handful of whole-body pose images (see
`character_studio`), a rigged character is built from separate body-part
images - torso, head (x3 mouth/eye variants), 2 arms, 2 legs - each
generated in isolation by the image provider. The renderer animates the
character by ROTATING each limb around a fixed joint every frame, like a
real paper-cutout puppet, instead of swapping flat pose art. This is what
gives real leg/arm movement (walking, idle sway) rather than a static pose
sliding across the screen.

Each part image follows a fixed cropping convention baked into its prompt
(see `providers/prompts.py::build_rig_part_prompt`):
  - an arm/leg image's own TOP edge is the joint (shoulder/hip);
  - a head image's own BOTTOM edge is the neck cut.
That convention is what lets us rotate/place parts using fixed anchor
fractions instead of trying to detect joints in the generated image.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

from PIL import Image

from pipeline.character_studio import _ensure_alpha, character_dir
from providers.base import ImageProvider
from providers.prompts import build_rig_part_prompt

# part name -> (base part passed to the prompt builder, head variant or None)
PART_SPECS: Dict[str, Tuple[str, str | None]] = {
    "torso": ("torso", None),
    "head_neutral": ("head", "neutral"),
    "head_talk": ("head", "talk"),
    "head_blink": ("head", "blink"),
    "arm_left": ("arm", None),
    "arm_right": ("arm", None),
    "leg_left": ("leg", None),
    "leg_right": ("leg", None),
}

# Attachment sockets, as fractions of the TORSO's own (width, height), where
# each limb/head's own anchor point is pinned. Fixed conventions tuned for a
# simple humanoid cutout silhouette - not detected from the generated art.
SOCKETS: Dict[str, Tuple[float, float]] = {
    "neck": (0.5, 0.0),
    "arm_left": (0.12, 0.10),
    "arm_right": (0.88, 0.10),
    # y=1.0 exactly (torso's own bottom edge): keeps the standing height
    # (head + torso + leg, computed in load_rig) consistent with where the
    # leg is actually placed, so a straight-standing figure's feet land
    # exactly on the canvas's bottom row - no gap, no overlap.
    "leg_left": (0.34, 1.0),
    "leg_right": (0.66, 1.0),
}

# Each part image's own attachment point, as a fraction of ITS OWN size.
PART_ANCHOR: Dict[str, Tuple[float, float]] = {
    "arm_left": (0.5, 0.0),
    "arm_right": (0.5, 0.0),
    "leg_left": (0.5, 0.0),
    "leg_right": (0.5, 0.0),
    "head_neutral": (0.5, 1.0),
    "head_talk": (0.5, 1.0),
    "head_blink": (0.5, 1.0),
}

HEAD_VARIANTS = ("neutral", "talk", "blink")


def rig_path(project: str, name: str) -> Path:
    return character_dir(project, name) / "rig.json"


def is_rigged(project: str, name: str) -> bool:
    return rig_path(project, name).exists()


def generate_rig(
    project: str,
    name: str,
    physical_description: str,
    personality: str,
    role: str,
    image_provider: ImageProvider,
) -> Dict[str, Any]:
    """Generate every body part with the image provider and save the rig.

    Known limitation: each part is a separate generation call, so color/
    style can drift slightly between parts (e.g. skin tone on the arm vs the
    head) even though every prompt repeats the same physical description -
    the image provider has no reference image of the other parts to match
    against. Retouching a part by hand (same file layout under
    characters/<name>/) is always possible; the render pipeline only cares
    about the files on disk.
    """
    c_dir = character_dir(project, name)
    c_dir.mkdir(parents=True, exist_ok=True)

    profile = {
        "name": name,
        "physical_description": physical_description,
        "personality": personality,
        "role": role,
        "rigged": True,
    }
    with open(c_dir / "profile.json", "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    paths: Dict[str, str] = {}
    for part_name, (base_part, variant) in PART_SPECS.items():
        prompt = build_rig_part_prompt(base_part, physical_description, personality, variant)
        raw = image_provider.generate_image(prompt, transparent_bg=True)
        img = _ensure_alpha(raw)
        out_path = c_dir / f"{part_name}.png"
        img.save(out_path)
        paths[part_name] = str(out_path)

    rig = {"parts": paths, "sockets": SOCKETS, "part_anchor": PART_ANCHOR}
    with open(rig_path(project, name), "w", encoding="utf-8") as f:
        json.dump(rig, f, ensure_ascii=False, indent=2)

    return {"name": name, "dir": str(c_dir), "paths": paths, "profile": profile, "rigged": True}


@dataclass
class LoadedRig:
    """A rig's parts pre-scaled to a target character height, ready to be
    posed and composited every frame without re-loading/re-scaling."""

    parts: Dict[str, Image.Image]
    sockets: Dict[str, Tuple[float, float]]
    anchors: Dict[str, Tuple[float, float]]
    char_height: int

    def canvas_size(self) -> Tuple[int, int]:
        arm = self.parts["arm_left"]
        head = self.parts["head_neutral"]
        margin_x = int(arm.width * 1.8)
        margin_top = int(head.height * 0.35)
        width = self.parts["torso"].width + 2 * margin_x
        height = self.char_height + margin_top
        return width, height

    def compose(
        self,
        head_variant: str = "neutral",
        leg_left_angle: float = 0.0,
        leg_right_angle: float = 0.0,
        arm_left_angle: float = 0.0,
        arm_right_angle: float = 0.0,
    ) -> Image.Image:
        """Render one posed frame. Returned image's bottom edge is exactly
        the standing feet line (angle=0 for both legs) - callers position it
        the same way as a flat pose sprite: bottom-center at the floor."""
        cw, ch = self.canvas_size()
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))

        torso = self.parts["torso"]
        head = self.parts[f"head_{head_variant}"]
        margin_top = ch - self.char_height
        torso_top = margin_top + head.height
        torso_left = (cw - torso.width) // 2

        def socket_point(socket_name: str) -> Tuple[float, float]:
            fx, fy = self.sockets[socket_name]
            return torso_left + fx * torso.width, torso_top + fy * torso.height

        def paste_rotated(part_name: str, angle: float, socket_name: str) -> None:
            img = self.parts[part_name]
            ax_f, ay_f = self.anchors[part_name]
            anchor_px = (img.width * ax_f, img.height * ay_f)
            rotated = img.rotate(angle, resample=Image.BICUBIC, center=anchor_px, expand=False)
            sx, sy = socket_point(socket_name)
            canvas.alpha_composite(rotated, (int(sx - anchor_px[0]), int(sy - anchor_px[1])))

        # Draw order: legs behind the torso, then the torso, then arms in
        # front, then the head on top - a standard paper-doll layering.
        paste_rotated("leg_left", leg_left_angle, "leg_left")
        paste_rotated("leg_right", leg_right_angle, "leg_right")
        canvas.alpha_composite(torso, (torso_left, torso_top))
        paste_rotated("arm_left", arm_left_angle, "arm_left")
        paste_rotated("arm_right", arm_right_angle, "arm_right")

        nx, ny = socket_point("neck")
        hax, hay = self.anchors[f"head_{head_variant}"]
        head_anchor_px = (head.width * hax, head.height * hay)
        canvas.alpha_composite(head, (int(nx - head_anchor_px[0]), int(ny - head_anchor_px[1])))

        return canvas


def load_rig(project: str, name: str, char_height: int) -> LoadedRig:
    with open(rig_path(project, name), "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_parts = {part: Image.open(path).convert("RGBA") for part, path in data["parts"].items()}
    # Uniform scale so a standing figure (head + torso + one straight leg,
    # stacked) is exactly `char_height` tall.
    standing_height = (
        raw_parts["head_neutral"].height + raw_parts["torso"].height + raw_parts["leg_left"].height
    )
    scale = char_height / max(1, standing_height)
    parts = {
        part: img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
        for part, img in raw_parts.items()
    }
    return LoadedRig(parts=parts, sockets=data["sockets"], anchors=data["part_anchor"], char_height=char_height)


def walk_leg_angle(t: float, step_duration: float, amplitude_deg: float, phase: float = 0.0) -> float:
    """Swing angle (degrees) for a leg in a walk cycle at time t."""
    return amplitude_deg * math.sin(2 * math.pi * t / step_duration + phase)


def idle_sway_angle(t: float, period: float, amplitude_deg: float, phase: float = 0.0) -> float:
    """Small idle sway angle (degrees) so a standing rig never looks frozen."""
    return amplitude_deg * math.sin(2 * math.pi * t / period + phase)
