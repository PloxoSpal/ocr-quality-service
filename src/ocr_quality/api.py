from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from ocr_quality.checks import ALL_CHECKS
from ocr_quality.config import settings
from ocr_quality.errors import FileTooLargeError, InvalidRequestError
from ocr_quality.schemas import ChecksList, Health, ImageAnalysis, PdfAnalysis
from ocr_quality.services import AnalysisService

router = APIRouter()


def get_service(request: Request) -> AnalysisService:
    return request.app.state.service


@router.get("/checks", response_model=ChecksList)
async def list_checks() -> ChecksList:
    return ChecksList(checks=list(ALL_CHECKS))


@router.post("/analyze", response_model=ImageAnalysis | PdfAnalysis)
async def analyze(
    file: UploadFile = File(description="Изображение (PNG, JPEG, WebP, TIFF, BMP) или PDF"),
    checks: str | None = Form(
        None, description="Какие проверки выполнить, через запятую: blur,skew. Если пусто - все."
    ),
    service: AnalysisService = Depends(get_service),
) -> ImageAnalysis | PdfAnalysis:
    # Размер известен до чтения: слишком большой файл не тащим в память.
    max_bytes = int(settings.MAX_UPLOAD_MB * 1024 * 1024)
    if file.size is not None and file.size > max_bytes:
        raise FileTooLargeError(f"File is too large (limit {max_bytes} bytes)")
    data = await file.read()
    if not data:
        raise InvalidRequestError("Uploaded file is empty")
    return await service.analyze(data, checks)


@router.get("/health", response_model=Health)
async def health(service: AnalysisService = Depends(get_service)) -> Health:
    return Health(
        workers=service.workers,
        requests_in_progress=service.requests_in_progress,
        request_limit=service.request_limit,
    )
