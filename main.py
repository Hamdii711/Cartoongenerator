#!/usr/bin/env python3
"""CLI entry point for the cartoon generator.

Designed to be driven by an AI agent, not a human: every command prints a
single JSON object on stdout on success, or a JSON error object on stderr
plus a non-zero exit code on failure. No interactive prompts.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from typing import Any, Dict

from config import load_config
from pipeline import character_studio, script_writer, scene_renderer, video_assembler
from providers import get_image_provider, get_llm_provider


def _print_ok(payload: Dict[str, Any]) -> None:
    print(json.dumps({"status": "ok", **payload}, ensure_ascii=False))


def _print_error(message: str) -> None:
    print(json.dumps({"status": "error", "message": message}), file=sys.stderr)


def cmd_character_add(args: argparse.Namespace) -> Dict[str, Any]:
    cfg = load_config()
    provider_name = args.provider or cfg["default_image_provider"]
    image_provider = get_image_provider(provider_name)
    result = character_studio.add_character(
        project=args.project,
        name=args.name,
        physical_description=args.description,
        personality=args.personality or "",
        role=args.role or "",
        image_provider=image_provider,
    )
    return result


def cmd_script_generate(args: argparse.Namespace) -> Dict[str, Any]:
    cfg = load_config()
    provider_name = args.provider or cfg["default_llm_provider"]
    llm_provider = get_llm_provider(provider_name)
    character_names = args.characters.split(",") if args.characters else None
    story = script_writer.generate_story(
        project=args.project,
        theme=args.theme,
        num_scenes=args.scenes,
        llm_provider=llm_provider,
        character_names=character_names,
    )
    return story


def cmd_render(args: argparse.Namespace) -> Dict[str, Any]:
    cfg = load_config()
    provider_name = args.image_provider or cfg["default_image_provider"]
    image_provider = get_image_provider(provider_name)
    story = script_writer.load_story(args.project)
    scene_renderer.ensure_backgrounds(args.project, story, image_provider)
    paths = scene_renderer.render_project(args.project, story, cfg)
    return {"project": args.project, "scenes": [str(p) for p in paths]}


def cmd_assemble(args: argparse.Namespace) -> Dict[str, Any]:
    cfg = load_config()
    out_path = video_assembler.assemble(args.project, cfg)
    return {"project": args.project, "output": str(out_path)}


def cmd_generate(args: argparse.Namespace) -> Dict[str, Any]:
    """Full pipeline: script -> render -> assemble. Characters must already
    exist in the project (added beforehand via `character add`)."""
    script_args = argparse.Namespace(
        project=args.project,
        theme=args.theme,
        scenes=args.scenes,
        provider=args.llm_provider,
        characters=args.characters,
    )
    story = cmd_script_generate(script_args)

    render_args = argparse.Namespace(project=args.project, image_provider=args.image_provider)
    render_result = cmd_render(render_args)

    assemble_args = argparse.Namespace(project=args.project)
    assemble_result = cmd_assemble(assemble_args)

    return {
        "project": args.project,
        "title": story.get("title"),
        "scenes": render_result["scenes"],
        "output": assemble_result["output"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cartoon_generator",
        description="Generate a South-Park-style 2D cutout cartoon episode, scene by scene, via pluggable AI providers.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_char = sub.add_parser("character", help="Manage a project's characters")
    char_sub = p_char.add_subparsers(dest="subcommand", required=True)
    p_char_add = char_sub.add_parser("add", help="Generate a new character's assets")
    p_char_add.add_argument("--project", required=True)
    p_char_add.add_argument("--name", required=True)
    p_char_add.add_argument("--description", required=True, help="Physical description")
    p_char_add.add_argument("--personality", default="", help="Personality / traits")
    p_char_add.add_argument("--role", default="", help="Role in the story")
    p_char_add.add_argument("--provider", default=None, help="Image provider (default from config.yaml)")
    p_char_add.set_defaults(func=cmd_character_add)

    p_script = sub.add_parser("script", help="Manage a project's story script")
    script_sub = p_script.add_subparsers(dest="subcommand", required=True)
    p_script_gen = script_sub.add_parser("generate", help="Generate story.json from a theme")
    p_script_gen.add_argument("--project", required=True)
    p_script_gen.add_argument("--theme", required=True)
    p_script_gen.add_argument("--scenes", type=int, required=True)
    p_script_gen.add_argument("--characters", default=None, help="Comma-separated character names (default: all in project)")
    p_script_gen.add_argument("--provider", default=None, help="LLM provider (default from config.yaml)")
    p_script_gen.set_defaults(func=cmd_script_generate)

    p_render = sub.add_parser("render", help="Render every scene of a project's story into a clip")
    p_render.add_argument("--project", required=True)
    p_render.add_argument("--image-provider", default=None, help="Image provider for backgrounds (default from config.yaml)")
    p_render.set_defaults(func=cmd_render)

    p_assemble = sub.add_parser("assemble", help="Concatenate a project's rendered scenes into final.mp4")
    p_assemble.add_argument("--project", required=True)
    p_assemble.set_defaults(func=cmd_assemble)

    p_generate = sub.add_parser("generate", help="Full pipeline: script -> render -> assemble")
    p_generate.add_argument("--project", required=True)
    p_generate.add_argument("--theme", required=True)
    p_generate.add_argument("--scenes", type=int, required=True)
    p_generate.add_argument("--characters", default=None, help="Comma-separated character names (default: all in project)")
    p_generate.add_argument("--llm-provider", default=None)
    p_generate.add_argument("--image-provider", default=None)
    p_generate.set_defaults(func=cmd_generate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.func(args)
    except Exception as exc:  # noqa: BLE001 - top-level CLI error boundary
        _print_error(f"{type(exc).__name__}: {exc}")
        if "--debug" in (argv or sys.argv):
            traceback.print_exc()
        return 1
    _print_ok(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
