"""Bounded equipment policy; CMN gate is requested local policy, not current Medicare law."""
from services.extraction.schemas import DMEEncounterFact
from services.coding_engine.references.behavioral_health_catalog import DME_CATALOG, active_entry


def evaluate_dme(fact: DMEEncounterFact, service_date: str, place_of_service: str = '12'):
    errors = []
    entry = next((e for e in DME_CATALOG if e['equipment_name'].casefold() == (fact.equipment_name or '').casefold()), None)
    if not entry:
        errors.append('Equipment code unavailable: exact supported equipment specification required.')
    elif not active_entry(entry['code'], 'HCPCS', service_date):
        errors.append('Dated DME catalog unavailable for this service date.')
    if fact.order_type == 'UNSPECIFIED':
        errors.append('Purchase/rental status unavailable.')
    high_value = bool(entry and entry['local_cmn_required']) or 'hospital bed' in (fact.equipment_name or '').casefold()
    if high_value and fact.cmn_on_file is not True:
        errors.append('CMN required before claim generation.')
    if entry and entry['code'] == 'E0601' and fact.sleep_study_criteria_met is not True:
        errors.append('CPAP sleep-study criteria unavailable or not verified.')
    if place_of_service != '12':
        errors.append('DME home-use setting must be confirmed as POS 12 in this profile.')
    modifiers = ['NU' if fact.order_type == 'PURCHASE' else 'RR']
    if entry and entry['code'] == 'E0601':
        modifiers.append('KX')
    return {'status': 'Unavailable' if errors else 'Available', 'errors': errors,
            'codes': [] if errors else [entry['code']], 'modifiers': [] if errors else modifiers,
            'place_of_service': place_of_service,
            'warnings': ['Local bounded policy only: CMN and sleep-study flags do not establish complete Medicare/payer coverage.']}
