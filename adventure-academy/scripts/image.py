import json
import logging
import time
import urllib.error
import urllib.request
import uuid

import requests as http_requests

from common.db import get_db
from config import openai_compatible_base_url, settings

logger = logging.getLogger(__name__)

BUCKET = "adventure-academy"

MAX_RETRIES = 2


def _image_request(payload: dict) -> dict:
    """Send a JSON request to the configured SiliconFlow image endpoint."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{openai_compatible_base_url(settings.IMAGE_BASE_URL)}/images/generations",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.IMAGE_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"SiliconFlow HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"SiliconFlow request failed: {exc}") from exc


def _extract_image_urls(data: dict) -> list[str]:
    """Extract image URLs from SiliconFlow and OpenAI-style responses."""
    urls: list[str] = []
    for key in ("url", "image_url"):
        if isinstance(data.get(key), str):
            urls.append(data[key])
    for key in ("images", "data"):
        items = data.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                for key in ("url", "image_url"):
                    if isinstance(item.get(key), str):
                        urls.append(item[key])
    return urls


def generate_image(story_title: str, story_content: str, story_id: str | None = None) -> str | None:
    if story_id is None:
        story_id = str(uuid.uuid4())

    prompt = (
        f"Illustration for a children's story titled '{story_title}'. "
        f"{story_content[:200] if story_content else ''} "
        "Style: colorful children's book illustration, warm and inviting, no text."
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("[image] Generating... (attempt %d/%d)", attempt, MAX_RETRIES)

            payload: dict = {
                "model": settings.IMAGE_MODEL,
                "prompt": prompt,
            }
            if settings.IMAGE_SIZE:
                payload["image_size"] = settings.IMAGE_SIZE
            payload["output_format"] = "png"

            data = _image_request(payload)
            urls = _extract_image_urls(data)

            if not urls:
                logger.warning("[image] No image URL in SiliconFlow response")
                continue

            image_url = urls[0]
            logger.info("[image] Got URL: %s", image_url)

            img_res = http_requests.get(image_url, timeout=30)
            img_res.raise_for_status()

            if len(img_res.content) < 1000:
                logger.warning("[image] Image too small (%d bytes), retrying", len(img_res.content))
                continue

            file_path = f"images/{story_id}.png"
            logger.info("[image] Uploading %d bytes to %s/%s...", len(img_res.content), BUCKET, file_path)

            db = get_db()
            db.storage.from_(BUCKET).upload(
                file_path,
                img_res.content,
                {"content-type": "image/png", "upsert": "true"},
            )
            public_url = db.storage.from_(BUCKET).get_public_url(file_path)
            logger.info("[image] Done: %s", public_url)
            return public_url

        except Exception as e:
            logger.warning("[image] Attempt %d failed: %s", attempt, e)
            if attempt < MAX_RETRIES:
                time.sleep(2)

    logger.error("[image] All %d attempts failed", MAX_RETRIES)
    return None
