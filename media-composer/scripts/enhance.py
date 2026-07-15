"""
enhance — one-pass picture cleanup + two-pass loudness normalization.

Video: denoise before sharpening (hqdn3d → unsharp) so grain isn't amplified.
Audio: highpass + spectral denoise, then ffmpeg loudnorm in *linear* mode —
a measurement pass extracts the real input stats, which are fed back as
``measured_*`` values.  Linear mode avoids the pumping/breathing artifacts of
single-pass dynamic normalization.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from scripts.common import logger, probe_video, resolve_ffmpeg, run

DEFAULT_VIDEO_FILTER = "hqdn3d=1.5:1.5:6:6,unsharp=5:5:0.5:3:3:0.0"
DEFAULT_AUDIO_PREFILTER = "highpass=f=80,afftdn=nr=8"


def _measure_loudness(ffmpeg: str, input_path: str | Path, prefilter: str, lufs: float) -> dict:
    """First loudnorm pass: measure real input stats (JSON on stderr)."""
    proc = subprocess.run(
        [
            ffmpeg, "-hide_banner", "-y",
            "-i", str(input_path),
            "-af", f"{prefilter},loudnorm=I={lufs}:TP=-1.5:LRA=11:print_format=json",
            "-vn", "-f", "null", "-",
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    stderr = proc.stderr.decode("utf-8", errors="replace")
    match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr, re.DOTALL)
    if not match:
        raise RuntimeError(f"loudnorm measurement pass produced no stats:\n{stderr[-1000:]}")
    return json.loads(match.group(0))


def enhance(
    input_path: str | Path,
    output_path: str | Path,
    lufs: float = -16.0,
    crf: int = 16,
    preset: str = "slow",
    video_filter: str | None = None,
    audio_filter: str | None = None,
) -> dict:
    """Enhance picture and sound; returns measured/target loudness stats.

    ``video_filter`` / ``audio_filter`` fully override the default chains
    (advanced use — an explicit audio_filter skips the loudnorm two-pass).
    """
    info = probe_video(input_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = resolve_ffmpeg()
    vf = video_filter or f"{DEFAULT_VIDEO_FILTER},format=yuv420p"

    stats = None
    if audio_filter:
        af = audio_filter
    elif info["has_audio"]:
        logger.info("enhance: loudnorm measurement pass...")
        stats = _measure_loudness(ffmpeg, input_path, DEFAULT_AUDIO_PREFILTER, lufs)
        logger.info(
            "enhance: measured I=%s LUFS, TP=%s, LRA=%s → target %.1f LUFS",
            stats["input_i"], stats["input_tp"], stats["input_lra"], lufs,
        )
        af = (
            f"{DEFAULT_AUDIO_PREFILTER},"
            f"loudnorm=I={lufs}:TP=-1.5:LRA=11"
            f":measured_I={stats['input_i']}:measured_TP={stats['input_tp']}"
            f":measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}"
            f":offset={stats['target_offset']}:linear=true"
        )
    else:
        af = None

    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
        "-pix_fmt", "yuv420p",
    ]
    if af:
        cmd += ["-af", af, "-c:a", "aac", "-b:a", "192k", "-ar", "44100"]
    cmd += ["-movflags", "+faststart", str(out)]

    logger.info("enhance: rendering (crf %d, preset %s)...", crf, preset)
    run(cmd)

    return {
        "input": str(Path(input_path).resolve()),
        "output": str(out.resolve()),
        "target_lufs": lufs,
        "measured": {
            "input_i": stats["input_i"],
            "input_tp": stats["input_tp"],
            "input_lra": stats["input_lra"],
        } if stats else None,
        "duration": round(probe_video(out)["duration"], 3),
    }
