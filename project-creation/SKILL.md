---
name: project-creation
description: "Generate Project data via LLM and sync to Supabase. Use when creating new projects from a natural language prompt."
---

# Project Creation

Generates project data (title, description) from a natural language prompt using an LLM, then inserts the record into the Supabase `Project` table.

This is an **Internal Skill** — no API routes are registered. It is invoked directly by Claude Code.

## Use Cases

- Create a new Project from a topic description
- Brainstorm and persist a Project in one step

## How It Works

```
Prompt
  │
  ▼
LLM (SiliconFlow Chat Completions)
  │
  ▼
JSON {title, description}
  │
  ▼
Supabase INSERT → Project table
```

## Database Schema

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| `id` | String (CUID) | Auto | Primary key |
| `title` | String | Yes | Project title |
| `description` | String | No | Project description |
| `createdAt` | DateTime | Auto | Creation timestamp |
| `updatedAt` | DateTime | Auto | Update timestamp |

## Scripts

### `scripts/project.py`

| Function | Description |
|----------|-------------|
| `generate_project(prompt)` | Call LLM to generate `{"title", "description"}` from a prompt |
| `insert_project(title, description?)` | Insert a row into Supabase `Project` table |
| `generate_and_sync_project(prompt)` | Combined flow: generate via LLM then insert into Supabase |

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
    "project", Path("project-creation/scripts/project.py")
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

result = mod.generate_and_sync_project("A community garden app for urban neighborhoods")
# → {"id": "...", "title": "GreenSpace", "description": "...", ...}
```

## Dependencies

All dependencies are declared in the root `requirements.txt`.
