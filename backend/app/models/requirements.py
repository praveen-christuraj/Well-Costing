"""Phase 3 project, well, requirement, and requirement-item models."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.models.master_data import CatalogItem, CostCode, Unit


class Project(TimestampMixin, AuditMixin, Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    wells: Mapped[list["Well"]] = relationship(back_populates="project", lazy="selectin")


class Well(TimestampMixin, AuditMixin, Base):
    __tablename__ = "wells"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_wells_project_code"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    project: Mapped[Project] = relationship(back_populates="wells", lazy="joined")
    requirements: Mapped[list["WellRequirement"]] = relationship(
        back_populates="well", lazy="selectin"
    )


class WellRequirement(TimestampMixin, AuditMixin, Base):
    __tablename__ = "well_requirements"
    __table_args__ = (
        UniqueConstraint(
            "well_id", "code", "revision_number", name="uq_requirements_well_code_revision"
        ),
        CheckConstraint("status IN ('draft','submitted')", name="valid_status"),
        CheckConstraint("revision_number >= 1", name="positive_revision"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    well_id: Mapped[UUID] = mapped_column(ForeignKey("wells.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="draft", server_default="draft", index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    supersedes_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("well_requirements.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    well: Mapped[Well] = relationship(back_populates="requirements", lazy="joined")
    supersedes: Mapped["WellRequirement | None"] = relationship(
        remote_side="WellRequirement.id", lazy="joined"
    )
    items: Mapped[list["RequirementItem"]] = relationship(
        back_populates="requirement",
        cascade="all, delete-orphan",
        order_by="RequirementItem.line_number",
        lazy="selectin",
    )


class RequirementItem(TimestampMixin, AuditMixin, Base):
    __tablename__ = "requirement_items"
    __table_args__ = (
        UniqueConstraint(
            "requirement_id", "line_number", name="uq_requirement_items_requirement_line"
        ),
        CheckConstraint("line_number >= 1", name="positive_line_number"),
        CheckConstraint("quantity >= 0", name="non_negative_quantity"),
        CheckConstraint(
            "planned_duration_days IS NULL OR planned_duration_days >= 0",
            name="non_negative_duration",
        ),
        CheckConstraint(
            "planned_depth_from IS NULL OR planned_depth_to IS NULL "
            "OR planned_depth_to >= planned_depth_from",
            name="valid_depth_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    requirement_id: Mapped[UUID] = mapped_column(
        ForeignKey("well_requirements.id", ondelete="CASCADE"), index=True
    )
    line_number: Mapped[int] = mapped_column(Integer)
    catalog_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="RESTRICT"), index=True
    )
    cost_code_id: Mapped[UUID] = mapped_column(
        ForeignKey("cost_codes.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id", ondelete="RESTRICT"), index=True)
    section_name: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    planned_duration_days: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    planned_depth_from: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    planned_depth_to: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    depth_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("units.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    requirement: Mapped[WellRequirement] = relationship(back_populates="items")
    catalog_item: Mapped[CatalogItem] = relationship(lazy="joined")
    cost_code: Mapped[CostCode] = relationship(lazy="joined")
    unit: Mapped[Unit] = relationship(foreign_keys=[unit_id], lazy="joined")
    depth_unit: Mapped[Unit | None] = relationship(foreign_keys=[depth_unit_id], lazy="joined")
