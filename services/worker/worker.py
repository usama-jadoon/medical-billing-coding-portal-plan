"""Durable local outbox consumer. SQLite supports one worker; PostgreSQL uses row locks."""
import argparse
import asyncio
from sqlalchemy import select
from services.api.db.session import async_session_factory, engine
from services.api.db.models import OutboxEvent, Encounter, AuditEvent
from services.worker.tasks.pipeline import run_encounter_pipeline


async def process_one():
    async with async_session_factory() as db:
        event = (await db.execute(select(OutboxEvent).where(OutboxEvent.status == 'pending')
            .order_by(OutboxEvent.occurred_at).limit(1).with_for_update(skip_locked=True))).scalars().first()
        if not event:
            return False
        event_id, case_id = event.id, event.case_id
        try:
            if event.event_type == 'document.uploaded':
                await run_encounter_pipeline(case_id, event.payload_json['document_id'], db)
            event.status = 'published'
            await db.commit()
        except Exception:
            await db.rollback()
            failed = await db.get(OutboxEvent, event_id)
            failed.status = 'failed'
            case = await db.get(Encounter, case_id)
            if case:
                case.status = 'review_required'
                case.active_snapshot_id = None
                db.add(AuditEvent(organization_id=case.organization_id, actor_id='processing-worker',
                    event_type='processing_failed', entity_type='case', entity_id=case_id,
                    metadata_json={'event_id': event_id, 'reason': 'processing_unavailable'}))
            await db.commit()
        return True


async def run(once):
    try:
        while True:
            handled = await process_one()
            if once and not handled:
                break
            if not handled:
                await asyncio.sleep(2)
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Drain pending events and exit')
    asyncio.run(run(parser.parse_args().once))
