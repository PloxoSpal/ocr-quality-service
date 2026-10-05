"""Регрессия на выданном наборе данных (пропускается, если набора нет)."""

import csv
from pathlib import Path

import pytest

from ocr_quality.analyzer import analyze_image, analyze_pdf
from ocr_quality.checks import ALL_CHECKS
from ocr_quality.schemas import PageResult

pytestmark = pytest.mark.dataset

LABELS = Path(__file__).resolve().parents[1] / "eval" / "labels.csv"
ALL = list(ALL_CHECKS)


@pytest.fixture(scope="module")
def results(dataset_dir: Path) -> dict[str, PageResult]:
    return {
        path.name: analyze_image(path.read_bytes(), ALL)
        for path in sorted((dataset_dir / "images").iterdir())
        if path.suffix.lower() in {".png", ".jpg", ".jpeg"}
    }


def test_all_images_are_processed_without_errors(results):
    assert len(results) == 50
    for name, result in results.items():
        assert all(c.status != "error" for c in result.checks.values()), name


def test_verdicts_match_labels(results):
    with LABELS.open() as fh:
        labels = {row["file"]: row["expected"] for row in csv.DictReader(fh)}
    decided = {name: label for name, label in labels.items() if label in {"yes", "no"}}
    wrong = [n for n, label in decided.items() if results[n].suitable_for_ocr != (label == "yes")]
    assert len(wrong) / len(decided) <= 0.05, wrong


@pytest.mark.parametrize(
    "name", ["image_008.jpg", "image_022.png", "image_030.png", "image_047.png"]
)
def test_blurred_images_fail_blur(results, name):
    assert results[name].checks["blur"].status == "failed"


@pytest.mark.parametrize(("name", "angle"), [("image_002.jpg", 13.4), ("image_005.png", 9.7)])
def test_rotated_images_fail_skew(results, name, angle):
    skew = results[name].checks["skew"]
    assert skew.status == "failed"
    assert abs(skew.value) == pytest.approx(angle, abs=1.0)


def test_image_without_text(results):
    result = results["image_031.png"]
    assert result.checks["text_presence"].status == "failed"
    assert result.checks["skew"].status == "not_applicable"


@pytest.mark.parametrize("name", ["image_011.png", "image_012.png", "image_029.png"])
def test_clean_pages_pass_everything(results, name):
    assert all(c.status == "passed" for c in results[name].checks.values())


def test_all_pdfs_are_processed(dataset_dir):
    pages = 0
    for path in sorted((dataset_dir / "pdf").glob("*.pdf")):
        result = analyze_pdf(path.read_bytes(), ALL)
        assert all(c.status != "error" for p in result for c in p.checks.values()), path.name
        pages += len(result)
    assert pages == 122
