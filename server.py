import importlib.util
import logging
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

from common.auth import setup_auth
from common.db import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_sms_spec = importlib.util.spec_from_file_location(
    "sms", Path(__file__).parent / "sms-auth" / "scripts" / "sms.py"
)
_sms_mod = importlib.util.module_from_spec(_sms_spec)
_sms_spec.loader.exec_module(_sms_mod)
send_sms_verify_code = _sms_mod.send_sms_verify_code
check_sms_verify_code = _sms_mod.check_sms_verify_code

_story_spec = importlib.util.spec_from_file_location(
    "story", Path(__file__).parent / "story-generation" / "scripts" / "story.py"
)
_story_mod = importlib.util.module_from_spec(_story_spec)
_story_spec.loader.exec_module(_story_mod)
find_story = _story_mod.find_story
generate_and_insert_story = _story_mod.generate_and_insert_story
update_story_media = _story_mod.update_story_media
get_story_by_id = _story_mod.get_story_by_id


class SmsSendRequest(BaseModel):
    phone_number: str


class SmsVerifyRequest(BaseModel):
    phone_number: str
    verify_code: str


class StoryRequest(BaseModel):
    project_title: str
    project_description: str
    user_age: int
    user_level: str
    project_id: str
    require_story_id: str | None = None
    require_choice: str | None = None
    depth: int = 0
    parent_story_title: str | None = None
    parent_story_content: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="RBH Skills API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_auth(app)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/auth/sms/send")
async def sms_send(req: SmsSendRequest):
    return send_sms_verify_code(req.phone_number)


@app.post("/api/auth/sms/verify")
async def sms_verify(req: SmsVerifyRequest):
    return check_sms_verify_code(req.phone_number, req.verify_code)


@app.post("/api/story/generate")
async def generate_story_endpoint(req: StoryRequest, background_tasks: BackgroundTasks):
    existing = find_story(
        req.project_id,
        req.user_age,
        req.user_level,
        require_story_id=req.require_story_id,
        require_choice=req.require_choice,
    )
    if existing:
        media_ready = bool(existing.get("imageUrl") and existing.get("audioUrl"))
        if media_ready:
            return {"story": existing, "generated": False, "mediaReady": True}

        logger.info("[generate] Story exists but media missing, regenerating media for %s", existing["id"])
        background_tasks.add_task(
            update_story_media,
            existing["id"],
            existing["title"],
            existing.get("content", ""),
        )
        return {"story": existing, "generated": False, "mediaReady": False}

    story = generate_and_insert_story(
        project_title=req.project_title,
        project_description=req.project_description,
        user_age=req.user_age,
        user_level=req.user_level,
        project_id=req.project_id,
        require_story_id=req.require_story_id,
        require_choice=req.require_choice,
        depth=req.depth,
        parent_story_title=req.parent_story_title,
        parent_story_content=req.parent_story_content,
    )

    background_tasks.add_task(
        update_story_media,
        story["id"],
        story["title"],
        story.get("content", ""),
    )
    return {"story": story, "generated": True, "mediaReady": False}


@app.get("/api/story/status/{story_id}")
async def story_status(story_id: str):
    story = get_story_by_id(story_id)
    if not story:
        return {"error": "Story not found"}, 404
    return {
        "imageReady": bool(story.get("imageUrl")),
        "audioReady": bool(story.get("audioUrl")),
    }
