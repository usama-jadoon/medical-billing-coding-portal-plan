from typing import Dict, Any, List
from services.rules_engine.rule import Rule, RuleResultDto


class OfficePlaceOfServiceRule(Rule):
    def __init__(self):
        super().__init__(
            rule_id="RULE-OFFICE-POS-11",
            description="Office visit E/M codes require Place of Service 11 (Office).",
            source="CMS Place of Service Code Set Guidelines",
            version="2026.1",
            effective_date="2026-01-01",
        )

    def evaluate(self, candidate_code: str, code_system: str, facts: List[Dict[str, Any]], encounter_context: Dict[str, Any]) -> RuleResultDto:
        if code_system != "CPT" or not candidate_code.startswith("9921"):
            return RuleResultDto(
                rule_id=self.rule_id,
                status="NOT_APPLICABLE",
                message="Rule only applies to Office Visit CPT codes.",
                source_reference=self.source,
            )

        pos = encounter_context.get("place_of_service", "")
        if pos not in ("11", "Office", "Outpatient Clinic"):
            return RuleResultDto(
                rule_id=self.rule_id,
                status="WARNING",
                message="Encounter place of service is not documented as Office (POS 11).",
                source_reference=self.source,
            )

        return RuleResultDto(
            rule_id=self.rule_id,
            status="PASS",
            message="Place of Service 11 verified for Office visit.",
            source_reference=self.source,
        )
