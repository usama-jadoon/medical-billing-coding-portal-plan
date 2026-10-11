"""Compatibility route; review commands share the case approval policy."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from services.api.db.session import get_db
from services.api.db.models import User
from services.api.security.tenant import get_fresh_user
from services.api.api.cases import CaseDecisionRequest, submit_case_decision

router = APIRouter(prefix="/reviews", tags=["reviews"])
SubmitReviewRequest = CaseDecisionRequest


@router.post("/encounter/{encounter_id}", status_code=201)
async def submit_review(encounter_id: str, req: SubmitReviewRequest,
                        db: AsyncSession = Depends(get_db), current_user: User = Depends(get_fresh_user)):
    result = await submit_case_decision(encounter_id, req, db, current_user)
    return {**result, "id": result["review_id"], "encounter_id": encounter_id,
            "encounter_status": result["status"], "notes": req.notes, "created_at": result["timestamp"]}
