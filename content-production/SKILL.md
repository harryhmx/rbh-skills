---
name: content-production
description: "Generate images, video, and speech audio from structured segment JSON files. The Local Agent (Claude Code, Codex, etc.) creates the JSON from user prompts directly. Reads image_prompt/video_prompt fields for images/videos and text field for speech. Produces PNG images via Agnes AI, MP4 videos via Agnes AI, or MP3 audio via Fish Speech. Use when asked to 'generate images from prompts', 'create videos from descriptions', 'generate speech audio', 'convert prompts to images/videos', or 'produce content from segments'."
version: "0.5.0"
allowed-tools: ["Bash", "Read", "Write"]
---

# Content Production

Generates images, videos, and speech audio from structured segment JSON — the **primary content generation step** of the RBH pipeline, producing assets for `video-converter`.

## Default path: Local Agent creates JSON directly

When a user wants to generate images, videos, or speech from prompts, the **only path** is:

1. **Local Agent (Claude Code / Codex / etc.) creates** a segments JSON file directly from user prompts
2. **content-production reads** that JSON and generates the assets

All generation is **batch-mode from segments JSON files** created by the Local Agent.

## What this skill does

1. **Reads** a segments JSON file (created by Local Agent)
2. **Extracts** the `image_prompt`, `video_prompt`, or `text` fields from each segment
3. **Generates** images via Agnes AI, videos via Agnes AI, or audio via Fish Speech
4. **Saves** files in index order as `000.png`, `000.mp4`, or `000.mp3`, ...
5. **Captions** images by overlaying segment titles centered on each image

## When to use it

**Direct usage (default):** Trigger this skill when the user wants to generate content from prompts they already have. The Local Agent creates the JSON, then invokes the CLI:

- "Generate images from these prompts / descriptions"
- "Create a video based on this prompt"
- "Turn these image descriptions into PNGs"
- "Generate speech audio for this text"
- "根据这些 prompt 生成图片 / 视频"
- "帮我把这些描述转成图片 / 视频 / 音频"

## When NOT to use it

- **Text splitting / segmentation** — Local Agent handles this natively
- **Text optimization or prompt generation from raw text** — Local Agent handles this natively
- **Story generation** — use the `story-generation` FastAPI service
- **Compositing images + audio into video** — use `video-converter` instead
- **Writing MD articles** — Local Agent writes articles directly (see `references/article-guide.md`); content-production only handles media generation

## Creating segments JSON directly (Local Agent)

The Local Agent creates a segments JSON file directly from user prompts:

```json
{
  "total_segments": 2,
  "segments": [
    {
      "index": 0,
      "title": "Sunset over mountains",
      "image_prompt": "A breathtaking sunset over snow-capped mountains, warm orange and pink sky, photorealistic, 4K"
    },
    {
      "index": 1,
      "title": "Forest stream",
      "image_prompt": "A crystal-clear stream winding through a dense green forest, dappled sunlight, cinematic lighting"
    }
  ]
}
```

Then pass this JSON to the CLI:

```bash
python scripts/cli.py image -i prompts.json -o images/
```

Each segment must have `index`, `title`. Include `image_prompt` for images, `video_prompt` for videos, or `text` for speech — whichever the user needs. The Local Agent fills these fields from the user's own prompts.

## How to invoke

### Native Claude Code

When invoked from Claude Code, Claude reads the segments JSON and runs the CLI:

```
Generate images from ucla-segments.json, size 512x512, save to images/
```

### Python Environment

Activate the shared virtual environment before running any Python CLI commands:

```bash
source ../.venv/bin/activate
```

### Python CLI

```bash
# Generate images from segments (default 1024x768)
python scripts/cli.py image -i ucla-segments.json -o images/

# Custom image size
python scripts/cli.py image -i ucla-segments.json -o images/ --size 512x512

# Generate videos from segments
python scripts/cli.py video -i ucla-segments.json -o videos/

# Custom video settings
python scripts/cli.py video -i ucla-segments.json -o videos/ --size 1152x768 --num-frames 121 --frame-rate 24

# Generate speech from segments (uses text field)
python scripts/cli.py speech -i ucla-segments.json -o audio/

# Overlay titles onto generated images
python scripts/cli.py caption -i ucla-segments.json -d images/ -o captioned/
```

**CLI arguments (image subcommand):**

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Path to segments JSON file | (required) |
| `--output` | `-o` | Output directory | `output/` |
| `--size` | | Image size `WxH` (e.g. `512x512`) | `1024x768` |
| `--prompt-key` | | Segment key for the image prompt | `image_prompt` |

