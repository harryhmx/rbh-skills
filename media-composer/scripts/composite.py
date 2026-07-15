"""
composite — burn still image + audio pairs into MP4 video segments.

Images and audio files are paired by filename sort order (first with first,
and so on); each pair becomes one ``{index:03d}.mp4``.  Migrated from the
retired video-converter skill.
"""

from __future__ import annotations

from pathlib import Path

from scripts.common import logger, resolve_ffmpeg, run

_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})
_AUDIO_EXTS = frozenset({".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"})


def composite_videos(
    image_dir: str | Path,
    audio_dir: str | Path,
    output_dir: str | Path = "output",
) -> list[dict]:
    """Pair images and audio by sort order; composite each pair into an MP4.

    Processing stops when either list is exhausted.  Entries with
    ``"output": None`` indicate a failed composite.
    """
    src_images = Path(image_dir)
    src_audio = Path(audio_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

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

    ffmpeg = resolve_ffmpeg()
    results = []
    for idx in range(total):
        img_path, aud_path = images[idx], audios[idx]
        out_path = out / f"{idx:03d}.mp4"
        logger.info(
            "[%d/%d] %s + %s → %s",
            idx + 1, total, img_path.name, aud_path.name, out_path.name,
        )
        try:
            run([
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-loop", "1", "-i", str(img_path),
                "-i", str(aud_path),
                "-c:v", "libx264", "-tune", "stillimage",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-shortest", "-movflags", "+faststart",
                str(out_path),
            ])
            size = out_path.stat().st_size
            logger.info("[%d/%d] Done — %s (%d bytes)", idx + 1, total, out_path.name, size)
            results.append({
                "index": idx,
                "image": str(img_path.resolve()),
                "audio": str(aud_path.resolve()),
                "output": str(out_path.resolve()),
                "size_bytes": size,
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
