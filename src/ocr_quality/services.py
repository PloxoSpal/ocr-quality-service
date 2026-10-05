import asyncio
import multiprocessing
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from typing import Any

from ocr_quality.analyzer import analyze_file, init_worker
from ocr_quality.checks import ALL_CHECKS
from ocr_quality.errors import ServiceBusyError, UnknownChecksError, WorkerCrashedError
from ocr_quality.schemas import ImageAnalysis, PdfAnalysis


class AnalysisService:
    """Выполняет анализ в пуле процессов и не пускает больше request_limit запросов."""

    def __init__(self, workers: int, request_limit: int) -> None:
        self.workers = workers
        self.request_limit = request_limit
        self.requests_in_progress = 0
        self.pool = create_pool(workers)

    async def warm_up(self) -> None:
        """Запустить процессы заранее, чтобы первый запрос не ждал их старта."""
        await asyncio.gather(*(self.run_in_pool(time.sleep, 0.1) for _ in range(self.workers)))

    def shutdown(self) -> None:
        """Остановить пул, отменив запросы в очереди."""
        self.pool.shutdown(cancel_futures=True)

    async def analyze(self, data: bytes, checks: str | None) -> ImageAnalysis | PdfAnalysis:
        """Проанализировать файл; checks - имена проверок через запятую."""
        started = time.perf_counter()
        check_names = parse_check_names(checks)

        if self.requests_in_progress >= self.request_limit:
            raise ServiceBusyError("Service is busy, retry later")
        self.requests_in_progress += 1
        try:
            result = await self.run_in_pool(analyze_file, data, check_names)
        finally:
            self.requests_in_progress -= 1

        result.processing_time_ms = round((time.perf_counter() - started) * 1000, 2)
        return result

    async def run_in_pool(self, function: Callable[..., Any], *args: Any) -> Any:
        """Выполнить функцию в пуле; сломанный пул пересоздаётся."""
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(self.pool, function, *args)
        except BrokenProcessPool as exc:
            # Воркер умер (например, его убила система из-за памяти), и пул сломан навсегда.
            self.pool = create_pool(self.workers)
            raise WorkerCrashedError("A worker process crashed while analysing the file") from exc


def create_pool(workers: int) -> ProcessPoolExecutor:
    """Создать пул процессов; spawn одинаково работает на macOS и Linux."""
    return ProcessPoolExecutor(
        max_workers=workers,
        mp_context=multiprocessing.get_context("spawn"),
        initializer=init_worker,
    )


def parse_check_names(checks: str | None) -> list[str]:
    """Разобрать строку "blur,skew" в список; пустая строка - все проверки."""
    names = [name.strip() for name in (checks or "").split(",") if name.strip()]
    if not names:
        return list(ALL_CHECKS)

    unknown = [name for name in names if name not in ALL_CHECKS]
    if unknown:
        raise UnknownChecksError(
            f"Unknown checks: {', '.join(unknown)}. Available: {', '.join(ALL_CHECKS)}"
        )
    return names
