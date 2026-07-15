---
name: content-production
description: "Generate images, video, and speech audio from structured segment JSON files. The Local Agent (Claude Code, Codex, etc.) creates the JSON from user prompts directly. Reads image_prompt/video_prompt fields for images/videos and text field for speech. Multi-provider: PNG images via Agnes AI or Gemini (Nano Banana), MP4 videos via Agnes AI or Gemini (Veo), MP3/WAV audio via Fish Speech or Gemini TTS — switched per capability in .env. Also extracts plain text from DOCX/PDF documents and converts DOCX to structured Markdown. Use when asked to 'generate images from prompts', 'create videos from descriptions', 'generate speech audio', 'convert prompts to images/videos', 'produce content from segments', 'extract text from a document', or 'convert a document to markdown'."
version: "0.7.0"
allowed-tools: ["Bash", "Read", "Write"]
---

# Content Production

A **media-generation + document-conversion** toolbox. It reads a segments JSON (created by the Local Agent) and generates images / videos / speech, or it converts DOCX/PDF documents. All generation is **batch-mode from segments JSON**. This is the primary content-generation step of the RBH pipeline, feeding assets to `media-composer`.

## When to invoke — decision tree

**This skill is a media-generation + document-conversion toolbox, NOT a content-authoring orchestrator.** Only run its CLI when a sub-task requires something the Agent and environment-native tools cannot do. Authoring text (`.md` / `.json` / `.txt`) is always Agent-native.

> **Invoking the skill ≠ reading its references.** Running `cli.py` is what "triggers" the skill. Reading `references/*.md` for quality guidance is just consulting a file — optional, and not a trigger.

```
incoming task
  │
  ├─ write / edit TEXT content (article, summary, segmentation, prompts)?
  │     → Agent writes it directly (Write / Edit). DO NOT run the CLI.
  │        · vague / too-short prompt → ask clarifying questions first
  │          (audience / length / key points), guided by references/article-guide.md —
  │          this is dialogue, not a skill run.
  │        · want consistent quality → optionally read references/*.md (reading ≠ invoking).
  │
  ├─ generate MEDIA (image / video / speech)?
  │     → run the CLI (image / video / speech).
  │        Create segments.json ONLY here, as scaffolding for generation — never as a standalone deliverable.
  │
  ├─ read / convert a DOCUMENT (docx / pdf / pptx / xlsx)?
  │     ├─ plain-text dump only → try environment tools first
  │     │     (textutil for docx on macOS; pdftotext for pdf if poppler is installed).
  │     │     · unavailable → run `extract` (NEVER `pip install` outside the venv).
  │     ├─ structured (docx/pptx → markdown) → run `convert` (environment tools can't do this).
  │     └─ partial range (`--range`) → run `extract`.
  │
  └─ none of the above → not this skill (story-generation / media-composer …).
```

**One-liner:** if you can write it (Agent) or shell-command it (`textutil` / `pdftotext`), do that; only run this skill's CLI for generation APIs or deterministic document conversion.

## Not this skill

- **Story generation** → `story-generation` (FastAPI service)
- **Compositing images + audio into video** → `media-composer` `composite` + `concat` subcommands
- **Captioning images (overlay text)** → `media-composer` `caption` subcommand
- **Writing / editing MD articles** → Agent-native; see `references/article-guide.md` for guidance

## What this skill does

1. **Reads** a segments JSON file (created by Local Agent)
2. **Extracts** `image_prompt`, `video_prompt`, or `text` from each segment
3. **Generates** images (Agnes AI / Gemini Nano Banana), videos (Agnes AI / Gemini Veo), or audio (Fish Speech / Gemini TTS) — provider switched via `IMAGE_PROVIDER` / `VIDEO_PROVIDER` / `SPEECH_PROVIDER` in `.env`, CLI unchanged
4. **Saves** files in index order as `000.png`, `000.mp4`, or `000.mp3` (`.wav` for Gemini TTS), …
5. **Extracts** plain text from DOCX/PDF → `.txt` (no formatting; supports partial ranges)
6. **Converts** DOCX to structured Markdown (`.md`), preserving headings/lists/tables

## Creating segments JSON

> **Only create a segments.json when you are about to generate images / videos / speech.** It is scaffolding for media generation, not a standalone deliverable. For plain-text output, write `.md` / `.txt` directly — do not produce a segments.json.

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

Each segment must have `index`, `title`. Include `image_prompt` (images), `video_prompt` (videos), or `text` (speech) — whichever the user needs. For end-to-end flows, see `references/examples.md`.

## How to invoke

The CLI needs the shared skills virtualenv and `skills/.env` (API keys), both **one level above this skill** (`../.venv` and `../.env`). `cli.py` locates `.env` automatically relative to its own location (following symlinks), so no manual env setup is needed.

Run from this skill's directory, calling the venv python directly (no `cd` / `activate`):

```bash
# Image (default 1024x768; --size 512x512 to customize)
../.venv/bin/python scripts/cli.py image  -i segments.json -o images/

# Video (--size / --num-frames / --frame-rate to customize)
../.venv/bin/python scripts/cli.py video  -i segments.json -o videos/

# Speech (uses the text field)
../.venv/bin/python scripts/cli.py speech -i segments.json -o audio/

# Extract DOCX/PDF → plain text   (--range 2-5 for a partial range)
../.venv/bin/python scripts/cli.py extract -i report.docx -o report.txt

# Convert DOCX → structured Markdown
../.venv/bin/python scripts/cli.py convert -i report.docx -o report.md
```

…or `source ../.venv/bin/activate` first, after which the bare `python scripts/cli.py …` form works as-is.

→ **Full argument tables & configuration:** see [references/cli-reference.md](references/cli-reference.md).

## Configuration

Configured via the shared `skills/.env` (API keys, provider switches, model/size/frame defaults).
Providers are selected per capability — `IMAGE_PROVIDER` / `VIDEO_PROVIDER` (agnes | gemini) and
`SPEECH_PROVIDER` (siliconflow | gemini) — with no CLI changes. The CLI reads `.env`
automatically — see [references/cli-reference.md](references/cli-reference.md#configuration) for the
full variable list.

## Dependencies

- Native mode: none (Claude Code handles everything)
- CLI mode: Python 3.10+, `openai`, `requests`, `python-dotenv` (in skills-root `requirements.txt`)
- extract/convert: `python-docx`, `pypdf`, `mammoth` (in `requirements-local.txt`; CLI-only, not in the Railway image). PPTX/XLSX will add `python-pptx` / `openpyxl` when implemented.

## References

- [cli-reference.md](references/cli-reference.md) — full argument tables + configuration variables for every subcommand
- [examples.md](references/examples.md) — end-to-end examples (image / video / speech)
- [architecture.md](references/architecture.md) — pipeline diagram + downstream consumers
- [article-guide.md](references/article-guide.md) — MD article structure, style, input-validation guardrails
- [prompt-guide.md](references/prompt-guide.md) — how to write effective `image_prompt` / `video_prompt`
