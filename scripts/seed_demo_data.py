"""
Seed demo data for local exploration of Medical Billing & Coding Portal.
"""
import asyncio
from datetime import datetime, timezone
import uuid

from services.api.db.session import async_session_factory, engine
from services.api.db.base import Base
from services.api.db.models import (
    Organization,
    User,
    Patient,
    Encounter,
    ClinicalFact,
    CodeCandidate,
    RuleResult,
    AuditEvent,
)
from services.api.security.auth import hash_password


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        from sqlalchemy import select
        res = await session.execute(select(Organization).where(Organization.name == "Apex Health System"))
        if res.scalar_one_or_none():
            print("Demo data already seeded.")
            return

        # 1. Organization
        org_id = str(uuid.uuid4())
        org = Organization(
            id=org_id,
            name="Apex Health System",
            status="active",
        )
        session.add(org)

        # 2. Users
        coder = User(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            email="coder@apexhealth.org",
            password_hash=hash_password("CoderPassword123!"),
            role="Coder",
            status="active",
        )
        reviewer = User(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            email="reviewer@apexhealth.org",
            password_hash=hash_password("ReviewerPassword123!"),
            role="Reviewer",
            status="active",
        )
        readonly = User(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            email="readonly@apexhealth.org",
            password_hash=hash_password("ReadOnlyPassword123!"),
            role="Read-only",
            status="active",
        )
        session.add_all([coder, reviewer, readonly])

        # 3. Patient
        patient = Patient(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            external_reference="PT-ER-77492",
        )
        session.add(patient)

        # 4. Encounter
        enc_id = str(uuid.uuid4())
        enc = Encounter(
            id=enc_id,
            organization_id=org_id,
            patient_id=patient.id,
            service_date="2026-04-15",
            coding_domain="emergency_department",
            place_of_service="23",
            status="review",
        )
        session.add(enc)

        # 5. Clinical Facts
        facts = [
            ClinicalFact(
                id=str(uuid.uuid4()),
                encounter_id=enc_id,
                fact_type="chief_complaint",
                value_json={"text": "Acute right lower quadrant abdominal pain with fever"},
                extraction_model="deterministic",
                extraction_version="1.0",
            ),
            ClinicalFact(
                id=str(uuid.uuid4()),
                encounter_id=enc_id,
                fact_type="diagnosis",
                value_json={"text": "Acute appendicitis with localized peritonitis", "acuity": "acute"},
                extraction_model="deterministic",
                extraction_version="1.0",
            ),
            ClinicalFact(
                id=str(uuid.uuid4()),
                encounter_id=enc_id,
                fact_type="mdm",
                value_json={"level": "high", "text": "High complexity - surgical consult requested"},
                extraction_model="deterministic",
                extraction_version="1.0",
            ),
        ]
        session.add_all(facts)

        # 6. Code Candidates
        cand1 = CodeCandidate(
            id=str(uuid.uuid4()),
            encounter_id=enc_id,
            code_system="ICD-10-CM",
            code="K35.80",
            code_version="FY2026",
            status="candidate",
            rationale="Supported by acute appendicitis diagnosis with localized RLQ tenderness.",
            human_review_required=True,
        )
        cand2 = CodeCandidate(
            id=str(uuid.uuid4()),
            encounter_id=enc_id,
            code_system="CPT",
            code="99285",
            code_version="2026-MOCK",
            status="candidate",
            rationale="Emergency department visit, high medical decision making [MOCK].",
            human_review_required=True,
        )
        session.add_all([cand1, cand2])

        # 7. Rule Results
        rr1 = RuleResult(
            id=str(uuid.uuid4()),
            candidate_id=cand2.id,
            rule_id="RULE-ED-POS-23",
            status="PASS",
            message="POS 23 confirmed for Emergency Department visit code 99285.",
            source_reference="CMS Guidelines Section 10.4",
        )
        rr2 = RuleResult(
            id=str(uuid.uuid4()),
            candidate_id=cand2.id,
            rule_id="RULE-MDM-COMPLEXITY",
            status="PASS",
            message="High MDM documented and supported by surgical consult and CT imaging.",
            source_reference="AMA E/M Guidelines Table 2",
        )
        session.add_all([rr1, rr2])

        # 8. Audit Event
        audit = AuditEvent(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            actor_id=coder.id,
            event_type="encounter_created",
            entity_type="encounter",
            entity_id=enc_id,
            metadata_json={"coding_domain": "emergency_department", "service_date": "2026-04-15"},
        )
        session.add(audit)

        await session.commit()
        print("Demo data successfully seeded for Apex Health System!")


if __name__ == "__main__":
    asyncio.run(seed())
