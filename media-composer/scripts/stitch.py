"""
stitch — combine multiple images into a single composite image.

Supports vertical (pillar / column) stacking and horizontal (panorama / row)
scanning with configurable spacing, alignment, and background color.  Pure
Pillow operation — no ffmpeg or GPU needed.  Adapted from the retired
solo-skills ``image-stitch`` skill.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PIL import Image, ImageColor

from scripts.common import logger

_DEFAULT_BG = (255, 255, 255)
_ALIGN_H = frozenset({"left", "center", "right"})
_ALIGN_V = frozenset({"top", "center", "bottom"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_color(color_str: str) -> tuple[int, int, int]:
    """Parse a color string (hex ``#RRGGBB``, ``#RGB``, or named) to an RGB tuple."""
    s = color_str.strip().lower()
    if s.startswith("#"):
        h = s.lstrip("#")
        if len(h) == 6:
            return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
        if len(h) == 3:
            return tuple(int(h[i] * 2, 16) for i in range(3))  # type: ignore[return-value]
    try:
        return ImageColor.getrgb(color_str)[:3]
    except ValueError:
        pass
    logger.warning("Unrecognised colour %r — falling back to white", color_str)
    return _DEFAULT_BG


def _load_images(
    paths: Sequence[str | Path],
) -> tuple[list[Image.Image], list[Path]]:
    """Load PIL Images from *paths*, converting any non-RGB mode.

    Returns ``(images, resolved_paths)``.  Raises ``FileNotFoundError``
    on the first missing file.
    """
    images: list[Image.Image] = []
    resolved: list[Path] = []
    for p in map(Path, paths):
        if not p.exists():
            raise FileNotFoundError(f"Input image not found: {p}")
        img = Image.open(p)
        if img.mode != "RGB":
            img = img.convert("RGB")
        images.append(img)
        resolved.append(p.resolve())
    return images, resolved


def _resolve_align(align: str, direction: str) -> str:
    """Ensure the alignment value is valid for the direction.

    When a mismatched value is passed (e.g. ``"top"`` for a vertical stack)
    we silently default to ``"center"`` with a warning — same ergonomic
    guard as the original solo-skills implementation.
    """
    a = align.lower()
    if direction == "vertical" and a in _ALIGN_V:
        logger.warning(
            "%r alignment is meant for horizontal stitching — using 'center'", a,
        )
        return "center"
    if direction == "horizontal" and a in _ALIGN_H:
        logger.warning(
            "%r alignment is meant for vertical stitching — using 'center'", a,
        )
        return "center"
    if a not in _ALIGN_H and a not in _ALIGN_V:
        logger.warning("Unknown alignment %r — using 'center'", a)
        return "center"
    return a


# ---------------------------------------------------------------------------
# Core stitch functions
# ---------------------------------------------------------------------------


def _stitch_vertical(
    images: list[Image.Image],
    spacing: int = 0,
    align: str = "center",
    background: tuple[int, int, int] = _DEFAULT_BG,
) -> Image.Image:
    """Stack images top-to-bottom, aligning along the horizontal axis."""
    max_w = max(img.width for img in images)
    total_h = sum(img.height for img in images) + spacing * (len(images) - 1)

    canvas = Image.new("RGB", (max_w, total_h), background)
    y = 0
    for img in images:
        if align == "left":
            x = 0
        elif align == "right":
            x = max_w - img.width
        else:  # center
            x = (max_w - img.width) // 2
        canvas.paste(img, (x, y))
        y += img.height + spacing
    return canvas


def _stitch_horizontal(
    images: list[Image.Image],
    spacing: int = 0,
    align: str = "center",
    background: tuple[int, int, int] = _DEFAULT_BG,
) -> Image.Image:
    """Place images left-to-right, aligning along the vertical axis."""
    max_h = max(img.height for img in images)
    total_w = sum(img.width for img in images) + spacing * (len(images) - 1)

    canvas = Image.new("RGB", (total_w, max_h), background)
    x = 0
    for img in images:
        if align == "top":
            y = 0
        elif align == "bottom":
            y = max_h - img.height
        else:  # center
            y = (max_h - img.height) // 2
        canvas.paste(img, (x, y))
        x += img.width + spacing
    return canvas


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def stitch_images(
    input_paths: Sequence[str | Path],
    output_path: str | Path,
    *,
    direction: str = "vertical",
    spacing: int = 0,
    align: str = "center",
    background: str = "#FFFFFF",
) -> dict:
    """Load, stitch, and save a set of images into a single composite.

    Parameters
    ----------
    input_paths
        Two or more image file paths (PNG, JPEG, WebP, …).
    output_path
        Where to write the composite image (extension determines format).
    direction
        ``"vertical"`` (stack top-to-bottom) or ``"horizontal"`` (side-by-side).
    spacing
        Gap in pixels between neighbouring images (default: 0).
    align
        Perpendicular alignment — ``"left"`` / ``"center"`` / ``"right"`` for
        vertical stacks, ``"top"`` / ``"center"`` / ``"bottom"`` for horizontal.
    background
        Colour for any area not covered by images.  Accepts ``#RRGGBB``,
        ``#RGB``, or named colours (default ``#FFFFFF``).

    Returns
    -------
    dict
        JSON-serialisable result with ``"output"`` path, dimensions, and input
        image list.
    """
    if len(input_paths) < 2:
        raise ValueError("At least two input images are required for stitching")

    images, resolved = _load_images(input_paths)
    align = _resolve_align(align, direction)
    bg_rgb = _parse_color(background)

    if direction == "horizontal":
        result = _stitch_horizontal(images, spacing, align, bg_rgb)
    else:
        result = _stitch_vertical(images, spacing, align, bg_rgb)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    result.save(out)
    size_bytes = out.stat().st_size

    logger.info(
        "Stitched %d images → %s (%d×%d, %d bytes)",
        len(input_paths), out.resolve(), result.width, result.height, size_bytes,
    )
    return {
        "output": str(out.resolve()),
        "width": result.width,
        "height": result.height,
        "size_bytes": size_bytes,
        "direction": direction,
        "spacing": spacing,
        "images": [str(p) for p in resolved],
    }
