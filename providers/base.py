"""Abstract provider interfaces.

To add a new backend: implement one (or both) of these ABCs in a new file
under `providers/`, then register the class in `providers/__init__.py`.
Nothing else in the codebase needs to change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class LLMProvider(ABC):
    """Generates a structured episode script (story.json) from a theme."""

    name: str = "base"

    @abstractmethod
    def generate_script(
        self,
        theme: str,
        num_scenes: int,
        characters: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Return a dict matching the story.json schema:

        {
          "title": str,
          "synopsis": str,
          "characters": [str, ...],
          "scenes": [
            {
              "id": int,
              "background_desc": str,
              "camera": "static" | "zoom_in" | "zoom_out" | "pan_left" | "pan_right",
              "lines": [{"speaker": str, "text": str}, ...]
            },
            ...
          ]
        }

        `characters` is a list of dicts with at least "name", and usually
        "physical_description", "personality", "role" (from each
        character's profile.json), so the script can stay in-character.
        """
        raise NotImplementedError


class ImageProvider(ABC):
    """Generates a single raster image from a text prompt."""

    name: str = "base"

    @abstractmethod
    def generate_image(
        self,
        prompt: str,
        transparent_bg: bool = False,
        size: str = "1024x1024",
    ) -> bytes:
        """Return raw image bytes (PNG). `transparent_bg` is a best-effort
        hint - not every backend supports a true alpha channel natively;
        callers that need a real cutout should post-process the result
        (see `pipeline.character_studio`)."""
        raise NotImplementedError
