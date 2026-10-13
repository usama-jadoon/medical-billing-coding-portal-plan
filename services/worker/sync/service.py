"""All-or-nothing immutable daily batches; no automatic coding rule activation."""
import hashlib
import asyncio
import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from services.api.db.models.references import AuditLog, CatalogSyncRun, CoveragePolicyReference, MedicalCodeCatalog
from services.coding_engine.providers.verification_api import VerificationUnavailable


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_catalog(records):
    if not {'CPT', 'HCPCS', 'ICD-10-CM'} <= {r.code_system for r in records}:
        raise VerificationUnavailable('Complete CPT, HCPCS and ICD-10-CM catalogs are required.')
    groups = {}
    for record in records:
        key = (record.code_system, record.code)
        groups.setdefault(key, []).append(record)
    for rows in groups.values():
        rows.sort(key=lambda r: r.effective_date)
        for previous, current in zip(rows, rows[1:]):
            if previous.expiration_date is None or previous.expiration_date > current.effective_date:
                raise VerificationUnavailable('Catalog contains overlapping validity windows.')


async def synchronize(session_factory, codes, cms, payers=(), *, now=None):
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(timezone.utc).date()
    async with session_factory() as db:
        try:
            # Hold one transaction-scoped lock through bounded fetching + publishing.
            # SQLite supports one writer; PostgreSQL workers use an advisory lock.
            if db.bind.dialect.name == 'postgresql':
                locked = (await db.execute(text('SELECT pg_try_advisory_xact_lock(724903211)'))).scalar()
                if not locked:
                    await db.rollback()
                    return 'BUSY'
            elif db.bind.dialect.name == 'sqlite':
                try:
                    await db.execute(text('BEGIN IMMEDIATE'))
                except OperationalError as exc:
                    if 'locked' not in str(exc.orig).lower():
                        raise
                    await db.rollback()
                    return 'BUSY'
            else:
                raise VerificationUnavailable('Sync locking supports PostgreSQL or SQLite only.')
            existing = (await db.execute(select(CatalogSyncRun).where(CatalogSyncRun.sync_date == day))).scalar_one_or_none()
            configuration = {'provider': codes.provider, 'payer_sources': [p.name for p in payers], 'cms_scope': cms.scope}
            if existing:
                if any(existing.manifest_json.get(key) != value for key, value in configuration.items()):
                    raise VerificationUnavailable('Feed configuration differs from today\'s completed batch.')
                await db.rollback()
                return 'ALREADY_COMPLETED'
            # Bound complete fetching, including pagination and all payer feeds.
            snapshot_id, records, policies = await asyncio.wait_for(fetch_all(codes, cms, payers), timeout=900)
            validate_catalog(records)
            previous = (await db.execute(select(CatalogSyncRun).order_by(CatalogSyncRun.sync_date.desc()).limit(1))).scalar_one_or_none()
            if previous:
                previous_keys = set((await db.execute(select(MedicalCodeCatalog.code_system, MedicalCodeCatalog.code, MedicalCodeCatalog.release,
                    MedicalCodeCatalog.effective_from).where(MedicalCodeCatalog.sync_run_id == previous.id))).all())
                new_keys = {(r.code_system, r.code, r.release, r.effective_date) for r in records}
                if not previous_keys <= new_keys:
                    raise VerificationUnavailable('Full catalog lost historical entries; deletion records must remain dated.')
            # Reject ambiguous policy records, even if the vendor paginates duplicates.
            policy_keys = [(p['source'], p['document_type'], p['document_id'], p['version']) for p in policies]
            if len(set(policy_keys)) != len(policy_keys):
                raise VerificationUnavailable('Policy snapshot contains duplicate identities.')
            manifest = {**configuration, 'vendor_snapshot': snapshot_id,
                        'codes': len(records), 'policies': len(policies),
                        'code_sha256': digest([r.model_dump(mode='json') for r in records]),
                        'policy_sha256': digest(policies)}
            run = CatalogSyncRun(id=str(uuid.uuid4()), sync_date=day, completed_at=now, manifest_json=manifest)
            db.add(run)
            await db.flush()
            for record in records:
                db.add(MedicalCodeCatalog(sync_run_id=run.id, source=codes.provider,
                    code_system=record.code_system, code=record.code, release=record.release,
                    is_active=record.status == 'ACTIVE', effective_from=record.effective_date,
                    effective_to=record.expiration_date, replacement_code=record.replacement_code,
                    last_synced_at=now))
            for policy in policies:
                db.add(CoveragePolicyReference(sync_run_id=run.id,
                    **{k: policy[k] for k in ['source', 'document_type', 'document_id', 'version', 'status']},
                    payload_json=policy['payload'], sha256=digest(policy['payload'])))
            db.add(AuditLog(event='CATALOG_SYNC_COMPLETED', timestamp=now,
                            metadata_json={'sync_run_id': run.id, **manifest}))
            await db.commit()
            return 'COMPLETED'
        except Exception:
            await db.rollback()
            # Operational metadata only: upstream errors may contain secrets or PHI.
            db.add(AuditLog(event='CATALOG_SYNC_FAILED', timestamp=now,
                            metadata_json={'sync_date': day.isoformat(), 'reason': 'Reference sync failed; previous batch retained.'}))
            await db.commit()
            raise VerificationUnavailable('Daily reference sync failed; previous batch retained.') from None


async def fetch_all(codes, cms, payers):
    snapshot_id, records = await codes.fetch_catalog()
    policies = await cms.fetch_policies()
    for payer in payers:
        policies.extend(await payer.fetch_policies())
    return snapshot_id, records, policies
