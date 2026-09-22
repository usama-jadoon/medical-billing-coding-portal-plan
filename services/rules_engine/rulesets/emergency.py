from typing import Dict, Any, List
from services.rules_engine.rule import Rule, RuleResultDto


class EDPlaceOfServiceRule(Rule):
    def __init__(self):
        super().__init__(
            rule_id="RULE-ED-POS-23",
            description="Emergency Department E/M codes require Place of Service 23 (or ED facility documentation).",
            source="CMS Place of Service Code Set Guidelines",
            version="2026.1",
            effective_date="2026-01-01",
        )

    def evaluate(self, candidate_code: str, code_system: str, facts: List[Dict[str, Any]], encounter_context: Dict[str, Any]) -> RuleResultDto:
        if code_system != "CPT" or not candidate_code.startswith("9928"):
            return RuleResultDto(
                rule_id=self.rule_id,
                status="NOT_APPLICABLE",
                message="Rule only applies to Emergency Department E&M CPT codes.",
                source_reference=self.source,
            )

        pos = encounter_context.get("place_of_service", "")
        # POS 23 is Emergency Room - Hospital
        has_ed_pos = pos in ("23", "Emergency Department", "ED")
        if not has_ed_pos:
            # Check facts for ED place of service
            has_ed_fact = any(
                f.get("fact_type") == "place_of_service" and "emergency" in str(f.get("value", {})).lower()
                for f in facts
            )
            if not has_ed_fact:
                return RuleResultDto(
                    rule_id=self.rule_id,
                    status="WARNING",
                    message="Encounter place of service is not documented as Emergency Department (POS 23).",
                    source_reference=self.source,
                )

        return RuleResultDto(
            rule_id=self.rule_id,
            status="PASS",
            message="Place of Service 23 verified for Emergency Department visit.",
            source_reference=self.source,
        )


class EDMedicalDecisionMakingRule(Rule):
    def __init__(self):
        super().__init__(
            rule_id="RULE-ED-MDM-LEVEL",
            description="CPT 99284/99285 requires documented moderate or high complexity Medical Decision Making.",
            source="AMA CPT E/M Documentation Guidelines & CMS Manual",
            version="2026.1",
            effective_date="2026-01-01",
        )

    def evaluate(self, candidate_code: str, code_system: str, facts: List[Dict[str, Any]], encounter_context: Dict[str, Any]) -> RuleResultDto:
        if candidate_code not in ("99284", "99285"):
            return RuleResultDto(
                rule_id=self.rule_id,
                status="NOT_APPLICABLE",
                message="Rule applies to high acuity ED E&M codes 99284 and 99285.",
                source_reference=self.source,
            )

        mdm_facts = [
            f.get("value", {}).get("mdm_level", "").lower()
            for f in facts
            if f.get("fact_type") == "medical_decision_making"
        ]

        if candidate_code == "99285":
            if any("high" in m for m in mdm_facts):
                return RuleResultDto(
                    rule_id=self.rule_id,
                    status="PASS",
                    message="High complexity medical decision making documented for 99285.",
                    source_reference=self.source,
                )
            return RuleResultDto(
                rule_id=self.rule_id,
                status="WARNING",
                message="CPT 99285 requires high MDM complexity; documentation may only support moderate or straightforward MDM.",
                source_reference=self.source,
            )
        elif candidate_code == "99284":
            if any(m in ("moderate", "high", "moderate complexity decision making") for m in mdm_facts):
                return RuleResultDto(
                    rule_id=self.rule_id,
                    status="PASS",
                    message="Moderate to high medical decision making documented for 99284.",
                    source_reference=self.source,
                )
            return RuleResultDto(
                rule_id=self.rule_id,
                status="WARNING",
                message="Documented MDM does not explicitly state moderate complexity for 99284.",
                source_reference=self.source,
            )

        return RuleResultDto(
            rule_id=self.rule_id,
            status="PASS",
            message="MDM validation satisfied.",
            source_reference=self.source,
        )
