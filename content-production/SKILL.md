---
name: content-production
description: "Generate images and speech audio from text-optimizer segment JSON files. Reads image_prompt/tts_prompt fields and produces PNG images via Flux.2-pro or MP3 audio via Fish Speech. Use when asked to 'generate images from segments', 'create illustrations for this story', 'convert prompts to images', or 'produce content from segments'."
version: "0.1.0"
allowed-tools: ["Bash", "Read", "Write"]
---

# Content Production

Generates images and speech audio from structured segment JSON — the second step of the RBH content production pipeline, receiving output from `text-optimizer` and producing assets for `video-converter`.

## What this skill does

1. **Reads** a segments JSON file (from `text-optimizer` output)
2. **Extracts** the `image_prompt` (or `tts_prompt`) field from each segment
3. **Generates** images via SiliconFlow Flux.2-pro or audio via Fish Speech
4. **Saves** files in index order as `000.png`, `001.png`, ...
5. **Captions** images by overlaying segment titles centered on each image

## When to use it

Trigger this skill when the user asks to:
- "Generate images from this segments JSON"
- "Create illustrations for these story segments"
- "Convert image prompts to actual images"
- "Produce content assets from text-optimizer output"
- "Batch generate images from prompts"

## When NOT to use it

- **Text splitting / segmentation** — use `text-optimizer` instead
- **Video generation** — use `video-converter` (A3, Stage 5)
- **Story generation** — use the `story-generation` FastAPI service
- **Direct image generation without segments** — use `story-generation/scripts/image.py` directly

## How to invoke

### Native Claude Code

When invoked from Claude Code, Claude reads the segments JSON and runs the CLI:

```
Generate images from ucla-segments.json, size 512x512, save to images/
```

### Python CLI

```bash
# Generate images from segments (default 1024x768)
python scripts/cli.py image -i ucla-segments.json -o images/

# Custom image size
python scripts/cli.py image -i ucla-segments.json -o images/ --size 512x512

# Generate speech from segments
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

**CLI arguments (speech subcommand):**

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Path to segments JSON file | (required) |
| `--output` | `-o` | Output directory | `output/` |
| `--prompt-key` | | Segment key for the TTS prompt | `tts_prompt` |

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

## Configuration

Uses the `skills/.env` configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `IMAGE_API_KEY` | Agnes AI API key | (from .env) |
| `IMAGE_BASE_URL` | Agnes AI API base URL | `https://apihub.agnes-ai.com` |
| `IMAGE_MODEL` | Image generation model | `agnes-image-2.1-flash` |
| `IMAGE_SIZE` | Default image size (WxH) | `1024x768` |
| `SPEECH_API_KEY` | SiliconFlow API key | (from .env) |
| `SPEECH_BASE_URL` | SiliconFlow API base URL | `https://api.siliconflow.com/v1` |
| `SPEECH_MODEL` | Speech generation model | `fishaudio/fish-speech-1.5` |
| `SPEECH_VOICE` | Speech voice preset | `fishaudio/fish-speech-1.5:anna` |

## Architecture

```
text-optimizer output (segments.json)
        │
        └── content-production (CLI)
                │
                ├── image ──> generate_images()
                │               │
                │               └── POST /v1/images/generations
                │                       │
                │                       └── Agnes AI (agnes-image-2.1-flash)
                │                             → 000.png, 001.png, ...
                │
                ├── speech ─> generate_speech()
                │               │
                │               └── OpenAI().audio.speech.create()
                │                       │
                │                       └── SiliconFlow Fish Speech
                │                             → 000.mp3, 001.mp3, ...
                │
                └── caption ─> caption_images()
                                │
                                └── PIL (Pillow)
                                      │
                                      └── Overlay title text centered
                                            → 000.png, 001.png, ...
```

## Output consumed by

- **video-converter (A3)**: receives images + audio for video synthesis
- **Direct publishing**: images published as article illustrations
- **Manual editing**: images and audio files for further processing

## Dependencies

- Native mode: none (Claude Code handles everything)
- CLI mode: Python 3.10+, `openai`, `requests`, `python-dotenv` (in skills root `requirements.txt`)
