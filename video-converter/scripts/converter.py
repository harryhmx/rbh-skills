"""
Video Converter — composite still images + audio into MP4 video segments.

Pure local processing via ffmpeg subprocess — no AI/API calls needed.
Each image+audio pair is burned into a single video segment.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported file extensions
# ---------------------------------------------------------------------------

_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})
_AUDIO_EXTS = frozenset({".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"})
_VIDEO_EXTS = frozenset({".mp4", ".mov", ".avi", ".mkv", ".webm"})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def composite_videos(
    image_dir: str | Path,
    audio_dir: str | Path,
    output_dir: str | Path = "output",
) -> list[dict]:
    """Pair images and audio by filename sort order, composite each into an MP4 video.

    Files in *image_dir* and *audio_dir* are sorted alphabetically by name.
    The first image is paired with the first audio, the second with the second,
    and so on.  Processing stops when either list is exhausted.

    Each pair is burned into an MP4 via ffmpeg::

        ffmpeg -loop 1 -i <image> -i <audio> -c:v libx264 -tune stillimage \\
               -c:a aac -b:a 192k -pix_fmt yuv420p -shortest -y <output>.mp4

    Parameters
    ----------
    image_dir : str or Path
        Directory containing image files (PNG, JPG, etc.).
    audio_dir : str or Path
        Directory containing audio files (MP3, WAV, etc.).
    output_dir : str or Path
        Directory to write MP4 video files, named ``{index:03d}.mp4``.

    Returns
    -------
    list[dict]
        Each dict has ``index``, ``image``, ``audio``, ``output`` keys.
        Entries with ``"output": None`` indicate a failed composite.
    """
    src_images = Path(image_dir)
    src_audio = Path(audio_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # ---- collect & sort files ----
    images = sorted(
        p for p in src_images.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTS
    )
    audios = sorted(
        p for p in src_audio.iterdir()
        if p.is_file() and p.suffix.lower() in _AUDIO_EXTS
    )

    if not images:
        raise ValueError(f"No image files found in {src_images.resolve()}")
    if not audios:
        raise ValueError(f"No audio files found in {src_audio.resolve()}")

    total = min(len(images), len(audios))
    logger.info(
        "Found %d images + %d audio → %d pairs to composite",
        len(images), len(audios), total,
    )

    # ---- composite each pair ----
    results = []
    for idx in range(total):
        img_path = images[idx]
        aud_path = audios[idx]
        out_path = out / f"{idx:03d}.mp4"

        logger.info(
            "[%d/%d] %s + %s → %s",
            idx + 1, total, img_path.name, aud_path.name, out_path.name,
        )

        try:
            _run_ffmpeg(img_path, aud_path, out_path)
            file_size = out_path.stat().st_size
            logger.info("[%d/%d] Done — %s (%d bytes)", idx + 1, total, out_path.name, file_size)

            results.append({
                "index": idx,
                "image": str(img_path.resolve()),
                "audio": str(aud_path.resolve()),
                "output": str(out_path.resolve()),
                "size_bytes": file_size,
            })
        except Exception as exc:
            logger.error("[%d/%d] Failed: %s", idx + 1, total, exc)
            results.append({
                "index": idx,
                "image": str(img_path.resolve()),
                "audio": str(aud_path.resolve()),
                "output": None,
                "error": str(exc),
            })

    succeeded = sum(1 for r in results if r.get("output"))
    logger.info("Done: %d/%d videos composited → %s", succeeded, total, out.resolve())
    return results


def concat_videos(
    video_dir: str | Path,
) -> dict:
    """Concatenate all video files in *video_dir* into a single MP4.

    Video files are sorted alphabetically by name and concatenated in order
    via ffmpeg's concat demuxer (stream copy — no re-encoding).

    The output file is named ``<video_dir>.mp4`` and placed in the **parent**
    directory of *video_dir*.

    Parameters
    ----------
    video_dir : str or Path
        Directory containing video files (MP4, etc.).

    Returns
    -------
    dict
        With keys ``input_dir``, ``input_count``, ``output``, ``size_bytes``.
    """
    import tempfile

    src = Path(video_dir).resolve()
    if not src.is_dir():
        raise ValueError(f"Not a directory: {src}")

    # ---- collect & sort files ----
    videos = sorted(
        p for p in src.iterdir()
        if p.is_file() and p.suffix.lower() in _VIDEO_EXTS
    )
    if not videos:
        raise ValueError(f"No video files found in {src}")

    # Output: <parent>/<dirname>.mp4
    out_path = src.parent / f"{src.name}.mp4"

    logger.info(
        "Concatenating %d video files → %s", len(videos), out_path.name,
    )

    # ---- build concat file list ----
    file_list = "\n".join(f"file '{v.resolve()}'" for v in videos)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", prefix="video-concat-", delete=False,
    ) as fh:
        fh.write(file_list)
        list_path = fh.name

    try:
        _run_ffmpeg_concat(list_path, out_path)
        file_size = out_path.stat().st_size
        logger.info("Done — %s (%d bytes)", out_path.name, file_size)
    finally:
        Path(list_path).unlink(missing_ok=True)

    return {
        "input_dir": str(src),
        "input_count": len(videos),
        "output": str(out_path.resolve()),
        "size_bytes": out_path.stat().st_size,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_ffmpeg(
    image: Path,
    audio: Path,
    output: Path,
    *,
    video_codec: str = "libx264",
    audio_codec: str = "aac",
    audio_bitrate: str = "192k",
) -> None:
    """Run ffmpeg to composite *image* + *audio* into *output*.

    Raises :exc:`subprocess.CalledProcessError` on non-zero exit.
    """
    cmd = [
        "ffmpeg",
        "-loop", "1",
        "-i", str(image),
        "-i", str(audio),
        "-c:v", video_codec,
        "-tune", "stillimage",
        "-c:a", audio_codec,
        "-b:a", audio_bitrate,
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-y",
        "-loglevel", "error",
        str(output),
    ]

    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _run_ffmpeg_concat(
    file_list: str,
    output: Path,
) -> None:
    """Run ffmpeg concat demuxer to join videos listed in *file_list*.

    Uses stream copy (``-c copy``) — fast and lossless, but all source files
    must share the same codecs and encoding parameters.

    Raises :exc:`subprocess.CalledProcessError` on non-zero exit.
    """
    cmd = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", file_list,
        "-c", "copy",
        "-y",
        "-loglevel", "error",
        str(output),
    ]

    subprocess.run(cmd, check=True, capture_output=True, text=True)
