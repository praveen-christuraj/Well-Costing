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


class CatalogItem(TimestampMixin, AuditMixin, Base):
    """Shared identity for rate-bearing services, tangibles, materials, and equipment."""

    __tablename__ = "catalog_items"
    __table_args__ = (
        UniqueConstraint("item_type", "code", name="uq_catalog_items_type_code"),
        CheckConstraint(
            "item_type IN ('service','tangible','material','equipment')",
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

    cost_category: Mapped[CostCategory | None] = relationship(lazy="joined")
    cost_code: Mapped[CostCode | None] = relationship(lazy="joined")
    default_unit: Mapped[Unit | None] = relationship(lazy="joined")

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
