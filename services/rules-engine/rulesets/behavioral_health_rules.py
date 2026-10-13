"""Bounded psychotherapy rules. Modifiers are proposals pending reviewer acceptance."""
from services.extraction.schemas import BehavioralHealthEncounterFact

SOURCE = 'https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleid=57520'


def evaluate_behavioral_health(fact: BehavioralHealthEncounterFact, service_date: str, place_of_service: str = '11'):
    from services.coding_engine.references.behavioral_health_catalog import active_entry
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


# Existing RuleEngine interfaces retained for development compatibility.
from typing import Dict, Any, List, Optional

from services.rules_engine.rule import Rule, RuleResultDto

CMS_BH_SOURCE = "CMS Medicare Claims Processing Manual, Chapter 12 (timed psychotherapy thresholds)"

# CMS time thresholds for timed psychotherapy codes (minutes, inclusive).
PSYCHOTHERAPY_TIME_BANDS = [
    {"code": "90832", "min_minutes": 16, "max_minutes": 37},
    {"code": "90834", "min_minutes": 38, "max_minutes": 52},
    {"code": "90837", "min_minutes": 53, "max_minutes": None},
]

# Add-on psychotherapy codes, each extending the standalone code in its band.
# An add-on can never be the primary/standalone code on a claim.
PSYCHOTHERAPY_ADD_ONS = {
    "90833": "90832",
    "90836": "90834",
    "90838": "90837",
}

# Psychiatric diagnostic evaluation codes (not time-banded here).
DIAGNOSTIC_EVAL_CODES = {"90791", "90792"}

# Below this floor a session cannot be billed as psychotherapy at all.
MIN_BILLABLE_MINUTES = 16

# Deterministic telehealth claim completion for BH services.
TELEHEALTH_MODIFIER = "95"
TELEHEALTH_POS = "02"  # Telehealth other than patient's home; 10 when home

BH_CODES = (
    {band["code"] for band in PSYCHOTHERAPY_TIME_BANDS}
    | set(PSYCHOTHERAPY_ADD_ONS)
    | set(DIAGNOSTIC_EVAL_CODES)
)


def select_psychotherapy_code(duration_minutes: Optional[int]) -> Optional[str]:
    """Return the psychotherapy code matching a documented duration.

    Returns None when the duration is unavailable (None) or below the
    16-minute billable floor. Never defaults to a code.
    """
    if duration_minutes is None or duration_minutes < MIN_BILLABLE_MINUTES:
        return None
    for band in PSYCHOTHERAPY_TIME_BANDS:
        if duration_minutes >= band["min_minutes"] and (
            band["max_minutes"] is None or duration_minutes <= band["max_minutes"]
        ):
            return band["code"]
    return None


def is_psychotherapy_code(code: str) -> bool:
    return any(band["code"] == code for band in PSYCHOTHERAPY_TIME_BANDS)


def is_add_on_code(code: str) -> bool:
    return code in PSYCHOTHERAPY_ADD_ONS


def band_for_code(code: str):
    for band in PSYCHOTHERAPY_TIME_BANDS:
        if band["code"] == code:
            return band
    return None


def telehealth_claim_attributes(patient_home: bool = False) -> Dict[str, str]:
    """Deterministic claim completion for telehealth BH services."""
    return {"modifier": TELEHEALTH_MODIFIER, "pos": "10" if patient_home else TELEHEALTH_POS}


