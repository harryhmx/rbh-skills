---
name: content-production
description: "Generate images, video, and speech audio from text-optimizer segment JSON files or single prompt files. Reads image_prompt/video_prompt/tts_prompt fields from segments or the proprietary genprompt format and produces PNG images via Agnes AI, MP4 videos via Agnes AI, or MP3 audio via Fish Speech. Use when asked to 'generate images from segments', 'create videos from prompts', 'convert prompts to images/videos', 'generate from prompt file', or 'produce content from segments'."
version: "0.3.0"
allowed-tools: ["Bash", "Read", "Write"]
---

# Content Production

Generates images, videos, and speech audio from structured segment JSON — the second step of the RBH content production pipeline, receiving output from `text-optimizer` and producing assets for `video-converter`.

## What this skill does

1. **Reads** a segments JSON file (from `text-optimizer` output) **or** a single prompt file (from `text-optimizer genprompt`)
2. **Extracts** the `image_prompt`, `video_prompt`, or `tts_prompt` field from each segment, or parses the proprietary frontmatter from a single prompt file
3. **Generates** images via Agnes AI, videos via Agnes AI, or audio via Fish Speech
4. **Saves** files in index order as `000.png`, `000.mp4`, or `000.mp3`, ... for batch mode; or **saves** as `{basename}.png` / `{basename}.mp4` in the same directory for single mode
5. **Captions** images by overlaying segment titles centered on each image

## When to use it

Trigger this skill when the user asks to:
- "Generate images from this segments JSON"
- "Generate videos from these segments"
- "Create illustrations/videos for these story segments"
- "Convert image/video prompts to actual images/videos"
- "Produce content assets from text-optimizer output"
- "Batch generate images/videos from prompts"
- "Generate a single image/video from this prompt file"
- "Produce the image for this prompt"

## When NOT to use it

- **Text splitting / segmentation** — use `text-optimizer` instead
- **Story generation** — use the `story-generation` FastAPI service
- **Direct image generation without segments** — use `story-generation/scripts/image.py` directly

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
python scripts/cli.py video -i ucla-segments.json -o videos/ --size 1024x768 --num-frames 121 --frame-rate 24

# Generate speech from segments
python scripts/cli.py speech -i ucla-segments.json -o audio/

# Overlay titles onto generated images
python scripts/cli.py caption -i ucla-segments.json -d images/ -o captioned/

# Generate a single image/video from a prompt file (from text-optimizer genprompt)
python scripts/cli.py single -i my-image-prompt.md
python scripts/cli.py single -i my-video-prompt.md
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
| `--size` | | Video size `WxH` (e.g. `1024x768`) | `1024x768` |
| `--num-frames` | | Number of frames (≤ 441, 8n+1) | `121` |
| `--frame-rate` | | Frame rate in FPS (1–60) | `24` |
| `--prompt-key` | | Segment key for the video prompt | `video_prompt` |

**CLI arguments (speech subcommand):**

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Path to segments JSON file | (required) |
| `--output` | `-o` | Output directory | `output/` |
| `--prompt-key` | | Segment key for the TTS prompt | `tts_prompt` |

**CLI arguments (single subcommand):**

Generates a single image or video from a prompt file (proprietary format from `text-optimizer genprompt`). The output file is saved in the same directory as the input file, with the same base filename and a `.png` or `.mp4` extension.

```bash
# Generate a single image from a prompt file
python scripts/cli.py single -i my-image-prompt.md
# → saves my-image-prompt.png in the same directory

# Generate a single video from a prompt file
python scripts/cli.py single -i my-video-prompt.md
# → saves my-video-prompt.mp4 in the same directory
```

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Path to prompt file (.md or .txt) | (required) |

All generation parameters (size, num_frames, frame_rate) are read from the prompt file's frontmatter — no additional CLI arguments needed.

**CLI arguments (caption subcommand):**

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Path to segments JSON file | (required) |
| `--dir` | `-d` | Directory containing `{index:03d}.png` images | (required) |
| `--output` | `-o` | Output directory for captioned images | (overwrites originals) |
| `--font` | | Path to .ttf/.ttc font file | (auto-detect CJK) |
| `--font-size` | | Font size in points | `36` |

## Examples

### Example 1: Generate images from text-optimizer output

