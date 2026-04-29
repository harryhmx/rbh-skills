# RBH Skills

Backend skills for the RBH Agent learning platform. Each skill is an independent Python module that exposes REST APIs for the frontend.

## Skills

| Skill | Description |
|-------|-------------|
| **sms-auth** | SMS verification for authentication (send + verify) |
| **course-generation** | AI-powered story generation with RC/CT questions |
| **course-branch** | Branching story generation based on Critical Thinking answers |

## Tech Stack

- Python 3.11+
- FastAPI + Uvicorn
- LLM: Zhipu AI GLM-5

## Architecture

```
RBH Agent Frontend (Next.js, Vercel)
    │
    ├──> RBH Skills (FastAPI, VPS)
    │       ├── sms-auth        ──> SMS Service
    │       ├── course-generation ──> LLM
    │       └── course-branch    ──> LLM
    │
    └──> Supabase (PostgreSQL)
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Install skill-specific dependencies
pip install -r sms-auth/references/requirements.txt
pip install -r course-generation/references/requirements.txt

# Run development server
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

| Method | Route | Skill | Description |
|--------|-------|-------|-------------|
| POST | `/api/auth/sms/send` | sms-auth | Send SMS verification code |
| POST | `/api/auth/sms/verify` | sms-auth | Verify SMS code, return auth info |
| POST | `/api/story/generate` | course-generation | Generate story matching user profile |
| POST | `/api/story/branch` | course-branch | Generate branching story from CT answer |
