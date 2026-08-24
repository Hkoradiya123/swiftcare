from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_here = Path(__file__).parent
_core_env = _here.parents[1] / ".env"   # swiftcare-core/.env
_root_env = _here.parents[2] / ".env"   # repo root .env


class Settings(BaseSettings):
    app_name: str = "Swiftcare"
    environment: str = "development"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/prahar_care"

    # Security
    secret_key: str = "dev-secret-key-change-in-production-1234567890!"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Email
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_pass: str = ""
    mail_from: str = "noreply@swiftcare.io"
    mock_smtp: bool = False

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    model_config = SettingsConfigDict(
        env_file=[str(_root_env), str(_core_env)],  # core overrides root
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
