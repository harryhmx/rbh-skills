import base64
import logging
import uuid

from openai import OpenAI

from common.db import get_db
from config import settings

logger = logging.getLogger(__name__)

BUCKET_NAME = "story-images"


def generate_image(story_title: str, story_content: str, story_id: str | None = None) -> str:
    """Generate an image via SiliconFlow and upload to Supabase Storage. Returns the public URL."""
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
        response_format="b64_json",
    )

    b64_data = response.data[0].b64_json

    if story_id is None:
        story_id = str(uuid.uuid4())

    db = get_db()
    file_path = f"{story_id}.png"
    image_bytes = base64.b64decode(b64_data)

    db.storage.from_(BUCKET_NAME).upload(file_path, image_bytes, {
        "content-type": "image/png",
    })

    return db.storage.from_(BUCKET_NAME).get_public_url(file_path)
