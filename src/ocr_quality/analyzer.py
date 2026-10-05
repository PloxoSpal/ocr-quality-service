import math
import time

import cv2
import numpy as np

from ocr_quality.checks import ALL_CHECKS
from ocr_quality.files import is_pdf, open_pdf, read_image, read_image_info, read_pdf_page
from ocr_quality.page import prepare_page
from ocr_quality.schemas import (
    CheckResult,
    DocumentResult,
    DocumentSummary,
    ImageAnalysis,
    InputInfo,
    PageResult,
    PageTimings,
    PdfAnalysis,
)

MIN_QUALITY_SCORE = 0.6
SCORE_FLOOR = 0.1  # чтобы одна нулевая оценка не обнуляла всё произведение


def init_worker() -> None:
    # Воркеров уже столько же, сколько ядер, - свои потоки OpenCV только мешали бы.
    cv2.setNumThreads(1)


def analyze_file(data: bytes, check_names: list[str]) -> ImageAnalysis | PdfAnalysis:
    # Выполняется в воркере. Тип файла определяем по содержимому, а не по имени.
    if is_pdf(data):
        pages = analyze_pdf(data, check_names)
        document = summarize_document(pages)
        return PdfAnalysis(
            input=InputInfo(type="pdf", format="PDF", size_bytes=len(data), page_count=len(pages)),
            suitable_for_ocr=document.suitable_for_ocr,
            quality_score=document.quality_score,
            issues=document.issues,
            summary=document.summary,
            pages=pages,
        )

    info = read_image_info(data)
    page = analyze_image(data, check_names)
    return ImageAnalysis(
        input=InputInfo(
            type="image",
            format=info.format,
            size_bytes=len(data),
            width=info.width,
            height=info.height,
        ),
        suitable_for_ocr=page.suitable_for_ocr,
        quality_score=page.quality_score,
        issues=page.issues,
        checks=page.checks,
        timings=page.timings,
    )


def analyze_image(data: bytes, check_names: list[str]) -> PageResult:
    started = time.perf_counter()
    gray = read_image(data)
    load_ms = (time.perf_counter() - started) * 1000
    return analyze_page(gray, check_names, page_number=1, load_ms=load_ms)


def analyze_pdf(data: bytes, check_names: list[str]) -> list[PageResult]:
    document = open_pdf(data)
    try:
        results = []
        for index in range(len(document)):
            started = time.perf_counter()
            gray = read_pdf_page(document, index)
            load_ms = (time.perf_counter() - started) * 1000
            results.append(analyze_page(gray, check_names, page_number=index + 1, load_ms=load_ms))
        return results
    finally:
        document.close()


def analyze_page(
    gray: np.ndarray, check_names: list[str], page_number: int = 1, load_ms: float = 0.0
) -> PageResult:
    page = prepare_page(gray)

    started = time.perf_counter()
    results = {name: ALL_CHECKS[name].run(page) for name in check_names}
    checks_ms = (time.perf_counter() - started) * 1000

    suitable, score, issues = score_page(results)
    text_check = results.get("text_presence")
    return PageResult(
        page=page_number,
        width=page.original_width,
        height=page.original_height,
        suitable_for_ocr=suitable,
        quality_score=score,
        text_detected=text_check.passed if text_check else None,
        issues=issues,
        checks=results,
        timings=PageTimings(
            load_ms=round(load_ms, 3),
            preprocess_ms=round(page.prepare_ms, 3),
            checks_ms=round(checks_ms, 3),
            total_ms=round(load_ms + page.prepare_ms + checks_ms, 3),
        ),
    )


def score_page(results: dict[str, CheckResult]) -> tuple[bool, float | None, list[str]]:
    # Взвешенное геометрическое среднее: одно очень плохое свойство (например, сильное
    # размытие) портит OCR, как бы хороши ни были остальные.
    scored = [r for r in results.values() if r.score is not None]
    quality = None
    if scored:
        total_weight = sum(r.weight for r in scored)
        log_sum = sum(r.weight * math.log(max(r.score or 0.0, SCORE_FLOOR)) for r in scored)
        quality = math.exp(log_sum / total_weight)

    failed = [r for r in results.values() if r.status == "failed"]
    errors = [r for r in results.values() if r.status == "error"]
    critical_failed = any(r.critical for r in failed)
    too_low = quality is not None and quality < MIN_QUALITY_SCORE

    issues = [r.message for r in failed + errors if r.message]
    if too_low and not critical_failed:
        issues.append(f"overall quality score {quality:.2f} is below {MIN_QUALITY_SCORE:.2f}")

    suitable = quality is not None and not critical_failed and not errors and not too_low
    return suitable, None if quality is None else round(quality, 4), issues


def summarize_document(pages: list[PageResult]) -> DocumentResult:
    # Страницы без текста (обложки, фото) в итоге документа не участвуют.
    blank = [p.page for p in pages if p.text_detected is False]
    text_pages = [p for p in pages if p.text_detected is not False]
    suitable = [p.page for p in text_pages if p.suitable_for_ocr]
    problems = [p.page for p in text_pages if not p.suitable_for_ocr]
    scores = [p.quality_score for p in text_pages if p.quality_score is not None]

    issues = []
    if not text_pages:
        issues.append("no page of the document contains text")
    if problems:
        issues.append(f"pages not suitable for OCR: {', '.join(map(str, problems))}")
    if blank:
        issues.append(f"pages without text (ignored): {', '.join(map(str, blank))}")

    return DocumentResult(
        suitable_for_ocr=bool(text_pages) and not problems,
        quality_score=round(sum(scores) / len(scores), 4) if scores else None,
        issues=issues,
        summary=DocumentSummary(
            page_count=len(pages),
            suitable_pages=suitable,
            problem_pages=problems,
            blank_pages=blank,
            min_page_score=round(min(scores), 4) if scores else None,
        ),
    )
