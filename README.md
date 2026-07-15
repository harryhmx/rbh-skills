# RBH Skills

Python-based skill modules for the RBH platform — each skill is a self-contained module providing specific capabilities via FastAPI routes (for online RBH Agent) and/or CLI commands (for local Agent usage). Part of the RBH Brand AI education ecosystem.

## Skills Overview

| Skill | Type | Description |
|-------|------|-------------|
| **rbh-core** | API + CLI | SMS authentication (Aliyun), User management (registration/login), Project generation (LLM + Supabase sync). Provides both FastAPI routes and CLI for conversational Agent usage. |
| **adventure-academy** | API | Story generation engine with branching chapters, RC/CT questions, cover images, and audio narration for gamified English learning. |
| **content-production** | Agent Skill | Generate images/video/speech via pluggable providers (Agnes AI, Gemini/Veo, Fish Speech); extract plain text from DOCX/PDF; convert DOCX to Markdown. Local Agent creates or edits TXT/MD/JSON/... files from user prompts directly. |
| **media-composer** | Agent Skill | Media editing toolkit: STT transcription (MLX Whisper), caption/title overlay, trim, extract-audio, replace-segment, replace-bg (RVM matting), enhance (loudnorm), subtitle-burn, composite (image+audio → segments), concat. Last step of the pipeline. |

## Quick Start

### Prerequisites

- Python 3.12+
- Git
- ffmpeg ≥ 5.0 (required for media-composer skill)
  - macOS: `brew install ffmpeg` or `brew install ffmpeg-full` (for subtitle-burn)
  - Linux: `apt install ffmpeg` or build with libass for subtitle support
  - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)
- Access to required API services (Aliyun, LLM providers, Supabase)

### Installation

**Option 1: Manual Setup**

```bash
# Clone repository
git clone <your-repo-url>
cd skills

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# For local Agent development (includes mlx-whisper, torch, etc.)
pip install -r requirements-local.txt

# Set up environment variables (see below)
cp .env.example .env
# Edit .env with your credentials
```

**Option 2: One-Click Setup with Agent**

Simply ask your local agent (Claude Code / Codex / etc.):

> "Help me set up the RBH Skills project following the README instructions"

The agent will create the virtual environment, install dependencies, and guide you through environment configuration.

### Environment Configuration

Create a `.env` file in the `skills/` directory with the following content:

```env
# ========== SMS Authentication (Aliyun) ==========
ALIBABA_CLOUD_ACCESS_KEY_ID=your-aliyun-access-key-id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your-aliyun-access-key-secret

# ========== LLM Configuration ==========
# SiliconFlow AI (or compatible OpenAI API endpoint)
TEXT_API_KEY=your-llm-api-key
TEXT_BASE_URL=https://api.siliconflow.cn/v1
TEXT_CHAT_MODEL=Qwen/Qwen2.5-7B-Instruct

# ========== Database (Supabase) ==========
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-service-role-key

# ========== Content Production ==========
# Image generation (Agnes AI)
IMAGE_API_KEY=your-agnes-ai-api-key
IMAGE_BASE_URL=https://apihub.agnes-ai.com
IMAGE_MODEL=agnes-imagine-pro

# Video generation (Gemini/Veo or compatible)
VIDEO_API_KEY=your-video-api-key
VIDEO_BASE_URL=https://generativelanguage.googleapis.com/v1beta
VIDEO_MODEL=gemini-2.0-flash-exp

# Speech synthesis (Fish Speech or compatible)
SPEECH_API_KEY=your-speech-api-key
SPEECH_BASE_URL=https://api.fish.audio/v1
SPEECH_MODEL=fish-speech-1.4
SPEECH_VOICE_ID=your-voice-id

# ========== Session Management ==========
JWT_SECRET=your-jwt-secret-min-32-chars-recommended
```

