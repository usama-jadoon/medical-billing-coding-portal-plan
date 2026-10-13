"""Loaded, bounded 2026 development catalog; no proprietary CPT descriptors."""
from datetime import date

CATALOG_VERSION = 'specialty-catalog-2026-v1'
BEHAVIORAL_HEALTH_CATALOG = [
    {'code': code, 'code_system': 'CPT', 'effective_start': '2026-01-01', 'effective_end': '2026-12-31',
     'code_version': 'CY2026'} for code in ('90832', '90834', '90837', '90833', '90836', '90838', '90791', '90792', '99213', '99214')
]
DME_CATALOG = [
    {'code': code, 'code_system': 'HCPCS', 'equipment_name': name,
     'effective_start': '2026-01-01', 'effective_end': '2026-12-31', 'code_version': 'CY2026',
     'local_cmn_required': cmn}
    for code, name, cmn in [('E0601', 'CPAP', False), ('E0260', 'semi-electric hospital bed with mattress', True)]
]


def active_entry(code, system, service_date):
    try:
        when = date.fromisoformat(service_date)
    except (TypeError, ValueError):
        return None
    return next((entry for entry in BEHAVIORAL_HEALTH_CATALOG + DME_CATALOG
                 if entry['code'] == code and entry['code_system'] == system
                 and date.fromisoformat(entry['effective_start']) <= when <= date.fromisoformat(entry['effective_end'])), None)
