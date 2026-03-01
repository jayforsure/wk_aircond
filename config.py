""" Configuration settings loaded from .env file """
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # WhatsApp
    WHATSAPP_ACCESS_TOKEN: str
    WHATSAPP_PHONE_NUMBER_ID: str
    WHATSAPP_VERIFY_TOKEN: str
    WHATSAPP_API_VERSION: str = "v19.0"

    # Anthropic
    ANTHROPIC_API_KEY: str
    AI_MODEL: str = "claude-haiku-4-5-20251001"
    AI_MAX_TOKENS: int = 1024

    # Redis (for conversation history)
    REDIS_URL: str = "redis://localhost:6379"

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore unused env vars

    @property
    def whatsapp_api_url(self) -> str:
        return f"https://graph.facebook.com/{self.WHATSAPP_API_VERSION}/{self.WHATSAPP_PHONE_NUMBER_ID}"


settings = Settings()