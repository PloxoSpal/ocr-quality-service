"""Создание приложения FastAPI.

Запуск: ``uvicorn ocr_quality.main:app`` или ``python -m ocr_quality``.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ocr_quality import __version__
from ocr_quality.api import router
from ocr_quality.config import Settings
from ocr_quality.errors import ServiceError
from ocr_quality.services import AnalysisService


def create_app(settings: Settings | None = None) -> FastAPI:
    """Собрать приложение: эндпоинты, сервис анализа и обработку ошибок."""
    settings = settings or Settings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # При старте создаём сервис и запускаем процессы, при остановке - гасим их.
        service = AnalysisService(
            workers=settings.workers,
            request_limit=settings.request_limit,
            request_timeout_s=settings.request_timeout_s,
            max_upload_bytes=settings.max_upload_bytes,
        )
        await service.warm_up()
        app.state.service = service
        yield
        service.shutdown()

    app = FastAPI(title="OCR Quality Service", version=__version__, lifespan=lifespan)
    app.include_router(router)

    @app.exception_handler(ServiceError)
    async def handle_service_error(request: Request, exc: ServiceError) -> JSONResponse:
        headers = {"Retry-After": "1"} if exc.status_code == 503 else None
        return error_response(exc.status_code, exc.code, exc.message, exc.details, headers)

    @app.exception_handler(RequestValidationError)
    async def handle_bad_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        problems = [{"field": list(e["loc"]), "problem": e["msg"]} for e in exc.errors()]
        return error_response(
            400, "invalid_input", "Request validation failed", {"errors": problems}
        )

    return app


def error_response(
    status: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """JSON-ответ с ошибкой в едином формате."""
    body = {"error": {"code": code, "message": message, "details": details or {}}}
    return JSONResponse(status_code=status, content=body, headers=headers)


app = create_app()
