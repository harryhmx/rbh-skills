import logging
import uuid

from openai import OpenAI

from common.db import get_db
from config import settings

logger = logging.getLogger(__name__)

BUCKET = "stories"


def generate_speech(story_title: str, story_content: str, story_id: str | None = None) -> str:
    """Generate audio via SiliconFlow TTS and upload to Supabase Storage. Returns the public URL."""
    if story_id is None:
        story_id = str(uuid.uuid4())

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

    audio_bytes = response.content if hasattr(response, "content") else response.read()

    # Upload to Supabase Storage: stories/audio/{story_id}.mp3
    file_path = f"audio/{story_id}.mp3"

    db = get_db()
    db.storage.from_(BUCKET).upload(file_path, audio_bytes, {
        "content-type": "audio/mpeg",
    })

    return db.storage.from_(BUCKET).get_public_url(file_path)
