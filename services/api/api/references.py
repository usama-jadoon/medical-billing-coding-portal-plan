from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy import select
from services.api.db.session import get_db
from services.api.db.models.references import CMSCoverageSnapshot
from services.api.security.tenant import get_current_user
from typing import List, Dict, Any

router = APIRouter(prefix="/references", tags=["references"])


@router.get('/cms-status', dependencies=[Depends(get_current_user)])
async def cms_status(db=Depends(get_db)):
    row = (await db.execute(select(CMSCoverageSnapshot).order_by(CMSCoverageSnapshot.completed_at.desc()).limit(1))).scalar_one_or_none()
    if not row:
        return {'status': 'unavailable', 'records': 0}
    return {'status': 'available', 'last_synced_at': row.completed_at.isoformat(),
            'records': len(row.records_json), 'scope': row.scope_json, 'sha256': row.sha256,
            'usage': 'Reference metadata only; does not establish coverage or medical necessity.'}

OFFICIAL_REFERENCES: List[Dict[str, Any]] = [
    {
        "id": "ref-cms-main",
        "category": "Government",
        "name": "Centers for Medicare & Medicaid Services (CMS)",
        "code_system": "General / Cross-System",
        "version": "Current Guidelines",
        "effective_date": "2026-01-01",
        "last_verified": "2026-09-20",
        "official_url": "https://www.cms.gov/",
        "is_official": True,
        "notes": "Official US government agency governing Medicare regulations, claims standards, and covered entity guidelines.",
    },
    {
        "id": "ref-cdc-icd10",
        "category": "Government",
        "name": "CDC / NCHS ICD-10-CM Files & Official Guidelines",
        "code_system": "ICD-10-CM",
        "version": "FY2026 / FY2027",
        "effective_date": "2025-10-01",
        "last_verified": "2026-09-20",
        "official_url": "https://www.cdc.gov/nchs/icd/icd-10-cm/files.html",
        "is_official": True,
        "notes": "Official release of tabular list, index, and coding guidelines for diagnostic reporting.",
    },
    {
        "id": "ref-cms-ncci",
        "category": "Government",
        "name": "CMS Medicare NCCI Policy Manual & Edits",
        "code_system": "NCCI / PTP / MUE",
        "version": "2026 Edition",
        "effective_date": "2026-01-01",
        "last_verified": "2026-09-20",
        "official_url": "https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-policy-manual",
        "is_official": True,
        "notes": "National Correct Coding Initiative policy manual defining procedure-to-procedure bundling and modifier rules.",
    },
    {
        "id": "ref-ama-cpt",
        "category": "Code-set owner",
        "name": "American Medical Association (AMA) CPT Code Set Basics",
        "code_system": "CPT",
        "version": "CY2026 Guidelines",
        "effective_date": "2026-01-01",
        "last_verified": "2026-09-20",
        "official_url": "https://www.ama-assn.org/practice-management/cpt/cpt-code-set-basics-and-resources",
        "is_official": True,
        "notes": "Official copyright holder and licensing authority for Current Procedural Terminology (CPT).",
    },
    {
        "id": "ref-ada-cdt",
        "category": "Code-set owner",
        "name": "American Dental Association (ADA) Code on Dental Procedures",
        "code_system": "CDT",
        "version": "CDT 2026",
        "effective_date": "2026-01-01",
        "last_verified": "2026-09-20",
        "official_url": "https://www.ada.org/publications/cdt",
        "is_official": True,
        "notes": "Official copyright owner for Current Dental Terminology. Maintained as an isolated code set.",
    },
]


@router.get("", response_model=List[Dict[str, Any]])
async def get_reference_sources():
    return OFFICIAL_REFERENCES
