#!/usr/bin/env python3
"""CLI entry point for content-production — generate images, video, and speech
from segments JSON (batch) or directly via --prompt (single), and extract text /
convert documents to Markdown.

The ``-i`` / ``--input`` flag runs batch generation from a validated
media-segments JSON; the ``--prompt`` flag runs single generation directly.
``extract`` / ``convert`` take a source document, not media segments.

Usage:
    python scripts/cli.py image   -i <media-segments.json> [-o <dir>] [--size WxH]
    python scripts/cli.py image   --prompt "prompt text" [-o <file>] [--size WxH]
    python scripts/cli.py video   -i <media-segments.json> [-o <dir>] [--size WxH] [--num-frames N] [--frame-rate FPS]
    python scripts/cli.py video   --prompt "prompt text" [-o <file>] [--size WxH] [--num-frames N] [--frame-rate FPS]
    python scripts/cli.py speech  -i <media-segments.json> [-o <dir>]
    python scripts/cli.py speech  --prompt "speech text" [-o <file>]
    python scripts/cli.py extract -i <file> [-o <out.txt>] [--range N-M] [--format docx|pdf]
    python scripts/cli.py convert -i <file> [-o <out.md>]  [--format docx]

Examples:
    # Generate images from segments (default 1024x768)
    python scripts/cli.py image -i media-segments.json -o images/

    # Custom image size
    python scripts/cli.py image -i media-segments.json -o images/ --size 512x512

    # Single image from prompt
    python scripts/cli.py image --prompt "A sunset over mountains" -o sunset.png

    # Generate videos from segments
    python scripts/cli.py video -i media-segments.json -o videos/

    # Custom video settings
    python scripts/cli.py video -i media-segments.json -o videos/ --size 1024x768 --num-frames 121 --frame-rate 24

    # Single video from prompt
    python scripts/cli.py video --prompt "A car driving through the desert" -o car.mp4

    # Generate speech from segments (uses text field)
    python scripts/cli.py speech -i media-segments.json -o audio/

    # Single speech from text
    python scripts/cli.py speech --prompt "Hello, welcome to the lesson." -o greeting.mp3

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
import os
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

from scripts.common import (
    IMAGE_SIZE_DEFAULT,
    VIDEO_SIZE_DEFAULT,
    VIDEO_NUM_FRAMES_DEFAULT,
    VIDEO_FRAME_RATE_DEFAULT,
    load_segments_json,
)  # noqa: E402

from scripts.images import generate_images          # noqa: E402
from scripts.images import generate_one_image       # noqa: E402

from scripts.videos import generate_videos          # noqa: E402
from scripts.videos import generate_one_video       # noqa: E402

from scripts.speech import generate_speech          # noqa: E402
from scripts.speech import generate_one_speech      # noqa: E402

from scripts.extract import extract_text            # noqa: E402
from scripts.convert import convert_to_md           # noqa: E402


def _size(value: str) -> str:
    try:
        width_text, height_text = value.lower().split("x", 1)
        width, height = int(width_text), int(height_text)
    except (ValueError, AttributeError) as exc:
        raise argparse.ArgumentTypeError("must be positive WxH dimensions") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("must be positive WxH dimensions")
    return value


def _num_frames(value: str) -> int:
    frames = int(value)
    if frames <= 0 or frames > 441 or (frames - 1) % 8 != 0:
        raise argparse.ArgumentTypeError("must be <= 441 and satisfy 8n+1")
    return frames


def _frame_rate(value: str) -> float:
    rate = float(value)
    if not 1 <= rate <= 60:
        raise argparse.ArgumentTypeError("must be between 1 and 60")
    return rate
def _single_output_path(output_arg: str | None, default_name: str) -> Path:
    """Resolve output path for single-generation commands.

    - If *output_arg* is None -> returns *default_name* in the current directory.
    - If *output_arg* ends with / or is an existing directory -> saves
      *default_name* inside it.
    - Otherwise -> treated as an exact file path.
    """
    if output_arg is None:
        return Path(default_name)
    p = Path(output_arg)
    if output_arg.endswith(('/', os.sep)) or p.is_dir():
        p.mkdir(parents=True, exist_ok=True)
        return p / default_name
    return p


def cmd_image(args: argparse.Namespace) -> None:
    """Handle the ``image`` subcommand."""
    if args.prompt:
        # ---- Single generation from --prompt ----
        size = args.size
        if "x" not in size:
            print("Error: --size must be in WxH format (e.g. 1024x768)", file=sys.stderr)
            sys.exit(2)

        output_path = _single_output_path(args.output, "output.png")

        try:
            result = generate_one_image(args.prompt, size, output_path)
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.input:
        # ---- Batch generation from JSON ----
        try:
            segments, name = load_segments_json(args.input, "image")
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(2)

        size = args.size
        if "x" not in size:
            print("Error: --size must be in WxH format (e.g. 1024x768)", file=sys.stderr)
            sys.exit(2)

        try:
            results = generate_images(
                segments,
                name=name,
                size=size,
                output_dir=args.output,
            )
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

        succeeded = sum(1 for r in results if r["file_path"])
        print(json.dumps({
            "total": len(results), "succeeded": succeeded,
            "failed": len(results) - succeeded, "results": results,
        }, ensure_ascii=False, indent=2))


def cmd_speech(args: argparse.Namespace) -> None:
    """Handle the ``speech`` subcommand.

    Uses the segment's ``text`` field as speech content.
    """
    if args.prompt:
        # ---- Single generation from --prompt ----
        output_path = _single_output_path(args.output, "output.mp3")

        try:
            result = generate_one_speech(args.prompt, output_path)
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.input:
        # ---- Batch generation from JSON ----
        try:
            segments, name = load_segments_json(args.input, "speech")
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(2)

        try:
            results = generate_speech(
                segments,
                name=name,
                output_dir=args.output,
            )
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

        succeeded = sum(1 for r in results if r["file_path"])
        print(json.dumps({
            "total": len(results), "succeeded": succeeded,
            "failed": len(results) - succeeded, "results": results,
        }, ensure_ascii=False, indent=2))


def cmd_video(args: argparse.Namespace) -> None:
    """Handle the ``video`` subcommand."""
    if args.prompt:
        # ---- Single generation from --prompt ----
        size = args.size
        if "x" not in size:
            print("Error: --size must be in WxH format (e.g. 1024x768)", file=sys.stderr)
            sys.exit(2)

        output_path = _single_output_path(args.output, "output.mp4")

        try:
            result = generate_one_video(
                args.prompt, size, output_path,
                num_frames=args.num_frames, frame_rate=args.frame_rate,
            )
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.input:
        # ---- Batch generation from JSON ----
        try:
            segments, name = load_segments_json(args.input, "video")
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(2)

        size = args.size
        if "x" not in size:
            print("Error: --size must be in WxH format (e.g. 1024x768)", file=sys.stderr)
            sys.exit(2)

        try:
            results = generate_videos(
                segments, name=name, size=size, output_dir=args.output,
                num_frames=args.num_frames, frame_rate=args.frame_rate,
            )
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

        succeeded = sum(1 for r in results if r["file_path"])
        print(json.dumps({
            "total": len(results), "succeeded": succeeded,
            "failed": len(results) - succeeded, "results": results,
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
        required=False,
        default=None,
        help="Path to segments JSON file (required for batch mode)",
    )
    image_parser.add_argument(
        "--prompt",
        required=False,
        default=None,
        help="Prompt text for single-image generation (use instead of -i)",
    )
    image_parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory or file path (default: output/)",
    )
    image_parser.add_argument(
        "--size",
        type=_size,
        default=IMAGE_SIZE_DEFAULT,
        help=f"Image size in WxH format (default: {IMAGE_SIZE_DEFAULT})",
    )

    # ---- video ----
    video_parser = subparsers.add_parser("video", help="Generate videos from segments")
    video_parser.add_argument(
        "-i", "--input",
        required=False,
        default=None,
        help="Path to segments JSON file (required for batch mode)",
    )
    video_parser.add_argument(
        "--prompt",
        required=False,
        default=None,
        help="Prompt text for single-video generation (use instead of -i)",
    )
    video_parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory or file path (default: output/)",
    )
    video_parser.add_argument(
        "--size",
        type=_size,
        default=VIDEO_SIZE_DEFAULT,
        help=f"Video size in WxH format (default: {VIDEO_SIZE_DEFAULT})",
    )
    video_parser.add_argument(
        "--num-frames",
        type=_num_frames,
        default=VIDEO_NUM_FRAMES_DEFAULT,
        help=f"Number of frames — must be <= 441 and satisfy 8n+1 (default: {VIDEO_NUM_FRAMES_DEFAULT})",
    )
    video_parser.add_argument(
        "--frame-rate",
        type=_frame_rate,
        default=VIDEO_FRAME_RATE_DEFAULT,
        help=f"Frame rate in FPS, 1–60 (default: {VIDEO_FRAME_RATE_DEFAULT:g})",
    )

    # ---- speech ----
    speech_parser = subparsers.add_parser("speech", help="Generate speech audio from segments")
    speech_parser.add_argument(
        "-i", "--input",
        required=False,
        default=None,
        help="Path to segments JSON file (required for batch mode)",
    )
    speech_parser.add_argument(
        "--prompt",
        required=False,
        default=None,
        help="Text to speak for single-speech generation (use instead of -i)",
    )
    speech_parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory or file path (default: output/)",
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
