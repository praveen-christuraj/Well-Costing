"""Immutable baseline AFE snapshots and audited creation attempts."""

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
from app.models.calculations import EstimateCalculation
from app.models.estimates import EstimateVersion


class AfeSnapshot(TimestampMixin, AuditMixin, Base):
    __tablename__ = "afe_snapshots"
    __table_args__ = (
        UniqueConstraint("estimate_version_id", name="uq_afe_snapshots_estimate_version"),
        CheckConstraint("snapshot_type = 'baseline'", name="baseline_only"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    afe_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    snapshot_type: Mapped[str] = mapped_column(
        String(20), default="baseline", server_default="baseline"
    )
    estimate_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("estimate_versions.id", ondelete="RESTRICT"), index=True
    )
    calculation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("estimate_calculations.id", ondelete="RESTRICT"), index=True
    )
    issue_date: Mapped[date] = mapped_column(Date)
    estimate_code: Mapped[str] = mapped_column(String(100))
    estimate_title: Mapped[str] = mapped_column(String(255))
    afe_code: Mapped[str] = mapped_column(String(100))
    project_code: Mapped[str] = mapped_column(String(100))
    well_code: Mapped[str] = mapped_column(String(100))
    currency_code: Mapped[str] = mapped_column(String(3))
    engine_version: Mapped[str] = mapped_column(String(50))
    rule_set_version: Mapped[str] = mapped_column(String(50))
    base_total: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    contingency_total: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    escalation_total: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    grand_total: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    source_snapshot: Mapped[dict[str, object]] = mapped_column(JSON)

    estimate_version: Mapped[EstimateVersion] = relationship(lazy="joined")
    calculation_run: Mapped[EstimateCalculation] = relationship(lazy="joined")
    lines: Mapped[list["AfeSnapshotLine"]] = relationship(
        back_populates="afe_snapshot",
        cascade="all, delete-orphan",
        order_by="AfeSnapshotLine.line_number",
        lazy="selectin",
    )


class AfeSnapshotLine(TimestampMixin, AuditMixin, Base):
    __tablename__ = "afe_snapshot_lines"
    __table_args__ = (
        UniqueConstraint("afe_snapshot_id", "line_number", name="uq_afe_snapshot_lines_number"),
        CheckConstraint("line_number >= 1", name="positive_line_number"),
        CheckConstraint("quantity >= 0", name="non_negative_quantity"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    afe_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("afe_snapshots.id", ondelete="CASCADE"), index=True
    )
    source_estimate_item_id: Mapped[UUID] = mapped_column(index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    item_code: Mapped[str] = mapped_column(String(100))
    item_description: Mapped[str] = mapped_column(String(255))
    item_type: Mapped[str] = mapped_column(String(30))
    cost_code: Mapped[str] = mapped_column(String(100))
    cost_category_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vendor_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unit_code: Mapped[str] = mapped_column(String(50))
    rate_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    rate_currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    base_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    contingency_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    escalation_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4))

    afe_snapshot: Mapped[AfeSnapshot] = relationship(back_populates="lines")


class AfeSnapshotAttempt(TimestampMixin, AuditMixin, Base):
    __tablename__ = "afe_snapshot_attempts"
    __table_args__ = (
        CheckConstraint("status IN ('completed','blocked','denied','failed')", name="valid_status"),
        Index("ix_afe_snapshot_attempts_version_created", "estimate_version_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    estimate_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("estimate_versions.id", ondelete="CASCADE"), index=True
    )
    resulting_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("afe_snapshots.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    requested_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    eligibility_snapshot: Mapped[dict[str, object]] = mapped_column(JSON)

    estimate_version: Mapped[EstimateVersion] = relationship(lazy="joined")
    resulting_snapshot: Mapped[AfeSnapshot | None] = relationship(lazy="joined")
