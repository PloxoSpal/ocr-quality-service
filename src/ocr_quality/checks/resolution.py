"""Разрешение: достаточно ли крупные символы (в пикселях) для OCR."""

from ocr_quality.checks.base import Check, Measurement, not_applicable, ramp
from ocr_quality.page import Page


class ResolutionCheck(Check):
    """Меряет «настоящее» разрешение - типичную высоту символа в пикселях.

    DPI в файлах обычно нет (в выданном наборе его нет ни у одного файла), а
    для OCR важно, сколько пикселей приходится на букву. Поэтому меряем буквы
    напрямую, в пикселях исходного файла.
    """

    name = "resolution"
    unit = "px"
    critical = True
    weight = 1.0

    TINY = 4.0  # высота символа 4 px и меньше - оценка 0
    ENOUGH = 7.0  # 7 px и больше - оценка 1
    threshold = (TINY + ENOUGH) / 2  # 5.5 px - граница
    MIN_IMAGE_SIDE = 256  # картинки с короткой стороной меньше - сразу провал
    MIN_CHARS = 15

    def measure(self, page: Page) -> Measurement:
        """Оценить типичную высоту символа в пикселях исходного файла."""
        shorter_side = min(page.original_width, page.original_height)
        if shorter_side < self.MIN_IMAGE_SIDE:
            return Measurement(
                value=None,
                score=0.0,
                problem=f"resolution: image is too small ({shorter_side}px < "
                f"{self.MIN_IMAGE_SIDE}px)",
            )
        if page.char_count < self.MIN_CHARS:
            return not_applicable("resolution: not enough text to estimate character size")

        char_height = page.char_height / page.scale
        # Типичная высота символа текста кеглем 10 pt - около 1/12 дюйма.
        equivalent_dpi = round(char_height * 12)
        return Measurement(
            value=char_height,
            score=ramp(char_height, self.TINY, self.ENOUGH),
            problem=(
                f"resolution: characters are {char_height:.1f}px high "
                f"(need ~{self.threshold:.1f}px); rescan at a higher resolution"
            ),
            details={"equivalent_dpi_10pt": equivalent_dpi},
        )
