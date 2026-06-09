---
name: video-converter
description: "Composite still images and audio files into MP4 video segments, and concatenate video segments into a final video. Pairs images and audio by filename sort order, burns each pair into a video via ffmpeg, then joins all segments in order. Use when asked to 'create videos from images and audio', 'convert slides to video', 'burn audio onto images', 'generate video segments', or 'merge videos into one'."
version: "0.1.0"
allowed-tools: ["Bash", "Read", "Write"]
---

# Video Converter

Composites still images + audio into MP4 video segments — the third step of the RBH content production pipeline, receiving assets from `content-production` and producing videos for publishing.

## What this skill does

1. **Reads** image files from an image directory (sorted by filename)
2. **Reads** audio files from an audio directory (sorted by filename)
3. **Pairs** them by position: first image + first audio, second + second, ...
4. **Composites** each pair into an MP4 video via ffmpeg (H.264 video + AAC audio)
5. **Saves** video files in index order as `000.mp4`, `001.mp4`, ...
6. **Concatenates** all video segments into a single final MP4 (stream copy, no re-encoding)

## When to use it

Trigger this skill when the user asks to:
- "Create videos from these images and audio"
- "Convert slides/images to video with narration"
- "Burn audio onto images"
- "Generate video segments from assets"
- "Composite image+audio pairs into MP4"
- "Merge/concatenate/join video files into one"
- "Combine all segments into a final video"

## When NOT to use it

- **Image generation** — use `content-production` instead
- **Audio/TTS generation** — use `content-production` instead
- **Text splitting / prompt generation** — use `text-optimizer` instead
- **Complex video editing** (transitions, multiple clips, effects) — out of scope for v0.1; use a dedicated video editor
- **Subtitle/closed-caption generation** — planned for a future version

## How to invoke

### Native Claude Code

When invoked from Claude Code, Claude runs the CLI:

```
Composite images from ucla-captioned/ and audio from ucla-audio/ into videos/
```

### Python CLI

```bash
# Composite images + audio into video segments
python scripts/cli.py convert -i images/ -a audio/ -o videos/

# With captioned images
python scripts/cli.py convert -i captioned/ -a audio/ -o videos/

# Concatenate all video segments into one final video
python scripts/cli.py concat -d videos/
```

**CLI arguments (convert subcommand):**

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--image-dir` | `-i` | Directory containing image files (PNG, JPG, etc.) | (required) |
| `--audio-dir` | `-a` | Directory containing audio files (MP3, WAV, etc.) | (required) |
| `--output` | `-o` | Output directory for MP4 videos | `output/` |

**CLI arguments (concat subcommand):**

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--dir` | `-d` | Directory containing video files (sorted by name, stream-copied in order) | (required) |

The concat output file is named ``<dirname>.mp4`` and placed in the **parent** directory of the input directory. For example, ``concat -d videos/`` produces ``videos.mp4``.

## Examples

### Example 1: Full pipeline — text to videos

```bash
# Step 1: Split text and generate image + TTS prompts
python ../text-optimizer/scripts/cli.py split -i article.md \
  --prompts --prompt-types image,tts -f json -o segments.json

# Step 2: Generate images and speech
python ../content-production/scripts/cli.py image -i segments.json -o images/
python ../content-production/scripts/cli.py speech -i segments.json -o audio/

# Step 3: Add titles to images
python ../content-production/scripts/cli.py caption \
  -i segments.json -d images/ -o captioned/

# Step 4: Composite into video segments
python scripts/cli.py convert -i captioned/ -a audio/ -o videos/

# Step 5: Concatenate all segments into final video
python scripts/cli.py concat -d videos/
```

Output:
```
videos/
├── 000.mp4   # Segment 0: image + narration
├── 001.mp4   # Segment 1: image + narration
├── 002.mp4   # Segment 2: image + narration
└── ...
videos.mp4    # All segments concatenated into one video

### Example 2: JSON output structure

```json
{
  "total": 14,
  "succeeded": 14,
  "failed": 0,
  "results": [
    {
      "index": 0,
      "image": "/abs/path/to/captioned/000.png",
      "audio": "/abs/path/to/audio/000.mp3",
      "output": "/abs/path/to/videos/000.mp4",
      "size_bytes": 1234567
    }
  ]
}
```

### Example 3: Concat output

```json
{
  "input_dir": "/abs/path/to/videos",
  "input_count": 14,
  "output": "/abs/path/to/videos.mp4",
  "size_bytes": 13805723
}
```

### Pairing behavior (convert)

Images and audio are sorted alphabetically by filename and paired by position:

```
Images (sorted):         Audio (sorted):         → Videos:
  000.png                  000.mp3                 000.mp4
  001.png                  001.mp3                 001.mp4
  002.png                  003.mp3                 002.mp4  (no audio for 003.png)
  003.png                                           ← stops here (no audio for 004.mp3)
```

Processing stops when either list is exhausted.

## Configuration

No environment variables or API keys needed — pure local processing via ffmpeg.

| Dependency | Version | Notes |
|------------|---------|-------|
| `ffmpeg` | ≥ 5.0 | System-installed, called via subprocess |

## Architecture

```
content-production output (images/ + audio/)
        │
        ├── images/    (000.png, 001.png, ...)
        └── audio/     (000.mp3, 001.mp3, ...)
                │
                ▼
        video-converter (CLI)
                │
                ├── convert ──> composite_videos()
                │               │
                │               ├── Sort files by name
                │               ├── Pair by position (0→0, 1→1, ...)
                │               └── ffmpeg per pair
                │                       │
                │                       ├── -loop 1 (still image)
                │                       ├── libx264 + stillimage tune
                │                       ├── aac 192k audio
                │                       └── → 000.mp4, 001.mp4, ...
                │
                └── concat ──> concat_videos()
                                │
                                ├── Sort videos by name
                                ├── ffmpeg concat demuxer
                                └── stream copy (no re-encode)
                                        │
                                        └── → <dirname>.mp4 (parent dir)
```

## Output consumed by

- **Direct publishing**: MP4 videos uploaded to video platforms (BiliBili, YouTube, etc.)
- **Social media**: short-form video content for Xiaohongshu, Douyin, WeChat Channels
- **RBH Agent**: embedded video content in course/article pages

## Dependencies

- `ffmpeg` (system): video/audio encoding — must be installed and on PATH
- Python 3.10+ (standard library only)
- No Python packages required beyond the standard library
