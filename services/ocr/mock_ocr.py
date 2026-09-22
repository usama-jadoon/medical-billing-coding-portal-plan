from typing import List
from services.ocr.base import OCRProvider, OCRResult, OCRPage


class MockOCRProvider(OCRProvider):
    def __init__(self, predefined_text: str = ""):
        self.predefined_text = predefined_text

    async def process(self, document_bytes: bytes, filename: str) -> OCRResult:
        text = self.predefined_text or document_bytes.decode("utf-8", errors="ignore")
        return OCRResult(
            pages=[
                OCRPage(
                    page_number=1,
                    text=text,
                )
            ],
            ocr_engine="mock-ocr",
            ocr_version="1.0.0",
        )
