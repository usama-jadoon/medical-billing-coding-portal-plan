import io
import csv
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from services.api.db.session import get_db
from services.api.db.models import Encounter, CodeCandidate, Review, AuditEvent
from services.api.security.tenant import get_current_tenant
from services.api.utils.logging import audit_logger

router = APIRouter(prefix="/exports", tags=["exports"])


async def _get_encounter_for_export(encounter_id: str, tenant_id: str, db: AsyncSession) -> Encounter:
    stmt = (
        select(Encounter)
        .where(Encounter.id == encounter_id, Encounter.organization_id == tenant_id)
        .options(
            selectinload(Encounter.patient),
            selectinload(Encounter.code_candidates).selectinload(CodeCandidate.supporting_evidence),
            selectinload(Encounter.code_candidates).selectinload(CodeCandidate.rule_results),
            selectinload(Encounter.reviews).selectinload(Review.reviewer),
        )
    )
    res = await db.execute(stmt)
    encounter = res.scalar_one_or_none()
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encounter not found for your organization.",
        )
    return encounter


@router.get("/encounter/{encounter_id}/json")
async def export_json(
    encounter_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
):
    encounter = await _get_encounter_for_export(encounter_id, tenant_id, db)

    # Record export audit
    audit = AuditEvent(
        organization_id=tenant_id,
        actor_id="exporter",
        event_type="encounter_exported_json",
        entity_type="encounter",
        entity_id=encounter.id,
        metadata_json={"export_format": "JSON"},
    )
    db.add(audit)
    await db.commit()

    export_data = {
        "export_timestamp": datetime.now(timezone.utc).isoformat(),
        "encounter_id": encounter.id,
        "patient_reference": encounter.patient.external_reference if encounter.patient else "",
        "service_date": encounter.service_date,
        "coding_domain": encounter.coding_domain,
        "place_of_service": encounter.place_of_service,
        "status": encounter.status,
        "codes": [
            {
                "code_system": c.code_system,
                "code": c.code,
                "code_version": c.code_version,
                "status": c.status,
                "rationale": c.rationale,
                "evidence_snippets": [ev.quoted_text for ev in c.supporting_evidence],
                "rules": [
                    {"rule_id": r.rule_id, "status": r.status, "message": r.message}
                    for r in c.rule_results
                ],
            }
            for c in encounter.code_candidates
        ],
        "reviews": [
            {
                "reviewer": r.reviewer.email if r.reviewer else "",
                "decision": r.decision,
                "notes": r.notes,
                "timestamp": r.created_at.isoformat(),
            }
            for r in encounter.reviews
        ],
    }

    return JSONResponse(
        content=export_data,
        headers={"Content-Disposition": f'attachment; filename="coding_export_{encounter.id}.json"'},
    )


@router.get("/encounter/{encounter_id}/csv")
async def export_csv(
    encounter_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
):
    encounter = await _get_encounter_for_export(encounter_id, tenant_id, db)

    # Record export audit
    audit = AuditEvent(
        organization_id=tenant_id,
        actor_id="exporter",
        event_type="encounter_exported_csv",
        entity_type="encounter",
        entity_id=encounter.id,
        metadata_json={"export_format": "CSV"},
    )
    db.add(audit)
    await db.commit()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "EncounterID", "PatientReference", "ServiceDate", "CodingDomain",
        "PlaceOfService", "Status", "CodeSystem", "Code", "CodeVersion",
        "CodeStatus", "Rationale", "SupportingEvidenceCount"
    ])

    for c in encounter.code_candidates:
        writer.writerow([
            encounter.id,
            encounter.patient.external_reference if encounter.patient else "",
            encounter.service_date,
            encounter.coding_domain,
            encounter.place_of_service,
            encounter.status,
            c.code_system,
            c.code,
            c.code_version,
            c.status,
            c.rationale,
            len(c.supporting_evidence),
        ])

    csv_bytes = output.getvalue().encode("utf-8")
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="coding_worksheet_{encounter.id}.csv"'},
    )


