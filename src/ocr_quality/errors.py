"""Ошибки сервиса.

У каждой ошибки есть HTTP-код и короткий машиночитаемый ``code``. Обработчик в
``main.py`` превращает любую из них в ответ ``{"error": {"code", "message", "details"}}``.
"""

from __future__ import annotations

from typing import Any


class ServiceError(Exception):
    """Базовая ошибка сервиса."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        # Оба аргумента передаём в Exception: так ошибка, брошенная в процессе-воркере,
        # корректно восстанавливается в основном процессе (pickle берёт их из args).
        super().__init__(message, details)
        self.message = message
        self.details = details or {}


class InvalidRequestError(ServiceError):
    """Некорректный запрос: нет файла или файл пустой."""

    status_code = 400
    code = "invalid_input"


class FileTooLargeError(ServiceError):
    """Файл больше допустимого размера, слишком много пикселей или страниц."""

    status_code = 413
    code = "payload_too_large"


class UnsupportedFileError(ServiceError):
    """Файл не является ни поддерживаемым изображением, ни PDF."""

    status_code = 415
    code = "unsupported_media_type"


class BrokenFileError(ServiceError):
    """Формат поддерживается, но файл повреждён или защищён паролем."""

    status_code = 422
    code = "corrupted_file"


class UnknownChecksError(ServiceError):
    """В запросе указаны проверки, которых нет."""

    status_code = 422
    code = "unknown_checks"


class ServiceBusyError(ServiceError):
    """Сервис занят: внутри уже максимальное число запросов."""

    status_code = 503
    code = "overloaded"


class AnalysisTimeoutError(ServiceError):
    """Анализ не уложился в отведённое время."""

    status_code = 504
    code = "timeout"


class WorkerCrashedError(ServiceError):
    """Процесс-воркер упал во время анализа (пул процессов создан заново)."""

    status_code = 500
    code = "worker_crashed"
