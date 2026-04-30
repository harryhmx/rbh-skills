import logging
import uuid

import requests as http_requests
from openai import OpenAI

from common.db import get_db
from config import settings

logger = logging.getLogger(__name__)

BUCKET = "stories"


def generate_image(story_title: str, story_content: str, story_id: str | None = None) -> str | None:
    if story_id is None:
        story_id = str(uuid.uuid4())

    client = OpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
    )

    prompt = (
        f"Illustration for a children's story titled '{story_title}'. "
        f"{story_content[:200] if story_content else ''} "
        "Style: colorful children's book illustration, warm and inviting, no text."
    )

    logger.info("[image] Generating...")
    response = client.images.generate(
        model=settings.LLM_IMAGE_MODEL,
        prompt=prompt,
        size=settings.LLM_IMAGE_SIZE,
        n=1,
    )

    image_url = response.data[0].url
    logger.info("[image] Got URL: %s", image_url)

    try:
        img_res = http_requests.get(image_url, timeout=30)
        img_res.raise_for_status()
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
        logger.warning("[image] Upload failed, falling back to SiliconFlow URL: %s", e)
        return image_url


