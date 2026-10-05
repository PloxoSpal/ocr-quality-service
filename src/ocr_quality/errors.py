# Обработчик в main.py превращает любую из этих ошибок в ответ {"detail": "..."} с её кодом.


class ServiceError(Exception):
    """Базовая ошибка сервиса; status_code - HTTP-код ответа."""

    status_code = 500


class InvalidRequestError(ServiceError):
    """Некорректный запрос, например пустой файл."""

    status_code = 400


class FileTooLargeError(ServiceError):
    """Файл больше лимита по байтам, пикселям или страницам."""

    status_code = 413


class UnsupportedFileError(ServiceError):
    """Файл не картинка поддерживаемого формата и не PDF."""

    status_code = 415


class BrokenFileError(ServiceError):
    """Формат распознан, но файл не читается."""

    status_code = 422


class UnknownChecksError(ServiceError):
    """Запрошена проверка, которой нет."""

    status_code = 422


class ServiceBusyError(ServiceError):
    """Достигнут лимит одновременных запросов."""

    status_code = 503


class WorkerCrashedError(ServiceError):
    """Процесс анализа упал во время обработки файла."""

    status_code = 500
