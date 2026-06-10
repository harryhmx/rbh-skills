---
name: text-optimizer
description: "Split long text into semantically coherent segments for content production, or generate single image/video prompts from text. Accepts raw text or file input (md/txt), outputs structured segments with optional image/video/TTS prompts, or outputs a single prompt in proprietary format for content-production. Use when preparing articles, stories, or long-form content for multi-segment publishing, when asked to 'split this article into parts', 'break this text into sections', 'generate a prompt for this text', or 'create an image/video prompt from this article'."
version: "0.2.0"
allowed-tools: ["Bash", "Read", "Write"]
---

# Text Optimizer

Splits long text into semantically coherent segments — the entry point of the RBH content production pipeline. Each output segment is self-contained and suitable for downstream processing (image generation, video synthesis, cross-platform publishing).

**Always AI-powered.** The full text + all requirements (segment count, word/char limits) are sent to the AI in a single prompt. The model sees the whole picture and returns finished segments in one response — no multi-step split-then-condense, no heuristic fallbacks.

## What this skill does

1. **Reads** long text from direct input or `.md` / `.txt` files
2. **Splits** the text at natural semantic boundaries
3. **Condenses** segments to fit within word/character limits (when specified)
4. **Outputs** structured segments as JSON, Markdown, or plain text
5. **Generates** (optionally) image/video/TTS prompts with strict format requirements for each medium — feeding into `content-production`
6. **Generates single prompts** — transform any text into a single image or video prompt, output in a proprietary format that `content-production single` can consume directly

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
- "Chunk this text for processing"
- Read a `.md` or `.txt` file and split its contents
- "Generate a prompt for this text" (single image/video prompt)
- "Create an image prompt from this article"
- "Turn this into a video prompt"

## When NOT to use it

- **Code refactoring / splitting source files** — this skill is for natural language text, not code
- **Summarization** — use the `summarize` skill instead
- **Translation** — this skill does not translate text
- **File format conversion** (e.g., PDF → MD) — use `content-extractor` (A5, Stage 6)
- **Short text** (< 100 words) — splitting is unnecessary; output the text as-is

## How to invoke

### Native Claude Code (zero-setup, always works)

When invoked from Claude Code, Claude itself acts as the AI — reading the text, analyzing semantic boundaries, and producing segments directly. No API keys or Python environment needed.

**From direct text:**
```
Split this article into 4 segments, each under 200 words:
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
4. **Apply length limits** if requested — condense while preserving key facts, tone, and core message
5. **Output** in the requested format

**Quality checks:**
- Each segment is self-contained
- No mid-sentence splits
- Logical flow preserved
- When condensing: key facts, tone, and core message are preserved

### Python CLI (for other Agents, batch processing, and REST API wrapping)

```bash
# Auto segment count, JSON to stdout
python scripts/cli.py split -i article.md

# 4 segments with word-count limit (one AI call handles both)
python scripts/cli.py split -i article.md -n 4 --max-words 200 -f md

# Split AND generate all image/video/TTS prompts
python scripts/cli.py split -i article.md -n 4 --prompts -f json -o result.json

# Split and generate only image prompts
python scripts/cli.py split -i article.md -n 4 --prompts --prompt-types image -f json

# Split and generate image + TTS prompts (skip video)
python scripts/cli.py split -i article.md -n 4 --prompts --prompt-types image,tts -f json

# Character-count limit for CJK text, write to file
python scripts/cli.py split -i article.md --max-chars 500 -f json -o result.json

# From stdin
cat article.md | python scripts/cli.py split -n 3 -f text

# Generate prompts from an existing segments JSON file
python scripts/cli.py prompts -i segments.json -o prompts.json

# Generate only TTS prompts from existing segments
python scripts/cli.py prompts -i segments.json --prompt-types tts
```

**CLI arguments:**

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Raw text string OR path to .md/.txt file (omit for stdin) | (stdin) |
| `--segments` | `-n` | Target number of segments (omit for auto) | `None` (auto) |
| `--format` | `-f` | Output format: `json`, `md`, or `text` | `json` |
| `--output` | `-o` | Output file path (omit to print to stdout) | `None` (stdout) |
| `--max-words` | | Max words per segment — AI condenses if exceeded | `None` (no limit) |
| `--max-chars` | | Max characters per segment (useful for CJK) | `None` (no limit) |
| `--prompts` | | Also generate image/video/TTS prompts via AI | `False` |
| `--prompt-types` | | Comma-separated prompt types: `image`, `video`, `tts`, or `all` | `all` |

### `prompts` subcommand

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Path to segments JSON file (from `split` command) | (required) |
| `--output` | `-o` | Output file path (omit to print to stdout) | `None` (stdout) |
| `--prompt-types` | | Comma-separated prompt types: `image`, `video`, `tts`, or `all` | `all` |

### `genprompt` subcommand — single prompt generation

Generate a single image or video prompt from raw text or file content. The output uses a proprietary YAML-like frontmatter format that `content-production single` can consume.

```bash
# Generate a single image prompt to stdout
python scripts/cli.py genprompt -t image -i "A classroom scene with students"

# Generate from a file, save to output
python scripts/cli.py genprompt -t image -i article.md -o my-image-prompt.md

# Generate a single video prompt from file content
python scripts/cli.py genprompt -t video -i article.md -o my-video-prompt.md

# Video with custom settings
python scripts/cli.py genprompt -t video -i article.md --size 1920x1080 --num-frames 241 --frame-rate 30
```

**Output format (proprietary RBH prompt file):**

```markdown
---
type: image
size: 1024x768
---