```bash
# First, split text and generate prompts
python ../text-optimizer/scripts/cli.py split -i article.md --prompts -f json -o segments.json

# Then, generate images
python scripts/cli.py image -i segments.json -o images/ --size 512x512
```

Output:
```
images/
├── 000.png   # Segment 0 image
├── 001.png   # Segment 1 image
├── 002.png   # Segment 2 image
└── ...
```

### Example 2: JSON output structure

```json
{
  "total": 4,
  "succeeded": 4,
  "failed": 0,
  "results": [
    {
      "index": 0,
      "title": "开篇引入",
      "file_path": "/abs/path/to/images/000.png",
      "url": "https://...",
      "prompt": "A wide shot of a sunlit classroom..."
    }
  ]
}
```

### Example 3: Generate videos from text-optimizer output

```bash
# First, split text and generate prompts (including video_prompt)
python ../text-optimizer/scripts/cli.py split -i article.md --prompts --prompt-types image,video -f json -o segments.json

# Then, generate videos
python scripts/cli.py video -i segments.json -o videos/ --size 1024x768 --num-frames 121 --frame-rate 24
```

Output:
```
videos/
├── 000.mp4   # Segment 0 video
├── 001.mp4   # Segment 1 video
├── 002.mp4   # Segment 2 video
└── ...
```

Video generation is asynchronous — each video task is submitted to Agnes AI, polled until complete (up to 15 min timeout), then downloaded. The JSON output includes `task_id` for each video result.

### Example 4: Single prompt → single image

```bash
# Step 1: Generate a single image prompt from some text
python ../text-optimizer/scripts/cli.py genprompt -t image -i "A cute cat sleeping on a bookshelf" -o cat-prompt.md

# Step 2: Generate the image
python scripts/cli.py single -i cat-prompt.md
```

Output:
```
Same directory as cat-prompt.md:
├── cat-prompt.md   # The prompt file (input)
└── cat-prompt.png  # The generated image (output)
```

All generation parameters (type, size) are read from the prompt file's frontmatter. The output is saved in the same directory with the same base filename.

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
| `VIDEO_SIZE` | Default video size (WxH) | `1024x768` |
| `VIDEO_NUM_FRAMES` | Default number of frames (≤ 441, 8n+1) | `121` |
| `VIDEO_FRAME_RATE` | Default frame rate in FPS (1–60) | `24` |
| `SPEECH_API_KEY` | SiliconFlow API key | (from .env) |
| `SPEECH_BASE_URL` | SiliconFlow API base URL | `https://api.siliconflow.com/v1` |
| `SPEECH_MODEL` | Speech generation model | `fishaudio/fish-speech-1.5` |
| `SPEECH_VOICE` | Speech voice preset | `fishaudio/fish-speech-1.5:anna` |

## Architecture

```
text-optimizer output
        │
        ├── segments.json (batch mode)
        │       │
        │       └── content-production (CLI)
        │               │
        │               ├── image ──> generate_images()
        │               │               │
        │               │               └── POST /v1/images/generations
        │               │                       → Agnes AI → 000.png, 001.png, ...
        │               │
        │               ├── video ──> generate_videos()
        │               │               │
        │               │               ├── POST /v1/videos (create tasks)
        │               │               ├── GET /v1/videos/{id} (parallel poll)
        │               │               └── Download MP4 → 000.mp4, 001.mp4, ...
        │               │
        │               └── speech ─> generate_speech()
        │                               └── SiliconFlow Fish Speech → 000.mp3, ...
        │
        └── prompt.md/.txt (single mode, from genprompt)
                │
                └── content-production (CLI)
                        │
                        └── single ──> parse_prompt_file()
                                        │
                                        ├── image → generate_single_image()
                                        │            → {basename}.png (same dir)
                                        │
                                        └── video → generate_single_video()
                                                     → {basename}.mp4 (same dir)

                └── caption ─> caption_images()
                                │
                                └── PIL (Pillow) — Overlay title text centered
```

## Output consumed by

- **video-converter (A3)**: receives images + audio for video synthesis
- **Direct publishing**: images published as article illustrations
- **Manual editing**: images and audio files for further processing
- **Upstream**: receives prompt files from `text-optimizer genprompt` (proprietary format)

## Dependencies

- Native mode: none (Claude Code handles everything)
- CLI mode: Python 3.10+, `openai`, `requests`, `python-dotenv` (in skills root `requirements.txt`)
