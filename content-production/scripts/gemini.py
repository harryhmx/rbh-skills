"""
Gemini API provider adapter — image (Nano Banana via the Interactions API),
video (Veo long-running operations), and speech (Gemini TTS via the
Interactions API).

Activated per capability via ``IMAGE_PROVIDER`` / ``VIDEO_PROVIDER`` /
``SPEECH_PROVIDER`` = ``gemini`` in skills/.env.  All calls hit the Gemini
REST API directly with the ``x-goog-api-key`` header — no SDK dependency.

Image and speech use ``POST /v1beta/interactions`` (GA since June 2026 and
the recommended interface; the legacy ``generateContent`` API remains
supported but new models launch on Interactions).  Video uses the Veo
``:predictLongRunning`` + operation-polling flow.
"""

from __future__ import annotations

import base64
import io
import json
import math
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

from scripts.common import (
    build_filename,
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    GEMINI_IMAGE_MODEL,
    GEMINI_IMAGE_SIZE,
    GEMINI_VIDEO_MODEL,
    GEMINI_VIDEO_DURATION,
    GEMINI_VIDEO_RESOLUTION,
    GEMINI_VIDEO_CONCURRENCY,
    GEMINI_TTS_MODEL,
    GEMINI_TTS_VOICE,
    VIDEO_POLL_TIMEOUT,
    VIDEO_POLL_INTERVAL,
    logger,
)

# ---------------------------------------------------------------------------
# Low-level REST helpers
# ---------------------------------------------------------------------------


def _gemini_request(
    path: str,
    payload: dict | None = None,
    method: str = "POST",
    timeout: int = 180,
) -> dict:
    """Send a JSON request to the Gemini API and return the parsed response."""
    url = path if path.startswith("http") else f"{GEMINI_BASE_URL}/{path.lstrip('/')}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "x-goog-api-key": GEMINI_API_KEY,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini request failed: {exc}") from exc


def _gemini_download(url: str, timeout: int = 300) -> bytes:
    """Download binary content (e.g. a generated video file) with the API key."""
    req = urllib.request.Request(url, headers={"x-goog-api-key": GEMINI_API_KEY})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini download HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini download failed: {exc}") from exc


def _nearest_aspect_ratio(size: str, supported: list[str]) -> str:
    """Map a ``WxH`` size string to the nearest supported aspect ratio."""
    try:
        w_str, h_str = size.lower().split("x")
        target = int(w_str) / int(h_str)
    except (ValueError, ZeroDivisionError, AttributeError):
        return supported[0]

    def distance(ratio: str) -> float:
        rw, rh = ratio.split(":")
        return abs(math.log(target) - math.log(int(rw) / int(rh)))

    return min(supported, key=distance)


def _find_interaction_block(data: dict, block_type: str) -> dict:
    """Extract the first content block of *block_type* from an Interactions
    API response (``steps[] → model_output → content[]``)."""
    for step in data.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for block in step.get("content", []):
            if block.get("type") == block_type and block.get("data"):
                return block
    raise RuntimeError(
        f"No '{block_type}' block in Gemini interaction response "
        f"(status={data.get('status')}): {json.dumps(data)[:500]}"
    )


# ---------------------------------------------------------------------------
# Image — Nano Banana (native Gemini image models) via the Interactions API
# ---------------------------------------------------------------------------

_IMAGE_ASPECT_RATIOS = [
    "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9",
]


def gemini_generate_image(prompt: str, size: str) -> bytes:
    """Generate a single image and return its raw bytes.

    Uses ``POST /interactions`` with a Nano Banana model
    (default ``gemini-3.1-flash-image``).  The ``WxH`` *size* is mapped to
    the nearest supported aspect ratio; resolution comes from
    ``GEMINI_IMAGE_SIZE`` (1K / 2K / 4K).
    """
    aspect_ratio = _nearest_aspect_ratio(size, _IMAGE_ASPECT_RATIOS)

    payload = {
        "model": GEMINI_IMAGE_MODEL,
        "input": [{"type": "text", "text": prompt}],
        "response_format": {
            "type": "image",
            "aspect_ratio": aspect_ratio,
            "image_size": GEMINI_IMAGE_SIZE,
        },
        "store": False,
    }
    data = _gemini_request("interactions", payload)
    block = _find_interaction_block(data, "image")
    return base64.b64decode(block["data"])


