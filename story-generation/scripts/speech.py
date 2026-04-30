import logging
import re
import uuid

from openai import OpenAI

from common.db import get_db
from config import settings

logger = logging.getLogger(__name__)

BUCKET = "stories"


def _strip_markdown(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[(.+?)\]\(.*?\)', r'\1', text)
    text = re.sub(r'[-*_>~]{2,}', '', text)
    text = re.sub(r'\n{2,}', '. ', text)
    return text.strip()


def generate_speech(story_title: str, story_content: str, story_id: str | None = None) -> str | None:
    if story_id is None:
        story_id = str(uuid.uuid4())

    client = OpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
    )

    text = f"{story_title}. {story_content}" if story_content else story_title
    text = _strip_markdown(text)

    logger.info("[speech] Generating...")
    response = client.audio.speech.create(
        model=settings.LLM_SPEECH_MODEL,
        voice=settings.LLM_SPEECH_VOICE,
        input=text,
    )

    audio_bytes = response.content if hasattr(response, "content") else response.read()
    logger.info("[speech] Got %d bytes", len(audio_bytes))

    try:
        file_path = f"audio/{story_id}.mp3"
        logger.info("[speech] Uploading to %s/%s...", BUCKET, file_path)

        db = get_db()
        db.storage.from_(BUCKET).upload(
            file_path,
            audio_bytes,
            {"content-type": "audio/mpeg", "upsert": "true"},
        )
        public_url = db.storage.from_(BUCKET).get_public_url(file_path)
        logger.info("[speech] Done: %s", public_url)
        return public_url
    except Exception as e:
        logger.warning("[speech] Upload failed: %s", e)
        return None
