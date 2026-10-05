"""Ошибки сервиса.

У каждой ошибки есть HTTP-код. Обработчик в ``main.py`` превращает любую из них
в ответ с этим кодом и телом ``{"detail": "текст ошибки"}``.
"""


class ServiceError(Exception):
    """Базовая ошибка сервиса."""

    status_code = 500


class InvalidRequestError(ServiceError):
    """Некорректный запрос: файл пустой."""

    status_code = 400


class FileTooLargeError(ServiceError):
    """Файл больше допустимого размера, слишком много пикселей или страниц."""

    status_code = 413


class UnsupportedFileError(ServiceError):
    """Файл не является ни поддерживаемым изображением, ни PDF."""

    status_code = 415


class BrokenFileError(ServiceError):
    """Формат поддерживается, но файл повреждён или защищён паролем."""

    status_code = 422


class UnknownChecksError(ServiceError):
    """В запросе указаны проверки, которых нет."""

    status_code = 422


class ServiceBusyError(ServiceError):
    """Сервис занят: внутри уже максимальное число запросов."""

    status_code = 503


class WorkerCrashedError(ServiceError):
    """Процесс-воркер упал во время анализа (пул процессов создан заново)."""

    status_code = 500
