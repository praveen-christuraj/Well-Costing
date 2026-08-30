"""Daily Cost persistence models.

The daily cost sheet is the operational counterpart of the AFE: the AFE plans
the money for a well, the daily sheet records what was actually spent on one
**rig + well + date**.

    Rig 1 ──< Well * ──< DailyCostEntry * ──< DailyCostServiceLine *
                                     ├──< DailyCostConsumableLine *
                                     └──< DailyCostTangibleLine *

Only the entry (the user's "day") is soft-deleteable: a delete moves it to the
Deleted Entries tab where it can be restored or permanently removed. Its lines
belong to the day and are replaced wholesale when the day is saved — the same
lifecycle the AFE estimate and the well configuration use.

Every line carries its **scope** (``section_id`` / ``phase_id`` from the well
configuration and ``sub_activity_id`` from the Well Sub Activities page) and
its own ``captured_rate`` / ``override_rate`` pair, so one service can appear
several times on the same day — different sub activities, different charge
categories — without the amounts interfering.

Sections and phases are referenced by their **master data** ids
(``hole_sections`` / ``phases``) rather than by ``well_sections`` rows, for the
same reason the AFE does it: saving a well configuration replaces those rows
wholesale, so the stable master ids keep a recorded day valid afterwards.

Reconciliation (planned)
------------------------

Actual cost is captured daily but reconciled weekly — or whenever required —
before it is compared with the AFE. The entry therefore already carries the
reconciliation hooks (``reconciliation_status``, ``reconciliation_ref``,
``reconciled_at``, ``reconciled_by``). The daily cost module writes them as
``pending`` and never changes them; the reconciliation module that lands later
stamps them, so no second migration is needed.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.models.afe import Afe
from app.models.catalogue import Service, Tangible
from app.models.master_data import MasterDataSoftDeleteMixin
from app.models.rig_well import Rig, Well
from app.models.well_sub_activity import WellSubActivity


class DailyCostEntry(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """One day of cost for one well.

    ``(well_id, cost_date)`` is unique: the user picks the rig, the well and
    the date and then enters that day, so a second sheet for the same well and
    date is a duplicate. ``daily_cost_code`` is generated as
    ``<well_code>/<YYYYMMDD>`` and gives the day a stable reference for
    exports, reports and audit log entries.

    ``status`` is ``draft`` while the day is being entered and ``submitted``
    once the user signs it off; only a draft can be edited.
    """

    __tablename__ = "daily_cost_entries"
    __table_args__ = (
        UniqueConstraint("well_id", "cost_date", name="uq_daily_cost_entries_well_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    daily_cost_code: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    rig_id: Mapped[int] = mapped_column(ForeignKey("rigs.id"), nullable=False, index=True)
    well_id: Mapped[int] = mapped_column(ForeignKey("wells.id"), nullable=False, index=True)
    cost_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    #: The AFE that supplied the rate card and that this day is compared with.
    afe_id: Mapped[int | None] = mapped_column(ForeignKey("afes.id"), nullable=True, index=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", nullable=False, index=True
    )  # draft | submitted
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Reconciliation middle layer (stamped later by the reconciliation module).
    reconciliation_status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", nullable=False, index=True
    )  # pending | reconciled
    reconciliation_ref: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reconciled_by: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    rig: Mapped[Rig] = relationship("Rig", lazy="joined")
    well: Mapped[Well] = relationship("Well", lazy="joined")
    #: Deliberately *not* joined: an AFE carries three eagerly loaded
    #: collections of its own, and pulling them into every daily-cost query
    #: explodes the load graph (a single ``db.get`` took ~50 s). The daily page
    #: only ever needs the AFE's code.
    afe: Mapped[Afe | None] = relationship("Afe", lazy="select")

    service_lines: Mapped[list["DailyCostServiceLine"]] = relationship(
        "DailyCostServiceLine",
        back_populates="entry",
        lazy="selectin",
        order_by="DailyCostServiceLine.sort_order",
        cascade="all, delete-orphan",
    )
    consumable_lines: Mapped[list["DailyCostConsumableLine"]] = relationship(
        "DailyCostConsumableLine",
        back_populates="entry",
        lazy="selectin",
        order_by="DailyCostConsumableLine.sort_order",
        cascade="all, delete-orphan",
    )
    tangible_lines: Mapped[list["DailyCostTangibleLine"]] = relationship(
        "DailyCostTangibleLine",
        back_populates="entry",
        lazy="selectin",
        order_by="DailyCostTangibleLine.sort_order",
        cascade="all, delete-orphan",
    )


class DailyCostServiceLine(Base, TimestampMixin, AuditMixin):
    """One service worked during one day.

    ``charging_basis`` and ``charge_category`` decide which AFE unit rate was
    captured:

    * **Daily Rate** — the rate of the chosen charge category (Mobilization,
      Demobilization, Operation, Standby, Personnel-Operation,
      Personnel-Standby, Fixed Charge, Others). Mobilization, Demobilization
      and Fixed Charge are one-time amounts and are never multiplied by the
      entered hours/days.
    * **Per Service Rate** — the price the AFE allotted to that service.
    * **Per Section Rate** — the amount the AFE configured for the selected
      section (and, when given, that phase).

    ``quantity`` is the operating time, entered in hours (0-24) or in decimal
    days (0-1) as recorded by ``quantity_unit``. ``amount`` is the server-side
    priced result, persisted so reports and analytics read a stored figure
    instead of recomputing history.
    """

    __tablename__ = "daily_cost_service_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("daily_cost_entries.id"), nullable=False, index=True
    )
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), nullable=False, index=True)
    #: The AFE line the rate was captured from (None when the service is not
    #: on the AFE and the rate was entered manually).
    afe_line_id: Mapped[int | None] = mapped_column(
        ForeignKey("afe_service_lines.id"), nullable=True, index=True
    )
    charging_basis: Mapped[str] = mapped_column(String(30), nullable=False)
    charge_category: Mapped[str] = mapped_column(
        String(40), default="Operation", server_default="Operation", nullable=False
    )
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("hole_sections.id"), nullable=True, index=True
    )
    phase_id: Mapped[int | None] = mapped_column(
        ForeignKey("phases.id"), nullable=True, index=True
    )
    sub_activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("well_sub_activities.id"), nullable=True, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), server_default="0", nullable=False
    )
    quantity_unit: Mapped[str] = mapped_column(
        String(10), default="hours", server_default="hours", nullable=False
    )  # hours | days
    captured_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0", nullable=False
    )
    override_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0", nullable=False
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    entry: Mapped[DailyCostEntry] = relationship(
        "DailyCostEntry", back_populates="service_lines", lazy="select"
    )
    service: Mapped[Service] = relationship("Service", lazy="joined")
    # ``afe_line_id`` is provenance only (which AFE line supplied the rate) —
    # no relationship, so loading a day never drags the AFE's estimate lines
    # and their rate collections into the query.
    sub_activity: Mapped[WellSubActivity | None] = relationship("WellSubActivity", lazy="joined")


class DailyCostConsumableLine(Base, TimestampMixin, AuditMixin):
    """One consumable used during one day.

    ``category`` selects which of the four consumable groups the line belongs
    to. Mud chemicals and drill bits pick an item from the Master Data /
    catalogue lists (``item_id`` + snapshotted code/name/UOM), fuel takes the
    unit rate captured on the AFE cost estimate, and cement additives record a
    manual ``manual_amount`` for the chosen section / phase / sub activity.
    """

    __tablename__ = "daily_cost_consumable_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("daily_cost_entries.id"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    item_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    item_code: Mapped[str] = mapped_column(String(50), nullable=False)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), default=Decimal("0"), server_default="0", nullable=False
    )
    uom: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    captured_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0", nullable=False
    )
    override_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    #: Cement additives: the total consumption cost entered by the user.
    manual_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0", nullable=False
    )
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("hole_sections.id"), nullable=True, index=True
    )
    phase_id: Mapped[int | None] = mapped_column(
        ForeignKey("phases.id"), nullable=True, index=True
    )
    sub_activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("well_sub_activities.id"), nullable=True, index=True
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    entry: Mapped[DailyCostEntry] = relationship(
        "DailyCostEntry", back_populates="consumable_lines", lazy="select"
    )
    sub_activity: Mapped[WellSubActivity | None] = relationship("WellSubActivity", lazy="joined")


class DailyCostTangibleLine(Base, TimestampMixin, AuditMixin):
    """One tangible recorded against a day.

    Tangibles are normally entered as a block at the end of the well rather
    than day by day, and the list always comes from **Master Data** — never
    from the AFE — because a tangible planned in the AFE may have been damaged
    and a different one actually used.
    """

    __tablename__ = "daily_cost_tangible_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("daily_cost_entries.id"), nullable=False, index=True
    )
    tangible_id: Mapped[int] = mapped_column(ForeignKey("tangibles.id"), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), default=Decimal("1"), server_default="1", nullable=False
    )
    uom: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    captured_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0", nullable=False
    )
    override_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), server_default="0", nullable=False
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    entry: Mapped[DailyCostEntry] = relationship(
        "DailyCostEntry", back_populates="tangible_lines", lazy="select"
    )
    tangible: Mapped[Tangible] = relationship("Tangible", lazy="joined")
