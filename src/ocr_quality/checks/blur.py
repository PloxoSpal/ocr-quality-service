"""Размытие: насколько резкие края у символов текста."""

from __future__ import annotations

import math

import cv2
import numpy as np

from ocr_quality.checks.base import Check, Measurement, not_applicable, ramp
from ocr_quality.page import Page, cut_text_tiles


class BlurCheck(Check):
    """Оценивает ширину размытия краёв символов в каждом текстовом тайле.

    Идея: у края с перепадом яркости ``C``, размытого гауссианом ширины ``sigma``,
    самый крутой перепад (градиент) равен ``C / (sigma * sqrt(2*pi))``. В каждом
    тайле берём самый сильный градиент и перепад яркости и находим ``sigma``.
    Такая оценка не зависит ни от контраста, ни от количества текста.

    Итоговая оценка - худшая из двух: по медианной ширине размытия и по доле
    размытых тайлов. Вторая ловит страницы, размытые только частично.
    """

    name = "blur"
    unit = "edge_sigma_px"
    critical = True
    weight = 1.5

    SHARP = 1.0  # ширина размытия, px: 1.0 и меньше - резко (оценка 1)
    BLURRED = 1.4  # 1.4 и больше - размыто (оценка 0)
    threshold = (SHARP + BLURRED) / 2  # 1.2 px - граница

    FEW_BLURRED_TILES = 0.1  # доля размытых тайлов, дающая оценку 1
    MANY_BLURRED_TILES = 0.5  # доля, дающая оценку 0
    MIN_TILE_CONTRAST = 25  # тайлы с меньшим перепадом яркости пропускаем
    MIN_TILES = 3

    def measure(self, page: Page) -> Measurement:
        """Измерить ширину размытия краёв в текстовых тайлах."""
        if page.text_tiles.sum() < self.MIN_TILES:
            return not_applicable("blur: not enough text to judge sharpness")

        # Модуль градиента: насколько резко меняется яркость в каждом пикселе.
        # Собель 3x3 даёт перепад, умноженный на 8, поэтому делим.
        gx = cv2.Sobel(page.gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(page.gray, cv2.CV_32F, 0, 1, ksize=3)
        gradient = cv2.magnitude(gx, gy) / 8

        sigmas = []
        for gray_tile, gradient_tile in zip(
            cut_text_tiles(page, page.gray), cut_text_tiles(page, gradient), strict=True
        ):
            low, high = np.percentile(gray_tile, [1, 99])
            contrast = high - low
            steepest = np.percentile(gradient_tile, 99)
            if contrast >= self.MIN_TILE_CONTRAST and steepest > 0:
                sigmas.append(contrast / (steepest * math.sqrt(2 * math.pi)))

        if len(sigmas) < self.MIN_TILES:
            return not_applicable("blur: text contrast is too low to judge sharpness")

        median_sigma = float(np.median(sigmas))
        blurred_share = float(np.mean(np.array(sigmas) > self.threshold))
        sigma_score = ramp(median_sigma, self.BLURRED, self.SHARP)
        share_score = ramp(blurred_share, self.MANY_BLURRED_TILES, self.FEW_BLURRED_TILES)

        if sigma_score <= share_score:
            problem = (
                f"blur: text edges are blurred (edge spread {median_sigma:.2f}px, "
                f"limit {self.threshold:.2f}px)"
            )
        else:
            problem = f"blur: {blurred_share:.0%} of the text area is blurred"
        return Measurement(
            value=median_sigma,
            score=min(sigma_score, share_score),
            problem=problem,
            details={"blurred_text_ratio": blurred_share, "text_tiles": len(sigmas)},
        )
