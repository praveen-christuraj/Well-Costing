"""Project, well, AFE, AFE section/phase breakdown, and AFE-line models."""

from datetime import date, datetime
from decimal import Decimal
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

from app.db.base import AuditMixin, Base, TimestampMixin
from app.domain.afe.rate_basis import RATE_BASES
from app.models.master_data import CatalogItem, CostCode, HoleSection, Unit, sql_in


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
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_wells_project_code"),
        CheckConstraint(
            "status IN ('planning','active','suspended','completed','abandoned')",
            name="valid_well_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rig_name: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="planning", server_default="planning", index=True
    )
    spud_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    rates_locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rate_lock_reference: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    project: Mapped[Project] = relationship(back_populates="wells", lazy="joined")
    afes: Mapped[list["Afe"]] = relationship(back_populates="well", lazy="selectin")


class DrillingPhase(TimestampMixin, AuditMixin, Base):
    """User-configurable drilling & completion operational phases."""

    __tablename__ = "drilling_phases"
    __table_args__ = (UniqueConstraint("code", name="uq_drilling_phases_code"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )


class Afe(TimestampMixin, AuditMixin, Base):
    """Authorisation for Expenditure — financial and technical well backbone."""

    __tablename__ = "afes"
    __table_args__ = (
        UniqueConstraint("well_id", "code", "revision_number", name="uq_afes_well_code_revision"),
        CheckConstraint("status IN ('draft','submitted')", name="valid_status"),
        CheckConstraint("revision_number >= 1", name="positive_revision"),
        CheckConstraint("budget_amount >= 0", name="non_negative_budget_amount"),
        CheckConstraint("total_planned_days >= 0", name="non_negative_total_planned_days"),
        CheckConstraint("total_planned_depth >= 0", name="non_negative_total_planned_depth"),
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
    budget_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    total_planned_days: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), server_default="0"
    )
    total_planned_depth: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), default=Decimal("0"), server_default="0"
    )
    depth_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("units.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    reopen_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reopened_by: Mapped[UUID | None] = mapped_column(nullable=True)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("afes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[UUID | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    well: Mapped[Well] = relationship(back_populates="afes", lazy="joined")
    depth_unit: Mapped[Unit | None] = relationship(foreign_keys=[depth_unit_id], lazy="joined")
    supersedes: Mapped["Afe | None"] = relationship(remote_side="Afe.id", lazy="joined")
    sections: Mapped[list["AfeSection"]] = relationship(
        back_populates="afe",
        cascade="all, delete-orphan",
        order_by="AfeSection.sequence",
        lazy="selectin",
    )
    items: Mapped[list["AfeLine"]] = relationship(
        back_populates="afe",
        cascade="all, delete-orphan",
        order_by="AfeLine.line_number",
        lazy="selectin",
    )
    audit_logs: Mapped[list["AfeAuditLog"]] = relationship(
        back_populates="afe",
        cascade="all, delete-orphan",
        order_by="AfeAuditLog.created_at.desc()",
        lazy="selectin",
    )


class AfeSection(TimestampMixin, AuditMixin, Base):
    """Section planning container for an AFE.

    A section is defined first (hole section plus the depth interval it covers);
    the operational phases that make up the section are then entered as child
    rows of :class:`AfeSectionPhase`. ``planned_days`` is derived on save as the
    sum of the planned days of the section's phases, and the AFE's
    ``total_planned_days`` is the sum over all sections.
    """

    __tablename__ = "afe_sections"
    __table_args__ = (
        CheckConstraint("sequence >= 1", name="positive_afe_section_sequence"),
        CheckConstraint("planned_days >= 0", name="non_negative_afe_section_days"),
        CheckConstraint(
            "planned_depth_from IS NULL OR planned_depth_to IS NULL"
            " OR planned_depth_to >= planned_depth_from",
            name="valid_afe_section_depth_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    afe_id: Mapped[UUID] = mapped_column(ForeignKey("afes.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    hole_section_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("hole_sections.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    # Legacy single-phase fields, retained for backward compatibility. New
    # writes carry the phases in ``afe_section_phases`` and ``planned_days`` is
    # recomputed from them; ``phase`` mirrors the first phase for old records.
    phase: Mapped[str] = mapped_column(
        String(100), default="Drilling", server_default="Drilling", index=True
    )
    planned_days: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), server_default="0"
    )
    planned_depth_from: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    planned_depth_to: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    depth_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("units.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    afe: Mapped[Afe] = relationship(back_populates="sections")
    hole_section: Mapped[HoleSection | None] = relationship(lazy="joined")
    depth_unit: Mapped[Unit | None] = relationship(lazy="joined")
    phases: Mapped[list["AfeSectionPhase"]] = relationship(
        back_populates="afe_section",
        cascade="all, delete-orphan",
        order_by="AfeSectionPhase.sequence",
        lazy="selectin",
    )


class AfeSectionPhase(TimestampMixin, AuditMixin, Base):
    """One operational phase of an AFE section with its planned days."""

    __tablename__ = "afe_section_phases"
    __table_args__ = (
        CheckConstraint("sequence >= 1", name="positive_afe_section_phase_sequence"),
        CheckConstraint("planned_days >= 0", name="non_negative_afe_section_phase_days"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    afe_section_id: Mapped[UUID] = mapped_column(
        ForeignKey("afe_sections.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    phase: Mapped[str] = mapped_column(
        String(100), default="Drilling", server_default="Drilling", index=True
    )
    planned_days: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), server_default="0"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    afe_section: Mapped[AfeSection] = relationship(back_populates="phases")


class AfeAuditLog(TimestampMixin, Base):
    """Audit log of changes and reopenings of an AFE."""

    __tablename__ = "afe_audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    afe_id: Mapped[UUID] = mapped_column(ForeignKey("afes.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(50), index=True)
    previous_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str] = mapped_column(String(30), index=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)

    afe: Mapped[Afe] = relationship(back_populates="audit_logs")


class AfeLine(TimestampMixin, AuditMixin, Base):
    __tablename__ = "afe_lines"
    __table_args__ = (
        UniqueConstraint("afe_id", "line_number", name="uq_afe_lines_afe_line"),
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
        CheckConstraint(f"rate_basis IN ({sql_in(RATE_BASES)})", name="valid_rate_basis"),
        CheckConstraint(
            "daily_consumption IS NULL OR daily_consumption >= 0",
            name="non_negative_daily_consumption",
        ),
        CheckConstraint(
            "computed_quantity IS NULL OR computed_quantity >= 0",
            name="non_negative_computed_quantity",
        ),
        CheckConstraint(
            "quantity_override_reason IS NULL OR length(trim(quantity_override_reason)) > 0",
            name="override_reason_not_blank",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    afe_id: Mapped[UUID] = mapped_column(ForeignKey("afes.id", ondelete="CASCADE"), index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    catalog_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="RESTRICT"), index=True
    )
    cost_code_id: Mapped[UUID] = mapped_column(
        ForeignKey("cost_codes.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id", ondelete="RESTRICT"), index=True)
    hole_section_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("hole_sections.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    # When true the line's rate applies to every section of the AFE, so the
    # planner enters it once instead of duplicating it per section. The
    # hole_section_id is ignored while this flag is set.
    applies_to_all_sections: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", index=True
    )
    rate_basis: Mapped[str] = mapped_column(
        String(20), default="daily", server_default="daily", index=True
    )
    daily_consumption: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    computed_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    quantity_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    afe: Mapped[Afe] = relationship(back_populates="items")
    catalog_item: Mapped[CatalogItem] = relationship(lazy="joined")
    cost_code: Mapped[CostCode] = relationship(lazy="joined")
    hole_section: Mapped[HoleSection | None] = relationship(lazy="joined")
    unit: Mapped[Unit] = relationship(foreign_keys=[unit_id], lazy="joined")
    depth_unit: Mapped[Unit | None] = relationship(foreign_keys=[depth_unit_id], lazy="joined")
