"""Контраст: насколько чернила текста отличаются от бумаги."""

import math

from ocr_quality.checks.base import Check, Measurement, not_applicable, ramp
from ocr_quality.page import Page


class ContrastCheck(Check):
    """Сравнивает яркость штрихов текста с яркостью бумаги рядом с ними.

    Меряется только внутри текстовых областей, поэтому фотографии, тёмные поля
    и пустые места на странице на результат не влияют.
    """

    name = "contrast"
    unit = "ratio"
    critical = True
    weight = 1.0

    LOW = 0.04  # (бумага - чернила) / 255: 0.04 и меньше - оценка 0
    HIGH = 0.16  # 0.16 и больше - оценка 1
    threshold = (LOW + HIGH) / 2  # 0.10 - граница
    MIN_CHARS = 15

    def measure(self, page: Page) -> Measurement:
        """Вычислить контраст чернил и бумаги."""
        if page.char_count < self.MIN_CHARS or math.isnan(page.ink_level):
            return not_applicable("contrast: no text to measure contrast on")

        contrast = (page.paper_level - page.ink_level) / 255
        return Measurement(
            value=contrast,
            score=ramp(contrast, self.LOW, self.HIGH),
            problem=(
                f"contrast: text/background contrast {contrast:.2f} is below "
                f"{self.threshold:.2f}; text is faded or the background is too dark"
            ),
            details={"ink_level": page.ink_level, "paper_level": page.paper_level},
        )
