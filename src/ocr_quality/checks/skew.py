"""Наклон: на сколько градусов повёрнуты строки текста."""

from __future__ import annotations

import numpy as np

from ocr_quality.checks.base import Check, Measurement, not_applicable, ramp
from ocr_quality.page import Page


class SkewCheck(Check):
    """Ищет угол, при котором центры символов лучше всего выстраиваются в строки.

    Для каждого угла-кандидата «поворачиваем» центры символов и строим их
    гистограмму по вертикали. Если угол верный, символы одной строки попадают в
    одну корзину и гистограмма состоит из острых пиков. Перебираем углы от -45
    до 45 градусов (сначала грубо, потом точнее) и берём самый «острый».

    Положительный угол - поворот текста против часовой стрелки.
    Проверка критичная: по замерам Tesseract уже 6-8 градусов сильно портят
    распознавание, а 10 и больше - ломают его полностью.
    """

    name = "skew"
    unit = "degrees"
    critical = True
    weight = 1.0

    STRAIGHT = 2.0  # модуль угла: 2 градуса и меньше - оценка 1
    SKEWED = 8.0  # 8 и больше - оценка 0
    threshold = (STRAIGHT + SKEWED) / 2  # 5 градусов - граница

    MIN_CHARS = 20
    MIN_CONFIDENCE = 0.2  # насколько лучший угол должен выделяться среди остальных
    MAX_POINTS = 4000  # больше центров не берём - для скорости

    def measure(self, page: Page) -> Measurement:
        """Найти угол наклона строк текста."""
        if page.char_count < self.MIN_CHARS:
            return not_applicable("skew: not enough text to estimate line direction")

        points = page.char_centers
        if len(points) > self.MAX_POINTS:
            random_rows = np.random.default_rng(0).choice(len(points), self.MAX_POINTS, False)
            points = points[random_rows]
        bin_size = max(1.0, 0.5 * page.char_height)

        # Грубый поиск с шагом 0.5 градуса, затем точный с шагом 0.05 вокруг лучшего.
        coarse_angles = np.arange(-45, 45 + 1e-9, 0.5)
        coarse = [line_sharpness(points, a, bin_size) for a in coarse_angles]
        best = coarse_angles[int(np.argmax(coarse))]

        fine_angles = np.arange(best - 0.5, best + 0.5 + 1e-9, 0.05)
        fine = [line_sharpness(points, a, bin_size) for a in fine_angles]
        angle = float(fine_angles[int(np.argmax(fine))])

        # Уверенность: насколько лучший угол «острее» типичного.
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
    """Насколько резко центры символов собираются в строки при повороте на ``angle``.

    Чем больше точек попадает в одни и те же корзины гистограммы, тем больше
    сумма квадратов их количеств.
    """
    theta = np.deg2rad(angle)
    # Координата точки поперёк строк, повёрнутых на angle.
    across = points[:, 1] * np.cos(theta) + points[:, 0] * np.sin(theta)
    bins = ((across - across.min()) / bin_size).astype(int)
    counts = np.bincount(bins).astype(float)
    return float((counts**2).sum() / len(points) ** 2)
