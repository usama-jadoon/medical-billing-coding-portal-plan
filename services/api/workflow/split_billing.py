"""Append-only billing review records tied to the source and coding approval."""
from fastapi import HTTPException
from sqlalchemy import select, desc
from services.api.db.models import AuditEvent, Review, DocumentPage
from services.api.workflow.approval import validate_export
from services.rules_engine.rulesets.er_split_billing import ERSplitBillingEngine, SplitBillingReview


async def resolve_split(db, case, request):
    if case.coding_domain != 'emergency_department' or case.place_of_service != '23':
        raise HTTPException(400, 'Split billing is available only for the ED development profile.')
    snapshot, candidates = await validate_export(db, case)
    if request.snapshot_id != snapshot.id:
        raise HTTPException(409, 'Billing review belongs to an old source snapshot.')
    pages = (await db.execute(select(DocumentPage).where(
        DocumentPage.document_id == snapshot.source_document_version_id))).scalars().all()
    page_text = {page.page_number: page.ocr_text for page in pages}
    for line in request.lines:
        if line.facility_basis:
            span = line.facility_basis
            text = page_text.get(span.page_number, '')
            if not (0 <= span.start_offset < span.end_offset <= len(text)) or text[span.start_offset:span.end_offset] != span.quoted_text:
                raise HTTPException(400, 'Facility resource evidence does not match the pinned source.')
    # validate_export already verified these evidence spans/hashes against original bytes.
    evidence = {ev.id: f'Document {ev.document_id}, page {ev.page_number}: {ev.quoted_text}'
                for c in candidates for ev in c.supporting_evidence}
    try:
        output = ERSplitBillingEngine().process_er_encounter(request, candidates={c.id: c for c in candidates},
            evidence=evidence, service_date=case.service_date, place_of_service=case.place_of_service)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    approval = (await db.execute(select(Review).where(Review.encounter_id == case.id)
                    .order_by(desc(Review.created_at), desc(Review.id)).limit(1))).scalar_one_or_none()
    if not approval or approval.decision != 'accept':
        raise HTTPException(400, 'Current coding approval is unavailable.')
    return output, approval.id


async def get_reviewed_split(db, case):
    event = (await db.execute(select(AuditEvent).where(AuditEvent.entity_id == case.id,
             AuditEvent.organization_id == case.organization_id, AuditEvent.event_type == 'er_split_billing_accepted')
             .order_by(desc(AuditEvent.created_at), desc(AuditEvent.id)).limit(1))).scalar_one_or_none()
    if not event:
        return None
    data = event.metadata_json
    # Never silently reuse billing selections after a new upload or coding decision.
    request = SplitBillingReview.model_validate(data['request'])
    output, approval_id = await resolve_split(db, case, request)
    if data['approval_id'] != approval_id or data['ruleset_version'] != ERSplitBillingEngine.version:
        raise HTTPException(409, 'Billing review is stale. Review the split again before export.')
    return {**output, 'billing_review_id': event.id}
