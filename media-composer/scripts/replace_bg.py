"""
replace-bg — replace a talking-head video's background via RVM matting.

Pipeline (all in-process, no temp frame dumps):

    ffmpeg decode  --stdout-->  raw RGB frames
            |
        Python reads frame chunks, runs Robust Video Matting on MPS (or CPU)
        with carried temporal recurrence, alpha-composites the foreground onto
        a background image, and writes raw RGB frames to a second ffmpeg.
            |
    ffmpeg encode <--stdin---   H.264 silent video

The silent output is then muxed with the source audio in a final step.

Design notes:
  * Frames travel as raw rgb24 bytes through OS pipes (backpressure-safe: the
    decode process simply pauses when its stdout buffer fills during inference).
  * The model is fed chunked frame batches ([B,T,C,H,W]) to amortise Python
    overhead, but recurrence state is carried chunk-to-chunk so temporal
    consistency is preserved across the whole video.
  * Edges are refined to full resolution by RVM's default DeepGuidedFilter.

Dependencies: torch (+ torchvision for the resnet50 backbone).  The
checkpoint lives in ``../models/`` (gitignored) — run
``python scripts/download_models.py`` on first use.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from scripts.common import (
    MODELS_DIR,
    auto_downsample_ratio,
    logger,
    probe_video,
    resolve_ffmpeg,
    run,
)


def _read_exact(stream, n: int) -> bytes:
    """Read exactly *n* bytes from *stream*, returning fewer only at EOF."""
    buf = bytearray()
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            break
        buf.extend(chunk)
    return bytes(buf)


def replace_bg(
    input_path: str | Path,
    bg_path: str | Path,
    output_path: str | Path,
    variant: str = "resnet50",
    checkpoint: str | Path | None = None,
    chunk: int = 8,
    downsample_ratio: float | None = None,
    crf: int = 18,
) -> dict:
    """Matte the person out of *input_path* and composite onto *bg_path*.

    Produces *output_path* with the source audio muxed back in.
    ``variant='mobilenetv3'`` is lighter (and avoids the torchvision
    dependency of the resnet50 backbone).
    """
    import torch
    from PIL import Image

    from scripts.rvm import MattingNetwork

    src = Path(input_path)
    bg_file = Path(bg_path)
    out = Path(output_path)
    if not bg_file.exists():
        raise FileNotFoundError(f"Background image not found: {bg_file}")

    ckpt = Path(checkpoint) if checkpoint else MODELS_DIR / f"rvm_{variant}.pth"
    if not ckpt.exists():
        raise FileNotFoundError(
            f"RVM checkpoint not found: {ckpt}\n"
            f"Run: python scripts/download_models.py rvm_{variant}.pth"
        )

    info = probe_video(src)
    w, h, fps = info["width"], info["height"], info["fps"]
    if not w:
        raise ValueError(f"No video stream in {src}")
    fps = fps or 30.0

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    if device == "cpu":
        logger.warning("MPS unavailable — falling back to CPU (will be slow)")

    dsr = downsample_ratio if downsample_ratio else auto_downsample_ratio(h, w)
    logger.info(
        "replace-bg: %s %dx%d @ %.3ffps, %s on %s, downsample %.4f, chunk %d",
        src.name, w, h, fps, variant, device, dsr, chunk,
    )

    # Background as [1,1,3,H,W] on device (resized to frame)
    bg_img = Image.open(bg_file).convert("RGB").resize((w, h))
    import numpy as np

    bg = (
        torch.from_numpy(np.asarray(bg_img).copy())
        .to(device).float().div_(255)
        .permute(2, 0, 1).unsqueeze(0).unsqueeze(0)
    )

    logger.info("Loading %s checkpoint...", variant)
    model = MattingNetwork(variant).eval().to(device)
    model.load_state_dict(
        torch.load(ckpt, map_location=device, weights_only=True), strict=True
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    silent = out.with_name(out.stem + ".silent.mp4")
    ffmpeg = resolve_ffmpeg()

    frame_bytes = w * h * 3
    decode = subprocess.Popen(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error",
            "-i", str(src),
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-an", "-",
        ],
        stdout=subprocess.PIPE,
    )
    encode = subprocess.Popen(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{w}x{h}", "-r", f"{fps}",
            "-i", "pipe:0",
            "-c:v", "libx264", "-crf", str(crf),
            "-preset", "medium", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(silent),
        ],
        stdin=subprocess.PIPE,
    )

    rec = [None, None, None, None]  # RVM temporal recurrence, carried chunk-to-chunk
    processed = 0
    t0 = time.time()
    last_report = t0
    try:
        with torch.no_grad():
            while True:
                frames = []
                for _ in range(chunk):
                    raw = _read_exact(decode.stdout, frame_bytes)
                    if not raw:
                        break
                    frames.append(raw)
                if not frames:
                    break

                src_t = torch.frombuffer(bytearray(b"".join(frames)), dtype=torch.uint8)
                src_t = src_t.view(len(frames), h, w, 3).permute(0, 3, 1, 2).contiguous()
                src_t = src_t.to(device).float().div_(255).unsqueeze(0)  # [1,T,3,H,W]

                fgr, pha, *rec = model(src_t, *rec, downsample_ratio=dsr)
                comp = (fgr * pha + bg * (1 - pha)).clamp(0, 1)

                out_t = comp[0].cpu().mul_(255).round_().to(torch.uint8)
                out_t = out_t.permute(0, 2, 3, 1).contiguous().numpy()  # [T,H,W,3]
                encode.stdin.write(out_t.tobytes())

                processed += len(frames)
                now = time.time()
                if now - last_report >= 2.0:
                    logger.info("  %d frames (%.1f fps)", processed, processed / (now - t0))
                    last_report = now
    finally:
        if decode.stdout:
            decode.stdout.close()
        encode.stdin.close()
        decode.wait()
        encode.wait()

    if encode.returncode not in (0, None):
        silent.unlink(missing_ok=True)
        raise RuntimeError(f"Encoder failed (code {encode.returncode})")

    elapsed = time.time() - t0
    logger.info(
        "Matting done: %d frames in %.1fs (%.2f fps)", processed, elapsed,
        processed / max(elapsed, 1e-9),
    )

    # Mux the source audio back onto the silent video
    try:
        if info["has_audio"]:
            run([
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(silent), "-i", str(src),
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                "-shortest", "-movflags", "+faststart",
                str(out),
            ])
            silent.unlink(missing_ok=True)
        else:
            silent.rename(out)
    except Exception:
        silent.unlink(missing_ok=True)
        raise

    return {
        "input": str(src.resolve()),
        "background": str(bg_file.resolve()),
        "output": str(out.resolve()),
        "frames": processed,
        "matting_fps": round(processed / max(elapsed, 1e-9), 2),
        "duration": round(probe_video(out)["duration"], 3),
    }
