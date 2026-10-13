"""Conservative documented-field extraction with one source pointer per fact."""
import re
from services.extraction.schemas import ExtractedClinicalFact, ExtractedEvidence


def extract_specialty(document_id, pages, domain):
    if domain not in {'behavioral_health', 'dme'}:
        return []
    boolean = lambda v: v.lower() in {'yes', 'true'}
    patterns = [
        ('service_kind', r'Service kind:\s*(PSYCHOTHERAPY|DIAGNOSTIC_EVALUATION)', str.upper),
        ('session_duration_minutes', r'Psychotherapy duration:\s*(\d+)\s*(?:minutes|mins)', int),
        ('is_telehealth', r'Telehealth:\s*(yes|no|true|false)', boolean),
        ('telehealth_modality', r'Telehealth modality:\s*(AUDIO_VIDEO|AUDIO_ONLY)', str.upper),
        ('patient_location', r'Telehealth patient location:\s*(HOME|OTHER)', str.upper),
        ('has_medical_em', r'Separate medical E/M:\s*(yes|no|true|false)', boolean),
        ('patient_present', r'Patient present:\s*(yes|no|true|false)', boolean),
        ('diagnostic_medical_services', r'Diagnostic medical services:\s*(yes|no|true|false)', boolean),
        ('em_mdm', r'Separate E/M MDM:\s*(LOW|MODERATE)', str.upper),
        ('established_patient', r'Establishment confirmed:\s*(yes|no|true|false)', boolean),
    ] if domain == 'behavioral_health' else [
        ('equipment_name', r'Equipment:\s*([^\r\n]+)', str.strip),
        ('order_type', r'Order type:\s*(PURCHASE|RENTAL|UNSPECIFIED)', str.upper),
        ('cmn_on_file', r'Signed CMN on file:\s*(yes|no|true|false)', boolean),
        ('ordering_physician_npi', r'Ordering physician NPI:\s*(\d{10})', str),
        ('sleep_study_criteria_met', r'Sleep study criteria met:\s*(yes|no|true|false)', boolean),
    ]
    facts = []
    def add(page, match, field, value):
        facts.append(ExtractedClinicalFact(fact_type=domain, value={field: value}, evidence=ExtractedEvidence(
            document_id=document_id, page_number=page.page_number, start_offset=match.start(), end_offset=match.end(),
            quoted_text=page.text[match.start():match.end()], evidence_type=domain)))
    for page in pages:
        for field, pattern, convert in patterns:
            # Only complete standalone documented fields, never planned/negated prose.
            for match in re.finditer(r'(?im)^[ \t]*' + pattern + r'[ \t]*\r?$', page.text):
                add(page, match, field, convert(match.group(1)))
        if domain == 'behavioral_health':
            for match in re.finditer(r'(?im)^Psychotherapy start:\s*(\d{2}):(\d{2});\s*stop:\s*(\d{2}):(\d{2})[ \t]*\r?$', page.text):
                h1, m1, h2, m2 = map(int, match.groups())
                if max(h1, h2) < 24 and max(m1, m2) < 60 and h2 * 60 + m2 >= h1 * 60 + m1:
                    add(page, match, 'session_duration_minutes', h2 * 60 + m2 - h1 * 60 - m1)
    return facts
