"""
Shared utilities for media-composer modules.

Provides the ffmpeg/ffprobe plumbing every editing subcommand relies on:
probing, capability-aware ffmpeg resolution (libass detection), subprocess
handling, and timecode conversion.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

SKILL_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = SKILL_ROOT.parent / "models"
ASSETS_DIR = SKILL_ROOT / "assets"


# ---------------------------------------------------------------------------
# Subprocess wrapper
# ---------------------------------------------------------------------------


def run(cmd: list, input: bytes | None = None, capture: bool = False) -> str:
    """Run *cmd*, raising RuntimeError with stderr detail on failure.

    Returns stdout as text when *capture* is True, else an empty string.
    """
    logger.debug("run: %s", " ".join(str(c) for c in cmd))
    proc = subprocess.run(
        [str(c) for c in cmd],
        input=input,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"Command failed (exit {proc.returncode}): {cmd[0]}\n{stderr[-2000:]}"
        )
    return proc.stdout.decode("utf-8", errors="replace") if capture else ""


# ---------------------------------------------------------------------------
# ffmpeg / ffprobe resolution
# ---------------------------------------------------------------------------

# Common keg-only / non-PATH locations for a full-featured ffmpeg build.
_FFMPEG_FULL_CANDIDATE_PATHS = [
    "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg",  # macOS ARM (Homebrew keg-only)
    "/usr/local/opt/ffmpeg-full/bin/ffmpeg",     # macOS Intel (Homebrew keg-only)
]


def _has_libass(ffmpeg_path: str) -> bool:
    """True if the given ffmpeg binary has the subtitles/ass filters."""
    try:
        out = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-filters"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15,
        ).stdout.decode("utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired):
        return False
    return " subtitles " in out or " ass " in out


@lru_cache(maxsize=None)
def resolve_ffmpeg(need_libass: bool = False) -> str:
    """Locate an ffmpeg binary, by capability rather than hardcoded path.

    With ``need_libass=False`` any ffmpeg on PATH is fine.  With
    ``need_libass=True`` candidates are probed in order — ``MC_FFMPEG_FULL``
    env var, ``ffmpeg-full`` on PATH, ``brew --prefix ffmpeg-full``, common
    keg locations, plain ``ffmpeg`` — and the first binary whose ``-filters``
    output includes subtitles/ass wins.  Any libass-capable build (brew, apt,
    source, static) is accepted.
    """
    if not need_libass:
        path = shutil.which("ffmpeg")
        if not path:
            raise RuntimeError(
                "ffmpeg not found on PATH. Install it first "
                "(macOS: `brew install ffmpeg`; Linux: `sudo apt install ffmpeg`)."
            )
        return path

    candidates: list[str] = []
    env_path = os.environ.get("MC_FFMPEG_FULL", "").strip()
    if env_path:
        candidates.append(env_path)
    which_full = shutil.which("ffmpeg-full")
    if which_full:
        candidates.append(which_full)
    try:
        prefix = subprocess.run(
            ["brew", "--prefix", "ffmpeg-full"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15,
        ).stdout.decode().strip()
        if prefix:
            candidates.append(str(Path(prefix) / "bin" / "ffmpeg"))
    except (OSError, subprocess.TimeoutExpired):
        pass
    candidates.extend(_FFMPEG_FULL_CANDIDATE_PATHS)
    which_plain = shutil.which("ffmpeg")
    if which_plain:
        candidates.append(which_plain)

    for cand in candidates:
        if Path(cand).exists() and _has_libass(cand):
            return cand

    raise RuntimeError(
        "No ffmpeg with libass (subtitles/ass filters) found. Install one:\n"
        "  macOS: brew install ffmpeg-full   (or set MC_FFMPEG_FULL=/path/to/ffmpeg)\n"
        "  Linux: sudo apt install ffmpeg    (distro builds normally include libass)"
    )


def resolve_ffprobe() -> str:
    """Locate ffprobe (ships alongside ffmpeg)."""
    path = shutil.which("ffprobe")
    if not path:
        raise RuntimeError("ffprobe not found on PATH (install ffmpeg).")
    return path


# ---------------------------------------------------------------------------
# Probing
# ---------------------------------------------------------------------------


def probe_video(path: str | Path) -> dict:
    """Probe a media file → dict(width, height, fps, duration, has_audio).

    ``width``/``height``/``fps`` are None for audio-only files.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input not found: {p}")

    out = run(
        [
            resolve_ffprobe(), "-v", "error",
            "-show_entries", "stream=codec_type,width,height,r_frame_rate",
            "-show_entries", "format=duration",
            "-of", "json", str(p),
        ],
        capture=True,
    )
    data = json.loads(out)
    info: dict = {
        "width": None, "height": None, "fps": None,
        "duration": float(data.get("format", {}).get("duration") or 0.0),
        "has_audio": False,
    }
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and info["width"] is None:
            info["width"] = stream.get("width")
            info["height"] = stream.get("height")
            fr = stream.get("r_frame_rate", "0/1")
            try:
                num, den = fr.split("/")
                info["fps"] = int(num) / int(den) if int(den) else None
            except ValueError:
                info["fps"] = None
        elif stream.get("codec_type") == "audio":
            info["has_audio"] = True
    return info


# ---------------------------------------------------------------------------
# Timecodes
# ---------------------------------------------------------------------------


def parse_time(value: str | float | int) -> float:
    """Parse seconds from a number or ``[HH:]MM:SS[.mmm]`` string."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if ":" not in text:
        return float(text)
    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError(f"Invalid timecode: {value!r}")
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds


def format_time(seconds: float) -> str:
    """Format seconds as ``HH:MM:SS.mmm``."""
    ms = round((seconds - int(seconds)) * 1000)
    total = int(seconds)
    if ms == 1000:
        total, ms = total + 1, 0
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


# ---------------------------------------------------------------------------
# RVM helpers
# ---------------------------------------------------------------------------


def auto_downsample_ratio(h: int, w: int) -> float:
    """Official RVM heuristic: scale the largest side toward 512px internally."""
    return min(512 / max(h, w), 1)
