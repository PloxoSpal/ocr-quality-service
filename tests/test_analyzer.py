"""Итоговая оценка, чтение файлов и анализ PDF."""

import io
import math

import numpy as np
import pypdfium2 as pdfium
import pytest
from PIL import Image

from ocr_quality.analyzer import analyze_image, analyze_pdf, score_page, summarize_document
from ocr_quality.errors import BrokenFileError, FileTooLargeError, UnsupportedFileError
from ocr_quality.files import count_pdf_pages, open_pdf, read_image, read_pdf_page
from ocr_quality.schemas import CheckResult, PageResult, PageTimings

from synthetic import blank_page, blur, encode, make_page, make_pdf

ALL = ["blur", "contrast", "exposure", "noise", "resolution", "skew", "text_presence"]


# --- итоговая оценка страницы ----------------------------------------------------------


def check(score, critical=False, weight=1.0, status=None) -> CheckResult:
    if status is None:
        status = "passed" if score >= 0.5 else "failed"
    return CheckResult(
        passed={"passed": True, "failed": False}.get(status),
        score=score,
        status=status,
        critical=critical,
        weight=weight,
        value=None,
        unit="x",
        threshold=None,
        message=f"problem {score}" if status != "passed" else None,
    )


def test_quality_is_weighted_geometric_mean():
    _, score, _ = score_page({"a": check(1.0, weight=3), "b": check(0.25, weight=1)})
    assert score == pytest.approx(0.25**0.25, abs=1e-4)


def test_zero_score_is_raised_to_floor():
    _, score, _ = score_page({"a": check(1.0), "b": check(0.0)})
    assert score == pytest.approx(math.sqrt(0.1), abs=1e-4)


def test_failed_critical_check_makes_page_unsuitable_even_with_high_score():
    results = {f"ok{i}": check(1.0) for i in range(10)}
    results["blur"] = check(0.4, critical=True)
    suitable, score, issues = score_page(results)
    assert score > 0.9
    assert not suitable
    assert issues == ["problem 0.4"]


def test_failed_non_critical_check_only_lowers_score():
    results = {f"ok{i}": check(1.0, critical=True) for i in range(5)}
    results["noise"] = check(0.3)
    suitable, _, issues = score_page(results)
    assert suitable
    assert issues == ["problem 0.3"]


def test_low_overall_score_makes_page_unsuitable():
    suitable, _, issues = score_page({"a": check(0.55), "b": check(0.55), "c": check(0.55)})
    assert not suitable
    assert "overall quality score" in issues[-1]


def test_errored_check_makes_page_unsuitable():
    suitable, _, _ = score_page({"a": check(1.0), "b": check(None, status="error")})
    assert not suitable


# --- итог документа -----------------------------------------------------------------


def page_result(number, suitable, score, has_text=True) -> PageResult:
    return PageResult(
        page=number,
        width=10,
        height=10,
        suitable_for_ocr=suitable,
        quality_score=score,
        text_detected=has_text,
        issues=[],
        checks={},
        timings=PageTimings(load_ms=0, preprocess_ms=0, checks_ms=0, total_ms=0),
    )


def test_document_with_a_bad_page_is_unsuitable():
    result = summarize_document([page_result(1, True, 0.9), page_result(2, False, 0.3)])
    assert not result.suitable_for_ocr
    assert result.summary.problem_pages == [2]
    assert result.quality_score == pytest.approx(0.6)
    assert result.summary.min_page_score == pytest.approx(0.3)


def test_pages_without_text_are_ignored():
    result = summarize_document([page_result(1, True, 0.9), page_result(2, False, 0.1, False)])
    assert result.suitable_for_ocr
    assert result.summary.blank_pages == [2]


def test_document_without_text_is_unsuitable():
    assert not summarize_document([page_result(1, False, 0.1, False)]).suitable_for_ocr


# --- чтение файлов -----------------------------------------------------------------


def pil_bytes(img: Image.Image, fmt: str, **kwargs) -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


@pytest.mark.parametrize("fmt", [".png", ".jpg", ".bmp", ".tiff", ".webp"])
def test_supported_formats_are_decoded(fmt):
    page = make_page(width=400, height=300, lines=5)
    assert read_image(encode(page, fmt)).shape == (300, 400)


def test_transparent_background_becomes_white():
    rgba = np.zeros((40, 60, 4), np.uint8)  # полностью прозрачный чёрный
    rgba[10:20, 10:50] = (0, 0, 0, 255)  # непрозрачный чёрный «текст»
    gray = read_image(pil_bytes(Image.fromarray(rgba, "RGBA"), "PNG"))
    assert gray[0, 0] == 255
    assert gray[15, 30] == 0


def test_exif_rotation_is_applied():
    exif = Image.Exif()
    exif[0x0112] = 6  # при показе повернуть на 90 градусов
    gray = read_image(pil_bytes(Image.new("L", (80, 40), 255), "JPEG", exif=exif))
    assert gray.shape == (80, 40)


def test_bad_images():
    with pytest.raises(UnsupportedFileError):
        read_image(b"definitely not an image")
    with pytest.raises(UnsupportedFileError, match="GIF"):
        read_image(pil_bytes(Image.new("L", (10, 10)), "GIF"))
    data = encode(make_page(width=400, height=300, lines=5))
    with pytest.raises(BrokenFileError):
        read_image(data[: len(data) // 3])


def test_pixel_limit(monkeypatch):
    monkeypatch.setattr("ocr_quality.files.MAX_PIXELS", 5000)
    with pytest.raises(FileTooLargeError):
        read_image(encode(np.full((100, 100), 255, np.uint8)))


def test_scanned_pdf_page_is_taken_at_native_resolution():
    original = make_page(width=640, height=480, lines=8)
    document = open_pdf(make_pdf([original], resolution=72))
    gray = read_pdf_page(document, 0)
    assert gray.shape == (480, 640)
    assert np.abs(gray.astype(int) - original.astype(int)).mean() < 2


def test_pdf_page_without_scan_is_rendered():
    document = pdfium.PdfDocument.new()
    document.new_page(612, 792)  # формат US Letter, без картинок
    buffer = io.BytesIO()
    document.save(buffer)
    assert read_pdf_page(open_pdf(buffer.getvalue()), 0).shape == (2200, 1700)  # 200 DPI


def test_broken_pdf():
    with pytest.raises(BrokenFileError):
        count_pdf_pages(make_pdf([make_page(width=200, height=200, lines=2)])[:200])


# --- анализ целиком ------------------------------------------------------------------


def test_clean_image_is_suitable():
    result = analyze_image(encode(make_page()), ALL)
    assert result.suitable_for_ocr
    assert result.text_detected is True
    assert list(result.checks) == ALL


def test_only_requested_checks_are_run():
    result = analyze_image(encode(make_page()), ["skew", "blur"])
    assert list(result.checks) == ["skew", "blur"]
    assert result.text_detected is None


def test_pdf_pages_are_checked_separately():
    pdf = make_pdf([make_page(), blur(make_page(seed=1), 3.0), blank_page()])
    pages = analyze_pdf(pdf, ALL)
    assert [p.page for p in pages] == [1, 2, 3]
    assert [p.suitable_for_ocr for p in pages] == [True, False, False]
    assert pages[2].text_detected is False
