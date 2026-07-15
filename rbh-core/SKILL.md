---
name: rbh-core
description: "Core data service layer for RBH platform — SMS authentication (Aliyun), User management (registration/login), Project generation (LLM + Supabase sync). Provides FastAPI routes and CLI for both online and local usage."
version: "1.0.0"
allowed-tools: ["Bash", "Read", "Write"]
---

# RBH Core

Core data service layer — account management and Project data operations for RBH platform.

## Scope

### 1. SMS Authentication (migrated)
- Send SMS verification code (Aliyun SDK)
- Verify SMS code
- Cooldown control (60s)

### 2. Project Generation (migrated, API not exposed yet)
- LLM-generated Project title + description
- Sync to Supabase database

### 3. User Management
- User registration (username + password)
- User authentication (password / SMS)
- Session management (JWT-based)

## Consumption

### FastAPI (online RBH Agent → server.py)
Routes:
- `POST /api/auth/sms/send` — send SMS verification code
- `POST /api/auth/sms/verify` — verify SMS code

**Note**: Project/Article/User routes reserved for Stage 4+ expansion.

### CLI (local management & Agent usage)

**Design Philosophy**: CLI uses parameterized commands (no interactive prompts). Agent creates conversational experience by asking questions and passing answers as arguments.

```bash
source ../.venv/bin/activate

# Authentication
python scripts/cli.py auth register --username <user> --password <pwd>
python scripts/cli.py auth login --username <user> --password <pwd>
python scripts/cli.py auth send-sms --phone <phone>
python scripts/cli.py auth login-sms --username <user> --phone <phone> --code <code>
python scripts/cli.py auth logout
python scripts/cli.py auth whoami

# Project generation (requires login)
python scripts/cli.py project generate --prompt "Create a story about..."
```

**For Agent Usage**: See `references/agent-usage-guide.md` for conversational flow examples.

## Architecture

### Dependencies
- `common/db.py` — Supabase connection (infrastructure layer, shared)
- `common/auth.py` — FastAPI auth middleware (infrastructure layer, shared)
- `config.py` — environment variables (root directory)

### Business Logic
- `scripts/auth.py` — SMS verification logic (Aliyun SDK calls)
- `scripts/user.py` — User registration and authentication
- `scripts/project.py` — Project generation logic (LLM + Supabase)
- `scripts/session.py` — Session management (JWT tokens)
- `scripts/decorators.py` — Authentication decorators
- `scripts/common.py` — Internal shared utilities

**Key**: common/ is infrastructure only, no business logic.

## Environment Variables

```env
# SMS Authentication (Aliyun)
ALIBABA_CLOUD_ACCESS_KEY_ID=<your-key>
ALIBABA_CLOUD_ACCESS_KEY_SECRET=<your-secret>

# LLM (Project generation)
TEXT_API_KEY=<your-api-key>
TEXT_BASE_URL=<api-base-url>
TEXT_CHAT_MODEL=<model-name>

# Database (Supabase)
SUPABASE_URL=<your-url>
SUPABASE_KEY=<your-key>
```

## Deployment

Railway image contains:
- `server.py` — FastAPI entry point
- `common/` — infrastructure layer (db + auth middleware)
- `rbh-core/` — this skill

**Excluded from Railway** (.dockerignore):
- `content-production/`
- `media-composer/`

## Dependencies

Already in `skills/requirements.txt` (root):
- `alibabacloud-dypnsapi20170525` — Aliyun SMS SDK
- `openai` — LLM calls (Project generation)
- `supabase` — database
- `fastapi` + `uvicorn` — API server

## References

- `references/agent-usage-guide.md` — conversational flow examples for Agent
- `references/api-contracts.md` — detailed API route specs
- `references/data-models.md` — data model documentation

## Migration Source

- `sms-auth/` → `scripts/auth.py` (SMS verification)
- `project-creation/` → `scripts/project.py` (Project generation)

## Future Expansion (Stage 4+)

- Add `/api/project/generate` route
- Add Article CRUD module
- Add User profile management module
