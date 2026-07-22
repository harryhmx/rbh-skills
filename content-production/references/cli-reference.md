# Content-Production CLI Reference

Detailed reference for media generation and supported document conversion. Run from this skill directory:

```bash
../.venv/bin/python scripts/cli.py <subcommand> [flags]
```

The CLI automatically loads the shared `skills/.env`.

## Media input schema

`image`, `video`, and `speech` consume a media-only input such as `media-segments.json`. Create it only immediately before actual media generation; ordinary JSON authoring does not use this schema.

```json
{
  "name": "lesson-1",
  "segments": [
    {
      "index": 0,
      "title": "Opening scene",
      "slug": "opening",
      "image_prompt": "A bright classroom at sunrise",
      "video_prompt": "Slow dolly into a bright classroom at sunrise",
      "text": "Welcome to today's lesson."
    }
  ]
}
```

Rules:

- The root object contains the required `segments` array and an optional `name` (kebab-case string for filename prefixes).
- Each item is an object containing `index`, `title`, an optional `slug` (kebab-case for custom filenames), and one or more known media fields: `image_prompt`, `video_prompt`, `text`.
- Indexes are non-negative integers ordered contiguously from `0`; they determine filenames when neither `name` nor `slug` is set.
- Titles and every present media field are non-empty strings.
- The current command requires its fixed field: image → `image_prompt`, video → `video_prompt`, speech → `text`.
- File naming follows `{name}-{slug}{ext}` when both are present, `{name}-{index:03d}{ext}` when only name is given, or `{index:03d}{ext}` when neither is set.
- Unknown fields are rejected. The batch count is derived from the array length; no separate count field is accepted.

Validation finishes before output directories, credentials, or provider requests are touched.

## image

```bash
python scripts/cli.py image -i media-segments.json -o images/
python scripts/cli.py image -i media-segments.json -o images/ --size 512x512
```

| Argument | Short | Description | Default |
|---|---|---|---|
| `--input` | `-i` | Media input requiring `image_prompt` | required |
| `--output` | `-o` | Output directory | `output/` |
| `--size` | | Positive `WxH` dimensions | `IMAGE_SIZE` or `1024x768` |

Images use the project filename scheme: `{name}-{slug}.png`, `{name}-{index:03d}.png`, or `{index:03d}.png`.

## video

```bash
python scripts/cli.py video -i media-segments.json -o videos/
```

| Argument | Short | Description | Default |
|---|---|---|---|
| `--input` | `-i` | Media input requiring `video_prompt` | required |
| `--output` | `-o` | Output directory | `output/` |
| `--size` | | Positive `WxH` dimensions | `VIDEO_SIZE` or `1152x768` |
| `--num-frames` | | Positive frame count ≤441 satisfying `8n+1` | `VIDEO_NUM_FRAMES` or `121` |
| `--frame-rate` | | FPS from 1 through 60 | `VIDEO_FRAME_RATE` or `24` |

Videos use the project filename scheme: `{name}-{slug}.mp4`, `{name}-{index:03d}.mp4`, or `{index:03d}.mp4`. All submitted inputs remain represented in the stdout results, including submission failures, provider failures, download failures, and timeouts. With Gemini/Veo, size maps to the nearest supported aspect ratio and Agnes-only frame settings are ignored.

## speech

```bash
python scripts/cli.py speech -i media-segments.json -o audio/
```

| Argument | Short | Description | Default |
|---|---|---|---|
| `--input` | `-i` | Media input requiring `text` | required |
| `--output` | `-o` | Output directory | `output/` |

SiliconFlow output is MP3; Gemini TTS output is 24 kHz mono WAV.


## Single generation via --prompt

All media commands also accept ``--prompt`` for one-off generation without a JSON file.

```bash
# Single image
python scripts/cli.py image --prompt "A sunset over mountains" -o sunset.png
python scripts/cli.py image --prompt "A sunset" -o output/ --size 512x512

# Single video
python scripts/cli.py video --prompt "A car driving through desert" -o car.mp4
python scripts/cli.py video --prompt "Drone shot over forest" -o output/ --size 1024x768

# Single speech
python scripts/cli.py speech --prompt "Welcome to the lesson" -o greeting.mp3
python scripts/cli.py speech --prompt "Hello world" -o output/
```

