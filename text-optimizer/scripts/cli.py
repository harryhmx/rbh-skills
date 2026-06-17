#!/usr/bin/env python3
"""CLI entry point for text-optimizer — AI-powered semantic text splitting,
unified text optimization, and prompt generation.

Usage:
    python scripts/cli.py split -i <file.md|.txt> [-n <count>] [-o <path>] [--prompts] [--prompt-types image,video] [--extra-requirements "..."]
    python scripts/cli.py prompts -i <segments.json> [-o <path>] [--prompt-types image,video]
    python scripts/cli.py optimize -i <text-or-file> [-n <count>] [-o <path>] [--fields text,image_prompt,...] [--direction auto|summarize|expand|refine] [--extra-requirements "..."]

Examples:
    # Split a file into segments (AI determines count)
    python scripts/cli.py split -i article.md

    # Split into 5 segments with extra requirements
    python scripts/cli.py split -i article.md -n 5 --extra-requirements "use simple language for children"

    # Split and generate image + video prompts
    python scripts/cli.py split -i article.md -n 4 --prompts --prompt-types image,video -o result.json

    # Generate prompts from existing segments JSON
    python scripts/cli.py prompts -i segments.json -o prompts.json

    # Optimize text (default: summarize/expand, single segment, text field only)
    python scripts/cli.py optimize -i article.md

    # Optimize: expand short text
    python scripts/cli.py optimize -i "A short sentence." --direction expand

    # Optimize: generate 4 different image prompts from text
    python scripts/cli.py optimize -i article.md -n 4 --fields image_prompt -o prompts.json

    # Optimize: generate text + image_prompt + video_prompt
    python scripts/cli.py optimize -i article.md --fields text,image_prompt,video_prompt

    # Then feed to content-production for batch generation
    python ../content-production/scripts/cli.py image -i result.json -o images/
    python ../content-production/scripts/cli.py video -i result.json -o videos/
    python ../content-production/scripts/cli.py speech -i result.json -o audio/
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
    generate_prompts,
    optimize_text,
    read_input,
    split_text,
    _parse_fields,
)

VALID_PROMPT_TYPES = {"image", "video"}


def _parse_prompt_types(raw: str | None) -> frozenset[str]:
    """Parse a comma-separated *raw* string into a frozenset of prompt types.

    ``"all"`` or ``""`` → all types; ``"image,video"`` → ``{"image", "video"}``.
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
    """Handle the ``split`` subcommand — semantic text splitting (file input only)."""
    # 1. Read input (must be .md or .txt file)
    source = args.input
    if source is None:
        print("Error: --input is required (path to .md or .txt file)", file=sys.stderr)
        sys.exit(1)

    input_path = Path(source)
    if not input_path.exists() or not input_path.is_file():
        print(f"Error: file not found: {source}", file=sys.stderr)
        sys.exit(1)
    if input_path.suffix.lower() not in (".md", ".txt"):
        print(
            f"Error: input must be .md or .txt file, got: {input_path.suffix}",
            file=sys.stderr,
        )
        sys.exit(1)

    text = input_path.read_text(encoding="utf-8")
    if not text.strip():
        print("Error: input file is empty", file=sys.stderr)
        sys.exit(1)

    # 2. Split via AI (one call handles split — no length limits)
    try:
        segments = split_text(
            text,
            num_segments=args.segments,
            extra_requirements=args.extra_requirements or "",
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

    # 4. Output (always JSON)
    output = format_output(segments)

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

    # 3. Output (always JSON)
    output = format_output(segments)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output, encoding="utf-8")
        print(f"Output written to: {out_path.resolve()}", file=sys.stderr)
    else:
        print(output)


def cmd_optimize(args: argparse.Namespace) -> None:
    """Handle the ``optimize`` subcommand — unified text optimization and prompt generation."""
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

    # 2. Parse and validate fields
    try:
        fields = _parse_fields(getattr(args, "fields", "text") or "text")
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # 3. Optimize via AI
    try:
        segments = optimize_text(
            text=text,
            num_segments=args.segments,
            fields=fields,
            direction=args.direction,
            extra_requirements=args.extra_requirements or "",
        )
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if not segments:
        print("Warning: no segments produced", file=sys.stderr)
        sys.exit(0)

    # 4. Output (always JSON)
    output = format_output(segments)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output, encoding="utf-8")
        print(f"Output written to: {out_path.resolve()}", file=sys.stderr)
    else:
        print(output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Text Optimizer — AI-powered semantic text splitting, unified optimization, and prompt generation",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ---- split ----
    split_parser = subparsers.add_parser(
        "split",
        help="Split a .md or .txt file into semantically coherent segments",
    )
    split_parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to .md or .txt file to split",
    )
    split_parser.add_argument(
        "-n", "--segments",
        type=int,
        default=None,
        help="Target number of segments (omit to auto-determine)",
    )
    split_parser.add_argument(
        "-o", "--output",
        help="Output JSON file path (omit to print to stdout)",
    )
    split_parser.add_argument(
        "--prompts",
        action="store_true",
        help="Generate image/video prompts for each segment via AI",
    )
    split_parser.add_argument(
        "--prompt-types",
        default="all",
        help="Prompt types to generate: image,video (comma-separated, or 'all'). Default: all",
    )
    split_parser.add_argument(
        "--extra-requirements",
        default="",
        help="Additional requirements appended to the AI prompt (e.g. 'use simple language for children')",
    )

    # ---- prompts ----
    prompts_parser = subparsers.add_parser(
        "prompts",
        help="Generate image/video prompts from an existing segments JSON file",
    )
    prompts_parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to segments JSON file (from 'split' or 'optimize' command)",
    )
    prompts_parser.add_argument(
        "-o", "--output",
        help="Output JSON file path (omit to print to stdout)",
    )
    prompts_parser.add_argument(
        "--prompt-types",
        default="all",
        help="Prompt types to generate: image,video (comma-separated, or 'all'). Default: all",
    )

    # ---- optimize ----
    optimize_parser = subparsers.add_parser(
        "optimize",
        help="Unified text optimization and prompt generation (replaces genprompt + multiprompt). "
             "Transforms text via AI: summarize, expand, refine, or generate image/video prompts.",
    )
    optimize_parser.add_argument(
        "-i", "--input",
        help="Raw text string or path to .md/.txt file (omit to read from stdin)",
    )
    optimize_parser.add_argument(
        "-n", "--segments",
        type=int,
        default=1,
        help="Number of segments to produce (default: 1). > 1 = multiple versions.",
    )
    optimize_parser.add_argument(
        "-o", "--output",
        help="Output JSON file path (omit to print to stdout)",
    )
    optimize_parser.add_argument(
        "--fields",
        default="text",
        help="Fields to generate: text,image_prompt,video_prompt (comma-separated, or 'all'). Default: text",
    )
    optimize_parser.add_argument(
        "--direction",
        choices=["auto", "summarize", "expand", "refine"],
        default="auto",
        help="Text transformation direction when 'text' is in --fields (default: auto)",
    )
    optimize_parser.add_argument(
        "--extra-requirements",
        default="",
        help="Additional requirements appended to the AI prompt (e.g. 'use simple language for children aged 8-10')",
    )

    args = parser.parse_args()

    if args.command == "split":
        cmd_split(args)
    elif args.command == "prompts":
        cmd_prompts(args)
    elif args.command == "optimize":
        cmd_optimize(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
