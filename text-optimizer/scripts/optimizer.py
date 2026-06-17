"""
Text Optimizer — AI-powered semantic text splitting, unified text optimization,
and prompt generation for image/video.

Single code path: the full text + all requirements are sent to the AI in ONE
prompt.  The model sees the whole picture and returns finished segments in a
single response.
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
    # Quick length guard: anything longer than max plausible filename is raw text
    if "\n" in source or len(source) > 255:
        return source

    path = Path(source)
    try:
        if path.exists() and path.is_file() and path.suffix.lower() in (".md", ".txt"):
            logger.info("Reading input from file: %s", path)
            return path.read_text(encoding="utf-8")
    except OSError:
        pass  # e.g. file name too long — treat as raw text

    return source


def split_text(
    text: str,
    num_segments: Optional[int] = None,
    extra_requirements: str = "",
) -> list[dict]:
    """Split *text* into semantically coherent segments via AI.

    The full text and all requirements are sent to the AI in ONE prompt.
    No word/character length limits are applied — the AI splits at natural
    semantic boundaries.

    Parameters
    ----------
    text : str
        The full text to split.
    num_segments : int or None
        Target segment count.  When ``None`` the AI decides.
    extra_requirements : str
        Additional requirements appended to the AI prompt (e.g.
        "use simple language for children").  Can be empty.

    Returns
    -------
    list[dict]
        Each dict has ``index``, ``title``, ``text``.
    """
    text = text.strip()
    if not text:
        return []

    if not TEXT_API_KEY:
        raise RuntimeError(
            "TEXT_API_KEY is not set. "
            "Set it in skills/.env or as an environment variable."
        )

    return _ai_split(text, num_segments, extra_requirements)


# ---------------------------------------------------------------------------
# Prompt generation — one AI call transforms all segments into image/video
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
}

ALL_PROMPT_TYPES = frozenset(_PROMPT_TYPE_SPECS.keys())  # {"image", "video"}


def _build_prompts_template(types: frozenset[str]) -> str:
    """Build the AI prompt template for the requested prompt *types*."""
    sections = []
    return_keys = []
    for t in sorted(types):  # deterministic order: image, video
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
    """Generate image/video prompts for each segment via AI.

    All segments are sent to the AI in ONE call.  The AI receives the full
    context and returns the requested prompt types for every segment, each
    following strict format requirements for its medium.

    Parameters
    ----------
    segments : list[dict]
        Segments from :func:`split_text` or :func:`optimize_text`.  Each must
        have ``index``, ``title``, and ``text``.
    types : frozenset[str]
        Which prompt types to generate.  Any subset of
        ``{"image", "video"}``.  Default: both.

    Returns
    -------
    list[dict]
        The same segments with the requested prompt keys added (``image_prompt``
        and/or ``video_prompt``).
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
            "text": seg.get("text", ""),
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

    # Unwrap wrapper object if the AI returns one (e.g. {"segments": [...]})
    if isinstance(prompts_list, dict):
        # Try "segments" key first
        if "segments" in prompts_list:
            prompts_list = prompts_list["segments"]
        # Try numeric-index dict: {"0": {...}, "1": {...}} → list
        elif all(str(k).isdigit() for k in prompts_list.keys()):
            prompts_list = [
                v for _, v in sorted(
                    prompts_list.items(), key=lambda x: int(x[0])
                )
            ]
        # Try any key whose value is a list
        else:
            for key, val in prompts_list.items():
                if isinstance(val, list):
                    prompts_list = val
                    break
            else:
                # No list value found — wrap the dict itself
                prompts_list = [prompts_list]
    if not isinstance(prompts_list, list):
        raise RuntimeError(
            f"Expected JSON array, got {type(prompts_list).__name__}"
            f" with keys: {list(prompts_list.keys()) if isinstance(prompts_list, dict) else 'N/A'}"
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


# ---------------------------------------------------------------------------
# Unified text optimization — replaces old genprompt + multiprompt
# ---------------------------------------------------------------------------

# Valid output fields for the optimize command
VALID_OPTIMIZE_FIELDS = frozenset({"text", "image_prompt", "video_prompt"})
DEFAULT_OPTIMIZE_FIELDS = frozenset({"text"})

# Text transformation directions
_OPTIMIZE_DIRECTION_SPECS: dict[str, str] = {
    "auto": (
        "Analyze the text length and complexity. If the text is long and "
        "detailed, summarize it into concise, polished content suitable for "
        "publishing. If the text is short, expand it with richer detail while "
        "preserving the core message. For medium-length text, refine it for "
        "readability and flow. NEVER introduce fictional facts."
    ),
    "summarize": (
        "Summarize the source text into concise, polished segments. Remove "
        "redundancy and filler, but preserve ALL key facts, the core message, "
        "tone, and writing style. NEVER introduce new information."
    ),
    "expand": (
        "Expand the source text with richer detail, vivid description, and "
        "natural elaboration. Preserve the core message while making the "
        "content more engaging and substantive. NEVER introduce fictional facts."
    ),
    "refine": (
        "Refine the source text for readability, flow, and polish. Fix awkward "
        "phrasing, improve transitions, and enhance clarity. Preserve length, "
        "all key facts, and the original message."
    ),
}

# Text optimization field spec (for when "text" is in the fields set)
_TEXT_FIELD_SPEC = {
    "key": "text",
    "header": "## Optimized Text (text)",
    "body": """Create polished, publication-ready text content.
STRICT format:
- Same language as the source text
- Self-contained and readable on its own
- Preserve all key facts, the core message, tone, and writing style
- NEVER introduce fictional facts or new information
""",
}


def _parse_fields(raw: str) -> frozenset[str]:
    """Parse comma-separated field names into a validated frozenset.

    ``""`` or ``"all"`` → ``{"text", "image_prompt", "video_prompt"}``.
    ``"text,image_prompt"`` → ``{"text", "image_prompt"}``.
    """
    if not raw or not raw.strip():
        return DEFAULT_OPTIMIZE_FIELDS
    raw = raw.strip()
    if raw == "all":
        return VALID_OPTIMIZE_FIELDS
    selected = {f.strip() for f in raw.split(",") if f.strip()}
    invalid = selected - VALID_OPTIMIZE_FIELDS
    if invalid:
        raise ValueError(
            f"Unknown fields: {sorted(invalid)}. "
            f"Valid: {sorted(VALID_OPTIMIZE_FIELDS)}"
        )
    if not selected:
        return DEFAULT_OPTIMIZE_FIELDS
    return frozenset(selected)


def _build_optimize_prompt(
    text: str,
    num_segments: int,
    fields: frozenset[str],
    direction: str,
    extra_requirements: str,
) -> str:
    """Dynamically build the AI prompt for :func:`optimize_text`.

    The prompt includes only the sections relevant to the requested *fields*,
    keeping the context tight and focused.
    """
    parts: list[str] = []

    # ── Header ────────────────────────────────────────────────────────
    parts.append(
        "You are a professional creative content producer. Process the "
        "source text according to ALL requirements below."
    )

    # ── Text transformation rule ───────────────────────────────────────
    if "text" in fields:
        direction_rule = _OPTIMIZE_DIRECTION_SPECS.get(
            direction, _OPTIMIZE_DIRECTION_SPECS["auto"]
        )
        parts.append(f"## Text transformation\n{direction_rule}")

    # ── Segments rule ──────────────────────────────────────────────────
    if num_segments == 1:
        parts.append(
            "## Segments to produce\n"
            "Produce exactly 1 segment from the source text."
        )
    else:
        parts.append(
            f"## Segments to produce\n"
            f"Produce exactly {num_segments} DIFFERENT segments. Each must "
            f"approach the content from a UNIQUE angle — vary the focus, "
            f"perspective, or creative treatment. No two segments should be "
            f"similar. When working with long text, split at natural topic "
            f"boundaries. For short text, create genuinely distinct variations."
        )

    # ── Field-specific sections ────────────────────────────────────────
    # "text" field
    if "text" in fields:
        parts.append(_TEXT_FIELD_SPEC["header"])
        parts.append(_TEXT_FIELD_SPEC["body"])

    # image_prompt field
    if "image_prompt" in fields:
        parts.append(_PROMPT_TYPE_SPECS["image"]["header"])
        parts.append(_PROMPT_TYPE_SPECS["image"]["body"])

    # video_prompt field
    if "video_prompt" in fields:
        parts.append(_PROMPT_TYPE_SPECS["video"]["header"])
        parts.append(_PROMPT_TYPE_SPECS["video"]["body"])

    # ── Output format ──────────────────────────────────────────────────
    required_keys = ["title"]
    for f in sorted(fields):
        required_keys.append(f)

    keys_str = "\n".join(f'- "{k}"' for k in required_keys)

    parts.append(
        f"## Output format\n\n"
        f"Return ONLY a valid JSON array of {num_segments} object(s). "
        f"Each object must have these keys:\n"
        f"{keys_str}\n\n"
        f"No markdown fences, no other text, no explanations."
    )

    # ── Extra requirements ─────────────────────────────────────────────
    if extra_requirements.strip():
        parts.append(f"## Additional requirements\n{extra_requirements.strip()}")

    # ── Source text ────────────────────────────────────────────────────
    parts.append(f"## Source text to process\n\n{text}")

    return "\n\n".join(parts)


def optimize_text(
    text: str,
    num_segments: int = 1,
    fields: frozenset[str] = DEFAULT_OPTIMIZE_FIELDS,
    direction: str = "auto",
    extra_requirements: str = "",
) -> list[dict]:
    """Unified text optimization and prompt generation via AI.

    Replaces the old ``genprompt`` and ``multiprompt`` commands.  Sends the
    full text + all requested output fields to the AI in ONE prompt.

    Parameters
    ----------
    text : str
        Source text to transform (raw string or file content).
    num_segments : int
        Number of segments to produce.  ``1`` = single output (old genprompt
        behavior), ``> 1`` = multiple versions (old multiprompt behavior).
        Must be >= 1.
    fields : frozenset[str]
        Which output fields to generate.  Any subset of
        ``{"text", "image_prompt", "video_prompt"}``.
        Default: ``{"text"}``.
    direction : str
        How to transform the text when ``"text"`` is in *fields*:
        ``"auto"`` (AI decides), ``"summarize"``, ``"expand"``, ``"refine"``.
    extra_requirements : str
        Additional instructions appended to the AI prompt (e.g.
        "use simple language for children aged 8-10").  Can be empty.

    Returns
    -------
    list[dict]
        Segments with ``index``, ``title``, and the requested field keys.
    """
    text = text.strip()
    if not text:
        return []

    if num_segments < 1:
        raise ValueError("num_segments must be at least 1")

    # Validate fields
    invalid = fields - VALID_OPTIMIZE_FIELDS
    if invalid:
        raise ValueError(
            f"Unknown fields: {sorted(invalid)}. "
            f"Valid: {sorted(VALID_OPTIMIZE_FIELDS)}"
        )

    if direction not in _OPTIMIZE_DIRECTION_SPECS:
        raise ValueError(
            f"Unknown direction '{direction}'. "
            f"Valid: {sorted(_OPTIMIZE_DIRECTION_SPECS.keys())}"
        )

    if not TEXT_API_KEY:
        raise RuntimeError(
            "TEXT_API_KEY is not set. "
            "Set it in skills/.env or as an environment variable."
        )

    prompt = _build_optimize_prompt(
        text=text,
        num_segments=num_segments,
        fields=fields,
        direction=direction,
        extra_requirements=extra_requirements,
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
                            "Return ONLY valid JSON — no markdown fences, "
                            "no explanations, no other text."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 8192,
            },
            timeout=300,
        )
        resp.raise_for_status()
        body = resp.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"Optimize API call failed: {exc}") from exc

    raw = body["choices"][0]["message"]["content"].strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: try concatenated objects
        items = []
        decoder = json.JSONDecoder()
        pos = 0
        while pos < len(raw):
            while pos < len(raw) and raw[pos] in " \t\n\r":
                pos += 1
            if pos >= len(raw):
                break
            try:
                obj, end = decoder.raw_decode(raw, pos)
                items.append(obj)
                pos = end
            except json.JSONDecodeError:
                break
        if not items:
            raise RuntimeError(
                f"AI returned non-JSON response for optimize. "
                f"Raw: {raw[:300]}..."
            )

    # Unwrap {"segments": [...]} wrapper if the AI returns it
    if isinstance(items, dict) and "segments" in items:
        items = items["segments"]
    if not isinstance(items, list):
        items = [items]

    # ── Assemble segments ────────────────────────────────────────────
    segments = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            item = {"title": f"Version {idx + 1}", "text": str(item)}

        seg = {
            "index": idx,
            "title": item.get("title", f"Version {idx + 1}").strip(),
        }

        # Include only the requested fields
        if "text" in fields:
            seg["text"] = item.get("text", "").strip() if isinstance(item.get("text"), str) else ""
        if "image_prompt" in fields:
            seg["image_prompt"] = item.get("image_prompt", "").strip() if isinstance(item.get("image_prompt"), str) else ""
        if "video_prompt" in fields:
            seg["video_prompt"] = item.get("video_prompt", "").strip() if isinstance(item.get("video_prompt"), str) else ""

        segments.append(seg)

    # Trim or pad to exact count
    if len(segments) > num_segments:
        segments = segments[:num_segments]
    elif len(segments) < num_segments:
        logger.warning(
            "AI returned %d segments, expected %d — padding with placeholders",
            len(segments), num_segments,
        )
        while len(segments) < num_segments:
            seg = {"index": len(segments), "title": f"Version {len(segments) + 1}"}
            for f in fields:
                seg[f] = ""
            segments.append(seg)

    logger.info(
        "Optimized %d segment(s) with fields: %s (%d total chars)",
        len(segments), sorted(fields),
        sum(len(str(s.get(f, ""))) for s in segments for f in fields),
    )
    return segments


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_output(segments: list[dict]) -> str:
    """Render segments as JSON (the only output format)."""
    return json.dumps(
        {"total_segments": len(segments), "segments": segments},
        ensure_ascii=False, indent=2,
    )


