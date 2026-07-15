"""
caption — overlay text onto images or a video (title banner).

Three modes share one rendering core:

1. **Batch images** — segments JSON + directory of ``{index:03d}.png``
2. **Single image** — one image + one text
3. **Video title** — PIL renders a transparent PNG, ffmpeg ``overlay`` puts
   it on the video (works on slim ffmpeg builds without drawtext)

Rendering (see references/cjk-fonts.md): 2× supersampled Pillow drawing with
Lanczos downscale for crisp CJK strokes, font size auto-shrinks until the
text fits one line, and a semi-transparent rounded box keeps the text
readable on any background.  Style is fixed by
``assets/style-presets/title-default.json``; size and position are
parameters.

Note: Pillow cannot open PingFang.ttc on macOS — STHeiti Medium.ttc is the
reliable CJK choice (libass is the opposite: use "PingFang SC" there).
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.common import ASSETS_DIR, logger, probe_video, resolve_ffmpeg, run

# CJK-capable font paths Pillow can actually open, in order of preference.
_CJK_FONT_CANDIDATES = [
    "/System/Library/Fonts/STHeiti Medium.ttc",                 # macOS (Pillow-safe CJK)
    "/Library/Fonts/Arial Unicode.ttf",                         # macOS (broad coverage)
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",           # Linux (WenQuanYi)
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",             # Linux (WenQuanYi)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",   # Linux (Noto CJK)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",          # Linux (Latin fallback)
]

_PRESET_FILE = ASSETS_DIR / "style-presets" / "title-default.json"

_POSITIONS = ("top", "center", "bottom")


def _load_preset() -> dict:
    try:
        return json.loads(_PRESET_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _find_cjk_font() -> str | None:
    for path in _CJK_FONT_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def _render_banner(
    text: str,
    canvas_w: int,
    font_path: str | None = None,
    font_size: int | None = None,
):
    """Render *text* as a transparent RGBA banner sized for *canvas_w*.

    2× supersampling + Lanczos downscale; the font auto-shrinks from
    ``font_size`` (or the preset max) until the text fits a single line.
    Returns a PIL Image (RGBA) of the rounded box with centered text.
    """
    from PIL import Image, ImageDraw, ImageFont

    preset = _load_preset()
    ss = int(preset.get("supersample", 2))
    pad_x = int(preset.get("padding_x", 22)) * ss
    pad_y = int(preset.get("padding_y", 12)) * ss
    radius = int(preset.get("box_radius", 14)) * ss
    text_color = tuple(preset.get("text_color", [255, 255, 255, 255]))
    box_color = tuple(preset.get("box_color", [20, 20, 20, 152]))
    max_size = font_size or int(preset.get("max_font_size", 40))
    margin = 24 * ss  # outer margin the banner keeps from frame edges

    if not font_path:
        font_path = _find_cjk_font()
        if font_path:
            logger.info("Using font: %s", font_path)
        else:
            logger.warning("No CJK font found — text may not render Chinese")

    max_text_w = canvas_w * ss - 2 * pad_x - 2 * margin

    def load_font(px: int):
        if font_path:
            return ImageFont.truetype(font_path, px)
        return ImageFont.load_default()

    # Auto-shrink until the text fits one line (floor: 12px)
    size = max_size
    probe = Image.new("RGBA", (8, 8))
    draw = ImageDraw.Draw(probe)
    while size > 12:
        bbox = draw.textbbox((0, 0), text, font=load_font(size * ss))
        if bbox[2] - bbox[0] <= max_text_w:
            break
        size -= 1

    font = load_font(size * ss)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    banner_w = tw + 2 * pad_x
    banner_h = th + 2 * pad_y
    banner = Image.new("RGBA", (banner_w, banner_h), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(banner)
    bdraw.rounded_rectangle([(0, 0), (banner_w - 1, banner_h - 1)], radius=radius, fill=box_color)
    bdraw.text((pad_x - bbox[0], pad_y - bbox[1]), text, font=font, fill=text_color)

    # Lanczos downscale from the supersampled canvas
    banner = banner.resize((banner_w // ss, banner_h // ss), Image.LANCZOS)
    logger.debug("banner: %r → %dx%d @ %dpx", text, banner.width, banner.height, size)
    return banner


def _paste_position(img_w: int, img_h: int, banner_w: int, banner_h: int, position: str) -> tuple:
    """Top-left corner for the banner at the given position."""
    x = (img_w - banner_w) // 2
    margin = 28
    if position == "top":
        return x, margin
    if position == "center":
        return x, (img_h - banner_h) // 2
    return x, img_h - banner_h - margin  # bottom


# ---------------------------------------------------------------------------
# Mode 2 — single image
# ---------------------------------------------------------------------------


def caption_image(
    image_path: str | Path,
    text: str,
    output_path: str | Path | None = None,
    font_path: str | None = None,
    font_size: int | None = None,
    position: str = "center",
) -> dict:
    """Overlay *text* onto one image; overwrites in place if no output given."""
    from PIL import Image

    if position not in _POSITIONS:
        raise ValueError(f"position must be one of {'/'.join(_POSITIONS)}")
    src = Path(image_path)
    if not src.exists():
        raise FileNotFoundError(f"Image not found: {src}")
    out = Path(output_path) if output_path else src
    out.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(src).convert("RGBA")
    banner = _render_banner(text, img.width, font_path, font_size)
    x, y = _paste_position(img.width, img.height, banner.width, banner.height, position)
    img.alpha_composite(banner, (x, y))
    img.convert("RGB").save(out, "PNG")

    logger.info("caption: %s (%s) → %s", text, position, out)
    return {"text": text, "source": str(src.resolve()), "output": str(out.resolve())}


# ---------------------------------------------------------------------------
# Mode 1 — batch images (segments JSON)
# ---------------------------------------------------------------------------


def caption_images(
    segments: list[dict],
    image_dir: str | Path,
    output_dir: str | Path | None = None,
    font_path: str | None = None,
    font_size: int | None = None,
    position: str = "center",
) -> list[dict]:
    """Overlay each segment's ``title`` onto its ``{index:03d}.png`` image."""
    if position not in _POSITIONS:
        raise ValueError(f"position must be one of {'/'.join(_POSITIONS)}")
    src_dir = Path(image_dir)
    out_dir = Path(output_dir) if output_dir else src_dir
    if output_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for seg in sorted(segments, key=lambda s: s.get("index", 0)):
        idx = seg.get("index", 0)
        title = seg.get("title", "").strip()
        if not title:
            logger.warning("[%d] No title, skipping", idx)
            continue

        src_file = src_dir / f"{idx:03d}.png"
        if not src_file.exists():
            logger.warning("[%d] Image not found: %s", idx, src_file)
            results.append({"index": idx, "title": title, "source": str(src_file),
                            "output": None, "error": "Source image not found"})
            continue

        try:
            result = caption_image(
                src_file, title, out_dir / f"{idx:03d}.png",
                font_path=font_path, font_size=font_size, position=position,
            )
            results.append({"index": idx, "title": title,
                            "source": result["source"], "output": result["output"]})
        except Exception as exc:
            logger.error("[%d] Caption failed: %s", idx, exc)
            results.append({"index": idx, "title": title, "source": str(src_file),
                            "output": None, "error": str(exc)})

    succeeded = sum(1 for r in results if r.get("output"))
    logger.info("Done: %d/%d images captioned → %s", succeeded, len(results), out_dir.resolve())
    return results


