"""
replace-segment — swap a time range of a video for a still image (or clip).

Three-part concat filter graph: [before] + [image scaled/padded to frame] +
[after].  The source audio is kept across the whole timeline by default (the
replaced range plays as a voice-over on the image).
"""

from __future__ import annotations

from pathlib import Path

from scripts.common import logger, probe_video, resolve_ffmpeg, run


def replace_segment(
    input_path: str | Path,
    image_path: str | Path,
    start: float,
    end: float,
    output_path: str | Path,
    pad_color: str = "black",
    fit: str = "contain",
    drop_audio: bool = False,
    crf: int = 18,
) -> dict:
    """Replace ``start``–``end`` with *image_path*, audio preserved.

    ``fit='contain'`` letterboxes the whole image with ``pad_color`` bars;
    ``fit='cover'`` fills the frame and crops overflow.  Boundaries snap to
    the nearest integer frame to avoid seam artifacts.
    """
    if fit not in ("contain", "cover"):
        raise ValueError("fit must be 'contain' or 'cover'")

    info = probe_video(input_path)
    w, h, fps, duration = info["width"], info["height"], info["fps"], info["duration"]
    if not w:
        raise ValueError(f"No video stream in {input_path}")
    if not Path(image_path).exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    if not 0 <= start < end <= duration + 0.001:
        raise ValueError(
            f"Invalid range: start={start:.3f}, end={end:.3f} (duration {duration:.3f})"
        )

    # Snap boundaries to integer frames (avoids seams at the concat joints)
    fps = fps or 30
    start = round(start * fps) / fps
    end = round(end * fps) / fps
    seg_len = end - start

    if fit == "contain":
        img_chain = (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:{pad_color}"
        )
    else:  # cover
        img_chain = (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h}"
        )

    filter_complex = (
        f"[0:v]trim=start=0:end={start:.6f},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v1];"
        f"[1:v]{img_chain},setsar=1,format=yuv420p,fps={fps:g}[v2];"
        f"[0:v]trim=start={end:.6f},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v3];"
        f"[v1][v2][v3]concat=n=3:v=1:a=0[vout]"
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        resolve_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(input_path),
        "-loop", "1", "-framerate", f"{fps:g}", "-t", f"{seg_len:.6f}", "-i", str(image_path),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
    ]
    if info["has_audio"] and not drop_audio:
        cmd += ["-map", "0:a", "-c:a", "copy"]
    cmd += [
        "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(out),
    ]

    logger.info(
        "replace-segment: %.3fs–%.3fs (%.3fs) ← %s (%s) → %s",
        start, end, seg_len, Path(image_path).name, fit, out,
    )
    run(cmd)

    return {
        "input": str(Path(input_path).resolve()),
        "image": str(Path(image_path).resolve()),
        "output": str(out.resolve()),
        "start": round(start, 3),
        "end": round(end, 3),
        "duration": round(probe_video(out)["duration"], 3),
    }
