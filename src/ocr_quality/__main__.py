"""``python -m ocr_quality`` - запуск HTTP-сервиса через uvicorn."""

from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    """Разобрать host/port и запустить uvicorn (один процесс; воркеры - пул внутри него)."""
    parser = argparse.ArgumentParser(description="OCR quality service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("ocr_quality.main:app", host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    main()
