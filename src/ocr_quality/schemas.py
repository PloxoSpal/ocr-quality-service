from typing import Any, Literal

from pydantic import BaseModel

CheckStatus = Literal["passed", "failed", "not_applicable", "error"]


class CheckResult(BaseModel):
    passed: bool | None  # None - проверка неприменима или упала
    score: float | None
    status: CheckStatus
    critical: bool
    weight: float
    value: float | None
    unit: str
    threshold: float | None  # value на границе «пройдено / не пройдено»
    message: str | None = None
    details: dict[str, Any] = {}
    time_ms: float = 0.0


class PageTimings(BaseModel):
    load_ms: float
    preprocess_ms: float
    checks_ms: float
    total_ms: float


class PageResult(BaseModel):
    page: int
    width: int
    height: int
    suitable_for_ocr: bool
    quality_score: float | None
    text_detected: bool | None  # None, если text_presence не запрашивалась
    issues: list[str]
    checks: dict[str, CheckResult]
    timings: PageTimings


class InputInfo(BaseModel):
    type: Literal["image", "pdf"]
    format: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    page_count: int | None = None


class ImageAnalysis(BaseModel):
    input: InputInfo
    suitable_for_ocr: bool
    quality_score: float | None
    processing_time_ms: float = 0.0  # заполняет сервис
    issues: list[str]
    checks: dict[str, CheckResult]
    timings: PageTimings


class DocumentSummary(BaseModel):
    page_count: int
    suitable_pages: list[int]
    problem_pages: list[int]
    blank_pages: list[int]  # в оценке не участвуют
    min_page_score: float | None


class DocumentResult(BaseModel):
    suitable_for_ocr: bool
    quality_score: float | None
    issues: list[str]
    summary: DocumentSummary


class PdfAnalysis(BaseModel):
    input: InputInfo
    suitable_for_ocr: bool
    quality_score: float | None
    processing_time_ms: float = 0.0  # заполняет сервис
    issues: list[str]
    summary: DocumentSummary
    pages: list[PageResult]


class ChecksList(BaseModel):
    checks: list[str]


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    workers: int
    requests_in_progress: int
    request_limit: int
