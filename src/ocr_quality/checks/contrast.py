import math
from typing import override

from ocr_quality.checks.base import Check, Measurement, not_applicable, ramp
from ocr_quality.page import Page


class ContrastCheck(Check):
    """Разница яркости штрихов текста и бумаги рядом с ними внутри текстовых областей."""

    name = "contrast"
    unit = "ratio"
    critical = True
    weight = 1.0

    LOW = 0.04  # (бумага - чернила) / 255
    HIGH = 0.16
    threshold = (LOW + HIGH) / 2
    MIN_CHARS = 15

    @override
    def measure(self, page: Page) -> Measurement:
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
