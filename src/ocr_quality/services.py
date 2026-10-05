"""Сценарий анализа: проверить запрос, посчитать в пуле процессов, собрать ответ.

Как сервис держит нагрузку:

* проверки считаются в пуле из ``workers`` процессов - так используются все
  ядра, а сервер не замирает, пока идёт анализ;
* внутри сервиса одновременно не больше ``request_limit`` запросов (считаются
  или ждут свободного процесса). Остальные сразу получают 503, поэтому очередь
  и память не растут без предела.
"""

from __future__ import annotations

import asyncio
import multiprocessing
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from typing import Any

from ocr_quality.analyzer import analyze_image, analyze_pdf, init_worker, summarize_document
from ocr_quality.checks import ALL_CHECKS
from ocr_quality.errors import (
    AnalysisTimeoutError,
    FileTooLargeError,
    InvalidRequestError,
    ServiceBusyError,
    UnknownChecksError,
    WorkerCrashedError,
)
from ocr_quality.files import count_pdf_pages, is_pdf, read_image_info
from ocr_quality.schemas import ImageAnalysis, InputInfo, PdfAnalysis, RequestTimings


class AnalysisService:
    """Выполняет анализ файлов в пуле процессов и ограничивает число запросов."""

    def __init__(
        self, workers: int, request_limit: int, request_timeout_s: float, max_upload_bytes: int
    ) -> None:
        self.workers = workers
        self.request_limit = request_limit
        self.request_timeout_s = request_timeout_s
        self.max_upload_bytes = max_upload_bytes
        self.requests_in_progress = 0
        self.pool = self.create_pool()

    def create_pool(self) -> ProcessPoolExecutor:
        """Создать пул процессов.

        ``spawn`` запускает каждый воркер чистым процессом - это надёжно и
        одинаково работает на macOS и Linux.
        """
        return ProcessPoolExecutor(
            max_workers=self.workers,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=init_worker,
        )

    async def warm_up(self) -> None:
        """Заранее запустить все процессы, чтобы первый запрос не ждал их старта."""
        loop = asyncio.get_running_loop()
        await asyncio.gather(
            *(loop.run_in_executor(self.pool, time.sleep, 0.1) for _ in range(self.workers))
        )

    def shutdown(self) -> None:
        """Остановить пул процессов."""
        self.pool.shutdown(cancel_futures=True)

    async def analyze(
        self, data: bytes, requested_checks: list[str]
    ) -> ImageAnalysis | PdfAnalysis:
        """Проанализировать изображение или PDF.

        Сначала идут дешёвые проверки запроса (имена проверок, тип и размер
        файла), и только потом запрос занимает место в сервисе.
        """
        started = time.perf_counter()
        check_names = parse_check_names(requested_checks)
        input_info = describe_input(data, self.max_upload_bytes)

        if self.requests_in_progress >= self.request_limit:
            raise ServiceBusyError("Service is busy, retry later")
        self.requests_in_progress += 1
        try:
            if input_info.type == "pdf":
                pages = await self.run_in_pool(analyze_pdf, data, check_names)
                document = summarize_document(pages)
                return PdfAnalysis(
                    input=input_info,
                    suitable_for_ocr=document.suitable_for_ocr,
                    quality_score=document.quality_score,
                    processing_time_ms=round((time.perf_counter() - started) * 1000, 2),
                    issues=document.issues,
                    summary=document.summary,
                    pages=pages,
                )

            pool_started = time.perf_counter()
            page = await self.run_in_pool(analyze_image, data, check_names)
            pool_ms = (time.perf_counter() - pool_started) * 1000
            return ImageAnalysis(
                input=input_info,
                suitable_for_ocr=page.suitable_for_ocr,
                quality_score=page.quality_score,
                processing_time_ms=round((time.perf_counter() - started) * 1000, 2),
                issues=page.issues,
                checks=page.checks,
                timings=RequestTimings(
                    queue_ms=round(max(0.0, pool_ms - page.timings.total_ms), 2),
                    load_ms=page.timings.load_ms,
                    preprocess_ms=page.timings.preprocess_ms,
                    checks_ms=page.timings.checks_ms,
                ),
            )
        finally:
            self.requests_in_progress -= 1

    async def run_in_pool(self, function: Callable[..., Any], *args: Any) -> Any:
        """Выполнить функцию в процессе-воркере и дождаться результата.

        Пока воркер считает, сервер продолжает принимать другие запросы.
        """
        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(self.pool, function, *args), timeout=self.request_timeout_s
            )
        except TimeoutError as exc:
            raise AnalysisTimeoutError(
                f"Analysis did not finish within {self.request_timeout_s:g}s"
            ) from exc
        except BrokenProcessPool as exc:
            # Процесс-воркер умер (например, его убила система из-за памяти), и пул
            # больше не принимает задачи. Создаём новый, чтобы сервис жил дальше.
            self.pool = self.create_pool()
            raise WorkerCrashedError("A worker process crashed while analysing the file") from exc


def parse_check_names(requested: list[str]) -> list[str]:
    """Разобрать запрошенные проверки.

    Понимает повтор поля и список через запятую, игнорирует регистр, пробелы и
    дубликаты. Пустой запрос - значит все проверки.
    """
    names: list[str] = []
    for item in requested:
        for part in item.split(","):
            name = part.strip().lower()
            if name and name not in names:
                names.append(name)
    if not names:
        return list(ALL_CHECKS)

    unknown = [name for name in names if name not in ALL_CHECKS]
    if unknown:
        raise UnknownChecksError(
            f"Unknown checks: {', '.join(unknown)}",
            {"unknown": unknown, "available": list(ALL_CHECKS)},
        )
    return names


def describe_input(data: bytes, max_bytes: int) -> InputInfo:
    """Проверить загруженный файл и описать его. Тип определяется по содержимому, а не по имени."""
    if not data:
        raise InvalidRequestError("Uploaded file is empty")
    if len(data) > max_bytes:
        raise FileTooLargeError(f"File is too large: {len(data)} bytes (limit {max_bytes})")

    if is_pdf(data):
        return InputInfo(
            type="pdf", format="PDF", size_bytes=len(data), page_count=count_pdf_pages(data)
        )
    info = read_image_info(data)
    return InputInfo(
        type="image",
        format=info.format,
        size_bytes=len(data),
        width=info.width,
        height=info.height,
    )
