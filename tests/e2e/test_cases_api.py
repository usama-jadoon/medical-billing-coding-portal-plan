import pytest


@pytest.mark.asyncio
async def test_cases_api_full_lifecycle(client, seed_data):
    token = seed_data["tokens"]["reviewer_org1"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create domain-scoped case
    create_resp = await client.post(
        "/api/cases",
        json={
            "patient_reference": "MRN-CASE-2026",
            "service_date": "2026-09-21",
            "coding_domain": "emergency_department",
            "place_of_service": "23",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    case_data = create_resp.json()
    case_id = case_data["id"]
    assert case_data["status"] == "created"
    assert case_data["snapshot_id"] is not None

    # 2. Get case status
    get_resp = await client.get(f"/api/cases/{case_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == case_id

    # 3. Get case review payload
    review_resp = await client.get(f"/api/cases/{case_id}/review", headers=headers)
    assert review_resp.status_code == 200
    review_pkg = review_resp.json()
    assert "clinical_facts" in review_pkg
    assert "candidate_codes" in review_pkg
    assert "validation_findings" in review_pkg

    # 4. Attempt export before approval -> should be blocked
    export_blocked_resp = await client.post(f"/api/cases/{case_id}/exports", headers=headers)
    assert export_blocked_resp.status_code == 400
    err_body = export_blocked_resp.json()
    err_msg = err_body.get("error", {}).get("message", "") or err_body.get("detail", "")
    assert "Export blocked" in err_msg

    # 5. Submit decision
    decision_resp = await client.post(
        f"/api/cases/{case_id}/decisions",
        json={
            "decision": "accept",
            "notes": "Verified against ED physician clinical chart.",
            "approved_candidate_ids": [],
                "version": case_data["version"],
        },
        headers=headers,
    )
    assert decision_resp.status_code == 400

    # 6. An empty case must remain non-exportable
    export_resp = await client.post(f"/api/cases/{case_id}/exports", headers=headers)
    assert export_resp.status_code == 400
