"""AFE (Authorization For Expenditure) persistence models.

The AFE is the backbone of the costing application: a **well-scoped** budget
that hangs off one rig + well pair and is estimated in three groups —
Services, Consumables and Tangibles — before it is submitted and approved.

    Rig 1 ──< Well * ──< Afe * ──< AfeServiceLine * ──< rates / charge lines
                              └──< AfeConsumableLine *
                              └──< AfeTangibleLine *

Only the AFE itself is soft-deleteable (``is_deleted`` / ``deleted_at``): it is
the user's "entry", so a delete moves it to the Deleted Entries tab where it can
be restored or permanently removed. Its configuration lines are part of the AFE
and are replaced wholesale when an estimate is saved (the same lifecycle the
well configuration uses), so they carry no independent soft delete.

Sections and phases are referenced by their **master data** ids
(``hole_sections`` / ``phases``) rather than by ``well_sections`` rows, because
saving a well configuration replaces those rows wholesale. Referencing the
stable master ids keeps an AFE's scope valid across well-configuration re-saves;
the estimation engine resolves them against the current configuration.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.models.master_data import MasterDataSoftDeleteMixin
from app.models.rig_well import Rig, Well


class Afe(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """A well-scoped Authorization For Expenditure.

    ``status`` is the AFE lifecycle — ``draft`` on creation, then ``submitted``
    and ``approved``. It is *displayed* on the AFE tab but only ever changed
    from the AFE Cost Estimation tab.
    """

    __tablename__ = "afes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    afe_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    afe_name: Mapped[str] = mapped_column(String(200), nullable=False)
    afe_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # Drilling | Completion
    rig_id: Mapped[int] = mapped_column(ForeignKey("rigs.id"), nullable=False, index=True)
    well_id: Mapped[int] = mapped_column(ForeignKey("wells.id"), nullable=False, index=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", nullable=False, index=True
    )  # draft | submitted | approved
    status_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rig: Mapped[Rig] = relationship("Rig", lazy="joined")
    well: Mapped[Well] = relationship("Well", lazy="joined")

    service_lines: Mapped[list["AfeServiceLine"]] = relationship(
        "AfeServiceLine",
        back_populates="afe",
        lazy="selectin",
        order_by="AfeServiceLine.sort_order",
        cascade="all, delete-orphan",
    )
    consumable_lines: Mapped[list["AfeConsumableLine"]] = relationship(
        "AfeConsumableLine",
        back_populates="afe",
        lazy="selectin",
        order_by="AfeConsumableLine.sort_order",
        cascade="all, delete-orphan",
    )
    tangible_lines: Mapped[list["AfeTangibleLine"]] = relationship(
        "AfeTangibleLine",
        back_populates="afe",
        lazy="selectin",
        order_by="AfeTangibleLine.sort_order",
        cascade="all, delete-orphan",
    )


class AfeServiceLine(Base, TimestampMixin, AuditMixin):
    """One service added to an AFE with its rate charging criteria.

    ``charging_basis`` is ``Daily Rate``, ``Per Service Rate`` or
    ``Per Section Rate``. The optional ``section_id`` / ``phase_id`` narrow the
    line to part of the well configuration; both are master-data ids.
    """

    __tablename__ = "afe_service_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    afe_id: Mapped[int] = mapped_column(ForeignKey("afes.id"), nullable=False, index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), nullable=False, index=True)
    charging_basis: Mapped[str] = mapped_column(String(30), nullable=False)
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("hole_sections.id"), nullable=True, index=True
    )
    phase_id: Mapped[int | None] = mapped_column(ForeignKey("phases.id"), nullable=True, index=True)
    per_service_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0", nullable=False
    )
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    afe: Mapped[Afe] = relationship("Afe", back_populates="service_lines", lazy="joined")
    service = relationship("Service", lazy="joined")

    rates: Mapped[list["AfeServiceRate"]] = relationship(
        "AfeServiceRate",
        back_populates="line",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    charge_lines: Mapped[list["AfeServiceChargeLine"]] = relationship(
        "AfeServiceChargeLine",
        back_populates="line",
        lazy="selectin",
        order_by="AfeServiceChargeLine.sort_order",
        cascade="all, delete-orphan",
    )
    section_rates: Mapped[list["AfeServiceSectionRate"]] = relationship(
        "AfeServiceSectionRate",
        back_populates="line",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class AfeServiceRate(Base, TimestampMixin, AuditMixin):
    """One charge category's unit rate on a service line (the rate card).

    The eight charge categories are constant; only the ones with a rate are
    stored. Mobilization, Demobilization and Fixed Charge are one-time amounts,
    the others are per-day rates.
    """

    __tablename__ = "afe_service_rates"
    __table_args__ = (
        UniqueConstraint("line_id", "category", name="uq_afe_service_rates_line_category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(
        ForeignKey("afe_service_lines.id"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    unit_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0", nullable=False
    )

    line: Mapped[AfeServiceLine] = relationship("AfeServiceLine", back_populates="rates", lazy="joined")


class AfeServiceChargeLine(Base, TimestampMixin, AuditMixin):
    """A day-based quantity entered against one charge category.

    ``quantity`` is entered either in decimal days (``0.2``, ``0.73``) or in
    hours (0-24) as recorded by ``quantity_unit``; the engine converts hours to
    days and prices the row as ``days x unit rate``.
    """

    __tablename__ = "afe_service_charge_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(
        ForeignKey("afe_service_lines.id"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), server_default="0", nullable=False
    )
    quantity_unit: Mapped[str] = mapped_column(
        String(10), default="days", server_default="days", nullable=False
    )  # days | hours
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    line: Mapped[AfeServiceLine] = relationship(
        "AfeServiceLine", back_populates="charge_lines", lazy="joined"
    )


class AfeServiceSectionRate(Base, TimestampMixin, AuditMixin):
    """A constant amount charged for one section (optionally one phase)."""

    __tablename__ = "afe_service_section_rates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(
        ForeignKey("afe_service_lines.id"), nullable=False, index=True
    )
    section_id: Mapped[int] = mapped_column(ForeignKey("hole_sections.id"), nullable=False, index=True)
    phase_id: Mapped[int | None] = mapped_column(ForeignKey("phases.id"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0", nullable=False
    )

    line: Mapped[AfeServiceLine] = relationship(
        "AfeServiceLine", back_populates="section_rates", lazy="joined"
    )


class AfeConsumableLine(Base, TimestampMixin, AuditMixin):
    """A consumable estimated for a section and/or a phase of the well.

    ``item_kind`` selects the master-data list the item comes from
    (``mud_chemical`` or ``drill_bit``); ``item_id`` therefore has no single
    foreign key, so the code/name/UOM/rate are snapshotted alongside it.
    """

    __tablename__ = "afe_consumable_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    afe_id: Mapped[int] = mapped_column(ForeignKey("afes.id"), nullable=False, index=True)
    item_kind: Mapped[str] = mapped_column(String(20), nullable=False)  # mud_chemical | drill_bit
    item_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    item_code: Mapped[str] = mapped_column(String(50), nullable=False)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), default=Decimal("1"), server_default="1", nullable=False
    )
    captured_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0", nullable=False
    )
    override_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    uom: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("hole_sections.id"), nullable=True, index=True
    )
    phase_id: Mapped[int | None] = mapped_column(ForeignKey("phases.id"), nullable=True, index=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    afe: Mapped[Afe] = relationship("Afe", back_populates="consumable_lines", lazy="joined")


class AfeTangibleLine(Base, TimestampMixin, AuditMixin):
    """A tangible for the well; the rate is captured from the master data and
    may be overridden per AFE."""

    __tablename__ = "afe_tangible_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    afe_id: Mapped[int] = mapped_column(ForeignKey("afes.id"), nullable=False, index=True)
    tangible_id: Mapped[int] = mapped_column(ForeignKey("tangibles.id"), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), default=Decimal("1"), server_default="1", nullable=False
    )
    captured_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0", nullable=False
    )
    override_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    uom: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    afe: Mapped[Afe] = relationship("Afe", back_populates="tangible_lines", lazy="joined")
    tangible = relationship("Tangible", lazy="joined")
