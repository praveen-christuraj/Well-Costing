"""Phase 4 estimate-build persistence models; calculated amounts remain null."""

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.models.master_data import CatalogItem, CostCategory, CostCode, Currency, Rate, Unit, Vendor
from app.models.requirements import RequirementItem, WellRequirement


class CostEstimate(TimestampMixin, AuditMixin, Base):
    __tablename__ = "cost_estimates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    requirement_id: Mapped[UUID] = mapped_column(
        ForeignKey("well_requirements.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    currency_id: Mapped[UUID] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"), index=True
    )
    current_version_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    requirement: Mapped[WellRequirement] = relationship(lazy="joined")
    currency: Mapped[Currency] = relationship(lazy="joined")
    versions: Mapped[list["EstimateVersion"]] = relationship(
        back_populates="estimate", cascade="all, delete-orphan", lazy="selectin"
    )


class EstimateVersion(TimestampMixin, AuditMixin, Base):
    __tablename__ = "estimate_versions"
    __table_args__ = (
        UniqueConstraint("estimate_id", "version_number", name="uq_estimate_versions_number"),
        CheckConstraint("version_number >= 1", name="positive_version"),
        CheckConstraint("status IN ('draft','pending_calculation')", name="valid_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    estimate_id: Mapped[UUID] = mapped_column(
        ForeignKey("cost_estimates.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(30), default="pending_calculation", server_default="pending_calculation", index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    contingency_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    escalation_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    grand_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)

    estimate: Mapped[CostEstimate] = relationship(back_populates="versions", lazy="joined")
    items: Mapped[list["EstimateItem"]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="EstimateItem.line_number",
        lazy="selectin",
    )
    assumptions: Mapped[list["EstimateAssumption"]] = relationship(
        back_populates="version", cascade="all, delete-orphan", lazy="selectin"
    )


class EstimateItem(TimestampMixin, AuditMixin, Base):
    __tablename__ = "estimate_items"
    __table_args__ = (
        UniqueConstraint(
            "estimate_version_id", "line_number", name="uq_estimate_items_version_line"
        ),
        CheckConstraint("quantity >= 0", name="non_negative_quantity"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    estimate_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("estimate_versions.id", ondelete="CASCADE"), index=True
    )
    line_number: Mapped[int] = mapped_column(Integer)
    requirement_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("requirement_items.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    catalog_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="RESTRICT"), index=True
    )
    cost_code_id: Mapped[UUID] = mapped_column(
        ForeignKey("cost_codes.id", ondelete="RESTRICT"), index=True
    )
    vendor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    rate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("rates.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id", ondelete="RESTRICT"), index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    contingency_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    escalation_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)

    version: Mapped[EstimateVersion] = relationship(back_populates="items")
    requirement_item: Mapped[RequirementItem | None] = relationship(lazy="joined")
    catalog_item: Mapped[CatalogItem] = relationship(lazy="joined")
    cost_code: Mapped[CostCode] = relationship(lazy="joined")
    vendor: Mapped[Vendor | None] = relationship(lazy="joined")
    rate: Mapped[Rate | None] = relationship(lazy="joined")
    unit: Mapped[Unit] = relationship(lazy="joined")


class EstimateAssumption(TimestampMixin, AuditMixin, Base):
    __tablename__ = "estimate_assumptions"
    __table_args__ = (
        CheckConstraint(
            "contingency_percent IS NULL OR contingency_percent >= 0",
            name="non_negative_contingency",
        ),
        CheckConstraint(
            "escalation_percent IS NULL OR escalation_percent >= 0", name="non_negative_escalation"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    estimate_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("estimate_versions.id", ondelete="CASCADE"), index=True
    )
    cost_category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cost_categories.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    contingency_percent: Mapped[Decimal | None] = mapped_column(Numeric(9, 4), nullable=True)
    escalation_percent: Mapped[Decimal | None] = mapped_column(Numeric(9, 4), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    version: Mapped[EstimateVersion] = relationship(back_populates="assumptions")
    cost_category: Mapped[CostCategory | None] = relationship(lazy="joined")