# ---------------------------------------------------------------------------
# AI split — ONE prompt, everything in one shot
# ---------------------------------------------------------------------------

_AI_SPLIT_PROMPT = """You are a professional content editor. Process the following text according to ALL of these requirements:

## Splitting
{segments_rule}

## Quality rules
- Split ONLY at natural semantic boundaries (topic shifts, section transitions).
- NEVER split mid-sentence.
- Each segment MUST be self-contained and readable on its own.
- When condensing: remove redundancy and filler first, merge related sentences,
  but preserve ALL key facts, the core message, tone, and writing style.
- NEVER introduce new information or opinions.
- Use the same language as the input text unless additional requirements specify otherwise.
- Give each segment a short, descriptive title (2-6 words, same language as input).
{extra_requirements_section}

Return ONLY a valid JSON array of objects with keys "title" and "text".
No other text, no markdown fences, no explanations.

## Text to process

{text}"""


def _ai_split(
    text: str,
    num_segments: Optional[int] = None,
    extra_requirements: str = "",
) -> list[dict]:
    """Send everything to the AI in one prompt — split only, no condensing."""

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

    # ── Extra requirements ────────────────────────────────────────────
    extra_section = ""
    if extra_requirements.strip():
        extra_section = f"\n## Additional requirements\n{extra_requirements.strip()}"

    # ── Call API (with retry if segment count mismatches) ────────────
    base_prompt = _AI_SPLIT_PROMPT.format(
        segments_rule=segments_rule,
        extra_requirements_section=extra_section,
        text=text,
    )

    max_attempts = 3
    segments: list[dict] = []
    current_prompt = base_prompt
    for attempt in range(1, max_attempts + 1):
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
                        {"role": "user", "content": current_prompt},
                    ],
                    "temperature": 0.3 if attempt == 1 else 0.1,
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
        except json.JSONDecodeError:
            # Model sometimes returns comma-separated objects
            # without enclosing brackets; try wrapping them
            try:
                items = json.loads("[" + raw + "]")
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"AI returned non-JSON response. Raw: {raw[:300]}..."
                ) from exc

        # Unwrap {"segments": [...]} wrapper if the AI returns it
        if isinstance(items, dict) and "segments" in items:
            items = items["segments"]
        if not isinstance(items, list):
            items = [items]

        # ── Assemble segments ────────────────────────────────────────
        segments = []
        for idx, item in enumerate(items):
            seg_text = item.get("text", "") if isinstance(item, dict) else str(item)
            title = item.get("title", "") if isinstance(item, dict) else ""
            seg = _make_segment(idx, seg_text.strip())
            if title:
                seg["title"] = title.strip()
            segments.append(seg)

        # Check if count matches (only when user specified a target)
        if num_segments and len(segments) != num_segments and attempt < max_attempts:
            logger.warning(
                "AI returned %d segments, expected %d — retrying (attempt %d/%d)...",
                len(segments), num_segments, attempt, max_attempts,
            )
            # Strengthen the prompt on retry
            current_prompt = (
                f"IMPORTANT: You MUST produce EXACTLY {num_segments} segments. "
                f"Do NOT return fewer or more. This is a hard requirement.\n\n"
            ) + base_prompt
            continue

        break

    if num_segments and len(segments) != num_segments:
        logger.warning(
            "AI returned %d segments after %d attempt(s), expected %d — "
            "returning available segments",
            len(segments), attempt, num_segments,
        )

    return segments


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_segment(index: int, text: str) -> dict:
    return {
        "index": index,
        "title": "",
        "text": text,
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
