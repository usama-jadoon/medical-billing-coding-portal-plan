from services.extraction.base import FactExtractionProvider
from services.extraction.deterministic_extractor import DeterministicFactExtractor
from services.extraction.schemas import ExtractionResult, ExtractedClinicalFact, ExtractedEvidence


def get_fact_extractor() -> FactExtractionProvider:
    return DeterministicFactExtractor()
