"""
concat — join video segments into one final video.

Files are sorted alphabetically and joined via ffmpeg's concat demuxer with
stream copy — fast and lossless, but every source must share the same codec
and encoding parameters (true for same-pipeline outputs like ``composite``'s).
Migrated from the retired video-converter skill.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from scripts.common import logger, resolve_ffmpeg, run

_VIDEO_EXTS = frozenset({".mp4", ".mov", ".avi", ".mkv", ".webm"})


def concat_videos(
    video_dir: str | Path,
    output_path: str | Path | None = None,
) -> dict:
    """Concatenate all videos in *video_dir* (sorted by name, stream copy).

    Default output is ``<video_dir>.mp4`` next to the directory; pass
    *output_path* to override.
    """
    src = Path(video_dir).resolve()
    if not src.is_dir():
        raise ValueError(f"Not a directory: {src}")

    videos = sorted(
        p for p in src.iterdir()
        if p.is_file() and p.suffix.lower() in _VIDEO_EXTS
    )
    if not videos:
        raise ValueError(f"No video files found in {src}")

    out_path = Path(output_path) if output_path else src.parent / f"{src.name}.mp4"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Concatenating %d video files → %s", len(videos), out_path.name)

    file_list = "\n".join(f"file '{v.resolve()}'" for v in videos)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", prefix="mc-concat-", delete=False,
    ) as fh:
        fh.write(file_list)
        list_path = fh.name

    try:
        run([
            resolve_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            str(out_path),
        ])
    finally:
        Path(list_path).unlink(missing_ok=True)

    size = out_path.stat().st_size
    logger.info("Done — %s (%d bytes)", out_path.name, size)
    return {
        "input_dir": str(src),
        "input_count": len(videos),
        "output": str(out_path.resolve()),
        "size_bytes": size,
    }
