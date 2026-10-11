import pytest
from pathlib import Path
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_end_to_end_medical_coding_workflow(client: AsyncClient, seed_data):
    """
    Complete end-to-end integration test of the clinical coding workflow:
    1. Login as Coder & Reviewer
    2. Create new Emergency Department encounter
    3. Upload synthetic emergency clinical document
    4. Verify automatic OCR, fact extraction & evidence linking
    5. Verify candidate codes proposed & validated by deterministic rules
    6. Reviewer reviews encounter and approves verified codes
    7. Verify append-only audit trail records all transitions
    8. Export final approved worksheet in JSON, CSV, and HTML formats
    """
    # Step 1: Login Coder
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "coder@apexhealth.org", "password": "CoderPassword123!"},
    )
    assert login_resp.status_code == 200
    coder_token = login_resp.json()["access_token"]
    coder_headers = {"Authorization": f"Bearer {coder_token}"}

    # Step 2: Create Encounter (Emergency Department)
    create_enc_resp = await client.post(
        "/api/encounters",
        json={
            "patient_reference": "SYNTH-PAT-E2E-1",
            "service_date": "2026-09-22",
            "coding_domain": "emergency_department",
            "place_of_service": "23",
        },
        headers=coder_headers,
    )
    assert create_enc_resp.status_code == 201
    enc = create_enc_resp.json()
    encounter_id = enc["id"]
    assert enc["status"] == "draft"

    # Step 3: Upload Synthetic Document
    doc_path = Path("tests/fixtures/synthetic-er-record.txt")
    doc_content = doc_path.read_bytes()

    upload_resp = await client.post(
        f"/api/documents/encounter/{encounter_id}/upload",
        files={"file": ("synthetic-er-record.txt", doc_content, "text/plain")},
        headers=coder_headers,
    )
    assert upload_resp.status_code == 201
    pipeline_result = upload_resp.json()["pipeline_result"]
    assert pipeline_result["status"] == "success"

    # Step 4: Fetch Encounter Details (Facts, Evidence, Candidates, Rules)
    detail_resp = await client.get(
        f"/api/cases/{encounter_id}/review",
        headers=coder_headers,
    )
    assert detail_resp.status_code == 200
    encounter_detail = detail_resp.json()

    assert encounter_detail["status"] == "review_required"
    assert len(encounter_detail["documents"]) == 1
    assert len(encounter_detail["clinical_facts"]) > 0

    # Ensure every clinical fact has evidence
    for fact in encounter_detail["clinical_facts"]:
        assert fact["evidence"] is not None
        assert "quoted_text" in fact["evidence"]

    # Verify candidate codes proposed
    candidates = encounter_detail["candidate_codes"]
    assert len(candidates) > 0
    candidate_codes = [c["code"] for c in candidates]
    # Should find acute appendicitis K35.80 and ED E/M or procedure
    assert "K35.80" in candidate_codes

    for cand in candidates:
        assert cand["human_review_required"] is True
        assert len(cand["rule_results"]) > 0
        assert len(cand["supporting_evidence"]) > 0

    # Step 5: Login Reviewer and Approve Encounter
    rev_login_resp = await client.post(
        "/api/auth/login",
        json={"email": "reviewer@apexhealth.org", "password": "ReviewerPassword123!"},
    )
    assert rev_login_resp.status_code == 200
    reviewer_token = rev_login_resp.json()["access_token"]
    reviewer_headers = {"Authorization": f"Bearer {reviewer_token}"}

    cand_ids = [c["id"] for c in candidates if c['code'] in {'K35.80', '99285'}]
    review_resp = await client.post(
        f"/api/reviews/encounter/{encounter_id}",
        json={
            "decision": "accept",
            "notes": "Reviewed by certified coder. Clinical facts and surgical pathology support K35.80 and ED E/M.",
            "approved_candidate_ids": cand_ids,
            "version": encounter_detail["version"],
        },
        headers=reviewer_headers,
    )
    assert review_resp.status_code == 201
    assert review_resp.json()["encounter_status"] == "approved"

    # Step 6: Verify Audit Trail
    audit_resp = await client.get("/api/audit", headers=reviewer_headers)
    assert audit_resp.status_code == 200
    events = audit_resp.json()
    event_types = [e["event_type"] for e in events]
    assert "user_login" in event_types
    assert "encounter_created" in event_types
    assert "document_uploaded" in event_types
    assert "pipeline_processed" in event_types
    assert "case_decision_accept" in event_types

    # Step 7: Export Approved Coding Results
    # JSON Export
    export_json_resp = await client.get(
        f"/api/exports/encounter/{encounter_id}/json",
        headers=reviewer_headers,
    )
    assert export_json_resp.status_code == 200
    exported_data = export_json_resp.json()
    assert exported_data["status"] == "approved"
    assert len(exported_data["codes"]) > 0

    # CSV Export
    export_csv_resp = await client.get(
        f"/api/exports/encounter/{encounter_id}/csv",
        headers=reviewer_headers,
    )
    assert export_csv_resp.status_code == 200
    assert b"K35.80" in export_csv_resp.content

    # Worksheet HTML/Print Export
    export_sheet_resp = await client.get(
        f"/api/exports/encounter/{encounter_id}/worksheet",
        headers=reviewer_headers,
    )
    assert export_sheet_resp.status_code == 200
    assert b"Official Medical Coding Worksheet" in export_sheet_resp.content
    assert b"K35.80" in export_sheet_resp.content
