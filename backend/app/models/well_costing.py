"""Well-scoped rate book and out-of-AFE register.

Master rates are revised periodically while up to twenty rigs drill at once. A
well therefore never reads a master rate at cost time: the rate is copied into
the well when the item is picked, and the copy is frozen when the AFE baseline
is issued. Deviations after that point are recorded as out-of-AFE entries
rather than by editing an approved AFE.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
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
from app.models.afe import Well
from app.models.afe_snapshots import AfeSnapshot
from app.models.master_data import (
    CatalogItem,
    CostCode,
    Currency,
    HoleSection,
    ItemPrice,
    Unit,
    Vendor,
)

RATE_STATUS_CHECK = "status IN ('draft','locked')"
RATE_ORIGIN_CHECK = "origin IN ('well_planning','unplanned')"
UNPLANNED_STATUS_CHECK = "status IN ('draft','submitted','approved','rejected','cancelled')"
UNPLANNED_REASON_CHECK = (
    "reason_code IN ('emergency','operational_necessity','scope_change',"
    "'afe_omission','rate_revision','other')"
)


class WellRateBookMixin(TimestampMixin, AuditMixin):
    """Fields shared by the service and tangible halves of a well rate book."""

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    vendor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    currency_id: Mapped[UUID] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"), index=True
    )
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id", ondelete="RESTRICT"), index=True)
    origin: Mapped[str] = mapped_column(
        String(20), default="well_planning", server_default="well_planning", index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", index=True
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revision_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    contract_reference: Mapped[str | None] = mapped_column(String(150), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )


class WellServiceRate(WellRateBookMixin, Base):
    """A service this well will use, priced for this well only.

    Services carry no master rate: the user types the negotiated rate when the
    service is added to the well, and that rate applies until the well is
    complete regardless of later central revisions.
    """

    __tablename__ = "well_service_rates"
    __table_args__ = (
        UniqueConstraint(
            "well_id",
            "service_id",
            "hole_section_id",
            "rate_basis",
            name="uq_well_service_rates_scope",
        ),
        CheckConstraint(RATE_STATUS_CHECK, name="valid_well_service_rate_status"),
        CheckConstraint(RATE_ORIGIN_CHECK, name="valid_well_service_rate_origin"),
        CheckConstraint(
            "rate_basis IN ('daily','per_service','per_section','fixed')",
            name="valid_well_service_rate_basis",
        ),
        CheckConstraint(
            "operating_rate >= 0 AND standby_rate >= 0 "
            "AND mobilisation_rate >= 0 AND demobilisation_rate >= 0 "
            "AND personnel_operating_rate >= 0 AND personnel_standby_rate >= 0 "
            "AND other_rate >= 0",
            name="non_negative_well_service_rates",
        ),
        Index("ix_well_service_rates_well_status", "well_id", "status"),
    )

    well_id: Mapped[UUID] = mapped_column(ForeignKey("wells.id", ondelete="CASCADE"), index=True)
    service_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="RESTRICT"), index=True
    )
    hole_section_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("hole_sections.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    rate_basis: Mapped[str] = mapped_column(
        String(20), default="daily", server_default="daily", index=True
    )
    operating_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    standby_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    mobilisation_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    demobilisation_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    personnel_operating_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    personnel_standby_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    other_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )

    # Eager loading is deliberately ``selectin`` rather than ``joined``: these
    # rows sit three levels deep in the catalogue graph, and joined loading
    # multiplies out into a query wide enough to hit SQLite's join limit.
    well: Mapped[Well] = relationship(lazy="select")
    service: Mapped[CatalogItem] = relationship(lazy="selectin")
    hole_section: Mapped[HoleSection | None] = relationship(lazy="selectin")
    vendor: Mapped[Vendor | None] = relationship(lazy="selectin")
    currency: Mapped[Currency] = relationship(lazy="selectin")
    unit: Mapped[Unit] = relationship(lazy="selectin")


class WellTangibleRate(WellRateBookMixin, Base):
    """A tangible this well will consume, at the rate copied from master data.

    ``master_unit_rate`` keeps the catalogue value as it stood when the item was
    picked, so an override is visible as a delta rather than hidden in history.
    """

    __tablename__ = "well_tangible_rates"
    __table_args__ = (
        UniqueConstraint("well_id", "tangible_id", name="uq_well_tangible_rates_scope"),
        CheckConstraint(RATE_STATUS_CHECK, name="valid_well_tangible_rate_status"),
        CheckConstraint(RATE_ORIGIN_CHECK, name="valid_well_tangible_rate_origin"),
        CheckConstraint("unit_rate >= 0", name="non_negative_well_unit_rate"),
        Index("ix_well_tangible_rates_well_status", "well_id", "status"),
    )

    well_id: Mapped[UUID] = mapped_column(ForeignKey("wells.id", ondelete="CASCADE"), index=True)
    tangible_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="RESTRICT"), index=True
    )
    unit_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    master_price_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("item_prices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    master_unit_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    master_effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_overridden: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", index=True
    )
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    well: Mapped[Well] = relationship(lazy="select")
    tangible: Mapped[CatalogItem] = relationship(lazy="selectin")
    master_price: Mapped[ItemPrice | None] = relationship(lazy="select")
    vendor: Mapped[Vendor | None] = relationship(lazy="selectin")
    currency: Mapped[Currency] = relationship(lazy="selectin")
    unit: Mapped[Unit] = relationship(lazy="selectin")


class WellRateRevision(TimestampMixin, AuditMixin, Base):
    """Append-only history of every change to a well's rate book."""

    __tablename__ = "well_rate_revisions"
    __table_args__ = (
        CheckConstraint("scope IN ('service','tangible')", name="valid_well_revision_scope"),
        CheckConstraint(
            "change_type IN ('added','rate_revised','details_updated','locked',"
            "'deactivated','unplanned_added')",
            name="valid_well_revision_change_type",
        ),
        Index("ix_well_rate_revisions_well_created", "well_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    well_id: Mapped[UUID] = mapped_column(ForeignKey("wells.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(String(20), index=True)
    well_service_rate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("well_service_rates.id", ondelete="CASCADE"), nullable=True, index=True
    )
    well_tangible_rate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("well_tangible_rates.id", ondelete="CASCADE"), nullable=True, index=True
    )
    item_code: Mapped[str] = mapped_column(String(100), index=True)
    item_name: Mapped[str] = mapped_column(String(255))
    change_type: Mapped[str] = mapped_column(String(30), index=True)
    revision_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    previous_rates: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    new_rates: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)

    well: Mapped[Well] = relationship(lazy="select")


