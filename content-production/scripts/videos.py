"""
Video generation — multi-provider dispatch (Agnes AI / Gemini Veo).

The provider is selected via ``VIDEO_PROVIDER`` in skills/.env:

- ``agnes`` (default) — Agnes AI ``POST /v1/videos``: all videos are
  submitted first in batch, then polled concurrently (round-robin) until each
  completes or fails, and finally downloaded.  Total wall-clock time is
  roughly the slowest single video, not the sum of all videos.
- ``gemini`` — Google Veo via the Gemini API long-running operations flow
  (same submit-all → poll → download pattern, implemented in
  :mod:`scripts.gemini`).
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

import requests as http_requests

from scripts.common import build_filename
from scripts.common import (
    VIDEO_PROVIDER,
    VIDEO_API_KEY,
    VIDEO_BASE_URL,
    VIDEO_MODEL,
    VIDEO_SIZE_DEFAULT,
    VIDEO_NUM_FRAMES_DEFAULT,
    VIDEO_FRAME_RATE_DEFAULT,
    VIDEO_POLL_TIMEOUT,
    VIDEO_POLL_INTERVAL,
    GEMINI_API_KEY,
    logger,
)

# ---------------------------------------------------------------------------
# Agnes AI video helpers
# ---------------------------------------------------------------------------


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




def _submit_one_video_agnes(
    prompt: str,
    width: int,
    height: int,
    num_frames: int,
    frame_rate: float,
) -> str:
    """Submit a single video generation request to Agnes AI. Returns the video ID."""
    payload: dict = {
        "model": VIDEO_MODEL,
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_frames": num_frames,
        "frame_rate": frame_rate,
    }
    logger.info(
        "Submitting video generation (%dx%d, %d frames, %.0f fps)...",
        width, height, num_frames, frame_rate,
    )
    data = _agnes_video_request(payload)
    video_id = str(data.get("id", ""))
    if not video_id:
        raise RuntimeError("No video ID in response")
    return video_id


def _download_video_completed(
    video_id: str, completed_data: dict, output_path: Path,
) -> str | None:
    """Download a completed video from the Agnes API. Returns the video URL or None."""
    urls = _extract_video_urls(completed_data)
    if not urls:
        logger.warning("No video URL for video %s", video_id)
        return None
    video_url = urls[0]
    logger.info("Downloading video from %s...", video_url[:80])
    vid_res = http_requests.get(video_url, timeout=300)
    vid_res.raise_for_status()
    if len(vid_res.content) < 10000:
        logger.warning("Video too small (%d bytes), may be invalid", len(vid_res.content))
    output_path.write_bytes(vid_res.content)
    logger.info("Saved %s (%d bytes)", output_path.name, len(vid_res.content))
    return video_url


def _agnes_video_request(payload: dict) -> dict:
    """Send a JSON request to the Agnes AI videos endpoint (create video)."""
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


def _get_video(video_id: str) -> dict:
    """Fetch the current state of a single video generation."""
    req = urllib.request.Request(
        f"{VIDEO_BASE_URL}/v1/videos/{video_id}",
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


def _poll_all_videos(
    pending: dict[str, dict],
    timeout: int,
    interval: int,
    on_completed: Callable[[str, dict], None] | None = None,
) -> tuple[dict[str, dict], dict[str, str]]:
    """Poll multiple video generations concurrently until all complete or fail.

    Parameters
    ----------
    pending : dict
        Map of ``video_id → {"index": int, "title": str}``.  Mutated in-place
        (completed/failed entries are removed).
    timeout : int
        Total deadline in seconds from now.
    interval : int
        Seconds between polling rounds.
    on_completed : callable or None
        Called as ``on_completed(video_id, response_data)`` for each video
        as soon as it completes.  Use this for immediate download.

    Returns
    -------
    tuple[dict, dict]
        Completed response data and failure messages, both keyed by video ID.
    """
    deadline = time.time() + timeout
    completed: dict[str, dict] = {}
    failed: dict[str, str] = {}  # video_id → error message

    while pending and time.time() < deadline:
        video_ids = list(pending.keys())
        logger.info(
            "Polling %d video(s), %d completed, %d failed...",
            len(video_ids), len(completed), len(failed),
        )

        for vid in video_ids:
            try:
                data = _get_video(vid)
            except RuntimeError as exc:
                failed[vid] = str(exc)
                del pending[vid]
                continue

            if data.get("error"):
                failed[vid] = f"API error: {data['error']}"
                del pending[vid]
                continue

            status = str(data.get("status", "")).lower()
            progress = data.get("progress")
            logger.info(
                "  [%d] %s: status=%s progress=%s",
                pending[vid]["index"], vid, status, progress,
            )

            if status == "completed":
                completed[vid] = data
                del pending[vid]
                if on_completed:
                    try:
                        on_completed(vid, data)
                    except Exception as exc:
                        logger.warning("on_completed callback failed for %s: %s", vid, exc)
            elif status == "failed":
                failed[vid] = f"Video generation failed: {json.dumps(data)}"
                del pending[vid]

        if not pending:
            break

        if pending:
            time.sleep(interval)

    if pending:
        for vid in list(pending.keys()):
            failed[vid] = f"Timed out after {timeout}s"
        pending.clear()

    if failed:
        logger.warning("%d video(s) failed/timed out: %s", len(failed), list(failed.keys()))

    return completed, failed


# ---------------------------------------------------------------------------
# Batch video generation
# ---------------------------------------------------------------------------



def generate_one_video_agnes(
    prompt: str,
    size: str,
    output_path: str | Path,
    num_frames: int = VIDEO_NUM_FRAMES_DEFAULT,
    frame_rate: float = VIDEO_FRAME_RATE_DEFAULT,
) -> dict:
    """Generate a single video via Agnes AI (submit → poll → download).

    Returns a result dict with ``file_path``, ``url``, ``prompt``, and ``video_id`` keys.
    """
    w_str, h_str = size.split("x")
    width, height = int(w_str), int(h_str)
    out = Path(output_path)

    try:
        video_id = _submit_one_video_agnes(prompt, width, height, num_frames, frame_rate)
    except Exception as exc:
        return {
            "file_path": None, "url": None, "prompt": prompt,
            "video_id": None, "error": f"Failed to submit: {exc}",
        }

    deadline = time.time() + VIDEO_POLL_TIMEOUT
    while time.time() < deadline:
        try:
            data = _get_video(video_id)
        except RuntimeError as exc:
            return {
                "file_path": None, "url": None, "prompt": prompt,
                "video_id": video_id, "error": str(exc),
            }
        status = str(data.get("status", "")).lower()
        if status == "completed":
            break
        elif status == "failed":
            return {
                "file_path": None, "url": None, "prompt": prompt,
                "video_id": video_id,
                "error": f"Video generation failed: {json.dumps(data)}",
            }
        time.sleep(VIDEO_POLL_INTERVAL)
    else:
        return {
            "file_path": None, "url": None, "prompt": prompt,
            "video_id": video_id,
            "error": f"Timed out after {VIDEO_POLL_TIMEOUT}s",
        }

    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        url = _download_video_completed(video_id, data, out)
        if not url:
            return {
                "file_path": None, "url": None, "prompt": prompt,
                "video_id": video_id, "error": "No video URL in completed response",
            }
        return {
            "file_path": str(out.resolve()),
            "url": url, "prompt": prompt, "video_id": video_id,
        }
    except Exception as exc:
        return {
            "file_path": None, "url": None, "prompt": prompt,
            "video_id": video_id, "error": f"Download failed: {exc}",
        }



def generate_one_video(
    prompt: str,
    size: str = VIDEO_SIZE_DEFAULT,
    output_path: str | Path | None = None,
    num_frames: int = VIDEO_NUM_FRAMES_DEFAULT,
    frame_rate: float = VIDEO_FRAME_RATE_DEFAULT,
) -> dict:
    """Generate a single video via the configured provider.

    The provider is selected by ``VIDEO_PROVIDER`` (agnes / gemini).
    Returns a result dict with ``file_path``, ``url``, ``prompt``, and ``video_id``.
    """
    out = Path(output_path or "output.mp4")

    if VIDEO_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is not set (required by VIDEO_PROVIDER=gemini). "
                "Set it in skills/.env or as an environment variable."
            )
        from scripts.gemini import gemini_generate_one_video

        return gemini_generate_one_video(prompt, size, out)

    if VIDEO_PROVIDER != "agnes":
        raise RuntimeError(
            f"Unknown VIDEO_PROVIDER '{VIDEO_PROVIDER}'. Supported: agnes, gemini."
        )

    if not VIDEO_API_KEY:
        raise RuntimeError(
            "VIDEO_API_KEY is not set. "
            "Set it in skills/.env or as an environment variable."
        )

    return generate_one_video_agnes(prompt, size, out, num_frames, frame_rate)




def generate_videos(
    segments: list[dict],
    name: str | None = None,
    size: str = VIDEO_SIZE_DEFAULT,
    output_dir: str | Path = "output",
    num_frames: int = VIDEO_NUM_FRAMES_DEFAULT,
    frame_rate: float = VIDEO_FRAME_RATE_DEFAULT,
) -> list[dict]:
    """Generate a video for each segment via the configured provider.

    The provider is selected by ``VIDEO_PROVIDER`` (agnes / gemini).

    All videos are **submitted first in batch**, then **polled
    concurrently** (round-robin) until each completes or fails, and
    finally downloaded.  This means total wall-clock time is roughly
    the slowest single video, not the sum of all videos.

    Videos are saved to *output_dir*.  File naming uses the optional
    top-level ``name`` and segment-level ``slug`` values, falling back to
    ``{index:03d}.mp4`` when neither is set.

    Parameters
    ----------
    segments : list[dict]
        Validated media segments. Each has ``index``, ``title``, and
        ``video_prompt``.
    name : str or None
        Optional top-level project name for filename prefixes (kebab-case).
    size : str
        Video size in ``WxH`` format (e.g. ``"1024x768"``).  For Gemini the
        size is mapped to the nearest supported aspect ratio.
    output_dir : str or Path
        Directory to save generated videos.
    num_frames : int
        Agnes only — number of frames.  Must be <= 441 and satisfy ``8n + 1``
        (e.g. 81, 121, 241).  Default from ``VIDEO_NUM_FRAMES`` env.
        Ignored by Gemini (Veo uses ``GEMINI_VIDEO_DURATION`` seconds).
    frame_rate : float
        Agnes only — frame rate in FPS (1–60).  Default from
        ``VIDEO_FRAME_RATE`` env.  Ignored by Gemini.

    Returns
    -------
    list[dict]
        Each dict has ``index``, ``title``, ``file_path``, ``url``,
        ``prompt``, and ``video_id`` keys.
    """
    if VIDEO_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is not set (required by VIDEO_PROVIDER=gemini). "
                "Set it in skills/.env or as an environment variable."
            )
        from scripts.gemini import gemini_generate_videos

        return gemini_generate_videos(
            segments,
            size=size,
            output_dir=output_dir,
            name=name,
        )

    if VIDEO_PROVIDER != "agnes":
        raise RuntimeError(
            f"Unknown VIDEO_PROVIDER '{VIDEO_PROVIDER}'. Supported: agnes, gemini."
        )

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
    # Phase 1 — Submit all video generation requests in batch
    # ------------------------------------------------------------------
    pending: dict[str, dict] = {}          # video_id → {index, title} for polling
    video_meta: dict[str, dict] = {}       # video_id → {index, title, prompt, file_path}
    submit_errors: dict[int, dict] = {}    # index → result (skipped / failed submit)

    for seg in sorted_segments:
        idx = seg["index"]
        title = seg["title"]
        prompt = seg["video_prompt"]

        try:
            video_id = _submit_one_video_agnes(prompt, width, height, num_frames, frame_rate)
            logger.info("[%d/%d] Video created: %s", idx + 1, total, video_id)
            pending[video_id] = {"index": idx, "title": title}
            video_meta[video_id] = {
                "index": idx, "title": title, "prompt": prompt,
                "file_path": out / build_filename(name, seg.get("slug"), idx, ".mp4"),
            }
            time.sleep(0.5)  # brief pause between submissions to avoid rate limits

        except Exception as exc:
            logger.error("[%d/%d] Failed to submit video generation: %s", idx + 1, total, exc)
            submit_errors[idx] = {
                "index": idx, "title": title, "file_path": None,
                "url": None, "prompt": prompt, "video_id": None,
                "error": f"Video submission failed: {exc}",
            }

    logger.info(
        "Submitted %d videos, %d skipped → now polling all concurrently",
        len(pending), len(submit_errors),
    )

    # ------------------------------------------------------------------
    # Phase 2 — Poll all videos concurrently; download each video IMMEDIATELY
    #           as soon as it completes (no waiting for slow videos)
    # ------------------------------------------------------------------
    final_results: list[dict] = []

    def _download_on_complete(vid: str, data: dict) -> None:
        """Called as soon as a video completes — download the video now."""
        meta = video_meta.get(vid)
        if not meta:
            return
        idx = meta["index"]
        file_path = meta["file_path"]
        title = meta["title"]
        prompt = meta["prompt"]

        try:
            url = _download_video_completed(vid, data, file_path)
            if not url:
                logger.warning("[%d] No video URL for video %s", idx, vid)
                final_results.append({
                    "index": idx, "title": title, "file_path": None,
                    "url": None, "prompt": prompt, "video_id": vid,
                    "error": "No video URL in completed response",
                })
                return
            final_results.append({
                "index": idx, "title": title, "file_path": str(file_path.resolve()),
                "url": url, "prompt": prompt, "video_id": vid,
            })
        except Exception as exc:
            logger.error("[%d] Video download failed: %s", idx, exc)
            final_results.append({
                "index": idx, "title": title, "file_path": None,
                "url": None, "prompt": prompt, "video_id": vid,
                "error": f"Video download failed: {exc}",
            })


    _completed_data, failed_data = _poll_all_videos(
        pending, VIDEO_POLL_TIMEOUT, VIDEO_POLL_INTERVAL,
        on_completed=_download_on_complete,
    )

    for video_id, error in failed_data.items():
        meta = video_meta.get(video_id)
        if meta:
            submit_errors[meta["index"]] = {
                "index": meta["index"],
                "title": meta["title"],
                "file_path": None, "url": None,
                "prompt": meta["prompt"],
                "video_id": video_id,
                "error": error,
            }

    # Merge submit and polling errors
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
# Batch video generation
# ---------------------------------------------------------------------------

