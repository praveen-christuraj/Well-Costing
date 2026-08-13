"""Auditable Excel import staging and error models."""

from uuid import UUID, uuid4

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin


class ImportBatch(TimestampMixin, AuditMixin, Base):
    __tablename__ = "import_batches"
    __table_args__ = (Index("ix_import_batches_entity_status", "entity_type", "status"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64))
    mapping_profile: Mapped[str] = mapped_column(String(100))
    mapping_version: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), index=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0)
    staged_rows: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)

    errors: Mapped[list["ImportError"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", lazy="selectin"
    )


class ImportError(TimestampMixin, AuditMixin, Base):
    __tablename__ = "import_errors"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), index=True
    )
    row_number: Mapped[int] = mapped_column(Integer)
    column_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_code: Mapped[str] = mapped_column(String(100), index=True)
    message: Mapped[str] = mapped_column(Text)
    raw_value: Mapped[object | None] = mapped_column(JSON, nullable=True)

    batch: Mapped[ImportBatch] = relationship(back_populates="errors")
