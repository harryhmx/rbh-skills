#!/usr/bin/env python3
"""CLI entry point for content-production — generate images, video, and speech
from segments JSON, and extract text / convert documents to Markdown.

All media generation is batch-mode from segments JSON.  The JSON is created
directly by the Local Agent (Claude Code / Codex / etc.) from user prompts.
``extract`` / ``convert`` instead take a single source document.

Usage:
    python scripts/cli.py image   -i <segments.json> [-o <dir>] [--size WxH] [--prompt-key image_prompt]
    python scripts/cli.py video   -i <segments.json> [-o <dir>] [--size WxH] [--num-frames N] [--frame-rate FPS] [--prompt-key video_prompt]
    python scripts/cli.py speech  -i <segments.json> [-o <dir>]
    python scripts/cli.py extract -i <file> [-o <out.txt>] [--range N-M] [--format docx|pdf]
    python scripts/cli.py convert -i <file> [-o <out.md>]  [--format docx]

Examples:
    # Generate images from segments (default 1024x768)
    python scripts/cli.py image -i ucla-segments.json -o images/

    # Custom image size
    python scripts/cli.py image -i ucla-segments.json -o images/ --size 512x512

    # Generate videos from segments
    python scripts/cli.py video -i ucla-segments.json -o videos/

    # Custom video settings
    python scripts/cli.py video -i ucla-segments.json -o videos/ --size 1024x768 --num-frames 121 --frame-rate 24

    # Generate speech from segments (uses text field)
    python scripts/cli.py speech -i ucla-segments.json -o audio/

    # Extract plain text (full document)
    python scripts/cli.py extract -i report.docx -o report.txt
    python scripts/cli.py extract -i paper.pdf -o paper.txt

    # Extract a page/paragraph range (1-indexed, inclusive)
    python scripts/cli.py extract -i paper.pdf --range 2-5 -o paper-excerpt.txt

    # Convert to structured Markdown
    python scripts/cli.py convert -i report.docx -o report.md
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

logger = logging.getLogger(__name__)

_skill_dir = Path(__file__).resolve().parents[1]
if str(_skill_dir) not in sys.path:
    sys.path.insert(0, str(_skill_dir))

from scripts.common import load_segments_json       # noqa: E402
from scripts.images import generate_images          # noqa: E402
from scripts.videos import generate_videos          # noqa: E402
from scripts.speech import generate_speech          # noqa: E402
from scripts.extract import extract_text            # noqa: E402
from scripts.convert import convert_to_md           # noqa: E402


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
    """Handle the ``speech`` subcommand.

    Uses the segment's ``text`` field as speech content.
    """
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


def cmd_video(args: argparse.Namespace) -> None:
    """Handle the ``video`` subcommand."""
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

    # 3. Generate videos
    try:
        results = generate_videos(
            segments,
            size=size,
            output_dir=args.output,
            prompt_key=args.prompt_key,
            num_frames=args.num_frames,
            frame_rate=args.frame_rate,
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


def _write_text_output(text: str, output: str | None) -> None:
    """Write *text* to the *output* file (creating parent dirs) or stdout."""
    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"Saved: {out_path.resolve()}")
    else:
        print(text)


def cmd_extract(args: argparse.Namespace) -> None:
    """Handle the ``extract`` subcommand — dump plain text from a document."""
    try:
        text = extract_text(
            input_path=args.input,
            fmt=args.format,
            range_spec=args.range,
        )
    except (FileNotFoundError, ValueError, NotImplementedError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    _write_text_output(text, args.output)


def cmd_convert(args: argparse.Namespace) -> None:
    """Handle the ``convert`` subcommand — convert a document to Markdown."""
    try:
        text = convert_to_md(
            input_path=args.input,
            fmt=args.format,
        )
    except (FileNotFoundError, ValueError, NotImplementedError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    _write_text_output(text, args.output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Content Production — generate images, video, and speech from segments JSON",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ---- image ----
    image_parser = subparsers.add_parser("image", help="Generate images from segments")
    image_parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to segments JSON file (from Local Agent)",
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

    # ---- video ----
    video_parser = subparsers.add_parser("video", help="Generate videos from segments")
    video_parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to segments JSON file (from Local Agent)",
    )
    video_parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory for generated videos (default: output/)",
    )
    video_parser.add_argument(
        "--size",
        default="1024x768",
        help="Video size in WxH format (default: 1152x768)",
    )
    video_parser.add_argument(
        "--num-frames",
        type=int,
        default=121,
        help="Number of frames — must be <= 441 and satisfy 8n+1 (default: 121)",
    )
    video_parser.add_argument(
        "--frame-rate",
        type=float,
        default=24,
        help="Frame rate in FPS, 1–60 (default: 24)",
    )
    video_parser.add_argument(
        "--prompt-key",
        default="video_prompt",
        help="Segment key containing the video prompt (default: video_prompt)",
    )

    # ---- speech ----
    speech_parser = subparsers.add_parser("speech", help="Generate speech audio from segments")
    speech_parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to segments JSON file (from Local Agent)",
    )
    speech_parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory for generated audio (default: output/)",
    )

    # ---- extract ----
    extract_parser = subparsers.add_parser(
        "extract", help="Extract plain text from DOCX/PDF (no formatting)"
    )
    extract_parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to source document (docx, pdf)",
    )
    extract_parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output .txt file (prints to stdout if omitted)",
    )
    extract_parser.add_argument(
        "--range",
        default=None,
        help="1-indexed inclusive range: N, N-M, N-, -M "
             "(paragraphs for docx, pages for pdf)",
    )
    extract_parser.add_argument(
        "--format",
        default=None,
        help="Force input format (docx, pdf); inferred from extension if omitted",
    )

    # ---- convert ----
    convert_parser = subparsers.add_parser(
        "convert", help="Convert DOCX to structured Markdown"
    )
    convert_parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to source document (docx)",
    )
    convert_parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output .md file (prints to stdout if omitted)",
    )
    convert_parser.add_argument(
        "--format",
        default=None,
        help="Force input format (docx); inferred from extension if omitted",
    )

    args = parser.parse_args()

    if args.command == "image":
        cmd_image(args)
    elif args.command == "video":
        cmd_video(args)
    elif args.command == "speech":
        cmd_speech(args)
    elif args.command == "extract":
        cmd_extract(args)
    elif args.command == "convert":
        cmd_convert(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
