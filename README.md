# RBH Skills

Backend skills for the RBH Agent learning platform. Each skill is an independent Python module — most expose REST APIs for the frontend, while some are used internally by Claude Code.

## Skills

| Skill | Type | Description |
|-------|------|-------------|
| **sms-auth** | API | SMS verification for authentication (send + verify) |
| **story-generation** | API | AI-powered story generation with branching support based on Critical Thinking answers |
| **project-creation** | Internal | Generate Project model data and sync to Supabase (Claude Code only) |
| **content-production** | Agent Skill | Generate images/video/speech via pluggable providers (Agnes AI, Gemini/Veo, Fish Speech); extract plain text from DOCX/PDF; convert DOCX to Markdown. Local Agent creates or edits TXT/MD/JSON/... files from user prompts directly, then content-production generates assets. |
| **media-composer** | Agent Skill | Media editing toolkit: STT transcription (MLX Whisper), caption/title overlay, trim, extract-audio, replace-segment, replace-bg (RVM matting), enhance (loudnorm), subtitle-burn, composite (image+audio → segments), concat. Last step of the pipeline, receives assets from content-production. |

## Tech Stack

- Python 3.12+
- FastAPI + Uvicorn
- LLM: Agnes AI (text + image), Gemini (image/video/speech), SiliconFlow (speech)

## Architecture

```
RBH Agent Frontend (Next.js, Vercel)
    │
    ├──> RBH Skills (FastAPI, Railway)
    │       ├── sms-auth          ──> SMS Service
    │       └── story-generation  ──> LLM
    │
    └──> Supabase (PostgreSQL)
         ↑
    Claude Code ──> project-creation (Internal Skill)
    
    Content Production Pipeline:
      Local Agent (Claude Code / Codex)
           │
           ├── creates segments.json ──> content-production (image/video/speech)
           │                                     │
           │                                     ▼
           │                               media-composer (compositing + concat + editing)
           │
           └── records audio / shoots video ──> media-composer (STT transcribe)
                                                        │
                                                        ▼
                                                  transcript.md → Agent 整理 → 文章
```

## Development

```bash
# Server deployment (Railway / VPS) — minimal cross-platform deps
pip install -r requirements.txt

# Local Agent development (Mac) — includes mlx-whisper, torch, etc.
pip install -r requirements-local.txt

# Run development server
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

| Method | Route | Skill | Description |
|--------|-------|-------|-------------|
| POST | `/api/auth/sms/send` | sms-auth | Send SMS verification code |
| POST | `/api/auth/sms/verify` | sms-auth | Verify SMS code, return auth info |
| POST | `/api/story/generate` | story-generation | Generate story matching user profile, supports branching via require_story_id/require_choice params |
