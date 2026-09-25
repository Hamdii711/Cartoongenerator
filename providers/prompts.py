"""Shared prompt text used by every LLM provider, so they all target the
exact same story.json contract regardless of backend."""

SCRIPT_SYSTEM_PROMPT = """You are a scriptwriter for a short 2D cutout-style \
animated cartoon episode (visual style: flat cutout paper-craft art, in the \
spirit of South Park - simple shapes, static camera cuts, sitcom pacing).

Given a theme and a cast of characters (with physical description, \
personality/traits and role), write one short episode broken into scenes.

Respond with ONLY valid JSON (no markdown code fences, no commentary)
matching exactly this schema:

{
  "title": "<short episode title>",
  "synopsis": "<2-3 sentence summary of the episode>",
  "characters": ["<name>", ...],
  "scenes": [
    {
      "id": <integer, starting at 1, sequential>,
      "background_desc": "<visual description of the setting, flat 2D cutout art style, no characters mentioned here>",
      "camera": "static" | "zoom_in" | "zoom_out" | "pan_left" | "pan_right",
      "lines": [
        {"speaker": "<must be one of the given character names>", "text": "<short line, 1-2 sentences>"}
      ]
    }
  ]
}

Rules:
- Produce EXACTLY the requested number of scenes.
- "speaker" must always be one of the given character names, spelled exactly.
- Keep dialogue short and punchy, like sitcom dialogue meant to be read as subtitles.
- Reflect each character's stated personality/traits in how they talk.
- "background_desc" must describe only the setting/environment, not the characters.
- Vary the "camera" value across scenes instead of repeating the same one every time.
"""


def format_cast(characters: list[dict]) -> str:
    lines = []
    for c in characters:
        lines.append(
            f"- {c.get('name', '?')}: "
            f"{c.get('physical_description', 'no description given')} | "
            f"personality: {c.get('personality', 'not specified')} | "
            f"role: {c.get('role', 'not specified')}"
        )
    return "\n".join(lines)


def build_user_prompt(theme: str, num_scenes: int, characters: list[dict]) -> str:
    return (
        f"Theme: {theme}\n"
        f"Number of scenes: {num_scenes}\n"
        f"Cast:\n{format_cast(characters)}\n"
    )


CUTOUT_STYLE_SUFFIX = (
    "flat 2D cutout paper-craft cartoon style, in the spirit of South Park, "
    "simple bold black outlines, solid flat colors, no gradients, no shading, "
    "no text, no watermark"
)

CHARACTER_POSE_PROMPTS = {
    "neutral": "standing in a neutral idle pose, mouth closed, facing forward",
    "talk": "standing in the same neutral idle pose, mouth open wide as if mid-speech, facing forward",
    "blink": "standing in the same neutral idle pose, eyes closed as if blinking, mouth closed, facing forward",
}


def build_character_prompt(physical_description: str, personality: str, pose: str) -> str:
    pose_desc = CHARACTER_POSE_PROMPTS.get(pose, CHARACTER_POSE_PROMPTS["neutral"])
    return (
        f"A single cartoon character, full body, centered, isolated on a plain "
        f"solid white background (no scenery, no objects, no shadow): "
        f"{physical_description}. Personality conveyed through pose/expression: "
        f"{personality}. {pose_desc}. {CUTOUT_STYLE_SUFFIX}."
    )


def build_background_prompt(background_desc: str) -> str:
    return f"A background illustration, no characters in it: {background_desc}. {CUTOUT_STYLE_SUFFIX}."


# ---------------------------------------------------------------------------
# Articulated rig parts
#
# Each body part is generated as its own isolated image so the renderer can
# rotate it around a joint (see pipeline/rig.py) instead of swapping whole-
# body pose images. The prompts fix a cropping convention per part (where the
# joint sits at the very edge of the image) so the renderer can rely on a
# consistent anchor point without needing to detect it.
# ---------------------------------------------------------------------------

RIG_PART_INSTRUCTIONS = {
    "head": (
        "Just the character's head and neck, facing forward, cropped tightly: "
        "the bottom edge of the image is exactly the neck cut, where it plugs "
        "into the body"
    ),
    "torso": (
        "Just the character's torso: chest, belly and hips as one rounded "
        "body shape, no head, no arms, no legs attached. Cropped tightly: the "
        "top edge of the image is exactly the neck socket (where the head "
        "plugs in), the bottom edge is exactly the hip line (where the legs "
        "plug in)"
    ),
    "arm": (
        "A single detached arm, from shoulder to hand, hanging straight down "
        "vertically, no torso attached. Cropped tightly so the very top edge "
        "of the image is exactly the shoulder joint (where it plugs into the "
        "torso)"
    ),
    "leg": (
        "A single detached leg, from hip to foot, straight and vertical, no "
        "torso attached. Cropped tightly so the very top edge of the image is "
        "exactly the hip joint (where it plugs into the torso)"
    ),
}

RIG_HEAD_VARIANT_DESC = {
    "neutral": "Mouth closed, eyes open, neutral expression.",
    "talk": "Mouth open wide as if speaking mid-sentence, eyes open.",
    "blink": "Eyes closed as if blinking, mouth closed.",
}


def build_rig_part_prompt(part: str, physical_description: str, personality: str, variant: str | None = None) -> str:
    """`part` is one of "head", "torso", "arm", "leg". For "head", `variant`
    is one of "neutral"/"talk"/"blink"."""
    variant_desc = RIG_HEAD_VARIANT_DESC.get(variant, "") if part == "head" else ""
    return (
        f"A single isolated body part cut out flat from a paper-cutout puppet "
        f"rig, like a toy action figure part - NOT a full character, just this "
        f"one piece: {RIG_PART_INSTRUCTIONS[part]}. "
        f"Character this part belongs to: {physical_description}. Personality: "
        f"{personality}. Use the exact same colors, proportions, skin tone and "
        f"outfit as the rest of this same character's body. {variant_desc} "
        f"Plain solid white background, no shadow, symmetrical, facing "
        f"straight forward, no other body parts visible. {CUTOUT_STYLE_SUFFIX}."
    )
