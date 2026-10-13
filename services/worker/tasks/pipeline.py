import hashlib
import uuid
import json
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from services.api.db.models import (
    Encounter, Document, DocumentPage, Evidence,
    ClinicalFact, CodeCandidate, RuleResult, AuditEvent, candidate_evidence,
    CaseSnapshot, OutboxEvent, ValidationFinding
)
from services.api.storage import get_storage
from services.ocr import get_ocr_provider
from services.extraction import get_fact_extractor
from services.coding_engine import get_coding_engine
from services.rules_engine import get_validation_pipeline
from services.api.utils.logging import audit_logger
from services.coding_engine.providers.base import CodeSetVersionProvider
from services.api.workflow.state_machine import CaseStateMachine, CaseState


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

    doc_stmt = select(Document).where(Document.id == document_id, Document.encounter_id == encounter.id)
    doc_res = await db.execute(doc_stmt)
    document = doc_res.scalar_one_or_none()
    if not document:
        raise ValueError(f"Document not found: {document_id}")

    if encounter.active_snapshot_id:
        active = await db.get(CaseSnapshot, encounter.active_snapshot_id)
        if active and active.source_document_version_id == document.id:
            return {"status": "success", "encounter_id": encounter.id, "duplicate": True}

    # A new attempt is isolated; earlier facts and decisions remain queryable.
    specialty = encounter.coding_domain in {'behavioral_health', 'dme'}
    catalog_version = 'specialty-catalog-2026-v1' if specialty else 'sample-catalog-1'
    ruleset_version = 'specialty-demo-2' if specialty else 'demo-1'
    snapshot = CaseSnapshot(
        case_id=encounter.id, source_document_version_id=document.id,
        service_date=encounter.service_date, domain_profile=encounter.coding_domain,
        code_system_release=CodeSetVersionProvider.resolve_version('HCPCS' if encounter.coding_domain == 'dme' else 'CPT' if specialty else 'ICD-10-CM', encounter.service_date),
        ruleset_version=ruleset_version,
        provenance_json={"catalog": catalog_version, "ruleset": ruleset_version, "extractor": "specialty-fields-2" if specialty else "deterministic-1", "model": "none", "prompt": "none", "mode": "synthetic-development"},
        snapshot_hash=hashlib.sha256(f"{encounter.id}:{document.sha256}:{encounter.service_date}:{ruleset_version}:{catalog_version}".encode()).hexdigest(),
    )
    db.add(snapshot)
    await db.flush()
    async def advance(state):
        encounter.status = state.value
        db.add(OutboxEvent(event_type={
            CaseState.OCR_READY: "ocr.completed", CaseState.FACTS_READY: "extraction.completed",
            CaseState.CANDIDATES_READY: "candidates.generated", CaseState.VALIDATED: "validation.completed",
        }.get(state, "review.requested"), owner_id=encounter.organization_id,
            case_id=encounter.id, snapshot_id=snapshot.id, producer="processing-worker",
            payload_json={"state": state.value}))
        await db.flush()

    # 2. Retrieve document content
    storage = get_storage()
    doc_bytes = await storage.get_file(document.object_key)
    if hashlib.sha256(doc_bytes).hexdigest() != document.sha256:
        raise ValueError("Source hash mismatch.")

    # 3. OCR
    ocr_provider = get_ocr_provider()
    ocr_result = await ocr_provider.process(doc_bytes, document.filename)
    snapshot.provenance_json = {**snapshot.provenance_json, "ocr_engine": ocr_result.ocr_engine, "ocr_version": ocr_result.ocr_version}
    if not any(page.text.strip() for page in ocr_result.pages):
        raise ValueError("No readable text. Configure a scanned-document OCR provider or upload a searchable PDF.")

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
    await advance(CaseState.OCR_READY)

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
            source_page = next((p for p in ocr_result.pages if p.page_number == ef.evidence.page_number), None)
            if not source_page or source_page.text[ef.evidence.start_offset:ef.evidence.end_offset] != ef.evidence.quoted_text:
                raise ValueError("Extractor returned an unresolved evidence span.")
            ev_key = f"{ef.evidence.page_number}_{ef.evidence.start_offset}_{ef.evidence.end_offset}"
            if ev_key not in evidence_cache:
                q_text = ef.evidence.quoted_text
                q_hash = hashlib.sha256(q_text.encode("utf-8")).hexdigest()
                db_evidence = Evidence(
                    document_id=document.id,
                    page_number=ef.evidence.page_number,
                    start_offset=ef.evidence.start_offset,
                    end_offset=ef.evidence.end_offset,
                    quoted_text=q_text,
                    evidence_type=ef.evidence.evidence_type,
                    region_id=str(uuid.uuid4()),
                    quote_hash=q_hash,
                    evidence_role="SUPPORT",
                )
                db.add(db_evidence)
                await db.flush()
                evidence_cache[ev_key] = db_evidence
            else:
                db_evidence = evidence_cache[ev_key]

        db_fact = ClinicalFact(
            encounter_id=encounter.id,
            snapshot_id=snapshot.id,
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
                "region_id": db_evidence.region_id,
                "bbox": {
                    "x": db_evidence.bbox_x,
                    "y": db_evidence.bbox_y,
                    "width": db_evidence.bbox_w,
                    "height": db_evidence.bbox_h,
                },
                "quote_hash": db_evidence.quote_hash,
                "evidence_role": db_evidence.evidence_role,
            } if db_evidence else None
        }
        created_facts.append(fact_dict)

    await advance(CaseState.FACTS_READY)

    # 5. Coding Engine: Generate Candidates & Validate Rules
    coding_engine = get_coding_engine()
    candidates_data = await coding_engine.generate_candidates(
        domain=encounter.coding_domain,
        service_date=encounter.service_date,
        place_of_service=encounter.place_of_service,
        facts=created_facts,
    )

    created_candidates_db: List[CodeCandidate] = []
    # Persist Candidates, rule results, and candidate_evidence
    for cand in candidates_data:
        db_candidate = CodeCandidate(
            encounter_id=encounter.id,
            snapshot_id=snapshot.id,
            code_system=cand["code_system"],
            code=cand["code"],
            code_version=cand["code_version"],
            status="candidate",
            rationale=cand["rationale"],
            modifiers_json=cand.get('proposed_modifiers', []),
            human_review_required=cand["human_review_required"],
        )
        db.add(db_candidate)
        await db.flush()
        created_candidates_db.append(db_candidate)

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

    await advance(CaseState.CANDIDATES_READY)

    # 6. Execute 8-Stage Deterministic Validation Pipeline
    val_pipeline = get_validation_pipeline()
    from services.worker.sync.validation import catalog_findings
    reference_findings = await catalog_findings(db, candidates_data, encounter.service_date)
    val_result = val_pipeline.validate_case(
        domain=encounter.coding_domain,
        service_date=encounter.service_date,
        place_of_service=encounter.place_of_service,
        facts=created_facts,
        candidates=candidates_data,
        reference_findings=reference_findings,
    )

    for finding in val_result.findings:
        matched_cand = next((c for c in created_candidates_db if c.code == finding.candidate_code), None)
        db_finding = ValidationFinding(
            case_id=encounter.id,
            snapshot_id=snapshot.id,
            candidate_id=matched_cand.id if matched_cand else None,
            stage=finding.stage,
            severity=finding.severity,
            rule_id=finding.rule_id,
            message=finding.message,
            source_reference=finding.source_reference,
        )
        db.add(db_finding)

    await advance(CaseState.VALIDATED)
    snapshot.snapshot_hash = hashlib.sha256(json.dumps({
        "document_sha256": document.sha256, "service_date": encounter.service_date,
        "domain": encounter.coding_domain, "provenance": snapshot.provenance_json,
        "facts": [{"fact_type": f['fact_type'], "value": f['value'], "evidence": {
            k: f['evidence'][k] for k in ('page_number', 'start_offset', 'end_offset', 'quote_hash')
        } if f['evidence'] else None} for f in created_facts],
        "candidates": [{"code": c['code'], "system": c['code_system'], "release": c['code_version'],
                         "rules": c['rule_results']} for c in candidates_data],
        "findings": [f.model_dump() for f in val_result.findings],
    }, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    # 8. Mark Status as Ready for Review & record outbox event
    encounter.active_snapshot_id = snapshot.id
    await advance(CaseState.REVIEW_REQUIRED)

    outbox = OutboxEvent(
        event_type="validation.completed",
        owner_id=encounter.organization_id,
        case_id=encounter.id,
        snapshot_id=snapshot.id,
        producer="coding-worker",
        payload_json={
            "candidates_count": len(candidates_data),
            "findings_count": len(val_result.findings),
            "has_blockers": val_result.has_blockers,
        },
        status="pending",
    )
    db.add(outbox)


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
