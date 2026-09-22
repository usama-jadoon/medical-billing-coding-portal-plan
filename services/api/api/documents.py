import hashlib
import uuid
import io
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from services.api.db.session import get_db
from services.api.db.models import Encounter, Document, AuditEvent, User
from services.api.security.tenant import get_current_user, get_current_tenant
from services.api.security.permissions import require_roles, Roles
from services.api.storage import get_storage
from services.worker.tasks.pipeline import run_encounter_pipeline
from services.api.utils.logging import audit_logger

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
    if lower_name.endswith(".txt") or mime_type == "text/plain":
        return

    # Check magic bytes
    signature_matched = False
    for magic, expected_mime in MAGIC_BYTES.items():
        if content.startswith(magic):
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
):
    require_roles([Roles.OWNER, Roles.ADMIN, Roles.CODER, Roles.REVIEWER])(current_user)
    org_id = current_user.organization_id

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

    content = await file.read()
    filename = file.filename or "record.pdf"
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

    # Generate random object key outside web root
    object_key = f"{org_id}/{encounter_id}/{uuid.uuid4().hex}_{filename}"

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
    await db.commit()

    # Execute processing pipeline (OCR -> Extraction -> Coding -> Rules)
    pipeline_result = await run_encounter_pipeline(
        encounter_id=encounter.id,
        document_id=document.id,
        db=db,
    )

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
