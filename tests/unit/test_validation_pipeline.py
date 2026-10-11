import pytest
from services.rules_engine.validator import (
    DeterministicValidationPipeline,
    get_validation_pipeline,
)


def test_validation_pipeline_catalog_and_date_blockers():
    pipeline = get_validation_pipeline()

    # Invalid code system and missing date
    result = pipeline.validate_case(
        domain="emergency_department",
        service_date="invalid-date",
        place_of_service="23",
        facts=[],
        candidates=[
            {"code": "UNKNOWN99", "code_system": "FAKE_SYSTEM", "supporting_evidence": []}
        ],
    )

    assert result.has_blockers is True
    assert result.eligible_for_approval is False

    stages = {f.stage for f in result.findings}
    assert "1_catalog" in stages
    assert "2_effective_date" in stages
    assert "3_evidence" in stages
    assert "8_approval_gate" in stages


def test_validation_pipeline_clean_case_eligible():
    pipeline = get_validation_pipeline()

    facts = [
        {"fact_type": "place_of_service", "value": {"pos": "23"}},
        {"fact_type": "medical_decision_making", "value": {"mdm_level": "moderate"}},
        {"fact_type": "diagnosis", "value": {"condition": "Chest pain"}},
    ]

    candidates = [
        {
            "code": "99284",
            "code_system": "CPT",
            "supporting_evidence": [{"id": "ev-1", "page_number": 1}],
        },
        {
            "code": "R07.9",
            "code_system": "ICD-10-CM",
            "supporting_evidence": [{"id": "ev-2", "page_number": 1}],
        },
    ]

    result = pipeline.validate_case(
        domain="emergency_department",
        service_date="2026-09-20",
        place_of_service="23",
        facts=facts,
        candidates=candidates,
    )

    assert result.has_blockers is False
    assert result.eligible_for_approval is True
    assert result.blocker_count == 0


def test_validation_pipeline_mutual_exclusion_and_modifiers():
    pipeline = get_validation_pipeline()

    facts = [
        {"fact_type": "place_of_service", "value": {"pos": "23"}},
        {"fact_type": "medical_decision_making", "value": {"mdm_level": "high"}},
        {"fact_type": "procedure", "value": {"procedure_name": "Laceration repair"}},
    ]

    # Two ED codes (99284 and 99285) which is mutually exclusive, plus procedure 12001 triggering modifier review
    candidates = [
        {"code": "99284", "code_system": "CPT", "supporting_evidence": [{"id": "ev-1"}]},
        {"code": "99285", "code_system": "CPT", "supporting_evidence": [{"id": "ev-2"}]},
        {"code": "12001", "code_system": "CPT", "supporting_evidence": [{"id": "ev-3"}]},
    ]

    result = pipeline.validate_case(
        domain="emergency_department",
        service_date="2026-09-20",
        place_of_service="23",
        facts=facts,
        candidates=candidates,
    )

    stages = {f.stage for f in result.findings}
    assert "5_relationships" in stages
    assert "6_modifiers" in stages
    assert "7_ncci" in stages
    assert result.has_blockers is True
    assert result.eligible_for_approval is False
