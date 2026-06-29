"""
Image captioning — overlay segment titles onto generated PNG images.

Uses Pillow to draw semi-transparent banner overlays with centered text.
Supports CJK fonts via auto-detection on Linux and macOS.
"""

from __future__ import annotations

import logging
from pathlib import Path

from scripts.common import logger

# ---------------------------------------------------------------------------
# Font configuration
# ---------------------------------------------------------------------------

# CJK-capable font paths to try (order: preference)
_CJK_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

_DEFAULT_FONT_SIZE = 36


def _find_cjk_font() -> str | None:
    """Return the first available CJK-capable font path, or None."""
    for path in _CJK_FONT_CANDIDATES:
        if Path(path).exists():
            return path
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def caption_images(
    segments: list[dict],
    image_dir: str | Path,
    output_dir: str | Path | None = None,
    font_path: str | None = None,
    font_size: int = _DEFAULT_FONT_SIZE,
) -> list[dict]:
    """Overlay the ``title`` from each segment onto the corresponding image.

    Images are matched by ``{index:03d}.png`` filename.  Text is placed
    centered on a semi-transparent dark banner spanning the image width.

    Parameters
    ----------
    segments : list[dict]
        Segments with ``index`` and ``title`` keys.
    image_dir : str or Path
        Directory containing PNG images named ``{index:03d}.png``.
    output_dir : str or Path or None
        Where to write captioned images.  If ``None``, overwrites originals.
    font_path : str or None
        Path to a .ttf/.ttc font (CJK-capable for Chinese text).  Auto-detected
        from common system paths when ``None``.
    font_size : int
        Font size in points.  Default: 36.

    Returns
    -------
    list[dict]
        Each dict has ``index``, ``title``, ``source``, ``output`` keys.
    """
    from PIL import Image, ImageDraw, ImageFont

    src_dir = Path(image_dir)
    out_dir = Path(output_dir) if output_dir else src_dir
    if output_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    # Resolve font
    font = None
    if font_path:
        font = ImageFont.truetype(font_path, font_size)
    else:
        auto = _find_cjk_font()
        if auto:
            font = ImageFont.truetype(auto, font_size)
            logger.info("Using font: %s", auto)
        else:
            logger.warning("No CJK font found — using PIL default (may not render Chinese)")
            font = ImageFont.load_default()

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
            results.append({"index": idx, "title": title, "source": str(src_file), "output": None, "error": "Source image not found"})
            continue

        out_file = out_dir / f"{idx:03d}.png"

        try:
            img = Image.open(src_file).convert("RGBA")
            draw = ImageDraw.Draw(img)
            img_w, img_h = img.size

            # Measure text
            bbox = draw.textbbox((0, 0), title, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]

            # Banner: full width, centered vertically
            banner_h = int(th * 1.6)
            banner_y = (img_h - banner_h) // 2

            # Draw semi-transparent dark overlay
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.rectangle(
                [(0, banner_y), (img_w, banner_y + banner_h)],
                fill=(0, 0, 0, 160),
            )
            img = Image.alpha_composite(img, overlay)

            # Draw title text centered
            draw = ImageDraw.Draw(img)
            tx = (img_w - tw) // 2
            ty = banner_y + (banner_h - th) // 2
            draw.text((tx, ty), title, font=font, fill=(255, 255, 255, 255))

            # Save as RGB (no alpha needed for final)
            img.convert("RGB").save(out_file, "PNG")

            logger.info("[%d] Captioned: %s", idx, out_file.name)

            results.append({
                "index": idx,
                "title": title,
                "source": str(src_file.resolve()),
                "output": str(out_file.resolve()),
            })

        except Exception as exc:
            logger.error("[%d] Caption failed: %s", idx, exc)
            results.append({"index": idx, "title": title, "source": str(src_file), "output": None, "error": str(exc)})

    succeeded = sum(1 for r in results if r.get("output"))
    logger.info("Done: %d/%d images captioned → %s", succeeded, len(results), out_dir.resolve())
    return results
