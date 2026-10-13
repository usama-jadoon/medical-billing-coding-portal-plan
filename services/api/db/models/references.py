"""Versioned operational references, separate from tenant clinical records."""
from datetime import date, datetime
from sqlalchemy import String, Date, DateTime, Boolean, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from services.api.db.base import Base
from services.api.db.models import generate_uuid, utc_now


class CatalogSyncRun(Base):
    __tablename__ = 'catalog_sync_runs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    sync_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    manifest_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class MedicalCodeCatalog(Base):
    __tablename__ = 'medical_code_catalog'
    __table_args__ = (UniqueConstraint('sync_run_id', 'code_system', 'code', 'release', 'effective_from'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    sync_run_id: Mapped[str] = mapped_column(ForeignKey('catalog_sync_runs.id'), index=True)
    source: Mapped[str] = mapped_column(String(100))
    code_system: Mapped[str] = mapped_column(String(20))
    code: Mapped[str] = mapped_column(String(30), index=True)
    release: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_from: Mapped[date] = mapped_column(Date)
    # Exclusive: the first date on which this version is no longer valid.
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    replacement_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CoveragePolicyReference(Base):
    __tablename__ = 'coverage_policy_references'
    __table_args__ = (UniqueConstraint('sync_run_id', 'source', 'document_type', 'document_id', 'version'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    sync_run_id: Mapped[str] = mapped_column(ForeignKey('catalog_sync_runs.id'), index=True)
    source: Mapped[str] = mapped_column(String(100))
    document_type: Mapped[str] = mapped_column(String(30))
    document_id: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(100))
    payload_json: Mapped[dict] = mapped_column(JSON)
    sha256: Mapped[str] = mapped_column(String(64))


class AuditLog(Base):
    """Global worker audit: no patient data or invented tenant identity."""
    __tablename__ = 'catalog_sync_audit_logs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    event: Mapped[str] = mapped_column(String(100), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    metadata_json: Mapped[dict] = mapped_column(JSON)