def _duration_minutes(facts: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[int]:
    if context.get("bh_duration_minutes") is not None:
        return context["bh_duration_minutes"]
    for fact in facts:
        if fact.get("fact_type") == "behavioral_health":
            value = fact.get("value") or {}
            if value.get("session_duration_minutes") is not None:
                return value["session_duration_minutes"]
    return None


class BHPsychotherapyTimeRule(Rule):
    """CMS time thresholds for 90832 / 90834 / 90837."""

    def __init__(self):
        super().__init__(
            rule_id="RULE-BH-TIME",
            description="Psychotherapy code must match the documented session duration; "
                        "sessions under 16 minutes cannot be billed as psychotherapy.",
            source=CMS_BH_SOURCE,
        )

    def evaluate(self, candidate_code: str, code_system: str, facts: List[Dict[str, Any]],
                 encounter_context: Dict[str, Any]) -> RuleResultDto:
        if code_system != "CPT" or not is_psychotherapy_code(candidate_code):
            return RuleResultDto(rule_id=self.rule_id, status="NOT_APPLICABLE",
                                 message="", source_reference=self.source)
        duration = _duration_minutes(facts, encounter_context)
        if duration is None:
            return RuleResultDto(rule_id=self.rule_id, status="FAIL",
                message="Session duration is unavailable. No psychotherapy candidate can be "
                        "generated until start/stop times or a stated duration are documented.",
                source_reference=self.source)
        if duration < MIN_BILLABLE_MINUTES:
            return RuleResultDto(rule_id=self.rule_id, status="FAIL",
                message="Session under 16 mins cannot be billed as psychotherapy.",
                source_reference=self.source)
        band = band_for_code(candidate_code)
        in_band = duration >= band["min_minutes"] and (
            band["max_minutes"] is None or duration <= band["max_minutes"])
        if not in_band:
            return RuleResultDto(rule_id=self.rule_id, status="FAIL",
                message=f"Documented duration {duration} minutes does not fall in the "
                        f"{band['min_minutes']}-{band['max_minutes'] or 'plus'} minute band for {candidate_code}.",
                source_reference=self.source)
        return RuleResultDto(rule_id=self.rule_id, status="PASS",
            message=f"Duration {duration} minutes matches the {candidate_code} time band.",
            source_reference=self.source)


class BHAddOnPrerequisiteRule(Rule):
    """Add-on psychotherapy codes require a same-day medical E/M and can never
    be the primary code."""

    def __init__(self):
        super().__init__(
            rule_id="RULE-BH-ADDON",
            description="Add-on psychotherapy (+90833/+90836/+90838) requires a same-day "
                        "medical E/M and cannot be billed as a primary code.",
            source=CMS_BH_SOURCE,
        )

    def evaluate(self, candidate_code: str, code_system: str, facts: List[Dict[str, Any]],
                 encounter_context: Dict[str, Any]) -> RuleResultDto:
        if code_system != "CPT" or not is_add_on_code(candidate_code):
            return RuleResultDto(rule_id=self.rule_id, status="NOT_APPLICABLE",
                                 message="", source_reference=self.source)
        if encounter_context.get("bh_addon_is_primary"):
            return RuleResultDto(rule_id=self.rule_id, status="FAIL",
                message=f"{candidate_code} is an add-on code and cannot be billed as a primary code.",
                source_reference=self.source)
        if not encounter_context.get("bh_has_medical_em"):
            return RuleResultDto(rule_id=self.rule_id, status="FAIL",
                message=f"Add-on {candidate_code} requires a same-day medical E/M service "
                        "(has_medical_em). No qualifying E/M was documented.",
                source_reference=self.source)
        return RuleResultDto(rule_id=self.rule_id, status="PASS",
            message=f"Add-on {candidate_code} has a documented same-day medical E/M.",
            source_reference=self.source)


class BHTelehealthCompletionRule(Rule):
    """Deterministic telehealth claim completion for BH services."""

    def __init__(self):
        super().__init__(
            rule_id="RULE-BH-TELEHEALTH",
            description="Telehealth behavioral-health services carry modifier -95 and POS 02/10.",
            source="CMS telehealth billing guidance",
        )

    def evaluate(self, candidate_code: str, code_system: str, facts: List[Dict[str, Any]],
                 encounter_context: Dict[str, Any]) -> RuleResultDto:
        if code_system != "CPT" or candidate_code not in BH_CODES:
            return RuleResultDto(rule_id=self.rule_id, status="NOT_APPLICABLE",
                                 message="", source_reference=self.source)
        if not encounter_context.get("bh_is_telehealth"):
            return RuleResultDto(rule_id=self.rule_id, status="NOT_APPLICABLE",
                                 message="", source_reference=self.source)
        attrs = telehealth_claim_attributes(encounter_context.get("bh_patient_home", False))
        return RuleResultDto(rule_id=self.rule_id, status="PASS",
            message=f"Telehealth service: modifier -{attrs['modifier']} and POS {attrs['pos']} "
                    "apply to this claim line.",
            source_reference=self.source)
