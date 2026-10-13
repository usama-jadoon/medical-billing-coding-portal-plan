import hashlib
import hmac
import json
import uuid
from datetime import date, datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from pydantic import BaseModel, Field, field_validator
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from services.api.db.session import get_db
from services.api.db.models import (
    Encounter, Patient, Document, DocumentPage, ClinicalFact, CodeCandidate,
    Evidence, RuleResult, Review, AuditEvent, User, CaseSnapshot, OutboxEvent, ValidationFinding
)
from services.api.security.tenant import get_current_user, get_fresh_user
from services.api.security.permissions import require_roles, Roles
from services.api.storage import get_storage
from services.api.workflow.state_machine import CaseStateMachine, CaseState, StateTransitionError
from services.api.utils.logging import audit_logger
from services.api.config import settings
from services.api.workflow.approval import validate_selection, validate_export
from services.coding_engine.providers.base import CodeSetVersionProvider
from services.rules_engine.rulesets.er_split_billing import SplitBillingReview
from services.api.workflow.split_billing import resolve_split, get_reviewed_split

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post('/detect-setting')
async def detect_setting(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    """Suggest a supported setting from source text; user confirmation is required."""
    import re
    from services.api.api.documents import validate_file_signature, MAX_FILE_SIZE
    from services.ocr.local_ocr import LocalOCRProvider
    from starlette.concurrency import run_in_threadpool
    import asyncio
    require_roles([Roles.OWNER, Roles.ADMIN, Roles.CODER, Roles.REVIEWER])(user)
    content = await file.read(MAX_FILE_SIZE + 1)
    validate_file_signature(content, file.filename or '', file.content_type or '')
    try:
        result = await run_in_threadpool(lambda: asyncio.run(LocalOCRProvider().process(content, file.filename or '')))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    text = '\n'.join(page.text for page in result.pages)
    ed = bool(re.search(r'\bemergency (department|room)\b|\bPOS\s*[:=]?\s*23\b', text, re.I))
    office = bool(re.search(r'\bphysician office\b|\bPOS\s*[:=]?\s*11\b', text, re.I))
    return {'coding_domain': ('emergency_department' if ed else 'professional_office') if ed != office else None,
            'confirmation_required': True, 'method': 'source-text-keywords',
            'message': 'Confirm the suggested setting before analysis.' if ed != office else
                       'No unambiguous supported setting found. Select it manually.'}


@router.post("/{case_id}/split-billing")
async def accept_split_billing(case_id: str, req: SplitBillingReview,
                              db: AsyncSession = Depends(get_db), user: User = Depends(get_fresh_user)):
    require_roles([Roles.OWNER, Roles.REVIEWER])(user)
    case = (await db.execute(select(Encounter).where(Encounter.id == case_id,
                                  Encounter.organization_id == user.organization_id))).scalar_one_or_none()
    if not case:
        raise HTTPException(404, 'Case not found.')
    if req.version != case.version:
        raise HTTPException(409, 'Case changed. Reload before accepting billing lines.')
    output, approval_id = await resolve_split(db, case, req)
    event = AuditEvent(organization_id=user.organization_id, actor_id=user.id,
        event_type='er_split_billing_accepted', entity_type='case', entity_id=case.id,
        metadata_json={'request': req.model_dump(mode='json'), 'approval_id': approval_id,
                       'ruleset_version': output['ruleset_version'], 'warnings': output['warnings']})
    db.add(event)
    case.version += 1
    await db.commit()
    return {**output, 'billing_review_id': event.id, 'version': case.version}


@router.get("/{case_id}/split-billing")
async def read_split_billing(case_id: str, db: AsyncSession = Depends(get_db),
                            user: User = Depends(get_fresh_user)):
    case = (await db.execute(select(Encounter).where(Encounter.id == case_id,
                                  Encounter.organization_id == user.organization_id))).scalar_one_or_none()
    if not case:
        raise HTTPException(404, 'Case not found.')
    return {'version': case.version, 'split': await get_reviewed_split(db, case)}


@router.post("/{case_id}/documents", status_code=201)
async def upload_case_document(case_id: str, file: UploadFile = File(...),
                               db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from services.api.api.documents import upload_document
    return await upload_document(case_id, file, db, current_user)


class CreateCaseRequest(BaseModel):
    patient_reference: str = Field(..., min_length=1, max_length=255, description="Pseudonymous patient reference / MRN")
    service_date: date = Field(..., description="Date of Service (YYYY-MM-DD)")
    coding_domain: Literal["emergency_department", "professional_office"] = "emergency_department"
    place_of_service: str = Field(default="23", description="23=ED, 11=Office")

    @field_validator("patient_reference")
    @classmethod
    def nonempty_reference(cls, value):
        if not value.strip():
            raise ValueError("Patient reference cannot be blank.")
        return value.strip()


class CaseDecisionRequest(BaseModel):
    decision: str = Field(..., description="accept, edit, reject, request_documentation, mark_uncertain")
    notes: str = Field(default="", description="Owner-reviewer rationale")
    approved_candidate_ids: List[str] = Field(default_factory=list)
    version: int = Field(..., ge=1, description="Current case version from the review package")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_case(
    req: CreateCaseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """POST /cases: Creates a domain-scoped medical coding case."""
    require_roles([Roles.OWNER, Roles.ADMIN, Roles.CODER, Roles.REVIEWER])(current_user)
    org_id = current_user.organization_id

    if req.place_of_service != {"emergency_department": "23", "professional_office": "11"}[req.coding_domain]:
        raise HTTPException(422, "Place of service must match the selected development profile.")

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

    # 2. Create case (Encounter) in CREATED state
    case = Encounter(
        organization_id=org_id,
        patient_id=patient.id,
        service_date=req.service_date.isoformat(),
        coding_domain=req.coding_domain.strip(),
        place_of_service=req.place_of_service.strip(),
        status=CaseState.CREATED.value,
    )
    db.add(case)
    await db.flush()

    # 3. Create CaseSnapshot pinning ruleset and code-set release
    release = CodeSetVersionProvider.resolve_version("ICD-10-CM", case.service_date)
    snapshot_raw = f"{case.id}:{case.service_date}:{case.coding_domain}:{release}:demo-1"
    snapshot_hash = hashlib.sha256(snapshot_raw.encode("utf-8")).hexdigest()

    snapshot = CaseSnapshot(
        case_id=case.id,
        service_date=case.service_date,
        domain_profile=case.coding_domain,
        code_system_release=release,
        ruleset_version="demo-1",
        snapshot_hash=snapshot_hash,
    )
    db.add(snapshot)
    await db.flush()

    # 4. Outbox event: document.created
    outbox = OutboxEvent(
        event_type="case.created",
        owner_id=current_user.id,
        case_id=case.id,
        snapshot_id=snapshot.id,
        producer="application-api",
        payload_json={"coding_domain": case.coding_domain, "service_date": case.service_date},
        status="pending",
    )
    db.add(outbox)

    # 5. Audit event
    audit = AuditEvent(
        organization_id=org_id,
        actor_id=current_user.id,
        event_type="case_created",
        entity_type="case",
        entity_id=case.id,
        metadata_json={"service_date": case.service_date, "coding_domain": case.coding_domain},
    )
    db.add(audit)
    await db.commit()

    return {
        "id": case.id,
        "patient_reference": patient.external_reference,
        "service_date": case.service_date,
        "coding_domain": case.coding_domain,
        "place_of_service": case.place_of_service,
        "status": case.status,
        "version": case.version,
        "snapshot_id": snapshot.id,
        "snapshot_hash": snapshot.snapshot_hash,
        "created_at": case.created_at.isoformat(),
    }


@router.get("")
async def list_cases(
    domain: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists cases for the authenticated owner."""
    stmt = (
        select(Encounter)
        .where(Encounter.organization_id == current_user.organization_id)
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
    cases = res.scalars().all()

    return [
        {
            "id": c.id,
            "patient_reference": c.patient.external_reference if c.patient else "",
            "service_date": c.service_date,
            "coding_domain": c.coding_domain,
            "place_of_service": c.place_of_service,
            "status": c.status,
            "version": c.version,
            "document_count": len(c.documents),
            "candidate_count": sum(candidate.snapshot_id == c.active_snapshot_id for candidate in c.code_candidates),
            "created_at": c.created_at.isoformat(),
        }
        for c in cases
    ]


@router.get("/{case_id}")
async def get_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """GET /cases/{id}: Fetch snapshot and status."""
    stmt = (
        select(Encounter)
        .where(Encounter.id == case_id, Encounter.organization_id == current_user.organization_id)
        .options(
            selectinload(Encounter.patient),
            selectinload(Encounter.documents).selectinload(Document.pages),
            selectinload(Encounter.code_candidates),
        )
    )
    res = await db.execute(stmt)
    case = res.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    snap_stmt = select(CaseSnapshot).where(CaseSnapshot.case_id == case.id).order_by(desc(CaseSnapshot.created_at))
    snap_res = await db.execute(snap_stmt)
    latest_snapshot = snap_res.scalars().first()

    return {
        "id": case.id,
        "patient_reference": case.patient.external_reference if case.patient else "",
        "service_date": case.service_date,
        "coding_domain": case.coding_domain,
        "place_of_service": case.place_of_service,
        "status": case.status,
        "version": case.version,
        "document_count": len(case.documents),
        "candidate_count": len(case.code_candidates),
        "latest_snapshot": {
            "id": latest_snapshot.id,
            "snapshot_hash": latest_snapshot.snapshot_hash,
            "code_system_release": latest_snapshot.code_system_release,
            "ruleset_version": latest_snapshot.ruleset_version,
        } if latest_snapshot else None,
        "created_at": case.created_at.isoformat(),
    }


@router.get("/{case_id}/review")
async def get_case_review(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """GET /cases/{id}/review: Load evidence package for three-pane owner review."""
    stmt = (
        select(Encounter)
        .where(Encounter.id == case_id, Encounter.organization_id == current_user.organization_id)
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
    case = res.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    findings_stmt = select(ValidationFinding).where(ValidationFinding.case_id == case_id, ValidationFinding.snapshot_id == case.active_snapshot_id)
    findings_res = await db.execute(findings_stmt)
    findings = findings_res.scalars().all()

    return {
        "id": case.id,
        "patient_reference": case.patient.external_reference if case.patient else "",
        "service_date": case.service_date,
        "coding_domain": case.coding_domain,
        "place_of_service": case.place_of_service,
        "status": case.status,
        "version": case.version,
        "snapshot_id": case.active_snapshot_id,
        "provenance": (await db.get(CaseSnapshot, case.active_snapshot_id)).provenance_json if case.active_snapshot_id else None,
        "created_at": case.created_at.isoformat(),
        "documents": [
            {
                "id": d.id,
                "filename": d.filename,
                "mime_type": d.mime_type,
                "sha256": d.sha256,
                "file_size_bytes": d.file_size_bytes,
                "created_at": d.created_at.isoformat(),
                "page_count": d.page_count,
                "pages": [
                    {
                        "page_number": p.page_number,
                        "ocr_text": p.ocr_text,
                    }
                    for p in d.pages
                ]
            }
            for d in case.documents
        ],
        "clinical_facts": [
            {
                "id": f.id,
                "fact_type": f.fact_type,
                "value": f.value_json,
                "evidence": {
                    "id": f.evidence.id,
                    "document_id": f.evidence.document_id,
                    "evidence_type": f.evidence.evidence_type,
                    "page_number": f.evidence.page_number,
                    "start_offset": f.evidence.start_offset,
                    "end_offset": f.evidence.end_offset,
                    "quoted_text": f.evidence.quoted_text,
                    "region_id": f.evidence.region_id,
                    "bbox": {
                        "x": f.evidence.bbox_x,
                        "y": f.evidence.bbox_y,
                        "width": f.evidence.bbox_w,
                        "height": f.evidence.bbox_h,
                    } if f.evidence.bbox_x is not None else None,
                    "quote_hash": f.evidence.quote_hash,
                    "evidence_role": f.evidence.evidence_role,
                } if f.evidence else None,
            }
            for f in case.clinical_facts if f.snapshot_id == case.active_snapshot_id
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
                        "document_id": ev.document_id,
                        "evidence_type": ev.evidence_type,
                        "page_number": ev.page_number,
                        "start_offset": ev.start_offset,
                        "end_offset": ev.end_offset,
                        "quoted_text": ev.quoted_text,
                        "region_id": ev.region_id,
                        "bbox": {
                            "x": ev.bbox_x,
                            "y": ev.bbox_y,
                            "width": ev.bbox_w,
                            "height": ev.bbox_h,
                        } if ev.bbox_x is not None else None,
                        "evidence_role": ev.evidence_role,
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
            for c in case.code_candidates if c.snapshot_id == case.active_snapshot_id
        ],
        "validation_findings": [
            {
                "id": vf.id,
                "stage": vf.stage,
                "severity": vf.severity,
                "rule_id": vf.rule_id,
                "message": vf.message,
                "source_reference": vf.source_reference,
                "candidate_id": vf.candidate_id,
            }
            for vf in findings
        ],
        "reviews": [
            {
                "id": r.id,
                "reviewer_email": r.reviewer.email if r.reviewer else "",
                "decision": r.decision,
                "notes": r.notes,
                "created_at": r.created_at.isoformat(),
            }
            for r in case.reviews
        ],
    }


@router.post("/{case_id}/decisions", status_code=status.HTTP_201_CREATED)
async def submit_case_decision(
    case_id: str,
    req: CaseDecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_fresh_user),
):
    """
    POST /cases/{id}/decisions: Record owner-reviewer action.
    Hard gate: automation cannot approve. Only authenticated owner-reviewer can approve.
    """
    require_roles([Roles.OWNER, Roles.ADMIN, Roles.REVIEWER])(current_user)
    org_id = current_user.organization_id

    stmt = select(Encounter).where(
        Encounter.id == case_id, Encounter.organization_id == org_id
    )
    res = await db.execute(stmt)
    case = res.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    allowed_decisions = {"accept", "edit", "reject", "request_documentation", "mark_uncertain"}
    if req.version != case.version:
        raise HTTPException(409, "Case changed. Reload before making a decision.")
    if req.decision not in allowed_decisions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid decision '{req.decision}'. Allowed: {allowed_decisions}",
        )

    # Revalidate the selected snapshot; excluded proposals do not become approved.
    if req.decision == "accept":
        await validate_selection(db, case, req.approved_candidate_ids)

    # State transition check
    target_state = CaseState.APPROVED if req.decision == "accept" else (
        CaseState.REVIEW_REQUIRED if req.decision in {"edit", "mark_uncertain"} else (
            CaseState.CREATED if req.decision == "request_documentation" else CaseState.REVIEW_REQUIRED
        )
    )

    try:
        current_state_enum = CaseState(case.status) if case.status in [s.value for s in CaseState] else (
            CaseState.REVIEW_REQUIRED if case.status == "review" else CaseState.CREATED
        )
        event = CaseStateMachine.transition(
            current_state=current_state_enum,
            target_state=target_state,
            case_id=case.id,
            owner_id=current_user.id,
            is_owner=current_user.role in {Roles.OWNER, Roles.REVIEWER},
            actor_role=current_user.role,
            payload={"decision": req.decision, "approved_candidates": req.approved_candidate_ids},
        )
    except StateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Persist Review record
    review = Review(
        encounter_id=case.id,
        reviewer_id=current_user.id,
        decision=req.decision,
        notes=req.notes,
    )
    db.add(review)
    case.status = target_state.value
    # Self-transitions (uncertain/edit) also consume a concurrency version.
    case.version += 1

    # Update candidate statuses if accepted
    current_candidates = (await db.execute(select(CodeCandidate).where(
        CodeCandidate.encounter_id == case.id, CodeCandidate.snapshot_id == case.active_snapshot_id,
    ))).scalars().all()
    for cand in current_candidates:
        selected = req.decision == "accept" and cand.id in req.approved_candidate_ids
        cand.status = "approved" if selected else ("rejected" if req.decision in {"accept", "reject"} else "candidate")
        cand.human_review_required = not selected

    # Outbox event
    outbox = OutboxEvent(
        event_id=event.event_id,
        event_type=event.event_type,
        owner_id=current_user.id,
        case_id=case.id,
        producer=event.producer,
        payload_json=event.payload,
        status="pending",
    )
    db.add(outbox)

    # Audit event
    audit = AuditEvent(
        organization_id=org_id,
        actor_id=current_user.id,
        event_type=f"case_decision_{req.decision}",
        entity_type="case",
        entity_id=case.id,
        metadata_json={"decision": req.decision, "approved_candidates": req.approved_candidate_ids},
    )
    db.add(audit)
    await db.commit()

    return {
        "case_id": case.id,
        "status": case.status,
        "version": case.version,
        "decision": req.decision,
        "review_id": review.id,
        "timestamp": review.created_at.isoformat(),
    }


@router.post("/{case_id}/exports", status_code=status.HTTP_200_OK)
async def export_case_manifest(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_fresh_user),
):
    """
    POST /cases/{id}/exports: Creates a signed export manifest and approved coding worksheet.
    Only approved cases can be exported.
    """
    stmt = (
        select(Encounter)
        .where(Encounter.id == case_id, Encounter.organization_id == current_user.organization_id)
        .options(
            selectinload(Encounter.patient),
            selectinload(Encounter.code_candidates),
            selectinload(Encounter.reviews),
        )
    )
    res = await db.execute(stmt)
    case = res.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    require_roles([Roles.OWNER, Roles.REVIEWER])(current_user)
    snapshot, candidates = await validate_export(db, case)

    approved_codes = [
        {"code": c.code, "system": c.code_system, "version": c.code_version}
        for c in candidates
    ]
    split_billing = await get_reviewed_split(db, case) if case.coding_domain == 'emergency_department' else None

    manifest_payload = {
        "manifest_id": str(uuid.uuid4()),
        "case_id": case.id,
        "service_date": case.service_date,
        "domain_profile": case.coding_domain,
        "snapshot_hash": snapshot.snapshot_hash if snapshot else "",
        "snapshot_id": snapshot.id,
        "source_document_version_id": snapshot.source_document_version_id,
        "provenance": snapshot.provenance_json,
        "approved_codes": approved_codes,
        "split_billing": split_billing,
        "reviewer_id": current_user.id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "signature_algorithm": "HMAC-SHA256",
        "mode": "synthetic-development",
    }
    manifest_payload["integrity_signature"] = hmac.new(
        settings.SECRET_KEY.encode(),
        json.dumps(manifest_payload, sort_keys=True, separators=(",", ":")).encode(),
        hashlib.sha256,
    ).hexdigest()

    # Transition to exported
    case.status = CaseState.EXPORTED.value

    # Record outbox and audit events
    outbox = OutboxEvent(
        event_type="export.completed",
        owner_id=current_user.id,
        case_id=case.id,
        producer="export-worker",
        payload_json=manifest_payload,
        status="pending",
    )
    db.add(outbox)

    audit = AuditEvent(
        organization_id=current_user.organization_id,
        actor_id=current_user.id,
        event_type="case_exported",
        entity_type="case",
        entity_id=case.id,
        metadata_json={"manifest_id": manifest_payload["manifest_id"]},
    )
    db.add(audit)
    await db.commit()

    return manifest_payload
