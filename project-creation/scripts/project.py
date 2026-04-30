import json
import logging
from datetime import datetime, timezone
import uuid

from common.db import get_db
from config import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a project title and description generator.
Given a topic or idea, generate a concise project title (max 100 characters) and a detailed description (100-200 words, markdown format).
Return ONLY a valid JSON object with exactly two keys: "title" and "description".
No markdown, no extra text, no code fences."""


def generate_project(prompt: str) -> dict:
    client = OpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
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
    return {"title": data["title"], "description": data.get("description")}


def insert_project(title: str, description: str | None = None) -> dict:
    db = get_db()
    payload = {"id": str(uuid.uuid4()), "title": title}
    if description:
        payload["description"] = description
    now = datetime.now(timezone.utc).isoformat()
    payload["createdAt"] = now
    payload["updatedAt"] = now
    result = db.table("Project").insert(payload).execute()
    return result.data[0]


def generate_and_sync_project(prompt: str) -> dict:
    project_data = generate_project(prompt)
    return insert_project(project_data["title"], project_data.get("description"))
