"""OpenAI backend: LLM for scripts (chat completions) + image generation
(gpt-image-1)."""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List

from .base import LLMProvider, ImageProvider
from .prompts import SCRIPT_SYSTEM_PROMPT, build_user_prompt

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - exercised only when dependency missing
    OpenAI = None  # type: ignore

from config import get_api_key


class OpenAIProvider(LLMProvider, ImageProvider):
    name = "openai"

    def __init__(self, model: str = "gpt-4o", image_model: str = "gpt-image-1"):
        if OpenAI is None:
            raise RuntimeError(
                "The 'openai' package is not installed. Run: pip install -r requirements.txt"
            )
        self.client = OpenAI(api_key=get_api_key("OPENAI_API_KEY"))
        self.model = model
        self.image_model = image_model

    def generate_script(
        self, theme: str, num_scenes: int, characters: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        user_prompt = build_user_prompt(theme, num_scenes, characters)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SCRIPT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.9,
        )
        content = response.choices[0].message.content
        return json.loads(content)

    def generate_image(
        self, prompt: str, transparent_bg: bool = False, size: str = "1024x1024"
    ) -> bytes:
        kwargs: Dict[str, Any] = {
            "model": self.image_model,
            "prompt": prompt,
            "size": size,
            "n": 1,
        }
        if transparent_bg:
            kwargs["background"] = "transparent"
        result = self.client.images.generate(**kwargs)
        b64 = result.data[0].b64_json
        return base64.b64decode(b64)
