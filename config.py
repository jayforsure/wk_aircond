"""Configuration settings loaded from environment variables"""
import os
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # WhatsApp
    WHATSAPP_ACCESS_TOKEN: str = Field(default="")
    WHATSAPP_PHONE_NUMBER_ID: str = Field(default="")
    WHATSAPP_VERIFY_TOKEN: str = Field(default="flux_webhook_secret_2025")
    WHATSAPP_API_VERSION: str = Field(default="v19.0")

    # Anthropic
    ANTHROPIC_API_KEY: str = Field(default="")
    AI_MODEL: str = Field(default="claude-haiku-4-5-20251001")
    AI_MAX_TOKENS: int = Field(default=1024)

    # Redis (for conversation history)
    REDIS_URL: str = Field(default="redis://localhost:6379")

    model_config = {
        "env_file": ".env",
        "extra": "ignore",  # Ignore unused env vars from other projects
    }

    @property
    def whatsapp_api_url(self) -> str:
        return f"https://graph.facebook.com/{self.WHATSAPP_API_VERSION}/{self.WHATSAPP_PHONE_NUMBER_ID}"

    def validate_required(self):
        missing = []
        if not self.WHATSAPP_ACCESS_TOKEN:
            missing.append("WHATSAPP_ACCESS_TOKEN")
        if not self.WHATSAPP_PHONE_NUMBER_ID:
            missing.append("WHATSAPP_PHONE_NUMBER_ID")
        if not self.ANTHROPIC_API_KEY:
            missing.append("ANTHROPIC_API_KEY")
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


settings = Settings()