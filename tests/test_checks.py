"""Каждая проверка на синтетических страницах с дозированными дефектами."""

from __future__ import annotations

import pytest

from ocr_quality.checks import ALL_CHECKS
from ocr_quality.checks.base import Check, Measurement
from ocr_quality.page import Page, prepare_page
from ocr_quality.schemas import CheckResult

from synthetic import (
    blank_page,
    blur,
    darken,
    downscale,
    fade,
    gaussian_noise,
    make_page,
    rotate,
    speckle,
)


def run(name: str, image) -> CheckResult:
    return ALL_CHECKS[name].run(prepare_page(image))


# --- общее -------------------------------------------------------------------------


def test_all_checks_pass_on_clean_page(clean_page):
    page = prepare_page(clean_page)
    for name, check in ALL_CHECKS.items():
        result = check.run(page)
        assert result.status == "passed", (name, result)
        assert result.score >= 0.9, name


def test_checks_needing_text_are_not_applicable_on_blank_page():
    page = prepare_page(blank_page())
    for name in ("blur", "contrast", "exposure", "resolution", "skew"):
        result = ALL_CHECKS[name].run(page)
        assert result.status == "not_applicable", name
        assert result.passed is None
        assert result.message


def test_exception_in_check_does_not_break_analysis(clean_page):
    class BrokenCheck(Check):
        name = "broken"
        unit = "x"

        def measure(self, page: Page) -> Measurement:
            raise RuntimeError("boom")

    result = BrokenCheck().run(prepare_page(clean_page))
    assert result.status == "error"
    assert "boom" in result.message


def test_page_preparation_finds_text(clean_page):
    page = prepare_page(clean_page)
    assert page.char_count > 500
    assert page.line_count > 20
    assert 8 <= page.char_height <= 20
    assert prepare_page(blank_page()).char_count == 0
    assert prepare_page(speckle(blank_page(), 0.005)).char_count == 0


# --- blur -------------------------------------------------------------------------


def test_blur_score_drops_as_blur_grows(clean_page):
    scores = [run("blur", blur(clean_page, sigma)).score for sigma in (0, 1.0, 1.5, 2.5)]
    assert scores == sorted(scores, reverse=True)


def test_blur_measures_real_blur_width(clean_page):
    assert run("blur", clean_page).value < 1.0
    # sqrt(резкость^2 + 2.5^2) ~ 2.6: оценка следует за настоящей шириной размытия.
    assert 2.0 < run("blur", blur(clean_page, 2.5)).value < 3.2


def test_partially_blurred_page_fails(clean_page):
    page = clean_page.copy()
    half = page.shape[0] // 2
    page[:half] = blur(clean_page, 2.5)[:half]
    result = run("blur", page)
    assert result.status == "failed"
    assert 0.3 < result.details["blurred_text_ratio"] < 0.7


# --- skew -------------------------------------------------------------------------


@pytest.mark.parametrize("angle", [-15.0, -7.0, -2.5, 0.0, 2.5, 7.0, 15.0])
def test_skew_angle_is_found(clean_page, angle):
    assert run("skew", rotate(clean_page, angle)).value == pytest.approx(angle, abs=0.5)


@pytest.mark.parametrize(("angle", "status"), [(3, "passed"), (7, "failed"), (-12, "failed")])
def test_skew_limit(clean_page, angle, status):
    assert run("skew", rotate(clean_page, angle)).status == status


# --- contrast и exposure ------------------------------------------------------------


def test_contrast_drops_as_ink_fades(clean_page):
    values = [run("contrast", fade(clean_page, ink)).value for ink in (0, 120, 200, 235)]
    assert values == sorted(values, reverse=True)
    assert run("contrast", fade(clean_page, 240)).status == "failed"


def test_exposure_detects_dark_and_washed_out_pages(clean_page):
    assert run("exposure", darken(clean_page, 0.7)).status == "passed"
    assert "under-exposed" in run("exposure", darken(clean_page, 0.25)).message
    assert "washed out" in run("exposure", fade(clean_page, 230)).message


# --- noise ------------------------------------------------------------------------


def test_noise_grows_with_specks(clean_page):
    values = [run("noise", speckle(clean_page, d)).value for d in (0.0, 0.002, 0.01, 0.03)]
    assert values == sorted(values)
    assert run("noise", speckle(clean_page, 0.03)).status == "failed"
    assert run("noise", gaussian_noise(clean_page, 20)).status == "failed"


# --- resolution -------------------------------------------------------------------


def test_resolution_reports_height_in_original_pixels():
    page = make_page()
    big = make_page(width=3600, height=4500, font_scale=2.4, thickness=6)
    height = run("resolution", page).value
    # Половинный масштаб - вдвое меньшие буквы.
    assert run("resolution", downscale(page, 0.5)).value == pytest.approx(height / 2, rel=0.25)
    # Большая страница анализируется уменьшенной, но высота сообщается в исходных пикселях.
    assert run("resolution", big).value == pytest.approx(3 * height, rel=0.25)


def test_low_resolution_and_tiny_images_fail(clean_page):
    assert run("resolution", downscale(clean_page, 0.25)).status == "failed"
    assert "too small" in run("resolution", make_page(width=200, height=150, lines=3)).message


# --- text presence ----------------------------------------------------------------


def test_text_presence(clean_page):
    assert run("text_presence", clean_page).status == "passed"
    assert run("text_presence", blank_page()).status == "failed"
    assert run("text_presence", speckle(blank_page(), 0.01)).status == "failed"
