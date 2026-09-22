from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ExtractedEvidence(BaseModel):
    document_id: str
    page_number: int
    start_offset: int
    end_offset: int
    quoted_text: str
    evidence_type: str = "clinical_snippet"


class ExtractedClinicalFact(BaseModel):
    fact_type: str  # diagnosis, procedure, symptom, service_date, pos, mdm, laterality, acuity, site
    value: Dict[str, Any]
    evidence: Optional[ExtractedEvidence] = None
    confidence: float = 1.0


class ExtractionResult(BaseModel):
    facts: List[ExtractedClinicalFact] = Field(default_factory=list)
    missing_documentation: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
