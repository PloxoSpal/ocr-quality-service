import time
from dataclasses import dataclass

import cv2
import numpy as np

# Большие картинки уменьшаем до этого размера по длинной стороне: так быстрее.
MAX_SIDE = 2048

# Бинаризация: пиксель считается «чернилами», если он темнее среднего по окну
# 31x31 больше чем на 12 уровней яркости.
INK_WINDOW = 31
INK_OFFSET = 12

# Какие пятна чернил могут быть символами.
MIN_CHAR_HEIGHT = 3  # px
MIN_CHAR_AREA = 6  # px
MAX_CHAR_HEIGHT_SHARE = 0.05  # не выше 5% короткой стороны страницы
MAX_CHAR_WIDTH_TO_HEIGHT = 6
MIN_CHAR_FILL = 0.08  # доля чернил в прямоугольнике символа

# Символы склеиваются в строки, если между ними меньше 1.5 высоты символа.
# Текстом считаются только строки хотя бы из 3 символов.
LINE_GAP_IN_CHAR_HEIGHTS = 1.5
MIN_CHARS_IN_LINE = 3

# Тайл (квадратный кусок страницы) считается текстовым, если текста в нём >= 4%.
MIN_TEXT_SHARE_IN_TILE = 0.04
# Область документа - текстовые тайлы плюс отступ в 2 тайла вокруг.
DOCUMENT_MARGIN_TILES = 2


@dataclass
class Page:
    """Всё, что известно о странице перед проверками.

    Все размеры - в пикселях уменьшенной картинки ``gray``; чтобы перевести в
    пиксели исходного файла, делите на ``scale``.
    """

    gray: np.ndarray  # серая картинка для анализа
    scale: float  # во сколько раз уменьшили (1.0 - не уменьшали)
    original_width: int
    original_height: int

    blobs: np.ndarray  # все пятна чернил: строки [x, y, ширина, высота, площадь]
    blob_centers: np.ndarray  # центры пятен: строки [x, y]

    text_mask: np.ndarray  # 255 - пиксели символов текста
    char_count: int  # сколько символов текста найдено
    char_centers: np.ndarray  # центры символов: строки [x, y]
    char_height: float  # типичная высота символа (0, если текста нет)
    line_count: int

    tile_size: int  # сторона тайла
    text_tiles: np.ndarray  # таблица тайлов: True - в тайле есть текст
    document_mask: np.ndarray  # 255 - область документа (текст и отступ вокруг)
    paper_mask: np.ndarray  # 255 - бумага (не чернила и не рядом с ними)

    ink_level: float  # яркость чернил текста (nan, если текста нет)
    paper_level: float  # яркость бумаги рядом с текстом (nan, если текста нет)

    prepare_ms: float  # сколько заняла подготовка


def prepare_page(gray: np.ndarray) -> Page:
    """Подготовить страницу к проверкам: найти текст, тайлы, бумагу и уровни яркости."""
    started = time.perf_counter()
    original_height, original_width = gray.shape

    # 1. Уменьшаем большие картинки.
    scale = min(1.0, MAX_SIDE / max(original_height, original_width))
    if scale < 1.0:
        new_size = (max(1, round(original_width * scale)), max(1, round(original_height * scale)))
        gray = cv2.resize(gray, new_size, interpolation=cv2.INTER_AREA)

    # 2. Ищем чернила: всё, что заметно темнее своего окружения.
    ink_mask = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, INK_WINDOW, INK_OFFSET
    )

    # 3. Разбиваем чернила на отдельные пятна и находим среди них символы текста.
    _, labels, stats, centers = cv2.connectedComponentsWithStats(ink_mask, connectivity=8)
    text = find_text(labels, stats, centers, gray.shape)

    # 4. Делим страницу на тайлы и отмечаем те, где есть текст.
    tile_size = int(np.clip(round(6 * (text.char_height or 10.0)), 32, 256))
    text_tiles = find_text_tiles(text.mask, tile_size)
    text_area = tiles_to_mask(text_tiles, tile_size, gray.shape)

    # 5. Область документа: текстовые тайлы плюс отступ (на фото - сам чек без стола).
    if text_tiles.any():
        margin = 2 * DOCUMENT_MARGIN_TILES + 1
        grown = cv2.dilate(text_tiles.astype(np.uint8), np.ones((margin, margin), np.uint8))
        document_mask = tiles_to_mask(grown, tile_size, gray.shape)
    else:
        document_mask = np.full_like(gray, 255)

    # 6. Бумага - пиксели, которые не чернила и не соседствуют с чернилами.
    paper_mask = cv2.bitwise_not(cv2.dilate(ink_mask, np.ones((5, 5), np.uint8)))

    # 7. Яркость чернил и бумаги внутри текстовых областей.
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
    """Найденный текст."""

    mask: np.ndarray
    char_count: int
    centers: np.ndarray
    char_height: float
    line_count: int