class WellUnplannedItem(TimestampMixin, AuditMixin, Base):
    """A service or tangible consumed outside the approved AFE and well plan.

    The approved AFE stays immutable; this register carries the deviation, its
    justification, and its approval trail, and feeds the well rate book once
    approved so the same rate is reused for the rest of the operation.
    """

    __tablename__ = "well_unplanned_items"
    __table_args__ = (
        UniqueConstraint("well_id", "reference", name="uq_well_unplanned_items_reference"),
        CheckConstraint(UNPLANNED_STATUS_CHECK, name="valid_unplanned_status"),
        CheckConstraint(UNPLANNED_REASON_CHECK, name="valid_unplanned_reason_code"),
        CheckConstraint(
            "item_kind IN ('service','tangible','other')", name="valid_unplanned_item_kind"
        ),
        CheckConstraint("quantity >= 0 AND unit_rate >= 0", name="non_negative_unplanned_amounts"),
        Index("ix_well_unplanned_items_well_status", "well_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    well_id: Mapped[UUID] = mapped_column(ForeignKey("wells.id", ondelete="CASCADE"), index=True)
    reference: Mapped[str] = mapped_column(String(50), index=True)
    afe_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("afe_snapshots.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    item_kind: Mapped[str] = mapped_column(String(20), index=True)
    catalog_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    item_description: Mapped[str] = mapped_column(String(255))
    well_service_rate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("well_service_rates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    well_tangible_rate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("well_tangible_rates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cost_code_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cost_codes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    vendor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    currency_id: Mapped[UUID] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"), index=True
    )
    unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("units.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    unit_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    reason_code: Mapped[str] = mapped_column(String(30), index=True)
    justification: Mapped[str] = mapped_column(Text)
    incurred_on: Mapped[date] = mapped_column(Date, index=True)
    source_document_reference: Mapped[str | None] = mapped_column(String(150), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", index=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_by: Mapped[UUID | None] = mapped_column(nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[UUID | None] = mapped_column(nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    well: Mapped[Well] = relationship(lazy="select")
    afe_snapshot: Mapped[AfeSnapshot | None] = relationship(lazy="select")
    catalog_item: Mapped[CatalogItem | None] = relationship(lazy="selectin")
    cost_code: Mapped[CostCode | None] = relationship(lazy="selectin")
    vendor: Mapped[Vendor | None] = relationship(lazy="selectin")
    currency: Mapped[Currency] = relationship(lazy="selectin")
    unit: Mapped[Unit | None] = relationship(lazy="selectin")
    well_service_rate: Mapped[WellServiceRate | None] = relationship(lazy="select")
    well_tangible_rate: Mapped[WellTangibleRate | None] = relationship(lazy="select")
