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

# Agnes AI image generation
IMAGE_API_KEY = os.environ.get("IMAGE_API_KEY", "")
IMAGE_BASE_URL = os.environ.get("IMAGE_BASE_URL", "https://apihub.agnes-ai.com")
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "agnes-image-2.1-flash")
IMAGE_SIZE_DEFAULT = os.environ.get("IMAGE_SIZE", "1024x768")

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

MAX_RETRIES = 2
DOWNLOAD_RETRIES = 3          # retries for the download step only
DOWNLOAD_BACKOFF_BASE = 2.0   # seconds, multiplied by 2^(attempt-1)


# ---------------------------------------------------------------------------
# Public API — segments JSON loading
# ---------------------------------------------------------------------------


def load_segments_json(path: str | Path) -> list[dict]:
    """Read a segments JSON file and return its ``segments`` list.

    The JSON can come from the Local Agent (default path).
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    segments = data.get("segments", [])
    if not segments:
        raise ValueError(f"No segments found in {path} (expected key 'segments')")
    return segments


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
