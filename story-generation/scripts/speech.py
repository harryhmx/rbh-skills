import logging
import uuid

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