# ---------------------------------------------------------------------------
# Video — Veo via long-running operations
# ---------------------------------------------------------------------------

_VIDEO_ASPECT_RATIOS = ["16:9", "9:16"]

# Veo preview quotas are tight (low requests-per-minute and few in-flight
# operations), so submissions are rate-limit aware: at most
# GEMINI_VIDEO_CONCURRENCY operations run concurrently, and an HTTP 429 puts
# the segment back in the queue after a cooldown instead of failing it.
_VEO_RATE_LIMIT_WAIT = 20.0  # seconds to cool down after an HTTP 429
_VEO_SUBMIT_MAX_ATTEMPTS = 8  # per-segment submission attempts before giving up


def _is_rate_limited(exc: Exception) -> bool:
    return "HTTP 429" in str(exc)


def _submit_video(prompt: str, aspect_ratio: str) -> str:
    """Submit a Veo generation request; returns the operation name."""
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "aspectRatio": aspect_ratio,
            "resolution": GEMINI_VIDEO_RESOLUTION,
            "durationSeconds": GEMINI_VIDEO_DURATION,
        },
    }
    data = _gemini_request(
        f"models/{GEMINI_VIDEO_MODEL}:predictLongRunning", payload
    )
    name = data.get("name", "")
    if not name:
        raise RuntimeError(f"No operation name in Veo response: {json.dumps(data)[:500]}")
    return name


def _extract_video_uri(operation: dict) -> str:
    """Extract the generated-video file URI from a completed Veo operation."""
    response = operation.get("response", {})
    samples = (
        response.get("generateVideoResponse", {}).get("generatedSamples")
        or response.get("generatedVideos")
        or []
    )
    for sample in samples:
        uri = sample.get("video", {}).get("uri", "")
        if uri:
            return uri
    raise RuntimeError(
        f"No video URI in completed Veo operation: {json.dumps(operation)[:500]}"
    )




def _process_veo_completion(
    op_name: str, operation: dict, output_path: Path,
) -> dict:
    """Download a completed Veo video and return a result dict.

    Returns ``{file_path, url, video_id}`` on success, or
    ``{file_path: None, url: None, video_id, error}`` on failure.
    """
    if operation.get("error"):
        return {
            "file_path": None, "url": None, "video_id": op_name,
            "error": f"Veo generation failed: {json.dumps(operation['error'])}",
        }

    try:
        uri = _extract_video_uri(operation)
        logger.info("Downloading video from %s...", uri[:80])
        video_bytes = _gemini_download(uri)
        Path(output_path).write_bytes(video_bytes)
        logger.info("Saved %s (%d bytes)", output_path.name, len(video_bytes))
        return {
            "file_path": str(Path(output_path).resolve()),
            "url": uri, "video_id": op_name,
        }
    except Exception as exc:
        logger.warning("Video download failed: %s", exc)
        return {
            "file_path": None, "url": None, "video_id": op_name,
            "error": f"Download failed: {exc}",
        }


