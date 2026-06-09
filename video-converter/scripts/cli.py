#!/usr/bin/env python3
"""CLI entry point for video-converter — composite still images + audio into MP4
video segments, and concatenate video segments into a final video.

Usage:
    python scripts/cli.py convert -i <image-dir> -a <audio-dir> [-o <output-dir>]
    python scripts/cli.py concat -d <video-dir>

Examples:
    # Composite images and audio into video segments
    python scripts/cli.py convert -i images/ -a audio/ -o videos/

    # With captioned images
    python scripts/cli.py convert -i captioned/ -a audio/ -o videos/

    # Concatenate all video segments into one final video
    python scripts/cli.py concat -d videos/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_skill_dir = Path(__file__).resolve().parents[1]
if str(_skill_dir) not in sys.path:
    sys.path.insert(0, str(_skill_dir))

from scripts.converter import composite_videos, concat_videos  # noqa: E402


def cmd_convert(args: argparse.Namespace) -> None:
    """Handle the ``convert`` subcommand."""
    # 1. Validate input directories
    image_dir = Path(args.image_dir)
    audio_dir = Path(args.audio_dir)

    if not image_dir.is_dir():
        print(f"Error: image directory not found: {args.image_dir}", file=sys.stderr)
        sys.exit(1)
    if not audio_dir.is_dir():
        print(f"Error: audio directory not found: {args.audio_dir}", file=sys.stderr)
        sys.exit(1)

    # 2. Composite videos
    try:
        results = composite_videos(
            image_dir=image_dir,
            audio_dir=audio_dir,
            output_dir=args.output,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
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


def cmd_concat(args: argparse.Namespace) -> None:
    """Handle the ``concat`` subcommand."""
    video_dir = Path(args.dir)

    if not video_dir.is_dir():
        print(f"Error: directory not found: {args.dir}", file=sys.stderr)
        sys.exit(1)

    try:
        result = concat_videos(video_dir=video_dir)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Video Converter — composite images + audio into MP4 video segments",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ---- convert ----
    convert_parser = subparsers.add_parser("convert", help="Composite images + audio into MP4 videos")
    convert_parser.add_argument(
        "-i", "--image-dir",
        required=True,
        help="Directory containing image files (PNG, JPG, etc.)",
    )
    convert_parser.add_argument(
        "-a", "--audio-dir",
        required=True,
        help="Directory containing audio files (MP3, WAV, etc.)",
    )
    convert_parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory for MP4 videos (default: output/)",
    )

    # ---- concat ----
    concat_parser = subparsers.add_parser("concat", help="Concatenate all video files in a directory")
    concat_parser.add_argument(
        "-d", "--dir",
        required=True,
        help="Directory containing video files (sorted by name, stream-copied in order)",
    )

    args = parser.parse_args()

    if args.command == "convert":
        cmd_convert(args)
    elif args.command == "concat":
        cmd_concat(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
