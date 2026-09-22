from abc import ABC, abstractmethod
from typing import List
from services.ocr.base import OCRPage
from services.extraction.schemas import ExtractionResult


class FactExtractionProvider(ABC):
    @abstractmethod
    async def extract(self, document_id: str, pages: List[OCRPage], domain: str) -> ExtractionResult:
        """Extracts documented clinical facts tied directly to evidence snippets."""
        pass
