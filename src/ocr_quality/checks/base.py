import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ocr_quality.page import Page
from ocr_quality.schemas import CheckResult, CheckStatus


@dataclass
class Measurement:
    value: float | None
    score: float | None  # None - проверку нельзя выполнить на этой странице
    problem: str = ""
    details: dict[str, Any] = field(default_factory=dict)


def not_applicable(reason: str, **details: Any) -> Measurement:
    return Measurement(value=None, score=None, problem=reason, details=details)


def ramp(value: float, bad: float, good: float) -> float:
    # При bad - 0, при good - 1, между ними линейно; граница пройдено/нет (0.5) посередине.
    return min(1.0, max(0.0, (value - bad) / (good - bad)))


class Check(ABC):
    name: str
    unit: str
    critical: bool = True  # провал делает страницу непригодной
    weight: float = 1.0
    threshold: float | None = None

    @abstractmethod
    def measure(self, page: Page) -> Measurement: ...

    def run(self, page: Page) -> CheckResult:
        started = time.perf_counter()
        status: CheckStatus
        try:
            m = self.measure(page)
        except Exception as exc:
            # Упавшая проверка не роняет весь анализ, но делает страницу непригодной.
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
