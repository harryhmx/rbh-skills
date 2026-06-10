#!/usr/bin/env python3
"""CLI entry point for content-production — generate images, video, and speech from
text-optimizer segments JSON, single prompt files, and caption images with segment titles.

Usage:
    python scripts/cli.py image -i <segments.json> [-o <dir>] [--size WxH] [--prompt-key image_prompt]
    python scripts/cli.py video -i <segments.json> [-o <dir>] [--size WxH] [--num-frames N] [--frame-rate FPS] [--prompt-key video_prompt]
    python scripts/cli.py speech -i <segments.json> [-o <dir>] [--prompt-key tts_prompt]
    python scripts/cli.py caption -i <segments.json> -d <image-dir> [-o <dir>] [--font FONT] [--font-size N]
    python scripts/cli.py single -i <prompt-file.md|.txt>

Examples:
    # Generate images from segments (default 1024x768)
    python scripts/cli.py image -i ucla-segments.json -o images/

    # Custom image size
    python scripts/cli.py image -i ucla-segments.json -o images/ --size 512x512

    # Generate videos from segments
    python scripts/cli.py video -i ucla-segments.json -o videos/

    # Custom video settings
    python scripts/cli.py video -i ucla-segments.json -o videos/ --size 1024x768 --num-frames 121 --frame-rate 24

    # Generate speech from segments
    python scripts/cli.py speech -i ucla-segments.json -o audio/

    # Overlay titles onto generated images
    python scripts/cli.py caption -i ucla-segments.json -d images/ -o captioned/

    # Generate a single image from a prompt file (from text-optimizer genprompt)
    python scripts/cli.py single -i my-image-prompt.md

    # Generate a single video from a prompt file
    python scripts/cli.py single -i my-video-prompt.md
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

from scripts.production import (  # noqa: E402
    caption_images,
    generate_images,
    generate_single_image,
    generate_single_video,
    generate_speech,
    generate_videos,
    load_segments_json,
    parse_prompt_file,
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


def cmd_single(args: argparse.Namespace) -> None:
    """Handle the ``single`` subcommand — generate one image/video from a prompt file."""
    input_path = Path(args.input)
    if not input_path.exists() or not input_path.is_file():
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # 1. Parse the prompt file
    try:
        meta = parse_prompt_file(input_path)
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    prompt_type = meta["type"]
    prompt = meta["prompt"]
    size = meta.get("size", "1024x768")

    # 2. Determine output path: same dir, same basename, different extension
    if prompt_type == "image":
        output_path = input_path.with_suffix(".png")
    else:
        output_path = input_path.with_suffix(".mp4")

    logger.info("Generating single %s: %s → %s", prompt_type, input_path.name, output_path.name)

    # 3. Generate
    try:
        if prompt_type == "image":
            result = generate_single_image(prompt, size=size, output_path=output_path)
        else:
            num_frames = meta.get("num_frames", 121)
            frame_rate = meta.get("frame_rate", 24)
            result = generate_single_video(
                prompt, size=size, num_frames=num_frames,
                frame_rate=frame_rate, output_path=output_path,
            )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # 4. Print result
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result.get("file_path"):
        logger.info("Done: %s", result["file_path"])
    else:
        logger.error("Failed to generate %s", prompt_type)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Content Production — generate images, video, and speech from segments JSON and prompt files",
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

    # ---- video ----
    video_parser = subparsers.add_parser("video", help="Generate videos from segments")
    video_parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to segments JSON file (from text-optimizer)",
    )
    video_parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory for generated videos (default: output/)",
    )
    video_parser.add_argument(
        "--size",
        default="1024x768",
        help="Video size in WxH format (default: 1024x768)",
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

    # ---- single ----
    single_parser = subparsers.add_parser(
        "single",
        help="Generate a single image or video from a prompt file (proprietary format from text-optimizer genprompt)",
    )
    single_parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to prompt file (.md or .txt, from text-optimizer genprompt)",
    )

    args = parser.parse_args()

    if args.command == "image":
        cmd_image(args)
    elif args.command == "video":
        cmd_video(args)
    elif args.command == "speech":
        cmd_speech(args)
    elif args.command == "caption":
        cmd_caption(args)
    elif args.command == "single":
        cmd_single(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
