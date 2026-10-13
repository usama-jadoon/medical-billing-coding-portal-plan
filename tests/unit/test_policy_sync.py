import asyncio
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
import httpx
import pytest
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from services.api.db.base import Base
from services.api.db.models.references import AuditLog, CatalogSyncRun, MedicalCodeCatalog
from services.api.config import settings
from services.coding_engine.providers.verification_api import CodeStatus, VerificationAPI, VerificationUnavailable
from services.worker.daily_sync_worker import next_midnight, sync_once
from services.worker.sync.cms import CMSCoverageClient
from services.worker.sync.payer import PayerPolicyClient
from services.worker.sync.service import synchronize
from services.worker.sync.validation import catalog_findings, validate_dated_codes
from services.rules_engine.validator import DeterministicValidationPipeline


def record(code='E0601', system='HCPCS', **kwargs):
    return {'code': code, 'code_system': system, 'release': '2026', 'status': 'ACTIVE',
            'effective_date': '2026-01-01', 'expiration_date': None, 'replacement_code': None, **kwargs}


def cms_report(kind='LCD'):
    return {'meta': {'status': {'id': 200, 'message': 'OK'}}, 'data': [
        {'document_id': 123, 'document_version': 2, 'document_status': 'Active', 'title': kind}]}


def adapter(client):
    return VerificationAPI(client, provider='findacode', validity_url='https://adapter.example/validity',
                           catalog_url='https://adapter.example/catalog', api_key='synthetic-test-token')


@pytest.mark.asyncio
async def test_validity_dates_and_no_clinical_payload():
    def handler(request):
        assert set(request.url.params) == {'code', 'service_date'}
        assert request.headers['authorization'] == 'Bearer synthetic-test-token'
        dos = date.fromisoformat(request.url.params['service_date'])
        return httpx.Response(200, json=record(status='ACTIVE' if dos < date(2027, 1, 1) else 'DELETED',
            expiration_date='2027-01-01', replacement_code='E9999'))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        api = adapter(client)
        assert (await api.verify_code_validity('E0601', date(2026, 12, 31))).status == 'ACTIVE'
        assert (await api.verify_code_validity('E0601', date(2027, 1, 1))).status == 'DELETED'


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', [record(code='OTHER'), record(status='DELETED'), record(expiration_date='2026-05-01'), {}])
async def test_invalid_validity_never_defaults_to_active(payload):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))) as client:
        with pytest.raises(VerificationUnavailable):
            await adapter(client).verify_code_validity('E0601', date(2026, 6, 1))


@pytest.mark.asyncio
async def test_catalog_pagination_and_mixed_snapshot_rejected():
    calls = []
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={'snapshot_id': 'stable', 'records': [record()],
                            'next_cursor': 'two' if 'cursor' not in request.url.params else None})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        sid, rows = await adapter(client).fetch_catalog()
        assert sid == 'stable' and len(rows) == 2 and len(calls) == 2
    count = 0
    def mixed(request):
        nonlocal count
        count += 1
        return httpx.Response(200, json={'snapshot_id': str(count), 'records': [record()], 'next_cursor': 'two'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(mixed)) as client:
        with pytest.raises(VerificationUnavailable):
            await adapter(client).fetch_catalog()


@pytest.mark.asyncio
async def test_retries_bounded_and_credentials_not_in_errors():
    count = 0
    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(503, text='synthetic-test-token')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(VerificationUnavailable) as error:
            await adapter(client).fetch_catalog()
        assert count == 3 and 'synthetic-test-token' not in str(error.value)


@pytest.mark.asyncio
async def test_cms_verified_report_paths_scope_and_error_envelope():
    paths = []
    def handler(request):
        paths.append(request.url.path)
        assert 'authorization' not in request.headers
        if 'national' in request.url.path:
            assert not request.url.params
        elif 'whats-new' in request.url.path:
            assert dict(request.url.params) == {'contractor_id': '7'}
        else:
            assert dict(request.url.params) == {'contractor_id': '7', 'state_id': '9'}
        return httpx.Response(200, json=cms_report())
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        rows = await CMSCoverageClient(client, contractor_id=7, state_id=9).fetch_policies()
        assert {r['document_type'] for r in rows} == {'LCD', 'ARTICLE', 'NCD', 'LOCAL_UPDATE'}
        assert set(paths) == set(CMSCoverageClient.REPORTS.values())
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={'meta': {'status': {'id': 400}}, 'data': []}))) as client:
        with pytest.raises(VerificationUnavailable):
            await CMSCoverageClient(client).fetch_policies()


