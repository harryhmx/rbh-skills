#!/usr/bin/env python3
"""CLI entry point for media-composer — media editing and transcription toolkit.

Usage:
    python scripts/cli.py transcribe -i <audio> [-o <output>] [--backend mlx-whisper] [--model turbo] [--lang zh]
    python scripts/cli.py caption   -i <segments.json> -d <image-dir> [-o <dir>] [--font FONT] [--font-size N]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)

_skill_dir = Path(__file__).resolve().parents[1]
if str(_skill_dir) not in sys.path:
    sys.path.insert(0, str(_skill_dir))

from scripts.transcribe import transcribe  # noqa: E402
from scripts.caption import caption_images  # noqa: E402


def cmd_transcribe(args: argparse.Namespace) -> None:
    """Handle the ``transcribe`` subcommand."""
    try:
        text = transcribe(
            audio_path=args.input,
            backend=args.backend,
            model=args.model,
            language=args.lang,
            output_format=args.format,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"Saved: {out_path.resolve()}")
    else:
        print(text)


def cmd_caption(args: argparse.Namespace) -> None:
    """Handle the ``caption`` subcommand — overlay titles onto images.

    The index→title mapping comes from a JSON file: either a segments wrapper
    (``{"segments": [{index, title, ...}]}``) or a bare list of
    ``{index, title, ...}`` objects.  Images are matched by ``{index:03d}.png``.
    """
    try:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if isinstance(data, dict):
        segments = data.get("segments", [])
    elif isinstance(data, list):
        segments = data
    else:
        print("Error: input JSON must be an object with 'segments' or a list", file=sys.stderr)
        sys.exit(1)

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

    succeeded = sum(1 for r in results if r.get("output"))
    print(json.dumps({
        "total": len(results),
        "succeeded": succeeded,
        "failed": len(results) - succeeded,
        "results": results,
    }, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Media Composer — media editing and transcription toolkit",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ---- transcribe ----
    transcribe_parser = subparsers.add_parser(
        "transcribe", help="Transcribe audio/video to text (STT)"
    )
    transcribe_parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to audio/video file",
    )
    transcribe_parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output file path (prints to stdout if omitted)",
    )
    transcribe_parser.add_argument(
        "--backend",
        default="mlx-whisper",
        choices=["mlx-whisper", "whisper-cpp"],
        help="Transcription backend (default: mlx-whisper)",
    )
    transcribe_parser.add_argument(
        "--model",
        default="turbo",
        help="Whisper model size (default: turbo)",
    )
    transcribe_parser.add_argument(
        "--lang",
        default=None,
        help="Language code e.g. zh/en (auto-detect if omitted)",
    )
    transcribe_parser.add_argument(
        "--format",
        default="md",
        choices=["md", "txt", "json"],
        help="Output format (default: md)",
    )

    # ---- caption ----
    caption_parser = subparsers.add_parser(
        "caption", help="Overlay title text onto PNG images"
    )
    caption_parser.add_argument(
        "-i", "--input",
        required=True,
        help="JSON with index→title mapping: {\"segments\":[...]} or a bare list",
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

    if args.command == "transcribe":
        cmd_transcribe(args)
    elif args.command == "caption":
        cmd_caption(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