When ``-o`` is a directory or ends with ``/``, a default filename (``output.png``, ``output.mp4``, ``output.mp3``, or ``output.wav``) is used inside it. Otherwise ``-o`` is treated as the exact output file path.

When ``-i`` is given, batch generation is used with the same defaults as before.

## Batch summary

Media commands print one JSON summary to stdout:

```json
{
  "total": 2,
  "succeeded": 1,
  "failed": 1,
  "results": []
}
```

`total` and `results` reflect every validated input segment. Detailed logs go to stderr.

## Document commands

| Command | Supported input | Output | Notes |
|---|---|---|---|
| `extract` | DOCX, PDF | plain text / `.txt` | `--range` selects DOCX paragraphs or PDF pages |
| `convert` | DOCX | structured Markdown / `.md` | preserves headings, lists, emphasis, and tables |

PPTX and XLSX are currently unsupported.

```bash
python scripts/cli.py extract -i report.docx -o report.txt
python scripts/cli.py extract -i paper.pdf --range 2-5 -o excerpt.txt
python scripts/cli.py convert -i report.docx -o report.md
```

## Configuration

### Provider switches

| Variable | Options | Default |
|---|---|---|
| `IMAGE_PROVIDER` | `agnes` / `gemini` / `openai` | `agnes` |
| `VIDEO_PROVIDER` | `agnes` / `gemini` | `agnes` |
| `SPEECH_PROVIDER` | `siliconflow` / `gemini` | `siliconflow` |

### Agnes AI / SiliconFlow

| Variable | Default |
|---|---|
| `IMAGE_BASE_URL` | `https://apihub.agnes-ai.com` |
| `IMAGE_MODEL` | `agnes-image-2.1-flash` |
| `IMAGE_SIZE` | `1024x768` |
| `VIDEO_BASE_URL` | `https://apihub.agnes-ai.com` |
| `VIDEO_MODEL` | `agnes-video-v2.0` |
| `VIDEO_SIZE` | `1152x768` |
| `VIDEO_NUM_FRAMES` | `121` |
| `VIDEO_FRAME_RATE` | `24` |
| `VIDEO_POLL_TIMEOUT` | `900` |
| `VIDEO_POLL_INTERVAL` | `10` |
| `SPEECH_BASE_URL` | `https://api.siliconflow.com/v1` |
| `SPEECH_MODEL` | `fishaudio/fish-speech-1.5` |
| `SPEECH_VOICE` | `fishaudio/fish-speech-1.5:anna` |

Set `IMAGE_API_KEY`, `VIDEO_API_KEY`, and `SPEECH_API_KEY` for the selected providers.

### OpenAI image generation

| Variable | Description | Default |
|---|---|---|
| `OPENAI_BASE_URL` | OpenAI API base URL | `https://api.openai.com/v1` |
| `OPENAI_IMAGE_MODEL` | Image generation model | `gpt-image-2` |
| `OPENAI_IMAGE_TRANSPORT` | OpenAI transport: `curl` (default) or `sdk` | `curl` |
| `OPENAI_IMAGE_TIMEOUT` | OpenAI request timeout in seconds | `180` |

### Gemini

One `GEMINI_API_KEY` is shared by image, video, and speech.

| Variable | Default |
|---|---|
| `GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta` |
| `GEMINI_IMAGE_MODEL` | `gemini-3.1-flash-image` |
| `GEMINI_IMAGE_SIZE` | `1K` |
| `GEMINI_VIDEO_MODEL` | `veo-3.1-generate-preview` |
| `GEMINI_VIDEO_DURATION` | `8` |
| `GEMINI_VIDEO_RESOLUTION` | `720p` |
| `GEMINI_VIDEO_CONCURRENCY` | `4` |
| `GEMINI_TTS_MODEL` | `gemini-3.1-flash-tts-preview` |
| `GEMINI_TTS_VOICE` | `Kore` |
