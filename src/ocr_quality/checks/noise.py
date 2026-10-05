import math
from typing import override

import cv2
import numpy as np

from ocr_quality.checks.base import Check, Measurement, ramp
from ocr_quality.page import Page


class NoiseCheck(Check):
    """Пылинки вдали от текста и зернистость бумаги, итог - по худшей.

    Меряем только в области документа: фактура стола на фото чека шумом не считается.
    Некритичная.
    """

    name = "noise"
    unit = "specks_per_mpx"
    critical = False
    weight = 0.5

    FEW_SPECKS = 3_000
    MANY_SPECKS = 30_000
    threshold = (FEW_SPECKS + MANY_SPECKS) / 2

    LOW_SIGMA = 4
    HIGH_SIGMA = 12
    MAX_SPECK_AREA = 6

    @override
    def measure(self, page: Page) -> Measurement:
        specks = self.specks_per_megapixel(page)
        sigma = self.grain_sigma(page)
        specks_score = ramp(specks, self.MANY_SPECKS, self.FEW_SPECKS)
        sigma_score = ramp(sigma, self.HIGH_SIGMA, self.LOW_SIGMA)
        if specks_score <= sigma_score:
            problem = f"noise: {specks:.0f} specks per megapixel on the background"
        else:
            problem = f"noise: background noise sigma {sigma:.1f} grey levels"
        return Measurement(
            value=specks,
            score=min(specks_score, sigma_score),
            problem=problem,
            details={"sigma": sigma},
        )

    def specks_per_megapixel(self, page: Page) -> float:
        """Пылинок на мегапиксель; точки над «i» и знаки препинания рядом с буквами не в счёт."""
        reach = max(3, round(page.char_height or 8.0))
        near_text = cv2.dilate(page.text_mask, np.ones((2 * reach + 1, 2 * reach + 1), np.uint8))
        free = (near_text == 0) & (page.document_mask > 0)
        free_area = int(free.sum())
        if len(page.blobs) == 0 or free_area < 0.02 * free.size:
            return 0.0

        tiny = page.blobs[:, cv2.CC_STAT_AREA] <= self.MAX_SPECK_AREA
        centers = page.blob_centers[tiny].round().astype(int)
        x = np.clip(centers[:, 0], 0, free.shape[1] - 1)
        y = np.clip(centers[:, 1], 0, free.shape[0] - 1)
        specks = int(free[y, x].sum())
        return specks / free_area * 1e6

    @staticmethod
    def grain_sigma(page: Page) -> float:
        """Шум по Immerkaer, только по пикселям бумаги, чтобы края букв его не завышали."""
        kernel = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)
        response = np.abs(cv2.filter2D(page.gray.astype(np.float32), -1, kernel))
        paper = (page.paper_mask > 0) & (page.document_mask > 0)
        if paper.sum() < 1000:
            paper = np.ones_like(paper)
        return float(math.sqrt(math.pi / 2) * response[paper].mean() / 6)
