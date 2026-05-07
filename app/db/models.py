from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


PK_TYPE = BigInteger().with_variant(Integer, "sqlite")


class BatchRun(Base):
    __tablename__ = "batch_runs"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    triggered_by: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    total_files_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_files_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    duplicate_files_skipped: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    failed_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_references_found: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    documents: Mapped[list["Document"]] = relationship(back_populates="batch_run")
    processing_logs: Mapped[list["ProcessingLog"]] = relationship(back_populates="batch_run")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_content_hash", "content_hash", unique=True),
        Index("ix_documents_document_number", "document_number"),
        Index("ix_documents_source_file_present", "source_file_present"),
        Index("ix_documents_retry_requires_reupload", "retry_requires_reupload"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    batch_run_id: Mapped[int | None] = mapped_column(
        PK_TYPE, ForeignKey("batch_runs.id", ondelete="SET NULL"), nullable=True
    )
    original_file_name: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(PK_TYPE, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processing_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_error_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moved_to_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    retention_mode: Mapped[str] = mapped_column(
        String(50), nullable=False, default="retain_failed_only", server_default="retain_failed_only"
    )
    source_file_present: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="0")
    source_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_requires_reupload: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="0")
    last_ingestion_used_cached_result: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="0"
    )

    batch_run: Mapped[BatchRun | None] = relationship(back_populates="documents")
    references: Mapped[list["DocumentReference"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    processing_logs: Mapped[list["ProcessingLog"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    ingestions: Mapped[list["DocumentIngestion"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentIngestion(Base):
    __tablename__ = "document_ingestions"
    __table_args__ = (
        Index("ix_document_ingestions_document_id", "document_id"),
        Index("ix_document_ingestions_batch_run_id", "batch_run_id"),
        Index("ix_document_ingestions_uploaded_at", "uploaded_at"),
        Index("ix_document_ingestions_ingestion_status", "ingestion_status"),
        Index("ix_document_ingestions_used_cached_result", "used_cached_result"),
        Index("ix_document_ingestions_cleanup_due_at", "cleanup_due_at"),
        Index("ix_document_ingestions_source_file_present", "source_file_present"),
        Index("ix_document_ingestions_retry_source_available", "retry_source_available"),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        PK_TYPE, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    batch_run_id: Mapped[int | None] = mapped_column(
        PK_TYPE, ForeignKey("batch_runs.id", ondelete="SET NULL"), nullable=True
    )
    uploaded_file_name: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ingestion_status: Mapped[str] = mapped_column(String(50), nullable=False, default="uploaded")
    used_cached_result: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="0")
    force_reprocess_requested: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="0"
    )
    retention_mode_used: Mapped[str] = mapped_column(String(50), nullable=False)
    source_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_file_present: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="0")
    source_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cleanup_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_source_available: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="0"
    )
    error_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped[Document] = relationship(back_populates="ingestions")


class DocumentReference(Base):
    __tablename__ = "document_references"
    __table_args__ = (
        Index("ix_document_references_document_id", "document_id"),
        Index("ix_document_references_resolution_status", "resolution_status"),
        Index("ix_document_references_source_type", "source_type"),
        UniqueConstraint(
            "document_id",
            "page_number",
            "raw_reference",
            "source_type",
            name="uq_document_references_document_page_raw_source",
        ),
    )

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        PK_TYPE, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_class: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_reference: Mapped[str] = mapped_column(Text, nullable=False)
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_status: Mapped[str] = mapped_column(String(50), nullable=False, default="raw_only")
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution_error_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped[Document] = relationship(back_populates="references")


class UserAudit(Base):
    __tablename__ = "users_audit"

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    action_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProcessingLog(Base):
    __tablename__ = "processing_logs"
    __table_args__ = (Index("ix_processing_logs_document_id", "document_id"),)

    id: Mapped[int] = mapped_column(PK_TYPE, primary_key=True, autoincrement=True)
    batch_run_id: Mapped[int | None] = mapped_column(
        PK_TYPE, ForeignKey("batch_runs.id", ondelete="SET NULL"), nullable=True
    )
    document_id: Mapped[int | None] = mapped_column(
        PK_TYPE, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True
    )
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    batch_run: Mapped[BatchRun | None] = relationship(back_populates="processing_logs")
    document: Mapped[Document | None] = relationship(back_populates="processing_logs")
