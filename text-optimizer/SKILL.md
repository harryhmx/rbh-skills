---
name: text-optimizer
description: "Split long text into semantically coherent segments, or optimize text (summarize/expand/refine) and generate image/video prompts. Accepts raw text or file input (md/txt), outputs structured JSON segments with optional prompts. Use when preparing articles, stories, or long-form content for multi-segment publishing, or transforming text into prompts for content production."
version: "0.4.0"
allowed-tools: ["Bash", "Read", "Write"]
---

# Text Optimizer

Splits long text into semantically coherent segments, or transforms text (summarize, expand, refine) and generates image/video prompts — an **optional pre-processing step** in the RBH content production pipeline. Not the default path: if the user already has prompts, skip directly to `content-production`.

**Always AI-powered.** The full text + all requirements are sent to the AI in a single prompt. The model sees the whole picture and returns finished segments in one response.

## What this skill does

1. **Reads** long text from direct input or `.md` / `.txt` files
2. **Splits** text at natural semantic boundaries (file input only)
3. **Optimizes** text — summarize long content, expand short content, or refine for readability
4. **Generates** image/video prompts for each segment
5. **Outputs** structured segments as JSON

### Splitting principles

Every segment must satisfy:
- **Self-contained**: a reader can understand the segment without seeing the others
- **Semantically coherent**: all sentences within a segment belong to the same sub-topic
- **Balanced**: segments should be roughly similar in length (unless a natural boundary dictates otherwise)
- **Natural boundaries only**: never split mid-sentence or mid-paragraph

## When to use it

Trigger this skill when the user asks to:
- "Split / break / segment this article / text / content"
- "Divide this into N parts / sections"
- "Prepare this article for content production"
- "Summarize / expand / refine this text"
- "Generate image/video prompts from this text"

## When to SKIP it (go directly to content-production)

**Most content generation tasks do NOT need text-optimizer.** Skip this skill and use `content-production` directly when:

- The user already has image/video prompts and just wants to generate content
- The user says "generate images from these prompts" or "create a video of..."
- The user provides specific visual/audio descriptions (not raw long-form text)
- The Local Agent can directly create the segments JSON from user prompts

Only use text-optimizer when the user **explicitly** asks for:
- "Split / break / segment this text"
- "Optimize / summarize / expand / refine this text"
- "Generate image/video prompts from this article"

## When NOT to use it

- **Code refactoring / splitting source files** — this skill is for natural language text, not code
- **Translation** — this skill does not translate text
- **File format conversion** (e.g., PDF → MD) — use `content-extractor` (A5, Stage 6)
- **Short text** (< 100 words) for splitting — use `optimize` instead
- **User already has specific prompts** — skip directly to `content-production`

## How to invoke

### Native Claude Code (zero-setup, always works)

When invoked from Claude Code, Claude itself acts as the AI — reading the text, analyzing semantic boundaries, and producing segments directly. No API keys or Python environment needed.

**From direct text:**
```
Split this article into 4 segments:
<article text>
```

**From a file:**
```
Split /path/to/article.md into 4 segments
```

**Claude Code's procedure:**

1. **Read** the input (user message or file via `Read` tool)
2. **Analyze** semantic structure: paragraph boundaries, topic shifts, section headings, narrative flow
3. **Determine segment count** (user-specified or auto: ~150-300 words per segment)
4. **Output** in JSON format

### Python Environment

Activate the shared virtual environment before running any Python CLI commands:

```bash
source ../.venv/bin/activate
```

### Python CLI

Three subcommands: `split`, `optimize`, and `prompts`.

#### `split` — Semantic text segmentation (file input only)

Splits a `.md` or `.txt` file into semantically coherent segments. No word/character length limits — the AI splits at natural boundaries. Use `--extra-requirements` for additional constraints.

```bash
# Auto segment count, JSON to stdout
python scripts/cli.py split -i article.md

# 4 segments with extra requirements
python scripts/cli.py split -i article.md -n 4 --extra-requirements "use simple language for children"

# Split AND generate image + video prompts
python scripts/cli.py split -i article.md -n 4 --prompts --prompt-types image,video -o result.json

```

**CLI arguments:**

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Path to .md or .txt file (required) | — |
| `--segments` | `-n` | Target number of segments (omit for auto) | `None` (auto) |
| `--output` | `-o` | Output JSON file path (omit to print to stdout) | `None` (stdout) |
| `--prompts` | | Also generate image/video prompts via AI | `False` |
| `--prompt-types` | | Comma-separated prompt types: `image`, `video`, or `all` | `all` |
| `--extra-requirements` | | Additional requirements for the AI prompt | `""` |

**Output format (JSON):**

```json
{
  "total_segments": 4,
  "segments": [
    {
      "index": 0,
      "title": "Opening Scene",
      "text": "Segment text content...",
      "image_prompt": "A wide shot of...",
      "video_prompt": "Fade in from black..."
    }
  ]
}
```

Required fields: `index`, `title`. Optional fields (added when `--prompts` is used): `text`, `image_prompt`, `video_prompt`.

#### `optimize` — Unified text optimization and prompt generation

Replaces the old `genprompt` and `multiprompt` commands. Transforms text via AI: summarize long content, expand short content, refine readability, or generate image/video prompts. Default mode: single segment with only the `text` field.

