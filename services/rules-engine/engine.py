from typing import List, Dict, Any
from services.rules_engine.rule import Rule, RuleResultDto
from services.rules_engine.rulesets.emergency import EDPlaceOfServiceRule, EDMedicalDecisionMakingRule
from services.rules_engine.rulesets.professional import OfficePlaceOfServiceRule
from services.rules_engine.rulesets.ncci import NCCIMutuallyExclusiveRule
from services.rules_engine.rulesets.modifiers import Modifier25RequirementRule


class RuleEngine:
    def __init__(self):
        self.rules: List[Rule] = [
            EDPlaceOfServiceRule(),
            EDMedicalDecisionMakingRule(),
            OfficePlaceOfServiceRule(),
            NCCIMutuallyExclusiveRule(),
            Modifier25RequirementRule(),
        ]

    def validate(
        self,
        candidate_code: str,
        code_system: str,
        facts: List[Dict[str, Any]],
        encounter_context: Dict[str, Any],
    ) -> List[RuleResultDto]:
        results: List[RuleResultDto] = []
        for rule in self.rules:
            res = rule.evaluate(candidate_code, code_system, facts, encounter_context)
            if res.status != "NOT_APPLICABLE":
                results.append(res)
        return results
