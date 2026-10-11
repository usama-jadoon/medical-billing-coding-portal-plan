import hashlib
import hmac
import json
from pathlib import Path
import pytest
from sqlalchemy import select
from services.api.config import settings
from services.api.db.models import CaseSnapshot, Evidence


async def prepared_case(client, seed_data):
    headers = {'Authorization': 'Bearer ' + seed_data['tokens']['reviewer_org1']}
    created = await client.post('/api/cases', headers=headers, json={
        'patient_reference': 'SYNTH-INTEGRITY', 'service_date': '2026-09-22',
        'coding_domain': 'emergency_department', 'place_of_service': '23',
    })
    assert created.status_code == 201
    case_id = created.json()['id']
    source = Path('tests/fixtures/synthetic-er-record.txt').read_bytes()
    uploaded = await client.post(f'/api/cases/{case_id}/documents', headers=headers,
                                 files={'file': ('record.txt', source, 'text/plain')})
    assert uploaded.status_code == 201, uploaded.text
    review = (await client.get(f'/api/cases/{case_id}/review', headers=headers)).json()
    return case_id, headers, source, review


def selected_ids(review):
    return [c['id'] for c in review['candidate_codes'] if c['code'] in {'K35.80', '99285'}]


@pytest.mark.asyncio
async def test_review_and_signed_export(client, seed_data):
    case_id, headers, _, review = await prepared_case(client, seed_data)
    for fact in review['clinical_facts']:
        ev = fact['evidence']
        page = next(p for d in review['documents'] if d['id'] == ev['document_id'] for p in d['pages'] if p['page_number'] == ev['page_number'])
        assert page['ocr_text'][ev['start_offset']:ev['end_offset']] == ev['quoted_text']
        assert ev['bbox'] is None
    decision = {'decision': 'accept', 'version': review['version'], 'approved_candidate_ids': selected_ids(review)}
    accepted = await client.post(f'/api/cases/{case_id}/decisions', headers=headers, json=decision)
    assert accepted.status_code == 201, accepted.text
    stale = await client.post(f'/api/cases/{case_id}/decisions', headers=headers, json=decision)
    assert stale.status_code == 409
    exported = await client.post(f'/api/cases/{case_id}/exports', headers=headers)
    assert exported.status_code == 200, exported.text
    manifest = exported.json()
    signature = manifest.pop('integrity_signature')
    expected = hmac.new(settings.SECRET_KEY.encode(), json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()
    assert hmac.compare_digest(signature, expected)
    assert {c['code'] for c in manifest['approved_codes']} == {'K35.80', '99285'}
    assert (await client.post(f'/api/cases/{case_id}/exports', headers=headers)).status_code == 200
    for format in ('json', 'csv', 'worksheet'):
        assert (await client.get(f'/api/exports/encounter/{case_id}/{format}', headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_source_change_preserves_history_and_invalidates_approval(client, seed_data, db_session):
    case_id, headers, source, review = await prepared_case(client, seed_data)
    accepted = await client.post(f'/api/cases/{case_id}/decisions', headers=headers, json={
        'decision': 'accept', 'version': review['version'], 'approved_candidate_ids': selected_ids(review),
    })
    assert accepted.status_code == 201
    duplicate = await client.post(f'/api/cases/{case_id}/documents', headers=headers, files={'file': ('same.txt', source, 'text/plain')})
    assert duplicate.json()['pipeline_result']['duplicate']
    assert (await client.get(f'/api/cases/{case_id}/review', headers=headers)).json()['status'] == 'approved'
    amendment = source + b'\nAdditional documentation: Follow-up required.'
    assert (await client.post(f'/api/cases/{case_id}/documents', headers=headers, files={'file': ('amended.txt', amendment, 'text/plain')})).status_code == 201
    latest = (await client.get(f'/api/cases/{case_id}/review', headers=headers)).json()
    assert latest['status'] == 'review_required'
    assert latest['snapshot_id'] != review['snapshot_id']
    assert len(latest['candidate_codes']) == len(review['candidate_codes'])
    assert len((await db_session.execute(select(CaseSnapshot).where(CaseSnapshot.case_id == case_id))).scalars().all()) == 3
    assert (await client.post(f'/api/cases/{case_id}/exports', headers=headers)).status_code == 400
    wrong_ids = await client.post(f'/api/cases/{case_id}/decisions', headers=headers, json={
        'decision': 'accept', 'version': latest['version'], 'approved_candidate_ids': selected_ids(review),
    })
    assert wrong_ids.status_code == 400


@pytest.mark.asyncio
async def test_tampered_evidence_blocks_approval(client, seed_data, db_session):
    case_id, headers, _, review = await prepared_case(client, seed_data)
    candidate = next(c for c in review['candidate_codes'] if c['code'] == 'K35.80')
    evidence = await db_session.get(Evidence, candidate['supporting_evidence'][0]['id'])
    evidence.quoted_text = 'fabricated diagnosis'
    await db_session.commit()
    response = await client.post(f'/api/cases/{case_id}/decisions', headers=headers, json={
        'decision': 'accept', 'version': review['version'], 'approved_candidate_ids': [candidate['id']],
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_all_exports_block_unapproved_case(client, seed_data):
    for format in ('json', 'csv', 'worksheet'):
        response = await client.get(f'/api/exports/encounter/{seed_data["encounter1"].id}/{format}', headers={'Authorization': 'Bearer ' + seed_data['tokens']['reviewer_org1']})
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_strict_case_inputs(client, seed_data):
    headers = {'Authorization': 'Bearer ' + seed_data['tokens']['reviewer_org1']}
    for overrides in ({'service_date': '2026-02-30'}, {'coding_domain': 'inpatient'}, {'patient_reference': '  '}):
        response = await client.post('/api/cases', headers=headers, json={
            'patient_reference': 'SYNTH', 'service_date': '2026-09-22', **overrides,
        })
        assert response.status_code == 422
