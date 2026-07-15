"""
subtitle-burn — burn an SRT into the picture via libass.

Uses the ``subtitles`` filter with ``force_style``, so it needs a
libass-capable ffmpeg (``resolve_ffmpeg(need_libass=True)`` — capability
detection, no hardcoded paths).

Style notes (see references/subtitle-styling.md):
- ASS colors are ``&HAABBGGRR`` (blue-green-red, not RGB).
- ``Fontsize`` is in libass PlayRes units — the rendered size is NOT 1:1
  pixels and needs eyeball calibration per resolution.
- ``MarginL/MarginR`` keep long lines from touching the frame edges.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.common import ASSETS_DIR, logger, probe_video, resolve_ffmpeg, run

# Named color presets → ASS &HAABBGGRR
_COLOR_PRESETS = {
    "teal": "&H00A6B814",     # #14B8A6
    "white": "&H00FFFFFF",
    "yellow": "&H0000FFFF",   # #FFFF00
    "black": "&H00000000",
}

_ALIGNMENTS = {"bottom": 2, "top": 8}

_PRESET_FILE = ASSETS_DIR / "style-presets" / "subtitle-default.json"


def _load_preset() -> dict:
    try:
        return json.loads(_PRESET_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _to_ass_color(color: str) -> str:
    """Convert a preset name or #RRGGBB to ASS &HAABBGGRR."""
    if color in _COLOR_PRESETS:
        return _COLOR_PRESETS[color]
    text = color.lstrip("#")
    if len(text) == 6:
        try:
            r, g, b = text[0:2], text[2:4], text[4:6]
            int(text, 16)
            return f"&H00{b.upper()}{g.upper()}{r.upper()}"
        except ValueError:
            pass
    raise ValueError(
        f"Invalid color: {color!r} (use {'/'.join(_COLOR_PRESETS)} or #RRGGBB)"
    )


def subtitle_burn(
    input_path: str | Path,
    srt_path: str | Path,
    output_path: str | Path,
    font: str | None = None,
    font_size: int | None = None,
    color: str | None = None,
    position: str | None = None,
    margin_v: int | None = None,
    margin_lr: int | None = None,
    crf: int = 16,
) -> dict:
    """Burn *srt_path* into the video with configurable libass styling.

    Defaults come from ``assets/style-presets/subtitle-default.json``
    (the values validated on bill-talks-v7).
    """
    preset = _load_preset()
    font = font or preset.get("font", "PingFang SC")
    font_size = font_size if font_size is not None else preset.get("font_size", 12)
    color = color or preset.get("color", "teal")
    position = position or preset.get("position", "bottom")
    margin_v = margin_v if margin_v is not None else preset.get("margin_v", 20)
    margin_lr = margin_lr if margin_lr is not None else preset.get("margin_lr", 28)
    outline = preset.get("outline", 2)
    shadow = preset.get("shadow", 1)

    if position not in _ALIGNMENTS:
        raise ValueError(f"position must be one of {'/'.join(_ALIGNMENTS)}")
    srt = Path(srt_path)
    if not srt.exists():
        raise FileNotFoundError(f"SRT not found: {srt}")
    probe_video(input_path)  # validates input exists / is media

    ass_color = _to_ass_color(color)
    force_style = (
        f"FontName={font},Fontsize={font_size},"
        f"PrimaryColour={ass_color},OutlineColour=&H00000000,"
        f"BorderStyle=1,Outline={outline},Shadow={shadow},"
        f"Alignment={_ALIGNMENTS[position]},"
        f"MarginL={margin_lr},MarginR={margin_lr},MarginV={margin_v}"
    )
    # The subtitles filter parses ':' and ',' — escape the filename minimally.
    srt_arg = str(srt).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = resolve_ffmpeg(need_libass=True)
    logger.info("subtitle-burn: %s + %s (%s, size %s, %s) → %s",
                Path(input_path).name, srt.name, color, font_size, position, out)
    run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(input_path),
        "-vf", f"subtitles='{srt_arg}':force_style='{force_style}'",
        "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(out),
    ])

    return {
        "input": str(Path(input_path).resolve()),
        "srt": str(srt.resolve()),
        "output": str(out.resolve()),
        "style": {
            "font": font, "font_size": font_size, "color": color,
            "position": position, "margin_v": margin_v, "margin_lr": margin_lr,
        },
        "duration": round(probe_video(out)["duration"], 3),
    }