@pytest.fixture
async def database():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


class Codes:
    provider = 'findacode'
    def __init__(self):
        self.rows = [CodeStatus.model_validate(record()), CodeStatus.model_validate(record('99213', 'CPT')),
                     CodeStatus.model_validate(record('F41.9', 'ICD-10-CM'))]
        self.calls = 0
    async def fetch_catalog(self):
        self.calls += 1
        return 'revision-1', self.rows


class Policies:
    scope = {}
    name = 'BCBSTX'
    def __init__(self, fail=False):
        self.fail = fail
    async def fetch_policies(self):
        if self.fail:
            raise RuntimeError('sensitive upstream body')
        return [{'source': 'CMS', 'document_type': 'LCD', 'document_id': '123', 'version': '1',
                 'status': 'Active', 'payload': {'document_id': 123}}]


@pytest.mark.asyncio
async def test_sync_atomic_idempotent_historical_and_failed_payer(database):
    codes = Codes()
    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    assert await synchronize(database, codes, Policies(), now=now) == 'COMPLETED'
    assert await synchronize(database, codes, Policies(), now=now) == 'ALREADY_COMPLETED'
    assert codes.calls == 1
    with pytest.raises(VerificationUnavailable):
        await synchronize(database, codes, Policies(), [Policies(fail=True)], now=now + timedelta(days=1))
    async with database() as db:
        assert (await db.scalar(select(func.count()).select_from(CatalogSyncRun))) == 1
        assert (await db.scalar(select(func.count()).select_from(MedicalCodeCatalog))) == 3
        audits = (await db.execute(select(AuditLog))).scalars().all()
        assert {r.event for r in audits} == {'CATALOG_SYNC_COMPLETED', 'CATALOG_SYNC_FAILED'}
        assert 'sensitive upstream' not in str([r.metadata_json for r in audits])
    codes.rows[0] = CodeStatus.model_validate(record(status='DELETED', expiration_date='2026-11-01', replacement_code='E9999'))
    assert await synchronize(database, codes, Policies(), now=now + timedelta(days=1)) == 'COMPLETED'
    async with database() as db:
        assert (await db.scalar(select(func.count()).select_from(MedicalCodeCatalog))) == 6
        assert (await db.execute(select(MedicalCodeCatalog).order_by(MedicalCodeCatalog.last_synced_at))).scalars().first().effective_to is None


@pytest.mark.asyncio
async def test_overlap_and_lost_history_cannot_publish(database):
    codes = Codes()
    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    await synchronize(database, codes, Policies(), now=now)
    codes.rows.append(CodeStatus.model_validate(record(release='2027', effective_date='2027-01-01')))
    with pytest.raises(VerificationUnavailable):
        await synchronize(database, codes, Policies(), now=now + timedelta(days=1))
    codes.rows = codes.rows[1:]
    with pytest.raises(VerificationUnavailable):
        await synchronize(database, codes, Policies(), now=now + timedelta(days=1))


