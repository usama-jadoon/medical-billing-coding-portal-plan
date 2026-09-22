import io
from typing import List
from pypdf import PdfReader
from services.ocr.base import OCRProvider, OCRResult, OCRPage


class LocalOCRProvider(OCRProvider):
    """
    Local OCR implementation extracting text per page using pypdf for PDF records,
    or raw decoding for text fixtures, preserving exact page traceability.
    """

    async def process(self, document_bytes: bytes, filename: str) -> OCRResult:
        pages: List[OCRPage] = []
        engine = "local-pypdf"
        version = "1.0.0"

        if filename.lower().endswith(".pdf"):
            try:
                reader = PdfReader(io.BytesIO(document_bytes))
                for idx, page in enumerate(reader.pages, start=1):
                    extracted = page.extract_text() or ""
                    pages.append(
                        OCRPage(
                            page_number=idx,
                            text=extracted.strip(),
                        )
                    )
            except Exception as e:
                # If PDF reading fails, provide empty first page with fallback error note
                pages.append(
                    OCRPage(
                        page_number=1,
                        text="",
                    )
                )
        else:
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

        if not pages:
            pages.append(OCRPage(page_number=1, text=""))

        return OCRResult(
            pages=pages,
            ocr_engine=engine,
            ocr_version=version,
        )
