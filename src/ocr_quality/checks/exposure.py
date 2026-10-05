import math

from ocr_quality.checks.base import Check, Measurement, not_applicable, ramp
from ocr_quality.page import Page


# Абсолютная яркость: не слишком ли тёмная съёмка и не выцвели ли штрихи.
# Некритичная - только снижает итоговую оценку.
class ExposureCheck(Check):
    name = "exposure"
    unit = "gray_level"
    critical = False
    weight = 0.5

    DARK_PAPER = 70
    LIGHT_PAPER = 140
    threshold = (DARK_PAPER + LIGHT_PAPER) / 2

    FADED_INK = 235
    DARK_INK = 195
    MIN_CHARS = 15

    def measure(self, page: Page) -> Measurement:
        if page.char_count < self.MIN_CHARS or math.isnan(page.ink_level):
            return not_applicable("exposure: no text to measure exposure on")

        paper_score = ramp(page.paper_level, self.DARK_PAPER, self.LIGHT_PAPER)
        ink_score = ramp(page.ink_level, self.FADED_INK, self.DARK_INK)
        if paper_score <= ink_score:
            problem = f"exposure: page is under-exposed (paper level {page.paper_level:.0f}/255)"
        else:
            problem = f"exposure: text is washed out (ink level {page.ink_level:.0f}/255)"
        return Measurement(
            value=page.paper_level,
            score=min(paper_score, ink_score),
            problem=problem,
            details={"paper_level": page.paper_level, "ink_level": page.ink_level},
        )