A wide shot of a sunlit classroom with students engaged...
```

Video prompt files additionally include `num_frames` and `frame_rate` frontmatter keys.

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--input` | `-i` | Raw text string or path to .md/.txt file | (required) |
| `--type` | `-t` | Prompt type: `image` or `video` | (required) |
| `--output` | `-o` | Output file path (.md/.txt). Omit to print to stdout. | `None` (stdout) |
| `--size` | | Target size `WxH` | `1024x768` |
| `--num-frames` | | Number of frames (video only) | `121` |
| `--frame-rate` | | Frame rate in FPS (video only) | `24` |

### Segment length control

Constrain each segment to a maximum word or character count:

- **`--max-words N`**: AI condenses segments to ≤N words
- **`--max-chars N`**: AI condenses segments to ≤N characters
- **Both set**: the stricter limit applies

The AI handles splitting AND condensation in a single pass — it sees the whole text and makes smarter decisions than a two-step split-then-condense pipeline would.

Use cases:
- Social media posts (e.g., WeChat ~140 chars)
- Video scripts (30 seconds ≈ 100 words per segment)
- Platform constraints (Xiaohongshu description limits)

### Prompt generation

When `--prompts` is used (or the `prompts` subcommand), the AI transforms each segment into professionally formatted prompts for three downstream tools. A single API call processes all segments.

#### Prompt format requirements

**Image prompt (`image_prompt`)** — suitable for Stable Diffusion, DALL·E, Midjourney, Flux:
- 2-4 sentences in English, describing the scene VISUALLY
- Includes: subjects, setting, actions, art style ("colorful children's book illustration"), composition, lighting, color palette
- Only what can be drawn/illustrated — no abstract concepts

**Video prompt (`video_prompt`)** — suitable for Runway, Pika, Sora:
- 2-4 sentences in English, describing motion and action
- Includes: camera movement, pacing, transitions (fade in/out)

**TTS prompt (`tts_prompt`)** — natural spoken narration:
- Same language as the original text
- Starts with a voice direction: `(warm and gentle tone, moderate pace)`
- Adjusted for natural speech flow

#### Selective generation

Use `--prompt-types` to generate only the prompts you need:

```bash
# Image prompts only
python scripts/cli.py split -i article.md --prompts --prompt-types image -f json

# Image + TTS, skip video
python scripts/cli.py split -i article.md --prompts --prompt-types image,tts -f json

# TTS only from existing segments
python scripts/cli.py prompts -i segments.json --prompt-types tts
```

## Examples

### Example 1: Native Claude Code — auto segments

**Input:**
```
Split this into segments:

人工智能正在改变教育的方方面面。从个性化学习路径到智能辅导系统，
AI技术让每个学生都能获得量身定制的学习体验...

然而，AI在教育中的应用也面临诸多挑战。数据隐私、算法偏见...

展望未来，AI与教育的融合将更加深入。自适应学习系统...
```

**Output (3 segments, auto-determined):**

- **Segment 1** (AI改变教育): 人工智能正在改变教育的方方面面...
- **Segment 2** (挑战与隐忧): 然而，AI在教育中的应用也面临诸多挑战...
- **Segment 3** (未来展望): 展望未来，AI与教育的融合将更加深入...

### Example 2: CLI — file input with length limits

```bash
$ python scripts/cli.py split -i article.md -n 4 --max-words 200 -f md -o result.md
```

### Example 3: CLI — JSON output structure

```json
{
  "total_segments": 4,
  "segments": [
    {
      "index": 0,
      "title": "开篇引入",
      "text": "Segment text content...",
      "word_count": 180,
      "char_count": 520
    }
  ]
}
```

## Configuration

The Python CLI requires these environment variables (from `skills/.env` or system env):

| Variable | Description | Required |
|----------|-------------|----------|
| `TEXT_API_KEY` | Agnes AI API key | **Yes** |
| `TEXT_BASE_URL` | Agnes AI API base URL | Default: `https://apihub.agnes-ai.com` |
| `TEXT_CHAT_MODEL` | Model for splitting | Default: `agnes-2.0-flash` |

**Native Claude Code requires no configuration** — Claude's built-in LLM handles everything.

## Architecture

```
User Input (text / file + requirements: segments, max_words, max_chars)
        │
        ├── Native Claude Code ──> Claude reads SKILL.md, receives the full
        │                          text + requirements in one turn, outputs result
        │
        └── CLI (scripts/cli.py)
                │
                ├── split ──> _ai_split() ──> ONE prompt to Agnes AI
                │                    │           full text + segment count + limits
                │                    │           returns: finished segments
                │                    │
                │                    └── + --prompts ──> generate_prompts()
                │                                          │
                │                                          └── ONE prompt → AI returns
                │                                              image/video/TTS prompts
                │                                              for all segments at once
                │
                ├── prompts ──> generate_prompts() ──> process existing
                │                 segments JSON → add prompt fields
                │
                └── genprompt ──> generate_single_prompt()
                                       │
                                       └── ONE prompt → AI returns
                                           single image or video prompt
                                           └── format_prompt_file()
                                                 └── proprietary .md/.txt
                                                     → content-production single
```

## Output consumed by

- **content-production (A2)**: receives segments + prompts for image/video/audio generation via `segments.json`, OR receives single prompt files (`.md`/`.txt`) via the proprietary `genprompt` format for single image/video generation
- **Direct publishing**: Markdown output published directly to RBH Agent Blog/Skills pages
- **Programmatic processing**: JSON output for downstream automation

## Dependencies

- Native mode: none (Claude Code handles everything)
- CLI mode: Python 3.10+, `requests`, `python-dotenv` (in skills root `requirements.txt`)
