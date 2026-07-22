#!/usr/bin/env python3
"""CLI entry point for media-composer — media editing and transcription toolkit.

Subcommands: transcribe, caption, trim, extract-audio, replace-segment,
enhance, subtitle-burn, replace-bg.  Run ``<subcommand> --help`` for flags.
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

from scripts.common import parse_time  # noqa: E402


def _fail(exc: Exception) -> None:
    print(f"Error: {exc}", file=sys.stderr)
    sys.exit(1)


def _emit(result) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def cmd_transcribe(args: argparse.Namespace) -> None:
    from scripts.transcribe import transcribe

    try:
        text = transcribe(
            audio_path=args.input,
            backend=args.backend,
            model=args.model,
            language=args.lang,
            output_format=args.format,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        _fail(exc)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"Saved: {out_path.resolve()}")
    else:
        print(text)


def cmd_caption(args: argparse.Namespace) -> None:
    from scripts.caption import caption_image, caption_images, caption_video

    modes = [bool(args.input), bool(args.image), bool(args.video)]
    if sum(modes) != 1:
        _fail(ValueError("Choose exactly one mode: -i JSON+-d DIR (batch), --image, or --video"))

    try:
        if args.video:  # video title overlay
            if not args.text:
                raise ValueError("--video mode requires --text")
            if not args.output:
                raise ValueError("--video mode requires -o output path")
            _emit(caption_video(
                args.video, args.text, args.output,
                font_path=args.font, font_size=args.font_size,
                position=args.position or "top",
            ))
        elif args.image:  # single image
            if not args.text:
                raise ValueError("--image mode requires --text")
            _emit(caption_image(
                args.image, args.text, args.output,
                font_path=args.font, font_size=args.font_size,
                position=args.position or "center",
            ))
        else:  # batch via segments JSON
            if not args.dir:
                raise ValueError("batch mode requires -d/--dir")
            data = json.loads(Path(args.input).read_text(encoding="utf-8"))
            segments = data.get("segments", []) if isinstance(data, dict) else data
            if not isinstance(segments, list):
                raise ValueError("input JSON must be {'segments': [...]} or a list")
            results = caption_images(
                segments, image_dir=args.dir, output_dir=args.output,
                font_path=args.font, font_size=args.font_size,
                position=args.position or "center",
            )
            succeeded = sum(1 for r in results if r.get("output"))
            _emit({
                "total": len(results),
                "succeeded": succeeded,
                "failed": len(results) - succeeded,
                "results": results,
            })
    except Exception as exc:
        _fail(exc)


def cmd_trim(args: argparse.Namespace) -> None:
    from scripts.trim import trim

    try:
        _emit(trim(
            args.input, args.output,
            start=parse_time(args.start) if args.start is not None else None,
            end=parse_time(args.end) if args.end is not None else None,
            head=args.head, tail=args.tail, crf=args.crf,
        ))
    except Exception as exc:
        _fail(exc)


def cmd_extract_audio(args: argparse.Namespace) -> None:
    from scripts.extract_audio import extract_audio

    try:
        _emit(extract_audio(args.input, args.output, format=args.format, bitrate=args.bitrate))
    except Exception as exc:
        _fail(exc)


def cmd_replace_segment(args: argparse.Namespace) -> None:
    from scripts.replace_segment import replace_segment

    try:
        _emit(replace_segment(
            args.input, args.image,
            start=parse_time(args.start), end=parse_time(args.end),
            output_path=args.output,
            pad_color=args.pad_color, fit=args.fit,
            drop_audio=args.drop_audio, crf=args.crf,
        ))
    except Exception as exc:
        _fail(exc)


def cmd_enhance(args: argparse.Namespace) -> None:
    from scripts.enhance import enhance

    try:
        _emit(enhance(
            args.input, args.output,
            lufs=args.lufs, crf=args.crf, preset=args.preset,
            video_filter=args.video_filter, audio_filter=args.audio_filter,
        ))
    except Exception as exc:
        _fail(exc)


def cmd_subtitle_burn(args: argparse.Namespace) -> None:
    from scripts.subtitle_burn import subtitle_burn

    try:
        _emit(subtitle_burn(
            args.input, args.srt, args.output,
            font=args.font, font_size=args.font_size, color=args.color,
            position=args.position, margin_v=args.margin_v,
            margin_lr=args.margin_lr, crf=args.crf,
        ))
    except Exception as exc:
        _fail(exc)


def cmd_replace_bg(args: argparse.Namespace) -> None:
    from scripts.replace_bg import replace_bg

    try:
        _emit(replace_bg(
            args.input, args.bg, args.output,
            variant=args.variant, checkpoint=args.checkpoint,
            chunk=args.chunk, downsample_ratio=args.downsample_ratio,
            crf=args.crf,
        ))
    except Exception as exc:
        _fail(exc)


def cmd_composite(args: argparse.Namespace) -> None:
    from scripts.composite import composite_videos

    try:
        results = composite_videos(args.image_dir, args.audio_dir, args.output)
        succeeded = sum(1 for r in results if r.get("output"))
        _emit({
            "total": len(results),
            "succeeded": succeeded,
            "failed": len(results) - succeeded,
            "results": results,
        })
    except Exception as exc:
        _fail(exc)


def cmd_concat(args: argparse.Namespace) -> None:
    from scripts.concat import concat_videos

    try:
        _emit(concat_videos(args.dir, output_path=args.output))
    except Exception as exc:
        _fail(exc)



def cmd_stitch(args: argparse.Namespace) -> None:
    from scripts.stitch import stitch_images

    if len(args.inputs) < 2:
        _fail(ValueError("At least two input images are required"))
    try:
        _emit(stitch_images(
            args.inputs,
            output_path=args.output,
            direction=args.direction,
            spacing=args.spacing,
            align=args.align,
            background=args.background,
        ))
    except Exception as exc:
        _fail(exc)


def cmd_overlay(args: argparse.Namespace) -> None:
    from scripts.overlay import load_overlay_spec, overlay_images

    if args.spec:
        if args.image or args.start is not None or args.end is not None:
            print("Error: --spec cannot be combined with --image/--start/--end", file=sys.stderr)
            sys.exit(2)
        overlays = load_overlay_spec(args.spec)
    else:
        if not (args.image and args.start is not None and args.end is not None):
            print("Error: provide --image/--start/--end, or --spec JSON file", file=sys.stderr)
            sys.exit(2)
        overlays = [{
            "image": args.image, "start": args.start, "end": args.end,
            "width": args.width, "x": args.x, "y": args.y,
        }]

    try:
        _emit(overlay_images(args.input, args.output, overlays, crf=args.crf))
    except Exception as exc:
        _fail(exc)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Media Composer — media editing and transcription toolkit",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ---- transcribe ----
    p = subparsers.add_parser("transcribe", help="Transcribe audio/video to text (STT)")
    p.add_argument("-i", "--input", required=True, help="Path to audio/video file")
    p.add_argument("-o", "--output", default=None, help="Output file path (stdout if omitted)")
    p.add_argument("--backend", default="mlx-whisper", choices=["mlx-whisper", "whisper-cpp"],
                   help="Transcription backend (default: mlx-whisper)")
    p.add_argument("--model", default="turbo", help="Whisper model size (default: turbo)")
    p.add_argument("--lang", default=None, help="Language code e.g. zh/en (auto-detect if omitted)")
    p.add_argument("--format", default="md", choices=["md", "txt", "json", "srt"],
                   help="Output format (default: md)")
    p.set_defaults(func=cmd_transcribe)

    # ---- caption ----
    p = subparsers.add_parser(
        "caption",
        help="Overlay text: batch images (-i JSON -d DIR), one image (--image), or video title (--video)",
    )
    p.add_argument("-i", "--input", default=None,
                   help="Batch mode: JSON with index→title mapping ({'segments':[...]} or list)")
    p.add_argument("-d", "--dir", default=None,
                   help="Batch mode: directory of {index:03d}.png images")
    p.add_argument("--image", default=None, help="Single-image mode: path to the image")
    p.add_argument("--video", default=None, help="Video mode: path to the video")
    p.add_argument("--text", default=None, help="Text to overlay (single-image / video modes)")
    p.add_argument("-o", "--output", default=None,
                   help="Output path (batch: directory; single/video: file). Batch/image default: in place")
    p.add_argument("--font", default=None, help="Path to .ttf/.ttc font (auto-detected CJK if omitted)")
    p.add_argument("--font-size", type=int, default=None,
                   help="Max font size in px; auto-shrinks to fit one line (default: preset 40)")
    p.add_argument("--position", default=None, choices=["top", "center", "bottom"],
                   help="Banner position (default: video=top, images=center)")
    p.set_defaults(func=cmd_caption)

    # ---- trim ----
    p = subparsers.add_parser("trim", help="Cut video head/tail (always re-encodes)")
    p.add_argument("-i", "--input", required=True, help="Input video")
    p.add_argument("-o", "--output", required=True, help="Output video")
    p.add_argument("--start", default=None, help="Keep from this time (sec or HH:MM:SS)")
    p.add_argument("--end", default=None, help="Keep until this time (sec or HH:MM:SS)")
    p.add_argument("--head", type=float, default=None, help="Drop this many seconds from the start")
    p.add_argument("--tail", type=float, default=None, help="Drop this many seconds from the end")
    p.add_argument("--crf", type=int, default=18, help="x264 CRF (default: 18)")
    p.set_defaults(func=cmd_trim)

    # ---- extract-audio ----
    p = subparsers.add_parser("extract-audio", help="Extract the audio track from a video")
    p.add_argument("-i", "--input", required=True, help="Input video")
    p.add_argument("-o", "--output", required=True, help="Output audio file")
    p.add_argument("--format", default="aac", choices=["aac", "wav", "mp3"],
                   help="Audio format (default: aac; wav is lossless, for transcribe)")
    p.add_argument("--bitrate", default="192k", help="Bitrate for aac/mp3 (default: 192k)")
    p.set_defaults(func=cmd_extract_audio)

    # ---- replace-segment ----
    p = subparsers.add_parser("replace-segment", help="Replace a time range with a still image")
    p.add_argument("-i", "--input", required=True, help="Input video")
    p.add_argument("-o", "--output", required=True, help="Output video")
    p.add_argument("--start", required=True, help="Range start (sec or HH:MM:SS)")
    p.add_argument("--end", required=True, help="Range end (sec or HH:MM:SS)")
    p.add_argument("--image", required=True, help="Replacement image")
    p.add_argument("--pad-color", default="black",
                   help="Letterbox bar color for --fit contain (e.g. 0x3B2417; default: black)")
    p.add_argument("--fit", default="contain", choices=["contain", "cover"],
                   help="contain: whole image + bars; cover: fill + crop (default: contain)")
    p.add_argument("--drop-audio", action="store_true", help="Drop audio instead of keeping it")
    p.add_argument("--crf", type=int, default=18, help="x264 CRF (default: 18)")
    p.set_defaults(func=cmd_replace_segment)

    # ---- enhance ----
    p = subparsers.add_parser("enhance", help="Denoise+sharpen video, two-pass loudnorm audio")
    p.add_argument("-i", "--input", required=True, help="Input video")
    p.add_argument("-o", "--output", required=True, help="Output video")
    p.add_argument("--lufs", type=float, default=-16.0, help="Target loudness (default: -16 LUFS)")
    p.add_argument("--crf", type=int, default=16, help="x264 CRF (default: 16)")
    p.add_argument("--preset", default="slow", help="x264 preset (default: slow)")
    p.add_argument("--video-filter", default=None, help="Override the default video filter chain")
    p.add_argument("--audio-filter", default=None,
                   help="Override the audio chain entirely (skips the loudnorm two-pass)")
    p.set_defaults(func=cmd_enhance)

    # ---- subtitle-burn ----
    p = subparsers.add_parser("subtitle-burn", help="Burn an SRT into the picture (needs libass ffmpeg)")
    p.add_argument("-i", "--input", required=True, help="Input video")
    p.add_argument("-o", "--output", required=True, help="Output video")
    p.add_argument("--srt", required=True, help="SRT subtitle file")
    p.add_argument("--font", default=None, help='libass font name (default: preset "PingFang SC")')
    p.add_argument("--font-size", type=int, default=None,
                   help="libass Fontsize — PlayRes units, NOT pixels; calibrate by eye (default: preset 12)")
    p.add_argument("--color", default=None, help="teal/white/yellow/black or #RRGGBB (default: preset teal)")
    p.add_argument("--position", default=None, choices=["bottom", "top"],
                   help="Subtitle position (default: preset bottom)")
    p.add_argument("--margin-v", type=int, default=None, help="Vertical margin (default: preset 20)")
    p.add_argument("--margin-lr", type=int, default=None,
                   help="Left/right margins to stop edge overflow (default: preset 28)")
    p.add_argument("--crf", type=int, default=16, help="x264 CRF (default: 16)")
    p.set_defaults(func=cmd_subtitle_burn)

    # ---- replace-bg ----
    p = subparsers.add_parser("replace-bg", help="Replace video background via RVM person matting")
    p.add_argument("-i", "--input", required=True, help="Input video")
    p.add_argument("-o", "--output", required=True, help="Output video")
    p.add_argument("--bg", required=True, help="Background image")
    p.add_argument("--variant", default="resnet50", choices=["resnet50", "mobilenetv3"],
                   help="RVM variant (mobilenetv3 is lighter, no torchvision needed)")
    p.add_argument("--checkpoint", default=None,
                   help="Checkpoint path (default: ../models/rvm_<variant>.pth)")
    p.add_argument("--chunk", type=int, default=8, help="Frames per model call (default: 8)")
    p.add_argument("--downsample-ratio", type=float, default=None,
                   help="Internal downsample ratio (default: auto, ~512px largest side)")
    p.add_argument("--crf", type=int, default=18, help="x264 CRF (default: 18)")
    p.set_defaults(func=cmd_replace_bg)

    # ---- composite ----
    p = subparsers.add_parser("composite", help="Composite image + audio pairs into MP4 segments")
    p.add_argument("-i", "--image-dir", required=True,
                   help="Directory of image files (paired with audio by name sort order)")
    p.add_argument("-a", "--audio-dir", required=True, help="Directory of audio files")
    p.add_argument("-o", "--output", default="output",
                   help="Output directory for {index:03d}.mp4 segments (default: output/)")
    p.set_defaults(func=cmd_composite)

    # ---- concat ----
    p = subparsers.add_parser("concat", help="Concatenate all videos in a directory (stream copy)")
    p.add_argument("-d", "--dir", required=True,
                   help="Directory of video files (sorted by name, joined in order)")
    p.add_argument("-o", "--output", default=None,
                   help="Output file (default: <dir>.mp4 next to the directory)")
    p.set_defaults(func=cmd_concat)



    # ---- stitch ----
    p = subparsers.add_parser("stitch", help="Stitch multiple images into a single composite image (vertical or horizontal)")
    p.add_argument("-o", "--output", required=True, help="Output composite image")
    p.add_argument("inputs", nargs="+", help="Source image files (2 or more)")
    p.add_argument("--direction", default="vertical", choices=["vertical", "horizontal"],
                   help="Stack direction (default: vertical)")
    p.add_argument("--spacing", type=int, default=0,
                   help="Pixels between images (default: 0)")
    p.add_argument("--align", default="center", choices=["left", "center", "right", "top", "bottom"],
                   help="Alignment: left/center/right for vertical, top/center/bottom for horizontal (default: center)")
    p.add_argument("--background", default="#FFFFFF",
                   help="Background color for gaps (hex #RRGGBB or named; default: #FFFFFF)")
    p.set_defaults(func=cmd_stitch)

    # ---- overlay ----
    p = subparsers.add_parser(
        "overlay",
        help="Overlay image(s) onto the video for time windows (video stays visible around them)")
    p.add_argument("-i", "--input", required=True, help="Input video")
    p.add_argument("-o", "--output", required=True, help="Output video")
    p.add_argument("--image", help="Overlay image (single-overlay mode)")
    p.add_argument("--start", type=float, help="Overlay start time in seconds")
    p.add_argument("--end", type=float, help="Overlay end time in seconds")
    p.add_argument("--width", type=int, default=None,
                   help="Scale image to this width, keeping aspect (default: native size)")
    p.add_argument("--x", default=None,
                   help="X position: center/left/right, pixels, or ffmpeg expression (default: center)")
    p.add_argument("--y", default=None,
                   help="Y position: center/top/bottom, pixels, or expression e.g. '470-h' (default: center)")
    p.add_argument("--spec", default=None,
                   help="JSON file with a list of overlay specs (multi-overlay, single encode pass)")
    p.add_argument("--crf", type=int, default=18, help="x264 CRF (default: 18)")
    p.set_defaults(func=cmd_overlay)

    args = parser.parse_args()
    if not getattr(args, "func", None):
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
