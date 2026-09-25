"""Google Gemini backend: LLM for scripts + image generation (Imagen).

Imagen does not support a native transparent background, so when
`transparent_bg=True` we ask for a plain white backdrop instead; the caller
(`pipeline.character_studio`) turns that white background into real alpha
transparency.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .base import LLMProvider, ImageProvider
from .prompts import SCRIPT_SYSTEM_PROMPT, build_user_prompt

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover - exercised only when dependency missing
    genai = None  # type: ignore
    genai_types = None  # type: ignore

from config import get_api_key


class GeminiProvider(LLMProvider, ImageProvider):
    name = "gemini"

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        image_model: str = "imagen-3.0-generate-002",
    ):
        if genai is None:
            raise RuntimeError(
                "The 'google-genai' package is not installed. "
                "Run: pip install -r requirements.txt"
            )
        self.client = genai.Client(api_key=get_api_key("GEMINI_API_KEY"))
        self.model = model
        self.image_model = image_model

    def generate_script(
        self, theme: str, num_scenes: int, characters: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        prompt = SCRIPT_SYSTEM_PROMPT + "\n\n" + build_user_prompt(theme, num_scenes, characters)
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        return json.loads(response.text)

    def generate_image(
        self, prompt: str, transparent_bg: bool = False, size: str = "1024x1024"
    ) -> bytes:
        full_prompt = prompt
        if transparent_bg:
            full_prompt += (
                " Plain solid pure white background, no shadow, no gradient "
                "on the background."
            )
        response = self.client.models.generate_images(
            model=self.image_model,
            prompt=full_prompt,
            config=genai_types.GenerateImagesConfig(number_of_images=1),
        )
        image = response.generated_images[0].image
        return image.image_bytes
