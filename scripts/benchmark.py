"""Benchmark сервиса.

Режим ``local`` (по умолчанию) - без HTTP: среднее время анализа одного
изображения с разбивкой по стадиям и проверкам, и сколько изображений в секунду
даёт пул из N процессов.

Режим ``http`` - поднимает сервис и нагружает его одновременными клиентами:
пропускная способность, задержка, число отказов 503 и память сервиса.

Usage:
    uv run python scripts/benchmark.py local [--repeats 5]
    uv run python scripts/benchmark.py http [--concurrency 1 4 16 32] [--pdf]
"""

from __future__ import annotations

import argparse
import asyncio
import multiprocessing
import os
import platform
import random
import subprocess
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import httpx
import numpy as np
import psutil

from ocr_quality.analyzer import analyze_image, init_worker
from ocr_quality.checks import ALL_CHECKS

DATASET = Path("OCR_team_developer_task/datatset")


def environment() -> str:
    """Описание машины, на которой идёт замер."""
    cpu = platform.processor() or platform.machine()
    if platform.system() == "Darwin":
        cpu = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True)
    ram = psutil.virtual_memory().total / 2**30
    return (
        f"CPU: {cpu.strip()}, {os.cpu_count()} ядер; RAM: {ram:.0f} GiB; "
        f"{platform.system()} {platform.release()}; Python {platform.python_version()}"
    )


def load_files(pdf: bool) -> list[tuple[str, bytes]]:
    """Прочитать файлы набора в память, чтобы чтение с диска не попало в замер."""
    folder = DATASET / ("pdf" if pdf else "images")
    return [
        (p.name, p.read_bytes()) for p in sorted(folder.iterdir()) if not p.name.startswith(".")
    ]


# --- режим local ---------------------------------------------------------------------


def run_local(repeats: int) -> None:
    """Замер анализа без HTTP."""
    images = load_files(pdf=False)
    names = list(ALL_CHECKS)
    init_worker()

    for _, data in images:  # прогрев
        analyze_image(data, names)

    stages: dict[str, list[float]] = {"load": [], "preprocess": [], "checks": [], "total": []}
    per_check: dict[str, list[float]] = {name: [] for name in names}
    for _ in range(repeats):
        for _, data in images:
            result = analyze_image(data, names)
            stages["load"].append(result.timings.load_ms)
            stages["preprocess"].append(result.timings.preprocess_ms)
            stages["checks"].append(result.timings.checks_ms)
            stages["total"].append(result.timings.total_ms)
            for name, check in result.checks.items():
                per_check[name].append(check.time_ms)

    print(f"### Анализ без HTTP\n\n{environment()}\n")
    print(f"{len(images)} изображений x {repeats} прогонов, все {len(names)} проверок.\n")
    print("| стадия | среднее, мс | p95, мс |\n|---|---|---|")
    for stage, values in stages.items():
        print(f"| {stage} | {np.mean(values):.1f} | {np.percentile(values, 95):.1f} |")
    print("\n| проверка | среднее, мс |\n|---|---|")
    for name, values in per_check.items():
        print(f"| {name} | {np.mean(values):.2f} |")

    workers = os.cpu_count() or 1
    payload = [data for _, data in images] * repeats
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(workers, mp_context=context, initializer=init_worker) as pool:
        list(pool.map(analyze_image, payload[:workers], [names] * workers))  # прогрев
        started = time.perf_counter()
        list(pool.map(analyze_image, payload, [names] * len(payload)))
        per_second = len(payload) / (time.perf_counter() - started)
    print(f"\nПул из {workers} процессов: **{per_second:.0f} изображений/с**.")


# --- режим http ----------------------------------------------------------------------


def encode_upload(name: str, data: bytes) -> tuple[bytes, str]:
    """Заранее закодировать файл в multipart, чтобы клиент не тратил на это CPU."""
    boundary = "benchmark-boundary-7MA4YWxkTrZu0gW"
    head = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    return (
        head + data + f"\r\n--{boundary}--\r\n".encode(),
        f"multipart/form-data; boundary={boundary}",
    )


