import pytest
from services.api.workflow.state_machine import (
    CaseStateMachine, CaseState, StateTransitionError
)


def test_state_machine_valid_progression():
    # Progress from CREATED to REVIEW_REQUIRED
    states = [
        (CaseState.CREATED, CaseState.INGESTING),
        (CaseState.INGESTING, CaseState.OCR_READY),
        (CaseState.OCR_READY, CaseState.FACTS_READY),
        (CaseState.FACTS_READY, CaseState.CANDIDATES_READY),
        (CaseState.CANDIDATES_READY, CaseState.VALIDATED),
        (CaseState.VALIDATED, CaseState.REVIEW_REQUIRED),
    ]
    for current, nxt in states:
        assert CaseStateMachine.can_transition(current, nxt, is_owner=False)
        envelope = CaseStateMachine.transition(
            current_state=current,
            target_state=nxt,
            case_id="case-123",
            owner_id="owner-456",
            is_owner=False,
        )
        assert envelope.case_id == "case-123"
        assert envelope.owner_id == "owner-456"


def test_state_machine_hard_gate_owner_approval():
    # Automated worker or non-owner CANNOT approve
    assert not CaseStateMachine.can_transition(
        CaseState.REVIEW_REQUIRED,
        CaseState.APPROVED,
        is_owner=False,
        actor_role="worker",
    )

    with pytest.raises(StateTransitionError) as exc_info:
        CaseStateMachine.transition(
            current_state=CaseState.REVIEW_REQUIRED,
            target_state=CaseState.APPROVED,
            case_id="case-123",
            owner_id="owner-456",
            is_owner=False,
            actor_role="worker",
        )
    assert "Hard gate violation" in str(exc_info.value)

    # Authenticated Owner CAN approve
    assert CaseStateMachine.can_transition(
        CaseState.REVIEW_REQUIRED,
        CaseState.APPROVED,
        is_owner=True,
        actor_role="Owner",
    )

    envelope = CaseStateMachine.transition(
        current_state=CaseState.REVIEW_REQUIRED,
        target_state=CaseState.APPROVED,
        case_id="case-123",
        owner_id="owner-456",
        is_owner=True,
        actor_role="Owner",
    )
    assert envelope.event_type == "review.decided"


def test_state_machine_invalidation_on_material_edit():
    # Approval invalidated by material change
    invalidation_event = CaseStateMachine.invalidate_approval(
        current_state=CaseState.APPROVED,
        case_id="case-123",
        owner_id="owner-456",
        reason="Source document re-uploaded with amendment",
    )
    assert invalidation_event.event_type == "approval.invalidated"
    assert invalidation_event.payload["reason"] == "Source document re-uploaded with amendment"
