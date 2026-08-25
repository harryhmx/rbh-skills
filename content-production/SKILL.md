---
name: content-production
description: "Generate batch images, videos, or speech from a validated media-segments JSON input; extract plain text from DOCX/PDF; convert DOCX to structured Markdown with embedded images extracted and tables extracted to CSV. Ordinary MD/JSON/TXT authoring is Agent-native and does not run this CLI."
version: "0.9.2"
sandbox: require-escalated
---

# Content Production

A **media-generation + document-conversion** toolbox. It is not a general writing or JSON-authoring skill.

## Sandbox requirement

**All CLI commands in this skill must run outside the sandbox.** The `cli.py` toolchain requires network access (API calls to image/video/speech providers, Supabase) and filesystem access (`.env` with credentials, project directories). Run every command below with `sandbox_permissions: "require_escalated"`.

When escalating, provide a clear `justification` (e.g. "Content-production CLI needs network access to media-generation APIs and credentials in skills/.env") and a `prefix_rule` scoped to the skill's Python environment (e.g. `["../.venv/bin/python", "scripts/cli.py"]`).

Ordinary `.md`/`.json`/`.txt` authoring does **not** need escalation — only the CLI invocations listed in the **Run commands** section.

---

## Execution boundary

**The requested operation—not the file extension or skill name—determines whether to run the CLI.**

- Write or edit ordinary `.md`, `.json`, and `.txt` files directly with Agent-native tools. This remains true when the request is vague or explicitly names `content-production`.
- Run `image`, `video`, or `speech` only when the user actually requests generated media.
  - **Single item** → use `--prompt` mode directly (no JSON file needed).
  - **Multiple items (≥2)** → create a `media-segments.json` and pass it via `--input`/`-i`.
  - **JSON already exists** → pass it via `--input`/`-i` regardless of item count; do not recreate it.
  Never create `media-segments.json` as a standalone deliverable — only as an input artifact immediately before generation.
- For documents, `extract` currently supports DOCX/PDF → plain text and `convert` supports DOCX → Markdown (extracting embedded images and tables as sidecar assets). PPTX/XLSX are not supported.
- Story generation belongs to `adventure-academy`; compositing, captions, subtitles, and editing belong to `media-composer`.

## Media input

The root object contains `segments` (required) and an optional `name` (kebab-case string for filename prefixes). Indexes must be ordered and contiguous from `0`; every segment requires a non-empty `title` and the field used by the command. Each segment may also include an optional `slug` (kebab-case) for custom filenames:

| Command | Required field |
|---|---|
| `image` | `image_prompt` |
| `video` | `video_prompt` |
| `speech` | `text` |

A segment may contain multiple known media fields so the same input can support several generation commands.

```json
{
  "name": "my-project",
  "segments": [
    {
      "index": 0,
      "title": "Sunset over mountains",
      "slug": "sunset",
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

File naming follows `{name}-{slug}{ext}` when both are present, `{name}-{index:03d}{ext}` when only name is given, or `{index:03d}{ext}` when neither is set. The number of items is always `len(segments)`; do not add a separate count field. See [references/cli-reference.md](references/cli-reference.md) for the complete schema.


## Run commands

Use the shared virtual environment and `.env` one level above this skill. When a project directory is specified, create the JSON input inside that directory so all artifacts are collocated. **Every command below requires escalation as described above.**

When generating media, always announce which provider is active before calling the CLI. The active provider is set by `IMAGE_PROVIDER`, `VIDEO_PROVIDER`, or `SPEECH_PROVIDER` in `skills/.env` (default is `openai` for image, `agnes` for video, `siliconflow` for speech).

```bash
# Batch generation — JSON and output files in the same project directory
../.venv/bin/python scripts/cli.py image   -i project/media-segments.json -o project/images/
../.venv/bin/python scripts/cli.py video   -i project/media-segments.json -o project/videos/
../.venv/bin/python scripts/cli.py speech  -i project/media-segments.json -o project/audio/

# Single generation via --prompt (no JSON file needed)
../.venv/bin/python scripts/cli.py image   --prompt "A sunset over mountains" -o sunset.png
../.venv/bin/python scripts/cli.py video   --prompt "A car driving through desert" -o car.mp4
../.venv/bin/python scripts/cli.py speech  --prompt "Hello world" -o greeting.mp3

# Image-to-image (i2i) — edit an existing image (scenario A)
../.venv/bin/python scripts/cli.py image   --prompt "Change title to 'Summer Camp 2026'" --ref poster.png -o poster-v2.png

