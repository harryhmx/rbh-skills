# RBH Skills

Python-based skill modules for the RBH platform — each skill is a self-contained module providing specific capabilities via FastAPI routes (for online RBH Agent) and/or CLI commands (for local Agent usage). Part of the RBH Brand AI education ecosystem.

## Skills Overview

| Skill | Type | Description |
|-------|------|-------------|
| **rbh-core** | API + CLI | SMS authentication (Aliyun), User management (registration/login), Project generation (LLM + Supabase sync). Provides both FastAPI routes and CLI for conversational Agent usage. |
| **adventure-academy** | API | Story generation engine with branching chapters, RC/CT questions, cover images, and audio narration for gamified English learning. |
| **content-production** | Agent Skill | Generate images/video/speech via pluggable providers (Agnes AI, Gemini/Veo, OpenAI/gpt-image-2, Fish Speech); extract plain text from DOCX/PDF; convert DOCX to Markdown. Local Agent creates or edits TXT/MD/JSON/... files from user prompts directly. |
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

# Create a .env file
touch .env

# Then, manually open the .env file and edit with your credentials
```

**Option 2: One-Click Setup with Agent**

Simply ask your local agent (Claude Code / Codex / etc.):

> "Help me set up the RBH Skills project following the README instructions"

The agent will create the virtual environment, install dependencies, and guide you through environment configuration.

### Environment Configuration

Create (Edit) a `.env` file in the `skills/` directory with the following content:

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
# Image provider: agnes (default), gemini, or openai
IMAGE_PROVIDER=your-model-provider  # agnes / gemini / openai

# Agnes AI image generation
IMAGE_API_KEY=your-agnes-ai-api-key
IMAGE_BASE_URL=https://apihub.agnes-ai.com
IMAGE_MODEL=agnes-image-2.1-flash
IMAGE_SIZE=1024x768

# OpenAI-compatible image generation (optional)
# Keep the API key and any relay URL in this local .env file.
OPENAI_API_KEY=your-openai-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_IMAGE_MODEL=gpt-image-2
# curl is the default; sdk is also supported
OPENAI_IMAGE_TRANSPORT=curl
OPENAI_IMAGE_TIMEOUT=180

# Gemini image/video/speech generation (optional)
GEMINI_API_KEY=your-gemini-api-key
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
GEMINI_IMAGE_MODEL=gemini-3.1-flash-image
GEMINI_IMAGE_SIZE=1K

# Video generation (Agnes/Gemini)

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

### Local Agent Integration (Required for Agent Skills)

Local Agents (Claude Code, Codex, OpenClaw, Hermes, etc.) discover skills by scanning their own skills directory for folders containing a `SKILL.md`. Since you cloned this repo elsewhere, you must **symlink each skill directory** into your agent's skills directory — otherwise the agent cannot see or invoke the skills.

Common skills directories:

| Agent | Global (all projects) | Project-level (single project) |
|-------|-----------------------|--------------------------------|
| Claude Code | `~/.claude/skills/` | `<project>/.claude/skills/` |
| Codex | `~/.codex/skills/` | `<project>/.codex/skills/` |
| OpenClaw | `~/.openclaw/skills/` | `<project>/.openclaw/skills/` |
| Hermes | `~/.hermes/skills/` | `<project>/.hermes/skills/` |

> If your agent uses a different location, check its documentation — the linking steps are the same.

**Global vs Project-level:**
- **Global** — the skill is available in every agent session on your machine. Recommended for general-purpose skills like `content-production` and `media-composer`.
- **Project-level** — the skill is only visible when the agent runs inside that project. Recommended when a skill is tied to one workspace (e.g. `rbh-core` / `adventure-academy` in your RBH content workspace), or when you want to keep the global list clean. If the project syncs to GitHub, add the symlinks to `.gitignore` (e.g. `.claude/skills/`) — they point to absolute paths on your machine and would break for anyone else.

If the same skill exists in both locations, the project-level one takes precedence.

Create the symlinks (macOS / Linux, using Claude Code as an example):

```bash
# Use the absolute path to your cloned repo
SKILLS_REPO="$(pwd)"   # run from the skills/ repo root

mkdir -p ~/.claude/skills

ln -s "$SKILLS_REPO/rbh-core"           ~/.claude/skills/rbh-core
ln -s "$SKILLS_REPO/adventure-academy"  ~/.claude/skills/adventure-academy
ln -s "$SKILLS_REPO/content-production" ~/.claude/skills/content-production
ln -s "$SKILLS_REPO/media-composer"     ~/.claude/skills/media-composer
```

For **project-level** installation, link into the project's own skills directory instead:

```bash
mkdir -p /path/to/your-project/.claude/skills

ln -s "$SKILLS_REPO/rbh-core" /path/to/your-project/.claude/skills/rbh-core
# ...repeat for other skills you need in this project
```

On Windows, use directory junctions instead (Command Prompt as Administrator):

```cmd
mklink /J "%USERPROFILE%\.claude\skills\rbh-core" "C:\path\to\skills\rbh-core"
mklink /J "%USERPROFILE%\.claude\skills\adventure-academy" "C:\path\to\skills\adventure-academy"
mklink /J "%USERPROFILE%\.claude\skills\content-production" "C:\path\to\skills\content-production"
mklink /J "%USERPROFILE%\.claude\skills\media-composer" "C:\path\to\skills\media-composer"
```

**Important Notes:**
- Link each **skill directory individually** — do not link the repo root, as agents only recognize folders that directly contain a `SKILL.md`
- Always use **absolute paths** for the link target; relative targets break when the agent resolves them from its own directory
- Symlinks mean `git pull` in the repo instantly updates the skills — no re-linking needed
- If you only need part of the pipeline, link just the skills you use (e.g. `content-production` + `media-composer` for media work)

Verify the links:

```bash
ls -la ~/.claude/skills/
# Each entry should point to your cloned repo, e.g.:
# content-production -> /path/to/skills/content-production
```

Then restart your agent and ask it to list available skills — the RBH skills should appear. You can test with a prompt like:

> "Use the content-production skill to generate an image of a sunrise"

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

## Model Checkpoints

Large binary checkpoints used by the **media-composer** skill (`replace-bg`). They live in `models/` at the repo root — gitignored, so not tracked — and are fetched on first use.

```bash
python media-composer/scripts/download_models.py                     # rvm_resnet50.pth (default)
python media-composer/scripts/download_models.py rvm_mobilenetv3.pth # optional lighter variant
```

| File | Used by | Size | Source | MD5 |
|------|---------|------|--------|-----|
| `rvm_resnet50.pth` | `replace-bg` | ~103 MB | [RobustVideoMatting v1.0.0](https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_resnet50.pth) | `04da1044ab32202b73a164f679824f39` |
| `rvm_mobilenetv3.pth` | `replace-bg --variant mobilenetv3` (optional) | ~15 MB | [RobustVideoMatting v1.0.0](https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3.pth) | (not pinned) |

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

**3. Agent does not detect the skills**

- Confirm the symlinks exist and point to valid paths: `ls -la ~/.claude/skills/` (broken links show the target but the directory is missing)
- Make sure you linked each skill directory (containing `SKILL.md`), not the repo root
- Restart the agent session after creating the links

**4. Virtual environment not found**

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
