---
name: adventure-academy
description: "Generate branching Adventure Academy story chapters for RBH learners. Uses SiliconFlow for text, image, and speech generation, stores stories in Supabase, and supports RC/CT questions, continuation branches, conclusion chapters, and media status checks."
version: "1.1.0"
allowed-tools: ["Bash", "Read", "Write"]
---

# Adventure Academy

Adventure Academy is RBH's story-based learning project. This skill generates a short, age- and Lexile-aware chapter, stores it in the Supabase `Story` table, and creates illustration and narration media asynchronously.

## API routes

The routes are served by the repository-level `server.py`:

```text
POST /api/story/generate
GET  /api/story/status/{story_id}
```

There is no standalone CLI for this skill yet. The RBH Core Next.js app calls these routes when a learner starts a story or submits a branching choice.

## Generation flow

```text
RBH Project + learner profile
        │
        ▼
SiliconFlow chat completion (story JSON)
        │
        ▼
Supabase Story row
        │
        ├── SiliconFlow image generation → adventure-academy/images/{story_id}.png
        └── SiliconFlow speech generation → adventure-academy/audio/{story_id}.mp3
```

Text generation runs in the request. Image and audio generation run as background work; the Core app polls `/api/story/status/{story_id}` until both media URLs are available.

Existing stories are reused for the same project, age, level, and branch constraints. A request with `fresh_story: true` bypasses that lookup.

## Request body

| Field | Required | Description |
|-------|----------|-------------|
| `project_title` | Yes | Project title |
| `project_description` | Yes | Project context |
| `user_age` | Yes | Learner age |
| `user_level` | Yes | Learner Lexile level or reading level |
| `project_id` | Yes | Core project identifier |
| `project_slug` | No | Slug used to resolve the remote Supabase Project ID |
| `require_story_id` | No | Parent story ID for a branch |
| `require_choice` | No | Choice that led to the branch |
| `depth` | No | Chapter depth; every fourth chapter is a conclusion |
| `parent_story_title` | No | Previous chapter title |
| `parent_story_content` | No | Previous chapter content |
| `system_prompt` | No | Project-specific story prompt override |
| `conclusion_prompt` | No | Project-specific conclusion prompt override |
| `fresh_story` | No | Skip existing-story lookup |

The generated story contains `title`, `content`, `rcQuestion`, `rcAnswer`, and `ctQuestion`. Conclusion chapters contain only `title` and `content`.

## Storage

All Adventure Academy media uses the Supabase Storage bucket:

```text
adventure-academy/
├── images/{story_id}.png
└── audio/{story_id}.mp3
```

SiliconFlow image responses may contain short-lived URLs under `images[].url`; the skill downloads each image immediately and uploads it to the bucket.

## Configuration

```env
TEXT_API_KEY=your-siliconflow-key
TEXT_BASE_URL=https://api.siliconflow.com/v1
TEXT_CHAT_MODEL=Qwen/Qwen3-32B

IMAGE_API_KEY=your-siliconflow-key
IMAGE_BASE_URL=https://api.siliconflow.com/v1
IMAGE_MODEL=black-forest-labs/FLUX.2-pro
IMAGE_SIZE=1024x768

SPEECH_API_KEY=your-siliconflow-key
SPEECH_BASE_URL=https://api.siliconflow.com/v1
SPEECH_MODEL=fishaudio/fish-speech-1.5
SPEECH_VOICE=fishaudio/fish-speech-1.5:anna

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
```

The code normalizes OpenAI-compatible base URLs, so both host-only URLs and URLs already ending in `/v1` are supported. Keep credentials in `skills/.env`; never commit them.

## Main modules

| File | Responsibility |
|------|----------------|
| `scripts/story.py` | Prompting, JSON validation, branch/conclusion logic, Story persistence |
| `scripts/image.py` | SiliconFlow image generation and Supabase image upload |
| `scripts/speech.py` | SiliconFlow narration and Supabase audio upload |
| `server.py` | FastAPI routes, remote project ID resolution, background media tasks |

## Dependencies

Install dependencies from the repository-level `requirements.txt`. The server requires FastAPI, Uvicorn, OpenAI-compatible client support, Supabase, and the SiliconFlow/Aliyun integrations configured by the environment.
