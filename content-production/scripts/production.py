"""
Content Production — generate images and speech from text-optimizer segments.

Uses the OpenAI-compatible SiliconFlow API (same keys as text-optimizer).
Images: Flux.2-pro via ``client.images.generate()``.
Speech: Fish Speech via ``client.audio.speech.create()`` (v0.2).
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import requests as http_requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(
    Path(__file__).resolve().parents[2] / ".env"  # skills root .env
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (from skills/.env)
# ---------------------------------------------------------------------------

LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.siliconflow.com/v1")
LLM_IMAGE_MODEL = os.environ.get("LLM_IMAGE_MODEL", "black-forest-labs/FLUX.2-pro")
LLM_IMAGE_SIZE_DEFAULT = os.environ.get("LLM_IMAGE_SIZE", "512x512")
LLM_SPEECH_MODEL = os.environ.get("LLM_SPEECH_MODEL", "fishaudio/fish-speech-1.5")
LLM_SPEECH_VOICE = os.environ.get("LLM_SPEECH_VOICE", "fishaudio/fish-speech-1.5:anna")

MAX_RETRIES = 2

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_segments_json(path: str | Path) -> list[dict]:
    """Read a text-optimizer output JSON and return its ``segments`` list."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    segments = data.get("segments", [])
    if not segments:
        raise ValueError(f"No segments found in {path} (expected key 'segments')")
    return segments


def generate_images(
    segments: list[dict],
    size: str = LLM_IMAGE_SIZE_DEFAULT,
    output_dir: str | Path = "output",
    prompt_key: str = "image_prompt",
) -> list[dict]:
    """Generate an image for each segment using SiliconFlow Flux.2-pro.

    Images are saved to *output_dir* as ``{index:03d}.png`` in index order.

    Parameters
    ----------
    segments : list[dict]
        Segments from :func:`load_segments_json`.  Each must have an
        ``index`` and the *prompt_key* field.
    size : str
        Image size in ``WxH`` format (e.g. ``"1024x768"``).
    output_dir : str or Path
        Directory to save generated images.
    prompt_key : str
        Which segment key holds the image generation prompt.
        Default: ``"image_prompt"``.

    Returns
    -------
    list[dict]
        Each dict has ``index``, ``title``, ``file_path``, ``url``, and
        ``prompt`` keys.
    """
    if not LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY is not set. "
            "Set it in skills/.env or as an environment variable."
        )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    client = OpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        timeout=120.0,
    )

    results = []
    total = len(segments)

    for seg in sorted(segments, key=lambda s: s.get("index", 0)):
        idx = seg.get("index", 0)
        title = seg.get("title", f"segment-{idx}")
        prompt = seg.get(prompt_key, "")

        if not prompt:
            logger.warning("[%d/%d] No prompt for segment %d, skipping", idx + 1, total, idx)
            results.append({
                "index": idx,
                "title": title,
                "file_path": None,
                "url": None,
                "prompt": prompt,
                "error": f"No '{prompt_key}' field",
            })
            continue

        file_path = out / f"{idx:03d}.png"
        url = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "[%d/%d] Generating image for '%s' (attempt %d/%d)...",
                    idx + 1, total, title, attempt, MAX_RETRIES,
                )

                response = client.images.generate(
                    model=LLM_IMAGE_MODEL,
                    prompt=prompt,
                    size=size,
                    n=1,
                )

                if not response.data or not hasattr(response.data[0], "url"):
                    logger.warning("Empty response from image API")
                    continue

                image_url = response.data[0].url
                if not image_url:
                    logger.warning("API returned empty URL")
                    continue

                logger.info("[%d/%d] Downloading from %s...", idx + 1, total, image_url[:80])

                img_res = http_requests.get(image_url, timeout=60)
                img_res.raise_for_status()

                if len(img_res.content) < 1000:
                    logger.warning("Image too small (%d bytes), retrying", len(img_res.content))
                    continue

                file_path.write_bytes(img_res.content)
                url = image_url

                logger.info(
                    "[%d/%d] Saved %s (%d bytes)",
                    idx + 1, total, file_path.name, len(img_res.content),
                )
                break

            except Exception as exc:
                logger.warning("[%d/%d] Attempt %d failed: %s", idx + 1, total, attempt, exc)
                if attempt < MAX_RETRIES:
                    time.sleep(2)

        results.append({
            "index": idx,
            "title": title,
            "file_path": str(file_path.resolve()) if url else None,
            "url": url,
            "prompt": prompt,
        })

    # Summary
    succeeded = sum(1 for r in results if r["url"])
    logger.info("Done: %d/%d images generated → %s", succeeded, total, out.resolve())
    return results


def generate_speech(
    segments: list[dict],
    output_dir: str | Path = "output",
    prompt_key: str = "tts_prompt",
) -> list[dict]:
    """Generate speech audio for each segment using SiliconFlow Fish Speech.

    Audio files are saved to *output_dir* as ``{index:03d}.mp3``.

    .. note::
       This is a v0.2 feature — currently a stub that will be implemented
       following the same pattern as :func:`generate_images`.
    """
    if not LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY is not set. "
            "Set it in skills/.env or as an environment variable."
        )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    client = OpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
    )

    results = []
    total = len(segments)

    for seg in sorted(segments, key=lambda s: s.get("index", 0)):
        idx = seg.get("index", 0)
        title = seg.get("title", f"segment-{idx}")
        prompt = seg.get(prompt_key, "")

        if not prompt:
            logger.warning("[%d/%d] No prompt for segment %d, skipping", idx + 1, total, idx)
            results.append({
                "index": idx, "title": title, "file_path": None,
                "prompt": prompt, "error": f"No '{prompt_key}' field",
            })
            continue

        file_path = out / f"{idx:03d}.mp3"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "[%d/%d] Generating speech for '%s' (attempt %d/%d)...",
                    idx + 1, total, title, attempt, MAX_RETRIES,
                )

                # Strip markdown voice direction prefix for cleaner speech
                clean_text = prompt
                if clean_text.startswith("(") and ")" in clean_text:
                    clean_text = clean_text.split(")", 1)[1].strip()

                response = client.audio.speech.create(
                    model=LLM_SPEECH_MODEL,
                    voice=LLM_SPEECH_VOICE,
                    input=clean_text,
                )

                audio_bytes = response.content if hasattr(response, "content") else response.read()

                if len(audio_bytes) < 1000:
                    logger.warning("Audio too small (%d bytes), retrying", len(audio_bytes))
                    continue

                file_path.write_bytes(audio_bytes)

                logger.info("[%d/%d] Saved %s (%d bytes)", idx + 1, total, file_path.name, len(audio_bytes))

                results.append({
                    "index": idx,
                    "title": title,
                    "file_path": str(file_path.resolve()),
                    "prompt": prompt,
                })
                break

            except Exception as exc:
                logger.warning("[%d/%d] Attempt %d failed: %s", idx + 1, total, attempt, exc)
                if attempt < MAX_RETRIES:
                    time.sleep(2)
        else:
            logger.error("[%d/%d] All %d attempts failed", idx + 1, total, MAX_RETRIES)
            results.append({
                "index": idx, "title": title, "file_path": None,
                "prompt": prompt, "error": f"All {MAX_RETRIES} attempts failed",
            })

    succeeded = sum(1 for r in results if r.get("file_path"))
    logger.info("Done: %d/%d speech files generated → %s", succeeded, total, out.resolve())
    return results


# ---------------------------------------------------------------------------
# Image captioning — overlay title text onto generated images
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
