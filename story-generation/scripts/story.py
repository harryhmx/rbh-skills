import json
import logging
import uuid
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from common.db import get_db
from config import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

_SCRIPTS_DIR = Path(__file__).parent


def _load_module(name: str, filename: str):
    spec = spec_from_file_location(name, _SCRIPTS_DIR / filename)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_image_mod = None
_speech_mod = None


def _get_image_module():
    global _image_mod
    if _image_mod is None:
        _image_mod = _load_module("image_gen", "image.py")
    return _image_mod


def _get_speech_module():
    global _speech_mod
    if _speech_mod is None:
        _speech_mod = _load_module("speech_gen", "speech.py")
    return _speech_mod


_SYSTEM_PROMPT = """You are a children's story and question generator.
Given a project's title and description, along with the reader's age and Lexile Level, generate a short story chapter with two questions.

Requirements:
- The story should match the reader's maturity level (based on his or her age) and English reading level (based on his or her Lexile level).
- The content must be written in markdown format (can include headings, bold text, etc.).
- The story body MUST be concise and engaging (60-100 words).
- Write the story in English, in the style of Roald Dahl, and in the structure of a fable, in the style of Aesop's Fables.

Generate two questions at the end of the story:

**RC Question (Reading Comprehension):**
- 4 options: A, B, C, D
- Tests reading comprehension and vocabulary from the story
- Must have one clearly correct answer

**CT Question (Critical Thinking):**
- 2 options: A, B
- Tests higher-level thinking (critical thinking, logical reasoning, creativity, wisdom)
- Make the choice challenging - one that forces the reader to think, one where there is no clear right or wrong answer, but rather, one that simply reveals the character and preferences of the reader
- Asks the student to decide the protagonist's action, which then shapes how the story continues in the following chapter (this is the MOST IMPORTANT part of the story)

Return ONLY a valid JSON object with exactly five keys: "title", "content", "rcQuestion", "rcAnswer", "ctQuestion".
- "title": a concise story title (max 100 characters)
- "content": the story body in markdown format. Do NOT repeat the title in the content. Start directly with the story narrative.
- "rcQuestion": the RC question text followed by EXACTLY TWO blank lines then "..." then EXACTLY TWO blank lines then the 4 choices, one per line, each formatted as "letter|letter) option text". CRITICAL FORMAT: "What did the hero find?\\n\\n...\\n\\na|a) A map\\nb|b) A key\\nc|c) A ring\\nd|d) A coin". There MUST be exactly two newlines before "..." and exactly two newlines after "...". Do NOT use a single newline.
- "rcAnswer": the correct answer letter only, e.g. "b"
- "ctQuestion": the CT question text followed by EXACTLY TWO blank lines then "..." then EXACTLY TWO blank lines then 2 choices. CRITICAL FORMAT: "What should the hero do?\\n\\n...\\n\\na|a) Go home\\nb|b) Keep exploring". Same two-newline rule applies.

No markdown, no extra text, no code fences."""

_CONCLUSION_PROMPT = """You are a children's story generator.
Given a project's title and description, along with the reader's age and Lexile Level, generate a short story chapter that serves as the conclusion of a story arc.

Requirements:
- The story should match the reader's maturity level (based on his or her age) and English reading level (based on his or her Lexile level).
- The content must be written in markdown format (can include headings, bold text, etc.).
- The story body MUST be concise and engaging (60-100 words).
- Write the story in English, in the style of Roald Dahl, and in the structure of a fable, in the style of Aesop's Fables.
- This is the FINAL chapter of a story arc — wrap up the narrative naturally with a sense of closure and a gentle moral.
- Do NOT generate any questions. This chapter has no questions.

Return ONLY a valid JSON object with exactly two keys: "title" and "content".
- "title": a concise story title (max 100 characters)
- "content": the story body in markdown format. Do NOT repeat the title in the content. Start directly with the story narrative.

No markdown, no extra text, no code fences."""


def find_story(
    project_id: str,
    user_age: int,
    user_level: str,
    require_story_id: str | None = None,
    require_choice: str | None = None,
) -> dict | None:
    db = get_db()
    query = (
        db.table("Story")
        .select("*")
        .eq("projectId", project_id)
        .eq("age", user_age)
        .eq("level", user_level)
    )
    if require_story_id:
        query = query.eq("requireStoryId", require_story_id)
    if require_choice:
        query = query.eq("requireChoice", require_choice)
    result = query.limit(1).execute()
    if result.data:
        return result.data[0]
    return None


