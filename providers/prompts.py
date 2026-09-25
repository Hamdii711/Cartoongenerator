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
