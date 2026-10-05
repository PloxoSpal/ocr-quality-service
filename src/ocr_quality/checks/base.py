"""Общее для всех проверок: базовый класс и перевод измерения в оценку от 0 до 1."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ocr_quality.page import Page
from ocr_quality.schemas import CheckResult, CheckStatus


@dataclass
class Measurement:
    """Что намерила проверка.

    ``score`` - оценка от 0 до 1; ``None`` значит, что проверку нельзя выполнить
    на этой странице (например, наклон текста, когда текста нет).
    """

    value: float | None
    score: float | None
    problem: str = ""  # что не так - показывается, если проверка не пройдена
    details: dict[str, Any] = field(default_factory=dict)


def not_applicable(reason: str, **details: Any) -> Measurement:
    """Результат для проверки, которую нельзя выполнить на этой странице."""
    return Measurement(value=None, score=None, problem=reason, details=details)


def ramp(value: float, bad: float, good: float) -> float:
    """Перевести значение в оценку: при ``bad`` - 0, при ``good`` - 1, между ними линейно.

    Работает в обе стороны: ``good`` может быть и больше, и меньше ``bad``.
    Граница «пройдено / не пройдено» (оценка 0.5) - ровно посередине.
    """
    return min(1.0, max(0.0, (value - bad) / (good - bad)))


class Check(ABC):
    """Базовый класс проверки качества.

    Наследник задаёт атрибуты класса и реализует ``measure``. Всё остальное
    (замер времени, статус, перехват ошибок) делает ``run``.
    """

    name: str  # имя проверки в API
    unit: str  # в чём измеряется value
    critical: bool = True  # провал делает страницу непригодной
    weight: float = 1.0  # вес в итоговой оценке
    threshold: float | None = None  # значение value на границе «пройдено / не пройдено»

    @abstractmethod
    def measure(self, page: Page) -> Measurement:
        """Измерить страницу."""

    def run(self, page: Page) -> CheckResult:
        """Выполнить проверку и оформить результат.

        Если проверка упала с исключением, анализ не падает целиком: проверка
        получает статус ``error``, а страница считается непригодной.
        """
        started = time.perf_counter()
        status: CheckStatus
        try:
            m = self.measure(page)
        except Exception as exc:
            m = Measurement(value=None, score=None, problem=f"{self.name}: internal error ({exc})")
            status, score = "error", None
        else:
            if m.score is None:
                status, score = "not_applicable", None
            else:
                score = round(m.score, 4)
                status = "passed" if score >= 0.5 else "failed"

        if status == "passed":
            passed = True
        elif status == "failed":
            passed = False
        else:
            passed = None

        return CheckResult(
            passed=passed,
            score=score,
            status=status,
            critical=self.critical,
            weight=self.weight,
            value=None if m.value is None else round(m.value, 4),
            unit=self.unit,
            threshold=self.threshold,
            message=None if status == "passed" else m.problem,
            details={
                key: round(v, 4) if isinstance(v, float) else v for key, v in m.details.items()
            },
            time_ms=round((time.perf_counter() - started) * 1000, 3),
        )
