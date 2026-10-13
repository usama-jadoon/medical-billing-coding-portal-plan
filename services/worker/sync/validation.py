"""Local-only service-date checks shared by analysis, approval, and export."""
from datetime import date, datetime, timedelta, timezone
import json
from sqlalchemy import select
from services.api.config import settings
from services.api.db.models.references import CatalogSyncRun, MedicalCodeCatalog
from services.rules_engine.validator import ValidationFindingDto


def validate_dated_codes(candidates, service_date, rows):
    findings = []
    try:
        dos = date.fromisoformat(service_date)
    except (ValueError, TypeError):
        return [ValidationFindingDto(stage='2_effective_date', severity='BLOCK', rule_id='LIVE-CATALOG-DATE', message='Service date is unavailable or malformed.')]
    for candidate in candidates:
        code = candidate['code']
        versions = [r for r in rows if r.code == code and r.code_system == candidate['code_system']]
        valid = [r for r in versions if r.effective_from <= dos and (r.effective_to is None or dos < r.effective_to)]
        message = None
        # is_active reflects current provider status; dates control historical DOS.
        if len(valid) > 1:
            message = f'Code {code} has ambiguous dated catalog versions. Review is unavailable.'
        elif not valid:
            expired = [r for r in versions if r.effective_to and dos >= r.effective_to]
            if expired:
                row = max(expired, key=lambda r: r.effective_to)
                message = f'Code {code} was deleted/expired as of {row.effective_to}. Review suggested replacement: {row.replacement_code or "Unavailable"}.'
            else:
                message = f'Code {code} is unavailable in the synchronized catalog for service date {service_date}.'
        if message:
            findings.append(ValidationFindingDto(stage='2_effective_date', severity='BLOCK', rule_id='LIVE-CATALOG-VALIDITY', message=message, candidate_code=code))
    return findings


async def catalog_findings(db, candidates, service_date):
    if not settings.POLICY_SYNC_ENABLED:
        return []
    run = (await db.execute(select(CatalogSyncRun).order_by(CatalogSyncRun.sync_date.desc()).limit(1))).scalar_one_or_none()
    timestamp = run.completed_at.replace(tzinfo=timezone.utc) if run and run.completed_at.tzinfo is None else (run.completed_at if run else None)
    if not timestamp or datetime.now(timezone.utc) - timestamp > timedelta(hours=settings.POLICY_CACHE_TTL_HOURS):
        return [ValidationFindingDto(stage='1_catalog', severity='BLOCK', rule_id='LIVE-CATALOG-UNAVAILABLE', message='Synchronized code validity is unavailable or stale. Review and export are blocked.')]
    try:
        expected = {'provider': settings.MCA_CODE_API_PROVIDER,
                    'payer_sources': [p['name'] for p in json.loads(settings.PAYER_POLICY_FEEDS_JSON)],
                    'cms_scope': {k: v for k, v in {'contractor_id': settings.CMS_CONTRACTOR_ID, 'state_id': settings.CMS_STATE_ID}.items() if v is not None}}
        if any(run.manifest_json.get(k) != v for k, v in expected.items()):
            raise ValueError('Feed configuration changed')
    except (ValueError, KeyError, TypeError):
        return [ValidationFindingDto(stage='1_catalog', severity='BLOCK', rule_id='LIVE-CATALOG-CONFIGURATION', message='Current feed configuration has no matching synchronized batch.')]
    rows = (await db.execute(select(MedicalCodeCatalog).where(MedicalCodeCatalog.sync_run_id == run.id,
             MedicalCodeCatalog.code.in_({c['code'] for c in candidates})))).scalars().all()
    return validate_dated_codes(candidates, service_date, rows)