def gemini_generate_videos(
    segments: list[dict],
    size: str,
    output_dir: str | Path = "output",
    name: str | None = None,
) -> list[dict]:
    """Generate a video for each segment via Veo.

    Veo quotas allow only a few concurrent operations, so this uses a
    sliding window instead of the Agnes submit-all pattern: at most
    ``GEMINI_VIDEO_CONCURRENCY`` operations are in flight, new segments are
    submitted as slots free up, and HTTP 429 responses re-queue the segment
    after a cooldown.  Videos are saved to *output_dir* as
    ``{index:03d}.mp4`` when neither is set (uses ``name``/``slug``).

    Returns the same result-dict shape as the Agnes provider (``video_id``
    holds the Veo operation name).
    """
    aspect_ratio = _nearest_aspect_ratio(size, _VIDEO_ASPECT_RATIOS)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    sorted_segments = sorted(segments, key=lambda s: s.get("index", 0))
    total = len(sorted_segments)

    # Submission queue: (segment, attempts) pairs, consumed front-first
    queue: list[tuple[dict, int]] = []
    results: list[dict] = []

    for seg in sorted_segments:
        queue.append((seg, 0))

    pending: dict[str, dict] = {}  # operation name → meta
    deadline = time.time() + VIDEO_POLL_TIMEOUT
    rate_limited_until = 0.0

    logger.info(
        "Generating %d video(s) via Veo (window: %d concurrent)",
        len(queue), GEMINI_VIDEO_CONCURRENCY,
    )

    while (queue or pending) and time.time() < deadline:
        # Fill free slots from the queue (unless cooling down after a 429)
        while (
            queue
            and len(pending) < GEMINI_VIDEO_CONCURRENCY
            and time.time() >= rate_limited_until
        ):
            seg, attempts = queue.pop(0)
            idx = seg["index"]
            title = seg["title"]
            prompt = seg["video_prompt"]
            try:
                logger.info(
                    "[%d/%d] Submitting Veo generation for '%s' (%s, %s, %ds, attempt %d)...",
                    idx + 1, total, title, aspect_ratio,
                    GEMINI_VIDEO_RESOLUTION, GEMINI_VIDEO_DURATION, attempts + 1,
                )
                op_name = _submit_video(prompt, aspect_ratio)
                logger.info("[%d/%d] Veo operation created: %s", idx + 1, total, op_name)
                pending[op_name] = {
                    "index": idx,
                    "title": title,
                    "prompt": prompt,
                    "file_path": out / build_filename(name, seg.get("slug"), idx, ".mp4"),
                }
            except Exception as exc:
                if _is_rate_limited(exc) and attempts + 1 < _VEO_SUBMIT_MAX_ATTEMPTS:
                    rate_limited_until = time.time() + _VEO_RATE_LIMIT_WAIT
                    queue.insert(0, (seg, attempts + 1))
                    logger.warning(
                        "[%d/%d] Rate limited (429) — re-queued, cooling down %.0fs",
                        idx + 1, total, _VEO_RATE_LIMIT_WAIT,
                    )
                else:
                    logger.error("[%d/%d] Failed to submit Veo generation: %s", idx + 1, total, exc)
                    results.append({
                        "index": idx, "title": title, "file_path": None,
                        "url": None, "prompt": prompt, "video_id": None,
                        "error": f"Video submission failed: {exc}",
                    })

        # Poll in-flight operations; download as soon as one completes
        for op_name in list(pending.keys()):
            meta = pending[op_name]
            try:
                operation = _gemini_request(op_name, method="GET")
            except RuntimeError as exc:
                logger.error("[%d] Poll failed: %s", meta["index"], exc)
                results.append({
                    "index": meta["index"], "title": meta["title"],
                    "file_path": None, "url": None, "prompt": meta["prompt"],
                    "video_id": op_name, "error": str(exc),
                })
                del pending[op_name]
                continue

            if not operation.get("done"):
                logger.info("  [%d] %s: running...", meta["index"], op_name)
                continue

            del pending[op_name]

            result = _process_veo_completion(op_name, operation, meta["file_path"])
            if result.get("error"):
                logger.error("[%d] %s", meta["index"], result["error"])
            results.append({
                "index": meta["index"], "title": meta["title"],
                "prompt": meta["prompt"],
                "file_path": result.get("file_path"),
                "url": result.get("url"),
                "video_id": op_name,
                "error": result.get("error"),
            })

        if queue or pending:
            time.sleep(VIDEO_POLL_INTERVAL)

    # Anything still pending or queued timed out
    for op_name, meta in pending.items():
        results.append({
            "index": meta["index"], "title": meta["title"],
            "file_path": None, "url": None, "prompt": meta["prompt"],
            "video_id": op_name,
            "error": f"Timed out after {VIDEO_POLL_TIMEOUT}s",
        })
    for seg, _attempts in queue:
        idx = seg["index"]
        results.append({
            "index": idx, "title": seg["title"],
            "file_path": None, "url": None, "prompt": seg["video_prompt"],
            "video_id": None,
            "error": f"Timed out after {VIDEO_POLL_TIMEOUT}s (never submitted)",
        })

    merged = sorted(results, key=lambda r: r["index"])
    succeeded = sum(1 for r in merged if r["file_path"])
    logger.info("Done: %d/%d videos generated → %s", succeeded, total, out.resolve())
    return merged

