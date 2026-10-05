import argparse
import csv
import time
from pathlib import Path

import numpy as np

from ocr_quality.analyzer import analyze_image, analyze_pdf, summarize_document
from ocr_quality.checks import ALL_CHECKS

# Какая проверка должна срабатывать на какой размеченный дефект.
DEFECT_CHECKS = {
    "blur": "blur",
    "skew": "skew",
    "noise": "noise",
    "low_contrast": "contrast",
    "small_text": "resolution",
    "no_text": "text_presence",
}


def read_csv(path: Path) -> dict[str, dict[str, str]]:
    with path.open() as fh:
        return {row["file"]: row for row in csv.DictReader(fh)}


def spearman(x: list[float], y: list[float]) -> float:

    def ranks(values: list[float]) -> np.ndarray:
        values_arr = np.array(values)
        result = values_arr.argsort().argsort().astype(float)
        for value in np.unique(values_arr):  # одинаковым значениям - средний ранг
            result[values_arr == value] = result[values_arr == value].mean()
        return result

    return float(np.corrcoef(ranks(x), ranks(y))[0, 1])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("eval/dataset"))
    args = parser.parse_args()

    labels = read_csv(Path("eval/labels.csv"))
    tesseract = read_csv(Path("eval/tesseract_reference.csv"))
    checks = list(ALL_CHECKS)

    started = time.perf_counter()
    images = sorted(p for p in (args.dataset / "images").iterdir() if not p.name.startswith("."))
    results = {path.name: analyze_image(path.read_bytes(), checks) for path in images}
    ms_per_image = (time.perf_counter() - started) * 1000 / len(results)

    report = [
        "# Оценка на выданном наборе данных",
        "",
        f"Изображений: {len(results)}, проверки: {', '.join(checks)}, "
        f"{ms_per_image:.1f} мс на изображение (один поток).",
        "",
    ]

    # 1. Совпадение с разметкой (пограничные случаи не считаем).
    decided = {n: row["expected"] for n, row in labels.items() if row["expected"] in ("yes", "no")}
    wrong = [n for n, exp in decided.items() if results[n].suitable_for_ocr != (exp == "yes")]
    borderline = [n for n, row in labels.items() if row["expected"] == "borderline"]
    report += [
        "## Совпадение с разметкой",
        "",
        f"Совпало **{len(decided) - len(wrong)} из {len(decided)}** "
        f"(пограничных случаев не считали: {len(borderline)}).",
        "",
        *(f"- не совпало: {n}" for n in wrong),
        *(
            f"- пограничный: {n} -> {'пригоден' if results[n].suitable_for_ocr else 'непригоден'}"
            for n in borderline
        ),
        "",
    ]

    # 2. Ловит ли проверка свой дефект.
    report += [
        "## Обнаружение дефектов",
        "",
        "| дефект | проверка | случаев | поймано |",
        "|---|---|---|---|",
    ]
    for defect, check in DEFECT_CHECKS.items():
        tagged = [n for n, row in labels.items() if defect in row["defects"].split(";")]
        caught = [n for n in tagged if results[n].checks[check].status != "passed"]
        if tagged:
            report.append(f"| {defect} | {check} | {len(tagged)} | {len(caught)} |")

    # 3. Корреляция с Tesseract.
    scores = [results[n].quality_score or 0.0 for n in tesseract]
    confidence = [float(t["mean_conf"]) if int(t["words"]) else 0.0 for t in tesseract.values()]
    report += [
        "",
        "## Корреляция с Tesseract",
        "",
        "Спирмен между quality_score и уверенностью Tesseract: "
        f"**{spearman(scores, confidence):.2f}**.",
        "",
    ]

    # 4. Таблица по изображениям.
    report += [
        "## Изображения",
        "",
        "| файл | разметка | вердикт | оценка | проблемы |",
        "|---|---|---|---|---|",
    ]
    for name, result in results.items():
        verdict = "пригоден" if result.suitable_for_ocr else "**непригоден**"
        label = labels.get(name, {}).get("expected", "?")
        issues = "; ".join(result.issues) or "-"
        report.append(f"| {name} | {label} | {verdict} | {result.quality_score} | {issues} |")

    # 5. PDF.
    report += [
        "",
        "## PDF",
        "",
        "| документ | страниц | пригоден | оценка | проблемные страницы | пустые страницы |",
        "|---|---|---|---|---|---|",
    ]
    for path in sorted((args.dataset / "pdf").glob("*.pdf")):
        pages = analyze_pdf(path.read_bytes(), checks)
        document = summarize_document(pages)
        problems = ", ".join(map(str, document.summary.problem_pages)) or "-"
        blank = ", ".join(map(str, document.summary.blank_pages)) or "-"
        verdict = "да" if document.suitable_for_ocr else "**нет**"
        report.append(
            f"| {path.name} | {len(pages)} | {verdict} | {document.quality_score} "
            f"| {problems} | {blank} |"
        )

    output = Path("eval/reports/evaluation.md")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(report) + "\n")
    print("\n".join(report[: report.index("## Изображения")]))
    print(f"Полный отчёт: {output}")


if __name__ == "__main__":
    main()