def generate_story(
    project_title: str,
    project_description: str,
    user_age: int,
    user_level: str,
    parent_story_title: str | None = None,
    parent_choice: str | None = None,
    parent_story_content: str | None = None,
    is_conclusion: bool = False,
) -> dict:
    client = OpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        timeout=60.0,
    )
    prompt = (
        f"Project title: {project_title}\n"
        f"Project description: {project_description}\n"
        f"Reader age: {user_age}\n"
        f"Reader level: {user_level}"
    )
    if parent_story_content and parent_choice:
        prompt += (
            f"\n\nThis is a continuation. Here is the previous story:\n\n"
            f"Title: {parent_story_title}\n"
            f"{parent_story_content}\n\n"
            f"The reader chose: \"{parent_choice}\". "
            "Continue the story based on that choice. The new chapter should "
            "naturally follow from the previous story events and the reader's decision."
        )
    elif parent_story_title and parent_choice:
        prompt += (
            f"\n\nThis is a continuation. The previous story was titled '{parent_story_title}' "
            f"and the reader chose: \"{parent_choice}\". "
            "Continue the story based on that choice."
        )

    system_prompt = _CONCLUSION_PROMPT if is_conclusion else _SYSTEM_PROMPT
    required_fields = (["title", "content"] if is_conclusion
                       else ["title", "content", "rcQuestion", "rcAnswer", "ctQuestion"])

    for attempt in range(1, 4):
        try:
            logger.info("[story] Generating... (attempt %d/3, conclusion=%s)", attempt, is_conclusion)
            response = client.chat.completions.create(
                model=settings.LLM_CHAT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(raw)

            missing = [k for k in required_fields if not data.get(k)]
            if missing:
                logger.warning("[story] Missing fields: %s, retrying", missing)
                continue

            break
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("[story] Parse error (attempt %d): %s", attempt, e)
            continue
    else:
        logger.error("[story] All 3 attempts failed")
        raise RuntimeError("Failed to generate valid story after 3 attempts")
    return {
        "title": data["title"],
        "content": data["content"],
        "rcQuestion": data.get("rcQuestion"),
        "rcAnswer": data.get("rcAnswer"),
        "ctQuestion": data.get("ctQuestion"),
    }


def insert_story(
    title: str,
    content: str,
    project_id: str,
    user_age: int,
    user_level: str,
    image_url: str | None = None,
    audio_url: str | None = None,
    rc_question: str | None = None,
    rc_answer: str | None = None,
    ct_question: str | None = None,
    require_story_id: str | None = None,
    require_choice: str | None = None,
    depth: int = 0,
    story_id: str | None = None,
) -> dict:
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "id": story_id or str(uuid.uuid4()),
        "title": title,
        "content": content,
        "imageUrl": image_url,
        "audioUrl": audio_url,
        "rcQuestion": rc_question,
        "rcAnswer": rc_answer,
        "ctQuestion": ct_question,
        "age": user_age,
        "level": user_level,
        "projectId": project_id,
        "requireStoryId": require_story_id,
        "requireChoice": require_choice,
        "depth": depth,
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
    require_story_id: str | None = None,
    require_choice: str | None = None,
    depth: int = 0,
    parent_story_title: str | None = None,
    parent_story_content: str | None = None,
) -> dict:
    is_conclusion = (depth + 1) % 4 == 0
    story_data = generate_story(
        project_title,
        project_description,
        user_age,
        user_level,
        parent_story_title=parent_story_title,
        parent_choice=require_choice,
        parent_story_content=parent_story_content,
        is_conclusion=is_conclusion,
    )

    story_id = str(uuid.uuid4())

    # Generate image
    image_url = None
    try:
        image_url = _get_image_module().generate_image(
            story_data["title"], story_data["content"], story_id=story_id
        )
    except Exception as e:
        logger.warning("Image generation failed: %s", e)

    # Generate audio
    audio_url = None
    try:
        audio_url = _get_speech_module().generate_speech(
            story_data["title"], story_data["content"], story_id=story_id
        )
    except Exception as e:
        logger.warning("Speech generation failed: %s", e)

    return insert_story(
        title=story_data["title"],
        content=story_data["content"],
        project_id=project_id,
        user_age=user_age,
        user_level=user_level,
        image_url=image_url,
        audio_url=audio_url,
        rc_question=story_data.get("rcQuestion"),
        rc_answer=story_data.get("rcAnswer"),
        ct_question=story_data.get("ctQuestion"),
        require_story_id=require_story_id,
        require_choice=require_choice,
        depth=depth,
        story_id=story_id,
    )


def generate_and_insert_story(
    project_title: str,
    project_description: str,
    user_age: int,
    user_level: str,
    project_id: str,
    require_story_id: str | None = None,
    require_choice: str | None = None,
    depth: int = 0,
    parent_story_title: str | None = None,
    parent_story_content: str | None = None,
) -> dict:
    is_conclusion = (depth + 1) % 4 == 0
    story_data = generate_story(
        project_title,
        project_description,
        user_age,
        user_level,
        parent_story_title=parent_story_title,
        parent_choice=require_choice,
        parent_story_content=parent_story_content,
        is_conclusion=is_conclusion,
    )

    story_id = str(uuid.uuid4())
    return insert_story(
        title=story_data["title"],
        content=story_data["content"],
        project_id=project_id,
        user_age=user_age,
        user_level=user_level,
        rc_question=story_data.get("rcQuestion"),
        rc_answer=story_data.get("rcAnswer"),
        ct_question=story_data.get("ctQuestion"),
        require_story_id=require_story_id,
        require_choice=require_choice,
        depth=depth,
        story_id=story_id,
    )


def update_story_media(story_id: str, title: str, content: str):
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    update_fields = {"updatedAt": now}

    image_url = None
    try:
        image_url = _get_image_module().generate_image(
            title, content, story_id=story_id
        )
        if image_url:
            update_fields["imageUrl"] = image_url
            logger.info("[story-media] Image ready: %s", image_url)
            db.table("Story").update(update_fields).eq("id", story_id).execute()
    except Exception as e:
        logger.warning("[story-media] Image generation failed: %s", e)

    audio_url = None
    try:
        audio_url = _get_speech_module().generate_speech(
            title, content, story_id=story_id
        )
        if audio_url:
            update_fields["audioUrl"] = audio_url
            logger.info("[story-media] Audio ready: %s", audio_url)
            db.table("Story").update(update_fields).eq("id", story_id).execute()
    except Exception as e:
        logger.warning("[story-media] Speech generation failed: %s", e)


def get_story_by_id(story_id: str) -> dict | None:
    db = get_db()
    result = db.table("Story").select("id, imageUrl, audioUrl").eq("id", story_id).execute()
    if result.data:
        return result.data[0]
    return None
