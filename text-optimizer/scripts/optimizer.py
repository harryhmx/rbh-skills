"""
Text Optimizer — semantic text splitting powered by AI.

Single code path: the full text + all requirements (segment count, word/char
limits) are sent to the AI in ONE prompt.  The model sees the whole picture
and returns finished segments in a single response.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv(
    Path(__file__).resolve().parents[2] / ".env"  # skills root .env
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TEXT_API_KEY = os.environ.get("TEXT_API_KEY", "")
TEXT_BASE_URL = os.environ.get("TEXT_BASE_URL", "https://apihub.agnes-ai.com")
TEXT_CHAT_MODEL = os.environ.get("TEXT_CHAT_MODEL", "agnes-2.0-flash")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_input(source: str) -> str:
    """Return *source* unchanged unless it is a readable file path.

    Heuristic: if *source* contains a newline we treat it as raw text
    (a file path is extremely unlikely to contain one).  Otherwise we
    check whether the string points to an existing ``.md`` or ``.txt``
    file.
    """
    if "\n" in source:
        return source

    path = Path(source)
    if path.exists() and path.is_file() and path.suffix.lower() in (".md", ".txt"):
        logger.info("Reading input from file: %s", path)
        return path.read_text(encoding="utf-8")

    return source


def split_text(
    text: str,
    num_segments: Optional[int] = None,
    max_words: Optional[int] = None,
    max_chars: Optional[int] = None,
) -> list[dict]:
    """Split *text* into semantically coherent segments via AI.

    The full text and all requirements are sent to the AI in ONE prompt.

    Parameters
    ----------
    text : str
        The full text to split.
    num_segments : int or None
        Target segment count.  When ``None`` the AI decides.
    max_words : int or None
        Maximum words per segment — AI condenses if needed.
    max_chars : int or None
        Maximum characters per segment.  When both are set the stricter
        limit applies.

    Returns
    -------
    list[dict]
        Each dict has ``index``, ``title``, ``text``, ``word_count``,
        ``char_count``.
    """
    text = text.strip()
    if not text:
        return []

    if not TEXT_API_KEY:
        raise RuntimeError(
            "TEXT_API_KEY is not set. "
            "Set it in skills/.env or as an environment variable."
        )

    return _ai_split(text, num_segments, max_words, max_chars)


# ---------------------------------------------------------------------------
# Prompt generation — one AI call transforms all segments into image/video/TTS
# prompts with strict format requirements for each medium.
# ---------------------------------------------------------------------------

# Prompt type definitions — each entry maps a key name to its section header
# and detailed format specification.  The AI prompt is built dynamically so
# users can request only the types they need.
_PROMPT_TYPE_SPECS: dict[str, dict[str, str]] = {
    "image": {
        "key": "image_prompt",
        "header": "## Image Generation Prompt (image_prompt)",
        "body": """Create a detailed visual description suitable for AI image generation.
STRICT format:
- 2-4 sentences in English describing the scene VISUALLY
- Must include: main subjects, setting/background, key actions, facial expressions
- Must include: composition framing (close-up / wide shot / etc.), lighting direction and quality, dominant color palette (3-5 colors)
- You may optionally specify an art style that matches the content (e.g. photorealistic, oil painting, editorial illustration, 3D render)
- Focus ONLY on what can be drawn/illustrated — no abstract concepts, no text
- Example: "A wide shot of a modern office conference room with professionals seated around a long table, engaged in discussion. Editorial illustration style with natural lighting from floor-to-ceiling windows on the left. Composition centers on the presenter standing at the head of the table. Dominant colors: navy blue, warm gray, cream white, and brushed steel."
""",
    },
    "video": {
        "key": "video_prompt",
        "header": "## Video Generation Prompt (video_prompt)",
        "body": """Create a short video scene description suitable for AI video generation (Runway, Pika, Sora).
