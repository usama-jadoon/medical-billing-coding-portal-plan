from services.extraction.schemas import resolve_specialty_facts
from services.rules_engine.rulesets.behavioral_health_rules import evaluate_behavioral_health
from services.rules_engine.rulesets.dme_rules import evaluate_dme
from pydantic import ValidationError


def assess_specialty(domain, facts, service_date, place_of_service):
    if domain not in {'behavioral_health', 'dme'}:
        return None
    try:
        fact, evidence, conflicts = resolve_specialty_facts(facts, domain)
    except ValidationError:
        return {'status': 'Unavailable', 'errors': ['Specialty facts failed strict schema validation.'], 'codes': [], 'modifiers': [], 'evidence': []}
    assessment = (evaluate_behavioral_health if domain == 'behavioral_health' else evaluate_dme)(fact, service_date, place_of_service)
    if conflicts:
        assessment.update(status='Unavailable', codes=[], modifiers=[], errors=assessment['errors'] + ['Conflicting documented fields: ' + ', '.join(conflicts)])
    assessment['evidence'] = list({ev.get('id', str(ev)): ev for refs in evidence.values() for ev in refs}.values())
    return assessment


def specialty_candidates(domain, facts, service_date, place_of_service):
    assessment = assess_specialty(domain, facts, service_date, place_of_service)
    if not assessment:
        return []
    return [{'code': code, 'code_system': 'CPT' if domain == 'behavioral_health' else 'HCPCS', 'code_version': 'CY2026',
             'status': 'candidate', 'human_review_required': True,
             'rationale': 'Bounded development matcher; explicit code and modifier acceptance required.',
             'supporting_evidence': assessment['evidence'], 'rule_results': [],
             'proposed_modifiers': assessment['modifiers'], 'place_of_service': assessment['place_of_service']}
            for code in assessment['codes']]