async def load_level(url: str, uploads: list, clients: int, total: int) -> dict:
    """Нагрузка одного уровня: ``clients`` клиентов шлют запросы подряд, всего ``total``."""
    latencies: list[float] = []
    stats = {"ok": 0, "rejected": 0, "errors": 0, "pages": 0}
    sent = 0
    last_ok = 0.0

    async with httpx.AsyncClient(base_url=url, timeout=300) as client:

        async def one_client() -> None:
            nonlocal sent, last_ok
            while sent < total:
                body, content_type = uploads[sent % len(uploads)]
                sent += 1
                started = time.perf_counter()
                try:
                    response = await client.post(
                        "/analyze", content=body, headers={"content-type": content_type}
                    )
                except httpx.HTTPError:
                    stats["errors"] += 1
                    continue
                if response.status_code == 200:
                    last_ok = time.perf_counter()
                    latencies.append((last_ok - started) * 1000)
                    stats["ok"] += 1
                    stats["pages"] += response.json().get("summary", {}).get("page_count", 1)
                elif response.status_code == 503:
                    stats["rejected"] += 1
                    # Вежливый клиент ждёт, как просит сервер, со случайным разбросом.
                    await asyncio.sleep(random.uniform(0.2, 1.0))
                else:
                    stats["errors"] += 1

        started = time.perf_counter()
        await asyncio.gather(*(one_client() for _ in range(clients)))
        elapsed = (last_ok or time.perf_counter()) - started

    return {
        **stats,
        "per_second": stats["ok"] / elapsed,
        "pages_per_second": stats["pages"] / elapsed,
        "mean": float(np.mean(latencies)) if latencies else 0.0,
        "p95": float(np.percentile(latencies, 95)) if latencies else 0.0,
    }


def watch_memory(pid: int, stop: threading.Event, peak: list[float]) -> None:
    """Следить за пиковой памятью сервиса (сам процесс и его воркеры)."""
    process = psutil.Process(pid)
    while not stop.wait(0.5):
        try:
            tree = [process, *process.children(recursive=True)]
            peak[0] = max(peak[0], sum(p.memory_info().rss for p in tree) / 2**20)
        except psutil.Error:
            pass


def run_http(concurrency: list[int], requests: int, pdf: bool, env: list[str]) -> None:
    """Поднять сервис и нагрузить его."""
    uploads = [encode_upload(name, data) for name, data in load_files(pdf)]
    port = 8765
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "ocr_quality.main:app", "--port", str(port)],
        env={**os.environ, "LOG_LEVEL": "WARNING", **dict(e.split("=", 1) for e in env)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(120):  # ждём, пока сервис поднимется
            try:
                health = httpx.get(f"{url}/health").json()
                break
            except httpx.HTTPError:
                time.sleep(0.5)

        kind = "PDF-документов" if pdf else "изображений"
        print(f"### Нагрузка по HTTP\n\n{environment()}\n")
        print(
            f"Сервис: {health['workers']} процессов, лимит запросов {health['request_limit']}; "
            f"клиенты по кругу шлют {len(uploads)} {kind} набора данных.\n"
        )
        print(
            "| клиентов | запросов/с | страниц/с | задержка средняя, мс | p95, мс "
            "| отказов 503 | пик памяти, MiB |\n|---|---|---|---|---|---|---|"
        )
        for clients in concurrency:
            stop, peak = threading.Event(), [0.0]
            watcher = threading.Thread(target=watch_memory, args=(server.pid, stop, peak))
            watcher.start()
            r = asyncio.run(load_level(url, uploads, clients, max(requests, 4 * clients)))
            stop.set()
            watcher.join()
            print(
                f"| {clients} | {r['per_second']:.1f} | {r['pages_per_second']:.1f} "
                f"| {r['mean']:.0f} | {r['p95']:.0f} | {r['rejected']} | {peak[0]:.0f} |"
            )
    finally:
        server.terminate()
        server.wait(timeout=30)


def main() -> None:
    """Точка входа."""
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["local", "http"], nargs="?", default="local")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 2, 4, 8, 16, 32])
    parser.add_argument("--requests", type=int, default=200, help="запросов на уровень")
    parser.add_argument("--pdf", action="store_true", help="слать PDF вместо изображений")
    parser.add_argument("--env", nargs="*", default=[], help="настройки сервиса, WORKERS=значение")
    args = parser.parse_args()

    if args.mode == "local":
        run_local(args.repeats)
    else:
        run_http(args.concurrency, args.requests, args.pdf, args.env)


if __name__ == "__main__":
    main()
