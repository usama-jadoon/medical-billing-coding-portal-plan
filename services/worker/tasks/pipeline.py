from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from services.api.db.models import (
    Encounter, Document, DocumentPage, Evidence,
    ClinicalFact, CodeCandidate, RuleResult, AuditEvent, candidate_evidence
)
from services.api.storage import get_storage
from services.ocr import get_ocr_provider
from services.extraction import get_fact_extractor
from services.coding_engine import get_coding_engine
from services.api.utils.logging import audit_logger


async def run_encounter_pipeline(encounter_id: str, document_id: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Executes the end-to-end processing pipeline for an encounter:
    1. Read document from storage
    2. OCR document pages
    3. Extract clinical facts with traceable evidence spans
    4. Propose coding candidates via coding engine
    5. Evaluate deterministic validation rules
    6. Transition encounter status to 'review'
    7. Record immutable audit events
    """
    # 1. Fetch encounter and document
    enc_stmt = select(Encounter).where(Encounter.id == encounter_id)
    enc_res = await db.execute(enc_stmt)
    encounter = enc_res.scalar_one_or_none()
    if not encounter:
        raise ValueError(f"Encounter not found: {encounter_id}")

    doc_stmt = select(Document).where(Document.id == document_id)
    doc_res = await db.execute(doc_stmt)
    document = doc_res.scalar_one_or_none()
    if not document:
        raise ValueError(f"Document not found: {document_id}")

    encounter.status = "processing"
    await db.commit()

    # 2. Retrieve document content
    storage = get_storage()
    doc_bytes = await storage.get_file(document.object_key)

    # 3. OCR
    ocr_provider = get_ocr_provider()
    ocr_result = await ocr_provider.process(doc_bytes, document.filename)

    document.page_count = len(ocr_result.pages)

    # Persist pages
    for page in ocr_result.pages:
        db_page = DocumentPage(
            document_id=document.id,
            page_number=page.page_number,
            ocr_text=page.text,
            ocr_engine=ocr_result.ocr_engine,
            ocr_version=ocr_result.ocr_version,
        )
        db.add(db_page)

    await db.flush()

    # 4. Extract Clinical Facts
    fact_extractor = get_fact_extractor()
    extraction_res = await fact_extractor.extract(
        document_id=document.id,
        pages=ocr_result.pages,
        domain=encounter.coding_domain,
    )

    # Persist Evidence and Facts
    created_facts: List[Dict[str, Any]] = []
    evidence_cache: Dict[str, Evidence] = {}

    for ef in extraction_res.facts:
        db_evidence = None
        if ef.evidence:
            ev_key = f"{ef.evidence.page_number}_{ef.evidence.start_offset}_{ef.evidence.end_offset}"
            if ev_key not in evidence_cache:
                db_evidence = Evidence(
                    document_id=document.id,
                    page_number=ef.evidence.page_number,
                    start_offset=ef.evidence.start_offset,
                    end_offset=ef.evidence.end_offset,
                    quoted_text=ef.evidence.quoted_text,
                    evidence_type=ef.evidence.evidence_type,
                )
                db.add(db_evidence)
                await db.flush()
                evidence_cache[ev_key] = db_evidence
            else:
                db_evidence = evidence_cache[ev_key]

        db_fact = ClinicalFact(
            encounter_id=encounter.id,
            fact_type=ef.fact_type,
            value_json=ef.value,
            evidence_id=db_evidence.id if db_evidence else None,
            extraction_model="deterministic",
            extraction_version="1.0",
        )
        db.add(db_fact)
        await db.flush()

        fact_dict = {
            "id": db_fact.id,
            "fact_type": db_fact.fact_type,
            "value": db_fact.value_json,
            "evidence": {
                "id": db_evidence.id,
                "document_id": db_evidence.document_id,
                "page_number": db_evidence.page_number,
                "start_offset": db_evidence.start_offset,
                "end_offset": db_evidence.end_offset,
                "quoted_text": db_evidence.quoted_text,
                "evidence_type": db_evidence.evidence_type,
            } if db_evidence else None
        }
        created_facts.append(fact_dict)

    # 5. Coding Engine: Generate Candidates & Validate Rules
    coding_engine = get_coding_engine()
    candidates_data = await coding_engine.generate_candidates(
        domain=encounter.coding_domain,
        service_date=encounter.service_date,
        place_of_service=encounter.place_of_service,
        facts=created_facts,
    )

    # Persist Candidates, rule results, and candidate_evidence
    for cand in candidates_data:
        db_candidate = CodeCandidate(
            encounter_id=encounter.id,
            code_system=cand["code_system"],
            code=cand["code"],
            code_version=cand["code_version"],
            status="candidate",
            rationale=cand["rationale"],
            human_review_required=cand["human_review_required"],
        )
        db.add(db_candidate)
        await db.flush()

        # Link supporting evidence
        for ev_data in cand.get("supporting_evidence", []):
            ev_id = ev_data.get("id")
            if ev_id:
                stmt_link = candidate_evidence.insert().values(
                    candidate_id=db_candidate.id,
                    evidence_id=ev_id,
                )
                await db.execute(stmt_link)

        # Persist Rule Results
        for rr in cand.get("rule_results", []):
            db_rr = RuleResult(
                candidate_id=db_candidate.id,
                rule_id=rr["rule_id"],
                status=rr["status"],
                message=rr["message"],
                source_reference=rr["source_reference"],
            )
            db.add(db_rr)

    # 6. Mark Encounter Status as Ready for Review
    encounter.status = "review"

    # 7. Audit Event
    audit = AuditEvent(
        organization_id=encounter.organization_id,
        actor_id="system_pipeline",
        event_type="pipeline_processed",
        entity_type="encounter",
        entity_id=encounter.id,
        metadata_json={
            "document_id": document.id,
            "page_count": len(ocr_result.pages),
            "candidate_count": len(candidates_data),
            "fact_count": len(created_facts),
        },
    )
    db.add(audit)
    await db.commit()

    audit_logger.log(
        level="info",
        action="PIPELINE_COMPLETE",
        organization_id=encounter.organization_id,
        status="success",
        metadata={
            "encounter_id": encounter.id,
            "document_id": document.id,
            "candidates": len(candidates_data),
        },
    )

    return {
        "status": "success",
        "encounter_id": encounter.id,
        "candidates_count": len(candidates_data),
        "facts_count": len(created_facts),
    }
