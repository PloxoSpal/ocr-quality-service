DATASET ?= dataset
PORT ?= 8000

.PHONY: install run test lint format check evaluate analyze-dataset bench bench-http \
        tesseract-reference docker-build docker-run

install:  ## Установить зависимости
	uv sync

run:  ## Запустить сервис локально
	uv run uvicorn ocr_quality.main:app --host 127.0.0.1 --port $(PORT)

test:  ## Все тесты (тесты на наборе данных пропускаются, если его нет)
	OCRQ_DATASET_DIR=$(DATASET) uv run pytest

lint:  ## Линтер, форматирование и типы
	uv run ruff check src tests scripts
	uv run ruff format --check src tests scripts
	uv run mypy

format:
	uv run ruff check --fix src tests scripts
	uv run ruff format src tests scripts

check: lint test  ## Всё, что запускал бы CI

evaluate:  ## Сравнить вердикты с разметкой и Tesseract -> eval/reports/evaluation.md
	uv run python scripts/evaluate.py --dataset $(DATASET)

analyze-dataset:  ## Отправить все файлы набора в запущенный сервис и напечатать вердикты
	uv run python scripts/analyze_dir.py $(DATASET)/images $(DATASET)/pdf --url http://127.0.0.1:$(PORT)

bench:  ## Benchmark без HTTP
	uv run python scripts/benchmark.py local

bench-http:  ## Нагрузочный benchmark по HTTP (сам поднимает сервис)
	uv run python scripts/benchmark.py http

tesseract-reference:  ## Пересобрать эталон Tesseract (нужен Docker)
	scripts/tesseract_reference.sh $(DATASET)/images eval/tesseract_reference.csv

docker-build:
	docker build -t ocr-quality:latest .

docker-run:
	docker run --rm -p $(PORT):8000 --cpus 4 --memory 2g -e WORKERS=4 ocr-quality:latest
