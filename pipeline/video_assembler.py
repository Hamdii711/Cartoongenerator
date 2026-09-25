"""Concatenate a project's per-scene clips into the final episode video."""

from __future__ import annotations

from pathlib import Path
from typing import List

from moviepy import VideoFileClip, concatenate_videoclips, vfx

from config import get_project_dir, load_config


def assemble(project: str, cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    scenes_dir = get_project_dir(project) / "scenes"
    scene_paths = sorted(
        scenes_dir.glob("scene_*.mp4"),
        key=lambda p: int(p.stem.split("_")[1]),
    )
    if not scene_paths:
        raise FileNotFoundError(
            f"No rendered scenes found for project {project!r} - run `render` first."
        )

    fade = cfg["scene_transition_fade"]
    clips: List = []
    for path in scene_paths:
        clip = VideoFileClip(str(path))
        clip = clip.with_effects([vfx.FadeIn(fade), vfx.FadeOut(fade)])
        clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")
    out_path = get_project_dir(project) / "final.mp4"
    final.write_videofile(
        str(out_path),
        fps=cfg["fps"],
        codec="libx264",
        audio=False,
        logger=None,
    )
    for clip in clips:
        clip.close()
    final.close()
    return out_path
