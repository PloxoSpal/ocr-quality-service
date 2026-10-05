from typing import override

from ocr_quality.checks.base import Check, Measurement, ramp
from ocr_quality.page import Page


class TextPresenceCheck(Check):
    """Число символов, выстроившихся в строки: пятна, фактура и рисунки в строки не складываются."""

    name = "text_presence"
    unit = "characters"
    critical = True
    weight = 1.0

    FEW = 10
    ENOUGH = 60
    threshold = (FEW + ENOUGH) / 2

    @override
    def measure(self, page: Page) -> Measurement:
        return Measurement(
            value=page.char_count,
            score=ramp(page.char_count, self.FEW, self.ENOUGH),
            problem=(
                f"text_presence: only {page.char_count} text characters found "
                f"(need ~{self.threshold:.0f}); the image may contain no text"
            ),
            details={"lines": page.line_count},
        )
