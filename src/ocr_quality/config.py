import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки из переменных окружения или файла .env."""

    WORKERS: int = os.cpu_count() or 1
    MAX_REQUESTS: int = 0  # 0 - значит 4 x WORKERS
    MAX_UPLOAD_MB: float = 50.0
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
