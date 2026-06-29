"""
Image generation via Agnes AI (``agnes-image-2.1-flash``).

Uses ``POST /v1/images/generations`` to create images from text prompts.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path

from scripts.common import (
    IMAGE_API_KEY,
    IMAGE_BASE_URL,
    IMAGE_MODEL,
    IMAGE_SIZE_DEFAULT,
    MAX_RETRIES,
    download_with_retry,
    logger,
)

# ---------------------------------------------------------------------------
# Agnes AI image helpers
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


# ---------------------------------------------------------------------------
# Batch image generation
# ---------------------------------------------------------------------------


def generate_images(
    segments: list[dict],
    size: str = IMAGE_SIZE_DEFAULT,
    output_dir: str | Path = "output",
    prompt_key: str = "image_prompt",
) -> list[dict]:
    """Generate an image for each segment using Agnes AI (agnes-image-2.1-flash).

    Images are saved to *output_dir* as ``{index:03d}.png`` in index order.

    Parameters
    ----------
    segments : list[dict]
        Segments from :func:`common.load_segments_json`.  Each must have an
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
    if not IMAGE_API_KEY:
        raise RuntimeError(
            "IMAGE_API_KEY is not set. "
            "Set it in skills/.env or as an environment variable."
        )

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

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "[%d/%d] Generating image for '%s' (attempt %d/%d)...",
                    idx + 1, total, title, attempt, MAX_RETRIES,
                )

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
                    logger.warning("No image URL in Agnes response")
                    continue

                image_url = urls[0]
                logger.info("[%d/%d] Downloading from %s...", idx + 1, total, image_url[:80])

                img_res = download_with_retry(image_url)

                if len(img_res) < 1000:
                    logger.warning("Image too small (%d bytes), retrying", len(img_res))
                    continue

                file_path.write_bytes(img_res)
                url = image_url

                logger.info(
                    "[%d/%d] Saved %s (%d bytes)",
                    idx + 1, total, file_path.name, len(img_res),
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
