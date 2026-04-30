---
name: story-generation
description: "Generate Story data via LLM and sync to Supabase. Use when creating new stories from project context and user profile."
---

# Story Generation

Generates story data (title, content) from a project and user profile using an LLM, then inserts the record into the Supabase `Story` table.

This is an **Internal Skill** — no API routes are registered. It is invoked directly by Claude Code.

## Use Cases

- Create a new Story for a Project based on a user's age and reading level
- Generate age-appropriate, level-appropriate story content from project context

## How It Works

```
Project (title, description) + User (age, level)
  │
  ▼
LLM (SiliconFlow Chat Completions)
  │
  ▼
JSON {title, content}
  │
  ▼
Supabase INSERT → Story table
```

## Input Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `project_title` | Project.title | The project's title |
| `project_description` | Project.description | The project's description |
| `user_age` | User.age | The user's age |
| `user_level` | User.level | The user's Lexile Level |

## Database Schema

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| `id` | String (CUID) | Auto | Primary key |
| `title` | String | Yes | Story title |
| `content` | String | Yes | Story content in markdown (max 100 words) |
| `projectId` | String | Yes | Foreign key to Project |
| `createdAt` | DateTime | Auto | Creation timestamp |
| `updatedAt` | DateTime | Auto | Update timestamp |

## Scripts

### `scripts/story.py`

| Function | Description |
|----------|-------------|
| `generate_story(project_title, project_description, user_age, user_level)` | Call LLM to generate `{"title", "content"}` from project and user context |
| `insert_story(title, content, project_id)` | Insert a row into Supabase `Story` table |
| `generate_and_sync_story(project_title, project_description, user_age, user_level, project_id)` | Combined flow: generate via LLM then insert into Supabase |

## Configuration

| Setting | Description |
|---------|-------------|
| `LLM_API_KEY` | SiliconFlow API key |
| `LLM_BASE_URL` | `https://api.siliconflow.cn/v1` |
| `LLM_CHAT_MODEL` | `Qwen/Qwen2.5-72B-Instruct` |

## Example Usage

```python
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "story", Path("story-generation/scripts/story.py")
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

result = mod.generate_and_sync_story(
    project_title="Ocean Explorer",
    project_description="An underwater adventure game",
    user_age=8,
    user_level="beginner",
    project_id="abc123",
)
# → {"id": "...", "title": "The Deep Blue", "content": "# Chapter 1\n...", ...}
```

## Dependencies

All dependencies are declared in the root `requirements.txt`.
