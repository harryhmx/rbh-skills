from fastapi import FastAPI, Depends, HTTPException, Header
import supabase


def setup_auth(app: FastAPI):
    @app.middleware("http")
    async def auth_middleware(request, call_next):
        skip_paths = ["/health", "/api/auth/sms/send", "/api/auth/sms/verify"]
        if request.url.path in skip_paths or request.method == "OPTIONS":
            return await call_next(request)
        token = request.headers.get("Authorization")
        if not token:
            raise HTTPException(status_code=401, detail="Missing authorization")
        # TODO: validate token with Supabase
        return await call_next(request)
