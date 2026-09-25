"""Turn a theme + a project's cast into a story.json episode script."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from config import get_project_dir
from pipeline.character_studio import list_characters, load_profile
from providers.base import LLMProvider


def _collect_cast(project: str, character_names: List[str] | None) -> List[Dict[str, Any]]:
    names = character_names or list_characters(project)
    if not names:
        raise ValueError(
            f"Project {project!r} has no characters yet - run `character add` first, "
            f"or pass --characters."
        )
    return [load_profile(project, name) for name in names]


def _validate_story(story: Dict[str, Any], num_scenes: int, cast_names: List[str]) -> None:
    if "scenes" not in story or not isinstance(story["scenes"], list):
        raise ValueError("LLM response is missing a 'scenes' list")
    if len(story["scenes"]) != num_scenes:
        raise ValueError(
            f"Expected {num_scenes} scenes, got {len(story['scenes'])}"
        )
    cast_set = set(cast_names)
    for scene in story["scenes"]:
        for key in ("id", "background_desc", "camera", "lines"):
            if key not in scene:
                raise ValueError(f"Scene missing required field {key!r}: {scene}")
        for line in scene["lines"]:
            if line.get("speaker") not in cast_set:
                raise ValueError(
                    f"Scene {scene.get('id')} has a line from unknown speaker "
                    f"{line.get('speaker')!r} (cast: {sorted(cast_set)})"
                )


def generate_story(
    project: str,
    theme: str,
    num_scenes: int,
    llm_provider: LLMProvider,
    character_names: List[str] | None = None,
) -> Dict[str, Any]:
    proj_dir = get_project_dir(project, create=True)
    cast = _collect_cast(project, character_names)
    cast_names = [c["name"] for c in cast]

    story = llm_provider.generate_script(theme, num_scenes, cast)
    _validate_story(story, num_scenes, cast_names)
    story.setdefault("characters", cast_names)

    story_path = proj_dir / "story.json"
    with open(story_path, "w", encoding="utf-8") as f:
        json.dump(story, f, ensure_ascii=False, indent=2)

    return story


def load_story(project: str) -> Dict[str, Any]:
    path = get_project_dir(project) / "story.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No story.json for project {project!r} - run `script generate` first."
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
