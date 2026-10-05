"""Настройки сервиса из .env и переменных окружения."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки сервиса, например ``WORKERS=4``."""

    # Сколько процессов параллельно считают проверки. По умолчанию - число ядер.
    WORKERS: int = os.cpu_count() or 1

    # Сколько запросов может одновременно находиться в сервисе (считаются или ждут
    # свободного процесса). Остальные сразу получают 503. 0 - значит 4 x workers.
    MAX_REQUESTS: int = 0

    # Максимальный размер загружаемого файла в мегабайтах, иначе 413.
    MAX_UPLOAD_MB: float = 50.0

    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