def find_text(
    labels: np.ndarray, stats: np.ndarray, centers: np.ndarray, shape: tuple[int, ...]
) -> Text:
    """Найти символы текста среди пятен чернил.

    Шаги:
    1. оставить пятна, похожие на символы по размеру и форме;
    2. оставить пятна примерно одной высоты с типичным символом страницы;
    3. склеить соседние символы в строки и оставить только строки из 3+ символов.
    Так отсеиваются пыль, фактура фона и картинки.
    """
    height, width = shape
    no_text = Text(
        mask=np.zeros(shape, np.uint8),
        char_count=0,
        centers=np.empty((0, 2)),
        char_height=0.0,
        line_count=0,
    )

    # Метка 0 - фон, поэтому смотрим строки статистики начиная с 1.
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

    # Таблица «метка пятна -> кандидат ли это» и маска пикселей кандидатов.
    is_candidate = np.zeros(len(stats), bool)
    is_candidate[candidates] = True
    candidate_mask = np.where(is_candidate[labels], 255, 0).astype(np.uint8)

    # 3. Склеиваем символы по горизонтали: каждое слово или строка - одно пятно.
    gap = max(3, round(LINE_GAP_IN_CHAR_HEIGHTS * typical))
    lines = cv2.morphologyEx(candidate_mask, cv2.MORPH_CLOSE, np.ones((1, gap), np.uint8))
    line_total, line_labels = cv2.connectedComponents(lines, connectivity=8)

    # Для каждого символа узнаём номер строки, в которую он попал.
    line_of = np.zeros(len(stats), np.int32)
    ys, xs = np.nonzero(candidate_mask)
    line_of[labels[ys, xs]] = line_labels[ys, xs]

    # Оставляем символы из строк, где символов хотя бы MIN_CHARS_IN_LINE.
    chars_in_line = np.bincount(line_of[candidates], minlength=line_total)
    real_lines = chars_in_line >= MIN_CHARS_IN_LINE
    real_lines[0] = False  # метка 0 - фон
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
    """Самая «весомая» высота пятен: пик гистограммы log2(высоты), взвешенной по площади.

    Взвешивание по площади не даёт тысячам мелких пылинок (например, фактуре
    стола на фото чека) перевесить настоящие символы.
    """
    log_h = np.log2(heights)
    step = 0.125  # 1/8 октавы
    edges = np.arange(log_h.min() - step / 2, log_h.max() + 2 * step, step)
    hist, edges = np.histogram(log_h, bins=edges, weights=areas)
    smoothed = np.convolve(hist, np.array([1, 2, 3, 2, 1]) / 9, mode="same")
    peak = int(np.argmax(smoothed))
    return float(2 ** ((edges[peak] + edges[peak + 1]) / 2))


def single_glyph_height(boxes: np.ndarray) -> float:
    """Медианная высота одиночных букв.

    При низком разрешении соседние буквы слипаются в широкие пятна высотой с
    самую высокую букву. Пятна не шире своей высоты - почти всегда одиночные
    буквы, поэтому берём их, если их достаточно.
    """
    widths, heights = boxes[:, 2], boxes[:, 3]
    narrow = heights[widths <= heights]
    if len(narrow) >= max(20, 0.2 * len(heights)):
        return float(np.median(narrow))
    return float(np.median(heights))


def find_text_tiles(text_mask: np.ndarray, size: int) -> np.ndarray:
    """Таблица тайлов страницы: True там, где текст занимает хотя бы 4% тайла."""
    padded = pad_to_tiles(text_mask, size)
    rows, cols = padded.shape[0] // size, padded.shape[1] // size
    # Доля текстовых пикселей в каждом тайле.
    share = padded.reshape(rows, size, cols, size).astype(np.float32).mean(axis=(1, 3)) / 255
    return share >= MIN_TEXT_SHARE_IN_TILE


def tiles_to_mask(tiles: np.ndarray, size: int, shape: tuple[int, ...]) -> np.ndarray:
    """Растянуть таблицу тайлов до маски размером со страницу (255 - отмеченный тайл)."""
    full = np.kron(tiles.astype(np.uint8), np.ones((size, size), np.uint8)) * 255
    return np.ascontiguousarray(full[: shape[0], : shape[1]])


def pad_to_tiles(image: np.ndarray, size: int) -> np.ndarray:
    """Дополнить картинку повтором краёв, чтобы она делилась на тайлы без остатка."""
    pad_bottom = -image.shape[0] % size
    pad_right = -image.shape[1] % size
    return np.pad(image, ((0, pad_bottom), (0, pad_right)), mode="edge")


def cut_text_tiles(page: Page, image: np.ndarray) -> list[np.ndarray]:
    """Вырезать из картинки (размером со страницу) все текстовые тайлы."""
    size = page.tile_size
    padded = pad_to_tiles(image, size)
    return [
        padded[row * size : (row + 1) * size, col * size : (col + 1) * size]
        for row, col in np.argwhere(page.text_tiles)
    ]
