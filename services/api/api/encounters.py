from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from services.api.db.session import get_db
from services.api.db.models import (
    Encounter, Patient, Document, ClinicalFact, CodeCandidate,
    Evidence, RuleResult, Review, AuditEvent, User
)
from services.api.security.tenant import get_current_user, get_current_tenant
from services.api.security.permissions import require_roles, Roles

router = APIRouter(prefix="/encounters", tags=["encounters"])


class CreateEncounterRequest(BaseModel):
    patient_reference: str = Field(..., description="Pseudonymous patient reference / MRN")
    service_date: str = Field(..., description="Date of Service (YYYY-MM-DD)")
    coding_domain: str = Field(..., description="Coding domain e.g. emergency_department, professional_office")
    place_of_service: str = Field(default="23", description="Place of service code (e.g. 23=ED, 11=Office)")


@router.get("")
async def list_encounters(
    domain: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
):
    stmt = (
        select(Encounter)
        .where(Encounter.organization_id == tenant_id)
        .options(
            selectinload(Encounter.patient),
            selectinload(Encounter.documents),
            selectinload(Encounter.code_candidates),
        )
        .order_by(desc(Encounter.created_at))
    )
    if domain:
        stmt = stmt.where(Encounter.coding_domain == domain)
    if status_filter:
        stmt = stmt.where(Encounter.status == status_filter)

    res = await db.execute(stmt)
    encounters = res.scalars().all()

    return [
        {
            "id": enc.id,
            "organization_id": enc.organization_id,
            "patient_id": enc.patient_id,
            "patient_reference": enc.patient.external_reference if enc.patient else "",
            "service_date": enc.service_date,
            "coding_domain": enc.coding_domain,
            "place_of_service": enc.place_of_service,
            "status": enc.status,
            "document_count": len(enc.documents),
            "candidate_count": len(enc.code_candidates),
            "created_at": enc.created_at.isoformat(),
        }
        for enc in encounters
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_encounter(
    req: CreateEncounterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Enforce coder or above
    require_roles([Roles.OWNER, Roles.ADMIN, Roles.CODER, Roles.REVIEWER])(current_user)
    org_id = current_user.organization_id

    # 1. Resolve or create pseudonymous patient reference
    stmt = select(Patient).where(
        Patient.organization_id == org_id,
        Patient.external_reference == req.patient_reference.strip(),
    )
    res = await db.execute(stmt)
    patient = res.scalar_one_or_none()
    if not patient:
        patient = Patient(
            organization_id=org_id,
            external_reference=req.patient_reference.strip(),
        )
        db.add(patient)
        await db.flush()

    # 2. Create encounter
    encounter = Encounter(
        organization_id=org_id,
        patient_id=patient.id,
        service_date=req.service_date.strip(),
        coding_domain=req.coding_domain.strip(),
        place_of_service=req.place_of_service.strip(),
        status="draft",
    )
    db.add(encounter)
    await db.flush()

    audit = AuditEvent(
        organization_id=org_id,
        actor_id=current_user.id,
        event_type="encounter_created",
        entity_type="encounter",
        entity_id=encounter.id,
        metadata_json={
            "coding_domain": encounter.coding_domain,
            "service_date": encounter.service_date,
        },
    )
    db.add(audit)
    await db.commit()

    return {
        "id": encounter.id,
        "patient_id": patient.id,
        "patient_reference": patient.external_reference,
        "service_date": encounter.service_date,
        "coding_domain": encounter.coding_domain,
        "place_of_service": encounter.place_of_service,
        "status": encounter.status,
        "created_at": encounter.created_at.isoformat(),
    }


@router.get("/{encounter_id}")
async def get_encounter(
    encounter_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
):
    # Must enforce tenant isolation
    stmt = (
        select(Encounter)
        .where(Encounter.id == encounter_id, Encounter.organization_id == tenant_id)
        .options(
            selectinload(Encounter.patient),
            selectinload(Encounter.documents).selectinload(Document.pages),
            selectinload(Encounter.clinical_facts).selectinload(ClinicalFact.evidence),
            selectinload(Encounter.code_candidates).selectinload(CodeCandidate.supporting_evidence),
            selectinload(Encounter.code_candidates).selectinload(CodeCandidate.rule_results),
            selectinload(Encounter.reviews).selectinload(Review.reviewer),
        )
    )
    res = await db.execute(stmt)
    enc = res.scalar_one_or_none()

    if not enc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encounter not found.",
        )

    return {
        "id": enc.id,
        "organization_id": enc.organization_id,
        "patient_id": enc.patient_id,
        "patient_reference": enc.patient.external_reference if enc.patient else "",
        "service_date": enc.service_date,
        "coding_domain": enc.coding_domain,
        "place_of_service": enc.place_of_service,
        "status": enc.status,
        "created_at": enc.created_at.isoformat(),
        "documents": [
            {
                "id": d.id,
                "filename": d.filename,
                "mime_type": d.mime_type,
                "file_size_bytes": d.file_size_bytes,
                "page_count": d.page_count,
                "created_at": d.created_at.isoformat(),
                "pages": [
                    {
                        "page_number": p.page_number,
                        "ocr_text": p.ocr_text,
                    }
                    for p in d.pages
                ]
            }
            for d in enc.documents
        ],
        "clinical_facts": [
            {
                "id": f.id,
                "fact_type": f.fact_type,
                "value": f.value_json,
                "evidence": {
                    "id": f.evidence.id,
                    "page_number": f.evidence.page_number,
                    "start_offset": f.evidence.start_offset,
                    "end_offset": f.evidence.end_offset,
                    "quoted_text": f.evidence.quoted_text,
                    "evidence_type": f.evidence.evidence_type,
                } if f.evidence else None,
            }
            for f in enc.clinical_facts
        ],
        "candidate_codes": [
            {
                "id": c.id,
                "code_system": c.code_system,
                "code": c.code,
                "code_version": c.code_version,
                "status": c.status,
                "rationale": c.rationale,
                "human_review_required": c.human_review_required,
                "supporting_evidence": [
                    {
                        "id": ev.id,
                        "page_number": ev.page_number,
                        "start_offset": ev.start_offset,
                        "end_offset": ev.end_offset,
                        "quoted_text": ev.quoted_text,
                        "evidence_type": ev.evidence_type,
                    }
                    for ev in c.supporting_evidence
                ],
                "rule_results": [
                    {
                        "rule_id": rr.rule_id,
                        "status": rr.status,
                        "message": rr.message,
                        "source_reference": rr.source_reference,
                    }
                    for rr in c.rule_results
                ],
            }
            for c in enc.code_candidates
        ],
        "reviews": [
            {
                "id": r.id,
                "reviewer_email": r.reviewer.email if r.reviewer else "",
                "decision": r.decision,
                "notes": r.notes,
                "created_at": r.created_at.isoformat(),
            }
            for r in enc.reviews
        ],
    }
