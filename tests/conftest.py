import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from services.api.config import settings
from services.api.db.base import Base
from services.api.db.session import get_db
from services.api.db.models import Organization, User, Patient, Encounter
from services.api.security.auth import hash_password, create_access_token
from services.api.app import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def isolate_local_runtime(monkeypatch, tmp_path):
    """Tests must not use a workstation's live feeds, queue or document storage."""
    from services.api import storage
    monkeypatch.setattr(settings, 'CMS_REFERENCE_DB', '')
    monkeypatch.setattr(settings, 'CMS_POLICY_SYNC_ENABLED', False)
    monkeypatch.setattr(settings, 'POLICY_SYNC_ENABLED', False)
    monkeypatch.setattr(settings, 'QUEUE_BACKEND', 'sync')
    monkeypatch.setattr(settings, 'LOCAL_STORAGE_PATH', str(tmp_path / 'documents'))
    monkeypatch.setattr(storage, '_default_storage', None)

test_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    future=True,
)

test_session_factory = async_sessionmaker(
    test_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_session_factory() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def seed_data(db_session: AsyncSession):
    # Organization 1
    org1 = Organization(id="org-1-uuid", name="Apex Health Systems")
    # Organization 2
    org2 = Organization(id="org-2-uuid", name="Beacon Medical Group")
    db_session.add_all([org1, org2])
    await db_session.flush()

    # Users in Org 1
    user_coder = User(
        id="user-coder-1",
        organization_id=org1.id,
        email="coder@apexhealth.org",
        password_hash=hash_password("CoderPassword123!"),
        role="Coder",
        status="active",
    )
    user_reviewer = User(
        id="user-reviewer-1",
        organization_id=org1.id,
        email="reviewer@apexhealth.org",
        password_hash=hash_password("ReviewerPassword123!"),
        role="Reviewer",
        status="active",
    )
    user_readonly = User(
        id="user-readonly-1",
        organization_id=org1.id,
        email="readonly@apexhealth.org",
        password_hash=hash_password("ReadOnlyPassword123!"),
        role="Read-only",
        status="active",
    )

    # User in Org 2
    user_org2_coder = User(
        id="user-coder-2",
        organization_id=org2.id,
        email="coder@beaconmed.org",
        password_hash=hash_password("Org2Password123!"),
        role="Coder",
        status="active",
    )

    db_session.add_all([user_coder, user_reviewer, user_readonly, user_org2_coder])
    await db_session.flush()

    # Patient & Encounter in Org 1
    patient1 = Patient(
        id="pat-1",
        organization_id=org1.id,
        external_reference="SYNTH-PAT-001",
    )
    db_session.add(patient1)
    await db_session.flush()

    encounter1 = Encounter(
        id="enc-1",
        organization_id=org1.id,
        patient_id=patient1.id,
        service_date="2026-09-22",
        coding_domain="emergency_department",
        place_of_service="23",
        status="draft",
    )
    db_session.add(encounter1)

    # Patient & Encounter in Org 2
    patient2 = Patient(
        id="pat-2",
        organization_id=org2.id,
        external_reference="SYNTH-PAT-002",
    )
    db_session.add(patient2)
    await db_session.flush()

    encounter2 = Encounter(
        id="enc-2",
        organization_id=org2.id,
        patient_id=patient2.id,
        service_date="2026-09-22",
        coding_domain="professional_office",
        place_of_service="11",
        status="draft",
    )
    db_session.add(encounter2)

    await db_session.commit()

    # Pre-generate tokens
    token_coder_org1 = create_access_token({"sub": user_coder.id, "org": org1.id, "role": user_coder.role})
    token_reviewer_org1 = create_access_token({"sub": user_reviewer.id, "org": org1.id, "role": user_reviewer.role})
    token_readonly_org1 = create_access_token({"sub": user_readonly.id, "org": org1.id, "role": user_readonly.role})
    token_coder_org2 = create_access_token({"sub": user_org2_coder.id, "org": org2.id, "role": user_org2_coder.role})

    return {
        "org1": org1,
        "org2": org2,
        "user_coder": user_coder,
        "user_reviewer": user_reviewer,
        "user_readonly": user_readonly,
        "user_org2_coder": user_org2_coder,
        "encounter1": encounter1,
        "encounter2": encounter2,
        "tokens": {
            "coder_org1": token_coder_org1,
            "reviewer_org1": token_reviewer_org1,
            "readonly_org1": token_readonly_org1,
            "coder_org2": token_coder_org2,
        },
    }
