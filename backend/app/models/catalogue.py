"""Catalogue models: Services, Consumables (Mud Chemicals, Drill Bits, and the
Cement Additives / Fuel placeholder subcategories), Tangibles, their periodic
rate revisions, and the user-configurable dropdown lists.

All business entities use soft delete (is_deleted/deleted_at); rate revisions
are append-only history rows kept even after an item is soft-deleted.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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
from app.models.master_data import MasterDataSoftDeleteMixin


class CatalogueConfig(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """User-configurable dropdown lists (bit types, manufacturers, categories…).

    Each config_type owns one ordered set of values. ``system_seeded`` marks
    values shipped with the app (e.g. the four consumable subcategories); they
    can be renamed/reordered but not deleted, while user values can be removed.
    """

    __tablename__ = "catalogue_configs"
    __table_args__ = (
        UniqueConstraint(
            "config_type", "parent_value", "value",
            name="uq_catalogue_configs_type_parent_value",
        ),
        Index("ix_catalogue_configs_type_parent", "config_type", "parent_value"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    config_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    # Parent value for dependent dropdowns (e.g. a tangible subcategory stores
    # the category it belongs to). NULL for top-level config types and for
    # legacy values created before the dependency existed.
    parent_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    system_seeded: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )


class Service(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """Service catalogue entry (Services group / Service Type)."""

    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    service_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    service_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    service_type: Mapped[str] = mapped_column(String(50), default="Service", server_default="Service", nullable=False)
    provider_type: Mapped[str] = mapped_column(String(30), nullable=False)  # Inhouse / 3rd Party
    vendor_id: Mapped[int | None] = mapped_column(
        ForeignKey("vendor_suppliers.id"), nullable=True, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    vendor = relationship("VendorSupplier", lazy="joined")


class ConsumableSubcategory(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """Consumables subcategories: Mud Chemicals, Cement Additives, Fuel, Drill Bits.

    Each subcategory has a fixed short code used as the item-code prefix.
    Cement Additives and Fuel are declared here but have no item entry section
    yet (placeholder tabs). Mud Chemicals and Drill Bits carry full item grids.
    """

    __tablename__ = "consumable_subcategories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subcategory_code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    subcategory_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    entry_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class MudChemical(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """Mud Chemicals consumable item with periodic rate revisions."""

    __tablename__ = "mud_chemicals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chemical_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    part_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    chemical_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    uom: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    current_rate: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), server_default="0", nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    rates: Mapped[list["MudChemicalRate"]] = relationship(
        "MudChemicalRate",
        back_populates="chemical",
        lazy="selectin",
        order_by="desc(MudChemicalRate.effective_date)",
        cascade="all, delete-orphan",
    )


class MudChemicalRate(Base, TimestampMixin, AuditMixin):
    """Append-only rate revision for a mud chemical."""

    __tablename__ = "mud_chemical_rates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chemical_id: Mapped[int] = mapped_column(
        ForeignKey("mud_chemicals.id"), nullable=False, index=True
    )
    unit_rate: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    previous_rate: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), server_default="0", nullable=False)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    uom: Mapped[str | None] = mapped_column(String(50), nullable=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    chemical: Mapped[MudChemical] = relationship("MudChemical", back_populates="rates", lazy="joined")


class DrillBit(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """Drill Bits consumable item with periodic rate revisions."""

    __tablename__ = "drill_bits"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bit_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    bit_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    bit_type: Mapped[str] = mapped_column(String(100), nullable=False)
    model_no: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[str] = mapped_column(String(100), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(200), nullable=False)
    po_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    unit_rate_po: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"), server_default="0")
    cost_uplift: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("100"), server_default="100")
    final_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"), server_default="0")
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    rates: Mapped[list["DrillBitRate"]] = relationship(
        "DrillBitRate",
        back_populates="bit",
        lazy="selectin",
        order_by="desc(DrillBitRate.effective_date)",
        cascade="all, delete-orphan",
    )


class DrillBitRate(Base, TimestampMixin, AuditMixin):
    """Append-only rate revision for a drill bit."""

    __tablename__ = "drill_bit_rates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bit_id: Mapped[int] = mapped_column(ForeignKey("drill_bits.id"), nullable=False, index=True)
    unit_rate_po: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    cost_uplift: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("100"), server_default="100")
    final_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    po_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    bit: Mapped[DrillBit] = relationship("DrillBit", back_populates="rates", lazy="joined")


class Tangible(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """Tangibles catalogue item with periodic rate revisions."""

    __tablename__ = "tangibles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tangible_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    tangible_scope: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # Drilling / Completion / Others
    category: Mapped[str] = mapped_column(String(200), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(200), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(200), nullable=False)
    po_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tangible_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    uom: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    unit_rate_po: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"), server_default="0")
    cost_uplift: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("100"), server_default="100")
    final_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"), server_default="0")
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    rates: Mapped[list["TangibleRate"]] = relationship(
        "TangibleRate",
        back_populates="tangible",
        lazy="selectin",
        order_by="desc(TangibleRate.effective_date)",
        cascade="all, delete-orphan",
    )


class TangibleRate(Base, TimestampMixin, AuditMixin):
    """Append-only rate revision for a tangible."""

    __tablename__ = "tangible_rates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tangible_id: Mapped[int] = mapped_column(ForeignKey("tangibles.id"), nullable=False, index=True)
    unit_rate_po: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    cost_uplift: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("100"), server_default="100")
    final_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    po_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tangible: Mapped[Tangible] = relationship("Tangible", back_populates="rates", lazy="joined")
