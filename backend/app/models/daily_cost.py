"""Daily cost tracking models: services hours, chemical usage, and daily operational logs."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.models.afe import Afe, Well
from app.models.categories import WellActivity
from app.models.master_data import CatalogItem, CostCode, HoleSection, Unit, Vendor


class DailyCostEntry(TimestampMixin, AuditMixin, Base):
    """Daily operational cost record for a well on a specific date."""

    __tablename__ = "daily_cost_entries"
    __table_args__ = (
        CheckConstraint(
            "current_depth IS NULL OR current_depth >= 0", name="non_negative_current_depth"
        ),
        CheckConstraint(
            "daily_progress IS NULL OR daily_progress >= 0", name="non_negative_daily_progress"
        ),
        CheckConstraint("total_services_cost >= 0", name="non_negative_total_services_cost"),
        CheckConstraint("total_consumables_cost >= 0", name="non_negative_total_consumables_cost"),
        CheckConstraint("total_daily_cost >= 0", name="non_negative_total_daily_cost"),
        Index("ix_daily_cost_entries_well_date", "well_id", "entry_date"),
        UniqueConstraint(
            "well_id",
            "entry_date",
            "sub_activity_id",
            name="uq_daily_cost_entries_well_date_activity",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    well_id: Mapped[UUID] = mapped_column(ForeignKey("wells.id", ondelete="CASCADE"), index=True)
    afe_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("afes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    hole_section_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("hole_sections.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    phase: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    sub_activity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("well_activities.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    current_depth: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    daily_progress: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    operational_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_services_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    total_consumables_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    total_daily_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    cumulative_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    well: Mapped[Well] = relationship(lazy="joined")
    afe: Mapped[Afe | None] = relationship(lazy="joined")
    hole_section: Mapped[HoleSection | None] = relationship(lazy="joined")
    sub_activity: Mapped[WellActivity | None] = relationship(lazy="joined")
    services: Mapped[list["DailyCostServiceLine"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", lazy="selectin"
    )
    consumables: Mapped[list["DailyCostConsumableLine"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", lazy="selectin"
    )


class DailyCostServiceLine(TimestampMixin, AuditMixin, Base):
    """A service utilised during a daily operational window."""

    __tablename__ = "daily_cost_service_lines"
    __table_args__ = (
        CheckConstraint("service_hours >= 0 AND service_hours <= 24", name="valid_service_hours"),
        CheckConstraint("operating_days >= 0", name="non_negative_operating_days"),
        CheckConstraint("unit_rate >= 0", name="non_negative_service_unit_rate"),
        CheckConstraint("amount >= 0", name="non_negative_service_amount"),
        CheckConstraint(
            "override_rate IS NULL OR override_rate >= 0",
            name="non_negative_service_override_rate",
        ),
        CheckConstraint(
            "service_type IN ('operation','standby','mobilisation','demobilisation',"
            "'personnel_operation','personnel_standby','other')",
            name="valid_service_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    daily_cost_entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("daily_cost_entries.id", ondelete="CASCADE"), index=True
    )
    service_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="RESTRICT"), index=True
    )
    cost_code_id: Mapped[UUID] = mapped_column(
        ForeignKey("cost_codes.id", ondelete="RESTRICT"), index=True
    )
    vendor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    hole_section_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("hole_sections.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    sub_activity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("well_activities.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    service_type: Mapped[str] = mapped_column(
        String(30), default="operation", server_default="operation", index=True
    )
    service_hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), default=Decimal("24.0"), server_default="24.0"
    )
    operating_days: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), default=Decimal("1.0"), server_default="1.0"
    )
    rate_basis: Mapped[str] = mapped_column(
        String(20), default="daily", server_default="daily", index=True
    )
    unit_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    override_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    entry: Mapped[DailyCostEntry] = relationship(back_populates="services")
    service: Mapped[CatalogItem] = relationship(lazy="joined")
    cost_code: Mapped[CostCode] = relationship(lazy="joined")
    vendor: Mapped[Vendor | None] = relationship(lazy="joined")
    hole_section: Mapped[HoleSection | None] = relationship(lazy="joined")
    sub_activity: Mapped[WellActivity | None] = relationship(lazy="joined")


class DailyCostConsumableLine(TimestampMixin, AuditMixin, Base):
    """Chemicals and additives consumed during a daily operational window."""

    __tablename__ = "daily_cost_consumable_lines"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="non_negative_consumable_quantity"),
        CheckConstraint("unit_rate >= 0", name="non_negative_consumable_unit_rate"),
        CheckConstraint("amount >= 0", name="non_negative_consumable_amount"),
        CheckConstraint(
            "override_rate IS NULL OR override_rate >= 0",
            name="non_negative_consumable_override_rate",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    daily_cost_entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("daily_cost_entries.id", ondelete="CASCADE"), index=True
    )
    consumable_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="RESTRICT"), index=True
    )
    cost_code_id: Mapped[UUID] = mapped_column(
        ForeignKey("cost_codes.id", ondelete="RESTRICT"), index=True
    )
    vendor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    sub_activity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("well_activities.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id", ondelete="RESTRICT"), index=True)
    unit_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    override_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    entry: Mapped[DailyCostEntry] = relationship(back_populates="consumables")
    consumable: Mapped[CatalogItem] = relationship(lazy="joined")
    cost_code: Mapped[CostCode] = relationship(lazy="joined")
    vendor: Mapped[Vendor | None] = relationship(lazy="joined")
    unit: Mapped[Unit] = relationship(lazy="joined")
    sub_activity: Mapped[WellActivity | None] = relationship(lazy="joined")
