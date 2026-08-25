"""
Shared configuration, utilities, and helpers for content-production modules.

All modules import their config constants and shared utilities from here.
The single ``load_dotenv`` call ensures the skills ``.env`` is read once.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import requests as http_requests
from dotenv import load_dotenv

load_dotenv(
    Path(__file__).resolve().parents[2] / ".env"  # skills root .env
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (from skills/.env)
# ---------------------------------------------------------------------------

# Provider selection — which backend serves each capability.
#   image:  "agnes" (default) | "gemini" | "openai"
#   video:  "agnes" (default) | "gemini"
#   speech: "siliconflow" (default) | "gemini"
IMAGE_PROVIDER = os.environ.get("IMAGE_PROVIDER", "openai").strip().lower()
VIDEO_PROVIDER = os.environ.get("VIDEO_PROVIDER", "agnes").strip().lower()
SPEECH_PROVIDER = os.environ.get("SPEECH_PROVIDER", "siliconflow").strip().lower()

# Generic image settings are retained for CLI compatibility. Provider-specific
# defaults below keep Content Production's Agnes image path isolated from the
# IMAGE_* settings used by Adventure Academy (currently SiliconFlow).
IMAGE_API_KEY = os.environ.get("IMAGE_API_KEY", "")
IMAGE_BASE_URL = os.environ.get("IMAGE_BASE_URL", "https://apihub.agnes-ai.com")
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "agnes-image-2.1-flash")
IMAGE_SIZE_DEFAULT = os.environ.get("IMAGE_SIZE", "1024x768")

# Agnes AI image generation (Content Production)
AGNES_API_KEY = os.environ.get("AGNES_API_KEY", "")
AGNES_IMAGE_BASE_URL = os.environ.get("AGNES_IMAGE_BASE_URL", "https://apihub.agnes-ai.com").rstrip("/")
AGNES_IMAGE_MODEL = os.environ.get("AGNES_IMAGE_MODEL", "agnes-image-2.1-flash")
AGNES_IMAGE_SIZE_DEFAULT = os.environ.get("AGNES_IMAGE_SIZE", "1024x768")

# OpenAI image generation
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_IMAGE_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2")
OPENAI_IMAGE_TRANSPORT = os.environ.get("OPENAI_IMAGE_TRANSPORT", "curl").strip().lower()
OPENAI_IMAGE_TIMEOUT = int(os.environ.get("OPENAI_IMAGE_TIMEOUT", "180"))

# Video (Agnes AI)
VIDEO_API_KEY = os.environ.get("VIDEO_API_KEY", "")
VIDEO_BASE_URL = os.environ.get("VIDEO_BASE_URL", "https://apihub.agnes-ai.com")
VIDEO_MODEL = os.environ.get("VIDEO_MODEL", "agnes-video-v2.0")
VIDEO_SIZE_DEFAULT = os.environ.get("VIDEO_SIZE", "1152x768")
VIDEO_NUM_FRAMES_DEFAULT = int(os.environ.get("VIDEO_NUM_FRAMES", "121"))
VIDEO_FRAME_RATE_DEFAULT = float(os.environ.get("VIDEO_FRAME_RATE", "24"))
VIDEO_POLL_TIMEOUT = int(os.environ.get("VIDEO_POLL_TIMEOUT", "900"))
VIDEO_POLL_INTERVAL = int(os.environ.get("VIDEO_POLL_INTERVAL", "10"))

# Speech (SiliconFlow)
SPEECH_API_KEY = os.environ.get("SPEECH_API_KEY", "")
SPEECH_BASE_URL = os.environ.get("SPEECH_BASE_URL", "https://api.siliconflow.com/v1")
SPEECH_MODEL = os.environ.get("SPEECH_MODEL", "fishaudio/fish-speech-1.5")
SPEECH_VOICE = os.environ.get("SPEECH_VOICE", "fishaudio/fish-speech-1.5:anna")

# Gemini (Google AI) — one API key shared by image / video / speech
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BASE_URL = os.environ.get(
    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
)
# Image: Nano Banana 2 (native Gemini image model; Imagen is deprecated)
GEMINI_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
GEMINI_IMAGE_SIZE = os.environ.get("GEMINI_IMAGE_SIZE", "1K")  # 1K / 2K / 4K
# Video: Veo 3.1 (long-running operations flow)
GEMINI_VIDEO_MODEL = os.environ.get("GEMINI_VIDEO_MODEL", "veo-3.1-generate-preview")
GEMINI_VIDEO_DURATION = int(os.environ.get("GEMINI_VIDEO_DURATION", "8"))  # 4 / 6 / 8 seconds
GEMINI_VIDEO_RESOLUTION = os.environ.get("GEMINI_VIDEO_RESOLUTION", "720p")  # 720p / 1080p / 4k
GEMINI_VIDEO_CONCURRENCY = int(os.environ.get("GEMINI_VIDEO_CONCURRENCY", "4"))  # max in-flight Veo operations
# Speech: Gemini TTS (PCM 24 kHz output, wrapped as WAV)
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.1-flash-tts-preview")
GEMINI_TTS_VOICE = os.environ.get("GEMINI_TTS_VOICE", "Kore")

MAX_RETRIES = 2
DOWNLOAD_RETRIES = 3          # retries for the download step only
DOWNLOAD_BACKOFF_BASE = 2.0   # seconds, multiplied by 2^(attempt-1)

# Image-to-image (i2i) limits
REFS_MAX_COUNT = 4            # max reference images per segment / --ref
REFS_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


# ---------------------------------------------------------------------------
# Public API — segments JSON loading
# ---------------------------------------------------------------------------

def build_filename(
    name: str | None,
    slug: str | None,
    index: int,
    extension: str,
) -> str:
    """Build a filename from optional top-level ``name`` and segment-level ``slug``.

    Rules
    -----
    * name + slug      -> ``{name}-{slug}{ext}``
    * name, no slug    -> ``{name}-{index:03d}{ext}``
    * no name, slug    -> ``{slug}{ext}``
    * no name, no slug -> ``{index:03d}{ext}``
    """
    if name:
        if slug:
            return f"{name}-{slug}{extension}"
        return f"{name}-{index:03d}{extension}"
    if slug:
        return f"{slug}{extension}"
    return f"{index:03d}{extension}"




def load_segments_json(path: str | Path, media_type: str = "image") -> tuple[list[dict], str | None]:
    """Read and validate a media-segments JSON file.

    The root may contain ``segments`` (required) and ``name`` (optional
    kebab-case string for filename prefixes).  Each segment may contain the
    known media fields plus an optional ``slug`` (kebab-case string for
    custom filenames).  *media_type* selects the required field for a command.

    Returns
    -------
    tuple[list[dict], str | None]
        Validated segments list and the optional top-level ``name`` value.
    """
    if media_type not in {"image", "video", "speech"}:
        raise ValueError(f"Unknown media type '{media_type}'")

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("top-level JSON value must be an object")
    allowed_top = {"segments", "name"}
    unknown = sorted(set(data) - allowed_top)
    if unknown:
        raise ValueError(f"unknown top-level field(s): {', '.join(unknown)}")

    if data.get("name") is not None:
        name_val = data["name"]
        if not isinstance(name_val, str) or not name_val.strip():
            raise ValueError("top-level 'name' must be a non-empty string")

    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("segments must be a non-empty array")

    allowed_fields = {"index", "title", "slug", "image_prompt", "image_refs", "video_prompt", "text"}
    required_field = {"image": "image_prompt", "video": "video_prompt", "speech": "text"}[media_type]
    for expected_index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise ValueError("each segment must be an object")
        unknown = sorted(set(segment) - allowed_fields)
        if unknown:
            raise ValueError(f"unknown segment field(s): {', '.join(unknown)}")
        if type(segment.get("index")) is not int or segment["index"] < 0:
            raise ValueError("segment index must be a non-negative integer")
        if segment["index"] != expected_index:
            raise ValueError("segment indexes must be contiguous and ordered from 0")
        if not isinstance(segment.get("title"), str) or not segment["title"].strip():
            raise ValueError("each segment requires a non-empty title")
        slug = segment.get("slug")
        if slug is not None and (not isinstance(slug, str) or not slug.strip()):
            raise ValueError("segment 'slug' must be a non-empty string when present")

        # Validate image_refs when present (i2i mode), then resolve to
        # absolute paths so downstream callers don't need the JSON dir.
        image_refs = segment.get("image_refs")
        if image_refs is not None:
            if not isinstance(image_refs, list):
                raise ValueError("segment 'image_refs' must be an array")
            if not image_refs:
                raise ValueError("segment 'image_refs' must be non-empty when present")
            if len(image_refs) > REFS_MAX_COUNT:
                raise ValueError(
                    f"segment 'image_refs' has {len(image_refs)} items, "
                    f"max {REFS_MAX_COUNT}"
                )
            json_dir = Path(path).resolve().parent
            resolved: list[str] = []
            for i, ref_path in enumerate(image_refs):
                if not isinstance(ref_path, str) or not ref_path.strip():
                    raise ValueError(
                        f"segment 'image_refs[{i}]' must be a non-empty string"
                    )
                full_path = (json_dir / ref_path).resolve()
                # Reject absolute paths and parent-dir escapes
                if ref_path.startswith("/") or ".." in Path(ref_path).parts:
                    raise ValueError(
                        f"segment 'image_refs[{i}]' must be a relative path "
                        f"inside the project directory, got: '{ref_path}'"
                    )
                if not full_path.is_file():
                    raise ValueError(
                        f"segment 'image_refs[{i}]' file not found: '{ref_path}' "
                        f"(resolved to '{full_path}')"
                    )
                ext = full_path.suffix.lower()
                if ext not in REFS_ALLOWED_EXTENSIONS:
                    raise ValueError(
                        f"segment 'image_refs[{i}]' unsupported extension "
                        f"'{ext}'; allowed: {', '.join(sorted(REFS_ALLOWED_EXTENSIONS))}"
                    )
                resolved.append(str(full_path))
            # Replace the relative paths with resolved absolute paths
            segment["image_refs"] = resolved

        if not isinstance(segment.get(required_field), str) or not segment[required_field].strip():
            raise ValueError(f"each segment requires a non-empty {required_field}")

    return segments, data.get("name")


def validate_image_refs(refs: list[str], base_dir: str | Path | None = None) -> list[Path]:
    """Validate and resolve CLI-provided ``--ref`` paths.

    Parameters
    ----------
    refs : list[str]
        List of paths to reference images (strings from CLI ``--ref``).
    base_dir : str, Path, or None
        Directory to resolve relative paths against.  When ``None``,
        resolves against the current working directory.

    Returns
    -------
    list[Path]
        Resolved absolute paths, all confirmed to exist.

    Raises
    ------
    ValueError
        If any path fails validation (count, existence, extension,
        absolute/escape).
    """
    if not refs:
        raise ValueError("refs must be non-empty when provided")
    if len(refs) > REFS_MAX_COUNT:
        raise ValueError(
            f"too many refs ({len(refs)}), max {REFS_MAX_COUNT}"
        )

    root = Path(base_dir).resolve() if base_dir else Path.cwd()
    resolved: list[Path] = []

    for i, ref_path in enumerate(refs):
        if not ref_path.strip():
            raise ValueError(f"ref[{i}] must be a non-empty path")

        # Reject absolute paths and escapes
        p = Path(ref_path)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError(
                f"ref[{i}] must be a relative path inside the project "
                f"directory, got: '{ref_path}'"
            )

        full = (root / p).resolve()
        if not full.is_file():
            raise ValueError(
                f"ref[{i}] file not found: '{ref_path}' "
                f"(resolved to '{full}')"
            )

        ext = full.suffix.lower()
        if ext not in REFS_ALLOWED_EXTENSIONS:
            raise ValueError(
                f"ref[{i}] unsupported extension '{ext}'; "
                f"allowed: {', '.join(sorted(REFS_ALLOWED_EXTENSIONS))}"
            )

        resolved.append(full)

    return resolved


# ---------------------------------------------------------------------------
# Download helper with retry
# ---------------------------------------------------------------------------


def download_with_retry(url: str, timeout: int = 60) -> bytes:
    """Download *url* with exponential-backoff retries on transient failures.

    Retries up to ``DOWNLOAD_RETRIES`` times, only for connection/timeout/SSL
    errors.  Does **not** retry on HTTP 4xx/5xx — those are treated as
    permanent failures.

    Raises the last exception if all attempts are exhausted.
    """
    last_exc: Exception | None = None

    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        try:
            resp = http_requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.content
        except (
            http_requests.exceptions.Timeout,
            http_requests.exceptions.ConnectionError,
            http_requests.exceptions.SSLError,
        ) as exc:
            last_exc = exc
            if attempt < DOWNLOAD_RETRIES:
                wait = DOWNLOAD_BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    "Download attempt %d/%d failed (%s), retrying in %.1fs...",
                    attempt, DOWNLOAD_RETRIES, exc, wait,
                )
                time.sleep(wait)
        except Exception:
            raise  # HTTPError, etc. — don't retry

    logger.error("Download failed after %d attempts", DOWNLOAD_RETRIES)
    raise last_exc  # type: ignore[misc]