**CLI arguments (video subcommand):**

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Path to segments JSON file | (required) |
| `--output` | `-o` | Output directory | `output/` |
| `--size` | | Video size `WxH` (e.g. `1152x768`) | `1152x768` |
| `--num-frames` | | Number of frames (≤ 441, 8n+1) | `121` |
| `--frame-rate` | | Frame rate in FPS (1–60) | `24` |
| `--prompt-key` | | Segment key for the video prompt | `video_prompt` |

**CLI arguments (speech subcommand):**

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Path to segments JSON file | (required) |
| `--output` | `-o` | Output directory | `output/` |

Speech generation uses the segment's `text` field as the speech content.

**CLI arguments (caption subcommand):**

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Path to segments JSON file | (required) |
| `--dir` | `-d` | Directory containing `{index:03d}.png` images | (required) |
| `--output` | `-o` | Output directory for captioned images | (overwrites originals) |
| `--font` | | Path to .ttf/.ttc font file | (auto-detect CJK) |
| `--font-size` | | Font size in points | `36` |

## Examples

### Example 1: Direct from prompts (default path)

Local Agent creates a segments JSON directly from user prompts:

```json
// prompts.json — created by Local Agent
{
  "total_segments": 2,
  "segments": [
    {
      "index": 0,
      "title": "Sunset mountains",
      "image_prompt": "A breathtaking sunset over snow-capped mountains, warm orange and pink sky, photorealistic, 4K"
    },
    {
      "index": 1,
      "title": "Forest stream",
      "image_prompt": "A crystal-clear stream winding through a dense green forest, dappled sunlight, cinematic lighting"
    }
  ]
}
```

```bash
# Generate images directly
python scripts/cli.py image -i prompts.json -o images/
```

Output:
```
images/
├── 000.png   # Segment 0 image
├── 001.png   # Segment 1 image
├── 002.png   # Segment 2 image
├── 003.png   # Segment 3 image
```

### Example 2: JSON output structure (image generation)

```json
{
  "total": 4,
  "succeeded": 4,
  "failed": 0,
  "results": [
    {
      "index": 0,
      "title": "Opening Scene",
      "file_path": "/abs/path/to/images/000.png",
      "url": "https://...",
      "prompt": "A wide shot of a sunlit classroom..."
    }
  ]
}
```

### Example 3: Generate videos from segments

Local Agent creates segments JSON with `video_prompt` fields, then:

```bash
python scripts/cli.py video -i segments.json -o videos/ --size 1152x768 --num-frames 121 --frame-rate 24
```

Output:
```
videos/
├── 000.mp4   # Segment 0 video
├── 001.mp4   # Segment 1 video
├── 002.mp4   # Segment 2 video
├── 003.mp4   # Segment 3 video
```

Video generation is asynchronous — each video is submitted to Agnes AI, polled until complete (up to 15 min timeout), then downloaded. The JSON output includes `video_id` for each video result.

### Example 4: Speech generation

Local Agent creates segments JSON with `text` fields directly from user input.

```bash
# Generate speech audio
python scripts/cli.py speech -i segments.json -o audio/
```

Output:
```
audio/
├── 000.mp3   # Segment 0 audio
├── 001.mp3   # Segment 1 audio
├── 002.mp3   # Segment 2 audio
├── 003.mp3   # Segment 3 audio
```

The speech content comes from the `text` field.

## Configuration

Uses the `skills/.env` configuration:

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

## Architecture

```
User Prompts
        │
        └── Local Agent
                │
                └── creates segments.json directly from user prompts
                        │
                        ▼
                content-production (CLI)
                        │
                        ├── image ──> generate_images()
                        │               │
                        │               └── POST /v1/images/generations
                        │                       → Agnes AI → 000.png, 001.png, ...
                        │
                        ├── video ──> generate_videos()
                        │               │
                        │               ├── POST /v1/videos (create video)
                        │               ├── GET /v1/videos/{video_id} (parallel poll)
                        │               └── Download MP4 → 000.mp4, 001.mp4, ...
                        │
                        ├── speech ─> generate_speech()
                        │               │
                        │               └── SiliconFlow Fish Speech → 000.mp3, ...
                        │                   (uses text field)
                        │
                        └── caption ─> caption_images()
                                        │
                                        └── PIL (Pillow) — Overlay title text centered
```

## Output consumed by

- **video-converter**: receives images + audio for video synthesis
- **Direct publishing**: images published as article illustrations
- **Manual editing**: images and audio files for further processing

## Dependencies

- Native mode: none (Claude Code handles everything)
- CLI mode: Python 3.10+, `openai`, `requests`, `python-dotenv` (in skills root `requirements.txt`)
