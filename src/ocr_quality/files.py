import io
from dataclasses import dataclass

import cv2
import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageOps

from ocr_quality.errors import BrokenFileError, FileTooLargeError, UnsupportedFileError

IMAGE_FORMATS = {"PNG", "JPEG", "WEBP", "TIFF", "BMP"}
MAX_PIXELS = 60_000_000  # защита от «бомб»
MAX_PDF_PAGES = 200
PDF_RENDER_DPI = 200

Image.MAX_IMAGE_PIXELS = None  # лимит пикселей проверяем сами


@dataclass
class ImageInfo:
    """Заголовок изображения, прочитанный без декодирования пикселей."""

    format: str
    width: int
    height: int
    has_alpha: bool


def is_pdf(data: bytes) -> bool:
    """Похож ли файл на PDF по сигнатуре в начале."""
    return b"%PDF-" in data[:1024]


def read_image_info(data: bytes) -> ImageInfo:
    """Прочитать формат и размер; неподдерживаемые и слишком большие файлы отклонить."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            info = ImageInfo(
                format=(img.format or "").upper(),
                width=img.width,
                height=img.height,
                has_alpha=img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info,
            )
    except Exception as exc:
        raise UnsupportedFileError("File is not a supported image or PDF") from exc

    if info.format not in IMAGE_FORMATS:
        raise UnsupportedFileError(f"Image format {info.format or 'unknown'} is not supported")
    check_pixel_limit(info.width, info.height)
    return info


def check_pixel_limit(width: int, height: int) -> None:
    """Отклонить картинку больше MAX_PIXELS."""
    if width * height > MAX_PIXELS:
        raise FileTooLargeError(
            f"Image is too large: {width}x{height} px exceeds {MAX_PIXELS} pixels"
        )


def read_image(data: bytes) -> np.ndarray:
    """Декодировать изображение в оттенки серого."""
    info = read_image_info(data)

    if info.has_alpha:
        # Прозрачный фон кладём на белую «бумагу», иначе он стал бы чёрным.
        try:
            with Image.open(io.BytesIO(data)) as img:
                rgba = ImageOps.exif_transpose(img).convert("RGBA")
        except Exception as exc:
            raise BrokenFileError(f"Cannot decode {info.format} image data") from exc
        white = Image.new("RGBA", rgba.size, "white")
        return np.array(Image.alpha_composite(white, rgba).convert("L"))

    # OpenCV сам поворачивает фото по EXIF и переводит 16-битные картинки в 8 бит.
    gray = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise BrokenFileError(f"Cannot decode {info.format} image data")
    return np.asarray(gray)


def open_pdf(data: bytes) -> pdfium.PdfDocument:
    """Открыть PDF и проверить число страниц."""
    try:
        document = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        raise BrokenFileError("Cannot open PDF (damaged or password-protected)") from exc

    pages = len(document)
    if pages == 0:
        document.close()
        raise BrokenFileError("PDF has no pages")
    if pages > MAX_PDF_PAGES:
        document.close()
        raise FileTooLargeError(f"PDF has too many pages: {pages} (limit {MAX_PDF_PAGES})")
    return document


def read_pdf_page(document: pdfium.PdfDocument, index: int) -> np.ndarray:
    """Получить страницу PDF в оттенках серого.

    Скан (одна картинка на всю страницу) берём как есть, в родном разрешении: так
    быстрее и точнее. Остальные страницы рисуем в PDF_RENDER_DPI.
    """
    try:
        page = document[index]
        scan = find_scan_image(page)
        if scan is not None:
            width, height = scan.get_px_size()
            check_pixel_limit(width, height)
            bitmap = scan.get_bitmap(render=False)
        else:
            scale = PDF_RENDER_DPI / 72
            width_pt, height_pt = page.get_size()
            check_pixel_limit(round(width_pt * scale), round(height_pt * scale))
            bitmap = page.render(scale=scale, grayscale=True)
        return bitmap_to_gray(bitmap.to_numpy())
    except pdfium.PdfiumError as exc:
        raise BrokenFileError(f"Cannot read PDF page {index + 1}") from exc


def find_scan_image(page: pdfium.PdfPage) -> pdfium.PdfImage | None:
    """Вернуть картинку скана, если страница - это одна неповёрнутая картинка во весь лист."""
    if page.get_rotation() != 0:
        return None
    images = list(page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE], max_depth=2))
    if len(images) != 1:
        return None
    image = images[0]

    page_width, page_height = page.get_size()
    left, bottom, right, top = image.get_bounds()
    covers_page = (right - left) * (top - bottom) >= 0.85 * page_width * page_height

    m = image.get_matrix()
    not_rotated = m.a > 0 and m.d > 0 and abs(m.b) < 1e-6 and abs(m.c) < 1e-6

    return image if covers_page and not_rotated else None


def bitmap_to_gray(array: np.ndarray) -> np.ndarray:
    """Перевести растр PDFium в серый; копия нужна, так как to_numpy() отдаёт память PDFium."""
    if array.ndim == 2:
        return array.copy()
    code = cv2.COLOR_BGR2GRAY if array.shape[2] == 3 else cv2.COLOR_BGRA2GRAY
    return cv2.cvtColor(array, code)