# Image-to-image (i2i) — reference-driven generation (scenario B, multiple refs)
../.venv/bin/python scripts/cli.py image   --prompt "Generate a 3D Pixar-style avatar" --ref photo-1.jpg --ref photo-2.jpg -o avatar.png

# Batch i2i — segments with image_refs field (see cli-reference.md for schema)
# Segments without image_refs use text-to-image; mixed batches are supported.

# Supported document operations
../.venv/bin/python scripts/cli.py extract -i report.docx -o report.txt
../.venv/bin/python scripts/cli.py extract -i paper.pdf --range 2-5 -o excerpt.txt
../.venv/bin/python scripts/cli.py convert -i report.docx -o report.md

# convert extracts images + tables as sidecar assets into <docx dir>/assets by default.
# Output .md defaults to <docx dir>/<stem>.md when -o is omitted.
# Images  → {stem}-image-{n}.{ext}, emitted as their own ![](path) blocks (separated from text)
# Tables  → {stem}-table-{n}.csv   (clean data handoff; render to PNG via media-composer)
../.venv/bin/python scripts/cli.py convert -i article-49.docx             # → article-49.md + assets/
# WeChat article pipeline: title → H1, sections → H2/H3, · bullets → lists
../.venv/bin/python scripts/cli.py convert -i article-49.docx --first-as-h1 --normalize-headings
../.venv/bin/python scripts/cli.py convert -i article-49.docx -o out/article-49.md --media-dir out/assets
../.venv/bin/python scripts/cli.py convert -i article.docx -o article.md --tables-as-images   # WeChat: tables → ![](stem-table-N.png)
```

`convert` writes images and table CSVs to `--media-dir` (default: an `assets` subdirectory beside the source DOCX, created if missing) and references images with paths relative to the `.md`. By default it also tidies the Markdown: images sit in their own blocks (never clinging to text), and `·`/`•` bullet paragraphs become tight Markdown lists. `--no-images` / `--no-tables` skip extraction; `--tables-as-images` swaps the Markdown table for an image reference (the PNG is rendered from the CSV by `media-composer`); `--first-as-h1` forces the first prose paragraph to an `# Title`; `--normalize-headings` remaps section heading levels via CJK numbering (`一、`→H2, `1.`→H3, `结语`→H2) — see [references/cli-reference.md](references/cli-reference.md).

For a simple full-document text dump, prefer environment-native tools such as `textutil` (DOCX on macOS) or `pdftotext` when available. Use this CLI when those are unavailable, a partial range is needed, or structured DOCX → Markdown conversion is required.

## Image-to-image (i2i)

The `image` command supports image-to-image generation via `--ref` (single) or `image_refs` (batch). Two scenarios share the same interface:

| Scenario | Example | Provider support |
|---|---|---|
| **A. Instruction-based editing** | Change poster text, add/remove elements | openai (default), gemini |
| **B. Reference-driven generation** | Photo → cartoon avatar, product → scene | openai (default), gemini |

- `--ref` is repeatable (max 4). The first ref is the primary image; a second ref serves as a mask (OpenAI) or additional reference (Gemini).
- `agnes` does **not** support i2i — requests with refs raise `provider_capability_unsupported`.
- Per-segment `image_refs` in batch JSON takes precedence over CLI `--ref`. Segments without `image_refs` use text-to-image — **mixed batches are fully backward compatible**.

### Compliance

**Only process images you own or have explicit authorization to modify.**
Do not use i2i to remove watermarks from others' work, forge attribution, or bypass copyright protection. This skill is designed for in-house content production — if a request is clearly aimed at infringing someone else's rights, refuse it.

## Configuration and references

Providers and defaults are configured in the shared `skills/.env`. The CLI needs this file at runtime, which is another reason it cannot run inside the sandbox. Switching `IMAGE_PROVIDER` (`openai`, `gemini`, or `agnes`), `VIDEO_PROVIDER`, or `SPEECH_PROVIDER` does not change the CLI commands. Agnes image generation uses its own `AGNES_API_KEY`, `AGNES_IMAGE_BASE_URL`, `AGNES_IMAGE_MODEL`, and `AGNES_IMAGE_SIZE` settings, so Adventure Academy's `IMAGE_*` settings can target SiliconFlow without changing this provider.

- [cli-reference.md](references/cli-reference.md) — schema, arguments, supported formats, and configuration
- [examples.md](references/examples.md) — media-generation examples
- [architecture.md](references/architecture.md) — pipeline and downstream consumers
- [article-guide.md](references/article-guide.md) — optional Agent-native article guidance
- [prompt-guide.md](references/prompt-guide.md) — effective image/video prompts
