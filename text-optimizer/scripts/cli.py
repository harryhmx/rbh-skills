#!/usr/bin/env python3
"""CLI entry point for text-optimizer — AI-powered semantic text splitting,
prompt generation for segments, and single image/video prompt generation.

Usage:
    python scripts/cli.py split -i <text-or-file> [-n <count>] [-f json|md|text] [-o <path>] [--max-words N] [--max-chars N] [--prompts] [--prompt-types image,video,tts]
    python scripts/cli.py prompts -i <segments.json> [-o <path>] [--prompt-types image,video,tts]
    python scripts/cli.py genprompt -i <text-or-file> -t image|video [-o <path>] [--size WxH] [--num-frames N] [--frame-rate FPS]
    python scripts/cli.py multiprompt -i <text-or-file> -t image|video [-n <count>] [-o <path>] [--size WxH] [--num-frames N] [--frame-rate FPS]

Examples:
    # Auto segment count, print JSON to stdout
    python scripts/cli.py split -i article.md

    # 5 segments with word-count limit (one AI call does both)
    python scripts/cli.py split -i article.md -n 5 --max-words 200 -f md

    # Split AND generate all image/video/TTS prompts
    python scripts/cli.py split -i article.md -n 4 --prompts -f json -o result.json

    # Split and generate only image prompts
    python scripts/cli.py split -i article.md -n 4 --prompts --prompt-types image -f json

    # Split and generate image + TTS prompts (no video)
    python scripts/cli.py split -i article.md -n 4 --prompts --prompt-types image,tts -f json

    # Generate prompts from existing segments JSON
    python scripts/cli.py prompts -i segments.json -o prompts.json

    # Generate a single image prompt from text
    python scripts/cli.py genprompt -i article.md -t image -o my-image-prompt.md

    # Generate a single video prompt, print to stdout
    python scripts/cli.py genprompt -t video -i "A physics lecture explaining quantum mechanics"

    # Generate video prompt with custom settings
    python scripts/cli.py genprompt -i article.md -t video --size 1920x1080 --num-frames 241 --frame-rate 30

    # Generate 4 different image prompt versions from text (default count)
    python scripts/cli.py multiprompt -t image -i article.md -o prompts.json

    # Generate 6 video prompt versions
    python scripts/cli.py multiprompt -t video -i article.md -n 6 -o video-prompts.json

    # Then feed to content-production for batch generation
    python ../content-production/scripts/cli.py image -i prompts.json -o images/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_skill_dir = Path(__file__).resolve().parents[1]
if str(_skill_dir) not in sys.path:
    sys.path.insert(0, str(_skill_dir))

from scripts.optimizer import (  # noqa: E402
    format_output,
    format_prompt_file,
    generate_multiple_prompts,
    generate_prompts,
    generate_single_prompt,
    read_input,
    split_text,
)


VALID_PROMPT_TYPES = {"image", "video", "tts"}


def _parse_prompt_types(raw: str | None) -> frozenset[str]:
    """Parse a comma-separated *raw* string into a frozenset of prompt types.

    ``"all"`` or ``""`` → all types; ``"image,tts"`` → ``{"image", "tts"}``.
    """
    if raw is None or raw.strip() == "":
        return frozenset(VALID_PROMPT_TYPES)
    raw = raw.strip().lower()
    if raw == "all":
        return frozenset(VALID_PROMPT_TYPES)
    selected = {t.strip() for t in raw.split(",") if t.strip()}
    invalid = selected - VALID_PROMPT_TYPES
    if invalid:
        print(
            f"Error: unknown prompt types: {sorted(invalid)}. "
            f"Valid: {sorted(VALID_PROMPT_TYPES)}",
            file=sys.stderr,
        )
        sys.exit(1)
    return frozenset(selected)


def cmd_split(args: argparse.Namespace) -> None:
    """Handle the ``split`` subcommand."""
    # 1. Read input
    source = args.input
    if source is None:
        if not sys.stdin.isatty():
            source = sys.stdin.read().strip()
        else:
            print("Error: --input is required (or pipe text via stdin)", file=sys.stderr)
            sys.exit(1)

    text = read_input(source)
    if not text.strip():
        print("Error: input text is empty", file=sys.stderr)
        sys.exit(1)

    # 2. Split via AI (one call handles split + condense)
    try:
        segments = split_text(
            text,
            num_segments=args.segments,
            max_words=args.max_words,
            max_chars=args.max_chars,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if not segments:
        print("Warning: no segments produced", file=sys.stderr)
        sys.exit(0)

    # 3. Optionally generate prompts
    if args.prompts:
        prompt_types = _parse_prompt_types(getattr(args, "prompt_types", "all"))
        segments = generate_prompts(segments, types=prompt_types)

    # 4. Format & output
    output = format_output(segments, args.format)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output, encoding="utf-8")
        print(f"Output written to: {out_path.resolve()}", file=sys.stderr)
    else:
        print(output)


def cmd_prompts(args: argparse.Namespace) -> None:
    """Handle the ``prompts`` subcommand — generate prompts from a segments JSON."""
    # 1. Read existing segments JSON
    source = args.input
    if source is None:
        print("Error: --input is required (path to segments JSON file)", file=sys.stderr)
        sys.exit(1)

    input_path = Path(source)
    if not input_path.exists() or not input_path.is_file():
        print(f"Error: file not found: {source}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {source}: {exc}", file=sys.stderr)
        sys.exit(1)

    segments = data.get("segments", [])
    if not segments:
        print("Error: no segments found in input JSON (expected key 'segments')", file=sys.stderr)
        sys.exit(1)

    # 2. Generate prompts via AI
    try:
        prompt_types = _parse_prompt_types(getattr(args, "prompt_types", "all"))
        segments = generate_prompts(segments, types=prompt_types)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # 3. Format & output
    output = json.dumps(
        {"total_segments": len(segments), "segments": segments},
        ensure_ascii=False, indent=2,
    )

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output, encoding="utf-8")
        print(f"Output written to: {out_path.resolve()}", file=sys.stderr)
    else:
        print(output)


def cmd_genprompt(args: argparse.Namespace) -> None:
    """Handle the ``genprompt`` subcommand — generate a single image/video prompt."""
    # 1. Read input
    source = args.input
    if source is None:
        print("Error: --input is required", file=sys.stderr)
        sys.exit(1)

    text = read_input(source)
    if not text.strip():
        print("Error: input text is empty", file=sys.stderr)
        sys.exit(1)

    # 2. Generate single prompt via AI
    try:
        prompt_text = generate_single_prompt(
            text,
            prompt_type=args.type,
            size=args.size,
            num_frames=args.num_frames,
            frame_rate=args.frame_rate,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # 3. Format in proprietary prompt file format
    output = format_prompt_file(
        prompt_text,
        prompt_type=args.type,
        size=args.size,
        num_frames=args.num_frames,
        frame_rate=args.frame_rate,
    )

    # 4. Output
    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output, encoding="utf-8")
        print(f"Output written to: {out_path.resolve()}", file=sys.stderr)
    else:
        print(output)


def cmd_multiprompt(args: argparse.Namespace) -> None:
    """Handle the ``multiprompt`` subcommand — generate multiple image/video prompt versions."""
    # 1. Read input
    source = args.input
    if source is None:
        print("Error: --input is required", file=sys.stderr)
        sys.exit(1)

    text = read_input(source)
    if not text.strip():
        print("Error: input text is empty", file=sys.stderr)
        sys.exit(1)

    # 2. Generate multiple prompt versions via AI
    try:
        segments = generate_multiple_prompts(
            text,
            prompt_type=args.type,
            count=args.count,
            size=args.size,
            num_frames=args.num_frames,
            frame_rate=args.frame_rate,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # 3. Wrap in the standard segments JSON format for content-production
    output = json.dumps(
        {"total_segments": len(segments), "segments": segments},
        ensure_ascii=False, indent=2,
    )

    # 4. Output
    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output, encoding="utf-8")
        print(f"Output written to: {out_path.resolve()}", file=sys.stderr)
    else:
        print(output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Text Optimizer — AI-powered semantic text splitting, prompt generation (single + multi-version)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ---- split ----
    split_parser = subparsers.add_parser("split", help="Split text into segments")
    split_parser.add_argument(
        "-i", "--input",
        help="Raw text string or path to .md/.txt file (omit to read from stdin)",
    )
    split_parser.add_argument(
        "-n", "--segments",
        type=int,
        default=None,
        help="Target number of segments (omit to auto-determine)",
    )
    split_parser.add_argument(
        "-f", "--format",
        choices=["json", "md", "text"],
        default="json",
        help="Output format (default: json)",
    )
    split_parser.add_argument(
        "-o", "--output",
        help="Output file path (omit to print to stdout)",
    )
    split_parser.add_argument(
        "--max-words",
        type=int,
        default=None,
        help="Maximum words per segment — AI condenses oversize segments",
    )
    split_parser.add_argument(
        "--max-chars",
        type=int,
        default=None,
        help="Maximum characters per segment (useful for CJK text). When both limits are set, the stricter one applies.",
    )
    split_parser.add_argument(
        "--prompts",
        action="store_true",
        help="Generate image/video/TTS prompts for each segment via AI",
    )
    split_parser.add_argument(
        "--prompt-types",
        default="all",
        help="Prompt types to generate: image,video,tts (comma-separated, or 'all'). Default: all",
    )

    # ---- prompts ----
    prompts_parser = subparsers.add_parser(
        "prompts",
        help="Generate image/video/TTS prompts from an existing segments JSON file",
    )
    prompts_parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to segments JSON file (from 'split' command)",
    )
    prompts_parser.add_argument(
        "-o", "--output",
        help="Output file path (omit to print to stdout)",
    )
    prompts_parser.add_argument(
        "--prompt-types",
        default="all",
        help="Prompt types to generate: image,video,tts (comma-separated, or 'all'). Default: all",
    )

    # ---- genprompt ----
    genprompt_parser = subparsers.add_parser(
        "genprompt",
        help="Generate a single image or video prompt from text (writes proprietary format for content-production)",
    )
    genprompt_parser.add_argument(
        "-i", "--input",
        help="Raw text string or path to .md/.txt file",
    )
    genprompt_parser.add_argument(
        "-t", "--type",
        required=True,
        choices=["image", "video"],
        help="Prompt type: 'image' or 'video'",
    )
    genprompt_parser.add_argument(
        "-o", "--output",
        help="Output file path (.md or .txt). Omit to print to stdout.",
    )
    genprompt_parser.add_argument(
        "--size",
        default="1024x768",
        help="Target size in WxH format (default: 1024x768)",
    )
    genprompt_parser.add_argument(
        "--num-frames",
        type=int,
        default=121,
        help="Number of frames — video only (default: 121)",
    )
    genprompt_parser.add_argument(
        "--frame-rate",
        type=float,
        default=24,
        help="Frame rate in FPS — video only (default: 24)",
    )

    # ---- multiprompt ----
    multiprompt_parser = subparsers.add_parser(
        "multiprompt",
        help="Generate multiple image or video prompt versions from text (outputs JSON for content-production batch)",
    )
    multiprompt_parser.add_argument(
        "-i", "--input",
        help="Raw text string or path to .md/.txt file",
    )
    multiprompt_parser.add_argument(
        "-t", "--type",
        required=True,
        choices=["image", "video"],
        help="Prompt type: 'image' or 'video'",
    )
    multiprompt_parser.add_argument(
        "-n", "--count",
        type=int,
        default=4,
        help="Number of prompt versions to generate (default: 4, min: 2, max: 10)",
    )
    multiprompt_parser.add_argument(
        "-o", "--output",
        help="Output JSON file path. Omit to print to stdout.",
    )
    multiprompt_parser.add_argument(
        "--size",
        default="1024x768",
        help="Target size in WxH format (default: 1024x768)",
    )
    multiprompt_parser.add_argument(
        "--num-frames",
        type=int,
        default=121,
        help="Number of frames — video only (default: 121)",
    )
    multiprompt_parser.add_argument(
        "--frame-rate",
        type=float,
        default=24,
        help="Frame rate in FPS — video only (default: 24)",
    )

    args = parser.parse_args()

    if args.command == "split":
        cmd_split(args)
    elif args.command == "prompts":
        cmd_prompts(args)
    elif args.command == "genprompt":
        cmd_genprompt(args)
    elif args.command == "multiprompt":
        cmd_multiprompt(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
