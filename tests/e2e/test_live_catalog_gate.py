"""Catalog changes are visible at review and enforced at approval/export."""
from datetime import datetime, date, timezone, timedelta
import uuid
import pytest
from services.api.config import settings
from services.api.db.models.references import CatalogSyncRun, MedicalCodeCatalog


async def batch(db, day, expiration=None):
    run = CatalogSyncRun(id=str(uuid.uuid4()), sync_date=day,
        completed_at=datetime.now(timezone.utc), manifest_json={
            'provider': settings.MCA_CODE_API_PROVIDER, 'payer_sources': [], 'cms_scope': {}})
    db.add(run)
    await db.flush()
    db.add(MedicalCodeCatalog(sync_run_id=run.id, source='findacode', code_system='HCPCS', code='E0601',
        release='2026', effective_from=date(2026, 1, 1), effective_to=expiration,
        replacement_code='E9999' if expiration else None, is_active=expiration is None))
    await db.commit()


@pytest.mark.asyncio
async def test_daily_deletion_is_visible_and_blocks_approved_export(client, seed_data, db_session, monkeypatch):
    headers = {'Authorization': 'Bearer ' + seed_data['tokens']['reviewer_org1']}
    response = await client.post('/api/cases', headers=headers, json={
        'patient_reference': 'SYNTH-SYNC', 'service_date': '2026-09-22', 'coding_domain': 'dme', 'place_of_service': '12'})
    cid = response.json()['id']
    note = ('Date of Service: 2026-09-22\nEquipment: CPAP\nOrder type: RENTAL\n'
            'Signed CMN on file: yes\nSleep study criteria met: yes\nSigned by: Synthetic Reviewer\n')
    assert (await client.post(f'/api/cases/{cid}/documents', headers=headers,
        files={'file': ('synthetic.txt', note.encode(), 'text/plain')})).status_code == 201
    monkeypatch.setattr(settings, 'POLICY_SYNC_ENABLED', True)
    monkeypatch.setattr(settings, 'PAYER_POLICY_FEEDS_JSON', '[]')
    monkeypatch.setattr(settings, 'CMS_CONTRACTOR_ID', None)
    monkeypatch.setattr(settings, 'CMS_STATE_ID', None)
    review = (await client.get(f'/api/cases/{cid}/review', headers=headers)).json()
    assert any(f['rule_id'] == 'LIVE-CATALOG-UNAVAILABLE' for f in review['validation_findings'])
    today = datetime.now(timezone.utc).date()
    await batch(db_session, today - timedelta(days=1))
    review = (await client.get(f'/api/cases/{cid}/review', headers=headers)).json()
    assert not any(f['rule_id'].startswith('LIVE-CATALOG-') for f in review['validation_findings'])
    c = review['candidate_codes'][0]
    decision = {'decision': 'accept', 'version': review['version'], 'approved_candidate_ids': [c['id']],
                'accepted_modifiers': {c['id']: ['RR', 'KX']}}
    assert (await client.post(f'/api/cases/{cid}/decisions', headers=headers, json=decision)).status_code == 201
    assert (await client.get(f'/api/exports/encounter/{cid}/collaboratemd', headers=headers)).status_code == 200
    # Provider correction establishes that the selected code was already expired on DOS.
    await batch(db_session, today, expiration=date(2026, 9, 1))
    review = (await client.get(f'/api/cases/{cid}/review', headers=headers)).json()
    finding = next(f for f in review['validation_findings'] if f['rule_id'] == 'LIVE-CATALOG-VALIDITY')
    assert '2026-09-01' in finding['message'] and 'E9999' in finding['message']
    assert any(r['status'] == 'FAIL' and r['rule_id'] == 'LIVE-CATALOG-VALIDITY' for r in review['candidate_codes'][0]['rule_results'])
    response = await client.get(f'/api/exports/encounter/{cid}/collaboratemd', headers=headers)
    assert response.status_code == 400 and 'deleted/expired' in response.text
