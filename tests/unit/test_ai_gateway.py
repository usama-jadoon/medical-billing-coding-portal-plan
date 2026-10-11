import pytest
from services.coding_engine.ai.gateway import (
    AIGatewayBroker,
    AIGatewayRequest,
    AIGatewayValidationError,
    get_ai_gateway_broker,
)


def test_ai_gateway_policy_validation_prohibited_task():
    broker = get_ai_gateway_broker()

    req = AIGatewayRequest(
        task_type="autonomous_approval",  # Prohibited!
        case_snapshot_id="snap-123",
    )

    with pytest.raises(AIGatewayValidationError) as exc:
        broker.validate_request(req)
    assert "Policy violation" in str(exc.value)


def test_ai_gateway_reference_validation_and_entailment_guard():
    broker = get_ai_gateway_broker()

    req = AIGatewayRequest(
        task_type="clinical_extraction",
        case_snapshot_id="snap-123",
        permitted_evidence_regions=["region-valid-1"],
        candidate_ids=["cand-1"],
    )

    source_text = "Patient presented with severe acute chest pain radiating to left shoulder."

    raw_response = {
        "claims": [
            # Grounded claim with valid region
            {
                "type": "diagnosis",
                "normalized_value": {"condition": "chest pain"},
                "evidence_region_ids": ["region-valid-1"],
            },
            # Ungrounded claim with forged/hallucinated region
            {
                "type": "diagnosis",
                "normalized_value": {"condition": "headache"},
                "evidence_region_ids": ["region-hallucinated-99"],
            },
            # Grounded region but fabricated condition not entailed in source
            {
                "type": "diagnosis",
                "normalized_value": {"condition": "unsupported fracture"},
                "evidence_region_ids": ["region-valid-1"],
            },
        ],
        "candidate_rankings": [
            {"candidate_id": "cand-1", "evidence_region_ids": ["region-valid-1"]},
            {"candidate_id": "cand-invalid-99", "evidence_region_ids": []},
        ],
        "missing_documentation": [],
        "explanation_draft": "Document supports acute chest pain evaluation.",
    }

    validated = broker.validate_and_filter_response(req, raw_response, known_source_text=source_text)

    # Hallucinated region and non-entailed condition filtered out
    assert len(validated.claims) == 1
    assert validated.claims[0].normalized_value["condition"] == "chest pain"

    # Invalid candidate ID filtered out
    assert len(validated.candidate_rankings) == 1
    assert validated.candidate_rankings[0].candidate_id == "cand-1"