# ---------------------------------------------------------------------------
# Mode 3 — video title overlay (PIL PNG → ffmpeg overlay)
# ---------------------------------------------------------------------------


def caption_video(
    video_path: str | Path,
    text: str,
    output_path: str | Path,
    font_path: str | None = None,
    font_size: int | None = None,
    position: str = "top",
    crf: int = 16,
) -> dict:
    """Overlay a rendered title banner onto a video.

    Uses the core ``overlay`` filter, so it works on slim ffmpeg builds
    that lack drawtext/libass.
    """
    import tempfile

    if position not in _POSITIONS:
        raise ValueError(f"position must be one of {'/'.join(_POSITIONS)}")
    info = probe_video(video_path)
    if not info["width"]:
        raise ValueError(f"No video stream in {video_path}")

    banner = _render_banner(text, info["width"], font_path, font_size)
    x, y = _paste_position(info["width"], info["height"], banner.width, banner.height, position)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        overlay_png = Path(tmp.name)
    try:
        banner.save(overlay_png, "PNG")
        cmd = [
            resolve_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(video_path),
            "-i", str(overlay_png),
            "-filter_complex", f"[0:v][1:v]overlay={x}:{y}:format=auto[v]",
            "-map", "[v]",
        ]
        if info["has_audio"]:
            cmd += ["-map", "0:a", "-c:a", "copy"]
        cmd += [
            "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(out),
        ]
        logger.info("caption(video): %r (%s) → %s", text, position, out)
        run(cmd)
    finally:
        overlay_png.unlink(missing_ok=True)

    return {
        "text": text,
        "source": str(Path(video_path).resolve()),
        "output": str(out.resolve()),
        "position": position,
        "duration": round(probe_video(out)["duration"], 3),
    }
