from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, StrictBool


class BehavioralHealthEncounterFact(BaseModel):
    model_config = ConfigDict(extra='forbid')
    session_duration_minutes: Optional[int] = Field(default=None, strict=True, ge=0, le=1440)
    is_telehealth: Optional[StrictBool] = None
    telehealth_modality: Optional[Literal['AUDIO_VIDEO', 'AUDIO_ONLY']] = None
    has_medical_em: Optional[StrictBool] = None
    patient_present: Optional[StrictBool] = None
    patient_location: Optional[Literal['HOME', 'OTHER']] = None
    service_kind: Optional[Literal['PSYCHOTHERAPY', 'DIAGNOSTIC_EVALUATION']] = None
    diagnostic_medical_services: Optional[StrictBool] = None
    em_mdm: Optional[Literal['LOW', 'MODERATE']] = None
    established_patient: Optional[StrictBool] = None


class DMEEncounterFact(BaseModel):
    model_config = ConfigDict(extra='forbid')
    equipment_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    order_type: Literal['PURCHASE', 'RENTAL', 'UNSPECIFIED'] = 'UNSPECIFIED'
    cmn_on_file: Optional[StrictBool] = None
    ordering_physician_npi: Optional[str] = Field(default=None, pattern=r'^\d{10}$')
    sleep_study_criteria_met: Optional[StrictBool] = None


def resolve_specialty_facts(facts, domain):
    """Unknown/conflicting fields stay unavailable; only evidenced facts contribute."""
    model = BehavioralHealthEncounterFact if domain == 'behavioral_health' else DMEEncounterFact
    values, evidence, conflicts = {}, {}, []
    for fact in facts:
        if fact.get('fact_type') != domain or not fact.get('evidence'):
            continue
        for name, value in fact.get('value', {}).items():
            if name not in model.model_fields:
                continue
            evidence.setdefault(name, []).append(fact['evidence'])
            if name in values and values[name] != value:
                conflicts.append(name)
            values[name] = value
    for name in set(conflicts):
        values.pop(name, None)
    return model.model_validate(values), evidence, sorted(set(conflicts))


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
