"""End-to-end smoke test with fake providers - no network calls.

Verifies the full chain (character assets -> story -> per-scene render ->
final assembly) actually produces a non-empty mp4, without needing real API
keys or a real image/LLM backend.

Run with: python -m pytest tests/test_pipeline_smoke.py -q
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from providers.base import ImageProvider, LLMProvider  # noqa: E402
from pipeline import character_studio, script_writer, scene_renderer, video_assembler  # noqa: E402
import config as cg  # noqa: E402


class FakeImageProvider(ImageProvider):
    name = "fake"

    def generate_image(self, prompt: str, transparent_bg: bool = False, size: str = "1024x1024") -> bytes:
        w, h = (256, 256) if transparent_bg else (512, 384)
        mode = "RGBA" if transparent_bg else "RGB"
        color = (200, 100, 100, 255) if transparent_bg else (100, 150, 200)
        img = Image.new(mode, (w, h), color)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


class FakeLLMProvider(LLMProvider):
    name = "fake"

    def generate_script(self, theme, num_scenes, characters):
        cast_names = [c["name"] for c in characters]
        scenes = []
        for i in range(1, num_scenes + 1):
            scenes.append(
                {
                    "id": i,
                    "background_desc": f"a test background for scene {i}",
                    "camera": ["static", "zoom_in", "pan_left"][i % 3],
                    "lines": [
                        {"speaker": cast_names[0], "text": f"Hello from scene {i}."},
                    ],
                }
            )
        return {
            "title": "Test Episode",
            "synopsis": "A fake episode used for testing.",
            "characters": cast_names,
            "scenes": scenes,
        }


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(cg, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(character_studio, "get_project_dir", cg.get_project_dir)
    monkeypatch.setattr(script_writer, "get_project_dir", cg.get_project_dir)
    monkeypatch.setattr(scene_renderer, "get_project_dir", cg.get_project_dir)
    monkeypatch.setattr(video_assembler, "get_project_dir", cg.get_project_dir)
    return "smoke_test_project"


def test_full_pipeline_produces_final_video(project):
    image_provider = FakeImageProvider()
    llm_provider = FakeLLMProvider()

    character_studio.add_character(
        project=project,
        name="Randy",
        physical_description="a simple test character",
        personality="calm",
        role="lead",
        image_provider=image_provider,
    )

    story = script_writer.generate_story(
        project=project,
        theme="a test theme",
        num_scenes=2,
        llm_provider=llm_provider,
    )
    assert len(story["scenes"]) == 2

    cfg = cg.load_config()
    cfg["resolution"] = [320, 180]  # tiny + fast for the test
    cfg["fps"] = 10

    scene_renderer.ensure_backgrounds(project, story, image_provider)
    scene_paths = scene_renderer.render_project(project, story, cfg)
    assert len(scene_paths) == 2
    for p in scene_paths:
        assert p.exists()
        assert p.stat().st_size > 0

    final_path = video_assembler.assemble(project, cfg)
    assert final_path.exists()
    assert final_path.stat().st_size > 0
