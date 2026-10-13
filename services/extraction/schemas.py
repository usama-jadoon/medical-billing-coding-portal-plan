from typing import List, Dict, Any, Optional, Literal
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


class BehavioralHealthEncounterFact(BaseModel):
    """Bounded behavioral-health facts. Unknown values stay None (unavailable),
    never defaulted to a billable value."""
    session_duration_minutes: Optional[int] = Field(
        default=None, ge=0,
        description="Strictly from documented start/stop times or a stated duration. "
                    "None means the duration is unavailable.")
    is_telehealth: bool = False
    telehealth_modality: Optional[Literal["AUDIO_VIDEO", "AUDIO_ONLY"]] = None
    has_medical_em: bool = False
    patient_present: Optional[bool] = Field(
        default=None, description="None means presence was not documented.")


class DMEEncounterFact(BaseModel):
    """Bounded DME facts. Unknown values stay unavailable, never defaulted."""
    equipment_name: str
    order_type: Literal["PURCHASE", "RENTAL", "UNSPECIFIED"] = "UNSPECIFIED"
    cmn_on_file: bool = False
    ordering_physician_npi: Optional[str] = None
    sleep_study_criteria_met: bool = False
