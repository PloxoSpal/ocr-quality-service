import time
from dataclasses import dataclass

import cv2
import numpy as np

MAX_SIDE = 2048  # большие картинки уменьшаем: так быстрее

# Пиксель - «чернила», если он темнее среднего по окну 31x31 больше чем на 12.
INK_WINDOW = 31
INK_OFFSET = 12

MIN_CHAR_HEIGHT = 3
MIN_CHAR_AREA = 6
MAX_CHAR_HEIGHT_SHARE = 0.05  # от короткой стороны страницы
MAX_CHAR_WIDTH_TO_HEIGHT = 6
MIN_CHAR_FILL = 0.08  # доля чернил в прямоугольнике символа

LINE_GAP_IN_CHAR_HEIGHTS = 1.5
MIN_CHARS_IN_LINE = 3

MIN_TEXT_SHARE_IN_TILE = 0.04
DOCUMENT_MARGIN_TILES = 2


# Всё, что нужно проверкам. Размеры - в пикселях уменьшенной gray; в пиксели
# исходного файла переводит деление на scale.
@dataclass
class Page:
    gray: np.ndarray
    scale: float
    original_width: int
    original_height: int

    blobs: np.ndarray  # все пятна чернил: [x, y, ширина, высота, площадь]
    blob_centers: np.ndarray

    text_mask: np.ndarray
    char_count: int
    char_centers: np.ndarray
    char_height: float  # 0, если текста нет
    line_count: int

    tile_size: int
    text_tiles: np.ndarray  # таблица тайлов: True - в тайле есть текст
    document_mask: np.ndarray  # текстовые тайлы и отступ вокруг
    paper_mask: np.ndarray

    ink_level: float  # nan, если текста нет
    paper_level: float  # nan, если текста нет

    prepare_ms: float


def prepare_page(gray: np.ndarray) -> Page:
    started = time.perf_counter()
    original_height, original_width = gray.shape

    # 1. Уменьшаем большие картинки.
    scale = min(1.0, MAX_SIDE / max(original_height, original_width))
    if scale < 1.0:
        new_size = (max(1, round(original_width * scale)), max(1, round(original_height * scale)))
        gray = cv2.resize(gray, new_size, interpolation=cv2.INTER_AREA)

    # 2. Чернила - всё, что заметно темнее своего окружения.
    ink_mask = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, INK_WINDOW, INK_OFFSET
    )

    # 3. Разбиваем чернила на пятна и находим среди них символы.
    _, labels, stats, centers = cv2.connectedComponentsWithStats(ink_mask, connectivity=8)
    text = find_text(labels, stats, centers, gray.shape)

    # 4. Тайлы с текстом.
    tile_size = int(np.clip(round(6 * (text.char_height or 10.0)), 32, 256))
    text_tiles = find_text_tiles(text.mask, tile_size)
    text_area = tiles_to_mask(text_tiles, tile_size, gray.shape)

    # 5. Область документа: на фото это сам чек без стола.
    if text_tiles.any():
        margin = 2 * DOCUMENT_MARGIN_TILES + 1
        grown = cv2.dilate(text_tiles.astype(np.uint8), np.ones((margin, margin), np.uint8))
        document_mask = tiles_to_mask(grown, tile_size, gray.shape)
    else:
        document_mask = np.full_like(gray, 255)

    # 6. Бумага - не чернила и не рядом с ними.
    paper_mask = cv2.bitwise_not(cv2.dilate(ink_mask, np.ones((5, 5), np.uint8)))

    # 7. Яркость чернил и бумаги внутри текстовых тайлов.
    ink_values = gray[(text.mask > 0) & (text_area > 0)]
    paper_values = gray[(paper_mask > 0) & (text_area > 0)]
    if ink_values.size and paper_values.size:
        ink_level = float(np.percentile(ink_values, 25))  # сердцевины штрихов, а не края
        paper_level = float(np.median(paper_values))
    else:
        ink_level = paper_level = float("nan")

    return Page(
        gray=gray,
        scale=scale,
        original_width=original_width,
        original_height=original_height,
        blobs=stats[1:],  # строка 0 - фон, она не нужна
        blob_centers=centers[1:],
        text_mask=text.mask,
        char_count=text.char_count,
        char_centers=text.centers,
        char_height=text.char_height,
        line_count=text.line_count,
        tile_size=tile_size,
        text_tiles=text_tiles,
        document_mask=document_mask,
        paper_mask=paper_mask,
        ink_level=ink_level,
        paper_level=paper_level,
        prepare_ms=(time.perf_counter() - started) * 1000,
    )


@dataclass
class Text:
    mask: np.ndarray
    char_count: int
    centers: np.ndarray
    char_height: float
    line_count: int


