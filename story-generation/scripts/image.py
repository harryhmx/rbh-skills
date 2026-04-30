import logging
import uuid

import requests as http_requests
from openai import OpenAI

from common.db import get_db
from config import settings

logger = logging.getLogger(__name__)

BUCKET = "stories"


def generate_image(story_title: str, story_content: str, story_id: str | None = None) -> str:
    """Generate an image via SiliconFlow and upload to Supabase Storage. Returns the public URL."""
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

    response = client.images.generate(
        model=settings.LLM_IMAGE_MODEL,
        prompt=prompt,
        size=settings.LLM_IMAGE_SIZE,
        n=1,
    )

    image_url = response.data[0].url

    # Download image from URL
    img_data = http_requests.get(image_url).content

    # Upload to Supabase Storage: stories/images/{story_id}.png
    file_path = f"images/{story_id}.png"

    db = get_db()
    db.storage.from_(BUCKET).upload(file_path, img_data, {
        "content-type": "image/png",
    })

    return db.storage.from_(BUCKET).get_public_url(file_path)
