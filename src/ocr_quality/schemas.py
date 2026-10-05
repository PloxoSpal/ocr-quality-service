from typing import Any, Literal

from pydantic import BaseModel

CheckStatus = Literal["passed", "failed", "not_applicable", "error"]


class CheckResult(BaseModel):
    """Результат одной проверки на одной странице."""

    passed: bool | None  # None - проверку нельзя было выполнить или она упала
    score: float | None  # оценка от 0 до 1, где 1 - идеально
    status: CheckStatus
    critical: bool  # провал критичной проверки делает страницу непригодной
    weight: float  # вес проверки в итоговой оценке
    value: float | None  # сырое измеренное значение
    unit: str  # в чём измерено value
    threshold: float | None  # значение value на границе «пройдено / не пройдено»
    message: str | None = None  # что не так (для проваленных и пропущенных проверок)
    details: dict[str, Any] = {}
    time_ms: float = 0.0


class PageTimings(BaseModel):
    """Сколько времени ушло на страницу, в миллисекундах."""

    load_ms: float  # чтение файла и декодирование
    preprocess_ms: float  # поиск текста и подготовка страницы
    checks_ms: float  # сами проверки
    total_ms: float


class PageResult(BaseModel):
    """Результат анализа одной страницы (изображение - это одна страница)."""

    page: int  # номер страницы, начиная с 1
    width: int
    height: int
    suitable_for_ocr: bool
    quality_score: float | None
    text_detected: bool | None  # None, если проверка text_presence не запрашивалась
    issues: list[str]
    checks: dict[str, CheckResult]
    timings: PageTimings


class InputInfo(BaseModel):
    """Что именно пришло на анализ."""

    type: Literal["image", "pdf"]
    format: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    page_count: int | None = None


class ImageAnalysis(BaseModel):
    """Ответ ``POST /analyze`` для изображения."""

    input: InputInfo
    suitable_for_ocr: bool
    quality_score: float | None
    processing_time_ms: float = 0.0  # заполняет сервис: время от приёма до ответа
    issues: list[str]
    checks: dict[str, CheckResult]
    timings: PageTimings


class DocumentSummary(BaseModel):
    """Сводка по страницам документа."""

    page_count: int
    suitable_pages: list[int]
    problem_pages: list[int]  # страницы с текстом, непригодные для OCR
    blank_pages: list[int]  # страницы без текста - в оценке не участвуют
    min_page_score: float | None


class DocumentResult(BaseModel):
    """Итог по многостраничному документу."""

    suitable_for_ocr: bool
    quality_score: float | None
    issues: list[str]
    summary: DocumentSummary


class PdfAnalysis(BaseModel):
    """Ответ ``POST /analyze`` для PDF."""

    input: InputInfo
    suitable_for_ocr: bool
    quality_score: float | None
    processing_time_ms: float = 0.0  # заполняет сервис: время от приёма до ответа
    issues: list[str]
    summary: DocumentSummary
    pages: list[PageResult]


class ChecksList(BaseModel):
    """Ответ ``GET /checks``."""

    checks: list[str]


class Health(BaseModel):
    """Ответ ``GET /health``."""

    status: Literal["ok"] = "ok"
    workers: int
    requests_in_progress: int
    request_limit: int