```bash
# Default: optimize text (summarize/expand as needed), single segment
python scripts/cli.py optimize -i article.md

# Expand short text
python scripts/cli.py optimize -i "A short description." --direction expand

# Summarize long text into 3 segments
python scripts/cli.py optimize -i article.md -n 3 --direction summarize

# Generate 4 different image prompts from text (no text field)
python scripts/cli.py optimize -i article.md -n 4 --fields image_prompt -o prompts.json

# Generate text + image_prompt + video_prompt
python scripts/cli.py optimize -i article.md --fields text,image_prompt,video_prompt

# All fields with extra requirements
python scripts/cli.py optimize -i article.md --fields all --extra-requirements "for children aged 8-10"

# Pipe from stdin
echo "A short text to optimize" | python scripts/cli.py optimize
```

**CLI arguments:**

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Raw text string, path to .md/.txt file, or stdin | required |
| `--segments` | `-n` | Number of segments (1 = single, > 1 = multiple versions) | `1` |
| `--output` | `-o` | Output JSON file path (omit for stdout) | `None` |
| `--fields` | | Fields to generate: `text`, `image_prompt`, `video_prompt` (comma-separated, or `all`) | `text` |
| `--direction` | | Text transformation: `auto`, `summarize`, `expand`, `refine` | `auto` |
| `--extra-requirements` | | Additional requirements for the AI prompt | `""` |

#### `prompts` — Add prompts to existing segments JSON

Takes a segments JSON file (from `split` or `optimize`) and generates prompt fields for each segment.

```bash
# Generate all prompt types
python scripts/cli.py prompts -i segments.json -o with-prompts.json

```

**CLI arguments:**

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Path to segments JSON file | required |
| `--output` | `-o` | Output JSON file path | `None` (stdout) |
| `--prompt-types` | | Comma-separated: `image`, `video`, or `all` | `all` |

### Prompt field descriptions

**`text`** — The optimized/transformed text content. Summarized for long input, expanded for short input, or refined for readability. Also serves as the speech content for audio generation.

**`image_prompt`** — Visual description for AI image generation (Stable Diffusion, DALL·E, etc.):
- 2-4 sentences in English, describing the scene VISUALLY
- Includes: subjects, setting, composition, lighting, color palette

**`video_prompt`** — Scene description for AI video generation (Runway, Pika, Sora):
- 2-4 sentences in English, describing motion and action
- Includes: camera movement, pacing, transitions

## Migration from old commands (v0.3.x)

| Old command | New command |
|---|---|
| `split -i file.md -n 4 --max-words 200 -f json` | `split -i file.md -n 4 --extra-requirements "each under 200 words"` |
| `genprompt -t image -i text` | `optimize -i text --fields image_prompt` |
| `genprompt -t video -i file.md -o prompt.md` | `optimize -i file.md --fields video_prompt -o output.json` |
| `multiprompt -t image -i text -n 4` | `optimize -i text -n 4 --fields image_prompt` |
| `multiprompt -t video -i file.md -n 6` | `optimize -i file.md -n 6 --fields video_prompt` |
| `content-production single -i prompt.md` | `optimize -i text -n 1 --fields image_prompt -o seg.json` then `content-production image -i seg.json` |

## Configuration

The Python CLI requires these environment variables (from `skills/.env` or system env):

| Variable | Description | Required |
|----------|-------------|----------|
| `TEXT_API_KEY` | Agnes AI API key | **Yes** |
| `TEXT_BASE_URL` | Agnes AI API base URL | Default: `https://apihub.agnes-ai.com` |
| `TEXT_CHAT_MODEL` | Model for text processing | Default: `agnes-2.0-flash` |

**Native Claude Code requires no configuration** — Claude's built-in LLM handles everything.

## Architecture

```
User Input (text / file + requirements)
        │
        │  ┌─ User already has prompts? ── YES ──> Skip text-optimizer
        │  │                                      Use content-production directly
        │  │
        │  └─ NO: raw text needs processing
        │
        ├── Native Claude Code ──> Claude reads SKILL.md, receives the full
        │                          text + requirements in one turn, outputs result
        │
        └── CLI (scripts/cli.py)
                │
                ├── split ──> _ai_split() ──> ONE prompt to Agnes AI
                │                    │           full text + segment count
                │                    │           returns: finished segments
                │                    │
                │                    └── + --prompts ──> generate_prompts()
                │                                          │
                │                                          └── ONE prompt → AI returns
                │                                              image_prompt/video_prompt
                │                                              for all segments
                │
                ├── optimize ──> optimize_text()
                │                    │
                │                    └── ONE prompt → AI returns
                │                        text/image_prompt/video_prompt
                │                        in 1 to N segment(s)
                │
                └── prompts ──> generate_prompts()
                                     │
                                     └── add prompt fields to existing segments JSON
```

## Output consumed by

- **content-production (A2)**: receives segments + prompts for image/video/audio generation via `segments.json`
- **Direct publishing**: JSON output published directly or further processed
- **Programmatic processing**: JSON output for downstream automation

## Dependencies

- Native mode: none (Claude Code handles everything)
- CLI mode: Python 3.10+, `requests`, `python-dotenv` (in skills root `requirements.txt`)
