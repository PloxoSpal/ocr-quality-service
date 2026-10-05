"""Все проверки качества.

Чтобы добавить проверку: создайте модуль с наследником ``Check`` и допишите его
экземпляр в список ниже. Больше ничего менять не нужно - проверка появится в
``GET /checks`` и станет доступна в ``POST /analyze``.
"""

from ocr_quality.checks.base import Check
from ocr_quality.checks.blur import BlurCheck
from ocr_quality.checks.contrast import ContrastCheck
from ocr_quality.checks.exposure import ExposureCheck
from ocr_quality.checks.noise import NoiseCheck
from ocr_quality.checks.resolution import ResolutionCheck
from ocr_quality.checks.skew import SkewCheck
from ocr_quality.checks.text_presence import TextPresenceCheck

ALL_CHECKS: dict[str, Check] = {
    check.name: check
    for check in [
        BlurCheck(),
        ContrastCheck(),
        ExposureCheck(),
        NoiseCheck(),
        ResolutionCheck(),
        SkewCheck(),
        TextPresenceCheck(),
    ]
}
