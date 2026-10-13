import io
import csv
from html import escape
from services.api.workflow.approval import validate_export
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from services.api.db.session import get_db
from services.api.db.models import Encounter, CodeCandidate, Review, AuditEvent
from services.api.security.tenant import get_current_tenant
from services.api.security.tenant import get_fresh_user
from services.api.utils.logging import audit_logger
from services.rules_engine.rulesets.er_split_billing import build_split_claim

XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# Column template for the CMS-1500 service-lines sheet. Adjust headers/widths
# here to match the exact CollaborateMD claim entry screen -- the renderer
# reads only these tables, so no other code changes when you tweak them.
CMS1500_LINE_COLUMNS = [
    ("line", "Ln", 6),
    ("dos", "DOS", 12),
    ("code_system", "Type", 10),
    ("code", "CPT/HCPCS", 13),
    ("modifiers", "Mod*", 10),
    ("dx_pointers", "Dx Ptr", 9),
    ("units", "Units", 8),
    ("charge", "Charge", 12),
    ("description", "Description", 44),
]

UB04_LINE_COLUMNS = [
    ("line", "Ln", 6),
    ("revenue_code", "Rev Code (Box 42)", 16),
    ("revenue_description", "Description (Box 43)", 34),
    ("cpt", "CPT/HCPCS (Box 44)", 16),
    ("units", "Units", 8),
    ("description", "Detail", 40),
]

