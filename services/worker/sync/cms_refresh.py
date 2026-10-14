"""Public CMS policy metadata can refresh without a proprietary code subscription."""
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from services.api.db.models.references import CMSCoverageSnapshot, AuditLog
from services.worker.sync.service import digest
from services.coding_engine.providers.verification_api import VerificationUnavailable


async def refresh_cms(factory, client):
    now = datetime.now(timezone.utc)
    scope_hash = digest(client.scope)
    async with factory() as db:
        existing = await db.scalar(select(CMSCoverageSnapshot.id).where(CMSCoverageSnapshot.sync_date == now.date(), CMSCoverageSnapshot.scope_sha256 == scope_hash))
        await db.rollback()
        if existing:
            return 'CMS_ALREADY_COMPLETED'
        try:
            records = await client.fetch_policies()
            if not records:
                raise VerificationUnavailable('Empty CMS refresh.')
            row = CMSCoverageSnapshot(sync_date=now.date(), scope_sha256=scope_hash,
                scope_json=client.scope, records_json=records, sha256=digest(records))
            db.add(row)
            db.add(AuditLog(event='CMS_POLICY_SYNC_COMPLETED', metadata_json={'scope': client.scope, 'records': len(records), 'sha256': row.sha256}))
            await db.commit()
            return 'CMS_COMPLETED'
        except IntegrityError:
            await db.rollback()
            existing = await db.scalar(select(CMSCoverageSnapshot.id).where(CMSCoverageSnapshot.sync_date == now.date(), CMSCoverageSnapshot.scope_sha256 == scope_hash))
            if existing:
                return 'CMS_ALREADY_COMPLETED'
            raise VerificationUnavailable('CMS snapshot integrity failure; no completion recorded.') from None
        except Exception:
            await db.rollback()
            db.add(AuditLog(event='CMS_POLICY_SYNC_FAILED', metadata_json={'scope': client.scope, 'reason': 'Public CMS refresh failed; previous snapshot retained.'}))
            await db.commit()
            raise VerificationUnavailable('Public CMS policy refresh failed; prior snapshot retained.') from None
