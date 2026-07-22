"""
Speech audio generation — multi-provider dispatch (SiliconFlow / Gemini).

The provider is selected via ``SPEECH_PROVIDER`` in skills/.env:

- ``siliconflow`` (default) — Fish Speech via the OpenAI-compatible audio
  endpoint, saved as MP3.
- ``gemini`` — Gemini TTS via the Gemini API, PCM output wrapped as WAV.

The segment's ``text`` field is used as the speech content.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from scripts.common import (
    build_filename,
    SPEECH_PROVIDER,
    SPEECH_API_KEY,
    SPEECH_BASE_URL,
    SPEECH_MODEL,
    SPEECH_VOICE,
    GEMINI_API_KEY,
    MAX_RETRIES,
    logger,
)

# ---------------------------------------------------------------------------
# SiliconFlow provider
# ---------------------------------------------------------------------------


def _generate_one_siliconflow(text: str) -> bytes:
    """Generate MP3 speech audio for *text* via SiliconFlow Fish Speech."""
    from openai import OpenAI

    client = OpenAI(api_key=SPEECH_API_KEY, base_url=SPEECH_BASE_URL)
    response = client.audio.speech.create(
        model=SPEECH_MODEL,
        voice=SPEECH_VOICE,
        input=text,
    )
    return response.content if hasattr(response, "content") else response.read()


# ---------------------------------------------------------------------------
# Gemini provider
# ---------------------------------------------------------------------------


def _generate_one_gemini(text: str) -> bytes:
    """Generate WAV speech audio for *text* via Gemini TTS."""
    from scripts.gemini import gemini_generate_speech

    return gemini_generate_speech(text)


# ---------------------------------------------------------------------------
# Provider dispatch
# ---------------------------------------------------------------------------

# provider → (generate_fn, key_name, key_getter, file_extension)
_PROVIDERS = {
    "siliconflow": (_generate_one_siliconflow, "SPEECH_API_KEY", lambda: SPEECH_API_KEY, ".mp3"),
    "gemini": (_generate_one_gemini, "GEMINI_API_KEY", lambda: GEMINI_API_KEY, ".wav"),
}


def _resolve_provider():
    """Return ``(generate_fn, file_extension)`` for SPEECH_PROVIDER, validating its API key."""
    if SPEECH_PROVIDER not in _PROVIDERS:
        raise RuntimeError(
            f"Unknown SPEECH_PROVIDER '{SPEECH_PROVIDER}'. "
            f"Supported: {', '.join(sorted(_PROVIDERS))}."
        )
    generate_fn, key_name, key_getter, extension = _PROVIDERS[SPEECH_PROVIDER]
    if not key_getter():
        raise RuntimeError(
            f"{key_name} is not set (required by SPEECH_PROVIDER={SPEECH_PROVIDER}). "
            "Set it in skills/.env or as an environment variable."
        )
    return generate_fn, extension


# ---------------------------------------------------------------------------
# Batch speech generation
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Single speech generation
# ---------------------------------------------------------------------------


def generate_one_speech(
    text: str,
    output_path: str | Path | None = None,
) -> dict:
    """Generate speech audio for *text* and save to *output_path*.

    The provider is selected by ``SPEECH_PROVIDER``.

    Parameters
    ----------
    text : str
        Text to synthesize.
    output_path : str or Path or None
        Where to save the audio file.  If ``None``, uses a default
        filename based on the provider's extension (``output.mp3`` or
        ``output.wav``).

    Returns
    -------
    dict
        ``file_path`` (str or None), ``prompt`` (str).
    """
    generate_fn, extension = _resolve_provider()

    out = Path(output_path or f"output{extension}")
    out.parent.mkdir(parents=True, exist_ok=True)

    saved = False

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Generating speech via %s (attempt %d/%d)...",
                SPEECH_PROVIDER, attempt, MAX_RETRIES,
            )
            audio_bytes = generate_fn(text)

            if len(audio_bytes) < 1000:
                logger.warning("Audio too small (%d bytes), retrying", len(audio_bytes))
                continue

            out.write_bytes(audio_bytes)
            saved = True
            logger.info("Saved %s (%d bytes)", out.name, len(audio_bytes))
            break

        except Exception as exc:
            logger.warning("Attempt %d failed: %s", attempt, exc)
            if attempt < MAX_RETRIES:
                time.sleep(2)

    return {
        "file_path": str(out.resolve()) if saved else None,
        "prompt": text,
    }



def generate_speech(
    segments: list[dict],
    name: str | None = None,
    output_dir: str | Path = "output",
) -> list[dict]:
    """Generate speech audio for each segment via the configured provider.

    The provider is selected by ``SPEECH_PROVIDER`` (siliconflow / gemini).
    Audio files are saved to *output_dir*.  File naming uses the optional
    top-level ``name`` and segment-level ``slug`` values, falling back to
    ``{index:03d}`` + extension when neither is set.

    Uses the segment's ``text`` field as the speech content.

    Parameters
    ----------
    segments : list[dict]
        Validated media segments with ``index``, ``title``, and ``text``.
    name : str or None
        Optional top-level project name for filename prefixes (kebab-case).
    output_dir : str or Path
        Directory to save generated audio files.

    Returns
    -------
    list[dict]
        Each dict has ``index``, ``title``, ``file_path``, ``prompt`` keys.
    """
    _, extension = _resolve_provider()

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    results = []
    total = len(segments)

    for seg in segments:
        idx = seg["index"]
        title = seg["title"]
        speech_text = seg["text"].strip()

        file_path = out / build_filename(name, seg.get("slug"), idx, extension)
        logger.info("[%d/%d] Generating speech for '%s'...", idx + 1, total, title)

        result = generate_one_speech(speech_text, file_path)
        if result["file_path"]:
            results.append({
                "index": idx,
                "title": title,
                **result,
            })
        else:
            logger.error("[%d/%d] All %d attempts failed", idx + 1, total, MAX_RETRIES)
            results.append({
                "index": idx, "title": title, "file_path": None,
                "prompt": speech_text, "error": f"All {MAX_RETRIES} attempts failed",
            })

    succeeded = sum(1 for r in results if r.get("file_path"))
    logger.info("Done: %d/%d speech files generated → %s", succeeded, total, out.resolve())
    return results
# Single speech generation
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------

