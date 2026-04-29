from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_KEY: str
    ALIBABA_CLOUD_ACCESS_KEY_ID: str
    ALIBABA_CLOUD_ACCESS_KEY_SECRET: str
    LLM_API_KEY: str
    LLM_BASE_URL: str = "https://api.siliconflow.cn/v1"
    LLM_MODEL: str = "Qwen/Qwen2.5-72B-Instruct"


settings = Settings()
