"""Daily 00:00 UTC worker. Run with --once for a scheduler invocation."""
import argparse
import asyncio
import json
from datetime import datetime, timedelta, timezone
import httpx
from services.api.config import settings
from services.api.db.session import async_session_factory, engine
from services.coding_engine.providers.verification_api import VerificationAPI, VerificationUnavailable
from services.worker.sync.cms import CMSCoverageClient
from services.worker.sync.payer import PayerPolicyClient
from services.worker.sync.service import synchronize


def next_midnight(now):
    return (now.astimezone(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


async def sync_once():
    if not settings.POLICY_SYNC_ENABLED and not settings.CMS_POLICY_SYNC_ENABLED:
        raise VerificationUnavailable('Daily policy sync is disabled. Configure licensed adapters before enabling it.')
    if settings.POLICY_SYNC_CRON != '0 0 * * *' or settings.POLICY_CACHE_TTL_HOURS <= 0:
        raise VerificationUnavailable('Supported schedule is 0 0 * * * UTC with a positive cache TTL.')
    if settings.CMS_COVERAGE_API_BASE_URL.rstrip('/') != CMSCoverageClient.BASE_URL:
        raise VerificationUnavailable('CMS endpoint must be the verified official Coverage API.')
    try:
        feeds = json.loads(settings.PAYER_POLICY_FEEDS_JSON)
        if not isinstance(feeds, list) or any(set(f) != {'name', 'url', 'token'} for f in feeds):
            raise ValueError('Invalid payer configuration')
        if len({f['name'] for f in feeds}) != len(feeds) or any(f['name'] == 'CMS' for f in feeds):
            raise ValueError('Duplicate payer identities')
    except (ValueError, TypeError):
        raise VerificationUnavailable('Payer feed configuration is invalid.') from None
    async with httpx.AsyncClient() as client:
        cms = CMSCoverageClient(client, contractor_id=settings.CMS_CONTRACTOR_ID, state_id=settings.CMS_STATE_ID)
        if settings.CMS_POLICY_SYNC_ENABLED:
            from services.worker.sync.cms_refresh import refresh_cms
            result = await refresh_cms(async_session_factory, cms)
            if not settings.POLICY_SYNC_ENABLED:
                return result
        codes = VerificationAPI(client, provider=settings.MCA_CODE_API_PROVIDER,
            validity_url=settings.MCA_CODE_API_VALIDITY_URL, catalog_url=settings.MCA_CODE_API_CATALOG_URL,
            api_key=settings.MCA_CODE_API_KEY)
        cms = CMSCoverageClient(client, contractor_id=settings.CMS_CONTRACTOR_ID, state_id=settings.CMS_STATE_ID)
        payers = [PayerPolicyClient(client, **feed) for feed in feeds]
        return await synchronize(async_session_factory, codes, cms, payers)


async def run(once=False):
    try:
        while True:
            try:
                # Startup catches today's missed run; successful runs are idempotent.
                result = await sync_once()
                print(f'Catalog sync: {result}', flush=True)
                delay = (next_midnight(datetime.now(timezone.utc)) - datetime.now(timezone.utc)).total_seconds()
                if result == 'BUSY':
                    delay = 300
            except (VerificationUnavailable, TimeoutError) as exc:
                print(f'Catalog sync unavailable: {exc}', flush=True)
                if once:
                    return 1
                delay = 300
            if once:
                return 0 if result != 'BUSY' else 2
            await asyncio.sleep(max(1, delay))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    raise SystemExit(asyncio.run(run(parser.parse_args().once)))
