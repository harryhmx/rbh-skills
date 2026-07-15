"""
Decorators for CLI authentication.
"""

import importlib.util
from functools import wraps
from pathlib import Path

# Dynamically import session module
_session_spec = importlib.util.spec_from_file_location(
    "rbh_core_session_decorators", Path(__file__).parent / "session.py"
)
_session_mod = importlib.util.module_from_spec(_session_spec)
_session_spec.loader.exec_module(_session_mod)
get_current_user = _session_mod.get_current_user


class AuthenticationError(Exception):
    """Raised when authentication is required but user is not logged in."""
    pass


def require_auth(func):
    """Decorator: require user to be logged in.

    Usage:
        @require_auth
        def some_function():
            user = get_current_user()  # guaranteed non-None
            ...

    Raises:
        AuthenticationError: If user is not logged in
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            raise AuthenticationError("Authentication required. Please login first.")
        return func(*args, **kwargs)
    return wrapper
