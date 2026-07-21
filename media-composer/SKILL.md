---
name: media-composer
description: "Media editing toolkit — transcribe audio/video to text or SRT subtitles (STT via MLX Whisper), overlay captions/titles onto images and videos, overlay images onto video time windows, trim videos, extract audio tracks, replace segments with images, replace video backgrounds (RVM person matting), enhance audio/video quality (two-pass loudnorm), burn SRT subtitles, composite image+audio pairs into video segments, and concatenate videos. Deterministic ffmpeg + Pillow operations. Use when asked to 'transcribe audio', 'convert speech to text', 'generate subtitles', 'caption an image', 'overlay text', 'add a title to a video', 'insert an image into a video', 'trim video', 'extract audio from video', 'replace a segment', 'replace background', 'enhance video', 'burn subtitles', 'composite images and audio into video', or 'merge/concatenate videos'."
version: "0.3.0"
allowed-tools: ["Bash", "Read", "Write"]
---

# Media Composer

Deterministic media editing — the "hands and feet" of the RBH media pipeline. All
subcommands are local ffmpeg/Pillow/PyTorch operations with no cloud AI calls
(`transcribe` uses a local Whisper model; `replace-bg` a local RVM checkpoint).

## Quick start

```bash
source ../.venv/bin/activate
python scripts/cli.py <subcommand> --help
```

## Subcommands

| Subcommand | What it does | Notes |
|------------|--------------|-------|
| `transcribe` | Audio/video → text (STT) | local MLX Whisper / whisper.cpp; md/txt/json/srt |
| `caption` | Overlay text: batch images / one image / video title | Pillow render + ffmpeg overlay |
| `trim` | Cut head/tail | always re-encodes (avoids keyframe freeze) |
| `extract-audio` | Pull the audio track | wav (lossless) / aac / mp3 |
| `replace-segment` | Swap a time range for a still image | audio kept as voice-over |
| `overlay` | Composite image(s) on top for time windows | video stays visible around them |
| `replace-bg` | Replace background, keep the person | RVM matting, MPS-accelerated |
| `enhance` | Denoise+sharpen video, normalize loudness | two-pass loudnorm (linear) |
| `subtitle-burn` | Burn an SRT into the picture | needs libass ffmpeg (auto-detected) |
| `composite` | Image + audio pairs → MP4 segments | pairs by filename sort order |
| `concat` | Join all videos in a directory | stream copy, no re-encode |

## Usage

```bash
# STT (--format md/txt/json/srt; srt gives ready-to-burn subtitles)
python scripts/cli.py transcribe -i recording.m4a -o transcript.md
python scripts/cli.py transcribe -i talk.mp4 -o subs.srt --format srt

# Caption: batch images / single image / video title
python scripts/cli.py caption -i titles.json -d images/ -o captioned/
python scripts/cli.py caption --image photo.png --text "标题" -o out.png --position bottom
python scripts/cli.py caption --video in.mp4 --text "视频标题" -o out.mp4 --position top

# Editing chain (each step is independent)
python scripts/cli.py trim -i in.mp4 -o cut.mp4 --head 0.5 --tail 1.0
python scripts/cli.py extract-audio -i in.mp4 -o audio.wav --format wav
python scripts/cli.py replace-segment -i in.mp4 -o out.mp4 --start 10.6 --end 35.4 \
  --image chart.jpg --pad-color 0x3B2417
python scripts/cli.py overlay -i in.mp4 -o out.mp4 --image card.jpg \
  --start 4.4 --end 13.2 --width 520 --y "470-h"     # or --spec overlays.json for several
python scripts/cli.py replace-bg -i in.mp4 -o out.mp4 --bg background.png
python scripts/cli.py enhance -i in.mp4 -o out.mp4 --lufs -16
python scripts/cli.py subtitle-burn -i in.mp4 -o out.mp4 --srt subs.srt --color teal

# Assembly: image+audio pairs → segments, then join
python scripts/cli.py composite -i images/ -a audio/ -o segments/
python scripts/cli.py concat -d segments/ -o final.mp4
```

Every editing subcommand prints a JSON result (paths, timings, measured stats) to stdout.

## Key behaviors

- **trim re-encodes on purpose** — stream copy freezes at the nearest keyframe.
- **subtitle-burn** resolves a libass-capable ffmpeg by capability detection (env
  `MC_FFMPEG_FULL` → PATH → brew prefix → known locations); install `ffmpeg-full` on
  macOS if missing. `--font-size` is in libass PlayRes units, not pixels.
- **replace-bg** needs `../models/rvm_resnet50.pth` (~103 MB, gitignored) — run
  `python scripts/download_models.py` once. Requires torch (+ torchvision for resnet50);
  `--variant mobilenetv3` is lighter.
- **caption** styles are fixed by `assets/style-presets/title-default.json` (rounded
  semi-transparent box, 2× supersampled CJK text, auto font-shrink to one line);
  `--font-size` and `--position` (top/center/bottom) are the tunables. Subtitle defaults
  live in `subtitle-default.json`.
- **concat** uses the concat demuxer with stream copy — inputs must share codec,
  resolution and fps (true for `composite` output and same-model generated videos).
- **overlay vs replace-segment** — `overlay` keeps the video visible around the image
  (picture-in-picture); `replace-segment` swaps the entire frame. Multiple overlays via
  `--spec` render in one encode pass. `--x/--y` accept keywords, pixels, or ffmpeg
  expressions (e.g. `--y "470-h"` pins the image's bottom edge to y=470).

## Deep-dive references (load on demand)

- `references/ffmpeg-recipes.md` — validated trim/replace-segment/concat command shapes
- `references/audio-loudnorm.md` — two-pass loudnorm measurement → linear apply
- `references/subtitle-styling.md` — ASS colors (&HAABBGGRR), PlayRes scaling trap, margins
- `references/rvm-matting.md` — RVM pipeline, recurrence, checkpoints, performance
- `references/cjk-fonts.md` — which CJK fonts work in Pillow vs libass (they differ)

## Dependencies

- `ffmpeg` ≥ 5.0 — all editing subcommands (`subtitle-burn` needs a libass build)
- `Pillow` — caption (in skills requirements.txt)
- `mlx-whisper` — transcribe (`pip install mlx-whisper`)
- `torch` (+ `torchvision` for resnet50) — replace-bg only; local install, not deployed
