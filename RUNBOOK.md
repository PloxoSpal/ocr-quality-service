# RUNBOOK: запуск и проверка

Как поднять сервис, проверить его на наборе данных из задания, запустить тесты и benchmark. Устройство и решения описаны в [README](README.md).

## 1. Что нужно

| Что | Зачем |
|---|---|
| macOS или Linux | проверено на macOS 26 (Apple M5) |
| [uv](https://docs.astral.sh/uv/) | ставит Python 3.12 и зависимости |
| Docker (необязательно) | запуск в контейнере и пересборка эталона Tesseract |

Набор данных из архива с заданием нужно положить в `eval/dataset/`:

```
eval/dataset/images/   # 50 изображений
eval/dataset/pdf/      # 20 PDF
```

> В архиве папка называется `OCR_team_developer_task/datatset` (с опечаткой): её содержимое переносится в `eval/dataset/`. Другой путь можно передать через `DATASET=...` в `make` или `OCRQ_DATASET_DIR` для тестов.
>
> На macOS терминал может не иметь доступа к `~/Downloads` (`Operation not permitted`). Скопируйте папку с заданием в проект через Finder.

## 2. Установка

```bash
uv sync
```

Скопируйте `.env.example` в `.env` в корне проекта и задайте настройки.
Сервис читает `.env` при импорте `settings`; переменные окружения имеют приоритет.

## 3. Запуск

```bash
make run                     # http://127.0.0.1:8000
# или
uv run python -m ocr_quality.main
```

Документация API (Swagger): <http://127.0.0.1:8000/docs>.

В Docker:

```bash
make docker-build && make docker-run      # 4 CPU, 2 GiB, 4 воркера
# или
docker compose up --build
```

> В контейнере Python видит все CPU хоста, а не лимит `--cpus`, поэтому `WORKERS` нужно задавать равным лимиту. В `docker-compose.yml` это уже сделано.

## 4. Проверка работы

```bash
D=eval/dataset

curl -s localhost:8000/health
curl -s localhost:8000/checks
# {"checks":["blur","contrast","exposure","noise","resolution","skew","text_presence"]}

# Чистая страница - пригодна
curl -s -F file=@$D/images/image_012.png localhost:8000/analyze | jq '{suitable_for_ocr, quality_score, issues}'

# Повёрнутая страница - непригодна: "skew: text is rotated by -13.4°"
curl -s -F file=@$D/images/image_002.jpg localhost:8000/analyze | jq '{suitable_for_ocr, issues}'

# Только некоторые проверки, через запятую
curl -s -F file=@$D/images/image_047.png -F checks=blur,skew localhost:8000/analyze | jq '.checks | keys'

# PDF: итог по каждой странице и по документу
curl -s -F file=@$D/pdf/document_013.pdf localhost:8000/analyze | jq '{suitable_for_ocr, quality_score, summary}'
```

Весь набор данных через запущенный сервис:

```bash
make analyze-dataset
# ...по строке на файл...
# 70 files: 35 suitable, 35 not, 0 errors
```

Некорректные запросы:

```bash
curl -s -F file=@$D/images/image_001.png -F checks=foo localhost:8000/analyze   # 422 Unknown checks: foo...
curl -s -F checks=blur localhost:8000/analyze                                   # 422, нет поля file
echo hello > /tmp/fake.png && curl -s -F file=@/tmp/fake.png localhost:8000/analyze   # 415
```

## 5. Тесты и проверки кода

```bash
make test     # все тесты, включая регрессию на наборе данных (~10 с)
make lint     # ruff (стиль, импорты) и mypy
make check    # всё вместе
```

Если набора данных нет, тесты из `tests/test_dataset.py` пропускаются, а не падают.

## 6. Оценка на наборе данных

```bash
make evaluate              # отчёт -> eval/reports/evaluation.md
make tesseract-reference   # пересобрать эталон Tesseract (в Docker, ~3 минуты)
```

## 7. Benchmark

```bash
make bench         # без HTTP: время на изображение по стадиям и пропускная способность пула
make bench-http    # по HTTP: скрипт сам поднимает сервис на порту 8765 и нагружает его

uv run python scripts/benchmark.py http --concurrency 1 8 32 --requests 300
uv run python scripts/benchmark.py http --pdf
uv run python scripts/benchmark.py http --env MAX_REQUESTS=12    # перегрузка
```

Скрипт сам печатает описание машины. Нагрузочный клиент работает на той же машине, поэтому перед замером лучше закрыть тяжёлые приложения. Между прогонами на ноутбуке возможен разброс 15–25%.

## 8. Настройки

| Переменная | По умолчанию | Что задаёт |
|---|---|---|
| `WORKERS` | число ядер | сколько процессов параллельно считают проверки |
| `MAX_REQUESTS` | `4 × workers` | сколько запросов одновременно пускать в сервис; остальным 503 |
| `MAX_UPLOAD_MB` | `50` | максимальный размер файла, иначе 413 |
| `LOG_LEVEL` | `INFO` | уровень логирования |
| `OCRQ_DATASET_DIR` | `eval/dataset` | путь к набору данных для тестов |

Пороги проверок — константы в начале каждого файла `src/ocr_quality/checks/*.py`.

## 9. Если что-то не так

| Симптом | Что делать |
|---|---|
| `503 Service is busy` | Сервис занят: внутри уже `MAX_REQUESTS` запросов. Клиенту нужно повторить запрос позже. Сервису — увеличить `WORKERS` или `MAX_REQUESTS`, либо добавить реплики |
| `413 ... too large` | Файл больше `MAX_UPLOAD_MB`, картинка больше 60 Мп или в PDF больше 200 страниц |
| Первый запуск 1–3 с | Сервис заранее запускает процессы-воркеры, это один раз при старте |
| Тесты на наборе данных `skipped` | Набор не найден: задайте `OCRQ_DATASET_DIR` |
| `Address already in use` | Порт занят: `make run PORT=8001` |
