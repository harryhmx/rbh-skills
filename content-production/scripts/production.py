"""
Content Production — generate images, video, and speech from text-optimizer segments.

Images: Agnes AI (``agnes-image-2.1-flash``) via ``POST /v1/images/generations``.
Videos: Agnes AI (``agnes-video-v2.0``) via ``POST /v1/videos`` + polling.
Speech: Fish Speech via SiliconFlow OpenAI-compatible endpoint.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

import requests as http_requests
from dotenv import load_dotenv
from openai import OpenAI

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
VIDEO_SIZE_DEFAULT = os.environ.get("VIDEO_SIZE", "1024x768")
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


def _download_with_retry(url: str, timeout: int = 60) -> bytes:
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


# ---------------------------------------------------------------------------
# Prompt file parser — reads the proprietary RBH prompt file format
# ---------------------------------------------------------------------------


def parse_prompt_file(path: str | Path) -> dict:
    """Parse a proprietary RBH prompt file (from text-optimizer ``genprompt``).

    Expected format::

        ---
        type: image
        size: 1024x768
        ---

        <prompt text>

    Video files additionally include ``num_frames`` and ``frame_rate`` keys.

    Parameters
    ----------
    path : str or Path
        Path to the prompt file (.md or .txt).

    Returns
    -------
    dict
        Keys: ``type`` (str), ``size`` (str), ``prompt`` (str).
        Video type also includes ``num_frames`` (int) and ``frame_rate`` (float).
    """
    raw = Path(path).read_text(encoding="utf-8")

    lines = raw.split("\n")
    metadata: dict[str, str] = {}
    in_frontmatter = False
    frontmatter_closed = False
    prompt_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not frontmatter_closed:
            if stripped == "---":
                if not in_frontmatter:
                    in_frontmatter = True
                    continue
                else:
                    frontmatter_closed = True
                    in_frontmatter = False
                    continue
            if in_frontmatter and ": " in stripped:
                key, value = stripped.split(": ", 1)
                metadata[key.strip()] = value.strip()
        else:
            prompt_lines.append(line)

    prompt_type = metadata.get("type", "")
    if prompt_type not in ("image", "video"):
        raise ValueError(
            f"Unknown or missing prompt type '{prompt_type}' in {path}. "
            "Expected 'image' or 'video'."
        )

    size = metadata.get("size", "1024x768")

    result: dict = {
        "type": prompt_type,
        "size": size,
        "prompt": "\n".join(prompt_lines).strip(),
    }

    if prompt_type == "video":
        result["num_frames"] = int(metadata.get("num_frames", "121"))
        result["frame_rate"] = float(metadata.get("frame_rate", "24"))

    if not result["prompt"]:
        raise ValueError(f"No prompt text found in {path}")

    logger.info(
        "Parsed %s prompt file: type=%s size=%s chars=%d",
        path, prompt_type, size, len(result["prompt"]),
    )
    return result


# ---------------------------------------------------------------------------
# Single asset generation — produce ONE image or video from a prompt file
# ---------------------------------------------------------------------------


def generate_single_image(
    prompt: str,
    size: str = IMAGE_SIZE_DEFAULT,
    output_path: str | Path = "output.png",
) -> dict:
    """Generate a single image from *prompt* using Agnes AI.

    Parameters
    ----------
    prompt : str
        The image generation prompt.
    size : str
        Image size in ``WxH`` format.
    output_path : str or Path
        Full path where the image should be saved.

    Returns
    -------
    dict
        Keys: ``file_path``, ``url``, ``prompt``.  ``file_path`` is ``None`` on failure.
    """
    if not IMAGE_API_KEY:
        raise RuntimeError(
            "IMAGE_API_KEY is not set. "
            "Set it in skills/.env or as an environment variable."
        )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("Generating single image (attempt %d/%d)...", attempt, MAX_RETRIES)

            payload: dict = {
                "model": IMAGE_MODEL,
                "prompt": prompt,
                "extra_body": {"response_format": "url"},
            }
            if size:
                payload["size"] = size

            data = _agnes_image_request(payload)
            urls = _extract_image_urls(data)

            if not urls:
                logger.warning("No image URL in Agnes response, retrying...")
                if attempt < MAX_RETRIES:
                    time.sleep(2)
                continue

            image_url = urls[0]
            logger.info("Downloading image from %s...", image_url[:80])

            img_res = _download_with_retry(image_url)

            if len(img_res) < 1000:
                logger.warning("Image too small (%d bytes), retrying", len(img_res))
                if attempt < MAX_RETRIES:
                    time.sleep(2)
                continue

            out.write_bytes(img_res)

            logger.info("Saved %s (%d bytes)", out.name, len(img_res))
            return {
                "file_path": str(out.resolve()),
                "url": image_url,
                "prompt": prompt,
            }

        except Exception as exc:
            logger.warning("Attempt %d failed: %s", attempt, exc)
            if attempt < MAX_RETRIES:
                time.sleep(2)

    logger.error("All %d attempts failed for single image generation", MAX_RETRIES)
    return {"file_path": None, "url": None, "prompt": prompt, "error": f"All {MAX_RETRIES} attempts failed"}


def generate_single_video(
    prompt: str,
    size: str = VIDEO_SIZE_DEFAULT,
    num_frames: int = VIDEO_NUM_FRAMES_DEFAULT,
    frame_rate: float = VIDEO_FRAME_RATE_DEFAULT,
    output_path: str | Path = "output.mp4",
) -> dict:
    """Generate a single video from *prompt* using Agnes AI.

    Submits a video task, polls until complete, then downloads.

    Parameters
    ----------
    prompt : str
        The video generation prompt.
    size : str
        Video size in ``WxH`` format.
    num_frames : int
        Number of frames (≤ 441, 8n+1).
    frame_rate : float
        Frame rate in FPS (1–60).
    output_path : str or Path
        Full path where the video should be saved.

    Returns
    -------
    dict
        Keys: ``file_path``, ``url``, ``prompt``, ``task_id``.
    """
    if not VIDEO_API_KEY:
        raise RuntimeError(
            "VIDEO_API_KEY is not set. "
            "Set it in skills/.env or as an environment variable."
        )

    # Parse size
    try:
        w_str, h_str = size.split("x")
        width, height = int(w_str), int(h_str)
    except (ValueError, AttributeError):
        raise RuntimeError(f"Invalid video size '{size}'. Expected WxH format (e.g. 1024x768).")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # 1. Submit video task
    payload: dict = {
        "model": VIDEO_MODEL,
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_frames": num_frames,
        "frame_rate": frame_rate,
    }
    logger.info(
        "Submitting single video task (%dx%d, %d frames, %.0f fps)...",
        width, height, num_frames, frame_rate,
    )

    try:
        data = _agnes_video_request(payload)
    except RuntimeError as exc:
        logger.error("Failed to submit video task: %s", exc)
        return {"file_path": None, "url": None, "prompt": prompt, "task_id": None, "error": str(exc)}

    task_id = str(data.get("id", ""))
    if not task_id:
        logger.error("No task ID in video response")
        return {"file_path": None, "url": None, "prompt": prompt, "task_id": None, "error": "No task ID in response"}

    logger.info("Video task created: %s", task_id)

    # 2. Poll until complete
    deadline = time.time() + VIDEO_POLL_TIMEOUT
    last: dict = {}
    while time.time() < deadline:
        try:
            last = _get_video_task(task_id)
        except RuntimeError as exc:
            logger.error("Video poll failed: %s", exc)
            return {"file_path": None, "url": None, "prompt": prompt, "task_id": task_id, "error": str(exc)}

        if last.get("error"):
            err = f"API error: {last['error']}"
            logger.error("Video task %s: %s", task_id, err)
            return {"file_path": None, "url": None, "prompt": prompt, "task_id": task_id, "error": err}

        status = str(last.get("status", "")).lower()
        progress = last.get("progress")
        logger.info("Video %s: status=%s progress=%s", task_id, status, progress)

        if status == "completed":
            break
        elif status == "failed":
            return {"file_path": None, "url": None, "prompt": prompt, "task_id": task_id, "error": f"Task failed: {json.dumps(last)}"}

        time.sleep(VIDEO_POLL_INTERVAL)
    else:
        return {"file_path": None, "url": None, "prompt": prompt, "task_id": task_id, "error": f"Timed out after {VIDEO_POLL_TIMEOUT}s"}

    # 3. Download video
    urls = _extract_video_urls(last)
    if not urls:
        logger.error("No video URL in completed response")
        return {"file_path": None, "url": None, "prompt": prompt, "task_id": task_id, "error": "No video URL in completed response"}

    video_url = urls[0]
    logger.info("Downloading video from %s...", video_url[:80])

    try:
        vid_res = http_requests.get(video_url, timeout=300)
        vid_res.raise_for_status()

        if len(vid_res.content) < 10000:
            logger.warning("Video too small (%d bytes), may be invalid", len(vid_res.content))

        out.write_bytes(vid_res.content)
        logger.info("Saved %s (%d bytes)", out.name, len(vid_res.content))
    except Exception as exc:
        logger.error("Video download failed: %s", exc)
        return {"file_path": None, "url": None, "prompt": prompt, "task_id": task_id, "error": str(exc)}

    return {
        "file_path": str(out.resolve()),
        "url": video_url,
        "prompt": prompt,
        "task_id": task_id,
    }


# ---------------------------------------------------------------------------
# Public API (multi-segment batch)
# ---------------------------------------------------------------------------


def load_segments_json(path: str | Path) -> list[dict]:
    """Read a text-optimizer output JSON and return its ``segments`` list."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    segments = data.get("segments", [])
    if not segments:
        raise ValueError(f"No segments found in {path} (expected key 'segments')")
    return segments


