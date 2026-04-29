from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

from common.auth import setup_auth
from common.db import init_db
from sms_auth.scripts.sms import send_sms_verify_code, check_sms_verify_code


class SmsSendRequest(BaseModel):
    phone_number: str


class SmsVerifyRequest(BaseModel):
    phone_number: str
    verify_code: str


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
