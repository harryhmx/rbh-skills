"""
trim — cut the head/tail of a video.

Always re-encodes (libx264): stream copy (``-c copy``) freezes the picture at
the nearest keyframe, and talking-head footage has large keyframe intervals,
so a copied cut can hold a stale frame for seconds.
"""

from __future__ import annotations

from pathlib import Path

from scripts.common import logger, probe_video, resolve_ffmpeg, run


def trim(
    input_path: str | Path,
    output_path: str | Path,
    start: float | None = None,
    end: float | None = None,
    head: float | None = None,
    tail: float | None = None,
    crf: int = 18,
) -> dict:
    """Trim a video and re-encode it cleanly.

    Either absolute ``start``/``end`` seconds, or ``head``/``tail`` seconds to
    drop from each end — the two styles are mutually exclusive.
    """
    if (head is not None or tail is not None) and (start is not None or end is not None):
        raise ValueError("Use either --start/--end or --head/--tail, not both")

    info = probe_video(input_path)
    duration = info["duration"]

    if head is not None or tail is not None:
        start = head or 0.0
        end = duration - (tail or 0.0)
    else:
        start = start or 0.0
        end = end if end is not None else duration

    if not 0 <= start < end <= duration + 0.001:
        raise ValueError(
            f"Invalid range: start={start:.3f}, end={end:.3f} (duration {duration:.3f})"
        )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    length = end - start
    cmd = [
        resolve_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start:.3f}",          # input-level seek (fast)
        "-i", str(input_path),
        "-t", f"{length:.3f}",
        "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
        "-pix_fmt", "yuv420p",
    ]
    if info["has_audio"]:
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    cmd += ["-movflags", "+faststart", str(out)]

    logger.info("trim: %.3fs–%.3fs (%.3fs) → %s", start, end, length, out)
    run(cmd)

    result = probe_video(out)
    return {
        "input": str(Path(input_path).resolve()),
        "output": str(out.resolve()),
        "start": round(start, 3),
        "end": round(end, 3),
        "duration": round(result["duration"], 3),
    }