def _agnes_image_request(payload: dict) -> dict:
    """Send a JSON request to the Agnes AI images endpoint."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{IMAGE_BASE_URL}/v1/images/generations",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {IMAGE_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Agnes HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Agnes request failed: {exc}") from exc


def _extract_image_urls(data: dict) -> list[str]:
    """Extract image URLs from an Agnes API response."""
    urls: list[str] = []
    if isinstance(data.get("url"), str):
        urls.append(data["url"])
    if isinstance(data.get("image_url"), str):
        urls.append(data["image_url"])
    if isinstance(data.get("data"), list):
        for item in data["data"]:
            if isinstance(item, dict):
                for key in ("url", "image_url"):
                    if isinstance(item.get(key), str):
                        urls.append(item[key])
    return urls


def _extract_video_urls(data: dict) -> list[str]:
    """Extract video URLs from an Agnes video API response."""
    urls: list[str] = []
    for key in ("video_url", "url", "remixed_from_video_id"):
        value = data.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            urls.append(value)
    if isinstance(data.get("data"), list):
        for item in data["data"]:
            if isinstance(item, dict):
                urls.extend(_extract_video_urls(item))
    return list(dict.fromkeys(urls))


def _agnes_video_request(payload: dict) -> dict:
    """Send a JSON request to the Agnes AI videos endpoint (create task)."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{VIDEO_BASE_URL}/v1/videos",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {VIDEO_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Agnes video HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Agnes video request failed: {exc}") from exc


def _get_video_task(task_id: str) -> dict:
    """Fetch the current state of a single video task."""
    req = urllib.request.Request(
        f"{VIDEO_BASE_URL}/v1/videos/{task_id}",
        method="GET",
        headers={
            "Authorization": f"Bearer {VIDEO_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Video poll HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Video poll request failed: {exc}") from exc


def _poll_all_video_tasks(
    pending: dict[str, dict],
    timeout: int,
    interval: int,
    on_completed: Callable[[str, dict], None] | None = None,
) -> dict[str, dict]:
    """Poll multiple video tasks concurrently until all complete or fail.

    Parameters
    ----------
    pending : dict
        Map of ``task_id → {"index": int, "title": str}``.  Mutated in-place
        (completed/failed entries are removed).
    timeout : int
        Total deadline in seconds from now.
    interval : int
        Seconds between polling rounds.
    on_completed : callable or None
        Called as ``on_completed(task_id, response_data)`` for each task
        as soon as it completes.  Use this for immediate download.

    Returns
    -------
    dict
        Map of ``task_id → response_dict`` for all completed tasks.
    """
    deadline = time.time() + timeout
    completed: dict[str, dict] = {}
    failed: dict[str, str] = {}  # task_id → error message

    while pending and time.time() < deadline:
        task_ids = list(pending.keys())
        logger.info(
            "Polling %d video task(s), %d completed, %d failed...",
            len(task_ids), len(completed), len(failed),
        )

        for tid in task_ids:
            try:
                data = _get_video_task(tid)
            except RuntimeError as exc:
                failed[tid] = str(exc)
                del pending[tid]
                continue

            if data.get("error"):
                failed[tid] = f"API error: {data['error']}"
                del pending[tid]
                continue

            status = str(data.get("status", "")).lower()
            progress = data.get("progress")
            logger.info(
                "  [%d] %s: status=%s progress=%s",
                pending[tid]["index"], tid, status, progress,
            )

            if status == "completed":
                completed[tid] = data
                del pending[tid]
                if on_completed:
                    try:
                        on_completed(tid, data)
                    except Exception as exc:
                        logger.warning("on_completed callback failed for %s: %s", tid, exc)
            elif status == "failed":
                failed[tid] = f"Task failed: {json.dumps(data)}"
                del pending[tid]

        if not pending:
            break

        if pending:
            time.sleep(interval)

    if pending:
        for tid in list(pending.keys()):
            failed[tid] = f"Timed out after {timeout}s"
        pending.clear()

    if failed:
        logger.warning("%d video task(s) failed/timed out: %s", len(failed), list(failed.keys()))

    return completed


def generate_images(
    segments: list[dict],
    size: str = IMAGE_SIZE_DEFAULT,
    output_dir: str | Path = "output",
    prompt_key: str = "image_prompt",
) -> list[dict]:
    """Generate an image for each segment using Agnes AI (agnes-image-2.1-flash).

    Images are saved to *output_dir* as ``{index:03d}.png`` in index order.

    Parameters
    ----------
    segments : list[dict]
        Segments from :func:`load_segments_json`.  Each must have an
        ``index`` and the *prompt_key* field.
    size : str
        Image size in ``WxH`` format (e.g. ``"1024x768"``).
    output_dir : str or Path
        Directory to save generated images.
    prompt_key : str
        Which segment key holds the image generation prompt.
        Default: ``"image_prompt"``.

    Returns
    -------
    list[dict]
        Each dict has ``index``, ``title``, ``file_path``, ``url``, and
        ``prompt`` keys.
    """
    if not IMAGE_API_KEY:
        raise RuntimeError(
            "IMAGE_API_KEY is not set. "
            "Set it in skills/.env or as an environment variable."
        )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    results = []
    total = len(segments)

    for seg in sorted(segments, key=lambda s: s.get("index", 0)):
        idx = seg.get("index", 0)
        title = seg.get("title", f"segment-{idx}")
        prompt = seg.get(prompt_key, "")

        if not prompt:
            logger.warning("[%d/%d] No prompt for segment %d, skipping", idx + 1, total, idx)
            results.append({
                "index": idx,
                "title": title,
                "file_path": None,
                "url": None,
                "prompt": prompt,
                "error": f"No '{prompt_key}' field",
            })
            continue

        file_path = out / f"{idx:03d}.png"
        url = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "[%d/%d] Generating image for '%s' (attempt %d/%d)...",
                    idx + 1, total, title, attempt, MAX_RETRIES,
                )

                payload: dict = {
                    "model": IMAGE_MODEL,
                    "prompt": prompt,
                    "extra_body": {"response_format": "url"},
                }
                if size:
                    payload["size"] = size

                data = _agnes_image_request(payload)
                urls = _extract_image_urls(data)

                if not urls:
                    logger.warning("No image URL in Agnes response")
                    continue

                image_url = urls[0]
                logger.info("[%d/%d] Downloading from %s...", idx + 1, total, image_url[:80])

                img_res = _download_with_retry(image_url)

                if len(img_res) < 1000:
                    logger.warning("Image too small (%d bytes), retrying", len(img_res))
                    continue

                file_path.write_bytes(img_res)
                url = image_url

                logger.info(
                    "[%d/%d] Saved %s (%d bytes)",
                    idx + 1, total, file_path.name, len(img_res),
                )
                break

            except Exception as exc:
                logger.warning("[%d/%d] Attempt %d failed: %s", idx + 1, total, attempt, exc)
                if attempt < MAX_RETRIES:
                    time.sleep(2)

        results.append({
            "index": idx,
            "title": title,
            "file_path": str(file_path.resolve()) if url else None,
            "url": url,
            "prompt": prompt,
        })

    # Summary
    succeeded = sum(1 for r in results if r["url"])
    logger.info("Done: %d/%d images generated → %s", succeeded, total, out.resolve())
    return results


def generate_speech(
    segments: list[dict],
    output_dir: str | Path = "output",
    prompt_key: str = "tts_prompt",
) -> list[dict]:
    """Generate speech audio for each segment using SiliconFlow Fish Speech.

    Audio files are saved to *output_dir* as ``{index:03d}.mp3``.

    .. note::
       This is a v0.2 feature — currently a stub that will be implemented
       following the same pattern as :func:`generate_images`.
    """
    if not SPEECH_API_KEY:
        raise RuntimeError(
            "SPEECH_API_KEY is not set. "
            "Set it in skills/.env or as an environment variable."
        )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    client = OpenAI(
        api_key=SPEECH_API_KEY,
        base_url=SPEECH_BASE_URL,
    )

    results = []
    total = len(segments)

    for seg in sorted(segments, key=lambda s: s.get("index", 0)):
        idx = seg.get("index", 0)
        title = seg.get("title", f"segment-{idx}")
        prompt = seg.get(prompt_key, "")

        if not prompt:
            logger.warning("[%d/%d] No prompt for segment %d, skipping", idx + 1, total, idx)
            results.append({
                "index": idx, "title": title, "file_path": None,
                "prompt": prompt, "error": f"No '{prompt_key}' field",
            })
            continue

        file_path = out / f"{idx:03d}.mp3"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "[%d/%d] Generating speech for '%s' (attempt %d/%d)...",
                    idx + 1, total, title, attempt, MAX_RETRIES,
                )

                # Strip markdown voice direction prefix for cleaner speech
                clean_text = prompt
                if clean_text.startswith("(") and ")" in clean_text:
                    clean_text = clean_text.split(")", 1)[1].strip()

                response = client.audio.speech.create(
                    model=SPEECH_MODEL,
                    voice=SPEECH_VOICE,
                    input=clean_text,
                )

                audio_bytes = response.content if hasattr(response, "content") else response.read()

                if len(audio_bytes) < 1000:
                    logger.warning("Audio too small (%d bytes), retrying", len(audio_bytes))
                    continue

                file_path.write_bytes(audio_bytes)

                logger.info("[%d/%d] Saved %s (%d bytes)", idx + 1, total, file_path.name, len(audio_bytes))

                results.append({
                    "index": idx,
                    "title": title,
                    "file_path": str(file_path.resolve()),
                    "prompt": prompt,
                })
                break

            except Exception as exc:
                logger.warning("[%d/%d] Attempt %d failed: %s", idx + 1, total, attempt, exc)
                if attempt < MAX_RETRIES:
                    time.sleep(2)
        else:
            logger.error("[%d/%d] All %d attempts failed", idx + 1, total, MAX_RETRIES)
            results.append({
                "index": idx, "title": title, "file_path": None,
                "prompt": prompt, "error": f"All {MAX_RETRIES} attempts failed",
            })

    succeeded = sum(1 for r in results if r.get("file_path"))
    logger.info("Done: %d/%d speech files generated → %s", succeeded, total, out.resolve())
    return results


