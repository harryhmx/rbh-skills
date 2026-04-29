from fastapi import FastAPI
from contextlib import asynccontextmanager

from common.auth import setup_auth
from common.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="RBH Skills API", lifespan=lifespan)

setup_auth(app)


@app.get("/health")
async def health():
    return {"status": "ok"}
