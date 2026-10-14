import hashlib
import uuid
from pathlib import Path
from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from services.api.db.session import get_db
from services.api.db.models import Encounter, Document, AuditEvent, User, OutboxEvent
from services.api.security.tenant import get_current_user, get_current_tenant
from services.api.security.permissions import require_roles, Roles
from services.api.storage import get_storage
from services.worker.tasks.pipeline import run_encounter_pipeline
from services.api.utils.logging import audit_logger
from services.api.config import settings

router = APIRouter(prefix="/documents", tags=["documents"])

# Allowed extensions and MIME types
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".txt"}
ALLOWED_MIMES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "text/plain",
}

# Magic byte signatures
MAGIC_BYTES = {
    b"%PDF": "application/pdf",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"II*\x00": "image/tiff",
    b"MM\x00*": "image/tiff",
}

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB


def validate_file_signature(content: bytes, filename: str, mime_type: str) -> None:
    if not content:
        raise HTTPException(400, "Empty files are not accepted.")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
            detail="File exceeds maximum allowed size of 25MB.",
        )

    # Check extension
    lower_name = filename.lower()
    if not any(lower_name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file extension. Allowed formats: PDF, PNG, JPG, TIFF, TXT.",
        )

    # Allow plain text synthetic test files
    if lower_name.endswith(".txt"):
        if mime_type != "text/plain" or b"\x00" in content:
            raise HTTPException(400, "Invalid text document.")
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(400, "Text documents must be UTF-8.")
        return

    # Check magic bytes
    signature_matched = False
    for magic, expected_mime in MAGIC_BYTES.items():
        if content.startswith(magic):
            expected_extensions = {"application/pdf": {".pdf"}, "image/png": {".png"}, "image/jpeg": {".jpg", ".jpeg"}, "image/tiff": {".tif", ".tiff"}}
            if mime_type != expected_mime or Path(lower_name).suffix not in expected_extensions[expected_mime]:
                raise HTTPException(400, "File extension, MIME type and signature must agree.")
            signature_matched = True
            break

    if not signature_matched:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File signature (magic bytes) validation failed. The file format does not match its extension.",
        )


@router.post("/encounter/{encounter_id}/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    encounter_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    force_reanalysis: bool = False,
):
    require_roles([Roles.OWNER, Roles.ADMIN, Roles.CODER, Roles.REVIEWER])(current_user)
    org_id = current_user.organization_id
    actor_id = current_user.id

    # Verify encounter belongs to this organization
    enc_stmt = select(Encounter).where(
        Encounter.id == encounter_id, Encounter.organization_id == org_id
    )
    enc_res = await db.execute(enc_stmt)
    encounter = enc_res.scalar_one_or_none()
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encounter not found for your organization.",
        )

    if encounter.status in {"ingesting", "ocr_ready", "facts_ready", "candidates_ready", "validated"}:
        raise HTTPException(409, "A document is already being processed.")
    content = await file.read(MAX_FILE_SIZE + 1)
    filename = (file.filename or "record.pdf").replace("\\", "/").split("/")[-1]
    filename = "".join(c for c in filename if c.isprintable() and c not in {'"', ';'})[:200]
    content_type = file.content_type or "application/octet-stream"

    # Validation
    validate_file_signature(content, filename, content_type)

    # Malware scanning hook (mock)
    if b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!" in content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malware scanner flagged this file.",
        )

    # Compute SHA-256
    file_sha256 = hashlib.sha256(content).hexdigest()
    existing = (await db.execute(select(Document).where(Document.encounter_id == encounter.id, Document.sha256 == file_sha256))).scalars().first()
    from services.api.db.models import CaseSnapshot
    from services.worker.sync.validation import cms_fingerprint
    current_snapshot = await db.get(CaseSnapshot, encounter.active_snapshot_id) if encounter.active_snapshot_id else None
    current_reference = await run_in_threadpool(cms_fingerprint)
    # Identical bytes still need a new analysis after the reference package changes.
    if not force_reanalysis and existing and current_snapshot and current_snapshot.provenance_json.get('cms_reference') == current_reference:
        return {"id": existing.id, "filename": existing.filename, "sha256": existing.sha256,
                "mime_type": existing.mime_type, "file_size_bytes": existing.file_size_bytes,
                "pipeline_result": {"status": "success", "duplicate": True}}

    # Generate random object key outside web root
    object_key = f"{org_id}/{encounter_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"

    # Store file
    storage = get_storage()
    await storage.save_file(object_key, content, content_type)

    # Create document record
    document = Document(
        organization_id=org_id,
        encounter_id=encounter.id,
        filename=filename,
        object_key=object_key,
        sha256=file_sha256,
        mime_type=content_type,
        file_size_bytes=len(content),
        page_count=0,
    )
    db.add(document)
    await db.flush()

    audit = AuditEvent(
        organization_id=org_id,
        actor_id=current_user.id,
        event_type="document_uploaded",
        entity_type="document",
        entity_id=document.id,
        metadata_json={
            "encounter_id": encounter.id,
            "filename": filename,
            "sha256": file_sha256,
            "size": len(content),
        },
    )
    db.add(audit)
    if encounter.status in {"approved", "exported"}:
        db.add(OutboxEvent(event_type="approval.invalidated", owner_id=current_user.id,
                          case_id=encounter.id, snapshot_id=encounter.active_snapshot_id,
                          producer="application-api", payload_json={"reason": "source_changed"}))
    encounter.status = "ingesting"
    upload_event = OutboxEvent(event_type="document.uploaded", owner_id=current_user.id,
                      case_id=encounter.id, producer="application-api", payload_json={"document_id": document.id})
    db.add(upload_event)
    await db.commit()

    if settings.QUEUE_BACKEND == "outbox":
        return {"id": document.id, "filename": filename, "sha256": file_sha256,
                "mime_type": content_type, "file_size_bytes": len(content),
                "pipeline_result": {"status": "queued"}}

    # Execute processing pipeline (OCR -> Extraction -> Coding -> Rules)
    document_id = document.id
    upload_event_id = upload_event.id
    try:
        pipeline_result = await run_encounter_pipeline(encounter_id=encounter_id, document_id=document_id, db=db)
        upload_event.status = "published"
        await db.commit()
    except Exception:
        await db.rollback()
        encounter = await db.get(Encounter, encounter_id)
        encounter.status = "review_required"
        encounter.active_snapshot_id = None
        failed_event = await db.get(OutboxEvent, upload_event_id)
        failed_event.status = "failed"
        db.add(AuditEvent(organization_id=org_id, actor_id=actor_id,
                         event_type="processing_failed", entity_type="document", entity_id=document_id,
                         metadata_json={"reason": "text_extraction_unavailable"}))
        await db.commit()
        raise HTTPException(422, "Document saved, but text processing failed. Use a searchable PDF or UTF-8 text; image/scanned OCR requires an OCR adapter.")

    return {
        "id": document.id,
        "filename": document.filename,
        "sha256": document.sha256,
        "mime_type": document.mime_type,
        "file_size_bytes": document.file_size_bytes,
        "pipeline_result": pipeline_result,
    }


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
):
    stmt = select(Document).where(
        Document.id == document_id, Document.organization_id == tenant_id
    )
    res = await db.execute(stmt)
    document = res.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found for your organization.",
        )

    storage = get_storage()
    content = await storage.get_file(document.object_key)

    return Response(
        content=content,
        media_type=document.mime_type,
        headers={"Content-Disposition": f'inline; filename="{document.filename}"'},
    )