def safe_csv(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


router = APIRouter(prefix="/exports", tags=["exports"], dependencies=[Depends(get_fresh_user)])


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
    await validate_export(db, encounter)
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
            for c in encounter.code_candidates if c.status == "approved" and c.snapshot_id == encounter.active_snapshot_id
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
        if c.status != "approved" or c.snapshot_id != encounter.active_snapshot_id:
            continue
        writer.writerow([safe_csv(value) for value in [
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
        ]])

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
            <div class="meta-value">{escape(encounter.patient.external_reference) if encounter.patient else 'N/A'}</div>
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
        if c.status != "approved" or c.snapshot_id != encounter.active_snapshot_id:
            continue
        evidence_text = "<br>".join([f"&bull; <i>{escape(ev.quoted_text)}</i> (p. {ev.page_number})" for ev in c.supporting_evidence])
        html += f"""
            <tr>
                <td><strong>{c.code_system}</strong></td>
                <td><span style="font-family: monospace; font-size: 14px; font-weight: bold;">{c.code}</span></td>
                <td>{c.code_version}</td>
                <td><span class="badge badge-pass">{c.status.upper()}</span></td>
                <td>{escape(c.rationale)}</td>
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


def _approved_candidates(encounter: Encounter) -> list:
    return [
        c for c in encounter.code_candidates
        if c.status == "approved" and c.snapshot_id == encounter.active_snapshot_id
    ]


def _split_for_encounter(encounter: Encounter) -> dict:
    approved = [
        {"code": c.code, "code_system": c.code_system,
         "description": c.rationale or "",
         "kind": "diagnosis" if c.code_system == "ICD-10-CM" else "procedure"}
        for c in _approved_candidates(encounter)
    ]
    return build_split_claim(approved, {
        "service_date": str(encounter.service_date or ""),
        "place_of_service": encounter.place_of_service or "",
        "domain": encounter.coding_domain or "",
    })


def _render_claim_workbook(encounter: Encounter, split: dict) -> bytes:
    """Dual-sheet CollaborateMD-ready workbook: CMS-1500 + UB-04 + audit."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2F5496")
    title_font = Font(bold=True, size=13, color="1F3864")
    wrap = Alignment(vertical="top", wrap_text=True)

    def start_sheet(title: str):
        ws = wb.active if wb.active.title == "Sheet" else wb.create_sheet()
        ws.title = title
        return ws

    def write_header(ws, row: int, columns) -> None:
        for idx, (_, label, _) in enumerate(columns, start=1):
            cell = ws.cell(row=row, column=idx, value=label)
            cell.font = header_font
            cell.fill = header_fill
        for idx, (_, _, width) in enumerate(columns, start=1):
            ws.column_dimensions[ws.cell(row=row, column=idx).column_letter].width = width
        ws.freeze_panes = ws.cell(row=row + 1, column=1).coordinate
        ws.auto_filter.ref = ws.dimensions

    # --- Sheet 1: CMS-1500 (professional) -------------------------------------
    ws = start_sheet("CMS-1500")
    ws["A1"] = "CMS-1500 Professional Claim Lines"
    ws["A1"].font = title_font
    ws["A2"] = (f"Patient ref: {encounter.patient.external_reference if encounter.patient else 'N/A'}"
                f"   |   DOS: {encounter.service_date}"
                f"   |   POS: {encounter.place_of_service}"
                f"   |   Domain: {(encounter.coding_domain or '').replace('_', ' ')}")
    ws["A4"] = "Box 21 — Diagnosis pointers"
    ws["A4"].font = Font(bold=True)
    dx_cols = [("pointer", "Ptr", 6), ("code", "ICD-10-CM", 14), ("description", "Description", 52)]
    write_header(ws, 5, dx_cols)
    r = 6
    for d in split["diagnoses"]:
        ws.cell(row=r, column=1, value=d["pointer"])
        ws.cell(row=r, column=2, value=d["code"])
        c3 = ws.cell(row=r, column=3, value=d["description"])
        c3.alignment = wrap
        r += 1
    if not split["diagnoses"]:
        ws.cell(row=r, column=1, value="(no approved ICD-10-CM diagnoses)")
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="Box 24 — Service lines").font = Font(bold=True)
    r += 1
    write_header(ws, r, CMS1500_LINE_COLUMNS)
    r += 1
    for line in split["professional"]:
        vals = {
            "line": line["line"], "dos": line["dos"],
            "code_system": line["code_system"], "code": line["code"],
            "modifiers": ",".join(line["modifiers"]),
            "dx_pointers": line["dx_pointers"], "units": line["units"],
            "charge": "", "description": line["description"],
        }
        for idx, (key, _, _) in enumerate(CMS1500_LINE_COLUMNS, start=1):
            cell = ws.cell(row=r, column=idx, value=vals[key])
            cell.alignment = wrap
        r += 1
    if not split["professional"]:
        ws.cell(row=r, column=1,
                value="(no approved CPT/HCPCS lines yet -- add procedure codes or load licensed CPT data)")
        r += 1
    r += 1
    ws.cell(row=r, column=1,
            value="* Mod = suggested modifier -- reviewer must confirm before claim entry.").font = Font(italic=True)

    # --- Sheet 2: UB-04 (institutional) ----------------------------------------
    ws2 = wb.create_sheet("UB-04")
    ws2["A1"] = "UB-04 Institutional Claim Lines"
    ws2["A1"].font = title_font
    ws2["A2"] = (f"Patient ref: {encounter.patient.external_reference if encounter.patient else 'N/A'}"
                 f"   |   DOS: {encounter.service_date}")
    ws2["A4"] = "Box 42/43/44 — Revenue lines"
    ws2["A4"].font = Font(bold=True)
    write_header(ws2, 5, UB04_LINE_COLUMNS)
    r = 6
    for line in split["institutional"]:
        vals = {"line": line["line"], "revenue_code": line["revenue_code"],
                "revenue_description": line["revenue_description"],
                "cpt": line["cpt"], "units": line["units"],
                "description": line["description"]}
        for idx, (key, _, _) in enumerate(UB04_LINE_COLUMNS, start=1):
            cell = ws2.cell(row=r, column=idx, value=vals[key])
            cell.alignment = wrap
        r += 1
    if not split["institutional"]:
        ws2.cell(row=r, column=1,
                 value="(no institutional lines derived -- facility revenue data not present)")
        r += 1
    r += 1
    ws2.cell(row=r, column=1, value="Box 67 — Principal diagnosis").font = Font(bold=True)
    r += 1
    if split["diagnoses"]:
        d0 = split["diagnoses"][0]
        ws2.cell(row=r, column=1, value=f"{d0['pointer']}: {d0['code']} -- {d0['description']}")
    else:
        ws2.cell(row=r, column=1, value="(none)")

    # --- Sheet 3: audit ---------------------------------------------------------
    ws3 = wb.create_sheet("Audit")
    for idx, label in enumerate(["Field", "Value"], start=1):
        cell = ws3.cell(row=1, column=idx, value=label)
        cell.font = header_font
        cell.fill = header_fill
    ws3.column_dimensions["A"].width = 26
    ws3.column_dimensions["B"].width = 70
    latest = encounter.reviews[-1] if encounter.reviews else None
    rows = [
        ("Encounter ID", encounter.id),
        ("Status", encounter.status),
        ("Reviewer", latest.reviewer.email if latest and latest.reviewer else "Pending"),
        ("Ruleset", f"{split['ruleset']} v{split['ruleset_version']}"),
        ("Exported at (UTC)", datetime.now(timezone.utc).isoformat()),
        ("Professional lines", len(split["professional"])),
        ("Institutional lines", len(split["institutional"])),
    ]
    for i, (k, v) in enumerate(rows, start=2):
        ws3.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws3.cell(row=i, column=2, value=str(v))

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@router.get("/encounter/{encounter_id}/claim-lines")
async def claim_lines(
    encounter_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
):
    """Split-billing preview for the review UI: professional + institutional lines."""
    encounter = await _get_encounter_for_export(encounter_id, tenant_id, db)
    return _split_for_encounter(encounter)


@router.get("/encounter/{encounter_id}/xlsx")
async def export_xlsx(
    encounter_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
):
    encounter = await _get_encounter_for_export(encounter_id, tenant_id, db)

    audit = AuditEvent(
        organization_id=tenant_id,
        actor_id="exporter",
        event_type="encounter_exported_xlsx",
        entity_type="encounter",
        entity_id=encounter.id,
        metadata_json={"export_format": "XLSX"},
    )
    db.add(audit)
    await db.commit()

    split = _split_for_encounter(encounter)
    content = _render_claim_workbook(encounter, split)
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="collaboratemd_claim_{encounter.id}.xlsx"'},
    )
