import pytest
from sqlalchemy import select, func
from services.api.db.models.references import CMSCoverageSnapshot, AuditLog, CatalogSyncRun
from services.worker.sync.cms_refresh import refresh_cms
from services.coding_engine.providers.verification_api import VerificationUnavailable
from services.api.config import settings
from services.worker.sync.cms import CMSCoverageClient
from services.coding_engine.providers.verification_api import ReferenceHTTPError
import httpx
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from services.worker.sync.service import digest


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


@pytest.mark.asyncio
@pytest.mark.parametrize('host,server,body,reason', [
    ('api.coverage.cms.gov', 'CloudFront', 'The distribution is configured to block access from your country. private-token', 'CMS_COUNTRY_RESTRICTED'),
    ('api.coverage.cms.gov', 'CloudFront', 'Access denied. private-token', 'HTTP_403'),
    ('adapter.example', 'CloudFront', 'configured to block access from your country private-token', 'HTTP_403'),
])
async def test_http_restriction_is_precise_and_sanitized(host, server, body, reason):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(403, text=body, headers={'server': server}))) as client:
        from services.coding_engine.providers.verification_api import RestClient
        with pytest.raises(ReferenceHTTPError) as error:
            await RestClient(client).get_json(f'https://{host}/report?secret=private-token')
        assert error.value.reason_code == reason
        assert error.value.http_status == 403
        assert 'private-token' not in str(error.value)
        assert host not in str(error.value)


@pytest.mark.asyncio
async def test_country_failure_preserves_snapshot_and_is_visible(client, db_session, seed_data, monkeypatch):
    from services.api.db.models.references import CMSCoverageSnapshot
    monkeypatch.setattr(settings, 'CMS_CONTRACTOR_ID', None)
    monkeypatch.setattr(settings, 'CMS_STATE_ID', None)
    db_session.add(CMSCoverageSnapshot(sync_date=datetime.now(timezone.utc).date() - timedelta(days=2),
        scope_sha256=digest({}), scope_json={}, records_json=[{'id': 'old'}], sha256='a' * 64,
        completed_at=datetime.now(timezone.utc) - timedelta(days=2)))
    # A newer snapshot for a different jurisdiction must not conceal a missing/old configured scope.
    db_session.add(CMSCoverageSnapshot(sync_date=datetime.now(timezone.utc).date(),
        scope_sha256=digest({'state_id': 9}), scope_json={'state_id': 9}, records_json=[{}, {}], sha256='b' * 64))
    await db_session.commit()
    @asynccontextmanager
    async def factory():
        yield db_session
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(403,
        headers={'server': 'CloudFront'}, text='configured to block access from your country private-token'))) as upstream:
        with pytest.raises(ReferenceHTTPError):
            await refresh_cms(factory, CMSCoverageClient(upstream))
    response = await client.get('/api/references/cms-status', headers={'Authorization': f"Bearer {seed_data['tokens']['reviewer_org1']}"})
    assert response.status_code == 200
    data = response.json()
    assert data['records'] == 1 and data['stale'] is True
    assert data['scope'] == {}
    assert data['last_attempt']['status'] == 'failed'
    assert data['last_attempt']['reason_code'] == 'CMS_COUNTRY_RESTRICTED'
    assert data['last_attempt']['http_status'] == 403
    assert 'private-token' not in response.text
    assert await db_session.scalar(select(func.count()).select_from(CMSCoverageSnapshot)) == 2
    assert await db_session.scalar(select(AuditLog.event)) == 'CMS_POLICY_SYNC_FAILED'
