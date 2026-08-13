"""Configurable enterprise hierarchy and well-costing administration models."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.models.master_data import CatalogItem, CostCategory, CostCode, Rate, Unit

LIFECYCLE_CHECK = "lifecycle_status IN ('draft','published','retired')"


class EnterpriseNodeType(TimestampMixin, AuditMixin, Base):
    __tablename__ = "enterprise_node_types"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    level_order: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class EnterpriseHierarchyRule(TimestampMixin, AuditMixin, Base):
    __tablename__ = "enterprise_hierarchy_rules"
    __table_args__ = (
        UniqueConstraint("parent_type_id", "child_type_id", name="uq_enterprise_hierarchy_rule"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    parent_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("enterprise_node_types.id", ondelete="RESTRICT"), index=True
    )
    child_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("enterprise_node_types.id", ondelete="RESTRICT"), index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    parent_type: Mapped[EnterpriseNodeType] = relationship(
        foreign_keys=[parent_type_id], lazy="joined"
    )
    child_type: Mapped[EnterpriseNodeType] = relationship(
        foreign_keys=[child_type_id], lazy="joined"
    )


class EnterpriseNode(TimestampMixin, AuditMixin, Base):
    __tablename__ = "enterprise_nodes"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    node_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("enterprise_node_types.id", ondelete="RESTRICT"), index=True
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("enterprise_nodes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    node_type: Mapped[EnterpriseNodeType] = relationship(lazy="joined")
    parent: Mapped["EnterpriseNode | None"] = relationship(
        remote_side="EnterpriseNode.id", lazy="joined"
    )


class CostBreakdownStructure(TimestampMixin, AuditMixin, Base):
    __tablename__ = "cost_breakdown_structures"
    __table_args__ = (
        UniqueConstraint("code", "version_number", name="uq_cost_breakdown_structure_version"),
        CheckConstraint(LIFECYCLE_CHECK, name="valid_lifecycle"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(200))
    version_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    lifecycle_status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    nodes: Mapped[list["CostBreakdownNode"]] = relationship(
        back_populates="structure", cascade="all, delete-orphan", lazy="selectin"
    )


class CostBreakdownNode(TimestampMixin, AuditMixin, Base):
    __tablename__ = "cost_breakdown_nodes"
    __table_args__ = (UniqueConstraint("structure_id", "code", name="uq_cost_breakdown_node_code"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    structure_id: Mapped[UUID] = mapped_column(
        ForeignKey("cost_breakdown_structures.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cost_breakdown_nodes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cost_category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cost_categories.id", ondelete="RESTRICT"), nullable=True
    )
    cost_code_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cost_codes.id", ondelete="RESTRICT"), nullable=True
    )
    structure: Mapped[CostBreakdownStructure] = relationship(back_populates="nodes")
    parent: Mapped["CostBreakdownNode | None"] = relationship(remote_side="CostBreakdownNode.id")
    cost_category: Mapped[CostCategory | None] = relationship(lazy="joined")
    cost_code: Mapped[CostCode | None] = relationship(lazy="joined")


class RateBook(TimestampMixin, AuditMixin, Base):
    __tablename__ = "rate_books"
    __table_args__ = (
        UniqueConstraint("code", "version_number", name="uq_rate_book_version"),
        CheckConstraint(LIFECYCLE_CHECK, name="valid_lifecycle"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(200))
    version_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    lifecycle_status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft"
    )
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entries: Mapped[list["RateBookEntry"]] = relationship(
        back_populates="rate_book", cascade="all, delete-orphan", lazy="selectin"
    )


class RateBookEntry(TimestampMixin, AuditMixin, Base):
    __tablename__ = "rate_book_entries"
    __table_args__ = (UniqueConstraint("rate_book_id", "rate_id", name="uq_rate_book_entry"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    rate_book_id: Mapped[UUID] = mapped_column(
        ForeignKey("rate_books.id", ondelete="CASCADE"), index=True
    )
    rate_id: Mapped[UUID] = mapped_column(ForeignKey("rates.id", ondelete="RESTRICT"), index=True)
    rate_book: Mapped[RateBook] = relationship(back_populates="entries")
    rate: Mapped[Rate] = relationship(lazy="joined")


class EstimateTemplate(TimestampMixin, AuditMixin, Base):
    __tablename__ = "estimate_templates"
    __table_args__ = (
        UniqueConstraint("code", "version_number", name="uq_estimate_template_version"),
        CheckConstraint(LIFECYCLE_CHECK, name="valid_lifecycle"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(200))
    version_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    lifecycle_status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    lines: Mapped[list["EstimateTemplateLine"]] = relationship(
        back_populates="template", cascade="all, delete-orphan", lazy="selectin"
    )


class EstimateTemplateLine(TimestampMixin, AuditMixin, Base):
    __tablename__ = "estimate_template_lines"
    __table_args__ = (
        UniqueConstraint("template_id", "line_number", name="uq_estimate_template_line"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    template_id: Mapped[UUID] = mapped_column(
        ForeignKey("estimate_templates.id", ondelete="CASCADE"), index=True
    )
    line_number: Mapped[int] = mapped_column(Integer)
    catalog_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="RESTRICT")
    )
    cost_code_id: Mapped[UUID] = mapped_column(ForeignKey("cost_codes.id", ondelete="RESTRICT"))
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id", ondelete="RESTRICT"))
    default_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    template: Mapped[EstimateTemplate] = relationship(back_populates="lines")
    catalog_item: Mapped[CatalogItem] = relationship(lazy="joined")
    cost_code: Mapped[CostCode] = relationship(lazy="joined")
    unit: Mapped[Unit] = relationship(lazy="joined")


class ReportingMapping(TimestampMixin, AuditMixin, Base):
    __tablename__ = "reporting_mappings"
    __table_args__ = (
        UniqueConstraint(
            "target_system",
            "source_dimension",
            "source_value",
            "version_number",
            name="uq_reporting_mapping_version",
        ),
        CheckConstraint(LIFECYCLE_CHECK, name="valid_lifecycle"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    target_system: Mapped[str] = mapped_column(String(100), index=True)
    source_dimension: Mapped[str] = mapped_column(String(100))
    source_value: Mapped[str] = mapped_column(String(200))
    target_value: Mapped[str] = mapped_column(String(200))
    version_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    lifecycle_status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
