import logging
import time
import uuid

import requests as http_requests
from openai import OpenAI

from common.db import get_db
from config import settings

logger = logging.getLogger(__name__)

BUCKET = "stories"

MAX_RETRIES = 2


def generate_image(story_title: str, story_content: str, story_id: str | None = None) -> str | None:
    if story_id is None:
        story_id = str(uuid.uuid4())

    client = OpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        timeout=60.0,
    )

    prompt = (
        f"Illustration for a children's story titled '{story_title}'. "
        f"{story_content[:200] if story_content else ''} "
        "Style: colorful children's book illustration, warm and inviting, no text."
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("[image] Generating... (attempt %d/%d)", attempt, MAX_RETRIES)
            response = client.images.generate(
                model=settings.LLM_IMAGE_MODEL,
                prompt=prompt,
                size=settings.LLM_IMAGE_SIZE,
                n=1,
            )

            if not response.data or not hasattr(response.data[0], 'url'):
                logger.warning("[image] Empty or invalid response from API")
                continue

            image_url = response.data[0].url
            if not image_url:
                logger.warning("[image] API returned empty URL")
                continue

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
