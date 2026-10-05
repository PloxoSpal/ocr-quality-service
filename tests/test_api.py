"""HTTP API целиком: настоящий сервис с пулом из двух процессов."""

from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient

from ocr_quality.config import settings
from ocr_quality.errors import WorkerCrashedError
from ocr_quality.main import create_app
from ocr_quality.services import AnalysisService

from synthetic import blur, encode, make_page, make_pdf

ALL = ["blur", "contrast", "exposure", "noise", "resolution", "skew", "text_presence"]


@pytest.fixture(scope="module")
def client():
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(settings, "WORKERS", 2)
        with TestClient(create_app()) as test_client:
            yield test_client


def service_of(client) -> AnalysisService:
    return client.app.state.service


def upload(data: bytes, name: str = "page.png") -> dict:
    return {"file": (name, data)}


def assert_error(response, status: int, code: str) -> dict:
    assert response.status_code == status, response.text
    body = response.json()
    assert body["error"]["code"] == code
    return body


# --- успешные запросы ---------------------------------------------------------------


def test_list_checks(client):
    assert client.get("/checks").json() == {"checks": ALL}


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_analyze_image(client):
    response = client.post("/analyze", files=upload(encode(make_page())))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["suitable_for_ocr"] is True
    assert 0.9 <= body["quality_score"] <= 1
    assert body["processing_time_ms"] > 0
    assert list(body["checks"]) == ALL
    assert body["checks"]["blur"]["passed"] is True
    assert body["input"]["type"] == "image"
    assert body["input"]["width"] == 1200


@pytest.mark.parametrize("checks", ["blur,skew", ["blur", "skew"]])
def test_analyze_selected_checks(client, checks):
    response = client.post("/analyze", files=upload(encode(make_page())), data={"checks": checks})
    assert list(response.json()["checks"]) == ["blur", "skew"]


def test_blurred_image_gets_issue(client):
    body = client.post("/analyze", files=upload(encode(blur(make_page(), 3.0)))).json()
    assert body["suitable_for_ocr"] is False
    assert body["issues"][0].startswith("blur:")


def test_analyze_pdf(client):
    pdf = make_pdf([make_page(), blur(make_page(seed=1), 3.0)])
    body = client.post("/analyze", files=upload(pdf, "doc.pdf")).json()
    assert body["input"]["page_count"] == 2
    assert [p["suitable_for_ocr"] for p in body["pages"]] == [True, False]
    assert body["summary"]["problem_pages"] == [2]
    assert body["suitable_for_ocr"] is False


def test_file_type_is_detected_by_content(client):
    response = client.post("/analyze", files=upload(encode(make_page(), ".jpg"), "scan.pdf"))
    assert response.json()["input"]["format"] == "JPEG"


# --- ошибки ------------------------------------------------------------------------


def test_unknown_check(client):
    response = client.post("/analyze", files=upload(encode(make_page())), data={"checks": "foo"})
    body = assert_error(response, 422, "unknown_checks")
    assert body["error"]["details"]["available"] == ALL


def test_missing_or_empty_file(client):
    assert_error(client.post("/analyze", data={"checks": "blur"}), 400, "invalid_input")
    assert_error(client.post("/analyze", files=upload(b"")), 400, "invalid_input")


def test_unsupported_and_broken_files(client):
    assert_error(client.post("/analyze", files=upload(b"hello")), 415, "unsupported_media_type")
    broken_png = encode(make_page())[:4000]
    assert_error(client.post("/analyze", files=upload(broken_png)), 422, "corrupted_file")
    broken_pdf = make_pdf([make_page()])[:300]
    assert_error(client.post("/analyze", files=upload(broken_pdf, "a.pdf")), 422, "corrupted_file")


def test_too_large_file(client, monkeypatch):
    monkeypatch.setattr(service_of(client), "max_upload_bytes", 1000)
    response = client.post("/analyze", files=upload(encode(make_page())))
    assert_error(response, 413, "payload_too_large")


def test_busy_service_returns_503(client, monkeypatch):
    service = service_of(client)
    monkeypatch.setattr(service, "requests_in_progress", service.request_limit)
    response = client.post("/analyze", files=upload(encode(make_page())))
    assert_error(response, 503, "overloaded")
    assert response.headers["retry-after"] == "1"


def test_crashed_worker_is_replaced():
    async def scenario():
        service = AnalysisService(
            workers=1, request_limit=4, request_timeout_s=30, max_upload_bytes=10**6
        )
        try:
            with pytest.raises(WorkerCrashedError):
                await service.run_in_pool(os._exit, 1)  # воркер умирает
            assert await service.run_in_pool(sum, [1, 2]) == 3  # пул создан заново
        finally:
            service.shutdown()

    asyncio.run(scenario())
