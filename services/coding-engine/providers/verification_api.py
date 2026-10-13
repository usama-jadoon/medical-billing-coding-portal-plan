"""Fail-closed REST boundary for a licensed vendor adapter.

No proprietary URL or authentication contract is guessed. Deploy the documented
normalization adapter contract in docs/POLICY_SYNC.md, or supply a vendor adapter
implementing these methods once licensed API documentation is available.
"""
import asyncio
from datetime import date
from typing import Literal
from urllib.parse import urlsplit
import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator


class VerificationUnavailable(RuntimeError):
    pass


class CodeStatus(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str = Field(min_length=1, max_length=30)
    code_system: Literal['CPT', 'HCPCS', 'ICD-10-CM', 'ICD-10-PCS', 'CDT']
    release: str = Field(min_length=1, max_length=100)
    status: Literal['ACTIVE', 'DELETED']
    effective_date: date
    expiration_date: date | None = None
    replacement_code: str | None = Field(default=None, max_length=30)

    @model_validator(mode='after')
    def valid_window(self):
        if self.expiration_date and self.expiration_date <= self.effective_date:
            raise ValueError('Expiration must follow effective date.')
        if self.status == 'DELETED' and self.expiration_date is None:
            raise ValueError('Deleted codes require a documented expiration date.')
        if self.replacement_code == self.code:
            raise ValueError('A replacement cannot be the same code.')
        return self


class RestClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def get_json(self, url, *, params=None, headers=None):
        # Retry read-only transient failures; never include URLs, keys or bodies in errors.
        for attempt in range(3):
            try:
                response = await self.client.get(url, params=params, headers=headers,
                                                 timeout=30, follow_redirects=False)
                if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                    await asyncio.sleep(0.25 * (2 ** attempt))
                    continue
                response.raise_for_status()
                if len(response.content) > 32 * 1024 * 1024:
                    raise VerificationUnavailable('Reference response exceeds size limit.')
                return response.json()
            except httpx.TransportError:
                if attempt < 2:
                    await asyncio.sleep(0.25 * (2 ** attempt))
                    continue
                raise VerificationUnavailable('Reference provider transport unavailable.') from None
            except (httpx.HTTPStatusError, ValueError):
                raise VerificationUnavailable('Reference provider rejected request or returned invalid JSON.') from None


def require_https(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise VerificationUnavailable('Configure an HTTPS endpoint without embedded credentials or query parameters.')
    return url


class VerificationAPI(RestClient):
    def __init__(self, client, *, provider, validity_url, catalog_url, api_key):
        super().__init__(client)
        if provider not in {'findacode', 'aapc'} or not api_key or api_key.startswith('your_'):
            raise VerificationUnavailable('Licensed provider and real adapter credentials are required.')
        self.provider = provider
        self.validity_url = require_https(validity_url)
        self.catalog_url = require_https(catalog_url)
        self.headers = {'Authorization': f'Bearer {api_key}'}

    async def verify_code_validity(self, code: str, service_date: date) -> CodeStatus:
        payload = await self.get_json(self.validity_url, params={'code': code, 'service_date': service_date.isoformat()}, headers=self.headers)
        try:
            result = CodeStatus.model_validate(payload)
            if result.code != code:
                raise ValueError('Code mismatch')
            active = result.effective_date <= service_date and (result.expiration_date is None or service_date < result.expiration_date)
            if (result.status == 'ACTIVE') != active:
                raise ValueError('Status contradicts requested date')
            return result
        except ValueError:
            raise VerificationUnavailable('Code validity response is inconsistent or incomplete.') from None

    async def fetch_catalog(self):
        """Complete dated snapshot each day, including quarterly/future revisions."""
        records, cursor, seen, snapshot_id = [], None, set(), None
        for _ in range(1000):
            payload = await self.get_json(self.catalog_url, params={'cursor': cursor} if cursor else {}, headers=self.headers)
            try:
                if set(payload) != {'snapshot_id', 'records', 'next_cursor'} or not isinstance(payload['records'], list):
                    raise ValueError('Invalid envelope')
                current = payload['snapshot_id']
                if not isinstance(current, str) or not current or (snapshot_id and snapshot_id != current):
                    raise ValueError('Mixed snapshots')
                snapshot_id = current
                records.extend(CodeStatus.model_validate(row) for row in payload['records'])
                cursor = payload['next_cursor']
                if cursor is not None and (not isinstance(cursor, str) or not cursor or cursor in seen):
                    raise ValueError('Invalid pagination')
                if len(records) > 500000:
                    raise ValueError('Too many records')
            except (ValueError, TypeError, KeyError):
                raise VerificationUnavailable('Licensed catalog snapshot is malformed or incomplete.') from None
            if cursor is None:
                if not records:
                    raise VerificationUnavailable('Empty licensed catalog cannot replace the previous snapshot.')
                return snapshot_id, records
            seen.add(cursor)
        raise VerificationUnavailable('Licensed catalog pagination limit reached.')
