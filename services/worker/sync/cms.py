"""CMS Coverage API v1.6 public report endpoints; metadata, not executable rules."""
from services.coding_engine.providers.verification_api import RestClient, VerificationUnavailable


class CMSCoverageClient(RestClient):
    BASE_URL = 'https://api.coverage.cms.gov'
    REPORTS = {
        'LCD': '/v1/reports/local-coverage-final-lcds/',
        'ARTICLE': '/v1/reports/local-coverage-articles/',
        'NCD': '/v1/reports/national-coverage-ncd/',
        'LOCAL_UPDATE': '/v1/reports/whats-new/local/',
    }

    def __init__(self, client, *, contractor_id=None, state_id=None):
        super().__init__(client)
        self.scope = {key: value for key, value in {'contractor_id': contractor_id, 'state_id': state_id}.items() if value is not None}

    async def fetch_policies(self):
        records = []
        for kind, path in self.REPORTS.items():
            params = {} if kind == 'NCD' else dict(self.scope)
            if kind == 'LOCAL_UPDATE':
                # Latest published weekly period (not a UTC day-sized delta).
                params.pop('state_id', None)
            payload = await self.get_json(self.BASE_URL + path, params=params)
            try:
                if not isinstance(payload['data'], list) or not isinstance(payload['meta']['status']['id'], int):
                    raise ValueError('Invalid CMS envelope')
                if not 200 <= payload['meta']['status']['id'] < 300 or payload['meta'].get('next_token'):
                    raise ValueError('Failed or unexpectedly paginated report')
                if kind != 'LOCAL_UPDATE' and not payload['data']:
                    raise ValueError('Empty CMS baseline')
                for row in payload['data']:
                    if not isinstance(row, dict) or row.get('document_id') is None or row.get('document_version') is None:
                        raise ValueError('Missing document identity')
                    status = row.get('document_status')
                    if kind != 'LOCAL_UPDATE' and (not isinstance(status, str) or not status):
                        raise ValueError('Missing coverage status')
                    records.append({'source': 'CMS', 'document_type': kind,
                                    'document_id': str(row['document_id']), 'version': str(row['document_version']),
                                    'status': status or 'UPDATE_NOTICE', 'payload': row})
            except (ValueError, KeyError, TypeError):
                raise VerificationUnavailable('CMS report contract failed; prior references retained.') from None
        return records
