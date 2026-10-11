from contextlib import asynccontextmanager
from pathlib import Path
import pytest
from sqlalchemy import select
from services.api.config import settings
from services.api.db.models import OutboxEvent, DocumentPage
from services.worker import worker


@pytest.mark.asyncio
async def test_durable_queued_pipeline(client, seed_data, db_session, monkeypatch):
    monkeypatch.setattr(settings, 'QUEUE_BACKEND', 'outbox')
    @asynccontextmanager
    async def session():
        yield db_session
    monkeypatch.setattr(worker, 'async_session_factory', session)
    headers = {'Authorization': 'Bearer ' + seed_data['tokens']['reviewer_org1']}
    created = await client.post('/api/cases', headers=headers, json={
        'patient_reference': 'SYNTH-WORKER', 'service_date': '2026-09-22',
    })
    case_id = created.json()['id']
    uploaded = await client.post(f'/api/cases/{case_id}/documents', headers=headers, files={
        'file': ('record.txt', Path('tests/fixtures/synthetic-er-record.txt').read_bytes(), 'text/plain'),
    })
    assert uploaded.status_code == 201
    assert uploaded.json()['pipeline_result']['status'] == 'queued'
    assert (await client.get(f'/api/cases/{case_id}', headers=headers)).json()['status'] == 'ingesting'
    for _ in range(20):
        if not await worker.process_one():
            break
    review = (await client.get(f'/api/cases/{case_id}/review', headers=headers)).json()
    assert review['status'] == 'review_required'
    assert review['candidate_codes']
    events = (await db_session.execute(select(OutboxEvent).where(OutboxEvent.case_id == case_id))).scalars().all()
    assert all(event.status == 'published' for event in events)
    from services.worker.tasks.pipeline import run_encounter_pipeline
    retry = await run_encounter_pipeline(case_id, uploaded.json()['id'], db_session)
    assert retry['duplicate']
    assert len((await db_session.execute(select(DocumentPage).where(DocumentPage.document_id == uploaded.json()['id']))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_unreadable_document_fails_visibly(client, seed_data):
    headers = {'Authorization': 'Bearer ' + seed_data['tokens']['reviewer_org1']}
    created = await client.post('/api/cases', headers=headers, json={
        'patient_reference': 'SYNTH-OCR-FAIL', 'service_date': '2026-09-22',
    })
    case_id = created.json()['id']
    response = await client.post(f'/api/cases/{case_id}/documents', headers=headers,
                                files={'file': ('blank.txt', b'  \n ', 'text/plain')})
    assert response.status_code == 422
    review = (await client.get(f'/api/cases/{case_id}/review', headers=headers)).json()
    assert review['status'] == 'review_required'
    assert review['snapshot_id'] is None
    assert review['candidate_codes'] == []
    assert (await client.post(f'/api/cases/{case_id}/exports', headers=headers)).status_code == 400
