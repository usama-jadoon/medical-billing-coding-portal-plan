import time
import pytest
from services.api.config import settings
from services.api.security.auth import create_access_token, verify_totp
from services.api.api.documents import validate_file_signature
from services.coding_engine.ai.gateway import AIGatewayBroker, AIGatewayRequest, AIGatewayValidationError
from fastapi import HTTPException


def test_totp_reference_vector(monkeypatch):
    monkeypatch.setattr(time, 'time', lambda: 59)
    assert verify_totp('GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ', '287082')
    assert not verify_totp('GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ', '000000')


@pytest.mark.asyncio
@pytest.mark.parametrize('format', ['json', 'collaboratemd'])
async def test_stale_signin_cannot_export(client, seed_data, format):
    import jwt
    token = jwt.encode({'sub': seed_data['user_reviewer'].id, 'iat': int(time.time()) - 600,
                        'exp': int(time.time()) + 600}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    response = await client.get(f'/api/exports/encounter/enc-1/{format}', headers={'Authorization': 'Bearer ' + token})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_named_owner_excludes_legacy_user(client, seed_data, monkeypatch):
    monkeypatch.setattr(settings, 'OWNER_EMAIL', 'private-owner@example.com')
    response = await client.get('/api/cases', headers={'Authorization': 'Bearer ' + seed_data['tokens']['reviewer_org1']})
    assert response.status_code == 403


@pytest.mark.parametrize('filename,mime,data', [
    ('fake.pdf', 'text/plain', b'plaintext'), ('fake.pdf', 'application/pdf', b'\x89PNG\r\n\x1a\nrest'),
    ('fake.txt', 'text/plain', b'\x00binary'), ('empty.txt', 'text/plain', b''),
])
def test_signature_cannot_be_bypassed(filename, mime, data):
    with pytest.raises(HTTPException):
        validate_file_signature(data, filename, mime)


def test_ai_unknown_fields_and_empty_allowlist_fail_closed():
    broker = AIGatewayBroker()
    request = AIGatewayRequest(task_type='clinical_extraction', case_snapshot_id='snapshot')
    with pytest.raises(AIGatewayValidationError):
        broker.validate_and_filter_response(request, {'approve': True})
    result = broker.validate_and_filter_response(request, {'claims': [{
        'type': 'diagnosis', 'normalized_value': {'condition': 'appendicitis'}, 'evidence_region_ids': ['made-up'],
    }]}, known_source_text='appendicitis')
    assert result.claims == []
