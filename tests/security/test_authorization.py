import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_readonly_user_cannot_create_encounter(client: AsyncClient, seed_data):
    """
    Proves Read-Only role cannot create an encounter.
    """
    token_readonly = seed_data["tokens"]["readonly_org1"]
    headers = {"Authorization": f"Bearer {token_readonly}"}

    payload = {
        "patient_reference": "READONLY-DENIED",
        "service_date": "2026-09-22",
        "coding_domain": "emergency_department",
        "place_of_service": "23",
    }
    response = await client.post("/api/encounters", json=payload, headers=headers)
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_coder_cannot_approve_review(client: AsyncClient, seed_data):
    """
    Proves Coder cannot perform final review approval (Reviewer role required).
    """
    token_coder = seed_data["tokens"]["coder_org1"]
    headers = {"Authorization": f"Bearer {token_coder}"}
    enc1_id = seed_data["encounter1"].id

    payload = {
        "decision": "accept",
        "notes": "Coder attempting to self-approve",
        "version": 1,
    }
    response = await client.post(f"/api/reviews/encounter/{enc1_id}", json=payload, headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_reviewer_can_submit_review(client: AsyncClient, seed_data):
    """
    Proves authorized Reviewer can submit a review decision.
    """
    token_reviewer = seed_data["tokens"]["reviewer_org1"]
    headers = {"Authorization": f"Bearer {token_reviewer}"}
    enc1_id = seed_data["encounter1"].id

    payload = {
        "decision": "mark_uncertain",
        "notes": "Awaiting clinical record verification",
        "version": 1,
    }
    response = await client.post(f"/api/reviews/encounter/{enc1_id}", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["decision"] == "mark_uncertain"
    assert data["encounter_status"] == "review_required"
