from services.rules_engine.rule import Rule, RuleResultDto
from services.rules_engine.engine import RuleEngine
from services.rules_engine.validator import (
    DeterministicValidationPipeline,
    ValidationFindingDto,
    ValidationPipelineResult,
    get_validation_pipeline,
)

_default_rule_engine = None


def get_rule_engine() -> RuleEngine:
    global _default_rule_engine
    if _default_rule_engine is None:
        _default_rule_engine = RuleEngine()
    return _default_rule_engine
