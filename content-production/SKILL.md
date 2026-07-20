---
name: content-production
description: "Generate batch images, videos, or speech from a validated media-segments JSON input; extract plain text from DOCX/PDF; convert DOCX to structured Markdown. Ordinary MD/JSON/TXT authoring is Agent-native and does not run this CLI."
version: "0.8.0"
allowed-tools: ["Bash", "Read", "Write"]
---

# Content Production

A **media-generation + document-conversion** toolbox. It is not a general writing or JSON-authoring skill.

## Execution boundary

**The requested operation—not the file extension or skill name—determines whether to run the CLI.**

- Write or edit ordinary `.md`, `.json`, and `.txt` files directly with Agent-native tools. This remains true when the request is vague or explicitly names `content-production`.
- Run `image`, `video`, or `speech` only when the user actually requests generated media. Immediately before generation, create a validated `media-segments.json` input; never create it as a standalone deliverable.
- For documents, `extract` currently supports DOCX/PDF → plain text and `convert` supports DOCX → Markdown. PPTX/XLSX are not supported.
- Story generation belongs to `adventure-academy`; compositing, captions, subtitles, and editing belong to `media-composer`.

## Media input

The root object contains only `segments`. Indexes must be ordered and contiguous from `0`; every segment requires a non-empty `title` and the field used by the command:

| Command | Required field |
|---|---|
| `image` | `image_prompt` |
| `video` | `video_prompt` |
| `speech` | `text` |

A segment may contain multiple known media fields so the same input can support several generation commands.

```json
{
  "segments": [
    {
      "index": 0,
      "title": "Sunset over mountains",
      "image_prompt": "A breathtaking sunset over snow-capped mountains, warm orange and pink sky, photorealistic"
    },
    {
      "index": 1,
      "title": "Forest stream",
      "image_prompt": "A crystal-clear stream winding through a dense green forest, dappled sunlight, cinematic lighting"
    }
  ]
}
```

The number of items is always `len(segments)`; do not add a separate count field. See [references/cli-reference.md](references/cli-reference.md) for the complete schema.

## Run commands

Use the shared virtual environment and `.env` one level above this skill:

```bash
# Actual media generation; media-segments.json is temporary CLI input
../.venv/bin/python scripts/cli.py image  -i media-segments.json -o images/
../.venv/bin/python scripts/cli.py video  -i media-segments.json -o videos/
../.venv/bin/python scripts/cli.py speech -i media-segments.json -o audio/

# Supported document operations
../.venv/bin/python scripts/cli.py extract -i report.docx -o report.txt
../.venv/bin/python scripts/cli.py extract -i paper.pdf --range 2-5 -o excerpt.txt
../.venv/bin/python scripts/cli.py convert -i report.docx -o report.md
```

For a simple full-document text dump, prefer environment-native tools such as `textutil` (DOCX on macOS) or `pdftotext` when available. Use this CLI when those are unavailable, a partial range is needed, or structured DOCX → Markdown conversion is required.

## Configuration and references

Providers and defaults are configured in the shared `skills/.env`. Switching `IMAGE_PROVIDER` (`agnes`, `gemini`, or `openai`), `VIDEO_PROVIDER`, or `SPEECH_PROVIDER` does not change the CLI commands.

- [cli-reference.md](references/cli-reference.md) — schema, arguments, supported formats, and configuration
- [examples.md](references/examples.md) — media-generation examples
- [architecture.md](references/architecture.md) — pipeline and downstream consumers
- [article-guide.md](references/article-guide.md) — optional Agent-native article guidance
- [prompt-guide.md](references/prompt-guide.md) — effective image/video prompts
