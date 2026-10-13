"""Bounded equipment policy; CMN gate is requested local policy, not current Medicare law."""
from services.extraction.schemas import DMEEncounterFact


def evaluate_dme(fact: DMEEncounterFact, service_date: str, place_of_service: str = '12'):
    from services.coding_engine.references.behavioral_health_catalog import DME_CATALOG, active_entry
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


# Existing RuleEngine interfaces retained for development compatibility.
from typing import Dict, Any, List

from services.rules_engine.rule import Rule, RuleResultDto

DME_MAC_SOURCE = "CMS DME MAC jurisdiction guidance (NU/RR/KX modifiers)"

# High-value DME families that require a signed CMN before claim generation.
# Prefixes cover: hospital beds (E025x-E037x), CPAP/RAD (E0601, E0470/E0471),
# standard and power wheelchairs (K0001-K0898).
HIGH_VALUE_DME_PREFIXES = (
    "E02", "E03", "E0601", "E0470", "E0471",
    "K00", "K01", "K02", "K03", "K04", "K05", "K06", "K07", "K08",
)


def is_dme_code(code: str, code_system: str) -> bool:
    return code_system == "HCPCS" and (code.startswith("E") or code.startswith("K"))


def is_high_value_dme(code: str) -> bool:
    return any(code.startswith(prefix) for prefix in HIGH_VALUE_DME_PREFIXES)


def dme_mac_modifiers(code: str, order_type: str, sleep_study_criteria_met: bool) -> List[str]:
    """Deterministic DME MAC modifiers. Never invents an order type: an
    UNSPECIFIED order yields no NU/RR."""
    modifiers: List[str] = []
    if order_type == "PURCHASE":
        modifiers.append("NU")
    elif order_type == "RENTAL":
        modifiers.append("RR")
    if code == "E0601" and sleep_study_criteria_met:
        modifiers.append("KX")
    return modifiers


class DMEMACModifierRule(Rule):
    """NU for purchase, RR for rental, KX for CPAP with met sleep-study criteria."""

    def __init__(self):
        super().__init__(
            rule_id="RULE-DME-MAC",
            description="DME claim lines carry NU (purchase) or RR (rental); CPAP with "
                        "qualifying sleep study carries KX.",
            source=DME_MAC_SOURCE,
        )

    def evaluate(self, candidate_code: str, code_system: str, facts: List[Dict[str, Any]],
                 encounter_context: Dict[str, Any]) -> RuleResultDto:
        if not is_dme_code(candidate_code, code_system):
            return RuleResultDto(rule_id=self.rule_id, status="NOT_APPLICABLE",
                                 message="", source_reference=self.source)
        order_type = encounter_context.get("dme_order_type", "UNSPECIFIED")
        sleep_ok = bool(encounter_context.get("dme_sleep_study_criteria_met"))
        modifiers = dme_mac_modifiers(candidate_code, order_type, sleep_ok)
        if order_type == "UNSPECIFIED":
            return RuleResultDto(rule_id=self.rule_id, status="WARNING",
                message="Order type is unavailable (not purchase or rental). NU/RR cannot be "
                        "determined; the reviewer must confirm purchase vs rental before claim entry.",
                source_reference=self.source)
        detail = f"DME MAC modifiers for this line: {'-'.join(modifiers) if modifiers else 'none'}."
        if candidate_code == "E0601" and not sleep_ok:
            return RuleResultDto(rule_id=self.rule_id, status="WARNING",
                message=f"{detail} Sleep-study criteria are not documented as met; KX requires "
                        "a qualifying sleep study.",
                source_reference=self.source)
        return RuleResultDto(rule_id=self.rule_id, status="PASS",
            message=detail, source_reference=self.source)


class DMECMNRule(Rule):
    """High-value DME requires a signed CMN on file before claim generation."""

    def __init__(self):
        super().__init__(
            rule_id="RULE-DME-CMN",
            description="High-value DME (beds, CPAP/RAD, wheelchairs) requires a signed "
                        "Certificate of Medical Necessity on file.",
            source=DME_MAC_SOURCE,
        )

    def evaluate(self, candidate_code: str, code_system: str, facts: List[Dict[str, Any]],
                 encounter_context: Dict[str, Any]) -> RuleResultDto:
        if not is_dme_code(candidate_code, code_system) or not is_high_value_dme(candidate_code):
            return RuleResultDto(rule_id=self.rule_id, status="NOT_APPLICABLE",
                                 message="", source_reference=self.source)
        if not encounter_context.get("dme_cmn_on_file"):
            return RuleResultDto(rule_id=self.rule_id, status="FAIL",
                message="CMN required before claim generation.",
                source_reference=self.source)
        return RuleResultDto(rule_id=self.rule_id, status="PASS",
            message="Signed CMN is on file for this high-value DME item.",
            source_reference=self.source)
