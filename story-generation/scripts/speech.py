import logging
import uuid

from openai import OpenAI

from common.db import get_db
from config import settings

logger = logging.getLogger(__name__)

BUCKET_NAME = "story-audio"


def generate_speech(story_title: str, story_content: str, story_id: str | None = None) -> str:
    """Generate audio via SiliconFlow TTS and upload to Supabase Storage. Returns the public URL."""
    client = OpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
    )

    text = f"{story_title}. {story_content}" if story_content else story_title

    response = client.audio.speech.create(
        model=settings.LLM_SPEECH_MODEL,
        voice=settings.LLM_SPEECH_VOICE,
        input=text,
    )

    if story_id is None:
        story_id = str(uuid.uuid4())

    db = get_db()
    file_path = f"{story_id}.mp3"

    db.storage.from_(BUCKET_NAME).upload(file_path, response.content, {
        "content-type": "audio/mpeg",
    })

    return db.storage.from_(BUCKET_NAME).get_public_url(file_path)
