"""
Image generation — multi-provider dispatch (Agnes AI / Gemini).

The provider is selected via ``IMAGE_PROVIDER`` in skills/.env:

- ``agnes`` (default) — Agnes AI ``POST /v1/images/generations``, image
  returned as a URL and downloaded.
- ``gemini`` — Google Gemini API (Imagen or native Gemini image models),
  image returned inline as base64 bytes.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path

from scripts.common import (
    IMAGE_PROVIDER,
    IMAGE_API_KEY,
    IMAGE_BASE_URL,
    IMAGE_MODEL,
    IMAGE_SIZE_DEFAULT,
    GEMINI_API_KEY,
    MAX_RETRIES,
    download_with_retry,
    logger,
)

# ---------------------------------------------------------------------------
# Agnes AI provider
# ---------------------------------------------------------------------------


def _agnes_image_request(payload: dict) -> dict:
    """Send a JSON request to the Agnes AI images endpoint."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{IMAGE_BASE_URL}/v1/images/generations",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {IMAGE_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Agnes HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Agnes request failed: {exc}") from exc


def _extract_image_urls(data: dict) -> list[str]:
    """Extract image URLs from an Agnes API response."""
    urls: list[str] = []
    if isinstance(data.get("url"), str):
        urls.append(data["url"])
    if isinstance(data.get("image_url"), str):
        urls.append(data["image_url"])
    if isinstance(data.get("data"), list):
        for item in data["data"]:
            if isinstance(item, dict):
                for key in ("url", "image_url"):
                    if isinstance(item.get(key), str):
                        urls.append(item[key])
    return urls


def _generate_one_agnes(prompt: str, size: str) -> tuple[bytes, str | None]:
    """Generate a single image via Agnes AI. Returns ``(png_bytes, source_url)``."""
    payload: dict = {
        "model": IMAGE_MODEL,
        "prompt": prompt,
        "extra_body": {"response_format": "url"},
    }
    if size:
        payload["size"] = size

    data = _agnes_image_request(payload)
    urls = _extract_image_urls(data)
    if not urls:
        raise RuntimeError("No image URL in Agnes response")

    image_url = urls[0]
    logger.info("Downloading from %s...", image_url[:80])
    return download_with_retry(image_url), image_url


# ---------------------------------------------------------------------------
# Gemini provider
# ---------------------------------------------------------------------------


def _generate_one_gemini(prompt: str, size: str) -> tuple[bytes, str | None]:
    """Generate a single image via the Gemini API. Returns ``(image_bytes, None)``."""
    from scripts.gemini import gemini_generate_image

    return gemini_generate_image(prompt, size), None


# ---------------------------------------------------------------------------
# Provider dispatch
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "agnes": (_generate_one_agnes, "IMAGE_API_KEY", lambda: IMAGE_API_KEY),
    "gemini": (_generate_one_gemini, "GEMINI_API_KEY", lambda: GEMINI_API_KEY),
}


def _resolve_provider():
    """Return the generate function for IMAGE_PROVIDER, validating its API key."""
    if IMAGE_PROVIDER not in _PROVIDERS:
        raise RuntimeError(
            f"Unknown IMAGE_PROVIDER '{IMAGE_PROVIDER}'. "
            f"Supported: {', '.join(sorted(_PROVIDERS))}."
        )
    generate_fn, key_name, key_getter = _PROVIDERS[IMAGE_PROVIDER]
    if not key_getter():
        raise RuntimeError(
            f"{key_name} is not set (required by IMAGE_PROVIDER={IMAGE_PROVIDER}). "
            "Set it in skills/.env or as an environment variable."
        )
    return generate_fn


# ---------------------------------------------------------------------------
# Batch image generation
# ---------------------------------------------------------------------------


def generate_images(
    segments: list[dict],
    size: str = IMAGE_SIZE_DEFAULT,
    output_dir: str | Path = "output",
    prompt_key: str = "image_prompt",
) -> list[dict]:
    """Generate an image for each segment via the configured provider.

    The provider is selected by ``IMAGE_PROVIDER`` (agnes / gemini).
    Images are saved to *output_dir* as ``{index:03d}.png`` in index order.

    Parameters
    ----------
    segments : list[dict]
        Segments from :func:`common.load_segments_json`.  Each must have an
        ``index`` and the *prompt_key* field.
    size : str
        Image size in ``WxH`` format (e.g. ``"1024x768"``).  For Gemini the
        size is mapped to the nearest supported aspect ratio.
    output_dir : str or Path
        Directory to save generated images.
    prompt_key : str
        Which segment key holds the image generation prompt.
        Default: ``"image_prompt"``.

    Returns
    -------
    list[dict]
        Each dict has ``index``, ``title``, ``file_path``, ``url``, and
        ``prompt`` keys.  ``url`` is the source URL for URL-based providers
        (Agnes) and ``None`` for inline-bytes providers (Gemini).
    """
    generate_fn = _resolve_provider()

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

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
        saved = False

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "[%d/%d] Generating image for '%s' via %s (attempt %d/%d)...",
                    idx + 1, total, title, IMAGE_PROVIDER, attempt, MAX_RETRIES,
                )

                img_bytes, url = generate_fn(prompt, size)

                if len(img_bytes) < 1000:
                    logger.warning("Image too small (%d bytes), retrying", len(img_bytes))
                    continue

                file_path.write_bytes(img_bytes)
                saved = True

                logger.info(
                    "[%d/%d] Saved %s (%d bytes)",
                    idx + 1, total, file_path.name, len(img_bytes),
                )
                break

            except Exception as exc:
                logger.warning("[%d/%d] Attempt %d failed: %s", idx + 1, total, attempt, exc)
                if attempt < MAX_RETRIES:
                    time.sleep(2)

        results.append({
            "index": idx,
            "title": title,
            "file_path": str(file_path.resolve()) if saved else None,
            "url": url if saved else None,
            "prompt": prompt,
        })

    # Summary
    succeeded = sum(1 for r in results if r["file_path"])
    logger.info("Done: %d/%d images generated → %s", succeeded, total, out.resolve())
    return results
