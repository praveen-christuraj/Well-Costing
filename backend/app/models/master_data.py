"""Phase 2 configurable cost-library models."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin


class MasterDataMixin(TimestampMixin, AuditMixin):
    """Common auditable fields for reference records."""

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )


class Unit(MasterDataMixin, Base):
    __tablename__ = "units"

    symbol: Mapped[str | None] = mapped_column(String(30), nullable=True)


class Currency(MasterDataMixin, Base):
    __tablename__ = "currencies"

    symbol: Mapped[str | None] = mapped_column(String(10), nullable=True)


class CostCategory(MasterDataMixin, Base):
    __tablename__ = "cost_categories"

    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cost_categories.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    parent: Mapped["CostCategory | None"] = relationship(remote_side="CostCategory.id")


class CostCode(MasterDataMixin, Base):
    __tablename__ = "cost_codes"

    cost_category_id: Mapped[UUID] = mapped_column(
        ForeignKey("cost_categories.id", ondelete="RESTRICT"), index=True
    )
    cost_category: Mapped[CostCategory] = relationship(lazy="joined")


class Vendor(MasterDataMixin, Base):
    __tablename__ = "vendors"
    __table_args__ = (
        CheckConstraint(
            "vendor_type IN ('third_party','inhouse')",
            name="valid_vendor_type",
        ),
    )

    vendor_type: Mapped[str] = mapped_column(
        String(20), default="third_party", server_default="third_party", index=True
    )
    contact_person: Mapped[str | None] = mapped_column(String(150), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)


class ItemCategory(MasterDataMixin, Base):
    """Sub-classification for catalogue items (bits, casings, shoes and collars, wellheads)."""

    __tablename__ = "item_categories"
    __table_args__ = (
        CheckConstraint(
            "applies_to IN ('service','tangible','mud_chemical','cement_additive')",
            name="valid_item_category_scope",
        ),
    )

    applies_to: Mapped[str] = mapped_column(
        String(30), default="tangible", server_default="tangible", index=True
    )


class CatalogItem(TimestampMixin, AuditMixin, Base):
    """Shared identity for rate-bearing services, tangibles, materials, and equipment."""

    __tablename__ = "catalog_items"
    __table_args__ = (
        UniqueConstraint("item_type", "code", name="uq_catalog_items_type_code"),
        CheckConstraint(
            "item_type IN ('service','tangible','material','equipment',"
            "'mud_chemical','cement_additive')",
            name="valid_item_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    item_type: Mapped[str] = mapped_column(String(30), index=True)
    code: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cost_categories.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    cost_code_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cost_codes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    default_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("units.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )
    item_category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("item_categories.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    material_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    specification: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(150), nullable=True)

    cost_category: Mapped[CostCategory | None] = relationship(lazy="joined")
    cost_code: Mapped[CostCode | None] = relationship(lazy="joined")
    default_unit: Mapped[Unit | None] = relationship(lazy="joined")
    item_category: Mapped[ItemCategory | None] = relationship(lazy="joined")

    __mapper_args__: dict[str, object] = {  # noqa: RUF012
        "polymorphic_on": item_type,
        "polymorphic_identity": "catalog_item",
    }


class Service(CatalogItem):
    __tablename__ = "services"

    id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="CASCADE"), primary_key=True
    )
    __mapper_args__: dict[str, object] = {"polymorphic_identity": "service"}  # noqa: RUF012


class Tangible(CatalogItem):
    __tablename__ = "tangibles"

    id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="CASCADE"), primary_key=True
    )
    __mapper_args__: dict[str, object] = {"polymorphic_identity": "tangible"}  # noqa: RUF012


class Material(CatalogItem):
    __tablename__ = "materials"

    id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="CASCADE"), primary_key=True
    )
    __mapper_args__: dict[str, object] = {"polymorphic_identity": "material"}  # noqa: RUF012


class Equipment(CatalogItem):
    __tablename__ = "equipment"

    id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="CASCADE"), primary_key=True
    )
    __mapper_args__: dict[str, object] = {"polymorphic_identity": "equipment"}  # noqa: RUF012


class MudChemical(CatalogItem):
    __tablename__ = "mud_chemicals"

    id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="CASCADE"), primary_key=True
    )
    __mapper_args__: dict[str, object] = {"polymorphic_identity": "mud_chemical"}  # noqa: RUF012


class CementAdditive(CatalogItem):
    __tablename__ = "cement_additives"

    id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="CASCADE"), primary_key=True
    )
    __mapper_args__: dict[str, object] = {"polymorphic_identity": "cement_additive"}  # noqa: RUF012


class ServiceOrder(TimestampMixin, AuditMixin, Base):
    """Contract/service order under which a vendor supplies services."""

    __tablename__ = "service_orders"
    __table_args__ = (
        CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name="valid_service_order_range",
        ),
        CheckConstraint(
            "status IN ('draft','active','expired','cancelled')",
            name="valid_service_order_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    vendor_id: Mapped[UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="RESTRICT"), index=True
    )
    currency_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    valid_from: Mapped[date] = mapped_column(Date, index=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    contract_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    vendor: Mapped[Vendor] = relationship(lazy="joined")
    currency: Mapped[Currency | None] = relationship(lazy="joined")


class PurchaseOrder(TimestampMixin, AuditMixin, Base):
    """Purchase order under which tangibles or consumables are procured."""

    __tablename__ = "purchase_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','open','partially_received','closed','cancelled')",
            name="valid_purchase_order_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    vendor_id: Mapped[UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="RESTRICT"), index=True
    )
    currency_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    order_date: Mapped[date] = mapped_column(Date, index=True)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    order_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    status: Mapped[str] = mapped_column(
        String(25), default="draft", server_default="draft", index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    vendor: Mapped[Vendor] = relationship(lazy="joined")
    currency: Mapped[Currency | None] = relationship(lazy="joined")


class Rate(TimestampMixin, AuditMixin, Base):
    __tablename__ = "rates"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="non_negative_amount"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="valid_effective_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    item_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="RESTRICT"), index=True
    )
    vendor_id: Mapped[UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="RESTRICT"), index=True
    )
    currency_id: Mapped[UUID] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"), index=True
    )
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id", ondelete="RESTRICT"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    item: Mapped[CatalogItem] = relationship(lazy="joined")
    vendor: Mapped[Vendor] = relationship(lazy="joined")
    currency: Mapped[Currency] = relationship(lazy="joined")
    unit: Mapped[Unit] = relationship(lazy="joined")


class ServiceRateCard(TimestampMixin, AuditMixin, Base):
    """Effective-dated service rate card holding each operational rate as a column."""

    __tablename__ = "service_rate_cards"
    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="valid_service_rate_range",
        ),
        CheckConstraint(
            "operating_rate >= 0 AND standby_rate >= 0 "
            "AND mobilisation_rate >= 0 AND demobilisation_rate >= 0",
            name="non_negative_service_rates",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    service_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="RESTRICT"), index=True
    )
    vendor_id: Mapped[UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="RESTRICT"), index=True
    )
    service_order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("service_orders.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    currency_id: Mapped[UUID] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"), index=True
    )
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id", ondelete="RESTRICT"), index=True)
    hole_section: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
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
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    service: Mapped[CatalogItem] = relationship(lazy="joined")
    vendor: Mapped[Vendor] = relationship(lazy="joined")
    service_order: Mapped[ServiceOrder | None] = relationship(lazy="joined")
    currency: Mapped[Currency] = relationship(lazy="joined")
    unit: Mapped[Unit] = relationship(lazy="joined")


class ItemPrice(TimestampMixin, AuditMixin, Base):
    """Effective-dated purchase price for a tangible or consumable catalogue item."""

    __tablename__ = "item_prices"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="non_negative_unit_price"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="valid_item_price_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    item_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="RESTRICT"), index=True
    )
    vendor_id: Mapped[UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="RESTRICT"), index=True
    )
    purchase_order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    currency_id: Mapped[UUID] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"), index=True
    )
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id", ondelete="RESTRICT"), index=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    item: Mapped[CatalogItem] = relationship(lazy="joined")
    vendor: Mapped[Vendor] = relationship(lazy="joined")
    purchase_order: Mapped[PurchaseOrder | None] = relationship(lazy="joined")
    currency: Mapped[Currency] = relationship(lazy="joined")
    unit: Mapped[Unit] = relationship(lazy="joined")
