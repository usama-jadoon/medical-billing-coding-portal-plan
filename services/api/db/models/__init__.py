import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    String, DateTime, ForeignKey, Integer, Boolean, JSON, Text, Table, Column, Index, Float
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from services.api.db.base import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    users: Mapped[List["User"]] = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    patients: Mapped[List["Patient"]] = relationship("Patient", back_populates="organization", cascade="all, delete-orphan")
    encounters: Mapped[List["Encounter"]] = relationship("Encounter", back_populates="organization", cascade="all, delete-orphan")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="organization", cascade="all, delete-orphan")
    audit_events: Mapped[List["AuditEvent"]] = relationship("AuditEvent", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="Coder", nullable=False)  # Owner, Admin, Coder, Reviewer, Read-only
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")
    reviews: Mapped[List["Review"]] = relationship("Review", back_populates="reviewer")


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    external_reference: Mapped[str] = mapped_column(String(255), nullable=False, index=True)  # Pseudonymous external MRN/identifier
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="patients")
    encounters: Mapped[List["Encounter"]] = relationship("Encounter", back_populates="patient", cascade="all, delete-orphan")


class Encounter(Base):
    __tablename__ = "encounters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    service_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    coding_domain: Mapped[str] = mapped_column(String(100), nullable=False)  # professional_office, emergency_department, etc.
    place_of_service: Mapped[str] = mapped_column(String(50), default="23", nullable=False)  # 11=Office, 23=ED, etc.
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False, index=True)  # draft, processing, review, approved, rejected
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    active_snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    __mapper_args__ = {"version_id_col": version}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="encounters")
    patient: Mapped["Patient"] = relationship("Patient", back_populates="encounters")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="encounter", cascade="all, delete-orphan")
    clinical_facts: Mapped[List["ClinicalFact"]] = relationship("ClinicalFact", back_populates="encounter", cascade="all, delete-orphan")
    code_candidates: Mapped[List["CodeCandidate"]] = relationship("CodeCandidate", back_populates="encounter", cascade="all, delete-orphan")
    reviews: Mapped[List["Review"]] = relationship("Review", back_populates="encounter", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    encounter_id: Mapped[str] = mapped_column(String(36), ForeignKey("encounters.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="documents")
    encounter: Mapped["Encounter"] = relationship("Encounter", back_populates="documents")
    pages: Mapped[List["DocumentPage"]] = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")
    evidence_items: Mapped[List["Evidence"]] = relationship("Evidence", back_populates="document", cascade="all, delete-orphan")


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ocr_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ocr_engine: Mapped[str] = mapped_column(String(100), default="local", nullable=False)
    ocr_version: Mapped[str] = mapped_column(String(50), default="1.0", nullable=False)

    document: Mapped["Document"] = relationship("Document", back_populates="pages")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quoted_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(100), default="clinical_snippet", nullable=False)
    region_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    bbox_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quote_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    evidence_role: Mapped[str] = mapped_column(String(50), default="SUPPORT", nullable=False)

    document: Mapped["Document"] = relationship("Document", back_populates="evidence_items")
    clinical_facts: Mapped[List["ClinicalFact"]] = relationship("ClinicalFact", back_populates="evidence")
    candidates: Mapped[List["CodeCandidate"]] = relationship("CodeCandidate", secondary="candidate_evidence", back_populates="supporting_evidence")


candidate_evidence = Table(
    "candidate_evidence",
    Base.metadata,
    Column("candidate_id", String(36), ForeignKey("code_candidates.id", ondelete="CASCADE"), primary_key=True),
    Column("evidence_id", String(36), ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True),
)


class ClinicalFact(Base):
    __tablename__ = "clinical_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    encounter_id: Mapped[str] = mapped_column(String(36), ForeignKey("encounters.id", ondelete="CASCADE"), nullable=False, index=True)
    fact_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # diagnosis, procedure, symptom, service_date, mdm, etc.
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    value_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    evidence_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True)
    extraction_model: Mapped[str] = mapped_column(String(100), default="deterministic", nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(50), default="1.0", nullable=False)

    encounter: Mapped["Encounter"] = relationship("Encounter", back_populates="clinical_facts")
    evidence: Mapped[Optional["Evidence"]] = relationship("Evidence", back_populates="clinical_facts")


class CodeCandidate(Base):
    __tablename__ = "code_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    encounter_id: Mapped[str] = mapped_column(String(36), ForeignKey("encounters.id", ondelete="CASCADE"), nullable=False, index=True)
    code_system: Mapped[str] = mapped_column(String(50), nullable=False)  # ICD-10-CM, CPT, HCPCS, CDT
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    code_version: Mapped[str] = mapped_column(String(50), default="FY2026", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="candidate", nullable=False, index=True)  # candidate, approved, rejected, modified
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    modifiers_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    encounter: Mapped["Encounter"] = relationship("Encounter", back_populates="code_candidates")
    supporting_evidence: Mapped[List["Evidence"]] = relationship("Evidence", secondary=candidate_evidence, back_populates="candidates")
    rule_results: Mapped[List["RuleResult"]] = relationship("RuleResult", back_populates="candidate", cascade="all, delete-orphan")


class RuleResult(Base):
    __tablename__ = "rule_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("code_candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # PASS, WARNING, FAIL, NOT_APPLICABLE
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_reference: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    candidate: Mapped["CodeCandidate"] = relationship("CodeCandidate", back_populates="rule_results")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    encounter_id: Mapped[str] = mapped_column(String(36), ForeignKey("encounters.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)  # accept, reject, edit, request_documentation, mark_uncertain
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    encounter: Mapped["Encounter"] = relationship("Encounter", back_populates="reviews")
    reviewer: Mapped["User"] = relationship("User", back_populates="reviews")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="audit_events")


class CaseSnapshot(Base):
    __tablename__ = "case_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("encounters.id", ondelete="CASCADE"), nullable=False, index=True)
    source_document_version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    service_date: Mapped[str] = mapped_column(String(10), nullable=False)
    domain_profile: Mapped[str] = mapped_column(String(100), nullable=False)
    code_system_release: Mapped[str] = mapped_column(String(50), default="FY2026", nullable=False)
    ruleset_version: Mapped[str] = mapped_column(String(50), default="2026.1", nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    event_id: Mapped[str] = mapped_column(String(36), default=generate_uuid, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(36), default=generate_uuid, nullable=False)
    causation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    producer: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False, index=True)  # pending, published, failed


class ValidationFinding(Base):
    __tablename__ = "validation_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("encounters.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("code_candidates.id", ondelete="CASCADE"), nullable=True, index=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # 1_catalog, 2_effective_date, 3_evidence, 4_documentation, 5_relationships, 6_modifiers, 7_ncci, 8_approval_gate
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)  # BLOCK, WARN, INFO
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    source_reference: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


# Alias Case to Encounter for single-user case terminology
Case = Encounter
