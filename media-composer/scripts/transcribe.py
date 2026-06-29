"""
Speech-to-text transcription via local MLX Whisper or cloud ASR APIs.

MLX Whisper is the default backend — it runs natively on Apple Silicon with
excellent performance per watt.  whisper.cpp + CoreML is available as an
alternative for high-throughput scenarios.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

from scripts.common import logger

# ---------------------------------------------------------------------------
# Backend registry
# ---------------------------------------------------------------------------

# Each backend is a callable: (audio_path: Path, model: str, language: str | None) -> list[dict]
# where each dict has {"start": float, "end": float, "text": str}
_BACKENDS: dict[str, callable] = {}


def _register(name: str):
    """Decorator: register a transcription backend."""
    def dec(fn):
        _BACKENDS[name] = fn
        return fn
    return dec


# ---------------------------------------------------------------------------
# MLX Whisper backend (default)
# ---------------------------------------------------------------------------

@_register("mlx-whisper")
def _transcribe_mlx(audio_path: Path, model: str, language: str | None) -> list[dict]:
    """Transcribe using MLX Whisper (Apple Silicon native)."""
    import mlx_whisper

    logger.info("Loading MLX Whisper model '%s'...", model)
    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=f"mlx-community/whisper-{model}",
        language=language,
        verbose=False,
    )

    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip(),
        })
    return segments


# ---------------------------------------------------------------------------
# whisper.cpp backend
# ---------------------------------------------------------------------------

@_register("whisper-cpp")
def _transcribe_whisper_cpp(audio_path: Path, model: str, language: str | None) -> list[dict]:
    """Transcribe using whisper.cpp CLI.

    Requires a pre-built ``whisper-cli`` binary and downloaded GGML model.
    The binary is searched on PATH; the model is expected at
    ``~/whisper-models/ggml-<model>.bin``.
    """
    binary = "whisper-cli"
    model_path = Path.home() / "whisper-models" / f"ggml-{model}.bin"

    if not model_path.exists():
        raise FileNotFoundError(
            f"whisper.cpp model not found: {model_path}\n"
            f"Download from https://huggingface.co/ggerganov/whisper.cpp"
        )

    cmd = [binary, "-m", str(model_path), "-f", str(audio_path), "-oj"]
    if language:
        cmd.extend(["-l", language])

    logger.info("Running whisper.cpp: %s", " ".join(str(c) for c in cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        raise RuntimeError(f"whisper.cpp failed: {proc.stderr}")

    # whisper.cpp -oj outputs a JSON file alongside the input
    json_path = audio_path.with_suffix(".json")
    if not json_path.exists():
        # Try current directory
        json_path = Path(audio_path.name).with_suffix(".json")

    data = json.loads(json_path.read_text())
    segments = []
    for seg in data.get("transcription", []):
        timestamps = seg.get("timestamps", {})
        segments.append({
            "start": round(float(timestamps.get("from", "0").replace("ms", "")) / 1000, 2),
            "end": round(float(timestamps.get("to", "0").replace("ms", "")) / 1000, 2),
            "text": seg.get("text", "").strip(),
        })
    return segments


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transcribe(
    audio_path: str | Path,
    model: str = "turbo",
    language: str | None = None,
    backend: str = "mlx-whisper",
    output_format: str = "md",
) -> str:
    """Transcribe an audio/video file to text.

    Parameters
    ----------
    audio_path : str or Path
        Path to the audio or video file (any format ffmpeg can read).
    model : str
        Whisper model size/name.  Default: ``"turbo"``.
        MLX Whisper models: ``tiny``, ``small``, ``medium``, ``large-v3``,
        ``large-v3-turbo``, ``turbo``.
    language : str or None
        Language code (e.g. ``"zh"``, ``"en"``).  Auto-detect when ``None``.
    backend : str
        Backend to use.  One of ``"mlx-whisper"``, ``"whisper-cpp"``.
        Default: ``"mlx-whisper"``.
    output_format : str
        Output format.  ``"md"`` (Markdown with timestamps as headings),
        ``"txt"`` (plain text), ``"json"`` (raw segments JSON).
        Default: ``"md"``.

    Returns
    -------
    str
        Formatted transcription text.
    """
    path = Path(audio_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    if backend not in _BACKENDS:
        raise ValueError(
            f"Unknown backend '{backend}'. Available: {sorted(_BACKENDS.keys())}"
        )

    logger.info("Transcribing %s with backend=%s model=%s...", path.name, backend, model)

    segments = _BACKENDS[backend](path, model=model, language=language)

    if not segments:
        logger.warning("No speech detected in %s", path.name)
        return "" if output_format == "txt" else "*No speech detected.*"

    # Format output
    if output_format == "json":
        return json.dumps({"segments": segments}, ensure_ascii=False, indent=2)

    if output_format == "txt":
        return "\n\n".join(seg["text"] for seg in segments)

    # md — default: format with timestamps
    lines = ["# Transcription\n"]
    for seg in segments:
        ts = f"{_fmt_time(seg['start'])} – {_fmt_time(seg['end'])}"
        lines.append(f"## {ts}")
        lines.append("")
        lines.append(seg["text"])
        lines.append("")

    return "\n".join(lines)


def _fmt_time(seconds: float) -> str:
    """Format seconds as MM:SS."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"
