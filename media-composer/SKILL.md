---
name: media-composer
description: "Media editing toolkit — transcribe audio/video to text (STT via MLX Whisper), overlay captions onto images, trim/crop videos, extract audio tracks, replace segments, enhance video quality, burn subtitles, stitch images, and concatenate videos. Deterministic ffmpeg + Pillow operations. Use when asked to 'transcribe audio', 'convert speech to text', 'caption an image', 'overlay text on an image', 'trim video', 'extract audio from video', 'enhance video', 'burn subtitles', 'stitch images', or 'concatenate videos'."
version: "0.2.0"
allowed-tools: ["Bash", "Read", "Write"]
---

# Media Composer

Deterministic media editing operations — the "hands and feet" of the RBH media pipeline.
All subcommands are local ffmpeg/Pillow operations with no AI model calls (except `transcribe`,
which uses a local MLX Whisper model for STT).

## Quick start

```bash
source ../.venv/bin/activate
python scripts/cli.py transcribe -i recording.m4a -o transcript.md
```

## Subcommands

### v0.1 — transcribe (STT)

Convert speech in audio/video files to text using local Whisper models.

```bash
# Default: MLX Whisper turbo
python scripts/cli.py transcribe -i recording.m4a -o transcript.md

# Custom model and language
python scripts/cli.py transcribe -i recording.m4a --model large-v3-turbo --lang zh

# whisper.cpp backend
python scripts/cli.py transcribe -i recording.m4a --backend whisper-cpp --model large-v3-turbo
```

**CLI arguments (transcribe subcommand):**

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Path to audio/video file | (required) |
| `--output` | `-o` | Output file path | (stdout) |
| `--backend` | | Backend: `mlx-whisper` or `whisper-cpp` | `mlx-whisper` |
| `--model` | | Whisper model size | `turbo` |
| `--lang` | | Language code (e.g. `zh`, `en`) | (auto-detect) |
| `--format` | | Output: `md`, `txt`, or `json` | `md` |

**Backend comparison:**

| Backend | Install | Best for |
|---------|---------|----------|
| `mlx-whisper` | `pip install mlx-whisper` | Daily use, Apple Silicon native, free & unlimited |
| `whisper-cpp` | Build from source + CoreML | High-throughput, Metal + ANE dual acceleration |
| Cloud API (future) | HTTP call | When local models aren't wanted |

### caption — overlay text on images

Draw a semi-transparent banner with centered text across each PNG. Deterministic Pillow operation (migrated here from content-production).

```bash
# Caption images named 000.png, 001.png, ... using a JSON index→title mapping
python scripts/cli.py caption -i titles.json -d images/ -o captioned/

# Force a specific font and size
python scripts/cli.py caption -i titles.json -d images/ --font /path/font.ttc --font-size 48
```

The `-i` JSON may be a segments wrapper (`{"segments": [{index, title, ...}]}`) or a bare list of `{index, title}` objects. Images are matched by `{index:03d}.png`. CJK fonts are auto-detected on macOS/Linux; pass `--font` to override.

**CLI arguments (caption subcommand):**

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | JSON with index→title mapping | (required) |
| `--dir` | `-d` | Directory of `{index:03d}.png` images | (required) |
| `--output` | `-o` | Output directory for captioned images | (overwrites originals) |
| `--font` | | Path to .ttf/.ttc font | (auto-detect CJK) |
| `--font-size` | | Font size in points | `36` |

### v0.2 — ffmpeg editing toolbox (coming soon)

`trim` / `extract-audio` / `replace-segment` / `replace-bg` / `enhance` / `subtitle-burn`

## Dependencies

- `mlx-whisper` (transcribe) — `pip install mlx-whisper`
- `ffmpeg` ≥ 5.0 (system) — audio preprocessing
- `Pillow` (caption; future stitch) — already in skills requirements.txt
