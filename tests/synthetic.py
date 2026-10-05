"""Синтетические страницы документа с дозированными дефектами для тестов."""

from __future__ import annotations

import io

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image

Gray = NDArray[np.uint8]

_WORDS = [
    "the",
    "quick",
    "brown",
    "fox",
    "jumps",
    "over",
    "lazy",
    "dog",
    "contract",
    "terms",
    "payment",
    "invoice",
    "total",
    "amount",
    "delivery",
    "services",
    "parties",
    "agreement",
    "section",
    "article",
    "schedule",
    "annex",
]


def make_page(
    width: int = 1200,
    height: int = 1500,
    font_scale: float = 0.8,
    thickness: int = 2,
    lines: int = 30,
    seed: int = 0,
) -> Gray:
    """Чистая белая страница с чёрными строками текста (шрифт Hershey)."""
    rng = np.random.default_rng(seed)
    page = np.full((height, width), 255, np.uint8)
    (_, char_h), _ = cv2.getTextSize("Ag", cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
    line_step = int(char_h * 2.2)
    y = int(height * 0.08)
    for _ in range(lines):
        if y > height * 0.92:
            break
        text = " ".join(rng.choice(_WORDS, size=12))
        cv2.putText(
            page,
            text,
            (int(width * 0.06), y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            0,
            thickness,
            cv2.LINE_AA,
        )
        y += line_step
    return page


def blank_page(width: int = 1200, height: int = 1500) -> Gray:
    """Белая страница без содержимого."""
    return np.full((height, width), 255, np.uint8)


def blur(img: Gray, sigma: float) -> Gray:
    """Гауссово размытие."""
    if sigma <= 0:
        return img.copy()
    return np.asarray(cv2.GaussianBlur(img, (0, 0), sigma), dtype=np.uint8)


def rotate(img: Gray, angle_deg: float) -> Gray:
    """Повернуть против часовой стрелки на ``angle_deg`` вокруг центра, с белой заливкой."""
    h, w = img.shape
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle_deg, 1.0)
    return np.asarray(
        cv2.warpAffine(img, matrix, (w, h), flags=cv2.INTER_LINEAR, borderValue=255),
        dtype=np.uint8,
    )


def fade(img: Gray, ink_level: int) -> Gray:
    """Осветлить чернила так, чтобы чёрный стал ``ink_level`` (бумага остаётся белой)."""
    scaled = ink_level + (img.astype(np.float32) / 255.0) * (255 - ink_level)
    return np.clip(scaled, 0, 255).astype(np.uint8)


def darken(img: Gray, factor: float) -> Gray:
    """Умножить все уровни яркости (имитация недоэкспонированной съёмки)."""
    return np.clip(img.astype(np.float32) * factor, 0, 255).astype(np.uint8)


def speckle(img: Gray, density: float, seed: int = 0) -> Gray:
    """Тёмные пятна в стиле «соль и перец»: ``density`` - доля пикселей."""
    rng = np.random.default_rng(seed)
    out = img.copy()
    mask = rng.random(img.shape) < density
    out[mask] = 0
    return out


def gaussian_noise(img: Gray, sigma: float, seed: int = 0) -> Gray:
    """Аддитивный гауссов шум."""
    rng = np.random.default_rng(seed)
    noisy = img.astype(np.float32) + rng.normal(0, sigma, img.shape)
    return np.clip(noisy, 0, 255).astype(np.uint8)


def downscale(img: Gray, factor: float) -> Gray:
    """Изменить размер в ``factor`` раз (< 1 снижает эффективное разрешение)."""
    h, w = img.shape
    size = (max(1, round(w * factor)), max(1, round(h * factor)))
    return np.asarray(cv2.resize(img, size, interpolation=cv2.INTER_AREA), dtype=np.uint8)


def encode(img: NDArray[np.uint8], fmt: str = ".png") -> bytes:
    """Закодировать массив через OpenCV (``.png``, ``.jpg``, ...)."""
    ok, buffer = cv2.imencode(fmt, img)
    assert ok
    return buffer.tobytes()


def make_pdf(pages: list[Gray], resolution: float = 100.0) -> bytes:
    """PDF из переданных растров (по одному встроенному изображению на страницу)."""
    images = [Image.fromarray(p) for p in pages]
    buffer = io.BytesIO()
    images[0].save(
        buffer, format="PDF", save_all=True, append_images=images[1:], resolution=resolution
    )
    return buffer.getvalue()
