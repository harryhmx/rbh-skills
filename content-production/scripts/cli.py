#!/usr/bin/env python3
"""CLI entry point for content-production — generate images and speech from
text-optimizer segments JSON, and caption images with segment titles.

Usage:
    python scripts/cli.py image -i <segments.json> [-o <dir>] [--size WxH] [--prompt-key image_prompt]
    python scripts/cli.py speech -i <segments.json> [-o <dir>] [--prompt-key tts_prompt]
    python scripts/cli.py caption -i <segments.json> -d <image-dir> [-o <dir>] [--font FONT] [--font-size N]

Examples:
    # Generate images from segments (default 1024x768)
    python scripts/cli.py image -i ucla-segments.json -o images/

    # Custom image size
    python scripts/cli.py image -i ucla-segments.json -o images/ --size 512x512

    # Generate speech from segments
    python scripts/cli.py speech -i ucla-segments.json -o audio/

    # Overlay titles onto generated images
    python scripts/cli.py caption -i ucla-segments.json -d images/ -o captioned/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_skill_dir = Path(__file__).resolve().parents[1]
if str(_skill_dir) not in sys.path:
    sys.path.insert(0, str(_skill_dir))

from scripts.production import (  # noqa: E402
    caption_images,
    generate_images,
    generate_speech,
    load_segments_json,
)


def cmd_image(args: argparse.Namespace) -> None:
    """Handle the ``image`` subcommand."""
    # 1. Load segments
    try:
        segments = load_segments_json(args.input)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # 2. Validate size format
    size = args.size
    if "x" not in size:
        print("Error: --size must be in WxH format (e.g. 1024x768)", file=sys.stderr)
        sys.exit(1)

    # 3. Generate images
    try:
        results = generate_images(
            segments,
            size=size,
            output_dir=args.output,
            prompt_key=args.prompt_key,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # 4. Print summary
    succeeded = sum(1 for r in results if r["file_path"])
    print(json.dumps({
        "total": len(results),
        "succeeded": succeeded,
        "failed": len(results) - succeeded,
        "results": results,
    }, ensure_ascii=False, indent=2))


def cmd_speech(args: argparse.Namespace) -> None:
    """Handle the ``speech`` subcommand."""
    # 1. Load segments
    try:
        segments = load_segments_json(args.input)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # 2. Generate speech
    try:
        results = generate_speech(
            segments,
            output_dir=args.output,
            prompt_key=args.prompt_key,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # 3. Print summary
    succeeded = sum(1 for r in results if r["file_path"])
    print(json.dumps({
        "total": len(results),
        "succeeded": succeeded,
        "failed": len(results) - succeeded,
        "results": results,
    }, ensure_ascii=False, indent=2))


def cmd_caption(args: argparse.Namespace) -> None:
    """Handle the ``caption`` subcommand — overlay titles onto images."""
    # 1. Load segments
    try:
        segments = load_segments_json(args.input)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # 2. Caption images
    try:
        results = caption_images(
            segments,
            image_dir=args.dir,
            output_dir=args.output,
            font_path=args.font,
            font_size=args.font_size,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # 3. Print summary
    succeeded = sum(1 for r in results if r.get("output"))
    print(json.dumps({
        "total": len(results),
        "succeeded": succeeded,
        "failed": len(results) - succeeded,
        "results": results,
    }, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Content Production — generate images and speech from segments JSON",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ---- image ----
    image_parser = subparsers.add_parser("image", help="Generate images from segments")
    image_parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to segments JSON file (from text-optimizer)",
    )
    image_parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory for generated images (default: output/)",
    )
    image_parser.add_argument(
        "--size",
        default="1024x768",
        help="Image size in WxH format (default: 1024x768)",
    )
    image_parser.add_argument(
        "--prompt-key",
        default="image_prompt",
        help="Segment key containing the image prompt (default: image_prompt)",
    )

    # ---- speech ----
    speech_parser = subparsers.add_parser("speech", help="Generate speech audio from segments")
    speech_parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to segments JSON file (from text-optimizer)",
    )
    speech_parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory for generated audio (default: output/)",
    )
    speech_parser.add_argument(
        "--prompt-key",
        default="tts_prompt",
        help="Segment key containing the TTS prompt (default: tts_prompt)",
    )

    # ---- caption ----
    caption_parser = subparsers.add_parser("caption", help="Overlay title text onto generated images")
    caption_parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to segments JSON file (from text-optimizer)",
    )
    caption_parser.add_argument(
        "-d", "--dir",
        required=True,
        help="Directory containing PNG images named {index:03d}.png",
    )
    caption_parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory for captioned images (omit to overwrite originals)",
    )
    caption_parser.add_argument(
        "--font",
        default=None,
        help="Path to .ttf/.ttc font file (auto-detected if omitted)",
    )
    caption_parser.add_argument(
        "--font-size",
        type=int,
        default=36,
        help="Font size in points (default: 36)",
    )

    args = parser.parse_args()

    if args.command == "image":
        cmd_image(args)
    elif args.command == "speech":
        cmd_speech(args)
    elif args.command == "caption":
        cmd_caption(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
