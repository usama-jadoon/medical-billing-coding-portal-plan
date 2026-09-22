from typing import Dict, Any, List
from services.rules_engine.rule import Rule, RuleResultDto


class Modifier25RequirementRule(Rule):
    """
    Validates Modifier -25 when a separate significant E&M is provided on same day as a minor surgical procedure.
    """

    def __init__(self):
        super().__init__(
            rule_id="RULE-MODIFIER-25",
            description="Significant, separately identifiable E/M service by same physician on same day of procedure.",
            source="CMS Claims Processing Manual Chapter 12 Section 30.6.6",
            version="2026.1",
            effective_date="2026-01-01",
        )

    def evaluate(self, candidate_code: str, code_system: str, facts: List[Dict[str, Any]], encounter_context: Dict[str, Any]) -> RuleResultDto:
        is_em = code_system == "CPT" and (candidate_code.startswith("9928") or candidate_code.startswith("9921"))
        other_candidates = encounter_context.get("all_candidate_codes", [])
        has_procedure = any(c.startswith("449") or c.startswith("1") for c in other_candidates)

        if is_em and has_procedure:
            return RuleResultDto(
                rule_id=self.rule_id,
                status="WARNING",
                message="Procedure billed on same date of service: verify if Modifier -25 is required for distinct E&M.",
                source_reference=self.source,
            )

        return RuleResultDto(
            rule_id=self.rule_id,
            status="PASS",
            message="Modifier 25 check satisfied.",
            source_reference=self.source,
        )
