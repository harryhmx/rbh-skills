"""
Project generation via LLM and Supabase sync.

Migrated from project-creation/scripts/project.py.
Functions maintain identical signatures for future API compatibility.
"""

import json
import logging
import uuid
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

from common.db import get_db
from config import settings
from openai import OpenAI

# Dynamically import decorators and session modules
_decorators_spec = importlib.util.spec_from_file_location(
    "rbh_core_decorators_project", Path(__file__).parent / "decorators.py"
)
_decorators_mod = importlib.util.module_from_spec(_decorators_spec)
_decorators_spec.loader.exec_module(_decorators_mod)
require_auth = _decorators_mod.require_auth

_session_spec = importlib.util.spec_from_file_location(
    "rbh_core_session_project", Path(__file__).parent / "session.py"
)
_session_mod = importlib.util.module_from_spec(_session_spec)
_session_spec.loader.exec_module(_session_mod)
get_current_user = _session_mod.get_current_user

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a project title and description generator.
Given a topic or idea, generate a concise project title (max 100 characters) and a brief description (100-200 characters).
Return ONLY a valid JSON object with exactly two keys: "title" and "description".
No markdown, no extra text, no code fences."""


def generate_project(prompt: str) -> dict:
    """Generate Project title and description via LLM.

    Args:
        prompt: User's topic or idea

    Returns:
        {"title": str, "description": str}
    """
    client = OpenAI(
        api_key=settings.TEXT_API_KEY,
        base_url=f"{settings.TEXT_BASE_URL}/v1",
    )
    response = client.chat.completions.create(
        model=settings.TEXT_CHAT_MODEL,
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
    """Insert Project into Supabase database.

    Args:
        title: Project title
        description: Optional description

    Returns:
        Inserted Project record (dict)
    """
    db = get_db()
    payload = {"id": str(uuid.uuid4()), "title": title}
    if description:
        payload["description"] = description
    now = datetime.now(timezone.utc).isoformat()
    payload["createdAt"] = now
    payload["updatedAt"] = now
    result = db.table("Project").insert(payload).execute()
    return result.data[0]


@require_auth
def generate_and_sync_project(prompt: str) -> dict:
    """Generate Project via LLM and sync to database.

    Requires authentication.

    Args:
        prompt: User's topic or idea

    Returns:
        Inserted Project record (dict)
    """
    user = get_current_user()
    logger.info(f"Generating project for user: {user['username']}")

    project_data = generate_project(prompt)
    return insert_project(project_data["title"], project_data.get("description"))
