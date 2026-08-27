"""Rate revision helpers for Mud Chemicals, Drill Bits and Tangibles.

Each priced item owns an append-only revision history. Creating an item records
revision #1; updating the rate fields appends a new revision whenever the rate
actually changes. The item's denormalised ``current_*`` fields always mirror
the latest revision so list views read a single row ("the current price is the
effective one").
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalogue import (
    DrillBit,
    DrillBitRate,
    MudChemical,
    MudChemicalRate,
    Tangible,
    TangibleRate,
)
from app.models.user import User
from app.services.import_helpers import final_cost


def _today() -> date:
    return date.today()


def add_mud_chemical_revision(
    db: Session,
    chemical: MudChemical,
    *,
    unit_rate: Decimal,
    currency: str | None,
    uom: str | None,
    effective_date: date | None,
    remarks: str | None = None,
    user: User | None = None,
    force: bool = False,
) -> MudChemicalRate | None:
    """Append a mud chemical rate revision when the rate changes."""

    latest = db.scalar(
        select(MudChemicalRate)
        .where(MudChemicalRate.chemical_id == chemical.id, MudChemicalRate.is_deleted == False)
        .order_by(MudChemicalRate.revision_number.desc())
    )
    previous = latest.unit_rate if latest else Decimal("0")
    if latest and not force and latest.unit_rate == unit_rate and latest.currency == (currency or None):
        # Same price — keep history clean but refresh display fields.
        chemical.current_rate = unit_rate
        chemical.currency = currency
        chemical.uom = uom or chemical.uom
        return None

    revision = MudChemicalRate(
        chemical_id=chemical.id,
        unit_rate=unit_rate,
        previous_rate=previous,
        currency=currency,
        uom=uom or (latest.uom if latest else chemical.uom),
        effective_date=effective_date or (latest.effective_date if latest else _today()),
        revision_number=(latest.revision_number + 1) if latest else 1,
        remarks=remarks,
        created_by=user.id if user else None,
        updated_by=user.id if user else None,
    )
    db.add(revision)
    chemical.current_rate = unit_rate
    chemical.currency = currency
    chemical.uom = revision.uom
    chemical.effective_date = revision.effective_date
    return revision


def add_drill_bit_revision(
    db: Session,
    bit: DrillBit,
    *,
    unit_rate_po: Decimal,
    cost_uplift: Decimal,
    currency: str | None,
    effective_date: date | None,
    po_number: str | None = None,
    remarks: str | None = None,
    user: User | None = None,
    force: bool = False,
) -> DrillBitRate | None:
    """Append a drill bit rate revision when the rate/uplift changes."""

    latest = db.scalar(
        select(DrillBitRate)
        .where(DrillBitRate.bit_id == bit.id, DrillBitRate.is_deleted == False)
        .order_by(DrillBitRate.revision_number.desc())
    )
    new_final = final_cost(unit_rate_po, cost_uplift)
    if latest and not force and latest.unit_rate_po == unit_rate_po and latest.cost_uplift == cost_uplift:
        bit.unit_rate_po = unit_rate_po
        bit.cost_uplift = cost_uplift
        bit.final_cost = new_final
        return None

    revision = DrillBitRate(
        bit_id=bit.id,
        unit_rate_po=unit_rate_po,
        cost_uplift=cost_uplift,
        final_cost=new_final,
        currency=currency,
        effective_date=effective_date or (latest.effective_date if latest else _today()),
        revision_number=(latest.revision_number + 1) if latest else 1,
        po_number=po_number,
        remarks=remarks,
        created_by=user.id if user else None,
        updated_by=user.id if user else None,
    )
    db.add(revision)
    bit.unit_rate_po = unit_rate_po
    bit.cost_uplift = cost_uplift
    bit.final_cost = new_final
    bit.currency = currency
    bit.effective_date = revision.effective_date
    if po_number:
        bit.po_number = po_number
    return revision


def add_tangible_revision(
    db: Session,
    tangible: Tangible,
    *,
    unit_rate_po: Decimal,
    cost_uplift: Decimal,
    currency: str | None,
    effective_date: date | None,
    po_number: str | None = None,
    remarks: str | None = None,
    user: User | None = None,
    force: bool = False,
) -> TangibleRate | None:
    """Append a tangible rate revision when the rate/uplift changes."""

    latest = db.scalar(
        select(TangibleRate)
        .where(TangibleRate.tangible_id == tangible.id, TangibleRate.is_deleted == False)
        .order_by(TangibleRate.revision_number.desc())
    )
    new_final = final_cost(unit_rate_po, cost_uplift)
    if latest and not force and latest.unit_rate_po == unit_rate_po and latest.cost_uplift == cost_uplift:
        tangible.unit_rate_po = unit_rate_po
        tangible.cost_uplift = cost_uplift
        tangible.final_cost = new_final
        return None

    revision = TangibleRate(
        tangible_id=tangible.id,
        unit_rate_po=unit_rate_po,
        cost_uplift=cost_uplift,
        final_cost=new_final,
        currency=currency,
        effective_date=effective_date or (latest.effective_date if latest else _today()),
        revision_number=(latest.revision_number + 1) if latest else 1,
        po_number=po_number,
        remarks=remarks,
        created_by=user.id if user else None,
        updated_by=user.id if user else None,
    )
    db.add(revision)
    tangible.unit_rate_po = unit_rate_po
    tangible.cost_uplift = cost_uplift
    tangible.final_cost = new_final
    tangible.currency = currency
    tangible.effective_date = revision.effective_date
    if po_number:
        tangible.po_number = po_number
    return revision
