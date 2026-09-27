"""OCR для сканов — отдельный, явно помеченный путь.

На MVP OCR не обязателен: скан определяется (почти нет текстового слоя),
документ помечается `needs_ocr`, и отчёт честно говорит, что анализировать
нечего. Если OCR включён, текст распознаётся tesseract с языками rus+kaz,
а отчёт помечает, что пункты получены распознаванием и цитаты могут
отличаться от оригинала.

Рендер страниц — pypdfium2 (Apache-2.0/BSD), а не PyMuPDF: у последнего
лицензия AGPL, что для сервиса означало бы обязанность открыть его код.
"""

from __future__ import annotations

import io
import shutil
from typing import Protocol


class OcrEngine(Protocol):
    name: str

    def pdf_pages(self, data: bytes) -> list[str]: ...

    def image(self, data: bytes) -> str: ...


class TesseractOcr:
    name = "tesseract"

    def __init__(self, languages: str = "rus+kaz", dpi: int = 300) -> None:
        self.languages = languages
        self.dpi = dpi

    @staticmethod
    def available() -> bool:
        if shutil.which("tesseract") is None:
            return False
        try:
            import pytesseract  # noqa: F401
        except ImportError:
            return False
        return True

    def _recognize(self, image) -> str:  # noqa: ANN001 — PIL.Image
        import pytesseract

        return pytesseract.image_to_string(image, lang=self.languages, config="--psm 6")

    def pdf_pages(self, data: bytes) -> list[str]:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(data)
        try:
            pages = []
            for i in range(len(pdf)):
                bitmap = pdf[i].render(scale=self.dpi / 72)
                pages.append(self._recognize(bitmap.to_pil()))
            return pages
        finally:
            pdf.close()

    def image(self, data: bytes) -> str:
        from PIL import Image

        return self._recognize(Image.open(io.BytesIO(data)))
