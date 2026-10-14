from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class OCRPage(BaseModel):
    page_number: int
    text: str
    bounding_boxes: List[BoundingBox] = Field(default_factory=list)
    word_spans: List[Dict[str, Any]] = Field(default_factory=list)


class OCRResult(BaseModel):
    document_id: Optional[str] = None
    pages: List[OCRPage]
    ocr_engine: str
    ocr_version: str


class OCRProvider(ABC):
    @abstractmethod
    async def process(self, document_bytes: bytes, filename: str) -> OCRResult:
        """Processes a document binary and returns traceable page-level OCR text."""
        pass
