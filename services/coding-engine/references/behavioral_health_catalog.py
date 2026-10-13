"""Development catalog for behavioral-health procedure codes.

Reuses the deterministic time bands from the rules layer (the dependency runs
coding -> rules). Adds paraphrased development labels tagged [MOCK].

CPT is a registered trademark of the American Medical Association;
proprietary AMA descriptors are not stored or redistributed here (same
convention as the mock CPT provider).

This catalog is NOT exposed as an activated profile. Behavioral health stays
unavailable in the UI until its end-to-end development workflow passes with a
licensed catalog.
"""
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