def generate_videos(
    segments: list[dict],
    size: str = VIDEO_SIZE_DEFAULT,
    output_dir: str | Path = "output",
    prompt_key: str = "video_prompt",
    num_frames: int = VIDEO_NUM_FRAMES_DEFAULT,
    frame_rate: float = VIDEO_FRAME_RATE_DEFAULT,
) -> list[dict]:
    """Generate a video for each segment using Agnes AI (agnes-video-v2.0).

    All video tasks are **submitted first in batch**, then **polled
    concurrently** (round-robin) until each completes or fails, and
    finally downloaded.  This means total wall-clock time is roughly
    the slowest single video, not the sum of all videos.

    Videos are saved to *output_dir* as ``{index:03d}.mp4`` in index order.

    Parameters
    ----------
    segments : list[dict]
        Segments from :func:`load_segments_json`.  Each must have an
        ``index`` and the *prompt_key* field.
    size : str
        Video size in ``WxH`` format (e.g. ``"1024x768"``).
    output_dir : str or Path
        Directory to save generated videos.
    prompt_key : str
        Which segment key holds the video generation prompt.
        Default: ``"video_prompt"``.
    num_frames : int
        Number of frames. Must be <= 441 and satisfy ``8n + 1``
        (e.g. 81, 121, 241).  Default from ``VIDEO_NUM_FRAMES`` env.
    frame_rate : float
        Frame rate in FPS (1–60).  Default from ``VIDEO_FRAME_RATE`` env.

    Returns
    -------
    list[dict]
        Each dict has ``index``, ``title``, ``file_path``, ``url``,
        ``prompt``, and ``task_id`` keys.
    """
    if not VIDEO_API_KEY:
        raise RuntimeError(
            "VIDEO_API_KEY is not set. "
            "Set it in skills/.env or as an environment variable."
        )

    # Parse size into width/height for the Agnes video API
    try:
        w_str, h_str = size.split("x")
        width, height = int(w_str), int(h_str)
    except (ValueError, AttributeError):
        raise RuntimeError(f"Invalid video size '{size}'. Expected WxH format (e.g. 1024x768).")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    sorted_segments = sorted(segments, key=lambda s: s.get("index", 0))
    total = len(sorted_segments)

    # ------------------------------------------------------------------
    # Phase 1 — Submit all video creation tasks in batch
    # ------------------------------------------------------------------
    pending: dict[str, dict] = {}          # task_id → {index, title} for polling
    task_meta: dict[str, dict] = {}        # task_id → {index, title, prompt, file_path}
    submit_errors: dict[int, dict] = {}    # index → result (skipped / failed submit)

    for seg in sorted_segments:
        idx = seg.get("index", 0)
        title = seg.get("title", f"segment-{idx}")
        prompt = seg.get(prompt_key, "")

        if not prompt:
            logger.warning("[%d/%d] No prompt for segment %d, skipping", idx + 1, total, idx)
            submit_errors[idx] = {
                "index": idx, "title": title, "file_path": None,
                "url": None, "prompt": prompt, "task_id": None,
                "error": f"No '{prompt_key}' field",
            }
            continue

        try:
            payload: dict = {
                "model": VIDEO_MODEL,
                "prompt": prompt,
                "width": width,
                "height": height,
                "num_frames": num_frames,
                "frame_rate": frame_rate,
            }
            logger.info(
                "[%d/%d] Submitting video task for '%s' (%dx%d, %d frames, %.0f fps)...",
                idx + 1, total, title, width, height, num_frames, frame_rate,
            )

            data = _agnes_video_request(payload)
            task_id = str(data.get("id", ""))

            if not task_id:
                logger.warning("[%d/%d] No task ID in response, skipping", idx + 1, total)
                submit_errors[idx] = {
                    "index": idx, "title": title, "file_path": None,
                    "url": None, "prompt": prompt, "task_id": None,
                    "error": "No task ID in response",
                }
                continue

            logger.info("[%d/%d] Task created: %s", idx + 1, total, task_id)
            pending[task_id] = {"index": idx, "title": title}
            task_meta[task_id] = {
                "index": idx,
                "title": title,
                "prompt": prompt,
                "file_path": out / f"{idx:03d}.mp4",
            }
            time.sleep(0.5)  # brief pause between submissions to avoid rate limits

        except Exception as exc:
            logger.error("[%d/%d] Failed to submit video task: %s", idx + 1, total, exc)
            submit_errors[idx] = {
                "index": idx, "title": title, "file_path": None,
                "url": None, "prompt": prompt, "task_id": None,
                "error": f"Task submission failed: {exc}",
            }

    logger.info(
        "Submitted %d tasks, %d skipped → now polling all concurrently",
        len(pending), len(submit_errors),
    )

    # ------------------------------------------------------------------
    # Phase 2 — Poll all tasks concurrently; download each video IMMEDIATELY
    #           as soon as it completes (no waiting for slow tasks)
    # ------------------------------------------------------------------
    final_results: list[dict] = []

    def _download_on_complete(tid: str, data: dict) -> None:
        """Called as soon as a task completes — download the video now."""
        meta = task_meta.get(tid)
        if not meta:
            return
        idx = meta["index"]
        file_path = meta["file_path"]
        title = meta["title"]
        prompt = meta["prompt"]
        url = None

        try:
            urls = _extract_video_urls(data)
            if not urls:
                logger.warning("[%d] No video URL for task %s", idx, tid)
                final_results.append({
                    "index": idx, "title": title, "file_path": None,
                    "url": None, "prompt": prompt, "task_id": tid,
                    "error": "No video URL in completed response",
                })
                return

            video_url = urls[0]
            logger.info("[%d] Downloading video from %s...", idx, video_url[:80])

            vid_res = http_requests.get(video_url, timeout=300)
            vid_res.raise_for_status()

            if len(vid_res.content) < 10000:
                logger.warning("[%d] Video too small (%d bytes), may be invalid", idx, len(vid_res.content))

            file_path.write_bytes(vid_res.content)
            url = video_url

            logger.info("[%d] Saved %s (%d bytes)", idx, file_path.name, len(vid_res.content))

        except Exception as exc:
            logger.error("[%d] Video download failed: %s", idx, exc)

        final_results.append({
            "index": idx,
            "title": title,
            "file_path": str(file_path.resolve()) if url else None,
            "url": url,
            "prompt": prompt,
            "task_id": tid,
        })

    completed_data = _poll_all_video_tasks(
        pending, VIDEO_POLL_TIMEOUT, VIDEO_POLL_INTERVAL,
        on_completed=_download_on_complete,
    )

    # Any tasks still in pending at this point are failures (timed out or failed)
    for task_id, _meta in pending.items():
        if task_id in task_meta:
            submit_errors[task_meta[task_id]["index"]] = {
                "index": task_meta[task_id]["index"],
                "title": task_meta[task_id]["title"],
                "file_path": None, "url": None,
                "prompt": task_meta[task_id]["prompt"],
                "task_id": task_id,
                "error": "Task did not complete within timeout",
            }

    # Merge submit errors
    for err_result in submit_errors.values():
        final_results.append(err_result)

    # Sort by index and deduplicate
    seen: set[int] = set()
    merged: list[dict] = []
    for r in sorted(final_results, key=lambda r: r["index"]):
        if r["index"] not in seen:
            seen.add(r["index"])
            merged.append(r)

    succeeded = sum(1 for r in merged if r["url"])
    logger.info("Done: %d/%d videos generated → %s", succeeded, total, out.resolve())
    return merged


