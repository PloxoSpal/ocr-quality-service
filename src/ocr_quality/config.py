"""Настройки сервиса. Каждую можно задать переменной окружения с префиксом ``OCRQ_``."""

from __future__ import annotations

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки сервиса, например ``OCRQ_WORKERS=4``."""

    model_config = SettingsConfigDict(env_prefix="OCRQ_")

    # Сколько процессов параллельно считают проверки. По умолчанию - число ядер.
    workers: int = os.cpu_count() or 1

    # Сколько запросов может одновременно находиться в сервисе (считаются или ждут
    # свободного процесса). Остальные сразу получают 503. 0 - значит 4 x workers.
    max_requests: int = 0

    # Сколько секунд даётся на анализ одного запроса, иначе 504.
    request_timeout_s: float = 120.0

    # Максимальный размер загружаемого файла в мегабайтах, иначе 413.
    max_upload_mb: float = 50.0

    log_level: str = "INFO"

    @property
    def request_limit(self) -> int:
        """Сколько запросов одновременно пускать в сервис."""
        return self.max_requests or 4 * self.workers

    @property
    def max_upload_bytes(self) -> int:
        """Максимальный размер файла в байтах."""
        return int(self.max_upload_mb * 1024 * 1024)