STRICT format:
- 2-4 sentences in English describing the visual scene WITH motion and action
- Must include: what HAPPENS visually over time (people move, objects change, scenes transform)
- Must specify: one primary camera movement (slow pan right / gentle zoom in / tracking shot following subject / static with internal motion)
- Must describe: pacing (slow and gentle / energetic and quick) and any transition at the start/end (fade in from black / cut to next scene)
- Example: "Fade in from black to a wide shot of a modern conference room. The camera slowly pans right across attendees seated around a table, each nodding in turn as a point is made. A presenter at the front gestures toward a projected chart. Slow, professional pacing with natural atmosphere. Fade out as the discussion concludes."
""",
    },
    "tts": {
        "key": "tts_prompt",
        "header": "## TTS Prompt (tts_prompt)",
        "body": """Convert the segment text into natural spoken narration.
STRICT format:
- Must be in the SAME LANGUAGE as the original segment text
- Start with a voice direction in parentheses: (warm and gentle tone, moderate pace) or (excited and energetic, faster pace) or (calm and thoughtful, slower pace) — choose the tone that best matches the content
- The spoken text should sound NATURAL when read aloud — adjust written phrasing slightly for speech if needed (e.g., break long sentences, add natural pauses)
- Preserve ALL key information and the core message
- Example: "(warm and gentle tone, moderate pace) 人工智能正在改变教育的方方面面。从个性化学习路径到智能辅导系统，AI技术让每个学生都能获得量身定制的学习体验。"
""",
    },
}

ALL_PROMPT_TYPES = frozenset(_PROMPT_TYPE_SPECS.keys())  # {"image", "video", "tts"}


def _build_prompts_template(types: frozenset[str]) -> str:
    """Build the AI prompt template for the requested prompt *types*."""
    sections = []
    return_keys = []
    for t in sorted(types):  # deterministic order: image, tts, video
        spec = _PROMPT_TYPE_SPECS[t]
        sections.append(spec["header"])
        sections.append(spec["body"])
        return_keys.append(f'"{spec["key"]}"')

    type_list = ", ".join(sorted(types))
    keys_list = ", ".join(return_keys)

    header = (
        f"You are a professional creative content producer. Below are {{count}} "
        f"text segments. For EACH segment, generate {type_list} prompt(s) "
        f"following the STRICT format requirements below."
    )

    footer = (
        f"---\n\n"
        f"## Segments to process\n\n"
        f"{{segments_json}}\n\n"
        f"---\n\n"
        f"Return ONLY a valid JSON array of objects. Each object must have "
        f'keys "index" (matching the input), {keys_list}.\n'
        f"No other text, no markdown fences, no explanations."
    )

    return header + "\n\n" + "\n".join(sections) + "\n\n" + footer


def generate_prompts(
    segments: list[dict],
    types: frozenset[str] = ALL_PROMPT_TYPES,
) -> list[dict]:
    """Generate image/video/TTS prompts for each segment via AI.

    All segments are sent to the AI in ONE call.  The AI receives the full
    context and returns the requested prompt types for every segment, each
    following strict format requirements for its medium.

    Parameters
    ----------
    segments : list[dict]
        Segments from :func:`split_text`.  Each must have ``index``,
        ``title``, and ``text``.
    types : frozenset[str]
        Which prompt types to generate.  Any subset of
        ``{"image", "video", "tts"}``.  Default: all three.

    Returns
    -------
    list[dict]
        The same segments with the requested prompt keys added.
    """
    if not segments:
        return segments

    # Validate types
    invalid = types - ALL_PROMPT_TYPES
    if invalid:
        raise ValueError(
            f"Unknown prompt types: {sorted(invalid)}. "
            f"Valid types: {sorted(ALL_PROMPT_TYPES)}"
        )

    if not TEXT_API_KEY:
        raise RuntimeError(
            "TEXT_API_KEY is not set. "
            "Set it in skills/.env or as an environment variable."
        )

    # Build a compact representation of all segments for the AI
    segments_for_ai = []
    for seg in segments:
        segments_for_ai.append({
            "index": seg["index"],
            "title": seg.get("title", ""),
            "text": seg["text"],
        })

    template = _build_prompts_template(types)
    prompt = template.format(
        count=len(segments),
        segments_json=json.dumps(segments_for_ai, ensure_ascii=False, indent=2),
    )

    try:
        resp = requests.post(
            f"{TEXT_BASE_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {TEXT_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": TEXT_CHAT_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a professional creative content producer. "
                            "Return ONLY valid JSON — no markdown fences, no "
                            "explanations, no other text."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.5,
                "max_tokens": 8192,
            },
            timeout=300,
        )
        resp.raise_for_status()
        body = resp.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"Prompt generation API call failed: {exc}") from exc

    raw = body["choices"][0]["message"]["content"].strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    # Try standard JSON array first, then fall back to concatenated objects
    try:
        prompts_list = json.loads(raw)
    except json.JSONDecodeError:
        # Some models return concatenated JSON objects instead of an array
        prompts_list = []
        decoder = json.JSONDecoder()
        pos = 0
        raw_stripped = raw.strip()
        while pos < len(raw_stripped):
            while pos < len(raw_stripped) and raw_stripped[pos] in " \t\n\r":
                pos += 1
            if pos >= len(raw_stripped):
                break
            try:
                obj, end = decoder.raw_decode(raw_stripped, pos)
                prompts_list.append(obj)
                pos = end
            except json.JSONDecodeError:
                break
        if not prompts_list:
            raise RuntimeError(
                f"AI returned non-JSON response for prompts. Raw: {raw[:300]}..."
            )

    if not isinstance(prompts_list, list):
        raise RuntimeError(
            f"Expected JSON array, got {type(prompts_list).__name__}"
        )

    # Merge prompts back into segments by index
    prompt_map: dict[int, dict] = {}
    for item in prompts_list:
        idx = item.get("index", -1) if isinstance(item, dict) else -1
        prompt_map[idx] = item if isinstance(item, dict) else {}

    # Map type names to segment keys
    type_keys = {t: _PROMPT_TYPE_SPECS[t]["key"] for t in types}

    for seg in segments:
        pm = prompt_map.get(seg["index"], {})
        for t in ALL_PROMPT_TYPES:
            key = _PROMPT_TYPE_SPECS[t]["key"]
            if t in types:
                seg[key] = pm.get(key, "") or ""
            else:
                # Remove any stale key from a previous call
                seg.pop(key, None)

    return segments


def format_output(segments: list[dict], fmt: str) -> str:
    """Render segments as *fmt* (``"json"``, ``"md"``, or ``"text"``)."""
    if fmt == "json":
        return json.dumps(
            {"total_segments": len(segments), "segments": segments},
            ensure_ascii=False, indent=2,
        )
    if fmt == "md":
        return _format_markdown(segments)
    return _format_plain(segments)


# ---------------------------------------------------------------------------
# AI split — ONE prompt, everything in one shot
# ---------------------------------------------------------------------------

_AI_SPLIT_PROMPT = """You are a professional content editor. Process the following text according to ALL of these requirements:

