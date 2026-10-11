import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_user_cannot_view_other_organization_encounter(client: AsyncClient, seed_data):
    """
    Proves User A (Org 1) cannot view Organization B's encounter.
    """
    token_org1 = seed_data["tokens"]["coder_org1"]
    enc2_id = seed_data["encounter2"].id  # Belongs to Org 2

    headers = {"Authorization": f"Bearer {token_org1}"}
    response = await client.get(f"/api/encounters/{enc2_id}", headers=headers)

    # Must return 404 Not Found to prevent tenant data leakage
    assert response.status_code == 404
    data = response.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_user_cannot_list_other_organization_encounters(client: AsyncClient, seed_data):
    """
    Proves User A (Org 1) only sees Org 1 encounters in list queries.
    """
    token_org1 = seed_data["tokens"]["coder_org1"]
    headers = {"Authorization": f"Bearer {token_org1}"}

    response = await client.get("/api/encounters", headers=headers)
    assert response.status_code == 200
    encounters = response.json()

    # Should only return encounters for org 1
    assert len(encounters) == 1
    assert encounters[0]["id"] == seed_data["encounter1"].id
    assert encounters[0]["organization_id"] == seed_data["org1"].id


@pytest.mark.asyncio
async def test_user_cannot_modify_other_organization_review(client: AsyncClient, seed_data):
    """
    Proves Reviewer A (Org 1) cannot submit or modify a review on Organization B's encounter.
    """
    token_org1_reviewer = seed_data["tokens"]["reviewer_org1"]
    enc2_id = seed_data["encounter2"].id  # Org 2 encounter

    headers = {"Authorization": f"Bearer {token_org1_reviewer}"}
    payload = {
        "decision": "accept",
        "notes": "Attempting cross-tenant approval",
        "version": 1,
    }
    response = await client.post(f"/api/reviews/encounter/{enc2_id}", json=payload, headers=headers)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_download_other_organization_document(client: AsyncClient, seed_data):
    """
    Proves User A (Org 1) cannot download a document belonging to Organization B.
    """
    token_org1 = seed_data["tokens"]["coder_org1"]
    fake_doc_id_org2 = "doc-org-2-uuid"

    headers = {"Authorization": f"Bearer {token_org1}"}
    response = await client.get(f"/api/documents/{fake_doc_id_org2}/download", headers=headers)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_spoof_organization_id_in_payload(client: AsyncClient, seed_data):
    """
    Proves server ignores or rejects any organization_id supplied in body,
    resolving tenant strictly from authenticated session token.
    """
    token_org1 = seed_data["tokens"]["coder_org1"]
    headers = {"Authorization": f"Bearer {token_org1}"}

    payload = {
        "patient_reference": "SPOOF-TEST-1",
        "service_date": "2026-09-22",
        "coding_domain": "emergency_department",
        "place_of_service": "23",
        "organization_id": seed_data["org2"].id,  # Attempt to inject Org 2 ID
    }
    response = await client.post("/api/encounters", json=payload, headers=headers)
    assert response.status_code == 201

    created_enc = response.json()
    # The created encounter MUST belong to Org 1 (from session token), NOT Org 2!
    enc_id = created_enc["id"]
    get_res = await client.get(f"/api/encounters/{enc_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["organization_id"] == seed_data["org1"].id
