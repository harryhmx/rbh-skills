#!/usr/bin/env python3
"""CLI entry point for media-composer — media editing and transcription toolkit.

Usage:
    python scripts/cli.py transcribe -i <audio> [-o <output>] [--backend mlx-whisper] [--model turbo] [--lang zh]
"""

from __future__ import annotations

import argparse
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

    args = parser.parse_args()

    if args.command == "transcribe":
        cmd_transcribe(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
