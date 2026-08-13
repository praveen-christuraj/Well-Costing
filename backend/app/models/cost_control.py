"""Phase 8 staged cost-state batches, immutable postings, and reversal lineage."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.models.afe import AfeSnapshot
from app.models.estimates import EstimateVersion

COST_STATE_CHECK = "cost_state IN ('field_estimate','commitment','accrual','actual','forecast')"


class CostControlBatch(TimestampMixin, AuditMixin, Base):
    __tablename__ = "cost_control_batches"
    __table_args__ = (
        CheckConstraint(COST_STATE_CHECK, name="valid_cost_state"),
        CheckConstraint("source_type IN ('manual','excel')", name="valid_source_type"),
        CheckConstraint(
            "status IN ('invalid','validated','blocked','committed')", name="valid_status"
        ),
        Index("ix_cost_control_batches_state_status", "cost_state", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    estimate_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("estimate_versions.id", ondelete="CASCADE"), index=True
    )
    afe_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("afe_snapshots.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    cost_state: Mapped[str] = mapped_column(String(30), index=True)
    source_type: Mapped[str] = mapped_column(String(20))
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mapping_profile: Mapped[str] = mapped_column(String(100))
    mapping_version: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), index=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    valid_rows: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_rows: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    posted_rows: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    estimate_version: Mapped[EstimateVersion] = relationship(lazy="joined")
    afe_snapshot: Mapped[AfeSnapshot | None] = relationship(lazy="joined")
    staged_lines: Mapped[list["CostControlStagedLine"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="CostControlStagedLine.row_number",
        lazy="selectin",
    )
    errors: Mapped[list["CostControlBatchError"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", lazy="selectin"
    )
    post_attempts: Mapped[list["CostControlPostAttempt"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", lazy="selectin"
    )


class CostControlStagedLine(TimestampMixin, AuditMixin, Base):
    __tablename__ = "cost_control_staged_lines"
    __table_args__ = (
        UniqueConstraint("batch_id", "row_number", name="uq_cost_control_staged_batch_row"),
        CheckConstraint("row_number >= 1", name="positive_row_number"),
        CheckConstraint(
            "correction_kind IN ('original','reversal','adjustment')",
            name="valid_correction_kind",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("cost_control_batches.id", ondelete="CASCADE"), index=True
    )
    row_number: Mapped[int] = mapped_column(Integer)
    transaction_date: Mapped[date] = mapped_column(Date)
    source_document_type: Mapped[str] = mapped_column(String(50))
    source_document_reference: Mapped[str] = mapped_column(String(150))
    external_transaction_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cost_code: Mapped[str] = mapped_column(String(100), index=True)
    vendor_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    correction_kind: Mapped[str] = mapped_column(
        String(20), default="original", server_default="original"
    )
    reverses_transaction_id: Mapped[UUID | None] = mapped_column(nullable=True)
    raw_snapshot: Mapped[dict[str, object]] = mapped_column(JSON)

    batch: Mapped[CostControlBatch] = relationship(back_populates="staged_lines")


class CostControlBatchError(TimestampMixin, AuditMixin, Base):
    __tablename__ = "cost_control_batch_errors"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("cost_control_batches.id", ondelete="CASCADE"), index=True
    )
    row_number: Mapped[int] = mapped_column(Integer)
    column_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_code: Mapped[str] = mapped_column(String(100), index=True)
    message: Mapped[str] = mapped_column(Text)
    raw_value: Mapped[object | None] = mapped_column(JSON, nullable=True)

    batch: Mapped[CostControlBatch] = relationship(back_populates="errors")


class CostTransaction(TimestampMixin, AuditMixin, Base):
    __tablename__ = "cost_transactions"
    __table_args__ = (
        CheckConstraint(COST_STATE_CHECK, name="valid_cost_state"),
        CheckConstraint(
            "correction_kind IN ('original','reversal','adjustment')",
            name="valid_correction_kind",
        ),
        Index(
            "ix_cost_transactions_afe_state_date",
            "afe_snapshot_id",
            "cost_state",
            "transaction_date",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    posting_reference: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    afe_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("afe_snapshots.id", ondelete="RESTRICT"), index=True
    )
    source_batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("cost_control_batches.id", ondelete="RESTRICT"), index=True
    )
    source_staged_line_id: Mapped[UUID] = mapped_column(
        ForeignKey("cost_control_staged_lines.id", ondelete="RESTRICT"), unique=True, index=True
    )
    cost_state: Mapped[str] = mapped_column(String(30), index=True)
    transaction_date: Mapped[date] = mapped_column(Date, index=True)
    source_document_type: Mapped[str] = mapped_column(String(50))
    source_document_reference: Mapped[str] = mapped_column(String(150), index=True)
    external_transaction_id: Mapped[str | None] = mapped_column(
        String(150), nullable=True, index=True
    )
    cost_code: Mapped[str] = mapped_column(String(100), index=True)
    vendor_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    correction_kind: Mapped[str] = mapped_column(String(20))
    reverses_transaction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cost_transactions.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    afe_snapshot: Mapped[AfeSnapshot] = relationship(lazy="joined")
    source_batch: Mapped[CostControlBatch] = relationship(lazy="joined")
    source_staged_line: Mapped[CostControlStagedLine] = relationship(lazy="joined")
    reverses_transaction: Mapped["CostTransaction | None"] = relationship(
        remote_side="CostTransaction.id", lazy="joined"
    )


class CostControlPostAttempt(TimestampMixin, AuditMixin, Base):
    __tablename__ = "cost_control_post_attempts"
    __table_args__ = (
        CheckConstraint("status IN ('completed','blocked','denied','failed')", name="valid_status"),
        Index("ix_cost_control_post_attempts_batch_created", "batch_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("cost_control_batches.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSON)

    batch: Mapped[CostControlBatch] = relationship(back_populates="post_attempts", lazy="joined")
