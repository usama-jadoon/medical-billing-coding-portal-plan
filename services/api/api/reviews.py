from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from services.api.db.session import get_db
from services.api.db.models import Encounter, Review, AuditEvent, User, CodeCandidate
from services.api.security.tenant import get_current_user
from services.api.security.permissions import require_roles, Roles
from services.api.utils.logging import audit_logger

router = APIRouter(prefix="/reviews", tags=["reviews"])


class SubmitReviewRequest(BaseModel):
    decision: str = Field(..., description="accept, reject, edit, request_documentation, mark_uncertain")
    notes: str = Field(default="", description="Reviewer notes or rationale")
    approved_candidate_ids: list[str] = Field(default_factory=list, description="IDs of accepted code candidates")


@router.post("/encounter/{encounter_id}", status_code=status.HTTP_201_CREATED)
async def submit_review(
    encounter_id: str,
    req: SubmitReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Enforce Reviewer or Admin/Owner
    require_roles([Roles.OWNER, Roles.ADMIN, Roles.REVIEWER])(current_user)
    org_id = current_user.organization_id

    # Verify encounter belongs to current tenant
    stmt = select(Encounter).where(
        Encounter.id == encounter_id, Encounter.organization_id == org_id
    )
    res = await db.execute(stmt)
    encounter = res.scalar_one_or_none()
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encounter not found for your organization.",
        )

    # Validate decision
    allowed_decisions = {
        "accept", "reject", "edit", "request_documentation", "mark_uncertain"
    }
    if req.decision not in allowed_decisions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid review decision '{req.decision}'. Allowed: {allowed_decisions}",
        )

    # Create review entry
    review = Review(
        encounter_id=encounter.id,
        reviewer_id=current_user.id,
        decision=req.decision,
        notes=req.notes,
    )
    db.add(review)
    await db.flush()

    # Update encounter status based on decision
    if req.decision == "accept":
        encounter.status = "approved"
        # Update candidate statuses
        if req.approved_candidate_ids:
            for cid in req.approved_candidate_ids:
                cand_stmt = select(CodeCandidate).where(
                    CodeCandidate.id == cid, CodeCandidate.encounter_id == encounter.id
                )
                cand_res = await db.execute(cand_stmt)
                cand = cand_res.scalar_one_or_none()
                if cand:
                    cand.status = "approved"
                    cand.human_review_required = False
    elif req.decision == "reject":
        encounter.status = "rejected"
    elif req.decision == "request_documentation":
        encounter.status = "draft"
    else:
        encounter.status = "review"

    # Append-only audit record
    audit = AuditEvent(
        organization_id=org_id,
        actor_id=current_user.id,
        event_type=f"review_{req.decision}",
        entity_type="review",
        entity_id=review.id,
        metadata_json={
            "encounter_id": encounter.id,
            "decision": req.decision,
            "approved_candidates": req.approved_candidate_ids,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(review)

    audit_logger.log(
        level="info",
        action="REVIEW_SUBMITTED",
        actor_id=current_user.id,
        organization_id=org_id,
        status="success",
        metadata={"decision": req.decision, "encounter_id": encounter.id},
    )

    return {
        "id": review.id,
        "encounter_id": encounter.id,
        "decision": review.decision,
        "notes": review.notes,
        "encounter_status": encounter.status,
        "created_at": review.created_at.isoformat(),
    }
