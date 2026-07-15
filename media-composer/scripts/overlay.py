"""
Overlay images onto a video for specific time windows.

Unlike ``replace-segment`` (which swaps the whole frame for a still image),
``overlay`` composites the image *on top of* the running video — the person
and background stay visible around the image.  Multiple overlays render in a
single encode pass.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.common import logger, probe_video, resolve_ffmpeg, run

# Position keywords → ffmpeg overlay expressions.
_X_PRESETS = {"center": "(W-w)/2", "left": "12", "right": "W-w-12"}
_Y_PRESETS = {"center": "(H-h)/2", "top": "28", "bottom": "H-h-28"}


def _pos_expr(value: str | float | None, presets: dict[str, str], default: str) -> str:
    """Resolve a position: keyword preset, number, or raw ffmpeg expression."""
    if value is None:
        return presets[default]
    value = str(value)
    return presets.get(value, value)


def overlay_images(
    input_path: str | Path,
    output_path: str | Path,
    overlays: list[dict],
    crf: int = 18,
) -> dict:
    """Overlay one or more images onto a video, each within a time window.

    Parameters
    ----------
    input_path, output_path : str or Path
        Source video and destination file.
    overlays : list of dict
        Each spec: ``{"image": path, "start": sec, "end": sec}`` plus optional
        ``"width"`` (scale image to this width, keeps aspect), ``"x"`` / ``"y"``
        (keyword ``center``/``left``/``right``/``top``/``bottom``, a pixel
        number, or a raw ffmpeg expression such as ``"470-h"``).
    crf : int
        x264 quality (lower = better).  Default 18.

    Returns
    -------
    dict with input/output paths, overlay specs as applied, and duration.
    """
    inp = Path(input_path).expanduser().resolve()
    out = Path(output_path).expanduser().resolve()
    if not inp.exists():
        raise FileNotFoundError(f"Input video not found: {inp}")
    if not overlays:
        raise ValueError("At least one overlay spec is required")

    images = []
    for ov in overlays:
        img = Path(ov["image"]).expanduser().resolve()
        if not img.exists():
            raise FileNotFoundError(f"Overlay image not found: {img}")
        images.append(img)

    parts = []
    applied = []
    prev = "[0:v]"
    for i, ov in enumerate(overlays):
        start, end = float(ov["start"]), float(ov["end"])
        if end <= start:
            raise ValueError(f"Overlay {i}: end ({end}) must be after start ({start})")
        width = ov.get("width")
        x = _pos_expr(ov.get("x"), _X_PRESETS, "center")
        y = _pos_expr(ov.get("y"), _Y_PRESETS, "center")

        img_label = f"[img{i}]"
        scale = f"scale={int(width)}:-1" if width else "null"
        parts.append(f"[{i + 1}:v]{scale}{img_label}")

        out_label = f"[v{i}]" if i < len(overlays) - 1 else "[vout]"
        parts.append(
            f"{prev}{img_label}overlay={x}:{y}:enable='between(t,{start},{end})'{out_label}"
        )
        prev = out_label
        applied.append({
            "image": str(images[i]), "start": start, "end": end,
            "width": width, "x": x, "y": y,
        })

    out.parent.mkdir(parents=True, exist_ok=True)
    logger.info("overlay: %d image(s) onto %s", len(overlays), inp.name)

    cmd = [resolve_ffmpeg(), "-y", "-i", str(inp)]
    for img in images:
        cmd.extend(["-i", str(img)])
    cmd.extend([
        "-filter_complex", ";".join(parts),
        "-map", "[vout]", "-map", "0:a?",
        "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
        "-pix_fmt", "yuv420p", "-c:a", "copy",
        "-movflags", "+faststart",
        str(out),
    ])
    run(cmd)

    info = probe_video(out)
    logger.info("overlay: done → %s (%.1fs)", out.name, info["duration"])
    return {
        "input": str(inp),
        "output": str(out),
        "overlays": applied,
        "duration": round(info["duration"], 3),
    }


def load_overlay_spec(spec_path: str | Path) -> list[dict]:
    """Load a JSON overlay spec file (a list of overlay dicts)."""
    path = Path(spec_path).expanduser().resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Overlay spec must be a JSON list, got {type(data).__name__}")
    return data
