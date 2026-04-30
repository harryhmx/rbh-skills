import logging
import uuid

import requests as http_requests
from openai import OpenAI

from common.db import get_db
from config import settings

logger = logging.getLogger(__name__)

BUCKET = "stories"


def _ensure_bucket(db) -> bool:
    """Try to create the bucket if it doesn't exist. Returns True if bucket is ready."""
    try:
        buckets = db.storage.list_buckets()
        names = [b.name for b in buckets]
        if BUCKET in names:
            return True
        db.storage.create_bucket(BUCKET, {"public": True})
        logger.info("Created Supabase Storage bucket: %s", BUCKET)
        return True
    except Exception as e:
        logger.warning("Failed to create bucket %s: %s", BUCKET, e)
        return False


def generate_image(story_title: str, story_content: str, story_id: str | None = None) -> str | None:
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

    logger.info("[image] Generating image for story '%s'...", story_title)
    response = client.images.generate(
        model=settings.LLM_IMAGE_MODEL,
        prompt=prompt,
        size=settings.LLM_IMAGE_SIZE,
        n=1,
    )

    image_url = response.data[0].url
    logger.info("[image] Got image URL: %s", image_url)

    # Try to download and upload to Supabase Storage
    try:
        logger.info("[image] Downloading image from SiliconFlow...")
        img_res = http_requests.get(image_url, timeout=30)
        img_res.raise_for_status()
        img_data = img_res.content

        file_path = f"images/{story_id}.png"
        db = get_db()

        if not _ensure_bucket(db):
            logger.warning("[image] Bucket not available, using SiliconFlow URL directly")
            return image_url

        logger.info("[image] Uploading to Supabase Storage (%d bytes)...", len(img_data))
        db.storage.from_(BUCKET).upload(file_path, img_data, {
            "content-type": "image/png",
        })

        public_url = db.storage.from_(BUCKET).get_public_url(file_path)
        logger.info("[image] Upload successful: %s", public_url)
        return public_url
    except Exception as e:
        logger.warning("[image] Upload failed, using SiliconFlow URL: %s", e)
        return image_url


def generate_speech(story_title: str, story_content: str, story_id: str | None = None) -> str | None:
    """Generate audio via SiliconFlow TTS and upload to Supabase Storage. Returns the public URL."""
    if story_id is None:
        story_id = str(uuid.uuid4())

    client = OpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
    )

    text = f"{story_title}. {story_content}" if story_content else story_title

    logger.info("[speech] Generating audio for story '%s'...", story_title)
    response = client.audio.speech.create(
        model=settings.LLM_SPEECH_MODEL,
        voice=settings.LLM_SPEECH_VOICE,
        input=text,
    )

    audio_bytes = response.content if hasattr(response, "content") else response.read()
    logger.info("[speech] Got audio (%d bytes)", len(audio_bytes))

    # Try to upload to Supabase Storage
    try:
        file_path = f"audio/{story_id}.mp3"
        db = get_db()

        if not _ensure_bucket(db):
            logger.warning("[speech] Bucket not available, skipping audio upload")
            return None

        logger.info("[speech] Uploading to Supabase Storage...")
        db.storage.from_(BUCKET).upload(file_path, audio_bytes, {
            "content-type": "audio/mpeg",
        })

        public_url = db.storage.from_(BUCKET).get_public_url(file_path)
        logger.info("[speech] Upload successful: %s", public_url)
        return public_url
    except Exception as e:
        logger.warning("[speech] Upload failed, skipping audio: %s", e)
        return None