**Important Notes:**
- Replace all `your-*` placeholders with actual credentials
- `JWT_SECRET` should be at least 32 characters for security
- `SUPABASE_KEY` requires service role key (not anon key) for admin operations
- Keep `.env` file secure and never commit it to version control

### Running the Server

```bash
# Activate virtual environment
source .venv/bin/activate

# Start FastAPI development server
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at `http://localhost:8000`

### Health Check

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

## Architecture

```
RBH Frontend (Next.js, Vercel)
    │
    ├──> RBH Skills API (FastAPI, Railway)
    │       ├── rbh-core          ──> SMS Service (Aliyun)
    │       │                      ──> LLM (Project generation)
    │       └── adventure-academy ──> LLM (Story generation)
    │                              ──> Media generation
    │
    └──> Supabase (PostgreSQL)
         ↑
    Claude Code CLI (rbh-core)  ──> Local user management
    
Content Production Pipeline:
  Local Agent (Claude Code)
       │
       ├── creates segments.json ──> content-production (image/video/speech)
       │                                     │
       │                                     ▼
       │                               media-composer (compositing + concat + editing)
       │
       └── records audio / shoots video ──> media-composer (STT transcribe)
                                                    │
                                                    ▼
                                              transcript.md → Agent organizes → Article
```

## API Endpoints

| Method | Route | Skill | Description |
|--------|-------|-------|-------------|
| GET | `/health` | - | Health check endpoint |
| POST | `/api/auth/sms/send` | rbh-core | Send SMS verification code |
| POST | `/api/auth/sms/verify` | rbh-core | Verify SMS code |
| POST | `/api/story/generate` | adventure-academy | Generate story with branching support |
| GET | `/api/story/status/{story_id}` | adventure-academy | Check story media generation status |

## CLI Usage (rbh-core)

The `rbh-core` skill provides a CLI for local user management with conversational Agent support.

```bash
source .venv/bin/activate

# Authentication
python rbh-core/scripts/cli.py auth register --username <user> --password <pwd>
python rbh-core/scripts/cli.py auth login --username <user> --password <pwd>
python rbh-core/scripts/cli.py auth send-sms --phone <phone>
python rbh-core/scripts/cli.py auth login-sms --username <user> --phone <phone> --code <code>
python rbh-core/scripts/cli.py auth logout
python rbh-core/scripts/cli.py auth whoami

# Project generation (requires login)
python rbh-core/scripts/cli.py project generate --prompt "Create a story about..."
```

**Note:** CLI commands are designed for Agent usage. Simply ask your agent:

> "Help me login to RBH platform"

The agent will guide you through the conversational flow and execute commands with your input.

## Development Tips

### Testing Individual Skills

Each skill has its own `SKILL.md` documentation:

- `rbh-core/SKILL.md` — CLI usage and Agent conversational flows
- `adventure-academy/SKILL.md` — Story generation API specs
- `content-production/SKILL.md` — Content generation workflows
- `media-composer/SKILL.md` — Media editing commands

### Common Issues

**1. Import errors after renaming directories**

```bash
# Clear Python cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
```

**2. JWT warnings about key length**

Set `JWT_SECRET` to at least 32 characters in `.env`

**3. Virtual environment not found**

```bash
# Recreate virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Tech Stack

- **Framework**: FastAPI + Uvicorn
- **Language**: Python 3.12+
- **Database**: Supabase (PostgreSQL) via Prisma-compatible schema
- **Authentication**: Aliyun SMS + JWT sessions
- **LLM**: SiliconFlow AI, Agnes AI (image), Gemini (video), Fish Speech (audio)
- **Media Processing**: ffmpeg, Pillow, MLX Whisper (local), PyTorch (RVM matting)

## Contributing

1. Each skill should be independent and self-contained
2. Follow the SKILL.md documentation format
3. Use `importlib` for dynamic imports to support kebab-case directory names
4. Keep CLI commands parameterized (no interactive prompts) for Agent usage
5. Document all API routes and CLI commands
