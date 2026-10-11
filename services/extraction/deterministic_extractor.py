import re
from typing import List, Dict, Any, Optional
from services.ocr.base import OCRPage
from services.extraction.base import FactExtractionProvider
from services.extraction.schemas import (
    ExtractionResult,
    ExtractedClinicalFact,
    ExtractedEvidence,
)


class DeterministicFactExtractor(FactExtractionProvider):
    """
    Deterministic fact extractor that identifies documented clinical entities,
    captures exact text offset boundaries, and enforces that every material fact
    has linked evidence.
    """

    PATTERNS = [
        # Service Date
        {
            "fact_type": "service_date",
            "regex": r"(?:Date of Service|DOS|Encounter Date|Service Date|Date):\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})",
            "extractor": lambda m: {"service_date": m.group(1).strip()},
        },
        # Place of Service
        {
            "fact_type": "place_of_service",
            "regex": r"\b(Emergency Department|Emergency Room|ED|Office Visit|Outpatient Clinic|Inpatient Hospital|Urgent Care)\b",
            "extractor": lambda m: {"pos_description": m.group(1).strip()},
        },
        # Chief Complaint
        {
            "fact_type": "chief_complaint",
            "regex": r"(?:Chief Complaint|CC|Reason for Visit):\s*([^\n\r]+)",
            "extractor": lambda m: {"complaint": m.group(1).strip()},
        },
        # Diagnoses
        {
            "fact_type": "diagnosis",
            "regex": r"(?:Assessment|Impression|Diagnosis|Documented Diagnosis):\s*([^\n\r]+)",
            "extractor": lambda m: {"condition": m.group(1).strip()},
        },
        {
            "fact_type": "diagnosis",
            "regex": r"(Acute appendicitis|Type 2 diabetes mellitus|Essential hypertension|Acute chest pain|Unspecified asthma|Acute bronchitis|Fracture of [^\n\r,]+|Laceration of [^\n\r,]+|COVID-19)",
            "extractor": lambda m: {"condition": m.group(1).strip()},
        },
        # Symptoms
        {
            "fact_type": "symptom",
            "regex": r"(right lower quadrant pain|RLQ pain|abdominal pain|fever|nausea|vomiting|shortness of breath|headache|cough|dizziness)",
            "extractor": lambda m: {"symptom": m.group(1).strip()},
        },
        # Procedures & Interventions
        {
            "fact_type": "procedure",
            "regex": r"(?:Procedure|Intervention):\s*([^\n\r]+)",
            "extractor": lambda m: {"procedure_name": m.group(1).strip()},
        },
        {
            "fact_type": "procedure",
            "regex": r"(Laparoscopic appendectomy|Appendectomy|CT abdomen and pelvis|EKG 12-lead|Intravenous fluid administration|Wound repair|Chest X-ray)",
            "extractor": lambda m: {"procedure_name": m.group(1).strip()},
        },
        # Laterality
        {
            "fact_type": "laterality",
            "regex": r"\b(right|left|bilateral|unilateral)\b",
            "extractor": lambda m: {"laterality": m.group(1).lower().strip()},
        },
        # Acuity
        {
            "fact_type": "acuity",
            "regex": r"\b(acute|chronic|subacute|recurrent|exacerbation)\b",
            "extractor": lambda m: {"acuity": m.group(1).lower().strip()},
        },
        # Medical Decision Making
        {
            "fact_type": "medical_decision_making",
            "regex": r"(?:Medical Decision Making|MDM):\s*(Straightforward|Low|Moderate|High)",
            "extractor": lambda m: {"mdm_level": m.group(1).strip()},
        },
        {
            "fact_type": "medical_decision_making",
            "regex": r"(high complexity decision making|moderate complexity decision making|straightforward decision making)",
            "extractor": lambda m: {"mdm_level": m.group(1).strip()},
        },
        # Provider Signature
        {
            "fact_type": "patient_status",
            "regex": r"\b(established patient|new patient)\b",
            "extractor": lambda m: {"status": m.group(1).strip()},
        },
        {
            "fact_type": "provider_signature",
            "regex": r"(?:Electronically Signed By|Signed by):\s*([^\n\r]+)",
            "extractor": lambda m: {"provider": m.group(1).strip()},
        },
    ]

    async def extract(self, document_id: str, pages: List[OCRPage], domain: str) -> ExtractionResult:
        facts: List[ExtractedClinicalFact] = []
        warnings: List[str] = []
        missing_docs: List[str] = []

        has_signature = False
        has_date = False
        has_diagnosis = False

        for page in pages:
            text = page.text
            if not text:
                continue

            for p_def in self.PATTERNS:
                pattern = re.compile(p_def["regex"], re.IGNORECASE)
                for match in pattern.finditer(text):
                    line_start = text.rfind('\n', 0, match.start()) + 1
                    line_end = text.find('\n', match.end())
                    context = text[line_start:line_end if line_end >= 0 else len(text)].lower()
                    if p_def['fact_type'] in {'diagnosis', 'procedure'} and re.search(
                        r'\b(no|not|denies|denied|without|ruled out|rule out|possible|suspected|history of|planned|scheduled|consider)\b', context
                    ):
                        warnings.append("Negated, historical, or uncertain clinical statement requires manual review.")
                        continue
                    val = p_def["extractor"](match)
                    start, end = match.span()
                    quoted = text[start:end]

                    evidence = ExtractedEvidence(
                        document_id=document_id,
                        page_number=page.page_number,
                        start_offset=start,
                        end_offset=end,
                        quoted_text=quoted,
                        evidence_type=p_def["fact_type"],
                    )

                    fact = ExtractedClinicalFact(
                        fact_type=p_def["fact_type"],
                        value=val,
                        evidence=evidence,
                        confidence=0.98,
                    )
                    facts.append(fact)

                    if p_def["fact_type"] == "provider_signature":
                        has_signature = True
                    elif p_def["fact_type"] == "service_date":
                        has_date = True
                    elif p_def["fact_type"] == "diagnosis":
                        has_diagnosis = True

        if not has_signature:
            missing_docs.append("Provider electronic signature or authentication missing from record.")
        if not has_date:
            missing_docs.append("Encounter service date not clearly documented in note.")
        if not has_diagnosis:
            warnings.append("No explicit assessment or primary diagnosis statement detected.")

        return ExtractionResult(
            facts=facts,
            missing_documentation=missing_docs,
            warnings=warnings,
        )
