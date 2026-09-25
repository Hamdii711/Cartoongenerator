"""Provider registry.

Adding a new backend: write a new module implementing `LLMProvider` and/or
`ImageProvider` from `providers/base.py`, then add one line to the
registries below. Nothing else needs to change - `main.py` and the pipeline
only ever go through `get_llm_provider` / `get_image_provider`.
"""

from __future__ import annotations

from typing import Dict, Type

from .base import ImageProvider, LLMProvider
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider

LLM_PROVIDERS: Dict[str, Type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
}

IMAGE_PROVIDERS: Dict[str, Type[ImageProvider]] = {
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
}


def get_llm_provider(name: str) -> LLMProvider:
    try:
        cls = LLM_PROVIDERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown LLM provider {name!r}. Available: {sorted(LLM_PROVIDERS)}"
        )
    return cls()


def get_image_provider(name: str) -> ImageProvider:
    try:
        cls = IMAGE_PROVIDERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown image provider {name!r}. Available: {sorted(IMAGE_PROVIDERS)}"
        )
    return cls()


__all__ = [
    "LLMProvider",
    "ImageProvider",
    "LLM_PROVIDERS",
    "IMAGE_PROVIDERS",
    "get_llm_provider",
    "get_image_provider",
]
