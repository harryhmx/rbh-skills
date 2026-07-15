"""
User registration and authentication for CLI.

Migrated from NextAuth logic, reuses Supabase User table.
"""

import bcrypt
import logging
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

from common.db import get_db

# Dynamically import auth module (avoid circular import + relative import issues)
_auth_spec = importlib.util.spec_from_file_location(
    "rbh_core_auth_check", Path(__file__).parent / "auth.py"
)
_auth_mod = importlib.util.module_from_spec(_auth_spec)
_auth_spec.loader.exec_module(_auth_mod)
check_sms_verify_code = _auth_mod.check_sms_verify_code

logger = logging.getLogger(__name__)


def get_user_by_username(username: str) -> dict | None:
    """Query user by username from Supabase.

    Args:
        username: Username to query

    Returns:
        User dict or None if not found
    """
    db = get_db()
    result = db.table("User").select("*").eq("username", username).execute()
    return result.data[0] if result.data else None


def register_user(username: str, password: str) -> dict:
    """Register new user (CLI).

    Flow:
    1. Check if username exists
    2. Hash password with bcrypt (cost=8, matches NextAuth)
    3. Insert into User table
    4. Return user data

    Args:
        username: Username (min 3 chars)
        password: Password (min 6 chars)

    Returns:
        {"success": bool, "user": dict | None, "message": str}
    """
    if len(username) < 3:
        return {"success": False, "user": None, "message": "Username must be at least 3 characters"}

    if len(password) < 6:
        return {"success": False, "user": None, "message": "Password must be at least 6 characters"}

    existing = get_user_by_username(username)
    if existing:
        return {"success": False, "user": None, "message": "Username already exists"}

    try:
        db = get_db()
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=8))

        # Generate cuid for User.id (Prisma uses cuid by default)
        import secrets
        user_id = "cl" + secrets.token_urlsafe(20)[:20]

        now = datetime.now(timezone.utc).isoformat()

        user_data = {
            "id": user_id,
            "username": username,
            "password": hashed.decode('utf-8'),
            "usertype": "student",
            "score": 0,
            "storyPhase": 0,
            "createdAt": now,
            "updatedAt": now,
        }

        result = db.table("User").insert(user_data).execute()
        user = result.data[0]

        logger.info(f"User registered: {username}")
        return {"success": True, "user": user, "message": "Registration successful"}

    except Exception as e:
        logger.error(f"Registration error: {e}")
        return {"success": False, "user": None, "message": f"Registration failed: {e}"}


def login_with_password(username: str, password: str) -> dict:
    """Login with username + password (CLI).

    Flow:
    1. Query user by username
    2. Verify password with bcrypt
    3. Return user data

    Args:
        username: Username
        password: Password

    Returns:
        {"success": bool, "user": dict | None, "message": str}
    """
    user = get_user_by_username(username)
    if not user:
        return {"success": False, "user": None, "message": "User not found"}

    try:
        password_match = bcrypt.checkpw(
            password.encode('utf-8'),
            user["password"].encode('utf-8')
        )

        if not password_match:
            return {"success": False, "user": None, "message": "Invalid password"}

        logger.info(f"User logged in: {username}")
        return {"success": True, "user": user, "message": "Login successful"}

    except Exception as e:
        logger.error(f"Login error: {e}")
        return {"success": False, "user": None, "message": f"Login failed: {e}"}


def login_with_sms(username: str, phone_number: str, sms_code: str) -> dict:
    """Login with username + phone + SMS code (CLI).

    Flow:
    1. Verify SMS code
    2. Query user by username
    3. If not exists, auto-create (matches NextAuth sms provider)
    4. Update phoneNumber field
    5. Return user data

    Args:
        username: Username
        phone_number: Phone number
        sms_code: SMS verification code

    Returns:
        {"success": bool, "user": dict | None, "message": str}
    """
    # Verify SMS code first
    sms_result = check_sms_verify_code(phone_number, sms_code)
    if not sms_result.get("success"):
        return {
            "success": False,
            "user": None,
            "message": f"SMS verification failed: {sms_result.get('message')}"
        }

    try:
        db = get_db()
        user = get_user_by_username(username)

        if user:
            # Update existing user's phone number
            updated = db.table("User").update({"phoneNumber": phone_number}).eq("username", username).execute()
            user = updated.data[0]
            logger.info(f"User logged in via SMS: {username}")
        else:
            # Auto-create user (matches NextAuth sms provider logic)
            import secrets
            user_id = "cl" + secrets.token_urlsafe(20)[:20]

            placeholder_pw = bcrypt.hashpw(
                f"sms_{datetime.now(timezone.utc).timestamp()}".encode('utf-8'),
                bcrypt.gensalt(rounds=8)
            )

            now = datetime.now(timezone.utc).isoformat()

            user_data = {
                "id": user_id,
                "username": username,
                "phoneNumber": phone_number,
                "password": placeholder_pw.decode('utf-8'),
                "usertype": "student",
                "score": 0,
                "storyPhase": 0,
                "createdAt": now,
                "updatedAt": now,
            }

            result = db.table("User").insert(user_data).execute()
            user = result.data[0]
            logger.info(f"User auto-created via SMS: {username}")

        return {"success": True, "user": user, "message": "Login successful"}

    except Exception as e:
        logger.error(f"SMS login error: {e}")
        return {"success": False, "user": None, "message": f"Login failed: {e}"}
