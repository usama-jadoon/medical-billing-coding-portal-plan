from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel


class RuleResultDto(BaseModel):
    rule_id: str
    status: str  # "PASS", "WARNING", "FAIL", "NOT_APPLICABLE"
    message: str
    source_reference: str


class Rule(ABC):
    def __init__(
        self,
        rule_id: str,
        description: str,
        source: str,
        version: str = "2026.1",
        effective_date: str = "2026-01-01",
    ):
        self.rule_id = rule_id
        self.description = description
        self.source = source
        self.version = version
        self.effective_date = effective_date

    @abstractmethod
    def evaluate(self, candidate_code: str, code_system: str, facts: List[Dict[str, Any]], encounter_context: Dict[str, Any]) -> RuleResultDto:
        pass