def find_text(
    labels: np.ndarray, stats: np.ndarray, centers: np.ndarray, shape: tuple[int, ...]
) -> Text:
    # Три фильтра отсеивают пыль, фактуру фона и картинки.
    height, width = shape
    no_text = Text(
        mask=np.zeros(shape, np.uint8),
        char_count=0,
        centers=np.empty((0, 2)),
        char_height=0.0,
        line_count=0,
    )

    # Метка 0 - фон.
    w = stats[1:, cv2.CC_STAT_WIDTH].astype(float)
    h = stats[1:, cv2.CC_STAT_HEIGHT].astype(float)
    area = stats[1:, cv2.CC_STAT_AREA].astype(float)

    # 1. Похоже на символ по размеру и форме.
    max_height = max(MIN_CHAR_HEIGHT + 1, MAX_CHAR_HEIGHT_SHARE * min(height, width))
    looks_like_char = (
        (h >= MIN_CHAR_HEIGHT)
        & (h <= max_height)
        & (area >= MIN_CHAR_AREA)
        & (w <= MAX_CHAR_WIDTH_TO_HEIGHT * h)
        & (area / np.maximum(w * h, 1) >= MIN_CHAR_FILL)
    )
    if not looks_like_char.any():
        return no_text

    # 2. Примерно той же высоты, что типичный символ страницы.
    typical = typical_char_height(h[looks_like_char], area[looks_like_char])
    candidates = np.flatnonzero(looks_like_char & (h >= 0.4 * typical) & (h <= 3 * typical)) + 1
    if len(candidates) < MIN_CHARS_IN_LINE:
        return no_text

    is_candidate = np.zeros(len(stats), bool)
    is_candidate[candidates] = True
    candidate_mask = np.where(is_candidate[labels], 255, 0).astype(np.uint8)

    # 3. Склеиваем соседние символы в строки и оставляем строки хотя бы из 3 символов.
    gap = max(3, round(LINE_GAP_IN_CHAR_HEIGHTS * typical))
    lines = cv2.morphologyEx(candidate_mask, cv2.MORPH_CLOSE, np.ones((1, gap), np.uint8))
    line_total, line_labels = cv2.connectedComponents(lines, connectivity=8)

    line_of = np.zeros(len(stats), np.int32)
    ys, xs = np.nonzero(candidate_mask)
    line_of[labels[ys, xs]] = line_labels[ys, xs]

    chars_in_line = np.bincount(line_of[candidates], minlength=line_total)
    real_lines = chars_in_line >= MIN_CHARS_IN_LINE
    real_lines[0] = False
    text_labels = candidates[real_lines[line_of[candidates]]]
    if len(text_labels) == 0:
        return no_text

    is_text = np.zeros(len(stats), bool)
    is_text[text_labels] = True
    boxes = stats[text_labels, :4].astype(np.int32)
    return Text(
        mask=np.where(is_text[labels], 255, 0).astype(np.uint8),
        char_count=len(text_labels),
        centers=centers[text_labels],
        char_height=single_glyph_height(boxes),
        line_count=int(real_lines.sum()),
    )


def typical_char_height(heights: np.ndarray, areas: np.ndarray) -> float:
    # Пик гистограммы log2(высоты), взвешенной по площади: так тысячи пылинок
    # (фактура стола на фото чека) не перевешивают настоящие символы.
    log_h = np.log2(heights)
    step = 0.125
    edges = np.arange(log_h.min() - step / 2, log_h.max() + 2 * step, step)
    hist, edges = np.histogram(log_h, bins=edges, weights=areas)
    smoothed = np.convolve(hist, np.array([1, 2, 3, 2, 1]) / 9, mode="same")
    peak = int(np.argmax(smoothed))
    return float(2 ** ((edges[peak] + edges[peak + 1]) / 2))


def single_glyph_height(boxes: np.ndarray) -> float:
    # При низком разрешении буквы слипаются в широкие пятна высотой с самую высокую
    # букву. Пятна не шире своей высоты - почти всегда одиночные буквы.
    widths, heights = boxes[:, 2], boxes[:, 3]
    narrow = heights[widths <= heights]
    if len(narrow) >= max(20, 0.2 * len(heights)):
        return float(np.median(narrow))
    return float(np.median(heights))


def find_text_tiles(text_mask: np.ndarray, size: int) -> np.ndarray:
    padded = pad_to_tiles(text_mask, size)
    rows, cols = padded.shape[0] // size, padded.shape[1] // size
    share = padded.reshape(rows, size, cols, size).astype(np.float32).mean(axis=(1, 3)) / 255
    return share >= MIN_TEXT_SHARE_IN_TILE


def tiles_to_mask(tiles: np.ndarray, size: int, shape: tuple[int, ...]) -> np.ndarray:
    full = np.kron(tiles.astype(np.uint8), np.ones((size, size), np.uint8)) * 255
    return np.ascontiguousarray(full[: shape[0], : shape[1]])


def pad_to_tiles(image: np.ndarray, size: int) -> np.ndarray:
    pad_bottom = -image.shape[0] % size
    pad_right = -image.shape[1] % size
    return np.pad(image, ((0, pad_bottom), (0, pad_right)), mode="edge")


def cut_text_tiles(page: Page, image: np.ndarray) -> list[np.ndarray]:
    size = page.tile_size
    padded = pad_to_tiles(image, size)
    return [
        padded[row * size : (row + 1) * size, col * size : (col + 1) * size]
        for row, col in np.argwhere(page.text_tiles)
    ]
