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
    for code, name, cmn in [('E0601', 'CPAP', True), ('E0260', 'semi-electric hospital bed with mattress', True)]
]


def active_entry(code, system, service_date):
    try:
        when = date.fromisoformat(service_date)
    except (TypeError, ValueError):
        return None
    return next((entry for entry in BEHAVIORAL_HEALTH_CATALOG + DME_CATALOG
                 if entry['code'] == code and entry['code_system'] == system
                 and date.fromisoformat(entry['effective_start']) <= when <= date.fromisoformat(entry['effective_end'])), None)

# Preserve upstream catalog reference helpers without reversing dependency flow.
from services.rules_engine.rulesets.behavioral_health_rules import (
    PSYCHOTHERAPY_TIME_BANDS,
    PSYCHOTHERAPY_ADD_ONS,
    DIAGNOSTIC_EVAL_CODES,
    MIN_BILLABLE_MINUTES,
    TELEHEALTH_MODIFIER,
    TELEHEALTH_POS,
    select_psychotherapy_code,
    is_psychotherapy_code,
    is_add_on_code,
    band_for_code,
)

# Paraphrased development labels only; not AMA descriptors.
BAND_LABELS = {
    "90832": "[MOCK] Psychotherapy session, ~30 minute band",
    "90834": "[MOCK] Psychotherapy session, ~45 minute band",
    "90837": "[MOCK] Psychotherapy session, ~60 minute band",
    "90833": "[MOCK] Add-on psychotherapy with medical E/M, ~30 minute band",
    "90836": "[MOCK] Add-on psychotherapy with medical E/M, ~45 minute band",
    "90838": "[MOCK] Add-on psychotherapy with medical E/M, ~60 minute band",
    "90791": "[MOCK] Psychiatric diagnostic evaluation",
    "90792": "[MOCK] Psychiatric diagnostic evaluation with medical services",
}

__all__ = [
    "PSYCHOTHERAPY_TIME_BANDS",
    "PSYCHOTHERAPY_ADD_ONS",
    "DIAGNOSTIC_EVAL_CODES",
    "MIN_BILLABLE_MINUTES",
    "TELEHEALTH_MODIFIER",
    "TELEHEALTH_POS",
    "BAND_LABELS",
    "select_psychotherapy_code",
    "is_psychotherapy_code",
    "is_add_on_code",
    "band_for_code",
]

__all__ += ['CATALOG_VERSION', 'BEHAVIORAL_HEALTH_CATALOG', 'DME_CATALOG', 'active_entry']
