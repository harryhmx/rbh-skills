"""
Speech audio generation via SiliconFlow Fish Speech.

Uses the OpenAI-compatible audio endpoint to generate MP3 speech from text.
The segment's ``text`` field is used as the speech content.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from openai import OpenAI

from scripts.common import (
    SPEECH_API_KEY,
    SPEECH_BASE_URL,
    SPEECH_MODEL,
    SPEECH_VOICE,
    MAX_RETRIES,
    logger,
)


def generate_speech(
    segments: list[dict],
    output_dir: str | Path = "output",
) -> list[dict]:
    """Generate speech audio for each segment using SiliconFlow Fish Speech.

    Audio files are saved to *output_dir* as ``{index:03d}.mp3``.

    Uses the segment's ``text`` field as the speech content.

    Parameters
    ----------
    segments : list[dict]
        Segments from :func:`common.load_segments_json`.  Each should have ``index``,
        ``title``, and ``text``.
    output_dir : str or Path
        Directory to save generated audio files.

    Returns
    -------
    list[dict]
        Each dict has ``index``, ``title``, ``file_path``, ``prompt`` keys.
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

        # Speech content comes from the "text" field
        speech_text = seg.get("text", "").strip()

        if not speech_text:
            logger.warning("[%d/%d] No text for segment %d, skipping", idx + 1, total, idx)
            results.append({
                "index": idx, "title": title, "file_path": None,
                "prompt": "", "error": "No 'text' field",
            })
            continue

        file_path = out / f"{idx:03d}.mp3"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "[%d/%d] Generating speech for '%s' (attempt %d/%d)...",
                    idx + 1, total, title, attempt, MAX_RETRIES,
                )

                response = client.audio.speech.create(
                    model=SPEECH_MODEL,
                    voice=SPEECH_VOICE,
                    input=speech_text,
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
                    "prompt": speech_text,
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
                "prompt": speech_text, "error": f"All {MAX_RETRIES} attempts failed",
            })

    succeeded = sum(1 for r in results if r.get("file_path"))
    logger.info("Done: %d/%d speech files generated → %s", succeeded, total, out.resolve())
    return results
