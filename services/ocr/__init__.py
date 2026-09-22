from services.ocr.base import OCRProvider, OCRResult, OCRPage
from services.ocr.local_ocr import LocalOCRProvider
from services.ocr.mock_ocr import MockOCRProvider
from services.api.config import settings


def get_ocr_provider() -> OCRProvider:
    if settings.OCR_PROVIDER == "mock":
        return MockOCRProvider()
    return LocalOCRProvider()
