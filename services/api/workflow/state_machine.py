"""
Workflow State Machine for Evidence-First Medical Coding Platform.
Enforces Section 4 & 9 of the October 2026 Architecture:
- Explicit 9 states: Created -> Ingesting -> OCR ready -> Facts ready -> Candidates ready -> Validated -> Review required -> Approved -> Exported
- Hard approval gate: Only authenticated owner-reviewer can approve.
- Invalidation on material edits: Reverts to Review Required.
"""

from enum import Enum
from typing import Dict, Set, Optional, Any
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field


class CaseState(str, Enum):
    CREATED = "created"
    INGESTING = "ingesting"
    OCR_READY = "ocr_ready"
    FACTS_READY = "facts_ready"
    CANDIDATES_READY = "candidates_ready"
    VALIDATED = "validated"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    EXPORTED = "exported"


# Permitted linear forward progression and branch/reset flows
ALLOWED_TRANSITIONS: Dict[CaseState, Set[CaseState]] = {
    CaseState.CREATED: {CaseState.INGESTING, CaseState.REVIEW_REQUIRED},
    CaseState.INGESTING: {CaseState.OCR_READY, CaseState.REVIEW_REQUIRED},
    CaseState.OCR_READY: {CaseState.FACTS_READY, CaseState.REVIEW_REQUIRED},
    CaseState.FACTS_READY: {CaseState.CANDIDATES_READY, CaseState.REVIEW_REQUIRED},
    CaseState.CANDIDATES_READY: {CaseState.VALIDATED, CaseState.REVIEW_REQUIRED},
    CaseState.VALIDATED: {CaseState.REVIEW_REQUIRED, CaseState.APPROVED},
    CaseState.REVIEW_REQUIRED: {CaseState.APPROVED, CaseState.REVIEW_REQUIRED, CaseState.CREATED, CaseState.INGESTING},
    CaseState.APPROVED: {CaseState.EXPORTED, CaseState.REVIEW_REQUIRED},  # Invalidation returns to review_required
    CaseState.EXPORTED: {CaseState.REVIEW_REQUIRED},  # If re-opened or amended
}


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted or permissions fail."""
    pass


class EventEnvelope(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    occurred_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    owner_id: str
    case_id: str
    snapshot_id: Optional[str] = None
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    causation_id: Optional[str] = None
    producer: str
    schema_version: int = 1
    payload: Dict[str, Any] = Field(default_factory=dict)


class CaseStateMachine:
    @staticmethod
    def can_transition(
        current_state: CaseState,
        target_state: CaseState,
        is_owner: bool = False,
        actor_role: str = "system",
    ) -> bool:
        if target_state not in ALLOWED_TRANSITIONS.get(current_state, set()):
            return False

        # Hard Gate: Only authenticated owner session can approve
        if target_state == CaseState.APPROVED:
            if not is_owner or actor_role.lower() not in {"owner", "reviewer"}:
                return False

        return True

    @staticmethod
    def transition(
        current_state: CaseState,
        target_state: CaseState,
        case_id: str,
        owner_id: str,
        is_owner: bool = False,
        actor_role: str = "system",
        snapshot_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        producer: str = "application-api",
        payload: Optional[Dict[str, Any]] = None,
    ) -> EventEnvelope:
        if not CaseStateMachine.can_transition(
            current_state=current_state,
            target_state=target_state,
            is_owner=is_owner,
            actor_role=actor_role,
        ):
            if target_state == CaseState.APPROVED and not is_owner:
                raise StateTransitionError(
                    "Hard gate violation: Automation, background workers, or non-owner sessions cannot approve a case. Only authenticated owner-reviewer can approve."
                )
            raise StateTransitionError(
                f"Invalid state transition from '{current_state.value}' to '{target_state.value}'"
            )

        # Determine domain event type
        event_type_map = {
            CaseState.INGESTING: "document.ingesting",
            CaseState.OCR_READY: "ocr.completed",
            CaseState.FACTS_READY: "extraction.completed",
            CaseState.CANDIDATES_READY: "candidates.generated",
            CaseState.VALIDATED: "validation.completed",
            CaseState.REVIEW_REQUIRED: "review.requested",
            CaseState.APPROVED: "review.decided",
            CaseState.EXPORTED: "export.completed",
        }

        event_type = event_type_map.get(target_state, f"case.{target_state.value}")

        return EventEnvelope(
            event_type=event_type,
            owner_id=owner_id,
            case_id=case_id,
            snapshot_id=snapshot_id,
            correlation_id=correlation_id or str(uuid.uuid4()),
            producer=producer,
            payload=payload or {"from_state": current_state.value, "to_state": target_state.value},
        )

    @staticmethod
    def invalidate_approval(
        current_state: CaseState,
        case_id: str,
        owner_id: str,
        reason: str,
        snapshot_id: Optional[str] = None,
    ) -> EventEnvelope:
        """Approval is invalidated by material edits (e.g. source document update or candidate changes)."""
        return EventEnvelope(
            event_type="approval.invalidated",
            owner_id=owner_id,
            case_id=case_id,
            snapshot_id=snapshot_id,
            producer="application-api",
            payload={"reason": reason, "previous_state": current_state.value},
        )
