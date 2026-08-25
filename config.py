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

    # Text generation (SiliconFlow, OpenAI-compatible)
    TEXT_API_KEY: str = ""
    TEXT_BASE_URL: str = "https://api.siliconflow.com/v1"
    TEXT_CHAT_MODEL: str = "Qwen/Qwen3-32B"

    # Image generation (SiliconFlow)
    IMAGE_API_KEY: str = ""
    IMAGE_BASE_URL: str = "https://api.siliconflow.com/v1"
    IMAGE_MODEL: str = "black-forest-labs/FLUX.2-pro"
    IMAGE_SIZE: str = "1024x768"

    # Speech generation (SiliconFlow)
    SPEECH_API_KEY: str = ""
    SPEECH_BASE_URL: str = "https://api.siliconflow.com/v1"
    SPEECH_MODEL: str = "fishaudio/fish-speech-1.5"
    SPEECH_VOICE: str = "fishaudio/fish-speech-1.5:anna"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._check_config()

    def _check_config(self):
        required = [
            ("SUPABASE_URL", self.SUPABASE_URL),
            ("SUPABASE_KEY", self.SUPABASE_KEY),
            ("ALIBABA_CLOUD_ACCESS_KEY_ID", self.ALIBABA_CLOUD_ACCESS_KEY_ID),
            ("ALIBABA_CLOUD_ACCESS_KEY_SECRET", self.ALIBABA_CLOUD_ACCESS_KEY_SECRET),
            ("TEXT_API_KEY", self.TEXT_API_KEY),
            ("IMAGE_API_KEY", self.IMAGE_API_KEY),
            ("SPEECH_API_KEY", self.SPEECH_API_KEY),
        ]
        missing = [name for name, val in required if not val.strip()]
        if missing:
            logger.warning("Missing env vars: %s — some features will be unavailable", ", ".join(missing))


settings = Settings()


def openai_compatible_base_url(base_url: str) -> str:
    """Return a normalized OpenAI-compatible API base URL.

    SiliconFlow's configured URL already includes ``/v1`` while older local
    configurations used a host-only URL. Supporting both avoids accidentally
    producing ``/v1/v1`` while retaining backwards compatibility.
    """
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/v1") else f"{normalized}/v1"
