# RBH Skills

Backend skills for the RBH Agent learning platform. Each skill is an independent Python module — most expose REST APIs for the frontend, while some are used internally by Claude Code.

## Skills

| Skill | Type | Description |
|-------|------|-------------|
| **sms-auth** | API | SMS verification for authentication (send + verify) |
| **story-generation** | API | AI-powered story generation with branching support based on Critical Thinking answers |
| **project-creation** | Internal | Generate Project model data and sync to Supabase (Claude Code only) |
| **content-production** | Agent Skill | **Primary** — Generate images/video via Agnes AI, speech via Fish Speech, caption images. Local Agent creates JSON from user prompts directly, then content-production generates assets. |
| **video-converter** | Agent Skill | Composite images + audio into MP4 video segments, then concatenate into a final video. Last step of the pipeline, receives assets from content-production. |

## Tech Stack

- Python 3.12+
- FastAPI + Uvicorn
- LLM: Agnes AI (text + image), SiliconFlow (speech)

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
           └── creates segments.json directly from user prompts
                  │
                  ▼
            content-production (image/video/speech generation)
                  │
                  ▼
            video-converter (video compositing + concat)
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

| Method | Route | Skill | Description |
|--------|-------|-------|-------------|
| POST | `/api/auth/sms/send` | sms-auth | Send SMS verification code |
| POST | `/api/auth/sms/verify` | sms-auth | Verify SMS code, return auth info |
| POST | `/api/story/generate` | story-generation | Generate story matching user profile, supports branching via require_story_id/require_choice params |
