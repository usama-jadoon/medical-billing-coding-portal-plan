"""One approval policy shared by review and every export route."""
import hashlib
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from services.api.db.models import CaseSnapshot, ClinicalFact, CodeCandidate, Document, DocumentPage
from services.rules_engine import get_validation_pipeline
from services.api.storage import get_storage
from services.coding_engine import get_coding_engine


async def validate_selection(db, case, candidate_ids, accepted_modifiers=None):
    ids = set(candidate_ids)
    if not ids:
        raise HTTPException(400, "Approval blocked: Select at least one supported candidate.")
    snapshot = await db.get(CaseSnapshot, case.active_snapshot_id) if case.active_snapshot_id else None
    if not snapshot or snapshot.case_id != case.id or not snapshot.source_document_version_id:
        raise HTTPException(400, "Approval blocked: A completed source analysis is required.")
    document = await db.get(Document, snapshot.source_document_version_id)
    if not document or document.encounter_id != case.id:
        raise HTTPException(400, "Approval blocked: Source document does not belong to this case.")
    if hashlib.sha256(await get_storage().get_file(document.object_key)).hexdigest() != document.sha256:
        raise HTTPException(400, "Approval blocked: Stored source hash does not match the document version.")
    specialty = case.coding_domain in {'behavioral_health', 'dme'}
    bundle = ('specialty-demo-2', 'specialty-catalog-2026-v1') if specialty else ('demo-1', 'sample-catalog-1')
    if (snapshot.ruleset_version, snapshot.provenance_json.get('catalog')) != bundle:
        raise HTTPException(400, "Approval blocked: Pinned policy bundle is unavailable.")
    candidates = (await db.execute(select(CodeCandidate).where(
        CodeCandidate.encounter_id == case.id, CodeCandidate.snapshot_id == snapshot.id,
        CodeCandidate.id.in_(ids),
    ).options(selectinload(CodeCandidate.supporting_evidence), selectinload(CodeCandidate.rule_results)))).scalars().all()
    if {c.id for c in candidates} != ids:
        raise HTTPException(400, "Approval blocked: Candidate IDs must belong to the current snapshot.")
    pages = (await db.execute(select(DocumentPage).where(DocumentPage.document_id == document.id))).scalars().all()
    text_by_page = {p.page_number: p.ocr_text for p in pages}
    facts = (await db.execute(select(ClinicalFact).where(
        ClinicalFact.encounter_id == case.id, ClinicalFact.snapshot_id == snapshot.id,
    ))).scalars().all()
    payload = []
    fact_payload = []
    # Retrieval is rerun from the pinned facts; changing a code cannot reuse arbitrary evidence.
    from services.api.db.models import Evidence
    for fact in facts:
        ev = await db.get(Evidence, fact.evidence_id) if fact.evidence_id else None
        fact_payload.append({"fact_type": fact.fact_type, "value": fact.value_json,
                             "evidence": {"id": ev.id, "quoted_text": ev.quoted_text} if ev else None})
    if specialty:
        from services.extraction.specialty_extractor import extract_specialty
        from services.ocr.base import OCRPage
        extracted = extract_specialty(document.id, [OCRPage(page_number=p.page_number, text=p.ocr_text) for p in pages], case.coding_domain)
        expected = {(f.evidence.page_number, f.evidence.start_offset, f.evidence.end_offset, str(f.value)) for f in extracted}
        actual = set()
        for fact in facts:
            if fact.fact_type != case.coding_domain:
                continue
            ev = await db.get(Evidence, fact.evidence_id) if fact.evidence_id else None
            if not ev or ev.document_id != document.id:
                raise HTTPException(400, 'Approval blocked: Specialty field has no pinned evidence.')
            actual.add((ev.page_number, ev.start_offset, ev.end_offset, str(fact.value_json)))
        if actual != expected:
            raise HTTPException(400, 'Approval blocked: Specialty facts differ from independently extracted source fields.')
    proposals = await get_coding_engine().generate_candidates(
        domain=case.coding_domain, service_date=case.service_date,
        place_of_service=case.place_of_service, facts=fact_payload,
    )
    for candidate in candidates:
        matching = next((p for p in proposals if p['code'] == candidate.code and p['code_system'] == candidate.code_system and p['code_version'] == candidate.code_version), None)
        if not matching or not {e.id for e in candidate.supporting_evidence}.issubset({e['id'] for e in matching['supporting_evidence']}):
            raise HTTPException(400, "Approval blocked: Candidate no longer matches the pinned clinical facts.")
        if specialty:
            if {e.id for e in candidate.supporting_evidence} != {e['id'] for e in matching['supporting_evidence']}:
                raise HTTPException(400, 'Approval blocked: Specialty candidate must retain all field evidence.')
            proposed = matching.get('proposed_modifiers', [])
            selected = (accepted_modifiers or {}).get(candidate.id, [])
            if selected != proposed or candidate.modifiers_json != proposed:
                raise HTTPException(400, 'Approval blocked: Explicit acceptance of the displayed deterministic modifiers is required.')
        evidence = []
        for ev in candidate.supporting_evidence:
            text = text_by_page.get(ev.page_number, "")
            if (ev.document_id != document.id or not ev.quoted_text
                or not 0 <= ev.start_offset < ev.end_offset <= len(text)
                or text[ev.start_offset:ev.end_offset] != ev.quoted_text
                or ev.quote_hash != hashlib.sha256(ev.quoted_text.encode()).hexdigest()
                or ev.evidence_role != "SUPPORT"):
                raise HTTPException(400, "Approval blocked: Evidence cannot be resolved to the pinned source.")
            evidence.append({"id": ev.id, "quoted_text": ev.quoted_text})
        if any(r.status == "FAIL" for r in candidate.rule_results):
            raise HTTPException(400, "Approval blocked: Selected candidate has a failed deterministic rule.")
        payload.append({"code": candidate.code, "code_system": candidate.code_system,
                        "code_version": candidate.code_version, "supporting_evidence": evidence})
    from services.worker.sync.validation import catalog_findings
    reference_findings = await catalog_findings(db, payload, case.service_date)
    result = get_validation_pipeline().validate_case(
        domain=case.coding_domain, service_date=case.service_date, place_of_service=case.place_of_service,
        facts=fact_payload, candidates=payload, reference_findings=reference_findings,
    )
    if result.has_blockers:
        messages = [f.message for f in result.findings if f.severity == "BLOCK"]
        raise HTTPException(400, "Approval blocked: " + " ".join(messages))
    return snapshot, candidates


async def validate_export(db, case):
    if case.status not in {"approved", "exported"}:
        raise HTTPException(400, "Export blocked: Only approved cases may be exported.")
    ids = (await db.execute(select(CodeCandidate.id).where(
        CodeCandidate.encounter_id == case.id, CodeCandidate.snapshot_id == case.active_snapshot_id,
        CodeCandidate.status == "approved", CodeCandidate.human_review_required.is_(False),
    ))).scalars().all()
    candidates = (await db.execute(select(CodeCandidate).where(CodeCandidate.id.in_(ids)))).scalars().all()
    return await validate_selection(db, case, ids, {c.id: c.modifiers_json for c in candidates})
