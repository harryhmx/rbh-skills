import logging
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    ALIBABA_CLOUD_ACCESS_KEY_ID: str = ""
    ALIBABA_CLOUD_ACCESS_KEY_SECRET: str = ""
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.siliconflow.com/v1"
    LLM_CHAT_MODEL: str = "Qwen/Qwen2.5-72B-Instruct"
    LLM_IMAGE_MODEL: str = "black-forest-labs/FLUX.2-pro"
    LLM_IMAGE_SIZE: str = "512x512"
    LLM_SPEECH_MODEL: str = "fishaudio/fish-speech-1.5"
    LLM_SPEECH_VOICE: str = "fishaudio/fish-speech-1.5:anna"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._check_config()

    def _check_config(self):
        required = [
            ("SUPABASE_URL", self.SUPABASE_URL),
            ("SUPABASE_KEY", self.SUPABASE_KEY),
            ("ALIBABA_CLOUD_ACCESS_KEY_ID", self.ALIBABA_CLOUD_ACCESS_KEY_ID),
            ("ALIBABA_CLOUD_ACCESS_KEY_SECRET", self.ALIBABA_CLOUD_ACCESS_KEY_SECRET),
            ("LLM_API_KEY", self.LLM_API_KEY),
        ]
        missing = [name for name, val in required if not val.strip()]
        if missing:
            logger.warning("Missing env vars: %s — some features will be unavailable", ", ".join(missing))


settings = Settings()
