import pytest
from sqlalchemy import select, func
from services.api.db.models.references import CMSCoverageSnapshot, AuditLog, CatalogSyncRun
from services.worker.sync.cms_refresh import refresh_cms
from services.coding_engine.providers.verification_api import VerificationUnavailable
from services.api.config import settings


class PublicCMS:
    scope = {}
    def __init__(self, fail=False):
        self.fail = fail
    async def fetch_policies(self):
        if self.fail:
            raise RuntimeError('upstream private response')
        return [{'document_id': 'synthetic', 'status': 'REFERENCE_ONLY'}]


@pytest.mark.asyncio
async def test_public_refresh_is_independent_and_idempotent(db_session):
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def factory():
        yield db_session
    assert await refresh_cms(factory, PublicCMS()) == 'CMS_COMPLETED'
    assert await refresh_cms(factory, PublicCMS()) == 'CMS_ALREADY_COMPLETED'
    assert await db_session.scalar(select(func.count()).select_from(CMSCoverageSnapshot)) == 1
    assert await db_session.scalar(select(func.count()).select_from(CatalogSyncRun)) == 0
    assert await db_session.scalar(select(AuditLog.event)) == 'CMS_POLICY_SYNC_COMPLETED'


@pytest.mark.asyncio
async def test_public_refresh_failure_is_not_completion(db_session):
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def factory():
        yield db_session
    with pytest.raises(VerificationUnavailable):
        await refresh_cms(factory, PublicCMS(fail=True))
    assert await db_session.scalar(select(func.count()).select_from(CMSCoverageSnapshot)) == 0
    assert await db_session.scalar(select(AuditLog.event)) == 'CMS_POLICY_SYNC_FAILED'


@pytest.mark.asyncio
async def test_reference_status_requires_login(client):
    assert (await client.get('/api/references/cms-status')).status_code == 401
