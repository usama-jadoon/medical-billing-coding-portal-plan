"""Bounded psychotherapy rules. Modifiers are proposals pending reviewer acceptance."""
from services.extraction.schemas import BehavioralHealthEncounterFact
from services.coding_engine.references.behavioral_health_catalog import active_entry

SOURCE = 'https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleid=57520'


def evaluate_behavioral_health(fact: BehavioralHealthEncounterFact, service_date: str, place_of_service: str = '11'):
    errors, codes, modifiers = [], [], []
    pos = place_of_service
    if fact.patient_present is not True:
        errors.append('Patient presence is unavailable or not confirmed.')
    if fact.is_telehealth is None:
        errors.append('Telehealth status is unavailable.')
    elif fact.is_telehealth:
        if fact.telehealth_modality != 'AUDIO_VIDEO':
            errors.append('Audio/video telehealth modality is unavailable; audio-only policy is not activated.')
        if fact.patient_location not in {'HOME', 'OTHER'}:
            errors.append('Telehealth patient location is unavailable; POS 02/10 cannot be inferred.')
        else:
            pos = '10' if fact.patient_location == 'HOME' else '02'
            if place_of_service != pos:
                errors.append('Confirmed place of service conflicts with documented telehealth location.')
        modifiers = ['95']
    elif fact.telehealth_modality is not None or fact.patient_location is not None:
        errors.append('Telehealth details conflict with an in-person encounter.')
    elif place_of_service != '11':
        errors.append('In-person behavioral health requires confirmed POS 11 in this profile.')
    if fact.service_kind == 'DIAGNOSTIC_EVALUATION':
        if fact.diagnostic_medical_services is None:
            errors.append('Diagnostic medical services status is unavailable.')
        else:
            codes = ['90792' if fact.diagnostic_medical_services else '90791']
    elif fact.service_kind == 'PSYCHOTHERAPY':
        minutes = fact.session_duration_minutes
        if minutes is None:
            errors.append('Psychotherapy duration unavailable: documented minutes or start/stop times required.')
        elif minutes < 16:
            errors.append('Session under 16 mins cannot be billed as psychotherapy.')
        elif fact.has_medical_em is None:
            errors.append('Separate medical E/M status is unavailable.')
        else:
            bucket = 0 if minutes <= 37 else 1 if minutes <= 52 else 2
            if fact.has_medical_em:
                if fact.established_patient is not True or fact.em_mdm not in {'LOW', 'MODERATE'}:
                    errors.append('Separate E/M code unavailable: established-patient status and documented E/M MDM required.')
                else:
                    codes = ['99213' if fact.em_mdm == 'LOW' else '99214', ('90833', '90836', '90838')[bucket]]
            else:
                codes = [('90832', '90834', '90837')[bucket]]
    else:
        errors.append('Behavioral health service kind is unavailable.')
    if any(not active_entry(code, 'CPT', service_date) for code in codes):
        errors.append('Dated behavioral health catalog unavailable for this service date.')
    return {'status': 'Unavailable' if errors else 'Available', 'errors': errors,
            'codes': [] if errors else codes, 'modifiers': [] if errors else modifiers, 'place_of_service': pos}


def validate_behavioral_selection(codes):
    if set(codes) & {'90833', '90836', '90838'} and not set(codes) & {'99213', '99214'}:
        return ['Psychotherapy add-on cannot be billed as a primary code; select its separate E/M prerequisite.']
    return []
