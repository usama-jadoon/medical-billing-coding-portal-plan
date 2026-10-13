import pytest
from pathlib import Path


@pytest.mark.asyncio
async def test_setting_detection_is_authenticated_and_does_not_choose_ambiguous_profile(client, seed_data):
    source = Path('tests/fixtures/synthetic-er-record.txt').read_bytes()
    payload = {'file': ('record.txt', source, 'text/plain')}
    assert (await client.post('/api/cases/detect-setting', files=payload)).status_code == 401
    headers = {'Authorization': 'Bearer ' + seed_data['tokens']['reviewer_org1']}
    result = await client.post('/api/cases/detect-setting', headers=headers, files=payload)
    assert result.status_code == 200
    assert result.json()['coding_domain'] == 'emergency_department'
    assert result.json()['confirmation_required'] is True
    for text in ('Office notes with no setting documented.', 'Emergency department; prior physician office visit POS 11.'):
        response = await client.post('/api/cases/detect-setting', headers=headers,
            files={'file': ('ambiguous.txt', text.encode(), 'text/plain')})
        assert response.json()['coding_domain'] is None
    office = await client.post('/api/cases/detect-setting', headers=headers,
        files={'file': ('office.txt', b'Physician office. POS 11.', 'text/plain')})
    assert office.json()['coding_domain'] == 'professional_office'
    bad = await client.post('/api/cases/detect-setting', headers=headers,
        files={'file': ('fake.pdf', b'plain text', 'application/pdf')})
    assert bad.status_code == 400
