from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from ocr_quality.checks import ALL_CHECKS
from ocr_quality.errors import FileTooLargeError
from ocr_quality.schemas import ChecksList, ErrorResponse, Health, ImageAnalysis, PdfAnalysis
from ocr_quality.services import AnalysisService

router = APIRouter()


def get_service(request: Request) -> AnalysisService:
    """Сервис анализа, созданный при старте приложения."""
    service: AnalysisService = request.app.state.service
    return service


@router.get("/checks", response_model=ChecksList)
async def list_checks() -> ChecksList:
    """Список всех проверок качества."""
    return ChecksList(checks=list(ALL_CHECKS))


@router.post(
    "/analyze",
    response_model=ImageAnalysis | PdfAnalysis,
    responses={code: {"model": ErrorResponse} for code in (400, 413, 415, 422, 503, 504)},
)
async def analyze(
    file: UploadFile = File(description="Изображение (PNG, JPEG, WebP, TIFF, BMP) или PDF"),
    checks: list[str] | None = Form(
        None,
        description="Какие проверки выполнить: через запятую или повтором поля. "
        "Если не указано - все.",
    ),
    service: AnalysisService = Depends(get_service),
) -> ImageAnalysis | PdfAnalysis:
    """Проверить пригодность изображения или PDF для OCR.

    Для PDF каждая страница проверяется отдельно, а документ получает общий итог.
    """
    # Размер известен ещё до чтения файла: слишком большой не тащим в память.
    if file.size is not None and file.size > service.max_upload_bytes:
        raise FileTooLargeError(f"File is too large (limit {service.max_upload_bytes} bytes)")
    data = await file.read()
    return await service.analyze(data, checks or [])


@router.get("/health", response_model=Health)
async def health(service: AnalysisService = Depends(get_service)) -> Health:
    """Сервис жив; сколько запросов сейчас внутри."""
    return Health(
        workers=service.workers,
        requests_in_progress=service.requests_in_progress,
        request_limit=service.request_limit,
    )
