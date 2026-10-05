# Обработчик в main.py превращает любую из этих ошибок в ответ {"detail": "..."} с её кодом.


class ServiceError(Exception):
    status_code = 500


class InvalidRequestError(ServiceError):
    status_code = 400


class FileTooLargeError(ServiceError):
    status_code = 413


class UnsupportedFileError(ServiceError):
    status_code = 415


class BrokenFileError(ServiceError):
    status_code = 422


class UnknownChecksError(ServiceError):
    status_code = 422


class ServiceBusyError(ServiceError):
    status_code = 503


class WorkerCrashedError(ServiceError):
    status_code = 500
