from typing import Dict, Any, List
from services.rules_engine.rule import Rule, RuleResultDto


class NCCIMutuallyExclusiveRule(Rule):
    """
    CMS National Correct Coding Initiative (NCCI) Procedure-to-Procedure (PTP) validation.
    """

    BUNDLED_PAIRS = {
        ("44970", "49320"): {
            "modifier_allowed": False,
            "message": "NCCI PTP Edit: Diagnostic laparoscopy (49320) is bundled into surgical laparoscopic appendectomy (44970) and cannot be unbundled.",
        },
        ("99284", "99214"): {
            "modifier_allowed": False,
            "message": "NCCI PTP Edit: Emergency Department E&M (99284) and Office Visit E&M (99214) cannot both be billed on the same date of service.",
        },
    }

    def __init__(self):
        super().__init__(
            rule_id="RULE-NCCI-PTP",
            description="CMS NCCI Policy Manual Procedure-to-Procedure (PTP) unbundling verification.",
            source="CMS Medicare NCCI Policy Manual Chapter 1 General Correct Coding Policies",
            version="2026.1",
            effective_date="2026-01-01",
        )

    def evaluate(self, candidate_code: str, code_system: str, facts: List[Dict[str, Any]], encounter_context: Dict[str, Any]) -> RuleResultDto:
        other_candidates = encounter_context.get("all_candidate_codes", [])

        for (code1, code2), info in self.BUNDLED_PAIRS.items():
            if candidate_code == code2 and code1 in other_candidates:
                return RuleResultDto(
                    rule_id=self.rule_id,
                    status="FAIL",
                    message=info["message"],
                    source_reference=self.source,
                )

        return RuleResultDto(
            rule_id=self.rule_id,
            status="PASS",
            message="No NCCI unbundling conflict detected.",
            source_reference=self.source,
        )
