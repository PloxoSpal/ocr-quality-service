import numpy as np

from ocr_quality.checks.base import Check, Measurement, not_applicable, ramp
from ocr_quality.page import Page


# Ищем угол, при котором центры символов лучше всего собираются в строки: при верном угле
# гистограмма их вертикальных координат состоит из острых пиков. Положительный угол -
# против часовой стрелки. Критичная: по Tesseract уже 6-8 градусов сильно портят OCR.
class SkewCheck(Check):
    name = "skew"
    unit = "degrees"
    critical = True
    weight = 1.0

    STRAIGHT = 2.0
    SKEWED = 8.0
    threshold = (STRAIGHT + SKEWED) / 2

    MIN_CHARS = 20
    MIN_CONFIDENCE = 0.2
    MAX_POINTS = 4000  # для скорости

    def measure(self, page: Page) -> Measurement:
        if page.char_count < self.MIN_CHARS:
            return not_applicable("skew: not enough text to estimate line direction")

        points = page.char_centers
        if len(points) > self.MAX_POINTS:
            random_rows = np.random.default_rng(0).choice(len(points), self.MAX_POINTS, False)
            points = points[random_rows]
        bin_size = max(1.0, 0.5 * page.char_height)

        # Сначала грубо с шагом 0.5 градуса, потом точно с шагом 0.05 вокруг лучшего.
        coarse_angles = np.linspace(-45, 45, 181)
        coarse = [line_sharpness(points, a, bin_size) for a in coarse_angles]
        best = coarse_angles[int(np.argmax(coarse))]

        fine_angles = np.linspace(best - 0.5, best + 0.5, 21)
        fine = [line_sharpness(points, a, bin_size) for a in fine_angles]
        angle = float(fine_angles[int(np.argmax(fine))])

        # Насколько лучший угол острее типичного: без явных строк угол не определить.
        confidence = 1 - float(np.median(coarse)) / max(fine)
        if confidence < self.MIN_CONFIDENCE:
            return not_applicable("skew: no dominant text line direction")

        return Measurement(
            value=angle,
            score=ramp(abs(angle), self.SKEWED, self.STRAIGHT),
            problem=f"skew: text is rotated by {angle:+.1f}° (limit ±{self.threshold:.0f}°)",
            details={"confidence": confidence},
        )


def line_sharpness(points: np.ndarray, angle: float, bin_size: float) -> float:
    # Чем больше точек в одних корзинах, тем больше сумма квадратов их количеств.
    theta = np.deg2rad(angle)
    across = points[:, 1] * np.cos(theta) + points[:, 0] * np.sin(theta)
    bins = ((across - across.min()) / bin_size).astype(int)
    counts = np.bincount(bins).astype(float)
    return float((counts**2).sum() / len(points) ** 2)
