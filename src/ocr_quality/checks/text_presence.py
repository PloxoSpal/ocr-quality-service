"""Наличие текста: есть ли на картинке вообще что распознавать."""

from __future__ import annotations

from ocr_quality.checks.base import Check, Measurement, ramp
from ocr_quality.page import Page


class TextPresenceCheck(Check):
    """Считает символы, которые выстроились в слова и строки.

    Одиночные пятна, фактура и рисунки в строки не складываются, поэтому у
    фотографии или иллюстрации без подписей результат близок к нулю.
    """

    name = "text_presence"
    unit = "characters"
    critical = True
    weight = 1.0

    FEW = 10  # 10 символов и меньше - оценка 0
    ENOUGH = 60  # 60 и больше - оценка 1
    threshold = (FEW + ENOUGH) / 2  # 35 символов - граница

    def measure(self, page: Page) -> Measurement:
        """Посчитать символы и строки текста."""
        return Measurement(
            value=page.char_count,
            score=ramp(page.char_count, self.FEW, self.ENOUGH),
            problem=(
                f"text_presence: only {page.char_count} text characters found "
                f"(need ~{self.threshold:.0f}); the image may contain no text"
            ),
            details={"lines": page.line_count},
        )
