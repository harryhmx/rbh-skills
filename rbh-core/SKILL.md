---
name: rbh-core
description: "RBH Core service layer for Aliyun SMS authentication, local CLI user management, and SiliconFlow-powered Project generation with Supabase synchronization."
version: "1.1.0"
allowed-tools: ["Bash", "Read", "Write"]
---

# RBH Core

RBH Core provides account and project-generation capabilities for Really Brave Hearts, the RBH platform that combines AI technology with education for learners of every age.

## Dual consumption model

RBH Core is designed for both kinds of RBH Agents:

- **Web Agent** — calls the FastAPI routes exposed by `server.py` for SMS authentication and, as the platform grows, Project, profile, and Adventure Academy operations.
- **Local Agent** — uses the parameterized `rbh-core/scripts/cli.py` commands to create conversational authentication and management flows on the local machine.

Adventure Academy is currently served through the FastAPI service. Its story-generation and learning operations can also be wrapped by the Local Agent CLI as the CLI surface expands; the skill documentation should remain the shared contract for both callers.

## Scope

### SMS authentication

- Aliyun DypnsAPI verification-code sending and checking
- Mainland China mobile-number validation
- Whitespace normalization for phone numbers and codes
- In-memory 60-second send cooldown

### User and session management

The CLI supports password registration/login, SMS login, logout, and `whoami`. The browser-facing Core app owns the primary NextAuth JWT session and uses these Skills routes for SMS delivery and verification.

### Project generation

`scripts/project.py` generates a concise Project title and description with SiliconFlow's OpenAI-compatible chat API and inserts the result into Supabase. The CLI command is available; a public FastAPI Project-generation route remains reserved for a later stage.

Future RBH projects, including Adventure Academy and later age groups or learning domains, should build on the same authenticated Project and User foundations rather than introducing a separate account system.

## FastAPI routes

The repository-level `server.py` exposes:

```text
GET  /health
POST /api/auth/sms/send
POST /api/auth/sms/verify
POST /api/story/generate       # Adventure Academy route
GET  /api/story/status/{id}    # Adventure Academy route
```

SMS responses always include a boolean `success` field. Callers must check `success === true`, not only the HTTP status.

## Local Agent CLI

```bash
source .venv/bin/activate

python rbh-core/scripts/cli.py auth register --username <user> --password <pwd>
python rbh-core/scripts/cli.py auth login --username <user> --password <pwd>
python rbh-core/scripts/cli.py auth send-sms --phone <phone>
python rbh-core/scripts/cli.py auth login-sms --username <user> --phone <phone> --code <code>
python rbh-core/scripts/cli.py auth logout
python rbh-core/scripts/cli.py auth whoami

python rbh-core/scripts/cli.py project generate --prompt "Create a project about..."
```

Commands are parameterized so an Agent can collect the user's answers conversationally without relying on interactive prompts.

The CLI is intentionally non-interactive: it accepts arguments, returns JSON-friendly results, stores the local JWT session in the Agent session file, and lets the Local Agent provide the natural-language conversation. See `references/agent-usage-guide.md` for the expected flow.

## Configuration

```env
ALIBABA_CLOUD_ACCESS_KEY_ID=your-aliyun-access-key-id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your-aliyun-access-key-secret

TEXT_API_KEY=your-siliconflow-key
TEXT_BASE_URL=https://api.siliconflow.com/v1
TEXT_CHAT_MODEL=Qwen/Qwen3-32B

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
JWT_SECRET=your-secret-at-least-32-characters
```

The code normalizes OpenAI-compatible URLs and avoids duplicating `/v1`. Credentials belong in `skills/.env` and must not be committed.

## Network and local development

Proxy settings belong to the process environment, not to the business logic. If FlClash is required on this Mac, start the host process with:

```bash
HTTPS_PROXY=http://127.0.0.1:7890 \
HTTP_PROXY=http://127.0.0.1:7890 \
ALL_PROXY=http://127.0.0.1:7890 \
NO_PROXY=127.0.0.1,localhost \
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Use official service endpoints only. Do not add proxy settings to Python modules.

## Main modules

| File | Responsibility |
|------|----------------|
| `scripts/auth.py` | Aliyun SMS send/check logic and input normalization |
| `scripts/user.py` | Registration and password authentication |
| `scripts/session.py` | JWT session persistence |
| `scripts/project.py` | SiliconFlow Project generation and Supabase insert |
| `scripts/cli.py` | Agent-friendly command-line interface |
| `common/` | Shared database and authentication infrastructure |

## Web Agent and Local Agent boundaries

The Web Agent should treat HTTP status and response bodies as separate signals and check `success === true` for SMS operations. The Local Agent should check CLI exit codes and parse the JSON result. Neither caller should access provider credentials directly; all provider calls stay inside the Skills service.

## Future expansion

- Expose authenticated Project CRUD for Web Agent use
- Add User profile and Project membership APIs
- Add Adventure Academy story/branch operations to the Local Agent CLI
- Reuse the same Core identity and Project model for additional RBH learning projects

## References

- `references/agent-usage-guide.md` — conversational command examples
- `references/api-contracts.md` — route contracts
- `references/data-models.md` — Supabase data models
