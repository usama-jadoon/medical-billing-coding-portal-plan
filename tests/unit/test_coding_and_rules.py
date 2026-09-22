import pytest
from services.coding_engine.providers.base import CodeSetVersionProvider
from services.coding_engine.providers.icd10 import MockICD10CodeProvider
from services.coding_engine.providers.cpt import MockProcedureCodeProvider
from services.coding_engine.providers.dental_cdt import MockDentalCDTProvider
from services.rules_engine.engine import RuleEngine


@pytest.mark.asyncio
async def test_code_set_version_resolution():
    # Service date in FY2026 (Oct 1, 2025 - Sep 30, 2026)
    v1 = CodeSetVersionProvider.resolve_version("ICD-10-CM", "2026-05-15")
    assert v1 == "FY2026"

    # Service date in FY2027 (starts Oct 1, 2026)
    v2 = CodeSetVersionProvider.resolve_version("ICD-10-CM", "2026-10-05")
    assert v2 == "FY2027"

    # CPT runs calendar year
    v3 = CodeSetVersionProvider.resolve_version("CPT", "2026-10-05")
    assert v3 == "CY2026"


@pytest.mark.asyncio
async def test_coding_providers_return_mock_tagged_records():
    dx_provider = MockICD10CodeProvider()
    px_provider = MockProcedureCodeProvider()
    dental_provider = MockDentalCDTProvider()

    dx_results = await dx_provider.search("appendicitis", "2026-09-22")
    assert len(dx_results) > 0
    assert dx_results[0].code == "K35.80"
    assert dx_results[0].is_mock is True
    assert "[MOCK]" in dx_results[0].description

    px_results = await px_provider.search("emergency department", "2026-09-22")
    assert len(px_results) > 0
    assert any(p.code == "99284" for p in px_results)
    assert px_results[0].is_mock is True

    # Dental CDT is isolated
    cdt_results = await dental_provider.search("oral evaluation", "2026-09-22")
    assert len(cdt_results) > 0
    assert cdt_results[0].code_system == "CDT"


def test_rule_engine_validations():
    engine = RuleEngine()

    facts = [
        {"fact_type": "place_of_service", "value": {"pos_description": "Emergency Department"}},
        {"fact_type": "medical_decision_making", "value": {"mdm_level": "high"}},
    ]

    # Evaluate ED Level 5 (99285) with POS 23 and High MDM
    results_99285 = engine.validate(
        candidate_code="99285",
        code_system="CPT",
        facts=facts,
        encounter_context={"place_of_service": "23", "all_candidate_codes": ["99285", "K35.80"]},
    )
    statuses = {r.status for r in results_99285}
    assert "PASS" in statuses
    assert "FAIL" not in statuses

    # Evaluate NCCI conflict: Laparoscopic appendectomy (44970) with bundled diagnostic laparoscopy (49320)
    results_bundled = engine.validate(
        candidate_code="49320",
        code_system="CPT",
        facts=facts,
        encounter_context={"place_of_service": "23", "all_candidate_codes": ["44970", "49320"]},
    )
    assert any(r.status == "FAIL" and "bundled" in r.message for r in results_bundled)
