"""
extract-audio — pull the audio track out of a video.

``wav`` is lossless (feed it to ``transcribe``); ``aac``/``mp3`` are for
distribution.
"""

from __future__ import annotations

from pathlib import Path

from scripts.common import logger, probe_video, resolve_ffmpeg, run

_CODECS = {
    "aac": ["-c:a", "aac"],
    "mp3": ["-c:a", "libmp3lame"],
    "wav": ["-c:a", "pcm_s16le"],
}


def extract_audio(
    input_path: str | Path,
    output_path: str | Path,
    format: str = "aac",
    bitrate: str = "192k",
) -> dict:
    """Extract the audio track (``-vn``) as aac / mp3 / wav."""
    if format not in _CODECS:
        raise ValueError(f"Unsupported format: {format} (choose {'/'.join(_CODECS)})")

    info = probe_video(input_path)
    if not info["has_audio"]:
        raise ValueError(f"No audio stream in {input_path}")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        resolve_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(input_path),
        "-vn", "-map", "0:a",
        *_CODECS[format],
    ]
    if format != "wav":
        cmd += ["-b:a", bitrate]
    cmd.append(str(out))

    logger.info("extract-audio: %s → %s (%s)", Path(input_path).name, out, format)
    run(cmd)

    return {
        "input": str(Path(input_path).resolve()),
        "output": str(out.resolve()),
        "format": format,
        "duration": round(probe_video(out)["duration"], 3),
    }
