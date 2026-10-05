import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ocr_quality.api import router
from ocr_quality.config import settings
from ocr_quality.errors import ServiceError
from ocr_quality.services import AnalysisService


def create_app() -> FastAPI:
    """Собирает приложение: пул процессов на время работы и обработчик ошибок."""
    logging.basicConfig(
        level=settings.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        service = AnalysisService(
            workers=settings.WORKERS,
            request_limit=settings.MAX_REQUESTS or 4 * settings.WORKERS,
        )
        await service.warm_up()
        app.state.service = service
        yield
        service.shutdown()

    app = FastAPI(title="OCR Quality Service", lifespan=lifespan)
    app.include_router(router)

    @app.exception_handler(ServiceError)
    async def handle_service_error(_request: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    return app


app = create_app()
