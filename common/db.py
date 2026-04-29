from supabase import create_client

from config import settings

_client = None


def init_db():
    global _client
    if not settings.SUPABASE_URL.strip():
        return
    _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


def get_db():
    if _client is None:
        init_db()
    return _client