## Splitting
{segments_rule}

## Length limits
{length_rule}

## Quality rules
- Split ONLY at natural semantic boundaries (topic shifts, section transitions).
- NEVER split mid-sentence.
- Each segment MUST be self-contained and readable on its own.
- When condensing: remove redundancy and filler first, merge related sentences,
  but preserve ALL key facts, the core message, tone, and writing style.
- NEVER introduce new information or opinions.
- Keep the same language as the input text.
- Give each segment a short, descriptive title (2-6 words, same language as input).

Return ONLY a valid JSON array of objects with keys "title" and "text".
No other text, no markdown fences, no explanations.

## Text to process

{text}"""


def _ai_split(
    text: str,
    num_segments: Optional[int] = None,
    max_words: Optional[int] = None,
    max_chars: Optional[int] = None,
) -> list[dict]:
    """Send everything to the AI in one prompt — split + condense."""

    # ── Segments rule ────────────────────────────────────────────────
    if num_segments:
        segments_rule = f"Split the text into EXACTLY {num_segments} segments."
    else:
        wc = _count_words(text)
        auto = max(2, min(10, wc // 200))
        segments_rule = (
            f"Determine the optimal number of segments (recommend around "
            f"{auto} for this {wc}-word article, use your judgment)."
        )

    # ── Length rule ──────────────────────────────────────────────────
    if max_words and max_chars:
        length_rule = (
            f"Each segment MUST be ≤ {max_words} words AND ≤ {max_chars} "
            "characters. Condense any segment that exceeds either limit. "
            "When condensing: remove redundancy and filler first, merge "
            "related sentences, preserve key facts, core message, and tone."
        )
    elif max_words:
        length_rule = (
            f"Each segment MUST be ≤ {max_words} words. "
            "Condense any segment that exceeds this limit. "
            "When condensing: remove redundancy and filler first, merge "
            "related sentences, preserve key facts, core message, and tone."
        )
    elif max_chars:
        length_rule = (
            f"Each segment MUST be ≤ {max_chars} characters. "
            "Condense any segment that exceeds this limit. "
            "When condensing: remove redundancy and filler first, merge "
            "related sentences, preserve key facts, core message, and tone."
        )
    else:
        length_rule = "No length limit — keep segments at their natural size."

    # ── Call API ─────────────────────────────────────────────────────
    prompt = _AI_SPLIT_PROMPT.format(
        segments_rule=segments_rule,
        length_rule=length_rule,
        text=text,
    )

    try:
        resp = requests.post(
            f"{TEXT_BASE_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {TEXT_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": TEXT_CHAT_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a precise content editor. Return ONLY valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 8192,
            },
            timeout=120,
        )
        resp.raise_for_status()
        body = resp.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"AI API call failed: {exc}") from exc

    raw = body["choices"][0]["message"]["content"].strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        items = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"AI returned non-JSON response. Raw: {raw[:300]}..."
        ) from exc

    if not isinstance(items, list):
        items = [items]

    # ── Assemble segments ────────────────────────────────────────────
    segments = []
    for idx, item in enumerate(items):
        seg_text = item.get("text", "") if isinstance(item, dict) else str(item)
        title = item.get("title", "") if isinstance(item, dict) else ""
        seg = _make_segment(idx, seg_text.strip())
        if title:
            seg["title"] = title.strip()
        segments.append(seg)

    return segments


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_segment(index: int, text: str) -> dict:
    return {
        "index": index,
        "title": "",
        "text": text,
        "word_count": _count_words(text),
        "char_count": len(text),
    }


def _count_words(text: str) -> int:
    """Count "words" in mixed CJK / Latin text.

    CJK characters are counted individually (each character ≈ 1 word),
    Latin script words are counted by whitespace splitting.
    """
    cjk = 0
    latin_parts: list[str] = []
    buf = ""
    in_cjk = False
    for ch in text:
        if "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿":
            if not in_cjk:
                if buf:
                    latin_parts.append(buf)
                    buf = ""
                in_cjk = True
            cjk += 1
        else:
            if in_cjk:
                in_cjk = False
            buf += ch
    if buf:
        latin_parts.append(buf)

    latin_words = sum(len(part.split()) for part in latin_parts)
    return cjk + latin_words


def _format_markdown(segments: list[dict]) -> str:
    lines = [
        "# Text Split Result",
        f"**Segments:** {len(segments)}",
        "",
    ]
    for seg in segments:
        title = seg.get("title") or f"Segment {seg['index'] + 1}"
        lines.append("---")
        lines.append("")
        lines.append(f"## {title}")
        lines.append(
            f"**Words:** {seg['word_count']}  |  **Chars:** {seg['char_count']}"
        )
        lines.append("")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


def _format_plain(segments: list[dict]) -> str:
    lines = []
    for seg in segments:
        title = seg.get("title") or f"Segment {seg['index'] + 1}"
        lines.append(
            f"【{title}】({seg['word_count']} words / {seg['char_count']} chars)"
        )
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)
