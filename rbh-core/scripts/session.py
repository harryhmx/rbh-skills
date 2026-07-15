"""
Local session management for CLI.

Stores session data in ~/.rbh/session.json using JWT tokens.
"""

import json
import jwt
from pathlib import Path
from datetime import datetime, timedelta, timezone

SESSION_FILE = Path.home() / ".rbh" / "session.json"
JWT_SECRET = "rbh-local-session-secret-2026"  # Local CLI only
JWT_ALGORITHM = "HS256"
SESSION_EXPIRE_DAYS = 7


def generate_token(user_id: str, username: str) -> str:
    """Generate JWT token with 7-day expiration.

    Args:
        user_id: User ID
        username: Username

    Returns:
        JWT token string
    """
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict | None:
    """Verify JWT token and return payload.

    Args:
        token: JWT token string

    Returns:
        Decoded payload dict or None if invalid/expired
    """
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def save_session(user: dict) -> None:
    """Save user session to local file.

    Args:
        user: User dict from database (must contain 'id' and 'username')
    """
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

    token = generate_token(user["id"], user["username"])
    payload = verify_token(token)

    session_data = {
        "user_id": user["id"],
        "username": user["username"],
        "token": token,
        "expires_at": datetime.fromtimestamp(payload["exp"], timezone.utc).isoformat(),
    }

    SESSION_FILE.write_text(json.dumps(session_data, indent=2, ensure_ascii=False))


def get_current_session() -> dict | None:
    """Read and verify current session from local file.

    Returns:
        Session dict or None if not found/expired
    """
    if not SESSION_FILE.exists():
        return None

    try:
        session = json.loads(SESSION_FILE.read_text())
        payload = verify_token(session["token"])

        if not payload:
            # Token expired or invalid, clean up
            clear_session()
            return None

        return session

    except Exception:
        return None


def get_current_user() -> dict | None:
    """Get current logged-in user info.

    Returns:
        User dict with id, username or None if not logged in
    """
    session = get_current_session()
    if not session:
        return None

    return {
        "id": session["user_id"],
        "username": session["username"],
    }


def clear_session() -> None:
    """Clear local session (logout)."""
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
