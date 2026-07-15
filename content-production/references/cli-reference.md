# Content-Production CLI Reference

Full argument reference for every `content-production` CLI subcommand. Loaded on demand — the
[SKILL.md](../SKILL.md) overview has the core run commands and the trigger decision tree; this file
holds the detailed flag tables and configuration.

Run from this skill's directory, calling the shared skills virtualenv directly (no `cd` / `activate`):

```bash
../.venv/bin/python scripts/cli.py <subcommand> [flags]
```

`scripts/cli.py` locates `../.env` (API keys) automatically relative to its own location, following
symlinks — no manual env setup is needed. If you prefer, `source ../.venv/bin/activate` first and
then the bare `python scripts/cli.py …` examples below work as-is.

## Contents

- [image](#image) — generate PNG images from `image_prompt`
- [video](#video) — generate MP4 videos from `video_prompt`
- [speech](#speech) — generate MP3 audio from `text`
- [extract](#extract) — DOCX/PDF → plain text (`.txt`)
- [convert](#convert) — DOCX → structured Markdown (`.md`)
- [Configuration](#configuration) — env vars and defaults

---

## image

Generate images from a segments JSON. Saved as `000.png`, `001.png`, … in index order.

```bash
# Default size 1024x768
python scripts/cli.py image -i segments.json -o images/

# Custom size
python scripts/cli.py image -i segments.json -o images/ --size 512x512
```

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Path to segments JSON file | (required) |
| `--output` | `-o` | Output directory | `output/` |
| `--size` | | Image size `WxH` (e.g. `512x512`) | `1024x768` |
| `--prompt-key` | | Segment key for the image prompt | `image_prompt` |

---

## video

Generate videos from a segments JSON. Saved as `000.mp4`, `001.mp4`, … in index order.

```bash
python scripts/cli.py video -i segments.json -o videos/ --size 1152x768 --num-frames 121 --frame-rate 24
```

Generation is asynchronous — each video is submitted, polled until complete (up to 15 min timeout),
then downloaded. The JSON output includes a `video_id` per result (Agnes video ID or Veo operation
name). With `VIDEO_PROVIDER=gemini`, `--num-frames` / `--frame-rate` are ignored (Veo uses
`GEMINI_VIDEO_DURATION` seconds) and `--size` maps to the nearest aspect ratio (16:9 / 9:16).

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Path to segments JSON file | (required) |
| `--output` | `-o` | Output directory | `output/` |
| `--size` | | Video size `WxH` (e.g. `1152x768`) | `1152x768` |
| `--num-frames` | | Number of frames (≤ 441, of form 8n+1) | `121` |
| `--frame-rate` | | Frame rate in FPS (1–60) | `24` |
| `--prompt-key` | | Segment key for the video prompt | `video_prompt` |

---

## speech

Generate speech audio from a segments JSON, using each segment's `text` field as the content.
Saved as `000.mp3`, `001.mp3`, … in index order (`SPEECH_PROVIDER=gemini` saves 24 kHz WAV:
`000.wav`, `001.wav`, …).

```bash
python scripts/cli.py speech -i segments.json -o audio/
```

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Path to segments JSON file | (required) |
| `--output` | `-o` | Output directory | `output/` |

Speech generation uses the segment's `text` field as the speech content.

---

## extract

Extract **plain text** (no formatting) from DOCX/PDF → `.txt`. Supports partial ranges.

```bash
# Full document
python scripts/cli.py extract -i report.docx -o report.txt
python scripts/cli.py extract -i paper.pdf -o paper.txt

# Partial range (1-indexed, inclusive): paragraphs for DOCX, pages for PDF
python scripts/cli.py extract -i paper.pdf --range 2-5 -o excerpt.txt

# Print to stdout instead of writing a file
python scripts/cli.py extract -i report.docx
```

Extract dumps raw text — no formatting is preserved. (PPTX/XLSX support is planned.)

> **For a plain-text dump, try environment tools first** — `textutil` for `.docx` on macOS, `pdftotext`
> for `.pdf` (if poppler is installed). Reach for `extract` only when those are unavailable, you need
> `--range`, or you need cross-platform portability. **Never `pip install` outside the skills venv.**

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Path to source document (docx, pdf) | (required) |
| `--output` | `-o` | Output `.txt` file | (stdout) |
| `--range` | | 1-indexed inclusive range: `N`, `N-M`, `N-`, `-M` | (whole doc) |
| `--format` | | Force input format | (from extension) |

---

## convert

Convert DOCX to **structured Markdown** (`.md`), preserving headings, lists, bold/italic, and tables.

```bash
python scripts/cli.py convert -i report.docx -o report.md
```

DOCX uses python-docx (precise style mapping) with a mammoth fallback for corrupted/non-compliant XML.
(PPTX support is planned.)

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Path to source document (docx) | (required) |
| `--output` | `-o` | Output `.md` file | (stdout) |
| `--format` | | Force input format | (from extension) |

---

## Configuration

All keys, providers, models, and defaults come from the shared `skills/.env` (one level above this
skill). The CLI reads it automatically — no manual env setup. Switching provider requires **no CLI
changes** — set the `*_PROVIDER` variable and re-run the same command.

### Provider switches

| Variable | Options | Default |
|----------|---------|---------|
| `IMAGE_PROVIDER` | `agnes` \| `gemini` | `agnes` |
| `VIDEO_PROVIDER` | `agnes` \| `gemini` | `agnes` |
| `SPEECH_PROVIDER` | `siliconflow` \| `gemini` | `siliconflow` |

### Agnes AI / SiliconFlow

| Variable | Description | Default |
|----------|-------------|---------|
| `IMAGE_API_KEY` | Agnes AI API key | (from .env) |
| `IMAGE_BASE_URL` | Agnes AI API base URL | `https://apihub.agnes-ai.com` |
| `IMAGE_MODEL` | Image generation model | `agnes-image-2.1-flash` |
| `IMAGE_SIZE` | Default image size (WxH) | `1024x768` |
| `VIDEO_API_KEY` | Agnes AI API key | (from .env) |
| `VIDEO_BASE_URL` | Agnes AI API base URL | `https://apihub.agnes-ai.com` |
| `VIDEO_MODEL` | Video generation model | `agnes-video-v2.0` |
| `VIDEO_SIZE` | Default video size (WxH) | `1152x768` |
| `VIDEO_NUM_FRAMES` | Default number of frames (≤ 441, 8n+1) | `121` |
| `VIDEO_FRAME_RATE` | Default frame rate in FPS (1–60) | `24` |
| `SPEECH_API_KEY` | SiliconFlow API key | (from .env) |
| `SPEECH_BASE_URL` | SiliconFlow API base URL | `https://api.siliconflow.com/v1` |
| `SPEECH_MODEL` | Speech generation model | `fishaudio/fish-speech-1.5` |
| `SPEECH_VOICE` | Speech voice preset | `fishaudio/fish-speech-1.5:anna` |

### Gemini (Google AI)

One `GEMINI_API_KEY` is shared by all three capabilities. Image and speech use the Interactions
API (`POST /v1beta/interactions`, GA); video uses the Veo long-running-operations flow.

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Gemini API key (shared: image / video / speech) | (from .env) |
| `GEMINI_BASE_URL` | Gemini API base URL | `https://generativelanguage.googleapis.com/v1beta` |
| `GEMINI_IMAGE_MODEL` | Image model — Nano Banana 2 (Imagen is deprecated) | `gemini-3.1-flash-image` |
| `GEMINI_IMAGE_SIZE` | Image resolution: `1K` / `2K` / `4K` | `1K` |
| `GEMINI_VIDEO_MODEL` | Video model — Veo 3.1 (`veo-3.1-lite-generate-preview` for lower cost) | `veo-3.1-generate-preview` |
| `GEMINI_VIDEO_DURATION` | Video length in seconds: `4` / `6` / `8` | `8` |
| `GEMINI_VIDEO_RESOLUTION` | Video resolution: `720p` / `1080p` / `4k` (1080p+ requires 8s) | `720p` |
| `GEMINI_VIDEO_CONCURRENCY` | Max in-flight Veo operations (sliding window; HTTP 429 re-queues with cooldown) | `4` |
| `GEMINI_TTS_MODEL` | TTS model | `gemini-3.1-flash-tts-preview` |
| `GEMINI_TTS_VOICE` | Prebuilt voice (Kore, Puck, Zephyr, Charon, …30 voices) | `Kore` |

**Gemini provider notes:**

- The CLI `--size WxH` is mapped to the **nearest supported aspect ratio** (images: 1:1 … 21:9;
  videos: 16:9 / 9:16); exact pixel dimensions are not honored.
- `--num-frames` / `--frame-rate` are Agnes-only and ignored by Veo (use `GEMINI_VIDEO_DURATION`).
- Gemini TTS outputs 24 kHz mono WAV — files are saved as `000.wav`, … (not `.mp3`).
