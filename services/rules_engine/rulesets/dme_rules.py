"""Bounded DME (durable medical equipment) ruleset (development profile, not exposed in UI).

Deterministic DME MAC modifier completion (NU/RR/KX) and Certificate of
Medical Necessity gating for high-value equipment.

Invariant: an unverified CMN stays "Unavailable" and blocks the candidate;
it is never assumed on file.
"""
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