# ---------------------------------------------------------------------------
# Image captioning — overlay title text onto generated images
# ---------------------------------------------------------------------------

# CJK-capable font paths to try (order: preference)
_CJK_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

_DEFAULT_FONT_SIZE = 36


def _find_cjk_font() -> str | None:
    """Return the first available CJK-capable font path, or None."""
    for path in _CJK_FONT_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def caption_images(
    segments: list[dict],
    image_dir: str | Path,
    output_dir: str | Path | None = None,
    font_path: str | None = None,
    font_size: int = _DEFAULT_FONT_SIZE,
) -> list[dict]:
    """Overlay the ``title`` from each segment onto the corresponding image.

    Images are matched by ``{index:03d}.png`` filename.  Text is placed
    centered on a semi-transparent dark banner spanning the image width.

    Parameters
    ----------
    segments : list[dict]
        Segments with ``index`` and ``title`` keys.
    image_dir : str or Path
        Directory containing PNG images named ``{index:03d}.png``.
    output_dir : str or Path or None
        Where to write captioned images.  If ``None``, overwrites originals.
    font_path : str or None
        Path to a .ttf/.ttc font (CJK-capable for Chinese text).  Auto-detected
        from common system paths when ``None``.
    font_size : int
        Font size in points.  Default: 36.

    Returns
    -------
    list[dict]
        Each dict has ``index``, ``title``, ``source``, ``output`` keys.
    """
    from PIL import Image, ImageDraw, ImageFont

    src_dir = Path(image_dir)
    out_dir = Path(output_dir) if output_dir else src_dir
    if output_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    # Resolve font
    font = None
    if font_path:
        font = ImageFont.truetype(font_path, font_size)
    else:
        auto = _find_cjk_font()
        if auto:
            font = ImageFont.truetype(auto, font_size)
            logger.info("Using font: %s", auto)
        else:
            logger.warning("No CJK font found — using PIL default (may not render Chinese)")
            font = ImageFont.load_default()

    results = []

    for seg in sorted(segments, key=lambda s: s.get("index", 0)):
        idx = seg.get("index", 0)
        title = seg.get("title", "").strip()

        if not title:
            logger.warning("[%d] No title, skipping", idx)
            continue

        src_file = src_dir / f"{idx:03d}.png"
        if not src_file.exists():
            logger.warning("[%d] Image not found: %s", idx, src_file)
            results.append({"index": idx, "title": title, "source": str(src_file), "output": None, "error": "Source image not found"})
            continue

        out_file = out_dir / f"{idx:03d}.png"

        try:
            img = Image.open(src_file).convert("RGBA")
            draw = ImageDraw.Draw(img)
            img_w, img_h = img.size

            # Measure text
            bbox = draw.textbbox((0, 0), title, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]

            # Banner: full width, centered vertically
            banner_h = int(th * 1.6)
            banner_y = (img_h - banner_h) // 2

            # Draw semi-transparent dark overlay
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.rectangle(
                [(0, banner_y), (img_w, banner_y + banner_h)],
                fill=(0, 0, 0, 160),
            )
            img = Image.alpha_composite(img, overlay)

            # Draw title text centered
            draw = ImageDraw.Draw(img)
            tx = (img_w - tw) // 2
            ty = banner_y + (banner_h - th) // 2
            draw.text((tx, ty), title, font=font, fill=(255, 255, 255, 255))

            # Save as RGB (no alpha needed for final)
            img.convert("RGB").save(out_file, "PNG")

            logger.info("[%d] Captioned: %s", idx, out_file.name)

            results.append({
                "index": idx,
                "title": title,
                "source": str(src_file.resolve()),
                "output": str(out_file.resolve()),
            })

        except Exception as exc:
            logger.error("[%d] Caption failed: %s", idx, exc)
            results.append({"index": idx, "title": title, "source": str(src_file), "output": None, "error": str(exc)})

    succeeded = sum(1 for r in results if r.get("output"))
    logger.info("Done: %d/%d images captioned → %s", succeeded, len(results), out_dir.resolve())
    return results
