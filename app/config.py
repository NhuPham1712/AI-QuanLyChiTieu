import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "UniBOT Finance Modern V11.7"
    APP_VERSION: str = "11-7-final-clean"
    PORT: int = 8030
    DATABASE_URL: str = "sqlite:///./finbot.db"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
