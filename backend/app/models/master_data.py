"""Phase 2 configurable cost-library models."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.categories import SecondaryCategory, TertiaryCategory

from app.db.base import AuditMixin, Base, TimestampMixin
from app.domain.afe.rate_basis import CONSUMABLE_RATE_BASES, SERVICE_RATE_BASES


def sql_in(values: tuple[str, ...]) -> str:
    """Render a tuple of literals as the body of a SQL ``IN (...)`` clause."""
    return ",".join(f"'{value}'" for value in values)


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


class HoleSection(MasterDataMixin, Base):
    """Configurable drilling hole section used for section-scoped service rates."""

    __tablename__ = "hole_sections"


class CostCategory(MasterDataMixin, Base):
    __tablename__ = "cost_categories"

    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cost_categories.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    secondary_category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("secondary_categories.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    secondary_category: Mapped["SecondaryCategory | None"] = relationship(lazy="joined")
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


class ItemSubCategory(MasterDataMixin, Base):
    """User-configurable second-level classification for catalogue items.

    A tangible such as a bit belongs to a category (``item_categories``) and a
    sub category (this table) — e.g. Bits > PDC bits, Casing > Surface casing.
    Sub categories are fully configurable, mirroring item categories, and are
    scoped with ``applies_to`` so the picker on each catalogue page only offers
    the values that make sense for it.
    """

    __tablename__ = "item_subcategories"
    __table_args__ = (
        CheckConstraint(
            "applies_to IN ('service','tangible','mud_chemical','cement_additive')",
            name="valid_item_subcategory_scope",
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
    sub_category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("item_subcategories.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    tertiary_category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tertiary_categories.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    tertiary_category: Mapped["TertiaryCategory | None"] = relationship(lazy="joined")
    material_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    specification: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(150), nullable=True)

    cost_category: Mapped[CostCategory | None] = relationship(lazy="joined")
    cost_code: Mapped[CostCode | None] = relationship(lazy="joined")
    default_unit: Mapped[Unit | None] = relationship(lazy="joined")
    item_category: Mapped[ItemCategory | None] = relationship(lazy="joined")
    sub_category: Mapped[ItemSubCategory | None] = relationship(lazy="joined")

    __mapper_args__: dict[str, object] = {  # noqa: RUF012
        "polymorphic_on": item_type,
        "polymorphic_identity": "catalog_item",
    }


class Service(CatalogItem):
    """A well service, categorised by how its rate is charged.

    ``rate_basis`` is the default pricing model negotiated for the service:
    daily rate, per hole section, per service, or a fixed rate. It is the
    catalogue-level classification; the actual amount is always agreed per well
    in the well rate book.
    """

    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint(
            f"rate_basis IN ({sql_in(SERVICE_RATE_BASES)})",
            name="valid_service_rate_basis",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="CASCADE"), primary_key=True
    )
    rate_basis: Mapped[str] = mapped_column(
        String(20), default="daily", server_default="daily", index=True
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
    """A drilling-fluid chemical.

    ``rate_basis`` records how the chemical is normally charged: ``per_unit``
    for a quantity bought outright, or ``daily_consumption`` when the planned
    volume is a consumption per day multiplied by the planned days.
    """

    __tablename__ = "mud_chemicals"
    __table_args__ = (
        CheckConstraint(
            f"rate_basis IN ({sql_in(CONSUMABLE_RATE_BASES)})",
            name="valid_mud_chemical_rate_basis",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="CASCADE"), primary_key=True
    )
    rate_basis: Mapped[str] = mapped_column(
        String(20), default="per_unit", server_default="per_unit", index=True
    )
    __mapper_args__: dict[str, object] = {"polymorphic_identity": "mud_chemical"}  # noqa: RUF012


class CementAdditive(CatalogItem):
    """A cement additive, charged per unit or on planned daily consumption."""

    __tablename__ = "cement_additives"
    __table_args__ = (
        CheckConstraint(
            f"rate_basis IN ({sql_in(CONSUMABLE_RATE_BASES)})",
            name="valid_cement_additive_rate_basis",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="CASCADE"), primary_key=True
    )
    rate_basis: Mapped[str] = mapped_column(
        String(20), default="per_unit", server_default="per_unit", index=True
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


class ItemPrice(TimestampMixin, AuditMixin, Base):
    """Effective-dated master rate for a tangible or consumable catalogue item.

    Services deliberately have no master rate: their price is negotiated per
    well and lives in the well rate book. Tangible rates are revised centrally
    and periodically, so a rate is never edited in place — ``revise`` closes the
    current row and inserts the next revision, keeping ``supersedes_id``
    lineage and appending a :class:`RateRevision` audit entry.
    """

    __tablename__ = "item_prices"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="non_negative_unit_price"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="valid_item_price_range",
        ),
        CheckConstraint("revision_number >= 1", name="positive_item_price_revision"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    item_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="RESTRICT"), index=True
    )
    vendor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=True, index=True
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
    revision_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    supersedes_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("item_prices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    item: Mapped[CatalogItem] = relationship(lazy="joined")
    vendor: Mapped[Vendor | None] = relationship(lazy="joined")
    purchase_order: Mapped[PurchaseOrder | None] = relationship(lazy="joined")
    currency: Mapped[Currency] = relationship(lazy="joined")
    unit: Mapped[Unit] = relationship(lazy="joined")
    supersedes: Mapped["ItemPrice | None"] = relationship(remote_side="ItemPrice.id")


class RateRevision(TimestampMixin, AuditMixin, Base):
    """Append-only log of every master rate change.

    One row per creation, revision, or withdrawal of a master rate, holding the
    amount before and after, the date the change takes effect, the actor, and
    the stated reason. Wells already drilling are unaffected by these rows —
    their rates were copied into the well rate book when the item was picked —
    so this log answers "what did the catalogue say, when, and who changed it".
    """

    __tablename__ = "rate_revisions"
    __table_args__ = (
        CheckConstraint("scope IN ('item_price')", name="valid_rate_revision_scope"),
        CheckConstraint(
            "change_type IN ('created','revised','withdrawn')",
            name="valid_rate_revision_change_type",
        ),
        CheckConstraint("revision_number >= 1", name="positive_rate_revision_number"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scope: Mapped[str] = mapped_column(
        String(20), default="item_price", server_default="item_price", index=True
    )
    item_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="CASCADE"), index=True
    )
    item_price_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("item_prices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    previous_price_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("item_prices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    vendor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    currency_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("units.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    change_type: Mapped[str] = mapped_column(String(20), index=True)
    revision_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    previous_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    new_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, index=True, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    item: Mapped[CatalogItem] = relationship(lazy="joined")
    vendor: Mapped[Vendor | None] = relationship(lazy="joined")
    currency: Mapped[Currency | None] = relationship(lazy="joined")
    unit: Mapped[Unit | None] = relationship(lazy="joined")
    item_price: Mapped[ItemPrice | None] = relationship(lazy="joined", foreign_keys=[item_price_id])
