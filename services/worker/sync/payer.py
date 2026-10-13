"""Explicit configured payer feeds using the normalization contract."""
from services.coding_engine.providers.verification_api import RestClient, VerificationUnavailable, require_https


class PayerPolicyClient(RestClient):
    def __init__(self, client, *, name, url, token):
        super().__init__(client)
        if not name or len(name) > 100 or not token or token.startswith('your_'):
            raise VerificationUnavailable('Payer feed requires an identity and credentials.')
        self.name, self.url, self.token = name, require_https(url), token

    async def fetch_policies(self):
        result, cursor, seen, snapshot = [], None, set(), None
        for _ in range(1000):
            payload = await self.get_json(self.url, params={'cursor': cursor} if cursor else {}, headers={'Authorization': f'Bearer {self.token}'})
            try:
                if set(payload) != {'snapshot_id', 'records', 'next_cursor'} or not isinstance(payload['records'], list):
                    raise ValueError('Invalid envelope')
                current = payload['snapshot_id']
                if not isinstance(current, str) or not current or (snapshot and snapshot != current):
                    raise ValueError('Mixed snapshot')
                snapshot = current
                for row in payload['records']:
                    if not isinstance(row, dict) or any(not isinstance(row.get(key), str) or not row[key] or len(row[key]) > 100 for key in ['document_id', 'version', 'status', 'document_type']):
                        raise ValueError('Missing policy identity')
                    result.append({'source': self.name, **{key: row[key] for key in ['document_id', 'version', 'status', 'document_type']}, 'payload': row})
                cursor = payload['next_cursor']
                if cursor is not None and (not isinstance(cursor, str) or not cursor or cursor in seen):
                    raise ValueError('Invalid cursor')
                if len(result) > 100000:
                    raise ValueError('Too many policies')
            except (ValueError, KeyError, TypeError):
                raise VerificationUnavailable('Payer policy feed contract failed.') from None
            if cursor is None:
                if not result:
                    raise VerificationUnavailable('Empty payer feed cannot replace prior references.')
                return result
            seen.add(cursor)
        raise VerificationUnavailable('Payer pagination limit reached.')
