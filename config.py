from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SMS_API_KEY: str
    SMS_API_URL: str
    LLM_API_KEY: str
    LLM_MODEL: str = "claude-sonnet-4-6"


settings = Settings()
