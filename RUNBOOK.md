# RUNBOOK

## Запуск

```bash
docker compose up --build        # http://localhost:8000, Swagger: /docs
```

Без Docker нужен [uv](https://docs.astral.sh/uv/):

```bash
uv sync
make run                         # http://127.0.0.1:8000
```

## Набор данных

Папки `dataset/images/` и `dataset/pdf/` в репозитории пустые. Положите в них изображения и PDF из архива с заданием:

```
dataset/images/   # 50 изображений
dataset/pdf/      # 20 PDF
```

Другой путь можно передать так: `make test DATASET=/path/to/dataset`.

## Проверка работы

```bash
curl -s localhost:8000/health
curl -s -F file=@dataset/images/image_002.jpg localhost:8000/analyze
curl -s -F file=@dataset/images/image_047.png -F checks=blur,skew localhost:8000/analyze
curl -s -F file=@dataset/pdf/document_013.pdf localhost:8000/analyze
```

## Команды

| Команда | Что делает |
|---|---|
| `make test` | все тесты (~10 с); без набора данных тесты на нём пропускаются |
| `make lint` | ruff и mypy |
| `make evaluate` | сравнить вердикты с разметкой → `eval/reports/evaluation.md` |
| `make analyze-dataset` | прогнать весь набор через запущенный сервис |
| `make bench` / `make bench-http` | benchmark без HTTP / под нагрузкой по HTTP |

## Настройки

Задаются переменными окружения или в `.env` (пример — `.env.example`).

| Переменная | По умолчанию | Что задаёт |
|---|---|---|
| `WORKERS` | число ядер | сколько процессов считают проверки |
| `MAX_REQUESTS` | `4 × WORKERS` | сколько запросов одновременно пускать; остальным 503 |
| `MAX_UPLOAD_MB` | `50` | максимальный размер файла |

В Docker `WORKERS` нужно задавать равным лимиту CPU: в `docker-compose.yml` это уже сделано.

## Если что-то не так

| Симптом | Что делать |
|---|---|
| `503 Service is busy` | повторить позже или увеличить `WORKERS` / `MAX_REQUESTS` |
| `Address already in use` | `make run PORT=8001` |
| тесты на наборе данных `skipped` | положить набор в `dataset/` |