def test_deleted_code_historical_window_and_boundary():
    rows = [SimpleNamespace(code='E0601', code_system='HCPCS', effective_from=date(2026, 1, 1),
                            effective_to=date(2026, 11, 1), replacement_code='E9999', is_active=False)]
    candidates = [{'code': 'E0601', 'code_system': 'HCPCS'}]
    assert validate_dated_codes(candidates, '2026-10-31', rows) == []
    findings = validate_dated_codes(candidates, '2026-11-01', rows)
    assert findings[0].severity == 'BLOCK'
    assert findings[0].message == 'Code E0601 was deleted/expired as of 2026-11-01. Review suggested replacement: E9999.'
    result = DeterministicValidationPipeline().validate_case('dme', '2026-11-01', '12', [], [], reference_findings=findings)
    assert result.has_blockers and not result.eligible_for_approval


@pytest.mark.asyncio
async def test_stale_missing_and_disabled_cache(database, monkeypatch):
    candidates = [{'code': 'E0601', 'code_system': 'HCPCS'}]
    monkeypatch.setattr(settings, 'POLICY_SYNC_ENABLED', True)
    async with database() as db:
        assert (await catalog_findings(db, candidates, '2026-10-13'))[0].rule_id == 'LIVE-CATALOG-UNAVAILABLE'
    await synchronize(database, Codes(), Policies(), now=datetime.now(timezone.utc) - timedelta(hours=25))
    async with database() as db:
        assert (await catalog_findings(db, candidates, '2026-10-13'))[0].rule_id == 'LIVE-CATALOG-UNAVAILABLE'
        monkeypatch.setattr(settings, 'POLICY_SYNC_ENABLED', False)
        assert await catalog_findings(db, candidates, '2026-10-13') == []


@pytest.mark.asyncio
async def test_disabled_worker_and_placeholder_credentials(monkeypatch):
    monkeypatch.setattr(settings, 'POLICY_SYNC_ENABLED', False)
    with pytest.raises(VerificationUnavailable, match='disabled'):
        await sync_once()
    async with httpx.AsyncClient() as client:
        with pytest.raises(VerificationUnavailable):
            VerificationAPI(client, provider='findacode', validity_url='https://example.com/a', catalog_url='https://example.com/b', api_key='your_findacode_api_key_here')


def test_utc_midnight_schedule():
    assert next_midnight(datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc)) == datetime(2027, 1, 1, tzinfo=timezone.utc)
    assert next_midnight(datetime(2026, 10, 13, 5, tzinfo=timezone(timedelta(hours=5)))) == datetime(2026, 10, 14, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_payer_pagination_is_required_and_bounded():
    def handler(request):
        page = '2' if request.url.params.get('cursor') else '1'
        return httpx.Response(200, json={'snapshot_id': 'payer-release', 'records': [
            {'document_id': page, 'document_type': 'medical_policy', 'version': '1', 'status': 'active'}],
            'next_cursor': 'two' if page == '1' else None})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        payer = PayerPolicyClient(client, name='BCBSTX', url='https://adapter.example/policies', token='synthetic')
        rows = await payer.fetch_policies()
        assert len(rows) == 2 and all(r['source'] == 'BCBSTX' for r in rows)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={
        'snapshot_id': 'payer-release', 'records': [], 'next_cursor': 'same'}))) as client:
        with pytest.raises(VerificationUnavailable):
            await PayerPolicyClient(client, name='BCBSTX', url='https://adapter.example/policies', token='synthetic').fetch_policies()


@pytest.mark.asyncio
async def test_overlapping_workers_cannot_publish_twice(tmp_path):
    engine = create_async_engine('sqlite+aiosqlite:///' + (tmp_path / 'sync.sqlite').as_posix(), connect_args={'timeout': 0})
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    entered, release = asyncio.Event(), asyncio.Event()
    class SlowCodes(Codes):
        async def fetch_catalog(self):
            entered.set()
            await release.wait()
            return await super().fetch_catalog()
    first = asyncio.create_task(synchronize(factory, SlowCodes(), Policies()))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        assert await synchronize(factory, Codes(), Policies()) == 'BUSY'
        release.set()
        assert await first == 'COMPLETED'
        assert await synchronize(factory, Codes(), Policies()) == 'ALREADY_COMPLETED'
    finally:
        release.set()
        await first
        await engine.dispose()
