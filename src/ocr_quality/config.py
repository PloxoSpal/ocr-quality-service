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

    # Сколько секунд даётся на анализ одного запроса, иначе 504.
    REQUEST_TIMEOUT_S: float = 120.0

    # Максимальный размер загружаемого файла в мегабайтах, иначе 413.
    MAX_UPLOAD_MB: float = 50.0

    LOG_LEVEL: str = "INFO"

    @property
    def REQUEST_LIMIT(self) -> int:  # noqa: N802 — свойства настроек в верхнем регистре
        """Сколько запросов одновременно пускать в сервис."""
        return self.MAX_REQUESTS or 4 * self.WORKERS

    @property
    def MAX_UPLOAD_BYTES(self) -> int:  # noqa: N802 — свойства настроек в верхнем регистре
        """Максимальный размер файла в байтах."""
        return int(self.MAX_UPLOAD_MB * 1024 * 1024)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
