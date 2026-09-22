from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from services.api.db.session import get_db
from services.api.db.models import AuditEvent, User
from services.api.security.tenant import get_current_user, get_current_tenant
from services.api.security.permissions import require_roles, Roles

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_audit_events(
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
):
    # Only Admin or Owner or Reviewer can view audit trail
    require_roles([Roles.OWNER, Roles.ADMIN, Roles.REVIEWER, Roles.CODER])(current_user)

    stmt = (
        select(AuditEvent)
        .where(AuditEvent.organization_id == tenant_id)
        .order_by(desc(AuditEvent.created_at))
        .limit(limit)
    )
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)

    res = await db.execute(stmt)
    events = res.scalars().all()

    return [
        {
            "id": ev.id,
            "organization_id": ev.organization_id,
            "actor_id": ev.actor_id,
            "event_type": ev.event_type,
            "entity_type": ev.entity_type,
            "entity_id": ev.entity_id,
            "metadata": ev.metadata_json,
            "created_at": ev.created_at.isoformat(),
        }
        for ev in events
    ]
