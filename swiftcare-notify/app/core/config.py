from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_here = Path(__file__).parent
_notify_env = _here.parents[1] / ".env"
_root_env = _here.parents[2] / ".env"


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/prahar_care"
    redis_url: str = "redis://localhost:6379/0"
    consumer_name: str = "notify-1"

    # S3 / MinIO
    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "swiftcare-docs"
    s3_region: str = "ap-south-1"

    # SMTP
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    mail_from: str = "noreply@swiftcare.local"
    mock_smtp: bool = False  # set True to log emails instead of sending

    model_config = SettingsConfigDict(
        env_file=[str(_root_env), str(_notify_env)],
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