def gemini_generate_one_video(
    prompt: str,
    size: str,
    output_path: str | Path,
) -> dict:
    """Generate a single video via Veo and save to *output_path*.

    Returns a result dict with ``file_path``, ``url``, ``prompt``, and
    ``video_id`` (the Veo operation name) keys.
    """
    aspect_ratio = _nearest_aspect_ratio(size, _VIDEO_ASPECT_RATIOS)

    try:
        op_name = _submit_video(prompt, aspect_ratio)
    except Exception as exc:
        return {
            "file_path": None, "url": None, "prompt": prompt,
            "video_id": None, "error": f"Failed to submit: {exc}",
        }

    deadline = time.time() + VIDEO_POLL_TIMEOUT
    while time.time() < deadline:
        try:
            operation = _gemini_request(op_name, method="GET")
        except RuntimeError as exc:
            return {
                "file_path": None, "url": None, "prompt": prompt,
                "video_id": op_name, "error": str(exc),
            }

        if operation.get("done"):
            break
        time.sleep(VIDEO_POLL_INTERVAL)
    else:
        return {
            "file_path": None, "url": None, "prompt": prompt,
            "video_id": op_name,
            "error": f"Timed out after {VIDEO_POLL_TIMEOUT}s",
        }

    result = _process_veo_completion(op_name, operation, Path(output_path))
    result["prompt"] = prompt
    return result




# ---------------------------------------------------------------------------
# Speech — Gemini TTS via the Interactions API
# ---------------------------------------------------------------------------

# Gemini TTS returns raw PCM: 16-bit signed little-endian, 24 kHz, mono.
_TTS_SAMPLE_RATE = 24000
_TTS_SAMPLE_WIDTH = 2  # bytes (s16le)
_TTS_CHANNELS = 1


def _pcm_to_wav(pcm: bytes) -> bytes:
    """Wrap raw Gemini TTS PCM data in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(_TTS_CHANNELS)
        wav.setsampwidth(_TTS_SAMPLE_WIDTH)
        wav.setframerate(_TTS_SAMPLE_RATE)
        wav.writeframes(pcm)
    return buf.getvalue()


def gemini_generate_speech(text: str, voice: str = GEMINI_TTS_VOICE) -> bytes:
    """Generate speech audio for *text* and return WAV bytes.

    Uses ``POST /interactions`` with a Gemini TTS model
    (default ``gemini-3.1-flash-tts-preview``) and a prebuilt voice.
    """
    payload = {
        "model": GEMINI_TTS_MODEL,
        "input": text,
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voice}]},
        "store": False,
    }
    data = _gemini_request("interactions", payload)
    block = _find_interaction_block(data, "audio")
    audio = base64.b64decode(block["data"])

    # Already a WAV container → save as-is; raw PCM → wrap it.
    mime = block.get("mime_type", "")
    if "wav" in mime or audio[:4] == b"RIFF":
        return audio
    return _pcm_to_wav(audio)
