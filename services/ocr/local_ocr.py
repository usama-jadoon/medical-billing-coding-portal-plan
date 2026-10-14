import io
import asyncio
from typing import List
from pypdf import PdfReader
from services.ocr.base import OCRProvider, OCRResult, OCRPage


class LocalOCRProvider(OCRProvider):
    """
    Local OCR implementation extracting text per page using pypdf for PDF records,
    or raw decoding for text fixtures, preserving exact page traceability.
    """

    async def process(self, document_bytes: bytes, filename: str) -> OCRResult:
        return await asyncio.to_thread(self._process, document_bytes, filename)

    def _process(self, document_bytes: bytes, filename: str) -> OCRResult:
        pages: List[OCRPage] = []
        engine = "local-pypdf"
        version = "1.0.0"

        if filename.lower().endswith(".pdf"):
            try:
                reader = PdfReader(io.BytesIO(document_bytes))
                from services.api.config import settings
                if len(reader.pages) > settings.OCR_MAX_PAGES:
                    raise ValueError('Document exceeds OCR page limit.')
                for idx, page in enumerate(reader.pages, start=1):
                    extracted = page.extract_text() or ""
                    if not extracted.strip():
                        from services.ocr.tesseract import pdf_page
                        pages.append(pdf_page(document_bytes, idx - 1))
                        engine, version = 'local-pypdf-tesseract', '2'
                        continue
                    pages.append(
                        OCRPage(
                            page_number=idx,
                            text=extracted.strip(),
                        )
                    )
            except ValueError:
                raise
            except Exception as e:
                raise ValueError("PDF text extraction failed.") from e
        elif filename.lower().endswith(".txt"):
            # For plain text / synthetic mock documents
            try:
                decoded = document_bytes.decode("utf-8", errors="replace")
            except Exception:
                decoded = ""
            pages.append(
                OCRPage(
                    page_number=1,
                    text=decoded.strip(),
                )
            )
        elif filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff')):
            from services.ocr.tesseract import image_pages
            pages = image_pages(document_bytes)
            engine, version = 'local-tesseract', '2'
        else:
            raise ValueError('Unsupported local OCR document format.')

        if not pages:
            pages.append(OCRPage(page_number=1, text=""))

        return OCRResult(
            pages=pages,
            ocr_engine=engine,
            ocr_version=version,
        )
