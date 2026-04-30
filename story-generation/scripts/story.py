import json
import logging
import uuid
from datetime import datetime, timezone

from common.db import get_db
from config import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a children's story generator.
Given a project's title and description, along with the reader's age and Lexile Level, generate a short story in markdown format.

Requirements:
- The story should be age-appropriate and match the reader's Lexile Level.
- The content must be written in markdown format (can include headings, bold text, etc.).
- The total content MUST be at most 100 words.
- Write the story in English.

Return ONLY a valid JSON object with exactly two keys: "title" and "content".
- "title": a concise story title (max 100 characters)
- "content": the story body in markdown format (max 100 words total)
No markdown, no extra text, no code fences."""


def generate_story(
    project_title: str,
    project_description: str,
    user_age: int,
    user_level: str,
) -> dict:
    client = OpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
    )
    prompt = (
        f"Project title: {project_title}\n"
        f"Project description: {project_description}\n"
        f"Reader age: {user_age}\n"
        f"Reader level: {user_level}"
    )
    response = client.chat.completions.create(
        model=settings.LLM_CHAT_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    data = json.loads(raw)
    return {"title": data["title"], "content": data["content"]}


def insert_story(title: str, content: str, project_id: str) -> dict:
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "id": str(uuid.uuid4()),
        "title": title,
        "content": content,
        "projectId": project_id,
        "createdAt": now,
        "updatedAt": now,
    }
    result = db.table("Story").insert(payload).execute()
    return result.data[0]


def generate_and_sync_story(
    project_title: str,
    project_description: str,
    user_age: int,
    user_level: str,
    project_id: str,
) -> dict:
    story_data = generate_story(
        project_title, project_description, user_age, user_level
    )
    return insert_story(story_data["title"], story_data["content"], project_id)