@router.get("/encounter/{encounter_id}/worksheet")
async def export_worksheet_html(
    encounter_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
):
    encounter = await _get_encounter_for_export(encounter_id, tenant_id, db)

    latest_review = encounter.reviews[-1] if encounter.reviews else None

    # Construct clean printable HTML worksheet
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Medical Coding Worksheet - {encounter.id}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.5; padding: 40px; color: #1e293b; }}
        .header {{ border-bottom: 2px solid #0284c7; padding-bottom: 16px; margin-bottom: 24px; }}
        h1 {{ margin: 0 0 8px 0; font-size: 24px; color: #0f172a; }}
        .meta-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }}
        .meta-item {{ background: #f8fafc; padding: 12px; border-radius: 6px; border: 1px solid #e2e8f0; }}
        .meta-label {{ font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600; }}
        .meta-value {{ font-size: 14px; font-weight: 600; margin-top: 4px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        th, td {{ border: 1px solid #cbd5e1; padding: 10px 12px; text-align: left; font-size: 13px; }}
        th {{ background: #f1f5f9; font-weight: 600; color: #334155; }}
        .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
        .badge-pass {{ background: #dcfce7; color: #15803d; }}
        .badge-warn {{ background: #fef9c3; color: #854d0e; }}
        .footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #64748b; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Official Medical Coding Worksheet</h1>
        <div>Medical Billing &amp; Coding Portal &bull; Human-Reviewed US Coding Verification</div>
    </div>

    <div class="meta-grid">
        <div class="meta-item">
            <div class="meta-label">Patient Pseudonymous ID</div>
            <div class="meta-value">{encounter.patient.external_reference if encounter.patient else 'N/A'}</div>
        </div>
        <div class="meta-item">
            <div class="meta-label">Date of Service</div>
            <div class="meta-value">{encounter.service_date}</div>
        </div>
        <div class="meta-item">
            <div class="meta-label">Coding Domain</div>
            <div class="meta-value">{encounter.coding_domain.replace('_', ' ').title()}</div>
        </div>
        <div class="meta-item">
            <div class="meta-label">Place of Service</div>
            <div class="meta-value">{encounter.place_of_service}</div>
        </div>
        <div class="meta-item">
            <div class="meta-label">Encounter Status</div>
            <div class="meta-value">{encounter.status.upper()}</div>
        </div>
        <div class="meta-item">
            <div class="meta-label">Final Reviewer</div>
            <div class="meta-value">{latest_review.reviewer.email if latest_review and latest_review.reviewer else 'Pending Review'}</div>
        </div>
    </div>

    <h2>Verified Coding Recommendations</h2>
    <table>
        <thead>
            <tr>
                <th>Code System</th>
                <th>Code</th>
                <th>Version</th>
                <th>Status</th>
                <th>Rationale</th>
                <th>Evidence Items</th>
            </tr>
        </thead>
        <tbody>
"""

    for c in encounter.code_candidates:
        evidence_text = "<br>".join([f"&bull; <i>{ev.quoted_text}</i> (p. {ev.page_number})" for ev in c.supporting_evidence])
        html += f"""
            <tr>
                <td><strong>{c.code_system}</strong></td>
                <td><span style="font-family: monospace; font-size: 14px; font-weight: bold;">{c.code}</span></td>
                <td>{c.code_version}</td>
                <td><span class="badge badge-pass">{c.status.upper()}</span></td>
                <td>{c.rationale}</td>
                <td>{evidence_text or 'Documented in record'}</td>
            </tr>
        """

    html += f"""
        </tbody>
    </table>

    <div class="footer">
        Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} &bull; Encounter ID: {encounter.id} &bull; Immutable Audit Record Attached
    </div>
</body>
</html>
"""

    return Response(
        content=html.encode("utf-8"),
        media_type="text/html",
        headers={"Content-Disposition": f'inline; filename="coding_worksheet_{encounter.id}.html"'},
    )
